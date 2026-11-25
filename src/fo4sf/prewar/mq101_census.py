"""MQ101 & MQ101KelloggSequence surviving scene/voice extractor and local Wwise .wem converter."""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from fo4sf import fo4land
from fo4sf.ba2 import Ba2
from . import s1_spec


def _make_mission():
    """Lazy-import `scripts/mission/make_mission.py` to reuse its canonical voice helpers (`S1-16`)."""
    mission_dir = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts", "mission")
    )
    if mission_dir not in sys.path:
        sys.path.insert(0, mission_dir)
    import make_mission  # noqa: E402

    return make_mission


def _u32(b: bytes, o: int = 0) -> int:
    return struct.unpack_from("<I", b, o)[0]


def _i32(b: bytes, o: int = 0) -> int:
    return struct.unpack_from("<i", b, o)[0]


def _u16(b: bytes, o: int = 0) -> int:
    return struct.unpack_from("<H", b, o)[0]


def split_fuz_xwma(data: bytes) -> bytes:
    """Extract raw xWMA RIFF bytes from a Fallout 4 `.fuz` blob via `make_mission.split_fuz_xwma`."""
    return _make_mission().split_fuz_xwma(data)


def parse_fuz_duration_s(raw: bytes) -> float:
    """Compute exact xWMA duration in seconds from `.fuz` RIFF header."""
    if len(raw) < 12 or raw[:4] != b"FUZE":
        return 0.0
    xw = split_fuz_xwma(raw)
    if len(xw) < 12 or xw[:4] != b"RIFF" or xw[8:12] != b"XWMA":
        return 0.0
    pos, avg_bps, data_len = 12, 0, 0
    while pos + 8 <= len(xw):
        cid = xw[pos : pos + 4]
        csz = _u32(xw, pos + 4)
        cbody = xw[pos + 8 : pos + 8 + csz]
        if cid == b"fmt " and len(cbody) >= 12:
            avg_bps = _u32(cbody, 8)
        elif cid == b"data":
            data_len = csz
        pos += 8 + csz + (csz & 1)
    return data_len / float(avg_bps) if (avg_bps > 0 and data_len > 0) else 0.0


