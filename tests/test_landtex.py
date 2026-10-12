"""Synthetic tests for the ground-texture path: FO4 LAND texture layers (src/fo4sf/landtex.py), the BTD texture codec,
LZ4 blocks, texture previews, the FO4 -> Starfield table (ground_map) and the exp2t helpers in
scripts/terrain/ground_textures.py. Every byte is built here; no game data."""
import os
import struct
import sys
import tempfile
import unittest
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
from fo4sf import btd, fo4land, ground_map, landtex, lz4block, texpreview  # noqa: E402
import ground_textures as gt  # noqa: E402

Q = landtex.QUAD


def btxt(fid, quad, layer=-1):
    return b"BTXT", struct.pack("<IBBh", fid, quad, 0, layer)


def atxt(fid, quad, layer):
    return b"ATXT", struct.pack("<IBBH", fid, quad, 0, layer)


def vtxt(entries):
    """entries: [(row, col, opacity)] inside one quadrant (row 0 = south)."""
    return b"VTXT", b"".join(struct.pack("<HHf", r * Q + c, 0, a) for r, c, a in entries)


class Fo4Layers(unittest.TestCase):
    def test_parse_positions_quadrants_and_clipping(self):
        fields = [btxt(0x10, 0), atxt(0x20, 0, 0), vtxt([(0, 0, 0.5), (16, 3, 1.0), (2, 1, 1.7), (1, 1, -0.2)]),
                  btxt(0x11, 3), atxt(0x21, 3, 1), vtxt([(5, 6, 0.25)]),
                  (b"VTXT", struct.pack("<HHf", 289, 0, 1.0))]          # position past 17 x 17: ignored
        q = landtex.parse_land_textures(fields)
        self.assertEqual([x["base"] for x in q], [0x10, None, None, 0x11])
        layer, fid, a = q[0]["layers"][0]
        self.assertEqual((layer, fid), (0, 0x20))
        self.assertEqual((a[0, 0], a[16, 3], a[2, 1], a[1, 1]), (0.5, 1.0, 1.0, 0.0))
        self.assertEqual(float(q[3]["layers"][0][2][5, 6]), 0.25)
        self.assertEqual(q[1], {"base": None, "layers": []})

    def test_vtxt_before_any_atxt_is_ignored(self):
        q = landtex.parse_land_textures([vtxt([(0, 0, 1.0)]), btxt(5, 1)])
        self.assertEqual(q[1]["base"], 5)
        self.assertEqual(sum(len(x["layers"]) for x in q), 0)

    def test_over_compositing_by_layer_number(self):
        a1 = np.full((Q, Q), 0.5, np.float32)
        a2 = np.full((Q, Q), 0.25, np.float32)
        # file order 2, 1: layer numbers decide; layer 2 is drawn over layer 1
        quad = {"base": 0xB, "layers": [(2, 0xD, a2), (1, 0xC, a1)]}
        w = landtex.quadrant_weights(quad)
        self.assertAlmostEqual(float(w[0xB][0, 0]), 0.5 * 0.75)
        self.assertAlmostEqual(float(w[0xC][0, 0]), 0.5 * 0.75)
        self.assertAlmostEqual(float(w[0xD][0, 0]), 0.25)
        np.testing.assert_allclose(sum(w.values()), 1.0)

    def test_missing_base_and_null_layer_mean_default(self):
        a = np.full((Q, Q), 0.4, np.float32)
        w = landtex.quadrant_weights({"base": None, "layers": [(0, 0, a), (1, 7, a)]}, default=99)
        self.assertEqual(set(w), {99, 7})
        np.testing.assert_allclose(w[99], 0.6)          # (1 - 0.4) base + 0.4 default layer, both 'default' -> 0.6
        np.testing.assert_allclose(w[7], 0.4)

    def test_cell_weights_average_shared_quadrant_borders(self):
        quads = [{"base": 1, "layers": []}, {"base": 2, "layers": []}, {"base": 1, "layers": []},
                 {"base": 2, "layers": []}]
        w = landtex.cell_weights(quads)
        self.assertEqual(w[1].shape, (33, 33))
        np.testing.assert_allclose(w[1][:, :16], 1.0)
        np.testing.assert_allclose(w[1][:, 16], 0.5)        # column 16 belongs to quadrants 0 and 1
        np.testing.assert_allclose(w[2][:, 17:], 1.0)
        np.testing.assert_allclose(w[1] + w[2], 1.0)

    def test_decode_vclr(self):
        raw = bytes(range(256)) * 13
        v = landtex.decode_vclr(raw[:33 * 33 * 3])
        self.assertEqual(v.shape, (33, 33, 3))
        self.assertEqual(tuple(v[0, 1]), (3, 4, 5))
        with self.assertRaises(ValueError):
            landtex.decode_vclr(b"\0" * 10)

    def test_weight_grid_merges_keys_and_borders(self):
        g = landtex.WeightGrid(-1, 0, 2, 1, missing="def")
        ones = np.ones((33, 33))
        g.add_cell(-1, 0, {0xA: ones * 0.25, 0xB: ones * 0.75}, key=lambda f: "x")   # both map to one key
        g.add_cell(0, 0, {0xC: ones}, key=lambda f: "y")
        keys, w = g.finish()
        self.assertEqual(keys, ["x", "y"])
        self.assertEqual(w[0].shape, (33, 65))
        np.testing.assert_allclose(w[0][:, :32], 1.0)
        np.testing.assert_allclose(w[0][:, 32], 0.5)        # shared column of the two cells
        np.testing.assert_allclose(w[0] + w[1], 1.0)
        with self.assertRaises(ValueError):
            g.add_cell(5, 0, {0xA: ones})

    def test_weight_grid_missing_cells_get_default(self):
        g = landtex.WeightGrid(0, 0, 2, 1, missing="def")
        g.add_cell(0, 0, {"a": np.ones((33, 33))})
        keys, w = g.finish()
        d = dict(zip(keys, w))
        np.testing.assert_allclose(d["def"][:, 33:], 1.0)
        np.testing.assert_allclose(d["a"][:, :33], 1.0)


def onehot(idx, n, shape=(64, 64)):
    w = np.zeros((n,) + shape)
    w[idx] = 1.0
    return w


