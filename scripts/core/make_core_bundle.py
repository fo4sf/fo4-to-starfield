r"""Stage, fold, verify, and inspect logs for the unified FO4SF Core Candidate Bundle (CF-10).

Stages every core component from one checkout (core values, gear door, exit lift, mission + Codsworth assets/voice,
NewGame with hold 199 and pod_step -2.5, rads, hardcore, workshop, route loot, power armor, progression,
list dialogue, combat + FO4SFCombat.dll, reputation, companions, A-Life when present, Fort Hagen when present,
the console-free candidate walk harness, and --with-pipboy --pipboy-stage), folds them into a clean hardlinked
copy of the owner's core set, runs full SHA-256 + TES4 master-order + plugin-count + 4 GiB BA2 archive-limit
verification, and prints one `exp_install.py install ... --pack` command plus its matching rollback command.

Refuses to run whenever Starfield.exe is open (via fo4sf.launcher.crashwatch.System.pids) or when any output
directory sits inside a Git worktree or game folder (R4).

usage:
  python scripts/core/make_core_bundle.py build --owner-set <owner-set-dir> --out <bundle-dir>
      --work <scratch-stage-dir> --starfield-dir <Starfield> --fo4-data <Fallout 4/Data>
      --port <FO4Port.esm> --port-ids <formids.json>
      --door-anim-dll <CALUMI.Animation.dll> --collision-template <nif> --texconv <texconv.exe>
      [--render-python <venv-render/python.exe>] [--combat-sfse-build <combat-sfse-dir>]
      [--mission-stage <02b-mission-dir>] [--route-loot-stage <17-route-loot-dir>]
      [--with-pipboy --pipboy-stage <pipboy-stage-dir>]
      [--no-alife] [--no-fort-hagen] [--no-walk-harness] [--no-hardlink]

  python scripts/core/make_core_bundle.py fold --owner-set <owner-set-dir> --stages-root <stages-dir>
      --out <bundle-dir> [--clean-core-out <clean-core-dir>] [--port <FO4Port.esm>]
      [--mission-stage <02b-mission-dir>] [--route-loot-stage <17-route-loot-dir>]
      [--with-pipboy --pipboy-stage <pipboy-stage-dir>] [--no-hardlink]

  python scripts/core/make_core_bundle.py verify --bundle-dir <bundle-dir>
      [--plan <bundle-dir>/bundle_plan.json] [--port <FO4Port.esm>]
      [--max-plugins 245] [--max-ba2-bytes 4294967295]

  python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <bundle-dir> --starfield <Starfield>
  python scripts/core/make_core_bundle.py sidecar-undo --starfield <Starfield>
  python scripts/core/make_core_bundle.py sidecar-status --starfield <Starfield>

  python scripts/core/make_core_bundle.py log [--log-dir <My Games/Starfield/Logs/Script/User>]
      [--sfse-log-dir <My Games/Starfield/SFSE/Logs>] [--no-pipboy]
      [--step all|exit|hold|rads|hardcore|workshop|powerarmor|dialogue|progression|combat|reputation|companions|pipboy]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (
    os.path.join(REPO, "src"),
    os.path.join(REPO, "scripts", "game"),
    os.path.join(REPO, "scripts", "newgame"),
    os.path.join(REPO, "scripts", "planet"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exp_install  # noqa: E402
import make_newgame  # noqa: E402
from make_workshop_probe import compile_text  # noqa: E402
from fo4sf.core import bundle_log, cross_plugin_check  # noqa: E402
from fo4sf.core.core_values import core_form_id  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402
from fo4sf.planet.esm import EsmError, Plugin as RawEsmPlugin  # noqa: E402

MAX_STARFIELD_PLUGINS = 245
MAX_BA2_BYTES = (4 * (1024 ** 3)) - 1  # 4,294,967,295 bytes (32-bit unsigned BA2 ceiling)
SIDECAR_RECEIPT_NAME = "FO4SFSidecar.install.json"
SIDECAR_BACKUP_DIRNAME = ".fo4sf_sidecar_backup"

INSTALL_LINE_RE = re.compile(r"(exp_install\.py install\b.*?--plugins )(?P<plugins>\S+)(?P<tail>.*)")
HEX_HEAD_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

DROPPED_SLICE_ESMS = frozenset({
    "fo4sfbridge.esm",
    "fo4sfcorevalues.esm",
    "fo4sfnewgame.esm",
    "fo4sfvaultgeardoor.esm",
    "fo4sfexitlift.esm",
    "fo4sfrads.esm",
    "fo4sfhardcore.esm",
    "fo4sfworkshop.esm",
    "fo4sfrouteloot.esm",
    "fo4sfpowerarmor.esm",
    "fo4sfprogression.esm",
    "fo4sflistdialogue.esm",
    "fo4sfcombat.esm",
    "fo4sfreputation.esm",
    "fo4sfcompanions.esm",
    "fo4sfalife.esm",
    "fo4sfforthagen.esm",
    "fo4sfcorecandidate.esm",
    "fo4sfpipboyprobe.esm",
    "fo4sfpipboytravel.esm",
})

DROPPED_MISSION_ESMS = frozenset({
    "fo4sfmission.esm",
})

DROPPED_SLICE_PEX = frozenset({
    "data/scripts/fo4sf_newgamequest.pex",
    "data/scripts/fo4sf_newgamelooks.pex",
    "data/scripts/fo4sf_newgamespecial.pex",
    "data/scripts/fo4sf_newgameversion.pex",
    "data/scripts/fo4sf_radscorequest.pex",
    "data/scripts/fo4sf_hardcorequest.pex",
    "data/scripts/fo4sf_workshopcorequest.pex",
    "data/scripts/fo4sf_powerarmorcorequest.pex",
    "data/scripts/fo4sf_progressionquest.pex",
    "data/scripts/fo4sf_listdialoguequest.pex",
    "data/scripts/fo4sf_combatquest.pex",
    "data/scripts/fo4sf_combatinput.pex",
    "data/scripts/fo4sf_reputationquest.pex",
    "data/scripts/fo4sf_companionsquest.pex",
    "data/scripts/fo4sf_alifecontrollerquest.pex",
    "data/scripts/fo4sf_forthagenquest.pex",
    "data/scripts/fo4sf_corecandidatewalk.pex",
    "data/scripts/fo4sf_pipboytravel.pex",
})

DROPPED_MISSION_PEX = frozenset({
    "data/scripts/fo4sf_min00quest.pex",
    "data/scripts/fo4sf_compreston.pex",
    "data/scripts/fo4sf_codsworth01quest.pex",
    "data/scripts/fo4sf_sanctuary01quest.pex",
})

DROPPED_MISSION_DATA_PREFIXES = (
    "data/sound/voice/fo4sfmission.esm/",
    "data/meshes/fo4port/actors/codsworth/",
    "data/materials/fo4port/texsets/actors/handy/",
    "data/textures/fo4port/texsets/actors/handy/",
)

ORDERED_COMPONENT_KEYS = (
    "core_values",
    "cog_door",
    "exit_lift",
    "mission",
    "newgame",
    "rads",
    "hardcore",
    "workshop",
    "route_loot",
    "powerarmor",
    "progression",
    "list_dialogue",
    "combat",
    "reputation",
    "companions",
    "alife",
    "fort_hagen",
    "candidate_walk",
    "pipboy",
)

EXPERIMENTAL_CORE_COMPONENT_KEYS = frozenset({
    "rads",
    "hardcore",
    "progression",
    "list_dialogue",
    "combat",
    "reputation",
    "companions",
    "alife",
})

EXPERIMENTAL_CORE_ESMS = frozenset({
    "fo4sfrads.esm",
    "fo4sfhardcore.esm",
    "fo4sfprogression.esm",
    "fo4sflistdialogue.esm",
    "fo4sfcombat.esm",
    "fo4sfreputation.esm",
    "fo4sfcompanions.esm",
    "fo4sfalife.esm",
})

PLAYER_BUNDLE_PLUGINS = (
    "FO4ActorRaider.esm",
    "FO4TerrainCore.esm",
    "FO4TerrainCore_Mars.esm",
    "FO4SFCoreValues.esm",
    "FO4SFVaultGearDoor.esm",
    "FO4SFExitLift.esm",
    "FO4SFMission.esm",
    "FO4SFNewGame.esm",
    "FO4SFWorkshop.esm",
    "FO4SFPowerArmor.esm",
    "FO4SFFortHagen.esm",
    "FO4SFPipboyProbe.esm",
    "FO4SFPipboyTravel.esm",
)

PLAYER_WITH_EXPERIMENTAL_CORE_PLUGINS = (
    "FO4ActorRaider.esm",
    "FO4TerrainCore.esm",
    "FO4TerrainCore_Mars.esm",
    "FO4SFCoreValues.esm",
    "FO4SFVaultGearDoor.esm",
    "FO4SFExitLift.esm",
    "FO4SFMission.esm",
    "FO4SFNewGame.esm",
    "FO4SFRads.esm",
    "FO4SFHardcore.esm",
    "FO4SFWorkshop.esm",
    "FO4SFPowerArmor.esm",
    "FO4SFProgression.esm",
    "FO4SFListDialogue.esm",
    "FO4SFCombat.esm",
    "FO4SFReputation.esm",
    "FO4SFCompanions.esm",
    "FO4SFALife.esm",
    "FO4SFFortHagen.esm",
    "FO4SFPipboyProbe.esm",
    "FO4SFPipboyTravel.esm",
)

PLAYER_WITH_ROUTE_LOOT_PLUGINS = (
    *PLAYER_WITH_EXPERIMENTAL_CORE_PLUGINS[:11],
    "FO4SFRouteLoot.esm",
    *PLAYER_WITH_EXPERIMENTAL_CORE_PLUGINS[11:],
)

CORE_BUNDLE_PLUGINS = (
    *PLAYER_WITH_EXPERIMENTAL_CORE_PLUGINS[:19],
    "FO4SFCoreCandidate.esm",
    *PLAYER_WITH_EXPERIMENTAL_CORE_PLUGINS[19:],
)

CORE_WITH_ROUTE_LOOT_PLUGINS = (
    *PLAYER_WITH_ROUTE_LOOT_PLUGINS[:20],
    "FO4SFCoreCandidate.esm",
    *PLAYER_WITH_ROUTE_LOOT_PLUGINS[20:],
)

TEST_CELL_SLICE_KEYS = frozenset({"powerarmor", "list_dialogue", "combat", "reputation", "companions"})


class BundleRefused(RuntimeError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_game_closed(system=None) -> None:
    """Refuse to run if Starfield.exe is running or process inspection fails."""
    sys_obj = system if system is not None else System()
    try:
        pids = sys_obj.pids(GAME_EXE)
    except ValueError as err:
        raise BundleRefused(f"bundle refused: cannot confirm {GAME_EXE} is closed ({err})") from err
    if pids:
        joined = ", ".join(str(p) for p in pids)
        raise BundleRefused(f"bundle refused: {GAME_EXE} is running (pid {joined}); close the game first")


def refuse_unsafe_output_dir(
    path_str: str,
    label: str = "--out",
    game_dirs: Sequence[Optional[str]] = (),
) -> None:
    """R4: refuse any bundle/work/clean-core output path inside a Git worktree or game folder."""
    forbidden_roots = [os.path.abspath(gd) for gd in game_dirs if gd]
    for candidate in {os.path.abspath(path_str), os.path.realpath(os.path.abspath(path_str))}:
        low_norm = candidate.replace("\\", "/").lower()
        if "steamapps/common/starfield" in low_norm or "steamapps/common/fallout 4" in low_norm:
            raise BundleRefused(f"bundle refused ({label}): output path inside game install folder ({candidate})")
        cand_case = os.path.normcase(candidate)
        for froot in forbidden_roots:
            froot_case = os.path.normcase(froot)
            if cand_case == froot_case or cand_case.startswith(froot_case + os.sep):
                raise BundleRefused(f"bundle refused ({label}): output path inside game folder ({froot})")
        cur = candidate
        while True:
            if os.path.exists(os.path.join(cur, ".git")):
                raise BundleRefused(f"bundle refused ({label}): output path inside Git worktree ({cur})")
            if (
                os.path.isfile(os.path.join(cur, "Starfield.exe"))
                or os.path.isfile(os.path.join(cur, "Fallout4.exe"))
                or os.path.isfile(os.path.join(cur, "Data", "Starfield.esm"))
            ):
                raise BundleRefused(f"bundle refused ({label}): output path inside game install folder ({cur})")
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent


def current_git_head(repo_dir: str = REPO) -> Optional[str]:
    """Return the current checkout's 40-char git commit SHA, or None outside a git checkout."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    sha = r.stdout.strip().lower()
    return sha if HEX_HEAD_RE.match(sha) else None


def _heads_match(bundle_head: str, tool_head: str) -> bool:
    bh = bundle_head.strip().lower()
    th = tool_head.strip().lower()
    if not bh or not th:
        return True
    if bh == th:
        return True
    if HEX_HEAD_RE.match(bh) and HEX_HEAD_RE.match(th):
        return bh.startswith(th) or th.startswith(bh)
    return False


def link_or_copy(src: str, dst: str, hardlink: bool = True) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if hardlink:
        os.link(src, dst)
    else:
        shutil.copy2(src, dst)


