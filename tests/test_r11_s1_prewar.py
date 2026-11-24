"""Offline verification tests for Round 11 S1 Pre-War probe staging, Slot 3 integration, and card/P3 rules."""
from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    ROOT / "src",
    ROOT / "scripts" / "probes",
    ROOT / "scripts" / "prewar",
    ROOT / "scripts" / "ui",
    ROOT / "scripts" / "testing",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import build_prewar_quest  # noqa: E402
import make_probe_swf as swf  # noqa: E402
import probe_common as pc  # noqa: E402
import r12_card_validator  # noqa: E402
import stage_r11_s1_prewar as stager  # noqa: E402
from fo4sf import overlay  # noqa: E402
from fo4sf.launcher import launch_choices as lc  # noqa: E402
from fo4sf.planet import home_planet_spec as hspec, wb_records  # noqa: E402
from fo4sf.planet.esm import PluginWriter, Record, group_bytes, zbytes  # noqa: E402
from fo4sf.prewar import s1_spec, vault111_append as va  # noqa: E402


class _FakeSystem:
    def __init__(self, pids: list[int] | None = None) -> None:
        self._pids = pids or []

    def pids(self, image: str = "Starfield.exe") -> list[int]:
        return list(self._pids)


def _raw_rec(sig: bytes, fid: int, subs: list[tuple[bytes, bytes]], flags: int = 0) -> bytes:
    body = b"".join(s + struct.pack("<H", len(d)) + d for s, d in subs)
    return struct.pack("<4sIIIIHH", sig, len(body), flags, fid, 0, 581, 0) + body


def _raw_grup(label: bytes, gtype: int, payload: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(payload)) + label + struct.pack("<III", gtype, 0, 0) + payload


def _minimal_swf_bytes() -> bytes:
    body = (
        swf.rect(0, 800 * 20, 0, 600 * 20)
        + struct.pack("<HH", 30 << 8, 1)
        + swf.tag(swf.FILE_ATTRIBUTES, struct.pack("<I", swf.AS3))
        + swf.tag(swf.SHOW_FRAME)
        + swf.tag(swf.END)
    )
    return b"CWS" + bytes([12]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 6)


def _synth_slot1_fo4port_esm() -> bytes:
    tes4 = _raw_rec(
        b"TES4",
        0,
        [(b"HEDR", struct.pack("<fII", 0.96, 12, 0x00EFAB)), (b"MAST", b"Starfield.esm\x00"), (b"DATA", b"\x00" * 8)],
        flags=1,
    )
    stat_end = _raw_rec(b"STAT", 0x0100E199, [(b"EDID", b"FO4Port_doors_anim_end\x00")])
    stat_m = _raw_rec(b"STAT", 0x0100E200, [(b"EDID", b"FO4Port_MuseumPiece01\x00")])
    shell_fid = 0x0100EFAA
    shell_cell = _raw_rec(b"CELL", shell_fid, [(b"EDID", b"FO4Port_PrewarVault111\x00"), (b"DATA", struct.pack("<H", 1))])
    pers_ref = _raw_rec(
        b"REFR",
        0x0100EFA8,
        [(b"EDID", b"FO4Port_PrewarShellMarker\x00"), (b"NAME", struct.pack("<I", 0x0100E200)), (b"DATA", struct.pack("<6f", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))],
        flags=va.PERSISTENT_FLAG,
    )
    cell_grp = _raw_grup(
        b"CELL",
        0,
        _raw_grup(
            struct.pack("<I", 0),
            2,
            _raw_grup(
                struct.pack("<I", 0),
                3,
                shell_cell + _raw_grup(struct.pack("<I", shell_fid), 6, _raw_grup(struct.pack("<I", shell_fid), 8, pers_ref)),
            ),
        ),
    )
    return tes4 + _raw_grup(b"STAT", 0, stat_end + stat_m) + cell_grp


