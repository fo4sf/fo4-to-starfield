"""stage_ra4_human.py: probe bundle "RA4 Human" (human-animation lane): Fallout 4 human clips retargeted onto Starfield's
own human rig and picked, for keyword-carrying NPCs only, through an add-on race the way Starfield's SFBGS003 add-on
adds its plasma-cutter set (a RACE with SADD HumanRace and its own sub-graph rows).

    python scripts/probes/stage_ra4_human.py build     [--out D:\\FO4SF-Owner-Tests\\robot-anim\\RA4]
    python scripts/probes/stage_ra4_human.py verify    [--stage-dir ...]
    python scripts/probes/stage_ra4_human.py install   --starfield <game dir> [--stage-dir ...] [--plugins-txt ...]
    python scripts/probes/stage_ra4_human.py uninstall --starfield <game dir> [--plugins-txt ...]
    python scripts/probes/stage_ra4_human.py status    --starfield <game dir>

build writes, under <out> (nothing else under D:\\FO4SF-Owner-Tests is touched):
  Data\\Meshes\\Actors\\FO4SF\\Human\\Animations\\Melee\\Unarmed\\<clip>.af + .afx   the four retargeted MT clips, each
                                    named like the vanilla clip it shadows (relaxed_idle, relaxed_walkforward, jogforward,
                                    runforward), with the vanilla .afx (tag, prefix, rampout) and events from the clip
  Data\\Meshes\\AnimTextData\\...      manifests of the one new sub-graph row (key below) + generatedsubgraphdata
  FO4SF_RA4Human.esm                master Starfield.esm; KYWD FO4SF_AnimArchetypeFO4, RACE FO4SF_RA4HumanAddRace (SADD
                                    HumanRace; one row: actor keyword FO4SF_AnimArchetypeFO4, NPC_MT_Wrapping.agx, our
                                    folder then the three vanilla folders of the default NPC MT row), two test NPCs
  FO4SF_RA4Human - Main.ba2         every file under Data (GNRL, uncompressed)
  bat\\ra4a.txt ra4c.txt ra4ac.txt   console batches (XX = load-order slot placeholder; install stamps real copies)
  work\\                             vanilla inputs read, the pistol ready idle (retargeted, written, checked; NOT wired)
  report.json, REPORT.md, manifest.json

install / uninstall never run as part of build; Starfield must not be running.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
for _p in (str(REPO / "src"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stage_ra2_handy as ra2  # noqa: E402  (plugin / BA2 writers, receipts, batch rule, install helpers)
from fo4sf import actor_anim as aa  # noqa: E402
from fo4sf import handy_race as hr  # noqa: E402
from fo4sf import human_retarget as hrt  # noqa: E402
from fo4sf.ba2 import Ba2  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

STARFIELD_DIR = Path(r"D:\SteamLibrary\steamapps\common\Starfield")
FO4_DATA = Path(r"D:\SteamLibrary\steamapps\common\Fallout 4\Data")
OUT = Path(r"D:\FO4SF-Owner-Tests\robot-anim\RA4")

PROBE = "ra4-human"
PLUGIN = "FO4SF_RA4Human.esm"
MAIN_BA2 = "FO4SF_RA4Human - Main.ba2"
RECEIPT = "FO4SF_RA4Human.install.json"
DEFAULT_MIN_FREE_GB = 20.0

# ---- form ids (local; the plugin's own index is 01 with one master; in game XX = load-order slot)
F_KYWD, F_RACE_ADD, F_NPC_FO4, F_NPC_CTRL = 0x800, 0x801, 0x802, 0x803
KEYWORD = "FO4SF_AnimArchetypeFO4"
EDIDS = {F_KYWD: KEYWORD, F_RACE_ADD: "FO4SF_RA4HumanAddRace", F_NPC_FO4: "FO4SF_RA4HumanClipTest",
         F_NPC_CTRL: "FO4SF_RA4HumanControl"}
NPC_NAMES = {F_NPC_FO4: "FO4 Clip Test", F_NPC_CTRL: "Starfield Clip Test"}
BATS = {"ra4a.txt": ((F_NPC_FO4,), "FO4 Clip Test: HumanRace NPC with the keyword; idles, walks, jogs and runs with "
                                   "Fallout 4's clips if the add-on row is picked"),
        "ra4c.txt": ((F_NPC_CTRL,), "Starfield Clip Test: the same NPC without the keyword (vanilla clips, control)"),
        "ra4ac.txt": ((F_NPC_FO4, F_NPC_CTRL), "both side by side")}

# ---- Starfield sources
HUMAN_RACE = 0x0000347D
SFBGS003_RACE_EDID = "SFBGS003_HumanRace"       # template: Bethesda's own add-on race (SADD HumanRace)
TEMPLATE_KEYWORD = 0x0006A4AF                    # AnimArchetypeAngry (KYWD: CNAM, TNAM 7, FNAM)
TEMPLATE_NPC = 0x0014A813                        # FC_Clinic_GennadyAyton: male HumanRace NPC, no template, no script,
                                                 # no keywords, own outfit
FOLLOW_PACKAGE = 0x00021E76                      # defaultFollowPlayerPKG (target: the player)

# ---- sub-graph row
GRAPH_DIR = "AnimTextData\\Tables\\Graphs\\"
MT_GRAPH = GRAPH_DIR + "NPC_MT_Wrapping.agx"
VANILLA_MT_FOLDERS = ("actors\\human\\animations\\melee\\unarmed", "actors\\human\\animations\\melee\\common",
                      "actors\\human\\animations\\common")
OUR_MT_FOLDER = "Actors\\FO4SF\\Human\\Animations\\Melee\\Unarmed"
ROW_SRAF_MT_KEYWORD = bytes.fromhex("00000000")  # as HumanRace's own AnimArchetype* NPC MT rows (Macho, Angry...)

# ---- clips: (Fallout 4 clip under meshes\actors\character\animations\, vanilla clip under
#               meshes\actors\human\animations\ that it shadows, kind)
CLIPS = (
    ("mt\\neutral\\posea_idle1.hkx", "melee\\unarmed\\relaxed_idle", "mt"),
    ("mt\\neutral\\walkforward.hkx", "melee\\unarmed\\relaxed_walkforward", "mt"),
    ("mt\\neutral\\jogforward.hkx", "melee\\unarmed\\jogforward", "mt"),
    ("mt\\neutral\\runforward.hkx", "melee\\unarmed\\runforward", "mt"),
    ("weapon\\pistol\\wpnidleready.hkx", "gun\\grippistol\\ready_idle", "pistol"),
)
FO4_ANIMS = "meshes\\actors\\character\\animations\\"
SF_ANIMS = "meshes\\actors\\human\\animations\\"
# unmapped bones that keep the shadowed vanilla clip's frame-0 value (weapon holders, helpers, cameras)
VANILLA_CONSTANT_BONES = ("Weapon", "WeaponLeft", "C_Waist", "L_Arm", "R_Arm", "L_Cup", "R_Cup", "CameraTarget",
                          "Camera")
ROOT_CANCEL_BONES = ("Camera Control", "Camera Control FP")     # vanilla: translation = -root motion
SYNC_LAG = 0.07          # Sync<Side>Foot = mid-stance frame + 0.07 cycle (fitted on vanilla walk/jog/run, within 1 frame)
FOLEY_LEAD = 3           # vanilla foley sits 3 frames before FootLeft / FootRight in walk, jog and run

P3_FORBIDDEN_RE = re.compile(r"[mnvMNV]")


class Ra4Error(ValueError):
    pass


# =============================================================================================== vanilla readers
def vanilla_local(cal, rig_path: Path, af_bytes: bytes, work: Path, name: str):
    """(bones, frames) of a vanilla clip read through the DLL with the measured offset rule."""
    p = work / (name + ".af")
    p.write_bytes(af_bytes)
    rc = cal.read_clip(str(rig_path), str(p))
    bones = rc["rig"]["bones"]
    return bones, hrt.local_from_offsets(bones, rc["blocks"], rc["frame_count"])


def afx_events(n: int, foot_frames: Dict[str, int], sync_frames: Dict[str, int]) -> List[Tuple[int, str, str]]:
    ev = [(f, "Foot" + side, "") for side, f in foot_frames.items()]
    ev += [(f, f"Sync{side}Foot", "") for side, f in sync_frames.items()]
    return sorted(ev)


def locomotion_events(skel: hrt.Skel, frames, clip: hrt.Fo4Clip) -> Tuple[list, list, dict]:
    """Events and foley for a locomotion loop on the Starfield rig. FootLeft / FootRight: Fallout 4's own landing
    annotations; Sync<Side>Foot: where the foot passes under the hips + SYNC_LAG of the cycle (Starfield's rule,
    measured on its walk / jog / run); foley FOLEY_LEAD frames before each Foot event."""
    n = len(frames)
    cyc = n - 1
    feet = {}
    for t, text in clip.events:
        if text in ("FootLeft", "FootRight"):
            feet[text[4:]] = int(round(t * hrt.FPS)) % cyc
    inplace = [[((0.0, 0.0, 0.0), hrt.IDENTITY)] + list(fr[1:]) for fr in frames]
    sync = {}
    for side, foot in (("Left", "L_Foot"), ("Right", "R_Foot")):
        mids = hrt.passes_under_hips(skel, inplace, foot, ("L_Thigh", "R_Thigh"))
        if not mids:
            raise Ra4Error(f"{side} foot never passes under the hips")
        sync[side] = (mids[0] + int(round(SYNC_LAG * cyc))) % cyc
    if set(feet) != {"Left", "Right"}:
        raise Ra4Error(f"Fallout 4 foot annotations missing: {clip.events}")
    events = afx_events(n, feet, sync)
    return events, [], {"feet": feet, "sync": sync}


# =============================================================================================== records
def keyword_record(src: esm.Record, formid: int, edid: str) -> esm.Record:
    subs = [(s, esm.zbytes(edid) if s == b"EDID" else d) for s, d in src.subs]
    return ra2._rec(src, b"KYWD", formid, subs)


def row_subrecords(actor_keywords: Sequence[int], target_keywords: Sequence[int], graph: str,
                   folders: Sequence[str], sraf: bytes) -> List[Tuple[bytes, bytes]]:
    """One sub-graph row as RACE subrecords, in the vanilla order: SAKD*, STKD*, SGNM, SAPT+, SRAF."""
    out = [(b"SAKD", struct.pack("<I", k)) for k in actor_keywords]
    out += [(b"STKD", struct.pack("<I", k)) for k in target_keywords]
    out.append((b"SGNM", esm.zbytes(graph)))
    out += [(b"SAPT", esm.zbytes(f)) for f in folders]
    out.append((b"SRAF", sraf))
    return out


ROW_SIGS = (b"SAKD", b"STKD", b"SGNM", b"SAPT", b"SRAF")


def addon_race(src: esm.Record, formid: int, edid: str, name: str, rows: Sequence[List[Tuple[bytes, bytes]]]) -> esm.Record:
    """A copy of Bethesda's own add-on race (SFBGS003_HumanRace: SADD HumanRace + its rows) with our EDID, plain-text
    name fields and our rows in place of its five. Every other subrecord is kept byte for byte; the template's own
    plugin forms (top byte FD: its keywords) occur only in the rows that are replaced (checked)."""
    subs, done = [], False
    sadd = [d for s, d in src.subs if s == b"SADD"]
    if sadd != [struct.pack("<I", HUMAN_RACE)]:
        raise Ra4Error(f"template race SADD {sadd} is not HumanRace")
    for s, d in ra2._plain_strings(src.subs, name):
        if s == b"EDID":
            d = esm.zbytes(edid)
        if s in ROW_SIGS:
            if not done:
                for row in rows:
                    subs.extend(row)
                done = True
            continue
        if len(d) == 4 and d[3] in (0xFD, 0xFE) and s not in (b"FULL", b"DESC", b"SNAM"):
            raise Ra4Error(f"template subrecord {s.decode()} {d.hex()} names a form of the template's own plugin")
        subs.append((s, d))
    if not done:
        raise Ra4Error("template race has no sub-graph rows")
    return ra2._rec(src, b"RACE", formid, subs)


def test_npc(src: esm.Record, formid: int, edid: str, name: str, keywords: Sequence[int], package: int) -> Tuple[esm.Record, dict]:
    """The template NPC as a harmless test actor: own EDID and plain name, no factions (SNAM), one package (follow the
    player), Unaggressive (AIDT byte 0 = 0), short name dropped, `keywords` as its KWDA (KSIZ/KWDA right after the
    package list, where vanilla NPC_ records keep them)."""
    subs, rep = [], {"dropped": []}
    had_pkid = False
    for s, d in src.subs:
        if s in (b"VMAD",) or (s == b"SNAM" and len(d) == 5) or s == b"SHRT":
            rep["dropped"].append(s.decode())
            continue
        if s in (b"KSIZ", b"KWDA"):
            rep["dropped"].append(s.decode())
            continue
        if s == b"PKID":
            if not had_pkid:
                subs.append((b"PKID", struct.pack("<I", package)))
                if keywords:
                    subs.append((b"KSIZ", struct.pack("<I", len(keywords))))
                    subs.append((b"KWDA", b"".join(struct.pack("<I", k) for k in keywords)))
                had_pkid = True
            continue
        if s == b"EDID":
            d = esm.zbytes(edid)
        elif s == b"FULL":
            d = esm.zbytes(name)
        elif s == b"AIDT":
            rep["aidt"] = [d.hex(), (bytes([0]) + d[1:]).hex()]
            d = bytes([0]) + d[1:]
        elif s == b"ACBS":
            if struct.unpack_from("<H", d, 14)[0] & 0x1:
                raise Ra4Error(f"{src.edid}: template supplies traits; the copy would ignore its own race")
            if struct.unpack_from("<I", d)[0] & 1:
                raise Ra4Error(f"{src.edid} is female: the probe row has no Female variant")
        subs.append((s, d))
        if s == b"RNAM" and struct.unpack("<I", d)[0] != HUMAN_RACE:
            raise Ra4Error(f"{src.edid} is not on HumanRace")
    if not had_pkid:
        raise Ra4Error(f"{src.edid}: no package list to replace")
    for s in (b"TPLT", b"TPTA"):
        if any(x == s for x, _ in subs):
            raise Ra4Error(f"{src.edid}: has a template ({s.decode()})")
    rep["keywords"] = [f"{k:08X}" for k in keywords]
    return ra2._rec(src, b"NPC_", formid, subs), rep


def gsd_row(keyword: str, graph: str, folders: Sequence[str]) -> bytes:
    return hr.generated_subgraph_data([("MT", "3rd", keyword, "", graph, list(folders))])


# =============================================================================================== batch files
def build_bats(slot: Optional[int] = None) -> Dict[str, str]:
    pre = "XX" if slot is None else f"{slot & 0xFF:02X}"
    out = {}
    for fname, (fids, what) in BATS.items():
        lines = [f"; RA4 Human probe: {what}",
                 "; spawns beside the player; the NPCs follow the player (walk, jog, run to keep up)"]
        lines += [f"player.placeatme {pre}{fid:06X} 1" for fid in fids]
        out[fname] = "\n".join(lines) + "\n"
    ra2.validate_bats(out)
    return out


# =============================================================================================== build
def _sf_names(sfa: Ba2) -> Dict[str, str]:
    return {n.lower().replace("/", "\\"): n for n in sfa.names}


def _read(sfa: Ba2, low: Dict[str, str], rel: str) -> bytes:
    n = low.get(rel.lower().replace("/", "\\"))
    if n is None:
        raise Ra4Error(f"{rel} not in {sfa.path if hasattr(sfa, 'path') else 'the archive'}")
    return sfa.read(sfa.find(n))


def build(out: Path = OUT, starfield_dir: Path = STARFIELD_DIR, fo4_data: Path = FO4_DATA, dll: Optional[str] = None) -> dict:
    out = ra2.check_out_dir(out)
    if "fo4sf-owner-tests" in os.path.normcase(str(out)) and os.path.normcase(str(out)) != os.path.normcase(str(OUT)):
        raise Ra4Error(f"{out}: under D:\\FO4SF-Owner-Tests only {OUT} may be written")
    sf_data = starfield_dir / "Data"
    for sub in ("Data", "work", "bat"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
    data, work = out / "Data", out / "work"
    data.mkdir(parents=True)
    work.mkdir(parents=True)
    cal = aa.Calumi(dll)
    sfa = Ba2(str(sf_data / "Starfield - Animations.ba2"))
    low = _sf_names(sfa)
    fo4a = Ba2(str(fo4_data / "Fallout4 - Animations.ba2"))

    # ---------------------------------------------------------------- rigs
    rig_path = work / "sf_human_skeleton.rig"
    rig_path.write_bytes(_read(sfa, low, hrt.SF_HUMAN_RIG))
    rig = cal.read_rig(str(rig_path))
    bones = rig["bones"]
    cbones = hrt.clip_bones(bones)
    sf = hrt.sf_skeleton(bones)
    fo4_hkx = fo4a.read(fo4a.find(hrt.FO4_HUMAN_SKELETON))
    fo4 = hrt.fo4_skeleton(fo4_hkx)
    rt = hrt.Retargeter(fo4, sf).prepare()
    report: dict = {"conventions": {
        "units": "FO4 units x 1/70 = metres; both Z up, +Y forward (no axis change)", "fps": hrt.FPS,
        "offset_rule": "q_local = q_bind q_offset, t_local = t_bind + t_offset (measured on vanilla human clips)",
        "clip_bones": len(cbones), "rig_bones": len(bones), "precision": rig["precision"],
        "leg_ik": {"on": rt.leg_ik, "full_below_m": rt.IK_FULL_BELOW_M, "none_above_m": rt.IK_NONE_ABOVE_M}},
        "retarget": rt.report, "rig": {"path": hrt.SF_HUMAN_RIG, "bones": len(bones)},
        "fo4_skeleton": {"path": hrt.FO4_HUMAN_SKELETON, "bones": len(fo4.names)}}

    # ---------------------------------------------------------------- clips
    clip_dir = data / "Meshes" / Path(*OUR_MT_FOLDER.split("\\"))
    clip_dir.mkdir(parents=True, exist_ok=True)
    pistol_dir = work / "pistol"
    pistol_dir.mkdir()
    six = sf.index()
    clips_rep, our_paths = [], []
    for fo4_rel, sf_rel, kind in CLIPS:
        clip = hrt.decode_fo4_clip(fo4a.read(fo4a.find(FO4_ANIMS + fo4_rel)), fo4)
        v_bones, v_frames = vanilla_local(cal, rig_path, _read(sfa, low, SF_ANIMS + sf_rel + ".af"), work,
                                          "vanilla_" + sf_rel.replace("\\", "_"))
        v_afx = _read(sfa, low, SF_ANIMS + sf_rel + ".afx")
        extras = {b: v_frames[0][six[b]] for b in VANILLA_CONSTANT_BONES}
        rt.ik_miss = []
        frames = hrt.retarget_clip(rt, clip, extras=extras, world_rot={"DirectAt": hrt.IDENTITY})
        for b in ROOT_CANCEL_BONES:                       # cameras stay put while the root moves (as vanilla)
            i = six[b]
            for fr in frames:
                rt_, rq_ = fr[0]
                inv = aa.q_conj(rq_)
                fr[i] = (aa.q_rotate(inv, tuple(-x for x in rt_)), inv)
        extra_rep = {}
        if kind == "pistol":
            vw = hrt.world_of(sf.parents, v_frames[0])
            hand_weapon = hrt.relative_transform(vw, six["R_Wrist"], six["Weapon"])
            frames, extra_rep["hold_weapon"] = hrt.hold_weapon(rt, clip, frames, hand_weapon)
            extra_rep["weapon_in_r_wrist_frame"] = {"t_m": [round(x, 5) for x in hand_weapon[0]],
                                                    "q_xyzw": [round(x, 5) for x in hand_weapon[1]],
                                                    "from": SF_ANIMS + sf_rel + ".af frame 0"}
        frames = hrt.attach_to(frames, sf, "R_HandIk", "R_Wrist")
        frames = hrt.attach_to(frames, sf, "L_HandIk", "L_Wrist")
        n = clip.n
        stem = sf_rel.rsplit("\\", 1)[1]
        target_dir = clip_dir if kind == "mt" else pistol_dir
        afx_info = aa.parse_afx(v_afx)
        loop = afx_info["tag"] in ("WalkForward", "JogForward", "RunForward")
        if loop:
            events, _au, ev_rep = locomotion_events(sf, frames, clip)
            audio = sorted(((f - FOLEY_LEAD) % (n - 1), foley) for f, name, _p in events if name.startswith("Foot")
                           for _f, foley in afx_info["audio"][:1])
        else:
            events, audio, ev_rep = [], [], {}
        blocks = hrt.blocks_for(bones, frames, n)
        af_path = target_dir / (stem + ".af")
        cal.write_clip(cbones, blocks, n, af_path, name=stem, precision=rig["precision"])
        (target_dir / (stem + ".afx")).write_bytes(
            ra2.afx_vanilla(afx_info["tag"], afx_info["filename"], afx_info["is_state"], events, audio, v_afx, frame_count=n))
        rc = cal.read_clip(str(rig_path), str(af_path))
        got = hrt.local_from_offsets(rc["rig"]["bones"], rc["blocks"], rc["frame_count"])
        hdr = aa.read_af_header(af_path.read_bytes())
        if rc["frame_count"] != n or hdr["bones"] != len(cbones) or hdr["frames"] != n:
            raise Ra4Error(f"{stem}: read-back frames {rc['frame_count']} / header {hdr}")
        rb_err = hrt.readback_error(cbones, [fr[:len(cbones)] for fr in frames], [fr[:len(cbones)] for fr in got])
        metrics = hrt.compare(rt, clip, got)
        if kind == "pistol":
            extra_rep["barrel"] = barrel_check(rt, clip, got)
        side = aa.parse_afx((target_dir / (stem + ".afx")).read_bytes())
        clips_rep.append({
            "fo4": FO4_ANIMS + fo4_rel, "shadows": SF_ANIMS + sf_rel + ".af", "kind": kind,
            "written": str(af_path.relative_to(out)), "wired": kind == "mt",
            "frames": n, "seconds": round((n - 1) / hrt.FPS, 4), "blocks": len(blocks), "header": hdr,
            "vanilla_frames": len(v_frames), "root_end_m": [round(x * rt.k, 4) for x in clip.root[-1][:3]],
            "root_speed_m_s": round(math.hypot(*clip.root[-1][:2]) * rt.k / max(1e-9, (n - 1) / hrt.FPS), 4),
            "afx": {"tag": side["tag"], "is_state": side["is_state"], "events": side["events"], "audio": side["audio"],
                    "kept_elements": [e for e, _t in ra2.afx_elements((target_dir / (stem + ".afx")).read_bytes())[0]]},
            "event_rule": ev_rep, "leg_ik_unreached_max_m": round(max(rt.ik_miss or [0.0]), 5),
            "readback_vs_written": rb_err, "fk_vs_fo4": metrics, **extra_rep})
        if kind == "mt":
            our_paths.append(OUR_MT_FOLDER + "\\" + afx_info["filename"])
    report["clips"] = clips_rep

    # ---------------------------------------------------------------- manifests
    folders = (OUR_MT_FOLDER,) + VANILLA_MT_FOLDERS
    key_default = hr.manifest_key(MT_GRAPH, VANILLA_MT_FOLDERS)
    key = hr.manifest_key(MT_GRAPH, folders)
    base = "meshes\\animtextdata\\"
    vkey, vlist = hrt.parse_animation_file_data(_read(sfa, low, base + f"animationfiledata\\{key_default}.txt"))
    if vkey != key_default:
        raise Ra4Error("default MT animationfiledata names another key")
    new_list = hrt.override_file_list(vlist, our_paths)
    shadowed = sorted(set(vlist) - set(new_list))
    if len(shadowed) != len(our_paths):
        raise Ra4Error(f"{len(our_paths)} clips shadow {len(shadowed)} vanilla entries: {shadowed}")
    files = {f"Meshes\\AnimTextData\\AnimationFileData\\{key}.txt": hrt.animation_file_data_in_order(key, new_list)}
    for kind_dir, out_dir in (("animationoffsets", "AnimationOffsets"), ("animationstancedata", "AnimationStanceData"),
                              ("dynamicidledata", "DynamicIdleData")):
        files[f"Meshes\\AnimTextData\\{out_dir}\\{key}.txt"] = _read(sfa, low, base + f"{kind_dir}\\{key_default}.txt")
    files[f"Meshes\\AnimTextData\\GeneratedSubgraphData\\{EDIDS[F_RACE_ADD].lower()}.txt"] = gsd_row(KEYWORD, MT_GRAPH, folders)
    hr.write_files(files, str(data))
    report["manifests"] = {"key": str(key), "graph": MT_GRAPH, "folders": list(folders),
                           "default_key": str(key_default), "clips_listed": len(new_list), "shadowed": shadowed,
                           "copied_from_default": ["animationoffsets", "animationstancedata", "dynamicidledata"],
                           "files": sorted(files)}

    # ---------------------------------------------------------------- plugin
    own = lambda local: (1 << 24) | local  # noqa: E731
    with esm.Plugin(str(sf_data / "SFBGS003.esm")) as p:
        tpl_race = next(r for r in p.records("RACE") if r.edid == SFBGS003_RACE_EDID)
    with esm.Plugin(str(sf_data / "Starfield.esm")) as p:
        group_order = list(p.groups)
        tpl_kw = next(r for r in p.records("KYWD") if r.formid == TEMPLATE_KEYWORD)
        tpl_npc = next(r for r in p.records("NPC_") if r.formid == TEMPLATE_NPC)
        if not any(r.formid == FOLLOW_PACKAGE for r in p.records("PACK")):
            raise Ra4Error("follow package not found")
    row = row_subrecords([own(F_KYWD)], [], MT_GRAPH, folders, ROW_SRAF_MT_KEYWORD)
    recs = [keyword_record(tpl_kw, own(F_KYWD), KEYWORD),
            addon_race(tpl_race, own(F_RACE_ADD), EDIDS[F_RACE_ADD], "FO4SF RA4 Human add-on", [row])]
    npc_rep = {}
    for fid, kws in ((F_NPC_FO4, [own(F_KYWD)]), (F_NPC_CTRL, [])):
        r, rep = test_npc(tpl_npc, own(fid), EDIDS[fid], NPC_NAMES[fid], kws, FOLLOW_PACKAGE)
        recs.append(r)
        npc_rep[EDIDS[fid]] = rep
    (out / PLUGIN).write_bytes(ra2.plugin_bytes(recs, ["Starfield.esm"], group_order,
                                                description="RA4 Human probe (FO4 human clips on HumanRace)"))
    report["plugin"] = {"file": PLUGIN, "records": {f"{r.formid:08X}": f"{r.sig.decode()} {r.edid}" for r in recs},
                        "npc_edits": npc_rep, "npc_template": f"{TEMPLATE_NPC:08X} {tpl_npc.edid}",
                        "race_template": f"SFBGS003.esm {tpl_race.formid:08X} {SFBGS003_RACE_EDID}",
                        "race_subrecords": len(recs[1].subs), "row": [(s.decode(), d.hex() if len(d) == 4 else esm.zstring(d))
                                                                       for s, d in row]}

    # ---------------------------------------------------------------- archive, batch files, manifest
    loose = sorted(p for p in data.rglob("*") if p.is_file())
    report["ba2"] = ra2.pack_gnrl_ba2_v2([(str(p.relative_to(data)).replace("/", "\\"), p.read_bytes()) for p in loose],
                                         out / MAIN_BA2, starfield_dir)
    bat_dir = out / "bat"
    bat_dir.mkdir(exist_ok=True)
    for f, text in build_bats().items():
        (bat_dir / f).write_text(text, encoding="utf-8")
    manifest = {"probe": PROBE, "plugin": PLUGIN, "ba2": MAIN_BA2, "form_ids_local": {EDIDS[k]: f"{k:06X}" for k in EDIDS},
                "files": {}, "data_files": {}}
    for p in [out / PLUGIN, out / MAIN_BA2] + sorted(bat_dir.glob("*.txt")):
        manifest["files"][str(p.relative_to(out)).replace("/", "\\")] = {"sha256": ra2.sha256_file(p), "size_bytes": p.stat().st_size}
    for p in loose:
        manifest["data_files"][str(p.relative_to(data)).replace("/", "\\")] = {"sha256": ra2.sha256_file(p), "size_bytes": p.stat().st_size}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    report["verify"] = verify(out, dll=dll)
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    (out / "REPORT.md").write_text(report_md(report, manifest), encoding="utf-8")
    return report


def barrel_check(rt: hrt.Retargeter, clip: hrt.Fo4Clip, sf_frames) -> dict:
    """Angle between the gun barrels: Fallout 4's Weapon bone axis that points most forward over the clip, against
    Starfield's Weapon local +Y (its barrel in the vanilla ready idle: local Y -> world +Y within 0.2 deg)."""
    fix, six = rt.fo4.index(), rt.sf.index()
    fws = [hrt.world_of(rt.fo4.parents, fr) for fr in clip.frames]
    axes = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0), (0, -1, 0), (0, 0, -1)]
    score = {ax: sum(aa.q_rotate(w[fix["Weapon"]][1], ax)[1] for w in fws) for ax in axes}
    fo4_axis = max(score, key=score.get)
    worst, total, gun_pos, hands = 0.0, 0.0, 0.0, 0.0
    for fw, fr in zip(fws, sf_frames):
        sw = hrt.world_of(rt.sf.parents, fr)
        a = aa.q_rotate(fw[fix["Weapon"]][1], fo4_axis)
        b = aa.q_rotate(sw[six["Weapon"]][1], (0.0, 1.0, 0.0))
        c = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (math.dist(a, (0, 0, 0)) * math.dist(b, (0, 0, 0)))))
        d = math.degrees(math.acos(c))
        worst, total = max(worst, d), total + d
        rel_sf = [x - y for x, y in zip(sw[six["Weapon"]][0], sw[six["C_Chest"]][0])]
        rel_fo = [rt.k * (x - y) for x, y in zip(fw[fix["Weapon"]][0], fw[fix["Chest"]][0])]
        gun_pos = max(gun_pos, math.dist(rel_sf, rel_fo))
        hands = max(hands, abs(math.dist(sw[six["L_Wrist"]][0], sw[six["Weapon"]][0])
                               - math.dist(fw[fix["LArm_Hand"]][0], fw[fix["Weapon"]][0])))
    return {"fo4_barrel_axis": fo4_axis, "barrel_max_deg": round(worst, 3), "barrel_mean_deg": round(total / len(fws), 3),
            "gun_from_chest_vs_k_fo4_max_m": round(gun_pos, 5), "left_wrist_to_gun_distance_diff_max_m": round(hands, 5)}


