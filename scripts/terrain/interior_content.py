"""interior_content.py: what the interior cells hold that the port has to decide about (research framework rows C1,
C3, C7 and C9 of docs/terrain/interior-batches.md "Content census"): initially disabled references and enable-parent
chains, the item types the containers' leveled lists reach, the terminals' menu depth, and the trap references.

  python scripts/terrain/interior_content.py --out <content.json> [--md <content.md>]
         [--census docs/terrain/data/interior-census.json] [--cells <editor id or form key>]... Fallout4.esm [DLCRobot.esm ...]

Read-only. Every plugin is read raw with src/fo4sf/fo4land.py (memory-mapped, one record decompressed at a time) in the
order given, Fallout4.esm first; a later plugin's record of the same form key replaces the earlier one (the base, the
container's items, the leveled list, the terminal, or the placed reference, which then leaves the cell the earlier
copy stood in, wherever the later copy stands: a measured cell, another interior, a worldspace), as
interior_census.py does; a later copy flagged Deleted (record flag 0x20) removes the reference. Form keys are
"<6 hex>:<owner plugin>" with the plugin spelled as the later plugins' MAST names it ("Fallout4.esm" however the
command line spells the file), so the keys match the census's. With --census only that census's cells are measured
(all of them, so pass a census filtered to the cells wanted, or --cells); without one every interior cell of the
plugins is.

Per cell (keys as interior_census.py writes them):
  C1  `disabled` references (record flag 0x800 Initially Disabled), `enable_parent` references (XESP), the distinct
      parents and the ones standing outside the cell (`parents_outside`: in another interior, a worldspace, or not
      placed in the plugins read), `opposite_state` (XESP flag 1, Set Enable State to Opposite of Parent),
      `deepest_chain` (child -> parent -> grandparent ..., the longest, with its references), `chain_cycles` (distinct
      cycles of parents) and `chains_cut` (chains the second walk gave up on after MAX_PARENT_PASSES hops outside).
  C3  `containers` (placed references whose base is a CONT), `leveled_item_refs` (placed references whose base is an
      LVLI), `direct_contents` (the containers' CNTO entries by the item's record signature, one per placed
      container) and `leaf_types`: the distinct records reached from those entries and the leveled-item refs through
      every LVLI (recursively; a cycle's members reach the same leaves), by record signature (WEAP, ARMO, AMMO, ALCH,
      MISC, BOOK, KEYM, NOTE, ...; "?" when the base is in no plugin read).
  C7  `terminals`: every placed TERM with its menu depth (0 = no submenu; a menu item's TNAM opens a submenu TERM,
      counted recursively, a cycle cut where the path repeats and flagged), the menu items and body texts at the top
      and over the distinct terminals of the whole tree.
  C9  `traps`: placed references whose base's editor id names a trap (hypothesis, the kinds below) or whose base is a
      HAZD / whose record is a PHZD, counted by base editor id and by kind.
Totals and the cells with the most of each follow, plus a short Markdown summary.
"""
import argparse
import json
import os
import re
import struct
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
sys.path.insert(0, HERE)
from fo4sf import fo4land as fl  # noqa: E402
import interior_census as ic  # noqa: E402

