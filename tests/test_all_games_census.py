"""Synthetic unit tests for scripts/research/all_games_census.py.

100% self-contained byte fixtures (cross-platform Linux/Windows safe; zero game files required).
Covers:
  - Fallout 1 DAT v1 reader + raw/LZSS block decompression + SSL .int bytecode parser
  - Fallout 2 DAT v2 zlib reader + override layering + data/quests.txt & vault13.gam counters
  - Fallout Tactics .bos PKZIP + <world> zlib .mis FSM <Trigger>/<esh> parser
  - BSA v104 (0x68) reader (compressed + 0x0100 embedded names)
  - TES4/ESM streaming reader (QUST/DIAL/INFO/CTDA/SCEN/SCPT, 0x00040000 zlib, XXXX subrecords,
    ObScript SCTX tokenizer, and FO3/FNV quest dependency extractor)
  - Papyrus .psc source zip scanner & .pex (0xFA57C0DE) v3.9 / v3.12 / v3.15 bytecode parser
"""
from __future__ import annotations

import io
import os
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_RESEARCH = os.path.join(REPO_ROOT, "scripts", "research")
SRC_DIR = os.path.join(REPO_ROOT, "src")
for p in (SCRIPTS_RESEARCH, SRC_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import all_games_census as census  # noqa: E402


def _build_synthetic_ssl_int() -> bytes:
    """Construct a valid big-endian Interplay SSL `.int` binary with 2 procedures (`start`, `talk_p_proc`)."""
    # 42-byte startup stub
    stub = bytearray(b"\x00" * 42)
    # Identifier payload: >H len + null-padded strings (`start\x00`, `talk_p_proc\x00`)
    s1 = b"start\x00"
    s2 = b"talk_p_proc\x00"
    ident_entries = struct.pack(">H", len(s1)) + s1 + struct.pack(">H", len(s2)) + s2 + b"\xff\xff"
    # name_off is relative to start of `>I ident_size` field:
    # 4 (ident_size) + 2 (len prefix) = 6 for s1; 4 + 2 + len(s1) + 2 = 14 for s2
    off_s1 = 6
    off_s2 = 6 + len(s1) + 2

    # String table: empty (0) + 0xFFFFFFFF
    str_section = struct.pack(">II", len(ident_entries), 0xFFFFFFFF)[4:]  # helper check below
    _ = str_section
    header_part = bytearray()
    header_part.extend(stub)
    header_part.extend(struct.pack(">I", 2))  # 2 procedures
    # Placeholder proc records (filled once code_offset is known)
    proc_pos = len(header_part)
    header_part.extend(b"\x00" * (2 * 24))
    header_part.extend(struct.pack(">I", len(ident_entries)))
    header_part.extend(ident_entries)
    header_part.extend(struct.pack(">I", 0xFFFFFFFF))
    header_part.extend(struct.pack(">I", 0))  # 0 string bytes

    # Bytecode:
    # proc 0 (`start`): self_obj (0x80BC), push int 5 (0xC001 + >i 5), global_var (0x80C5), ret (0x800D)
    code_p0 = struct.pack(">HHiHH", 0x80BC, 0xC001, 5, 0x80C5, 0x800D)
    # proc 1 (`talk_p_proc`): dude_obj (0x80BF), set_global_var (0x80C6), gsay_reply (0x811E), giq_option (0x8121), ret (0x800D)
    code_p1 = struct.pack(">HHHHH", 0x80BF, 0x80C6, 0x811E, 0x8121, 0x800D)

    boff0 = len(header_part)
    boff1 = boff0 + len(code_p0)
    struct.pack_into(">IIIIII", header_part, proc_pos, off_s1, 0, 0, 0, boff0, 0)
    struct.pack_into(">IIIIII", header_part, proc_pos + 24, off_s2, 0, 0, 0, boff1, 0)

    return bytes(header_part) + code_p0 + code_p1


def _fo1_lzss_pack_literal_and_ref(literal_prefix: bytes, repeat_len: int) -> Tuple[bytes, int]:
    """Build a FO1 LZSS stream mixing a negative raw block and a positive LZSS ring-buffer block."""
    # Block 1: negative block header = raw literal_prefix
    b1 = struct.pack(">h", -len(literal_prefix)) + literal_prefix
    # Block 2: positive LZSS block encoding 1 literal 'A' at ring[4078] then 1 back-reference (offset=4078, len=repeat_len)
    # Flag byte bit 0 = 1 (literal), bit 1 = 0 (backref): flags = 0b00000001 = 0x01
    assert 3 <= repeat_len <= 18
    off = 4078
    lo = off & 0xFF
    hi = ((off >> 4) & 0xF0) | ((repeat_len - 3) & 0x0F)
    lz_payload = bytes([0x01, ord("A"), lo, hi])
    b2 = struct.pack(">h", len(lz_payload)) + lz_payload
    unpacked_total = len(literal_prefix) + 1 + repeat_len
    return b1 + b2, unpacked_total


def _build_fo1_dat_bytes(files_by_dir: dict[str, list[tuple[str, bytes, bool]]]) -> bytes:
    """Build a synthetic big-endian FO1 DAT v1 archive."""
    dirs = list(files_by_dir.keys())
    hdr = bytearray(struct.pack(">IIII", len(dirs), 0, 0, 0))
    for d in dirs:
        db = d.encode("latin-1")
        hdr.append(len(db))
        hdr.extend(db)

    # Compute directory table size first so offsets are exact
    tables_meta = []
    table_bytes_len = 0
    for d in dirs:
        table_bytes_len += 16
        prepared = []
        for fname, raw, compress in files_by_dir[d]:
            fb = fname.encode("latin-1")
            if compress:
                # Negative chunk header in FO1 LZSS = exact raw copy inside compressed stream
                packed = struct.pack(">h", -len(raw)) + raw
                attrs = 0x40
            else:
                packed = raw
                attrs = 0x20
            table_bytes_len += 1 + len(fb) + 16
            prepared.append((fb, attrs, len(raw), packed))
        tables_meta.append(prepared)

    data_offset = len(hdr) + table_bytes_len
    tables_buf = bytearray()
    payload_buf = bytearray()
    for prepared in tables_meta:
        tables_buf.extend(struct.pack(">IIII", len(prepared), 0, 0, 0))
        for fb, attrs, unp_len, packed in prepared:
            off = data_offset + len(payload_buf)
            payload_buf.extend(packed)
            tables_buf.append(len(fb))
            tables_buf.extend(fb)
            tables_buf.extend(struct.pack(">IIII", attrs, off, unp_len, len(packed) if attrs == 0x40 else 0))

    return bytes(hdr + tables_buf + payload_buf)


def _build_fo2_dat_bytes(entries: list[tuple[str, bytes, bool]]) -> bytes:
    """Build a synthetic little-endian FO2 DAT v2 archive."""
    data_buf = bytearray()
    tree_buf = bytearray(struct.pack("<I", len(entries)))
    for name, raw, compress in entries:
        off = len(data_buf)
        packed = zlib.compress(raw) if compress else raw
        data_buf.extend(packed)
        nb = name.encode("latin-1")
        tree_buf.extend(struct.pack("<I", len(nb)))
        tree_buf.extend(nb)
        tree_buf.extend(struct.pack("<BIII", 1 if compress else 0, len(raw), len(packed), off))
    total_size = len(data_buf) + len(tree_buf) + 8
    footer = struct.pack("<II", len(tree_buf), total_size)
    return bytes(data_buf + tree_buf + footer)


def _subrec(sig: bytes, data: bytes) -> bytes:
    if len(data) > 0xFFFF:
        return b"XXXX" + struct.pack("<HI", 4, len(data)) + sig + struct.pack("<H", 0) + data
    return sig + struct.pack("<H", len(data)) + data


def _rec(sig: bytes, fid: int, payload: bytes, *, compress: bool = False, fver: int = 2) -> bytes:
    flags = 0x00040000 if compress else 0
    body = struct.pack("<I", len(payload)) + zlib.compress(payload) if compress else payload
    return struct.pack("<4sIIIIHH", sig, len(body), flags, fid, 0, fver, 0) + body


def _grup(label: bytes, gtype: int, body: bytes) -> bytes:
    return struct.pack("<4sI4sIII", b"GRUP", 24 + len(body), label, gtype, 0, 0) + body


def _build_synthetic_pex(game_id: int, maj: int, minv: int, *, native_only: bool = False, empty_stub: bool = False) -> bytes:
    """Build a valid little-endian `0xFA57C0DE` `.pex` binary for v3.9 (FO4), v3.12 (SF), or v3.15 (FO76)."""
    strings = ["TestScript", "", "ScriptObject", "OnLoad", "DoWork", "Utility", "Wait", "None"]
    s_idx = {s: i for i, s in enumerate(strings)}

    buf = bytearray(struct.pack("<IBBHQ", 0xFA57C0DE, maj, minv, game_id, 0))
    for meta in (b"TestScript.psc", b"anon", b"ci"):
        buf.extend(struct.pack("<H", len(meta)) + meta)

    buf.extend(struct.pack("<H", len(strings)))
    for s in strings:
        sb = s.encode("utf-8")
        buf.extend(struct.pack("<H", len(sb)) + sb)

    buf.append(0)  # hasDebugInfo = 0
    buf.extend(struct.pack("<H", 0))  # userFlagCount = 0
    buf.extend(struct.pack("<H", 1))  # objectCount = 1

    obj_body = bytearray()
    obj_body.extend(struct.pack("<HH", s_idx["ScriptObject"], s_idx[""]))  # parent, doc
    obj_body.append(0)  # constFlag
    obj_body.extend(struct.pack("<I", 0x01 if native_only else 0x00))  # userFlags
    obj_body.extend(struct.pack("<H", s_idx[""]))  # autoStateName
    obj_body.extend(struct.pack("<H", 0))  # structCount
    obj_body.extend(struct.pack("<H", 0))  # varCount
    if game_id == 4:
        obj_body.extend(struct.pack("<H", 1))  # 1 Starfield Guard (after variables)
        obj_body.extend(struct.pack("<H", s_idx["DoWork"]))
    obj_body.extend(struct.pack("<H", 0))  # propCount

    # 1 state ("") with 1 function (`OnLoad`)
    obj_body.extend(struct.pack("<H", 1))
    obj_body.extend(struct.pack("<H", s_idx[""]))
    obj_body.extend(struct.pack("<H", 1))
    obj_body.extend(struct.pack("<H", s_idx["OnLoad"]))
    # Function header: retType(H), doc(H), uflags(I), flags(B: 0x02 if native_only else 0x00), params(H), locals(H)
    obj_body.extend(struct.pack("<HHIBHH", s_idx["None"], s_idx[""], 0, 0x02 if native_only else 0x00, 0, 0))

    if native_only or empty_stub:
        obj_body.extend(struct.pack("<H", 0))  # 0 instructions
    else:
        # 2 instructions:
        # 1) CallStatic (0x19): Utility, Wait, NoneVar(0), variadic int(1), float(1.0)
        # 2) CallMethod (0x17): DoWork, ident("TestScript"), NoneVar(0), variadic int(0)
        obj_body.extend(struct.pack("<H", 2))
        inst1 = (
            bytes([0x19])
            + bytes([1]) + struct.pack("<H", s_idx["Utility"])
            + bytes([1]) + struct.pack("<H", s_idx["Wait"])
            + bytes([0])
            + bytes([3]) + struct.pack("<i", 1)
            + bytes([4]) + struct.pack("<f", 1.0)
        )
        inst2 = (
            bytes([0x17])
            + bytes([1]) + struct.pack("<H", s_idx["DoWork"])
            + bytes([1]) + struct.pack("<H", s_idx["TestScript"])
            + bytes([0])
            + bytes([3]) + struct.pack("<i", 0)
        )
        obj_body.extend(inst1 + inst2)

    if game_id == 3:
        # FO76 v3.15 trailing networked variable index list
        obj_body.extend(struct.pack("<HH", 1, 0))

    buf.extend(struct.pack("<HI", s_idx["TestScript"], 4 + len(obj_body)))
    buf.extend(obj_body)
    return bytes(buf)


class TestAllGamesCensus(unittest.TestCase):
    def test_fo1_lzss_and_dat_v1_and_ssl_int(self) -> None:
        packed_lz, unp_len = _fo1_lzss_pack_literal_and_ref(b"HDR:", 6)
        dec = census.fo1_lzss_decompress(packed_lz, unp_len)
        self.assertEqual(dec, b"HDR:AAAAAAA")

        ssl_bytes = _build_synthetic_ssl_int()
        gam_bytes = b"// Globals\nGVAR_ALPHA := 0;\nGVAR_BETA := 1;\n"
        msg_bytes = b"{100}{}{ok}\n{101}{}{ok}\n"
        pro_ammo = b"\x00" * 32 + struct.pack(">I", 4) + b"\x00" * 12
        map_hdr = bytearray(240)
        struct.pack_into(">I", map_hdr, 0, 19)
        struct.pack_into(">iiiii", map_hdr, 32, 3, 12, 0, 0, 4)

        dat_raw = _build_fo1_dat_bytes({
            "DATA": [("VAULT13.GAM", gam_bytes, True)],
            "SCRIPTS": [("TEST.INT", ssl_bytes, True)],
            "TEXT\\ENGLISH\\DIALOG": [("TEST.MSG", msg_bytes, False)],
            "PROTO\\ITEMS": [("00000001.PRO", pro_ammo, False)],
            "MAPS": [("TEST.MAP", bytes(map_hdr), True)],
        })

        with census.Fo1DatReader(io.BytesIO(dat_raw)) as rdr:
            res = census.scan_classic_dat_set([("MASTER.DAT", rdr)], "Fallout 1")

        self.assertEqual(res["unique_entries"], 5)
        self.assertEqual(res["quests"]["vault13_gam_gvars"], 2)
        self.assertEqual(res["quests"]["msg_entries_english"], 2)
        self.assertEqual(res["quests"]["maps"], 1)
        self.assertEqual(res["quests"]["maps_with_header_script"], 1)
        self.assertEqual(res["scripts"]["compiled_int_count"], 1)
        self.assertEqual(res["scripts"]["total_procedures"], 2)
        self.assertEqual(res["shared_systems"]["item_prototypes_by_subtype"]["ammo"], 1)
        top_names = {x["name"]: x["count"] for x in res["scripts"]["top_40"]}
        self.assertEqual(top_names["proc:start"], 1)
        self.assertEqual(top_names["proc:talk_p_proc"], 1)
        self.assertEqual(top_names["self_obj"], 1)
        self.assertEqual(top_names["global_var"], 1)
        self.assertEqual(top_names["giq_option"], 1)

    def test_fo2_dat_v2_and_patch_overrides(self) -> None:
        ssl_bytes = _build_synthetic_ssl_int()
        quests_txt = b"# header\n0, 10, 1, 0, 100\n0, 11, 2, 0, 101\n3, 12, 1, 0, 102\n"
        v13_gam = b"GVAR_0 := 0;\nGVAR_1 := 0;\nGVAR_2 := 0;\n"

        base_dat = _build_fo2_dat_bytes([
            ("data\\quests.txt", quests_txt, True),
            ("data\\vault13.gam", v13_gam, True),
            ("scripts\\test.int", ssl_bytes, False),
        ])
        patch_dat = _build_fo2_dat_bytes([
            ("scripts\\test.int", ssl_bytes, True),
        ])

        with census.Fo2DatReader(io.BytesIO(base_dat)) as r1, census.Fo2DatReader(io.BytesIO(patch_dat)) as r2:
            res = census.scan_classic_dat_set([("master.dat", r1), ("patch000.dat", r2)], "Fallout 2")

        self.assertEqual(res["unique_entries"], 3)
        self.assertEqual(res["override_entries"], 1)
        self.assertEqual(res["quests"]["quests_txt_rows"], 3)
        self.assertEqual(res["quests"]["quests_txt_distinct_locations"], 2)
        self.assertEqual(res["quests"]["vault13_gam_gvars"], 3)

    def test_tactics_bos_and_mis_fsm_parser(self) -> None:
        world_inner = (
            b"<Trigger>\x00"
            + struct.pack("<I", 13) + b"Add Objective<esh>\x00"
            + struct.pack("<I", 12) + b"Set Variable<esh>\x00"
            + b"CVAR_M01_DONE\x00"
            + b"<gameEvent>\x00"
            + b"<speech_node>\x00"
        )
        mis_raw = b"<world>\x0068\x00" + struct.pack("<II", len(world_inner), len(world_inner)) + zlib.compress(world_inner)

        with tempfile.TemporaryDirectory() as td:
            bos_path = os.path.join(td, "mis-core_A.bos")
            with zipfile.ZipFile(bos_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("campaigns/missions/core/mission01.mis", mis_raw)
                zf.writestr("entities/recruits/rec01.ent", b"<entity>\x00")
                zf.writestr("entities/vehicles/veh01.ent", b"<entity>\x00")
                zf.writestr("gui/pip/icon.zar", b"<zar>\x00")
                zf.writestr("locale/game/perk.txt", "\ufeffperk_a = {1}\nperk_b = {2}\n".encode("utf-16-le"))

            res = census.scan_tactics_bos_archives([bos_path])

        self.assertEqual(res["quests"]["mis_total"], 1)
        self.assertEqual(res["quests"]["triggers_total"], 1)
        self.assertEqual(res["quests"]["add_objective_actions"], 1)
        self.assertEqual(res["quests"]["speech_nodes_total"], 1)
        self.assertEqual(res["quests"]["campaign_and_mission_vars"], 1)
        self.assertEqual(res["shared_systems"]["entities_by_category"]["recruits"], 1)
        self.assertEqual(res["shared_systems"]["entities_by_category"]["vehicles"], 1)
        self.assertEqual(res["shared_systems"]["locale_game_key_counts"]["perk.txt"], 2)
        top_map = {x["name"]: x["count"] for x in res["scripts"]["top_40"]}
        self.assertEqual(top_map["Add Objective"], 1)
        self.assertEqual(top_map["Set Variable"], 1)

    def test_bsa_v104_reader_embedded_and_compressed(self) -> None:
        # 1 folder ("menus"), 1 compressed file ("main.xml") with 0x0100 embedded BString name
        archive_flags = 0x0001 | 0x0002 | 0x0004 | 0x0100
        dir_raw = b"menus\x00"
        file_names_block = b"main.xml\x00"
        raw_content = b"<menu/>"
        emb_name = b"menus\\main.xml"
        payload = bytes([len(emb_name)]) + emb_name + struct.pack("<I", len(raw_content)) + zlib.compress(raw_content)

        folder_rec_off = 36
        file_block_off = folder_rec_off + 16
        names_off = file_block_off + 1 + len(dir_raw) + 16
        data_off = names_off + len(file_names_block)

        bsa_bytes = bytearray()
        bsa_bytes.extend(
            struct.pack(
                "<4s8I",
                b"BSA\x00",
                104,
                36,
                archive_flags,
                1,
                1,
                len(dir_raw),
                len(file_names_block),
                0,
            )
        )
        # folder record: hash, count=1, offset_plus_total_file_name_len
        bsa_bytes.extend(struct.pack("<QII", 1, 1, file_block_off + len(file_names_block)))
        bsa_bytes.append(len(dir_raw))
        bsa_bytes.extend(dir_raw)
        bsa_bytes.extend(struct.pack("<QII", 2, len(payload), data_off))
        bsa_bytes.extend(file_names_block)
        bsa_bytes.extend(payload)

        with census.BsaV104Reader(io.BytesIO(bytes(bsa_bytes))) as bsa:
            self.assertEqual(bsa.names, ["menus\\main.xml"])
            self.assertEqual(bsa.read("menus/main.xml"), raw_content)

    def test_tes4_esm_qust_scpt_xxxx_and_quest_dependencies(self) -> None:
        # Build a synthetic FO3/FNV ESM with:
        #  - SCPT 0x001000 (`MQ01Script`) with GameMode + SetStage + evp alias
        #  - QUST 0x002000 (`MQ01`, SCRI=0x001000, 2 INDX stages, 1 QOBJ, repeatable flag 0x09)
        #  - QUST 0x002001 (`MS01`, 1 INDX stage)
        #  - DIAL 0x003000 (`QSTI=0x002000`) + child GRUP(7) with compressed INFO 0x003001 (CTDA GetActorValue=14 + HasPerk=448 + SCTX)
        #  - PACK 0x004000 referencing QUST 0x002000 via CTDA param1 + oversized XXXX dummy subrecord check
        sctx_src = (
            b"scn MQ01Script\n"
            b"short bDone ; comment GetStage ignored\n"
            b"Begin GameMode\n"
            b"  if player.getav Speech >= 50\n"
            b"    SetStage MQ01 20\n"
            b"    evp\n"
            b"  endif\n"
            b"End\n\x00"
        )
        scpt_pay = (
            _subrec(b"EDID", b"MQ01Script\x00")
            + _subrec(b"SCHR", struct.pack("<4sIIII", b"\x00" * 4, 1, 32, 1, 1))
            + _subrec(b"SCTX", sctx_src)
            + _subrec(b"SCRO", struct.pack("<I", 0x002000))
        )
        qust_mq = (
            _subrec(b"EDID", b"MQ01\x00")
            + _subrec(b"SCRI", struct.pack("<I", 0x001000))
            + _subrec(b"DATA", bytes([0x09, 50, 0, 0, 0, 0, 0, 0]))
            + _subrec(b"INDX", struct.pack("<H", 10))
            + _subrec(b"INDX", struct.pack("<H", 20))
            + _subrec(b"QOBJ", struct.pack("<i", 10))
        )
        qust_ms = (
            _subrec(b"EDID", b"MS01\x00")
            + _subrec(b"DATA", bytes([0x00, 50]))
            + _subrec(b"INDX", struct.pack("<H", 10))
        )

        # CTDA: type(1), unk(3), val(4f), fn_id(2H @ 8), pad(2), param1(4I @ 12), param2(4I), runOn(4I), ref(4I) = 28 bytes
        ctda_av = struct.pack("<B3sfHHIIII", 0, b"\x00\x00\x00", 50.0, 14, 0, 18, 0, 2, 0x14)
        ctda_perk = struct.pack("<B3sfHHIIII", 0, b"\x00\x00\x00", 1.0, 448, 0, 0x5000, 0, 2, 0x14)
        info_pay = (
            _subrec(b"QSTI", struct.pack("<I", 0x002000))
            + _subrec(b"CTDA", ctda_av)
            + _subrec(b"CTDA", ctda_perk)
            + _subrec(b"SCTX", b"SetObjectiveCompleted MQ01 10 1\x00")
        )
        dial_rec = _rec(b"DIAL", 0x003000, _subrec(b"EDID", b"MQ01Topic\x00") + _subrec(b"QSTI", struct.pack("<I", 0x002000)))
        info_rec = _rec(b"INFO", 0x003001, info_pay, compress=True)

        ctda_pack_q = struct.pack("<B3sfHHIIII", 0, b"\x00\x00\x00", 10.0, 58, 0, 0x002000, 0, 0, 0)
        xxxx_sub = b"XXXX" + struct.pack("<HI", 4, 8) + b"UNKN" + struct.pack("<H", 0) + (b"\x01" * 8)
        pack_rec = _rec(b"PACK", 0x004000, _subrec(b"EDID", b"MQ01FollowPack\x00") + _subrec(b"CTDA", ctda_pack_q) + xxxx_sub)

        tes4_hdr = _rec(b"TES4", 0, _subrec(b"HEDR", struct.pack("<fII", 1.34, 5, 0x800)))
        esm_bytes = (
            tes4_hdr
            + _grup(b"SCPT", 0, _rec(b"SCPT", 0x001000, scpt_pay))
            + _grup(b"QUST", 0, _rec(b"QUST", 0x002000, qust_mq) + _rec(b"QUST", 0x002001, qust_ms))
            + _grup(b"DIAL", 0, dial_rec + _grup(struct.pack("<I", 0x003000), 7, info_rec))
            + _grup(b"PACK", 0, pack_rec)
        )

        with tempfile.TemporaryDirectory() as td:
            esm_path = os.path.join(td, "Synthetic.esm")
            with open(esm_path, "wb") as fp:
                fp.write(esm_bytes)

            scan = census.scan_esm_file(esm_path, is_ce2=False, parse_obscript=True)
            deps = census.extract_fo3_fnv_quest_dependencies(esm_path, ["MQ01"], ["MS01"])

        self.assertEqual(scan["qust_detail"]["quests"], 2)
        self.assertEqual(scan["qust_detail"]["stages_indx"], 3)
        self.assertEqual(scan["qust_detail"]["objectives_qobj"], 1)
        self.assertEqual(scan["qust_detail"]["repeatable_stages_flag"], 1)
        self.assertEqual(scan["dialogue_detail"]["dial_topics"], 1)
        self.assertEqual(scan["dialogue_detail"]["info_responses"], 1)
        self.assertEqual(scan["dialogue_detail"]["info_ctda_skill_or_av"], 1)
        self.assertEqual(scan["dialogue_detail"]["info_ctda_perk"], 1)
        self.assertEqual(scan["obscript_detail"]["scpt_records"], 1)
        self.assertEqual(scan["obscript_detail"]["scpt_with_sctx"], 1)
        self.assertEqual(scan["obscript_detail"]["blocks"]["Begin:GameMode"], 1)
        self.assertEqual(scan["obscript_detail"]["calls"]["GetActorValue"], 1)
        self.assertEqual(scan["obscript_detail"]["calls"]["EvaluatePackage"], 1)
        self.assertEqual(scan["obscript_detail"]["calls"]["SetStage"], 1)
        self.assertEqual(scan["obscript_detail"]["calls"]["SetObjectiveCompleted"], 1)

        mq_row = deps["main_10"][0]
        self.assertEqual(mq_row["edid"], "MQ01")
        self.assertEqual(mq_row["form_id"], "0x002000")
        self.assertEqual(mq_row["stage_count"], 2)
        self.assertEqual(mq_row["info_owned"], 1)
        self.assertEqual(mq_row["info_skill_av_checks"], 1)
        self.assertEqual(mq_row["pack_count"], 1)

    def test_psc_zip_and_pex_v39_v312_v315_parsers(self) -> None:
        psc_native = "ScriptName MyNative extends Form Native Hidden\nbool Function Ping() Native\n"
        psc_game = (
            "ScriptName MyQuest extends Quest\n"
            "{Doc comment mentioning FakeCall() ignored}\n"
            "Event OnQuestInit()\n"
            "  ; comment IgnoredCall()\n"
            "  String s = \"LiteralCall()\"\n"
            "  Utility.Wait(1.0)\n"
            "  SetStage(10)\n"
            "EndEvent\n"
        )
        with tempfile.TemporaryDirectory() as td:
            zpath = os.path.join(td, "Scripts.zip")
            with zipfile.ZipFile(zpath, "w") as zf:
                zf.writestr("Source/MyNative.psc", psc_native)
                zf.writestr("Source/MyQuest.psc", psc_game)
            psc_res = census.scan_psc_zip(zpath)

        self.assertEqual(psc_res["psc_total"], 2)
        self.assertEqual(psc_res["native_headers"], 1)
        self.assertEqual(psc_res["non_native_scripts"], 1)
        top_psc = {x["name"]: x["count"] for x in psc_res["top_40"]}
        self.assertEqual(top_psc["Event:OnQuestInit"], 1)
        self.assertEqual(top_psc["Utility.Wait"], 1)
        self.assertEqual(top_psc["SetStage"], 1)
        self.assertNotIn("FakeCall", top_psc)
        self.assertNotIn("IgnoredCall", top_psc)
        self.assertNotIn("LiteralCall", top_psc)

        # Test FO4 (v3.9, game 2), FO76 (v3.15, game 3), and Starfield (v3.12, game 4 w/ Guard)
        for gid, maj, minv in ((2, 3, 9), (3, 3, 15), (4, 3, 12)):
            active_pex = _build_synthetic_pex(gid, maj, minv)
            parsed = census.parse_pex_bytes(active_pex)
            self.assertEqual(parsed["version"], f"{maj}.{minv}")
            self.assertEqual(parsed["game_id"], gid)
            self.assertFalse(parsed["is_native_header"])
            self.assertFalse(parsed["is_empty_stub"])
            self.assertEqual(parsed["instructions"], 2)
            self.assertEqual(parsed["events"], ["Event:OnLoad"])
            self.assertEqual(parsed["calls"], ["Utility.Wait", "DoWork"])

        stub_parsed = census.parse_pex_bytes(_build_synthetic_pex(3, 3, 15, empty_stub=True))
        self.assertTrue(stub_parsed["is_empty_stub"])
        native_parsed = census.parse_pex_bytes(_build_synthetic_pex(4, 3, 12, native_only=True))
        self.assertTrue(native_parsed["is_native_header"])


if __name__ == "__main__":
    unittest.main()
