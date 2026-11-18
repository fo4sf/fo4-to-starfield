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


if __name__ == "__main__":
    unittest.main()