def build_prewar_voice_plan(
    fo4_esm_path: str,
    voices_ba2_path: Optional[str] = None,
    *,
    include_player_lines: bool = True,
    include_clipboard_offer: bool = False,
) -> dict:
    """Extract surviving MQ101 + MQ101KelloggSequence scene & voice manifest (zero FO4 dialogue text persisted)."""
    by_info: Dict[str, List[Tuple[str, str, int, str]]] = defaultdict(list)
    if voices_ba2_path and os.path.isfile(voices_ba2_path):
        arch = Ba2(voices_ba2_path)
        for e in arch.entries:
            norm = e.name.lower().replace("\\", "/")
            parts = norm.split("/")
            fn = parts[-1]
            if fn.endswith(".fuz") and "_" in fn:
                info_hex, rest = fn[:-4].split("_", 1)
                if len(info_hex) == 8:
                    fld = parts[3] if len(parts) >= 5 else ""
                    by_info[info_hex].append((rest, fld, e.packed or e.unpacked, e.name))

    target_quests = {s1_spec.MQ101_QUEST_FID, s1_spec.MQ101_KELLOGG_QUEST_FID}
    scenes_out: List[dict] = []
    voice_stems: List[dict] = []

    with fo4land.Plugin(fo4_esm_path) as p:
        buf = p.buf
        q_recs: Dict[int, List[Tuple[bytes, bytes]]] = {}
        q_grups: Dict[int, Tuple[int, int]] = {}
        for it in fo4land.iter_items(buf, *p.top_group(b"QUST")):
            if it[0] == b"QUST" and it[3] in target_quests:
                q_recs[it[3]] = list(fo4land.iter_subrecords(fo4land.record_data(buf, it[1])))
            elif it[0] == "GRUP" and _u32(it[3]) in target_quests:
                q_grups[_u32(it[3])] = (it[1] + 24, it[2])

        for qfid in (s1_spec.MQ101_QUEST_FID, s1_spec.MQ101_KELLOGG_QUEST_FID):
            if qfid not in q_grups:
                continue
            scens, dials, infos = [], {}, []

            def _walk(s: int, e: int, dfid: Optional[int] = None) -> None:
                for sub in fo4land.iter_items(buf, s, e):
                    if sub[0] == "GRUP":
                        _walk(sub[1] + 24, sub[2], _u32(sub[3]) if sub[4] == 7 else dfid)
                    elif sub[0] == b"SCEN":
                        scens.append((sub[3], list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))))
                    elif sub[0] == b"DIAL":
                        dials[sub[3]] = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                    elif sub[0] == b"INFO":
                        infos.append((dfid, sub[3], list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))))

            _walk(*q_grups[qfid])
            dial_to_scen: Dict[int, Tuple[str, int, bool]] = {}
            for sfid, ssubs in scens:
                sed = next((fo4land.zstring(d) for sg, d in ssubs if sg == b"EDID"), "")
                acts, cur = [], None
                for sg, d in ssubs:
                    if sg == b"ANAM" and len(d) == 2:
                        if cur:
                            acts.append(cur)
                        cur = {"type": _u16(d), "subs": []}
                    elif sg == b"ANAM" and len(d) == 0:
                        if cur:
                            acts.append(cur)
                            cur = None
                    elif cur is not None:
                        cur["subs"].append((sg.decode("latin1"), d))
                if cur:
                    acts.append(cur)
                is_cut_scene = sed == "MQ101_001_MirrorScene" or (
                    not include_clipboard_offer and sed == "MQ101_007_PlayerDoesntSign"
                )
                if not is_cut_scene:
                    scenes_out.append({"quest": f"0x{qfid:08X}", "fid": f"0x{sfid:08X}", "edid": sed})
                for a in acts:
                    alid = next((_i32(d) for sg, d in a["subs"] if sg == "ALID" and len(d) == 4), None)
                    sph = next((_u32(d) for sg, d in a["subs"] if sg == "SNAM" and len(d) == 4), -1)
                    for sg, d in a["subs"]:
                        if len(d) == 4 and _u32(d) in dials:
                            is_player = (sg in ("PTOP", "NTOP", "NETO", "QTOP") and a["type"] == 3) or (alid == -2)
                            dial_to_scen[_u32(d)] = (sed, sph, is_player)

            cur_helo_grp = "ROOT"
            helo_player_groups = {
                "MQ101PlayerSpouseTVGroup", "MQ101PlayerSpouseHouseGroup",
                "MQ101PlayerCodsworthHouseGroup", "MQ101PlayerCodsworthBombsGroup",
                "MQ101PlayerToSpouseVaultLineHellos", "MQ101PlayerSpouseBombsDropping",
            }
            for dfid, ifid, isubs in infos:
                dsubs = dials.get(dfid, [])
                dsnam = next((d[:4].decode("latin1") for sg, d in dsubs if sg == b"SNAM"), "")
                ied = next((fo4land.zstring(d) for sg, d in isubs if sg == b"EDID"), "")
                if dfid == 0x000A7D2F and ied:
                    cur_helo_grp = ied
                is_player_line = False
                cut = False
                if dfid in dial_to_scen:
                    sed, sph, is_p = dial_to_scen[dfid]
                    is_player_line = is_p
                    if sed == "MQ101_001_MirrorScene":
                        cut = True
                    elif sed == "MQ101_006_VaultTecRep" and (sph == 7 or (sph == 6 and not include_clipboard_offer)):
                        cut = True
                    elif sed == "MQ101_007_PlayerDoesntSign" and (sph == 3 or not include_clipboard_offer):
                        cut = True
                else:
                    if dsnam in ("CUST", "IMNG", "WFPI") or (dfid == 0x000A7D2F and cur_helo_grp == "MQ101SpouseMirrorGroup"):
                        cut = True
                    elif dfid == 0x000A7D2F and cur_helo_grp in helo_player_groups:
                        is_player_line = True
                    elif any(_u16(d, 8) == 72 and _u32(d, 12) == 7 for sg, d in isubs if sg == b"CTDA" and len(d) >= 16):
                        is_player_line = True

                if cut or (is_player_line and not include_player_lines):
                    continue
                trda_count = sum(1 for sg, _ in isubs if sg == b"TRDA")
                if trda_count == 0:
                    continue
                hits = by_info.get(f"{ifid:08x}", [])
                if hits:
                    for resp, fld, _pk, ba2_name in hits:
                        voice_stems.append({
                            "quest": f"0x{qfid:08X}",
                            "dial": f"0x{dfid:08X}",
                            "info": f"0x{ifid:08X}",
                            "resp": resp,
                            "folder": fld,
                            "ba2_path": ba2_name,
                            "stem": f"{fld}/{ifid:08x}_{resp}",
                            "is_player": is_player_line,
                        })
                else:
                    voice_stems.append({
                        "quest": f"0x{qfid:08X}",
                        "dial": f"0x{dfid:08X}",
                        "info": f"0x{ifid:08X}",
                        "resp": "1",
                        "folder": "",
                        "ba2_path": "",
                        "stem": f"{ifid:08x}_1",
                        "is_player": is_player_line,
                    })

    extractable = [st for st in voice_stems if st["ba2_path"]]
    return {
        "surviving_scenes": scenes_out,
        "voice_stems": voice_stems,
        "extractable_stems": extractable,
        "scene_count": len(scenes_out),
        "stem_count": len(voice_stems),
        "extractable_stem_count": len(extractable),
    }


