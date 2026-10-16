"""Compare actual relaunch verification on deterministic, temporary hard links.

python scripts/testing/benchmark_relaunch.py --before <old exp_install.py> [--runs 5] [--workers 1]
Only verify_relaunch runs, with synthetic files and a temporary LOCALAPPDATA.
Never installs, launches or controls a game. JSON output includes code pins.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "scripts/game")]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(before_path, runs, workers=1):
    after_path = REPO / "scripts/game/exp_install.py"
    versions = {"before": load("relaunch_before", before_path), "after": load("relaunch_after", after_path)}
    samples = {k: [] for k in versions}
    calls = {k: [] for k in versions}
    with tempfile.TemporaryDirectory(prefix="fo4sf-relaunch-bench-") as temporary:
        root = Path(temporary)
        stage, data, local = root / "stage", root / "game/Data", root / "local"
        for p in (stage / "Data/Terrain", data / "Terrain", local / "Starfield"):
            p.mkdir(parents=True)
        for n in range(512):
            rel = Path("Terrain") / f"synthetic-{n:04d}.btd"
            source = stage / "Data" / rel
            source.write_bytes(hashlib.sha256(str(n).encode()).digest() * 2048)
            (data / rel).hardlink_to(source)
        plugin = stage / "Experiment.esm"
        plugin.write_bytes(b"SYNTHETIC BENCHMARK - NOT A GAME PLUGIN")
        (data / plugin.name).hardlink_to(plugin)
        (local / "Starfield/Plugins.txt").write_text("*Experiment.esm\n", encoding="utf-8")
        original = versions["before"]
        rec = {"files": {str(p.relative_to(data)).replace("\\", "/"): original.digest(p)
                         for p in data.rglob("*") if p.is_file()},
               "source_inputs": original.source_inventory(str(stage), [plugin.name])}
        with patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
            for round_no in range(runs + 1):
                order = list(versions.items())
                if round_no % 2:
                    order.reverse()
                for label, module in order:
                    seen = []
                    digest = module.digest

                    def counted(path):
                        seen.append(os.fspath(path))
                        return digest(path)

                    with patch.object(module, "digest", side_effect=counted):
                        start = perf_counter()
                        module.verify_relaunch(SimpleNamespace(exp_dir=str(stage), verify_workers=workers),
                                               str(data), [plugin.name], False, rec)
                        elapsed = perf_counter() - start
                    if len(seen) != 1026:
                        raise ValueError(f"{label}: expected 1026 full hashes, got {len(seen)}")
                    if round_no:  # one warm-up pair; alternate before/after order
                        samples[label].append(elapsed)
                        calls[label].append(len(seen))
    return {"loose_files": 512, "bytes_per_file": 65536, "hardlinked": True, "workers": workers,
            "runs": samples, "median_seconds": {k: median(v) for k, v in samples.items()},
            "full_hashes": calls, "runtime": sys.version, "native_input": False,
            "code_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest()
                            for k, p in (("before", before_path), ("after", after_path))}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    if not 1 <= args.runs <= 20:
        parser.error("--runs must be between 1 and 20")
    print(json.dumps(measure(args.before, args.runs, args.workers), indent=2))
