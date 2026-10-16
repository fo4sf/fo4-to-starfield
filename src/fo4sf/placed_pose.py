"""Per-reference poses: a placed FO4 reference whose ragdoll data (XRGD) lays its model out differently from the NIF's
own node pose gets a converted model of its own, built in that pose.

FO4 keeps the pose a placed ragdoll lies in (skeletons, mannequins, destructible saw horses, hanging lamps) on the
reference, not in the model (docs/ai/research-log.md 2026-10-11 "XRGD ragdoll pose decoded"; ragdoll_pose). A converted
model is shared by every reference of its base, so a reference whose pose moves the model gets a variant: the same source
NIF converted with its bone nodes' local transforms replaced by the entries (convert_static pose=...). The variant is named
after the base plus a hash of the pose, so equal poses share one variant and a rebuild keeps the name (the plugin writer
keys its stable FormIDs by editor ID). References whose entries do not fit the model (stale XRGD, no bodies, a body on the
scene root) or leave its vertices where the node pose has them (moved body nodes alone would only misplace the collision)
keep the shared model; plan() counts each case.

Only articulated models are posed (MIN_BODIES: two or more bodies in the system, i.e. skeletons, mannequins, saw horses,
barriers, chains), the case the decoder's frames were checked on (joint lengths and hinge axes, research log 2026-10-11).
A single-body loose item (bottle, pen, pillow) also carries XRGD; its one entry would turn and shift the whole item
against its reference, which is not checked yet (no resting test for root bodies), and the item is movable here anyway,
so it keeps the shared model and is counted as "single_body".

    variants, stats = placed_pose.plan(cell_refs, {source.lower(): manifest_item}, read_nif_bytes)
    for v in variants:
        converter.convert_nif(v.source, pose=v.overrides, out_suffix=v.suffix)
"""
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from . import convert_static, nif as nifmod, ragdoll_pose

POSE_EPSILON = 0.5          # game units (7 mm): a pose that moves no vertex further keeps the shared model (body nodes
                            # alone carry only collision: moving them without the mesh would misplace it, PR #244 review)
MIN_BODIES = 2              # articulated models only (see above)
SUFFIX = "_xrgd_"


@dataclass
class Variant:
    source: str                              # FO4 NIF path as in the manifest ("meshes\\...")
    key: str                                 # pose hash (pose_key)
    overrides: Dict[int, tuple]              # ragdoll_pose.local_overrides: {node block: (t, R, s)}
    shift: float                             # largest move of a vertex or body node against the node pose, game units
    refs: List[str] = field(default_factory=list)   # FO4 FormKeys of the references placed with this variant

    @property
    def suffix(self) -> str:
        return SUFFIX + self.key


def pose_key(ragdoll) -> str:
    """Stable 10-hex hash of a reference's ragdoll entries (cell-export dicts): positions to 0.001 units, rotations to
    1e-5 rad, in index order. The uninitialised first 4 bytes of each entry (bone_id / unused) are left out."""
    entries = ragdoll_pose.entries_from_export(ragdoll)
    canon = [[round(v, 3) + 0.0 for v in e.position] + [round(v, 5) + 0.0 for v in e.rotation] for e in entries]
    return hashlib.sha1(json.dumps(canon, separators=(",", ":")).encode()).hexdigest()[:10]


def _points(n: nifmod.NifFile, pose: Optional[dict]) -> Tuple[List[tuple], Dict[int, tuple]]:
    """(vertex positions used by triangles, in NIF space after skinning; {body node block: world origin}) in the node
    pose (pose None) or with the reference's local overrides. Same frame as convert_static (placed=True)."""
    world = nifmod.world_transforms(n, placed=True, local_overrides=pose)
    shapes = [s for s in nifmod.fo4_trishapes(n, placed=True, local_overrides=pose) if s.positions and s.triangles]
    shapes = convert_static.pose_skinned_shapes(n, shapes, None, world)
    pts = []
    for s in shapes:
        r, t, k = s.rotation, s.translation, s.scale
        used = sorted({v for tri in s.triangles for v in tri if v < len(s.positions)})
        for v in used:
            x, y, z = s.positions[v]
            pts.append(tuple(k * (r[3 * a] * x + r[3 * a + 1] * y + r[3 * a + 2] * z) + t[a] for a in range(3)))
    nodes = {}
    try:
        _, body_node = ragdoll_pose.ragdoll_nodes(n)
        nodes = {node: tuple(world(node)[0]) for node in body_node.values()}
    except ragdoll_pose.RagdollPoseError:
        pass
    return pts, nodes


