"""Install / uninstall / undo / status / order / active of a staged home-world host swap
(`FO4SFHome.esm` + `FO4TerrainCore_Home.esm` replacing `FO4TerrainCore_Mars.esm` in `Plugins.txt`),
reversibly (`W3`, `C1`, `C3`).

Usage:
  python scripts/planet/home_world_install.py install --dir <stage> --starfield <game dir> [--prepacked <ba2>]
  python scripts/planet/home_world_install.py uninstall|undo|status|order|active --starfield <game dir>

Invariants:
- Imports `scripts/game/exp_install.py` unchanged and uses its own receipt `Data/FO4SFHomeWorld.install.json`
  plus `Data/FO4SFHomeWorld.swap.json` — `Data/FO4SFExp.install.json` is never written or modified.
- Refuses `install` and `uninstall` / `undo` whenever `Starfield.exe` is running (`System.pids`).
- Unticks `FO4TerrainCore_Mars.esm` and ticks `FO4SFHome.esm` + `FO4TerrainCore_Home.esm` in `Plugins.txt`
  after `FO4SFMapMarkers.esm` (refusing any other order in `install` and `order`).
- Reads every active (`*`) FO4SF plugin from `Plugins.txt` in `install` and `order`, checking `PNDT`, `LCTN`,
  and `WRLD` overrides across the full load list; allows only `FO4SFMapMarkers.esm -> FO4TerrainCore_Home.esm`
  when `LCSR` rows and `map_markers_sha256` match, refusing every other duplicate override.
- Refuses any `Plugins.txt` holding both `FO4TerrainCore_Mars.esm` and `FO4TerrainCore_Home.esm` active (`*`).
- Restores `Data` and `Plugins.txt` byte-for-byte on `uninstall` / `undo`.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from typing import Any, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPTS_DIR, ".."))
GAME_SCRIPTS = os.path.join(SCRIPTS_DIR, "game")
SRC_DIR = os.path.join(REPO_ROOT, "src")
for _p in (HERE, GAME_SCRIPTS, SCRIPTS_DIR, SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exp_install  # noqa: E402
import deploy_starfield as deployment  # noqa: E402
from fo4sf.core import loadset  # noqa: E402
from fo4sf.launcher import crashwatch  # noqa: E402
from fo4sf.planet import home_planet_spec as hspec  # noqa: E402
import make_home_planet  # noqa: E402

RECORD = "FO4SFHomeWorld.install.json"
SWAP_RECORD = "FO4SFHomeWorld.swap.json"
MARS_PLUGIN = "FO4TerrainCore_Mars.esm"
HOME_MASTER_PLUGIN = "FO4SFHome.esm"
HOME_REG_PLUGIN = "FO4TerrainCore_Home.esm"
MAP_MARKERS_PLUGIN = hspec.MAP_MARKERS_PLUGIN
PORT_PLUGIN = hspec.PORT_PLUGIN
GAME_EXE = "Starfield.exe"


def core_values_weather_flags(program_cs_path: str) -> List[str]:
    """Return `['--commonwealth-weather', '0']` when CoreValues exposes `--commonwealth-weather`, else `[]`."""
    try:
        with open(program_cs_path, encoding="utf-8") as f:
            if "--commonwealth-weather" in f.read():
                return ["--commonwealth-weather", "0"]
    except OSError:
        pass
    return []


def _active_game_pids(system: Any = None) -> List[int]:
    sys_obj = system if system is not None else crashwatch.System()
    return sys_obj.pids(GAME_EXE)


def ensure_game_closed(what: str, system: Any = None) -> None:
    """Refuse mutating Data or Plugins.txt while Starfield.exe is running or process inspection fails."""
    try:
        pids = _active_game_pids(system)
    except ValueError as err:
        sys.exit(f"{what}: cannot confirm {GAME_EXE} is closed ({err})")
    if pids:
        joined = ", ".join(str(p) for p in pids)
        sys.exit(f"{what}: {GAME_EXE} is running (pid {joined}); close the game first")


def installer(argv: List[str]) -> Optional[int]:
    """Invoke `exp_install.main` against this tool's own `FO4SFHomeWorld.install.json` receipt."""
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def _active_names(lines: Sequence[str]) -> set[str]:
    return {ln.strip()[1:].strip().casefold() for ln in lines if ln.strip().startswith("*")}