def prepare_clean_core(
    owner_set: str,
    clean_out: str,
    hardlink: bool = True,
    strip_mission: bool = False,
    extra_dropped_data: Sequence[str] = (),
) -> Dict[str, object]:
    """Create a clean copy of owner_set without slice ESMs/PEX (and stale mission files when strip_mission=True)."""
    refuse_unsafe_output_dir(clean_out, label="--clean-core-out")
    src_root = Path(os.path.abspath(owner_set))
    dst_root = Path(os.path.abspath(clean_out))
    if not src_root.is_dir():
        raise BundleRefused(f"owner-set directory not found: {src_root}")
    src_readme = src_root / "README.txt"
    if not src_readme.is_file():
        raise BundleRefused(f"owner-set missing README.txt: {src_readme}")
    if dst_root.exists():
        raise BundleRefused(f"clean-core output already exists: {dst_root}")

    dropped_esms = (DROPPED_SLICE_ESMS | DROPPED_MISSION_ESMS) if strip_mission else DROPPED_SLICE_ESMS
    dropped_pex = (DROPPED_SLICE_PEX | DROPPED_MISSION_PEX) if strip_mission else DROPPED_SLICE_PEX
    extra_drop_low = {
        r.replace("\\", "/").lower()
        for r in extra_dropped_data
        if r.replace("\\", "/").lower() != "data/materials/fo4port/_neutral.mat"
    }

    orig_readme_sha = sha256_file(str(src_readme))
    linked_count = 0
    dropped: List[str] = []

    partial = Path(make_newgame.new_partial(str(dst_root), create=True))
    for dp, dirs, files in os.walk(src_root):
        dirs.sort()
        rel_dir = Path(dp).relative_to(src_root)
        for fn in sorted(files):
            s = Path(dp) / fn
            rel_posix = s.relative_to(src_root).as_posix()
            rel_low = rel_posix.lower()
            if rel_low == "readme.txt":
                continue
            if (
                ("/" not in rel_posix and rel_low in dropped_esms)
                or rel_low in dropped_pex
                or rel_low in extra_drop_low
                or (strip_mission and rel_low.startswith(DROPPED_MISSION_DATA_PREFIXES))
            ):
                dropped.append(rel_posix)
                continue
            link_or_copy(str(s), str(partial / rel_dir / fn), hardlink=hardlink)
            linked_count += 1

    def strip_slice_plugins(line: str) -> str:
        m = INSTALL_LINE_RE.search(line)
        if not m:
            return line
        kept = [p for p in m.group("plugins").split(",") if p and p.lower() not in dropped_esms]
        if not kept:
            raise BundleRefused("clean-core README install line has zero base core plugins left after stripping slice ESMs")
        return line[:m.start()] + m.group(1) + ",".join(kept) + m.group("tail")

    readme_lines = src_readme.read_text(encoding="utf-8").splitlines()
    new_readme = "\n".join(strip_slice_plugins(ln) for ln in readme_lines) + "\n"
    (partial / "README.txt").write_text(new_readme, encoding="utf-8", newline="\n")

    if sha256_file(str(src_readme)) != orig_readme_sha:
        raise BundleRefused("source owner-set README.txt sha256 changed unexpectedly!")

    os.replace(str(partial), str(dst_root))
    base_plugins = make_newgame.core_plugins(str(dst_root), new_readme)
    return {
        "clean_core_dir": str(dst_root),
        "base_plugins": base_plugins,
        "linked_files": linked_count,
        "dropped_files": sorted(dropped),
        "owner_readme_sha256": orig_readme_sha,
    }


def resolve_stage_source(stage_dir: str, rel_posix: str) -> str:
    """Resolve a bundle-relative output path inside stage_dir (supporting Data/<Plugin>.esm stagers like Fort Hagen)."""
    direct = os.path.join(stage_dir, *rel_posix.split("/"))
    if os.path.isfile(direct):
        return direct
    if "/" not in rel_posix and rel_posix.lower().endswith(".esm"):
        in_data = os.path.join(stage_dir, "Data", rel_posix)
        if os.path.isfile(in_data):
            return in_data
    return direct


def extract_component_outputs(comp_key: str, stage_dir: str) -> Tuple[List[str], Dict[str, str]]:
    """Read a staged component folder and return (ordered_plugins, {rel_posix_path: sha256})."""
    st = os.path.abspath(stage_dir)
    if not os.path.isdir(st):
        raise BundleRefused(f"component {comp_key}: stage directory missing ({st})")
    plan_p = os.path.join(st, "plan.json")
    outputs: Dict[str, str] = {}
    plugins: List[str] = []
    plan_plugin_sha: Optional[str] = None

    if os.path.isfile(plan_p):
        with open(plan_p, encoding="utf-8") as f:
            plan = json.load(f)
        if isinstance(plan.get("plugins"), list) and plan["plugins"]:
            plugins = list(plan["plugins"])
        elif isinstance(plan.get("plugin"), str) and plan["plugin"]:
            plugins = [plan["plugin"]]
        if isinstance(plan.get("plugin_sha256"), str):
            plan_plugin_sha = plan["plugin_sha256"]

        if isinstance(plan.get("outputs"), dict) and plan["outputs"]:
            for rel, digest in plan["outputs"].items():
                rel_norm = rel.replace("\\", "/")
                if rel_norm in plugins:
                    continue
                outputs[rel_norm] = digest
        elif isinstance(plan.get("files"), dict) and plan["files"]:
            for rel, meta in plan["files"].items():
                rel_norm = rel.replace("\\", "/")
                if not rel_norm.startswith("Data/"):
                    continue
                digest = meta["sha256"] if isinstance(meta, dict) else str(meta)
                outputs[rel_norm] = digest
        else:
            for s_name, digest in (plan.get("scripts") or {}).items():
                s_pex = s_name if s_name.lower().endswith(".pex") else f"{s_name}.pex"
                outputs[f"Data/Scripts/{s_pex}"] = digest
            if isinstance(plan.get("script"), str) and isinstance(plan.get("script_sha256"), str):
                scr = plan["script"]
                scr_pex = scr if scr.lower().endswith(".pex") else f"{scr}.pex"
                outputs[f"Data/Scripts/{scr_pex}"] = plan["script_sha256"]
    else:
        plugins = sorted(f for f in os.listdir(st) if f.lower().endswith(".esm"))
        if not plugins and os.path.isdir(os.path.join(st, "Data")):
            plugins = sorted(f for f in os.listdir(os.path.join(st, "Data")) if f.lower().endswith(".esm"))
        data_root = os.path.join(st, "Data")
        if os.path.isdir(data_root):
            for dp, _, fns in os.walk(data_root):
                for fn in sorted(fns):
                    full = os.path.join(dp, fn)
                    rel = os.path.relpath(full, st).replace("\\", "/")
                    if rel == f"Data/{fn}" and fn.lower().endswith(".esm"):
                        continue
                    outputs[rel] = sha256_file(full)

    if not plugins and comp_key != "pipboy":
        raise BundleRefused(f"component {comp_key}: no .esm plugin found in {st}")

    plugin_hashes: Dict[str, str] = {}
    for plg in plugins:
        plg_path = resolve_stage_source(st, plg)
        if not os.path.isfile(plg_path):
            raise BundleRefused(f"component {comp_key}: plugin {plg} missing in {st}")
        got_plg = sha256_file(plg_path)
        if len(plugins) == 1 and plan_plugin_sha and got_plg != plan_plugin_sha:
            raise BundleRefused(f"component {comp_key}: plugin {plg} sha256 {got_plg} != plan {plan_plugin_sha}")
        plugin_hashes[plg] = got_plg

    for rel, want in outputs.items():
        full = resolve_stage_source(st, rel)
        if not os.path.isfile(full):
            raise BundleRefused(f"component {comp_key}: staged output {rel} missing in {st}")
        got = sha256_file(full)
        if got != want:
            raise BundleRefused(f"component {comp_key}: staged {rel} sha256 {got} != plan {want}")

    merged_outputs = dict(plugin_hashes)
    merged_outputs.update(outputs)
    return plugins, merged_outputs


def install_and_rollback_commands(bundle_dir: str, starfield_dir: str, plugins: Sequence[str]) -> Tuple[str, str]:
    joined = ",".join(plugins)
    install_cmd = (
        f'python scripts/game/exp_install.py install --exp-dir "{bundle_dir}" '
        f'--starfield "{starfield_dir}" --plugins {joined} --pack'
    )
    rollback_cmd = f'python scripts/game/exp_install.py uninstall --starfield "{starfield_dir}"'
    return install_cmd, rollback_cmd


def bundle_readme(clean_core_readme: str, plugins: Sequence[str], component_keys: Sequence[str]) -> str:
    """Rewrite README.txt so there is EXACTLY ONE exp_install.py install ... --pack line and matching rollback."""
    kept_lines: List[str] = []
    for ln in clean_core_readme.splitlines():
        if "exp_install.py install" in ln:
            continue
        kept_lines.append(ln)
    install_cmd, rollback_cmd = install_and_rollback_commands("<BUNDLE_DIR>", "<STARFIELD_DIR>", plugins)
    footer = [
        "",
        f"==== FO4SF Core Candidate Bundle ({datetime.date.today().isoformat()}) ====",
        f"Components folded: {', '.join(component_keys)}",
        f"Plugins ({len(plugins)}): {', '.join(plugins)}",
        "",
        "Install (game closed — single command):",
        "  " + install_cmd,
        "Rollback (game closed — matching uninstall):",
        "  " + rollback_cmd,
    ]
    return "\n".join(kept_lines + footer) + "\n"


def estimate_general_ba2_bytes(data_dir: str, exclude_textures: bool = False) -> Tuple[int, int, int]:
    """Return (file_count, raw_payload_bytes, exact_ba2_v2_bytes) for <bundle>/Data."""
    if not os.path.isdir(data_dir):
        return 0, 0, 0
    file_count = 0
    payload_bytes = 0
    name_table_bytes = 0
    for dp, dirs, fns in os.walk(data_dir):
        dirs.sort()
        rel_dir = os.path.relpath(dp, data_dir).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        top = rel_dir.split("/", 1)[0].casefold() if rel_dir else ""
        if exclude_textures and top == "textures":
            continue
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel_archive = f"{rel_dir}/{fn}" if rel_dir else fn
            rel_bs = rel_archive.replace("/", "\\")
            sz = os.path.getsize(full)
            file_count += 1
            payload_bytes += sz
            name_table_bytes += 2 + len(rel_bs.encode("utf-8"))
    if file_count == 0:
        return 0, 0, 0
    # BA2 v2 header = 24 + 8 = 32 bytes; GNRL entry = 36 bytes/file
    ba2_bytes = 32 + (36 * file_count) + name_table_bytes + payload_bytes
    return file_count, payload_bytes, ba2_bytes


PIPBOY_INI_MOVIE_KEYS = ("Movie", "BootMovie", "SpecialMovie", "WorldMovie")


def named_pipboy_ini_movies(ini_text: str) -> List[Tuple[str, str]]:
    """Return `(ini_key, swf_filename)` for every non-empty movie named under `[FO4SFPipboyMenu]`."""
    in_main = False
    kv: Dict[str, str] = {}
    for raw in ini_text.splitlines():
        s = raw.strip()
        if not s or s.startswith(";"):
            continue
        if s.startswith("[") and s.endswith("]"):
            in_main = s[1:-1].strip() == "FO4SFPipboyMenu"
            continue
        if in_main and "=" in s:
            k, v = s.split("=", 1)
            kv[k.strip()] = v.strip()

    named: List[Tuple[str, str]] = []
    for key in PIPBOY_INI_MOVIE_KEYS:
        val = kv.get(key, "")
        if not val:
            continue
        if key == "SpecialMovie" and kv.get("SpecialMenu", "0") in ("0", ""):
            continue
        if key == "WorldMovie" and kv.get("World", "0") in ("0", ""):
            continue
        swf_name = val if val.lower().endswith(".swf") else f"{val}.swf"
        named.append((key, swf_name))
    return named


def _find_interface_swf_in_dir(iface_dir: str, swf_name: str) -> Optional[str]:
    if not os.path.isdir(iface_dir):
        return None
    exact = os.path.join(iface_dir, *swf_name.split("/"))
    if os.path.isfile(exact):
        return swf_name.replace("\\", "/")
    want_low = swf_name.replace("\\", "/").casefold()
    for dp, _, fns in os.walk(iface_dir):
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, iface_dir).replace("\\", "/")
            if rel.casefold() == want_low:
                return rel
    return None


def read_core_values_test_mode_fltv(esm_path: str) -> Tuple[Optional[float], Optional[str]]:
    """Inspect `FO4SFCoreValues.esm`'s `FO4SF_TestModeEnabled` (`0x000860`) GLOB `FLTV` float32 value."""
    target_local_id = core_form_id("FO4SF_TestModeEnabled")
    try:
        with RawEsmPlugin(esm_path) as plg:
            want_fid = (plg.self_index << 24) | (target_local_id & 0xFFFFFF)
            for rec in plg.records("GLOB"):
                if rec.formid == want_fid or rec.edid == "FO4SF_TestModeEnabled":
                    if (rec.formid & 0xFFFFFF) != target_local_id:
                        return None, f"FO4SF_TestModeEnabled local id 0x{rec.formid & 0xFFFFFF:06X} != 0x{target_local_id:06X}"
                    if rec.edid and rec.edid != "FO4SF_TestModeEnabled":
                        return None, f"GLOB 0x{target_local_id:06X} edid {rec.edid!r} != 'FO4SF_TestModeEnabled'"
                    fltv = rec.get(b"FLTV")
                    if fltv is None or len(fltv) != 4:
                        return None, f"GLOB 0x{target_local_id:06X} FO4SF_TestModeEnabled missing 4-byte FLTV"
                    val = struct.unpack("<f", fltv)[0]
                    return float(val), None
    except (OSError, EsmError) as err:
        return None, f"unreadable TES4/GLOB records ({err})"
    return None, f"missing GLOB 0x{target_local_id:06X} FO4SF_TestModeEnabled"


