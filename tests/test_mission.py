"""The cut-down "When Freedom Calls" mission: the contract between dotnet/Mission (the plugin), FO4SF_Min00Quest.psc (the
quest script) and make_mission.py (staging and the log reader). Synthetic only; the C# writer's own self-test runs when
a dotnet SDK is on PATH (dotnet/Mission selftest: synthetic masters, write + check)."""
import os
import shutil
import subprocess
import sys
import json
import math
import re
import tempfile
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "mission"))
import make_mission  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "mission", "FO4SF_Min00Quest.psc")
CS = os.path.join(ROOT, "dotnet", "Mission", "Program.cs")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def function_body(psc, name):
    """A script function's text, from its "Function <name>(" to its EndFunction."""
    i = psc.index(f"Function {name}(")
    return psc[i:psc.index("EndFunction", i)]


class ContractTests(unittest.TestCase):
    def test_script_properties_are_the_ones_the_plugin_fills(self):
        self.assertEqual(tuple(make_mission.mandatory_properties(read(PSC))), make_mission.PROPERTIES)
        cs = read(CS)
        for name in make_mission.PROPERTIES:
            self.assertIn(f'"{name}"', cs, f"Program.cs never writes the property {name}")

    def test_stages_match_between_plugin_and_script(self):
        cs = read(CS)
        stages = ", ".join(str(s) for s in make_mission.STAGES)
        self.assertIn("Stages = { " + stages + " }", cs)
        psc = read(PSC)
        for s in make_mission.STAGES:
            self.assertRegex(psc, rf"auiStageID == {s}\b", f"the script never handles stage {s}")
        for o in (10, 85, 86):                                   # Min00's objective indices, written by Program.cs
            self.assertIn(f"SetObjectiveDisplayed({o})", psc)
            self.assertIn(f"({o}, \"", cs)

    def test_make_mission_compiles_without_warnings(self):
        """PC, Python 3.14 (FAL-128): make_mission.py's docstring printed a SyntaxWarning for "\\S" (Data\\Scripts)."""
        import warnings
        src = read(os.path.join(ROOT, "scripts", "mission", "make_mission.py"))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            compile(src, "make_mission.py", "exec")
        self.assertIn(r"Data\Scripts\FO4SF_Min00Quest.pex", make_mission.__doc__)     # the help text is unchanged

    def test_mandatory_properties_parser(self):
        text = ("Actor Property A Auto Const Mandatory\nActor[] Property B Auto Const Mandatory\n"
                "int Property C = 1 Auto Const\n  MiscObject Property D Auto Const Mandatory\n")
        self.assertEqual(make_mission.mandatory_properties(text), ["A", "B", "D"])


class FollowCommandTests(unittest.TestCase):
    """FAL-866: the first slice is Preston follows. The door hold stays until the test-only command, and that command
    does not use the host follower quest."""

    def test_place_returns_before_the_hold_once_follow_is_armed(self):
        body = function_body(read(PSC), "PlacePreston")
        self.assertLess(body.index("if prestonFollow"), body.index("PlaceAt("))
        self.assertLess(body.index("if prestonFollow"), body.index("HoldDue("))
        armed = function_body(read(PSC), "BeginFollow")
        self.assertIn("prestonFollow = True", armed)
        self.assertIn("prestonHeld = False", armed)

    def test_the_command_is_test_only_and_not_the_host_follower_quest(self):
        com = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_COMPreston.psc"))
        self.assertIn('cgf "FO4SF_COMPreston.FollowTest"', com)
        self.assertIn("follow preston test-only", com)
        self.assertIn("SetRestrained(False)", com)
        self.assertIn("SetLinkedRef(player)", com)
        self.assertIn("ForceRefTo(preston)", com)
        self.assertIn("EvaluatePackage()", com)
        self.assertIn("Utility.Wait(2.0)", com)
        self.assertIn("GetCurrentPackage()", com)
        self.assertIn("follow preston package=", com)
        self.assertIn("BeginFollow()", com)
        code = re.sub(r"\{[^}]*\}", "", com)
        code = "\n".join(line.split(";")[0] for line in code.splitlines())
        cs = read(CS)
        cs_code = re.sub(r"/\*.*?\*/", "", re.sub(r"//.*?$", "", cs, flags=re.M), flags=re.S)
        for banned in ("0000D773", "ActiveFollowers", "Constellation", "SetPlayerTeammate", "CompanionAffinity"):
            self.assertNotIn(banned, code)
            self.assertNotIn(banned, cs_code)
        self.assertIn('ComQuestEdid = "FO4SF_COMPreston"', cs)
        self.assertIn("FollowPackageId = 0x0301C5", cs)
        self.assertIn('FollowPackageEdid = "DefaultMaster_FollowPackage"', cs)
        self.assertIn('Name = ComAliasName', cs)
        self.assertIn("AQuestAlias.Flag.AllowReserved", cs)

    def test_a_hold_after_the_command_is_counted(self):
        lines = [
            "[11/15/2026 - 01:00:00AM] FO4SF_MISSION rt=10.0 hold preston by=keeper off=0.2 ok=True",
            "[11/15/2026 - 01:00:01AM] FO4SF_MISSION rt=11.0 follow preston armed by=mission",
            "[11/15/2026 - 01:00:01AM] FO4SF_MISSION rt=11.0 follow preston test-only alias=Preston filled=1 linked=player released=True quest=2069",
            "[11/15/2026 - 01:00:06AM] FO4SF_MISSION rt=16.0 hold preston by=keeper off=1.0 ok=True",
        ]
        s = make_mission.summarize(lines)
        self.assertTrue(s["follow"].startswith("follow preston test-only"))
        self.assertEqual(s["holds_after_follow"], 1)
        self.assertIsNone(s["follow_package"])
        self.assertIsNone(make_mission.summarize(lines[:1])["follow"])
        self.assertEqual(make_mission.summarize(lines[:1])["holds_after_follow"], 0)
        with_package = lines[:3] + [
            "[11/15/2026 - 01:00:03AM] FO4SF_MISSION rt=13.0 follow preston package=197061",
            lines[3],
        ]
        sp = make_mission.summarize(with_package)
        self.assertTrue(sp["follow"].startswith("follow preston test-only"))
        self.assertEqual(sp["follow_package"], "follow preston package=197061")
        self.assertEqual(sp["holds_after_follow"], 1)


class LogTests(unittest.TestCase):
    LINES = [
        "[10/18/2026 - 02:00:00PM] FO4SF_MISSION rt=10.5 init raiders=3",
        "[10/18/2026 - 02:00:00PM] FO4SF_MISSION rt=10.6 stage 10",
        "[10/18/2026 - 02:01:00PM] FO4SF_MISSION rt=70.1 startcombat raider 0 d=55.2",
        "[10/18/2026 - 02:01:00PM] FO4SF_MISSION rt=70.1 stage 20",
        "[10/18/2026 - 02:01:01PM] FO4SF rt=70.2 pos=1 2 3 ang=0 cell=none world=none loaded=True n=4",
        "[10/18/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 status stage=20 dead=3/3 nearest_raider=-1.0 preston=40.0 pos=1 2 3",
        "[10/18/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 stage 30",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 preston activated at stage 30",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 40",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 reward credits=100",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 200",
    ]

    def test_full_run(self):
        s = make_mission.summarize(self.LINES)
        self.assertEqual(s["stages"], [10, 20, 30, 40, 200])
        self.assertEqual(s["reward"], 100)
        self.assertEqual(s["startcombat"], 1)
        self.assertEqual(s["activated"], 1)
        self.assertTrue(s["status"].startswith("status stage=20 dead=3/3"))

    def test_partial_run_is_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "fo4sf_mission.0.log")
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(self.LINES[:4]) + "\n")
            self.assertEqual(make_mission.main(["log", "--file", p]), 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(self.LINES) + "\n")
            self.assertEqual(make_mission.main(["log", "--file", p]), 0)

    def test_other_log_lines_ignored(self):
        self.assertEqual(make_mission.summarize(["FO4SF rt=1 pos=1 2 3 n=1", "noise"])["stages"], [])

    def test_found_preston_is_reported_once(self):
        s = make_mission.summarize(self.LINES)
        self.assertIsNone(s["found"])
        lines = ["[10/28/2026 - 06:12:45PM] FO4SF_MISSION rt=200.0 preston activated at stage 10",
                 "[10/28/2026 - 06:12:45PM] FO4SF_MISSION rt=200.0 found preston activated",
                 "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 found preston near d=2.5",
                 "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 startcombat raider 0 d=91.3",
                 "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 stage 20"]
        s = make_mission.summarize(lines)
        self.assertEqual((s["found"], s["activated"], s["startcombat"], s["stages"]), ("activated", 1, 1, [20]))

    def test_keeper_reports_preston_after_the_mission(self):
        """FAL-64: after stage 200 the keeper's lines are the only evidence of where Preston is."""
        s = make_mission.summarize(self.LINES)
        self.assertEqual((s["preston_moves"], s["keeper"]), (0, None))
        after = self.LINES + [
            "[11/07/2026 - 09:40:00PM] FO4SF_MISSION rt=300.0 keeper load preston d=155.3 off=160.2 state=none moves=0 "
            "at -1960.0 -1850.0 89.1 disabled=False dead=False fails=0 player=-2011.1 -1697.2 90.0 interior=False",
            "[11/07/2026 - 09:40:05PM] FO4SF_MISSION rt=305.0 moved preston to -2011.1 -1697.5 89.1 target -2011.1 "
            "-1697.5 89.1 before=155.3 off=160.2 d=0.3 failed=False by=keeper",
            "[11/07/2026 - 09:40:05PM] FO4SF_MISSION rt=305.0 moved codsworth to 1 2 3 target 1 2 3 before=1 d=1 failed=False",
            "[11/07/2026 - 09:41:00PM] FO4SF_MISSION rt=360.0 keeper status preston d=3.2 off=0.4 state=at spot moves=1 "
            "at -2011.1 -1697.5 89.1 disabled=False dead=False fails=0 player=-2012.0 -1700.0 90.0 interior=False",
        ]
        s = make_mission.summarize(after)
        self.assertEqual(s["preston_moves"], 1)
        self.assertTrue(s["keeper"].startswith("keeper status preston d=3.2"))
        self.assertEqual(s["preston_off"], 0.4)                         # FAL-128: the PC check's PASS reads this
        self.assertEqual(s["stages"], [10, 20, 30, 40, 200])
        # a 2590549e keeper line has no off=, and an unreadable one is None, never an error
        self.assertIsNone(make_mission.summarize([after[-1].replace(" off=0.4", "")])["preston_off"])
        self.assertIsNone(make_mission.summarize([after[-1].replace("off=0.4", "off=nan?")])["preston_off"])

    def test_names_are_read_in_any_case(self):
        """The 31 Oct logs (FAL-128 pc-evidence-20261110) print "moved Codsworth" and "moved Preston" where the script's
        literals were "codsworth" and "preston": the game prints a name as the property it matches. Those moves count."""
        lines = [
            "[15:04:21] FO4SF_MISSION rt=130.3 moved Codsworth to -2346.7 -1406.1 111.7 target -2346.7 -1406.1 111.7 "
            "before=INF d=122.0 failed=false",
            "[15:04:21] FO4SF_MISSION rt=131.1 moved Preston to -2011.5 -1697.2 89.0 target -2011.1 -1697.5 89.0 "
            "before=INF d=544.4 failed=false",
            "[15:04:22] FO4SF_MISSION rt=131.6 moved raider 0 to -2029.7 -1696.5 88.3 target -2029.1 -1698.2 88.3 "
            "before=INF d=529.7 failed=false",
        ]
        s = make_mission.summarize(lines)
        self.assertEqual((s["preston_moves"], s["codsworth_moves"]), (1, 1))

    def test_keeper_reports_codsworth(self):
        """FAL-163: the keeper's lines for Codsworth (load, status) are read like Preston's, apart from his."""
        lines = [
            "[11/10/2026 - 09:40:00PM] FO4SF_MISSION rt=30.0 keeper load Preston d=3.0 off=0.5 state=at spot moves=1 "
            "at -2011.1 -1697.5 89.1 disabled=False dead=False fails=0 player=-2012.0 -1700.0 90.0 interior=False",
            "[11/10/2026 - 09:40:00PM] FO4SF_MISSION rt=30.0 keeper load Codsworth d=3102.0 off=2955.1 state=none "
            "moves=0 at -1146.7 1293.8 111.7 disabled=False dead=False fails=0 player=-2012.0 -1700.0 90.0 interior=False",
            "[11/10/2026 - 09:45:05PM] FO4SF_MISSION rt=335.0 moved Codsworth to -2346.7 -1406.2 111.7 target -2346.709 "
            "-1406.163 111.734 before=3001.2 off=2955.1 d=120.3 failed=False by=keeper",
            "[11/10/2026 - 09:46:00PM] FO4SF_MISSION rt=390.0 keeper status Codsworth d=118.0 off=1.2 state=placed "
            "moves=1 at -2346.0 -1406.0 111.7 disabled=False dead=False fails=0 player=-2460.0 -1400.0 127.0 "
            "interior=False",
        ]
        s = make_mission.summarize(lines)
        self.assertEqual((s["codsworth_moves"], s["codsworth_off"], s["preston_moves"], s["preston_off"]),
                         (1, 1.2, 0, 0.5))
        self.assertTrue(s["codsworth_keeper"].startswith("keeper status Codsworth d=118.0"))
        self.assertTrue(s["keeper"].startswith("keeper load Preston"))
        self.assertIsNone(make_mission.summarize(lines[:1])["codsworth_keeper"])


class NextStageTests(unittest.TestCase):
    """make_mission.next_stage mirrors the script's NextStage (Codex review 5563368986: progress must not depend on
    this script having issued StartCombat)."""
    def test_fight_started_by_anyone_advances(self):
        self.assertEqual(make_mission.next_stage(10, 0, 5, True, False), 20)      # already fighting at start/reload
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False), 10)     # nothing yet

    def test_dead_before_next_check(self):
        self.assertEqual(make_mission.next_stage(10, 2, 5, False, False), 20)
        self.assertEqual(make_mission.next_stage(10, 5, 5, False, False), 30)     # all died between two checks
        self.assertEqual(make_mission.next_stage(20, 5, 5, False, False), 30)

    def test_preston_only_after_the_raiders(self):
        self.assertEqual(make_mission.next_stage(20, 4, 5, True, True), 20)
        self.assertEqual(make_mission.next_stage(30, 5, 5, False, True), 40)
        self.assertEqual(make_mission.next_stage(30, 5, 5, False, False), 30)

    def test_never_goes_back_and_no_raiders_never_counts_as_cleared(self):
        self.assertEqual(make_mission.next_stage(40, 0, 5, False, False), 40)
        self.assertEqual(make_mission.next_stage(10, 0, 0, False, False), 10)

    def test_finding_preston_starts_the_fight(self):
        # in game 28 Oct (new game run 3): Preston activated five times at stage 10, every raider 91 to 129 m away and
        # none fighting; the stage stayed 10. Found, it is 20 even before a raider's 3D is loaded.
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False), 10)
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False, found=True), 20)
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, True, found=True), 20)    # not past the fight
        self.assertEqual(make_mission.next_stage(20, 3, 5, True, True, found=True), 20)
        self.assertEqual(make_mission.next_stage(10, 5, 5, False, False, found=True), 30)   # all dead is still 30
        self.assertEqual(make_mission.next_stage(10, 0, 0, False, False, found=True), 20)   # never "cleared"

    def test_script_carries_the_same_rule(self):
        psc = read(PSC)
        for cond in ("s < 20 && (fighting || dead > 0 || found)", "s < 30 && total > 0 && dead == total",
                     "s == 30 && atPreston"):
            self.assertIn(cond, psc)
        self.assertNotIn("GetCombatState() == 0\n", psc)
        self.assertIn("int Function NextStage(int stage, int dead, int total, bool fighting, bool atPreston, bool found)",
                      psc)
        self.assertIn("bool readyTalk = TalkCompleteReady(stage, dp)", psc)
        self.assertIn("NextStage(stage, dead, Raiders.Length, fighting, readyTalk, prestonFound)", psc)


