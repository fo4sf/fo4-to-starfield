"""Codsworth structural dump (read-only, PC): the layouts the model rebind needs, as text.

    python scripts/actors/codsworth_dump.py --fo4-data "<FO4 Data>" --sf-data "<Starfield Data>" --out <dir>

1. Starfield mini bot NIFs (minibota_mesh, minibota_base, minibota_gardening, skeleton.nif): every block's index,
   type, size and name; BSGeometry mesh refs and bounds; BSSkin::Instance bone names; BSSkin::BoneData size and the
   first entry's raw floats (to confirm whether Starfield keeps FO4's 68-byte entry); each referenced .mesh parsed
   with fo4sf.sfmesh (version, scale, weights per vertex, counts, bones used, decoded bounds).
2. FO4 mrhandy.nif: every shape with vertex count, skin bone list and per-bone vertex counts by heaviest weight;
   bone world positions in the bind pose.
3. Voice: every FO4 voice-type folder whose name has robot/handy/codsworth, with counts, and the FO4 Codsworth
   voice type folder's first file names; the Starfield RobotMiniBotA folder if any.
4. Starfield Tools: wwise, LipGenerator, FaceFX and RoboVoicer file names (depth 2).
Writes <out>/codsworth_dump.txt and prints its first 7000 characters.
"""
import argparse
import glob
import os
import struct
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf import fo4skin, nif as nifmod, sfmesh, sfnif  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402

SF_NIFS = ("meshes\\actors\\minibota\\mesh\\minibota_base\\minibota_mesh.nif",
           "meshes\\actors\\minibota\\mesh\\minibota_base\\minibota_base.nif",
           "meshes\\actors\\minibota\\mesh\\minibota_gardening\\minibota_gardening.nif",
           "meshes\\actors\\minibota\\characterassets\\skeleton.nif")
FO4_NIF = "meshes\\actors\\robot\\characterassets\\mrhandy.nif"


class Archives:
    def __init__(self, data_dir, pattern):
        self.index = {}
        for path in sorted(glob.glob(os.path.join(data_dir, pattern))):
            a = Ba2(path)
            for e in a.entries:
                self.index.setdefault(e.name.lower().replace("/", "\\"), a)

    def find(self, suffix):
        suffix = suffix.lower().replace("/", "\\")
        return [k for k in self.index if k.endswith(suffix)]

    def read(self, name):
        a = self.index[name]
        return a.read(next(e.name for e in a.entries if e.name.lower().replace("/", "\\") == name))


def name_of(n, i):
    b = n.blocks[i]
    if len(b) < 4:
        return ""
    k, = struct.unpack_from("<i", b, 0)
    return n.strings[k].decode("latin-1") if 0 <= k < len(n.strings) else ""


def dump_sf_nif(out, arch, meshes, name):
    hits = [k for k in arch.index if k.endswith(name.split("\\")[-1])]
    if not hits:
        out.append(f"!! {name} not found")
        return
    key = name if name in arch.index else hits[0]
    n = nifmod.parse(arch.read(key))
    out.append(f"== {key} bs{n.bs_version} blocks={len(n.blocks)}")
    for i in range(len(n.blocks)):
        t, b = n.type_of(i), n.blocks[i]
        line = f"[{i}] {t} {len(b)}B"
        if t in ("NiNode", "BSFadeNode", "BSGeometry", "BSLightingShaderProperty", "NiIntegerExtraData"):
            line += f" '{name_of(n, i)}'"
        if t == "BSGeometry":
            try:
                g = sfnif.parse_bsgeometry(b)
                line += f" skin={g.skin} shader={g.shader} flags={g.flags:#x} sphere={tuple(round(v, 3) for v in g.sphere)}"
                for lod, m in enumerate(g.meshes):
                    if m:
                        path = m.path.decode("latin-1")
                        line += f"\n    mesh{lod} {path} isz={m.indices_size} nv={m.num_verts} fl={m.flags:#x}"
                        if lod == 0:
                            line += "\n    " + describe_mesh(meshes, path)
            except Exception as e:
                line += f" PARSE {e}"
        elif t == "BSSkin::Instance":
            root, data, count = struct.unpack_from("<iiI", b, 0)
            bones = struct.unpack_from(f"<{count}i", b, 12)
            line += f" root={root} data={data} bones={[name_of(n, p) for p in bones]} tail={len(b) - 12 - 4 * count}B"
        elif t == "BSSkin::BoneData":
            count, = struct.unpack_from("<I", b, 0)
            per = (len(b) - 4) / count if count else 0
            line += f" count={count} bytes/entry={per}"
            if count and per >= 68:
                line += f" first={tuple(round(v, 4) for v in struct.unpack_from('<17f', b, 4))}"
        out.append(line)
    world = nifmod.world_transforms(n)
    nodes = [(name_of(n, i), tuple(round(v, 3) for v in world(i)[0])) for i in range(len(n.blocks))
             if n.type_of(i) in ("NiNode", "BSFadeNode")]
    out.append(f"  node world positions: {nodes[:40]}")