def verify_bundle(
    bundle_dir: str,
    plan_path: Optional[str] = None,
    port_esm: Optional[str] = None,
    max_plugins: int = MAX_STARFIELD_PLUGINS,
    max_ba2_bytes: int = MAX_BA2_BYTES,
    tool_head: Optional[str] = None,
) -> Tuple[List[str], Dict[str, object]]:
    """Verify every component hash, TES4 master chain, plugin count, Data root cleanliness, and 4 GiB BA2 ceiling."""
    bdir = os.path.abspath(bundle_dir)
    ppath = os.path.abspath(plan_path or os.path.join(bdir, "bundle_plan.json"))
    problems: List[str] = []
    if not os.path.isfile(ppath):
        return [f"bundle_plan.json missing: {ppath}"], {}

    with open(ppath, encoding="utf-8") as f:
        bplan = json.load(f)

    # H2: Refuse immediately with ONE clear line when bundle build_head differs from this checkout's git head
    effective_tool_head = current_git_head(REPO) if tool_head is None else tool_head
    recorded_head = str(bplan.get("build_head") or "").strip()
    if recorded_head and effective_tool_head and not _heads_match(recorded_head, effective_tool_head):
        b_disp = recorded_head[:8] if HEX_HEAD_RE.match(recorded_head) else recorded_head
        t_disp = effective_tool_head[:8] if HEX_HEAD_RE.match(effective_tool_head) else effective_tool_head
        return [f"this bundle was built at {b_disp}; this tool is at {t_disp}"], {
            "build_head": recorded_head,
            "tool_head": effective_tool_head,
        }
    if not recorded_head and effective_tool_head:
        unknown_comps = sorted(k for k in (bplan.get("components") or {}) if k not in ORDERED_COMPONENT_KEYS)
        if unknown_comps:
            t_disp = effective_tool_head[:8] if HEX_HEAD_RE.match(effective_tool_head) else effective_tool_head
            return [
                f"this bundle was built at <other-head ({','.join(unknown_comps)})>; this tool is at {t_disp}"
            ], {"build_head": None, "tool_head": effective_tool_head}

    plugins: List[str] = list(bplan.get("plugins") or [])
    if not plugins:
        problems.append("bundle_plan.json lists zero plugins")
    if len(plugins) > max_plugins:
        problems.append(f"plugin count {len(plugins)} exceeds limit {max_plugins}")
    if len({p.casefold() for p in plugins}) != len(plugins):
        problems.append(f"duplicate plugins in bundle order: {plugins}")

    # 1. Verify README.txt has exactly ONE exp_install.py install ... --pack line naming the exact plugin list
    readme_p = os.path.join(bdir, "README.txt")
    if not os.path.isfile(readme_p):
        problems.append("README.txt missing in bundle")
    else:
        readme_txt = Path(readme_p).read_text(encoding="utf-8")
        install_matches = list(INSTALL_LINE_RE.finditer(readme_txt))
        if len(install_matches) != 1:
            problems.append(f"README.txt must contain exactly 1 exp_install.py install line, found {len(install_matches)}")
        else:
            readme_plugins = install_matches[0].group("plugins").split(",")
            if readme_plugins != plugins:
                problems.append(f"README.txt --plugins {readme_plugins} != bundle_plan plugins {plugins}")

    # 1b. Enforce safe W1 defaults: FO4SFBridge.esm OFF everywhere, FO4SFRouteLoot.esm OFF unless --with-route-loot,
    # and Track 2 experimental core slices OFF in player profile unless --with-experimental-core
    if any(p.casefold() == "fo4sfbridge.esm" for p in plugins):
        problems.append("bundle must not include held FO4SFBridge.esm")
    if bplan.get("profile") == "player" and any(p.casefold() == "fo4sfcorecandidate.esm" for p in plugins):
        problems.append("player profile must not include FO4SFCoreCandidate.esm")
    if not bplan.get("with_route_loot", False) and any(p.casefold() == "fo4sfrouteloot.esm" for p in plugins):
        problems.append("bundle must not include FO4SFRouteLoot.esm unless --with-route-loot is set (T1)")
    if (
        bplan.get("profile") == "player"
        and not bplan.get("with_experimental_core", False)
        and any(p.casefold() in EXPERIMENTAL_CORE_ESMS for p in plugins)
    ):
        problems.append("player profile must not include Track 2 experimental core plugins unless --with-experimental-core is set")

    # 2. Verify every recorded file SHA-256 across all folded components & sidecar
    for comp, cinfo in (bplan.get("components") or {}).items():
        for rel, want in (cinfo.get("outputs") or {}).items():
            full = os.path.join(bdir, *rel.split("/"))
            if not os.path.isfile(full):
                problems.append(f"{comp}: missing {rel}")
            else:
                got = sha256_file(full)
                if got != want:
                    problems.append(f"{comp}: {rel} sha256 {got} != expected {want}")

    for rel, want in (bplan.get("sfse_sidecar") or {}).items():
        full = os.path.join(bdir, "sfse_sidecar", *rel.split("/"))
        if not os.path.isfile(full):
            problems.append(f"sfse_sidecar: missing {rel}")
        elif sha256_file(full) != want:
            problems.append(f"sfse_sidecar: {rel} sha256 mismatch")

    # 3. Verify TES4 header & master chain order for every plugin in bundle
    seen_before: set[str] = {"fo4port.esm"}  # FO4Port.esm is deployed in game Data alongside the experiment
    if port_esm and not os.path.isfile(port_esm):
        problems.append(f"--port plugin not found: {port_esm}")

    for plg in plugins:
        plg_path = os.path.join(bdir, plg)
        if not os.path.isfile(plg_path):
            problems.append(f"plugin missing at bundle root: {plg}")
            continue
        try:
            masters = exp_install.plugin_masters(plg_path)
        except ValueError as err:
            problems.append(f"{plg}: invalid TES4 header ({err})")
            continue
        for m in masters:
            m_low = m.casefold()
            if not exp_install.implicit(m) and m_low not in seen_before:
                problems.append(f"{plg}: master {m} is neither implicit nor loaded before {plg}")
        seen_before.add(plg.casefold())

    # 3b (A16). Explicit refusal when FO4SFNewGame.esm masters FO4SFCoreValues.esm and the store plugin is absent or ordered after it
    ng_esm_path = os.path.join(bdir, "FO4SFNewGame.esm")
    p_low = [p.casefold() for p in plugins]
    if "fo4sfnewgame.esm" in p_low or os.path.isfile(ng_esm_path):
        if os.path.isfile(ng_esm_path):
            try:
                ng_masters_low = [m.casefold() for m in exp_install.plugin_masters(ng_esm_path)]
            except ValueError:
                ng_masters_low = []
            if "fo4sfcorevalues.esm" in ng_masters_low:
                cv_esm_path = os.path.join(bdir, "FO4SFCoreValues.esm")
                if "fo4sfcorevalues.esm" not in p_low or not os.path.isfile(cv_esm_path):
                    problems.append("FO4SFNewGame.esm masters FO4SFCoreValues.esm, but bundle lacks FO4SFCoreValues.esm")
                elif "fo4sfnewgame.esm" in p_low and p_low.index("fo4sfnewgame.esm") < p_low.index("fo4sfcorevalues.esm"):
                    problems.append("FO4SFNewGame.esm is ordered before its required master FO4SFCoreValues.esm in Plugins.txt")

    # 3c (A5). Inspect FO4SFCoreValues.esm FO4SF_TestModeEnabled (0x000860) FLTV against bundle profile
    cv_bundle_path = os.path.join(bdir, "FO4SFCoreValues.esm")
    bundle_profile = bplan.get("profile")
    if "fo4sfcorevalues.esm" in p_low and os.path.isfile(cv_bundle_path) and bundle_profile in ("player", "test"):
        tm_val, tm_err = read_core_values_test_mode_fltv(cv_bundle_path)
        if tm_err is not None or tm_val is None:
            problems.append(f"FO4SFCoreValues.esm: {tm_err}")
        elif bundle_profile == "test" and abs(tm_val - 1.0) > 1e-4:
            problems.append(
                f"FO4SFCoreValues.esm: --profile test requires FO4SF_TestModeEnabled (0x000860) FLTV=1.0, found {tm_val}"
            )
        elif bundle_profile == "player" and abs(tm_val - 0.0) > 1e-4:
            problems.append(
                f"FO4SFCoreValues.esm: --profile player requires FO4SF_TestModeEnabled (0x000860) FLTV=0.0, found {tm_val}"
            )

    # 3d (A15 + R13). Binary .esm duplicate-EditorID / cross-plugin check and native C++ shared-value table check
    base_skip_binary = {"fo4actorraider.esm", "fo4terraincore.esm", "fo4terraincore_mars.esm"}
    esm_paths_to_inspect: List[str] = []
    seen_esm_paths: set[str] = set()
    for plg in plugins:
        if plg.casefold() in base_skip_binary:
            continue
        cand_p = os.path.join(bdir, plg)
        if os.path.isfile(cand_p):
            esm_paths_to_inspect.append(cand_p)
            seen_esm_paths.add(os.path.normcase(os.path.abspath(cand_p)))
    if os.path.isdir(bdir):
        for fn in sorted(os.listdir(bdir)):
            if fn.lower().endswith(".esm") and fn.casefold() not in base_skip_binary:
                cand_p = os.path.join(bdir, fn)
                norm_p = os.path.normcase(os.path.abspath(cand_p))
                if os.path.isfile(cand_p) and norm_p not in seen_esm_paths:
                    esm_paths_to_inspect.append(cand_p)
                    seen_esm_paths.add(norm_p)
    try:
        catalog, dup_errs = cross_plugin_check.build_writer_catalog(REPO)
        for de in dup_errs:
            problems.append(f"cross_plugin_check: {de}")
        psc_props = cross_plugin_check.collect_psc_props_by_script(REPO)
        if esm_paths_to_inspect:
            bin_errs = cross_plugin_check.validate_staged_esms(esm_paths_to_inspect, catalog, psc_props)
            for be in bin_errs:
                problems.append(f"binary esm check: {be}")
        for ne in cross_plugin_check.validate_native_core_value_refs(REPO, catalog):
            problems.append(f"native core value check: {ne}")
    except Exception as exc:
        problems.append(f"binary esm check failed: {exc}")

    # 3e (A1). Verify every movie named in shipped FO4SFPipboyMenu.ini exists in Data/Interface/ and in bundle manifest
    pb_ini_candidates = (
        os.path.join(bdir, "sfse_sidecar", "SFSE", "Plugins", "FO4SFPipboyMenu.ini"),
        os.path.join(bdir, "sfse_sidecar", "FO4SFPipboyMenu.ini"),
    )
    pb_comp_outputs = ((bplan.get("components") or {}).get("pipboy") or {}).get("outputs") or {}
    pb_manifest_low = {k.replace("\\", "/").casefold() for k in pb_comp_outputs}
    iface_bundle_dir = os.path.join(bdir, "Data", "Interface")
    for pb_ini_p in pb_ini_candidates:
        if not os.path.isfile(pb_ini_p):
            continue
        ini_txt = Path(pb_ini_p).read_text(encoding="utf-8")
        for ini_key, swf_name in named_pipboy_ini_movies(ini_txt):
            matched_rel = _find_interface_swf_in_dir(iface_bundle_dir, swf_name)
            if matched_rel is None:
                problems.append(
                    f"pipboy: FO4SFPipboyMenu.ini {ini_key} names {swf_name}, which is absent from Data/Interface/"
                )
            elif f"data/interface/{matched_rel.casefold()}" not in pb_manifest_low:
                problems.append(
                    f"pipboy: Data/Interface/{matched_rel} (named by {ini_key}) is missing from bundle_plan.json manifest"
                )
        break

    # 4. Run make_newgame.verify_dir when real newgame plan is bundled
    ng_plan = bplan.get("newgame_plan")
    if isinstance(ng_plan, dict) and "checked_against_sha256" in ng_plan:
        effective_port = port_esm or bplan.get("port_esm_checked")
        core_path = os.path.join(bdir, "FO4TerrainCore.esm")
        if effective_port and os.path.isfile(effective_port) and os.path.isfile(core_path):
            ng_probs = make_newgame.verify_dir(bdir, ng_plan, effective_port, core_path)
            for p in ng_probs:
                problems.append(f"newgame verify: {p}")

    # 5. Check Data/ root has no loose root files (exp_install.py --pack refuses root-level Data files)
    data_dir = os.path.join(bdir, "Data")
    if os.path.isdir(data_dir):
        root_files = sorted(n for n in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, n)))
        if root_files:
            problems.append(f"Data/ contains root-level files refused by exp_install --pack: {root_files}")

    # 6. Check 4 GiB BA2 archive limit (existing .ba2 files + packed Main.ba2 size estimate)
    for dp, _, fns in os.walk(bdir):
        for fn in sorted(fns):
            if fn.lower().endswith(".ba2"):
                fp = os.path.join(dp, fn)
                sz = os.path.getsize(fp)
                if sz > max_ba2_bytes:
                    problems.append(f"archive {fn} is {sz} bytes, exceeding 4 GiB limit ({max_ba2_bytes})")

    n_files, raw_bytes, est_ba2_bytes = estimate_general_ba2_bytes(data_dir)
    if est_ba2_bytes > max_ba2_bytes:
        problems.append(
            f"packed Main.ba2 estimate is {est_ba2_bytes:,} bytes ({est_ba2_bytes / (1024**3):.3f} GiB) "
            f"across {n_files:,} Data/ files, exceeding 4 GiB limit ({max_ba2_bytes:,} bytes)"
        )

    metrics = {
        "plugin_count": len(plugins),
        "plugins": plugins,
        "data_file_count": n_files,
        "data_raw_bytes": raw_bytes,
        "estimated_main_ba2_bytes": est_ba2_bytes,
        "max_ba2_bytes": max_ba2_bytes,
    }
    return problems, metrics