class FindPrestonTests(unittest.TestCase):
    """In game 28 Oct (new game run 3, the owner: "the freedoms calls activation didnt work"): OnActivate ran ("preston
    activated at stage 10" five times) but only stage 30 acted on it, and the fight waited for a raider within
    EngageRadius while the nearest stayed 91 to 129 m away. Reaching Preston (activation or FindRadius) now starts the
    fight, and once it is on every loaded raider is put into combat."""

    def setUp(self):
        self.psc = read(PSC)

    def block(self, start, end):
        i = self.psc.index(start)
        return self.psc[i:self.psc.index(end, i)]

    def test_activation_before_the_fight_finds_preston(self):
        act = self.block("Event ObjectReference.OnActivate(", "EndEvent")
        self.assertRegex(act, r"if stage < 20\s+FoundPreston\(\"activated\"\)")
        self.assertIn("elseif stage == 30", act)
        self.assertIn("PrestonTalkScene.Start()", act)
        self.assertIn('AdvanceTo(40, "fallback")', act)

    def test_standing_near_preston_before_the_fight_finds_him(self):
        tick = self.block("Event OnTimer(", "EndEvent")
        self.assertRegex(tick, r"if stage < 20 && dp < FindRadius\s+FoundPreston\(")
        self.assertLess(tick.index("FoundPreston("), tick.index("while i < Raiders.Length"))   # before the raiders' loop
        num = lambda name: float(re.search(r"float Property %s = (-?[\d.]+) Auto Const" % name, self.psc).group(1))
        self.assertEqual(num("FindRadius"), 20.0)                                          # the documented 20 m
        self.assertGreater(num("FindRadius"), num("TalkRadius"))
        self.assertNotIn("FindRadius", make_mission.mandatory_properties(self.psc))         # the plugin never fills it

    def test_once_the_fight_is_on_every_loaded_raider_is_put_into_combat(self):
        tick = self.block("Event OnTimer(", "EndEvent")
        self.assertIn("bool everyone = prestonFound || stage >= 20", tick)
        self.assertIn("elseif stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()", tick)
        # the raider itself is put into combat, with the player as its target
        self.assertRegex(tick, r"r\.Is3DLoaded\(\)\s+(;[^\n]*\s+)*r\.StartCombat\(player\)")
        self.assertEqual(re.findall(r"\b(\w+)\.StartCombat\((\w+)\)", self.psc), [("r", "player")])

    def test_dead_raiders_are_skipped(self):
        """A dead or WFC-01 auto-cleared raider is counted and never put into combat."""
        tick = self.block("Event OnTimer(", "EndEvent")
        self.assertRegex(tick, r"Actor r = Raiders\[i\]\s+if r\.IsDead\(\) \|\| raiderCleared\[i\]\s+dead \+= 1\s+else\s")
        loop = tick[tick.index("Actor r = Raiders[i]"):]
        self.assertLess(loop.index("if r.IsDead() || raiderCleared[i]"), loop.index("r.StartCombat(player)"))

    def test_found_is_set_and_logged_once(self):
        found = self.block("Function FoundPreston(string how)", "EndFunction")
        self.assertRegex(found, r"if !prestonFound && !Preston\.IsDead\(\)\s+prestonFound = True\s+"
                                r"Trace\(\"found preston \" \+ how\)")
        self.assertRegex(self.psc, r"(?m)^bool prestonFound = False$")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class RelocateContractTests(unittest.TestCase):
    """In game 18 Oct: the core's persistent cell keeps its references at their local position in the base world, so the
    script moves its actors by the core's merge offset; that offset must be the one the door writer uses."""

    def test_script_merge_offset_is_the_measured_one(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
        import vmad_patch
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        got = {k: float(v) for k, v in re.findall(r"float Property MergeOffset([XY]) = (-?[\d.]+) Auto Const", psc)}
        self.assertEqual((got["X"], got["Y"]), vmad_patch.MERGE_MEASURED[:2])

    def test_no_exponent_float_literals(self):
        """Papyrus has no 1.0e30 literals (PC compile of 6ee0896: "required (...)+ loop did not match anything at
        input 'e30'"); comments and doc strings are exempt."""
        with open(PSC, encoding="utf-8") as f:
            code = re.sub(r"\{[^}]*\}", "", f.read())
        code = "\n".join(line.split(";")[0] for line in code.splitlines())
        self.assertIsNone(re.search(r"\d[eE][-+]?\d", code))

    def test_no_keyword_names(self):
        """Papyrus keywords (case-insensitive) cannot name a parameter or a variable: a parameter "state" (TraceSpot,
        FAL-163) would not compile, and this host has no Papyrus compiler to catch it."""
        keywords = {"as", "auto", "autoreadonly", "betaonly", "bool", "collapsed", "conditional", "const", "customevent",
                    "debugonly", "else", "elseif", "endevent", "endfunction", "endguard", "endif", "endproperty",
                    "endstate", "endstruct", "endwhile", "event", "extends", "false", "float", "function", "global",
                    "guard", "hidden", "if", "import", "int", "is", "length", "mandatory", "native", "new", "none",
                    "parent", "property", "return", "scriptname", "self", "state", "string", "struct", "true",
                    "tryguard", "var", "while"}
        all_psc = "\n".join(read(os.path.join(ROOT, "scripts", "mission", s + ".psc")) for s in make_mission.ALL_SCRIPTS)
        code = re.sub(r"\{[^}]*\}", "", all_psc)
        code = re.sub(r'"[^"]*"', '""', "\n".join(line.split(";")[0] for line in code.splitlines()))
        names = [n for n in re.findall(r"\b(?:bool|int|float|string|Actor|WorldSpace|MiscObject|Scene|ObjectReference)(?:\[\])?[ \t]+(\w+)",
                                       code, re.I) if n not in ("Property", "Function")]
        self.assertIn("spotState", names)
        self.assertEqual([n for n in names if n.lower() in keywords], [])

    def test_relocate_decides_by_position(self):
        """In game 18 Oct 14:40 the unmoved actors read a finite distance of about 2,955 (the offset's length), and the
        "finite means reachable" test skipped the move: the gap must sit between the radius and that length."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        num = lambda name: float(re.search(r"float Property %s = (-?[\d.]+) Auto Const" % name, psc).group(1))
        offset = (num("MergeOffsetX") ** 2 + num("MergeOffsetY") ** 2) ** 0.5
        radius, gap = num("RelocateRadius"), num("RelocateGap")
        self.assertLess(radius, gap)
        self.assertLess(gap, offset - radius)
        self.assertNotIn("1000000000", psc)

    def test_relocate_is_per_actor_and_retries(self):
        """Codex 5564899342: no global "relocated" flag (a no-op or partial move must be retried, a moved actor never
        offset twice), and no move from an interior."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertNotIn("relocated = true", psc)
        self.assertIn("if player.IsInInterior()", psc)
        self.assertRegex(psc, r"if relocateFails < 10\s+Relocate\(player\)")

    def test_relocate_rule_model(self):
        """The PSC's per-actor rule on plain numbers: unmoved (same world at the local spot, or another world), moved,
        a no-op MoveTo, and a partial pass followed by a retry."""
        far = float("inf")
        ox, oy, radius, gap = -1200.0, -2700.0, 800.0, 1500.0

        def step(player, actors, moveto_works):
            for a in actors:
                dist = far if a["world"] != "merged" else math.dist(player, a["pos"])
                tx, ty = a["pos"][0] + ox, a["pos"][1] + oy
                if dist < gap or math.dist(player, (tx, ty)) > radius:
                    continue
                if moveto_works(a):
                    a["pos"], a["world"] = (tx, ty), "merged"

        street = (-2011.1, -1697.2)
        for world in ("merged", "base"):
            actors = [{"pos": (-811.1, 1002.5), "world": world}, {"pos": (-790.0, 1010.0), "world": world}]
            step(street, actors, lambda a: False)                       # no-op MoveTo: still pending
            self.assertTrue(all(a["pos"] == (-811.1, 1002.5) or a["pos"] == (-790.0, 1010.0) for a in actors))
            step(street, actors, lambda a: a is actors[0])              # partial: only the first arrives
            self.assertEqual(actors[0]["pos"], (-2011.1, -1697.5))
            self.assertEqual(actors[1]["pos"], (-790.0, 1010.0))
            step(street, actors, lambda a: True)                        # retry: the second arrives, the first stays
            self.assertEqual(actors[0]["pos"], (-2011.1, -1697.5))
            self.assertEqual(actors[1]["pos"], (-1990.0, -1690.0))
            step(street, actors, lambda a: True)                        # nothing moves twice
            self.assertEqual(actors[1]["pos"], (-1990.0, -1690.0))
        away = [{"pos": (-811.1, 1002.5), "world": "merged"}]
        step((-1276.0, -3032.0), away, lambda a: True)                  # Red Rocket: not at the museum yet
        self.assertEqual(away[0]["pos"], (-811.1, 1002.5))

    def test_codsworth_is_kept_after_the_mission(self):
        """Review 20 Oct: Codsworth has his own timer (2) and failure budget, which stage 200 does not cancel, and the
        mission's Relocate no longer moves him."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        keep = psc[psc.index("Function KeepCodsworth()"):psc.index("bool Function MoveOver")]
        self.assertIn("codsworthFails += 1", keep)
        self.assertRegex(keep, r"if \(Codsworth != None && \(codsworthFails < 10 \|\| codsworthHolds > 0\)\) \|\| "
                               r"\(KeeperOnly && \(prestonFails < 10 \|\| prestonHolds > 0\)\)"
                               r"\s+StartTimer\(CodsworthCheck, 2\)")
        self.assertNotIn("GetStage", keep)
        relocate = psc[psc.index("Function Relocate("):psc.index("Function KeepCodsworth()")]
        self.assertNotIn("MoveOver(Codsworth", relocate)
        self.assertIn("CancelTimer(1)", psc)
        self.assertNotIn("CancelTimer(2)", psc)
        self.assertRegex(psc, r"if aiTimerID == 2\s+KeepCodsworth\(\)")
        self.assertEqual(psc.count("KeepCodsworthStart()"), 3)          # defined, from OnQuestInit, from timer 1

    def test_the_keeper_restarts_codsworth_on_an_existing_save(self):
        """His keeper (KeeperOnly) starts via StartQuestInstance (OnQuestStarted / OnQuestInit), enables Codsworth, and
        restarts his timer with a fresh budget at start and on every save load; it never runs the mission."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertRegex(psc, r"(?m)^bool Property KeeperOnly = False Auto Const$")
        self.assertNotIn("KeeperOnly", make_mission.mandatory_properties(psc))
        init = function_body(psc, "StartQuestInstance")
        keeper_start = init.index("if KeeperOnly")
        keeper = init[keeper_start:init.index("endif", keeper_start)]
        self.assertIn("if KeeperOnly", keeper)
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', keeper)
        self.assertIn("KeepCodsworthLoad()", keeper)
        self.assertIn("return", keeper)
        self.assertLess(init.index("return", keeper_start), init.index('Trace("init raiders="'))
        load = psc[psc.index("Function KeepCodsworthLoad()"):psc.index("EndFunction", psc.index("Function KeepCodsworthLoad()"))]
        self.assertRegex(load, r"if Codsworth.IsDisabled\(\)\s+Codsworth.Enable\(\)")
        self.assertIn("codsworthFails = 0", load)
        self.assertIn("StartTimer(CodsworthCheck, 2)", load)
        self.assertRegex(psc, r"Event Actor.OnPlayerLoadGame\(Actor akSender\)\s+Debug\.OpenUserLog\(LogName\)\s+if KeeperOnly\s+KeepCodsworthLoad\(\)")
        keep = psc[psc.index("Function KeepCodsworth()"):psc.index("bool Function MoveOver")]
        self.assertRegex(keep, r"if Codsworth != None && codsworthFails < 10\s+if PlaceCodsworth\(player\)")

    def test_a_missing_codsworth_does_not_stop_preston(self):
        """FAL-128 (2590549e review): KeepCodsworthLoad and KeepCodsworth returned early when Codsworth was None, which
        also silently stopped Preston's keeping. Only Codsworth's own steps need him now."""
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        for name in ("KeepCodsworthLoad", "KeepCodsworth"):
            self.assertNotIn("Codsworth == None", body(name), name)
            self.assertNotRegex(body(name), r"(?m)^\s+return\s*$", name)
        load = body("KeepCodsworthLoad")
        guarded = load[load.index("if Codsworth != None"):load.index("prestonFails = 0")]
        for step in ("Codsworth.Enable()", "codsworthFails = 0", "codsworthKept = True"):
            self.assertIn(step, guarded)
        rest = load[load.index("prestonFails = 0"):]
        for step in ('TracePreston("keeper load")', "StartTimer(CodsworthCheck, 2)"):
            self.assertIn(step, rest)                                   # outside Codsworth's guard

    def test_the_keeper_keeps_preston_after_the_mission(self):
        """FAL-64, the owner's report of 7 Nov: "no preston garvy after misson finshes". Stage 200 cancels timer 1, the
        mission's Relocate with it, while Preston snaps back to his unmerged spot (in game 19 Oct: moved 5 times in one
        session). The keeper (timer 2, not cancelled by stage 200, restarted on every load) puts him back by the same
        rule and to the same spot as the mission (PlacePreston), with its own budget, and logs where he is; the mission
        instance never runs KeepPreston."""
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        keep, preston, load = body("KeepCodsworth"), body("KeepPreston"), body("KeepCodsworthLoad")
        self.assertRegex(keep, r"if KeeperOnly\s+KeepPreston\(player\)")                # only the keeper instance
        self.assertRegex(preston, r"if prestonFails < 10\s+if PlacePreston\(player, \"keeper\"\)")
        self.assertRegex(body("Relocate"), r"if PlacePreston\(player, \"mission\"\)\s+relocateFails \+= 1")
        self.assertNotIn("MoveOver(Preston", psc)                       # one rule for him: PlacePreston
        self.assertIn("prestonFails += 1", preston)
        self.assertNotIn("GetStage", preston)                           # runs after stage 200, whatever the stage
        self.assertNotIn("GetStage", body("PlacePreston"))
        self.assertNotIn("MoveTo(", preston)                            # the same move as Relocate: PlacePreston only
        self.assertIn('TracePreston("keeper status")', preston)
        self.assertIn("keeperChecks % KeeperStatusEvery == 0", preston)
        self.assertIn("prestonFails = 0", load)                         # a fresh budget on every save load
        self.assertLess(load.index("prestonFails = 0"), load.index("StartTimer(CodsworthCheck, 2)"))
        self.assertIn('TracePreston("keeper load")', load)
        self.assertNotIn("CancelTimer(2)", psc)
        for v in ("int prestonFails = 0", "int keeperChecks = 0"):
            self.assertRegex(psc, rf"(?m)^{v}$")
        self.assertRegex(psc, r"(?m)^int Property KeeperStatusEvery = 12 Auto Const$")
        self.assertNotIn("KeeperStatusEvery", make_mission.mandatory_properties(psc))     # the plugin is unchanged
        self.assertIn('TraceSpot(what, Preston, "preston", prestonOff, prestonState, prestonMoves, prestonHeld, prestonHolds, '
                      'prestonFails)',
                      body("TracePreston"))
        trace = body("TraceSpot")
        for field in ('" d="', '" off="', '" state="', '" moves="', '" disabled="', '" dead="', '" fails="',
                      '" player="', '" interior="'):
            self.assertIn(field, trace)
        self.assertIn('Trace(what + " " + name + " d="', trace)
        # the keeper quest carries the mission's properties, Preston among them (no new plugin record)
        cs = read(CS)
        keeper = cs[cs.index("var ks = new SF.ScriptEntry"):cs.index("keeper.VirtualMachineAdapter")]
        self.assertIn("MissionProps(ks);", keeper)
        self.assertIn('Obj("Preston", prestonRef.FormKey)', cs[cs.index("void MissionProps("):cs.index("MissionProps(script);")])

    def test_keeper_rule_model_after_the_mission(self):
        """The keeper's rule on plain numbers, after stage 200, with make_mission.place_at (the script's PlaceAt, by
        PlacePreston): Preston snapped back to his local spot, the mission's check is off. He is put back only when the
        player is outdoors near his merged spot, always to that spot, and a no-op move spends the budget until a load
        renews it."""
        ox, oy, local = -1200.0, -2700.0, (-811.14, 1002.46)
        spot = (local[0] + ox, local[1] + oy)

        def keeper_check(state, player, outdoors, moveto_works, same_world=True):
            if state["fails"] >= 10:
                return
            off = math.dist(state["pos"], spot)
            dp = math.dist(player, state["pos"]) if same_world else float("inf")
            if make_mission.place_at(off, dp, math.dist(player, spot), not outdoors, False) == "move":
                if moveto_works:
                    state["pos"] = spot
                else:
                    state["fails"] += 1

        street, sanctuary = (-2011.1, -1697.2), (-1146.7, 1293.8)
        s = {"pos": local, "fails": 0}
        keeper_check(s, sanctuary, True, True)                          # elsewhere: he stays where he is
        self.assertEqual(s["pos"], local)
        keeper_check(s, street, False, True)                            # in the museum: no move from an interior
        self.assertEqual(s["pos"], local)
        keeper_check(s, street, True, True)                             # back at the museum: put back
        self.assertEqual(s["pos"], spot)
        keeper_check(s, street, True, True)                             # at his spot: left alone
        self.assertEqual(s["pos"], spot)
        s = {"pos": local, "fails": 0}
        for _ in range(12):
            keeper_check(s, street, True, False)
        self.assertEqual(s["fails"], 10)                                # budget spent: the keeper stops trying
        keeper_check(s, street, True, True)
        self.assertEqual(s["pos"], local)
        s["fails"] = 0                                                  # a save load renews it
        keeper_check(s, street, True, True, same_world=False)           # another world (float max) counts as off
        self.assertEqual(s["pos"], spot)

    def test_preston_off_his_spot_near_the_player_is_put_back(self):
        """FAL-128, the PC's 31 Oct logs (pc-evidence-20261110): Preston was moved once from 544 m away (cell=None) and
        then read 100 to 453 m from the player all session; at 20:59:31 the player stood 9 m from the spot and he was
        155.3 away. Under RelocateGap, MoveOver called that "already moved" and never moved him again. The fixed-spot
        rule puts him back once the player is within PlaceRadius, but not while he fights or the player is inside."""
        spot, player, preston = (-2011.14, -1697.54), (-2018.7, -1692.4), (-1960.0, -1850.0)
        off, dp, to_spot = math.dist(preston, spot), math.dist(player, preston), math.dist(player, spot)
        self.assertGreater(off, 25.0)
        self.assertLess(dp, 1500.0)                                     # what MoveOver read as "already there"
        self.assertEqual(make_mission.place_at(off, dp, to_spot, False, False), "move")
        self.assertEqual(make_mission.place_at(off, dp, to_spot, False, True), "off, fighting")
        self.assertEqual(make_mission.place_at(off, dp, to_spot, True, False), "off, player inside")
        self.assertEqual(make_mission.place_at(off, dp, 544.4, False, False), "off, player away")   # cell=None range
        self.assertEqual(make_mission.place_at(10.0, 9.0, to_spot, False, False), "at spot")
        # snapped back or in another world: off, also while "fighting" (he cannot fight from there)
        self.assertEqual(make_mission.place_at(2955.0, 2955.0, to_spot, False, True), "move")
        self.assertEqual(make_mission.place_at(0.0, float("inf"), to_spot, False, False), "move")

    def test_follow_skips_the_door_hold(self):
        """FAL-866: once BeginFollow has armed the instance, PlacePreston does not move him back or hold him,
        including when he is already at the door (the 10 Nov hold) or off it (the put-back)."""
        self.assertEqual(make_mission.place_at(1.0, 2.0, 2.0, False, False, held=False), "at spot, held")
        self.assertEqual(make_mission.place_at(1.0, 2.0, 2.0, False, False, held=False, following=True), "follow")
        self.assertEqual(make_mission.place_at(40.0, 10.0, 10.0, False, False), "move")
        self.assertEqual(make_mission.place_at(40.0, 10.0, 10.0, False, False, following=True), "follow")
        self.assertEqual(make_mission.place_at(40.0, 10.0, 10.0, False, True, following=True), "follow")

    def test_preston_is_never_offset_twice(self):
        """31 Oct 16:33 (.1.log): with the player about one offset length south-west of them, raiders already moved
        were offset again by MoveOver, to (-3000..-3150, -4500..-4600). PlacePreston's target is fixed, never his own
        position + the offset, so the keeper can never send Preston there (2590549e's keeper could)."""
        psc = read(PSC)
        place = psc[psc.index("bool Function PlacePreston("):psc.index("EndFunction", psc.index("bool Function PlacePreston("))]
        self.assertIn("float tx = PrestonLocalX + MergeOffsetX", place)
        self.assertIn("float ty = PrestonLocalY + MergeOffsetY", place)
        self.assertIn("float tz = PrestonLocalZ", place)
        self.assertNotRegex(place, r"\.GetPosition[XY]\(\) \+ MergeOffset")
        self.assertIn('PlaceAt(Preston, "Preston", tx, ty, tz, player, who, "at the museum door", fighting)', place)
        self.assertIn("a.MoveTo(player, tx - px, ty - py, tz - pz, True, False)", function_body(psc, "PlaceAt"))
        far = (-2011.14 - 1200.0, -1697.54 - 2700.0)                    # MoveOver's second target for him
        self.assertEqual(make_mission.place_at(0.0, 2955.0, math.dist(far, (-2011.14, -1697.54)), False, False),
                         "off, player away")

    def test_script_carries_the_place_rule(self):
        """make_mission.place_at is PlaceAt's decision with its callers' hold, in the same order; PlacePreston and
        PlaceCodsworth both use it, count a move whichever way it ends, and hold (FAL-170: the hold at the spot and after
        a move that lands; the release is the callers', before it)."""
        psc = read(PSC)
        place = function_body(psc, "PlaceAt")
        steps = ["if off <= HoldRadius && dp < RelocateGap", 'return "at spot"',
                 "if player.IsInInterior()", 'return "off, player inside"',
                 "> PlaceRadius * PlaceRadius", 'return "off, player away"',
                 "if dp < RelocateGap && fighting", 'return "off, fighting"',
                 "a.MoveTo(", "bool failed = after > HoldRadius || d >= RelocateGap", 'return "move failed"',
                 'return "placed"']
        at = [place.index(s) for s in steps]
        self.assertEqual(at, sorted(at))
        self.assertIn("Debug.Notification(", place)
        self.assertNotIn("SetRestrained", place)                         # the callers hold (HoldDue)
        self.assertEqual(len(re.findall(r"\.MoveTo\(", psc)), 3)          # PlaceAt, MoveOver, and WFC-01 rescue
        due = function_body(psc, "HoldDue")
        self.assertRegex(due, r"if fighting\s+return False\s+endif\s+"
                              r'return s == "placed" \|\| \(s == "at spot" && !held && off <= HeldRadius\)')
        for who in ("Preston", "Codsworth"):
            wrap = function_body(psc, "Place" + who)
            low = who[0].lower() + who[1:]
            steps = [f"bool fighting = {who}.GetCombatState() != 0",
                     f'string s = PlaceAt({who}, "{who}", tx, ty, tz, player, ',
                     f"{low}Off = SpotOff({who}, tx, ty, tz)",
                     'if s == "placed" || s == "move failed"', f"{low}Moves += 1",
                     f"if HoldDue(s, fighting, {low}Held, {low}Off)", f"Hold{who}(",
                     f"{low}State = HeldState(s, {low}Held)", 'return s == "move failed"']
            at = 0
            for s in steps:                                             # each one after the one before
                at = wrap.index(s, at) + len(s)
            self.assertNotIn(f'{low}State = "', wrap)                    # every state goes through HeldState

    def test_place_radii_follow_the_evidence(self):
        """PlaceRadius below the farthest move that landed in a loaded cell and held (353 m, raider 4, 31 Oct) and so
        below every move that ended with cell=None (488 m on), and above Codsworth's 122 m moves (loaded cell, 31 Oct);
        HoldRadius above FindRadius (finding him is no move)."""
        f = make_mission.script_floats(read(PSC))
        self.assertLess(f["PlaceRadius"], 353.0)
        self.assertGreater(f["PlaceRadius"], 122.0)
        self.assertLess(f["PlaceRadius"], f["RelocateRadius"])
        self.assertGreater(f["HoldRadius"], f["FindRadius"])
        self.assertLess(f["HoldRadius"], f["PlaceRadius"])
        self.assertLess(f["HeldRadius"], f["HoldRadius"])               # FAL-170: held only close to the spot...
        self.assertGreater(f["HeldRadius"], 1.5)                        # ...where the 10 Nov placement landed
        for name in ("PlaceRadius", "HoldRadius", "HeldRadius", "PrestonLocalX", "PrestonLocalY", "PrestonLocalZ",
                     "CodsworthLocalX", "CodsworthLocalY", "CodsworthLocalZ"):
            self.assertNotIn(name, make_mission.mandatory_properties(read(PSC)))   # the plugin is unchanged

    def test_codsworth_spot_is_where_the_moves_put_him(self):
        """FAL-163: every logged move put Codsworth at (-2346.7, -1406.1..-1406.2, 111.7) (23 Oct, playtest row 32; 31 Oct,
        pc-evidence-20261110): his plugin spot (ACHR 0x811 = Fallout 4's 01CA7D, the writer's fixture and the doc's
        table) + the merge offset."""
        f = make_mission.script_floats(read(PSC))
        local = (f["CodsworthLocalX"], f["CodsworthLocalY"], f["CodsworthLocalZ"])
        self.assertEqual(local, (-1146.709, 1293.837, 111.734))
        self.assertIn('"pos": [-1146.709, 1293.837, 111.734]', read(CS))
        self.assertIn("(-1146.709, 1293.837, 111.734) m",
                      read(os.path.join(ROOT, "docs", "mission", "when-freedom-calls.md")))
        merged = (local[0] + f["MergeOffsetX"], local[1] + f["MergeOffsetY"], local[2])
        for a, b in zip(merged, (-2346.7, -1406.15, 111.7)):
            self.assertAlmostEqual(a, b, delta=0.06)

    def test_codsworth_has_prestons_rule(self):
        """FAL-163, the owner's most reported defect ("Codsworth is not at Sanctuary", playtest rows 27, 32, 42): the
        keeper moved him with MoveOver once per session (31 Oct, from 122 m) and never again, and he went back to his
        unmerged spot within about three minutes (29 Oct). He now has Preston's fixed-spot rule (PlaceAt): his own
        fixed target, budget, state variables, load and status lines and on-screen notes; MoveOver is the raiders' only."""
        psc = read(PSC)
        place = function_body(psc, "PlaceCodsworth")
        for line in ("float tx = CodsworthLocalX + MergeOffsetX", "float ty = CodsworthLocalY + MergeOffsetY",
                     "float tz = CodsworthLocalZ"):
            self.assertIn(line, place)
        self.assertNotRegex(place, r"\.GetPosition[XY]\(\) \+ MergeOffset")
        self.assertNotIn("MoveOver(Codsworth", psc)
        self.assertEqual(re.findall(r"if MoveOver\((\w+)", psc), ["Raiders"])
        keep = function_body(psc, "KeepCodsworth")
        self.assertRegex(keep, r"if PlaceCodsworth\(player\)\s+codsworthFails \+= 1\s+if codsworthFails >= 10\s+"
                               r'codsworthState = "gave up"\s+Trace\([^\n]*\n\s+if IsTestModeEnabled\(\)\s+Debug\.Notification\(')
        self.assertRegex(keep, r"if KeeperOnly\s+KeepPreston\(player\)\s+"
                               r"if Codsworth != None && keeperChecks % KeeperStatusEvery == 0\s+"
                               r'TraceCodsworth\("keeper status"\)')
        self.assertNotIn("GetStage", keep + place)                      # after stage 200 too
        load = function_body(psc, "KeepCodsworthLoad")
        tail = load[load.rindex("if Codsworth != None"):]
        self.assertRegex(tail, r'if Codsworth != None\s+TraceCodsworth\("keeper load"\)\s+if IsTestModeEnabled\(\)\s+Debug\.Notification\('
                               r'"FO4SF keeper: Codsworth "')
        self.assertLess(load.index('TraceCodsworth("keeper load")'), load.index("StartTimer(CodsworthCheck, 2)"))
        self.assertIn('TraceSpot(what, Codsworth, "codsworth", codsworthOff, codsworthState, codsworthMoves, '
                      'codsworthHeld, codsworthHolds, codsworthFails)', function_body(psc, "TraceCodsworth"))
        for v in ("int codsworthMoves = 0", "float codsworthOff = -1.0", 'string codsworthState = "none"'):
            self.assertRegex(psc, rf"(?m)^{v}$")                          # sqv FO4SF_CodsworthKeeper shows them

    def test_codsworth_rule_model(self):
        """His rule on the logged numbers (make_mission.place_at, the script's PlaceAt). 31 Oct: moved from 122 m, he
        landed in a loaded cell. A snap-back is caught at the next check once the player is near; from Concord (444 m)
        nothing is moved into an unloaded cell, where MoveOver (800 m) would; a drift under RelocateGap from the player,
        which MoveOver called "already moved", is put back."""
        spot, local = (-2346.709, -1406.163), (-1146.709, 1293.837)
        start, concord = (-2467.7, -1406.9), (-2011.1, -1697.5)          # the walk's start and the museum door

        def decide(codsworth, player, same_world=True, interior=False):
            dp = math.dist(player, codsworth) if same_world else float("inf")
            return make_mission.place_at(math.dist(codsworth, spot), dp, math.dist(player, spot), interior, False)

        self.assertAlmostEqual(math.dist(start, spot), 121.0, delta=1.5)
        self.assertEqual(decide(local, start), "move")                  # unmoved at the start: placed from 121 m
        self.assertEqual(decide(local, start, same_world=False), "move")
        self.assertEqual(decide((-2346.5, -1406.0), start), "at spot, held")   # calm within HeldRadius
        self.assertEqual(decide(local, concord), "off, player away")    # snapped back while the player is at Concord
        self.assertEqual(decide(local, (-2300.0, -1450.0)), "move")     # ...caught when he comes back
        self.assertEqual(decide(local, start, interior=True), "off, player inside")
        drifted = (-2290.0, -1380.0)                                    # 62 m off his spot, 180 m from the player
        self.assertLess(math.dist(drifted, start), 1500.0)              # what MoveOver read as "already there"
        self.assertEqual(decide(drifted, start), "move")

    def test_codsworth_is_held_once_placed(self):
        """FAL-163, the PC's saves of 7 to 9 Nov (save-evidence-20261110): Codsworth heads straight for his editor
        coordinates (heading = bearing within 0.02 degrees) at about 0.34 m/s, so a put-back alone repeats about every
        75 s. With the keeper's check (8.3 s measured on the PC) over 10 minutes: without a hold that holds, 9 put-backs;
        with it, the one at the start. A fight releases him whatever his flag; calm at his spot, he is held again."""
        def put_backs(hold_works, step=8.3, speed=0.34):
            off, held, moves, t = 178.9, False, 0, 0.0                   # 9 Nov 19:49:33: 178.9 m off his spot
            while t < 600.0:
                state = make_mission.place_at(off, off, 120.0, False, False, held=held, landed=True)
                if state.startswith("placed"):
                    off, moves = 0.5, moves + 1
                held = hold_works and state.endswith(", held")
                if not held:
                    off += speed * step                                 # he walks off towards his editor spot
                t += step
            return moves

        self.assertEqual(put_backs(False), 9)
        self.assertEqual(put_backs(True), 1)
        self.assertEqual(make_mission.place_at(0.5, 120.0, 120.0, False, True, held=True), "at spot")     # released
        self.assertEqual(make_mission.place_at(0.5, 120.0, 120.0, False, False, held=False), "at spot, held")

    def test_raiders_are_never_offset_twice(self):
        """31 Oct 16:33:47 (.1.log): with the player at about (-2551, -4055), one offset length south-west of the
        museum, MoveOver moved raiders already at the museum a second time, raider 0 from about (-1950, -1850) to
        (-3150, -4550). A raider's target must lie within RelocateRadius of Preston's merged spot (its unmerged spot is
        within 120 m of his), so a raider already moved is never moved again (FAL-163)."""
        psc = read(PSC)
        move = function_body(psc, "MoveOver")
        guard = ("float hx = x - (PrestonLocalX + MergeOffsetX)", "float hy = y - (PrestonLocalY + MergeOffsetY)",
                 "if hx * hx + hy * hy > RelocateRadius * RelocateRadius")
        for line in guard:
            self.assertIn(line, move)
        self.assertLess(move.index(guard[-1]), move.index("a.MoveTo("))
        self.assertRegex(move, re.escape(guard[-1]) + r"\s+return False")
        f = make_mission.script_floats(psc)
        ox, oy, radius, gap = f["MergeOffsetX"], f["MergeOffsetY"], f["RelocateRadius"], f["RelocateGap"]
        door = (f["PrestonLocalX"] + ox, f["PrestonLocalY"] + oy)

        def moves(raider, player):
            target = (raider[0] + ox, raider[1] + oy)
            return (math.dist(player, raider) >= gap and math.dist(player, target) <= radius
                    and math.dist(target, door) <= radius)

        self.assertTrue(moves((-829.1, 1001.8), (-2011.1, -1697.5)))    # unmerged, player at the door: moved
        moved, far_player = (-1950.0, -1850.0), (-2551.3, -4055.1)
        self.assertTrue(math.dist(far_player, moved) >= gap and
                        math.dist(far_player, (moved[0] + ox, moved[1] + oy)) <= radius)   # what MoveOver did
        self.assertFalse(moves(moved, far_player))                      # now: no second offset
        self.assertFalse(moves((-829.1, 1001.8), far_player))           # and the player is not at its spot

    def test_preston_spot_is_where_the_moves_put_him(self):
        """In game 28 Oct (new game run 3) the moves put Preston at (-2011.14, -1697.54, 89.09): his spot + the merge
        offset must be that point."""
        f = make_mission.script_floats(read(PSC))
        got = (f["PrestonLocalX"] + f["MergeOffsetX"], f["PrestonLocalY"] + f["MergeOffsetY"], f["PrestonLocalZ"])
        for a, b in zip(got, (-2011.14, -1697.54, 89.09)):
            self.assertAlmostEqual(a, b, places=2)

    def test_keeper_state_is_visible_without_a_log(self):
        """FAL-128: both owner tests (7 and 9 Nov) ran with Papyrus logging off, so nothing showed whether the keeper
        ran. Its state is in script variables (sqv FO4SF_CodsworthKeeper) and on screen at each load, each move and a
        spent budget."""
        psc = read(PSC)
        for v in ("int prestonMoves = 0", "float prestonOff = -1.0", 'string prestonState = "none"'):
            self.assertRegex(psc, rf"(?m)^{v}$")
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        load = body("KeepCodsworthLoad")
        self.assertLess(load.index('TracePreston("keeper load")'), load.index("Debug.Notification("))
        self.assertIn("PlaceAt(Preston,", body("PlacePreston"))
        self.assertIn("Debug.Notification(", body("PlaceAt"))         # every move, on screen
        self.assertRegex(body("KeepPreston"), r'prestonState = "gave up"[^\n]*\n(.*\n)*\s+Debug\.Notification\(')
        self.assertIn('" preston_off=" + prestonOff', psc)             # and in the mission's status line

    def test_preston_is_held_after_a_placement(self):
        """FAL-170, in game 10 Nov (f9cae827, the 9 Nov save, logging on): placed 1.5 m off his spot, he walked off at
        about 0.9 m/s, not fighting, and was put back every 29 s. A move that lands holds him in the same call (unless he
        fights); a failed move holds nobody. Only the move is on screen."""
        spot, player = (-2011.14, -1697.54), (-2013.0, -1696.0)
        off = 73.7                                                      # at the load, 10 Nov
        self.assertEqual(make_mission.place_at(off, off, math.dist(player, spot), False, False), "move")
        self.assertEqual(make_mission.place_at(off, off, 2.4, False, False, landed=True), "placed, held")
        self.assertEqual(make_mission.place_at(off, off, 2.4, False, False, landed=False), "move failed")
        self.assertEqual(make_mission.place_at(off, off, 2.4, False, False, held=True, landed=False),
                         "move failed, held")
        # in another world while "fighting": moved, but never held in a fight
        self.assertEqual(make_mission.place_at(0.0, float("inf"), 2.4, False, True, landed=True), "placed")
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        hold = body("HoldActor")
        self.assertIn("bool ok = a.SetRestrained(True)", hold)
        self.assertIn('Trace("hold " + name + " by=" + who + " off=" + off + " ok=" + ok)', hold)
        self.assertEqual(body("PlaceAt").count("Debug.Notification("), 1)   # the move's, as before
        for who in ("Preston", "Codsworth"):                            # FAL-163: the same hold for Codsworth
            low = who.lower()
            mine = body("Hold" + who)
            for step in (f'HoldActor({who}, "{low}", who, {low}Off)', f"{low}Held = True", f"{low}Holds += 1"):
                self.assertIn(step, mine)
            place = body("Place" + who)
            self.assertLess(place.index("PlaceAt("), place.index(f"Hold{who}("))   # in the same call, after the move
            self.assertNotIn("Debug.Notification(", place)
            for v in (f"bool {low}Held = False", f"int {low}Holds = 0"):   # readable with sqv
                self.assertRegex(psc, rf"(?m)^{v}$")
        for name in ("HoldActor", "HoldPreston", "HoldCodsworth", "HoldDue", "ReleaseInFight", "ReleaseCodsworthInFight",
                     "ReleaseActor", "HeldState"):
            self.assertNotIn("Debug.Notification(", body(name), name)
            self.assertNotIn("GetStage", body(name), name)
        self.assertRegex(psc, r"(?m)^float Property HeldRadius = 3\.0 Auto Const$")

    def test_preston_is_held_at_his_spot(self):
        """FAL-170: at his spot, calm, not yet held and within HeldRadius, he is held without a move (a load whose hold
        the engine did not keep, a save where he already stands there). Up to HoldRadius he is left until his put-back,
        which holds him."""
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False), "at spot, held")
        self.assertEqual(make_mission.place_at(3.0, 4.0, 2.4, False, False), "at spot, held")
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False, held=True), "at spot, held")
        self.assertEqual(make_mission.place_at(10.0, 12.0, 2.4, False, False), "at spot")
        self.assertEqual(make_mission.place_at(10.0, 12.0, 2.4, False, False, held=True), "at spot, held")
        self.assertEqual(make_mission.place_at(26.0, 28.0, 2.4, False, False), "move")
        self.assertEqual(make_mission.place_at(1.5, float("inf"), 2.4, False, False), "move")   # another world
        psc = read(PSC)
        trace = function_body(psc, "TraceSpot")
        for field in ('" held=" + held', '" holds=" + holds'):
            self.assertIn(field, trace)
        for who in ("Preston", "Codsworth"):                            # FAL-163: his status line too
            low = who.lower()
            self.assertIn(f"{low}Moves, {low}Held, {low}Holds, {low}Fails)", function_body(psc, "Trace" + who))
        self.assertIn('" preston_off=" + prestonOff + " held=" + prestonHeld', psc)   # the mission's status line
        self.assertRegex(function_body(psc, "HeldState"), r'if held\s+return s \+ ", held"\s+endif\s+return s')

    def test_a_held_preston_is_let_go_in_a_fight(self):
        """FAL-170: never held in a fight (his death stays the quest's failure path). PC review of 79c9ba81: the release
        trusted this instance's prestonHeld, which can be False while he is held. Now both instances let him go on
        every check of a fight, whatever the flag, before PlacePreston, whatever the budget, interior or stage, with one
        log line per fight and instance; held again once calm."""
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, True, held=True), "at spot")
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, True), "at spot")
        self.assertEqual(make_mission.place_at(40.0, 42.0, 2.4, False, True, held=True), "off, fighting")
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False), "at spot, held")   # calm again
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        self.assertRegex(body("ReleaseActor"), r"if a\.GetCombatState\(\) != 0\s+a\.SetRestrained\(False\)\s+"
                                               r"if !logged\s+Trace\(\"release \" \+ name \+ \" by=\" \+ who \+ "
                                               r"\" reason=fighting\"\)\s+endif\s+return True\s+endif\s+return False")
        for who, fn in (("Preston", "ReleaseInFight"), ("Codsworth", "ReleaseCodsworthInFight")):
            low = who.lower()
            self.assertRegex(body(fn), rf'if ReleaseActor\({who}, "{low}", who, {low}Fighting\)\s+{low}Held = False\s+'
                                       rf"{low}Fighting = True\s+return True\s+endif\s+{low}Fighting = False\s+return False")
            self.assertRegex(psc, rf"(?m)^bool {low}Fighting = False$")
        # FAL-163: the keeper releases Codsworth on every check, before his placement and whatever his budget
        self.assertRegex(body("KeepCodsworth"), r'if Codsworth != None\s+ReleaseCodsworthInFight\("keeper"\)\s+endif\s+'
                                                r"if Codsworth != None && codsworthFails < 10\s+if PlaceCodsworth")
        self.assertIn("(Codsworth != None && (codsworthFails < 10 || codsworthHolds > 0))", body("KeepCodsworth"))
        self.assertNotIn("ReleasePreston", psc)
        self.assertNotRegex(psc, r"if prestonHeld &&")                   # no release behind the flag
        self.assertNotIn("ReleaseInFight(\"", body("PlacePreston"))      # the callers release, not PlacePreston
        tick = psc[psc.index("Event OnTimer("):psc.index("EndEvent", psc.index("Event OnTimer("))]
        self.assertRegex(tick, r'KeepCodsworthStart\(\)\s+ReleaseInFight\("mission"\)[^\n]*\s+if relocateFails < 10')
        self.assertRegex(body("KeepPreston"), r'ReleaseInFight\("keeper"\)\s+if prestonFails < 10')
        # the keeper keeps checking with a spent budget once it has held him, so a fight still releases him
        self.assertIn("(KeeperOnly && (prestonFails < 10 || prestonHolds > 0))", body("KeepCodsworth"))
        self.assertRegex(psc, r"(?m)^bool prestonFighting = False$")

    def test_two_instances_a_load_and_a_spent_budget(self):
        """PC review of 79c9ba81, on plain numbers: the engine's restraint is one, the flags are two (mission, keeper).
        Each check of an instance: in a fight SetRestrained(False) whatever its flag (ReleaseInFight), then PlacePreston
        (make_mission.place_preston) unless its budget is spent; a new hold sets the restraint."""
        def check(world, who, fighting, off=1.5, spent=False):
            if fighting:
                world["restrained"] = False                             # ReleaseInFight
                world[who] = False
            if spent:
                return
            state = make_mission.place_at(off, off + 2.0, 2.4, False, fighting, held=world[who], landed=True)
            if state.endswith(", held") and not world[who]:
                world["restrained"] = True                              # HoldPreston
            world[who] = state.endswith(", held")

        # the mission holds him; the keeper's flag stays False until its own check: a fight still releases him
        w = {"restrained": False, "mission": False, "keeper": False}
        check(w, "mission", False)
        self.assertEqual(w, {"restrained": True, "mission": True, "keeper": False})
        check(w, "keeper", True)
        self.assertFalse(w["restrained"])
        # held across a load: the keeper clears its flag, the engine keeps the restraint; after stage 200 only the
        # keeper runs, and a fight releases him
        w = {"restrained": True, "mission": True, "keeper": False}
        check(w, "keeper", True)
        self.assertFalse(w["restrained"])
        # a spent budget: no PlacePreston, the release still runs
        w = {"restrained": True, "mission": False, "keeper": False}
        check(w, "keeper", True, spent=True)
        self.assertFalse(w["restrained"])
        check(w, "keeper", False, spent=True)                           # no hold without PlacePreston
        self.assertFalse(w["restrained"])
        # a hold 3 to 25 m off (a put-back that landed there): out of HeldRadius, still released in a fight
        w = {"restrained": False, "mission": False, "keeper": False}
        check(w, "mission", False, off=60.0)
        self.assertTrue(w["restrained"])
        check(w, "keeper", True, off=10.0)
        self.assertFalse(w["restrained"])

    def test_a_load_holds_him_again(self):
        """FAL-170: the keeper counts Preston as not held at every save load, Codsworth or not, so its first check after
        the load holds him again whatever the engine kept. The mission instance registers no load event, so its flag can
        outlive a load: the keeper's hold and every put-back cover that."""
        psc = read(PSC)
        load = psc[psc.index("Function KeepCodsworthLoad()"):psc.index("EndFunction", psc.index("Function KeepCodsworthLoad()"))]
        self.assertIn("prestonHeld = False", load[load.index("prestonFails = 0"):])       # outside Codsworth's guard
        self.assertLess(load.index("prestonHeld = False"), load.index("StartTimer(CodsworthCheck, 2)"))
        self.assertEqual(psc.count('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")'), 2)   # keeper + mission (2f)
        guarded = load[load.index("if Codsworth != None"):load.index("prestonFails = 0")]
        self.assertIn("codsworthHeld = False", guarded)                  # FAL-163: Codsworth too
        # held before the save; after the load the flag is False, so the first check at his spot holds him again
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False, held=False), "at spot, held")

    def test_held_preston_is_put_back_once(self):
        """In game 10 Nov: 73.7 m off at the load, placed within a second, then 7 put-backs in 175 s while he walked off
        at about 0.9 m/s; held from the console, none in 100 s and the same position in every line. On plain numbers,
        with the mission's 1 s check: without a hold that holds, 7 put-backs; with it, the one at the load (the PC's check
        3 expects that)."""
        def put_backs(hold_works):
            off, held, moves = 73.7, False, 0
            for _ in range(175):
                state = make_mission.place_at(off, off, 2.4, False, False, held=held, landed=True)
                if state.startswith("placed"):
                    off, moves = 1.5, moves + 1
                held = hold_works and state.endswith(", held")
                if not held:
                    off += 0.9                                          # he walks off
            return moves

        self.assertEqual(put_backs(False), 7)
        self.assertEqual(put_backs(True), 1)

    def test_moves_trace_the_worlds(self):
        """Codex's world-identity point (#353): every move logs the player's and the actor's world before it and the
        actor's world after it, so the anchor gate can be designed from evidence."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        move = psc[psc.index("bool Function MoveOver"):psc.index("Function Trace(")]
        self.assertIn("player.GetWorldSpace()", move)
        self.assertIn("a.GetWorldSpace()", move)
        self.assertLess(move.index('" player="'), move.index("a.MoveTo("))
        self.assertGreater(move.index('" player="'), move.index("RelocateRadius * RelocateRadius"))   # moves only
        self.assertGreater(move.index('" after="'), move.index("a.MoveTo("))

    def test_trace_reopens_the_log_after_a_save_load(self):
        """2f: OpenUserLog runs once at start (StartQuestInstance) and once on reload (OnPlayerLoadGame) rather than on
        every Trace call."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertIn("Debug.OpenUserLog(LogName)", function_body(psc, "StartQuestInstance"))
        load_ev = psc[psc.index("Event Actor.OnPlayerLoadGame"):psc.index("EndEvent", psc.index("Event Actor.OnPlayerLoadGame"))]
        self.assertIn("Debug.OpenUserLog(LogName)", load_ev)
        trace = psc[psc.index("Function Trace("):]
        trace = trace[:trace.index("EndFunction")]
        lines = [ln.strip() for ln in trace.splitlines()[1:] if ln.strip() and not ln.strip().startswith(";")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("Debug.TraceUser(LogName,"))

    def test_codsworth_is_an_optional_property(self):
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertRegex(psc, r"(?m)^Actor Property Codsworth Auto Const$")
        self.assertNotIn("Codsworth", make_mission.mandatory_properties(psc))


