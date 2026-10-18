"""Synthetic companion-only registration changes, not a test of the engine hypothesis."""
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("registration_probe", ROOT / "scripts/slice/stage_registration_probe.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def rec(sig, data, fid=0, flags=0):
    return struct.pack("<4sIII8s", sig, len(data), flags, fid, b"\0" * 8) + data


def header(names):
    return rec(b"TES4", b"".join(sub(b"MAST", n.encode() + b"\0") for n in names))


OLD, NEW = (0.3, -1.2), (0.3008, -1.1996)


def companion(entries=None, names=None, flags=0):
    names = names or ["Starfield.esm", "Core.esm"]
    entries = entries if entries is not None else [(0.1, 0.2, 0x999), (*OLD, 0x01000803)]
    planet = rec(b"PNDT", sub(b"CNAM", b"\1") + sub(b"CNAM", b"".join(
        struct.pack("<ddI", *e) for e in entries)), 0x3F59A, flags)
    group = struct.pack("<4sI16s", b"GRUP", 24 + len(planet), b"PNDT" + b"\0" * 12)
    return header(names) + group + planet


class RegistrationProbeTests(unittest.TestCase):
    def test_changes_only_pair_preserving_foreign_entry_and_identity(self):
        before = companion()
        after, report = m.patch_registration(before, "Core.esm", 0x803, OLD, NEW)
        pos = report["cnam_offset"]
        expected = bytearray(before)
        struct.pack_into("<dd", expected, pos, *NEW)
        self.assertEqual(after, bytes(expected))
        self.assertEqual(struct.unpack_from("<ddI", after, pos), (*NEW, 0x01000803))
        self.assertEqual(report["entry_count"], 2)

    def test_resolves_shifted_master_slot(self):
        data = companion([(*OLD, 0x02000803)], ["Starfield.esm", "Other.esm", "Core.esm"])
        _, report = m.patch_registration(data, "Core.esm", 0x803, OLD, NEW)
        self.assertEqual(report["world_form_id_in_companion"], "02000803")

    def test_compressed_payload_only_pair_changes_and_group_size_tracks(self):
        original = companion()
        planet = list(m.records(original))[1]
        raw = original[planet[3]:planet[4]]
        compressed = m.replace_payload(original, planet, struct.pack("<I", len(raw)) + zlib.compress(raw), 0x40000)
        candidate, report = m.patch_registration(compressed, "Core.esm", 0x803, OLD, NEW)
        target = list(m.records(candidate))[1]
        payload = zlib.decompress(candidate[target[3] + 4:target[4]])
        expected = bytearray(raw)
        struct.pack_into("<dd", expected, report["cnam_payload_offset"], *NEW)
        self.assertEqual(payload, bytes(expected))
        self.assertEqual(target[2], 0x40000)
        self.assertEqual(candidate[:len(header(["Starfield.esm", "Core.esm"]))],
                         compressed[:len(header(["Starfield.esm", "Core.esm"]))])
        self.assertEqual(target[4], len(candidate))
        self.assertTrue(report["compressed"])

    def test_compressed_length_and_trailing_stream_refused(self):
        original = companion()
        planet = list(m.records(original))[1]
        raw = original[planet[3]:planet[4]]
        for size, suffix in ((len(raw) - 1, b""), (len(raw) + 1, b""), (len(raw), b"trailing"), (2000000, b"")):
            data = m.replace_payload(original, planet, struct.pack("<I", size) + zlib.compress(raw) + suffix, 0x40000)
            with self.assertRaises(ValueError):
                m.patch_registration(data, "Core.esm", 0x803, OLD, NEW)

    def test_ambiguous_missing_and_wrong_baseline_refused(self):
        for data in (companion([]), companion([(*OLD, 0x01000803)] * 2),
                     companion([(*OLD, 0x02000803)]), companion([(0.4, -1.2, 0x01000803)]),
                     companion([(*OLD, 0x01000803), (*NEW, 0x999)])):
            with self.subTest(data=data), self.assertRaises(ValueError):
                m.patch_registration(data, "Core.esm", 0x803, OLD, NEW)

    def test_malformed_or_unsupported_companion_refused(self):
        valid = companion()
        cases = [valid[:-1], valid + b"x", companion(flags=0x40000), companion(flags=0x20),
                 valid + rec(b"STAT", b""), companion(names=["Core.esm", "Starfield.esm"]),
                 companion(names=["Starfield.esm", "Core.esm", "Core.esm"])]
        for data in cases:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                m.patch_registration(data, "Core.esm", 0x803, OLD, NEW)

    def test_invalid_or_noop_coordinates_refused(self):
        for new in (OLD, (math.nan, 0), (0, math.inf), (2, 0), (0, 4)):
            with self.subTest(new=new), self.assertRaises(ValueError):
                m.patch_registration(companion(), "Core.esm", 0x803, OLD, new)

    def test_world_is_unique_and_owned(self):
        world = rec(b"WRLD", sub(b"EDID", b"World\0"), 0x01000803)
        self.assertEqual(m.world_id(header(["Starfield.esm"]) + world, "World"), 0x803)
        for data in (header([]) + world, header(["Starfield.esm"]) + world * 2,
                     header(["Starfield.esm"]) + rec(b"WRLD", sub(b"EDID", b"World\0"), 0x01000803, 0x20)):
            with self.assertRaises(ValueError):
                m.world_id(data, "World")

    def fixture(self, source):
        source.mkdir()
        params = {"plugin": "Core.esm", "mars": {"plugin": "Mars.esm", "radius_km": 3390,
                  "reference": {"latitude": .3, "longitude": -1.2, "offset_cells": [-12, -27]}},
                  "overlays": [{"world": "World", "latitude": .3, "longitude": -1.2, "spawn": [5, 6, 7]}]}
        (source / "overlays_params.json").write_text(json.dumps(params))
        (source / "Mars.esm").write_bytes(companion())
        (source / "Core.esm").write_bytes(header(["Starfield.esm"]) +
            rec(b"WRLD", sub(b"EDID", b"World\0"), 0x01000803))

    def test_stage_preserves_baseline_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp) / "source", Path(tmp) / "candidate"
            self.fixture(source)
            before = {p.name: p.read_bytes() for p in source.iterdir()}
            report = m.stage(source, out)
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir()})
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["Mars.esm", "registration-probe.json"])
            self.assertFalse(report["native_accepted"])
            self.assertFalse(report["complete_installation"])
            self.assertLess(max(abs(v) for v in report["predicted_offset_cells"]), 1e-8)
            with self.assertRaises(ValueError):
                m.stage(source, out)
            with self.assertRaises(ValueError):
                m.stage(source, source / "child")

    def test_source_change_refuses_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp) / "source", Path(tmp) / "candidate"
            self.fixture(source)
            real_patch = m.patch_registration

            def mutate(*args):
                result = real_patch(*args)
                (source / "Core.esm").write_bytes(b"changed")
                return result

            with patch.object(m, "patch_registration", side_effect=mutate), self.assertRaisesRegex(ValueError, "source changed"):
                m.stage(source, out)
            self.assertFalse(out.exists())

    def test_cli_keeps_private_report_in_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "private-source-sentinel"
            out = Path(tmp) / "private-output-sentinel"
            self.fixture(source)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/slice/stage_registration_probe.py"),
                 "--source-stage", str(source), "--out", str(out)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((out / "registration-probe.json").read_text(encoding="utf-8"))
            self.assertEqual(report["source_stage"], str(source.resolve()))
            self.assertEqual(report["source_pins"]["Core.esm"], m.pin((source / "Core.esm").read_bytes()))
            self.assertEqual(report["candidate"]["Mars.esm"], m.pin((out / "Mars.esm").read_bytes()))
            self.assertFalse(report["native_accepted"])
            self.assertFalse(report["complete_installation"])
            self.assertEqual(result.stderr, "")
            self.assertEqual(result.stdout, "Registration candidate staged; inspect registration-probe.json in the requested output directory.\n")

    def test_plain_filenames_only(self):
        for name in ("../Core.esm", "sub/Core.esm", "sub\\Core.esm", "C:Core.esm", "..", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                m.safe_name(name)


if __name__ == "__main__":
    unittest.main()
