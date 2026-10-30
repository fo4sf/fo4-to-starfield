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
            self.assertEqual(model["limit"]["output"], 32768, name)

    def test_opencode_waits_longer_than_the_guardian_holds_a_request(self):
        options = json.loads(read("opencode.json", ROOT))["provider"]["guardian"]["options"]
        queue_wait_ms = json.loads(read("config.json"))["guardian"]["queue_wait_s"] * 1000
        # the guardian sends no headers until it admits a job (up to queue_wait_s), then the prompt is read
        self.assertGreater(options["headerTimeout"], queue_wait_ms + 120000)
        self.assertGreater(options["chunkTimeout"], queue_wait_ms)
        self.assertIs(options["timeout"], False)          # a long answer streams for longer than any fixed total

    def test_the_unattended_lead_stays_in_its_worktree_and_commits_only_through_the_wrapper(self):
        self.assertIn("never cd anywhere", read("run-lead.ps1"))
        self.assertIn("lead_commit.py", read("run-lead.ps1"))
        lead = read(os.path.join(".opencode", "agents", "fo4-lead.md"), ROOT)
        self.assertRegex(lead, r'"python tools/ai-team/lead_commit.py \*": allow')
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

    def test_start_team_names_the_loaders_context(self):
        self.assertIn(f"load_model.py ({load_model.DEFAULT_CONTEXT // 1024}K", read("start-team.ps1"))


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


if __name__ == "__main__":
    unittest.main()