class StageAndInstallTests(unittest.TestCase):
    """Codex review 5563368986: a failed rebuild keeps the earlier stage; the pins are checked before install."""

    SPOT = [-811.14, 1002.46, 89.09]                                    # the script's PrestonLocalX/Y/Z
    CODSWORTH_SPOT = [-1146.709, 1293.837, 111.734]                     # the script's CodsworthLocalX/Y/Z

    def fake_stage(self, d, out, fail_at=None, during_check=None, extra=(), writes=None, preston=None, codsworth=None):
        def fake_run(cmd, cwd=None):
            if "points" in cmd:
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    json.dump({"raiders": [{"src": "046458", "dist_m": 18.9}], "preston": {"pos": preston or self.SPOT},
                               "codsworth": {"src": "01CA7D", "name": "Codsworth", "pos": codsworth or self.CODSWORTH_SPOT,
                                             "rot": [0, 0, 1]}}, f)
            elif "write" in cmd:
                if writes is not None:
                    writes.append(cmd)
                _write(os.path.join(cmd[cmd.index("write") + 5], make_mission.PLUGIN), b"plugin-" + out.encode())
            elif "check" in cmd:
                if writes is not None:
                    writes.append(cmd)
                if during_check:
                    during_check()
                if fail_at == "check":
                    sys.exit("check exit 1")
                return "all checks pass"
            elif "PapyrusCompiler" in cmd[0] or cmd[0] == "compiler":
                psc_name = next(a for a in cmd if str(a).endswith(".psc"))
                out_dir = next(a for a in cmd if str(a).startswith("-o="))[3:]
                stem = os.path.splitext(os.path.basename(psc_name))[0]
                _write(os.path.join(out_dir, stem + ".pex"), b"pex-" + stem.encode())
                return "Compilation succeeded"
            return ""
        core, raider = os.path.join(d, "FO4TerrainCore.esm"), os.path.join(d, "FO4ActorRaider.esm")
        for p, b in ((core, b"core"), (raider, b"raider")):
            if not os.path.exists(p):
                _write(p, b)
        zf = os.path.join(d, "cr.zip")
        if not os.path.exists(zf):
            import zipfile
            with zipfile.ZipFile(zf, "w") as z:
                z.writestr("Scripts/Source/Quest.psc", "Scriptname Quest")
                z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        with mock.patch.object(make_mission, "run", side_effect=fake_run):
            make_mission.main(["stage", "--out", out, "--fo4", "f4", "--starfield", "sf", "--core", core,
                               "--raider", raider, "--compiler", "compiler", "--content-resources", zf, *extra])

    def test_codsworth_is_in_the_plan_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, writes=writes)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertEqual(plan["codsworth"]["src"], "01CA7D")
            self.assertNotIn("--no-codsworth", writes[0])
            self.assertIn("check", writes[1])
            self.assertNotIn("--no-codsworth", writes[1])

    def test_no_codsworth_reaches_the_writer_and_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--no-codsworth"], writes=writes)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertIsNone(plan["codsworth"])
            self.assertIn("--no-codsworth", writes[0])
            self.assertIn("--no-codsworth", writes[1])   # check expects the same mode (Codex review 5564480667)

    def test_codsworth_assets_reach_the_writer_fold_and_verify(self):
        """The Codsworth thread's model (PR #361): stage copies the asset folders (not the report), names the mesh to the
        writer and check, pins each file in the plan; fold carries them and verify catches a changed one."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "codsworth_1018b")
            files = {"meshes/fo4port/actors/codsworth/codsworth.nif": b"nif", "geometries/ab/cd.mesh": b"mesh",
                     "materials/fo4port/texsets/actors/handy/body.mat": b"mat",
                     "textures/fo4port/actors/handy/body_color.dds": b"dds", "codsworth_report.json": b"{}"}
            for rel, b in files.items():
                _write(os.path.join(src, *rel.split("/")), b)
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--codsworth-assets", src], writes=writes)
            for cmd in writes:
                self.assertEqual(cmd[cmd.index("--codsworth-model") + 1], make_mission.CODSWORTH_MESH)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertEqual(sorted(plan["assets"]), sorted(r for r in files if r != "codsworth_report.json"))
            core_dir = os.path.join(d, "coreset")
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"core")
            folded = os.path.join(d, "folded")
            raider = os.path.join(d, "FO4ActorRaider.esm")
            self.assertEqual(make_mission.main(["fold", "--mission", out, "--core-dir", core_dir, "--out", folded,
                                                "--raider", raider]), 0)
            nif = os.path.join(folded, "Data", "meshes", "fo4port", "actors", "codsworth", "codsworth.nif")
            self.assertTrue(os.path.isfile(nif))
            self.assertFalse(os.path.exists(os.path.join(folded, "Data", "codsworth_report.json")))
            _write(nif, b"other")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", os.path.join(out, "plan.json"),
                                                "--raider", raider]), 1)

    def test_codsworth_voice_reaches_the_writer_and_the_plan(self):
        """His voice (PR #361): each lines.tsv row's <info>_<response>.wem is copied under his voice type's folder, named
        by its WEMFile id; voice.json carries the text and the sex rule ("sir" male, "mum" female) to the writer."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "voice")
            rows = [("000F1F6E", "1", "Synthetic line 1"), ("000F1F78", "1", "Synthetic line sir"), ("000F1F80", "1", "Synthetic line mum")]
            os.makedirs(src)
            with open(os.path.join(src, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
                f.write("quest\tsubtype\ttopic\tinfo\tresponse\tvoice\ttext\n")
                for info, resp, text in rows:
                    f.write(f"COMCodsworth\tHELO\tCOMCodsworthHellos\t{info}\t{resp}\tv.fuz\t{text}\n")
                    _write(os.path.join(src, "wem", "Windows", f"{info.lower()}_{resp}.wem"), info.encode())
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--codsworth-voice", src], writes=writes)
            voice_json = writes[0][writes[0].index("--codsworth-voice") + 1]
            self.assertEqual(writes[1][writes[1].index("--codsworth-voice") + 1], voice_json)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            base = make_mission.VOICE_DIR
            self.assertEqual(sorted(plan["assets"]), [f"{base}/00f4c001.wem", f"{base}/00f4c002.wem", f"{base}/00f4c003.wem"])
            with open(os.path.join(out, "Data", *base.split("/"), "00f4c002.wem"), "rb") as f:
                self.assertEqual(f.read(), b"000F1F78")

    def test_voice_sex_rule_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "voice")
            os.makedirs(src)
            with open(os.path.join(src, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
                f.write("info\tresponse\ttext\nAA\t1\tSynthetic sir.\nBB\t1\tSynthetic mum.\nCC\t1\tSynthetic Sirius\n")
            for n in ("aa_1", "bb_1", "cc_1"):
                _write(os.path.join(src, "wem", f"{n}.wem"), b"x")
            vj = os.path.join(d, "voice.json")
            make_mission.copy_voice(src, os.path.join(d, "data"), vj)
            with open(vj, encoding="utf-8") as f:
                self.assertEqual([l["sex"] for l in json.load(f)], ["male", "female", None])
            os.remove(os.path.join(src, "wem", "bb_1.wem"))
            with self.assertRaises(SystemExit):
                make_mission.copy_voice(src, os.path.join(d, "data2"), vj)

    def test_codsworth_assets_need_the_mesh(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "empty")
            os.makedirs(src)
            with self.assertRaises(SystemExit):
                self.fake_stage(d, os.path.join(d, "m"), extra=["--codsworth-assets", src])

    def snapshot(self, root):
        got = {}
        for base, _, files in os.walk(root):
            for n in files:
                p = os.path.join(base, n)
                with open(p, "rb") as f:
                    got[os.path.relpath(p, root)] = f.read()
        return got

    def test_rebuild_into_existing_stage_refused_and_failure_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            first = os.path.join(d, "wfc1")
            self.fake_stage(d, first)
            before = self.snapshot(first)
            self.assertIn("plan.json", before)
            with self.assertRaises(SystemExit):
                self.fake_stage(d, first)                       # occupied output
            self.assertEqual(self.snapshot(first), before)
            second = os.path.join(d, "wfc2")
            with self.assertRaises(SystemExit):
                self.fake_stage(d, second, fail_at="check")     # a failed rebuild publishes nothing
            self.assertFalse(os.path.exists(second))
            self.assertEqual(self.snapshot(first), before)
            # the failed attempt is kept, and a retry neither reuses nor deletes it
            failed = [n for n in os.listdir(d) if n.startswith("wfc2.partial-")]
            self.assertEqual(len(failed), 1)
            _write(os.path.join(d, failed[0], "failed-run.txt"), b"evidence")
            kept = self.snapshot(os.path.join(d, failed[0]))
            with self.assertRaises(SystemExit):
                self.fake_stage(d, second, fail_at="check")
            self.assertEqual(self.snapshot(os.path.join(d, failed[0])), kept)
            self.assertEqual(len([n for n in os.listdir(d) if n.startswith("wfc2.partial-")]), 2)
            self.fake_stage(d, second)                          # and a good retry still publishes
            self.assertTrue(os.path.exists(os.path.join(second, "plan.json")))
            self.assertEqual(self.snapshot(os.path.join(d, failed[0])), kept)

    def test_points_that_moved_preston_are_refused(self):
        """FAL-128: the script keeps Preston at its own PrestonLocalX/Y/Z, so a build whose points put him elsewhere
        would ship a keeper that drags him to the old spot. stage refuses it before the writer runs."""
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, writes=writes, preston=[-880.5, 1050.25, 90.0])   # the writer's synthetic spot
            self.assertIn("PrestonLocalX/Y/Z", str(e.exception))
            self.assertEqual(writes, [])
            self.assertFalse(os.path.exists(out))
            self.fake_stage(d, out, preston=[-811.1, 1002.5, 89.1])     # within SPOT_TOLERANCE: staged
            self.assertTrue(os.path.exists(os.path.join(out, "plan.json")))
        psc = read(PSC)
        self.assertIsNone(make_mission.spot_problem(psc, self.SPOT))
        self.assertIsNotNone(make_mission.spot_problem(psc, [-811.14, 1002.46]))           # not a position
        self.assertIsNotNone(make_mission.spot_problem(psc, [-811.14, 1002.46, 90.0]))     # z off by 0.91

    def test_points_that_moved_codsworth_are_refused(self):
        """FAL-163: the same guard for Codsworth's CodsworthLocalX/Y/Z; a --no-codsworth build has no keeper to drag him,
        so it is not refused."""
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, writes=writes, codsworth=[4, 5, 6])
            self.assertIn("CodsworthLocalX/Y/Z", str(e.exception))
            self.assertEqual(writes, [])
            self.assertFalse(os.path.exists(out))
            self.fake_stage(d, out, codsworth=[4, 5, 6], extra=["--no-codsworth"])
            self.assertTrue(os.path.exists(os.path.join(out, "plan.json")))
        psc = read(PSC)
        self.assertIsNone(make_mission.spot_problem(psc, self.CODSWORTH_SPOT, "Codsworth"))
        self.assertIsNotNone(make_mission.spot_problem(psc, self.SPOT, "Codsworth"))

    def test_master_changed_during_build_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            core = os.path.join(d, "FO4TerrainCore.esm")
            _write(core, b"core A")
            out = os.path.join(d, "wfc1")
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, during_check=lambda: _write(core, b"core B"))
            self.assertIn("changed during the build", str(e.exception))
            self.assertFalse(os.path.exists(out))

    def test_fold_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            stage = os.path.join(d, "wfc1")
            self.fake_stage(d, stage)
            core_dir = os.path.join(d, "coreset")
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"core")
            _write(os.path.join(core_dir, "Data", "Terrain", "x.btd"), b"btd")
            raider = os.path.join(d, "FO4ActorRaider.esm")
            folded = os.path.join(d, "folded")
            self.assertEqual(make_mission.main(["fold", "--mission", stage, "--core-dir", core_dir, "--out", folded,
                                                "--raider", raider]), 0)
            plan = os.path.join(stage, "plan.json")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 0)
            self.assertTrue(os.path.exists(os.path.join(folded, "Data", "Terrain", "x.btd")))
            # the masters or the staged files changed: verify refuses
            _write(raider, b"other raider")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 1)
            _write(raider, b"raider")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan]), 1)   # raider missing
            _write(os.path.join(folded, "FO4TerrainCore.esm"), b"newer core")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 1)
            # fold against a different core is refused and writes nothing
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"newer core")
            with self.assertRaises(SystemExit):
                make_mission.main(["fold", "--mission", stage, "--core-dir", core_dir, "--out", os.path.join(d, "f2"),
                                   "--raider", raider])
            self.assertFalse(os.path.exists(os.path.join(d, "f2")))
            self.assertFalse(os.path.exists(os.path.join(d, "f2.partial")))


