"""SANDBOX ONLY: an activation prompt shows when a load door without the automatic flag is within 2.5 m of the
simulated player (fake_game.py doors), in the same cell, outside a load."""
import json
import math
import os
import time

yes = False
try:
    with open(os.environ["FAKE_STATE"]) as f:
        s = json.load(f)
    p = s["player"]
    if float(s.get("loading_until") or 0) <= time.time():
        yes = any(not d.get("auto") and (d.get("cell") or "").lower() == (s.get("cell") or "").lower()
                  and math.dist(p, d["pos"]) <= 2.5 for d in s.get("doors", []))
except (KeyError, OSError, ValueError):
    pass
print("yes" if yes else "no")
