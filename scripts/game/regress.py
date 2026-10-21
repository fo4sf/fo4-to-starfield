"""What changed between two builds' test results (docs/testing/regress.md): the queues of an old build against the
queues of a new one, matched by what each test checks rather than by its test number, so a re-planned queue still
lines up. Offline: it only reads queue folders.

usage:
  python scripts/game/regress.py --old <queue> [<queue> ...] --new <queue> [<queue> ...] [--out <report.json>]

A test's final verdict is its last row in results.jsonl. A door_rounds judge (door_rounds_judge.json) replaces the
runner's verdicts of its queue, since the runner's terrain verdict does not judge the door; its rows for tests the queue
does not hold are left out, and a judge older than the queue's newest attempt of a test is refused (exit 2). Tests are matched by:
  door round legs     ("door", interior cell, leg, FO4 door src)
  terrain tests       ("terrain", "", coc, side, label): several walks can start from one coc
  every other test    (kind, cell, ref, side): a door's two sides are two tests
Each match is one of:
  regressed     PASS before, FAIL now
  lost          PASS before, INCONCLUSIVE or not run now (the proof is gone, the cause is not known)
  new_failure   INCONCLUSIVE or not run before, FAIL now
  fixed         not PASS before, PASS now
  still_failing FAIL both times
  changed       any other change of verdict (FAIL to INCONCLUSIVE, NOT_RUN to INCONCLUSIVE, ...)
  unchanged     the same verdict
  new / gone    only in the new / only in the old results
Every group but unchanged, new and gone is printed. Exit 1 when anything regressed, was lost or newly failed, else 0.
A key that tests of two queues on one side share is reported, and the later queue on the command line wins for it.
Exit 2, with no report, when a queue cannot be read as evidence: a key repeated inside one queue (two tests the
match can not tell apart), a missing or unreadable queue.json (no "tests" list), an unreadable door_rounds_judge.json, or a door rounds queue
(tests labelled "door round N ...", or an experiment folder holding rounds.json) that has not been judged yet
(scripts/bridge/door_rounds.py judge): the runner's terrain verdicts never stand in for a door's.
"""
import argparse
import json
import os
import sys

PASS, FAIL = "PASS", "FAIL"


class Unavailable(Exception):
    """A queue whose evidence cannot be read: compared, it would read as an empty or wrong side."""


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


def latest_attempt(qdir, test_id):
    """The newest attempt folder name (aN) of a test, as door_rounds.py judge records it, else None."""
    d = os.path.join(qdir, "tests", test_id)
    tries = sorted((int(n[1:]), n) for n in (os.listdir(d) if os.path.isdir(d) else [])
                   if n.startswith("a") and n[1:].isdigit())
    return tries[-1][1] if tries else None


def is_door_queue(q):
    """A door rounds queue, from the queue itself: its tests carry door_rounds.py's "door round N IN/OUT" labels
    (plan-terrain copies them into model), so an archived queue whose stage folder moved still counts; or its
    experiment folder holds rounds.json."""
    if any(str(t.get("model", "")).startswith("door round ") for t in q["tests"] if isinstance(t, dict)):
        return True
    return bool(q.get("experiment")) and os.path.exists(os.path.join(q["experiment"], "rounds.json"))


def results(qdir):
    """({key: {"verdict", "detail", "id", "queue"}}, build id, [duplicate keys]) for one queue."""
    q = load(os.path.join(qdir, "queue.json"))
    if not isinstance(q, dict) or not isinstance(q.get("tests"), list):
        raise Unavailable(f"{qdir}: queue.json missing, unreadable or without a tests list")
    build = q.get("build_id") or ""
    out, dup = {}, []

    def put(k, v):
        if k in out:
            raise Unavailable(f"{qdir}: tests {out[k]['id']} and {v['id']} share the key {list(k)}; "
                              f"the comparison can not tell them apart")
        out[k] = v
    judge_p = os.path.join(qdir, "door_rounds_judge.json")
    judged = load(judge_p)
    if os.path.exists(judge_p) and not (isinstance(judged, dict) and isinstance(judged.get("results"), list)):
        raise Unavailable(f"{judge_p}: unreadable or without a results list; judge the queue again")
    if judged is None and is_door_queue(q):
        raise Unavailable(f"{qdir}: a door rounds queue not judged yet; run scripts/bridge/door_rounds.py judge "
                          f"--queue {qdir} first")
    if judged is not None:
        ids = {t.get("id") for t in q["tests"] if isinstance(t, dict)}
        for r in judged["results"]:
            if r.get("id") not in ids:
                continue                                   # an expectation the queue never planned (plan-terrain --only)
            now = latest_attempt(qdir, r["id"])
            if now != r.get("attempt"):                    # the queue ran again after it was judged (Codex on #401)
                raise Unavailable(f"{judge_p}: judged at attempt {r.get('attempt') or 'none'} of {r['id']}, the "
                                  f"queue now has {now or 'none'}; judge the queue again (scripts/bridge/"
                                  f"door_rounds.py judge --queue {qdir})")
            k = ("door", r.get("cell_edid"), r.get("leg"), r.get("src"))
            put(k, {"verdict": r.get("verdict"), "detail": r.get("why", ""), "id": r.get("id"), "queue": qdir})
        return out, build, dup
    last = {}
    for r in rows(qdir):
        last[r["id"]] = r                                  # the last row of a test is its final verdict
    for t in q["tests"]:
        r = last.get(t["id"])
        k = (t.get("kind"), t.get("cell") or "", t.get("ref") or "", "" if t.get("side") is None else str(t["side"]))
        if t.get("kind") == "terrain":
            k += (t.get("model") or "",)
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
    if n == FAIL:
        return "new_failure"
    if o == n:
        return "unchanged"
    return "changed"


ORDER = ("regressed", "lost", "new_failure", "fixed", "still_failing", "changed", "new", "gone", "unchanged")
SHOWN = ("regressed", "lost", "new_failure", "fixed", "still_failing", "changed")
BAD = ("regressed", "lost", "new_failure")


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
    try:
        d = diff(a.old, a.new)
    except Unavailable as e:
        print(f"not compared: {e}")
        return 2
    print(f"builds {','.join(d['old_builds']) or '?'} -> {','.join(d['new_builds']) or '?'}: "
          + ", ".join(f"{g} {c}" for g, c in d["counts"].items()))
    for g in SHOWN:
        for r in d[g]:
            print(f"  {g:13s} {' '.join(str(x) for x in r['key'])}: {r['old']} -> {r['new']} {r['detail']}")
    for s in ("old", "new"):
        if d["duplicates"][s]:
            print(f"  note: {len(d['duplicates'][s])} key(s) repeated on the {s} side; the later queue wins")
    if a.out:
        if os.path.exists(a.out):
            sys.exit(f"{a.out} exists: a new file only")
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    return 1 if any(d["counts"][g] for g in BAD) else 0


if __name__ == "__main__":
    sys.exit(main())