class Phase2TrackBTests(unittest.TestCase):
    """Phase 2 Track B: 2b (StartNoWait startup), 2f (WFC-01 anti-stall + mission reload),
    2g (Preston HumanRace NPC + 3-exchange Scene + TestMode FollowTest gate),
    2h (Codsworth01 0x816 4-choice Scene + AllowPcDialog/AllowDefaultDialog),
    2k (Sanctuary01 0x817 workbench 0250FE/0x005C50 + 5-min test card)."""

    def test_2b_quests_are_not_start_game_enabled_and_support_startnowait(self):
        cs = read(CS)
        self.assertIn("static bool NonStartGameReady(SF.IQuestGetter q)", cs)
        self.assertIn("!q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled)", cs)
        self.assertIn("!q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled)", cs)
        self.assertIn("(((uint)q.Data.Flags & 0x10000u) == 0)", cs)
        for mutation_label in (
            "FO4SF_Min00 has StartGameEnabled",
            "keeper carries StartsEnabled",
            "Min00 carries 0x10000 flag",
            "Min00 stage 30 lacks QSDT log entry",
            "keeper has StartGameEnabled",
            "FO4SF_Codsworth01 has StartGameEnabled",
            "Codsworth alias not Optional",
            "FO4SF_Sanctuary01 has StartGameEnabled",
            "Sanctuary01 stage 10 lacks QSDT log entry",
        ):
            self.assertIn(mutation_label, cs)
        for scr in ("FO4SF_Min00Quest.psc", "FO4SF_Codsworth01Quest.psc", "FO4SF_Sanctuary01Quest.psc"):
            txt = read(os.path.join(ROOT, "scripts", "mission", scr))
            self.assertIn("Event OnQuestStarted()", txt, scr)
            self.assertIn("Event OnQuestInit()", txt, scr)
            self.assertIn("Function StartQuestInstance()", txt, scr)

    def test_m1_story_gate_silent_start_and_1h_no_dev_banners(self):
        psc = read(PSC)
        start_fn = function_body(psc, "StartQuestInstance")
        self.assertIn('Trace("mission gate mode=1 started=true")', start_fn)
        self.assertIn("LogWarfareStop()", start_fn)
        self.assertIn('Trace("mission gate mode=2 started=false")', function_body(psc, "LogWarfareStop"))
        self.assertNotIn("AdvanceTo(10)", start_fn)
        self.assertIn('Trace("min00 given by=codsworth")', function_body(psc, "GiveFromCodsworth"))
        self.assertIn('Trace("min00 given by=concord")', psc)
        self.assertRegex(psc, r"(?m)^float Property GiveConcordRadius = 150\.0 Auto Const$")

        # 1h: zero objective Debug.Notification banners, and every keeper Debug.Notification gated behind IsTestModeEnabled()
        self.assertNotIn("When Freedom Calls:", function_body(psc, "Apply"))
        for scr in make_mission.ALL_SCRIPTS:
            txt = read(os.path.join(ROOT, "scripts", "mission", scr + ".psc"))
            lines = txt.splitlines()
            for idx, ln in enumerate(lines):
                if "Debug.Notification(" in ln:
                    prev = lines[idx - 1].strip() if idx > 0 else ""
                    self.assertEqual(prev, "if IsTestModeEnabled()", f"{scr}:{idx + 1} notification not gated by test mode")

    def test_2f_and_m3_wfc01_rescue_absent_clear_combat_package_and_reload(self):
        cs = read(CS)
        self.assertIn('RaiderCombatPackageEdid = "DefaultCombatMasterPackage"', cs)
        self.assertIn('RaiderSandboxPackageEdid = "DefaultSandboxCurrentLocation"', cs)
        self.assertIn('"raider alias lacks combat package"', cs)

        psc = read(PSC)
        load_ev = psc[psc.index("Event Actor.OnPlayerLoadGame"):psc.index("EndEvent", psc.index("Event Actor.OnPlayerLoadGame"))]
        self.assertIn("relocateFails = 0", load_ev)
        self.assertIn('Trace("reload mission stage=" + st + " relocate_fails=" + relocateFails)', load_ev)
        self.assertIn("if st == 20", load_ev)
        self.assertIn("CheckConcordRaidersWfc01(Game.GetPlayer(), False)", load_ev)
        wfc = function_body(psc, "CheckConcordRaidersWfc01")
        writeoff = function_body(psc, "WriteOffRaider")
        self.assertIn('Trace("wfc01 rescue raider=" + i', wfc)
        self.assertIn('WriteOffRaider(r, i, "absent"', wfc)
        self.assertIn('Trace("wfc01 raider cleared " + reason + " id="', writeoff)
        self.assertIn("raiderCleared[idx] = True", writeoff)

        # Negative/stall test (M3): 4 raiders dead + 1 raider far away (> 250 m) ends with 'raider cleared absent' and stage 30
        door = (-2011.14, -1697.54, 89.09)
        player = (-2015.0, -1700.0, 89.1)
        raiders = [
            {"pos": (-2029.0, -1701.0, 75.0), "target": (-2029.0, -1701.0, 88.3), "dead": False, "loaded": True,
             "absent_sec": 0.0, "cleared": False},  # subterranean (z < targetZ - 8)
            {"pos": (-1820.0, -1701.0, 88.3), "target": (-2029.0, -1708.0, 88.1), "dead": False, "loaded": True,
             "absent_sec": 0.0, "cleared": False},  # drifted > 140 m
            {"pos": (-2450.0, -1710.0, 88.2), "target": (-2035.0, -1710.0, 88.2), "dead": False, "loaded": False,
             "absent_sec": 0.0, "cleared": False},  # far away / unloaded straggler
            {"pos": (-2027.0, -1721.0, 88.1), "target": (-2027.0, -1721.0, 88.1), "dead": True, "loaded": True,
             "absent_sec": 0.0, "cleared": False},  # already dead
            {"pos": (-2048.0, -1740.0, 88.2), "target": (-2048.0, -1740.0, 88.2), "dead": True, "loaded": True,
             "absent_sec": 0.0, "cleared": False},  # already dead
        ]
        rescued, cleared = make_mission.wfc01_step(player, False, door, raiders)
        self.assertEqual(rescued, [0, 1, 2])
        self.assertEqual(cleared, [])
        self.assertEqual(raiders[0]["pos"], raiders[0]["target"])
        self.assertEqual(raiders[1]["pos"], raiders[1]["target"])

        raiders[0]["dead"] = True
        raiders[1]["dead"] = True
        # Before >60 s, 4/5 dead keeps stage at 20; on second 61 (> 60.0 s), straggler clears -> stage 30!
        for _ in range(59):
            _, cleared = make_mission.wfc01_step(player, False, door, raiders)
            self.assertEqual(cleared, [])
            self.assertEqual(make_mission.next_stage(20, sum(1 for r in raiders if r["dead"] or r["cleared"]), 5, True, False), 20)
        _, cleared = make_mission.wfc01_step(player, False, door, raiders)
        self.assertEqual(cleared, [2])
        self.assertTrue(raiders[2]["cleared"])
        effective_dead = sum(1 for r in raiders if r["dead"] or r["cleared"])
        self.assertEqual(effective_dead, 5)
        self.assertEqual(make_mission.next_stage(20, effective_dead, 5, False, False), 30)

    def test_2g_and_m4_preston_npc_scene_logs_and_test_mode_follow_gate(self):
        cs = read(CS)
        self.assertIn('SfHumanRaceEdid = "HumanRace"', cs)
        self.assertIn('SfPapaKatzEdid = "UC_NA_PapaKatz"', cs)
        self.assertIn('SfPrestonVoiceEdid = "GenericMaleEvenToned"', cs)
        self.assertIn('SfPrestonOutfitEdid = "Outfit_FreestarRanger_Vest_with_Hat"', cs)
        self.assertIn('SfPrestonWeaponEdid = "Orion"', cs)
        self.assertIn("PrestonTalkSceneId = 0x900", cs)
        self.assertNotIn("calm.Duplicate", cs)
        # T6 fix: Preston & Codsworth direct E-Talk NPC scenes use 0x1814 (not 0x2814), SCPI = null, and only SceneActor ID = 0
        build_scene = cs[cs.index("static SF.Scene BuildTopScene("):cs.index("public sealed record MqVoiceSpec")]
        self.assertIn("Flags = (SF.Scene.Flag)0x1814", build_scene)
        self.assertIn("SCPI = null", build_scene)
        self.assertNotIn("0x2814", build_scene)
        self.assertNotIn("unchecked((uint)-2)", build_scene)
        self.assertIn("pscnFlags == 0x1814u", cs)
        self.assertIn("pscn.SCPI is null", cs)
        self.assertIn("pscn.Actors.Count == 1 && pscn.Actors[0].ID == 0", cs)
        self.assertIn("cscnFlags == 0x1814u", cs)
        self.assertIn("cscn.SCPI is null", cs)
        self.assertIn("cscn.Actors.Count == 1 && cscn.Actors[0].ID == 0", cs)

        com = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_COMPreston.psc"))
        psc = read(PSC)
        self.assertIn('Trace("preston talk end info=0x092A -> stage 40")', psc)
        self.assertIn('AdvanceTo(40, "fallback")', psc)
        self.assertIn('Trace("stage " + auiStageID + " by=" + by)', psc)
        for src in (com, function_body(psc, "BeginFollow")):
            self.assertIn('Game.GetFormFromFile(0x000860, "FO4SFCoreValues.esm") as GlobalVariable', src)
            self.assertIn("follow preston test-only refused: test mode off", src)

        s = make_mission.summarize([
            "FO4SF_MISSION rt=5.0 mission gate mode=1 started=true",
            "FO4SF_MISSION rt=6.0 min00 given by=codsworth",
            "FO4SF_MISSION rt=7.0 follow preston test-only refused: test mode off",
            "FO4SF_MISSION rt=8.0 reload mission stage=20 relocate_fails=0",
            "FO4SF_MISSION rt=9.0 wfc01 rescue raider=0 z=70.0 target_z=88.3 drift=18.3",
            "FO4SF_MISSION rt=70.0 wfc01 raider cleared absent id=2051 raider=2 elapsed=61.0",
            "FO4SF_MISSION rt=90.0 preston talk end info=0x092A -> stage 40",
        ])
        self.assertTrue(s["follow_refused_test_mode"])
        self.assertEqual(s["mission_gate"], "mission gate mode=1 started=true")
        self.assertEqual(s["min00_given_by"], "codsworth")
        self.assertEqual(s["preston_talk_end"], "preston talk end info=0x092A -> stage 40")
        self.assertFalse(s["stage40_fallback"])
        self.assertEqual((s["reloads"], s["wfc01_rescues"], s["wfc01_absent_cleared"]), (1, 1, 1))

        s_fb = make_mission.summarize(["FO4SF_MISSION rt=90.0 stage 40 by=fallback"])
        self.assertTrue(s_fb["stage40_fallback"])

    def test_2h_and_m6_codsworth_steel_mat_fix_and_talk_end(self):
        cs = read(CS)
        self.assertIn('CodsworthQuestId = 0x816', cs)
        self.assertIn('CodsworthQuestEdid = "FO4SF_Codsworth01"', cs)
        self.assertIn('CodsworthRaceEdid = "FO4SF_CodsworthRace"', cs)
        self.assertIn('CodsworthVoiceEdid = "FO4SF_CodsworthVoice"', cs)
        self.assertIn("SF.Race.Flag.AllowPcDialog", cs)
        self.assertIn("SF.VoiceType.Flag.AllowDefaultDialog", cs)
        self.assertEqual(make_mission.VOICE_DIR, "sound/voice/fo4sfmission.esm/fo4sf_codsworthvoice")

        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))
        self.assertIn('Game.GetFormFromFile(0x000800, "FO4SFMission.esm") as FO4SF_Min00Quest', c_psc)
        self.assertIn("min00.GiveFromCodsworth()", c_psc)
        self.assertIn('Trace("codsworth talk end -> min00 stage 10")', c_psc)
        self.assertIn('Trace("codsworth01 complete choices=" + choicesCount + " concord_pointed=" + pointedStr)', c_psc)

        # M6: verify dark-diffuse Metalness=0.0 .mat is upgraded to bright brushed steel (Metalness=0.85, Roughness=0.22, Tint=0.72)
        dark_mat = {
            "Objects": [
                {
                    "Components": [
                        {"Type": "BSMaterial::TextureSetID", "Index": 0, "Data": {"ID": "res:1"}},
                        {"Type": "BSMaterial::Color", "Index": 0, "Data": {"Value": {"Data": {"w": "0.0", "x": "1.0", "y": "1.0", "z": "1.0"}}}},
                    ],
                    "Edges": [{"EdgeIndex": 0, "To": "res:0", "Type": "BSComponentDB2::OuterEdge"}],
                    "ID": "res:2",
                },
                {
                    "Components": [
                        {"Type": "BSMaterial::MRTextureFile", "Index": 0, "Data": {"FileName": "Data\\textures\\handy_color.dds"}},
                        {"Type": "BSMaterial::MRTextureFile", "Index": 1, "Data": {"FileName": "Data\\textures\\handy_normal.dds"}},
                        {"Type": "BSMaterial::MRTextureFile", "Index": 3, "Data": {"FileName": "Data\\textures\\handy_rough.dds"}},
                        {"Type": "BSMaterial::TextureReplacement", "Index": 4, "Data": {"Color": {"Data": {"Value": {"Data": {"w": "1", "x": "0", "y": "0", "z": "0"}}}}, "Enabled": "true"}},
                    ],
                    "ID": "res:1",
                },
            ],
            "Summary": {
                "Layer1": {
                    "Tint": {"w": 0.0, "x": 1.0, "y": 1.0, "z": 1.0},
                    "Textures": {
                        "Metalness": {"File": "", "Replacement": {"w": 1, "x": 0.0, "y": 0.0, "z": 0.0}, "UseReplacement": True},
                        "Roughness": {"File": "Data\\textures\\handy_rough.dds", "Replacement": {"w": 1, "x": 0, "y": 0, "z": 0}, "UseReplacement": False},
                    },
                }
            },
        }
        patched = make_mission.patch_codsworth_steel_mat(json.loads(json.dumps(dark_mat)))
        self.assertAlmostEqual(patched["Summary"]["Layer1"]["Tint"]["w"], 0.72)
        self.assertAlmostEqual(patched["Summary"]["Layer1"]["Textures"]["Metalness"]["Replacement"]["x"], 0.85)
        self.assertTrue(patched["Summary"]["Layer1"]["Textures"]["Roughness"]["UseReplacement"])
        self.assertAlmostEqual(patched["Summary"]["Layer1"]["Textures"]["Roughness"]["Replacement"]["x"], 0.22)
        mr_indices = [
            c["Index"] for c in patched["Objects"][1]["Components"] if c["Type"] == "BSMaterial::MRTextureFile"
        ]
        self.assertEqual(mr_indices, [0, 1])

        s = make_mission.summarize([
            "FO4SF_MISSION rt=119.9 codsworth talk end -> min00 stage 10",
            "FO4SF_MISSION rt=120.0 codsworth01 complete choices=4 concord_pointed=true",
        ])
        self.assertTrue(s["codsworth_talk_end"])
        self.assertEqual(s["codsworth01_complete"], "codsworth01 complete choices=4 concord_pointed=true")

    def test_2k_m5_and_r4_sanctuary_bench_and_forbidden_output_guard(self):
        psc = read(PSC)
        apply_fn = function_body(psc, "Apply")
        self.assertIn('Game.GetFormFromFile(0x000817, "FO4SFMission.esm") as Quest', apply_fn)
        self.assertIn("sanctuaryQuest.StartNoWait()", apply_fn)

        s_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Sanctuary01Quest.psc"))
        self.assertIn("int BenchRefId = 0x005C50", s_psc)
        self.assertIn("int BenchBaseId = 0x0A2ECD", s_psc)
        self.assertIn('RegisterForRemoteEvent(boundBench, "OnActivate")', s_psc)
        self.assertIn('RegisterForRemoteEvent(boundBench, "OnWorkshopMode")', s_psc)
        self.assertIn('Trace("min01 bench activated -> stage 100")', s_psc)
        self.assertIn('Trace("sanctuary01 bench_activated=true ref=" + refUsed + " complete=true")', s_psc)

        card_path = os.path.join(ROOT, "docs", "testing", "sanctuary-workbench-card.md")
        self.assertTrue(os.path.isfile(card_path))
        card = read(card_path)
        for required in ("0x000817", "0x005C50", "0x0A2ECD", "0250FE", "reload mission stage=20 relocate_fails=0",
                         "min01 bench activated -> stage 100", "preston talk end info=0x092A -> stage 40"):
            self.assertIn(required, card)

        s = make_mission.summarize([
            "FO4SF_MISSION rt=299.9 min01 bench activated -> stage 100",
            "FO4SF_MISSION rt=300.0 sanctuary01 bench_activated=true ref=[ObjectReference < (04005C50)>] complete=true",
        ])
        self.assertTrue(s["min01_bench_activated"])
        self.assertTrue(s["sanctuary01_complete"].startswith("sanctuary01 bench_activated=true"))

        # R4: make_mission refuses --out inside a Git worktree or under a game folder
        with tempfile.TemporaryDirectory() as d:
            git_sub = os.path.join(d, "worktree", "sub", "out")
            os.makedirs(os.path.join(d, "worktree", ".git"))
            with self.assertRaises(SystemExit):
                make_mission.refuse_forbidden_output_dir(git_sub)

            game_sub = os.path.join(d, "game", "Data", "out")
            _write(os.path.join(d, "game", "Starfield.exe"), b"MZ")
            with self.assertRaises(SystemExit):
                make_mission.refuse_forbidden_output_dir(game_sub)

    def test_b6_b9_b12_stage_causes_preston_stage35_raider_stuck_writeoff_and_codsworth_objective_clear(self):
        cs = read(CS)
        self.assertIn("Stages = { 10, 20, 30, 35, 40, 200 }", cs)
        self.assertIn("(short)35", cs)
        self.assertIn("OnEnd == 35", cs)

        psc = read(PSC)
        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))
        s_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Sanctuary01Quest.psc"))

        # B6: every quest script logs stage <n> by=<cause> and unexpected OnStageSet logs by=other
        self.assertIn('Trace("stage " + auiStageID + " by=" + by)', psc)
        self.assertIn('Trace("codsworth01 stage " + auiStageID + " by=" + cause)', c_psc)
        self.assertIn('Trace("sanctuary01 stage " + auiStageID + " by=" + cause)', s_psc)
        apply_fn = function_body(psc, "Apply")
        self.assertIn("elseif auiStageID == 35", apply_fn)
        self.assertIn('AdvanceTo(40, "info")', apply_fn)
        self.assertIn('AdvanceTo(40, "other")', apply_fn)
        scene_end = psc[psc.index("Event Scene.OnEnd("):psc.index("EndEvent", psc.index("Event Scene.OnEnd("))]
        self.assertIn("GetStageDone(35) || st == 35", scene_end)
        self.assertIn("reason=scene_incomplete", scene_end)

        # B12: Concord route clears Codsworth's initial landing objective
        self.assertIn("Function ClearObjectiveOnConcordStart()", c_psc)
        self.assertIn("cods01.ClearObjectiveOnConcordStart()", function_body(psc, "ClearCodsworthObjectiveForConcord"))
        self.assertEqual(psc.count("ClearCodsworthObjectiveForConcord()"), 3)

        # B9: write-off stops combat and disables the raider, and rescued stuck raiders (< 2 m, no damage, 60 s) write off
        writeoff_fn = function_body(psc, "WriteOffRaider")
        self.assertIn("r.StopCombat()", writeoff_fn)
        self.assertIn("r.DisableNoWait(False)", writeoff_fn)
        wfc_fn = function_body(psc, "CheckConcordRaidersWfc01")
        self.assertIn("Wfc01StuckMoveRadius", wfc_fn)
        self.assertIn("Wfc01StuckLimit", wfc_fn)
        self.assertIn('WriteOffRaider(r, i, "stuck", raiderRescueSec[i])', wfc_fn)

        door = (-2011.14, -1697.54, 89.09)
        player = (-2015.0, -1700.0, 89.1)
        stuck_raiders = [
            {"pos": (-2029.0, -1701.0, 75.0), "target": (-2029.0, -1701.0, 88.3), "dead": False, "loaded": True,
             "absent_sec": 0.0, "cleared": False, "hp": 100.0},
        ]
        rescued, cleared = make_mission.wfc01_step(player, False, door, stuck_raiders)
        self.assertEqual((rescued, cleared), ([0], []))
        # Takes damage at t=30 -> resets stuck timer!
        for _ in range(30):
            _, cleared = make_mission.wfc01_step(player, False, door, stuck_raiders)
            self.assertEqual(cleared, [])
        stuck_raiders[0]["hp"] = 80.0
        _, cleared = make_mission.wfc01_step(player, False, door, stuck_raiders)
        self.assertEqual(cleared, [])
        # Now stays within 2 m (moves 1.2 m) with no damage for 60 s -> cleared as stuck + stopped_combat + disabled!
        stuck_raiders[0]["pos"] = (-2027.8, -1701.0, 88.3)
        for _ in range(59):
            _, cleared = make_mission.wfc01_step(player, False, door, stuck_raiders)
            self.assertEqual(cleared, [])
        _, cleared = make_mission.wfc01_step(player, False, door, stuck_raiders)
        self.assertEqual(cleared, [0])
        self.assertTrue(stuck_raiders[0]["stopped_combat"])
        self.assertTrue(stuck_raiders[0]["disabled"])
        self.assertEqual(stuck_raiders[0]["clear_reason"], "stuck")

        s_causes = make_mission.summarize([
            "FO4SF_MISSION rt=10.0 stage 10 by=info",
            "FO4SF_MISSION rt=20.0 stage 20 by=trigger",
            "FO4SF_MISSION rt=30.0 stage 30 by=trigger",
            "FO4SF_MISSION rt=40.0 stage 35 by=info",
            "FO4SF_MISSION rt=40.0 preston talk end info=0x092A -> stage 40",
            "FO4SF_MISSION rt=40.0 stage 40 by=info",
            "FO4SF_MISSION rt=41.0 stage 200 by=trigger",
            "FO4SF_MISSION rt=42.0 wfc01 raider cleared stuck id=2051 raider=0 elapsed=60.0 disabled=true",
        ])
        self.assertEqual(s_causes["stages"], [10, 20, 30, 35, 40, 200])
        self.assertEqual(s_causes["stage_causes"][35], "info")
        self.assertEqual(s_causes["stage_causes"][40], "info")
        self.assertEqual(s_causes["wfc01_stuck_cleared"], 1)