def _wav_duration_seconds(wav_path: str) -> float:
    import wave

    try:
        with wave.open(wav_path, "rb") as w:
            rate = w.getframerate() or 44100
            return round(max(1.0, w.getnframes() / float(rate)), 2)
    except Exception:
        return 2.5


def _load_fo4_ilstrings(fo4_esm_path: str, interface_ba2_path: Optional[str] = None) -> Tuple[bool, Dict[int, str]]:
    """Return `(is_localized, {string_id: cp1252_text})` from `Fallout4.esm` + sibling `Fallout4 - Interface.ba2`."""
    with open(fo4_esm_path, "rb") as f:
        hdr = f.read(24)
    localized = len(hdr) >= 12 and hdr[:4] == b"TES4" and bool(_u32(hdr, 8) & 0x00000080)
    if not localized:
        return False, {}

    ba2_cand = interface_ba2_path or os.path.join(os.path.dirname(os.path.abspath(fo4_esm_path)), "Fallout4 - Interface.ba2")
    raw_tbl: Optional[bytes] = None
    if os.path.isfile(ba2_cand):
        arch = Ba2(ba2_cand)
        hit = arch.find("Strings/Fallout4_en.ILSTRINGS")
        if hit is not None:
            raw_tbl = arch.read(hit)
    if raw_tbl is None:
        loose = os.path.join(os.path.dirname(os.path.abspath(fo4_esm_path)), "Strings", "Fallout4_en.ILSTRINGS")
        if os.path.isfile(loose):
            with open(loose, "rb") as f:
                raw_tbl = f.read()
    if raw_tbl is None or len(raw_tbl) < 8:
        return True, {}

    count, _data_size = struct.unpack_from("<II", raw_tbl, 0)
    base = 8 + 8 * count
    out: Dict[int, str] = {}
    for k in range(count):
        if 8 + 8 * (k + 1) > len(raw_tbl):
            break
        sid, off = struct.unpack_from("<II", raw_tbl, 8 + 8 * k)
        if base + off + 4 > len(raw_tbl):
            continue
        (ln,) = struct.unpack_from("<I", raw_tbl, base + off)
        text = raw_tbl[base + off + 4 : base + off + 4 + ln].split(b"\x00", 1)[0].decode("cp1252", "replace")
        out[sid] = text
    return True, out


def _decode_info_nam1(raw: bytes, *, localized: bool, ilstrings: Dict[int, str]) -> str:
    """Resolve `INFO.NAM1` bytes (4-byte StringID when localized, else inline string) to readable text."""
    if not raw:
        return ""
    if localized and len(raw) == 4:
        sid = _u32(raw)
        if sid == 0:
            return ""
        if sid in ilstrings:
            return ilstrings[sid]
        return f"Line {sid:08x}"
    return raw.rstrip(b"\x00").decode("utf-8", "replace")