# Record layouts (xEdit dev-4.1.6, Core/wbDefinitionsFO4.pas unless named):
#   record flag 0x800 "Initially Disabled": REFR line 11352, ACHR 4487, the projectile / hazard placements 3206.
#   record flag 0x20 "Deleted": every record's header, Core/wbInterface.pas 20552-20554 (IsDeleted: _Flags and $20).
#   XESP "Enable Parent" (lines 4330-4336): u32 Reference, u8 Flags (1 Set Enable State to Opposite of Parent, 2 Pop In),
#     3 unused; on REFR (11693) and ACHR (4605).
#   CNTO "Item" (3300-3305): u32 Item (sigBaseObjects), s32 Count; COCT the count (3315); on CONT (6176-6194).
#   LVLO "Leveled List Entry" (Core/wbDefinitionsCommon.pas 9062-9074, FO4 branch): u16 Level, 2 unused, u32 Item
#     (sigBaseObjects, so an LVLI nests), u16 Count, u8 Chance None, 1 unused; Count onwards optional; LLCT the count
#     (3278); on LVLI (10009-10027).
#   TERM (12671-12760): BSIZ + "Body Text" items starting at BTXT (12707); ISIZ + "Menu Items" starting at ITXT with
#     ANAM Type (4 = Submenu - Terminal) and TNAM Submenu [TERM] (12722-12753).
#   HAZD "Hazard" record (7180); PHZD "Placed Hazard" (5950), whose NAME is a PROJ or HAZD (3212).
INITIALLY_DISABLED = 0x800
DELETED = 0x20
XESP_OPPOSITE = 0x01
XESP = struct.Struct("<IB")
CNTO = struct.Struct("<Ii")
LVLO_FORM_OFFSET = 4
ANAM_SUBMENU = 4
LEVELED = "LVLI"
EDID_KEEP = {"CONT", "LVLI", "TERM", "HAZD"}
# Trap kinds by base editor id (a hypothesis over FO4's naming: no record flag marks a trap). Checked in this order,
# after "Trapper" (the raider outfit and NPCs) is taken out of the name. "trap" wants a word start (CamelCase or a
# separator: not Strap, Contraption, Extrapolator) and not a Trapdoor; "mine" wants the explosive's CamelCase word
# (MineFrag, MineBottlecap, MinePlasma, MinePulse, MineCryo, MineNuke, LandMines, Mine01: not MineCart, MinerOutfit,
# LC_MinesDrainage).
TRAP_KINDS = (("bear_trap", re.compile(r"beartrap", re.I)),
              ("tripwire", re.compile(r"tripwire", re.I)),
              ("gas", re.compile(r"gas.*trap|trap.*gas", re.I)),
              ("oil", re.compile(r"oil.*trap|trap.*oil", re.I)),
              ("mine", re.compile(r"(^[mM]|M)ines?(?=Frag|Bottlecap|Plasma|Pulse|Cryo|Nuke|Nuclear|[0-9_]|$)")),
              ("trap", re.compile(r"(^|[^a-z])trap(?!per|door)", re.I)))
TRAPPER = re.compile(r"trapper", re.I)
MAX_PARENT_PASSES = 4
NO_HIT = 1 << 30
TOP = 20


def trap_kind(edid):
    name = TRAPPER.sub("", edid or "")
    for kind, rx in TRAP_KINDS:
        if rx.search(name):
            return kind
    return None


def xesp(d):
    """(parent form id, flags) of an XESP, or None when shorter than the 5 bytes read."""
    if len(d) < XESP.size:
        return None
    return XESP.unpack_from(d)


def plugin_masters(path):
    with fl.Plugin(path) as p:
        return [fl.zstring(d) for s, d in fl.iter_subrecords(fl.record_data(p.buf, 0)) if s == b"MAST"]


def plugin_names(paths):
    """One spelling per plugin for the form keys: the first plugin is "Fallout4.esm" (the census's spelling), the
    others as a later plugin's MAST names them, else the file name; a case-insensitive disk opens fallout4.esm too."""
    canon = {}
    first = os.path.basename(paths[0])
    if first.casefold() == "fallout4.esm":
        canon[first.casefold()] = "Fallout4.esm"
    for path in paths[1:]:
        for m in plugin_masters(path):
            canon.setdefault(m.casefold(), m)
    return [canon.setdefault(os.path.basename(p).casefold(), os.path.basename(p)) for p in paths], canon


class PluginKeys(ic.Keys):
    """interior_census.py's form keys with the owner plugin spelled one way (plugin_names) whether it is named by the
    command line or by a MAST subrecord."""

    def __init__(self, canon):
        super().__init__()
        self.canon = canon

    def spell(self, name):
        return self.canon.get(name.casefold(), name)

    def add(self, name):
        self.names.append(self.spell(name))

    def key(self, pi, masters, fid):
        mi = fid >> 24
        owner = self.spell(masters[mi]) if mi < len(masters) else self.names[pi]
        return "%06X:%s" % (fid & 0xFFFFFF, owner)