class BtdTextures(unittest.TestCase):
    def test_up_to_five_textures_last_slot_opaque_no_base_byte(self):
        n = 7
        wq = np.stack([np.full((64, 64), 0.25), np.full((64, 64), 0.75)])
        b, word = landtex.encode_quadrant(wq, [2, 6], n)
        self.assertEqual(list(b), [5, 1, 0, 0, 0, 0, 0, 0])            # value = n - table index, ascending index
        self.assertTrue(((word >> 3) & 7 == 7).all())                    # bottom slot alpha 7 (vanilla LC overlays)
        self.assertTrue((word & 7 == 2).all())                           # 0.25 * 7 = 1.75 -> 2

    def test_six_textures_base_in_byte_six(self):
        n = 9
        wq = np.full((6, 64, 64), 1 / 6)
        b, word = landtex.encode_quadrant(wq, [0, 1, 3, 4, 5, 8], n)
        self.assertEqual(list(b), [9, 8, 6, 5, 4, 0, 1, 0])
        self.assertTrue((word < (1 << 15)).all())
        dec = landtex.decode(np.frombuffer(b, np.uint8).reshape(1, 1, 8), word, n)
        np.testing.assert_allclose(dec[[0, 1, 3, 4, 5, 8]].mean(axis=(1, 2)), 1 / 6, atol=0.05)
        np.testing.assert_allclose(dec.sum(0), 1.0, atol=1e-6)

    def test_rejects_bad_quadrant_input(self):
        with self.assertRaises(ValueError):                 # not in ascending table order
            landtex.encode_quadrant(np.ones((2, 64, 64)) / 2, [3, 1], 4)
        with self.assertRaises(ValueError):                 # more than 6 textures
            landtex.encode_quadrant(np.ones((7, 64, 64)) / 7, list(range(7)), 8)

    def test_alpha_search_never_worse_than_rounding(self):
        rng = np.random.default_rng(7)
        w = rng.random((6, 64, 64)) ** 3
        w /= w.sum(0)
        q = landtex._alphas(w[:5], forced_bottom=False)
        rem, got = np.ones((64, 64)), []
        rq, rrem, rgot = np.zeros_like(q), np.ones((64, 64)), []
        for j in range(5):
            got.append(q[j] / 7 * rem)
            rem = rem * (1 - q[j] / 7)
            a = np.where(rrem > 1e-9, w[j] / np.maximum(rrem, 1e-9), 0)
            rq[j] = np.clip(np.rint(a * 7), 0, 7)
            rgot.append(rq[j] / 7 * rrem)
            rrem = rrem * (1 - rq[j] / 7)
        e_search = np.abs(np.stack(got + [rem]) - w).sum(0)
        e_round = np.abs(np.stack(rgot + [rrem]) - w).sum(0)
        self.assertTrue((e_search <= e_round + 1e-12).all())
        self.assertLess(float(e_search.mean()), float(e_round.mean()))

    def test_vanilla_pattern_reading(self):
        # lc172world pattern (6,5,4,3,2,0,1,0) with 7 LTEX: slots 0..4 = table 1..5, base = table 6 (byte 6)
        qb = np.array([6, 5, 4, 3, 2, 0, 1, 0], np.uint8)
        self.assertEqual(landtex.quadrant_textures(qb, 7), ([1, 2, 3, 4, 5], 6))
        # without byte 6 the last slot is the base (fo76utils getCellTextureSet)
        self.assertEqual(landtex.quadrant_textures(np.array([5, 4, 3, 2, 1, 0, 0, 0], np.uint8), 7),
                         ([2, 3, 4, 5, 6], 6))
        word = np.zeros((64, 64), np.uint16)
        word[:] = (7 << 0) | (3 << 3)              # slot 0 opaque on top: everything else hidden
        dec = landtex.decode(qb.reshape(1, 1, 8), word, 7)
        np.testing.assert_allclose(dec[1], 1.0)
        word[:] = 0                                # no alpha anywhere: the base shows
        dec = landtex.decode(qb.reshape(1, 1, 8), word, 7)
        np.testing.assert_allclose(dec[6], 1.0)
        word[:] = 7 << 12                          # slot 4 opaque, slots above transparent
        dec = landtex.decode(qb.reshape(1, 1, 8), word, 7)
        np.testing.assert_allclose(dec[5], 1.0)

    def test_round_trip_is_exact_for_one_hot_and_close_for_mixtures(self):
        n = 8
        rng = np.random.default_rng(3)
        W = np.zeros((n, 128, 192))
        # left quadrants one-hot, right ones smooth random mixtures of 4 textures
        W[:, :, :64] = onehot(3, n, (128, 64))
        W[2, :64, 64:128] = 1.0
        mix = rng.random((4, 128, 64)) ** 2
        mix /= mix.sum(0)
        W[[0, 4, 6, 7], :, 128:] = mix
        W[:, 64:, 64:128] = onehot(7, n, (64, 64))
        qm, words, st = landtex.encode(W, n)
        self.assertEqual(qm.shape, (2, 3, 8))
        self.assertEqual(st["dropped"], 0.0)
        dec = landtex.decode(qm, words, n)
        np.testing.assert_allclose(dec.sum(0), 1.0, atol=1e-6)
        np.testing.assert_allclose(dec[:, :, :128], W[:, :, :128], atol=1e-6)
        err = np.abs(dec - W).sum(0) / 2
        self.assertLess(float(err.mean()), 0.05)
        self.assertLessEqual(float(err.max()), 0.25)
        self.assertTrue(((qm[..., 5] == 0) & (qm[..., 7] == 0)).all())

    def test_seventh_texture_is_dropped_and_renormalised(self):
        n = 7
        W = np.zeros((n, 64, 64))
        edges = [0, 10, 20, 30, 40, 50, 59, 64]               # seven stripes, texture 6 is the narrowest
        for i in range(7):
            W[i, :, edges[i]:edges[i + 1]] = 1.0
        qm, words, st = landtex.encode(W, n)
        tex, base = landtex.quadrant_textures(qm[0, 0], n)
        self.assertEqual(len(tex) + (base not in tex), 6)
        self.assertGreater(st["dropped"], 0)
        dec = landtex.decode(qm, words, n)
        np.testing.assert_allclose(dec.sum(0), 1.0, atol=1e-6)

    def test_table_order_rarest_first(self):
        self.assertEqual(landtex.table_order(["a", "b", "c"], {"a": 5.0, "b": 1.0, "c": 5.0}), ["b", "a", "c"])

    def test_written_btd_keeps_heights_and_carries_textures(self):
        ncx = ncy = 2
        yy, xx = np.mgrid[0:256, 0:256]
        raw = btd.quantize(5.0 + 0.03 * xx - 0.01 * yy, -100.0, 200.0)
        quad = np.zeros((4, 4, 8), np.uint8)
        quad[..., 0] = 1
        plain = btd.write(btd.Btd(6, -100.0, 200.0, [0x1235C2], raw, np.zeros_like(raw), quad))
        W = np.zeros((3, 256, 256))
        W[0, :, :100] = 1.0
        W[1, :, 100:] = 1.0
        W[2, 130:, :] = 0.5
        W /= W.sum(0)
        qm, words, _ = landtex.encode(W, 3)
        tex = btd.write(btd.Btd(6, -100.0, 200.0, [0xA, 0xB, 0xC], raw, words, qm))
        self.assertNotEqual(plain, tex)
        self.assertEqual(btd.height_digest(plain), btd.height_digest(tex))
        back = btd.read(tex)
        np.testing.assert_array_equal(back.heights_raw, raw)
        np.testing.assert_array_equal(back.quad_map, qm)
        np.testing.assert_array_equal(back.weights, words)
        self.assertEqual(back.ltex, [0xA, 0xB, 0xC])
        moved = raw.copy()
        moved[5, 5] += 1
        other = btd.write(btd.Btd(6, -100.0, 200.0, [0xA, 0xB, 0xC], moved, words, qm))
        d1, d2 = btd.height_digest(tex), btd.height_digest(other)
        self.assertNotEqual(d1["block_heights"], d2["block_heights"])
        self.assertEqual(d1["header"], d2["header"])


