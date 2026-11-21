"""Unit tests for DLC tools (D1..D5): UHR exclusion, --dlc-plugins load order, prefix EditorIDs & manifest rewriter,
SCOL path/None guards, and the FO4DLC interiors driver. Pure synthetic fixtures — zero local game paths."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
sys.path.insert(0, str(ROOT / "tests"))

from ba2_fixture import general_archive  # noqa: E402
from pluginspike_fixture import ensure_pluginspike_dll  # noqa: E402
from fo4sf import nif, pipeline, sfnif  # noqa: E402
import interior_batch as ib  # noqa: E402
import interior_dlc  # noqa: E402

_cb_spec = importlib.util.spec_from_file_location("convert_batch_dlc", ROOT / "scripts" / "convert_batch.py")
convert_batch = importlib.util.module_from_spec(_cb_spec)
_cb_spec.loader.exec_module(convert_batch)

# Pinned SHA-256 parity digests produced by commit cd03411a on the synthetic fixtures below (Rule R12).
CD03411A_CHECKPOINT_EXTRA_ARCHIVES_SHA256 = "8a8336dc255dfcf5a2fac65089a685bf3b0d404b90f75ee693ca442abd8d2d90"
CD03411A_CONVERT_BATCH_EDITORIDS_SHA256 = "dd03dbb81479968a4d5c2e39e5f8e5f578b0b214d1fa9954a348ca2fd459758d"


def _sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


class D1UltraHighResAndDlcPluginsTests(unittest.TestCase):
    def test_fo4_archives_skips_ultra_high_res_and_preserves_workshop_textures(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data"
            data.mkdir()
            archives = {
                "Fallout4 - Meshes.ba2": {"meshes/base.nif": b"base-mesh"},
                "Fallout4 - Textures1.ba2": {"textures/base_d.dds": b"base-tex"},
                "DLCUltraHighResolution - Textures01.ba2": {"textures/dlc02/cage_d.dds": b"uhr-58gb-wrong"},
                "DLCUltraHighResolution - Textures16.ba2": {"textures/dlc06/vault_d.dds": b"uhr-58gb-wrong-2"},
                "DLCworkshop01 - Main.ba2": {"meshes/dlc02/cage.nif": b"ws01-mesh"},
                "DLCworkshop01 - Textures.ba2": {"textures/dlc02/cage_d.dds": b"ws01-tex"},
                "DLCworkshop03 - Textures.ba2": {"textures/dlc06/vault_d.dds": b"ws03-tex"},
            }
            for name, entries in archives.items():
                (data / name).write_bytes(general_archive(entries))
            (data / "DLCUltraHighResolution.esm").write_bytes(b"TES4uhr")

            src = pipeline.Fo4Archives(str(data), [str(data)])
            self.assertEqual(src.mesh("meshes/base.nif"), b"base-mesh")
            self.assertEqual(src.mesh("meshes/dlc02/cage.nif"), b"ws01-mesh")
            self.assertEqual(src.texture("dlc02/cage_d.dds"), b"ws01-tex")
            self.assertEqual(src.texture("dlc06/vault_d.dds"), b"ws03-tex")
            self.assertEqual(len(src.textures), 3)  # base + ws01 + ws03 (0 UHR archives opened)

    def test_dlc_plugins_orders_and_restricts_archives_in_load_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data"
            data.mkdir()
            archives = {
                "Fallout4 - Meshes.ba2": {"meshes/base.nif": b"base"},
                "DLCCoast - Main.ba2": {"meshes/shared.nif": b"coast", "meshes/coast_only.nif": b"coast-only"},
                "DLCRobot - Main.ba2": {"meshes/shared.nif": b"robot", "meshes/robot_only.nif": b"robot-only"},
                "DLCNukaWorld - Main.ba2": {"meshes/nuka.nif": b"nuka"},
            }
            for name, entries in archives.items():
                (data / name).write_bytes(general_archive(entries))

            # Alphabetical default: DLCCoast sorts before DLCRobot
            default_src = pipeline.Fo4Archives(str(data), [str(data)])
            self.assertEqual(default_src.mesh("meshes/shared.nif"), b"coast")
            self.assertEqual(default_src.mesh("meshes/nuka.nif"), b"nuka")

            # Explicit load order DLCRobot,DLCCoast (Nuka omitted -> restricted out)
            ordered = pipeline.Fo4Archives(str(data), [str(data)], dlc_plugins="DLCRobot.esm,DLCCoast")
            self.assertEqual(ordered.mesh("meshes/shared.nif"), b"robot")
            self.assertEqual(ordered.mesh("meshes/coast_only.nif"), b"coast-only")
            self.assertIsNone(ordered.mesh("meshes/nuka.nif"))

            with self.assertRaisesRegex(ValueError, "DLCUltraHighResolution"):
                pipeline.parse_dlc_plugins("DLCRobot,DLCUltraHighResolution.esm")

    def test_checkpoint_signature_skips_uhr_and_voices_and_keeps_default_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fo4, clean_dlc, full_data = root / "fo4", root / "clean_dlc", root / "full_data"
            for d in (fo4, clean_dlc, full_data):
                d.mkdir()
            (fo4 / "Fallout4 - Meshes.ba2").write_bytes(b"base")
            for dep in ("texconv.exe", "res.zip", "tmpl.nif"):
                (root / dep).write_bytes(b"dep")

            dlc_stems = ("DLCRobot", "DLCworkshop01", "DLCCoast", "DLCworkshop02", "DLCworkshop03", "DLCNukaWorld")
            for stem in dlc_stems:
                for kind in ("Main", "Textures"):
                    payload = f"{stem}-{kind}".encode()
                    (clean_dlc / f"{stem} - {kind}.ba2").write_bytes(payload)
                    (full_data / f"{stem} - {kind}.ba2").write_bytes(payload)
            for stem in ("DLCRobot", "DLCCoast", "DLCworkshop03", "DLCNukaWorld"):
                (full_data / f"{stem} - Voices_en.ba2").write_bytes(b"voice")
            for i in range(1, 17):
                (full_data / f"DLCUltraHighResolution - Textures{i:02d}.ba2").write_bytes(b"uhr")

            def make_args(extra_dirs, dlc_plugins=""):
                return SimpleNamespace(
                    fo4_data=str(fo4), starfield_data="", texconv=str(root / "texconv.exe"),
                    content_resources=str(root / "res.zip"), collision_template=str(root / "tmpl.nif"),
                    static_items=False, extra_data=[str(d) for d in extra_dirs], dlc_plugins=dlc_plugins,
                )

            sig_full = convert_batch.checkpoint_signature(make_args([full_data]))
            self.assertNotIn("dlc_plugins", sig_full)
            self.assertEqual(len(sig_full["extra_archives"][0][1]), 12)  # 12 DLC Main/Textures, not 28 or 32

            # Default behavior on a clean 12-archive DLC folder: matches pinned cd03411a digest list, no dlc_plugins key
            sig_clean = convert_batch.checkpoint_signature(make_args([clean_dlc]))
            self.assertNotIn("dlc_plugins", sig_clean)
            clean_digests = [(Path(x[0]).name, x[1], x[2]) for x in sig_clean["extra_archives"][0][1]]
            full_digests = [(Path(x[0]).name, x[1], x[2]) for x in sig_full["extra_archives"][0][1]]
            self.assertEqual(_sha256_json(clean_digests), CD03411A_CHECKPOINT_EXTRA_ARCHIVES_SHA256)
            self.assertEqual(_sha256_json(full_digests), CD03411A_CHECKPOINT_EXTRA_ARCHIVES_SHA256)

            # Explicit --dlc-plugins records load-order stems and changes signature when order changes
            sig_ord_a = convert_batch.checkpoint_signature(make_args([full_data], "DLCRobot,DLCCoast"))
            sig_ord_b = convert_batch.checkpoint_signature(make_args([full_data], "DLCCoast,DLCRobot"))
            self.assertEqual(sig_ord_a["dlc_plugins"], ["dlcrobot", "dlccoast"])
            self.assertEqual(len(sig_ord_a["extra_archives"][0][1]), 4)
            self.assertNotEqual(_sha256_json(sig_ord_a), _sha256_json(sig_ord_b))

    def test_interior_batch_source_pins_skip_uhr_and_preserve_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data"
            data.mkdir()
            (data / "Fallout4.esm").write_bytes(b"TES4fo4")
            (data / "DLCRobot.esm").write_bytes(b"TES4robot")
            (data / "DLCCoast.esm").write_bytes(b"TES4coast")
            (data / "DLCUltraHighResolution.esm").write_bytes(b"TES4uhr")
            (data / "Fallout4 - Meshes.ba2").write_bytes(b"BTDXbase")
            (data / "DLCRobot - Main.ba2").write_bytes(b"BTDXrobot")
            (data / "DLCCoast - Main.ba2").write_bytes(b"BTDXcoast")
            (data / "DLCUltraHighResolution - Textures01.ba2").write_bytes(b"BTDXuhr")

            plan = {"batches": [{"cells": [
                {"editor_id": "Lair", "formkey": "0008A3:DLCRobot.esm",
                 "plugins": ["Fallout4.esm", "DLCRobot.esm", "DLCUltraHighResolution.esm"]}
            ]}]}
            a_default = argparse.Namespace(fo4_data=str(data), dlc_data=[str(data)], census_data=None, dlc_plugins="")
            pins = ib.source_pins(a_default, plan, 1)
            self.assertEqual(sorted(pins["plugins"]), ["DLCRobot.esm", "Fallout4.esm"])
            self.assertEqual(sorted(pins["archives"]),
                             ["DLCCoast - Main.ba2", "DLCRobot - Main.ba2", "Fallout4 - Meshes.ba2"])

            a_restricted = argparse.Namespace(fo4_data=str(data), dlc_data=[str(data)], census_data=None,
                                              dlc_plugins="DLCRobot")
            pins_r = ib.source_pins(a_restricted, plan, 1)
            self.assertEqual(sorted(pins_r["archives"]), ["DLCRobot - Main.ba2", "Fallout4 - Meshes.ba2"])

    def test_output_refusal_guard_blocks_git_worktree_and_game_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wt = root / "fake_worktree"
            (wt / ".git").mkdir(parents=True)
            game = root / "Starfield"
            (game / "Data").mkdir(parents=True)
            (game / "Starfield.exe").write_bytes(b"MZ")
            safe = root / "safe_staging" / "out"

            pipeline.refuse_unsafe_output_dir(str(safe), "--out")
            with self.assertRaisesRegex(ValueError, "Git worktree"):
                pipeline.refuse_unsafe_output_dir(str(wt / "sub" / "out"), "--out")
            with self.assertRaisesRegex(ValueError, "game folder"):
                pipeline.refuse_unsafe_output_dir(str(game / "Data" / "out"), "--out")


class D2PrefixEditorIdsAndManifestRewriterTests(unittest.TestCase):
    def test_default_prefix_matches_cd03411a(self):
        sources = [
            "meshes\\SetDressing\\Chair01.nif",
            "meshes\\Architecture\\Chair01.nif",
            "Meshes\\DLC03\\Architecture\\DLC03_ParkStoneBlockA.nif",
            "meshes\\Props\\Box-A.01.nif",
        ]
        current_default_ids, explicit_default_ids = {}, {}
        for s in sources:
            convert_batch.editor_id(s, current_default_ids)
            convert_batch.editor_id(s, explicit_default_ids, prefix="fo4port")

        default_bytes = json.dumps(current_default_ids, indent=1).encode("utf-8")
        explicit_bytes = json.dumps(explicit_default_ids, indent=1).encode("utf-8")
        self.assertEqual(hashlib.sha256(default_bytes).hexdigest(), CD03411A_CONVERT_BATCH_EDITORIDS_SHA256)
        self.assertEqual(hashlib.sha256(explicit_bytes).hexdigest(), CD03411A_CONVERT_BATCH_EDITORIDS_SHA256)

    def test_non_default_prefix_generates_prefixed_editor_ids(self):
        ids_dlc, ids_ui = {}, {}
        self.assertEqual(
            convert_batch.editor_id("Meshes\\DLC03\\DLC03_ParkStoneBlockA.nif", ids_dlc, prefix="fo4dlc"),
            "FO4DLC_dlc03_parkstoneblocka",
        )
        self.assertEqual(
            convert_batch.editor_id("Meshes\\DLC03\\Sub\\DLC03_ParkStoneBlockA.nif", ids_dlc, prefix="fo4dlc"),
            "FO4DLC_dlc03_parkstoneblocka_"
            + hashlib.sha256(b"meshes/dlc03/sub/dlc03_parkstoneblocka.nif").hexdigest()[:16],
        )
        self.assertEqual(
            convert_batch.editor_id("Meshes\\AnimObjects\\Pipboy.nif", ids_ui, prefix="fo4ui"),
            "FO4UI_pipboy",
        )

    def test_rewrite_manifest_prefix_rewrites_and_merges_without_reconverting_and_keeps_default_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_dir = root / "src_stage"
            src_dir.mkdir()
            editorids = {
                "meshes/dlc03/blocka.nif": "FO4Port_blocka",
                "meshes/setdressing/chair01.nif": "FO4Port_chair01",
                "meshes/doors/loaddoor01.nif": "FO4Port_loaddoor01",
            }
            man_models = {
                "items": [
                    {"editor_id": "FO4Port_blocka", "model": "fo4dlc\\dlc03\\blocka.nif",
                     "source": "Meshes\\DLC03\\BlockA.nif", "shapes": 2, "fallback_materials": 0, "form_index": 0,
                     "collision_report": {"source": "fo4-native"}},
                    {"editor_id": "FO4Port_loaddoor01", "model": "fo4dlc\\doors\\loaddoor01.nif",
                     "source": "Meshes\\Doors\\LoadDoor01.nif", "shapes": 1, "fallback_materials": 0, "form_index": 1,
                     "collision_report": {"source": "fo4-native"}},
                ],
                "failures": [{"nif": "meshes\\dlc01\\fx.nif", "reason": "ValueError: effect-only"}],
                "material_fallbacks": {},
                "materials_converted": ["materials\\dlc03\\a.bgsm"],
                "stats": {"assets": 2, "failed": 1, "materials_ok": 1, "materials_fallback": 0},
                "seconds": 1.2,
            }
            man_cells = {
                "items": [
                    {"editor_id": "FO4Port_chair01", "model": "fo4dlc\\setdressing\\chair01.nif",
                     "source": "meshes\\SetDressing\\Chair01.nif", "shapes": 1, "fallback_materials": 0, "form_index": 0,
                     "collision_report": {"source": "fo4-native"}},
                    {"editor_id": "FO4Port_loaddoor01", "model": "fo4dlc\\doors\\loaddoor01.nif",
                     "source": "meshes\\Doors\\LoadDoor01.nif", "shapes": 1, "fallback_materials": 0, "form_index": 1,
                     "collision_report": {"source": "fo4-native"},
                     "load_door": {"bounds": [[-1, -1, 0], [1, 1, 2]]}},
                    {"editor_id": "FO4Port_chair01_pose_abc", "model": "fo4dlc\\setdressing\\chair01_pose_abc.nif",
                     "source": "meshes\\SetDressing\\Chair01.nif", "shapes": 1, "fallback_materials": 0, "form_index": 2,
                     "collision_report": {"source": "fo4-native"},
                     "pose": {"kind": "xrgd", "key": "abc", "refs": ["000001:DLCCoast.esm"]}},
                ],
                "failures": [],
                "material_fallbacks": {},
                "materials_converted": ["materials\\b.bgsm"],
                "stats": {"assets": 3, "failed": 0, "materials_ok": 1, "materials_fallback": 0},
                "seconds": 2.3,
            }
            for fn, obj in (("editorids.json", editorids), ("manifest-models.json", man_models),
                            ("manifest-cells.json", man_cells)):
                convert_batch.write_json_atomic(str(src_dir / fn), obj)
            orig_hashes = {fn: hashlib.sha256((src_dir / fn).read_bytes()).hexdigest()
                           for fn in ("editorids.json", "manifest-models.json", "manifest-cells.json")}

            # Rewriting with default prefix fo4port produces byte-for-byte identical files (Rule R3)
            out_default = root / "out_default"
            rc = convert_batch.main([
                "rewrite-manifest-prefix",
                "--manifest", str(src_dir / "manifest-models.json"),
                "--manifest", str(src_dir / "manifest-cells.json"),
                "--editorids", str(src_dir / "editorids.json"),
                "--prefix", "fo4port",
                "--out-dir", str(out_default),
            ])
            self.assertEqual(rc, 0)
            for fn, h in orig_hashes.items():
                self.assertEqual(hashlib.sha256((out_default / fn).read_bytes()).hexdigest(), h)

            # Rewriting with fo4dlc rewrites all EditorIDs (including posed) and merges load_door metadata cleanly
            out_dlc = root / "out_dlc"
            rc2 = convert_batch.main([
                "rewrite-manifest-prefix",
                "--manifest", str(src_dir / "manifest-models.json"),
                "--manifest", str(src_dir / "manifest-cells.json"),
                "--editorids", str(src_dir / "editorids.json"),
                "--prefix", "fo4dlc",
                "--out-dir", str(out_dlc),
                "--merge-out", "manifest.json",
            ])
            self.assertEqual(rc2, 0)
            # Original source files untouched
            for fn, h in orig_hashes.items():
                self.assertEqual(hashlib.sha256((src_dir / fn).read_bytes()).hexdigest(), h)

            rewritten_ids = json.loads((out_dlc / "editorids.json").read_text(encoding="utf-8"))
            self.assertEqual(rewritten_ids["meshes/dlc03/blocka.nif"], "FO4DLC_blocka")
            merged = json.loads((out_dlc / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([it["editor_id"] for it in merged["items"]],
                             ["FO4DLC_blocka", "FO4DLC_loaddoor01", "FO4DLC_chair01", "FO4DLC_chair01_pose_abc"])
            self.assertEqual([it["form_index"] for it in merged["items"]], [0, 1, 2, 3])
            self.assertIn("load_door", merged["items"][1])

            # Refuses overwriting input folder in place or writing into a Git worktree
            with self.assertRaises(SystemExit):
                convert_batch.main([
                    "rewrite-manifest-prefix", "--manifest", str(src_dir / "manifest-models.json"),
                    "--prefix", "fo4dlc", "--out-dir", str(src_dir),
                ])
            wt = root / "git_wt"
            (wt / ".git").mkdir(parents=True)
            with self.assertRaises(SystemExit):
                convert_batch.main([
                    "rewrite-manifest-prefix", "--manifest", str(src_dir / "manifest-models.json"),
                    "--prefix", "fo4dlc", "--out-dir", str(wt / "out"),
                ])


class D5ScolMissingMeshAndFallbackTests(unittest.TestCase):
    def test_missing_nif_reports_file_not_found_instead_of_none_startswith_attribute_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data"
            data.mkdir()
            (data / "Fallout4 - Meshes.ba2").write_bytes(general_archive({"meshes/other.nif": b"other"}))
            src = pipeline.Fo4Archives(str(data))
            conv = pipeline.Converter.__new__(pipeline.Converter)
            conv.src = src
            conv.stats = {"assets": 0, "failed": 0}
            res = conv.convert_nif("meshes\\SCOL\\DLCRobot.esm\\CM0000DBF3.NIF")
            self.assertFalse(res["ok"])
            self.assertIn("FileNotFoundError", res["reason"])
            self.assertNotIn("AttributeError", res["reason"])
            self.assertNotIn("startswith", res["reason"])

    def test_scol_fallbacks_resolve_developer_esp_folder_to_base_formkey_path(self):
        self.assertEqual(pipeline.scol_archive_path("008B79:DLCRobot.esm"), "meshes/scol/dlcrobot.esm/cm00008b79.nif")
        self.assertEqual(pipeline.scol_archive_path("DLCRobot.esm:0x008B79"), "meshes/scol/dlcrobot.esm/cm00008b79.nif")
        self.assertIsNone(pipeline.scol_archive_path("invalid"))

        cell = {
            "cell": "DLC01Lair01",
            "refs": [
                {
                    "type": "StaticCollection",
                    "base_formkey": "008B79:DLCRobot.esm",
                    "model": "SCOL\\DevMergeA.esp\\CM00083F.NIF",
                },
                {
                    # Direct canonical path matches itself -> no redundant fallback entry needed
                    "type": "StaticCollection",
                    "base_formkey": "009999:DLCRobot.esm",
                    "model": "SCOL\\DLCRobot.esm\\CM00009999.NIF",
                },
                {
                    # Ambiguous 1-to-many MODL -> never guessed
                    "type": "StaticCollection",
                    "base_formkey": "00AAAA:DLCRobot.esm",
                    "model": "SCOL\\DevMergeB.esp\\CM000111.NIF",
                },
                {
                    "type": "StaticCollection",
                    "base_formkey": "00BBBB:DLCRobot.esm",
                    "model": "SCOL\\DevMergeB.esp\\CM000111.NIF",
                },
            ],
        }
        fb = convert_batch.scol_fallbacks(cell)
        self.assertEqual(fb, {"meshes/scol/devmergea.esp/cm00083f.nif": "meshes/scol/dlcrobot.esm/cm00008b79.nif"})

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data"
            data.mkdir()
            (data / "Fallout4 - Meshes.ba2").write_bytes(general_archive({"meshes/direct.nif": b"direct-bytes"}))
            (data / "DLCRobot - Main.ba2").write_bytes(
                general_archive({
                    "meshes/scol/dlcrobot.esm/cm00008b79.nif": b"scol-combined-nif-bytes",
                    "meshes/direct.nif": b"dlc-override-unused",
                })
            )
            src = pipeline.Fo4Archives(str(data), [str(data)])
            src.register_mesh_fallbacks(fb | {"meshes/direct.nif": "meshes/scol/dlcrobot.esm/cm00008b79.nif"})
            # Direct archive hit MUST still win 100% unchanged (R3)
            self.assertEqual(src.mesh("Meshes\\direct.nif"), b"direct-bytes")
            # Missing developer-ESP SCOL resolves cleanly to its base FormKey path in DLCRobot - Main.ba2
            self.assertEqual(src.mesh("meshes\\SCOL\\DevMergeA.esp\\CM00083F.NIF"), b"scol-combined-nif-bytes")

    def test_interior_batch_default_prefix_converts_automatron_scol_and_retries_uncheckpointed_failure(self):
        """D6: interior_batch default-prefix (`fo4port` -> `FO4Port_cm*` / `fo4port\\scol\\...`) converts Automatron SCOL
        meshes from merged cell exports when `--dlc-data` and `--dlc-plugins DLCRobot.esm` are passed, both in a fresh
        `--work` folder and when resuming over an earlier failed run (failures are never frozen in `.checkpoints`)."""
        dll = ensure_pluginspike_dll(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fo4_data = root / "fo4_data"
            dlc_data = root / "dlc_data"
            sf_data = root / "sf_data"
            for d in (fo4_data, dlc_data, sf_data):
                d.mkdir()
            (fo4_data / "Fallout4 - Meshes.ba2").write_bytes(general_archive({"meshes/base_wall.nif": b"base-nif"}))
            (dlc_data / "DLCRobot - Main.ba2").write_bytes(
                general_archive({
                    "meshes/scol/dlcrobot.esm/cm000100da.nif": b"scol-lair-bytes",
                    "meshes/scol/dlcrobot.esm/cm00010555.nif": b"scol-array-bytes",
                })
            )
            # Extra unrelated DLC archive in the same folder: restricted out by --dlc-plugins DLCRobot.esm
            (dlc_data / "DLCCoast - Main.ba2").write_bytes(general_archive({"meshes/dlc03/unused.nif": b"unused"}))
            tool_dep = root / "tool.bin"
            tool_dep.write_bytes(b"synthetic-tool")

            cell_lair = root / "DLC01Lair01.json"
            cell_array = root / "DLC01FortHagenSatelliteArray01.json"
            lair_doc = {
                "schema_version": 3,
                "cell": "DLC01Lair01",
                "location": {"formkey": "0008A4:DLCRobot.esm", "editor_id": "DLC01LairLocation", "name": "Lair"},
                "refs": [
                    {
                        "formkey": "008B01:DLCRobot.esm",
                        "base_formkey": "0100DA:DLCRobot.esm",
                        "type": "StaticCollection",
                        "base_editor_id": "DLC01LairScol01",
                        "model": "SCOL\\DevMergeA.esp\\CM00007E0C.NIF",
                        "pos": [0.0, 0.0, 0.0],
                        "rot": [0.0, 0.0, 0.0],
                        "scale": 1.0,
                        "disabled": 0,
                    }
                ],
            }
            array_doc = {
                "schema_version": 3,
                "cell": "DLC01FortHagenSatelliteArray01",
                "location": {"formkey": "05BA28:Fallout4.esm", "editor_id": "FortHagenArrayLocation", "name": "Array"},
                "refs": [
                    {
                        "formkey": "0044F0:DLCRobot.esm",
                        "base_formkey": "010555:DLCRobot.esm",
                        "type": "StaticCollection",
                        "base_editor_id": "DLC01ArrayScol01",
                        "model": "SCOL\\DevMergeB.esp\\CM0000E3E8.NIF",
                        "pos": [140.0, 0.0, 0.0],
                        "rot": [0.0, 0.0, 0.0],
                        "scale": 1.0,
                        "disabled": 0,
                    }
                ],
            }
            cell_lair.write_text(json.dumps(lair_doc), encoding="utf-8")
            cell_array.write_text(json.dumps(array_doc), encoding="utf-8")

            # Build merged.json identically to interior_batch.py step 3.
            merged = root / "merged.json"
            merged.write_text(
                json.dumps({"cell": "merged", "refs": lair_doc["refs"] + array_doc["refs"]}),
                encoding="utf-8",
            )

            def make_fake_converter(src_archives, staging_dir, *_args, **kwargs):
                prefix = kwargs.get("prefix", "fo4port")

                def fake_convert_nif(nif_name, **_kw):
                    raw = src_archives.mesh(nif_name)
                    if raw is None:
                        return {"nif": nif_name, "ok": False, "reason": f"FileNotFoundError: {nif_name}"}
                    rel = nif_name.replace("\\", "/")
                    if rel.lower().startswith("meshes/"):
                        rel = rel[7:]
                    out_name = f"{prefix}/{os.path.splitext(rel)[0].lower()}"
                    geom_rel = f"geometries/{out_name}.mesh"
                    mat_rel = f"materials/{prefix}/scol_test.mat"
                    tex_rel = f"textures/{prefix}/scol_test_color.dds"
                    st = Path(staging_dir)
                    for p_rel, payload in (
                        (geom_rel, b"synthetic-mesh:" + raw),
                        (mat_rel, json.dumps({"Objects": [], "texture": f"Data\\Textures\\{prefix}\\scol_test_color.dds"}).encode()),
                        (tex_rel, b"synthetic-dds"),
                    ):
                        dst = st / p_rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(payload)
                    shape = sfnif.StaticShape(
                        b"SCOL",
                        out_name.replace("/", "\\").encode("latin-1"),
                        3,
                        3,
                        mat_rel.replace("/", "\\"),
                        (0, 0, 0, 1),
                        (0, 0, 0, 1, 1, 1),
                    )
                    nif_dst = st / f"meshes/{out_name}.nif"
                    nif_dst.parent.mkdir(parents=True, exist_ok=True)
                    nif_dst.write_bytes(nif.serialize(sfnif.build_static_nif(b"SCOL", [shape])))
                    return {"nif": nif_name, "ok": True, "out_name": out_name, "shapes": 1, "fallback_materials": 0}

                return SimpleNamespace(convert_nif=fake_convert_nif, stats={}, material_errors={})

            work_resumed = root / "work_resumed"
            work_fresh = root / "work_fresh"
            base_args = [
                "--fo4-data", str(fo4_data),
                "--content-resources", str(tool_dep),
                "--texconv", str(tool_dep),
                "--collision-template", str(tool_dep),
                "--cell-json", str(merged),
                "--limit", "100000",
                "--resume",
            ]
            with patch.object(convert_batch.pipeline, "Converter", side_effect=make_fake_converter), \
                 patch.object(convert_batch.convert_static, "collision_template_from_nif", return_value=b"tmpl"), \
                 patch("builtins.print"):
                # 1. Without --extra-data (no DLCRobot - Main.ba2): both SCOLs fail, and .checkpoints freezes neither.
                convert_batch.main(base_args + ["--staging", str(work_resumed)])
                man_fail = json.loads((work_resumed / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(len(man_fail["items"]), 0)
                self.assertEqual(len(man_fail["failures"]), 2)

                # 2. Resumed with --extra-data + --dlc-plugins DLCRobot.esm AND in a fresh --work dir under default prefix:
                dlc_args = ["--extra-data", str(dlc_data), "--dlc-plugins", "DLCRobot.esm"]
                convert_batch.main(base_args + ["--staging", str(work_resumed)] + dlc_args)
                convert_batch.main(base_args + ["--staging", str(work_fresh)] + dlc_args)

            for wdir in (work_resumed, work_fresh):
                man_ok = json.loads((wdir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(man_ok["failures"], [])
                self.assertEqual(
                    [(it["editor_id"], it["model"]) for it in man_ok["items"]],
                    [
                        ("FO4Port_cm00007e0c", "fo4port\\scol\\devmergea.esp\\cm00007e0c.nif"),
                        ("FO4Port_cm0000e3e8", "fo4port\\scol\\devmergeb.esp\\cm0000e3e8.nif"),
                    ],
                )
                self.assertTrue((wdir / "meshes" / "fo4port" / "scol" / "devmergea.esp" / "cm00007e0c.nif").is_file())
                self.assertTrue((wdir / "meshes" / "fo4port" / "scol" / "devmergeb.esp" / "cm0000e3e8.nif").is_file())

            # 3. PluginSpike places both converted SCOL statics into FO4Port.esm under default prefix FO4Port.
            out_plugin = root / "out_plugin"
            subprocess.run(
                ["dotnet", dll, str(out_plugin), str(work_fresh / "manifest.json"), str(cell_lair), str(cell_array)],
                check=True,
                env=dict(os.environ, STARFIELD_DATA=str(sf_data)),
                capture_output=True,
            )
            fids = json.loads((out_plugin / "formids.json").read_text(encoding="utf-8"))
            self.assertIn("STAT:FO4Port_cm00007e0c", fids)
            self.assertIn("STAT:FO4Port_cm0000e3e8", fids)
            self.assertIn("REFR:FO4Port_DLC01Lair01:008B01:DLCRobot.esm", fids)
            self.assertIn("REFR:FO4Port_DLC01FortHagenSatelliteArray01:0044F0:DLCRobot.esm", fids)


class D4DlcInteriorsDriverTests(unittest.TestCase):
    @classmethod
    def _pluginspike_dll(cls) -> str:
        return ensure_pluginspike_dll(ROOT)

    def test_pluginspike_helper_skips_cleanly_without_dotnet_and_rebuilds_stale_dll(self):
        with patch("pluginspike_fixture.shutil.which", return_value=None):
            with self.assertRaises(unittest.SkipTest):
                ensure_pluginspike_dll(ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            proj = fake_root / "dotnet" / "PluginSpike"
            dll_dir = proj / "bin" / "Release" / "net9.0"
            dll_dir.mkdir(parents=True)
            csproj = proj / "PluginSpike.csproj"
            cs = proj / "Program.cs"
            dll = dll_dir / "PluginSpike.dll"
            dll.write_bytes(b"OLD_DLL")
            csproj.write_text("<Project/>", encoding="utf-8")
            cs.write_text("// newer source", encoding="utf-8")
            os.utime(dll, (1000.0, 1000.0))
            os.utime(cs, (2000.0, 2000.0))

            def fake_run(cmd, **_kwargs):
                dll.write_bytes(b"REBUILT_DLL")
                os.utime(dll, (3000.0, 3000.0))
                return SimpleNamespace(returncode=0)

            with patch("pluginspike_fixture.shutil.which", return_value="dotnet"), \
                 patch("pluginspike_fixture.subprocess.run", side_effect=fake_run) as run_mock:
                resolved = ensure_pluginspike_dll(fake_root)
                self.assertEqual(resolved, str(dll))
                self.assertEqual(run_mock.call_count, 1)

    def test_select_dlc_cells_excludes_fo4port_owned_and_builds_self_contained_test_station_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf = root / "sf"
            (sf / "Data").mkdir(parents=True)
            exports = root / "exports"
            exports.mkdir()
            staging = root / "staging"
            (staging / "meshes" / "fo4dlc").mkdir(parents=True)
            (staging / "textures" / "fo4dlc").mkdir(parents=True)
            (staging / "meshes" / "fo4dlc" / "wall.nif").write_bytes(b"NIFDATA")
            (staging / "textures" / "fo4dlc" / "wall_d.dds").write_bytes(b"DDSDATA")

            owned_stage = root / "interiors_b10"
            owned_stage.mkdir()
            (owned_stage / "result.json").write_text(
                json.dumps(
                    {
                        "name": "interiors_b10",
                        "pins": {"base_exports": {"DmndValentines01": "abc"}},
                        "cells": {
                            "GeneralAtomicsFactory01": {},
                            "RailroadHQ01": {},
                            "DLC01FortHagenSatelliteArray01": {},
                            "DLC01Lair01": {},
                        },
                    }
                ),
                encoding="utf-8",
            )

            census_cells = [
                # 5 overlapping cells owned by FO4Port / interiors_b10
                {"editor_id": "DmndValentines01", "formkey": "001E47:Fallout4.esm", "plugins": ["Fallout4.esm", "DLCCoast.esm"], "reach": "worldspace", "test_name": False},
                {"editor_id": "GeneralAtomicsFactory01", "formkey": "04280D:Fallout4.esm", "plugins": ["Fallout4.esm", "DLCRobot.esm"], "reach": "worldspace", "test_name": False},
                {"editor_id": "RailroadHQ01", "formkey": "092B21:Fallout4.esm", "plugins": ["Fallout4.esm", "DLCCoast.esm"], "reach": "behind_interior", "test_name": False},
                {"editor_id": "DLC01FortHagenSatelliteArray01", "formkey": "0044DF:DLCRobot.esm", "plugins": ["DLCRobot.esm"], "reach": "worldspace", "test_name": False},
                {"editor_id": "DLC01Lair01", "formkey": "0008A3:DLCRobot.esm", "plugins": ["DLCRobot.esm"], "reach": "behind_interior", "test_name": False},
                # Filtered out: test_name and no_load_door
                {"editor_id": "DLC04TestCell", "formkey": "009999:DLCNukaWorld.esm", "plugins": ["DLCNukaWorld.esm"], "reach": "worldspace", "test_name": True},
                {"editor_id": "DLC03Unreachable", "formkey": "008888:DLCCoast.esm", "plugins": ["DLCCoast.esm"], "reach": "no_load_door", "test_name": False},
                # 3 net-new DLC cells across Coast, Workshop03, NukaWorld
                {"editor_id": "DLC03Acadia", "formkey": "004643:DLCCoast.esm", "plugins": ["DLCCoast.esm"], "reach": "worldspace", "test_name": False},
                {"editor_id": "DLC06VaultWorkshop", "formkey": "000801:DLCworkshop03.esm", "plugins": ["DLCworkshop03.esm"], "reach": "worldspace", "test_name": False},
                {"editor_id": "DLC04BradbertonsOffice01", "formkey": "005000:DLCNukaWorld.esm", "plugins": ["DLCNukaWorld.esm"], "reach": "behind_interior", "test_name": False},
            ]
            census_path = root / "census.json"
            census_path.write_text(json.dumps({"cells": census_cells}), encoding="utf-8")

            for edid, plug in (
                ("DLC03Acadia", "DLCCoast.esm"),
                ("DLC06VaultWorkshop", "DLCworkshop03.esm"),
                ("DLC04BradbertonsOffice01", "DLCNukaWorld.esm"),
            ):
                (exports / f"{edid}.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 3,
                            "cell": edid,
                            "formkey": f"001000:{plug}",
                            "location": {"formkey": f"002000:{plug}", "editor_id": f"{edid}Loc", "name": edid},
                            "refs": [
                                {
                                    "formkey": f"003001:{plug}",
                                    "base_formkey": f"003002:{plug}",
                                    "type": "Static",
                                    "base_editor_id": "DLCWall",
                                    "model": "DLC\\Wall.nif",
                                    "pos": [0.0, 0.0, 0.0],
                                    "rot": [0.0, 0.0, 0.0],
                                    "scale": 1.0,
                                    "disabled": 0,
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

            man_path = root / "manifest.json"
            man_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {"editor_id": "FO4DLC_Wall", "model": "fo4dlc\\wall.nif", "source": "DLC\\Wall.nif"}
                        ],
                        "failures": [],
                    }
                ),
                encoding="utf-8",
            )

            def fake_archive(_packer, out_ba2, _dirs, _fmt):
                Path(out_ba2).write_bytes(b"BTDX" + b"pack" * 8)

            out_stage = root / "fo4dlc-stage"
            res = interior_dlc.build_dlc_interiors(
                census_path=str(census_path),
                exports_dir=str(exports),
                manifest_paths=[str(man_path)],
                out_dir=str(out_stage),
                pluginspike_dll=self._pluginspike_dll(),
                starfield_dir=str(sf),
                owned_stages=[str(owned_stage)],
                staging_dir=str(staging),
                no_promote=True,
                build_archive_fn=fake_archive,
            )

            self.assertEqual(res["classification"], "TEST-STATION")
            self.assertEqual(res["architecture"], "self-contained")
            self.assertEqual(res["masters"], ["Starfield.esm"])
            self.assertEqual(res["dlc_reachable_total"], 8)
            self.assertEqual(res["excluded_count"], 5)
            self.assertEqual(res["selected_count"], 3)
            self.assertEqual(
                sorted(e["editor_id"] for e in res["excluded_cells"]),
                [
                    "DLC01FortHagenSatelliteArray01",
                    "DLC01Lair01",
                    "DmndValentines01",
                    "GeneralAtomicsFactory01",
                    "RailroadHQ01",
                ],
            )
            fids = json.loads((out_stage / "port" / "formids.json").read_text(encoding="utf-8"))
            self.assertIn("CELL:FO4DLC_DLC03Acadia", fids)
            self.assertIn("CELL:FO4DLC_DLC04BradbertonsOffice01", fids)
            self.assertIn("CELL:FO4DLC_DLC06VaultWorkshop", fids)
            self.assertNotIn("CELL:FO4DLC_DLC01Lair01", fids)
            self.assertNotIn("CELL:FO4DLC_DmndValentines01", fids)
            self.assertIn("[TEST-STATION]", (out_stage / "README.txt").read_text(encoding="utf-8"))

            # Refuses Git worktree output dir (R4)
            git_wt = root / "git_wt"
            (git_wt / ".git").mkdir(parents=True)
            with self.assertRaises(ValueError):
                interior_dlc.build_dlc_interiors(
                    census_path=str(census_path),
                    exports_dir=str(exports),
                    manifest_paths=[str(man_path)],
                    out_dir=str(git_wt / "out"),
                    pluginspike_dll=self._pluginspike_dll(),
                    starfield_dir=str(sf),
                    no_pack=True,
                    no_promote=True,
                )


if __name__ == "__main__":
    unittest.main()
