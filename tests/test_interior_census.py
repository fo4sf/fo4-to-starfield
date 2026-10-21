"""scripts/terrain/interior_census.py, interior_batches.py and interior_batch.py on synthetic plugins and plans: every
interior cell and how it is reached, the batch order and limits, the port id comparison, the door selection, the prune
rule. No game data."""
import json
import argparse
import os
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import interior_batch as ib  # noqa: E402
import interior_batches as ibs  # noqa: E402
import interior_census as ic  # noqa: E402
import vmad_patch as vp  # noqa: E402

G = vp.Group


def rec(sig, fid, fields, flags=0):
    return vp.record_bytes(sig, fid, flags, fields)


def ref(fid, base, xtel=None, sig=b"REFR"):
    fields = [(b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))]
    if xtel:
        fields.append((b"XTEL", struct.pack("<I", xtel) + bytes(28)))
    return rec(sig, fid, fields)


def cell(fid, edid, refs, interior=True, persistent=(), fields=()):
    c = rec(b"CELL", fid, [(b"EDID", edid.encode() + b"\0"), (b"DATA", struct.pack("<H", 1 if interior else 0))] + list(fields))
    kids = []
    if persistent:
        kids.append(G(struct.pack("<I", fid), vp.GROUP_PERSISTENT, bytes(8), list(persistent)))
    kids.append(G(struct.pack("<I", fid), vp.GROUP_TEMPORARY, bytes(8), list(refs)))
    return [c, G(struct.pack("<I", fid), vp.GROUP_CELL_CHILDREN, bytes(8), kids)]


def fo4_plugin():
    """Fallout4.esm in miniature: a DOOR and a LIGH base; interiors Lobby (door from the Commonwealth, door on to
    Vault), Vault (reached only through Lobby), Store (a door from DiamondCity) and zzTestCell (no door leads in);
    the Commonwealth's exterior cell holds the door into Lobby, DiamondCity's the door into Store. Lobby and Vault
    share the location VaultLocation (XLCN); Lobby sits in the encounter zone VaultZone (XEZN: levels 3-10, flags
    NeverResets|DisableCombatBoundary, location VaultLocation); Store names a zone the plugin does not hold."""
    DOOR, LIGH, LCTN, ECZN = 0x100, 0x101, 0x400, 0x410
    # ECZN DATA: owner u32, location u32, rank u8, min level u8, flags u8, max level u8 (Mutagen's byte widths)
    zone = rec(b"ECZN", ECZN, [(b"EDID", b"VaultZone\0"), (b"DATA", struct.pack("<IIbbBb", 0, LCTN, 0, 3, 5, 10))])
    bases = [G(b"DOOR", 0, bytes(8), [rec(b"DOOR", DOOR, [(b"EDID", b"Door\0")])]),
             G(b"LIGH", 0, bytes(8), [rec(b"LIGH", LIGH, [(b"EDID", b"Light\0")])]),
             G(b"ECZN", 0, bytes(8), [zone]),                       # before LCTN on purpose: resolved after the walk
             G(b"LCTN", 0, bytes(8), [rec(b"LCTN", LCTN, [(b"EDID", b"VaultLocation\0"), (b"FULL", b"Vault\0")])])]
    lobby = cell(0x200, "Lobby", [ref(0x301, DOOR, xtel=0x900), ref(0x302, DOOR, xtel=0x311), ref(0x303, LIGH),
                                   ref(0x304, LIGH), ref(0x305, 0x102, sig=b"ACHR")],
                 fields=[(b"XLCN", struct.pack("<I", LCTN)), (b"XEZN", struct.pack("<I", ECZN))])
    vault = cell(0x210, "Vault", [ref(0x311, DOOR, xtel=0x302), ref(0x312, 0x103)], fields=[(b"XLCN", struct.pack("<I", LCTN))])
    store = cell(0x220, "Store", [ref(0x321, DOOR, xtel=0x910)], fields=[(b"XEZN", struct.pack("<I", 0x411))])
    test = cell(0x230, "zzTestCell", [ref(0x331, 0x103)])
    sub = G(struct.pack("<I", 0), vp.GROUP_INT_SUB if hasattr(vp, "GROUP_INT_SUB") else 3, bytes(8), lobby + vault + store + test)
    cells = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [sub])])
    ext_cw = cell(0x500, "", [ref(0x900, DOOR, xtel=0x301)], interior=False)
    ext_dc = cell(0x510, "", [ref(0x910, DOOR, xtel=0x321)], interior=False)

    def world(fid, edid, cells_):
        w = rec(b"WRLD", fid, [(b"EDID", edid.encode() + b"\0")])
        blk = G(struct.pack("<I", 0), 4, bytes(8), [G(struct.pack("<I", 0), 5, bytes(8), cells_)])
        return [w, G(struct.pack("<I", fid), 1, bytes(8), [blk])]
    worlds = G(b"WRLD", 0, bytes(8), world(0x3C, "Commonwealth", ext_cw) + world(0xF94, "DiamondCity", ext_dc))
    tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 20, 0x1000))], flags=1)
    return tes4.serialize() + b"".join(g.serialize() for g in bases) + cells.serialize() + worlds.serialize()


def fk(local):
    return "%06X:Fallout4.esm" % local


class CensusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.esm = os.path.join(self.tmp.name, "Fallout4.esm")
        with open(self.esm, "wb") as f:
            f.write(fo4_plugin())

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_interior_and_its_reach(self):
        backlog = {"backlog": [{"formkey": fk(0x200), "rank": 1}], "second_hop": [{"formkey": fk(0x210), "after_rank": 1}]}
        r = ic.census([self.esm], port_cells=["Store"], backlog=backlog)
        by = {c["editor_id"]: c for c in r["cells"]}
        self.assertEqual(sorted(by), ["Lobby", "Store", "Vault", "zzTestCell"])
        self.assertEqual((by["Lobby"]["reach"], by["Lobby"]["hop"], by["Lobby"]["entered_from"]), ("worldspace", 1, ["Commonwealth"]))
        self.assertEqual((by["Vault"]["reach"], by["Vault"]["hop"], by["Vault"]["entered_from"]), ("behind_interior", 2, ["Lobby"]))
        self.assertEqual(by["Store"]["entered_from"], ["DiamondCity"])
        self.assertEqual((by["zzTestCell"]["reach"], by["zzTestCell"]["test_name"]), ("no_load_door", True))
        self.assertEqual((by["Lobby"]["status"], by["Lobby"]["backlog_rank"]), ("backlog", 1))
        self.assertEqual(by["Vault"]["status"], "second_hop")
        self.assertEqual(by["Store"]["status"], "in_port")
        self.assertEqual(by["zzTestCell"]["status"], "new")
        self.assertEqual((by["Lobby"]["refs"], by["Lobby"]["lights"], by["Lobby"]["placed"]), (5, 2, {"ACHR": 1, "REFR": 4}))
        self.assertEqual(sorted(d["to"] for d in by["Lobby"]["load_doors_out"]), ["Vault", "world:Commonwealth"])
        self.assertEqual(by["Lobby"]["formkey"], fk(0x200))
        self.assertEqual(r["totals"]["interiors"], 4)
        with self.assertRaisesRegex(ValueError, "port cells not among"):
            ic.census([self.esm], port_cells=["Nowhere"])

    def test_location_and_encounter_zone_per_cell(self):
        r = ic.census([self.esm])
        by = {c["editor_id"]: c for c in r["cells"]}
        # the FO4 location (XLCN) resolves to its editor id for both cells that share it, None elsewhere
        self.assertEqual((by["Lobby"]["location"], by["Vault"]["location"]), ("VaultLocation", "VaultLocation"))
        self.assertEqual((by["Store"]["location"], by["zzTestCell"]["location"]), (None, None))
        # the encounter zone (XEZN -> ECZN DATA): level band, flags, rank and the location the zone names
        self.assertEqual(by["Lobby"]["encounter_zone"], {"formkey": fk(0x410), "editor_id": "VaultZone", "min_level": 3,
                                                        "max_level": 10, "flags": 5, "rank": 0, "location": "VaultLocation"})
        self.assertIsNone(by["Vault"]["encounter_zone"])
        self.assertIsNone(by["zzTestCell"]["encounter_zone"])
        # a zone the plugins do not hold keeps its key, with nothing to fold
        self.assertEqual(by["Store"]["encounter_zone"]["formkey"], fk(0x411))
        self.assertIsNone(by["Store"]["encounter_zone"]["min_level"])
        self.assertEqual((r["totals"]["with_location"], r["totals"]["with_encounter_zone"]), (2, 2))
        # the raw DATA reader: the 12-byte layout with unsigned levels (255 stays 255, as Fo4Export exports it), and a
        # short DATA is no zone
        self.assertEqual(ic.zone_data(struct.pack("<IIBBBB", 0x804, 0x801, 2, 5, 5, 255)),
                         {"owner": 0x804, "location": 0x801, "rank": 2, "min_level": 5, "flags": 5, "max_level": 255})
        self.assertIsNone(ic.zone_data(bytes(8)))

    def test_a_dlc_override_of_a_reference_counts_once(self):
        # A DLC re-saves Lobby's light 0x303 as a door (base 0x100) and its load door 0x301 with a new destination.
        tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 2, 0x800)), (b"MAST", b"Fallout4.esm\0"),
                                (b"DATA", bytes(8))], flags=1)
        lobby = cell(0x200, "Lobby", [ref(0x303, 0x100), ref(0x301, 0x100, xtel=0x311)])
        sub = G(struct.pack("<I", 0), 3, bytes(8), lobby)
        cells = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [sub])])
        dlc = os.path.join(self.tmp.name, "DLCRobot.esm")
        with open(dlc, "wb") as f:
            f.write(tes4.serialize() + cells.serialize())
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc])["cells"]}
        self.assertEqual((by["Lobby"]["refs"], by["Lobby"]["lights"], by["Lobby"]["placed"]), (5, 1, {"ACHR": 1, "REFR": 4}))
        self.assertEqual(sorted(d["to"] for d in by["Lobby"]["load_doors_out"]), ["Vault", "Vault"])

    def test_a_deleted_override_removes_the_reference_and_its_door(self):
        # The DLC re-saves Lobby's light 0x303 and its load door 0x302 (to Vault) with the Deleted flag; the deleted door
        # keeps an XTEL, which must not keep the edge alive. A third plugin re-adds the light: it counts again.
        def plugin(name, refs, nmast=1):
            masts = [(b"MAST", b"Fallout4.esm\0"), (b"DATA", bytes(8))] + ([(b"MAST", b"DLCRobot.esm\0"), (b"DATA", bytes(8))] if nmast > 1 else [])
            tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 2, 0x800))] + masts, flags=1)
            lobby = cell(0x200, "Lobby", refs)
            sub = G(struct.pack("<I", 0), 3, bytes(8), lobby)
            cells = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [sub])])
            path = os.path.join(self.tmp.name, name)
            with open(path, "wb") as f:
                f.write(tes4.serialize() + cells.serialize())
            return path
        dlc = plugin("DLCRobot.esm", [rec(b"REFR", 0x303, [(b"NAME", struct.pack("<I", 0x101))], flags=ic.DELETED),
                                      rec(b"REFR", 0x302, [(b"NAME", struct.pack("<I", 0x100)), (b"XTEL", struct.pack("<I", 0x311) + bytes(28))], flags=ic.DELETED)])
        r = ic.census([self.esm, dlc])
        by = {c["editor_id"]: c for c in r["cells"]}
        self.assertEqual((by["Lobby"]["refs"], by["Lobby"]["lights"], by["Lobby"]["placed"]), (3, 1, {"ACHR": 1, "REFR": 2}))
        self.assertEqual(sorted(d["to"] for d in by["Lobby"]["load_doors_out"]), ["world:Commonwealth"])
        self.assertEqual(by["Vault"]["reach"], "no_load_door")              # the only door into Vault is gone with its edge
        self.assertEqual(by["Vault"]["load_doors_out"], [{"ref": fk(0x311), "to": None}])   # its door back names a deleted door
        self.assertEqual(r["totals"]["refs_deleted"], 2)
        again = plugin("DLCAgain.esm", [ref(0x303, 0x101)], nmast=2)
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc, again])["cells"]}
        self.assertEqual((by["Lobby"]["refs"], by["Lobby"]["lights"]), (4, 2))
        self.assertEqual(by["Lobby"]["plugins"], ["Fallout4.esm", "DLCRobot.esm", "DLCAgain.esm"])

    def test_a_deleted_cell_leaves_the_census(self):
        # The DLC deletes Vault's CELL (record flag 0x20, no DATA): Vault, its references and its door back to Lobby
        # are gone; Lobby's door into it now names a door that no longer exists. A later plugin re-adds it: it is back.
        def plugin(name, recs, nmast=1):
            masts = [(b"MAST", b"Fallout4.esm\0"), (b"DATA", bytes(8))] + ([(b"MAST", b"DLCRobot.esm\0"), (b"DATA", bytes(8))] if nmast > 1 else [])
            tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 2, 0x800))] + masts, flags=1)
            sub = G(struct.pack("<I", 0), 3, bytes(8), recs)
            cells = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [sub])])
            path = os.path.join(self.tmp.name, name)
            with open(path, "wb") as f:
                f.write(tes4.serialize() + cells.serialize())
            return path
        dlc = plugin("DLCRobot.esm", [rec(b"CELL", 0x210, [(b"EDID", b"Vault\0")], flags=ic.DELETED)])
        r = ic.census([self.esm, dlc])
        by = {c["editor_id"]: c for c in r["cells"]}
        self.assertNotIn("Vault", by)
        self.assertEqual(r["totals"]["cells_deleted"], 1)
        self.assertEqual(r["totals"]["interiors"], 3)
        self.assertEqual(sorted((d["to"] or "") for d in by["Lobby"]["load_doors_out"]), ["", "world:Commonwealth"])
        again = plugin("DLCAgain.esm", cell(0x210, "Vault", [ref(0x312, 0x103)]), nmast=2)
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc, again])["cells"]}
        self.assertEqual((by["Vault"]["refs"], by["Vault"]["plugins"]), (1, ["DLCAgain.esm"]))

    def test_an_override_without_location_or_zone_clears_them(self):
        # The DLC re-saves Lobby without XLCN and with a zero XEZN: the winning record names neither.
        tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 1, 0x800)), (b"MAST", b"Fallout4.esm\0"),
                                (b"DATA", bytes(8))], flags=1)
        lobby = cell(0x200, "Lobby", [], fields=[(b"XEZN", struct.pack("<I", 0))])
        sub = G(struct.pack("<I", 0), 3, bytes(8), lobby)
        cells = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [sub])])
        dlc = os.path.join(self.tmp.name, "DLCPlain.esm")
        with open(dlc, "wb") as f:
            f.write(tes4.serialize() + cells.serialize())
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc])["cells"]}
        self.assertEqual((by["Lobby"]["location"], by["Lobby"]["encounter_zone"]), (None, None))
        self.assertEqual(by["Vault"]["location"], "VaultLocation")

    def test_a_deleted_base_record_is_no_light(self):
        # The DLC deletes the LIGH base 0x101: Lobby's two refs to it stay references but are no lights any more.
        tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 1, 0x800)), (b"MAST", b"Fallout4.esm\0"),
                                (b"DATA", bytes(8))], flags=1)
        dlc = os.path.join(self.tmp.name, "DLCBase.esm")
        with open(dlc, "wb") as f:
            f.write(tes4.serialize() + G(b"LIGH", 0, bytes(8), [rec(b"LIGH", 0x101, [], flags=ic.DELETED)]).serialize())
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc])["cells"]}
        self.assertEqual((by["Lobby"]["refs"], by["Lobby"]["lights"]), (5, 0))

    def test_navmesh_overrides_count_once_and_deleted_ones_not_at_all(self):
        # DLCRobot adds two navmeshes to Lobby; DLCAgain re-saves the first (same FormKey) and deletes the second.
        def plugin(name, kids, nmast=1):
            masts = [(b"MAST", b"Fallout4.esm\0"), (b"DATA", bytes(8))] + ([(b"MAST", b"DLCRobot.esm\0"), (b"DATA", bytes(8))] if nmast > 1 else [])
            tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 2, 0x800))] + masts, flags=1)
            sub = G(struct.pack("<I", 0), 3, bytes(8), cell(0x200, "Lobby", kids))
            cells = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [sub])])
            path = os.path.join(self.tmp.name, name)
            with open(path, "wb") as f:
                f.write(tes4.serialize() + cells.serialize())
            return path
        dlc = plugin("DLCRobot.esm", [rec(b"NAVM", 0x350, []), rec(b"NAVM", 0x351, [])])
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc])["cells"]}
        self.assertEqual(by["Lobby"]["navmeshes"], 2)
        again = plugin("DLCAgain.esm", [rec(b"NAVM", 0x350, []), rec(b"NAVM", 0x351, [], flags=ic.DELETED)], nmast=2)
        by = {c["editor_id"]: c for c in ic.census([self.esm, dlc, again])["cells"]}
        self.assertEqual(by["Lobby"]["navmeshes"], 1)

    def test_main_writes_the_census(self):
        out = os.path.join(self.tmp.name, "census.json")
        self.assertEqual(ic.main(["--out", out, self.esm]), 0)
        self.assertEqual(len(ib.load(out)["cells"]), 4)
        with self.assertRaises(SystemExit):
            ic.main(["--out", out, os.path.join(self.tmp.name, "DLCRobot.esm")])   # Fallout4.esm must come first


