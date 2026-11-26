"""Round 15 Wave A Item 2:
1. Duplicate NEW MISSION / MISSION UPDATED toast suppression in FO4SF_Codsworth01Quest.psc
   behind `bool Property MuteDuplicateObjectiveToasts = True Auto Const`.
2. Stage-time `Data/Interface/Translate_en.txt` generator (`scripts/ui/make_quest_translate.py`)
   replacing Starfield's 6 `$Mission*` HUD toast/status lines behind `--mode quest|mission`
   and `--label QUEST` (preserving Out of Time / all other lines, UTF-16LE BOM, and CRLF).
3. Header-only SFSE helper `sfse/FO4SFPipboyMenu/src/hud_quest_label.h` parsing
   `[FO4SFPipboyMenu]` `ReplaceMissionLabel` and `QuestHudLabel`.
"""
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
for _p in (str(TESTS_DIR), str(REPO / "src"), str(REPO / "scripts" / "mission"), str(REPO / "scripts" / "ui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ba2_fixture  # noqa: E402
from fo4sf import ba2  # noqa: E402
import make_mission  # noqa: E402
import make_quest_translate  # noqa: E402
import test_mission  # noqa: E402

CODS_PSC = REPO / "scripts" / "mission" / "FO4SF_Codsworth01Quest.psc"
HUD_HEADER = REPO / "sfse" / "FO4SFPipboyMenu" / "src" / "hud_quest_label.h"
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


def _build_codsworth_harness(*, mute_duplicates=True, is_objective_displayed=False):
    c_psc = CODS_PSC.read_text(encoding="utf-8")
    logs = []
    obj_calls = []
    top_calls = []
    active_calls = []
    timers = []
    stages = set()
    cur_stage = [0]

    cods = _MockActorRef("Codsworth(09000811)", (-2346.709, -1406.163, 111.734))
    player = _MockActorRef("Player", (-2345.0, -1405.0, 111.8))
    cods_alias = SimpleNamespace(GetActorRef=lambda: None, ForceRefTo=lambda *_a: None)

    def set_stage(n):
        stages.add(int(n))
        if int(n) > cur_stage[0]:
            cur_stage[0] = int(n)

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
        "IsObjectiveDisplayed": lambda obj: bool(is_objective_displayed),
        "SetObjectiveDisplayed": lambda obj, disp=True, force=False: obj_calls.append((int(obj), bool(disp), bool(force))),
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
        h = _build_codsworth_harness(mute_duplicates=True, is_objective_displayed=False)
        h.ns["StartQuestInstance"]()

        # Exactly one non-forced display, SetActive(True) once, zero SetObjectiveDisplayedAtTop spam
        self.assertEqual(h.obj_calls, [(10, True, False)])
        self.assertEqual(h.active_calls, [True])
        self.assertEqual(h.top_calls, [])
        self.assertTrue(h.ns["objective10DisplayedOnce"])
        self.assertIn("codsworth01 objective10_toast shown=true muted_duplicates=True force=false", h.logs)

        # EnsureTalkProxy spawns proxy without re-displaying Objective 10
        h.ns["EnsureTalkProxy"](h.player)
        self.assertIsNotNone(h.ns["talkProxy"])
        self.assertEqual(h.obj_calls, [(10, True, False)])
        self.assertEqual(h.active_calls, [True])

        # Repeated ShowCodsworthObjective() and 10 ticks of OnTimer(1) even when IsObjectiveDisplayed(10)==False
        # never re-display Objective 10 and emit skip trace at most once (no per-second log spam)
        h.ns["ShowCodsworthObjective"]()
        for _ in range(10):
            h.ns["OnTimer"](1)
        self.assertEqual(h.obj_calls, [(10, True, False)])
        self.assertEqual(h.top_calls, [])
        skip_logs = [ln for ln in h.logs if "codsworth01 objective10_toast skipped=true" in ln]
        self.assertEqual(len(skip_logs), 1)

        # ClearObjectiveOnConcordStart clears Objective 10 cleanly
        h.ns["ClearObjectiveOnConcordStart"]()
        self.assertEqual(h.obj_calls[-1], (10, False, False))
        self.assertEqual(h.active_calls[-1], False)

    def test_unmuted_flag_preserves_forced_display_and_retry(self):
        h = _build_codsworth_harness(mute_duplicates=False, is_objective_displayed=False)
        h.ns["StartQuestInstance"]()
        self.assertEqual(h.obj_calls, [(10, True, True)])
        self.assertEqual(h.top_calls, [10])
        self.assertIn("codsworth01 objective10_toast shown=true muted_duplicates=False force=true", h.logs)

        # When IsObjectiveDisplayed(10) is still False, OnTimer(1) retries normal forced display
        h.ns["OnTimer"](1)
        self.assertEqual(h.obj_calls, [(10, True, True), (10, True, True)])
        self.assertEqual(h.top_calls, [10, 10])


class MakeQuestTranslateTests(unittest.TestCase):
    SAMPLE_LINES = [
        "$ACCEPT\tACCEPT",
        "$MISSION\tMISSION",
        "$MISSION COMPLETE\tMISSION COMPLETE",
        "$Mission Data\tMISSION DATA",
        "$MISSION FAILED\tMISSION FAILED",
        "$Mission Info\tMISSION INFO",
        "$Mission name\tMISSION NAME",
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
        "$YES\tYES",
    ]

    def _make_sample_ba2(self, tmp_dir: Path, *, encoding="utf-16-le", bom=b"\xff\xfe", eol="\r\n", trailing_eol=False) -> tuple[Path, bytes]:
        text = eol.join(self.SAMPLE_LINES) + (eol if trailing_eol else "")
        raw = bom + text.encode(encoding)
        ba2_bytes = ba2_fixture.general_archive({"interface\\translate_en.txt": raw}, compressed=True, version=2)
        data_dir = tmp_dir / "Starfield" / "Data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "Starfield - Interface.ba2").write_bytes(ba2_bytes)
        return data_dir, raw

    def test_synthetic_utf16le_bom_crlf_rewrites_exact_6_lines_only(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            data_dir, vanilla_raw = self._make_sample_ba2(tmp)
            stage_root = tmp / "stage"

            rc = make_quest_translate.main(["--starfield-data", str(data_dir), "--out", str(stage_root)])
            self.assertEqual(rc, 0)

            out_file = stage_root / "Data" / "Interface" / "Translate_en.txt"
            self.assertTrue(out_file.is_file())
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

            self.assertEqual(diffs, {
                "$MISSION FAILED": "QUEST FAILED",
                "$MISSION STATUS": "QUEST STATUS",
                "$MISSION UPDATED": "QUEST UPDATED",
                "$MissionFailed": "QUEST FAILED",
                "$MissionNew": "NEW QUEST",
                "$MissionUpdate": "QUEST UPDATED",
            })

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
    def test_real_starfield_interface_ba2_exact_line_count_and_6_changes(self):
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

            self.assertEqual(len(changed), 6, f"expected exactly 6 changed lines, got {changed}")
            changed_map = {orig.split("\t", 1)[0]: new.split("\t", 1)[1] for _i, orig, new in changed}
            self.assertEqual(changed_map, {
                "$MISSION FAILED": "QUEST FAILED",
                "$MISSION STATUS": "QUEST STATUS",
                "$MISSION UPDATED": "QUEST UPDATED",
                "$MissionFailed": "QUEST FAILED",
                "$MissionNew": "NEW QUEST",
                "$MissionUpdate": "QUEST UPDATED",
            })

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
    def test_header_contract_settings_rewrite_and_startup_log(self):
        src = HUD_HEADER.read_text(encoding="utf-8")
        self.assertIn("namespace fo4sf::hud", src)
        self.assertIn("ReplaceMissionLabel", src)
        self.assertIn("QuestHudLabel", src)
        self.assertIn("RewriteMissionHudLabel", src)
        self.assertIn("ParseQuestLabelIniText", src)
        self.assertIn("LoadQuestLabelConfig", src)
        self.assertIn("FormatStartupLog", src)
        self.assertIn("step=hud_quest_label mode={} label={} active={}", src)
        for token in ("$MissionNew", "$MissionUpdate", "$MISSION UPDATED", "$MISSION STATUS", "$MissionFailed", "$MISSION FAILED"):
            self.assertIn(token, src)
        self.assertNotIn("Out of Time", src.split("RewriteMissionHudLabel", 1)[1])


if __name__ == "__main__":
    unittest.main()
