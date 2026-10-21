"""Stage the Fallout 4 new game (docs/newgame/vault111-start.md): FO4SFNewGame.esm and its scripts, offline.

usage:
  python make_newgame.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native and event the four scripts use, looked up in Starfield's base sources
      (Scripts/Source of ContentResources.zip), and every source line naming MQ101Debug (how Starfield's debug start
      works). Exit 1 when a native of FO4SF_NewGameQuest is missing (do not stage); a missing native of the looks
      script (Game.ShowRaceMenu, the menu open/close event) only means --no-looks, one of the SPECIAL script
      (Actor.SetValue / GetValue) only --no-special, one of the version script (OnPlayerLoadGame) only --no-version.
  python make_newgame.py stage --out <dir> --fo4 <Fallout4.esm> --port <FO4Port.esm> --port-ids <formids.json>
                               --core <FO4TerrainCore.esm> [--starfield <Starfield.esm>] [--compiler <exe>]
                               [--content-resources <zip>] [--no-looks] [--race-menu-mode N] [--no-special]
                               [--no-version] [--build-version N] [--hold MQ00,MQ101,...] [--mq101debug N]
                               [--no-mq101debug] [--pod-ref HEX] [--terminal-ref HEX]
                               [--clear-inventory [--vault-suit EDITORID]]
      1. dotnet/NewGame points (Fallout4.esm read only: the pod, the console, the cog door, the platform, the arrival,
         the cell's terminals);
      2. dotnet/NewGame write + check against the port and core given (offline_check.txt);
      3. the Papyrus compile of FO4SF_NewGameQuest.psc (and FO4SF_NewGameLooks.psc unless --no-looks,
         FO4SF_NewGameSpecial.psc unless --no-special, FO4SF_NewGameVersion.psc unless --no-version);
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
      the run's user log as a summary (stages by the contract below, held-off quests by pass, what ended the looks wait,
      the SPECIAL ending, the save version lines, the inventory reset, moves, the landing); exit 0 when stage 200 was
      reached.
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
SPECIAL = "FO4SF_NewGameSpecial"
VERSION = "FO4SF_NewGameVersion"
# The stage contract (NG-14): the stages FO4SF_NewGame publishes for later phases and other mods to listen to, with
# what each means. FO4SF_NewGameQuest.psc's header lists the same lines and tests/test_newgame.py holds them equal;
# docs/newgame/vault111-start.md section 9 is the published table. Stage 0 is the quest's start, not a QUST record.
STAGE_CONTRACT = {
    0: "started: waiting for the player's 3D, then the guard and the hold-off",
    1: "stood down: not a new game, nothing moved",
    10: "in the vault: the player stands at their pod",
    20: "looks done: character creation closed, or LooksWait passed",
    30: "cog door opened: from its console",
    40: "on the surface: the elevator ride is over",
    200: "complete: landed, or put on the fallback spot",
}
STAGES = tuple(n for n in STAGE_CONTRACT if n > 0)           # the QUST's stage records (Program.cs Stages)
# the writer's defaults (Program.cs DefaultHold and DefaultMQ101Debug, held equal by tests/test_newgame.py): the opening
# quests, the two MQ101's stage 9000 starts when it is stopped (NG-19, NG-N1), and GLOB MQ101Debug set to 10 ourselves,
# the value MQ00 writes before starting MQ101 (NG-2)
DEFAULT_HOLD = ("MQ00", "MQ101", "MQ101PostQuest", "MQ_TutorialQuest_Misc04")
DEFAULT_MQ101DEBUG = 10
# Game.ShowRaceMenu's uiMode (Program.cs DefaultRaceMenuMode, the looks script's RaceMenuMode): 0 is the full creator;
# which mode is looks-only is unverified until the in-game C1 test
DEFAULT_RACE_MENU_MODE = 0
# SPECIAL at the vault terminal (NG-5 / NG-C4; Program.cs SpecialNames, SpecialExtraButtons, SpecialBase, SpecialPoints,
# SpecialMax and the SPECIAL script's defaults, held equal by tests/test_newgame.py): Fallout 4's rule, 1 in each stat,
# 21 points to spend, 10 at most in one stat. SPECIAL_BUTTONS is the allocation message's button order, the index
# Message.Show returns; special_press is the script's rule for one press, tested in Python. SPECIAL_MAX_PRESSES is the
# script's MaxPresses: the allocation ends as Leave after that many presses without Confirm or Leave (about 22 per
# pass; the guard against a message box that returns at once).
SPECIAL_STATS = ("Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck")
SPECIAL_BUTTONS = SPECIAL_STATS + ("Reset", "Confirm", "Leave")
SPECIAL_BASE, SPECIAL_POINTS, SPECIAL_MAX = 1, 21, 10
SPECIAL_MAX_PRESSES = 300
# The save version check (NG-15 / NG-L2; Program.cs DefaultBuildVersion, held equal by tests/test_newgame.py): the
# build's version number, written to GLOB FO4SF_NewGameVersion (constant) and recorded by the version script when a new
# game starts; on every load the script compares the two and logs "version load saved=<n> installed=<n>", then "version
# mismatch" and a notification when they differ. --build-version sets another number; bump it when a save made under
# the old build must not go on under the new one.
DEFAULT_BUILD_VERSION = 1
# The starting inventory reset (NG-K8 / NG-N3; Program.cs DefaultClearInventory, held equal by tests/test_newgame.py):
# OFF until the first in-game proof shows what Starfield leaves the player with when MQ101 is held off. --clear-inventory
# makes the quest script call RemoveAllItems (quest items kept) right after the move into the pod and log "inventory
# cleared removed=<n> left=<n>"; --vault-suit <EditorID> (only with it) names the port's ARMO the script then adds and
# equips ("vault suit equipped ..."), resolved offline by the writer with the same owner checks as the other ids.
DEFAULT_CLEAR_INVENTORY = False
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_newgame.0.log")
LINE = re.compile(r"FO4SF_NEWGAME rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")
# the natives each script calls and the events it handles, by the base script that must declare them (precheck).
# Events are declarations too (Event OnMenuOpenCloseEvent in ScriptObject.psc), looked up the same way.
NATIVES = {
    # the inventory reset (ClearInventory, off by default) calls RemoveAllItems, GetItemCount, AddItem, EquipItem and
    # IsEquipped with FO4's signatures; whether Starfield's declare them the same way is what this precheck reads
    SCRIPT: {
        "Actor": ["GetLevel", "EquipItem", "IsEquipped"],
        "Debug": ["OpenUserLog", "TraceUser", "Notification"],
        "Game": ["GetPlayer", "GetFormFromFile", "SetInChargen", "SetCharGenHUDMode"],
        "GlobalVariable": ["GetValue"],
        "Message": ["Show"],
        "ObjectReference": ["MoveTo", "SetPosition", "SetAngle", "GetPositionX", "GetParentCell", "GetWorldSpace",
                            "IsInInterior", "Is3DLoaded", "GetOpenState", "SetOpen", "RemoveAllItems", "GetItemCount",
                            "AddItem"],
        "Quest": ["SetStage", "GetStage", "IsRunning", "Stop", "CompleteQuest", "SetObjectiveDisplayed",
                  "SetObjectiveCompleted", "SetActive", "IsCompleted", "IsStopped"],
        "ScriptObject": ["StartTimer"],
        "Utility": ["GetCurrentRealTime"],
    },
    LOOKS: {
        "Debug": ["TraceUser"],
        "Game": ["ShowRaceMenu"],
        "Message": ["Show"],
        "Quest": ["SetStage", "GetStage"],
        "ScriptObject": ["StartTimer", "RegisterForMenuOpenCloseEvent", "OnMenuOpenCloseEvent"],
        "Utility": ["Wait", "GetCurrentRealTime"],
    },
    # Actor.SetValue(ActorValue, float) / GetValue(ActorValue) are FO4's; whether Starfield's Actor.psc declares them
    # the same way is what this precheck reads (unverified until then)
    SPECIAL: {
        "Actor": ["SetValue", "GetValue"],
        "Debug": ["TraceUser", "Notification"],
        "Game": ["GetPlayer", "GetFormFromFile"],
        "Message": ["Show"],
        "ObjectReference": ["GetPositionX", "IsInInterior"],
        "Quest": ["GetStage"],
        "ScriptObject": ["StartTimer"],
        "Utility": ["GetCurrentRealTime"],
    },
    # OnPlayerLoadGame is declared on ReferenceAlias (PC read 19 Oct, NG-L3); OnInit on ScriptObject is where the
    # script records the version when the alias fills
    VERSION: {
        "Debug": ["OpenUserLog", "TraceUser", "Notification"],
        "GlobalVariable": ["GetValue"],
        "ReferenceAlias": ["OnPlayerLoadGame"],
        "ScriptObject": ["OnInit"],
        "Utility": ["GetCurrentRealTime"],
    },
}
# the optional scripts: the stage option that drops each, and the precheck's advice when a native is missing
OPTIONAL = {LOOKS: "--no-looks", SPECIAL: "--no-special", VERSION: "--no-version"}


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


def special_press(values, left, button, base=SPECIAL_BASE, points=SPECIAL_POINTS, maximum=SPECIAL_MAX):
    """FO4SF_NewGameSpecial.Allocate's rule for one press of SPECIAL_BUTTONS[button] on (values, left): the new
    (values, left, ending), ending None while the message shows again, "set" on Confirm with every point spent,
    "left" on Leave (or a closed message, button -1). A stat button with no points left or the stat at the maximum
    changes nothing; Confirm with points left changes nothing."""
    values = list(values)
    name = SPECIAL_BUTTONS[button] if 0 <= button < len(SPECIAL_BUTTONS) else "Leave"
    if name in SPECIAL_STATS:
        if left > 0 and values[button] < maximum:
            values[button] += 1
            left -= 1
        return values, left, None
    if name == "Reset":
        return [base] * len(SPECIAL_STATS), points, None
    if name == "Confirm":
        return values, left, "set" if left == 0 else None
    return values, left, "left"


def is_new_game(days, level, max_days=0.25, max_level=1):
    """FO4SF_NewGameQuest.IsNewGame: fewer than max_days game days passed and the player at most max_level. An
    existing save that gains the plugin stands down."""
    return days < max_days and level <= max_level


SAVEABLE_STAGE = 105   # MQ101's stage that turns saving back on (QF_MQ101_00003448.psc, PC read 19 Oct)


def is_fresh_start(opening_stage, opening_completed, opening_stopped, saveable=SAVEABLE_STAGE):
    """FO4SF_NewGameQuest.IsFreshStart: the opening (MQ101) below the stage that turns saving back on, not completed,
    and not stopped after it began. A save the player made cannot have it there, so an early level-1 save under six
    game hours still stands down (21 Oct review on #393)."""
    return opening_stage < saveable and not opening_completed and not (opening_stopped and opening_stage > 0)


def declared_properties(psc_text):
    """{name: mandatory?} of every Property the script declares."""
    out = {}
    for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)(?:\s*=\s*[^\n]*?)?\s+Auto(\s+Const)?(\s+Mandatory)?\b",
                         psc_text, re.M | re.I):
        out[m.group(1)] = bool(m.group(3))
    return out


