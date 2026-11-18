"""Install / uninstall / undo / status / order / active of a staged home-world host swap
(`FO4SFHome.esm` + `FO4TerrainCore_Home.esm` replacing `FO4TerrainCore_Mars.esm` in `Plugins.txt`),
reversibly (`W3`).

Usage:
  python scripts/planet/home_world_install.py install --dir <stage> --starfield <game dir> [--prepacked <ba2>]
  python scripts/planet/home_world_install.py uninstall|undo|status|order|active --starfield <game dir>

Invariants:
- Imports `scripts/game/exp_install.py` unchanged and uses its own receipt `Data/FO4SFHomeWorld.install.json`
  plus `Data/FO4SFHomeWorld.swap.json` — `Data/FO4SFExp.install.json` is never written or modified.
- Unticks `FO4TerrainCore_Mars.esm` and ticks `FO4SFHome.esm` + `FO4TerrainCore_Home.esm` in `Plugins.txt`.
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
from typing import List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
GAME_SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "game"))
if GAME_SCRIPTS not in sys.path:
    sys.path.insert(0, GAME_SCRIPTS)

import deploy_starfield as deployment  # noqa: E402
import exp_install  # noqa: E402
import make_home_planet  # noqa: E402

RECORD = "FO4SFHomeWorld.install.json"
SWAP_RECORD = "FO4SFHomeWorld.swap.json"
MARS_PLUGIN = "FO4TerrainCore_Mars.esm"
HOME_REG_PLUGIN = "FO4TerrainCore_Home.esm"


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


def install(a: argparse.Namespace) -> int:
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
        return 0

    try:
        after_raw = exp_install.read_bytes(p_txt)
        after_lines, bom, nl = exp_install.plugin_lines(after_raw)
        swapped_lines, unticked = _untick_plugin_lines(after_lines, MARS_PLUGIN)
        dual_after = check_no_dual_host_active(swapped_lines)
        if dual_after:
            raise ValueError(dual_after)
        if swapped_lines != after_lines:
            exp_install.write_plugins(p_txt, swapped_lines, bom, nl, after_raw)
        swap_payload = {
            "schema": 1,
            "plugins_txt": p_txt,
            "original_plugins_b64": base64.b64encode(pre_raw).decode("ascii") if pre_raw is not None else None,
            "original_plugins_sha256": hashlib.sha256(pre_raw).hexdigest() if pre_raw is not None else None,
            "unticked": unticked,
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
    p_txt = exp_install.plugins_txt()
    lines, _, _ = exp_install.read_plugins(p_txt)
    dual_err = check_no_dual_host_active(lines)
    if dual_err:
        print(f"not ordered: {dual_err}")
        return 6
    return installer(["order", "--starfield", a.starfield]) or 0


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
