"""Aggregate Papyrus, SFSE, and crash/process logs from a soak run into one phone-sized report.

Reads three log families without touching or modifying game files:
  1. Crash & session health (.dmp minidumps, driver/monitor/crashwatch process exits, sfse_loader).
  2. SFSE runtime & plugin logs (sfse.txt/sfse.log, FO4SFPipboyMenu.log, FO4SFCombat.log, etc.).
  3. Papyrus VM & slice user logs (Papyrus.0.log + Logs/Script/User/*.log).
"""

from __future__ import annotations

import datetime
import os
import re
import struct
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from ..core.loadset import OUR_PREFIXES
except ImportError:  # pragma: no cover - direct script import fallback
    OUR_PREFIXES = ("FO4", "FOCC", "FOSF", "FO3SF", "FNVSF")

PHONE_MAX_WIDTH = 56
PHONE_MAX_LINES = 40
DEFAULT_STALL_SECONDS = 300.0

_OURS_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:" + "|".join(map(re.escape, OUR_PREFIXES)) + r")[A-Za-z0-9_]*",
    re.IGNORECASE,
)
_PAPYRUS_LINE_RE = re.compile(r"^\[(?P<time>[^\]]{1,40})\]\s*(?P<text>.*)$")
_CLOCK_RE = re.compile(r"(?:^|\s)(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?\s*(AM|PM)?$", re.IGNORECASE)
_SFSE_LINE_RE = re.compile(r"^\[(?P<time>\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s*\[[^\]]+\]\s*\[(?P<lvl>[A-Z])\]\s*(?P<body>.*)$")
_ISO_LINE_RE = re.compile(
    r"^\[?(?P<iso>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?(?:\s+|$)(?P<body>.*)$"
)
_CLOCK_LINE_RE = re.compile(r"^\[?(?P<clock>\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]?\s+(?P<body>.*)$")
_WATCH_UP_RE = re.compile(r"\bafter\s+(?P<up>\d+(?:\.\d+)?)\s*s\s+up\b", re.IGNORECASE)
_ROTATED_LOG_RE = re.compile(r"^(?P<stem>.+?)\.(?P<idx>\d+)\.log$", re.IGNORECASE)
_RT_RE = re.compile(r"\brt=(?P<rt>-?\d+(?:\.\d+)?)")
_HOLD_PASS_RE = re.compile(r"\bhold-off pass\s+(?P<pass>\d+)\s+stopped=(?P<stopped>\d+)\s+of\s+(?P<total>\d+)", re.IGNORECASE)
_HELD_OFF_RE = re.compile(
    r"\bheld off\s+(?P<quest>.+?)\s+running_after=(?P<running>true|false)(?:\s+pass=(?P<pass>\d+))?",
    re.IGNORECASE,
)
_QUEST_BRACKET_RE = re.compile(r"<\s*(?P<edid>[A-Za-z0-9_]+)\s*\([0-9A-Fa-f]+\)\s*>|\[(?P<bare>[A-Za-z0-9_]+)\s*\([0-9A-Fa-f]+\)\]")
_STAGE_EVENT_RE = re.compile(r"(?:\bstage\s+(?P<s1>\d+)\b|\bstage=(?P<s2>\d+)\b)", re.IGNORECASE)
_ALIFE_WP_RE = re.compile(r"\bstep=rung1a_progress\b.*?\bwp=(?P<wp>\d+)/(?P<total>\d+)", re.IGNORECASE)
_ALIFE_STUCK_RE = re.compile(r"\bstep=rung1a_stuck\b.*?\bstill_s=(?P<still>\d+(?:\.\d+)?)", re.IGNORECASE)
_ALIFE_SUMMARY_RE = re.compile(r"\bstep=summary\s+rung=(?P<rung>1a|1b)\s+result=(?P<res>PASS|FAIL)", re.IGNORECASE)
_REFUSE_STEP_RE = re.compile(r"\brefuse\s+step=(?P<step>[A-Za-z0-9_.-]+)", re.IGNORECASE)
_FAULT_RE = re.compile(r"(?:\bstep=fault\b|\bfault\b)", re.IGNORECASE)
_STARMAP_BLOCKED_RE = re.compile(r"\bstarmap_blocked(?:=(?P<count>\d+))?\b", re.IGNORECASE)
_SFSE_LOADED_DLL_RE = re.compile(r"^\s*plugin\s+(?P<dll>[A-Za-z0-9_.-]+\.dll)\b.*?\bloaded correctly\b", re.IGNORECASE)
_CANNOT_OPEN_STORE_RE = re.compile(r'Cannot open store for class "(?P<cls>[^"]+)"', re.IGNORECASE)
_ASSIGN_NONE_RE = re.compile(r"\bAssigning None to a non-object variable\b", re.IGNORECASE)
_STACK_DUMP_RE = re.compile(r"(?:\bdumping stacks?\b|\bstack dumps?\b|\bsuspended stacks?\s+(?:count\s+)?is\s+over\b)", re.IGNORECASE)
_VM_OVERLOAD_RE = re.compile(
    r"(?:\bvm is overstressed\b|\boverstressed\b|\bsuspended stack\b|\bstack count\b|\bbudget exceeded\b)",
    re.IGNORECASE,
)

DEFAULT_SESSION_WINDOW_HOURS = 12.0

# Vanilla Starfield quests that FO4SF_NewGame holds off; runtime noise from them indicates unheld leakage.
_VANILLA_HELD_PREFIXES = (
    "mq00",
    "mq101",
    "mq_tutorialquest",
    "sq_env",
    "com_companion_sarah",
    "com_companion_barrett",
    "com_companion_andreja",
    "com_companion_samcoe",
)

_TERMINAL_STAGES = {
    "FO4SF_NewGame": {1, 200},
    "FO4SF_Min00": {200},
    "FO4SF_ALife": {200},
}

_EXCEPTION_NAMES = {
    0xC0000005: "ACCESS_VIOLATION",
    0x80000003: "BREAKPOINT",
    0xC0000409: "STACK_BUFFER_OVERRUN",
    0xC00000FD: "STACK_OVERFLOW",
    0xC0000374: "HEAP_CORRUPTION",
    0xC000001D: "ILLEGAL_INSTRUCTION",
}


def _read_lines(path: str) -> List[str]:
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        return [ln.replace("\x00", "").rstrip("\r\n") for ln in handle]


def _parse_iso_epoch(raw_iso: str) -> Optional[float]:
    s = raw_iso.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def _parse_clock_seconds(token: str) -> Optional[float]:
    match = _CLOCK_RE.search(token.strip())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3))
    frac_str = match.group(4) or ""
    ampm = (match.group(5) or "").upper()
    if ampm == "PM" and hour < 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    frac = int(frac_str) / (10 ** len(frac_str)) if frac_str else 0.0
    return hour * 3600.0 + minute * 60.0 + second + frac


