"""CI-safe and optional live-staged tests for Round 11 Probe P1 (Museum of Freedom)."""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / "src"
PROBES_DIR = REPO / "scripts" / "probes"
TERRAIN_DIR = REPO / "scripts" / "terrain"
TESTS_DIR = REPO / "tests"
for _p in (str(SRC_DIR), str(PROBES_DIR), str(TERRAIN_DIR), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_fo4port_r11_museum as ext  # noqa: E402
import stage_r11_p1_museum as p1  # noqa: E402
import test_r11_fo4port_museum as t3bc  # noqa: E402
import vmad_patch  # noqa: E402
from fo4sf import nif as fo4_nif  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402

QUEST_PSC = REPO / "scripts" / "probes" / "FO4SF_R11P1Quest.psc"
STAGE_SCRIPT = REPO / "scripts" / "probes" / "stage_r11_p1_museum.py"
DRIVE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]")


class TestProbeP1PluginsAndBatches(unittest.TestCase):
    def test_p1_museum_esm_structure_and_vmad_wiring(self) -> None:
        raw = p1.build_p1_museum_esm()
        tes4, _ = ext.parse_top_level(raw)
        masters = [sp.rstrip(b"\x00").decode("ascii") for ss, sp in ext.iter_subrecords(tes4.decompressed_body()) if ss == b"MAST"]
        self.assertEqual(masters, ["Starfield.esm", "FO4Port.esm", "FO4TerrainCore.esm", "FO4ActorRaider.esm"])

        recs = {r.fid: r for r in ext.walk_all_records(raw) if r.sig != b"TES4"}
        # Zero WRLD / PNDT overrides (prevents wiping FO4TerrainCore.esm:0x01000803 and dropping onto bare Mars!)
        self.assertEqual([r for r in recs.values() if r.sig in (b"WRLD", b"PNDT")], [])
        # Probe holding interior CELL + full 6-subrecord Museum CELL override (LTMP=0x0006BCF8)
        self.assertIn(p1.FID_CELL_HOLDING, recs)
        self.assertEqual(recs[p1.FID_CELL_HOLDING].sig, b"CELL")
        museum_cell = recs[p1.PORT_MUSEUM_CELL]
        museum_subs = {ss: sp for ss, sp in ext.iter_subrecords(museum_cell.decompressed_body())}
        self.assertEqual(struct.unpack("<I", museum_subs[b"LTMP"])[0], p1.SF_PROVEN_LTMP)
        self.assertEqual(struct.unpack("<I", museum_subs[b"XCIM"])[0], p1.SF_PROVEN_XCIM)
        self.assertEqual(museum_subs[b"XEMP"], p1.SF_PROVEN_XEMP)
        self.assertEqual(len(museum_subs[b"DATA"]), 4)

        # All 4 confirmed-arrival doors + basement terminal + 3F raider trigger + ground raider + quest present
        for fid in (
            p1.FID_REF_EXT_FRONT_IN,
            p1.FID_REF_INT_FRONT_OUT,
            p1.FID_REF_INT_ROOF_OUT,
            p1.FID_REF_EXT_ROOF_IN,
            p1.FID_REF_INT_BASEMENT_TERM,
            p1.FID_REF_INT_RAIDER_TRIGGER,
            p1.FID_ACHR_GROUND_RAIDER,
            p1.FID_QUST_P1,
            p1.FID_QUST_LOADDOOR,
        ):
            self.assertIn(fid, recs, f"missing expected record 0x{fid:08X}")
        self.assertEqual(recs[p1.FID_REF_INT_RAIDER_TRIGGER].flags & 0x400, 0x400)

        # B1: Verify every new ACTI uses a real non-marker MODL and non-zero 24-byte ObjectBounds (OBND)
        for acti_fid in (
            p1.FID_ACTI_FRONT_IN,
            p1.FID_ACTI_FRONT_OUT,
            p1.FID_ACTI_ROOF_OUT,
            p1.FID_ACTI_ROOF_IN,
            p1.FID_ACTI_BASEMENT_TERM,
            p1.FID_ACTI_RAIDER_TRIGGER,
        ):
            subs = {ss: sp for ss, sp in ext.iter_subrecords(recs[acti_fid].decompressed_body())}
            modl = subs.get(b"MODL", b"").rstrip(b"\x00").decode("utf-8", errors="replace")
            self.assertFalse(p1.is_invalid_or_marker_model(modl), f"invalid/marker MODL on ACTI 0x{acti_fid:08X}: {modl!r}")
            self.assertTrue(p1.has_nonzero_obnd(subs.get(b"OBND", b"")), f"zero OBND on ACTI 0x{acti_fid:08X}")

        # Verify VMAD on all 4 confirmed-arrival doors decodes cleanly via vmad_patch
        for door_fid, want_dir, want_plugin, want_core in (
            (p1.FID_REF_EXT_FRONT_IN, "in", "FO4Port.esm", False),
            (p1.FID_REF_INT_FRONT_OUT, "out", "FO4TerrainCore.esm", True),
            (p1.FID_REF_INT_ROOF_OUT, "out", "FO4TerrainCore.esm", True),
            (p1.FID_REF_EXT_ROOF_IN, "in", "FO4Port.esm", False),
        ):
            rec = recs[door_fid]
            self.assertEqual(rec.flags & 0x400, 0x400, f"door 0x{door_fid:08X} must be persistent")
            vmad_bytes = next(sp for ss, sp in ext.iter_subrecords(rec.decompressed_body()) if ss == b"VMAD")
            decoded = vmad_patch.decode(vmad_bytes)
            self.assertEqual(decoded["scripts"][0]["name"], "FO4SF_ConfirmedLoadDoor")
            pmap = {p["name"]: p["value"] for p in decoded["scripts"][0]["properties"]}
            self.assertEqual(pmap["Direction"], want_dir)
            self.assertEqual(pmap["TargetPlugin"], want_plugin)
            self.assertEqual(pmap["RequireCoreCell"], want_core)
            self.assertEqual(pmap["LoadDoorController"]["form"], p1.FID_QUST_LOADDOOR)
            self.assertTrue(pmap["UseDestinationPosition"])
            if want_dir == "out":
                self.assertEqual(pmap["TargetFormId"], p1.CORE_EXIT_PRIMARY_ANCHOR_LOCAL)
                self.assertEqual(pmap["FallbackTargetPlugin"], "FO4TerrainCore.esm")
                self.assertEqual(pmap["FallbackTargetFormId"], p1.CORE_EXIT_FALLBACK_ANCHOR_LOCAL)
                self.assertEqual(pmap["MergeOffsetX"], p1.MERGE_OFFSET_X)
                self.assertEqual(pmap["MergeOffsetY"], p1.MERGE_OFFSET_Y)
            else:
                self.assertEqual(pmap["TargetFormId"], p1.PORT_MUSEUM_ANCHOR_LOCAL)

        # Verify QUST FO4SF_LoadDoorQuest (0x4000821) + GroundRaider follow package ALPC
        lqrec = recs[p1.FID_QUST_LOADDOOR]
        lqdnam = next(sp for ss, sp in ext.iter_subrecords(lqrec.decompressed_body()) if ss == b"DNAM")
        self.assertEqual(struct.unpack_from("<I", lqdnam, 0)[0], p1.QUST_DNAM_START_GAME_ENABLED)
        lqvmad = next(sp for ss, sp in ext.iter_subrecords(lqrec.decompressed_body()) if ss == b"VMAD")
        self.assertIn(b"FO4SF_LoadDoorQuest", lqvmad)

        # Verify ACHR ground-floor raider is Persistent | InitiallyDisabled (0xC00) & uses FO4ActorRaider.esm:0xF04800
        raider_rec = recs[p1.FID_ACHR_GROUND_RAIDER]
        self.assertEqual(raider_rec.sig, b"ACHR")
        self.assertEqual(raider_rec.flags & 0xC00, 0xC00, "GroundRaider must be Persistent | InitiallyDisabled (0xC00)")
        self.assertEqual(ext.refr_name(raider_rec), p1.RAIDER_NPC_BASE)

        # Verify QUST DNAM flags (0x00000009 StartGameEnabled | AllowRepeatedStages) + VMAD bindings
        qrec = recs[p1.FID_QUST_P1]
        qdnam = next(sp for ss, sp in ext.iter_subrecords(qrec.decompressed_body()) if ss == b"DNAM")
        self.assertEqual(struct.unpack_from("<I", qdnam, 0)[0], p1.QUST_DNAM_START_GAME_ENABLED)
        qvmad = next(sp for ss, sp in ext.iter_subrecords(qrec.decompressed_body()) if ss == b"VMAD")
        self.assertIn(b"PortPlugin", qvmad)
        self.assertIn(b"BasementGateLocalId", qvmad)
        self.assertIn(b"ExtFrontInDoor", qvmad)
        self.assertIn(b"ExtRoofInDoor", qvmad)
        self.assertIn(b"RaiderTrigger", qvmad)
        self.assertIn(b"HideSpacesuitAV", qvmad)
        self.assertTrue(qvmad.endswith(p1.QUST_VMAD_TAIL))
        alpc_vals = [struct.unpack_from("<I", sp, 0)[0] for ss, sp in ext.iter_subrecords(qrec.decompressed_body()) if ss == b"ALPC" and len(sp) >= 4]
        self.assertIn(p1.SF_DEFAULT_FOLLOW_PKG, alpc_vals)

    def test_optional_xtel_extra_trap_removed_and_roof_separated(self) -> None:
        with self.assertRaises(p1.ProbeError):
            p1.build_optional_xtel_extra_esm()
        self.assertEqual(p1.EXT_ROOF_ARRIVAL_MERGED, (-1990.58, -1724.19, 97.56))
        self.assertNotEqual(p1.EXT_ROOF_ARRIVAL_MERGED, p1.EXT_ROOF_DOOR_MERGED)
        dx = p1.EXT_ROOF_ARRIVAL_MERGED[0] - p1.EXT_ROOF_DOOR_MERGED[0]
        dy = p1.EXT_ROOF_ARRIVAL_MERGED[1] - p1.EXT_ROOF_DOOR_MERGED[1]
        sep_xy = (dx * dx + dy * dy) ** 0.5
        self.assertGreaterEqual(sep_xy, 1.5)
        self.assertLessEqual(sep_xy, 2.2)

    def test_b1_rejects_marker_empty_modl_and_zero_obnd(self) -> None:
        self.assertTrue(p1.is_invalid_or_marker_model(""))
        self.assertTrue(p1.is_invalid_or_marker_model("Markers\\DecoratorMarker.nif"))
        self.assertTrue(p1.is_invalid_or_marker_model("EditorMarker.nif"))
        self.assertFalse(p1.is_invalid_or_marker_model("fo4port\\setdressing\\doors\\paintedwooddoordoubleload01.nif"))
        self.assertFalse(p1.has_nonzero_obnd(b"\x00" * 24))
        with self.assertRaises(p1.ProbeError):
            p1._make_acti(0x04000899, "FO4SF_BadActi", "Bad", modl=b"Markers\\DecoratorMarker.nif\x00")
        with self.assertRaises(p1.ProbeError):
            p1._make_acti(
                0x0400089A,
                "FO4SF_ZeroObndActi",
                "Bad",
                modl=b"fo4port\\furniture\\terminals\\terminalwall01.nif\x00",
                obnd=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            )

    def test_p3_zero_mnv_and_exterior_hop_math_under_200m(self) -> None:
        batches = p1.build_p3_batch_scripts()
        rep = p1.validate_p3_batches_and_hops(batches)
        self.assertTrue(rep["p3_zero_mnv"])
        for fname, content in batches.items():
            self.assertIsNone(p1.P3_FORBIDDEN_RE.search(fname), f"P3 forbidden char in {fname}")
            self.assertIsNone(p1.STRIPPED_MOD_EDID_RE.search(content), f"stripped mod EDID in {fname}")
        self.assertIn("SetStage 11000820 10", batches["p1b.txt"])
        self.assertNotIn("player.setpos", batches["p1b.txt"])
        self.assertIn("SetStage 11000820 20", batches["p1k.txt"])
        self.assertNotIn("player.setpos", batches["p1k.txt"])
        self.assertIn("SetStage 11000820 30", batches["p1q.txt"])
        for cmd in rep["typed_commands"]:
            self.assertIsNone(p1.P3_FORBIDDEN_RE.search(cmd), f"P3 forbidden char in typed cmd {cmd}")
        for hop in rep["exterior_hops"]:
            self.assertLess(hop["max_axis_m"], 200.0)
            self.assertTrue(hop["under_200m_per_axis"])

        # Negative tests: filename containing M/N/V OR stripped FO4SF_ EDID inside batch must be rejected
        with self.assertRaises(p1.ProbeError):
            p1.validate_p3_batches_and_hops({"p1museum.txt": "coc FO4Port_ConcordMuseum01\n"})
        with self.assertRaises(p1.ProbeError):
            p1.validate_p3_batches_and_hops({"p1b.txt": "SetStage FO4SF_R11P1Quest 10\n"})

    def test_synthetic_stage_verify_install_and_reversible_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_dir = root / "b00"
            src_dir = root / "b10"
            stage_dir = root / "r11-p1-museum"
            sf_dir = root / "FakeStarfield"
            sf_data = sf_dir / "Data"
            plugins_txt = root / "Plugins.txt"

            for d in (base_dir, src_dir, sf_data):
                d.mkdir(parents=True, exist_ok=True)

            base_esm, src_esm = t3bc._build_synthetic_base_and_source()
            (base_dir / "FO4Port.esm").write_bytes(base_esm)
            (src_dir / "FO4Port.esm").write_bytes(src_esm)
            nif_obj = fo4_nif.NifFile(user_version=12, bs_version=172)
            nif_obj.block_types = ["NiNode", "bhkNPCollisionObject"]
            nif_obj.block_type_index = [0, 1]
            nif_obj.blocks = [b"", b""]
            nif_obj.strings = [b"materials\\fo4port\\shared.mat"]
            nif_bytes = fo4_nif.serialize(nif_obj)
            mat_bytes = b'{"textures": {"color": "textures\\\\fo4port\\\\a.dds"}}\n'
            port_main_entries = [
                ("meshes\\fo4port\\shared.nif", nif_bytes),
                ("meshes\\fo4port\\setdressing\\doors\\paintedwooddoordoubleload01.nif", nif_bytes),
                ("meshes\\fo4port\\interiors\\building\\woodp\\doors\\bldwoodpdoorload01.nif", nif_bytes),
                ("meshes\\fo4port\\furniture\\terminals\\terminalwall01.nif", nif_bytes),
                ("meshes\\fo4port\\furniture\\terminals\\terminalconsoleon.nif", nif_bytes),
                ("materials\\fo4port\\shared.mat", mat_bytes),
            ]
            p1.pack_gnrl_ba2_v2(port_main_entries, base_dir / "FO4Port - Main.ba2")
            p1.pack_gnrl_ba2_v2(port_main_entries, src_dir / "FO4Port - Main.ba2")

            def _write_bs_dx10(path: Path, rel: str, chunk: bytes) -> None:
                norm = rel.replace("/", "\\").lstrip("\\")
                nh = p1.bs_crc32(Path(norm).stem.lower().encode("ascii"))
                dh = p1.bs_crc32(os.path.dirname(norm).lower().encode("ascii"))
                table_sz = 24 + 24
                cur = 32 + table_sz
                name_off = cur + len(chunk)
                nb = norm.encode("utf-8")
                with path.open("wb") as f:
                    f.write(struct.pack("<4sI4sIQII", b"BTDX", 2, b"DX10", 1, name_off, 1, 0))
                    f.write(struct.pack("<I4sIBBHHHBBBB", nh, b"dds\x00", dh, 0, 1, 24, 4, 4, 1, 71, 0, 8))
                    f.write(struct.pack("<QIIHHI", cur, 0, len(chunk), 0, 0, ext.BA2_ALIGN))
                    f.write(chunk)
                    f.write(struct.pack("<H", len(nb)) + nb)

            _write_bs_dx10(base_dir / "FO4Port - Textures.ba2", "textures\\fo4port\\a.dds", b"\x11" * 16)
            _write_bs_dx10(src_dir / "FO4Port - Textures.ba2", "textures\\fo4port\\a.dds", b"\x11" * 16)

            # Build synthetic FO4 ESM containing CELL 0x00017DF7 + NAVM 0x00197BB0
            fo4_nvnm = t3bc._build_synthetic_fo4_interior_nvnm()
            navm_rec = ext.RawRecord(b"NAVM", 0, ext.FO4_MUSEUM_NAVM_FID, 0, 131, 0, ext.pack_subrecords([(b"NVNM", fo4_nvnm)]))
            fo4_cell = ext.RawRecord(b"CELL", 0, ext.FO4_MUSEUM_CELL_FID, 0, 131, 0, ext.pack_subrecords([(b"EDID", b"ConcordMuseum01\x00")]))
            fo4_tes4 = ext.RawRecord(b"TES4", 1, 0, 0, 131, 0, ext.pack_subrecords([(b"HEDR", struct.pack("<fII", 0.95, 2, 0x800))]))
            fo4_cell_grup = ext.TopGrup(b"CELL", 0, 0, 0, ext.wrap_cell_entry(fo4_cell, [], [navm_rec]))
            fo4_esm = root / "Fallout4.esm"
            fo4_esm.write_bytes(fo4_tes4.to_bytes() + fo4_cell_grup.to_bytes())

            # Seed fake Starfield Data with implicit full master + light master + FO4Port + FO4TerrainCore
            full_tes4 = ext.RawRecord(b"TES4", 0x001, 0, 0, 576, 0, ext.pack_subrecords([(b"HEDR", struct.pack("<fII", 0.96, 0, 0x800))])).to_bytes()
            light_tes4 = ext.RawRecord(b"TES4", 0x201, 0, 0, 576, 0, ext.pack_subrecords([(b"HEDR", struct.pack("<fII", 0.96, 0, 0x800))])).to_bytes()
            (sf_data / "Starfield.esm").write_bytes(full_tes4)
            (sf_data / "FO4TerrainCore.esm").write_bytes(full_tes4)
            (sf_data / "SFBGS003.esm").write_bytes(light_tes4)  # light master (0x200) must NOT consume full slot
            (sf_data / "FO4Port.esm").write_bytes(base_esm)
            pre_port_sha = ext.sha256_file(sf_data / "FO4Port.esm")
            (sf_data / "FO4Port - Main.ba2").write_bytes((base_dir / "FO4Port - Main.ba2").read_bytes())
            (sf_data / "FO4Port - Textures.ba2").write_bytes((base_dir / "FO4Port - Textures.ba2").read_bytes())
            plugins_txt.write_text("*FO4Port.esm\n*SFBGS003.esm\n*FO4TerrainCore.esm\n", encoding="utf-8")

            manifest = p1.stage_probe_p1(
                base_dir=base_dir,
                source_dir=src_dir,
                fo4_esm=fo4_esm,
                out_dir=stage_dir,
                prebuilt_pex={
                    "FO4SF_ConfirmedLoadDoor": b"PEX_FAKE_DOOR_BYTES",
                    "FO4SF_LoadDoorQuest": b"PEX_FAKE_LOADDOOR_BYTES",
                    "FO4SF_R11P1Quest": b"PEX_FAKE_QUEST_BYTES",
                },
                min_free_gb=0.0,
                allow_custom_base=True,
            )
            # F11: Non-empty out_dir must be refused unless clean=True
            with self.assertRaises(ext.ExtensionError):
                p1.stage_probe_p1(
                    base_dir=base_dir,
                    source_dir=src_dir,
                    fo4_esm=fo4_esm,
                    out_dir=stage_dir,
                    prebuilt_pex={
                        "FO4SF_ConfirmedLoadDoor": b"X",
                        "FO4SF_LoadDoorQuest": b"L",
                        "FO4SF_R11P1Quest": b"Y",
                    },
                    min_free_gb=0.0,
                    allow_custom_base=True,
                )
            self.assertEqual(manifest["port_extension"]["verification"]["missing_base_ids"], 0)
            self.assertEqual(manifest["port_extension"]["verification"]["body_changes"], 0)
            ver = p1.verify_probe_stage(stage_dir)
            self.assertTrue(ver["p3_zero_mnv"])
            self.assertEqual(ver["p1_main_ba2_entries"], 3)

            # Verify BA2 contains all 3 Scripts/*.pex entries AND exact Bethesda bs_crc32 headers
            self.assertEqual(p1.bs_crc32(b"scripts"), 0x40724840)
            self.assertEqual(p1.bs_crc32(b"textures\\fo4core\\ammo\\10mm"), 0x01C88DFC)
            self.assertEqual(p1.bs_crc32(b"10mmcartridge_color"), 0xABDBFB3B)
            p1_ba2_path = stage_dir / "exp" / p1.PROBE_MAIN_BA2
            self.assertEqual(p1.verify_ba2_bs_crc32_headers(p1_ba2_path), 3)
            ba2 = Ba2(str(p1_ba2_path))
            self.assertEqual(ba2.read("Scripts\\FO4SF_ConfirmedLoadDoor.pex"), b"PEX_FAKE_DOOR_BYTES")
            self.assertEqual(ba2.read("Scripts\\FO4SF_LoadDoorQuest.pex"), b"PEX_FAKE_LOADDOOR_BYTES")
            self.assertEqual(ba2.read("Scripts\\FO4SF_R11P1Quest.pex"), b"PEX_FAKE_QUEST_BYTES")

            # Negative check: IEEE zlib.crc32 header corruption must be rejected by verify_ba2_bs_crc32_headers
            bad_ba2 = root / "bad_crc.ba2"
            bad_bytes = bytearray(p1_ba2_path.read_bytes())
            bad_bytes[32] ^= 0xFF  # flip first entry name_hash byte
            bad_ba2.write_bytes(bytes(bad_bytes))
            with self.assertRaises(p1.ProbeError):
                p1.verify_ba2_bs_crc32_headers(bad_ba2)

            # Reversible install + status + uninstall round-trip (mock OS process check so synthetic tempfile
            # tests stay deterministic even when Starfield.exe is running elsewhere on the machine).
            # Full masters ahead of FO4SF_R11P1Museum: Starfield(00), FO4Port(01), FO4TerrainCore(02) -> slot 0x03!
            with mock.patch.object(p1, "_check_starfield_not_running", return_value=None):
                # F1: Base SHA check refuses unexpected live FO4Port.esm without allow_custom_base=True
                with self.assertRaises(p1.ProbeError):
                    p1.install_probe_p1(stage_dir, sf_dir, plugins_txt=plugins_txt, min_free_gb=0.0)
                # F2: Batch file collision fails BEFORE modifying Data/ or Plugins.txt!
                (sf_dir / "p1b.txt").write_text("existing\n", encoding="utf-8")
                with self.assertRaises(p1.ProbeError):
                    p1.install_probe_p1(
                        stage_dir, sf_dir, plugins_txt=plugins_txt, min_free_gb=0.0, allow_custom_base=True
                    )
                self.assertEqual(ext.sha256_file(sf_data / "FO4Port.esm"), pre_port_sha)
                self.assertEqual(
                    plugins_txt.read_text(encoding="utf-8"),
                    "*FO4Port.esm\n*SFBGS003.esm\n*FO4TerrainCore.esm\n",
                )
                (sf_dir / "p1b.txt").unlink()

                inst_rec = p1.install_probe_p1(
                    stage_dir, sf_dir, plugins_txt=plugins_txt, min_free_gb=0.0, allow_custom_base=True
                )
                self.assertEqual(inst_rec["quest_load_prefix_hex"], "0x03")
                self.assertEqual(inst_rec["quest_runtime_formid"], "03000820")
                self.assertIn("SetStage 03000820 10", (sf_dir / "p1b.txt").read_text(encoding="utf-8"))
                self.assertIn("SetStage 03000820 20", (sf_dir / "p1k.txt").read_text(encoding="utf-8"))
                self.assertIn("SetStage 03000820 30", (sf_dir / "p1q.txt").read_text(encoding="utf-8"))
                # Verify .esm files are independent copies (NOT hardlinked to stage_dir!)
                self.assertNotEqual(
                    os.stat(sf_data / "FO4Port.esm").st_ino,
                    os.stat(stage_dir / "port" / "FO4Port.esm").st_ino,
                )
                self.assertNotEqual(
                    os.stat(sf_data / p1.PROBE_PLUGIN).st_ino,
                    os.stat(stage_dir / "exp" / p1.PROBE_PLUGIN).st_ino,
                )
                self.assertTrue(p1.status_probe_p1(sf_dir)["installed"])
                self.assertTrue((sf_data / p1.PROBE_PLUGIN).is_file())
                self.assertFalse((sf_data / p1.XTEL_EXTRA_PLUGIN).exists())
                self.assertIn("*FO4SF_R11P1Museum.esm", plugins_txt.read_text(encoding="utf-8"))
                self.assertTrue((sf_dir / "p1c.txt").is_file())
                self.assertNotEqual(ext.sha256_file(sf_data / "FO4Port.esm"), pre_port_sha)

                res = p1.uninstall_probe_p1(sf_dir, plugins_txt=plugins_txt)
            self.assertTrue(res["uninstalled"])
            self.assertFalse(p1.status_probe_p1(sf_dir)["installed"])
            self.assertFalse((sf_data / p1.PROBE_PLUGIN).exists())
            self.assertFalse((sf_dir / "p1c.txt").exists())
            self.assertEqual(ext.sha256_file(sf_data / "FO4Port.esm"), pre_port_sha)
            self.assertEqual(
                plugins_txt.read_text(encoding="utf-8"),
                "*FO4Port.esm\n*SFBGS003.esm\n*FO4TerrainCore.esm\n",
            )

            # F12: Verify --reuse-port-ba2-dir copies (never hardlinks) unchanged FO4Port BA2s while rebuilding FO4Port.esm
            stage_v2 = root / "r11-p1-museum-v2"
            p1.stage_probe_p1(
                base_dir=base_dir,
                source_dir=src_dir,
                fo4_esm=fo4_esm,
                out_dir=stage_v2,
                prebuilt_pex={
                    "FO4SF_ConfirmedLoadDoor": b"PEX_FAKE_DOOR_V2",
                    "FO4SF_LoadDoorQuest": b"PEX_FAKE_LOADDOOR_V2",
                    "FO4SF_R11P1Quest": b"PEX_FAKE_QUEST_V2",
                },
                min_free_gb=0.0,
                reuse_port_ba2_dir=stage_dir / "port",
                allow_custom_base=True,
            )
            self.assertNotEqual(
                os.stat(stage_v2 / "port" / "FO4Port - Main.ba2").st_ino,
                os.stat(stage_dir / "port" / "FO4Port - Main.ba2").st_ino,
            )
            self.assertNotEqual(
                os.stat(stage_v2 / "port" / "FO4Port - Textures.ba2").st_ino,
                os.stat(stage_dir / "port" / "FO4Port - Textures.ba2").st_ino,
            )
            self.assertNotEqual(
                os.stat(stage_v2 / "port" / "FO4Port.esm").st_ino,
                os.stat(stage_dir / "port" / "FO4Port.esm").st_ino,
            )
            self.assertTrue(p1.verify_probe_stage(stage_v2)["p3_zero_mnv"])

            # Negative B1 check: stripping bhkNPCollisionObject from a placed ACTI NIF in stage_v2/port must fail verify_probe_stage
            bad_nif_obj = fo4_nif.NifFile(user_version=12, bs_version=172)
            bad_nif_obj.block_types = ["NiNode"]
            bad_nif_obj.block_type_index = [0]
            bad_nif_obj.blocks = [b""]
            bad_nif_obj.strings = []
            bad_entries = [
                (name, fo4_nif.serialize(bad_nif_obj) if name.endswith("paintedwooddoordoubleload01.nif") else payload)
                for name, payload in port_main_entries
            ]
            p1.pack_gnrl_ba2_v2(bad_entries, stage_v2 / "port" / "FO4Port - Main.ba2")
            with self.assertRaises(p1.ProbeError):
                p1.verify_probe_stage(stage_v2)

    def test_starfield_running_guard_refuses_when_game_active(self) -> None:
        fake_hit = SimpleNamespace(stdout="Starfield.exe                42196 Console                    1  100,000 K\n")
        fake_none = SimpleNamespace(stdout="INFO: No tasks are running which match the specified criteria.\n")
        with mock.patch.object(p1.sys, "platform", "win32"):
            with mock.patch.object(p1.subprocess, "run", return_value=fake_hit):
                with self.assertRaises(p1.ProbeError):
                    p1._check_starfield_not_running()
            with mock.patch.object(p1.subprocess, "run", return_value=fake_none):
                p1._check_starfield_not_running()

    def test_script_hygiene_and_quest_papyrus_contract(self) -> None:
        for path in (QUEST_PSC, STAGE_SCRIPT):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"BOM in {path.name}")
            txt = raw.decode("utf-8")
            self.assertIsNone(DRIVE_PATH_RE.search(txt), f"local drive path leak in {path.name}")
        qtxt = QUEST_PSC.read_text(encoding="utf-8")
        for token in (
            "Scriptname FO4SF_R11P1Quest extends Quest",
            "string Property PortPlugin = \"FO4Port.esm\" Auto",
            "int Property BasementGateLocalId = 0 Auto",
            "int Property BasementTerminalLocalId = 0x00E35E Auto",
            "bool Function IsPlayerInMuseum(Actor player)",
            "Function OpenBasementGate(string sourceTag)",
            "ObjectReference Property ExtFrontInDoor Auto",
            "ObjectReference Property ExtRoofInDoor Auto",
            "ObjectReference Property RaiderTrigger Auto",
            "Event OnInit()",
            "Event OnQuestInit()",
            "Event OnQuestStarted()",
            "Event Actor.OnPlayerLoadGame(Actor akSender)",
            "Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)",
            "elseif akSender == RaiderTrigger",
            "Event OnStageSet(int auiStageID, int auiItemID)",
            "ObjectReference Function ResolveBasementGate()",
            "Function SyncExteriorDoors(string sourceTag)",
            "FO4SF_R11P1 ext_door_placed tag=",
            "GroundRaider.Enable(false)",
            "GroundRaider.Is3DLoaded()",
            "GroundRaider.Resurrect()",
            "GroundRaider.SetRestrained(false)",
            "ActorValue Property HideSpacesuitAV Auto",
            "Game.GetAggressionAV()",
            "Game.GetConfidenceAV()",
            "GroundRaider.SetValue(HideSpacesuitAV, 1.0)",
            "GroundRaider.EvaluatePackage()",
            "FO4SF_R11P1 basement_gate opened=true",
            "FO4SF_R11P1 raider_combat started=true",
            "FO4SF_R11P1 raider_nav tick=",
            "FO4SF_R11P1 snapshot tag=",
            "gate.SetOpen(true)",
            'gate.PlayGamebryoAnimation("Open", false, 0.0)',
            "GroundRaider.StartCombat(player)",
        ):
            self.assertIn(token, qtxt, f"missing token in FO4SF_R11P1Quest.psc: {token}")