def check_no_dual_host_active(lines: Sequence[str]) -> Optional[str]:
    """Return an error string if both `FO4TerrainCore_Mars.esm` and `FO4TerrainCore_Home.esm` are active."""
    on = _active_names(lines)
    if MARS_PLUGIN.casefold() in on and HOME_REG_PLUGIN.casefold() in on:
        return f"Plugins.txt holds both {MARS_PLUGIN} and {HOME_REG_PLUGIN} active; dual host overrides are forbidden"
    return None


def _untick_plugin_lines(lines: Sequence[str], target_name: str) -> Tuple[List[str], List[dict]]:
    out: List[str] = []
    unticked: List[dict] = []
    want = target_name.casefold()
    for idx, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped.startswith("*") and stripped[1:].strip().casefold() == want:
            plain = stripped[1:].strip()
            out.append(plain)
            unticked.append({"index": idx, "original": ln, "unticked": plain})
        else:
            out.append(ln)
    return out, unticked


def _retick_plugin_lines(lines: Sequence[str], unticked_entries: Sequence[dict]) -> List[str]:
    out = list(lines)
    by_plain = {e["unticked"].strip().casefold(): e["original"] for e in unticked_entries}
    for idx, ln in enumerate(out):
        key = ln.strip().casefold()
        if key in by_plain:
            out[idx] = by_plain[key]
    return out


def validate_active_load_order(
    lines: Sequence[str],
    *,
    data_dir: str,
    stage_dir: Optional[str] = None,
    plan: Optional[dict] = None,
    pinned_map_markers_sha256: Optional[str] = None,
    map_markers_plugin_name: str = MAP_MARKERS_PLUGIN,
) -> List[str]:
    """Validate active (`*`) FO4SF plugins in `lines` against `C3` load-order and single-override rules."""
    problems: List[str] = []
    active_ours = [p for p in loadset.active_plugins(lines) if loadset.ours(p)]
    active_low = [p.casefold() for p in active_ours]
    mm_low = map_markers_plugin_name.casefold()
    port_low = PORT_PLUGIN.casefold()
    hm_low = HOME_MASTER_PLUGIN.casefold()
    hr_low = HOME_REG_PLUGIN.casefold()

    if mm_low in active_low:
        mm_idx = active_low.index(mm_low)
        mm_disp = active_ours[mm_idx]
        for tgt_low, tgt_disp in ((hm_low, HOME_MASTER_PLUGIN), (hr_low, HOME_REG_PLUGIN)):
            if tgt_low in active_low and active_low.index(tgt_low) < mm_idx:
                problems.append(
                    f"invalid load order: {mm_disp} loads after {tgt_disp}; "
                    f"{HOME_MASTER_PLUGIN} and {HOME_REG_PLUGIN} must load after {mm_disp}"
                )
    if port_low in active_low:
        port_idx = active_low.index(port_low)
        port_disp = active_ours[port_idx]
        for tgt_low, tgt_disp in ((hm_low, HOME_MASTER_PLUGIN), (hr_low, HOME_REG_PLUGIN)):
            if tgt_low in active_low and active_low.index(tgt_low) < port_idx:
                problems.append(
                    f"invalid load order: {port_disp} loads after {tgt_disp}; "
                    f"{HOME_MASTER_PLUGIN} and {HOME_REG_PLUGIN} must load after {port_disp}"
                )
    if hm_low in active_low and hr_low in active_low and active_low.index(hr_low) < active_low.index(hm_low):
        problems.append(f"invalid load order: {HOME_REG_PLUGIN} loads before its master {HOME_MASTER_PLUGIN}")

    stage_names = {p.casefold() for p in (plan.get("plugins") or ())} if (stage_dir and plan) else set()
    plugin_paths: List[str] = []
    for pname in active_ours:
        plow = pname.casefold()
        if stage_dir and plow in stage_names:
            cand = os.path.join(stage_dir, pname)
            if os.path.isfile(cand):
                plugin_paths.append(cand)
            else:
                problems.append(f"staged plugin missing: {pname}")
        else:
            cand = os.path.join(data_dir, pname)
            if os.path.isfile(cand):
                plugin_paths.append(cand)
            elif plow in (mm_low, hm_low, hr_low):
                problems.append(f"active plugin missing in Data: {pname}")

    pin_sha = (
        pinned_map_markers_sha256
        if pinned_map_markers_sha256 is not None
        else (plan.get("map_markers_sha256") if plan else None)
    )
    ov_probs = hspec.check_load_order_overrides(
        plugin_paths,
        allow_map_markers_pair=True,
        pinned_map_markers_sha256=pin_sha,
        map_markers_plugin_name=map_markers_plugin_name,
        allow_prewar_home_pair=True,
    )
    for op in ov_probs:
        if op not in problems:
            problems.append(op)
    mars_probs, _ = hspec.audit_zero_mars_references(plugin_paths)
    for mp in mars_probs:
        if mp not in problems:
            problems.append(mp)
    return problems