def _clock_span(times: Sequence[float]) -> float:
    if len(times) < 2:
        return 0.0
    total = 0.0
    prev = times[0]
    for cur in times[1:]:
        diff = cur - prev
        if diff < -3600.0:  # midnight wrap
            diff += 86400.0
        if diff > 0.0:
            total += diff
        prev = cur
    return total


def _has_ours(text: str, frames: Iterable[str] = ()) -> bool:
    if _OURS_RE.search(text):
        return True
    return any(_OURS_RE.search(frame) for frame in frames)


def _clean_quest_label(raw: str) -> str:
    match = _QUEST_BRACKET_RE.search(raw)
    if match:
        return match.group("edid") or match.group("bare") or raw.strip()
    cleaned = raw.strip().strip("[]<>")
    return cleaned.split()[0] if cleaned else "unknown"


def _select_log_files(folder: str, *, include_rotated: bool, stem_filter=None) -> Tuple[List[Tuple[str, str]], int]:
    """Return [(stem, filepath)] ordered oldest-to-newest per stem, plus count of .1 fallback selections."""
    if not folder or not os.path.isdir(folder):
        return [], 0
    grouped: Dict[str, Dict[Optional[int], str]] = {}
    for entry in sorted(os.listdir(folder)):
        full = os.path.join(folder, entry)
        if not os.path.isfile(full) or not entry.lower().endswith(".log"):
            continue
        m = _ROTATED_LOG_RE.match(entry)
        if m:
            stem = m.group("stem")
            idx: Optional[int] = int(m.group("idx"))
        else:
            stem = entry[:-4]
            idx = None
        if stem_filter and not stem_filter(stem):
            continue
        grouped.setdefault(stem.casefold(), {})[idx] = (stem, full)

    selected: List[Tuple[str, str]] = []
    fallbacks = 0
    for _key in sorted(grouped):
        variants = grouped[_key]
        if include_rotated:
            if 1 in variants:
                selected.append(variants[1])
            if 0 in variants:
                selected.append(variants[0])
            elif None in variants and 1 not in variants:
                selected.append(variants[None])
        else:
            if 0 in variants:
                selected.append(variants[0])
            elif 1 in variants:
                selected.append(variants[1])
                fallbacks += 1
            elif None in variants:
                selected.append(variants[None])
    return selected, fallbacks


def _resolve_layout(
    log_dir: Optional[str],
    sfse_log_dir: Optional[str],
    crash_dir: Optional[str],
    driver_log: Optional[str],
) -> dict:
    missing_dirs: List[str] = []
    script_dirs: List[str] = []
    user_dirs: List[str] = []
    sfse_dirs: List[str] = []
    crash_dirs: List[str] = []
    driver_logs: List[str] = []

    if log_dir:
        if not os.path.exists(log_dir):
            missing_dirs.append("log_dir")
        elif os.path.isdir(log_dir):
            # Support <My Games>/Starfield, <My Games>/Starfield/Logs, <My Games>/Starfield/Logs/Script, or flat dir.
            cand_script = [
                os.path.join(log_dir, "Logs", "Script"),
                os.path.join(log_dir, "Script"),
                log_dir,
            ]
            for c in cand_script:
                if os.path.isdir(c) and c not in script_dirs:
                    script_dirs.append(c)
            cand_user = [
                os.path.join(log_dir, "Logs", "Script", "User"),
                os.path.join(log_dir, "Script", "User"),
                os.path.join(log_dir, "User"),
                log_dir,
            ]
            for c in cand_user:
                if os.path.isdir(c) and c not in user_dirs:
                    user_dirs.append(c)

            if sfse_log_dir is None:
                for c in (
                    os.path.join(log_dir, "SFSE", "Logs"),
                    os.path.join(log_dir, "SFSE"),
                ):
                    if os.path.isdir(c) and c not in sfse_dirs:
                        sfse_dirs.append(c)
                if not sfse_dirs and os.path.basename(os.path.normpath(log_dir)).lower() == "logs":
                    parent_sfse = os.path.join(os.path.dirname(os.path.normpath(log_dir)), "SFSE", "Logs")
                    if os.path.isdir(parent_sfse):
                        sfse_dirs.append(parent_sfse)

            if crash_dir is None:
                crash_dirs.append(log_dir)

            if driver_log is None:
                for name in ("driver.log", "monitor.log", "crashwatch.log"):
                    p = os.path.join(log_dir, name)
                    if os.path.isfile(p):
                        driver_logs.append(p)

    if sfse_log_dir:
        if os.path.isdir(sfse_log_dir):
            sfse_dirs.append(sfse_log_dir)
        else:
            missing_dirs.append("sfse_log_dir")

    if crash_dir:
        if os.path.isdir(crash_dir):
            if crash_dir not in crash_dirs:
                crash_dirs.insert(0, crash_dir)
            if driver_log is None:
                for name in ("crashwatch.log", "driver.log", "monitor.log"):
                    p = os.path.join(crash_dir, name)
                    if os.path.isfile(p) and p not in driver_logs:
                        driver_logs.append(p)
        else:
            missing_dirs.append("crash_dir")

    if driver_log:
        if os.path.isfile(driver_log):
            driver_logs.insert(0, driver_log)
        else:
            missing_dirs.append("driver_log")

    return {
        "missing_dirs": missing_dirs,
        "script_dirs": script_dirs,
        "user_dirs": user_dirs,
        "sfse_dirs": sfse_dirs,
        "crash_dirs": crash_dirs,
        "driver_logs": driver_logs,
    }


def _is_fresh(path: str, min_mtime: Optional[float]) -> bool:
    if min_mtime is None:
        return True
    try:
        return os.path.getmtime(path) >= min_mtime
    except OSError:
        return True


