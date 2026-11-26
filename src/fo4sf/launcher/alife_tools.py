"""Headless model and output parser for the launcher's A-Life Mod tools tab.

Pure Python standard library; importing this module requires no display or tkinter.
All SDK actions delegate to scripts/alife/build_alife_mod.py via argv lists (no shell).
"""
import os
import re
import sys

from . import settings

STEPS = ("init", "validate", "simulate", "package", "verify-dist")
STEP_LABELS = {
    "init": "Init",
    "validate": "Validate",
    "simulate": "Simulate",
    "package": "Package",
    "verify-dist": "Verify dist",
}
TEMPLATES = ("vanilla", "custom")
ARRAY_CAP = 128

STEP_MARKS = {
    "not_run": ("○ not run", "muted"),
    "running": ("◐ running", "warn"),
    "passed": ("✓ passed", "ok"),
    "failed": ("✗ failed", "bad"),
}

GAME_EXES = {
    "starfield.exe",
    "fallout4.exe",
    "skyrimse.exe",
    "fallout76.exe",
    "skyrim.exe",
    "oblivion.exe",
}
GAME_PATH_PARTS = {"steamapps", "xboxgames", "windowsapps"}

_BORDER_RE = re.compile(r"^\+(?:-+\+)+$")
_REFUSED_RE = re.compile(r"^[a-z0-9_-]+\s+refused:\s*(.+)$", re.IGNORECASE)
_NODES_RATIO_RE = re.compile(r"^(\d+/\d+)\b")
_NODES_COUNT_RE = re.compile(r"\b(\d+)\s+nodes\b")
_PROBLEM_SUMMARY_RE = re.compile(r"^(validate|verify-dist):\s*\d+\s+problem", re.IGNORECASE)
_TRACEBACK_FRAME_RE = re.compile(r'^File\s+".+",\s+line\s+\d+')


def progress(statuses):
    """Return (passed_count, total_steps) for the 5-step A-Life workflow (0..5)."""
    done = sum(1 for step in STEPS if statuses.get(step) == "passed")
    return done, len(STEPS)


def progress_text(statuses):
    done, total = progress(statuses)
    return f"{done}/{total} steps passed"


def config_path(output_dir):
    return os.path.join(os.path.abspath(output_dir), "alife_config.json")


def dist_dir(output_dir):
    return os.path.join(os.path.abspath(output_dir), "dist")


def path_basename(path):
    """Cross-OS file name of a Windows drive, UNC, POSIX, or mixed-separator path string."""
    s = str(path or "").rstrip("\\/")
    if not s:
        return ""
    m_unc = re.match(r"^(?:\\\\|//)[^\\/]+[\\/][^\\/]+(.*)$", s)
    if m_unc is not None:
        s = m_unc.group(1).lstrip("\\/")
        return re.split(r"[\\/]+", s)[-1] if s else ""
    if len(s) >= 2 and s[0].isascii() and s[0].isalpha() and s[1] == ":":
        s = s[2:].lstrip("\\/")
        return re.split(r"[\\/]+", s)[-1] if s else ""
    s = s.lstrip("\\/")
    return re.split(r"[\\/]+", s)[-1] if s else ""


_WIN_ABS_OR_UNC_RE = re.compile(r"^(?:(?:\\\\|//)[^\\/]+[\\/][^\\/]+|[A-Za-z]:(?:[\\/]|$))")


def _is_foreign_os_abs(path):
    """Return True when `path` uses another OS's root syntax so os.path.abspath would mis-anchor it to CWD."""
    s = str(path or "").strip()
    if not s:
        return False
    if os.name != "nt":
        return bool(_WIN_ABS_OR_UNC_RE.match(s))
    return s.startswith("/") and not s.startswith("//")


def _collapse_parts(raw_parts, *, anchored):
    stack = []
    for part in raw_parts:
        if not part or part == ".":
            continue
        if part == "..":
            if stack and stack[-1] != "..":
                stack.pop()
            elif not anchored:
                stack.append("..")
        else:
            stack.append(part)
    return tuple(stack)