def report_md(rep: dict, manifest: dict) -> str:
    L = ["# RA4 Human probe bundle", "",
         "Built by `scripts/probes/stage_ra4_human.py build` (worktree claude-human-anim). Nothing here was run in the "
         "game.", "", "## Files and SHA-256", "", "| file | bytes | SHA-256 |", "|---|---|---|"]
    for f, m in manifest["files"].items():
        L.append(f"| {f} | {m['size_bytes']} | `{m['sha256']}` |")
    L += ["", "## Records (local ids; in game the top byte is the load-order slot)", ""]
    for fid, what in rep["plugin"]["records"].items():
        L.append(f"- `{fid}` {what}")
    L += ["", "## Retarget numbers (read back through the DLL, every frame)", "",
          f"k (hip height ratio) = {rep['retarget']['k_hip_height_ratio']:.4f}", "",
          "| clip | chain | direction deg max/mean | position m max/mean | motion m max/mean | stance slide m max |",
          "|---|---|---|---|---|---|"]
    for c in rep["clips"]:
        for chain, m in c["fk_vs_fo4"].items():
            sl = m.get("stance_slide_m", {}).get("max", "")
            L.append(f"| {Path(c['fo4']).name} | {chain} | {m['direction_deg']['max']:.2f} / {m['direction_deg']['mean']:.2f} | "
                     f"{m['position_m']['max']:.3f} / {m['position_m']['mean']:.3f} | {m['motion_m']['max']:.3f} / "
                     f"{m['motion_m']['mean']:.3f} | {sl} |")
    L += ["", "Read-back against the poses written (quantisation): " +
          "; ".join(f"{Path(c['fo4']).name} {c['readback_vs_written']}" for c in rep["clips"]), ""]
    return "\n".join(L) + "\n"


