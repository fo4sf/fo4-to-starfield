"""Unit tests for `scripts/probes/probe_common.py` (Round 12 shared probe infrastructure)."""
from __future__ import annotations

import inspect
import os
import pathlib
import shutil
import struct
import sys
import tempfile
import unittest
import warnings
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
PROBES = SCRIPTS / "probes"
for _p in (str(SRC), str(SCRIPTS), str(PROBES)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_common as pc  # noqa: E402
from fo4sf.planet.esm import ESM, PERSISTENT, PluginWriter, Record, group_bytes, zbytes  # noqa: E402


def _make_dx10_dds(width: int = 8, height: int = 8, mips: int = 1, dxgi: int = 72, payload: bytes = b"\xAB" * 64) -> bytes:
    flags = 0x1 | 0x2 | 0x4 | 0x1000
    caps = 0x1000
    h = b"DDS " + struct.pack("<7I", 124, flags, height, width, 0, 0, mips) + b"\0" * 44
    h += struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    h += struct.pack("<5I", caps, 0, 0, 0, 0)
    h += struct.pack("<5I", dxgi, 3, 0, 1, 0)
    return h + payload


def _make_legacy_dxt5_dds(width: int = 4, height: int = 4, payload: bytes = b"\xCD" * 16) -> bytes:
    h = b"DDS " + struct.pack("<7I", 124, 0x1007, height, width, 16, 0, 1) + b"\0" * 44
    h += struct.pack("<II4sIIIII", 32, 0x4, b"DXT5", 0, 0, 0, 0, 0)
    h += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return h + payload


def _build_vmad_v6_obj_prop(script_name: str, prop_name: str, raw_formid: int, *, array: bool = False) -> bytes:
    sn = script_name.encode("cp1252")
    pn = prop_name.encode("cp1252")
    # ver=6, obj_fmt=2, script_count=1
    parts = [
        struct.pack("<HHH", 6, 2, 1),
        struct.pack("<H", len(sn)) + sn + b"\x01",
        struct.pack("<H", 1),  # prop_count
        struct.pack("<H", len(pn)) + pn,
    ]
    elem = struct.pack("<HhI", 0, -1, raw_formid)
    if array:
        parts.append(struct.pack("<BBI", 11, 1, 1) + elem)
    else:
        parts.append(struct.pack("<BB", 1, 1) + elem)
    return b"".join(parts)


class FakeSystem:
    def __init__(self, pids: list[int] | None = None, raise_err: bool = False) -> None:
        self._pids = pids or []
        self._raise_err = raise_err

    def pids(self, image: str = "Starfield.exe") -> list[int]:
        if self._raise_err:
            raise ValueError("tasklist simulated failure")
        return list(self._pids)


class ProbeCommonTests(unittest.TestCase):
    def test_no_bundle_install_reference(self) -> None:
        text = (PROBES / "probe_common.py").read_text(encoding="utf-8")
        self.assertNotIn("bundle_install", text)
        import ast
        tree = ast.parse(text)
        imported = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        for node in imported:
            if isinstance(node, ast.Import):
                self.assertFalse(any("bundle_install" in alias.name for alias in node.names))
            elif node.module:
                self.assertNotIn("bundle_install", node.module)

    def test_preflight_starfield_and_disk_space(self) -> None:
        self.assertEqual(pc.check_starfield_not_running(FakeSystem([])), [])
        with self.assertRaises(pc.ProbePreflightError):
            pc.check_starfield_not_running(FakeSystem([4242]))
        with self.assertRaises(pc.ProbePreflightError):
            pc.check_starfield_not_running(FakeSystem(raise_err=True))

        sig = inspect.signature(pc.check_free_space_gb)
        self.assertEqual(sig.parameters["min_gb"].default, 60.0)

        with tempfile.TemporaryDirectory() as td:
            fake_usage_low = mock.Mock(free=int(59.9 * (1024 ** 3)))
            with mock.patch("shutil.disk_usage", return_value=fake_usage_low):
                with self.assertRaises(pc.ProbePreflightError):
                    pc.check_free_space_gb(td, min=60.0)

            fake_usage_ok = mock.Mock(free=int(61.5 * (1024 ** 3)))
            with mock.patch("shutil.disk_usage", return_value=fake_usage_ok):
                free_gb = pc.check_free_space_gb(td, min=60.0)
                self.assertGreater(free_gb, 60.0)

    def test_check_out_dir_safe_guards_and_clean(self) -> None:
        with self.assertRaises(pc.ProbeSafetyError):
            pc.check_out_dir_safe("")
        with self.assertRaises(pc.ProbeSafetyError):
            pc.check_out_dir_safe(ROOT)

        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            # Frozen folders must always be refused
            frozen_cand = base / "gemini-core" / "candidate-2g-fix2"
            frozen_probe = base / "gemini-probes" / "r11-p4-10mm"
            frozen_cand.mkdir(parents=True)
            frozen_probe.mkdir(parents=True)
            with self.assertRaises(pc.ProbeSafetyError):
                pc.check_out_dir_safe(frozen_cand)
            with self.assertRaises(pc.ProbeSafetyError):
                pc.check_out_dir_safe(frozen_probe / "sub", clean=True)
            with self.assertRaises(pc.ProbeSafetyError):
                pc.check_out_dir_safe(base / "gemini-core")

            # Live Starfield install refused
            game = base / "StarfieldGame"
            (game / "Data").mkdir(parents=True)
            (game / "Starfield.exe").write_bytes(b"exe")
            with self.assertRaises(pc.ProbeSafetyError):
                pc.check_out_dir_safe(game / "stage")

            # Non-empty new probe folder refused unless clean=True
            new_probe = base / "gemini-probes" / "r11-p6-arsenal"
            new_probe.mkdir(parents=True)
            (new_probe / "stale.txt").write_text("stale", encoding="utf-8")
            with self.assertRaises(pc.ProbeSafetyError):
                pc.check_out_dir_safe(new_probe, clean=False)

            res = pc.check_out_dir_safe(new_probe, clean=True)
            self.assertTrue(res.is_dir())
            self.assertEqual(list(res.iterdir()), [])

    def test_copy_or_link_staged_file_frozen_and_copy_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            stage_src = base / "staging"
            frozen_probe = base / "gemini-probes" / "r11-p5-weapons"
            new_probe = base / "gemini-probes" / "r11-p6-arsenal"
            stage_src.mkdir(parents=True)
            frozen_probe.mkdir(parents=True)
            new_probe.mkdir(parents=True)

            # Never write/hardlink INTO a frozen probe folder
            src_txt = stage_src / "a.txt"
            src_txt.write_text("hi", encoding="utf-8")
            with self.assertRaises(pc.ProbeSafetyError):
                pc.copy_or_link_staged_file(src_txt, frozen_probe / "a.txt")

            # Copy-only extensions MUST produce st_nlink == 1 even on same drive
            for ext in (".esm", ".pex", ".json", ".txt", ".dll"):
                s = stage_src / f"item{ext}"
                d = new_probe / f"item{ext}"
                s.write_bytes(b"payload-" + ext.encode())
                mode = pc.copy_or_link_staged_file(s, d, allow_hardlink=True)
                self.assertEqual(mode, "copied")
                self.assertEqual(os.lstat(d).st_nlink, 1)

            # Frozen probe .ba2 source must NOT be hardlinked either
            frozen_ba2 = frozen_probe / "test - Main.ba2"
            frozen_ba2.write_bytes(b"ba2bytes")
            out_ba2 = new_probe / "test - Main.ba2"
            mode = pc.copy_or_link_staged_file(frozen_ba2, out_ba2, allow_hardlink=True)
            self.assertEqual(mode, "copied")
            self.assertEqual(os.lstat(frozen_ba2).st_nlink, 1)
            self.assertEqual(os.lstat(out_ba2).st_nlink, 1)

    def test_reuse_tested_binary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            cpp1 = base / "main.cpp"
            cpp2 = base / "pipboy_map.cpp"
            cpp1.write_text("// tested v1\n", encoding="utf-8")
            cpp2.write_text("// tested map v1\n", encoding="utf-8")
            src_digest = pc.hash_source_files([cpp1, cpp2])

            tested_dll = base / "tested" / "FO4SFPipboyMenu.dll"
            tested_dll.parent.mkdir()
            tested_dll.write_bytes(b"MZ-tested-dll")
            out_dll = base / "staged" / "FO4SFPipboyMenu.dll"

            calls: list[int] = []

            def fallback_build() -> pathlib.Path:
                calls.append(1)
                rebuilt = base / "built" / "FO4SFPipboyMenu.dll"
                rebuilt.parent.mkdir(exist_ok=True)
                rebuilt.write_bytes(b"MZ-rebuilt-dll")
                return rebuilt

            # Unchanged sources reuse tested binary without running fallback
            res1 = pc.reuse_tested_binary(
                [cpp1, cpp2], src_digest[:16], tested_dll, fallback_build, dst_path=out_dll
            )
            self.assertTrue(res1.reused)
            self.assertEqual(calls, [])
            self.assertEqual(pathlib.Path(res1).read_bytes(), b"MZ-tested-dll")
            self.assertEqual(os.lstat(out_dll).st_nlink, 1)

            # Modifying one C++ source invalidates reuse and invokes fallback build
            cpp2.write_text("// task4 fix\n", encoding="utf-8")
            res2 = pc.reuse_tested_binary(
                [cpp1, cpp2], src_digest, tested_dll, fallback_build, dst_path=out_dll
            )
            self.assertFalse(res2.reused)
            self.assertEqual(calls, [1])
            self.assertEqual(out_dll.read_bytes(), b"MZ-rebuilt-dll")

            # Verify pinned R12-7 DLL metadata constants are exposed
            self.assertEqual(len(pc.TESTED_PIPBOY_SOURCE_HASHES), 10)
            self.assertTrue(pc.TESTED_PIPBOY_DLL_SHA256.startswith(pc.TESTED_PIPBOY_DLL_SHA256_PREFIX))

    def test_pack_and_verify_gnrl_and_dx10_ba2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            src_dir = base / "loose"
            (src_dir / "meshes" / "weapons").mkdir(parents=True)
            (src_dir / "textures" / "weapons").mkdir(parents=True)
            mesh_p = src_dir / "meshes" / "weapons" / "baton.nif"
            mesh_p.write_bytes(b"Gamebryo File Format\x00testmesh")
            readme_p = src_dir / "readme"
            readme_p.write_bytes(b"no-extension-test")

            gnrl_out = base / "Probe - Main.ba2"
            pc.pack_gnrl_ba2(
                {
                    "meshes/weapons/baton.nif": mesh_p,
                    "readme": readme_p,
                },
                gnrl_out,
                compress=True,
            )
            hashes = pc.verify_ba2_entry_hashes(
                gnrl_out,
                {
                    "meshes/weapons/baton.nif": pc.sha256_file(mesh_p),
                    "readme": pc.sha256_file(readme_p),
                },
            )
            self.assertEqual(len(hashes), 2)

            with self.assertRaises(pc.ProbeValidationError):
                pc.verify_ba2_entry_hashes(
                    gnrl_out,
                    {"meshes/weapons/baton.nif": "0" * 64, "readme": pc.sha256_file(readme_p)},
                )

            dds1 = src_dir / "textures" / "weapons" / "baton_color.dds"
            dds2 = src_dir / "textures" / "weapons" / "baton_normal.dds"
            dds1.write_bytes(_make_dx10_dds(8, 8, 1, 72, b"\x11" * 64))
            dds2.write_bytes(_make_legacy_dxt5_dds(4, 4, b"\x22" * 16))
            dx10_out = base / "Probe - Textures.ba2"
            pc.pack_dx10_ba2(
                {
                    "textures/weapons/baton_color.dds": dds1,
                    "textures/weapons/baton_normal.dds": dds2,
                },
                dx10_out,
                compress=False,
            )
            pc.verify_ba2_entry_hashes(
                dx10_out,
                source_files={
                    "textures/weapons/baton_color.dds": dds1,
                    "textures/weapons/baton_normal.dds": dds2,
                },
            )

    def test_validate_batches_and_hops(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            ok_bat = base / "p6a.txt"
            ok_bat.write_text("player.setpos x 10.0\n", encoding="utf-8")
            bad_bat_name = base / "p6mv.txt"
            bad_bat_name.write_text("player.setpos x 10.0\n", encoding="utf-8")
            bad_bat_cmd = base / "p6b.txt"
            bad_bat_cmd.write_text("set FO4SF_PipboyAcquired to 1\n", encoding="utf-8")

            anchors = [
                pc.AnchorPoint("sanctuary", 100.0, 200.0, 50.0, "exterior"),
                pc.AnchorPoint("cryo", 0.0, 0.0, 0.0, "interior", "Vault111Cryo"),
            ]
            ok_hops = [
                pc.HopSpec("h1", "sanctuary", 250.0, 210.0, 55.0, "exterior"),
                pc.HopSpec("h_int", "cryo", 12.0, -5.0, 2.0, "interior", "Vault111Cryo"),
            ]
            errs = pc.validate_batches_and_hops(
                batch_files=[ok_bat],
                activate_commands=["bat p6a"],
                anchors=anchors,
                hops=ok_hops,
                raise_on_error=False,
            )
            self.assertEqual(errs, [])

            # Batch filename with M/N/V rejected
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(batch_files=[bad_bat_name])
            # Stripped FO4SF_ GLOB inside batch rejected
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(batch_files=[bad_bat_cmd])
            # Console M/N/V in activate command rejected
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(activate_commands=["bat p6m"])
            # >=200m hop on an axis rejected
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(
                    anchors=anchors,
                    hops=[pc.HopSpec("too_far", "sanctuary", 300.0, 200.0, 50.0, "exterior")],
                )
            # Cross-domain interior/exterior hop rejected by interior guard
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(
                    anchors=anchors,
                    hops=[pc.HopSpec("cross", "cryo", 10.0, 10.0, 10.0, "exterior")],
                )
            # Exterior hop rejected when interior_mode=True
            with self.assertRaises(pc.ProbeValidationError):
                pc.validate_batches_and_hops(
                    anchors=anchors,
                    hops=[pc.HopSpec("h_ext", "sanctuary", 110.0, 200.0, 50.0, "exterior")],
                    interior_mode=True,
                )

    def test_scan_plugin_cleanliness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)

            # Build minimal FO4TerrainCore.esm with WRLD 0x000803 + ext CELL 0x000804
            tc_w = PluginWriter(["Starfield.esm"])
            tc_w.add(Record(b"WRLD", tc_w.own(0x803), [(b"EDID", zbytes("FO4Core_Commonwealth"))]))
            tc_w.add(Record(b"CELL", tc_w.own(0x804), [
                (b"EDID", zbytes("FO4Core_SanctuaryExt")),
                (b"DATA", struct.pack("<H", 0x0000)),
                (b"XCLC", struct.pack("<iiI", 0, 0, 0)),
            ]))
            tc_path = base / "FO4TerrainCore.esm"
            tc_w.write(str(tc_path))

            # Build FO4Port.esm with persistent 0x000810 REFR and non-persistent 0x000811 REFR
            port_w = PluginWriter(["Starfield.esm"])
            port_w.add(Record(b"REFR", port_w.own(0x810), [(b"EDID", zbytes("GoodPersRef"))], flags=PERSISTENT))
            port_w.add(Record(b"REFR", port_w.own(0x811), [(b"EDID", zbytes("BadTempRef"))], flags=0))
            port_path = base / "FO4Port.esm"
            port_w.write(str(port_path))

            # Clean mission plugin referencing persistent FO4Port.esm:0x000810 + interior cell only
            clean_w = PluginWriter(["Starfield.esm", "FO4TerrainCore.esm", "FO4Port.esm"])
            clean_w.add(Record(b"CELL", clean_w.own(0x820), [
                (b"EDID", zbytes("CleanIntCell")),
                (b"DATA", struct.pack("<H", 0x0001)),
            ]))
            clean_w.add(Record(b"QUST", clean_w.own(0x821), [
                (b"EDID", zbytes("CleanQuest")),
                (b"VMAD", _build_vmad_v6_obj_prop("FO4SF_TestQuest", "TargetRef", (2 << 24) | 0x810)),
            ]))
            clean_path = base / "FO4SF_CleanProbe.esm"
            clean_w.write(str(clean_path))

            self.assertEqual(
                pc.scan_plugin_cleanliness([clean_path], reference_esms=[tc_path, port_path], raise_on_error=False),
                [],
            )

            # Dirty plugin with: PNDT, WRLD override on 0x01000803, ext CELL override on 0x01000804,
            # and non-persistent cross-plugin VMAD property pointing to FO4Port.esm:0x000811.
            dirty_w = PluginWriter(["Starfield.esm", "FO4TerrainCore.esm", "FO4Port.esm"])
            dirty_w.add(Record(b"PNDT", dirty_w.own(0x900), [(b"EDID", zbytes("BadPlanet"))]))
            cw_wrld = Record(b"WRLD", (1 << 24) | 0x803, [(b"EDID", zbytes("FO4Core_Commonwealth"))])
            cw_cell = Record(b"CELL", (1 << 24) | 0x804, [
                (b"EDID", zbytes("FO4Core_SanctuaryExt")),
                (b"DATA", struct.pack("<H", 0x0000)),
            ])
            dirty_w.add(Record(b"QUST", dirty_w.own(0x901), [
                (b"EDID", zbytes("BadQuest")),
                (b"VMAD", _build_vmad_v6_obj_prop("FO4SF_TestQuest", "TempGate", (2 << 24) | 0x811, array=True)),
            ]))
            # Write dirty plugin with WRLD GRUP nesting cw_cell cleanly
            base_bytes = dirty_w.to_bytes()
            wrld_group = group_bytes("WRLD", cw_wrld.to_bytes() + group_bytes(
                struct.pack("<I", cw_wrld.formid), cw_cell.to_bytes(), gtype=1
            ))
            dirty_path = base / "FO4SF_DirtyProbe.esm"
            dirty_path.write_bytes(base_bytes + wrld_group)

            errs = pc.scan_plugin_cleanliness(
                [dirty_path], reference_esms=[tc_path, port_path], raise_on_error=False
            )
            joined = "\n".join(errs)
            self.assertIn("PNDT", joined)
            self.assertIn("WRLD override", joined)
            self.assertIn("exterior CELL override", joined)
            self.assertIn("non-persistent cross-plugin REFR", joined)

    def test_atomic_install_collision_warning_rollback_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            sf = base / "Starfield"
            stage = base / "stage"
            (sf / "Data").mkdir(parents=True)
            stage.mkdir(parents=True)

            # Create pre-existing files simulating installed game state
            fo4port = sf / "Data" / "FO4Port.esm"
            fo4port.write_bytes(b"ORIG-FO4PORT")
            port_sha = pc.sha256_file(fo4port)

            mission = sf / "Data" / "FO4SFMission.esm"
            mission.write_bytes(b"NOT-2G-FIX2-MISSION")

            plugins_txt = sf / "Plugins.txt"
            orig_plg_bytes = b"\xef\xbb\xbf*Starfield.esm\r\n*FO4Port.esm\r\n"
            plugins_txt.write_bytes(orig_plg_bytes)

            # Staged artifacts
            (stage / "FO4Port.esm").write_bytes(b"PATCHED-FO4PORT")
            (stage / "FO4SF_Probe.esm").write_bytes(b"PROBE-ESM")
            (stage / "p6a.txt").write_text("player.setpos x 10\n", encoding="utf-8")
            card = stage / "card.md"
            card.write_text("# Test Card\n> - **Version Tag:** pending\n", encoding="utf-8")

            # 1. Pre-check *.txt collision must abort BEFORE changing any files
            unowned_txt = sf / "p6a.txt"
            unowned_txt.write_text("preexisting batch", encoding="utf-8")
            files_plan = [
                {"src_rel": "FO4Port.esm", "target_rel": "Data/FO4Port.esm", "allow_swap": True},
                {"src_rel": "FO4SF_Probe.esm", "target_rel": "Data/FO4SF_Probe.esm"},
                {"src_rel": "p6a.txt", "target_rel": "p6a.txt"},
            ]
            with self.assertRaisesRegex(pc.ProbeInstallError, r"\*\.txt collision"):
                pc.install_probe(
                    probe_id="p6",
                    stage_dir=stage,
                    starfield_dir=sf,
                    plugins_txt=plugins_txt,
                    plugins_to_activate=["FO4SF_Probe.esm"],
                    files=files_plan,
                    expected_base_hashes={"Data/FO4Port.esm": port_sha[:12]},
                    min_free_gb=0.0,
                    system=FakeSystem([]),
                )
            unowned_txt.unlink()

            # 2. Required base-hash mismatch must abort cleanly
            with self.assertRaisesRegex(pc.ProbeInstallError, "Base hash mismatch"):
                pc.install_probe(
                    probe_id="p6",
                    stage_dir=stage,
                    starfield_dir=sf,
                    plugins_txt=plugins_txt,
                    files=files_plan,
                    expected_base_hashes={"Data/FO4Port.esm": "ffffffff"},
                    min_free_gb=0.0,
                    system=FakeSystem([]),
                )

            # 3. Exception mid-install must roll back swapped files, added files, and Plugins.txt
            def boom(step: str) -> None:
                if step == "after_plugins":
                    raise RuntimeError("simulated disk error after Plugins.txt")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                with self.assertRaisesRegex(RuntimeError, "simulated disk error"):
                    pc.install_probe(
                        probe_id="p6",
                        stage_dir=stage,
                        starfield_dir=sf,
                        plugins_txt=plugins_txt,
                        plugins_to_activate=["FO4SF_Probe.esm"],
                        files=files_plan,
                        expected_base_hashes={"Data/FO4Port.esm": port_sha[:8]},
                        min_free_gb=0.0,
                        system=FakeSystem([]),
                        _fault_hook=boom,
                    )
            self.assertTrue(any("candidate-2g-fix2" in str(w.message) for w in caught))
            self.assertEqual(fo4port.read_bytes(), b"ORIG-FO4PORT")
            self.assertFalse((sf / "Data" / "FO4SF_Probe.esm").exists())
            self.assertFalse((sf / "p6a.txt").exists())
            self.assertEqual(plugins_txt.read_bytes(), orig_plg_bytes)
            self.assertFalse((sf / "Data" / ".fo4sf_probe_p6.json").exists())

            # 4. Clean install -> verify receipt, status, version stamp, BOM/CRLF Plugins.txt -> uninstall
            with warnings.catch_warnings(record=True) as caught2:
                warnings.simplefilter("always")
                rcpt = pc.install_probe(
                    probe_id="p6",
                    stage_dir=stage,
                    starfield_dir=sf,
                    plugins_txt=plugins_txt,
                    plugins_to_activate=["FO4SF_Probe.esm"],
                    files=files_plan,
                    expected_base_hashes={"Data/FO4Port.esm": port_sha[:8]},
                    version_tag="r12-abc1234",
                    card_path=card,
                    min_free_gb=0.0,
                    system=FakeSystem([]),
                )
            self.assertTrue(rcpt["complete"])
            self.assertEqual(rcpt["version_tag"], "r12-abc1234")
            self.assertTrue(rcpt["planned_swaps"])
            self.assertIn("`r12-abc1234`", card.read_text(encoding="utf-8"))
            self.assertEqual(os.lstat(sf / "Data" / "FO4SF_Probe.esm").st_nlink, 1)
            self.assertEqual(plugins_txt.read_bytes(), b"\xef\xbb\xbf*Starfield.esm\r\n*FO4Port.esm\r\n*FO4SF_Probe.esm\r\n")
            self.assertTrue(any("candidate-2g-fix2" in str(w.message) for w in caught2))

            st = pc.probe_status(probe_id="p6", starfield_dir=sf)
            self.assertEqual(st["state"], "installed")
            self.assertTrue(st["installed"])
            self.assertEqual(st["version_tag"], "r12-abc1234")

            pc.uninstall_probe(probe_id="p6", starfield_dir=sf, system=FakeSystem([]))
            self.assertEqual(fo4port.read_bytes(), b"ORIG-FO4PORT")
            self.assertFalse((sf / "Data" / "FO4SF_Probe.esm").exists())
            self.assertFalse((sf / "p6a.txt").exists())
            self.assertEqual(plugins_txt.read_bytes(), orig_plg_bytes)
            st_after = pc.probe_status(probe_id="p6", starfield_dir=sf)
            self.assertEqual(st_after["state"], "not_installed")

            # 5. Exact 2g-fix2 baseline hash match (including multi-variant tuple) produces 0 warnings
            mission_sha = pc.sha256_file(mission)
            with warnings.catch_warnings(record=True) as no_warn:
                warnings.simplefilter("always")
                pc.install_probe(
                    probe_id="p6_clean_base",
                    stage_dir=stage,
                    starfield_dir=sf,
                    plugins_txt=plugins_txt,
                    files=[{"src_rel": "FO4SF_Probe.esm", "target_rel": "Data/FO4SF_Probe.esm"}],
                    baseline_2g_fix2_hashes={"Data/FO4SFMission.esm": ("deadbeef", mission_sha)},
                    min_free_gb=0.0,
                    system=FakeSystem([]),
                )
            self.assertEqual(no_warn, [])
            pc.uninstall_probe(probe_id="p6_clean_base", starfield_dir=sf, system=FakeSystem([]))

    def test_crash_recovery_incomplete_receipt_and_status_replaced_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            sf = base / "Starfield"
            stage = base / "stage"
            (sf / "Data").mkdir(parents=True)
            stage.mkdir(parents=True)

            fo4port = sf / "Data" / "FO4Port.esm"
            fo4port.write_bytes(b"ORIG-PORT")
            port_sha = pc.sha256_file(fo4port)

            (stage / "FO4Port.esm").write_bytes(b"NEW-PORT")
            (stage / "FO4SF_Probe.esm").write_bytes(b"NEW-PROBE")
            (stage / "p6a.txt").write_text("player.setpos x 10\n", encoding="utf-8")

            plugins_txt = sf / "Plugins.txt"
            plugins_txt.write_text("*Starfield.esm\nFO4SF_Probe.esm\n", encoding="utf-8")
            files_plan = [
                {"src_rel": "FO4Port.esm", "target_rel": "Data/FO4Port.esm", "allow_swap": True},
                {"src_rel": "FO4SF_Probe.esm", "target_rel": "Data/FO4SF_Probe.esm"},
                {"src_rel": "p6a.txt", "target_rel": "p6a.txt"},
            ]

            # 1. Simulate post-copy hash verification failure BEFORE published_files is appended
            orig_copy = pc.copy_or_link_staged_file

            def corrupt_probe_copy(src, dst, **kwargs):
                res = orig_copy(src, dst, **kwargs)
                if pathlib.Path(dst).name == "FO4SF_Probe.esm":
                    pathlib.Path(dst).write_bytes(b"CORRUPT-WRITE")
                return res

            with mock.patch.object(pc, "copy_or_link_staged_file", side_effect=corrupt_probe_copy):
                with self.assertRaisesRegex(pc.ProbeInstallError, "Post-install SHA-256 verification failed"):
                    pc.install_probe(
                        probe_id="p6_postcopy_fail",
                        stage_dir=stage,
                        starfield_dir=sf,
                        plugins_txt=plugins_txt,
                        plugins_to_activate=["FO4SF_Probe.esm"],
                        files=files_plan,
                        expected_base_hashes={"Data/FO4Port.esm": port_sha},
                        min_free_gb=0.0,
                        system=FakeSystem([]),
                    )
            self.assertEqual(fo4port.read_bytes(), b"ORIG-PORT")
            self.assertFalse((sf / "Data" / "FO4SF_Probe.esm").exists())
            self.assertFalse((sf / "p6a.txt").exists())
            self.assertFalse((sf / "Data" / ".fo4sf_probe_p6_postcopy_fail.json").exists())

            # 2. Simulate interrupted install leaving complete=False & published_files=[] on disk,
            #    while planned_adds files already landed -> uninstall_probe must remove all orphans.
            rcpt = pc.install_probe(
                probe_id="p6_crash",
                stage_dir=stage,
                starfield_dir=sf,
                plugins_txt=plugins_txt,
                plugins_to_activate=["FO4SF_Probe.esm"],
                files=files_plan,
                expected_base_hashes={"Data/FO4Port.esm": port_sha},
                min_free_gb=0.0,
                system=FakeSystem([]),
            )
            # Downgrade Plugins.txt deactivation & inspect probe_status on plugins_replaced
            st_ok = pc.probe_status(probe_id="p6_crash", starfield_dir=sf)
            self.assertEqual(st_ok["state"], "installed")
            self.assertTrue(st_ok["plugins_ok"])

            plugins_txt.write_text("*Starfield.esm\nFO4SF_Probe.esm\n", encoding="utf-8")
            st_bad_plg = pc.probe_status(probe_id="p6_crash", starfield_dir=sf)
            self.assertFalse(st_bad_plg["plugins_ok"])
            self.assertEqual(st_bad_plg["state"], "degraded")

            # Also verify plugins_replaced alone (without plugins_added) is checked by probe_status
            rcpt_p = sf / "Data" / ".fo4sf_probe_p6_crash.json"
            rcpt["plugins_added"] = []
            rcpt["plugins_requested"] = []
            pc._write_json_atomic(rcpt_p, rcpt)
            st_rep = pc.probe_status(probe_id="p6_crash", starfield_dir=sf)
            self.assertFalse(st_rep["plugins_ok"])

            # Simulate crash receipt: complete=False, published_files=[]
            rcpt["complete"] = False
            rcpt["published_files"] = []
            rcpt["plugins_added"] = ["*FO4SF_Probe.esm"]
            pc._write_json_atomic(rcpt_p, rcpt)
            pc.uninstall_probe(probe_id="p6_crash", starfield_dir=sf, system=FakeSystem([]))
            self.assertEqual(fo4port.read_bytes(), b"ORIG-PORT")
            self.assertFalse((sf / "Data" / "FO4SF_Probe.esm").exists())
            self.assertFalse((sf / "p6a.txt").exists())
            self.assertFalse(rcpt_p.exists())
            self.assertIn("FO4SF_Probe.esm", plugins_txt.read_text(encoding="utf-8"))
            self.assertNotIn("*FO4SF_Probe.esm", plugins_txt.read_text(encoding="utf-8"))

            # 3. Dangling symlink target must be rejected cleanly before copy/backup
            with mock.patch.object(pathlib.Path, "is_symlink", autospec=True,
                                   side_effect=lambda p: p.parent.name == "Data" and p.name == "FO4SF_Probe.esm"):
                with self.assertRaisesRegex(pc.ProbeInstallError, "dangling-symlink"):
                    pc.install_probe(
                        probe_id="p6_sym",
                        stage_dir=stage,
                        starfield_dir=sf,
                        plugins_txt=plugins_txt,
                        files=[{"src_rel": "FO4SF_Probe.esm", "target_rel": "Data/FO4SF_Probe.esm"}],
                        min_free_gb=0.0,
                        system=FakeSystem([]),
                    )


if __name__ == "__main__":
    unittest.main()
