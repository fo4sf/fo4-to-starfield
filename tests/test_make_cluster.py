"""make_cluster.py: the Commonwealth-wide promotion lists from the band exports and core64c's placed references."""
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import make_cluster as mc  # noqa: E402

TABLE = {"default": {"name": None, "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
         "by_editor_id": {"Loot_Prewar_Medkit": {"name": "First Aid Kit", "items": [{"form": "Starfield.esm:00000F", "count": 25}]},
                          "Loot_Safe*": {"name": "Safe", "items": [{"form": "Starfield.esm:00000F", "count": 60}]},
                          "Loot_SafeWall*": {"name": "Wall Safe", "items": [{"form": "Starfield.esm:00000F", "count": 40}]}}}


def ref(fk, typ="Container", edid="Loot_Prewar_Medkit", base="04B6E9:Fallout4.esm", disabled=0):
    return {"formkey": fk, "type": typ, "base_editor_id": edid, "base_formkey": base, "disabled": disabled}


class TableTests(unittest.TestCase):
    def test_exact_then_longest_prefix_then_default(self):
        self.assertEqual(mc.table_entry(TABLE, "Loot_Prewar_Medkit")[1], "exact")
        e, how = mc.table_entry(TABLE, "Loot_SafeWall01")
        self.assertEqual((e["name"], how), ("Wall Safe", "prefix"))
        self.assertEqual(mc.table_entry(TABLE, "Loot_Safe01")[0]["name"], "Safe")
        self.assertEqual(mc.table_entry(TABLE, "Loot_Toolbox01")[1], "default")
        self.assertEqual(mc.table_entry({"by_editor_id": {}}, "x"), (None, "none"))

    def test_humanize(self):
        self.assertEqual(mc.humanize("Loot_Prewar_Medkit"), "Loot Prewar Medkit")
        self.assertEqual(mc.humanize("PrewarCabinetGarage01"), "Prewar Cabinet Garage01")


class ContainersTests(unittest.TestCase):
    def test_placed_containers_in_placement_order_with_table_names(self):
        placed = ["000003:Fallout4.esm", "19EE52:Fallout4.esm", "000001:Fallout4.esm", "000002:Fallout4.esm"]
        refs = [ref("000001:Fallout4.esm", edid="Loot_Safe01", base="0001:Fallout4.esm"),
                ref("19EE52:Fallout4.esm"),
                ref("000002:Fallout4.esm", edid="Loot_Toolbox01", base="0002:Fallout4.esm"),
                ref("000003:Fallout4.esm", typ="Static"),                           # not a container
                ref("000009:Fallout4.esm"),                                          # not placed by the build
                ref("000004:Fallout4.esm", disabled=1)]                              # initially disabled: not placed here either
        cl, rep = mc.containers(refs, placed, TABLE)
        self.assertEqual([c["src"] for c in cl["containers"]], ["19EE52:Fallout4.esm", "000001:Fallout4.esm", "000002:Fallout4.esm"])
        self.assertEqual([c["name"] for c in cl["containers"]], ["First Aid Kit", "Safe", "Loot Toolbox01"])
        self.assertEqual(cl["containers"][2]["items"], TABLE["default"]["items"])
        self.assertEqual(cl["containers"][0]["slot"], 1)
        self.assertEqual((rep["containers"], rep["distinct bases"], rep["not placed"]), (3, 3, 2))
        self.assertEqual(rep["table default"], 1)

    def test_limit_and_only_known(self):
        placed = ["000001:Fallout4.esm", "000002:Fallout4.esm"]
        refs = [ref("000001:Fallout4.esm", edid="Loot_Safe01"), ref("000002:Fallout4.esm", edid="Loot_Toolbox01")]
        cl, rep = mc.containers(refs, placed, TABLE, limit=1)
        self.assertEqual(len(cl["containers"]), 1)
        self.assertEqual(rep["cut by --limit"], 1)
        cl, rep = mc.containers(refs, placed, TABLE, only_known=True)
        self.assertEqual([c["src"] for c in cl["containers"]], ["000001:Fallout4.esm"])
        self.assertEqual(rep["skipped (default only)"], 1)

    def test_report_and_cli_on_synthetic_bands(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "work", "export"))
            os.makedirs(os.path.join(d, "build"))
            band = {"refs": [ref("000001:Fallout4.esm", edid="Loot_Safe01"), ref("000002:Fallout4.esm", typ="Static")]}
            json.dump(band, open(os.path.join(d, "work", "export", "band_-5_4.json"), "w"))
            json.dump({"refs": [{"src": "000002:Fallout4.esm"}, {"src": "000001:Fallout4.esm"}]}, open(os.path.join(d, "build", "objects.json"), "w"))
            json.dump(TABLE, open(os.path.join(d, "table.json"), "w"))
            out = os.path.join(d, "cluster.json")
            self.assertEqual(mc.main(["containers", "--work", os.path.join(d, "work"), "--build", os.path.join(d, "build"),
                                      "--table", os.path.join(d, "table.json"), "--out", out]), 0)
            cl = json.load(open(out))
            self.assertEqual([c["src"] for c in cl["containers"]], ["000001:Fallout4.esm"])
            all_c, placed_c = mc.by_type(mc.band_refs(os.path.join(d, "work")), mc.placed_sources(os.path.join(d, "build")))
            self.assertEqual((all_c["Container"], placed_c["Static"]), (1, 1))
            self.assertEqual(mc.main(["report", "--work", os.path.join(d, "work"), "--build", os.path.join(d, "build")]), 0)


class ItemsTests(unittest.TestCase):
    TABLE = {"default": {"name": None, "value": 5, "weight": 0.5},
             "by_editor_id": {"Stimpak*": {"name": "Stimpak", "value": 48, "weight": 0.1}}}

    def test_misc_and_ingestible_in_placement_order(self):
        placed = ["000002:Fallout4.esm", "000001:Fallout4.esm"]
        refs = [ref("000001:Fallout4.esm", typ="Ingestible", edid="Stimpak", base="23736:Fallout4.esm"),
                ref("000002:Fallout4.esm", typ="MiscItem", edid="Junk_Can", base="0001:Fallout4.esm"),
                ref("000003:Fallout4.esm", typ="Container")]
        cl, rep = mc.items(refs, placed, self.TABLE)
        self.assertEqual([(e["src"], e["name"], e["value"], e["kind"]) for e in cl["items"]],
                         [("000002:Fallout4.esm", "Junk Can", 5, "MiscItem"), ("000001:Fallout4.esm", "Stimpak", 48, "Ingestible")])
        self.assertEqual((rep["items"], rep["MiscItem"], rep["Ingestible"], rep["distinct bases"]), (2, 1, 1, 2))
        cl, rep = mc.items(refs, placed, self.TABLE, only_known=True)
        self.assertEqual([e["name"] for e in cl["items"]], ["Stimpak"])

    def test_world_weapon_becomes_a_pick_up_item(self):
        # owner, 2026-10-17: the tire iron before the Red Rocket bridge was a static; FO4 WEAP references are items now
        placed = ["000004:Fallout4.esm"]
        refs = [ref("000004:Fallout4.esm", typ="Weapon", edid="TireIron", base="0D1EB0:Fallout4.esm")]
        table = mc.load(os.path.join(ROOT, "scripts", "terrain", "clusters", "item_table.json"))
        cl, rep = mc.items(refs, placed, table)
        self.assertEqual([(e["src"], e["name"], e["kind"]) for e in cl["items"]],
                         [("000004:Fallout4.esm", "Tire Iron", "Weapon")])
        self.assertEqual((rep["items"], rep["Weapon"], rep["table prefix"]), (1, 1, 1))