def has_function(source, name):
    """True when a base script's source declares Function <name> (native or not) or Event <name>."""
    return re.search(rf"^\s*(?:[\w\[\]:]+\s+)?(?:Function|Event)\s+{re.escape(name)}\s*\(", source, re.M | re.I) is not None


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
    drop = [opt for script, opt in OPTIONAL.items() if not all(natives[script].values())]
    return {"natives": natives, "mq101debug": debug, "missing_core": missing, "drop": drop}


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
    print("precheck: " + ("ok" if not r["missing_core"] else f"{len(r['missing_core'])} native(s) missing; do not stage")
          + "".join(f"; {script} cannot compile: stage with {opt}" for script, opt in OPTIONAL.items() if opt in r["drop"]))
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
        hint = f" (stage again with {OPTIONAL[name]})" if name in OPTIONAL else ""
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
    if a.no_mq101debug:
        opts.append("--no-mq101debug")
    elif a.mq101debug is not None:
        opts += ["--mq101debug", str(a.mq101debug)]
    if not a.looks:
        opts.append("--no-looks")
    if a.race_menu_mode is not None:
        opts += ["--race-menu-mode", str(a.race_menu_mode)]
    if not a.special:
        opts.append("--no-special")
    if not a.version:
        opts.append("--no-version")
    if a.build_version is not None:
        opts += ["--build-version", str(a.build_version)]
    if a.clear_inventory:
        opts.append("--clear-inventory")
        if a.vault_suit:
            opts += ["--vault-suit", a.vault_suit]
    elif a.vault_suit:
        sys.exit("--vault-suit is equipped by the inventory reset: stage with --clear-inventory too")
    return opts