class Lz4(unittest.TestCase):
    def test_literals_only(self):
        self.assertEqual(lz4block.decompress(bytes([0x50]) + b"hello", 5), b"hello")

    def test_match_and_overlapping_run(self):
        # "abcd" literals, then match offset 4 length 4 (token low nibble 0), then 'x' + run of 9 'x' (offset 1)
        blk = bytes([0x40]) + b"abcd" + struct.pack("<H", 4) + bytes([0x15]) + b"x" + struct.pack("<H", 1) + \
            bytes([0x10]) + b"!"
        self.assertEqual(lz4block.decompress(blk, 4 + 4 + 1 + 9 + 1), b"abcdabcd" + b"x" * 10 + b"!")

    def test_long_lengths(self):
        lit = bytes(range(256)) * 2                       # 512 literals: 15 + 255 + 242
        blk = bytes([0xF0, 255, 242]) + lit
        self.assertEqual(lz4block.decompress(blk, 512), lit)
        # match length 4 + 15 + 20 = 39 copied from offset 1
        blk = bytes([0x1F]) + b"z" + struct.pack("<H", 1) + bytes([20]) + bytes([0x10]) + b"."
        self.assertEqual(lz4block.decompress(blk, 41), b"z" * 40 + b".")

    def test_errors(self):
        with self.assertRaises(lz4block.Lz4Error):
            lz4block.decompress(bytes([0x50]) + b"hel", 5)
        with self.assertRaises(lz4block.Lz4Error):
            lz4block.decompress(bytes([0x10]) + b"a" + struct.pack("<H", 5) + bytes([0x10]) + b"b", 10)
        with self.assertRaises(lz4block.Lz4Error):
            lz4block.decompress(bytes([0x30]) + b"abc", 4)


class FakeArchive:
    def __init__(self, path, entries, version=1, compression=0):
        self.path, self.entries, self.version, self.compression = path, entries, version, compression

    def find(self, name):
        return 0 if name == "t.dds" else None


class Previews(unittest.TestCase):
    def test_tail_dds_keeps_small_mips(self):
        from fo4sf.ba2 import Entry
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.ba2")
            mip0, mip1, rest = b"A" * 64, b"B" * 16, b"C" * 12
            z = zlib.compress(rest)
            with open(path, "wb") as f:
                f.write(mip0 + mip1 + z)
            e = Entry("t.dds", "DX10", width=512, height=512, mips=10, dxgi=71,
                      chunks=[(0, 0, 64, 0, 0), (64, 0, 16, 1, 1), (80, len(z), len(rest), 2, 9)])
            out = texpreview.tail_dds(FakeArchive(path, [e]), "t.dds", 128)
            self.assertEqual(struct.unpack_from("<II", out, 12), (128, 128))      # height, width of mip 2
            self.assertEqual(struct.unpack_from("<I", out, 28)[0], 8)              # mips 2..9
            self.assertTrue(out.endswith(rest))
            out = texpreview.tail_dds(FakeArchive(path, [e]), "t.dds", 256)
            self.assertTrue(out.endswith(mip1 + rest))
            with self.assertRaises(KeyError):
                texpreview.tail_dds(FakeArchive(path, [e]), "x.dds")

    def test_colour_helpers(self):
        c = np.array([0.0, 10.0, 128.0, 255.0])
        np.testing.assert_allclose(texpreview.linear_to_srgb(texpreview.srgb_to_linear(c)), c, atol=1e-9)
        img = np.zeros((2, 1, 4), np.uint8)
        img[1, 0, :3] = 255
        m = texpreview.mean_color(img)
        self.assertAlmostEqual(m[0], float(texpreview.linear_to_srgb(0.5)), places=6)   # averaged in linear light
        self.assertEqual(texpreview.delta_e((50, 60, 70), (50, 60, 70)), 0.0)
        self.assertAlmostEqual(float(texpreview.srgb_to_lab(np.array([255.0, 255.0, 255.0]))[0]), 100.0, places=2)


class Mapping(unittest.TestCase):
    def test_table_is_closed(self):
        for cat, cands in ground_map.SF_CANDIDATES.items():
            for c in cands:
                self.assertIn(c, ground_map.SF_FORMID, f"{cat}: {c}")
        for fo4, cat in ground_map.FO4_CATEGORY.items():
            self.assertIn(cat, ground_map.SF_CANDIDATES, fo4)
        for fo4, sf in ground_map.MAP.items():
            self.assertIn(fo4, ground_map.FO4_CATEGORY, fo4)
            self.assertIn(sf, ground_map.SF_FORMID, fo4)
            self.assertIn(sf, ground_map.SF_CANDIDATES[ground_map.category(fo4)], fo4)
        for fo4 in ground_map.REVIEWED:
            self.assertIn(fo4, ground_map.MAP)
        self.assertEqual(len(set(ground_map.SF_FORMID.values())), len(ground_map.SF_FORMID))

    def test_fallbacks(self):
        self.assertEqual(ground_map.sf_for("LDriedGrass01"), "LGrassDeadWet01")
        self.assertEqual(ground_map.category("LSomethingNew"), "dirt")
        self.assertEqual(ground_map.sf_for("LSomethingNew"), ground_map.SF_CANDIDATES["dirt"][0])


