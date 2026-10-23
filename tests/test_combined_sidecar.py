"""Combined-core sidecar codec (sidecar.py): round trip, tamper detection, atomic write and orphans, in temp dirs."""
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, sidecar, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402


def world(seed=1, hours=0):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    if hours:
        sim.run(ws, hours)
    return ws


class NameTests(unittest.TestCase):
    def test_name_is_safe_and_unique(self):
        for name in ("Save1_Player", "Quick Save", "../evil", "a/b\\c:d*e?f\"g<h>i|j", "ünïcödé", "x" * 300):
            fn = sidecar.sidecar_name(name)
            self.assertTrue(fn.endswith(sidecar.EXTENSION), fn)
            self.assertNotIn(os.sep, fn)
            self.assertNotIn("/", fn)
            self.assertRegex(fn, r"^[A-Za-z0-9_.-]+$")
            self.assertLessEqual(len(fn), sidecar.SAFE_NAME_MAX + 1 + sidecar.HASH_CHARS + len(sidecar.EXTENSION))
        self.assertNotEqual(sidecar.sidecar_name("a/b"), sidecar.sidecar_name("a_b"))     # the hash tells them apart
        self.assertNotEqual(sidecar.sidecar_name("y" * 300), sidecar.sidecar_name("y" * 301))
        self.assertEqual(sidecar.sidecar_name("Save 1"), sidecar.sidecar_name("Save 1"))

    def test_empty_name_refused(self):
        for bad in ("", None):
            with self.assertRaises(ValueError):
                sidecar.sidecar_name(bad)


class RoundTripTests(unittest.TestCase):
    def test_write_then_read_gives_the_same_state(self):
        for seed in (1, 4, 9):
            ws = world(seed, hours=30 * 24)
            with tempfile.TemporaryDirectory() as d:
                path = sidecar.write(d, f"Save{seed}", ws)
                self.assertTrue(os.path.isfile(path))
                self.assertEqual(os.listdir(d), [os.path.basename(path)])   # no temp file left behind
                back = sidecar.read(d, f"Save{seed}")
                self.assertEqual(back.to_json(), ws.to_json())
                sim.run(back, 10 * 24)
                sim.run(ws, 10 * 24)
                self.assertEqual(back.to_json(), ws.to_json())              # and it replays exactly

    def test_body_shape_and_determinism(self):
        ws = world(2, hours=24)
        text = sidecar.encode("Save2", ws)
        self.assertEqual(text, sidecar.encode("Save2", ws))
        body = json.loads(text)
        self.assertEqual(set(body), {"format", "schema", "save_name", "world_state", "sha256"})
        self.assertEqual((body["format"], body["schema"], body["save_name"]), (sidecar.FORMAT, sidecar.SCHEMA, "Save2"))
        self.assertEqual(body["world_state"]["schema"], model.SCHEMA_VERSION)
        self.assertEqual(body["sha256"], sidecar.checksum(ws.to_json()))
        with tempfile.TemporaryDirectory() as d:
            sidecar.write(d, "Save2", ws)
            with open(sidecar.sidecar_path(d, "Save2"), encoding="utf-8") as f:
                self.assertEqual(f.read(), text)

    def test_rewrite_replaces_the_old_sidecar(self):
        ws = world(3)
        with tempfile.TemporaryDirectory() as d:
            sidecar.write(d, "Save3", ws)
            sim.run(ws, 20 * 24)
            sidecar.write(d, "Save3", ws)
            self.assertEqual(len(os.listdir(d)), 1)
            self.assertEqual(sidecar.read(d, "Save3").hour, ws.hour)

    def test_missing_sidecar_is_file_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                sidecar.read(d, "Nope")


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.ws = world(5, hours=12 * 24)
        self.text = sidecar.encode("Save5", self.ws)
        self.body = json.loads(self.text)

    def rewrite(self, body):
        return json.dumps(body, sort_keys=True)

    def test_tampered_state_fails_checksum(self):
        body = copy.deepcopy(self.body)
        body["world_state"]["places"]["ruins"]["holder"] = "raiders"
        with self.assertRaisesRegex(ValueError, "checksum"):
            sidecar.decode(self.rewrite(body), "Save5")
        body = copy.deepcopy(self.body)
        body["world_state"]["reputation"]["raiders"]["fame"] += 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            sidecar.decode(self.rewrite(body))

    def test_wrong_format_schema_or_save_name(self):
        body = dict(self.body, format="other")
        with self.assertRaisesRegex(ValueError, "not a focc-sidecar"):
            sidecar.decode(self.rewrite(body))
        body = dict(self.body, schema=sidecar.SCHEMA + 1)
        with self.assertRaisesRegex(ValueError, "schema"):
            sidecar.decode(self.rewrite(body))
        with self.assertRaisesRegex(ValueError, "belongs to save"):
            sidecar.decode(self.text, "Save6")
        sidecar.decode(self.text)                                     # no name given: name not checked

    def test_truncated_or_foreign_text(self):
        with self.assertRaisesRegex(ValueError, "not JSON"):
            sidecar.decode(self.text[:-20])
        with self.assertRaisesRegex(ValueError, "not a focc-sidecar"):
            sidecar.decode("[1, 2, 3]")
        body = {k: v for k, v in self.body.items() if k != "sha256"}
        with self.assertRaisesRegex(ValueError, "lacks"):
            sidecar.decode(self.rewrite(body))

    def test_stale_world_schema_is_refused_after_checksum(self):
        body = copy.deepcopy(self.body)
        body["world_state"]["schema"] = 99
        body["sha256"] = sidecar.checksum(json.dumps(body["world_state"], sort_keys=True))
        with self.assertRaisesRegex(ValueError, "world-state schema"):
            sidecar.decode(self.rewrite(body))

    def test_tamper_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            path = sidecar.write(d, "Save5", self.ws)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace('"hour": 288', '"hour": 289'))
            with self.assertRaisesRegex(ValueError, "checksum"):
                sidecar.read(d, "Save5")