def _split_foreign_root(path):
    """Return (kind_and_root, parts) splitting on both / and \\ for cross-OS containment and segment checks."""
    s = str(path or "").strip().rstrip("\\/")
    if not s:
        return ("", ())
    m_unc = re.match(r"^(?:\\\\|//)([^\\/]+)[\\/]([^\\/]+)(.*)$", s)
    if m_unc is not None:
        root = f"unc://{m_unc.group(1).lower()}/{m_unc.group(2).lower()}"
        tail = m_unc.group(3).lstrip("\\/")
        parts = _collapse_parts(re.split(r"[\\/]+", tail), anchored=True) if tail else ()
        return (root, parts)
    if len(s) >= 2 and s[0].isascii() and s[0].isalpha() and s[1] == ":":
        root = f"drive:{s[0].lower()}"
        tail = s[2:].lstrip("\\/")
        parts = _collapse_parts(re.split(r"[\\/]+", tail), anchored=True) if tail else ()
        return (root, parts)
    if s.startswith(("/", "\\")):
        tail = s.lstrip("\\/")
        parts = _collapse_parts(re.split(r"[\\/]+", tail), anchored=True) if tail else ()
        return ("/", parts)
    parts = _collapse_parts(re.split(r"[\\/]+", s), anchored=False)
    return ("rel", parts)


def path_parts(path):
    """Non-root path segments of `path`, splitting on both / and \\ on every OS."""
    return _split_foreign_root(path)[1]


def _cross_os_inside(path, root):
    p_root, p_parts = _split_foreign_root(path)
    r_root, r_parts = _split_foreign_root(root)
    if not p_root or not r_root or p_root == "rel" or p_root != r_root:
        return False
    if len(p_parts) < len(r_parts):
        return False
    if p_root.startswith(("drive:", "unc://")):
        return [x.lower() for x in p_parts[:len(r_parts)]] == [x.lower() for x in r_parts]
    return p_parts[:len(r_parts)] == r_parts


def _ancestors(path):
    if _is_foreign_os_abs(path):
        return []
    p = os.path.abspath(path)
    out = [p]
    while True:
        parent = os.path.dirname(p)
        if parent == p:
            return out
        out.append(parent)
        p = parent


def _inside(path, root):
    if not path or not root:
        return False
    if _cross_os_inside(path, root):
        return True
    if _is_foreign_os_abs(path) or _is_foreign_os_abs(root):
        return False
    try:
        p = os.path.normcase(os.path.realpath(path))
        r = os.path.normcase(os.path.realpath(root))
        return os.path.commonpath([p, r]) == r
    except ValueError:
        return False


def git_root_of(path):
    """Return the nearest ancestor containing a .git directory or worktree .git file, or None."""
    for anc in _ancestors(path):
        if os.path.exists(os.path.join(anc, ".git")):
            return anc
    return None


def game_root_of(path, starfield_dir="", extra_game_dirs=()):
    """Return the game installation folder enclosing `path`, or None."""
    for candidate in (starfield_dir, *extra_game_dirs):
        if candidate and _inside(path, candidate):
            if _is_foreign_os_abs(path) or _is_foreign_os_abs(candidate):
                return str(candidate)
            return os.path.abspath(candidate)
    if any(seg.lower() in GAME_PATH_PARTS for seg in path_parts(path)):
        return str(path)
    for anc in _ancestors(path):
        if path_basename(anc).lower() in GAME_PATH_PARTS:
            return anc
        if os.path.isdir(anc):
            try:
                names = {name.lower() for name in os.listdir(anc)}
            except OSError:
                continue
            if names & GAME_EXES or os.path.isfile(os.path.join(anc, "Data", "Starfield.esm")):
                return anc
    return None


def validate_output_dir(output_dir, *, starfield_dir="", repo_dir="", extra_game_dirs=()):
    """Return '' when `output_dir` is safe, or a human-readable refusal reason."""
    text = str(output_dir or "").strip()
    if not text:
        return "Choose an output folder outside this repository and outside the Starfield game folder."
    out = text if _is_foreign_os_abs(text) else os.path.abspath(text)
    if git_root_of(out):
        return "Output folder cannot be inside a Git checkout; choose a folder outside any repository."
    if repo_dir and _inside(out, repo_dir):
        return "Output folder cannot be inside this repository; choose a folder outside the checkout."
    if game_root_of(out, starfield_dir=starfield_dir, extra_game_dirs=extra_game_dirs):
        return "Output folder cannot be inside the Starfield or game installation folder; choose a separate folder."
    return ""


def _parse_int(value, name, *, minimum=None):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a whole number.")
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number.") from None
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return parsed


