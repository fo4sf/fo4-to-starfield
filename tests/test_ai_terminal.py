"""The owner's side of the local team: the model pick (models.py) that the proxy and OpenCode follow, the guard's file
write checks and the owner's-terminal commit wrapper (agent_git.py), the terminal and menu scripts, the team's commands
and skill, and Claude Code's skills. Temp folders and synthetic git repos; no LM Studio, no network."""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
        models.save(models.preset("qwen3-14b"))           # what a load that worked saves (ModelLoadTests)
        self.assertEqual(store.picked_model(), "qwen3-14b")
        saved = proxy.CFG
        self.addCleanup(setattr, proxy, "CFG", saved)
        proxy.CFG = proxy.load_cfg()                     # what the running proxy reads at start (main)
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

    def test_only_the_presets_can_be_picked(self):
        # the owner's choice (30 Oct): the measured setups only, the 35B at 64K and the 14B fallback; and the 35B at
        # 3-bit on trial (the owner's pick, 31 Oct), which replaces the 4-bit one if it passes
        self.assertEqual(sorted(models.read_config()["models"]), ["qwen3-14b", "qwen3.6-35b", "qwen3.6-35b-q3"])
        models.save(models.preset("qwen3-14b"))
        for bad in (["pick", "--model", "qwen/qwen3-8b", "--context", "16384"], ["pick", "qwen3.6-35b-128k"],
                    ["pick", "no-such-preset"], ["pick"], ["pick", "qwen3-14b", "--no-load"]):
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = models.main(bad)
                except SystemExit as stop:               # argparse refuses an unknown option or a missing name
                    code = stop.code
            self.assertNotEqual(code, 0, bad)
        self.assertEqual(store.picked_model(), "qwen3-14b")             # a refused pick keeps the last good one
        # a row that names no preset (an older build's custom pick) reads as the default preset
        c = store.connect()
        self.addCleanup(c.close)
        store.set_pick(c, {"preset": None, "model": "qwen/qwen3-8b", "context": 16384, "output": 4096, "kv": "f16",
                           "gpu": None})
        self.assertEqual(models.current()["preset"], "qwen3.6-35b")
        saved = proxy.CFG
        self.addCleanup(setattr, proxy, "CFG", saved)
        proxy.CFG = proxy.load_cfg()
        self.assertEqual(proxy._agent_and_model("fo4-lead"), ("fo4-lead", "qwen3.6-35b-a3b"))

    def test_cloud_puts_every_agent_on_a_claude_model(self):
        cfg = models.read_config()
        oc = models.cloud_config("claude-sonnet", cfg)
        self.assertEqual(oc, {"model": "anthropic/claude-sonnet-5-5",
                              "agent": {a: {"model": "anthropic/claude-sonnet-5-5"} for a in AGENTS}})
        self.assertEqual(models.cloud_config("claude-haiku", cfg)["model"], "anthropic/claude-haiku-5-5")
        for bad in ("claude-opus", "anthropic/claude-sonnet-5-5", "qwen3.6-35b", ""):
            with self.assertRaises(models.PickError, msg=bad):
                models.cloud_config(bad, cfg)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(models.main(["opencode", "--cloud", "claude-opus"]), 1)
        self.assertIn("no cloud model", out.getvalue())

    def test_only_the_cloud_models_can_be_reached_and_the_cap_is_set(self):
        # opencode.json lets OpenCode offer the local proxy and Anthropic only, and of Anthropic's models only the two
        # config.json names (not Opus); their windows are kept well under the 1M the API allows, to hold the spend down
        cfg = models.read_config()
        oc = json.loads(read("opencode.json"))
        self.assertEqual(oc["enabled_providers"], ["guardian", "anthropic"])
        cloud = sorted(cfg["cloud"]["models"].values())
        self.assertEqual(cloud, ["claude-haiku-5-5", "claude-sonnet-5-5"])
        self.assertEqual(sorted(oc["provider"]["anthropic"]["whitelist"]), cloud)
        self.assertEqual(sorted(oc["provider"]["anthropic"]["models"]), cloud)
        for m, entry in oc["provider"]["anthropic"]["models"].items():
            self.assertLessEqual(entry["limit"]["context"], 200000, m)
            self.assertEqual(entry["limit"]["output"], 32000, m)
        self.assertNotIn("options", oc["provider"]["anthropic"])      # no key here: the owner's opencode auth login
        self.assertEqual(cfg["cloud"]["monthly_cap_usd"], 50)

    def test_a_load_waits_for_running_requests(self):
        c = store.connect()
        self.addCleanup(c.close)
        c.execute("INSERT INTO jobs (agent, model, kind, status, created) VALUES ('fo4-lead', 'm', 'chat', 'running', 0)")
        with self.assertRaises(models.PickError):
            models.load(models.preset("qwen3-14b"), models.read_config())
        self.assertIsNone(store.get_hold(c))                            # the hold is let go again
        self.assertIsNone(store.picked_model())

    def test_a_refused_load_keeps_a_failed_hold(self):
        # After a load that failed, the proxy refuses requests. A load refused for a running request unloads
        # nothing, so the failed hold must stand, or the proxy would serve requests with no model loaded.
        c = store.connect()
        self.addCleanup(c.close)
        store.fail_hold(c, "loading qwen3-14b failed (out of memory)")
        c.execute("UPDATE control SET t=1 WHERE key=?", (store.HOLD,))
        c.execute("INSERT INTO jobs (agent, model, kind, status, created) VALUES ('fo4-lead', 'm', 'chat', 'running', 0)")
        with self.assertRaises(models.PickError):
            models.load(models.preset("qwen3-14b"), models.read_config())
        self.assertEqual(store.get_hold(c)[:2], ("failed", "loading qwen3-14b failed (out of memory)"))
        self.assertEqual(c.execute("SELECT t FROM control WHERE key=?", (store.HOLD,)).fetchone()[0], 1)

    def test_models_py_runs_isolated(self):
        # The guard and the Lead's rules take `python -I tools/ai-team/models.py list`; -I drops the script's folder.
        env = dict(os.environ, FO4_AI_TEAM_STATE=self.state)
        r = subprocess.run([sys.executable, "-I", os.path.join(TEAM, "models.py"), "list"], capture_output=True,
                           text=True, env=env)
        self.assertNotIn("ModuleNotFoundError", r.stderr)
        self.assertEqual(json.loads(r.stdout)["picked"]["preset"], models.read_config()["default_model"])

    def test_list_tells_a_missing_sdk_from_lm_studio_being_off(self):
        saved = sys.modules.get("lmstudio")
        self.addCleanup(lambda: sys.modules.__setitem__("lmstudio", saved) if saved else sys.modules.pop("lmstudio"))
        sys.modules["lmstudio"] = None                     # import lmstudio raises ImportError
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            models.main(["list"])
        self.assertIn("SDK not importable", json.loads(out.getvalue())["lmstudio"])
        import types
        def off():
            raise ConnectionRefusedError
        sys.modules["lmstudio"] = types.SimpleNamespace(get_default_client=off)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            models.main(["list"])
        self.assertEqual(json.loads(out.getvalue())["lmstudio"], "not reachable (ConnectionRefusedError)")

    def test_list_and_loaded_contexts_read_what_lm_studio_has_loaded(self):
        import types
        saved = sys.modules.get("lmstudio")
        self.addCleanup(lambda: sys.modules.__setitem__("lmstudio", saved) if saved else sys.modules.pop("lmstudio"))

        class Loaded:
            def __init__(self, identifier, context):
                self.identifier, self.context = identifier, context

            def get_context_length(self):
                if self.context is None:
                    raise AttributeError("an older SDK")
                return self.context

        loaded = [Loaded("qwen3.6-35b-a3b", 65536), Loaded("qwen3-14b", None)]
        client = types.SimpleNamespace(llm=types.SimpleNamespace(list_loaded=lambda: loaded))
        sys.modules["lmstudio"] = types.SimpleNamespace(get_default_client=lambda: client)
        self.assertEqual(models.loaded_contexts(), {"qwen3.6-35b-a3b": 65536, "qwen3-14b": None})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            models.main(["list"])
        listed = json.loads(out.getvalue())
        self.assertEqual(listed["loaded"], ["qwen3.6-35b-a3b", "qwen3-14b"])
        self.assertNotIn("lmstudio", listed)                 # no error to report


