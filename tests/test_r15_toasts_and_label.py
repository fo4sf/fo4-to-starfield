"""Round 15 Wave A Item 2:
1. Duplicate NEW MISSION / MISSION UPDATED toast suppression in FO4SF_Codsworth01Quest.psc
   behind `bool Property MuteDuplicateObjectiveToasts = True Auto Const`.
2. Stage-time `Data/Interface/Translate_en.txt` generator (`scripts/ui/make_quest_translate.py`)
   replacing Starfield's 6 `$Mission*` HUD toast/status lines behind `--mode quest|mission`
   and `--label QUEST` (preserving Out of Time / all other lines, UTF-16LE BOM, and CRLF).
3. Header-only SFSE helper `sfse/FO4SFPipboyMenu/src/hud_quest_label.h` parsing
   `[FO4SFPipboyMenu]` `ReplaceMissionLabel` and `QuestHudLabel`.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
for _p in (str(TESTS_DIR), str(REPO / "src"), str(REPO / "scripts" / "core"), str(REPO / "scripts" / "mission"), str(REPO / "scripts" / "ui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ba2_fixture  # noqa: E402
from fo4sf import ba2  # noqa: E402
import make_core_bundle  # noqa: E402
import make_mission  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402
import make_quest_translate  # noqa: E402
import test_mission  # noqa: E402

CODS_PSC = REPO / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"
MIN00_PSC = REPO / "scripts" / "mission" / "FO4SF_Min00Quest.psc"
TOAST_UTIL_PSC = REPO / "scripts" / "mission" / "FO4SF_QuestToastUtil.psc"
NEWGAME_PSC = REPO / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc"
GAME_START_CFG = REPO / "src" / "fo4sf" / "core" / "game_start_config.json"
MISSION_CS = REPO / "dotnet" / "Mission" / "Program.cs"
HUD_HEADER = REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "hud_quest_label.h"
MAIN_CPP = REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp"
REAL_STARFIELD_DATA = Path(r"D:\SteamLibrary\steamapps\common\Starfield\Data")
REAL_INTERFACE_BA2 = REAL_STARFIELD_DATA / "Starfield - Interface.ba2"


class _MockActorRef:
    def __init__(self, label, pos=(-2346.709, -1406.163, 111.734)):
        self.label = label
        self.pos = list(pos)
        self.spawned = []
        self.disabled = False
        self.scale = 1.0
        self.allow_pc = False
        self.blocked = None

    def __repr__(self):
        return self.label

    def AllowPCDialogue(self, flag):
        self.allow_pc = bool(flag)

    def BlockActivation(self, blocked=True, hide=False):
        self.blocked = (bool(blocked), bool(hide))

    def StopCombat(self):
        return None

    def SetRestrained(self, _flag):
        return True

    def SetScale(self, scale):
        self.scale = float(scale)

    def EnableNoWait(self, _fade=False):
        self.disabled = False
        return True

    def IsDisabled(self):
        return self.disabled

    def IsDeleted(self):
        return False

    def IsDead(self):
        return False

    def Is3DLoaded(self):
        return True

    def IsInInterior(self):
        return False

    def GetPositionX(self):
        return self.pos[0]

    def GetPositionY(self):
        return self.pos[1]

    def GetPositionZ(self):
        return self.pos[2]

    def SetPosition(self, x, y, z):
        self.pos = [float(x), float(y), float(z)]

    def PlaceAtMe(self, form, count=1, persistent=False, disabled=False, delete_when_able=False):
        prx = _MockActorRef("CodsworthTalkProxyRef", tuple(self.pos))
        prx.disabled = bool(disabled)
        self.spawned.append((form, prx, bool(persistent), bool(disabled), bool(delete_when_able)))
        return prx


def _build_codsworth_harness(*, mute_duplicates=True, landing_handoff="two_quests", is_objective_displayed=False, fail_display=False):
    c_psc = CODS_PSC.read_text(encoding="utf-8")
    logs = []
    obj_calls = []
    top_calls = []
    active_calls = []
    timers = []
    stages = set()
    cur_stage = [0]
    displayed_objs = {10} if is_objective_displayed else set()

    cods = _MockActorRef("Codsworth(09000811)", (-2346.709, -1406.163, 111.734))
    player = _MockActorRef("Player", (-2345.0, -1405.0, 111.8))
    cods_alias = SimpleNamespace(GetActorRef=lambda: None, ForceRefTo=lambda *_a: None)

    def set_stage(n):
        stages.add(int(n))
        if int(n) > cur_stage[0]:
            cur_stage[0] = int(n)

    def set_obj_displayed(obj, disp=True, force=False):
        obj_calls.append((int(obj), bool(disp), bool(force)))
        if disp and not fail_display:
            displayed_objs.add(int(obj))
        elif not disp:
            displayed_objs.discard(int(obj))

    ns = {
        "Trace": lambda m: logs.append(str(m)),
        "LogName": "fo4sf_mission",
        "Codsworth": cods,
        "CodsworthTalkActi": "FO4SF_CodsworthTalkActi(09000970)",
        "CodsworthTalkMsg": None,
        "CodsworthReply0Msg": None,
        "CodsworthReply1Msg": None,
        "CodsworthReply2Msg": None,
        "TalkUseMessageBox": None,
        "MuteDuplicateObjectiveToasts": mute_duplicates,
        "LandingHandoff": landing_handoff,
        "CodsworthLocalX": -1146.709,
        "CodsworthLocalY": 1293.837,
        "CodsworthLocalZ": 111.734,
        "MergeOffsetX": -1200.0,
        "MergeOffsetY": -2700.0,
        "ProxyHoldRadius": 25.0,
        "ProxyBindRadius": 180.0,
        "ProxyZOffset": 1.36,
        "ProxyScale": 1.6,
        "ProxyResyncDrift": 0.25,
        "MinTalkCameraDistance": 1.65,
        "SafeTalkCameraDistance": 1.85,
        "SceneOpenCheckSeconds": 1.5,
        "SceneMaxWaitChecks": 16,
        "MaxSceneRestarts": 3,
        "S3Stage50Scene": None,
        "EnableS3HouseSearch": False,
        "instanceStarted": False,
        "dialogueSeen": False,
        "dialogueMenuOpen": False,
        "talkBoxOpen": False,
        "sceneTalkPending": False,
        "sceneMenuOpened": False,
        "scenePhase1Entered": False,
        "scenePhase1At": 0.0,
        "sceneCheckTicks": 0,
        "sceneRestartCount": 0,
        "scenePostActive": False,
        "ownSceneStopPending": False,
        "sceneAttemptStartedAt": 0.0,
        "talkSessionId": 0,
        "codsworthTalkReloaded": False,
        "concordCleared": False,
        "talkProxy": None,
        "proxyLogged": False,
        "proxyLastX": 0.0,
        "proxyLastY": 0.0,
        "proxyLastZ": 0.0,
        "applied": 0,
        "pendingStage": -1,
        "pendingStageBy": "other",
        "choice1Seen": False,
        "choice2Seen": False,
        "choice3Seen": False,
        "choice4Seen": False,
        "choicesCount": 0,
        "completed": False,
        "objective10DisplayedOnce": False,
        "objective10SkipLogged": False,
        "IsRunning": lambda: True,
        "Start": lambda: True,
        "Stop": lambda: None,
        "GetStage": lambda: cur_stage[0],
        "GetStageDone": lambda s: int(s) in stages,
        "SetStage": set_stage,
        "GetAlias": lambda idx: cods_alias if idx == 0 else None,
        "IsObjectiveDisplayed": lambda obj: int(obj) in displayed_objs,
        "SetObjectiveDisplayed": set_obj_displayed,
        "SetObjectiveDisplayedAtTop": lambda obj: top_calls.append(int(obj)),
        "SetObjectiveCompleted": lambda *_a: None,
        "SetActive": lambda act=True: active_calls.append(bool(act)),
        "StartTimer": lambda sec, tid: timers.append((float(sec), int(tid))),
        "CancelTimer": lambda *_a: None,
        "RegisterForRemoteEvent": lambda *_a: None,
        "RegisterForMenuOpenCloseEvent": lambda *_a: None,
        "Debug": SimpleNamespace(OpenUserLog=lambda *_a: None),
        "Game": SimpleNamespace(
            GetPlayer=lambda: player,
            GetFormFromFile=lambda *_a: None,
        ),
    }

    code = test_mission._translate_mission_psc(
        c_psc,
        (
            "EffectiveStage",
            "ShowCodsworthObjective",
            "ResolveCodsworth",
            "ResolveTalkActi",
            "ResolveCodsworthScene",
            "ResolveCodsworthPostScene",
            "EnsureCodsworthAlias",
            "EnsureKeeperCodsworthAlias",
            "RegisterCodsworthSceneEvents",
            "BindCodsworthActivation",
            "EnsureTalkProxy",
            "ClearObjectiveOnConcordStart",
            "AdvanceTo",
            "IsWarfareMode",
            "StartQuestInstance",
            "OnTimer",
            "SyncProgress",
        ),
        (
            "instanceStarted",
            "dialogueSeen",
            "talkSessionId",
            "concordCleared",
            "talkProxy",
            "proxyLogged",
            "proxyLastX",
            "proxyLastY",
            "proxyLastZ",
            "applied",
            "pendingStage",
            "pendingStageBy",
            "choice1Seen",
            "choice2Seen",
            "choice3Seen",
            "choice4Seen",
            "choicesCount",
            "completed",
            "objective10DisplayedOnce",
            "objective10SkipLogged",
        ),
    )
    exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)
    return SimpleNamespace(
        ns=ns,
        logs=logs,
        obj_calls=obj_calls,
        top_calls=top_calls,
        active_calls=active_calls,
        timers=timers,
        player=player,
        cods=cods,
    )


class CodsworthDuplicateToastTests(unittest.TestCase):
    def test_mute_flag_is_default_true_and_not_mandatory(self):
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        self.assertRegex(c_psc, r"(?m)^bool Property MuteDuplicateObjectiveToasts = True Auto Const$")
        self.assertNotIn("MuteDuplicateObjectiveToasts", make_mission.mandatory_properties(c_psc))
        proxy_body = test_mission.function_body(c_psc, "EnsureTalkProxy")
        self.assertNotIn("SetObjectiveDisplayed(", proxy_body)
        self.assertNotIn("SetActive(", proxy_body)

    def test_no_papyrus_keywords_or_exponent_literals_in_codsworth(self):
        c_psc = CODS_PSC.read_text(encoding="utf-8")
        code = re.sub(r"\{[^}]*\}", "", c_psc)
        code = "\n".join(line.split(";")[0] for line in code.splitlines())
        self.assertIsNone(re.search(r"\d[eE][-+]?\d", code))
        keywords = {"as", "auto", "bool", "const", "else", "elseif", "endevent", "endfunction", "endif", "event",
                    "extends", "false", "float", "function", "if", "int", "new", "none", "property", "return",
                    "scriptname", "state", "string", "true", "while"}
        code_no_str = re.sub(r'"[^"]*"', '""', code)
        names = [n for n in re.findall(r"\b(?:bool|int|float|string|Actor|Scene|ObjectReference|GlobalVariable|Message|Activator)[ \t]+(\w+)", code_no_str, re.I)
                 if n not in ("Property", "Function")]
        self.assertEqual([n for n in names if n.lower() in keywords], [])

    def test_muted_default_displays_objective_once_without_force_or_spam(self):
        h = _build_codsworth_harness(mute_duplicates=True, landing_handoff="two_quests", is_objective_displayed=False)
        h.ns["StartQuestInstance"]()

        # Exactly one non-forced display, SetActive(True) once, SetObjectiveDisplayedAtTop(10) once
        self.assertEqual(h.obj_calls, [(10, True, False)])
        self.assertEqual(h.active_calls, [True])
        self.assertEqual(h.top_calls, [10])
        self.assertTrue(h.ns["objective10DisplayedOnce"])
        self.assertTrue(any(ln.lower() == "codsworth01 objective10_toast shown=true muted_duplicates=true force=false" for ln in h.logs), h.logs)

        # EnsureTalkProxy spawns proxy without re-displaying Objective 10
        h.ns["EnsureTalkProxy"](h.player)
        self.assertIsNotNone(h.ns["talkProxy"])
        self.assertEqual(h.obj_calls, [(10, True, False)])
        self.assertEqual(h.active_calls, [True])

        # Repeated ShowCodsworthObjective() and 10 ticks of OnTimer(1) never re-display Objective 10
        h.ns["ShowCodsworthObjective"]()
        for _ in range(10):
            h.ns["OnTimer"](1)
        self.assertEqual(h.obj_calls, [(10, True, False)])
        self.assertEqual(h.top_calls, [10])
        skip_logs = [ln for ln in h.logs if "codsworth01 objective10_toast skipped=true" in ln]
        self.assertEqual(len(skip_logs), 1)

        # ClearObjectiveOnConcordStart clears Objective 10 cleanly
        h.ns["ClearObjectiveOnConcordStart"]()
        self.assertEqual(h.obj_calls[-1], (10, False, False))
        self.assertEqual(h.active_calls[-1], False)

    def test_single_quest_handoff_displays_codsworth01_go_home_once_and_latch_requires_displayed(self):
        h_single = _build_codsworth_harness(mute_duplicates=True, landing_handoff="single_quest")
        h_single.ns["StartQuestInstance"]()
        for _ in range(5):
            h_single.ns["OnTimer"](1)
        self.assertEqual(h_single.obj_calls, [(10, True, False)])
        self.assertEqual(h_single.top_calls, [10])
        self.assertTrue(h_single.ns["objective10DisplayedOnce"])

        # Latch stays False when IsObjectiveDisplayed(10) returns False (fail_display=True)
        h_fail = _build_codsworth_harness(mute_duplicates=True, landing_handoff="two_quests", fail_display=True)
        h_fail.ns["StartQuestInstance"]()
        self.assertEqual(h_fail.obj_calls, [(10, True, False)])
        self.assertEqual(h_fail.top_calls, [])
        self.assertFalse(h_fail.ns["objective10DisplayedOnce"])
        self.assertIn("codsworth01 objective10_toast deferred=true reason=not_displayed muted_duplicates=True", h_fail.logs)

    def test_unmuted_flag_preserves_forced_display_and_retry(self):
        h = _build_codsworth_harness(mute_duplicates=False, landing_handoff="two_quests", is_objective_displayed=False)
        h.ns["StartQuestInstance"]()
        self.assertEqual(h.obj_calls, [(10, True, True)])
        self.assertEqual(h.top_calls, [10])
        self.assertTrue(any(ln.lower() == "codsworth01 objective10_toast shown=true muted_duplicates=false force=true" for ln in h.logs), h.logs)

        # When IsObjectiveDisplayed(10) is reset/not displayed, OnTimer(1) retries forced display
        h.ns["SetObjectiveDisplayed"](10, False, False)
        h.ns["OnTimer"](1)
        self.assertEqual(h.obj_calls, [(10, True, True), (10, False, False), (10, True, True)])
        self.assertEqual(h.top_calls, [10, 10])


class MakeQuestTranslateTests(unittest.TestCase):
    SAMPLE_LINES = [
        "$ACCEPT\tACCEPT",
        "$MISSION\tMISSION",
        "$MISSION COMPLETE\tMISSION COMPLETE",
        "$Mission Data\tMission Data",
        "$MISSION FAILED\tMISSION FAILED",
        "$Mission Info\tMission Info",
        "$Mission name\tMission Name",
        "$MISSION REWARDS\tMISSION REWARDS",
        "$MISSION STATUS\tMISSION STATUS",
        "$MISSION UPDATED\tMISSION UPDATED",
        "$MissionAdded\tADDED TO MISSION MENU",
        "$MissionComplete\tMISSION COMPLETE",
        "$MissionFailed\tMISSION FAILED",
        "$MissionMenu\tMISSION MENU",
        "$MissionMenu_ShowOnMap\tShow On Map",
        "$MissionNew\tNEW MISSION",
        "$MISSIONS\tMISSIONS",
        "$MissionUpdate\tMISSION UPDATED",
        "$QUEST\tMISSION",
        "$Quest\tMission",
        "$QUESTS\tMISSIONS",
        "$SET MISSION ACTIVE\tSET MISSION ACTIVE",
        "$YES\tYES",
    ]

    EXPECTED_QUEST_MAP = {
        "$MISSION": "QUEST",
        "$MISSIONS": "QUESTS",
        "$MISSION COMPLETE": "QUEST COMPLETE",
        "$MISSION FAILED": "QUEST FAILED",
        "$MISSION REWARDS": "QUEST REWARDS",
        "$MISSION STATUS": "QUEST STATUS",
        "$MISSION UPDATED": "QUEST UPDATED",
        "$MissionAdded": "ADDED TO QUEST LOG",
        "$MissionComplete": "QUEST COMPLETED",
        "$MissionFailed": "QUEST FAILED",
        "$MissionMenu": "QUEST LOG",
        "$MissionNew": "NEW QUEST",
        "$MissionUpdate": "QUEST UPDATED",
        "$Mission Data": "Quest Data",
        "$Mission Info": "Quest Info",
        "$Mission name": "Quest Name",
        "$QUEST": "QUEST",
        "$Quest": "Quest",
        "$QUESTS": "QUESTS",
        "$SET MISSION ACTIVE": "SET QUEST ACTIVE",
    }

    def _make_sample_ba2(self, tmp_dir: Path, *, encoding="utf-16-le", bom=b"\xff\xfe", eol="\r\n", trailing_eol=False) -> tuple[Path, bytes]:
        text = eol.join(self.SAMPLE_LINES) + (eol if trailing_eol else "")
        raw = bom + text.encode(encoding)
        ba2_bytes = ba2_fixture.general_archive({"interface\\translate_en.txt": raw}, compressed=True, version=2)
        data_dir = tmp_dir / "Starfield" / "Data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "Starfield - Interface.ba2").write_bytes(ba2_bytes)
        return data_dir, raw

    def test_synthetic_utf16le_bom_crlf_rewrites_exact_20_lines_and_pins_ba2_in_plan(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            data_dir, vanilla_raw = self._make_sample_ba2(tmp)
            stage_root = tmp / "stage"

            rc = make_quest_translate.main(["--starfield-data", str(data_dir), "--out", str(stage_root)])
            self.assertEqual(rc, 0)

            out_file = stage_root / "Data" / "Interface" / "Translate_en.txt"
            plan_file = stage_root / "plan.json"
            self.assertTrue(out_file.is_file())
            self.assertTrue(plan_file.is_file())
            out_bytes = out_file.read_bytes()
            self.assertTrue(out_bytes.startswith(b"\xff\xfe"))

            in_lines = vanilla_raw[2:].decode("utf-16-le").splitlines(keepends=True)
            out_lines = out_bytes[2:].decode("utf-16-le").splitlines(keepends=True)
            self.assertEqual(len(out_lines), len(in_lines))

            diffs = {}
            for a, b in zip(in_lines, out_lines):
                if a != b:
                    diffs[a.rstrip("\r\n").split("\t", 1)[0]] = b.rstrip("\r\n").split("\t", 1)[1]
                self.assertEqual(a.endswith("\r\n"), b.endswith("\r\n"))

            self.assertEqual(diffs, self.EXPECTED_QUEST_MAP)
            plan_doc = json.loads(plan_file.read_text(encoding="utf-8"))
            qt = plan_doc["quest_translate"]
            ba2_stat = (data_dir / "Starfield - Interface.ba2").stat()
            self.assertEqual(qt["source_ba2"]["size"], ba2_stat.st_size)
            self.assertEqual(qt["source_ba2"]["mtime_ns"], ba2_stat.st_mtime_ns)
            self.assertEqual(len(qt["source_ba2"]["sha256"]), 64)

            # Native mission mode preserves exact bytes
            mission_stage = tmp / "stage_mission"
            rc2 = make_quest_translate.main(["--starfield-data", str(data_dir), "--out", str(mission_stage), "--mode", "mission"])
            self.assertEqual(rc2, 0)
            self.assertEqual((mission_stage / "Data" / "Interface" / "Translate_en.txt").read_bytes(), vanilla_raw)

            # Custom --label support
            job_stage = tmp / "stage_job"
            rc3 = make_quest_translate.main(["--starfield-data", str(data_dir), "--out", str(job_stage), "--label", "JOB"])
            self.assertEqual(rc3, 0)
            job_text = (job_stage / "Data" / "Interface" / "Translate_en.txt").read_bytes()[2:].decode("utf-16-le")
            self.assertIn("$MissionNew\tNEW JOB\r\n", job_text)
            self.assertIn("$MissionUpdate\tJOB UPDATED\r\n", job_text)
            self.assertIn("$MISSIONS\tJOBS\r\n", job_text)
            self.assertIn("$Quest\tJob\r\n", job_text)
            self.assertIn("$MissionMenu\tJOB LOG\r\n", job_text)

    def test_refuses_unsafe_repo_or_game_output_paths(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            data_dir, _ = self._make_sample_ba2(tmp)
            # 1. Inside current Git worktree
            rc_repo = make_quest_translate.main(["--starfield-data", str(data_dir), "--out", str(REPO / "tmp_bad_out")])
            self.assertEqual(rc_repo, 1)
            # 2. Inside a game folder containing Starfield.exe
            game_dir = tmp / "FakeStarfield"
            game_dir.mkdir(parents=True, exist_ok=True)
            (game_dir / "Starfield.exe").write_bytes(b"MZ")
            rc_game = make_quest_translate.main(["--starfield-data", str(data_dir), "--out", str(game_dir / "stage")])
            self.assertEqual(rc_game, 1)

    @unittest.skipUnless(REAL_INTERFACE_BA2.is_file(), "Starfield - Interface.ba2 not installed on this host")
    def test_real_starfield_interface_ba2_exact_line_count_and_20_changes(self):
        vanilla_raw = ba2.Ba2(str(REAL_INTERFACE_BA2)).read("interface/translate_en.txt")
        self.assertTrue(vanilla_raw.startswith(b"\xff\xfe"), "expected UTF-16LE BOM in Starfield Translate_en.txt")
        vanilla_lines = vanilla_raw[2:].decode("utf-16-le").splitlines(keepends=True)

        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            quest_stage = tmp / "quest_stage"
            rc = make_quest_translate.main([
                "--starfield-data", str(REAL_STARFIELD_DATA),
                "--out", str(quest_stage),
                "--mode", "quest",
                "--label", "QUEST",
            ])
            self.assertEqual(rc, 0)
            out_path = quest_stage / "Data" / "Interface" / "Translate_en.txt"
            self.assertTrue(out_path.is_file())
            out_raw = out_path.read_bytes()
            self.assertTrue(out_raw.startswith(b"\xff\xfe"))

            out_lines = out_raw[2:].decode("utf-16-le").splitlines(keepends=True)
            self.assertEqual(len(out_lines), len(vanilla_lines))

            changed = []
            for idx, (orig, new) in enumerate(zip(vanilla_lines, out_lines), 1):
                if orig != new:
                    changed.append((idx, orig.rstrip("\r\n"), new.rstrip("\r\n")))
                self.assertEqual(orig.endswith("\r\n"), new.endswith("\r\n"), f"line {idx} EOL mismatch")

            self.assertEqual(len(changed), 20, f"expected 20 changed lines, got {len(changed)}: {changed}")
            changed_map = {orig.split("\t", 1)[0]: new.split("\t", 1)[1] for _i, orig, new in changed}
            self.assertEqual(changed_map, self.EXPECTED_QUEST_MAP)

            plan_doc = json.loads((quest_stage / "plan.json").read_text(encoding="utf-8"))
            st = REAL_INTERFACE_BA2.stat()
            self.assertEqual(plan_doc["quest_translate"]["source_ba2"]["size"], st.st_size)
            self.assertEqual(plan_doc["quest_translate"]["source_ba2"]["mtime_ns"], st.st_mtime_ns)

            # --mode mission keeps the real file byte-for-byte identical
            mission_stage = tmp / "mission_stage"
            rc_m = make_quest_translate.main([
                "--starfield-data", str(REAL_STARFIELD_DATA),
                "--out", str(mission_stage),
                "--mode", "mission",
            ])
            self.assertEqual(rc_m, 0)
            self.assertEqual((mission_stage / "Data" / "Interface" / "Translate_en.txt").read_bytes(), vanilla_raw)


class HudQuestLabelHeaderTests(unittest.TestCase):
    def test_header_contract_settings_rewrite_verify_and_runtime_probe(self):
        src = HUD_HEADER.read_text(encoding="utf-8")
        main_src = MAIN_CPP.read_text(encoding="utf-8")
        self.assertIn("namespace fo4sf::hud", src)
        self.assertIn("ReplaceMissionLabel", src)
        self.assertIn("QuestHudLabel", src)
        self.assertIn("RewriteMissionHudLabel", src)
        self.assertIn("VerifyTranslateEnFile", src)
        self.assertIn("TranslateFileStatus", src)
        self.assertIn("ParseQuestLabelIniText", src)
        self.assertIn("LoadQuestLabelConfig", src)
        self.assertIn("FormatStartupLog", src)
        self.assertIn("step=hud_quest_label mode={} label={} active={} file={} file_ok={}", src)
        for token in make_quest_translate.TARGET_KEY_TEMPLATES:
            self.assertIn(token, src)
        self.assertNotIn("Out of Time", src.split("RewriteMissionHudLabel", 1)[1])
        self.assertIn("VerifyTranslateEnFile(", main_src)
        self.assertIn("ProbeQuestLabelRuntime(", main_src)
        self.assertIn("BSScaleformManager", main_src)
        self.assertIn("step=hud_quest_label_runtime", main_src)


class SharedToastUtilMin00AndLandingHandoffTests(unittest.TestCase):
    def test_game_start_config_defaults(self):
        cfg = json.loads(GAME_START_CFG.read_text(encoding="utf-8"))
        self.assertEqual(cfg["landing_handoff_modes_supported"], ["single_quest", "two_quests"])
        for gid in ("fo4", "fo3", "fnv"):
            g = cfg["games"][gid]
            self.assertEqual(g["landing_handoff"], "single_quest")
            self.assertTrue(g["mute_duplicate_objective_toasts"])
            self.assertEqual(g["hud_label"], {"mode": "quest", "label": "QUEST"})

    def test_replace_mission_label_zero_keeps_vanilla_ini_and_no_rewrite(self):
        import make_probe_swf  # noqa: E402
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "Data" / "Interface").mkdir(parents=True)
            (tmp / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(make_probe_swf.movie_bytes())
            make_pipboy_stage_ini.generate_stage_ini(
                tmp, replace_mission_label=0, quest_hud_label="QUEST"
            )
            ini_txt = (tmp / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
            self.assertIn("ReplaceMissionLabel=0", ini_txt)
        src = HUD_HEADER.read_text(encoding="utf-8")
        self.assertIn("if (!a_cfg.Active()) {", src)

    def test_shared_show_objective_once_used_by_both_codsworth_and_min00(self):
        util_psc = TOAST_UTIL_PSC.read_text(encoding="utf-8")
        min_psc = MIN00_PSC.read_text(encoding="utf-8")
        cods_psc = CODS_PSC.read_text(encoding="utf-8")
        self.assertIn("bool Function ShowObjectiveOnce(", util_psc)
        self.assertIn("FO4SF_QuestToastUtil.ShowObjectiveOnce(", cods_psc)
        self.assertIn("FO4SF_QuestToastUtil.ShowObjectiveOnce(", min_psc)
        self.assertNotIn("Function ShowObjectiveOnce(", min_psc)
        self.assertNotIn("SetObjectiveDisplayed(", min_psc)

        # Execute Min00 GiveFromCodsworth, Apply(10/20/30), OnTimer(1) muted vs unmuted
        m_obj_calls = []
        m_displayed = set()
        m_logs = []
        preston = _MockActorRef("Preston", (-2011.14, -1697.54, 89.09))
        m_ns = {
            "Trace": lambda m: m_logs.append(str(m)),
            "KeeperOnly": False,
            "MuteDuplicateObjectiveToasts": True,
            "Raiders": [],
            "Credits": "Credits",
            "RewardCount": 100,
            "FindRadius": 20.0,
            "Preston": preston,
            "min00Given": False,
            "applied": 0,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "obj10DisplayedOnce": False,
            "obj85DisplayedOnce": False,
            "obj86DisplayedOnce": False,
            "IsRunning": lambda: True,
            "Start": lambda: True,
            "GetStage": lambda: m_ns["applied"],
            "SetStage": lambda *_a: None,
            "IsWarfareMode": lambda: False,
            "EnsurePrestonAlias": lambda: None,
            "EffectiveStage": lambda: m_ns["applied"],
            "IsObjectiveDisplayed": lambda o: int(o) in m_displayed,
            "SetObjectiveDisplayed": lambda o, d=True, f=False: (
                m_obj_calls.append((int(o), bool(d), bool(f))),
                m_displayed.add(int(o)) if d else m_displayed.discard(int(o)),
            ),
            "SetObjectiveCompleted": lambda *_a: None,
            "SetActive": lambda *_a: None,
            "CheckConcordRaidersWfc01": lambda *_a: None,
            "FoundPreston": lambda *_a: None,
            "CancelTimer": lambda *_a: None,
            "Game": SimpleNamespace(
                GetPlayer=lambda: _MockActorRef("Player", (-2500.0, -2500.0, 89.0)),
                GetFormFromFile=lambda *_a: None,
            ),
        }
        code = test_mission._translate_mission_psc(
            min_psc,
            ("GiveFromCodsworth", "AdvanceTo", "Apply"),
            ("min00Given", "applied", "pendingStage", "pendingStageBy", "obj10DisplayedOnce", "obj85DisplayedOnce", "obj86DisplayedOnce"),
        )
        exec(compile(code, "FO4SF_Min00Quest.psc", "exec"), m_ns)
        m_ns["GiveFromCodsworth"]()
        m_ns["GiveFromCodsworth"]()  # duplicate call stays muted
        m_ns["Apply"](20, "combat")
        m_ns["Apply"](30, "combat")
        self.assertEqual(m_obj_calls, [(10, True, False), (85, True, False), (86, True, False)])

    def test_mission_cs_writes_and_checks_mute_and_landing_handoff(self):
        cs = MISSION_CS.read_text(encoding="utf-8")
        self.assertIn("MuteDuplicateObjectiveToasts", cs)
        self.assertIn("LandingHandoff", cs)
        self.assertIn("LoadMissionStartConfig", cs)

    def test_landing_handoff_single_quest_vs_two_quests_and_shared_silent_strip(self):
        from tests.test_exit_arrival import translated_functions

        ng_psc = NEWGAME_PSC.read_text(encoding="utf-8")
        # Shared silent strip called by both ResetInventory and RunWarfareBranch
        reset_body = ng_psc[ng_psc.index("Function ResetInventory"):ng_psc.index("int Function StripStarterItemsSilently")]
        wf_body = ng_psc[ng_psc.index("Function RunWarfareBranch"):ng_psc.index("Event OnMenuOpenCloseEvent")]
        self.assertIn("StripStarterItemsSilently(player)", reset_body)
        self.assertIn("StripStarterItemsSilently(player)", wf_body)
        self.assertEqual(ng_psc.count("Function StripStarterItemsSilently("), 1)
        self.assertEqual(ng_psc.count("RemoveAllItems(None, false, false)"), 1)

        # Single-quest vs two-quests landing handoff at stage 40 -> 200 -> Codsworth01 start
        for mode, want_ng_comp, want_cw_disp, want_events in (("single_quest", False, True, 1), ("two_quests", True, True, 2)):
            with self.subTest(mode=mode):
                cw = _build_codsworth_harness(mute_duplicates=True, landing_handoff=mode)
                ng_logs = []
                ng_complete_calls = []
                ng_obj_completed = []
                ng_obj_displayed = []
                quest_map = {
                    (0x000800, "FO4SFMission.esm"): SimpleNamespace(IsRunning=lambda: False, StartNoWait=lambda: True),
                    (0x000814, "FO4SFMission.esm"): SimpleNamespace(IsRunning=lambda: False, StartNoWait=lambda: True),
                    (0x000816, "FO4SFMission.esm"): SimpleNamespace(IsRunning=lambda: False, StartNoWait=lambda: (cw.ns["StartQuestInstance"](), True)[1]),
                }
                ng_ns = {
                    "Trace": lambda m: ng_logs.append(str(m)),
                    "LandingHandoff": mode,
                    "h00SkipQuests": False,
                    "GameModeGlobal": SimpleNamespace(GetValue=lambda: 1.0),
                    "applied": 20,
                    "GetStage": lambda: 200,
                    "GetStageDone": lambda s: int(s) in (40, 200),
                    "CompleteQuest": lambda: ng_complete_calls.append("NewGame:OutOfTime"),
                    "ClearVaultSaveLock": lambda: None,
                    "ReleaseStoryLandingFade": lambda: None,
                    "SetObjectiveDisplayed": lambda o, d=True: ng_obj_displayed.append((int(o), bool(d))),
                    "SetObjectiveCompleted": lambda o: ng_obj_completed.append(int(o)),
                    "SetActive": lambda *_a: None,
                    "RunPodExitHook": lambda *_a: None,
                    "TriggerVaultPodRecoveryAutosave": lambda *_a: None,
                    "Game": SimpleNamespace(
                        GetPlayer=lambda: None,
                        GetFormFromFile=lambda fid, plg: quest_map.get((int(fid), str(plg))),
                    ),
                }
                ng_code = translated_functions(ng_psc, ("ApplyStage", "StartOptionalMissionQuest", "StartLandingQuests"), "applied")
                exec(compile(ng_code, "FO4SF_NewGameQuest.psc", "exec"), ng_ns)
                ng_ns["ApplyStage"](40, "Trigger")
                ng_ns["ApplyStage"](200, "Trigger")
                self.assertEqual(ng_obj_completed, [10])
                hud_out_of_time_events = len(ng_complete_calls) + len(cw.obj_calls)
                self.assertEqual(hud_out_of_time_events, want_events)
                if mode == "single_quest":
                    self.assertEqual(ng_complete_calls, [])
                    self.assertIn((10, False), ng_obj_displayed)
                    self.assertEqual(cw.obj_calls, [(10, True, False)])
                self.assertIn(
                    f"landing handoff mode={mode} newgame_completed={want_ng_comp} codsworth01_displayed={want_cw_disp}",
                    ng_logs,
                )

    def test_core_bundle_refuses_missing_ba2_and_verifies_pin_mismatch(self):
        import make_probe_swf  # noqa: E402
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            src_pb = tmp / "src_pb"
            (src_pb / "Data" / "Interface").mkdir(parents=True)
            (src_pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(make_probe_swf.movie_bytes())
            (src_pb / "SFSE" / "Plugins").mkdir(parents=True)
            (src_pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"MZ")
            (src_pb / "plan.json").write_text(json.dumps({"kind": "pipboy-stack-stage", "files": {}}), encoding="utf-8")

            # Missing Starfield - Interface.ba2 under mode=quest must refuse
            missing_sf_data = tmp / "EmptySfData"
            missing_sf_data.mkdir()
            with self.assertRaises(make_core_bundle.BundleRefused):
                make_core_bundle.refresh_pipboy_stage_for_bundle(
                    str(src_pb),
                    str(tmp / "out_refuse"),
                    str(tmp / "no_fo4"),
                    sf_data_dir=str(missing_sf_data),
                )

            # BA2 size/mtime/sha256 mismatch refuses verify_quest_translate_pin
            sample_lines = MakeQuestTranslateTests.SAMPLE_LINES
            raw = b"\xff\xfe" + "\r\n".join(sample_lines).encode("utf-16-le")
            ba2_bytes = ba2_fixture.general_archive({"interface\\translate_en.txt": raw}, compressed=True, version=2)
            sf_dir = tmp / "FakeSf"
            (sf_dir / "Data").mkdir(parents=True)
            ba2_path = sf_dir / "Data" / "Starfield - Interface.ba2"
            ba2_path.write_bytes(ba2_bytes)

            ok_out = tmp / "out_ok"
            make_core_bundle.refresh_pipboy_stage_for_bundle(
                str(src_pb),
                str(ok_out),
                str(tmp / "no_fo4"),
                sf_data_dir=str(sf_dir / "Data"),
            )
            pb_plan = json.loads((ok_out / "plan.json").read_text(encoding="utf-8"))
            bplan = {
                "quest_translate": pb_plan["quest_translate"],
                "sfse_sidecar": {"Interface/Translate_en.txt": pb_plan["quest_translate"]["out_sha256"]},
            }
            self.assertIsNone(make_core_bundle.verify_quest_translate_pin(bplan, starfield_dir=str(sf_dir)))
            ba2_path.write_bytes(ba2_bytes + b"TAMPER")
            prob = make_core_bundle.verify_quest_translate_pin(bplan, starfield_dir=str(sf_dir))
            self.assertIsNotNone(prob)


if __name__ == "__main__":
    unittest.main()
