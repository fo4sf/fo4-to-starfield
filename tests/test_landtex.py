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
                c = pl.read_world("W", refs=False, land_textures=True)["cells"][(3, -2)]
                plain = pl.read_world("W", refs=False)["cells"][(3, -2)]
        self.assertNotIn("land_tex", plain)
        self.assertEqual([s for s, _ in c["land_tex"]], [b"BTXT", b"ATXT", b"VTXT", b"VCLR"])
        q = landtex.parse_land_textures(c["land_tex"])
        self.assertEqual(q[2]["base"], 0x900)
        self.assertEqual(float(q[2]["layers"][0][2][1, 2]), 0.5)


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

    def test_sample_matches_terrain_grid_bilinear(self):
        from fo4sf import terrain_grid as tg
        g = np.random.default_rng(0).random((20, 30))
        xs, ys = np.array([10.0, 33.3, 50.0]), np.array([5.0, 12.5])
        ref = tg.resample_bilinear(g, 0.0, 0.0, 128.0, xs * 70, ys * 70)
        got = gt.sample(g, gt.axis(ys, 0.0, 20), gt.axis(xs, 0.0, 30))
        np.testing.assert_allclose(got, ref)

    def test_spots_pick_pure_flat_vertex_nearest_the_reference(self):
        rows = cols = 41
        keys = ["LAsphalt01", "LDriedGrass01", "LRootsEroded01", "LRubbleRock01"]
        w = [np.zeros((rows, cols)) for _ in keys]
        w[1][:] = 1.0
        w[1][:, 30:], w[0][:, 30:] = 0.0, 1.0              # asphalt strip in the east
        w[1][:5, :10], w[2][:5, :10] = 0.0, 1.0            # dirt in the south-west corner
        heights = np.zeros((rows, cols))
        used = [(0.0, 0.0)]
        spots = gt.find_spots(keys, w, heights, (0.0, 0.0), (20 * 128 / 70, 20 * 128 / 70), lambda r, c: 0.0, 0.004,
                              used)
        got = {s["label"]: s for s in spots}
        self.assertNotIn("ground_road", got)               # no RubbleRock01 anywhere
        self.assertEqual(got["ground_lot"]["fo4_textures"], {"LAsphalt01": 1.0})
        self.assertGreaterEqual(got["ground_lot"]["x"], 31 * 128 / 70 - 1e-3)   # inside the strip (purity radius 1)
        self.assertEqual(got["ground_grass"]["sf_mapped"], "LGrassDeadWet01")
        self.assertEqual(got["ground_dirt"]["fo4_textures"], {"LRootsEroded01": 1.0})
        self.assertTrue(all(s["expect"] == 0.0 for s in spots))
        self.assertEqual(len(used), 1 + len(spots))


if __name__ == "__main__":
    unittest.main()