# ---------------------------------------------------------------------------
# Optional live-staged Probe P1 verification (skipped cleanly on hosted Linux CI)
# ---------------------------------------------------------------------------
_LIVE_P1_STAGE = os.environ.get("FO4SF_R11_P1_STAGE", "")
_LIVE_P1_READY = bool(_LIVE_P1_STAGE and (Path(_LIVE_P1_STAGE) / "manifest.json").is_file())


@unittest.skipUnless(_LIVE_P1_READY, "FO4SF_R11_P1_STAGE not configured (skipped on CI)")
class TestLiveStagedProbeP1(unittest.TestCase):
    def test_live_staged_probe_p1_manifest_hashes_and_p3(self) -> None:
        stage_dir = Path(_LIVE_P1_STAGE)
        ver = p1.verify_probe_stage(stage_dir)
        self.assertTrue(ver["p3_zero_mnv"])
        self.assertGreaterEqual(ver["verified_files"], 15)
        self.assertEqual(ver["p1_main_ba2_entries"], 3)
        manifest = json.loads((stage_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["port_extension"]["verification"]["missing_base_ids"], 0)
        self.assertEqual(manifest["port_extension"]["verification"]["body_changes"], 0)
        self.assertEqual(manifest["port_extension"]["museum_navm"]["validation_errors"], 0)
        self.assertGreaterEqual(manifest["disk_free_gb_after"], 60.0)


if __name__ == "__main__":
    unittest.main()
