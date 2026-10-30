"""The owner's side of the local team: the model pick (models.py) that the proxy and OpenCode follow, the guard's file
write checks and the owner's-terminal commit wrapper (agent_git.py), the terminal and menu scripts, the team's commands
and skill, and Claude Code's skills. Temp folders and synthetic git repos; no LM Studio, no network."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAM = os.path.join(ROOT, "tools", "ai-team")
sys.path.insert(0, TEAM)
sys.path.insert(0, os.path.join(TEAM, "guard"))
sys.path.insert(0, os.path.join(TEAM, "guardian"))
import allowlist  # noqa: E402
import models     # noqa: E402
import proxy      # noqa: E402
import store      # noqa: E402

AGENTS = ("fo4-implement", "fo4-lead", "fo4-qa", "fo4-research")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def frontmatter(text):
    """The simple key: value lines between the leading --- markers. A value is one double-quoted string, or a plain one
    with nothing YAML reads differently: ' #' starts a comment there and a second ': ' is an error."""
    head = text.split("\n---\n", 1)[0]
    assert head.startswith("---\n"), "no frontmatter"
    out = {}
    for line in head[4:].splitlines():
        if ": " not in line or line.startswith(" "):
            continue
        key, value = line.split(": ", 1)
        if value.startswith('"'):
            assert value.endswith('"') and '"' not in value[1:-1] and "\\" not in value, line
            value = value[1:-1]
        else:
            assert " #" not in value and ": " not in value and not value.startswith(("'", "[", "{", "&", "*", "!")), line
        out[key] = value
    return out


def allowed(command, owner_present=False):
    try:
        allowlist.check({"root": ROOT, "command": command, "owner_present": owner_present})
        return True
    except allowlist.Refused:
        return False


class TempState(unittest.TestCase):
    """store.STATE and store.DB pointed at a temp folder, so a pick and the job table are the test's own."""
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state, ignore_errors=True)
        saved = (store.STATE, store.DB)
        store.STATE, store.DB = self.state, os.path.join(self.state, "guardian.db")
        self.addCleanup(lambda: (setattr(store, "STATE", saved[0]), setattr(store, "DB", saved[1])))


