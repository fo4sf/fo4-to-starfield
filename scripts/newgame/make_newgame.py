"""Stage the Fallout 4 new game (docs/newgame/vault111-start.md): FO4SFNewGame.esm and its scripts, offline.

usage:
  python make_newgame.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the two scripts call, looked up in Starfield's base sources (Scripts/Source of
      ContentResources.zip), and every source line naming MQ101Debug (how Starfield's debug start works). Exit 1 when a
      native of FO4SF_NewGameQuest is missing (do not stage); a missing Game.ShowRaceMenu only means --no-looks.
  python make_newgame.py stage --out <dir> --fo4 <Fallout4.esm> --port <FO4Port.esm> --port-ids <formids.json>
                               --core <FO4TerrainCore.esm> [--starfield <Starfield.esm>] [--compiler <exe>]
                               [--content-resources <zip>] [--no-looks] [--hold MQ00,MQ101] [--mq101debug N] [--pod-ref HEX]
      1. dotnet/NewGame points (Fallout4.esm read only: the pod, the console, the cog door, the platform, the arrival);
      2. dotnet/NewGame write + check against the port and core given (offline_check.txt);
      3. the Papyrus compile of FO4SF_NewGameQuest.psc (and FO4SF_NewGameLooks.psc unless --no-looks);
      4. plan.json (the plugin's and scripts' SHA-256 and the port, its formids.json and the core it was checked
         against) and README.txt. Built in a new <out>.partial-<time>-<pid> and renamed to <out> only when every step
         passed; an existing <out> is refused.
  python make_newgame.py verify --exp-dir <dir> --plan <stage>\\plan.json [--port <FO4Port.esm>] [--core <FO4TerrainCore.esm>]
      the install preflight: the plugin and scripts in <exp-dir> are the staged ones; the port and core (in <exp-dir>,
      else the paths given) are the bytes the ids were checked against. Exit 1 on any mismatch: re-stage, do not install.
  python make_newgame.py fold --stage <stage dir> --core-dir <core experiment dir> --out <new dir>
      exp_install.py holds one experiment, so the new game goes in WITH a core set: a copy of it plus the plugin and its
      .pex, published only after verify passes on the result.
  python make_newgame.py log [--file <fo4sf_newgame.0.log>]
      the run's user log as a summary (stages, held-off quests, moves, the landing); exit 0 when stage 200 was reached.
Nothing here installs anything: the install is the owner's line, to the install session, after the current test.
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
PROJECT = os.path.join(REPO, "dotnet", "NewGame")
PLUGIN = "FO4SFNewGame.esm"
SCRIPT = "FO4SF_NewGameQuest"
LOOKS = "FO4SF_NewGameLooks"
STAGES = (1, 10, 20, 30, 40, 200)
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_newgame.0.log")
LINE = re.compile(r"FO4SF_NEWGAME rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")
# the natives each script calls, by the base script that must declare them (precheck)
NATIVES = {
    SCRIPT: {
        "Actor": ["GetLevel"],
        "Debug": ["OpenUserLog", "TraceUser", "Notification"],
        "Game": ["GetPlayer", "GetFormFromFile"],
        "GlobalVariable": ["GetValue"],
        "Message": ["Show"],
        "ObjectReference": ["MoveTo", "SetPosition", "SetAngle", "GetPositionX", "GetParentCell", "GetWorldSpace",
                            "IsInInterior", "Is3DLoaded", "GetOpenState", "SetOpen"],
        "Quest": ["SetStage", "GetStage", "IsRunning", "Stop", "CompleteQuest", "SetObjectiveDisplayed",
                  "SetObjectiveCompleted", "SetActive"],
        "ScriptObject": ["StartTimer"],
        "Utility": ["GetCurrentRealTime", "IsInMenuMode"],
    },
    LOOKS: {
        "Game": ["ShowRaceMenu"],
        "Utility": ["Wait", "IsInMenuMode"],
    },
}


def run(cmd, cwd=None, check=True):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        if check:
            sys.exit(f"{os.path.basename(cmd[0])} exit {r.returncode}")
    return r


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def is_new_game(days, level, max_days=0.25, max_level=1):
    """FO4SF_NewGameQuest.IsNewGame: fewer than max_days game days passed and the player at most max_level. An
    existing save that gains the plugin stands down."""
    return days < max_days and level <= max_level


def declared_properties(psc_text):
    """{name: mandatory?} of every Property the script declares."""
    out = {}
    for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)(?:\s*=\s*[^\n]*?)?\s+Auto(\s+Const)?(\s+Mandatory)?\b",
                         psc_text, re.M | re.I):
        out[m.group(1)] = bool(m.group(3))
    return out


def has_function(source, name):
    """True when a base script's source declares Function <name> (native or not)."""
    return re.search(rf"^\s*(?:[\w\[\]:]+\s+)?Function\s+{re.escape(name)}\s*\(", source, re.M | re.I) is not None


