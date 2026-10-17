"""interior_backlog.py: the interior conversion backlog (exterior load doors -> interiors, measured and ranked), and
convert_batch.cell_candidates, the rule both use for the models a cell export converts. Synthetic fixtures only."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
import interior_backlog as ib  # noqa: E402

spec = importlib.util.spec_from_file_location("convert_batch_candidates", os.path.join(ROOT, "scripts", "convert_batch.py"))
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
WANTED = set(cb.DEFAULT_CELL_TYPES.split(","))

RR, SANC = "0211C0:Fallout4.esm", "072A48:Fallout4.esm"
CELL_A, CELL_B, WORLD = "00A001:Fallout4.esm", "00B001:Fallout4.esm", "000F94:Fallout4.esm"


def ref(fk, typ="Static", model="a\\b.nif", pos=(0.0, 0.0, 0.0), teleport=None, eid="X"):
    return {"formkey": fk, "type": typ, "base_editor_id": eid, "model": model, "pos": list(pos), "disabled": 0,
            "exterior_cell": [int(pos[0] // 4096), int(pos[1] // 4096)],
            "teleport_destination": None if teleport is None else {"door": teleport}}


def dep(src, door, cell, eid, world=None):
    return {"source": src, "door": door,
            "destination_cell": None if cell is None else {"formkey": cell, "editor_id": eid, "worldspace": world}}


def bands():
    """Two bands: landmarks 7,000 units (100 m) apart; two doors into A (one placed), one into B, one into a worldspace,
    one plain door."""
    b1 = {"refs": [ref(RR, pos=(0, 0, 0)), ref(SANC, pos=(7000, 0, 0)),
                   ref("000101:Fallout4.esm", "Door", pos=(70 * 50, 0, 0), teleport="00A101:Fallout4.esm"),
                   ref("000102:Fallout4.esm", "Door", pos=(-70 * 3000, 0, 0), teleport="00A102:Fallout4.esm"),
                   ref("000103:Fallout4.esm", "Door")],
          "deferred_refs": [{"formkey": "000900:Fallout4.esm", "type": "PlacedNpc"}],
          "teleport_dependencies": [dep("000101:Fallout4.esm", "00A101:Fallout4.esm", CELL_A, "CellA"),
                                    dep("000102:Fallout4.esm", "00A102:Fallout4.esm", CELL_A, "CellA")]}
    b2 = {"refs": [ref("000201:Fallout4.esm", "Door", pos=(70 * 1500, 0, 0), teleport="00B101:Fallout4.esm"),
                   ref("000202:Fallout4.esm", "Door", pos=(0, 70 * 10, 0), teleport="0F0001:Fallout4.esm")],
          "teleport_dependencies": [dep("000201:Fallout4.esm", "00B101:Fallout4.esm", CELL_B, "CellB"),
                                    dep("000202:Fallout4.esm", "0F0001:Fallout4.esm", "0F0000:Fallout4.esm", "DmndExt", WORLD)]}
    return [b1, b2]


def export(cell_fk, eid, refs, deferred=(), deps=()):
    return {"schema_version": 2, "cell": eid, "formkey": cell_fk, "refs": refs, "deferred_refs": list(deferred),
            "teleport_dependencies": list(deps)}


class CellCandidatesTests(unittest.TestCase):
    def test_types_markers_effects_once_sorted(self):
        cell = {"refs": [ref("1", "Static", "Arch\\Wall.nif"), ref("2", "StaticCollection", "Arch\\Wall.nif"),
                         ref("3", "Furniture", "\\Furn\\Chair.nif"), ref("4", "Static", "Markers\\XMarker.nif"),
                         ref("5", "Activator", "Effects\\FogVolume.nif"), ref("6", "Flora", "Plants\\Fern.nif"),
                         ref("7", "Light", "Lights\\Bulb.nif"), ref("8", "Static", ""), ref("9", "Door", "a\\SubEffects\\d.nif")]}
        names = cb.cell_candidates(cell, WANTED)
        # one entry per model; leading backslash dropped; Flora / Light not in the default types; markers and a top-level
        # effects folder out, "effects" deeper in the path stays; sorted case-insensitively
        self.assertEqual(names, ["meshes\\a\\SubEffects\\d.nif", "meshes\\Arch\\Wall.nif", "meshes\\Furn\\Chair.nif"])
        self.assertEqual(cb.cell_candidates(cell, {"Flora"}), ["meshes\\Plants\\Fern.nif"])

    def test_water_planes_out_like_the_exterior_path(self):
        """A placed Water\\*.nif is a BSWaterShaderProperty quad: converted as a static it is a flat grey sheet (the neutral
        fallback material) and its L_WATER body is a solid floor for the player (Vault 111 gear pit, owner playtest row 20).
        The exterior path already skips it (exterior.WATER_RE); the interior path must agree, and only for the top-level
        water folder: scum, debris and the water cooler are ordinary lighting-shader models and stay."""
        from fo4sf import exterior
        planes = ["Water\\Water1024.nif", "\\Water\\TroughBathWater.nif", "water/Water2048.nif"]
        keepers = ["Landscape\\Water\\MarshScumm01.nif", "SetDressing\\WaterCooler\\WaterCooler01.nif",
                   "Architecture\\Waterfront\\Dock01.nif", "SetDressing\\Plumbing\\Watercolor.nif"]
        cell = {"refs": [ref(str(i), "Activator", m) for i, m in enumerate(planes + keepers)]}
        self.assertEqual(cb.cell_candidates(cell, WANTED),
                         sorted(["meshes\\" + m.lstrip("\\") for m in keepers], key=str.lower))
        # the two paths give the same verdict for every model above (Activator is a type both convert)
        for m in planes:
            self.assertEqual(exterior.classify(ref("1", "Activator", m))[1], "water", m)
        for m in keepers:
            self.assertEqual(exterior.classify(ref("1", "Activator", m))[0], "convert", m)


class CensusTests(unittest.TestCase):
    def test_doors_kinds_placed_and_landmarks(self):
        doc = ib.census(bands(), placed={"000101:Fallout4.esm", "000201:Fallout4.esm"})
        t = doc["totals"]
        self.assertEqual((t["bands"], t["doors"], t["load_doors"]), (2, 5, 4))
        self.assertEqual((t["to_interior"], t["to_worldspace"]), (3, 1))
        self.assertEqual(doc["landmarks"], {"red_rocket": [0, 0, 0], "sanctuary": [7000, 0, 0]})
        by = {d["formkey"]: d for d in doc["doors"]}
        self.assertTrue(by["000101:Fallout4.esm"]["placed"])
        self.assertFalse(by["000102:Fallout4.esm"]["placed"])
        self.assertEqual(by["000202:Fallout4.esm"]["kind"], "worldspace")
        self.assertEqual(by["000101:Fallout4.esm"]["model_kind"], "model")
        cells = ib.destinations(doc["doors"])
        self.assertEqual(sorted(cells), [CELL_A, CELL_B])
        self.assertEqual(len(cells[CELL_A]["doors"]), 2)

    def test_refuses_duplicate_missing_and_unlinked(self):
        b = bands()
        b[1]["teleport_dependencies"].append(b[0]["teleport_dependencies"][0])
        with self.assertRaisesRegex(ValueError, "exported twice"):
            ib.census(b, set())
        b = bands()
        b[0]["refs"].pop(1)
        with self.assertRaisesRegex(ValueError, "sanctuary"):
            ib.census(b, set())
        b = bands()
        b[0]["teleport_dependencies"].pop(0)
        with self.assertRaisesRegex(ValueError, "no teleport_dependencies"):
            ib.census(b, set())
        b = bands()
        b[0]["deferred_refs"].append({"formkey": "000901:Fallout4.esm", "teleport_destination": {"door": "x"}})
        with self.assertRaisesRegex(ValueError, "deferred placement"):
            ib.census(b, set())

    def test_unresolved_destination_kept(self):
        b = bands()
        b[1]["teleport_dependencies"][0]["destination_cell"] = None
        doc = ib.census(b, set())
        self.assertEqual(doc["totals"]["to_unresolved"], 1)
        self.assertNotIn(CELL_B, ib.destinations(doc["doors"]))


class DoorKindTests(unittest.TestCase):
    def test_model_marker_none(self):
        self.assertEqual(ib.door_model_kind("Architecture\\Door01.nif"), "model")
        self.assertEqual(ib.door_model_kind("Markers\\AutoLoadMarker01.nif"), "marker")
        self.assertEqual(ib.door_model_kind(""), "none")


class MeasureTests(unittest.TestCase):
    def test_measures(self):
        exp = export(CELL_A, "CellA",
                     [ref("00A101:Fallout4.esm", "Door", "Doors\\Load.nif"), ref("1", "Static", "Arch\\Done.nif"),
                      ref("2", "Static", "Arch\\Done.nif"), ref("3", "Static", "Arch\\Failed.nif"),
                      ref("4", "Static", "Arch\\New.nif"), ref("5", "Light", "Lights\\L.nif"), ref("6", "Light", ""),
                      ref("7", "Static", "Markers\\XMarker.nif")],
                     deferred=[{"type": "PlacedNpc"}, {"type": "PlacedHazard"}],
                     deps=[dep("00A101:Fallout4.esm", "000101:Fallout4.esm", "00C000:Fallout4.esm", "Commonwealth_x", "W"),
                           dep("00A110:Fallout4.esm", "00B110:Fallout4.esm", CELL_B, "CellB"),
                           dep("00A111:Fallout4.esm", "00B111:Fallout4.esm", CELL_B, "CellB"),
                           dep("00A112:Fallout4.esm", "00A113:Fallout4.esm", CELL_A, "CellA"),
                           dep("00A114:Fallout4.esm", "x", None, None)])
        converted = {"meshes\\arch\\done.nif", "meshes\\doors\\load.nif"}
        failed = {"meshes\\arch\\failed.nif", "meshes\\arch\\done.nif"}
        m = ib.cell_measures(exp, cb.cell_candidates(exp, WANTED), converted, failed, {"meshes\\arch\\new.nif"})
        self.assertEqual((m["refs"], m["deferred"], m["actors"], m["lights"]), (8, 2, 1, 2))
        self.assertEqual(m["distinct_models"], 6)                     # every non-empty model, markers and lights included
        self.assertEqual(m["convertible_models"], 4)                  # load door, done, failed, new
        self.assertEqual((m["converted_in_integ"], m["failed_in_integ"], m["new_models"]), (2, 1, 1))
        self.assertEqual(m["converted_fraction"], 0.5)
        self.assertEqual(m["in_core_build"], 1)
        self.assertEqual(m["_new"], ["meshes\\arch\\new.nif"])
        self.assertEqual(m["leads_to_interiors"], {"(unresolved)": 1, "CellB": 2})   # exterior and self links left out
        self.assertEqual(m["teleports_inside"], 5)
        self.assertEqual(ib.effort(m)["load_doors_in_cell"], 5)                    # every load door, exits included

    def test_leading_separator_is_the_same_model(self):
        # convert_batch.cell_candidates and PluginSpike drop a leading separator; the counts and placeable() must too
        exp = export(CELL_A, "CellA", [ref("1", "Furniture", "\\Furn\\Chair.nif"), ref("2", "Furniture", "Furn\\Chair.nif"),
                                       ref("3", "Static", "/Arch/Wall.nif")])
        m = ib.cell_measures(exp, cb.cell_candidates(exp, WANTED), set(), set())
        self.assertEqual((m["distinct_models"], m["convertible_models"]), (2, 2))
        man = {"items": [{"source": "meshes\\Furn\\Chair.nif"}, {"source": "meshes\\Arch\\Wall.nif"}]}
        self.assertEqual(ib.placeable(exp, man)["placed"], 3)

    def test_empty_cell_counts_as_converted(self):
        m = ib.cell_measures(export(CELL_A, "CellA", []), [], set(), set())
        self.assertEqual((m["converted_fraction"], m["new_models"]), (1.0, 0))

    def test_effort_classes(self):
        base = {"actors": 0, "teleports_inside": 0}
        self.assertEqual(ib.effort({**base, "refs": 300, "new_models": 50})["class"], "S")
        self.assertEqual(ib.effort({**base, "refs": 301, "new_models": 0})["class"], "M")
        self.assertEqual(ib.effort({**base, "refs": 100, "new_models": 201})["class"], "L")
        self.assertEqual(ib.effort({**base, "refs": 5001, "new_models": 0})["class"], "XL")
        e = ib.effort({**base, "refs": 10, "new_models": 40}, seconds_per_model=0.5)
        self.assertEqual(e["convert_s_est"], 20.0)
        self.assertNotIn("convert_s_est", ib.effort({**base, "refs": 10, "new_models": 40}))


class RankTests(unittest.TestCase):
    def cell(self, eid, doors, near, frac, new):
        return {"editor_id": eid, "doors": doors, "nearest_m": near, "converted_fraction": frac, "_new": new,
                "refs": len(new) * 10, "new_models": len(new), "enterable": True}

    def test_doors_then_ring_then_fraction_then_distance(self):
        cells = [self.cell("far2", 2, 5200.0, 0.9, ["m1"]),
                 self.cell("near1_low", 1, 100.0, 0.1, ["m1", "m2"]),
                 self.cell("near1_high", 1, 900.0, 0.8, ["m2", "m3"]),     # same ring as near1_low: fraction wins
                 self.cell("ring2", 1, 1100.0, 1.0, []),
                 self.cell("near2", 2, 50.0, 0.0, ["m4"])]
        r = ib.rank(cells)
        self.assertEqual([c["editor_id"] for c in r], ["near2", "far2", "near1_high", "near1_low", "ring2"])
        self.assertEqual([c["rank"] for c in r], [1, 2, 3, 4, 5])
        self.assertEqual([c["adds_models"] for c in r], [1, 1, 2, 0, 0])     # m4; m1; m2 m3; (m1 m2 seen); none
        self.assertEqual(r[-1]["cumulative_new_models"], 4)

    def test_pick_smallest_of_top(self):
        r = ib.rank([self.cell(f"c{i}", 1, 10.0 * i, 0.5, [f"m{j}" for j in range(n)])
                     for i, n in enumerate([5, 1, 3, 1, 9])])
        self.assertEqual([c["editor_id"] for c in ib.pick_dryrun(r, top=4, pick=2)], ["c1", "c3"])   # refs 10, 10: rank
        self.assertEqual([c["editor_id"] for c in ib.pick_dryrun(r, top=1, pick=3)], ["c0"])
        r[1]["enterable"] = False                                                # no arrival: never picked
        self.assertEqual([c["editor_id"] for c in ib.pick_dryrun(r, top=4, pick=2)], ["c3", "c2"])


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.doors = ib.census(bands(), placed={"000101:Fallout4.esm"})
        self.exports = {
            "CellA": export(CELL_A, "CellA", [ref("00A101:Fallout4.esm", "Door", "D\\A.nif"),
                                              ref("00A102:Fallout4.esm", "Door", "D\\A.nif"), ref("a1", "Static", "S\\Old.nif")]),
            "CellB": export(CELL_B, "CellB", [ref("00B101:Fallout4.esm", "Door", "D\\B.nif"), ref("b1", "Static", "S\\New.nif")],
                            deps=[dep("00B102:Fallout4.esm", "x", CELL_A, "CellA")])}

    def plan(self, done=(), exports=None, dry=()):
        return ib.plan(self.doors, exports or self.exports, lambda e: cb.cell_candidates(e, WANTED),
                       {"meshes\\s\\old.nif"}, set(), set(done), dryruns=dry)

    def test_ranked_backlog_and_converted(self):
        doc = self.plan(done={"CellB"}, dry=[{"seconds": 10.0, "attempted": 4}])
        self.assertEqual([c["editor_id"] for c in doc["backlog"]], ["CellA"])
        self.assertEqual([c["editor_id"] for c in doc["converted"]], ["CellB"])
        a = doc["backlog"][0]
        self.assertEqual((a["doors"], a["doors_placed_by_core"], a["nearest_landmark"], a["nearest_door"]),
                         (2, 1, "red_rocket", "000101:Fallout4.esm"))
        self.assertTrue(a["enterable"])
        self.assertEqual((a["doors_marker"], a["doors_without_model"], a["doors_disabled"]), (0, 0, 0))
        self.assertEqual(a["nearest_m"], 50.0)
        self.assertEqual(a["distance_m"], {"red_rocket": 50.0, "sanctuary": 50.0})
        self.assertEqual((a["convertible_models"], a["converted_in_integ"], a["new_models"]), (2, 1, 1))
        self.assertEqual(a["effort"]["convert_s_est"], 2.5)
        self.assertNotIn("_new", a)
        t = doc["totals"]
        self.assertEqual((t["interiors"], t["interiors_converted"], t["doors_into_converted"], t["doors_into_backlog"]),
                         (2, 1, 1, 2))
        self.assertEqual(list(doc["worldspace_destinations"]), [WORLD])
        self.assertEqual(doc["worldspace_destinations"][WORLD][0]["formkey"], "000202:Fallout4.esm")
        self.assertEqual(doc["seconds_per_model"], 2.5)
        self.assertEqual((t["backlog_new_models"], t["backlog_new_models_per_cell_sum"], t["backlog_new_models_in_core_build"]),
                         (1, 1, 0))
        self.assertEqual(doc["dryrun_pick"], ["CellA"])
        self.assertIn("| 1 | CellA | 2 (1) | 50 |", ib.md_table(doc))
        b = doc["converted"][0]
        self.assertEqual(b["leads_to_interiors"], {"CellA": 1})

    def test_shared_models_count_once(self):
        self.exports["CellB"]["refs"].append(ref("b2", "Static", "d\\a.nif"))       # CellA's new door model, other case
        doc = self.plan(dry=[{"seconds": 1.0, "attempted": 1}])
        t = doc["totals"]
        self.assertEqual((t["backlog_new_models"], t["backlog_new_models_per_cell_sum"]), (3, 4))
        self.assertEqual(t["backlog_convert_s_est"], 3.0)
        self.assertEqual([c["adds_models"] for c in doc["backlog"]], [1, 2])         # CellA first (2 doors)

    def test_enterable_needs_a_placed_or_marker_door(self):
        b = bands()
        for r in b[0]["refs"]:
            if r["formkey"] in ("000101:Fallout4.esm", "000102:Fallout4.esm"):
                r["model"] = ""
        self.doors = ib.census(b, placed={"000201:Fallout4.esm"})          # CellB's door placed, CellA's have no model
        doc = self.plan()
        a = next(c for c in doc["backlog"] if c["editor_id"] == "CellA")
        self.assertFalse(a["enterable"])
        self.assertEqual(a["doors_without_model"], 2)
        self.assertEqual(doc["totals"]["backlog_not_enterable"], 1)
        self.assertEqual(doc["dryrun_pick"], ["CellB"])
        self.assertIn("CellA (no arrival)", ib.md_table(doc))
        b[0]["refs"][2]["model"] = "Markers\\AutoLoadMarker01.nif"
        self.doors = ib.census(b, placed=set())
        self.assertTrue(next(c for c in self.plan()["backlog"] if c["editor_id"] == "CellA")["enterable"])

    def test_enterable_needs_an_enabled_door_and_a_known_marker(self):
        b = bands()
        b[0]["refs"][2]["model"] = "Markers\\Special\\InvisibleDoor01.nif"     # a marker door with no recorded path
        b[0]["refs"][3]["model"] = "Markers\\AutoLoadMarker01.nif"
        b[0]["refs"][3]["disabled"] = 2048                                     # the AutoloadDoor is initially disabled
        b[1]["refs"][0]["disabled"] = 2048                                     # CellB's only door: placed, but disabled
        self.doors = ib.census(b, placed={"000201:Fallout4.esm"})
        doc = self.plan()
        by = {c["editor_id"]: c for c in doc["backlog"]}
        self.assertEqual(by["CellA"]["doors_marker"], 2)
        self.assertFalse(by["CellA"]["enterable"])
        self.assertFalse(by["CellB"]["enterable"])
        self.assertEqual(doc["totals"]["backlog_not_enterable"], 2)
        b[0]["refs"][3]["disabled"] = 0
        self.doors = ib.census(b, placed=set())
        self.assertTrue({c["editor_id"]: c for c in self.plan()["backlog"]}["CellA"]["enterable"])

    def test_entrances_count_distinct_enabled_positions(self):
        b = bands()
        b[0]["refs"][3]["pos"] = list(b[0]["refs"][2]["pos"])                 # CellA's two doors stacked on one spot
        self.doors = ib.census(b, placed=set())
        a = {c["editor_id"]: c for c in self.plan()["backlog"]}["CellA"]
        self.assertEqual((a["doors"], a["entrances"]), (2, 1))
        b[0]["refs"][2]["disabled"] = 2048
        b[0]["refs"][3]["disabled"] = 2048
        self.doors = ib.census(b, placed=set())
        self.assertEqual({c["editor_id"]: c for c in self.plan()["backlog"]}["CellA"]["entrances"], 0)

    def test_second_hop_interiors_measured_and_counted(self):
        # CellA (backlog) leads on into CellC, CellC into CellD (hop 3); CellB (converted) into CellE (no export) and
        # back into CellA; CellD into CellC again (counted as a door, not a new cell)
        cell_c, cell_d, cell_e = "00C001:Fallout4.esm", "00D001:Fallout4.esm", "00E001:Fallout4.esm"
        self.exports["CellA"]["teleport_dependencies"] = [dep("00A120:Fallout4.esm", "00C101:Fallout4.esm", cell_c, "CellC")]
        self.exports["CellB"]["teleport_dependencies"] += [dep("00B120:Fallout4.esm", "00E101:Fallout4.esm", cell_e, "CellE")]
        self.exports["CellC"] = export(cell_c, "CellC", [ref("00C101:Fallout4.esm", "Door", "D\\C.nif"),
                                                         ref("c1", "Static", "S\\New.nif"), ref("c2", "Static", "S\\Old.nif")],
                                       deps=[dep("00C120:Fallout4.esm", "00D101:Fallout4.esm", cell_d, "CellD")])
        self.exports["CellD"] = export(cell_d, "CellD", [ref("00D101:Fallout4.esm", "Door", "D\\D.nif")],
                                       deps=[dep("00D120:Fallout4.esm", "00C101:Fallout4.esm", cell_c, "CellC")])
        doc = self.plan(done={"CellB"}, dry=[{"seconds": 1.0, "attempted": 1}])
        self.assertEqual([c["editor_id"] for c in doc["backlog"]], ["CellA"])        # still ranked on exterior doors only
        hop = {c["editor_id"]: c for c in doc["second_hop"]}
        self.assertEqual([c["editor_id"] for c in doc["second_hop"]], ["CellE", "CellC", "CellD"])   # after_rank 0, 1, 1
        self.assertEqual((hop["CellE"]["status"], hop["CellE"]["after_rank"], hop["CellE"]["reached_from"]),
                         ("not_exported", 0, {"CellB": 1}))
        self.assertEqual((hop["CellC"]["status"], hop["CellC"]["hop"], hop["CellC"]["after_rank"]), ("backlog", 2, 1))
        self.assertEqual(hop["CellC"]["reached_from"], {"CellA": 1, "CellD": 1})
        self.assertEqual((hop["CellD"]["hop"], hop["CellD"]["after_rank"]), (3, 1))
        # CellA brings D\A.nif; CellC brings D\C.nif and S\New.nif (S\Old.nif converted); CellD brings D\D.nif
        self.assertEqual((hop["CellC"]["new_models"], hop["CellC"]["adds_models"], hop["CellC"]["cumulative_new_models"]),
                         (2, 2, 3))
        self.assertEqual((hop["CellD"]["adds_models"], hop["CellD"]["cumulative_new_models"]), (1, 4))
        self.assertEqual(hop["CellC"]["effort"]["convert_s_est"], 2.0)
        self.assertNotIn("_new", hop["CellC"])
        t = doc["totals"]
        self.assertEqual((t["second_hop_interiors"], t["second_hop_backlog"], t["second_hop_not_exported"],
                          t["second_hop_converted"], t["second_hop_backlog_through_converted"]), (3, 2, 1, 0, 0))
        self.assertEqual((t["doors_into_second_hop_backlog"], t["second_hop_backlog_refs"]), (3, 4))
        self.assertEqual((t["backlog_new_models"], t["second_hop_adds_models"], t["backlog_and_second_hop_new_models"]),
                         (1, 3, 4))
        self.assertEqual(t["backlog_and_second_hop_convert_s_est"], 4.0)
        md = ib.md_table(doc)
        self.assertIn("| 1 | CellC | 2 | CellA, CellD | 3 |", md)
        self.assertIn("| 0 | CellE | 2 | CellB | not exported |", md)
        self.exports["CellD"]["formkey"] = cell_e
        with self.assertRaisesRegex(ValueError, "export CellD is cell"):
            self.plan(done={"CellB"})
        self.exports["CellD"]["formkey"] = cell_d
        self.exports["CellD"]["refs"] = []
        with self.assertRaisesRegex(ValueError, "CellD: destination doors not in its export"):
            self.plan(done={"CellB"})

    def test_archive_check(self):
        doc = ib.plan(self.doors, self.exports, lambda e: cb.cell_candidates(e, WANTED), {"meshes\\s\\old.nif"}, set(),
                      set(), archive={"meshes\\d\\a.nif", "meshes\\s\\old.nif"})
        by = {c["editor_id"]: c for c in doc["backlog"]}
        self.assertEqual((by["CellA"]["missing_from_archives"], by["CellB"]["missing_from_archives"]), (0, 2))
        t = doc["totals"]
        self.assertEqual((t["backlog_cells_with_models_missing_from_archives"], t["backlog_new_models_missing_from_archives"]),
                         (1, 2))

    def test_refuses_missing_wrong_or_incomplete_exports(self):
        with self.assertRaisesRegex(ValueError, "no export"):
            self.plan(exports={"CellA": self.exports["CellA"]})
        wrong = dict(self.exports, CellB=dict(self.exports["CellB"], formkey="00FFFF:Fallout4.esm"))
        with self.assertRaisesRegex(ValueError, "is cell"):
            self.plan(exports=wrong)
        short = dict(self.exports, CellA=dict(self.exports["CellA"], refs=self.exports["CellA"]["refs"][1:]))
        with self.assertRaisesRegex(ValueError, "destination doors not in its export"):
            self.plan(exports=short)


class StagingTests(unittest.TestCase):
    def test_dryrun_result_placeable_and_converted_cells(self):
        with tempfile.TemporaryDirectory() as d:
            st = os.path.join(d, "CellA")
            os.makedirs(st)
            man = {"items": [{"source": "meshes\\S\\Old.nif", "load_door": {}}, {"source": "meshes\\D\\A.nif", "door": {}}],
                   "failures": [{"nif": "meshes\\S\\Bad.nif", "reason": "ValueError: no static BSTriShape geometry"}],
                   "stats": {"reused": 0}, "seconds": 6.0}
            with open(os.path.join(st, "manifest.json"), "w") as f:
                json.dump(man, f)
            r = ib.dryrun_result(st)
            self.assertEqual((r["attempted"], r["converted"], r["failed"], r["seconds_per_model"]), (3, 2, 1, 2.0))
            self.assertEqual(r["reasons"], {"ValueError": 1})
            self.assertEqual((r["load_doors"], r["doors"]), (1, 1))
            exp = export(CELL_A, "CellA", [ref("1", "Static", "s\\old.nif"), ref("2", "Light", ""), ref("3", "Static", "S\\Bad.nif"),
                                           dict(ref("4", "Static", "m\\coc.nif"), base_editor_id="COCMarkerHeading")])
            self.assertEqual(ib.placeable(exp, man), {"placed": 1, "skipped": 1, "light_refs": 1, "coc_markers": 1})
            for name, body in (("CellA.json", {"cell": "CellA", "refs": []}), ("merged.json", {"cell": "merged", "refs": []}),
                               ("routes_CellA.json", {"cell": "routes_CellA", "refs": []}), ("Other.json", {"cell": "X", "refs": []}),
                               ("bad.json", None)):
                with open(os.path.join(d, name), "w") as f:
                    f.write("{" if body is None else json.dumps(body))
            self.assertEqual(ib.converted_cells(d), {"CellA"})


class CliTests(unittest.TestCase):
    def test_doors_then_plan(self):
        with tempfile.TemporaryDirectory() as d:
            work, build, exps, integ = (os.path.join(d, n) for n in ("work", "build", "exports", "integ"))
            for p in (os.path.join(work, "export"), build, exps, integ):
                os.makedirs(p)
            for i, b in enumerate(bands()):
                with open(os.path.join(work, "export", f"band_{i}.json"), "w") as f:
                    json.dump(b, f)
            with open(os.path.join(build, "objects.json"), "w") as f:
                json.dump({"refs": [{"src": "000201:Fallout4.esm"}], "bases": [{"source": "meshes\\D\\B.nif"}]}, f)
            out, cells_txt = os.path.join(d, "doors.json"), os.path.join(d, "cells.txt")
            self.assertEqual(ib.main(["doors", "--work", work, "--build", build, "--out", out, "--cells-txt", cells_txt]), 0)
            with open(cells_txt, "rb") as f:
                self.assertEqual(f.read(), b"CellA\nCellB\n")
            pt = PlanTests()
            pt.setUp()
            # CellA leads on into CellC (exported), CellC into CellZ (not exported yet)
            pt.exports["CellA"]["teleport_dependencies"] = [dep("00A120:Fallout4.esm", "00C101:Fallout4.esm",
                                                                "00C001:Fallout4.esm", "CellC")]
            pt.exports["CellC"] = export("00C001:Fallout4.esm", "CellC", [ref("00C101:Fallout4.esm", "Door", "D\\C.nif")],
                                         deps=[dep("00C120:Fallout4.esm", "00F101:Fallout4.esm", "00F001:Fallout4.esm", "CellZ")])
            for eid, e in pt.exports.items():
                with open(os.path.join(exps, eid + ".json"), "w") as f:
                    json.dump(e, f)
            with open(os.path.join(integ, "manifest.json"), "w") as f:
                json.dump({"items": [{"source": "meshes\\S\\Old.nif"}], "failures": []}, f)
            with open(os.path.join(integ, "CellB.json"), "w") as f:
                json.dump(pt.exports["CellB"], f)
            st = os.path.join(d, "dryrun", "CellA")                   # a staging named after its cell: placed / skipped
            os.makedirs(st)
            with open(os.path.join(st, "manifest.json"), "w") as f:
                json.dump({"items": [{"source": "meshes\\D\\A.nif"}], "failures": [], "stats": {}, "seconds": 3.0}, f)
            js, md, nxt = (os.path.join(d, n) for n in ("backlog.json", "table.md", "next.txt"))
            self.assertEqual(ib.main(["plan", "--doors", out, "--exports", exps, "--manifest", os.path.join(integ, "manifest.json"),
                                      "--converted", integ, "--core-build", build, "--dryrun", st, "--json", js,
                                      "--md-table", md, "--next-cells-txt", nxt]), 0)
            doc = ib.load(js)
            self.assertEqual([c["editor_id"] for c in doc["backlog"]], ["CellA"])
            self.assertEqual(doc["converted"][0]["in_core_build"], 1)
            self.assertEqual(doc["converted"][0]["doors_placed_by_core"], 1)
            self.assertEqual(len(doc["inputs"]["manifest_sha256"]), 64)
            self.assertTrue(os.path.getsize(md) > 0)
            self.assertEqual([(c["editor_id"], c["status"]) for c in doc["second_hop"]],
                             [("CellC", "backlog"), ("CellZ", "not_exported")])
            with open(nxt, "rb") as f:
                self.assertEqual(f.read(), b"CellZ\n")
            dr = doc["dryrun"][0]
            self.assertEqual((dr["cell"], dr["placed"], dr["skipped"], dr["seconds_per_model"]), ("CellA", 2, 1, 3.0))
            self.assertEqual(doc["seconds_per_model"], 3.0)


if __name__ == "__main__":
    unittest.main()