def walk_plugin(path, pi, keys, on_base, on_cell, on_ref, on_world=None):
    """One plugin, streamed: on_base(K, typ, off, fid) for every top-level base record; on_cell(K, key, interior,
    world, fields, plugin) for every CELL (returns the state passed on to on_ref); on_ref(state, typ, off, flags,
    fid, K) for every placed reference of every cell's children (state None for a cell on_cell declined);
    on_world(K, key, edid)."""
    keys.add(os.path.basename(path))
    name = keys.names[pi]
    with fl.Plugin(path) as p:
        buf = p.buf
        hdr = list(fl.iter_subrecords(fl.record_data(buf, 0)))
        masters = [fl.zstring(d) for s, d in hdr if s == b"MAST"]
        K = lambda fid: keys.key(pi, masters, fid)  # noqa: E731
        for item in fl.iter_items(buf, p.body, len(buf)):
            if item[0] != "GRUP":
                continue
            _g, off, end, label, _gt = item
            if label == b"CELL":
                _walk_cells(buf, off + 24, end, None, K, name, on_cell, on_ref)
            elif label == b"WRLD":
                world = None
                for it in fl.iter_items(buf, off + 24, end):
                    if it[0] == "GRUP":
                        if it[4] == ic.GROUP_WORLD and world is not None:
                            _walk_cells(buf, it[1] + 24, it[2], world, K, name, on_cell, on_ref)
                        continue
                    typ, roff, _flags, fid = it
                    if typ == b"WRLD":
                        world = K(fid)
                        if on_world:
                            eid = next((fl.zstring(d) for s, d in fl.iter_subrecords(fl.record_data(buf, roff))
                                        if s == b"EDID"), "")
                            on_world(world, eid)
            else:
                for rec in fl.iter_items(buf, off + 24, end):
                    if rec[0] != "GRUP":
                        on_base(K, buf, rec[0], rec[1], rec[3])


def _walk_cells(buf, start, end, world, K, plugin, on_cell, on_ref):
    state, cell_key = None, None
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            _g, off, gend, label, gtype = item
            if gtype in (ic.GROUP_INT_BLOCK, ic.GROUP_INT_SUB, ic.GROUP_EXT_BLOCK, ic.GROUP_EXT_SUB):
                _walk_cells(buf, off + 24, gend, world, K, plugin, on_cell, on_ref)
            elif gtype == ic.GROUP_CELL and cell_key is not None and K(ic.u32(label)) == cell_key:
                _walk_children(buf, off + 24, gend, state, K, on_ref)
            continue
        typ, off, rflags, fid = item
        if typ != b"CELL":
            state = cell_key = None
            continue
        cell_key = K(fid)
        fields = list(fl.iter_subrecords(fl.record_data(buf, off)))
        flags = next((struct.unpack_from("<H", d)[0] for s, d in fields if s == b"DATA" and len(d) >= 2), 0)
        interior = world is None and bool(flags & ic.CELL_INTERIOR)
        # a CELL re-saved with the Deleted flag is gone from the game with everything in it (CellMerge and
        # interior_census.py drop it too): on_cell takes it back and returns None, so its own children are not read
        state = on_cell(K, cell_key, interior, world, fields, plugin, deleted=bool(rflags & DELETED))
        if rflags & DELETED:
            cell_key = None


def _walk_children(buf, start, end, state, K, on_ref):
    for item in fl.iter_items(buf, start, end):
        if item[0] == "GRUP":
            _walk_children(buf, item[1] + 24, item[2], state, K, on_ref)
        elif item[0] in ic.PLACED:
            on_ref(state, buf, item[0], item[1], item[2], item[3], K)


