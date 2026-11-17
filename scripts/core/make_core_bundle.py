r"""Stage, fold, verify, and inspect logs for the unified FO4SF Core Candidate Bundle (CF-10).

Stages every core component from one checkout (gear door, exit lift, NewGame with hold 199 and pod_step -2.5,
rads, hardcore, workshop, power armor, progression, list dialogue, Fort Hagen when present, the console-free
candidate walk harness, and optional --with-pipboy), folds them into a clean hardlinked copy of the owner's
core set, runs full SHA-256 + TES4 master-order + plugin-count + 4 GiB BA2 archive-limit verification, and
prints one `exp_install.py install ... --pack` command plus its matching rollback command.

Refuses to run whenever Starfield.exe is open (via fo4sf.launcher.crashwatch.System.pids).

usage:
  python scripts/core/make_core_bundle.py build --owner-set <owner-set-dir> --out <bundle-dir>
      --work <scratch-stage-dir> --starfield-dir <Starfield> --fo4-data <Fallout 4/Data>
      --port <FO4Port.esm> --port-ids <formids.json>
      --door-anim-dll <CALUMI.Animation.dll> --collision-template <nif> --texconv <texconv.exe>
      [--render-python <venv-render/python.exe>] [--no-fort-hagen] [--no-walk-harness]
      [--with-pipboy --pipboy-stage <pipboy-stage-dir>] [--no-hardlink]

  python scripts/core/make_core_bundle.py fold --owner-set <owner-set-dir> --stages-root <stages-dir>
      --out <bundle-dir> [--clean-core-out <clean-core-dir>] [--port <FO4Port.esm>]
      [--with-pipboy --pipboy-stage <pipboy-stage-dir>] [--no-hardlink]

  python scripts/core/make_core_bundle.py verify --bundle-dir <bundle-dir>
      [--plan <bundle-dir>/bundle_plan.json] [--port <FO4Port.esm>]
      [--max-plugins 245] [--max-ba2-bytes 4294967295]

  python scripts/core/make_core_bundle.py log [--log-dir <My Games/Starfield/Logs/Script/User>]
      [--step all|exit|hold|rads|hardcore|workshop|powerarmor|dialogue|progression]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
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
from fo4sf.core import bundle_log  # noqa: E402
from fo4sf.launcher.crashwatch import GAME_EXE, System  # noqa: E402

MAX_STARFIELD_PLUGINS = 245
MAX_BA2_BYTES = (4 * (1024 ** 3)) - 1  # 4,294,967,295 bytes (32-bit unsigned BA2 ceiling)

INSTALL_LINE_RE = re.compile(r"(exp_install\.py install\b.*?--plugins )(?P<plugins>\S+)(?P<tail>.*)")

DROPPED_SLICE_ESMS = frozenset({
    "fo4sfnewgame.esm",
    "fo4sfvaultgeardoor.esm",
    "fo4sfexitlift.esm",
    "fo4sfrads.esm",
    "fo4sfhardcore.esm",
    "fo4sfworkshop.esm",
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

ORDERED_COMPONENT_KEYS = (
    "cog_door",
    "exit_lift",
    "newgame",
    "rads",
    "hardcore",
    "workshop",
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


def link_or_copy(src: str, dst: str, hardlink: bool = True) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if hardlink:
        os.link(src, dst)
    else:
        shutil.copy2(src, dst)


def prepare_clean_core(owner_set: str, clean_out: str, hardlink: bool = True) -> Dict[str, object]:
    """Create a clean copy of owner_set without FO4SFNewGame.esm (or other slice ESMs/PEX) and with a NEW README.txt."""
    src_root = Path(os.path.abspath(owner_set))
    dst_root = Path(os.path.abspath(clean_out))
    if not src_root.is_dir():
        raise BundleRefused(f"owner-set directory not found: {src_root}")
    src_readme = src_root / "README.txt"
    if not src_readme.is_file():
        raise BundleRefused(f"owner-set missing README.txt: {src_readme}")
    if dst_root.exists():
        raise BundleRefused(f"clean-core output already exists: {dst_root}")

    orig_readme_sha = sha256_file(str(src_readme))
    linked_count = 0
    dropped: List[str] = []

    partial = Path(make_newgame.new_partial(str(dst_root), create=True))
    for dp, dirs, files in os.walk(src_root):
        dirs.sort()
        rel_dir = Path(dp).relative_to(src_root)
        (partial / rel_dir).mkdir(parents=True, exist_ok=True)
        for fn in sorted(files):
            s = Path(dp) / fn
            rel_posix = s.relative_to(src_root).as_posix()
            rel_low = rel_posix.lower()
            if rel_low == "readme.txt":
                continue
            if ("/" not in rel_posix and rel_low in DROPPED_SLICE_ESMS) or rel_low in DROPPED_SLICE_PEX:
                dropped.append(rel_posix)
                continue
            link_or_copy(str(s), str(partial / rel_dir / fn), hardlink=hardlink)
            linked_count += 1

    def strip_slice_plugins(line: str) -> str:
        m = INSTALL_LINE_RE.search(line)
        if not m:
            return line
        kept = [p for p in m.group("plugins").split(",") if p and p.lower() not in DROPPED_SLICE_ESMS]
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


def verify_bundle(
    bundle_dir: str,
    plan_path: Optional[str] = None,
    port_esm: Optional[str] = None,
    max_plugins: int = MAX_STARFIELD_PLUGINS,
    max_ba2_bytes: int = MAX_BA2_BYTES,
) -> Tuple[List[str], Dict[str, object]]:
    """Verify every component hash, TES4 master chain, plugin count, Data root cleanliness, and 4 GiB BA2 ceiling."""
    bdir = os.path.abspath(bundle_dir)
    ppath = os.path.abspath(plan_path or os.path.join(bdir, "bundle_plan.json"))
    problems: List[str] = []
    if not os.path.isfile(ppath):
        return [f"bundle_plan.json missing: {ppath}"], {}

    with open(ppath, encoding="utf-8") as f:
        bplan = json.load(f)

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


def _run_py(py_exe: str, script_rel: str, args: Sequence[str]) -> None:
    cmd = [py_exe, os.path.join(REPO, *script_rel.split("/")), *args]
    print("+ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise BundleRefused(f"{script_rel} exited {r.returncode}")


def stage_from_checkout(a) -> Dict[str, str]:
    """Run every component's stager from this single checkout into <a.work>."""
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

    stages: Dict[str, str] = {}

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

    ng_dir = os.path.join(work, "03-newgame")
    if not os.path.exists(ng_dir):
        _run_py(py_main, "scripts/newgame/make_newgame.py", [
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
        ])
    # Verify hold 199 and pod_step -2.5 in staged NewGame plan
    with open(os.path.join(ng_dir, "plan.json"), encoding="utf-8") as f:
        ng_plan = json.load(f)
    hold_cnt = len(ng_plan["options"]["hold"].split(","))
    pod_step = float(ng_plan["points"]["pod"]["step_m"])
    if hold_cnt != 199:
        raise BundleRefused(f"NewGame hold count is {hold_cnt}, expected 199")
    if abs(pod_step - (-2.5)) > 1e-4:
        raise BundleRefused(f"NewGame pod_step is {pod_step}, expected -2.5")
    stages["newgame"] = ng_dir

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
        sdir = os.path.join(work, folder)
        if not os.path.exists(sdir):
            _run_py(py_main, rel_script, [
                "stage",
                "--out", sdir,
                "--starfield", sf_esm,
                "--compiler", compiler,
                "--content-resources", cr_zip,
            ])
        stages[key] = sdir

    combat_dir = os.path.join(work, "10-combat")
    if not os.path.exists(combat_dir):
        combat_args = ["stage", "--out", combat_dir, "--starfield-dir", sf_dir]
        if getattr(a, "combat_sfse_build", None):
            combat_args.extend(["--sfse-build", os.path.abspath(a.combat_sfse_build)])
        _run_py(py_main, "scripts/combat/make_combat_core.py", combat_args)
    stages["combat"] = combat_dir

    alife_script = os.path.join(REPO, "scripts", "alife", "make_alife.py")
    raider_esm = os.path.join(os.path.abspath(a.owner_set), "FO4ActorRaider.esm")
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

    if not getattr(a, "no_walk_harness", False):
        cw_dir = os.path.join(work, "15-candidate-walk")
        if not os.path.exists(cw_dir):
            stage_candidate_walk(cw_dir, sf_esm, compiler, cr_zip)
        stages["candidate_walk"] = cw_dir

    if getattr(a, "with_pipboy", False):
        if not getattr(a, "pipboy_stage", None):
            raise BundleRefused("--with-pipboy requires --pipboy-stage <dir>")
        stages["pipboy"] = os.path.abspath(a.pipboy_stage)

    return stages


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
) -> Dict[str, object]:
    """Prepare clean core from owner_set, fold all staged components, verify, and publish <out_dir>."""
    final = os.path.abspath(out_dir)
    if os.path.exists(final):
        raise BundleRefused(f"output bundle directory already exists: {final}")

    cc_dir = os.path.abspath(clean_core_out or (final + ".clean-core"))
    if os.path.exists(cc_dir):
        shutil.rmtree(cc_dir)
    cc_info = prepare_clean_core(owner_set, cc_dir, hardlink=hardlink)
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
            for fn in ("FO4SFPipboyMenu.reputation.ini", "FO4SFPipboyReputation.json", "FO4SFPipboyReputation.tsv"):
                sfile = os.path.join(st_dir, fn)
                if os.path.isfile(sfile):
                    rel_sc = f"reputation/{fn}"
                    dst_sc = os.path.join(partial, "sfse_sidecar", "reputation", fn)
                    os.makedirs(os.path.dirname(dst_sc), exist_ok=True)
                    shutil.copy2(sfile, dst_sc)
                    sfse_sidecar_hashes[rel_sc] = sha256_file(dst_sc)
        elif key == "pipboy":
            sfse_plugins_src = os.path.join(st_dir, "SFSE", "Plugins")
            sidecar_src = os.path.join(st_dir, "sfse")
            if os.path.isdir(sfse_plugins_src):
                for fn in sorted(os.listdir(sfse_plugins_src)):
                    sfile = os.path.join(sfse_plugins_src, fn)
                    if os.path.isfile(sfile):
                        rel_sc = f"SFSE/Plugins/{fn}"
                        dst_sc = os.path.join(partial, "sfse_sidecar", "SFSE", "Plugins", fn)
                        os.makedirs(os.path.dirname(dst_sc), exist_ok=True)
                        shutil.copy2(sfile, dst_sc)
                        sfse_sidecar_hashes[rel_sc] = sha256_file(dst_sc)
            elif os.path.isdir(sidecar_src):
                for fn in sorted(os.listdir(sidecar_src)):
                    sfile = os.path.join(sidecar_src, fn)
                    if os.path.isfile(sfile):
                        dst_sc = os.path.join(partial, "sfse_sidecar", fn)
                        os.makedirs(os.path.dirname(dst_sc), exist_ok=True)
                        shutil.copy2(sfile, dst_sc)
                        sfse_sidecar_hashes[fn] = sha256_file(dst_sc)

        comp_plugins, comp_outputs = extract_component_outputs(key, st_dir)
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
        "version": 1,
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
    )
    return 0


