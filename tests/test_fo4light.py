"""src/fo4sf/fo4light.py: FO4 LIGH / light REFR reading (raw records of a synthetic plugin) and the mapping to
Starfield light fields (docs/terrain/exterior-lights.md), all on synthetic bytes."""
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import fo4land, fo4light  # noqa: E402


def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def ligh_data(radius=256, color=(237, 168, 122), flags=0x9, falloff=1.0, fov=90.0, near=7.2174, flicker=(0.3636, 0.8, 0.8),
              size=64):
    d = struct.pack("<iI4BI", -1, radius, *color, 0, flags) + struct.pack("<10f", falloff, fov, near, *flicker, 0.0, 1.0,
                                                                          2.0, 0.0)
    d += struct.pack("<If", 0, 0.0)
    return d[:size]


def ligh_fields(edid="defaultLightFire01NSFlicker", fade=1.0, model=None, gobo=None, lens=0, data=None, bounds=(-9, -10, -18, 9, 10, 12)):
    f = [(b"EDID", edid.encode() + b"\0"), (b"OBND", struct.pack("<6h", *bounds))]
    if model:
        f.append((b"MODL", model.encode() + b"\0"))
    f.append((b"DATA", data if data is not None else ligh_data()))
    if fade is not None:
        f.append((b"FNAM", struct.pack("<f", fade)))
    if gobo:
        f.append((b"NAM0", gobo.encode() + b"\0"))
    if lens:
        f.append((b"LNAM", struct.pack("<I", lens)))
    return f


def record(sig, fid, fields, flags=0, compress=False):
    body = b"".join(sub(s, d) for s, d in fields)
    if compress:
        body = struct.pack("<I", len(body)) + zlib.compress(body)
        flags |= fo4land.COMPRESSED
    return sig + struct.pack("<IIIIHH", len(body), flags, fid, 0, 131, 0) + body


def group(label, gtype, items):
    body = b"".join(items)
    lab = label if isinstance(label, bytes) else struct.pack("<I", label)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + lab + struct.pack("<iI", gtype, 0) + struct.pack("<I", 0) + body


def light_ref_fields(base, xrds=None, xlig=None, xemi=0):
    f = [(b"NAME", struct.pack("<I", base))]
    if xrds is not None:
        f.append((b"XRDS", struct.pack("<f", xrds)))
    if xlig is not None:
        f.append((b"XLIG", struct.pack(f"<{len(xlig)}f", *xlig)))
    if xemi:
        f.append((b"XEMI", struct.pack("<I", xemi)))
    f.append((b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0)))
    return f


def synthetic_esm(path):
    """TES4, a LIGH group (one record compressed) and two worldspaces with light references in every kind of cell."""
    tes4 = b"TES4" + struct.pack("<IIIIHH", 0, 0, 0, 0, 131, 0)
    lighs = group(b"LIGH", 0, [record(b"LIGH", 0x08ADFA, ligh_fields(), flags=0x20000),
                               record(b"LIGH", 0x0E5F97, ligh_fields("IndustrialOmni01NSFlicker", data=ligh_data(size=48)),
                                      compress=True),
                               record(b"LIGH", 0x000777, ligh_fields("NotWanted"))])
    wanted_base = 0x08ADFA

    def world(fid, edid, ref_ids, cell_fid):
        persistent_cell = record(b"CELL", cell_fid, [(b"EDID", b"\0")])
        pcell_children = group(cell_fid, 6, [group(cell_fid, 8, [record(b"REFR", ref_ids[0], light_ref_fields(wanted_base, xrds=-58.5))])])
        ext_cell = record(b"CELL", cell_fid + 1, [(b"XCLC", struct.pack("<iiI", 3, -4, 0))])
        ext_children = group(cell_fid + 1, 6, [group(cell_fid + 1, 9, [
            record(b"REFR", ref_ids[1], light_ref_fields(wanted_base, xlig=(0, 2.0, 0, 1.0, 14.0, 0)), compress=True),
            record(b"REFR", ref_ids[2], light_ref_fields(wanted_base, xlig=(5.0, -0.5, 0, 1.0), xemi=0x1173)),
            record(b"REFR", 0x00AAAA, light_ref_fields(wanted_base))])])
        block = group(struct.pack("<hh", 0, -1), 4, [group(struct.pack("<hh", 0, -1), 5, [ext_cell, ext_children])])
        return [record(b"WRLD", fid, [(b"EDID", edid.encode() + b"\0")]), group(fid, 1, [persistent_cell, pcell_children, block])]
    wrld = group(b"WRLD", 0, world(0x00003C, "Commonwealth", (0x000101, 0x000102, 0x000103), 0x00018AA2)
                 + world(0x000555, "Other", (0x000201, 0x000202, 0x000203), 0x00019000))
    with open(path, "wb") as f:
        f.write(tes4 + lighs + wrld)


