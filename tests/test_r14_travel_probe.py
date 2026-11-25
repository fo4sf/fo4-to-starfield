"""Unit tests for Round 14 Task 4: Travel Service, Two-Landing Probe, and Option B Loading Screens."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (str(SRC_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf.planet.esm import COMPRESSED, ESM, LOCALIZED, Plugin, PluginWriter, Record, group_bytes, zbytes  # noqa: E402
from fo4sf.world.load_screens import (  # noqa: E402
    CTDA_FUNC_GET_GLOBAL_VALUE,
    DEFAULT_FALLOUT_SCREENS,
    SUPPRESS_GLOBAL_EDID,
    pack_get_global_ctda,
    unpack_ctda_header,
    verify_load_screens_plugin,
    write_load_screens_plugin,
)
from fo4sf.world.travel_service import (  # noqa: E402
    PendingTripRecord,
    TravelMode,
    TravelState,
    TravelTransitionError,
    resolve_registered_destinations,
)
from world.make_travel_probe import (  # noqa: E402
    PROBE_PSC_PATH,
    build_travel_probe_bytes,
    check_staged_dir,
    stage_travel_probe,
    verify_travel_probe_plugin,
)


def _write_synthetic_starfield(path: Path) -> None:
    """Create a synthetic localized Starfield.esm fixture containing LSCRs (plain + OR-chained CTDAs) and MISC."""
    w = PluginWriter(["Starfield.esm"][:0], flags=ESM | LOCALIZED, author="Test", description="Synthetic Starfield")
    # Remove self-master hack: PluginWriter([]) gives self_index=0.
    # Add one MISC item so _clone_misc_token exercises cloning.
    w.add(
        Record(
            b"MISC",
            0x00000810,
            [(b"EDID", zbytes("Misc_Junk_Fork")), (b"FULL", struct.pack("<I", 0x00001001)), (b"MODL", zbytes("Props/Fork.nif"))],
            flags=LOCALIZED,
        )
    )
    # 1. Unconditioned LSCR (plain Starfield global tip)
    w.add(
        Record(
            b"LSCR",
            0x00000900,
            [
                (b"EDID", zbytes("LS_TestGeneral01")),
                (b"DESC", struct.pack("<I", 0x00032763)),
                (b"ICON", zbytes(r"Data\textures\interface\loadscreens\generic\starfield_general.dds")),
            ],
            flags=COMPRESSED | LOCALIZED,
        )
    )
    # 2. Conditioned LSCR with OR-chained CTDAs matching Starfield.esm LS_UnitedColonies pattern
    or_ctda_1 = struct.pack("<B3xfHHIIIII", 0xA0, 10.0, 77, 0, 0, 0, 0, 0, 0xFFFFFFFF)
    or_ctda_2 = struct.pack("<B3xfHHIIIII", 0x01, 1.0, 359, 0, 0x00012345, 0, 0, 0, 0xFFFFFFFF)
    or_ctda_3 = struct.pack("<B3xfHHIIIII", 0x01, 1.0, 359, 0, 0x00012346, 0, 0, 0, 0xFFFFFFFF)
    w.add(
        Record(
            b"LSCR",
            0x00000901,
            [
                (b"EDID", zbytes("LS_TestORChain")),
                (b"DESC", struct.pack("<I", 0x00032764)),
                (b"ICON", zbytes(r"Data\textures\interface\loadscreens\generic\starfield_uc.dds")),
                (b"CTDA", or_ctda_1),
                (b"CTDA", or_ctda_2),
                (b"CTDA", or_ctda_3),
            ],
            flags=LOCALIZED,
        )
    )
    w.write(path, compress=False)


class TravelServiceTests(unittest.TestCase):
    def test_state_machine_and_single_trip_lock(self) -> None:
        rec = PendingTripRecord()
        rec.begin(
            seq=1,
            source_world="Commonwealth",
            dest_world="FarHarbor",
            source_plugin_code=1,
            dest_plugin_code=5,
            mode=TravelMode.MOVETO_SETPOS,
            target_x=10.0,
            target_y=20.0,
            target_z=5.0,
        )
        self.assertEqual(rec.state, TravelState.PENDING_WRITE)
        with self.assertRaises(TravelTransitionError):
            rec.begin(2, "Commonwealth", "FarHarbor", 1, 5)
        rec.transition(TravelState.FADING_OUT).transition(TravelState.MOVING).transition(TravelState.WAITING_3D).transition(
            TravelState.ARRIVED
        ).transition(TravelState.CLEARED)
        self.assertEqual(rec.state, TravelState.CLEARED)

    def test_reload_recovery_paths(self) -> None:
        rec = PendingTripRecord()
        rec.begin(1, "Commonwealth", "FarHarbor", 1, 5).transition(TravelState.FADING_OUT)
        self.assertEqual(rec.recover_on_load(dest_anchor_loaded=False), "aborted_pre_move_lock_cleared")
        self.assertEqual(rec.state, TravelState.CLEARED)

        rec.begin(2, "FarHarbor", "Commonwealth", 5, 1).transition(TravelState.FADING_OUT).transition(
            TravelState.MOVING
        ).transition(TravelState.WAITING_3D)
        self.assertEqual(rec.recover_on_load(dest_anchor_loaded=True), "recovered_completed_at_dest")
        self.assertEqual(rec.state, TravelState.CLEARED)

    def test_registry_destinations_present(self) -> None:
        dests = resolve_registered_destinations(world_keys=("Commonwealth", "FarHarbor", "CapitalWasteland", "MojaveWasteland"))
        self.assertEqual(dests["Commonwealth"]["reachability"], "REACHABLE")
        self.assertEqual(dests["FarHarbor"]["reachability"], "TEST-STATION (coc only)")
        self.assertEqual(dests["FarHarbor"]["pipboy_plugin_code"], 5)
        self.assertEqual(dests["CapitalWasteland"]["reachability"], "TEST-STATION (coc only)")
        self.assertEqual(dests["MojaveWasteland"]["reachability"], "TEST-STATION (coc only)")


class LoadScreensTests(unittest.TestCase):
    def test_option_b_overrides_or_chain_and_custom_screens(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sf_esm = root / "Starfield.esm"
            out_esm = root / "FO4SFLoadScreens.esm"
            data_dir = root / "Data"
            _write_synthetic_starfield(sf_esm)

            rep = write_load_screens_plugin(sf_esm, out_esm, write_blank_icon_under_data=data_dir)
            self.assertEqual(rep["vanilla_override_count"], 2)
            self.assertEqual(rep["or_chain_overrides"], 1)
            self.assertEqual(rep["custom_fallout_lscr_count"], len(DEFAULT_FALLOUT_SCREENS))
            self.assertTrue((data_dir / "textures/interface/loadscreens/fo4sf_load_blank_color.dds").is_file())

            chk = verify_load_screens_plugin(out_esm, sf_esm)
            self.assertTrue(chk["ok"])
            with Plugin(str(out_esm)) as plug:
                by_edid = {r.edid: r for r in plug.records("LSCR")}
                or_rec = by_edid["LS_TestORChain"]
                ctdas = [unpack_ctda_header(c) for c in or_rec.all(b"CTDA")]
                self.assertEqual(len(ctdas), 4)
                self.assertEqual(ctdas[0]["func"], CTDA_FUNC_GET_GLOBAL_VALUE)
                self.assertFalse(ctdas[0]["is_or"])
                self.assertEqual(ctdas[0]["value"], 0.0)
                # Original trailing OR flags remain intact after prepended gate
                self.assertTrue(ctdas[2]["is_or"])
                self.assertTrue(ctdas[3]["is_or"])

                custom_rec = by_edid["FO4SF_LSCR_Commonwealth"]
                c_ctda = unpack_ctda_header(custom_rec.all(b"CTDA")[0])
                self.assertEqual(c_ctda["value"], 1.0)
                self.assertEqual(custom_rec.get(b"DESC"), b"\x00")


class TravelProbeTests(unittest.TestCase):
    def test_stage_and_check_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sf_esm = root / "Starfield.esm"
            out_dir = root / "stage"
            _write_synthetic_starfield(sf_esm)

            manifest = stage_travel_probe(sf_esm, out_dir)
            self.assertEqual(manifest["plugins"], ["FO4SFTravelProbe.esm", "FO4SFLoadScreens.esm"])
            chk = check_staged_dir(out_dir, sf_esm)
            self.assertTrue(chk["ok"])
            self.assertTrue(chk["probe"]["ok"])
            self.assertTrue(chk["load_screens"]["ok"])

            with Plugin(str(out_dir / "Data" / "FO4SFTravelProbe.esm")) as p:
                miscs = list(p.records("MISC"))
                self.assertEqual([m.edid for m in miscs], ["FO4SF_TravelToken"])

    def test_papyrus_invariants_no_hud_debug(self) -> None:
        txt = PROBE_PSC_PATH.read_text(encoding="utf-8")
        self.assertIn("OnPlayerLoadGame", txt)
        self.assertIn("SQ_FollowersScript", txt)
        self.assertIn("Game.FastTravel", txt)
        self.assertIn("WaitFor3DLoad", txt)
        self.assertIn("ResolveHostWorld", txt)
        # Rule 13: zero HUD debug messages
        self.assertNotIn("Debug.MessageBox", txt)
        self.assertNotIn("Debug.Notification", txt)

    def test_docs_exist_and_mark_defaults_and_reachability(self) -> None:
        contract = (REPO_ROOT / "docs/world/travel-service-contract.md").read_text(encoding="utf-8")
        card = (REPO_ROOT / "docs/testing/travel-probe-card.md").read_text(encoding="utf-8")
        disc = (REPO_ROOT / "docs/world/discovery-store-design.md").read_text(encoding="utf-8")
        self.assertIn("recommended default", contract.lower())
        self.assertIn("TEST-STATION (coc only)", card)
        self.assertIn("REACHABLE", card)
        self.assertIn("recommended default", disc.lower())


if __name__ == "__main__":
    unittest.main()