def dump(value, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f)


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class ActivatorTerminalTests(unittest.TestCase):
    NAMES = {"0BB1E1:Fallout4.esm": "Bell", "0BB1E2:Fallout4.esm": None, "0E1E33:Fallout4.esm": "Zeke's Terminal",
             "0E1E34:Fallout4.esm": None}

    @staticmethod
    def a(fk, edid="Bell_Free", base="0BB1E1:Fallout4.esm", model="SetDressing\\Boats\\Bell_01.nif", typ="Activator", **kw):
        r = ref(fk, typ=typ, edid=edid, base=base)
        r.update(model=model, **kw)
        return r

    def test_activators_in_placement_order_with_fo4_names(self):
        placed = ["000004:Fallout4.esm", "000001:Fallout4.esm", "000002:Fallout4.esm", "000003:Fallout4.esm",
                  "000006:Fallout4.esm", "000008:Fallout4.esm"]
        refs = [self.a("000001:Fallout4.esm"),
                self.a("000002:Fallout4.esm", edid="SpotLightDetect01", base="0BB1E2:Fallout4.esm"),     # FO4: no FULL
                self.a("000003:Fallout4.esm", edid="Standpipe01", base="0BB1E3:Fallout4.esm"),            # not in names
                self.a("000004:Fallout4.esm", edid="TrapTrigPlate01", base="0BB1E4:Fallout4.esm"),
                self.a("000005:Fallout4.esm", edid="DefaultActivateSelfTrigger", model=""),               # not placed
                self.a("000006:Fallout4.esm", edid="DefaultDummy", model="markers\\MarkerDummy01.nif"),   # marker model
                self.a("000007:Fallout4.esm", edid="AO_Comment_Marker_512", model="markers\\c512.nif"),
                self.a("000008:Fallout4.esm", disabled=1),
                ref("000009:Fallout4.esm", typ="Static")]
        table = {"by_editor_id": {"TrapTrig*": {"name": "Bathroom Scale"}}}
        skipped = {"000007:Fallout4.esm": "editor_marker"}
        cl, rep = mc.activators(refs, placed, table, self.NAMES, skipped)
        self.assertEqual([(e["src"], e["name"], e["name_from"]) for e in cl["activators"]],
                         [("000004:Fallout4.esm", "Bathroom Scale", "table"), ("000001:Fallout4.esm", "Bell", "fo4"),
                          ("000002:Fallout4.esm", None, "fo4 (no name)"), ("000003:Fallout4.esm", "Standpipe01", "editor id")])
        self.assertEqual([e["slot"] for e in cl["activators"]], [0, 1, 2, 3])
        self.assertEqual((rep["activators"], rep["distinct bases"]), (4, 4))
        ex = cl["excluded"]
        self.assertEqual({k: v["refs"] for k, v in ex.items()},
                         {"no_model": 1, "editor_marker": 1, "initially disabled": 1,
                          "placed without a model / with a marker model": 1})
        self.assertEqual(ex["no_model"]["patterns"], {"trigger volume": {"refs": 1, "editor_ids": {"DefaultActivateSelfTrigger": 1}}})
        self.assertEqual(list(ex["editor_marker"]["patterns"]), ["editor / comment marker"])
        self.assertEqual(list(ex["placed without a model / with a marker model"]["patterns"]), ["dummy"])
        cl, rep = mc.activators(refs, placed, limit=2)                       # no names, no table: humanized editor ids
        self.assertEqual([e["name"] for e in cl["activators"]], ["Trap Trig Plate01", "Bell Free"])
        self.assertEqual(rep["cut by --limit"], 2)

    def test_terminals_carry_the_body_and_a_name(self):
        placed = ["000001:Fallout4.esm", "000002:Fallout4.esm"]
        refs = [self.a("000001:Fallout4.esm", typ="Terminal", edid="DN054_ZekesTerminal", base="0E1E33:Fallout4.esm",
                       model="Furniture\\Terminals\\TerminalOn.nif"),
                self.a("000002:Fallout4.esm", typ="Terminal", edid="DefaultTerminalDesk", base="0E1E34:Fallout4.esm",
                       model="Furniture\\Terminals\\TerminalOn.nif"),
                self.a("000003:Fallout4.esm")]                                     # an activator: not a terminal
        cl, rep = mc.terminals(refs, placed, None, self.NAMES)
        self.assertEqual([(e["name"], e["body"]) for e in cl["terminals"]],
                         [("Zeke's Terminal", mc.TERMINAL_BODY), ("Terminal", mc.TERMINAL_BODY)])   # no FULL: "Terminal"
        self.assertEqual(mc.TERMINAL_BODY, "FO4 terminal (text not ported yet)")
        self.assertEqual((rep["terminals"], cl["excluded"]), (2, {}))

    def test_excluded_patterns(self):
        cases = {"DefaultActivateSelfTrigger": "trigger volume", "RETriggerScene": "trigger volume",
                 "DefaultSetAVTrig": "trigger volume", "PackageLocationPrimitive": "package / sandbox primitive",
                 "AO_Comment_Marker_512": "editor / comment marker", "FloatingPlatformHelper01": "platform / rotate helper",
                 "DefaultDummyOFF": "dummy", "BirdZone": "zone / area", "FlightAvoidArea": "zone / area",
                 "EMSystemTurf": "zone / area", "SimpleElevatorMaster": "master (elevator, lift, breaker)",
                 "Water1024ExtPuddle": "water plane", "DefaultActivator": "default / music activator",
                 "DNSC_MusicActivator": "default / music activator",
                 "TrapTrigPlate01": "other", "TrapExplOilPool01": "other", "MirelurkEgg_Harvestable": "other"}
        for edid, label in cases.items():
            self.assertEqual(mc.excluded_pattern(edid), label, edid)

    def test_placed_sources_put_promoted_entries_back_in_their_slots(self):
        with tempfile.TemporaryDirectory() as d:
            o = {"refs": [{"src": "B"}, {"src": "D"}],
                 "containers": [{"src": "A", "reference_index": 0}], "terminals": [{"src": "E", "reference_index": 4}],
                 "activators": [{"src": "C", "reference_index": 2}]}
            dump(o, os.path.join(d, "objects.json"))
            self.assertEqual(mc.placed_sources(d), ["A", "B", "C", "D", "E"])
            self.assertEqual(mc.skipped_reasons(d), {})

    def test_cli_on_synthetic_bands_names_and_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "work", "export"))
            os.makedirs(os.path.join(d, "build"))
            band = {"refs": [self.a("000001:Fallout4.esm"), self.a("000002:Fallout4.esm", edid="BirdZone", model=""),
                             self.a("000003:Fallout4.esm", typ="Terminal", edid="DN054_ZekesTerminal", base="0E1E33:Fallout4.esm")]}
            dump(band, os.path.join(d, "work", "export", "band_-5_4.json"))
            dump({"refs": [{"src": "000001:Fallout4.esm"}, {"src": "000003:Fallout4.esm"}]}, os.path.join(d, "build", "objects.json"))
            dump({"refs": [{"formkey": "000002:Fallout4.esm", "reason": "no_model"}]}, os.path.join(d, "build", "skipped.json"))
            dump({"plugin": "Fallout4.esm", "names": {k: {"type": "Activator", "editor_id": "x", "name": v}
                                                     for k, v in self.NAMES.items()}}, os.path.join(d, "names.json"))
            common = ["--work", os.path.join(d, "work"), "--build", os.path.join(d, "build"),
                      "--names", os.path.join(d, "names.json")]
            out = os.path.join(d, "a.json")
            self.assertEqual(mc.main(["activators"] + common + ["--out", out]), 0)
            cl = read(out)
            self.assertEqual([(e["src"], e["name"]) for e in cl["activators"]], [("000001:Fallout4.esm", "Bell")])
            self.assertEqual(cl["excluded"]["no_model"]["patterns"]["zone / area"]["refs"], 1)
            self.assertEqual(mc.main(["terminals"] + common + ["--out", out]), 0)
            self.assertEqual([e["name"] for e in read(out)["terminals"]], ["Zeke's Terminal"])


