r"""Stage the cut-down "When Freedom Calls" mission (docs/mission/when-freedom-calls.md) and read its in-game log.

usage:
  python make_mission.py stage --out <experiment dir> --fo4 <Fallout4.esm> --starfield <Starfield.esm>
                               --core <FO4TerrainCore.esm> --raider <FO4ActorRaider.esm>
                               [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>] [--no-alias]
      1. dotnet/Mission points: Fallout 4's Concord raiders, the museum door's outside arrival, Preston's NPC metadata
         and Concord talk lines, Codsworth's Sanctuary spot and MQ102-lite 4-choice lines, and the Sanctuary workbench;
      2. dotnet/Mission write + check: FO4SFMission.esm against the given core and raider plugins (offline_check.txt);
      3. the Papyrus compile of FO4SF_Min00Quest.psc, FO4SF_COMPreston.psc, FO4SF_Codsworth01Quest.psc and
         FO4SF_Sanctuary01Quest.psc against every base script of ContentResources.zip;
      4. plan.json (the plugin's, the scripts' and the masters' SHA-256) and README.txt.
      The masters are hashed BEFORE the build and again before publication: a core or raider plugin that changed
      during the build is refused. The stage is built in a new <out>.partial-<time>-<pid> folder (never reused or
      deleted: a failed attempt stays as evidence) and renamed to <out> only when every step passed; an existing
      <out> is refused, so a failed rebuild never touches an earlier stage.
  python make_mission.py fold --mission <stage dir> --core-dir <core experiment dir> --out <new experiment dir>
                              [--raider <FO4ActorRaider.esm>]
      exp_install.py holds one experiment at a time, so the mission goes in WITH the core set: a copy of the core's
      experiment folder plus FO4SFMission.esm and Data\Scripts\FO4SF_Min00Quest.pex (and the companion, Codsworth01 and
      Sanctuary01 .pex files), written only after verify passes on the result (built in a new <out>.partial-<time>-<pid>,
      kept on failure; an existing <out> is refused).
  python make_mission.py verify --exp-dir <experiment dir> --plan <stage dir>\plan.json [--raider <FO4ActorRaider.esm>]
      the install preflight: FO4SFMission.esm and the .pex files in <exp-dir> match the plan's hashes, FO4TerrainCore.esm
      in <exp-dir> and FO4ActorRaider.esm (in <exp-dir>, else --raider) match the masters the plugin was built
      against (it copies the core's world record). Exit 1 on any mismatch or missing file: install only after exit 0.
  python make_mission.py log [--file <fo4sf_mission.0.log>]
      the mission's user log as a summary: stages reached in order, the last status line, the reward, the keeper's
      last line for Preston and for Codsworth; exit 0 when stage 200 was reached, 1 otherwise.
Install (the install session, game closed, on the owner's words): fold, then verify, then
  python scripts/game/exp_install.py install --exp-dir <folded dir> --starfield <game> --plugins <the core set's list>,FO4SFMission.esm --pack
"""
import argparse
import csv
import datetime
import glob
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC_DIR = os.path.join(REPO, "src")
ACTORS_DIR = os.path.join(REPO, "scripts", "actors")
for _p in (SRC_DIR, ACTORS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from convert_codsworth import patch_codsworth_steel_mat  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "Mission")
PLUGIN = "FO4SFMission.esm"
SCRIPT = "FO4SF_Min00Quest"
COM_SCRIPT = "FO4SF_COMPreston"
CODSWORTH_SCRIPT = "FO4SF_Codsworth01Quest"
SANCTUARY_SCRIPT = "FO4SF_Sanctuary01Quest"
MINRECRUIT00_SCRIPT = "FO4SF_MinRecruit00Quest"
MQ103_SCRIPT = "FO4SF_MQ103Quest"
MQ104_SCRIPT = "FO4SF_MQ104Quest"
MQ105_SCRIPT = "FO4SF_MQ105Quest"
MQ106_SCRIPT = "FO4SF_MQ106Quest"
MQ203_SCRIPT = "FO4SF_MQ203Quest"
MQ204_SCRIPT = "FO4SF_MQ204Quest"
MQ206_SCRIPT = "FO4SF_MQ206Quest"
ALL_SCRIPTS = (
    SCRIPT, COM_SCRIPT, CODSWORTH_SCRIPT, SANCTUARY_SCRIPT,
    MINRECRUIT00_SCRIPT, MQ103_SCRIPT, MQ104_SCRIPT, MQ105_SCRIPT,
    MQ106_SCRIPT, MQ203_SCRIPT, MQ204_SCRIPT, MQ206_SCRIPT,
)

ASSET_DIRS = ("meshes", "geometries", "materials", "textures")
CODSWORTH_MESH = "fo4port\\actors\\codsworth\\codsworth.nif"
# robot-anim (--codsworth-handy): the Mr. Handy bundle of scripts/probes/stage_ra2_handy.py. Its plugin is the race
# template for dotnet/Mission; its Data holds the rig, clips, manifests, skeleton and mesh.
HANDY_TEMPLATE = "FO4SF_RA2Handy.esm"
HANDY_MESH = "FO4SF\\Actors\\Handy\\handy.nif"
HANDY_RACE_EDID = "FO4SF_HandyRace"
CODSWORTH_RACE_EDID = "FO4SF_CodsworthRace"
HANDY_DIRS = ("geometries/", "meshes/actors/fo4sf/handy/", "meshes/fo4sf/actors/handy/")
HANDY_MANIFEST_DIRS = ("AnimationFileData", "AnimationOffsets", "AnimationStanceData", "DynamicIdleData")
# Codsworth carries his own VTYP FO4SF_CodsworthVoice (0x819, AllowDefaultDialog) so Starfield resolves his .wem files here:
VOICE_DIR = "sound/voice/" + PLUGIN.lower() + "/fo4sf_codsworthvoice"
# Preston uses Starfield.esm GenericMaleEvenToned (AllowDefaultDialog), resolved under FO4SFMission.esm's voice folder:
PRESTON_VOICE_DIR = "sound/voice/" + PLUGIN.lower() + "/genericmaleeventoned"
FIRST_WEM = 0x00F4C001
FIRST_MQ_WEM = 0x00F4C101
FIRST_PRESTON_WEM = 0x00F4C201

# FormIDs only (zero FO4 text in source): 20 Codsworth Hello INFOs + 5 MQ102 DialogueCodsworthPostWar Codsworth INFOs
HELLO_INFO_IDS = (
    0x000F1F6E, 0x000F1F78, 0x000F1F7D, 0x000841D6, 0x000F1F9C,
    0x000F1F9A, 0x000F1F62, 0x000841C3, 0x000F1F53, 0x000841C1,
    0x000F1F61, 0x000841C2, 0x000F1F48, 0x000841B8, 0x000841B9,
    0x000F1F9D, 0x000841C6, 0x000785E8, 0x000F1F46, 0x000F1F57,
)
MQ102_CODSWORTH_INFO_IDS = (
    0x0001E64D,  # greeting
    0x000A1818,  # choice 1 reply (date / what happened)
    0x000A51A3,  # choice 2 reply (Sanctuary / family)
    0x0019E112,  # choice 3 reply (nearby survivors)
    0x0019E711,  # choice 4 reply (head to Concord)
)
MQ102_CODSWORTH_CLIP_SPECS = (
    (0x0001E64D, (1, 2, 3)),
    (0x000A1818, (1,)),
    (0x000A51A3, (1, 2)),
    (0x0019E112, (1,)),
    (0x0019E711, (1,)),
)
PRESTON_SCENE_CLIP_SPECS = (
    (0x000CA9CC, (1,)),
    (0x0005DF11, (1, 2, 3)),
    (0x0005DF0D, (1, 2)),
    (0x0005DF1B, (1,)),
)