# =============================================================================================== verify
def verify(stage: Path = OUT, dll: Optional[str] = None) -> dict:
    stage = Path(stage)
    man = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    for rel, meta in man["files"].items():
        p = stage / rel
        if not p.is_file() or ra2.sha256_file(p) != meta["sha256"]:
            raise Ra4Error(f"staged file missing or changed: {rel}")
    entries = ra2.verify_ba2_entry_hashes(stage / MAIN_BA2)
    arc = Ba2(str(stage / MAIN_BA2))
    for rel, meta in man["data_files"].items():
        if hashlib.sha256(arc.read(rel)).hexdigest() != meta["sha256"]:
            raise Ra4Error(f"{MAIN_BA2}: {rel} differs from the staged loose file")
    with esm.Plugin(str(stage / PLUGIN)) as p:
        if p.masters != ["Starfield.esm"]:
            raise Ra4Error(f"masters {p.masters}")
        recs = {}
        for g, spans in p.groups.items():
            for start, end in spans:
                for item in p.walk(start, end):
                    if item[0] == "REC":
                        r = p.record_at(item[1])
                        recs[r.formid] = r
    want = {(1 << 24) | k: v for k, v in EDIDS.items()}
    got = {fid: r.edid for fid, r in recs.items()}
    if got != want:
        raise Ra4Error(f"plugin records {got} != {want}")
    race = recs[(1 << 24) | F_RACE_ADD]
    rows = [esm.zstring(d) for s, d in race.subs if s == b"SAPT"]
    if [s for s, _ in race.subs if s in ROW_SIGS] != [b"SAKD", b"SGNM", b"SAPT", b"SAPT", b"SAPT", b"SAPT", b"SRAF"]:
        raise Ra4Error("add-on race rows are not the one keyword row")
    if race.get(b"SADD") != struct.pack("<I", HUMAN_RACE) or race.get(b"SAKD") != struct.pack("<I", (1 << 24) | F_KYWD):
        raise Ra4Error("add-on race SADD / SAKD")
    if not any(n.lower().replace("/", "\\").startswith(("meshes\\" + rows[0]).lower() + "\\") for n in arc.names):
        raise Ra4Error(f"the row's first folder {rows[0]} has nothing in the archive")
    key = hr.manifest_key(esm.zstring(race.get(b"SGNM")), rows)
    for d in ("AnimationFileData", "AnimationOffsets", "AnimationStanceData", "DynamicIdleData"):
        if arc.find(f"Meshes\\AnimTextData\\{d}\\{key}.txt") is None:
            raise Ra4Error(f"no {d} manifest for the row's key {key}")
    _k, listed = hrt.parse_animation_file_data(arc.read(f"Meshes\\AnimTextData\\AnimationFileData\\{key}.txt"))
    ours = [x for x in listed if x.lower().startswith(rows[0].lower() + "\\")]
    for x in ours:
        for ext in (".af", ".afx"):
            if arc.find("Meshes\\" + x[:-3] + ext) is None:
                raise Ra4Error(f"listed clip {x} has no {ext} in the archive")
    npc_kw = {}
    for fid in (F_NPC_FO4, F_NPC_CTRL):
        r = recs[(1 << 24) | fid]
        kd = r.get(b"KWDA") or b""
        npc_kw[EDIDS[fid]] = [f"{struct.unpack_from('<I', kd, i)[0]:08X}" for i in range(0, len(kd), 4)]
        if struct.unpack("<I", r.get(b"RNAM"))[0] != HUMAN_RACE:
            raise Ra4Error(f"{r.edid} is not on HumanRace")
    if npc_kw[EDIDS[F_NPC_FO4]] != [f"{(1 << 24) | F_KYWD:08X}"] or npc_kw[EDIDS[F_NPC_CTRL]]:
        raise Ra4Error(f"test NPC keywords {npc_kw}")
    bats = {p.name: p.read_text(encoding="utf-8") for p in sorted((stage / "bat").glob("*.txt"))}
    p3 = ra2.validate_bats(bats)
    if sorted(bats) != sorted(BATS):
        raise Ra4Error(f"batch files {sorted(bats)}")
    rig_bones = None
    if aa.find_dll(dll):
        cal = aa.Calumi(dll)
        rb = cal.read_rig(str(stage / "work" / "sf_human_skeleton.rig"))["bones"]
        n_clip = len(hrt.clip_bones(rb))
        rig_bones = len(rb)
        for x in ours:
            h = aa.read_af_header(arc.read("Meshes\\" + x))
            if h["bones"] != n_clip or h["version"] != aa.AF_VERSION or h["kind"] != aa.AF_KIND_FULL:
                raise Ra4Error(f"{x}: header {h}")
    return {"staged_files": len(man["files"]), "ba2_entries": entries, "data_files_in_ba2": len(man["data_files"]),
            "records": {f"{k:08X}": v for k, v in sorted(got.items())}, "row_key": str(key), "row_folders": rows,
            "our_clips_listed": ours, "npc_keywords": npc_kw, "rig_bones": rig_bones, "bats": p3}