class ModelPickTests(TempState):
    def test_every_preset_is_a_valid_setup(self):
        cfg = models.read_config()
        self.assertIn(cfg["default_model"], cfg["models"])
        for name in cfg["models"]:
            s = models.preset(name, cfg)
            self.assertLessEqual(s["output"], s["context"] // 2, name)

    def test_the_default_preset_matches_opencode_json(self):
        # A plain `opencode` run (no pick passed in) must still compact at the default window.
        cfg = models.read_config()
        default = models.preset(cfg["default_model"], cfg)
        provider = json.loads(read("opencode.json"))["provider"]["guardian"]["models"]
        for agent in AGENTS:
            self.assertEqual(provider[agent]["limit"], {"context": default["context"], "output": default["output"]})

    def test_no_pick_means_the_default_and_a_broken_row_too(self):
        cfg = models.read_config()
        self.assertEqual(models.current(cfg)["preset"], cfg["default_model"])
        c = store.connect()
        self.addCleanup(c.close)
        for bad in ("{not json", '"a string"', '{"model": "x"}'):
            c.execute("INSERT OR REPLACE INTO control VALUES (?, ?, 0)", (store.PICK, bad))
            self.assertEqual(models.current(cfg)["preset"], cfg["default_model"], bad)
        self.assertIsNone(store.picked_model())

    def test_a_pick_reaches_the_proxy_and_opencode(self):
        self.assertEqual(models.main(["pick", "qwen3-14b", "--no-load"]), 0)
        self.assertEqual(store.picked_model(), "qwen3-14b")
        saved = proxy.CFG
        self.addCleanup(setattr, proxy, "CFG", saved)
        proxy.CFG = {"agents": {a: "qwen3.6-35b-a3b" for a in AGENTS}}
        self.assertEqual(proxy._agent_and_model("fo4-lead"), ("fo4-lead", "qwen3-14b"))
        self.assertEqual(proxy._agent_and_model("other-model"), ("unknown", "other-model"))
        oc = models.opencode_config(models.current())
        for agent in AGENTS:
            self.assertEqual(oc["provider"]["guardian"]["models"][agent]["limit"], {"context": 32768, "output": 8192})

    def test_without_a_pick_the_proxy_keeps_the_config_map(self):
        saved = proxy.CFG
        self.addCleanup(setattr, proxy, "CFG", saved)
        proxy.CFG = {"agents": {"fo4-lead": "qwen3.6-35b-a3b"}}
        self.assertEqual(proxy._agent_and_model("fo4-lead"), ("fo4-lead", "qwen3.6-35b-a3b"))

    def test_any_downloaded_model_with_checked_numbers(self):
        self.assertEqual(models.main(["pick", "--model", "qwen/qwen3-8b", "--context", "16384", "--no-load"]), 0)
        self.assertEqual(models.current()["output"], 4096)
        for bad in (["pick", "--model", "a;b", "--context", "16384", "--no-load"],
                    ["pick", "--model", "x", "--context", "1024", "--no-load"],
                    ["pick", "--model", "x", "--context", "16384", "--output", "9000", "--no-load"],
                    ["pick", "--model", "x", "--no-load"],
                    ["pick", "no-such-preset", "--no-load"]):
            self.assertEqual(models.main(bad), 1, bad)
        self.assertEqual(store.picked_model(), "qwen/qwen3-8b")         # a refused pick keeps the last good one

    def test_a_load_waits_for_running_requests(self):
        c = store.connect()
        self.addCleanup(c.close)
        c.execute("INSERT INTO jobs (agent, model, kind, status, created) VALUES ('fo4-lead', 'm', 'chat', 'running', 0)")
        with self.assertRaises(models.PickError):
            models.load(models.preset("qwen3-14b"), models.read_config())
        self.assertIsNone(store.get_hold(c))                            # the hold is let go again
        self.assertIsNone(store.picked_model())


def admission(c, snapshot=lambda *_: {}):
    """The proxy's decision for one new job, with the resource policy set to admit and no queue wait."""
    saved = dict(proxy.CFG), proxy.policy.admit, proxy.resources.snapshot
    proxy.CFG.clear()
    proxy.CFG.update(queue_wait_s=0)
    proxy.policy.admit = lambda *_: ("admit", "normal", [])
    proxy.resources.snapshot = snapshot
    try:
        job = c.execute("INSERT INTO jobs (agent, model, kind, status, created, heartbeat) "
                        "VALUES ('fo4-lead', 'm', 'chat', 'queued', 0, 0)").lastrowid
        decision = proxy.Handler._wait_for_admission(None, c, job)
        if decision == "admit":
            proxy.STATE["running"] -= 1
        return decision
    finally:
        proxy.CFG.clear()
        proxy.CFG.update(saved[0])
        proxy.policy.admit, proxy.resources.snapshot = saved[1], saved[2]


class ModelLoadTests(TempState):
    """models.load with LM Studio replaced by a fake that records what it was asked to do."""
    def setUp(self):
        super().setUp()
        self.c = store.connect()
        self.addCleanup(self.c.close)
        self.cfg = models.read_config()
        self.calls, self.during = [], None
        saved = models.load_model.load
        self.addCleanup(setattr, models.load_model, "load", saved)
        models.load_model.load = self.fake_load

    def fake_load(self, model, cfg_lm, unload=()):
        self.calls.append((model, cfg_lm["contextLength"], set(unload)))
        self.hold_during = store.get_hold(self.c)
        if self.during:
            self.during()
        return model

    def test_a_load_holds_the_proxy_saves_the_pick_and_lets_go(self):
        self.assertEqual(models.load(models.preset("qwen3-14b"), self.cfg), "qwen3-14b")
        self.assertEqual(self.hold_during[0], "loading")
        self.assertIsNone(store.get_hold(self.c))
        self.assertEqual(store.picked_model(), "qwen3-14b")
        model, context, unload = self.calls[0]
        self.assertEqual((model, context), ("qwen3-14b", 32768))
        self.assertIn("qwen3.6-35b-a3b", unload)
        self.assertNotIn("qwen3-14b", unload)

    def test_switching_away_from_a_custom_pick_unloads_it(self):
        models.save(models.setup("qwen/qwen3-8b", 16384))
        models.load(models.preset("qwen3-14b"), self.cfg)
        self.assertIn("qwen/qwen3-8b", self.calls[0][2])

    def test_the_owners_pause_or_stop_during_a_load_stays(self):
        for mode in ("paused", "stopped"):
            store.set_mode(self.c, "running")
            self.during = lambda m=mode: store.set_mode(self.c, m)
            models.load(models.preset("qwen3-14b"), self.cfg)
            self.assertEqual(store.get_mode(self.c), mode)

    def test_a_failed_load_keeps_the_old_pick_and_the_proxy_refuses(self):
        models.save(models.preset("qwen3.6-35b"))

        def boom():
            raise RuntimeError("out of memory")
        self.during = boom
        with self.assertRaises(models.PickError) as e:
            models.load(models.preset("qwen3-14b"), self.cfg)
        self.assertIn("out of memory", str(e.exception))
        hold = store.get_hold(self.c)
        self.assertEqual(hold[0], "failed")
        self.assertIn("out of memory", hold[1])
        self.assertEqual(store.picked_model(), "qwen3.6-35b-a3b")
        self.assertIn("not loaded", admission(self.c))
        self.during = None                                              # the next load that works clears it
        models.load(models.preset("qwen3-14b"), self.cfg)
        self.assertIsNone(store.get_hold(self.c))
        self.assertEqual(admission(self.c), "admit")

    def test_one_load_at_a_time_and_a_dead_loaders_hold_expires(self):
        self.assertTrue(store.take_hold(self.c, "qwen3-14b"))
        with self.assertRaises(models.PickError):
            models.load(models.preset("qwen3-14b"), self.cfg)
        self.assertEqual(self.calls, [])
        self.assertTrue(admission(self.c).startswith("rejected (waited"))  # a live load: requests wait
        self.c.execute("UPDATE control SET t=t-? WHERE key=?", (store.HOLD_FRESH_S + 1, store.HOLD))
        self.assertEqual(store.get_hold(self.c)[0], "failed")
        self.assertIn("did not finish", admission(self.c))
        models.load(models.preset("qwen3-14b"), self.cfg)
        self.assertIsNone(store.get_hold(self.c))

    def test_a_job_cannot_start_once_the_hold_is_in(self):
        # The hold lands after the proxy's own hold check, before its update: the conditional update still refuses.
        self.assertTrue(admission(self.c, lambda *_: (store.take_hold(self.c, "m"), {})[1]).startswith("rejected (waited"))
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0], 0)

    def test_ensure_reloads_a_model_loaded_at_another_context(self):
        saved = models.loaded_contexts
        self.addCleanup(setattr, models, "loaded_contexts", saved)
        models.save(models.preset("qwen3-14b"))
        for loaded, reloads in (({"qwen3-14b": 32768}, False), ({"qwen3-14b": 4096}, True), ({}, True),
                                ({"qwen3-14b": None}, False)):
            self.calls.clear()
            models.loaded_contexts = lambda loaded=loaded: dict(loaded)
            self.assertEqual(models.main(["ensure"]), 0)
            self.assertEqual(bool(self.calls), reloads, loaded)
        store.fail_hold(self.c, "x")                                    # after a failed load, ensure loads again
        self.calls.clear()
        models.loaded_contexts = lambda: {"qwen3-14b": 32768}
        self.assertEqual(models.main(["ensure"]), 0)
        self.assertTrue(self.calls)