PRESTON_PLACEHOLDER_NOTE = (
    "Starfield human face, colonial/frontier outfit, and weapon placeholder: "
    "HumanRace (0x00347D, UC_NA_PapaKatz 0x01169C template) + GenericMaleEvenToned + "
    "Outfit_FreestarRanger_Vest_with_Hat (0x208E39) + Orion laser rifle (0x2773C8)"
)

STAGES = (10, 20, 30, 35, 40, 200)
PROPERTIES = ("Preston", "Raiders", "Credits")
SPOT_TOLERANCE = 0.5
STARFIELD = os.environ.get("FO4SF_STARFIELD_DIR", "")
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_mission.0.log")
LINE = re.compile(r"FO4SF_MISSION rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")


def path_basename(p):
    """Cross-OS basename splitting on both '/' and '\\'."""
    cleaned = str(p).rstrip("/\\")
    return re.split(r"[\\/]+", cleaned)[-1] if cleaned else ""


def run(cmd, cwd=None):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        sys.exit(f"{path_basename(cmd[0])} exit {r.returncode}")
    return r.stdout


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def refuse_forbidden_output_dir(out_dir):
    """R4: refuse any output directory inside a Git worktree or under a Starfield / Fallout 4 game folder."""
    for candidate in {os.path.abspath(out_dir), os.path.realpath(os.path.abspath(out_dir))}:
        low_norm = candidate.replace("\\", "/").lower()
        if "steamapps/common/starfield" in low_norm or "steamapps/common/fallout 4" in low_norm:
            sys.exit(f"{out_dir}: refusing output inside a game install folder ({candidate})")
        cur = candidate
        while True:
            if os.path.exists(os.path.join(cur, ".git")):
                sys.exit(f"{out_dir}: refusing output inside a Git worktree ({cur})")
            if os.path.isfile(os.path.join(cur, "Starfield.exe")) or os.path.isfile(os.path.join(cur, "Fallout4.exe")):
                sys.exit(f"{out_dir}: refusing output inside a game install folder ({cur})")
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent


def mandatory_properties(psc_text):
    """The names of the script's Auto Const Mandatory properties (what the plugin must fill), in source order."""
    return [m.group(1) for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\s+Const\s+Mandatory\b",
                                            psc_text, re.M | re.I)]


def script_floats(psc_text):
    """The script's float properties with a default (`float Property Name = value Auto Const`), as {name: value}."""
    return {m.group(1): float(m.group(2)) for m in re.finditer(
        r"^\s*float\s+Property\s+(\w+)\s*=\s*(-?[\d.]+)\s+Auto\s+Const\b", psc_text, re.M | re.I)}


def spot_problem(psc_text, pos, who="Preston"):
    """None when points.json's position of who (Preston or Codsworth) is the script's <who>LocalX/Y/Z (within
    SPOT_TOLERANCE), else why not."""
    f = script_floats(psc_text)
    want = [f[who + "LocalX"], f[who + "LocalY"], f[who + "LocalZ"]]
    got = [float(v) for v in pos]
    if len(got) != 3 or any(abs(a - b) > SPOT_TOLERANCE for a, b in zip(got, want)):
        return (f"points.json puts {who} at {got} but {SCRIPT}.psc {who}LocalX/Y/Z are {want}: set them to the "
                f"points and stage again")
    return None


def extract_sources(zip_path, work):
    """Every base script (Scripts/Source/*.psc, top level) and the flags file from ContentResources.zip."""
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        sys.exit(f"{zip_path}: no Scripts/Source base scripts or flags file")
    return src


def compile_script(compiler, src_dir, out_dir, script):
    os.makedirs(out_dir, exist_ok=True)
    name = script + ".psc"
    out = run([compiler, name, "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"], cwd=HERE)
    pex = os.path.join(out_dir, script + ".pex")
    if "Compilation succeeded" not in out or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {script}.pex")
    return pex


def split_fuz_xwma(data):
    """Extract xWMA RIFF bytes from a Fallout 4 .fuz file."""
    if data[:4] != b"FUZE":
        raise ValueError(f"not a .fuz header: {data[:4]!r}")
    _ver, lip_len = struct.unpack_from("<II", data, 4)
    xwma = data[12 + lip_len:]
    if xwma[:4] != b"RIFF":
        raise ValueError(f".fuz audio stream is not RIFF: {xwma[:4]!r}")
    return xwma


def extract_fo4_strings(interface_ba2_path, dest_dir):
    """Extract Strings/Fallout4_en.*STRINGS from Fallout4 - Interface.ba2 into dest_dir."""
    from fo4sf.ba2 import Ba2
    arch = Ba2(interface_ba2_path)
    os.makedirs(dest_dir, exist_ok=True)
    extracted = 0
    for entry in arch.entries:
        low = entry.name.lower().replace("\\", "/")
        if low.startswith("strings/fallout4_en."):
            out_file = os.path.join(dest_dir, low.rsplit("/", 1)[-1])
            with open(out_file, "wb") as f:
                f.write(arch.read(entry.name))
            extracted += 1
    if extracted < 3:
        sys.exit(f"{interface_ba2_path}: expected 3 Fallout4_en.*STRINGS files, found {extracted}")
    return dest_dir