def _load_pinned_map_markers_info(data_dir: str) -> Tuple[Optional[str], str]:
    swap_path = os.path.join(data_dir, SWAP_RECORD)
    if os.path.isfile(swap_path):
        try:
            with open(swap_path, encoding="utf-8") as f:
                swap_doc = json.load(f)
            if isinstance(swap_doc, dict) and (
                "map_markers_sha256" in swap_doc or "map_markers_plugin" in swap_doc
            ):
                return (
                    swap_doc.get("map_markers_sha256"),
                    swap_doc.get("map_markers_plugin") or MAP_MARKERS_PLUGIN,
                )
        except (OSError, ValueError):
            pass

    rec_path = os.path.join(data_dir, RECORD)
    if os.path.isfile(rec_path):
        try:
            with open(rec_path, encoding="utf-8") as f:
                rec_doc = json.load(f)
            exp_dir = rec_doc.get("exp_dir") if isinstance(rec_doc, dict) else None
            if exp_dir and os.path.isfile(os.path.join(exp_dir, "plan.json")):
                plan_doc = make_home_planet.load_plan(exp_dir)
                return (
                    plan_doc.get("map_markers_sha256"),
                    plan_doc.get("map_markers_plugin") or MAP_MARKERS_PLUGIN,
                )
        except (OSError, ValueError):
            pass

    return None, MAP_MARKERS_PLUGIN