def _translate_mission_psc(src_text, fn_names, global_vars):
    """Translate selected Papyrus functions/events directly from .psc source for offline execution."""
    clean_text = re.sub(r"\{[^}]*\}", "", src_text)
    out = [
        "class _PStr(str):",
        "    def __add__(self, other): return _PStr(super().__add__(str(other)))",
        "    def __radd__(self, other): return _PStr(str(other) + str(self))",
    ]
    for name in fn_names:
        esc = re.escape(name)
        match = re.search(
            rf"(?m)^(?:[\w\[\]]+[ \t]+)?(?:Function|Event)[ \t]+{esc}\(([^)]*)\)[ \t]*\r?\n(.*?)^End(?:Function|Event)\b",
            clean_text,
            re.S,
        )
        if match is None:
            raise AssertionError(f"missing Papyrus function/event: {name}")
        args_raw, body = match.groups()
        py_args = []
        for raw_arg in args_raw.split(","):
            raw_arg = raw_arg.strip()
            if not raw_arg:
                continue
            if "=" in raw_arg:
                lhs, rhs = raw_arg.split("=", 1)
                p_name = lhs.strip().split()[-1]
                rhs = rhs.strip()
                rhs = {"true": "True", "false": "False", "none": "None"}.get(rhs.lower(), rhs)
                py_args.append(f"{p_name}={rhs}")
            else:
                py_args.append(raw_arg.split()[-1])
        fn_py_name = name.split(".")[-1]
        out.append(f"def {fn_py_name}({', '.join(py_args)}):")
        if global_vars:
            out.append("    global " + ", ".join(global_vars))
        depth = 1
        for raw_line in body.splitlines():
            line = re.sub(r'("(?:[^"\\]|\\.)*")|;.*', lambda m: m.group(1) or "", raw_line).strip()
            if not line:
                continue
            if line in ("endif", "endwhile"):
                depth -= 1
                continue
            if line.startswith(("elseif ", "else")):
                depth -= 1
            if "Trace(" in line:
                line = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', r'_PStr("\1")', line)
            line = re.sub(r"^int\s+(\w+)\s*=\s*(.+)", r"\1 = int(\2)", line)
            line = re.sub(
                r"^(?:bool|float|string|Actor|ActorValue|Activator|Message|ObjectReference|Quest|GlobalVariable|Scene|ReferenceAlias|WorldSpace|FO4SF_\w+)\s+(\w+)\s*=",
                r"\1 =",
                line,
            )
            line = re.sub(
                r"\s+as\s+(?:Actor|ActorValue|Activator|Message|ObjectReference|Quest|GlobalVariable|Scene|ReferenceAlias|WorldSpace|FO4SF_\w+)\b",
                "",
                line,
            )
            line = re.sub(r"([\w.\[\]()]+)\s+as\s+int\b", r"int(\1)", line)
            parts = re.split(r'("(?:[^"\\]|\\.)*")', line)
            for idx in range(0, len(parts), 2):
                seg = re.sub(r"\btrue\b", "True", parts[idx], flags=re.I)
                seg = re.sub(r"\bfalse\b", "False", seg, flags=re.I)
                parts[idx] = re.sub(r"!(?!=)", "not ", seg).replace("&&", "and").replace("||", "or")
            line = "".join(parts)
            if line.startswith("elseif "):
                line = "elif " + line[7:]
            if line.startswith(("if ", "elif ", "while ")) or line == "else":
                out.append("    " * depth + line + ":")
                depth += 1
            else:
                out.append("    " * depth + line)
        if len(out) == 2 or out[-1].endswith(":"):
            out.append("    " * depth + "pass")
    return "\n".join(out)