def find_wwise_console(explicit=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    env_wwise = os.environ.get("WWISE_CONSOLE")
    if env_wwise and os.path.isfile(env_wwise):
        return env_wwise
    on_path = shutil.which("WwiseConsole")
    if on_path:
        return on_path
    appdata = os.environ.get("APPDATA", "")
    known = os.path.join(appdata, "WwiseLauncher", "Json", "knownInstalls.json") if appdata else ""
    if known and os.path.isfile(known):
        with open(known, encoding="utf-8") as f:
            roots = json.load(f)
        for root in reversed(roots if isinstance(roots, list) else []):
            cand = os.path.join(str(root), "Authoring", "x64", "Release", "bin", "WwiseConsole.exe")
            if os.path.isfile(cand):
                return cand
    return None


def find_xwmaencode(fo4_esm_path, explicit=None):
    if explicit and os.path.isfile(explicit):
        return explicit
    fo4_data = os.path.dirname(os.path.abspath(fo4_esm_path))
    fo4_root = os.path.dirname(fo4_data)
    bundled = os.path.join(fo4_root, "Tools", "Audio", "xwmaencode.exe")
    if os.path.isfile(bundled):
        return bundled
    return shutil.which("xwmaencode")


def wav_duration_seconds(wav_path):
    """Measure PCM .wav duration in seconds (with deterministic size fallback for synthetic test stubs)."""
    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0 and frames > 0:
                return round(frames / float(rate), 3)
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        pass
    try:
        return round(max(0.5, os.path.getsize(wav_path) / 88200.0), 3)
    except OSError:
        return 1.0


def _norm_voice_spec(spec):
    norm = str(spec).strip().lower().replace("\\", "/").strip("/")
    if "/" in norm:
        folder, stem = norm.rsplit("/", 1)
        return norm, folder, stem, f"{folder}__{stem}"
    return norm, "robotmrhandy", norm, norm


def convert_fuz_stems_to_wem(voices_ba2_path, stems, xwmaencode_exe, wwise_console_exe, scratch_dir,
                             conversion="Vorbis Quality High", return_durations=False):
    """Convert `stems` (e.g. ['0001e64d_1', 'npcmprestongarvey/000ca9cc_1', ...]) from Fallout4 - Voices.ba2 -> .wem."""
    from fo4sf.ba2 import Ba2
    arch = Ba2(voices_ba2_path)
    by_low = {e.name.lower().replace("\\", "/"): e.name for e in arch.entries}
    xwm_dir = os.path.join(scratch_dir, "xwm")
    wav_dir = os.path.join(scratch_dir, "wav")
    wem_dir = os.path.join(scratch_dir, "wem")
    os.makedirs(xwm_dir, exist_ok=True)
    os.makedirs(wav_dir, exist_ok=True)
    os.makedirs(wem_dir, exist_ok=True)

    specs = [_norm_voice_spec(s) for s in stems]
    durations = {}
    flat_names = []
    for norm_key, folder, stem, flat in specs:
        key = f"sound/voice/fallout4.esm/{folder}/{stem}.fuz"
        if key not in by_low:
            sys.exit(f"{voices_ba2_path}: missing voice entry {key}")
        xwma = split_fuz_xwma(arch.read(by_low[key]))
        xp = os.path.join(xwm_dir, flat + ".xwm")
        wp = os.path.join(wav_dir, flat + ".wav")
        with open(xp, "wb") as f:
            f.write(xwma)
        run([xwmaencode_exe, xp, wp])
        if not os.path.isfile(wp) or os.path.getsize(wp) == 0:
            sys.exit(f"xwmaencode did not produce {wp}")
        durations[norm_key] = wav_duration_seconds(wp)
        flat_names.append(flat)

    proj = os.path.join(scratch_dir, "wwise", "CodsworthStageVoice", "CodsworthStageVoice.wproj")
    run([wwise_console_exe, "create-new-project", proj, "--platform", "Windows", "--quiet"])
    wsources = os.path.join(scratch_dir, "sources.wsources")
    with open(wsources, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f'<ExternalSourcesList SchemaVersion="1" Root="{wav_dir}">\n')
        for flat in sorted(set(flat_names)):
            f.write(f'  <Source Path="{flat}.wav" Conversion="{conversion}"/>\n')
        f.write("</ExternalSourcesList>\n")
    run([wwise_console_exe, "convert-external-source", proj, "--platform", "Windows", "--source-file", wsources,
         "--output", wem_dir, "--quiet"])

    by_flat = {}
    for dp, _, fns in os.walk(wem_dir):
        for fn in fns:
            if fn.lower().endswith(".wem"):
                by_flat[os.path.splitext(fn.lower())[0]] = os.path.join(dp, fn)
    found = {}
    missing = []
    for orig, (norm_key, _folder, _stem, flat) in zip(stems, specs):
        if flat in by_flat:
            found[norm_key] = by_flat[flat]
        else:
            missing.append(orig)
    if missing:
        sys.exit(f"WwiseConsole missing converted .wem files: {missing}")
    return (found, durations) if return_durations else found


def _build_scene_voice_payload(clip_specs, folder_prefix, first_wem, voice_dir, available_ba2_keys, converted, durations, data_dir):
    """Copy converted .wem clips for a scene into Data/<voice_dir>/ and build the JSON spec for dotnet/Mission."""
    copied = []
    # Assign primary clip (#1) of greeting + each choice first to preserve contiguous base WEM IDs, then continuations
    primary_wems = []
    per_entry_stems = []
    for fid, resp_nums in clip_specs:
        entry_keys = []
        for rnum in resp_nums:
            stem = f"{fid:08x}_{rnum}"
            spec_key = f"{folder_prefix}/{stem}" if folder_prefix else stem
            ba2_folder = folder_prefix or "robotmrhandy"
            ba2_key = f"sound/voice/fallout4.esm/{ba2_folder}/{stem}.fuz"
            if rnum == 1 or ba2_key in available_ba2_keys:
                entry_keys.append(spec_key)
        per_entry_stems.append(entry_keys)

    next_wem = first_wem
    assigned = {}
    for entry_keys in per_entry_stems:
        wem_hex = f"{next_wem:08x}"
        next_wem += 1
        assigned[entry_keys[0]] = wem_hex
        primary_wems.append(wem_hex)
    for entry_keys in per_entry_stems:
        for extra_key in entry_keys[1:]:
            assigned[extra_key] = f"{next_wem:08x}"
            next_wem += 1

    os.makedirs(os.path.join(data_dir, *voice_dir.split("/")), exist_ok=True)
    clips_lists = []
    for entry_keys in per_entry_stems:
        entry_clips = []
        for spec_key in entry_keys:
            wem_hex = assigned[spec_key]
            rel = f"{voice_dir}/{wem_hex}.wem"
            shutil.copy2(converted[spec_key], os.path.join(data_dir, *rel.split("/")))
            copied.append(rel)
            entry_clips.append({"wem": wem_hex, "duration": float(durations.get(spec_key, 0.0))})
        clips_lists.append(entry_clips)

    payload = {
        "greeting_wem": primary_wems[0],
        "reply_wems": primary_wems[1:],
        "greeting_clips": clips_lists[0],
        "reply_clips": clips_lists[1:],
    }
    return copied, payload


def stage_mq102_and_hello_voices(a, pts, data_dir, tmp_dir, has_explicit_hello_voice):
    """Build-time voice staging for Codsworth (Hello + MQ102 scene) and Preston (Min00 scene)."""
    from fo4sf.ba2 import Ba2
    fo4_data = os.path.dirname(os.path.abspath(a.fo4))
    voices_ba2 = getattr(a, "fo4_voices", None) or os.path.join(fo4_data, "Fallout4 - Voices.ba2")
    if not os.path.isfile(voices_ba2):
        return [], None, None, None

    xwm_exe = find_xwmaencode(a.fo4, getattr(a, "xwmaencode", None))
    wwise_exe = find_wwise_console(getattr(a, "wwise_console", None))
    if not xwm_exe or not wwise_exe:
        return [], None, None, None

    want_codsworth = bool(getattr(a, "codsworth", True))
    want_preston = bool(getattr(a, "alias", True))
    if not want_codsworth and not want_preston:
        return [], None, None, None

    arch = Ba2(voices_ba2)
    available_ba2_keys = {e.name.lower().replace("\\", "/") for e in arch.entries}

    needed_stems = []
    hello_rows = (pts.get("codsworth_hellos") or []) if want_codsworth else []
    if want_codsworth:
        for fid, resp_nums in MQ102_CODSWORTH_CLIP_SPECS:
            for rnum in resp_nums:
                stem = f"{fid:08x}_{rnum}"
                ba2_key = f"sound/voice/fallout4.esm/robotmrhandy/{stem}.fuz"
                if rnum == 1 or ba2_key in available_ba2_keys:
                    needed_stems.append(stem)
        if not has_explicit_hello_voice and hello_rows:
            for hr in hello_rows:
                needed_stems.append(f"{hr['info'].lower()}_{hr['response']}")

    if want_preston:
        for fid, resp_nums in PRESTON_SCENE_CLIP_SPECS:
            for rnum in resp_nums:
                stem = f"{fid:08x}_{rnum}"
                ba2_key = f"sound/voice/fallout4.esm/npcmprestongarvey/{stem}.fuz"
                if rnum == 1 or ba2_key in available_ba2_keys:
                    needed_stems.append(f"npcmprestongarvey/{stem}")

    converted, durations = convert_fuz_stems_to_wem(
        voices_ba2, sorted(set(needed_stems)), xwm_exe, wwise_exe,
        os.path.join(tmp_dir, "audio_conv"), return_durations=True
    )

    copied = []
    voice_json_out = None
    mq_voice_json = None
    preston_voice_json = None

    if want_codsworth:
        dest_voice_dir = os.path.join(data_dir, *VOICE_DIR.split("/"))
        os.makedirs(dest_voice_dir, exist_ok=True)
        if not has_explicit_hello_voice and hello_rows:
            lines = []
            for idx, hr in enumerate(hello_rows):
                stem = f"{hr['info'].lower()}_{hr['response']}"
                wem_hex = f"{FIRST_WEM + idx:08x}"
                rel = f"{VOICE_DIR}/{wem_hex}.wem"
                shutil.copy2(converted[stem], os.path.join(data_dir, *rel.split("/")))
                copied.append(rel)
                text = hr["text"]
                sex = "male" if re.search(r"\bsir\b", text, re.I) else "female" if re.search(r"\bmum\b", text, re.I) else None
                lines.append({
                    "info": hr["info"], "response": int(hr["response"]), "text": text,
                    "wem": wem_hex, "sex": sex, "duration": float(durations.get(stem, 0.0)),
                })
            voice_json_out = os.path.join(tmp_dir, "auto_hello_voice.json")
            with open(voice_json_out, "w", encoding="utf-8") as f:
                json.dump(lines, f, indent=1)

        mq_copied, mq_payload = _build_scene_voice_payload(
            MQ102_CODSWORTH_CLIP_SPECS, "", FIRST_MQ_WEM, VOICE_DIR,
            available_ba2_keys, converted, durations, data_dir
        )
        copied.extend(mq_copied)
        mq_voice_json = os.path.join(tmp_dir, "mq_voice.json")
        with open(mq_voice_json, "w", encoding="utf-8") as f:
            json.dump(mq_payload, f, indent=1)

    if want_preston:
        pr_copied, pr_payload = _build_scene_voice_payload(
            PRESTON_SCENE_CLIP_SPECS, "npcmprestongarvey", FIRST_PRESTON_WEM, PRESTON_VOICE_DIR,
            available_ba2_keys, converted, durations, data_dir
        )
        copied.extend(pr_copied)
        preston_voice_json = os.path.join(tmp_dir, "preston_voice.json")
        with open(preston_voice_json, "w", encoding="utf-8") as f:
            json.dump(pr_payload, f, indent=1)

    return copied, voice_json_out, mq_voice_json, preston_voice_json


def stage(a):
    with open(os.path.join(HERE, SCRIPT + ".psc"), encoding="utf-8") as f:
        psc = f.read()
    props = mandatory_properties(psc)
    if tuple(props) != PROPERTIES:
        sys.exit(f"{SCRIPT}.psc properties {props} differ from what dotnet/Mission writes {list(PROPERTIES)}")
    final = os.path.abspath(a.out)
    refuse_forbidden_output_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    masters = pin_masters((a.core, a.raider))
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]

    fo4_data = os.path.dirname(os.path.abspath(a.fo4))
    iface_ba2 = getattr(a, "fo4_interface", None) or os.path.join(fo4_data, "Fallout4 - Interface.ba2")
    has_real_fo4_ba2 = os.path.isfile(a.fo4) and os.path.isfile(iface_ba2)

    with tempfile.TemporaryDirectory(prefix="fo4sf-mission-tmp-") as tmp_dir:
        points = os.path.join(tmp_dir if has_real_fo4_ba2 else work, "points.json")
        if has_real_fo4_ba2:
            sdir = extract_fo4_strings(iface_ba2, os.path.join(tmp_dir, "Strings"))
            hello_csv = ",".join(f"{fid:08X}" for fid in HELLO_INFO_IDS)
            run(tool + ["points", a.fo4, points, "--strings-dir", sdir, "--hello-infos", hello_csv])
        else:
            run(tool + ["points", a.fo4, points])

        with open(points, encoding="utf-8") as f:
            pts = json.load(f)
        problem = spot_problem(psc, pts["preston"]["pos"])
        if not problem and a.codsworth and pts.get("codsworth"):
            problem = spot_problem(psc, pts["codsworth"]["pos"], "Codsworth")
        if problem:
            sys.exit(f"{problem}; attempt kept in {out}")

        alias = [] if a.alias else ["--no-alias"]
        cods = [] if a.codsworth else ["--no-codsworth"]
        assets = set()
        if getattr(a, "codsworth_assets", None):
            if not a.codsworth:
                sys.exit("--codsworth-assets needs Codsworth (drop --no-codsworth)")
            assets = set(copy_assets(a.codsworth_assets, os.path.join(out, "Data")))
            cods = ["--codsworth-model", CODSWORTH_MESH]
        if getattr(a, "codsworth_handy", None):
            if not a.codsworth:
                sys.exit("--codsworth-handy needs Codsworth (drop --no-codsworth)")
            template, handy_copied = copy_handy_bundle(a.codsworth_handy, os.path.join(out, "Data"))
            assets |= set(handy_copied)
            cods = ["--codsworth-model", HANDY_MESH, "--codsworth-handy", template]

        has_explicit_voice = bool(getattr(a, "codsworth_voice", None))
        if has_explicit_voice:
            if not a.codsworth:
                sys.exit("--codsworth-voice needs Codsworth (drop --no-codsworth)")
            voice_json = os.path.join(tmp_dir if has_real_fo4_ba2 else work, "voice.json")
            assets |= set(copy_voice(a.codsworth_voice, os.path.join(out, "Data"), voice_json))
            cods = cods + ["--codsworth-voice", voice_json]

        if (a.codsworth or a.alias) and has_real_fo4_ba2:
            extra_copied, auto_hello_json, mq_voice_json, preston_voice_json = stage_mq102_and_hello_voices(
                a, pts, os.path.join(out, "Data"), tmp_dir, has_explicit_voice
            )
            assets |= set(extra_copied)
            if auto_hello_json:
                cods = cods + ["--codsworth-voice", auto_hello_json]
            if mq_voice_json:
                cods = cods + ["--codsworth-mq-voice", mq_voice_json]
            if preston_voice_json:
                alias = alias + ["--preston-voice", preston_voice_json]

        looks_args = []
        if getattr(a, "actor_looks_assets", None):
            assets |= set(copy_actor_looks_assets(a.actor_looks_assets, os.path.join(out, "Data")))
            looks_args = ["--actor-looks-dir", a.actor_looks_assets]

        run(tool + ["write", a.starfield, a.core, a.raider, points, out, "--plugin", PLUGIN] + alias + cods + looks_args)
        check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, a.core, a.raider] + alias + cods + looks_args)

    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    src = extract_sources(a.content_resources, work)
    scripts_dir = os.path.join(out, "Data", "Scripts")
    compiled_pex = {}
    for scr_name in ALL_SCRIPTS:
        compiled_pex[scr_name] = compile_script(a.compiler, src, scripts_dir, scr_name)
        shutil.copy(os.path.join(HERE, scr_name + ".psc"), os.path.join(out, scr_name + ".psc"))
    if os.path.isdir(work):
        shutil.rmtree(work)

    pex = compiled_pex[SCRIPT]
    com_pex = compiled_pex[COM_SCRIPT]
    drift = [f"{n}: {masters[n]} at the start, {h} now" for n, h in pin_masters((a.core, a.raider)).items()
             if h != masters[n]]
    if drift:
        sys.exit("a master changed during the build, nothing published (" + "; ".join(drift) + f"); attempt kept in {out}")

    plugin_sha = sha256(os.path.join(out, PLUGIN))
    scripts_sha = {scr_name: sha256(p_path) for scr_name, p_path in compiled_pex.items()}
    assets_sha = {rel: sha256(os.path.join(out, "Data", *rel.split("/"))) for rel in sorted(assets)}
    outputs_sha = {PLUGIN: plugin_sha}
    for scr_name, digest in scripts_sha.items():
        outputs_sha[f"Data/Scripts/{scr_name}.pex"] = digest
    for rel, digest in assets_sha.items():
        outputs_sha[f"Data/{rel}"] = digest

    plan = {
        "kind": "mission",
        "plugin": PLUGIN,
        "plugin_sha256": plugin_sha,
        "script": SCRIPT,
        "script_sha256": scripts_sha[SCRIPT],
        "companion_script": COM_SCRIPT,
        "companion_script_sha256": scripts_sha[COM_SCRIPT],
        "scripts": scripts_sha,
        "outputs": outputs_sha,
        "alias": a.alias,
        "masters_sha256": masters,
        "stages": list(STAGES),
        "raiders": [r["src"] for r in pts["raiders"]],
        "preston": pts["preston"],
        "preston_placeholder": PRESTON_PLACEHOLDER_NOTE,
        "codsworth": pts.get("codsworth") if a.codsworth else None,
        "sanctuary_workbench": {"fo4_src": "0250FE", "core_base": "0A2ECD", "core_ref": "005C50",
                                "merged_pos": [-2329.25043, -1420.19271, 112.08571]},
        "assets": assets_sha,
        "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_mission.0.log",
    }
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    raiders = ", ".join(f"{r['src']} ({r.get('dist_m', '?')} m)" for r in pts["raiders"])
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Cut-down "When Freedom Calls", Codsworth MQ102-lite, and Sanctuary Workbench ({datetime.date.today().isoformat()}).
{PLUGIN} (sha256 {plan['plugin_sha256']}):
- QUST FO4SF_Min00 (0x0800, started at FO4SFNewGame stage 200 via StartNoWait; NOT StartGameEnabled),
- QUST FO4SF_CodsworthKeeper (0x0814, started at FO4SFNewGame stage 200 via StartNoWait; NOT StartGameEnabled),
- QUST FO4SF_COMPreston (0x0815, test-only follow alias gated behind FO4SF_TestModeEnabled != 0),
- QUST FO4SF_Codsworth01 (0x0816, MQ102-lite 4-choice Sanctuary conversation pointing to Concord; NOT StartGameEnabled),
- QUST FO4SF_Sanctuary01 (0x0817, full Min01 Sanctuary settlement quest completed in place on workbench 0250FE / FO4TerrainCore.esm 0x005C50 + Sturges 0x0A00/0x0A01, started at FO4SF_Min00 stage 200),
- QUST FO4SF_MinRecruit00 (0x0A20, The First Step — Tenpines Bluff / Corvega / Flare Gun 0x0A25, NOT StartGameEnabled),
- QUST FO4SF_MQ103 (0x0A50, Jewel of the Commonwealth — Diamond City Gate / Piper / Mayor / Valentine Detective Agency, NOT StartGameEnabled),
- QUST FO4SF_MQ104 (0x0A80, Unlikely Valentine — Park Street Station / Vault 114 / Nick Valentine / Skinny Malone, NOT StartGameEnabled),
- QUST FO4SF_MQ105 (0x0AB0, Getting a Clue — Valentine Agency / Kellogg's House / Cigar Trail / Fort Hagen 0D handoff, NOT StartGameEnabled).
Preston Garvey (0x0801 / ACHR 0x0802 at {pts['preston']['pos']} m): {PRESTON_PLACEHOLDER_NOTE}.
Raiders: {len(pts['raiders'])} ACHR(s) of FO4_LvlRaider ({raiders}).
Codsworth: {"NPC_ FO4_Codsworth (0x0810, FO4SF_CodsworthRace AllowPcDialog + FO4SF_CodsworthVoice AllowDefaultDialog) at " + str(plan["codsworth"]["pos"]) + " m" if plan["codsworth"] else "left out (--no-codsworth)"}.
Masters (must match the installed files): {json.dumps(masters)}. Rebuild after any core change.
Scripts compiled into Data\\Scripts\\: {", ".join(s + ".pex" for s in ALL_SCRIPTS)}.
The follow command is test-only (requires FO4SFCoreValues.esm:0x000860 FO4SF_TestModeEnabled != 0):
  cgf "FO4SF_COMPreston.FollowTest"
Install (game closed): fold this stage into a copy of the core set and verify it first:
  python scripts\\mission\\make_mission.py fold --mission "{final}" --core-dir <core experiment dir> --out <new dir>
Log: {plan['log']} (read with: python scripts\\mission\\make_mission.py log).
Uninstall: exp_install.py uninstall.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, " + ", ".join(f"Data\\Scripts\\{s}.pex" for s in ALL_SCRIPTS) +
          ", offline_check.txt, plan.json, README.txt")