class Content:
    """The census: read(paths) streams the plugins, then result() computes the per-cell answers."""

    def __init__(self, wanted=None):
        self.wanted = wanted                    # cell form keys to measure, None = every interior
        self.names, self.canon = [], {}         # plugin spellings (plugin_names)
        self.keys = None
        self.sigs = {}                          # base form key -> record signature
        self.edids = {}                         # base form key -> editor id (CONT, LVLI, TERM, HAZD, trap names)
        self.cont = {}                          # CONT key -> [(item key, count)]
        self.lvli = {}                          # LVLI key -> [item key]
        self.term = {}                          # TERM key -> {"items", "bodies", "submenus": [TERM key]}
        self.cells = {}                         # measured cell key -> {"editor_id", "plugins", "refs": {}}
        self.ref_cell = {}                      # measured ref key -> cell key (the last plugin's copy wins)
        self.worlds = {}                        # WRLD key -> editor id
        self.placed = {}                        # parent ref key (found outside) -> {"place", "parent", "opposite"}
        self.unresolved = set()                 # parent ref keys the second walk gave up on (MAX_PARENT_PASSES)

    # ---------------------------------------------------------------------------------------------- pass 1
    def read(self, paths):
        self.names, self.canon = plugin_names(paths)
        self.keys = PluginKeys(self.canon)
        for pi, path in enumerate(paths):
            walk_plugin(path, pi, self.keys, self.on_base, self.on_cell, self.on_ref, self.on_world)
        self.resolve_parents(paths)

    def on_world(self, key, edid):
        self.worlds[key] = edid or key

    def on_base(self, K, buf, typ, off, fid):
        key = K(fid)
        sig = typ.decode("ascii")
        self.sigs[key] = sig
        keep = sig in EDID_KEEP
        if not keep:
            # only the editor id is wanted: stop at the first field (EDID comes first when present)
            for s, d in fl.iter_subrecords(fl.record_data(buf, off)):
                if s == b"EDID" and trap_kind(fl.zstring(d)):
                    self.edids[key] = fl.zstring(d)
                elif s == b"EDID" and key in self.edids:
                    del self.edids[key]         # an override renamed it away from a trap name
                break
            return
        fields = list(fl.iter_subrecords(fl.record_data(buf, off)))
        self.edids[key] = next((fl.zstring(d) for s, d in fields if s == b"EDID"), "")
        if sig == "CONT":
            self.cont[key] = [(K(ic.u32(d)), CNTO.unpack_from(d)[1]) for s, d in fields
                              if s == b"CNTO" and len(d) >= CNTO.size and ic.u32(d)]
        elif sig == "LVLI":
            self.lvli[key] = [K(ic.u32(d, LVLO_FORM_OFFSET)) for s, d in fields
                              if s == b"LVLO" and len(d) >= LVLO_FORM_OFFSET + 4 and ic.u32(d, LVLO_FORM_OFFSET)]
        elif sig == "TERM":
            t = {"items": 0, "bodies": 0, "submenus": []}
            item_type = None
            for s, d in fields:
                if s == b"BTXT":
                    t["bodies"] += 1
                elif s == b"ITXT":
                    t["items"] += 1
                    item_type = None
                elif s == b"ANAM" and len(d) >= 1:
                    item_type = d[0]
                elif s == b"TNAM" and len(d) >= 4 and ic.u32(d):
                    # every TNAM opens a submenu; the type is kept only as a check (ANAM 4 = Submenu - Terminal)
                    t["submenus"].append(K(ic.u32(d)))
                    if item_type is not None and item_type != ANAM_SUBMENU:
                        t.setdefault("odd_types", []).append(item_type)
            self.term[key] = t

    def on_cell(self, K, key, interior, world, fields, plugin, deleted=False):
        if deleted:
            gone = self.cells.pop(key, None)
            for ref in (gone or {}).get("refs", {}):
                self.ref_cell.pop(ref, None)
            return None
        if not interior or (self.wanted is not None and key not in self.wanted):
            return None
        cell = self.cells.get(key)
        if cell is None:
            cell = self.cells[key] = {"key": key, "editor_id": "", "plugins": [], "refs": {}}
        cell["plugins"].append(plugin)
        eid = next((fl.zstring(d) for s, d in fields if s == b"EDID"), "")
        if eid:
            cell["editor_id"] = eid
        return cell

    def on_ref(self, cell, buf, typ, off, flags, fid, K):
        if cell is None and not self.ref_cell:
            return                                          # nothing to take back yet (the first plugin, mostly)
        ref = K(fid)
        prev = self.ref_cell.pop(ref, None)
        if prev is not None:
            self.cells[prev]["refs"].pop(ref, None)         # a later plugin's copy of the ref replaces the earlier one
        if cell is None or flags & DELETED:
            return                                          # it stands in a cell not measured now, or is deleted
        base, parent, opposite = None, None, False
        for s, d in fl.iter_subrecords(fl.record_data(buf, off)):
            if s == b"NAME" and len(d) >= 4:
                base = K(ic.u32(d))
            elif s == b"XESP":
                x = xesp(d)
                if x and x[0]:
                    parent, opposite = K(x[0]), bool(x[1] & XESP_OPPOSITE)
        self.ref_cell[ref] = cell["key"]
        cell["refs"][ref] = (typ.decode("ascii"), base, bool(flags & INITIALLY_DISABLED), parent, opposite)

    # ---------------------------------------------------------------------------------------------- pass 2
    def resolve_parents(self, paths):
        """Enable parents that stand outside the measured cells: walk the plugins again for just those references
        (where they stand, their own parent), repeating while the chain leads further out, at most
        MAX_PARENT_PASSES times; what is still wanted after that is `unresolved`."""
        wanted = {r[3] for c in self.cells.values() for r in c["refs"].values() if r[3]} - set(self.ref_cell)
        passes = 0
        while wanted and passes < MAX_PARENT_PASSES:
            passes += 1
            found = {}
            keys = PluginKeys(self.canon)

            def on_cell(K, key, interior, world, fields, plugin, deleted=False):
                if deleted:
                    for ref in [r for r, f in found.items() if f and f["place"][0] != "world" and f["place"][1] == key]:
                        found.pop(ref)
                    return None
                eid = next((fl.zstring(d) for s, d in fields if s == b"EDID"), "")
                return (key, interior, world, eid)

            def on_ref(state, buf, typ, off, flags, fid, K):
                ref = K(fid)
                if ref not in wanted:
                    return
                if flags & DELETED or state is None:
                    found.pop(ref, None)
                    return
                key, interior, world, eid = state
                parent, opposite = None, False
                for s, d in fl.iter_subrecords(fl.record_data(buf, off)):
                    if s == b"XESP":
                        x = xesp(d)
                        if x and x[0]:
                            parent, opposite = K(x[0]), bool(x[1] & XESP_OPPOSITE)
                        break
                # a cell of the interior group whose DATA lacks the interior flag is still an interior here
                place = ("world", world) if world is not None else ("interior", key, eid)
                found[ref] = {"place": place, "parent": parent, "opposite": opposite,
                              "disabled": bool(flags & INITIALLY_DISABLED)}

            for pi, path in enumerate(paths):
                walk_plugin(path, pi, keys, lambda *a: None, on_cell, on_ref)
            for ref in wanted:
                self.placed[ref] = found.get(ref)        # None: not placed in the plugins read
            wanted = {f["parent"] for f in found.values() if f and f["parent"]} - set(self.ref_cell) - set(self.placed)
        self.unresolved = wanted

    # ---------------------------------------------------------------------------------------------- answers
    def leaves(self, item, memo, stack=None):
        """The distinct leaf records (key -> signature) reached from an item through its LVLIs. `memo` (LVLI key ->
        leaves) is filled only with complete answers: a list is memoized once its whole strongly connected
        component is done, every member of a cycle sharing the same leaves, so the answer does not depend on
        which list was asked first."""
        sig = self.sigs.get(item, "?")
        if sig != LEVELED:
            return {item: sig}
        return self._leaves(item, memo, {} if stack is None else stack)[0]

    def _leaves(self, item, memo, stack):
        """(leaves, lowest stack index reached, members not yet memoized) of an LVLI; stack: key -> index on the path."""
        if item in memo:
            return memo[item], NO_HIT, []
        if item in stack:
            return {}, stack[item], []
        idx = stack[item] = len(stack)
        out, low, members = {}, NO_HIT, [item]
        for entry in self.lvli.get(item, ()):
            sig = self.sigs.get(entry, "?")
            if sig != LEVELED:
                out[entry] = sig
                continue
            sub, sublow, submembers = self._leaves(entry, memo, stack)
            out.update(sub)
            low = min(low, sublow)
            members += submembers
        del stack[item]
        if low >= idx:                          # nothing above on the path was reached: complete for the whole cycle
            for m in members:
                memo[m] = out
            return out, NO_HIT, []
        return out, low, members

    def terminal(self, key, memo, stack=None):
        """{"depth", "reach" (the distinct TERM keys of the menu tree, this one included), "cycle", "missing" (TNAM
        submenus that are no TERM read)} of a TERM's menu tree; a submenu already on the path is cut and flagged.
        `memo` keeps only terminals that are in no cycle, so a cycle member's answer is always the one measured from
        itself."""
        if key not in self.term:
            return {"depth": 0, "reach": set(), "cycle": False, "missing": 1}
        return self._terminal(key, memo, {} if stack is None else stack)[0]

    def _terminal(self, key, memo, stack):
        if key in memo:
            return memo[key], NO_HIT
        if key in stack:
            return None, stack[key]
        idx = stack[key] = len(stack)
        t = self.term[key]
        depth, reach, cycle, missing, low = 0, {key}, False, 0, NO_HIT
        for sub in t["submenus"]:
            if sub not in self.term:
                missing += 1
                continue
            r, sublow = self._terminal(sub, memo, stack)
            low = min(low, sublow)
            if r is None:                       # on the path: the cycle is cut here
                cycle = True
                continue
            depth = max(depth, r["depth"] + 1)
            reach |= r["reach"]
            cycle = cycle or r["cycle"]
            missing += r["missing"]
        del stack[key]
        out = {"depth": depth, "reach": reach, "cycle": cycle, "missing": missing}
        if low > idx:                           # in no cycle: complete whoever asks
            memo[key] = out
            return out, NO_HIT
        return out, (NO_HIT if low == idx else low)

    def place_name(self, ref):
        """Where a reference stands: the measured cell's editor id, another interior's, "world:<edid>", or None."""
        cell = self.ref_cell.get(ref)
        if cell is not None:
            return self.cells[cell]["editor_id"] or cell
        p = self.placed.get(ref)
        if not p:
            return None
        if p["place"][0] == "interior":
            return p["place"][2] or p["place"][1]
        world = p["place"][1]
        return "world:" + str(self.worlds.get(world, world))

    def parent_of(self, ref):
        cell = self.ref_cell.get(ref)
        if cell is not None:
            return self.cells[cell]["refs"][ref][3]
        p = self.placed.get(ref)
        return p["parent"] if p else None

    def chain(self, ref):
        """[ref, parent, grandparent, ...] up to the root: (chain, cycle, cut) with the chain cut where it repeats
        (cycle: the frozenset of the repeating refs) or where the second walk gave up (cut: True)."""
        out, seen = [ref], {ref}
        while True:
            p = self.parent_of(out[-1])
            if not p:
                return out, None, out[-1] in self.unresolved
            if p in seen:
                return out, frozenset(out[out.index(p):]), False
            seen.add(p)
            out.append(p)

    def cell_row(self, key, cell, leaf_memo, term_memo):
        refs = cell["refs"]
        row = {"formkey": key, "editor_id": cell["editor_id"], "plugins": cell["plugins"], "refs": len(refs)}
        # C1
        disabled = [r for r, v in refs.items() if v[2]]
        parented = {r: v[3] for r, v in refs.items() if v[3]}
        parents = Counter(parented.values())
        outside = []
        for p, n in sorted(parents.items()):
            if self.ref_cell.get(p) == key:
                continue
            outside.append({"ref": p, "in": self.place_name(p), "children": n})
        deepest, deepest_refs, cycles, cut = 0, [], set(), 0
        for r in parented:
            ch, cyc, was_cut = self.chain(r)
            if cyc:
                cycles.add(cyc)
            cut += was_cut
            if len(ch) - 1 > deepest:
                deepest, deepest_refs = len(ch) - 1, ch
        row.update({"disabled": len(disabled), "enable_parent": len(parented),
                    "disabled_without_parent": sum(1 for r in disabled if r not in parented),
                    "opposite_state": sum(1 for v in refs.values() if v[3] and v[4]),
                    "parents": len(parents), "parents_outside": outside,
                    "deepest_chain": deepest, "deepest_chain_refs": deepest_refs, "chain_cycles": len(cycles),
                    "chains_cut": cut})
        # C3
        conts = [v[1] for v in refs.values() if v[1] and self.sigs.get(v[1]) == "CONT"]
        lists = [v[1] for v in refs.values() if v[1] and self.sigs.get(v[1]) == LEVELED]
        direct, leaves, unresolved = Counter(), {}, set()
        for c in conts:
            for item, _n in self.cont.get(c, ()):
                direct[self.sigs.get(item, "?")] += 1
                leaves.update(self.leaves(item, leaf_memo))
        for lv in lists:
            leaves.update(self.leaves(lv, leaf_memo))
        for item, sig in leaves.items():
            if sig == "?":
                unresolved.add(item)
        row.update({"containers": len(conts), "container_bases": len(set(conts)), "leveled_item_refs": len(lists),
                    "direct_contents": dict(sorted(direct.items())),
                    "leaf_types": dict(sorted(Counter(leaves.values()).items())),
                    "leaves_unresolved": len(unresolved)})
        row["_leaves"] = leaves
        # C7
        terminals = []
        for r, v in sorted(refs.items()):
            if v[1] and self.sigs.get(v[1]) == "TERM":
                t = self.terminal(v[1], term_memo)
                top = self.term.get(v[1], {"items": 0, "bodies": 0, "submenus": []})
                tree = [self.term[k] for k in t["reach"]]
                terminals.append({"ref": r, "base": v[1], "editor_id": self.edids.get(v[1], ""), "depth": t["depth"],
                                  "menu_items": top["items"], "body_texts": top["bodies"],
                                  "menu_items_total": sum(x["items"] for x in tree),
                                  "body_texts_total": sum(x["bodies"] for x in tree),
                                  "terminals_total": len(t["reach"]), "cycle": t["cycle"],
                                  "submenus_missing": t["missing"]})
        row["terminals"] = terminals
        row["terminal_depths"] = dict(sorted(Counter(str(t["depth"]) for t in terminals).items()))
        # C9
        traps, kinds = Counter(), Counter()
        for r, v in refs.items():
            sig = self.sigs.get(v[1], "?") if v[1] else "?"
            eid = self.edids.get(v[1], "") if v[1] else ""
            kind = trap_kind(eid)
            if v[0] == "PHZD" or sig == "HAZD":
                kind = "hazard"
            if kind:
                traps[f"{eid or v[1] or '?'} ({sig})"] += 1
                kinds[kind] += 1
        row.update({"trap_refs": sum(traps.values()), "traps": dict(sorted(traps.items())),
                    "trap_kinds": dict(sorted(kinds.items()))})
        return row

    def result(self, plugins=None, census_path=None):
        plugins = plugins or self.names
        leaf_memo, term_memo = {}, {}
        rows = [self.cell_row(k, c, leaf_memo, term_memo) for k, c in self.cells.items()]
        rows.sort(key=lambda r: (r["formkey"].split(":")[1] != plugins[0], r["editor_id"].casefold(), r["formkey"]))
        summed = ("disabled", "enable_parent", "disabled_without_parent", "opposite_state", "chain_cycles", "chains_cut",
                  "containers", "leveled_item_refs", "trap_refs")
        totals = Counter({k: 0 for k in ("cells", "refs", "cells_with_enable_state", "parents_outside",
                                         "parents_outside_unplaced", "parents_unresolved", "deepest_chain", "terminals",
                                         "cells_with_terminals", "terminal_cycles", "cells_with_traps",
                                         "leaves_unresolved") + summed})
        leaves, depths, base_depths, traps, kinds, direct = {}, Counter(), {}, Counter(), Counter(), Counter()
        for r in rows:
            totals["cells"] += 1
            totals["refs"] += r["refs"]
            for k in summed:
                totals[k] += r[k]
            totals["cells_with_enable_state"] += bool(r["disabled"] or r["enable_parent"])
            totals["parents_outside"] += len(r["parents_outside"])
            totals["parents_outside_unplaced"] += sum(1 for p in r["parents_outside"] if p["in"] is None)
            totals["deepest_chain"] = max(totals["deepest_chain"], r["deepest_chain"])
            totals["terminals"] += len(r["terminals"])
            totals["cells_with_terminals"] += bool(r["terminals"])
            totals["cells_with_traps"] += bool(r["trap_refs"])
            totals["leaves_unresolved"] += r["leaves_unresolved"]
            leaves.update(r.pop("_leaves"))
            direct.update(r["direct_contents"])
            for t in r["terminals"]:
                depths[str(t["depth"])] += 1
                base_depths[t["base"]] = t["depth"]
                totals["terminal_cycles"] += t["cycle"]
            traps.update(r["traps"])
            kinds.update(r["trap_kinds"])
        totals["parents_unresolved"] = len(self.unresolved)
        totals["leaf_records"] = len(leaves)
        totals["terminal_bases"] = len(base_depths)
        totals["terminal_depth_max"] = max(base_depths.values(), default=0)

        def top(key, n=TOP):
            best = sorted((r for r in rows if key(r)), key=lambda r: (-key(r), r["editor_id"]))[:n]
            return [{"formkey": r["formkey"], "editor_id": r["editor_id"], "count": key(r)} for r in best]
        return {"note": "scripts/terrain/interior_content.py: C1 enable state, C3 loot leaf types, C7 terminal depth, "
                        "C9 traps of the interior cells (docs/terrain/interior-batches.md, Content census)",
                "plugins": plugins, "census": census_path,
                "totals": dict(sorted(totals.items())),
                "leaf_types": dict(sorted(Counter(leaves.values()).items())),
                "direct_contents": dict(sorted(direct.items())),
                "terminal_depths": dict(sorted(depths.items(), key=lambda kv: int(kv[0]))),
                "terminal_base_depths": dict(sorted(Counter(str(d) for d in base_depths.values()).items(),
                                                    key=lambda kv: int(kv[0]))),
                "traps": dict(sorted(traps.items())), "trap_kinds": dict(sorted(kinds.items())),
                "top_enable_state": top(lambda r: r["disabled"] + r["enable_parent"]),
                "top_deepest_chain": top(lambda r: r["deepest_chain"]),
                "top_terminals": top(lambda r: len(r["terminals"])),
                "top_traps": top(lambda r: r["trap_refs"]),
                "cells": rows}


