"""Regression tests for A1(b) Pool of 40 ('40 for all', GAP-J3-05).

Verifies that every active S.P.E.C.I.A.L. allocator, plugin writer, Papyrus script,
SFSE native menu INI/host, core value store, and beginning-pilot log validator
agrees on the 40-point creation pool (7 stats at base 1 + 33 points to spend = 40
in additive pickers, matching #806's 40-point total = 5 base x 7 + 5 unspent in
increment/decrement pickers), and documents FO4SF_SpecialPool28's backward-compat
off-by-default status.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts" / "newgame") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
if str(ROOT / "scripts" / "progression") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "progression"))
if str(ROOT / "scripts" / "ui") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "ui"))

import make_newgame as ng  # noqa: E402
import make_pipboy_stage_ini as pip_ini  # noqa: E402
from fo4sf.beginning_pilot import evaluate_beginning_logs  # noqa: E402
from fo4sf.progression import tables as prog_tables  # noqa: E402
from tests.test_exit_arrival import translated_functions  # noqa: E402
from tests.test_fo4_beginning_pilot import (  # noqa: E402
    _handwritten_mission_lines,
    _handwritten_newgame_lines,
)


class SpecialPool40Tests(unittest.TestCase):
    def test_newgame_writer_script_and_python_agree_on_33_points_and_40_total(self) -> None:
        cs = (ROOT / "dotnet" / "NewGame" / "Program.cs").read_text(encoding="utf-8")
        psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameSpecial.psc").read_text(encoding="utf-8")

        self.assertEqual(ng.SPECIAL_BASE, 1)
        self.assertEqual(ng.SPECIAL_POINTS, 33)
        self.assertEqual(ng.SPECIAL_MAX, 10)
        self.assertEqual(len(ng.SPECIAL_STATS) * ng.SPECIAL_BASE + ng.SPECIAL_POINTS, 40)
        self.assertGreater(ng.SPECIAL_MAX_PRESSES, 10 * (ng.SPECIAL_POINTS + 1))

        self.assertIn("public const int SpecialBase = 1, SpecialPoints = 33, SpecialMax = 10;", cs)
        self.assertNotIn("SpecialPoints = 21", cs)

        self.assertIn("int Property SpecialBase = 1 Auto Const", psc)
        self.assertIn("int Property SpecialPoints = 33 Auto Const", psc)
        self.assertIn("int Property SpecialMax = 10 Auto Const", psc)
        self.assertIn(f"int Property MaxPresses = {ng.SPECIAL_MAX_PRESSES} Auto Const", psc)
        self.assertNotIn("SpecialPoints = 21", psc)
        self.assertIn("return Allocate(target)", psc)
        self.assertIn('Trace("special set S="', psc)

    def test_special_press_rejects_confirm_at_28_and_accepts_40(self) -> None:
        values = [ng.SPECIAL_BASE] * 7
        left = ng.SPECIAL_POINTS
        self.assertEqual(sum(values) + left, 40)

        # Spend 21 points (legacy FO4 28-pt total) -> 12 points still left, Confirm MUST NOT finish
        for btn in (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6):
            values, left, end = ng.special_press(values, left, btn)
            self.assertIsNone(end)
        self.assertEqual(sum(values), 28)
        self.assertEqual(left, 12)
        values, left, end = ng.special_press(values, left, 8)  # Confirm
        self.assertIsNone(end)

        # Spend the remaining 12 points -> sum == 40, left == 0 -> Confirm returns "set"
        for btn in (0, 0, 1, 1, 2, 2, 3, 4, 4, 5, 5, 6):
            values, left, end = ng.special_press(values, left, btn)
            self.assertIsNone(end)
        self.assertEqual(sum(values), 40)
        self.assertEqual(left, 0)
        _, _, end = ng.special_press(values, left, 8)  # Confirm
        self.assertEqual(end, "set")

    def test_fo4sf_newgame_special_allocate_from_lift_executes_40_point_flow(self) -> None:
        psc = (ROOT / "scripts" / "newgame" / "FO4SF_NewGameSpecial.psc").read_text(encoding="utf-8")
        compiled = compile(
            translated_functions(psc, ("ResetValues", "Apply", "Allocate", "AllocateFromLift"), "done"),
            "FO4SF_NewGameSpecial.psc",
            "exec",
        )
        # Script sequence:
        # Page 1: S x5, P x5, E x5 (=15 spent), Next (btn 3)
        # Page 2: C x4, I x5, A x5, L x4 (=18 spent -> 33 total, sum=40), Confirm (btn 5)
        p1_buttons = iter([0] * 5 + [1] * 5 + [2] * 5 + [3])
        p2_buttons = iter([0] * 4 + [1] * 5 + [2] * 5 + [3] * 4 + [5])
        seen_initial_left: list[int] = []
        written: dict[str, float] = {}
        logs: list[str] = []

        def show_p1(*args):
            if not seen_initial_left:
                seen_initial_left.append(int(args[7]))
            return next(p1_buttons)

        def show_p2(*args):
            return next(p2_buttons)

        special_avs = [f"AV_{k}" for k in ("S", "P", "E", "C", "I", "A", "L")]
        player = SimpleNamespace(
            SetValue=lambda av, val: written.__setitem__(av, float(val)),
            GetValue=lambda av: written.get(av, 1.0),
        )
        ns = {
            "SpecialBase": 1,
            "SpecialPoints": 33,
            "SpecialMax": 10,
            "MaxPresses": 400,
            "Special": special_avs,
            "SpecialMessage": SimpleNamespace(Show=show_p1),
            "SpecialMessagePage2": SimpleNamespace(Show=show_p2),
            "Debug": SimpleNamespace(Notification=lambda m: None),
            "Game": SimpleNamespace(GetPlayer=lambda: player),
            "Trace": lambda m: logs.append(str(m)),
            "done": False,
        }
        exec(compiled, ns)
        ok = ns["AllocateFromLift"](player)
        self.assertTrue(ok)
        self.assertEqual(seen_initial_left, [33])
        self.assertEqual([int(written[av]) for av in special_avs], [6, 6, 6, 5, 6, 6, 5])
        self.assertEqual(sum(int(written[av]) for av in special_avs), 40)
        self.assertTrue(any("special set S=6 P=6 E=6 C=5 I=6 A=6 L=5 readback=6.0 5.0" in ln for ln in logs), logs)

    def test_progression_core_and_special_pool28_backward_compat_status(self) -> None:
        # #806 defines 40 as 5 base x 7 + 5 pool = 40 (sum 40, range 1..10 per stat),
        # keeping FO4SF_SpecialPool28 (0x808, default 0) for backward script/save compat.
        self.assertEqual(prog_tables.SPECIAL_POOL_DEFAULT, 40)
        self.assertEqual(prog_tables.SPECIAL_POOL_FO4_OPT, 28)

        prog_cs = (ROOT / "dotnet" / "ProgressionCore" / "Program.cs").read_text(encoding="utf-8")
        prog_psc = (ROOT / "scripts" / "progression" / "FO4SF_ProgressionQuest.psc").read_text(encoding="utf-8")
        prog_py = (ROOT / "scripts" / "progression" / "make_progression.py").read_text(encoding="utf-8")

        self.assertIn("int pool28 = 0;", prog_cs)
        self.assertIn("public const uint Pool28GlobId = 0x808;", prog_cs)
        self.assertIn('EditorID = "FO4SF_SpecialPool28"', prog_cs)
        self.assertIn("StandardSpread40 = { 6, 5, 5, 6, 7, 6, 5 };", prog_cs)
        self.assertIn("GlobalVariable Property Pool28Global Auto Const", prog_psc)
        self.assertIn("return 40", prog_psc)
        self.assertIn('p_st.add_argument("--pool28", type=int, choices=(0, 1), default=0)', prog_py)

    def test_core_values_and_sfse_special_menu_default_to_pool_of_40(self) -> None:
        core_json = json.loads((ROOT / "src" / "fo4sf" / "core" / "core_values.json").read_text(encoding="utf-8"))
        by_edid = {r["edid"]: r for r in core_json["records"]}
        for stat in ng.SPECIAL_STATS:
            rec = by_edid[f"FO4SF_Special_{stat}"]
            self.assertEqual(rec["default"], 5.0)
            self.assertEqual(rec["min"], 1.0)
        for ch in ("S", "P", "E", "C", "I", "A", "L"):
            self.assertEqual(by_edid[f"FO4SF_SpecialMenuPending{ch}"]["default"], 5.0)

        ini_text = (ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        main_cpp = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertIn("SpecialMaxPoints=40", ini_text)
        self.assertIn("g_specialMaxPoints = 40;", main_cpp)
        self.assertIn('ReadNumber(ini, L"SpecialMaxPoints", 40)', main_cpp)

        rendered = pip_ini.format_stage_ini(["PopulatePipboyInfoObj"])
        self.assertIn("SpecialMaxPoints=40", rendered)

    def test_beginning_pilot_b3_requires_40_on_both_progression_and_newgame_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            # Fallback with 40 points passes
            lines_40 = [
                "FO4SF_NEWGAME rt=75.0 special set S=7 P=6 E=5 C=5 I=7 A=5 L=5 sum=40 source=Lift readback=7.0 5.0\n"
                "FO4SF_NEWGAME rt=75.2 elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=True confirmed=True"
                if "special set" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(lines_40) + "\n", encoding="utf-8")
            res_ok = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertEqual(res_ok["steps"]["B3_exit_lift"]["status"], "PASS", res_ok)

            # Fallback with legacy 28 points fails
            lines_28 = [
                "FO4SF_NEWGAME rt=75.0 special set S=4 P=4 E=4 C=4 I=4 A=4 L=4 sum=28 source=Lift readback=4.0 4.0\n"
                "FO4SF_NEWGAME rt=75.2 elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=True confirmed=True"
                if "special set" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(lines_28) + "\n", encoding="utf-8")
            res_fail = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertEqual(res_fail["steps"]["B3_exit_lift"]["status"], "FAIL", res_fail)
            self.assertIn("!= required 40 points", res_fail["steps"]["B3_exit_lift"]["detail"])

    def test_cross_os_path_safety_no_drive_letters_in_this_test(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", text))


if __name__ == "__main__":
    unittest.main()