def precheck_zip(zip_path):
    """{"natives": {script: {"Base.Function": bool}}, "mq101debug": [file:line: text], "missing_core": [...]}."""
    sources, debug = {}, []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.lower().endswith(".psc"):
                continue
            text = z.read(name).decode("utf-8", errors="replace")
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"]:
                sources[parts[2][:-4].lower()] = text
            for i, line in enumerate(text.splitlines(), 1):
                if "mq101debug" in line.lower():
                    debug.append(f"{name}:{i}: {line.strip()}")
    natives = {}
    for script, bases in NATIVES.items():
        natives[script] = {f"{b}.{f}": has_function(sources.get(b.lower(), ""), f) for b, fs in bases.items() for f in fs}
    missing = [k for k, ok in natives[SCRIPT].items() if not ok]
    return {"natives": natives, "mq101debug": debug, "missing_core": missing}


def precheck(a):
    r = precheck_zip(a.content_resources)
    for script, found in r["natives"].items():
        for k, ok in found.items():
            print(f"{'ok  ' if ok else 'MISSING'}  {script}: {k}")
    print(f"MQ101Debug: {len(r['mq101debug'])} line(s)")
    for line in r["mq101debug"][:80]:
        print("  " + line)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    looks = all(r["natives"][LOOKS].values())
    print("precheck: " + ("ok" if not r["missing_core"] else f"{len(r['missing_core'])} native(s) missing; do not stage")
          + ("" if looks else "; the looks script cannot compile: stage with --no-looks"))
    return 0 if not r["missing_core"] else 1


def extract_sources(zip_path, work):
    """Every base script (Scripts/Source/*.psc, top level) and the flags file, as make_mission.py does."""
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


def compile_script(compiler, name, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    r = run([compiler, name + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"],
            cwd=HERE, check=False)
    pex = os.path.join(out_dir, name + ".pex")
    if r.returncode != 0 or "Compilation succeeded" not in r.stdout or not os.path.exists(pex):
        hint = " (stage again with --no-looks)" if name == LOOKS else ""
        sys.exit(f"the Papyrus compile of {name}.psc did not produce {name}.pex{hint}")
    return pex


def new_partial(final, create=True):
    base = f"{final}.partial-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    if create:
        os.makedirs(out)
    return out


def tool_options(a):
    opts = []
    if a.hold:
        opts += ["--hold", a.hold]
    if a.mq101debug is not None:
        opts += ["--mq101debug", str(a.mq101debug)]
    if not a.looks:
        opts.append("--no-looks")
    return opts


def pins(a):
    return {"FO4Port.esm": sha256(a.port), "formids.json": sha256(a.port_ids), "FO4TerrainCore.esm": sha256(a.core)}


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    before = pins(a)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    points = os.path.join(work, "points.json")
    run(tool + ["points", a.fo4, points] + (["--pod-ref", a.pod_ref] if a.pod_ref else []))
    opts = tool_options(a)
    masters = [a.starfield, a.port, a.port_ids, a.core, points]
    run(tool + ["write", a.starfield, a.port, a.port_ids, a.core, points, out] + opts)
    check = run(tool + ["check", os.path.join(out, PLUGIN)] + masters + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    src = extract_sources(a.content_resources, work)
    scripts = [SCRIPT] + ([LOOKS] if a.looks else [])
    pex = {s: compile_script(a.compiler, s, src, os.path.join(out, "Data", "Scripts")) for s in scripts}
    for s in scripts:
        shutil.copy(os.path.join(HERE, s + ".psc"), os.path.join(out, s + ".psc"))
    drift = [f"{n}: {before[n]} at the start, {h} now" for n, h in pins(a).items() if h != before[n]]
    if drift:
        sys.exit("an input changed during the build, nothing published (" + "; ".join(drift) + f"); attempt kept in {out}")
    with open(points, encoding="utf-8") as f:
        pts = json.load(f)
    plan = {"kind": "newgame", "plugin": PLUGIN, "plugin_sha256": sha256(os.path.join(out, PLUGIN)),
            "scripts": {s: sha256(p) for s, p in pex.items()}, "checked_against_sha256": before,
            "options": {"hold": a.hold or "MQ00,MQ101", "mq101debug": a.mq101debug, "looks": a.looks},
            "stages": list(STAGES), "points": pts, "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_newgame.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Fallout 4 new game (Claude-cloud, {datetime.date.today().isoformat()}). docs/newgame/vault111-start.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_NewGame "{pts['quest_name']}" (start game enabled, run once),
MESG FO4SF_NewGameElevator; master Starfield.esm only. Scripts: {', '.join(s + '.pex' for s in scripts)} in Data\\Scripts.
Checked against (the ids it resolves at run time must stay): {json.dumps(before)}. Re-stage after a port or core change.
Pod {pts['pod']['src']} {pts['pod'].get('edid')}; arrival {pts['arrival']['pos']} m (core-local). Options {json.dumps(plan['options'])}.
Install: not now. When the owner says so (game closed): fold into a core set, verify, then exp_install.py.
In game: a NEW game only (an existing save stands the quest down at stage 1). Read the run:
  python scripts\\newgame\\make_newgame.py log
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {len(scripts)} script(s), offline_check.txt, plan.json, README.txt")
    return 0


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("plugin", "plugin_sha256", "scripts", "checked_against_sha256") if k not in plan]
    if missing or plan.get("kind") != "newgame":
        sys.exit(f"{path} is not a new-game plan (missing {missing})")
    return plan


def verify_dir(exp_dir, plan, port=None, core=None):
    problems = []

    def same(label, path, want):
        if not path or not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        elif sha256(path) != want:
            problems.append(f"{label}: {path} sha256 {sha256(path)} is not the plan's {want}")

    same("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    for s, want in plan["scripts"].items():
        same("script", os.path.join(exp_dir, "Data", "Scripts", s + ".pex"), want)
    pinned = plan["checked_against_sha256"]
    for name, given in (("FO4Port.esm", port), ("FO4TerrainCore.esm", core)):
        path = os.path.join(exp_dir, name)
        same(f"checked against {name}", path if os.path.isfile(path) else given, pinned[name])
    return problems


def verify(a):
    problems = verify_dir(a.exp_dir, load_plan(a.plan), a.port, a.core)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def fold(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.stage, "plan.json"))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"{a.core_dir} already holds {plan['plugin']}")
    out = new_partial(final, create=False)
    shutil.copytree(a.core_dir, out)
    shutil.copy2(os.path.join(a.stage, plan["plugin"]), os.path.join(out, plan["plugin"]))
    for s in plan["scripts"]:
        dst = os.path.join(out, "Data", "Scripts", s + ".pex")
        if os.path.exists(dst):
            sys.exit(f"fold refused: the core set already has Data/Scripts/{s}.pex (attempt kept in {out})")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(a.stage, "Data", "Scripts", s + ".pex"), dst)
    problems = verify_dir(out, plan, a.port, a.core)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); nothing published (attempt kept in {out})")
    os.replace(out, final)
    print(f"folded {final}: {a.core_dir} + {plan['plugin']} + {len(plan['scripts'])} script(s); verify ok")
    return 0


