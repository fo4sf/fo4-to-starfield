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
            with open(p, "wb") as f:                                   # a byte-order mark does not hide the first line
                f.write(b"\xef\xbb\xbf[05:20:01] Papyrus log opened (PC-64)\n")
            log = pl.read(p)
            self.assertEqual((log.unparsed, log.events[0].text), (0, "Papyrus log opened (PC-64)"))


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

    def test_every_baseline_line_is_counted_once(self):
        rep = self.rep
        self.assertEqual(sum(g["baseline_lines"] for g in rep["summary"].values()),
                         rep["baseline"]["error"] + rep["baseline"]["warning"])
        base = "\n".join([                                            # three lines at one script line, two kinds
            "[1] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", SHUTDOWN,
            "[2] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", SHUTDOWN, "\t[Q2 (00001234)].Q2Script.Go() - \"Q2Script.psc\" Line 4",
            "[3] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", SHUTDOWN, "\t[Q2 (00001234)].Q2Script.Go() - \"Q2Script.psc\" Line 4", ""])
        run = "\n".join([                                             # the first kind exactly, and two other callers
            "[1] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", SHUTDOWN,
            "[2] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", SHUTDOWN, "\t[Q3 (00001235)].Q3Script.Go() - \"Q3Script.psc\" Line 9",
            "[3] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", SHUTDOWN, "\t[Q4 (00001236)].Q4Script.Go() - \"Q4Script.psc\" Line 2", ""])
        rep = pl.compare(pl.parse(run), pl.parse(base))
        s = rep["summary"]
        self.assertEqual([(k["group"], k["baseline_count"]) for k in rep["kinds"]],
                         [("both_place", 2), ("both_place", 2), ("both", 1)])
        self.assertEqual((s["both"]["baseline_lines"], s["both_place"]["baseline_lines"], s["baseline"]["kinds"]), (1, 2, 0))
        only_exact = pl.compare(pl.parse("\n".join(run.splitlines()[:3])), pl.parse(base))
        self.assertEqual([(k["group"], k["baseline_count"]) for k in only_exact["kinds"]],
                         [("both", 1), ("baseline", 2)])                 # the other kind at that line is not lost
        self.assertEqual(sum(g["baseline_lines"] for g in only_exact["summary"].values()), 3)
        # the baseline's only kind at that line came in the run exactly: another caller there is still both_place
        rep = pl.compare(pl.parse("\n".join(run.splitlines()[:7])), pl.parse("\n".join(base.splitlines()[:3])))
        self.assertEqual([(k["group"], k["baseline_count"], k["place_count"]) for k in rep["kinds"]],
                         [("both_place", 0, 1), ("both", 1, 1)])
        self.assertEqual(sum(g["baseline_lines"] for g in rep["summary"].values()), 1)

    def test_ours_comes_before_the_same_script_line(self):
        run = "\n".join([                                             # our reference, at a line vanilla errors at too
            "[1] error: Cannot call Disable() on a None object, aborting function call",
            "stack:", "\t[FO4Core_MarkerRef (0A001234)].SFBGS003:SFBGS003_ShutdownQuestScript.Shutdown() - "
            "\"SFBGS003_ShutdownQuestScript.psc\" Line 51", ""])
        rep = pl.compare(pl.parse(run), pl.parse(BASELINE))
        ours = [k for k in rep["kinds"] if k["group"] == "ours"]
        self.assertEqual([(k["ours"], k["place_count"]) for k in ours], [(["FO4Core_MarkerRef"], 1)])
        self.assertEqual(rep["summary"]["ours"], {"kinds": 1, "run_lines": 1, "baseline_lines": 0})
        self.assertEqual(rep["summary"]["both_place"]["kinds"], 0)
        self.assertIn("baseline", {k["group"] for k in rep["kinds"]})   # the vanilla kind there is still counted
        self.assertEqual(sum(g["baseline_lines"] for g in rep["summary"].values()), 3)
        self.assertTrue(any("[ours: FO4Core_MarkerRef; 1 baseline lines at this place]" in ln
                            for ln in pl.report_lines(rep)))
        rep = pl.compare(pl.parse(run + RUN), pl.parse(BASELINE))         # the vanilla kind there came too
        ours = [k for k in rep["kinds"] if k["group"] == "ours" and k["ours"] == ["FO4Core_MarkerRef"]]
        self.assertEqual([k["place_count"] for k in ours], [1])

    def test_the_baseline_count_is_beside_each_shared_kind(self):
        lines = pl.report_lines(self.rep)
        self.assertIn("     2x error: Cannot call Disable() on a None object, aborting function call at "
                      "SFBGS003:SFBGS003_ShutdownQuestScript.Shutdown() - \"SFBGS003_ShutdownQuestScript.psc\" Line 51 "
                      "(baseline 1x)", lines)                                  # both: the same kind's count
        self.assertTrue(any(ln.startswith("     1x error: Cannot call GetValue()") and ln.endswith("(baseline 1x)")
                            for ln in lines))                                  # both_place: the lines at its place
        disable = "\n".join(BASELINE.splitlines()[1:5])                        # the baseline's first error, its stack
        for n, mark in ((9, "(baseline 1x)"), (10, "(baseline 1x, 10x or more)")):
            rep = pl.compare(pl.parse("\n".join([disable] * n)), pl.parse(BASELINE))
            self.assertTrue(any(ln.startswith(f"{n:6}x error: Cannot call Disable()") and ln.endswith(mark)
                                for ln in pl.report_lines(rep)), n)            # far more often: still ours to look at

    def test_an_unnamed_reference_of_ours_is_not_found_as_ours(self):
        run = "\n".join(["[1] error: Cannot call Disable() on a None object, aborting function call", "stack:",
                         "\t[ (0A001234)].SFBGS003:SFBGS003_ShutdownQuestScript.Shutdown() - "
                         "\"SFBGS003_ShutdownQuestScript.psc\" Line 51", ""])   # no EditorID, so no name
        rep = pl.compare(pl.parse(run), pl.parse(BASELINE))
        self.assertEqual([(k["group"], k["ours"]) for k in rep["kinds"] if k["run_count"]], [("both_place", [])])

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
