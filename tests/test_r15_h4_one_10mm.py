"""Round 15 Wave B Item H4 tests: One 10mm seam (game_start_config.json -> NewGame -> PSC -> check-bundle)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "core"), str(ROOT / "scripts" / "newgame"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle as mcb  # noqa: E402
import make_newgame as mng  # noqa: E402
from fo4sf.beginning_pilot import verify_bundle_beginning_readiness  # noqa: E402
from fo4sf.core import cross_plugin_check as cpc  # noqa: E402
from tests.test_exit_arrival import Reference, translated_functions  # noqa: E402
from tests.test_fo4_beginning_pilot import BeginningPilotTests  # noqa: E402

GAME_START_CFG = ROOT / "src" / "fo4sf" / "core" / "game_start_config.json"
NEWGAME_PSC = ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc"
NEWGAME_PROJ = ROOT / "dotnet" / "NewGame" / "NewGame.csproj"
COREVALUES_PROJ = ROOT / "dotnet" / "CoreValues" / "CoreValues.csproj"


class R15H4One10mmTests(unittest.TestCase):
    def test_game_start_config_has_fo4_vault_pistol_row(self) -> None:
        cfg = json.loads(GAME_START_CFG.read_text(encoding="utf-8"))
        vp = cfg["games"]["fo4"]["vault_pistol"]
        self.assertEqual(vp["weapon_plugin"], "FO4SFCoreValues.esm")
        self.assertEqual(int(vp["weapon_id"], 16), 0x000899)
        self.assertEqual(vp["ammo_plugin"], "FO4SFCoreValues.esm")
        self.assertEqual(int(vp["ammo_id"], 16), 0x000898)
        self.assertEqual([int(x, 16) for x in vp["ref_ids"]], [0x820, 0x821])

    def test_psc_has_no_hardcoded_0822_or_id_arithmetic(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        forbidden_patterns = (
            r"GetFormFromFile\(\s*0x0*822\b",
            r"VaultPistolId\s*==\s*0x0*899\b",
            r"VaultPistolId\s*-\s*1\b",
        )
        for pat in forbidden_patterns:
            self.assertIsNone(
                re.search(pat, psc, re.IGNORECASE),
                f"FO4SF_NewGameQuest.psc still contains forbidden hardcoded 10mm pattern {pat!r}",
            )
        self.assertIn("Weapon Property VaultPistolBase Auto Const Mandatory", psc)
        self.assertIn("Ammo Property VaultAmmoBase Auto Const", psc)
        self.assertIn("int Property VaultAmmoCount = 48 Auto Const", psc)
        self.assertIn("AddInventoryEventFilter(VaultPistolBase)", psc)
        self.assertIn("AddInventoryEventFilter(VaultAmmoBase)", psc)

    def test_psc_ammo_world_pickup_tops_up_count_1_to_48(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        funcs = ("ObjectReference.OnItemAdded",)
        vars_csv = "pistolPickedLogged, ammoPickedLogged"
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(NEWGAME_PSC), "exec")
        player = Reference(None, (-57.0, 30.37, 0.70), form_id=0x00000014)
        ammo = "FO4_Ammo10mm (06000898)"
        inv = {ammo: 1}  # Simulate Starfield world REFR pickup granting only 1 round despite XCNT=48
        traces: list[str] = []

        def add_item(item, count=1, _silent=False):
            inv[item] = inv.get(item, 0) + count
            # Re-entrant OnItemAdded from AddItem must not double-grant or double-log
            ns["OnItemAdded"](player, item, count, None, None, 0)

        player.AddItem = add_item  # type: ignore[attr-defined]
        ns = dict(
            Trace=traces.append,
            pistolPickedLogged=False,
            ammoPickedLogged=False,
            VaultPistolBase="FO4_10mmPistol (06000899)",
            VaultAmmoBase=ammo,
            VaultAmmoCount=48,
            Game=SimpleNamespace(GetPlayer=lambda: player),
            GetStage=lambda: 20,
        )
        exec(compiled, ns)
        ns["OnItemAdded"](player, ammo, 1, None, None, 0)
        self.assertEqual(inv[ammo], 48)
        self.assertEqual(traces, [f"pistol ammo picked item={ammo} count=48 base={ammo}"])

    def test_psc_uses_only_bound_vault_pistol_and_ammo_bases_for_both_modes(self) -> None:
        psc = NEWGAME_PSC.read_text(encoding="utf-8")
        funcs = ("EnsureVaultInteractivesRegistered", "ObjectReference.OnItemAdded")
        vars_csv = (
            "itemWatchRegistered, pipboyRegistered, pipboyEquipWatchRegistered, cogDoorRegistered, cogDoorWatchedRef, "
            "consoleRegistered, consoleWatchedRef, portConsoleRegistered, portConsoleWatchedRef, "
            "consoleOpening, pistolPickedLogged"
        )
        compiled = compile(translated_functions(psc, funcs, vars_csv), str(NEWGAME_PSC), "exec")

        class _FormObj:
            def __init__(self, label: str) -> None:
                self.label = label

            def __str__(self) -> str:
                return self.label

        for mode_name, weap_lbl, ammo_lbl, fid in (
            ("fo4_10mm_1", "FO4_10mmPistol (06000899)", "FO4_Ammo10mm (06000898)", 0x000899),
            ("fo4_10mm_0_fallback", "FO4SF_Vault111_10mm (0A000822)", "Ammo45Caliber (002B5598)", 0x000822),
        ):
            with self.subTest(mode=mode_name):
                player = Reference(None, (-57.0, 30.0, 1.29), form_id=0x00000014)
                equipped: set[object] = set()
                player.EquipItem = lambda item, _p=False, _s=False: equipped.add(item)
                player.IsEquipped = lambda item: item in equipped
                weap = _FormObj(weap_lbl)
                ammo = _FormObj(ammo_lbl)
                traces: list[str] = []
                calls: list[tuple[object, ...]] = []
                ns = dict(
                    Trace=traces.append,
                    itemWatchRegistered=False,
                    pipboyRegistered=True,
                    pipboyEquipWatchRegistered=True,
                    PipboyWristArmor=None,
                    cogDoorRegistered=True,
                    cogDoorWatchedRef=None,
                    consoleRegistered=True,
                    consoleWatchedRef=None,
                    portConsoleRegistered=True,
                    portConsoleWatchedRef=None,
                    consoleOpening=False,
                    pistolPickedLogged=False,
                    VaultPistolBase=weap,
                    VaultAmmoBase=ammo,
                    VaultPistolId=fid,
                    PipboyCorpseRef=None,
                    GearDoorConsoleRef=None,
                    CogDoorId=0,
                    ConsoleRefId=0,
                    LiftId=0,
                    VaultPlugin="FO4Port.esm",
                    TestModeGlobal=None,
                    Game=SimpleNamespace(
                        GetPlayer=lambda: player,
                        GetFormFromFile=lambda *_: (_ for _ in ()).throw(AssertionError("unexpected GetFormFromFile")),
                    ),
                    AddInventoryEventFilter=lambda f: calls.append(("filter", f)),
                    RegisterForRemoteEvent=lambda target, ev: calls.append(("register", target, ev)),
                    GetStage=lambda: 20,
                )
                exec(compiled, ns)
                ns["EnsureVaultInteractivesRegistered"]()
                self.assertEqual(calls, [("filter", weap), ("filter", ammo), ("register", player, "OnItemAdded")])
                ns["OnItemAdded"](player, weap, 1, None, None, 0)
                ns["OnItemAdded"](player, ammo, 48, None, None, 0)
                self.assertTrue(any(f"pistol picked item={weap_lbl} count=1 equipped=True base={weap_lbl}" == t for t in traces), traces)
                self.assertTrue(any(f"pistol ammo picked item={ammo_lbl} count=48 base={ammo_lbl}" == t for t in traces), traces)

    def test_make_newgame_and_make_core_bundle_forward_fo4_10mm(self) -> None:
        fake_args = SimpleNamespace(
            exit_lift=None, hold=None, omit_hold_group=None, no_mq101debug=False, mq101debug=None,
            debug_after_hold=None, looks=True, race_menu_mode=None, special=True, version=True,
            build_version=None, keep_inventory=False, clear_inventory=False, vault_suit=None,
            allow_temporary_anchor=False, require_persistent_anchor=False, no_o2_fill=False,
            fade_hold=False, no_fade_hold=False, start_choice_backdrop=None, warfare_starts=None,
            start_places=None, game=None, game_start_config="cfg.json", fo4_10mm=1, core_values_esm="cv.esm",
        )
        opts = mng.tool_options(fake_args)
        self.assertIn("--fo4-10mm", opts)
        self.assertEqual(opts[opts.index("--fo4-10mm") + 1], "1")
        self.assertIn("--core-values-esm", opts)
        self.assertIn("--game-start-config", opts)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            port = root / "FO4Port.esm"
            port.write_bytes(b"TES4")
            owner = root / "owner"
            owner.mkdir()
            (owner / "FO4TerrainCore.esm").write_bytes(b"TES4")
            (owner / "FO4ActorRaider.esm").write_bytes(b"TES4")
            ng_calls: list[list[str]] = []
            orig_run_py = mcb._run_py

            def _spy_run(_py, script_rel, args):
                arg_l = list(args)
                out_flag = "--out" if "--out" in arg_l else "--staging"
                out_d = Path(arg_l[arg_l.index(out_flag) + 1])
                out_d.mkdir(parents=True, exist_ok=True)
                if script_rel == "scripts/core/make_core_values.py":
                    (out_d / "Data").mkdir(parents=True, exist_ok=True)
                    (out_d / "Data" / "FO4SFCoreValues.esm").write_bytes(b"TES4_CV")
                elif script_rel == "scripts/newgame/make_newgame.py":
                    ng_calls.append(arg_l)
                    (out_d / "plan.json").write_text(
                        json.dumps({
                            "options": {"hold": ",".join(f"Q{i}" for i in range(199)), "fade_hold": False},
                            "points": {"pod": {"step_m": -2.5}},
                        }),
                        encoding="utf-8",
                    )

            mcb._run_py = _spy_run
            try:
                mcb.stage_from_checkout(SimpleNamespace(
                    work=str(root / "work"),
                    out=str(root / "out"),
                    render_python=None,
                    starfield_dir=str(root / "sf"),
                    fo4_data=str(root / "fo4"),
                    port=str(port),
                    port_ids=str(root / "ids.json"),
                    door_anim_dll=str(root / "calumi.dll"),
                    collision_template=str(root / "col.nif"),
                    texconv=str(root / "texconv.exe"),
                    owner_set=str(owner),
                    profile="player",
                    commonlibsf=None,
                    msvc_env=None,
                    no_walk_harness=True,
                    allow_starfield_standins=True,
                ))
            finally:
                mcb._run_py = orig_run_py

            self.assertEqual(len(ng_calls), 1)
            self.assertIn("--fo4-10mm", ng_calls[0])
            self.assertEqual(ng_calls[0][ng_calls[0].index("--fo4-10mm") + 1], "1")
            self.assertIn("--core-values-esm", ng_calls[0])

    @unittest.skipUnless(shutil.which("dotnet") is not None, "dotnet SDK required for binary .esm swap verification")
    def test_swapping_vault_pistol_in_game_start_config_swaps_built_newgame_and_check_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # 1. Build CoreValues (all arsenal weapons/ammo) + NewGame selftest fixtures
            cv_st = tmp / "cv_st"
            r_cv = subprocess.run(
                ["dotnet", "run", "--project", str(COREVALUES_PROJ), "-c", "Release", "--", "selftest", str(cv_st)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_cv.returncode, 0, r_cv.stdout + "\n" + r_cv.stderr)
            ars_sf = cv_st / "arsenal_fixture" / "Starfield.esm"
            cv_full_dir = tmp / "cv_full"
            r_cv_bld = subprocess.run(
                [
                    "dotnet", "run", "--project", str(COREVALUES_PROJ), "-c", "Release", "--",
                    "build", str(ars_sf), str(cv_full_dir),
                    "--fo4-10mm", "1", "--fo4-p5-weapons", "1", "--fo4-arsenal", "1",
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_cv_bld.returncode, 0, r_cv_bld.stdout + "\n" + r_cv_bld.stderr)
            cv_full_esm = cv_full_dir / "FO4SFCoreValues.esm"

            ng_st = tmp / "ng_st"
            r_ng = subprocess.run(
                ["dotnet", "run", "--project", str(NEWGAME_PROJ), "-c", "Release", "--", "selftest", str(ng_st)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_ng.returncode, 0, r_ng.stdout + "\n" + r_ng.stderr)

            sf_esm = ng_st / "Starfield.esm"
            port_esm = ng_st / "FO4Port.esm"
            port_ids = ng_st / "formids.json"
            core_esm = ng_st / "FO4TerrainCore.esm"
            points_json = ng_st / "points.json"

            # 2. Swap games.fo4.vault_pistol in a temp copy of game_start_config.json (Pipe Pistol 0x8A2 + .38 0x8A1)
            swapped_cfg = tmp / "swapped_game_start_config.json"
            cfg_obj = json.loads(GAME_START_CFG.read_text(encoding="utf-8"))
            cfg_obj["games"]["fo4"]["vault_pistol"] = {
                "weapon_plugin": "FO4SFCoreValues.esm",
                "weapon_id": "0x0008A2",
                "ammo_plugin": "FO4SFCoreValues.esm",
                "ammo_id": "0x0008A1",
                "ref_ids": ["0x000820", "0x000821"],
            }
            swapped_cfg.write_text(json.dumps(cfg_obj, indent=2), encoding="utf-8")

            swapped_out = tmp / "ng_swapped"
            common_args = [
                str(sf_esm), str(port_esm), str(port_ids), str(core_esm), str(points_json),
            ]
            r_w = subprocess.run(
                [
                    "dotnet", "run", "--project", str(NEWGAME_PROJ), "-c", "Release", "--no-build", "--",
                    "write", *common_args, str(swapped_out),
                    "--fo4-10mm", "1",
                    "--core-values-esm", str(cv_full_esm),
                    "--game-start-config", str(swapped_cfg),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_w.returncode, 0, r_w.stdout + "\n" + r_w.stderr)
            r_c = subprocess.run(
                [
                    "dotnet", "run", "--project", str(NEWGAME_PROJ), "-c", "Release", "--no-build", "--",
                    "check", str(swapped_out / "FO4SFNewGame.esm"), *common_args,
                    "--fo4-10mm", "1",
                    "--core-values-esm", str(cv_full_esm),
                    "--game-start-config", str(swapped_cfg),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_c.returncode, 0, r_c.stdout + "\n" + r_c.stderr)

            rep_swapped = cpc.inspect_esm_binary(str(swapped_out / "FO4SFNewGame.esm"))
            self.assertIn(("REFR:FO4SF_Vault111PistolRef.NAME", "FO4SFCoreValues.esm", 0x0008A2), rep_swapped.cross_plugin_item_refs)
            self.assertIn(("REFR:FO4SF_Vault111AmmoRef.NAME", "FO4SFCoreValues.esm", 0x0008A1), rep_swapped.cross_plugin_item_refs)
            vp_map = {
                vp.prop_name: vp.object_refs[0][1:]
                for vp in rep_swapped.vmad_properties
                if vp.script_name == "FO4SF_NewGameQuest" and vp.prop_name in ("VaultPistolBase", "VaultAmmoBase")
            }
            self.assertEqual(vp_map["VaultPistolBase"], ("FO4SFCoreValues.esm", 0x0008A2))
            self.assertEqual(vp_map["VaultAmmoBase"], ("FO4SFCoreValues.esm", 0x0008A1))

            # 3. Verify check-bundle B2/B5 accepts both --fo4-10mm 1 (0x899/0x898) and --fo4-10mm 0 (0x822/0x2B5598)
            helper = BeginningPilotTests("_build_synthetic_bundle")
            bundle_10mm = helper._build_synthetic_bundle(tmp / "b_10mm")
            shutil.copy2(cv_full_esm, bundle_10mm / "FO4SFCoreValues.esm")
            ng_10mm_out = tmp / "ng_10mm_real"
            r_w10 = subprocess.run(
                [
                    "dotnet", "run", "--project", str(NEWGAME_PROJ), "-c", "Release", "--no-build", "--",
                    "write", *common_args, str(ng_10mm_out),
                    "--fo4-10mm", "1", "--core-values-esm", str(cv_full_esm),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_w10.returncode, 0, r_w10.stdout + "\n" + r_w10.stderr)
            shutil.copy2(ng_10mm_out / "FO4SFNewGame.esm", bundle_10mm / "FO4SFNewGame.esm")
            res_10mm = verify_bundle_beginning_readiness(str(bundle_10mm))
            self.assertTrue(res_10mm["ok"], res_10mm["problems"])

            # Fallback --fo4-10mm 0 (0x822 / 0x2B5598) also passes check-bundle B2
            bundle_fb = helper._build_synthetic_bundle(tmp / "b_fb")
            shutil.copy2(cv_full_esm, bundle_fb / "FO4SFCoreValues.esm")
            shutil.copy2(ng_st / "out" / "cv_rollback_10mm0" / "FO4SFNewGame.esm", bundle_fb / "FO4SFNewGame.esm")
            res_fb = verify_bundle_beginning_readiness(str(bundle_fb))
            self.assertTrue(res_fb["ok"], res_fb["problems"])

            # Bad bound base (Pipe Pistol 0x8A2 not in default game_start_config.json) fails check-bundle B2
            shutil.copy2(swapped_out / "FO4SFNewGame.esm", bundle_10mm / "FO4SFNewGame.esm")
            res_bad = verify_bundle_beginning_readiness(str(bundle_10mm))
            self.assertFalse(res_bad["ok"])
            self.assertEqual(res_bad["steps"]["B2_gear_door"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
