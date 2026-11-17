"""Unit tests for `fo4sf.beginning_pilot` and `docs/testing/fo4-beginning-pilot.md`."""
from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.beginning_pilot import (  # noqa: E402
    BEGINNING_STEPS,
    CODSWORTH_NIF_REL,
    CODSWORTH_VOICE_DIR_REL,
    MIN_CODSWORTH_WEMS,
    evaluate_beginning_logs,
    verify_bundle_beginning_readiness,
)


def _dummy_tes4() -> bytes:
    return b"TES4" + struct.pack("<IIII", 0, 1, 0, 0) + b"\x00\x00\x00\x00"


class BeginningPilotTests(unittest.TestCase):
    def _build_synthetic_bundle(self, root: Path) -> Path:
        bundle = root / "candidate"
        (bundle / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        req_plugins = {
            "FO4ActorRaider.esm",
            "FO4TerrainCore.esm",
            "FO4SFMission.esm",
            "FO4SFVaultGearDoor.esm",
            "FO4SFExitLift.esm",
            "FO4SFNewGame.esm",
        }
        for p in sorted(req_plugins):
            (bundle / p).write_bytes(_dummy_tes4())

        for sc in (
            "FO4SF_NewGameQuest.pex",
            "FO4SF_NewGameLooks.pex",
            "FO4SF_Min00Quest.pex",
            "FO4SF_COMPreston.pex",
        ):
            (bundle / "Data" / "Scripts" / sc).write_bytes(b"PEX_SYNTHETIC_BINARY_PAYLOAD")

        nif = bundle / "Data" / Path(CODSWORTH_NIF_REL)
        nif.parent.mkdir(parents=True, exist_ok=True)
        nif.write_bytes(b"NIF_CODSWORTH")

        vdir = bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)
        vdir.mkdir(parents=True, exist_ok=True)
        for idx in range(MIN_CODSWORTH_WEMS):
            (vdir / f"00f4c{idx:03x}.wem").write_bytes(b"RIFF_WEM")

        (bundle / "bundle_plan.json").write_text(
            json.dumps(
                {
                    "plugins": sorted(req_plugins),
                    "components": {
                        "cog_door": {"outputs": {"FO4SFVaultGearDoor.esm": "aa", "Data/meshes/door.nif": "bb"}},
                        "exit_lift": {"outputs": {"FO4SFExitLift.esm": "cc", "Data/meshes/lift.nif": "dd"}},
                    },
                }
            ),
            encoding="utf-8",
        )
        return bundle

    def test_verify_bundle_beginning_readiness_passes_and_catches_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._build_synthetic_bundle(Path(tmp))
            ok_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertTrue(ok_res["ok"], ok_res["problems"])
            self.assertEqual(len(ok_res["steps"]), 7)

            # Remove one Codsworth WEM and verify B5_codsworth_sanctuary reports FAIL
            first_wem = sorted((bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)).glob("*.wem"))[0]
            first_wem.unlink()
            bad_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

    def test_evaluate_beginning_logs_full_pass_and_partial_untested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"

            # 1. Partial Vault 111 pod-only run (matching 17 Nov pod walk-out check)
            ng_log.write_text(
                "FO4SF_NEWGAME stage 10\n"
                "pod settle ok=true pos=9.14 -6.61 -0.85\n"
                "hold-off pass 2 stopped=162 of 165\n"
                "FO4SF_NEWGAME stage 20\n",
                encoding="utf-8",
            )
            partial = evaluate_beginning_logs(str(ng_log), None)
            self.assertTrue(partial["ok"])
            self.assertFalse(partial["all_pass"])
            self.assertEqual(partial["steps"]["B1_pod"]["status"], "PASS")
            self.assertEqual(partial["steps"]["B2_gear_door"]["status"], "UNTESTED")
            self.assertEqual(partial["steps"]["B7_preston_turnin"]["status"], "UNTESTED")

            # 2. Full B1..B7 console-free completion
            ng_log.write_text(
                "FO4SF_NEWGAME stage 10\n"
                "pod settle ok=true pos=9.14 -6.61 -0.85\n"
                "hold-off pass 2 stopped=195 of 199\n"
                "FO4SF_NEWGAME stage 20\n"
                "FO4SF_NEWGAME stage 30\n"
                "FO4SF_NEWGAME stage 40\n"
                "FO4SF_NEWGAME stage 200\n",
                encoding="utf-8",
            )
            ms_log.write_text(
                "[11/17/2026 - 02:00:00PM] FO4SF_MISSION rt=10.0 stage 10\n"
                "[11/17/2026 - 02:01:00PM] FO4SF_MISSION rt=70.0 hold codsworth by=keeper off=0.4 ok=True\n"
                "[11/17/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 stage 20\n"
                "[11/17/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 30\n"
                "[11/17/2026 - 02:04:10PM] FO4SF_MISSION rt=260.0 stage 40\n"
                "[11/17/2026 - 02:04:10PM] FO4SF_MISSION rt=260.0 reward credits=100\n"
                "[11/17/2026 - 02:04:11PM] FO4SF_MISSION rt=261.0 stage 200\n",
                encoding="utf-8",
            )
            full = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(full["ok"])
            self.assertTrue(full["all_pass"])
            for spec in BEGINNING_STEPS:
                self.assertEqual(full["steps"][spec.step_id]["status"], "PASS")

            # 3. Regression: door hold re-applied after follow armed -> B7 FAIL
            ms_log.write_text(
                ms_log.read_text(encoding="utf-8")
                + "[11/17/2026 - 02:05:00PM] FO4SF_MISSION rt=310.0 follow preston test-only alias=Preston filled=1 linked=player released=True quest=2069\n"
                + "[11/17/2026 - 02:05:05PM] FO4SF_MISSION rt=315.0 hold preston by=keeper off=0.5 ok=True\n",
                encoding="utf-8",
            )
            reg = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(reg["ok"])
            self.assertEqual(reg["steps"]["B7_preston_turnin"]["status"], "FAIL")

    def test_docs_cover_all_beginning_steps_and_extended_pc_card(self) -> None:
        pilot_doc = (ROOT / "docs" / "testing" / "fo4-beginning-pilot.md").read_text(encoding="utf-8")
        card_doc = (ROOT / "docs" / "testing" / "core-candidate-pc-card.md").read_text(encoding="utf-8")
        for spec in BEGINNING_STEPS:
            self.assertIn(spec.step_id, pilot_doc)
        for step_num in ("Step 13", "Step 14", "Step 15"):
            self.assertIn(step_num, card_doc)


if __name__ == "__main__":
    unittest.main()
