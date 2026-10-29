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
                               [--no-mq101debug] [--debug-after-hold N] [--pod-ref HEX] [--terminal-ref HEX]
                               [--clear-inventory [--vault-suit EDITORID]] [--allow-temporary-anchor]
      1. dotnet/NewGame points (Fallout4.esm read only: the pod, the console, the cog door, the platform, the arrival,
         the cell's terminals);
      2. dotnet/NewGame write + check against the port and core given (offline_check.txt; its "vault anchor" line says
         whether the anchor is persistent or the temporary COC marker the script must center on first, and plan.json
         records that mode; a vault cell without a persistent reference is refused unless --allow-temporary-anchor);
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
      .pex, published only after verify passes on the result. Its README.txt is the core's with every exp_install.py
      install line naming EVERY plugin (the core's and FO4SFNewGame.esm, --pack), then the stage's README: the
      installer activates only the plugins listed (none listed: the first .esm alphabetically), so the core's own
      command would never install the new game.
  python make_newgame.py log [--file <fo4sf_newgame.0.log>]
      the run's user log as a summary (the start events that came, stages by the contract below, a hand back to
      Starfield's start, the fade in, held-off quests by pass, what ended the looks wait, the SPECIAL ending, the save
      version lines, the inventory reset, the centering of a temporary-anchor start, moves, the landing); exit 0 when
      stage 200 was reached.
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
    0: "started: as Starfield's startup quest, the guard, the move into the vault and the hold-off",
    1: "stood down: not a new game, or no move into the vault (Starfield's opening is asked to start if the game still loads)",
    10: "in the vault: the player stands at their pod",
    20: "looks done: character creation closed, or LooksWait passed",
    30: "cog door opened: from its console",
    40: "on the surface: the elevator ride is over",
    200: "complete: landed, or put on the fallback spot",
}
STAGES = tuple(n for n in STAGE_CONTRACT if n > 0)           # the QUST's stage records (Program.cs Stages)
# the writer's default hold-off list (Program.cs DefaultHold, held equal by tests/test_newgame.py): the opening quests
# and the two MQ101's stage 9000 starts when it is stopped (NG-19, NG-N1). MQ101Debug: see below. The first build's
# override of 10 was the developer start at the pirate fight (28 Oct run 1: opening_stage=250, our quest stood down);
# the second build's 2 matched no start and hung the first load (28 Oct run 2). MQ00's stage 10 writes 10 but is not a
# start-up stage, so vanilla never does.
DEFAULT_HOLD = ("MQ00", "MQ101", "MQ101PostQuest", "MQ_TutorialQuest_Misc04")
# GLOB MQ101Debug (Starfield.esm 0A7D31) at the start: the build overrides it NOT AT ALL by default (None). Each of MQ101's
# stage-0 entries that matches moves the player into the game (the intro's Item_02: moveto CharGenStartMarker, then
# WaitFor3dLoad); a value no entry matches moves nobody and the new game never leaves its loading screen (28 Oct run 2,
# value 2: the quest started, its version alias logged, but OnQuestInit never fired). With our own start (the plugin's
# StartupQuest_DO override, the owner's pick F) MQ101 never runs; the quest writes DEBUG_AFTER_HOLD (the value the main
# quests' developer skip-start stages write; a normal intro leaves 0) right after the hold-off's first pass, once the
# player has been moved, which opens PEO_SustenanceAllowed's "MQ101Debug != 0" (its normal route, MQ101 stage 310, is
# never reached); --debug-after-hold, 0 writes nothing.
DEFAULT_MQ101DEBUG = None
DEBUG_AFTER_HOLD = 2
DEBUG_INTRO = 0               # Starfield's own intro, entry 2
DEBUG_START_PIRATES = 10      # the first build's value: Fragment_Stage_0000_Item_10, SetStage 210 and 250 (28 Oct run 1)
DEBUG_UNMATCHED = 2           # the second build's value: no entry, no move, an endless loading screen (28 Oct run 2)
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
# OFF until an in-game run shows what Starfield leaves the player with when MQ101 never runs. --clear-inventory
# makes the quest script call RemoveAllItems (FO4's arguments; Starfield's third parameter is abRespectTargetCapacity,
# so whether quest items stay is unverified) once the player is in the vault and log "inventory cleared removed=<n>
# left=<n>"; --vault-suit <EditorID> (only with it) names the port's ARMO the script then adds and equips ("vault suit
# equipped ..."), resolved offline by the writer with the same owner checks as the other ids.
DEFAULT_CLEAR_INVENTORY = False
# The vault anchor's mode (Program.cs DefaultRequirePersistentAnchor, held equal by tests/test_newgame.py). The port
# installed on 21 Oct had no persistent reference in FO4Port_Vault111Cryo (0 of 1,166; its COC marker 001338 and every
# terminal temporary), and a temporary reference of an unloaded cell resolves to None (verified 16 Oct), so the writer
# can anchor on the temporary COC marker and have the quest script load the cell first (Debug.CenterOnCell, the
# AnchorTemporary / VaultCell properties). The port of run 3 (28 Oct) has the marker persistent. Since newgame_v11 the
# temporary mode is refused by default: its centering comes during our own start's first load, and when it moves nobody
# the start hands nothing back (29 Oct review on #588); --allow-temporary-anchor builds it on request, and
# --require-persistent-anchor (the default now) is kept for old command lines. check prints the mode after the anchor
# ("vault anchor FO4Port.esm:<id> persistent|temporary"), anchor_mode reads it into plan.json.
DEFAULT_REQUIRE_PERSISTENT_ANCHOR = True
ANCHOR_LINE = re.compile(r"vault anchor FO4Port\.esm:(?P<id>[0-9A-Fa-f]+) (?P<mode>persistent|temporary)\b")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_newgame.0.log")
LINE = re.compile(r"FO4SF_NEWGAME rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")
# the natives each script calls and the events it handles, by the base script that must declare them (precheck).
# Events are declarations too (Event OnMenuOpenCloseEvent in ScriptObject.psc), looked up the same way.
NATIVES = {
    # the inventory reset (ClearInventory, off by default) calls RemoveAllItems, GetItemCount, AddItem, EquipItem and
    # IsEquipped with FO4's signatures; whether Starfield's declare them the same way is what this precheck reads. The
    # temporary-anchor mode calls Debug.CenterOnCell(string) (FO4's signature; Starfield's Debug.psc declares it too,
    # read in ContentResources.zip 29 Oct; whether it works in retail is unverified until the PC run).
    # Our own start: the events OnQuestStarted and OnQuestInit on Quest (Roleplayers' Alternate Start handles the first on
    # its startup quest), Game.FadeOutGame (its five-argument call), ObjectReference.WaitFor3DLoad (MQ101's own intro
    # waits so), Quest.StartNoWait and IsStarting (the hand back to MQ101, which waits for nothing)
    SCRIPT: {
        "Actor": ["GetLevel", "EquipItem", "IsEquipped"],
        "Debug": ["OpenUserLog", "TraceUser", "Notification", "CenterOnCell"],
        "Game": ["GetPlayer", "GetFormFromFile", "SetInChargen", "SetCharGenHUDMode", "FadeOutGame"],
        "GlobalVariable": ["GetValue", "SetValueInt"],
        "Message": ["Show"],
        "ObjectReference": ["MoveTo", "SetPosition", "SetAngle", "GetPositionX", "GetParentCell", "GetWorldSpace",
                            "IsInInterior", "Is3DLoaded", "WaitFor3DLoad", "GetOpenState", "SetOpen", "RemoveAllItems",
                            "GetItemCount", "AddItem"],
        "Quest": ["SetStage", "GetStage", "IsRunning", "IsStarting", "StartNoWait", "Stop", "CompleteQuest",
                  "SetObjectiveDisplayed", "SetObjectiveCompleted", "SetActive", "OnQuestStarted", "OnQuestInit"],
        "ScriptObject": ["StartTimer"],
        "Utility": ["GetCurrentRealTime"],
    },
    LOOKS: {
        "Debug": ["TraceUser"],
        "Game": ["ShowRaceMenu"],
        "Message": ["Show"],
        "Quest": ["SetStage", "GetStage", "OnQuestStarted", "OnQuestInit"],
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
        "Quest": ["GetStage", "OnQuestStarted", "OnQuestInit"],
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


def read_text(path):
    """The file's text, "" when there is none (a core set or stage without a README)."""
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


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


# the guard's day limit (FO4SF_NewGameQuest MaxNewGameDays, held equal by tests/test_newgame.py). Starfield's clock
# starts at GameHour 8 (the record's value, docs/ai/test-queue.md) and GameDaysPassed carries the hour, so a new game
# reads about 0.3335 one second in: verified in game 28 Oct, two runs (0.333530 with MQ101 at stage 0, 0.333537 at
# 250). The first build's 0.25 stood every new game down on this test alone; a player's save should never start the
# startup quest (supported hypothesis), so one game day is the bound here.
MAX_NEW_GAME_DAYS = 1.0
NEW_GAME_DAYS_MEASURED = 0.3335


def is_new_game(days, level, max_days=MAX_NEW_GAME_DAYS, max_level=1):
    """FO4SF_NewGameQuest.IsNewGame, the whole guard: fewer than max_days game days passed and the player at most
    max_level. Only a New Game (or a New Game+, which keeps the player's level) should start the startup quest, never
    a save (supported hypothesis, the doc's section 1 step 2), so newgame_v9's opening-stage test (is_fresh_start, 21
    Oct review on #393) had nothing left to judge. A console start under a day at level 1 passes, as a New Game does."""
    return days < max_days and level <= max_level


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


def parent_of(source):
    """The base script a source extends ("Scriptname Actor extends ObjectReference"), or None."""
    m = re.search(r"^\s*Scriptname\s+[\w:]+\s+extends\s+([\w:]+)", source, re.M | re.I)
    return m.group(1) if m else None


def declares(sources, base, name, depth=8):
    """True when base's source, or one it extends (Actor extends ObjectReference extends Form ...), declares name. The
    Papyrus compiler resolves an inherited call the same way: FO4SF_NewGameSpecial compiled on the PC (newgame_v7) while
    a check of Actor.psc alone said Actor.SetValue was missing (28 Oct), so the two are declared above Actor. Bounded
    by depth and by a seen set (a cycle in the sources stops the walk)."""
    seen = set()
    while base and base.lower() not in seen and len(seen) < depth:
        seen.add(base.lower())
        source = sources.get(base.lower(), "")
        if has_function(source, name):
            return True
        base = parent_of(source)
    return False


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
        natives[script] = {f"{b}.{f}": declares(sources, b, f) for b, fs in bases.items() for f in fs}
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
    if a.debug_after_hold is not None:
        opts += ["--debug-after-hold", str(a.debug_after_hold)]
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
    if a.allow_temporary_anchor:
        if a.require_persistent_anchor:
            sys.exit("--allow-temporary-anchor and --require-persistent-anchor contradict each other")
        opts.append("--allow-temporary-anchor")
    return opts


def mq101debug_option(a):
    """The GLOB MQ101Debug override the build writes at the start: None (no override, the default since 28 Oct run 2, and
    under --no-mq101debug), else the value given with --mq101debug (experiments only)."""
    if a.no_mq101debug:
        return None
    return DEFAULT_MQ101DEBUG if a.mq101debug is None else a.mq101debug


def debug_after_hold_option(a):
    """The value the quest writes into MQ101Debug right after the hold-off (0: nothing)."""
    return DEBUG_AFTER_HOLD if a.debug_after_hold is None else a.debug_after_hold


def build_version_option(a):
    """The version number the build writes to GLOB FO4SF_NewGameVersion: None under --no-version, else the value
    given or the default."""
    if not a.version:
        return None
    return DEFAULT_BUILD_VERSION if a.build_version is None else a.build_version


def anchor_mode(check_text):
    """The vault anchor as check printed it: {"id": "<hex>", "mode": "persistent" | "temporary"}; None when the text has
    no such line (a check that never reached the anchor). "temporary" means the quest script centers on the vault cell
    before the marker resolves (AnchorTemporary); plan.json records it as "anchor"."""
    m = ANCHOR_LINE.search(check_text)
    return {"id": m.group("id").upper(), "mode": m.group("mode")} if m else None


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
    anchor = anchor_mode(check)
    if anchor is None:
        sys.exit(f"check printed no vault anchor line (persistent or temporary); attempt kept in {out}")
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
            "options": {"hold": a.hold or ",".join(DEFAULT_HOLD), "mq101debug": mq101debug_option(a), "debug_after_hold": debug_after_hold_option(a), "looks": a.looks,
                        "race_menu_mode": DEFAULT_RACE_MENU_MODE if a.race_menu_mode is None else a.race_menu_mode,
                        "special": a.special, "version": a.version,
                        "build_version": build_version_option(a),
                        "clear_inventory": bool(a.clear_inventory), "vault_suit": a.vault_suit if a.clear_inventory else None,
                        "allow_temporary_anchor": bool(a.allow_temporary_anchor)},
            "anchor": anchor,
            "stages": {str(n): what for n, what in STAGE_CONTRACT.items()}, "points": pts,
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_newgame.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Fallout 4 new game (Claude-cloud, {datetime.date.today().isoformat()}). docs/newgame/vault111-start.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_NewGame "{pts['quest_name']}" (run once, Starfield's startup quest: DFOB StartupQuest_DO overridden),
MESG FO4SF_NewGameElevator and FO4SF_NewGameStart{', FO4SF_NewGameTerminal and FO4SF_NewGameSpecial, 7 AVIF FO4SF_Special_<stat>' if a.special else ''}{f', GLOB FO4SF_NewGameVersion = {build_version_option(a)} and a player alias (the save version check)' if a.version else ''};
master Starfield.esm only. Scripts: {', '.join(s + '.pex' for s in scripts)} in Data\\Scripts.
Checked against (the ids it resolves at run time must stay): {json.dumps(before)}. Re-stage after a port or core change.
Pod {pts['pod']['src']} {pts['pod'].get('edid')}; arrival {pts['arrival']['pos']} m (core-local); {len(pts.get('terminals', []))} terminal(s) in the cell.
Inventory reset at the pod: {('ON (whether quest items stay is unverified; left= says how many stayed, not which), vault suit ' + (a.vault_suit or 'none')) if a.clear_inventory else 'off (the default until the first in-game proof)'}.
Vault anchor FO4Port.esm:{anchor['id']} {anchor['mode']}{' (the script centers on the vault cell first: the log says "centered on ...")' if anchor['mode'] == 'temporary' else ''}.
Options {json.dumps(plan['options'])}.
Install: not now. When the owner says so (game closed): fold into a core set (the folded README gives the exp_install.py
command, every plugin listed), verify, then exp_install.py.
In game: a NEW game from the main menu only (a save should never start the quest, nor a coc from the menu). Read the run:
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


INSTALL_LINE = re.compile(r"exp_install\.py install\b.*--plugins (?P<plugins>\S+)")


def core_plugins(core_dir, readme):
    """The core set's plugins in install order: the --plugins list of its README's exp_install.py install line when it
    has one (the first named plugin names the --pack archive), else its .esm files sorted. The README's list must be
    exactly the .esm files present: a README naming another set is a core set that cannot be installed as it says."""
    present = sorted(f for f in os.listdir(core_dir) if f.lower().endswith(".esm"))
    if not present:
        sys.exit(f"fold refused: {core_dir} holds no .esm")
    m = INSTALL_LINE.search(readme)
    if not m:
        return present
    listed = m.group("plugins").split(",")
    if sorted(listed) != present:
        sys.exit(f"fold refused: {core_dir}'s README installs {listed} but the folder holds {present}")
    return listed


def install_command(plugins):
    return f"scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(plugins)} --pack"


def folded_readme(core_readme, stage_readme, plugins, plugin, stage):
    """The folded set's README.txt: the core's, with the --plugins list of every exp_install.py install line widened to
    the whole set, then the stage's README and the one install command. exp_install.py installs only the plugins
    listed (none listed: the first .esm alphabetically), so the core's own command, copied as it was, would install the
    core and never the new game (Codex review on #393)."""
    def widen(line):
        m = INSTALL_LINE.search(line)
        return line[:m.start("plugins")] + ",".join(plugins) + line[m.end("plugins"):] if m else line

    return "\n".join([widen(line) for line in core_readme.splitlines()] + ["", f"==== {plugin} folded in ({datetime.date.today().isoformat()}) from {stage} ====",
                             stage_readme.rstrip("\n"), "",
                             f"Install (game closed): this folder, EVERY plugin listed. exp_install.py activates only "
                             f"the plugins of --plugins (none: the first .esm alphabetically), so a core-only or "
                             f"plugin-less command never installs {plugin}:",
                             "  " + install_command(plugins)]) + "\n"


def fold(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.stage, "plan.json"))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"{a.core_dir} already holds {plan['plugin']}")
    core_readme = read_text(os.path.join(a.core_dir, "README.txt"))
    stage_readme = read_text(os.path.join(a.stage, "README.txt"))
    plugins = core_plugins(a.core_dir, core_readme) + [plan["plugin"]]
    out = new_partial(final, create=False)
    shutil.copytree(a.core_dir, out)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(folded_readme(core_readme, stage_readme, plugins, plan["plugin"], os.path.abspath(a.stage)))
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
    print("install (game closed): " + install_command(plugins))
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
    "special", "version_saved", "version_load", "version_mismatch", "inventory_cleared", "vault_suit", "centered",
    "entered_vault", "pod_settle", "surfaced", "landed", "fell", "stood_down", "stand_down", "handing_back",
    "handed_back", "start", "start_events", "start_wait", "waiting_3d", "fade", "guard", "last_status", "runs",
    "earlier_completed"}.
    Our own start (newgame_v11, the startup quest): "start" is the start's first line ("<route> player_loaded=<bool>
    cell=<cell> loading=<bool>", the start event that ran it, its two readings and whether either said the game was
    still loading, which decides a hand back), "start_events" every start event that came, the one that ran the start
    first, then any "came after the start" (which fire on 1.16.244 is what run 4 shows), "start_wait" the end of the
    start's wait for the player's 3D ("loaded=<bool>": false leaves the fade to the timer), "waiting_3d" the timer's
    last line while it still waits for that 3D ("tick=<n> vault_moves=<n> centered=<n> cell=<cell>", every 10 ticks;
    None when the 3D came sooner, or the timer never ran then) and "fade" the one fade in ("by=<start|timer>
    loaded=<bool> cell=<cell>; ..."); an older build's log has none of them (None, and no events).
    "stood_down" is true on either stand-down ("not a new game: ..." or "no move into the vault: ...", the line in
    "stand_down"). The hand back to Starfield's opening writes two lines: "handing_back" is the first ("<why>;
    mq101debug=<n>"), written before the request, and "handed_back" the second ("requested=<bool> opening
    starting=<bool> running=<bool> stage=<n>"), MQ101's state right after a request that waits for nothing: no
    verdict. Both None when nothing was handed back (a stand-down whose readings both said the game runs, or a start
    that went on); "handing_back" alone means the request never returned.
    "guard" is the guard's readings line ("days=<n> level=<n> opening_stage=<n> opening_running=<bool> mq101debug=<n>
    write_after_hold=<n>"; newgame_v9 and v10 also wrote "fresh=<bool>"; None in a build before 28 Oct).
    "mq101debug_written" is the write right after hold-off pass 1 ("<n> was=<n>"; None when the build writes nothing,
    or when the hold-off never ran: run 2 of 28 Oct has only the version line, the game never finished its first load).
    "inventory_cleared" is the reset's line ("removed=<n> left=<n>"; None when the build kept the inventory) and
    "vault_suit" the suit's ("equipped <armor> worn=<bool>", or that it did not resolve; None when none was named).
    "centered" is the temporary-anchor mode's first centering line ("<cell> attempt=1 tick=<n>: ..."; None in the
    persistent mode, which never centers, or when the anchor resolved at once). "entered_vault" is the last move's
    verdict, or true once the timer confirms after the load that the start's move took ("enter vault confirmed").
    "pod_settle" is where the player stood the first loaded tick after the move into the pod ("ok=<bool> pos=<x y z>
    dx=<n> dy=<n> drop=<n>"; None in a build before newgame_v10, which had no such line: run 3 of 28 Oct sank under the
    pod's z and the game put the player on the COC marker). "surfaced" is the last "surface setposition" line: since
    newgame_v10 it says whether the merged arrival took ("ok=<bool> set=<n> pos=... target=...").
    "stages_named" reads each stage reached by the contract (STAGE_CONTRACT); "held_off_by_pass" says what each
    hold-off pass stopped (since newgame_v11 pass 1 in the start right after the move, pass 2 once the vault has loaded;
    before it pass 1 came before the move and pass 2 a tick later); "looks_done" says what ended the looks wait
    ("creator closed", "quick start", or the quest's "LooksWait fallback ..."); "special"
    is the SPECIAL script's ending ("set S=.. P=.. ..." or "skipped: ..." when the player left the vault without it;
    "later" and "left" prompts are not endings). "version_saved" is the build version the version script recorded
    when the new game started, "version_load" the last "saved=<n> installed=<n>" line of a save load (a load logs no
    "init", so it joins the run before it) and "version_mismatch" whether any load found the two apart. Only the
    latest run is judged; "runs" counts the runs in the file and "earlier_completed" says whether an older one reached
    stage 200 (kept as history, never as the current result). Lines of other logs are ignored."""
    s = {"stages": [], "stages_named": [], "held_off": [], "held_off_by_pass": {}, "looks_done": None, "special": None,
         "version_saved": None, "version_load": None, "version_mismatch": False,
         "inventory_cleared": None, "vault_suit": None, "centered": None,
         "entered_vault": None, "pod_settle": None, "surfaced": None, "landed": None, "fell": False, "stood_down": False,
         "stand_down": None, "handing_back": None, "handed_back": None, "start": None, "start_events": [],
         "start_wait": None, "waiting_3d": None, "fade": None,
         "guard": None, "mq101debug_written": None, "last_status": None, "runs": 0, "earlier_completed": False}
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
        elif msg.startswith("centered on "):
            if s["centered"] is None:                        # the first centering; a second one is the bound's retry
                s["centered"] = msg[len("centered on "):]
        elif msg.startswith("enter vault ok="):
            # Starfield's Papyrus prints a bool as "true" / "false" (the 28 Oct log: anchor_temporary=true), FO4's
            # tests wrote "True"; both read
            s["entered_vault"] = msg.split()[2].lower() == "ok=true"
        elif msg.startswith("enter vault confirmed "):
            s["entered_vault"] = True                        # the start's move took: the timer saw the vault cell
        elif msg.startswith("pod settle "):
            if s["pod_settle"] is None:                      # the script checks once
                s["pod_settle"] = msg[len("pod settle "):]
        elif msg.startswith("surface setposition "):
            s["surfaced"] = msg
        elif msg.startswith("landed "):
            s["landed"] = True
        elif msg.startswith("fell "):
            s["fell"] = True
        elif msg.startswith("not a new game") or msg.startswith("no move into the vault"):
            s["stood_down"] = True
            s["stand_down"] = msg
        elif msg.startswith("handing back to Starfield's start: "):
            s["handing_back"] = msg[len("handing back to Starfield's start: "):]
        elif msg.startswith("handed back: "):
            s["handed_back"] = msg[len("handed back: "):]
        elif msg.startswith("start route="):
            s["start"] = msg[len("start route="):]
            # the event that ran the start: first, since the script writes the other event's line after this one
            # (Begin's lateRoute, 29 Oct review on #588)
            s["start_events"].append(s["start"].split()[0])
        elif msg.startswith("start event "):
            s["start_events"].append(msg.split()[2])         # "start event <route> came after the start: ..."
        elif msg.startswith("3d wait over "):
            s["start_wait"] = msg[len("3d wait over "):]
        elif msg.startswith("waiting for the 3d "):
            s["waiting_3d"] = msg[len("waiting for the 3d "):]
        elif msg.startswith("fade in by="):
            if s["fade"] is None:                            # the script fades in once
                s["fade"] = msg[len("fade in "):]
        elif msg.startswith("guard "):
            s["guard"] = msg[len("guard "):]
        elif msg.startswith("mq101debug written="):
            s["mq101debug_written"] = msg[len("mq101debug written="):]
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
    s.add_argument("--mq101debug", type=float, default=None,
                   help=f"override GLOB MQ101Debug, experiments only (default: no override). MQ101 never runs with our own "
                        f"start, so it matters only when the start hands back to MQ101 (a New Game+, or no move into the vault): "
                        f"{DEBUG_INTRO} is the intro, {DEBUG_START_PIRATES} the pirate-fight developer start of 28 Oct run 1, "
                        f"{DEBUG_UNMATCHED} matched no entry and never left the loading screen (run 2)")
    s.add_argument("--no-mq101debug", action="store_true",
                   help="kept for old command lines: the default already writes no override; it still cancels a --mq101debug given with it")
    s.add_argument("--debug-after-hold", type=int, default=None,
                   help=f"the value the quest writes into MQ101Debug right after the hold-off's first pass (default "
                        f"{DEBUG_AFTER_HOLD}, the developer skip-start value, which opens the sustenance condition; 0 writes nothing)")
    s.add_argument("--pod-ref", default=None, help="the player's pod in Vault111Cryo, FO4 hex id (when points finds several)")
    s.add_argument("--clear-inventory", action="store_true",
                   help="empty the player's inventory once the player is confirmed in the vault, before stage 10 "
                        "(NG-K8; off by default; whether quest items stay is unverified)")
    s.add_argument("--vault-suit", default=None, metavar="EDITORID",
                   help="with --clear-inventory: the port's ARMO the script adds and equips after the reset, by EditorID")
    s.add_argument("--allow-temporary-anchor", action="store_true",
                   help="build on a port whose vault cell has no persistent reference: anchor on its temporary COC "
                        "marker, and the script centers on the cell first (unverified during our own start's first load, "
                        "and a centering that moves nobody hands nothing back; refused by default)")
    s.add_argument("--require-persistent-anchor", action="store_true",
                   help="kept for old command lines: the default since newgame_v11 already refuses a vault cell without "
                        "a persistent reference")
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
