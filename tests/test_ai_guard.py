"""The unattended Lead's shell guard (tools/ai-team/guard/allowlist.py) allows exactly the listed commands and refuses
everything else, including the shapes OpenCode's text rules let through. Pure checks, no LM Studio, no git."""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "tools", "ai-team", "guard")
sys.path.insert(0, GUARD)
import allowlist  # noqa: E402


def verdict(command, workdir=None):
    try:
        allowlist.check({"root": ROOT, "command": command, "workdir": workdir})
        return True
    except allowlist.Refused:
        return False


ALLOWED = (
    # the Lead's own reads and its one comment on #32
    "gh issue list --state all --limit 15",
    "gh issue list --state open --label agent:local-team --limit 5",
    "gh issue view 32",
    "gh issue view 32 --comments",
    "gh pr view 599 --json 'title,state'",
    "gh pr list --state open",
    "gh pr diff 599 --name-only",
    "gh issue comment 32 --body 'Lead (local): CI failed, I will re-run it'",
    "gh issue comment 32 --body \"Lead (local): status refreshed\"",
    "git status --short",
    "git status",
    "git log --oneline -5",
    "git log -n 3 --oneline",
    "git log --oneline origin/main..HEAD",
    "git diff --stat origin/main",
    "git diff origin/main..HEAD",
    "git diff -- docs/ai/agent-status.md",
    "git diff --stat HEAD~1",
    "git show --stat HEAD",
    "git worktree list",
    "git branch --show-current",
    "git rev-parse --short HEAD",
    # the team's scripts and the write path for the Lead's docs
    "python -I tools/ai-team/lead_commit.py 'refresh agent status'",
    "python -I tools/ai-team/guardian/guardian.py status",
    "python tools/ai-team/guardian/guardian.py report",
    "python tools/ai-team/team.py board",
    # the implementation and QA agents' checks
    "python -m unittest tests.test_ai_team_defaults tests.test_ai_guardian",
    "python -m unittest discover -s tests -v",
    "python scripts/guard.py",
    "python3 scripts/guard.py",
)

REFUSED = (
    # redirects and file-writing options
    "git log > x",
    "git status > x",
    "git log --output=x",
    "git show --output=x",
    "git diff --output=x",
    "git diff --no-index a b",
    "git diff HEAD > /tmp/leak",
    # git reading outside the repo, by path shape
    "git show HEAD:secret.env",
    "git diff /etc/passwd README.md",
    "git diff ../x",
    "git diff -- ../../x",
    "git diff -- C:x",
    "git diff ~/.ssh/id_rsa README.md",
    "git diff $HOME/.ssh/id_rsa README.md",
    "git diff --stat ../secret",
    "git -C /etc log",
    # other git writes and other git commands
    "git push",
    "git commit -m x",
    "git add -A",
    "git checkout -- x",
    "git log -1 --format=%H",
    # shell syntax, expansion and chaining
    "git log | head -200",
    "git log && git push",
    "git log; rm -rf x",
    "echo $(id)",
    "echo `id`",
    "git log \"$(id)\"",
    "git status\ngit push",
    "FOO=1 git status",
    "git log 'x",
    "git log 'a'b",
    "git log “status”",
    "git diff ~ README.md",
    # PowerShell 5.1, the shell OpenCode uses on the team's PC
    "git log `; git push",
    "git status $env:USERPROFILE",
    "git log @(1)",
    "git status --% > x",
    "& git status",
    "git log {x}",
    "git status -s , git push",
    "gh issue comment 32 --body 'Lead (local): it''s done'",
    "gh issue comment 32 --body \"Lead (local): $(id)\"",
    "gh issue comment 32 --body \"Lead (local): `$x\"",
    "git log ‘x’",
    "powershell -EncodedCommand ZQBjAGgAbwA=",
    "pwsh -c 'git push'",
    "cmd /c git push",
    # gh outside the list: other repos, bodies from files, approvals, merges, the API
    "gh issue comment 32 --body-file ~/.ssh/config",
    "gh issue comment 32 --repo other/repo --body 'Lead (local): x'",
    "gh issue comment 5 --body 'Lead (local): x'",
    "gh issue comment 32 --body 'hi'",
    "gh issue list --repo other/repo",
    "gh issue list --jq .x",
    "gh issue view 32 --repo x",
    "gh pr view 599 --json title,state",
    "gh issue comment 32 --body 'Lead (local): say \"hi\"'",
    "gh issue view 32; rm -rf /",
    "gh pr review 5 --comment",
    "gh pr merge 5",
    "gh api repos/x",
    # other programs and the agent wakes
    "curl http://x",
    "rm -rf x",
    "python -c 'import os'",
    "python tools/ai-team/wake_agent.py codex --message x",
    "python tools/ai-team/wake_agent.py grok",
    "python -I tools/ai-team/lead_commit.py",
    "python tools/ai-team/lead_commit.py 'x'",
    "python tools/ai-team/team.py start",
    "python -I tools/ai-team/guard/allowlist.py",
    "python -m unittest -k x",
    "python -m unittest",
    "python -m unittest discover",
    "python -m unittest discover -s docs",
    "python -m unittest discover -s tests -p x",
    "python -m unittest docs.ai.test_x",
    "",
)


