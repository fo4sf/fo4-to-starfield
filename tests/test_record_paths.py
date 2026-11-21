"""Read-only group ancestry: synthetic nested/sibling groups, identities and refusal controls."""
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
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
import ref_inspect as reader  # noqa: E402
from fo4sf.planet import esm  # noqa: E402


def form_group(fid, payload, gtype):
    return esm.group_bytes(struct.pack("<I", fid), payload, gtype)


def fixture(duplicate=False):
    header = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"]).to_bytes()
    # Payload deliberately is not a zlib stream: header-only inspection must not decode it.
    opaque = struct.pack("<4sIIIIHH", b"REFR", 7, esm.COMPRESSED | esm.PERSISTENT, 0x010A775B, 0, 581, 0) + b"opaque!"
    own = esm.Record("REFR", 0x02000901).to_bytes()
    temp = esm.Record("REFR", 0x02000902).to_bytes()
    cell = esm.Record("CELL", 0x01001805).to_bytes()
    children = form_group(0x01001805, opaque + own, 8) + form_group(0x01001805, temp, 9)
    first = esm.Record("WRLD", 0x01000803).to_bytes() + form_group(0x01000803, cell + form_group(0x01001805, children, 6), 1)
    # A new world and cell after the first tree: no ancestor may leak from a previous sibling.
    other = esm.Record("REFR", 0x00000901).to_bytes()
    if duplicate:
        other += own
    second = esm.Record("WRLD", 0x0002DF8C).to_bytes() + form_group(0x0002DF8C,
        esm.Record("CELL", 0x003E5E10).to_bytes() + form_group(0x003E5E10, form_group(0x003E5E10, other, 8), 6), 1)
    flat = esm.group_bytes("LCTN", esm.Record("LCTN", 0x01000802).to_bytes())
    return header + esm.group_bytes("WRLD", first + second) + flat


class RecordPathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "Markers.esm")
        self.data = fixture()
        self.write(self.data)

    def write(self, data):
        with open(self.path, "wb") as f:
            f.write(data)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "terrain", "ref_inspect.py"),
                               "--plugin", self.path, *args], capture_output=True, text=True)

    def test_exact_root_to_record_path_offsets_and_qualified_identities(self):
        digest = hashlib.sha256(self.data).hexdigest()
        report = reader.record_paths(self.path, [0x010A775B, 0x02000901], digest)
        self.assertEqual(report["sha256"], digest)
        self.assertEqual(report["sha256_after"], digest)
        self.assertEqual(report["masters"], ["Starfield.esm", "FO4TerrainCore.esm"])
        core, own = report["records"]
        self.assertEqual(core["record"], {"stored_id": "010A775B", "plugin": "FO4TerrainCore.esm", "local_id": "0A775B"})
        self.assertEqual(own["record"]["plugin"], "Markers.esm")
        self.assertEqual(core["signature"], "REFR")
        self.assertEqual(core["flags"], "00040400")
        self.assertEqual([g["type"] for g in core["groups"]], [0, 1, 6, 8])
        self.assertEqual([g["label_form"]["stored_id"] for g in core["groups"][1:]], ["01000803", "01001805", "01001805"])
        self.assertEqual(core["groups"][0]["label_text"], "WRLD")
        self.assertEqual(core["groups"], own["groups"])
        for row in (core, own):
            offset = row["offset"]
            self.assertEqual(self.data[offset:offset + 4], b"REFR")
            self.assertEqual(struct.unpack_from("<I", self.data, offset + 12)[0], int(row["record"]["stored_id"], 16))
            for group in row["groups"]:
                off = group["offset"]
                self.assertEqual(self.data[off:off + 4], b"GRUP")
                self.assertEqual(group["label_hex"], self.data[off + 8:off + 12].hex())
                self.assertEqual(off + struct.unpack_from("<I", self.data, off + 4)[0], group["end_offset"])
                self.assertLess(off, offset)
                self.assertGreaterEqual(group["end_offset"], row["end_offset"])

    def test_sibling_world_and_group_type_dont_inherit_previous_ancestors(self):
        report = reader.record_paths(self.path, [0x02000902, 0x00000901, 0x01000802])
        temp, other, flat = report["records"]
        self.assertEqual([g["type"] for g in temp["groups"]], [0, 1, 6, 9])
        self.assertEqual(other["record"]["plugin"], "Starfield.esm")  # same low id as own TEST2, different stored identity
        self.assertEqual([g["label_form"]["stored_id"] for g in other["groups"][1:]], ["0002DF8C", "003E5E10", "003E5E10"])
        self.assertEqual(len(flat["groups"]), 1)
        self.assertEqual(flat["groups"][0]["label_text"], "LCTN")

    def test_grid_and_block_labels_are_raw_not_mistaken_for_form_ids(self):
        ref = esm.Record("REFR", 0x02000901).to_bytes()
        block = form_group(0x01000803, ref, 4)  # bytes look like a form ID; this group type does not use one
        self.write(esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"]).to_bytes() + esm.group_bytes("WRLD", block))
        group = reader.record_paths(self.path, [0x02000901])["records"][0]["groups"][-1]
        self.assertEqual(group["label_hex"], "03080001")
        self.assertNotIn("label_form", group)

    def test_unknown_master_label_stays_explicitly_unqualified(self):
        ref = esm.Record("REFR", 0x02000901).to_bytes()
        self.write(esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"]).to_bytes() + esm.group_bytes("WRLD", form_group(0xFF000803, ref, 1)))
        label = reader.record_paths(self.path, [0x02000901])["records"][0]["groups"][-1]["label_form"]
        self.assertIn("qualification_error", label)
        self.assertNotIn("plugin", label)

    def test_missing_duplicate_and_runtime_targets_refuse(self):
        with self.assertRaisesRegex(ValueError, "0 matches"):
            reader.record_paths(self.path, [0x02000999])
        with self.assertRaisesRegex(ValueError, "cannot qualify"):
            reader.record_paths(self.path, [0xFF000901])
        self.write(fixture(duplicate=True))
        with self.assertRaisesRegex(ValueError, "2 matches"):
            reader.record_paths(self.path, [0x02000901])

    def test_wrong_hash_malformed_hash_and_changed_mapping_refuse(self):
        with self.assertRaisesRegex(ValueError, "pinned input"):
            reader.record_paths(self.path, [0x02000901], "0" * 64)
        with self.assertRaisesRegex(ValueError, "64 hex"):
            reader.record_paths(self.path, [0x02000901], "short")
        with patch.object(reader.hashlib, "sha256") as h:
            h.return_value.hexdigest.side_effect = ["a" * 64, "b" * 64]
            with self.assertRaisesRegex(ValueError, "changed during"):
                reader.record_paths(self.path, [0x02000901])

    def test_malformed_nested_group_never_yields_a_partial_success(self):
        # Nested size exceeds its parent even though the bytes still fit in the entire file.
        buf = bytearray(self.data)
        group = reader.record_paths(self.path, [0x010A775B])["records"][0]["groups"][-1]
        struct.pack_into("<I", buf, group["offset"] + 4, len(buf) - group["offset"])
        self.write(buf)
        result = self.cli("--record-path", "010A775B")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("bad group", result.stderr)

    def test_cli_requires_explicit_full_ids_and_reports_without_writing(self):
        before = os.stat(self.path)
        result = self.cli("--record-path", "010A775B", "--record-path", "02000901", "--expect-sha256", hashlib.sha256(self.data).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["records"]), 2)
        self.assertEqual(os.listdir(self.tmp.name), ["Markers.esm"])
        after = os.stat(self.path)
        self.assertEqual((before.st_size, before.st_mtime_ns), (after.st_size, after.st_mtime_ns))
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), self.data)
        for args in [("--record-path", "901"), ("--record-path", "100000901"), ("--record-path", "-0000901"),
                     ("--ref", "901", "--record-path", "02000901"), ("--ref", "901", "--expect-sha256", "0" * 64)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.cli(*args).returncode, 0)


if __name__ == "__main__":
    unittest.main()