class WriteGuardTests(unittest.TestCase):
    def verdict(self, *paths):
        try:
            allowlist.check({"root": ROOT, "write": list(paths)})
            return True
        except allowlist.Refused:
            return False

    def test_the_agents_own_files_are_writable(self):
        for p in ("docs/ai/agent-status.md", "docs/ai/research-log.md", "src/fo4sf/x.py", "tests/test_x.py",
                  "./docs/ai/x.md"):
            self.assertTrue(self.verdict(p), p)

    def test_the_teams_rules_and_tools_and_anything_outside_are_refused(self):
        for p in ("docs/ai/AGENTS.md", "src/CLAUDE.md", "docs/Context.md", "opencode.jsonc", "tui.json", "tools",
                  "docs/ai", "tools/ai-team/", "docs/..", "opencode.json", "OpenCode.json", "AGENTS.md", "agents.md",
                  ".opencode/plugin/fo4-guard.js",
                  ".OpenCode/agents/fo4-lead.md", ".opencode/commands/next.md", ".claude/skills/x/SKILL.md",
                  ".github/workflows/ci.yml", ".git/config", "tools/ai-team/guard/allowlist.py",
                  "tools/ai-team/run-lead.ps1", "Tools/AI-Team/menu.ps1", "scripts/guard.py",
                  "docs/CODEX-HANDOFF.md", "docs/../opencode.json", "../elsewhere/x", "/etc/passwd", ".", ""):
            self.assertFalse(self.verdict(p), p)
        self.assertFalse(self.verdict("docs/ai/x.md", "opencode.json"))
        self.assertFalse(self.verdict())

    def test_the_windows_path_rules_for_writes(self):
        # The PC's case, with Windows path rules (ntpath): case, backslashes and drive paths are all one file to NTFS.
        import ntpath
        from unittest import mock
        root = "D:\\Work\\fo4-to-starfield-wt\\local-terminal"

        def ok(p):
            with mock.patch.object(allowlist.os, "path", ntpath):
                try:
                    allowlist.check({"root": root, "directory": root, "write": [p]})
                    return True
                except allowlist.Refused:
                    return False
        for good in ("docs\\ai\\x.md", "docs/ai/x.md", root + "\\docs\\ai\\x.md", "src\\fo4sf\\x.py"):
            self.assertTrue(ok(good), good)
        for bad in ("OPENCODE.JSON", "Docs\\AI\\Agents.md", "tools\\AI-Team\\x.py", root + "\\.git\\config",
                    ".OpenCode\\plugin\\x.js", "D:\\Work\\other\\x", "..\\x", "C:\\x", "docs\\..\\opencode.jsonc"):
            self.assertFalse(ok(bad), bad)

    def test_writes_need_a_session_at_the_root(self):
        # A write's relative path follows the session's folder, so a session in a subfolder could reach a guarded file
        # by a path that looks harmless from the root.
        for directory, ok in ((ROOT, True), (os.path.join(ROOT, ".opencode"), False), (os.path.join(ROOT, "docs"), False)):
            try:
                allowlist.check({"root": ROOT, "directory": directory, "write": ["plugin/x.js"]})
                self.assertTrue(ok, directory)
            except allowlist.Refused:
                self.assertFalse(ok, directory)