def _is_mq203_memory_replay_info(isubs: Sequence[Tuple[bytes, bytes]]) -> bool:
    """Return True when `INFO` carries `CTDA GetQuestRunning(MQ101) == 0.0` (MQ203 memory-den duplicate)."""
    for sg, d in isubs:
        if sg == b"CTDA" and len(d) >= 24:
            comp_val = struct.unpack_from("<f", d, 4)[0]
            func_idx = _u16(d, 8)
            param1 = _u32(d, 12)
            if func_idx == 56 and param1 == s1_spec.MQ101_QUEST_FID and comp_val == 0.0:
                return True
    return False


def _parse_scen_topic_phases(subs: Sequence[Tuple[bytes, bytes]]) -> Dict[int, Tuple[int, int]]:
    """Map `{topic_fid: (start_phase, action_index)}` from a Fallout 4 `SCEN` record."""
    topic_phase: Dict[int, Tuple[int, int]] = {}
    cur_phase = -1
    act_idx = 0
    in_action = False
    saw_snam = False
    for sg, d in subs:
        if sg == b"ANAM":
            in_action = len(d) >= 2
            cur_phase = -1
            saw_snam = False
            act_idx += 1
        elif in_action:
            if sg == b"SNAM" and len(d) == 4 and not saw_snam:
                cur_phase = _i32(d)
                saw_snam = True
            elif sg in (b"DATA", b"HTID") and len(d) == 4:
                tid = _u32(d)
                if tid != 0:
                    cand = (cur_phase if cur_phase >= 0 else 9999, act_idx)
                    prev = topic_phase.get(tid)
                    if prev is None or cand < prev:
                        topic_phase[tid] = cand
    return topic_phase


def extract_kellogg_scene_order(
    fo4_esm_path: str,
    *,
    interface_ba2_path: Optional[str] = None,
) -> List[Tuple[int, str, str, int, int]]:
    """Extract deduplicated `MQ101` Kellogg pod lines ordered by `SCEN 0x000D3CAF` phase (`S1-02`).

    Drops `MQ203` memory-den duplicate INFOs (`GetQuestRunning(MQ101) == 0.0` or higher duplicate `INFO`
    FormID per `(topic, text)`), keeping phase `12` (`000CF910`) before phase `20` (`0001A6A0`) plus agent lines.
    """
    localized, ilstrings = _load_fo4_ilstrings(fo4_esm_path, interface_ba2_path=interface_ba2_path)
    kellogg_scen_fid = getattr(s1_spec, "MQ101_KELLOGG_SCENE_FID", 0x000D3CAF)
    topic_phases: Dict[int, Tuple[int, int]] = {}
    raw_infos: List[Tuple[int, int, str]] = []

    with fo4land.Plugin(fo4_esm_path) as p:
        buf = p.buf
        k_grup = None
        for it in fo4land.iter_items(buf, *p.top_group(b"QUST")):
            if it[0] == "GRUP" and _u32(it[3]) == s1_spec.MQ101_KELLOGG_QUEST_FID:
                k_grup = (it[1] + 24, it[2])
                break
        if k_grup is not None:
            def _walk_k(s: int, e: int, dfid: int = 0) -> None:
                cur_dial = dfid
                for sub in fo4land.iter_items(buf, s, e):
                    if sub[0] == "GRUP":
                        grp_dial = _u32(sub[3]) if sub[4] == 7 else cur_dial
                        _walk_k(sub[1] + 24, sub[2], grp_dial)
                    elif sub[0] == b"SCEN" and sub[3] == kellogg_scen_fid:
                        ssubs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                        topic_phases.update(_parse_scen_topic_phases(ssubs))
                    elif sub[0] == b"DIAL":
                        cur_dial = sub[3]
                    elif sub[0] == b"INFO":
                        isubs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                        if _is_mq203_memory_replay_info(isubs):
                            continue
                        raw_nam1 = next((d for sg, d in isubs if sg == b"NAM1"), b"")
                        nam1 = _decode_info_nam1(raw_nam1, localized=localized, ilstrings=ilstrings)
                        tpic = next((_u32(d) for sg, d in isubs if sg == b"TPIC" and len(d) == 4), cur_dial)
                        if nam1:
                            raw_infos.append((sub[3], tpic, nam1))

            _walk_k(*k_grup)

    by_topic_lowest: Dict[Tuple[int, str], Tuple[int, int, int, int, str]] = {}
    for seq_idx, (ifid, tid, nam1) in enumerate(raw_infos):
        key = (tid, nam1.strip().lower()) if tid else (ifid, nam1.strip().lower())
        ph, act_idx = topic_phases.get(tid, (10000 + seq_idx, seq_idx))
        cand = (ph, act_idx, ifid, tid, nam1)
        prev = by_topic_lowest.get(key)
        if prev is None or ifid < prev[2]:
            by_topic_lowest[key] = cand

    ordered = sorted(by_topic_lowest.values(), key=lambda row: (row[0], row[1], row[2]))
    return [(ph, f"{ifid:08x}", nam1, ifid, tid) for ph, _act, ifid, tid, nam1 in ordered]


