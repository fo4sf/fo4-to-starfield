"""MQ101 & MQ101KelloggSequence surviving scene/voice extractor and local Wwise .wem converter."""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from fo4sf import fo4land
from fo4sf.ba2 import Ba2
from . import s1_spec


def _u32(b: bytes, o: int = 0) -> int:
    return struct.unpack_from("<I", b, o)[0]


def _i32(b: bytes, o: int = 0) -> int:
    return struct.unpack_from("<i", b, o)[0]


def _u16(b: bytes, o: int = 0) -> int:
    return struct.unpack_from("<H", b, o)[0]


def split_fuz_xwma(data: bytes) -> bytes:
    """Extract raw xWMA RIFF bytes from a Fallout 4 `.fuz` blob (mirrors `make_mission.py`)."""
    if len(data) < 12 or data[:4] != b"FUZE":
        raise ValueError(f"Invalid FUZ header: {data[:4]!r}")
    _ver, lip_len = struct.unpack_from("<II", data, 4)
    return data[12 + lip_len :]


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


def build_local_kellogg_voices_payload(
    fo4_esm_path: str,
    stem_durations: Dict[str, float],
    out_voice_dir: str,
    stem_to_wem: Dict[str, str],
    *,
    first_wem: int = 0x00F50001,
) -> Tuple[List[dict], List[str]]:
    """Build local-only Kellogg pod scene lines from `Fallout4.esm` (`MQ101KelloggSequence`) and place numbered `.wem`s.

    FO4 dialogue text stays local only (written into scratch JSON passed to `Prewar`, never committed to Git).
    """
    scene_infos: List[Tuple[str, int, str]] = []
    with fo4land.Plugin(fo4_esm_path) as p:
        buf = p.buf
        k_grup = None
        for it in fo4land.iter_items(buf, *p.top_group(b"QUST")):
            if it[0] == "GRUP" and _u32(it[3]) == s1_spec.MQ101_KELLOGG_QUEST_FID:
                k_grup = (it[1] + 24, it[2])
                break
        if k_grup is not None:
            def _walk_k(s: int, e: int) -> None:
                for sub in fo4land.iter_items(buf, s, e):
                    if sub[0] == "GRUP":
                        _walk_k(sub[1] + 24, sub[2])
                    elif sub[0] == b"INFO":
                        isubs = list(fo4land.iter_subrecords(fo4land.record_data(buf, sub[1])))
                        nam1 = next((d.rstrip(b"\x00").decode("utf-8", "replace") for sg, d in isubs if sg == b"NAM1"), "")
                        anmc = next((_u32(d) for sg, d in isubs if sg == b"ANAM" and len(d) == 4), 0)
                        if nam1:
                            scene_infos.append((f"{sub[3]:08x}", anmc, nam1))
            _walk_k(*k_grup)

    os.makedirs(out_voice_dir, exist_ok=True)
    kellogg_rows: List[dict] = []
    copied: List[str] = []
    for idx, (info_hex, _anmc, text) in enumerate(scene_infos[:12]):
        cand_stem = None
        speaker = "FO4SF_PrewarKelloggNPC"
        for prefix, spk in (
            ("npcmkellogg", "FO4SF_PrewarKelloggNPC"),
            ("mq101instagentmalevoice", "FO4SF_PrewarInstAgentMNPC"),
            ("mq101instagentfemalevoice", "FO4SF_PrewarInstAgentFNPC"),
        ):
            st = f"{prefix}/{info_hex}_1"
            if st in stem_to_wem:
                cand_stem = st
                speaker = spk
                break
        if cand_stem is None:
            continue
        wem_id = first_wem + idx
        wem_hex = f"{wem_id:08x}"
        voice_sub = "genericfemaleeventoned" if speaker == "FO4SF_PrewarInstAgentFNPC" else "genericmaleeventoned"
        dst_dir = os.path.join(out_voice_dir, voice_sub)
        os.makedirs(dst_dir, exist_ok=True)
        dst_wem = os.path.join(dst_dir, f"{wem_hex}.wem")
        shutil.copy2(stem_to_wem[cand_stem], dst_wem)
        copied.append(dst_wem)
        dur = float(stem_durations.get(cand_stem, 2.5))
        kellogg_rows.append([speaker, text, f"0x{wem_id:08X}", dur])

    return kellogg_rows, copied


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
    """Local-only `.fuz -> .xwm -> .wav -> .wem` conversion using `make_mission`'s WwiseConsole workflow."""
    if not os.path.isfile(xwmaencode_exe):
        raise FileNotFoundError(f"Missing xwmaencode: {xwmaencode_exe}")
    if not os.path.isfile(wwise_console_exe):
        raise FileNotFoundError(f"Missing WwiseConsole: {wwise_console_exe}")

    arch = Ba2(voices_ba2_path)
    by_low = {e.name.lower().replace("\\", "/"): e.name for e in arch.entries}
    xwm_dir = os.path.join(scratch_dir, "xwm")
    wav_dir = os.path.join(scratch_dir, "wav")
    wem_dir = os.path.join(scratch_dir, "wem")
    os.makedirs(xwm_dir, exist_ok=True)
    os.makedirs(wav_dir, exist_ok=True)
    os.makedirs(wem_dir, exist_ok=True)

    flats: List[Tuple[str, str]] = []
    for s in stems:
        norm = s.replace("\\", "/").lower()
        key = f"sound/voice/fallout4.esm/{norm}.fuz"
        if key not in by_low:
            raise FileNotFoundError(f"{voices_ba2_path}: missing {key}")
        flat = norm.replace("/", "__")
        xp = os.path.join(xwm_dir, flat + ".xwm")
        wp = os.path.join(wav_dir, flat + ".wav")
        with open(xp, "wb") as f:
            f.write(split_fuz_xwma(arch.read(by_low[key])))
        subprocess.run([xwmaencode_exe, xp, wp], check=True)
        if durations_out is not None:
            durations_out[norm] = _wav_duration_seconds(wp)
        flats.append((norm, flat))

    proj = os.path.join(scratch_dir, "wwise", "PrewarVoice", "PrewarVoice.wproj")
    if os.path.isdir(os.path.dirname(proj)):
        shutil.rmtree(os.path.dirname(proj))
    subprocess.run([wwise_console_exe, "create-new-project", proj, "--platform", "Windows", "--quiet"], check=True)
    wsources = os.path.join(scratch_dir, "sources.wsources")
    with open(wsources, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f'<ExternalSourcesList SchemaVersion="1" Root="{wav_dir}">\n')
        for _, flat in sorted(set(flats)):
            f.write(f'  <Source Path="{flat}.wav" Conversion="{conversion}"/>\n')
        f.write("</ExternalSourcesList>\n")
    subprocess.run(
        [wwise_console_exe, "convert-external-source", proj, "--platform", "Windows", "--source-file", wsources, "--output", wem_dir, "--quiet"],
        check=True,
    )

    found: Dict[str, str] = {}
    by_flat: Dict[str, str] = {}
    for dp, _, fns in os.walk(wem_dir):
        for fn in fns:
            if fn.lower().endswith(".wem"):
                by_flat[os.path.splitext(fn.lower())[0]] = os.path.join(dp, fn)
    for norm, flat in flats:
        if flat not in by_flat:
            raise RuntimeError(f"WwiseConsole missing .wem for {norm}")
        found[norm] = by_flat[flat]
    return found