class ParseTests(unittest.TestCase):
    def test_ligh_fields_as_stored(self):
        b = fo4light.parse_ligh(ligh_fields(fade=1.5, model="Effects\\X.nif", gobo="data\\Textures\\G.dds", lens=0x239223))
        self.assertEqual((b["edid"], b["radius"], b["color"], b["flags"], b["time"]), ("defaultLightFire01NSFlicker", 256,
                                                                                       [237, 168, 122], 9, -1))
        self.assertAlmostEqual(b["near_clip"], 7.2174, places=4)
        self.assertAlmostEqual(b["flicker_movement"], 0.8, places=6)
        self.assertEqual((b["fade"], b["model"], b["gobo"], b["lens"]), (1.5, "Effects\\X.nif", "data\\Textures\\G.dds", 0x239223))
        self.assertEqual(b["bounds"], [-9, -10, -18, 9, 10, 12])
        self.assertEqual(b["data_size"], 64)

    def test_short_data_and_default_fade(self):
        b = fo4light.parse_ligh(ligh_fields(fade=None, data=ligh_data(fov=60.0, size=48)))
        self.assertEqual((b["fov"], b["exponent"], b["god_rays_near_clip"], b["value"], b["weight"]), (60.0, 0.0, 0.0, 0, 0.0))
        self.assertEqual(b["fade"], 1.0)
        with self.assertRaises(ValueError):
            fo4light.parse_ligh([(b"EDID", b"NoData\0")])

    def test_light_ref_fields(self):
        r = fo4light.parse_light_ref(light_ref_fields(0x08ADFA, xrds=-58.5, xlig=(5.0, -0.5, 0, 1.0), xemi=0x1173))
        self.assertEqual((r["base"], r["radius_delta"], r["emittance"]), (0x08ADFA, -58.5, 0x1173))
        self.assertEqual(r["lighting"], {"fov": 5.0, "fade": -0.5, "end_distance_cap": 0.0, "shadow_depth_bias": 1.0,
                                         "near_clip": 0.0, "volumetric": 0.0})
        r = fo4light.parse_light_ref(light_ref_fields(1))
        self.assertEqual((r["radius_delta"], r["lighting"], r["emittance"]), (None, None, None))


class ReadTests(unittest.TestCase):
    def test_bases_and_references_of_one_worldspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Synthetic.esm")
            synthetic_esm(path)
            with fo4land.Plugin(path) as p:
                bases = fo4light.read_bases(p, {0x08ADFA, 0x0E5F97, 0x123456})
                refs = fo4light.read_refs(p, "Commonwealth", {0x000101, 0x000102, 0x000103, 0x000201})
        self.assertEqual(sorted(bases), [0x08ADFA, 0x0E5F97])                       # not 000777, not the absent one
        self.assertEqual(bases[0x08ADFA]["record_flags"], 0x20000)
        self.assertEqual(bases[0x0E5F97]["edid"], "IndustrialOmni01NSFlicker")       # decompressed, 48-byte DATA
        self.assertEqual(sorted(refs), [0x000101, 0x000102, 0x000103])               # never the other worldspace's
        self.assertEqual(refs[0x000101]["radius_delta"], -58.5)                      # persistent cell child
        self.assertEqual(refs[0x000102]["lighting"]["near_clip"], 14.0)              # compressed temporary child
        self.assertEqual(refs[0x000103]["emittance"], 0x1173)