def fo4_base(edid="defaultLightFire01NSFlicker", fade=1.0, flags=0x9, radius=256, model=None):
    """A fo4light.parse_ligh() result."""
    return {"edid": edid, "bounds": [-9, -10, -18, 9, 10, 12], "model": model, "fade": fade, "gobo": None, "lens": None,
            "god_rays": None, "sound": None, "data_size": 64, "time": -1, "radius": radius, "color": [237, 168, 122],
            "flags": flags, "falloff": 1.0, "fov": 90.0, "near_clip": 7.2174, "flicker_period": 0.36, "flicker_intensity": 0.8,
            "flicker_movement": 0.8, "constant": 0.0, "scalar": 1.0, "exponent": 2.0, "god_rays_near_clip": 0.0,
            "value": 0, "weight": 0.0, "record_flags": 0}


def light_ref(fk, base="08ADFA:Fallout4.esm", pos=(700.0, 1400.0, 70.0), **kw):
    r = dict(ref(fk, typ="Light", edid="defaultLightFire01NSFlicker", base=base), pos=list(pos), rot=[0.0, 0.0, 1.0],
             scale=1, enable_parent=None)
    r.update(kw)
    return r


class LightsTests(unittest.TestCase):
    BASES = {0x08ADFA: fo4_base(), 0x0517B0: fo4_base("DefaultLightWhite01NS", flags=0x1, model="L.nif"),
             0x1C0DE0: fo4_base("AmbientModifierDarkGrey01Amb", flags=0x100001)}

    def refs_and_fields(self):
        refs = [light_ref("000003:Fallout4.esm"), light_ref("000001:Fallout4.esm", disabled=1),
                light_ref("000002:Fallout4.esm", base="0517B0:Fallout4.esm", enable_parent={"ref": "x"}),
                light_ref("000004:Fallout4.esm", base="1C0DE0:Fallout4.esm"),            # ambient only: skipped
                light_ref("000005:Fallout4.esm", base="999999:Fallout4.esm"),            # base not in Fallout4.esm
                light_ref("000006:DLCCoast.esm"),                                         # another plugin's reference
                ref("000007:Fallout4.esm", typ="Static")]                                 # not a light
        fields = {1: {"radius_delta": None, "lighting": {"fov": 0, "fade": 3.0, "near_clip": 0}, "emittance": None,
                      "flags": 0x30100 | 0x800},                       # FO4 header: the three light bits + disabled
                  2: {"radius_delta": 70.0, "lighting": None, "emittance": 0x1173},
                  3: {"radius_delta": -35.0, "lighting": {"fov": -10.0, "fade": -0.5, "near_clip": 14.0}, "emittance": None,
                      "flags": 0},
                  4: {"radius_delta": None, "lighting": None, "emittance": None},
                  5: {"radius_delta": None, "lighting": None, "emittance": None}}
        return refs, fields

    def test_every_light_in_source_order_with_its_mapped_base(self):
        refs, fields = self.refs_and_fields()
        cl, rep = mc.lights(refs, self.BASES, fields, lumens_per_m2=333.0)
        self.assertEqual([e["src"] for e in cl["lights"]], ["000001:Fallout4.esm", "000002:Fallout4.esm", "000003:Fallout4.esm"])
        self.assertEqual(set(cl["light_bases"]), {"08ADFA:Fallout4.esm", "0517B0:Fallout4.esm"})
        fire = cl["light_bases"]["08ADFA:Fallout4.esm"]
        # the fire base's two references have intensities 4.0 and 0.5 x (221 / 256)^2 (fade x its XRDS radius squared,
        # the review of #246): their median goes into the lumens
        third_i = 0.5 * ((256 - 35) / 256) ** 2
        scale = (4.0 + third_i) / 2
        self.assertEqual(fire["intensity_scale"], round(scale, 6))
        self.assertEqual(fire["lumens"], round(333.0 * 1.0 * scale * (256 / 70.0) ** 2))
        self.assertEqual((fire["editor_id"], fire["flicker_effect"], fire["dropped"]), ("defaultLightFire01NSFlicker", 1, []))
        self.assertEqual(cl["light_bases"]["0517B0:Fallout4.esm"]["dropped"], ["model"])
        first, second, third = cl["lights"]
        self.assertEqual(first["lighting"]["fade"], 1.6)                     # 4.0 / 2.19 = 1.83: clamped
        self.assertEqual((first["record_flags"], second["record_flags"], third["record_flags"]), (0x30100, 0, 0))
        self.assertTrue(first["disabled"])
        self.assertEqual(first["fo4_pos"], [700.0, 1400.0, 70.0])             # units, as exported: stage converts
        self.assertEqual((second["radius_delta"], second["lighting"]), (1.0, None))   # its base's only light: scale = it
        self.assertEqual(cl["light_bases"]["0517B0:Fallout4.esm"]["intensity_scale"], round((326 / 256) ** 2, 6))
        self.assertEqual(third["lighting"], {"fov": -10.0, "fade": round(third_i / scale, 6), "near_clip": 0.2})
        self.assertEqual(third["radius_delta"], -0.5)
        self.assertEqual((rep["lights"], rep["distinct bases"], rep["skipped (ambient_only)"],
                          rep["skipped (not found in Fallout4.esm)"], rep["skipped (not a Fallout4.esm light)"]), (3, 2, 1, 1, 1))
        self.assertEqual((rep["fade clamped to the vanilla XLIG range"], rep["emittance (XEMI) not carried"],
                          rep["enable parent not translated"], rep["initially disabled"]), (1, 1, 1, 1))
        self.assertEqual(rep["features not carried (references)"], {"model": 1})
        self.assertEqual((rep["record flag does not light water (0x100)"], rep["record flag never fades (0x10000)"],
                          rep["record flag does not light landscape (0x20000)"]), (1, 1, 1))

    def test_limit_keeps_the_bases_of_the_kept_lights_and_their_full_scale(self):
        refs, fields = self.refs_and_fields()
        cl, rep = mc.lights(refs, self.BASES, fields, limit=1)
        self.assertEqual([e["src"] for e in cl["lights"]], ["000001:Fallout4.esm"])
        self.assertEqual(list(cl["light_bases"]), ["08ADFA:Fallout4.esm"])
        self.assertEqual(cl["light_bases"]["08ADFA:Fallout4.esm"]["intensity_scale"],          # from both references
                         round((4.0 + 0.5 * (221 / 256) ** 2) / 2, 6))
        self.assertEqual(rep["cut by --limit"], 2)

    def test_cli_reads_fallout4_esm_raw(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from test_fo4light import synthetic_esm                           # a TES4 + LIGH + two worldspaces fixture
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "work", "export"))
            esm = os.path.join(d, "Fallout4.esm")
            synthetic_esm(esm)
            band = {"refs": [light_ref("000102:Fallout4.esm"), light_ref("000101:Fallout4.esm"),
                             light_ref("000201:Fallout4.esm")]}           # 000201 lives in the other worldspace
            with open(os.path.join(d, "work", "export", "band_-5_4.json"), "w") as f:
                json.dump(band, f)
            out = os.path.join(d, "lights.json")
            self.assertEqual(mc.main(["lights", "--work", os.path.join(d, "work"), "--fo4", esm, "--out", out]), 0)
            with open(out) as f:
                cl = json.load(f)
        self.assertEqual([e["src"] for e in cl["lights"]], ["000101:Fallout4.esm", "000102:Fallout4.esm"])
        self.assertEqual(cl["lights"][0]["radius_delta"], round(-58.5 / 70.0, 6))
        self.assertEqual(list(cl["light_bases"]), ["08ADFA:Fallout4.esm"])
        self.assertEqual(cl["lumens_per_m2"], 333.0)

    def test_fo4_local_id(self):
        self.assertEqual(mc.fo4_local_id("08ADFA:Fallout4.esm"), 0x08ADFA)
        self.assertEqual(mc.fo4_local_id("08adfa:FALLOUT4.ESM"), 0x08ADFA)
        self.assertIsNone(mc.fo4_local_id("08ADFA:DLCCoast.esm"))
        self.assertIsNone(mc.fo4_local_id("zz:Fallout4.esm"))
        self.assertIsNone(mc.fo4_local_id(None))


