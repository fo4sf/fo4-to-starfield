"""scripts/terrain/interior_content.py on synthetic plugins: enable state and enable-parent chains (C1), the leaf item
types the containers' leveled lists reach (C3), terminal menu depth (C7) and trap refs (C9), with cycles, a DLC
override and refs whose base lives in another plugin. No game data."""
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import interior_content as icn  # noqa: E402
import vmad_patch as vp  # noqa: E402

G = vp.Group
U32 = lambda v: struct.pack("<I", v)  # noqa: E731

# Fallout4.esm bases (file-local ids)
WEAP, ARMO, AMMO, ALCH, MISC, BOOK, KEYM, NOTE = 0x101, 0x102, 0x103, 0x104, 0x105, 0x106, 0x107, 0x108
LVLI_A, LVLI_B, LVLI_C, LVLI_CYCLE1, LVLI_CYCLE2, LVLI_MISSING = 0x120, 0x121, 0x122, 0x123, 0x124, 0x12F
CONT_SAFE, CONT_BOX, CONT_EMPTY = 0x130, 0x131, 0x132
TERM_ROOT, TERM_SUB, TERM_LEAF, TERM_CYC1, TERM_CYC2, TERM_PLAIN = 0x140, 0x141, 0x142, 0x143, 0x144, 0x145
TERM_DIA, TERM_ODD, TERM_MISS = 0x146, 0x147, 0x148
TRAP_MINE, TRAP_BEAR, TRAP_TRIPWIRE, TRAP_GAS, TRAPPER, HAZD, STAT, MINER = 0x150, 0x151, 0x152, 0x153, 0x154, 0x155, 0x156, 0x157
LOBBY, VAULT, STORE, ANNEX, AARDVARK = 0x200, 0x210, 0x220, 0x230, 0x1F0
WORLD, EXT = 0x3C, 0x500


def rec(sig, fid, fields, flags=0):
    return vp.record_bytes(sig, fid, flags, fields)


def edid(sig, fid, name, *fields):
    return rec(sig, fid, [(b"EDID", name.encode() + b"\0")] + list(fields))


def ref(fid, base, flags=0, parent=None, opposite=False, sig=b"REFR"):
    fields = [(b"NAME", U32(base)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))]
    if parent is not None:
        # XESP: u32 reference, u8 flags (1 opposite of parent, 2 pop in), 3 unused
        fields.insert(1, (b"XESP", struct.pack("<IB3x", parent, 1 if opposite else 0)))
    return rec(sig, fid, fields, flags=flags)


def cell(fid, name, refs, interior=True, persistent=()):
    c = rec(b"CELL", fid, [(b"EDID", name.encode() + b"\0"), (b"DATA", struct.pack("<H", 1 if interior else 0))])
    kids = []
    if persistent:
        kids.append(G(U32(fid), vp.GROUP_PERSISTENT, bytes(8), list(persistent)))
    kids.append(G(U32(fid), vp.GROUP_TEMPORARY, bytes(8), list(refs)))
    return [c, G(U32(fid), vp.GROUP_CELL_CHILDREN, bytes(8), kids)]


def lvlo(item, level=1, count=1, chance=0):
    # LVLO: u16 level, 2 unused, u32 item, u16 count, u8 chance none, 1 unused
    return (b"LVLO", struct.pack("<HxxIHBx", level, item, count, chance))


def cnto(item, count=1):
    return (b"CNTO", struct.pack("<Ii", item, count))


def menu_item(text, submenu=None, typ=None):
    out = [(b"ITXT", text.encode() + b"\0")]
    if submenu is not None:
        out.append((b"ANAM", bytes([4 if typ is None else typ])))
        out.append((b"TNAM", U32(submenu)))
    else:
        out.append((b"ANAM", bytes([8])))
    return out


def term(fid, name, bodies, items):
    fields = [(b"BSIZ", U32(len(bodies)))] + [(b"BTXT", b.encode() + b"\0") for b in bodies] + [(b"ISIZ", U32(len(items)))]
    for it in items:
        fields += it
    return edid(b"TERM", fid, name, *fields)


def group(sig, records):
    return G(sig, 0, bytes(8), records)


def plugin_bytes(tes4, groups):
    return tes4.serialize() + b"".join(g.serialize() for g in groups)


def interiors(cells_):
    sub = G(U32(0), 3, bytes(8), cells_)
    return G(b"CELL", 0, bytes(8), [G(U32(0), 2, bytes(8), [sub])])


def worlds_group(ext):
    w = rec(b"WRLD", WORLD, [(b"EDID", b"Commonwealth\0")])
    blk = G(U32(0), 4, bytes(8), [G(U32(0), 5, bytes(8), ext)])
    return G(b"WRLD", 0, bytes(8), [w, G(U32(WORLD), 1, bytes(8), [blk])])


