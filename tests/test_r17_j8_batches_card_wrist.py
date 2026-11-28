"""Round 17 J8 tests:
1. 14-plugin load order gives FO4Port=02, FO4SFCoreValues=06, FO4SFVaultPod=09, FO4SFMission=0A,
   FO4SFNewGame=0B, FO4SFWorkshop=0C, FO4SFPowerArmor=0D, Fusion Core 0D000809, gate 0200EDF0.
2. h2h4 hop clearance >= 15 m from Concord street raiders; fails if any hop < 15 m.
3. LogPipboyWrist3DNodes checks all 4 NIF prefixes (FO4WristHousing1st_, 1stF_, F_, M_).
4. generate_candidate_2h_card.py matches docs/testing/candidate-2h-card.md deterministically.
5. All 5 new check-bundle gates pass cleanly and reject negative fixtures.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (
    str(SRC),
    str(ROOT / "scripts" / "core"),
    str(ROOT / "scripts" / "mission"),
    str(ROOT / "scripts" / "testing"),
    str(ROOT / "scripts" / "ui"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle  # noqa: E402
import make_mission  # noqa: E402
import generate_candidate_2h_card  # noqa: E402
from fo4sf.beginning_pilot import (  # noqa: E402
    verify_j1_anchor_immutability,
    verify_j1_footprint_guard,
    verify_j1_shared_placement,
    verify_j6_basement_lock,
    verify_j8_card_and_batches,
)
from fo4sf.planet.esm import ESM, PluginWriter, Record, zbytes  # noqa: E402


class J8BatchesCardWristTests(unittest.TestCase):
    def test_14_plugin_load_order_gives_09_0a_0b_0d000809_and_0200edf0(self) -> None:
        idx = make_mission.compute_bundle_load_indices(
            make_core_bundle.PLAYER_BUNDLE_PLUGINS,
            base_full_slots=2,
        )
        self.assertEqual(idx["FO4Port.esm"], 0x02)
        self.assertEqual(idx["FO4SFCoreValues.esm"], 0x06)
        self.assertEqual(idx["FO4SFVaultPod.esm"], 0x09)
        self.assertEqual(idx["FO4SFMission.esm"], 0x0A)
        self.assertEqual(idx["FO4SFNewGame.esm"], 0x0B)
        self.assertEqual(idx["FO4SFWorkshop.esm"], 0x0C)
        self.assertEqual(idx["FO4SFPowerArmor.esm"], 0x0D)

        with tempfile.TemporaryDirectory(prefix="r17-j8-bat-") as td:
            files = make_mission.write_r12_h2_batches(td, plugins=make_core_bundle.PLAYER_BUNDLE_PLUGINS)
            self.assertIn("h2ge.txt", files)
            st = (Path(td) / "h2st.txt").read_text(encoding="utf-8")
            h2p = (Path(td) / "h2p.txt").read_text(encoding="utf-8")
            h2b = (Path(td) / "h2b.txt").read_text(encoding="utf-8")
            h2ge = (Path(td) / "h2ge.txt").read_text(encoding="utf-8")
            self.assertIn("sqv 0A000800", st)
            self.assertIn("getglobalvalue 06000860", st)
            self.assertIn("060008A5", h2p)
            self.assertIn("0200EDF0", h2b)
            self.assertIn("prid 0200EDF0", h2ge)
            self.assertNotIn("0100EDF0", h2b)
            self.assertNotIn("09000800", st)

    def test_h2h4_raider_clearance_passes_and_rejects_close_hop(self) -> None:
        batches = make_mission.build_r12_h2_batches(plugins=make_core_bundle.PLAYER_BUNDLE_PLUGINS)
        self.assertEqual(make_mission.validate_batch_hops_clear_of_raiders(batches), [])

        bad = dict(batches)
        bad["h2h4.txt"] = "player.setpos x -2015.00\nplayer.setpos y -1700.00\nplayer.setpos z 90.00\n"
        errs = make_mission.validate_batch_hops_clear_of_raiders(bad)
        self.assertTrue(errs, "Expected failure when h2h4 lands within 15 m of a Concord street raider")
        self.assertIn("h2h4.txt", errs[0])

    def test_log_pipboy_wrist_3d_nodes_checks_all_4_nif_prefixes(self) -> None:
        ng_psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")
        m = re.search(r"(?ms)^Function\s+LogPipboyWrist3DNodes\b.*?^EndFunction", ng_psc)
        self.assertIsNotNone(m)
        body = m.group(0)
        for prefix in (
            "FO4WristHousing1st_",
            "FO4WristHousing1stF_",
            "FO4WristHousingF_",
            "FO4WristHousingM_",
        ):
            self.assertIn(prefix, body, f"LogPipboyWrist3DNodes missing prefix {prefix!r}")
            for k in range(6):
                self.assertIn(
                    f'HasNode("{prefix}{k}")',
                    body,
                    f"LogPipboyWrist3DNodes missing builder group index {prefix}{k}",
                )
        for stale in ("FO4WristHousing1st_21", "FO4WristHousingM_11", "FO4WristHousingF_01", "FO4WristHousing1stF_01"):
            self.assertNotIn(stale, body, f"partition id {stale} is not a staged BSGeometry name")

    def test_generate_candidate_2h_card_is_deterministic_and_matches_committed_doc(self) -> None:
        rendered = generate_candidate_2h_card.render_candidate_2h_card()
        committed = (ROOT / "docs" / "testing" / "candidate-2h-card.md").read_text(encoding="utf-8")
        self.assertEqual(rendered, committed, "Regenerate docs/testing/candidate-2h-card.md via generate_candidate_2h_card.py")
        self.assertIn("0200EDF0", committed)
        self.assertIn("0D000809", committed)
        self.assertIn("getstage 0A000816", committed)
        self.assertIn("-2061.23", committed)

    def test_five_check_bundle_gates_pass_and_catch_negative_cases(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r17-gates-") as td:
            bundle = Path(td) / "bundle"
            (bundle / "Data" / "Scripts").mkdir(parents=True)
            (bundle / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").write_bytes(b"fake_pex_01234567")
            (bundle / "Data" / "Scripts" / "FO4SF_Placement.pex").write_bytes(b"fake_pex_01234567")
            bplan = {"plugins": list(make_core_bundle.PLAYER_BUNDLE_PLUGINS), "components": {"newgame": {"outputs": {}}}}

            make_mission.write_r12_h2_batches(bundle / "bat", plugins=make_core_bundle.PLAYER_BUNDLE_PLUGINS)

            self.assertEqual(verify_j1_footprint_guard(str(bundle), bplan=bplan)["status"], "PASS")
            self.assertEqual(verify_j1_anchor_immutability(str(bundle))["status"], "PASS")
            self.assertEqual(verify_j1_shared_placement(str(bundle))["status"], "PASS")
            self.assertEqual(verify_j6_basement_lock(str(bundle))["status"], "PASS")
            self.assertEqual(verify_j8_card_and_batches(str(bundle), bplan=bplan)["status"], "PASS")

            # Negative 1: j1_footprint rejects retired 0x826 marker inside FO4SFNewGame.esm
            w_ng = PluginWriter(("Starfield.esm",), flags=ESM)
            w_ng.add(Record(b"REFR", w_ng.own(0x000826), [(b"EDID", zbytes("FO4SF_ArrivalMergedMarker"))], 0, 0, 581, 0))
            (bundle / "FO4SFNewGame.esm").write_bytes(w_ng.to_bytes(compress=False))
            r_fp_fail = verify_j1_footprint_guard(str(bundle), bplan=bplan)
            self.assertEqual(r_fp_fail["status"], "FAIL", r_fp_fail)
            (bundle / "FO4SFNewGame.esm").unlink()

            # Negative 2: j1_anchor_immutability rejects PreAttachArrivalMarker referencing ExitAnchorId
            bad_scripts = Path(td) / "bad_scripts"
            shutil.copytree(ROOT / "scripts" / "newgame", bad_scripts / "newgame")
            shutil.copytree(ROOT / "scripts" / "doors", bad_scripts / "doors")
            shutil.copytree(ROOT / "scripts" / "mission", bad_scripts / "mission")
            ng_file = bad_scripts / "newgame" / "FO4SF_NewGameQuest.psc"
            orig_ng = ng_file.read_text(encoding="utf-8")
            self.assertIn("ResolveArrivalDiscoveryMarker()", orig_ng)
            ng_file.write_text(
                orig_ng.replace(
                    "ObjectReference marker = ResolveArrivalDiscoveryMarker()",
                    "ObjectReference marker = Game.GetFormFromFile(ExitAnchorId, ArrivalPlugin) as ObjectReference",
                    1,
                ),
                encoding="utf-8",
            )
            r_anc_fail = verify_j1_anchor_immutability(str(bundle), scripts_dir=bad_scripts)
            self.assertEqual(r_anc_fail["status"], "FAIL", r_anc_fail)

            # Negative 3: j1_shared_placement rejects unlisted direct player.SetPosition inside Surface()
            ng_file.write_text(
                orig_ng.replace(
                    "FO4SF_Placement.MovePlayerToExteriorAnchor",
                    "player.MoveTo(anchor)\n    ; stripped",
                    1,
                ),
                encoding="utf-8",
            )
            r_sh_fail = verify_j1_shared_placement(str(bundle), scripts_dir=bad_scripts)
            self.assertEqual(r_sh_fail["status"], "FAIL", r_sh_fail)

            # Negative 4: j6_basement_lock rejects TryOpenS6BasementGate inside OnLockStateChanged
            min_file = bad_scripts / "mission" / "FO4SF_Min00Quest.psc"
            orig_min = min_file.read_text(encoding="utf-8")
            min_file.write_text(
                orig_min.replace(
                    "RecordS6BasementGateUnlocked(\"lock_event\")",
                    "TryOpenS6BasementGate(\"lock_event\")",
                    1,
                ),
                encoding="utf-8",
            )
            r_j6_fail = verify_j6_basement_lock(str(bundle), scripts_dir=bad_scripts)
            self.assertEqual(r_j6_fail["status"], "FAIL", r_j6_fail)

            # Negative 5: j8_card_and_batches rejects close hop & stale batch FormID
            (bundle / "bat" / "h2b.txt").write_text("; stale\nplayer.setpos x -14.38\n; 0100EDF0\n", encoding="utf-8")
            r_j8_fail = verify_j8_card_and_batches(str(bundle), bplan=bplan)
            self.assertEqual(r_j8_fail["status"], "FAIL", r_j8_fail)


if __name__ == "__main__":
    unittest.main()
