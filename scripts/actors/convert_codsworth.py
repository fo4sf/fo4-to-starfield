"""Codsworth's FO4 model on the Starfield garden mini bot's skeleton (fo4sf.actor_rebind), into a staging folder.

    python scripts/actors/convert_codsworth.py --fo4-data "<FO4 Data>" --sf-data "<Starfield Data>" --staging <dir>
        --content-resources "<Starfield>\\Tools\\ContentResources.zip" --texconv <texconv.exe> [--animate-arms]

Source Meshes\\Actors\\Robot\\CharacterAssets\\MrHandy.nif (Torso, Legs, HandyShell, Arms:0, Arms:1; 63 skin bones),
template Meshes\\Actors\\MiniBotA\\Mesh\\minibota_base\\minibota_mesh.nif (one weight per vertex; bones C_Chassis,
C_Arm1-3, C_Base, C_Axle, C_Hatch), both verified on the PC 2026-10-18 (codsworth_dump.py). Materials and textures go
through pipeline.Converter exactly as the statics do. Everything is built in a fresh <staging>.partial-* folder, renamed
to <staging> only once complete (a failed attempt's folder is kept as evidence, never cleaned up); <staging> must be new or empty, so an earlier stage is never overwritten. Writes:
    meshes/fo4port/actors/codsworth/codsworth.nif, geometries/<hash>/<hash>.mesh, materials/..., textures/...
    codsworth_report.json
Bone map: Pelvis (the thruster) -> C_Base, everything else -> C_Chassis. With --animate-arms the three arm chains
(LArm*, MArm*, RArm* with their palms) go to C_Arm1..3, which then swing about the mini bot's arm roots, not Codsworth's.
The plugin side (an ARMA/ARMO whose model is this NIF, set as Codsworth's skin) belongs to the mission build.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf import actor_rebind, ba2, convert_material, nif, pipeline  # noqa: E402

SOURCE = "meshes\\actors\\robot\\characterassets\\mrhandy.nif"
TEMPLATE = "meshes\\actors\\minibota\\mesh\\minibota_base\\minibota_mesh.nif"
OUT_NAME = "fo4port/actors/codsworth/codsworth"
ARMS = (("LArm", "C_Arm1"), ("MArm", "C_Arm2"), ("RArm", "C_Arm3"))
HANDY_LENS_BGEM = "materials\\actors\\robot\\handylens.bgem"
CODSWORTH_STEEL_TINT = (0.88, 0.90, 0.92, 0.72)
CODSWORTH_METALNESS = 0.85
CODSWORTH_FALLBACK_ROUGHNESS = 0.45


def _roughness_texture_file(mat: dict) -> str:
    """Return the non-empty Roughness texture path from Objects (MRTextureFile idx 3) or Summary, else ''."""
    for obj in mat.get("Objects") or []:
        for c in obj.get("Components") or []:
            if c.get("Type") == "BSMaterial::MRTextureFile" and c.get("Index") == 3:
                fn = (c.get("Data") or {}).get("FileName") or ""
                if isinstance(fn, str) and fn.strip():
                    return fn.strip()
    layer = (mat.get("Summary") or {}).get("Layer1") or {}
    r = ((layer.get("Textures") or {}).get("Roughness") or {}).get("File") or ""
    return r.strip() if isinstance(r, str) else ""


def patch_codsworth_steel_mat(mat: dict) -> dict:
    """Calibrate FO4 Mr. Handy brushed-steel PBR parameters while preserving any real _rough.dds map:
    blend bright brushed-steel tint over the dark FO4 _color.dds seams, enable Metalness=0.85 (slot 4),
    and keep MRTextureFile slot 3 (_rough.dds) when present (UseReplacement=False); only when no roughness
    texture exists, fall back to a non-mirror Roughness=0.45 so Metalness > 0.5 never pairs with Roughness < 0.4
    without a roughness texture."""
    tx, ty, tz, tw = CODSWORTH_STEEL_TINT
    m_str = f"{CODSWORTH_METALNESS:g}"
    r_str = f"{CODSWORTH_FALLBACK_ROUGHNESS:g}"
    rough_file = _roughness_texture_file(mat)
    has_rough_tex = bool(rough_file)
    for obj in mat.get("Objects") or []:
        comps = obj.get("Components") or []
        if not comps:
            continue
        has_texset_id = any(c.get("Type") == "BSMaterial::TextureSetID" for c in comps)
        has_texfiles = any(
            c.get("Type") in ("BSMaterial::MRTextureFile", "BSMaterial::TextureReplacement") for c in comps
        )
        if has_texset_id and "Edges" in obj:
            for c in comps:
                if c.get("Type") == "BSMaterial::Color" and c.get("Index") == 0 and "Value" in c.get("Data", {}):
                    d = c["Data"]["Value"]["Data"]
                    d["x"], d["y"], d["z"], d["w"] = f"{tx:g}", f"{ty:g}", f"{tz:g}", f"{tw:g}"
        if has_texfiles:
            kept = []
            saw_rough_repl, saw_metal_repl = False, False
            for c in comps:
                ctype = c.get("Type")
                cidx = c.get("Index")
                if ctype == "BSMaterial::MRTextureFile" and cidx == 4:
                    continue
                if ctype == "BSMaterial::MRTextureFile" and cidx == 3 and not has_rough_tex:
                    continue
                if ctype == "BSMaterial::TextureReplacement" and cidx == 3:
                    d = c["Data"]["Color"]["Data"]["Value"]["Data"]
                    if has_rough_tex:
                        d["x"] = d["y"] = d["z"] = "0"
                        d["w"] = "1"
                        c["Data"].pop("Enabled", None)
                    else:
                        d["x"] = d["y"] = d["z"] = r_str
                        d["w"] = "1"
                        c["Data"]["Enabled"] = "true"
                    saw_rough_repl = True
                elif ctype == "BSMaterial::TextureReplacement" and cidx == 4:
                    d = c["Data"]["Color"]["Data"]["Value"]["Data"]
                    d["x"] = d["y"] = d["z"] = m_str
                    d["w"] = "1"
                    c["Data"]["Enabled"] = "true"
                    saw_metal_repl = True
                kept.append(c)
            if not has_rough_tex and not saw_rough_repl:
                kept.append({
                    "Data": {
                        "Color": {"Data": {"Value": {"Data": {"w": "1", "x": r_str, "y": r_str, "z": r_str}, "Type": "XMFLOAT4"}},
                                  "Type": "BSMaterial::Color", "Version": 1},
                        "Enabled": "true",
                    },
                    "Index": 3,
                    "Type": "BSMaterial::TextureReplacement",
                })
            if not saw_metal_repl:
                kept.append({
                    "Data": {
                        "Color": {"Data": {"Value": {"Data": {"w": "1", "x": m_str, "y": m_str, "z": m_str}, "Type": "XMFLOAT4"}},
                                  "Type": "BSMaterial::Color", "Version": 1},
                        "Enabled": "true",
                    },
                    "Index": 4,
                    "Type": "BSMaterial::TextureReplacement",
                })
            obj["Components"] = kept
    layer = (mat.get("Summary") or {}).get("Layer1")
    if isinstance(layer, dict):
        layer["Tint"] = {"w": tw, "x": tx, "y": ty, "z": tz}
        tex = layer.setdefault("Textures", {})
        tex["Metalness"] = {
            "File": "",
            "Replacement": {"w": 1, "x": CODSWORTH_METALNESS, "y": CODSWORTH_METALNESS, "z": CODSWORTH_METALNESS},
            "UseReplacement": True,
        }
        if has_rough_tex:
            prev_r = tex.get("Roughness") if isinstance(tex.get("Roughness"), dict) else {}
            tex["Roughness"] = {
                **prev_r,
                "File": rough_file,
                "Replacement": prev_r.get("Replacement", {"w": 1, "x": 0, "y": 0, "z": 0}),
                "UseReplacement": False,
            }
        else:
            tex["Roughness"] = {
                "File": "",
                "Replacement": {"w": 1, "x": CODSWORTH_FALLBACK_ROUGHNESS, "y": CODSWORTH_FALLBACK_ROUGHNESS, "z": CODSWORTH_FALLBACK_ROUGHNESS},
                "UseReplacement": True,
            }
    return mat


def bone_map(animate_arms: bool):
    def bone_for(name):
        if name is None:
            return "C_Chassis"
        if name.lower() == "pelvis":
            return "C_Base"
        if animate_arms:
            for prefix, target in ARMS:
                if name.lower().startswith(prefix.lower()):
                    return target
        return "C_Chassis"
    return bone_for


def read_starfield(sf_data: str, name: str) -> bytes:
    for path in sorted(glob.glob(os.path.join(sf_data, "Starfield - Meshes*.ba2")), reverse=True):   # patch archives first
        a = ba2.Ba2(path)
        i = a.find(name)
        if i is not None:
            return a.read(i)
    raise FileNotFoundError(f"{name} not in Starfield - Meshes*.ba2")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fo4-data", required=True)
    p.add_argument("--sf-data", required=True)
    p.add_argument("--staging", required=True)
    p.add_argument("--content-resources", required=True)
    p.add_argument("--texconv", required=True)
    p.add_argument("--template", default=TEMPLATE)
    p.add_argument("--animate-arms", action="store_true")
    # crash bisect switches (docs/spikes/red-rocket-crash-bisect.md)
    p.add_argument("--one-material", action="store_true",
                   help="every shape takes the first shape's material, so the model is one geometry set (the template's "
                        "own), with no copied geometry, shader or skin blocks")
    p.add_argument("--plain-shader", action=argparse.BooleanOptionalAction, default=True,
                   help="shader properties as the static converter writes them (the .mat name only; the default, which "
                        "walks clean in game). --no-plain-shader keeps the template's block with its name swapped, the "
                        "build that crashed the game at Red Rocket")
    a = p.parse_args(argv)
    if os.path.exists(a.staging) and os.listdir(a.staging):
        raise SystemExit(f"{a.staging} is not empty: give a new staging folder (an earlier stage is never overwritten)")
    parent = os.path.dirname(os.path.abspath(a.staging))
    os.makedirs(parent, exist_ok=True)
    # a fresh attempt folder each run: earlier failed or concurrent attempts are left as they are (evidence)
    partial = tempfile.mkdtemp(prefix=os.path.basename(os.path.abspath(a.staging)) + ".partial-", dir=parent)
    report = build(a, partial)
    if os.path.exists(a.staging):
        os.rmdir(a.staging)                                                 # empty (checked above)
    os.replace(partial, a.staging)                                          # publish only the complete stage
    print(json.dumps({k: report[k] for k in ("template_geometry", "template_bones", "groups", "bound", "detached", "pose")},
                     indent=1)[:6000])
    return 0


def _shape_texture_paths(fo4, s):
    """Return (diffuse, normal, spec) for an inline BSShaderTextureSet shape without a .bgsm, or None."""
    if s.shader_ref < 0 or fo4.type_of(s.shader_ref) != "BSLightingShaderProperty":
        return None
    blk = fo4.blocks[s.shader_ref]
    idx, = struct.unpack_from("<i", blk, 4)
    name = fo4.strings[idx] if 0 <= idx < len(fo4.strings) else b""
    if name.lower().endswith(b".bgsm"):
        return None
    n_extra, = struct.unpack_from("<I", blk, 8)
    ts_ref, = struct.unpack_from("<i", blk, 12 + 4 * n_extra + 4 + 8 + 16)
    if not (0 <= ts_ref < len(fo4.blocks)) or fo4.type_of(ts_ref) != "BSShaderTextureSet":
        return None
    tb = fo4.blocks[ts_ref]
    count, = struct.unpack_from("<I", tb, 0)
    paths, p = [], 4
    for _ in range(count):
        ln, = struct.unpack_from("<I", tb, p)
        paths.append(tb[p + 4:p + 4 + ln].rstrip(b"\0").decode("latin-1"))
        p += 4 + ln
    diffuse = paths[0] if paths else ""
    normal = paths[1] if len(paths) > 1 else ""
    spec = paths[7] if len(paths) > 7 else ""
    if not (diffuse and normal):
        return None
    return diffuse, normal, spec


def _canonical_texset_stem(diffuse: str, normal: str, spec: str = "") -> str:
    """Match pipeline.Converter.texture_set_material's deterministic stem for (diffuse, normal, spec)."""
    stem = "texsets/" + re.sub(r"^textures[\\/]", "", diffuse.replace("\\", "/"), flags=re.I).lower()
    ident = "|".join(x.replace("\\", "/").lower() for x in (diffuse, normal, spec))
    return os.path.splitext(stem)[0] + "_" + hashlib.sha1(ident.encode()).hexdigest()[:8]