class LoadModelSdkTests(unittest.TestCase):
    def test_load_unloads_the_model_and_the_named_ones_only(self):
        import types
        import load_model
        unloaded, loads = [], []

        class Loaded:
            def __init__(self, identifier):
                self.identifier = identifier

            def unload(self):
                unloaded.append(self.identifier)

        class Llm:
            def list_loaded(self):
                return [Loaded("qwen3-14b"), Loaded("old-pick"), Loaded("owners-own")]

            def load_new_instance(self, model, identifier, config):
                loads.append((model, identifier, config))
                return Loaded(identifier)

        fake = types.ModuleType("lmstudio")
        fake.get_default_client = lambda: types.SimpleNamespace(llm=Llm())
        saved = sys.modules.get("lmstudio")
        sys.modules["lmstudio"] = fake
        self.addCleanup(lambda: sys.modules.__setitem__("lmstudio", saved) if saved else sys.modules.pop("lmstudio"))
        cfg = load_model.load_config(32768, "q8_0", 1.0)
        self.assertEqual(load_model.load("qwen3-14b", cfg, unload={"old-pick"}), "qwen3-14b")
        self.assertEqual(unloaded, ["qwen3-14b", "old-pick"])          # the owner's own model stays
        self.assertEqual(loads, [("qwen3-14b", "qwen3-14b", cfg)])
        # a model LM Studio lists under a publisher key loads under the short id the team's requests name
        self.assertEqual(load_model.load("qwen3.6-35b-a3b-q3", cfg, key="unsloth/qwen3.6-35b-a3b"), "qwen3.6-35b-a3b-q3")
        self.assertEqual(loads[1], ("unsloth/qwen3.6-35b-a3b", "qwen3.6-35b-a3b-q3", cfg))


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
        self.calls, self.keys, self.during = [], [], None
        saved = models.load_model.load
        self.addCleanup(setattr, models.load_model, "load", saved)
        models.load_model.load = self.fake_load

    def fake_load(self, model, cfg_lm, unload=(), key=None):
        self.calls.append((model, cfg_lm["contextLength"], set(unload)))
        self.keys.append(key)
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

    def test_switching_presets_unloads_the_other_ones(self):
        models.save(models.preset("qwen3.6-35b"))
        models.load(models.preset("qwen3-14b"), self.cfg)
        self.assertEqual(set(self.calls[0][2]), {"qwen3.6-35b-a3b", "qwen3.6-35b-a3b-q3"})
        # the 3-bit trial and the 4-bit 35B never sit in RAM together
        models.load(models.preset("qwen3.6-35b-q3"), self.cfg)
        self.assertEqual(set(self.calls[1][2]), {"qwen3.6-35b-a3b", "qwen3-14b"})
        # each loads by the key LM Studio lists it under (two downloads of one model get publisher keys), under the
        # short id the proxy sends requests to
        models.load(models.preset("qwen3.6-35b"), self.cfg)
        self.assertEqual([c[0] for c in self.calls], ["qwen3-14b", "qwen3.6-35b-a3b-q3", "qwen3.6-35b-a3b"])
        self.assertEqual(self.keys, ["qwen3-14b", "unsloth/qwen3.6-35b-a3b", "lmstudio-community/qwen3.6-35b-a3b"])
        self.assertEqual(store.picked_model(), "qwen3.6-35b-a3b")
        with self.assertRaises(models.PickError):
            models.setup("qwen3.6-35b-a3b", 65536, key="unsloth/qwen 3.6")

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
        self.assertIsNotNone(store.take_hold(self.c, "qwen3-14b"))
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

    def test_the_refused_writes_mode_lists_what_an_agent_may_not_write(self):
        # terminal.ps1's start check: paths on stdin as PowerShell sends them (CRLF), one reason out for each refused
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        checker = os.path.join(TEAM, "guard", "allowlist.py")
        ok = ["src/a.py", "tests/test_x.py", "docs/ai/note.md"]
        bad = [".opencode/plugin/fo4-guard.js", "AGENTS.md", "docs/ai/CLAUDE.md", "scripts/re.py", "opencode.jsonc",
               "tools/ai-team/guard/allowlist.py", "a b.md", '"docs/\\303\\251.md"']   # the last as git quotes it
        r = subprocess.run([sys.executable, "-I", checker, "--refused-writes", d], capture_output=True, text=True,
                           input="\r\n".join(ok + bad) + "\r\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), len(bad), r.stdout)
        for p in ok:
            self.assertFalse(any(p in line for line in lines), p)
        for p in bad[:-2]:
            self.assertTrue(any(p in line for line in lines), p)
        r = subprocess.run([sys.executable, "-I", checker, "--refused-writes", d], capture_output=True, text=True,
                           input="")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        for argv in (["--refused-writes"], ["--refused-writes", os.path.join(d, "none")], ["--other", d]):
            r = subprocess.run([sys.executable, "-I", checker, *argv], capture_output=True, text=True, input="AGENTS.md")
            self.assertNotEqual(r.returncode, 0, argv)                  # not checked: the terminal does not start

    def test_the_agents_own_files_are_writable(self):
        for p in ("docs/ai/agent-status.md", "docs/ai/research-log.md", "src/fo4sf/x.py", "tests/test_x.py",
                  "./docs/ai/x.md", "docs/ai/opencode-notes.md", "docs/ai/git-notes.md", "docs/ai/x.opencode.md",
                  "docs/ai/pr-drafts/618.md", "docs/ai/summaries/2026-10-28-to-30.md"):
            self.assertTrue(self.verdict(p), p)

    def test_the_teams_rules_and_tools_and_anything_outside_are_refused(self):
        for p in ("docs/ai/AGENTS.md", "src/CLAUDE.md", "docs/Context.md", "opencode.jsonc", "tui.json", "tools",
                  "docs/ai", "tools/ai-team/", "docs/..", "opencode.json", "OpenCode.json", "AGENTS.md", "agents.md",
                  ".opencode/plugin/fo4-guard.js",
                  ".OpenCode/agents/fo4-lead.md", ".opencode/commands/next.md", ".claude/skills/x/SKILL.md",
                  ".github/workflows/ci.yml", ".git/config", "tools/ai-team/guard/allowlist.py",
                  "tools/ai-team/run-lead.ps1", "Tools/AI-Team/menu.ps1", "scripts/guard.py",
                  "docs/CODEX-HANDOFF.md", "docs/../opencode.json", "../elsewhere/x", "/etc/passwd", ".", "",
                  # nested config: OpenCode loads it in a session started there or below
                  "docs/ai/.opencode/plugin/x.js", "src/.OpenCode/agents/x.md", "docs/ai/opencode.json",
                  "docs/ai/x/OpenCode.jsonc", "docs/ai/tui.json", "docs/ai/.claude/settings.json",
                  "src/.github/workflows/x.yml", "docs/ai/.git/hooks/pre-commit", "docs/ai/.agents/skills/x/SKILL.md",
                  # names NTFS reads as another file, and anything outside the repo's own name characters
                  "src/AGENTS.md::$DATA", "src/AGENTS.md:x", "opencode.jsonc.", "docs/AGENTS.md ", "docs/ai/x.md.",
                  "docs/ai/a b.md", "docs/ai/x~1.md", "docs/ai/\u00fc.md", "docs/ai/x\n.md", "docs/ai/.hidden"):
            self.assertFalse(self.verdict(p), p)
        self.assertFalse(self.verdict("docs/ai/x.md", "opencode.json"))
        self.assertFalse(self.verdict())

    def test_names_python_searches_first_are_refused(self):
        # python scripts/guard.py searches scripts/ first, and python -m unittest the repo root: a standard module's
        # name there would run in place of the module.
        for p in ("scripts/re.py", "scripts/RE.py", "scripts/json/__init__.py", "scripts/re.pyc", "scripts/os.x.py",
                  "re.py", "unittest.py", "json/__init__.py", "sitecustomize.py", "usercustomize.py", "Ast.py"):
            self.assertFalse(self.verdict(p), p)
        for p in ("scripts/new_tool.py", "src/re.py", "docs/ai/json.md".replace(".md", "-notes.md"), "tests/test_re.py",
                  "notes.md"):
            self.assertTrue(self.verdict(p), p)

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
                    ".OpenCode\\plugin\\x.js", "D:\\Work\\other\\x", "..\\x", "C:\\x", "docs\\..\\opencode.jsonc",
                    # names NTFS reads as another file: a stream, a trailing dot or space (dropped), a short-name tilde
                    "src\\AGENTS.md::$DATA", "src\\AGENTS.md:x", "AGENTS.md::$DATA", "opencode.jsonc.", "tui.json ",
                    "docs\\AGENTS.md ", "src\\CONTEXT.md.", "docs\\ai\\x.md.", "docs\\ai\\AGENTS~1.MD",
                    root + "\\src\\CLAUDE.md::$DATA", "docs\\ai\\x.md\t", "docs\\ai\\\u00fc.md", "docs\\ai\\.hidden"):
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

    def test_the_wrapper_commits_only_files_an_agent_may_write(self):
        for paths in ("opencode.json", "src/a.py AGENTS.md", "tools/ai-team/agent_git.py", "scripts/re.py",
                      ".opencode/plugin/x.js", "docs/ai/.git/hooks/pre-commit"):
            command = f"python -I tools/ai-team/agent_git.py commit 'Implement (local): x' {paths}"
            self.assertFalse(allowed(command, owner_present=True), command)
        self.assertTrue(allowed("python -I tools/ai-team/agent_git.py commit 'Implement (local): x' src/a.py",
                                owner_present=True))

    def test_a_handoff_to_claude_comes_only_from_the_owners_terminal(self):
        for text in ("Lead (local): for Claude: done", "Lead (local): For  claude: done", "Lead (local):  FOR Claude x",
                     "Lead (local): **for Claude:** done", "Lead (local): for-Claude: done",
                     "Lead (local): F O R Claude: done", "Lead (local): _for_ _claude_ done",
                     "Lead (local): [](a)for Claude: done", "Lead (local): for CIaude: done",
                     "Lead (local): f0r C1aude: done"):
            command = f"gh issue comment 32 --body '{text}'"
            self.assertTrue(allowed(command, owner_present=True), text)
            self.assertFalse(allowed(command), text)
        for text in ("<b>for</b> Claude", "<!-- x -->for Claude", "for&nbsp;Claude", "for Cl\u0430ude",
                     "\uff46or Claude", "[](x(y)z)for Claude", "[](<a)b>)for Claude", "[](<a(b>)for Claude", "(#594) for Claude"):
            self.assertTrue(allowlist.is_handoff("Lead (local): " + text), text)    # markup, look-alikes, nesting
        for text in ("(#594) refreshed agent status", "status (for Claude) refreshed", "(x)(y) notes for Claude"):
            self.assertFalse(allowlist.is_handoff("Lead (local): " + text), text)
        self.assertTrue(allowed("gh issue comment 32 --body 'Lead (local): refreshed agent status'"))
        self.assertTrue(allowed("gh issue comment 32 --body 'Lead (local): formatted the notes for the Claude review'"))

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
        self.assertEqual(self.run_tool("commit", "fix the clamp", "src/a.py", "src/b.py")[0], 1)   # no agent tag
        code, out = self.run_tool("commit", "Implement (local): fix the clamp", "src/a.py", "src/b.py")
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
        # The guard's names already refuse * : ( and friends, so the wrapper is run with its write check off here, to
        # show that git itself takes each path literally (--literal-pathspecs).
        self.git("checkout", "-q", "-b", "ai/9-x")
        self.write("opencode.json", '{"x": 1}\n')
        self.write("src/a.py", "new\n")
        unchecked = ("import sys; sys.path.insert(0, sys.argv[1]); import agent_git; "
                     "agent_git.allowlist.check_write = lambda *a: None; sys.exit(agent_git.main(sys.argv[2:]))")
        for spec in ("*.json", ":/opencode.json", ":(glob)*.json", "src/*"):
            r = subprocess.run([sys.executable, "-I", "-c", unchecked, TEAM, "commit", "Implement (local): x", spec],
                               cwd=self.d, capture_output=True, text=True, env=self.env)
            self.assertEqual(r.returncode, 1, (spec, r.stdout, r.stderr))
            self.assertIn("did not match", r.stdout, spec)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")
        self.assertEqual(self.git("diff", "--cached", "--name-only"), "")

    def test_the_branch_command_switches_back_to_an_existing_branch(self):
        self.assertEqual(self.run_tool("branch", "ai/7-x")[0], 0)
        self.write("src/a.py", "new\n")
        self.assertEqual(self.run_tool("commit", "Implement (local): one", "src/a.py")[0], 0)
        work = self.git("rev-parse", "HEAD")
        self.git("switch", "-q", "--detach", "origin/main")               # the terminal reopened on a clean worktree
        self.write("opencode.json", '{"changed": true}\n')                # not with a change an agent may not make
        code, out = self.run_tool("branch", "ai/7-x")
        self.assertEqual(code, 1, out)
        self.assertIn("opencode.json", out)
        self.git("checkout", "-q", "--", "opencode.json")
        self.write("src/b.py", "untracked\n")                             # an ordinary edit comes along
        code, out = self.run_tool("branch", "ai/7-x")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git("rev-parse", "HEAD"), work)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "ai/7-x")
        self.assertTrue(os.path.exists(os.path.join(self.d, "src", "b.py")))

    def test_no_switch_back_to_a_branch_whose_protected_files_are_not_mains(self):
        # The guard and OpenCode read these from the worktree: one of each kind the guard refuses an agent to write.
        for i, rel in enumerate((".opencode/plugin/fo4-guard.js", "tools/ai-team/guard/allowlist.py", "AGENTS.md",
                                 "opencode.jsonc", "opencode.json", "docs/ai/CLAUDE.md", "scripts/guard.py")):
            name = f"ai/{i}-y"
            self.git("switch", "-q", "-c", name, "origin/main")
            self.write(rel, "changed by hand\n")
            self.git("add", "--", rel)
            self.git("commit", "-q", "-m", "by hand")
            self.git("switch", "-q", "--detach", "origin/main")
            code, out = self.run_tool("branch", name)
            self.assertEqual(code, 1, (rel, out))
            self.assertIn(rel, out)
            self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "HEAD")
        # A branch made before main changed such a file is behind it in that file too.
        self.assertEqual(self.run_tool("branch", "ai/20-z")[0], 0)
        self.git("switch", "-q", "--detach", "origin/main")
        self.write("tools/ai-team/team.py", "a guard fix on main\n")
        self.git("add", "--", "tools/ai-team/team.py")
        self.git("commit", "-q", "-m", "main moves on")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        code, out = self.run_tool("branch", "ai/20-z")
        self.assertEqual(code, 1, out)
        self.assertIn("tools/ai-team/team.py", out)

    def test_refusals(self):
        self.write("src/a.py", "new\n")
        self.assertEqual(self.run_tool("commit", "Implement (local): x", "src/a.py")[0], 1)                 # on main
        self.assertEqual(self.run_tool("branch", "ai/local-lead")[0], 1)                 # before it exists
        self.assertNotIn("ai/local-lead", self.git("branch", "--list"))
        self.git("checkout", "-q", "-b", "ai/local-lead")
        self.assertEqual(self.run_tool("commit", "Implement (local): x", "src/a.py")[0], 1)                 # the Lead's branch
        self.git("checkout", "-q", "-b", "ai/8-x")
        self.write("opencode.json", '{"x": 1}\n')
        self.assertEqual(self.run_tool("commit", "Implement (local): x", "opencode.json")[0], 1)            # a protected path
        self.assertEqual(self.run_tool("commit", "Implement (local): x", "../x")[0], 1)
        self.assertEqual(self.run_tool("branch", "main2")[0], 1)
        unattended = dict(self.env, FO4SF_UNATTENDED="1")
        self.assertEqual(self.run_tool("commit", "Implement (local): x", "src/a.py", env=unattended)[0], 1)
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), "base")
        self.assertEqual(self.run_tool("commit", "Implement (local): x", "src/a.py")[0], 0)   # the same call works here

    def test_no_hook_runs(self):
        hook = os.path.join(self.d, ".git", "hooks", "post-checkout")
        with open(hook, "w") as f:
            f.write("#!/bin/sh\ntouch hook-ran\n")
        os.chmod(hook, 0o755)
        self.assertEqual(self.run_tool("branch", "ai/9-x")[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.d, "hook-ran")))


