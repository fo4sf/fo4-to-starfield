"""Unit tests for scripts/ui/make_pipboy_stage_ini.py and Task 1 Pip-Boy / menu / Papyrus contracts.

Uses purely synthetic in-memory AVM2 SWF bytecode and GNRL BA2 fixtures (zero game files or player logs).
"""
from __future__ import annotations

import io
import os
import re
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    str(ROOT / "src"),
    str(ROOT / "scripts" / "ui"),
    str(ROOT / "scripts" / "core"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle  # noqa: E402
import make_pipboy_stage_ini as mpsi  # noqa: E402
import make_probe_swf  # noqa: E402
import pipboy_map_store  # noqa: E402


def _u30(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def _swf_tag(code: int, body: bytes) -> bytes:
    return struct.pack("<HI", (code << 6) | 0x3F, len(body)) + body


class _AbcBuilder:
    """Minimal AVM2 DoABC encoder supporting QName, MultinameL, Slot, Const(String), and method bodies."""

    def __init__(self) -> None:
        self.strings: list[str] = []
        self.namespaces: list[tuple[int, int]] = []
        self.ns_sets: list[list[int]] = []
        self.multinames: list[bytes] = []
        self.methods = 0
        self.classes: list[dict] = []
        self.scripts: list[tuple[int, list[bytes]]] = []
        self.bodies: list[tuple[int, bytes]] = []

    def s(self, text: str) -> int:
        if text not in self.strings:
            self.strings.append(text)
        return self.strings.index(text) + 1

    def ns(self, kind: int, name: str) -> int:
        entry = (kind, self.s(name))
        if entry not in self.namespaces:
            self.namespaces.append(entry)
        return self.namespaces.index(entry) + 1

    def nsset(self, ns_indices: list[int]) -> int:
        self.ns_sets.append(list(ns_indices))
        return len(self.ns_sets)

    def qname(self, name: str, ns_idx: int) -> int:
        self.multinames.append(b"\x07" + _u30(ns_idx) + _u30(self.s(name)))
        return len(self.multinames)

    def multiname_l(self, nsset_idx: int) -> int:
        self.multinames.append(b"\x1B" + _u30(nsset_idx))
        return len(self.multinames)

    def method(self) -> int:
        self.methods += 1
        return self.methods - 1

    def trait_slot(self, name_mn: int, type_mn: int = 0) -> bytes:
        return _u30(name_mn) + b"\x00" + _u30(0) + _u30(type_mn) + _u30(0)

    def trait_const_str(self, name_mn: int, type_mn: int, value_str: str) -> bytes:
        return _u30(name_mn) + b"\x06" + _u30(0) + _u30(type_mn) + _u30(self.s(value_str)) + b"\x01"

    def trait_method(self, name_mn: int, method_id: int) -> bytes:
        return _u30(name_mn) + b"\x01" + _u30(0) + _u30(method_id)

    def trait_class(self, name_mn: int, class_idx: int) -> bytes:
        return _u30(name_mn) + b"\x04" + _u30(0) + _u30(class_idx)

    def to_bytes(self) -> bytes:
        out = bytearray(struct.pack("<HH", 16, 46))
        out += _u30(0) + _u30(0) + _u30(0)  # ints, uints, doubles
        out += _u30(len(self.strings) + 1)
        for text in self.strings:
            raw = text.encode("utf-8")
            out += _u30(len(raw)) + raw
        out += _u30(len(self.namespaces) + 1)
        for kind, sidx in self.namespaces:
            out += bytes([kind]) + _u30(sidx)
        out += _u30(len(self.ns_sets) + 1 if self.ns_sets else 0)
        for ns_list in self.ns_sets:
            out += _u30(len(ns_list)) + b"".join(_u30(x) for x in ns_list)
        out += _u30(len(self.multinames) + 1)
        for mn_raw in self.multinames:
            out += mn_raw
        out += _u30(self.methods)
        for _ in range(self.methods):
            out += _u30(0) + _u30(0) + _u30(0) + b"\x00"
        out += _u30(0)  # metadata
        out += _u30(len(self.classes))
        for c in self.classes:
            out += _u30(c["name"]) + _u30(c["super"]) + bytes([c["flags"]]) + _u30(0) + _u30(c["iinit"])
            out += _u30(len(c["traits"])) + b"".join(c["traits"])
        for c in self.classes:
            out += _u30(c["cinit"]) + _u30(len(c["static"])) + b"".join(c["static"])
        out += _u30(len(self.scripts))
        for init, traits in self.scripts:
            out += _u30(init) + _u30(len(traits)) + b"".join(traits)
        out += _u30(len(self.bodies))
        for method_id, code in self.bodies:
            out += _u30(method_id) + _u30(6) + _u30(3) + _u30(0) + _u30(2) + _u30(len(code)) + code + _u30(0) + _u30(0)
        return bytes(out)


def _wrap_swf(abc_bytes: bytes, compressed: bool = True) -> bytes:
    body = (
        make_probe_swf.rect(0, 876 * 20, 0, 700 * 20)
        + struct.pack("<HH", 30 << 8, 1)
        + _swf_tag(69, b"\x08\x00\x00\x00")
        + _swf_tag(82, struct.pack("<I", 1) + b"frame1\x00" + abc_bytes)
        + b"\x40\x00\x00\x00"
    )
    if compressed:
        return b"CWS" + bytes([15]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body)
    return b"FWS" + bytes([15]) + struct.pack("<I", 8 + len(body)) + body


def _build_shell_swf() -> bytes:
    abc = _AbcBuilder()
    pub = abc.ns(0x16, "")
    shared = abc.ns(0x16, "Shared")
    nss = abc.nsset([pub])

    cls_q = abc.qname("SyntheticShell", pub)
    base_q = abc.qname("MovieClip", pub)
    bgs_ext = abc.qname("BGSExternalInterface", shared)
    call_q = abc.qname("call", pub)
    code_obj_q = abc.qname("BGSCodeObj", pub)
    stage_q = abc.qname("stage", pub)
    page_q = abc.qname("currPage", pub)
    init_code_q = abc.qname("InitCodeObj", pub)
    dyn_idx = abc.multiname_l(nss)
    run_q = abc.qname("run", pub)

    iinit, cinit, run_m, sinit = (abc.method() for _ in range(4))
    abc.classes.append({
        "name": cls_q,
        "super": base_q,
        "flags": 0x01,
        "iinit": iinit,
        "cinit": cinit,
        "traits": [abc.trait_slot(code_obj_q), abc.trait_slot(page_q), abc.trait_method(run_q, run_m)],
        "static": [],
    })
    abc.scripts.append((sinit, [abc.trait_class(cls_q, 0)]))

    s_pop = abc.s("PopulatePipboyInfoObj")
    s_page = abc.s("onNewPage")
    s_tab = abc.s("onNewTab")
    s_scroll_start = abc.s("OnScrollingStarted")
    s_scroll_stop = abc.s("OnScrollingStopped")
    s_bgs_holder = abc.s("BGSCodeObj")

    code = (
        b"\xd0\x30"
        # BGSExternalInterface.call(this.BGSCodeObj, "PopulatePipboyInfoObj", local1)
        + b"\x60" + _u30(bgs_ext)
        + b"\xd0\x66" + _u30(code_obj_q)
        + b"\x2c" + _u30(s_pop)
        + b"\xd1"
        + b"\x4f" + _u30(call_q) + _u30(3)
        # BGSExternalInterface.call(this.stage["BGSCodeObj"], "OnScrollingStarted")
        + b"\x60" + _u30(bgs_ext)
        + b"\xd0\x66" + _u30(stage_q) + b"\x2c" + _u30(s_bgs_holder) + b"\x66" + _u30(dyn_idx)
        + b"\x2c" + _u30(s_scroll_start)
        + b"\x4f" + _u30(call_q) + _u30(2)
        # BGSExternalInterface.call(this.stage["BGSCodeObj"], "OnScrollingStopped")
        + b"\x60" + _u30(bgs_ext)
        + b"\xd0\x66" + _u30(stage_q) + b"\x2c" + _u30(s_bgs_holder) + b"\x66" + _u30(dyn_idx)
        + b"\x2c" + _u30(s_scroll_stop)
        + b"\x4f" + _u30(call_q) + _u30(2)
        # BGSExternalInterface.call(this.BGSCodeObj, "onNewPage", 0)
        + b"\x60" + _u30(bgs_ext) + b"\xd0\x66" + _u30(code_obj_q) + b"\x2c" + _u30(s_page) + b"\x24\x00"
        + b"\x4f" + _u30(call_q) + _u30(3)
        # BGSExternalInterface.call(this.BGSCodeObj, "onNewTab", 0)
        + b"\x60" + _u30(bgs_ext) + b"\xd0\x66" + _u30(code_obj_q) + b"\x2c" + _u30(s_tab) + b"\x24\x00"
        + b"\x4f" + _u30(call_q) + _u30(3)
        # Negative decoy: this.currPage.InitCodeObj(this.BGSCodeObj) -> must NOT record InitCodeObj!
        + b"\xd0\x66" + _u30(page_q)
        + b"\xd0\x66" + _u30(code_obj_q)
        + b"\x4f" + _u30(init_code_q) + _u30(1)
        + b"\x47"
    )
    abc.bodies = [(iinit, b"\xd0\x30\x47"), (cinit, b"\x47"), (run_m, code), (sinit, b"\x47")]
    return _wrap_swf(abc.to_bytes(), compressed=True)


def _build_stats_swf() -> bytes:
    abc = _AbcBuilder()
    pub = abc.ns(0x16, "")
    shared = abc.ns(0x16, "Shared")
    cls_q = abc.qname("SyntheticStatsPage", pub)
    base_q = abc.qname("MovieClip", pub)
    str_q = abc.qname("String", pub)
    bgs_ext = abc.qname("BGSExternalInterface", shared)
    call_q = abc.qname("call", pub)
    code_obj_q = abc.qname("codeObj", pub)
    stop_const_q = abc.qname("STOP_PERK_SOUND_FN", pub)
    use_stimpak_q = abc.qname("UseStimpak", pub)
    play_sound_q = abc.qname("PlaySound", pub)
    run_q = abc.qname("run", pub)

    iinit, cinit, run_m, sinit = (abc.method() for _ in range(4))
    abc.classes.append({
        "name": cls_q,
        "super": base_q,
        "flags": 0x01,
        "iinit": iinit,
        "cinit": cinit,
        "traits": [abc.trait_slot(code_obj_q), abc.trait_method(run_q, run_m)],
        "static": [abc.trait_const_str(stop_const_q, str_q, "StopPerkSound")],
    })
    abc.scripts.append((sinit, [abc.trait_class(cls_q, 0)]))
    s_ok = abc.s("UIPipBoyOK")

    code = (
        b"\xd0\x30"
        # BGSExternalInterface.call(this.codeObj, STOP_PERK_SOUND_FN) -> const trait resolution!
        + b"\x60" + _u30(bgs_ext)
        + b"\xd0\x66" + _u30(code_obj_q)
        + b"\x60" + _u30(stop_const_q)
        + b"\x4f" + _u30(call_q) + _u30(2)
        # Direct 0-arg call: this.codeObj.UseStimpak()
        + b"\xd0\x66" + _u30(code_obj_q)
        + b"\x4f" + _u30(use_stimpak_q) + _u30(0)
        # Direct 1-arg call: this.codeObj.PlaySound("UIPipBoyOK")
        + b"\xd0\x66" + _u30(code_obj_q)
        + b"\x2c" + _u30(s_ok)
        + b"\x4f" + _u30(play_sound_q) + _u30(1)
        + b"\x47"
    )
    abc.bodies = [(iinit, b"\xd0\x30\x47"), (cinit, b"\x47"), (run_m, code), (sinit, b"\x47")]
    return _wrap_swf(abc.to_bytes(), compressed=True)


def _build_map_swf() -> bytes:
    abc = _AbcBuilder()
    pub = abc.ns(0x16, "")
    shared = abc.ns(0x16, "Shared")
    cls_q = abc.qname("SyntheticMapPage", pub)
    base_q = abc.qname("MovieClip", pub)
    bgs_ext = abc.qname("BGSExternalInterface", shared)
    call_q = abc.qname("call", pub)
    code_obj_q = abc.qname("codeObj", pub)
    hc_q = abc.qname("CheckHardcoreModeFastTravel", pub)
    run_q = abc.qname("run", pub)

    iinit, cinit, run_m, sinit = (abc.method() for _ in range(4))
    abc.classes.append({
        "name": cls_q,
        "super": base_q,
        "flags": 0x01,
        "iinit": iinit,
        "cinit": cinit,
        "traits": [abc.trait_slot(code_obj_q), abc.trait_method(run_q, run_m)],
        "static": [],
    })
    abc.scripts.append((sinit, [abc.trait_class(cls_q, 0)]))
    s_refresh = abc.s("RefreshMapMarkers")
    s_gps = abc.s("functiononGPSModeButtonClicked")
    s_sound = abc.s("PlaySound")

    code = (
        b"\xd0\x30"
        # Direct 1-arg call returning bool: this.codeObj.CheckHardcoreModeFastTravel(false)
        + b"\xd0\x66" + _u30(code_obj_q)
        + b"\x27"  # pushfalse
        + b"\x46" + _u30(hc_q) + _u30(1)
        + b"\x29"  # pop
        # BGSExternalInterface.call(this.codeObj, "RefreshMapMarkers")
        + b"\x60" + _u30(bgs_ext) + b"\xd0\x66" + _u30(code_obj_q) + b"\x2c" + _u30(s_refresh)
        + b"\x4f" + _u30(call_q) + _u30(2)
        # BGSExternalInterface.call(this.codeObj, "functiononGPSModeButtonClicked")
        + b"\x60" + _u30(bgs_ext) + b"\xd0\x66" + _u30(code_obj_q) + b"\x2c" + _u30(s_gps)
        + b"\x4f" + _u30(call_q) + _u30(2)
        # Duplicate across movies to test deduplication: "PlaySound"
        + b"\x60" + _u30(bgs_ext) + b"\xd0\x66" + _u30(code_obj_q) + b"\x2c" + _u30(s_sound)
        + b"\x4f" + _u30(call_q) + _u30(2)
        + b"\x47"
    )
    abc.bodies = [(iinit, b"\xd0\x30\x47"), (cinit, b"\x47"), (run_m, code), (sinit, b"\x47")]
    return _wrap_swf(abc.to_bytes(), compressed=False)


def _build_boot_swf() -> bytes:
    abc = _AbcBuilder()
    pub = abc.ns(0x16, "")
    cls_q = abc.qname("SyntheticBoot", pub)
    base_q = abc.qname("MovieClip", pub)
    code_obj_q = abc.qname("BGSCodeObj", pub)
    hide_q = abc.qname("HideMenu", pub)
    run_q = abc.qname("run", pub)

    iinit, cinit, run_m, sinit = (abc.method() for _ in range(4))
    abc.classes.append({
        "name": cls_q,
        "super": base_q,
        "flags": 0x01,
        "iinit": iinit,
        "cinit": cinit,
        "traits": [abc.trait_slot(code_obj_q), abc.trait_method(run_q, run_m)],
        "static": [],
    })
    abc.scripts.append((sinit, [abc.trait_class(cls_q, 0)]))
    code = b"\xd0\x30\xd0\x66" + _u30(code_obj_q) + b"\x4f" + _u30(hide_q) + _u30(0) + b"\x47"
    abc.bodies = [(iinit, b"\xd0\x30\x47"), (cinit, b"\x47"), (run_m, code), (sinit, b"\x47")]
    return _wrap_swf(abc.to_bytes(), compressed=True)


def _build_gnrl_ba2(entries: list[tuple[str, bytes]]) -> bytes:
    """Build a minimal v1 GNRL BTDX archive in memory."""
    count = len(entries)
    payload_offset = 24 + 36 * count
    records = bytearray()
    payloads = bytearray()
    names_blob = bytearray()
    cur = payload_offset
    for name, raw in entries:
        packed = zlib.compress(raw)
        records += struct.pack("<I4sIIQIII", 0, b"swf\x00", 0, 0x00100100, cur, len(packed), len(raw), 0xBAADF00D)
        payloads += packed
        cur += len(packed)
        nb = name.encode("utf-8")
        names_blob += struct.pack("<H", len(nb)) + nb
    name_offset = payload_offset + len(payloads)
    header = struct.pack("<4sI4sIQ", b"BTDX", 1, b"GNRL", count, name_offset)
    return header + bytes(records) + bytes(payloads) + bytes(names_blob)


class StageIniGeneratorTests(unittest.TestCase):
    def _populate_synthetic_stage(self, stage_dir: Path) -> Path:
        iface = stage_dir / "Data" / "Interface"
        iface.mkdir(parents=True, exist_ok=True)
        (iface / "FO4SF_Fo4Shell.swf").write_bytes(_build_shell_swf())
        (iface / "Pipboy_StatsPage.swf").write_bytes(_build_stats_swf())
        (iface / "Pipboy_MapPage.swf").write_bytes(_build_map_swf())
        return iface

    def test_avm2_extraction_boot_staging_and_clean_stage2_ini(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage = root / "stage"
            iface = self._populate_synthetic_stage(stage)
            sounds = stage / "SFSE" / "Plugins" / "FO4SFPipboyMenuSounds"
            sounds.mkdir(parents=True, exist_ok=True)
            (sounds / "UIPipBoyOK.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

            ba2_path = root / "SyntheticInterface.ba2"
            boot_bytes = _build_boot_swf()
            ba2_path.write_bytes(_build_gnrl_ba2([("Interface\\PipboyBootSequence.swf", boot_bytes)]))

            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc = mpsi.main(["--stage", str(stage), "--fo4-ba2", str(ba2_path)])
            self.assertEqual(rc, 0)

            staged_boot = iface / "pipboybootsequence.swf"
            self.assertTrue(staged_boot.is_file())
            self.assertEqual(staged_boot.read_bytes(), boot_bytes)

            ini_path = stage / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini"
            self.assertTrue(ini_path.is_file())
            ini_txt = ini_path.read_text(encoding="utf-8")

            # Zero [Kit], [Page ...], or Kit* keys anywhere in the generated INI
            mpsi.assert_no_kit_entries(ini_txt)
            self.assertNotIn("[Kit]", ini_txt)
            self.assertNotIn("[Page ", ini_txt)
            self.assertIsNone(re.search(r"(?im)^\s*Kit\w*\s*=", ini_txt))

            for required_line in (
                "Stage=2",
                "Movie=FO4SF_Fo4Shell",
                "Pause=1",
                "CodeObj=1",
                "CodeObjSound=1",
                "PopulateInCall=0",
                "LateInvalidate=0",
                "StatActions=0",
                "InvDataAnswers=0",
                "RequirePickup=0",
                "BootMovie=pipboybootsequence",
                "BootOnFirstOpen=1",
                "ShellKeys=",
                "Map=1",
                "MapMenus=GalaxyStarMapMenu,SurfaceMap,MapMenu",
            ):
                self.assertIn(f"\n{required_line}\n", "\n" + ini_txt, required_line)

            m = re.search(r"^CodeObjNames=(.+)$", ini_txt, re.M)
            self.assertIsNotNone(m)
            names = m.group(1).split(",")
            expected = [
                "PopulatePipboyInfoObj",
                "OnScrollingStarted",
                "OnScrollingStopped",
                "onNewPage",
                "onNewTab",
                "StopPerkSound",
                "UseStimpak",
                "PlaySound",
                "CheckHardcoreModeFastTravel",
                "RefreshMapMarkers",
                "functiononGPSModeButtonClicked",
                "HideMenu",
            ]
            self.assertEqual(names, expected)
            self.assertNotIn("InitCodeObj", names)

    def test_coverage_check_fails_on_unallowed_omission_and_allows_negative_proof_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td) / "stage"
            self._populate_synthetic_stage(stage)

            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                rc_fail = mpsi.main(["--stage", str(stage), "--omit", "StopPerkSound"])
            self.assertEqual(rc_fail, 1)
            self.assertIn("Pipboy_StatsPage.swf:StopPerkSound", err_buf.getvalue())
            self.assertFalse((stage / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").exists())

            out_buf = io.StringIO()
            with redirect_stdout(out_buf):
                rc_neg = mpsi.main([
                    "--stage", str(stage),
                    "--omit", "StopPerkSound",
                    "--allow-omit", "StopPerkSound",
                ])
            self.assertEqual(rc_neg, 0)
            ini_txt = (stage / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
            names = re.search(r"^CodeObjNames=(.+)$", ini_txt, re.M).group(1).split(",")
            self.assertNotIn("StopPerkSound", names)
            self.assertIn("PopulatePipboyInfoObj", names)

    def test_kit_entry_guard_rejects_kit_sections_and_keys(self) -> None:
        for bad in (
            "[FO4SFPipboyMenu]\nStage=2\n\n[Kit]\nHeadingAt=88\n",
            "[FO4SFPipboyMenu]\nStage=2\n\n[Page STAT/KARMA]\nRow=A|B\n",
            "[FO4SFPipboyMenu]\nStage=2\nKitVersion=1\n",
        ):
            with self.assertRaises(mpsi.StageIniError):
                mpsi.assert_no_kit_entries(bad)

    def test_r4_refuses_output_paths_inside_git_worktree_or_game_install(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for marker_name, is_dir in ((".git", True), ("Starfield.exe", False), ("Fallout4.exe", False)):
                sub = root / f"unsafe_{marker_name.replace('.', '_')}"
                sub.mkdir(parents=True, exist_ok=True)
                marker = sub / marker_name
                if is_dir:
                    marker.mkdir(exist_ok=True)
                else:
                    marker.write_bytes(b"MZ")

                target = sub / "stage"
                with self.assertRaises(mpsi.StageIniError):
                    mpsi.refuse_unsafe_output_path(target)
                with self.assertRaises(pipboy_map_store.MapStoreError):
                    pipboy_map_store.refuse_unsafe_output_path(target)
                with self.assertRaises(make_core_bundle.BundleRefused):
                    make_core_bundle.refresh_pipboy_stage_for_bundle(str(root), str(target), str(root))

        # Also refuse the live Git worktree itself
        with self.assertRaises(mpsi.StageIniError):
            mpsi.refuse_unsafe_output_path(ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini")


class Task1CrossModuleContractsTests(unittest.TestCase):
    def test_1a_1b_1c_1d_1e_1f_1g_cpp_contracts(self) -> None:
        main_cpp = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp").read_text(encoding="utf-8")
        map_cpp = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "pipboy_map.cpp").read_text(encoding="utf-8")
        blocking_h = (ROOT / "sfse" / "common" / "blocking_menus.h").read_text(encoding="utf-8")

        # 1a: plain Object holder, zero CreateFunction holder (g_codeObjSelf), zero committed 49-name list
        self.assertNotIn("g_codeObjSelf", main_cpp)
        self.assertNotIn("kFo4ShellCodeObjNames", main_cpp)
        self.assertIn('root->CreateObject(&holder, "Object")', main_cpp)
        self.assertIn("step=code_obj_holder type=object", main_cpp)
        self.assertIn("step=movie_call_miss", main_cpp)

        # 1b: gated PopulateInCall + exact populate log format
        self.assertIn('ReadNumber(ini, L"PopulateInCall", 0)', main_cpp)
        self.assertIn(
            "step=populate page={} tab={} hp={:.0f}/{:.0f} ap={:.0f}/{:.0f} level={} special={},{},{},{},{},{},{} source={} paused={}",
            main_cpp,
        )

        # 1c: closing flag + onCodeObjDestruction logged before deferred UnregisterMap logs + destroy
        self.assertIn("step=code_obj_destruction movie={} called={}", main_cpp)
        teardown = main_cpp[main_cpp.index("void ShellHideTeardown("):main_cpp.index("bool ProcessPendingShellEvents(")]
        self.assertLess(
            teardown.index("step=code_obj_destruction movie={} called={}"),
            teardown.index("deferred.swap(g_deferredDestructionLogs);"),
        )

        # 1d: shared blocking_menus.h without FaderMenu + ProcessUserEvent Cancel log
        self.assertNotIn('"FaderMenu"', blocking_h)
        for req_menu in ("Console", "TextInputMenu", "MonocleMenu", "SecurityMenu", "SkillsMenu", "WorkshopMenu", "PhotoModeMenu"):
            self.assertIn(f'"{req_menu}"', blocking_h)
        self.assertIn("step=menu_guard registered={} count={}", blocking_h)
        self.assertIn("step=process_user_event name={} handled={} down={}", main_cpp)

        # 1e, 1f, 1g, X2: verified plugin prefix, zero map_file skipped=, per-slot StarMap block, RequirePickup & BootMovie
        self.assertIn("VerifyPluginCandidate(", map_cpp)
        self.assertNotIn("skipped=", map_cpp)
        self.assertIn("kMaxMapMenus = 16", map_cpp)
        self.assertIn("blocked menu={} route=create", map_cpp)
        self.assertIn("step=pipboy_pickup_required", main_cpp)
        self.assertIn("step=boot_sequence finished=1", main_cpp)

    def test_1h_no_unguarded_developer_notifications_in_lane_a_papyrus(self) -> None:
        lane_a_dirs = (
            "newgame",
            "mission",
            "rads",
            "survival",
            "workshop",
            "powerarmor",
            "progression",
            "combat",
            "reputation",
            "companions",
            "alife",
            "fort_hagen",
        )
        psc_files: list[Path] = []
        for sub in lane_a_dirs:
            d = ROOT / "scripts" / sub
            if d.is_dir():
                psc_files.extend(sorted(d.rglob("*.psc")))
        self.assertGreaterEqual(len(psc_files), 12)

        notif_re = re.compile(r'Debug\.Notification\(([^\n]+)\)')
        for psc in psc_files:
            txt = psc.read_text(encoding="utf-8")
            self.assertNotIn("When Freedom Calls:", txt, f"duplicate banner still present in {psc.name}")
            lines = txt.splitlines()
            for idx, line in enumerate(lines):
                if line.lstrip().startswith(";"):
                    continue
                m = notif_re.search(line)
                if not m:
                    continue
                arg = m.group(1)
                if "FO4SF" in arg or '"Vault 111"' in arg:
                    window = "\n".join(lines[max(0, idx - 4):idx + 1])
                    self.assertTrue(
                        ("TestMode" in window) or ("IsTestMode()" in window),
                        f"unguarded developer Debug.Notification at {psc.name}:{idx + 1}: {line.strip()}",
                    )

    def test_1g_1l_ui_docs_exist_and_stay_public_clean(self) -> None:
        docs = (
            ROOT / "docs" / "ui" / "starfield-map-menus.md",
            ROOT / "docs" / "ui" / "fo4-menus-hosting.md",
            ROOT / "docs" / "ui" / "fo4-hud-options.md",
        )
        banned = (
            re.compile(r"\b[A-Za-z]:[\\/]"),
            re.compile(r"/(?:users|home)/", re.I),
            re.compile(r"fo4sf-", re.I),
            re.compile(r"\bfal-\d+", re.I),
        )
        for doc in docs:
            self.assertTrue(doc.is_file(), f"missing {doc}")
            txt = doc.read_text(encoding="utf-8")
            self.assertGreater(len(txt), 400)
            for pat in banned:
                self.assertIsNone(pat.search(txt), f"forbidden pattern {pat.pattern!r} in {doc.name}")


if __name__ == "__main__":
    unittest.main()