def install(a: argparse.Namespace) -> int:
    ensure_game_closed("home world not installed")
    stage_dir = os.path.abspath(a.dir)
    data_dir = os.path.abspath(os.path.join(a.starfield, "Data"))
    try:
        plan = make_home_planet.load_plan(stage_dir)
    except (OSError, ValueError) as exc:
        sys.exit(f"home world not installed: {exc}")

    problems = make_home_planet.verify_stage(stage_dir, plan, data_dir if os.path.isfile(os.path.join(data_dir, "Starfield.esm")) else None)
    if problems:
        sys.exit("home world not installed: stage check failed: " + "; ".join(problems))

    esm_names = sorted(n for n in os.listdir(stage_dir) if n.lower().endswith(".esm"))
    if sorted(plan["plugins"]) != esm_names:
        sys.exit(f"home world not installed: stage holds {esm_names}, plan.json lists {plan['plugins']}")

    p_txt = exp_install.plugins_txt()
    pre_raw = exp_install.read_bytes(p_txt)
    pre_lines, pre_bom, pre_nl = exp_install.plugin_lines(pre_raw)
    dual_err = check_no_dual_host_active(pre_lines)
    if dual_err:
        sys.exit(f"home world not installed: {dual_err}")

    rec_path = os.path.join(data_dir, RECORD)
    swap_path = os.path.join(data_dir, SWAP_RECORD)
    relaunch = os.path.exists(rec_path)

    mm_plugin_name = plan.get("map_markers_plugin") or MAP_MARKERS_PLUGIN
    try:
        planned_activated, _, _ = exp_install.plan_activation(pre_lines, plan["plugins"])
    except ValueError as exc:
        sys.exit(f"home world not installed: {exc}")
    planned_swapped = pre_lines if relaunch else _untick_plugin_lines(planned_activated, MARS_PLUGIN)[0]
    load_errs = validate_active_load_order(
        planned_swapped,
        data_dir=data_dir,
        stage_dir=None if relaunch else stage_dir,
        plan=plan,
        pinned_map_markers_sha256=plan.get("map_markers_sha256"),
        map_markers_plugin_name=mm_plugin_name,
    )
    if load_errs:
        sys.exit("home world not installed: " + "; ".join(load_errs))

    rc = installer(
        ["install", "--exp-dir", stage_dir, "--starfield", a.starfield, "--pack", "--plugins", ",".join(plan["plugins"])]
        + (["--prepacked", a.prepacked] if getattr(a, "prepacked", "") else [])
    )
    if rc not in (None, 0):
        return int(rc)

    if relaunch:
        cur_lines, _, _ = exp_install.read_plugins(p_txt)
        dual_after = check_no_dual_host_active(cur_lines)
        if dual_after:
            sys.exit(f"home world relaunch refused: {dual_after}")
        relaunch_errs = validate_active_load_order(
            cur_lines,
            data_dir=data_dir,
            plan=plan,
            pinned_map_markers_sha256=plan.get("map_markers_sha256"),
            map_markers_plugin_name=mm_plugin_name,
        )
        if relaunch_errs:
            sys.exit("home world relaunch refused: " + "; ".join(relaunch_errs))
        return 0

    try:
        after_raw = exp_install.read_bytes(p_txt)
        after_lines, bom, nl = exp_install.plugin_lines(after_raw)
        swapped_lines, unticked = _untick_plugin_lines(after_lines, MARS_PLUGIN)
        dual_after = check_no_dual_host_active(swapped_lines)
        if dual_after:
            raise ValueError(dual_after)
        post_errs = validate_active_load_order(
            swapped_lines,
            data_dir=data_dir,
            plan=plan,
            pinned_map_markers_sha256=plan.get("map_markers_sha256"),
            map_markers_plugin_name=mm_plugin_name,
        )
        if post_errs:
            raise ValueError("; ".join(post_errs))
        if swapped_lines != after_lines:
            exp_install.write_plugins(p_txt, swapped_lines, bom, nl, after_raw)
        swap_payload = {
            "schema": 1,
            "plugins_txt": p_txt,
            "original_plugins_b64": base64.b64encode(pre_raw).decode("ascii") if pre_raw is not None else None,
            "original_plugins_sha256": hashlib.sha256(pre_raw).hexdigest() if pre_raw is not None else None,
            "unticked": unticked,
            "map_markers_plugin": plan.get("map_markers_plugin"),
            "map_markers_sha256": plan.get("map_markers_sha256"),
        }
        deployment.write_manifest(swap_path, swap_payload)
    except Exception as exc:
        try:
            installer(["uninstall", "--starfield", a.starfield])
            if pre_raw is not None:
                deployment.atomic_write_bytes(p_txt, pre_raw, ".fo4sfhome-restore-")
            if os.path.exists(swap_path):
                os.remove(swap_path)
        finally:
            sys.exit(f"home world swap failed and was rolled back: {exc}")
    return 0