# CI always runs these (GitHub sets CI): there a missing node is a failure, not a quiet skip.
@unittest.skipUnless(shutil.which("node") or os.environ.get("CI"), "node is not installed")
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

    def setUp(self):
        if not shutil.which("node"):
            self.fail("node is not installed: CI must run the plugin tests")

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


class ReportPluginTests(unittest.TestCase):
    # .opencode/plugin/fo4-reports.js, driven with the events and hook calls OpenCode 1.18.35 makes (read from its code)
    HARNESS = r"""
import { readFileSync } from "node:fs";
const [url, stepsFile] = process.argv.slice(2);
const stepsJson = readFileSync(stepsFile, "utf8");
const mod = await import(url);
const out = { exports: Object.entries(mod).map(([k, v]) => [k, typeof v]) };
const hooks = await mod.default({});
out.results = [];
for (const [kind, input, output] of JSON.parse(stepsJson)) {
  if (kind === "event") { await hooks.event({ event: input }); continue; }
  if (kind === "autocontinue") {
    const o = { enabled: true };
    await hooks["experimental.compaction.autocontinue"](input, o);
    out.results.push(o.enabled);
  } else {
    await hooks["tool.execute.after"](input, output);
    out.results.push(output.output);
  }
}
console.log(JSON.stringify(out));
"""

    def setUp(self):
        if not shutil.which("node"):
            self.fail("node is not installed: CI must run the plugin tests")

    def run_steps(self, steps):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        plugin = os.path.join(d, "fo4-reports.mjs")
        shutil.copy(os.path.join(ROOT, ".opencode", "plugin", "fo4-reports.js"), plugin)
        harness = os.path.join(d, "harness.mjs")
        with open(harness, "w") as f:
            f.write(self.HARNESS)
        with open(os.path.join(d, "steps.json"), "w", encoding="utf-8") as f:
            json.dump(steps, f)
        r = subprocess.run(["node", harness, "file://" + plugin, os.path.join(d, "steps.json")], capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    @staticmethod
    def answer(session, msg, text, finish="stop", summary=False, parts=()):
        """The events of one assistant step: created, its text part (then any other parts), finished."""
        info = {"id": msg, "sessionID": session, "role": "assistant", **({"summary": True} if summary else {})}
        def part(n, kind, **more):
            return ["event", {"type": "message.part.updated", "properties": {"sessionID": session, "part": {
                "id": f"{msg}-p{n}", "messageID": msg, "sessionID": session, "type": kind, **more}}}]
        return ([["event", {"type": "message.updated", "properties": {"sessionID": session, "info": info}}],
                 part(0, "text", text=text)] + [part(n + 1, kind, **more) for n, (kind, more) in enumerate(parts)] +
                [["event", {"type": "message.updated", "properties": {"sessionID": session,
                                                                      "info": dict(info, finish=finish)}}]])

    @staticmethod
    def layout(session, text):
        # the task tool's result as 1.18.35 lays it out (Rr: the lines joined with "\n")
        return "\n".join([f'<task id="{session}" state="completed">', "<task_result>", text, "</task_result>",
                          "</task>"])

    @classmethod
    def task(cls, session, text):
        return ["after", {"tool": "task", "sessionID": "lead", "callID": "c1", "args": {}},
                {"title": "t", "metadata": {"parentSessionId": "lead", "sessionId": session},
                 "output": cls.layout(session, text)}]

    @staticmethod
    def compaction(session, msg):
        """SessionCompaction.create: a user message with a compaction part, before the summary is written."""
        return [["event", {"type": "message.updated", "properties": {"sessionID": session, "info": {
                    "id": msg, "sessionID": session, "role": "user"}}}],
                ["event", {"type": "message.part.updated", "properties": {"sessionID": session, "part": {
                    "id": f"{msg}-p0", "messageID": msg, "sessionID": session, "type": "compaction", "auto": True,
                    "overflow": False}}}]]

    @staticmethod
    def start(session, parent, event="session.created"):
        info = {"id": session, **({"parentID": parent} if parent else {})}
        return [["event", {"type": event, "properties": {"sessionID": session, "info": info}}]]

    @staticmethod
    def compacts(session, overflow=False):
        return ["autocontinue", {"sessionID": session, "agent": "fo4-qa", "overflow": overflow}]

    def test_a_subagents_report_survives_a_compaction_after_it(self):
        report = "Bugs found: 3. Tests: tests/test_x.py. Odd text: $& $1 </task_result>"
        summary = "SUMMARY of the session: it said </task_result>\n</task>\nand then"
        steps = (self.start("lead", None) + self.start("sub", "lead") +
                 self.answer("sub", "m1", "reading files", finish="tool-calls", parts=[("tool", {"tool": "read"})]) +
                 # the thinking comes as its own part, after the text here, and is not the report; a tool the
                 # provider ran itself does not keep OpenCode's loop going
                 self.answer("sub", "m2", report, parts=[
                     ("reasoning", {"text": "I should check line 54"}),
                     ("tool", {"tool": "web", "metadata": {"providerExecuted": True}})]) +
                 self.compaction("sub", "u1") + self.answer("sub", "s1", summary, summary=True) +
                 # the summary quotes the tags, and OpenCode cut the result before its own closing ones
                 [self.compacts("sub"), ["after", {"tool": "task"}, {"metadata": {"sessionId": "sub"},
                                                                     "output": self.layout("sub", summary)[:-20]}]])
        got = self.run_steps(steps)
        self.assertEqual(got["exports"], [["Fo4Reports", "function"], ["default", "function"]])  # plugins only
        enabled, output = got["results"]
        self.assertFalse(enabled)                           # no "Continue": the subagent stops, as it had
        self.assertEqual(output, self.layout("sub", report))

    def test_a_subagent_resumed_after_a_restart_is_known_from_its_update(self):
        # A resumed task touches its session, which publishes session.updated with the stored parentID.
        steps = (self.start("sub", "lead", event="session.updated") + self.answer("sub", "m1", "the report") +
                 [self.compacts("sub"), self.task("sub", "a summary")])
        enabled, output = self.run_steps(steps)["results"]
        self.assertFalse(enabled)
        self.assertIn("\nthe report\n", output)

    def test_every_other_compaction_runs_as_opencode_makes_it(self):
        steps = (self.start("lead", None) + self.start("sub", "lead") +
                 # the owner's own session, after an answer
                 self.answer("lead", "l1", "a reply to the owner") + [self.compacts("lead")] +
                 # a subagent in the middle of its task, after a step that ran out of room, and an overflow
                 self.answer("sub", "m1", "reading files", finish="tool-calls") + [self.compacts("sub")] +
                 self.answer("sub", "m2", "thinking...", finish="length") + [self.compacts("sub")] +
                 # a step that ends "stop" with a tool call of its own is not a finished answer for OpenCode either
                 self.answer("sub", "m3", "Let me read the next file.", parts=[("tool", {"tool": "read"})]) +
                 [self.compacts("sub")] +
                 # a step with no text
                 self.answer("sub", "m4", "") + [self.compacts("sub")] +
                 self.answer("sub", "m5", "a report") + [self.compacts("sub", overflow=True),
                                                         self.task("sub", "the reply to Continue")])
        got = self.run_steps(steps)["results"]
        self.assertEqual(got[:6], [True] * 6)
        self.assertIn("the reply to Continue", got[6])        # nothing kept, so the task's result is OpenCode's

    def test_a_kept_report_goes_only_to_its_own_task(self):
        steps = (self.start("sub", "lead") + self.answer("sub", "m1", "the report") + [self.compacts("sub")] +
                 # another tool with the same session id in its metadata is not touched, and the report stays kept
                 [["after", {"tool": "read"},
                   {"metadata": {"sessionId": "sub"}, "output": "<task_result>x</task_result>"}],
                  self.task("sub", "a summary"), self.task("sub", "a second call")])
        got = self.run_steps(steps)["results"]
        self.assertEqual(got[1], "<task_result>x</task_result>")
        self.assertIn("\nthe report\n", got[2])
        self.assertIn("a second call", got[3])               # used once

    def test_a_kept_report_is_not_given_for_a_later_task(self):
        # The task tool's result never came (cancelled), and the Lead resumes the subagent: its new report stands.
        steps = (self.start("sub", "lead") + self.answer("sub", "m1", "the first report") + [self.compacts("sub")] +
                 self.answer("sub", "m2", "the second report") + [self.task("sub", "the second report")])
        got = self.run_steps(steps)["results"]
        self.assertFalse(got[0])
        self.assertIn("the second report", got[1])
        self.assertNotIn("the first report", got[1])

    def test_a_report_put_back_is_cut_as_opencode_cuts_a_tools_output(self):
        # OpenCode keeps a cut output's first lines within 2000 lines and 51,200 bytes, its layout counted; here
        # the layout around a report is 4 lines and 69 bytes (a one-letter task id)
        reports = {
            "a": "\n".join(f"line {i}" for i in range(1996)),       # fits: 2000 lines
            "b": "\n".join(f"line {i}" for i in range(1997)),
            "c": "x" * (51200 - 69),                                 # fits: 51,200 bytes
            "d": "x" * (51200 - 68),                                 # one line too long: whole characters
            "e": "a" + "\U0001F600" * 13000,                         # 4 bytes, two UTF-16 units a character
            "f": "\n".join(["y" * 99] * 600),                        # 99 bytes and a newline a line
        }
        steps = []
        for session, report in reports.items():
            steps += (self.start(session, "lead") + self.answer(session, "m" + session, report) +
                      [self.compacts(session), self.task(session, "a summary")])
        got = dict(zip(reports, self.run_steps(steps)["results"][1::2]))

        def kept(session):
            body = got[session].split("<task_result>\n", 1)[1].rsplit("\n</task_result>", 1)[0]
            text, note = body.split("\n\n(the report is cut to fit OpenCode's tool output limits, ")
            self.assertEqual(note, f"2000 lines or 51200 bytes; all of it is in the subagent's session, "
                                   f"task id {session})")
            self.assertEqual(got[session], self.layout(session, body))
            without_note = self.layout(session, text)
            self.assertLessEqual(len(without_note.split("\n")), 2000)
            self.assertLessEqual(len(without_note.encode("utf-8")), 51200)
            return text

        self.assertEqual(len(self.layout("a", "").encode("utf-8")), 69)
        self.assertEqual(got["a"], self.layout("a", reports["a"]))
        self.assertEqual(kept("b"), reports["a"])
        self.assertEqual(got["c"], self.layout("c", reports["c"]))
        self.assertEqual(kept("d"), reports["c"])
        self.assertEqual(kept("e"), "a" + "\U0001F600" * 12782)   # 1 + 51,128 bytes, and no broken character
        self.assertEqual(kept("f").split("\n"), ["y" * 99] * 511)  # 511 lines: 51,099 bytes


class CloudCapPluginTests(unittest.TestCase):
    # .opencode/plugin/fo4-cloud-cap.js, driven with the events and the chat.params call OpenCode 1.18.35 makes
    HARNESS = r"""
import { readFileSync } from "node:fs";
const [url, root, stepsFile] = process.argv.slice(2);
const hooks = await (await import(url)).default({ worktree: root, directory: root });
const out = [];
for (const [kind, arg] of JSON.parse(readFileSync(stepsFile, "utf8"))) {
  if (kind === "event") { await hooks.event({ event: arg }); continue; }
  try {
    await hooks["chat.params"]({ sessionID: "s", agent: "fo4-lead", model: arg, provider: {}, message: {} }, {});
    out.push("ok");
  } catch (err) { out.push(err.message); }
}
console.log(JSON.stringify(out));
"""
    CLAUDE = {"id": "claude-sonnet-5-5", "providerID": "anthropic"}
    LOCAL = {"id": "fo4-lead", "providerID": "guardian"}
    OWNER = {"FO4SF_OWNER_PRESENT": "1"}

    def setUp(self):
        if not shutil.which("node"):
            self.fail("node is not installed: CI must run the plugin tests")
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.state = os.path.join(self.d, "state")
        self.ledger = os.path.join(self.state, "cloud-spend.json")
        self.cap({"cloud": {"monthly_cap_usd": 1}})

    def cap(self, cfg):
        os.makedirs(os.path.join(self.d, "root", "tools", "ai-team"), exist_ok=True)
        with open(os.path.join(self.d, "root", "tools", "ai-team", "config.json"), "w") as f:
            f.write(cfg if isinstance(cfg, str) else json.dumps(cfg))

    def tally(self, value):
        os.makedirs(self.state, exist_ok=True)
        with open(self.ledger, "w") as f:
            f.write(value if isinstance(value, str) else json.dumps(value))

    def run_steps(self, steps, state=None, **env):
        plugin = os.path.join(self.d, "fo4-cloud-cap.mjs")
        shutil.copy(os.path.join(ROOT, ".opencode", "plugin", "fo4-cloud-cap.js"), plugin)
        harness = os.path.join(self.d, "harness.mjs")
        with open(harness, "w") as f:
            f.write(self.HARNESS)
        with open(os.path.join(self.d, "steps.json"), "w") as f:
            json.dump(steps, f)
        e = {k: v for k, v in os.environ.items() if not k.startswith(("FO4SF_", "FO4_AI_TEAM_STATE"))}
        e.update({"FO4_AI_TEAM_STATE": state or self.state, **env})
        r = subprocess.run(["node", harness, "file://" + plugin, os.path.join(self.d, "root"),
                            os.path.join(self.d, "steps.json")], capture_output=True, text=True, env=e, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    @staticmethod
    def spend(msg, cost, provider="anthropic", role="assistant"):
        return ["event", {"type": "message.updated", "properties": {"sessionID": "s", "info": {
            "id": msg, "sessionID": "s", "role": role, "providerID": provider, "modelID": "m", "cost": cost}}}]

    def month(self):
        return time.strftime("%Y-%m", time.gmtime())

    def test_claude_runs_only_in_the_owners_terminal(self):
        steps = [["params", self.CLAUDE], ["params", self.LOCAL]]
        self.assertEqual(self.run_steps(steps, **self.OWNER), ["ok", "ok"])
        for env in ({}, {"FO4SF_OWNER_PRESENT": "true"}, {"FO4SF_OWNER_PRESENT": "1", "FO4SF_UNATTENDED": "1"},
                    {"FO4SF_UNATTENDED": "1"}):
            got = self.run_steps(steps, **env)
            self.assertIn("only in the owner's terminal", got[0], env)
            self.assertEqual(got[1], "ok", env)                    # the local models are never touched

    def test_spend_is_tallied_across_windows_and_capped(self):
        got = self.run_steps([
            self.spend("a", 0.3), self.spend("a", 0.7),            # one message's cost so far: 0.7 in all
            self.spend("a", 0.7), self.spend("a", 0.5),            # an update that did not grow it counts nothing
            self.spend("l", 5.0, provider="guardian"),             # a local model's cost is not Claude's
            self.spend("u", 5.0, role="user"), self.spend("x", "5"),
            ["event", dict(self.spend("y", 5.0)[1], type="session.updated")],
            ["params", self.CLAUDE],
            self.spend("b", 0.4),                                  # 1.1 of the 1 dollar cap
            ["params", self.CLAUDE], ["params", self.LOCAL]], **self.OWNER)
        self.assertEqual(got[:1], ["ok"])
        self.assertIn("this month's Claude spend is $1.10 of the $1 cap", got[1])
        self.assertEqual(got[2], "ok")
        with open(self.ledger) as f:
            t = json.load(f)
        self.assertEqual(t["month"], self.month())
        self.assertAlmostEqual(t["usd"], 1.1)
        # another OpenCode window reads the same tally
        self.assertIn("of the $1 cap", self.run_steps([["params", self.CLAUDE]], **self.OWNER)[0])

    def test_a_new_month_starts_again(self):
        self.tally({"month": "2000-01", "usd": 999})
        self.assertEqual(self.run_steps([["params", self.CLAUDE], self.spend("a", 0.2)], **self.OWNER), ["ok"])
        with open(self.ledger) as f:
            self.assertEqual(json.load(f), {"month": self.month(), "usd": 0.2})

    def test_a_cap_or_a_tally_that_cannot_be_read_refuses(self):
        for cfg in ({}, {"cloud": {}}, {"cloud": {"monthly_cap_usd": 0}}, {"cloud": {"monthly_cap_usd": -5}},
                    {"cloud": {"monthly_cap_usd": "50"}}, "{not json"):
            self.cap(cfg)
            got = self.run_steps([["params", self.CLAUDE], ["params", self.LOCAL]], **self.OWNER)
            self.assertIn("no cloud.monthly_cap_usd", got[0], cfg)
            self.assertEqual(got[1], "ok", cfg)
        self.cap({"cloud": {"monthly_cap_usd": 1}})
        for bad in ("{not json", {"month": self.month()}, {"month": self.month(), "usd": "0.5"},
                    {"month": self.month(), "usd": -1}):
            self.tally(bad)
            self.assertIn("cannot be read", self.run_steps([["params", self.CLAUDE]], **self.OWNER)[0], bad)
        # a tally that cannot be written: the state folder is a file
        os.remove(self.ledger)
        blocked = os.path.join(self.d, "a-file")
        open(blocked, "w").close()
        got = self.run_steps([["params", self.CLAUDE], self.spend("a", 0.1), ["params", self.CLAUDE]], state=blocked,
                             **self.OWNER)
        self.assertEqual(got[0], "ok")
        self.assertIn("could not be updated", got[1])


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
        self.assertIn("gh pr view $1 --json statusCheckRollup", text)
        self.assertNotIn("gh pr checks", text)
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
                     "$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'", "$env:OPENCODE_CONFIG_CONTENT = $config",
                     "(& $pythonPath $models opencode --cloud $Cloud | Out-String)",
                     "if ($LASTEXITCODE -ne 0) { \"models.py opencode: $config. Not starting.\"; exit 1 }",
                     "fo4-to-starfield-wt\\local-terminal", "Set-Location $wt"):
            self.assertIn(line, s)
            self.assertLess(s.index(line), launch, line)
        self.assertIn("switch -q --detach origin/main", s)      # a clean terminal worktree goes back to main
        self.assertNotIn("ai/local-terminal", s)                # no branch of its own that could fall behind main

    def test_a_second_terminal_window_leaves_the_worktree_where_it_is(self):
        # The menu can open several windows on the one worktree; a reset to main under an open window would move its
        # agent off the branch it is committing on.
        s = self.script("terminal.ps1")
        mine = s.index("$null = New-Item -ItemType File -Force $mine")
        check = s.index("$others += $id")
        skip = s.index("} elseif ($others) {")
        reset = s.index("git -C $wt switch -q --detach origin/main")
        launch = s.index("& $opencode @argv")
        self.assertLess(s.index("try {"), mine)                 # the file is removed however the script ends
        self.assertTrue(mine < check < skip < reset < launch)
        self.assertEqual(s.count("switch -q --detach"), 1)      # the reset only in the last branch
        # a reused pid is not a window: another kind of process, or one that started after the file was written
        self.assertIn("$_.ProcessName -in 'powershell', 'pwsh' -and $started -and $started -le $f.LastWriteTime", s)
        tail = s[launch:]
        self.assertIn("} finally {", tail)
        self.assertIn("Remove-Item -LiteralPath $mine", tail[tail.index("} finally {"):])

    def test_the_terminal_starts_only_on_files_the_guard_lets_an_agent_write(self):
        s = self.script("terminal.ps1")
        steps = ["git -C $wt switch -q --detach origin/main", "-Filter '__pycache__'",
                 "$local = @(git -C $wt diff --no-renames --name-only HEAD)",
                 "$untracked = @(git -C $wt ls-files --others)",              # untracked, ignored ones included
                 "$local += @($untracked | Where-Object { $_ -notmatch $installFiles })",
                 "$behind = @(git -C $wt diff --no-renames --name-only HEAD origin/main)",
                 "$checker = Join-Path $PSScriptRoot 'guard\\allowlist.py'",   # the main checkout's guard
                 "$refusedHere = @($local | & $pythonPath -I $checker --refused-writes $wt)",
                 "$refusedBehind = @($behind | & $pythonPath -I $checker --refused-writes $wt)",
                 "if ($refusedHere) {", "if ($refusedBehind) {", "& $opencode @argv"]
        at = [s.index(step) for step in steps]
        self.assertEqual(at, sorted(at))
        self.assertNotIn("--exclude-standard", s)
        self.assertNotIn("WARNING: its guard", s)                 # it used to warn and start anyway
        for block in ("if ($refusedHere) {", "if ($refusedBehind) {"):
            body = s[s.index(block):]
            self.assertIn("exit 1", body[:body.index("\n  }")], block)
        # git's and the checker's own failures stop it too, rather than starting on an unchecked tree
        for step in ("worktree add -q --detach $wt origin/main", "switch -q --detach origin/main", "--name-only HEAD)",
                     "ls-files --others)", "--name-only HEAD origin/main)", "--refused-writes $wt)"):
            for i in [m.start() for m in re.finditer(re.escape(step), s)]:
                self.assertTrue(s[i:].split("\n", 1)[1].lstrip().startswith("if ($LASTEXITCODE -ne 0)"), step)

    def test_only_opencodes_install_files_are_left_out_of_the_start_check(self):
        pattern = re.search(r"\$installFiles = '([^']+)'", self.script("terminal.ps1")).group(1)
        for path in (".opencode/node_modules/x/index.js", ".opencode/package.json", ".opencode/package-lock.json",
                     ".opencode/bun.lock", ".opencode/.gitignore", ".OpenCode/Package.json"):
            self.assertTrue(re.search(pattern, path, re.I), path)       # PowerShell's -notmatch ignores case
        for path in (".opencode/plugin/x.js", ".opencode/agents/fo4-lead.md", ".opencode/plugin/package.json",
                     ".opencode/package.json.bak", "x/.opencode/package.json", "package.json", "tools/ai-team/x.py",
                     ".opencode/node_modules", "tools/ai-team/__pycache__/x.pyc"):
            self.assertFalse(re.search(pattern, path, re.I), path)

    def start_check(self):
        # The script's own git listings and filter, and the guard's --refused-writes mode, on a synthetic worktree.
        s = self.script("terminal.ps1")
        listing = {v: re.search(r"\$%s = @\(git -C \$wt ([^)]*)\)" % v, s).group(1).split()
                   for v in ("local", "untracked", "behind")}
        pattern = re.search(r"\$installFiles = '([^']+)'", s).group(1)
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        empty = os.path.join(home, "empty.gitconfig")
        open(empty, "w").close()
        env = dict(os.environ, HOME=home, GIT_CONFIG_GLOBAL=empty, GIT_CONFIG_NOSYSTEM="1", LC_ALL="C", GIT_AUTHOR_NAME="t",
                   GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        wt = os.path.join(home, "wt")

        def git(*a, check=True):
            r = subprocess.run(["git", "-C", wt, *a], capture_output=True, text=True, env=env)
            if check:
                self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout if check else r

        def write(rel, text="x\n"):
            os.makedirs(os.path.dirname(os.path.join(wt, rel)) or wt, exist_ok=True)
            with open(os.path.join(wt, rel), "w") as f:
                f.write(text)

        def refused():
            here = git(*listing["local"]).split() + [p for p in git(*listing["untracked"]).split()
                                                     if not re.search(pattern, p, re.I)]
            out = {}
            for name, paths in (("here", here), ("behind", git(*listing["behind"]).split())):
                r = subprocess.run([sys.executable, "-I", os.path.join(TEAM, "guard", "allowlist.py"),
                                    "--refused-writes", wt], input="\r\n".join(paths), capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                out[name] = r.stdout
            return out

        os.makedirs(wt)
        git("init", "-q", "-b", "main")
        write(".gitignore", "*.log\n")
        write(".opencode/plugin/fo4-guard.js")
        write("src/a.py")
        write("docs/ai/notes/lead.md")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
        return s, git, write, refused

    def test_the_start_check_catches_what_it_is_for(self):
        s, git, write, refused = self.start_check()
        write("src/a.py", "an agent's edit\n")
        write("tests/test_new.py")
        for rel in (".opencode/node_modules/p/index.js", ".opencode/package.json", ".opencode/bun.lock"):
            write(rel)
        self.assertEqual(refused(), {"here": "", "behind": ""})          # an agent's own work and OpenCode's installs
        for rel in (".opencode/plugin/fo4-guard.js", ".opencode/plugin/extra.log", "docs/ai/AGENTS.md",
                    "opencode.jsonc", "tools/ai-team/guard/allowlist.py"):
            write(rel, "planted\n")
            self.assertIn(rel, refused()["here"], rel)                   # changed, added, or added and ignored
            git("reset", "-q", "--hard")
            git("clean", "-qfdx")
        git("switch", "-q", "-c", "ai/1-x")
        write(".opencode/plugin/fo4-guard.js", "older\n")
        git("commit", "-qam", "on the branch")
        self.assertIn(".opencode/plugin/fo4-guard.js", refused()["behind"])

    def test_an_uncommitted_note_with_no_branch_moves_to_main_with_the_worktree(self):
        # The case that locked the terminal: no branch, a Lead's uncommitted note, and main has since changed a file
        # the guard protects. The script's own switch carries the note to main's newest commit, and the start check
        # then passes; a note that clashes with main's newer copy stays, and the switch leaves it as it was.
        s, git, write, refused = self.start_check()
        switch = re.search(r"git -C \$wt (switch -q --detach origin/main)", s).group(1).split()
        git("switch", "-q", "--detach", "HEAD")
        write("docs/ai/notes/lead.md", "the Lead's note\n")
        write("docs/ai/notes/new.md", "a new note\n")
        git("switch", "-q", "-c", "newer-main")
        write(".opencode/plugin/fo4-guard.js", "newer\n")
        git("commit", "-q", "-m", "main moves on", "--", ".opencode/plugin/fo4-guard.js")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
        git("switch", "-q", "--detach", "HEAD~1")
        self.assertEqual(refused()["here"], "")                          # a note is an agent's own work
        self.assertIn(".opencode/plugin/fo4-guard.js", refused()["behind"])   # what locked the terminal
        git(*switch)
        self.assertEqual(git("rev-parse", "HEAD"), git("rev-parse", "origin/main"))
        self.assertEqual(refused(), {"here": "", "behind": ""})
        self.assertEqual(git("status", "--porcelain").split(),
                         ["M", "docs/ai/notes/lead.md", "??", "docs/ai/notes/new.md"])
        # a clash: main changes the note too, so git refuses the switch and nothing moves
        write("docs/ai/notes/lead.md", "main's copy\n")
        git("commit", "-q", "-m", "main changes the note", "--", "docs/ai/notes/lead.md")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
        git("switch", "-q", "--detach", "HEAD~1")
        write("docs/ai/notes/lead.md", "the Lead's note\n")
        before = git("rev-parse", "HEAD")
        self.assertNotEqual(git(*switch, check=False).returncode, 0)
        self.assertEqual(git("rev-parse", "HEAD"), before)
        with open(os.path.join(git("rev-parse", "--show-toplevel").strip(), "docs/ai/notes/lead.md")) as f:
            self.assertEqual(f.read(), "the Lead's note\n")

    def test_git_tells_a_clash_in_the_words_the_terminal_reads(self):
        # terminal.ps1 takes a failed move as a clash only on git's own words, and lists the paths from git's message.
        # Git for Windows ships no translations, so its messages are these English ones (LC_ALL=C here).
        s, git, write, refused = self.start_check()
        switch = re.search(r"git -C \$wt (switch -q --detach origin/main)", s).group(1).split()
        clash = re.search(r"\"\$moved\" -match '([^']*)'", s).group(1)
        own = re.search(r"\$_ -notmatch '([^']*)'", s).group(1)
        top = git("rev-parse", "--show-toplevel").strip()
        base = git("rev-parse", "HEAD").strip()

        def main_with(change):          # a newer main from the base commit; the worktree goes back to the base
            git("switch", "-q", "--detach", base)
            change()
            git("add", "-A")
            git("commit", "-q", "-m", "main moves on")
            git("update-ref", "refs/remotes/origin/main", "HEAD")
            git("switch", "-q", "--detach", base)

        said = []                       # git's lines on each move

        def move():
            r = git(*switch, check=False)
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertEqual(git("rev-parse", "HEAD").strip(), base)     # nothing moved
            said.append(r.stderr.splitlines())
            listed = [line.strip() for line in said[-1] if line.strip() and not re.search(own, line.strip(), re.I)]
            return bool(re.search(clash, r.stderr, re.I)), listed

        def turn_src_into_a_file():
            git("rm", "-q", "-r", "src")
            write("src", "now a file\n")

        main_with(lambda: write("docs/ai/notes/lead.md", "main's copy\n"))
        write("docs/ai/notes/lead.md", "the Lead's note\n")                    # a tracked edit
        self.assertEqual(move(), (True, ["docs/ai/notes/lead.md"]))
        git("checkout", "-q", "--", ".")
        main_with(lambda: write("docs/ai/notes/new.md", "main's new file\n"))
        write("docs/ai/notes/new.md", "the Lead's new note\n")                # an untracked file in main's way
        self.assertEqual(move(), (True, ["docs/ai/notes/new.md"]))
        os.remove(os.path.join(top, "docs/ai/notes/new.md"))
        main_with(turn_src_into_a_file)
        write("src/b.py", "the agent's new file\n")                          # main makes its folder a file
        self.assertEqual(move(), (True, ["src"]))
        os.remove(os.path.join(top, "src/b.py"))
        write("docs/ai/notes/other.md", "a note main does not touch\n")      # a stale lock is no clash: stop
        open(os.path.join(top, ".git", "index.lock"), "w").close()
        self.assertFalse(move()[0])
        self.assertIn("index.lock", said[-1][0])        # the stop message gives git's first line

    def test_the_worktree_moves_only_with_no_branch_and_no_other_window(self):
        s = self.script("terminal.ps1")
        block = s[s.index("} elseif ($others) {"):s.index("# HEAD: no branch")]
        # each condition with the line it leads to, in order: read the state, keep a branch's edits, move, tell a clash
        # (git's own words for one) from any other failure, list the clashing paths, and say "moved" only when HEAD
        # did move
        steps = [r'\$on = "\$\(git -C \$wt rev-parse --abbrev-ref HEAD\)"\.Trim\(\)',
                 r'\$was = "\$\(git -C \$wt rev-parse HEAD\)"\.Trim\(\)',
                 r'\$dirty = @\(git -C \$wt status --porcelain\)',
                 r'if \(\$LASTEXITCODE -ne 0 -or -not \$on -or -not \$was\) \{ "could not read [^"]*"; exit 1 \}',
                 r'if \(\$dirty -and \$on -ne \'HEAD\'\) \{ "note: \$wt has uncommitted changes on \$on, so it stays',
                 r'else \{\s*\$moved = @\(git -C \$wt switch -q --detach origin/main 2>&1\)\s*'
                 r'if \(\$LASTEXITCODE -ne 0\) \{',
                 r'if \(-not \$dirty -or -not \("\$moved" -match \'would be overwritten\|would lose untracked '
                 r'files\'\)\) \{\s*"could not move \$wt to main \(git: \$\(\("\$\(\$moved \| Select-Object -First 1\)"\)'
                 r'\.Trim\(\)\)\): not starting"; exit 1\s*\}\s*'
                 r'"note: \$wt has uncommitted edits that clash with main\'s newer files, so it stays at its older',
                 r'\$moved \| ForEach-Object \{ "\$_"\.Trim\(\) \} \|\s*Where-Object \{ \$_ -and \$_ -notmatch \'[^\']*\' \} '
                 r'\|\s*Select-Object -First 20 \| ForEach-Object \{ "  \$_" \}',
                 r'\} elseif \(\$dirty -and "\$\(git -C \$wt rev-parse HEAD\)"\.Trim\(\) -ne \$was\) \{\s*'
                 r'"note: moved \$wt to main\'s newest commit with its uncommitted edits"']
        at = []
        for step in steps:
            m = re.search(step, block)
            self.assertIsNotNone(m, step)
            at.append(m.start())
        self.assertEqual(at, sorted(at))
        # the branch is read again after the move, before the start check and its messages use it
        recompute = '$on = "$(git -C $wt rev-parse --abbrev-ref HEAD)".Trim()      # HEAD: no branch'
        self.assertLess(s.index("switch -q --detach origin/main"), s.index(recompute))
        self.assertLess(s.index(recompute), s.index("$installFiles = "))
        refusal = s[s.index("if ($refusedBehind) {"):]
        refusal = refusal[:refusal.index("exit 1")]
        for case in (r'if \(\$on -ne \'HEAD\'\) \{\s*"\$wt is on \$on, which differs from main',
                     r'\} else \{\s*"\$wt sits at an older main',
                     r'if \(\$others\) \{ "Another terminal window is open on it: close that window',
                     r'elseif \(\$on -ne \'HEAD\'\) \{ "Have Claude merge main into \$on',
                     r'else \{ "Its uncommitted edits clash with main\'s: have Claude move them onto a branch'):
            self.assertRegex(refusal, case)   # the message names a branch only when there is one

    def test_the_menu_stops_the_loop_before_its_session(self):
        s = self.script("menu.ps1")
        stop = s[s.index("Type stop to stop"):]
        at = [stop.index(x) for x in ("$loop = (Get-Lead).loop", "Stop-Process -Id $loop.Id",
                                      "Remove-Item (Join-Path $state 'run-lead.pid')", "$sessions = @((Get-Lead).session)")]
        self.assertEqual(at, sorted(at))      # the loop is stopped and its file gone before the sessions are looked up
        self.assertIn('ParentProcessId=$($loop.Id)', stop)    # a session the loop started before its pid file
        self.assertIn("$started -le $file.LastWriteTime", s)   # a reused pid is not the run's

    def test_no_variable_is_followed_by_a_colon(self):
        # PowerShell reads "$wt: text" as a drive-qualified variable and refuses to parse the file; "${wt}: text" is
        # the way to write it. CI parses every script too (test_game_scripts), where PowerShell is installed.
        token = re.compile(r"<#.*?#>|#[^\n]*|'(?:[^']|'')*'|\"(?:[^\"`]|`.)*\"", re.S)
        for folder in (TEAM, os.path.join(ROOT, "scripts", "game")):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".ps1"):
                    with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
                        code = token.sub(lambda m: m.group(0) if m.group(0).startswith('"') else " ", f.read())
                    self.assertEqual(re.findall(r"\$[A-Za-z_]\w*:(?![\w{:])", code), [], name)

    def test_one_start_rule_for_every_pid_file(self):
        # A pid file left behind can name a pid Windows has given out again: the process it named started before it.
        for name, rule in (("run-lead.ps1", "$started -le $file.LastWriteTime.AddSeconds(2)"),
                           ("terminal.ps1", "$started -le $f.LastWriteTime.AddSeconds(2)"),
                           ("menu.ps1", "$started -le $file.LastWriteTime.AddSeconds(2)")):
            self.assertIn(rule, self.script(name), name)

    def test_unattended_runs_never_count_as_the_owners_terminal(self):
        s = self.script("run-lead.ps1")
        self.assertEqual(re.findall(r"\$env:FO4SF_OWNER_PRESENT = (\S+)", s), ["$null"])   # removed, never set
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
