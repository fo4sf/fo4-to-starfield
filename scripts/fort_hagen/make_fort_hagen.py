r"""Stage and verify the Fort Hagen elevator and roof-gate controller (docs/mission/fort-hagen-elevators.md).

usage:
  python make_fort_hagen.py inspect --port <FO4Port.esm> --core <FO4TerrainCore.esm> [--json <out.json>]
  python make_fort_hagen.py stage --out <stage dir> --starfield <Starfield.esm> --port <FO4Port.esm>
                                  --core <FO4TerrainCore.esm> [--compiler <PapyrusCompiler.exe>]
                                  [--content-resources <ContentResources.zip>]
  python make_fort_hagen.py verify --exp-dir <dir> --plan <stage dir>/plan.json
  python make_fort_hagen.py log [--file <fo4sf_forthagen.0.log>]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROJECT = os.path.join(REPO, "dotnet", "FortHagen")
PLUGIN = "FO4SFFortHagen.esm"
SCRIPT = "FO4SF_FortHagenQuest"
PSC_PATH = os.path.join(HERE, SCRIPT + ".psc")

PROPERTIES = (
    "XMarkerBase",
    "Anchor01Id", "UpperCall01Id", "UpperCall01BaseId", "LowerCall01Id", "InnerPanel01Id", "InnerPanel01BaseId",
    "UpperDoor01Id", "LowerDoor01Id", "OuterDoor01BaseId", "InnerDoor01Id", "InnerDoor01BaseId",
    "Planks01Id", "Planks01BaseId", "BlockerDoor01Id", "BlockerDoor01BaseId", "BlockerBoards01Id", "BlockerBoards01BaseId",
    "MaintSwitch01Id", "MaintSwitch01BaseId",
    "UpperLandingX", "UpperLandingY", "UpperLandingZ", "LowerCarX", "LowerCarY", "LowerCarZ",
    "Marker02Id", "Call02Id", "Call02BaseId", "Panel02Id", "Panel02BaseId",
    "OuterDoor02Id", "OuterDoor02BaseId", "LoadDoor02Id", "LoadDoor02BaseId",
    "RoofMarkerId", "RoofCallId", "RoofCallBaseId", "RoofPanelId", "RoofPanelBaseId",
    "RoofOuterDoorId", "RoofOuterDoorBaseId", "RoofLoadDoorId", "RoofLoadDoorBaseId",
    "RoofGateId", "RoofGateBaseId", "RoofTermId", "RoofTermBaseId",
    "RoofCenterX", "RoofCenterY", "RoofCenterZ",
    "RoofGateX", "RoofGateY", "RoofGateZ",
    "RoofTermX", "RoofTermY", "RoofTermZ",
    "RoofCallX", "RoofCallY", "RoofCallZ",
    "RoofPanelX", "RoofPanelY", "RoofPanelZ",
    "RoofOuterDoorX", "RoofOuterDoorY", "RoofOuterDoorZ",
    "RoofLoadDoorX", "RoofLoadDoorY", "RoofLoadDoorZ",
)

LINE_RE = re.compile(r"FO4SF_FORTHAGEN rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mandatory_properties(psc_text):
    """Names of Auto Const Mandatory properties declared in FO4SF_FortHagenQuest.psc, in source order."""
    return [
        m.group(1)
        for m in re.finditer(
            r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\s+Const\s+Mandatory\b",
            psc_text,
            re.M | re.I,
        )
    ]


def check_script_contract(psc_path=PSC_PATH):
    with open(psc_path, encoding="utf-8") as f:
        txt = f.read()
    got = tuple(mandatory_properties(txt))
    if got != PROPERTIES:
        raise ValueError(f"{SCRIPT}.psc mandatory properties differ from writer contract: {got} != {PROPERTIES}")
    return txt


def extract_base_sources(zip_path, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    flags_path = None
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            norm = info.filename.replace("\\", "/")
            if norm.lower().endswith(".flg") and "/" not in norm.removeprefix("Scripts/Source/"):
                out = os.path.join(dst_dir, os.path.basename(norm))
                with z.open(info) as src, open(out, "wb") as f:
                    shutil.copyfileobj(src, f)
                flags_path = out
            elif norm.startswith("Scripts/Source/") and norm.endswith(".psc") and norm.count("/") == 2:
                out = os.path.join(dst_dir, os.path.basename(norm))
                with z.open(info) as src, open(out, "wb") as f:
                    shutil.copyfileobj(src, f)
    if not flags_path:
        raise RuntimeError(f"no .flg file found in {zip_path}")
    return flags_path


def run_cmd(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise RuntimeError(f"{os.path.basename(cmd[0])} exited with {r.returncode}")
    return r.stdout


def cmd_inspect(args):
    check_script_contract()
    cmd = ["dotnet", "run", "--project", PROJECT, "--", "inspect", args.port, args.core]
    if args.json:
        cmd.extend(["--json", args.json])
    run_cmd(cmd)
    return 0


def cmd_stage(args):
    check_script_contract()
    out_dir = os.path.abspath(args.out)
    if os.path.exists(out_dir):
        raise RuntimeError(f"refused: output directory already exists: {out_dir}")

    sf_hash_before = sha256(args.starfield)
    port_hash_before = sha256(args.port)
    core_hash_before = sha256(args.core)

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    partial = f"{out_dir}.partial-{stamp}-{os.getpid()}"
    data_dir = os.path.join(partial, "Data")
    scripts_dir = os.path.join(data_dir, "Scripts")
    work_src = os.path.join(partial, "_papyrus_src")
    os.makedirs(scripts_dir, exist_ok=True)

    inspect_json = os.path.join(partial, "inspect.json")
    run_cmd(["dotnet", "run", "--project", PROJECT, "--", "inspect", args.port, args.core, "--json", inspect_json])
    run_cmd(["dotnet", "run", "--project", PROJECT, "--no-build", "--", "write", args.starfield, args.port, args.core, data_dir, "--plugin", PLUGIN])
    plugin_path = os.path.join(data_dir, PLUGIN)
    check_out = run_cmd(["dotnet", "run", "--project", PROJECT, "--no-build", "--", "check", plugin_path, args.starfield, args.port, args.core])
    with open(os.path.join(partial, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check_out)

    flags_file = extract_base_sources(args.content_resources, work_src)
    shutil.copy2(PSC_PATH, os.path.join(work_src, SCRIPT + ".psc"))
    run_cmd([
        args.compiler,
        SCRIPT,
        f"-i={work_src}",
        f"-o={scripts_dir}",
        f"-f={flags_file}",
    ], cwd=work_src)
    shutil.rmtree(work_src)

    pex_path = os.path.join(scripts_dir, SCRIPT + ".pex")
    if not os.path.isfile(pex_path):
        raise RuntimeError(f"PapyrusCompiler did not produce {pex_path}")

    if (sha256(args.starfield), sha256(args.port), sha256(args.core)) != (sf_hash_before, port_hash_before, core_hash_before):
        raise RuntimeError("refused: input master changed during build")

    plan = {
        "plugin": PLUGIN,
        "plugin_sha256": sha256(plugin_path),
        "plugin_bytes": os.path.getsize(plugin_path),
        "script": SCRIPT + ".pex",
        "script_sha256": sha256(pex_path),
        "script_bytes": os.path.getsize(pex_path),
        "masters": {
            "Starfield.esm": sf_hash_before,
            "FO4Port.esm": port_hash_before,
            "FO4TerrainCore.esm": core_hash_before,
        },
    }
    with open(os.path.join(partial, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    with open(os.path.join(partial, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"{PLUGIN} stage ({plan['plugin_bytes']} bytes) + {SCRIPT}.pex ({plan['script_bytes']} bytes)\n")

    os.rename(partial, out_dir)
    print(f"staged {out_dir}")
    return 0


def verify_stage(exp_dir, plan_path, port_path=None, core_path=None):
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    data_dir = os.path.join(exp_dir, "Data") if os.path.isdir(os.path.join(exp_dir, "Data")) else exp_dir
    plug = os.path.join(data_dir, plan["plugin"])
    pex = os.path.join(data_dir, "Scripts", plan["script"])
    problems = []
    if not os.path.isfile(plug):
        problems.append(f"missing plugin {plug}")
    elif sha256(plug) != plan["plugin_sha256"]:
        problems.append(f"plugin hash mismatch for {plan['plugin']}")
    if not os.path.isfile(pex):
        problems.append(f"missing script {pex}")
    elif sha256(pex) != plan["script_sha256"]:
        problems.append(f"script hash mismatch for {plan['script']}")
    if port_path and sha256(port_path) != plan["masters"]["FO4Port.esm"]:
        problems.append("FO4Port.esm hash differs from staged plan")
    if core_path and sha256(core_path) != plan["masters"]["FO4TerrainCore.esm"]:
        problems.append("FO4TerrainCore.esm hash differs from staged plan")
    return problems


def cmd_verify(args):
    problems = verify_stage(args.exp_dir, args.plan, args.port, args.core)
    if problems:
        for p in problems:
            sys.stderr.write("verify failed: " + p + "\n")
        return 1
    print("verify: ok")
    return 0


def summarize_log(text):
    events = []
    summary = {
        "inited": False,
        "fh01_ready": False,
        "fh01_planks_cleared": False,
        "fh01_rode_down": False,
        "fh01_rode_up": False,
        "fh02_ready": False,
        "fh02_dispatched": False,
        "fh_roof_ready": False,
        "fh_roof_gate_opened": False,
        "fh_roof_dispatched": False,
        "events": events,
    }
    for raw in text.splitlines():
        m = LINE_RE.search(raw)
        if not m:
            continue
        msg = m.group("msg").strip()
        events.append((float(m.group("rt")), msg))
        if msg.startswith("init "):
            summary["inited"] = True
        elif msg.startswith("fh01_ready "):
            summary["fh01_ready"] = True
            if "planks=True" in msg:
                summary["fh01_planks_cleared"] = True
        elif msg.startswith("fh01_arrived floor=lower"):
            summary["fh01_rode_down"] = True
        elif msg.startswith("fh01_arrived floor=upper"):
            summary["fh01_rode_up"] = True
        elif msg.startswith("fh02_ready "):
            summary["fh02_ready"] = True
        elif msg in ("fh02_outer_open", "fh02_panel_dispatch"):
            summary["fh02_dispatched"] = True
        elif msg.startswith("fh_roof_ready "):
            summary["fh_roof_ready"] = True
        elif msg.startswith("fh_roof_gate_opened"):
            summary["fh_roof_gate_opened"] = True
        elif msg in ("fh_roof_outer_open", "fh_roof_panel_dispatch"):
            summary["fh_roof_dispatched"] = True
    return summary


def cmd_log(args):
    with open(args.file, encoding="utf-8", errors="replace") as f:
        s = summarize_log(f.read())
    print(json.dumps({k: v for k, v in s.items() if k != "events"}, indent=2))
    ok = (
        s["fh01_ready"]
        and s["fh01_planks_cleared"]
        and s["fh01_rode_down"]
        and s["fh01_rode_up"]
        and s["fh_roof_gate_opened"]
    )
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage and verify Fort Hagen elevator controller.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ins = sub.add_parser("inspect")
    p_ins.add_argument("--port", required=True)
    p_ins.add_argument("--core", required=True)
    p_ins.add_argument("--json")
    p_ins.set_defaults(func=cmd_inspect)

    p_stg = sub.add_parser("stage")
    p_stg.add_argument("--out", required=True)
    p_stg.add_argument("--starfield", required=True)
    p_stg.add_argument("--port", required=True)
    p_stg.add_argument("--core", required=True)
    p_stg.add_argument("--compiler", required=True)
    p_stg.add_argument("--content-resources", required=True)
    p_stg.set_defaults(func=cmd_stage)

    p_ver = sub.add_parser("verify")
    p_ver.add_argument("--exp-dir", required=True)
    p_ver.add_argument("--plan", required=True)
    p_ver.add_argument("--port")
    p_ver.add_argument("--core")
    p_ver.set_defaults(func=cmd_verify)

    p_log = sub.add_parser("log")
    p_log.add_argument("--file", required=True)
    p_log.set_defaults(func=cmd_log)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
