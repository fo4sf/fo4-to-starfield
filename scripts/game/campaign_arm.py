"""Arm a chain of planned queues only when it can not swap the installed set, go where the owner said not to go, or run
without the crash and disk caps (docs/testing/campaign-arm.md). Offline: it reads queue.json files and a campaign
manifest, it never launches the game, installs or types anything.

usage:
  python scripts/game/campaign_arm.py check --campaign <campaign.json> [--release HOLD,...]
      every queue of the campaign, refused with the reason when:
        - its queue.json is missing, or its tests name no coc;
        - it pins another FO4Port staging than the campaign's, or that staging's FO4Port.esm changed since the plan;
        - its pinned bridge is not the campaign's, or changed since the plan;
        - its pre_launch would install anything but the campaign's installed experiment with its installed plugins
          (a walk queue's exp_install.py install of the set already installed is allowed: it changes nothing);
        - a test starts in a held cell (campaign "holds", e.g. the Red Rocket arrival) not named in --release;
      and the campaign is refused when its caps are not the night-run caps (one launch, stop at the first crash, at
      least 40 GB free on the dump drive). Exit 0 only when every queue can be armed.
  python scripts/game/campaign_arm.py script --campaign <campaign.json> --out <NEW chain.ps1> [--release HOLD,...]
      after the same check, the PowerShell chain: the check again at run time, then per queue the run with the caps,
      its judge, and the gate; the chain stops at the first queue the gate refuses.
  python scripts/game/campaign_arm.py run --campaign <campaign.json>
      the same chain without PowerShell: the check (holds
      lifted only by the campaign's "released" list), then per queue testqueue.py run with the caps, its judge and the
      gate, stopping at the first refusal. The campaign's "launch" ("steam", the default, or "exe") becomes
      FO4SF_LAUNCH for cycle.ps1. Every step is logged to <campaign>.run.log. Exit 0 only when every queue passed.
  python scripts/game/campaign_arm.py gate --queue <queue> --run-exit N [--judge-exit N]
      exit 0 only when the run ended with exit 0, the judge (when given) with exit 0, and the queue's state.json
      exists, says finished and counts no crash and no dead start.

campaign.json:
  {"name": "v6e", "checkout": "D:\\Modding\\wt_nightrun", "python": "C:\\Modding\\venv-render\\Scripts\\python.exe",
   "staging": "<the installed FO4Port staging>", "bridge": "<the installed bridge staging>",
   "installed_exp": "<the installed experiment folder>", "installed_plugins": ["FO4TerrainCore.esm", ...],
   "caps": {"max_attempts": 1, "max_relaunch": 1, "crash_budget": 1, "min_free_gb": 43, "dump_drive": "D:\\"},
   "holds": {"red_rocket": ["FO4Core_RedRocketSpawn"]},
   "queues": [{"name": "doors_out", "queue": "<queue folder>", "judge": ["scripts/bridge/door_rounds.py", "judge",
               "--queue", "<queue folder>"]}]}
"""
import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testqueue as tq  # noqa: E402

FLOOR_GB = 40.0                  # the coordinator's night-run floor (2026-10-19): at least 40 GB free on D:
JUDGES = ("scripts/bridge/door_rounds.py", "scripts/bridge/presence.py", "scripts/game/testqueue.py")
JUDGE_CMDS = {"scripts/bridge/door_rounds.py": ("judge",), "scripts/bridge/presence.py": ("judge",),
              "scripts/game/testqueue.py": ("report",)}


def norm(p):
    """A Windows path compared without case, slash direction or a trailing separator."""
    return str(p).replace("/", "\\").rstrip("\\").casefold()


def cells(q):
    """The cells every test of a queue starts in (a plan kind's cell, coc, a "coc X" travel), in order, no repeats."""
    out = []
    for t in q.get("tests") or []:
        for c in (t.get("cell"), t.get("coc"), *re.findall(r"(?i)\bcoc\s+([A-Za-z0-9_]+)", str(t.get("travel") or ""))):
            if c and c not in out:
                out.append(c)
    return out