class OwnerTerminalCommandTests(unittest.TestCase):
    WRAPPER = ("python -I tools/ai-team/agent_git.py branch ai/123-door-fix",
               "python -I tools/ai-team/agent_git.py commit 'Implement (local): fix the clamp' src/a.py tests/test_a.py")

    def test_the_wrapper_runs_only_in_the_owners_terminal(self):
        for command in self.WRAPPER:
            self.assertTrue(allowed(command, owner_present=True), command)
            self.assertFalse(allowed(command), command)

    def test_the_wrapper_takes_only_its_two_forms(self):
        for command in ("python tools/ai-team/agent_git.py branch ai/x",          # without -I
                        "python -I tools/ai-team/agent_git.py branch main",
                        "python -I tools/ai-team/agent_git.py branch ai/X",
                        "python -I tools/ai-team/agent_git.py branch ai/a/b",
                        "python -I tools/ai-team/agent_git.py commit '-x' a.py",
                        "python -I tools/ai-team/agent_git.py commit 'x'",
                        "python -I tools/ai-team/agent_git.py commit 'x' ../a.py",
                        "python -I tools/ai-team/agent_git.py push",
                        "git commit -m x", "git add -A", "git switch -c ai/x", "git push"):
            self.assertFalse(allowed(command, owner_present=True), command)

    def test_a_handoff_to_claude_comes_only_from_the_owners_terminal(self):
        for text in ("Lead (local): for Claude: done", "Lead (local): For  claude: done", "Lead (local):  FOR Claude x"):
            command = f"gh issue comment 32 --body '{text}'"
            self.assertTrue(allowed(command, owner_present=True), text)
            self.assertFalse(allowed(command), text)
        self.assertTrue(allowed("gh issue comment 32 --body 'Lead (local): refreshed agent status'"))

    def test_owner_present_must_be_true_not_just_present(self):
        try:
            allowlist.check({"root": ROOT, "command": self.WRAPPER[0], "owner_present": "1"})
            self.fail("a string flag was taken as the owner's terminal")
        except allowlist.Refused:
            pass


