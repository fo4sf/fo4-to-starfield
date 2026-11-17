"""Synthetic folder tests for `fo4sf.bundle_installer` and `scripts/game/bundle_install.py`."""
from __future__ import annotations

import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "scripts", ROOT / "scripts" / "game", ROOT / "tests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import ba2_fixture  # noqa: E402
from fo4sf.bundle_installer import (  # noqa: E402
    BundleInstallRefused,
    install_bundle,
    rollback_bundle,
    run_postcheck,
    sha256_file,
)


def _subrecord(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<H", len(payload)) + payload


def _record(rec_type: bytes, form_id: int, subrecords: bytes, flags: int = 0) -> bytes:
    # Starfield/TES4 24-byte record header: type(4), size(4), flags(4), formid(4), vc1(4), vc2(2), ver(2)
    return rec_type + struct.pack("<IIIHH", len(subrecords), flags, form_id, 0, 0) + b"\x00\x00\x00\x00" + subrecords


def _make_esm(
    masters: tuple[str, ...] = ("Starfield.esm",),
    quest_stages: tuple[int, ...] = (),
    vmad_prop: bytes = b"",
) -> bytes:
    tes4_subs = b"".join(_subrecord(b"MAST", m.encode("utf-8") + b"\x00") + _subrecord(b"DATA", b"\x00" * 8) for m in masters)
    tes4 = _record(b"TES4", 0, tes4_subs, flags=0x01)
    if not quest_stages and not vmad_prop:
        return tes4
    q_subs = b""
    if vmad_prop:
        q_subs += _subrecord(b"VMAD", vmad_prop)
    for stg in quest_stages:
        q_subs += _subrecord(b"INDX", struct.pack("<H", stg))
    q_rec = _record(b"QUST", 0x01000800, q_subs)
    grup = b"GRUP" + struct.pack("<I", 24 + len(q_rec)) + b"QUST" + struct.pack("<III", 0, 0, 0) + q_rec
    return tes4 + grup


class BundleInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self._tmp.name)
        self.local_app = self.base / "LocalAppData"
        self.ptxt = self.local_app / "Starfield" / "Plugins.txt"
        self.ptxt.parent.mkdir(parents=True, exist_ok=True)
        self.lsettings = self.local_app / "fo4sf" / "launcher_settings.json"
        self.lsettings.parent.mkdir(parents=True, exist_ok=True)
        self.lsettings.write_text('{"route": "sfse"}\n', encoding="utf-8")

        self.my_games = self.base / "MyGames" / "Starfield"
        (self.my_games / "Saves").mkdir(parents=True, exist_ok=True)
        (self.my_games / "StarfieldCustom.ini").write_text("[Archive]\nbInvalidateOlderFiles=1\n", encoding="utf-8")
        (self.my_games / "Saves" / "Save1_00000000.sfs").write_bytes(b"SAVE-DUMMY")

        self.sf = self.base / "Starfield"
        (self.sf / "Data" / "SFSE" / "Plugins").mkdir(parents=True, exist_ok=True)
        (self.sf / "Starfield.exe").write_bytes(b"MZ-STARFIELD")
        (self.sf / "Starfield.ini").write_text("[General]\nsLanguage=en\n", encoding="utf-8")
        (self.sf / "Data" / "Starfield.esm").write_bytes(_make_esm(masters=()))

        self._old_localapp = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = str(self.local_app)

    def tearDown(self) -> None:
        if self._old_localapp is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self._old_localapp
        self._tmp.cleanup()

    def _seed_prior_terrain_core_install(self) -> Path:
        """Seed a prior install whose primary archive is `FO4TerrainCore - Main.ba2` + held `FO4SFBridge.esm`."""
        self.ptxt.write_text("# Starfield Plugins\n*FO4SFBridge.esm\n", encoding="utf-8")
        (self.sf / "Data" / "FO4SFBridge.esm").write_bytes(_make_esm(("Starfield.esm",)))
        bridge_rec = {
            "plugin": "FO4SFBridge.esm",
            "files": {"FO4SFBridge.esm": sha256_file(str(self.sf / "Data" / "FO4SFBridge.esm"))},
            "plugins_txt": str(self.ptxt),
            "complete": True,
        }
        (self.sf / "Data" / "FO4SFBridge.install.json").write_text(json.dumps(bridge_rec), encoding="utf-8")

        old_bundle = self.base / "bundle-old"
        (old_bundle / "Data" / "meshes").mkdir(parents=True, exist_ok=True)
        (old_bundle / "FO4TerrainCore.esm").write_bytes(
            _make_esm(("Starfield.esm",), quest_stages=(10, 20), vmad_prop=b"PROP_V1")
        )
        (old_bundle / "FO4ActorRaider.esm").write_bytes(_make_esm(("Starfield.esm",)))
        (old_bundle / "Data" / "meshes" / "old.nif").write_bytes(b"OLD-NIF-BYTES")
        old_prepacked = self.base / "old-prepacked.ba2"
        old_prepacked.write_bytes(ba2_fixture.archive_from_tree(old_bundle / "Data"))

        seed_work = self.base / "seed-work"
        install_bundle(
            bundle_dir=str(old_bundle),
            starfield_dir=str(self.sf),
            work_dir=str(seed_work),
            plugins_txt_path=str(self.ptxt),
            my_games_dir=str(self.my_games),
            launcher_settings_path=str(self.lsettings),
            plugins_csv="FO4TerrainCore.esm,FO4ActorRaider.esm",
            prepacked_ba2=str(old_prepacked),
            min_free_gb=0.0,
            pids_fn=lambda _img: [],
            repo_root=str(ROOT),
        )
        self.assertTrue((self.sf / "Data" / "FO4TerrainCore - Main.ba2").is_file())

        # Hold FO4SFBridge.esm off via plugin_toggle.py just like the owner PC setup
        import subprocess
        rc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "game" / "plugin_toggle.py"),
                "off",
                "--plugins",
                "FO4SFBridge.esm",
                "--starfield",
                str(self.sf),
                "--why",
                "owner play hold",
            ],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        self.assertEqual(rc, 0)
        return old_bundle

    def _make_new_candidate_bundle(self) -> Path:
        """Build a new bundle where `plugins[0]` is `FO4ActorRaider.esm` -> produces `FO4ActorRaider - Main.ba2`."""
        new_bundle = self.base / "bundle-new"
        (new_bundle / "Data" / "meshes").mkdir(parents=True, exist_ok=True)
        (new_bundle / "FO4ActorRaider.esm").write_bytes(_make_esm(("Starfield.esm",)))
        (new_bundle / "FO4TerrainCore.esm").write_bytes(
            _make_esm(("Starfield.esm",), quest_stages=(10, 20, 30), vmad_prop=b"PROP_V2")
        )
        (new_bundle / "FO4SFCoreCandidate.esm").write_bytes(
            _make_esm(("Starfield.esm", "FO4ActorRaider.esm", "FO4TerrainCore.esm"))
        )
        (new_bundle / "Data" / "meshes" / "new.nif").write_bytes(b"NEW-CANDIDATE-NIF")
        self.new_prepacked = self.base / "new-prepacked.ba2"
        self.new_prepacked.write_bytes(ba2_fixture.archive_from_tree(new_bundle / "Data"))
        (new_bundle / "sfse_sidecar" / "SFSE" / "Plugins").mkdir(parents=True, exist_ok=True)
        (new_bundle / "sfse_sidecar" / "SFSE" / "Plugins" / "FO4SFCombat.dll").write_bytes(b"DLL-BYTES")
        (new_bundle / "bundle_plan.json").write_text(
            json.dumps(
                {
                    "kind": "core-candidate-bundle",
                    "version": 1,
                    "plugins": ["FO4ActorRaider.esm", "FO4TerrainCore.esm", "FO4SFCoreCandidate.esm"],
                }
            ),
            encoding="utf-8",
        )
        return new_bundle

    def test_refuses_when_game_or_launcher_is_open(self) -> None:
        new_bundle = self._make_new_candidate_bundle()
        self.ptxt.write_text("*FO4SFBridge.esm\n", encoding="utf-8")

        # 1. Game running
        with self.assertRaisesRegex(BundleInstallRefused, "Starfield.exe"):
            install_bundle(
                bundle_dir=str(new_bundle),
                starfield_dir=str(self.sf),
                work_dir=str(self.base / "w1"),
                plugins_txt_path=str(self.ptxt),
                min_free_gb=0.0,
                pids_fn=lambda img: [4242] if img == "Starfield.exe" else [],
                repo_root=str(ROOT),
            )

        # 2. Launcher lock present
        lock_file = self.lsettings.parent / "launcher.lock"
        lock_file.write_text("locked", encoding="utf-8")
        try:
            with self.assertRaisesRegex(BundleInstallRefused, "launcher lock"):
                install_bundle(
                    bundle_dir=str(new_bundle),
                    starfield_dir=str(self.sf),
                    work_dir=str(self.base / "w2"),
                    plugins_txt_path=str(self.ptxt),
                    launcher_settings_path=str(self.lsettings),
                    min_free_gb=0.0,
                    pids_fn=lambda _img: [],
                    repo_root=str(ROOT),
                )
        finally:
            lock_file.unlink()

    def test_dry_run_makes_zero_disk_changes_and_emits_save_warning(self) -> None:
        self._seed_prior_terrain_core_install()
        new_bundle = self._make_new_candidate_bundle()
        work_dir = self.base / "swap-dry"

        before_ptxt_bytes = self.ptxt.read_bytes()
        buf = io.StringIO()
        with redirect_stdout(buf):
            plan = install_bundle(
                bundle_dir=str(new_bundle),
                starfield_dir=str(self.sf),
                work_dir=str(work_dir),
                plugins_txt_path=str(self.ptxt),
                my_games_dir=str(self.my_games),
                launcher_settings_path=str(self.lsettings),
                with_sfse_sidecar=True,
                min_free_gb=0.0,
                dry_run=True,
                pids_fn=lambda _img: [],
                repo_root=str(ROOT),
            )
        out = buf.getvalue()
        self.assertEqual(plan["mode"], "dry-run")
        self.assertEqual(plan["expected_primary_archive"], "FO4ActorRaider - Main.ba2")
        self.assertIn("SAVE-WARNING:", out)
        self.assertIn("reordered active plugins", out)
        self.assertIn("FO4TerrainCore.esm", out)
        self.assertFalse(work_dir.exists())
        self.assertEqual(self.ptxt.read_bytes(), before_ptxt_bytes)
        self.assertTrue((self.sf / "Data" / "FO4TerrainCore - Main.ba2").is_file())
        self.assertFalse((self.sf / "Data" / "FO4ActorRaider - Main.ba2").exists())

    def test_swap_fixes_fo4terraincore_archive_postcheck_and_rolls_back_byte_identical(self) -> None:
        self._seed_prior_terrain_core_install()
        new_bundle = self._make_new_candidate_bundle()
        work_dir = self.base / "swap-live"

        # Capture exact pre-swap bytes for independent test assertion
        ptxt_before = self.ptxt.read_bytes()
        ini_before = (self.my_games / "StarfieldCustom.ini").read_bytes()
        old_ba2_sha = sha256_file(str(self.sf / "Data" / "FO4TerrainCore - Main.ba2"))
        old_rec_bytes = (self.sf / "Data" / "FO4SFExp.install.json").read_bytes()
        old_toggle_bytes = (self.sf / "Data" / "FO4SF.toggle.json").read_bytes()

        install_buf = io.StringIO()
        with redirect_stdout(install_buf):
            receipt = install_bundle(
                bundle_dir=str(new_bundle),
                starfield_dir=str(self.sf),
                work_dir=str(work_dir),
                plugins_txt_path=str(self.ptxt),
                my_games_dir=str(self.my_games),
                launcher_settings_path=str(self.lsettings),
                prepacked_ba2=str(self.new_prepacked),
                with_sfse_sidecar=True,
                require_hardlinks=True,
                min_free_gb=0.0,
                pids_fn=lambda _img: [],
                repo_root=str(ROOT),
            )

        install_out = install_buf.getvalue()
        self.assertIn("SAVE-WARNING:", install_out)
        self.assertIn("POST-CHECK OK:", install_out)

        # Post-check succeeded on `FO4ActorRaider - Main.ba2` (NOT hardcoded `FO4TerrainCore - Main.ba2`)!
        self.assertEqual(receipt["archives"], ["FO4ActorRaider - Main.ba2"])
        self.assertTrue((self.sf / "Data" / "FO4ActorRaider - Main.ba2").is_file())
        self.assertFalse((self.sf / "Data" / "FO4TerrainCore - Main.ba2").exists())
        self.assertTrue((self.sf / "Data" / "SFSE" / "Plugins" / "FO4SFCombat.dll").is_file())
        self.assertTrue((work_dir / "install_receipt.json").is_file())
        self.assertTrue((work_dir / "owner-files" / "FO4TerrainCore - Main.ba2").is_file())

        # Standalone postcheck also passes
        post = run_postcheck(str(self.sf), str(self.ptxt))
        self.assertTrue(post["ok"])
        self.assertEqual(post["archives"], ["FO4ActorRaider - Main.ba2"])

        # Dry-run rollback verifies backup without mutating Data
        dry_rb = rollback_bundle(work_dir=str(work_dir), dry_run=True, pids_fn=lambda _img: [], repo_root=str(ROOT))
        self.assertEqual(dry_rb["mode"], "dry-run")
        self.assertTrue((self.sf / "Data" / "FO4ActorRaider - Main.ba2").is_file())

        # Live rollback restores byte-identical files and prints every comparison
        rb_buf = io.StringIO()
        with redirect_stdout(rb_buf):
            rb = rollback_bundle(work_dir=str(work_dir), pids_fn=lambda _img: [], repo_root=str(ROOT))
        rb_out = rb_buf.getvalue()

        self.assertTrue(rb["ok"])
        self.assertIn("COMPARED Plugins.txt bytes: BYTE-IDENTICAL", rb_out)
        self.assertIn("COMPARED INI files", rb_out)
        self.assertIn("COMPARED owner Data files", rb_out)
        self.assertIn("FO4TerrainCore - Main.ba2", rb_out)
        self.assertIn("COMPARED hashes-before.txt vs hashes-rollback.txt", rb_out)

        self.assertEqual(self.ptxt.read_bytes(), ptxt_before)
        self.assertEqual((self.my_games / "StarfieldCustom.ini").read_bytes(), ini_before)
        self.assertEqual((self.sf / "Data" / "FO4SFExp.install.json").read_bytes(), old_rec_bytes)
        self.assertEqual((self.sf / "Data" / "FO4SF.toggle.json").read_bytes(), old_toggle_bytes)
        self.assertEqual(sha256_file(str(self.sf / "Data" / "FO4TerrainCore - Main.ba2")), old_ba2_sha)
        self.assertFalse((self.sf / "Data" / "FO4ActorRaider - Main.ba2").exists())
        self.assertFalse((self.sf / "Data" / "FO4SFCoreCandidate.esm").exists())
        self.assertFalse((self.sf / "Data" / "SFSE" / "Plugins" / "FO4SFCombat.dll").exists())


if __name__ == "__main__":
    unittest.main()