class ModToolsModel:
    """Headless argv builder and guard model for scripts/alife/build_alife_mod.py."""

    def __init__(self, launcher_path, settings_path, sdk_script=None):
        self.launcher = os.path.abspath(launcher_path)
        self.settings_path = os.path.abspath(settings_path)
        self.repo_dir = os.path.dirname(os.path.dirname(self.launcher))
        if sdk_script:
            self.sdk_script = os.path.abspath(sdk_script)
        else:
            self.sdk_script = os.path.join(self.repo_dir, "scripts", "alife", "build_alife_mod.py")
        self.reload()

    def reload(self):
        self.saved = settings.load(self.settings_path)
        return self.saved

    def _current_saved(self):
        try:
            return settings.load(self.settings_path)
        except OSError:
            return dict(self.saved)

    def saved_starfield_dir(self):
        cur = self._current_saved()
        return cur.get("instance") or cur.get("starfield") or ""

    def config_path(self, output_dir):
        return config_path(output_dir)

    def dist_dir(self, output_dir):
        return dist_dir(output_dir)

    def validate_output_dir(self, output_dir, *, starfield_dir="", repo_dir=""):
        cur = self._current_saved()
        effective_sf = (starfield_dir or "").strip() or cur.get("instance") or cur.get("starfield") or ""
        return validate_output_dir(
            output_dir,
            starfield_dir=effective_sf,
            repo_dir=repo_dir or self.repo_dir,
            extra_game_dirs=(cur.get("instance", ""), cur.get("starfield", "")),
        )

    def can_open_output_dir(self, output_dir):
        text = str(output_dir or "").strip()
        if not text:
            return False, "Choose an output folder first."
        target = os.path.abspath(text)
        if not os.path.isdir(target):
            return False, "Output folder does not exist yet; run Init first."
        return True, target

    def command(self, step, *, output_dir, template="vanilla", ticks=20, seed=42,
                starfield_dir="", pack_ba2=False, force=False):
        if step not in STEPS:
            raise ValueError(f"Unknown A-Life step: {step!r}.")
        if not os.path.isfile(self.sdk_script):
            raise ValueError("A-Life SDK script scripts/alife/build_alife_mod.py was not found in this checkout.")
        cur = self._current_saved()
        effective_sf = (starfield_dir or "").strip() or cur.get("instance") or cur.get("starfield") or ""
        problem = self.validate_output_dir(output_dir, starfield_dir=effective_sf)
        if problem:
            raise ValueError(problem)

        cfg = self.config_path(output_dir)
        dist = self.dist_dir(output_dir)
        argv = [sys.executable, "-I", "-u", self.sdk_script]

        if step == "init":
            if template not in TEMPLATES:
                raise ValueError("Template must be 'vanilla' or 'custom'.")
            cmd = argv + ["init", "--out", cfg, "--template", template]
            if force:
                cmd.append("--force")
            return cmd

        if step == "validate":
            return argv + ["validate", "--config", cfg]

        if step == "simulate":
            ticks_i = _parse_int(ticks, "Ticks", minimum=1)
            seed_i = _parse_int(seed, "Seed")
            return argv + ["simulate", "--config", cfg, "--ticks", str(ticks_i), "--seed", str(seed_i)]

        if step == "package":
            if not effective_sf:
                raise ValueError("Confirm the Starfield folder on the Locations tab before packaging.")
            cmd = argv + ["package", "--config", cfg, "--out", dist, "--starfield-dir", os.path.abspath(effective_sf)]
            if pack_ba2:
                cmd.append("--pack-ba2")
            return cmd

        if step == "verify-dist":
            return argv + ["verify-dist", "--dist-dir", dist]

        raise ValueError(f"Unknown A-Life step: {step!r}.")