def check_caps(caps):
    """Reasons the caps are not the night-run caps."""
    c, bad = caps or {}, []
    if c.get("max_relaunch") != 1:
        bad.append(f"max_relaunch {c.get('max_relaunch')!r}, want 1 (one launch, no relaunch after a crash)")
    if c.get("crash_budget") != 1:
        bad.append(f"crash_budget {c.get('crash_budget')!r}, want 1 (stop at the first crash or dead start)")
    g = c.get("min_free_gb")
    if not (isinstance(g, (int, float)) and not isinstance(g, bool) and math.isfinite(g) and g >= FLOOR_GB):
        bad.append(f"min_free_gb {g!r}, want {FLOOR_GB:g} or more")
    if c.get("max_attempts") not in (1, 2):
        bad.append(f"max_attempts {c.get('max_attempts')!r}, want 1 or 2")
    if not re.fullmatch(r"[A-Za-z]:\\", str(c.get("dump_drive") or "")):
        bad.append(f"dump_drive {c.get('dump_drive')!r}, want a drive root such as D:\\")
    return bad


def pre_launch_why(pre, camp):
    """Why a queue's pre_launch is not allowed, else None."""
    if not pre:
        return None
    args = [str(x) for x in pre[1:]]
    script = norm(args[0]) if args else ""
    if script == norm(os.path.join("scripts", "game", "runner_features.py")) and args[1:2] == ["check"]:
        return None
    if script != norm(os.path.join("scripts", "game", "exp_install.py")) or args[1:2] != ["install"]:
        return f"pre_launch runs {' '.join(args[:2])}, not a runner check or the installed experiment"

    def opt(name):
        return args[args.index(name) + 1] if name in args[:-1] else None
    exp, plugins = opt("--exp-dir"), opt("--plugins")
    if not camp.get("installed_exp") or exp is None or norm(exp) != norm(camp["installed_exp"]):
        return f"pre_launch would install {exp}, not the installed experiment {camp.get('installed_exp')}"
    want = {p.casefold() for p in camp.get("installed_plugins") or []}
    got = {p.strip().casefold() for p in (plugins or "").split(",") if p.strip()}
    if not got or got != want:
        return f"pre_launch would activate {sorted(got)}, the installed set is {sorted(want)}"
    return None


def check_queue(entry, camp, release):
    """(queue.json or None, [reasons it is refused], [notes])."""
    qdir, why, notes = entry.get("queue") or "", [], []
    q = tq.load(os.path.join(qdir, "queue.json"))
    if not isinstance(q, dict) or not q.get("tests"):
        return None, [f"no planned queue at {qdir}"], notes
    if norm(q.get("staging") or "") != norm(camp.get("staging") or ""):
        why.append(f"pins the staging {q.get('staging')}, the campaign's is {camp.get('staging')}")
    else:
        esm = os.path.join(q["staging"], "FO4Port.esm")
        if not os.path.exists(esm):
            why.append(f"{esm} is missing")
        elif tq.sha256(esm) != q.get("plugin_sha256"):
            why.append(f"{esm} changed since the plan (build {q.get('build_id')})")
    br = q.get("bridge")
    if br:
        if camp.get("bridge") and norm(br.get("dir") or "") != norm(camp["bridge"]):
            why.append(f"pins the bridge {br.get('dir')}, the campaign's is {camp['bridge']}")
        else:
            m = tq.bridge_mismatch(br)
            if m:
                why.append(m)
    p = pre_launch_why(q.get("pre_launch"), camp)
    if p:
        why.append(p)
    starts = cells(q)
    if not starts:
        why.append("no test names a coc: where it starts can not be checked")
    for hold, names in (camp.get("holds") or {}).items():
        hit = [c for c in starts if c.casefold() in {n.casefold() for n in names}]
        if hit and hold not in release:
            why.append(f"starts at {', '.join(hit)}: held ({hold}); --release {hold} once the owner allows it")
        elif hit:
            notes.append(f"starts at {', '.join(hit)}: {hold} released for this run")
    judge = entry.get("judge")
    if judge is not None:
        if not (isinstance(judge, list) and judge and all(isinstance(x, str) for x in judge)) or \
                norm(judge[0]) not in {norm(j) for j in JUDGES} or \
                tuple(judge[1:2]) not in {JUDGE_CMDS[j] for j in JUDGES if norm(j) == norm(judge[0])}:
            why.append(f"judge {judge!r} is not door_rounds.py judge, presence.py judge or testqueue.py report")
    st = tq.load(os.path.join(qdir, "state.json"), {}) or {}
    left = len([t for t in q["tests"] if t["id"] not in (st.get("done") or {})])
    if st.get("crashes") or st.get("start_deaths"):
        why.append(f"state.json counts {st.get('crashes', 0)} crash(es) and {st.get('start_deaths', 0)} dead start(s): "
                   f"plan a new queue folder for a clean budget")
    if not left:
        why.append("every test is already done")
    notes.append(f"{left} of {len(q['tests'])} tests to run; starts: {', '.join(starts[:6])}"
                 + (" ..." if len(starts) > 6 else ""))
    return q, why, notes


