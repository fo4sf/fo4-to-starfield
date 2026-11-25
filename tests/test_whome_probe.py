"""Offline end-to-end tests for scripts/probes/make_whome_probe.py."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import warnings

ROOT = Path(__file__).resolve().parents[1]
for p in (
    str(ROOT / "src"),
    str(ROOT / "tests"),
    str(ROOT / "scripts" / "probes"),
    str(ROOT / "scripts" / "ui"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf.planet import census, esm, home_planet_spec as hspec, records  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402
import make_whome_probe  # noqa: E402
import pipboy_map_store  # noqa: E402
import probe_common  # noqa: E402
import test_pipboy_stage_ini as tpsi  # noqa: E402
import test_planet_home as tph  # noqa: E402


class FakeSystemClean:
    def pids(self, name: str):
        return []


class FakeSystemRunning:
    def pids(self, name: str):
        return [4242]


def _write_synthetic_whome_inputs(root: Path) -> dict[str, Path]:
    sf_dir = root / "Starfield"
    sf_data = sf_dir / "Data"
    sf_data.mkdir(parents=True, exist_ok=True)
    tph._build_synthetic_starfield_data(sf_data)
    core_path_str = str(sf_data / "FO4TerrainCore.esm")

    baseline = root / "baseline_2g_fix2"
    (baseline / "Data" / "Interface" / "Components").mkdir(parents=True, exist_ok=True)

    xmrk_rec = esm.Record(
        b"REFR",
        0x010A7759,
        [
            (b"EDID", esm.zbytes("FO4Core_CommonwealthMapMarker")),
            (b"NAME", struct.pack("<I", 0x00000010)),
            (b"XMRK", b""),
            (b"FNAM", struct.pack("<I", 0x03)),
            (b"FULL", esm.zbytes("Red Rocket Truck Stop")),
            (b"TNAM", struct.pack("<H", 86)),
            (b"DATA", struct.pack("<6f", -991.13, 1144.97, 100.0, 0.0, 0.0, 0.0)),
        ],
        flags=esm.PERSISTENT,
    ).to_bytes(compress=False)
    cell_rec = esm.Record(b"CELL", 0x01000801, [(b"EDID", esm.zbytes("TestPersistentCell"))]).to_bytes(compress=False)
    cell_grp = esm.group_bytes(struct.pack("<I", 0x01000801), esm.group_bytes(struct.pack("<I", 0x01000801), xmrk_rec, gtype=8), gtype=6)
    wrld_children = esm.group_bytes(struct.pack("<I", 0x01000803), cell_rec + cell_grp, gtype=1)
    with esm.Plugin(core_path_str) as cp:
        core_lctn_bytes = next(cp.records("LCTN", [b"LCTN"])).to_bytes(compress=False)
        core_wrld_bytes = census.worlds(cp)[0].to_bytes(compress=False)
    tes4 = esm.Record(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 0.96, 3, 0x0B0000)), (b"MAST", esm.zbytes("Starfield.esm"))], esm.ESM, 0, 581, 0).to_bytes(compress=False)
    (baseline / "FO4TerrainCore.esm").write_bytes(
        tes4
        + esm.group_bytes("LCTN", core_lctn_bytes, gtype=0)
        + esm.group_bytes("WRLD", core_wrld_bytes + wrld_children, gtype=0)
    )

    # Create synthetic Interface SWFs matching candidate-2g-fix2 shell
    (baseline / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(tpsi._build_shell_swf())
    (baseline / "Data" / "Interface" / "Pipboy_MapPage.swf").write_bytes(tpsi._build_map_swf())

    # Synthetic FO4Port.esm with 0x0100E18A + 2 children
    port_esm = root / "FO4Port.esm"
    pw = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    pw.add(records.new_location(0x0100E18A, "FO4Port_InteriorsLocation", "", [], 0x0001B736, 0, 0))
    pw.add(records.new_location(0x0100E18B, "FO4Port_ConcordMuseumLocation", "", [], 0x0100E18A, 0, 0))
    pw.write(str(port_esm), compress=False)

    # Synthetic FO4SFMapMarkers.esm overriding LCTN 000802 with 1 LCSR row (matches FO4TerrainCore_Home)
    mm_esm = root / "FO4SFMapMarkers.esm"
    mm_w = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
    mm_row = struct.pack("<5I", 0x0002271F, 0x010A7759, 0x01000803, 0, 0xFFFFFFFF)
    mm_w.add(esm.Record(b"LCTN", 0x01000802, [(b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")), (b"LCSR", mm_row)]))
    mm_w.write(str(mm_esm), compress=False)

    # Synthetic FO4SFCoreValues, FO4SFMission (clean: 0 WRLD overrides), FO4SFNewGame, DLL, PEX
    cv_esm = root / "FO4SFCoreValues.esm"
    esm.PluginWriter(["Starfield.esm"], esm.ESM).write(str(cv_esm), compress=False)
    mission_esm = baseline / "FO4SFMission.esm"
    esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM).write(str(mission_esm), compress=False)
    newgame_esm = baseline / "FO4SFNewGame.esm"
    esm.PluginWriter(["Starfield.esm"], esm.ESM).write(str(newgame_esm), compress=False)

    pipboy_dll = root / "FO4SFPipboyMenu.dll"
    pipboy_dll.write_bytes(b"MZ-synthetic-pipboy-dll")
    (root / "build.json").write_text(
        json.dumps({"plugin": "FO4SFPipboyMenu", "note": "null read + latent refcount UAF"}) + "\n",
        encoding="utf-8",
    )
    travel_pex = root / "FO4SF_PipboyTravel.pex"
    travel_pex.write_bytes(b"FA57C0DE-synthetic-pex")

    # Populate simulated installed Starfield\Data baseline files to test atomic swap + uninstall restore
    for rel, content in (
        ("FO4TerrainCore.esm", (baseline / "FO4TerrainCore.esm").read_bytes()),
        ("FO4TerrainCore_Mars.esm", esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM).to_bytes(compress=False)),
        ("FO4Port.esm", b"OLD_PORT"),
        ("FO4SFCoreValues.esm", b"OLD_CORE_VALUES"),
        ("FO4SFMission.esm", b"OLD_MISSION"),
        ("FO4SFNewGame.esm", b"OLD_NEWGAME"),
        ("FO4SFPipboyTravel.esm", b"OLD_TRAVEL"),
        ("Scripts/FO4SF_PipboyTravel.pex", b"OLD_PEX"),
        ("Scripts/FO4SF_Min00Quest.pex", b"OLD_MIN00"),
        ("Scripts/FO4SF_NewGameQuest.pex", b"OLD_NG"),
        ("SFSE/Plugins/FO4SFPipboyMenu.dll", b"OLD_DLL"),
        ("SFSE/Plugins/FO4SFPipboyMenu.ini", b"OLD_INI"),
        ("SFSE/Plugins/FO4SFPipboyMapMarkers.tsv", b"OLD_TSV"),
    ):
        dst = sf_data / Path(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(content)

    m_scripts = root / "m_scripts"
    ng_scripts = root / "ng_scripts"
    m_scripts.mkdir(parents=True, exist_ok=True)
    ng_scripts.mkdir(parents=True, exist_ok=True)
    (m_scripts / "FO4SF_Min00Quest.pex").write_bytes(b"NEW_MIN00_PEX")
    (ng_scripts / "FO4SF_NewGameQuest.pex").write_bytes(b"NEW_NG_PEX")

    plugins_txt = root / "Plugins.txt"
    plugins_txt.write_bytes(
        b"# Installed baseline\r\n"
        b"*FO4TerrainCore.esm\r\n"
        b"*FO4TerrainCore_Mars.esm\r\n"
        b"*FO4SFCoreValues.esm\r\n"
        b"*FO4SFMission.esm\r\n"
        b"*FO4SFNewGame.esm\r\n"
        b"*FO4SFPipboyTravel.esm\r\n"
    )

    return {
        "starfield": sf_dir,
        "baseline": baseline,
        "port": port_esm,
        "map_markers": mm_esm,
        "dll": pipboy_dll,
        "pex": travel_pex,
        "cv": cv_esm,
        "m_scripts": m_scripts,
        "ng_scripts": ng_scripts,
        "plugins_txt": plugins_txt,
    }


class WhomeProbeTests(unittest.TestCase):
    def test_stage_install_status_uninstall_roundtrip_and_dirty_mission_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _write_synthetic_whome_inputs(root)
            out_dir = root / "w-home"
            orig_plugins = inp["plugins_txt"].read_bytes()

            with mock.patch.object(probe_common, "check_starfield_not_running", return_value=[]):
                man = make_whome_probe.stage_probe(
                    starfield_dir=inp["starfield"],
                    out_dir=out_dir,
                    baseline_dir=inp["baseline"],
                    port_esm=inp["port"],
                    map_markers_esm=inp["map_markers"],
                    pipboy_dll=inp["dll"],
                    mission_scripts_dir=inp["m_scripts"],
                    newgame_scripts_dir=inp["ng_scripts"],
                    travel_pex_override=inp["pex"],
                    core_values_override=inp["cv"],
                    min_free_gb=0.1,
                )
            self.assertTrue((out_dir / "Data" / "FO4SFMission - Main.ba2").is_file())
            self.assertTrue((out_dir / "Data" / "FO4SFNewGame - Main.ba2").is_file())
            self.assertTrue((out_dir / "Data" / "FO4SFPipboyTravel - Main.ba2").is_file())
            self.assertEqual((out_dir / "Data" / "Scripts" / "FO4SF_Min00Quest.pex").read_bytes(), b"NEW_MIN00_PEX")
            self.assertEqual((out_dir / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").read_bytes(), b"NEW_NG_PEX")
            self.assertEqual(man["census"]["mars_planet_data_winning_refs"], 0)
            self.assertEqual(man["census"]["mars_surface_lctn_winning_refs"], 0)
            self.assertEqual(man["census"]["fo4port_child_lctns"]["reaching_earth"], 1)
            self.assertGreaterEqual(man["marker_rows"], 2)  # Red Rocket + Diamond City anchor
            self.assertIsNotNone(man["pipboy_build_json_sha256"])
            self.assertTrue((out_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.build.json").is_file())

            ver = make_whome_probe.verify_staged_probe(out_dir)
            self.assertTrue(ver["verified"])
            self.assertIn("ktg.txt", ver["batches"])
            self.assertIn("we1.txt", ver["batches"])
            self.assertIn("we2.txt", ver["batches"])

            # Verify staged INI preserves Stage=2, MapBlockStarMap=1, MapSurvival=0, and zero Kit* entries
            ini_text = (out_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
            self.assertIn("Stage=2", ini_text)
            self.assertIn("Map=1", ini_text)
            self.assertIn("MapBlockStarMap=1", ini_text)
            self.assertIn("MapSurvival=0", ini_text)
            make_pipboy_stage_ini.assert_no_kit_entries(ini_text)

            # Verify staged copies are independent (st_nlink == 1)
            self.assertEqual(os.stat(out_dir / "Data" / "FO4SFHome.esm").st_nlink, 1)
            self.assertEqual(os.stat(out_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").st_nlink, 1)

            # Install + verify status + Mars unticked + Home active (emit baseline mismatch warning cleanly)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                make_whome_probe.install_probe_cmd(
                    stage_dir=out_dir,
                    starfield_dir=inp["starfield"],
                    plugins_txt=inp["plugins_txt"],
                    version_tag="r12-t4-test",
                    allow_hardlink=False,
                    min_free_gb=0.1,
                    system=FakeSystemClean(),
                )
            plg_lines = inp["plugins_txt"].read_text(encoding="utf-8").splitlines()
            self.assertIn("FO4TerrainCore_Mars.esm", plg_lines)
            self.assertNotIn("*FO4TerrainCore_Mars.esm", plg_lines)
            self.assertIn("*FO4SFHome.esm", plg_lines)
            self.assertIn("*FO4TerrainCore_Home.esm", plg_lines)
            self.assertTrue((inp["starfield"] / "w1.txt").is_file())
            self.assertTrue((inp["starfield"] / "ktg.txt").is_file())
            self.assertTrue((inp["starfield"] / "we1.txt").is_file())
            self.assertTrue((inp["starfield"] / "we2.txt").is_file())

            st = probe_common.probe_status(probe_id="w-home", starfield_dir=inp["starfield"])
            self.assertTrue(st["installed"], st)
            self.assertEqual(st["state"], "installed")

            # Uninstall -> byte-for-byte restoration of Plugins.txt & swapped baseline files + removal of added files
            probe_common.uninstall_probe(probe_id="w-home", starfield_dir=inp["starfield"], system=FakeSystemClean())
            self.assertEqual(inp["plugins_txt"].read_bytes(), orig_plugins)
            self.assertEqual((inp["starfield"] / "Data" / "FO4Port.esm").read_bytes(), b"OLD_PORT")
            self.assertEqual((inp["starfield"] / "Data" / "FO4SFCoreValues.esm").read_bytes(), b"OLD_CORE_VALUES")
            self.assertEqual((inp["starfield"] / "Data" / "Scripts" / "FO4SF_Min00Quest.pex").read_bytes(), b"OLD_MIN00")
            self.assertEqual((inp["starfield"] / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").read_bytes(), b"OLD_NG")
            self.assertEqual((inp["starfield"] / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").read_bytes(), b"OLD_DLL")
            self.assertFalse((inp["starfield"] / "Data" / "FO4SFHome.esm").exists())
            self.assertFalse((inp["starfield"] / "Data" / "FO4SFMission - Main.ba2").exists())
            self.assertFalse((inp["starfield"] / "Data" / "FO4SFNewGame - Main.ba2").exists())
            self.assertFalse((inp["starfield"] / "w1.txt").exists())
            self.assertFalse((inp["starfield"] / "ktg.txt").exists())

            # Negative: dirty FO4SFMission.esm carrying WRLD override on FO4Core_Commonwealth is refused
            dirty_mission = root / "DirtyMission.esm"
            dm_w = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
            dm_w.add(esm.Record(b"WRLD", 0x02000803, [(b"EDID", esm.zbytes("FO4Core_Commonwealth"))]))
            dm_w.write(str(dirty_mission), compress=False)
            with self.assertRaises(probe_common.ProbeValidationError):
                with mock.patch.object(probe_common, "check_starfield_not_running", return_value=[]):
                    make_whome_probe.stage_probe(
                        starfield_dir=inp["starfield"],
                        out_dir=root / "w-home-bad",
                        baseline_dir=inp["baseline"],
                        port_esm=inp["port"],
                        map_markers_esm=inp["map_markers"],
                        pipboy_dll=inp["dll"],
                        mission_esm=dirty_mission,
                        travel_pex_override=inp["pex"],
                        core_values_override=inp["cv"],
                        min_free_gb=0.1,
                    )

    def test_f12_stage_and_install_refuse_when_starfield_running(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _write_synthetic_whome_inputs(root)
            out_dir = root / "w-home"
            with mock.patch.object(probe_common, "check_starfield_not_running", side_effect=probe_common.ProbeError("Starfield running")):
                with self.assertRaises(probe_common.ProbeError):
                    make_whome_probe.stage_probe(
                        starfield_dir=inp["starfield"],
                        out_dir=out_dir,
                        baseline_dir=inp["baseline"],
                        port_esm=inp["port"],
                        map_markers_esm=inp["map_markers"],
                        pipboy_dll=inp["dll"],
                        travel_pex_override=inp["pex"],
                        core_values_override=inp["cv"],
                        min_free_gb=0.1,
                    )
            with mock.patch.object(probe_common, "check_starfield_not_running", return_value=[]):
                make_whome_probe.stage_probe(
                    starfield_dir=inp["starfield"],
                    out_dir=out_dir,
                    baseline_dir=inp["baseline"],
                    port_esm=inp["port"],
                    map_markers_esm=inp["map_markers"],
                    pipboy_dll=inp["dll"],
                    travel_pex_override=inp["pex"],
                    core_values_override=inp["cv"],
                    min_free_gb=0.1,
                )
            with self.assertRaises(probe_common.ProbeError):
                make_whome_probe.install_probe_cmd(
                    stage_dir=out_dir,
                    starfield_dir=inp["starfield"],
                    plugins_txt=inp["plugins_txt"],
                    allow_hardlink=False,
                    min_free_gb=0.1,
                    system=FakeSystemRunning(),
                )

    def test_f2_diamond_city_stops_and_64_cell_edge_hops_and_ktg_batch(self) -> None:
        anchors, hops, batches = make_whome_probe._build_batch_plan()
        probe_common.validate_batches_and_hops(
            anchors=anchors,
            hops=hops,
            max_axis_m=make_whome_probe.MAX_HOP_AXIS_M,
            raise_on_error=True,
        )
        bat_map = {name: body for name, body in batches}
        for name in bat_map:
            stem = Path(name).stem.lower()
            self.assertFalse(any(ch in stem for ch in ("m", "n", "v")), f"forbidden P3 letter in {name}")
        self.assertEqual(bat_map["ktg.txt"].strip().splitlines()[-1].strip(), "tgm")

        # k7 must be ground_z+2.5m (~12.60), strictly below the 26.35m interpolated roof.
        anchor_by_name = {a.name: a for a in anchors}
        self.assertLess(anchor_by_name["DC_Step7"].z, 20.0)
        # k8 stands ~5.15 m SW of DmndGateREF (-1416.36, -3129.39).
        dc = anchor_by_name["DiamondCity"]
        dist_to_gate = math.hypot(dc.x - (-1416.36), dc.y - (-3129.39))
        self.assertGreaterEqual(dist_to_gate, 4.0)
        self.assertLessEqual(dist_to_gate, 6.0)
        # West 64-cell boundary sits at -4400.0; we1 is inside and we2 crosses outside.
        self.assertGreater(anchor_by_name["WestEdge_Inside"].x, -4400.0)
        self.assertLess(anchor_by_name["WestEdge_Outside"].x, -4400.0)

    def test_f11_stage_passes_weather_flags_to_make_core_values(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _write_synthetic_whome_inputs(root)
            out_dir = root / "w-home-f11"
            seen_argv: list[list[str]] = []

            def fake_cv_main(argv):
                seen_argv.append(list(argv))
                out_p = Path(argv[argv.index("--out") + 1]) / "Data"
                out_p.mkdir(parents=True, exist_ok=True)
                esm.PluginWriter(["Starfield.esm"], esm.ESM).write(str(out_p / "FO4SFCoreValues.esm"), compress=False)
                return 0

            with (
                mock.patch.object(probe_common, "check_starfield_not_running", return_value=[]),
                mock.patch.object(make_whome_probe.make_core_values, "main", side_effect=fake_cv_main),
            ):
                make_whome_probe.stage_probe(
                    starfield_dir=inp["starfield"],
                    out_dir=out_dir,
                    baseline_dir=inp["baseline"],
                    port_esm=inp["port"],
                    map_markers_esm=inp["map_markers"],
                    pipboy_dll=inp["dll"],
                    travel_pex_override=inp["pex"],
                    min_free_gb=0.1,
                )
            self.assertEqual(len(seen_argv), 1)
            self.assertIn("--commonwealth-weather", seen_argv[0])
            idx = seen_argv[0].index("--commonwealth-weather")
            self.assertEqual(seen_argv[0][idx + 1], "0")

    def test_f3_install_missing_card_emits_warning_without_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _write_synthetic_whome_inputs(root)
            out_dir = root / "w-home-f3"
            with mock.patch.object(probe_common, "check_starfield_not_running", return_value=[]):
                make_whome_probe.stage_probe(
                    starfield_dir=inp["starfield"],
                    out_dir=out_dir,
                    baseline_dir=inp["baseline"],
                    port_esm=inp["port"],
                    map_markers_esm=inp["map_markers"],
                    pipboy_dll=inp["dll"],
                    travel_pex_override=inp["pex"],
                    core_values_override=inp["cv"],
                    min_free_gb=0.1,
                )
            missing_card = root / "does_not_exist_card.md"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", RuntimeWarning)
                rcpt = make_whome_probe.install_probe_cmd(
                    stage_dir=out_dir,
                    starfield_dir=inp["starfield"],
                    plugins_txt=inp["plugins_txt"],
                    version_tag="r13-f3-test",
                    card_path=missing_card,
                    allow_hardlink=False,
                    min_free_gb=0.1,
                    system=FakeSystemClean(),
                )
            self.assertTrue(rcpt["complete"])
            self.assertTrue(any("card" in str(w.message).lower() for w in caught), caught)
            self.assertTrue(probe_common.probe_status(probe_id="w-home", starfield_dir=inp["starfield"])["installed"])

    def test_f7_f8_all_mission_quests_resolve_host_world_via_persistent_anchor(self) -> None:
        quest_files = [
            ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc",
            *(ROOT / "scripts" / "mission" / f"{q}.psc" for q in (
                "FO4SF_Min00Quest",
                "FO4SF_Sanctuary01Quest",
                "FO4SF_MQ103Quest",
                "FO4SF_MinRecruit00Quest",
                "FO4SF_MQ104Quest",
                "FO4SF_MQ105Quest",
                "FO4SF_MQ106Quest",
                "FO4SF_MQ203Quest",
                "FO4SF_MQ204Quest",
                "FO4SF_MQ206Quest",
            )),
        ]
        for qpath in quest_files:
            text = qpath.read_text(encoding="utf-8")
            self.assertIn("0x0A775B", text, qpath.name)
            self.assertNotIn("MarsPlanetWorld", text, qpath.name)
            for ln in text.splitlines():
                if "worldspace" in ln.lower() or "commonwealthworldid" in ln.lower():
                    self.assertNotIn("0x000803", ln, f"{qpath.name}: {ln}")
        min00_text = (ROOT / "scripts" / "mission" / "FO4SF_Min00Quest.psc").read_text(encoding="utf-8")
        self.assertNotIn("UnequipAll", min00_text)

    def test_install_uses_candidate_2g_fix4_hashes_and_label(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _write_synthetic_whome_inputs(root)
            out_dir = root / "w-home-fix4"
            with mock.patch.object(probe_common, "check_starfield_not_running", return_value=[]):
                make_whome_probe.stage_probe(
                    starfield_dir=inp["starfield"],
                    out_dir=out_dir,
                    baseline_dir=inp["baseline"],
                    port_esm=inp["port"],
                    map_markers_esm=inp["map_markers"],
                    pipboy_dll=inp["dll"],
                    travel_pex_override=inp["pex"],
                    core_values_override=inp["cv"],
                    min_free_gb=0.1,
                )
            with (
                mock.patch.object(probe_common, "install_probe", wraps=probe_common.install_probe) as spy_install,
                warnings.catch_warnings(),
            ):
                warnings.simplefilter("ignore", RuntimeWarning)
                make_whome_probe.install_probe_cmd(
                    stage_dir=out_dir,
                    starfield_dir=inp["starfield"],
                    plugins_txt=inp["plugins_txt"],
                    allow_hardlink=False,
                    min_free_gb=0.1,
                    system=FakeSystemClean(),
                )
            self.assertEqual(spy_install.call_count, 1)
            kw = spy_install.call_args.kwargs
            self.assertEqual(kw["baseline_label"], "candidate-2g-fix4")
            self.assertIs(kw["baseline_2g_fix2_hashes"], probe_common.CANDIDATE_2G_FIX4_HASHES)


if __name__ == "__main__":
    unittest.main()
