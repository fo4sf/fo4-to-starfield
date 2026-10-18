"""scripts/slice/persistent_refs.py on a synthetic plugin: the GRUP walk finds a world's persistent cell (its record
flags, subrecords, XCLC), the references in it, an exterior cell's persistent and temporary children, and given refs.
Synthetic bytes only (docs/slice/door-frames.md section 3)."""
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "slice"))
import persistent_refs as pr  # noqa: E402


def sr(typ, payload):
    return typ.encode() + struct.pack("<H", len(payload)) + payload


def rec(typ, fid, flags, subs, compress=False):
    data = b"".join(subs)
    if compress:
        data = struct.pack("<I", len(data)) + zlib.compress(data)
        flags |= 0x40000
    return typ.encode() + struct.pack("<IIIIHH", len(data), flags, fid, 0, 0, 0) + data


def grup(label, gtype, body):
    return b"GRUP" + struct.pack("<IIIII", 24 + len(body), label, gtype, 0, 0) + body


def refr(fid, base, pos, flags=0x400, edid=None):
    subs = ([sr("EDID", edid.encode() + b"\0")] if edid else []) + [sr("NAME", struct.pack("<I", base)),
                                                                     sr("DATA", struct.pack("<6f", *pos, 0, 0, 0))]
    return rec("REFR", fid, flags, subs)


def plugin(vanilla_shape):
    """One world 'W' (0x01000801): its persistent cell (vanilla-shaped or ours) holding an anchor, and exterior cell
    (-10, 11) with one persistent and one temporary marker."""
    head = rec("TES4", 0, 1, [sr("HEDR", b"\0" * 12), sr("MAST", b"Starfield.esm\0"), sr("DATA", b"\0" * 8)])
    wrld = rec("WRLD", 0x01000801, 0, [sr("EDID", b"W\0"), sr("DATA", b"\0")])
    if vanilla_shape:
        pcell = rec("CELL", 0x01000802, 0x400, [sr("DATA", b"\x02\0\0\0"),
                                                sr("XCLC", struct.pack("<ii", 0x7FFFFFFF, 0x7FFFFFFF) + b"\0" * 4),
                                                sr("LTMP", b"\0" * 4), sr("XCLW", b"\xff\xff\x7f\x7f"),
                                                sr("XILS", struct.pack("<f", 1.0))], compress=True)
    else:
        pcell = rec("CELL", 0x01000802, 0, [sr("DATA", b"\x02\0\0\0")])
    pchildren = grup(0x01000802, 6, grup(0x01000802, 8, refr(0x01000800, 0x3B, (-989.0, 1146.5, 105.1), edid="Anchor")))
    ecell = rec("CELL", 0x01000803, 0, [sr("DATA", b"\0\0\0\0"), sr("XCLC", struct.pack("<ii", -10, 11) + b"\0" * 4)])
    echildren = grup(0x01000803, 6, grup(0x01000803, 8, refr(0x01000804, 0x3B, (-987.0, 1146.5, 105.1)))
                     + grup(0x01000803, 9, refr(0x01000805, 0x3B, (-985.0, 1146.5, 105.1), flags=0)))
    block = grup(0, 4, grup(0, 5, ecell + echildren))
    world = grup(0, 0, wrld + grup(0x01000801, 1, pcell + pchildren + block))
    return head + world


