"""Headless and synthetic-signal tests for X8 Start Cover (src/fo4sf/launcher/start_cover.py).

Never starts Starfield.exe, Steam, or ProcDump; importing start_cover needs neither tkinter nor a display.
"""
import ast
import json
import os
import posixpath
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import gui, settings, start_cover  # noqa: E402


def can_open_a_window():
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:
        return False


class FakeClock:
    def __init__(self, now=100.0):
        self.t = float(now)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += float(dt)


class StartCoverHeadlessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.signal_path = self.root / "start_ready.json"

    def test_module_is_stdlib_only_no_top_level_tkinter_and_clean_room_banner(self):
        source = (ROOT / "src" / "fo4sf" / "launcher" / "start_cover.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        top_imports = set()
        forbidden_calls = {"focus_force", "focus_set", "grab_set", "SendInput", "keybd_event"}
        seen_calls = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_imports.add(node.module.split(".")[0])
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    seen_calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    seen_calls.add(node.func.attr)
        self.assertNotIn("tkinter", top_imports)
        self.assertEqual(seen_calls & forbidden_calls, set())

        # Clean-room Fallout-style terminal art/text ONLY — zero Bethesda logo/music/movie assets.
        rendered = "\n".join(start_cover.COVER_BANNER_LINES) + "\n" + "\n".join(
            line for _k, line in start_cover.COVER_STAGE_LINES
        )
        self.assertIn("FO4SF // PIP-OS", rendered)
        low = rendered.lower()
        for forbidden_word in ("bethesda", "zenimax", "todd", ".bk2", ".bik", ".swf", ".mp3", ".wav"):
            self.assertNotIn(forbidden_word, low)

    def test_settings_default_off_and_timeout_validation(self):
        d = settings.defaults()
        self.assertIs(d["start_cover"], False)
        self.assertEqual(d["start_cover.timeout_s"], 90.0)
        self.assertEqual(settings.problems(d), [])

        on_valid = settings.assign(d, ["start_cover=on", "start_cover.timeout_s=45"])
        self.assertIs(on_valid["start_cover"], True)
        self.assertEqual(on_valid["start_cover.timeout_s"], 45.0)
        self.assertEqual(settings.problems(on_valid), [])

        on_zero = settings.assign(d, ["start_cover=on", "start_cover.timeout_s=0"])
        self.assertTrue(any("start_cover.timeout_s" in p for p in settings.problems(on_zero)))

    def test_fake_ready_signal_closes_cover_and_releases_file_immediately(self):
        # Write a stale ready file before start() -> start(clear_stale=True) clears it first.
        start_cover.write_fake_ready_signal(str(self.signal_path), nonce="old", stage="stale")
        clock = FakeClock()
        ctrl = start_cover.StartCoverController(
            str(self.signal_path), timeout_s=30.0, expected_nonce="run-42", clock=clock
        )
        snap0 = ctrl.start()
        self.assertTrue(snap0["active"])
        self.assertFalse(self.signal_path.exists())

        clock.advance(2.5)
        self.assertTrue(ctrl.poll()["active"])

        # Wrong nonce is ignored; file is not locked (can be overwritten/removed immediately on Windows).
        start_cover.write_fake_ready_signal(str(self.signal_path), nonce="wrong-nonce", stage="stage20")
        self.assertTrue(ctrl.poll()["active"])
        os.remove(self.signal_path)

        # Partial / corrupt JSON is ignored safely without raising.
        self.signal_path.write_text("{not-complete-json", encoding="utf-8")
        self.assertTrue(ctrl.poll()["active"])

        # Matching ready signal closes the cover immediately.
        start_cover.write_fake_ready_signal(str(self.signal_path), nonce="run-42", stage="stage20_pod_settle", pid=999)
        done = ctrl.poll()
        self.assertFalse(done["active"])
        self.assertEqual(done["state"], "closed")
        self.assertEqual(done["reason"], "ready")
        self.assertEqual(done["ready_info"]["stage"], "stage20_pod_settle")
        self.assertFalse(done["topmost"])
        # Signal file handle is closed immediately (deletable on Windows).
        os.remove(self.signal_path)

    def test_hard_timeout_and_cancel_close_cleanly(self):
        clock = FakeClock()
        ctrl = start_cover.StartCoverController(str(self.signal_path), timeout_s=12.0, clock=clock)
        ctrl.start()
        clock.advance(11.9)
        self.assertTrue(ctrl.poll()["active"])
        clock.advance(0.2)
        timed = ctrl.poll()
        self.assertFalse(timed["active"])
        self.assertEqual(timed["reason"], "timeout")

        ctrl2 = start_cover.StartCoverController(str(self.signal_path), timeout_s=90.0, clock=clock)
        ctrl2.start()
        cancelled = ctrl2.cancel()
        self.assertFalse(cancelled["active"])
        self.assertEqual(cancelled["reason"], "cancelled")
        self.assertFalse(cancelled["topmost"])

    def test_crash_watcher_override_and_early_game_exit_always_beat_ready_signal(self):
        clock = FakeClock()
        # Even if a ready signal file is present simultaneously, crash_fn wins!
        start_cover.write_fake_ready_signal(str(self.signal_path), stage="stage20")
        crash_state = {"msg": ""}
        ctrl = start_cover.StartCoverController(
            str(self.signal_path),
            timeout_s=90.0,
            clock=clock,
            crash_fn=lambda: crash_state["msg"],
        )
        ctrl.start(clear_stale=False)
        crash_state["msg"] = "ProcDump captured ACCESS_VIOLATION"
        snap = ctrl.poll()
        self.assertFalse(snap["active"])
        self.assertEqual(snap["reason"], "crash_detected")
        self.assertIn("ACCESS_VIOLATION", snap["detail"])

        # Tracked game PID appears then vanishes before ready -> closes as game_exited.
        live_pids = [[], [7788], []]
        ctrl_exit = start_cover.StartCoverController(
            str(self.signal_path),
            timeout_s=90.0,
            clock=clock,
            pids_fn=lambda: live_pids.pop(0),
        )
        ctrl_exit.start(clear_stale=True)
        self.assertTrue(ctrl_exit.poll()["active"])   # game not up yet
        self.assertTrue(ctrl_exit.poll()["active"])   # PID 7788 seen
        exited = ctrl_exit.poll()                     # PID 7788 vanished before ready
        self.assertFalse(exited["active"])
        self.assertEqual(exited["reason"], "game_exited")

    def test_alt_tab_topmost_yield_and_win32_noactivate_style(self):
        fg_state = {"hwnd": 9001, "pid": 1111}

        class FakeUser32:
            calls = []

            @classmethod
            def GetAncestor(cls, hwnd, flags):
                cls.calls.append(("ancestor", hwnd, flags))
                return 99999 if hwnd == 12345 and flags == start_cover.GA_ROOT else 0

            @classmethod
            def GetParent(cls, hwnd):
                cls.calls.append(("parent", hwnd))
                return 88888 if hwnd == 54321 else 0

            @classmethod
            def GetWindowLongPtrW(cls, hwnd, idx):
                cls.calls.append(("get", hwnd, idx))
                return 0x00040000

            @classmethod
            def SetWindowLongPtrW(cls, hwnd, idx, style):
                cls.calls.append(("set", hwnd, idx, style))
                return style

            @staticmethod
            def GetForegroundWindow():
                return fg_state["hwnd"]

            @staticmethod
            def foreground_pid_of(_hwnd):
                return fg_state["pid"]

        class FakeKernel32:
            images = {3333: "Starfield.exe", 4444: "explorer.exe"}

            @classmethod
            def image_of(cls, pid):
                return cls.images.get(pid, "")

        # Wrapper HWND resolution: GetAncestor(GA_ROOT) preferred, GetParent fallback, raw hwnd fallback.
        self.assertTrue(start_cover.apply_win32_noactivate(12345, user32=FakeUser32))
        self.assertEqual(FakeUser32.calls[0], ("ancestor", 12345, start_cover.GA_ROOT))
        self.assertEqual(FakeUser32.calls[1], ("get", 99999, start_cover.GWL_EXSTYLE))
        applied_style = FakeUser32.calls[2][3]
        self.assertEqual(FakeUser32.calls[2][1], 99999)
        self.assertTrue(applied_style & start_cover.WS_EX_NOACTIVATE)
        self.assertTrue(applied_style & start_cover.WS_EX_TOOLWINDOW)
        self.assertTrue(applied_style & start_cover.WS_EX_TOPMOST)

        FakeUser32.calls.clear()
        self.assertTrue(start_cover.apply_win32_noactivate(54321, user32=FakeUser32))
        self.assertEqual(FakeUser32.calls[0], ("ancestor", 54321, start_cover.GA_ROOT))
        self.assertEqual(FakeUser32.calls[1], ("parent", 54321))
        self.assertEqual(FakeUser32.calls[2], ("get", 88888, start_cover.GWL_EXSTYLE))
        self.assertFalse(start_cover.apply_win32_noactivate(0, user32=FakeUser32))

        # Foreground PID classification + poll()-driven Alt+Tab topmost transitions.
        ctrl = start_cover.StartCoverController(
            str(self.signal_path),
            pids_fn=lambda: [2222],
            foreground_fn=lambda pids: start_cover.foreground_kind_win32(
                pids, own_pid=1111, user32=FakeUser32, kernel32=FakeKernel32
            ),
        )
        ctrl.start()
        self.assertTrue(ctrl.poll()["topmost"])   # launcher PID 1111 -> topmost True
        fg_state["pid"] = 4444                    # Explorer PID 4444 (Alt+Tab) -> topmost False
        self.assertFalse(ctrl.poll()["topmost"])
        fg_state["pid"] = 2222                    # tracked game PID 2222 -> topmost True
        self.assertTrue(ctrl.poll()["topmost"])
        fg_state["pid"] = 3333                    # newly spawned Starfield.exe before pids_fn refresh -> topmost True
        self.assertTrue(ctrl.poll()["topmost"])

    def test_cross_os_paths_and_cover_signal_cli(self):
        drv = "D:"
        with mock.patch("os.path.basename", side_effect=posixpath.basename):
            self.assertEqual(start_cover.path_basename(drv + "\\Local\\FO4SF\\start_ready.json"), "start_ready.json")
            self.assertEqual(start_cover.path_basename("/tmp/fo4sf/start_ready.json"), "start_ready.json")
            self.assertEqual(start_cover.path_basename("\\\\nas\\share\\FO4SF\\start_ready.json"), "start_ready.json")
            win_sig = start_cover.default_signal_path({"LOCALAPPDATA": drv + "\\UsersData\\Local"})
            self.assertTrue(win_sig.endswith("FO4SF\\start_ready.json"), win_sig)
            pos_sig = start_cover.default_signal_path({"XDG_STATE_HOME": "/var/tmp/state"})
            self.assertTrue(pos_sig.replace("\\", "/").endswith("FO4SF/start_ready.json"), pos_sig)

        cli_sig = self.root / "cli_ready.json"
        proc = subprocess.run(
            [
                sys.executable, "-I", str(ROOT / "scripts" / "launcher.py"),
                "cover-signal", "--signal-file", str(cli_sig), "--nonce", "n1", "--stage", "cli_ok",
            ],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        ok, info = start_cover.read_ready_signal(str(cli_sig), expected_nonce="n1")
        self.assertTrue(ok)
        self.assertEqual(info["stage"], "cli_ok")

    def test_workflow_steps_headless_model(self):
        s0 = gui.workflow_steps(
            settings.defaults(),
            loc_statuses={"fo4_data": "missing", "starfield": "missing", "my_games": "missing"},
            play_reason="Choose the Starfield folder first (Locations tab)",
        )
        self.assertEqual([r["label"] for r in s0], ["1. Locate", "2. Build or Update", "3. Play"])
        self.assertEqual((s0[0]["ready"], s0[0]["tone"]), (False, "bad"))
        self.assertEqual((s0[1]["ready"], s0[1]["tone"]), (False, "muted"))
        self.assertFalse(s0[2]["ready"])

        saved_cov = dict(settings.defaults(), start_cover=True)
        s_ready = gui.workflow_steps(
            saved_cov,
            loc_statuses={"fo4_data": "saved", "starfield": "saved", "my_games": "saved"},
            play_reason="",
        )
        self.assertTrue(all(r["ready"] for r in s_ready))
        self.assertEqual([r["tone"] for r in s_ready], ["ok", "ok", "ok"])
        self.assertIn("cover on", s_ready[2]["detail"])


@unittest.skipUnless(can_open_a_window(), "needs tkinter and a display")
class StartCoverRealTkTests(unittest.TestCase):
    def test_standalone_cover_window_closes_on_fake_ready_and_on_cancel(self):
        script = r"""
import json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
import tkinter as tk
from fo4sf.launcher import start_cover

d = tempfile.mkdtemp()
sig = os.path.join(d, "start_ready.json")
root = tk.Tk()
root.withdraw()

fg_mode = {"kind": "game"}
closed_reasons = []
ctrl1 = start_cover.StartCoverController(sig, timeout_s=30.0, foreground_fn=lambda _p=(): fg_mode["kind"])
win1 = start_cover.StartCoverWindow(root, ctrl1, fullscreen=False, on_closed=lambda s: closed_reasons.append(s["reason"]))
root.update()
topmost_initial = bool(win1.win.attributes("-topmost"))
fg_mode["kind"] = "other"
end = time.time() + 1.0
while time.time() < end and bool(win1.win.attributes("-topmost")):
    root.update()
    time.sleep(0.05)
topmost_after_alt_tab = bool(win1.win.attributes("-topmost"))
fg_mode["kind"] = "game"
end = time.time() + 1.0
while time.time() < end and not bool(win1.win.attributes("-topmost")):
    root.update()
    time.sleep(0.05)
topmost_restored = bool(win1.win.attributes("-topmost"))

start_cover.write_fake_ready_signal(sig, stage="vault111_stage20")
end = time.time() + 2.0
while time.time() < end and not closed_reasons:
    root.update()
    time.sleep(0.05)

ctrl2 = start_cover.StartCoverController(sig, timeout_s=30.0)
win2 = start_cover.StartCoverWindow(root, ctrl2, fullscreen=False, on_closed=lambda s: closed_reasons.append(s["reason"]))
root.update()
win2.cancel_button.invoke()
root.update()
root.destroy()
print(json.dumps({
    "reasons": closed_reasons,
    "topmost_initial": topmost_initial,
    "topmost_after_alt_tab": topmost_after_alt_tab,
    "topmost_restored": topmost_restored,
}))
"""
        proc = subprocess.run(
            [sys.executable, "-I", "-c", script, str(ROOT / "src")],
            capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(out["reasons"], ["ready", "cancelled"])
        self.assertTrue(out["topmost_initial"])
        self.assertFalse(out["topmost_after_alt_tab"])
        self.assertTrue(out["topmost_restored"])


if __name__ == "__main__":
    unittest.main()
