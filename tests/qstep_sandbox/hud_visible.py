"""SANDBOX ONLY: the simulated HUD is up, except during a simulated load (fake_game.py loading_until)."""
import json
import os
import time

up = True
try:
    with open(os.environ["FAKE_STATE"]) as f:
        up = float(json.load(f).get("loading_until") or 0) <= time.time()
except (KeyError, OSError, ValueError):
    pass
print("yes" if up else "no")