def rec(typ, fid, fields):
    data = b"".join(sig + struct.pack("<H", len(d)) + d for sig, d in fields)
    return typ + struct.pack("<III", len(data), 0, fid) + b"\0" * 8 + data


def grup(label, gtype, items):
    body = b"".join(items)
    if isinstance(label, int):
        label = struct.pack("<I", label)
    return b"GRUP" + struct.pack("<I4si", 24 + len(body), label, gtype) + b"\0" * 8 + body


class Fo4landTextures(unittest.TestCase):
    def test_read_world_keeps_land_texture_fields_and_group_records(self):
        vhgt = fo4land.encode_vhgt(1.0, np.zeros((33, 33), int))
        tex = [btxt(0x900, 2), atxt(0x901, 2, 0), vtxt([(1, 2, 0.5)]), (b"VCLR", bytes(33 * 33 * 3))]
        land = rec(b"LAND", 0x501, [(b"DATA", b"\0" * 4), (b"VHGT", vhgt)] + tex)
        cell = rec(b"CELL", 0x500, [(b"XCLC", struct.pack("<iiI", 3, -2, 0))])
        pcell = rec(b"CELL", 0x200, [(b"XCLC", struct.pack("<iiI", 0, 0, 0))])
        world = [pcell, grup(0x200, 6, []), grup(b"\0\0\0\0", 4, [grup(b"\0\0\0\0", 5, [cell, grup(0x500, 6, [
            grup(0x500, 9, [land])])])])]
        data = (rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 0, 0))]) +
                grup(b"LTEX", 0, [rec(b"LTEX", 0x900, [(b"EDID", b"LDirtA\0")]),
                                  rec(b"LTEX", 0x901, [(b"EDID", b"LGrassB\0")])]) +
                grup(b"WRLD", 0, [rec(b"WRLD", 0x3C, [(b"EDID", b"W\0")]), grup(0x3C, 1, world)]))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.esm")
            with open(p, "wb") as f:
                f.write(data)
            with fo4land.Plugin(p) as pl:
                names = {fid: fo4land.zstring(dict(f)[b"EDID"]) for fid, f in pl.group_records(b"LTEX")}
                self.assertEqual(names, {0x900: "LDirtA", 0x901: "LGrassB"})
                self.assertEqual(list(pl.group_records(b"TXST")), [])
                self.assertEqual([f for f, _ in pl.group_records(b"WRLD")], [0x3C])     # children group skipped
                c = pl.read_world("W", refs=False, land_textures=True)["cells"][(3, -2)]
                plain = pl.read_world("W", refs=False)["cells"][(3, -2)]
        self.assertNotIn("land_tex", plain)
        self.assertEqual([s for s, _ in c["land_tex"]], [b"BTXT", b"ATXT", b"VTXT", b"VCLR"])
        q = landtex.parse_land_textures(c["land_tex"])
        self.assertEqual(q[2]["base"], 0x900)
        self.assertEqual(float(q[2]["layers"][0][2][1, 2]), 0.5)


def synthetic_fo4(path):
    """Fallout4.esm stand-in: WRLD Commonwealth with FO4 cells (0..1, 0..1), flat at 8 units, dried grass everywhere
    and an opaque asphalt layer over all of cell (1, 1)."""
    vhgt = fo4land.encode_vhgt(1.0, np.zeros((33, 33), int))
    items, fid = [], 0x400
    for cy in (0, 1):
        for cx in (0, 1):
            tex = [btxt(0x900, q) for q in range(4)]
            if (cx, cy) == (1, 1):
                for q in range(4):
                    tex += [atxt(0x901, q, 0), vtxt([(r, c, 1.0) for r in range(Q) for c in range(Q)])]
            land = rec(b"LAND", fid + 1, [(b"DATA", b"\0" * 4), (b"VHGT", vhgt)] + tex)
            items += [rec(b"CELL", fid, [(b"XCLC", struct.pack("<iiI", cx, cy, 0))]),
                      grup(fid, 6, [grup(fid, 9, [land])])]
            fid += 2
    pcell = rec(b"CELL", 0x200, [(b"XCLC", struct.pack("<iiI", 0, 0, 0))])
    world = [pcell, grup(0x200, 6, []), grup(b"\0\0\0\0", 4, [grup(b"\0\0\0\0", 5, items)])]
    data = (rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 0, 0))]) +
            grup(b"LTEX", 0, [rec(b"LTEX", 0x900, [(b"EDID", b"LDriedGrass01\0")]),
                              rec(b"LTEX", 0x901, [(b"EDID", b"LAsphalt01\0")])]) +
            grup(b"WRLD", 0, [rec(b"WRLD", 0x3C, [(b"EDID", b"Commonwealth\0")]), grup(0x3C, 1, world)]))
    with open(path, "wb") as f:
        f.write(data)


def mars_plugin(entries, compressed=True, masters=("Starfield.esm", "FO4TerrainExp2.esm")):
    """Registration plugin stand-in: TES4 with masters, GRUP PNDT with one PNDT record: EDID, the 1-byte CNAM and the
    master-worldspace CNAM (f64, f64, u32 WRLD per entry), zlib-compressed when asked."""
    tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 1, 0x800))] +
               [x for mst in masters for x in ((b"MAST", mst.encode() + b"\0"), (b"DATA", b"\0" * 8))])
    fields = [(b"EDID", b"MarsPlanetData\0"), (b"CNAM", b"\x01"),
              (b"CNAM", b"".join(struct.pack("<ddI", la, lo, w) for la, lo, w in entries)), (b"FNAM", b"\0" * 4)]
    data = b"".join(sig + struct.pack("<H", len(d)) + d for sig, d in fields)
    body, flags = (struct.pack("<I", len(data)) + zlib.compress(data), fo4land.COMPRESSED) if compressed else (data, 0)
    pndt = b"PNDT" + struct.pack("<III", len(body), flags, 0x3F59A) + b"\0" * 8 + body
    return tes4 + grup(b"PNDT", 0, [pndt])