def summarize(lines):
    """The new-game log as {"stages", "held_off", "entered_vault", "surfaced", "landed", "fell", "stood_down",
    "last_status"}; lines of other logs are ignored."""
    s = {"stages": [], "held_off": [], "entered_vault": None, "surfaced": None, "landed": None, "fell": False,
         "stood_down": False, "last_status": None}
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        msg = m.group("msg")
        if msg.startswith("stage "):
            s["stages"].append(int(msg.split()[1]))
        elif msg.startswith("held off "):
            s["held_off"].append(msg[len("held off "):].split(" running_after=")[0])
        elif msg.startswith("enter vault ok="):
            s["entered_vault"] = msg.split()[2] == "ok=True"
        elif msg.startswith("surface setposition "):
            s["surfaced"] = msg
        elif msg.startswith("landed "):
            s["landed"] = True
        elif msg.startswith("fell "):
            s["fell"] = True
        elif msg.startswith("not a new game"):
            s["stood_down"] = True
        elif msg.startswith("status "):
            s["last_status"] = msg
    return s


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = summarize(f)
    print(json.dumps(s, indent=1))
    return 0 if 200 in s["stages"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--fo4", required=True)
    s.add_argument("--port", required=True)
    s.add_argument("--port-ids", required=True)
    s.add_argument("--core", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--no-looks", dest="looks", action="store_false")
    s.add_argument("--hold", default=None, help="Starfield start quests to stop, by EditorID (default MQ00,MQ101)")
    s.add_argument("--mq101debug", type=float, default=None, help="override GLOB MQ101Debug (off by default)")
    s.add_argument("--pod-ref", default=None, help="the player's pod in Vault111Cryo, FO4 hex id (when points finds several)")
    v = sub.add_parser("verify")
    v.add_argument("--exp-dir", required=True)
    v.add_argument("--plan", required=True)
    v.add_argument("--port", default=None)
    v.add_argument("--core", default=None)
    fo = sub.add_parser("fold")
    fo.add_argument("--stage", required=True)
    fo.add_argument("--core-dir", required=True)
    fo.add_argument("--out", required=True)
    fo.add_argument("--port", default=None)
    fo.add_argument("--core", default=None)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "verify": verify, "fold": fold, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
