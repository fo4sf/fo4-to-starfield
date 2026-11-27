"""Cross-OS synthetic + live-stage tests for Round 11 Probe P4 (Part 1 — 10mm Pistol ALONE).

Covers:
  1. Pure-Python synthetic Probe P4 staging & verification (`FO4SF_R11P4Pistol.esm` masters,
     `FO4SF_P4_TargetDummyRef` `0xC00` `Persistent|InitiallyDisabled` flag, `GNRL` + `DX10` BA2
     round-trip, and negative tamper refusals).
  2. Rule P3 enforcement (`0` `M`/`N`/`V` characters in batch filenames or typed console commands,
     `0` stripped `FO4SF_` EditorIDs inside `bat/*.txt`, and `< 200 m`/axis exterior hop math).
  3. Reversible `install` / `status` / `uninstall` round-trip proving `.esm` files are NEVER
     hardlinked (`st_nlink == 1`), `FE`/`FD` light/medium masters are skipped during `<XX>000820`
     slot stamping, and pre-probe `FO4SFCoreValues.esm`, `FO4SFNewGame.esm`, and `Plugins.txt`
     SHA-256s are restored bit-for-bit.
  4. Translated execution of `FO4SF_R11P4Quest.psc` (12-round mag counter, 30-HP target spawn,
     hit & kill logging, 0 `XM2311`/`.45` leak check) + BOM/drive-path hygiene.
  5. Optional live verification of `FO4SF_R11_P4_STAGE` when set (skipped cleanly on CI).
"""
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

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
SRC_DIR = REPO_ROOT / "src"
PROBES_DIR = REPO_ROOT / "scripts" / "probes"
WEAPONS_DIR = REPO_ROOT / "scripts" / "weapons"

