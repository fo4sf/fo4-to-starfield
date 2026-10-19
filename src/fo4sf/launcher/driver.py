"""Resumable build driver: runs a recipe of the repo's existing make scripts, one step at a time, and records each
step's result so an interrupted build resumes without guessing.

It wraps the scripts (make_core64c.py, make_mission.py, convert_batch.py, vmad_patch.py, light_patch.py, the dotnet
writers); it does not replace them or their own checkpoints. A recipe is JSON:

    {"name": "v6e", "state_dir": "{out}/.launcher", "vars": {"work": "...", "out": "..."},
     "steps": [{"id": "stage", "argv": ["{python}", "{repo}/scripts/terrain/make_core64c.py", "stage", ...],
                "inputs": ["{work}/selected.json"], "outputs": ["{out}/FO4TerrainCore.esm"],
                "after": ["select"], "timeout_s": 14400, "retries": 0, "code": ["scripts/terrain"]}],
     "manifest": {"outputs": ["{out}"], "fo4_data": ["..."], "starfield": "..."}}

{python} and {repo} are filled in; every other {name} comes from "vars" or --set name=value. A var whose value is
"?" must be given with --set (example recipes leave the PC paths open that way).

A step is reused only when its last run finished with exit 0, its outputs still exist, and its fingerprint is
unchanged: the resolved argv and cwd, the identity of each declared input (size and time; content hash for files up to
64 MiB) and the content of its code paths (default: the scripts named in argv plus src/fo4sf). Anything else reruns.

Statuses, and what they mean in the run report:
    done     ran in this run, exit 0, every declared output present
    reused   not run: an earlier run's result still holds (counted apart from done, never as new work)
    failed   exit code other than 0, or an output missing after exit 0
    timeout  stopped at timeout_s
    blocked  not run: a step it depends on is not done or reused, or the disk floor was not met
    not_run  not reached (the run stopped earlier, or --until)
Only a run where every step is done or reused is complete; the exit code says so.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

from . import files
from . import manifest as build_manifest

OK = ("done", "reused")
SMALL = 64 << 20
IDLE_PRIORITY_CLASS = 0x00000040          # Windows: the PC rule "Idle priority" for long jobs
_VAR = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


class RecipeError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def substitute(value, env):
    if isinstance(value, list):
        return [substitute(v, env) for v in value]

    def one(m):
        if m.group(1) not in env:
            raise RecipeError(f"unknown variable {{{m.group(1)}}} in {value!r}")
        return str(env[m.group(1)])
    return _VAR.sub(one, value)


def load_recipe(path, overrides=(), repo=None):
    """(recipe with every {var} resolved, env). Refuses duplicate ids, unknown dependencies and cycles."""
    r = files.load_json(path)
    env = {"python": sys.executable, "repo": repo or os.getcwd()}
    env.update({k: str(v) for k, v in (r.get("vars") or {}).items()})
    for o in overrides:
        k, sep, v = o.partition("=")
        if not sep or not k:
            raise RecipeError(f"--set needs name=value, got {o!r}")
        env[k] = v
    missing = sorted(k for k, v in env.items() if v == "?")
    if missing:
        raise RecipeError(f"set {', '.join(missing)} with --set name=value (the recipe leaves them open)")
    # vars may refer to each other ("out": "{root}/x"): resolve a few rounds
    for _ in range(5):
        env = {k: (substitute(v, env) if k not in ("python", "repo") else v) for k, v in env.items()}
    steps, seen = [], set()
    for s in r.get("steps") or []:
        sid = s.get("id")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", sid):
            raise RecipeError(f"step id {sid!r}: letters, digits, _ . - only")
        if sid in seen:
            raise RecipeError(f"step id {sid!r} twice")
        if not s.get("argv"):
            raise RecipeError(f"step {sid}: no argv")
        for dep in s.get("after") or []:
            if dep not in seen:
                raise RecipeError(f"step {sid}: depends on {dep!r}, which is not an earlier step")
        seen.add(sid)
        steps.append({"id": sid, "argv": substitute(list(map(str, s["argv"])), env),
                      "cwd": substitute(s.get("cwd", "{repo}"), env),
                      "inputs": substitute(list(s.get("inputs") or []), env),
                      "outputs": substitute(list(s.get("outputs") or []), env),
                      "after": list(s.get("after") or []),
                      "code": list(s.get("code") or []),
                      "timeout_s": s.get("timeout_s"), "retries": int(s.get("retries", 0)),
                      "description": s.get("description", "")})
    if not steps:
        raise RecipeError("recipe has no steps")
    out = {"name": r.get("name", os.path.splitext(os.path.basename(path))[0]), "steps": steps,
           "state_dir": substitute(r.get("state_dir", "{repo}/.launcher"), env),
           "manifest": {k: substitute(v, env) for k, v in (r.get("manifest") or {}).items()}}
    return out, env


def path_identity(p):
    if os.path.isfile(p):
        return files.identity(p, SMALL)
    if os.path.isdir(p):
        n, size, newest = 0, 0, 0
        for d, _dirs, names in os.walk(p):
            for name in names:
                st = os.stat(os.path.join(d, name))
                n, size, newest = n + 1, size + st.st_size, max(newest, st.st_mtime_ns)
        return {"dir_files": n, "dir_bytes": size, "dir_newest_ns": newest}
    return None


def code_paths(step, repo):
    paths = [os.path.join(repo, c) for c in step["code"]]
    if not step["code"]:
        paths = [a for a in step["argv"] if a.endswith(".py") and os.path.isfile(a)]
        paths.append(os.path.join(repo, "src", "fo4sf"))
    return paths


def code_hash(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        targets = [p] if os.path.isfile(p) else sorted(
            os.path.join(d, n) for d, dirs, names in os.walk(p) for n in names
            if n.endswith((".py", ".cs", ".csproj", ".json")) and "__pycache__" not in d)
        for t in targets:
            h.update(os.path.relpath(t, os.path.dirname(p)).replace(os.sep, "/").encode())
            h.update(files.sha256(t).encode())
    return h.hexdigest()


def fingerprint(step, repo):
    body = {"argv": step["argv"], "cwd": step["cwd"],
            "inputs": {p: path_identity(p) for p in step["inputs"]},
            "code": code_hash(code_paths(step, repo))}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def free_gb(path):
    probe = path
    while probe and not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return shutil.disk_usage(probe or ".").free / 2 ** 30


class Lock:
    """One driver per state folder: an O_EXCL lock file with the holder's pid. A leftover lock is never taken over
    silently; --break-lock removes it on purpose."""

    def __init__(self, state_dir, break_lock=False):
        self.path = os.path.join(state_dir, "driver.lock")
        self.break_lock = break_lock

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if self.break_lock and os.path.exists(self.path):
            os.remove(self.path)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            with open(self.path, encoding="utf-8", errors="replace") as f:
                holder = f.read().strip()
            raise RecipeError(f"another driver holds {self.path} ({holder}); if none runs, pass --break-lock")
        with os.fdopen(fd, "w") as f:
            f.write(f"pid {os.getpid()} since {now()}")
        return self

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


def run_step(step, log_path, idle=False):
    """(status, returncode, seconds). stdout and stderr go to log_path."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    flags = IDLE_PRIORITY_CLASS if idle and os.name == "nt" else 0
    t0 = time.monotonic()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        log.write(f"# {now()} {json.dumps(step['argv'])}\n")
        log.flush()
        try:
            r = subprocess.run(step["argv"], cwd=step["cwd"], stdout=log, stderr=subprocess.STDOUT,
                               timeout=step["timeout_s"], creationflags=flags)
        except subprocess.TimeoutExpired:
            return "timeout", None, time.monotonic() - t0
        except OSError as e:
            log.write(f"\n# could not start: {e}\n")
            return "failed", None, time.monotonic() - t0
    dt = time.monotonic() - t0
    if r.returncode != 0:
        return "failed", r.returncode, dt
    missing = [p for p in step["outputs"] if not os.path.exists(p)]
    if missing:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"\n# exit 0 but outputs missing: {missing}\n")
        return "failed", 0, dt
    return "done", 0, dt