def extra_cells():
    """Two more interiors for the order tests: Aardvark (before Lobby in the plugin) and Annex (after Store) each hold
    the second member of the LVLI cycle and of the TERM cycle, a diamond terminal (root -> sub -> leaf and root ->
    leaf), a terminal with a submenu in no plugin, two refs of the same Box, and a second TermSub."""
    def refs(base):
        return [ref(base + 0, LVLI_CYCLE2), ref(base + 1, TERM_CYC2), ref(base + 2, TERM_DIA), ref(base + 3, TERM_MISS),
                ref(base + 4, CONT_BOX), ref(base + 5, CONT_BOX), ref(base + 6, TERM_SUB)]
    return cell(AARDVARK, "Aardvark", refs(0x3A0)), cell(ANNEX, "Annex", refs(0x3B0))


def fo4_plugin(extra=False):
    """Fallout4.esm in miniature. Lobby: a chain of enable parents 0x301 -> 0x302 -> 0x303 (0x303 persistent, disabled,
    opposite), a ref whose parent 0x311 stands in Vault, one whose parent 0x900 stands in the Commonwealth, one whose
    parent 0x999 is placed nowhere, a 2-ref XESP cycle; a safe (CONT -> LVLI_A -> LVLI_B -> leaves, plus a direct
    MISC and the cyclic LVLI pair), an empty container, a leveled-item ref (LVLI_C -> AMMO, missing LVLI), terminals
    (root -> sub -> leaf = depth 2, a 2-TERM cycle, a plain one), traps (mine, bear trap, tripwire x2, a gas trap
    ACTI, a hazard PHZD) and non-traps (Trapper armor, MinerOutfit). Vault and Store hold little."""
    bases = [
        group(b"WEAP", [edid(b"WEAP", WEAP, "Pipe"), edid(b"WEAP", TRAP_MINE, "MineFrag")]),
        group(b"ARMO", [edid(b"ARMO", ARMO, "Leather"), edid(b"ARMO", TRAPPER, "TrapperArmor"), edid(b"ARMO", MINER, "MinerOutfit")]),
        group(b"AMMO", [edid(b"AMMO", AMMO, "Ammo10mm")]),
        group(b"ALCH", [edid(b"ALCH", ALCH, "Stimpak")]),
        group(b"MISC", [edid(b"MISC", MISC, "Junk")]),
        group(b"BOOK", [edid(b"BOOK", BOOK, "Magazine")]),
        group(b"KEYM", [edid(b"KEYM", KEYM, "Key")]),
        group(b"NOTE", [edid(b"NOTE", NOTE, "Holotape")]),
        group(b"LVLI", [
            edid(b"LVLI", LVLI_A, "LL_A", (b"LLCT", b"\x03"), lvlo(WEAP), lvlo(LVLI_B), lvlo(LVLI_MISSING)),
            edid(b"LVLI", LVLI_B, "LL_B", (b"LLCT", b"\x03"), lvlo(ARMO), lvlo(ALCH, count=3), lvlo(WEAP)),
            edid(b"LVLI", LVLI_C, "LL_C", (b"LLCT", b"\x01"), lvlo(AMMO)),
            edid(b"LVLI", LVLI_CYCLE1, "LL_Cyc1", (b"LLCT", b"\x02"), lvlo(LVLI_CYCLE2), lvlo(BOOK)),
            edid(b"LVLI", LVLI_CYCLE2, "LL_Cyc2", (b"LLCT", b"\x02"), lvlo(LVLI_CYCLE1), lvlo(KEYM))]),
        group(b"CONT", [
            edid(b"CONT", CONT_SAFE, "Safe", (b"COCT", U32(3)), cnto(LVLI_A), cnto(MISC, 2), cnto(LVLI_CYCLE1)),
            edid(b"CONT", CONT_BOX, "Box", (b"COCT", U32(1)), cnto(NOTE)),
            edid(b"CONT", CONT_EMPTY, "Empty")]),
        group(b"TERM", [
            term(TERM_ROOT, "TermRoot", ["Welcome"], [menu_item("Logs", TERM_SUB), menu_item("Note")]),
            term(TERM_SUB, "TermSub", [], [menu_item("Entry 1", TERM_LEAF), menu_item("Entry 2", TERM_LEAF)]),
            term(TERM_LEAF, "TermLeaf", ["Body A", "Body B"], [menu_item("Read")]),
            term(TERM_CYC1, "TermCyc1", [], [menu_item("To 2", TERM_CYC2)]),
            term(TERM_CYC2, "TermCyc2", [], [menu_item("To 1", TERM_CYC1), menu_item("Text")]),
            term(TERM_PLAIN, "TermPlain", ["Hello"], []),
            term(TERM_DIA, "TermDia", [], [menu_item("Logs", TERM_SUB), menu_item("Last", TERM_LEAF)]),
            term(TERM_ODD, "TermOdd", [], [menu_item("Odd", TERM_LEAF, typ=8)]),
            term(TERM_MISS, "TermMiss", [], [menu_item("Gone", 0xEEE)])]),
        group(b"ACTI", [edid(b"ACTI", TRAP_BEAR, "TrapBearTrap01"), edid(b"ACTI", TRAP_TRIPWIRE, "TrapTripwire01"),
                        edid(b"ACTI", TRAP_GAS, "gastrap01")]),
        group(b"HAZD", [edid(b"HAZD", HAZD, "GasHazard")]),
        group(b"STAT", [edid(b"STAT", STAT, "Wall")]),
    ]
    lobby = cell(LOBBY, "Lobby", [
        ref(0x301, STAT, parent=0x302), ref(0x302, STAT, parent=0x303, opposite=True),
        ref(0x304, STAT, parent=0x311), ref(0x305, STAT, parent=0x900), ref(0x306, STAT, parent=0x999),
        ref(0x307, STAT, parent=0x308), ref(0x308, STAT, parent=0x307),
        ref(0x309, STAT, flags=icn.INITIALLY_DISABLED), ref(0x30A, STAT, parent=0, opposite=True),
        ref(0x320, CONT_SAFE), ref(0x321, CONT_EMPTY), ref(0x322, LVLI_C), ref(0x323, LVLI_MISSING),
        ref(0x330, TERM_ROOT), ref(0x331, TERM_CYC1), ref(0x332, TERM_PLAIN),
        ref(0x340, TRAP_MINE), ref(0x341, TRAP_BEAR), ref(0x342, TRAP_TRIPWIRE), ref(0x343, TRAP_TRIPWIRE),
        ref(0x344, TRAP_GAS), ref(0x345, HAZD, sig=b"PHZD"), ref(0x346, TRAPPER), ref(0x347, MINER),
    ], persistent=[ref(0x303, STAT, flags=icn.INITIALLY_DISABLED | vp.PERSISTENT, parent=0x312)])
    vault = cell(VAULT, "Vault", [ref(0x311, STAT, flags=icn.INITIALLY_DISABLED), ref(0x312, STAT), ref(0x313, CONT_BOX)])
    store = cell(STORE, "Store", [ref(0x350, TERM_SUB)])
    ext = cell(EXT, "", [ref(0x900, STAT, flags=icn.INITIALLY_DISABLED, parent=0x901), ref(0x901, STAT)], interior=False)
    cells_ = lobby + vault + store
    if extra:
        aardvark, annex = extra_cells()
        cells_ = aardvark + cells_ + annex
    tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 20, 0x1000))], flags=1)
    return plugin_bytes(tes4, bases + [interiors(cells_), worlds_group(ext)])


