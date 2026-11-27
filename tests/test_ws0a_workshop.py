"""Offline regressions for Round 14 WS0a (`gemini/r14-workshop`):
- Opening-toast candidate switch (GLOB 0x858 default OFF, Sanctuary01 BlockActivation + delayed StartWorkshop)
- C.A.M.P. kit leak gate (COBJ 0x843 + FO4SF_WorkshopCoreQuest drop handler, 'until owner Q6')
- Zero skill gates (RQPK), zero research CTDA (874), zero Starfield workbench keywords on bench-offered recipes
- Zero LCTN/STDT/PNDT overrides; vanilla overrides strictly FLST 0x058606 and 0x1A5507
- Existing FormIDs preserved, new FormIDs start at 0x858, zero probe records in player plugins, card/doc completeness
"""
from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DOTNET_ENABLED = shutil.which("dotnet") is not None

WORKSHOP_CS = ROOT / "dotnet" / "WorkshopCore" / "Program.cs"
WORKSHOP_PSC = ROOT / "scripts" / "workshop" / "FO4SF_WorkshopCoreQuest.psc"
SANCTUARY_PSC = ROOT / "scripts" / "mission" / "FO4SF_Sanctuary01Quest.psc"
CARD_DOC = ROOT / "docs" / "testing" / "workshop-ws0a-card.md"
DECISION_DOC = ROOT / "docs" / "workshop" / "ws0a-tab-and-bench-decision.md"
DESIGN_DOC = ROOT / "docs" / "workshop" / "ws0a-category-and-layering-design.md"
FORMULA_DOC = ROOT / "docs" / "workshop" / "ws0a-formula-sheet.md"
PIPBOY_C4_DOC = ROOT / "docs" / "ui" / "pipboy-c4-fixes.md"
FO4_INTERNALS_DOC = ROOT / "docs" / "research" / "framework" / "engine-mechanics-notes" / "fo4-systems-internals.md"
ECONOMY_DOC = ROOT / "docs" / "research" / "framework" / "engine-mechanics-notes" / "workshop-items-economy.md"


def _iter_esm_records(esm_bytes: bytes):
    n = len(esm_bytes)

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
                if sig != "TES4":
                    yield sig, fid, flags, esm_bytes[off + 24 : off + 24 + size]
                off += 24 + size

    yield from walk(0, n)


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


