"""Same-ids check (src/fo4sf/launcher/same_ids.py) on synthetic plugins written here; no game files."""
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import same_ids  # noqa: E402


def sub(typ, data):
    if len(data) > 0xFFFF:              # XXXX carries the real size, the subrecord's own u16 is 0
        return b"XXXX" + struct.pack("<HI", 4, len(data)) + typ.encode() + struct.pack("<H", 0) + data
    return typ.encode() + struct.pack("<H", len(data)) + data


def record(typ, formid, subs, stamp=0, compress=False, flags=0):
    body = b"".join(sub(t, d) for t, d in subs)
    if compress:
        body = struct.pack("<I", len(body)) + zlib.compress(body)
        flags |= same_ids.COMPRESSED
    return typ.encode() + struct.pack("<IIIIHH", len(body), flags, formid, stamp, 131, 0) + body


def grup(label, records):
    inner = b"".join(records)
    return b"GRUP" + struct.pack("<I", 24 + len(inner)) + label.encode() + struct.pack("<IHHHH", 0, 0, 0, 0, 0) + inner


def plugin(recs, hedr_next=0x800, stamp_tes4=0):
    tes4 = record("TES4", 0, [("HEDR", struct.pack("<fII", 0.96, len(recs), hedr_next)),
                               ("MAST", b"Starfield.esm\0")], stamp=stamp_tes4)
    return tes4 + grup("STAT", recs)


def stat(formid, edid, model=b"a.nif", **kw):
    return record("STAT", formid, [("EDID", edid.encode() + b"\0"), ("MODL", model + b"\0")], **kw)


class SameIdsTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.a, self.b = os.path.join(t.name, "a"), os.path.join(t.name, "b")
        os.makedirs(self.a)
        os.makedirs(self.b)

    def write(self, side, name, data):
        with open(os.path.join(side, name), "wb") as f:
            f.write(data)

    def base(self, **kw):
        return [stat(0x01000800, "FO4Core_a", **kw), stat(0x01000801, "FO4Core_b")]

    def test_identical_bytes(self):
        for side in (self.a, self.b):
            self.write(side, "P.esm", plugin(self.base()))
        rep = same_ids.check(self.a, self.b)
        self.assertEqual(rep["verdict"], "IDENTICAL")

    def test_timestamp_only_is_same_ids_with_metadata_explained(self):
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base(stamp=0x1234)))
        rep = same_ids.check(self.a, self.b)
        e = rep["plugins"]["P.esm"]
        self.assertEqual(rep["verdict"], "SAME_IDS")
        self.assertEqual((e["metadata"]["count"], e["content"]["count"]), (1, 0))
        self.assertEqual(e["metadata"]["examples"], ["01000800"])

    def test_content_change_keeps_ids(self):
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base(model=b"other.nif")))
        e = same_ids.check(self.a, self.b)["plugins"]["P.esm"]
        self.assertEqual(e["verdict"], "SAME_IDS")
        self.assertEqual(e["content"]["count"], 1)

    def test_tes4_header_difference_is_listed(self):
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base(), hedr_next=0x900))
        e = same_ids.check(self.a, self.b)["plugins"]["P.esm"]
        self.assertEqual(e["verdict"], "SAME_IDS")
        self.assertEqual(sorted(e["tes4"]), ["HEDR"])

    def test_editor_id_on_another_formid_differs(self):
        self.write(self.a, "P.esm", plugin([stat(0x01000800, "X"), stat(0x01000801, "Y")]))
        self.write(self.b, "P.esm", plugin([stat(0x01000800, "Y"), stat(0x01000801, "X")]))
        rep = same_ids.check(self.a, self.b)
        e = rep["plugins"]["P.esm"]
        self.assertEqual(rep["verdict"], "IDS_DIFFER")
        self.assertEqual(e["ids"]["edid_moved"], 2)
        self.assertIn("X: 01000800 -> 01000801", e["ids"]["examples"]["edid_moved"])

    def test_extra_record_differs(self):
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base() + [stat(0x01000802, "FO4Core_c")]))
        rep = same_ids.check(self.a, self.b)
        self.assertEqual(rep["verdict"], "IDS_DIFFER")
        self.assertEqual(rep["plugins"]["P.esm"]["ids"]["only_b"], 1)

    def test_compressed_record_is_inflated_and_compared(self):
        self.write(self.a, "P.esm", plugin([stat(0x01000800, "Z")]))
        self.write(self.b, "P.esm", plugin([stat(0x01000800, "Z", compress=True)]))
        e = same_ids.check(self.a, self.b)["plugins"]["P.esm"]
        self.assertEqual(e["verdict"], "SAME_IDS")
        self.assertEqual(e["content"]["count"], 0)       # same inflated body
        self.assertEqual(e["metadata"]["count"], 0)      # the compressed flag itself is not metadata

    def test_large_subrecord_with_xxxx(self):
        big = b"q" * 70000
        rec = record("STAT", 0x01000800, [("EDID", b"Big\0"), ("DATA", big)])
        self.write(self.a, "P.esm", plugin([rec]))
        parsed = same_ids.read_plugin(os.path.join(self.a, "P.esm"))
        self.assertEqual(parsed["records"][0x01000800]["edid"], "Big")

    def test_plugin_in_one_build_only_is_incomplete(self):
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base()))
        self.write(self.a, "Q.esm", plugin(self.base()))
        rep = same_ids.check(self.a, self.b)
        self.assertEqual(rep["verdict"], "INCOMPLETE")

    def test_truncated_plugin_is_incomplete_not_a_crash(self):
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base())[:-5])
        self.assertEqual(same_ids.check(self.a, self.b)["verdict"], "INCOMPLETE")

    def test_formids_json_difference_fails_even_with_identical_plugins(self):
        for side, ref in ((self.a, "00D9B8"), (self.b, "00D9B9")):
            self.write(side, "P.esm", plugin(self.base()))
            with open(os.path.join(side, "formids.json"), "w") as f:
                json.dump({"doors": {"src1": {"ref": ref}}}, f)
        rep = same_ids.check(self.a, self.b)
        self.assertEqual(rep["verdict"], "IDS_DIFFER")
        self.assertEqual(rep["formids_json"]["doors"]["status"], "changed")

    def test_cli_exit_codes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.write(self.a, "P.esm", plugin(self.base()))
        self.write(self.b, "P.esm", plugin(self.base(stamp=7)))
        out = os.path.join(self.a, "..", "rep.json")
        self.assertEqual(cli.main(["same-ids", self.a, self.b, "--report", out]), 0)
        self.assertTrue(os.path.isfile(out))
        self.write(self.b, "P.esm", plugin([stat(0x01000900, "FO4Core_a")]))
        self.assertEqual(cli.main(["same-ids", self.a, self.b]), 1)


if __name__ == "__main__":
    unittest.main()