class StepRunParser:
    """Stream parser for build_alife_mod.py output: key numbers, simulate table, and readable errors."""

    def __init__(self, step):
        self.step = step
        self.metrics = {}
        self.tables = []
        self.summary_table = ([], [])
        self.faction_table = ([], [])
        self.table_columns = []
        self.table_rows = []
        self._state = "idle"
        self._headers = []
        self._rows = []
        self._refused = ""
        self._fails = []
        self._problem_summary = ""
        self._traceback_seen = False
        self._traceback_exc = ""
        self._last_clean_line = ""

    def _flush_table(self):
        if not self._headers:
            return
        cols = list(self._headers)
        rows = [list(r) for r in self._rows]
        self.tables.append({"columns": cols, "rows": rows})
        lower_cols = [c.lower() for c in cols]
        if lower_cols[:2] == ["metric", "value"]:
            self.summary_table = (cols, rows)
        elif lower_cols and lower_cols[0] == "faction":
            self.faction_table = (cols, rows)
        if self.faction_table[0]:
            self.table_columns, self.table_rows = self.faction_table
        elif self.summary_table[0]:
            self.table_columns, self.table_rows = self.summary_table
        else:
            self.table_columns, self.table_rows = cols, rows
        self._headers = []
        self._rows = []

    def _consume_row_metrics(self, cells):
        if len(cells) < 2:
            return
        key = cells[0].strip().lower()
        val = cells[1].strip()
        if key == "nodes":
            m = _NODES_RATIO_RE.match(val)
            if m:
                self.metrics["nodes"] = m.group(1)
        elif key == "squads spawned":
            self.metrics["spawns"] = val
        elif key == "offline battles":
            self.metrics["battles"] = val
        elif key == "territory captures":
            self.metrics["captures"] = val

    def observe(self, line):
        raw = str(line or "").rstrip("\r\n")
        s = raw.strip()
        if not s:
            if self._state == "in_rows":
                self._flush_table()
                self._state = "idle"
            return

        # Error / diagnostic capture (avoid raw traceback frames in banners).
        if s == "Traceback (most recent call last):":
            self._traceback_seen = True
            return
        if self._traceback_seen:
            if raw.startswith("  ") or _TRACEBACK_FRAME_RE.match(s):
                return
            self._traceback_exc = s
            return

        refused_m = _REFUSED_RE.match(s)
        if refused_m:
            self._refused = refused_m.group(1).strip()
        elif s.startswith("FAIL "):
            detail = s[5:].strip()
            if detail:
                self._fails.append(detail)
        elif _PROBLEM_SUMMARY_RE.match(s):
            self._problem_summary = s
        elif not _BORDER_RE.match(s) and not (s.startswith("|") and s.endswith("|")):
            self._last_clean_line = s

        # Node count extraction from init / simulate header lines.
        if "nodes" not in self.metrics and not s.startswith("|"):
            m = _NODES_COUNT_RE.search(s)
            if m:
                self.metrics["nodes"] = f"{m.group(1)}/{ARRAY_CAP}"

        # ASCII table parsing.
        is_border = bool(_BORDER_RE.match(s))
        is_row = s.startswith("|") and s.endswith("|") and len(s) >= 2
        if is_border:
            if self._state == "idle":
                self._state = "await_header"
            elif self._state == "await_header_sep":
                self._rows = []
                self._state = "in_rows"
            elif self._state == "in_rows":
                self._flush_table()
                self._state = "idle"
            return

        if is_row:
            cells = [c.strip() for c in s[1:-1].split("|")]
            if self._state == "await_header":
                self._headers = cells
                self._state = "await_header_sep"
            elif self._state == "in_rows":
                self._rows.append(cells)
                self._consume_row_metrics(cells)
            else:
                self._consume_row_metrics(cells)
            return

        if self._state == "in_rows":
            self._flush_table()
        self._state = "idle"

    def error_banner(self, exit_code):
        if exit_code == 0:
            return ""
        label = STEP_LABELS.get(self.step, self.step)
        if self._refused:
            return f"{label} refused: {self._refused}"
        if self._fails:
            head = "; ".join(self._fails[:2])
            extra = f" (+{len(self._fails) - 2} more)" if len(self._fails) > 2 else ""
            return f"{label} failed: {head}{extra}"
        if self._problem_summary:
            return f"{label} failed: {self._problem_summary}"
        if self._traceback_seen:
            if self._traceback_exc:
                return f"{label} stopped unexpectedly: {self._traceback_exc}. Open the Log tab for details."
            return f"{label} stopped unexpectedly (exit {exit_code}). Open the Log tab for details."
        if self._last_clean_line:
            return f"{label} failed (exit {exit_code}): {self._last_clean_line}"
        return f"{label} failed (exit {exit_code}). Open the Log tab for details."

    def finished(self, exit_code):
        if self._state == "in_rows":
            self._flush_table()
            self._state = "idle"
        return {
            "step": self.step,
            "status": "passed" if exit_code == 0 else "failed",
            "metrics": dict(self.metrics),
            "table_columns": list(self.table_columns),
            "table_rows": [list(r) for r in self.table_rows],
            "error": self.error_banner(exit_code),
        }
