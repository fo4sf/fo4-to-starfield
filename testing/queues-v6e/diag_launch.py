"""Read-only facts for a v6e launch that never became playable (doors_out, 2026-10-21): the load order with each
active plugin's masters, any master that loads after a plugin needing it, the install records cycle.ps1 orders by,
and the newest saves (the main menu's Continue loads the newest).
usage: python testing/queues-v6e/diag_launch.py --repo <checkout> --starfield <game dir>
Nothing is written."""
import argparse
import glob
import json
import os
import sys
import time

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--starfield", required=True)
a = ap.parse_args()
sys.path.insert(0, os.path.join(a.repo, "scripts", "game"))
import exp_install  # noqa: E402

data = os.path.join(a.starfield, "Data")
pt = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")
lines = [l.strip() for l in open(pt, encoding="utf-8-sig") if l.strip() and not l.startswith("#")]
active = [l[1:] for l in lines if l.startswith("*")]
print(f"Plugins.txt {pt}: {len(lines)} lines, {len(active)} active")
pos = {n.lower(): i for i, n in enumerate(active)}
for i, n in enumerate(active):
    p = os.path.join(data, n)
    try:
        m = exp_install.plugin_masters(p)
    except (OSError, ValueError) as e:
        print(f"  {i:2} {n}: masters unreadable ({e})")
        continue
    late = [x for x in m if pos.get(x.lower(), -1) > i]
    print(f"  {i:2} {n}: masters {m}" + (f"  LOADS BEFORE ITS MASTER {late}" if late else ""))
for rec in ("FO4SFExp.install.json", "FO4SFBridge.install.json", "FO4SFMapMarkers.install.json",
            "FO4Port.deploy.json"):
    p = os.path.join(data, rec)
    if os.path.exists(p):
        try:
            r = json.load(open(p, encoding="utf-8"))
            print(f"{rec}: plugins {r.get('plugins') or r.get('plugins_added')}, complete {r.get('complete')}")
        except ValueError as e:
            print(f"{rec}: unreadable ({e})")
    else:
        print(f"{rec}: none")
for base in (os.path.join(os.path.expanduser("~"), "OneDrive", "Documents"), os.path.join(os.path.expanduser("~"), "Documents")):
    saves = os.path.join(base, "My Games", "Starfield", "Saves")
    if os.path.isdir(saves):
        newest = sorted(glob.glob(os.path.join(saves, "*.sfs")), key=os.path.getmtime, reverse=True)[:6]
        print(f"newest saves in {saves}:")
        for s in newest:
            print(f"  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(s)))} {os.path.basename(s)}")
        break
