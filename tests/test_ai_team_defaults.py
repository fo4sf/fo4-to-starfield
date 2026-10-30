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

    def test_redirects_and_git_file_options_are_denied_last_everywhere(self):
        # OpenCode takes the last matching rule (agent file after the global block) and matches a redirect as part of
        # the command's text; git's --output writes and --no-index reads files without a '>'
        last = [("*>*", "deny"), ("*--output*", "deny"), ("*--no-index*", "deny")]
        bash = json.loads(read("opencode.json", ROOT))["permission"]["bash"]
        self.assertEqual(list(bash.items())[-3:], last)
        for agent in ("fo4-lead", "fo4-research", "fo4-qa", "fo4-implement"):
            front = read(os.path.join(".opencode", "agents", agent + ".md"), ROOT).split("\n---", 1)[0]
            rules = [l.strip() for l in front.split("  bash:", 1)[1].splitlines() if l.startswith("    ")]
            self.assertEqual(rules[-3:], [f'"{p}": {a}' for p, a in last], agent)

    def test_the_unattended_lead_commits_only_through_the_wrapper(self):
        self.assertIn("lead_commit.py", read("run-lead.ps1"))
        lead = read(os.path.join(".opencode", "agents", "fo4-lead.md"), ROOT)
        self.assertRegex(lead, r'"python -P tools/ai-team/lead_commit.py \*": allow')
        self.assertIn("python -P tools/ai-team/lead_commit.py", read("run-lead.ps1"))
        self.assertNotRegex(lead, r'"git (add|commit)[^"]*": allow')   # no raw git writes
        self.assertRegex(lead, r'"git push\*": deny')
        self.assertRegex(lead, r'"gh pr review\*": deny')
        self.assertRegex(lead, r'"gh pr comment\*": deny')
        self.assertRegex(lead, r'"docs/ai/\*\*": allow')         # the only files it may edit

    def test_run_lead_logs_a_failed_pull_and_skips_on_unmerged_files(self):
        script = read("run-lead.ps1")
        self.assertNotRegex(script, r"pull[^\n]*2>\$null")          # a failed pull is no longer silent
        self.assertIn("git pull of main failed", script)
        self.assertRegex(script, r"ls-files -u[\s\S]{0,200}skipped: unmerged files")
        self.assertRegex(script, r"rev-parse --abbrev-ref HEAD[\s\S]{0,200}'ai/local-lead'[\s\S]{0,200}skipped")
        # the branch is checked before the pull, so a moved worktree's branch is never rebased
        self.assertLess(script.index("rev-parse --abbrev-ref HEAD"), script.index("pull -q --rebase"))

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
        import fnmatch
        text = read(os.path.join(".opencode", "agents", "fo4-lead.md"), ROOT)
        self.assertIn("Stay in your worktree", text)
        rules, in_bash = [], False
        for line in text.split("\n---\n", 1)[0].splitlines():
            if line == "  bash:":
                in_bash = True
            elif in_bash and line.startswith("    "):
                pattern, _, action = line.strip().partition(":")
                rules.append((pattern.strip().strip('"'), action.strip()))
            elif line and not line.startswith(" "):
                in_bash = False

        def verdict(command):
            found = "ask"
            for pattern, action in rules:
                if fnmatch.fnmatchcase(command, pattern):
                    found = action
            return found
        for command in ("gh issue list --state all --limit 15", "gh issue view 32",
                        "python tools/ai-team/guardian/guardian.py status",
                        "python -P tools/ai-team/lead_commit.py 'refresh agent status'"):
            self.assertEqual(verdict(command), "allow", command)
        # a redirect behind an allowed command (as OpenCode matches it: the redirect is part of the text) is denied
        for command in ("git log -1 --format=tformat:x > tools/ai-team/argparse.py",
                        "python -P tools/ai-team/lead_commit.py x > a", "gh issue view 32 2>&1",
                        "python tools/ai-team/lead_commit.py x"):
            self.assertIn(verdict(command), ("deny", "ask"), command)
        self.assertEqual(verdict("git log -1 > .git/hooks/pre-commit"), "deny")
        self.assertEqual(verdict("git log -1 --format=tformat:x --output=tools/ai-team/guardian/argparse.py"), "deny")
        self.assertEqual(verdict("git diff --no-index /dev/null ../../outside/secret.txt"), "deny")
        # pipe filters stay unallowed (with a path argument they would read files outside the worktree); the prompt
        # tells the Lead to run gh and git without pipes instead
        for command in ("head -200", "grep -r token C:/Users"):
            self.assertEqual(verdict(command), "ask", command)
        self.assertIn("without pipes", read("run-lead.ps1"))
        for command in ("gh pr review 5 -c -b hi", "gh pr review 5 --approve", "gh pr comment 5 -b hi"):
            self.assertEqual(verdict(command), "deny", command)
        self.assertEqual(verdict("git commit -m x"), "ask")    # raw git writes stay unallowed


if __name__ == "__main__":
    unittest.main()