def _read_quest_info_texts(
    fo4_esm_path: str,
    wanted_info_fids: Sequence[int],
    *,
    interface_ba2_path: Optional[str] = None,
) -> Dict[int, str]:
    """Resolve localized/inline `NAM1` dialogue strings for `INFO` FormIDs across `MQ101` & `MQ101KelloggSequence`."""
    wanted = set(wanted_info_fids)
    localized, ilstrings = _load_fo4_ilstrings(fo4_esm_path, interface_ba2_path=interface_ba2_path)
    out: Dict[int, str] = {}
    target_quests = {s1_spec.MQ101_QUEST_FID, s1_spec.MQ101_KELLOGG_QUEST_FID}
    with fo4land.Plugin(fo4_esm_path) as p:
        buf = p.buf

        def _walk_infos(s: int, e: int) -> None:
            for sub in fo4land.iter_items(buf, s, e):
                if sub[0] == "GRUP":
                    _walk_infos(sub[1] + 24, sub[2])
                elif sub[0] == b"INFO" and sub[3] in wanted:
                    isubs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                    raw_nam1 = next((d for sg, d in isubs if sg == b"NAM1"), b"")
                    txt = _decode_info_nam1(raw_nam1, localized=localized, ilstrings=ilstrings)
                    if txt:
                        out[sub[3]] = txt

        for it in fo4land.iter_items(buf, *p.top_group(b"QUST")):
            if it[0] == "GRUP" and _u32(it[3]) in target_quests:
                _walk_infos(it[1] + 24, it[2])
        if len(out) < len(wanted):
            for it in fo4land.iter_items(buf, *p.top_group(b"DIAL")):
                if it[0] == "GRUP":
                    _walk_infos(it[1] + 24, it[2])
    return out


CURATED_PREWAR_SCENE_DEFS: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
    "codsworth_scene": (
        ("FO4SF_PrewarCodsworthNPC", "robotmrhandy/000aa75d_1", "FO4SF_PrewarCodsworthVoice"),
        ("FO4SF_PrewarCodsworthNPC", "robotmrhandy/000aa762_1", "FO4SF_PrewarCodsworthVoice"),
        ("FO4SF_PrewarCodsworthNPC", "robotmrhandy/000c3709_1", "FO4SF_PrewarCodsworthVoice"),
        ("FO4SF_PrewarCodsworthNPC", "robotmrhandy/000c3175_1", "FO4SF_PrewarCodsworthVoice"),
    ),
    "vault_tec_rep_scene": (
        ("FO4SF_PrewarVaultTecRepNPC", "npcmvaulttecrep/000abf8f_1", "FO4SF_PrewarRepVoice"),
        ("FO4SF_PrewarVaultTecRepNPC", "npcmvaulttecrep/000eaead_1", "FO4SF_PrewarRepVoice"),
        ("FO4SF_PrewarVaultTecRepNPC", "npcmvaulttecrep/000eaeb8_1", "FO4SF_PrewarRepVoice"),
        ("FO4SF_PrewarVaultTecRepNPC", "npcmvaulttecrep/000abfc3_1", "FO4SF_PrewarRepVoice"),
        ("FO4SF_PrewarVaultTecRepNPC", "npcmvaulttecrep/000f7041_1", "FO4SF_PrewarRepVoice"),
    ),
    "broadcast_scene": (
        ("FO4SF_PrewarBroadcastNPC", "mq101emergbroadcastvoice/000be813_1", "FO4SF_PrewarBroadcastVoice"),
        ("FO4SF_PrewarSpouseFemaleNPC", "playervoicefemale01/001ebb00_1", "FO4SF_PrewarFemaleVoice"),
        ("FO4SF_PrewarSpouseFemaleNPC", "playervoicefemale01/000bad08_1", "FO4SF_PrewarFemaleVoice"),
        ("FO4SF_PrewarSpouseMaleNPC", "playervoicemale01/001ebb00_1", "FO4SF_PrewarMaleVoice"),
        ("FO4SF_PrewarSpouseMaleNPC", "playervoicemale01/000bad08_1", "FO4SF_PrewarMaleVoice"),
    ),
    "soldier_gate_scene": (
        ("FO4SF_PrewarSoldierCheckerNPC", "mq101prewarsoldier01/00121c88_1", "FO4SF_PrewarSoldierVoice"),
        ("FO4SF_PrewarSoldierCheckerNPC", "mq101prewarsoldier01/000ddb8f_1", "FO4SF_PrewarSoldierVoice"),
    ),
    "vault_doctor_scene": (
        ("FO4SF_PrewarVaultDoctorNPC", "vault111voice/0018ad65_1", "FO4SF_PrewarDoctorVoice"),
        ("FO4SF_PrewarVaultDoctorNPC", "npcmvaulttecscientist03/0018bac6_1", "FO4SF_PrewarDoctorVoice"),
        ("FO4SF_PrewarVaultDoctorNPC", "vault111voice/0001ab75_1", "FO4SF_PrewarDoctorVoice"),
    ),
}


