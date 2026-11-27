"""Round 15 Wave B Item H1 tests: --fo4-arsenal wiring and check-bundle arsenal WEAP verification."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "core"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle as mcb  # noqa: E402
import make_core_values as mcv  # noqa: E402
from fo4sf.beginning_pilot import (  # noqa: E402
    EXPECTED_ARSENAL_WEAPS,
    verify_bundle_beginning_readiness,
    verify_core_values_arsenal_weaps,
)
from fo4sf.planet.esm import ESM, PluginWriter, Record, zbytes  # noqa: E402
from tests.test_fo4_beginning_pilot import BeginningPilotTests  # noqa: E402


def _make_arsenal_core_values(path: Path, weaps: dict[int, str] | None = None) -> None:
    w = PluginWriter(("Starfield.esm",), flags=ESM, author="fo4-to-starfield CoreValues")
    items = EXPECTED_ARSENAL_WEAPS if weaps is None else weaps
    for fid, edid in sorted(items.items()):
        w.add(Record(b"WEAP", w.own(fid), [(b"EDID", zbytes(edid))], 0, 0, 581, 0))
    path.write_bytes(w.to_bytes(compress=False))


def _make_s2_s6_mission(path: Path) -> None:
    w = PluginWriter(("Starfield.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"), flags=ESM)
    w.add(Record(b"QUST", w.own(0x000B90), [(b"EDID", zbytes("FO4SF_Vault111Roaches"))], 0, 0, 581, 0))
    path.write_bytes(w.to_bytes(compress=False))


class R15H1ArsenalBundleTests(unittest.TestCase):
    def test_make_core_values_parses_and_forwards_fo4_arsenal_flags(self) -> None:
        parser = mcv.build_parser()
        ns_def = parser.parse_args(["stage", "--sf-data", "sf", "--out", "out"])
        self.assertEqual(ns_def.fo4_10mm, 1)
        self.assertEqual(ns_def.fo4_p5_weapons, 1)
        self.assertEqual(ns_def.fo4_arsenal, 1)

        ns_off = parser.parse_args(["stage", "--sf-data", "sf", "--out", "out", "--fo4-arsenal", "0"])
        self.assertEqual(ns_off.fo4_arsenal, 0)

        ns_flag = parser.parse_args(["stage", "--sf-data", "sf", "--out", "out", "--fo4-arsenal"])
        self.assertEqual(ns_flag.fo4_arsenal, 1)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sf_data = root / "sf_data"
            sf_data.mkdir()
            (sf_data / "Starfield.esm").write_bytes(b"TES4")
            out_dir = root / "cv_stage"
            seen_calls: list[list[str]] = []

            orig_run_dotnet = mcv._run_dotnet

            def _fake_dotnet(args: list[str]) -> str:
                seen_calls.append(list(args))
                if args[0] == "build":
                    Path(args[2], mcv.CORE_VALUES_PLUGIN).write_bytes(b"TES4_FAKE")
                return "ok"

            mcv._run_dotnet = _fake_dotnet
            try:
                mcv.main(["stage", "--sf-data", str(sf_data), "--out", str(out_dir), "--fo4-arsenal", "1"])
            finally:
                mcv._run_dotnet = orig_run_dotnet

            self.assertEqual(len(seen_calls), 2)
            for call in seen_calls:
                self.assertIn("--fo4-arsenal", call)
                self.assertEqual(call[call.index("--fo4-arsenal") + 1], "1")
            plan = json.loads((out_dir / mcv.PLAN_NAME).read_text(encoding="utf-8"))
            self.assertEqual(plan["fo4_arsenal"], 1)

    def test_make_core_bundle_forwards_fo4_arsenal_before_test_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            port = root / "FO4Port.esm"
            port.write_bytes(b"TES4")
            owner = root / "owner"
            owner.mkdir()
            (owner / "FO4TerrainCore.esm").write_bytes(b"TES4")
            (owner / "FO4ActorRaider.esm").write_bytes(b"TES4")

            recorded: list[list[str]] = []
            orig_run_py = mcb._run_py

            def _spy_run_py(_py, script_rel, args):
                if script_rel == "scripts/core/make_core_values.py":
                    recorded.append(list(args))
                    out_idx = list(args).index("--out") + 1
                    Path(args[out_idx]).mkdir(parents=True, exist_ok=True)
                    raise StopIteration("stop")
                return orig_run_py(_py, script_rel, args)

            mcb._run_py = _spy_run_py
            try:
                ns = SimpleNamespace(
                    work=str(root / "work"),
                    out=str(root / "out"),
                    render_python=None,
                    starfield_dir=str(root / "sf"),
                    port=str(port),
                    owner_set=str(owner),
                    profile="player",
                    commonlibsf=None,
                    msvc_env=None,
                    allow_starfield_standins=True,
                    fo4_arsenal=1,
                )
                with self.assertRaises(StopIteration):
                    mcb.stage_from_checkout(ns)
            finally:
                mcb._run_py = orig_run_py

            self.assertEqual(len(recorded), 1)
            cv_args = recorded[0]
            self.assertEqual(cv_args[-2:], ["--test-mode", "0"])
            self.assertIn("--fo4-arsenal", cv_args)
            self.assertEqual(cv_args[cv_args.index("--fo4-arsenal") + 1], "1")

    def test_check_bundle_arsenal_weaps_auto_detect_pass_fail_and_fix7b_compat(self) -> None:
        cli = ROOT / "scripts" / "testing" / "check_beginning_pilot.py"
        helper = BeginningPilotTests("_build_synthetic_bundle")
        self.assertEqual(len(EXPECTED_ARSENAL_WEAPS), 25)
        self.assertIn(0x000899, EXPECTED_ARSENAL_WEAPS)
        self.assertIn(0x0008A2, EXPECTED_ARSENAL_WEAPS)
        self.assertIn(0x0008D6, EXPECTED_ARSENAL_WEAPS)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # 1. candidate-2g-fix7b-compatible bundle (0 arsenal WEAPs, no S2-S6 markers): SKIP (exit 0), FAIL under --require-arsenal
            bundle_compat = helper._build_synthetic_bundle(root / "compat")
            r_skip = subprocess.run(
                [sys.executable, str(cli), "check-bundle", "--bundle-dir", str(bundle_compat)],
                capture_output=True, text=True,
            )
            self.assertEqual(r_skip.returncode, 0, r_skip.stdout + r_skip.stderr)
            self.assertIn("SKIP  arsenal_weap", r_skip.stdout)

            r_req_fail = subprocess.run(
                [sys.executable, str(cli), "check-bundle", "--bundle-dir", str(bundle_compat), "--require-arsenal"],
                capture_output=True, text=True,
            )
            self.assertEqual(r_req_fail.returncode, 1, r_req_fail.stdout + r_req_fail.stderr)
            self.assertIn("FAIL  arsenal_weap", r_req_fail.stdout)

            # 2. Full 25/25 arsenal WEAP set passes both auto-detect and --require-arsenal
            _make_arsenal_core_values(bundle_compat / "FO4SFCoreValues.esm")
            r_pass = subprocess.run(
                [sys.executable, str(cli), "check-bundle", "--bundle-dir", str(bundle_compat), "--require-arsenal"],
                capture_output=True, text=True,
            )
            self.assertEqual(r_pass.returncode, 0, r_pass.stdout + r_pass.stderr)
            self.assertIn("PASS  arsenal_weap", r_pass.stdout)
            self.assertIn("25/25", r_pass.stdout)

            # 3. Partial arsenal (missing 0x0008D6 Gauss Rifle) fails auto-detect even without --require-arsenal
            partial = dict(EXPECTED_ARSENAL_WEAPS)
            partial.pop(0x0008D6)
            _make_arsenal_core_values(bundle_compat / "FO4SFCoreValues.esm", weaps=partial)
            bad_res = verify_bundle_beginning_readiness(str(bundle_compat))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["arsenal_weaps"]["status"], "FAIL")
            self.assertIn("0x0008D6", bad_res["arsenal_weaps"]["detail"])

            # 4. S2-S6 mission without arsenal WEAPs fails auto-detect
            bundle_s2s6 = helper._build_synthetic_bundle(root / "s2s6")
            _make_s2_s6_mission(bundle_s2s6 / "FO4SFMission.esm")
            aw_s2s6 = verify_core_values_arsenal_weaps(str(bundle_s2s6))
            self.assertEqual(aw_s2s6["status"], "FAIL")
            self.assertIn("missing 25/25", aw_s2s6["detail"])

    def test_fold_arsenal_assets_copies_data_and_bat_and_refuses_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            aa = root / "arsenal_assets"
            w_nif = aa / "Data" / "meshes" / "fo4sf" / "weapons" / "10mm" / "fo4_10mmpistol.nif"
            w_nif.parent.mkdir(parents=True, exist_ok=True)
            w_nif.write_bytes(b"NIF_BYTES")
            (aa / "Data" / "textures" / "fo4core" / "weapons" / "10mm").mkdir(parents=True, exist_ok=True)
            (aa / "Data" / "textures" / "fo4core" / "weapons" / "10mm" / "10mm_d.dds").write_bytes(b"DDS_BYTES")
            (aa / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
            (aa / "Data" / "Scripts" / "Ignored.pex").write_bytes(b"PEX")
            (aa / "bat").mkdir(parents=True, exist_ok=True)
            (aa / "bat" / "h2st.txt").write_text("getglobalvalue 06000860\n", encoding="utf-8")

            partial = root / "partial"
            partial.mkdir()
            cc = root / "cc"
            cc.mkdir()
            folded_hashes: dict[str, str] = {}
            comps = {"core_values": {"plugins": ["FO4SFCoreValues.esm"], "outputs": {}}}
            mcb._fold_arsenal_assets(str(aa), str(partial), str(cc), folded_hashes, comps)

            rel_nif = "Data/meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif"
            rel_dds = "Data/textures/fo4core/weapons/10mm/10mm_d.dds"
            self.assertTrue((partial / rel_nif).is_file())
            self.assertTrue((partial / rel_dds).is_file())
            self.assertFalse((partial / "Data" / "Scripts" / "Ignored.pex").exists())
            self.assertTrue((partial / "bat" / "h2st.txt").is_file())
            self.assertIn(rel_nif, comps["core_values"]["outputs"])
            self.assertIn(rel_dds, folded_hashes)

            # Re-folding identical bytes is idempotent; differing bytes refuse.
            mcb._fold_arsenal_assets(str(aa), str(partial), str(cc), folded_hashes, comps)
            w_nif.write_bytes(b"DIFFERING")
            with self.assertRaises(mcb.BundleRefused):
                mcb._fold_arsenal_assets(str(aa), str(partial), str(cc), folded_hashes, comps)


if __name__ == "__main__":
    unittest.main()