def check(camp, release):
    """({"caps": [...], "queues": [(entry, why, notes)]}, ok)."""
    caps = check_caps(camp.get("caps"))
    unknown = sorted(set(release) - set(camp.get("holds") or {}))
    if unknown:
        caps.append(f"--release names holds the campaign does not have: {unknown}")
    rows, names = [], set()
    for e in camp.get("queues") or []:
        _, why, notes = check_queue(e, camp, release)
        if e.get("name") in names or not re.fullmatch(r"[A-Za-z0-9_.-]+", str(e.get("name") or "")):
            why.append(f"queue name {e.get('name')!r} is missing, repeated or not plain")
        names.add(e.get("name"))
        rows.append((e, why, notes))
    if not rows:
        caps.append("the campaign has no queues")
    return {"caps": caps, "queues": rows}, not caps and all(not w for _, w, _ in rows)


def read_campaign(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def releases(s):
    return {x.strip() for x in (s or "").split(",") if x.strip()}


def show(res):
    for c in res["caps"]:
        print(f"REFUSED campaign: {c}")
    for e, why, notes in res["queues"]:
        print(f"{'REFUSED' if why else 'OK':8s} {e.get('name')}: {e.get('queue')}")
        for w in why:
            print(f"    - {w}")
        for n in notes:
            print(f"    . {n}")


def ps(s):
    """A PowerShell single-quoted string; exits on a quote."""
    if "'" in str(s) or "\n" in str(s):
        sys.exit(f"{s!r}: a quote or a line break in a path or argument")
    return f"'{s}'"


def run_args(qdir, caps):
    return ["scripts\\game\\testqueue.py", "run", "--queue", qdir, "--max-attempts", str(caps["max_attempts"]),
            "--max-relaunch", str(caps["max_relaunch"]), "--crash-budget", str(caps["crash_budget"]),
            "--min-free-gb", f"{caps['min_free_gb']:g}", "--dump-drive", caps["dump_drive"], "--wait-for-idle"]


def chain(camp, path, release):
    caps, py = camp["caps"], camp.get("python") or "python"
    rel = ",".join(sorted(release))
    lines = [f"# {camp.get('name')} chain, written by scripts/game/campaign_arm.py from {path} at "
             f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}" + (f"; released: {rel}" if rel else ""),
             "# Every queue runs with one launch, stops at the first crash or dead start, and keeps "
             f"{caps['min_free_gb']:g} GB free on {caps['dump_drive']}.",
             "# The chain stops at the first queue whose run or gate fails. It types nothing itself.",
             f"$py = {ps(py)}", f"Set-Location {ps(camp['checkout'])}",
             f"& $py scripts\\game\\campaign_arm.py check --campaign {ps(path)}" + (f" --release {ps(rel)}" if rel else ""),
             "if ($LASTEXITCODE -ne 0) { Write-Host 'campaign check refused: nothing run'; exit 1 }"]
    for e, _, _ in check(camp, release)[0]["queues"]:
        lines += ["", f"# {e['name']}",
                  "& $py " + " ".join(ps(x) for x in run_args(e["queue"], caps)), "$rc = $LASTEXITCODE"]
        judge = ""
        if e.get("judge"):
            lines += ["& $py " + " ".join(ps(x.replace("/", "\\") if i == 0 else x) for i, x in enumerate(e["judge"])),
                      "$jr = $LASTEXITCODE"]
            judge = " --judge-exit $jr"
        lines += [f"& $py scripts\\game\\campaign_arm.py gate --queue {ps(e['queue'])} --run-exit $rc{judge}",
                  f"if ($LASTEXITCODE -ne 0) {{ Write-Host 'stopped after {e['name']}'; exit 1 }}"]
    lines += ["", "Write-Host 'chain finished'"]
    return "\r\n".join(lines) + "\r\n"