def copy_assets(src, data):
    """Copies the asset folders (ASSET_DIRS) of a convert_codsworth.py output into data; anything else stays out.
    Upgrades any unpatched handy*.mat JSON files to brushed-steel/chrome PBR parameters (M6)."""
    mesh = os.path.join(src, "meshes", *CODSWORTH_MESH.split("\\"))
    if not os.path.isfile(mesh):
        sys.exit(f"--codsworth-assets {src} has no meshes\\{CODSWORTH_MESH}")
    copied = []
    for d in ASSET_DIRS:
        root = os.path.join(src, d)
        for dirpath, _, files in os.walk(root):
            for name in files:
                rel = os.path.relpath(os.path.join(dirpath, name), src)
                dst = os.path.join(data, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                rel_slash = rel.replace(os.sep, "/")
                if d == "materials" and name.lower().endswith(".mat") and "/handy/" in rel_slash.lower():
                    try:
                        with open(os.path.join(src, rel), encoding="utf-8") as mf:
                            mat_obj = json.load(mf)
                    except (OSError, UnicodeDecodeError, ValueError):
                        mat_obj = None
                    if isinstance(mat_obj, dict) and "Objects" in mat_obj and "Summary" in mat_obj:
                        patched = patch_codsworth_steel_mat(mat_obj)
                        with open(dst, "wb") as out_f:
                            out_f.write((json.dumps(patched, indent="\t", sort_keys=True) + "\n").encode("utf-8"))
                        copied.append(rel_slash)
                        continue
                shutil.copy2(os.path.join(src, rel), dst)
                copied.append(rel_slash)
    return copied


def handy_bundle_files(src):
    """robot-anim: {path under the bundle's Data: path under the mission's Data} for Codsworth on the Mr. Handy body.
    Takes the Handy mesh, skeleton, rig, clips and geometry, the manifests of the template race's own sub-graph keys, and
    its generated sub-graph text renamed for FO4SF_CodsworthRace. Leaves the bundle's Mini Bot test files out."""
    from fo4sf import handy_race as hr
    from fo4sf.planet import esm
    template = os.path.join(src, HANDY_TEMPLATE)
    root = os.path.join(src, "Data")
    if not os.path.isfile(template) or not os.path.isdir(root):
        sys.exit(f"--codsworth-handy {src} is not a stage_ra2_handy.py bundle ({HANDY_TEMPLATE} and Data\\)")
    with esm.Plugin(template) as p:
        race = next((r for r in p.records("RACE") if r.edid == HANDY_RACE_EDID), None)
    if race is None:
        sys.exit(f"--codsworth-handy: {HANDY_TEMPLATE} has no RACE {HANDY_RACE_EDID}")
    keys = {f"{hr.manifest_key(g, f)}.txt" for g, f in hr.race_subgraph_sets(race)}
    gsd = f"meshes/animtextdata/generatedsubgraphdata/{HANDY_RACE_EDID.lower()}.txt"
    out = {}
    for dirpath, _, files in os.walk(root):
        for name in files:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            low = rel.lower()
            parts = low.split("/")
            if low == gsd:
                out[rel] = "meshes/AnimTextData/GeneratedSubgraphData/" + CODSWORTH_RACE_EDID.lower() + ".txt"
            elif low.startswith(HANDY_DIRS):
                out[rel] = rel
            elif (len(parts) == 4 and parts[:2] == ["meshes", "animtextdata"] and
                  parts[2] in {d.lower() for d in HANDY_MANIFEST_DIRS} and name in keys):
                out[rel] = rel
    mesh = "meshes/" + HANDY_MESH.replace("\\", "/").lower()
    if not any(v.lower() == mesh for v in out.values()):
        sys.exit(f"--codsworth-handy: the bundle has no Data\\meshes\\{HANDY_MESH}")
    if gsd not in {k.lower() for k in out}:
        sys.exit(f"--codsworth-handy: the bundle has no generated sub-graph text for {HANDY_RACE_EDID}")
    return template, out


def copy_handy_bundle(src, data):
    """Copies handy_bundle_files() into data; refuses to overwrite. Returns (template plugin, copied paths under data)."""
    template, files = handy_bundle_files(src)
    copied = []
    for rel, out_rel in sorted(files.items()):
        dst = os.path.join(data, *out_rel.split("/"))
        if os.path.exists(dst):
            sys.exit(f"--codsworth-handy would overwrite Data/{out_rel}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(src, "Data", *rel.split("/")), dst)
        copied.append(out_rel)
    return template, copied


def copy_actor_looks_assets(src, data):
    """Verifies and copies staged C5 Fallout 4 Preston & Concord raider outfit assets (ASSET_DIRS) into Data."""
    actors_dir = os.path.join(REPO, "scripts", "actors")
    if actors_dir not in sys.path:
        sys.path.insert(0, actors_dir)
    import stage_c5_actor_looks  # noqa: E402

    stage_c5_actor_looks.verify_staged_c5_assets(src, require_preston_mats=True)
    copied = []
    for d in ASSET_DIRS:
        root = os.path.join(src, d)
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for name in files:
                rel = os.path.relpath(os.path.join(dirpath, name), src)
                dst = os.path.join(data, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(src, rel), dst)
                copied.append(rel.replace(os.sep, "/"))
    stage_c5_actor_looks.verify_staged_c5_assets(data, require_preston_mats=True)
    return copied


def copy_voice(src, data, voice_json):
    """Reads src/lines.tsv, finds each line's src/wem/**/<info>_<response>.wem, copies it to data/VOICE_DIR/<wem>.wem
    with the line's WEMFile id (FIRST_WEM on, 8 lowercase hex digits) and writes voice.json for the writer."""
    with open(os.path.join(src, "lines.tsv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    wems = {}
    for dirpath, _, files in os.walk(os.path.join(src, "wem")):
        for name in files:
            if name.lower().endswith(".wem"):
                wems.setdefault(name.lower(), []).append(os.path.join(dirpath, name))
    lines, copied = [], []
    for i, r in enumerate(rows):
        want = f"{r['info'].lower()}_{r['response']}.wem"
        hits = wems.get(want, [])
        if len(hits) != 1:
            sys.exit(f"--codsworth-voice: {len(hits)} files named {want} under {os.path.join(src, 'wem')}")
        wem = f"{FIRST_WEM + i:08x}"
        text = r["text"]
        sex = "male" if re.search(r"\bsir\b", text, re.I) else "female" if re.search(r"\bmum\b", text, re.I) else None
        rel = f"{VOICE_DIR}/{wem}.wem"
        os.makedirs(os.path.join(data, *VOICE_DIR.split("/")), exist_ok=True)
        shutil.copy2(hits[0], os.path.join(data, *rel.split("/")))
        copied.append(rel)
        lines.append({"info": r["info"], "response": int(r["response"]), "text": text, "wem": wem, "sex": sex})
    if not lines:
        sys.exit(f"--codsworth-voice: {src}/lines.tsv has no lines")
    with open(voice_json, "w", encoding="utf-8") as f:
        json.dump(lines, f, indent=1)
    return copied


def pin_masters(paths):
    """{file name: SHA-256} of the masters the plugin is built against."""
    return {path_basename(p): sha256(p) for p in paths}


def new_partial(final, create=True):
    """A new, unique attempt folder beside final (<final>.partial-<UTC time>-<pid>[-n])."""
    base = f"{final}.partial-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    if create:
        os.makedirs(out)
    return out


def _plan_scripts(plan):
    if isinstance(plan.get("scripts"), dict) and plan["scripts"]:
        return dict(plan["scripts"])
    out = {plan["script"]: plan["script_sha256"]}
    if plan.get("companion_script"):
        out[plan["companion_script"]] = plan["companion_script_sha256"]
    return out


def verify_dir(exp_dir, plan, raider=None):
    """Problems (a list of strings, empty when the experiment folder may be installed) of an experiment folder against
    a mission plan."""
    problems = []

    def same(label, path, want):
        if not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        elif sha256(path) != want:
            problems.append(f"{label}: {path} sha256 {sha256(path)} is not the plan's {want}")

    same("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    for scr_name, scr_sha in _plan_scripts(plan).items():
        same(f"script {scr_name}", os.path.join(exp_dir, "Data", "Scripts", scr_name + ".pex"), scr_sha)
    for rel, want in plan.get("assets", {}).items():
        same("asset", os.path.join(exp_dir, "Data", *rel.split("/")), want)
    for name, want in plan["masters_sha256"].items():
        path = os.path.join(exp_dir, name)
        if not os.path.isfile(path) and raider and name.lower() == path_basename(raider).lower():
            path = raider
        same(f"master {name}", path, want)
    return problems


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("plugin", "plugin_sha256", "script", "script_sha256", "masters_sha256") if k not in plan]
    if missing or plan.get("kind") != "mission":
        sys.exit(f"{path} is not a mission plan (missing {missing})")
    return plan


def verify(a):
    problems = verify_dir(a.exp_dir, load_plan(a.plan), a.raider)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def fold(a):
    final = os.path.abspath(a.out)
    refuse_forbidden_output_dir(final)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.mission, "plan.json"))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"{a.core_dir} already holds {plan['plugin']}")
    out = new_partial(final, create=False)
    shutil.copytree(a.core_dir, out)
    shutil.copy2(os.path.join(a.mission, plan["plugin"]), os.path.join(out, plan["plugin"]))
    script_rels = ["Scripts/" + s + ".pex" for s in _plan_scripts(plan)]
    for rel in script_rels + sorted(plan.get("assets", {})):
        dst = os.path.join(out, "Data", *rel.split("/"))
        if os.path.exists(dst):
            sys.exit(f"fold refused: the core set already has Data/{rel} (attempt kept in {out})")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(a.mission, "Data", *rel.split("/")), dst)
    problems = verify_dir(out, plan, a.raider)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); nothing published (attempt kept in {out})")
    os.replace(out, final)
    print(f"folded {final}: {a.core_dir} + {plan['plugin']} + {len(script_rels)} script(s)"
          f" + {len(plan.get('assets', {}))} Codsworth asset(s); verify ok")
    return 0


