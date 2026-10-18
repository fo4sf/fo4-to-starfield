"""Stage the cut-down "When Freedom Calls" mission (docs/mission/when-freedom-calls.md) and read its in-game log.

usage:
  python make_mission.py stage --out <experiment dir> --fo4 <Fallout4.esm> --starfield <Starfield.esm>
                               --core <FO4TerrainCore.esm> --raider <FO4ActorRaider.esm>
                               [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>] [--no-alias]
      1. dotnet/Mission points: Fallout 4's Concord raiders and the museum door's outside arrival (points.json);
      2. dotnet/Mission write + check: FO4SFMission.esm against the given core and raider plugins (offline_check.txt);
      3. the Papyrus compile of FO4SF_Min00Quest.psc against every base script of ContentResources.zip;
      4. plan.json and README.txt with the masters' SHA-256: the plugin copies the core's world record, so it must be
         rebuilt whenever FO4TerrainCore.esm changes (install refuses a plan whose core hash differs).
  python make_mission.py log [--file <fo4sf_mission.0.log>]
      the mission's user log as a summary: stages reached in order, the last status line, the reward; exit 0 when
      stage 200 was reached, 1 otherwise.
Install (the runner or the install session, game closed):
  python scripts/game/exp_install.py install --exp-dir <out> --starfield <game> --plugins FO4SFMission.esm --pack
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
PROJECT = os.path.join(REPO, "dotnet", "Mission")
PLUGIN = "FO4SFMission.esm"
SCRIPT = "FO4SF_Min00Quest"
STAGES = (10, 20, 30, 40, 200)
# the script properties dotnet/Mission writes (Program.cs, Write): a renamed property would leave the script unbound
PROPERTIES = ("Preston", "Raiders", "Credits")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_mission.0.log")
LINE = re.compile(r"FO4SF_MISSION rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")


def run(cmd, cwd=None):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        sys.exit(f"{os.path.basename(cmd[0])} exit {r.returncode}")
    return r.stdout


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mandatory_properties(psc_text):
    """The names of the script's Auto Const Mandatory properties (what the plugin must fill), in source order."""
    return [m.group(1) for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\s+Const\s+Mandatory\b",
                                            psc_text, re.M | re.I)]


def extract_sources(zip_path, work):
    """Every base script (Scripts/Source/*.psc, top level) and the flags file from ContentResources.zip: the quest
    script uses Actor, Quest, ObjectReference, MiscObject and their own imports, so all of them are given."""
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        sys.exit(f"{zip_path}: no Scripts/Source base scripts or flags file")
    return src


def compile_script(compiler, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    name = SCRIPT + ".psc"
    out = run([compiler, name, "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"], cwd=HERE)
    pex = os.path.join(out_dir, SCRIPT + ".pex")
    if "Compilation succeeded" not in out or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {SCRIPT}.pex")
    return pex


def stage(a):
    with open(os.path.join(HERE, SCRIPT + ".psc"), encoding="utf-8") as f:
        props = mandatory_properties(f.read())
    if tuple(props) != PROPERTIES:
        sys.exit(f"{SCRIPT}.psc properties {props} differ from what dotnet/Mission writes {list(PROPERTIES)}")
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    points = os.path.join(work, "points.json")
    run(tool + ["points", a.fo4, points])
    alias = [] if a.alias else ["--no-alias"]
    run(tool + ["write", a.starfield, a.core, a.raider, points, out, "--plugin", PLUGIN] + alias)
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, a.core, a.raider] + alias)
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    src = extract_sources(a.content_resources, work)
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    with open(points, encoding="utf-8") as f:
        pts = json.load(f)
    masters = {os.path.basename(p): sha256(p) for p in (a.core, a.raider)}
    plan = {"kind": "mission", "plugin": PLUGIN, "plugin_sha256": sha256(os.path.join(out, PLUGIN)),
            "script": SCRIPT, "alias": a.alias, "masters_sha256": masters, "stages": list(STAGES),
            "raiders": [r["src"] for r in pts["raiders"]], "preston": pts["preston"],
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_mission.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    raiders = ", ".join(f"{r['src']} ({r.get('dist_m', '?')} m)" for r in pts["raiders"])
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Cut-down "When Freedom Calls" (Claude-cloud, {datetime.date.today().isoformat()}). docs/mission/when-freedom-calls.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_Min00 (start game enabled), NPC_ FO4_PrestonGarvey, Preston's ACHR
at the museum door's outside arrival {pts['preston']['pos']} m, {len(pts['raiders'])} raider ACHRs of FO4_LvlRaider at
Fallout 4's Concord positions ({raiders}), all persistent in the core world's persistent cell (WRLD override).
Masters (must match the installed files): {json.dumps(masters)}. Rebuild after any core change.
Data\\Scripts\\{SCRIPT}.pex compiled from {SCRIPT}.psc (beside this file).
Install (game closed): python scripts\\game\\exp_install.py install --exp-dir "{out}" --starfield <game> --plugins {PLUGIN} --pack
Logging needs the [Papyrus] keys of make_bridge.py ini (already set where the bridge runs).
In game: load a save, walk to Concord. The HUD shows the objectives; the log {plan['log']} gets each stage and a
status line every 5 s. Read it: python scripts\\mission\\make_mission.py log
Uninstall: exp_install.py uninstall.
""")
    print(f"staged {out}: {PLUGIN}, {os.path.relpath(pex, out)}, offline_check.txt, plan.json, README.txt")


def summarize(lines):
    """The mission log's lines as {"stages": [...], "status": <last status line or None>, "reward": int or None,
    "startcombat": n, "activated": n}; lines of other logs are ignored."""
    s = {"stages": [], "status": None, "reward": None, "startcombat": 0, "activated": 0}
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        msg = m.group("msg")
        if msg.startswith("stage "):
            s["stages"].append(int(msg.split()[1]))
        elif msg.startswith("status "):
            s["status"] = msg
        elif msg.startswith("reward credits="):
            s["reward"] = int(msg.split("=", 1)[1])
        elif msg.startswith("startcombat "):
            s["startcombat"] += 1
        elif msg.startswith("preston activated"):
            s["activated"] += 1
    return s


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = summarize(f)
    print(json.dumps(s, indent=1))
    return 0 if 200 in s["stages"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--fo4", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--core", required=True)
    s.add_argument("--raider", required=True)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--no-alias", dest="alias", action="store_false")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    if a.cmd == "stage":
        stage(a)
        return 0
    return log(a)


if __name__ == "__main__":
    sys.exit(main())
