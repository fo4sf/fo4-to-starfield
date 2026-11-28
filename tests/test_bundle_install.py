"""Synthetic folder tests for `fo4sf.bundle_installer` and `scripts/game/bundle_install.py`."""
from __future__ import annotations

import io
import json
import os
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "scripts", ROOT / "scripts" / "game", ROOT / "tests"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import ba2_fixture  # noqa: E402
import exp_install as exp  # noqa: E402
from fo4sf import bundle_installer as bi_mod  # noqa: E402
from fo4sf.bundle_installer import (  # noqa: E402
    BundleInstallRefused,
    install_bundle,
    rollback_bundle,
    run_postcheck,
    sha256_bytes,
    sha256_file,
)


def _subrecord(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<H", len(payload)) + payload


def _record(rec_type: bytes, form_id: int, subrecords: bytes, flags: int = 0) -> bytes:
    # Starfield/TES4 24-byte record header: type(4), size(4), flags(4), formid(4), vc1(4), vc2(2), ver(2)
    return rec_type + struct.pack("<IIIHH", len(subrecords), flags, form_id, 0, 0) + b"\x00\x00\x00\x00" + subrecords


def _wstr_cp1252(text: str) -> bytes:
    raw = text.encode("cp1252")
    return struct.pack("<H", len(raw)) + raw


def _build_qust_vmad_int_prop(script_name: str, prop_name: str, val: int) -> bytes:
    prop_bytes = _wstr_cp1252(prop_name) + struct.pack("<BBi", 3, 1, int(val))
    return (
        struct.pack("<hHH", 6, 2, 1)
        + _wstr_cp1252(script_name)
        + struct.pack("<BH", 0, 1)
        + prop_bytes
        + struct.pack("<BHHH", 3, 0, 0, 0)
    )


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
        (self.sf / "Tools" / "Archive2").mkdir(parents=True, exist_ok=True)
        (self.sf / "Tools" / "Archive2" / "Archive2.exe").write_bytes(b"ARCHIVE2-STUB")
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

    @staticmethod
    def _fake_archive2_run(command, **kwargs):
        cwd = Path(kwargs["cwd"])
        output = next(arg[len("-create="):] for arg in command if arg.startswith("-create="))
        Path(output).write_bytes(ba2_fixture.archive_from_tree(cwd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

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
            _make_esm(
                ("Starfield.esm",),
                quest_stages=(10, 20),
                vmad_prop=_build_qust_vmad_int_prop("FO4TerrainQuestScript", "LegacyProp", 1),
            )
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

    def _make_new_candidate_bundle(self, *, break_vmad: bool = True) -> Path:
        """Build a new bundle where `plugins[0]` is `FO4ActorRaider.esm` -> produces `FO4ActorRaider - Main.ba2`."""
        new_bundle = self.base / ("bundle-new" if break_vmad else "bundle-new-slot-only")
        (new_bundle / "Data" / "meshes").mkdir(parents=True, exist_ok=True)
        (new_bundle / "FO4ActorRaider.esm").write_bytes(_make_esm(("Starfield.esm",)))
        prop_name = "ReplacementProp" if break_vmad else "LegacyProp"
        (new_bundle / "FO4TerrainCore.esm").write_bytes(
            _make_esm(
                ("Starfield.esm",),
                quest_stages=(10, 20, 30),
                vmad_prop=_build_qust_vmad_int_prop("FO4TerrainQuestScript", prop_name, 2),
            )
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

    def test_dry_run_makes_zero_disk_changes_and_delegates_to_save_safety(self) -> None:
        self._seed_prior_terrain_core_install()
        new_bundle = self._make_new_candidate_bundle(break_vmad=True)
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
        self.assertIn("WARNING: swapping builds will invalidate existing saves (changed_script_property=1)", out)
        self.assertFalse(work_dir.exists())
        self.assertEqual(self.ptxt.read_bytes(), before_ptxt_bytes)
        self.assertTrue((self.sf / "Data" / "FO4TerrainCore - Main.ba2").is_file())
        self.assertFalse((self.sf / "Data" / "FO4ActorRaider - Main.ba2").exists())

        # Slot-shift-only swap delegates to save_safety and emits NOTE (... unverified, waits for a game test), NOT WARNING!
        slot_only_bundle = self._make_new_candidate_bundle(break_vmad=False)
        note_buf = io.StringIO()
        with redirect_stdout(note_buf):
            note_plan = install_bundle(
                bundle_dir=str(slot_only_bundle),
                starfield_dir=str(self.sf),
                work_dir=str(self.base / "swap-dry-note"),
                plugins_txt_path=str(self.ptxt),
                my_games_dir=str(self.my_games),
                launcher_settings_path=str(self.lsettings),
                min_free_gb=0.0,
                dry_run=True,
                pids_fn=lambda _img: [],
                repo_root=str(ROOT),
            )
        note_out = note_buf.getvalue()
        self.assertNotIn("WARNING:", note_out)
        self.assertIn("NOTE: plugin load-order indices shifted (reordered_plugin=2; unverified, waits for a game test).", note_out)
        self.assertIn("unverified, waits for a game test", note_plan["save_warning"])

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
        self.assertIn("WARNING: swapping builds will invalidate existing saves", install_out)
        self.assertIn("POST-CHECK OK:", install_out)
        self.assertEqual(receipt["status"], "complete")

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
        self.assertEqual(rb["recovered_from_status"], "complete")
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

    def test_failed_install_after_uninstall_recovers_byte_identical_from_pending_receipt(self) -> None:
        self._seed_prior_terrain_core_install()
        new_bundle = self._make_new_candidate_bundle()
        work_dir = self.base / "swap-failed-midway"

        ptxt_before = self.ptxt.read_bytes()
        ini_before = (self.my_games / "StarfieldCustom.ini").read_bytes()
        old_ba2_sha = sha256_file(str(self.sf / "Data" / "FO4TerrainCore - Main.ba2"))
        old_rec_bytes = (self.sf / "Data" / "FO4SFExp.install.json").read_bytes()
        old_toggle_bytes = (self.sf / "Data" / "FO4SF.toggle.json").read_bytes()

        real_runner = bi_mod._run_game_tool

        def fail_on_exp_install(script_path: str, args, plugins_txt_path: str, log_path=None):
            if os.path.basename(script_path) == "exp_install.py" and list(args)[:1] == ["install"]:
                return 2, "injected exp_install.py install failure after uninstall"
            return real_runner(script_path, args, plugins_txt_path, log_path)

        with patch.object(bi_mod, "_run_game_tool", side_effect=fail_on_exp_install):
            with self.assertRaisesRegex(BundleInstallRefused, "exp_install.py install failed"):
                install_bundle(
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

        # Old install was genuinely uninstalled before the injected failure
        self.assertFalse((self.sf / "Data" / "FO4TerrainCore - Main.ba2").exists())
        self.assertFalse((self.sf / "Data" / "FO4SFExp.install.json").exists())

        # Pending receipt was journaled BEFORE plugin_toggle / uninstall ran
        receipt_path = work_dir / "install_receipt.json"
        self.assertTrue(receipt_path.is_file())
        pending = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(pending["status"], "pending")
        self.assertIn("Plugins.txt", pending["backed_up_configs"])
        self.assertTrue(pending["ini_manifest"])
        self.assertIn("FO4SFExp.install.json", pending["meta_manifest"])
        self.assertIn("FO4TerrainCore - Main.ba2", pending["owner_files_before"])

        # Rollback recovers byte-identically from the pending receipt!
        rb = rollback_bundle(work_dir=str(work_dir), pids_fn=lambda _img: [], repo_root=str(ROOT))
        self.assertTrue(rb["ok"])
        self.assertEqual(rb["recovered_from_status"], "pending")
        self.assertEqual(self.ptxt.read_bytes(), ptxt_before)
        self.assertEqual((self.my_games / "StarfieldCustom.ini").read_bytes(), ini_before)
        self.assertEqual((self.sf / "Data" / "FO4SFExp.install.json").read_bytes(), old_rec_bytes)
        self.assertEqual((self.sf / "Data" / "FO4SF.toggle.json").read_bytes(), old_toggle_bytes)
        self.assertEqual(sha256_file(str(self.sf / "Data" / "FO4TerrainCore - Main.ba2")), old_ba2_sha)
        self.assertTrue((self.sf / "Data" / "FO4TerrainCore.esm").is_file())
        self.assertTrue((self.sf / "Data" / "FO4ActorRaider.esm").is_file())

    def test_split_archives_plugin_multi_ba2_install_and_rollback_leaves_zero_fo4sf_ba2(self) -> None:
        self.ptxt.write_text("# Starfield Plugins\n", encoding="utf-8")
        ptxt_before = self.ptxt.read_bytes()

        split_bundle = self.base / "bundle-split-plugin"
        (split_bundle / "Data" / "meshes" / "door").mkdir(parents=True, exist_ok=True)
        (split_bundle / "Data" / "Interface").mkdir(parents=True, exist_ok=True)
        (split_bundle / "Data" / "textures" / "terrain").mkdir(parents=True, exist_ok=True)

        plugins = ["FO4SFAlpha.esm", "FO4SFBravo.esm", "FO4SFCharlie.esm"]
        for p in plugins:
            (split_bundle / p).write_bytes(_make_esm(("Starfield.esm",)))

        nif_bytes = b"NIF-ALPHA-" * 40
        swf_bytes = b"SWF-CHARLIE-" * 35
        dds_bytes = b"DDS-SHARED-" * 45
        (split_bundle / "Data" / "meshes" / "door" / "cog.nif").write_bytes(nif_bytes)
        (split_bundle / "Data" / "Interface" / "FO4SF_Shell.swf").write_bytes(swf_bytes)
        (split_bundle / "Data" / "textures" / "terrain" / "ground.dds").write_bytes(dds_bytes)

        bplan = {
            "kind": "core-candidate-bundle",
            "version": 1,
            "plugins": plugins,
            "components": {
                "alpha_comp": {
                    "plugins": ["FO4SFAlpha.esm"],
                    "outputs": {
                        "FO4SFAlpha.esm": sha256_file(str(split_bundle / "FO4SFAlpha.esm")),
                        "Data/meshes/door/cog.nif": sha256_bytes(nif_bytes),
                    },
                },
                "charlie_comp": {
                    "plugins": ["FO4SFCharlie.esm"],
                    "outputs": {
                        "FO4SFCharlie.esm": sha256_file(str(split_bundle / "FO4SFCharlie.esm")),
                        "Data/Interface/FO4SF_Shell.swf": sha256_bytes(swf_bytes),
                    },
                },
            },
        }
        (split_bundle / "bundle_plan.json").write_text(json.dumps(bplan, indent=1), encoding="utf-8")

        real_runner = bi_mod._run_game_tool

        def inproc_exp_install_runner(script_path: str, args, plugins_txt_path: str, log_path=None):
            if os.path.basename(script_path) == "exp_install.py":
                out_buf = io.StringIO()
                err_buf = io.StringIO()
                rc = 0
                with patch.object(exp.subprocess, "run", side_effect=self._fake_archive2_run):
                    try:
                        with redirect_stdout(out_buf), patch("sys.stderr", err_buf):
                            exp.main(list(args))
                    except SystemExit as exc:
                        rc = exc.code if isinstance(exc.code, int) else 1
                        if isinstance(exc.code, str):
                            err_buf.write(exc.code + "\n")
                return rc, (out_buf.getvalue() + err_buf.getvalue()).strip()
            return real_runner(script_path, args, plugins_txt_path, log_path)

        work_dir = self.base / "swap-split"
        with patch.object(bi_mod, "_run_game_tool", side_effect=inproc_exp_install_runner):
            receipt = install_bundle(
                bundle_dir=str(split_bundle),
                starfield_dir=str(self.sf),
                work_dir=str(work_dir),
                plugins_txt_path=str(self.ptxt),
                my_games_dir=str(self.my_games),
                launcher_settings_path=str(self.lsettings),
                split_archives="plugin",
                min_free_gb=0.0,
                pids_fn=lambda _img: [],
                repo_root=str(ROOT),
            )
            self.assertEqual(receipt["status"], "complete")
            self.assertEqual(receipt["archives"], ["FO4SFAlpha - Main.ba2", "FO4SFCharlie - Main.ba2"])
            self.assertTrue((self.sf / "Data" / "FO4SFAlpha - Main.ba2").is_file())
            self.assertTrue((self.sf / "Data" / "FO4SFCharlie - Main.ba2").is_file())

            rb = rollback_bundle(work_dir=str(work_dir), pids_fn=lambda _img: [], repo_root=str(ROOT))
            self.assertTrue(rb["ok"])

        remaining_fo4sf_ba2 = sorted(p.name for p in (self.sf / "Data").glob("FO4SF*.ba2"))
        self.assertEqual(remaining_fo4sf_ba2, [])
        self.assertEqual(self.ptxt.read_bytes(), ptxt_before)

    def test_needed_bytes_counts_archive2_temp_and_copy_fallback_and_sidecar_refusal_prints_manual_instruction(self) -> None:
        self._seed_prior_terrain_core_install()
        new_bundle = self._make_new_candidate_bundle()

        # 1. Loose Data (--pack builds new archive) + require_hardlinks=False -> counts 1x archive2_temp AND owner_copy_fallback
        dry_loose = install_bundle(
            bundle_dir=str(new_bundle),
            starfield_dir=str(self.sf),
            work_dir=str(self.base / "space-loose"),
            plugins_txt_path=str(self.ptxt),
            with_sfse_sidecar=True,
            require_hardlinks=False,
            min_free_gb=0.0,
            dry_run=True,
            pids_fn=lambda _img: [],
            repo_root=str(ROOT),
        )
        bd = dry_loose["needed_bytes_breakdown"]
        self.assertGreater(bd["archive"], 0)
        self.assertEqual(bd["archive2_temp"], bd["archive"])
        self.assertGreater(bd["owner_copy_fallback"], 0)
        self.assertGreater(bd["sidecars"], 0)

        # 2. Cross-volume work_dir vs starfield_dir forces owner_copy_fallback even when require_hardlinks=True,
        #    and floor guard refuses when free_now - needed_bytes < floor_bytes!
        with patch.object(bi_mod, "_same_volume", return_value=False):
            dry_xvol = install_bundle(
                bundle_dir=str(new_bundle),
                starfield_dir=str(self.sf),
                work_dir=str(self.base / "space-xvol"),
                plugins_txt_path=str(self.ptxt),
                prepacked_ba2=str(self.new_prepacked),
                require_hardlinks=True,
                min_free_gb=0.0,
                dry_run=True,
                pids_fn=lambda _img: [],
                repo_root=str(ROOT),
            )
            self.assertEqual(dry_xvol["needed_bytes_breakdown"]["archive2_temp"], 0)
            self.assertGreater(dry_xvol["needed_bytes_breakdown"]["owner_copy_fallback"], 0)

            with self.assertRaisesRegex(BundleInstallRefused, "Target drive would drop to"):
                install_bundle(
                    bundle_dir=str(new_bundle),
                    starfield_dir=str(self.sf),
                    work_dir=str(self.base / "space-refuse"),
                    plugins_txt_path=str(self.ptxt),
                    with_sfse_sidecar=True,
                    min_free_gb=1.0,
                    dry_run=True,
                    free_bytes_fn=lambda _p: (1024 ** 3) + dry_loose["needed_bytes"] - 1,
                    pids_fn=lambda _img: [],
                    repo_root=str(ROOT),
                )

        # 3. Existing SFSE sidecar DLL in Data/SFSE/Plugins/ refuses overwrite AND prints one-line manual instruction naming it
        existing_dll = self.sf / "Data" / "SFSE" / "Plugins" / "FO4SFCombat.dll"
        existing_dll.write_bytes(b"PRIOR-DLL")
        refuse_buf = io.StringIO()
        with redirect_stdout(refuse_buf):
            with self.assertRaisesRegex(BundleInstallRefused, "FO4SFCombat.dll") as ctx:
                install_bundle(
                    bundle_dir=str(new_bundle),
                    starfield_dir=str(self.sf),
                    work_dir=str(self.base / "sidecar-refuse"),
                    plugins_txt_path=str(self.ptxt),
                    with_sfse_sidecar=True,
                    min_free_gb=0.0,
                    dry_run=True,
                    pids_fn=lambda _img: [],
                    repo_root=str(ROOT),
                )
        printed = refuse_buf.getvalue().strip()
        self.assertEqual(len(printed.splitlines()), 1)
        self.assertIn("MANUAL-SIDECAR:", printed)
        self.assertIn("Data/SFSE/Plugins/FO4SFCombat.dll", printed)
        self.assertIn("Data/SFSE/Plugins/FO4SFCombat.dll", str(ctx.exception))
        self.assertEqual(existing_dll.read_bytes(), b"PRIOR-DLL")


if __name__ == "__main__":
    unittest.main()
