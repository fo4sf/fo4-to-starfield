"""Commit the unattended Lead's own docs/ai edits on its branch, and nothing else (the Lead's only git write).

  python -P tools/ai-team/lead_commit.py "<what changed>"   (-P: the script's folder is not put on sys.path)

Refuses (exit 1) unless the current branch is ai/local-lead, nothing is unmerged, no merge / cherry-pick / revert /
rebase is in progress, and nothing outside docs/ai/ is staged (renames count as their source and destination);
stages only docs/ai/ (no -f, so ignored files stay out), checks again, prefixes the subject with "Lead (local): ";
never amends and never pushes. Exit 0 with "nothing to commit" when docs/ai/ has no change. OpenCode allows exactly
this command for fo4-lead, so a raw `git add` / `git commit` pattern (which also matches -a, --amend, pathspecs and ..)
is not needed.
"""
import argparse
import os
import subprocess
import sys

BRANCH = "ai/local-lead"
DOCS = "docs/ai/"
PREFIX = "Lead (local): "
IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply")


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def staged():
    """Staged paths; with --no-renames a rename shows its deleted source as well as its destination."""
    return [p for p in git("diff", "--cached", "--name-only", "--no-renames", "-z").split("\0") if p]


def outside_docs():
    return [p for p in staged() if not p.startswith(DOCS)]


def why_not():
    """The reason the worktree is not in a state to commit, or None."""
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != BRANCH:
        return f"on {branch!r}, not {BRANCH}"
    unmerged = sorted({line.split("\t", 1)[-1] for line in git("ls-files", "-u").splitlines() if line})
    if unmerged:
        return "unmerged files (resolve them first): " + ", ".join(unmerged)
    busy = [n for n in IN_PROGRESS if os.path.exists(git("rev-parse", "--git-path", n).strip())]
    if busy:
        return "a git operation is in progress: " + ", ".join(busy)
    outside = outside_docs()
    if outside:
        return "staged outside docs/ai/: " + ", ".join(outside)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lead_commit.py", description=__doc__.splitlines()[0])
    ap.add_argument("message", help="one line: what changed")
    a = ap.parse_args(argv)
    msg = " ".join(a.message.split())
    if not msg:
        print("refused: empty message"); return 1
    if not msg.startswith(PREFIX.strip()):
        msg = PREFIX + msg
    try:
        reason = why_not()
        if reason:
            print(f"refused: {reason}"); return 1
        git("add", "--", DOCS)
        outside = outside_docs()                      # nothing else may have been staged since the first check
        if outside:
            print("refused: staged outside docs/ai/: " + ", ".join(outside)); return 1
        if not staged():
            print("nothing to commit in docs/ai/"); return 0
        git("commit", "--only", "-m", msg, "--", DOCS)     # only docs/ai/, whatever else is staged by then
        print(git("log", "-1", "--format=%h %s").strip())
        return 0
    except RuntimeError as e:
        print(f"failed: {e}"); return 1


if __name__ == "__main__":
    sys.exit(main())
