"""The local team's model settings agree: config.json's agents, run-lead.ps1's loaded-model check, opencode.json's limits
and load_model.py's defaults name one model at one context, loaded without memory mapping. Text and pure functions only;
no LM Studio."""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = os.path.join(ROOT, "tools", "ai-team")
sys.path.insert(0, TEAM)
import load_model  # noqa: E402  (imports without the lmstudio SDK; main() imports it)


def read(name, root=TEAM):
    with open(os.path.join(root, name), encoding="utf-8") as f:
        return f.read()


AGENTS = ("fo4-implement", "fo4-lead", "fo4-qa", "fo4-research")


def agent_bash_rules(agent):
    """The (pattern, action) bash rules in an agent's frontmatter, in file order. Every key is quoted, so the pattern
    is read from inside the quotes: a pattern may itself contain a colon (git diff*:*), which a split on ':' would
    mangle into a different rule."""
    rules, in_bash = [], False
    for line in read(os.path.join(".opencode", "agents", f"{agent}.md"), ROOT).split("\n---\n", 1)[0].splitlines():
        if line == "  bash:":
            in_bash = True
        elif in_bash and line.startswith("    "):
            m = re.match(r'\s*"(.*)":\s*(\S+)\s*$', line)
            self_check = m or line.strip().startswith("#")
            assert self_check, f"unparsed bash rule: {line!r}"
            if m:
                rules.append((m.group(1), m.group(2)))
        elif line and not line.startswith(" "):
            in_bash = False
    return rules


def merged_bash_rules(agent):
    """The root opencode.json bash rules, then the agent's: OpenCode takes the last rule that matches."""
    return list(json.loads(read("opencode.json", ROOT))["permission"]["bash"].items()) + agent_bash_rules(agent)


def _opencode_regex(pattern):
    """OpenCode's wildcard.ts: normalize backslashes, escape regex metacharacters, '*'->'.*', '?'->'.', and treat a
    trailing ' *' as optional. fnmatch does none of this, so a Windows-only false match would slip past it."""
    escaped = re.sub(r"[.+^${}()|\[\]\\]", lambda m: "\\" + m.group(0), pattern.replace("\\", "/"))
    escaped = escaped.replace("*", ".*").replace("?", ".")
    if escaped.endswith(" .*"):
        escaped = escaped[:-3] + "( .*)?"
    return "^" + escaped + "$"


def verdict(rules, command, win32=False):
    """The action of the last rule that matches the command; OpenCode asks when none does. win32=True adds the
    case-insensitive flag OpenCode uses on Windows, where the team's PC runs (a lowercase -r then matches a -R rule)."""
    flags = re.DOTALL | (re.IGNORECASE if win32 else 0)
    found = "ask"
    for pattern, action in rules:
        if re.search(_opencode_regex(pattern), command.replace("\\", "/"), flags):
            found = action
    return found