def vmad(scripts):
    """A FO4 VMAD blob (version 6, object format 2): each script with one object property (as workshopscript's
    WorkshopParent) so that the parser has to skip property data to reach the next name."""
    out = struct.pack("<HHH", 6, 2, len(scripts))
    for name in scripts:
        out += struct.pack("<H", len(name)) + name.encode() + struct.pack("<BH", 0, 2)
        out += struct.pack("<H", 14) + b"WorkshopParent" + struct.pack("<BB", 1, 1) + struct.pack("<IHH", 0x02058E, 0, 0)
        out += struct.pack("<H", 5) + b"Names" + struct.pack("<BB", 12, 1) + struct.pack("<I", 2) + b"\x01\x00a\x02\x00bc"
    return out


def station_esm(path):
    """A synthetic Fallout4.esm: CONT (the workshop with workshopscript, one with another script, one without VMAD)
    and FURN (bench types 2 / 7 / 5 / 8 / 0 and a bench type without a table entry) groups."""
    from test_fo4light import record, group
    tes4 = b"TES4" + struct.pack("<IIIIHH", 0, 0, 0, 0, 131, 0)
    conts = group(b"CONT", 0, [
        record(b"CONT", 0x0C1AEB, [(b"EDID", b"WorkshopWorkbench\0"), (b"VMAD", vmad(["workshopscript"])),
                                   (b"KWDA", struct.pack("<2I", 0x054BA7, 0x04AF68))]),
        record(b"CONT", 0x246F86, [(b"EDID", b"WorkshopWorkbenchNonSettlement\0"), (b"VMAD", vmad(["Other", "WorkshopScript"])),
                                   (b"KWDA", struct.pack("<I", 0x054BA7))], compress=True),
        record(b"CONT", 0x22BF75, [(b"EDID", b"WorkshopResourceContainerSettlement\0"), (b"VMAD", vmad(["WorkshopResourceScript"]))]),
        record(b"CONT", 0x04B6E9, [(b"EDID", b"Loot_Prewar_Medkit\0")])])
    furns = group(b"FURN", 0, [
        record(b"FURN", 0x17B3A4, [(b"EDID", b"workbenchWeaponsA\0"), (b"WBDT", b"\x02\x00")]),
        record(b"FURN", 0x12EA9B, [(b"EDID", b"WorkbenchArmorA\0"), (b"WBDT", b"\x07\x00")], compress=True),
        record(b"FURN", 0x1487C1, [(b"EDID", b"WorkbenchChemistryB\0"), (b"WBDT", b"\x05\x00")]),
        record(b"FURN", 0x14FBCD, [(b"EDID", b"WorkbenchCookingSpit\0"), (b"WBDT", b"\x05\x00")]),
        record(b"FURN", 0x157FEB, [(b"EDID", b"WorkbenchPowerArmor\0"), (b"WBDT", b"\x08\x00")]),
        record(b"FURN", 0x1796AE, [(b"EDID", b"SupermutantCookingCauldron\0"), (b"WBDT", b"\x00\x00")]),
        record(b"FURN", 0x0ABCDE, [(b"EDID", b"WorkbenchMystery\0"), (b"WBDT", b"\x0b\x00")]),
        record(b"FURN", 0x0ABCDF, [(b"EDID", b"WorkbenchCookingOdd\0"), (b"WBDT", b"\x02\x00")]),
        record(b"FURN", 0x0ABCE0, [(b"EDID", b"ChairPatio01\0")])])
    with open(path, "wb") as f:
        f.write(tes4 + conts + furns)


