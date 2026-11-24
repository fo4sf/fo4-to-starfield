"""Build FO4SFPrewar.esm, stage --codsworth-handy assets, compile S1 Papyrus scripts, and validate checks."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fo4sf.prewar import handy_codsworth, s1_spec, sanctuary_strip

PREWAR_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PAPYRUS_COMPILER = r"D:\SteamLibrary\steamapps\common\Starfield\Tools\Papyrus Compiler\PapyrusCompiler.exe"
DEFAULT_CONTENT_RES = r"D:\SteamLibrary\steamapps\common\Starfield\Tools\ContentResources.zip"
DEFAULT_PAPYRUS_FLAGS = "Starfield_Papyrus_Flags.flg"


def build_tile_local_spec(
    *,
    sanctuary_esm: str | None = None,
    port_esm: str | None = None,
    port_cell_edid: str = "FO4Port_PrewarVault111S1",
    vertibird_model: str | None = None,
    ext_lift_model: str | None = None,
    female_spouse: bool = True,
) -> dict:
    """Compute tile-local Sanctuary + PrewarVault111 marker map JSON for `dotnet/Prewar`."""
    tile = sanctuary_strip.strip_sf_tile()

    def _sanc(name: str, rot_z: float = 0.0) -> list[float]:
        px, py, pz = s1_spec.SANCTUARY_KEY_COORDS_M[name]
        lx, ly = tile.to_local(px, py)
        return [round(lx, 4), round(ly, 4), round(pz, 4), rot_z]

    def _v111(name: str, rot_z: float = 0.0) -> list[float]:
        px, py, pz = s1_spec.PREWAR_V111_KEY_COORDS_M[name]
        return [round(px, 4), round(py, 4), round(pz, 4), rot_z]

    markers = {
        "FO4SF_PrewarHouseSpawnMarker": _sanc("player_start"),
        "FO4SF_PrewarCodsworthRef": _sanc("player_house_door", 1.57),
        "FO4SF_PrewarSpouseRef": _sanc("player_start", 0.2),
        "FO4SF_PrewarVaultTecRepRef": _sanc("vault_tec_rep_door", 3.14),
        "FO4SF_PrewarSoldierCheckerRef": _sanc("military_gate_checker", 1.2),
        "FO4SF_PrewarVertibird01Ref": _sanc("vertibird_b_orbit", 0.5),
        "FO4SF_PrewarVertibird02Ref": _sanc("vertibird_c_hover", -0.7),
        "FO4SF_PrewarExtLiftPlatformRef": _sanc("ext_elevator_center"),
        "FO4SF_PrewarNukeAnchorRef": _sanc("nuke_look_marker"),
        "FO4SF_PrewarCrowdGoalMarkRef": _sanc("ext_elevator_center"),
        "FO4SF_PrewarCrowdBridgeMarkRef": _sanc("west_bridge", 1.57),
        "FO4SF_PrewarVaultArrivalMarker": _v111("int_elevator_spawn"),
        "FO4SF_PrewarKelloggMarkRef": _v111("kellogg_pod_spot", 3.14),
        "FO4SF_PrewarInstMalePodMarkRef": _v111("inst_male_pod_spot", 3.14),
        "FO4SF_PrewarInstFemalePodMarkRef": _v111("inst_female_pod_spot", 3.14),
        "FO4SF_PrewarSpousePodMarkRef": _v111("spouse_cryopod"),
        "FO4SF_PrewarPlayerPodMarkRef": _v111("player_cryopod", 3.14),
    }

    spec: dict = {
        "player_female_spouse": female_spouse,
        "elevator_drop_m": 21.6,
        "nuke_delay_s": 4.2,
        "markers": markers,
    }
    if sanctuary_esm:
        spec["sanctuary_world"] = {"esm": os.path.abspath(sanctuary_esm), "world_edid": "FO4SF_PrewarSanctuaryWorld"}
    if port_esm:
        spec["port_vault"] = {"esm": os.path.abspath(port_esm), "cell_edid": port_cell_edid}
    if vertibird_model:
        spec["vertibird_model"] = vertibird_model
    if ext_lift_model:
        spec["ext_lift_model"] = ext_lift_model
    return spec


def _extract_papyrus_base_sources(content_zip: str, dest_dir: str) -> str:
    """Extract base Starfield Papyrus headers and flags from ContentResources.zip cleanly into a short folder."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(content_zip) as zf:
        for name in zf.namelist():
            if not name.startswith("Scripts/Source/") or name.endswith("/"):
                continue
            rel = name[len("Scripts/Source/"):]
            if "/" in rel:
                continue
            low = rel.lower()
            if low.endswith(".psc") or low == DEFAULT_PAPYRUS_FLAGS.lower():
                target = os.path.join(dest_dir, rel)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return dest_dir


