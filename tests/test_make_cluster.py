"""make_cluster.py: the Commonwealth-wide promotion lists from the band exports and core64c's placed references."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
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



class DoorsTests(unittest.TestCase):
    """doors: exterior load doors whose XTEL destination is a placed door of a converted interior, both sides checked."""
    PORT = {"CELL:FO4Port_SuperDuperMart01": 27718, "REFR:FO4Port_SuperDuperMart01:0EE5D6:Fallout4.esm": 32011,
            "CELL:FO4Port_RedRocket01": 9016}
    PORT_RECS = {27718: "CELL", 32011: "REFR", 9016: "CELL"}

    @staticmethod
    def interiors():
        sdm = {"cell": "SuperDuperMart01", "formkey": "0320A2:Fallout4.esm", "refs": [
            {"formkey": "0EE5D6:Fallout4.esm", "type": "Door", "base_editor_id": "IndMetalDoorLoad02", "model": "Interiors\\IndMetalDoorLoad02.nif",
             "pos": [448, 1216, -256], "rot": [0, 0, 4.7123895],
             "teleport_destination": {"door": "0EE661:Fallout4.esm", "pos": [-32861.09, 44525.188, 2964.9192], "rot": [0, 0, 2.5812104], "flags": 0}}]}
        rr = {"cell": "RedRocket01", "formkey": "05E62F:Fallout4.esm", "refs": [
            {"formkey": "05E844:Fallout4.esm", "type": "Door", "base_editor_id": "AutoloadDoor", "model": "AutoLoadMarker01.nif", "pos": [-116.135, 169.106, 0], "rot": [0, 0, 5.7596],
             "teleport_destination": {"door": "08EB65:Fallout4.esm", "pos": [-69687.12, 77290, 6984], "rot": [0, 0, -3.1081858], "flags": 0}}]}
        return sdm, rr

    @staticmethod
    def exterior(fk="0EE661:Fallout4.esm", dest="0EE5D6:Fallout4.esm", **kw):
        r = {"formkey": fk, "type": "Door", "base_editor_id": "IndMetalDoorLoad01", "base_formkey": "018C8B:Fallout4.esm",
             "model": "Interiors\\IndMetalDoorLoad01.nif", "pos": [-32889.703, 44569.62, 2964.9192], "rot": [0, 0, 2.5812104], "scale": 1,
             "disabled": 0, "persistent": True, "exterior_cell": [-9, 10],
             "teleport_destination": {"door": dest, "pos": [381.42923, 1210.3624, -255.75], "rot": [0, 0, 4.7123895], "flags": 0}}
        r.update(kw)
        return r

    def index(self):
        sdm, rr = self.interiors()
        return {r["formkey"].casefold(): (e["cell"], r) for e in (sdm, rr) for r in e["refs"]}

    def test_both_sides_present_lists_the_door_with_both_arrivals(self):
        refs = [self.exterior(), self.exterior("08EB65:Fallout4.esm", "05E844:Fallout4.esm", base_editor_id="AutoloadDoor", model="AutoLoadMarker01.nif"),
                self.exterior("111111:Fallout4.esm", "222222:Fallout4.esm"),                      # into an unconverted interior
                self.exterior("333333:Fallout4.esm", teleport_destination=None), ref("444444:Fallout4.esm")]
        placed = {"0EE661:Fallout4.esm": 161262}
        skipped = [{"formkey": "08EB65:Fallout4.esm", "reason": "editor_marker", "detail": "editor marker model AutoLoadMarker01.nif"}]
        bases = {161262: {"edid": "FO4Core_indmetaldoorload01", "model": "fo4core\\x.nif", "door": False, "collision": "fo4-native"}}
        fo4 = {0x018C8B: {"name": "Door", "obnd": [[-0.8, -0.22857, 0.0], [0.8, 0.11429, 2.51429]], "fnam": 0}}
        cl, rep = mc.doors(refs, placed, skipped, bases, self.PORT, self.PORT_RECS, self.index(), fo4)
        self.assertEqual((rep["load doors"], rep["destination not a converted interior"], rep["doors"], rep["unplaced"]), (3, 1, 1, 1))
        d = cl["doors"][0]
        self.assertEqual((d["src"], d["slot"], d["name"], d["base"], d["core_base"]["edid"]), ("0EE661:Fallout4.esm", 161262, "Door", "018C8B:Fallout4.esm", "FO4Core_indmetaldoorload01"))
        self.assertEqual(d["pos"], [-469.8529, 636.70886, 42.35599])
        self.assertEqual(d["destination"]["port_id"], 32011)
        self.assertEqual(d["destination"]["port_key"], "REFR:FO4Port_SuperDuperMart01:0EE5D6:Fallout4.esm")
        self.assertEqual((d["destination"]["cell"], d["destination"]["port_cell_id"]), ("SuperDuperMart01", 27718))
        self.assertEqual(d["arrival_in"]["pos"], [5.44899, 17.29089, -3.65357])
        self.assertEqual(d["arrival_out"]["pos"], [-469.44414, 636.07411, 42.35599])
        self.assertEqual((d["arrival_out"]["rot"][2], d["xtel_flags"], d["reciprocal"]), (2.5812104, {"out": 0, "in": 0}, True))
        self.assertEqual(d["obnd"], fo4[0x018C8B]["obnd"])
        u = cl["unplaced"][0]
        self.assertEqual(u["src"], "08EB65:Fallout4.esm")
        self.assertIn("editor_marker", u["reason"])
        self.assertIn("interior side not in FO4Port.esm", u["reason"])
        # without Fallout4.esm the name is "Door" and the bounds None; --only and --limit
        cl2, _ = mc.doors(refs, placed, skipped, bases, self.PORT, self.PORT_RECS, self.index())
        self.assertEqual((cl2["doors"][0]["name"], cl2["doors"][0]["obnd"]), ("Door", None))
        cl3, rep3 = mc.doors(refs, placed, skipped, bases, self.PORT, self.PORT_RECS, self.index(), only=["0ee661:fallout4.esm"])
        self.assertEqual((len(cl3["doors"]), rep3["not in --only"]), (1, 1))
        cl4, _rep4 = mc.doors(refs, placed, skipped, bases, self.PORT, self.PORT_RECS, self.index(), limit=0)
        self.assertEqual(len(cl4["doors"]), 1)

    def test_a_port_key_without_its_record_is_a_missing_side(self):
        refs = [self.exterior()]
        placed = {"0EE661:Fallout4.esm": 5}
        bases = {5: {"edid": "e", "model": "m", "door": False, "collision": None}}
        cl, rep = mc.doors(refs, placed, [], bases, self.PORT, {27718: "CELL"}, self.index())
        self.assertEqual((rep["doors"], rep["unplaced"]), (0, 1))
        self.assertIn("is not a REFR", cl["unplaced"][0]["reason"])
        cl, _ = mc.doors(refs, placed, [], bases, self.PORT, None, self.index())              # no plugin to read: trusted
        self.assertEqual(len(cl["doors"]), 1)
        sdm, _rr = self.interiors()
        sdm["refs"][0]["teleport_destination"] = None
        idx = {r["formkey"].casefold(): (sdm["cell"], r) for r in sdm["refs"]}
        cl, _ = mc.doors(refs, placed, [], bases, self.PORT, self.PORT_RECS, idx)
        self.assertIn("no XTEL back", cl["unplaced"][0]["reason"])

    def test_read_strings(self):
        import struct
        entries = [(0x14F6B, b"Door\0"), (0x1AA16, b"Auto Door\0")]
        data_part = b"".join(t for _, t in entries)
        directory, off = b"", 0
        for sid, t in entries:
            directory += struct.pack("<II", sid, off)
            off += len(t)
        blob = struct.pack("<II", len(entries), len(data_part)) + directory + data_part
        self.assertEqual(mc.read_strings(blob), {0x14F6B: "Door", 0x1AA16: "Auto Door"})

    def test_cli_on_synthetic_folders(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "work", "export"))
            os.makedirs(os.path.join(d, "build"))
            os.makedirs(os.path.join(d, "port"))
            os.makedirs(os.path.join(d, "exports"))
            json.dump({"refs": [self.exterior(), ref("444444:Fallout4.esm")]}, open(os.path.join(d, "work", "export", "band_5_14.json"), "w"))
            json.dump({"bases": [{"edid": "FO4Core_indmetaldoorload01", "model": "fo4core\\x.nif"}],
                       "refs": [{"src": "444444:Fallout4.esm", "base": 0}, {"src": "0EE661:Fallout4.esm", "base": 0}]}, open(os.path.join(d, "build", "objects.json"), "w"))
            json.dump({"refs": {"0EE661:Fallout4.esm": "02D22C", "444444:Fallout4.esm": "000900"}}, open(os.path.join(d, "build", "formids.json"), "w"))
            json.dump({"refs": []}, open(os.path.join(d, "build", "skipped.json"), "w"))
            json.dump(self.PORT, open(os.path.join(d, "port", "formids.json"), "w"))
            sdm, rr = self.interiors()
            json.dump(sdm, open(os.path.join(d, "exports", "SuperDuperMart01.json"), "w"))
            json.dump(rr, open(os.path.join(d, "exports", "RedRocket01.json"), "w"))
            out = os.path.join(d, "doors.json")
            self.assertEqual(mc.main(["doors", "--work", os.path.join(d, "work"), "--build", os.path.join(d, "build"), "--port", os.path.join(d, "port"),
                                      "--exports", os.path.join(d, "exports"), "--out", out]), 0)
            cl = json.load(open(out))
            self.assertEqual([(e["src"], e["slot"], e["core_id"]) for e in cl["doors"]], [("0EE661:Fallout4.esm", 1, "02D22C")])
            self.assertEqual(cl["unplaced"], [])

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


if __name__ == "__main__":
    unittest.main()