class AgentGitTests(unittest.TestCase):
    SCRIPT = os.path.join(TEAM, "agent_git.py")

    def setUp(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        empty = os.path.join(home, "empty.gitconfig")
        open(empty, "w").close()
        self.env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home, GIT_CONFIG_GLOBAL=empty, GIT_CONFIG_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        self.env.pop("FO4SF_UNATTENDED", None)
        self.d = os.path.join(home, "repo")
        os.makedirs(self.d)
        self.git("init", "-q", "-b", "main")
        self.write("src/a.py", "old\n")
        self.write("opencode.json", "{}\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")      # as fetched: new branches start here

    def git(self, *a):
        return subprocess.run(["git", "-C", self.d, *a], capture_output=True, text=True, check=True, env=self.env).stdout

    def write(self, rel, text):
        p = os.path.join(self.d, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def run_tool(self, *args, env=None):
        r = subprocess.run([sys.executable, "-I", self.SCRIPT, *args], cwd=self.d, capture_output=True, text=True,
                           env=env or self.env)
        return r.returncode, r.stdout

    def test_branch_then_commit_only_the_named_files(self):
        self.assertEqual(self.run_tool("branch", "ai/7-clamp")[0], 0)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "ai/7-clamp")
        self.write("src/a.py", "new\n")
        self.write("src/b.py", "added\n")
        self.write("src/c.py", "not named\n")
        code, out = self.run_tool("commit", "fix the clamp", "src/a.py", "src/b.py")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "Implement (local): fix the clamp")
        self.assertEqual(sorted(self.git("show", "--name-only", "--format=", "HEAD").split()), ["src/a.py", "src/b.py"])
        self.assertIn("src/c.py", self.git("status", "--porcelain"))
        self.assertEqual(self.run_tool("commit", "Lead (local): notes", "src/c.py")[0], 0)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "Lead (local): notes")
        # The next issue's branch starts from main, not from this one.
        self.assertEqual(self.run_tool("branch", "ai/8-next")[0], 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.git("rev-parse", "origin/main"))

    def test_paths_are_literal(self):
        self.git("checkout", "-q", "-b", "ai/9-x")
        self.write("opencode.json", '{"x": 1}\n')
        self.write("src/a.py", "new\n")
        for spec in ("*.json", ":/opencode.json", ":(glob)*.json", "src/*"):
            self.assertEqual(self.run_tool("commit", "x", spec)[0], 1, spec)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")

    def test_refusals(self):
        self.write("src/a.py", "new\n")
        self.assertEqual(self.run_tool("commit", "x", "src/a.py")[0], 1)                 # on main
        self.assertEqual(self.run_tool("branch", "ai/local-lead")[0], 1)                 # before it exists
        self.assertNotIn("ai/local-lead", self.git("branch", "--list"))
        self.git("checkout", "-q", "-b", "ai/local-lead")
        self.assertEqual(self.run_tool("commit", "x", "src/a.py")[0], 1)                 # the Lead's branch
        self.git("checkout", "-q", "-b", "ai/8-x")
        self.write("opencode.json", '{"x": 1}\n')
        self.assertEqual(self.run_tool("commit", "x", "opencode.json")[0], 1)            # a protected path
        self.assertEqual(self.run_tool("commit", "x", "../x")[0], 1)
        self.assertEqual(self.run_tool("branch", "main2")[0], 1)
        unattended = dict(self.env, FO4SF_UNATTENDED="1")
        self.assertEqual(self.run_tool("commit", "x", "src/a.py", env=unattended)[0], 1)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")

    def test_no_hook_runs(self):
        hook = os.path.join(self.d, ".git", "hooks", "post-checkout")
        with open(hook, "w") as f:
            f.write("#!/bin/sh\ntouch hook-ran\n")
        os.chmod(hook, 0o755)
        self.assertEqual(self.run_tool("branch", "ai/9-x")[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.d, "hook-ran")))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class PluginTests(unittest.TestCase):
    """The real plugin, loaded in node and driven through its hook, with the real checker behind it."""
    HARNESS = """
const mod = await import(process.argv[2]);
const hooks = await mod.default({ worktree: process.argv[3], directory: process.argv[5] || process.argv[3] });
const out = [];
for (const [tool, args] of JSON.parse(process.argv[4])) {
  try { await hooks["tool.execute.before"]({ tool }, { args }); out.push("allow"); }
  catch (e) { out.push("refuse"); }
}
console.log(JSON.stringify(out));
"""

    def hook(self, calls, directory=None, **env):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        plugin = os.path.join(d, "fo4-guard.mjs")          # .mjs: node loads it as a module whatever its version
        shutil.copy(os.path.join(ROOT, ".opencode", "plugin", "fo4-guard.js"), plugin)
        harness = os.path.join(d, "harness.mjs")
        with open(harness, "w") as f:
            f.write(self.HARNESS)
        e = {k: v for k, v in os.environ.items() if not k.startswith("FO4SF_")}
        e.update(FO4SF_PYTHON=sys.executable, **env)
        r = subprocess.run(["node", harness, "file://" + plugin, ROOT, json.dumps(calls), directory or ROOT],
                           capture_output=True, text=True, env=e, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_writes_and_commands_go_through_the_checker(self):
        calls = [["bash", {"command": "git status"}], ["bash", {"command": "git push"}],
                 ["edit", {"filePath": "docs/ai/agent-status.md"}], ["edit", {"filePath": "opencode.json"}],
                 ["write", {"filePath": ".OpenCode/plugin/x.js"}],
                 ["apply_patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.py\n*** End Patch"}],
                 ["apply_patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.py\n"
                                               "*** Move to: tools/ai-team/x.py\n*** End Patch"}],
                 ["apply_patch", {"patchText": "no file named"}], ["read", {"filePath": "opencode.json"}],
                 ["apply_patch", {"patchText": "*** Begin Patch\n***Update File:tools/ai-team/x.py\n*** End Patch"}],
                 ["apply_patch", {"patchText": "*** Begin Patch\n  *** add file :  AGENTS.md  \n*** End Patch"}]]
        self.assertEqual(self.hook(calls), ["allow", "refuse", "allow", "refuse", "refuse", "allow", "refuse",
                                            "refuse", "allow", "refuse", "refuse"])

    def test_a_write_from_a_session_in_a_subfolder_is_refused(self):
        calls = [["write", {"filePath": "plugin/x.js"}], ["edit", {"filePath": "x.md"}]]
        self.assertEqual(self.hook(calls, directory=os.path.join(ROOT, ".opencode")), ["refuse", "refuse"])
        self.assertEqual(self.hook(calls[1:]), ["allow"])

    def test_the_wrapper_only_with_the_owner_and_never_unattended(self):
        calls = [["bash", {"command": OwnerTerminalCommandTests.WRAPPER[0]}],
                 ["task", {"subagent_type": "fo4-implement", "prompt": "x"}]]
        self.assertEqual(self.hook(calls), ["refuse", "allow"])
        self.assertEqual(self.hook(calls, FO4SF_OWNER_PRESENT="1"), ["allow", "allow"])
        self.assertEqual(self.hook(calls, FO4SF_OWNER_PRESENT="1", FO4SF_UNATTENDED="1"), ["refuse", "refuse"])


