"""scripts/terrain/light_patch.py: LIGH lumens scaled as a raw patch on a synthetic plugin (two LIGH, other records);
check proves the two files differ only in those four bytes per LIGH."""
import contextlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import light_patch as lp  # noqa: E402
import vmad_patch as vp  # noqa: E402

OWN = 0x01000000


def dat2(lumens, radius=100.0):
    d = bytearray(58)
    struct.pack_into("<f", d, 4, radius)
    d[8:11] = bytes((255, 200, 100))
    struct.pack_into("<I", d, 52, lumens)
    d[56] = 1
    return bytes(d)


def plugin(lumens=(2827, 1), compressed=False):
    ligh = [vp.record_bytes(b"LIGH", OWN | (0x900 + i), 0x40000 if compressed and i == 1 else 0,
                            [(b"EDID", f"Light{i}\0".encode()), (b"DAT2", dat2(v))]) for i, v in enumerate(lumens)]
    stat = vp.record_bytes(b"STAT", OWN | 0x800, 0, [(b"EDID", b"Stat\0"), (b"MODL", b"a.nif\0")])
    refr = vp.record_bytes(b"REFR", OWN | 0x801, 0, [(b"NAME", struct.pack("<I", OWN | 0x800)),
                                                  (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0))])
    groups = [vp.Group(b"STAT", 0, bytes(8), [stat]), vp.Group(b"LIGH", 0, bytes(8), ligh),
              vp.Group(b"REFR", 0, bytes(8), [refr])]
    tes4 = vp.record_bytes(b"TES4", 0, 1, [(b"HEDR", struct.pack("<fII", 0.96, 4, 0x910)), (b"MAST", b"Starfield.esm\0")])
    return tes4.serialize() + b"".join(g.serialize() for g in groups)


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = lp.main(list(argv))
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
            if isinstance(e.code, str):
                err.write(e.code)
    return code, out.getvalue(), err.getvalue()


class LightPatchBoundsTests(unittest.TestCase):
    def assert_refused(self, raw):
        with tempfile.TemporaryDirectory() as folder:
            src, dst = os.path.join(folder, "source.esm"), os.path.join(folder, "output.esm")
            with open(src, "wb") as stream:
                stream.write(raw)
            code, _out, _err = run("scale", "--in", src, "--out", dst, "--factor", "0.375")
            self.assertNotEqual(code, 0)
            self.assertFalse(os.path.exists(dst), "malformed input must not publish output")
            code, out, _err = run("check", "--a", src, "--b", src, "--factor", "1")
            self.assertNotEqual(code, 0, out)
            self.assertNotIn("CHECK PASS", out)
            with open(src, "rb") as stream:
                self.assertEqual(stream.read(), raw)

    @staticmethod
    def raw_light(payload):
        header = vp.record_bytes(b"TES4", 0, 1, [(b"HEDR", struct.pack("<fII", 0.96, 2, 0x902))]).serialize()
        record = bytearray(vp.record_bytes(b"LIGH", OWN | 0x900, 0, []).serialize())
        struct.pack_into("<I", record, 4, len(payload))
        neighbor = vp.record_bytes(b"STAT", OWN | 0x901, 0, [(b"DATA", bytes([17]) * 120)]).serialize()
        return header + record + payload + neighbor

    def test_dat2_cannot_write_into_following_non_light_record(self):
        # The old parser treats four bytes of the following STAT as light lumens.
        self.assert_refused(self.raw_light(b"DAT2" + struct.pack("<H", 58)))

    def test_validate_fields_after_dat2_instead_of_stopping_early(self):
        valid = b"DAT2" + struct.pack("<H", 58) + dat2(2827)
        for tail in (b"BAD", b"JUNK" + struct.pack("<H", 100), b"XXXX" + struct.pack("<H", 4) + bytes(4)):
            with self.subTest(tail=tail):
                self.assert_refused(self.raw_light(valid + tail))

    def test_duplicate_dat2_is_ambiguous(self):
        field = b"DAT2" + struct.pack("<H", 58) + dat2(2827)
        self.assert_refused(self.raw_light(field + field))

    def test_truncated_tes4_header_or_payload(self):
        self.assert_refused(b"TES4")
        self.assert_refused(plugin()[:24])

    def test_trailing_partial_record_header(self):
        self.assert_refused(plugin() + b"LIGH")

    def test_record_payload_cannot_extend_outside_its_group(self):
        raw = bytearray(plugin())
        off = next(off for sig, off, _size, _flags, _fid in lp.walk(raw) if sig == "LIGH")
        struct.pack_into("<I", raw, off + 4, len(raw) - off - 24)
        self.assert_refused(raw)

    def test_groups_cannot_overlap_parent_or_make_no_progress(self):
        raw = plugin()
        off = next(off for sig, off, _size, _flags, _fid in lp.walk(raw) if sig == "GRUP")
        for size in (0, 23, len(raw) + 1):
            with self.subTest(size=size):
                bad = bytearray(raw)
                struct.pack_into("<I", bad, off + 4, size)
                self.assert_refused(bad)

    def test_record_payload_cannot_extend_beyond_file(self):
        raw = bytearray(plugin())
        off = next(off for sig, off, _size, _flags, _fid in lp.walk(raw) if sig == "LIGH")
        struct.pack_into("<I", raw, off + 4, len(raw))
        self.assert_refused(raw)

    def test_valid_fields_after_dat2_remain_unchanged(self):
        raw = self.raw_light(b"DAT2" + struct.pack("<H", 58) + dat2(2827) + b"JUNK" + struct.pack("<H", 3) + b"abc")
        with tempfile.TemporaryDirectory() as folder:
            src, dst = os.path.join(folder, "source.esm"), os.path.join(folder, "output.esm")
            with open(src, "wb") as stream:
                stream.write(raw)
            self.assertEqual(run("scale", "--in", src, "--out", dst, "--factor", "0.375")[0], 0)
            self.assertEqual(run("check", "--a", src, "--b", dst, "--factor", "0.375")[0], 0)
            with open(dst, "rb") as stream:
                result = stream.read()
            self.assertIn(b"JUNK\x03\x00abc", result)


class LightPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "a.esm")
        self.dst = os.path.join(self.tmp.name, "b.esm")
        self.raw = plugin()
        with open(self.src, "wb") as f:
            f.write(self.raw)

    def lumens(self, path):
        with open(path, "rb") as f:
            buf = f.read()
        return [struct.unpack_from("<I", buf, off)[0] for off, _ in lp.lumens_windows(buf, lp.walk(buf))]

    def test_rule(self):
        self.assertEqual([lp.scaled(v, 0.375) for v in (2827, 1, 2, 8000, 75000)], [1060, 1, 1, 3000, 28125])

    def test_scale_then_check_passes(self):
        code, out, _ = run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.lumens(self.dst), [1060, 1])
        with open(self.dst, "rb") as f:
            new = f.read()
        self.assertEqual(len(new), len(self.raw))
        self.assertEqual(sum(1 for x, y in zip(self.raw, new) if x != y), 2)       # 2827 -> 1060 changes two bytes
        code, out, _ = run("check", "--a", self.src, "--b", self.dst, "--factor", "0.375")
        self.assertEqual(code, 0, out)
        self.assertIn("LIGH 2", out)
        self.assertIn("CHECK PASS", out)

    def test_check_fails_on_a_non_ligh_byte(self):
        run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375")
        with open(self.dst, "rb") as f:
            buf = bytearray(f.read())
        i = buf.index(b"a.nif")
        buf[i] ^= 0x20
        bad = os.path.join(self.tmp.name, "bad.esm")
        with open(bad, "wb") as f:
            f.write(buf)
        code, out, _ = run("check", "--a", self.src, "--b", bad, "--factor", "0.375")
        self.assertEqual(code, 1)
        self.assertIn("outside any LIGH", out)

    def test_check_fails_on_a_wrong_value_a_wrong_factor_and_a_wrong_size(self):
        run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375")
        code, out, _ = run("check", "--a", self.src, "--b", self.dst, "--factor", "0.5")
        self.assertEqual(code, 1)
        self.assertIn("rule gives", out)
        short = os.path.join(self.tmp.name, "short.esm")
        with open(short, "wb") as f:
            f.write(self.raw[:-8])
        self.assertEqual(run("check", "--a", self.src, "--b", short, "--factor", "0.375")[0], 1)

    def test_check_fails_when_the_files_are_identical_but_the_factor_is_not_one(self):
        self.assertEqual(run("check", "--a", self.src, "--b", self.src, "--factor", "0.375")[0], 1)

    def test_refuses_existing_out_and_out_equal_in(self):
        with open(self.dst, "wb") as f:
            f.write(b"keep")
        code, _, err = run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375")
        self.assertNotEqual(code, 0)
        self.assertIn("exists", err)
        with open(self.dst, "rb") as f:
            self.assertEqual(f.read(), b"keep")
        code, _, err = run("scale", "--in", self.src, "--out", self.src, "--factor", "0.375")
        self.assertNotEqual(code, 0)
        with open(self.src, "rb") as f:
            self.assertEqual(f.read(), self.raw)

    def test_refuses_a_compressed_ligh(self):
        with open(self.src, "wb") as f:
            f.write(plugin(compressed=True))
        code, _, err = run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375")
        self.assertNotEqual(code, 0)
        self.assertIn("compressed", err)
        self.assertFalse(os.path.exists(self.dst))

    def test_objects_are_scaled_with_lumens_scale(self):
        objs = os.path.join(self.tmp.name, "objects.json")
        out = os.path.join(self.tmp.name, "objects_l.json")
        doc = {"world": "W", "lumens_per_m2": 333.0, "lights": [{"src": "x"}],
               "light_bases": [{"edid": "Light0", "lumens": 2827, "radius": 100.0}, {"edid": "Light1", "lumens": 1}]}
        with open(objs, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        code, text, _ = run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375", "--objects", objs,
                            "--objects-out", out)
        self.assertEqual(code, 0, text)
        with open(out, encoding="utf-8") as f:
            new = json.load(f)
        self.assertEqual([b["lumens"] for b in new["light_bases"]], [1060, 1])
        self.assertEqual(new["lumens_scale"], 0.375)
        self.assertEqual({k: v for k, v in new.items() if k not in ("light_bases", "lumens_scale")},
                         {k: v for k, v in doc.items() if k != "light_bases"})
        self.assertEqual(new["light_bases"][0]["radius"], 100.0)
        with open(objs, encoding="utf-8") as f:
            self.assertEqual(json.load(f), doc)                                      # the input is untouched
        # objects.json lumens agree with the patched plugin's, which is what make_core64c.py check compares
        self.assertEqual([b["lumens"] for b in new["light_bases"]], self.lumens(self.dst))
        # a second run must not overwrite the objects copy
        os.remove(self.dst)
        code, _, err = run("scale", "--in", self.src, "--out", self.dst, "--factor", "0.375", "--objects", objs,
                           "--objects-out", out)
        self.assertNotEqual(code, 0)
        self.assertFalse(os.path.exists(self.dst))


if __name__ == "__main__":
    unittest.main()