def crow(eid, key, reach="worldspace", status="backlog", refs=100, entered=("Commonwealth",), bases=10, worlds=None):
    return {"editor_id": eid, "formkey": key, "reach": reach, "status": status, "refs": refs, "lights": 1, "navmeshes": 1,
            "distinct_bases": bases, "entered_from": list(entered), "test_name": False,
            "load_doors_out": [], "load_doors_in": [{"from": e, "door": "D" + eid} for e in entered]}


class BatchPlanTests(unittest.TestCase):
    def plan_inputs(self):
        rows = [crow("Port", "1", status="in_port"),
                crow("BehindPort", "2", reach="behind_interior", status="second_hop", entered=("Port",)),
                crow("Near", "3"), crow("Far1", "4"), crow("Far2", "5"),
                crow("Behind2", "6", reach="behind_interior", status="second_hop", entered=("Far1",)),
                crow("DmndShop", "7", status="new", entered=("DiamondCity",)),
                crow("ccABCFO4001", "8", status="new"), crow("Unreached", "9", reach="no_load_door", status="new")]
        backlog = {"totals": {"backlog_new_models": 10, "backlog_new_models_per_cell_sum": 20},
                   "backlog": [{"formkey": "3", "nearest_m": 200, "rank": 9, "adds_models": 5, "distinct_models": 10, "new_models": 5},
                               {"formkey": "4", "nearest_m": 1500, "rank": 1, "adds_models": 7, "distinct_models": 10, "new_models": 5},
                               {"formkey": "5", "nearest_m": 1600, "rank": 2, "adds_models": 1, "distinct_models": 10, "new_models": 5}],
                   "second_hop": [{"formkey": "2", "after_rank": 0, "adds_models": 2},
                                  {"formkey": "6", "after_rank": 1, "adds_models": 3}]}
        return {"cells": rows, "worlds": {"a": "Commonwealth", "b": "DiamondCity"}}, backlog

    def test_order_limits_and_left_out(self):
        census, backlog = self.plan_inputs()
        r = ibs.plan(census, backlog, min_cells=1, max_cells=30)
        names = [c["editor_id"] for b in r["batches"] for c in b["cells"]]
        # completes the port first, then near, then the ranking with Behind2 right after Far1, then other worlds
        self.assertEqual(names, ["BehindPort", "Near", "Far1", "Behind2", "Far2", "DmndShop"])
        self.assertEqual([s["editor_id"] for s in r["skipped"]], ["ccABCFO4001"])
        phases = {c["editor_id"]: c["phase"] for b in r["batches"] for c in b["cells"]}
        self.assertEqual((phases["BehindPort"], phases["Near"], phases["Far1"], phases["DmndShop"]),
                         ("completes_port", "near", "ranked", "world"))
        self.assertEqual(r["batches"][0]["new_models_est"], 2 + 5 + 7 + 3 + 1 + round(10 * 0.5 * 0.5))
        small = ibs.plan(census, backlog, min_cells=1, max_cells=2)
        self.assertEqual([b["cell_count"] for b in small["batches"]], [2, 2, 2])
        byrefs = ibs.plan(census, backlog, min_cells=1, max_cells=30, max_refs=250)
        self.assertEqual([b["cell_count"] for b in byrefs["batches"]], [2, 2, 2])
        checked = ibs.disk_check(ibs.plan(census, backlog, 1, 2), free_gb=45, floor_gb=40)
        self.assertEqual(checked["totals"]["first_batch_under_floor"], 1)   # 2 x archives + loose: about 9 GB already
        self.assertIn("| 1 | 2 |", ibs.markdown(small))


    def test_extend_keeps_the_built_batches_and_adds_only_new_cells(self):
        census, backlog = self.plan_inputs()
        old = ibs.plan(census, backlog, min_cells=1, max_cells=2)
        census["cells"].append(crow("DLC01Lair01", "A:DLCRobot.esm", status="new", entered=("Commonwealth",)))
        near = next(r for r in census["cells"] if r["editor_id"] == "Near")
        near["plugins"] = ["Fallout4.esm", "DLCRobot.esm"]                     # a DLC now overrides an earlier cell
        grown = ibs.extend(old, ibs.plan(census, backlog, min_cells=1, max_cells=2), min_cells=1, max_cells=2)
        rows = {c["editor_id"]: c for b in grown["batches"] for c in b["cells"]}
        self.assertEqual(rows["Near"]["plugins"], ["Fallout4.esm", "DLCRobot.esm"])
        self.assertEqual(grown["totals"]["plugins_refreshed"], 1)
        strip = lambda bs: [dict(b, cells=[{k: v for k, v in c.items() if k != "plugins"} for c in b["cells"]]) for b in bs]
        self.assertEqual(strip(grown["batches"][:3]), strip(old["batches"]))   # built batches keep order and fields
        self.assertEqual([c["editor_id"] for c in grown["batches"][3]["cells"]], ["DLC01Lair01"])
        self.assertEqual(grown["batches"][3]["name"], "interiors_b04")
        self.assertEqual(grown["totals"]["extended_by"], 1)
        census["cells"] = [r for r in census["cells"] if r["editor_id"] != "Near"]
        with self.assertRaises(ValueError):                                     # an earlier cell may not vanish
            ibs.extend(old, ibs.plan(census, backlog, min_cells=1, max_cells=2))


class BatchToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def port(self, name, ids, plugin_bytes):
        d = os.path.join(self.tmp.name, name)
        os.makedirs(d)
        with open(os.path.join(d, "FO4Port.esm"), "wb") as f:
            f.write(plugin_bytes)
        with open(os.path.join(d, "formids.json"), "w", encoding="utf-8") as f:
            json.dump(ids, f)
        return d

    def plugin(self, extra=(), change=False, drop=False, xlcn=None, lctn=()):
        """The base port in miniature; `xlcn` gives the base cell an XLCN, `lctn` adds LCTN records as a top group
        (both what a later batch does once PluginSpike writes locations)."""
        OWN = 0x01000000
        stat = rec(b"STAT", OWN | 0x800, [(b"EDID", b"FO4Port_a\0"), (b"MODL", b"a.nif\0" if not change else b"b.nif\0")])
        c = rec(b"CELL", OWN | 0x801, [(b"EDID", b"FO4Port_Old\0"), (b"DATA", struct.pack("<I", 1))]
                + ([(b"XLCN", struct.pack("<I", xlcn))] if xlcn else []))
        refs = [] if drop else [ref(OWN | 0x802, OWN | 0x800)]
        kids = G(struct.pack("<I", OWN | 0x801), vp.GROUP_CELL_CHILDREN, bytes(8),
                 [G(struct.pack("<I", OWN | 0x801), vp.GROUP_TEMPORARY, bytes(8), refs)])
        blocks = [c, kids] + list(extra)
        top = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [G(struct.pack("<I", 0), 3, bytes(8), blocks)])])
        tes4 = vp.record_bytes(b"TES4", 0, 1, [(b"HEDR", struct.pack("<fII", 0.96, 3, 0x900)), (b"MAST", b"Starfield.esm\0"),
                                               (b"DATA", bytes(8))])
        locs = G(b"LCTN", 0, bytes(8), list(lctn)).serialize() if lctn else b""
        return tes4.serialize() + G(b"STAT", 0, bytes(8), [stat]).serialize() + locs + top.serialize()

    def test_compare_passes_when_base_cells_gain_locations(self):
        # The locations milestone: a base CELL gains an XLCN (its record changes, allowed) and LCTN records appear
        # (added); no id moves, no record goes, cells_added sees only CELL keys. The compare must keep passing.
        OWN = 0x01000000
        ids = {"STAT:FO4Port_a": 0x800, "CELL:FO4Port_Old": 0x801, "REFR:FO4Port_Old:1:Fallout4.esm": 0x802}
        old = self.port("old", ids, self.plugin())
        root = rec(b"LCTN", OWN | 0x8F0, [(b"EDID", b"FO4Port_InteriorsLocation\0"), (b"PNAM", struct.pack("<I", 0x01B736))])
        loc = rec(b"LCTN", OWN | 0x8F1, [(b"EDID", b"FO4Port_OldLocation\0"), (b"PNAM", struct.pack("<I", OWN | 0x8F0)),
                                         (b"DATA", bytes(4) + b"\xff" + bytes(3))])
        grown_ids = dict(ids, **{"LCTN:FO4Port_InteriorsLocation": 0x8F0, "LCTN:FO4Port_OldLocation": 0x8F1})
        grown = self.port("grown", grown_ids, self.plugin(xlcn=OWN | 0x8F1, lctn=[root, loc]))
        r = ib.compare(old, grown)
        self.assertTrue(r["pass"], r["problems"])
        self.assertEqual(r["records"]["changed"], {"CELL": 1})
        self.assertEqual(r["records"]["added"], {"LCTN": 2})
        self.assertEqual(r["records"]["identical"], {"REFR": 1, "STAT": 1})
        self.assertEqual((r["cells_added"], r["cells_removed"]), ([], []))
        # and the next batch over that one: the LCTN ids are base ids now, so they must keep their numbers
        later = self.port("later", dict(grown_ids, **{"LCTN:FO4Port_OldLocation": 0x8F2}),
                          self.plugin(xlcn=OWN | 0x8F1, lctn=[root, loc]))
        self.assertIn("renumbered", ib.compare(grown, later)["problems"][0])
        self.assertTrue(ib.compare(grown, self.port("same", grown_ids, self.plugin(xlcn=OWN | 0x8F1, lctn=[root, loc])))["pass"])

    def test_compare_passes_a_grown_port_and_fails_renumbered_or_removed(self):
        OWN = 0x01000000
        ids = {"STAT:FO4Port_a": 0x800, "CELL:FO4Port_Old": 0x801, "REFR:FO4Port_Old:1:Fallout4.esm": 0x802}
        old = self.port("old", ids, self.plugin())
        newc = rec(b"CELL", OWN | 0x850, [(b"EDID", b"FO4Port_New\0"), (b"DATA", struct.pack("<I", 1))])
        grown = self.port("grown", dict(ids, **{"CELL:FO4Port_New": 0x850}), self.plugin(extra=[newc], change=True))
        r = ib.compare(old, grown)
        self.assertTrue(r["pass"], r["problems"])
        self.assertEqual(r["cells_added"], ["FO4Port_New"])
        self.assertEqual((r["records"]["changed"], r["records"]["identical"], r["records"]["added"]),
                         ({"STAT": 1}, {"CELL": 1, "REFR": 1}, {"CELL": 1}))
        moved = self.port("moved", dict(ids, **{"STAT:FO4Port_a": 0x851}), self.plugin())
        self.assertIn("renumbered", ib.compare(old, moved)["problems"][0])
        gone = self.port("gone", {k: v for k, v in ids.items() if not k.startswith("REFR")}, self.plugin(drop=True))
        problems = " ".join(ib.compare(old, gone)["problems"])
        self.assertIn("missing", problems)
        self.assertIn("removed", problems)

    def test_batch_cells_doors_placed_counts_and_prune(self):
        plan = {"batches": [{"name": "interiors_b01", "cells": [{"editor_id": "A"}, {"editor_id": "B"}]},
                            {"name": "interiors_b02", "cells": [{"editor_id": "C"}]}]}
        self.assertEqual(ib.batch_cells(plan, 0), [])
        self.assertEqual(ib.batch_cells(plan, 2), ["A", "B", "C"])
        with self.assertRaises(ValueError):
            ib.batch_cells(plan, 3)
        census = {"worlds": {"x": "Commonwealth", "y": "DiamondCity"},
                  "cells": [{"editor_id": "A", "load_doors_in": [{"from": "Commonwealth", "door": "0AA:Fallout4.esm"}]},
                            {"editor_id": "B", "load_doors_in": [{"from": "A", "door": "0BB:Fallout4.esm"},
                                                                 {"from": "DiamondCity", "door": "0CC:Fallout4.esm"}]}]}
        d = ib.doors(plan, census, 1)
        self.assertEqual(d["only"], "FO4Port_A")
        self.assertEqual(d["coc_only"], ["FO4Port_B"])
        self.assertEqual(d["cells"][1]["interior_doors_from"], ["A"])
        self.assertEqual(d["cells"][1]["other_worldspace_doors"], ["DiamondCity"])
        log = os.path.join(self.tmp.name, "build.log")
        with open(log, "w", encoding="utf-8") as f:
            f.write("cell FO4Port_ConcordFactory 001387:FO4Port.esm: placed 493 references + 23 lights (0 initially disabled), skipped 28\n")
        self.assertEqual(ib.placed_counts(log), {"ConcordFactory": {"placed": 493, "lights": 23, "skipped": 28}})
        root = os.path.join(self.tmp.name, "staging")
        for n, mine in (("interiors_b01", True), ("interiors_b02", True), ("interiors_b03", True), ("interiors_b04", False),
                        ("integ_v6", True)):
            os.makedirs(os.path.join(root, n, "port"))
            if mine:
                with open(os.path.join(root, n, "result.json"), "w", encoding="utf-8") as f:
                    json.dump({"name": n, "installed": False, "pass": True}, f)
                with open(os.path.join(root, n, "port", "FO4Port.esm"), "wb") as f:
                    f.write(n.encode())
        # nothing is released yet: prune keeps everything, even with --delete
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        self.assertTrue(os.path.isdir(os.path.join(root, "interiors_b01")))
        self.assertEqual(sorted(os.listdir(root)), ["integ_v6", "interiors_b01", "interiors_b02", "interiors_b03", "interiors_b04"])

    def test_release_refuses_installed_queued_failed_or_unsuperseded_stages(self):
        root = os.path.join(self.tmp.name, "staging")
        refs = os.path.join(self.tmp.name, "refs")
        arch = os.path.join(self.tmp.name, "archive")
        sf = os.path.join(self.tmp.name, "Starfield")
        os.makedirs(os.path.join(sf, "Data"))
        os.makedirs(refs)

        def stage(n, ok, prev=None):
            os.makedirs(os.path.join(root, n, "port"), exist_ok=True)
            steps = {"compare_prev": {"prev": os.path.join(root, prev), "pass": True}} if prev else {}
            with open(os.path.join(root, n, "port", "FO4Port.esm"), "wb") as f:
                f.write(n.encode())
            with open(os.path.join(root, n, "port", "FO4Port - Main.ba2"), "wb") as f:
                f.write(b"BTDX" + n.encode())
            steps["pack"] = {"bytes": {"FO4Port - Main.ba2": 4 + len(n)},
                             "sha256": {"FO4Port - Main.ba2": ib.sha256(os.path.join(root, n, "port", "FO4Port - Main.ba2"))}}
            pins = {"plugin": ib.sha256(os.path.join(root, n, "port", "FO4Port.esm"))}
            with open(os.path.join(root, n, "result.json"), "w", encoding="utf-8") as f:
                json.dump({"name": n, "installed": False, "pass": ok, "steps": steps, "pins": pins}, f)
            with open(os.path.join(root, n, "build.log"), "w", encoding="utf-8") as f:
                f.write("log of " + n)
            return os.path.join(root, n)

        b01 = stage("interiors_b01", True)
        b02 = stage("interiors_b02", False, "interiors_b01")         # failed: not a successor, and itself evidence
        b03 = stage("interiors_b03", True, "interiors_b01")
        b04 = stage("interiors_b04", True, "interiors_b03")
        b05 = stage("interiors_b05", True, "interiors_b04")

        def rel(st, succ):
            return ib.release(st, "superseded", [refs], sf, succ, arch)

        # failed builds are evidence; a reason, reference folders, the Starfield folder and a real successor are required
        with self.assertRaisesRegex(ValueError, "failed build"):
            rel(b02, b03)
        with self.assertRaisesRegex(ValueError, "reason"):
            ib.release(b01, " ", [refs], sf, b03, arch)
        with self.assertRaisesRegex(ValueError, "check-refs"):
            ib.release(b01, "x", [], sf, b03, arch)
        with self.assertRaisesRegex(ValueError, "missing"):
            ib.release(b01, "x", [refs], os.path.join(self.tmp.name, "NoStarfield"), b03, arch)
        with self.assertRaisesRegex(ValueError, "did not pass"):
            rel(b01, b02)
        with self.assertRaisesRegex(ValueError, "was not built with --prev"):
            rel(b01, b04)
        # a queue or recovery receipt naming the stage (either slash form, any case) keeps it
        receipt = os.path.join(refs, "queue", "cleanup_pending.json")
        os.makedirs(os.path.dirname(receipt))
        with open(receipt, "w", encoding="utf-8") as f:
            json.dump({"plugins_restore_pending": b01.upper().replace("/", "\\") + "\\port"}, f)
        with self.assertRaisesRegex(ValueError, "still named by"):
            rel(b01, b03)
        os.remove(receipt)
        # the installed plugin keeps it
        with open(os.path.join(sf, "Data", "FO4Port.esm"), "wb") as f:
            f.write(b"interiors_b01")
        with self.assertRaisesRegex(ValueError, "installed"):
            rel(b01, b03)
        os.remove(os.path.join(sf, "Data", "FO4Port.esm"))
        # nothing is deleted without a release
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        # released: the evidence is archived and verified, then prune deletes it; the failed one and the newest two stay
        rec = rel(b01, b03)
        self.assertEqual(sorted(rec["tree"]), ["build.log", "port/FO4Port - Main.ba2", "port/FO4Port.esm", "result.json"])
        self.assertEqual(sorted(rec["archived"]), ["build.log", "result.json"])          # the port: carried by b03
        with open(os.path.join(rec["archive"], "build.log"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "log of interiors_b01")
        self.assertEqual(os.path.dirname(rec["archive"]), os.path.join(arch, "interiors_b01"))
        self.assertEqual(ib.release(b01, "again", [refs], sf, b03, arch)["archive"], rec["archive"])   # idempotent
        self.assertEqual([os.path.basename(p) for p in ib.prune(root, 2, delete=False)], ["interiors_b01"])
        self.assertTrue(os.path.isdir(b01))
        ib.prune(root, 2, delete=True)
        self.assertEqual(sorted(os.listdir(root)), ["interiors_b02", "interiors_b03", "interiors_b04", "interiors_b05"])
        # a release goes stale when anything changes after it
        rel(b03, b04)
        with open(os.path.join(b03, "crash.log"), "w", encoding="utf-8") as f:     # new evidence after the release
            f.write("x")
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        os.remove(os.path.join(b03, "crash.log"))
        with open(os.path.join(refs, "running_queue.json"), "w", encoding="utf-8") as f:   # a queue naming it
            json.dump({"stage": b03}, f)
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        os.remove(os.path.join(refs, "running_queue.json"))
        with open(os.path.join(sf, "Data", "FO4Port.esm"), "wb") as f:              # its plugin installed
            f.write(b"interiors_b03")
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        os.remove(os.path.join(sf, "Data", "FO4Port.esm"))
        first = rel(b03, b04)["archive"]
        os.remove(os.path.join(first, "build.log"))                                  # the archive copy lost
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        # a changed stage released again gets a new generation; the first one's bytes stay as they were
        with open(os.path.join(first, "build.log"), "w", encoding="utf-8") as f:
            f.write("log of interiors_b03")
        with open(os.path.join(b03, "build.log"), "w", encoding="utf-8") as f:
            f.write("second observation")
        second = rel(b03, b04)["archive"]
        self.assertNotEqual(first, second)
        with open(os.path.join(first, "build.log"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "log of interiors_b03")
        # an existing generation with other bytes is never overwritten
        with open(os.path.join(second, "build.log"), "w", encoding="utf-8") as f:
            f.write("tampered")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            rel(b03, b04)
        # another writer publishing at the destination mid-copy keeps its bytes, and the release refuses
        with open(os.path.join(b03, "late.log"), "w", encoding="utf-8") as f:
            f.write("ours")
        real_copy = shutil.copyfile

        def racing_copy(src, dst, *args, **kwargs):
            out = real_copy(src, dst, *args, **kwargs)
            if src.endswith("late.log"):
                with open(os.path.join(os.path.dirname(dst), "late.log"), "w", encoding="utf-8") as f:
                    f.write("theirs")
            return out

        shutil.copyfile = racing_copy
        try:
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                rel(b03, b04)
        finally:
            shutil.copyfile = real_copy
        racing = [d for d in os.listdir(os.path.join(arch, "interiors_b03")) if os.path.isfile(
            os.path.join(arch, "interiors_b03", d, "late.log"))]
        with open(os.path.join(arch, "interiors_b03", racing[0], "late.log"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "theirs")
        os.remove(os.path.join(b03, "late.log"))
        # any file other than the port plugin and archives is archived whatever its size; a successor whose port has
        # gone or changed no longer covers the stage
        with open(os.path.join(b03, "crash-evidence.bin"), "wb") as f:
            f.write(b"\0" * 1000)
        rec = rel(b03, b04)
        self.assertIn("crash-evidence.bin", rec["archived"])
        os.rename(os.path.join(b04, "port"), os.path.join(b04, "port_moved"))
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        with self.assertRaisesRegex(ValueError, "not the one it built"):
            rel(b03, b04)
        os.rename(os.path.join(b04, "port_moved"), os.path.join(b04, "port"))
        with open(os.path.join(b04, "port", "FO4Port - Main.ba2"), "ab") as f:
            f.write(b"more")
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        with open(os.path.join(b04, "port", "FO4Port - Main.ba2"), "wb") as f:   # same size, one byte flipped
            f.write(b"BTDXinteriors_b05")
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        legacy = os.path.join(b04, "result.json")                               # a build with no archive sha256s
        with open(legacy, encoding="utf-8") as f:
            r4 = json.load(f)
        del r4["steps"]["pack"]["sha256"]
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump(r4, f)
        with self.assertRaisesRegex(ValueError, "no build-time sha256"):
            rel(b03, b04)
        with open(os.path.join(b04, "port", "FO4Port - Main.ba2"), "wb") as f:
            f.write(b"BTDXinteriors_b04")
        r4["steps"]["pack"]["sha256"] = {"FO4Port - Main.ba2": ib.sha256(os.path.join(b04, "port", "FO4Port - Main.ba2"))}
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump(r4, f)
        os.rename(refs, refs + "_moved")                                           # a check that cannot run
        self.assertEqual(ib.prune(root, 2, delete=True), [])
        os.rename(refs + "_moved", refs)
        self.assertTrue(os.path.isdir(b03))
        self.assertEqual([os.path.basename(p) for p in ib.prune(root, 2, delete=True)], ["interiors_b03"])
        self.assertFalse(os.path.isdir(b03))

if __name__ == "__main__":
    unittest.main()


class BuildFlowTests(unittest.TestCase):
    """build() with every external step faked (export, convert, promote, PluginSpike, the door patch): the order of the
    steps, the arguments they get, the base exports pinned, the result table. The real tools run on the PC."""

    def test_build_runs_the_steps_and_writes_the_result(self):
        self._build_flow()

    def test_a_cell_missing_from_the_plugin_fails_the_batch_and_skips_the_pack(self):
        # Bad exports fine but PluginSpike never writes it: the batch fails and nothing is packed.
        res = self._build_flow(bad_export_ok=True)
        self.assertEqual((res["cells"]["Bad"]["result"], res["cells"]["Bad"]["reason"]),
                         ("failed", "cell not written by PluginSpike"))
        self.assertEqual(res["steps"]["export"]["failed"], [])
        self.assertEqual(res["steps"]["cells_failed"], ["Bad"])
        self.assertNotIn("pack", res["steps"])

    def test_a_failed_locations_run_fails_the_batch_before_pluginspike(self):
        res = self._build_flow(locations_fail=True)
        self.assertEqual(res["error"], "locations failed")
        self.assertEqual(res["steps"]["locations"]["exit"], 1)
        self.assertNotIn("pluginspike", res["steps"])

    def test_a_cached_pre_schema_3_export_joins_the_locations_run(self):
        # An earlier batch's export still in --work from before schema 3 is reused as is (never re-exported), so its
        # FO4 location data must come from the sidecar too, or the cell's LCTN key would change on a later re-export
        res = self._build_flow(stale_cache=True)
        self.assertEqual((res["steps"]["locations"]["exit"], res["steps"]["locations"]["cells"]), (0, 2))
        # a work staging with exports but no sources.json (made before the pins) is adopted, which result.json says
        self.assertEqual(res["steps"]["sources"]["work"], "adopted")
        self.assertEqual(ib.load(os.path.join(res["work"], "exports", "sources.json"))["status"], "adopted")

    def test_work_sources_states(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = os.path.join(tmp.name, "work")
        pins = {"plugins": {"Fallout4.esm": {"sha256": "aa", "bytes": 1}}, "archives": {}}
        a = argparse.Namespace(work=work, allow_source_change=False)
        self.assertEqual(ib.work_sources(work), (None, "new"))              # absent
        os.makedirs(os.path.join(work, "exports"))
        self.assertEqual(ib.work_sources(work), (None, "new"))              # empty
        self.assertEqual(ib.check_work(a, pins), ("new", []))
        ib.save(os.path.join(work, "exports", "Cell.json"), {"cell": "Cell", "refs": []})
        self.assertEqual(ib.work_sources(work), (None, "adopted"))          # exports from before the pins
        self.assertEqual(ib.check_work(a, pins), ("adopted", []))
        os.remove(os.path.join(work, "exports", "Cell.json"))
        ib.save(os.path.join(work, "manifest.json"), {"items": []})
        self.assertEqual(ib.work_sources(work), (None, "adopted"))          # conversion checkpoints count too
        ib.save(os.path.join(work, "exports", "sources.json"), {"schema_version": 1, "sources": pins, "status": "new"})
        self.assertEqual(ib.work_sources(work), (pins, "pinned"))
        self.assertEqual(ib.check_work(a, pins), ("match", []))
        grown = {"plugins": dict(pins["plugins"], **{"DLCRobot.esm": {"sha256": "bb", "bytes": 2}}), "archives": {}}
        self.assertEqual(ib.check_work(a, grown), ("match", []))            # a plugin pinned for the first time is no change
        other = {"plugins": {"Fallout4.esm": {"sha256": "cc", "bytes": 1}}, "archives": {}}
        with self.assertRaisesRegex(SystemExit, "--work .*refusing to reuse its exports and checkpoints"):
            ib.check_work(a, other)
        a.allow_source_change = True
        self.assertEqual(ib.check_work(a, other), ("changed", ["Fallout4.esm sha256 aa -> cc"]))
        with open(os.path.join(work, "exports", "sources.json"), "w") as f:
            f.write("not json")
        self.assertEqual(ib.work_sources(work), (None, "adopted"))          # an unreadable record proves nothing
        # ... and neither does one that pins nothing (a partial write, a hand edit): adopted, never "match"
        for empty in ({"schema_version": 1}, {"sources": None}, {"sources": {"plugins": {}, "archives": {}}}, {"sources": {"archives": {"x.ba2": {}}}}):
            ib.save(os.path.join(work, "exports", "sources.json"), empty)
            self.assertEqual(ib.work_record(work), (None, "adopted"), empty)
            self.assertEqual(ib.check_work(a, pins), ("adopted", []), empty)
        # the full record carries the per-cell export plugins and the sticky history
        full = {"schema_version": 2, "sources": pins, "cells": {"Cell": ["Fallout4.esm"]}, "history": [{"batch": "b05", "status": "adopted", "differences": []}]}
        ib.save(os.path.join(work, "exports", "sources.json"), full)
        self.assertEqual(ib.work_record(work), (full, "pinned"))
        self.assertEqual(ib.work_status_label("match", full["history"]), "match (adopted by b05)")
        self.assertEqual(ib.work_status_label("match", []), "match")
        self.assertEqual(ib.work_status_label("changed", full["history"] + [{"batch": "b07", "status": "changed"}]), "changed (adopted by b05; changed by b07)")

    def test_a_cached_export_made_from_fewer_plugins_is_exported_again(self):
        # Batch 8 once exported GeneralAtomicsFactory01 from Fallout4.esm alone (no plan `plugins`, no --census); the
        # build repeated with the census wants [Fallout4.esm, DLCRobot.esm]: the cached file is not the merged cell and
        # must be exported again, whatever the work pins say (DLCRobot.esm newly pinned is "added", not a change).
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        t = tmp.name
        dlc = os.path.join(t, "DLC")
        os.makedirs(dlc)
        open(os.path.join(dlc, "DLCRobot.esm"), "wb").close()
        a = argparse.Namespace(fo4export="Fo4Export.dll", fo4_data=t, dlc_data=[dlc])
        out, log = os.path.join(t, "exports"), os.path.join(t, "export.log")
        os.makedirs(out)
        calls = []

        def fake_run(cmd, log, env=None, cwd=None):
            calls.append(cmd)
            ib.save(cmd[-1], {"schema_version": 3, "cell": cmd[-2], "formkey": "04280D:Fallout4.esm", "refs": [{"n": len(cmd)}]})
            return 0, 0.1
        real, ib.run = ib.run, fake_run
        try:
            fo4, robot = os.path.join(t, "Fallout4.esm"), os.path.join(dlc, "DLCRobot.esm")
            both = ["Fallout4.esm", "DLCRobot.esm"]
            self.assertEqual(ib.export_cell(a, "Factory", out, log)[1], 0)                 # exported from Fallout4.esm alone
            self.assertEqual(calls[-1][2:5], [fo4, "export", "Factory"])
            path = os.path.join(out, "Factory.json")
            self.assertEqual(ib.export_plugins(path), ["Fallout4.esm"])                     # no record: its formkey's owner
            self.assertEqual(ib.export_cell(a, "Factory", out, log, ["Fallout4.esm"])[1:], (0, 0.0))   # same list: cached
            self.assertEqual(ib.export_cell(a, "Factory", out, log, None, {"Factory": ["Fallout4.esm"]})[1:], (0, 0.0))
            self.assertEqual(len(calls), 1)
            self.assertEqual(ib.export_cell(a, "Factory", out, log, both)[1], 0)          # the DLC override is now known
            self.assertEqual(calls[-1][2:7], [robot, "--master", fo4, "export", "Factory"])
            self.assertEqual(len(calls), 2)
            with open(log, encoding="utf-8") as f:
                self.assertIn("Factory: cached export was made from ['Fallout4.esm'], now ['Fallout4.esm', 'DLCRobot.esm']: exporting again", f.read())
            # the record says what it was made from, so the formkey (still Fallout4.esm's) no longer decides
            self.assertEqual(ib.export_plugins(path, {"Factory": both}), both)
            self.assertEqual(ib.export_cell(a, "Factory", out, log, both, {"Factory": both})[1:], (0, 0.0))
            self.assertEqual(ib.export_cell(a, "Factory", out, log, ["DLCRobot.esm"], {"Factory": both})[1:], (0, 0.0))   # same order, Fallout4.esm implied
            self.assertEqual(len(calls), 2)
            # a recorded merged export asked for from Fallout4.esm alone is exported again too: the list differs
            self.assertEqual(ib.export_cell(a, "Factory", out, log, None, {"Factory": both})[1], 0)
            self.assertEqual(len(calls), 3)
            # a DLC's own cell cached before the record: its formkey names the plugin, Fallout4.esm is its master: cached
            ib.save(os.path.join(out, "Lair.json"), {"cell": "Lair", "formkey": "0008A3:DLCRobot.esm", "refs": []})
            self.assertEqual(ib.export_cell(a, "Lair", out, log, both)[1:], (0, 0.0))
            self.assertEqual(len(calls), 3)
            # an unreadable cached export counts as Fallout4.esm's: a base-game cell keeps it, a multi-plugin one re-exports
            with open(os.path.join(out, "Odd.json"), "w") as f:
                f.write("not json")
            self.assertEqual(ib.export_plugins(os.path.join(out, "Odd.json")), ["Fallout4.esm"])
            self.assertEqual(ib.export_cell(a, "Odd", out, log)[1:], (0, 0.0))
            self.assertEqual(ib.export_cell(a, "Odd", out, log, both)[1], 0)
            self.assertEqual(len(calls), 4)
        finally:
            ib.run = real

    def test_base_cells_a_dlc_overrides_read_the_census(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = tmp.name
        ib.save(os.path.join(base, "Old.json"), {"cell": "Old", "formkey": "000010:Fallout4.esm"})
        ib.save(os.path.join(base, "Factory.json"), {"cell": "Factory", "formkey": "04280D:Fallout4.esm"})
        ib.save(os.path.join(base, "Lair.json"), {"cell": "Lair", "formkey": "0008A3:DLCRobot.esm"})
        with open(os.path.join(base, "Odd.json"), "w") as f:
            f.write("not json")
        census = {"cells": [{"editor_id": "Factory", "formkey": "04280D:Fallout4.esm", "plugins": ["Fallout4.esm", "DLCRobot.esm"]},
                            {"editor_id": "Old", "formkey": "000010:Fallout4.esm", "plugins": ["Fallout4.esm"]},
                            {"editor_id": "Lair", "formkey": "0008A3:DLCRobot.esm", "plugins": ["DLCRobot.esm"]}]}
        cells = ["Old", "Factory", "Lair", "Odd", "Missing"]
        self.assertEqual(ib.base_plugins(cells, base, census), {"Factory": ["Fallout4.esm", "DLCRobot.esm"], "Lair": ["Fallout4.esm", "DLCRobot.esm"]})
        self.assertEqual(ib.base_plugins(cells, base, None), {})
        # the pins cover a base cell's DLC plugin, as a batch cell's
        a = argparse.Namespace(fo4_data=os.path.join(base, "Data"), dlc_data=[])
        os.makedirs(a.fo4_data)
        open(os.path.join(a.fo4_data, "Fallout4.esm"), "wb").close()
        plan = {"batches": [{"cells": [{"editor_id": "Plain", "formkey": "000011:Fallout4.esm", "plugins": ["Fallout4.esm"]}]}]}
        self.assertEqual(sorted(ib.source_pins(a, plan, 1)["plugins"]), ["Fallout4.esm"])
        pins = ib.source_pins(a, plan, 1, ib.base_plugins(cells, base, census))["plugins"]
        self.assertEqual((sorted(pins), pins["DLCRobot.esm"]), (["DLCRobot.esm", "Fallout4.esm"], None))   # not under --dlc-data: pinned None

    def test_locations_sidecar_runs_once_per_source_plugin(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        t = tmp.name
        dlc = os.path.join(t, "dlcdata")
        os.makedirs(dlc)
        open(os.path.join(dlc, "DLCRobot.esm"), "wb").close()
        a = argparse.Namespace(fo4export="Fo4Export.dll", fo4_data=os.path.join(t, "Data"), dlc_data=[dlc])
        fo4 = os.path.join(a.fo4_data, "Fallout4.esm")
        exports = {}
        for c, fk in (("Old", "000001:Fallout4.esm"), ("Lair", "0008A3:DLCRobot.esm"), ("Keyless", None), ("Gone", "000002:DLCCoast.esm")):
            exports[c] = os.path.join(t, c + ".json")
            ib.save(exports[c], {"cell": c, "refs": []} if fk is None else {"cell": c, "formkey": fk, "refs": []})
        calls, empty = [], [False]

        def fake_run(cmd, log, env=None, cwd=None):
            calls.append(cmd)
            ib.save(cmd[cmd.index("locations") + 1], {"schema_version": 1, "cells": {} if empty[0] else {
                c: {"cell_data": {"flags": 1, "name": c}, "location": None, "encounter_zone": None} for c in cmd[cmd.index("locations") + 2:]}})
            return 0, 0.1
        real, ib.run = ib.run, fake_run
        try:
            dst, log = os.path.join(t, "locations.json"), os.path.join(t, "build.log")
            # Fallout4.esm's cells (a formkey-less export counts as Fallout4.esm's) in one run, the DLC's in its own with the master
            self.assertEqual(ib.locations_sidecar(a, {c: exports[c] for c in ("Old", "Lair", "Keyless")}, dst, log)[0], 0)
            self.assertEqual([c[1:] for c in calls], [["Fo4Export.dll", fo4, "locations", dst + ".tmp", "Keyless", "Old"],
                                                      ["Fo4Export.dll", os.path.join(dlc, "DLCRobot.esm"), "--master", fo4, "locations",
                                                       dst + ".DLCRobot.esm.tmp", "Lair"]])
            self.assertEqual(sorted(ib.load(dst)["cells"]), ["Keyless", "Lair", "Old"])
            # a cell the plan says a DLC overrides (a Fallout4.esm formkey) joins the DLC's run, from the same sources as its export
            del calls[:]
            self.assertEqual(ib.locations_sidecar(a, {c: exports[c] for c in ("Old", "Lair", "Keyless")}, dst, log,
                                                  {"Old": ["Fallout4.esm", "DLCRobot.esm"]})[0], 0)
            self.assertEqual([c[c.index("locations") + 2:] for c in calls], [["Keyless"], ["Lair", "Old"]])
            self.assertEqual(ib.load(dst)["cells"]["Lair"]["cell_data"]["name"], "Lair")
            self.assertFalse(os.path.exists(dst + ".tmp") or os.path.exists(dst + ".DLCRobot.esm.tmp"))
            # a DLC that is not under --dlc-data fails the step before any run
            del calls[:]
            self.assertEqual(ib.locations_sidecar(a, {"Gone": exports["Gone"]}, dst, log)[0], 2)
            self.assertEqual(calls, [])
            # a run that wrote no cells is a failure, not an empty sidecar
            empty[0] = True
            self.assertEqual(ib.locations_sidecar(a, {"Old": exports["Old"]}, dst, log)[0], 3)
            # nothing stale: no run, an empty sidecar
            del calls[:]
            self.assertEqual(ib.locations_sidecar(a, {}, dst, log)[0], 0)
            self.assertEqual((calls, ib.load(dst)["cells"]), ([], {}))
            self.assertIn("locations: Fo4Export exit 0", open(log, encoding="utf-8").read())
        finally:
            ib.run = real

    def _build_flow(self, bad_export_ok=False, locations_fail=False, stale_cache=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        t = tmp.name
        base = os.path.join(t, "base")
        os.makedirs(base)
        OWN = 0x01000000
        tool = BatchToolTests()
        old_plugin = tool.plugin()
        with open(os.path.join(base, "FO4Port.esm"), "wb") as f:
            f.write(old_plugin)
        ids = {"STAT:FO4Port_a": 0x800, "CELL:FO4Port_Old": 0x801, "REFR:FO4Port_Old:1:Fallout4.esm": 0x802}
        ib.save(os.path.join(base, "formids.json"), ids)
        ib.save(os.path.join(base, "doors.json"), {"doors": [{"src": "1:Fallout4.esm", "marker": "000803"}]})
        ib.save(os.path.join(base, "Old.json"), {"cell": "Old", "refs": [{"model": "a.nif"}]})
        ib.save(os.path.join(base, "editorids.json"), {"meshes\\A.nif": "FO4Port_A"})
        plan = os.path.join(t, "plan.json")
        ib.save(plan, {"batches": [{"name": "interiors_b01", "archives_gb_est": 0.0, "work_staging_gb_est": 0.0, "cells": [{"editor_id": "New"}, {"editor_id": "Bad"}]}]})
        work, out = os.path.join(t, "work"), os.path.join(t, "staging", "interiors_b01")
        calls = []
        newc = rec(b"CELL", OWN | 0x850, [(b"EDID", b"FO4Port_New\0"), (b"DATA", struct.pack("<I", 1))])
        if stale_cache:                                                   # an earlier batch's export, schema 2, reused as is
            os.makedirs(os.path.join(work, "exports"))
            ib.save(os.path.join(work, "exports", "New.json"), {"cell": "New", "refs": [{"model": "meshes\\n.nif"}]})
        sidecar_cells = ["New", "Old"] if stale_cache else ["Old"]

        def fake_run(cmd, log, env=None, cwd=None):
            calls.append(cmd)
            joined = " ".join(cmd)
            if "export" in cmd and cmd[0] == "dotnet":
                if cmd[-2] == "Bad" and not bad_export_ok:
                    return 1, 0.1
                if stale_cache:                                           # the cached export is never re-exported
                    self.assertNotEqual(cmd[-2], "New")
                ib.save(cmd[-1], {"schema_version": 3, "cell": cmd[-2], "refs": [{"model": "meshes\\n.nif"}],
                                  "cell_data": {"flags": 1, "name": None}, "location": None, "encounter_zone": None})
            elif "convert_batch.py" in joined:
                self.assertEqual(ib.load(os.path.join(work, "editorids.json")), {"meshes\\A.nif": "FO4Port_A"})
                merged = ib.load(cmd[cmd.index("--cell-json") + 1])
                self.assertEqual(len(merged["refs"]), 3 if bad_export_ok else 2)   # Old (pinned) + New (+ Bad)
                ib.save(os.path.join(work, "manifest.json"), {"items": [], "failures": [{"nif": "meshes\\n.nif", "reason": "x"}]})
            elif "port_promote.py" in joined:
                ib.save(cmd[cmd.index("--out") + 1], {})
            elif "locations" in cmd and cmd[0] == "dotnet":              # Fo4Export locations: the exports without the keys
                self.assertEqual(cmd[1:4], ["Fo4Export.dll", os.path.join(t, "Fallout4.esm"), "locations"])
                self.assertEqual(cmd[5:], sidecar_cells)
                if locations_fail:
                    return 1, 0.1
                ib.save(cmd[4], {"schema_version": 1, "cells": {c: {"cell_data": {"flags": 1, "name": None}, "location": None,
                                                                     "encounter_zone": None} for c in cmd[5:]}})
            elif cmd[0] == "dotnet":                                     # PluginSpike
                raw = cmd[2]
                self.assertEqual(ib.load(os.path.join(raw, "formids.json")), ids)   # seeded with the base map
                self.assertEqual(sorted(ib.load(os.path.join(raw, "locations.json"))["cells"]), sidecar_cells)   # the sidecar is there first
                with open(os.path.join(raw, "FO4Port.esm"), "wb") as f:
                    f.write(tool.plugin(extra=[newc]))
                ib.save(os.path.join(raw, "formids.json"), dict(ids, **{"CELL:FO4Port_New": 0x850}))
                ib.save(os.path.join(raw, "teleports.json"), {"Linked": 0, "Issues": []})
                with open(log, "a", encoding="utf-8") as f:
                    f.write("cell FO4Port_New 000850:FO4Port.esm: placed 1 references + 0 lights (0 initially disabled), skipped 0\n")
            elif "vmad_patch.py" in joined and cmd[2] == "port":
                self.assertEqual(cmd[cmd.index("--keep-markers") + 1], os.path.join(base, "doors.json"))
                dst = cmd[cmd.index("--out") + 1]
                os.makedirs(dst)
                src = cmd[cmd.index("--port") + 1]
                for n in ("FO4Port.esm", "formids.json"):
                    with open(os.path.join(src, n), "rb") as a_, open(os.path.join(dst, n), "wb") as b_:
                        b_.write(a_.read())
            return 0, 0.1

        argv = ["build", "--plan", plan, "--batch", "1", "--base", base, "--base-exports", base, "--core", os.path.join(t, "core"),
                "--work", work, "--out", out, "--fo4-data", t, "--starfield", t, "--content-resources", "c.zip",
                "--texconv", "tex.exe", "--collision-template", "t.nif", "--fo4export", "Fo4Export.dll",
                "--pluginspike", "PluginSpike.dll", "--jobs", "1", "--min-free-gb", "0"] + ([] if bad_export_ok else ["--no-pack"])
        real, real_pack = ib.run, ib.deploy_starfield.build_archive
        ib.run = fake_run
        ib.deploy_starfield.build_archive = lambda *_a, **_k: self.fail("packed a failed batch")
        try:
            rc = ib.main(argv)
        finally:
            ib.run, ib.deploy_starfield.build_archive = real, real_pack
        res = ib.load(os.path.join(out, "result.json"))
        self.assertEqual(rc, 1, res)                                      # the Bad cell fails the batch
        if bad_export_ok or locations_fail or stale_cache:
            return res
        self.assertEqual((res["steps"]["locations"]["exit"], res["steps"]["locations"]["cells"]), (0, 1))
        self.assertEqual(ib.load(os.path.join(out, "plugin", "locations.json"))["schema_version"], 1)
        self.assertEqual(res["cells"]["New"]["result"], "converted")
        self.assertEqual(res["cells"]["New"]["placed"], 1)
        self.assertEqual(res["cells"]["New"]["failed_models"], ["meshes\\n.nif"])
        self.assertEqual((res["cells"]["Bad"]["result"], res["cells"]["Bad"]["reason"]), ("failed", "export failed"))
        self.assertTrue(res["steps"]["compare"]["pass"])
        self.assertFalse(res["installed"])
        self.assertTrue(os.path.isfile(os.path.join(out, "base_exports", "Old.json")))
        self.assertIn("--resume", calls[[i for i, c in enumerate(calls) if "convert_batch.py" in " ".join(c)][0]])
        with self.assertRaises(SystemExit):                                # never into an existing folder
            ib.main(argv)
        # a work staging that names a base model differently is refused (the base's names keep the FormID keys)
        ib.save(os.path.join(work, "editorids.json"), {"meshes/a.nif": "FO4Port_a"})
        out2 = os.path.join(t, "staging", "interiors_b01b")
        argv2 = [out2 if x == out else x for x in argv]
        ib.run = fake_run
        try:
            self.assertEqual(ib.main(argv2), 1)
        finally:
            ib.run = real
        self.assertIn("use a new --work", ib.load(os.path.join(out2, "result.json"))["error"])

    def test_prev_batch_seeds_the_ids_and_must_compare_clean(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        t = tmp.name
        base = os.path.join(t, "base")
        os.makedirs(base)
        OWN = 0x01000000
        tool = BatchToolTests()
        with open(os.path.join(base, "FO4Port.esm"), "wb") as f:
            f.write(tool.plugin())
        ids = {"STAT:FO4Port_a": 0x800, "CELL:FO4Port_Old": 0x801, "REFR:FO4Port_Old:1:Fallout4.esm": 0x802}
        ib.save(os.path.join(base, "formids.json"), ids)
        ib.save(os.path.join(base, "doors.json"), {"doors": []})
        ib.save(os.path.join(base, "Old.json"), {"cell": "Old", "refs": []})
        plan = os.path.join(t, "plan.json")
        ib.save(plan, {"batches": [
            {"archives_gb_est": 1.0, "work_staging_gb_est": 2.0, "cells": [{"editor_id": "One"}]},
            {"archives_gb_est": 1.5, "work_staging_gb_est": 3.0, "cells": [{"editor_id": "Two"}]}]})
        work = os.path.join(t, "work")
        one = rec(b"CELL", OWN | 0x850, [(b"EDID", b"FO4Port_One\0"), (b"DATA", struct.pack("<I", 1))])
        two = rec(b"CELL", OWN | 0x851, [(b"EDID", b"FO4Port_Two\0"), (b"DATA", struct.pack("<I", 1))])
        seeds, renumber = [], [False]

        def fake_run(cmd, log, env=None, cwd=None):
            joined = " ".join(cmd)
            if "export" in cmd and cmd[0] == "dotnet":
                ib.save(cmd[-1], {"cell": cmd[-2], "refs": []})
            elif "convert_batch.py" in joined:
                ib.save(os.path.join(work, "manifest.json"), {"items": [], "failures": []})
            elif "port_promote.py" in joined:
                ib.save(cmd[cmd.index("--out") + 1], {})
            elif "locations" in cmd and cmd[0] == "dotnet":
                ib.save(cmd[4], {"schema_version": 1, "cells": {c: {"cell_data": {"flags": 1, "name": None}, "location": None,
                                                                     "encounter_zone": None} for c in cmd[5:]}})
            elif cmd[0] == "dotnet":
                raw = cmd[2]
                seed = ib.load(os.path.join(raw, "formids.json"))
                seeds.append(seed)
                second = "CELL:FO4Port_One" in seed
                extra = [one, two] if second else [one]
                if second and renumber[0]:
                    extra = [rec(b"CELL", OWN | 0x852, [(b"EDID", b"FO4Port_One\0"), (b"DATA", struct.pack("<I", 1))]), two]
                # the root LCTN every batch writes: batch 1 allocates it, batch 2 must find it in the seed and keep it
                root_id = seed.get("LCTN:FO4Port_InteriorsLocation", 0x8F0)
                root = rec(b"LCTN", OWN | root_id, [(b"EDID", b"FO4Port_InteriorsLocation\0"), (b"PNAM", struct.pack("<I", 0x01B736))])
                with open(os.path.join(raw, "FO4Port.esm"), "wb") as f:
                    f.write(tool.plugin(extra=extra, xlcn=OWN | root_id, lctn=[root]))
                got = dict(seed, **{"CELL:FO4Port_One": 0x852 if renumber[0] else 0x850, "LCTN:FO4Port_InteriorsLocation": root_id})
                if second:
                    got["CELL:FO4Port_Two"] = 0x851
                ib.save(os.path.join(raw, "formids.json"), got)
                open(log, "a").close()
            elif "vmad_patch.py" in joined and cmd[2] == "port":
                dst = cmd[cmd.index("--out") + 1]
                os.makedirs(dst)
                for n in ("FO4Port.esm", "formids.json"):
                    shutil.copyfile(os.path.join(cmd[cmd.index("--port") + 1], n), os.path.join(dst, n))
            return 0, 0.1

        with open(os.path.join(t, "Fallout4.esm"), "wb") as f:           # the source the batches are pinned to (X8)
            f.write(b"TES4 fallout 4")
        with open(os.path.join(t, "Fallout4 - Meshes.ba2"), "wb") as f:
            f.write(b"BTDX")

        def build(n, out, prev=None, extra=(), pack=False):
            argv = ["build", "--plan", plan, "--batch", str(n), "--base", base, "--base-exports", base,
                    "--core", t, "--work", work, "--out", out, "--fo4-data", t, "--starfield", t,
                    "--content-resources", "c", "--texconv", "x", "--collision-template", "t", "--fo4export", "e",
                    "--pluginspike", "p", "--jobs", "1", "--min-free-gb", "0"] + (["--prev", prev] if prev else []) \
                + ([] if pack else ["--no-pack"]) + list(extra)
            real, ib.run = ib.run, fake_run
            real_pack, ib.deploy_starfield.build_archive = ib.deploy_starfield.build_archive, PackAndSourcesTests.fake_pack
            try:
                return ib.main(argv)
            finally:
                ib.run, ib.deploy_starfield.build_archive = real, real_pack

        b1, b2, b2x = (os.path.join(t, "staging", n) for n in ("interiors_b01", "interiors_b02", "interiors_b02x"))
        self.assertEqual(build(1, b1), 0)
        self.assertEqual(seeds[-1], ids)                                  # batch 1 starts from the base map
        r1 = ib.load(os.path.join(b1, "result.json"))
        self.assertEqual(r1["sources"]["plugins"], {"Fallout4.esm": {"sha256": ib.sha256(os.path.join(t, "Fallout4.esm")), "bytes": 14}})
        self.assertEqual(list(r1["sources"]["archives"]), ["Fallout4 - Meshes.ba2"])
        self.assertEqual(r1["steps"]["sources"], {"plugins": 1, "archives": 1, "allowed_change": None, "added": None, "work": "new", "work_history": None, "work_retired": None})
        # the work staging now carries the pins its exports were made from (X8), and what each export was made from
        rec1 = ib.load(os.path.join(work, "exports", "sources.json"))
        self.assertEqual((rec1["sources"], rec1["cells"], rec1["history"]), (r1["sources"], {"One": ["Fallout4.esm"]}, []))
        self.assertEqual(r1["install"], {"files": ["FO4Port.esm"], "plugins_txt": ["FO4Port.esm"]})   # --no-pack: the plugin only
        # the base exports the batch rebuilt its base cells from are pinned; a --prev pinned to other ones is refused
        self.assertEqual(r1["pins"]["base_exports"], {c: ib.sha256(os.path.join(base, c + ".json")) for c in ib.base_cells(base)})
        self.assertTrue(r1["pins"]["base_exports"])
        first = os.path.join(base, ib.base_cells(base)[0] + ".json")
        with open(first, "rb") as f:
            kept = f.read()
        with open(first, "ab") as f:
            f.write(b" ")
        with self.assertRaisesRegex(SystemExit, "--base-exports .* differs from the exports --prev was built from"):
            build(2, os.path.join(t, "staging", "interiors_b02e"), prev=b1)
        self.assertFalse(os.path.exists(os.path.join(t, "staging", "interiors_b02e")))
        with open(first, "wb") as f:
            f.write(kept)
        # batch 2 packed (Archive2 faked), with textures split at a tiny limit: two parts, one companion plugin
        for n, size in (("a.dds", 40), ("b.dds", 40), ("c.dds", 30)):
            os.makedirs(os.path.join(work, "textures"), exist_ok=True)
            with open(os.path.join(work, "textures", n), "wb") as f:
                f.write(b"x" * size)
        limit = ib.ARCHIVE_LIMIT
        ib.ARCHIVE_LIMIT = 100
        try:
            self.assertEqual(build(2, b2, prev=b1, pack=True), 0)
        finally:
            ib.ARCHIVE_LIMIT = limit
        self.assertEqual(ib.load(os.path.join(b2, "result.json"))["steps"]["sources"]["work"], "match")   # pinned by batch 1
        self.assertEqual(seeds[-1]["CELL:FO4Port_One"], 0x850)            # batch 2 starts from batch 1's map
        self.assertEqual(seeds[-1]["LCTN:FO4Port_InteriorsLocation"], 0x8F0)   # and the LCTN key rides the chain
        r2 = ib.load(os.path.join(b2, "result.json"))
        self.assertEqual([p["archive"] for p in r2["steps"]["pack"]["parts"]], ["FO4Port - Textures.ba2", "FO4PortTextures2 - Textures.ba2"])
        self.assertEqual(r2["install"], {"files": ["FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2",
                                                   "FO4PortTextures2.esm", "FO4PortTextures2 - Textures.ba2"],
                                         "plugins_txt": ["FO4Port.esm", "FO4PortTextures2.esm"]})
        self.assertEqual(sorted(r2["steps"]["pack"]["sha256"]), sorted(r2["install"]["files"][1:]))
        with open(os.path.join(b2, "README.txt"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("  port\\FO4PortTextures2 - Textures.ba2\n", readme)
        self.assertIn("*FO4Port.esm\n  *FO4PortTextures2.esm\n", readme)
        self.assertEqual(ib.load(os.path.join(b2, "port", "textures_parts.json"))["assignment"], {"a.dds": 0, "b.dds": 0, "c.dds": 1})
        self.assertTrue(r2["steps"]["compare_prev"]["pass"])
        self.assertEqual(r2["steps"]["compare_prev"]["records"]["changed"], {})   # batch 1's LCTN and XLCN unchanged
        self.assertEqual(r2["steps"]["compare"]["records"]["changed"], {"CELL": 1})   # the base cell gained its XLCN
        self.assertEqual(r2["steps"]["compare"]["records"]["added"], {"CELL": 2, "LCTN": 1})
        self.assertEqual(ib.load(os.path.join(b2, "plugin", "locations.json"))["cells"]["Old"]["cell_data"]["flags"], 1)
        self.assertTrue(os.path.isfile(os.path.join(b2, "port", "compare_prev.json")))
        renumber[0] = True                                                # batch 1's cell moved: the batch fails
        self.assertEqual(build(2, b2x, prev=b1), 1)
        self.assertFalse(ib.load(os.path.join(b2x, "result.json"))["steps"]["compare_prev"]["pass"])
        with self.assertRaises(SystemExit):                               # a failed batch is no --prev
            build(2, os.path.join(t, "staging", "interiors_b02y"), prev=b2x)
        with self.assertRaisesRegex(SystemExit, "batch 2 needs --prev"):  # a later batch grows the one before it
            build(2, os.path.join(t, "staging", "interiors_b02n"))
        with self.assertRaisesRegex(SystemExit, "not a passing build of batch 2"):   # ... exactly that one
            ib.check_prev(argparse.Namespace(prev=b1, base=base), 3)
        plug = os.path.join(b1, "port", "FO4Port.esm")                 # ... and its plugin as it passed
        with open(plug, "rb") as f:
            kept_plugin = f.read()
        with open(plug, "ab") as f:
            f.write(b"x")
        with self.assertRaisesRegex(SystemExit, "is not the plugin that build passed with"):
            ib.check_prev(argparse.Namespace(prev=b1, base=base), 2)
        with open(plug, "wb") as f:
            f.write(kept_plugin)
        # X8: a --prev built from another Fallout4.esm is refused, unless --allow-source-change, which is recorded
        renumber[0] = False
        with open(os.path.join(t, "Fallout4.esm"), "wb") as f:
            f.write(b"TES4 fallout 4 patched")
        with self.assertRaisesRegex(SystemExit, "--prev was built from other game files .*Fallout4.esm sha256"):
            build(2, os.path.join(t, "staging", "interiors_b02z"), prev=b1)
        self.assertFalse(os.path.exists(os.path.join(t, "staging", "interiors_b02z")))
        b2w = os.path.join(t, "staging", "interiors_b02w")
        os.makedirs(os.path.join(work, ".checkpoints"), exist_ok=True)
        with open(os.path.join(work, ".checkpoints", "old.json"), "w") as f:
            f.write("{}")
        self.assertEqual(build(2, b2w, prev=b1, extra=["--allow-source-change"]), 0)
        r2w = ib.load(os.path.join(b2w, "result.json"))
        allowed = r2w["steps"]["sources"]["allowed_change"]
        self.assertEqual(list(allowed), ["--prev", "--work"])             # the work staging's exports came from the old file too
        self.assertTrue(allowed["--prev"][0].startswith("Fallout4.esm sha256 "))
        self.assertEqual(allowed["--work"], allowed["--prev"])
        self.assertEqual(r2w["steps"]["sources"]["work"], "changed")
        self.assertEqual(r2w["steps"]["sources"]["work_history"], [{"batch": "interiors_b02w", "status": "changed", "differences": allowed["--work"]}])
        # nothing the staging cached from the old file reaches the build: its exports (and checkpoints, when it has
        # any) are moved aside, not deleted, and every cell is exported again
        retired = r2w["steps"]["sources"]["work_retired"]
        self.assertTrue(retired and retired[0].startswith("exports ("))
        stale = os.path.join(work, "stale-interiors_b02w", "exports")
        self.assertTrue(os.listdir(stale))
        self.assertEqual(retired[1:], [".checkpoints"])
        self.assertTrue(os.path.isfile(os.path.join(work, "stale-interiors_b02w", ".checkpoints", "old.json")))
        self.assertEqual(sorted(n for n in os.listdir(os.path.join(work, "exports")) if n != "sources.json"), sorted(os.listdir(stale)))
        # ... and the override re-pins the work staging to the patched file, so the next build over it matches, but the
        # allowed change stays on the staging's record: every later build's result.json says it happened
        wrec = ib.load(os.path.join(work, "exports", "sources.json"))
        self.assertEqual((wrec["sources"], wrec["history"]), (r2w["sources"], r2w["steps"]["sources"]["work_history"]))
        # a --base that is a batch's own stage (its result.json carries sources) is checked the same way; the installed
        # doors staging has no record and is never refused for one
        ib.save(os.path.join(base, "result.json"), {"sources": r1["sources"]})
        with self.assertRaisesRegex(SystemExit, "--base was built from other game files"):
            build(1, os.path.join(t, "staging", "interiors_b01v"))
        os.remove(os.path.join(base, "result.json"))
        self.assertEqual(build(1, os.path.join(t, "staging", "interiors_b01u")), 0)
        r1u = ib.load(os.path.join(t, "staging", "interiors_b01u", "result.json"))["steps"]["sources"]
        self.assertEqual(r1u["work"], "match (changed by interiors_b02w)")            # sticky: the staging was once re-pinned
        self.assertEqual(r1u["work_history"], r2w["steps"]["sources"]["work_history"])
        self.assertIsNone(r1u["allowed_change"])
        # a work staging pinned to other game files is refused like a --prev: the cached exports and checkpoints would
        # silently come from the other files while result.json pins the current ones
        with open(os.path.join(t, "Fallout4.esm"), "wb") as f:
            f.write(b"TES4 fallout 4 patched again")
        with self.assertRaisesRegex(SystemExit, "--work .* was built from other game files .*Fallout4.esm sha256 .*refusing to reuse"):
            build(1, os.path.join(t, "staging", "interiors_b01t"))
        self.assertFalse(os.path.exists(os.path.join(t, "staging", "interiors_b01t")))
        # a staging used before the pins (an export, no sources.json) is adopted; the adoption sticks to its record, so
        # the next build over it says so instead of "match", and the adopting build's own label is the plain status
        work = os.path.join(t, "work2")                                   # the build closure reads this name
        os.makedirs(os.path.join(work, "exports"))
        ib.save(os.path.join(work, "exports", "Stray.json"), {"cell": "Stray", "refs": []})
        self.assertEqual(build(1, os.path.join(t, "staging", "interiors_b01s")), 0)
        r1s = ib.load(os.path.join(t, "staging", "interiors_b01s", "result.json"))["steps"]["sources"]
        self.assertEqual((r1s["work"], r1s["work_history"]), ("adopted", [{"batch": "interiors_b01s", "status": "adopted", "differences": []}]))
        self.assertEqual(build(1, os.path.join(t, "staging", "interiors_b01r")), 0)
        r1r = ib.load(os.path.join(t, "staging", "interiors_b01r", "result.json"))["steps"]["sources"]
        self.assertEqual((r1r["work"], r1r["work_history"]), ("match (adopted by interiors_b01s)", r1s["work_history"]))
        self.assertEqual(ib.load(os.path.join(work, "exports", "sources.json"))["cells"], {"One": ["Fallout4.esm"]})   # the stray export is not recorded as this build's

    def test_dlc_cells_export_from_their_plugin_with_the_master(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dlc = os.path.join(tmp.name, "dlcdata")
        os.makedirs(dlc)
        open(os.path.join(dlc, "DLCRobot.esm"), "wb").close()
        plan = {"batches": [{"cells": [{"editor_id": "Old", "formkey": "000001:Fallout4.esm"}]},
                            {"cells": [{"editor_id": "DLC01Lair01", "formkey": "0008A3:DLCRobot.esm"},
                                       {"editor_id": "DLC03Gone", "formkey": "000001:DLCCoast.esm"}]}]}
        self.assertEqual(ib.cell_plugins(plan, 1), {})
        self.assertEqual(ib.cell_plugins(plan, 2), {"DLC01Lair01": ["Fallout4.esm", "DLCRobot.esm"], "DLC03Gone": ["Fallout4.esm", "DLCCoast.esm"]})
        self.assertEqual(ib.plugins_from(plan, 2, None), "formkey")
        a = argparse.Namespace(fo4export="Fo4Export.dll", fo4_data=os.path.join(tmp.name, "Data"), dlc_data=[dlc])
        calls = []

        def fake_run(cmd, log, env=None, cwd=None):
            calls.append(cmd)
            with open(cmd[-1], "w") as f:
                f.write("{}")
            return 0, 0.1
        real, ib.run = ib.run, fake_run
        try:
            out = os.path.join(tmp.name, "exports")
            os.makedirs(out)
            self.assertEqual(ib.export_cell(a, "DLC01Lair01", out, os.path.join(tmp.name, "x.log"), ["Fallout4.esm", "DLCRobot.esm"])[1], 0)
            self.assertEqual(calls[-1][2:5], [os.path.join(dlc, "DLCRobot.esm"), "--master", os.path.join(a.fo4_data, "Fallout4.esm")])
            self.assertEqual(ib.export_cell(a, "Old", out, os.path.join(tmp.name, "x.log"))[1], 0)
            self.assertEqual(calls[-1][2:4], [os.path.join(a.fo4_data, "Fallout4.esm"), "export"])
            self.assertEqual(ib.export_cell(a, "Old2", out, os.path.join(tmp.name, "x.log"), ["Fallout4.esm"])[1], 0)
            self.assertEqual(calls[-1][2:4], [os.path.join(a.fo4_data, "Fallout4.esm"), "export"])
            n = len(calls)                                                      # a DLC that is not installed: no run
            self.assertEqual(ib.export_cell(a, "DLC03Gone", out, os.path.join(tmp.name, "x.log"), ["Fallout4.esm", "DLCCoast.esm"])[1], 2)
            self.assertEqual(len(calls), n)
            # a Fallout4.esm cell two DLCs override: the last plugin, then the masters in load order (Fo4Export's order)
            open(os.path.join(dlc, "DLCworkshop01.esm"), "wb").close()
            fo4 = os.path.join(a.fo4_data, "Fallout4.esm")
            self.assertEqual(ib.export_sources(a, ["Fallout4.esm", "DLCRobot.esm", "DLCworkshop01.esm"]),
                             ([os.path.join(dlc, "DLCworkshop01.esm"), "--master", fo4, "--master", os.path.join(dlc, "DLCRobot.esm")], None))
            self.assertEqual(ib.export_sources(a, None), ([fo4], None))
            self.assertEqual(ib.export_sources(a, ["DLCRobot.esm"]), ([os.path.join(dlc, "DLCRobot.esm"), "--master", fo4], None))
        finally:
            ib.run = real
        # cell_plugins: the plan row's `plugins` (the census's) names every plugin that holds a Fallout4.esm cell a DLC
        # overrides; a plan without the key reads the census row of the same formkey; without a census the formkey's
        # owner alone (recorded as "formkey": the override is missed)
        census = {"cells": [{"editor_id": "Factory", "formkey": "04280D:Fallout4.esm", "plugins": ["Fallout4.esm", "DLCRobot.esm"]},
                            {"editor_id": "Plain", "formkey": "000010:Fallout4.esm", "plugins": ["Fallout4.esm"]},
                            {"editor_id": "DLC01Lair01", "formkey": "0008A3:DLCRobot.esm", "plugins": ["DLCRobot.esm"]}]}
        old_plan = {"batches": [{"cells": [{"editor_id": "Factory", "formkey": "04280D:Fallout4.esm"}, {"editor_id": "Plain", "formkey": "000010:Fallout4.esm"}]},
                                {"cells": [{"editor_id": "DLC01Lair01", "formkey": "0008A3:DLCRobot.esm"}]}]}
        self.assertEqual(ib.cell_plugins(old_plan, 2), {"DLC01Lair01": ["Fallout4.esm", "DLCRobot.esm"]})
        self.assertEqual(ib.cell_plugins(old_plan, 2, census), {"Factory": ["Fallout4.esm", "DLCRobot.esm"], "DLC01Lair01": ["Fallout4.esm", "DLCRobot.esm"]})
        self.assertEqual(ib.cell_plugins(old_plan, 1, census), {"Factory": ["Fallout4.esm", "DLCRobot.esm"]})
        self.assertEqual(ib.plugins_from(old_plan, 1, census), "census")
        new_plan = ibs.plan({"cells": [dict(crow("Factory", "04280D:Fallout4.esm"), plugins=["Fallout4.esm", "DLCRobot.esm"]),
                                       dict(crow("Plain", "000010:Fallout4.esm"), plugins=["Fallout4.esm"])],
                             "worlds": {"a": "Commonwealth"}}, {"backlog": [], "second_hop": []}, min_cells=1)
        self.assertEqual([c["plugins"] for c in new_plan["batches"][0]["cells"]], [["Fallout4.esm", "DLCRobot.esm"], ["Fallout4.esm"]])
        self.assertEqual(ib.cell_plugins(new_plan, 1), {"Factory": ["Fallout4.esm", "DLCRobot.esm"]})
        self.assertEqual(ib.plugins_from(new_plan, 1, None), "plan")
        # the pins follow: a batch with an overridden cell pins the DLC plugin too
        os.makedirs(a.fo4_data)
        open(os.path.join(a.fo4_data, "Fallout4.esm"), "wb").close()
        self.assertEqual(sorted(ib.source_pins(a, new_plan, 1)["plugins"]), ["DLCRobot.esm", "Fallout4.esm"])

    def test_an_export_that_writes_nothing_is_a_failed_export(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        a = argparse.Namespace(fo4_data=tmp.name, fo4export="Fo4Export.dll", dlc_data=tmp.name)
        log = os.path.join(tmp.name, "export.log")
        real = ib.run
        for wrote in (None, b""):
            def fake_run(cmd, log_, env=None, cwd=None):
                if wrote is not None:
                    with open(cmd[-1], "wb") as f:
                        f.write(wrote)
                return 0, 0.1
            ib.run = fake_run
            try:
                cell, rc, _s = ib.export_cell(a, "Lobby", tmp.name, log)
            finally:
                ib.run = real
            self.assertEqual((cell, rc), ("Lobby", 3))
            self.assertFalse(os.path.exists(os.path.join(tmp.name, "Lobby.json")))
            with open(log + ".Lobby", encoding="utf-8") as f:
                self.assertIn("missing or empty", f.read())

    def test_disk_need_counts_what_the_batch_adds(self):
        plan = {"batches": [{"archives_gb_est": 2.9, "work_staging_gb_est": 5.9},
                            {"archives_gb_est": 3.8, "work_staging_gb_est": 7.6}]}
        self.assertEqual(ib.disk_need(plan, 0, False), 0.0)
        self.assertEqual(ib.disk_need(plan, 2, True), 5.5)                # 3.8 packed + 1.7 work growth
        self.assertEqual(ib.disk_need(plan, 2, False), 11.4)              # a new work staging holds everything

    def test_archive_check_fails_an_archive_at_the_limit_and_warns_near_it(self):
        ok = ib.archive_check({"Main": 230_547_923, "Textures": 3_590_442_691})   # batch 4's measured sizes
        self.assertTrue(ok["pass"])
        self.assertEqual(ok["near_limit"], [])
        near = ib.archive_check({"Textures": int(ib.ARCHIVE_LIMIT * 0.95)})
        self.assertTrue(near["pass"])
        self.assertEqual(near["near_limit"], ["Textures"])
        over = ib.archive_check({"Main": 1, "Textures": ib.ARCHIVE_LIMIT})
        self.assertFalse(over["pass"])
        self.assertIn("Textures", over["problem"])

    def test_removed_causes(self):
        old = {"STAT:FO4Port_Chair": 0x800, "DOOR:FO4Port_VaultDoor": 0x801, "FURN:FO4Port_furn_1": 0x802}
        new = dict(old, **{"STAT:FO4Port_chair": 0x900, "STAT:FO4Port_vaultdoor": 0x901})
        recs = {0x01000900: None, 0x01000901: None}
        why = ib.removed_causes(old, new, ["STAT 01000800", "DOOR 01000801", "FURN 01000802"], recs)
        self.assertEqual(why["counts"], {"gone": 1, "renamed_case": 1, "retyped": 1})
        self.assertEqual(why["first"]["retyped"], ["DOOR:FO4Port_VaultDoor -> STAT:FO4Port_vaultdoor"])


class PackAndSourcesTests(unittest.TestCase):
    """The textures split over companion plugins (X3) and the game-file pins (X8), with Archive2 faked: a fake packer
    writes "BTDX" plus every packed file's bytes, so an archive's size is its part's loose size plus 4."""

    # Mutagen.Bethesda.Starfield 0.55.0-alpha.67 writing `new StarfieldMod(key, StarfieldRelease.Starfield)` with
    # HeaderFlag.Master and no records (verified: scratchpad/probe-companion, `dotnet9 run`, both companions 42 bytes).
    PROBE_HEX = "544553341200000001000000000000000000000040020000484544520c008fc2753f0000000000000000"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.t = self.tmp.name
        self.limit, self.warn = ib.ARCHIVE_LIMIT, ib.ARCHIVE_WARN
        self.addCleanup(self._restore)

    def _restore(self):
        ib.ARCHIVE_LIMIT, ib.ARCHIVE_WARN = self.limit, self.warn

    @staticmethod
    def fake_pack(a, out, folders, fmt, compression="Default"):
        body = b"BTDX"
        for d in folders:
            root = os.path.join(a.staging, d)
            if os.path.isdir(root):
                for dp, _dn, fs in sorted(os.walk(root)):
                    for f in sorted(fs):
                        with open(os.path.join(dp, f), "rb") as h:
                            body += h.read()
        with open(out, "wb") as h:
            h.write(body)

    def test_plan_parts_is_deterministic_greedy_and_keeps_previous_parts(self):
        sizes = {"b.dds": 40, "A.dds": 30, "c/d.dds": 50, "e.dds": 10}
        # sorted by path (case-insensitive), greedy, a file never split: A+b (70) | c/d (50) | e... no: e fits part 1
        self.assertEqual(ib.plan_parts(sizes, 90), [["A.dds", "b.dds", "e.dds"], ["c/d.dds"]])
        self.assertEqual(ib.plan_parts(sizes, 90), ib.plan_parts(dict(reversed(list(sizes.items()))), 90))
        self.assertEqual(ib.plan_parts(sizes, 1000), [["A.dds", "b.dds", "c/d.dds", "e.dds"]])
        self.assertEqual(ib.plan_parts({}, 90), [])
        # a file keeps the part the previous batch gave it while that part has room; new files take the lowest part with room
        prev = {"c/d.dds": 0, "A.dds": 1}
        self.assertEqual(ib.plan_parts(sizes, 90, prev), [["b.dds", "c/d.dds"], ["A.dds", "e.dds"]])
        # ... and moves only when its old part filled up around it (c/d's part 0 has no room once new files take it)
        grown = dict(sizes, **{"aa.dds": 45})
        self.assertEqual(ib.plan_parts(grown, 90, {"c/d.dds": 0, "A.dds": 0, "b.dds": 1}),
                         [["A.dds", "c/d.dds", "e.dds"], ["aa.dds", "b.dds"]])
        with self.assertRaisesRegex(ValueError, "larger than one archive part"):
            ib.plan_parts({"huge.dds": 91}, 90)
        self.assertEqual(ib.pack_ratio(None), 1.0)
        self.assertEqual(ib.pack_ratio({"steps": {"pack": {"parts": [{"bytes": 50, "loose_bytes": 100}, {"bytes": 80, "loose_bytes": 100}]}}}), 0.8)
        self.assertEqual(ib.pack_ratio({"steps": {"pack": {"parts": [{"bytes": 300, "loose_bytes": 100}]}}}), 3.0)   # plans tighter
        legacy = {"steps": {"pack": {"bytes": {"FO4Port - Main.ba2": 900, "FO4Port - Textures.ba2": 40}}}}   # batches 0-4
        self.assertEqual(ib.pack_ratio(legacy, 100), 0.4)
        self.assertEqual(ib.pack_ratio(legacy), 1.0)
        self.assertEqual(ib.pack_ratio({"steps": {"pack": {"bytes": {"FO4Port - Textures.ba2": 400}}}}, 100), 1.0)
        # a part emptied by the previous assignment is dropped and the later ones move down: no empty part anywhere,
        # at the tail or in the middle (an empty middle part would be packed from a folder that was never made)
        self.assertEqual(ib.plan_parts({"a.dds": 10, "c.dds": 10}, 100, {"a.dds": 0, "c.dds": 2}), [["a.dds"], ["c.dds"]])
        self.assertEqual(ib.plan_parts({"a.dds": 10}, 100, {"a.dds": 2}), [["a.dds"]])
        self.assertNotIn([], ib.plan_parts({"a.dds": 10, "b.dds": 10, "c.dds": 10}, 15, {"a.dds": 0, "c.dds": 3}))

    def test_companion_plugin_bytes_match_the_mutagen_probe(self):
        b = ib.companion_plugin_bytes()
        self.assertEqual(b.hex(), self.PROBE_HEX)
        p = vp.Plugin(b)
        self.assertEqual((p.masters(), p.items, p.tes4.flags, struct.unpack_from("<H", p.tes4.header, 20)[0]), ([], [], 1, 576))
        self.assertEqual(p.hedr()[1:], (0, 0))
        self.assertEqual(ib.part_names(0), ("FO4Port - Textures.ba2", None))
        self.assertEqual(ib.part_names(2), ("FO4PortTextures3 - Textures.ba2", "FO4PortTextures3.esm"))
        for rel, want in (("port/FO4PortTextures2.esm", True), ("port/FO4PortTextures12 - Textures.ba2", True),
                          ("port/FO4Port - Textures.ba2", True), ("port/FO4PortTextures2 - Main.ba2", False),
                          ("plugin/FO4PortTextures2.esm", False), ("port/x/FO4PortTextures2.esm", False)):
            self.assertEqual(ib.is_superseded(rel), want, rel)

    def _work(self, files, name="work"):
        work = os.path.join(self.t, name)
        for rel, n in files.items():
            p = os.path.join(work, "textures", *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(bytes([n % 251]) * n)
        os.makedirs(os.path.join(work, "meshes"), exist_ok=True)
        with open(os.path.join(work, "meshes", "m.mesh"), "wb") as f:
            f.write(b"mesh")
        return work

    def test_pack_splits_textures_into_companion_archives_and_keeps_the_assignment(self):
        ib.ARCHIVE_LIMIT, ib.ARCHIVE_WARN = 100, 0.9                       # cap 90 loose bytes per part
        work = self._work({"a.dds": 40, "b.dds": 40, "sub/c.dds": 30, "d.dds": 60})
        out1 = os.path.join(self.t, "interiors_b01")
        port1 = os.path.join(out1, "port")
        os.makedirs(port1)
        a = argparse.Namespace(starfield=self.t, work=work, out=out1)
        real = ib.deploy_starfield.build_archive
        ib.deploy_starfield.build_archive = self.fake_pack
        try:
            r1 = ib.pack(a, port1, None, None, os.path.join(out1, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        # a+b (80) | d (60) + sub/c (30 -> part 2 since 60+30 > 90)... sorted: a, b, d, sub/c: a+b=80, d -> part 1, sub/c: part 0? 80+30>90, part 1: 60+30=90 fits
        parts = [p["archive"] for p in r1["parts"]]
        self.assertEqual(parts, ["FO4Port - Textures.ba2", "FO4PortTextures2 - Textures.ba2"])
        self.assertEqual([p["files"] for p in r1["parts"]], [2, 2])
        self.assertEqual([p["loose_bytes"] for p in r1["parts"]], [80, 90])
        self.assertEqual([p["bytes"] for p in r1["parts"]], [84, 94])
        self.assertEqual([p["plugin"] for p in r1["parts"]], [None, "FO4PortTextures2.esm"])
        self.assertEqual(sorted(os.listdir(port1)), ["FO4Port - Main.ba2", "FO4Port - Textures.ba2", "FO4PortTextures2 - Textures.ba2",
                                                     "FO4PortTextures2.esm", "textures_parts.json"])
        self.assertFalse(os.path.exists(os.path.join(out1, "pack_parts")))   # the link trees are gone
        with open(os.path.join(port1, "FO4PortTextures2.esm"), "rb") as f:
            self.assertEqual(f.read().hex(), self.PROBE_HEX)
        self.assertEqual(sorted(r1["sha256"]), sorted(r1["bytes"]))
        self.assertEqual(sorted(r1["bytes"]), ["FO4Port - Main.ba2", "FO4Port - Textures.ba2", "FO4PortTextures2 - Textures.ba2", "FO4PortTextures2.esm"])
        self.assertEqual(r1["bytes"]["FO4PortTextures2.esm"], 42)
        self.assertEqual(r1["sha256"]["FO4Port - Main.ba2"], ib.sha256(os.path.join(port1, "FO4Port - Main.ba2")))
        self.assertTrue(r1["pass"])
        self.assertEqual(r1["near_limit"], ["FO4PortTextures2 - Textures.ba2"])   # 94 of 100: listed, not failed
        self.assertEqual((r1["ratio"], r1["cap_loose_bytes"], r1["moved"], r1["ratio_source"]), (1.0, 90, 0, "default"))
        self.assertEqual(r1["attempts"], [{"ratio": 1.0, "cap_loose_bytes": 90, "parts": 2, "over": []}])
        self.assertEqual(ib.load(os.path.join(port1, "textures_parts.json"))["assignment"],
                         {"a.dds": 0, "b.dds": 0, "d.dds": 1, "sub/c.dds": 1})
        self.assertEqual(ib.install_set(port1), {"files": ["FO4Port - Main.ba2", "FO4Port - Textures.ba2",
                                                           "FO4PortTextures2.esm", "FO4PortTextures2 - Textures.ba2"],
                                                 "plugins_txt": ["FO4PortTextures2.esm"]})   # no FO4Port.esm in this port folder
        # the next batch: a new texture joins, every old one keeps its part; the measured ratio (<1) widens the cap
        with open(os.path.join(work, "textures", "0first.dds"), "wb") as f:
            f.write(b"x" * 5)
        out2 = os.path.join(self.t, "interiors_b02")
        port2 = os.path.join(out2, "port")
        os.makedirs(port2)
        prev_result = {"steps": {"pack": {"parts": [{"bytes": 42, "loose_bytes": 80}, {"bytes": 47, "loose_bytes": 90}]}}}
        ib.deploy_starfield.build_archive = self.fake_pack
        try:
            r2 = ib.pack(argparse.Namespace(starfield=self.t, work=work, out=out2), port2, port1, prev_result, os.path.join(out2, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        self.assertAlmostEqual(r2["ratio"], 0.525)                        # the least packed part: 42 / 80
        self.assertEqual((r2["cap_loose_bytes"], r2["ratio_source"]), (int(90 / 0.525), "prev"))
        self.assertEqual(ib.load(os.path.join(port2, "textures_parts.json"))["assignment"],
                         {"0first.dds": 0, "a.dds": 0, "b.dds": 0, "d.dds": 1, "sub/c.dds": 1})   # kept, though one part would do now
        self.assertEqual(r2["moved"], 0)
        # a single part is packed straight from the work staging (no link tree), with no companion
        ib.ARCHIVE_LIMIT = 10_000
        out3 = os.path.join(self.t, "interiors_b03")
        os.makedirs(os.path.join(out3, "port"))
        ib.deploy_starfield.build_archive = self.fake_pack
        try:
            r3 = ib.pack(argparse.Namespace(starfield=self.t, work=work, out=out3), os.path.join(out3, "port"), None, None, os.path.join(out3, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        self.assertEqual(sorted(r3["bytes"]), ["FO4Port - Main.ba2", "FO4Port - Textures.ba2"])
        self.assertEqual(r3["parts"][0]["loose_bytes"], 175)
        # an unsplittable texture fails the step, which fails the batch
        ib.ARCHIVE_LIMIT = 50
        ib.deploy_starfield.build_archive = self.fake_pack
        try:
            with self.assertRaisesRegex(ValueError, "larger than one archive part"):
                ib.pack(argparse.Namespace(starfield=self.t, work=work, out=out3), os.path.join(out3, "port"), None, None, os.path.join(out3, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real

    def test_pack_replans_a_part_that_packs_over_the_limit_and_repacks_only_changed_parts(self):
        """The --prev's ratio is measured on its parts, not on the files this batch adds: when the new ones pack worse,
        the over-limit part is replanned with the measured ratio, parts whose file list did not change are not packed
        again, and the files that moved are counted."""
        ib.ARCHIVE_LIMIT, ib.ARCHIVE_WARN = 100, 0.9
        work = self._work({"p.dds": 80, "q.dds": 80, "r.dds": 80})
        out = os.path.join(self.t, "interiors_b05")
        port, prev_port = os.path.join(out, "port"), os.path.join(self.t, "interiors_b04", "port")
        os.makedirs(port)
        os.makedirs(prev_port)
        ib.save(os.path.join(prev_port, ib.PARTS), {"assignment": {"p.dds": 0, "q.dds": 1}})
        prev_result = {"steps": {"pack": {"parts": [{"bytes": 40, "loose_bytes": 80}, {"bytes": 40, "loose_bytes": 80}]}}}  # ratio 0.5
        calls = []

        def counting_pack(a, out_, folders, fmt, compression="Default"):
            calls.append(os.path.basename(out_))
            self.fake_pack(a, out_, folders, fmt, compression)              # the new file packs 1:1, so part 0 overshoots

        a = argparse.Namespace(starfield=self.t, work=work, out=out)
        real, ib.deploy_starfield.build_archive = ib.deploy_starfield.build_archive, counting_pack
        try:
            r = ib.pack(a, port, prev_port, prev_result, os.path.join(out, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        # attempt 1: cap 180 loose, p + r in part 0 (164 packed: over), q in part 1 (84); the measured ratio (the
        # least packed part's: 84/80 = 1.05) plans attempt 2 at cap 85: p | q | r, part 1 untouched
        self.assertTrue(r["pass"])
        self.assertEqual([(x["ratio"], x["cap_loose_bytes"], x["parts"], x["over"]) for x in r["attempts"]],
                         [(0.5, 180, 2, ["FO4Port - Textures.ba2"]), (1.05, 85, 3, [])])
        self.assertEqual((r["ratio"], r["cap_loose_bytes"], r["ratio_source"]), (1.05, 85, "prev"))
        self.assertEqual([p["files"] for p in r["parts"]], [1, 1, 1])
        self.assertEqual(calls.count("FO4PortTextures2 - Textures.ba2"), 1)
        self.assertEqual(calls.count("FO4Port - Textures.ba2"), 2)
        self.assertEqual(r["moved"], 0)                                   # p and q kept their parts; r is new
        self.assertEqual(ib.load(os.path.join(port, ib.PARTS))["assignment"], {"p.dds": 0, "q.dds": 1, "r.dds": 2})
        self.assertEqual(sorted(r["sha256"]), ["FO4Port - Main.ba2", "FO4Port - Textures.ba2", "FO4PortTextures2 - Textures.ba2",
                                              "FO4PortTextures2.esm", "FO4PortTextures3 - Textures.ba2", "FO4PortTextures3.esm"])
        self.assertEqual(sorted(os.listdir(port)), sorted(r["sha256"]) + ["textures_parts.json"])
        # --pack-ratio plans by the given ratio instead (first attempt right at 1.0, no replanning)
        out2 = os.path.join(self.t, "interiors_b06")
        os.makedirs(os.path.join(out2, "port"))
        ib.deploy_starfield.build_archive = self.fake_pack
        try:
            r2 = ib.pack(argparse.Namespace(starfield=self.t, work=work, out=out2, pack_ratio=1.0), os.path.join(out2, "port"),
                         port, {"steps": {"pack": r}}, os.path.join(out2, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        self.assertEqual((r2["ratio"], r2["ratio_source"], len(r2["attempts"]), r2["moved"]), (1.0, "--pack-ratio", 1, 0))
        # a file moves when its old part filled up around it (counted), and a part that packs over the limit after
        # every attempt fails the step with the reason
        out3 = os.path.join(self.t, "interiors_b07")
        os.makedirs(os.path.join(out3, "port"))
        ib.save(os.path.join(port, ib.PARTS), {"assignment": {"p.dds": 1, "q.dds": 1, "r.dds": 1}})   # 240 loose in one part
        ib.deploy_starfield.build_archive = self.fake_pack
        try:
            r3 = ib.pack(argparse.Namespace(starfield=self.t, work=work, out=out3, pack_ratio=1.0), os.path.join(out3, "port"),
                         port, None, os.path.join(out3, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        self.assertEqual((r3["moved"], r3["pass"]), (2, True))            # p stays in part 1 (becomes 0); q and r move
        # a packer whose output does not follow the loose bytes (any two files pack to the limit) is still over after
        # PACK_ATTEMPTS plans: the step fails with the attempts recorded, and the batch with it
        work4 = self._work({"a.dds": 10, "b.dds": 10, "c.dds": 10, "d.dds": 10}, "work4")

        def odd_pack(a, out_, folders, fmt, compression="Default"):
            n = sum(len(fs) for d in folders for _dp, _dn, fs in os.walk(os.path.join(a.staging, d)))
            with open(out_, "wb") as h:
                h.write(b"BTDX" + b"x" * (96 if n >= 2 else 6))

        out4 = os.path.join(self.t, "interiors_b08")
        os.makedirs(os.path.join(out4, "port"))
        ib.deploy_starfield.build_archive = odd_pack
        try:
            r4 = ib.pack(argparse.Namespace(starfield=self.t, work=work4, out=out4), os.path.join(out4, "port"),
                         None, None, os.path.join(out4, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real
        self.assertFalse(r4["pass"])
        self.assertEqual([(x["cap_loose_bytes"], x["parts"]) for x in r4["attempts"]], [(90, 1), (36, 2), (27, 2)])
        self.assertIn("packed worse than planned even after replanning", r4["problem"])
        # ... and a replanned cap no file fits says so, naming the attempts
        ib.ARCHIVE_LIMIT, ib.ARCHIVE_WARN = 100, 0.9
        work5 = self._work({"a.dds": 20}, "work5")
        out5 = os.path.join(self.t, "interiors_b09")
        os.makedirs(os.path.join(out5, "port"))
        ib.deploy_starfield.build_archive = odd_pack                       # one file packs to 10 bytes: never over
        try:
            self.assertTrue(ib.pack(argparse.Namespace(starfield=self.t, work=work5, out=out5), os.path.join(out5, "port"),
                                    None, None, os.path.join(out5, "build.log"))["pass"])
            ib.ARCHIVE_LIMIT = 10                                          # 10 >= the limit: over; the measured ratio 0.5 shrinks the cap under 20
            out6 = os.path.join(self.t, "interiors_b10")
            os.makedirs(os.path.join(out6, "port"))
            with self.assertRaisesRegex(ValueError, r"larger than one archive part .* after replanning"):
                ib.pack(argparse.Namespace(starfield=self.t, work=work5, out=out6, pack_ratio=0.2), os.path.join(out6, "port"),
                        None, None, os.path.join(out6, "build.log"))
        finally:
            ib.deploy_starfield.build_archive = real

    def test_install_set_orders_many_companions_by_number_and_link_tree_counts_copies(self):
        port = os.path.join(self.t, "port")
        os.makedirs(port)
        for n in ("FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2", "FO4PortTextures10.esm", "FO4PortTextures10 - Textures.ba2",
                  "FO4PortTextures2.esm", "FO4PortTextures2 - Textures.ba2", "FO4PortTextures3.esm", "FO4PortTextures3 - Textures.ba2",
                  "textures_parts.json", "compare.json"):
            with open(os.path.join(port, n), "wb") as f:
                f.write(b"x")
        self.assertEqual(ib.install_set(port), {
            "files": ["FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2", "FO4PortTextures2.esm", "FO4PortTextures2 - Textures.ba2",
                      "FO4PortTextures3.esm", "FO4PortTextures3 - Textures.ba2", "FO4PortTextures10.esm", "FO4PortTextures10 - Textures.ba2"],
            "plugins_txt": ["FO4Port.esm", "FO4PortTextures2.esm", "FO4PortTextures3.esm", "FO4PortTextures10.esm"]})
        # a volume that refuses hard links gets copies, counted
        work = self._work({"a.dds": 3, "s/b.dds": 4})
        tree = os.path.join(self.t, "tree")
        self.assertEqual(ib.link_tree(work, ["a.dds", "s/b.dds"], tree), 0)
        self.assertEqual(os.stat(os.path.join(tree, "textures", "a.dds")).st_nlink, 2)
        real_link = os.link

        def no_link(src, dst, **kw):
            raise OSError(18, "Invalid cross-device link")

        os.link = no_link
        try:
            self.assertEqual(ib.link_tree(work, ["a.dds", "s/b.dds"], os.path.join(self.t, "tree2")), 2)
        finally:
            os.link = real_link
        with open(os.path.join(self.t, "tree2", "textures", "s", "b.dds"), "rb") as f:
            self.assertEqual(f.read(), bytes([4]) * 4)

    def test_release_treats_companions_like_the_ports_archives(self):
        root, refs, arch, sf = (os.path.join(self.t, n) for n in ("staging", "refs", "archive", "Starfield"))
        os.makedirs(os.path.join(sf, "Data"))
        os.makedirs(refs)

        def stage(n, prev=None, companions=(2,), succ_sha_for=None):
            port = os.path.join(root, n, "port")
            os.makedirs(port)
            names = ["FO4Port - Main.ba2", "FO4Port - Textures.ba2"]
            for k in companions:
                names += [f"FO4PortTextures{k}.esm", f"FO4PortTextures{k} - Textures.ba2"]
            for f in names:
                with open(os.path.join(port, f), "wb") as h:
                    h.write(ib.companion_plugin_bytes() if f.endswith(".esm") else b"BTDX" + (n + f).encode())
            with open(os.path.join(port, "FO4Port.esm"), "wb") as h:
                h.write(n.encode())
            steps = {"compare_prev": {"prev": os.path.join(root, prev), "pass": True}} if prev else {}
            steps["pack"] = {"bytes": {f: os.path.getsize(os.path.join(port, f)) for f in names},
                             "sha256": {f: ib.sha256(os.path.join(port, f)) for f in (succ_sha_for if succ_sha_for is not None else names)}}
            ib.save(os.path.join(root, n, "result.json"), {"name": n, "installed": False, "pass": True, "steps": steps,
                                                           "pins": {"plugin": ib.sha256(os.path.join(port, "FO4Port.esm"))}})
            with open(os.path.join(root, n, "build.log"), "w", encoding="utf-8") as h:
                h.write("log of " + n)
            return os.path.join(root, n)

        b01 = stage("interiors_b01")
        b02 = stage("interiors_b02", "interiors_b01")
        self.assertEqual(ib.superseded_files(b01), ["port/FO4Port - Main.ba2", "port/FO4Port - Textures.ba2", "port/FO4Port.esm",
                                                    "port/FO4PortTextures2 - Textures.ba2", "port/FO4PortTextures2.esm"])
        # the companion archive installed keeps the stage (its plugin is the same 42 bytes in every stage: not a key)
        shutil.copyfile(os.path.join(b01, "port", "FO4PortTextures2 - Textures.ba2"), os.path.join(sf, "Data", "FO4PortTextures2 - Textures.ba2"))
        with self.assertRaisesRegex(ValueError, "FO4PortTextures2 - Textures.ba2 is the one installed"):
            ib.release(b01, "x", [refs], sf, b02, arch)
        os.remove(os.path.join(sf, "Data", "FO4PortTextures2 - Textures.ba2"))
        shutil.copyfile(os.path.join(b02, "port", "FO4PortTextures2.esm"), os.path.join(sf, "Data", "FO4PortTextures2.esm"))   # another stage's: identical, not a key
        rec = ib.release(b01, "superseded", [refs], sf, b02, arch)
        self.assertEqual(sorted(rec["archived"]), ["build.log", "result.json"])       # the companions: carried by b02
        self.assertEqual([os.path.basename(p) for p in ib.prune(root, 1, delete=False)], ["interiors_b01"])
        # a successor without a build-time sha256 for the companion, or whose companion archive changed, cannot stand in
        b03 = stage("interiors_b03", "interiors_b02", succ_sha_for=["FO4Port - Main.ba2", "FO4Port - Textures.ba2", "FO4PortTextures2.esm"])
        with self.assertRaisesRegex(ValueError, "no build-time sha256 for port/FO4PortTextures2 - Textures.ba2"):
            ib.release(b02, "x", [refs], sf, b03, arch)
        b04 = stage("interiors_b04", "interiors_b03")
        with open(os.path.join(b04, "port", "FO4PortTextures2 - Textures.ba2"), "ab") as h:
            h.write(b"!")
        with self.assertRaisesRegex(ValueError, "FO4PortTextures2 - Textures.ba2 is missing or not the one it packed"):
            ib.release(b03, "x", [refs], sf, b04, arch)
        # a successor that needed one part fewer lacks the stage's last companion: refused, conservatively
        b05 = stage("interiors_b05", "interiors_b04", companions=())
        with self.assertRaisesRegex(ValueError, "no build-time sha256 for port/FO4PortTextures2 - Textures.ba2"):
            ib.release(b04, "x", [refs], sf, b05, arch)
        # a release.json that lists a companion neither archived nor superseded would refuse; a companion is superseded
        rec = dict(rec, tree=dict(rec["tree"], **{"port/FO4PortTextures3.esm": [42, "0" * 64]}))
        ib.archived_check(rec)
        with self.assertRaisesRegex(ValueError, "not archived: port/FO4PortTextures3 - Main.ba2"):
            ib.archived_check(dict(rec, tree=dict(rec["tree"], **{"port/FO4PortTextures3 - Main.ba2": [1, "0" * 64]})))

    def test_source_pins_and_changes(self):
        data, dlc = os.path.join(self.t, "Data"), os.path.join(self.t, "dlc")
        os.makedirs(data)
        os.makedirs(dlc)
        for d, names in ((data, ["Fallout4.esm", "Fallout4 - Meshes.ba2", "Fallout4 - Textures1.ba2"]), (dlc, ["DLCRobot.esm", "DLCRobot - Main.ba2"])):
            for n in names:
                with open(os.path.join(d, n), "wb") as f:
                    f.write(n.encode())
        plan = {"batches": [{"cells": [{"editor_id": "Old", "formkey": "000001:Fallout4.esm"}]},
                            {"cells": [{"editor_id": "Lair", "formkey": "0008A3:DLCRobot.esm"}, {"editor_id": "Gone", "formkey": "000001:DLCCoast.esm"}]}]}
        a = argparse.Namespace(fo4_data=data, dlc_data=[dlc])
        s1 = ib.source_pins(a, plan, 1)
        self.assertEqual(sorted(s1["plugins"]), ["Fallout4.esm"])
        self.assertEqual(s1["plugins"]["Fallout4.esm"], {"sha256": ib.sha256(os.path.join(data, "Fallout4.esm")), "bytes": 12})
        self.assertEqual(sorted(s1["archives"]), ["DLCRobot - Main.ba2", "Fallout4 - Meshes.ba2", "Fallout4 - Textures1.ba2"])
        self.assertEqual(set(s1["archives"]["Fallout4 - Meshes.ba2"]), {"bytes", "mtime", "folder"})
        self.assertEqual(s1["archives"]["DLCRobot - Main.ba2"]["folder"], os.path.abspath(dlc))
        s2 = ib.source_pins(a, plan, 2)
        self.assertEqual(sorted(s2["plugins"]), ["DLCCoast.esm", "DLCRobot.esm", "Fallout4.esm"])
        self.assertIsNone(s2["plugins"]["DLCCoast.esm"])                   # not installed: pinned as missing
        self.assertEqual(ib.source_changes(s1, s1), [])
        # the first batch with a DLC cell pins the DLC plugin for the first time: not a change (nothing the --prev read
        # differs), listed by source_added instead; the DLC plugin pinned before and gone now is one; a changed Fallout4.esm too
        self.assertEqual(ib.source_changes(s1, s2), [])
        self.assertEqual(ib.source_added(s1, s2), ["DLCCoast.esm", "DLCRobot.esm"])
        self.assertEqual(ib.source_added(s2, s1), [])
        self.assertEqual(ib.source_changes(s2, s1), ["DLCRobot.esm sha256 " + s2["plugins"]["DLCRobot.esm"]["sha256"] + " -> None"])
        with open(os.path.join(data, "Fallout4.esm"), "wb") as f:
            f.write(b"patched")
        diff = ib.source_changes(s1, ib.source_pins(a, plan, 1))
        self.assertEqual(len(diff), 1)
        self.assertTrue(diff[0].startswith("Fallout4.esm sha256 "))
        # a BA2 that changed size or mtime differs too; one only one side has differs by bytes only (not twice)
        os.utime(os.path.join(data, "Fallout4 - Meshes.ba2"), (1, 1))
        diff = ib.source_changes(s1, ib.source_pins(a, plan, 1))
        self.assertEqual(len(diff), 2)
        self.assertTrue(diff[1].startswith("Fallout4 - Meshes.ba2 mtime "), diff)
        os.remove(os.path.join(dlc, "DLCRobot - Main.ba2"))
        self.assertIn("DLCRobot - Main.ba2 bytes 19 -> None", ib.source_changes(s1, ib.source_pins(a, plan, 1)))
        # a BA2 added to a folder since (a DLC installed) is pinned for the first time: added, not changed
        with open(os.path.join(dlc, "DLCRobot - Textures.ba2"), "wb") as f:
            f.write(b"BTDX")
        s3 = ib.source_pins(a, plan, 1)
        self.assertNotIn("DLCRobot - Textures.ba2", " ".join(ib.source_changes(s1, s3)))
        self.assertEqual(ib.source_added(s1, s3), ["DLCRobot - Textures.ba2"])
        # base_sources: a stage's port folder (or the stage) carries its result.json's record; the installed doors staging has none
        stage = os.path.join(self.t, "interiors_b04")
        os.makedirs(os.path.join(stage, "port"))
        self.assertIsNone(ib.base_sources(os.path.join(stage, "port")))
        ib.save(os.path.join(stage, "result.json"), {"sources": s1})
        self.assertEqual(ib.base_sources(os.path.join(stage, "port")), s1)
        self.assertEqual(ib.base_sources(stage), s1)
