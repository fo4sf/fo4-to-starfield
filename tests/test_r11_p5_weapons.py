"""Cross-OS synthetic + translated-Papyrus + card tests for Round 11 Probe P5 (Baton, 10mm, Laser Musket & Minigun).

Covers:
  1. Synthetic Probe P5 staging & verification (`FO4SF_R11P5Weapons.esm` masters, `QUST DNAM = 0x00000009`
     `StartGameEnabled | AllowRepeatedStages`, zero `ArmoryCageDoor` VMAD ObjectRef, `TargetDummy` `0xC00`,
     exact FO4 Vault 111 Baton placements `0x0019891C` & `0x000AE470`, range Laser Musket + 3x24 Cells,
     Minigun + 500x 5mm, all 4 weapon + 3 ammo NIFs packed in GNRL/DX10 BA2s with Bethesda bs_crc32).
  2. Negative tamper guards (forbidden Starfield donor mesh tokens, corrupted bs_crc32, bad QUST DNAM).
  3. Rule P3 (`0` `M`/`N`/`V` in batch filenames and typed console lines across both stager & card,
     `0` stripped `FO4SF_` EditorIDs inside `bat/*.txt`, and `< 200 m`/axis exterior hops).
  4. Reversible `install` / `status` / `uninstall` round-trip (`st_nlink == 1` on `.esm`/`.txt`, skips
     `FE`/`FD` masters when computing `<XX>000820`, restores exact pre-probe SHA-256s & `Plugins.txt`).
  5. Translated execution of `FO4SF_R11P5Quest.psc` (start-of-game `OnInit` logging, runtime `GetFormFromFile`
     `ArmoryCageDoor`, `RemoveAllItems` unarmed dummy, auto-equip all 4 weapons, Baton melee kill + reset +
     ranged mag/charge/burst kills without double-counting, `donor_leaks=0`) + BOM/drive-path/card hygiene.
"""
from __future__ import annotations

import json
import math
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