def curated_prewar_scene_stems() -> List[str]:
    """Return every FO4 stem required for Codsworth, Vault-Tec Rep, Broadcast, Soldier Gate, and Vault Doctor."""
    out: List[str] = []
    for rows in CURATED_PREWAR_SCENE_DEFS.values():
        for _npc, stem, _vtyp in rows:
            if stem not in out:
                out.append(stem)
    return out


def kellogg_scene_stems(fo4_esm_path: str, voices_ba2_path: str) -> List[str]:
    """Return deduplicated phase-sorted Kellogg + Institute Agent stems available in `voices_ba2_path`."""
    arch = Ba2(voices_ba2_path)
    by_info: Dict[str, str] = {}
    wanted_prefixes = ("npcmkellogg", "mq101instagentmalevoice", "mq101instagentfemalevoice")
    for e in arch.entries:
        norm = e.name.lower().replace("\\", "/")
        parts = norm.split("/")
        if len(parts) >= 5 and parts[-1].endswith(".fuz"):
            fld = parts[3]
            stem_base = parts[-1][:-4]
            if fld in wanted_prefixes and stem_base.endswith("_1"):
                by_info[stem_base[:-2]] = f"{fld}/{stem_base}"

    out: List[str] = []
    for _ph, info_hex, _txt, _fid, _tid in extract_kellogg_scene_order(fo4_esm_path):
        st = by_info.get(info_hex)
        if st and st not in out:
            out.append(st)
    return out


def build_local_kellogg_voices_payload(
    fo4_esm_path: str,
    stem_durations: Dict[str, float],
    out_voice_dir: str,
    stem_to_wem: Dict[str, str],
    *,
    first_wem: int = 0x00F50001,
    interface_ba2_path: Optional[str] = None,
) -> Tuple[List[dict], List[str]]:
    """Build local-only deduplicated & phase-sorted Kellogg pod scene lines (`S1-02`) and place numbered `.wem`s.

    FO4 dialogue text stays local only (written into scratch JSON passed to `Prewar`, never committed to Git).
    """
    ordered_infos = extract_kellogg_scene_order(fo4_esm_path, interface_ba2_path=interface_ba2_path)
    os.makedirs(out_voice_dir, exist_ok=True)
    kellogg_rows: List[dict] = []
    copied: List[str] = []
    next_wem = first_wem
    for _ph, info_hex, text, _ifid, _tid in ordered_infos:
        cand_stem = None
        speaker = "FO4SF_PrewarKelloggNPC"
        voice_sub = "fo4sf_prewarmalevoice"
        for prefix, spk, vsub in (
            ("npcmkellogg", "FO4SF_PrewarKelloggNPC", "fo4sf_prewarmalevoice"),
            ("mq101instagentmalevoice", "FO4SF_PrewarInstAgentMNPC", "fo4sf_prewarmalevoice"),
            ("mq101instagentfemalevoice", "FO4SF_PrewarInstAgentFNPC", "fo4sf_prewarfemalevoice"),
        ):
            st = f"{prefix}/{info_hex}_1"
            if st in stem_to_wem:
                cand_stem = st
                speaker = spk
                voice_sub = vsub
                break
        if cand_stem is None:
            continue
        wem_id = next_wem
        next_wem += 1
        wem_hex = f"{wem_id:08x}"
        dst_dir = os.path.join(out_voice_dir, voice_sub)
        os.makedirs(dst_dir, exist_ok=True)
        dst_wem = os.path.join(dst_dir, f"{wem_hex}.wem")
        shutil.copy2(stem_to_wem[cand_stem], dst_wem)
        copied.append(dst_wem)
        dur = float(stem_durations.get(cand_stem, 2.5))
        kellogg_rows.append([speaker, text, f"0x{wem_id:08X}", dur])

    return kellogg_rows, copied