def staged_source(d, mars=True):
    """A staged-exp2b2 stand-in in d: one-cell BTD (flat 8 units, LDirtFootprints01 everywhere), plugins, plan."""
    fo4, src = os.path.join(d, "fo4"), os.path.join(d, "src")
    for p in (fo4, os.path.join(src, "Data", "Terrain"), os.path.join(src, "Data", "meshes", "terrain")):
        os.makedirs(p)
    synthetic_fo4(os.path.join(fo4, "Fallout4.esm"))
    raw = btd.quantize(np.full((128, 128), 8 / 70), -10.0, 10.0)
    quad = np.zeros((2, 2, 8), np.uint8)
    quad[..., 0] = 1
    data = btd.write(btd.Btd(6, -10.0, 10.0, [ground_map.formid(k) for k in ground_map.TEMPLATE_TABLE], raw,
                             np.zeros_like(raw), quad))
    for sub in (("Data", "Terrain"), ("Data", "meshes", "terrain")):
        with open(os.path.join(src, *sub, gt.BTD_NAME), "wb") as f:
            f.write(data)
    with open(os.path.join(src, "FO4TerrainExp2.esm"), "wb") as f:
        f.write(b"stand-in")
    if mars:
        with open(os.path.join(src, "FO4TerrainExp2_Mars.esm"), "wb") as f:
            f.write(mars_plugin([(-0.04, -0.09, 0x0000ABCD), (0.3, -1.2, 0x01000802)]))
    gt.write_json(os.path.join(src, "expected.json"), {
        "fo4_cells": {"x": [0, 1], "y": [0, 1]}, "structure": {"pos_m": [40.0, 40.0, 0.0]},
        "region_of_interest_m": {"xmin": 2.0, "xmax": 98.0, "ymin": 2.0, "ymax": 98.0}})
    gt.write_json(os.path.join(src, "plan.json"), [
        {"coc": "Spawn", "points": [{"label": "p1", "x": 40.0, "y": 40.0, "expect": 0.1143}]},
        {"coc": "Spawn", "points": [{"label": "p2", "x": 60.0, "y": 60.0, "expect": 0.1143}]}])
    return fo4, src, raw, data


class Exp2tBuild(unittest.TestCase):
    def test_build_and_check_every_variant_on_a_synthetic_one_cell_btd(self):
        with tempfile.TemporaryDirectory() as d:
            fo4, src, raw, src_btd = staged_source(d)
            out = os.path.join(d, "exp2t")
            self.assertEqual(gt.main(["build", "--from", src, "--out", out, "--fo4-data", fo4]), 0)
            self.assertEqual(gt.main(["check", "--from", src, "--out", out]), 0)
            self.assertEqual(gt.main(["check", "--from", src, "--out", out + "a"]), 0)     # one variant folder
            with self.assertRaises(SystemExit):                  # an existing staging is not overwritten silently
                gt.main(["build", "--from", src, "--out", out, "--fo4-data", fo4])
            self.assertEqual(gt.main(["build", "--from", src, "--out", out, "--fo4-data", fo4, "--replace",
                                      "--variants", "t,ta"]), 0)
            got = {}
            for v in gt.BUILD_ORDER:
                f = gt.variant_dir(out, v)
                got[v] = (gt.read_json(os.path.join(f, "plan.json")), gt.read_json(os.path.join(f, "expected.json")),
                          gt.read_bytes(os.path.join(f, "Data", "Terrain", gt.BTD_NAME)),
                          gt.read_bytes(os.path.join(f, "FO4TerrainExp2_Mars.esm")))
                self.assertFalse(os.path.exists(f + ".partial"))
            src_mars = gt.read_bytes(os.path.join(src, "FO4TerrainExp2_Mars.esm"))
        self.assertEqual(sorted(gt.BUILD_ORDER), sorted(gt.VARIANTS))
        for v, (plan, exp, data, mars) in got.items():
            self.assertEqual(len(plan), 2)
            self.assertTrue(all(w["fresh"] is True for w in plan))
            labels = [p["label"] for p in plan[0]["points"]]
            self.assertEqual(labels[0], "p1")
            self.assertIn("ground_grass", labels)
            self.assertIn("ground_lot", labels)
            new = btd.read(data)
            np.testing.assert_array_equal(new.heights_raw, raw)
            self.assertEqual(exp["experiment"], "terrain_exp2" + v)
            self.assertEqual(exp["variant"]["name"], v)
            _o, _g, _e, pair = gt.registration_entry(mars, "FO4TerrainExp2.esm")
            self.assertEqual(pair, gt.SITES["day"])
            self.assertTrue(gt.registration_diff(mars, src_mars, _e)[0])
            table = [e["edid"] for e in exp["ltex"]["table"]]
            for s in exp["ground_textures"]["spots"]:
                self.assertGreaterEqual(min(s["target_share"].values()), gt.VIEW_MIN_SHARE, (v, s["label"]))
        plan, exp, data, _m = got["t0"]
        self.assertEqual(data, src_btd)
        self.assertEqual([e["edid"] for e in exp["ltex"]["table"]], ground_map.TEMPLATE_TABLE)
        plan, exp, data, _m = got["t"]
        self.assertEqual([e["edid"] for e in exp["ltex"]["table"]], ["LGravelDecorative01", "LGrassDeadWet01"])
        self.assertEqual(btd.read(data).ltex, [ground_map.SF_FORMID["LGravelDecorative01"],
                                               ground_map.SF_FORMID["LGrassDeadWet01"]])
        lot = next(s for s in exp["ground_textures"]["spots"] if s["label"] == "ground_lot")
        self.assertEqual(lot["sf_mapped"], "LGravelDecorative01")
        self.assertGreater(lot["x"], 58.5 + 3.0)                   # inside the asphalt cell with the view window
        self.assertEqual(list(lot["sf_view"]), ["LGravelDecorative01"])
        plan, exp, data, _m = got["ta"]
        table = [e["edid"] for e in exp["ltex"]["table"]]
        self.assertEqual(table, ground_map.TEMPLATE_TABLE + ["LLooseRocksForest01", "LGrassAridSparse01_Dead"])
        self.assertEqual(exp["ltex"]["template_indices"], list(range(7)))
        lot = next(s for s in exp["ground_textures"]["spots"] if s["label"] == "ground_lot")
        self.assertEqual(lot["sf_mapped"], "LLooseRocksForest01")
        plan, exp, data, _m = got["tc"]
        self.assertEqual([e["edid"] for e in exp["ltex"]["table"]],
                         ground_map.TEMPLATE_TABLE + ["LGravelDecorative01", "LGrassDeadWet01"])
        plan, exp, data, _m = got["tb"]
        self.assertEqual([e["edid"] for e in exp["ltex"]["table"]][7:], ["LGravelDecorative01", "LGrassDeadWet01"])

    def test_site_day_needs_the_registration_plugin_and_source_keeps_it(self):
        with tempfile.TemporaryDirectory() as d:
            fo4, src, _raw, _data = staged_source(d, mars=False)
            out = os.path.join(d, "exp2t")
            with self.assertRaises(SystemExit):
                gt.main(["build", "--from", src, "--out", out, "--fo4-data", fo4, "--variants", "t"])
            self.assertEqual(gt.main(["build", "--from", src, "--out", out, "--fo4-data", fo4, "--variants", "t",
                                      "--site", "source"]), 0)
            exp = gt.read_json(os.path.join(out, "expected.json"))
            self.assertIsNone(exp["site"]["mars"])
            self.assertFalse(os.path.exists(out + "a"))
            self.assertEqual(gt.main(["check", "--from", src, "--out", out, "--variants", "t"]), 0)
            self.assertEqual(gt.main(["check", "--from", src, "--out", out]), 1)       # the other variants are missing


