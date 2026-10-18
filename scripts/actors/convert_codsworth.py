"""Codsworth's FO4 model on the Starfield garden mini bot's skeleton (fo4sf.actor_rebind), into a staging folder.

    python scripts/actors/convert_codsworth.py --fo4-data "<FO4 Data>" --sf-data "<Starfield Data>" --staging <dir>
        --content-resources "<Starfield>\\Tools\\ContentResources.zip" --texconv <texconv.exe> [--animate-arms]

Source Meshes\\Actors\\Robot\\CharacterAssets\\MrHandy.nif (Torso, Legs, HandyShell, Arms:0, Arms:1; 63 skin bones),
template Meshes\\Actors\\MiniBotA\\Mesh\\minibota_mesh\\minibota_mesh.nif (one weight per vertex; bones C_Chassis,
C_Arm1-3, C_Base, C_Axle, C_Hatch), both verified on the PC 2026-10-18 (codsworth_dump.py). Materials and textures go
through pipeline.Converter exactly as the statics do. Writes into <staging>:
    meshes/fo4port/actors/codsworth/codsworth.nif, geometries/<hash>/<hash>.mesh, materials/..., textures/...
    codsworth_report.json
Bone map: Pelvis (the thruster) -> C_Base, everything else -> C_Chassis. With --animate-arms the three arm chains
(LArm*, MArm*, RArm* with their palms) go to C_Arm1..3, which then swing about the mini bot's arm roots, not Codsworth's.
The plugin side (an ARMA/ARMO whose model is this NIF, set as Codsworth's skin) belongs to the mission build.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from fo4sf import actor_rebind, ba2, nif, pipeline  # noqa: E402

SOURCE = "meshes\\actors\\robot\\characterassets\\mrhandy.nif"
TEMPLATE = "meshes\\actors\\minibota\\mesh\\minibota_mesh\\minibota_mesh.nif"
OUT_NAME = "fo4port/actors/codsworth/codsworth"
ARMS = (("LArm", "C_Arm1"), ("MArm", "C_Arm2"), ("RArm", "C_Arm3"))


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
    a = p.parse_args(argv)

    src = pipeline.Fo4Archives(a.fo4_data)
    raw = src.mesh(SOURCE)
    if raw is None:
        raise SystemExit(f"{SOURCE} not found in {a.fo4_data}")
    conv = pipeline.Converter(src, a.staging, a.texconv, a.content_resources)
    fo4 = nif.parse(raw)
    materials = {}
    for s in nif.fo4_trishapes(fo4, placed=True):
        mat = conv._shape_material(fo4, s)
        if mat:
            materials[s.name.decode("latin-1")] = mat
    res = actor_rebind.rebind(read_starfield(a.sf_data, a.template), raw, bone_map(a.animate_arms), materials=materials,
                              default_material=conv.neutral)
    files = {f"meshes/{OUT_NAME}.nif": res.nif}
    files.update({f"geometries/{d}/{f}.mesh": data for (d, f), data in res.meshes.items()})
    for rel, data in files.items():
        dst = os.path.join(a.staging, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
    report = {"source": SOURCE, "template": a.template, "animate_arms": a.animate_arms, "materials": materials,
              "files": sorted(files), **res.report}
    with open(os.path.join(a.staging, "codsworth_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: report[k] for k in ("template_geometry", "template_bones", "groups", "bound", "detached", "pose")},
                     indent=1)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
