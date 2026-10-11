import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

GAME = Path(__file__).resolve().parents[1] / "scripts" / "game"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, GAME / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


memory = _load("prompt_memory")
rounds = _load("prompt_rounds")

MODEL = "SetDressing\\Doors\\SwitchDoors\\SwitchDoorExSmLatch01\\SwitchDoorExSmLatch01.nif"


class PromptMemoryTests(unittest.TestCase):
    def test_no_memory_offers_nothing(self):
        self.assertIsNone(memory.lookup({"cells": {}}, "Vault114", MODEL, "05C7DC:Fallout4.esm"))
        self.assertIsNone(memory.lookup({}, "Vault114"))
        self.assertIsNone(memory.lookup({"cells": {"Vault114": "junk"}}, "Vault114"))

    def test_a_hit_is_offered_to_the_next_route_of_that_cell_only(self):
        data = memory.record_hit({"cells": {}}, "Vault114", MODEL, "05C7DC:Fallout4.esm", 1000, when="t")
        self.assertEqual(memory.lookup(data, "Vault114"), 1000)
        self.assertEqual(memory.lookup(data, "Vault114", "Doors\\Other.nif", "000001:Fallout4.esm"), 1000)
        self.assertIsNone(memory.lookup(data, "ParsonsState01", MODEL, "05C7DC:Fallout4.esm"))

    def test_ref_beats_model_beats_cell(self):
        data = memory.record_hit({"cells": {}}, "V", "a\\DoorA.nif", "refA", 850, when="t")
        memory.record_hit(data, "V", "b\\DoorB.nif", "refB", 1150, when="t")
        self.assertEqual(memory.lookup(data, "V"), 1150)                                   # last hit in the cell
        self.assertEqual(memory.lookup(data, "V", "x/doora.nif", "unknown"), 850)          # model, any slash or case
        self.assertEqual(memory.lookup(data, "V", "x/DoorB.nif", "refA"), 850)             # ref first
        self.assertEqual(data["cells"]["V"]["models"], {"doora.nif": 850, "doorb.nif": 1150})

    def test_the_level_pitch_is_never_offered(self):
        data = memory.record_hit({"cells": {}}, "V", MODEL, "r", memory.LEVEL, when="t")
        self.assertIsNone(memory.lookup(data, "V", MODEL, "r"))

    def test_a_pitch_that_missed_twice_is_dropped_and_the_cell_falls_back(self):
        data = memory.record_hit({"cells": {}}, "V", "a\\DoorA.nif", "refA", 1000, when="t")
        # the remembered 1000 showed no prompt; the sweep then found 850 on another door
        memory.record_hit(data, "V", "b\\DoorB.nif", "refB", 850, missed=1000, when="t")
        self.assertEqual(memory.lookup(data, "V", "a\\DoorA.nif", "refA"), 1000)          # one miss is tolerated
        memory.record_hit(data, "V", "c\\DoorC.nif", "refC", 850, missed=1000, when="t")
        self.assertEqual(data["cells"]["V"]["misses"], {"1000": 2})
        self.assertEqual(memory.lookup(data, "V", "a\\DoorA.nif", "refA"), 850)           # ref/model 1000 skipped
        memory.record_hit(data, "V", "d\\DoorD.nif", "refD", 850, missed=850, when="t")
        memory.record_hit(data, "V", "d\\DoorD.nif", "refD", 850, missed=850, when="t")
        self.assertIsNone(memory.lookup(data, "V", "a\\DoorA.nif", "refA"))               # nothing trusted: old sweep

    def test_file_round_trip_and_unreadable_files_are_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "prompt_pitch.json")
            self.assertEqual(memory.load(path), {"cells": {}})
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(memory.main(["get", path, "Vault114", MODEL, "05C7DC:Fallout4.esm"]), 0)
            self.assertEqual(out.getvalue().strip(), "none")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(memory.main(["hit", path, "Vault114", MODEL, "05C7DC:Fallout4.esm", "1000"]), 0)
            with redirect_stdout(io.StringIO()) as out:
                memory.main(["get", path, "Vault114", MODEL, "05C7DC:Fallout4.esm"])
            self.assertEqual(out.getvalue().strip(), "1000")
            with redirect_stdout(io.StringIO()):
                memory.main(["hit", path, "Vault114", "Doors\\B.nif", "ref2", "850", "--missed", "1000"])
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["cells"]["Vault114"]["misses"], {"1000": 1})
            self.assertEqual(saved["cells"]["Vault114"]["refs"]["05C7DC:Fallout4.esm"], 1000)
            self.assertFalse(os.path.exists(path + ".tmp"))
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(memory.load(path), {"cells": {}})
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"cells": []}, f)
            self.assertEqual(memory.load(path), {"cells": {}})

    def test_a_dash_stands_for_an_empty_model_or_ref(self):
        # route_run.ps1 passes '-' for an empty model or ref (routes.py: model = r.get("model") or ""): Windows
        # PowerShell 5.1 drops an empty-string argument to a native command, so "" would shift the positional arguments
        # and the hit would fail on the missing pitch. '-' must record and look up by cell only, never as a model name.
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "prompt_pitch.json")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(memory.main(["hit", path, "V", "-", "-", "1000"]), 0)
            saved = memory.load(path)
            self.assertEqual(saved["cells"]["V"]["pitch"], 1000)
            self.assertNotIn("models", saved["cells"]["V"])
            self.assertNotIn("refs", saved["cells"]["V"])
            with redirect_stdout(io.StringIO()) as out:
                memory.main(["get", path, "V", "-", "-"])
            self.assertEqual(out.getvalue().strip(), "1000")
            with redirect_stdout(io.StringIO()) as out:
                memory.main(["get", path, "V", "-"])
            self.assertEqual(out.getvalue().strip(), "1000")