class TeamSkillAndCommandTests(unittest.TestCase):
    def test_every_example_in_the_teams_skill_is_allowed(self):
        text = read(".opencode", "skills", "fo4-allowed-commands", "SKILL.md")
        blocks = re.findall(r"```text\n(.*?)```", text, re.S)
        self.assertEqual(len(blocks), 2)
        everywhere, owner_only = (b.strip().splitlines() for b in blocks)
        self.assertGreater(len(everywhere), 15)
        for command in everywhere:
            self.assertTrue(allowed(command), command)
        for command in owner_only:
            self.assertTrue(allowed(command, owner_present=True), command)
            self.assertFalse(allowed(command), command)

    def test_skill_names_follow_the_rules_and_only_the_teams_own_is_visible_to_it(self):
        rule = json.loads(read("opencode.json"))["permission"]["skill"]
        self.assertEqual(rule, {"*": "deny", "fo4-*": "allow"})
        name = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
        for base, visible in ((".opencode/skills", True), (".claude/skills", False)):
            for d in sorted(os.listdir(os.path.join(ROOT, base))):
                meta = frontmatter(read(base, d, "SKILL.md"))
                self.assertEqual(meta["name"], d)
                self.assertTrue(name.fullmatch(d) and len(d) <= 64, d)
                self.assertTrue(0 < len(meta["description"]) <= 1024, d)
                self.assertEqual(d.startswith("fo4-"), visible, d)  # Claude's skills stay hidden from the team

    def test_commands_name_a_team_agent_and_only_allowed_commands(self):
        folder = os.path.join(ROOT, ".opencode", "commands")
        names = sorted(f[:-3] for f in os.listdir(folder))
        self.assertEqual(names, ["board", "handoff", "next", "research", "review", "team"])   # no clash with /status
        for n in names:
            text = read(".opencode", "commands", n + ".md")
            meta = frontmatter(text)
            self.assertIn(meta["agent"], AGENTS, n)
            self.assertTrue(meta["description"], n)
            self.assertNotIn("!`", text, n)                     # no shell injection: every command passes the guard
            for command in re.findall(r"`((?:gh|git|python) [^`]*)`", text):
                filled = re.sub(r"<[^>]*>", "x", " ".join(command.split())).replace("$1", "605")
                owner_only = "agent_git.py" in filled or "for Claude" in filled
                self.assertTrue(allowed(filled, owner_present=owner_only), (n, filled))
                self.assertEqual(allowed(filled), not owner_only, (n, filled))