class TeamModelTests(unittest.TestCase):
    def test_every_agent_uses_the_loaders_default_model(self):
        agents = json.loads(read("config.json"))["agents"]
        self.assertEqual(sorted(agents), ["fo4-implement", "fo4-lead", "fo4-qa", "fo4-research"])
        self.assertEqual(set(agents.values()), {load_model.DEFAULT_MODEL})

    def test_run_lead_checks_for_that_model(self):
        m = re.search(r"lms ps 2>&1 \| Out-String\) -match '([^']+)'", read("run-lead.ps1"))
        self.assertIsNotNone(m, "run-lead.ps1 has no loaded-model check")
        pattern = m.group(1)
        self.assertRegex(f"{load_model.DEFAULT_MODEL}    {load_model.DEFAULT_MODEL}    IDLE", pattern)
        self.assertNotRegex("qwen3-14b    qwen3-14b    IDLE", pattern)

    def test_unattended_lead_takes_no_qa_reviews(self):
        script = read("run-lead.ps1")
        self.assertNotIn("needs-qa", script, "the unattended Lead must not pick up QA reviews")
        self.assertNotIn("QA (local)", script)
        self.assertIn("Do not call fo4-qa", script)

    def test_start_team_does_not_advise_the_old_16k_context(self):
        self.assertNotIn("16384", read("start-team.ps1"))

    def test_the_configured_ram_levels_keep_the_35b_idle_level_admitted(self):
        sys.path.insert(0, os.path.join(TEAM, "guardian"))
        import policy
        cfg = dict(policy.DEFAULTS, **json.loads(read("config.json"))["guardian"])
        self.assertLess(cfg["caution_pct"], cfg["restrict_pct"])
        self.assertLess(cfg["restrict_pct"], cfg["ram_block_pct"])

        def level(ram):
            snap = {"gpu": {"available": True, "vram_pct": 85.0}, "ram": {"used_pct": ram},
                    "lmstudio": {"reachable": True, "loaded": [{"id": load_model.DEFAULT_MODEL}]},
                    "agents": {"processes": {}}}
            return policy.level(snap, cfg)[0]
        self.assertEqual(level(87.3), "caution")       # the idle level that got job 66 refused at 85%
        self.assertEqual(level(88.9), "caution")       # the working level that held jobs 109-114 at 88%
        self.assertEqual(level(89.5), "restrict")
        self.assertEqual(level(91.0), "block")

    def test_opencode_limits_match_the_loaded_context(self):
        models = json.loads(read("opencode.json", ROOT))["provider"]["guardian"]["models"]
        self.assertEqual(sorted(models), ["fo4-implement", "fo4-lead", "fo4-qa", "fo4-research"])
        for name, model in models.items():
            self.assertEqual(model["limit"]["context"], load_model.DEFAULT_CONTEXT, name)
            self.assertEqual(model["limit"]["output"], 16384, name)
            # OpenCode compacts at context minus min(output, 32000); the Lead's sessions reached 46K tokens
            self.assertGreaterEqual(model["limit"]["context"] - min(model["limit"]["output"], 32000), 46000, name)

    def test_the_unattended_lead_commits_only_through_the_wrapper(self):
        self.assertIn("lead_commit.py", read("run-lead.ps1"))
        lead = read(os.path.join(".opencode", "agents", "fo4-lead.md"), ROOT)
        self.assertRegex(lead, r'"python -I tools/ai-team/lead_commit.py \*": allow')
        self.assertIn("python -I tools/ai-team/lead_commit.py", read("run-lead.ps1"))
        self.assertNotRegex(lead, r'"git (add|commit)[^"]*": allow')   # no raw git writes
        self.assertRegex(lead, r'"git push\*": deny')
        self.assertRegex(lead, r'"gh pr review\*": deny')
        self.assertRegex(lead, r'"gh pr comment\*": deny')
        self.assertRegex(lead, r'"docs/ai/\*\*": allow')         # the only files it may edit

    def test_run_lead_checks_branch_and_in_progress_before_pulling_and_logs_the_pull(self):
        script = read("run-lead.ps1")
        self.assertNotRegex(script, r"pull[^\n]*2>\$null")          # a failed pull is no longer silent
        self.assertIn("git pull of main failed", script)
        self.assertRegex(script, r"ls-files -u[\s\S]{0,200}skipped: unmerged files")
        self.assertRegex(script, r"unmerged files[^\n]*\$pull")     # the stash/pull output is logged on that skip
        # the branch and the in-progress-operation checks run BEFORE the pull, so no other branch is rebased and no
        # stopped rebase/merge/cherry-pick starts a session on a half-done state (the pull itself can leave those)
        self.assertIn("CHERRY_PICK_HEAD", script)
        self.assertLess(script.index("rev-parse --abbrev-ref HEAD"), script.index("pull -q --rebase"))
        self.assertLess(script.index("CHERRY_PICK_HEAD"), script.index("pull -q --rebase"))

    def test_start_team_names_the_loaders_context(self):
        self.assertIn(f"load_model.py ({load_model.DEFAULT_CONTEXT // 1024}K", read("start-team.ps1"))

    def test_provider_header_timeout_outlasts_guardians_queue_wait(self):
        # OpenCode gives up when response headers take longer than headerTimeout. Guardian holds a queued request
        # for queue_wait_s. The hold has to end first, or the Lead's session dies inside the hold.
        header_ms = json.loads(read("opencode.json", ROOT))["provider"]["guardian"]["options"]["headerTimeout"]
        queue_wait_s = json.loads(read("config.json"))["guardian"]["queue_wait_s"]
        self.assertGreater(header_ms, queue_wait_s * 1000)


class LoadConfigTests(unittest.TestCase):
    def test_defaults_are_64k_unquantized_and_unmapped(self):
        self.assertEqual(load_model.DEFAULT_MODEL, "qwen3.6-35b-a3b")
        cfg = load_model.load_config()
        self.assertEqual(cfg, {"contextLength": 65536, "tryMmap": False, "keepModelInMemory": False,
                               "flashAttention": True, "llamaKCacheQuantizationType": "f16",
                               "llamaVCacheQuantizationType": "f16"})

    def test_the_14b_fallback_loads_as_before(self):
        cfg = load_model.load_config(32768, "q8_0", 1.0)
        self.assertEqual(cfg, {"contextLength": 32768, "tryMmap": False, "keepModelInMemory": False,
                               "gpu": {"ratio": 1.0}, "flashAttention": True,
                               "llamaKCacheQuantizationType": "q8_0", "llamaVCacheQuantizationType": "q8_0"})


