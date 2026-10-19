"""What changed between two builds' test results (docs/testing/regress.md): the queues of an old build against the
queues of a new one, matched by what each test checks rather than by its test number, so a re-planned queue still
lines up. Offline: it only reads queue folders.

usage:
  python scripts/game/regress.py --old <queue> [<queue> ...] --new <queue> [<queue> ...] [--out <report.json>]

A test's final verdict is its last row in results.jsonl. A door_rounds judge (door_rounds_judge.json) replaces the
runner's verdicts of its queue, since the runner's terrain verdict does not judge the door. Tests are matched by:
  door round legs     ("door", interior cell, leg, FO4 door src)
  every other test    (kind, cell, ref)
Each match is one of:
  regressed     PASS before, FAIL now
  lost          PASS before, INCONCLUSIVE or not run now (the proof is gone, the cause is not known)
  fixed         not PASS before, PASS now
  still_failing FAIL both times
  unchanged     the same verdict otherwise
  new / gone    only in the new / only in the old results
Exit 1 when anything regressed or was lost, else 0. A key that two tests of one side share is reported, and the
later queue on the command line wins for it.
"""
import argparse
import json
import os
import sys

PASS, FAIL = "PASS", "FAIL"


def load(p, default=None):
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def rows(qdir):
    """The parsed results.jsonl rows of a queue; torn or non-object lines are skipped."""
    out = []
    try:
        with open(os.path.join(qdir, "results.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("id"):
                    out.append(r)
    except OSError:
        pass
    return out


def results(qdir):
    """({key: {"verdict", "detail", "id", "queue"}}, build id, [duplicate keys]) for one queue."""
    q = load(os.path.join(qdir, "queue.json"), {}) or {}
    build = q.get("build_id") or ""
    out, dup = {}, []

    def put(k, v):
        if k in out:
            dup.append(k)
        out[k] = v
    judged = load(os.path.join(qdir, "door_rounds_judge.json"))
    if isinstance(judged, dict) and isinstance(judged.get("results"), list):
        for r in judged["results"]:
            k = ("door", r.get("cell_edid"), r.get("leg"), r.get("src"))
            put(k, {"verdict": r.get("verdict"), "detail": r.get("why", ""), "id": r.get("id"), "queue": qdir})
        return out, build, dup
    last = {}
    for r in rows(qdir):
        last[r["id"]] = r                                  # the last row of a test is its final verdict
    for t in q.get("tests") or []:
        r = last.get(t["id"])
        k = (t.get("kind"), t.get("cell") or "", t.get("ref") or "")
        put(k, {"verdict": r.get("verdict") if r else "NOT_RUN",
                "detail": (r.get("class", "") + " " + str(r.get("detail", ""))).strip() if r else "",
                "id": t["id"], "queue": qdir})
    return out, build, dup


def side(queues):
    out, builds, dup = {}, [], []
    for q in queues:
        r, b, d = results(q)
        dup += d + [k for k in r if k in out]
        out.update(r)
        if b and b not in builds:
            builds.append(b)
    return out, builds, dup


def classify(old, new):
    if old is None:
        return "new"
    if new is None:
        return "gone"
    o, n = old["verdict"], new["verdict"]
    if o == PASS and n == FAIL:
        return "regressed"
    if o == PASS and n != PASS:
        return "lost"
    if o != PASS and n == PASS:
        return "fixed"
    if o == FAIL and n == FAIL:
        return "still_failing"
    return "unchanged"


ORDER = ("regressed", "lost", "fixed", "still_failing", "new", "gone", "unchanged")


def diff(old_queues, new_queues):
    old, ob, od = side(old_queues)
    new, nb, nd = side(new_queues)
    groups = {g: [] for g in ORDER}
    for k in sorted(set(old) | set(new), key=lambda k: [str(x) for x in k]):
        o, n = old.get(k), new.get(k)
        groups[classify(o, n)].append({"key": list(k), "old": o and o["verdict"], "new": n and n["verdict"],
                                       "detail": (n or o)["detail"], "id": (n or o)["id"]})
    return {"old_builds": ob, "new_builds": nb, "duplicates": {"old": [list(k) for k in od], "new": [list(k) for k in nd]},
            "counts": {g: len(v) for g, v in groups.items()}, **groups}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", nargs="+", required=True)
    ap.add_argument("--new", nargs="+", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    d = diff(a.old, a.new)
    print(f"builds {','.join(d['old_builds']) or '?'} -> {','.join(d['new_builds']) or '?'}: "
          + ", ".join(f"{g} {c}" for g, c in d["counts"].items()))
    for g in ("regressed", "lost", "fixed"):
        for r in d[g]:
            print(f"  {g:9s} {' '.join(str(x) for x in r['key'])}: {r['old']} -> {r['new']} {r['detail']}")
    for s in ("old", "new"):
        if d["duplicates"][s]:
            print(f"  note: {len(d['duplicates'][s])} key(s) repeated on the {s} side; the later queue wins")
    if a.out:
        if os.path.exists(a.out):
            sys.exit(f"{a.out} exists: a new file only")
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    return 1 if d["counts"]["regressed"] or d["counts"]["lost"] else 0


if __name__ == "__main__":
    sys.exit(main())
