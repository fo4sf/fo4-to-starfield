"""Synthetic before/after for convert_batch.py --retry-failures (docs/ai/optimization.md).

The FO4 archives and the converter are stubbed: each convert_nif call sleeps --cost seconds (default 0.085 s,
the PC's 2026-10-09 full build of 4,014 models in 311-373 s). One initial run leaves --models models staged with
--failures of them failed; each round then restores that stage and times the same rerun two ways:
  before: convert_batch.py ... (no flag, every model again)
  after:  convert_batch.py ... --retry-failures (only the failed models)
Prints the convert_nif call count and wall time of each, and the medians.

    PYTHONPATH=src python3 scripts/testing/bench_retry_failures.py [--models 200] [--failures 20] [--rounds 3]
"""
import argparse
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("convert_batch", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def run(staging, collision, names, convert, extra):
    calls = []

    def counted(name, pose=None, out_suffix=""):
        calls.append(name)
        return convert(name)
    src = SimpleNamespace(mesh_names=lambda pattern: list(names), mesh=lambda name: None)
    converter = SimpleNamespace(stats={"materials_ok": 0, "materials_fallback": 0}, _materials={},
                                material_errors={}, convert_nif=counted)
    argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging), "--content-resources", "unused",
            "--texconv", "unused", "--collision-template", str(collision), "--limit", str(len(names)), *extra]
    with ExitStack() as stack:
        for p in (patch.object(sys, "argv", argv),
                  patch.object(batch.pipeline, "Fo4Archives", return_value=src),
                  patch.object(batch.pipeline, "Converter", return_value=converter),
                  patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"),
                  patch("builtins.print")):
            stack.enter_context(p)
        start = time.perf_counter()
        batch.main()
        return len(calls), time.perf_counter() - start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=int, default=200)
    ap.add_argument("--failures", type=int, default=20)
    ap.add_argument("--cost", type=float, default=0.085, help="seconds per convert_nif call")
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()
    names = [f"meshes/bench/m{i:04d}.nif" for i in range(a.models)]
    failing = set(names[::max(1, a.models // a.failures)][:a.failures])

    def convert(name, fail=True):
        time.sleep(a.cost)
        if fail and name in failing:
            return {"ok": False, "reason": "bench: synthetic failure"}
        return {"ok": True, "out_name": Path(name).stem, "shapes": 1, "fallback_materials": 0}

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        collision = tmp / "collision.nif"
        collision.write_bytes(b"synthetic")
        initial = tmp / "initial"
        run(initial, collision, names, convert, [])
        results = {"before": [], "after": []}
        for _ in range(a.rounds):
            for label, extra in (("before", []), ("after", ["--retry-failures"])):
                stage = tmp / label
                shutil.rmtree(stage, ignore_errors=True)
                shutil.copytree(initial, stage)
                calls, secs = run(stage, collision, names, lambda n: convert(n, fail=False), extra)
                results[label].append((calls, secs))
                print(f"{label:6} convert_nif calls {calls:5}  wall {secs:7.3f} s")
        for label, rows in results.items():
            print(f"{label} median: {statistics.median(s for _, s in rows):.3f} s, calls {rows[0][0]}")


if __name__ == "__main__":
    main()
