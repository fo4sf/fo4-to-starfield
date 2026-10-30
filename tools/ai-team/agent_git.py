"""The implementation agent's own branch and commits, in the owner's terminal only (terminal.ps1).

  python -I tools/ai-team/agent_git.py branch ai/<name>                 new branch from origin/main, switched to; or,
                                                                        if ai/<name> exists, back onto it
  python -I tools/ai-team/agent_git.py commit "<Role (local): what changed>" <paths>
                                                                        commit exactly these paths on the ai/ branch

git runs as in lead_commit.py: no GIT_* variables but the identity, core.hooksPath at the null device, core.fsmonitor
off, so no planted hook or injected setting runs. Refuses (exit 1) in an unattended run (FO4SF_UNATTENDED=1), off an
ai/ branch, on ai/local-lead (the unattended Lead's branch, which commits through lead_commit.py), with a merge,
rebase, cherry-pick or revert in progress, or for a path the agents may not write (the guard's list: the team's rules,
tools, skills, CI and git's own files). Paths are literal (no git globs or pathspec magic). A new branch starts from
origin/main (terminal.ps1 fetches it), so one issue's branch never carries the last one's commits; uncommitted edits
come along. The terminal goes back to main whenever it opens on a clean worktree, so `branch` with an existing name
switches back to that branch, but only from a clean worktree and only while its guard and agent files (GUARD_PATHS)
are main's, since the guard reads them from the worktree. The message starts with the committing agent's own tag.
The owner's choice J (30 Oct) gives these commits to the coding agent: fo4-implement's rules allow this wrapper, while
the Lead's ask, so the Lead commits a docs note in the terminal only when the owner approves that call. Never amends,
never pushes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "guard"))
import allowlist                                     # noqa: E402  (the guard's write rules)
from lead_commit import IN_PROGRESS, git            # noqa: E402  (git without hooks or injected settings)

ROLES = ("Lead (local): ", "Implement (local): ", "Research (local): ", "QA (local): ")
LEAD_BRANCH = "ai/local-lead"
# The files the guard and OpenCode read from the worktree; terminal.ps1 checks the same list before it starts.
GUARD_PATHS = (".opencode", "opencode.json", "tools/ai-team", "AGENTS.md")


def why_not():
    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    if not branch.startswith("ai/") or branch == LEAD_BRANCH:
        return f"on {branch!r}: commits go on the agent's own ai/ branch (agent_git.py branch ai/<name>)"
    if git("ls-files", "-u").strip():
        return "unmerged files: resolve them first"
    busy = [n for n in IN_PROGRESS if os.path.exists(git("rev-parse", "--git-path", n).strip())]
    if busy:
        return "a git operation is in progress: " + ", ".join(busy)
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if os.environ.get("FO4SF_UNATTENDED") == "1":
        print("refused: unattended runs do not commit outside docs/ai (lead_commit.py)"); return 1
    try:
        root = git("rev-parse", "--show-toplevel").strip()
        if len(argv) == 2 and argv[0] == "branch":
            if not allowlist.AGENT_BRANCH.fullmatch(argv[1]) or argv[1] == LEAD_BRANCH:
                print("refused: the branch is ai/<lowercase-name>, and not ai/local-lead"); return 1
            if git("branch", "--list", argv[1]).strip():
                if git("status", "--porcelain", "--untracked-files=all").strip():
                    print(f"refused: {argv[1]} exists; commit or drop the uncommitted edits, then switch back"); return 1
                if git("diff", "--name-only", "origin/main", argv[1], "--", *GUARD_PATHS).strip():
                    print(f"refused: {argv[1]}'s guard or agent files are not main's; ask the owner to merge main into "
                          "it"); return 1
                git("switch", argv[1])
                print(f"back on {argv[1]}")
                return 0
            git("switch", "--no-track", "-c", argv[1], "origin/main")
            print(f"on new branch {argv[1]}")
            return 0
        if len(argv) >= 3 and argv[0] == "commit":
            msg, paths = " ".join(argv[1].split()), argv[2:]
            if not msg.startswith(ROLES):
                print('refused: the message starts with your own tag, for example "Implement (local): "'); return 1
            try:
                allowlist.check_write(root, paths)
            except allowlist.Refused as why:
                print(f"refused: {why}"); return 1
            reason = why_not()
            if reason:
                print(f"refused: {reason}"); return 1
            git("--literal-pathspecs", "add", "--", *paths)
            git("--literal-pathspecs", "commit", "--no-verify", "--only", "-m", msg, "--", *paths)   # only these paths
            print(git("log", "-1", "--format=%h %s").strip())
            return 0
        print('usage: agent_git.py branch ai/<name> | commit "<Role (local): what changed>" <paths>'); return 1
    except RuntimeError as e:
        print(f"failed: {e}"); return 1


if __name__ == "__main__":
    sys.exit(main())
