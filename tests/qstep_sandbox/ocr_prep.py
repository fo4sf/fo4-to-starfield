"""SANDBOX ONLY: copies the placeholder capture, and keeps the brightness threshold it was asked for as "ocr_th" in
the simulated game's state (fake_game.py screen: isid_lost_at)."""
import json
import os
import shutil
import sys

shutil.copyfile(sys.argv[1], sys.argv[2])
if len(sys.argv) > 3 and os.environ.get("FAKE_STATE"):
    with open(os.environ["FAKE_STATE"]) as f:
        s = json.load(f)
    s["ocr_th"] = int(sys.argv[3])
    with open(os.environ["FAKE_STATE"], "w") as f:
        json.dump(s, f, indent=1)