class PersistentRefsTests(unittest.TestCase):
    def walk(self, vanilla_shape, refs=()):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.esm")
        with open(p, "wb") as f:
            f.write(plugin(vanilla_shape))
        return pr.walk(p, ["W"], refs)

    def test_our_shape(self):
        rep = self.walk(False)
        w = rep["worlds"]["W"]
        self.assertEqual(rep["masters"], ["Starfield.esm"])
        self.assertEqual(w["persistent_cell"]["record_flags"], "0x0")
        self.assertEqual(w["persistent_cell"]["subrecords"], ["DATA"])
        self.assertIsNone(w["persistent_cell"]["grid"])
        self.assertEqual([(r["formid"], r["edid"], r["pos"]) for r in w["persistent_refs"]],
                         [("01000800", "Anchor", [-989.0, 1146.5, 105.1])])
        self.assertEqual([(r["formid"], r["cell_kind"], r["cell_grid"]) for r in w["exterior_persistent_refs"]],
                         [("01000804", "exterior", [-10, 11])])
        self.assertEqual(w["temporary_refs"], 1)

    def test_vanilla_shape_compressed(self):
        w = self.walk(True)["worlds"]["W"]
        pc = w["persistent_cell"]
        self.assertEqual(pc["record_flags"], "0x40400")
        self.assertEqual(pc["subrecords"], ["DATA", "XCLC", "LTMP", "XCLW", "XILS"])
        self.assertEqual(pc["grid"], [0x7FFFFFFF, 0x7FFFFFFF])
        self.assertEqual(pc["raw"]["XILS"], "0000803f")

    def test_given_refs_are_found_wherever_they_are(self):
        rep = self.walk(False, refs=["000805", "01000800"])
        got = {r["formid"]: (r["group"], r["persistent"], r["cell_kind"]) for r in rep["refs"]}
        self.assertEqual(got, {"01000805": ("temporary children", False, "exterior"),
                               "01000800": ("persistent children", True, "persistent")})

    def test_the_storage_counts_do_not_depend_on_the_refs_asked_for(self):
        # Codex's review of PR #107: asking for 000805 made W report 0 temporary refs although it listed the ref
        plain = self.walk(False)["worlds"]["W"]
        rep = self.walk(False, refs=["000805", "000804"])
        w = rep["worlds"]["W"]
        self.assertEqual((w["temporary_refs"], plain["temporary_refs"]), (1, 1))
        self.assertEqual([r["formid"] for r in rep["refs"]], ["01000804", "01000805"])
        self.assertEqual([r["formid"] for r in w["exterior_persistent_refs"]],
                         [r["formid"] for r in plain["exterior_persistent_refs"]])
        self.assertEqual(len(w["persistent_refs"]), len(plain["persistent_refs"]))

    def alias_report(self, refs):
        # Two genuinely different references share their low 24 bits. A native
        # master override is at x=10; this plugin's own reference is at x=20.
        head = rec("TES4", 0, 1, [sr("HEDR", b"\0" * 12), sr("MAST", b"Starfield.esm\0"), sr("DATA", b"\0" * 8)])
        cell = rec("CELL", 0x01000802, 0x400, [sr("DATA", b"\x02\0\0\0")])
        children = grup(0x01000802, 6, grup(0x01000802, 8,
            refr(0x00000800, 0x3B, (10, 0, 0), edid="MasterDoor") +
            refr(0x01000800, 0x3B, (20, 0, 0), edid="LocalDoor")))
        body = grup(0, 0, rec("WRLD", 0x01000801, 0, [sr("EDID", b"W\0")]) +
            grup(0x01000801, 1, cell + children))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "Synthetic.esm")
            with open(path, "wb") as stream:
                stream.write(head + body)
            return pr.walk(path, ["W"], refs)

    def test_local_selector_does_not_select_master_override_with_same_low_id(self):
        report = self.alias_report(["000800"])
        self.assertEqual([(r["formid"], r["pos"][0]) for r in report["refs"]], [("01000800", 20)])

    def test_exact_master_selector_does_not_select_local_reference(self):
        report = self.alias_report(["00000800"])
        self.assertEqual([(r["formid"], r["pos"][0]) for r in report["refs"]], [("00000800", 10)])

    def test_exact_local_and_mixed_selectors(self):
        self.assertEqual([r["formid"] for r in self.alias_report(["01000800"])["refs"]], ["01000800"])
        self.assertEqual([r["formid"] for r in self.alias_report(["00000800", "000800"])["refs"]],
                         ["00000800", "01000800"])
        self.assertEqual([r["formid"] for r in self.alias_report(["0x00000800"])["refs"]], ["00000800"])

    def test_ambiguous_or_invalid_selector_is_refused(self):
        for selector in ("0000800", "100000800", "-800", "+800", "", "GGGGGG"):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                self.alias_report([selector])


if __name__ == "__main__":
    unittest.main()