def master_header(count):
    return rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, count, 0x800)), (b"MAST", b"Fallout4.esm\0"), (b"DATA", bytes(8))], flags=1)


def dlc_plugin():
    """DLCRobot.esm: overrides Fallout4.esm's Box container (now holds LVLI_C: AMMO) and the safe's ref 0x320 (now a
    Box); adds its own interior Lair with a ref whose base is Fallout4.esm's TERM_ROOT and one of its own CONT whose
    items are Fallout4.esm's WEAP and a DLC LVLI of a DLC MISC; re-saves Lobby's trap 0x340 as a plain wall and renames
    the tripwire ACTI to a non-trap name."""
    tes4 = master_header(2)
    DLC_CONT, DLC_LVLI, DLC_MISC, LAIR = 0x01000800, 0x01000801, 0x01000802, 0x01000810
    bases = [group(b"MISC", [edid(b"MISC", DLC_MISC, "RobotPart")]),
             group(b"ACTI", [edid(b"ACTI", TRAP_TRIPWIRE, "Wire01")]),
             group(b"LVLI", [edid(b"LVLI", DLC_LVLI, "LL_Robot", (b"LLCT", b"\x01"), lvlo(DLC_MISC))]),
             group(b"CONT", [edid(b"CONT", CONT_BOX, "Box", (b"COCT", U32(1)), cnto(LVLI_C)),
                             edid(b"CONT", DLC_CONT, "RobotCrate", (b"COCT", U32(2)), cnto(WEAP), cnto(DLC_LVLI))])]
    lobby = cell(LOBBY, "Lobby", [ref(0x320, CONT_BOX), ref(0x340, STAT)])
    lair = cell(LAIR, "Lair", [ref(0x01000820, TERM_ROOT), ref(0x01000821, DLC_CONT), ref(0x01000822, STAT, parent=0x303)])
    return plugin_bytes(tes4, bases + [interiors(lobby + lair)])


def mover_plugin():
    """DLCMove.esm: moves Lobby's bear trap 0x341 into the Commonwealth cell and its tripwire 0x343 into Vault, and
    deletes the tripwire 0x342 (record flag 0x20, no fields)."""
    tes4 = master_header(1)
    vault = cell(VAULT, "Vault", [ref(0x343, TRAP_TRIPWIRE)])
    lobby = cell(LOBBY, "Lobby", [rec(b"REFR", 0x342, [], flags=icn.DELETED)])
    ext = cell(EXT, "", [ref(0x341, TRAP_BEAR)], interior=False)
    return plugin_bytes(tes4, [interiors(lobby + vault), worlds_group(ext)])


