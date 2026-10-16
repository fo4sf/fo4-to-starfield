"""Pick probe points from an exported FO4 cell: floor-like pieces, converted to Starfield metres. Writes 'x y z name' lines.
usage: probe_points.py <cell.json> <out.txt> [max_points=40]"""
import json
import random
import re
import sys

cell = json.load(open(sys.argv[1], encoding="utf-8-sig"))
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
pts = []
for r in cell["refs"]:
    m = r.get("model") or ""
    base = m.rsplit("\\", 1)[-1]
    # match the FILE name: the folder "Small_FloorCeilKit" made ceiling-only pieces look like floors (test queue
    # 2026-10-11: a drop onto BldDecoSmCeilOnly03 fell one storey); "Flr" is the kit's own floor abbreviation
    walkable = re.search(r"floor|flr|stair|ramp|walkway|catwalk|plat", base, re.I)
    # ceiling or wall pieces only count when the name also says floor or stairs (BldWlpSmFlrCeil01 is a floor)
    not_floor = re.search(r"ceil|wall", base, re.I) and not re.search(r"floor|flr|stair", base, re.I)
    if r["type"] in ("Static", "MovableStatic") and walkable and not not_floor:
        x, y, z = (v / 70.0 for v in r["pos"])
        pts.append((x, y, z, m.rsplit("\\", 1)[-1]))
random.seed(1)
random.shuffle(pts)
# spread: drop points within 2 m of an already chosen one
chosen = []
for p in pts:
    if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 > 4 for q in chosen):
        chosen.append(p)
    if len(chosen) >= limit:
        break
with open(sys.argv[2], "w") as f:
    for x, y, z, n in chosen:
        f.write(f"{x:.2f} {y:.2f} {z:.2f} {n}\n")
print(len(chosen), "probe points from", len(pts), "floor-like refs")
