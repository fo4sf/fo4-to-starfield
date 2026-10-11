"""How many screenshot+OCR rounds route_run.ps1 spent looking for the activation prompt, per door route.

usage: python prompt_rounds.py <run dir> [<run dir> ...]
Runs made with prompt memory record `prompt_rounds` (and `prompt_pitch`, `pitch_source`) in results.jsonl. Older
runs did not, but the runner overwrote r<k>_pre.png once per round, so that file's creation time is the first round
and its last write the last one: rounds = 1 + round(span / seconds per round). The seconds per round come from the
run's own full sweeps (prompt false: 9 rounds, 8 tilts, span / 8) when it has any, else ROUND_SECONDS.
Prints one line per door route, a summary per run and a total: door routes, rounds, rounds beyond the first (what a
remembered pitch could save), and seconds.
"""
import json
import os
import re
import sys

ROUND_SECONDS = 2.07   # shot + prompt_visible.py + 150-count tilt + 450 ms wait; 2026-10-09 full sweeps: 16.5 s / 8
MAX_ROUNDS = 9         # route_run.ps1 sweep length


def read_results(path):
    with open(path, encoding="utf-8-sig") as f:
        return [json.loads(line) for line in f if line.strip()]


def pre_spans(run_dir):
    """{route index: seconds between the first and the last write of r<k>_pre.png}."""
    spans = {}
    for name in os.listdir(run_dir):
        m = re.fullmatch(r"r(\d+)_pre\.png", name)
        if not m:
            continue
        st = os.stat(os.path.join(run_dir, name))
        created = getattr(st, "st_birthtime", st.st_ctime)   # Windows: creation time either way
        spans[int(m.group(1))] = max(0.0, st.st_mtime - created)
    return spans


def round_seconds(results, spans, default=ROUND_SECONDS):
    """Seconds per round from this run's full sweeps (prompt never seen: 9 rounds), else the default."""
    full = [spans[r["index"]] for r in results
            if r.get("prompt") is False and r.get("index") in spans and spans[r["index"]] > 0]
    if not full:
        return default
    return sum(full) / len(full) / (MAX_ROUNDS - 1)


def rounds(results, spans, seconds):
    """One row per door route that searched for the prompt (skipped routes never did)."""
    rows = []
    for r in results:
        if r.get("kind") != "door" or r.get("prompt") is None:
            continue
        index = r.get("index")
        if isinstance(r.get("prompt_rounds"), int):
            n, source = r["prompt_rounds"], "recorded"
        elif index in spans:
            n, source = 1 + int(round(spans[index] / seconds)), "timestamps"
        else:
            n, source = None, "unknown"
        rows.append({"index": index, "ref": r.get("ref"), "prompt": r.get("prompt"), "rounds": n, "source": source,
                     "pitch": r.get("prompt_pitch"), "pitch_source": r.get("pitch_source")})
    return rows


def summary(rows, seconds):
    counted = [row["rounds"] for row in rows if row["rounds"] is not None]
    histogram = {}
    for n in counted:
        histogram[n] = histogram.get(n, 0) + 1
    found = [row["rounds"] for row in rows if row["rounds"] is not None and row["prompt"]]
    return {"door_routes": len(rows), "counted": len(counted), "rounds": sum(counted),
            "beyond_first": sum(n - 1 for n in found), "no_prompt": sum(1 for row in rows if row["prompt"] is False),
            "histogram": dict(sorted(histogram.items())), "seconds": round(sum(counted) * seconds, 1)}


def report(run_dir):
    results = read_results(os.path.join(run_dir, "results.jsonl"))
    spans = pre_spans(run_dir)
    seconds = round_seconds(results, spans)
    rows = rounds(results, spans, seconds)
    return rows, summary(rows, seconds), seconds


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    total = {"door_routes": 0, "counted": 0, "rounds": 0, "beyond_first": 0, "no_prompt": 0, "seconds": 0.0}
    for run_dir in argv:
        rows, s, seconds = report(run_dir)
        print(f"== {run_dir}  ({seconds:.2f} s per round)")
        for row in rows:
            n = "?" if row["rounds"] is None else row["rounds"]
            extra = f" pitch {row['pitch']} ({row['pitch_source']})" if row["pitch"] is not None else ""
            print(f"  r{row['index']:<3} {row['ref']:<22} prompt={str(row['prompt']):<5} rounds={n:<2} {row['source']}{extra}")
        print(f"  door routes {s['door_routes']}, counted {s['counted']}, rounds {s['rounds']} "
              f"(beyond the first {s['beyond_first']}, no prompt {s['no_prompt']}), histogram {s['histogram']}, "
              f"~{s['seconds']} s")
        for key in total:
            total[key] += s[key]
    if len(argv) > 1:
        print(f"== total: door routes {total['door_routes']}, counted {total['counted']}, rounds {total['rounds']} "
              f"(beyond the first {total['beyond_first']}, no prompt {total['no_prompt']}), ~{total['seconds']:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