def mq101debug_option(a):
    """The GLOB MQ101Debug value the build writes: None under --no-mq101debug, else the value given or the default."""
    if a.no_mq101debug:
        return None
    return DEFAULT_MQ101DEBUG if a.mq101debug is None else a.mq101debug


def build_version_option(a):
    """The version number the build writes to GLOB FO4SF_NewGameVersion: None under --no-version, else the value
    given or the default."""
    if not a.version:
        return None
    return DEFAULT_BUILD_VERSION if a.build_version is None else a.build_version


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
    run(tool + ["points", a.fo4, points] + (["--pod-ref", a.pod_ref] if a.pod_ref else [])
        + (["--terminal-ref", a.terminal_ref] if a.terminal_ref else []))
    opts = tool_options(a)
    masters = [a.starfield, a.port, a.port_ids, a.core, points]
    run(tool + ["write", a.starfield, a.port, a.port_ids, a.core, points, out] + opts)
    check = run(tool + ["check", os.path.join(out, PLUGIN)] + masters + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    src = extract_sources(a.content_resources, work)
    scripts = [SCRIPT] + ([LOOKS] if a.looks else []) + ([SPECIAL] if a.special else []) + ([VERSION] if a.version else [])
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
            "options": {"hold": a.hold or ",".join(DEFAULT_HOLD), "mq101debug": mq101debug_option(a), "looks": a.looks,
                        "race_menu_mode": DEFAULT_RACE_MENU_MODE if a.race_menu_mode is None else a.race_menu_mode,
                        "special": a.special, "version": a.version,
                        "build_version": build_version_option(a),
                        "clear_inventory": bool(a.clear_inventory), "vault_suit": a.vault_suit if a.clear_inventory else None},
            "stages": {str(n): what for n, what in STAGE_CONTRACT.items()}, "points": pts,
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_newgame.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Fallout 4 new game (Claude-cloud, {datetime.date.today().isoformat()}). docs/newgame/vault111-start.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_NewGame "{pts['quest_name']}" (start game enabled, run once),
MESG FO4SF_NewGameElevator and FO4SF_NewGameStart{', FO4SF_NewGameTerminal and FO4SF_NewGameSpecial, 7 AVIF FO4SF_Special_<stat>' if a.special else ''}{f', GLOB FO4SF_NewGameVersion = {build_version_option(a)} and a player alias (the save version check)' if a.version else ''};
master Starfield.esm only. Scripts: {', '.join(s + '.pex' for s in scripts)} in Data\\Scripts.
Checked against (the ids it resolves at run time must stay): {json.dumps(before)}. Re-stage after a port or core change.
Pod {pts['pod']['src']} {pts['pod'].get('edid')}; arrival {pts['arrival']['pos']} m (core-local); {len(pts.get('terminals', []))} terminal(s) in the cell.
Inventory reset at the pod: {('ON (quest items kept), vault suit ' + (a.vault_suit or 'none')) if a.clear_inventory else 'off (the default until the first in-game proof)'}.
Options {json.dumps(plan['options'])}.
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


def split_runs(lines, line_re, start="init ", carry=()):
    """The messages of each run, oldest first: a user log is appended across game sessions, so a run starts at each
    message beginning with `start` (the script's OnInit trace); messages before the first one form a run of their own.
    A message beginning with one of `carry` that comes right before a `start` belongs to that new run: another
    script's init can trace before the quest's own (21 Oct review on #393, the version script). Lines of other logs
    are dropped."""
    runs, pending = [], []
    for line in lines:
        m = line_re.search(line)
        if not m:
            continue
        msg = m.group("msg")
        if carry and msg.startswith(carry):
            pending.append(msg)
            continue
        if msg.startswith(start) or not runs:
            runs.append([])
            if msg.startswith(start):
                runs[-1] += pending
                pending = []
        runs[-1] += pending + [msg]
        pending = []
    if pending:
        if not runs:
            runs.append([])
        runs[-1] += pending
    return runs


def summarize(lines):
    """The LATEST run of the new-game log as {"stages", "stages_named", "held_off", "held_off_by_pass", "looks_done",
    "special", "version_saved", "version_load", "version_mismatch", "inventory_cleared", "vault_suit", "entered_vault",
    "surfaced", "landed", "fell", "stood_down", "last_status", "runs", "earlier_completed"}.
    "inventory_cleared" is the reset's line ("removed=<n> left=<n> ..."; None when the build kept the inventory) and
    "vault_suit" the suit's ("equipped <armor> worn=<bool>", or that it did not resolve; None when none was named).
    "stages_named" reads each stage reached by the contract (STAGE_CONTRACT); "held_off_by_pass" says what each
    hold-off pass stopped (pass 1 before the move, pass 2 one tick later for what MQ101's stop started); "looks_done"
    says what ended the looks wait ("creator closed", "quick start", or the quest's "LooksWait fallback ..."); "special"
    is the SPECIAL script's ending ("set S=.. P=.. ..." or "skipped: ..." when the player left the vault without it;
    "later" and "left" prompts are not endings). "version_saved" is the build version the version script recorded
    when the new game started, "version_load" the last "saved=<n> installed=<n>" line of a save load (a load logs no
    "init", so it joins the run before it) and "version_mismatch" whether any load found the two apart. Only the
    latest run is judged; "runs" counts the runs in the file and "earlier_completed" says whether an older one reached
    stage 200 (kept as history, never as the current result). Lines of other logs are ignored."""
    s = {"stages": [], "stages_named": [], "held_off": [], "held_off_by_pass": {}, "looks_done": None, "special": None,
         "version_saved": None, "version_load": None, "version_mismatch": False,
         "inventory_cleared": None, "vault_suit": None,
         "entered_vault": None, "surfaced": None, "landed": None, "fell": False, "stood_down": False, "last_status": None,
         "runs": 0, "earlier_completed": False}
    runs = split_runs(lines, LINE, carry=("version saved=",))
    s["runs"] = len(runs)
    s["earlier_completed"] = any("stage 200" in r for r in runs[:-1])
    for msg in runs[-1] if runs else []:
        if msg.startswith("stage "):
            n = int(msg.split()[1])
            s["stages"].append(n)
            s["stages_named"].append(f"{n} {STAGE_CONTRACT.get(n, 'not in the contract')}")
        elif msg.startswith("held off "):
            quest, _, rest = msg[len("held off "):].partition(" running_after=")
            s["held_off"].append(quest)
            m = re.search(r"\bpass=(\d+)", rest)
            s["held_off_by_pass"].setdefault(m.group(1) if m else "1", []).append(quest)
        elif msg.startswith("looks done: "):
            if s["looks_done"] is None:                      # the first ending counts; a later one changes nothing
                s["looks_done"] = msg[len("looks done: "):]
        elif msg.startswith("special set ") or msg.startswith("special skipped"):
            if s["special"] is None:
                s["special"] = msg[len("special "):]
        elif msg.startswith("version saved="):
            if s["version_saved"] is None:
                s["version_saved"] = msg[len("version saved="):].split()[0]
        elif msg.startswith("version load "):
            s["version_load"] = msg[len("version load "):]
        elif msg.startswith("version mismatch"):
            s["version_mismatch"] = True
        elif msg.startswith("inventory cleared "):
            s["inventory_cleared"] = msg[len("inventory cleared "):]
        elif msg.startswith("vault suit "):
            s["vault_suit"] = msg[len("vault suit "):]
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
    return 0 if 200 in s["stages"] and not s["stood_down"] else 1


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
    s.add_argument("--race-menu-mode", type=int, default=None,
                   help=f"Game.ShowRaceMenu's uiMode for the looks script (default {DEFAULT_RACE_MENU_MODE}, the full creator)")
    s.add_argument("--no-special", dest="special", action="store_false",
                   help="no SPECIAL terminal: no FO4SF_NewGameSpecial script, AVIF or its two MESG")
    s.add_argument("--terminal-ref", default=None, help="the SPECIAL terminal in Vault111Cryo, FO4 hex id (default: the cell's terminals, nearest the pod first)")
    s.add_argument("--no-version", dest="version", action="store_false",
                   help="no save version check: no FO4SF_NewGameVersion script, player alias or GLOB")
    s.add_argument("--build-version", type=int, default=None,
                   help=f"the build's version number, GLOB FO4SF_NewGameVersion (default {DEFAULT_BUILD_VERSION})")
    s.add_argument("--hold", default=None, help=f"Starfield start quests to stop, by EditorID (default {','.join(DEFAULT_HOLD)})")
    s.add_argument("--mq101debug", type=float, default=None, help=f"the GLOB MQ101Debug override's value (default {DEFAULT_MQ101DEBUG})")
    s.add_argument("--no-mq101debug", action="store_true", help="write no GLOB MQ101Debug override")
    s.add_argument("--pod-ref", default=None, help="the player's pod in Vault111Cryo, FO4 hex id (when points finds several)")
    s.add_argument("--clear-inventory", action="store_true",
                   help="empty the player's inventory (quest items kept) right after the move into the pod (NG-K8; off by default)")
    s.add_argument("--vault-suit", default=None, metavar="EDITORID",
                   help="with --clear-inventory: the port's ARMO the script adds and equips after the reset, by EditorID")
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