# =============================================================================================== install / uninstall
def install(stage: Path, starfield_dir: Path, plugins_txt: Optional[Path] = None,
            min_free_gb: float = DEFAULT_MIN_FREE_GB, check_running=True) -> dict:
    """Copy the plugin and its BA2 into Data, append *FO4SF_RA4Human.esm to Plugins.txt (original kept in
    <stage>\\backup_pre_ra4), write the batch files stamped with the real load-order slot into the game folder and a
    receipt. Refuses to overwrite anything. (Mirrors stage_ra2_handy.install.)"""
    if check_running:
        ra2.check_starfield_not_running()
    verify(stage)
    ra2.check_free_space_gb(starfield_dir, min_free_gb)
    data = starfield_dir / "Data"
    if not data.is_dir():
        raise Ra4Error(f"no Data folder in {starfield_dir}")
    receipt_path = data / RECEIPT
    if receipt_path.exists():
        raise Ra4Error(f"already installed ({receipt_path}); uninstall first")
    ptxt = plugins_txt or ra2._default_plugins_txt()
    orig = ptxt.read_bytes() if ptxt.is_file() else None
    lines = orig.decode("utf-8-sig").splitlines() if orig is not None else []
    backup = stage / "backup_pre_ra4"
    if backup.exists() and any(backup.iterdir()):
        raise Ra4Error(f"non-empty backup folder {backup}; inspect or uninstall first")
    backup.mkdir(parents=True, exist_ok=True)
    if orig is not None:
        (backup / "Plugins.txt").write_bytes(orig)
    added, bats = [], []
    try:
        for name in (PLUGIN, MAIN_BA2):
            dst = data / name
            if dst.exists():
                raise Ra4Error(f"refusing to overwrite {dst}")
            shutil.copy2(stage / name, dst)
            added.append({"name": name, "sha256": ra2.sha256_file(dst)})
        low = {ln.strip().lstrip("*").casefold() for ln in lines if ln.strip()}
        appended = [] if PLUGIN.casefold() in low else [f"*{PLUGIN}"]
        new_lines = lines + appended
        slot = ra2.full_master_slot(data, new_lines, target=PLUGIN)
        for f, text in build_bats(slot).items():
            dst = starfield_dir / f
            if dst.exists():
                raise Ra4Error(f"refusing to overwrite {dst}")
            dst.write_text(text, encoding="utf-8")
            bats.append({"name": f, "sha256": ra2.sha256_file(dst)})
        ptxt.parent.mkdir(parents=True, exist_ok=True)
        ptxt.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        receipt = {"probe": PROBE, "stage_dir": str(stage), "backup_dir": str(backup), "plugins_txt": str(ptxt),
                   "plugins_txt_had_file": orig is not None, "plugins_txt_sha256_after": ra2.sha256_file(ptxt),
                   "appended_plugins_lines": appended, "slot_hex": f"{slot:02X}",
                   "form_ids": {EDIDS[k]: f"{slot:02X}{k:06X}" for k in EDIDS}, "added_data_files": added,
                   "added_root_bats": bats}
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return receipt
    except Exception:
        for b in bats:
            (starfield_dir / b["name"]).unlink(missing_ok=True)
        for a in added:
            (data / a["name"]).unlink(missing_ok=True)
        if orig is not None:
            ptxt.write_bytes(orig)
        shutil.rmtree(backup, ignore_errors=True)
        raise