def next_stage(stage, dead, total, fighting, at_preston, found=False):
    """The script's NextStage (FO4SF_Min00Quest.psc)."""
    s = stage
    if s < 20 and (fighting or dead > 0 or found):
        s = 20
    if s < 30 and total > 0 and dead == total:
        s = 30
    if s == 30 and at_preston:
        s = 40
    return s


def wfc01_step(player_pos, interior, door_pos, raiders, dt=1.0, check_radius=150.0, door_radius=100.0,
               subterranean_drop=8.0, max_drift=140.0, absent_distance=250.0, absent_limit=60.0,
               stuck_move_radius=2.0, stuck_limit=60.0):
    """Python mirror of CheckConcordRaidersWfc01 (FO4SF_Min00Quest.psc) at stage 20.
    Each raider dict holds {"pos": (x,y,z), "target": (tx,ty,tz), "dead": bool, "loaded": bool,
    "absent_sec": float, "cleared": bool, ...}. Mutates raiders in place and returns (rescued_indices, newly_cleared_indices)."""
    if interior:
        return [], []
    door_dist = math.dist(player_pos, door_pos)
    rescued, newly_cleared = [], []
    for i, r in enumerate(raiders):
        if r.get("dead") or r.get("cleared"):
            r["absent_sec"] = 0.0
            r["rescue_sec"] = 0.0
            continue
        tx, ty, tz = r["target"]
        rx, ry, rz = r["pos"]
        if door_dist < check_radius:
            drift = math.dist((rx, ry, rz), (tx, ty, tz))
            if rz < tz - subterranean_drop or drift > max_drift:
                r["pos"] = (tx, ty, tz)
                rx, ry, rz = tx, ty, tz
                r["rescued"] = True
                r["rescue_sec"] = 0.0
                r["rescue_pos"] = (rx, ry, rz)
                r["rescue_hp"] = float(r.get("hp", 100.0))
                rescued.append(i)
        if dt > 0.0:
            dist_p = math.dist(player_pos, (rx, ry, rz))
            if door_dist <= door_radius and (not r.get("loaded", True) or dist_p > absent_distance):
                r["absent_sec"] = r.get("absent_sec", 0.0) + dt
                if r["absent_sec"] > absent_limit:
                    r["cleared"] = True
                    r["clear_reason"] = "absent"
                    r["stopped_combat"] = True
                    r["disabled"] = True
                    r["absent_sec"] = 0.0
                    r["rescue_sec"] = 0.0
                    newly_cleared.append(i)
            else:
                r["absent_sec"] = 0.0
            if not r.get("cleared") and r.get("rescued") and r.get("loaded", True):
                ref_pos = r.get("rescue_pos", (rx, ry, rz))
                ref_hp = float(r.get("rescue_hp", r.get("hp", 100.0)))
                cur_hp = float(r.get("hp", 100.0))
                moved = math.dist((rx, ry, rz), ref_pos)
                if moved >= stuck_move_radius or cur_hp < ref_hp - 0.01:
                    r["rescue_sec"] = 0.0
                    r["rescue_pos"] = (rx, ry, rz)
                    r["rescue_hp"] = cur_hp
                else:
                    r["rescue_sec"] = r.get("rescue_sec", 0.0) + dt
                    if r["rescue_sec"] >= stuck_limit:
                        r["cleared"] = True
                        r["clear_reason"] = "stuck"
                        r["stopped_combat"] = True
                        r["disabled"] = True
                        r["rescue_sec"] = 0.0
                        newly_cleared.append(i)
    return rescued, newly_cleared


