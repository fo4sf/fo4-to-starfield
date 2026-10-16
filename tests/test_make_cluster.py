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


if __name__ == "__main__":
    unittest.main()
