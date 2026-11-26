#!/usr/bin/env python3
"""Stage, verify, and fold `FO4SFCoreValues.esm` from `src/fo4sf/core/core_values.json`."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core.core_values import (  # noqa: E402
    CORE_VALUES_JSON,
    CORE_VALUES_PLUGIN,
    load_core_values,
)

PROJECT = os.path.join(ROOT, "dotnet", "CoreValues", "CoreValues.csproj")
PLAN_NAME = "core_values_plan.json"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_dotnet(args: list[str]) -> str:
    cmd = ["dotnet", "run", "--project", PROJECT, "--", *args]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"CoreValues failed ({proc.returncode}): {detail}")
    return proc.stdout


def cmd_stage(ns: argparse.Namespace) -> int:
    plugin_name, next_id, records = load_core_values(ns.json)
    out = os.path.abspath(ns.out)
    data_dir = os.path.join(out, "Data")
    os.makedirs(data_dir, exist_ok=True)
    sf_esm = os.path.join(os.path.abspath(ns.sf_data), "Starfield.esm")
    if not os.path.isfile(sf_esm):
        raise SystemExit(f"refused: missing Starfield.esm at {sf_esm}")

    opts = [
        "--json", os.path.abspath(ns.json),
        "--default-rads-rule", str(ns.default_rads_rule),
        "--default-hardcore", str(ns.default_hardcore),
        "--test-mode", str(ns.test_mode),
        "--commonwealth-weather", str(ns.commonwealth_weather),
        "--fo4-10mm", str(ns.fo4_10mm),
        "--fo4-p5-weapons", str(ns.fo4_p5_weapons),
        "--fo4-arsenal", str(ns.fo4_arsenal),
    ]
    _run_dotnet(["build", sf_esm, data_dir, *opts])
    esm_path = os.path.join(data_dir, plugin_name)
    _run_dotnet(["check", esm_path, sf_esm, *opts])

    plan = {
        "plugin": plugin_name,
        "next_form_id": f"0x{next_id:06X}",
        "record_count": len(records),
        "default_rads_rule": ns.default_rads_rule,
        "default_hardcore": ns.default_hardcore,
        "test_mode": ns.test_mode,
        "commonwealth_weather": ns.commonwealth_weather,
        "fo4_10mm": ns.fo4_10mm,
        "fo4_p5_weapons": ns.fo4_p5_weapons,
        "fo4_arsenal": ns.fo4_arsenal,
        "plugin_sha256": _sha256(esm_path),
        "schema_sha256": _sha256(ns.json),
    }
    with open(os.path.join(out, PLAN_NAME), "w", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"staged {plugin_name} ({len(records)} records, test_mode={ns.test_mode})")
    return 0


def cmd_verify(ns: argparse.Namespace) -> int:
    stage = os.path.abspath(ns.stage)
    plan_path = os.path.join(stage, PLAN_NAME)
    if not os.path.isfile(plan_path):
        raise SystemExit(f"refused: missing {PLAN_NAME} in {stage}")
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    plugin_name, _, records = load_core_values(ns.json)
    esm_path = os.path.join(stage, "Data", plugin_name)
    if not os.path.isfile(esm_path):
        raise SystemExit(f"refused: missing {plugin_name} in {stage}")
    with open(esm_path, "rb") as handle:
        magic = handle.read(4)
    if magic != b"TES4":
        raise SystemExit(f"refused: {plugin_name} does not start with TES4")
    if _sha256(esm_path) != plan.get("plugin_sha256"):
        raise SystemExit(f"refused: {plugin_name} sha256 does not match {PLAN_NAME}")
    if plan.get("record_count") != len(records):
        raise SystemExit("refused: record_count mismatch against core_values.json")
    if ns.sf_data:
        sf_esm = os.path.join(os.path.abspath(ns.sf_data), "Starfield.esm")
        opts = [
            "--json", os.path.abspath(ns.json),
            "--default-rads-rule", str(plan.get("default_rads_rule", 0)),
            "--default-hardcore", str(plan.get("default_hardcore", 0)),
            "--test-mode", str(plan.get("test_mode", 0)),
            "--commonwealth-weather", str(plan.get("commonwealth_weather", 1)),
            "--fo4-10mm", str(plan.get("fo4_10mm", 1)),
            "--fo4-p5-weapons", str(plan.get("fo4_p5_weapons", 1)),
            "--fo4-arsenal", str(plan.get("fo4_arsenal", 1)),
        ]
        _run_dotnet(["check", esm_path, sf_esm, *opts])
    print(f"verify: ok ({plugin_name})")
    return 0


def cmd_fold(ns: argparse.Namespace) -> int:
    cmd_verify(argparse.Namespace(stage=ns.stage, json=ns.json, sf_data=None))
    src = os.path.join(os.path.abspath(ns.stage), "Data", CORE_VALUES_PLUGIN)
    dst_data = os.path.join(os.path.abspath(ns.into), "Data")
    os.makedirs(dst_data, exist_ok=True)
    shutil.copy2(src, os.path.join(dst_data, CORE_VALUES_PLUGIN))
    print(f"folded {CORE_VALUES_PLUGIN} into {ns.into}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stage")
    st.add_argument("--sf-data", required=True)
    st.add_argument("--out", required=True)
    st.add_argument("--json", default=CORE_VALUES_JSON)
    st.add_argument("--default-rads-rule", type=int, choices=(0, 1), default=0)
    st.add_argument("--default-hardcore", type=int, choices=(0, 1), default=0)
    st.add_argument("--test-mode", type=int, choices=(0, 1), default=0)
    st.add_argument("--commonwealth-weather", type=int, choices=(0, 1), default=1)
    st.add_argument("--fo4-10mm", nargs="?", const=1, type=int, choices=(0, 1), default=1)
    st.add_argument("--fo4-p5-weapons", nargs="?", const=1, type=int, choices=(0, 1), default=1)
    st.add_argument("--fo4-arsenal", nargs="?", const=1, type=int, choices=(0, 1), default=1)
    st.set_defaults(func=cmd_stage)

    vr = sub.add_parser("verify")
    vr.add_argument("--stage", required=True)
    vr.add_argument("--sf-data", default=None)
    vr.add_argument("--json", default=CORE_VALUES_JSON)
    vr.set_defaults(func=cmd_verify)

    fd = sub.add_parser("fold")
    fd.add_argument("--stage", required=True)
    fd.add_argument("--into", required=True)
    fd.add_argument("--json", default=CORE_VALUES_JSON)
    fd.set_defaults(func=cmd_fold)
    return p


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    raise SystemExit(main())
