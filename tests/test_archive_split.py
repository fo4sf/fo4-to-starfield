"""Synthetic unit tests for multi-archive BA2 splitting in fo4sf.archive_split and exp_install.py."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "tests"), str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "scripts" / "game")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ba2_fixture import archive_from_tree  # noqa: E402
import exp_install as exp  # noqa: E402
from fo4sf import archive_split  # noqa: E402
from verify_packed_experiment import verify_archive  # noqa: E402


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ArchiveSplitTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.staging = self.root / "bundle"
        self.game = self.root / "game"
        self.data = self.game / "Data"
        self.local = self.root / "local"
        self.data.mkdir(parents=True)
        (self.local / "Starfield").mkdir(parents=True)
        self.plugins_txt = self.local / "Starfield" / "Plugins.txt"
        self.orig_plugins_bytes = b"\xef\xbb\xbf*FO4Port.esm\r\n"
        self.plugins_txt.write_bytes(self.orig_plugins_bytes)

        tool = self.game / "Tools" / "Archive2" / "Archive2.exe"
        tool.parent.mkdir(parents=True)
        tool.write_bytes(b"synthetic Archive2 stub")

        env = patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)})
        env.start()
        self.addCleanup(env.stop)

    def _populate_synthetic_bundle(self):
        self.staging.mkdir(parents=True, exist_ok=True)
        plugins = ["Alpha.esm", "Bravo.esm", "Charlie.esm"]
        for p in plugins:
            (self.staging / p).write_bytes(f"TES4_SYNTH_{p}".encode("ascii"))

        files = {
            "meshes/door/cog.nif": b"M" * 400,
            "Scripts/FO4SF_Alpha.pex": b"S" * 300,
            "Interface/FO4SF_Shell.swf": b"I" * 250,
            "textures/set_a/t1.dds": b"A" * 500,
            "textures/set_b/t2.dds": b"B" * 500,
        }
        for rel, raw in files.items():
            fp = self.staging / "Data" / Path(*rel.split("/"))
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(raw)

        bundle_plan = {
            "plugins": plugins,
            "components": {
                "alpha_comp": {
                    "plugins": ["Alpha.esm"],
                    "outputs": {
                        "Alpha.esm": _sha256((self.staging / "Alpha.esm").read_bytes()),
                        "Data/Scripts/FO4SF_Alpha.pex": _sha256(files["Scripts/FO4SF_Alpha.pex"]),
                    },
                },
                "charlie_comp": {
                    "plugins": ["Charlie.esm"],
                    "outputs": {
                        "Charlie.esm": _sha256((self.staging / "Charlie.esm").read_bytes()),
                        "Data/Interface/FO4SF_Shell.swf": _sha256(files["Interface/FO4SF_Shell.swf"]),
                    },
                },
            },
        }
        (self.staging / "bundle_plan.json").write_text(json.dumps(bundle_plan, indent=1), encoding="utf-8")
        return plugins, files

    @staticmethod
    def _fake_archive2_run(command, **kwargs):
        cwd = Path(kwargs["cwd"])
        output = next(arg[len("-create="):] for arg in command if arg.startswith("-create="))
        Path(output).write_bytes(archive_from_tree(cwd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def test_plan_split_by_size_separates_non_textures_and_textures_then_spills(self):
        plugins, _ = self._populate_synthetic_bundle()
        resources = archive_split.scan_data_resources(str(self.staging))

        # Tight 1,400-byte archive cap: non-textures (~1,150 B BA2) fit in Alpha, textures (~1,150 B) fit in Bravo
        buckets_2 = archive_split.plan_split_by_size(resources, plugins, max_archive_bytes=1400)
        self.assertEqual([b.archive_name for b in buckets_2], ["Alpha - Main.ba2", "Bravo - Main.ba2"])
        self.assertTrue(all(r.top_folder != "textures" for r in buckets_2[0].resources))
        self.assertTrue(all(r.top_folder == "textures" for r in buckets_2[1].resources))
        self.assertTrue(all(b.estimated_ba2_bytes <= 1400 for b in buckets_2))

        # Even tighter 900-byte cap: textures split across Bravo + Charlie (3 archives total)
        buckets_3 = archive_split.plan_split_by_size(resources, ["Alpha.esm", "Bravo.esm", "Charlie.esm", "Delta.esm"], max_archive_bytes=900)
        self.assertGreaterEqual(len(buckets_3), 3)
        self.assertTrue(all(b.estimated_ba2_bytes <= 900 for b in buckets_3))

        # Insufficient carrier plugins must refuse cleanly
        with self.assertRaisesRegex(ValueError, "only 1 active plugins"):
            archive_split.plan_split_by_size(resources, ["Alpha.esm"], max_archive_bytes=1400)

    def test_plan_split_by_plugin_maps_component_outputs_and_base_core(self):
        plugins, _ = self._populate_synthetic_bundle()
        resources = archive_split.scan_data_resources(str(self.staging))
        bplan = json.loads((self.staging / "bundle_plan.json").read_text(encoding="utf-8"))

        buckets = archive_split.plan_split_by_plugin(resources, plugins, bundle_plan=bplan, max_archive_bytes=10000)
        by_arc = {b.archive_name: {r.rel_posix for r in b.resources} for b in buckets}
        self.assertIn("Scripts/FO4SF_Alpha.pex", by_arc["Alpha - Main.ba2"])
        self.assertIn("Interface/FO4SF_Shell.swf", by_arc["Charlie - Main.ba2"])
        # Base assets without component entries fall onto default base plugin (Alpha.esm when FO4TerrainCore absent)
        self.assertIn("meshes/door/cog.nif", by_arc["Alpha - Main.ba2"])

    def test_exp_install_split_by_size_installs_verifies_relaunch_and_rolls_back(self):
        plugins, _ = self._populate_synthetic_bundle()
        plugins_csv = ",".join(plugins)

        with patch.object(exp.subprocess, "run", side_effect=self._fake_archive2_run):
            exp.main([
                "install",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--plugins", plugins_csv,
                "--pack",
                "--split-archives", "size",
                "--max-archive-bytes", "1400",
            ])

        self.assertTrue((self.data / "Alpha - Main.ba2").is_file())
        self.assertTrue((self.data / "Bravo - Main.ba2").is_file())
        self.assertFalse((self.data / "Charlie - Main.ba2").exists())

        rec = json.loads((self.data / exp.RECORD).read_text(encoding="utf-8"))
        self.assertTrue(rec["complete"])
        self.assertEqual(rec["archives"], ["Alpha - Main.ba2", "Bravo - Main.ba2"])
        self.assertEqual(rec["split_mode"], "size")

        # Idempotent relaunch verifies EVERY split archive in Data/
        exp.main([
            "install",
            "--exp-dir", str(self.staging),
            "--starfield", str(self.game),
            "--plugins", plugins_csv,
            "--pack",
            "--split-archives", "size",
            "--max-archive-bytes", "1400",
        ])

        # Tampering with the second split archive refuses relaunch
        second_ba2 = self.data / "Bravo - Main.ba2"
        orig_second = second_ba2.read_bytes()
        second_ba2.write_bytes(orig_second + b"TAMPER")
        with self.assertRaisesRegex(SystemExit, "missing or changed: Bravo - Main.ba2"):
            exp.main([
                "install",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--plugins", plugins_csv,
                "--pack",
                "--split-archives", "size",
                "--max-archive-bytes", "1400",
            ])
        second_ba2.write_bytes(orig_second)

        # Uninstall removes all plugins and all split BA2 archives cleanly
        exp.main(["uninstall", "--starfield", str(self.game)])
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins_txt.read_bytes(), self.orig_plugins_bytes)

    def test_offline_split_build_and_prepacked_dir_install(self):
        plugins, _ = self._populate_synthetic_bundle()
        split_out = self.root / "prepacked-split"

        with patch("deploy_starfield.subprocess.run", side_effect=self._fake_archive2_run):
            rc = archive_split.main([
                "build",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--out", str(split_out),
                "--plugins", ",".join(plugins),
                "--split-by", "size",
                "--max-archive-bytes", "1400",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(archive_split.main(["verify", "--split-dir", str(split_out), "--exp-dir", str(self.staging)]), 0)

        # Install from --prepacked-dir must NOT invoke Archive2 again
        with patch.object(exp.subprocess, "run", side_effect=AssertionError("Archive2 must not run for --prepacked-dir")):
            exp.main([
                "install",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--plugins", ",".join(plugins),
                "--pack",
                "--prepacked-dir", str(split_out),
            ])
        self.assertTrue((self.data / "Alpha - Main.ba2").is_file())
        self.assertTrue((self.data / "Bravo - Main.ba2").is_file())
        exp.main(["uninstall", "--starfield", str(self.game)])
        self.assertEqual(list(self.data.iterdir()), [])

    def test_default_plugin_mode_and_held_off_carrier_refusal_in_every_mode(self):
        plugins, _ = self._populate_synthetic_bundle()
        resources = archive_split.scan_data_resources(str(self.staging))
        bplan = json.loads((self.staging / "bundle_plan.json").read_text(encoding="utf-8"))

        # 1. archive_split CLI --split-by defaults to 'plugin'; bare exp_install --split-archives defaults to 'plugin'
        split_out = self.root / "default-plugin-split"
        with patch("deploy_starfield.subprocess.run", side_effect=self._fake_archive2_run):
            rc = archive_split.main([
                "build",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--out", str(split_out),
                "--plugins", ",".join(plugins),
            ])
        self.assertEqual(rc, 0)
        manifest = json.loads((split_out / "archive_split_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["split_by"], "plugin")

        with patch.object(exp.subprocess, "run", side_effect=self._fake_archive2_run):
            exp.main([
                "install",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--plugins", ",".join(plugins),
                "--pack",
                "--split-archives",
            ])
        rec = json.loads((self.data / exp.RECORD).read_text(encoding="utf-8"))
        self.assertEqual(rec["split_mode"], "plugin")
        self.assertEqual(rec["archives"], ["Alpha - Main.ba2", "Charlie - Main.ba2"])

        # 2. Holding off a carrier plugin in Data/FO4SF.toggle.json refuses relaunch, order, active, AND both split planners
        toggle_path = self.data / exp.TOGGLE
        toggle_path.write_text(
            json.dumps({"off": ["Charlie.esm"], "plugins_txt": str(self.plugins_txt)}),
            encoding="utf-8",
        )
        # Untick Charlie.esm in Plugins.txt as plugin_toggle.py off does
        cur_lines = self.plugins_txt.read_text(encoding="utf-8-sig").splitlines()
        unticked = [ln.lstrip("*") if "charlie.esm" in ln.lower() else ln for ln in cur_lines]
        self.plugins_txt.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(unticked) + "\r\n").encode("utf-8"))

        with self.assertRaisesRegex(SystemExit, "split archive carrier.*Charlie.esm"):
            exp.main([
                "install",
                "--exp-dir", str(self.staging),
                "--starfield", str(self.game),
                "--plugins", ",".join(plugins),
                "--pack",
                "--split-archives",
            ])
        with self.assertRaises(SystemExit) as cm_ord:
            exp.main(["order", "--starfield", str(self.game)])
        self.assertEqual(cm_ord.exception.code, 6)
        with self.assertRaises(SystemExit) as cm_act:
            exp.main(["active", "--starfield", str(self.game)])
        self.assertEqual(cm_act.exception.code, 8)

        with self.assertRaisesRegex(ValueError, "carrier plugin.*Charlie.esm"):
            archive_split.plan_split_by_plugin(
                resources, plugins, bundle_plan=bplan, max_archive_bytes=10000, starfield_dir=str(self.game)
            )
        toggle_path.write_text(
            json.dumps({"off": ["Bravo.esm"], "plugins_txt": str(self.plugins_txt)}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "carrier plugin.*Bravo.esm"):
            archive_split.plan_split_by_size(
                resources, plugins, max_archive_bytes=1400, starfield_dir=str(self.game)
            )
        # Alternate toggle schema ("plugins_off") and unticked Plugins.txt lines are also refused in every mode
        toggle_path.write_text(json.dumps({"plugins_off": ["Alpha.esm"]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "carrier plugin.*Alpha.esm"):
            archive_split.plan_split_by_plugin(
                resources, plugins, bundle_plan=bplan, max_archive_bytes=10000, starfield_dir=str(self.game)
            )
        toggle_path.unlink()
        with self.assertRaisesRegex(ValueError, "carrier plugin.*Charlie.esm"):
            archive_split.plan_split_by_plugin(
                resources, plugins, bundle_plan=bplan, max_archive_bytes=10000, plugins_txt_path=str(self.plugins_txt)
            )


if __name__ == "__main__":
    unittest.main()
