"""Per-part door audit: does every part the FO4 door moves still move after conversion, with its own moving body?

For each manifest door the FO4 source's "Open" targets that carry geometry (door_motion.inspect) are its parts.
- Template doors (the single-hinge vanilla rig, sfnif.DOOR_TEMPLATE): the first part (nif.door_hinge) rides the template
  hinge; another part moves only if its geometry is below that node (a knob on the leaf). Every other part is frozen.
- Doors with their own rig (manifest door "rig": "native"): each part must have a track in the Open AND Close clip and a
  moving body on its node or below it in the converted NIF. --dll reads the clips back with the external CALUMI
  library; without it the manifest's animated_bones stand in for the tracks and the report says "tracks": "manifest".
Exit 1 when any part is frozen, untracked or without a moving body. Offline evidence only: not an in-game result.

usage: python scripts/oracles/door_panels.py --manifest <staging>/manifest.json --staging <staging> --fo4-data <FO4 Data>
       [--dll CALUMI.Animation.dll] [--only <regex on the source path>]
"""
import argparse
import ctypes as c
import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fo4sf import door_motion, nif, pipeline  # noqa: E402

MOVING_LAYER = 2        # collision layer word at offset 240 of a keyframed leaf box (ANIMSTATIC), as door_bodies.py


def source_parts(fo4_nif):
    """[(part name, moves with the template hinge)] for the FO4 "Open" targets that have geometry below them."""
    src = nif.parse(fo4_nif)
    report = door_motion.inspect(src)
    outside = set(report["animated_shapes_outside_single_hinge"])
    parts = []
    for seq in report["sequences"]:
        if seq["name"] != "Open":
            continue
        for t in seq["targets"]:
            if t["shape_blocks"] and t["name"] not in [p[0] for p in parts]:
                parts.append((t["name"], not (outside & set(t["shape_blocks"]))))
    return parts


def model_bodies(sf_nif):
    """{node name: True if a moving body sits on that node or below it} for every named node of a converted NIF."""
    f = nif.parse(sf_nif)
    names, bodies = {}, set()
    for i, block in enumerate(f.blocks):
        kind = f.type_of(i)
        if kind == "NiNode":
            names[f.strings[struct.unpack_from("<i", block)[0]].decode("latin-1")] = i
        elif kind == "bhkNPCollisionObject":
            target, _, system = struct.unpack_from("<iHi", block)
            blob = f.blocks[system][4:] if 0 <= system < len(f.blocks) else b""
            if len(blob) >= 244 and struct.unpack_from("<I", blob, 240)[0] == MOVING_LAYER:
                bodies.add(target)
    return {name: bool(nif.descendants(f, i) & bodies) for name, i in names.items()}


def assess(parts, kind, tracks, bodies, template_body=False):
    """parts: source_parts(); kind 'template' or 'native'; tracks: {'Open': set, 'Close': set} of bone names (native);
    bodies: model_bodies() (native); template_body: the template leaf node carries a moving body. Returns part rows."""
    rows = []
    for name, rides_hinge in parts:
        if kind == "template":
            ok = rides_hinge
            row = {"part": name, "track_open": ok, "track_close": ok, "body": ok and template_body}
        else:
            row = {"part": name, "track_open": name in tracks.get("Open", set()),
                   "track_close": name in tracks.get("Close", set()), "body": bodies.get(name, False)}
        row["status"] = ("moves" if row["track_open"] and row["track_close"] and row["body"] else
                         "frozen" if not (row["track_open"] or row["track_close"]) else
                         "no body" if not row["body"] else "missing a clip")
        rows.append(row)
    return rows


def clip_tracks(dll, rig, clips):
    """{clip name: set of bone names with keys} read back with CALUMI (LoadAnimationSceneFromSFBGSFormatC)."""
    lib = c.CDLL(str(Path(dll).resolve()))
    def bind(name, args, result):
        fn = getattr(lib, name); fn.argtypes = args; fn.restype = result; return fn
    p = c.c_void_p
    error = bind("CreateStringContainerC", [], p)()
    load = bind("LoadAnimationSceneFromSFBGSFormatC", [c.POINTER(c.c_wchar_p), c.c_int, p], p)
    out = {}
    try:
        for name, path in clips.items():
            scene = load((c.c_wchar_p * 2)(str(rig), str(path)), 2, error)
            if not scene:
                raise RuntimeError(f"CALUMI could not read {path}")
            try:
                anim = bind("GetAnimationC", [p, c.c_int, p], p)(scene, 0, error)
                count = bind("GetAnimationBlockCountC", [p], c.c_size_t)(anim)
                block_at = bind("GetAnimationBlockC", [p, c.c_int, p], p)
                bone = bind("GetAnimBlockBoneNameC", [p], c.c_char_p)
                rotations = bind("GetRotationSqSizeC", [p], c.c_size_t)
                translations = bind("GetTranslationSqSizeC", [p], c.c_size_t)
                out[name] = set()
                for k in range(count):
                    block = block_at(anim, k, error)
                    if rotations(block) or translations(block):
                        out[name].add(bone(block).decode("latin-1"))
            finally:
                bind("DeleteAnimationSceneC", [p], c.c_bool)(scene)
    finally:
        bind("DeleteStringContainerC", [p], None)(error)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--fo4-data", required=True)
    parser.add_argument("--dll", default="")
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    src = pipeline.Fo4Archives(args.fo4_data)
    meshes = (args.staging / "meshes").resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    only = re.compile(args.only, re.I) if args.only else None
    reports = []
    for item in manifest["items"]:
        door = item.get("door")
        if not door or (only and not only.search(item["source"])):
            continue
        report = {"source": item["source"]}
        try:
            parts = source_parts(src.mesh(item["source"]))
            if len(parts) < 2 and not item.get("door_frozen_parts"):
                continue                                          # single-part door: not this audit's subject
            model = (meshes / item["model"].replace("\\", "/")).resolve()
            if not model.is_relative_to(meshes):
                raise ValueError("model path escapes staging meshes")
            bodies = model_bodies(model.read_bytes())
            if door.get("rig") == "native":
                folder = (meshes / door["animations"].replace("\\", "/")).resolve()
                rig = (meshes / door["skeleton"].replace("\\", "/")).resolve()
                if not (folder.is_relative_to(meshes) and rig.is_relative_to(meshes)):
                    raise ValueError("rig or clip path escapes staging meshes")
                if args.dll:
                    tracks = clip_tracks(args.dll, rig, {n: folder / f"{n}.af" for n in ("Open", "Close")})
                    report["tracks"] = "read back"
                else:
                    tracks = {n: set(door.get("animated_bones", [])) for n in ("Open", "Close")}
                    report["tracks"] = "manifest"
                report.update(kind="native", parts=assess(parts, "native", tracks, bodies))
            else:
                report.update(kind="template", parts=assess(parts, "template", {}, {},
                                                             template_body=bodies.get("mesh001", False)))
        except (ValueError, OSError, RuntimeError, nif.NifError, struct.error) as error:
            report.update(kind="error", parts=[], error=f"{type(error).__name__}: {error}")
        report["ok"] = bool(report["parts"]) and all(p["status"] == "moves" for p in report["parts"])
        reports.append(report)
    summary = {"doors": len(reports), "ok": sum(r["ok"] for r in reports),
               "parts": sum(len(r["parts"]) for r in reports),
               "parts_moving": sum(p["status"] == "moves" for r in reports for p in r["parts"])}
    print(json.dumps({"summary": summary, "reports": reports}, indent=1))
    return int(not reports or not all(r["ok"] for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())