class Ws0aContractsTests(unittest.TestCase):
    def test_camp_kit_gate_until_owner_q6_in_csharp_and_papyrus(self) -> None:
        cs = WORKSHOP_CS.read_text(encoding="utf-8")
        psc = WORKSHOP_PSC.read_text(encoding="utf-8")
        self.assertIn("until owner Q6", cs)
        self.assertIn("CobjFo4PortableCampKitId", cs)
        self.assertIn("until owner Q6", psc)
        m = re.search(r"if campKit != None && baseId == campKit\.GetFormID\(\).*?elseif packToken", psc, re.S)
        self.assertIsNotNone(m)
        self.assertIn("TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0", m.group(0))

    def test_opening_toast_switch_0x858_default_off_in_sanctuary01(self) -> None:
        psc = SANCTUARY_PSC.read_text(encoding="utf-8")
        self.assertIn("bool Property EnableWorkshopStartViaScript = False Auto", psc)
        self.assertIn("int StartViaScriptGlobId = 0x000858", psc)
        self.assertIn("Function SyncBenchActivationMode()", psc)
        self.assertIn("boundBench.BlockActivation(True, False)", psc)
        self.assertIn("boundBench.StartWorkshop(True)", psc)
        self.assertIn("RegisterForRemoteEvent(boundBench, \"OnActivate\")", psc)
        self.assertIn("RegisterForRemoteEvent(boundBench, \"OnWorkshopMode\")", psc)

    def test_docs_decision_formula_sheet_and_card_rows_complete(self) -> None:
        for doc in (CARD_DOC, DECISION_DOC, DESIGN_DOC, FORMULA_DOC):
            self.assertTrue(doc.is_file(), f"missing {doc}")
        c4 = PIPBOY_C4_DOC.read_text(encoding="utf-8")
        self.assertIn("MODIFY MODE", c4)
        self.assertIn("kBlockingMenuCooldownMs", c4)

        internals = FO4_INTERNALS_DOC.read_text(encoding="utf-8")
        for val in ("0.02", "0.001", "0.01", "0.005", "7.0", "CheckForAttack", "AllowAttacks"):
            self.assertIn(val, internals)

        econ = ECONOMY_DOC.read_text(encoding="utf-8")
        for qid in ("B1", "B3", "B7", "B9", "S3", "T1", "T2", "T3"):
            self.assertRegex(econ, re.compile(rf"^\| {qid} \| .*?(VERIFIED|ANSWERED|Staged)", re.M), msg=qid)

        formulas = FORMULA_DOC.read_text(encoding="utf-8")
        self.assertIn("Base.zip", formulas)
        self.assertIn("7,854", formulas)

        card = CARD_DOC.read_text(encoding="utf-8")
        self.assertIn("stand-in screen", card)
        for row in ("WS0-1", "WS0-5", "WS0-6", "WS0-8", "WS0-9", "WS0-10", "WS0-11", "WS0-12", "WS0-14"):
            self.assertIn(f"**{row}**", card)
            line = next(l for l in card.splitlines() if f"**{row}**" in l)
            self.assertTrue("REACHABLE" in line or "TEST-STATION" in line, row)

    def test_zero_census_outputs_or_game_plugins_in_repo(self) -> None:
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True)
        files = r.stdout.splitlines()
        for f in files:
            low = f.lower()
            self.assertFalse(low.endswith(".esm") or low.endswith(".esp") or low.endswith(".esl"), f)
            if low.endswith(".json"):
                self.assertNotIn("fo4_census", low)
                self.assertNotIn("fo4-census", low)
                self.assertNotIn("private-fo4-census", low)

    def test_no_probe_records_in_player_plugins_and_29_core_bench_base_invariant(self) -> None:
        self.assertNotIn("FO4SF_WS0aProbeQuest", WORKSHOP_CS.read_text(encoding="utf-8"))
        self.assertNotIn("FO4SF_P18WorkbenchKeyword", WORKSHOP_CS.read_text(encoding="utf-8"))
        make_core = ROOT / "scripts" / "terrain" / "make_core64c.py"
        if make_core.is_file():
            txt = make_core.read_text(encoding="utf-8")
            self.assertIn("Starfield.esm", txt)
            self.assertIn("master", txt.lower())

    @unittest.skipUnless(DOTNET_ENABLED, "dotnet SDK required")
    def test_binary_workshop_esm_gates_overrides_formids_and_zero_skill_research_gates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ws0a-bin-") as tmp:
            t = Path(tmp)
            sf_dir = t / "sf"
            out_dir = t / "out"
            r1 = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "WorkshopCore"), "--", "fixture", str(sf_dir), "--mode", "full"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
            r2 = subprocess.run(
                ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(ROOT / "dotnet" / "WorkshopCore"), "--", "build", str(sf_dir / "Starfield.esm"), str(out_dir)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

            esm_bytes = (out_dir / "FO4SFWorkshop.esm").read_bytes()
            sf_workbench_kws = {0x0AA209, 0x102158, 0x102152, 0x054BA7}
            foreign_fids = []
            own_lids = []
            forbidden_types = {"LCTN", "STDT", "PNDT"}

            for rtype, fid, _flags, pay in _iter_esm_records(esm_bytes):
                self.assertNotIn(rtype, forbidden_types)
                subs = list(_iter_subs(pay))
                if (fid >> 24) == 0:
                    foreign_fids.append((rtype, fid))
                else:
                    own_lids.append(fid & 0x00FFFFFF)
                if rtype == "COBJ":
                    tags = [k for k, _ in subs]
                    self.assertNotIn("RQPK", tags, f"COBJ 0x{fid:08X} must have 0 RQPK perk gates")
                    for k, v in subs:
                        if k == "CTDA" and len(v) >= 12:
                            # CTDA function index sits at bytes 8..10 (uint16)
                            func_idx = struct.unpack_from("<H", v, 8)[0]
                            self.assertNotEqual(func_idx, 874, f"COBJ 0x{fid:08X} must not use research CTDA 874")
                    if (fid & 0x00FFFFFF) in (0x00084E, 0x00084F, 0x000850):
                        bnam = struct.unpack("<I", dict(subs)["BNAM"])[0] & 0x00FFFFFF
                        self.assertNotIn(bnam, sf_workbench_kws)
                        self.assertEqual(bnam, 0x000848)
                if (fid & 0x00FFFFFF) == 0x000858 and rtype == "GLOB":
                    self.assertAlmostEqual(struct.unpack("<f", dict(subs)["FLTV"])[0], 0.0, places=4)
                if (fid & 0x00FFFFFF) == 0x000843 and rtype == "COBJ":
                    ctdas = [v for k, v in subs if k == "CTDA"]
                    self.assertEqual(len(ctdas), 1, "COBJ 0x843 must carry TestMode gate")

            self.assertEqual(sorted(fid for _, fid in foreign_fids), [0x058606, 0x1A5507])
            self.assertGreaterEqual(min(own_lids), 0x800)
            self.assertIn(0x858, own_lids)
            self.assertEqual(max(own_lids), 0x858)


if __name__ == "__main__":
    unittest.main()
