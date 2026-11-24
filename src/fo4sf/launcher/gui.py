"""Optional tkinter front end to launcher.py. Importing this module needs no display or tkinter.

SettingsModel and ModToolsSession are headless. Commands are argv lists for the existing CLIs; no build, install,
settings validation, game-start or crash-watch implementation lives here. Tk and OS folder opening are used only after
opening the UI.
"""
import os
import queue
import re
import subprocess
import sys
import threading
import uuid

from . import alife_tools, launch_choices, paths, recovery, settings, start_cover, test_kits


def controls():
    """The Settings tab's widgets come from the same specification as `settings --show`; the file locations are on
    the Locations tab instead (paths.LOCATIONS)."""
    return [{"key": key, "label": settings.LABELS[key], "default": default, "cost": cost,
             "kind": "bool" if kind is bool else "choice" if isinstance(kind, tuple) else "text",
             "choices": kind if isinstance(kind, tuple) else ()}
            for key, default, kind, cost in settings.SPEC if key not in paths.KEYS]


class SettingsModel:
    def __init__(self, launcher, path):
        self.launcher = os.path.abspath(launcher)
        self.path = os.path.abspath(path)
        self.reload()

    def reload(self):
        self.saved = settings.load(self.path)

    def values(self, raw):
        if set(raw) != set(settings.KEYS):
            raise ValueError("The settings fields do not match the launcher's settings specification")
        return {key: settings.coerce(key, raw[key]) for key in settings.KEYS}

    def command(self, action, raw=None, *, recipe="", overrides=(), fo4_data=(), starfield="", my_games="",
                pids=None, windows=None):
        argv = [sys.executable, "-I", "-u", self.launcher]
        if action == "save":
            values = self.values(raw)
            pairs = [f"{key}={str(value).lower() if isinstance(value, bool) else value}"
                     for key, value in values.items() if value != self.saved[key]]
            # Do not even open a file for writing on an unchanged Save (including a missing settings file).
            if not pairs:
                return None
            return argv + ["settings", "--settings", self.path] + [a for p in pairs for a in ("--set", p)]
        if action == "status":
            if not recipe:
                raise ValueError("Choose a build recipe first")
            return argv + ["status", recipe] + [a for p in overrides for a in ("--set", p)]
        if action == "detect":
            fo4_data = fo4_data or paths.split_dirs(self.saved["fo4_data"])
            starfield = starfield or self.saved["starfield"]
            if not fo4_data or not starfield:
                raise ValueError("Confirm the Fallout 4 Data and Starfield folders on the Locations tab first")
            # this window's settings file, never the default one: my_games falls back to it (Codex, #481)
            argv += ["detect", "--settings", self.path, "--starfield", starfield]
            argv += [a for path in fo4_data for a in ("--fo4-data", path)]
            my_games = my_games or self.saved["my_games"]       # the folder on screen first (Codex, #481)
            if my_games:
                argv += ["--my-games", my_games]
            return argv  # no --report or other output argument: the status panes are read-only
        if action == "update-check":
            return argv + ["update", "--check"]                 # fetches; changes nothing
        if action == "update":
            return argv + ["update"]                            # a fast-forward of a clean main only (selfupdate.py)
        if action == "recover-install":
            if pids is None or pids:
                raise ValueError("Close Starfield and wait for the process check before recovery")
            if self.values(raw) != self.saved or settings.load(self.path) != self.saved:
                raise ValueError("Save or reload the settings and locations before recovery")
            folder = self.saved["instance"] or starfield or self.saved["starfield"]
            if not folder:
                raise ValueError("Confirm the Starfield folder before recovery")
            return argv + ["recover-install", "--settings", self.path, "--starfield", folder, "--apply"]
        if action == "play":
            starfield = starfield or (raw or self.saved).get("starfield", "")
            reason = self.play_reason(raw, starfield, pids, windows=windows)
            if reason:
                raise ValueError(reason)
            try:
                current = settings.load(self.path)
            except OSError as e:
                raise ValueError(f"Cannot read saved settings: {e}") from None
            if current != self.saved:
                raise ValueError("Settings changed outside this window; reload settings before playing")
            folder = current.get("instance")               # the FO4SF game folder: play starts that one
            return argv + ["play", "--settings", self.path, "--starfield", folder or starfield]
        raise ValueError(f"Unknown window action {action!r}")

    def kit_command(self, action, raw, key, pids, *, stage="", windows=None):
        if key not in test_kits.BY_KEY or action not in ("register", "install", "remove"):
            raise ValueError("Unknown test kit or action")
        if self.values(raw) != self.saved or settings.load(self.path) != self.saved:
            raise ValueError("Save or reload settings and locations before changing a test kit")
        folder = self.saved["instance"] or self.saved["starfield"]
        if not folder:
            raise ValueError("Confirm the game folder on the Locations tab")
        if action != "register":
            if not (os.name == "nt" if windows is None else windows):
                raise ValueError("Installing and removing test kits is available on Windows")
            if pids is None or pids:
                raise ValueError("Close Starfield and wait for the process check before changing test kits")
            reason = recovery.play_reason(folder)
            if reason:
                raise ValueError(reason)
        argv = [sys.executable, "-I", "-u", self.launcher, "tests", action,
                "--kit", key, "--settings", self.path, "--starfield", folder]
        if action == "register":
            if not stage:
                raise ValueError("Choose a staged test-kit folder")
            argv += ["--stage", stage]
        return argv

    def play_reason(self, raw, starfield, pids, *, windows=None):
        if windows is None:
            windows = os.name == "nt"
        if not windows:
            return "Playing is available on Windows"
        if pids is None:
            return "Checking whether Starfield is running"
        if pids:
            return "Starfield is already running (PID " + ", ".join(map(str, pids)) + ")"
        try:
            values = self.values(raw)
        except ValueError as e:
            return str(e)
        problems = settings.problems(values)
        if problems:
            return "; ".join(problems)
        changed = {k for k in settings.KEYS if values[k] != self.saved[k]}
        if changed and changed <= set(paths.KEYS):
            return "Confirm the locations before playing (Locations tab)"
        if changed:
            return "Save the changed settings before playing"
        if not (starfield or values["starfield"]):
            return "Choose the Starfield folder first (Locations tab)"
        # a saved location can stop working (the game moved): Play waits until it is fixed (Codex, #481)
        for key in paths.needed(values):
            problem = paths.check(key, starfield or values[key] if key == "starfield" else values[key])
            if problem:
                return f"{settings.LABELS[key]}: {problem} (Locations tab)"
        return recovery.play_reason(values["instance"] or starfield or values["starfield"])

    def part(self, raw, part="all"):
        """raw with the other half put back to the saved values: "settings" keeps the saved locations, so Save
        settings never saves a found path the player has not confirmed; "locations" keeps the saved settings (Codex,
        #481)."""
        if part == "all":
            return dict(raw)
        if part not in ("settings", "locations"):
            raise ValueError(f"Unknown part {part!r}")
        keep = [k for k in raw if (k in paths.KEYS) == (part == "settings")]
        return dict(raw, **{k: self.saved[k] for k in keep if k in self.saved})

    def locations(self, found, prefer=(), dirty=()):
        """Rows for the Locations tab: the saved value, or what was found and waits for the player's yes. dirty are
        locations the player typed or browsed and has not saved: a late detection never overwrites them (Codex,
        #481)."""
        return [r for r in paths.rows(self.saved, found, prefer) if r["key"] not in dirty]


REPORT_ACTIONS = ("status", "detect", "update-check", "update", "recover-install")

_TRACEBACK_HEADER = "Traceback (most recent call last):"
_TRACEBACK_FRAME_RE = re.compile(r'^\s*File\s+".+",\s+line\s+\d+')
_ERROR_PREFIX_RE = re.compile(
    r"^(?:(?:launcher\.py|build_alife_mod\.py)\s*:\s*)?(?:error|fatal|valueerror|runtimeerror|oserror)\s*:\s*",
    re.IGNORECASE,
)

ACTION_TITLES = {
    "play": "Play could not start",
    "save": "Settings could not be saved",
    "locations": "Locations not saved",
    "detect": "Installation check failed",
    "status": "Build status check failed",
    "update-check": "Update check failed",
    "update": "Launcher update failed",
    "recover-install": "Install recovery stopped",
    "process": "Game process check failed",
    "card": "Owner card unavailable",
    "logs": "Dump folder unavailable",
    "alife-open": "Output folder unavailable",
}


def _action_title(action):
    if action in ACTION_TITLES:
        return ACTION_TITLES[action]
    if action.startswith("tests-"):
        sub = action.split("-", 1)[1]
        return f"Test kit {sub} stopped"
    if action.startswith("alife-"):
        step = action.split("-", 1)[1]
        label = alife_tools.STEP_LABELS.get(step, step.capitalize())
        return f"Mod tools — {label} stopped"
    if action:
        return f"{action.replace('-', ' ').capitalize()} failed"
    return "Action could not complete"