class GuardTests(unittest.TestCase):
    def test_the_commands_the_team_runs_are_allowed(self):
        for command in ALLOWED:
            self.assertTrue(verdict(command), command)

    def test_everything_else_is_refused(self):
        for command in REFUSED:
            self.assertFalse(verdict(command), command)

    def test_commands_run_from_the_repo_root_only(self):
        # The agents can write under docs/ai/, so a subfolder is refused as well as anything outside the repo.
        self.assertFalse(verdict("git status", workdir="/etc"))
        self.assertFalse(verdict("git status", workdir="../elsewhere"))
        self.assertFalse(verdict("git status", workdir="docs"))
        self.assertFalse(verdict("python -m unittest discover -s tests", workdir="docs/ai"))
        self.assertFalse(verdict("python -I tools/ai-team/lead_commit.py 'x'", workdir="docs/ai"))
        self.assertTrue(verdict("git status", workdir="."))
        self.assertTrue(verdict("git status", workdir=ROOT))
        self.assertTrue(verdict("git status"))

    def test_unattended_runs_cannot_delegate_to_the_implementation_agent(self):
        with open(os.path.join(ROOT, ".opencode", "plugin", "fo4-guard.js"), encoding="utf-8") as f:
            plugin = f.read()
        self.assertIn('process.env.FO4SF_UNATTENDED === "1"', plugin)
        self.assertIn('input.tool === "task"', plugin)
        self.assertIn('"fo4-implement"', plugin)
        with open(os.path.join(ROOT, "tools", "ai-team", "run-lead.ps1"), encoding="utf-8") as f:
            script = f.read()
        self.assertIn("$env:FO4SF_UNATTENDED = '1'", script)
        self.assertLess(script.index("$env:FO4SF_UNATTENDED"), script.index("Start-Process -FilePath $opencode"))

    def test_the_checker_speaks_the_plugins_protocol(self):
        script = os.path.join(GUARD, "allowlist.py")

        def run(payload):
            return subprocess.run([sys.executable, "-I", script], input=payload, capture_output=True, text=True)
        allowed = run(json.dumps({"root": ROOT, "command": "git status --short"}))
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)
        refused = run(json.dumps({"root": ROOT, "command": "git log > x"}))
        self.assertEqual(refused.returncode, 1)
        self.assertFalse(json.loads(refused.stdout)["allowed"])
        self.assertEqual(run("not json").returncode, 1)
        self.assertEqual(run(json.dumps({"root": ROOT})).returncode, 1)

    def test_the_plugin_only_lets_a_clean_exit_through(self):
        with open(os.path.join(ROOT, ".opencode", "plugin", "fo4-guard.js"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"tool.execute.before"', source)
        self.assertIn('["-I", checker]', source)
        self.assertIn('"allowlist.py"', source)
        self.assertIn("if (run.status === 0) return;", source)
        self.assertIn("throw new Error", source)
        self.assertIn('input.tool !== "bash"', source)


if __name__ == "__main__":
    unittest.main()