def fk(local, plugin="Fallout4.esm"):
    return "%06X:%s" % (local, plugin)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.esm = os.path.join(self.tmp.name, "Fallout4.esm")
        with open(self.esm, "wb") as f:
            f.write(fo4_plugin())
        self.dlc = os.path.join(self.tmp.name, "DLCRobot.esm")
        with open(self.dlc, "wb") as f:
            f.write(dlc_plugin())

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    @staticmethod
    def by_cell(r):
        return {c["editor_id"]: c for c in r["cells"]}

    def test_c1_enable_state_and_parent_chains(self):
        r = icn.content([self.esm])
        by = {c["editor_id"]: c for c in r["cells"]}
        lobby = by["Lobby"]
        # 0x303 (persistent, disabled) and 0x309 are flagged; 0x303 and 0x302 ... have parents; 0x302 is opposite
        self.assertEqual((lobby["disabled"], lobby["enable_parent"], lobby["opposite_state"]), (2, 8, 1))
        self.assertEqual(lobby["disabled_without_parent"], 1)                       # 0x309
        # parents outside the cell: 0x311 in Vault, 0x312 in Vault (0x303's), 0x900 in the Commonwealth, 0x999 nowhere
        outside = {p["ref"]: p for p in lobby["parents_outside"]}
        self.assertEqual(sorted(outside), [fk(0x311), fk(0x312), fk(0x900), fk(0x999)])
        self.assertEqual(outside[fk(0x311)], {"ref": fk(0x311), "in": "Vault", "children": 1})
        self.assertEqual(outside[fk(0x900)]["in"], "world:Commonwealth")
        self.assertIsNone(outside[fk(0x999)]["in"])
        # 0x30A's XESP names parent 0 with the opposite flag: no parent, not an opposite state
        self.assertEqual(lobby["parents"], 8)
        # the deepest chain: 0x301 -> 0x302 -> 0x303 -> 0x312 (in Vault), depth 3; one 2-ref cycle (0x307 <-> 0x308)
        self.assertEqual(lobby["deepest_chain"], 3)
        self.assertEqual(lobby["deepest_chain_refs"], [fk(0x301), fk(0x302), fk(0x303), fk(0x312)])
        self.assertEqual((lobby["chain_cycles"], lobby["chains_cut"]), (1, 0))
        self.assertEqual((by["Vault"]["disabled"], by["Vault"]["enable_parent"]), (1, 0))
        t = r["totals"]
        self.assertEqual((t["disabled"], t["enable_parent"], t["cells_with_enable_state"], t["deepest_chain"]), (3, 8, 2, 3))
        self.assertEqual((t["parents_outside"], t["parents_outside_unplaced"], t["parents_unresolved"]), (4, 1, 0))
        self.assertEqual(r["top_enable_state"][0], {"formkey": fk(LOBBY), "editor_id": "Lobby", "count": 10})
        # the XESP reader and the raw flag
        self.assertEqual(icn.xesp(struct.pack("<IB3x", 0x1234, 3)), (0x1234, 3))
        self.assertIsNone(icn.xesp(bytes(3)))
        self.assertEqual(icn.INITIALLY_DISABLED, 0x800)

    def test_c3_leaf_item_types_through_leveled_lists(self):
        r = icn.content([self.esm])
        lobby = {c["editor_id"]: c for c in r["cells"]}["Lobby"]
        # 0x323's base (an LVLI in no plugin read) has no known signature, so only 0x322 counts as a leveled-item ref
        self.assertEqual((lobby["containers"], lobby["container_bases"], lobby["leveled_item_refs"]), (2, 2, 1))
        # the safe's direct entries: LVLI_A, MISC, LVLI_CYCLE1 (the empty container adds none)
        self.assertEqual(lobby["direct_contents"], {"LVLI": 2, "MISC": 1})
        # leaves: WEAP (once, reached twice), ARMO, ALCH via LL_A -> LL_B; MISC direct; BOOK, KEYM through the cycle;
        # AMMO from the placed LL_C; LL_A's entry for the LVLI in no plugin read is one "?" leaf
        self.assertEqual(lobby["leaf_types"], {"?": 1, "ALCH": 1, "AMMO": 1, "ARMO": 1, "BOOK": 1, "KEYM": 1, "MISC": 1, "WEAP": 1})
        self.assertEqual(lobby["leaves_unresolved"], 1)
        self.assertEqual(r["leaf_types"], {"?": 1, "ALCH": 1, "AMMO": 1, "ARMO": 1, "BOOK": 1, "KEYM": 1, "MISC": 1, "NOTE": 1, "WEAP": 1})
        self.assertEqual(r["totals"]["leaf_records"], 9)
        # the LVLO reader takes the form id at offset 4 of the 12-byte entry, and skips a short one
        c = icn.Content()
        c.read([self.esm])
        self.assertEqual(c.lvli[fk(LVLI_B)], [fk(ARMO), fk(ALCH), fk(WEAP)])
        self.assertEqual(c.cont[fk(CONT_SAFE)], [(fk(LVLI_A), 1), (fk(MISC), 2), (fk(LVLI_CYCLE1), 1)])
        self.assertEqual(sorted(c.leaves(fk(LVLI_CYCLE1), {}).values()), ["BOOK", "KEYM"])

    def test_c7_terminal_menu_depth(self):
        r = icn.content([self.esm])
        by = {c["editor_id"]: c for c in r["cells"]}
        terms = {t["editor_id"]: t for t in by["Lobby"]["terminals"]}
        self.assertEqual(sorted(terms), ["TermCyc1", "TermPlain", "TermRoot"])
        root = terms["TermRoot"]
        self.assertEqual((root["depth"], root["menu_items"], root["body_texts"]), (2, 2, 1))
        # the whole tree: root (2 items, 1 body) + sub (2 items) + leaf (1 item, 2 bodies), the leaf counted once
        self.assertEqual((root["menu_items_total"], root["body_texts_total"], root["terminals_total"], root["cycle"]), (5, 3, 3, False))
        cyc = terms["TermCyc1"]
        self.assertEqual((cyc["depth"], cyc["cycle"], cyc["menu_items_total"]), (1, True, 3))
        self.assertEqual((terms["TermPlain"]["depth"], terms["TermPlain"]["body_texts"]), (0, 1))
        self.assertEqual(by["Lobby"]["terminal_depths"], {"0": 1, "1": 1, "2": 1})
        self.assertEqual(by["Store"]["terminals"][0]["depth"], 1)                   # TermSub placed on its own
        self.assertEqual(r["terminal_depths"], {"0": 1, "1": 2, "2": 1})
        self.assertEqual(r["terminal_base_depths"], {"0": 1, "1": 2, "2": 1})
        self.assertEqual((r["totals"]["terminals"], r["totals"]["terminal_bases"], r["totals"]["terminal_depth_max"],
                          r["totals"]["terminal_cycles"]), (4, 4, 2, 1))

    def test_c9_traps_by_base(self):
        r = icn.content([self.esm])
        lobby = {c["editor_id"]: c for c in r["cells"]}["Lobby"]
        self.assertEqual(lobby["trap_refs"], 6)
        self.assertEqual(lobby["traps"], {"GasHazard (HAZD)": 1, "MineFrag (WEAP)": 1, "TrapBearTrap01 (ACTI)": 1,
                                          "TrapTripwire01 (ACTI)": 2, "gastrap01 (ACTI)": 1})
        self.assertEqual(lobby["trap_kinds"], {"bear_trap": 1, "gas": 1, "hazard": 1, "mine": 1, "tripwire": 2})
        self.assertEqual(r["top_traps"][0]["editor_id"], "Lobby")
        self.assertEqual(r["totals"]["cells_with_traps"], 1)
        for name, kind in (("TrapperArmor", None), ("MinerOutfit", None), ("Determine", None), ("TrapMineFrag01", "mine"),
                           ("oiltrappuddle01", "oil"), ("TrapFlamethrower", "trap"), ("LandMines", "mine")):
            self.assertEqual(icn.trap_kind(name), kind, name)

    def test_a_dlc_overrides_and_cross_plugin_bases(self):
        r = icn.content([self.esm, self.dlc])
        by = {c["editor_id"]: c for c in r["cells"]}
        lobby, lair = by["Lobby"], by["Lair"]
        self.assertEqual(lobby["plugins"], ["Fallout4.esm", "DLCRobot.esm"])
        # 0x320 is a Box now, and the DLC's Box holds LL_C (AMMO): the safe's leaves are gone from Lobby
        self.assertEqual(lobby["direct_contents"], {"LVLI": 1})
        self.assertEqual(lobby["leaf_types"], {"AMMO": 1})
        # 0x340 is a wall now: one trap less, and the ref is still counted once
        self.assertEqual((lobby["trap_refs"], lobby["refs"]), (3, 25))
        self.assertNotIn("MineFrag (WEAP)", lobby["traps"])
        self.assertNotIn("tripwire", lobby["trap_kinds"])                        # the DLC renamed the ACTI to Wire01
        self.assertEqual([c["editor_id"] for c in r["cells"]], ["Lobby", "Store", "Vault", "Lair"])    # esm cells first
        # the DLC cell: a TERM from Fallout4.esm, a DLC CONT whose items cross both plugins, a parent in Lobby
        self.assertEqual(lair["formkey"], fk(0x000810, "DLCRobot.esm"))
        self.assertEqual(lair["terminals"][0]["editor_id"], "TermRoot")
        self.assertEqual(lair["terminals"][0]["depth"], 2)
        self.assertEqual(lair["leaf_types"], {"MISC": 1, "WEAP": 1})
        self.assertEqual(lair["parents_outside"], [{"ref": fk(0x303), "in": "Lobby", "children": 1}])
        self.assertEqual(lair["deepest_chain"], 2)                                  # 0x...822 -> 0x303 -> 0x312
        self.assertEqual(r["totals"]["cells"], 4)
        self.assertEqual(r["totals"]["terminals"], 5)

    def test_census_selects_cells(self):
        census = {"cells": [{"formkey": fk(VAULT), "editor_id": "Vault"}, {"formkey": fk(STORE), "editor_id": "Store"}]}
        keys = icn.census_cells(census)
        r = icn.content([self.esm], keys)
        self.assertEqual(sorted(c["editor_id"] for c in r["cells"]), ["Store", "Vault"])
        self.assertEqual(icn.census_cells(census, ["vault"]), {fk(VAULT)})
        with self.assertRaisesRegex(ValueError, "not in the census"):
            icn.census_cells(census, ["Nowhere"])

    def test_main_writes_json_and_markdown(self):
        out = os.path.join(self.tmp.name, "content.json")
        census = os.path.join(self.tmp.name, "census.json")
        with open(census, "w") as f:
            json.dump({"cells": [{"formkey": fk(LOBBY), "editor_id": "Lobby"}]}, f)
        self.assertEqual(icn.main(["--out", out, "--census", census, self.esm, self.dlc]), 0)
        with open(out) as f:
            r = json.load(f)
        self.assertEqual([c["editor_id"] for c in r["cells"]], ["Lobby"])
        self.assertEqual(r["census"], census)
        with open(os.path.join(self.tmp.name, "content.md")) as f:
            md = f.read()
        self.assertIn("## C7 Terminals", md)
        self.assertIn("Trap refs: 3 in 1 cells; by kind: bear_trap 1, gas 1, hazard 1.", md)
        self.assertIn("parent cycles: 1; chains cut after 4 hops outside: 0 (0 parents unresolved)", md)
        with self.assertRaises(SystemExit):
            icn.main(["--out", out, self.dlc])                                       # Fallout4.esm must come first
        with self.assertRaises(SystemExit):
            icn.main(["--out", out, "--cells", "Lobby", self.esm])                   # --cells needs --census

    def test_cycle_answers_do_not_depend_on_cell_order(self):
        """A cycle member reached after the other member was measured (Annex after Lobby) and before it (Aardvark
        before Lobby) gets the same C3 leaves and C7 depth as when measured alone."""
        esm = self.write("Fallout4.esm", fo4_plugin(extra=True))
        together = self.by_cell(icn.content([esm]))
        alone = {n: self.by_cell(icn.content([esm], {fk(k)}))[n] for n, k in (("Aardvark", AARDVARK), ("Annex", ANNEX))}
        for name in ("Aardvark", "Annex"):
            for r in (together[name], alone[name]):
                self.assertEqual(r["leaf_types"], {"BOOK": 1, "KEYM": 1, "NOTE": 1}, name)
                terms = {t["editor_id"]: (t["depth"], t["cycle"], t["menu_items_total"], t["terminals_total"])
                         for t in r["terminals"]}
                self.assertEqual(terms["TermCyc2"], (1, True, 3, 2), name)
                self.assertEqual(terms["TermSub"], (1, False, 3, 2), name)
        lobby = together["Lobby"]
        self.assertEqual(lobby["leaf_types"]["BOOK"], 1)
        self.assertEqual({t["editor_id"]: t["depth"] for t in lobby["terminals"]}["TermCyc1"], 1)
        # the unit: a shared memo gives each cycle member its own full answer, and both are memoized together
        c = icn.Content()
        c.read([esm])
        memo = {}
        self.assertEqual(sorted(c.leaves(fk(LVLI_CYCLE1), memo).values()), ["BOOK", "KEYM"])
        self.assertEqual(sorted(c.leaves(fk(LVLI_CYCLE2), memo).values()), ["BOOK", "KEYM"])
        self.assertEqual(sorted(memo), [fk(LVLI_CYCLE1), fk(LVLI_CYCLE2)])
        memo = {}
        self.assertEqual(c.terminal(fk(TERM_CYC1), memo)["depth"], 1)
        self.assertEqual(c.terminal(fk(TERM_CYC2), memo)["depth"], 1)
        self.assertEqual(memo, {})                                                   # cycle members are never memoized
        self.assertEqual(c.terminal(fk(TERM_ROOT), memo)["depth"], 2)
        self.assertEqual(sorted(memo), [fk(TERM_ROOT), fk(TERM_SUB), fk(TERM_LEAF)])

    def test_terminal_tree_counts_distinct_terminals(self):
        esm = self.write("Fallout4.esm", fo4_plugin(extra=True))
        r = icn.content([esm])
        annex = self.by_cell(r)["Annex"]
        terms = {t["editor_id"]: t for t in annex["terminals"]}
        # the diamond: dia (2 items) -> sub (2 items) -> leaf (1 item, 2 bodies) and dia -> leaf: the leaf counted once
        dia = terms["TermDia"]
        self.assertEqual((dia["depth"], dia["menu_items_total"], dia["body_texts_total"], dia["terminals_total"]), (2, 5, 2, 3))
        # a submenu in no plugin read: no depth, flagged
        self.assertEqual((terms["TermMiss"]["depth"], terms["TermMiss"]["submenus_missing"]), (0, 1))
        self.assertEqual(terms["TermDia"]["submenus_missing"], 0)
        # TermSub placed three times (Store, Aardvark, Annex) counts three placed terminals of depth 1 but one base
        self.assertEqual(r["terminal_depths"]["1"], 2 + 3 + 1)                       # Cyc2 x2, Sub x3, Cyc1 in Lobby
        self.assertEqual(r["terminal_base_depths"], {"0": 2, "1": 3, "2": 2})         # Plain, Miss; Sub, Cyc1, Cyc2; Root, Dia
        self.assertEqual((r["totals"]["terminal_bases"], r["totals"]["terminal_cycles"]), (7, 3))
        # the ANAM check: a TNAM under a menu item of another type is noted
        c = icn.Content()
        c.read([esm])
        self.assertEqual(c.term[fk(TERM_ODD)]["odd_types"], [8])
        self.assertNotIn("odd_types", c.term[fk(TERM_DIA)])
        self.assertEqual((annex["containers"], annex["container_bases"]), (2, 1))

    def test_override_moves_and_deletes_refs(self):
        """A later plugin's copy leaves the earlier cell whether it lands in a measured cell, an unmeasured interior,
        a worldspace cell, or is deleted."""
        mover = self.write("DLCMove.esm", mover_plugin())
        r = icn.content([self.esm, mover])
        by = self.by_cell(r)
        # 0x341 to the Commonwealth, 0x342 deleted, 0x343 to Vault: Lobby keeps the mine, the gas trap and the hazard
        self.assertEqual((by["Lobby"]["refs"], by["Lobby"]["trap_refs"]), (25 - 3, 3))
        self.assertEqual(by["Lobby"]["trap_kinds"], {"gas": 1, "hazard": 1, "mine": 1})
        self.assertEqual(by["Vault"]["traps"], {"TrapTripwire01 (ACTI)": 1})
        self.assertEqual(r["totals"]["trap_refs"], 4)
        # the same with only Lobby measured: the destinations are not measured, the refs still leave
        r = icn.content([self.esm, mover], {fk(LOBBY)})
        lobby = self.by_cell(r)["Lobby"]
        self.assertEqual((lobby["refs"], lobby["trap_refs"], r["totals"]["trap_refs"]), (22, 3, 3))
        self.assertEqual(lobby["plugins"], ["Fallout4.esm", "DLCMove.esm"])

    def test_a_deleted_cell_leaves_the_content_scan(self):
        """A later plugin deletes Vault's CELL (record flag 0x20, no fields, no child group): Vault and every ref its
        earlier copy held leave the scan, measured or named."""
        before = self.by_cell(icn.content([self.esm]))
        self.assertIn("Vault", before)
        gone = self.write("DLCGone.esm", plugin_bytes(master_header(1), [interiors([rec(b"CELL", VAULT, [], flags=icn.DELETED)])]))
        r = icn.content([self.esm, gone])
        by = self.by_cell(r)
        self.assertNotIn("Vault", by)
        self.assertEqual(r["totals"]["refs"], sum(c["refs"] for c in before.values()) - before["Vault"]["refs"])
        self.assertNotIn("Vault", self.by_cell(icn.content([self.esm, gone], {fk(VAULT), fk(LOBBY)})))

    def test_a_deleted_base_record_no_longer_resolves(self):
        """A later plugin deletes the empty container's CONT (flag 0x20): Lobby's ref to it is no container any more."""
        gone = self.write("DLCBase.esm", plugin_bytes(master_header(1), [group(b"CONT", [rec(b"CONT", CONT_EMPTY, [], flags=icn.DELETED)])]))
        lobby = self.by_cell(icn.content([self.esm, gone]))["Lobby"]
        self.assertEqual((lobby["containers"], lobby["container_bases"]), (1, 1))

    def test_plugin_name_case_follows_the_masters(self):
        """fallout4.esm on the command line (a case-insensitive disk opens it) still keys its records Fallout4.esm,
        as the DLC's MAST and the census spell it."""
        esm = self.write("fallout4.esm", fo4_plugin())
        r = icn.content([esm, self.dlc])
        self.assertEqual(r["plugins"], ["Fallout4.esm", "DLCRobot.esm"])
        by = self.by_cell(r)
        self.assertEqual(by["Lobby"]["formkey"], fk(LOBBY))
        self.assertEqual(by["Lobby"]["plugins"], ["Fallout4.esm", "DLCRobot.esm"])   # one cell, overridden
        self.assertEqual(by["Lair"]["terminals"][0]["editor_id"], "TermRoot")       # the DLC ref's esm base resolves
        self.assertEqual(r["totals"]["cells"], 4)
        r = icn.content([esm, self.dlc], {fk(LOBBY)})
        self.assertEqual((r["totals"]["cells"], r["totals"]["refs"]), (1, 25))
        names, canon = icn.plugin_names([esm, self.dlc])
        self.assertEqual(names, ["Fallout4.esm", "DLCRobot.esm"])
        self.assertEqual(canon["fallout4.esm"], "Fallout4.esm")

    def test_parent_chain_cut_after_the_passes(self):
        """0x305 -> 0x900 (Commonwealth) -> 0x901: with one pass only 0x900 is found, so the chain is flagged cut."""
        saved = icn.MAX_PARENT_PASSES
        try:
            icn.MAX_PARENT_PASSES = 1
            r = icn.content([self.esm], {fk(LOBBY)})
        finally:
            icn.MAX_PARENT_PASSES = saved
        lobby = self.by_cell(r)["Lobby"]
        self.assertEqual((lobby["chains_cut"], r["totals"]["parents_unresolved"]), (1, 1))
        self.assertEqual({p["ref"]: p["in"] for p in lobby["parents_outside"]}[fk(0x900)], "world:Commonwealth")
        r = icn.content([self.esm], {fk(LOBBY)})
        self.assertEqual((self.by_cell(r)["Lobby"]["chains_cut"], r["totals"]["parents_unresolved"]), (0, 0))

    def test_parent_in_an_unflagged_interior_group_cell(self):
        """A CELL of the interior top group whose DATA lacks the interior flag (hypothesis: none in Fallout4.esm)
        holding an enable parent is named by its editor id, not crashed on as a worldspace cell."""
        odd = cell(0x240, "OddCell", [ref(0x3C0, STAT)], interior=False)
        lobby = cell(LOBBY, "Lobby", [ref(0x301, STAT, parent=0x3C0)])
        tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 3, 0x1000))], flags=1)
        esm = self.write("Fallout4.esm", plugin_bytes(tes4, [group(b"STAT", [edid(b"STAT", STAT, "Wall")]), interiors(lobby + odd)]))
        r = icn.content([esm])
        self.assertEqual([c["editor_id"] for c in r["cells"]], ["Lobby"])            # the unflagged cell is not measured
        self.assertEqual(self.by_cell(r)["Lobby"]["parents_outside"], [{"ref": fk(0x3C0), "in": "OddCell", "children": 1}])

    def test_markdown_without_terminals_or_cells(self):
        census = os.path.join(self.tmp.name, "census.json")
        with open(census, "w") as f:
            json.dump({"cells": [{"formkey": fk(VAULT), "editor_id": "Vault"}]}, f)
        out = os.path.join(self.tmp.name, "vault.json")
        self.assertEqual(icn.main(["--out", out, "--census", census, self.esm]), 0)
        with open(os.path.join(self.tmp.name, "vault.md")) as f:
            md = f.read()
        self.assertIn("Placed terminals: 0 in 0 cells, 0 TERM bases, deepest menu 0, cycles 0.", md)
        self.assertIn("Trap refs: 0 in 0 cells", md)
        empty = icn.content([self.esm], set())
        self.assertEqual(empty["totals"]["cells"], 0)
        self.assertIn("0 cells, 0 placed references", icn.markdown(empty))
        self.assertEqual(empty["top_traps"], [])

    def test_hazards_and_trap_names(self):
        esm = self.write("Fallout4.esm", fo4_plugin())
        r = icn.content([esm])
        lobby = self.by_cell(r)["Lobby"]
        self.assertEqual(lobby["traps"]["GasHazard (HAZD)"], 1)                      # the PHZD of a HAZD
        self.assertEqual(len(r["top_traps"]), 1)                                     # cells without traps are left out
        c = icn.Content()
        c.read([esm])
        # a REFR of a HAZD base and a PHZD of any base are hazards; a REFR of a wall is not
        for v, kind in ((("REFR", fk(HAZD), False, None, False), "hazard"), (("PHZD", fk(STAT), False, None, False), "hazard"),
                        (("REFR", fk(STAT), False, None, False), None)):
            c.cells[fk(VAULT)]["refs"] = {fk(0x3D0): v}
            self.assertEqual(c.cell_row(fk(VAULT), c.cells[fk(VAULT)], {}, {})["trap_kinds"], {kind: 1} if kind else {}, v)
        for name, kind in (("LeatherStrap", None), ("Straps01", None), ("Contraption01", None), ("Extrapolator", None),
                           ("TrapdoorHatch", None), ("MineCart01", None), ("LC_MinesDrainage", None), ("DN015_MineShaft", None),
                           ("GasTrapper", None), ("TrappedChest", "trap"), ("MineBottlecap", "mine"), ("Mine01", "mine"),
                           ("DN_Trap_Flamer", "trap"), ("TrapMineFrag01", "mine")):
            self.assertEqual(icn.trap_kind(name), kind, name)


if __name__ == "__main__":
    unittest.main()
