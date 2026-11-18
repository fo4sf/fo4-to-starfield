"""Unit tests for DLC tools (D1..D5): UHR exclusion, --dlc-plugins load order, prefix EditorIDs & manifest rewriter,
SCOL path/None guards, and the FO4DLC interiors driver. Pure synthetic fixtures — zero local game paths."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
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
from fo4sf import pipeline  # noqa: E402
import interior_batch as ib  # noqa: E402

_cb_spec = importlib.util.spec_from_file_location("convert_batch_dlc", ROOT / "scripts" / "convert_batch.py")
convert_batch = importlib.util.module_from_spec(_cb_spec)
_cb_spec.loader.exec_module(convert_batch)


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

            # Default behavior on a clean 12-archive DLC folder: identical archive digest list, no dlc_plugins key
            sig_clean = convert_batch.checkpoint_signature(make_args([clean_dlc]))
            self.assertNotIn("dlc_plugins", sig_clean)
            clean_digests = [(Path(x[0]).name, x[1], x[2]) for x in sig_clean["extra_archives"][0][1]]
            full_digests = [(Path(x[0]).name, x[1], x[2]) for x in sig_full["extra_archives"][0][1]]
            self.assertEqual(_sha256_json(clean_digests), _sha256_json(full_digests))

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
    @staticmethod
    def _legacy_editor_id(source, ids):
        """Exact pre-D2 editor_id implementation for SHA-256 byte-identity proof (Rule R3)."""
        import re
        key = source.replace("\\", "/").lower()
        if key not in ids:
            basename = key.rsplit("/", 1)[-1]
            stem = re.sub(r"[^A-Za-z0-9_]", "_", os.path.splitext(basename)[0])
            name = "FO4Port_" + stem
            reserved = {v.lower() for v in ids.values()}
            if name.lower() in reserved:
                name += "_" + hashlib.sha256(key.encode()).hexdigest()[:16]
            ids[key] = name
        return ids[key]

    def test_default_prefix_is_sha256_byte_identical_to_pre_d2(self):
        sources = [
            "meshes\\SetDressing\\Chair01.nif",
            "meshes\\Architecture\\Chair01.nif",
            "Meshes\\DLC03\\Architecture\\DLC03_ParkStoneBlockA.nif",
            "meshes\\Props\\Box-A.01.nif",
        ]
        legacy_ids, current_default_ids, explicit_default_ids = {}, {}, {}
        for s in sources:
            self._legacy_editor_id(s, legacy_ids)
            convert_batch.editor_id(s, current_default_ids)
            convert_batch.editor_id(s, explicit_default_ids, prefix="fo4port")

        legacy_bytes = json.dumps(legacy_ids, indent=1).encode("utf-8")
        default_bytes = json.dumps(current_default_ids, indent=1).encode("utf-8")
        explicit_bytes = json.dumps(explicit_default_ids, indent=1).encode("utf-8")
        self.assertEqual(hashlib.sha256(default_bytes).hexdigest(), hashlib.sha256(legacy_bytes).hexdigest())
        self.assertEqual(hashlib.sha256(explicit_bytes).hexdigest(), hashlib.sha256(legacy_bytes).hexdigest())

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


if __name__ == "__main__":
    unittest.main()