def _compute_session_bounds(
    layout: dict, session_window_hours: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    newest = 0.0
    # Prefer Papyrus.0.log / Papyrus.1.log or sfse.txt as session time anchors, falling back to any log file.
    anchor_candidates: List[str] = []
    other_candidates: List[str] = []
    for d in layout["script_dirs"] + layout["user_dirs"] + layout["sfse_dirs"]:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            low = fn.lower()
            if not (low.endswith(".log") or (low.startswith("sfse") and low.endswith(".txt"))):
                continue
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                other_candidates.append(p)
                if low in ("papyrus.0.log", "papyrus.1.log", "sfse.txt", "sfse.log"):
                    anchor_candidates.append(p)
    pool = anchor_candidates or other_candidates
    for p in pool:
        try:
            newest = max(newest, os.path.getmtime(p))
        except OSError:
            continue
    if newest <= 0.0:
        for p in layout["driver_logs"]:
            if not os.path.isfile(p):
                continue
            for ln in _read_lines(p):
                m_iso = _ISO_LINE_RE.match(ln)
                if m_iso:
                    ts = _parse_iso_epoch(m_iso.group("iso"))
                    if ts is not None:
                        newest = max(newest, ts)
            if newest <= 0.0:
                try:
                    newest = max(newest, os.path.getmtime(p))
                except OSError:
                    continue
    anchor_ts = newest if newest > 0.0 else None
    if session_window_hours is None or session_window_hours <= 0 or anchor_ts is None:
        return None, anchor_ts
    return anchor_ts - session_window_hours * 3600.0, anchor_ts


def _inspect_minidump_exception(path: str) -> Optional[str]:
    """Read exception code from an MDMP header when present; never fail on synthetic or partial dumps."""
    try:
        with open(path, "rb") as f:
            data = f.read(4096)
        if len(data) < 32 or data[:4] != b"MDMP":
            return None
        count, rva = struct.unpack_from("<II", data, 8)
        if count > 128 or rva + count * 12 > len(data):
            return None
        for i in range(count):
            kind, _size, at = struct.unpack_from("<III", data, rva + 12 * i)
            if kind == 6 and at + 12 <= len(data):  # ExceptionStream
                code, = struct.unpack_from("<I", data, at + 8)
                name = _EXCEPTION_NAMES.get(code)
                return f"0x{code:08X}" + (f" {name}" if name else "")
    except OSError:
        return None
    return None


def _parse_crashes_and_exits(
    crash_dirs: Sequence[str],
    driver_logs: Sequence[str],
    sfse_dirs: Sequence[str],
    *,
    min_mtime: Optional[float] = None,
    anchor_ts: Optional[float] = None,
) -> dict:
    seen_dumps = set()
    dumps = []
    stale_skipped = 0
    stale_lines_skipped = 0
    for folder in crash_dirs:
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if not fn.lower().endswith(".dmp"):
                continue
            full = os.path.normcase(os.path.abspath(os.path.join(folder, fn)))
            if full in seen_dumps:
                continue
            seen_dumps.add(full)
            real = os.path.join(folder, fn)
            if not _is_fresh(real, min_mtime):
                stale_skipped += 1
                continue
            try:
                st = os.stat(real)
                ts = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                size = st.st_size
            except OSError:
                ts, size = "", 0
            exc = _inspect_minidump_exception(real)
            dumps.append({"name": fn, "timestamp": ts, "size": size, "exception": exc})

    clean_exits = 0
    unexpected_exits = 0
    exit_notes: List[str] = []
    logs_read = 0
    watch_runs: List[Tuple[float, float]] = []  # [(end_ts, duration_s)]

    for path in driver_logs:
        if not os.path.isfile(path):
            continue
        raw_lines = _read_lines(path)
        has_iso = any(_ISO_LINE_RE.match(ln) for ln in raw_lines if ln.strip())
        if not has_iso:
            if not _is_fresh(path, min_mtime):
                stale_skipped += 1
                continue

        base = os.path.basename(path)
        cur_ts: Optional[float] = None
        cur_clock_s: Optional[float] = None
        active_start_ts: Optional[float] = None
        active_clock_start: Optional[float] = None
        forced_stop_pending = False
        kept_in_file = 0
        skipped_in_file = 0

        for line in raw_lines:
            if not line.strip():
                continue
            # Folded ProcDump stdout/stderr lines (`  procdump: ...`) summarize already-recorded `ended:` runs.
            if line[:1].isspace() and line.lstrip().lower().startswith("procdump:"):
                continue

            m_iso = _ISO_LINE_RE.match(line)
            if m_iso:
                cur_ts = _parse_iso_epoch(m_iso.group("iso"))
                cur_clock_s = None
                body = m_iso.group("body")
            else:
                m_clk = _CLOCK_LINE_RE.match(line)
                if m_clk:
                    cur_clock_s = _parse_clock_seconds(m_clk.group("clock"))
                    body = m_clk.group("body")
                else:
                    body = line

            if has_iso and min_mtime is not None:
                if cur_ts is None or cur_ts < min_mtime or (anchor_ts is not None and cur_ts > anchor_ts + 3600.0):
                    skipped_in_file += 1
                    continue

            kept_in_file += 1
            low = body.lower().strip()

            # Track watch/driver session start / cancel / end lines to derive session duration accurately.
            if cur_ts is not None:
                if low.startswith(("play: starting", "watch: waiting", "session start", "started:", "launch guards pass:")):
                    active_start_ts = cur_ts
                    forced_stop_pending = False
                elif low.startswith(("armed: process", "not armed on process", "game up pid ")) and active_start_ts is None:
                    active_start_ts = cur_ts
                elif low.startswith(("play: refused:", "play: stopped by", "play: could not start", "game did not stay up")):
                    active_start_ts = None
            if cur_clock_s is not None:
                if low.startswith(("launch guards pass:", "play: starting", "watch: waiting", "session start", "started:")):
                    active_clock_start = cur_clock_s
                    forced_stop_pending = False
                elif low.startswith(("game up pid ", "armed: process", "not armed on process")) and active_clock_start is None:
                    active_clock_start = cur_clock_s

            if "window did not close: process stopped" in low or low.startswith("not responding:"):
                forced_stop_pending = True

            is_end_line = (
                low.startswith(("ended:", "exited:", "game closed:", "game gone", "game exited "))
                or "alive=false" in low
                or "alive=0" in low
            )
            if is_end_line:
                m_up = _WATCH_UP_RE.search(body)
                up_s = float(m_up.group("up")) if m_up else 0.0
                span_s = (
                    cur_ts - active_start_ts
                    if (cur_ts is not None and active_start_ts is not None and cur_ts >= active_start_ts)
                    else 0.0
                )
                clock_dur_s = 0.0
                if cur_clock_s is not None and active_clock_start is not None:
                    diff = cur_clock_s - active_clock_start
                    if diff < -3600.0:
                        diff += 86400.0
                    if diff > 0.0:
                        clock_dur_s = diff
                active_start_ts = None
                active_clock_start = None
                dur_s = max(up_s, span_s, clock_dur_s)
                if dur_s > 0.0:
                    watch_runs.append((cur_ts or 0.0, dur_s))

            if "alive=false" in low or "alive=0" in low:
                is_clean_driver_close = low.startswith("game closed:") and (not forced_stop_pending)
                forced_stop_pending = False
                if is_clean_driver_close or any(
                    tok in low for tok in ("clean_quit", "clean=true", "clean=1", "expected", "user_quit", "phase=quit")
                ):
                    clean_exits += 1
                else:
                    unexpected_exits += 1
                    exit_notes.append(f"{base}: unexpected process exit (alive=False)")
                continue

            if "0x00000000 normal exit" in low or "clean quit" in low:
                clean_exits += 1
            elif (
                low.startswith(("ended:", "game gone", "game exited within", "game exited before", "guard: the game is not running"))
                or any(
                    tok in low
                    for tok in (
                        "unexpected exit",
                        "ended before it settled",
                        "access_violation",
                        "0xc0000005",
                        "0x80000003",
                        "stack_buffer_overrun",
                        "0xc0000409",
                        "stack_overflow",
                        "0xc00000fd",
                        "heap_corruption",
                        "0xc0000374",
                        "# timed out after",
                    )
                )
                or re.search(r"\bexit code [1-9]\d*\b", low)
            ):
                unexpected_exits += 1
                exit_notes.append(f"{base}: abnormal exit")

        if active_start_ts is not None and anchor_ts is not None and anchor_ts > active_start_ts:
            watch_runs.append((anchor_ts, anchor_ts - active_start_ts))

        stale_lines_skipped += skipped_in_file
        if kept_in_file > 0 or not has_iso or min_mtime is None:
            logs_read += 1
        elif skipped_in_file > 0:
            stale_skipped += 1

    watch_duration_s = 0.0
    if watch_runs:
        watch_runs.sort(key=lambda item: item[0])
        latest_end_ts, latest_dur_s = watch_runs[-1]
        if anchor_ts is None or latest_end_ts <= 0.0 or abs(anchor_ts - latest_end_ts) <= 1800.0:
            watch_duration_s = latest_dur_s

    loader_errors: List[str] = []
    for folder in sfse_dirs:
        if not os.path.isdir(folder):
            continue
        for fn in ("sfse_loader.txt", "sfse_loader.log"):
            p = os.path.join(folder, fn)
            if not os.path.isfile(p):
                continue
            logs_read += 1
            for line in _read_lines(p):
                low = line.strip().lower()
                if not low or low.startswith("winverifytrust: 00000000"):
                    continue
                if any(
                    bad in low
                    for bad in (
                        "error",
                        "failed",
                        "couldn't",
                        "cannot",
                        "mismatch",
                        "dll not found",
                        "unsupported runtime",
                    )
                ):
                    loader_errors.append(line.strip()[:80])

    return {
        "dump_count": len(dumps),
        "dumps": dumps,
        "clean_exits": clean_exits,
        "unexpected_exits": unexpected_exits,
        "exit_notes": exit_notes,
        "loader_errors": loader_errors,
        "logs_read": logs_read,
        "stale_skipped": stale_skipped,
        "stale_lines_skipped": stale_lines_skipped,
        "watch_duration_s": round(watch_duration_s, 1),
    }


def _parse_sfse_logs(sfse_dirs: Sequence[str], *, min_mtime: Optional[float] = None) -> dict:
    seen_paths = set()
    plugins_loaded = set()
    refusals: List[str] = []
    faults = 0
    errors = 0
    starmap_blocked = 0
    logs_read = 0
    stale_skipped = 0
    clock_span_s = 0.0

    for folder in sfse_dirs:
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            low_fn = fn.lower()
            if low_fn in ("sfse_loader.txt", "sfse_loader.log"):
                continue
            if not (low_fn.endswith(".log") or (low_fn.startswith("sfse") and low_fn.endswith(".txt"))):
                continue
            full = os.path.normcase(os.path.abspath(os.path.join(folder, fn)))
            if full in seen_paths:
                continue
            seen_paths.add(full)
            real = os.path.join(folder, fn)
            if not os.path.isfile(real):
                continue
            if not _is_fresh(real, min_mtime):
                stale_skipped += 1
                continue
            logs_read += 1
            stem = os.path.splitext(fn)[0]
            is_runtime_txt = low_fn in ("sfse.txt", "sfse.log")
            times: List[float] = []

            for line in _read_lines(real):
                if is_runtime_txt:
                    m_dll = _SFSE_LOADED_DLL_RE.match(line)
                    if m_dll:
                        plugins_loaded.add(os.path.splitext(m_dll.group("dll"))[0])
                    if any(b in line.lower() for b in ("failed to load", "error:", "plugin limit")):
                        errors += 1
                    continue

                m_sfse = _SFSE_LINE_RE.match(line)
                lvl = m_sfse.group("lvl") if m_sfse else ""
                body = m_sfse.group("body") if m_sfse else line
                if m_sfse:
                    ts = _parse_clock_seconds(m_sfse.group("time"))
                    if ts is not None:
                        times.append(ts)

                if "step=load" in body or "loaded on runtime" in body or re.match(r"^[A-Za-z0-9_]+\s+v\d+\.", body):
                    plugins_loaded.add(stem)

                m_ref = _REFUSE_STEP_RE.search(body)
                if m_ref:
                    refusals.append(f"{stem}:{m_ref.group('step')}")
                    continue

                m_sm = _STARMAP_BLOCKED_RE.search(body)
                if m_sm:
                    starmap_blocked += int(m_sm.group("count")) if m_sm.group("count") else 1

                # Guard against matching words like 'default' when looking for 'fault'.
                if _FAULT_RE.search(body):
                    faults += 1
                    continue

                if lvl == "E" or re.search(r"(?:\bstep=error\b|\berror:|\bfailed\b)", body, re.IGNORECASE):
                    errors += 1

            clock_span_s = max(clock_span_s, _clock_span(times))

    return {
        "plugins_loaded_count": len(plugins_loaded),
        "plugins_loaded": sorted(plugins_loaded),
        "refusals": refusals,
        "faults": faults,
        "errors": errors,
        "starmap_blocked": starmap_blocked,
        "logs_read": logs_read,
        "stale_skipped": stale_skipped,
        "clock_span_s": clock_span_s,
    }


def _parse_papyrus_engine_logs(script_dirs: Sequence[str], *, include_rotated: bool) -> dict:
    seen_files = set()
    files_to_read: List[str] = []
    fallbacks = 0
    for folder in script_dirs:
        chosen, fb = _select_log_files(
            folder,
            include_rotated=include_rotated,
            stem_filter=lambda s: s.casefold() == "papyrus",
        )
        fallbacks += fb
        for _stem, path in chosen:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen_files:
                seen_files.add(norm)
                files_to_read.append(path)

    vm_errors_total = 0
    vm_errors_ours = 0
    vm_warnings_total = 0
    vm_warnings_ours = 0
    stack_errors_total = 0
    stack_errors_ours = 0
    stack_dumps = 0
    cannot_open_store_total = 0
    cannot_open_store_ours = 0
    assign_none_total = 0
    assign_none_ours = 0
    vm_budget_warnings = 0
    vm_overload_errors = 0
    unheld_vanilla = set()
    freeze_windows: List[Tuple[float, float]] = []
    clock_span_s = 0.0
    sample_ours_errors: List[str] = []

    for path in files_to_read:
        lines = _read_lines(path)
        events = []
        cur = None
        in_stack = False
        times: List[float] = []
        freeze_start: Optional[float] = None

        for raw in lines:
            if not raw.strip():
                continue
            m = _PAPYRUS_LINE_RE.match(raw)
            if m:
                t_sec = _parse_clock_seconds(m.group("time"))
                if t_sec is not None:
                    times.append(t_sec)
                body = m.group("text")
                low = body.lower()
                if "vm is freezing" in low and t_sec is not None:
                    freeze_start = t_sec
                elif "vm is thawing" in low and t_sec is not None and freeze_start is not None:
                    end_t = t_sec if t_sec >= freeze_start else t_sec + 86400.0
                    freeze_windows.append((freeze_start, end_t))
                    freeze_start = None

                level = "note"
                msg = body
                if body.startswith("error: "):
                    level, msg = "error", body[7:]
                elif body.startswith("warning: "):
                    level, msg = "warning", body[9:]
                cur = {"level": level, "msg": msg, "body": body, "frames": [], "t": t_sec}
                events.append(cur)
                in_stack = False
                continue
            if raw.strip() == "stack:" and cur is not None:
                in_stack = True
                continue
            if in_stack and raw[:1] in ("\t", " ") and cur is not None:
                cur["frames"].append(raw.strip())

        clock_span_s = max(clock_span_s, _clock_span(times))

        for ev in events:
            lvl = ev["level"]
            msg = ev["msg"]
            body = ev["body"]
            frames = ev["frames"]
            ours = _has_ours(body, frames)

            m_store = _CANNOT_OPEN_STORE_RE.search(body)
            if m_store:
                cannot_open_store_total += 1
                if _OURS_RE.search(m_store.group("cls")) or ours:
                    cannot_open_store_ours += 1

            if _STACK_DUMP_RE.search(body):
                stack_dumps += 1
                if "suspended stack" in body.lower():
                    vm_overload_errors += 1

            if _VM_OVERLOAD_RE.search(body) and not body.startswith("Update budget:"):
                vm_budget_warnings += 1
                if "overstressed" in body.lower() or "suspended stack" in body.lower():
                    vm_overload_errors += 1

            if lvl == "error":
                vm_errors_total += 1
                if frames:
                    stack_errors_total += 1
                if ours:
                    vm_errors_ours += 1
                    if frames:
                        stack_errors_ours += 1
                    if len(sample_ours_errors) < 3:
                        sample_ours_errors.append(msg[:60])
            elif lvl == "warning":
                vm_warnings_total += 1
                if ours:
                    vm_warnings_ours += 1
                if _ASSIGN_NONE_RE.search(msg):
                    assign_none_total += 1
                    if ours:
                        assign_none_ours += 1

            # Check for unheld vanilla start/companion quest activity in stack frames.
            for fr in frames:
                low_fr = fr.lower()
                for vp in _VANILLA_HELD_PREFIXES:
                    if vp in low_fr:
                        m_q = re.search(r"\[(?:alias [^\]]+ on quest )?([A-Za-z0-9_]+)\s*\([0-9A-Fa-f]+\)\]", fr)
                        unheld_vanilla.add(m_q.group(1) if m_q else vp.upper())

    return {
        "logs_read": len(files_to_read),
        "rotated_fallbacks": fallbacks,
        "vm_errors_total": vm_errors_total,
        "vm_errors_ours": vm_errors_ours,
        "vm_warnings_total": vm_warnings_total,
        "vm_warnings_ours": vm_warnings_ours,
        "stack_errors_total": stack_errors_total,
        "stack_errors_ours": stack_errors_ours,
        "stack_dumps": stack_dumps,
        "cannot_open_store_total": cannot_open_store_total,
        "cannot_open_store_ours": cannot_open_store_ours,
        "assign_none_total": assign_none_total,
        "assign_none_ours": assign_none_ours,
        "vm_budget_warnings": vm_budget_warnings,
        "vm_overload_errors": vm_overload_errors,
        "unheld_vanilla_quests": sorted(unheld_vanilla),
        "freeze_windows": freeze_windows,
        "clock_span_s": clock_span_s,
        "sample_ours_errors": sample_ours_errors,
    }


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 == 1 else 0.5 * (s[mid - 1] + s[mid])


def _in_freeze_window(t_prev: Optional[float], t_cur: Optional[float], windows: Sequence[Tuple[float, float]]) -> bool:
    if t_prev is None or t_cur is None or not windows:
        return False
    a, b = (t_prev, t_cur) if t_cur >= t_prev else (t_prev, t_cur + 86400.0)
    return any(w0 <= b and w1 >= a for w0, w1 in windows)


def _canonical_quest_name(stem: str, line: str) -> Optional[str]:
    low_s = stem.lower()
    low_l = line.lower()
    if "fo4sf_newgame" in low_l or low_s == "fo4sf_newgame":
        return "FO4SF_NewGame"
    if "fo4sf_mission" in low_l or "fo4sf_min00" in low_l or low_s in ("fo4sf_mission", "fo4sf_min00"):
        return "FO4SF_Min00"
    if "fo4sf_alife" in low_l or low_s == "fo4sf_alife":
        return "FO4SF_ALife"
    return None


def _nominal_for_stream(stream: str, deltas: Sequence[float]) -> float:
    if stream == "FO4SF_NewGame":
        return 6.0
    if stream == "FO4SF_Min00":
        return max(6.0, min(_median(deltas), 8.0)) if deltas else 6.0
    if stream == "FO4SF_ALife:1a":
        return 2.0
    if stream == "FO4SF_ALife:1b":
        return 1.0
    if stream == "FO4SF_Bridge":
        return max(0.75, min(_median(deltas), 2.0)) if deltas else 1.0
    med = _median(deltas)
    return med if med > 0.1 else 5.0


def _parse_user_slice_logs(
    user_dirs: Sequence[str],
    *,
    include_rotated: bool,
    stall_seconds: float,
    freeze_windows: Sequence[Tuple[float, float]],
    min_mtime: Optional[float] = None,
) -> dict:
    seen_files = set()
    selected: List[Tuple[str, str]] = []
    fallbacks = 0
    stale_skipped = 0
    skip_stems = {"papyrus", "driver", "monitor", "crashwatch"}

    for folder in user_dirs:
        chosen, fb = _select_log_files(
            folder,
            include_rotated=include_rotated,
            stem_filter=lambda s: s.casefold() not in skip_stems,
        )
        fallbacks += fb
        for stem, path in chosen:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen_files:
                seen_files.add(norm)
                if not _is_fresh(path, min_mtime):
                    stale_skipped += 1
                    continue
                selected.append((stem, path))

    hold_passes: Dict[int, Tuple[int, int]] = {}
    running_after_hold: List[str] = []
    quest_final_stage: Dict[str, str] = {}
    stuck_quests: List[dict] = []
    alife_failures: List[str] = []
    timer_dips: List[dict] = []
    max_observed_gap_s = 0.0
    max_observed_excess_ms = 0
    rt_span_s = 0.0
    clock_span_s = 0.0

    for stem, path in selected:
        lines = _read_lines(path)
        times: List[float] = []
        # Split file into monotonic rt runs so restarts or rotated files never cross-contaminate deltas.
        runs: List[List[Tuple[Optional[float], float, str]]] = []
        cur_run: List[Tuple[Optional[float], float, str]] = []
        prev_rt: Optional[float] = None

        for raw in lines:
            if not raw.strip():
                continue
            m_p = _PAPYRUS_LINE_RE.match(raw)
            t_clock = _parse_clock_seconds(m_p.group("time")) if m_p else None
            if t_clock is not None:
                times.append(t_clock)
            body = m_p.group("text") if m_p else raw

            if "log opened" in body.lower():
                if cur_run:
                    runs.append(cur_run)
                    cur_run = []
                prev_rt = None
                continue

            m_hp = _HOLD_PASS_RE.search(body)
            if m_hp:
                hold_passes[int(m_hp.group("pass"))] = (int(m_hp.group("stopped")), int(m_hp.group("total")))

            m_ho = _HELD_OFF_RE.search(body)
            if m_ho and m_ho.group("running").lower() == "true":
                qlabel = _clean_quest_label(m_ho.group("quest"))
                if qlabel not in running_after_hold:
                    running_after_hold.append(qlabel)

            m_rt = _RT_RE.search(body)
            if m_rt:
                rt = float(m_rt.group("rt"))
                if prev_rt is not None and rt < prev_rt - 1.0:
                    runs.append(cur_run)
                    cur_run = []
                prev_rt = rt
                cur_run.append((t_clock, rt, body))

        if cur_run:
            runs.append(cur_run)
        clock_span_s = max(clock_span_s, _clock_span(times))

        for run in runs:
            if len(run) >= 2:
                rt_span_s = max(rt_span_s, run[-1][1] - run[0][1])

            # Track quest stage dwell times within this run.
            stage_spans: Dict[str, Dict[int, List[float]]] = {}
            stage_order: Dict[str, List[int]] = {}
            alife_wp_spans: Dict[int, List[float]] = {}
            alife_completed = False

            # Track periodic heartbeat streams: stream_name -> [(clock, rt, paused_since_prev)]
            heartbeats: Dict[str, List[Tuple[Optional[float], float, bool]]] = {}
            pause_between: Dict[str, bool] = {}

            for t_clock, rt, body in run:
                low = body.lower()
                qname = _canonical_quest_name(stem, body)

                # Pause / prompt / load transitions excuse the next heartbeat gap on that stream.
                if any(
                    p in low
                    for p in (
                        "looks position",
                        "looks done",
                        "elevator prompt",
                        "step=load_game",
                        "keeper load",
                        "paused=1",
                        "paused=true",
                        "menu=pausemenu",
                        "waiting for the 3d",
                    )
                ):
                    for k in list(pause_between):
                        pause_between[k] = True
                    if qname:
                        pause_between[qname] = True

                if qname:
                    m_st = _STAGE_EVENT_RE.search(body)
                    # Ignore Codsworth/Preston keeper lines which carry no quest stage.
                    if m_st and "keeper " not in low:
                        stg = int(m_st.group("s1") or m_st.group("s2"))
                        quest_final_stage[qname] = str(stg)
                        qmap = stage_spans.setdefault(qname, {})
                        if stg not in qmap:
                            qmap[stg] = [rt, rt]
                            stage_order.setdefault(qname, []).append(stg)
                        else:
                            qmap[stg][1] = max(qmap[stg][1], rt)

                if qname == "FO4SF_ALife":
                    m_wp = _ALIFE_WP_RE.search(body)
                    if m_wp:
                        wp_idx = int(m_wp.group("wp"))
                        quest_final_stage.setdefault("FO4SF_ALife", f"wp{wp_idx}/{m_wp.group('total')}")
                        quest_final_stage["FO4SF_ALife"] = f"wp{wp_idx}/{m_wp.group('total')}"
                        if wp_idx not in alife_wp_spans:
                            alife_wp_spans[wp_idx] = [rt, rt]
                        else:
                            alife_wp_spans[wp_idx][1] = max(alife_wp_spans[wp_idx][1], rt)
                    m_stuck = _ALIFE_STUCK_RE.search(body)
                    if m_stuck:
                        stuck_quests.append(
                            {
                                "quest": "FO4SF_ALife",
                                "stage": "rung1a_wp",
                                "seconds": round(float(m_stuck.group("still")), 1),
                            }
                        )
                    m_sum = _ALIFE_SUMMARY_RE.search(body)
                    if m_sum:
                        res = m_sum.group("res").upper()
                        rung = m_sum.group("rung")
                        quest_final_stage["FO4SF_ALife"] = f"{rung}:{res}"
                        if res == "PASS":
                            alife_completed = True
                        else:
                            alife_failures.append(f"FO4SF_ALife:{rung}=FAIL")

                # Heartbeat stream classification
                hb_stream: Optional[str] = None
                if qname in ("FO4SF_NewGame", "FO4SF_Min00") and " status stage=" in low:
                    hb_stream = qname
                elif qname == "FO4SF_ALife" and "step=rung1a_progress" in low:
                    hb_stream = "FO4SF_ALife:1a"
                elif qname == "FO4SF_ALife" and ("step=rung1b_tick" in low or "step=rung1b_progress" in low):
                    hb_stream = "FO4SF_ALife:1b"
                elif stem.lower() == "fo4sf" and " pos=" in low and " n=" in low:
                    hb_stream = "FO4SF_Bridge"
                elif (" status " in low or "step=tick" in low or "heartbeat" in low) and qname is None:
                    hb_stream = stem

                if hb_stream is not None:
                    was_paused = pause_between.pop(hb_stream, False) or (
                        qname is not None and pause_between.pop(qname, False)
                    )
                    heartbeats.setdefault(hb_stream, []).append((t_clock, rt, was_paused))

            # Evaluate quest stage stalls (> stall_seconds without advancing to a subsequent stage).
            run_end_rt = run[-1][1] if run else 0.0
            for qname, qmap in stage_spans.items():
                terminals = _TERMINAL_STAGES.get(qname, {200})
                ordered = stage_order.get(qname, [])
                for idx_s, stg in enumerate(ordered):
                    if stg in terminals:
                        continue
                    t_first, t_last = qmap[stg]
                    # If a later stage came in the same run, dwell ends at the next stage's first timestamp;
                    # otherwise dwell extends through the last observation of this stage (or run_end_rt if still on it).
                    if idx_s + 1 < len(ordered):
                        next_stg = ordered[idx_s + 1]
                        dwell = qmap[next_stg][0] - t_first
                    else:
                        dwell = max(t_last, run_end_rt) - t_first
                    if dwell > stall_seconds:
                        stuck_quests.append({"quest": qname, "stage": stg, "seconds": round(dwell, 1)})

            if alife_wp_spans and not alife_completed:
                wp_keys = sorted(alife_wp_spans)
                for i_w, wp_idx in enumerate(wp_keys):
                    t_first, t_last = alife_wp_spans[wp_idx]
                    dwell = (
                        alife_wp_spans[wp_keys[i_w + 1]][0] - t_first
                        if i_w + 1 < len(wp_keys)
                        else max(t_last, run_end_rt) - t_first
                    )
                    if dwell > stall_seconds:
                        stuck_quests.append(
                            {"quest": "FO4SF_ALife", "stage": f"wp{wp_idx}", "seconds": round(dwell, 1)}
                        )

            # Evaluate heartbeat timer dips (> 3x nominal interval outside menu pause).
            for hb_stream, pts in heartbeats.items():
                if len(pts) < 2:
                    continue
                raw_deltas = [
                    pts[i][1] - pts[i - 1][1]
                    for i in range(1, len(pts))
                    if not pts[i][2] and pts[i][1] >= pts[i - 1][1]
                ]
                if not raw_deltas:
                    continue
                nominal = _nominal_for_stream(hb_stream, raw_deltas)
                for i in range(1, len(pts)):
                    t_prev_c, rt_prev, _ = pts[i - 1]
                    t_cur_c, rt_cur, paused = pts[i]
                    if paused or _in_freeze_window(t_prev_c, t_cur_c, freeze_windows):
                        continue
                    dt = rt_cur - rt_prev
                    if dt <= 0.0:
                        continue
                    excess_ms = int(round(max(0.0, dt - nominal) * 1000.0))
                    if dt > max_observed_gap_s:
                        max_observed_gap_s = dt
                        max_observed_excess_ms = excess_ms
                    if dt > 3.0 * nominal and (dt - nominal) >= 1.5:
                        timer_dips.append(
                            {
                                "stream": hb_stream,
                                "gap_s": round(dt, 2),
                                "nominal_s": round(nominal, 2),
                                "excess_ms": excess_ms,
                                "rt_at": round(rt_cur, 1),
                            }
                        )

    timer_dips.sort(key=lambda d: (-d["gap_s"], d["stream"]))
    return {
        "logs_read": len(selected),
        "rotated_fallbacks": fallbacks,
        "stale_skipped": stale_skipped,
        "hold_passes": {str(k): {"stopped": v[0], "total": v[1]} for k, v in sorted(hold_passes.items())},
        "running_after_hold": running_after_hold,
        "quest_final_stage": quest_final_stage,
        "stuck_quests": stuck_quests,
        "alife_failures": alife_failures,
        "timer_dips": timer_dips,
        "worst_dip_s": round(timer_dips[0]["gap_s"] if timer_dips else max_observed_gap_s, 2),
        "worst_excess_ms": timer_dips[0]["excess_ms"] if timer_dips else max_observed_excess_ms,
        "rt_span_s": rt_span_s,
        "clock_span_s": clock_span_s,
    }


def analyze_session(
    log_dir: Optional[str] = None,
    *,
    sfse_log_dir: Optional[str] = None,
    crash_dir: Optional[str] = None,
    driver_log: Optional[str] = None,
    include_rotated: bool = False,
    stall_seconds: float = DEFAULT_STALL_SECONDS,
    session_window_hours: Optional[float] = DEFAULT_SESSION_WINDOW_HOURS,
) -> dict:
    """Parse Crash/Process, SFSE, and Papyrus/Slice logs into a structured soak report dict."""
    layout = _resolve_layout(log_dir, sfse_log_dir, crash_dir, driver_log)
    min_mtime, anchor_ts = _compute_session_bounds(layout, session_window_hours)
    crashes = _parse_crashes_and_exits(
        layout["crash_dirs"],
        layout["driver_logs"],
        layout["sfse_dirs"],
        min_mtime=min_mtime,
        anchor_ts=anchor_ts,
    )
    sfse = _parse_sfse_logs(layout["sfse_dirs"], min_mtime=min_mtime)
    papyrus = _parse_papyrus_engine_logs(layout["script_dirs"], include_rotated=include_rotated)
    slices = _parse_user_slice_logs(
        layout["user_dirs"],
        include_rotated=include_rotated,
        stall_seconds=stall_seconds,
        freeze_windows=papyrus["freeze_windows"],
        min_mtime=min_mtime,
    )

    total_logs = crashes["logs_read"] + sfse["logs_read"] + papyrus["logs_read"] + slices["logs_read"]
    stale_skipped = crashes["stale_skipped"] + sfse["stale_skipped"] + slices["stale_skipped"]
    fallback_span_s = max(
        sfse["clock_span_s"],
        papyrus["clock_span_s"],
        slices["clock_span_s"],
        slices["rt_span_s"],
    )
    watch_span_s = crashes.get("watch_duration_s", 0.0)
    duration_s = round(watch_span_s if watch_span_s > 0.0 else fallback_span_s, 1)

    fail_reasons: List[str] = []
    warn_reasons: List[str] = []

    if crashes["dump_count"] > 0:
        fail_reasons.append(f"crash_dumps={crashes['dump_count']}")
    if crashes["unexpected_exits"] > 0:
        fail_reasons.append(f"unexpected_exits={crashes['unexpected_exits']}")
    if crashes["loader_errors"]:
        fail_reasons.append(f"sfse_loader_errors={len(crashes['loader_errors'])}")

    if sfse["refusals"]:
        fail_reasons.append(f"sfse_refusals={len(sfse['refusals'])}")
    if sfse["faults"] > 0:
        fail_reasons.append(f"sfse_faults={sfse['faults']}")
    if sfse["errors"] > 0:
        fail_reasons.append(f"sfse_errors={sfse['errors']}")

    if papyrus["vm_errors_ours"] > 0:
        fail_reasons.append(f"papyrus_errors_ours={papyrus['vm_errors_ours']}")
    if papyrus["cannot_open_store_ours"] > 0:
        fail_reasons.append(f"missing_pex_ours={papyrus['cannot_open_store_ours']}")
    if papyrus["stack_dumps"] > 0 or papyrus["vm_overload_errors"] > 0:
        fail_reasons.append("papyrus_vm_overload")

    if slices["running_after_hold"]:
        fail_reasons.append(f"running_after_hold={len(slices['running_after_hold'])}")
    if slices["alife_failures"]:
        fail_reasons.append(f"alife_failed={len(slices['alife_failures'])}")

    if slices["stuck_quests"]:
        warn_reasons.append(f"stuck_quests={len(slices['stuck_quests'])}")
    if papyrus["unheld_vanilla_quests"]:
        warn_reasons.append(f"unheld_vanilla={len(papyrus['unheld_vanilla_quests'])}")
    if papyrus["assign_none_ours"] > 0:
        warn_reasons.append(f"assign_none_ours={papyrus['assign_none_ours']}")
    if slices["timer_dips"]:
        warn_reasons.append(f"timer_dips={len(slices['timer_dips'])}")
    if papyrus["vm_budget_warnings"] > 0:
        warn_reasons.append(f"vm_budget_warnings={papyrus['vm_budget_warnings']}")
    if total_logs == 0 and crashes["dump_count"] == 0:
        warn_reasons.append("no_logs_found")

    verdict = "FAIL" if fail_reasons else ("WARN" if warn_reasons else "PASS")
    return {
        "verdict": verdict,
        "duration_seconds": duration_s,
        "logs_scanned": total_logs,
        "stale_logs_skipped": stale_skipped,
        "rotated_fallbacks": papyrus["rotated_fallbacks"] + slices["rotated_fallbacks"],
        "missing_dirs": layout["missing_dirs"],
        "fail_reasons": fail_reasons,
        "warn_reasons": warn_reasons,
        "crashes": crashes,
        "sfse": sfse,
        "papyrus": papyrus,
        "quests": {
            "hold_passes": slices["hold_passes"],
            "running_after_hold": slices["running_after_hold"],
            "final_stages": slices["quest_final_stage"],
            "stuck_quests": slices["stuck_quests"],
            "unheld_vanilla_quests": papyrus["unheld_vanilla_quests"],
            "alife_failures": slices["alife_failures"],
        },
        "perf": {
            "timer_dips": slices["timer_dips"],
            "worst_dip_s": slices["worst_dip_s"],
            "worst_excess_ms": slices["worst_excess_ms"],
            "vm_budget_warnings": papyrus["vm_budget_warnings"],
        },
    }


def _clamp(line: str, width: int) -> str:
    if len(line) <= width:
        return line
    return line[: max(0, width - 3)].rstrip() + "..."


def _fmt_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    mins, secs = divmod(total, 60)
    if mins >= 60:
        hrs, rem_m = divmod(mins, 60)
        return f"{hrs}h {rem_m:02d}m {secs:02d}s"
    return f"{mins}m {secs:02d}s"


def format_phone_report(
    report: dict,
    *,
    max_width: int = PHONE_MAX_WIDTH,
    max_lines: int = PHONE_MAX_LINES,
) -> str:
    """Render a compact narrow summary card (<= 56 chars/line, <= 40 lines) readable on a phone."""
    crashes = report["crashes"]
    sfse = report["sfse"]
    papyrus = report["papyrus"]
    quests = report["quests"]
    perf = report["perf"]

    dur = _fmt_duration(report.get("duration_seconds", 0.0))
    lines: List[str] = [
        "FO4SF SOAK REPORT",
        f"VERDICT: {report['verdict']}",
        f"Duration: {dur} | Logs: {report['logs_scanned']}",
    ]
    if report.get("fail_reasons"):
        lines.append("Why: " + ", ".join(report["fail_reasons"][:2]))
    elif report.get("warn_reasons"):
        lines.append("Note: " + ", ".join(report["warn_reasons"][:2]))

    # 1. Crashes & Exits
    lines.append("")
    lines.append("1. Crashes & Exits")
    if crashes["dump_count"]:
        first_dmp = crashes["dumps"][0]
        ts_short = first_dmp["timestamp"][11:19] if len(first_dmp["timestamp"]) >= 19 else "dmp"
        lines.append(f"- Dumps: {crashes['dump_count']} ({first_dmp['name']} {ts_short})")
    else:
        lines.append("- Dumps (.dmp): 0")
    lines.append(f"- Exits: {crashes['clean_exits']} clean, {crashes['unexpected_exits']} unexp")
    loader_st = f"{len(crashes['loader_errors'])} err" if crashes["loader_errors"] else "ok"
    lines.append(f"- SFSE loader: {loader_st}")

    # 2. Script & SFSE Errors
    lines.append("")
    lines.append("2. Script & SFSE Errors")
    base_err = max(0, papyrus["vm_errors_total"] - papyrus["vm_errors_ours"])
    lines.append(f"- VM err: {papyrus['vm_errors_ours']} ours ({base_err} base)")
    lines.append(
        f"- Store: {papyrus['cannot_open_store_ours']} ours | None: {papyrus['assign_none_ours']} ours"
    )
    if papyrus["stack_dumps"]:
        lines.append(f"- Stack dumps/overload: {papyrus['stack_dumps']}")
    lines.append(
        f"- SFSE: {sfse['plugins_loaded_count']} dll, {len(sfse['refusals'])} ref, {sfse['faults']} flt, {sfse['errors']} err"
    )
    if sfse["refusals"]:
        lines.append(f"- Refuse: {', '.join(sfse['refusals'][:2])}")
    if sfse["starmap_blocked"]:
        lines.append(f"- Starmap blocked: {sfse['starmap_blocked']}")

    # 3. Quests (Held / Stuck)
    lines.append("")
    lines.append("3. Quests (Held / Stuck)")
    hp = quests["hold_passes"]
    if hp:
        hp_txt = ", ".join(f"p{k} {v['stopped']}/{v['total']}" for k, v in sorted(hp.items())[:2])
        lines.append(f"- Hold-off: {hp_txt}")
    else:
        lines.append("- Hold-off: none logged")
    if quests["running_after_hold"]:
        lines.append(
            f"- Running after hold ({len(quests['running_after_hold'])}): {', '.join(quests['running_after_hold'][:2])}"
        )
    else:
        lines.append("- Running after hold: 0")
    st_map = quests["final_stages"]
    if st_map:
        short_names = {"FO4SF_NewGame": "NG", "FO4SF_Min00": "Min00", "FO4SF_ALife": "ALife"}
        st_txt = ", ".join(f"{short_names.get(k, k)}={v}" for k, v in sorted(st_map.items()))
        lines.append(f"- Stages: {st_txt}")
    if quests["stuck_quests"]:
        sq = quests["stuck_quests"][0]
        qshort = sq["quest"].replace("FO4SF_", "")
        lines.append(f"- Stuck: {qshort}@{sq['stage']} ({int(round(sq['seconds']))}s)")
    else:
        lines.append("- Stuck (>300s): none")
    if quests["unheld_vanilla_quests"]:
        lines.append(f"- Unheld base: {', '.join(quests['unheld_vanilla_quests'][:2])}")

    # 4. Perf & Timer Dips
    lines.append("")
    lines.append("4. Perf & Timer Dips")
    dips = perf["timer_dips"]
    if dips:
        top = dips[0]
        sname = top["stream"].replace("FO4SF_", "")
        lines.append(f"- Dips (>3x): {len(dips)} (max {top['gap_s']:.1f}s +{top['excess_ms']}ms)")
        lines.append(f"- Worst stream: {sname} (nom {top['nominal_s']:.1f}s)")
    else:
        lines.append(f"- Dips (>3x): 0 (max {perf['worst_dip_s']:.1f}s)")
    lines.append(f"- VM budget/stack alerts: {perf['vm_budget_warnings']}")

    clamped = [_clamp(ln, max_width) for ln in lines[:max_lines]]
    return "\n".join(clamped) + "\n"
