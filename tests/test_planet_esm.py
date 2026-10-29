"""src/fo4sf/planet/esm.py: the raw plugin reader and writer the planet master is written with, on synthetic bytes
only (no game file): records with and without compression, XXXX sizes, nested groups, the header and the walk."""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.planet import esm  # noqa: E402


class SubrecordTests(unittest.TestCase):
    def test_round_trip_and_xxxx_for_a_long_field(self):
        subs = [(b"EDID", esm.zbytes("Probe")), (b"PCCC", bytes(range(256)) * 300), (b"DNAM", b"\x01\x02")]
        data = esm.pack_subrecords(subs)
        self.assertIn(b"XXXX", data[:40])
        self.assertEqual(esm.parse_subrecords(data), subs)

    def test_truncated_and_dangling_xxxx_are_refused(self):
        with self.assertRaises(esm.EsmError):
            esm.parse_subrecords(b"EDID\x05\x00ab")
        with self.assertRaises(esm.EsmError):
            esm.parse_subrecords(b"XXXX\x04\x00" + struct.pack("<I", 9))
        with self.assertRaises(esm.EsmError):
            esm.pack_subrecords([(b"TOOLONG", b"")])

    def test_zstring(self):
        self.assertEqual(esm.zstring(b"Jemison\0junk"), "Jemison")
        self.assertEqual(esm.zbytes("Sol"), b"Sol\0")


class RecordTests(unittest.TestCase):
    def test_compressed_record_round_trip(self):
        r = esm.Record(b"PNDT", 0x01000805, [(b"EDID", esm.zbytes("X")), (b"PCCC", bytes(5000))],
                       flags=esm.COMPRESSED, vc=7, version=0x245, unknown=8)
        raw = r.to_bytes()
        sig, size, flags = struct.unpack_from("<4sII", raw)
        self.assertEqual((sig, flags & esm.COMPRESSED), (b"PNDT", esm.COMPRESSED))
        self.assertLess(size, 5000)
        back = esm.Record.parse(raw, 0)
        self.assertEqual((back.formid, back.vc, back.version, back.unknown, back.subs),
                         (r.formid, 7, 0x245, 8, r.subs))
        plain = esm.Record.parse(r.to_bytes(compress=False), 0)
        self.assertFalse(plain.flags & esm.COMPRESSED)
        self.assertEqual(plain.subs, r.subs)

    def test_bad_compression_is_refused(self):
        raw = bytearray(esm.Record(b"STAT", 1, [(b"EDID", b"a\0")], flags=esm.COMPRESSED).to_bytes())
        raw[28:30] = b"\0\0"
        with self.assertRaises(esm.EsmError):
            esm.Record.parse(bytes(raw), 0)

    def test_access(self):
        r = esm.Record(b"LCTN", 5, [(b"EDID", b"Loc\0"), (b"KWDA", b"1"), (b"KWDA", b"2")])
        self.assertEqual((r.edid, r.get(b"KWDA"), r.all("KWDA"), r.index(b"KWDA", 2), r.get(b"NONE", 3)),
                         ("Loc", b"1", [b"1", b"2"], 2, 3))
        c = r.copy(9)
        c.subs.append((b"DATA", b""))
        self.assertEqual((c.formid, len(r.subs)), (9, 3))


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_writer_header_masters_group_order_and_reader(self):
        w = esm.PluginWriter(["Starfield.esm"], esm.ESM, author="test")
        w.add(esm.Record(b"STDT", w.own(0x800), [(b"EDID", b"Star\0")]))
        w.add(esm.Record(b"LCTN", w.own(0x801), [(b"EDID", b"Loc\0")]))
        w.add(esm.Record(b"KYWD", 0x000123, [(b"EDID", b"Kw\0")]))
        w.write(self.path("a.esm"))
        with esm.Plugin(self.path("a.esm")) as p:
            self.assertEqual((p.masters, p.flags & esm.ESM, p.localized, p.self_index), (["Starfield.esm"], 1, False, 1))
            self.assertEqual(list(p.groups), ["KYWD", "LCTN", "STDT"])     # xEdit's group order
            hedr = p.header.get(b"HEDR")
            self.assertEqual(struct.unpack("<fII", hedr)[1:], (6, 0x802))
            self.assertEqual(p.header.version, esm.HEADER_FORM_VERSION)
            self.assertEqual([r.edid for r in p.records("STDT")], ["Star"])
            self.assertEqual([r.formid for r in p.records("LCTN", ["LCTN"])], [0x01000801])

    def test_walk_nested_groups_and_type_filter(self):
        inner = esm.Record(b"REFR", 0x10, [(b"NAME", b"\0\0\0\0")]).to_bytes()
        cell = esm.Record(b"CELL", 0x11, [(b"EDID", b"C\0")]).to_bytes()
        payload = (esm.Record(b"WRLD", 0x12, [(b"EDID", b"W\0")]).to_bytes()
                   + esm.group_bytes(struct.pack("<I", 0x12), cell + esm.group_bytes(
                       struct.pack("<I", 0x11), esm.group_bytes(struct.pack("<I", 0x11), inner, 9), 6), 1))
        w = esm.PluginWriter([], esm.ESM)
        with open(self.path("b.esm"), "wb") as f:
            f.write(w.to_bytes() + esm.group_bytes("WRLD", payload))
        with esm.Plugin(self.path("b.esm")) as p:
            start, end = p.groups["WRLD"][0]
            items = list(p.walk(start, end))
            self.assertEqual([(i[0], i[2] if i[0] == "REC" else i[2]) for i in items],
                             [("REC", b"WRLD"), ("GRUP", 1), ("REC", b"CELL"), ("GRUP", 6), ("GRUP", 9), ("REC", b"REFR")])
            top = list(p.walk(start, end, groups=set()))
            self.assertEqual([i[0] for i in top], ["REC", "GRUP"])
            self.assertEqual(p.record_at(items[-1][1]).formid, 0x10)

    def test_not_a_plugin_and_bad_groups(self):
        with open(self.path("c.esm"), "wb") as f:
            f.write(b"nope" + bytes(40))
        with self.assertRaises(esm.EsmError):
            esm.Plugin(self.path("c.esm"))
        with open(self.path("d.esm"), "wb") as f:
            f.write(b"")
        with self.assertRaises(esm.EsmError):
            esm.Plugin(self.path("d.esm"))
        w = esm.PluginWriter([], esm.ESM)
        with open(self.path("e.esm"), "wb") as f:
            f.write(w.to_bytes() + b"GRUP" + struct.pack("<I", 99) + b"STAT" + bytes(12))
        with self.assertRaises(esm.EsmError):
            esm.Plugin(self.path("e.esm"))


if __name__ == "__main__":
    unittest.main()