def format_error_banner(error, *, action="", exit_code=None):
    """Turn a raw exception, CLI refusal, or exit status into a clean, traceback-free banner dict."""
    raw = str(error or "")
    lines = [ln.rstrip("\r") for ln in raw.splitlines()]
    in_tb = False
    chosen = ""
    clean_lines = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s == _TRACEBACK_HEADER:
            in_tb = True
            continue
        if in_tb:
            if ln.startswith("  ") or _TRACEBACK_FRAME_RE.match(ln):
                continue
            chosen = s
            in_tb = False
            continue
        clean_lines.append(s)

    if not chosen and clean_lines:
        # Prefer explicit error/refusal/FAIL lines over generic progress output.
        for candidate in reversed(clean_lines):
            low = candidate.lower()
            if ("refused" in low or low.startswith("error:") or low.startswith("fail ")
                    or "error:" in low or "cannot " in low or "not found" in low):
                chosen = candidate
                break
        if not chosen:
            chosen = clean_lines[-1]

    if not chosen and (exit_code is None or exit_code == 0):
        return {"title": "", "message": "", "hint": ""}

    if not chosen:
        chosen = f"The command exited with code {exit_code}."
    else:
        chosen = _ERROR_PREFIX_RE.sub("", chosen).strip()
        if chosen.startswith("PermissionError:"):
            chosen = "Access was denied while reading or writing a file or folder."
        elif len(chosen) > 260:
            chosen = chosen[:257].rstrip() + "..."
        if chosen and chosen[0].islower():
            chosen = chosen[0].upper() + chosen[1:]

    low_msg = chosen.lower()
    if "locations tab" in low_msg or "starfield.exe" in low_msg or "fallout4.esm" in low_msg:
        hint = "Review folder paths on the Locations tab and press Confirm locations."
    elif "git checkout" in low_msg or "repository" in low_msg or "game installation" in low_msg:
        hint = "Choose a scratch or workspace folder outside Git and outside the Starfield folder."
    elif "log tab" in low_msg or "open log" in low_msg:
        hint = "Full raw command output is preserved on the Log tab."
    elif exit_code not in (None, 0):
        hint = f"Exit code {exit_code} — open the Log tab for full command output."
    else:
        hint = ""

    return {
        "title": _action_title(action),
        "message": chosen,
        "hint": hint,
    }


class CommandFeedback:
    """Keep the Tests CLI's readable refusal visible after its process exits, and capture clean error context."""
    def __init__(self, action):
        self.action = action
        self.refusal = ""
        self._lines = []

    def observe(self, line):
        if self.action.startswith("tests-") and line.startswith("tests: "):
            self.refusal = line[len("tests: "):].strip()
        if line:
            self._lines.append(line)
            if len(self._lines) > 60:
                self._lines = self._lines[-60:]

    def finished(self, code):
        if self.action.startswith("tests-") and code:
            return self.refusal or f"Test kit command stopped (exit {code}); open Log for details"
        return f"{self.action} finished (exit {code})"

    def error_detail(self, code):
        if not code:
            return ""
        if self.refusal:
            return self.refusal
        return "".join(self._lines)


def path_dirname(path):
    """Cross-OS parent directory splitting on both / and \\ on every OS."""
    s = str(path or "").rstrip("\\/")
    if not s:
        return ""
    idx = max(s.rfind("/"), s.rfind("\\"))
    if idx < 0:
        if len(s) >= 2 and s[0].isascii() and s[0].isalpha() and s[1] == ":":
            return s[:2]
        return ""
    head = s[:idx]
    if not head:
        return s[0]
    if len(head) == 2 and head[0].isascii() and head[0].isalpha() and head[1] == ":":
        return head + s[idx]
    return head


def run_command(argv, on_line, *, popen=subprocess.Popen, cwd=None):
    """Stream a single existing CLI command; the UI calls this on a worker, never on the Tk thread."""
    repo = path_dirname(path_dirname(argv[3])) if cwd is None else cwd
    with popen(argv, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
               text=True, errors="replace", bufsize=1) as proc:
        for line in proc.stdout:
            on_line(line)
        return proc.wait()


# A dark terminal look (owner, 2026-10-22: "more code terminal but less 90s"): one monospace face, flat panels,
# a single accent for the next thing to press, and green/amber/red only for state.
DARK_PALETTE = {
    "bg": "#0d1117", "panel": "#161b22", "field": "#010409", "border": "#30363d", "fg": "#e6edf3",
    "muted": "#8b949e", "accent": "#58a6ff", "ok": "#3fb950", "warn": "#d29922", "bad": "#f85149",
}
LIGHT_PALETTE = {
    "bg": "#ffffff", "panel": "#f6f8fa", "field": "#ffffff", "border": "#d0d7de", "fg": "#1f2328",
    "muted": "#57606a", "accent": "#0969da", "ok": "#1a7f37", "warn": "#9a6700", "bad": "#cf222e",
}
PALETTE = DARK_PALETTE

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
LIGHT_THEME_VALUE = "AppsUseLightTheme"

MONO = ("Cascadia Mono", "Cascadia Code", "JetBrains Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono",
        "Liberation Mono")
MARKS = {"saved": ("✓ saved", "ok"), "found": ("? confirm", "warn"), "edited": ("• edited", "warn"),
         "problem": ("✗ problem", "bad"), "missing": ("✗ missing", "bad")}

TAB_MARKS = {
    "Play": "►",
    "Locations": "⌂",
    "Status": "●",
    "Settings": "≡",
    "Tests": "◊",
    "Mod tools": "♦",
    "Log": "▸",
}

CHECKLIST_ITEMS = (
    ("fo4_data", "Fallout 4 Data"),
    ("starfield", "Starfield"),
    ("my_games", "My Games"),
)

STEP_DESCRIPTIONS = {
    "init": "Write alife_config.json into the output folder",
    "validate": "Check schema, 128-slot Papyrus cap, and graph connectivity",
    "simulate": "Run deterministic offline tick simulation and faction table",
    "package": "Compile .esm + .pex into dist/ (reads Starfield from Locations)",
    "verify-dist": "Verify SHA-256 manifest, plugin header, and script magic",
}


def tab_label(name):
    mark = TAB_MARKS.get(name, "")
    return f"{mark}  {name}" if mark else name


def detect_windows_light_theme(reg_reader=None, *, windows=None):
    """Read HKCU Personalize AppsUseLightTheme on Windows; default safely to False (dark)."""
    if windows is False:
        return False
    if reg_reader is None:
        if not (os.name == "nt" if windows is None else windows):
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
                raw, _kind = winreg.QueryValueEx(key, LIGHT_THEME_VALUE)
        except (ImportError, OSError):
            return False
    else:
        try:
            raw = reg_reader(PERSONALIZE_KEY, LIGHT_THEME_VALUE)
        except OSError:
            return False
    if isinstance(raw, tuple):
        raw = raw[0]
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return False
    try:
        return int(raw) != 0
    except (TypeError, ValueError):
        return False


def select_palette(light=None, *, reg_reader=None):
    use_light = detect_windows_light_theme(reg_reader=reg_reader) if light is None else bool(light)
    return dict(LIGHT_PALETTE if use_light else DARK_PALETTE)


def format_header_state(saved, *, pids=None, process_error="", raw=None, recovery_reason=None):
    """Format read-only header state for live Starfield process and crash-watcher / recovery."""
    saved = saved or {}
    active = raw if raw is not None else saved

    if process_error:
        game_text, game_tone = "✗ Game: check failed", "bad"
    elif pids is None:
        game_text, game_tone = "● Game: checking", "warn"
    elif pids:
        game_text = "● Game: running (PID " + ", ".join(map(str, pids)) + ")"
        game_tone = "ok"
    else:
        game_text, game_tone = "● Game: closed", "ok"

    if recovery_reason is None:
        folder = saved.get("instance") or saved.get("starfield") or ""
        rec_reason = recovery.play_reason(folder) if folder and os.path.isdir(folder) else ""
    else:
        rec_reason = recovery_reason

    if rec_reason:
        if "unreadable" in rec_reason.lower():
            watcher_text, watcher_tone = "✗ Recovery: unreadable", "bad"
        else:
            watcher_text, watcher_tone = "! Recovery: needed", "bad"
    else:
        watcher_keys = ("crash_watch.enabled", "crash_watch.dump", "crash_watch.folder", "crash_watch.procdump")
        unsaved = raw is not None and any(raw.get(k) != saved.get(k) for k in watcher_keys if k in raw)
        if active.get("crash_watch.enabled"):
            pd_bad = paths.check("crash_watch.procdump", active.get("crash_watch.procdump", ""))
            fd_bad = paths.check("crash_watch.folder", active.get("crash_watch.folder", ""))
            dump_kind = active.get("crash_watch.dump", "mini")
            if pd_bad or fd_bad:
                watcher_text, watcher_tone = "! Watcher: setup needed", "bad"
            elif unsaved:
                watcher_text, watcher_tone = f"• Watcher: {dump_kind} (unsaved)", "warn"
            else:
                watcher_text, watcher_tone = f"● Watcher: armed ({dump_kind})", "ok"
        elif unsaved:
            watcher_text, watcher_tone = "• Watcher: off (unsaved)", "warn"
        else:
            watcher_text, watcher_tone = "○ Watcher: off", "muted"

    return {
        "game_text": game_text,
        "game_tone": game_tone,
        "watcher_text": watcher_text,
        "watcher_tone": watcher_tone,
    }


def first_run_checklist(saved, statuses=None, *, found=None, prefer=()):
    """Compute first-run folder confirmation state for Fallout 4 Data, Starfield, and My Games."""
    if statuses is None:
        row_map = {r["key"]: r["status"] for r in paths.rows(saved or {}, found or {}, prefer)}
    else:
        row_map = dict(statuses)

    status_meta = {
        "saved": (True, "✓", "ok", "confirmed"),
        "found": (False, "?", "warn", "detected — confirm below"),
        "edited": (False, "•", "warn", "edited — confirm below"),
        "problem": (False, "✗", "bad", "fix folder path"),
        "missing": (False, "○", "bad", "choose folder"),
    }
    items = []
    for key, label in CHECKLIST_ITEMS:
        st = row_map.get(key, "missing")
        done, mark, tone, detail = status_meta.get(st, status_meta["missing"])
        items.append({
            "key": key,
            "label": label,
            "status": st,
            "done": done,
            "mark": mark,
            "tone": tone,
            "detail": detail,
        })

    confirmed = sum(1 for item in items if item["done"])
    total = len(items)
    remaining = [item["label"] for item in items if not item["done"]]
    ready = confirmed == total
    if ready:
        summary = f"First-run checklist ({confirmed}/{total}): all required folders confirmed."
        tone = "ok"
    elif all(item["status"] in ("saved", "found", "edited") for item in items):
        summary = f"First-run checklist ({confirmed}/{total}): press Confirm locations for {', '.join(remaining)}."
        tone = "warn"
    else:
        summary = f"First-run checklist ({confirmed}/{total}): confirm {', '.join(remaining)} before Play."
        tone = "warn" if confirmed > 0 else "bad"

    return {
        "items": items,
        "confirmed": confirmed,
        "total": total,
        "remaining": remaining,
        "ready": ready,
        "summary": summary,
        "tone": tone,
    }