def build_local_prewar_scenes_payload(
    fo4_esm_path: str,
    stem_durations: Dict[str, float],
    out_voice_dir: str,
    stem_to_wem: Dict[str, str],
    *,
    first_wem: int = 0x00F50001,
    interface_ba2_path: Optional[str] = None,
) -> Tuple[Dict[str, List[list]], List[str]]:
    """Build local-only voice rows for all 6 S1 scenes (`S1-01`), naming `.wem` files by INFO `WEMFile` IDs."""
    kellogg_rows, copied = build_local_kellogg_voices_payload(
        fo4_esm_path,
        stem_durations,
        out_voice_dir,
        stem_to_wem,
        first_wem=first_wem,
        interface_ba2_path=interface_ba2_path,
    )
    info_fids = [
        int(stem.split("/", 1)[1].split("_", 1)[0], 16)
        for rows in CURATED_PREWAR_SCENE_DEFS.values()
        for _npc, stem, _vtyp in rows
    ]
    text_by_info = _read_quest_info_texts(fo4_esm_path, info_fids, interface_ba2_path=interface_ba2_path)

    payload: Dict[str, List[list]] = {"kellogg_scene": kellogg_rows}
    next_wem = first_wem + len(kellogg_rows)
    for scene_key, rows in CURATED_PREWAR_SCENE_DEFS.items():
        scene_rows: List[list] = []
        for npc_edid, stem, vtyp_edid in rows:
            if stem not in stem_to_wem:
                continue
            ifid = int(stem.split("/", 1)[1].split("_", 1)[0], 16)
            text = text_by_info.get(ifid, "")
            if not text:
                continue
            wem_id = next_wem
            next_wem += 1
            wem_hex = f"{wem_id:08x}"
            vdir = os.path.join(out_voice_dir, vtyp_edid.lower())
            os.makedirs(vdir, exist_ok=True)
            dst_wem = os.path.join(vdir, f"{wem_hex}.wem")
            shutil.copy2(stem_to_wem[stem], dst_wem)
            copied.append(dst_wem)
            dur = float(stem_durations.get(stem, 2.5))
            scene_rows.append([npc_edid, text, f"0x{wem_id:08X}", dur, vtyp_edid])
        payload[scene_key] = scene_rows
    return payload, copied


def convert_stems_via_wwise(
    voices_ba2_path: str,
    stems: Sequence[str],
    xwmaencode_exe: str,
    wwise_console_exe: str,
    scratch_dir: str,
    *,
    conversion: str = "Vorbis Quality High",
    durations_out: Optional[Dict[str, float]] = None,
) -> Dict[str, str]:
    """Local-only `.fuz -> .xwm -> .wav -> .wem` conversion delegating directly to `make_mission` (`S1-16`)."""
    mm = _make_mission()
    found, durations = mm.convert_fuz_stems_to_wem(
        voices_ba2_path,
        list(stems),
        xwmaencode_exe,
        wwise_console_exe,
        scratch_dir,
        conversion=conversion,
        return_durations=True,
    )
    if durations_out is not None:
        durations_out.update(durations)
    return found