def describe_mesh(meshes, path):
    rel = "geometries\\" + path.replace("/", "\\").lower() + ".mesh"
    if rel not in meshes.index:
        return f"(mesh {rel} not in archives)"
    m = sfmesh.parse(meshes.read(rel))
    pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
    lo = tuple(round(min(p[k] for p in pts), 3) for k in range(3)) if pts else ()
    hi = tuple(round(max(p[k] for p in pts), 3) for k in range(3)) if pts else ()
    used = Counter(b for b, w in m.weights if w)
    return (f"v{m.version} scale={m.scale:.4f} wpv={m.weights_per_vertex} verts={len(m.positions)} tris={len(m.triangles)}"
            f" uv2={len(m.uv2)} colors={len(m.colors)} lods={len(m.lods)} meshlets={len(m.meshlets)} bounds={lo}..{hi}"
            f" bone_slots_used={dict(sorted(used.items()))} first_weights={m.weights[:8]}")


def dump_fo4(out, arch):
    hits = arch.find(FO4_NIF)
    if not hits:
        out.append(f"!! {FO4_NIF} not found")
        return
    n = nifmod.parse(arch.read(hits[0]))
    out.append(f"== {hits[0]} bs{n.bs_version}")
    for s in nifmod.fo4_trishapes(n):
        skin = fo4skin.read_skin(n, s.block)
        line = f"shape {s.name.decode('latin-1')} verts={len(s.positions)} tris={len(s.triangles)} skinned={bool(skin)}"
        if skin:
            heavy = Counter()
            for w, ix in zip(skin.weights, skin.indices):
                k = max(range(4), key=lambda j: w[j])
                heavy[skin.bone_names[ix[k]].decode("latin-1")] += 1
            line += f" bones={len(skin.bones)} heaviest={dict(heavy.most_common())}"
            bw = fo4skin.bind_world(skin)
            line += f"\n    bind bone positions: {[(skin.bone_names[i].decode('latin-1'), tuple(round(v, 1) for v in bw[i][0])) for i in range(len(skin.bones))]}"
            pts = s.positions
            line += f"\n    bounds {tuple(round(min(p[k] for p in pts), 1) for k in range(3))}..{tuple(round(max(p[k] for p in pts), 1) for k in range(3))}"
        out.append(line)


def dump_voices(out, data_dir, pattern, keys):
    folders = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(data_dir, pattern))):
        for e in Ba2(path).entries:
            parts = e.name.lower().replace("/", "\\").split("\\")
            if len(parts) >= 5 and parts[0] == "sound" and parts[1] == "voice" and any(k in parts[3] for k in keys):
                folders[f"{os.path.basename(path)}:{parts[2]}\\{parts[3]}"].append(parts[-1])
    out.append(f"== voices {pattern} {keys}: {len(folders)} folders")
    for k, v in sorted(folders.items(), key=lambda kv: -len(kv[1])):
        out.append(f"{k}: {len(v)} {dict(Counter(os.path.splitext(x)[1] for x in v))} e.g. {sorted(v)[:4]}")


def dump_tools(out, sf_data):
    root = os.path.normpath(os.path.join(sf_data, "..", "Tools"))
    out.append(f"== tools under {root}")
    for sub in ("wwise", "LipGenerator", "FaceFX", "RoboVoicer"):
        for d in glob.glob(os.path.join(root, sub + "*")):
            for dirpath, dirs, files in os.walk(d):
                depth = dirpath[len(d):].count(os.sep)
                if depth > 2:
                    continue
                out.append(f"{os.path.relpath(dirpath, root)}: {sorted(files)[:25]}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fo4-data", required=True)
    p.add_argument("--sf-data", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    out = []
    sf = Archives(a.sf_data, "Starfield - Meshes*.ba2")
    for name in SF_NIFS:
        try:
            dump_sf_nif(out, sf, sf, name)
        except Exception as e:
            out.append(f"!! {name}: {type(e).__name__} {e}")
    try:
        dump_fo4(out, Archives(a.fo4_data, "Fallout4 - Meshes*.ba2"))
    except Exception as e:
        out.append(f"!! fo4: {type(e).__name__} {e}")
    dump_voices(out, a.fo4_data, "Fallout4 - Voices*.ba2", ("robot", "handy", "codsworth"))
    dump_voices(out, a.sf_data, "Starfield - Voices*.ba2", ("minibot",))
    dump_tools(out, a.sf_data)
    text = "\n".join(out)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "codsworth_dump.txt"), "w") as f:
        f.write(text)
    print(text[:7000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
