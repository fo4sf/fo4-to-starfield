"""The owner's eight-bullet work-period report from the leader's ledger (docs/ai/leader-core.md §8):
python scripts\\leader_report.py --ledger C:\\Modding\\testqueue\\leader [--now <ISO>] [--json]
A thin wrapper so `python -I` finds src/fo4sf/core/report.py. Read-only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.core.report import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