for _p in (str(REPO_ROOT), str(SRC_DIR), str(PROBES_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_r11_p5_weapons as p5  # noqa: E402
from fo4sf import convert_static, nif, sfmesh, sfnif  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.planet.esm import Plugin  # noqa: E402
from tests.test_exit_arrival import Reference, _wrap_pstr_literals, translated_functions  # noqa: E402

P5_STAGE_PY = PROBES_DIR / "stage_r11_p5_weapons.py"
P5_QUEST_PSC = PROBES_DIR / "FO4SF_R11P5Quest.psc"
P5_CARD_MD = REPO_ROOT / "docs" / "testing" / "round11-probe-p5-card.md"
DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")


def _minimal_tes4_esm(flags: int = 0x1, payload: bytes = b"") -> bytes:
    hedr = b"HEDR" + struct.pack("<HfII", 12, 0.96, 0, 0x800) + payload
    return b"TES4" + struct.pack("<IIIIHH", len(hedr), flags, 0, 0, 576, 0) + hedr


def _dx10_4x4_dds() -> bytes:
    return (
        b"DDS "
        + struct.pack("<7I", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8, 4, 4, 16, 0, 1)
        + b"\x00" * 44
        + struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
        + struct.pack("<5I", 0x1000, 0, 0, 0, 0)
        + struct.pack("<5I", 28, 3, 0, 1, 0)
        + (b"\x80" * 64)
    )


def _write_synthetic_nif_and_assets(assets: Path, rel_nif: str, root_name: bytes, shape_name: bytes, mat_rel: str, tex_prefix: str, seed_offset: float) -> None:
    dds_bytes = _dx10_4x4_dds()
    dds_rels = [f"textures/{tex_prefix}_{sfx}.dds" for sfx in ("color", "normal", "rough")]
    for dr in dds_rels:
        dp = assets / Path(*dr.split("/"))
        dp.parent.mkdir(parents=True, exist_ok=True)
        dp.write_bytes(dds_bytes)
    mp = assets / Path(*mat_rel.split("/"))
    mp.parent.mkdir(parents=True, exist_ok=True)
    # Match convert_material.game_path's real "Data\\Textures\\..." prefix so verify_p5_assets_tree strips "data/"
    mat_tex_entries = [
        "Data\\" + dr.replace("/", "\\") if idx == 0 else dr
        for idx, dr in enumerate(dds_rels)
    ]
    mp.write_text(json.dumps({"Textures": mat_tex_entries}, indent=2), encoding="utf-8")

    m = sfmesh.SfMesh(version=2)
    m.scale, m.positions = sfmesh.encode_positions(
        [
            (-0.05 + seed_offset, -0.02, 0.0),
            (0.05 + seed_offset, -0.02, 0.0),
            (0.05 + seed_offset, 0.02, 0.04),
            (-0.05 + seed_offset, 0.02, 0.04),
        ]
    )
    m.triangles = [(0, 1, 2), (0, 2, 3)]
    sfmesh.build_meshlets(m)
    mb = sfmesh.serialize(m)
    d_hex, f_hex = convert_static.mesh_file_path(mb)
    (assets / "geometries" / d_hex).mkdir(parents=True, exist_ok=True)
    (assets / "geometries" / d_hex / f"{f_hex}.mesh").write_bytes(mb)
    pts_dec = [sfmesh.decode_position(pt, m.scale) for pt in m.positions]
    sph, bx = sfnif.bounds_from_points(pts_dec)
    nf = sfnif.build_static_nif(
        root_name,
        [
            sfnif.StaticShape(
                name=shape_name,
                mesh_path=f"{d_hex}\\{f_hex}".encode("ascii"),
                indices_size=6,
                num_verts=4,
                material_path=mat_rel,
                sphere=sph,
                box=bx,
            )
        ],
    )
    np = assets / Path(*rel_nif.split("/"))
    np.parent.mkdir(parents=True, exist_ok=True)
    np.write_bytes(nif.serialize(nf))


def _build_synthetic_p5_assets_dir(root: Path) -> Path:
    assets = root / "syn_p5_assets"
    specs = [
        (p5.WEAPON_NIF_RELS["10mm"], b"WEAPON", b"Pistol10mmReceiver:0", "materials/fo4sf/weapons/10mm/10mm.mat", "fo4sf/weapons/10mm/10mm", 0.001),
        (p5.WEAPON_NIF_RELS["baton"], b"BatonLowHandleMerged", b"BatonLowHandleMerged:0", "materials/fo4sf/weapons/baton/baton.mat", "fo4sf/weapons/baton/baton", 0.002),
        (p5.WEAPON_NIF_RELS["lasermusket"], b"WEAPON", b"LaserMusketCrank:0", "materials/fo4sf/weapons/lasermusket/musket.mat", "fo4sf/weapons/lasermusket/musket", 0.003),
        (p5.WEAPON_NIF_RELS["minigun"], b"WEAPON", b"Minigun_Barrel:0", "materials/fo4sf/weapons/minigun/minigun.mat", "fo4sf/weapons/minigun/minigun", 0.004),
        (p5.AMMO_NIF_RELS["10mm"], b"10mmammo", b"Box10mm:0", "materials/fo4core/ammo/10mm/10mm.mat", "fo4core/ammo/10mm/10mm", 0.005),
        (p5.AMMO_NIF_RELS["fusioncell"], b"microfusioncell", b"Cell:0", "materials/fo4core/ammo/laserammo/cell.mat", "fo4core/ammo/laserammo/cell", 0.006),
        (p5.AMMO_NIF_RELS["5mm"], b"5mmammo", b"Box5mm:0", "materials/fo4core/ammo/5mm/5mm.mat", "fo4core/ammo/5mm/5mm", 0.007),
    ]
    for rel_nif, rname, sname, mat_rel, tpref, off in specs:
        _write_synthetic_nif_and_assets(assets, rel_nif, rname, sname, mat_rel, tpref, off)
    return assets


class R11ProbeP5WeaponsTests(unittest.TestCase):
    def test_synthetic_probe_p5_stage_verify_dnam_vmad_and_placements(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.object(p5.System, "pids", return_value=[]):
            tmp = Path(td)
            syn_assets = _build_synthetic_p5_assets_dir(tmp)
            stage_out = tmp / "p5_stage"
            manifest = p5.stage_probe_p5(
                out_dir=stage_out,
                prebuilt_core_esms={
                    "FO4SFCoreValues.esm": _minimal_tes4_esm(0x1, b"CORE_P5"),
                    "FO4SFNewGame.esm": _minimal_tes4_esm(0x1, b"NG_P5"),
                },
                prebuilt_assets_dir=syn_assets,
                prebuilt_pex={
                    "FO4SF_NewGameQuest": b"PEX_NG_P5",
                    "FO4SF_R11P5Quest": b"PEX_P5_QUEST",
                },
                min_free_gb=0.001,
            )
            self.assertEqual(manifest["probe"], "r11-p5-weapons")
            self.assertIn("stand-ins", manifest["standin_disclosure"])
            self.assertEqual(manifest["probe_plugin"]["quest_dnam_flags_hex"], "0x00000009")

            vf = p5.verify_probe_p5(stage_out)
            self.assertTrue(vf["p3_zero_mnv"])
            self.assertTrue(vf["p3_zero_stripped_fo4sf_edids"])
            self.assertEqual(vf["qust_dnam_hex"], "0x00000009")
            self.assertEqual(vf["verified_weapons"], ["10mm", "baton", "lasermusket", "minigun"])
            self.assertEqual(vf["verified_ammo"], ["10mm", "5mm", "fusioncell"])
            self.assertEqual(vf["textures_ba2_entries"], 21)

            # Inspect FO4SF_R11P5Weapons.esm exact records, positions, flat Baton pitch & flags
            with Plugin(str(stage_out / "exp" / p5.PROBE_PLUGIN)) as plg:
                self.assertEqual(
                    tuple(plg.masters),
                    ("Starfield.esm", "FO4Port.esm", "FO4SFCoreValues.esm", "FO4ActorRaider.esm"),
                )
                coords_by_lid = {}
                rots_by_lid = {}
                for spans in plg.groups.values():
                    for start, end in spans:
                        for item in plg.walk(start, end):
                            if item[0] != "REC":
                                continue
                            rec = plg.record_at(item[1])
                            if rec.sig == b"REFR":
                                dr = rec.get(b"DATA")
                                if dr and len(dr) >= 24:
                                    vals = struct.unpack_from("<6f", dr, 0)
                                    coords_by_lid[rec.formid & 0xFFFFFF] = vals[:3]
                                    rots_by_lid[rec.formid & 0xFFFFFF] = vals[3:]
                # Exact FO4 Vault111Cryo Baton locations (0x0019891C & 0x000AE470) & rx=-pi/2 flat pitch
                for got, want in zip(coords_by_lid[0x000812], p5.BATON_CRYO_POS):
                    self.assertAlmostEqual(got, want, places=3)
                for got, want in zip(coords_by_lid[0x000813], p5.BATON_CRATE_POS):
                    self.assertAlmostEqual(got, want, places=3)
                self.assertAlmostEqual(rots_by_lid[0x000812][0], -math.pi / 2.0, places=4)
                self.assertAlmostEqual(rots_by_lid[0x000813][0], -math.pi / 2.0, places=4)

            # Main BA2 carries both .pex scripts and all 4 weapon + 3 ammo NIFs
            m_ba2 = Ba2(str(stage_out / "exp" / p5.PROBE_MAIN_BA2))
            self.assertEqual(m_ba2.read("Scripts\\FO4SF_NewGameQuest.pex"), b"PEX_NG_P5")
            self.assertEqual(m_ba2.read("Scripts\\FO4SF_R11P5Quest.pex"), b"PEX_P5_QUEST")
            for rel_nif in list(p5.WEAPON_NIF_RELS.values()) + list(p5.AMMO_NIF_RELS.values()):
                self.assertIsNotNone(m_ba2.find(rel_nif), f"missing {rel_nif} in Main.ba2")

    def test_refuses_stage_and_install_while_starfield_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.object(p5.System, "pids", return_value=[42424]):
            tmp = Path(td)
            with self.assertRaisesRegex(p5.ProbeP5Error, "refused while Starfield.exe is running"):
                p5.stage_probe_p5(out_dir=tmp / "blocked_stage", min_free_gb=0.001)
            with self.assertRaisesRegex(p5.ProbeP5Error, "refused while Starfield.exe is running"):
                p5.install_probe_p5(tmp / "s", tmp / "sf", min_free_gb=0.001)
            with self.assertRaisesRegex(p5.ProbeP5Error, "refused while Starfield.exe is running"):
                p5.uninstall_probe_p5(tmp / "sf")

    def test_negative_tamper_guards_donor_token_and_ba2_crc(self) -> None:
        self.assertEqual(p5.bs_crc32(b"scripts"), 0x40724840)
        self.assertEqual(p5.bs_crc32(b"textures\\fo4core\\ammo\\10mm"), 0x01C88DFC)

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # 1. Corrupting GNRL dir_hash to IEEE zlib.crc32 must fail
            gnrl_p = tmp / "test_main.ba2"
            p5.pack_gnrl_ba2_v2([("Scripts\\FO4SF_R11P5Quest.pex", b"PEX_P5")], gnrl_p)
            self.assertEqual(p5.verify_ba2_entry_hashes(gnrl_p, require_uncompressed_gnrl=True), 1)
            bad = bytearray(gnrl_p.read_bytes())
            struct.pack_into("<I", bad, 32 + 8, 0xDD1E973E)
            bad_p = tmp / "bad_main.ba2"
            bad_p.write_bytes(bad)
            with self.assertRaises(p5.ProbeP5Error):
                p5.verify_ba2_entry_hashes(bad_p)

            # 2. Forbidden Starfield donor weapon token in NIF fails verify_p5_assets_tree
            syn = _build_synthetic_p5_assets_dir(tmp)
            baton_nif = syn / Path(*p5.WEAPON_NIF_RELS["baton"].split("/"))
            baton_nif.write_bytes(baton_nif.read_bytes() + b"weapons/rescueaxe/bad")
            with self.assertRaisesRegex(p5.ProbeP5Error, "forbidden Starfield donor token"):
                p5.verify_p5_assets_tree(syn)

    def test_p3_zero_mnv_zero_stripped_fo4sf_edids_and_under_200m_hops(self) -> None:
        batches = p5.build_p3_batch_scripts(quest_load_prefix=0x11)
        for req_bat in ("p5b1.txt", "p5b2.txt", "p5d.txt", "p5o.txt", "p5r.txt", "p5t.txt", "p5g.txt", "p5h1.txt", "p5e.txt", "p5s.txt", "p5q.txt"):
            self.assertIn(req_bat, batches)
        rep = p5.validate_p3_batches_and_hops(batches)
        self.assertTrue(rep["p3_zero_mnv"])
        self.assertTrue(rep["p3_zero_stripped_fo4sf_edids"])
        for h in rep["exterior_hops"]:
            self.assertLess(h["max_axis_m"], 200.0)

        # Negative: M/N/V in filename must fail P3 check
        bad_mnv = dict(batches)
        bad_mnv["p5m.txt"] = "player.setangle z 90\n"
        with self.assertRaises(p5.ProbeP5Error):
            p5.validate_p3_batches_and_hops(bad_mnv)

        # Negative: stripped FO4SF_ EditorID inside batch file must fail P3 check
        bad_edid = dict(batches)
        bad_edid["p5t.txt"] = "SetStage FO4SF_R11P5Quest 20\n"
        with self.assertRaises(p5.ProbeP5Error):
            p5.validate_p3_batches_and_hops(bad_edid)

    def test_reversible_install_uninstall_never_hardlinks_esms_and_stamps_slot(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.object(p5.System, "pids", return_value=[]):
            tmp = Path(td)
            syn_assets = _build_synthetic_p5_assets_dir(tmp)
            stage_out = tmp / "p5_stage"
            p5.stage_probe_p5(
                out_dir=stage_out,
                prebuilt_core_esms={
                    "FO4SFCoreValues.esm": _minimal_tes4_esm(0x1, b"P5_CV_NEW"),
                    "FO4SFNewGame.esm": _minimal_tes4_esm(0x1, b"P5_NG_NEW"),
                },
                prebuilt_assets_dir=syn_assets,
                prebuilt_pex={
                    "FO4SF_NewGameQuest": b"PEX_NG",
                    "FO4SF_R11P5Quest": b"PEX_P5",
                },
                min_free_gb=0.001,
            )

            sf_root = tmp / "Starfield"
            data_dir = sf_root / "Data"
            data_dir.mkdir(parents=True)
            (data_dir / "Starfield.esm").write_bytes(_minimal_tes4_esm(0x1))
            (data_dir / "BlueprintShips-Starfield.esm").write_bytes(_minimal_tes4_esm(0x1))
            # FE light (0x201) & FD medium (0x101) masters must NOT consume 0x00..0xFC full-master slots
            (data_dir / "SFBGS003.esm").write_bytes(_minimal_tes4_esm(0x201))
            (data_dir / "SFBGS007.esm").write_bytes(_minimal_tes4_esm(0x101))
            (data_dir / "FO4Port.esm").write_bytes(_minimal_tes4_esm(0x1))
            (data_dir / "FO4SFCoreValues.esm").write_bytes(_minimal_tes4_esm(0x1, b"ORIG_2GFIX2_CV"))
            (data_dir / "FO4SFNewGame.esm").write_bytes(_minimal_tes4_esm(0x1, b"ORIG_2GFIX2_NG"))
            orig_cv_sha = p5.sha256_file(data_dir / "FO4SFCoreValues.esm")
            orig_ng_sha = p5.sha256_file(data_dir / "FO4SFNewGame.esm")

            ptxt = tmp / "Plugins.txt"
            orig_ptxt = "*SFBGS003.esm\n*SFBGS007.esm\n*FO4Port.esm\n*FO4SFCoreValues.esm\n*FO4SFNewGame.esm\n"
            ptxt.write_text(orig_ptxt, encoding="utf-8")

            rc_in = p5.install_probe_p5(stage_out, sf_root, plugins_txt=ptxt, min_free_gb=0.001)
            self.assertEqual(rc_in["quest_full_master_slot_hex"], "0x05")
            self.assertIn("SetStage 05000820 20", (sf_root / "p5t.txt").read_text(encoding="utf-8"))
            self.assertIn("getstage 05000820", (sf_root / "p5q.txt").read_text(encoding="utf-8"))
            self.assertTrue(p5.status_probe_p5(sf_root)["installed"])

            # .esm and .txt MUST NEVER be hardlinked (st_nlink == 1)
            for esm_nm in ("FO4SFCoreValues.esm", "FO4SFNewGame.esm", p5.PROBE_PLUGIN):
                self.assertEqual((data_dir / esm_nm).stat().st_nlink, 1, f"{esm_nm} was hardlinked!")
            self.assertEqual((sf_root / "p5t.txt").stat().st_nlink, 1)

            # Uninstall restores exact original SHA-256s and Plugins.txt
            p5.uninstall_probe_p5(sf_root, plugins_txt=ptxt)
            self.assertFalse(p5.status_probe_p5(sf_root)["installed"])
            self.assertEqual(p5.sha256_file(data_dir / "FO4SFCoreValues.esm"), orig_cv_sha)
            self.assertEqual(p5.sha256_file(data_dir / "FO4SFNewGame.esm"), orig_ng_sha)
            self.assertEqual(ptxt.read_text(encoding="utf-8"), orig_ptxt)
            self.assertFalse((data_dir / p5.PROBE_PLUGIN).exists())
            self.assertFalse((sf_root / "p5t.txt").exists())

    def test_translated_p5_quest_psc_auto_equip_baton_kill_reset_and_runtime_door(self) -> None:
        psc = P5_QUEST_PSC.read_text(encoding="utf-8")
        funcs = (
            "OnInit",
            "OnQuestInit",
            "EnsureInitialized",
            "EquippedWeaponTag",
            "WeaponTagForForm",
            "ObjectReference.OnItemAdded",
            "ResolveArmoryCageDoor",
            "SpawnPracticeTarget",
            "OnTimer",
            "Actor.OnDying",
            "CountDonorLeaks",
            "LogScorecard",
            "FormatPos",
        )
        vars_csv = (
            "TIMER_POLL, initLogged, lastAmmo10mm, lastAmmoCell, lastAmmo5mm, "
            "shots10mm, shotsCell, shots5mm, fullMag12Proven, fullChargeProven, burst5mmProven, "
            "targetActive, targetKilled, batonKilledTarget, rangedKilledTarget, "
            "targetHits, targetKillsTotal, lastTargetHp"
        )
        baton, pistol10, musket, minigun = object(), object(), object(), object()
        a10, acell, a5 = object(), object(), object()
        donors = [object() for _ in range(7)]
        health_av, hide_suit_av = object(), object()

        inv = {baton: 0, pistol10: 0, musket: 0, minigun: 0, a10: 0, acell: 0, a5: 0}
        for d in donors:
            inv[d] = 0
        equipped = {"cur": None}

        player = Reference(None, (-55.40, 29.80, 0.15), form_id=0x14)
        player.GetItemCount = lambda f: inv.get(f, 0)  # type: ignore[attr-defined]
        player.IsEquipped = lambda f: equipped["cur"] is f  # type: ignore[attr-defined]
        player.EquipItem = lambda f, *_: equipped.__setitem__("cur", f)  # type: ignore[attr-defined]

        cage_state = {"lock_level": 100, "locked": True, "open": False, "anim": ""}
        cage_door = SimpleNamespace(
            SetLockLevel=lambda lv: cage_state.__setitem__("lock_level", int(lv)),
            Lock=lambda locked=True, as_owner=False: cage_state.__setitem__("locked", bool(locked)),
            SetOpen=lambda is_open=True: cage_state.__setitem__("open", bool(is_open)),
            PlayGamebryoAnimation=lambda anim, start_over=False, ease=0.0: cage_state.__setitem__("anim", str(anim)),
        )

        dummy_state = {"hp": 100.0, "dead": False, "restrained": False, "suit_hidden": 0.0, "stripped": 0}
        dummy = Reference(None, (-48.80, 30.00, 0.15), form_id=0x04000811)
        dummy.IsDead = lambda: dummy_state["dead"]  # type: ignore[attr-defined]
        dummy.Resurrect = lambda: dummy_state.__setitem__("dead", False)  # type: ignore[attr-defined]
        dummy.RemoveAllItems = lambda *_: dummy_state.__setitem__("stripped", dummy_state["stripped"] + 1)  # type: ignore[attr-defined]
        dummy.SetRestrained = lambda v: dummy_state.__setitem__("restrained", bool(v))  # type: ignore[attr-defined]
        dummy.GetValue = lambda av: dummy_state["hp"] if av is health_av else 0.0  # type: ignore[attr-defined]
        dummy.SetValue = lambda av, v: dummy_state.__setitem__("suit_hidden", v) if av is hide_suit_av else None  # type: ignore[attr-defined]
        dummy.DamageValue = lambda av, d: dummy_state.__setitem__("hp", dummy_state["hp"] - d)  # type: ignore[attr-defined]
        dummy.RestoreValue = lambda av, d: dummy_state.__setitem__("hp", dummy_state["hp"] + d)  # type: ignore[attr-defined]
        dummy.GetDistance = lambda other: 4.40  # type: ignore[attr-defined]

        logs: list[str] = []
        ns = dict(
            Log=logs.append,
            RegisterHooks=lambda: None,
            TIMER_POLL=1,
            initLogged=False,
            lastAmmo10mm=-1,
            lastAmmoCell=-1,
            lastAmmo5mm=-1,
            shots10mm=0,
            shotsCell=0,
            shots5mm=0,
            fullMag12Proven=False,
            fullChargeProven=False,
            burst5mmProven=False,
            targetActive=False,
            targetKilled=False,
            batonKilledTarget=False,
            rangedKilledTarget=False,
            targetHits=0,
            targetKillsTotal=0,
            lastTargetHp=0.0,
            TargetTrigger=object(),
            ArmoryCageDoorLocalId=0x001539,
            PortPlugin="FO4Port.esm",
            TargetDummy=dummy,
            BatonWeap=baton,
            Pistol10mm=pistol10,
            LaserMusketWeap=musket,
            MinigunWeap=minigun,
            Ammo10mm=a10,
            AmmoFusionCell=acell,
            Ammo5mm=a5,
            DonorRescueAxe=donors[0],
            DonorXm2311=donors[1],
            DonorOrion=donors[2],
            DonorMicrogun=donors[3],
            DonorAmmo45=donors[4],
            DonorAmmoLaser=donors[5],
            DonorAmmo777=donors[6],
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
        exec(compile(py_src, str(P5_QUEST_PSC), "exec"), ns)

        # 1. Start-of-game init logs once even if both OnInit and OnQuestInit fire
        ns["OnInit"]()
        ns["OnQuestInit"]()
        init_lines = [ln for ln in logs if "FO4SF_R11P5 init " in ln]
        self.assertEqual(len(init_lines), 1)
        self.assertIn("anim_audio_standin=RescueAxe_0x04F760,XM2311_0x24561C,Orion_0x2773C8,Microgun_0x0546CD", init_lines[0])

        # 2. Pick up Baton -> auto-equips; spawn target -> cage door opens via GetFormFromFile & dummy stripped unarmed
        inv[baton] = 1
        ns["OnItemAdded"](player, baton, 1, None, None, 0)
        self.assertIs(equipped["cur"], baton)

        ns["SpawnPracticeTarget"]("trigger_activate")
        self.assertEqual(cage_state, {"lock_level": 0, "locked": False, "open": True, "anim": "Open"})
        self.assertEqual(dummy_state["stripped"], 1)
        self.assertTrue(dummy_state["restrained"])
        self.assertAlmostEqual(dummy_state["hp"], 30.0, places=3)

        # 3. Kill dummy with Baton (3 swings of 10 dmg); verify no double-count when both OnTimer & OnDying fire
        dummy_state["hp"] = 0.0
        dummy_state["dead"] = True
        ns["OnTimer"](1)
        ns["OnDying"](dummy, player)
        self.assertTrue(ns["batonKilledTarget"])
        self.assertEqual(ns["targetKillsTotal"], 1)

        # 4. Reset target, pick up 10mm + Laser Musket + Minigun + ammo, fire full mag/charge/burst & score ranged kill
        ns["SpawnPracticeTarget"]("stage_20")
        self.assertEqual(dummy_state["stripped"], 2)
        self.assertFalse(dummy_state["dead"])
        for w, a, cnt in ((pistol10, a10, 48), (musket, acell, 72), (minigun, a5, 500)):
            inv[w] = 1
            inv[a] = cnt
            ns["OnItemAdded"](player, w, 1, None, None, 0)
            ns["OnItemAdded"](player, a, cnt, None, None, 0)
        self.assertIs(equipped["cur"], minigun)

        inv[a10] = 36
        inv[acell] = 70
        inv[a5] = 480
        dummy_state["hp"] = 0.0
        dummy_state["dead"] = True
        ns["OnTimer"](1)
        ns["OnDying"](dummy, player)

        self.assertTrue(ns["fullMag12Proven"])
        self.assertTrue(ns["fullChargeProven"])
        self.assertTrue(ns["burst5mmProven"])
        self.assertTrue(ns["rangedKilledTarget"])
        self.assertEqual(ns["targetKillsTotal"], 2)

        ns["LogScorecard"]("stage_30")
        self.assertTrue(
            any(
                "FO4SF_R11P5 summary tag=stage_30" in ln
                and "baton=1 pistol_10mm=1 laser_musket=1 minigun=1" in ln
                and "full_mag_12_proven=True full_charge_proven=True burst_5mm_proven=True" in ln
                and "target_kills=2 baton_kill=True ranged_kill=True donor_leaks=0" in ln
                for ln in logs
            ),
            logs,
        )

    def test_p5_files_and_card_hygiene_standins_and_p3_console_blocks(self) -> None:
        for path in (P5_STAGE_PY, P5_QUEST_PSC, P5_CARD_MD, HERE):
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM in {path.name}")
            txt = raw.decode("utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"Drive-letter path leak in {path.name}")

        card = P5_CARD_MD.read_text(encoding="utf-8")
        self.assertTrue(card.startswith("Titles: Fallout 4 -> all 7 Fallout titles"))
        for tok in (
            "RescueAxe",
            "0x0004F760",
            "XM2311",
            "0x0024561C",
            "Orion",
            "0x002773C8",
            "Microgun",
            "0x000546CD",
            "stand-in",
            "WeaponBolt",
            "LaserMusketCrank",
            "Minigun_Barrel",
            "BatonLowExt01",
            "BatonLowExt02",
            "BatonLowHandle",
            "Archive2.exe",
            "bs_crc32",
            "uninstall",
        ):
            self.assertIn(tok, card, f"missing expected token {tok!r} in {P5_CARD_MD.name}")

        # Every typed ```console block in round11-probe-p5-card.md must obey P3 (0 M/N/V)
        blocks = re.findall(r"```console\s*\n(.*?)```", card, flags=re.S)
        self.assertGreaterEqual(len(blocks), 1)
        for blk in blocks:
            for line in blk.splitlines():
                s = line.strip()
                if not s:
                    continue
                self.assertIsNone(p5.P3_FORBIDDEN_RE.search(s), f"P3 M/N/V violation in console line: {s!r}")

    @unittest.skipUnless(
        os.environ.get("FO4SF_R11_P5_STAGE")
        and Path(os.environ["FO4SF_R11_P5_STAGE"], "manifest.json").is_file(),
        "Set FO4SF_R11_P5_STAGE to live staged r11-p5-weapons directory to cross-check manifest.json",
    )
    def test_live_p5_manifest_matches_card_hashes(self) -> None:
        manifest_path = Path(os.environ["FO4SF_R11_P5_STAGE"]) / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = data["files"]
        card = P5_CARD_MD.read_text(encoding="utf-8")
        expected = {
            "core/FO4SFCoreValues.esm": (20441, "b69a8078447ab7c83572d58ac5c85e92cd14c3b7f038d5fbf0f9335753b4fadb"),
            "core/FO4SFNewGame.esm": (12688, "7fcbb12ff901daa2b392dba54948ea076f21db22d9eb20a6e2429a6baa45301e"),
            "exp/FO4SF_R11P5Weapons.esm": (2411, "f8b5378339ab726e7f3069e58a084a220082ff63faec29636803e4b8476538ff"),
            "exp/FO4SF_R11P5Weapons - Main.ba2": (1541379, "140669b5de6363c54f1beab66e2d187b9dc0a56fbbe12042e2599f023e52cba3"),
            "exp/FO4SF_R11P5Weapons - Textures.ba2": (40502897, "6b22ba04a39d4b13ff7fbebec12d651857a370f93059a240b7deac6508b6556b"),
            "assets/meshes/fo4sf/weapons/baton/fo4_baton.nif": (9937, "bc86420f4e293525a8ecb33a7424e07702446e033255f4ea8d76ceb6fbdd22d9"),
            "assets/meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif": (12525, "9c656214512c89ac3e965e58274d672dd337132c1aebc313389e9f46d38d9ed0"),
            "assets/meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif": (15928, "839161fc29bdb50709fe43dd9e5799b6e265fe6819ffa328ffffca5101ef3010"),
            "assets/meshes/fo4sf/weapons/minigun/fo4_minigun.nif": (12187, "010bbb3a19bfc493d70fd0f1cc5bb18d395ce69082109b515fdd22a11b25ebe1"),
        }
        for rel, (size_b, sha) in expected.items():
            self.assertIn(rel, files, f"manifest missing {rel}")
            self.assertEqual(files[rel]["size_bytes"], size_b)
            self.assertEqual(files[rel]["sha256"], sha)
            self.assertIn(f"`{size_b:,}`", card)
            self.assertIn(sha, card)


if __name__ == "__main__":
    unittest.main()
