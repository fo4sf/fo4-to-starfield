"""dotnet/MapMarkers on a synthetic core (the actual terrain writer, dotnet/TerrainOverlays, on the synthetic master of
test_terrain_reference_identity with the map-marker template), never a game: the quest's Markers are the core's own
MapMarker REFRs in FormID order and LocalX / LocalY / LocalZ their written positions (docs/terrain/map-markers.md
"Markers in the merged world"); the plugin's overrides of those REFRs (the marker's own name shown, the arrival lifted,
docs/terrain/map-markers.md "Overrides"); plus the Papyrus script's contract (it cannot be compiled here)."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402

SCRIPT = ROOT / "scripts/mapmarkers/FO4SF_MapMarkers.psc"
Z_LIFT = 2.5                     # dotnet/MapMarkers DefaultZLift, metres above the core's sampled terrain height
USE_LOCATION_NAME, VISIBLE = 0x8, 0x1   # map-marker FNAM bits (docs/terrain/map-markers.md)


def build(dotnet, project):
    proc = subprocess.run([dotnet, "build", str(ROOT / "dotnet" / project), "-c", "Release", "--nologo"],
                          capture_output=True, text=True)
    if proc.returncode:
        raise AssertionError(proc.stdout + proc.stderr)
    return ROOT / f"dotnet/{project}/bin/Release/net9.0/{project}.dll"


class MapMarkersPluginTests(unittest.TestCase):
    run_writer = tri.TerrainReferenceIdentityTests.run_writer

    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual writer test")
        fixture = build(cls.dotnet, "TerrainIdentityFixture")
        cls.writer = Path(os.environ.get("FO4SF_TERRAIN_WRITER", build(cls.dotnet, "TerrainOverlays")))
        cls.tool = build(cls.dotnet, "MapMarkers")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-mapmarkers-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "map-marker"], capture_output=True, check=True)
        cls.params = {                                   # test_terrain_map_marker_writer's synthetic overlay
            "plugin": "Synthetic.esm", "hmin": 0, "hmax": 1, "alignment": "absolute", "hnam": 0,
            "objects": "objects.json", "overlays": [{"world": "SyntheticWorld", "block": "SyntheticBlock",
            "location": "SyntheticLocation", "tag": "Synthetic", "n": 2, "cell_min": 0, "cell_max": 1,
            "btd_path": "Terrain/Synthetic.btd", "fnam": [0] * 4, "bounds_min_m": 0, "bounds_max_m": 200,
            "spawn": [1, 1, 2], "spawn_cell": [1, 0], "coc": "SyntheticSpawn",
            "anchor": {"form_id": 0x800, "edid": "SyntheticAnchor", "local": [1, 1, 2]}}]}
        cls.objects = {"world": "SyntheticWorld", "bases": [{"edid": "SyntheticBase", "model": "synthetic.nif"}],
                       "refs": [{"src": "000001:Synthetic.esm", "base": 0, "cell": [0, 0], "pos": [1, 2, 3],
                                 "rot": [0, 0, 0], "scale": 1, "disabled": False}]}
        ov = cls.params["overlays"][0]
        cls.markers = [{"tag": "RedRocket", "name": "Red Rocket Truck Stop", "pos": ov["spawn"], "cell": [0, 0]},
                       {"tag": "Sanctuary", "name": "Sanctuary Hills", "pos": [150.0, 50.0, 1.0], "cell": [1, 0]},
                       {"tag": "Concord", "name": "Concord", "pos": [50.0, 150.0, 1.5], "cell": [0, 1]}]
        ov["map_markers"] = cls.markers
        proc, cls.stage = cls.run_writer(cls, cls.objects, "core")
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.core = cls.stage / "Synthetic.esm"
        cls.ids = json.loads((cls.stage / "formids.json").read_text())["map_marker_refs"]["SyntheticWorld"]

    def tool_run(self, *argv):
        return subprocess.run([self.dotnet, str(self.tool), *map(str, argv)], capture_output=True, text=True)

    def test_build_lists_every_core_marker_with_its_written_position(self):
        out = self.root / "plugin"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("all checks pass", check.stdout)
        recs = tri.records(plugin)
        # the quest, plus an override of each core marker under the core's worldspace and persistent cell: nothing else
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"), sorted(int(v, 16) for v in self.ids.values()))
        self.assertEqual(sorted(r[0] for r in recs.values()), [b"CELL", b"QUST"] + [b"REFR"] * 3 + [b"WRLD"])
        for m in self.markers:
            sig, payload, _, flags = recs[int(self.ids[m["tag"]], 16)]
            self.assertEqual(flags & 0xC00, 0x400, m["tag"])                       # persistent, enabled
            fnam = struct.unpack("<I", tlw.field(payload, b"FNAM"))[0]
            self.assertEqual(fnam & (USE_LOCATION_NAME | VISIBLE), VISIBLE, m["tag"])  # its own name, visible
            self.assertEqual(tlw.field(payload, b"FULL"), m["name"].encode() + b"\0")
            x, y, z = struct.unpack_from("<fff", tlw.field(payload, b"DATA"))
            self.assertEqual([x, y], [float(v) for v in m["pos"][:2]])
            self.assertAlmostEqual(z, m["pos"][2] + Z_LIFT, places=4)
        self.assertEqual(check.stdout.count("  override "), 3)
        self.assertIn(f"overridden (own name shown, lifted {Z_LIFT} m)", proc.stdout)
        sig, payload, _, flags = recs[0x800]
        self.assertEqual(sig, b"QUST")
        vmad = tlw.field(payload, b"VMAD")
        self.assertIsNotNone(vmad)
        self.assertEqual(struct.unpack_from("<hH", vmad), (6, 2))
        self.assertIn(b"FO4SF_MapMarkers", vmad)
        # the three markers in FormID order, each a core reference (master index 1, after Starfield.esm)
        want = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(len(want), 3)
        got = [f & 0xFFFFFF for f in self.object_list(vmad)]
        self.assertEqual(got, want)
        # masters: Starfield.esm (the overrides' base STAT) then the core; the quest's references are the core's
        self.assertTrue(all(f >> 24 == 1 for f in self.object_list(vmad)))
        # LocalX in FormID order equals the positions the writer was given; LocalZ the lifted height the override holds
        by_id = {int(self.ids[m["tag"]], 16): m["pos"] for m in self.markers}
        self.assertIn(f"LocalX: {', '.join(self.num(by_id[i][0]) for i in want)}", check.stdout)
        self.assertIn(f"LocalZ: {', '.join(self.num(by_id[i][2] + Z_LIFT) for i in want)}", check.stdout)

    def test_z_lift_is_an_option_and_the_check_follows_it(self):
        out = self.root / "plugin-flat"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--z-lift", "0")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        recs = tri.records(plugin)
        for m in self.markers:
            z = struct.unpack_from("<fff", tlw.field(recs[int(self.ids[m["tag"]], 16)][1], b"DATA"))[2]
            self.assertAlmostEqual(z, m["pos"][2], places=4)
        self.assertEqual(self.tool_run("check", plugin, self.core, "--z-lift", "0").returncode, 0)
        other = self.tool_run("check", plugin, self.core)               # the default lift is not what was built
        self.assertEqual(other.returncode, 1, other.stdout)
        self.assertIn(f"not the core's {self.num(self.markers[0]['pos'][2])} lifted {Z_LIFT} m", other.stdout)
        bad = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-bad-lift", "--z-lift", "-1")
        self.assertEqual(bad.returncode, 2)

    def test_check_rejects_an_override_that_still_uses_the_location_name(self):
        out = self.root / "plugin-locname"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        at = data.index(b"FNAM\x04\x00") + 6                       # the first override's map-marker flags
        struct.pack_into("<I", data, at, struct.unpack_from("<I", data, at)[0] | USE_LOCATION_NAME)
        plugin.write_bytes(bytes(data))
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("override still uses the location's name", check.stdout)

    def test_many_markers_split_into_quests_of_100(self):
        params = copy.deepcopy(self.params)
        params["overlays"][0]["map_markers"] = [
            {"tag": f"M{k:03d}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
            for k in range(205)]
        saved, type(self).params = type(self).params, params
        try:
            proc, many = self.run_writer(self.objects, "core-many")
        finally:
            type(self).params = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.root / "plugin-many"
        built = self.tool_run("build", "--core", many / "Synthetic.esm", "--out", out)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("3 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", many / "Synthetic.esm")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        recs = tri.records(out / "FO4SFMapMarkers.esm")
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"QUST"), [0x800, 0x801, 0x802])
        self.assertEqual(sum(1 for r in recs.values() if r[0] == b"REFR"), 205)    # one override per marker
        lists = [self.object_list(tlw.field(recs[q][1], b"VMAD")) for q in (0x800, 0x801, 0x802)]
        self.assertEqual([len(x) for x in lists], [100, 100, 5])
        ids = [f & 0xFFFFFF for x in lists for f in x]
        self.assertEqual(ids, sorted(ids))                                     # FormID order across the quests
        self.assertEqual(len(set(ids)), 205)
        for q, cap in ((0x800, 200), (0x801, 200)):
            vmad = tlw.field(recs[q][1], b"VMAD")
            name = b"\x08\x00MaxMoves"
            at = vmad.index(name) + len(name)
            self.assertEqual(struct.unpack_from("<BBi", vmad, at), (3, 1, cap))  # int property, edited, the cap
        self.assertNotIn(b"MaxMoves", tlw.field(recs[0x802][1], b"VMAD"))       # 5 markers: the script's 40
        # a plugin missing its last quest no longer matches the core
        short = self.root / "plugin-many-short"
        three = self.tool_run("build", "--core", self.core, "--out", short)
        self.assertEqual(three.returncode, 0)
        bad = self.tool_run("check", short / "FO4SFMapMarkers.esm", many / "Synthetic.esm")
        self.assertEqual(bad.returncode, 1, bad.stdout)
        self.assertIn("1 quest(s) for 205 marker(s): 3 wanted", bad.stdout)

    def test_check_rejects_an_alias_encoded_marker(self):
        out = self.root / "plugin-alias"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        name = b"\x07\x00Markers"
        entry = data.index(name) + len(name) + 6                # type, status, u32 count
        self.assertEqual(struct.unpack_from("<Hh", data, entry), (0, -1))
        struct.pack_into("<h", data, entry + 2, 0)              # alias -1 -> 0, the form id untouched
        plugin.write_bytes(bytes(data))
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  Markers[0] is not a direct reference (alias 0, unused 0)", check.stdout)

    def test_check_rejects_a_plugin_built_from_another_core(self):
        params = copy.deepcopy(self.params)
        params["overlays"][0]["map_markers"] = self.markers[:2]
        saved, type(self).params = type(self).params, params
        try:
            proc, other = self.run_writer(self.objects, "core-two")
        finally:
            type(self).params = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.root / "plugin-two"
        self.assertEqual(self.tool_run("build", "--core", other / "Synthetic.esm", "--out", out).returncode, 0)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  Markers", check.stdout)

    def test_build_refuses_a_core_without_markers(self):
        # the plain synthetic master has no LC172 template, so the writer writes no MapMarker REFR
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        plain = self.root / "master-plain/Starfield.esm"
        plain.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.dotnet, str(fixture), str(plain)], capture_output=True, check=True)
        saved, type(self).master = type(self).master, plain
        try:
            proc, stage = self.run_writer(self.objects, "core-plain")
        finally:
            type(self).master = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self.tool_run("build", "--core", stage / "Synthetic.esm", "--out", self.root / "none")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("no MapMarker REFR", proc.stderr)

    @staticmethod
    def num(v):
        return f"{v:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def object_list(vmad):
        """Form ids of the Markers array property (type 11) in a quest VMAD."""
        name = b"\x07\x00Markers"                     # the property's u16-length-prefixed name
        pos = vmad.index(name) + len(name)
        kind, _status, count = struct.unpack_from("<BBI", vmad, pos)
        assert kind == 11, kind
        pos += 6
        out = []
        for _ in range(count):
            _zero, _alias, form = struct.unpack_from("<HhI", vmad, pos)
            out.append(form)
            pos += 8
        return out


class ScriptContractTests(unittest.TestCase):
    text = SCRIPT.read_text(encoding="utf-8")

    def test_properties_the_writer_fills(self):
        for decl in ("ObjectReference[] Property Markers", "float[] Property LocalX", "float[] Property LocalY",
                     "float[] Property LocalZ"):
            self.assertIn(decl, self.text)

    def test_offset_and_extent_match_the_repo(self):
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        import vmad_patch
        dx, dy, _ = vmad_patch.MERGE_MEASURED
        self.assertIn(f"MergeOffsetX = {dx}", self.text)
        self.assertIn(f"MergeOffsetY = {dy}", self.text)
        half = 64 // 2 * 100.0                             # core64: local -3200..3200 m
        for name, v in (("MinX", -half + dx), ("MaxX", half + dx), ("MinY", -half + dy), ("MaxY", half + dy)):
            self.assertIn(f"{name} = {v}", self.text)

    def test_a_marker_at_the_old_height_is_moved_again(self):
        # a save from before a lifted build holds the markers at the old z (Codex on #483): the reposition test
        # reads the height too, with a tolerance below the default lift, so the first pass moves them once more
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertIn("ez * ez > ZTolerance * ZTolerance", place)
        tol = float(re.search(r"float Property ZTolerance = ([0-9.]+) Auto Const", self.text).group(1))
        self.assertLess(tol, Z_LIFT)
        self.assertGreater(tol, 0.01)                                     # a landed move is within 0.01 m (22 Oct log)

    def test_moves_only_outdoors_capped_and_logged(self):
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("IsInInterior"), place.index("MoveTo"))
        # the budget is part of the loop condition, so it holds before every Enable / MoveTo (Codex 4311385104)
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        self.assertLess(loop, place.index("m.Enable"))
        self.assertEqual(place.count("moves += 1"), 1)
        self.assertEqual(place.count("MoveTo("), 1)
        self.assertRegex(place, r"m\.MoveTo\(player, x - px, y - py, z - pz, True, False\)")
        self.assertIn('Trace("moved "', place)
        self.assertNotIn("Math.", self.text)               # only the base scripts the bridge already imports


class StageTests(unittest.TestCase):
    def test_stage_builds_compiles_and_checks_against_the_core(self):
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        import make_map_markers as mm
        calls = []

        def fake_run(cmd, cwd=None):
            calls.append((cmd, cwd))
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w):
            out, core = os.path.join(d, "stage"), os.path.join(d, "FO4TerrainCore.esm")
            with open(core, "wb") as f:
                f.write(b"core bytes")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe"])
            with open(os.path.join(out, "core.json"), encoding="utf-8") as f:   # the installer's pin on this core
                self.assertEqual(json.load(f), {"masters": {"FO4TerrainCore.esm": hashlib.sha256(b"core bytes").hexdigest()}})
            self.assertTrue(os.path.exists(os.path.join(out, "README.txt")))
            self.assertTrue(os.path.exists(os.path.join(out, "Data", "Scripts", "FO4SF_MapMarkers.pex")))
            with self.assertRaises(SystemExit):                # never into a used folder
                mm.main(["stage", "--core", core, "--out", out])
            with self.assertRaises(SystemExit):                # one plugin name, the one the installer knows
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--plugin", "Custom.esm"])
        build, comp, check = calls
        self.assertEqual(build[0][-7:], ["build", "--core", core, "--out", out, "--plugin", "FO4SFMapMarkers.esm"])
        self.assertEqual(comp[0][1], "FO4SF_MapMarkers.psc")
        self.assertEqual(check[0][-3:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core])


if __name__ == "__main__":
    unittest.main()