class Exp2tHelpers(unittest.TestCase):
    def test_encode_btd_from_vertex_grids(self):
        n = 1                                              # one 100 m cell: samples -0..99.2 m (origin rule n // 2 = 0)
        rows = cols = 65                                   # 2 x 2 FO4 cells from (0, 0): 117 m
        a = np.zeros((rows, cols), np.float32)
        a[:, :20] = 1.0                                    # west part texture "w", east "e"
        keys, grids = ["e", "w"], [1.0 - a, a]
        order, qm, words, st = gt.encode_btd(keys, grids, (0.0, 0.0), n)
        self.assertEqual(order, ["w", "e"])                # "w" covers less of the vertex grid: rarest first
        self.assertEqual(qm.shape, (2, 2, 8))
        self.assertGreater(st["dominant_texture_kept"], 0.99)
        dec = landtex.decode(qm, words, 2)
        x = np.arange(128) * 100 / 128 * 70 / 128          # sample column -> FO4 vertex column
        self.assertTrue((np.argmax(dec, 0)[:, x < 19] == 0).all())
        self.assertTrue((np.argmax(dec, 0)[:, x > 20] == 1).all())
        # with a template: its entries come first and stay unused; the same weights land on the later indices
        table, qm2, words2, st2 = gt.encode_btd(keys, grids, (0.0, 0.0), n, template=("p1", "p2", "p3"))
        self.assertEqual(table, ["p1", "p2", "p3", "w", "e"])
        dec2 = landtex.decode(qm2, words2, 5)
        self.assertEqual(float(np.abs(dec2[:3]).max()), 0.0)
        np.testing.assert_allclose(dec2[3:], dec, atol=1e-6)
        self.assertTrue(((qm2[..., :7] == 0) | (qm2[..., :7] <= 2)).all())   # values 1..2 -> table 3..4 (n - v)
        # plain rounding is never better on average than the search
        _t, qm3, words3, st3 = gt.encode_btd(keys, grids, (0.0, 0.0), n, search=False)
        self.assertEqual(st3["alpha_rounding"], "plain")
        self.assertGreaterEqual(st3["mean_weight_error"] + 1e-12, st["mean_weight_error"])

    def test_sample_matches_terrain_grid_bilinear(self):
        from fo4sf import terrain_grid as tg
        g = np.random.default_rng(0).random((20, 30))
        xs, ys = np.array([10.0, 33.3, 50.0]), np.array([5.0, 12.5])
        ref = tg.resample_bilinear(g, 0.0, 0.0, 128.0, xs * 70, ys * 70)
        got = gt.sample(g, gt.axis(ys, 0.0, 20), gt.axis(xs, 0.0, 30))
        np.testing.assert_allclose(got, ref)
        X, Y = np.meshgrid(xs, ys)
        pts = gt.points_bilinear(g, gt.axis(Y.ravel(), 0.0, 20), gt.axis(X.ravel(), 0.0, 30)).reshape(X.shape)
        np.testing.assert_allclose(pts, ref)

    def test_spots_pick_pure_flat_vertex_nearest_the_reference(self):
        rows = cols = 41
        keys = ["LAsphalt01", "LDriedGrass01", "LRootsEroded01", "LRubbleRock01"]
        w = [np.zeros((rows, cols)) for _ in keys]
        w[1][:] = 1.0
        w[1][:, 30:], w[0][:, 30:] = 0.0, 1.0              # asphalt strip in the east
        w[1][:5, :10], w[2][:5, :10] = 0.0, 1.0            # eroded dirt in the south-west corner
        heights = np.zeros((rows, cols))
        used = [(0.0, 0.0)]
        spots = gt.find_spots(keys, w, heights, (0.0, 0.0), (20 * 128 / 70, 20 * 128 / 70), lambda r, c: 0.0, 0.004,
                              used)
        got = {s["label"]: s for s in spots}
        self.assertNotIn("ground_road", got)               # no RubbleRock01 anywhere
        self.assertEqual(got["ground_lot"]["fo4_at_vertex"], {"LAsphalt01": 1.0})
        self.assertEqual(got["ground_lot"]["sf_mapped"], "LGravelDecorative01")
        self.assertGreaterEqual(got["ground_lot"]["x"], 31 * 128 / 70 - 1e-3)   # inside the strip (purity radius 1)
        self.assertEqual(got["ground_grass"]["sf_mapped"], "LGrassDeadWet01")
        self.assertEqual(got["ground_dirt"]["fo4_at_vertex"], {"LRootsEroded01": 1.0})
        self.assertEqual(got["ground_dirt"]["fo4_sources"], ["LRootsEroded01"])
        self.assertTrue(all(s["expect"] == 0.0 for s in spots))
        self.assertEqual(len(used), 1 + len(spots))

    def test_spot_purity_counts_only_textures_of_one_starfield_target(self):
        # the old bug: RootsEroded01 (-> LDirtPacked04) and DirtPath01 (-> LDirtPacked10) half and half passed a purity
        # test over their union; now neither target is pure there, and the pure RootsEroded01 patch further away wins
        rows = cols = 61
        keys = ["LDirtPath01", "LDriedGrass01", "LRootsEroded01"]
        w = [np.zeros((rows, cols)) for _ in keys]
        w[1][:] = 1.0
        w[1][25:36, 25:36] = 0.0
        w[0][25:36, 25:36], w[2][25:36, 25:36] = 0.5, 0.5           # mixed patch right at the reference point
        w[1][50:61, 50:61], w[2][50:61, 50:61] = 0.0, 1.0           # pure eroded dirt in the north-east corner
        self.assertNotEqual(ground_map.sf_for("LDirtPath01"), ground_map.sf_for("LRootsEroded01"))
        ref = (30 * 128 / 70, 30 * 128 / 70)
        dirt = [("ground_dirt", "dirt", "LDirtPacked04", 0.0, 2, 0.9)]
        spots = gt.find_spots(keys, w, np.zeros((rows, cols)), (0.0, 0.0), ref, lambda r, c: 0.0, 0.004, [],
                              spots=dirt)
        self.assertEqual(len(spots), 1)
        self.assertGreaterEqual(spots[0]["x"], 52 * 128 / 70 - 1e-3)
        self.assertEqual(spots[0]["fo4_textures"], {"LRootsEroded01": 1.0})
        path = [("ground_path", "path", "LDirtPacked10", 0.0, 2, 0.9)]
        self.assertEqual(gt.find_spots(keys, w, np.zeros((rows, cols)), (0.0, 0.0), ref, lambda r, c: 0.0, 0.004, [],
                                       spots=path), [])

    def test_spot_needs_the_target_share_in_the_view_window_and_disk(self):
        rows = cols = 41
        keys = ["LDriedGrass01"]
        w = [np.ones((rows, cols))]
        calls = []

        def share(x, y, target):                          # the decoded view is poor south of y = 50 m
            calls.append((x, y, target))
            return {"view": 0.95 if y >= 50 else 0.5, "disk": 0.97}

        spot = [("ground_grass", "grass", "LGrassDeadWet01", 0.0, 2, 0.9)]
        got = gt.find_spots(keys, w, np.zeros((rows, cols)), (0.0, 0.0), (36.6, 36.6), lambda r, c: 0.0, 0.004, [],
                            share_fn=share, spots=spot)
        self.assertEqual(len(got), 1)
        self.assertGreaterEqual(got[0]["y"], 50.0)
        self.assertGreater(got[0]["skipped_for_low_share"], 0)
        self.assertEqual(got[0]["target_share"], {"view": 0.95, "disk": 0.97})
        self.assertTrue(all(c[2] == "LGrassDeadWet01" for c in calls))

    def test_decoded_shares_cover_the_view_window_not_one_sample(self):
        # one-cell BTD: table [A, B]; B everywhere except a band y >= 58.5 m of A. A spot at y = 56 m sits on B, but the
        # runner's screenshot looks 2..7 m north (58..63 m), which is all A
        n, H = 1, 128
        o = gt.tg.grid_origin(n)
        ys = o + np.arange(H) * gt.tg.SF_STEP_M
        wA = np.zeros((2, H, H))
        wA[0][ys >= 58.5, :] = 1.0
        wA[1] = 1.0 - wA[0]
        qm, words, _st = landtex.encode(wA, 2)
        t = btd.Btd(6, 0.0, 1.0, [1, 2], np.zeros((H, H), np.uint16), words, qm)
        at = gt.decoded_at(t, ["A", "B"], 50.0, 56.0)
        view = gt.decoded_shares(t, ["A", "B"], 50.0, 56.0, "view")
        disk = gt.decoded_shares(t, ["A", "B"], 50.0, 56.0, "disk")
        self.assertEqual(list(at), ["B"])
        self.assertGreater(view["A"], 0.9)
        self.assertAlmostEqual(sum(view.values()), 1.0, places=2)
        self.assertLess(disk["A"], 0.5)
        # samples in the window: x 47..53, y 58..63 at 0.78125 m
        X, Y = gt.window_points(50.0, 56.0, "view")
        self.assertAlmostEqual(float(X.min()), 47.0)
        self.assertAlmostEqual(float(Y.max()), 63.0)
        Xd, Yd = gt.window_points(0.0, 0.0, "disk")
        self.assertLessEqual(float(np.hypot(Xd, Yd).max()), gt.DISK_M + 1e-9)
        self.assertEqual(gt.decoded_shares(t, ["A", "B"], 500.0, 500.0, "view"), {})     # outside the BTD

    def test_fold_rare_textures(self):
        keys = ["a", "b", "c", "rare"]
        g = [np.full((3, 3), x) for x in (0.5, 0.3, 0.1997, 0.0003)]
        pal = {"sf": {"a": {"color": [200, 10, 10]}, "b": {"color": [10, 200, 10]}, "c": {"color": [10, 10, 200]},
                      "rare": {"color": [20, 190, 20]}}}
        self.assertEqual(gt.fold_rare(keys, g, pal), {"rare": "b"})        # nearest colour
        self.assertEqual(gt.fold_rare(keys, g), {"rare": "a"})             # no palette: the most common
        self.assertEqual(gt.fold_rare(keys, g, pal, min_coverage=0.0), {})


