"""The terrain "activate" block: a runner feature, and its summary in the verdict detail (shown, never judged)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import runner_features  # noqa: E402
import testqueue  # noqa: E402

import json
import re
import tempfile

QSTEP = os.path.join(ROOT, "scripts", "game", "qstep.ps1")

# The console text the runner's OCR read from core64g_accept_1016 test 0002's activate_sel.png (prid 02008C5F, GetIsID
# 020A2AB2; the capture itself shows "GetIsID >> 1.00") at each threshold, re-read offline with ocr_prep.py + ocr.ps1
# (the 135 text equals that run's obs.activate.sel_ocr). Only the last rows matter to the pattern.
HEAD = "Get Disabled > > 1\nplayer. setpos x -2185.257\nplayer.setangle x 15\nprid 02008C5F\n"
CABINET_OCR = {135: HEAD + "GetlslD 020A2AB2", 140: HEAD + "GetlslD 020A2AB2\nGet ISID > > 1.00",
               130: HEAD + "GetlslD 020A2AB2\n1.00", 145: HEAD + "GetlsID 020A2AB2\n1.00"}
KIT_OCR = "prid 02069435\nGetlslD 020A2AB7\nGetlslD 1.00"      # tests 0000 / 0001 at 135: read on the first pass


def qstep_source():
    with open(QSTEP, encoding="utf-8") as f:
        return f.read()


def isid_reply():
    """qstep.ps1's $isidReply as PowerShell -match applies it (case-insensitive), None when the step has none."""
    m = re.search(r"\$isidReply = '([^']*)'", qstep_source())
    return re.compile(m.group(1), re.IGNORECASE) if m else None


def first_read(texts, thresholds):
    """Read-Console with $until, on OCR texts per threshold: (the first threshold whose text has the reply, its text),
    else (None, the first threshold's text)."""
    rx = isid_reply()
    for th in thresholds:
        if rx.search(texts[th]):
            return th, texts[th]
    return None, texts[thresholds[0]]


TEST ={"kind": "terrain", "activate": {"ref": "020A2AA5", "base": "020A2AA4", "expect": ["First Aid Kit", "Credits", "Digipick"]}}
PLAN = {"coc": "FO4Core_RedRocketSpawn", "travel": "coc FO4Core_RedRocketSpawn", "label": "r05", "spawn_local": [-989.26, 1146.51, 105.26],
        "settle_ms": 8000, "z_ref": "kit_south", "drop_z": 40.0, "points": [{"label": "kit_south", "x": -993.1, "y": 1148.6, "expect": 105.26}],
        "activate": TEST["activate"], "teleport_console": True}


