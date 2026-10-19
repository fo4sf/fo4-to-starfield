"""Keep only the OUT legs of a staged door_rounds plan whose doors stand at least MIN_M from the Red Rocket arrival.

    python scripts/bridge/door_out_legs.py <staged rounds folder> <NEW folder> <min metres>

Each OUT leg starts with a coc into its interior, so none of them goes near Red Rocket (the v6 build crashed there on
2026-10-19). The distance is the one stage wrote into the door's IN label. The new folder holds plan.json and
rounds.json renumbered, so plan-terrain and door_rounds.py judge work on it unchanged.
"""
import json
import os
import re
import sys


def main(argv=None):
    src, dst, min_m = (argv or sys.argv[1:])[:3]
    min_m = float(min_m)
    with open(os.path.join(src, "plan.json"), encoding="utf-8") as f:
        plan = json.load(f)
    with open(os.path.join(src, "rounds.json"), encoding="utf-8") as f:
        rounds = json.load(f)
    dist = {}
    for e in rounds["tests"]:
        if e["leg"] == "in":
            m = re.search(r"([0-9]+) m from the Red Rocket arrival", plan[e["test"]]["label"])
            if not m:
                sys.exit(f"test {e['test']}: no distance in its label")
            dist[e["door"]] = float(m.group(1))
    keep = [e for e in rounds["tests"] if e["leg"] == "out" and dist.get(e["door"], 0.0) >= min_m]
    os.makedirs(dst)                                      # a NEW folder only
    with open(os.path.join(dst, "plan.json"), "w", encoding="utf-8") as f:
        json.dump([plan[e["test"]] for e in keep], f, indent=1)
    with open(os.path.join(dst, "rounds.json"), "w", encoding="utf-8") as f:
        json.dump(dict(rounds, tests=[dict(e, test=i) for i, e in enumerate(keep)]), f, indent=1)
    for i, e in enumerate(keep):
        print(i, e["cell_edid"], int(dist[e["door"]]), "m")
    print(len(keep), "OUT tests kept of", sum(1 for e in rounds["tests"] if e["leg"] == "out"))


if __name__ == "__main__":
    main()