def compile_prewar_scripts(
    out_scripts_dir: str,
    *,
    compiler_exe: str = DEFAULT_PAPYRUS_COMPILER,
    content_zip: str = DEFAULT_CONTENT_RES,
) -> list[str]:
    """Compile S1 Papyrus scripts from `scripts/prewar` (cwd short path safe) into `out_scripts_dir`."""
    os.makedirs(out_scripts_dir, exist_ok=True)
    outputs: list[str] = []
    with tempfile.TemporaryDirectory(prefix="prewar_psc_src_") as src_tmp:
        base_src = _extract_papyrus_base_sources(content_zip, src_tmp) if os.path.isfile(content_zip) else content_zip
        for psc_name in ("FO4SF_PrewarStandIns.psc", "FO4SF_PrewarQuest.psc"):
            cmd = [
                compiler_exe,
                psc_name,
                f"-f={DEFAULT_PAPYRUS_FLAGS}",
                f"-i={PREWAR_SCRIPTS_DIR};{base_src}",
                f"-o={os.path.abspath(out_scripts_dir)}",
            ]
            subprocess.run(cmd, cwd=PREWAR_SCRIPTS_DIR, check=True)
            outputs.append(os.path.join(out_scripts_dir, psc_name[:-4] + ".pex"))
    return outputs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--starfield-esm", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--codsworth-handy", help="Path to #854 robot-anim E2 bundle directory")
    ap.add_argument("--handy-esm", help="Direct path to FO4SF_RA2Handy.esm (when not copying full bundle)")
    ap.add_argument("--sanctuary-esm", help="Optional FO4SFPrewar_Sanctuary.esm host world")
    ap.add_argument("--port-esm", help="Optional FO4Port.esm with Slot 2 PrewarVault111S1")
    ap.add_argument("--voices-json", help="Optional local Kellogg/NPC voices manifest JSON")
    ap.add_argument("--compile-scripts", action="store_true", help="Compile S1 Papyrus .psc -> .pex into <out-dir>/Data/Scripts")
    ap.add_argument("--papyrus-compiler", default=DEFAULT_PAPYRUS_COMPILER)
    ap.add_argument("--content-resources", default=DEFAULT_CONTENT_RES)
    ap.add_argument("--report-json")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    spec_path = os.path.join(args.out_dir, "prewar_spec.json")
    spec = build_tile_local_spec(sanctuary_esm=args.sanctuary_esm, port_esm=args.port_esm)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    handy_esm = args.handy_esm
    copied_handy: list[str] = []
    if args.codsworth_handy:
        hspec, copied_handy = handy_codsworth.copy_handy_assets(
            args.codsworth_handy,
            os.path.join(args.out_dir, "Data"),
            target_race_edid=handy_codsworth.DEFAULT_CODSWORTH_RACE_EDID,
        )
        handy_esm = handy_esm or hspec.template_esm

    prewar_proj = os.path.join(ROOT, "dotnet", "Prewar", "Prewar.csproj")
    write_cmd = [
        "dotnet", "run", "--project", prewar_proj, "-c", "Release", "--",
        "write", args.starfield_esm, args.out_dir, "--spec", spec_path,
    ]
    if handy_esm:
        write_cmd.extend(["--handy-esm", handy_esm])
    if args.voices_json:
        write_cmd.extend(["--voices", args.voices_json])
    subprocess.run(write_cmd, cwd=ROOT, check=True)

    plugin_path = os.path.join(args.out_dir, s1_spec.PLUGIN_PREWAR)
    check_cmd = [
        "dotnet", "run", "--project", prewar_proj, "-c", "Release", "--",
        "check", plugin_path, args.starfield_esm, "--spec", spec_path,
    ]
    if handy_esm:
        check_cmd.extend(["--handy-esm", handy_esm])
    if args.voices_json:
        check_cmd.extend(["--voices", args.voices_json])
    subprocess.run(check_cmd, cwd=ROOT, check=True)

    compiled_pex: list[str] = []
    if args.compile_scripts:
        compiled_pex = compile_prewar_scripts(
            os.path.join(args.out_dir, "Data", "Scripts"),
            compiler_exe=args.papyrus_compiler,
            content_zip=args.content_resources,
        )

    rep = {
        "plugin": plugin_path,
        "handy_files_copied": len(copied_handy),
        "compiled_pex": compiled_pex,
    }
    if args.report_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.report_json)), exist_ok=True)
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)
    print(f"built {plugin_path} (handy_files={len(copied_handy)}, pex={len(compiled_pex)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
