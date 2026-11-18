"""Unit tests for I2 (and I4): adopt-core, --animated-doors with --prev and --installed-port (--compare-installed)
with zero installed FormIDs moved, and build --dry-run."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "scripts"), os.path.join(ROOT, "scripts", "terrain")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_starfield  # noqa: E402
import interior_batch as ib  # noqa: E402
import pack_staging as ps  # noqa: E402
import vmad_patch  # noqa: E402
from fo4sf import fo4land  # noqa: E402


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pluginspike_dll() -> str:
    for cfg in ("Release", "Debug"):
        cand = os.path.join(ROOT, "dotnet", "PluginSpike", "bin", cfg, "net9.0", "PluginSpike.dll")
        if os.path.isfile(cand):
            return cand
    subprocess.run(
        ["dotnet", "build", os.path.join(ROOT, "dotnet", "PluginSpike", "PluginSpike.csproj"), "-c", "Release", "--nologo"],
        check=True,
    )
    return os.path.join(ROOT, "dotnet", "PluginSpike", "bin", "Release", "net9.0", "PluginSpike.dll")


class AdoptCoreAndAnimatedPrevTests(unittest.TestCase):
    def _make_stage_without_core_pin(self, root: str):
        stage = os.path.join(root, "interiors_b10")
        port = os.path.join(stage, "port")
        core = os.path.join(root, "terrain_core_v6i")
        os.makedirs(port)
        os.makedirs(core)
        core_bytes = ps.companion_plugin_bytes() + b"COREPAYLOAD"
        with open(os.path.join(core, "FO4TerrainCore.esm"), "wb") as f:
            f.write(core_bytes)
        files = {
            "FO4Port.esm": ps.companion_plugin_bytes(),
            "FO4Port - Main.ba2": b"BTDX" + b"main" * 8,
            "FO4Port - Textures.ba2": b"BTDX" + b"tex1" * 8,
        }
        for name, body in files.items():
            with open(os.path.join(port, name), "wb") as f:
                f.write(body)
        with open(os.path.join(port, "doors_check.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "plugin": "FO4Port.esm",
                    "core": core,
                    "checks": [["masters unchanged", True], ["every record byte-identical", True]],
                    "pass": True,
                },
                f,
            )
        with open(os.path.join(stage, "result.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "batch": 10,
                    "name": "interiors_b10",
                    "pass": True,
                    "error": None,
                    "core": os.path.join(root, "missing_old_core"),
                    "pins": {"plugin": _sha256_bytes(files["FO4Port.esm"])},
                    "install": {"files": list(files), "plugins_txt": ["FO4Port.esm"]},
                    "steps": {
                        "pack": {
                            "sha256": {k: _sha256_bytes(v) for k, v in files.items() if k != "FO4Port.esm"}
                        }
                    },
                },
                f,
            )
        return stage, core, _sha256_bytes(core_bytes)

    def test_adopt_core_records_verified_core_sha256_and_unblocks_installer_without_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage, core, core_sha = self._make_stage_without_core_pin(tmp)
            orig_result_sha = _sha256_file(os.path.join(stage, "result.json"))

            game = os.path.join(tmp, "game")
            os.makedirs(os.path.join(game, "Data"))
            copy_src = os.path.join(core, "FO4TerrainCore.esm")
            with open(copy_src, "rb") as s, open(os.path.join(game, "Data", "FO4TerrainCore.esm"), "wb") as d:
                d.write(s.read())
            pt = os.path.join(tmp, "Plugins.txt")
            with open(pt, "w", encoding="utf-8") as f:
                f.write("*FO4TerrainCore.esm\n")

            # Before adopt-core: deploy_starfield refuses without --other-core because pins.core_plugin is absent.
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=pt):
                with self.assertRaises(SystemExit):
                    deploy_starfield.install(
                        SimpleNamespace(
                            action="install", staging="", batch=stage, starfield=game,
                            min_free_gb=0.0, dry_run=False, other_core=False, plugin_name="",
                        )
                    )

            # Non-destructive --out adoption leaves original stage untouched and records pins.core_plugin.
            adopted = os.path.join(tmp, "interiors_b10_adopted")
            rc = ib.main(["adopt-core", "--stage", stage, "--out", adopted])
            self.assertEqual(rc, 0)
            self.assertEqual(_sha256_file(os.path.join(stage, "result.json")), orig_result_sha)

            with open(os.path.join(adopted, "result.json"), encoding="utf-8") as f:
                adopted_res = json.load(f)
            self.assertEqual(adopted_res["pins"]["core_plugin"], core_sha)
            self.assertEqual(adopted_res["steps"]["adopt_core"]["checks"], 2)

            # Installer now accepts the adopted stage WITHOUT --other-core!
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=pt):
                deploy_starfield.install(
                    SimpleNamespace(
                        action="install", staging="", batch=adopted, starfield=game,
                        min_free_gb=0.0, dry_run=False, other_core=False, plugin_name="",
                    )
                )
            self.assertTrue(os.path.isfile(os.path.join(game, "Data", "FO4Port.esm")))

            # And if a DIFFERENT core is in Data, installer still refuses without --other-core.
            game_other = os.path.join(tmp, "game_other")
            os.makedirs(os.path.join(game_other, "Data"))
            with open(os.path.join(game_other, "Data", "FO4TerrainCore.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes() + b"OTHERCORE")
            with patch.object(deploy_starfield, "plugins_txt_path", return_value=pt):
                with self.assertRaises(SystemExit):
                    deploy_starfield.install(
                        SimpleNamespace(
                            action="install", staging="", batch=adopted, starfield=game_other,
                            min_free_gb=0.0, dry_run=False, other_core=False, plugin_name="",
                        )
                    )

    def test_adopt_core_refuses_failed_doors_check_mismatched_core_and_git_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage, _core, _sha = self._make_stage_without_core_pin(tmp)
            other_core = os.path.join(tmp, "other_core")
            os.makedirs(other_core)
            with open(os.path.join(other_core, "FO4TerrainCore.esm"), "wb") as f:
                f.write(ps.companion_plugin_bytes() + b"DIFFERENT")

            # Mismatched --core is refused.
            self.assertEqual(
                ib.main(["adopt-core", "--stage", stage, "--core", other_core, "--out", os.path.join(tmp, "bad1")]),
                1,
            )

            # Git worktree --out is refused (R4).
            git_dir = os.path.join(tmp, "git_repo")
            os.makedirs(os.path.join(git_dir, ".git"))
            self.assertEqual(
                ib.main(["adopt-core", "--stage", stage, "--out", os.path.join(git_dir, "out")]),
                1,
            )

            # Failed doors_check is refused.
            with open(os.path.join(stage, "port", "doors_check.json"), "w", encoding="utf-8") as f:
                json.dump({"plugin": "FO4Port.esm", "checks": [["door check", False]], "pass": False}, f)
            self.assertEqual(
                ib.main(["adopt-core", "--stage", stage, "--out", os.path.join(tmp, "bad2")]),
                1,
            )

    def test_reconcile_formids_and_pluginspike_compare_keep_zero_installed_ids_moved(self):
        dll = _pluginspike_dll()
        with tempfile.TemporaryDirectory() as tmp:
            sf_data = os.path.join(tmp, "sf_data")
            os.makedirs(sf_data)
            env = dict(os.environ, STARFIELD_DATA=sf_data)

            # Build synthetic installed_port (b00: BaseCell with animated xtel door + base LCTNs)
            # and synthetic uninstalled prev_port (b10: BaseCell + BatchCell without xtel door, where BatchCell STATs
            # claimed the same FormIDs that b00 used for its xtel door and LCTNs).
            base_cell = os.path.join(tmp, "BaseCell.json")
            batch_cell = os.path.join(tmp, "BatchCell.json")
            with open(base_cell, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 3,
                        "cell": "BaseCell",
                        "cell_name": "Base Cell",
                        "location_formkey": "001000:Fallout4.esm",
                        "location_editor_id": "BaseCellLocation",
                        "location_name": "Base Cell",
                        "refs": [
                            {
                                "formkey": "001001:Fallout4.esm",
                                "base_formkey": "001002:Fallout4.esm",
                                "type": "Static",
                                "base_editor_id": "BaseWall",
                                "model": "Set\\BaseWall.nif",
                                "pos": [0.0, 0.0, 0.0],
                                "rot": [0.0, 0.0, 0.0],
                                "scale": 1.0,
                                "disabled": 0,
                            }
                        ],
                    },
                    f,
                )
            with open(batch_cell, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 3,
                        "cell": "BatchCell",
                        "cell_name": "Batch Cell",
                        "location_formkey": "002000:Fallout4.esm",
                        "location_editor_id": "BatchCellLocation",
                        "location_name": "Batch Cell",
                        "refs": [
                            {
                                "formkey": "002001:Fallout4.esm",
                                "base_formkey": "002002:Fallout4.esm",
                                "type": "Static",
                                "base_editor_id": "BatchPillar",
                                "model": "Set\\BatchPillar.nif",
                                "pos": [70.0, 0.0, 0.0],
                                "rot": [0.0, 0.0, 0.0],
                                "scale": 1.0,
                                "disabled": 0,
                            }
                        ],
                    },
                    f,
                )

            manifest_b00 = os.path.join(tmp, "manifest_b00.json")
            with open(manifest_b00, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "items": [
                            {"editor_id": "FO4Port_BaseWall", "model": "fo4port\\set\\basewall.nif", "source": "Set\\BaseWall.nif"},
                            {
                                "editor_id": "FO4Port_LoadDoor01",
                                "model": "fo4port\\set\\loaddoor01.nif",
                                "source": "Set\\LoadDoor01.nif",
                                "load_door": {"bounds": [[-1, -1, 0], [1, 1, 2]]},
                            },
                        ],
                        "failures": [],
                    },
                    f,
                )
            manifest_b10 = os.path.join(tmp, "manifest_b10.json")
            with open(manifest_b10, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "items": [
                            {"editor_id": "FO4Port_BaseWall", "model": "fo4port\\set\\basewall.nif", "source": "Set\\BaseWall.nif"},
                            {
                                "editor_id": "FO4Port_LoadDoor01",
                                "model": "fo4port\\set\\loaddoor01.nif",
                                "source": "Set\\LoadDoor01.nif",
                                "load_door": {"bounds": [[-1, -1, 0], [1, 1, 2]]},
                            },
                            {"editor_id": "FO4Port_BatchPillar", "model": "fo4port\\set\\batchpillar.nif", "source": "Set\\BatchPillar.nif"},
                        ],
                        "failures": [],
                    },
                    f,
                )

            # Seed b00 and b10 from a common ancestor where LCTNs were not yet allocated, so b10 allocates BatchPillar
            # at 0x804 while b00 allocates LCTN:FO4Port_BaseCellLocation at 0x804!
            ancestor_ids = {
                "STAT:FO4Port_BaseWall": 0x800,
                "DOOR:FO4Port_LoadDoor01": 0x801,
                "CELL:FO4Port_BaseCell": 0x802,
                "REFR:FO4Port_BaseCell:001001:Fallout4.esm": 0x803,
            }
            inst_dir = os.path.join(tmp, "installed_b00")
            prev_dir = os.path.join(tmp, "prev_b10")
            os.makedirs(inst_dir)
            os.makedirs(prev_dir)
            with open(os.path.join(inst_dir, "formids.json"), "w", encoding="utf-8") as f:
                json.dump(ancestor_ids, f)
            with open(os.path.join(prev_dir, "formids.json"), "w", encoding="utf-8") as f:
                json.dump(ancestor_ids, f)

            subprocess.run(["dotnet", dll, inst_dir, manifest_b00, base_cell], check=True, env=env, capture_output=True)
            subprocess.run(["dotnet", dll, prev_dir, manifest_b10, base_cell, batch_cell], check=True, env=env, capture_output=True)

            inst_ids = ib.load(os.path.join(inst_dir, "formids.json"))
            prev_ids = ib.load(os.path.join(prev_dir, "formids.json"))
            # Confirm real FormID collision exists between inst_ids and prev_ids (just like b00 vs b10 on disk!).
            self.assertEqual(inst_ids["LCTN:FO4Port_BaseCellLocation"], prev_ids["STAT:FO4Port_BatchPillar"])

            # If prev_installed=True, reconcile_formids MUST refuse to move any installed ID!
            with self.assertRaises(ValueError):
                ib.reconcile_formids(prev_ids, inst_ids, prev_installed=True)

            # With prev_installed=False, reconcile_formids preserves 100% of inst_ids and moves only displaced prev IDs.
            seed_ids, rec_map = ib.reconcile_formids(prev_ids, inst_ids, prev_installed=False, reserved_ids={0x850})
            for k, v in inst_ids.items():
                self.assertEqual(seed_ids[k], v)
            self.assertNotIn(0x850, set(seed_ids.values()))

            # Build rebuilt stage using seed_ids and prove BOTH compare(inst_dir, new_dir) AND compare(prev_dir, new_dir, reconciled=rec_map) pass!
            new_dir = os.path.join(tmp, "rebuilt_b10_anim")
            os.makedirs(new_dir)
            with open(os.path.join(new_dir, "formids.json"), "w", encoding="utf-8") as f:
                json.dump(seed_ids, f)
            subprocess.run(["dotnet", dll, new_dir, manifest_b10, base_cell, batch_cell], check=True, env=env, capture_output=True)

            cmp_inst = ib.compare(inst_dir, new_dir)
            self.assertTrue(cmp_inst["pass"], cmp_inst["problems"])
            self.assertEqual(cmp_inst["ids"]["renumbered"], 0)
            self.assertEqual(cmp_inst["ids"]["missing"], 0)

            cmp_prev = ib.compare(prev_dir, new_dir, reconciled=rec_map)
            self.assertTrue(cmp_prev["pass"], cmp_prev["problems"])
            self.assertEqual(cmp_prev["ids"]["renumbered"], 0)
            self.assertEqual(cmp_prev["ids"]["reconciled"], len(rec_map))

    def test_build_dry_run_with_animated_doors_prev_and_compare_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "base")
            base_exports = os.path.join(tmp, "base_exports")
            inst = os.path.join(tmp, "doors_anim_b00", "port")
            prev = os.path.join(tmp, "interiors_b10")
            prev_port = os.path.join(prev, "port")
            core = os.path.join(tmp, "core")
            work = os.path.join(tmp, "work")
            fo4_data = os.path.join(tmp, "fo4_data")
            sf = os.path.join(tmp, "sf")
            for d in (base, base_exports, inst, prev_port, core, work, fo4_data, os.path.join(sf, "Data")):
                os.makedirs(d, exist_ok=True)

            esm = ps.companion_plugin_bytes()
            for d in (base, inst, prev_port):
                with open(os.path.join(d, "FO4Port.esm"), "wb") as f:
                    f.write(esm)
            with open(os.path.join(core, "FO4TerrainCore.esm"), "wb") as f:
                f.write(esm + b"CORE")
            with open(os.path.join(fo4_data, "Fallout4.esm"), "wb") as f:
                f.write(esm + b"FO4")

            with open(os.path.join(base_exports, "BaseCell.json"), "w", encoding="utf-8") as f:
                json.dump({"cell": "BaseCell", "refs": []}, f)
            with open(os.path.join(base, "doors.json"), "w", encoding="utf-8") as f:
                json.dump({"doors": [{"src": "001000:Fallout4.esm", "marker": "00E175"}]}, f)
            with open(os.path.join(base, "formids.json"), "w", encoding="utf-8") as f:
                json.dump({"CELL:FO4Port_BaseCell": 0x800}, f)
            with open(os.path.join(inst, "formids.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "CELL:FO4Port_BaseCell": 0x800,
                        "DOOR:FO4Port_DoorA:xtel": 0x801,
                        "LCTN:FO4Port_InteriorsLocation": 0x802,
                    },
                    f,
                )
            with open(os.path.join(prev_port, "formids.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "CELL:FO4Port_BaseCell": 0x800,
                        "STAT:FO4Port_BatchMesh1": 0x801,
                        "STAT:FO4Port_BatchMesh2": 0x802,
                        "LCTN:FO4Port_InteriorsLocation": 0x900,
                        "CELL:FO4Port_BatchCell1": 0x901,
                    },
                    f,
                )
            plan = os.path.join(tmp, "plan.json")
            with open(plan, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "batches": [
                            {
                                "batch": 1,
                                "name": "b1",
                                "work_staging_gb_est": 0.1,
                                "archives_gb_est": 0.1,
                                "cells": [{"editor_id": "BatchCell1", "formkey": "002000:Fallout4.esm"}],
                            }
                        ]
                    },
                    f,
                )
            with open(os.path.join(prev, "result.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "batch": 1,
                        "name": "interiors_b10",
                        "pass": True,
                        "installed": False,
                        "pins": {
                            "base_plugin": _sha256_bytes(esm),
                            "plugin": _sha256_bytes(esm),
                        },
                    },
                    f,
                )

            out_dry = os.path.join(tmp, "dry_out")
            rc = ib.main(
                [
                    "build",
                    "--dry-run",
                    "--batch", "1",
                    "--plan", plan,
                    "--base", base,
                    "--base-exports", base_exports,
                    "--prev", prev,
                    "--compare-installed", inst,
                    "--animated-doors",
                    "--core", core,
                    "--work", work,
                    "--out", out_dry,
                    "--fo4-data", fo4_data,
                    "--starfield", sf,
                    "--content-resources", tmp,
                    "--texconv", tmp,
                    "--collision-template", tmp,
                    "--fo4export", tmp,
                    "--pluginspike", tmp,
                    "--min-free-gb", "0",
                ]
            )
            self.assertEqual(rc, 0)
            dry_doc = ib.load(os.path.join(out_dry, "dry_run.json"))
            self.assertTrue(dry_doc["pass"])
            self.assertEqual(dry_doc["formids"]["installed_moved"], 0)
            self.assertEqual(dry_doc["formids"]["installed_keys_adopted"], 1)
            self.assertEqual(dry_doc["formids"]["displaced_by_installed"], 2)
            # Confirm work dir stayed untouched during --dry-run!
            self.assertEqual(os.listdir(work), [])


class RootLocationParentTests(unittest.TestCase):
    def test_default_root_location_parent_is_sha256_byte_identical_and_custom_parent_updates_only_root_lctn(self):
        self.assertEqual(ib.normalize_parent_formkey(""), "Starfield.esm:01B736")
        self.assertEqual(ib.normalize_parent_formkey("01B736:Starfield.esm"), "Starfield.esm:01B736")
        self.assertEqual(ib.normalize_parent_formkey("FO4SFHome.esm:0x00810"), "FO4SFHome.esm:000810")
        with self.assertRaises(ValueError):
            ib.normalize_parent_formkey("BadPlugin.esp:000800")

        dll = _pluginspike_dll()
        with tempfile.TemporaryDirectory() as tmp:
            sf_data = os.path.join(tmp, "sf_data")
            os.makedirs(sf_data)
            env = dict(os.environ, STARFIELD_DATA=sf_data)

            manifest = os.path.join(tmp, "manifest.json")
            cell = os.path.join(tmp, "ConcordMuseum01.json")
            with open(manifest, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "items": [
                            {"editor_id": "FO4Port_MuseumWall", "model": "fo4port\\set\\wall.nif", "source": "Set\\Wall.nif"}
                        ],
                        "failures": [],
                    },
                    f,
                )
            with open(cell, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 3,
                        "cell": "ConcordMuseum01",
                        "location": {"formkey": "019000:Fallout4.esm", "editor_id": "ConcordMuseumLocation", "name": "Museum"},
                        "refs": [
                            {
                                "formkey": "019001:Fallout4.esm",
                                "base_formkey": "019002:Fallout4.esm",
                                "type": "Static",
                                "base_editor_id": "MuseumWall",
                                "model": "Set\\Wall.nif",
                                "pos": [0.0, 0.0, 0.0],
                                "rot": [0.0, 0.0, 0.0],
                                "scale": 1.0,
                                "disabled": 0,
                            }
                        ],
                    },
                    f,
                )

            out_default = os.path.join(tmp, "out_default")
            out_mars_a = os.path.join(tmp, "out_mars_a")
            out_mars_b = os.path.join(tmp, "out_mars_b")
            out_sf_custom = os.path.join(tmp, "out_sf_custom")
            out_home_custom = os.path.join(tmp, "out_home_custom")

            subprocess.run(["dotnet", dll, out_default, manifest, cell], check=True, env=env, capture_output=True)
            subprocess.run(
                ["dotnet", dll, out_mars_a, manifest, "--root-location-parent", "Starfield.esm:01B736", cell],
                check=True, env=env, capture_output=True,
            )
            subprocess.run(
                ["dotnet", dll, out_mars_b, manifest, "--root-location-parent=01B736:Starfield.esm", cell],
                check=True, env=env, capture_output=True,
            )
            subprocess.run(
                ["dotnet", dll, out_sf_custom, manifest, "--root-location-parent", "Starfield.esm:02ABCD", cell],
                check=True, env=env, capture_output=True,
            )
            subprocess.run(
                ["dotnet", dll, out_home_custom, manifest, "--root-location-parent", "FO4SFHome.esm:000810", cell],
                check=True, env=env, capture_output=True,
            )

            # R3: Default vs explicit Starfield.esm:01B736 vs 01B736:Starfield.esm must be 100% SHA-256 byte-identical!
            sha_def = _sha256_file(os.path.join(out_default, "FO4Port.esm"))
            self.assertEqual(sha_def, _sha256_file(os.path.join(out_mars_a, "FO4Port.esm")))
            self.assertEqual(sha_def, _sha256_file(os.path.join(out_mars_b, "FO4Port.esm")))
            self.assertEqual(
                _sha256_file(os.path.join(out_default, "formids.json")),
                _sha256_file(os.path.join(out_mars_a, "formids.json")),
            )

            # Custom Starfield.esm parent: every record except LCTN:FO4Port_InteriorsLocation is byte-identical, and
            # root LCTN's PNAM carries 0x0002ABCD.
            fids = ib.load(os.path.join(out_default, "formids.json"))
            root_local = fids["LCTN:FO4Port_InteriorsLocation"]
            p_def = vmad_patch.Plugin.read(os.path.join(out_default, "FO4Port.esm"))
            p_sfc = vmad_patch.Plugin.read(os.path.join(out_sf_custom, "FO4Port.esm"))
            self.assertEqual(p_def.masters(), ["Starfield.esm"])
            self.assertEqual(p_sfc.masters(), ["Starfield.esm"])
            r_def, r_sfc = p_def.records(), p_sfc.records()
            root_fid_1 = 0x01000000 | root_local
            for fid in r_def:
                if fid == root_fid_1:
                    continue
                self.assertEqual(r_def[fid], r_sfc[fid])
            pnam_def = dict(fo4land.iter_subrecords(r_def[root_fid_1][2]))[b"PNAM"]
            pnam_sfc = dict(fo4land.iter_subrecords(r_sfc[root_fid_1][2]))[b"PNAM"]
            self.assertEqual(int.from_bytes(pnam_def, "little"), 0x0001B736)
            self.assertEqual(int.from_bytes(pnam_sfc, "little"), 0x0002ABCD)

            # Custom external master (FO4SFHome.esm:000810): masters == ["Starfield.esm", "FO4SFHome.esm"] and
            # root LCTN's PNAM points to master index 1 (0x01000810).
            p_home = vmad_patch.Plugin.read(os.path.join(out_home_custom, "FO4Port.esm"))
            self.assertEqual(p_home.masters(), ["Starfield.esm", "FO4SFHome.esm"])
            r_home = p_home.records()
            root_fid_2 = 0x02000000 | root_local
            pnam_home = dict(fo4land.iter_subrecords(r_home[root_fid_2][2]))[b"PNAM"]
            self.assertEqual(int.from_bytes(pnam_home, "little"), 0x01000810)


if __name__ == "__main__":
    unittest.main()
