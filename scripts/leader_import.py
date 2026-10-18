"""Existing queue, install and deploy records into the leader's ledger (docs/ai/leader-core.md section 3):
python scripts\\leader_import.py --ledger C:\\Modding\\testqueue\\leader --queues C:\\Modding\\testqueue [--deploy <manifest>] [--install <record>]
A thin wrapper so `python -I` finds src/fo4sf/core/import_cli.py. Never writes to the files it reads."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.core.import_cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