def place_at(off, dp, to_spot, interior, fighting, held=False, landed=None, hold=25.0, gap=1500.0, radius=300.0,
             held_radius=3.0, following=False):
    """The script's PlaceAt decision with its caller's hold (FO4SF_Min00Quest.psc: PlacePreston, PlaceCodsworth, HoldDue)."""
    if following:
        return "follow"
    if fighting:
        held = False
    state = lambda s, h: s + ", held" if h else s
    if off <= hold and dp < gap:
        return state("at spot", held or (not fighting and off <= held_radius))
    if interior:
        return state("off, player inside", held)
    if to_spot > radius:
        return state("off, player away", held)
    if dp < gap and fighting:
        return state("off, fighting", held)
    if landed is None:
        return "move"
    if not landed:
        return state("move failed", held)
    return state("placed", held or not fighting)


def off_of(msg):
    """A keeper line's off= (m from the spot) as a float, or None when it has none or it is unreadable."""
    off = re.search(r" off=(\S+)", msg)
    try:
        return float(off.group(1)) if off else None
    except ValueError:
        return None


def summarize(lines):
    """Summarize fo4sf_mission.0.log across FO4SF_Min00, FO4SF_CodsworthKeeper, FO4SF_Codsworth01, and FO4SF_Sanctuary01."""
    s = {"stages": [], "stage_causes": {}, "status": None, "reward": None, "startcombat": 0, "activated": 0, "found": None,
         "preston_moves": 0, "keeper": None, "preston_off": None,
         "codsworth_moves": 0, "codsworth_keeper": None, "codsworth_off": None,
         "follow": None, "follow_package": None, "holds_after_follow": 0, "follow_refused_test_mode": False,
         "reloads": 0, "wfc01_rescues": 0, "wfc01_absent_cleared": 0, "wfc01_stuck_cleared": 0,
         "mission_gate": None, "min00_given_by": None,
         "codsworth_scene_requested": 0, "codsworth_dialogue_menu_opened": 0, "codsworth_talk_fallbacks": [],
         "codsworth_talk_opened": 0, "codsworth_choices": [],
         "codsworth_talk_end": False, "codsworth01_complete": None,
         "preston_scene_requested": 0, "preston_dialogue_menu_opened": 0, "preston_talk_fallbacks": [],
         "preston_talk_opened": 0, "preston_choices": [],
         "preston_talk_end": None, "stage40_fallback": False,
         "min01_bench_activated": False, "sanctuary01_complete": None,
         "sanctuary01_bench_log": None,
         "sanctuary01_stages": [], "sanctuary01_finished": None,
         "minrecruit00_stages": [], "minrecruit00_complete": None,
         "mq103_stages": [], "mq103_complete": None,
         "mq104_stages": [], "mq104_complete": None,
         "mq105_stages": [], "mq105_complete": None,
         "mq106_stages": [], "mq106_complete": None,
         "mq203_stages": [], "mq203_complete": None,
         "mq204_stages": [], "mq204_complete": None,
         "mq206_stages": [], "mq206_complete": None,
         "stand_in_events": [], "blocked_missing_port": []}
    follow_seen = False
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        msg = m.group("msg")
        low = msg.lower()
        if low.startswith("stage "):
            parts = msg.split()
            st_num = int(parts[1])
            s["stages"].append(st_num)
            m_by = re.search(r"\bby=([a-z0-9_]+)", low)
            if m_by:
                s["stage_causes"][st_num] = m_by.group(1)
            if st_num == 40 and "by=fallback" in low:
                s["stage40_fallback"] = True
        elif low.startswith("mission gate ") and "quest=" not in low:
            s["mission_gate"] = msg
        elif low.startswith("min00 given by="):
            s["min00_given_by"] = msg.split("=", 1)[1].strip()
        elif low.startswith("status "):
            s["status"] = msg
        elif low.startswith("reward credits="):
            s["reward"] = int(msg.split("=", 1)[1])
        elif low.startswith("startcombat "):
            s["startcombat"] += 1
        elif low.startswith("preston activated"):
            s["activated"] += 1
        elif low.startswith("preston scene talk requested "):
            s["preston_scene_requested"] += 1
        elif low == "preston dialogue menu opened":
            s["preston_dialogue_menu_opened"] += 1
        elif low.startswith("preston talk fallback=messagebox reason="):
            s["preston_talk_fallbacks"].append(msg.split("reason=", 1)[1].split()[0])
        elif low.startswith("preston talk opened"):
            s["preston_talk_opened"] += 1
        elif low.startswith("preston choice button="):
            s["preston_choices"].append(int(msg.split("=", 1)[1].split()[0]))
        elif low.startswith("preston talk end "):
            s["preston_talk_end"] = msg
        elif low.startswith("found preston ") and s["found"] is None:
            s["found"] = msg[len("found preston "):]
        elif low.startswith("moved preston "):
            s["preston_moves"] += 1
        elif low.startswith("moved codsworth "):
            s["codsworth_moves"] += 1
        elif low.startswith("reload mission "):
            s["reloads"] += 1
        elif low.startswith("wfc01 rescue "):
            s["wfc01_rescues"] += 1
        elif "raider cleared absent" in low or "raider cleared stuck" in low or low.startswith("wfc01 absent_cleared "):
            if "raider cleared stuck" in low:
                s["wfc01_stuck_cleared"] += 1
            else:
                s["wfc01_absent_cleared"] += 1
        elif low.startswith("codsworth scene talk requested "):
            s["codsworth_scene_requested"] += 1
        elif low == "codsworth dialogue menu opened":
            s["codsworth_dialogue_menu_opened"] += 1
        elif low.startswith("codsworth talk fallback=messagebox reason="):
            s["codsworth_talk_fallbacks"].append(msg.split("reason=", 1)[1].split()[0])
        elif low.startswith("codsworth talk opened"):
            s["codsworth_talk_opened"] += 1
        elif low.startswith("codsworth choice button="):
            s["codsworth_choices"].append(int(msg.split("=", 1)[1].split()[0]))
        elif low.startswith("codsworth talk end -> min00 stage 10"):
            s["codsworth_talk_end"] = True
        elif low.startswith("codsworth01 complete "):
            s["codsworth01_complete"] = msg
        elif low.startswith("min01 bench activated -> stage 100"):
            s["min01_bench_activated"] = True
        elif low.startswith("sanctuary01 bench_activated=true "):
            s["sanctuary01_bench_log"] = msg
            if "complete=true" in low:
                s["sanctuary01_complete"] = msg
        elif low.startswith("sanctuary01 stand_in_build_menu ") or low.startswith("mq106 prydwen_stand_in=true") or low.startswith("mq203 stand_in_scan=true") or low.startswith("mq206 stand_in_build "):
            s["stand_in_events"].append(msg)
        elif low.startswith("mq203 brain_move blocked=true") or low.startswith("mq206 relay_blocked "):
            s["blocked_missing_port"].append(msg)
        elif low.startswith("sanctuary01 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["sanctuary01_stages"].append(int(parts[2]))
        elif low.startswith("sanctuary01 finished "):
            s["sanctuary01_finished"] = msg
        elif low.startswith("minrecruit00 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["minrecruit00_stages"].append(int(parts[2]))
        elif low.startswith("minrecruit00 complete "):
            s["minrecruit00_complete"] = msg
        elif low.startswith("mq103 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq103_stages"].append(int(parts[2]))
        elif low.startswith("mq103 complete "):
            s["mq103_complete"] = msg
        elif low.startswith("mq104 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq104_stages"].append(int(parts[2]))
        elif low.startswith("mq104 complete "):
            s["mq104_complete"] = msg
        elif low.startswith("mq105 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq105_stages"].append(int(parts[2]))
        elif low.startswith("mq105 complete "):
            s["mq105_complete"] = msg
        elif low.startswith("mq106 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq106_stages"].append(int(parts[2]))
        elif low.startswith("mq106 complete "):
            s["mq106_complete"] = msg
        elif low.startswith("mq203 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq203_stages"].append(int(parts[2]))
        elif low.startswith("mq203 complete "):
            s["mq203_complete"] = msg
        elif low.startswith("mq204 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq204_stages"].append(int(parts[2]))
        elif low.startswith("mq204 complete "):
            s["mq204_complete"] = msg
        elif low.startswith("mq206 stage "):
            parts = msg.split()
            if len(parts) >= 3 and parts[2].isdigit():
                s["mq206_stages"].append(int(parts[2]))
        elif low.startswith("mq206 complete "):
            s["mq206_complete"] = msg
        elif low.startswith("follow preston test-only refused: test mode off"):
            s["follow"] = msg
            s["follow_refused_test_mode"] = True
        elif low.startswith("follow preston test-only"):
            s["follow"] = msg
            follow_seen = True
        elif low.startswith("follow preston package="):
            s["follow_package"] = msg
            follow_seen = True
        elif low.startswith("follow preston "):
            follow_seen = True
        elif low.startswith("hold preston ") and follow_seen:
            s["holds_after_follow"] += 1
        elif low.startswith(("keeper load preston ", "keeper status preston ")):
            s["keeper"], s["preston_off"] = msg, off_of(msg)
        elif low.startswith(("keeper load codsworth ", "keeper status codsworth ")):
            s["codsworth_keeper"], s["codsworth_off"] = msg, off_of(msg)
    return s


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = summarize(f)
    print(json.dumps(s, indent=1))
    return 0 if 200 in s["stages"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--fo4", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--core", required=True)
    s.add_argument("--raider", required=True)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--fo4-interface", default=None, help="optional path to Fallout4 - Interface.ba2")
    s.add_argument("--fo4-voices", default=None, help="optional path to Fallout4 - Voices.ba2")
    s.add_argument("--xwmaencode", default=None, help="optional path to xwmaencode.exe")
    s.add_argument("--wwise-console", default=None, help="optional path to WwiseConsole.exe")
    s.add_argument("--no-alias", dest="alias", action="store_false")
    s.add_argument("--no-codsworth", dest="codsworth", action="store_false", help="leave Codsworth out of the plugin")
    s.add_argument("--codsworth-voice", default=None,
                   help="a codsworth_voice.py output folder (lines.tsv, wem): his Hello lines and their .wem files")
    s.add_argument("--codsworth-assets", default=None,
                   help="a convert_codsworth.py output folder: his own model (ARMA, skin ARMO) and its files in Data")
    s.add_argument("--codsworth-handy", default=None,
                   help="a scripts/probes/stage_ra2_handy.py bundle: Codsworth on the Mr. Handy body with his Fallout 4 "
                        "skeleton and animations (race and body parts from its plugin, files from its Data)")
    s.add_argument("--actor-looks-assets", default=None,
                   help="a stage_c5_actor_looks.py output folder: Preston & Concord raider FO4 outfit NIF/mesh/mat/dds files")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    v = sub.add_parser("verify")
    v.add_argument("--exp-dir", required=True)
    v.add_argument("--plan", required=True)
    v.add_argument("--raider", default=None)
    fo = sub.add_parser("fold")
    fo.add_argument("--mission", required=True)
    fo.add_argument("--core-dir", required=True)
    fo.add_argument("--out", required=True)
    fo.add_argument("--raider", default=None)
    a = p.parse_args(argv)
    if a.cmd == "stage":
        stage(a)
        return 0
    if a.cmd == "verify":
        return verify(a)
    if a.cmd == "fold":
        return fold(a)
    return log(a)


if __name__ == "__main__":
    sys.exit(main())