def gate(qdir, rc, judge_rc=None):
    """(ok, why) for one run: ok only for exit 0, a judge (when one ran) that exited 0, and a state.json that
    says finished with no crash and no dead start. A missing or unfinished state is no proof the queue ran."""
    try:
        st = tq.load(os.path.join(qdir, "state.json"))
    except ValueError:
        st = None
    if not isinstance(st, dict):
        return False, f"no readable state.json in {qdir}: nothing proves the queue ran"
    if rc != 0:
        return False, f"the run ended with exit {rc} ({st.get('status')})"
    if judge_rc not in (None, 0):
        return False, f"the judge exited {judge_rc}"
    if st.get("status") != "finished":
        return False, f"the queue is {st.get('status')!r}, not finished"
    if st.get("crashes") or st.get("start_deaths"):
        return False, f"{st.get('crashes', 0)} crash(es), {st.get('start_deaths', 0)} dead start(s)"
    return True, "clean: finished"


LAUNCHES = ("steam", "exe")


def run_chain(camp, log=print, call=None):
    """The chain in Python: 0 when every queue ran clean, else 1. call(argv, env) runs one
    step and returns its exit code (subprocess in the repo by default)."""
    import subprocess
    if call is None:
        def call(argv, env):
            return subprocess.run(argv, cwd=os.path.dirname(os.path.dirname(HERE)), env=env).returncode
    launch = camp.get("launch", "steam")
    if launch not in LAUNCHES:
        log(f"REFUSED campaign: launch {launch!r}, want one of {LAUNCHES}")
        return 1
    released = camp.get("released") or []
    if not (isinstance(released, list) and all(isinstance(x, str) for x in released)):
        log(f"REFUSED campaign: released {released!r} is not a list of hold names")
        return 1
    res, ok = check(camp, set(released))
    for c in res["caps"]:
        log(f"REFUSED campaign: {c}")
    for e, why, notes in res["queues"]:
        log(f"{'REFUSED' if why else 'OK'} {e.get('name')}: " + "; ".join(why + notes))
    if not ok:
        return 1
    env = dict(os.environ, FO4SF_LAUNCH=launch)
    py, caps = sys.executable, camp["caps"]
    for e, _, _ in res["queues"]:
        rc = call([py, os.path.join("scripts", "game", "testqueue.py")] + run_args(e["queue"], caps)[1:], env)
        log(f"{e['name']}: run exit {rc}")
        jr = None
        if e.get("judge"):
            jr = call([py, e["judge"][0].replace("/", os.sep)] + e["judge"][1:], env)
            log(f"{e['name']}: judge exit {jr}")
        good, why = gate(e["queue"], rc, jr)
        log(f"{e['name']}: {'PASS' if good else 'STOP'} {why}")
        if not good:
            return 1
    log("chain finished")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rn = sub.add_parser("run")
    rn.add_argument("--campaign", required=True)
    for name in ("check", "script"):
        s = sub.add_parser(name)
        s.add_argument("--campaign", required=True)
        s.add_argument("--release", default="", help="holds the owner lifted, comma-separated")
        if name == "script":
            s.add_argument("--out", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--queue", required=True)
    g.add_argument("--run-exit", type=int, required=True)
    g.add_argument("--judge-exit", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "gate":
        ok, why = gate(a.queue, a.run_exit, a.judge_exit)
        print(("PASS " if ok else "STOP ") + why)
        return 0 if ok else 1
    if a.cmd == "run":
        logp = a.campaign + ".run.log"

        def log(msg):
            line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}"
            print(line)
            with open(logp, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return run_chain(read_campaign(a.campaign), log)
    camp, release = read_campaign(a.campaign), releases(a.release)
    res, ok = check(camp, release)
    show(res)
    if a.cmd == "check" or not ok:
        return 0 if ok else 1
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists: the script writes a new file only")
    if not camp.get("checkout"):
        sys.exit("the campaign names no checkout to run from")
    text = chain(camp, a.campaign, release)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
