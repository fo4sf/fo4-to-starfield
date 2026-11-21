"""Synthetic selected-world identity controls; no game files or runtime assumptions."""
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "planet"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import read_overlay_control as reader  # noqa: E402
import planet_fixture as pf  # noqa: E402
from fo4sf.planet import esm, probe  # noqa: E402

WORLD, MARKER, PCELL, EXT, COC = 0x1187EA, 0x3A866E, 0x300000, 0x300001, 0x300002


def fixture(disabled=False, base=0x10, xmrk=True, candidate=True, duplicate=False,
            wrong_world=False, overlay=True, masters=(), compressed=False, coc_disabled=False):
    world = pf.overlay_world(WORLD, "LandingOverlay01", 0, 4, 0x1000, 0x2000) if overlay else esm.Record("WRLD", WORLD)
    marker = pf.placed(b"REFR", MARKER, base, (1, 2, 3), persistent=True, flags=0x800 if disabled else 0)
    if xmrk:
        marker.subs.append((b"XMRK", b""))
    if compressed:
        marker.flags |= esm.COMPRESSED
    coc = pf.placed(b"REFR", COC, probe.COC_MARKER, (1, 2, 3), flags=0x800 if coc_disabled else 0)
    ext = pf.cell(EXT, (0, 1), "LandingTestExt01" if candidate else None)
    inner = pf.world_group(world, pf.cell(PCELL), [] if wrong_world else [marker], [(ext, [coc])])
    # A valid unrelated world must never supply the requested world's missing identity/coc.
    other = pf.overlay_world(0x4000, "OtherOverlay", 0, 4, 0x1001, 0x2001)
    extra = [marker] if wrong_world or duplicate else []
    inner += pf.world_group(other, pf.cell(0x4001), extra,
                            [(pf.cell(0x4002, (1, 1), "UnrelatedExt01"),
                              [pf.placed(b"REFR", 0x4003, probe.COC_MARKER, (0, 0, 0))])])
    return esm.PluginWriter(masters).to_bytes() + esm.group_bytes("WRLD", inner)


class OverlayControlReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "Starfield.esm")
        self.write(fixture())

    def write(self, data):
        with open(self.path, "wb") as f:
            f.write(data)
        self.digest = hashlib.sha256(data).hexdigest()

    def read(self, **kwargs):
        return reader.read_control(self.path, kwargs.get("world", WORLD), kwargs.get("marker", MARKER),
                                   kwargs.get("digest", self.digest))

    def cli(self, *extra):
        return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "planet", "read_overlay_control.py"),
                               "--starfield-esm", self.path, "--world", "001187EA", "--marker", "003A866E",
                               "--expect-sha256", self.digest, *extra], capture_output=True, text=True)

    def test_candidate_is_actual_same_world_cell_coc_and_read_only(self):
        before = os.stat(self.path)
        got = self.cli()
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(got.stderr, "")
        report = json.loads(got.stdout)
        self.assertEqual(report["decision"], "CANDIDATE_IDENTITY_ONLY")
        self.assertEqual(report["sha256"], report["sha256_after"])
        self.assertEqual(report["world"]["edid"], "LandingOverlay01")
        self.assertEqual(report["marker"]["flags"], "00000400")
        self.assertEqual([(x["cell_edid"], x["coc_ref"]) for x in report["coc_candidates"]],
                         [("LandingTestExt01", "00300002")])
        with open(self.path, "rb") as f:
            raw = f.read()
        pair = report["coc_candidates"][0]
        for offset, sig in [(report["marker"]["offset"], b"REFR"), (report["world"]["offset"], b"WRLD"),
                            (pair["cell_offset"], b"CELL"), (pair["coc_offset"], b"REFR")]:
            self.assertEqual(raw[offset:offset + 4], sig)
        self.assertEqual(os.listdir(self.tmp.name), ["Starfield.esm"])
        after = os.stat(self.path)
        self.assertEqual((before.st_size, before.st_mtime_ns), (after.st_size, after.st_mtime_ns))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.digest)

    def test_no_candidate_is_unresolved_not_an_invented_cell(self):
        for options in ({"candidate": False}, {"coc_disabled": True}):
            with self.subTest(options=options):
                self.write(fixture(**options))
                report = self.read()
                self.assertEqual(report["decision"], "UNRESOLVED_NO_COC_CANDIDATE")
                self.assertEqual(report["coc_candidates"], [])

    def test_disabled_wrong_base_missing_xmrk_and_non_overlay_refuse(self):
        for options in ({"disabled": True}, {"base": 0x3B}, {"xmrk": False}, {"overlay": False}):
            with self.subTest(options=options):
                self.write(fixture(**options))
                got = self.cli()
                self.assertEqual(got.returncode, 2)
                self.assertEqual(got.stdout, "")
                self.assertIn("error", json.loads(got.stderr))

    def test_wrong_world_missing_duplicate_and_namespace_refuse(self):
        for options in ({"wrong_world": True}, {"duplicate": True}, {"masters": ["Other.esm"]}):
            with self.subTest(options=options):
                self.write(fixture(**options))
                with self.assertRaises(ValueError):
                    self.read()
        self.write(fixture())
        for options in ({"marker": 0x1234}, {"world": 0x1234}, {"marker": 0xFF3A866E}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.read(**options)
        for text in ("3A866E", "FF3A866E", "1003A866E", "-03A866E"):
            with self.assertRaises(Exception):
                reader.vanilla_id(text)

    def test_hash_pin_changed_mapping_and_malformed_group_refuse(self):
        for digest in ("0" * 64, "bad"):
            with self.assertRaises(ValueError):
                self.read(digest=digest)
        with patch.object(reader.hashlib, "sha256") as h:
            h.return_value.hexdigest.side_effect = ["a" * 64, "b" * 64]
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.read(digest="a" * 64)
        with open(self.path, "rb") as f:
            raw = bytearray(f.read())
        with esm.Plugin(self.path) as p:
            start, _ = p.groups["WRLD"][0]
        struct.pack_into("<I", raw, start - 20, len(raw) + 1)
        self.write(raw)
        got = self.cli()
        self.assertEqual(got.returncode, 2)
        self.assertEqual(got.stdout, "")

    def test_compressed_payload_uses_existing_record_reader(self):
        self.write(fixture(compressed=True))
        self.assertEqual(self.read()["marker"]["flags"], "00040400")


if __name__ == "__main__":
    unittest.main()
