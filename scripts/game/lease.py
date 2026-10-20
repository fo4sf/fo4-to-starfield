"""The controller lease for the game scripts (docs/ai/leader-core.md section 6): python -I scripts\\game\\lease.py ...

A thin wrapper so `python -I` (no PYTHONPATH, as cycle.ps1 and watchdog.ps1 call Python) finds
src/fo4sf/core/controller.py. Commands: claim, renew, release, status (--require OWNER exits 0 only while OWNER holds an
unexpired lease; --json for the watchdog). Nothing here touches the game.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf.core.controller import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