class AtomicTests(unittest.TestCase):
    def test_failed_write_keeps_the_old_file_and_no_temp(self):
        ws = world(7)
        with tempfile.TemporaryDirectory() as d:
            path = sidecar.write(d, "Save7", ws)
            with open(path, encoding="utf-8") as f:
                before = f.read()
            sim.run(ws, 24)
            with mock.patch.object(sidecar, "encode", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    sidecar.write(d, "Save7", ws)
            self.assertEqual(os.listdir(d), [os.path.basename(path)])
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), before)

    def test_write_uses_replace_not_in_place(self):
        ws = world(8)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(sidecar.os, "replace", wraps=os.replace) as rep:
                sidecar.write(d, "Save8", ws)
            self.assertEqual(rep.call_count, 1)
            src, dst = rep.call_args[0]
            self.assertEqual(os.path.dirname(src), d)                 # temp file in the same directory
            self.assertEqual(dst, sidecar.sidecar_path(d, "Save8"))


class OrphanTests(unittest.TestCase):
    def test_orphans_listed_never_deleted(self):
        ws = world(9)
        with tempfile.TemporaryDirectory() as d:
            paths = {n: sidecar.write(d, n, ws) for n in ("Save1", "Save2", "Quick Save")}
            with open(os.path.join(d, "notes.txt"), "w") as f:
                f.write("not a sidecar")
            self.assertEqual(sidecar.orphans(d, ["Save1", "Save2", "Quick Save"]), [])
            got = sidecar.orphans(d, ["Save2"])
            self.assertEqual(got, sorted([paths["Save1"], paths["Quick Save"]]))
            self.assertEqual(sidecar.orphans(d, []), sorted(paths.values()))
            self.assertEqual(sorted(os.listdir(d)),                      # nothing removed
                             sorted([os.path.basename(p) for p in paths.values()] + ["notes.txt"]))
            self.assertEqual(sidecar.orphans(d, ["Save1", "Save2", "Quick Save", "Never Written"]), [])

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sidecar.orphans(d, ["Save1"]), [])


if __name__ == "__main__":
    unittest.main()