def _synth_home_world_and_strip(whome_data: Path, strip_dir: Path) -> None:
    whome_data.mkdir(parents=True, exist_ok=True)
    pw_home = PluginWriter(["Starfield.esm"])
    pw_home.add(Record(b"CLMT", pw_home.own(wb_records.HOME_CLIMATE), [(b"EDID", zbytes("FO4SFHomeClimate"))]))
    pw_home.add(Record(b"WATR", pw_home.own(wb_records.HOME_WATER), [(b"EDID", zbytes("FO4SFHomeDryWater"))]))
    pw_home.add(Record(b"LCTN", pw_home.own(hspec.SURFACE_LOC), [(b"EDID", zbytes("SFO4SFHome_PEarth_Surface"))]))
    pw_home.add(Record(b"BIOM", pw_home.own(hspec.BIOME), [(b"EDID", zbytes("FO4SFHomeBiome"))]))
    pw_home.add(Record(b"PNDT", pw_home.own(hspec.PLANET), [(b"EDID", zbytes("EarthPlanetData"))]))
    (whome_data / hspec.HOME_MASTER).write_bytes(pw_home.to_bytes())
    pc.pack_gnrl_ba2({"materials/terrain/fo4sfhomegrounddirt01.mat": b"{}"}, whome_data / "FO4SFHome - Main.ba2")
    mask_dds = overlay.dds_bc4(overlay.mask_array(4))
    pc.pack_dx10_ba2({"textures/fo4sfhome/dummy.dds": mask_dds}, whome_data / "FO4SFHome - Textures.ba2")
    for rel in (
        f"PlanetData/BiomeMaps/{hspec.DEFAULT_BODY_NAME}.biom",
        f"PlanetData/BiomeMaps/fo4sfhome.esm/{hspec.DEFAULT_BODY_NAME}.biom",
    ):
        p = whome_data / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"BIOM")

    strip_dir.mkdir(parents=True, exist_ok=True)
    pw_sanc = PluginWriter(["Starfield.esm", hspec.HOME_MASTER])
    home_idx = 1 << 24
    pw_sanc.add(
        Record(
            b"LCTN",
            pw_sanc.own(0x802),
            [(b"EDID", zbytes("FO4SF_PrewarSanctuaryWorldLocation")), (b"PNAM", struct.pack("<I", home_idx | hspec.SURFACE_LOC))],
        )
    )
    wrld = Record(
        b"WRLD",
        pw_sanc.own(0x800),
        [
            (b"EDID", zbytes("FO4SF_PrewarSanctuaryWorld")),
            (b"CNAM", struct.pack("<I", home_idx | wb_records.HOME_CLIMATE)),
            (b"NAM3", struct.pack("<I", home_idx | wb_records.HOME_WATER)),
            (b"BNAM", struct.pack("<I", home_idx | hspec.BIOME)),
        ],
    )
    (strip_dir / s1_spec.PLUGIN_PREWAR_WORLD).write_bytes(pw_sanc.to_bytes() + group_bytes("WRLD", wrld.to_bytes()))

    pw_reg = PluginWriter(["Starfield.esm", hspec.HOME_MASTER, s1_spec.PLUGIN_PREWAR_WORLD])
    pw_reg.add(Record(b"PNDT", home_idx | hspec.PLANET, [(b"EDID", zbytes("EarthPlanetData"))]))
    (strip_dir / "FO4SFPrewar_Sanctuary_Home.esm").write_bytes(pw_reg.to_bytes())

    btd_p = strip_dir / "Data" / "Terrain" / "FO4SF_PrewarSanctuaryWorld.btd"
    btd_p.parent.mkdir(parents=True, exist_ok=True)
    btd_p.write_bytes(b"BTD0" + b"\x00" * 64)
    mask_p = strip_dir / "Data" / "textures" / "terrain" / "overlaymasks" / "fo4sf_prewarsanctuaryworld.dds"
    mask_p.parent.mkdir(parents=True, exist_ok=True)
    mask_p.write_bytes(mask_dds)


