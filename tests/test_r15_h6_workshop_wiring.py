"""Round 15 Wave B Item H6 unit tests (Sanctuary workshop wiring from settlement_rules.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "scripts" / "terrain")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import vmad_patch  # noqa: E402
from tests.test_exit_arrival import translated_functions  # noqa: E402

SETTLEMENT_RULES_PATH = ROOT / "src" / "fo4sf" / "workshop" / "settlement_rules.json"
WORKSHOP_CS_PATH = ROOT / "dotnet" / "WorkshopCore" / "Program.cs"
WORKSHOP_PSC_PATH = ROOT / "scripts" / "workshop" / "FO4SF_WorkshopCoreQuest.psc"
SANCTUARY_PSC_PATH = ROOT / "scripts" / "mission" / "FO4SF_Sanctuary01Quest.psc"

DOTNET_AVAILABLE = shutil.which("dotnet") is not None


def _iter_esm_records(esm_bytes: bytes):
    def walk(off: int, end: int):
        while off + 24 <= end:
            sig = esm_bytes[off : off + 4].decode("latin1")
            size = struct.unpack_from("<I", esm_bytes, off + 4)[0]
            if sig == "GRUP":
                yield from walk(off + 24, off + size)
                off += size
            else:
                flags = struct.unpack_from("<I", esm_bytes, off + 8)[0]
                fid = struct.unpack_from("<I", esm_bytes, off + 12)[0]
                pay = esm_bytes[off + 24 : off + 24 + size]
                if flags & 0x00040000 and len(pay) >= 4:
                    pay = zlib.decompress(pay[4:])
                if sig != "TES4":
                    yield sig, fid, flags, pay
                off += 24 + size

    yield from walk(0, len(esm_bytes))


def _iter_subs(pay: bytes):
    pos = 0
    big = None
    while pos + 6 <= len(pay):
        sig = pay[pos : pos + 4].decode("latin1")
        ln = struct.unpack_from("<H", pay, pos + 4)[0]
        pos += 6
        if sig == "XXXX" and ln == 4:
            big = struct.unpack_from("<I", pay, pos)[0]
            pos += 4
            continue
        if big is not None:
            ln = big
            big = None
        yield sig, pay[pos : pos + ln]
        pos += ln


def _decode_quest_vmad_scripts(vmad_bytes: bytes) -> list[dict]:
    """Decode scripts and properties from a Starfield QUST VMAD (ignoring trailing quest fragment bytes)."""
    version, fmt, count = struct.unpack_from("<hHH", vmad_bytes, 0)
    assert version in (5, 6) and fmt in (1, 2)
    pos = 6
    scripts = []
    for _ in range(count):
        name, pos = vmad_patch._rstr(vmad_bytes, pos)
        status, nprops = struct.unpack_from("<BH", vmad_bytes, pos)
        pos += 3
        props = []
        for _ in range(nprops):
            pname, pos = vmad_patch._rstr(vmad_bytes, pos)
            ptype, pstatus = struct.unpack_from("<BB", vmad_bytes, pos)
            val, pos = vmad_patch._read_value(vmad_bytes, pos + 2, ptype)
            props.append({"name": pname, "type": ptype, "status": pstatus, "value": val})
        scripts.append({"name": name, "status": status, "properties": props})
    return scripts


class R15H6WorkshopWiringTests(unittest.TestCase):
    def test_w5_w6_rows_marked_not_wired_and_zero_psc_reads_them(self) -> None:
        data = json.loads(SETTLEMENT_RULES_PATH.read_text(encoding="utf-8"))
        attack_rules = data.get("attack_rules", [])
        pop_rules = data.get("population_upgrade_rules", [])
        self.assertGreaterEqual(len(attack_rules), 1)
        self.assertGreaterEqual(len(pop_rules), 3)

        for row in attack_rules:
            self.assertEqual(row.get("status"), "NOT WIRED", row)
            self.assertIs(row.get("wired"), False, row)
            self.assertIs(row.get("enabled_hook"), False, row)

        for row in pop_rules:
            self.assertEqual(row.get("status"), "NOT WIRED", row)
            self.assertIs(row.get("wired"), False, row)

        w5_w6_tokens = (
            "attack_rules",
            "population_upgrade_rules",
            "commonwealth_raider_probe",
            "min_defense_exempt_ratio",
            "cooldown_game_hours",
            "base_chance_pct",
            "attacker_faction",
            "beacon_recruit_cap",
        )
        for psc_path in list((ROOT / "scripts" / "workshop").glob("*.psc")) + [SANCTUARY_PSC_PATH]:
            txt = psc_path.read_text(encoding="utf-8")
            for tok in w5_w6_tokens:
                self.assertNotIn(tok, txt, f"{psc_path.name} unexpectedly references W5/W6 token {tok!r}")

    def test_clean_swap_bench_runtime_hex_removed_and_zero_hardcoded_005c50_in_sanctuary01(self) -> None:
        rules_txt = SETTLEMENT_RULES_PATH.read_text(encoding="utf-8")
        self.assertNotIn("clean_swap_bench_runtime_hex", rules_txt)

        for p in (
            WORKSHOP_CS_PATH,
            WORKSHOP_PSC_PATH,
            SANCTUARY_PSC_PATH,
        ):
            self.assertNotIn("clean_swap_bench_runtime_hex", p.read_text(encoding="utf-8"), p.name)

        sanc_psc = SANCTUARY_PSC_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(sanc_psc, re.compile(r"005C50", re.I))
        self.assertNotRegex(sanc_psc, re.compile(r"\bint\s+BenchRefId\b"))
        self.assertNotRegex(sanc_psc, re.compile(r"\bfloat\s+BindRadius\b"))

        # Behavior check: ResolveSanctuaryBenchPlugin / RefId / BuildRadius read from FO4SFWorkshop.esm quest properties
        compiled = compile(
            translated_functions(
                sanc_psc,
                (
                    "ActiveCorePlugin",
                    "ResolveSanctuaryBenchPlugin",
                    "ResolveSanctuaryBenchRefId",
                    "ResolveSanctuaryBuildRadius",
                ),
                "",
            ),
            str(SANCTUARY_PSC_PATH),
            "exec",
        )
        ws_stub = SimpleNamespace(
            SanctuaryWorkbenchPlugin="CustomCore.esm",
            SanctuaryWorkbenchRefId=0x00ABCD,
            SanctuaryBuildRadiusM=333.5,
        )
        ns = {
            "CorePlugin": "FO4TerrainCore.esm",
            "CoreFallbackPlugin": "FO4TerrainCore_Mars.esm",
            "WorkshopPlugin": "FO4SFWorkshop.esm",
            "WorkshopQuestId": 0x000800,
            "Game": SimpleNamespace(
                IsPluginInstalled=lambda plg: plg in ("FO4SFWorkshop.esm", "FO4TerrainCore.esm"),
                GetFormFromFile=lambda fid, plg: ws_stub if (fid == 0x000800 and plg == "FO4SFWorkshop.esm") else None,
            ),
        }
        exec(compiled, ns)
        self.assertEqual(ns["ResolveSanctuaryBenchPlugin"](), "CustomCore.esm")
        self.assertEqual(ns["ResolveSanctuaryBenchRefId"](), 0x00ABCD)
        self.assertAlmostEqual(ns["ResolveSanctuaryBuildRadius"](), 333.5, places=3)

        # When FO4SFWorkshop.esm is not installed, zero hardcoded 0x005C50 fallback is returned
        ns_no_ws = {
            "CorePlugin": "FO4TerrainCore.esm",
            "CoreFallbackPlugin": "FO4TerrainCore_Mars.esm",
            "WorkshopPlugin": "FO4SFWorkshop.esm",
            "WorkshopQuestId": 0x000800,
            "Game": SimpleNamespace(
                IsPluginInstalled=lambda plg: plg == "FO4TerrainCore.esm",
                GetFormFromFile=lambda fid, plg: None,
            ),
        }
        exec(compiled, ns_no_ws)
        self.assertEqual(ns_no_ws["ResolveSanctuaryBenchRefId"](), 0)
        self.assertEqual(ns_no_ws["ResolveSanctuaryBuildRadius"](), 0.0)

    @unittest.skipUnless(DOTNET_AVAILABLE, "dotnet SDK required")
    def test_temp_settlement_rules_changes_propagate_to_built_vmad_quest_properties(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r15-h6-") as tmp:
            t = Path(tmp)
            sf_dir = t / "sf"
            out_dir = t / "out_custom"
            rules_path = t / "settlement_rules_custom.json"

            custom_rules = json.loads(SETTLEMENT_RULES_PATH.read_text(encoding="utf-8"))
            custom_rules["settlements"][0]["workbench_plugin"] = "FO4TerrainCore_CustomTest.esm"
            custom_rules["settlements"][0]["workbench_ref_id"] = "0x0077AA"
            custom_rules["settlements"][0]["build_radius_m"] = 412.5
            rules_path.write_text(json.dumps(custom_rules, indent=2), encoding="utf-8")

            env = dict(os.environ)
            env.setdefault("DOTNET_ROLL_FORWARD", "Major")
            r_fix = subprocess.run(
                [
                    "dotnet", "run", "-c", "Release",
                    "--project", str(ROOT / "dotnet" / "WorkshopCore"),
                    "--", "fixture", str(sf_dir), "--mode", "full",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_fix.returncode, 0, r_fix.stdout + r_fix.stderr)

            r_build = subprocess.run(
                [
                    "dotnet", "run", "--no-build", "-c", "Release",
                    "--project", str(ROOT / "dotnet" / "WorkshopCore"),
                    "--", "build", str(sf_dir / "Starfield.esm"), str(out_dir),
                    "--settlement-rules", str(rules_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_build.returncode, 0, r_build.stdout + r_build.stderr)

            r_check = subprocess.run(
                [
                    "dotnet", "run", "--no-build", "-c", "Release",
                    "--project", str(ROOT / "dotnet" / "WorkshopCore"),
                    "--", "check", str(out_dir / "FO4SFWorkshop.esm"), str(sf_dir / "Starfield.esm"),
                    "--settlement-rules", str(rules_path),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_check.returncode, 0, r_check.stdout + r_check.stderr)

            esm_bytes = (out_dir / "FO4SFWorkshop.esm").read_bytes()
            quest_vmad = None
            acti_prps = None
            for rtype, fid, _flags, pay in _iter_esm_records(esm_bytes):
                lid = fid & 0x00FFFFFF
                if rtype == "QUST" and lid == 0x000800:
                    quest_vmad = dict(_iter_subs(pay))["VMAD"]
                elif rtype == "ACTI" and lid == 0x000849:
                    acti_prps = dict(_iter_subs(pay)).get("PRPS")

            self.assertIsNotNone(quest_vmad, "missing VMAD on QUST 0x000800")
            scripts = _decode_quest_vmad_scripts(quest_vmad)
            self.assertEqual(len(scripts), 1)
            self.assertEqual(scripts[0]["name"], "FO4SF_WorkshopCoreQuest")
            by_name = {p["name"]: p for p in scripts[0]["properties"]}
            self.assertEqual(set(by_name), {
                "TestModeGlobal",
                "SanctuaryWorkbenchPlugin",
                "SanctuaryWorkbenchRefId",
                "SanctuaryBuildRadiusM",
            })
            self.assertEqual(by_name["SanctuaryWorkbenchPlugin"]["type"], vmad_patch.T_STRING)
            self.assertEqual(by_name["SanctuaryWorkbenchPlugin"]["value"], "FO4TerrainCore_CustomTest.esm")
            self.assertEqual(by_name["SanctuaryWorkbenchRefId"]["type"], vmad_patch.T_INT)
            self.assertEqual(by_name["SanctuaryWorkbenchRefId"]["value"], 0x0077AA)
            self.assertEqual(by_name["SanctuaryBuildRadiusM"]["type"], vmad_patch.T_FLOAT)
            self.assertAlmostEqual(by_name["SanctuaryBuildRadiusM"]["value"], 412.5, places=3)

            # ACTI 0x000849 OutpostBuildAreaRadius PRPS also reflects custom build_radius_m
            self.assertIsNotNone(acti_prps)
            self.assertIn(struct.pack("<f", 412.5), acti_prps)


if __name__ == "__main__":
    unittest.main()
