"""scripts/terrain/port_promote.py: the interior promotion list PluginSpike reads (synthetic cell exports)."""
import json
import math
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
import port_promote  # noqa: E402
from fo4sf import nif  # noqa: E402

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
                                "activators": ["000106"], "terminals": ["000107"], "furniture": []})
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


def marker_nif(*positions):
    """A NifFile with one BSFurnitureMarkerNode holding (x, y, z, heading) positions (FO4 layout)."""
    blk = struct.pack("<II", 0, len(positions)) + b"".join(struct.pack("<4f2H", *p, 3, 0x0F) for p in positions)
    return nif.NifFile(block_types=["BSFurnitureMarkerNode"], block_type_index=[0], blocks=[blk])


FURN = {"0C0001:Fallout4.esm": {"editor_id": "NpcChairStadiumRedSit03", "name": "Chair", "bench_type": "None",
                                "keywords": ["AnimFurnChairSitAnims", "FurnitureClassRelaxation"],
                                "entry_points": [{"type": "Sit", "points": "Front, Right, Left"}]},
        "0C0002:Fallout4.esm": {"editor_id": "NpcBedSleep", "name": "Bed", "bench_type": "None",
                                "keywords": ["AnimFurnBedSleep"], "entry_points": [{"type": "Lay", "points": "Left"}]},
        "0C0003:Fallout4.esm": {"editor_id": "WorkbenchChemistry", "name": "Chemistry Station", "bench_type": "Alchemy",
                                "keywords": ["AnimFurnChairSitAnims"], "entry_points": [{"type": "Sit", "points": "Front"}]}}


class FurnitureTests(unittest.TestCase):
    def test_the_nif_markers_are_read_in_fo4_units(self):
        marks = nif.furniture_markers(marker_nif((0.0, -14.0, 0.0, math.pi), (35.0, -14.0, 0.0, math.pi)))
        self.assertEqual([m["offset"] for m in marks], [(0.0, -14.0, 0.0), (35.0, -14.0, 0.0)])
        self.assertEqual((marks[0]["anim_type"], marks[0]["entry"]), (3, 0x0F))

    def test_a_marker_block_of_the_wrong_size_is_refused(self):
        n = marker_nif((0.0, 0.0, 0.0, 0.0))
        n.blocks[0] += b"\0"
        with self.assertRaisesRegex(nif.NifError, "with 1 positions"):
            nif.furniture_markers(n)

    def test_only_chairs_are_promoted_with_their_nif_markers_in_metres_and_degrees(self):
        refs = [ref("000601", "Furniture", "NpcChairStadiumRedSit03", base="0C0001:Fallout4.esm"),
                ref("000602", "Furniture", "NpcChairStadiumRedSit03", base="0C0001:Fallout4.esm"),
                ref("000603", "Furniture", "NpcBedSleep", base="0C0002:Fallout4.esm"),
                ref("000604", "Furniture", "WorkbenchChemistry", base="0C0003:Fallout4.esm")]
        reads = []
        chair = nif.serialize(marker_nif((0.0, -14.0, 0.0, math.pi)))

        def mesh(name):
            reads.append(name)
            return chair
        entries, rep = port_promote.furniture(refs, [r["formkey"] for r in refs], FURN, mesh)
        self.assertEqual([e["src"][:6] for e in entries], ["000601", "000602"])
        self.assertEqual(entries[0]["markers"], [{"offset": [0.0, -0.2, 0.0], "rotation_z": 180.0}])
        self.assertEqual((entries[0]["edid"], entries[0]["name"], entries[0]["template"]),
                         ("FO4Port_furn_0c0001_fallout4", "Chair", "0027D5"))
        self.assertEqual(reads, ["meshes\\SetDressing\\x.nif"])          # one read per FO4 base
        self.assertEqual(rep["left out: crafting bench"], 1)
        self.assertEqual(rep["left out: not a chair yet (animfurnbedsleep)"], 1)

    def test_a_chair_without_nif_markers_keeps_the_template_marker(self):
        refs = [ref("000701", "Furniture", "NpcChairStadiumRedSit03", base="0C0001:Fallout4.esm")]
        entries, rep = port_promote.furniture(refs, [refs[0]["formkey"]], FURN, mesh=lambda name: None)
        self.assertIsNone(entries[0]["markers"])
        self.assertEqual(rep["chairs with the template marker"], 1)

    def test_chairs_need_the_starfield_master(self):
        refs = [ref("000801", "Furniture", "NpcChairStadiumRedSit03", base="0C0001:Fallout4.esm")]
        with self.assertRaisesRegex(ValueError, "furniture need --starfield-data"):
            port_promote.promote(refs, [refs[0]["formkey"]], CONT_TABLE, ITEM_TABLE, furniture_bases=FURN)


if __name__ == "__main__":
    unittest.main()