def uninstall(a: argparse.Namespace) -> int:
    ensure_game_closed("home world not uninstalled")
    data_dir = os.path.abspath(os.path.join(a.starfield, "Data"))
    rec_path = os.path.join(data_dir, RECORD)
    swap_path = os.path.join(data_dir, SWAP_RECORD)
    if not os.path.exists(rec_path) and not os.path.exists(swap_path):
        print("nothing installed")
        return 0

    exp_install.refuse_while_held(data_dir, "home world not uninstalled")
    swap_data = None
    if os.path.exists(swap_path):
        with open(swap_path, encoding="utf-8") as f:
            swap_data = json.load(f)

    rc = installer(["uninstall", "--starfield", a.starfield])
    if rc not in (None, 0):
        return int(rc)

    if swap_data is not None:
        p_txt = exp_install.plugins_txt()
        if os.path.normcase(os.path.abspath(swap_data.get("plugins_txt", p_txt))) != os.path.normcase(os.path.abspath(p_txt)):
            sys.exit("uninstall incomplete: recorded Plugins.txt path differs from current user profile")
        cur_raw = exp_install.read_bytes(p_txt)
        cur_lines, bom, nl = exp_install.plugin_lines(cur_raw)
        restored_lines = _retick_plugin_lines(cur_lines, swap_data.get("unticked", []))
        orig_b64 = swap_data.get("original_plugins_b64")
        if orig_b64 is not None:
            orig_bytes = base64.b64decode(orig_b64)
            orig_lines, _, _ = exp_install.plugin_lines(orig_bytes)
            if restored_lines == orig_lines:
                deployment.atomic_write_bytes(p_txt, orig_bytes, ".fo4sfhome-restore-", expected_current=cur_raw)
            else:
                exp_install.write_plugins(p_txt, restored_lines, bom, nl, cur_raw)
        elif cur_raw is not None and restored_lines != cur_lines:
            exp_install.write_plugins(p_txt, restored_lines, bom, nl, cur_raw)
        os.remove(swap_path)
    return 0


def order_cmd(a: argparse.Namespace) -> int:
    data_dir = os.path.abspath(os.path.join(a.starfield, "Data"))
    p_txt = exp_install.plugins_txt()
    lines, _, _ = exp_install.read_plugins(p_txt)
    dual_err = check_no_dual_host_active(lines)
    if dual_err:
        print(f"not ordered: {dual_err}")
        return 6
    pinned_mm_sha, pinned_mm_plugin = _load_pinned_map_markers_info(data_dir)
    load_errs = validate_active_load_order(
        lines,
        data_dir=data_dir,
        pinned_map_markers_sha256=pinned_mm_sha,
        map_markers_plugin_name=pinned_mm_plugin,
    )
    if load_errs:
        print("not ordered: " + "; ".join(load_errs))
        return 6
    rc = installer(["order", "--starfield", a.starfield]) or 0
    if rc != 0:
        return rc
    after_lines, _, _ = exp_install.read_plugins(p_txt)
    after_errs = validate_active_load_order(
        after_lines,
        data_dir=data_dir,
        pinned_map_markers_sha256=pinned_mm_sha,
        map_markers_plugin_name=pinned_mm_plugin,
    )
    if after_errs:
        print("not ordered: " + "; ".join(after_errs))
        return 6
    return 0


def active_cmd(a: argparse.Namespace) -> int:
    p_txt = exp_install.plugins_txt()
    lines, _, _ = exp_install.read_plugins(p_txt)
    dual_err = check_no_dual_host_active(lines)
    if dual_err:
        print(dual_err)
        return 8
    return installer(["active", "--starfield", a.starfield]) or 0


def status_cmd(a: argparse.Namespace) -> int:
    data_dir = os.path.abspath(os.path.join(a.starfield, "Data"))
    rec_path = os.path.join(data_dir, RECORD)
    if not os.path.exists(rec_path):
        print("nothing installed")
        return 0
    with open(rec_path, encoding="utf-8") as f:
        rec = json.load(f)
    swap_path = os.path.join(data_dir, SWAP_RECORD)
    if os.path.exists(swap_path):
        with open(swap_path, encoding="utf-8") as f:
            rec["swap"] = json.load(f)
    print(json.dumps(rec, indent=1))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "undo", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="Staged home-world folder (install)")
    ap.add_argument("--prepacked", default="", help="Verify and install an existing Main BA2 archive without building")
    ap.add_argument("--starfield", required=True, help="Starfield game root folder")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    if a.cmd in ("uninstall", "undo"):
        return uninstall(a)
    if a.cmd == "order":
        return order_cmd(a)
    if a.cmd == "active":
        return active_cmd(a)
    if a.cmd == "status":
        return status_cmd(a)
    return 1


if __name__ == "__main__":
    sys.exit(main())