def stage_candidate_walk(out_dir: str, starfield_esm: str, compiler: str, content_resources: str) -> str:
    """Build FO4SFCoreCandidate.esm and compile FO4SF_CoreCandidateWalk.pex."""
    os.makedirs(out_dir, exist_ok=True)
    proj = os.path.join(REPO, "dotnet", "CoreCandidate")
    r_build = subprocess.run(["dotnet", "run", "--project", proj, "--", "build", starfield_esm, out_dir],
                             capture_output=True, text=True)
    if r_build.returncode != 0:
        raise BundleRefused(f"CoreCandidate build failed: {r_build.stderr or r_build.stdout}")
    esm_path = os.path.join(out_dir, "FO4SFCoreCandidate.esm")
    r_chk = subprocess.run(["dotnet", "run", "--project", proj, "--", "check", esm_path, starfield_esm],
                           capture_output=True, text=True)
    if r_chk.returncode != 0:
        raise BundleRefused(f"CoreCandidate check failed: {r_chk.stderr or r_chk.stdout}")

    psc_path = os.path.join(REPO, "scripts", "core", "FO4SF_CoreCandidateWalk.psc")
    with open(psc_path, encoding="utf-8") as f:
        psc_txt = f.read()
    scripts_out = os.path.join(out_dir, "Data", "Scripts")
    with tempfile.TemporaryDirectory(prefix="fo4sf-cand-src-") as td:
        src_dir = make_newgame.extract_sources(content_resources, td)
        prog_psc = os.path.join(REPO, "scripts", "progression", "FO4SF_ProgressionQuest.psc")
        if os.path.isfile(prog_psc):
            shutil.copy2(prog_psc, os.path.join(src_dir, "FO4SF_ProgressionQuest.psc"))
        ok, err = compile_text(compiler, psc_txt, src_dir, scripts_out, script="FO4SF_CoreCandidateWalk")
        if not ok:
            raise BundleRefused(f"FO4SF_CoreCandidateWalk.psc compile failed: {err}")

    pex_path = os.path.join(scripts_out, "FO4SF_CoreCandidateWalk.pex")
    plan = {
        "kind": "core-candidate-walk",
        "version": 1,
        "plugin": "FO4SFCoreCandidate.esm",
        "plugins": ["FO4SFCoreCandidate.esm"],
        "outputs": {
            "FO4SFCoreCandidate.esm": sha256_file(esm_path),
            "Data/Scripts/FO4SF_CoreCandidateWalk.pex": sha256_file(pex_path),
        },
    }
    with open(os.path.join(out_dir, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    return out_dir


def build_sfse_dll_from_source(plugin_name: str, out_dir: str, commonlibsf: str, msvc_env: str) -> str:
    """Compile an SFSE plugin from C++ source via build.ps1 into a fresh non-deleted folder."""
    script_ps1 = os.path.join(REPO, "sfse", plugin_name, "build.ps1")
    if not os.path.isfile(script_ps1):
        raise BundleRefused(f"missing SFSE build script: {script_ps1}")
    dll_path = os.path.join(out_dir, f"{plugin_name}.dll")
    if os.path.isfile(dll_path):
        return out_dir
    cmd = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", script_ps1,
        "-Out", os.path.abspath(out_dir),
        "-Lib", os.path.abspath(commonlibsf),
        "-Env", os.path.abspath(msvc_env),
    ]
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd)
    if proc.returncode != 0 or not os.path.isfile(dll_path):
        raise BundleRefused(f"SFSE source build failed for {plugin_name} (exit {proc.returncode})")
    return os.path.abspath(out_dir)


def validate_pipboy_stage(stage_dir: str, has_override_dll: bool = False) -> None:
    """Refuse --with-pipboy when --pipboy-stage holds no Pip-Boy .esm or .dll (T9/Q13)."""
    st = os.path.abspath(stage_dir)
    if not os.path.isdir(st):
        raise BundleRefused(f"--with-pipboy: --pipboy-stage directory not found: {st}")
    comp_plugins, _ = extract_component_outputs("pipboy", st)
    pb_esms = [p for p in comp_plugins if "pipboy" in p.lower() and p.lower().endswith(".esm")]
    if not pb_esms:
        raise BundleRefused(f"--with-pipboy refused: {st} holds no FO4SFPipboy*.esm plugin (check --pipboy-stage path)")
    dll_candidates = (
        os.path.join(st, "SFSE", "Plugins", "FO4SFPipboyMenu.dll"),
        os.path.join(st, "sfse", "FO4SFPipboyMenu.dll"),
        os.path.join(st, "FO4SFPipboyMenu.dll"),
    )
    if not has_override_dll and not any(os.path.isfile(c) for c in dll_candidates):
        raise BundleRefused(f"--with-pipboy refused: {st} holds no FO4SFPipboyMenu.dll (and no source build provided)")