class Exp2tRegistration(unittest.TestCase):
    def test_relocate_compressed_and_uncompressed(self):
        ents = [(-0.04, -0.09, 0x0000ABCD), (0.3, -1.2, 0x01000802), (0.7, -0.17, 0x00001234)]
        for compressed in (True, False):
            src = mars_plugin(ents, compressed)
            off, groups, e, pair = gt.registration_entry(src, "FO4TerrainExp2.esm")
            self.assertEqual(pair, (0.3, -1.2))
            new, old = gt.relocate_registration(src, "FO4TerrainExp2.esm", (0.2, 1.2))
            self.assertEqual(old, (0.3, -1.2))
            self.assertEqual(gt.registration_entry(new, "fo4terrainexp2.esm")[3], (0.2, 1.2))
            ok, summary = gt.registration_diff(new, src, e)
            self.assertTrue(ok, summary)
            _h, recs = gt.plugin_records(new)
            fields = dict(fo4land.iter_subrecords(recs[0][3]))
            self.assertEqual(fields[b"EDID"], b"MarsPlanetData\0")
            cn = [d for s, d in fo4land.iter_subrecords(recs[0][3]) if s == b"CNAM" and len(d) == 60][0]
            self.assertEqual(struct.unpack_from("<ddI", cn, 0), (-0.04, -0.09, 0x0000ABCD))
            self.assertEqual(struct.unpack_from("<ddI", cn, 40), (0.7, -0.17, 0x00001234))
            gsize = struct.unpack_from("<I", new, groups[0] + 4)[0]
            self.assertEqual(groups[0] + gsize, len(new))                   # group size follows the record
            if not compressed:                                              # only bytes of the entry's f64 pair
                diff = [i for i, (x, y) in enumerate(zip(new, src)) if x != y]
                self.assertTrue(diff and all(off + 24 + e <= i < off + 24 + e + 16 for i in diff))
        # a different site entry is caught by the diff
        a = mars_plugin(ents, False)
        b = mars_plugin([ents[0], ents[1], (0.7, -0.18, 0x00001234)], False)
        self.assertFalse(gt.registration_diff(a, b, gt.registration_entry(a, "FO4TerrainExp2.esm")[2])[0])

    def test_registration_entry_errors(self):
        with self.assertRaises(ValueError):                                  # not a master
            gt.registration_entry(mars_plugin([(0.3, -1.2, 0x01000802)]), "Other.esm")
        with self.assertRaises(ValueError):                                  # two entries of the plugin
            gt.registration_entry(mars_plugin([(0.3, -1.2, 0x01000802), (0.1, 0.1, 0x01000803)]), "FO4TerrainExp2.esm")
        with self.assertRaises(ValueError):                                  # none
            gt.registration_entry(mars_plugin([(0.3, -1.2, 0x00000802)]), "FO4TerrainExp2.esm")