class RunnerConstantsTests(unittest.TestCase):
    def test_route_run_sweep_matches_the_memory_module_and_is_the_old_one(self):
        # a remembered pitch is "LEVEL + STEP * round": the runner and prompt_memory must agree on both numbers
        # (prompt_memory refuses to offer LEVEL, the sweep's own first shot), and the fallback sweep must still be the
        # old one: level sequence, 150 counts per round with a 450 ms wait, 9 rounds, re-levelled after a miss
        text = (GAME / "route_run.ps1").read_text(encoding="utf-8")
        self.assertIn(f"$LevelPitch = {memory.LEVEL}; $TiltStep = {memory.STEP}; $MaxRounds = {rounds.MAX_ROUNDS}", text)
        self.assertEqual((memory.LEVEL, memory.STEP, rounds.MAX_ROUNDS), (700, 150, 9))
        self.assertIn('"move:0,-2500|wait:250|move:0,-2500|wait:300|move:0,$pitch|wait:500"', text)
        self.assertIn('"move:0,$TiltStep|wait:450"', text)
        self.assertIn("Level-Camera $LevelPitch }", text)
        # empty model / ref go to prompt_memory.py as '-' (PowerShell 5.1 drops empty-string arguments), both calls
        self.assertIn("if (-not $model) { $model = '-' }", text)
        self.assertIn("if (-not $refArg) { $refArg = '-' }", text)
        self.assertIn("$memPy get $PitchMemory $cell $model $refArg", text)
        self.assertIn("@('hit', $PitchMemory, $cell, $model, $refArg, $pitch)", text)
        self.assertEqual(memory.NONE_ARG, "-")
        self.assertIn("$PitchMemory -ne 'off'", text)


def door(index, prompt, **extra):
    return dict({"index": index, "kind": "door", "ref": f"{index:06X}:Fallout4.esm", "prompt": prompt}, **extra)


class PromptRoundsTests(unittest.TestCase):
    def test_rounds_from_pre_shot_timestamps(self):
        results = [{"index": 0, "kind": "stairs", "prompt": None}, door(1, True), door(2, True), door(3, False),
                   door(4, True), {"index": 5, "kind": "door", "skipped": "start not reached"}]
        spans = {1: 0.05, 2: 2.11, 3: 16.54, 4: 6.22}
        seconds = rounds.round_seconds(results, spans)
        self.assertAlmostEqual(seconds, 16.54 / 8, places=4)
        rows = rounds.rounds(results, spans, seconds)
        self.assertEqual([(r["index"], r["rounds"], r["source"]) for r in rows],
                         [(1, 1, "timestamps"), (2, 2, "timestamps"), (3, 9, "timestamps"), (4, 4, "timestamps")])
        s = rounds.summary(rows, seconds)
        self.assertEqual((s["door_routes"], s["counted"], s["rounds"], s["beyond_first"], s["no_prompt"]),
                         (4, 4, 16, 4, 1))
        self.assertEqual(s["histogram"], {1: 1, 2: 1, 4: 1, 9: 1})

    def test_recorded_rounds_win_and_the_default_interval_is_used_without_full_sweeps(self):
        results = [door(0, True, prompt_rounds=1, prompt_pitch=850, pitch_source="memory"),
                   door(1, True, prompt_rounds=3, prompt_pitch=1000, pitch_source="sweep-after-miss"), door(2, True)]
        spans = {0: 4.2, 1: 4.2}
        self.assertEqual(rounds.round_seconds(results, spans), rounds.ROUND_SECONDS)
        rows = rounds.rounds(results, spans, rounds.ROUND_SECONDS)
        self.assertEqual([(r["rounds"], r["source"]) for r in rows],
                         [(1, "recorded"), (3, "recorded"), (None, "unknown")])
        self.assertEqual(rows[0]["pitch"], 850)
        self.assertEqual(rounds.summary(rows, rounds.ROUND_SECONDS)["counted"], 2)

    def test_report_reads_a_run_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            lines = [json.dumps(door(0, True)), json.dumps(door(1, True, prompt_rounds=1))]
            with open(os.path.join(folder, "results.jsonl"), "w", encoding="utf-8-sig") as f:
                f.write("\n".join(lines) + "\n")
            pre = os.path.join(folder, "r0_pre.png")
            with open(pre, "wb") as f:
                f.write(b"png")
            st = os.stat(pre)
            os.utime(pre, (st.st_atime, st.st_mtime + 2 * rounds.ROUND_SECONDS))
            rows, s, seconds = rounds.report(folder)
            self.assertEqual(seconds, rounds.ROUND_SECONDS)
            self.assertEqual([(r["rounds"], r["source"]) for r in rows], [(3, "timestamps"), (1, "recorded")])
            self.assertEqual(s["rounds"], 4)
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(rounds.main([folder]), 0)
            self.assertIn("rounds=3", out.getvalue())