def _run_py(py_exe: str, script_rel: str, args: Sequence[str]) -> None:
    cmd = [py_exe, os.path.join(REPO, *script_rel.split("/")), *args]
    print("+ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise BundleRefused(f"{script_rel} exited {r.returncode}")


def stage_from_checkout(a) -> Dict[str, str]:
    """Run every component's stager from this single checkout into <a.work>."""
    game_roots = (getattr(a, "starfield_dir", None), getattr(a, "fo4_data", None))
    refuse_unsafe_output_dir(a.work, label="--work", game_dirs=game_roots)
    if getattr(a, "out", None):
        refuse_unsafe_output_dir(a.out, label="--out", game_dirs=game_roots)
    if getattr(a, "clean_core_out", None):
        refuse_unsafe_output_dir(a.clean_core_out, label="--clean-core-out", game_dirs=game_roots)
    work = os.path.abspath(a.work)
    os.makedirs(work, exist_ok=True)

    py_main = sys.executable
    py_render = a.render_python or py_main
    sf_dir = os.path.abspath(a.starfield_dir)
    sf_data = os.path.join(sf_dir, "Data")
    sf_esm = os.path.join(sf_data, "Starfield.esm")
    compiler = os.path.join(sf_dir, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe")
    cr_zip = os.path.join(sf_dir, "Tools", "ContentResources.zip")
    port_esm = os.path.abspath(a.port)
    port_dir = os.path.dirname(port_esm)
    core_esm = os.path.join(os.path.abspath(a.owner_set), "FO4TerrainCore.esm")
    raider_esm = os.path.join(os.path.abspath(a.owner_set), "FO4ActorRaider.esm")
    profile = getattr(a, "profile", "player")
    commonlibsf = getattr(a, "commonlibsf", None)
    msvc_env = getattr(a, "msvc_env", None)

    stages: Dict[str, str] = {}

    want_test_mode = "1" if profile == "test" else "0"
    cv_folder = "00-core-values-test" if profile == "test" else "00-core-values-player"
    cv_dir = os.path.join(work, cv_folder)
    if not os.path.exists(cv_dir):
        _run_py(py_main, "scripts/core/make_core_values.py", [
            "stage",
            "--sf-data", sf_data,
            "--out", cv_dir,
            "--test-mode", want_test_mode,
        ])
    stages["core_values"] = cv_dir

    cog_dir = os.path.join(work, "01-cog-door")
    if not os.path.exists(cog_dir):
        _run_py(py_render, "scripts/newgame/make_cog_door.py", [
            "stage", "--production-cog",
            "--out", cog_dir,
            "--starfield-data", sf_data,
            "--port-data", port_dir,
            "--fo4-data", os.path.abspath(a.fo4_data),
            "--door-anim-dll", os.path.abspath(a.door_anim_dll),
            "--collision-template", os.path.abspath(a.collision_template),
            "--texconv", os.path.abspath(a.texconv),
            "--content-resources", cr_zip,
        ])
    stages["cog_door"] = cog_dir

    lift_dir = os.path.join(work, "02-exit-lift")
    if not os.path.exists(lift_dir):
        _run_py(py_render, "scripts/newgame/make_anim_console.py", [
            "stage", "--production-lift",
            "--edid", "FO4Port_acti_0244ef_fallout4",
            "--states", "stage3=StateA_Play,stage2=StateB_Play",
            "--idles", "toggle",
            "--rest-after", "stage2",
            "--out", lift_dir,
            "--starfield-data", sf_data,
            "--port-data", port_dir,
            "--fo4-data", os.path.abspath(a.fo4_data),
            "--door-anim-dll", os.path.abspath(a.door_anim_dll),
            "--collision-template", os.path.abspath(a.collision_template),
            "--texconv", os.path.abspath(a.texconv),
            "--content-resources", cr_zip,
        ])
    stages["exit_lift"] = lift_dir

    if getattr(a, "mission_stage", None):
        ms_override = os.path.abspath(a.mission_stage)
        if not os.path.isdir(ms_override):
            raise BundleRefused(f"--mission-stage directory not found: {ms_override}")
        stages["mission"] = ms_override
    elif not getattr(a, "no_mission", False) and os.path.isfile(raider_esm):
        mission_dir = os.path.join(work, "02b-mission")
        if not os.path.exists(mission_dir):
            fo4_data_abs = os.path.abspath(a.fo4_data)
            ms_args = [
                "stage",
                "--out", mission_dir,
                "--fo4", os.path.join(fo4_data_abs, "Fallout4.esm"),
                "--starfield", sf_esm,
                "--core", core_esm,
                "--raider", raider_esm,
                "--compiler", compiler,
                "--content-resources", cr_zip,
            ]
            fo4_iface = os.path.join(fo4_data_abs, "Fallout4 - Interface.ba2")
            fo4_voices = os.path.join(fo4_data_abs, "Fallout4 - Voices.ba2")
            if os.path.isfile(fo4_iface):
                ms_args.extend(["--fo4-interface", fo4_iface])
            if os.path.isfile(fo4_voices):
                ms_args.extend(["--fo4-voices", fo4_voices])
            _run_py(py_main, "scripts/mission/make_mission.py", ms_args)
        stages["mission"] = mission_dir

    want_fade_hold = (
        not getattr(a, "no_fade_hold", False)
        and (profile == "test" or bool(getattr(a, "fade_hold", False)))
    )
    ng_folder = "03-newgame-fadehold" if want_fade_hold else "03-newgame"
    ng_dir = os.path.join(work, ng_folder)
    if not os.path.exists(ng_dir):
        ng_args = [
            "stage",
            "--out", ng_dir,
            "--cog-door", cog_dir,
            "--exit-lift", lift_dir,
            "--fo4", os.path.join(os.path.abspath(a.fo4_data), "Fallout4.esm"),
            "--port", port_esm,
            "--port-ids", os.path.abspath(a.port_ids),
            "--core", core_esm,
            "--starfield", sf_esm,
            "--compiler", compiler,
            "--content-resources", cr_zip,
        ]
        if want_fade_hold:
            ng_args.append("--fade-hold")
        if getattr(a, "show_unavailable_starts", None) is not None:
            ng_args.extend(["--show-unavailable-starts", str(int(a.show_unavailable_starts))])
        _run_py(py_main, "scripts/newgame/make_newgame.py", ng_args)
    # Verify hold 199, pod_step -2.5, and fade_hold policy in staged NewGame plan
    with open(os.path.join(ng_dir, "plan.json"), encoding="utf-8") as f:
        ng_plan = json.load(f)
    hold_cnt = len(ng_plan["options"]["hold"].split(","))
    pod_step = float(ng_plan["points"]["pod"]["step_m"])
    if hold_cnt != 199:
        raise BundleRefused(f"NewGame hold count is {hold_cnt}, expected 199")
    if abs(pod_step - (-2.5)) > 1e-4:
        raise BundleRefused(f"NewGame pod_step is {pod_step}, expected -2.5")
    if bool(ng_plan["options"].get("fade_hold", False)) != want_fade_hold:
        raise BundleRefused(f"NewGame fade_hold is {ng_plan['options'].get('fade_hold')}, expected {want_fade_hold}")
    stages["newgame"] = ng_dir

    include_experimental_core = profile == "test" or bool(getattr(a, "with_experimental_core", False))
    slice_specs = [
        ("rads", "04-rads", "scripts/rads/make_rads_core.py"),
        ("hardcore", "05-hardcore", "scripts/survival/make_hardcore.py"),
        ("workshop", "06-workshop", "scripts/workshop/make_workshop_core.py"),
        ("powerarmor", "07-powerarmor", "scripts/powerarmor/make_power_armor_core.py"),
        ("progression", "08-progression", "scripts/progression/make_progression.py"),
        ("list_dialogue", "09-list-dialogue", "scripts/dialogue/make_list_dialogue.py"),
        ("reputation", "11-reputation", "scripts/reputation/make_reputation_core.py"),
        ("companions", "12-companions", "scripts/companions/make_companions_core.py"),
    ]
    for key, folder, rel_script in slice_specs:
        if key in EXPERIMENTAL_CORE_COMPONENT_KEYS and not include_experimental_core:
            continue
        suffix = "-player" if (profile == "player" and key in TEST_CELL_SLICE_KEYS) else ""
        sdir = os.path.join(work, folder + suffix)
        if not os.path.exists(sdir):
            st_args = [
                "stage",
                "--out", sdir,
                "--starfield", sf_esm,
                "--compiler", compiler,
                "--content-resources", cr_zip,
            ]
            if profile == "player" and key in TEST_CELL_SLICE_KEYS:
                st_args.append("--no-test-cell")
            _run_py(py_main, rel_script, st_args)
        stages[key] = sdir

    if include_experimental_core:
        combat_sfse_dir = getattr(a, "combat_sfse_build", None)
        if not combat_sfse_dir and commonlibsf and msvc_env:
            combat_sfse_dir = build_sfse_dll_from_source(
                "FO4SFCombat",
                os.path.join(work, "sfse-src-builds", "combat"),
                commonlibsf,
                msvc_env,
            )

        combat_folder = "10-combat-player" if profile == "player" else "10-combat"
        combat_dir = os.path.join(work, combat_folder)
        if not os.path.exists(combat_dir):
            combat_args = ["stage", "--out", combat_dir, "--starfield-dir", sf_dir]
            if profile == "player":
                combat_args.append("--no-test-cell")
            if combat_sfse_dir:
                combat_args.extend(["--sfse-build", os.path.abspath(combat_sfse_dir)])
            _run_py(py_main, "scripts/combat/make_combat_core.py", combat_args)
        stages["combat"] = combat_dir

        alife_script = os.path.join(REPO, "scripts", "alife", "make_alife.py")
        if not getattr(a, "no_alife", False) and os.path.isfile(alife_script) and os.path.isfile(raider_esm):
            alife_dir = os.path.join(work, "13-alife")
            if not os.path.exists(alife_dir):
                _run_py(py_main, "scripts/alife/make_alife.py", [
                    "stage",
                    "--out", alife_dir,
                    "--starfield", sf_esm,
                    "--core", core_esm,
                    "--raider", raider_esm,
                    "--compiler", compiler,
                    "--content-resources", cr_zip,
                ])
            stages["alife"] = alife_dir

    include_route_loot = (
        not getattr(a, "no_route_loot", False)
        and bool(getattr(a, "with_route_loot", False))
    )
    if include_route_loot and getattr(a, "route_loot_stage", None):
        rl_override = os.path.abspath(a.route_loot_stage)
        if not os.path.isdir(rl_override):
            raise BundleRefused(f"--route-loot-stage directory not found: {rl_override}")
        stages["route_loot"] = rl_override
    elif include_route_loot:
        rl_script = os.path.join(REPO, "scripts", "loot", "make_route_loot.py")
        if os.path.isfile(rl_script):
            rl_dir = os.path.join(work, "17-route-loot")
            if not os.path.exists(rl_dir):
                _run_py(py_main, "scripts/loot/make_route_loot.py", [
                    "stage",
                    "--out", rl_dir,
                    "--starfield", sf_esm,
                    "--core", core_esm,
                    "--port", port_esm,
                ])
            stages["route_loot"] = rl_dir

    fh_script = os.path.join(REPO, "scripts", "fort_hagen", "make_fort_hagen.py")
    if not getattr(a, "no_fort_hagen", False) and os.path.isfile(fh_script):
        fh_dir = os.path.join(work, "14-fort-hagen")
        if not os.path.exists(fh_dir):
            _run_py(py_main, "scripts/fort_hagen/make_fort_hagen.py", [
                "stage",
                "--out", fh_dir,
                "--starfield", sf_esm,
                "--port", port_esm,
                "--core", core_esm,
                "--compiler", compiler,
                "--content-resources", cr_zip,
            ])
        stages["fort_hagen"] = fh_dir

    if profile == "test" and not getattr(a, "no_walk_harness", False):
        cw_dir = os.path.join(work, "15-candidate-walk")
        if not os.path.exists(cw_dir):
            stage_candidate_walk(cw_dir, sf_esm, compiler, cr_zip)
        stages["candidate_walk"] = cw_dir

    if getattr(a, "with_pipboy", False):
        if not getattr(a, "pipboy_stage", None):
            raise BundleRefused("--with-pipboy requires --pipboy-stage <dir>")
        pb_override = getattr(a, "pipboy_sfse_build", None)
        has_src_pb = bool(pb_override or (commonlibsf and msvc_env))
        validate_pipboy_stage(a.pipboy_stage, has_override_dll=has_src_pb)
        pb_refreshed = os.path.join(work, "16-pipboy-refreshed")
        if not os.path.exists(pb_refreshed):
            resolved_show_unavail = resolve_setup_show_unavailable(
                getattr(a, "show_unavailable_starts", None),
                ng_plan,
            )
            refresh_pipboy_stage_for_bundle(
                os.path.abspath(a.pipboy_stage),
                pb_refreshed,
                os.path.abspath(a.fo4_data),
                setup_show_unavailable=resolved_show_unavail or 0,
            )
        stages["pipboy"] = pb_refreshed
        if pb_override:
            a._pipboy_sfse_override = os.path.abspath(pb_override)
        elif commonlibsf and msvc_env:
            pb_src_dir = build_sfse_dll_from_source(
                "FO4SFPipboyMenu",
                os.path.join(work, "sfse-src-builds", "pipboy"),
                commonlibsf,
                msvc_env,
            )
            a._pipboy_sfse_override = pb_src_dir

    return stages


def refresh_pipboy_stage_for_bundle(
    src_stage: str,
    out_stage: str,
    fo4_data_dir: str,
    *,
    setup_show_unavailable: int = 0,
) -> None:
    """Copy a Pip-Boy stage into <out_stage>, re-patch Pipboy_MapPage.swf, stage STAT/boot/Setup SWFs, generate clean INI, and update plan.json."""
    ui_dir = os.path.join(REPO, "scripts", "ui")
    if ui_dir not in sys.path:
        sys.path.insert(0, ui_dir)
    import make_pipboy_stage_ini  # type: ignore
    import make_probe_swf  # type: ignore
    import pipboy_map_store  # type: ignore

    try:
        pipboy_map_store.refuse_unsafe_output_path(out_stage)
    except pipboy_map_store.MapStoreError as exc:
        raise BundleRefused(str(exc)) from exc

    partial = out_stage + ".partial"
    if os.path.exists(partial):
        shutil.rmtree(partial)
    shutil.copytree(src_stage, partial)

    iface_dir = os.path.join(partial, "Data", "Interface")
    os.makedirs(iface_dir, exist_ok=True)
    updated_data_rels: List[str] = []

    mappage_p = os.path.join(iface_dir, "Pipboy_MapPage.swf")
    if os.path.isfile(mappage_p):
        with open(mappage_p, "rb") as f:
            raw_mp = f.read()
        patched_mp, _ = pipboy_map_store.patch_map_page_swf(raw_mp)
        with open(mappage_p, "wb") as f:
            f.write(patched_mp)
        updated_data_rels.append("Data/Interface/Pipboy_MapPage.swf")

    fo4_iface_ba2 = os.path.join(fo4_data_dir, "Fallout4 - Interface.ba2")
    if os.path.isfile(fo4_iface_ba2):
        staged_specs = pipboy_map_store.stage_fo4_stat_components(fo4_iface_ba2, iface_dir)
        for spec in staged_specs:
            updated_data_rels.append(f"Data/Interface/{spec}.swf")
        boot_spec = pipboy_map_store.stage_fo4_boot_movie(fo4_iface_ba2, iface_dir)
        updated_data_rels.append(f"Data/Interface/{boot_spec}.swf")

    if any(p.lower().endswith(".swf") for _, _, fns in os.walk(iface_dir) for p in fns):
        try:
            make_pipboy_stage_ini.generate_stage_ini(
                partial,
                setup_show_unavailable=setup_show_unavailable,
            )
        except make_pipboy_stage_ini.StageIniError as exc:
            raise BundleRefused(str(exc)) from exc
        updated_data_rels.append("SFSE/Plugins/FO4SFPipboyMenu.ini")

    for aux_name, aux_kw in (
        ("FO4SF_StartCard.swf", {"start_card": True}),
        ("FO4SF_SetupScreen.swf", {"setup_screen": True}),
    ):
        aux_p = os.path.join(iface_dir, aux_name)
        if not os.path.isfile(aux_p):
            make_probe_swf.write_movie(aux_p, **aux_kw)
        rel_aux = f"Data/Interface/{aux_name}"
        if rel_aux not in updated_data_rels:
            updated_data_rels.append(rel_aux)

    start_places_src = os.path.join(REPO, "src", "fo4sf", "core", "start_places.json")
    if os.path.isfile(start_places_src):
        sfse_plugins_dst = os.path.join(partial, "SFSE", "Plugins")
        os.makedirs(sfse_plugins_dst, exist_ok=True)
        shutil.copy2(start_places_src, os.path.join(sfse_plugins_dst, "FO4SFStartPlaces.json"))
        updated_data_rels.append("SFSE/Plugins/FO4SFStartPlaces.json")
    warfare_starts_src = os.path.join(REPO, "src", "fo4sf", "core", "warfare_starts.json")
    if os.path.isfile(warfare_starts_src):
        sfse_plugins_dst = os.path.join(partial, "SFSE", "Plugins")
        os.makedirs(sfse_plugins_dst, exist_ok=True)
        shutil.copy2(warfare_starts_src, os.path.join(sfse_plugins_dst, "FO4SFWarfareStarts.json"))
        updated_data_rels.append("SFSE/Plugins/FO4SFWarfareStarts.json")

    stage_ini_p = os.path.join(partial, "SFSE", "Plugins", "FO4SFPipboyMenu.ini")
    if os.path.isfile(stage_ini_p):
        for _ini_k, swf_nm in named_pipboy_ini_movies(Path(stage_ini_p).read_text(encoding="utf-8")):
            matched_swf = _find_interface_swf_in_dir(iface_dir, swf_nm)
            if matched_swf is not None:
                rel_swf = f"Data/Interface/{matched_swf}"
                if rel_swf not in updated_data_rels:
                    updated_data_rels.append(rel_swf)

    plan_p = os.path.join(partial, "plan.json")
    if os.path.isfile(plan_p) and updated_data_rels:
        with open(plan_p, encoding="utf-8") as f:
            plan = json.load(f)
        if isinstance(plan.get("outputs"), dict) and plan["outputs"]:
            for rel in updated_data_rels:
                full = os.path.join(partial, *rel.split("/"))
                if rel.startswith("Data/") and os.path.isfile(full):
                    plan["outputs"][rel] = sha256_file(full)
        elif isinstance(plan.get("files"), dict) and plan["files"]:
            for rel in updated_data_rels:
                full = os.path.join(partial, *rel.split("/"))
                if os.path.isfile(full):
                    existing = plan["files"].get(rel)
                    digest = sha256_file(full)
                    plan["files"][rel] = {"sha256": digest, "bytes": os.path.getsize(full)} if isinstance(existing, dict) or existing is None else digest
        with open(plan_p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(plan, f, indent=2)
            f.write("\n")

    os.replace(partial, out_stage)


def strip_pipboy_kit_sections(ini_text: str) -> str:
    """Strip legacy Stage=5 [Kit] and [Page ...] sections from shipped FO4SFPipboyMenu.ini (G5)."""
    heading_val: Optional[str] = None
    has_map_heading = False
    for raw in ini_text.splitlines():
        s = raw.strip()
        if s.startswith("MapHeadingAt="):
            val = s.split("=", 1)[1].strip()
            if val:
                has_map_heading = True
        elif s.startswith("HeadingAt=") and heading_val is None:
            val = s.split("=", 1)[1].strip()
            if val:
                heading_val = val

    out_lines: List[str] = []
    skip_section = False
    in_main_section = False
    injected_heading = False
    for line in ini_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_main_section and not has_map_heading and heading_val and not injected_heading:
                out_lines.append(f"MapHeadingAt={heading_val}")
                injected_heading = True
            sec = stripped[1:-1].strip()
            in_main_section = sec == "FO4SFPipboyMenu"
            skip_section = sec == "Kit" or sec.startswith("Page ")
            if skip_section:
                continue
        if skip_section:
            continue
        out_lines.append(line)
    if in_main_section and not has_map_heading and heading_val and not injected_heading:
        out_lines.append(f"MapHeadingAt={heading_val}")
    return "\n".join(out_lines).rstrip() + "\n"


def resolve_setup_show_unavailable(
    cli_value: Optional[int],
    ng_plan: Optional[dict],
) -> Optional[int]:
    """Resolve `SetupShowUnavailable` (`0|1`) from `--show-unavailable-starts` or `03-newgame/plan.json`."""
    if cli_value is not None:
        return 1 if int(cli_value) else 0
    if isinstance(ng_plan, dict):
        opts = ng_plan.get("options")
        if isinstance(opts, dict) and "show_unavailable_starts" in opts:
            return 1 if bool(opts["show_unavailable_starts"]) else 0
        if "show_unavailable_starts" in ng_plan:
            return 1 if bool(ng_plan["show_unavailable_starts"]) else 0
    return None


def set_pipboy_ini_setup_show_unavailable(ini_text: str, setup_show_unavailable: int) -> str:
    """Update or insert `SetupShowUnavailable=<0|1>` inside `[FO4SFPipboyMenu]`."""
    val_line = f"SetupShowUnavailable={1 if setup_show_unavailable else 0}"
    out_lines: List[str] = []
    in_main = False
    replaced = False
    saw_main = False
    for line in ini_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_main and not replaced:
                out_lines.append(val_line)
                replaced = True
            sec = stripped[1:-1].strip()
            in_main = sec == "FO4SFPipboyMenu"
            if in_main:
                saw_main = True
            out_lines.append(line)
            continue
        if in_main and "=" in stripped and stripped.split("=", 1)[0].strip().lower() == "setupshowunavailable":
            if not replaced:
                out_lines.append(val_line)
                replaced = True
            continue
        out_lines.append(line)
    if in_main and not replaced:
        out_lines.append(val_line)
        replaced = True
    elif not saw_main and not replaced:
        out_lines.extend(["[FO4SFPipboyMenu]", val_line])
    return "\n".join(out_lines).rstrip() + "\n"


def _copy_or_strip_pipboy_ini(
    src_path: str,
    dst_path: str,
    *,
    setup_show_unavailable: Optional[int] = None,
) -> None:
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    if os.path.basename(dst_path).lower().endswith(".ini") and "pipboymenu" in os.path.basename(dst_path).lower():
        with open(src_path, encoding="utf-8") as f:
            cleaned = strip_pipboy_kit_sections(f.read())
        if setup_show_unavailable is not None:
            cleaned = set_pipboy_ini_setup_show_unavailable(cleaned, setup_show_unavailable)
        with open(dst_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(cleaned)
    else:
        shutil.copy2(src_path, dst_path)


def fold_bundle(
    owner_set: str,
    stages: Dict[str, str],
    out_dir: str,
    clean_core_out: Optional[str] = None,
    port_esm: Optional[str] = None,
    starfield_dir: Optional[str] = None,
    hardlink: bool = True,
    max_plugins: int = MAX_STARFIELD_PLUGINS,
    max_ba2_bytes: int = MAX_BA2_BYTES,
    profile: str = "player",
    pipboy_sfse_override: Optional[str] = None,
    with_route_loot: bool = False,
    with_experimental_core: bool = False,
    setup_show_unavailable: Optional[int] = None,
) -> Dict[str, object]:
    """Prepare clean core from owner_set, fold all staged components, verify, and publish <out_dir>."""
    final = os.path.abspath(out_dir)
    cc_dir = os.path.abspath(clean_core_out or (final + ".clean-core"))
    refuse_unsafe_output_dir(final, label="--out", game_dirs=(starfield_dir,))
    refuse_unsafe_output_dir(cc_dir, label="--clean-core-out", game_dirs=(starfield_dir,))
    if os.path.exists(final):
        raise BundleRefused(f"output bundle directory already exists: {final}")
    dropped_keys: set[str] = set()
    if not with_route_loot:
        dropped_keys.add("route_loot")
    if profile == "player":
        dropped_keys.add("candidate_walk")
        if not with_experimental_core:
            dropped_keys.update(EXPERIMENTAL_CORE_COMPONENT_KEYS)
    if dropped_keys:
        stages = {k: v for k, v in stages.items() if k not in dropped_keys}

    has_mission_stage = "mission" in stages
    mission_data_rels: List[str] = []
    if has_mission_stage:
        _, ms_outputs = extract_component_outputs("mission", stages["mission"])
        mission_data_rels = [r for r in ms_outputs if r.startswith("Data/")]

    if os.path.exists(cc_dir):
        shutil.rmtree(cc_dir)
    cc_info = prepare_clean_core(
        owner_set,
        cc_dir,
        hardlink=hardlink,
        strip_mission=has_mission_stage,
        extra_dropped_data=mission_data_rels,
    )
    base_plugins: List[str] = list(cc_info["base_plugins"])
    clean_readme = Path(os.path.join(cc_dir, "README.txt")).read_text(encoding="utf-8")

    partial = make_newgame.new_partial(final, create=True)
    for dp, dirs, fns in os.walk(cc_dir):
        dirs.sort()
        rel_d = os.path.relpath(dp, cc_dir)
        dst_d = partial if rel_d == "." else os.path.join(partial, rel_d)
        os.makedirs(dst_d, exist_ok=True)
        for fn in sorted(fns):
            if rel_d == "." and fn.lower() == "readme.txt":
                continue
            link_or_copy(os.path.join(dp, fn), os.path.join(dst_d, fn), hardlink=hardlink)

    ordered_keys = [k for k in ORDERED_COMPONENT_KEYS if k in stages]
    for extra_k in stages:
        if extra_k not in ordered_keys:
            ordered_keys.append(extra_k)

    plugins: List[str] = list(base_plugins)
    components_record: Dict[str, dict] = {}
    folded_data_hashes: Dict[str, str] = {}
    sfse_sidecar_hashes: Dict[str, str] = {}
    ng_plan_obj: Optional[dict] = None

    for key in ordered_keys:
        st_dir = os.path.abspath(stages[key])
        if key == "newgame":
            ng_plan_p = os.path.join(st_dir, "plan.json")
            if os.path.isfile(ng_plan_p):
                with open(ng_plan_p, encoding="utf-8") as f:
                    ng_plan_obj = json.load(f)

        # Optional SFSE sidecar handling (kept outside Data/ so Archive2 never packs DLLs/INIs into BA2)
        if key == "combat":
            combat_sc = os.path.join(st_dir, "sfse_sidecar")
            if os.path.isdir(combat_sc):
                for fn in sorted(os.listdir(combat_sc)):
                    sfile = os.path.join(combat_sc, fn)
                    if os.path.isfile(sfile):
                        rel_sc = f"SFSE/Plugins/{fn}"
                        dst_sc = os.path.join(partial, "sfse_sidecar", "SFSE", "Plugins", fn)
                        os.makedirs(os.path.dirname(dst_sc), exist_ok=True)
                        shutil.copy2(sfile, dst_sc)
                        sfse_sidecar_hashes[rel_sc] = sha256_file(dst_sc)
        elif key == "reputation":
            for fn in ("FO4SFPipboyKit.ini", "FO4SFPipboyMenu.reputation.ini", "FO4SFPipboyReputation.json", "FO4SFPipboyReputation.tsv"):
                sfile = os.path.join(st_dir, fn)
                if os.path.isfile(sfile):
                    dst_name = "FO4SFPipboyKit.ini" if fn == "FO4SFPipboyMenu.reputation.ini" else fn
                    rel_sc = f"reputation/{dst_name}"
                    dst_sc = os.path.join(partial, "sfse_sidecar", "reputation", dst_name)
                    os.makedirs(os.path.dirname(dst_sc), exist_ok=True)
                    shutil.copy2(sfile, dst_sc)
                    sfse_sidecar_hashes[rel_sc] = sha256_file(dst_sc)
        elif key == "pipboy":
            validate_pipboy_stage(st_dir, has_override_dll=bool(pipboy_sfse_override))
            effective_setup_show_unavailable = resolve_setup_show_unavailable(
                setup_show_unavailable,
                ng_plan_obj,
            )
            sfse_plugins_src = os.path.join(st_dir, "SFSE", "Plugins")
            sidecar_src = os.path.join(st_dir, "sfse")
            if os.path.isdir(sfse_plugins_src):
                for fn in sorted(os.listdir(sfse_plugins_src)):
                    sfile = os.path.join(sfse_plugins_src, fn)
                    if os.path.isfile(sfile):
                        rel_sc = f"SFSE/Plugins/{fn}"
                        dst_sc = os.path.join(partial, "sfse_sidecar", "SFSE", "Plugins", fn)
                        _copy_or_strip_pipboy_ini(
                            sfile,
                            dst_sc,
                            setup_show_unavailable=effective_setup_show_unavailable,
                        )
                        sfse_sidecar_hashes[rel_sc] = sha256_file(dst_sc)
            elif os.path.isdir(sidecar_src):
                for fn in sorted(os.listdir(sidecar_src)):
                    sfile = os.path.join(sidecar_src, fn)
                    if os.path.isfile(sfile):
                        dst_sc = os.path.join(partial, "sfse_sidecar", fn)
                        _copy_or_strip_pipboy_ini(
                            sfile,
                            dst_sc,
                            setup_show_unavailable=effective_setup_show_unavailable,
                        )
                        sfse_sidecar_hashes[fn] = sha256_file(dst_sc)
            if pipboy_sfse_override and os.path.isdir(pipboy_sfse_override):
                for src_fn, dst_fn in (
                    ("FO4SFPipboyMenu.dll", "FO4SFPipboyMenu.dll"),
                    ("FO4SFPipboyMenu.ini", "FO4SFPipboyMenu.ini"),
                    ("build.json", "FO4SFPipboyMenu.build.json"),
                ):
                    sfile = os.path.join(pipboy_sfse_override, src_fn)
                    if os.path.isfile(sfile):
                        rel_sc = f"SFSE/Plugins/{dst_fn}"
                        dst_sc = os.path.join(partial, "sfse_sidecar", "SFSE", "Plugins", dst_fn)
                        # Never overwrite a generated Stage=2 FO4SFPipboyMenu.ini with build.ps1's idle Stage=0 INI
                        if dst_fn == "FO4SFPipboyMenu.ini" and os.path.isfile(dst_sc):
                            continue
                        _copy_or_strip_pipboy_ini(
                            sfile,
                            dst_sc,
                            setup_show_unavailable=effective_setup_show_unavailable,
                        )
                        sfse_sidecar_hashes[rel_sc] = sha256_file(dst_sc)

        comp_plugins, comp_outputs = extract_component_outputs(key, st_dir)
        if key == "pipboy":
            for pb_ini_cand in (
                os.path.join(partial, "sfse_sidecar", "SFSE", "Plugins", "FO4SFPipboyMenu.ini"),
                os.path.join(partial, "sfse_sidecar", "FO4SFPipboyMenu.ini"),
            ):
                if not os.path.isfile(pb_ini_cand):
                    continue
                st_iface = os.path.join(st_dir, "Data", "Interface")
                existing_low = {r.replace("\\", "/").casefold() for r in comp_outputs}
                for _ini_k, swf_nm in named_pipboy_ini_movies(Path(pb_ini_cand).read_text(encoding="utf-8")):
                    matched_swf = _find_interface_swf_in_dir(st_iface, swf_nm)
                    if matched_swf is not None:
                        rel_swf = f"Data/Interface/{matched_swf}"
                        if rel_swf.casefold() not in existing_low:
                            comp_outputs[rel_swf] = sha256_file(os.path.join(st_iface, *matched_swf.split("/")))
                            existing_low.add(rel_swf.casefold())
                break
        for plg in comp_plugins:
            if plg.casefold() in {p.casefold() for p in plugins}:
                raise BundleRefused(f"duplicate plugin {plg} from component {key}")
            plugins.append(plg)

        recorded_comp_outputs: Dict[str, str] = {}
        for rel, want in comp_outputs.items():
            src_f = resolve_stage_source(st_dir, rel)
            dst_f = os.path.join(partial, *rel.split("/"))
            cc_f = os.path.join(cc_dir, *rel.split("/"))
            if os.path.exists(cc_f):
                if rel.startswith("Data/") and os.path.isfile(cc_f) and sha256_file(cc_f) == want and sha256_file(dst_f) == want:
                    folded_data_hashes[rel] = want
                    recorded_comp_outputs[rel] = want
                    continue
                raise BundleRefused(f"fold refused: clean core already has {rel} with differing sha256 (component {key})")
            if os.path.exists(dst_f):
                if rel.startswith("Data/") and os.path.isfile(dst_f) and folded_data_hashes.get(rel) == want and sha256_file(dst_f) == want:
                    recorded_comp_outputs[rel] = want
                    continue
                raise BundleRefused(f"fold refused: {key} output {rel} collides with differing staged file")
            os.makedirs(os.path.dirname(dst_f), exist_ok=True)
            shutil.copy2(src_f, dst_f)
            if rel.startswith("Data/"):
                folded_data_hashes[rel] = want
            recorded_comp_outputs[rel] = want

        components_record[key] = {
            "plugins": comp_plugins,
            "outputs": recorded_comp_outputs,
        }

    # Ensure --plugins list already respects every TES4 master edge (e.g. FO4SFMission.esm after FO4TerrainCore.esm)
    # while keeping plugins[0] (FO4ActorRaider.esm) first to name "<first plugin> - Main.ba2".
    try:
        masters_map = {p: exp_install.plugin_masters(os.path.join(partial, p)) for p in plugins}
        seed_lines = ["*FO4Port.esm"] + [f"*{p}" for p in plugins]
        ordered_lines, _moved, missing_masters = exp_install.order_lines(seed_lines, plugins, masters_map)
    except ValueError as err:
        raise BundleRefused(f"bundle plugin order failed: {err}") from err
    if missing_masters:
        joined_miss = ", ".join(f"{p}->{m}" for p, m in missing_masters)
        raise BundleRefused(f"bundle plugins missing required masters: {joined_miss}")
    plugins = [ln.lstrip("*") for ln in ordered_lines if ln.lstrip("*").casefold() != "fo4port.esm"]

    Path(os.path.join(partial, "README.txt")).write_text(
        bundle_readme(clean_readme, plugins, ordered_keys),
        encoding="utf-8",
        newline="\n",
    )

    sf_placeholder = starfield_dir or "<STARFIELD_DIR>"
    install_cmd, rollback_cmd = install_and_rollback_commands(final, sf_placeholder, plugins)
    bplan = {
        "kind": "core-candidate-bundle",
        "version": 2,
        "build_head": current_git_head(REPO),
        "profile": profile,
        "with_route_loot": bool(with_route_loot),
        "with_experimental_core": True if profile == "test" else bool(with_experimental_core),
        "base_plugins": base_plugins,
        "plugins": plugins,
        "components": components_record,
        "sfse_sidecar": sfse_sidecar_hashes,
        "newgame_plan": ng_plan_obj,
        "port_esm_checked": os.path.abspath(port_esm) if port_esm else None,
        "install_command": install_cmd,
        "rollback_command": rollback_cmd,
    }
    plan_partial_p = os.path.join(partial, "bundle_plan.json")
    with open(plan_partial_p, "w", encoding="utf-8") as f:
        json.dump(bplan, f, indent=1)

    problems, metrics = verify_bundle(
        partial,
        plan_partial_p,
        port_esm=port_esm,
        max_plugins=max_plugins,
        max_ba2_bytes=max_ba2_bytes,
    )
    if problems:
        for p in problems:
            print("FAIL  " + p)
        raise BundleRefused(f"bundle verify failed with {len(problems)} problem(s) (attempt kept at {partial})")

    os.replace(partial, final)
    print(f"folded plugins ({len(plugins)}): {', '.join(plugins)}")
    print(
        f"archive check: {metrics['data_file_count']:,} Data/ files, "
        f"estimated Main.ba2 = {metrics['estimated_main_ba2_bytes']:,} B "
        f"({metrics['estimated_main_ba2_bytes'] / (1024**3):.3f} GiB <= 4.000 GiB limit)"
    )
    print("verify: ok")
    print("INSTALL (game closed):  " + install_cmd)
    print("ROLLBACK (game closed): " + rollback_cmd)
    return {"bundle_dir": final, "clean_core": cc_info, "metrics": metrics, "plan": bplan}


def cmd_build(a, system=None) -> int:
    ensure_game_closed(system)
    stages = stage_from_checkout(a)
    fold_bundle(
        owner_set=a.owner_set,
        stages=stages,
        out_dir=a.out,
        clean_core_out=a.clean_core_out,
        port_esm=a.port,
        starfield_dir=a.starfield_dir,
        hardlink=not a.no_hardlink,
        max_plugins=a.max_plugins,
        max_ba2_bytes=a.max_ba2_bytes,
        profile=a.profile,
        pipboy_sfse_override=getattr(a, "_pipboy_sfse_override", None),
        with_route_loot=bool(getattr(a, "with_route_loot", False)),
        with_experimental_core=bool(getattr(a, "with_experimental_core", False)),
        setup_show_unavailable=getattr(a, "show_unavailable_starts", None),
    )
    return 0


def cmd_fold(a, system=None) -> int:
    ensure_game_closed(system)
    refuse_unsafe_output_dir(a.out, label="--out", game_dirs=(a.starfield_dir,))
    if a.clean_core_out:
        refuse_unsafe_output_dir(a.clean_core_out, label="--clean-core-out", game_dirs=(a.starfield_dir,))
    root = os.path.abspath(a.stages_root)
    profile = getattr(a, "profile", "player")
    with_route_loot = bool(getattr(a, "with_route_loot", False)) and not getattr(a, "no_route_loot", False)
    with_experimental_core = bool(getattr(a, "with_experimental_core", False))
    want_fade_hold = (
        not getattr(a, "no_fade_hold", False)
        and (profile == "test" or bool(getattr(a, "fade_hold", False)))
    )
    mapping = {
        "core_values": (
            ("00-core-values-player", "00-core-values-r2", "00-core-values")
            if profile == "player"
            else ("00-core-values-test", "00-core-values-r2", "00-core-values")
        ),
        "cog_door": ("01-cog-door-r2", "01-cog-door"),
        "exit_lift": ("02-exit-lift-r2", "02-exit-lift"),
        "mission": ("02b-mission-r2", "02b-mission"),
        "newgame": (
            ("03-newgame-fadehold", "03-newgame-r2", "03-newgame")
            if want_fade_hold
            else ("03-newgame", "03-newgame-r2")
        ),
        "workshop": ("06-workshop-r2", "06-workshop"),
        "powerarmor": ("07-powerarmor-player", "07-powerarmor") if profile == "player" else ("07-powerarmor",),
        "fort_hagen": ("14-fort-hagen", "10-fort-hagen"),
    }
    if profile == "test" or with_experimental_core:
        mapping.update({
            "rads": ("04-rads-r2", "04-rads"),
            "hardcore": ("05-hardcore-r2", "05-hardcore"),
            "progression": ("08-progression-r2", "08-progression"),
            "list_dialogue": ("09-list-dialogue-player", "09-list-dialogue") if profile == "player" else ("09-list-dialogue",),
            "combat": ("10-combat-player", "10-combat") if profile == "player" else ("10-combat",),
            "reputation": ("11-reputation-player", "11-reputation") if profile == "player" else ("11-reputation",),
            "companions": ("12-companions-player", "12-companions") if profile == "player" else ("12-companions",),
            "alife": ("13-alife-r2", "13-alife"),
        })
    if with_route_loot:
        mapping["route_loot"] = ("17-route-loot-r2", "17-route-loot")
    if profile == "test":
        mapping["candidate_walk"] = ("15-candidate-walk", "11-candidate-walk")
    stages: Dict[str, str] = {}
    for k, subs in mapping.items():
        for sub in subs:
            cand = os.path.join(root, sub)
            if os.path.isdir(cand):
                stages[k] = cand
                break
    if getattr(a, "mission_stage", None):
        ms_dir = os.path.abspath(a.mission_stage)
        if not os.path.isdir(ms_dir):
            raise BundleRefused(f"--mission-stage directory not found: {ms_dir}")
        stages["mission"] = ms_dir
    if getattr(a, "route_loot_stage", None) and with_route_loot:
        rl_dir = os.path.abspath(a.route_loot_stage)
        if not os.path.isdir(rl_dir):
            raise BundleRefused(f"--route-loot-stage directory not found: {rl_dir}")
        stages["route_loot"] = rl_dir
    if a.with_pipboy:
        if not a.pipboy_stage:
            raise BundleRefused("--with-pipboy requires --pipboy-stage <dir>")
        pb_override = getattr(a, "pipboy_sfse_build", None)
        validate_pipboy_stage(a.pipboy_stage, has_override_dll=bool(pb_override))
        stages["pipboy"] = os.path.abspath(a.pipboy_stage)
    fold_bundle(
        owner_set=a.owner_set,
        stages=stages,
        out_dir=a.out,
        clean_core_out=a.clean_core_out,
        port_esm=a.port,
        starfield_dir=a.starfield_dir,
        hardlink=not a.no_hardlink,
        max_plugins=a.max_plugins,
        max_ba2_bytes=a.max_ba2_bytes,
        profile=profile,
        pipboy_sfse_override=os.path.abspath(a.pipboy_sfse_build) if getattr(a, "pipboy_sfse_build", None) else None,
        with_route_loot=with_route_loot,
        with_experimental_core=with_experimental_core,
        setup_show_unavailable=getattr(a, "show_unavailable_starts", None),
    )
    return 0


def _atomic_write_file(dst_path: str, payload: bytes, prefix: str = ".fo4sf-sidecar-") -> None:
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    exp_install.deployment.atomic_write_bytes(dst_path, payload, prefix)


def _safe_sidecar_rel_target(data_dir: str, rel: str) -> str:
    norm = rel.replace("\\", "/")
    parts = [p for p in norm.split("/") if p]
    if len(parts) != 3 or parts[0] != "SFSE" or parts[1] != "Plugins" or parts[2] in (".", ".."):
        raise BundleRefused(f"sidecar path must be SFSE/Plugins/<filename>, got {rel!r}")
    data_real = os.path.realpath(data_dir)
    target = os.path.abspath(os.path.join(data_dir, *parts))
    parent_real = os.path.realpath(os.path.dirname(target)) if os.path.exists(os.path.dirname(target)) else data_real
    if os.path.commonpath((data_real, parent_real)) != data_real:
        raise BundleRefused(f"sidecar target escapes Data/: {rel!r}")
    return target


def sidecar_install(bundle_dir: str, starfield_dir: str, system=None) -> Dict[str, object]:
    """H3: Install `<bundle>/sfse_sidecar/SFSE/Plugins/*` into `<starfield>/Data/SFSE/Plugins/` with byte backups."""
    ensure_game_closed(system)
    bdir = os.path.abspath(bundle_dir)
    sf_dir = os.path.abspath(starfield_dir)
    if not os.path.isdir(bdir):
        raise BundleRefused(f"sidecar install refused: bundle directory not found: {bdir}")
    data_dir = os.path.join(sf_dir, "Data")
    if not os.path.isdir(data_dir) or os.path.islink(sf_dir) or os.path.islink(data_dir):
        raise BundleRefused(f"sidecar install refused: <starfield>/Data directory not found: {data_dir}")

    b_real = os.path.realpath(bdir)
    sf_real = os.path.realpath(sf_dir)
    try:
        common = os.path.commonpath((b_real, sf_real))
    except ValueError:
        common = ""
    if common in (b_real, sf_real):
        raise BundleRefused("sidecar install refused: --bundle-dir and --starfield must not overlap")

    rec_path = os.path.join(data_dir, SIDECAR_RECEIPT_NAME)
    sfse_dir = os.path.join(data_dir, "SFSE")
    plugins_dir = os.path.join(sfse_dir, "Plugins")
    backup_dir = os.path.join(sfse_dir, SIDECAR_BACKUP_DIRNAME)

    if os.path.lexists(rec_path):
        raise BundleRefused(f"sidecar install refused: receipt already exists ({rec_path}); run sidecar-undo first")
    if os.path.lexists(backup_dir):
        raise BundleRefused(f"sidecar install refused: backup folder already exists ({backup_dir}); run sidecar-undo first")
    for chk_d in (sfse_dir, plugins_dir):
        if os.path.islink(chk_d) or (os.path.exists(chk_d) and not os.path.isdir(chk_d)):
            raise BundleRefused(f"sidecar install refused: unsafe target path {chk_d}")

    ppath = os.path.join(bdir, "bundle_plan.json")
    if not os.path.isfile(ppath):
        raise BundleRefused(f"sidecar install refused: bundle_plan.json missing in {bdir}")
    with open(ppath, encoding="utf-8") as f:
        bplan = json.load(f)

    sidecar_map: Dict[str, str] = dict(bplan.get("sfse_sidecar") or {})
    install_entries: List[Tuple[str, str, str]] = []
    skipped_reputation: List[str] = []
    for rel, want_sha in sorted(sidecar_map.items()):
        norm = rel.replace("\\", "/")
        if norm.startswith("reputation/"):
            skipped_reputation.append(norm)
            continue
        if not norm.startswith("SFSE/Plugins/"):
            raise BundleRefused(f"sidecar install refused: unexpected sfse_sidecar entry {rel!r}")
        src_p = os.path.join(bdir, "sfse_sidecar", *norm.split("/"))
        if os.path.islink(src_p) or not os.path.isfile(src_p):
            raise BundleRefused(f"sidecar install refused: staged file missing or symlink: {norm}")
        got_sha = sha256_file(src_p)
        if got_sha != want_sha:
            raise BundleRefused(f"sidecar install refused: {norm} sha256 {got_sha} != manifest {want_sha}")
        install_entries.append((norm, src_p, want_sha))

    if not install_entries:
        raise BundleRefused(f"sidecar install refused: bundle has zero SFSE/Plugins sidecar files ({bdir})")

    staged_plugins_dir = os.path.join(bdir, "sfse_sidecar", "SFSE", "Plugins")
    if os.path.isdir(staged_plugins_dir):
        expected_names = {os.path.basename(norm) for norm, _, _ in install_entries}
        actual_names = set(os.listdir(staged_plugins_dir))
        untracked = sorted(actual_names - expected_names)
        if untracked:
            raise BundleRefused(f"sidecar install refused: untracked files in sfse_sidecar/SFSE/Plugins: {untracked}")

    created_sfse_dir = not os.path.exists(sfse_dir)
    created_plugins_dir = not os.path.exists(plugins_dir)

    added: List[Dict[str, object]] = []
    overwritten: List[Dict[str, object]] = []

    # Validate targets & take byte-exact backups BEFORE writing any target file
    os.makedirs(backup_dir, exist_ok=False)
    try:
        for idx, (norm, _src_p, want_sha) in enumerate(install_entries):
            dst_p = _safe_sidecar_rel_target(data_dir, norm)
            if os.path.islink(dst_p) or os.path.isdir(dst_p):
                raise BundleRefused(f"sidecar install refused: target is a symlink or directory: {dst_p}")
            if os.path.isfile(dst_p):
                with open(dst_p, "rb") as rf:
                    orig_bytes = rf.read()
                orig_sha = hashlib.sha256(orig_bytes).hexdigest()
                bak_name = f"{idx:02d}_{os.path.basename(dst_p)}.bak"
                bak_p = os.path.join(backup_dir, bak_name)
                _atomic_write_file(bak_p, orig_bytes, prefix=".fo4sf-scbak-")
                if sha256_file(bak_p) != orig_sha:
                    raise BundleRefused(f"sidecar install refused: backup verification failed for {norm}")
                overwritten.append(
                    {
                        "rel": norm,
                        "backup_file": bak_name,
                        "original_sha256": orig_sha,
                        "original_size": len(orig_bytes),
                        "installed_sha256": want_sha,
                    }
                )
            else:
                added.append({"rel": norm, "installed_sha256": want_sha})

        receipt: Dict[str, object] = {
            "kind": "fo4sf-sidecar-install",
            "schema": 1,
            "complete": False,
            "bundle_dir": bdir,
            "build_head": bplan.get("build_head"),
            "created_sfse_dir": created_sfse_dir,
            "created_plugins_dir": created_plugins_dir,
            "added": added,
            "overwritten": overwritten,
            "not_installed_reference_only": skipped_reputation,
        }
        _atomic_write_file(rec_path, (json.dumps(receipt, indent=2) + "\n").encode("utf-8"))
    except Exception:
        shutil.rmtree(backup_dir, ignore_errors=True)
        if created_sfse_dir and os.path.isdir(sfse_dir) and not os.listdir(sfse_dir):
            try:
                os.rmdir(sfse_dir)
            except OSError:
                pass
        raise

    published_added: List[str] = []
    published_overwritten: List[Dict[str, object]] = []
    ow_by_rel = {str(e["rel"]): e for e in overwritten}
    try:
        os.makedirs(plugins_dir, exist_ok=True)
        for norm, src_p, want_sha in install_entries:
            dst_p = _safe_sidecar_rel_target(data_dir, norm)
            with open(src_p, "rb") as sf_f:
                payload = sf_f.read()
            _atomic_write_file(dst_p, payload)
            if sha256_file(dst_p) != want_sha:
                raise BundleRefused(f"sidecar install failed post-write hash check: {norm}")
            if norm in ow_by_rel:
                published_overwritten.append(ow_by_rel[norm])
            else:
                published_added.append(dst_p)

        receipt["complete"] = True
        _atomic_write_file(rec_path, (json.dumps(receipt, indent=2) + "\n").encode("utf-8"))
    except Exception:
        # Roll back partial publication from verified backups
        for ow in published_overwritten:
            bak_p = os.path.join(backup_dir, str(ow["backup_file"]))
            dst_p = _safe_sidecar_rel_target(data_dir, str(ow["rel"]))
            if os.path.isfile(bak_p):
                with open(bak_p, "rb") as bf:
                    _atomic_write_file(dst_p, bf.read())
        for ad_p in published_added:
            if os.path.isfile(ad_p):
                try:
                    os.remove(ad_p)
                except OSError:
                    pass
        shutil.rmtree(backup_dir, ignore_errors=True)
        if os.path.isfile(rec_path):
            try:
                os.remove(rec_path)
            except OSError:
                pass
        if created_plugins_dir and os.path.isdir(plugins_dir) and not os.listdir(plugins_dir):
            try:
                os.rmdir(plugins_dir)
            except OSError:
                pass
        if created_sfse_dir and os.path.isdir(sfse_dir) and not os.listdir(sfse_dir):
            try:
                os.rmdir(sfse_dir)
            except OSError:
                pass
        raise

    print(
        f"installed sidecar: {len(install_entries)} file(s) "
        f"(added={len(added)}, overwritten={len(overwritten)}, not_installed_reputation={len(skipped_reputation)})"
    )
    return receipt


def sidecar_undo(starfield_dir: str, system=None) -> Dict[str, object]:
    """H3: Restore every backed-up sidecar file byte-for-byte and remove only what sidecar-install added."""
    ensure_game_closed(system)
    sf_dir = os.path.abspath(starfield_dir)
    data_dir = os.path.join(sf_dir, "Data")
    rec_path = os.path.join(data_dir, SIDECAR_RECEIPT_NAME)
    sfse_dir = os.path.join(data_dir, "SFSE")
    plugins_dir = os.path.join(sfse_dir, "Plugins")
    backup_dir = os.path.join(sfse_dir, SIDECAR_BACKUP_DIRNAME)

    if os.path.islink(rec_path) or not os.path.isfile(rec_path):
        raise BundleRefused(f"sidecar undo refused: receipt not found ({rec_path})")

    try:
        with open(rec_path, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError) as err:
        raise BundleRefused(f"sidecar undo refused: unreadable receipt ({err})") from err

    if not isinstance(rec, dict) or rec.get("kind") != "fo4sf-sidecar-install" or rec.get("schema") != 1:
        raise BundleRefused("sidecar undo refused: unrecognized FO4SFSidecar.install.json schema")

    added = list(rec.get("added") or [])
    overwritten = list(rec.get("overwritten") or [])

    # Pre-verify ALL backup files & target safety BEFORE mutating Data/SFSE/Plugins
    restored_payloads: List[Tuple[str, bytes, str]] = []
    for ow in overwritten:
        rel = str(ow.get("rel") or "")
        bak_name = str(ow.get("backup_file") or "")
        want_orig_sha = str(ow.get("original_sha256") or "")
        dst_p = _safe_sidecar_rel_target(data_dir, rel)
        if os.path.islink(dst_p) or os.path.isdir(dst_p):
            raise BundleRefused(f"sidecar undo refused: target is a symlink or directory: {dst_p}")
        if not bak_name or "/" in bak_name or "\\" in bak_name:
            raise BundleRefused(f"sidecar undo refused: invalid backup_file {bak_name!r}")
        bak_p = os.path.join(backup_dir, bak_name)
        if os.path.islink(bak_p) or not os.path.isfile(bak_p):
            raise BundleRefused(f"sidecar undo refused: backup file missing ({bak_p})")
        with open(bak_p, "rb") as bf:
            raw_orig = bf.read()
        got_sha = hashlib.sha256(raw_orig).hexdigest()
        if got_sha != want_orig_sha:
            raise BundleRefused(
                f"sidecar undo refused: backup {bak_name} sha256 {got_sha} != recorded {want_orig_sha}"
            )
        restored_payloads.append((dst_p, raw_orig, want_orig_sha))

    added_targets: List[str] = []
    for ad in added:
        rel = str(ad.get("rel") or "")
        dst_p = _safe_sidecar_rel_target(data_dir, rel)
        if os.path.islink(dst_p) or os.path.isdir(dst_p):
            raise BundleRefused(f"sidecar undo refused: added target is a symlink or directory: {dst_p}")
        added_targets.append(dst_p)

    # 1. Restore every backed-up file and verify its restored SHA-256
    for dst_p, raw_orig, want_orig_sha in restored_payloads:
        _atomic_write_file(dst_p, raw_orig)
        if sha256_file(dst_p) != want_orig_sha:
            raise BundleRefused(f"sidecar undo failed post-restore hash check: {dst_p}")

    # 2. Remove ONLY the files added by sidecar-install
    removed_count = 0
    for dst_p in added_targets:
        if os.path.isfile(dst_p):
            os.remove(dst_p)
            removed_count += 1

    # 3. Clean up backup dir, receipt, and any empty SFSE dirs created by sidecar-install
    if os.path.isdir(backup_dir):
        shutil.rmtree(backup_dir)
    os.remove(rec_path)
    if rec.get("created_plugins_dir") and os.path.isdir(plugins_dir) and not os.listdir(plugins_dir):
        try:
            os.rmdir(plugins_dir)
        except OSError:
            pass
    if rec.get("created_sfse_dir") and os.path.isdir(sfse_dir) and not os.listdir(sfse_dir):
        try:
            os.rmdir(sfse_dir)
        except OSError:
            pass

    print(f"uninstalled sidecar: removed={removed_count}, restored={len(restored_payloads)}")
    return {"removed": removed_count, "restored": len(restored_payloads)}


def cmd_sidecar_status(a) -> int:
    rec_path = os.path.join(os.path.abspath(a.starfield), "Data", SIDECAR_RECEIPT_NAME)
    if not os.path.exists(rec_path):
        print("sidecar status: nothing installed")
        return 0
    with open(rec_path, encoding="utf-8") as f:
        rec = json.load(f)
    added = len(rec.get("added") or [])
    overwritten = len(rec.get("overwritten") or [])
    print(f"sidecar status: complete={rec.get('complete')} added={added} overwritten={overwritten}")
    return 0 if rec.get("complete") is True else 1


def cmd_verify(a) -> int:
    problems, metrics = verify_bundle(
        a.bundle_dir,
        plan_path=a.plan,
        port_esm=a.port,
        max_plugins=a.max_plugins,
        max_ba2_bytes=a.max_ba2_bytes,
    )
    if len(problems) == 1 and problems[0].startswith("this bundle was built at "):
        print(problems[0])
        return 1
    for p in problems:
        print("FAIL  " + p)
    if problems:
        print(f"verify: {len(problems)} problem(s); do not install")
        return 1
    plugins = metrics["plugins"]
    print(f"folded plugins ({len(plugins)}): {', '.join(plugins)}")
    print(
        f"archive check: {metrics['data_file_count']:,} Data/ files, "
        f"estimated Main.ba2 = {metrics['estimated_main_ba2_bytes']:,} B "
        f"({metrics['estimated_main_ba2_bytes'] / (1024**3):.3f} GiB <= 4.000 GiB limit)"
    )
    print("verify: ok")
    return 0


def cmd_log(a) -> int:
    results = bundle_log.evaluate_walk_logs(
        a.log_dir,
        make_newgame.summarize,
        sfse_log_dir=getattr(a, "sfse_log_dir", None),
    )
    if a.step == "all":
        steps = [s for s in bundle_log.STEP_NAMES if not (getattr(a, "no_pipboy", False) and s == "pipboy")]
    else:
        steps = [a.step]
    any_fail = False
    for s in steps:
        r = results[s]
        tag = "PASS" if r["ok"] else "FAIL"
        if not r["ok"]:
            any_fail = True
        print(f"{tag}  {s}: {r['detail']}")
    print("verdict: " + ("PASS" if not any_fail else "FAIL"))
    return 0 if not any_fail else 1


def main(argv: Optional[Sequence[str]] = None, system=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--owner-set", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--work", required=True)
    b.add_argument("--clean-core-out", default=None)
    b.add_argument("--starfield-dir", required=True)
    b.add_argument("--fo4-data", required=True)
    b.add_argument("--port", required=True)
    b.add_argument("--port-ids", required=True)
    b.add_argument("--door-anim-dll", required=True)
    b.add_argument("--collision-template", required=True)
    b.add_argument("--texconv", required=True)
    b.add_argument("--render-python", default=None)
    b.add_argument("--profile", choices=("player", "test"), default="player")
    b.add_argument("--commonlibsf", default=None)
    b.add_argument("--msvc-env", default=None)
    b.add_argument("--combat-sfse-build", default=None)
    b.add_argument("--pipboy-sfse-build", default=None)
    b.add_argument("--mission-stage", default=None)
    b.add_argument("--route-loot-stage", default=None)
    b.add_argument("--no-mission", action="store_true")
    b.add_argument("--no-route-loot", action="store_true")
    b.add_argument("--with-route-loot", action="store_true", help="Opt-in FO4SFRouteLoot.esm (held out by default on both player and test per T1)")
    b.add_argument("--with-experimental-core", action="store_true", help="Opt-in Track 2 experimental core slices on --profile player (off by default)")
    b.add_argument("--fade-hold", action="store_true", help="Opt-in pre-world start setup room in NewGame (off by default on --profile player per T3)")
    b.add_argument("--no-fade-hold", action="store_true", help="Disable pre-world start setup room even on --profile test")
    b.add_argument("--no-alife", action="store_true")
    b.add_argument("--no-fort-hagen", action="store_true")
    b.add_argument("--no-walk-harness", action="store_true")
    b.add_argument("--with-pipboy", action="store_true")
    b.add_argument("--pipboy-stage", default=None)
    b.add_argument(
        "--show-unavailable-starts",
        type=int,
        choices=(0, 1),
        default=None,
        help="S3 unavailable-start policy (0|1) forwarded to NewGame and FO4SFPipboyMenu.ini SetupShowUnavailable (default: inherit 03-newgame/plan.json or 0)",
    )
    b.add_argument("--no-hardlink", action="store_true")
    b.add_argument("--max-plugins", type=int, default=MAX_STARFIELD_PLUGINS)
    b.add_argument("--max-ba2-bytes", type=int, default=MAX_BA2_BYTES)

    fo = sub.add_parser("fold")
    fo.add_argument("--owner-set", required=True)
    fo.add_argument("--stages-root", required=True)
    fo.add_argument("--out", required=True)
    fo.add_argument("--clean-core-out", default=None)
    fo.add_argument("--port", default=None)
    fo.add_argument("--starfield-dir", default=None)
    fo.add_argument("--profile", choices=("player", "test"), default="player")
    fo.add_argument("--mission-stage", default=None)
    fo.add_argument("--route-loot-stage", default=None)
    fo.add_argument("--no-route-loot", action="store_true")
    fo.add_argument("--with-route-loot", action="store_true", help="Opt-in FO4SFRouteLoot.esm (held out by default on both player and test per T1)")
    fo.add_argument("--with-experimental-core", action="store_true", help="Opt-in Track 2 experimental core slices on --profile player (off by default)")
    fo.add_argument("--fade-hold", action="store_true", help="Prefer 03-newgame-fadehold when folding --profile player")
    fo.add_argument("--no-fade-hold", action="store_true", help="Prefer direct-vault 03-newgame even when folding --profile test")
    fo.add_argument("--with-pipboy", action="store_true")
    fo.add_argument("--pipboy-stage", default=None)
    fo.add_argument("--pipboy-sfse-build", default=None)
    fo.add_argument(
        "--show-unavailable-starts",
        type=int,
        choices=(0, 1),
        default=None,
        help="S3 unavailable-start policy (0|1) forwarded to FO4SFPipboyMenu.ini SetupShowUnavailable (default: inherit 03-newgame/plan.json or 0)",
    )
    fo.add_argument("--no-hardlink", action="store_true")
    fo.add_argument("--max-plugins", type=int, default=MAX_STARFIELD_PLUGINS)
    fo.add_argument("--max-ba2-bytes", type=int, default=MAX_BA2_BYTES)

    v = sub.add_parser("verify")
    v.add_argument("--bundle-dir", required=True)
    v.add_argument("--plan", default=None)
    v.add_argument("--port", default=None)
    v.add_argument("--max-plugins", type=int, default=MAX_STARFIELD_PLUGINS)
    v.add_argument("--max-ba2-bytes", type=int, default=MAX_BA2_BYTES)

    sci = sub.add_parser("sidecar-install")
    sci.add_argument("--bundle-dir", required=True)
    sci.add_argument("--starfield", required=True)

    scu = sub.add_parser("sidecar-undo")
    scu.add_argument("--starfield", required=True)

    scs = sub.add_parser("sidecar-status")
    scs.add_argument("--starfield", required=True)

    default_logs = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User")
    lg = sub.add_parser("log")
    lg.add_argument("--log-dir", default=default_logs)
    lg.add_argument("--sfse-log-dir", default=None)
    lg.add_argument("--no-pipboy", action="store_true")
    lg.add_argument("--step", choices=("all", *bundle_log.STEP_NAMES), default="all")

    args = p.parse_args(argv)
    try:
        if args.cmd == "build":
            return cmd_build(args, system=system)
        if args.cmd == "fold":
            return cmd_fold(args, system=system)
        if args.cmd == "verify":
            return cmd_verify(args)
        if args.cmd == "sidecar-install":
            sidecar_install(args.bundle_dir, args.starfield, system=system)
            return 0
        if args.cmd == "sidecar-undo":
            sidecar_undo(args.starfield, system=system)
            return 0
        if args.cmd == "sidecar-status":
            return cmd_sidecar_status(args)
        if args.cmd == "log":
            return cmd_log(args)
    except BundleRefused as err:
        print(str(err), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
