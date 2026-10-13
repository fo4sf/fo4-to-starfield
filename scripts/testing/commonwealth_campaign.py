"""Prepare offline, pinned core64c phase queues. Never installs, launches or queues a game.

prepare --source-queue <queue.json> --runner <reviewed checkout> --out <new folder>
verify  --campaign <folder>  (exit 0 means inputs/queues unchanged, NOT runtime acceptance)
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


PLUGINS = ("FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm")
METADATA = ("plan.json", "expected.json", "offline_check.json", "data_manifest.json",
            "objects.json", "formids.json", "overlays_params.json", "skipped.json")
MAX_MOVE_M = 200.0  # supported by the teleport audit on PR #76, not an engine guarantee
MAX_NEARBY_RADIUS_M = 510.0
PHASES = (
    ("01-smoke", ((0, 3), (1, 4)), "loading and repeated Sanctuary roof", True),
    ("02-nearby-baseline", ((0, None), (1, None)), "terrain and roofs around Red Rocket", True),
    ("03-informational", ((2, None),), "known obstructed probes; inspect point by point", False),
)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_pinned(path):
    raw = Path(path).read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def match_plan(source, plan):
    tests = source.get("tests") or []
    if len(plan) != len(tests) or any(
            t.get("world_coc") != p.get("coc") or any(t.get(k) != p.get(k) for k in
            ("points", "spawn_local", "z_ref", "drop_z", "settle_ms", "hop_m", "hop_wait_ms"))
            for t, p in zip(tests, plan)):
        raise ValueError("source queue differs from the staged terrain plan")


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stat_id(path):
    s = Path(path).stat()
    return [s.st_size, s.st_mtime_ns]


def plain_file(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or linked file: {path}")
    return path


def tree_files(root):
    """Only enumerate real files, refusing directory symlinks/junctions as well."""
    if not root.is_dir() or root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
        raise ValueError(f"missing or linked tree: {root}")
    files = []
    for base, dirs, names in os.walk(root):
        for name in dirs:
            p = Path(base) / name
            if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                raise ValueError(f"linked directory: {p}")
        files.extend(plain_file(Path(base) / name) for name in names)
    return sorted(files)


def relative_file(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or ".." in rel.parts or "\\" in name or ":" in name:
        raise ValueError(f"unsafe relative path: {name}")
    p = root.joinpath(*rel.parts)
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes input root: {name}")
    return plain_file(p)


def checked_tree(exp):
    report, manifest = load(exp / "offline_check.json"), load(exp / "data_manifest.json")
    checks = report.get("checks") or []
    if report.get("pass") is not True or manifest.get("pass") is not True or not checks \
            or any(len(c) != 2 or c[1] is not True for c in checks):
        raise ValueError("exterior offline check is missing or failed")
    actual = {p.relative_to(exp).as_posix(): stat_id(p) for p in tree_files(exp / "Data")}
    actual.update({name: stat_id(plain_file(exp / name)) for name in PLUGINS})
    if actual != manifest.get("files"):
        raise ValueError("exterior is not the tree recorded by its offline check")
    return actual


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_route(test):
    """qstep moves x, then y; no unchecked auto hops or final 'beyond' jump."""
    points = test.get("points") or []
    start = test.get("spawn_local") or []
    hop = test.get("hop_m")
    if len(start) != 3 or not all(finite_number(x) for x in start) or not points \
            or not finite_number(hop) or not 0 < hop <= MAX_MOVE_M:
        raise ValueError("route needs finite spawn_local, points and hop_m <= 200")
    if points[0].get("label") != test.get("z_ref"):
        raise ValueError("first point must be the measured z_ref")
    if test.get("travel") or test.get("anchor") or test.get("drop_above_spawn"):
        raise ValueError("core64c campaign requires spawn-local COC setup without a fixed load-order anchor")
    if not finite_number(test.get("drop_z")):
        raise ValueError("missing drop height")
    labels = set()
    for p in points:
        label = p.get("label")
        if not isinstance(label, str) or not label or label in labels \
                or not all(finite_number(p.get(k)) for k in ("x", "y", "expect")):
            raise ValueError("point labels must be unique and coordinates/heights finite")
        labels.add(label)
    final = test.get("beyond") or {}
    if not all(finite_number(final.get(k)) for k in ("x", "y")):
        raise ValueError("missing final diagnostic position")
    prev = start[:2]
    longest = 0.0
    for p in [*points, final]:
        dx, dy = p["x"] - prev[0], p["y"] - prev[1]
        longest = max(longest, abs(dx), abs(dy))
        if max(abs(dx), abs(dy)) > MAX_MOVE_M or math.hypot(dx, dy) > hop:
            raise ValueError("route contains a move over 200m per axis or an unverified automatic hop")
        prev = [p["x"], p["y"]]
    return round(longest, 4)


def phase_queues(source):
    tests = source.get("tests") or []
    if len(tests) != 3 or len({t.get("id") for t in tests}) != 3 \
            or any(t.get("kind") != "terrain" or t.get("world_coc") != "FO4Core_RedRocketSpawn" for t in tests):
        raise ValueError("expected core64c's three terrain entries; re-plan changed experiments explicitly")
    roofs = {p.get("label") for p in tests[1].get("points", [])}
    if not {"sanctuary_house_roof", "sanctuary_house_roof_again", "redrocket_roof",
            "redrocket_roof_again", "concord_museum_roof", "concord_museum_roof_again"} <= roofs:
        raise ValueError("object entry lacks the three repeated source-verified roofs")
    for t, labels in ((tests[0], [tests[0].get("z_ref"), "wp_01", "w_200m"]),
                      (tests[1], [tests[1].get("z_ref"), "wp_01", "sanctuary_house_roof", "sanctuary_house_roof_again"])):
        if [p.get("label") for p in t["points"][:len(labels)]] != labels:
            raise ValueError("smoke prefix no longer matches its terrain/Sanctuary purpose; explicitly re-plan")
    for t in tests:
        # Validate the declared nearby scope as well as the retained phase routes.
        start = t.get("spawn_local") or []
        if len(start) != 3 or not all(finite_number(x) for x in start):
            raise ValueError("missing finite spawn-local frame")
        for p in t.get("points") or []:
            if not all(finite_number(p.get(k)) for k in ("x", "y", "expect")) or \
                    math.hypot(p["x"] - start[0], p["y"] - start[1]) > MAX_NEARBY_RADIUS_M:
                raise ValueError("source points are nonfinite or outside the 510m nearby scope")
    for label in ("sanctuary_house_roof", "redrocket_roof", "concord_museum_roof"):
        pts = tests[1]["points"]
        index = next(i for i, p in enumerate(pts) if p["label"] == label)
        if index + 1 >= len(pts) or pts[index + 1]["label"] != label + "_again" or any(
                pts[index][k] != pts[index + 1][k] for k in ("x", "y", "expect")):
            raise ValueError("roof repeats must be consecutive drops on the same surface")
    out = []
    for name, selected, purpose, required in PHASES:
        q = copy.deepcopy(source)
        q["tests"] = []
        mappings = []
        for index, count in selected:
            t = copy.deepcopy(tests[index])
            if count and len(t["points"]) < count:
                raise ValueError("source entry is too short for the smoke prefix")
            t["points"] = t["points"][:count] if count else t["points"]
            t["id"] = f"{name}_{t['id']}"
            t["fresh"] = True
            last = t["points"][-1]
            t["beyond"] = {"x": last["x"], "y": last["y"]}
            longest = validate_route(t)
            mappings.append({"id": t["id"], "source_id": tests[index]["id"], "prefix_points": len(t["points"]),
                             "max_axis_move_m": longest})
            q["tests"].append(t)
        points = sum(len(t["points"]) for t in q["tests"])
        # Observed exterior runs: 75-115s/point. Reserve 120s/fresh entry for launch/arrival.
        # These are planning estimates, not step timeouts or measured campaign results.
        estimates = [round((points * rate + 120 * len(q["tests"])) / 60, 1) for rate in (75, 115)]
        out.append((name, q, {"purpose": purpose, "acceptance_gate": required, "source_tests": mappings,
                            "points": points, "estimated_active_minutes": estimates,
                            "estimate_basis": "75-115s/point plus 120s/fresh entry; waits/retries extra"}))
    return out


def input_files(source_queue, source, runner):
    exp, staging = Path(source["experiment"]).resolve(), Path(source["staging"]).resolve()
    files = {"source": [plain_file(source_queue)],
             "experiment": [relative_file(exp, n) for n in (*PLUGINS, *METADATA)] + tree_files(exp / "Data"),
             "staging": [plain_file(staging / "FO4Port.esm"), plain_file(staging / "FO4Port - Main.ba2"),
                         plain_file(staging / "FO4Port - Textures.ba2"), plain_file(staging / "formids.json"),
                         plain_file(staging / "manifest.json")],
             "runner": tree_files(runner / "scripts" / "game")}
    # Python bytecode is not runner source and may be regenerated during read-only imports.
    files["runner"] = [p for p in files["runner"] if p.suffix in (".py", ".ps1")]
    roots = {"source": source_queue.parent, "experiment": exp, "staging": staging, "runner": runner}
    return roots, files


def snapshot(roots, files, progress=None):
    out = {}
    for label, paths in files.items():
        out[label] = {}
        for index, p in enumerate(paths, 1):
            before = stat_id(p)
            sha = digest(p)
            if before != stat_id(p):
                raise ValueError(f"input changed while hashing: {p}")
            out[label][p.relative_to(roots[label]).as_posix()] = {"bytes": before[0], "sha256": sha}
            if progress and (index % 10000 == 0 or index == len(paths)):
                progress(f"Hashed {label}: {index:,}/{len(paths):,} files")
    return out


def regional_targets(objects, expected, offline):
    """Cell-level coverage candidates only: a cell centre is NOT a verified landing point."""
    counts, risks = Counter(), Counter()
    bases = objects.get("bases") or []
    refs = objects.get("refs") or []
    for ref in refs:
        cell, index = ref.get("cell"), ref.get("base")
        if not isinstance(cell, list) or len(cell) != 2 or any(type(v) is not int for v in cell) \
                or type(index) is not int or not 0 <= index < len(bases):
            raise ValueError("invalid exterior cell/base identity")
        key = tuple(cell)
        counts[key] += 1
        if bases[index].get("collision") in ("guessed-boxes", "rigged-door-box"):
            risks[key] += 1
    if len(refs) != expected.get("objects", {}).get("placed") or len(counts) != offline.get("cells", {}).get("with_refs"):
        raise ValueError("regional inventory differs from offline placed-reference/cell counts")
    by_region = defaultdict(list)
    for cell in counts:
        by_region[(cell[0] // 16, cell[1] // 16)].append(cell)
    regions = []
    for region, cells in sorted(by_region.items()):
        dense = min(cells, key=lambda c: (-counts[c], c))
        risk = min(cells, key=lambda c: (-risks[c], -counts[c], c))
        edge = min(cells, key=lambda c: (min(c[0] % 16, 15 - c[0] % 16, c[1] % 16, 15 - c[1] % 16),
                                         -counts[c], c))
        selected = defaultdict(list)
        for cell, reason in ((dense, "densest"), (risk, "collision-risk"), (edge, "near-region-edge")):
            selected[cell].append(reason)
        regions.append({"region": list(region), "refs": sum(counts[c] for c in cells), "populated_cells": len(cells),
                        "candidates": [{"cell": list(c), "refs": counts[c], "risk_refs": risks[c], "reasons": reasons}
                                       for c, reasons in sorted(selected.items())]})
    return {"region_width_cells": 16, "regions": regions, "populated_cells": len(counts),
            "densest_cells": [{"cell": list(c), "refs": counts[c]} for c in
                              sorted(counts, key=lambda c: (-counts[c], c))[:5]],
            "status": "blocked: needs verified arrival anchors, surfaces and short setup routes; no runnable regional queues"}


def prepare(source_queue, runner, out, progress=None):
    source_queue, runner, out = source_queue.resolve(), runner.resolve(), out.resolve()
    if out.exists():
        raise ValueError("campaign output already exists; use a new folder to preserve results")
    source, source_sha = load_pinned(source_queue)
    roots, files = input_files(source_queue, source, runner)
    if any(out.is_relative_to(root) or root.is_relative_to(out) for root in roots.values()):
        raise ValueError("campaign output must be separate from every input root")
    checked = checked_tree(roots["experiment"])
    plan, plan_sha = load_pinned(roots["experiment"] / "plan.json")
    match_plan(source, plan)
    if digest(roots["staging"] / "FO4Port.esm") != source.get("plugin_sha256"):
        raise ValueError("source queue's interior build pin differs from staging")
    phases = phase_queues(source)
    pins = snapshot(roots, files, progress)
    if checked != checked_tree(roots["experiment"]):
        raise ValueError("exterior changed while preparing campaign")
    if source_sha != pins["source"][source_queue.name]["sha256"] or source_sha != digest(source_queue):
        raise ValueError("source queue changed while preparing campaign")
    expected, expected_sha = load_pinned(roots["experiment"] / "expected.json")
    offline, offline_sha = load_pinned(roots["experiment"] / "offline_check.json")
    objects, objects_sha = load_pinned(roots["experiment"] / "objects.json")
    regions = regional_targets(objects, expected, offline)
    for name, parsed_sha in (("expected.json", expected_sha), ("offline_check.json", offline_sha),
                             ("objects.json", objects_sha), ("plan.json", plan_sha)):
        if parsed_sha != pins["experiment"][name]["sha256"] or digest(roots["experiment"] / name) != parsed_sha:
            raise ValueError(f"parsed metadata changed while preparing campaign: {name}")
    proc = subprocess.run(["git", "-C", str(runner), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    manifest = {"version": 1, "created": datetime.now(timezone.utc).isoformat(), "runtime_accepted": False,
                "roots": {k: str(v) for k, v in roots.items()}, "source_queue": source_queue.name,
                "runner_commit": proc.stdout.strip(), "source_queue_commit": source.get("commit"),
                "build_id": source.get("build_id"), "pins": pins, "phases": {},
                "coverage": {"placed_refs": expected.get("objects", {}).get("placed"),
                             "cells": offline.get("cells"), "runtime_probe_radius_m": 510,
                             "limitation": "nearby probes do not accept the whole staged Commonwealth"},
                "regional_selection": regions,
                "blocked_followups": [
                    "continuous bidirectional Red Rocket-Sanctuary bridge/cell-border walk: source-surface checkpoints and runner needed",
                    "same-build source-linked cave/Vault111 entry-return-save: core64c currently has no connected interior slice",
                    "regional/dense-cell/edge queues: verified arrival anchors, collision/BTD expectations and bounded setup routes needed"],
                "operator_gates": [
                    "review terrain PR #76 and integrate a runner including budget-pause fix #89 and reviewed installer #83",
                    "one live controller, owner idle/STOP/Guardian controls; verify campaign before each run",
                    "uninstall conflicting Mars/core64-family experiment using its recovery receipt; never overwrite it",
                    "build and verify installed archives/plugins and capture their hashes/load order before judging",
                    "run smoke then inspect all point captures before baseline; diagnostic queue is informational",
                    "capture lighting/visual quality in daylight separately; old queue has no daylight feature"],
                "identity_notes": "interior build_id is not exterior identity; exterior plugins/Data/formids are independently hashed"}
    out.mkdir(parents=True, exist_ok=False)
    for name, q, details in phases:
        folder = out / name
        folder.mkdir()
        write(folder / "queue.json", q)
        manifest["phases"][name] = {**details, "queue_sha256": digest(folder / "queue.json")}
    write(out / "campaign.json", manifest)
    (out / "README.txt").write_text(
        "Prepared offline. NOT scheduled, deployed or runtime accepted.\n"
        "Verify inputs/queues before each phase: commonwealth_campaign.py verify --campaign <this folder>\n"
        "Live operator: adopt reviewed runner/installer and check campaign.json operator_gates first.\n"
        "Run each phase separately through testqueue.py run --queue <phase> --max-hours 2 --wait-for-idle --refocus.\n"
        "Do not automatically chain later phases; inspect smoke/baseline captures first.\n"
        "A zero runner exit means terminal results, not all PASS. Exit4 retains unfinished work.\n"
        "Keep runs/observations and report with each phase, never combine different input hashes.\n"
        "03-informational is expected to contain HEIGHTS failures; it cannot approve terrain or walking.\n"
        "Never treat COC/hops as normal travel. Connected walks/doors and distant regions remain unplanned.\n",
        encoding="utf-8")
    return manifest


def verify(out, progress=None):
    m = load(out / "campaign.json")
    if m.get("version") != 1:
        raise ValueError("unsupported campaign version")
    roots = {k: Path(v).resolve() for k, v in m["roots"].items()}
    source_queue = relative_file(roots["source"], m["source_queue"])
    source, source_sha = load_pinned(source_queue)
    if source_sha != m["pins"]["source"][m["source_queue"]]["sha256"]:
        raise ValueError("source queue contents changed")
    if Path(source["experiment"]).resolve() != roots["experiment"] or Path(source["staging"]).resolve() != roots["staging"]:
        raise ValueError("queue roots differ from campaign")
    _, current = input_files(source_queue, source, roots["runner"])
    for label, paths in current.items():
        if {p.relative_to(roots[label]).as_posix() for p in paths} != set(m["pins"][label]):
            raise ValueError(f"{label} input inventory changed")
    checked_tree(roots["experiment"])
    if snapshot(roots, current, progress) != m["pins"]:
        raise ValueError("campaign input contents changed; prepare a new campaign")
    proc = subprocess.run(["git", "-C", str(roots["runner"]), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True)
    if proc.stdout.strip() != m["runner_commit"]:
        raise ValueError("runner revision changed; prepare a new campaign")
    parsed = {}
    for name in ("plan.json", "expected.json", "offline_check.json", "objects.json"):
        value, parsed_sha = load_pinned(roots["experiment"] / name)
        if parsed_sha != m["pins"]["experiment"][name]["sha256"]:
            raise ValueError(f"parsed metadata differs from campaign: {name}")
        parsed[name] = value
    match_plan(source, parsed["plan.json"])
    expected_regions = regional_targets(parsed["objects.json"], parsed["expected.json"], parsed["offline_check.json"])
    if expected_regions != m.get("regional_selection"):
        raise ValueError("regional selection changed or missing")
    if m.get("runtime_accepted") is not False or set(m["phases"]) != {p[0] for p in PHASES}:
        raise ValueError("campaign phase/acceptance status changed")
    for name, expected, details in phase_queues(source):
        queue = relative_file(out, name + "/queue.json")
        if digest(queue) != m["phases"][name]["queue_sha256"] or load(queue) != expected:
            raise ValueError(f"phase queue changed: {name}")
        if {k: v for k, v in m["phases"][name].items() if k != "queue_sha256"} != details:
            raise ValueError(f"phase purpose/gate/estimate changed: {name}")
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--source-queue", type=Path, required=True)
    p.add_argument("--runner", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("verify")
    p.add_argument("--campaign", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        progress = lambda message: print(message, flush=True)
        m = prepare(a.source_queue, a.runner, a.out, progress) if a.command == "prepare" else verify(a.campaign, progress)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as e:
        print(f"campaign refused: {e}", file=sys.stderr)
        return 1
    print(f"{'Prepared' if a.command == 'prepare' else 'Integrity verified'}; runtime acceptance remains open")
    for name, p in m["phases"].items():
        print(f"{name}: {p['points']} points, {p['estimated_active_minutes']} active minutes; waits/retries extra")
    return 0


if __name__ == "__main__":
    sys.exit(main())