BENCH_TABLE = {"by_editor_id": {"workbenchWeapons*": {"kind": "weapon"}, "WorkbenchArmor*": {"kind": "armor"},
                                "WorkbenchChemistry*": {"kind": "chem"}, "WorkbenchCooking*": {"kind": "cooking"},
                                "WorkbenchPowerArmor*": {"kind": None, "reason": "power armor station: no Starfield bench type 8"},
                                "WorkbenchOdd*": {"kind": "stone"}}}


class StationTests(unittest.TestCase):
    """make_cluster.py workshops / benches (docs/terrain/stations.md): the settlement workshops by their VMAD script,
    the crafting stations by their WBDT bench type, both read raw from a synthetic Fallout4.esm."""

    @staticmethod
    def st(fk, typ, edid, base, model="SetDressing\\Garage\\WorkbenchGarage01.nif", **kw):
        r = ref(fk, typ=typ, edid=edid, base=base)
        r.update(model=model, **kw)
        return r

    def refs(self):
        return [self.st("054BAE:Fallout4.esm", "Container", "WorkshopWorkbench", "0C1AEB:Fallout4.esm"),
                self.st("0B3506:Fallout4.esm", "Container", "WorkshopWorkbenchNonSettlement", "246F86:Fallout4.esm"),
                self.st("019956:Fallout4.esm", "Container", "WorkshopWorkbench", "0C1AEB:Fallout4.esm", disabled=1),
                self.st("019957:Fallout4.esm", "Container", "WorkshopWorkbench", "0C1AEB:Fallout4.esm"),      # not placed
                self.st("22BF76:Fallout4.esm", "Container", "WorkshopResourceContainerSettlement", "22BF75:Fallout4.esm"),
                self.st("000011:Fallout4.esm", "Container", "Loot_Prewar_Medkit", "04B6E9:Fallout4.esm"),
                self.st("000012:DLCCoast.esm", "Container", "WorkshopWorkbench", "0C1AEB:DLCCoast.esm"),       # not Fallout4.esm
                self.st("1A708B:Fallout4.esm", "Furniture", "workbenchWeaponsA", "17B3A4:Fallout4.esm", model="w.nif"),
                self.st("178D9F:Fallout4.esm", "Furniture", "WorkbenchArmorA", "12EA9B:Fallout4.esm", model="a.nif"),
                self.st("1AB6BE:Fallout4.esm", "Furniture", "WorkbenchChemistryB", "1487C1:Fallout4.esm", model="c.nif"),
                self.st("178D9D:Fallout4.esm", "Furniture", "WorkbenchCookingSpit", "14FBCD:Fallout4.esm", model="s.nif"),
                self.st("17FC5E:Fallout4.esm", "Furniture", "WorkbenchPowerArmor", "157FEB:Fallout4.esm", model="p.nif"),
                self.st("000021:Fallout4.esm", "Furniture", "SupermutantCookingCauldron", "1796AE:Fallout4.esm", model="k.nif"),
                self.st("000022:Fallout4.esm", "Furniture", "WorkbenchMystery", "0ABCDE:Fallout4.esm", model="m.nif"),
                self.st("000023:Fallout4.esm", "Furniture", "WorkbenchCookingOdd", "0ABCDF:Fallout4.esm", model="o.nif"),
                self.st("000024:Fallout4.esm", "Furniture", "ChairPatio01", "0ABCE0:Fallout4.esm", model="ch.nif"),
                self.st("000025:Fallout4.esm", "Furniture", "workbenchWeaponsA", "17B3A4:Fallout4.esm", model="w.nif", disabled=1),
                ref("000026:Fallout4.esm", typ="Static")]

    PLACED = ["000011:Fallout4.esm", "1A708B:Fallout4.esm", "054BAE:Fallout4.esm", "178D9F:Fallout4.esm", "0B3506:Fallout4.esm",
              "019956:Fallout4.esm", "22BF76:Fallout4.esm", "1AB6BE:Fallout4.esm", "178D9D:Fallout4.esm", "17FC5E:Fallout4.esm",
              "000021:Fallout4.esm", "000022:Fallout4.esm", "000023:Fallout4.esm", "000024:Fallout4.esm", "000025:Fallout4.esm",
              "000012:DLCCoast.esm", "000026:Fallout4.esm"]

    def bases(self):
        with tempfile.TemporaryDirectory() as d:
            esm = os.path.join(d, "Fallout4.esm")
            station_esm(esm)
            return mc.station_bases(esm, self.refs())

    def test_vmad_script_names_and_raw_bases(self):
        from fo4sf import fo4station
        self.assertEqual(fo4station.vmad_scripts(vmad(["workshopscript", "Second"])), ["workshopscript", "Second"])
        self.assertEqual(fo4station.vmad_scripts(None), [])
        with self.assertRaises(ValueError):
            fo4station.vmad_scripts(b"\x06\x00\x02\x00")                       # too short
        with self.assertRaises(ValueError):
            fo4station.vmad_scripts(struct.pack("<HHH", 9, 2, 0))                # a version this does not parse
        bases = self.bases()
        self.assertEqual(sorted(bases), [0x04B6E9, 0x0ABCDE, 0x0ABCDF, 0x0ABCE0, 0x0C1AEB, 0x12EA9B, 0x1487C1, 0x14FBCD,
                                         0x157FEB, 0x1796AE, 0x17B3A4, 0x22BF75, 0x246F86])
        self.assertEqual((bases[0x0C1AEB]["type"], bases[0x0C1AEB]["scripts"], bases[0x0C1AEB]["keywords"]),
                         ("CONT", ["workshopscript"], [0x054BA7, 0x04AF68]))
        self.assertEqual(bases[0x246F86]["scripts"], ["Other", "WorkshopScript"])    # compressed record, second script
        self.assertTrue(fo4station.has_script(bases[0x246F86], "workshopscript"))      # case-blind
        self.assertFalse(fo4station.has_script(bases[0x22BF75], "workshopscript"))
        self.assertEqual([bases[i]["wbdt"] for i in (0x17B3A4, 0x12EA9B, 0x1487C1, 0x157FEB, 0x1796AE, 0x0ABCE0)],
                         [2, 7, 5, 8, 0, None])

    def test_workshops_are_the_containers_with_the_workshop_script(self):
        cl, rep = mc.workshops(self.refs(), self.PLACED, self.bases(), {"019957:Fallout4.esm": "outside_terrain"})
        self.assertEqual([(e["src"], e["editor_id"], e["slot"]) for e in cl["workshops"]],
                         [("054BAE:Fallout4.esm", "WorkshopWorkbench", 2), ("0B3506:Fallout4.esm", "WorkshopWorkbenchNonSettlement", 4)])
        e = cl["workshops"][0]
        self.assertEqual((e["name"], e["radius"], e["base"]), (mc.WORKSHOP_NAME, mc.WORKSHOP_RADIUS_M, "0C1AEB:Fallout4.esm"))
        self.assertEqual((mc.WORKSHOP_NAME, mc.WORKSHOP_RADIUS_M, mc.WORKSHOP_KEYWORD), ("Workshop", 250.0, 0x054BA7))
        self.assertEqual((rep["workshops"], rep["distinct bases"], rep["containers without the workshop script"],
                          rep["container base not in Fallout4.esm"], rep["with WorkshopKeyword in the FO4 KWDA"]), (2, 2, 2, 1, 4))
        self.assertEqual({k: v["refs"] for k, v in cl["excluded"].items()}, {"initially disabled": 1, "outside_terrain": 1})
        cl, rep = mc.workshops(self.refs(), self.PLACED, self.bases(), limit=1)
        self.assertEqual((len(cl["workshops"]), rep["cut by --limit"]), (1, 1))

    def test_benches_by_bench_type_and_table_kind(self):
        cl, rep = mc.benches(self.refs(), self.PLACED, self.bases(), BENCH_TABLE)
        self.assertEqual([(e["src"], e["kind"], e["vanilla"], e["wbdt"], e["slot"]) for e in cl["benches"]],
                         [("1A708B:Fallout4.esm", "weapon", "2B6A63:Starfield.esm", 2, 1),
                          ("178D9F:Fallout4.esm", "armor", "2B6A62:Starfield.esm", 7, 3),
                          ("1AB6BE:Fallout4.esm", "chem", "2B6A61:Starfield.esm", 5, 7),
                          ("178D9D:Fallout4.esm", "cooking", "2B6A65:Starfield.esm", 5, 8)])
        self.assertEqual(cl["kinds"], {k: v["vanilla"] for k, v in mc.BENCH_KINDS.items()})
        self.assertEqual({(s["editor_id"], s["wbdt"], s["reason"]) for s in cl["bench_skipped"]},
                         {("WorkbenchPowerArmor", 8, "power armor station: no Starfield bench type 8 (FO4 bench type 8 (power armor))"),
                          ("WorkbenchMystery", 11, "unknown kind: no table entry for WorkbenchMystery (FO4 bench type 11 (research))"),
                          ("WorkbenchCookingOdd", 2, "table kind cooking (bench type 5) disagrees with the base's FO4 bench type 2 (weapons)")})
        self.assertEqual((rep["benches"], rep["distinct bases"], rep["bench_skipped"], rep["weapon"], rep["cooking"],
                          rep["furniture that is no crafting station (WBDT 0)"]), (4, 4, 3, 1, 1, 2))
        self.assertEqual({k: v["refs"] for k, v in cl["excluded"].items()}, {"initially disabled": 1})
        self.assertEqual(mc.bench_reason("WorkbenchOddThing", 2, BENCH_TABLE), (None, "unknown kind 'stone' in the table (FO4 bench type 2 (weapons))"))
        self.assertEqual(mc.bench_reason("workbenchWeaponsB", 2, BENCH_TABLE), ("weapon", None))
        self.assertEqual(sorted(mc.BENCH_KINDS), ["armor", "chem", "cooking", "weapon"])
        self.assertEqual([mc.BENCH_KINDS[k]["wbdt"] for k in ("weapon", "armor", "chem", "cooking")], [2, 7, 5, 5])

    def test_container_table_skip_drops_the_workshop_bases(self):
        table = {"default": {"name": None, "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
                 "by_editor_id": {"WorkshopWorkbench": {"skip": "settlement workshop"}}}
        cl, rep = mc.containers(self.refs(), self.PLACED, table)
        self.assertNotIn("054BAE:Fallout4.esm", [c["src"] for c in cl["containers"]])
        self.assertIn("0B3506:Fallout4.esm", [c["src"] for c in cl["containers"]])     # not in this table: still a container
        self.assertEqual(rep["skipped by the table (settlement workshop)"], 2)
        repo_table = read(os.path.join(ROOT, "scripts", "terrain", "clusters", "container_table.json"))
        for edid in ("WorkshopWorkbench", "WorkshopWorkbenchNonSettlement"):
            self.assertTrue(repo_table["by_editor_id"][edid].get("skip"), edid)
        bench_table = read(os.path.join(ROOT, "scripts", "terrain", "clusters", "bench_table.json"))
        kinds = {k: v.get("kind") for k, v in bench_table["by_editor_id"].items()}
        self.assertEqual({kinds[k] for k in ("workbenchWeapons*", "WorkbenchArmor*", "WorkbenchChemistry*", "WorkbenchCooking*")},
                         {"weapon", "armor", "chem", "cooking"})
        self.assertIsNone(kinds["WorkbenchPowerArmor*"])
        self.assertNotIn("default", bench_table)

    def test_merge_one_class_per_input(self):
        a = {"note": "x", "workshops": [1], "excluded": {}}
        b = {"benches": [2], "bench_skipped": [3], "kinds": {}}
        c = {"containers": [4], "items": [5]}
        m = mc.merge({"a.json": a, "b.json": b, "c.json": c})
        self.assertEqual({k: v for k, v in m.items() if k != "note"}, {"workshops": [1], "benches": [2], "containers": [4], "items": [5]})
        self.assertIn("a.json + b.json + c.json", m["note"])
        with self.assertRaisesRegex(ValueError, "'items' is in both c.json and d.json"):
            mc.merge({"c.json": c, "d.json": {"items": []}})
        self.assertEqual(mc.MERGE_KEYS, ("containers", "items", "activators", "terminals", "lights", "light_bases",
                                         "lumens_per_m2", "workshops", "benches", "doors", "doors_port"))

    def test_placed_sources_know_the_station_classes(self):
        with tempfile.TemporaryDirectory() as d:
            dump({"refs": [{"src": "B"}], "workshops": [{"src": "A", "reference_index": 0}],
                  "benches": [{"src": "C", "reference_index": 2}]}, os.path.join(d, "objects.json"))
            self.assertEqual(mc.placed_sources(d), ["A", "B", "C"])
        self.assertEqual(mc.PROMOTED_KEYS, ("containers", "items", "activators", "terminals", "workshops", "benches", "doors"))

    def test_cli_on_synthetic_bands_and_esm(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "work", "export"))
            os.makedirs(os.path.join(d, "build"))
            esm = os.path.join(d, "Fallout4.esm")
            station_esm(esm)
            dump({"refs": self.refs()}, os.path.join(d, "work", "export", "band_-5_4.json"))
            dump({"refs": [{"src": s} for s in self.PLACED]}, os.path.join(d, "build", "objects.json"))
            dump(BENCH_TABLE, os.path.join(d, "bench_table.json"))
            common = ["--work", os.path.join(d, "work"), "--build", os.path.join(d, "build"), "--fo4", esm]
            w, b, m = (os.path.join(d, n) for n in ("w.json", "b.json", "m.json"))
            self.assertEqual(mc.main(["workshops"] + common + ["--out", w]), 0)
            self.assertEqual([e["src"] for e in read(w)["workshops"]], ["054BAE:Fallout4.esm", "0B3506:Fallout4.esm"])
            self.assertEqual(mc.main(["benches"] + common + ["--table", os.path.join(d, "bench_table.json"), "--out", b]), 0)
            self.assertEqual([e["kind"] for e in read(b)["benches"]], ["weapon", "armor", "chem", "cooking"])
            self.assertEqual(mc.main(["merge", "--out", m, w, b]), 0)
            merged = read(m)
            self.assertEqual((len(merged["workshops"]), len(merged["benches"])), (2, 4))
            self.assertNotIn("excluded", merged)
            dump(read(w), os.path.join(d, "w2.json"))                      # the same class twice: refused
            with self.assertRaises(SystemExit):
                mc.main(["merge", "--out", m, w, os.path.join(d, "w2.json")])



