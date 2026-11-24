#!/usr/bin/env python3
"""Offline tests for Round 11 Probe P2 (Power Armor frame, T-45, Fusion Core gate & Vertibird Minigun)."""
from __future__ import annotations

import json
import pathlib
import struct
import sys
import tempfile
import unittest
from typing import List

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PROBES_DIR = ROOT / "scripts" / "probes"
POWERARMOR_DIR = ROOT / "scripts" / "powerarmor"
TESTING_DIR = ROOT / "scripts" / "testing"
for _p in (str(SRC), str(PROBES_DIR), str(TESTING_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probe_common  # noqa: E402
import r12_card_validator  # noqa: E402
import stage_r11_p2_powerarmor as p2  # noqa: E402
from fo4sf.core.cross_plugin_check import build_writer_catalog, parse_binary_vmad_properties  # noqa: E402
from fo4sf.planet.esm import PERSISTENT, Plugin, parse_subrecords  # noqa: E402


class FakeSystem:
    def __init__(self, pids_list: List[int] | None = None) -> None:
        self._pids = list(pids_list or [])

    def pids(self, exe: str) -> List[int]:
        return list(self._pids)


def _minimal_tes4(flags: int = 0) -> bytes:
    return probe_common.build_tes4([], 0, 0x800, flags=flags)


def _make_min_cv_esm(wt: float = 0.009) -> bytes:
    ag = probe_common.rec_bytes(b"AVIF", 0x01000815, [(b"EDID", b"FO4SF_Special_Agility\x00")])
    am = probe_common.rec_bytes(
        b"AMMO", 0x0100089F, [(b"EDID", b"FO4_Ammo5mm\x00"), (b"DATA", struct.pack("<If", 1, wt))]
    )
    wp = probe_common.rec_bytes(
        b"WEAP",
        0x010008A0,
        [(b"EDID", b"FO4_Minigun\x00"), (b"MOD4", b"fo4sf\\weapons\\minigun\\fo4_minigun.nif\x00")],
    )
    body = (
        probe_common.grup_bytes(b"AVIF", 0, ag)
        + probe_common.grup_bytes(b"AMMO", 0, am)
        + probe_common.grup_bytes(b"WEAP", 0, wp)
    )
    return probe_common.build_esm(("Starfield.esm",), body, 0x8A1, flags=1)


def _make_min_pa_esm(core_modl: bytes = b"fo4sf\\powerarmor\\fusioncore.nif\x00", leak_sub=None) -> bytes:
    rc = probe_common.rec_bytes(
        b"RACE",
        0x02000802,
        [(b"EDID", b"FO4SF_PowerArmorRace\x00"), (b"NAM4", struct.pack("<I", p2.EXPECTED_METAL_MATT_ID))],
    )
    pk = probe_common.rec_bytes(b"PERK", 0x0200081E, [(b"EDID", b"FO4SF_PANoFallDamagePerk\x00")])
    mc = probe_common.rec_bytes(b"MISC", 0x02000809, [(b"EDID", b"FO4SF_FusionCore\x00"), (b"MODL", core_modl)])
    armo_subs = [(b"EDID", b"FO4SF_PATorso\x00"), (b"FULL", b"T-45 Chest Piece\x00")]
    if leak_sub is not None:
        armo_subs.append(leak_sub)
    ar = probe_common.rec_bytes(b"ARMO", 0x02000817, armo_subs)
    body = (
        probe_common.grup_bytes(b"RACE", 0, rc)
        + probe_common.grup_bytes(b"PERK", 0, pk)
        + probe_common.grup_bytes(b"MISC", 0, mc)
        + probe_common.grup_bytes(b"ARMO", 0, ar)
    )
    return probe_common.build_esm(("Starfield.esm", "FO4SFCoreValues.esm"), body, 0x840, flags=1)


class ProbeP2Tests(unittest.TestCase):
    def test_p2_esm_structure_cleanliness_and_zero_prefix(self) -> None:
        raw = p2.build_p2_powerarmor_esm()
        with tempfile.TemporaryDirectory() as td:
            td_p = pathlib.Path(td)
            esm_p = td_p / p2.PROBE_PLUGIN
            esm_p.write_bytes(raw)

            with Plugin(str(esm_p)) as plg:
                self.assertEqual(plg.masters, ["Starfield.esm", "FO4SFCoreValues.esm", "FO4SFPowerArmor.esm"])
                self.assertNotIn("WRLD", plg.groups)
                self.assertNotIn("PNDT", plg.groups)

            recs = list(probe_common.walk_esm_records(raw))
            sigs = [sig for sig, _fid, _fl, _d in recs]
            self.assertNotIn("WRLD", sigs)
            self.assertNotIn("PNDT", sigs)
            self.assertEqual(sigs.count("CELL"), 1)
            self.assertEqual(sigs.count("ACTI"), 2)
            self.assertEqual(sigs.count("REFR"), 5)
            self.assertEqual(sigs.count("QUST"), 1)

            actis = {}
            for sig, fid, fl, data in recs:
                subs = dict(parse_subrecords(data))
                if b"FULL" in subs:
                    full = subs[b"FULL"].rstrip(b"\x00").decode("latin-1")
                    self.assertFalse(full.startswith("FO4SF "), f"Unexpected FO4SF prefix on {sig} 0x{fid:08X}: {full!r}")
                if sig == "ACTI":
                    actis[fid & 0xFFFFFF] = subs
                elif sig == "REFR":
                    self.assertTrue(fl & PERSISTENT, f"REFR 0x{fid:08X} must be PERSISTENT")
                elif sig == "QUST":
                    dnam = struct.unpack("<III", subs[b"DNAM"])
                    self.assertEqual(dnam[0], p2.QUST_DNAM_START_GAME_AND_REPEAT)
                    stages = [struct.unpack("<I", v)[0] for t, v in parse_subrecords(data) if t == b"INDX"]
                    self.assertEqual(stages, [10, 20, 30, 40, 50, 60, 70, 75, 80])
                    vprops = parse_binary_vmad_properties(
                        subs[b"VMAD"],
                        ["Starfield.esm", "FO4SFCoreValues.esm", "FO4SFPowerArmor.esm"],
                        p2.PROBE_PLUGIN,
                        "FO4SF_R11P2Quest",
                    )
                    by_name = {vp.prop_name: vp for vp in vprops}
                    self.assertEqual(tuple(by_name["RoofFrameRef"].object_refs), ((-1, p2.PROBE_PLUGIN, 0x000810),))
                    self.assertEqual(tuple(by_name["RoofMinigunRef"].object_refs), ((-1, p2.PROBE_PLUGIN, 0x000811),))
                    self.assertEqual(tuple(by_name["RoofSpareCoreRef"].object_refs), ((-1, p2.PROBE_PLUGIN, 0x000812),))
                    self.assertEqual(tuple(by_name["RoofExitRef"].object_refs), ((-1, p2.PROBE_PLUGIN, 0x000813),))
                    self.assertEqual(tuple(by_name["StreetExitRef"].object_refs), ((-1, p2.PROBE_PLUGIN, 0x000814),))
                    self.assertEqual(tuple(by_name["HealthAV"].object_refs), ((-1, "Starfield.esm", 0x0002D4),))

            self.assertEqual(actis[0x801][b"FULL"].rstrip(b"\x00"), b"Vertibird Minigun")
            self.assertEqual(actis[0x801][b"MODL"].rstrip(b"\x00"), b"fo4sf\\powerarmor\\vertibirdminigun.nif")
            self.assertEqual(actis[0x803][b"FULL"].rstrip(b"\x00"), b"Power Armor Exit Terminal")
            self.assertEqual(actis[0x803][b"MODL"].rstrip(b"\x00"), b"fo4sf\\powerarmor\\pa_exit_terminal.nif")
            self.assertNotIn("marker", actis[0x803][b"MODL"].decode("latin-1").lower())

            errs = probe_common.scan_plugin_cleanliness([esm_p], raise_on_error=True)
            self.assertEqual(errs, [])

    def test_p2_batches_p3_clean_roof_arrival_and_control_drop(self) -> None:
        self.assertEqual(p2.MUSEUM_ROOF_ARRIVAL_POS, (-1990.58, -1724.19, 97.56))
        self.assertNotEqual(round(p2.MUSEUM_ROOF_ARRIVAL_POS[0], 2), -2008.49)
        with tempfile.TemporaryDirectory() as td:
            bat_dir = pathlib.Path(td) / "bat"
            bat_dir.mkdir()
            batches = p2.render_p2_batches()
            self.assertEqual(
                set(batches),
                {"p2h1.txt", "p2h2.txt", "p2r.txt", "p2f.txt", "p2g.txt", "p2w.txt", "p2d.txt", "p2c.txt", "p2x.txt", "p2s.txt", "p2q.txt"},
            )
            written = []
            for name, body in batches.items():
                self.assertFalse(any(ch in name.lower().removesuffix(".txt") for ch in "mnv"), name)
                self.assertNotIn("07000820", body)
                p = bat_dir / name
                p.write_text(body, encoding="utf-8")
                written.append(p)
            errs = probe_common.validate_batches_and_hops(
                batch_files=written,
                anchors=p2.P2_ANCHORS,
                hops=p2.P2_HOPS,
                max_axis_m=200.0,
                interior_mode=False,
                raise_on_error=True,
            )
            self.assertEqual(errs, [])

            # Armored drop p2d and unarmored control drop p2c must target the exact same coordinates
            self.assertIn("SetStage XX000820 75", batches["p2d.txt"])
            self.assertIn("SetStage XX000820 80", batches["p2c.txt"])
            drop_xyz = (
                f"player.setpos x {p2.STREET_DROP_OVER_LEDGE_POS[0]:.2f}\n"
                f"player.setpos y {p2.STREET_DROP_OVER_LEDGE_POS[1]:.2f}\n"
                f"player.setpos z {p2.STREET_DROP_OVER_LEDGE_POS[2]:.2f}\n"
            )
            self.assertIn(drop_xyz, batches["p2d.txt"])
            self.assertIn(drop_xyz, batches["p2c.txt"])
            self.assertIn("-1990.58", batches["p2r.txt"])
            self.assertIn("-1724.19", batches["p2r.txt"])
            self.assertIn("97.56", batches["p2r.txt"])

            chain = [
                ("sanctuary", p2.SANCTUARY_POS),
                ("p2h1", p2.MID_HOP_1_POS),
                ("p2h2", p2.CONCORD_FRONT_POS),
                ("p2r", p2.MUSEUM_ROOF_ARRIVAL_POS),
                ("p2w", p2.ROOF_VERTIBIRD_PERCH_POS),
            ]
            for (n0, p0), (n1, p1_pos) in zip(chain, chain[1:]):
                dx = max(abs(a - b) for a, b in zip(p0, p1_pos))
                self.assertLess(dx, 200.0, f"Chain hop {n0}->{n1} exceeded 200m: {dx:.2f}")

    def test_p2_live_prefix_stamping_and_no_card_mutation_on_install(self) -> None:
        card_p = ROOT / "docs" / "testing" / "round11-p2-powerarmor-card.md"
        card_sha_before = probe_common.sha256_file(card_p)

        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            sf = base / "Starfield"
            st = base / "stage"
            for sub in (st / "core", st / "assets" / "meshes" / "fo4sf" / "powerarmor", st / "assets" / "meshes" / "fo4sf" / "weapons" / "minigun", st / "exp" / "Data" / "Scripts", st / "sfse" / "SFSE" / "Plugins", st / "bat", sf / "Data" / "Scripts"):
                sub.mkdir(parents=True, exist_ok=True)

            # Populate minimal valid staged artifacts so verify_staged passes cleanly via mocked BA2/NIF checks
            cv_bytes = _make_min_cv_esm(0.009)
            pa_bytes = _make_min_pa_esm()
            (sf / "Data" / "FO4SFCoreValues.esm").write_bytes(b"ORIG-CV")
            (sf / "Data" / "FO4SFPowerArmor.esm").write_bytes(b"ORIG-PA")
            (sf / "Data" / "Scripts" / "FO4SF_PowerArmorCoreQuest.pex").write_bytes(b"ORIG-PEX")

            # Implicit Starfield + 12 active full plugins + 1 light plugin (0x200) -> P2 lands at slot 0x0E
            implicit_0 = sf / "Data" / "Starfield.esm"
            implicit_0.write_bytes(_minimal_tes4(0))
            full_names = [
                "FO4Port.esm",
                "FO4TerrainCore.esm",
                "FO4TerrainCore_Mars.esm",
                "FO4SFCoreValues.esm",
                "FO4SFPowerArmor.esm",
                "FO4SFMission.esm",
                "FO4SFNewGame.esm",
                "FO4SFWorkshop.esm",
                "FO4SFFortHagen.esm",
                "FO4SFPipboyProbe.esm",
                "FO4SFPipboyTravel.esm",
                "FO4SFVaultGearDoor.esm",
                "FO4SFExitLift.esm",
            ]
            for nm in full_names:
                (sf / "Data" / nm).write_bytes(_minimal_tes4(0))
            (sf / "Data" / "LightSkip.esm").write_bytes(_minimal_tes4(0x200))
            orig_cv = (sf / "Data" / "FO4SFCoreValues.esm").read_bytes()
            orig_pa = (sf / "Data" / "FO4SFPowerArmor.esm").read_bytes()
            orig_pex = (sf / "Data" / "Scripts" / "FO4SF_PowerArmorCoreQuest.pex").read_bytes()

            (st / "core" / "FO4SFCoreValues.esm").write_bytes(cv_bytes)
            (st / "core" / "FO4SFPowerArmor.esm").write_bytes(pa_bytes)
            (st / "exp" / p2.PROBE_PLUGIN).write_bytes(p2.build_p2_powerarmor_esm())
            (st / "exp" / p2.PROBE_MAIN_BA2).write_bytes(b"MAIN-BA2")
            (st / "exp" / p2.PROBE_TEX_BA2).write_bytes(b"TEX-BA2")
            (st / "exp" / "Data" / "Scripts" / "FO4SF_PowerArmorCoreQuest.pex").write_bytes(b"NEW-PEX")
            (st / "exp" / "Data" / "Scripts" / "FO4SF_R11P2Quest.pex").write_bytes(b"P2-PEX")
            for name, body in p2.render_p2_batches().items():
                (st / "bat" / name).write_text(body, encoding="utf-8")

            plg_txt = sf / "Plugins.txt"
            plg_txt.write_text(
                "\n".join([*(f"*{n}" for n in full_names), "*LightSkip.esm"]) + "\n",
                encoding="utf-8",
            )

            from unittest import mock
            with mock.patch.object(p2, "verify_staged", return_value={"verified": True}):
                res = p2.install_probe_p2(
                    stage_dir=st,
                    starfield_dir=sf,
                    plugins_txt=plg_txt,
                    version_tag="p2-v2",
                    min_free_gb=0.0,
                    system=FakeSystem(),
                )

            # Starfield.esm (0x00) + 13 full plugins (0x01..0x0D) + 1 light skipped -> 0x0E!
            self.assertEqual(res["live_prefix"], "0x0E")
            self.assertEqual(res["quest_form_id"], "0E000820")
            self.assertEqual(res["version_tag"], "p2-v2")
            for bat_name in p2.STAMPED_SETSTAGE_BATCHES:
                txt = (sf / bat_name).read_text(encoding="utf-8")
                self.assertIn("0E000820", txt, f"{bat_name} missing live stamped prefix")
                self.assertNotIn("XX000820", txt)
                self.assertNotIn("07000820", txt)

            rcpt = json.loads(probe_common.receipt_path(sf, p2.PROBE_ID).read_text(encoding="utf-8"))
            self.assertEqual(rcpt["live_prefix"], "0x0E")
            self.assertEqual(rcpt["quest_form_id"], "0E000820")
            self.assertEqual(rcpt["version_tag"], "p2-v2")
            self.assertIsNone(rcpt["card_stamped"])
            self.assertEqual(probe_common.sha256_file(card_p), card_sha_before)

            probe_common.uninstall_probe(probe_id=p2.PROBE_ID, starfield_dir=sf, system=FakeSystem())
            self.assertEqual((sf / "Data" / "FO4SFCoreValues.esm").read_bytes(), orig_cv)
            self.assertEqual((sf / "Data" / "FO4SFPowerArmor.esm").read_bytes(), orig_pa)
            self.assertEqual((sf / "Data" / "Scripts" / "FO4SF_PowerArmorCoreQuest.pex").read_bytes(), orig_pex)
            self.assertFalse((sf / "Data" / p2.PROBE_PLUGIN).exists())
            self.assertNotIn(p2.PROBE_PLUGIN, plg_txt.read_text(encoding="utf-8"))

    def test_p2_quest_script_contract_f1_f2_f3_f5_f8(self) -> None:
        psc = (PROBES_DIR / "FO4SF_R11P2Quest.psc").read_text(encoding="utf-8")
        pa_psc = (POWERARMOR_DIR / "FO4SF_PowerArmorCoreQuest.psc").read_text(encoding="utf-8")
        for token in (
            "Scriptname FO4SF_R11P2Quest extends Quest",
            "0x0008A0",
            "0x00089F",
            "0x000805",
            "0x000809",
            "0x00081E",
            "0x008913",
            "0x005119",
            "FO4TerrainCore.esm",
            "DisableNoWait(false)",
            "terrain_dupes_disabled",
            "-1990.58",
            "-1724.19",
            "97.56",
            "RoofExitRef",
            "StreetExitRef",
            "p2_inworld_exit_activate",
            "OnLocationChange",
            "OnPlayerLoadGame",
            "HealthAV",
            "hp_before=",
            "hp_after=",
            "auiStageID == 75",
            "auiStageID == 80",
            "AddItem(ammoForm, 1200, false)",
            'pa.EnterFrame(RoofFrameRef, "p2_roof_frame_activate")',
            'pa.ExitFrame("p2_stage30")',
        ):
            self.assertIn(token, psc)
        self.assertNotIn("SyncTicks < 90", psc)

        for token in (
            "0x008913",
            "0x005119",
            "FO4TerrainCore.esm",
            "DisableNoWait(false)",
            "terrain_dupes_disabled",
            "hp_before=",
            "hp_after=",
        ):
            self.assertIn(token, pa_psc)

    def test_p2_f9_shared_helpers_task8_no_hardcoded_paths_and_card_valid(self) -> None:
        stager_src = (PROBES_DIR / "stage_r11_p2_powerarmor.py").read_text(encoding="utf-8")
        for forbidden_fn in ("def _pack_subs", "def _rec_bytes", "def _grup_bytes", "def _walk_esm_records", "DEFAULT_SLOT_PREFIX", "07000820"):
            self.assertNotIn(forbidden_fn, stager_src)
        for forbidden_path in ("FO4SF-Owner-Tests", "SteamLibrary", "FO4SF-Progress-Archive"):
            self.assertNotIn(forbidden_path, stager_src)

        card_p = ROOT / "docs" / "testing" / "round11-p2-powerarmor-card.md"
        card_txt = card_p.read_text(encoding="utf-8")
        self.assertEqual(r12_card_validator.validate_r12_card_file(card_p), [])
        self.assertNotIn("| `pending` |", card_txt.lower())
        self.assertIn("`P2-07`", card_txt)
        self.assertIn("`P2-08`", card_txt)
        self.assertIn("candidate-2g-fix4", card_txt)
        self.assertIn("`built in`", card_txt)
        self.assertIn("`not applicable`", card_txt)
        self.assertIn("`gated", card_txt)

    def test_p2_cross_plugin_check_registers_p2_and_terrain_forms(self) -> None:
        catalog, dups = build_writer_catalog(str(ROOT))
        self.assertEqual(dups, [])
        self.assertIn(p2.PROBE_PLUGIN, catalog)
        p2_tbl = catalog[p2.PROBE_PLUGIN]
        for lid, rtype in (
            (0x801, "ACTI"),
            (0x802, "CELL"),
            (0x803, "ACTI"),
            (0x810, "REFR"),
            (0x811, "REFR"),
            (0x812, "REFR"),
            (0x813, "REFR"),
            (0x814, "REFR"),
            (0x820, "QUST"),
        ):
            self.assertEqual(p2_tbl[lid][0], rtype)
        pa_tbl = catalog["FO4SFPowerArmor.esm"]
        self.assertEqual(pa_tbl[0x801][0], "FURN")
        self.assertEqual(pa_tbl[0x81E][0], "PERK")
        tc_tbl = catalog["FO4TerrainCore.esm"]
        self.assertEqual(tc_tbl[0x008913][0], "REFR")
        self.assertEqual(tc_tbl[0x005119][0], "REFR")
        cv_tbl = catalog["FO4SFCoreValues.esm"]
        self.assertEqual(cv_tbl[0x00089F], ("AMMO", "FO4_Ammo5mm"))
        self.assertEqual(cv_tbl[0x0008A0], ("WEAP", "FO4_Minigun"))

    def test_p2_finding1_to_3_validators(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            cv_ok = base / "cv_ok.esm"
            cv_bad = base / "cv_bad.esm"
            cv_ok.write_bytes(_make_min_cv_esm(0.009))
            cv_bad.write_bytes(_make_min_cv_esm(0.0))
            p2._verify_core_values_has_minigun_and_5mm(cv_ok)
            with self.assertRaises(p2.ProbeP2Error):
                p2._verify_core_values_has_minigun_and_5mm(cv_bad)

            p2_esm = base / p2.PROBE_PLUGIN
            p2_esm.write_bytes(p2.build_p2_powerarmor_esm())
            pa_ok = base / "pa_ok.esm"
            pa_bad_core = base / "pa_bad_core.esm"
            pa_bad_inrd = base / "pa_bad_inrd.esm"
            pa_ok.write_bytes(_make_min_pa_esm(b"fo4sf\\powerarmor\\fusioncore.nif\x00"))
            pa_bad_core.write_bytes(_make_min_pa_esm(b"SetDressing\\manufactured_goods\\Mfg_Positron_Battery.nif\x00"))
            pa_bad_inrd.write_bytes(_make_min_pa_esm(b"fo4sf\\powerarmor\\fusioncore.nif\x00", (b"INRD", struct.pack("<I", 0x00184BC1))))

            p2._verify_p2_esms(pa_ok, p2_esm)
            with self.assertRaises(p2.ProbeP2Error):
                p2._verify_p2_esms(pa_bad_core, p2_esm)
            with self.assertRaises(p2.ProbeP2Error):
                p2._verify_p2_esms(pa_bad_inrd, p2_esm)

    def test_stage_probe_refuses_when_starfield_running(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            with self.assertRaises(probe_common.ProbePreflightError):
                p2.stage_probe(
                    stage_dir=base / "out",
                    fo4_data=base,
                    core_values_src=base / "cv.esm",
                    weapons_assets_dir=base,
                    tested_pipboy_dll=base / "FO4SFPipboyMenu.dll",
                    starfield_dir=base,
                    system=FakeSystem([39276]),
                )


if __name__ == "__main__":
    unittest.main()