WORKFLOW_STEPS = (
    ("locate", "1. Locate"),
    ("build", "2. Build or Update"),
    ("play", "3. Play"),
)


def workflow_steps(saved, *, loc_statuses=None, play_reason="", busy_action=""):
    """Compute headless GAMMA-style 3-step workflow state (Locate -> Build or Update -> Play)."""
    saved = saved or {}
    chk = first_run_checklist(saved, loc_statuses)
    locate_done = chk["ready"]
    if locate_done:
        locate_tone = "ok"
        locate_detail = f"✓ {chk['confirmed']}/{chk['total']} folders confirmed"
    else:
        locate_tone = "warn" if chk["confirmed"] > 0 else "bad"
        locate_detail = f"{chk['confirmed']}/{chk['total']} confirmed — open Locations"

    build_running = busy_action in ("detect", "status", "update-check", "update") or busy_action.startswith(
        ("tests-", "alife-")
    )
    if build_running:
        build_tone = "warn"
        build_detail = f"◐ running {busy_action}"
    elif locate_done:
        build_tone = "ok"
        build_detail = "✓ ready to check / build / update"
    else:
        build_tone = "muted"
        build_detail = "confirm folders in Step 1 first"

    cover_note = " · cover on" if saved.get("start_cover") else ""
    if busy_action == "play":
        play_tone = "ok"
        play_detail = f"► session running{cover_note}"
    elif not play_reason:
        play_tone = "ok"
        play_detail = f"► ready to launch{cover_note}"
    else:
        play_tone = "muted" if busy_action else "warn"
        short = play_reason if len(play_reason) <= 44 else play_reason[:41].rstrip() + "..."
        play_detail = short

    return [
        {"key": "locate", "label": "1. Locate", "ready": locate_done, "tone": locate_tone, "detail": locate_detail},
        {"key": "build", "label": "2. Build or Update", "ready": locate_done, "tone": build_tone, "detail": build_detail},
        {"key": "play", "label": "3. Play", "ready": not play_reason, "tone": play_tone, "detail": play_detail},
    ]


def format_alife_metrics(metrics):
    """Format A-Life key numbers (nodes N/128, spawns, battles, captures) for display."""
    m = metrics or {}
    nodes = m.get("nodes") or f"—/{alife_tools.ARRAY_CAP}"
    spawns = m.get("spawns") or "—"
    battles = m.get("battles") or "—"
    captures = m.get("captures") or "—"
    return {
        "nodes": f"nodes {nodes}",
        "spawns": f"spawns {spawns}",
        "battles": f"battles {battles}",
        "captures": f"captures {captures}",
        "summary": f"nodes {nodes}  ·  spawns {spawns}  ·  battles {battles}  ·  captures {captures}",
    }


class ModToolsSession:
    """Headless state and runner bridge between gui.py and alife_tools.ModToolsModel."""

    def __init__(self, model, *, runner=None):
        self.model = model
        self._runner = runner
        self.statuses = {step: "not_run" for step in alife_tools.STEPS}
        self.metrics = {}
        self.table_columns = []
        self.table_rows = []
        self.active_step = ""
        self.parser = None
        self.last_error = {"title": "", "message": "", "hint": ""}

    def progress(self):
        return alife_tools.progress(self.statuses)

    def progress_text(self):
        return alife_tools.progress_text(self.statuses)

    def key_numbers(self):
        return format_alife_metrics(self.metrics)

    def step_rows(self):
        rows = []
        for step in alife_tools.STEPS:
            st = self.statuses.get(step, "not_run")
            mark_text, mark_tone = alife_tools.STEP_MARKS[st]
            pct = 100 if st == "passed" else 50 if st == "running" else 0
            rows.append({
                "step": step,
                "label": alife_tools.STEP_LABELS[step],
                "status": st,
                "mark_text": mark_text,
                "mark_tone": mark_tone,
                "progress_pct": pct,
                "description": STEP_DESCRIPTIONS[step],
            })
        return rows

    def prepare(self, step, *, output_dir, template="vanilla", ticks=20, seed=42, pack_ba2=False, force=False):
        try:
            return self.model.command(
                step,
                output_dir=output_dir,
                template=template,
                ticks=ticks,
                seed=seed,
                pack_ba2=pack_ba2,
                force=force,
            )
        except ValueError as e:
            if step in self.statuses:
                self.statuses[step] = "failed"
            self.last_error = format_error_banner(str(e), action=f"alife-{step}")
            raise

    def begin(self, step):
        self.active_step = step
        self.statuses[step] = "running"
        self.parser = alife_tools.StepRunParser(step)
        self.last_error = {"title": "", "message": "", "hint": ""}

    def observe(self, line):
        if self.parser is not None:
            self.parser.observe(line)
            if self.parser.metrics:
                self.metrics.update(self.parser.metrics)

    def finish(self, exit_code, *, transport_error=""):
        step = self.active_step
        self.active_step = ""
        if self.parser is None:
            st = "passed" if exit_code == 0 and not transport_error else "failed"
            if step in self.statuses:
                self.statuses[step] = st
            err = transport_error or ("" if exit_code == 0 else f"{step} exited with code {exit_code}")
            self.last_error = format_error_banner(err, action=f"alife-{step}", exit_code=exit_code) if err else {
                "title": "", "message": "", "hint": ""}
            return {"step": step, "status": st, "metrics": dict(self.metrics),
                    "table_columns": list(self.table_columns), "table_rows": list(self.table_rows), "error": err}

        done = self.parser.finished(1 if transport_error else exit_code)
        self.parser = None
        if step in self.statuses:
            self.statuses[step] = done["status"]
        if done["metrics"]:
            self.metrics.update(done["metrics"])
        if done["table_columns"]:
            self.table_columns = list(done["table_columns"])
            self.table_rows = [list(r) for r in done["table_rows"]]
        err_text = transport_error or done["error"]
        if err_text:
            self.last_error = format_error_banner(
                err_text, action=f"alife-{step}", exit_code=1 if transport_error else exit_code
            )
            done["error"] = err_text
        else:
            self.last_error = {"title": "", "message": "", "hint": ""}
        return done

    def run_step(self, step, on_line=None, *, popen=subprocess.Popen, **kwargs):
        """Synchronous worker helper exercising prepare -> begin -> run_command(cwd=repo_dir) -> finish."""
        argv = self.prepare(step, **kwargs)
        self.begin(step)
        runner = self._runner or run_command
        def handle_line(line):
            self.observe(line)
            if on_line is not None:
                on_line(line)
        try:
            rc = runner(argv, handle_line, popen=popen, cwd=self.model.repo_dir)
        except Exception as e:
            self.finish(1, transport_error=str(e))
            raise
        self.finish(rc)
        return rc

    def open_output_dir(self, output_dir, *, opener=None, windows=None):
        ok, target = self.model.can_open_output_dir(output_dir)
        if not ok:
            self.last_error = format_error_banner(target, action="alife-open")
            return False, target
        is_win = os.name == "nt" if windows is None else bool(windows)
        if not is_win and opener is None:
            msg = "Opening the output folder is available on Windows."
            self.last_error = format_error_banner(msg, action="alife-open")
            return False, msg
        try:
            (opener or os.startfile)(target)
        except OSError as e:
            self.last_error = format_error_banner(str(e), action="alife-open")
            return False, str(e)
        self.last_error = {"title": "", "message": "", "hint": ""}
        return True, target


def pick_font(families):
    for name in MONO:
        if name in families:
            return name
    return "TkFixedFont"