class MapBaseTests(unittest.TestCase):
    def base(self, **kw):
        b = fo4light.parse_ligh(ligh_fields(**{k: v for k, v in kw.items() if k in ("fade", "model", "gobo", "lens")},
                                            data=ligh_data(**{k: v for k, v in kw.items() if k in ("radius", "flags", "near",
                                                                                                    "flicker", "fov")})))
        b["record_flags"] = kw.get("record_flags", 0)
        return b

    def test_units_to_metres_and_copied_fields(self):
        sf, why, lost = fo4light.map_base(self.base(), lumens_per_m2=333.0)
        self.assertIsNone(why)
        self.assertEqual(lost, [])
        self.assertAlmostEqual(sf["radius"], 256 / 70.0, places=5)
        self.assertAlmostEqual(sf["near_clip"], 7.2174 / 70.0, places=5)
        self.assertAlmostEqual(sf["flicker"][2], 0.8 / 70.0, places=5)                # movement amplitude: a distance
        self.assertAlmostEqual(sf["flicker"][0], 0.3636, places=4)
        self.assertEqual((sf["color"], sf["fov"], sf["falloff"], sf["time"]), ([237, 168, 122], 90.0, 1.0, -1))
        self.assertEqual(sf["bounds"], [[round(-9 / 70, 6), round(-10 / 70, 6), round(-18 / 70, 6)],
                                        [round(9 / 70, 6), round(10 / 70, 6), round(12 / 70, 6)]])
        self.assertEqual(sf["lumens"], round(333.0 * (256 / 70.0) ** 2))

    def test_flags_type_and_flicker_effect(self):
        sf = fo4light.map_base(self.base(flags=0x9))[0]                             # dynamic | flicker
        self.assertEqual((sf["flags"], sf["type"], sf["flicker_effect"]), (1, fo4light.SF_OMNI, fo4light.SF_FLICKER))
        sf = fo4light.map_base(self.base(flags=0x81))[0]                            # pulse
        self.assertEqual(sf["flicker_effect"], fo4light.SF_PULSE)
        self.assertEqual(fo4light.map_base(self.base(flags=0x8))[0]["flags"], 0)      # FO4 bit 0x1 is carried, not invented
        sf = fo4light.map_base(self.base(flags=0x4001 | 0x8000 | 0x20))[0]          # non-shadow spot, non specular, off
        self.assertEqual((sf["type"], sf["flags"]), (fo4light.SF_NONSHADOW_SPOT, 0x1 | 0x40 | 0x20))
        sf = fo4light.map_base(self.base(flags=0x401))[0]
        self.assertEqual((sf["type"], sf["flicker_effect"]), (fo4light.SF_SHADOW_SPOT, fo4light.SF_FLICKER_NONE))
        sf, _w, lost = fo4light.map_base(self.base(flags=0x1 | 0x1000 | 0x80000 | 0x2000, model="L.nif", gobo="g.dds", lens=5))
        self.assertEqual((sf["type"], sf["flags"]), (fo4light.SF_OMNI, 1))
        self.assertEqual(lost, ["flag shadow omnidirectional", "flag no rim lighting", "flag bits 0x2000", "model", "gobo", "lens"])

    def test_random_anim_start_and_skips(self):
        self.assertTrue(fo4light.map_base(self.base(record_flags=0x30000))[0]["random_anim_start"])
        self.assertFalse(fo4light.map_base(self.base(record_flags=0x20000))[0]["random_anim_start"])
        self.assertEqual(fo4light.map_base(self.base(flags=0x100001))[:2], (None, "ambient_only"))
        self.assertEqual(fo4light.map_base(self.base(fade=0.0))[:2], (None, "no_intensity"))

    def test_lumens_follow_fade_scale_and_radius(self):
        a = fo4light.map_base(self.base(fade=1.0, radius=256), 333.0, scale=1.0)[0]["lumens"]
        b = fo4light.map_base(self.base(fade=2.0, radius=256), 333.0, scale=1.5)[0]["lumens"]
        c = fo4light.map_base(self.base(fade=1.0, radius=512), 333.0)[0]["lumens"]
        self.assertAlmostEqual(b / a, 3.0, places=3)
        self.assertAlmostEqual(c / a, 4.0, places=3)
        self.assertEqual(fo4light.map_base(self.base(radius=1), 333.0)[0]["lumens"], 1)    # never 0
        with self.assertRaises(ValueError):
            fo4light.map_base(self.base(), scale=0.0)