class V2MissionTalkTests(unittest.TestCase):
    """Round 8 V2: reliable 4-option Fallout-4 MessageBox talk on Codsworth (09000811 + eye-level talk proxy 09000970)
    and Preston (09000802) in the 13-plugin player bundle without FO4SFListDialogue.esm."""

    def test_v2_records_prompts_and_hold_talkability_contract(self):
        cs = read(CS)
        psc = read(PSC)
        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))

        self.assertIn('CodsworthTalkActiId = 0x970', cs)
        self.assertIn('CodsworthTalkActiEdid = "FO4SF_CodsworthTalkActi"', cs)
        self.assertIn('SFBGS006_SBShipDecoratorMarker.nif', cs)
        self.assertIn('CodsworthTalkMsgId = 0x971', cs)
        self.assertIn('PrestonTalkMsgId = 0x975', cs)
        self.assertIn('MaxTalkButtons = 4', cs)
        self.assertIn('npc.ActivateTextOverride = "Talk";', cs)
        self.assertIn('cods.ActivateTextOverride = "Talk";', cs)
        self.assertIn('cods.DefaultTemplate.Clear();', cs)
        self.assertIn('cods.TemplateActors = null;', cs)
        self.assertIn('cods.Keywords?.Clear();', cs)

        # HoldActor keeps AllowPCDialogue(True) + BlockActivation(False, False) after SetRestrained(True)
        hold_body = function_body(psc, "HoldActor")
        self.assertLess(hold_body.index("SetRestrained(True)"), hold_body.index("EnsureActorTalkable(a)"))
        talkable_body = function_body(psc, "EnsureActorTalkable")
        self.assertIn("a.AllowPCDialogue(True)", talkable_body)
        self.assertIn("a.BlockActivation(False, False)", talkable_body)

        # Codsworth01 registers OnActivate on both Codsworth (0x811) and talkProxy (0x970)
        self.assertIn('RegisterForRemoteEvent(cods, "OnActivate")', c_psc)
        self.assertIn('RegisterForRemoteEvent(talkProxy, "OnActivate")', c_psc)
        self.assertIn('Trace("codsworth talk opened stage=" + EffectiveStage())', c_psc)
        self.assertIn('Trace("codsworth choice button=" + btn)', c_psc)
        self.assertIn('Trace("preston talk opened stage=" + stage)', psc)
        self.assertIn('Trace("preston choice button=" + btn)', psc)

    def test_v2_negative_without_onactivate_handler_codsworth_press_logs_nothing(self):
        """Negative control reproducing 21 Nov 2d-r7: if DialogueMenu never opens and no OnActivate listener is wired,
        pressing E on Codsworth produces zero mission trace lines and never advances FO4SF_Codsworth01 or FO4SF_Min00."""
        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))
        # Strip OnActivate body to model pre-V2 behavior where only OnMenuOpenCloseEvent("DialogueMenu") existed
        traces = []
        stages_done = {10}
        ns = {
            "Trace": traces.append,
            "dialogueSeen": False,
            "dialogueMenuOpen": False,
            "applied": 10,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "choice1Seen": False,
            "choice2Seen": False,
            "choice3Seen": False,
            "choice4Seen": False,
            "choicesCount": 0,
            "completed": False,
            "GetStage": lambda: max(stages_done),
            "GetStageDone": lambda s: s in stages_done,
            "SetStage": stages_done.add,
            "SetObjectiveCompleted": lambda *_: None,
            "CompleteQuest": lambda: None,
            "CancelTimer": lambda *_: None,
            "Game": mock.MagicMock(),
        }
        code = _translate_mission_psc(
            c_psc,
            ("OnMenuOpenCloseEvent", "SyncProgress"),
            ("dialogueSeen", "dialogueMenuOpen", "applied", "pendingStage", "pendingStageBy",
             "choice1Seen", "choice2Seen", "choice3Seen", "choice4Seen", "choicesCount", "completed"),
        )
        exec(compile(code, "FO4SF_Codsworth01Quest.psc", "exec"), ns)
        # Native SCEN fails to open DialogueMenu on E -> SyncProgress sees nothing
        ns["SyncProgress"]()
        self.assertEqual(traces, [])
        self.assertFalse(ns["completed"])

    def test_v2_translated_codsworth_and_preston_talk_advance_first_mission_to_stage_200(self):
        """Positive translated execution: E on Codsworth (or his eye-level talkProxy at z + 1.36 m) opens the 4-option
        box, logs choices, completes FO4SF_Codsworth01 -> FO4SF_Min00 stage 10; clearing raiders -> E on Preston opens
        his 4-option box, grants 100 Credits, reaches stage 200, and starts FO4SF_Sanctuary01."""
        from types import SimpleNamespace

        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))
        m_psc = read(PSC)
        all_logs = []

        def emit(msg):
            all_logs.append(f"FO4SF_MISSION rt=12.5 {msg}")

        class _MockMsg:
            def __init__(self, name, queue, on_show=None):
                self.name = name
                self.queue = queue
                self.shown = 0
                self.on_show = on_show

            def Show(self):
                self.shown += 1
                if self.on_show is not None:
                    self.on_show()
                return self.queue.pop(0)

        class _MockRef:
            def __init__(self, label, pos=(0.0, 0.0, 0.0), disabled=False):
                self.label = label
                self.pos = list(pos)
                self.allow_pc_dial = False
                self.block_args = None
                self.restrained = False
                self.disabled = bool(disabled)
                self.scale = 1.0
                self.combat_stopped = 0
                self.spawned = []

            def __repr__(self):
                return self.label

            def AllowPCDialogue(self, flag):
                self.allow_pc_dial = bool(flag)

            def BlockActivation(self, blocked=True, hide=False):
                self.block_args = (bool(blocked), bool(hide))

            def SetRestrained(self, flag=True):
                self.restrained = bool(flag)
                return True

            def StopCombat(self):
                self.combat_stopped += 1

            def SetScale(self, s):
                self.scale = float(s)

            def EnableNoWait(self, fade=False):
                self.disabled = False
                return True

            def IsDisabled(self):
                return self.disabled

            def IsDead(self):
                return False

            def Is3DLoaded(self):
                return True

            def IsDeleted(self):
                return False

            def GetPositionX(self):
                return self.pos[0]

            def GetPositionY(self):
                return self.pos[1]

            def GetPositionZ(self):
                return self.pos[2]

            def SetPosition(self, x, y, z):
                self.pos = [float(x), float(y), float(z)]

            def PlaceAtMe(self, base_form, count=1, persistent=False, disabled=False, delete_when_able=False):
                prx = _MockRef("CodsworthTalkProxyRef", tuple(self.pos), disabled=disabled)
                self.spawned.append((base_form, prx, bool(persistent), bool(disabled), bool(delete_when_able)))
                return prx

        player = SimpleNamespace(
            IsInInterior=lambda: False,
            GetPositionX=lambda: -2345.0,
            GetPositionY=lambda: -1405.0,
            GetPositionZ=lambda: 111.8,
            AddItem=mock.MagicMock(),
        )
        # Start Codsworth unmoved first -> EnsureTalkProxy must wait until keeper places him in Sanctuary
        cods = _MockRef("CodsworthRef(09000811)", (-1146.709, 1293.837, 111.734))
        preston = _MockRef("PrestonRef(09000802)", (-2011.14, -1697.54, 89.09))
        sanctuary_q = SimpleNamespace(IsRunning=lambda: False, StartNoWait=mock.MagicMock(return_value=True))

        cods_clicks = [0, 2, 3, 3]  # Choice 1 -> Choice 3 -> Choice 4 (completes), then post-complete re-talk -> Choice 4
        c_msg_talk = _MockMsg("CodsworthTalk", cods_clicks)
        c_msg_r0 = _MockMsg("CodsworthR0", cods_clicks)
        c_msg_r1 = _MockMsg("CodsworthR1", cods_clicks)
        c_msg_r2 = _MockMsg("CodsworthR2", cods_clicks)

        preston_clicks = [0, 1, 2, 3]  # All 4 buttons exercised in sequence
        p_msg_talk = _MockMsg("PrestonTalk", preston_clicks)
        p_msg_r0 = _MockMsg("PrestonR0", preston_clicks)
        p_msg_r1 = _MockMsg("PrestonR1", preston_clicks)
        p_msg_r2 = _MockMsg("PrestonR2", preston_clicks)

        # Build translated FO4SF_Min00Quest namespace first so FO4SF_Codsworth01Quest can call min00.GiveFromCodsworth()
        m_stages = set()
        m_cur_stage = [0]
        m_regs = []

        def m_set_stage(n):
            m_stages.add(int(n))
            if int(n) > m_cur_stage[0]:
                m_cur_stage[0] = int(n)

        m_ns = {
            "Trace": emit,
            "KeeperOnly": False,
            "Preston": preston,
            "Codsworth": cods,
            "Credits": "StarfieldCredits",
            "RewardCount": 100,
            "PrestonTalkScene": None,
            "PrestonTalkMsg": p_msg_talk,
            "PrestonReply0Msg": p_msg_r0,
            "PrestonReply1Msg": p_msg_r1,
            "PrestonReply2Msg": p_msg_r2,
            "TalkUseMessageBox": None,
            "PrestonSceneCheckSeconds": 1.5,
            "PrestonSceneMaxWaitChecks": 16,
            "min00Given": False,
            "applied": 0,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "prestonFound": False,
            "talkActivated": False,
            "talkStartedAt": 0.0,
            "prestonUsedFallback": False,
            "prestonTalkLogged": False,
            "prestonTalkBoxOpen": False,
            "prestonDialogueMenuOpen": False,
            "prestonScenePending": False,
            "prestonSceneMenuOpened": False,
            "prestonScenePhase1": False,
            "prestonSceneChecks": 0,
            "talkNearSec": 5.0,
            "talkFailures": 0,
            "TalkRadius": 3.0,
            "TalkFallbackSeconds": 120.0,
            "TalkSceneTimeout": 90.0,
            "IsTestModeEnabled": lambda: True,
            "GetStage": lambda: m_cur_stage[0],
            "GetStageDone": lambda s: int(s) in m_stages,
            "SetStage": m_set_stage,
            "GetAlias": lambda *_: None,
            "SetObjectiveDisplayed": lambda *_: None,
            "SetObjectiveCompleted": lambda *_: None,
            "SetActive": lambda *_: None,
            "StartTimer": lambda *_: None,
            "CancelTimer": lambda *_: None,
            "CompleteQuest": mock.MagicMock(),
            "RegisterForRemoteEvent": lambda obj, ev: m_regs.append((obj, ev)),
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 50.0),
            "Game": SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm") else None,
            ),
        }
        m_code = _translate_mission_psc(
            m_psc,
            ("IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias", "EnsureActorTalkable",
             "HoldActor", "GiveFromCodsworth", "AdvanceTo", "Apply", "FoundPreston", "ResolvePrestonMsg",
             "RunPrestonTalk", "MarkPrestonFallback", "TalkCompleteReady", "ObjectReference.OnActivate"),
            ("min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound", "talkActivated",
             "talkStartedAt", "prestonUsedFallback", "prestonTalkLogged", "prestonTalkBoxOpen",
             "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened", "prestonScenePhase1",
             "prestonSceneChecks", "talkNearSec", "talkFailures"),
        )
        exec(compile(m_code, "FO4SF_Min00Quest.psc", "exec"), m_ns)
        min00_obj = SimpleNamespace(
            IsRunning=lambda: True,
            StartNoWait=lambda: True,
            GiveFromCodsworth=m_ns["GiveFromCodsworth"],
        )

        # Keeper holds both Codsworth & Preston -> verify SetRestrained(True) + AllowPCDialogue(True) + BlockActivation(False, False)
        m_ns["HoldActor"](cods, "codsworth", "keeper", 0.2)
        m_ns["HoldActor"](preston, "preston", "keeper", 0.3)
        self.assertTrue(cods.restrained and cods.allow_pc_dial and cods.block_args == (False, False))
        self.assertTrue(preston.restrained and preston.allow_pc_dial and preston.block_args == (False, False))

        # Build translated FO4SF_Codsworth01Quest namespace
        c_stages = {10}
        c_cur_stage = [10]
        c_regs = []

        def c_set_stage(n):
            c_stages.add(int(n))
            if int(n) > c_cur_stage[0]:
                c_cur_stage[0] = int(n)

        c_ns = {
            "Trace": emit,
            "Codsworth": cods,
            "CodsworthScene": None,
            "CodsworthTalkActi": "FO4SF_CodsworthTalkActi(09000970)",
            "CodsworthTalkMsg": c_msg_talk,
            "CodsworthReply0Msg": c_msg_r0,
            "CodsworthReply1Msg": c_msg_r1,
            "CodsworthReply2Msg": c_msg_r2,
            "TalkUseMessageBox": None,
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
            "SceneOpenCheckSeconds": 1.5,
            "SceneMaxWaitChecks": 16,
            "instanceStarted": True,
            "dialogueSeen": False,
            "dialogueMenuOpen": False,
            "talkBoxOpen": False,
            "sceneTalkPending": False,
            "sceneMenuOpened": False,
            "scenePhase1Entered": False,
            "sceneCheckTicks": 0,
            "talkProxy": None,
            "proxyLogged": False,
            "proxyLastX": 0.0,
            "proxyLastY": 0.0,
            "proxyLastZ": 0.0,
            "applied": 10,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "choice1Seen": False,
            "choice2Seen": False,
            "choice3Seen": False,
            "choice4Seen": False,
            "choicesCount": 0,
            "completed": False,
            "GetStage": lambda: c_cur_stage[0],
            "GetStageDone": lambda s: int(s) in c_stages,
            "SetStage": c_set_stage,
            "GetAlias": lambda *_: None,
            "SetObjectiveDisplayed": lambda *_: None,
            "SetObjectiveCompleted": lambda *_: None,
            "SetActive": lambda *_: None,
            "CompleteQuest": mock.MagicMock(),
            "StartTimer": lambda *_: None,
            "CancelTimer": lambda *_: None,
            "RegisterForRemoteEvent": lambda obj, ev: c_regs.append((obj, ev)),
            "Game": SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: min00_obj if (fid, plg) == (0x000800, "FO4SFMission.esm") else None,
            ),
        }
        c_code = _translate_mission_psc(
            c_psc,
            ("EffectiveStage", "ResolveCodsworth", "ResolveTalkActi", "ResolveTalkMsg", "ResolveCodsworthScene",
             "ShouldUseMessageBox", "EnsureCodsworthAlias", "BindCodsworthActivation", "EnsureTalkProxy", "AdvanceTo",
             "IsWarfareMode", "ObjectReference.OnActivate", "RunCodsworthTalk", "SyncProgress"),
            ("dialogueSeen", "dialogueMenuOpen", "talkBoxOpen", "sceneTalkPending", "sceneMenuOpened",
             "scenePhase1Entered", "sceneCheckTicks", "talkProxy", "proxyLogged", "proxyLastX", "proxyLastY",
             "proxyLastZ", "applied", "pendingStage", "pendingStageBy", "choice1Seen", "choice2Seen", "choice3Seen",
             "choice4Seen", "choicesCount", "completed"),
        )
        exec(compile(c_code, "FO4SF_Codsworth01Quest.psc", "exec"), c_ns)

        # Before keeper moves Codsworth to Sanctuary, talkProxy stays None, but Codsworth himself is already bound
        c_ns["BindCodsworthActivation"]()
        self.assertIsNone(c_ns["talkProxy"])
        self.assertIn((cods, "OnActivate"), c_regs)

        # Keeper places Codsworth at merged Sanctuary spot (-2346.709, -1406.163, 111.734) -> EnsureTalkProxy spawns hitbox at z + 1.36
        cods.SetPosition(-2346.709, -1406.163, 111.734)
        c_ns["EnsureTalkProxy"](player)
        self.assertIsNotNone(c_ns["talkProxy"])
        self.assertEqual(len(cods.spawned), 1)
        self.assertEqual(cods.spawned[0][2:], (True, True, False))  # persistent=True, initiallyDisabled=True, deleteWhenAble=False
        self.assertFalse(c_ns["talkProxy"].IsDisabled())
        self.assertAlmostEqual(c_ns["talkProxy"].scale, 1.6, places=3)
        self.assertAlmostEqual(c_ns["talkProxy"].GetPositionZ(), 111.734 + 1.36, places=3)
        self.assertIn((c_ns["talkProxy"], "OnActivate"), c_regs)

        # Simulate double-tap E while Codsworth MessageBox is open: re-entrant OnActivate must not open a second box
        c_msg_talk.on_show = lambda: (setattr(c_msg_talk, "on_show", None), c_ns["OnActivate"](cods, player))

        # Player presses E on eye-level talkProxy -> runs choices 0, 2, 3 -> completes Codsworth01 and gives Min00 stage 10!
        c_ns["OnActivate"](c_ns["talkProxy"], player)
        self.assertTrue(c_ns["completed"])
        self.assertEqual(m_cur_stage[0], 10)

        # Pressing E directly on Codsworth ACHR (09000811) after stage 100 still opens cleanly without re-giving Min00
        c_ns["OnActivate"](cods, player)
        self.assertEqual(m_cur_stage[0], 10)

        # Concord fight progresses 10 -> 20 -> 30, then player presses E on Preston at stage 30
        m_ns["AdvanceTo"](20, "Trigger")
        m_ns["AdvanceTo"](30, "Trigger")
        self.assertEqual(preston.combat_stopped, 1)

        # While Preston's MessageBox is open: re-entrant E and proximity fallback timer must both be suppressed!
        def _while_preston_box_open():
            p_msg_talk.on_show = None
            m_ns["OnActivate"](preston, player)
            self.assertFalse(m_ns["TalkCompleteReady"](30, 1.5))
            self.assertEqual(m_ns["talkNearSec"], 0.0)

        p_msg_talk.on_show = _while_preston_box_open
        m_ns["OnActivate"](preston, player)
        self.assertEqual(m_cur_stage[0], 200)
        player.AddItem.assert_called_once_with("StarfieldCredits", 100)
        sanctuary_q.StartNoWait.assert_called_once()

        s = make_mission.summarize(all_logs)
        self.assertEqual(s["codsworth_talk_opened"], 2)
        self.assertEqual(s["codsworth_choices"], [0, 2, 3, 3])
        self.assertTrue(s["codsworth_talk_end"])
        self.assertEqual(s["min00_given_by"], "codsworth")
        self.assertEqual(s["preston_talk_opened"], 1)
        self.assertEqual(s["preston_choices"], [0, 1, 2, 3])
        self.assertEqual(s["preston_talk_end"], "preston talk end info=0x092A -> stage 40")
        self.assertEqual(s["stages"], [10, 20, 30, 35, 40, 200])
        self.assertFalse(s["stage40_fallback"])
        self.assertEqual(s["reward"], 100)


