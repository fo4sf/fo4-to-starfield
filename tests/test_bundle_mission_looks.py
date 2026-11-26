"""A fresh core-bundle mission stage must keep C5 actor looks (26 Nov B5).

candidate-2g-fix7 ran ``make_core_bundle build`` without ``--codsworth-assets`` or
``--actor-looks-assets``. The staged ``02b-mission`` then had no ``codsworth.nif``,
Preston outfit, or ``concord_raider_m.nif``, and check-bundle B5 failed.
Offline only. No game files.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CORE = str(ROOT / "scripts" / "core")
if CORE not in sys.path:
    sys.path.insert(0, CORE)

import make_core_bundle as mcb  # noqa: E402


class _Stop(Exception):
    def __init__(self, script: str) -> None:
        super().__init__(script)
        self.script = script


class BundleMissionLooksTests(unittest.TestCase):
    def test_forward_args_refuse_a_bare_stage_and_keep_race_framing_off(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(mcb.BundleRefused) as caught:
                mcb.mission_asset_forward_args(SimpleNamespace())
            self.assertIn("--codsworth-assets", str(caught.exception))
            self.assertIn("--actor-looks-assets", str(caught.exception))
            self.assertIn("26 Nov B5", str(caught.exception))

            cods = root / "codsworth"
            looks = root / "looks"
            cods.mkdir()
            looks.mkdir()
            args = mcb.mission_asset_forward_args(SimpleNamespace(
                codsworth_assets=str(cods),
                actor_looks_assets=str(looks),
            ))
            self.assertEqual(args, [
                "--codsworth-assets", str(cods.resolve()),
                "--actor-looks-assets", str(looks.resolve()),
            ])
            framed = mcb.mission_asset_forward_args(SimpleNamespace(
                codsworth_assets=str(cods),
                actor_looks_assets=str(looks),
                codsworth_race_framing=True,
            ))
            self.assertEqual(framed[-1], "--codsworth-race-framing")

    def test_checkout_refuses_to_stage_a_lookless_mission(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            seen = self._drive(Path(td), {})
            self.assertIsInstance(seen["error"], mcb.BundleRefused)
            self.assertIn("26 Nov B5", str(seen["error"]))
            self.assertNotIn("scripts/mission/make_mission.py", seen["scripts"])

    def test_checkout_forwards_look_dirs_onto_make_mission(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cods = root / "codsworth"
            looks = root / "looks"
            cods.mkdir()
            looks.mkdir()
            seen = self._drive(root, {
                "codsworth_assets": str(cods),
                "actor_looks_assets": str(looks),
            })
            self.assertIsInstance(seen["error"], _Stop)
            self.assertEqual(seen["error"].script, "scripts/mission/make_mission.py")
            mission = seen["calls"][-1][1]
            self.assertEqual(mission[mission.index("--codsworth-assets") + 1], str(cods.resolve()))
            self.assertEqual(mission[mission.index("--actor-looks-assets") + 1], str(looks.resolve()))
            self.assertNotIn("--codsworth-race-framing", mission)

    def test_prebuilt_mission_stage_does_not_need_look_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prebuilt = root / "already-staged"
            prebuilt.mkdir()
            seen = self._drive(root, {"mission_stage": str(prebuilt)})
            self.assertIsInstance(seen["error"], _Stop)
            self.assertEqual(seen["error"].script, "scripts/ui/stage_pipboy_wrist.py")
            self.assertNotIn("scripts/mission/make_mission.py", seen["scripts"])

    def _drive(self, root: Path, extra: dict) -> dict:
        owner = root / "owner"
        owner.mkdir(exist_ok=True)
        (owner / "FO4ActorRaider.esm").write_bytes(b"raider")
        calls: list[tuple[str, list[str]]] = []
        orig = mcb._run_py

        def spy(py_exe: str, script_rel: str, args) -> None:
            arg_list = list(args)
            calls.append((script_rel, arg_list))
            for flag in ("--out", "--staging"):
                if flag in arg_list:
                    Path(arg_list[arg_list.index(flag) + 1]).mkdir(parents=True, exist_ok=True)
            if script_rel in (
                "scripts/mission/make_mission.py",
                "scripts/ui/stage_pipboy_wrist.py",
            ):
                raise _Stop(script_rel)

        work = root / "work"
        ns = SimpleNamespace(
            work=str(work),
            out=str(root / "out"),
            render_python=None,
            starfield_dir=str(root / "sf"),
            fo4_data=str(root / "fo4"),
            port=str(root / "FO4Port.esm"),
            port_ids=str(root / "ids.json"),
            door_anim_dll=str(root / "calumi.dll"),
            collision_template=str(root / "col.nif"),
            texconv=str(root / "texconv.exe"),
            owner_set=str(owner),
            profile="player",
            commonlibsf=None,
            msvc_env=None,
            no_walk_harness=True,
            **extra,
        )
        error: BaseException | None = None
        mcb._run_py = spy
        try:
            try:
                mcb.stage_from_checkout(ns)
            except (mcb.BundleRefused, _Stop) as exc:
                error = exc
        finally:
            mcb._run_py = orig
        return {
            "error": error,
            "calls": calls,
            "scripts": [script for script, _args in calls],
        }


if __name__ == "__main__":
    unittest.main()