class Exp2tSurveyAndLighting(unittest.TestCase):
    def test_btd_table_reads_only_the_header_and_biom_refs(self):
        tab = [0x1085C, 0x1235C2]
        head = btd.MAGIC + struct.pack("<IffIIiiiiI", 6, 0.0, 1.0, 128, 128, 0, 0, 0, 0, len(tab)) + \
            struct.pack("<2I", *tab)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.bin")
            with open(p, "wb") as f:
                f.write(b"junk" + head + b"\xff" * 64)

            class A:
                path = p
                entries = [type("E", (), {"packed": 0, "offset": 4, "unpacked": len(head) + 64})()]
            self.assertEqual(gt.btd_table(A, 0), tab)
            biom = rec(b"BIOM", 0x77, [(b"EDID", b"B\0"), (b"LNAM", struct.pack("<I", 0x1235C2)),
                                       (b"ANAM", struct.pack("<2I", 0x1235C2, 0x55)), (b"XNAM", struct.pack("<I", 9))])
            esm = os.path.join(d, "s.esm")
            with open(esm, "wb") as f:
                f.write(rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 0, 0))]) + grup(b"BIOM", 0, [biom]))
            self.assertEqual(gt.biom_ltex_refs(esm), {0x1235C2: 2, 0x55: 1})

    def test_lighting_verdicts_and_report(self):
        from PIL import Image
        self.assertEqual(gt.lighting_verdict(110.0, 120.0), "daylight")
        self.assertEqual(gt.lighting_verdict(7.0, 51.6), "daylight")        # arrival in a pit, probes in daylight
        self.assertEqual(gt.lighting_verdict(12.0, 35.0), "night")
        self.assertEqual(gt.lighting_verdict(12.0, None), "night")
        self.assertEqual(gt.lighting_verdict(45.0, 42.0), "unclear")
        with tempfile.TemporaryDirectory() as d:
            att = os.path.join(d, "q", "tests", "0000_terrain_X", "a1")
            os.makedirs(att)
            sky = np.zeros((720, 1280, 3), np.uint8)
            sky[:200] = 15
            Image.fromarray(sky).save(os.path.join(att, "spawn.png"))
            for k in (0, 1, 10):
                im = np.full((720, 1280, 3), 30, np.uint8)
                im[300:420, 500:780] = 200                  # the helmet lamp's circle does not count
                Image.fromarray(im).save(os.path.join(att, f"pt{k}.png"))
            rep = os.path.join(d, "rep.json")
            self.assertEqual(gt.main(["lighting", "--run", os.path.join(d, "q"), "--out", rep]), 0)
            r = gt.read_json(rep)["attempts"][0]
            self.assertEqual(r["verdict"], "night")
            self.assertEqual(r["sky_top_rows"], 15.0)
            self.assertEqual(r["probe_corner_median"], 30.0)
            self.assertEqual(list(r["probe_corners"]), ["pt0", "pt1", "pt10"])
            self.assertEqual(gt.main(["lighting", "--run", os.path.join(d, "empty")]), 1)


class Exp2tMappingVariants(unittest.TestCase):
    def test_folds_placeholders_and_notes(self):
        for v, fold in ground_map.FOLD.items():
            self.assertEqual(set(fold), set(ground_map.SF_CANDIDATES), v)
            self.assertEqual(len(set(fold.values())), 4, v)
            for k in fold.values():
                self.assertIn(k, ground_map.SF_FORMID)
            self.assertEqual(len(ground_map.TEMPLATE_TABLE) + 4, 11)
        self.assertEqual(sorted(ground_map.PLACEHOLDERS), sorted(ground_map.PLACEHOLDER_FORMID))
        self.assertEqual(set(ground_map.TEMPLATE_TABLE), set(ground_map.PLACEHOLDERS) | {"LDirtFootprints01"})
        self.assertEqual(ground_map.formid("LDefault001Solid"), 0x0001085C)
        self.assertEqual(ground_map.formid("LGravelRoad01"), 0x001235C1)
        with self.assertRaises(KeyError):
            ground_map.formid("LNoSuchTexture")
        self.assertEqual(ground_map.folded("ta", "LDriedGrass01"), "LGrassAridSparse01_Dead")
        self.assertEqual(ground_map.folded("tb", "LAsphalt01"), "LGravelDecorative01")
        self.assertTrue(set(ground_map.NOTES) <= set(ground_map.MAP))
        self.assertEqual(gt.parse_variants("all"), gt.BUILD_ORDER)
        self.assertEqual(gt.parse_variants("ta,t"), ["t", "ta"])
        with self.assertRaises(SystemExit):
            gt.parse_variants("tz")
        self.assertEqual([gt.variant_dir("x", v) for v in ("t", "t0", "ta")], ["x", "x0", "xa"])
        self.assertEqual(set(gt.RUN_ORDER), set(gt.VARIANTS))
        chain = {v: i["vs"] for v, i in gt.VARIANTS.items()}
        self.assertEqual(chain, {"t0": "exp2b2", "ta": "t0", "tb": "ta", "tc": "tb", "t": "tc"})


if __name__ == "__main__":
    unittest.main()