class MapRefTests(unittest.TestCase):
    B = {"fade": 2.0, "radius": 140}                               # units: 2 m

    def test_intensity_and_median_scale(self):
        self.assertEqual(fo4light.ref_intensity({"lighting": None}, self.B), 1.0)
        self.assertEqual(fo4light.ref_intensity({"lighting": {"fade": 1.0}}, self.B), 1.5)
        self.assertEqual(fo4light.base_scale([1.0, 3.0, 2.0]), 2.0)
        self.assertEqual(fo4light.base_scale([1.0, 3.0]), 2.0)
        self.assertEqual(fo4light.base_scale([]), 1.0)

    def test_reference_fields(self):
        r = {"radius_delta": -70.0, "lighting": {"fov": -39.2, "fade": 1.0, "near_clip": 7.0}}
        m = fo4light.map_ref(r, self.B, scale=1.0)
        self.assertEqual(m["radius_delta"], -1.0)
        self.assertEqual(m["lighting"], {"fov": -39.2, "fade": 0.375, "near_clip": 0.1})   # 1.5 x (1 m / 2 m)^2
        self.assertFalse(m["fade_clamped"])
        m = fo4light.map_ref({"radius_delta": None, "lighting": {"fov": 0, "fade": 6.0, "near_clip": 0}}, self.B)
        self.assertEqual((m["lighting"]["fade"], m["fade_clamped"]), (fo4light.XLIG_FADE_MAX, True))   # 4.0 -> 1.6
        m = fo4light.map_ref({"radius_delta": None, "lighting": {"fov": 0, "fade": -1.99, "near_clip": 0}}, self.B)
        self.assertEqual((m["lighting"]["fade"], m["fade_clamped"]), (fo4light.XLIG_FADE_MIN, True))
        m = fo4light.map_ref({"radius_delta": None, "lighting": {"fov": 0, "fade": 2.0, "near_clip": 0}}, self.B, scale=2.0)
        self.assertEqual(m["lighting"]["fade"], 1.0)                                # (2 + 2) / 2 / scale 2

    def test_no_xlig_gets_one_only_when_the_base_is_scaled(self):
        self.assertIsNone(fo4light.map_ref({"radius_delta": None, "lighting": None}, self.B)["lighting"])
        m = fo4light.map_ref({"radius_delta": None, "lighting": None}, self.B, scale=4.0)
        self.assertEqual(m["lighting"], {"fov": 0.0, "fade": 0.25, "near_clip": 0.0})

    def test_xrds_radius_enters_the_intensity_squared(self):
        # the review of #246 (P2-2): lumens follow radius^2, so a reference's own radius (base + XRDS) counts.
        # 090C85:Fallout4.esm: a 3.66 m base (256 units) + XRDS 12.43 m (870.1 units) = 16.08 m, about 19x the lumens
        b = {"fade": 1.0, "radius": 256}
        r = {"radius_delta": 870.1, "lighting": None}
        self.assertAlmostEqual(fo4light.radius_ratio(r, b), (256 + 870.1) / 256)
        self.assertAlmostEqual(fo4light.ref_intensity(r, b), ((256 + 870.1) / 256) ** 2)
        self.assertAlmostEqual(fo4light.ref_intensity(r, b), 19.35, places=2)
        self.assertEqual(fo4light.radius_ratio({"radius_delta": None}, b), 1.0)
        self.assertEqual(fo4light.radius_ratio({"radius_delta": -300.0}, b), 0.0)       # never a negative radius
        # 20E065:Fallout4.esm: 3.66 m - 2.97 m = 0.68 m keeps (0.68 / 3.66)^2 of the base, fade 1 x that
        self.assertAlmostEqual(fo4light.ref_intensity({"radius_delta": -208.0, "lighting": {"fade": 0.0}}, b),
                               (48 / 256) ** 2)
        # a reference with XRDS but no XLIG on an unscaled base gets an XLIG fade for its own size
        m = fo4light.map_ref({"radius_delta": -70.0, "lighting": None}, self.B, scale=1.0)
        self.assertEqual(m["lighting"], {"fov": 0.0, "fade": 0.25, "near_clip": 0.0})
        # the base takes the median of its references' intensities, radius included, into its lumens
        refs = [{"radius_delta": 140.0, "lighting": None}] * 2 + [{"radius_delta": None, "lighting": None}]
        self.assertEqual(fo4light.base_scale([fo4light.ref_intensity(x, self.B) for x in refs]), 4.0)

    def test_reference_record_flags_are_carried(self):
        # the review of #246 (P2-1): DoesNotLightWater 0x100, NeverFades 0x10000, DoesNotLightLandscape 0x20000 (the
        # Mutagen names in both games) come from the FO4 REFR header; every other header bit stays behind
        r = {"radius_delta": None, "lighting": None}
        self.assertEqual(fo4light.map_ref(dict(r, flags=0x30100), self.B)["record_flags"], 0x30100)   # 017C49:Fallout4.esm
        self.assertEqual(fo4light.map_ref(dict(r, flags=0x0), self.B)["record_flags"], 0)             # lights water
        self.assertEqual(fo4light.map_ref(dict(r, flags=0x400 | 0x800 | 0x100), self.B)["record_flags"], 0x100)
        self.assertEqual(fo4light.map_ref(r, self.B)["record_flags"], 0)


if __name__ == "__main__":
    unittest.main()