def _synth_prewar_and_newgame(base: Path) -> dict[str, Path]:
    pq_dir = base / "prewar_stage"
    (pq_dir / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
    (pq_dir / "Data" / "sound" / "voice" / "fo4sfprewar.esm" / "genericmaleeventoned").mkdir(parents=True, exist_ok=True)
    pw_pq = PluginWriter(["Starfield.esm"])
    pw_pq.add(Record(b"QUST", pw_pq.own(0x800), [(b"EDID", zbytes("FO4SF_PrewarQuest"))]))
    (pq_dir / s1_spec.PLUGIN_PREWAR).write_bytes(pw_pq.to_bytes())
    (pq_dir / "Data" / "Scripts" / "FO4SF_PrewarQuest.pex").write_bytes(b"PEX:PREWAR_QUEST")
    (pq_dir / "Data" / "Scripts" / "FO4SF_PrewarStandIns.pex").write_bytes(b"PEX:PREWAR_STANDINS")
    (pq_dir / "Data" / "sound" / "voice" / "fo4sfprewar.esm" / "genericmaleeventoned" / "00f50001.wem").write_bytes(b"RIFF")

    ng_dir = base / "ng_stage"
    (ng_dir / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
    pw_ng = PluginWriter(["Starfield.esm"])
    pw_ng.add(Record(b"QUST", pw_ng.own(0x800), [(b"EDID", zbytes("FO4SF_NewGame"))]))
    (ng_dir / "FO4SFNewGame.esm").write_bytes(pw_ng.to_bytes())
    for sname in ("FO4SF_NewGameQuest.pex", "FO4SF_NewGameLooks.pex", "FO4SF_NewGameSpecial.pex", "FO4SF_NewGameVersion.pex"):
        (ng_dir / "Data" / "Scripts" / sname).write_bytes(f"PEX:{sname}".encode("ascii"))

    iface_dir = base / "Interface"
    iface_dir.mkdir(parents=True, exist_ok=True)
    (iface_dir / "FO4SF_Fo4Shell.swf").write_bytes(_minimal_swf_bytes())
    dll_src = base / "FO4SFPipboyMenu.dll"
    dll_src.write_bytes(b"MZ-SYNTHETIC-DLL")

    sf_dir = base / "Starfield"
    (sf_dir / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
    (sf_dir / "Data" / "SFSE" / "Plugins").mkdir(parents=True, exist_ok=True)
    (sf_dir / "Data" / "FO4Port.esm").write_bytes(b"OLD-FO4PORT")
    (sf_dir / "Data" / "FO4SFNewGame.esm").write_bytes(b"OLD-NEWGAME")
    (sf_dir / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").write_bytes(b"OLD-NG-PEX")
    (sf_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"OLD-DLL")
    (sf_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").write_bytes(b"OLD-INI")
    plugins_txt = base / "Plugins.txt"
    plugins_txt.write_text("# Starfield Plugins\n*FO4TerrainCore.esm\n*FO4TerrainCore_Mars.esm\n", encoding="utf-8", newline="\n")

    return {"pq_dir": pq_dir, "ng_dir": ng_dir, "iface_dir": iface_dir, "dll_src": dll_src, "sf_dir": sf_dir, "plugins_txt": plugins_txt}


class R11S1PrewarTests(unittest.TestCase):
    def test_start_places_enables_prewar_and_preserves_skip_prewar(self) -> None:
        doc = stager.build_s1_start_places_doc(stager.DEFAULT_BASE_START_PLACES)
        by_id = {row["id"]: row for row in doc["places"]}
        self.assertIn("fo4_prewar_sanctuary", by_id)
        self.assertIn("fo4_vault111", by_id)
        pre = by_id["fo4_prewar_sanctuary"]
        self.assertEqual(pre["mode"], "story")
        self.assertEqual(pre["plugin"], "FO4SFPrewar.esm")
        self.assertEqual(pre["space"], "FO4SF_PrewarSanctuaryWorld")
        self.assertEqual(pre["marker_edid"], "FO4SF_PrewarHouseSpawnMarker")
        self.assertTrue(pre["available"])
        self.assertTrue(by_id["fo4_vault111"]["available"])
        self.assertEqual(by_id["fo4_vault111"]["space"], "FO4Port_Vault111Cryo")

    def test_launcher_allows_prewar_when_fo4sfprewar_loaded(self) -> None:
        base_doc = json.loads(stager.DEFAULT_BASE_START_PLACES.read_text(encoding="utf-8"))
        s1_doc = stager.build_s1_start_places_doc(stager.DEFAULT_BASE_START_PLACES)
        with tempfile.TemporaryDirectory() as td:
            sp_path = Path(td) / "start_places.json"
            sp_path.write_text(json.dumps(s1_doc), encoding="utf-8")
            ws_path = stager.DEFAULT_WARFARE_STARTS
            avail, _reasons = lc.evaluate_start_places(
                start_places_path=str(sp_path),
                mode="story",
                loaded_plugins={"fo4sfprewar.esm", "fo4sfprewar_sanctuary.esm", "fo4port.esm", "fo4terraincore.esm"},
                loaded_places={
                    "markers": {"FO4SF_PrewarHouseSpawnMarker"},
                    "interior_cells": {"FO4Port_Vault111Cryo"},
                    "exterior_cells": {(0, -1), (-12, 12)},
                },
            )
            self.assertEqual([r.id for r in avail], ["fo4_prewar_sanctuary", "fo4_vault111"])

            payload = lc.resolve_and_build_launch_choices(
                {"start.mode": "story", "start.survival": False, "start.place": "fo4_prewar_sanctuary"},
                loaded_plugins={"fo4sfprewar.esm", "fo4sfprewar_sanctuary.esm", "fo4port.esm", "fo4terraincore.esm"},
                loaded_places={
                    "markers": {"FO4SF_PrewarHouseSpawnMarker"},
                    "interior_cells": {"FO4Port_Vault111Cryo"},
                    "exterior_cells": {(0, -1), (-12, 12)},
                },
                start_places_path=str(sp_path),
                warfare_starts_path=str(ws_path),
                nonce="test_nonce",
            )
            self.assertEqual(payload["place_id"], "fo4_prewar_sanctuary")
            self.assertEqual(payload["mode"], "story")

            # Without FO4SFPrewar.esm loaded, base start_places resolves only fo4_vault111 cleanly
            sp_base_path = Path(td) / "base_start_places.json"
            sp_base_path.write_text(json.dumps(base_doc), encoding="utf-8")
            avail_base, _ = lc.evaluate_start_places(
                start_places_path=str(sp_base_path),
                mode="story",
                loaded_plugins={"fo4port.esm", "fo4terraincore.esm"},
            )
            self.assertEqual([r.id for r in avail_base], ["fo4_vault111"])

    def test_build_tile_local_spec_forwards_hero_models(self) -> None:
        spec = build_prewar_quest.build_tile_local_spec(
            vertibird_model=stager.HERO_VERTIBIRD_MODEL,
            ext_lift_model=stager.HERO_EXT_LIFT_MODEL,
        )
        self.assertEqual(spec["vertibird_model"], stager.HERO_VERTIBIRD_MODEL)
        self.assertEqual(spec["ext_lift_model"], stager.HERO_EXT_LIFT_MODEL)
        self.assertIn("FO4SF_PrewarHouseSpawnMarker", spec["markers"])

    def test_synthetic_stage_verify_install_and_atomic_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slot1_esm = root / "slot1_FO4Port.esm"
            slot1_esm.write_bytes(_synth_slot1_fo4port_esm())
            whome_data = root / "whome_Data"
            strip_dir = root / "strip_dir"
            _synth_home_world_and_strip(whome_data, strip_dir)
            fx = _synth_prewar_and_newgame(root)

            stage_dir = root / "stage_s1"
            manifest = stager.stage_probe(
                out_dir=stage_dir,
                starfield_dir=fx["sf_dir"],
                fo4_data=root / "fo4_empty",
                whome_data_dir=whome_data,
                interface_dir=fx["iface_dir"],
                pipboy_dll=fx["dll_src"],
                slot1_port_esm=slot1_esm,
                strip_dir=strip_dir,
                prewar_dir=fx["pq_dir"],
                newgame_stage_dir=fx["ng_dir"],
                skip_port_ba2=True,
                skip_strip_assets=True,
                skip_voices=True,
                fast_ba2=True,
                clean=True,
                min_free_gb=0.0,
                system=_FakeSystem([]),
            )
            self.assertEqual(manifest["probe_id"], "r11-s1-prewar")
            self.assertEqual(manifest["port_slot2"]["append_report"]["start_id"], "0x00EFAB")

            ver = stager.verify_probe(stage_dir=stage_dir)
            self.assertTrue(ver["verified"])
            self.assertIn("fo4_prewar_sanctuary", ver["available_starts"])
            self.assertIn("fo4_vault111", ver["available_starts"])

            # Guard refusals on incompatible active plugins
            fx["plugins_txt"].write_text("*FO4SFRouteLoot.esm\n", encoding="utf-8")
            with self.assertRaises(pc.ProbeInstallError):
                stager.install_probe_cmd(
                    stage_dir=stage_dir, starfield_dir=fx["sf_dir"], plugins_txt=fx["plugins_txt"], min_free_gb=0.0, system=_FakeSystem([])
                )
            fx["plugins_txt"].write_text("*FO4TerrainCore_Home.esm\n", encoding="utf-8")
            with self.assertRaises(pc.ProbeInstallError):
                stager.install_probe_cmd(
                    stage_dir=stage_dir, starfield_dir=fx["sf_dir"], plugins_txt=fx["plugins_txt"], min_free_gb=0.0, system=_FakeSystem([])
                )

            # Clean install -> verify swapped files -> atomic uninstall restores originals byte-for-byte
            orig_plugins = "*FO4TerrainCore.esm\n*FO4TerrainCore_Mars.esm\n"
            fx["plugins_txt"].write_text(orig_plugins, encoding="utf-8")
            stager.install_probe_cmd(
                stage_dir=stage_dir,
                starfield_dir=fx["sf_dir"],
                plugins_txt=fx["plugins_txt"],
                version_tag="test-s1-tag",
                min_free_gb=0.0,
                allow_hardlink=False,
                system=_FakeSystem([]),
            )
            self.assertTrue(pc.probe_status(probe_id=stager.PROBE_ID, starfield_dir=fx["sf_dir"])["installed"])
            self.assertEqual((fx["sf_dir"] / "Data" / "FO4SFNewGame.esm").read_bytes(), (fx["ng_dir"] / "FO4SFNewGame.esm").read_bytes())

            pc.uninstall_probe(probe_id=stager.PROBE_ID, starfield_dir=fx["sf_dir"], system=_FakeSystem([]))
            self.assertFalse(pc.probe_status(probe_id=stager.PROBE_ID, starfield_dir=fx["sf_dir"])["installed"])
            self.assertEqual((fx["sf_dir"] / "Data" / "FO4Port.esm").read_bytes(), b"OLD-FO4PORT")
            self.assertEqual((fx["sf_dir"] / "Data" / "FO4SFNewGame.esm").read_bytes(), b"OLD-NEWGAME")
            self.assertEqual(fx["plugins_txt"].read_text(encoding="utf-8"), orig_plugins)

    def test_p3_batches_hops_and_card_valid(self) -> None:
        errs = pc.validate_batches_and_hops(
            activate_commands=stager.P3_ACTIVATE_COMMANDS,
            anchors=stager.S1_ANCHORS,
            hops=stager.S1_HOPS,
            max_axis_m=200.0,
            raise_on_error=False,
        )
        self.assertEqual(errs, [])
        if stager.DEFAULT_CARD_PATH.is_file():
            self.assertEqual(r12_card_validator.validate_r12_card_file(stager.DEFAULT_CARD_PATH), [])


if __name__ == "__main__":
    unittest.main()