def pose_shifts(n: nifmod.NifFile, pose: dict, baseline=None) -> Tuple[float, float]:
    """(largest vertex move, largest body node move) in game units between the node pose and `pose`."""
    base_pts, base_nodes = baseline or _points(n, None)
    pts, nodes = _points(n, pose)
    if len(pts) != len(base_pts):
        return math.inf, math.inf
    verts = max((math.dist(p, q) for p, q in zip(pts, base_pts)), default=0.0)
    bodies = max((math.dist(o, base_nodes[k]) for k, o in nodes.items() if k in base_nodes), default=0.0)
    return verts, bodies


def pose_shift(n: nifmod.NifFile, pose: dict, baseline=None) -> float:
    """Largest distance (game units) any vertex or body node moves between the node pose and `pose`."""
    return max(pose_shifts(n, pose, baseline))


def _reason(e: Exception) -> str:
    return re.sub(r"\d+(\.\d+)?", "N", str(e))


def plan(refs: Iterable[Mapping], models: Mapping[str, Mapping], read_nif: Callable[[str], Optional[bytes]],
         min_shift: float = POSE_EPSILON, min_bodies: int = MIN_BODIES) -> Tuple[List[Variant], dict]:
    """Variants to convert for the references that carry ragdoll data.
    refs: cell-export references (formkey, model, ragdoll). models: converted manifest items by lower-case source path
    ("meshes\\..."); door and load-door items are never posed. read_nif(source) -> FO4 NIF bytes.
    Returns (variants sorted by source and key, stats): stats counts every reference with ragdoll data once, under
    posed / unchanged (no vertex moves min_shift or more from the node pose; moved body nodes alone do not count) /
    single_body (fewer than min_bodies bodies) / rejected (reason; also a multi-body pose with a body on the scene root) /
    not_converted / door."""
    stats = {"refs_with_ragdoll": 0, "posed_refs": 0, "variants": 0, "unchanged": 0, "single_body": 0, "not_converted": 0,
             "door": 0, "rejected": {}}
    parsed: Dict[str, Optional[nifmod.NifFile]] = {}
    baselines: Dict[str, tuple] = {}
    variants: Dict[Tuple[str, str], Variant] = {}
    unchanged: Dict[Tuple[str, str], str] = {}          # (source, key) -> "unchanged" / "single_body"

    def reject(reason):
        stats["rejected"][reason] = stats["rejected"].get(reason, 0) + 1

    for r in refs:
        ragdoll = r.get("ragdoll")
        if not ragdoll:
            continue
        stats["refs_with_ragdoll"] += 1
        model = r.get("model") or ""
        source = ("meshes\\" + model.lstrip("\\")).replace("/", "\\")
        item = models.get(source.lower()) if model else None
        if item is None:
            stats["not_converted"] += 1
            continue
        if "door" in item or "load_door" in item:
            stats["door"] += 1
            continue
        source = item.get("source", source)
        try:
            key = pose_key(ragdoll)
        except (ragdoll_pose.RagdollPoseError, KeyError, TypeError, ValueError) as e:
            reject(f"unreadable ragdoll export: {_reason(e)}")
            continue
        ident = (source.lower(), key)
        if ident in unchanged:
            stats[unchanged[ident]] += 1
            continue
        if ident not in variants:
            if source.lower() not in parsed:
                raw = read_nif(source)
                try:
                    parsed[source.lower()] = nifmod.parse(raw) if raw else None
                except nifmod.NifError:
                    parsed[source.lower()] = None
            n = parsed[source.lower()]
            if n is None:
                reject("source NIF unreadable")
                continue
            try:
                overrides = ragdoll_pose.local_overrides(n, ragdoll)
                if len(overrides) < min_bodies:
                    unchanged[ident] = "single_body"
                    stats["single_body"] += 1
                    continue
                if set(overrides) & ({0} | set(nifmod.footer_roots(n))):
                    # a body on the scene root: the pose would move every shape, but convert_static keeps a root body
                    # in place (and the root frame of an entry is unchecked), so mesh and collision would part
                    reject("body on the scene root")
                    continue
                if source.lower() not in baselines:
                    baselines[source.lower()] = _points(n, None)
                verts, bodies = pose_shifts(n, overrides, baselines[source.lower()])
                shift = max(verts, bodies)
            except (ragdoll_pose.RagdollPoseError, nifmod.NifError, ValueError) as e:
                reject(_reason(e))
                continue
            if verts < min_shift:           # bodies alone (stale XRGD with a fitting entry count): collision only
                unchanged[ident] = "unchanged"
                stats["unchanged"] += 1
                continue
            variants[ident] = Variant(source, key, overrides, shift)
        variants[ident].refs.append(r["formkey"])
        stats["posed_refs"] += 1
    out = sorted(variants.values(), key=lambda v: (v.source.lower(), v.key))
    stats["variants"] = len(out)
    return out, stats
