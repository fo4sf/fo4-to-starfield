"""Tests for S1 beats/Stage 20/Skip Pre-War preservation, Handy Codsworth bundle, MQ101 filter, dotnet Prewar & Papyrus."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for sub in ("src", "scripts/prewar", "scripts/newgame"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf.planet import esm  # noqa: E402
from fo4sf.prewar import handy_codsworth, mq101_census, s1_spec  # noqa: E402
import build_prewar_quest  # noqa: E402
import make_newgame  # noqa: E402


def _make_synthetic_handy_bundle(bundle_dir: Path) -> None:
    """Create a valid synthetic `--codsworth-handy` bundle matching #854 (`FO4SF_RA2Handy.esm` + `Data/`)."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    data = bundle_dir / "Data"
    (data / "meshes" / "fo4sf" / "actors" / "handy").mkdir(parents=True, exist_ok=True)
    (data / "meshes" / "fo4sf" / "actors" / "handy" / "handy.nif").write_bytes(b"NIF_SYNTH")
    (data / "geometries" / "fo4sf").mkdir(parents=True, exist_ok=True)
    (data / "geometries" / "fo4sf" / "handy.mesh").write_bytes(b"MESH_SYNTH")

    graph = "Actors\\FO4SF\\Handy\\HandyGraph.agx"
    key_hex = f"{handy_codsworth.manifest_key(graph, ['Neutral'])}.txt"
    for d in handy_codsworth.HANDY_MANIFEST_DIRS:
        p = data / "meshes" / "AnimTextData" / d / key_hex
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("synth manifest\n", encoding="utf-8")

    gsd = data / "meshes" / "AnimTextData" / "GeneratedSubgraphData" / "fo4sf_handyrace.txt"
    gsd.parent.mkdir(parents=True, exist_ok=True)
    gsd.write_text("synth gsd\n", encoding="utf-8")

    # Synthetic FO4SF_RA2Handy.esm with BPTD 0x802 and RACE 0x801 linked via GNAM + SGNM/SAPT
    w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    w.add(esm.Record(b"BPTD", 0x000802, [(b"EDID", esm.zbytes(handy_codsworth.HANDY_BPTD_EDID))]))
    w.add(
        esm.Record(
            b"RACE",
            0x000801,
            [
                (b"EDID", esm.zbytes(handy_codsworth.HANDY_RACE_EDID)),
                (b"GNAM", struct.pack("<I", 0x000802)),
                (b"SGNM", esm.zbytes(graph)),
                (b"SAPT", esm.zbytes("Neutral")),
            ],
        )
    )
    w.write(str(bundle_dir / handy_codsworth.HANDY_TEMPLATE_PLUGIN), compress=False)


class PrewarScenesAndHandyTests(unittest.TestCase):
    def test_standin_beats_and_skip_prewar_preservation(self) -> None:
        self.assertEqual([b.code for b in s1_spec.STANDIN_BEATS], ["a", "b", "c", "d", "e"])
        self.assertTrue(all(b.status_label == "animation stand-in" for b in s1_spec.STANDIN_BEATS))

        # Fixed IDs must stay cleanly below PREWAR_VOICE_START_ID (0x900) and distinct
        fids = [fid for _sig, fid in s1_spec.PREWAR_FORMS.values()]
        self.assertEqual(len(fids), len(set(fids)))
        self.assertTrue(all(0x000800 <= fid < s1_spec.PREWAR_VOICE_START_ID for fid in fids))

        # Verify actual repo start_places.json preserves fo4_vault111 (Skip Pre-War)
        sp_path = ROOT / "src" / "fo4sf" / "core" / "start_places.json"
        sp_doc = json.loads(sp_path.read_text(encoding="utf-8"))
        s1_spec.validate_start_places_preserves_skip_prewar(sp_doc)

        # Verify FO4SF_NewGame STAGE_CONTRACT keeps Stage 20 + Vault 111 / S2 chain intact
        s1_spec.validate_stage20_handoff_contract(make_newgame.STAGE_CONTRACT)

    def test_mq101_fuz_duration_parser_and_tile_spec(self) -> None:
        fmt_payload = struct.pack("<HHIIIHH", 0x0161, 1, 22050, 4000, 1, 16, 0)
        fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_payload)) + fmt_payload
        data_chunk = b"data" + struct.pack("<I", 8000) + (b"\x00" * 8000)
        xwma = b"RIFF" + struct.pack("<I", 4 + len(fmt_chunk) + len(data_chunk)) + b"XWMA" + fmt_chunk + data_chunk
        fuz = b"FUZE" + struct.pack("<II", 1, 4) + b"LIPS" + xwma
        self.assertEqual(mq101_census.split_fuz_xwma(fuz), xwma)
        self.assertAlmostEqual(mq101_census.parse_fuz_duration_s(fuz), 2.0, places=5)

        spec = build_prewar_quest.build_tile_local_spec()
        self.assertIn("FO4SF_PrewarHouseSpawnMarker", spec["markers"])
        self.assertIn("FO4SF_PrewarVaultArrivalMarker", spec["markers"])
        hx, hy, _hz, _hr = spec["markers"]["FO4SF_PrewarHouseSpawnMarker"]
        self.assertTrue(-200.0 <= hx < 200.0 and -200.0 <= hy < 200.0)

    def test_synthetic_handy_bundle_inspect_and_no_overwrite_copy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / "E2_synth"
            _make_synthetic_handy_bundle(bundle)
            dest = root / "OutData"

            spec, copied = handy_codsworth.copy_handy_assets(str(bundle), str(dest))
            self.assertEqual(spec.subgraph_count, 1)
            self.assertTrue((dest / "meshes" / "fo4sf" / "actors" / "handy" / "handy.nif").is_file())
            self.assertTrue(
                (dest / "meshes" / "AnimTextData" / "GeneratedSubgraphData" / "fo4sf_prewarcodsworthrace.txt").is_file()
            )
            self.assertGreaterEqual(len(copied), 7)

            with self.assertRaises(FileExistsError):
                handy_codsworth.copy_handy_assets(str(bundle), str(dest))

    def test_dotnet_prewar_selftest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            proj = ROOT / "dotnet" / "Prewar" / "Prewar.csproj"
            res = subprocess.run(
                ["dotnet", "run", "--project", str(proj), "-c", "Release", "--", "selftest", td],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stdout + "\n" + res.stderr)
            self.assertIn("selftest ok", res.stdout)

    def test_optional_live_e2_handy_inspect_and_papyrus_compile(self) -> None:
        e2_dir = Path(r"D:\FO4SF-Owner-Tests\robot-anim\E2")
        if e2_dir.is_dir():
            spec = handy_codsworth.inspect_handy_bundle(str(e2_dir))
            self.assertGreaterEqual(spec.subgraph_count, 1)
            self.assertIn("meshes/fo4sf/actors/handy/handy.nif", {v.lower() for v in spec.files_to_copy.values()})

        compiler = Path(build_prewar_quest.DEFAULT_PAPYRUS_COMPILER)
        res_zip = Path(build_prewar_quest.DEFAULT_CONTENT_RES)
        if compiler.is_file() and res_zip.is_file():
            with tempfile.TemporaryDirectory() as td:
                pex_list = build_prewar_quest.compile_prewar_scripts(td)
                self.assertEqual(len(pex_list), 2)
                for pex in pex_list:
                    self.assertTrue(os.path.isfile(pex), f"Missing compiled {pex}")


if __name__ == "__main__":
    unittest.main()
