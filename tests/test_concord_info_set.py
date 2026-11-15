"""scripts/dialogue/concord_info_set.py and make_concord_talk.py (FAL-865). Synthetic only; no game files."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "dialogue"))
import concord_info_set as info  # noqa: E402
import make_concord_talk as mct  # noqa: E402
import make_dialogue_wheel_swf as wheel  # noqa: E402
import make_probe_swf as swf  # noqa: E402
from fo4sf.planet.esm import EsmError, PluginWriter  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "dialogue", "make_concord_talk.py")


class InfoSetTest(unittest.TestCase):
    def test_smallest_set_is_one_open_and_four_player(self):
        payload = info.check(info.info_set())
        self.assertEqual(payload["quest_formid"], 0x000179F3)
        self.assertEqual(payload["quest_edid"], "DialogueConcordArea")
        self.assertEqual(payload["player_info_count"], 4)
        self.assertEqual(payload["info_count"], 5)
        self.assertEqual(payload["dial_count"], 1)
        self.assertEqual(payload["keep_menu"], "DialogueMenu")
        self.assertEqual(payload["replace_movie"], "Interface/DialogueMenu.swf")
        self.assertEqual([r["prompt"] for r in payload["infos"] if r["role"] == "player"],
                         ["ONE", "TWO", "THREE", "FOUR"])

    def test_refuses_a_fifth_player_info(self):
        payload = info.info_set()
        payload["infos"].append({"role": "player", "kind": "choice", "slot": "X", "prompt": "FIVE", "index": 4})
        with self.assertRaisesRegex(info.InfoSetError, "four player"):
            info.check(payload)

    def test_refuses_fallout_prompt_text(self):
        payload = info.info_set()
        payload["infos"][1]["prompt"] = "What happened?"
        with self.assertRaisesRegex(info.InfoSetError, "stand-in"):
            info.check(payload)

    def test_slot_index(self):
        self.assertEqual(info.slot_index("N"), 0)
        self.assertEqual(info.slot_index("W"), 3)
        with self.assertRaises(info.InfoSetError):
            info.slot_index("UP")


class StageTest(unittest.TestCase):
    def test_plugin_header(self):
        data = mct.plugin_bytes()
        sig, size, flags = struct.unpack_from("<4sII", data, 0)
        self.assertEqual(sig, b"TES4")
        self.assertEqual(len(data), 24 + size)
        self.assertTrue(flags & 1)
        self.assertIn(b"Starfield.esm\x00", data)
        self.assertNotIn(b"GRUP", data)

    def test_stage_twins_dialogue_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            esm, movie, twin = mct.stage(tmp)
            self.assertEqual(os.path.basename(esm), "FO4SFConcordTalk.esm")
            self.assertEqual(os.path.relpath(movie, tmp).replace(os.sep, "/"), "Data/" + mct.MOVIE)
            self.assertEqual(os.path.relpath(twin, tmp).replace(os.sep, "/"), "Data/Interface/DialogueMenu.swf")
            with open(movie, "rb") as f:
                a = f.read()
            with open(twin, "rb") as f:
                b = f.read()
            self.assertEqual(a, b)
            self.assertEqual(a, wheel.movie_bytes())
            self.assertEqual(mct.check(esm)["masters"], ["Starfield.esm"])
            self.assertEqual(wheel.named_places(swf.read_movie(a)), list(wheel.SLOT_NAMES))

    def test_check_refuses_records(self):
        from fo4sf.planet.esm import Record
        w = PluginWriter(["Starfield.esm"])
        w.add(Record(b"GLOB", w.own(0x800), [(b"EDID", b"X\0"), (b"FLTV", struct.pack("<f", 0))], 0, 0, 576, 0))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.esm")
            with open(path, "wb") as f:
                f.write(w.to_bytes())
            with self.assertRaisesRegex(EsmError, "groups"):
                mct.check(path)

    def test_cli_stage_and_info_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, SCRIPT, "stage", tmp], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("DialogueMenu.swf", r.stdout)
            r = subprocess.run([sys.executable, SCRIPT, "info-set"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            info.check(payload)


if __name__ == "__main__":
    unittest.main()