def apply_theme(root, ttk, tkfont, *, light=None):
    use_light = detect_windows_light_theme() if light is None else bool(light)
    c = LIGHT_PALETTE if use_light else DARK_PALETTE
    accent_active = "#0550ae" if use_light else "#79b8ff"
    banner_bg = "#ffebe9" if use_light else "#2d1215"
    face = pick_font(set(tkfont.families(root)))
    base, small, bold, title = (face, 10), (face, 9), (face, 10, "bold"), (face, 13, "bold")
    root.configure(background=c["bg"])
    root.option_add("*TCombobox*Listbox.background", c["field"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
    root.option_add("*TCombobox*Listbox.font", base)
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=c["bg"], foreground=c["fg"], font=base, bordercolor=c["border"],
                 lightcolor=c["border"], darkcolor=c["border"], troughcolor=c["panel"], focuscolor=c["accent"],
                 selectbackground=c["accent"], selectforeground=c["bg"], insertcolor=c["fg"])
    st.configure("TFrame", background=c["bg"])
    st.configure("Panel.TFrame", background=c["panel"])
    st.configure("Card.TFrame", background=c["panel"], borderwidth=1, relief="solid")
    st.configure("Banner.TFrame", background=banner_bg, borderwidth=1, relief="solid")
    st.configure("TLabel", background=c["bg"], foreground=c["fg"])
    st.configure("Bold.TLabel", background=c["bg"], foreground=c["fg"], font=bold)
    st.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"], font=small)
    st.configure("Title.TLabel", background=c["panel"], foreground=c["accent"], font=title)
    st.configure("Panel.TLabel", background=c["panel"], foreground=c["fg"])
    st.configure("PanelBold.TLabel", background=c["panel"], foreground=c["fg"], font=bold)
    st.configure("PanelMuted.TLabel", background=c["panel"], foreground=c["muted"], font=small)
    st.configure("BannerTitle.TLabel", background=banner_bg, foreground=c["bad"], font=bold)
    st.configure("BannerBody.TLabel", background=banner_bg, foreground=c["fg"], font=small)
    for name in ("ok", "warn", "bad", "muted"):
        st.configure(f"{name}.TLabel", background=c["bg"], foreground=c[name])
        st.configure(f"Panel.{name}.TLabel", background=c["panel"], foreground=c[name],
                     font=small if name == "muted" else base)
    st.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
    st.configure("TNotebook.Tab", background=c["panel"], foreground=c["muted"], padding=(16, 8), borderwidth=0)
    st.map("TNotebook.Tab", background=[("selected", c["bg"])], foreground=[("selected", c["fg"])])
    st.configure("TButton", background=c["panel"], foreground=c["fg"], padding=(14, 7), borderwidth=1, relief="flat")
    st.map("TButton", background=[("disabled", c["bg"]), ("active", c["border"])],
           foreground=[("disabled", c["muted"])], bordercolor=[("focus", c["accent"]), ("active", c["accent"])])
    st.configure("Small.TButton", background=c["panel"], foreground=c["fg"], padding=(10, 4),
                 borderwidth=1, relief="flat", font=small)
    st.configure("Accent.TButton", background=c["accent"], foreground=c["bg"], padding=(16, 7), font=bold)
    st.map("Accent.TButton", background=[("disabled", c["panel"]), ("active", accent_active)],
           foreground=[("disabled", c["muted"])])
    st.configure("TEntry", fieldbackground=c["field"], foreground=c["fg"], padding=6, insertcolor=c["fg"])
    st.map("TEntry", bordercolor=[("focus", c["accent"])])
    st.configure("TCombobox", fieldbackground=c["field"], background=c["panel"], foreground=c["fg"],
                 arrowcolor=c["fg"], padding=5)
    st.map("TCombobox", fieldbackground=[("readonly", c["field"])], foreground=[("readonly", c["fg"])],
           bordercolor=[("focus", c["accent"])])
    st.configure("TCheckbutton", background=c["bg"], foreground=c["fg"], indicatorbackground=c["field"],
                 indicatorforeground=c["accent"], padding=(4, 3))
    st.map("TCheckbutton", background=[("active", c["bg"])], indicatorbackground=[("selected", c["field"])])
    st.configure("Panel.TCheckbutton", background=c["panel"], foreground=c["fg"], indicatorbackground=c["field"],
                 indicatorforeground=c["accent"], padding=(4, 3))
    st.map("Panel.TCheckbutton", background=[("active", c["panel"])], indicatorbackground=[("selected", c["field"])])
    st.configure("Vertical.TScrollbar", background=c["panel"], arrowcolor=c["muted"], borderwidth=0)
    st.configure("Horizontal.TProgressbar", troughcolor=c["field"], background=c["accent"],
                 bordercolor=c["border"], lightcolor=c["accent"], darkcolor=c["accent"], thickness=10)
    st.configure("Treeview", background=c["field"], fieldbackground=c["field"], foreground=c["fg"],
                 bordercolor=c["border"], borderwidth=1, rowheight=26, font=small)
    st.map("Treeview", background=[("selected", c["accent"])], foreground=[("selected", c["bg"])])
    st.configure("Treeview.Heading", background=c["panel"], foreground=c["muted"], font=(face, 9, "bold"),
                 padding=(8, 5), relief="flat")
    st.map("Treeview.Heading", background=[("active", c["border"])])
    text = {"background": c["field"], "foreground": c["fg"], "insertbackground": c["fg"], "font": base,
            "relief": "flat", "highlightthickness": 1, "highlightbackground": c["border"],
            "highlightcolor": c["accent"], "selectbackground": c["accent"], "selectforeground": c["bg"],
            "padx": 8, "pady": 6}
    return text


def launch(launcher, path, *, recipe="", overrides=(), fo4_data=(), starfield=""):
    # The CLI's --help and every other subcommand work even when Python has no tkinter or display.
    try:
        import tkinter as tk
        from tkinter import filedialog, font as tkfont, messagebox, ttk
        from tkinter.scrolledtext import ScrolledText
    except ImportError:
        raise ValueError("The launcher window needs Python's tkinter; the command-line launcher still works") from None
    model = SettingsModel(launcher, path)
    alife_model = alife_tools.ModToolsModel(launcher, path)
    alife_session = ModToolsSession(alife_model)
    try:
        root = tk.Tk()
    except tk.TclError as e:
        raise ValueError(f"Cannot open the launcher window: {e}") from None
    use_light = detect_windows_light_theme()
    palette = select_palette(use_light)
    text_style = apply_theme(root, ttk, tkfont, light=use_light)
    # paths given on the command line are offered like found ones: the player still confirms them
    given = {}
    if starfield:
        given["starfield"] = (os.path.normpath(starfield), "command line")
    if fo4_data:
        given["fo4_data"] = (paths.join_dirs(fo4_data), "command line")

    class Window:
        def __init__(self):
            self.events = queue.Queue()
            self.busy, self.closed, self.action = False, False, ""
            self.pids, self.process_error = None, ""
            self.found = dict(given)
            self.dirty = set()                     # locations the player typed or browsed and has not saved yet
            self.widgets, self.vars, self.loc = [], {}, {}
            self.alife_session = alife_session
            self.cover_window = None
            self.cover_controller = None
            self.cover_crash_reason = ""
            self.start_place_box = None
            root.title("FO4SF Launcher")
            root.geometry("1040x840")
            root.minsize(840, 650)
            root.columnconfigure(0, weight=1)
            root.rowconfigure(3, weight=1)

            # Top read-only header strip: title + live Starfield process state + crash-watcher / recovery state
            header = ttk.Frame(root, style="Panel.TFrame", padding=(18, 12))
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(1, weight=1)
            ttk.Label(header, text="fo4sf ▸ launcher", style="Title.TLabel").grid(row=0, column=0, sticky="w")
            status_strip = ttk.Frame(header, style="Panel.TFrame")
            status_strip.grid(row=0, column=2, sticky="e")
            self.game = tk.StringVar(value="● Game: checking")
            self.game_label = ttk.Label(status_strip, textvariable=self.game, style="Panel.warn.TLabel")
            self.game_label.pack(side="left", padx=(0, 16))
            self.watcher = tk.StringVar(value="○ Watcher: off")
            self.watcher_label = ttk.Label(status_strip, textvariable=self.watcher, style="Panel.muted.TLabel")
            self.watcher_label.pack(side="left")

            # GAMMA-style three-step workflow strip: 1. Locate -> 2. Build or Update -> 3. Play (+ offline cover preview)
            self.workflow_frame = ttk.Frame(root, style="Card.TFrame", padding=(14, 10))
            self.workflow_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 0))
            for col in range(3):
                self.workflow_frame.columnconfigure(col, weight=1)
            self.workflow_step_widgets = {}
            step_commands = {
                "locate": lambda: self.notebook.select(self.places_tab),
                "build": lambda: self.notebook.select(self.status_tab),
                "play": lambda: self.start("play"),
            }
            for col, (step_key, step_title) in enumerate(WORKFLOW_STEPS):
                cell = ttk.Frame(self.workflow_frame, style="Panel.TFrame")
                cell.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0))
                btn_style = "Accent.TButton" if step_key == "play" else "Small.TButton"
                step_btn = ttk.Button(cell, text=step_title, style=btn_style, command=step_commands[step_key])
                step_btn.pack(side="left", padx=(0, 8))
                detail_var = tk.StringVar(value="")
                detail_lbl = ttk.Label(cell, textvariable=detail_var, style="PanelMuted.TLabel")
                detail_lbl.pack(side="left", fill="x", expand=True)
                self.workflow_step_widgets[step_key] = {"button": step_btn, "var": detail_var, "label": detail_lbl}
                if step_key != "play":
                    self.widgets.append((step_btn, "normal"))
            self.step_play_btn = self.workflow_step_widgets["play"]["button"]
            self.preview_cover_btn = ttk.Button(
                self.workflow_frame, text="Preview cover", style="Small.TButton",
                command=lambda: self.open_start_cover(for_play=False),
            )
            self.preview_cover_btn.grid(row=0, column=3, sticky="e", padx=(12, 0))
            self.widgets.append((self.preview_cover_btn, "normal"))

            # Dismissible / auto-updating readable error banner (hidden until an error or refusal occurs)
            self.banner_frame = ttk.Frame(root, style="Banner.TFrame", padding=(14, 8))
            self.banner_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
            self.banner_frame.columnconfigure(0, weight=1)
            self.banner_title_var = tk.StringVar()
            self.banner_body_var = tk.StringVar()
            ttk.Label(self.banner_frame, textvariable=self.banner_title_var, style="BannerTitle.TLabel").grid(
                row=0, column=0, sticky="w")
            ttk.Label(self.banner_frame, textvariable=self.banner_body_var, style="BannerBody.TLabel",
                      wraplength=880).grid(row=1, column=0, sticky="w", pady=(2, 0))
            ttk.Button(self.banner_frame, text="× Dismiss", style="Small.TButton",
                       command=self.clear_error_banner).grid(row=0, column=1, rowspan=2, padx=(12, 0), sticky="ne")
            self.banner_frame.grid_remove()

            self.notebook = ttk.Notebook(root)
            self.notebook.grid(row=3, column=0, sticky="nsew", padx=12, pady=(8, 0))
            places, status, config, tests, mod_tools, logs = (ttk.Frame(self.notebook, padding=16) for _ in range(6))
            for frame, name in ((places, "Locations"), (status, "Status"), (config, "Settings"),
                                (tests, "Tests"), (mod_tools, "Mod tools"), (logs, "Log")):
                self.notebook.add(frame, text=tab_label(name))
            self.places_tab = places
            self.status_tab = status
            self.mod_tools_tab = mod_tools
            self.build_locations(places)
            self.build_status(status)
            self.build_settings(config)
            self.build_tests(tests)
            self.build_mod_tools(mod_tools)
            self.build_log(logs)

            footer = ttk.Frame(root, padding=(16, 12))
            footer.grid(row=4, column=0, sticky="ew")
            footer.columnconfigure(0, weight=1)
            self.message = tk.StringVar(value="Looking for the game folders…")
            ttk.Label(footer, textvariable=self.message, wraplength=600).grid(row=0, column=0, sticky="w")
            self.reason = tk.StringVar()
            ttk.Label(footer, textvariable=self.reason, style="Muted.TLabel", wraplength=600).grid(
                row=1, column=0, sticky="w", pady=(2, 0))
            reload_button = ttk.Button(footer, text="Reload", command=self.reload_settings)
            reload_button.grid(row=0, column=1, rowspan=2, padx=(8, 0))
            save = ttk.Button(footer, text="Save settings", command=lambda: self.start("save", part="settings"))
            save.grid(row=0, column=2, rowspan=2, padx=(8, 0))
            self.play = ttk.Button(footer, text="►  Play", style="Accent.TButton", command=lambda: self.start("play"))
            self.play.grid(row=0, column=3, rowspan=2, padx=(8, 0))
            self.widgets += [(reload_button, "normal"), (save, "normal")]
            recover = ttk.Button(footer, text="Recover install", command=lambda: self.start("recover-install"))
            recover.grid(row=0, column=4, rowspan=2, padx=(8, 0))
            self.widgets.append((recover, "normal"))
            for var in self.vars.values():
                var.trace_add("write", lambda *_args: self.refresh_play())
            if "start.mode" in self.vars:
                self.vars["start.mode"].trace_add("write", lambda *_args: self.refresh_start_place_choices())
            root.protocol("WM_DELETE_WINDOW", self.close)
            self.render_locations()
            self.refresh_start_place_choices()
            self.refresh_play()
            self.detect_locations()
            root.after(75, self.drain)
            self.poll_processes()
            self.refresh_tests()

        # --- Banner & Header helpers -------------------------------------------------------------------------
        def show_error_banner(self, banner):
            if not banner or not banner.get("message"):
                self.clear_error_banner()
                return
            self.banner_title_var.set("✗  " + banner["title"])
            body = banner["message"]
            if banner.get("hint"):
                body = f"{body}  ({banner['hint']})"
            self.banner_body_var.set(body)
            self.banner_frame.grid()

        def clear_error_banner(self):
            self.banner_title_var.set("")
            self.banner_body_var.set("")
            self.banner_frame.grid_remove()

        def refresh_header(self):
            raw_vals = None
            if len(self.loc) == len(paths.KEYS) and len(self.vars) == len(controls()):
                raw_vals = self.raw()
            state = format_header_state(
                model.saved,
                pids=self.pids,
                process_error=self.process_error,
                raw=raw_vals,
            )
            self.game.set(state["game_text"])
            self.game_label.configure(style=f"Panel.{state['game_tone']}.TLabel")
            self.watcher.set(state["watcher_text"])
            self.watcher_label.configure(style=f"Panel.{state['watcher_tone']}.TLabel")

        # --- Tests -------------------------------------------------------------------------------------------
        def build_tests(self, tab):
            ttk.Label(tab, text="Choose a staged test kit below. Install and Remove use its installer with the game closed.",
                      wraplength=860).pack(anchor="w")
            bar = ttk.Frame(tab)
            bar.pack(fill="x", pady=(10, 14))
            self.kit_choice = ttk.Combobox(bar, state="readonly", values=[k.title for k in test_kits.KITS], width=16)
            self.kit_choice.current(0)
            self.kit_choice.pack(side="left")
            add = ttk.Button(bar, text="Add staged kit…", command=self.add_kit)
            add.pack(side="left", padx=8)
            refresh = ttk.Button(bar, text="Refresh", command=self.refresh_tests)
            refresh.pack(side="left")
            standalone = ttk.Button(bar, text="Standalone owner card", command=lambda: self.show_card(
                os.path.join(os.path.dirname(os.path.dirname(model.launcher)), "docs", "testing", "standalone")))
            standalone.pack(side="right")
            self.widgets += [(self.kit_choice, "readonly"), (add, "normal"), (refresh, "normal"), (standalone, "normal")]
            self.kit_list = ttk.Frame(tab)
            self.kit_list.pack(fill="both", expand=True)
            self.kit_buttons, self.kit_generation = [], 0
            self.kit_status = ttk.Label(tab, text="Refresh to read the staged and installed test kits.",
                                        style="Muted.TLabel", wraplength=860)
            self.kit_status.pack(anchor="w", pady=(8, 0))

        def refresh_tests(self):
            if self.busy:
                return
            self.kit_generation += 1
            generation = self.kit_generation
            self.kit_status.configure(text="Reading test kits…")
            def read():
                try:
                    value = test_kits.inventory(model.path, os.path.dirname(os.path.dirname(model.launcher)))
                    self.events.put(("kits", (generation, value, "")))
                except (OSError, ValueError) as error:
                    self.events.put(("kits", (generation, [], str(error))))
            threading.Thread(target=read, daemon=True).start()

        def render_kits(self, rows, error):
            for child in self.kit_list.winfo_children():
                child.destroy()
            self.kit_buttons = []
            self.kit_status.configure(text=error or ("No test kits registered or installed. Add a staged kit above." if not rows
                else "Install uses a prepared archive. Ask the PC helper if a kit is unavailable or refuses."))
            for row in rows:
                panel = ttk.Frame(self.kit_list, padding=(0, 8))
                panel.pack(fill="x", anchor="n")
                panel.columnconfigure(0, weight=1)
                ttk.Label(panel, text=row["title"] + " — " + row["state"]).grid(row=0, column=0, sticky="w")
                for col, action, text in ((1, "install", "Install"), (2, "remove", "Remove")):
                    button = ttk.Button(panel, text=text, command=lambda r=row, a=action: self.start_kit(a, r["key"]))
                    button.grid(row=0, column=col, padx=(8, 0))
                    available = row["installer_available"] and (row["installed"] == (action == "remove"))
                    self.kit_buttons.append((button, action, row["key"], available))
                ttk.Button(panel, text="Show card", command=lambda r=row: self.show_card(r["stage"])).grid(
                    row=0, column=3, padx=(8, 0))
                note = "; ".join(row["problems"])
                if not row["installer_available"]:
                    note = (note + "; " if note else "") + "Installer unavailable in this checkout"
                if row["notice"]:
                    ttk.Label(panel, text=row["notice"], style="warn.TLabel").grid(row=1, column=0, columnspan=4, sticky="w")
                if note:
                    ttk.Label(panel, text=note, style="Muted.TLabel", wraplength=850).grid(
                        row=2, column=0, columnspan=4, sticky="w")
            self.refresh_kit_controls()

        def refresh_kit_controls(self):
            for button, action, key, available in getattr(self, "kit_buttons", []):
                enabled = available and not self.busy
                if enabled:
                    try:
                        model.kit_command(action, self.raw(), key, None if self.process_error else self.pids)
                    except (OSError, ValueError):
                        enabled = False
                button.configure(state="normal" if enabled else "disabled")

        def show_card(self, stage):
            try:
                text = test_kits.owner_card(stage) if stage else ""
                if not text:
                    raise ValueError("No owner-card folder was recorded; ask the PC helper for the kit's card")
            except OSError:
                msg = "Cannot read owner card; ask the PC helper to check the card file"
                self.message.set(msg)
                self.show_error_banner(format_error_banner(msg, action="card"))
                return
            except ValueError as error:
                msg = f"Cannot show owner card: {error}"
                self.message.set(msg)
                self.show_error_banner(format_error_banner(msg, action="card"))
                return
            dialog = tk.Toplevel(root)
            dialog.title("FO4SF owner test card")
            dialog.geometry("800x420")
            box = tk.Text(dialog, wrap="word", **dict(text_style, padx=16, pady=16))
            box.pack(fill="both", expand=True)
            box.insert("1.0", text)
            box.configure(state="disabled")
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=8)

        def add_kit(self):
            if self.busy:
                return
            key = test_kits.KITS[self.kit_choice.current()].key
            folder = filedialog.askdirectory(title="Choose the staged test-kit folder", parent=root)
            if folder:
                self.start_kit("register", key, folder)

        def start_kit(self, action, key, stage=""):
            if self.busy:
                return
            try:
                argv = model.kit_command(action, self.raw(), key, None if self.process_error else self.pids, stage=stage)
            except (OSError, ValueError) as error:
                self.message.set(str(error))
                self.show_error_banner(format_error_banner(str(error), action="tests-" + action))
                return
            self.launch_command("tests-" + action, argv)

        # --- Locations ---------------------------------------------------------------------------------------
        def build_locations(self, tab):
            tab.columnconfigure(2, weight=1)
            # First-run checklist panel
            checklist_box = ttk.Frame(tab, style="Card.TFrame", padding=(14, 10))
            checklist_box.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 12))
            checklist_box.columnconfigure(0, weight=1)
            self.checklist_summary_var = tk.StringVar()
            self.checklist_summary_label = ttk.Label(checklist_box, textvariable=self.checklist_summary_var,
                                                     style="PanelBold.TLabel")
            self.checklist_summary_label.grid(row=0, column=0, columnspan=3, sticky="w")
            self.checklist_item_labels = {}
            items_row = ttk.Frame(checklist_box, style="Panel.TFrame")
            items_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
            for key, label in CHECKLIST_ITEMS:
                lbl = ttk.Label(items_row, text=f"○ {label}: choose folder", style="Panel.bad.TLabel")
                lbl.pack(side="left", padx=(0, 20))
                self.checklist_item_labels[key] = lbl

            ttk.Label(tab, text="The launcher looked for everything it needs on this PC. Check each path; "
                                "Browse to change one, then press Confirm locations.",
                      style="Muted.TLabel", wraplength=880).grid(row=1, column=0, columnspan=4, sticky="w",
                                                                  pady=(0, 10))
            for i, (key, label, kind, what) in enumerate(paths.LOCATIONS):
                r = 2 + 2 * i
                ttk.Label(tab, text=label).grid(row=r, column=0, sticky="nw", padx=(0, 12), pady=(6, 0))
                mark = ttk.Label(tab, text="", width=11)
                mark.grid(row=r, column=1, sticky="nw", pady=(6, 0))
                if kind == "dirs":
                    entry = tk.Text(tab, height=3, wrap="none", **text_style)
                    entry.bind("<<Modified>>", lambda _e, k=key: self.location_edited(k))
                else:
                    var = tk.StringVar()
                    entry = ttk.Entry(tab, textvariable=var)
                    entry.var = var
                    var.trace_add("write", lambda *_a, k=key: self.location_edited(k))
                entry.grid(row=r, column=2, sticky="ew", pady=(4, 0))
                browse = ttk.Button(tab, text="Browse…", command=lambda k=key, kd=kind: self.browse(k, kd))
                browse.grid(row=r, column=3, sticky="ne", padx=(8, 0), pady=(4, 0))
                note = ttk.Label(tab, text=what, style="Muted.TLabel", wraplength=660)
                note.grid(row=r + 1, column=2, columnspan=2, sticky="w", pady=(2, 6))
                self.loc[key] = {"entry": entry, "mark": mark, "note": note, "what": what, "kind": kind,
                                 "status": "missing", "quiet": False}
                self.widgets += [(entry, "normal"), (browse, "normal")]
            buttons = ttk.Frame(tab)
            buttons.grid(row=3 + 2 * len(paths.LOCATIONS), column=0, columnspan=4, sticky="e", pady=(12, 0))
            again = ttk.Button(buttons, text="Detect again", command=self.detect_locations)
            again.pack(side="left", padx=(0, 8))
            confirm = ttk.Button(buttons, text="Confirm locations", style="Accent.TButton",
                                 command=self.confirm_locations)
            confirm.pack(side="left")
            self.widgets += [(again, "normal"), (confirm, "normal")]

        def refresh_checklist(self):
            statuses = {k: item["status"] for k, item in self.loc.items()}
            state = first_run_checklist(model.saved, statuses)
            self.checklist_summary_var.set(state["summary"])
            self.checklist_summary_label.configure(style=f"Panel.{state['tone']}.TLabel")
            for item in state["items"]:
                lbl = self.checklist_item_labels.get(item["key"])
                if lbl is not None:
                    lbl.configure(
                        text=f"{item['mark']} {item['label']}: {item['detail']}",
                        style=f"Panel.{item['tone']}.TLabel",
                    )

        def location_value(self, key):
            e = self.loc[key]["entry"]
            if self.loc[key]["kind"] == "dirs":
                return paths.join_dirs(e.get("1.0", "end").splitlines())
            return e.var.get().strip()

        def set_location(self, key, value):
            e, item = self.loc[key]["entry"], self.loc[key]
            item["quiet"] = True
            if item["kind"] == "dirs":
                e.configure(state="normal")
                e.delete("1.0", "end")
                e.insert("1.0", "\n".join(paths.split_dirs(value)))
                e.edit_modified(False)
            else:
                e.var.set(value)
            item["quiet"] = False

        def show_mark(self, key, status, note):
            text, colour = MARKS[status]
            item = self.loc[key]
            item["status"] = status
            item["mark"].configure(text=text, style=f"{colour}.TLabel")
            item["note"].configure(text=f"{item['what']}  ·  {note}" if note else item["what"])

        def render_locations(self):
            for row in model.locations(self.found, prefer=given, dirty=self.dirty):
                self.set_location(row["key"], row["value"])
                self.show_mark(row["key"], row["status"], row["note"])
            self.refresh_checklist()
            self.refresh_start_place_choices()
            self.refresh_play()

        def location_edited(self, key):
            item = self.loc[key]
            if item["kind"] == "dirs":
                if not item["entry"].edit_modified():
                    return
                item["entry"].edit_modified(False)
            if item["quiet"]:
                return
            given.pop(key, None)                       # the player's own choice now beats the command line (Codex, #481)
            self.dirty.add(key)
            value = self.location_value(key)
            problem = paths.check(key, value) if value else "not set"
            if value == model.saved[key] and not problem:
                self.show_mark(key, "saved", "saved")
            else:
                self.show_mark(key, "problem" if problem else "edited", problem or "press Confirm locations")
            self.refresh_checklist()
            self.refresh_start_place_choices()
            self.refresh_play()

        def browse(self, key, kind):
            current = paths.split_dirs(self.location_value(key))
            start = current[-1] if current else ""
            if kind == "file":
                choice = filedialog.askopenfilename(initialdir=path_dirname(start) or None,
                                                    filetypes=[("procdump64.exe", "procdump*.exe"), ("All", "*.*")])
            else:
                choice = filedialog.askdirectory(initialdir=start or None, mustexist=key != "crash_watch.folder")
            if not choice:
                return
            choice = os.path.normpath(choice)
            self.set_location(key, paths.join_dirs(current + [choice]) if kind == "dirs" else choice)
            self.location_edited(key) if kind != "dirs" else self.loc[key]["entry"].event_generate("<<Modified>>")
            if kind == "dirs":
                self.loc[key]["entry"].edit_modified(True)
                self.location_edited(key)

        def detect_locations(self):
            self.message.set("Looking for the game folders…")
            def work():
                try:
                    self.events.put(("found", paths.detect()))
                except Exception as e:                          # detection is a convenience: never fatal
                    self.events.put(("found_error", str(e)))
            threading.Thread(target=work, daemon=True).start()

        def confirm_locations(self):
            bad = [(paths.LOCATIONS[i][1], paths.check(k, self.location_value(k)))
                   for i, k in enumerate(paths.KEYS) if self.location_value(k)
                   and paths.check(k, self.location_value(k))]
            if bad:
                msg = "Not saved: " + "; ".join(f"{label}: {why}" for label, why in bad)
                self.message.set(msg)
                self.show_error_banner(format_error_banner(msg, action="locations"))
                return
            self.start("save", part="locations")

        # --- Mod tools (A-Life SDK) --------------------------------------------------------------------------
        def build_mod_tools(self, tab):
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(3, weight=1)

            cfg_panel = ttk.Frame(tab, style="Card.TFrame", padding=(14, 10))
            cfg_panel.grid(row=0, column=0, sticky="ew")
            cfg_panel.columnconfigure(1, weight=1)

            ttk.Label(cfg_panel, text="Output folder", style="Panel.TLabel").grid(
                row=0, column=0, sticky="w", padx=(0, 12))
            self.alife_out_var = tk.StringVar()
            out_entry = ttk.Entry(cfg_panel, textvariable=self.alife_out_var)
            out_entry.grid(row=0, column=1, sticky="ew")
            out_browse = ttk.Button(cfg_panel, text="Browse…", command=self.browse_alife_output)
            out_browse.grid(row=0, column=2, padx=(8, 0))
            self.alife_open_btn = ttk.Button(cfg_panel, text="Open output folder", command=self.open_alife_output)
            self.alife_open_btn.grid(row=0, column=3, padx=(8, 0))

            opts = ttk.Frame(cfg_panel, style="Panel.TFrame")
            opts.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
            ttk.Label(opts, text="Template", style="Panel.TLabel").pack(side="left", padx=(0, 6))
            self.alife_template_var = tk.StringVar(value=alife_tools.TEMPLATES[0])
            template_box = ttk.Combobox(opts, textvariable=self.alife_template_var,
                                        values=alife_tools.TEMPLATES, state="readonly", width=10)
            template_box.pack(side="left", padx=(0, 16))
            ttk.Label(opts, text="Ticks", style="Panel.TLabel").pack(side="left", padx=(0, 6))
            self.alife_ticks_var = tk.StringVar(value="20")
            ticks_entry = ttk.Entry(opts, textvariable=self.alife_ticks_var, width=7)
            ticks_entry.pack(side="left", padx=(0, 14))
            ttk.Label(opts, text="Seed", style="Panel.TLabel").pack(side="left", padx=(0, 6))
            self.alife_seed_var = tk.StringVar(value="42")
            seed_entry = ttk.Entry(opts, textvariable=self.alife_seed_var, width=7)
            seed_entry.pack(side="left", padx=(0, 16))
            self.alife_pack_ba2_var = tk.BooleanVar(value=False)
            pack_chk = ttk.Checkbutton(opts, text="Pack .ba2 archive", variable=self.alife_pack_ba2_var,
                                       style="Panel.TCheckbutton")
            pack_chk.pack(side="left", padx=(0, 14))
            self.alife_force_var = tk.BooleanVar(value=False)
            force_chk = ttk.Checkbutton(opts, text="Overwrite config", variable=self.alife_force_var,
                                        style="Panel.TCheckbutton")
            force_chk.pack(side="left")

            self.widgets += [
                (out_entry, "normal"), (out_browse, "normal"), (self.alife_open_btn, "normal"),
                (template_box, "readonly"), (ticks_entry, "normal"), (seed_entry, "normal"),
                (pack_chk, "normal"), (force_chk, "normal"),
            ]

            # Overall progress strip + key numbers bar
            metrics_bar = ttk.Frame(tab, style="Panel.TFrame", padding=(14, 8))
            metrics_bar.grid(row=1, column=0, sticky="ew", pady=(10, 8))
            metrics_bar.columnconfigure(2, weight=1)
            self.alife_progress_bar = ttk.Progressbar(
                metrics_bar, orient="horizontal", mode="determinate", maximum=len(alife_tools.STEPS), length=170
            )
            self.alife_progress_bar.grid(row=0, column=0, sticky="w", padx=(0, 10))
            self.alife_progress_var = tk.StringVar(value=alife_session.progress_text())
            ttk.Label(metrics_bar, textvariable=self.alife_progress_var, style="PanelBold.TLabel").grid(
                row=0, column=1, sticky="w")
            self.alife_metrics_var = tk.StringVar(value=alife_session.key_numbers()["summary"])
            ttk.Label(metrics_bar, textvariable=self.alife_metrics_var, style="PanelMuted.TLabel").grid(
                row=0, column=2, sticky="e")

            # Five step rows: button, status mark, step progress strip, description
            steps_frame = ttk.Frame(tab)
            steps_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
            steps_frame.columnconfigure(3, weight=1)
            self.alife_step_widgets = {}
            for idx, row in enumerate(alife_session.step_rows()):
                step = row["step"]
                btn = ttk.Button(steps_frame, text=row["label"], width=13,
                                 command=lambda s=step: self.start_alife_step(s))
                btn.grid(row=idx, column=0, sticky="w", pady=3, padx=(0, 10))
                mark_lbl = ttk.Label(steps_frame, text=row["mark_text"], style=f"{row['mark_tone']}.TLabel", width=12)
                mark_lbl.grid(row=idx, column=1, sticky="w", padx=(0, 10))
                step_bar = ttk.Progressbar(steps_frame, orient="horizontal", mode="determinate",
                                           maximum=100, length=88, value=row["progress_pct"])
                step_bar.grid(row=idx, column=2, sticky="w", padx=(0, 12))
                desc_lbl = ttk.Label(steps_frame, text=row["description"], style="Muted.TLabel", wraplength=540)
                desc_lbl.grid(row=idx, column=3, sticky="w")
                self.alife_step_widgets[step] = {"button": btn, "mark": mark_lbl, "bar": step_bar, "desc": desc_lbl}
                self.widgets.append((btn, "normal"))

            # Simulation result table (ttk.Treeview)
            table_wrap = ttk.Frame(tab)
            table_wrap.grid(row=3, column=0, sticky="nsew")
            table_wrap.columnconfigure(0, weight=1)
            table_wrap.rowconfigure(1, weight=1)
            ttk.Label(table_wrap, text="Simulation faction summary (populated by Simulate; full stream in Log)",
                      style="Muted.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
            default_cols = ("faction", "spawned", "losses", "nodes owned", "captures")
            self.alife_table = ttk.Treeview(table_wrap, columns=default_cols, show="headings", height=6)
            for col in default_cols:
                self.alife_table.heading(col, text=col)
                self.alife_table.column(col, width=130, anchor="w" if col == "faction" else "e")
            tscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.alife_table.yview)
            self.alife_table.configure(yscrollcommand=tscroll.set)
            self.alife_table.grid(row=1, column=0, sticky="nsew")
            tscroll.grid(row=1, column=1, sticky="ns")

        def render_alife_state(self):
            done_count, _total = alife_session.progress()
            self.alife_progress_bar["value"] = done_count
            self.alife_progress_var.set(alife_session.progress_text())
            self.alife_metrics_var.set(alife_session.key_numbers()["summary"])
            for row in alife_session.step_rows():
                w = self.alife_step_widgets[row["step"]]
                w["mark"].configure(text=row["mark_text"], style=f"{row['mark_tone']}.TLabel")
                w["bar"]["value"] = row["progress_pct"]
            if alife_session.table_columns:
                cols = tuple(alife_session.table_columns)
                self.alife_table.configure(columns=cols)
                for idx, col in enumerate(cols):
                    self.alife_table.heading(col, text=col)
                    self.alife_table.column(col, width=150 if idx == 0 else 115, anchor="w" if idx == 0 else "e")
                for item_id in self.alife_table.get_children():
                    self.alife_table.delete(item_id)
                for r in alife_session.table_rows:
                    self.alife_table.insert("", "end", values=r)

        def browse_alife_output(self):
            if self.busy:
                return
            current = self.alife_out_var.get().strip()
            choice = filedialog.askdirectory(
                title="Choose output folder (outside Git and Starfield)",
                initialdir=current if current and os.path.isdir(current) else None,
                mustexist=False,
                parent=root,
            )
            if choice:
                self.alife_out_var.set(os.path.normpath(choice))

        def open_alife_output(self):
            ok, info = alife_session.open_output_dir(self.alife_out_var.get())
            if not ok:
                self.message.set(info)
                self.show_error_banner(alife_session.last_error)

        def start_alife_step(self, step):
            if self.busy:
                return
            alife_model.reload()
            try:
                argv = alife_session.prepare(
                    step,
                    output_dir=self.alife_out_var.get(),
                    template=self.alife_template_var.get(),
                    ticks=self.alife_ticks_var.get(),
                    seed=self.alife_seed_var.get(),
                    pack_ba2=self.alife_pack_ba2_var.get(),
                    force=self.alife_force_var.get(),
                )
            except ValueError as e:
                self.render_alife_state()
                self.message.set(str(e))
                self.show_error_banner(alife_session.last_error)
                return
            alife_session.begin(step)
            self.render_alife_state()
            self.launch_command(f"alife-{step}", argv, cwd=alife_model.repo_dir)

        # --- Status, Settings, Log ---------------------------------------------------------------------------
        def build_status(self, tab):
            tab.columnconfigure(1, weight=1)
            tab.rowconfigure(2, weight=1)
            self.recipe = tk.StringVar(value=recipe)
            ttk.Label(tab, text="Build recipe").grid(row=0, column=0, sticky="w", padx=(0, 12))
            ttk.Entry(tab, textvariable=self.recipe).grid(row=0, column=1, sticky="ew")
            def pick():
                choice = filedialog.askopenfilename(filetypes=[("Recipe", "*.json"), ("All", "*.*")])
                if choice:
                    self.recipe.set(os.path.normpath(choice))
            ttk.Button(tab, text="Browse…", command=pick).grid(row=0, column=2, padx=(8, 0))
            actions = ttk.Frame(tab)
            actions.grid(row=1, column=0, columnspan=3, sticky="w", pady=12)
            for action, label in (("detect", "Check installation"), ("status", "Build status"),
                                  ("update-check", "Check for updates"), ("update", "Update launcher")):
                button = ttk.Button(actions, text=label, command=lambda a=action: self.start(a))
                button.pack(side="left", padx=(0, 8))
                self.widgets.append((button, "normal"))
            self.report = ScrolledText(tab, height=12, wrap="word", state="disabled", **text_style)
            self.report.grid(row=2, column=0, columnspan=3, sticky="nsew")

        def build_settings(self, tab):
            canvas = tk.Canvas(tab, highlightthickness=0, background=palette["bg"])
            scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            form = ttk.Frame(canvas, padding=(0, 0, 12, 0))
            item = canvas.create_window((0, 0), window=form, anchor="nw")
            form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
            canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
            form.columnconfigure(1, weight=1)
            ttk.Label(form, text="saved in " + model.path, style="Muted.TLabel", wraplength=760).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
            for i, spec in enumerate(controls()):
                key, kind = spec["key"], spec["kind"]
                var = tk.BooleanVar(value=model.saved[key]) if kind == "bool" else tk.StringVar(value=model.saved[key])
                self.vars[key] = var
                ttk.Label(form, text=spec["label"]).grid(row=1 + 2 * i, column=0, sticky="w", padx=(0, 16))
                if kind == "bool":
                    widget = ttk.Checkbutton(form, variable=var)
                elif kind == "choice":
                    widget = ttk.Combobox(form, textvariable=var, values=spec["choices"], state="readonly")
                elif key == "start.place":
                    init_vals = launch_choices.available_place_options(
                        model.saved["start.mode"],
                        starfield_dir=model.saved.get("instance") or model.saved.get("starfield") or "",
                    )
                    widget = ttk.Combobox(form, textvariable=var, values=init_vals, state="readonly")
                    self.start_place_box = widget
                else:
                    widget = ttk.Entry(form, textvariable=var)
                widget.grid(row=1 + 2 * i, column=1, sticky="w" if kind == "bool" else "ew")
                self.widgets.append((widget, "readonly" if (kind == "choice" or key == "start.place") else "normal"))
                ttk.Label(form, text=spec["cost"], style="Muted.TLabel", wraplength=760).grid(
                    row=2 + 2 * i, column=0, columnspan=2, sticky="w", pady=(2, 14))

        def build_log(self, tab):
            tab.rowconfigure(0, weight=1)
            tab.columnconfigure(0, weight=1)
            self.log = ScrolledText(tab, wrap="word", state="disabled", **text_style)
            self.log.grid(row=0, column=0, sticky="nsew")
            row = ttk.Frame(tab)
            row.grid(row=1, column=0, sticky="ew", pady=(10, 0))
            ttk.Label(row, text="Recent command output. The crash watcher keeps its own crashwatch.log in the dump "
                                "folder.", style="Muted.TLabel").pack(side="left")
            ttk.Button(row, text="Open dump folder", command=self.open_logs).pack(side="right")

        # --- state -------------------------------------------------------------------------------------------
        def raw(self, part="all"):
            """The window's values. part="settings" keeps the saved locations (Save settings never saves a found path
            the player has not confirmed); part="locations" keeps the saved settings (Codex, #481)."""
            out = {key: var.get() for key, var in self.vars.items()}
            out.update({key: self.location_value(key) for key in paths.KEYS})
            return model.part(out, part)

        def reload_settings(self):
            self.dirty.clear()                         # Reload discards unsaved edits, locations included
            try:
                model.reload()
                alife_model.reload()
                for key, var in self.vars.items():
                    var.set(model.saved[key])
                self.render_locations()
                self.clear_error_banner()
                self.message.set("Reloaded saved settings")
            except (OSError, ValueError) as e:
                self.message.set(str(e))
                self.show_error_banner(format_error_banner(str(e), action="save"))
            self.refresh_start_place_choices()
            self.refresh_play()
            self.refresh_tests()

        def refresh_start_place_choices(self):
            if self.start_place_box is None or "start.mode" not in self.vars or "start.place" not in self.vars:
                return
            mode_val = self.vars["start.mode"].get()
            folder = self.location_value("instance") if "instance" in self.loc else model.saved.get("instance", "")
            sf_dir = folder or (
                self.location_value("starfield") if "starfield" in self.loc else model.saved.get("starfield", "")
            )
            entries = None
            if folder:
                from . import crashwatch, instance
                entries = crashwatch.System(plugins_txt=instance.plugins_txt(folder)).plugin_entries()
            opts = launch_choices.available_place_options(mode_val, starfield_dir=sf_dir, entries=entries)
            self.start_place_box.configure(values=opts)
            if self.vars["start.place"].get() not in opts:
                self.vars["start.place"].set("")

        def refresh_workflow_strip(self, play_reason=""):
            loc_statuses = {k: item["status"] for k, item in self.loc.items()} if self.loc else None
            rows = workflow_steps(
                model.saved,
                loc_statuses=loc_statuses,
                play_reason=play_reason,
                busy_action=self.action if self.busy else "",
            )
            for row in rows:
                w = self.workflow_step_widgets.get(row["key"])
                if w is not None:
                    w["var"].set(row["detail"])
                    w["label"].configure(style=f"Panel.{row['tone']}.TLabel")

        def open_start_cover(self, *, for_play=False, signal_path="", fullscreen=True, expected_nonce=""):
            self.close_start_cover()
            self.cover_crash_reason = ""
            sig = signal_path or start_cover.default_signal_path()
            timeout_s = model.saved.get("start_cover.timeout_s", start_cover.DEFAULT_TIMEOUT_S)
            pids_fn = (lambda: list(self.pids or [])) if for_play else None
            crash_fn = (lambda: self.cover_crash_reason or self.process_error) if for_play else None
            ctrl = start_cover.StartCoverController(
                sig,
                timeout_s=timeout_s,
                expected_nonce=expected_nonce,
                pids_fn=pids_fn,
                crash_fn=crash_fn,
            )
            self.cover_controller = ctrl
            face = pick_font(set(tkfont.families(root)))

            def handle_closed(snap):
                self.cover_window = None
                if snap.get("reason") and not self.closed:
                    self.message.set(f"Start cover closed ({snap['reason']})")

            self.cover_window = start_cover.StartCoverWindow(
                root,
                ctrl,
                palette=palette,
                font_family=face,
                fullscreen=fullscreen,
                on_closed=handle_closed,
            )
            return self.cover_window

        def close_start_cover(self, crash_reason=""):
            if crash_reason and self.cover_controller is not None:
                self.cover_crash_reason = crash_reason
                self.cover_controller.notify_crash(crash_reason)
            if self.cover_window is not None:
                win = self.cover_window
                self.cover_window = None
                win.close()

        def refresh_play(self):
            if not hasattr(self, "play"):
                return
            reason = "A command is still running" if self.busy else self.process_error or model.play_reason(
                self.raw(), self.location_value("starfield"), self.pids)
            self.reason.set(reason)
            play_state = "disabled" if reason else "normal"
            self.play.configure(state=play_state)
            if hasattr(self, "step_play_btn"):
                self.step_play_btn.configure(state=play_state)
            self.refresh_kit_controls()
            self.refresh_header()
            self.refresh_workflow_strip(play_reason=reason)

        def append(self, widget, text):
            widget.configure(state="normal")
            widget.insert("end", text)
            # Bound the window's memory; the underlying commands keep their own full recorded logs.
            lines = int(widget.index("end-1c").split(".")[0])
            if lines > 2000:
                widget.delete("1.0", f"{lines - 2000}.0")
            widget.see("end")
            widget.configure(state="disabled")

        def start(self, action, part="all"):
            if self.busy:
                return
            try:
                argv = model.command(action, self.raw(part), recipe=self.recipe.get(), overrides=overrides,
                                     starfield=self.location_value("starfield"),
                                     fo4_data=paths.split_dirs(self.location_value("fo4_data")),
                                     my_games=self.location_value("my_games"),
                                     pids=None if self.process_error else self.pids)
            except ValueError as e:
                self.message.set(str(e))
                self.show_error_banner(format_error_banner(str(e), action="locations" if part == "locations" else action))
                return
            if argv is None:
                self.clear_error_banner()
                self.message.set("Nothing changed; nothing written")
                return
            if action == "play" and model.saved.get("start_cover"):
                nonce = uuid.uuid4().hex[:16]
                argv = list(argv) + ["--nonce", nonce]
                self.open_start_cover(for_play=True, expected_nonce=nonce)
            self.launch_command(action, argv, part)

        def launch_command(self, action, argv, part="all", *, cwd=None):
            self.busy, self.action, self.part = True, action, part
            self.feedback = CommandFeedback(action)
            self.clear_error_banner()
            for widget, _state in self.widgets:
                widget.configure(state="disabled")
            self.message.set(f"Running {action}…")
            self.refresh_play()
            self.append(self.log, "\n$ " + subprocess.list2cmdline(argv[3:]) + "\n")
            if action in REPORT_ACTIONS:
                self.report.configure(state="normal")
                self.report.delete("1.0", "end")
                self.report.configure(state="disabled")
            def work():
                try:
                    kwargs = {} if cwd is None else {"cwd": cwd}
                    rc = run_command(argv, lambda line: self.events.put(("line", line)), **kwargs)
                    self.events.put(("done", rc))
                except Exception as e:
                    self.events.put(("error", str(e)))
            threading.Thread(target=work, daemon=True).start()

        def drain(self):
            if self.closed:
                return
            while True:
                try:
                    kind, value = self.events.get_nowait()
                except queue.Empty:
                    break
                if kind == "processes":
                    self.pids, self.process_error = value, ""
                elif kind == "process_error":
                    self.pids, self.process_error = None, "Cannot check game processes: " + value
                    self.close_start_cover(self.process_error)
                    self.show_error_banner(format_error_banner(self.process_error, action="process"))
                elif kind in ("found", "found_error"):
                    if kind == "found":
                        self.found = dict(value, **given)
                    self.render_locations()
                    waiting = [s for s in (self.loc[k]["status"] for k in paths.KEYS) if s != "saved"]
                    if any(self.loc[k]["status"] != "saved" for k in paths.needed(model.saved)):
                        self.notebook.select(self.places_tab)
                        self.message.set("Check the locations the launcher found, then press Confirm locations.")
                    elif waiting:
                        self.message.set("Ready. Some optional locations wait on the Locations tab.")
                    else:
                        self.message.set("Ready.")
                elif kind == "kits":
                    generation, rows, error = value
                    if generation == self.kit_generation and not self.busy:
                        self.render_kits(rows, error)
                elif kind == "line":
                    self.feedback.observe(value)
                    self.append(self.log, value)
                    if self.action in REPORT_ACTIONS:
                        self.append(self.report, value)
                    if self.action.startswith("alife-"):
                        alife_session.observe(value)
                        self.alife_metrics_var.set(alife_session.key_numbers()["summary"])
                else:
                    self.busy = False
                    for widget, state in self.widgets:
                        widget.configure(state=state)
                    if self.action.startswith("alife-"):
                        done = alife_session.finish(
                            value if kind == "done" else 1,
                            transport_error="" if kind == "done" else str(value),
                        )
                        self.render_alife_state()
                        if done["status"] == "passed":
                            self.clear_error_banner()
                            label = alife_tools.STEP_LABELS.get(done["step"], done["step"])
                            self.message.set(f"Mod tools: {label} passed ({alife_session.progress_text()})")
                        else:
                            self.message.set(done["error"])
                            self.show_error_banner(alife_session.last_error)
                    else:
                        if self.action == "play":
                            if kind == "error" or value != 0:
                                self.close_start_cover(f"Play stopped (exit {value})")
                            else:
                                self.close_start_cover()
                        self.message.set(self.feedback.finished(value) if kind == "done" else value)
                        if kind == "error":
                            self.show_error_banner(format_error_banner(value, action=self.action))
                        elif kind == "done" and value != 0:
                            self.show_error_banner(
                                format_error_banner(self.feedback.error_detail(value), action=self.action, exit_code=value)
                            )
                        else:
                            self.clear_error_banner()
                        if kind == "done" and value == 0 and self.action == "update":
                            self.message.set("Update finished: close and open the window again to use a new version.")
                        if kind == "done" and value == 0 and self.action == "save":
                            if self.part == "locations":   # confirmed: the command-line paths have had their say
                                given.clear()
                                self.dirty.clear()
                            try:
                                model.reload()
                                alife_model.reload()
                                for key, var in self.vars.items():
                                    var.set(model.saved[key])
                                self.render_locations()
                                self.message.set("Saved.")
                            except (OSError, ValueError) as e:
                                self.message.set(str(e))
                                self.show_error_banner(format_error_banner(str(e), action="save"))
                self.refresh_play()
                if kind in ("done", "error"):
                    self.refresh_tests()
            root.after(75, self.drain)

        def poll_processes(self):
            if self.closed:
                return
            def read():
                try:
                    from .crashwatch import System
                    self.events.put(("processes", System().pids()))
                except Exception as e:
                    self.events.put(("process_error", str(e)))
            threading.Thread(target=read, daemon=True).start()
            root.after(3000, self.poll_processes)

        def open_logs(self):
            folder = model.saved["crash_watch.folder"]
            if not folder or not os.path.isdir(folder):
                msg = "Confirm an existing dump folder on the Locations tab first"
                self.message.set(msg)
                self.show_error_banner(format_error_banner(msg, action="logs"))
                return
            try:
                if os.name == "nt":
                    os.startfile(folder)
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
            except OSError as e:
                self.message.set(str(e))
                self.show_error_banner(format_error_banner(str(e), action="logs"))

        def close(self):
            if self.busy:
                messagebox.showinfo("A command is still running", "Keep this window open until the command "
                                    "finishes. Play follows the game and crash watcher until they finish.")
                return
            self.closed = True
            self.close_start_cover()
            root.destroy()

    Window()
    root.mainloop()
    return 0
