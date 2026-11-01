"""The launcher's self-update (src/fo4sf/launcher/selfupdate.py) on throwaway git repositories: a bare "GitHub" and a
clone the launcher runs from. Only a clean main with nothing of its own moves, and only by a fast-forward."""
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import restore, selfupdate, settings  # noqa: E402

class GameRunningGateTests(unittest.TestCase):
    def test_failed_query_refuses_update_before_any_git_command(self):
        for stdout, stderr in (("ERROR: Access is denied.", ""), ("", "Access is denied."), ("", "")):
            with self.subTest(stdout=stdout, stderr=stderr), \
                 mock.patch.object(restore.os, "name", "nt"), \
                 mock.patch.object(restore.subprocess, "run", return_value=subprocess.CompletedProcess(
                     ["tasklist"], 1, stdout, stderr)), \
                 mock.patch.object(selfupdate, "git", side_effect=AssertionError("unknown game state")), \
                 mock.patch.dict(os.environ, {selfupdate.RESTARTED: ""}):
                said = []
                self.assertTrue(restore.game_running())
                self.assertFalse(selfupdate.update("unused", "pull", say=said.append, running=restore.game_running))
                self.assertIn("skipped while Starfield runs", said[0])

    def test_successful_query_distinguishes_running_and_absent(self):
        for stdout, expected in (("Starfield.exe 1234 Console 1 100 K", True),
                                 ("INFO: No tasks are running which match the specified criteria.", False)):
            with self.subTest(stdout=stdout), mock.patch.object(restore.os, "name", "nt"), \
                 mock.patch.object(restore.subprocess, "run", return_value=subprocess.CompletedProcess(
                     ["tasklist"], 0, stdout, "")):
                self.assertEqual(restore.game_running(), expected)

    def test_unavailable_or_timed_out_query_remains_unknown(self):
        for error in (OSError("tasklist unavailable"), subprocess.TimeoutExpired("tasklist", 30)):
            with self.subTest(error=error), mock.patch.object(restore.os, "name", "nt"), \
                 mock.patch.object(restore.subprocess, "run", side_effect=error):
                self.assertTrue(restore.game_running())


# throwaway repositories: no signing, a fixed identity, no hooks or templates from the machine's own config
GIT = ["git", "-c", "commit.gpgsign=false", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
       "-c", "init.defaultBranch=main", "-c", f"core.hooksPath={os.devnull}"]


