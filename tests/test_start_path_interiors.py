"""Unit tests for `IB1` start-path interiors (`--fo4-loot`, `--usable-beds-benches`, `--interactive-fidelity`,
and `scripts/terrain/interior_start_census.py`), including Rule R12 SHA-256 parity with all three switches off.

Uses 100% synthetic ESM/JSON fixtures — zero local game paths."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    str(ROOT / "src"),
    str(ROOT / "scripts"),
    str(ROOT / "scripts" / "terrain"),
    str(ROOT / "tests"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import fo4loot  # noqa: E402
import interior_batch as ib  # noqa: E402
import interior_start_census as isc  # noqa: E402
from pluginspike_fixture import ensure_pluginspike_dll  # noqa: E402
import port_promote  # noqa: E402
from test_pack_staging import (  # noqa: E402
    CD03411A_IB_FINISH_MAIN_BA2_SHA256,
    CD03411A_IB_FINISH_PARTS_JSON_SHA256,
    CD03411A_IB_FINISH_README_SHA256,
    CD03411A_IB_FINISH_TEX_BA2_SHA256,
    CD03411A_PLUGINSPIKE_DEFAULT_ESM_SHA256,
    CD03411A_PLUGINSPIKE_DEFAULT_FORMIDS_SHA256,
    CD03411A_PORT_PROMOTE_SHA256,
)


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(path: str | Path) -> str:
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _sub(sig: str, payload: bytes) -> bytes:
    return sig.encode("ascii") + struct.pack("<H", len(payload)) + payload


def _zstr(text: str) -> bytes:
    return text.encode("utf-8") + b"\x00"


def _rec(sig: str, fid: int, payload: bytes, *, flags: int = 0, form_version: int = 581) -> bytes:
    return struct.pack("<4sIIIIHH", sig.encode("ascii"), len(payload), flags, fid, 0, form_version, 0) + payload


def _grup(label: bytes, gtype: int, body: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<iII", gtype, 0, 0) + body


def _write_synthetic_starfield_master(path: Path) -> None:
    """Write a minimal synthetic `Starfield.esm` carrying the template records `Promotions.cs` duplicates:
      - `TERM` `0155A2` (`OE_AustinF_DeployMicrobe_Terminal`)
      - `FURN` `0027D5` (chair, `WBDT=0`, 1 marker)
      - `FURN` `1FA770` (bed, `WBDT=0`, `KWDA=[0x021B18 IsSleepFurniture]`, 1 marker)
      - `FURN` `2B6A63` / `2B6A62` / `2B6A61` / `2B6A65` (workbenches with `WBDT != 0`)
    """
    tes4 = _rec("TES4", 0, _sub("HEDR", struct.pack("<fII", 0.96, 1, 0x800)), flags=0x81)

    term = _rec(
        "TERM",
        0x0155A2,
        _sub("EDID", _zstr("SynthTerminalTemplate"))
        + _sub("WBDT", b"\x00")
        + _sub("SNAM", struct.pack("<4f12s", 0.0, -0.5, 0.0, 0.0, b"\x00" * 12)),
    )
    term_grup = _grup(b"TERM", 0, term)

    def make_furn(fid: int, edid: str, wbdt: int, keywords: tuple[int, ...] = (), major_flags: int = 0) -> bytes:
        kw_bytes = b""
        if keywords:
            kw_bytes = _sub("KSIZ", struct.pack("<I", len(keywords))) + _sub(
                "KWDA", b"".join(struct.pack("<I", k) for k in keywords)
            )
        payload = (
            _sub("EDID", _zstr(edid))
            + _sub("MODL", _zstr("Markers\\SynthTemplate.nif"))
            + kw_bytes
            + _sub("MNAM", struct.pack("<I", 1))
            + _sub("WBDT", bytes([wbdt]))
            + _sub("FNPR", struct.pack("<HH", 2, 1))
            + _sub("SNAM", struct.pack("<4f12s", 0.0, -0.6, 0.0, 0.0, b"\x00" * 12))
        )
        return _rec("FURN", fid, payload, flags=major_flags)

    furn_records = b"".join([
        make_furn(0x0027D5, "SynthChairTemplate", wbdt=0),
        make_furn(0x1FA770, "SynthBedTemplate", wbdt=0, keywords=(0x021B18, 0x1FA760), major_flags=0x00080080),
        make_furn(0x2B6A63, "SynthWeaponBench", wbdt=2),
        make_furn(0x2B6A62, "SynthArmorBench", wbdt=7),
        make_furn(0x2B6A61, "SynthChemBench", wbdt=5),
        make_furn(0x2B6A65, "SynthCookingBench", wbdt=5),
    ])
    furn_grup = _grup(b"FURN", 0, furn_records)
    path.write_bytes(tes4 + term_grup + furn_grup)


def _write_synthetic_fallout4_esm(path: Path) -> None:
    """Write a synthetic `Fallout4.esm` with `MISC`, `ALCH`, `WEAP`, `LVLI` (nested + cyclic), `CONT`, and `FURN`."""
    tes4 = _rec("TES4", 0, _sub("HEDR", struct.pack("<fII", 1.0, 1, 0x800)), flags=0x01, form_version=131)

    # Items:
    # 0x050001 DeskFan01 (MISC, converted in manifest)
    # 0x050002 Stimpak01 (ALCH, converted in manifest)
    # 0x050003 FusionCore01 (AMMO, converted in manifest)
    # 0x050004 PipePistol01 (WEAP, NOT in manifest -> unconverted fallback)
    # 0x050005 NoModelToken (MISC, no MODL -> fallback)
    misc_recs = b"".join([
        _rec(
            "MISC",
            0x050001,
            _sub("EDID", _zstr("DeskFan01"))
            + _sub("FULL", _zstr("Desk Fan"))
            + _sub("MODL", _zstr("Props\\DeskFan01.nif"))
            + _sub("DATA", struct.pack("<if", 14, 3.0)),
            form_version=131,
        ),
        _rec(
            "MISC",
            0x050005,
            _sub("EDID", _zstr("NoModelToken")) + _sub("DATA", struct.pack("<if", 1, 0.0)),
            form_version=131,
        ),
    ])
    alch_recs = _rec(
        "ALCH",
        0x050002,
        _sub("EDID", _zstr("Stimpak01"))
        + _sub("FULL", _zstr("Stimpak"))
        + _sub("MODL", _zstr("Props\\Stimpak01.nif"))
        + _sub("DATA", struct.pack("<f", 0.1)),
        form_version=131,
    )
    ammo_recs = _rec(
        "AMMO",
        0x050003,
        _sub("EDID", _zstr("FusionCore01"))
        + _sub("FULL", _zstr("Fusion Core"))
        + _sub("MODL", _zstr("Props\\FusionCore01.nif")),
        form_version=131,
    )
    weap_recs = _rec(
        "WEAP",
        0x050004,
        _sub("EDID", _zstr("PipePistol01"))
        + _sub("FULL", _zstr("Pipe Pistol"))
        + _sub("MODL", _zstr("Weapons\\Pipe\\PipePistol.nif")),
        form_version=131,
    )

    def lvlo(form_id: int, count: int = 1, level: int = 1) -> bytes:
        return _sub("LVLO", struct.pack("<H2sIH2s", level, b"\x00\x00", form_id, count, b"\x00\x00"))

    # Leveled lists:
    # 0x060001 LvliOuter -> 0x060002 LvliInner (count 2) + 0x050004 PipePistol01 (unconverted)
    # 0x060002 LvliInner -> 0x060001 LvliOuter (cycle!) + 0x050002 Stimpak01 (converted, count 2)
    # 0x060003 LvliUnconvertedOnly -> 0x050004 PipePistol01 + 0x050005 NoModelToken
    lvli_recs = b"".join([
        _rec("LVLI", 0x060001, _sub("EDID", _zstr("LvliOuter")) + lvlo(0x060002, 2) + lvlo(0x050004, 1), form_version=131),
        _rec("LVLI", 0x060002, _sub("EDID", _zstr("LvliInner")) + lvlo(0x060001, 1) + lvlo(0x050002, 2), form_version=131),
        _rec("LVLI", 0x060003, _sub("EDID", _zstr("LvliUnconvertedOnly")) + lvlo(0x050004, 1) + lvlo(0x050005, 1), form_version=131),
    ])

    def cnto(form_id: int, count: int) -> bytes:
        return _sub("CNTO", struct.pack("<Ii", form_id, count))

    # Containers:
    # 0x070001 ContMuseumDesk: DeskFan01 x2 + Caps001 (0x00000F) x15 + BobbyPin (0x00000A) x3
    # 0x070002 ContMedkitLvli: LvliOuter x1 -> resolves Stimpak01 x2, logs partial unconverted PipePistol01
    # 0x070003 ContCivicTrunk: FusionCore01 x1 + DeskFan01 x1
    # 0x070004 ContUnconverted: LvliUnconvertedOnly x1 -> all fail -> falls back to container_table (Credits only)
    # 0x070005 ContEmpty: no CNTO entries -> falls back to container_table (Credits only)
    cont_recs = b"".join([
        _rec("CONT", 0x070001, _sub("EDID", _zstr("ContMuseumDesk")) + cnto(0x050001, 2) + cnto(0x00000F, 15) + cnto(0x00000A, 3), form_version=131),
        _rec("CONT", 0x070002, _sub("EDID", _zstr("ContMedkitLvli")) + cnto(0x060001, 1), form_version=131),
        _rec("CONT", 0x070003, _sub("EDID", _zstr("ContCivicTrunk")) + cnto(0x050003, 1) + cnto(0x050001, 1), form_version=131),
        _rec("CONT", 0x070004, _sub("EDID", _zstr("ContUnconverted")) + cnto(0x060003, 1), form_version=131),
        _rec("CONT", 0x070005, _sub("EDID", _zstr("ContEmpty")), form_version=131),
    ])

    body = (
        tes4
        + _grup(b"MISC", 0, misc_recs)
        + _grup(b"ALCH", 0, alch_recs)
        + _grup(b"AMMO", 0, ammo_recs)
        + _grup(b"WEAP", 0, weap_recs)
        + _grup(b"LVLI", 0, lvli_recs)
        + _grup(b"CONT", 0, cont_recs)
    )
    path.write_bytes(body)


class StartPathInteriorsTests(unittest.TestCase):
    @classmethod
    def _dll(cls) -> str:
        return ensure_pluginspike_dll(ROOT)

    def test_r12_parity_all_three_switches_off_matches_cd03411a(self):
        """With `--fo4-loot`, `--usable-beds-benches`, and `--interactive-fidelity` OFF (defaults),
        `port_promote.py`, `PluginSpike.dll`, and `interior_batch.py` match pinned `cd03411a` SHA-256 constants."""
        dll = self._dll()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # 1. port_promote.py default output == CD03411A_PORT_PROMOTE_SHA256
            containers = root / "containers.json"
            items = root / "items.json"
            cell_p = root / "TestCell01.json"
            containers.write_text(json.dumps({"default": {"name": None, "items": []}, "by_editor_id": {}}), encoding="utf-8")
            items.write_text(
                json.dumps({
                    "default": {"name": None, "value": 5, "weight": 0.5},
                    "by_editor_id": {"DeskFan*": {"name": "Desk Fan", "value": 12, "weight": 3.0}},
                }),
                encoding="utf-8",
            )
            cell_p.write_text(
                json.dumps({
                    "cell": "TestCell01",
                    "refs": [{
                        "formkey": "001000:DLCCoast.esm",
                        "base_formkey": "002000:Fallout4.esm",
                        "type": "MiscItem",
                        "base_editor_id": "DeskFan01",
                        "model": "Props\\DeskFan01.nif",
                        "pos": [0.0, 0.0, 0.0],
                        "rot": [0.0, 0.0, 0.0],
                        "scale": 1.0,
                        "disabled": 0,
                    }],
                }),
                encoding="utf-8",
            )
            out_prom = root / "promote_default" / "promote.json"
            self.assertEqual(
                port_promote.main(["--out", str(out_prom), "--containers-table", str(containers), "--items-table", str(items), str(cell_p)]),
                0,
            )
            self.assertEqual(_sha256_text(out_prom), CD03411A_PORT_PROMOTE_SHA256)

            # 2. PluginSpike default output == CD03411A_PLUGINSPIKE_DEFAULT_*_SHA256
            sf_data = root / "sf_data"
            sf_data.mkdir()
            man_p = root / "manifest.json"
            acadia_p = root / "DLC03Acadia.json"
            man_p.write_text(
                json.dumps({
                    "items": [{"editor_id": "FO4Port_Wall01", "model": "fo4port\\dlc03\\wall01.nif", "source": "DLC03\\Wall01.nif"}],
                    "failures": [],
                }),
                encoding="utf-8",
            )
            acadia_p.write_text(
                json.dumps({
                    "schema_version": 3,
                    "cell": "DLC03Acadia",
                    "cell_name": "Acadia",
                    "location_formkey": "004000:DLCCoast.esm",
                    "location_editor_id": "DLC03AcadiaLocation",
                    "location_name": "Acadia",
                    "refs": [{
                        "formkey": "004001:DLCCoast.esm",
                        "base_formkey": "004002:DLCCoast.esm",
                        "type": "Static",
                        "base_editor_id": "DLC03Wall01",
                        "model": "DLC03\\Wall01.nif",
                        "pos": [70.0, 140.0, 0.0],
                        "rot": [0.0, 0.0, 0.0],
                        "scale": 1.0,
                        "disabled": 0,
                    }],
                }),
                encoding="utf-8",
            )
            out_spike = root / "out_spike"
            subprocess.run(
                ["dotnet", dll, str(out_spike), str(man_p), str(acadia_p)],
                check=True,
                env=dict(os.environ, STARFIELD_DATA=str(sf_data)),
                capture_output=True,
            )
            self.assertEqual(_sha256_file(out_spike / "FO4Port.esm"), CD03411A_PLUGINSPIKE_DEFAULT_ESM_SHA256)
            self.assertEqual(_sha256_text(out_spike / "formids.json"), CD03411A_PLUGINSPIKE_DEFAULT_FORMIDS_SHA256)

            # 3. interior_batch.py build CLI defaults all 3 switches OFF and finish() matches cd03411a
            captured_ns = {}

            def capture_build(parsed_ns):
                captured_ns["ns"] = parsed_ns
                return 0

            orig_build_fn = ib.build
            ib.build = capture_build
            try:
                self.assertEqual(
                    ib.main([
                        "build", "--plan", "p.json", "--batch", "1", "--base", "b", "--base-exports", "be",
                        "--core", "c", "--work", "w", "--out", "o", "--fo4-data", "f", "--starfield", "s",
                        "--content-resources", "cr.zip", "--texconv", "tx.exe", "--collision-template", "ct.nif",
                        "--fo4export", "fe.dll", "--pluginspike", "ps.dll",
                    ]),
                    0,
                )
            finally:
                ib.build = orig_build_fn

            parsed = captured_ns["ns"]
            self.assertFalse(parsed.fo4_loot)
            self.assertFalse(parsed.usable_beds_benches)
            self.assertFalse(parsed.interactive_fidelity)

            work = root / "work"
            (work / "meshes" / "fo4port").mkdir(parents=True)
            (work / "textures" / "fo4port").mkdir(parents=True)
            (work / "meshes" / "fo4port" / "m.nif").write_bytes(b"NIFDATA")
            (work / "textures" / "fo4port" / "t.dds").write_bytes(b"DDSDATA")
            plan_p = root / "plan.json"
            plan_p.write_text(json.dumps({"batches": []}), encoding="utf-8")
            base_dir = root / "base"
            core_dir = root / "core"
            base_dir.mkdir()
            core_dir.mkdir()
            (base_dir / "FO4Port.esm").write_bytes(ib.companion_plugin_bytes())
            (base_dir / "formids.json").write_text("{}", encoding="utf-8")

            stage = root / "interiors_b01"
            port_dir = stage / "port"
            port_dir.mkdir(parents=True)
            (port_dir / "FO4Port.esm").write_bytes(ib.companion_plugin_bytes())

            def fake_build_archive(_a, out_ba2, folders, fmt):
                Path(out_ba2).write_bytes(b"BTDX:" + fmt.encode("ascii") + b":" + ",".join(folders).encode("ascii"))

            orig_ba = ib.deploy_starfield.build_archive
            ib.deploy_starfield.build_archive = fake_build_archive
            try:
                ns = ib.argparse.Namespace(
                    batch=1,
                    out=str(stage),
                    work=str(work),
                    starfield=str(root),
                    base=str(base_dir),
                    core=str(core_dir),
                    plan=str(plan_p),
                    plugin_name="",
                    prefix="",
                    animated_doors=False,
                    pack_ratio=None,
                    fo4_loot=False,
                    usable_beds_benches=False,
                    interactive_fidelity=False,
                )
                pack_info = ib.pack(ns, str(port_dir), None, None, str(stage / "build.log"))
                rc = ib.finish(ns, {}, {"pack": pack_info}, {"CellA": {"result": "converted"}}, 0.0, None)
            finally:
                ib.deploy_starfield.build_archive = orig_ba

            self.assertEqual(rc, 0)
            res_doc = json.loads((stage / "result.json").read_text(encoding="utf-8"))
            self.assertNotIn("start_path_switches", res_doc)
            self.assertEqual(_sha256_text(stage / "README.txt"), CD03411A_IB_FINISH_README_SHA256)
            self.assertEqual(_sha256_file(port_dir / "FO4Port - Main.ba2"), CD03411A_IB_FINISH_MAIN_BA2_SHA256)
            self.assertEqual(_sha256_file(port_dir / "FO4Port - Textures.ba2"), CD03411A_IB_FINISH_TEX_BA2_SHA256)
            self.assertEqual(_sha256_text(port_dir / "textures_parts.json"), CD03411A_IB_FINISH_PARTS_JSON_SHA256)

    def test_fo4loot_resolver_handles_nested_and_cyclic_lvli_and_logs_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            fo4_esm = Path(tmp) / "Fallout4.esm"
            _write_synthetic_fallout4_esm(fo4_esm)
            idx = fo4loot.Fo4LootIndex.from_plugins([str(fo4_esm)])

            # Cyclic LVLI expansion terminates cleanly and returns unique leaf items in deterministic BFS order.
            leaves = idx.lvli_leaves("060001:Fallout4.esm")
            self.assertEqual(leaves, [("050004:Fallout4.esm", 1), ("050002:Fallout4.esm", 2)])

            manifest_models = {
                "meshes/props/deskfan01.nif": "fo4port\\props\\deskfan01.nif",
                "meshes/props/stimpak01.nif": "fo4port\\props\\stimpak01.nif",
                "meshes/props/fusioncore01.nif": "fo4port\\props\\fusioncore01.nif",
            }
            cont_entries = [
                {"src": "001001:Fallout4.esm", "edid": "FO4Port_cont_070001_fallout4", "name": "Desk", "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
                {"src": "001002:Fallout4.esm", "edid": "FO4Port_cont_070002_fallout4", "name": "First Aid", "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
                {"src": "001004:Fallout4.esm", "edid": "FO4Port_cont_070004_fallout4", "name": "Crate", "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
                {"src": "001005:Fallout4.esm", "edid": "FO4Port_cont_070005_fallout4", "name": "Empty Box", "items": [{"form": "Starfield.esm:00000F", "count": 10}]},
            ]
            ref_bases = {
                "001001:Fallout4.esm": ("070001:Fallout4.esm", "ContMuseumDesk"),
                "001002:Fallout4.esm": ("070002:Fallout4.esm", "ContMedkitLvli"),
                "001004:Fallout4.esm": ("070004:Fallout4.esm", "ContUnconverted"),
                "001005:Fallout4.esm": ("070005:Fallout4.esm", "ContEmpty"),
            }
            loot_items, rep = fo4loot.resolve_containers_fo4_loot(
                cont_entries,
                ref_bases,
                idx,
                manifest_models,
                edid_for_item_fn=lambda fk: f"FO4Port_misc_{fk[:6].lower()}_fallout4",
                item_meta_fn=lambda fk, meta: (meta.get("full") or "Item", meta.get("value") or 10, meta.get("weight") or 0.5),
            )
            self.assertEqual([li["edid"] for li in loot_items], [
                "FO4Port_misc_050001_fallout4",
                "FO4Port_misc_050002_fallout4",
            ])
            # Container 1: converted Desk Fan x2 + Starfield Credits x15 + Digipick x3
            self.assertEqual(cont_entries[0]["items"], [
                {"form": "self:FO4Port_misc_050001_fallout4", "count": 2},
                {"form": "Starfield.esm:00000F", "count": 15},
                {"form": "Starfield.esm:00000A", "count": 3},
            ])
            # Container 2: cyclic LVLI resolved Stimpak x2 and logged partial unconverted leaf
            self.assertEqual(cont_entries[1]["items"], [
                {"form": "self:FO4Port_misc_050002_fallout4", "count": 2},
            ])
            # Containers 3 & 4: fell back to container_table Credits and logged reasons
            self.assertEqual(cont_entries[2]["items"], [{"form": "Starfield.esm:00000F", "count": 10}])
            self.assertEqual(cont_entries[3]["items"], [{"form": "Starfield.esm:00000F", "count": 10}])
            self.assertEqual(rep["containers_fo4_resolved"], 2)
            self.assertEqual(rep["containers_non_credit_loot"], 2)
            self.assertEqual(rep["containers_table_fallback"], 2)
            reasons = [fb["reason"] for fb in rep["fallbacks"]]
            self.assertTrue(any(r.startswith("lvli_partial_unconverted") for r in reasons), reasons)
            self.assertIn("lvli_no_converted_leaf", reasons)
            self.assertIn("no_cnto_entries_converted", reasons)
            self.assertIn("empty_fo4_cnto", reasons)

    def test_start_path_five_interiors_individual_switches_all_three_on_and_census_cli(self):
        """End-to-end verification across all 5 start-path interiors + 1 non-start-path cell:
        tests all 3 switches OFF, each switch ON individually, and all 3 ON together, then verifies
        `interior_start_census.py` and `interior_batch.py start-census` per-cell and aggregate counts."""
        dll = self._dll()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf_dir = root / "sf"
            sf_data = sf_dir / "Data"
            sf_data.mkdir(parents=True)
            _write_synthetic_starfield_master(sf_data / "Starfield.esm")

            fo4_dir = root / "fo4_data"
            fo4_dir.mkdir()
            fo4_esm = fo4_dir / "Fallout4.esm"
            _write_synthetic_fallout4_esm(fo4_esm)

            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps({
                    "items": [
                        {"editor_id": "FO4Port_Wall", "model": "fo4port\\wall.nif", "source": "meshes\\Architecture\\Wall.nif"},
                        {"editor_id": "FO4Port_Door", "model": "fo4port\\door.nif", "source": "meshes\\Doors\\RoomDoor.nif",
                         "door": {"anim_graph": "SimpleOpenClose01.agx", "skeleton": "fo4port\\d\\s.rig",
                                  "animations": "fo4port\\d\\a", "origin_offset": [0, 0, 0]}},
                        {"editor_id": "FO4Port_DeskCont", "model": "fo4port\\desk.nif", "source": "meshes\\Furniture\\DeskCont.nif"},
                        {"editor_id": "FO4Port_Medkit", "model": "fo4port\\medkit.nif", "source": "meshes\\SetDressing\\Medkit.nif"},
                        {"editor_id": "FO4Port_Trunk", "model": "fo4port\\trunk.nif", "source": "meshes\\Containers\\Trunk.nif"},
                        {"editor_id": "FO4Port_Crate", "model": "fo4port\\crate.nif", "source": "meshes\\Containers\\Crate.nif"},
                        {"editor_id": "FO4Port_Chair", "model": "fo4port\\chair.nif", "source": "meshes\\Furniture\\Chair01.nif"},
                        {"editor_id": "FO4Port_Bed", "model": "fo4port\\bed.nif", "source": "meshes\\Furniture\\BedMattress01.nif"},
                        {"editor_id": "FO4Port_WeapBench", "model": "fo4port\\wbench.nif", "source": "meshes\\Furniture\\WorkbenchWeaponsA.nif"},
                        {"editor_id": "FO4Port_ArmorBench", "model": "fo4port\\abench.nif", "source": "meshes\\Furniture\\WorkbenchArmorA.nif"},
                        {"editor_id": "FO4Port_ChemBench", "model": "fo4port\\cbench.nif", "source": "meshes\\Furniture\\WorkbenchChemistryA.nif"},
                        {"editor_id": "FO4Port_CookStove", "model": "fo4port\\cook.nif", "source": "meshes\\Furniture\\CookingStove01.nif"},
                        {"editor_id": "FO4Port_PowerArmor", "model": "fo4port\\pa.nif", "source": "meshes\\Furniture\\PowerArmorStation01.nif"},
                        {"editor_id": "FO4Port_Switch", "model": "fo4port\\switch.nif", "source": "meshes\\SetDressing\\Switch01.nif"},
                        {"editor_id": "FO4Port_DeskFan", "model": "fo4port\\props\\deskfan01.nif", "source": "meshes\\Props\\DeskFan01.nif"},
                        {"editor_id": "FO4Port_Stimpak", "model": "fo4port\\props\\stimpak01.nif", "source": "meshes\\Props\\Stimpak01.nif"},
                        {"editor_id": "FO4Port_FusionCore", "model": "fo4port\\props\\fusioncore01.nif", "source": "meshes\\Props\\FusionCore01.nif"},
                    ],
                    "failures": [],
                }),
                encoding="utf-8",
            )

            furn_export = root / "fo4_furniture.json"
            furn_export.write_text(
                json.dumps({
                    "furniture": {
                        "0C1001:Fallout4.esm": {
                            "editor_id": "NpcChairSit01",
                            "name": "Chair",
                            "bench_type": "None",
                            "keywords": ["AnimFurnChairSitAnims"],
                            "entry_points": [{"type": "Sit", "points": "Front"}],
                        },
                        "0C1002:Fallout4.esm": {
                            "editor_id": "NpcBedMattressSleep01",
                            "name": "Mattress",
                            "bench_type": "None",
                            "keywords": ["AnimFurnBedSleep"],
                            "entry_points": [{"type": "Lay", "points": "Left"}],
                        },
                        "0C1003:Fallout4.esm": {
                            "editor_id": "WorkbenchWeaponsA",
                            "name": "Weapons Workbench",
                            "bench_type": "CreateObject",
                            "keywords": [],
                            "entry_points": [{"type": "Sit", "points": "Front"}],
                        },
                        "0C1004:Fallout4.esm": {
                            "editor_id": "WorkbenchArmorA",
                            "name": "Armor Workbench",
                            "bench_type": "Armor",
                            "keywords": [],
                            "entry_points": [{"type": "Sit", "points": "Front"}],
                        },
                        "0C1005:Fallout4.esm": {
                            "editor_id": "WorkbenchChemistryA",
                            "name": "Chemistry Station",
                            "bench_type": "Alchemy",
                            "keywords": [],
                            "entry_points": [{"type": "Sit", "points": "Front"}],
                        },
                        "0C1006:Fallout4.esm": {
                            "editor_id": "CookingStove01",
                            "name": "Cooking Stove",
                            "bench_type": "Alchemy",
                            "keywords": [],
                            "entry_points": [{"type": "Sit", "points": "Front"}],
                        },
                        "0C1007:Fallout4.esm": {
                            "editor_id": "PowerArmorStation01",
                            "name": "Power Armor Station",
                            "bench_type": "PowerArmor",
                            "keywords": [],
                            "entry_points": [{"type": "Sit", "points": "Front"}],
                        },
                    }
                }),
                encoding="utf-8",
            )

            exports_dir = root / "exports"
            exports_dir.mkdir()

            def mk_ref(fk: str, rtype: str, edid: str, base_fk: str, model: str, x: float = 0.0, **extra) -> dict:
                d = {
                    "formkey": f"{fk}:Fallout4.esm",
                    "base_formkey": f"{base_fk}:Fallout4.esm",
                    "type": rtype,
                    "base_editor_id": edid,
                    "model": model,
                    "pos": [x, 0.0, 0.0],
                    "rot": [0.0, 0.0, 0.0],
                    "scale": 1.0,
                    "disabled": 0,
                }
                d.update(extra)
                return d

            kw_defs = [
                {"formkey": "000CC1:Fallout4.esm", "editor_id": "SynthLinkKeyword", "record_flags": 0,
                 "name": None, "notes": None, "display_name": None, "type": "None", "type_value": 0,
                 "color": None, "attraction_rule": None},
                {"formkey": "195411:Fallout4.esm", "editor_id": "MultirefLOD", "record_flags": 0,
                 "name": None, "notes": None, "display_name": None, "type": "None", "type_value": 0,
                 "color": None, "attraction_rule": None},
            ]

            cells_spec = {
                "ConcordMuseum01": {
                    "schema_version": 3,
                    "cell": "ConcordMuseum01",
                    "formkey": "017DF7:Fallout4.esm",
                    "referenced_keywords": kw_defs,
                    "refs": [
                        mk_ref("100001", "Static", "EnableMarker", "00001F", "", 0.0, persistent=True),
                        mk_ref(
                            "100002", "Static", "Wall01", "080001", "Architecture\\Wall.nif", 70.0,
                            enable_parent={"reference": "100001:Fallout4.esm", "flags": 1},
                            linked_references=[
                                {"keyword_or_reference": "000CC1:Fallout4.esm", "reference": "100003:Fallout4.esm"},
                                {"keyword_or_reference": "195411:Fallout4.esm", "reference": "100003:Fallout4.esm"},
                            ],
                        ),
                        mk_ref(
                            "100003", "Door", "RoomDoor01", "080002", "Doors\\RoomDoor.nif", 140.0,
                            lock_data={"level": 25, "key": None, "flags": 0, "unused": 0},
                            activate_parents={"flags": 1, "parents": [{"reference": "100004:Fallout4.esm", "delay": 0.0}]},
                        ),
                        mk_ref(
                            "10000B", "Door", "RoomDoor01", "080002", "Doors\\RoomDoor.nif", 175.0,
                            activate_parents={"flags": 1, "parents": [{"reference": "100004:Fallout4.esm", "delay": 0.5}]},
                        ),
                        mk_ref("100004", "Activator", "Switch01", "080003", "SetDressing\\Switch01.nif", 210.0),
                        mk_ref("100005", "Container", "ContMuseumDesk", "070001", "Furniture\\DeskCont.nif", 280.0),
                        mk_ref("100006", "Container", "ContUnconverted", "070004", "Containers\\Crate.nif", 350.0),
                        mk_ref("100007", "Furniture", "NpcChairSit01", "0C1001", "Furniture\\Chair01.nif", 420.0),
                        mk_ref("100008", "Furniture", "NpcBedMattressSleep01", "0C1002", "Furniture\\BedMattress01.nif", 490.0),
                        mk_ref("100009", "Furniture", "WorkbenchWeaponsA", "0C1003", "Furniture\\WorkbenchWeaponsA.nif", 560.0),
                        mk_ref("10000A", "Furniture", "PowerArmorStation01", "0C1007", "Furniture\\PowerArmorStation01.nif", 630.0),
                    ],
                },
                "ConcordSpeakeasy01": {
                    "schema_version": 3,
                    "cell": "ConcordSpeakeasy01",
                    "formkey": "0788D4:Fallout4.esm",
                    "refs": [
                        mk_ref(
                            "200001", "Container", "ContMedkitLvli", "070002", "SetDressing\\Medkit.nif", 0.0,
                            lock_data={"level": 50, "key": None, "flags": 0, "unused": 0},
                        ),
                        mk_ref("200002", "Furniture", "NpcBedMattressSleep01", "0C1002", "Furniture\\BedMattress01.nif", 70.0),
                    ],
                },
                "ConcordWorkhouse01": {
                    "schema_version": 3,
                    "cell": "ConcordWorkhouse01",
                    "formkey": "0E3CC4:Fallout4.esm",
                    "refs": [
                        mk_ref("300001", "Static", "EnableMarker", "00001F", "", 0.0, persistent=True),
                        mk_ref(
                            "300002", "Static", "Wall01", "080001", "Architecture\\Wall.nif", 70.0,
                            enable_parent={"reference": "300001:Fallout4.esm", "flags": 0},
                        ),
                        mk_ref("300003", "Furniture", "WorkbenchArmorA", "0C1004", "Furniture\\WorkbenchArmorA.nif", 140.0),
                        mk_ref("300004", "Furniture", "WorkbenchChemistryA", "0C1005", "Furniture\\WorkbenchChemistryA.nif", 210.0),
                    ],
                },
                "ConcordCivicAccess01": {
                    "schema_version": 3,
                    "cell": "ConcordCivicAccess01",
                    "formkey": "03776D:Fallout4.esm",
                    "referenced_keywords": kw_defs,
                    "refs": [
                        mk_ref("400001", "Container", "ContCivicTrunk", "070003", "Containers\\Trunk.nif", 0.0),
                        mk_ref("400002", "Furniture", "CookingStove01", "0C1006", "Furniture\\CookingStove01.nif", 70.0),
                        mk_ref(
                            "400003", "Static", "Wall01", "080001", "Architecture\\Wall.nif", 140.0,
                            linked_references=[{"keyword_or_reference": "000CC1:Fallout4.esm", "reference": "400001:Fallout4.esm"}],
                        ),
                    ],
                },
                "SanctuaryRootCellar01": {
                    "schema_version": 3,
                    "cell": "SanctuaryRootCellar01",
                    "formkey": "0A36EA:Fallout4.esm",
                    "referenced_keywords": kw_defs,
                    "refs": [
                        mk_ref(
                            "500001", "Container", "ContMuseumDesk", "070001", "Furniture\\DeskCont.nif", 0.0,
                            lock_data={"level": 75, "key": None, "flags": 0, "unused": 0},
                        ),
                        mk_ref("500002", "Furniture", "NpcBedMattressSleep01", "0C1002", "Furniture\\BedMattress01.nif", 70.0),
                        mk_ref("500003", "Furniture", "WorkbenchWeaponsA", "0C1003", "Furniture\\WorkbenchWeaponsA.nif", 140.0),
                        mk_ref(
                            "500004", "Static", "Wall01", "080001", "Architecture\\Wall.nif", 210.0,
                            linked_references=[{"keyword_or_reference": "000CC1:Fallout4.esm", "reference": "500001:Fallout4.esm"}],
                        ),
                    ],
                },
                "OtherInterior01": {
                    "schema_version": 3,
                    "cell": "OtherInterior01",
                    "formkey": "099999:Fallout4.esm",
                    "refs": [
                        mk_ref("600001", "Container", "ContCivicTrunk", "070003", "Containers\\Trunk.nif", 0.0),
                        mk_ref("600002", "Furniture", "WorkbenchChemistryA", "0C1005", "Furniture\\WorkbenchChemistryA.nif", 70.0),
                    ],
                },
            }

            export_paths: list[str] = []
            for cname, cdoc in cells_spec.items():
                cp = exports_dir / f"{cname}.json"
                cp.write_text(json.dumps(cdoc), encoding="utf-8")
                export_paths.append(str(cp))

            tables = ROOT / "scripts" / "terrain" / "clusters"
            env = dict(os.environ, STARFIELD_DATA=str(sf_data))

            def run_variant(tag: str, *, fo4_loot_on: bool, beds_benches_on: bool, fidelity_on: bool) -> tuple[Path, dict]:
                out_dir = root / f"build_{tag}"
                out_dir.mkdir()
                prom_args = [
                    "--out", str(out_dir / "promote.json"),
                    "--containers-table", str(tables / "container_table.json"),
                    "--items-table", str(tables / "item_table.json"),
                    "--starfield-data", str(sf_data),
                    "--furniture", str(furn_export),
                ]
                if fo4_loot_on:
                    prom_args += [
                        "--fo4-loot",
                        "--manifest", str(manifest_path),
                        "--fo4-plugin", str(fo4_esm),
                        "--loot-fallbacks-out", str(out_dir / "loot_fallbacks.json"),
                    ]
                if beds_benches_on:
                    prom_args += ["--usable-beds-benches"]
                self.assertEqual(port_promote.main(prom_args + export_paths), 0)

                spike_cmd = ["dotnet", dll, str(out_dir), str(manifest_path)]
                if fidelity_on:
                    spike_cmd.append("--interactive-fidelity")
                spike_cmd += export_paths
                subprocess.run(spike_cmd, check=True, env=env, capture_output=True)
                census = isc.measure_plugin(str(out_dir / "FO4Port.esm"))
                return out_dir, census

            # (A) All 3 switches OFF
            _dir_off, c_off = run_variant("all_off", fo4_loot_on=False, beds_benches_on=False, fidelity_on=False)
            sp_off = c_off["start_path_totals"]
            self.assertEqual(sp_off["cells"], 5)
            self.assertEqual(sp_off["containers_total"], 5)
            self.assertEqual(sp_off["containers_with_non_credit_loot"], 0)
            self.assertEqual(sp_off["usable_beds_and_benches"], 0)
            self.assertEqual(sp_off["usable_chairs"], 1)
            self.assertEqual(sp_off["carried_locks"], 0)
            self.assertEqual(sp_off["carried_enable_parents"], 0)
            self.assertEqual(sp_off["carried_linked_refs"], 0)
            self.assertEqual(sp_off["carried_activate_chains"], 0)

            # (B) --fo4-loot ON alone
            dir_loot, c_loot = run_variant("loot_only", fo4_loot_on=True, beds_benches_on=False, fidelity_on=False)
            sp_loot = c_loot["start_path_totals"]
            self.assertEqual(sp_loot["containers_with_non_credit_loot"], 4)
            self.assertEqual(sp_loot["containers_with_converted_fo4_loot"], 4)
            self.assertEqual(sp_loot["usable_beds_and_benches"], 0)
            self.assertEqual(sp_loot["carried_locks"], 0)
            self.assertTrue((dir_loot / "loot_fallbacks.json").is_file())
            fb_doc = json.loads((dir_loot / "loot_fallbacks.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(fb_doc["fallback_count"], 2)

            # (C) --usable-beds-benches ON alone
            _dir_bb, c_bb = run_variant("beds_benches_only", fo4_loot_on=False, beds_benches_on=True, fidelity_on=False)
            sp_bb = c_bb["start_path_totals"]
            self.assertEqual(sp_bb["containers_with_non_credit_loot"], 0)
            self.assertEqual(sp_bb["usable_beds"], 3)
            self.assertEqual(sp_bb["usable_benches"], 5)
            self.assertEqual(sp_bb["usable_beds_and_benches"], 8)
            self.assertEqual(sp_bb["usable_chairs"], 1)
            self.assertEqual(sp_bb["usable_furniture"], 9)  # PowerArmorStation01 skipped cleanly
            self.assertEqual(sp_bb["carried_locks"], 0)

            # (D) --interactive-fidelity ON alone
            _dir_fid, c_fid = run_variant("fidelity_only", fo4_loot_on=False, beds_benches_on=False, fidelity_on=True)
            sp_fid = c_fid["start_path_totals"]
            self.assertEqual(sp_fid["containers_with_non_credit_loot"], 0)
            self.assertEqual(sp_fid["usable_beds_and_benches"], 0)
            self.assertEqual(sp_fid["carried_locks"], 3)
            self.assertEqual(sp_fid["carried_enable_parents"], 2)
            self.assertEqual(sp_fid["carried_linked_refs"], 3)  # MultirefLOD excluded!
            self.assertEqual(sp_fid["carried_activate_chains"], 2)

            # (E) All 3 switches ON together + per-cell census CLI checks
            dir_all, c_all = run_variant("all_on", fo4_loot_on=True, beds_benches_on=True, fidelity_on=True)
            sp_all = c_all["start_path_totals"]
            self.assertEqual(sp_all["cells"], 5)
            self.assertEqual(c_all["totals"]["cells"], 6)
            self.assertEqual(sp_all["containers_with_non_credit_loot"], 4)
            self.assertEqual(sp_all["usable_beds"], 3)
            self.assertEqual(sp_all["usable_benches"], 5)
            self.assertEqual(sp_all["usable_beds_and_benches"], 8)
            self.assertEqual(sp_all["usable_chairs"], 1)
            self.assertEqual(sp_all["usable_furniture"], 9)
            self.assertEqual(sp_all["carried_locks"], 3)
            self.assertEqual(sp_all["carried_enable_parents"], 2)
            self.assertEqual(sp_all["carried_linked_refs"], 3)
            self.assertEqual(sp_all["carried_activate_chains"], 2)

            # Verify exact per-cell metrics across all 5 start-path interiors
            per_cell = c_all["cells"]
            self.assertEqual(
                {
                    k: (
                        v["containers_with_non_credit_loot"],
                        v["usable_beds"],
                        v["usable_benches"],
                        v["carried_locks"],
                        v["carried_enable_parents"],
                        v["carried_linked_refs"],
                    )
                    for k, v in per_cell.items()
                    if v["is_start_path"]
                },
                {
                    "FO4Port_ConcordCivicAccess01": (1, 0, 1, 0, 0, 1),
                    "FO4Port_ConcordMuseum01": (1, 1, 1, 1, 1, 1),
                    "FO4Port_ConcordSpeakeasy01": (1, 1, 0, 1, 0, 0),
                    "FO4Port_ConcordWorkhouse01": (0, 0, 2, 0, 1, 0),
                    "FO4Port_SanctuaryRootCellar01": (1, 1, 1, 1, 0, 1),
                },
            )

            # Test CLI `--start-path-only --out` and `interior_batch.py start-census --stage`
            census_out = root / "census_start_only.json"
            self.assertEqual(
                isc.main(["--plugin", str(dir_all / "FO4Port.esm"), "--start-path-only", "--out", str(census_out)]),
                0,
            )
            saved_census = json.loads(census_out.read_text(encoding="utf-8"))
            self.assertEqual(saved_census["totals"]["cells"], 5)
            self.assertNotIn("FO4Port_OtherInterior01", saved_census["cells"])

            fake_stage = root / "fake_stage"
            (fake_stage / "port").mkdir(parents=True)
            (fake_stage / "port" / "FO4Port.esm").write_bytes((dir_all / "FO4Port.esm").read_bytes())
            stage_census_out = root / "stage_census.json"
            self.assertEqual(
                ib.main(["start-census", "--stage", str(fake_stage), "--start-path-only", "--out", str(stage_census_out)]),
                0,
            )
            self.assertEqual(json.loads(stage_census_out.read_text(encoding="utf-8"))["totals"], saved_census["totals"])

            # Git worktree output is refused (R4)
            git_wt = root / "git_wt"
            (git_wt / ".git").mkdir(parents=True)
            self.assertEqual(
                isc.main(["--plugin", str(dir_all / "FO4Port.esm"), "--out", str(git_wt / "bad.json")]),
                1,
            )


if __name__ == "__main__":
    unittest.main()