def _handy_spec_path(src, diffuse: str) -> str:
    """Resolve FO4's Handy <part>_s.dds alongside <part>_d.dds when MrHandy.nif leaves slot 7 blank."""
    cand = re.sub(r"_d\.dds$", "_s.dds", diffuse, flags=re.I)
    if cand != diffuse and src.texture(cand) is not None:
        return cand
    return ""


def convert_handy_lens_material(src, conv):
    """Convert FO4 Materials\\Actors\\Robot\\HandyLens.BGEM into a Starfield glass/lens .mat when present."""
    if not (hasattr(src, "material") and hasattr(conv, "glass_material")):
        return None
    raw = src.material(HANDY_LENS_BGEM)
    if raw is None:
        return None
    base, normal = convert_material.parse_bgem_textures(raw)
    if not base:
        return None
    return conv.glass_material(base, normal)


def build(a, staging):
    src = pipeline.Fo4Archives(a.fo4_data)
    raw = src.mesh(SOURCE)
    if raw is None:
        raise SystemExit(f"{SOURCE} not found in {a.fo4_data}")
    try:
        conv = pipeline.Converter(src, staging, a.texconv, a.content_resources, spec_mask_roughness=True)
    except TypeError:
        conv = pipeline.Converter(src, staging, a.texconv, a.content_resources)
    fo4 = nif.parse(raw)
    materials = {}
    s_dds_converted = {}
    for s in nif.fo4_trishapes(fo4, placed=True):
        s_name = s.name.decode("latin-1")
        mat = None
        if hasattr(conv, "_convert_texture_set") and hasattr(src, "texture"):
            tx_paths = _shape_texture_paths(fo4, s)
            if tx_paths is not None:
                diffuse, normal, spec = tx_paths
                stem = _canonical_texset_stem(diffuse, normal, spec)
                eff_spec = spec or _handy_spec_path(src, diffuse)
                if eff_spec:
                    s_dds_converted[s_name] = eff_spec
                try:
                    mat = conv._convert_texture_set(stem, diffuse, normal, eff_spec)
                except Exception:
                    mat = None
        if mat is None:
            mat = conv._shape_material(fo4, s)
        if mat:
            materials[s_name] = mat
    lens_mat = convert_handy_lens_material(src, conv)
    default = conv.neutral
    for mat_rel in sorted(set(materials.values())):
        if mat_rel and mat_rel != default:
            mat_path = os.path.join(staging, *mat_rel.replace("\\", "/").split("/"))
            if os.path.isfile(mat_path):
                try:
                    with open(mat_path, encoding="utf-8") as mf:
                        raw_mat = json.load(mf)
                except (OSError, UnicodeDecodeError, ValueError):
                    raw_mat = None
                if isinstance(raw_mat, dict):
                    patched = patch_codsworth_steel_mat(raw_mat)
                    pipeline.write_staged(mat_path, (json.dumps(patched, indent="\t", sort_keys=True) + "\n").encode("utf-8"))
    if a.one_material and materials:                                        # shapes without one fall back to it too
        default = materials[next(iter(materials))]
        materials = {k: default for k in materials}
    res = actor_rebind.rebind(read_starfield(a.sf_data, a.template), raw, bone_map(a.animate_arms), materials=materials,
                              default_material=default, plain_shader=a.plain_shader)
    files = {f"meshes/{OUT_NAME}.nif": res.nif}
    files.update({f"geometries/{d}/{f}.mesh": data for (d, f), data in res.meshes.items()})
    for rel, data in files.items():
        dst = os.path.join(staging, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
    report = {"source": SOURCE, "template": a.template, "animate_arms": a.animate_arms,
              "one_material": a.one_material, "plain_shader": a.plain_shader,
              "materials": materials,
              "handy_lens_material": lens_mat,
              "s_dds_converted": s_dds_converted,
              "files": sorted(files), **res.report}
    with open(os.path.join(staging, "codsworth_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    return report


if __name__ == "__main__":
    raise SystemExit(main())