def cmd_fold(a, system=None) -> int:
    ensure_game_closed(system)
    root = os.path.abspath(a.stages_root)
    mapping = {
        "cog_door": ("01-cog-door",),
        "exit_lift": ("02-exit-lift",),
        "newgame": ("03-newgame",),
        "rads": ("04-rads",),
        "hardcore": ("05-hardcore",),
        "workshop": ("06-workshop",),
        "powerarmor": ("07-powerarmor",),
        "progression": ("08-progression",),
        "list_dialogue": ("09-list-dialogue",),
        "combat": ("10-combat",),
        "reputation": ("11-reputation",),
        "companions": ("12-companions",),
        "alife": ("13-alife",),
        "fort_hagen": ("14-fort-hagen", "10-fort-hagen"),
        "candidate_walk": ("15-candidate-walk", "11-candidate-walk"),
    }
    stages: Dict[str, str] = {}
    for k, subs in mapping.items():
        for sub in subs:
            cand = os.path.join(root, sub)
            if os.path.isdir(cand):
                stages[k] = cand
                break
    if a.with_pipboy:
        if not a.pipboy_stage:
            raise BundleRefused("--with-pipboy requires --pipboy-stage <dir>")
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
    )
    return 0


def cmd_verify(a) -> int:
    problems, metrics = verify_bundle(
        a.bundle_dir,
        plan_path=a.plan,
        port_esm=a.port,
        max_plugins=a.max_plugins,
        max_ba2_bytes=a.max_ba2_bytes,
    )
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
    results = bundle_log.evaluate_walk_logs(a.log_dir, make_newgame.summarize)
    steps = list(bundle_log.STEP_NAMES) if a.step == "all" else [a.step]
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
    b.add_argument("--combat-sfse-build", default=None)
    b.add_argument("--no-alife", action="store_true")
    b.add_argument("--no-fort-hagen", action="store_true")
    b.add_argument("--no-walk-harness", action="store_true")
    b.add_argument("--with-pipboy", action="store_true")
    b.add_argument("--pipboy-stage", default=None)
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
    fo.add_argument("--with-pipboy", action="store_true")
    fo.add_argument("--pipboy-stage", default=None)
    fo.add_argument("--no-hardlink", action="store_true")
    fo.add_argument("--max-plugins", type=int, default=MAX_STARFIELD_PLUGINS)
    fo.add_argument("--max-ba2-bytes", type=int, default=MAX_BA2_BYTES)

    v = sub.add_parser("verify")
    v.add_argument("--bundle-dir", required=True)
    v.add_argument("--plan", default=None)
    v.add_argument("--port", default=None)
    v.add_argument("--max-plugins", type=int, default=MAX_STARFIELD_PLUGINS)
    v.add_argument("--max-ba2-bytes", type=int, default=MAX_BA2_BYTES)

    default_logs = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User")
    lg = sub.add_parser("log")
    lg.add_argument("--log-dir", default=default_logs)
    lg.add_argument("--step", choices=("all", *bundle_log.STEP_NAMES), default="all")

    args = p.parse_args(argv)
    try:
        if args.cmd == "build":
            return cmd_build(args, system=system)
        if args.cmd == "fold":
            return cmd_fold(args, system=system)
        if args.cmd == "verify":
            return cmd_verify(args)
        if args.cmd == "log":
            return cmd_log(args)
    except BundleRefused as err:
        print(str(err), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
