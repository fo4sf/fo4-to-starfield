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


def cell(fid, edid, refs, interior=True, persistent=()):
    c = rec(b"CELL", fid, [(b"EDID", edid.encode() + b"\0"), (b"DATA", struct.pack("<H", 1 if interior else 0))])
    kids = []
    if persistent:
        kids.append(G(struct.pack("<I", fid), vp.GROUP_PERSISTENT, bytes(8), list(persistent)))
    kids.append(G(struct.pack("<I", fid), vp.GROUP_TEMPORARY, bytes(8), list(refs)))
    return [c, G(struct.pack("<I", fid), vp.GROUP_CELL_CHILDREN, bytes(8), kids)]


def fo4_plugin():
    """Fallout4.esm in miniature: a DOOR and a LIGH base; interiors Lobby (door from the Commonwealth, door on to
    Vault), Vault (reached only through Lobby), Store (a door from DiamondCity) and zzTestCell (no door leads in);
    the Commonwealth's exterior cell holds the door into Lobby, DiamondCity's the door into Store."""
    DOOR, LIGH = 0x100, 0x101
    bases = [G(b"DOOR", 0, bytes(8), [rec(b"DOOR", DOOR, [(b"EDID", b"Door\0")])]),
             G(b"LIGH", 0, bytes(8), [rec(b"LIGH", LIGH, [(b"EDID", b"Light\0")])])]
    lobby = cell(0x200, "Lobby", [ref(0x301, DOOR, xtel=0x900), ref(0x302, DOOR, xtel=0x311), ref(0x303, LIGH),
                                   ref(0x304, LIGH), ref(0x305, 0x102, sig=b"ACHR")])
    vault = cell(0x210, "Vault", [ref(0x311, DOOR, xtel=0x302), ref(0x312, 0x103)])
    store = cell(0x220, "Store", [ref(0x321, DOOR, xtel=0x910)])
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
        grown = ibs.extend(old, ibs.plan(census, backlog, min_cells=1, max_cells=2), min_cells=1, max_cells=2)
        self.assertEqual(grown["batches"][:3], old["batches"])                  # built batches stay byte-for-byte
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

    def plugin(self, extra=(), change=False, drop=False):
        OWN = 0x01000000
        stat = rec(b"STAT", OWN | 0x800, [(b"EDID", b"FO4Port_a\0"), (b"MODL", b"a.nif\0" if not change else b"b.nif\0")])
        c = rec(b"CELL", OWN | 0x801, [(b"EDID", b"FO4Port_Old\0"), (b"DATA", struct.pack("<I", 1))])
        refs = [] if drop else [ref(OWN | 0x802, OWN | 0x800)]
        kids = G(struct.pack("<I", OWN | 0x801), vp.GROUP_CELL_CHILDREN, bytes(8),
                 [G(struct.pack("<I", OWN | 0x801), vp.GROUP_TEMPORARY, bytes(8), refs)])
        blocks = [c, kids] + list(extra)
        top = G(b"CELL", 0, bytes(8), [G(struct.pack("<I", 0), 2, bytes(8), [G(struct.pack("<I", 0), 3, bytes(8), blocks)])])
        tes4 = vp.record_bytes(b"TES4", 0, 1, [(b"HEDR", struct.pack("<fII", 0.96, 3, 0x900)), (b"MAST", b"Starfield.esm\0"),
                                               (b"DATA", bytes(8))])
        return tes4.serialize() + G(b"STAT", 0, bytes(8), [stat]).serialize() + top.serialize()

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

    def _build_flow(self, bad_export_ok=False):
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

        def fake_run(cmd, log, env=None, cwd=None):
            calls.append(cmd)
            joined = " ".join(cmd)
            if "export" in cmd and cmd[0] == "dotnet":
                if cmd[-2] == "Bad" and not bad_export_ok:
                    return 1, 0.1
                ib.save(cmd[-1], {"cell": cmd[-2], "refs": [{"model": "meshes\\n.nif"}]})
            elif "convert_batch.py" in joined:
                self.assertEqual(ib.load(os.path.join(work, "editorids.json")), {"meshes\\A.nif": "FO4Port_A"})
                merged = ib.load(cmd[cmd.index("--cell-json") + 1])
                self.assertEqual(len(merged["refs"]), 3 if bad_export_ok else 2)   # Old (pinned) + New (+ Bad)
                ib.save(os.path.join(work, "manifest.json"), {"items": [], "failures": [{"nif": "meshes\\n.nif", "reason": "x"}]})
            elif "port_promote.py" in joined:
                ib.save(cmd[cmd.index("--out") + 1], {})
            elif cmd[0] == "dotnet":                                     # PluginSpike
                raw = cmd[2]
                self.assertEqual(ib.load(os.path.join(raw, "formids.json")), ids)   # seeded with the base map
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
        if bad_export_ok:
            return res
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
            elif cmd[0] == "dotnet":
                raw = cmd[2]
                seed = ib.load(os.path.join(raw, "formids.json"))
                seeds.append(seed)
                second = "CELL:FO4Port_One" in seed
                extra = [one, two] if second else [one]
                if second and renumber[0]:
                    extra = [rec(b"CELL", OWN | 0x852, [(b"EDID", b"FO4Port_One\0"), (b"DATA", struct.pack("<I", 1))]), two]
                with open(os.path.join(raw, "FO4Port.esm"), "wb") as f:
                    f.write(tool.plugin(extra=extra))
                got = dict(seed, **{"CELL:FO4Port_One": 0x852 if renumber[0] else 0x850})
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

        def build(n, out, prev=None):
            argv = ["build", "--plan", plan, "--batch", str(n), "--base", base, "--base-exports", base,
                    "--core", t, "--work", work, "--out", out, "--fo4-data", t, "--starfield", t,
                    "--content-resources", "c", "--texconv", "x", "--collision-template", "t", "--fo4export", "e",
                    "--pluginspike", "p", "--no-pack", "--jobs", "1", "--min-free-gb", "0"] + (["--prev", prev] if prev else [])
            real, ib.run = ib.run, fake_run
            try:
                return ib.main(argv)
            finally:
                ib.run = real

        b1, b2, b2x = (os.path.join(t, "staging", n) for n in ("interiors_b01", "interiors_b02", "interiors_b02x"))
        self.assertEqual(build(1, b1), 0)
        self.assertEqual(seeds[-1], ids)                                  # batch 1 starts from the base map
        self.assertEqual(build(2, b2, prev=b1), 0)
        self.assertEqual(seeds[-1]["CELL:FO4Port_One"], 0x850)            # batch 2 starts from batch 1's map
        r2 = ib.load(os.path.join(b2, "result.json"))
        self.assertTrue(r2["steps"]["compare_prev"]["pass"])
        self.assertTrue(os.path.isfile(os.path.join(b2, "port", "compare_prev.json")))
        renumber[0] = True                                                # batch 1's cell moved: the batch fails
        self.assertEqual(build(2, b2x, prev=b1), 1)
        self.assertFalse(ib.load(os.path.join(b2x, "result.json"))["steps"]["compare_prev"]["pass"])
        with self.assertRaises(SystemExit):                               # a failed batch is no --prev
            build(2, os.path.join(t, "staging", "interiors_b02y"), prev=b2x)

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
        self.assertEqual(ib.cell_plugins(plan, 2), {"DLC01Lair01": "DLCRobot.esm", "DLC03Gone": "DLCCoast.esm"})
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
            self.assertEqual(ib.export_cell(a, "DLC01Lair01", out, os.path.join(tmp.name, "x.log"), "DLCRobot.esm")[1], 0)
            self.assertEqual(calls[-1][2:5], [os.path.join(dlc, "DLCRobot.esm"), "--master", os.path.join(a.fo4_data, "Fallout4.esm")])
            self.assertEqual(ib.export_cell(a, "Old", out, os.path.join(tmp.name, "x.log"))[1], 0)
            self.assertEqual(calls[-1][2:4], [os.path.join(a.fo4_data, "Fallout4.esm"), "export"])
            n = len(calls)                                                      # a DLC that is not installed: no run
            self.assertEqual(ib.export_cell(a, "DLC03Gone", out, os.path.join(tmp.name, "x.log"), "DLCCoast.esm")[1], 2)
            self.assertEqual(len(calls), n)
        finally:
            ib.run = real

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