class CommandTextTests(unittest.TestCase):
    def test_review_reads_the_pr_and_its_ci_and_does_not_run_tests_here(self):
        text = read(".opencode", "commands", "review.md")
        self.assertIn("gh pr checks $1", text)
        self.assertNotIn("unittest", text)

    def test_the_handoff_names_every_character_the_guard_refuses(self):
        for name in (("commands", "handoff.md"), ("skills", "fo4-allowed-commands", "SKILL.md")):
            text = " ".join(read(".opencode", *name).split())
            for word in ("apostrophe", "ampersand", "pipe", "caret", "percent", "angle bracket", "backtick"):
                self.assertIn(word, text, (name, word))

    def test_next_makes_a_branch_from_main_before_committing(self):
        text = read(".opencode", "commands", "next.md")
        self.assertLess(text.index("agent_git.py branch"), text.index("agent_git.py commit"))

    def test_the_terminal_can_open_each_agent(self):
        # OpenCode's --agent falls back to the default agent for a subagent-only mode, so the three the menu offers
        # are "all": a primary agent in the terminal and a subagent for the Lead.
        for agent in AGENTS:
            meta = frontmatter(read(".opencode", "agents", agent + ".md"))
            self.assertEqual(meta["mode"], "primary" if agent == "fo4-lead" else "all", agent)


class ScriptTests(unittest.TestCase):
    def script(self, name):
        return read("tools", "ai-team", name)

    def test_scripts_are_ascii_for_powershell_5(self):
        # Windows PowerShell 5.1 reads a file without a BOM as the ANSI code page, so a UTF-8 dash breaks a string.
        for name in sorted(os.listdir(TEAM)):
            if name.endswith(".ps1"):
                self.assertTrue(self.script(name).isascii(), name)

    def test_the_terminal_is_the_owners_and_hides_outside_skills(self):
        s = self.script("terminal.ps1")
        launch = s.index("& $opencode @argv")
        for line in ("Remove-Item Env:FO4SF_UNATTENDED", "$env:FO4SF_OWNER_PRESENT = '1'",
                     "$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'", "$env:OPENCODE_CONFIG_CONTENT = (& $Python $models opencode",
                     "fo4-to-starfield-wt\\local-terminal", "Set-Location $wt"):
            self.assertIn(line, s)
            self.assertLess(s.index(line), launch, line)
        self.assertIn("switch -q --detach origin/main", s)      # a clean terminal worktree goes back to main
        self.assertNotIn("ai/local-terminal", s)                # no branch of its own that could fall behind main

    def test_unattended_runs_never_count_as_the_owners_terminal(self):
        s = self.script("run-lead.ps1")
        self.assertNotIn("$env:FO4SF_OWNER_PRESENT =", s)
        self.assertIn("Remove-Item Env:FO4SF_OWNER_PRESENT", s)
        self.assertIn("$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'", s)
        self.assertIn("-replace '[\"`$\\\\]'", s)              # a brief cannot end the quoted prompt argument
        self.assertNotIn("Start-Sleep $Interval; continue", s)  # a skip in the last cycle exits without the wait
        self.assertIn("Wait-Next; continue", s)

    def test_the_menu_offers_what_the_owner_asked_for(self):
        s = self.script("menu.ps1")
        for item in ("Start the local team", "Talk to the local agents", "Talk to one agent", "Start Claude Code",
                     "Status", "Pick a model", "Start or stop the unattended Lead", "Pause or resume",
                     "Stop the local team"):
            self.assertIn(item, s)
        for model in ("'opus'", "'sonnet'", "'haiku'"):
            self.assertIn(model, s)
        self.assertIn("Type yes to start the unattended Lead", s)
        self.assertIn("Type stop to stop the unattended Lead and the session it is running", s)
        self.assertIn("lead-session.pid", self.script("run-lead.ps1"))   # the session the menu stops
        self.assertIn("'menu.ps1'", self.script("install-shortcut.ps1"))


if __name__ == "__main__":
    unittest.main()