class DoorsTests(unittest.TestCase):
    """make_cluster.py doors (docs/terrain/scripted-doors.md): every exterior load door into a converted interior whose
    both sides are placed, with both arrival points, the port ids and the promised interior marker id; a door with a
    missing side is listed with the reason; merge and placed_sources know the class."""
    PORT = "FO4Port.esm"

    @staticmethod
    def door(fk, dest, pos, arrival, base="018C8B:Fallout4.esm", edid="IndMetalDoorLoad01", rot=2.5812, flags=0,
             model="Interiors\\Industrial\\Doors\\IndMetalDoorLoad01.nif"):
        r = ref(fk, typ="Door", edid=edid, base=base)
        r.update(model=model, pos=list(pos), rot=[0, 0, rot], scale=1,
                 teleport_destination={"door": dest, "pos": list(arrival), "rot": [0, 0, 4.7124], "flags": flags})
        return r

    def bands(self):
        return [self.door("0EE661:Fallout4.esm", "0EE5D6:Fallout4.esm", (-32889.703, 44569.62, 2964.9192), (381.42923, 1210.3624, -255.75)),
                self.door("0EED8A:Fallout4.esm", "0EE5B6:Fallout4.esm", (-34479.016, 42113.668, 3228.919), (1679.779, -1422.672, 0),
                          base="077CFC:Fallout4.esm", edid="PaintedWoodDoorDoubleLoadA01", flags=2),
                self.door("08EB65:Fallout4.esm", "05E844:Fallout4.esm", (-69646.37, 77664.305, 6907.905), (3.448, -463.539, -0.436),
                          base="01ED77:Fallout4.esm", edid="AutoloadDoor", model="AutoLoadMarker01.nif"),      # the cave: both sides markers
                self.door("000010:Fallout4.esm", "000011:Fallout4.esm", (100, 100, 0), (0, 0, 0)),                # not reciprocal
                self.door("000020:Fallout4.esm", "000021:Fallout4.esm", (100, 200, 0), (0, 0, 0)),                # interior not placed
                self.door("000030:Fallout4.esm", "000031:Fallout4.esm", (100, 300, 0), (0, 0, 0)),                # not a converted interior
                dict(self.door("000040:Fallout4.esm", "000041:Fallout4.esm", (100, 400, 0), (0, 0, 0)), teleport_destination=None),
                ref("000050:Fallout4.esm", typ="Static")]

    @staticmethod
    def inner(fk, back, pos, arrival, model="Interiors\\Industrial\\Doors\\IndMetalDoorLoad02.nif"):
        return {"formkey": fk, "type": "Door", "base_editor_id": "IndMetalDoorLoad02", "base_formkey": "0C9717:Fallout4.esm",
                "model": model, "pos": list(pos), "rot": [0, 0, 4.7124], "scale": 1, "disabled": 0,
                "teleport_destination": {"door": back, "pos": list(arrival), "rot": [0, 0, 2.5812], "flags": 0}}

    def port_folder(self, d):
        from test_vmad_patch import tiny_plugin
        port = os.path.join(d, "integ")
        os.makedirs(port)
        with open(os.path.join(port, self.PORT), "wb") as f:
            f.write(tiny_plugin())                                               # next free id 0x804
        dump({"CELL:FO4Port_SuperDuperMart01": 0x6C46, "REFR:FO4Port_SuperDuperMart01:0EE5D6:Fallout4.esm": 0x7D0B,
              "REFR:FO4Port_SuperDuperMart01:0EE5B6:Fallout4.esm": 0x7D0A, "CELL:FO4Port_RedRocket01": 0x2338,
              "CELL:FO4Port_Other": 0x900, "REFR:FO4Port_Other:000011:Fallout4.esm": 0x901},
             os.path.join(port, "formids.json"))
        dump({"cell": "SuperDuperMart01", "refs": [
            self.inner("0EE5D6:Fallout4.esm", "0EE661:Fallout4.esm", (448, 1216, -256), (-32861.09, 44525.188, 2964.9192)),
            self.inner("0EE5B6:Fallout4.esm", "0EED8A:Fallout4.esm", (1743.5, -1479.8, 0), (-34496.33, 42037.707, 3229.325))]},
             os.path.join(port, "SuperDuperMart01.json"))
        dump({"cell": "RedRocket01", "refs": [self.inner("05E844:Fallout4.esm", "08EB65:Fallout4.esm", (-116.1, 169.1, 0),
                                                         (-69687.12, 77290, 6984), model="AutoLoadMarker01.nif")]},
             os.path.join(port, "RedRocket01.json"))
        dump({"cell": "Other", "refs": [self.inner("000011:Fallout4.esm", "000012:Fallout4.esm", (0, 0, 0), (0, 0, 0)),
                                        self.inner("000021:Fallout4.esm", "000020:Fallout4.esm", (0, 0, 0), (0, 0, 0))]},
             os.path.join(port, "Other.json"))
        return port

    PLACED = ["000050:Fallout4.esm", "0EED8A:Fallout4.esm", "000010:Fallout4.esm", "0EE661:Fallout4.esm", "000020:Fallout4.esm",
              "000030:Fallout4.esm", "000040:Fallout4.esm"]

    def test_doors_with_both_sides_and_the_skipped_with_their_reason(self):
        with tempfile.TemporaryDirectory() as d:
            port = mc.port_index(self.port_folder(d))
        self.assertEqual((port["plugin"], port["next"]), (self.PORT, 0x804))
        self.assertEqual(port["refs"]["0EE5D6:Fallout4.esm"], ("FO4Port_SuperDuperMart01", 0x7D0B))
        self.assertIn("05E844:Fallout4.esm", port["exported"])
        cl, rep = mc.doors(self.bands(), self.PLACED, port, skipped={"08EB65:Fallout4.esm": "editor_marker"})
        self.assertEqual([e["src"] for e in cl["doors"]], ["0EED8A:Fallout4.esm", "0EE661:Fallout4.esm"])   # placement order
        e = cl["doors"][1]
        self.assertEqual((e["base"], e["editor_id"], e["name"], e["slot"]), ("018C8B:Fallout4.esm", "IndMetalDoorLoad01", "Door", 3))
        self.assertEqual(e["fo4_pos"], [-32889.703, 44569.62, 2964.9192])
        d = e["destination"]
        self.assertEqual((d["plugin"], d["door"], d["cell"], d["port_ref"], d["port_cell"], d["flags"]),
                         (self.PORT, "0EE5D6:Fallout4.esm", "FO4Port_SuperDuperMart01", "007D0B", "006C46", 0))
        self.assertEqual(d["arrival"]["pos"], [round(v / 70.0, 6) for v in (381.42923, 1210.3624, -255.75)])
        self.assertEqual(d["arrival"]["rot"], [0, 0, 4.7124])
        self.assertEqual(e["return"]["arrival"]["pos"], [round(v / 70.0, 6) for v in (-32861.09, 44525.188, 2964.9192)])
        self.assertEqual(e["return"]["arrival"]["rot"], [0, 0, 2.5812])
        self.assertEqual([x["destination"]["id"] for x in cl["doors"]], ["000804", "000805"])   # port next + k, in order
        self.assertEqual(cl["doors"][0]["destination"]["flags"], 2)
        self.assertEqual(cl["doors_port"], {"plugin": self.PORT, "next": "000804", "cells": 3})
        skipped = {s["src"]: s["reason"] for s in cl["door_skipped"]}
        self.assertEqual(set(skipped), {"08EB65:Fallout4.esm", "000010:Fallout4.esm", "000020:Fallout4.esm"})
        self.assertIn("exterior side not placed by the build (editor_marker)", skipped["08EB65:Fallout4.esm"])
        self.assertIn("interior side missing in the port (marker model", skipped["08EB65:Fallout4.esm"])
        self.assertIn("not reciprocal (interior door 000011:Fallout4.esm links to 000012:Fallout4.esm", skipped["000010:Fallout4.esm"])
        self.assertEqual(rep["left out: not reciprocal"], 1)
        self.assertIn("interior side missing in the port (not placed", skipped["000020:Fallout4.esm"])
        self.assertEqual((rep["doors"], rep["distinct bases"], rep["door_skipped"], rep["doors without an XTEL"],
                          rep["destination not a converted interior"]), (2, 2, 3, 1, 1))
        # --names gives the FO4 FULL; a limit keeps the first and renumbers nothing
        cl2, _rep = mc.doors(self.bands(), self.PLACED, port, names={"018C8B:Fallout4.esm": "Metal Door"}, limit=1)
        self.assertEqual([(x["src"], x["name"], x["destination"]["id"]) for x in cl2["doors"]], [("0EED8A:Fallout4.esm", "Door", "000804")])
        cl3, _rep = mc.doors(self.bands(), self.PLACED, port, names={"018C8B:Fallout4.esm": "Metal Door"})
        self.assertEqual(cl3["doors"][1]["name"], "Metal Door")

    def test_cli_merge_and_placed_sources(self):
        with tempfile.TemporaryDirectory() as d:
            port = self.port_folder(d)
            os.makedirs(os.path.join(d, "work", "export"))
            os.makedirs(os.path.join(d, "build"))
            dump({"refs": self.bands()}, os.path.join(d, "work", "export", "band_5_14.json"))
            conv = "fo4core\\interiors\\industrial\\doors\\indmetaldoorload01.nif"
            dump({"bases": [{"edid": "FO4Core_a", "model": "fo4core\\a.nif"}, {"edid": "FO4Core_indmetaldoorload01", "model": conv}],
                  "refs": [{"src": s, "base": 1 if s == "0EE661:Fallout4.esm" else 0} for s in self.PLACED]},
                 os.path.join(d, "build", "objects.json"))
            dump({"refs": [{"formkey": "08EB65:Fallout4.esm", "reason": "editor_marker"}]}, os.path.join(d, "build", "skipped.json"))
            out = os.path.join(d, "doors.json")
            self.assertEqual(mc.main(["doors", "--work", os.path.join(d, "work"), "--build", os.path.join(d, "build"),
                                      "--port", port, "--out", out]), 0)
            cl = read(out)
            self.assertEqual([e["src"] for e in cl["doors"]], ["0EED8A:Fallout4.esm", "0EE661:Fallout4.esm"])
            self.assertEqual(cl["doors"][1]["converted_model"], conv)
            self.assertEqual(len(cl["door_skipped"]), 3)
            merged = os.path.join(d, "merged.json")
            dump({"containers": [{"src": "X"}]}, os.path.join(d, "c.json"))
            self.assertEqual(mc.main(["merge", "--out", merged, os.path.join(d, "c.json"), out]), 0)
            m = read(merged)
            self.assertEqual(set(m) - {"note"}, {"containers", "doors", "doors_port"})
            self.assertEqual(m["doors_port"]["next"], "000804")
            dump(cl, os.path.join(d, "doors2.json"))
            with self.assertRaises(SystemExit):                                   # the class twice (two inputs)
                mc.main(["merge", "--out", merged, out, os.path.join(d, "doors2.json")])
            # a build that promoted doors puts them back in their slots
            dump({"refs": [{"src": s} for s in self.PLACED if s != "0EE661:Fallout4.esm"],
                  "doors": [{"src": "0EE661:Fallout4.esm", "reference_index": 3}]}, os.path.join(d, "build", "objects.json"))
            self.assertEqual(mc.placed_sources(os.path.join(d, "build")), self.PLACED)
            self.assertIn("doors", mc.PROMOTED_KEYS)
            self.assertIn("doors", mc.MERGE_KEYS)
            with self.assertRaisesRegex(SystemExit, "--port"):                    # no plugin in the folder
                mc.main(["doors", "--work", os.path.join(d, "work"), "--build", os.path.join(d, "build"),
                         "--port", os.path.join(d, "build"), "--out", out])


if __name__ == "__main__":
    unittest.main()
