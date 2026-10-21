"""Synthetic-fixture tests for the placement-frame oracle."""
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "oracles"))
from fo4sf import fo4land  # noqa: E402
import placement_frame as pf  # noqa: E402

G = fo4land.GRID


def rec(typ, fid, fields, compress=False):
    data = b"".join(sig + struct.pack("<H", len(d)) + d for sig, d in fields)
    flags = 0
    if compress:
        data = struct.pack("<I", len(data)) + zlib.compress(data)
        flags = fo4land.COMPRESSED
    return typ + struct.pack("<III", len(data), flags, fid) + b"\0" * 8 + data


def grup(label, gtype, items):
    body = b"".join(items)
    if isinstance(label, int):
        label = struct.pack("<I", label)
    return b"GRUP" + struct.pack("<I4si", 24 + len(body), label, gtype) + b"\0" * 8 + body


def refr(fid, base, pos, rot=(0.0, 0.0, 0.0)):
    return rec(b"REFR", fid, [(b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", *pos, *rot))])


def cell_rec(fid, x, y, edid=""):
    fields = [(b"XCLC", struct.pack("<ii", x, y))]
    if edid:
        fields.append((b"EDID", edid.encode("cp1252") + b"\0"))
    return rec(b"CELL", fid, fields)


def land_rec(fid):
    # minimal VHGT so the cell is counted as having land
    steps = fo4land.encode_vhgt(0.0, [[0] * G for _ in range(G)])
    return rec(b"LAND", fid, [(b"VHGT", steps)])


def world_plugin(cells_with_land, refs_by_cell, world_edid="Commonwealth", wfid=0x000800):
    """Build a minimal plugin with a worldspace containing the given cells and refs."""
    tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 0.94, 0, 0)), (b"CNAM", b"test\0")])
    cell_items = []
    for (cx, cy), refs in refs_by_cell.items():
        cfid = 0x001000 + cx * 100 + cy
        cell = cell_rec(cfid, cx, cy, f"Cell{cx}_{cy}")
        children = []
        if (cx, cy) in cells_with_land:
            children.append(land_rec(0x002000 + cx * 100 + cy))
        for i, (rfid, pos) in enumerate(refs):
            children.append(refr(rfid, 0x000001, pos))
        if children:
            # cell children group type 6, then temp type 9
            temp = grup(9, 9, children)
            cell_group = grup(cfid, 6, [temp])
            cell_items.append(cell + cell_group)
        else:
            cell_items.append(cell)
    # world children group type 1 containing the cells (simplified: put cells directly; real layout uses blocks)
    # For the walker, exterior cells live under blocks (type 4/5). Put a simple block.
    block = grup(0, 4, cell_items)  # label ignored for type 4
    world_children = grup(wfid, 1, [block])
    world = rec(b"WRLD", wfid, [(b"EDID", world_edid.encode() + b"\0")])
    wrld_group = grup(b"WRLD", 0, [world + world_children])
    return tes4 + wrld_group


class PlacementFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_ref_inside_core_no_flag(self):
        # core has cell (0, 0) with land
        core = world_plugin({(0, 0)}, {(0, 0): []})
        # plugin places a ref at (100, 100) which is cell (0, 0)
        plugin = world_plugin(set(), {(0, 0): [(0x000ABC, (100.0, 100.0, 0.0))]})
        cp = self.write("core.esm", core)
        pp = self.write("mission.esp", plugin)
        result = pf.audit(cp, pp)
        self.assertEqual(result["flags"], 0)
        self.assertEqual(result["refs"], 1)
        self.assertTrue(result["entries"][0]["in_core"])
        self.assertTrue(result["entries"][0]["parent_ok"])

    def test_ref_outside_core_flagged(self):
        core = world_plugin({(0, 0)}, {(0, 0): []})
        # ref at (5000, 0) is cell (1, 0), which core lacks
        plugin = world_plugin(set(), {(1, 0): [(0x000DEF, (5000.0, 0.0, 0.0))]})
        cp = self.write("core.esm", core)
        pp = self.write("mission.esp", plugin)
        result = pf.audit(cp, pp)
        self.assertEqual(result["flags"], 1)
        self.assertEqual(result["flagged"], ["00000DEF"])
        self.assertFalse(result["entries"][0]["in_core"])

    def test_parent_mismatch_flagged(self):
        core = world_plugin({(0, 0), (1, 0)}, {(0, 0): [], (1, 0): []})
        # parent CELL is (0, 0) but position is in (1, 0)
        plugin = world_plugin(set(), {(0, 0): [(0x000111, (5000.0, 0.0, 0.0))]})
        cp = self.write("core.esm", core)
        pp = self.write("mission.esp", plugin)
        result = pf.audit(cp, pp)
        self.assertEqual(result["flags"], 1)
        self.assertEqual(result["entries"][0]["flag"], "parent_cell_mismatch")

    def test_cli_exit_code(self):
        core = world_plugin({(0, 0)}, {(0, 0): []})
        plugin = world_plugin(set(), {(1, 0): [(0x000222, (5000.0, 0.0, 0.0))]})
        cp = self.write("core.esm", core)
        pp = self.write("mission.esp", plugin)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts/oracles/placement_frame.py"),
                            "--core", cp, "--plugin", pp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("flags: 1", r.stdout)


if __name__ == "__main__":
    unittest.main()
