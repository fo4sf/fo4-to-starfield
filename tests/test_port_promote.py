"""scripts/terrain/port_promote.py: the interior promotion list PluginSpike reads (synthetic cell exports)."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
import port_promote  # noqa: E402

CONT_TABLE = {"default": {"name": None, "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
              "by_editor_id": {"WorkshopWorkbench": {"skip": "settlement workshop"},
                               "NukaColaMachine*": {"name": "Nuka-Cola Machine",
                                                    "items": [{"form": "Starfield.esm:00000F", "count": 3}]}}}
ITEM_TABLE = {"default": {"name": None, "value": 5, "weight": 0.5}, "by_editor_id": {"Stimpak*": {"name": "Stimpak",
                                                                                                  "value": 48, "weight": 0.1}}}


def ref(local, kind, edid, model="SetDressing\\x.nif", base=None, disabled=0):
    return {"formkey": f"{local}:Fallout4.esm", "type": kind, "base_editor_id": edid, "model": model,
            "base_formkey": base or f"0{local[1:]}B:Fallout4.esm", "disabled": disabled}


class PortPromoteTests(unittest.TestCase):
    def write_cells(self, d, *cells):
        paths = []
        for i, refs in enumerate(cells):
            p = os.path.join(d, f"cell{i}.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"cell": f"Cell{i}", "refs": refs}, f)
            paths.append(p)
        return paths

    def test_every_usable_class_is_listed_with_the_core_rules(self):
        refs = [ref("000101", "Container", "NukaColaMachine01", base="0A0001:Fallout4.esm"),
                ref("000102", "Container", "NukaColaMachine01", base="0A0001:Fallout4.esm"),
                ref("000103", "Container", "WorkshopWorkbench"),
                ref("000104", "MiscItem", "Stimpak", base="0A0002:Fallout4.esm"),
                ref("000105", "Weapon", "TireIron", base="0A0003:Fallout4.esm"),
                ref("000106", "Activator", "LightSwitch01", base="0A0004:Fallout4.esm"),
                ref("000107", "Terminal", "TerminalWall01", base="0A0005:Fallout4.esm"),
                ref("000108", "Container", "Desk01", disabled=0x800),
                ref("000109", "Activator", "TriggerMarker", model="Markers\\XMarker.nif"),
                ref("00010A", "Static", "Wall01"),
                ref("00010B", "Furniture", "Chair01")]
        refs_, placed = port_promote.cell_refs(self.write_cells(tempfile.mkdtemp(), refs[:6], refs[6:]))
        doc = port_promote.promote(refs_, placed, CONT_TABLE, ITEM_TABLE,
                                   names={"0A0004:Fallout4.esm": "Light Switch"}, starfield_esm="X:\\Starfield.esm")
        srcs = {k: [e["src"][:6] for e in doc[k]] for k in port_promote.KINDS}
        self.assertEqual(srcs, {"containers": ["000101", "000102"], "items": ["000104", "000105"],
                                "activators": ["000106"], "terminals": ["000107"]})
        c = doc["containers"][0]
        self.assertEqual((c["edid"], c["name"], c["items"]), ("FO4Port_cont_0a0001_fallout4", "Nuka-Cola Machine",
                                                              [{"form": "Starfield.esm:00000F", "count": 3}]))
        self.assertEqual(doc["containers"][1]["edid"], c["edid"])          # one base per FO4 base record
        self.assertEqual([(e["name"], e["value"], e["weight"]) for e in doc["items"]],
                         [("Stimpak", 48, 0.1), ("Tire Iron", 5, 0.5)])
        self.assertEqual(doc["activators"][0]["name"], "Light Switch")
        t = doc["terminals"][0]
        self.assertEqual((t["edid"], t["menu_edid"]), ("FO4Port_term_0a0005_fallout4", "FO4Port_tmlm_0a0005_fallout4"))
        self.assertEqual(doc["starfield_esm"], "X:\\Starfield.esm")

    def test_an_activator_without_an_fo4_name_has_none(self):
        refs, placed = port_promote.cell_refs(self.write_cells(tempfile.mkdtemp(), [
            ref("000201", "Activator", "PipeSteam01", base="0B0001:Fallout4.esm")]))
        doc = port_promote.promote(refs, placed, CONT_TABLE, ITEM_TABLE, names={"0B0001:Fallout4.esm": None})
        self.assertIsNone(doc["activators"][0]["name"])

    def test_terminals_need_the_starfield_master(self):
        refs, placed = port_promote.cell_refs(self.write_cells(tempfile.mkdtemp(), [
            ref("000301", "Terminal", "TerminalWall01")]))
        with self.assertRaisesRegex(ValueError, "starfield-data"):
            port_promote.promote(refs, placed, CONT_TABLE, ITEM_TABLE)

    def test_a_reference_in_two_exports_is_refused(self):
        r = ref("000401", "Container", "Desk01")
        with self.assertRaisesRegex(ValueError, "000401:Fallout4.esm is in both"):
            port_promote.cell_refs(self.write_cells(tempfile.mkdtemp(), [r], [r]))

    def test_the_cli_writes_promote_json(self):
        d = tempfile.mkdtemp()
        paths = self.write_cells(d, [ref("000501", "MiscItem", "Stimpak")])
        tables = []
        for name, t in (("c.json", CONT_TABLE), ("i.json", ITEM_TABLE)):
            tables.append(os.path.join(d, name))
            with open(tables[-1], "w", encoding="utf-8") as f:
                json.dump(t, f)
        out = os.path.join(d, "out", "promote.json")
        self.assertEqual(port_promote.main(["--out", out, "--containers-table", tables[0], "--items-table", tables[1],
                                            *paths]), 0)
        with open(out, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual([e["src"] for e in doc["items"]], ["000501:Fallout4.esm"])
        self.assertIsNone(doc["starfield_esm"])


if __name__ == "__main__":
    unittest.main()