class ActivateStepTests(unittest.TestCase):
    def test_activate_is_a_runner_feature(self):
        self.assertIn("activate", runner_features.FEATURES)
        self.assertIn("activate", runner_features.needs([TEST]))
        self.assertNotIn("activate", runner_features.needs([{"kind": "terrain"}]))

    def test_plan_terrain_carries_the_block(self):
        import inspect
        body = inspect.getsource(testqueue.plan_terrain)
        self.assertIn('"activate"', body)
        self.assertIn('"teleport_console"', body)

    def test_summary_lists_the_words_read(self):
        obs = {"activate": {"ref": "020A2AA5", "shot": "activate.png", "ocr": "FIRST AID KIT\nCredits 25\nDigipick 1"}}
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: read ['First Aid Kit', 'Credits', 'Digipick'] of ['First Aid Kit', 'Credits', 'Digipick']]")
        obs["activate"]["ocr"] = "MARS\nHEALTH 2/75"
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: read [] of ['First Aid Kit', 'Credits', 'Digipick']]")

    def test_unproven_selection_activates_nothing(self):
        obs = {"activate": {"ref": "020A2AA5", "base": "020A2AA4", "selected": False, "sel_ocr": "prid 020A2AA5\nItem not found"}}
        self.assertEqual(testqueue.activate_summary(TEST, obs),
                         "[activate 020A2AA5: selection not confirmed (GetIsID 020A2AA4 did not reply 1); nothing activated]")

    def test_planner_carries_and_validates_the_block(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "exp")); os.makedirs(os.path.join(d, "staging"))
            open(os.path.join(d, "staging", "FO4Port.esm"), "wb").write(b"TES4")
            open(os.path.join(d, "exp", "plan.json"), "w").write(json.dumps([PLAN]))
            args = type("A", (), dict(staging=os.path.join(d, "staging"), exp_dir=os.path.join(d, "exp"), out=os.path.join(d, "q"),
                                      plugin_index="02", launch_cell="Vault111Cryo", only=0, plugins="", starfield="", fresh=True))()
            testqueue.plan_terrain(args)
            q = json.load(open(os.path.join(d, "q", "queue.json")))
            self.assertEqual(q["tests"][0]["activate"], TEST["activate"])
            self.assertIs(q["tests"][0]["teleport_console"], True)
            self.assertIn("activate", q["needs"])
            bad = dict(PLAN, activate={"ref": "020A2AA5", "expect": ["x"]})          # no base: nothing to prove the selection with
            open(os.path.join(d, "exp", "plan.json"), "w").write(json.dumps([bad]))
            with self.assertRaises(SystemExit):
                testqueue.plan_terrain(args)

    def test_no_capture_and_no_block(self):
        self.assertEqual(testqueue.activate_summary(TEST, {"activate": {"ref": "020A2AA5", "shot": None}}),
                         "[activate 020A2AA5: no capture]")
        self.assertEqual(testqueue.activate_summary(TEST, {}), "")
        self.assertEqual(testqueue.activate_summary({"kind": "terrain"}, {"activate": {"shot": "x"}}), "")

    def test_the_reply_pattern_on_the_core64g_cabinet_reads(self):
        rx = isid_reply()
        self.assertIsNotNone(rx)
        self.assertFalse(rx.search(CABINET_OCR[135]))       # the reply row lost: the run's "selection not confirmed"
        self.assertFalse(rx.search(CABINET_OCR[140]))       # "Get ISID" split by the OCR: not taken
        self.assertTrue(rx.search(CABINET_OCR[130]))
        self.assertTrue(rx.search(CABINET_OCR[145]))
        self.assertTrue(rx.search(KIT_OCR))
        for refused in ("prid 02008C5F\nGetlslD 020A2AB2\nGetlslD 0.00", "prid 02008C5F\nItem not found",
                        "GetIsID 020A2AB1", "GetIsID 10000001", "GetlslD 020A2AB2\n> > 0.00"):
            self.assertFalse(rx.search(refused), refused)

    def test_the_selection_is_read_at_each_threshold_until_the_reply(self):
        src = qstep_source()
        m = re.search(r"\$ocrThresholds = @\(([0-9, ]+)\)", src)
        self.assertIsNotNone(m)
        ths = [int(x) for x in m.group(1).split(",")]
        self.assertEqual(ths, [135, 140, 130, 145])
        self.assertIn("foreach ($th in 135, 140, 130, 145)", src)            # Item-Capture's own four, same order
        self.assertIn("$sel = Read-Console 'activate_sel' $ocrThresholds $isidReply", src)
        self.assertIn('$selected = [bool]("$($sel.ocr)" -match $isidReply)', src)
        self.assertIn("sel_threshold = $sel.th", src)
        # the core64g cabinet: 135 and 140 do not take, 130 does; the kit reads at 135 as before; a lost reply keeps
        # the first threshold's text
        self.assertEqual(first_read(CABINET_OCR, ths), (130, CABINET_OCR[130]))
        self.assertEqual(first_read(dict.fromkeys(ths, KIT_OCR), ths), (135, KIT_OCR))
        lost = {th: CABINET_OCR[135] if th == 135 else CABINET_OCR[140] for th in ths}
        self.assertEqual(first_read(lost, ths), (None, CABINET_OCR[135]))

    def test_other_console_reads_keep_one_threshold(self):
        src = qstep_source()
        self.assertIn("function Read-Console([string]$name, [int[]]$thresholds = @(135), [string]$until = '')", src)
        for call in ('Read-Console "tp$($script:tpN)"', 'Read-Console "console_$k"', 'Read-Console "sky_${k}_console"'):
            self.assertIn(call + "\n", src.replace("\r\n", "\n"))


if __name__ == "__main__":
    unittest.main()