class LeadPromptTests(unittest.TestCase):
    def test_the_commands_the_lead_is_told_to_run_are_allowed(self):
        # An unattended run refuses any command its bash rules do not allow, so the prompt's examples must match them.
        text = read(os.path.join(".opencode", "agents", "fo4-lead.md"), ROOT)
        self.assertIn("Stay in your worktree", text)
        rules = agent_bash_rules("fo4-lead")
        for command in ("gh issue list --state all --limit 15", "gh issue view 32",
                        "python tools/ai-team/guardian/guardian.py status",
                        "python -I tools/ai-team/lead_commit.py 'refresh agent status'"):
            self.assertEqual(verdict(rules, command), "allow", command)
        # a redirect behind an allowed command (OpenCode matches it as part of the text) is denied, as is lead_commit
        # without -I and any raw git write
        for command in ("git log -1 --format=tformat:x > tools/ai-team/argparse.py",
                        "python -I tools/ai-team/lead_commit.py x > a", "gh issue view 32 2>&1",
                        "python tools/ai-team/lead_commit.py x", "git commit -m x"):
            self.assertIn(verdict(rules, command), ("deny", "ask"), command)
        self.assertEqual(verdict(rules, "git log -1 > .git/hooks/pre-commit"), "deny")
        self.assertEqual(verdict(rules, "git log -1 --format=tformat:x --output=tools/ai-team/guardian/argparse.py"), "deny")
        self.assertEqual(verdict(rules, "git diff --no-index /dev/null ../../outside/secret.txt"), "deny")
        # pipe filters stay unallowed (with a path argument they would read files outside the worktree); the prompt
        # tells the Lead to run gh and git without pipes instead
        for command in ("head -200", "grep -r token C:/Users"):
            self.assertEqual(verdict(rules, command), "ask", command)
        self.assertIn("without pipes", read("run-lead.ps1"))
        for command in ("gh pr review 5 -c -b hi", "gh pr review 5 --approve", "gh pr comment 5 -b hi"):
            self.assertEqual(verdict(rules, command), "deny", command)


class BashRuleTests(unittest.TestCase):
    # Each command writes a file (a redirect, an --output flag, --no-index) or reads one outside the repo. The last
    # six reach outside without the --no-index flag: git switches to no-index on its own when a path is outside the
    # worktree, so a drive-letter path, a leading-slash absolute path, a ~ or $ the shell expands, and a ../ climb all
    # read an outside file.
    WRITES_OR_READS = (
        "git log > x", "git status > x", "git diff >> x", "git log --output=x", "git log -p --output x",
        "git show --output=x", "git diff --output=x", "git diff --no-index ~/.ssh/config x",
        "python -m unittest > x", "python scripts/guard.py > x",
        "python tools/ai-team/team.py status > tools/ai-team/team.py", "python tools/ai-team/team.py status --output x",
        "git diff C:\\Users\\great\\.ssh\\id_rsa README.md", "git diff /etc/passwd README.md",
        "git diff ../../other-worktree/secret.txt README.md", "git diff ~/.ssh/id_rsa README.md",
        "git diff $HOME/.ssh/id_rsa README.md", "git diff $env:USERPROFILE/.ssh/id_rsa README.md",
    )
    # gh issue comment and gh pr review: a local file as the body, another repo, an edit, a delete, or an approval or
    # request-changes through either the long flag or its short form (-a, -r), with --comment only in the body text.
    POSTS = (
        "gh issue comment 32 --body-file ~/.ssh/config", "gh issue comment 32 -F secret.txt",
        "gh issue comment 32 -R other/repo --body hi", "gh issue comment 32 --repo other/repo --body hi",
        "gh issue comment 32 --body hi --edit-last", "gh issue comment 32 --delete-last --yes",
        "gh pr review 5 --comment --body-file x", "gh pr review 5 --comment -R other/repo",
        "gh pr review 5 --comment --approve", "gh pr review 5 -a --body 'looks like --comment'",
        "gh pr review 5 -r --body 'needs work, see --comment'",
    )

    def test_no_agent_can_write_a_file_or_read_one_outside_the_repo(self):
        for agent in AGENTS:
            for rules in (agent_bash_rules(agent), merged_bash_rules(agent)):
                for win32 in (False, True):
                    for command in self.WRITES_OR_READS:
                        self.assertNotEqual(verdict(rules, command, win32), "allow", (agent, win32, command))

    def test_the_lead_cannot_post_a_local_file_approve_or_target_another_repo(self):
        for rules in (agent_bash_rules("fo4-lead"), merged_bash_rules("fo4-lead")):
            for win32 in (False, True):
                for command in self.POSTS:
                    self.assertNotEqual(verdict(rules, command, win32), "allow", (win32, command))

    def test_the_lead_can_still_read_and_comment(self):
        rules = agent_bash_rules("fo4-lead")
        # A normal comment whose body contains "re-run" must not be caught by the -R/-F denies, on Windows too, where
        # the match ignores case ("re-run" has "-r" but not " -r", so a leading-space anchor keeps it clear).
        for win32 in (False, True):
            for command in ("gh issue list --state all --limit 15", "gh issue view 32",
                            "gh issue comment 32 --body 'Lead (local): CI failed, I will re-run it'",
                            "git log --oneline -5", "git diff --stat origin/main",
                            "git diff origin/main..HEAD", "git diff -- docs/ai/agent-status.md",
                            "python tools/ai-team/team.py status"):
                self.assertEqual(verdict(rules, command, win32), "allow", (win32, command))

    def test_each_agent_ends_its_bash_rules_with_the_redirect_deny(self):
        # The last matching rule wins, so no allow may come after the redirect deny.
        for agent in AGENTS:
            self.assertEqual(agent_bash_rules(agent)[-1], ("*>*", "deny"), agent)


if __name__ == "__main__":
    unittest.main()
