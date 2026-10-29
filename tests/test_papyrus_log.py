"""fo4sf.core.papyrus_log: Starfield's Papyrus log read into messages with their stacks (the 1.16.244 format of the
28 Oct 2026 run 3 log, rebuilt here with made-up lines), and a run compared with a vanilla baseline. Synthetic logs
only."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import papyrus_log as pl  # noqa: E402

SHUTDOWN = ("\t[SFBGS003_BountyScannerQuest (FD00556E)].SFBGS003:SFBGS003_ShutdownQuestScript.Shutdown() - "
            "\"SFBGS003_ShutdownQuestScript.psc\" Line 51")
BASELINE = "\n".join([
    "[05:20:01] Papyrus log opened (PC-64)",
    "[05:20:02] error: Cannot call Disable() on a None object, aborting function call",
    "stack:",
    SHUTDOWN,
    "\t[Patch_Update7_1_SFBGS003 (FD00FFDF)].SFBGS003:Fragments:QF_X.Fragment_Stage_0000_Item_00() - \"QF_X.psc\" Line 13",
    "[05:20:03] warning: Property Ship on script Y attached to Z (FF000123) cannot be initialized",
    "[05:20:04] error: Cannot call GetValue() on a None object, aborting function call",
    "stack:",
    "\t[MQ101 (00003448)].MQ101Script.OnStageSet() - \"MQ101Script.psc\" Line 7",
    "[05:20:05] VM is freezing...",
    "",
])
RUN = "\r\n".join([
    "[06:00:01] Papyrus log opened (PC-64)",
    "[06:00:02] error: Cannot call Disable() on a None object, aborting function call",
    "stack:",
    SHUTDOWN,
    "\t[Patch_Update7_1_SFBGS003 (FD00FFDF)].SFBGS003:Fragments:QF_X.Fragment_Stage_0000_Item_00() - \"QF_X.psc\" Line 13",
    "[06:00:02] error: Cannot call Disable() on a None object, aborting function call",
    "stack:",
    SHUTDOWN,
    "\t[Patch_Update7_1_SFBGS003 (FD00FFDF)].SFBGS003:Fragments:QF_X.Fragment_Stage_0000_Item_00() - \"QF_X.psc\" Line 13",
    "[06:00:03] warning: Property Ship on script Y attached to Z (FF000456) cannot be initialized",
    "[06:00:04] error: Cannot call SetValue() on a None object, aborting function call",
    "stack:",
    "\t[FO4SFNewGameQuest (0A000800)].FO4SF_NewGameScript.OnStageSet() - \"FO4SF_NewGameScript.psc\" Line 30",
    "[06:00:05] error: Cannot call GetValue() on a None object, aborting function call",
    "stack:",
    "\t[alias Ship on quest MQ101 (00003448)].MQ101Script.OnStageSet() - \"MQ101Script.psc\" Line 7",
    "[06:00:06] error: LandingPad cannot be moved",
    "stack:",
    "\t[ (FF000ABC)].ObjectReference.MoveTo() - \"<native>\" Line ?",
    "\t[MQ101 (00003448)].MQ101Script.Stage200() - \"MQ101Script.psc\" Line 99",
    "a line the log reader does not know",
    "",
])


class ParseTests(unittest.TestCase):
    def test_messages_levels_and_stacks(self):
        log = pl.parse(BASELINE, "base.log")
        self.assertEqual(log.counts(), {"error": 2, "warning": 1, "note": 2})
        first = log.events[1]
        self.assertEqual((first.level, first.time, first.line), ("error", "05:20:02", 2))
        self.assertEqual(first.text, "Cannot call Disable() on a None object, aborting function call")
        self.assertEqual(first.frames[0], SHUTDOWN.strip())
        self.assertEqual(len(first.frames), 2)
        self.assertEqual((log.events[2].level, log.events[2].frames), ("warning", []))
        self.assertEqual(log.events[4].text, "VM is freezing...")
        self.assertEqual((log.unparsed, log.lines), (0, 10))

    def test_crlf_and_a_line_it_does_not_know(self):
        log = pl.parse(RUN)
        self.assertEqual(log.unparsed, 1)
        self.assertEqual(log.counts()["error"], 5)
        self.assertEqual(log.events[-1].frames[0], "[ (FF000ABC)].ObjectReference.MoveTo() - \"<native>\" Line ?")

    def test_a_runtime_id_is_the_same_thing_in_two_runs(self):
        a = pl.parse(BASELINE).events[2]
        b = pl.parse(RUN).events[3]
        self.assertNotEqual(a.text, b.text)                       # FF000123 and FF000456
        self.assertEqual(a.key, b.key)
        self.assertEqual(pl.runtime_free("x FF00ABCD y 0A000800"), "x FF?????? y 0A000800")
        self.assertEqual(pl.template("ref 0A000800 at 12 FF000001"), "ref #id at # #id")

    def test_place_is_the_innermost_script_line(self):
        e = pl.parse(RUN).events[-1]
        self.assertEqual(e.place, ("error", "LandingPad cannot be moved", 'MQ101Script.Stage200() - "MQ101Script.psc" Line 99'))
        self.assertEqual(pl.parse("[1] error: no stack\n").events[0].place, ("error", "no stack", ""))

    def test_ours_are_named_by_their_prefix(self):
        log = pl.parse(RUN)
        self.assertEqual(log.events[4].ours(), ["FO4SF_NewGameScript", "FO4SFNewGameQuest"])
        self.assertEqual(log.events[1].ours(), [])

    def test_read_replaces_a_byte_that_does_not_decode(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "Papyrus.0.log")
            with open(p, "wb") as f:
                f.write(b"[1] error: bad \xff byte\n")
            log = pl.read(p)
            self.assertEqual((log.path, log.events[0].text), (p, "bad � byte"))


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.rep = pl.compare(pl.parse(RUN, "run.log"), pl.parse(BASELINE, "base.log"))
        self.by = {}
        for k in self.rep["kinds"]:
            self.by.setdefault(k["group"], []).append(k)

    def test_groups(self):
        both = self.by["both"]
        self.assertEqual([(k["level"], k["run_count"], k["baseline_count"]) for k in both],
                         [("error", 2, 1), ("warning", 1, 1)])           # the most frequent first
        place = self.by["both_place"][0]                                # another object, the same script line
        self.assertEqual((place["text"], place["place"]), ("Cannot call GetValue() on a None object, aborting function call",
                                                           'MQ101Script.OnStageSet() - "MQ101Script.psc" Line 7'))
        ours = self.by["ours"][0]
        self.assertEqual((ours["ours"], ours["run_count"]), (["FO4SF_NewGameScript", "FO4SFNewGameQuest"], 1))
        self.assertEqual(self.by["starfield"][0]["text"], "LandingPad cannot be moved")
        self.assertNotIn("baseline", self.by)                           # every baseline kind came in the run too
        self.assertEqual(self.rep["summary"]["ours"], {"kinds": 1, "run_lines": 1, "baseline_lines": 0})
        self.assertEqual(self.rep["run"]["error"], 5)
        self.assertEqual(self.rep["levels"], ["error", "warning"])

    def test_a_kind_only_the_baseline_has(self):
        rep = pl.compare(pl.parse(""), pl.parse(BASELINE))
        self.assertEqual([k["group"] for k in rep["kinds"]], ["baseline"] * 3)
        self.assertEqual(rep["summary"]["baseline"]["baseline_lines"], 3)

    def test_notes_are_grouped_only_when_asked(self):
        rep = pl.compare(pl.parse(RUN), pl.parse(BASELINE), levels=("note",))
        self.assertEqual([k["text"] for k in rep["kinds"] if k["group"] == "both"], ["Papyrus log opened (PC-64)"])

    def test_report_lines_and_json(self):
        lines = pl.report_lines(self.rep, top=1)
        self.assertTrue(lines[0].startswith("run:      run.log: 5 errors, 1 warnings, 1 notes"))
        self.assertIn("only in this run, naming one of ours: 1 kinds, 1 lines", lines)
        self.assertIn("     1x error: Cannot call SetValue() on a None object, aborting function call at "
                      "FO4SF_NewGameScript.OnStageSet() - \"FO4SF_NewGameScript.psc\" Line 30 "
                      "[ours: FO4SF_NewGameScript, FO4SFNewGameQuest]", lines)
        self.assertIn("  ... and 1 more kinds (all in the JSON report)", lines)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "r.json")
            pl.write_report(self.rep, p)
            with open(p, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["summary"], self.rep["summary"])


if __name__ == "__main__":
    unittest.main()