def git(cwd, *args):
    r = subprocess.run([*GIT, *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"git {' '.join(args)}: {r.stdout}{r.stderr}")
    return r.stdout.strip()


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class SelfUpdateTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.hub = os.path.join(self.root, "hub.git")
        git(self.root, "init", "--bare", "-b", "main", self.hub)
        self.dev = os.path.join(self.root, "dev")                    # where merges land on "GitHub"
        git(self.root, "clone", "-q", self.hub, self.dev)
        self.commit(self.dev, "a.txt", "one", "first")
        git(self.dev, "push", "-q", "origin", "HEAD:main")
        self.pc = os.path.join(self.root, "pc")                      # the owner's checkout the launcher runs from
        git(self.root, "clone", "-q", self.hub, self.pc)
        self.said = []
        env = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(selfupdate.RESTARTED, None)

    def commit(self, repo, name, text, msg):
        with open(os.path.join(repo, name), "w", encoding="utf-8") as f:
            f.write(text)
        git(repo, "add", name)
        git(repo, "commit", "-q", "-m", msg)

    def merged(self, n=1):
        for k in range(n):
            self.commit(self.dev, "a.txt", f"merged {k}", f"merged change {k}")
        git(self.dev, "push", "-q", "origin", "HEAD:main")
        return git(self.dev, "rev-parse", "HEAD")

    def head(self):
        return git(self.pc, "rev-parse", "HEAD")

    def update(self, mode, **kw):
        return selfupdate.update(self.pc, mode, say=self.said.append, **kw)

    def test_off_fetches_nothing(self):
        self.merged()
        before = self.head()
        with mock.patch.object(selfupdate, "git", side_effect=AssertionError("off must not run git")):
            self.assertFalse(self.update("off"))
        self.assertEqual((self.head(), self.said), (before, []))

    def test_check_says_how_far_behind_and_moves_nothing(self):
        self.merged(2)
        before = self.head()
        self.assertFalse(self.update("check"))
        self.assertEqual(self.head(), before)
        self.assertIn("has 2 new commit(s)", self.said[-1])

    def test_pull_fast_forwards_a_clean_main_and_lists_what_came(self):
        new = self.merged(2)
        old = self.head()
        self.assertTrue(self.update("pull"))
        self.assertEqual(self.head(), new)
        self.assertIn(f"main {old[:7]} -> {new[:7]}, 2 commit(s):", self.said[0])
        self.assertTrue(any("merged change 1" in s for s in self.said))
        self.said = []
        self.assertFalse(self.update("pull"))                        # nothing more to bring
        self.assertIn("up to date", self.said[-1])

    def test_untracked_files_do_not_stop_it(self):
        new = self.merged()
        with open(os.path.join(self.pc, "notes.local"), "w", encoding="utf-8") as f:
            f.write("mine")
        self.assertTrue(self.update("pull"))
        self.assertEqual(self.head(), new)
        self.assertTrue(os.path.exists(os.path.join(self.pc, "notes.local")))

    def refused(self, text, mode="pull"):
        before = self.head()
        self.assertFalse(self.update(mode))
        self.assertEqual(self.head(), before)
        self.assertTrue(any(text in s for s in self.said), self.said)

    def test_a_changed_tracked_file_is_never_overwritten(self):
        self.merged()
        with open(os.path.join(self.pc, "a.txt"), "w", encoding="utf-8") as f:
            f.write("an edit of the owner's")
        self.refused("tracked file(s) changed")
        with open(os.path.join(self.pc, "a.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "an edit of the owner's")

    def test_another_branch_is_never_moved(self):
        self.merged()
        git(self.pc, "checkout", "-q", "-b", "claude/some-work")
        self.refused("not main")
        git(self.pc, "checkout", "-q", "--detach")
        self.refused("detached HEAD")

    def test_local_commits_are_never_merged_or_dropped(self):
        self.merged()
        self.commit(self.pc, "b.txt", "local", "a local commit")
        mine = self.head()
        self.refused("1 commit(s) GitHub's main lacks")
        self.assertEqual(self.head(), mine)

    def test_an_operation_in_progress_stops_it(self):
        self.merged()
        gitdir = git(self.pc, "rev-parse", "--absolute-git-dir")
        with open(os.path.join(gitdir, "MERGE_HEAD"), "w", encoding="utf-8") as f:
            f.write(self.head() + "\n")
        self.refused("operation is in progress (MERGE_HEAD)")

    def test_no_network_goes_on_with_this_version(self):
        git(self.pc, "remote", "set-url", "origin", os.path.join(self.root, "gone.git"))
        self.refused("could not fetch origin/main")

    def test_not_while_the_game_runs_and_not_twice(self):
        self.merged()
        before = self.head()
        self.assertFalse(self.update("pull", running=lambda: True))
        self.assertIn("skipped while Starfield runs", self.said[-1])
        with mock.patch.dict(os.environ, {selfupdate.RESTARTED: "1"}):
            self.assertFalse(self.update("pull"))                      # the restarted command never updates again
        self.assertEqual(self.head(), before)

    def test_a_folder_that_is_no_checkout(self):
        plain = os.path.join(self.root, "plain")
        os.makedirs(plain)
        self.assertFalse(selfupdate.update(plain, "pull", say=self.said.append))
        self.assertIn("skipped", self.said[-1])

    def test_describe_names_the_version_without_fetching(self):
        head = git(self.pc, "rev-parse", "--short=12", "HEAD")
        self.assertEqual(selfupdate.describe(self.pc), f"launcher code: main at {head}, no local changes")
        with open(os.path.join(self.pc, "a.txt"), "w", encoding="utf-8") as f:
            f.write("edited")
        self.assertIn("1 tracked file(s) changed", selfupdate.describe(self.pc))
        git(self.pc, "remote", "set-url", "origin", os.path.join(self.root, "gone.git"))   # no network needed
        self.assertTrue(selfupdate.describe(self.pc).startswith("launcher code: main at"))
        self.assertIn("not a git checkout", selfupdate.describe(self.root))

    def test_no_git_on_the_path(self):
        def no_git(*_a, **_k):
            raise FileNotFoundError("git")
        self.assertFalse(self.update("pull", run=no_git))
        self.assertIn("git is not installed", self.said[-1])


class SettingAndCommandTests(unittest.TestCase):
    def load_cli(self):
        spec = importlib.util.spec_from_file_location("launcher_cli_upd", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        return cli

    def test_the_setting_is_off_by_default_and_takes_only_its_modes(self):
        self.assertEqual(settings.defaults()["update"], "off")
        self.assertEqual(settings.coerce("update", "PULL"), "pull")
        with self.assertRaises(ValueError):
            settings.coerce("update", "always")
        self.assertIn("update", settings.LABELS)

    def test_play_starts_again_after_an_update_and_a_dry_run_only_checks(self):
        cli = self.load_cli()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            settings.save(path, settings.assign(settings.defaults(), ["update=pull"]))
            modes, restarts = [], []
            with mock.patch.object(cli.selfupdate, "update", side_effect=lambda repo, mode, **k: modes.append(mode) or True), \
                    mock.patch.object(cli.selfupdate, "restart", side_effect=lambda argv: restarts.append(argv) or 7):
                self.assertEqual(cli.main(["play", "--settings", path, "--starfield", d]), 7)
                self.assertEqual(modes, ["pull"])
                self.assertEqual(restarts[0][1:], ["play", "--settings", path, "--starfield", d])
                self.assertTrue(restarts[0][0].endswith("launcher.py"))
                modes.clear()
                with mock.patch.object(cli.crashwatch, "play", return_value={"dry_run": True}):
                    cli.selfupdate.update.side_effect = lambda repo, mode, **k: modes.append(mode) or False
                    self.assertEqual(cli.main(["play", "--settings", path, "--starfield", d, "--dry-run"]), 0)
                self.assertEqual(modes, ["check"])                      # a dry run never moves the checkout

    def test_the_window_starts_again_after_an_update_before_it_opens(self):
        cli = self.load_cli()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            settings.save(path, settings.assign(settings.defaults(), ["update=pull"]))
            with mock.patch.object(cli.selfupdate, "update", return_value=True), \
                    mock.patch.object(cli.selfupdate, "restart", return_value=0) as restart, \
                    mock.patch.dict(sys.modules, {"fo4sf.launcher.gui": None}):   # importing the window would fail
                self.assertEqual(cli.main(["gui", "--settings", path]), 0)
            self.assertEqual(restart.call_args[0][0][1:], ["gui", "--settings", path])

    def test_off_never_calls_the_updater(self):
        cli = self.load_cli()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")                         # no file: the defaults, update=off
            with mock.patch.object(cli.selfupdate, "update", side_effect=AssertionError("off")), \
                    mock.patch.object(cli.crashwatch, "play", return_value={"dry_run": True}):
                self.assertEqual(cli.main(["play", "--settings", path, "--starfield", d, "--dry-run"]), 0)

    def test_the_update_command(self):
        cli = self.load_cli()
        modes = []
        with mock.patch.object(cli.selfupdate, "update", side_effect=lambda repo, mode, **k: modes.append(mode) or False):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["update", "--check"]), 0)
                self.assertEqual(cli.main(["update"]), 0)
        self.assertEqual(modes, ["check", "pull"])

    def test_restart_marks_the_new_process(self):
        seen = {}
        selfupdate.restart(["launcher.py", "play"], run=lambda argv, env: seen.update(argv=argv, env=env) or 0)
        self.assertEqual(seen["argv"], [sys.executable, "launcher.py", "play"])
        self.assertEqual(seen["env"][selfupdate.RESTARTED], "1")


if __name__ == "__main__":
    unittest.main()
