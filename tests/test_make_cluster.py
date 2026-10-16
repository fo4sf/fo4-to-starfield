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


if __name__ == "__main__":
    unittest.main()
