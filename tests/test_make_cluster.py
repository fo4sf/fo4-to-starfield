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

if __name__ == "__main__":
    unittest.main()