class A1dRealTalkTests(unittest.TestCase):
    """Round 9 A1(d): Real voiced Starfield DialogueMenu SCEN talk on Codsworth (09000940) and Preston (09000900),
    gated by GLOB 09000979 FO4SF_MissionTalkUseMessageBox (default 0.0 = SCEN primary; 1.0 = V2 MessageBox fallback)
    with bounded 1.5 s R10 auto-fallback to MessageBox if DialogueMenu fails to open."""

    def _build_harnesses(self, glob_val=0.0, cods_scene_starts=True, preston_scene_starts=True):
        from types import SimpleNamespace

        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))
        m_psc = read(PSC)
        logs = []

        def emit(msg):
            logs.append(f"FO4SF_MISSION rt=42.0 {msg}")

        class _SceneMock:
            def __init__(self, label, starts=True):
                self.label = label
                self.starts = starts
                self.playing = False
                self.start_calls = 0
                self.force_calls = 0
                self.stop_calls = 0

            def __repr__(self):
                return self.label

            def IsPlaying(self):
                return self.playing

            def Start(self):
                self.start_calls += 1
                if self.starts:
                    self.playing = True

            def ForceStart(self):
                self.force_calls += 1
                if self.starts:
                    self.playing = True

            def Stop(self):
                self.stop_calls += 1
                self.playing = False

        class _AliasMock:
            def __init__(self):
                self.actor = None
                self.forced = []

            def GetActorRef(self):
                return self.actor

            def ForceRefTo(self, ref):
                self.actor = ref
                self.forced.append(ref)

        class _MsgMock:
            def __init__(self, queue):
                self.queue = queue
                self.shown = 0

            def Show(self):
                self.shown += 1
                return self.queue.pop(0)

        class _ActorMock:
            def __init__(self, label, pos):
                self.label = label
                self.pos = list(pos)
                self.default_activations = []

            def __repr__(self):
                return self.label

            def AllowPCDialogue(self, _flag):
                pass

            def BlockActivation(self, *_args):
                pass

            def StopCombat(self):
                pass

            def IsDisabled(self):
                return False

            def IsDead(self):
                return False

            def Is3DLoaded(self):
                return True

            def IsDeleted(self):
                return False

            def GetPositionX(self):
                return self.pos[0]

            def GetPositionY(self):
                return self.pos[1]

            def GetPositionZ(self):
                return self.pos[2]

            def SetPosition(self, x, y, z):
                self.pos = [float(x), float(y), float(z)]

            def SetScale(self, _s):
                pass

            def EnableNoWait(self, _fade=False):
                return True

            def Activate(self, activator, default_only=False):
                self.default_activations.append((activator, bool(default_only)))
                return True

            def PlaceAtMe(self, *_args):
                return _ActorMock("CodsworthTalkProxy(09000970)", tuple(self.pos))

        glob_obj = SimpleNamespace(GetValue=lambda: float(glob_val))
        player = SimpleNamespace(
            IsInInterior=lambda: False,
            GetPositionX=lambda: -2346.0,
            GetPositionY=lambda: -1406.0,
            GetPositionZ=lambda: 111.8,
            AddItem=mock.MagicMock(),
        )
        cods = _ActorMock("CodsworthRef(09000811)", (-2346.709, -1406.163, 111.734))
        preston = _ActorMock("PrestonRef(09000802)", (-2011.14, -1697.54, 89.09))
        cods_scene = _SceneMock("FO4SF_Codsworth01_Scene(09000940)", starts=cods_scene_starts)
        preston_scene = _SceneMock("FO4SF_Min00_PrestonScene(09000900)", starts=preston_scene_starts)
        cods_alias = _AliasMock()
        preston_alias = _AliasMock()
        sanctuary_q = SimpleNamespace(IsRunning=lambda: False, StartNoWait=mock.MagicMock(return_value=True))

        c_clicks = [0, 1, 2, 3]
        c_msgs = [_MsgMock(c_clicks) for _ in range(4)]
        p_clicks = [0, 1, 3]
        p_msgs = [_MsgMock(p_clicks) for _ in range(4)]

        m_stages = set()
        m_cur = [0]
        m_timers = []
        m_cancelled = []

        def m_set_stage(n):
            m_stages.add(int(n))
            if int(n) > m_cur[0]:
                m_cur[0] = int(n)

        m_ns = {
            "Trace": emit,
            "KeeperOnly": False,
            "Preston": preston,
            "Codsworth": cods,
            "Credits": "StarfieldCredits",
            "RewardCount": 100,
            "PrestonTalkScene": preston_scene,
            "PrestonTalkMsg": p_msgs[0],
            "PrestonReply0Msg": p_msgs[1],
            "PrestonReply1Msg": p_msgs[2],
            "PrestonReply2Msg": p_msgs[3],
            "TalkUseMessageBox": glob_obj,
            "PrestonSceneCheckSeconds": 1.5,
            "PrestonSceneMaxWaitChecks": 16,
            "min00Given": False,
            "applied": 0,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "prestonFound": False,
            "talkActivated": False,
            "talkStartedAt": 0.0,
            "prestonUsedFallback": False,
            "prestonTalkLogged": False,
            "prestonTalkBoxOpen": False,
            "prestonDialogueMenuOpen": False,
            "prestonScenePending": False,
            "prestonSceneMenuOpened": False,
            "prestonScenePhase1": False,
            "prestonSceneChecks": 0,
            "talkNearSec": 4.0,
            "talkFailures": 0,
            "TalkRadius": 3.0,
            "TalkFallbackSeconds": 120.0,
            "TalkSceneTimeout": 120.0,
            "IsTestModeEnabled": lambda: True,
            "GetStage": lambda: m_cur[0],
            "GetStageDone": lambda s: int(s) in m_stages,
            "SetStage": m_set_stage,
            "GetAlias": lambda idx: preston_alias if idx == 0 else None,
            "SetObjectiveDisplayed": lambda *_: None,
            "SetObjectiveCompleted": lambda *_: None,
            "SetActive": lambda *_: None,
            "StartTimer": lambda sec, tid: m_timers.append((float(sec), int(tid))),
            "CancelTimer": lambda tid: m_cancelled.append(int(tid)),
            "CompleteQuest": mock.MagicMock(),
            "RegisterForRemoteEvent": lambda *_: None,
            "RegisterForMenuOpenCloseEvent": lambda *_: None,
            "Utility": SimpleNamespace(GetCurrentRealTime=lambda: 80.0),
            "Game": SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: (
                    sanctuary_q if (fid, plg) == (0x000817, "FO4SFMission.esm")
                    else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                    else None
                ),
            ),
        }
        m_code = _translate_mission_psc(
            m_psc,
            ("IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias", "GiveFromCodsworth",
             "AdvanceTo", "OnStageSet", "Apply", "FoundPreston", "ResolvePrestonMsg", "RunPrestonTalk",
             "FallbackPrestonToMessageBox", "CheckPrestonSceneOpen", "OnMenuOpenCloseEvent",
             "Scene.OnBegin", "Scene.OnPhaseBegin", "Scene.OnEnd", "MarkPrestonFallback",
             "TalkCompleteReady", "ObjectReference.OnActivate"),
            ("min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound", "talkActivated",
             "talkStartedAt", "prestonUsedFallback", "prestonTalkLogged", "prestonTalkBoxOpen",
             "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened", "prestonScenePhase1",
             "prestonSceneChecks", "talkNearSec", "talkFailures"),
        )
        exec(compile(m_code, "FO4SF_Min00Quest.psc", "exec"), m_ns)

        min00_obj = SimpleNamespace(
            IsRunning=lambda: True,
            StartNoWait=lambda: True,
            GiveFromCodsworth=m_ns["GiveFromCodsworth"],
        )

        c_stages = {10}
        c_cur = [10]
        c_timers = []
        c_cancelled = []

        def c_set_stage(n):
            c_stages.add(int(n))
            if int(n) > c_cur[0]:
                c_cur[0] = int(n)

        c_ns = {
            "Trace": emit,
            "Codsworth": cods,
            "CodsworthScene": cods_scene,
            "CodsworthTalkActi": "FO4SF_CodsworthTalkActi(09000970)",
            "CodsworthTalkMsg": c_msgs[0],
            "CodsworthReply0Msg": c_msgs[1],
            "CodsworthReply1Msg": c_msgs[2],
            "CodsworthReply2Msg": c_msgs[3],
            "TalkUseMessageBox": glob_obj,
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
            "SceneOpenCheckSeconds": 1.5,
            "SceneMaxWaitChecks": 16,
            "instanceStarted": True,
            "dialogueSeen": False,
            "dialogueMenuOpen": False,
            "talkBoxOpen": False,
            "sceneTalkPending": False,
            "sceneMenuOpened": False,
            "scenePhase1Entered": False,
            "sceneCheckTicks": 0,
            "talkProxy": None,
            "proxyLogged": False,
            "proxyLastX": 0.0,
            "proxyLastY": 0.0,
            "proxyLastZ": 0.0,
            "applied": 10,
            "pendingStage": -1,
            "pendingStageBy": "other",
            "choice1Seen": False,
            "choice2Seen": False,
            "choice3Seen": False,
            "choice4Seen": False,
            "choicesCount": 0,
            "completed": False,
            "GetStage": lambda: c_cur[0],
            "GetStageDone": lambda s: int(s) in c_stages,
            "SetStage": c_set_stage,
            "GetAlias": lambda idx: cods_alias if idx == 0 else None,
            "SetObjectiveDisplayed": lambda *_: None,
            "SetObjectiveCompleted": lambda *_: None,
            "SetActive": lambda *_: None,
            "CompleteQuest": mock.MagicMock(),
            "StartTimer": lambda sec, tid: c_timers.append((float(sec), int(tid))),
            "CancelTimer": lambda tid: c_cancelled.append(int(tid)),
            "RegisterForRemoteEvent": lambda *_: None,
            "RegisterForMenuOpenCloseEvent": lambda *_: None,
            "Game": SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: (
                    min00_obj if (fid, plg) == (0x000800, "FO4SFMission.esm")
                    else cods_scene if (fid, plg) == (0x000940, "FO4SFMission.esm")
                    else glob_obj if (fid, plg) == (0x000979, "FO4SFMission.esm")
                    else None
                ),
            ),
        }
        c_code = _translate_mission_psc(
            c_psc,
            ("EffectiveStage", "ResolveCodsworth", "ResolveTalkActi", "ResolveTalkMsg", "ResolveCodsworthScene",
             "ShouldUseMessageBox", "EnsureCodsworthAlias", "BindCodsworthActivation", "EnsureTalkProxy", "AdvanceTo",
             "IsWarfareMode", "OnMenuOpenCloseEvent", "Scene.OnBegin", "Scene.OnPhaseBegin", "Scene.OnEnd",
             "CheckCodsworthSceneOpen", "ObjectReference.OnActivate", "RunCodsworthTalk", "OnStageSet", "SyncProgress"),
            ("dialogueSeen", "dialogueMenuOpen", "talkBoxOpen", "sceneTalkPending", "sceneMenuOpened",
             "scenePhase1Entered", "sceneCheckTicks", "talkProxy", "proxyLogged", "proxyLastX", "proxyLastY",
             "proxyLastZ", "applied", "pendingStage", "pendingStageBy", "choice1Seen", "choice2Seen", "choice3Seen",
             "choice4Seen", "choicesCount", "completed"),
        )
        exec(compile(c_code, "FO4SF_Codsworth01Quest.psc", "exec"), c_ns)

        return SimpleNamespace(
            logs=logs, player=player, cods=cods, preston=preston,
            cods_scene=cods_scene, preston_scene=preston_scene,
            cods_alias=cods_alias, preston_alias=preston_alias,
            c_msgs=c_msgs, p_msgs=p_msgs, sanctuary_q=sanctuary_q,
            c_ns=c_ns, m_ns=m_ns, c_cur=c_cur, m_cur=m_cur,
            c_set_stage=c_set_stage, m_set_stage=m_set_stage,
            c_timers=c_timers, m_timers=m_timers,
            c_cancelled=c_cancelled, m_cancelled=m_cancelled,
        )

    def test_a1d_scene_devt_glob_and_trot_contract(self):
        cs = read(CS)
        c_psc = read(os.path.join(ROOT, "scripts", "mission", "FO4SF_Codsworth01Quest.psc"))
        m_psc = read(PSC)

        self.assertIn("MissionTalkUseMessageBoxGlobId = 0x979", cs)
        self.assertIn('MissionTalkUseMessageBoxGlobEdid = "FO4SF_MissionTalkUseMessageBox"', cs)
        self.assertIn("DEVT = true", cs)
        self.assertIn("GlobalIsZero(new FormKey(modKey, MissionTalkUseMessageBoxGlobId))", cs)
        self.assertIn("new SF.DialogResponseTROT", cs)
        self.assertIn('"--preston-voice"', cs)
        self.assertIn('CodsworthProp("CodsworthScene", new FormKey(modKey, CodsworthSceneId))', cs)
        self.assertIn('CodsworthProp("TalkUseMessageBox", new FormKey(modKey, MissionTalkUseMessageBoxGlobId))', cs)
        self.assertIn('Obj("TalkUseMessageBox", new FormKey(modKey, MissionTalkUseMessageBoxGlobId))', cs)
        self.assertEqual(make_mission.PRESTON_VOICE_DIR, "sound/voice/fo4sfmission.esm/genericmaleeventoned")
        self.assertEqual(make_mission.FIRST_PRESTON_WEM, 0x00F4C201)

        # Timer 2 in FO4SF_Min00Quest.psc remains exclusively KeepCodsworth(); Preston's 1.5 s check uses Timer 3
        self.assertNotIn("CancelTimer(2)", m_psc)
        self.assertIn("StartTimer(PrestonSceneCheckSeconds, 3)", m_psc)
        self.assertIn("CancelTimer(3)", m_psc)
        self.assertIn("StartTimer(SceneOpenCheckSeconds, 2)", c_psc)

    def test_a1d_primary_voiced_dialoguemenu_route_completes_codsworth_and_preston_without_messagebox(self):
        h = self._build_harnesses(glob_val=0.0)
        h.c_ns["BindCodsworthActivation"]()
        self.assertEqual(h.cods_alias.actor, h.cods)
        self.assertIsNotNone(h.c_ns["talkProxy"])

        # Press E on Codsworth's eye-height talkProxy (09000970) -> starts real SCEN 09000940 (no MessageBox!)
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)
        self.assertEqual(h.cods_scene.start_calls, 1)
        self.assertTrue(h.cods_scene.IsPlaying())
        self.assertEqual(h.c_timers[-1], (1.5, 2))
        self.assertEqual(sum(m.shown for m in h.c_msgs), 0)

        h.c_ns["OnBegin"](h.cods_scene)
        h.c_ns["OnPhaseBegin"](h.cods_scene, 1)
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertIn(2, h.c_cancelled)

        # Player picks all 4 choices inside Starfield DialogueMenu -> INFO OnEnd stages 20, 30, 40, 100
        for st in (20, 30, 40, 100):
            h.c_set_stage(st)
            h.c_ns["OnStageSet"](st, 0)
        h.cods_scene.playing = False
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        h.c_ns["OnEnd"](h.cods_scene)

        self.assertTrue(h.c_ns["completed"])
        self.assertEqual(h.m_cur[0], 10)
        self.assertEqual(sum(m.shown for m in h.c_msgs), 0)

        # Post-stage-100 E on talkProxy forwards default activation to Codsworth ACHR for voiced Hello barks
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)
        self.assertEqual(h.cods.default_activations, [(h.player, True)])

        # Concord raiders cleared -> stage 30 -> press E on Preston (09000802) -> starts real SCEN 09000900
        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.m_ns["OnActivate"](h.preston, h.player)
        self.assertEqual(h.preston_alias.actor, h.preston)
        self.assertEqual(h.preston_scene.start_calls, 1)
        self.assertEqual(h.m_timers[-1], (1.5, 3))
        self.assertEqual(sum(m.shown for m in h.p_msgs), 0)

        h.m_ns["OnBegin"](h.preston_scene)
        h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertIn(3, h.m_cancelled)
        self.assertFalse(h.m_ns["TalkCompleteReady"](30, 1.2))
        self.assertEqual(h.m_ns["talkNearSec"], 0.0)

        # Final Preston INFO 0x092A sets stage 35 -> advances to 40 (100 Credits) -> OnEnd completes to 200 & starts Sanctuary01
        h.m_set_stage(35)
        h.m_ns["OnStageSet"](35, 0)
        h.preston_scene.playing = False
        h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", False)
        h.m_ns["OnEnd"](h.preston_scene)

        self.assertEqual(h.m_cur[0], 200)
        h.player.AddItem.assert_called_once_with("StarfieldCredits", 100)
        h.sanctuary_q.StartNoWait.assert_called_once()
        self.assertEqual(sum(m.shown for m in h.p_msgs), 0)

        s = make_mission.summarize(h.logs)
        self.assertEqual(s["codsworth_scene_requested"], 1)
        self.assertEqual(s["codsworth_dialogue_menu_opened"], 1)
        self.assertEqual(s["codsworth_talk_fallbacks"], [])
        self.assertEqual(s["codsworth_talk_opened"], 0)
        self.assertTrue(s["codsworth_talk_end"])
        self.assertEqual(s["preston_scene_requested"], 1)
        self.assertEqual(s["preston_dialogue_menu_opened"], 1)
        self.assertEqual(s["preston_talk_fallbacks"], [])
        self.assertEqual(s["preston_talk_opened"], 0)
        self.assertEqual(s["stages"], [10, 20, 30, 35, 40, 200])
        self.assertEqual(s["reward"], 100)

    def test_a1d_auto_fallback_to_messagebox_when_dialoguemenu_fails_to_open_in_1p5s(self):
        # Codsworth scene fails to start (IsPlaying == False at 1.5 s); Preston enters Phase 1 but DialogueMenu never opens
        h = self._build_harnesses(glob_val=0.0, cods_scene_starts=False, preston_scene_starts=True)
        h.c_ns["BindCodsworthActivation"]()

        h.c_ns["OnActivate"](h.cods, h.player)
        self.assertEqual(h.cods_scene.start_calls, 1)
        self.assertEqual(h.cods_scene.force_calls, 1)
        self.assertFalse(h.c_ns["completed"])
        # 1.5 s Timer 2 check sees !dialogueMenuOpen and !scn.IsPlaying() -> MessageBox fallback completes Codsworth01!
        h.c_ns["CheckCodsworthSceneOpen"]()
        self.assertTrue(h.c_ns["completed"])
        self.assertEqual(h.m_cur[0], 10)
        self.assertGreater(sum(m.shown for m in h.c_msgs), 0)

        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.m_ns["OnActivate"](h.preston, h.player)
        h.m_ns["OnBegin"](h.preston_scene)
        h.m_ns["OnPhaseBegin"](h.preston_scene, 1)
        # 1.5 s Timer 3 check after Phase 1 entered with !prestonDialogueMenuOpen -> stops scene & opens MessageBox!
        h.m_ns["CheckPrestonSceneOpen"]()
        self.assertEqual(h.preston_scene.stop_calls, 1)
        self.assertEqual(h.m_cur[0], 200)
        self.assertGreater(sum(m.shown for m in h.p_msgs), 0)

        s = make_mission.summarize(h.logs)
        self.assertEqual(s["codsworth_talk_fallbacks"], ["scene_inactive"])
        self.assertEqual(s["preston_talk_fallbacks"], ["dialogue_menu_timeout"])
        self.assertEqual(s["codsworth_talk_opened"], 1)
        self.assertEqual(s["preston_talk_opened"], 1)

    def test_a1d_glob_toggle_1_forces_messagebox_fallback_immediately(self):
        h = self._build_harnesses(glob_val=1.0)
        h.c_ns["BindCodsworthActivation"]()
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)
        self.assertEqual(h.cods_scene.start_calls, 0)
        self.assertTrue(h.c_ns["completed"])
        self.assertEqual(h.m_cur[0], 10)

        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.m_ns["OnActivate"](h.preston, h.player)
        self.assertEqual(h.preston_scene.start_calls, 0)
        self.assertEqual(h.m_cur[0], 200)

        s = make_mission.summarize(h.logs)
        self.assertEqual(s["codsworth_talk_fallbacks"], ["glob"])
        self.assertEqual(s["preston_talk_fallbacks"], ["glob"])

    def test_a1d_multi_clip_voice_staging_and_cross_os_path_basename(self):
        import posixpath
        import struct
        import wave
        from types import SimpleNamespace

        # Cross-OS path_basename check under posixpath simulation
        win_tool_sample = "X" + ":\\Tools\\PapyrusCompiler.exe"
        with mock.patch.object(os.path, "basename", side_effect=posixpath.basename):
            self.assertEqual(make_mission.path_basename(win_tool_sample), "PapyrusCompiler.exe")
            self.assertEqual(make_mission.path_basename("/opt/tools/xwmaencode"), "xwmaencode")
            self.assertEqual(make_mission.path_basename(r"sound\voice\fallout4.esm\npcmprestongarvey\000ca9cc_1.fuz"),
                             "000ca9cc_1.fuz")

        def make_fuz_bytes():
            return b"FUZE" + struct.pack("<II", 1, 4) + b"LIP!" + b"RIFF\x04\x00\x00\x00XWMA"

        entries = []
        for fid, rnums in make_mission.MQ102_CODSWORTH_CLIP_SPECS:
            for rn in rnums:
                entries.append(f"sound\\voice\\fallout4.esm\\robotmrhandy\\{fid:08x}_{rn}.fuz")
        for fid, rnums in make_mission.PRESTON_SCENE_CLIP_SPECS:
            for rn in rnums:
                entries.append(f"sound\\voice\\fallout4.esm\\npcmprestongarvey\\{fid:08x}_{rn}.fuz")

        class _FakeBa2:
            def __init__(self, _path):
                self.entries = [SimpleNamespace(name=n) for n in entries]

            def read(self, _name):
                return make_fuz_bytes()

        with tempfile.TemporaryDirectory() as d:
            fo4_esm = os.path.join(d, "Fallout4.esm")
            voices_ba2 = os.path.join(d, "Fallout4 - Voices.ba2")
            xwm_exe = os.path.join(d, "xwmaencode.exe")
            wwise_exe = os.path.join(d, "WwiseConsole.exe")
            for p in (fo4_esm, voices_ba2, xwm_exe, wwise_exe):
                _write(p, b"stub")

            def fake_audio_run(cmd, cwd=None):
                exe = make_mission.path_basename(cmd[0]).lower()
                if "xwmaencode" in exe:
                    wav_out = cmd[2]
                    os.makedirs(os.path.dirname(wav_out), exist_ok=True)
                    with wave.open(wav_out, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(b"\x00\x00" * 36000)  # 1.500 s
                elif "wwiseconsole" in exe and "convert-external-source" in cmd:
                    wsources = cmd[cmd.index("--source-file") + 1]
                    wem_out = cmd[cmd.index("--output") + 1]
                    src_txt = read(wsources)
                    for m in re.finditer(r'Path="([^"]+)\.wav"', src_txt):
                        _write(os.path.join(wem_out, "Windows", m.group(1) + ".wem"), b"WEM-" + m.group(1).encode())
                return ""

            args = SimpleNamespace(
                fo4=fo4_esm, fo4_voices=voices_ba2, xwmaencode=xwm_exe, wwise_console=wwise_exe,
                codsworth=True, alias=True,
            )
            data_dir = os.path.join(d, "out", "Data")
            tmp_dir = os.path.join(d, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            with mock.patch("fo4sf.ba2.Ba2", _FakeBa2), \
                 mock.patch.object(make_mission, "run", side_effect=fake_audio_run), \
                 mock.patch.object(os.path, "basename", side_effect=posixpath.basename):
                copied, auto_hello, mq_json, pr_json = make_mission.stage_mq102_and_hello_voices(
                    args, {"codsworth_hellos": []}, data_dir, tmp_dir, True
                )

            self.assertIsNone(auto_hello)
            self.assertEqual(len(copied), 15)  # 8 Codsworth MQ102 clips + 7 Preston scene clips
            mq_spec = json.loads(read(mq_json))
            pr_spec = json.loads(read(pr_json))
            self.assertEqual(mq_spec["greeting_wem"], "00f4c101")
            self.assertEqual(mq_spec["reply_wems"], ["00f4c102", "00f4c103", "00f4c104", "00f4c105"])
            self.assertEqual([c["wem"] for c in mq_spec["greeting_clips"]], ["00f4c101", "00f4c106", "00f4c107"])
            self.assertAlmostEqual(mq_spec["greeting_clips"][0]["duration"], 1.5, places=3)
            self.assertEqual([c["wem"] for c in mq_spec["reply_clips"][1]], ["00f4c103", "00f4c108"])

            self.assertEqual(pr_spec["greeting_wem"], "00f4c201")
            self.assertEqual(pr_spec["reply_wems"], ["00f4c202", "00f4c203", "00f4c204"])
            self.assertEqual([c["wem"] for c in pr_spec["reply_clips"][0]], ["00f4c202", "00f4c205", "00f4c206"])
            self.assertEqual([c["wem"] for c in pr_spec["reply_clips"][1]], ["00f4c203", "00f4c207"])

    def test_a1d_phase1_begin_resets_1p5s_timer_avoiding_stale_phase0_tick_race(self):
        h = self._build_harnesses(glob_val=0.0)
        h.c_ns["BindCodsworthActivation"]()

        # Codsworth Phase 0 plays across two 1.5 s ticks -> OnPhaseBegin(1) must CancelTimer(2) + StartTimer(1.5, 2)
        h.c_ns["OnActivate"](h.cods, h.player)
        h.c_ns["OnBegin"](h.cods_scene)
        h.c_ns["CheckCodsworthSceneOpen"]()
        h.c_ns["CheckCodsworthSceneOpen"]()
        timers_before_c = len(h.c_timers)
        cancelled_before_c = len(h.c_cancelled)
        h.c_ns["OnPhaseBegin"](h.cods_scene, 1)
        self.assertEqual(h.c_cancelled[cancelled_before_c:], [2])
        self.assertEqual(h.c_timers[timers_before_c:], [(1.5, 2)])
        # Scaleform opens DialogueMenu inside that fresh 1.5 s window -> scene is NOT stopped!
        h.c_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertEqual(h.cods_scene.stop_calls, 0)
        self.assertEqual(sum(m.shown for m in h.c_msgs), 0)

        # Preston Phase 0 plays across two 1.5 s ticks -> OnPhaseBegin(1) must CancelTimer(3) + StartTimer(1.5, 3)
        h.m_ns["AdvanceTo"](10, "Trigger")
        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.m_ns["OnActivate"](h.preston, h.player)
        h.m_ns["OnBegin"](h.preston_scene)
        h.m_ns["CheckPrestonSceneOpen"]()
        h.m_ns["CheckPrestonSceneOpen"]()
        timers_before_m = len(h.m_timers)
        cancelled_before_m = len(h.m_cancelled)
        h.m_ns["OnPhaseBegin"](h.preston_scene, 1)
        self.assertEqual(h.m_cancelled[cancelled_before_m:], [3])
        self.assertNotIn(2, h.m_cancelled)
        self.assertEqual(h.m_timers[timers_before_m:], [(1.5, 3)])
        h.m_ns["OnMenuOpenCloseEvent"]("DialogueMenu", True)
        self.assertEqual(h.preston_scene.stop_calls, 0)
        self.assertEqual(sum(m.shown for m in h.p_msgs), 0)

    def test_a1d_devt_native_scene_begin_without_onactivate_arms_1p5s_fallback(self):
        h = self._build_harnesses(glob_val=0.0)
        h.c_ns["BindCodsworthActivation"]()

        # C++ DEVT=true starts Codsworth 09000940 natively without firing ObjectReference.OnActivate
        h.cods_scene.playing = True
        h.c_ns["OnBegin"](h.cods_scene)
        self.assertTrue(h.c_ns["sceneTalkPending"])
        self.assertEqual(h.c_timers[-1], (1.5, 2))
        self.assertTrue(any("codsworth scene talk requested" in ln and "via=devt" in ln for ln in h.logs))
        # Scene ends incomplete before DialogueMenu ever opens -> R10 MessageBox fallback runs and completes stage 100!
        h.cods_scene.playing = False
        h.c_ns["OnEnd"](h.cods_scene)
        self.assertTrue(h.c_ns["completed"])
        self.assertEqual(h.m_cur[0], 10)

        # C++ DEVT=true starts Preston 09000900 natively at stage 30 without firing ObjectReference.OnActivate
        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        h.preston_scene.playing = True
        h.m_ns["OnBegin"](h.preston_scene)
        self.assertTrue(h.m_ns["prestonScenePending"])
        self.assertEqual(h.m_timers[-1], (1.5, 3))
        h.m_ns["OnPhaseBegin"](h.preston_scene, 1)
        # DialogueMenu fails to open within the reset 1.5 s Phase-1 window -> R10 MessageBox fallback completes to 200!
        h.m_ns["CheckPrestonSceneOpen"]()
        self.assertEqual(h.preston_scene.stop_calls, 1)
        self.assertEqual(h.m_cur[0], 200)

        s = make_mission.summarize(h.logs)
        self.assertEqual(s["codsworth_scene_requested"], 1)
        self.assertEqual(s["preston_scene_requested"], 1)
        self.assertEqual(s["codsworth_talk_fallbacks"], ["scene_incomplete"])
        self.assertEqual(s["preston_talk_fallbacks"], ["dialogue_menu_timeout"])


class A1aInGame2eBreakTests(unittest.TestCase):
    """Round 9 A1(a): regressions for in-game candidate-2e breaks B1 (Preston stage=0 / setstage),
    B2 (FO4SF_MapMarkersHop 100008F4 interior raider misplacement + rescue), and B4 (Codsworth stage 100 completion +
    Min00 stage 10 handover + HUD objective)."""

    def test_b1_and_b4_binary_quest_flags_qsdt_and_optional_aliases_contract(self):
        cs = read(CS)
        self.assertIn("st.LogEntries.Add(new SF.QuestLogEntry", cs)
        self.assertIn("q.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null)", cs)
        self.assertIn("cwq.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null)", cs)
        self.assertIn("sq.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null)", cs)
        self.assertIn("(al.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional)", cs)
        self.assertIn("(cal0.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional)", cs)
        self.assertIn("Flags = (SF.QuestObjective.Flag)0", cs)

    def test_b1_preston_talk_opens_when_cpp_getstage_lags_at_zero_and_console_setstage_completes(self):
        from types import SimpleNamespace

        h = A1dRealTalkTests()._build_harnesses(glob_val=0.0)
        # Freeze C++ GetStage() at 0 and GetStageDone() at False to reproduce candidate-2e's non-running QUST symptom
        h.m_ns["GetStage"] = lambda: 0
        h.m_ns["GetStageDone"] = lambda _s: False
        h.m_ns["SetStage"] = lambda _n: None

        # Also instantiate a KeeperOnly=True quest (FO4SF_CodsworthKeeper 09000814) sharing Preston ACHR 09000802
        keeper_logs = []
        keeper_ns = dict(h.m_ns)
        keeper_ns["KeeperOnly"] = True
        keeper_ns["Trace"] = lambda m: keeper_logs.append(str(m))
        m_psc = read(PSC)
        keeper_code = _translate_mission_psc(
            m_psc,
            ("IsWarfareMode", "ShouldUseMessageBox", "EffectiveStage", "EnsurePrestonAlias", "GiveFromCodsworth",
             "AdvanceTo", "OnStageSet", "Apply", "FoundPreston", "ResolvePrestonMsg", "RunPrestonTalk",
             "ObjectReference.OnActivate"),
            ("min00Given", "applied", "pendingStage", "pendingStageBy", "prestonFound", "talkActivated",
             "talkStartedAt", "prestonUsedFallback", "prestonTalkLogged", "prestonTalkBoxOpen",
             "prestonDialogueMenuOpen", "prestonScenePending", "prestonSceneMenuOpened", "prestonScenePhase1",
             "prestonSceneChecks", "talkNearSec", "talkFailures"),
        )
        exec(compile(keeper_code, "FO4SF_Min00Quest.psc", "exec"), keeper_ns)

        # Progress mission through Concord fight 10 -> 20 -> 30 while C++ GetStage() remains 0
        h.m_ns["AdvanceTo"](10, "Trigger")
        h.m_ns["AdvanceTo"](20, "Trigger")
        h.m_ns["AdvanceTo"](30, "Trigger")
        self.assertEqual(h.m_ns["EffectiveStage"](), 30)

        # KeeperOnly must ignore Preston OnActivate, GiveFromCodsworth, and OnStageSet completely
        keeper_ns["OnActivate"](h.preston, h.player)
        keeper_ns["GiveFromCodsworth"]()
        keeper_ns["OnStageSet"](40, 0)
        self.assertEqual(keeper_logs, [])

        # Mission instance OnActivate logs stage 30 (NEVER stage 0) and starts PrestonTalkScene 09000900!
        h.m_ns["OnActivate"](h.preston, h.player)
        self.assertTrue(any("preston activated at stage 30" in ln for ln in h.logs))
        self.assertFalse(any("preston activated at stage 0" in ln for ln in h.logs))
        self.assertEqual(h.preston_scene.start_calls, 1)

        # Scene enters Phase 1 without opening DialogueMenu -> 1.5 s fallback opens MessageBox and completes 35->40->200!
        h.m_ns["OnBegin"](h.preston_scene)
        h.m_ns["OnPhaseBegin"](h.preston_scene, 1)
        h.m_ns["CheckPrestonSceneOpen"]()
        self.assertEqual(h.m_ns["EffectiveStage"](), 200)
        h.player.AddItem.assert_called_once_with("StarfieldCredits", 100)
        h.sanctuary_q.StartNoWait.assert_called_once()

        # Verify console `setstage 09000800 35` and `setstage 09000800 40` immediately complete when scene is idle
        for console_stage in (35, 40):
            h2 = A1dRealTalkTests()._build_harnesses(glob_val=0.0)
            h2.m_ns["AdvanceTo"](10, "Trigger")
            h2.m_ns["AdvanceTo"](20, "Trigger")
            h2.m_ns["AdvanceTo"](30, "Trigger")
            h2.m_set_stage(console_stage)
            h2.m_ns["OnStageSet"](console_stage, 0)
            self.assertEqual(h2.m_ns["EffectiveStage"](), 200, f"console setstage {console_stage} did not reach 200")
            h2.player.AddItem.assert_called_once_with("StarfieldCredits", 100)
            h2.sanctuary_q.StartNoWait.assert_called_once()
            h2.m_ns["CompleteQuest"].assert_called_once()

    def test_b2_mapmarkers_interior_hop_never_misplaces_concord_raiders_and_wfc01_rescues_interior_raiders(self):
        from types import SimpleNamespace

        m_psc = read(PSC)
        logs = []
        fo4_world = SimpleNamespace(name="FO4_World(05000805)")

        class _WorldActor:
            def __init__(self, label, pos, world, interior=False):
                self.label = label
                self.pos = [float(pos[0]), float(pos[1]), float(pos[2])]
                self.world = world
                self.interior = interior
                self.cell = "Cell<FO4SF_MapMarkersHop(100008F4)>" if interior else "Cell<(05000806)>"
                self.moveto_calls = 0
                self.on_query = None

            def __repr__(self):
                return self.label

            def GetPositionX(self):
                return self.pos[0]

            def GetPositionY(self):
                return self.pos[1]

            def GetPositionZ(self):
                return self.pos[2]

            def SetPosition(self, x, y, z):
                self.pos = [float(x), float(y), float(z)]

            def IsInInterior(self):
                if self.on_query is not None:
                    self.on_query()
                return self.interior

            def GetWorldSpace(self):
                if self.on_query is not None:
                    self.on_query()
                return self.world

            def GetParentCell(self):
                return self.cell

            def GetDistance(self, other):
                if self.interior != other.interior or self.world != other.world:
                    return 3.4e38
                return math.dist(self.pos, other.pos)

            def MoveTo(self, ref, dx=0.0, dy=0.0, dz=0.0, *_args):
                self.moveto_calls += 1
                self.world = ref.world
                self.interior = ref.interior
                self.cell = ref.cell
                self.pos = [ref.pos[0] + float(dx), ref.pos[1] + float(dy), ref.pos[2] + float(dz)]

            def EvaluatePackage(self):
                pass

            def GetCombatState(self):
                return 0

            def IsDead(self):
                return False

            def IsDisabled(self):
                return False

            def Is3DLoaded(self):
                return not self.interior and self.world == fo4_world

            def SetRestrained(self, _v):
                return True

            def AllowPCDialogue(self, _v):
                pass

            def BlockActivation(self, *_a):
                pass

            def StopCombat(self):
                pass

            def DisableNoWait(self, _fade=False):
                pass

            def GetFormID(self):
                return 0x09000803

            def GetValue(self, _av):
                return 100.0

        class _PArray(list):
            @property
            def Length(self):
                return len(self)

        # Exact unmerged editor coordinates from candidate-2e fo4sf_mission.0.log
        raider_locals = [
            (-829.180054, 1001.739990, 88.330002),
            (-841.359985, 1018.880005, 88.190002),
            (-849.840027, 1026.910034, 88.110001),
            (-847.250000, 1041.530029, 88.150002),
            (-850.820007, 1009.469971, 88.220001),
        ]
        raiders = _PArray([_WorldActor(f"Raider{i}", p, world="BaseWorld") for i, p in enumerate(raider_locals)])
        preston = _WorldActor("Preston", (-811.14, 1002.46, 89.09), world=fo4_world)
        player = _WorldActor("Player", (-2467.78, -1406.92, 127.45), world=fo4_world, interior=False)

        ns = {
            "_PArray": _PArray,
            "Trace": lambda m: logs.append(str(m)),
            "Preston": preston,
            "Raiders": raiders,
            "MergeOffsetX": -1200.0,
            "MergeOffsetY": -2700.0,
            "PrestonLocalX": -811.14,
            "PrestonLocalY": 1002.46,
            "PrestonLocalZ": 89.09,
            "RelocateRadius": 800.0,
            "RelocateGap": 1500.0,
            "PlaceRadius": 300.0,
            "HoldRadius": 25.0,
            "HeldRadius": 3.0,
            "Wfc01CheckRadius": 150.0,
            "Wfc01DoorRadius": 100.0,
            "Wfc01SubterraneanDrop": 8.0,
            "Wfc01MaxDrift": 140.0,
            "Wfc01AbsentDistance": 250.0,
            "Wfc01AbsentLimit": 60.0,
            "Wfc01StuckMoveRadius": 2.0,
            "Wfc01StuckLimit": 60.0,
            "relocateFails": 0,
            "prestonFollow": False,
            "prestonOff": -1.0,
            "prestonMoves": 0,
            "prestonHeld": False,
            "prestonHolds": 0,
            "prestonState": "none",
            "raiderTargetX": None,
            "raiderTargetY": None,
            "raiderTargetZ": None,
            "raiderAbsentSec": None,
            "raiderCleared": None,
            "raiderRescued": None,
            "raiderRescueSec": None,
            "raiderRescueX": None,
            "raiderRescueY": None,
            "raiderRescueZ": None,
            "raiderRescueHp": None,
            "healthAvCache": "HealthAV",
            "Math": SimpleNamespace(Sqrt=math.sqrt),
            "IsTestModeEnabled": lambda: False,
            "Debug": SimpleNamespace(Notification=lambda *_: None),
            "Game": SimpleNamespace(GetFormFromFile=lambda *_: "HealthAV"),
        }
        code = _translate_mission_psc(
            m_psc,
            ("IsCommonwealthExterior", "IsPlayerStableAt", "SpotOff", "HeldState", "HoldDue", "EnsureActorTalkable",
             "HoldActor", "HoldPreston", "PlaceAt", "PlacePreston", "MoveOver", "Relocate", "GetRaiderHealth",
             "WriteOffRaider", "CheckConcordRaidersWfc01"),
            ("relocateFails", "prestonFollow", "prestonOff", "prestonMoves", "prestonHeld", "prestonHolds",
             "prestonState", "raiderTargetX", "raiderTargetY", "raiderTargetZ", "raiderAbsentSec", "raiderCleared",
             "raiderRescued", "raiderRescueSec", "raiderRescueX", "raiderRescueY", "raiderRescueZ",
             "raiderRescueHp", "healthAvCache"),
        )
        # Translate InitRaiderTracking array allocations for Python
        init_src = function_body(m_psc, "InitRaiderTracking")
        init_src = re.sub(r"new (?:float|bool)\[count\]", "_PArray([0] * count)", init_src)
        exec(compile(code + "\n" + _translate_mission_psc(init_src + "\nEndFunction\n", ("InitRaiderTracking",), (
            "raiderTargetX", "raiderTargetY", "raiderTargetZ", "raiderAbsentSec", "raiderCleared",
            "raiderRescued", "raiderRescueSec", "raiderRescueX", "raiderRescueY", "raiderRescueZ", "raiderRescueHp",
        )), "FO4SF_Min00Quest.psc", "exec"), ns)

        ns["InitRaiderTracking"]()

        # 1. Exact 16:50:47 candidate-2e race: Relocate starts on hilltop, then FO4SF_MapMarkers hops player into
        # interior FO4SF_MapMarkersHop (100008F4) right after PlacePreston before MoveOver runs on Raiders[0..4]!
        orig_place_preston = ns["PlacePreston"]

        def hop_into_mapmarkers_after_preston(p, who):
            res = orig_place_preston(p, who)
            p.interior = True
            p.world = None
            p.cell = "Cell<FO4SF_MapMarkersHop(100008F4)>"
            p.pos = [2888.89, 983.17, -38.48]
            return res

        ns["PlacePreston"] = hop_into_mapmarkers_after_preston
        ns["Relocate"](player)
        ns["PlacePreston"] = orig_place_preston

        self.assertEqual(sum(r.moveto_calls for r in raiders), 0)
        self.assertEqual(ns["relocateFails"], 0)
        for r, want_local in zip(raiders, raider_locals):
            self.assertFalse(r.interior)
            self.assertEqual(tuple(r.pos), want_local)

        # 2. Even if 5 raiders start pre-stranded in FO4SF_MapMarkersHop at (421.11, -275.25, -38.48), walking outdoors
        # to Concord (-2015, -1700, 89.1) rescues all 5 back to their Concord street targets!
        for i, r in enumerate(raiders):
            r.interior = True
            r.world = None
            r.cell = "Cell<FO4SF_MapMarkersHop(100008F4)>"
            r.pos = [421.11 - i, -275.25 + i, -38.48]

        player.interior = False
        player.world = fo4_world
        player.cell = "Cell<(05000806)>"
        player.pos = [-2015.0, -1700.0, 89.1]

        ns["CheckConcordRaidersWfc01"](player, False)
        for i, (r, loc) in enumerate(zip(raiders, raider_locals)):
            self.assertFalse(r.interior, f"raider {i} stayed in interior")
            self.assertEqual(r.world, fo4_world)
            self.assertAlmostEqual(r.pos[0], loc[0] - 1200.0, places=2)
            self.assertAlmostEqual(r.pos[1], loc[1] - 2700.0, places=2)
            self.assertAlmostEqual(r.pos[2], loc[2], places=2)
        self.assertEqual(sum(1 for ln in logs if "wfc01 rescue raider=" in ln), 5)

    def test_b4_codsworth_completes_and_hands_over_min00_even_when_cpp_getstage_stays_zero(self):
        # Reproduce candidate-2e 16:51:52..16:52:21: C++ GetStage() == 0 and GetStageDone() == False on BOTH quests
        h = A1dRealTalkTests()._build_harnesses(glob_val=1.0)
        h.c_ns["GetStage"] = lambda: 0
        h.c_ns["GetStageDone"] = lambda _s: False
        h.c_ns["SetStage"] = lambda _n: None
        h.m_ns["GetStage"] = lambda: 0
        h.m_ns["GetStageDone"] = lambda _s: False
        h.m_ns["SetStage"] = lambda _n: None

        # Out-of-order choice clicks (button 1 -> stage 30, button 0 -> stage 20, button 3 -> stage 100)
        for m in h.c_msgs:
            m.queue[:] = [1, 0, 3]

        h.c_ns["BindCodsworthActivation"]()
        h.c_ns["OnActivate"](h.c_ns["talkProxy"], h.player)

        self.assertTrue(h.c_ns["completed"])
        self.assertEqual(h.c_ns["choicesCount"], 3)
        h.c_ns["CompleteQuest"].assert_called_once()
        self.assertEqual(h.m_ns["EffectiveStage"](), 10)
        self.assertTrue(any("codsworth talk opened stage=10" in ln for ln in h.logs))
        self.assertTrue(any("codsworth talk end -> min00 stage 10" in ln for ln in h.logs))
        self.assertTrue(any("codsworth01 complete choices=3 concord_pointed=true" in ln for ln in h.logs))
        self.assertTrue(any("min00 given by=codsworth" in ln for ln in h.logs))


@unittest.skipUnless(shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS"),
                     "set FO4SF_DOTNET_TESTS=1 with a dotnet SDK on PATH to run the C# self-test")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, DOTNET_ROLL_FORWARD="Major")
            r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "Mission"),
                                "--", "selftest", d], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