def uninstall(starfield_dir: Path, plugins_txt: Optional[Path] = None, check_running=True) -> dict:
    """Remove what install added (each file only if unchanged) and restore Plugins.txt byte for byte when nobody
    changed it since; otherwise drop only the appended line. (Mirrors stage_ra2_handy.uninstall.)"""
    if check_running:
        ra2.check_starfield_not_running()
    data = starfield_dir / "Data"
    receipt_path = data / RECEIPT
    if not receipt_path.is_file():
        raise Ra4Error(f"not installed ({receipt_path} missing)")
    rc = json.loads(receipt_path.read_text(encoding="utf-8"))
    for group, root in (("added_root_bats", starfield_dir), ("added_data_files", data)):
        for b in rc[group]:
            p = root / b["name"]
            if p.is_file():
                if ra2.sha256_file(p) != b["sha256"]:
                    raise Ra4Error(f"refusing to delete changed {p}")
                p.unlink()
    ptxt = plugins_txt or Path(rc["plugins_txt"])
    backup = Path(rc["backup_dir"])
    how = "unchanged"
    if ptxt.is_file() and ra2.sha256_file(ptxt) == rc["plugins_txt_sha256_after"]:
        if rc["plugins_txt_had_file"]:
            ptxt.write_bytes((backup / "Plugins.txt").read_bytes())
            how = "restored byte for byte"
        else:
            ptxt.unlink()
            how = "removed (there was none before)"
    elif ptxt.is_file() and rc["appended_plugins_lines"]:
        drop = {ln.casefold() for ln in rc["appended_plugins_lines"]}
        kept = [ln for ln in ptxt.read_text(encoding="utf-8-sig").splitlines() if ln.strip().casefold() not in drop]
        ptxt.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        how = "changed since install: only the appended line was removed"
    (backup / "Plugins.txt").unlink(missing_ok=True)
    if backup.is_dir() and not any(backup.iterdir()):
        backup.rmdir()
    receipt_path.unlink()
    return {"uninstalled": PROBE, "plugins_txt": how}


