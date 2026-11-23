"""Headless GUI model and real settings CLI, synthetic files only. No Tk, game, Steam or watcher is started."""
import io
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
from fo4sf.launcher import alife_tools, gui, paths, settings  # noqa: E402


class GuiModelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.path = self.folder / "settings.json"
        self.launcher = str(ROOT / "scripts" / "launcher.py")
        self.model = gui.SettingsModel(self.launcher, str(self.path))
        self.game = str(self.folder / "game folder")          # Play checks the folder holds Starfield.exe
        os.makedirs(self.game)
        Path(self.game, "Starfield.exe").write_bytes(b"")

    def run_cli(self, argv):
        return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)

    def test_exactly_one_control_per_setting_with_labels_choices_and_costs(self):
        specs = gui.controls()
        # the file locations live on the Locations tab, not among the toggles
        spec = [s for s in settings.SPEC if s[0] not in paths.KEYS]
        self.assertEqual([s["key"] for s in specs], [s[0] for s in spec])
        for desc, (key, default, kind, cost) in zip(specs, spec):
            self.assertEqual((desc["label"], desc["default"], desc["cost"]), (settings.LABELS[key], default, cost))
            expected = "bool" if kind is bool else "choice" if isinstance(kind, tuple) else "text"
            self.assertEqual(desc["kind"], expected)
            self.assertEqual(desc["choices"], kind if isinstance(kind, tuple) else ())

    def test_unchanged_save_never_creates_or_rewrites_settings(self):
        self.assertIsNone(self.model.command("save", self.model.saved))
        self.assertFalse(self.path.exists())
        # Preserve even noncanonical bytes and explicit defaults; this is a no-op, not a reserialization.
        original = b'{\n  "route" : "steam", "crash_watch.min_free_gb": 25\n}\n'
        self.path.write_bytes(original)
        self.model.reload()
        before = self.path.stat().st_mtime_ns
        raw = {k: str(v) if not isinstance(v, bool) else v for k, v in self.model.saved.items()}
        self.assertIsNone(self.model.command("save", raw))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_save_uses_real_settings_command_and_validation(self):
        raw = dict(self.model.saved, **{"crash_watch.dump": "full", "crash_watch.min_free_gb": "42.5"})
        argv = self.model.command("save", raw)
        self.assertEqual(argv[:5], [sys.executable, "-I", "-u", self.launcher, "settings"])
        result = self.run_cli(argv)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.model.reload()
        self.assertEqual(self.model.saved["crash_watch.dump"], "full")
        self.assertEqual(self.model.saved["crash_watch.min_free_gb"], 42.5)
        for invalid in ("nan", "inf", "-1", "nope"):
            raw["crash_watch.min_free_gb"] = invalid
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                self.model.command("save", raw)
            self.assertEqual(self.path.read_bytes(), before)

    def test_save_applies_only_changed_keys_and_preserves_external_settings(self):
        # Someone changes an unrelated key after the window opens; the existing CLI merges only this window's edits.
        self.path.write_text(json.dumps({"route": "exe"}), encoding="utf-8")
        raw = dict(self.model.saved, **{"crash_watch.dump": "full"})
        argv = self.model.command("save", raw)
        self.assertNotIn("route=steam", argv)
        result = self.run_cli(argv)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(settings.load(str(self.path))["route"], "exe")

    def test_watcher_requirements_use_existing_problems_and_are_visible(self):
        raw = dict(self.model.saved, **{"crash_watch.enabled": True})
        # CLI allows saving a setup in progress; Play's existing problems remain visible and block the button.
        self.assertIn("crash_watch.folder", self.model.play_reason(raw, "game", [], windows=True))
        result = self.run_cli(self.model.command("save", raw))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("play would refuse: crash_watch.folder", result.stdout)
        self.assertIn("play would refuse: crash_watch.procdump", result.stdout)

    def test_play_is_disabled_for_running_unknown_and_invalid_state(self):
        raw = dict(self.model.saved)
        for pids, want in ((None, "Checking"), ([123, 456], "already running")):
            self.assertIn(want, self.model.play_reason(raw, "game", pids, windows=True))
            with self.assertRaises(ValueError):
                self.model.command("play", raw, starfield="game", pids=pids, windows=True)
        self.assertIn("Windows", self.model.play_reason(raw, "game", [], windows=False))
        self.assertIn("Choose", self.model.play_reason(raw, "", [], windows=True))
        raw["route"] = "exe"
        self.assertIn("Save", self.model.play_reason(raw, "game", [], windows=True))

    def test_unconfirmed_locations_block_play_until_saved(self):
        raw = dict(self.model.saved, starfield="found game folder")
        self.assertIn("Confirm the locations", self.model.play_reason(raw, "found game folder", [], windows=True))
        raw["route"] = "exe"
        self.assertIn("Save the changed settings", self.model.play_reason(raw, "found game folder", [], windows=True))

    def test_save_settings_never_saves_unconfirmed_locations(self):
        raw = dict(self.model.saved, **{"starfield": "found game", "crash_watch.dump": "full"})
        argv = self.model.command("save", self.model.part(raw, "settings"))
        self.assertIn("crash_watch.dump=full", argv)
        self.assertFalse([a for a in argv if a.startswith("starfield=")])
        argv = self.model.command("save", self.model.part(raw, "locations"))
        self.assertIn("starfield=found game", argv)
        self.assertFalse([a for a in argv if a.startswith("crash_watch.dump=")])
        self.assertEqual(self.model.part(raw), raw)

    def test_play_and_detect_fall_back_to_the_saved_locations(self):
        self.path.write_text(json.dumps({"starfield": self.game, "fo4_data": "Data A;Data B"}), encoding="utf-8")
        self.model.reload()
        argv = self.model.command("play", self.model.saved, pids=[], windows=True)
        self.assertEqual(argv[-2:], ["--starfield", self.game])
        argv = self.model.command("detect")
        self.assertEqual(argv[4:], ["detect", "--settings", str(self.path), "--starfield", self.game,
                                    "--fo4-data", "Data A", "--fo4-data", "Data B"])

    def test_play_waits_while_a_saved_location_no_longer_works(self):
        self.path.write_text(json.dumps({"starfield": self.game}), encoding="utf-8")
        self.model.reload()
        self.assertEqual(self.model.play_reason(self.model.saved, "", [], windows=True), "")
        os.remove(os.path.join(self.game, "Starfield.exe"))          # the game moved since it was confirmed
        self.assertIn("no Starfield.exe", self.model.play_reason(self.model.saved, "", [], windows=True))
        raw = dict(self.model.saved, **{"crash_watch.enabled": True, "crash_watch.folder": self.game,
                                        "crash_watch.procdump": os.path.join(self.game, "gone", "procdump64.exe")})
        self.path.write_text(json.dumps(dict(raw, starfield=self.game)), encoding="utf-8")
        Path(self.game, "Starfield.exe").write_bytes(b"")
        self.model.reload()
        self.assertIn("ProcDump path: file not found", self.model.play_reason(self.model.saved, "", [], windows=True))

    def test_a_late_detection_leaves_the_players_edits_alone(self):
        found = {"starfield": (self.game, "Steam library")}
        self.assertEqual([r["key"] for r in self.model.locations(found)], list(paths.KEYS))
        rows = self.model.locations(found, dirty={"starfield"})
        self.assertNotIn("starfield", [r["key"] for r in rows])
        self.assertEqual(len(rows), len(paths.KEYS) - 1)

    def test_play_delegates_to_existing_cli_for_both_routes(self):
        for route in ("sfse", "steam", "exe"):
            self.path.write_text(json.dumps({"route": route}), encoding="utf-8")
            self.model.reload()
            argv = self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True)
            self.assertEqual(argv[4:], ["play", "--settings", str(self.path), "--starfield", self.game])
            # Do NOT execute this command: the existing play handler owns routes, process checks and the watcher.

    def test_play_starts_the_fo4sf_game_folder_when_one_is_set(self):
        self.path.write_text(json.dumps({"route": "sfse", "instance": "D:/FO4SF/Starfield"}), encoding="utf-8")
        self.model.reload()
        argv = self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True)
        self.assertEqual(argv[-2:], ["--starfield", "D:/FO4SF/Starfield"])

    def test_play_refuses_a_stale_view_of_the_saved_settings(self):
        raw = dict(self.model.saved)
        self.path.write_text(json.dumps({"route": "exe"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed outside"):
            self.model.command("play", raw, starfield=self.game, pids=[], windows=True)
        self.model.reload()
        self.assertEqual(self.model.saved["route"], "exe")
        self.assertIn("play", self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True))

    def test_settings_read_failure_is_a_visible_command_error(self):
        with mock.patch.object(settings, "load", side_effect=PermissionError("settings cannot be read")):
            with self.assertRaisesRegex(ValueError, "Cannot read saved settings"):
                self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True)

    def test_status_and_detect_argv_request_no_writes(self):
        argv = self.model.command("status", recipe="recipe file.json", overrides=["root=some folder"])
        self.assertEqual(argv[4:], ["status", "recipe file.json", "--set", "root=some folder"])
        self.assertNotIn("--json", argv)
        argv = self.model.command("detect", fo4_data=["Data A", "Data B"], starfield="game")
        self.assertEqual(argv[4:], ["detect", "--settings", str(self.path), "--starfield", "game",
                                    "--fo4-data", "Data A", "--fo4-data", "Data B"])
        self.assertNotIn("--report", argv)
        self.assertNotIn("--allow-unknown", argv)
        with self.assertRaises(ValueError):
            self.model.command("status")
        with self.assertRaises(ValueError):
            self.model.command("detect")

    def test_the_update_buttons_run_the_update_command(self):
        self.assertEqual(self.model.command("update-check")[4:], ["update", "--check"])
        self.assertEqual(self.model.command("update")[4:], ["update"])

    def test_saved_my_games_argument_is_forwarded_without_guessing(self):
        self.path.write_text(json.dumps({"my_games": "resolved documents folder"}), encoding="utf-8")
        self.model.reload()
        argv = self.model.command("detect", fo4_data=["data"], starfield="game")
        self.assertEqual(argv[-2:], ["--my-games", "resolved documents folder"])

    def test_streaming_preserves_output_and_nonzero_exit_without_a_shell(self):
        calls = []
        class Child:
            stdout = io.StringIO("first\nerror\n")
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                self.stdout.close()
            def wait(self):
                return 7
        def spawn(argv, **kwargs):
            calls.append((argv, kwargs))
            return Child()
        lines = []
        argv = self.model.command("status", recipe="a b.json")
        self.assertEqual(gui.run_command(argv, lines.append, popen=spawn), 7)
        self.assertEqual(lines, ["first\n", "error\n"])
        self.assertEqual(calls[0][0], argv)
        self.assertEqual(calls[0][1]["cwd"], str(ROOT))
        self.assertNotIn("shell", calls[0][1])

    def test_missing_or_unknown_widgets_are_not_silently_saved(self):
        for raw in ({}, dict(self.model.saved, unknown="x")):
            with self.assertRaises(ValueError):
                self.model.command("save", raw)


class PathsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "Starfield"
        self.data = self.root / "Fallout 4" / "Data"
        self.docs = self.root / "user" / "Documents" / "My Games" / "Starfield"
        self.tools = self.root / "Program Files" / "Sysinternals"
        for d in (self.game, self.data, self.docs, self.tools):
            d.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"")
        (self.data / "Fallout4.esm").write_bytes(b"")
        (self.tools / "procdump64.exe").write_bytes(b"")
        self.env = {"USERPROFILE": str(self.root / "user"), "ProgramFiles": str(self.root / "Program Files"),
                    "LOCALAPPDATA": str(self.root / "local")}
        # Keep Windows' redirected Documents folder out of these synthetic path-discovery fixtures.
        documents = mock.patch.object(paths, "_documents", return_value=[str(self.docs.parents[1])])
        documents.start()
        self.addCleanup(documents.stop)

    def find(self):
        return {"starfield": str(self.game), "fallout4": str(self.data.parent), "fallout4_depots": []}

    def test_check_names_what_is_wrong(self):
        self.assertEqual(paths.check("starfield", str(self.game)), "")
        self.assertIn("Starfield.exe", paths.check("starfield", str(self.data)))
        self.assertIn("not found", paths.check("starfield", str(self.root / "nope")))
        self.assertEqual(paths.check("fo4_data", f"{self.data};{self.game}"), "")
        self.assertIn("Fallout4.esm", paths.check("fo4_data", str(self.game)))
        self.assertIn("not found", paths.check("fo4_data", f"{self.data};{self.root / 'nope'}"))
        self.assertEqual(paths.check("crash_watch.procdump", str(self.tools / "procdump64.exe")), "")
        self.assertIn("not procdump", paths.check("crash_watch.procdump", str(self.game / "Starfield.exe")))
        self.assertEqual(paths.check("crash_watch.folder", str(self.root / "new dumps")), "")
        # play makes every missing folder, so a fresh %LOCALAPPDATA%\FO4SF\crashdumps is fine (Codex, #481)
        self.assertEqual(paths.check("crash_watch.folder", str(self.root / "a" / "b")), "")
        self.assertIn("is a file", paths.check("crash_watch.folder", str(self.game / "Starfield.exe" / "dumps")))
        self.assertEqual(paths.check("my_games", ""), "not set")

    def test_detect_finds_every_location_without_writing(self):
        before = sorted(p for p in self.root.rglob("*"))
        found = paths.detect(env=self.env, find=self.find, which=lambda _n: None)
        self.assertEqual(paths.check("crash_watch.folder", found["crash_watch.folder"][0]), "")
        self.assertEqual(found["starfield"][0], os.path.normpath(self.game))
        self.assertEqual(found["fo4_data"][0], str(self.data))
        self.assertEqual(found["my_games"][0], os.path.normpath(self.docs))
        self.assertEqual(found["crash_watch.procdump"], (os.path.normpath(self.tools / "procdump64.exe"), "Program Files"))
        self.assertEqual(found["crash_watch.folder"][1], "suggested")
        self.assertEqual(sorted(p for p in self.root.rglob("*")), before)

    def test_detect_reports_nothing_it_cannot_verify(self):
        (self.game / "Starfield.exe").unlink()
        def broken():
            raise OSError("registry unreadable")
        for find in (self.find, broken):
            found = paths.detect(env={}, find=find, which=lambda _n: str(self.game / "not-procdump.exe"))
            self.assertEqual(found["starfield"], ("", ""))
            self.assertEqual(found["crash_watch.procdump"], ("", ""))

    def test_rows_ask_about_found_values_and_keep_good_saved_ones(self):
        found = paths.detect(env=self.env, find=self.find, which=lambda _n: None)
        saved = dict(settings.defaults(), **{"starfield": str(self.game), "my_games": str(self.root / "gone")})
        rows = {r["key"]: r for r in paths.rows(saved, found)}
        self.assertEqual(rows["starfield"]["status"], "saved")
        self.assertEqual(rows["fo4_data"]["status"], "found")
        self.assertIn("is this right?", rows["fo4_data"]["note"])
        # a saved value that no longer works is replaced by what was found, and still has to be confirmed
        self.assertEqual((rows["my_games"]["status"], rows["my_games"]["value"]), ("found", os.path.normpath(self.docs)))
        # a path given on the command line is offered even over a good saved one (Codex, #481)
        other = str(self.root / "Other Starfield")
        rows = {r["key"]: r for r in paths.rows(saved, {"starfield": (other, "command line")}, prefer=["starfield"])}
        self.assertEqual((rows["starfield"]["status"], rows["starfield"]["value"]), ("found", other))
        rows = {r["key"]: r for r in paths.rows(saved, {"starfield": (str(self.game), "command line")},
                                                prefer=["starfield"])}
        self.assertEqual(rows["starfield"]["status"], "saved")
        rows = {r["key"]: r for r in paths.rows(saved, {})}
        self.assertEqual(rows["my_games"]["status"], "problem")
        self.assertEqual(rows["fo4_data"]["status"], "missing")

    def test_needed_follows_the_settings(self):
        values = settings.defaults()
        self.assertEqual(paths.needed(values), ["starfield"])
        values.update({"crash_watch.enabled": True, "papyrus_logging": "on"})
        self.assertEqual(paths.needed(values), ["starfield", "crash_watch.procdump", "crash_watch.folder", "my_games"])


class LocationsCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "launcher.py"), *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_play_without_any_starfield_folder_is_refused_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run_cli("play", "--dry-run", "--settings", os.path.join(d, "s.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no Starfield folder", result.stdout + result.stderr)

    def test_plain_play_refuses_a_saved_starfield_folder_that_moved(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            Path(path).write_text(json.dumps({"starfield": os.path.join(d, "moved")}), encoding="utf-8")
            result = self.run_cli("play", "--dry-run", "--settings", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("saved Starfield folder", result.stdout + result.stderr)
        self.assertIn("folder not found", result.stdout + result.stderr)

    def test_detect_given_every_location_does_not_need_a_readable_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "s.json")
            Path(bad).write_text('{"newer_setting": 1}', encoding="utf-8")
            args = ("detect", "--settings", bad, "--fo4-data", os.path.join(d, "Data"), "--starfield", d)
            full = self.run_cli(*args, "--my-games", d)
            self.assertNotIn("newer_setting", full.stdout + full.stderr)
            part = self.run_cli(*args)
            self.assertIn("settings not read", part.stdout)
            self.assertIn("detect runs without --my-games", part.stdout)

    def test_paths_lists_every_location_and_says_what_play_still_needs(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            result = self.run_cli("paths", "--settings", path)
            self.assertFalse(os.path.exists(path))
        for _key, label, _kind, _what in paths.LOCATIONS:
            self.assertIn(label, result.stdout)
        # no Steam here, so nothing is saved or found for the game folder
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("still needed to play: Starfield game folder", result.stdout)


WINDOW_SCRIPT = r"""
import gc, json, os, sys, tempfile, threading, time
sys.path.insert(0, sys.argv[1])
import tkinter as tk
from fo4sf.launcher import gui, paths
d = tempfile.mkdtemp()
def made(name, file):
    os.makedirs(os.path.join(d, name))
    open(os.path.join(d, name, file), "wb").close()
    return os.path.join(d, name)
detected, typed = made("SteamGame", "Starfield.exe"), made("MyGame", "Starfield.exe")
gate = threading.Event()
def late_detect(**_kw):
    gate.wait(10)
    return {k: ("", "") for k in paths.KEYS} | {"starfield": (detected, "Steam library")}
paths.detect = late_detect
errors = []
tk.Tk.report_callback_exception = lambda self, *a: errors.append(repr(a[1]))
def pump(root, s):
    end = time.time() + s
    while time.time() < end:
        root.update()
        time.sleep(0.02)
def run(root):
    w = next(o for o in gc.get_objects() if type(o).__name__ == "Window")
    pump(root, 0.3)
    entry = w.loc["starfield"]["entry"]
    entry.delete(0, "end")
    entry.insert(0, typed)                      # the player types while detection is still running
    pump(root, 0.2)
    gate.set()
    pump(root, 1.0)
    out = {"after_detect": w.location_value("starfield")}
    w.detect_locations()                        # Detect again
    pump(root, 1.0)
    out["after_redetect"] = w.location_value("starfield")
    data = w.loc["fo4_data"]["entry"]          # the player browses to other Data folders, then checks the install
    data.delete("1.0", "end")
    data.insert("1.0", "Data A\nData B")
    games = w.loc["my_games"]["entry"]
    games.delete(0, "end")
    games.insert(0, "Other My Games")
    ran = []
    gui.run_command = lambda argv, on_line, **_kw: ran.append(argv) or 0
    w.start("detect")
    pump(root, 0.5)
    out["detect_argv"] = ran[0][4:] if ran else w.message.get()
    def refused(_argv, on_line, **_kw):
        on_line("tests: Synthetic missing archive; nothing built\n")
        return 2
    gui.run_command = refused
    w.launch_command("tests-install", [sys.executable, "-I", "-u", sys.argv[2], "tests", "install"])
    pump(root, 0.4)
    out["refusal_footer"] = w.message.get()
    w.show_card(os.path.join(d, "private-owner-marker", "missing kit"))
    out["missing_card"] = w.message.get()
    out["errors"] = errors
    print(json.dumps(out))
    root.destroy()
tk.Tk.mainloop = lambda self, n=0: run(self)
gui.launch(sys.argv[2], os.path.join(d, "settings.json"))
"""


def can_open_a_window():
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:            # no tkinter, or no display (CI): the model tests above still run
        return False


@unittest.skipUnless(can_open_a_window(), "needs tkinter and a display")
class GuiWindowTests(unittest.TestCase):
    def test_a_late_detection_keeps_a_typed_location_in_the_real_window(self):
        result = subprocess.run([sys.executable, "-I", "-c", WINDOW_SCRIPT, str(ROOT / "src"),
                                 str(ROOT / "scripts" / "launcher.py")], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["refusal_footer"], "Synthetic missing archive; nothing built")
        self.assertIn("Owner card is missing", out["missing_card"])
        self.assertNotIn("private-owner-marker", out["missing_card"])
        self.assertTrue(out["after_detect"].endswith("MyGame"), out)
        self.assertTrue(out["after_redetect"].endswith("MyGame"), out)
        # Check installation uses the folders on screen, not the saved ones (Codex, #481)
        argv = out["detect_argv"]
        self.assertEqual(argv[argv.index("--fo4-data"):], ["--fo4-data", "Data A", "--fo4-data", "Data B",
                                                           "--my-games", "Other My Games"], out)
        self.assertTrue(argv[argv.index("--starfield") + 1].endswith("MyGame"), out)

    def test_x5_mod_tools_and_x6_polish_in_the_real_window(self):
        script = r"""
import gc, json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
import tkinter as tk
from fo4sf.launcher import gui, paths
d = tempfile.mkdtemp()
sf = os.path.join(d, "Starfield")
fo4 = os.path.join(d, "FO4Data")
mg = os.path.join(d, "MyGames")
out_dir = os.path.join(d, "alife_out")
git_dir = os.path.join(d, "repo_checkout")
os.makedirs(sf); os.makedirs(fo4); os.makedirs(mg); os.makedirs(os.path.join(git_dir, ".git"))
open(os.path.join(sf, "Starfield.exe"), "wb").close()
open(os.path.join(fo4, "Fallout4.esm"), "wb").close()
settings_file = os.path.join(d, "settings.json")
with open(settings_file, "w", encoding="utf-8") as fp:
    json.dump({"starfield": sf, "fo4_data": fo4, "my_games": mg}, fp)
paths.detect = lambda **_kw: {k: ("", "") for k in paths.KEYS}
errors = []
tk.Tk.report_callback_exception = lambda self, *a: errors.append(repr(a[1]))
def pump(root, s):
    end = time.time() + s
    while time.time() < end:
        root.update()
        time.sleep(0.02)
def run(root):
    w = next(o for o in gc.get_objects() if type(o).__name__ == "Window")
    pump(root, 0.35)
    tabs = [w.notebook.tab(i, "text") for i in range(w.notebook.index("end"))]
    checklist_summary = w.checklist_summary_var.get()
    # Trigger Git-checkout refusal on Mod tools -> banner appears, then Dismiss hides it
    w.notebook.select(w.mod_tools_tab)
    w.alife_out_var.set(os.path.join(git_dir, "out"))
    w.start_alife_step("init")
    pump(root, 0.1)
    banner_shown = bool(w.banner_frame.grid_info())
    banner_title = w.banner_title_var.get()
    banner_body = w.banner_body_var.get()
    init_refused_mark = w.alife_step_widgets["init"]["mark"].cget("text")
    w.clear_error_banner()
    banner_dismissed = not bool(w.banner_frame.grid_info())
    # Run mocked simulate into safe output folder -> updates metrics, table, progress, and Log tab
    captured = []
    def fake_run(argv, on_line, **kw):
        captured.append({"argv": argv, "cwd": kw.get("cwd")})
        for ln in [
            "A-Life offline simulation: Demo (16 nodes, 24 edges, 2 factions)\n",
            "+--------------------+-------+\n",
            "| metric             | value |\n",
            "+--------------------+-------+\n",
            "| squads spawned     |     9 |\n",
            "| offline battles    |     3 |\n",
            "| territory captures |     2 |\n",
            "+--------------------+-------+\n",
            "+-------------+---------+--------+-------------+----------+\n",
            "| faction     | spawned | losses | nodes owned | captures |\n",
            "+-------------+---------+--------+-------------+----------+\n",
            "| uc_security |       5 |      1 |           9 |        1 |\n",
            "| spacers     |       4 |      2 |           7 |        1 |\n",
            "+-------------+---------+--------+-------------+----------+\n",
        ]:
            on_line(ln)
        return 0
    gui.run_command = fake_run
    w.alife_out_var.set(out_dir)
    w.alife_ticks_var.set("35")
    w.alife_seed_var.set("7")
    w.start_alife_step("simulate")
    pump(root, 0.45)
    rows = [w.alife_table.item(item, "values") for item in w.alife_table.get_children()]
    log_text = w.log.get("1.0", "end")
    print(json.dumps({
        "tabs": tabs,
        "checklist_summary": checklist_summary,
        "header_game": w.game.get(),
        "header_watcher": w.watcher.get(),
        "banner_shown": banner_shown,
        "banner_title": banner_title,
        "banner_body": banner_body,
        "banner_dismissed": banner_dismissed,
        "init_refused_mark": init_refused_mark,
        "sim_mark": w.alife_step_widgets["simulate"]["mark"].cget("text"),
        "progress": w.alife_progress_var.get(),
        "metrics": w.alife_metrics_var.get(),
        "rows": rows,
        "captured": captured,
        "log_has_sim": "A-Life offline simulation" in log_text,
        "errors": errors,
    }))
    root.destroy()
tk.Tk.mainloop = lambda self, n=0: run(self)
gui.launch(sys.argv[2], settings_file)
"""
        result = subprocess.run([sys.executable, "-I", "-c", script, str(ROOT / "src"),
                                 str(ROOT / "scripts" / "launcher.py")], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(out["errors"], [])
        self.assertEqual(len(out["tabs"]), 6)
        self.assertIn("♦  Mod tools", out["tabs"])
        self.assertIn("⌂  Locations", out["tabs"])
        self.assertIn("3/3", out["checklist_summary"])
        self.assertIn("Game:", out["header_game"])
        self.assertIn("Watcher:", out["header_watcher"])
        self.assertTrue(out["banner_shown"])
        self.assertIn("Mod tools", out["banner_title"])
        self.assertIn("Git checkout", out["banner_body"])
        self.assertTrue(out["banner_dismissed"])
        self.assertIn("failed", out["init_refused_mark"])
        self.assertIn("passed", out["sim_mark"])
        self.assertEqual(out["progress"], "1/5 steps passed")
        self.assertIn("nodes 16/128", out["metrics"])
        self.assertIn("spawns 9", out["metrics"])
        self.assertIn("battles 3", out["metrics"])
        self.assertIn("captures 2", out["metrics"])
        self.assertEqual(len(out["rows"]), 2)
        self.assertEqual(list(out["rows"][0]), ["uc_security", "5", "1", "9", "1"])
        self.assertEqual(out["captured"][0]["cwd"], str(ROOT))
        self.assertIn("--ticks", out["captured"][0]["argv"])
        self.assertTrue(out["log_has_sim"])

    def test_x8_three_step_workflow_strip_and_cover_preview_in_real_window(self):
        script = r"""
import gc, json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
import tkinter as tk
from fo4sf.launcher import gui, paths, start_cover
d = tempfile.mkdtemp()
sf = os.path.join(d, "Starfield")
fo4 = os.path.join(d, "FO4Data")
mg = os.path.join(d, "MyGames")
sig = os.path.join(d, "ready.json")
os.makedirs(sf); os.makedirs(fo4); os.makedirs(mg)
open(os.path.join(sf, "Starfield.exe"), "wb").close()
open(os.path.join(fo4, "Fallout4.esm"), "wb").close()
settings_file = os.path.join(d, "settings.json")
with open(settings_file, "w", encoding="utf-8") as fp:
    json.dump({"starfield": sf, "fo4_data": fo4, "my_games": mg}, fp)
paths.detect = lambda **_kw: {k: ("", "") for k in paths.KEYS}
errors = []
tk.Tk.report_callback_exception = lambda self, *a: errors.append(repr(a[1]))
def pump(root, s):
    end = time.time() + s
    while time.time() < end:
        root.update()
        time.sleep(0.02)
def run(root):
    w = next(o for o in gc.get_objects() if type(o).__name__ == "Window")
    pump(root, 0.3)
    step_labels = [w.workflow_step_widgets[k]["button"].cget("text") for k, _t in gui.WORKFLOW_STEPS]
    step_details = {k: w.workflow_step_widgets[k]["var"].get() for k, _t in gui.WORKFLOW_STEPS}
    w.workflow_step_widgets["build"]["button"].invoke()
    pump(root, 0.05)
    selected_after_build = w.notebook.tab(w.notebook.select(), "text")
    w.workflow_step_widgets["locate"]["button"].invoke()
    pump(root, 0.05)
    selected_after_locate = w.notebook.tab(w.notebook.select(), "text")
    cover = w.open_start_cover(for_play=False, signal_path=sig, fullscreen=False)
    pump(root, 0.1)
    cover_opened = w.cover_window is not None
    start_cover.write_fake_ready_signal(sig, stage="stage20")
    pump(root, 0.4)
    cover_closed = w.cover_window is None
    print(json.dumps({
        "step_labels": step_labels,
        "step_details": step_details,
        "start_cover_default": bool(w.vars["start_cover"].get()),
        "selected_after_build": selected_after_build,
        "selected_after_locate": selected_after_locate,
        "cover_opened": cover_opened,
        "cover_closed": cover_closed,
        "footer_msg": w.message.get(),
        "errors": errors,
    }))
    root.destroy()
tk.Tk.mainloop = lambda self, n=0: run(self)
gui.launch(sys.argv[2], settings_file)
"""
        result = subprocess.run([sys.executable, "-I", "-c", script, str(ROOT / "src"),
                                 str(ROOT / "scripts" / "launcher.py")], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["step_labels"], ["1. Locate", "2. Build or Update", "3. Play"])
        self.assertIn("3/3", out["step_details"]["locate"])
        self.assertFalse(out["start_cover_default"])
        self.assertIn("Status", out["selected_after_build"])
        self.assertIn("Locations", out["selected_after_locate"])
        self.assertTrue(out["cover_opened"])
        self.assertTrue(out["cover_closed"])
        self.assertIn("Start cover closed (ready)", out["footer_msg"])


class TestCommandFeedback(unittest.TestCase):
    def test_refused_test_keeps_the_reason_in_the_footer_after_exit(self):
        feedback = gui.CommandFeedback("tests-install")
        feedback.observe("tests: The prebuilt test archive is missing; nothing built\n")
        self.assertEqual(feedback.finished(2), "The prebuilt test archive is missing; nothing built")

    def test_register_success_and_other_actions_keep_normal_completion(self):
        for action in ("tests-register", "save", "detect"):
            feedback = gui.CommandFeedback(action)
            feedback.observe("tests: earlier output is not a failure\n")
            self.assertEqual(feedback.finished(0), f"{action} finished (exit 0)")

    def test_unrecognized_child_error_points_to_log_without_reusing_an_old_reason(self):
        previous = gui.CommandFeedback("tests-install")
        previous.observe("tests: missing archive\n")
        current = gui.CommandFeedback("tests-remove")
        current.observe("a child installer wrote a diagnostic\n")
        self.assertEqual(current.finished(1), "Test kit command stopped (exit 1); open Log for details")
        self.assertEqual(previous.finished(2), "missing archive")

    def test_non_test_action_does_not_treat_output_as_a_test_refusal(self):
        feedback = gui.CommandFeedback("status")
        feedback.observe("tests: a line in a build report\n")
        self.assertEqual(feedback.finished(2), "status finished (exit 2)")


class GuiEntryTests(unittest.TestCase):
    def test_opening_without_tkinter_gives_a_clear_error(self):
        import builtins
        original = builtins.__import__
        def no_tk(name, *args, **kwargs):
            if name == "tkinter" or name.startswith("tkinter."):
                raise ImportError("not installed")
            return original(name, *args, **kwargs)
        with mock.patch("builtins.__import__", side_effect=no_tk):
            with self.assertRaisesRegex(ValueError, "needs Python's tkinter"):
                gui.launch("launcher.py", "not-read.json")

    def test_import_and_cli_help_need_neither_tkinter_nor_a_display(self):
        code = """
import builtins,runpy,sys
sys.path.insert(0,sys.argv[1])
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name=='tkinter' or name.startswith('tkinter.'):
        raise AssertionError('headless import tried tkinter')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
import fo4sf.launcher.gui
sys.argv=[sys.argv[2],'gui','--help']
runpy.run_path(sys.argv[0],run_name='__main__')
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(ROOT / "src"),
                                 str(ROOT / "scripts" / "launcher.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--settings", result.stdout)
        self.assertIn("--recipe", result.stdout)


class X6LauncherPolishHeadlessTests(unittest.TestCase):
    def test_palettes_share_exact_keys_and_preserve_dark_terminal_colors(self):
        self.assertEqual(set(gui.DARK_PALETTE), set(gui.LIGHT_PALETTE))
        self.assertEqual(gui.PALETTE, gui.DARK_PALETTE)
        self.assertEqual(gui.DARK_PALETTE["bg"], "#0d1117")
        self.assertEqual(gui.DARK_PALETTE["panel"], "#161b22")
        self.assertEqual(gui.DARK_PALETTE["accent"], "#58a6ff")
        self.assertEqual(gui.LIGHT_PALETTE["bg"], "#ffffff")
        self.assertEqual(gui.LIGHT_PALETTE["fg"], "#1f2328")

    def test_detect_windows_light_theme_follows_registry_and_defaults_safely(self):
        seen = []
        def reader_light(subkey, value_name):
            seen.append((subkey, value_name))
            return (1, 4)

        self.assertTrue(gui.detect_windows_light_theme(reg_reader=reader_light, windows=True))
        self.assertEqual(seen[-1], (gui.PERSONALIZE_KEY, gui.LIGHT_THEME_VALUE))
        self.assertEqual(gui.select_palette(reg_reader=reader_light), gui.LIGHT_PALETTE)

        for dark_val in (0, (0, 4), "0", None, "", "not-an-int"):
            self.assertFalse(gui.detect_windows_light_theme(reg_reader=lambda _k, _v, v=dark_val: v, windows=True))
            self.assertEqual(gui.select_palette(reg_reader=lambda _k, _v, v=dark_val: v), gui.DARK_PALETTE)

        def missing_key(_subkey, _value_name):
            raise FileNotFoundError("Personalize key missing")

        self.assertFalse(gui.detect_windows_light_theme(reg_reader=missing_key, windows=True))
        self.assertFalse(gui.detect_windows_light_theme(reg_reader=reader_light, windows=False))
        self.assertFalse(gui.detect_windows_light_theme(windows=False))

    def test_apply_theme_configures_dark_and_light_styles_and_hit_targets_headlessly(self):
        class FakeRoot:
            def __init__(self):
                self.cfg = {}
                self.options = {}
            def configure(self, **kw):
                self.cfg.update(kw)
            def option_add(self, k, v):
                self.options[k] = v

        class FakeStyle:
            def __init__(self, _root):
                self.theme = None
                self.configured = {}
                self.mapped = {}
            def theme_use(self, name):
                self.theme = name
            def configure(self, name, **kw):
                self.configured.setdefault(name, {}).update(kw)
            def map(self, name, **kw):
                self.mapped.setdefault(name, {}).update(kw)

        class FakeTtk:
            def __init__(self):
                self.last_style = None
            def Style(self, root):
                self.last_style = FakeStyle(root)
                return self.last_style

        class FakeFont:
            @staticmethod
            def families(_root):
                return ["Consolas", "Arial"]

        for light_flag, expected_palette in ((False, gui.DARK_PALETTE), (True, gui.LIGHT_PALETTE)):
            root = FakeRoot()
            fake_ttk = FakeTtk()
            text_cfg = gui.apply_theme(root, fake_ttk, FakeFont, light=light_flag)
            st = fake_ttk.last_style
            self.assertEqual(root.cfg["background"], expected_palette["bg"])
            self.assertEqual(text_cfg["background"], expected_palette["field"])
            self.assertEqual(text_cfg["foreground"], expected_palette["fg"])
            self.assertEqual(text_cfg["font"], ("Consolas", 10))
            self.assertEqual(st.configured["TButton"]["padding"], (14, 7))
            self.assertEqual(st.configured["TNotebook.Tab"]["padding"], (16, 8))
            self.assertIn("Banner.TFrame", st.configured)
            self.assertIn("Treeview", st.configured)
            self.assertIn("Horizontal.TProgressbar", st.configured)
            for tone in ("ok", "warn", "bad", "muted"):
                self.assertEqual(st.configured[f"Panel.{tone}.TLabel"]["foreground"], expected_palette[tone])

    def test_tab_marks_cover_every_tab_cleanly(self):
        for name in ("Play", "Locations", "Status", "Settings", "Tests", "Mod tools", "Log"):
            self.assertIn(name, gui.TAB_MARKS)
            rendered = gui.tab_label(name)
            self.assertTrue(rendered.endswith(name))
            self.assertGreater(len(rendered), len(name))

    def test_header_state_formats_game_watcher_and_recovery_tones(self):
        with tempfile.TemporaryDirectory() as tmp:
            procdump = Path(tmp) / "procdump64.exe"
            procdump.write_bytes(b"")
            dumps = Path(tmp) / "dumps"
            base = settings.defaults()

            s_checking = gui.format_header_state(base, pids=None, recovery_reason="")
            self.assertIn("Game: checking", s_checking["game_text"])
            self.assertEqual(s_checking["game_tone"], "warn")
            self.assertIn("Watcher: off", s_checking["watcher_text"])
            self.assertEqual(s_checking["watcher_tone"], "muted")

            s_closed = gui.format_header_state(base, pids=[], recovery_reason="")
            self.assertIn("Game: closed", s_closed["game_text"])
            self.assertEqual(s_closed["game_tone"], "ok")

            s_running = gui.format_header_state(base, pids=[101, 202], recovery_reason="")
            self.assertIn("Game: running (PID 101, 202)", s_running["game_text"])
            self.assertEqual(s_running["game_tone"], "ok")

            s_err = gui.format_header_state(base, pids=None, process_error="query failed", recovery_reason="")
            self.assertEqual(s_err["game_tone"], "bad")

            armed = dict(base, **{
                "crash_watch.enabled": True,
                "crash_watch.dump": "full",
                "crash_watch.procdump": str(procdump),
                "crash_watch.folder": str(dumps),
            })
            s_armed = gui.format_header_state(armed, pids=[], recovery_reason="")
            self.assertIn("Watcher: armed (full)", s_armed["watcher_text"])
            self.assertEqual(s_armed["watcher_tone"], "ok")

            s_unsaved = gui.format_header_state(base, pids=[], raw=armed, recovery_reason="")
            self.assertIn("unsaved", s_unsaved["watcher_text"])
            self.assertEqual(s_unsaved["watcher_tone"], "warn")

            broken_watcher = dict(armed, **{"crash_watch.procdump": ""})
            s_need_setup = gui.format_header_state(broken_watcher, pids=[], recovery_reason="")
            self.assertEqual(s_need_setup["watcher_tone"], "bad")

            s_rec = gui.format_header_state(base, pids=[], recovery_reason="Installation incomplete (port)")
            self.assertIn("Recovery: needed", s_rec["watcher_text"])
            self.assertEqual(s_rec["watcher_tone"], "bad")

    def test_first_run_checklist_tracks_fo4_data_starfield_and_my_games(self):
        c0 = gui.first_run_checklist(settings.defaults(), {"fo4_data": "missing", "starfield": "missing", "my_games": "missing"})
        self.assertEqual((c0["confirmed"], c0["total"], c0["ready"], c0["tone"]), (0, 3, False, "bad"))
        self.assertEqual(c0["remaining"], ["Fallout 4 Data", "Starfield", "My Games"])

        c1 = gui.first_run_checklist(settings.defaults(), {"fo4_data": "found", "starfield": "saved", "my_games": "edited"})
        self.assertEqual((c1["confirmed"], c1["ready"], c1["tone"]), (1, False, "warn"))
        self.assertEqual(c1["remaining"], ["Fallout 4 Data", "My Games"])
        self.assertIn("Confirm locations", c1["summary"])

        c3 = gui.first_run_checklist(settings.defaults(), {"fo4_data": "saved", "starfield": "saved", "my_games": "saved"})
        self.assertEqual((c3["confirmed"], c3["ready"], c3["tone"], c3["remaining"]), (3, True, "ok", []))

    def test_format_error_banner_strips_tracebacks_and_adds_hints(self):
        self.assertEqual(gui.format_error_banner("", exit_code=0), {"title": "", "message": "", "hint": ""})

        raw_tb = (
            "Traceback (most recent call last):\n"
            '  File "scripts/alife/build_alife_mod.py", line 412, in main\n'
            "    run_package()\n"
            "ValueError: confirm the Starfield folder on the Locations tab first\n"
        )
        b1 = gui.format_error_banner(raw_tb, action="alife-package", exit_code=1)
        self.assertEqual(b1["title"], "Mod tools — Package stopped")
        self.assertNotIn("Traceback", b1["message"])
        self.assertNotIn("line 412", b1["message"])
        self.assertIn("Starfield folder", b1["message"])
        self.assertIn("Locations tab", b1["hint"])

        b2 = gui.format_error_banner(
            "Output folder cannot be inside a Git checkout; choose a folder outside any repository.",
            action="alife-init",
        )
        self.assertIn("Mod tools — Init", b2["title"])
        self.assertIn("outside Git", b2["hint"])

    def test_cross_os_path_dirname_and_run_command_cwd_under_posix(self):
        drv = "D:"
        with mock.patch("os.path.dirname", side_effect=posixpath.dirname), \
                mock.patch("os.path.basename", side_effect=posixpath.basename):
            self.assertEqual(gui.path_dirname(drv + "\\Work\\repo\\scripts\\launcher.py"),
                             drv + "\\Work\\repo\\scripts")
            self.assertEqual(gui.path_dirname(gui.path_dirname(drv + "\\Work\\repo\\scripts\\launcher.py")),
                             drv + "\\Work\\repo")
            self.assertEqual(gui.path_dirname("/opt/work/repo/scripts/launcher.py"), "/opt/work/repo/scripts")
            self.assertEqual(gui.path_dirname(gui.path_dirname("/opt/work/repo/scripts/launcher.py")), "/opt/work/repo")
            self.assertEqual(gui.path_dirname(drv + "\\Work/repo\\scripts/launcher.py"), drv + "\\Work/repo\\scripts")

            calls = []
            class Child:
                stdout = io.StringIO("ok\n")
                def __enter__(self):
                    return self
                def __exit__(self, *_a):
                    self.stdout.close()
                def wait(self):
                    return 0
            def spawn(argv, **kwargs):
                calls.append((argv, kwargs))
                return Child()

            win_argv = [sys.executable, "-I", "-u", drv + "\\Work\\repo\\scripts\\launcher.py", "status", "r.json"]
            self.assertEqual(gui.run_command(win_argv, lambda _ln: None, popen=spawn), 0)
            self.assertEqual(calls[-1][1]["cwd"], drv + "\\Work\\repo")

            b_win = gui.format_error_banner(f"missing {drv}\\Games\\Starfield\\Starfield.exe", action="play")
            b_pos = gui.format_error_banner("missing /opt/games/Starfield/Starfield.exe", action="play")
            self.assertIn("Locations tab", b_win["hint"])
            self.assertIn("Locations tab", b_pos["hint"])


class X5ModToolsTabHeadlessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.settings_path = self.root / "settings.json"
        self.launcher_path = ROOT / "scripts" / "launcher.py"
        self.game_dir = self.root / "Starfield"
        (self.game_dir / "Data").mkdir(parents=True)
        (self.game_dir / "Starfield.exe").write_bytes(b"")
        self.out_dir = self.root / "alife build space"
        self.settings_path.write_text(json.dumps({"starfield": str(self.game_dir)}), encoding="utf-8")
        self.alife_model = alife_tools.ModToolsModel(str(self.launcher_path), str(self.settings_path))
        self.session = gui.ModToolsSession(self.alife_model)

    def test_run_command_supports_explicit_cwd_without_shell(self):
        calls = []
        class Child:
            stdout = io.StringIO("ok\n")
            def __enter__(self):
                return self
            def __exit__(self, *_a):
                self.stdout.close()
            def wait(self):
                return 0
        def spawn(argv, **kwargs):
            calls.append((argv, kwargs))
            return Child()

        argv = self.alife_model.command("validate", output_dir=str(self.out_dir))
        lines = []
        rc = gui.run_command(argv, lines.append, popen=spawn, cwd=self.alife_model.repo_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(lines, ["ok\n"])
        self.assertEqual(calls[0][0], argv)
        self.assertEqual(calls[0][1]["cwd"], str(ROOT))
        self.assertNotIn("shell", calls[0][1])

    def test_mod_tools_session_worker_transitions_key_numbers_and_table_rows(self):
        self.assertEqual(self.session.progress(), (0, 5))
        self.assertEqual(self.session.key_numbers()["nodes"], "nodes —/128")
        self.assertTrue(all(r["status"] == "not_run" and r["progress_pct"] == 0 for r in self.session.step_rows()))

        outputs = {
            "init": ["Initialized A-Life config (16 nodes)\n"],
            "validate": [
                "+-------+-------------------+\n",
                "| graph | value             |\n",
                "+-------+-------------------+\n",
                "| nodes | 16/128 (112 free) |\n",
                "+-------+-------------------+\n",
                "validate: ok\n",
            ],
            "simulate": [
                "A-Life offline simulation: New Atlantis (16 nodes, 24 edges, 3 factions)\n",
                "+--------------------+-------+\n",
                "| metric             | value |\n",
                "+--------------------+-------+\n",
                "| squads spawned     |    14 |\n",
                "| offline battles    |     5 |\n",
                "| territory captures |     3 |\n",
                "+--------------------+-------+\n",
                "+-------------+---------+--------+-------------+----------+\n",
                "| faction     | spawned | losses | nodes owned | captures |\n",
                "+-------------+---------+--------+-------------+----------+\n",
                "| uc_security |       6 |      1 |           7 |        1 |\n",
                "| spacers     |       5 |      3 |           5 |        1 |\n",
                "| ecliptic    |       3 |      1 |           4 |        1 |\n",
                "+-------------+---------+--------+-------------+----------+\n",
            ],
            "package": ["Packaged Data/StarfieldALife.esm\n"],
            "verify-dist": ["verify-dist: ok\n"],
        }
        calls = []
        observed_running = []
        log_stream = []

        def make_popen(step_name):
            def spawn(argv, **kwargs):
                calls.append((step_name, argv, kwargs))
                row_map = {r["step"]: r for r in self.session.step_rows()}
                observed_running.append((row_map[step_name]["status"], row_map[step_name]["progress_pct"]))
                class Child:
                    stdout = io.StringIO("".join(outputs[step_name]))
                    def __enter__(self):
                        return self
                    def __exit__(self, *_a):
                        self.stdout.close()
                    def wait(self):
                        return 0
                return Child()
            return spawn

        for step in alife_tools.STEPS:
            kw = {"output_dir": str(self.out_dir)}
            if step == "init":
                kw.update({"template": "vanilla", "force": True})
            elif step == "simulate":
                kw.update({"ticks": 50, "seed": 42})
            elif step == "package":
                kw.update({"pack_ba2": True})
            rc = self.session.run_step(step, on_line=log_stream.append, popen=make_popen(step), **kw)
            self.assertEqual(rc, 0)

        self.assertEqual(observed_running, [("running", 50)] * 5)
        self.assertEqual(self.session.progress(), (5, 5))
        self.assertEqual(self.session.progress_text(), "5/5 steps passed")
        self.assertTrue(all(r["status"] == "passed" and r["progress_pct"] == 100 for r in self.session.step_rows()))

        nums = self.session.key_numbers()
        self.assertEqual(nums["nodes"], "nodes 16/128")
        self.assertEqual(nums["spawns"], "spawns 14")
        self.assertEqual(nums["battles"], "battles 5")
        self.assertEqual(nums["captures"], "captures 3")
        self.assertEqual(self.session.table_columns, ["faction", "spawned", "losses", "nodes owned", "captures"])
        self.assertEqual(len(self.session.table_rows), 3)
        self.assertEqual(self.session.table_rows[0], ["uc_security", "6", "1", "7", "1"])
        self.assertEqual(self.session.last_error["message"], "")

        for _step, argv, kwargs in calls:
            self.assertEqual(argv[:3], [sys.executable, "-I", "-u"])
            self.assertEqual(kwargs["cwd"], str(ROOT))
            self.assertNotIn("shell", kwargs)
        pkg_argv = dict((s, a) for s, a, _k in calls)["package"]
        self.assertIn("--pack-ba2", pkg_argv)
        self.assertIn(str(self.game_dir.resolve()), pkg_argv)
        self.assertTrue(any("verify-dist: ok" in ln for ln in log_stream))

    def test_mod_tools_session_refuses_git_and_game_folders_and_surfaces_failed_banner(self):
        git_checkout = self.root / "some_repo"
        (git_checkout / ".git").mkdir(parents=True)
        spawned = []
        def never_spawn(*_a, **_kw):
            spawned.append(True)
            raise AssertionError("popen must not run on refused output_dir")

        with self.assertRaisesRegex(ValueError, "Git checkout"):
            self.session.run_step("init", popen=never_spawn, output_dir=str(git_checkout / "out"))
        self.assertEqual(spawned, [])
        self.assertEqual(self.session.statuses["init"], "failed")
        self.assertIn("Git checkout", self.session.last_error["message"])

        with self.assertRaisesRegex(ValueError, "game"):
            self.session.run_step("package", popen=never_spawn, output_dir=str(self.game_dir / "out"))
        self.assertEqual(spawned, [])
        self.assertEqual(self.session.statuses["package"], "failed")
        self.assertIn("game", self.session.last_error["message"])

        # Non-zero child exit with traceback sets failed state and strips raw stack frames from banner
        def failing_popen(_argv, **_kw):
            class Child:
                stdout = io.StringIO(
                    "Traceback (most recent call last):\n"
                    '  File "scripts/alife/build_alife_mod.py", line 88, in main\n'
                    "RuntimeError: synthetic broken graph\n"
                )
                def __enter__(self):
                    return self
                def __exit__(self, *_a):
                    self.stdout.close()
                def wait(self):
                    return 2
            return Child()

        rc = self.session.run_step("validate", popen=failing_popen, output_dir=str(self.out_dir))
        self.assertEqual(rc, 2)
        self.assertEqual(self.session.statuses["validate"], "failed")
        self.assertNotIn("Traceback", self.session.last_error["message"])
        self.assertIn("synthetic broken graph", self.session.last_error["message"])

    def test_open_output_dir_checks_folder_exists_and_uses_startfile_on_windows(self):
        opened = []
        ok, msg = self.session.open_output_dir(str(self.out_dir), opener=opened.append, windows=True)
        self.assertFalse(ok)
        self.assertIn("Init", msg)
        self.assertEqual(opened, [])

        self.out_dir.mkdir()
        ok_nonwin, msg_nonwin = self.session.open_output_dir(str(self.out_dir), windows=False)
        self.assertFalse(ok_nonwin)
        self.assertIn("Windows", msg_nonwin)

        with mock.patch.object(os, "startfile", side_effect=opened.append, create=True):
            ok_win, resolved = self.session.open_output_dir(str(self.out_dir), windows=True)
        self.assertTrue(ok_win)
        self.assertEqual(opened, [str(self.out_dir.resolve())])
        self.assertEqual(resolved, str(self.out_dir.resolve()))


if __name__ == "__main__":
    unittest.main()
