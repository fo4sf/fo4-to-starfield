"""Launcher self-update: bring the checkout the launcher runs from up to date with GitHub's main before it plays, so
whatever was merged is what runs (owner, 2026-10-31: "a way for the launcher to auto update itself so once everything
is merged, I don't need to tell anybody to install it").

The setting `update` (launcher/settings.py) says when: off (the default: nothing is fetched), check (fetches and says
how many commits main is behind), pull (fetches and fast-forwards, then the command starts again on the new code).
`launcher.py update` does it once by hand, whatever the setting.

Only a fast-forward, and only of a checkout that:
* is on main (a worktree on another branch, an agent's, is never moved);
* has no uncommitted change to a tracked file (files git does not track are left alone; git itself refuses a
  fast-forward that would overwrite one);
* has no merge, rebase, cherry-pick, revert or bisect in progress;
* has no commit of its own that GitHub's main lacks (then it is somebody's work, and only a merge could join them).
Never a reset, a stash, a merge commit or a checkout of another branch, and never while Starfield runs. A refusal or a
network failure is said in one line and the command goes on with the code it has. What it updates is code only: built
plugins, archives and installs in the game folder change only through their own install steps.
"""
import os
import subprocess
import sys

REMOTE, BRANCH = "origin", "main"
MODES = ("off", "check", "pull")
# files git keeps in the checkout's own git folder while an operation is half done
IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-merge", "rebase-apply")
RESTARTED = "FO4SF_LAUNCHER_UPDATED"           # set on the restarted command, so it never updates (or restarts) again
FETCH_TIMEOUT_S = 60


def git(repo, *args, run=subprocess.run, timeout=30):
    """(exit code, stdout stripped) of one git command in repo; (None, why) when git cannot be run or times out."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")            # never wait on a credential prompt
    try:
        r = run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError:
        return None, "git is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return None, f"git {args[0]} took longer than {timeout} s"
    except OSError as e:
        return None, f"git could not run ({e.strerror or e})"
    return r.returncode, (r.stdout or "").strip()


def check(repo, run=subprocess.run):
    """What an update would do: {"reason": why not (None when it can go ahead), "head", "remote", "behind"}.
    Fetches GitHub's main (the only thing that changes: the remote-tracking ref and FETCH_HEAD)."""
    out = {"reason": None, "head": None, "remote": None, "behind": 0}

    def stop(why):
        out["reason"] = why
        return out
    code, top = git(repo, "rev-parse", "--show-toplevel", run=run)
    if code != 0:
        return stop(top if code is None else f"{repo} is not a git checkout")
    if os.path.normcase(os.path.realpath(top)) != os.path.normcase(os.path.realpath(repo)):
        return stop(f"{repo} is inside another checkout ({top})")
    code, branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", run=run)
    if code != 0 or branch != BRANCH:
        return stop(f"the checkout is on {branch or 'a detached HEAD'}, not {BRANCH}")
    code, gitdir = git(repo, "rev-parse", "--absolute-git-dir", run=run)
    if code != 0:
        return stop("its git folder cannot be found")
    busy = [n for n in IN_PROGRESS if os.path.exists(os.path.join(gitdir, n))]
    if busy:
        return stop(f"a git operation is in progress ({', '.join(busy)})")
    code, dirty = git(repo, "status", "--porcelain", "--untracked-files=no", run=run)
    if code != 0:
        return stop("git status failed")
    if dirty:
        lines = dirty.splitlines()
        return stop(f"{len(lines)} tracked file(s) changed and not committed ({', '.join(l[3:] for l in lines[:3])}"
                    + (", ..." if len(lines) > 3 else "") + ")")
    code, why = git(repo, "fetch", "--quiet", REMOTE, BRANCH, run=run, timeout=FETCH_TIMEOUT_S)
    if code != 0:
        return stop(f"could not fetch {REMOTE}/{BRANCH} ({why or 'no network?'})")
    _c, out["head"] = git(repo, "rev-parse", "HEAD", run=run)
    code, out["remote"] = git(repo, "rev-parse", "FETCH_HEAD", run=run)
    if code != 0:
        return stop("the fetched commit cannot be read")
    code, ahead = git(repo, "rev-list", "--count", f"{out['remote']}..HEAD", run=run)
    if code != 0:
        return stop("the checkout's history cannot be compared with GitHub's")
    if int(ahead or 0):
        return stop(f"local {BRANCH} has {ahead} commit(s) GitHub's {BRANCH} lacks")
    _c, behind = git(repo, "rev-list", "--count", f"HEAD..{out['remote']}", run=run)
    out["behind"] = int(behind or 0)
    return out


def describe(repo, run=subprocess.run):
    """One line on which code this checkout runs, read locally (nothing is fetched): branch, commit, and how many
    tracked files differ from it. For the support bundle, so a report names the version it came from."""
    code, head = git(repo, "rev-parse", "--short=12", "HEAD", run=run)
    if code != 0:
        return f"launcher code: not a git checkout or git missing ({head or 'no commit'})"
    _c, branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", run=run)
    _c, dirty = git(repo, "status", "--porcelain", "--untracked-files=no", run=run)
    n = len((dirty or "").splitlines())
    return (f"launcher code: {branch or 'detached HEAD'} at {head}"
            + (f", {n} tracked file(s) changed and not committed" if n else ", no local changes"))


def update(repo, mode, say=print, *, running=lambda: False, run=subprocess.run):
    """Do what `mode` says (MODES); True only when the checkout moved, so the caller starts the command again."""
    if mode not in MODES:
        raise ValueError(f"update: {mode!r} is not one of {', '.join(MODES)}")
    if mode == "off" or os.environ.get(RESTARTED):
        return False
    if running():
        say("update: skipped while Starfield runs")
        return False
    c = check(repo, run=run)
    if c["reason"]:
        say(f"update: skipped: {c['reason']}; going on with this version")
        return False
    if not c["behind"]:
        say(f"update: up to date ({BRANCH} {c['head'][:7]})")
        return False
    if mode == "check":
        say(f"update: GitHub's {BRANCH} has {c['behind']} new commit(s); `launcher.py update` (or the setting "
            "update=pull) brings them")
        return False
    _c, log = git(repo, "log", "--oneline", "--no-decorate", "-n", "10", f"HEAD..{c['remote']}", run=run)
    code, why = git(repo, "merge", "--ff-only", "--quiet", c["remote"], run=run)
    if code != 0:
        say(f"update: the fast-forward failed ({why or 'see git status'}); going on with this version")
        return False
    say(f"update: {BRANCH} {c['head'][:7]} -> {c['remote'][:7]}, {c['behind']} commit(s):")
    for line in (log or "").splitlines():
        say(f"    {line}")
    if c["behind"] > 10:
        say(f"    ... and {c['behind'] - 10} more")
    return True


def restart(argv, run=subprocess.call):
    """Run the same command again on the updated code (marked RESTARTED, so it does not update again); its exit code."""
    return run([sys.executable, *argv], env=dict(os.environ, **{RESTARTED: "1"}))