def census_cells(census, names=()):
    """The form keys of a census's cells, or of the ones named (editor id or form key) in `names`."""
    rows = census.get("cells", [])
    if not names:
        return {c["formkey"] for c in rows}
    want = {n.casefold() for n in names}
    keys = {c["formkey"] for c in rows if c["formkey"].casefold() in want or (c.get("editor_id") or "").casefold() in want}
    missing = want - {c["formkey"].casefold() for c in rows} - {(c.get("editor_id") or "").casefold() for c in rows}
    if missing:
        raise ValueError(f"cells not in the census: {sorted(missing)}")
    return keys


def content(paths, wanted=None, census_path=None):
    c = Content(wanted)
    c.read(paths)
    return c.result(c.names, census_path)


def markdown(r):
    t = r["totals"]
    lines = [f"# Interior content census ({', '.join(r['plugins'])})", "",
             f"{t['cells']} cells, {t['refs']} placed references" + (f", cells from {r['census']}" if r["census"] else "") + ".",
             "",
             "## C1 Enable state", "",
             f"- Initially disabled (flag 0x800): {t['disabled']} refs; with an enable parent (XESP): {t['enable_parent']} "
             f"({t['opposite_state']} opposite state); disabled without a parent: {t['disabled_without_parent']}.",
             f"- Cells with either: {t['cells_with_enable_state']} of {t['cells']}. Parents outside their cell: "
             f"{t['parents_outside']} ({t['parents_outside_unplaced']} not placed in the plugins read). Deepest chain: "
             f"{t['deepest_chain']}; parent cycles: {t['chain_cycles']}; chains cut after {MAX_PARENT_PASSES} hops outside: "
             f"{t['chains_cut']} ({t['parents_unresolved']} parents unresolved).",
             "- Most: " + ", ".join(f"{c['editor_id'] or c['formkey']} {c['count']}" for c in r["top_enable_state"][:10]) + ".",
             "", "## C3 Loot", "",
             f"- Placed containers: {t['containers']}; leveled-item refs: {t['leveled_item_refs']}; distinct leaf records "
             f"reached through the LVLIs: {t['leaf_records']} ({t['leaves_unresolved']} in no plugin read).",
             "- Leaf types: " + ", ".join(f"{k} {n}" for k, n in r["leaf_types"].items()) + ".",
             "- Direct container entries: " + ", ".join(f"{k} {n}" for k, n in r["direct_contents"].items()) + ".",
             "", "## C7 Terminals", "",
             f"- Placed terminals: {t['terminals']} in {t['cells_with_terminals']} cells, {t['terminal_bases']} TERM bases, "
             f"deepest menu {t['terminal_depth_max']}, cycles {t['terminal_cycles']}.",
             "- Depth of the placed terminals: " + ", ".join(f"{d}: {n}" for d, n in r["terminal_depths"].items()) + ".",
             "- Depth of the TERM bases: " + ", ".join(f"{d}: {n}" for d, n in r["terminal_base_depths"].items()) + ".",
             "", "## C9 Traps", "",
             f"- Trap refs: {t['trap_refs']} in {t['cells_with_traps']} cells; by kind: "
             + ", ".join(f"{k} {n}" for k, n in r["trap_kinds"].items()) + ".",
             "- By base: " + ", ".join(f"{k} {n}" for k, n in sorted(r["traps"].items(), key=lambda kv: -kv[1])[:30]) + ".",
             "- Most: " + ", ".join(f"{c['editor_id'] or c['formkey']} {c['count']}" for c in r["top_traps"][:10]) + ".",
             ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="", help="Markdown summary (default: --out with .md)")
    ap.add_argument("--census", default="", help="interior-census.json: measure its cells only")
    ap.add_argument("--cells", action="append", default=[], help="with --census: only these editor ids or form keys")
    ap.add_argument("plugins", nargs="+")
    a = ap.parse_args(argv)
    if os.path.basename(a.plugins[0]).casefold() != "fallout4.esm":
        sys.exit("Fallout4.esm comes first")
    md = a.md or os.path.splitext(a.out)[0] + ".md"
    for p in a.plugins:
        if os.path.abspath(p) in (os.path.abspath(a.out), os.path.abspath(md)):
            sys.exit("--out is one of the plugins")
    wanted = None
    if a.census:
        with open(a.census, encoding="utf-8-sig") as f:
            wanted = census_cells(json.load(f), a.cells)
    elif a.cells:
        sys.exit("--cells needs --census")
    result = content(a.plugins, wanted, a.census or None)
    text = markdown(result)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    os.replace(tmp, a.out)
    with open(md, "w", encoding="utf-8") as f:
        f.write(text)
    print(json.dumps(result["totals"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
