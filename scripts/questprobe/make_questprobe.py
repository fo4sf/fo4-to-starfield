"""Stage the quest-engine probe (docs/questprobe/engine-questions.md): FO4SFQuestProbe.esm and its scripts, offline.

usage:
  python make_questprobe.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native function and event the three scripts use, looked up in Starfield's base sources
      (Scripts/Source of ContentResources.zip). Exit 1 when one is missing (do not stage).
  python make_questprobe.py stage --out <dir> --port <FO4Port.esm> [--starfield <Starfield.esm>] [--compiler <exe>]
                                  [--content-resources <zip>] [--cell FO4Port_BostonPublicLibrary02] [--no-sm]
      1. dotnet/QuestProbe write + check against the port given (offline_check.txt, with the vanilla shapes copied);
      2. the Papyrus compile of FO4SF_QProbeQuest, FO4SF_QProbeFragments (and FO4SF_QProbeSMQuest unless --no-sm);
      3. plan.json (the plugin's and scripts' SHA-256, the port's it was checked against) and README.txt. Built in a
         new <out>.partial-<time>-<pid> and renamed to <out> only when every step passed; an existing <out> is refused.
  python make_questprobe.py log [--file <fo4sf_qprobe.0.log>]
      the run's user log as a summary: the five answers; exit 0 when the result line was written.
Nothing here installs anything. The probe goes in only on the owner's word, after the current test, and runs only in
its cell (the library by default), far from Red Rocket, Sanctuary and the museum.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
from make_newgame import extract_sources, has_function, new_partial, run, sha256  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "QuestProbe")
PLUGIN = "FO4SFQuestProbe.esm"
SCRIPT = "FO4SF_QProbeQuest"
FRAGMENTS = "FO4SF_QProbeFragments"
SM_SCRIPT = "FO4SF_QProbeSMQuest"
STAGES = (10, 20, 100)
DEFAULT_CELL = "FO4Port_BostonPublicLibrary02"
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_qprobe.0.log")
LINE = re.compile(r"FO4SF_QPROBE rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")
ANSWERS = ("E1_fragment", "E2_onstageset", "E3_alias", "E4_questtype", "E5_storymanager")
# the natives (and events) each script uses, by the base script that must declare them (precheck)
NATIVES = {
    SCRIPT: {
        "Debug": ["OpenUserLog", "TraceUser", "Notification"],
        "Game": ["GetPlayer", "GetFormFromFile"],
        "Keyword": ["SendStoryEventAndWait"],
        "ObjectReference": ["GetParentCell", "GetDistance"],
        "Quest": ["SetStage", "GetStage", "GetStageDone", "SetObjectiveDisplayed", "SetObjectiveCompleted", "SetActive",
                  "IsRunning", "IsCompleted"],
        "ReferenceAlias": ["ForceRefTo", "GetReference"],
        "ScriptObject": ["StartTimer"],
        "Utility": ["GetCurrentRealTime"],
    },
    FRAGMENTS: {},
    SM_SCRIPT: {
        "Debug": ["OpenUserLog", "TraceUser"],
        "Utility": ["GetCurrentRealTime"],
    },
}
EVENTS = {"Quest": ["OnStageSet", "OnQuestInit"], "ScriptObject": ["OnTimer"]}


def has_event(source, name):
    """True when a base script's source declares Event <name>."""
    return re.search(rf"^\s*Event\s+{re.escape(name)}\s*\(", source, re.M | re.I) is not None


def scripts_for(sm):
    return [SCRIPT, FRAGMENTS] + ([SM_SCRIPT] if sm else [])


def precheck_zip(zip_path):
    """{"natives": {script: {"Base.Function": bool}}, "events": {"Base.Event": bool}, "missing": [...],
    "signatures": {"Base.Name": declaration line}} from Starfield's base sources."""
    sources = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and name.lower().endswith(".psc"):
                sources[parts[2][:-4].lower()] = z.read(name).decode("utf-8", errors="replace")
    natives = {s: {f"{b}.{f}": has_function(sources.get(b.lower(), ""), f) for b, fs in bases.items() for f in fs}
               for s, bases in NATIVES.items()}
    events = {f"{b}.{e}": has_event(sources.get(b.lower(), ""), e) for b, es in EVENTS.items() for e in es}
    signatures = {}
    for key in ("Quest.SetStage", "Keyword.SendStoryEventAndWait", "Quest.OnStageSet"):
        b, n = key.split(".")
        m = re.search(rf"^.*\b(?:Function|Event)\s+{n}\s*\(.*$", sources.get(b.lower(), ""), re.M | re.I)
        signatures[key] = m.group(0).strip() if m else None
    missing = [k for found in natives.values() for k, ok in found.items() if not ok] + [k for k, ok in events.items() if not ok]
    return {"natives": natives, "events": events, "signatures": signatures, "missing": missing}


