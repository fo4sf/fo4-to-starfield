"""tools/ai-team/lead_commit.py: the unattended Lead commits only its docs/ai edits, only on ai/local-lead.
Synthetic git repositories in a temp folder; no network, no global git config."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "ai-team", "lead_commit.py")


class LeadCommitTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        empty = os.path.join(self.d, "empty.gitconfig")
        open(empty, "w").close()
        # HOME/XDG_CONFIG_HOME isolate the wrapper's git too (it drops GIT_CONFIG_GLOBAL by design)
        self.env = dict(os.environ, HOME=self.d, XDG_CONFIG_HOME=self.d, GIT_CONFIG_GLOBAL=empty,
                        GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        self.d = os.path.join(self.d, "repo")
        os.makedirs(self.d)
        self.git("init", "-q", "-b", "main")
        self.write("docs/ai/agent-status.md", "old\n")
        self.write("tools/ai-team/run-lead.ps1", "old\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("checkout", "-q", "-b", "ai/local-lead")

    def git(self, *a, check=True):
        return subprocess.run(["git", "-C", self.d, *a], capture_output=True, text=True, check=check, env=self.env).stdout

    def write(self, rel, text):
        p = os.path.join(self.d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, SCRIPT, *args], cwd=self.d, capture_output=True, text=True, env=self.env)
        return r.returncode, r.stdout

    def head(self):
        return self.git("log", "-1", "--format=%s").strip()

    def test_commits_only_docs_ai_with_the_lead_prefix(self):
        self.write("docs/ai/agent-status.md", "new\n")
        self.write("docs/ai/research-log.md", "added\n")
        self.write("tools/ai-team/run-lead.ps1", "changed by someone else\n")
        code, out = self.run_tool("refresh agent status")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "Lead (local): refresh agent status")
        files = sorted(self.git("show", "--name-only", "--format=", "HEAD").split())
        self.assertEqual(files, ["docs/ai/agent-status.md", "docs/ai/research-log.md"])
        self.assertIn("tools/ai-team/run-lead.ps1", self.git("status", "--porcelain"))   # left alone

    def test_refuses_on_any_other_branch(self):
        self.git("checkout", "-q", "-b", "claude/some-work")
        self.write("docs/ai/agent-status.md", "new\n")
        code, out = self.run_tool("x")
        self.assertEqual(code, 1)
        self.assertIn("refused", out)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")

    def test_refuses_when_something_outside_docs_ai_is_staged(self):
        self.write("tools/ai-team/run-lead.ps1", "staged by someone else\n")
        self.git("add", "tools/ai-team/run-lead.ps1")
        self.write("docs/ai/agent-status.md", "new\n")
        code, out = self.run_tool("x")
        self.assertEqual(code, 1)
        self.assertIn("tools/ai-team/run-lead.ps1", out)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")

    def test_takes_no_extra_arguments_and_keeps_an_existing_prefix(self):
        self.write("docs/ai/agent-status.md", "new\n")
        code, _ = self.run_tool("x", "--amend")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")
        code, out = self.run_tool("Lead (local): already prefixed")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "Lead (local): already prefixed")

    def test_refuses_a_staged_rename_into_docs_ai(self):
        self.git("mv", "tools/ai-team/run-lead.ps1", "docs/ai/run-lead.ps1")
        code, out = self.run_tool("x")
        self.assertEqual(code, 1)
        self.assertIn("tools/ai-team/run-lead.ps1", out)      # the deleted source counts as outside docs/ai
        self.assertEqual(self.head(), "base")

    def test_refuses_on_a_detached_head(self):
        self.git("checkout", "-q", "--detach")
        self.write("docs/ai/agent-status.md", "new\n")
        code, out = self.run_tool("x")
        self.assertEqual(code, 1)
        self.assertIn("refused", out)

    def test_refuses_with_unmerged_files_from_a_conflicted_merge(self):
        self.write("docs/ai/agent-status.md", "lead's line\n")
        self.git("commit", "-q", "-am", "Lead (local): mine")
        self.git("checkout", "-q", "main")
        self.write("docs/ai/agent-status.md", "main's line\n")
        self.git("commit", "-q", "-am", "theirs")
        self.git("checkout", "-q", "ai/local-lead")
        self.git("merge", "main", check=False)                 # conflicts in docs/ai/agent-status.md
        code, out = self.run_tool("resolve")
        self.assertEqual(code, 1)
        self.assertIn("unmerged", out)
        self.assertEqual(self.head(), "Lead (local): mine")
        with open(os.path.join(self.d, "docs", "ai", "agent-status.md"), encoding="utf-8") as f:
            self.assertIn("<<<<<<<", f.read())                   # left for a person, not committed

    def test_injected_git_settings_and_planted_hooks_do_not_run(self):
        hooks = os.path.join(self.d, "docs", "ai", "hooks")
        os.makedirs(hooks)
        marker = os.path.join(self.d, "hook-ran")
        with open(os.path.join(hooks, "pre-commit"), "w", newline="\n") as f:
            f.write(f"#!/bin/sh\ntouch '{marker}'\n")
        os.chmod(os.path.join(hooks, "pre-commit"), 0o755)
        self.write("docs/ai/agent-status.md", "new\n")
        env = dict(self.env, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath", GIT_CONFIG_VALUE_0="docs/ai/hooks")
        r = subprocess.run([sys.executable, "-I", SCRIPT, "x"], cwd=self.d, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse(os.path.exists(marker), "a hook ran inside lead_commit.py")
        self.assertEqual(self.head(), "Lead (local): x")

    def test_nothing_to_commit_is_not_an_error(self):
        code, out = self.run_tool("x")
        self.assertEqual(code, 0)
        self.assertIn("nothing to commit", out)


if __name__ == "__main__":
    unittest.main()