def decide(step, prev, fp, force=()):
    """("reuse" | "run", reason) for one step, given its last record and its fingerprint now."""
    if step["id"] in force:
        return "run", "forced"
    if prev.get("status") not in OK:
        return "run", f"last status {prev.get('status', 'never run')}"
    if prev.get("fingerprint") != fp:
        return "run", "inputs, command or code changed"
    if any(not os.path.exists(p) for p in step["outputs"]):
        return "run", "an output is gone"
    return "reuse", f"finished {prev.get('finished')}"


def plan(recipe, state, repo, force=()):
    """[(step, would, reason)] as things stand now (a dry run: a step whose inputs an earlier step will rewrite shows
    the state before that rewrite)."""
    out = []
    for s in recipe["steps"]:
        would, why = decide(s, (state.get("steps") or {}).get(s["id"]) or {}, fingerprint(s, repo), force)
        out.append((s, would, why))
    return out


def build(recipe, repo, *, dry_run=False, force=(), until=None, min_free_gb=0.0, disk_paths=(), idle=False,
          break_lock=False, keep_going=False, echo=print):
    """Run (or with dry_run, only print) the recipe. Returns the run report dict; report["complete"] is the verdict."""
    state_dir = recipe["state_dir"]
    state_path = os.path.join(state_dir, "state.json")
    state = files.load_json(state_path) if os.path.isfile(state_path) else {"recipe": recipe["name"], "steps": {}}
    if dry_run:
        steps_plan = plan(recipe, state, repo, force)
        for s, would, why in steps_plan:
            echo(f"  {s['id']:<20} {would:<6} {why}")
        return {"dry_run": True, "plan": [(s["id"], w, why) for s, w, why in steps_plan], "complete": False}
    report = {"recipe": recipe["name"], "started": now(), "steps": []}
    with Lock(state_dir, break_lock):
        # a step left "running" by an interrupted run is not a result
        for sid, rec in (state.get("steps") or {}).items():
            if rec.get("status") == "running":
                rec["status"] = "interrupted"
        stop = False
        status_of = {}
        for s in recipe["steps"]:
            sid = s["id"]
            rec = state["steps"].setdefault(sid, {})
            # the fingerprint is taken at the step's turn, after the steps before it have written its inputs
            fp = fingerprint(s, repo) if not stop else None
            would, why = decide(s, rec, fp, force) if not stop else ("run", "")
            if stop:
                status, note = "not_run", "run stopped earlier"
            elif any(status_of.get(d) not in OK for d in s["after"]):
                status, note = "blocked", "depends on " + ", ".join(d for d in s["after"] if status_of.get(d) not in OK)
            elif would == "reuse" and not any(status_of.get(d) == "done" for d in s["after"]):
                status, note = "reused", why
            elif would == "reuse":
                why = "a step it depends on ran in this run"
                status, note = None, why
            elif min_free_gb and any(free_gb(p) < min_free_gb for p in (disk_paths or s["outputs"] or [state_dir])):
                status, note = "blocked", f"less than {min_free_gb} GB free"
            else:
                status, note = None, why
            if status is None:
                rec.pop("last_run_status", None)
                rec.update(status="running", started=now(), fingerprint=fp)
                files.save_json(state_path, state)
                for attempt in range(1 + s["retries"]):
                    log = os.path.join(state_dir, "logs", f"{sid}.{rec.get('runs', 0) + 1}.log")
                    status, rc, dt = run_step(s, log, idle)
                    rec["runs"] = rec.get("runs", 0) + 1
                    rec.update(returncode=rc, seconds=round(dt, 1), log=log, attempt=attempt + 1)
                    if status == "done":
                        break
                rec.update(status=status, finished=now())
                if status == "done":
                    rec["outputs"] = {p: path_identity(p) for p in s["outputs"]}
                files.save_json(state_path, state)
            elif status in ("blocked", "not_run"):
                # keep an earlier good result on record only as history; this run did not reach it
                rec["last_run_status"] = status
                files.save_json(state_path, state)
            status_of[sid] = status
            report["steps"].append({"id": sid, "status": status, "note": note,
                                    "returncode": rec.get("returncode") if status not in ("reused",) else None})
            echo(f"  {sid:<20} {status:<8} {note}")
            if status not in OK and not keep_going:
                stop = True
            if until and sid == until:
                stop = True
        report["finished"] = now()
        counts = {}
        for r in report["steps"]:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        report["counts"] = counts
        report["complete"] = all(r["status"] in OK for r in report["steps"])
        if report["complete"] and recipe["manifest"]:
            m = recipe["manifest"]
            man = build_manifest.build_manifest(repo=repo, fo4_data=m.get("fo4_data") or (),
                                                starfield=m.get("starfield") or "",
                                                output_paths=m.get("outputs") or (),
                                                extra={"recipe": recipe["name"], "run": report})
            target = m.get("path") or os.path.join(state_dir, "build_manifest.json")
            files.save_json(target, man)
            report["manifest"] = target
        files.save_json(os.path.join(state_dir, "last_run.json"), report)
    return report