def precheck(a):
    r = precheck_zip(a.content_resources)
    for script, found in r["natives"].items():
        for k, ok in found.items():
            print(f"{'ok  ' if ok else 'MISSING'}  {script}: {k}")
    for k, ok in r["events"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  event {k}")
    for k, line in r["signatures"].items():
        print(f"  {k}: {line}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} missing; do not stage"))
    return 0 if not r["missing"] else 1


def compile_script(compiler, name, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    r = run([compiler, name + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"],
            cwd=HERE, check=False)
    pex = os.path.join(out_dir, name + ".pex")
    if r.returncode != 0 or "Compilation succeeded" not in r.stdout or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile of {name}.psc did not produce {name}.pex")
    return pex


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    before = {"FO4Port.esm": sha256(a.port)}
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    opts = ["--cell", a.cell] + ([] if a.sm else ["--no-sm"])
    wrote = run(tool + ["write", a.starfield, a.port, out] + opts).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, a.port] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    src = extract_sources(a.content_resources, work)
    scripts = scripts_for(a.sm)
    pex = {s: compile_script(a.compiler, s, src, os.path.join(out, "Data", "Scripts")) for s in scripts}
    for s in scripts:
        shutil.copy(os.path.join(HERE, s + ".psc"), os.path.join(out, s + ".psc"))
    shutil.rmtree(os.path.join(work, "Source"))
    now = {"FO4Port.esm": sha256(a.port)}
    if now != before:
        sys.exit(f"the port changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": "questprobe", "plugin": PLUGIN, "plugin_sha256": sha256(os.path.join(out, PLUGIN)),
            "scripts": {s: sha256(p) for s, p in pex.items()}, "checked_against_sha256": before,
            "options": {"cell": a.cell, "story_manager": a.sm}, "stages": list(STAGES),
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_qprobe.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Quest-engine probe (Claude-cloud, {datetime.date.today().isoformat()}). docs/questprobe/engine-questions.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_QProbe (start game enabled, idles until the player is in
{a.cell}); master Starfield.esm only; adds records, overrides none. Scripts: {', '.join(s + '.pex' for s in scripts)}.
Checked against FO4Port.esm {before['FO4Port.esm']}. Re-stage after a port change.
Install: not now; only on the owner's word, after the current test, game closed (loose scripts are not read: the
installer packs them into "FO4SFQuestProbe - Main.ba2"):
  python scripts\\questprobe\\questprobe_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\questprobe\\questprobe_install.py uninstall --starfield <game dir>
In game: coc {a.cell}, wait 15 s, screenshot the compass, open the Missions tab and screenshot it, walk to the marker.
Read the run:  python scripts\\questprobe\\make_questprobe.py log
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {len(scripts)} script(s), offline_check.txt, plan.json, README.txt")
    return 0


def summarize(lines):
    """The probe's log as {"started", "fragment", "stage_events", "setstage", "alias", "story_event", "sm_started",
    "result": {answer: value}, "reached"}; lines of other logs are ignored."""
    s = {"started": False, "fragment": None, "stage_events": [], "setstage": None, "alias": None, "story_event": None,
         "sm_started": False, "result": None, "reached": False}
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        msg = m.group("msg")
        if msg.startswith("probe start"):
            s["started"] = True
        elif msg.startswith("fragment ran stage="):
            s["fragment"] = int(msg.split("=")[1].split()[0])
        elif msg.startswith("onstageset stage="):
            s["stage_events"].append(int(msg.split("=")[1].split()[0]))
        elif msg.startswith("setstage 10 "):
            s["setstage"] = msg
        elif msg.startswith("alias "):
            s["alias"] = msg
        elif msg.startswith("story event "):
            s["story_event"] = msg
        elif msg.startswith("sm quest started"):
            s["sm_started"] = True
        elif msg.startswith("result "):
            s["result"] = dict(kv.split("=", 1) for kv in msg.split() if "=" in kv and kv.split("=")[0] in ANSWERS)
        elif msg.startswith("reached target"):
            s["reached"] = True
    return s


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = summarize(f)
    print(json.dumps(s, indent=1))
    return 0 if s["result"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--port", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--cell", default=DEFAULT_CELL)
    s.add_argument("--no-sm", dest="sm", action="store_false")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