for _p in (str(REPO_ROOT), str(SRC_DIR), str(PROBES_DIR), str(WEAPONS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_r11_10mm as s10  # noqa: E402
import stage_r11_p4_10mm as p4  # noqa: E402
from fo4sf import nif, sfmesh, sfnif  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.planet.esm import Plugin  # noqa: E402
from tests.test_exit_arrival import Reference, _wrap_pstr_literals, translated_functions  # noqa: E402
from tests.test_r11_10mm_pistol import _build_synthetic_fo4_10mm_part_nifs  # noqa: E402

P4_STAGE_PY = PROBES_DIR / "stage_r11_p4_10mm.py"
P4_QUEST_PSC = PROBES_DIR / "FO4SF_R11P4Quest.psc"
DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")


def _minimal_tes4_esm(flags: int = 0x1, payload: bytes = b"") -> bytes:
    hedr = b"HEDR" + struct.pack("<HfII", 12, 0.96, 0, 0x800) + payload
    return b"TES4" + struct.pack("<IIIIHH", len(hedr), flags, 0, 0, 576, 0) + hedr


def _build_synthetic_assets_dir(root: Path) -> Path:
    assets = root / "syn_assets"
    rec_b, grip_b, mag_b = _build_synthetic_fo4_10mm_part_nifs()
    mat_weap = "materials/fo4sf/weapons/10mmpistol/10mmpistol.mat"
    welded = s10.build_welded_10mm_nif(rec_b, grip_b, mag_b, conv=None, weapon_collision_blob=None, default_material=mat_weap)

    weap_p = assets / s10.WEAP_10MM_REL
    weap_p.parent.mkdir(parents=True, exist_ok=True)
    weap_p.write_bytes(welded.nif_bytes)
    for (d_hex, f_hex), mb in welded.meshes.items():
        mp = assets / "geometries" / d_hex / f"{f_hex}.mesh"
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_bytes(mb)

    # Valid 4x4 DX10 R8G8B8A8_UNORM (dxgi=28) DDS files so DX10 BA2 header reader validates dimensions & dxgi:
    dx10_4x4 = (
        b"DDS "
        + struct.pack("<7I", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8, 4, 4, 16, 0, 1)
        + b"\x00" * 44
        + struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
        + struct.pack("<5I", 0x1000, 0, 0, 0, 0)
        + struct.pack("<5I", 28, 3, 0, 1, 0)
        + (b"\x80" * 64)
    )

    def write_dx10_dds_set(mat_rel: str, tex_prefix: str) -> None:
        dds_rels = [f"textures/{tex_prefix}_{sfx}.dds" for sfx in ("color", "normal", "rough")]
        for dr in dds_rels:
            dp = assets / dr
            dp.parent.mkdir(parents=True, exist_ok=True)
            dp.write_bytes(dx10_4x4)
        mp = assets / mat_rel
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps({"Textures": dds_rels}, indent=2), encoding="utf-8")

    write_dx10_dds_set(mat_weap, "fo4sf/weapons/10mmpistol/10mmpistol")

    mat_ammo = "materials/fo4core/ammo/10mm/10mm.mat"
    ammo_m = sfmesh.SfMesh(version=2)
    ammo_m.scale, ammo_m.positions = sfmesh.encode_positions(
        [(-0.04, -0.02, 0.0), (0.04, -0.02, 0.0), (0.04, 0.02, 0.03), (-0.04, 0.02, 0.03)]
    )
    ammo_m.triangles = [(0, 1, 2), (0, 2, 3)]
    sfmesh.build_meshlets(ammo_m)
    ammo_mb = sfmesh.serialize(ammo_m)
    ad_hex, af_hex = s10.convert_static.mesh_file_path(ammo_mb)
    (assets / "geometries" / ad_hex).mkdir(parents=True, exist_ok=True)
    (assets / "geometries" / ad_hex / f"{af_hex}.mesh").write_bytes(ammo_mb)
    pts_dec = [sfmesh.decode_position(pt, ammo_m.scale) for pt in ammo_m.positions]
    sph, bx = sfnif.bounds_from_points(pts_dec)
    ammo_nf = sfnif.build_static_nif(
        b"10mmammo",
        [
            sfnif.StaticShape(
                name=b"Box:0",
                mesh_path=f"{ad_hex}\\{af_hex}".encode("ascii"),
                indices_size=6,
                num_verts=4,
                material_path=mat_ammo,
                sphere=sph,
                box=bx,
            )
        ],
    )
    ammo_p = assets / s10.AMMO_10MM_REL
    ammo_p.parent.mkdir(parents=True, exist_ok=True)
    ammo_p.write_bytes(nif.serialize(ammo_nf))
    write_dx10_dds_set(mat_ammo, "fo4core/ammo/10mm/10mm")
    return assets


class R11ProbeP4PistolTests(unittest.TestCase):
    def test_synthetic_probe_p4_stage_verify_and_target_dummy_initially_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.object(p4, "check_starfield_not_running", return_value=None):
            tmp = Path(td)
            syn_assets = _build_synthetic_assets_dir(tmp)
            stage_out = tmp / "p4_stage"
            manifest = p4.stage_probe_p4(
                out_dir=stage_out,
                prebuilt_core_esms={
                    "FO4SFCoreValues.esm": _minimal_tes4_esm(0x1, b"CORE10MM"),
                    "FO4SFNewGame.esm": _minimal_tes4_esm(0x1, b"NG10MM"),
                },
                prebuilt_assets_dir=syn_assets,
                prebuilt_pex={
                    "FO4SF_NewGameQuest": b"PEX_NG_10MM",
                    "FO4SF_R11P4Quest": b"PEX_P4_10MM",
                },
                min_free_gb=0.001,
            )
            self.assertEqual(manifest["probe"], "r11-p4-10mm")
            self.assertIn("rigid and do not move", manifest["rigid_parts_disclosure"])

            vf = p4.verify_probe_p4(stage_out)
            self.assertTrue(vf["p3_zero_mnv"])
            self.assertTrue(vf["p3_zero_stripped_fo4sf_edids"])
            self.assertEqual(vf["textures_ba2_entries"], 6)

            # Inspect FO4SF_R11P4Pistol.esm masters, TargetDummy flags (0xC00), QUST DNAM (0x00000009), and VMAD
            with Plugin(str(stage_out / "exp" / p4.PROBE_PLUGIN)) as plg:
                self.assertEqual(
                    tuple(plg.masters),
                    ("Starfield.esm", "FO4Port.esm", "FO4SFCoreValues.esm", "FO4ActorRaider.esm"),
                )
                found_dummy = False
                found_qust = False
                for spans in plg.groups.values():
                    for start, end in spans:
                        for item in plg.walk(start, end):
                            if item[0] != "REC":
                                continue
                            rec = plg.record_at(item[1])
                            if rec.sig == b"ACHR" and (rec.formid & 0xFFFFFF) == 0x000811:
                                self.assertEqual(rec.flags & 0xC00, 0xC00)
                                found_dummy = True
                            if rec.sig == b"QUST" and (rec.formid & 0xFFFFFF) == 0x000820:
                                subs = dict(rec.subs)
                                self.assertEqual(struct.unpack_from("<I", subs[b"DNAM"], 0)[0], 0x00000009)
                                self.assertIn(b"PortPlugin", subs[b"VMAD"])
                                self.assertIn(b"ArmoryCageDoorLocalId", subs[b"VMAD"])
                                found_qust = True
                self.assertTrue(found_dummy)
                self.assertTrue(found_qust)

            # Main BA2 carries both compiled .pex scripts and weapon/ammo NIFs
            m_ba2 = Ba2(str(stage_out / "exp" / p4.PROBE_MAIN_BA2))
            self.assertEqual(m_ba2.read("Scripts\\FO4SF_NewGameQuest.pex"), b"PEX_NG_10MM")
            self.assertEqual(m_ba2.read("Scripts\\FO4SF_R11P4Quest.pex"), b"PEX_P4_10MM")
            self.assertIsNotNone(m_ba2.find(s10.WEAP_10MM_REL))
            self.assertIsNotNone(m_ba2.find(s10.AMMO_10MM_REL))

    def test_bs_crc32_vectors_and_binary_ba2_entry_hash_validator(self) -> None:
        self.assertEqual(p4.bs_crc32(b"scripts"), 0x40724840)
        self.assertEqual(p4.bs_crc32(b"textures\\fo4core\\ammo\\10mm"), 0x01C88DFC)
        self.assertEqual(p4.bs_crc32(b"10mmcartridge_color"), 0xABDBFB3B)

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            gnrl_p = tmp / "test_main.ba2"
            p4.pack_gnrl_ba2_v2([("Scripts\\FO4SF_NewGameQuest.pex", b"PEX_DATA_UNCOMPRESSED")], gnrl_p)
            self.assertEqual(p4.verify_ba2_entry_hashes(gnrl_p, require_uncompressed_gnrl=True), 1)

            # Corrupting dir_hash to IEEE zlib.crc32 (0xDD1E973E) must fail verify_ba2_entry_hashes!
            bad = bytearray(gnrl_p.read_bytes())
            struct.pack_into("<I", bad, 32 + 8, 0xDD1E973E)
            bad_p = tmp / "bad_main.ba2"
            bad_p.write_bytes(bad)
            with self.assertRaises(p4.ProbeP4Error):
                p4.verify_ba2_entry_hashes(bad_p)

    def test_p3_zero_mnv_zero_stripped_fo4sf_edids_and_under_200m_hops(self) -> None:
        batches = p4.build_p3_batch_scripts(quest_load_prefix=0x11)
        self.assertIn("player.setpos x -53.20", batches["p4t.txt"])
        rep = p4.validate_p3_batches_and_hops(batches)
        self.assertTrue(rep["p3_zero_mnv"])
        self.assertTrue(rep["p3_zero_stripped_fo4sf_edids"])
        for h in rep["exterior_hops"]:
            self.assertLess(h["max_axis_m"], 200.0)

        # Negative 1: M/N/V in filename must fail P3 check
        bad_mnv = dict(batches)
        bad_mnv["p4m.txt"] = "player.setangle z 90\n"
        with self.assertRaises(p4.ProbeP4Error):
            p4.validate_p3_batches_and_hops(bad_mnv)

        # Negative 2: stripped FO4SF_ EditorID inside batch file must fail P3 check
        bad_edid = dict(batches)
        bad_edid["p4t.txt"] = "SetStage FO4SF_R11P4Quest 20\n"
        with self.assertRaises(p4.ProbeP4Error):
            p4.validate_p3_batches_and_hops(bad_edid)

    def test_reversible_install_uninstall_never_hardlinks_esms_and_stamps_full_master_slot(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.object(p4, "check_starfield_not_running", return_value=None):
            tmp = Path(td)
            syn_assets = _build_synthetic_assets_dir(tmp)
            stage_out = tmp / "p4_stage"
            p4.stage_probe_p4(
                out_dir=stage_out,
                prebuilt_core_esms={
                    "FO4SFCoreValues.esm": _minimal_tes4_esm(0x1, b"P4_CV_NEW"),
                    "FO4SFNewGame.esm": _minimal_tes4_esm(0x1, b"P4_NG_NEW"),
                },
                prebuilt_assets_dir=syn_assets,
                prebuilt_pex={
                    "FO4SF_NewGameQuest": b"PEX_NG",
                    "FO4SF_R11P4Quest": b"PEX_P4",
                },
                min_free_gb=0.001,
            )

            sf_root = tmp / "Starfield"
            data_dir = sf_root / "Data"
            data_dir.mkdir(parents=True)
            # Implicit full masters (2): Starfield.esm (0x00), BlueprintShips-Starfield.esm (0x01)
            (data_dir / "Starfield.esm").write_bytes(_minimal_tes4_esm(0x1))
            (data_dir / "BlueprintShips-Starfield.esm").write_bytes(_minimal_tes4_esm(0x1))
            # Active FE light (0x201) & FD medium (0x101) masters — MUST NOT consume 0x00..0xFC full-master slots!
            (data_dir / "SFBGS003.esm").write_bytes(_minimal_tes4_esm(0x201))
            (data_dir / "SFBGS007.esm").write_bytes(_minimal_tes4_esm(0x101))
            # Active FO4SF full masters ahead of probe (3): FO4Port (0x02), FO4SFCoreValues (0x03), FO4SFNewGame (0x04)
            (data_dir / "FO4Port.esm").write_bytes(_minimal_tes4_esm(0x1))
            orig_cv = _minimal_tes4_esm(0x1, b"ORIG_2G_CV")
            orig_ng = _minimal_tes4_esm(0x1, b"ORIG_2G_NG")
            (data_dir / "FO4SFCoreValues.esm").write_bytes(orig_cv)
            (data_dir / "FO4SFNewGame.esm").write_bytes(orig_ng)
            orig_cv_sha = p4.sha256_file(data_dir / "FO4SFCoreValues.esm")
            orig_ng_sha = p4.sha256_file(data_dir / "FO4SFNewGame.esm")

            ptxt = tmp / "Plugins.txt"
            orig_ptxt = "*SFBGS003.esm\n*SFBGS007.esm\n*FO4Port.esm\n*FO4SFCoreValues.esm\n*FO4SFNewGame.esm\n"
            ptxt.write_text(orig_ptxt, encoding="utf-8")

            rc_in = p4.install_probe_p4(stage_out, sf_root, plugins_txt=ptxt, min_free_gb=0.001)
            # Slot must be 0x05 (Starfield=0, Blueprint=1, FO4Port=2, CV=3, NG=4 -> Probe=5, skipping FE & FD!)
            self.assertEqual(rc_in["quest_full_master_slot_hex"], "0x05")
            self.assertIn("SetStage 05000820 20", (sf_root / "p4t.txt").read_text(encoding="utf-8"))
            self.assertTrue(p4.status_probe_p4(sf_root)["installed"])

            # Mandatory #559 Rule 2: .esm and .txt files in Data/root MUST NEVER share hardlink inodes (st_nlink == 1)!
            for esm_nm in ("FO4SFCoreValues.esm", "FO4SFNewGame.esm", p4.PROBE_PLUGIN):
                self.assertEqual((data_dir / esm_nm).stat().st_nlink, 1, f"{esm_nm} was hardlinked!")
            self.assertEqual((sf_root / "p4t.txt").stat().st_nlink, 1)

            # Uninstall restores bit-for-bit original SHA-256s and Plugins.txt
            p4.uninstall_probe_p4(sf_root, plugins_txt=ptxt)
            self.assertFalse(p4.status_probe_p4(sf_root)["installed"])
            self.assertEqual(p4.sha256_file(data_dir / "FO4SFCoreValues.esm"), orig_cv_sha)
            self.assertEqual(p4.sha256_file(data_dir / "FO4SFNewGame.esm"), orig_ng_sha)
            self.assertEqual(ptxt.read_text(encoding="utf-8"), orig_ptxt)
            self.assertFalse((data_dir / p4.PROBE_PLUGIN).exists())
            self.assertFalse((sf_root / "p4t.txt").exists())

    def test_starfield_running_guard_refuses_when_game_active(self) -> None:
        with mock.patch.object(p4.System, "pids", return_value=[42196]):
            with self.assertRaises(p4.ProbeP4Error):
                p4.check_starfield_not_running()
        with mock.patch.object(p4.System, "pids", return_value=[]):
            p4.check_starfield_not_running()

    def test_translated_p4_quest_psc_execution_and_hygiene(self) -> None:
        for path in (P4_STAGE_PY, P4_QUEST_PSC, HERE):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM in {path.name}")
            txt = raw.decode("utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive-letter path leak in {path.name}")

        psc = P4_QUEST_PSC.read_text(encoding="utf-8")
        for tok in ("Event OnInit()", "Event OnQuestInit()", "Event OnQuestStarted()", "EnsureStarted("):
            self.assertIn(tok, psc, f"missing autostart lifecycle hook {tok}")
        self.assertNotIn("ObjectReference Property ArmoryCageDoor Auto", psc)

        funcs = ("SpawnPracticeTarget", "OnTimer", "Actor.OnDying", "LogScorecard", "FormatPos")
        vars_csv = (
            "TIMER_POLL, lastAmmoCount, shotsFiredTotal, fullMag12Proven, "
            "targetActive, targetKilled, targetHits, lastTargetHp"
        )
        pistol = object()
        ammo = object()
        xm2311 = object()
        cal45 = object()
        health_av = object()
        hide_suit_av = object()
        inv = {pistol: 1, ammo: 48, xm2311: 0, cal45: 0}

        player = Reference(None, (-55.40, 29.80, 0.15), form_id=0x14)
        player.GetItemCount = lambda f: inv.get(f, 0)  # type: ignore[attr-defined]
        player.IsEquipped = lambda f: f is pistol  # type: ignore[attr-defined]

        cage_state = {"lock_level": 100, "locked": True, "open": False, "anim": ""}
        cage_door = SimpleNamespace(
            SetLockLevel=lambda lv: cage_state.__setitem__("lock_level", int(lv)),
            Lock=lambda locked=True, as_owner=False: cage_state.__setitem__("locked", bool(locked)),
            SetOpen=lambda is_open=True: cage_state.__setitem__("open", bool(is_open)),
            PlayGamebryoAnimation=lambda anim, start_over=False, ease=0.0: cage_state.__setitem__("anim", str(anim)),
        )

        dummy_state = {"hp": 100.0, "dead": False, "restrained": False, "suit_hidden": 0.0, "removed_items": False}
        dummy = Reference(None, (-48.80, 30.00, 0.15), form_id=0x04000811)
        dummy.IsDead = lambda: dummy_state["dead"]  # type: ignore[attr-defined]
        dummy.Resurrect = lambda: dummy_state.__setitem__("dead", False)  # type: ignore[attr-defined]
        dummy.RemoveAllItems = lambda *_: dummy_state.__setitem__("removed_items", True)  # type: ignore[attr-defined]
        dummy.SetRestrained = lambda v: dummy_state.__setitem__("restrained", bool(v))  # type: ignore[attr-defined]
        dummy.GetValue = lambda av: dummy_state["hp"] if av is health_av else 0.0  # type: ignore[attr-defined]
        dummy.SetValue = lambda av, v: dummy_state.__setitem__("suit_hidden", v) if av is hide_suit_av else None  # type: ignore[attr-defined]
        dummy.DamageValue = lambda av, d: dummy_state.__setitem__("hp", dummy_state["hp"] - d)  # type: ignore[attr-defined]
        dummy.RestoreValue = lambda av, d: dummy_state.__setitem__("hp", dummy_state["hp"] + d)  # type: ignore[attr-defined]
        dummy.GetDistance = lambda other: 4.40  # type: ignore[attr-defined]

        logs: list[str] = []
        ns = dict(
            Log=logs.append,
            TIMER_POLL=1,
            lastAmmoCount=48,
            shotsFiredTotal=0,
            fullMag12Proven=False,
            targetActive=False,
            targetKilled=False,
            targetHits=0,
            lastTargetHp=0.0,
            TargetTrigger=object(),
            PortPlugin="FO4Port.esm",
            ArmoryCageDoorLocalId=0x001539,
            TargetDummy=dummy,
            Pistol10mm=pistol,
            Ammo10mm=ammo,
            DonorXm2311=xm2311,
            DonorAmmo45=cal45,
            HealthAV=health_av,
            HideSuitAV=hide_suit_av,
            Game=SimpleNamespace(
                GetPlayer=lambda: player,
                GetFormFromFile=lambda fid, plg: cage_door if (fid == 0x001539 and plg == "FO4Port.esm") else None,
            ),
            Utility=SimpleNamespace(Wait=lambda *_: None),
            StartTimer=lambda *_: None,
        )
        py_src = "\n".join(
            ln if idx < 5 else _wrap_pstr_literals(ln)
            for idx, ln in enumerate(translated_functions(psc, funcs, vars_csv).splitlines())
        )
        exec(compile(py_src, str(P4_QUEST_PSC), "exec"), ns)

        ns["SpawnPracticeTarget"]("trigger_activate")
        self.assertEqual(cage_state, {"lock_level": 0, "locked": False, "open": True, "anim": "Open"})
        self.assertEqual((dummy.GetPositionX(), dummy.GetPositionY(), dummy.GetPositionZ()), (-48.80, 30.00, 0.15))
        self.assertTrue(dummy_state["removed_items"])
        self.assertTrue(dummy_state["restrained"])
        self.assertEqual(dummy_state["suit_hidden"], 1.0)
        self.assertAlmostEqual(dummy_state["hp"], 30.0, places=3)

        # Fire 12 rounds (1 full magazine) and land 2 shots (18 + 18 >= 30 HP) on TargetDummy
        inv[ammo] = 36
        dummy_state["hp"] = 12.0
        ns["OnTimer"](1)
        self.assertTrue(ns["fullMag12Proven"])
        self.assertEqual(ns["shotsFiredTotal"], 12)
        self.assertEqual(ns["targetHits"], 1)

        dummy_state["hp"] = 0.0
        dummy_state["dead"] = True
        ns["OnTimer"](1)
        ns["OnDying"](dummy, player)
        self.assertTrue(ns["targetKilled"])

        ns["LogScorecard"]("stage_30")
        self.assertTrue(
            any(
                "FO4SF_R11P4 summary tag=stage_30" in ln
                and "equipped=True pistol_10mm=1 ammo_10mm=36 fired_total=12 full_mag_12_proven=True" in ln
                and "target_killed=True xm2311_leak=0 cal45_leak=0" in ln
                for ln in logs
            ),
            logs,
        )

    @unittest.skipUnless(
        bool(os.environ.get("FO4SF_R11_P4_STAGE")),
        "Set FO4SF_R11_P4_STAGE to verify live staged r11-p4-10mm folder",
    )
    def test_live_staged_probe_p4_folder_when_present(self) -> None:
        stage_dir = Path(os.environ["FO4SF_R11_P4_STAGE"])
        res = p4.verify_probe_p4(stage_dir)
        self.assertGreaterEqual(res["verified_files"], 40)
        self.assertEqual(res["textures_ba2_entries"], 13)
        self.assertTrue(res["p3_zero_mnv"])
        self.assertTrue(res["p3_zero_stripped_fo4sf_edids"])


if __name__ == "__main__":
    unittest.main()