def status(starfield_dir: Path) -> dict:
    p = starfield_dir / "Data" / RECEIPT
    return {"installed": p.is_file(), "receipt": json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", type=Path, default=OUT)
    b.add_argument("--starfield", type=Path, default=STARFIELD_DIR)
    b.add_argument("--fo4-data", type=Path, default=FO4_DATA)
    b.add_argument("--dll", default=None)
    v = sub.add_parser("verify")
    v.add_argument("--stage-dir", type=Path, default=OUT)
    i = sub.add_parser("install")
    i.add_argument("--stage-dir", type=Path, default=OUT)
    i.add_argument("--starfield", type=Path, required=True)
    i.add_argument("--plugins-txt", type=Path, default=None)
    i.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    u = sub.add_parser("uninstall")
    u.add_argument("--starfield", type=Path, required=True)
    u.add_argument("--plugins-txt", type=Path, default=None)
    s = sub.add_parser("status")
    s.add_argument("--starfield", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        rep = build(a.out, a.starfield, a.fo4_data, a.dll)
        print(json.dumps({"out": str(a.out), "ba2": rep["ba2"], "plugin": rep["plugin"]["records"],
                          "manifest_key": rep["manifests"]["key"], "verify": rep["verify"]["records"]}, indent=1, default=str))
    elif a.cmd == "verify":
        print(json.dumps(verify(a.stage_dir), indent=1))
    elif a.cmd == "install":
        print(json.dumps(install(a.stage_dir, a.starfield, a.plugins_txt, a.min_free_gb), indent=1))
    elif a.cmd == "uninstall":
        print(json.dumps(uninstall(a.starfield, a.plugins_txt), indent=1))
    else:
        print(json.dumps(status(a.starfield), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
