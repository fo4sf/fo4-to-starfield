#!/usr/bin/env python3
"""Run Mutagen C# writer self-tests locally across all FO4SF plugin writers.

GitHub Actions CI (`ubuntu-24.04`) runs Python unit tests and `scripts/guard.py`
only and does not install a .NET SDK. Run this script on the build PC before
posting or folding a phase and include its summary output in the PR report.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

WRITER_PROJECTS = (
    "CoreValues",
    "NewGame",
    "RadsCore",
    "HardcoreToggle",
    "WorkshopCore",
    "PowerArmorCore",
    "ProgressionCore",
    "ListDialogue",
    "CombatCore",
    "ReputationCore",
    "CompanionsCore",
    "ALife",
    "FortHagen",
    "Mission",
    "RouteLoot",
    "CoreCandidate",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--writers",
        default=",".join(WRITER_PROJECTS),
        help="Comma-separated list of dotnet/<Writer> project names to run.",
    )
    ns = parser.parse_args(argv)

    if not shutil.which("dotnet"):
        print("refused: dotnet SDK not found on PATH", file=sys.stderr)
        return 2

    selected = [w.strip() for w in ns.writers.split(",") if w.strip()]
    failures = 0
    print(f"Running {len(selected)} C# writer selftests...")
    for name in selected:
        csproj = os.path.join(ROOT, "dotnet", name, f"{name}.csproj")
        if not os.path.isfile(csproj):
            print(f"SKIP  {name:<18} (missing {name}.csproj)")
            continue
        t0 = time.monotonic()
        with tempfile.TemporaryDirectory(prefix=f"fo4sf-selftest-{name.lower()}-") as scratch:
            proc = subprocess.run(
                ["dotnet", "run", "--project", csproj, "--", "selftest", scratch],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        dt = time.monotonic() - t0
        if proc.returncode == 0:
            print(f"PASS  {name:<18} ({dt:.1f}s)")
        else:
            failures += 1
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            tail = detail[-1] if detail else "failed"
            print(f"FAIL  {name:<18} ({dt:.1f}s): {tail}")

    print(f"Summary: {len(selected) - failures}/{len(selected)} writer selftests passed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
