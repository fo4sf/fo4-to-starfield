r"""Stage, verify, and inspect logs for FO4SF Combat Core (CF-8, docs/combat/combat-core.md).

Stages FO4SFCombat.esm (via dotnet/CombatCore), compiles FO4SF_CombatInput.pex and FO4SF_CombatQuest.pex
against Starfield's PapyrusCompiler.exe and ContentResources.zip, optionally bundles built FO4SFCombat.dll +
FO4SFCombat.ini into sfse_sidecar/, writes plan.json and README.txt, and verifies SHA-256 + record invariants.

Refuses to stage whenever Starfield.exe is running (fo4sf.launcher.crashwatch.System.pids).

usage:
  python scripts/combat/make_combat_core.py stage --out <stage-dir> --starfield-dir <Starfield>
      [--sfse-build <sfse-build-dir>]
  python scripts/combat/make_combat_core.py verify --stage-dir <stage-dir> [--starfield <Starfield.esm>]
  python scripts/combat/make_combat_core.py log [--file <FO4SFCombat.0.log>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (
    os.path.join(REPO, "src"),
    os.path.join(REPO, "scripts", "newgame"),
    os.path.join(REPO, "scripts", "game"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exp_install  # noqa: E402
import make_newgame  # noqa: E402
from fo4sf.combat import parse_combat_log  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402

PLUGIN = "FO4SFCombat.esm"
SCRIPTS = ("FO4SF_CombatQuest", "FO4SF_CombatInput")


class CombatStageRefused(RuntimeError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_game_closed(system=None) -> None:
    sys_obj = system if system is not None else System()
    try:
        pids = sys_obj.pids(GAME_EXE)
    except ValueError as err:
        raise CombatStageRefused(f"stage refused: cannot confirm {GAME_EXE} is closed ({err})") from err
    if pids:
        joined = ", ".join(str(p) for p in pids)
        raise CombatStageRefused(f"stage refused: {GAME_EXE} is running (pid {joined}); close the game first")


def compile_combat_scripts(compiler: str, content_resources: str, scripts_out: str) -> Dict[str, str]:
    os.makedirs(scripts_out, exist_ok=True)
    hashes: Dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="fo4sf-combat-src-") as td:
        src_dir = make_newgame.extract_sources(content_resources, td)
        for name in SCRIPTS:
            psc_src = os.path.join(HERE, f"{name}.psc")
            shutil.copy2(psc_src, os.path.join(src_dir, f"{name}.psc"))
        for name in SCRIPTS:
            cmd = [
                compiler,
                f"{name}.psc",
                "-f=Starfield_Papyrus_Flags.flg",
                f"-i={src_dir}",
                f"-o={scripts_out}",
            ]
            r = subprocess.run(cmd, cwd=src_dir, capture_output=True, text=True)
            pex_path = os.path.join(scripts_out, f"{name}.pex")
            if r.returncode != 0 or not os.path.isfile(pex_path):
                raise CombatStageRefused(f"Papyrus compile failed for {name}.psc:\n{r.stdout}\n{r.stderr}")
            hashes[f"Data/Scripts/{name}.pex"] = sha256_file(pex_path)
    return hashes


def stage_combat_core(
    out_dir: str,
    starfield_dir: str,
    sfse_build_dir: Optional[str] = None,
    system=None,
) -> Dict[str, object]:
    ensure_game_closed(system=system)
    dst = os.path.abspath(out_dir)
    if os.path.exists(dst):
        raise CombatStageRefused(f"stage output already exists (refusing overwrite): {dst}")

    sf_root = os.path.abspath(starfield_dir)
    sf_esm = os.path.join(sf_root, "Data", "Starfield.esm")
    compiler = os.path.join(sf_root, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe")
    cr_zip = os.path.join(sf_root, "Tools", "ContentResources.zip")
    for label, p in (("Starfield.esm", sf_esm), ("PapyrusCompiler.exe", compiler), ("ContentResources.zip", cr_zip)):
        if not os.path.isfile(p):
            raise CombatStageRefused(f"missing {label}: {p}")

    partial = make_newgame.new_partial(dst, create=True)
    proj = os.path.join(REPO, "dotnet", "CombatCore")

    r_build = subprocess.run(["dotnet", "run", "--project", proj, "--", "build", sf_esm, partial],
                             capture_output=True, text=True)
    if r_build.returncode != 0:
        raise CombatStageRefused(f"CombatCore build failed:\n{r_build.stdout}\n{r_build.stderr}")

    esm_path = os.path.join(partial, PLUGIN)
    r_chk = subprocess.run(["dotnet", "run", "--project", proj, "--", "check", esm_path, sf_esm],
                           capture_output=True, text=True)
    if r_chk.returncode != 0:
        raise CombatStageRefused(f"CombatCore check failed:\n{r_chk.stdout}\n{r_chk.stderr}")

    scripts_out = os.path.join(partial, "Data", "Scripts")
    script_hashes = compile_combat_scripts(compiler, cr_zip, scripts_out)

    sidecar: Dict[str, str] = {}
    if sfse_build_dir:
        sb = os.path.abspath(sfse_build_dir)
        dll_src = os.path.join(sb, "FO4SFCombat.dll")
        ini_src = os.path.join(sb, "FO4SFCombat.ini")
        if not os.path.isfile(dll_src):
            raise CombatStageRefused(f"--sfse-build missing FO4SFCombat.dll: {dll_src}")
        sc_dir = os.path.join(partial, "sfse_sidecar")
        os.makedirs(sc_dir, exist_ok=True)
        shutil.copy2(dll_src, os.path.join(sc_dir, "FO4SFCombat.dll"))
        sidecar["FO4SFCombat.dll"] = sha256_file(os.path.join(sc_dir, "FO4SFCombat.dll"))
        if os.path.isfile(ini_src):
            shutil.copy2(ini_src, os.path.join(sc_dir, "FO4SFCombat.ini"))
            sidecar["FO4SFCombat.ini"] = sha256_file(os.path.join(sc_dir, "FO4SFCombat.ini"))

    outputs: Dict[str, str] = {PLUGIN: sha256_file(esm_path)}
    outputs.update(script_hashes)

    plan = {
        "kind": "combat-core",
        "version": 1,
        "plugin": PLUGIN,
        "plugins": [PLUGIN],
        "plugin_sha256": outputs[PLUGIN],
        "outputs": outputs,
        "sfse_sidecar": sidecar,
    }
    with open(os.path.join(partial, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)

    readme = "\n".join([
        "FO4SF Combat Core (CF-8) — Staged Experiment",
        "============================================",
        f"Plugin: {PLUGIN}",
        "Scripts: Data/Scripts/FO4SF_CombatQuest.pex, Data/Scripts/FO4SF_CombatInput.pex",
        "SFSE sidecar (optional for live 'V'/'N' hotkeys): sfse_sidecar/FO4SFCombat.dll + FO4SFCombat.ini",
        "",
        "Install (game closed):",
        f'  python scripts/game/exp_install.py install --exp-dir "<STAGE_DIR>" --starfield "<STARFIELD_DIR>" --plugins {PLUGIN} --pack',
        "Rollback (game closed):",
        '  python scripts/game/exp_install.py uninstall --starfield "<STARFIELD_DIR>"',
        "",
    ])
    Path(os.path.join(partial, "README.txt")).write_text(readme, encoding="utf-8", newline="\n")

    os.replace(partial, dst)
    return plan


def verify_stage(stage_dir: str, starfield_esm: Optional[str] = None) -> Tuple[List[str], Dict[str, object]]:
    st = os.path.abspath(stage_dir)
    plan_p = os.path.join(st, "plan.json")
    if not os.path.isfile(plan_p):
        return [f"missing plan.json in {st}"], {}
    with open(plan_p, encoding="utf-8") as f:
        plan = json.load(f)

    problems: List[str] = []
    for rel, want in (plan.get("outputs") or {}).items():
        full = os.path.join(st, *rel.split("/"))
        if not os.path.isfile(full):
            problems.append(f"missing staged output: {rel}")
        elif sha256_file(full) != want:
            problems.append(f"sha256 mismatch for {rel}")

    for rel, want in (plan.get("sfse_sidecar") or {}).items():
        full = os.path.join(st, "sfse_sidecar", *rel.split("/"))
        if not os.path.isfile(full):
            problems.append(f"missing sfse_sidecar output: {rel}")
        elif sha256_file(full) != want:
            problems.append(f"sfse_sidecar sha256 mismatch for {rel}")

    esm_p = os.path.join(st, PLUGIN)
    if os.path.isfile(esm_p):
        try:
            masters = exp_install.plugin_masters(esm_p)
            if masters != ["Starfield.esm"]:
                problems.append(f"expected masters ['Starfield.esm'], got {masters}")
        except ValueError as err:
            problems.append(f"invalid TES4 header: {err}")

        if starfield_esm and os.path.isfile(starfield_esm):
            proj = os.path.join(REPO, "dotnet", "CombatCore")
            r = subprocess.run(["dotnet", "run", "--project", proj, "--", "check", esm_p, starfield_esm],
                               capture_output=True, text=True)
            if r.returncode != 0:
                problems.append(f"CombatCore check failed: {r.stderr or r.stdout}".strip())

    return problems, plan


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage, verify, and inspect FO4SF Combat Core (CF-8).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_st = sub.add_parser("stage")
    p_st.add_argument("--out", required=True)
    p_st.add_argument("--starfield-dir", required=True)
    p_st.add_argument("--sfse-build", default=None)

    p_vf = sub.add_parser("verify")
    p_vf.add_argument("--stage-dir", required=True)
    p_vf.add_argument("--starfield", default=None)

    p_lg = sub.add_parser("log")
    p_lg.add_argument("--file", required=True)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "stage":
            plan = stage_combat_core(args.out, args.starfield_dir, sfse_build_dir=args.sfse_build)
            print(json.dumps(plan, indent=2))
            return 0
        if args.cmd == "verify":
            probs, plan = verify_stage(args.stage_dir, starfield_esm=args.starfield)
            if probs:
                for p in probs:
                    print(f"FAIL: {p}", file=sys.stderr)
                return 1
            print(f"PASS: verified {plan.get('plugin')} ({len(plan.get('outputs', {}))} outputs)")
            return 0
        if args.cmd == "log":
            txt = Path(args.file).read_text(encoding="utf-8", errors="replace")
            rep = parse_combat_log(txt)
            print(json.dumps({
                "zones_pass": rep.zones_pass,
                "ammo_dt_pass": rep.ammo_dt_pass,
                "cripple_cure_pass": rep.cripple_cure_pass,
                "vats_pass": rep.vats_pass,
                "all_pass": rep.all_pass,
                "zones_hit": rep.zones_hit,
                "high_dt_hits": rep.high_dt_hits,
                "crippled_zones": rep.crippled_zones,
                "cures": rep.cures,
                "vats_shots": rep.vats_shots,
            }, indent=2))
            return 0 if rep.all_pass else 1
    except CombatStageRefused as err:
        print(str(err), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
