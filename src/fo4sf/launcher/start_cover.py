"""Stand-alone Fallout-style Start Cover for the FO4SF launcher (X8).

Pure Python standard library; importing this module requires no display and no tkinter.
Watches an atomic signal file (never tails or locks Papyrus/game logs), enforces a hard
timeout, exposes an always-visible Cancel action, yields immediately when the crash watcher
or process check detects a crash or early game exit, and never sends input or steals focus.
"""
import json
import os
import re
import time

DEFAULT_TIMEOUT_S = 90.0
MIN_TIMEOUT_S = 1.0
MAX_TIMEOUT_S = 600.0
POLL_INTERVAL_MS = 200
SIGNAL_FILENAME = "start_ready.json"

# Win32 constants (applied lazily only on Windows real windows; never required in tests)
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

# Original clean-room terminal frame & text ONLY — zero Bethesda logos, music, or movies.
COVER_BANNER_LINES = (
    "+======================================================================+",
    "|  FO4SF // PIP-OS STANDALONE TERMINAL                    [BOOT LINK]  |",
    "+======================================================================+",
)

COVER_STAGE_LINES = (
    ("locate", "1. LOCATE     :: Verified local installations & isolated Plugins.txt"),
    ("launch", "2. LAUNCH     :: Starting runtime via configured route (crash guard armed)"),
    ("world", "3. WORLD SYNC :: Holding cover until starting cell reports READY"),
)


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


def default_signal_path(env=None):
    """Default atomic ready-signal path under LOCALAPPDATA/FO4SF (outside Documents and Data/)."""
    environ = os.environ if env is None else env
    base = environ.get("LOCALAPPDATA") or environ.get("XDG_STATE_HOME") or os.path.expanduser("~")
    sep = "\\" if "\\" in base and "/" not in base else os.sep
    return f"{base.rstrip('/\\')}{sep}FO4SF{sep}{SIGNAL_FILENAME}"


def clamp_timeout(timeout_s):
    try:
        val = float(timeout_s)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_S
    if val != val:  # NaN guard
        return DEFAULT_TIMEOUT_S
    return max(MIN_TIMEOUT_S, min(MAX_TIMEOUT_S, val))


def write_fake_ready_signal(signal_path, *, nonce="", stage="fake_ready", pid=0):
    """Atomically write a synthetic 'ready' signal file for offline/desktop cover verification."""
    target = os.path.abspath(signal_path)
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{target}.tmp-{os.getpid()}"
    payload = {
        "status": "ready",
        "nonce": str(nonce or ""),
        "stage": str(stage or "ready"),
        "pid": int(pid or 0),
    }
    with open(tmp, "w", encoding="utf-8", newline="\n") as fp:
        json.dump(payload, fp, indent=2)
        fp.write("\n")
    os.replace(tmp, target)
    return target


def clear_signal_file(signal_path):
    """Remove a stale ready-signal file before launch; ignore missing files."""
    if not signal_path:
        return
    try:
        os.remove(signal_path)
    except FileNotFoundError:
        return
    except OSError:
        return


def read_ready_signal(signal_path, *, expected_nonce=""):
    """Read and immediately close `signal_path` (no persistent handle or tail lock).

    Returns `(is_ready, info_dict)`. Accepts either JSON `{"status": "ready", ...}` or
    a plain single-token `ready` file when `expected_nonce` is empty.
    """
    if not signal_path or not os.path.isfile(signal_path):
        return False, {}
    try:
        with open(signal_path, "r", encoding="utf-8") as fp:
            raw = fp.read(4096).strip()
    except OSError:
        return False, {}
    if not raw:
        return False, {}
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
        except ValueError:
            return False, {}
        if not isinstance(data, dict):
            return False, {}
        if str(data.get("status", "")).strip().lower() != "ready":
            return False, {}
        if expected_nonce and str(data.get("nonce", "")) != str(expected_nonce):
            return False, {}
        return True, {
            "status": "ready",
            "nonce": str(data.get("nonce", "")),
            "stage": str(data.get("stage", "ready") or "ready"),
            "pid": data.get("pid", 0),
            "file": path_basename(signal_path),
        }
    if not expected_nonce and raw.splitlines()[0].strip().lower() == "ready":
        return True, {"status": "ready", "nonce": "", "stage": "ready", "pid": 0, "file": path_basename(signal_path)}
    return False, {}


def format_timer_text(elapsed_s, timeout_s):
    rem = max(0.0, float(timeout_s) - max(0.0, float(elapsed_s)))
    el_i = int(max(0.0, float(elapsed_s)))
    rem_i = int(round(rem))
    return f"Elapsed {el_i // 60:02d}:{el_i % 60:02d}  ·  Auto-close in {rem_i // 60:02d}:{rem_i % 60:02d}"


class StartCoverController:
    """Headless state machine for the Start Cover.

    Safety precedence on every `poll()`:
      1. Crash watcher / process crash check (`crash_fn`) -> closes immediately (`crash_detected`).
      2. Tracked game PID disappeared (`pids_fn`) -> closes immediately (`game_exited`).
      3. Manual Cancel (`cancel()`) -> closes immediately (`cancelled`).
      4. Valid `"ready"` signal file -> closes (`ready`).
      5. Hard timeout (`elapsed >= timeout_s`) -> closes (`timeout`).
    """

    def __init__(
        self,
        signal_path,
        *,
        timeout_s=DEFAULT_TIMEOUT_S,
        expected_nonce="",
        clock=time.monotonic,
        pids_fn=None,
        crash_fn=None,
        foreground_fn=None,
    ):
        self.signal_path = str(signal_path or "")
        self.timeout_s = clamp_timeout(timeout_s)
        self.expected_nonce = str(expected_nonce or "")
        self._clock = clock
        self._pids_fn = pids_fn
        self._crash_fn = crash_fn
        self._foreground_fn = foreground_fn
        self.state = "idle"
        self.reason = ""
        self.detail = ""
        self.ready_info = {}
        self.started_at = 0.0
        self.closed_at = None
        self.seen_game_pid = False
        self.topmost = True

    def start(self, *, clear_stale=True):
        if clear_stale and self.signal_path:
            clear_signal_file(self.signal_path)
        self.started_at = float(self._clock())
        self.closed_at = None
        self.state = "active"
        self.reason = ""
        self.detail = "Waiting for game ready signal…"
        self.ready_info = {}
        self.seen_game_pid = False
        self.topmost = True
        return self.snapshot()

    def elapsed(self):
        if self.state == "idle":
            return 0.0
        end = self.closed_at if self.closed_at is not None else float(self._clock())
        return max(0.0, end - self.started_at)

    def _close(self, reason, detail=""):
        if self.state != "closed":
            self.state = "closed"
            self.closed_at = float(self._clock())
            self.reason = reason
            self.detail = detail or reason
            self.topmost = False
        return self.snapshot()

    def cancel(self):
        """Player pressed Cancel / Dismiss cover (never stops the game)."""
        if self.state == "idle":
            self.started_at = float(self._clock())
        return self._close("cancelled", "Cover dismissed by player; game continues unaffected.")

    def notify_crash(self, detail="Crash watcher reported a stop or dump."):
        """Immediate crash-watcher override: the cover never hides a crash dialog or dump."""
        if self.state == "idle":
            self.started_at = float(self._clock())
        return self._close("crash_detected", str(detail or "Crash watcher reported a stop."))

    def update_focus(self, foreground_kind):
        """Yield topmost when the player Alt+Tabs to another desktop window (`other`)."""
        if self.state != "active":
            self.topmost = False
            return False
        self.topmost = foreground_kind in ("game", "launcher", "cover", None, "")
        return self.topmost

    def poll(self):
        if self.state != "active":
            return self.snapshot()

        # 1. Crash watcher ALWAYS wins before any other check.
        if self._crash_fn is not None:
            try:
                crash = self._crash_fn()
            except Exception as exc:
                return self._close("crash_detected", f"Crash check error: {exc}")
            if crash:
                msg = crash if isinstance(crash, str) else "Crash watcher detected a stop or dump."
                return self._close("crash_detected", msg)

        # 2. If Starfield was running and exited before ready, remove cover immediately.
        live_pids = ()
        if self._pids_fn is not None:
            try:
                live_pids = tuple(self._pids_fn() or ())
            except Exception as exc:
                return self._close("crash_detected", f"Process check failed: {exc}")
            if live_pids:
                self.seen_game_pid = True
            elif self.seen_game_pid:
                return self._close("game_exited", "Starfield exited before reporting ready.")

        # 3. Check atomic signal file (short-lived open/close; zero log tailing).
        ok, info = read_ready_signal(self.signal_path, expected_nonce=self.expected_nonce)
        if ok:
            self.ready_info = info
            stage = info.get("stage", "ready")
            return self._close("ready", f"Game ready ({stage}).")

        # 4. Enforce hard timeout so a hung load spinner is never hidden indefinitely.
        el = self.elapsed()
        if el >= self.timeout_s:
            return self._close("timeout", f"Start Cover timed out after {self.timeout_s:g} s.")

        # 5. Update Alt+Tab topmost courtesy from live foreground window check when provided.
        if self._foreground_fn is not None:
            try:
                fg_kind = self._foreground_fn(live_pids)
            except TypeError:
                fg_kind = self._foreground_fn()
            except Exception:
                fg_kind = "game"
            self.update_focus(fg_kind)

        self.detail = format_timer_text(el, self.timeout_s)
        return self.snapshot()

    def snapshot(self):
        el = self.elapsed()
        return {
            "state": self.state,
            "active": self.state == "active",
            "reason": self.reason,
            "detail": self.detail,
            "elapsed_s": round(el, 3),
            "timeout_s": self.timeout_s,
            "timer_text": format_timer_text(el, self.timeout_s),
            "topmost": self.topmost,
            "signal_file": path_basename(self.signal_path),
            "ready_info": dict(self.ready_info),
        }


def _declare_user32(user32):
    """Declare 64-bit safe HWND/LONG_PTR signatures on real ctypes.windll.user32."""
    try:
        import ctypes
        from ctypes import POINTER, wintypes
    except Exception:
        return user32
    if not hasattr(user32, "_FuncPtr"):
        return user32
    long_ptr = ctypes.c_ssize_t
    if hasattr(user32, "GetAncestor"):
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
    if hasattr(user32, "GetParent"):
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
    if hasattr(user32, "GetForegroundWindow"):
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
    if hasattr(user32, "GetWindowThreadProcessId"):
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    for name in ("GetWindowLongPtrW", "GetWindowLongW"):
        if hasattr(user32, name):
            fn = getattr(user32, name)
            fn.argtypes = [wintypes.HWND, ctypes.c_int]
            fn.restype = long_ptr
    for name in ("SetWindowLongPtrW", "SetWindowLongW"):
        if hasattr(user32, name):
            fn = getattr(user32, name)
            fn.argtypes = [wintypes.HWND, ctypes.c_int, long_ptr]
            fn.restype = long_ptr
    return user32


def resolve_toplevel_hwnd(hwnd, user32=None):
    """Resolve Tk's inner child HWND (`winfo_id()`) to its top-level Win32 wrapper HWND."""
    if not hwnd:
        return 0
    if user32 is None:
        return int(hwnd)
    top = 0
    get_anc = getattr(user32, "GetAncestor", None)
    if callable(get_anc):
        try:
            top = int(get_anc(hwnd, GA_ROOT) or 0)
        except Exception:
            top = 0
    if not top:
        get_par = getattr(user32, "GetParent", None)
        if callable(get_par):
            try:
                top = int(get_par(hwnd) or 0)
            except Exception:
                top = 0
    return top or int(hwnd)


def foreground_pid_win32(user32=None):
    """Read-only PID of the current Win32 foreground window, or 0 if unavailable."""
    if user32 is None:
        if os.name != "nt":
            return 0
        try:
            import ctypes
            user32 = _declare_user32(ctypes.windll.user32)
        except Exception:
            return 0
    try:
        fg_hwnd = int(user32.GetForegroundWindow() or 0)
        if not fg_hwnd:
            return 0
        # Support lightweight test doubles exposing foreground_pid_of(hwnd) or standard Win32 out-pointer.
        helper = getattr(user32, "foreground_pid_of", None)
        if callable(helper):
            return int(helper(fg_hwnd) or 0)
        import ctypes
        from ctypes import wintypes
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(pid))
        return int(pid.value or 0)
    except Exception:
        return 0


def _process_image_basename_win32(pid, kernel32=None):
    """Fast (<0.02 ms, zero subprocess) image basename of `pid` on Windows via QueryFullProcessImageNameW."""
    if not pid:
        return ""
    if kernel32 is None:
        if os.name != "nt":
            return ""
        try:
            import ctypes
            from ctypes import POINTER, wintypes
            kernel32 = ctypes.windll.kernel32
            if hasattr(kernel32, "_FuncPtr"):
                kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
                kernel32.OpenProcess.restype = wintypes.HANDLE
                kernel32.QueryFullProcessImageNameW.argtypes = [
                    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, POINTER(wintypes.DWORD),
                ]
                kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
                kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
                kernel32.CloseHandle.restype = wintypes.BOOL
        except Exception:
            return ""
    helper = getattr(kernel32, "image_of", None)
    if callable(helper):
        return path_basename(helper(pid))
    handle = 0
    try:
        import ctypes
        from ctypes import wintypes
        handle = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return path_basename(buf.value[:size.value])
    except Exception:
        return ""
    finally:
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass


def foreground_kind_win32(game_pids=(), *, own_pid=None, allowed_pids=(), user32=None, kernel32=None):
    """Classify the active desktop foreground window as 'launcher', 'game', or 'other' (Alt+Tab)."""
    fg_pid = foreground_pid_win32(user32=user32)
    if not fg_pid:
        return "game"
    me = os.getpid() if own_pid is None else int(own_pid)
    if fg_pid == me or fg_pid in set(allowed_pids or ()):
        return "launcher"
    if fg_pid in set(game_pids or ()):
        return "game"
    img = _process_image_basename_win32(fg_pid, kernel32=kernel32).lower()
    if img in ("starfield.exe", "sfse_loader.exe"):
        return "game"
    return "other"


def apply_win32_noactivate(hwnd, user32=None):
    """Apply WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW on the top-level wrapper HWND so focus is never stolen."""
    if not hwnd:
        return False
    if user32 is None:
        if os.name != "nt":
            return False
        try:
            import ctypes
            user32 = _declare_user32(ctypes.windll.user32)
        except Exception:
            return False
    try:
        target_hwnd = resolve_toplevel_hwnd(hwnd, user32=user32)
        get_fn = getattr(user32, "GetWindowLongPtrW", None) or getattr(user32, "GetWindowLongW")
        set_fn = getattr(user32, "SetWindowLongPtrW", None) or getattr(user32, "SetWindowLongW")
        cur = int(get_fn(target_hwnd, GWL_EXSTYLE))
        new_style = cur | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        set_fn(target_hwnd, GWL_EXSTYLE, new_style)
        return True
    except Exception:
        return False


class StartCoverWindow:
    """Stand-alone borderless Tk Toplevel/Tk wrapper around `StartCoverController`.

    Never calls `focus_force()` or `grab_set()`, never sends input to any process, sizes to a
    single monitor (`winfo_screenwidth` x `winfo_screenheight`), yields `-topmost` on `Alt+Tab`,
    and provides a visible Cancel button.
    """

    def __init__(self, parent, controller, *, palette=None, font_family="Consolas", fullscreen=True, on_closed=None):
        import tkinter as tk
        from tkinter import ttk

        self.controller = controller
        self._on_closed = on_closed
        self._destroyed = False
        if controller._foreground_fn is None and os.name == "nt":
            initial_fg = foreground_pid_win32()
            allowed = (initial_fg,) if initial_fg and controller._pids_fn is None else ()
            controller._foreground_fn = lambda pids=(): foreground_kind_win32(pids, allowed_pids=allowed)
        c = dict(palette or {
            "bg": "#0d1117", "panel": "#161b22", "field": "#010409", "border": "#30363d",
            "fg": "#e6edf3", "muted": "#8b949e", "accent": "#58a6ff", "ok": "#3fb950",
            "warn": "#d29922", "bad": "#f85149",
        })

        self.win = tk.Toplevel(parent) if parent is not None else tk.Tk()
        self.win.title("FO4SF Start Cover")
        self.win.configure(background=c["bg"])
        self.win.overrideredirect(True)
        if fullscreen:
            w = max(640, int(self.win.winfo_screenwidth()))
            h = max(480, int(self.win.winfo_screenheight()))
            self.win.geometry(f"{w}x{h}+0+0")
        else:
            self.win.geometry("760x420+80+80")
        try:
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass

        # Apply WS_EX_NOACTIVATE on Windows so Starfield retains keyboard/controller focus.
        try:
            self.win.update_idletasks()
            apply_win32_noactivate(self.win.winfo_id())
        except Exception:
            pass

        outer = tk.Frame(self.win, bg=c["bg"], padx=48, pady=48)
        outer.pack(fill="both", expand=True)

        card = tk.Frame(outer, bg=c["panel"], highlightbackground=c["border"], highlightthickness=1, padx=36, pady=32)
        card.place(relx=0.5, rely=0.5, anchor="center")

        banner_text = "\n".join(COVER_BANNER_LINES)
        tk.Label(card, text=banner_text, bg=c["panel"], fg=c["accent"],
                 font=(font_family, 11, "bold"), justify="left").pack(anchor="w")

        tk.Label(
            card,
            text="Preparing standalone Fallout session — Starfield startup & menu hidden.",
            bg=c["panel"], fg=c["fg"], font=(font_family, 11), pady=12,
        ).pack(anchor="w")

        stages_box = tk.Frame(card, bg=c["field"], highlightbackground=c["border"], highlightthickness=1, padx=18, pady=14)
        stages_box.pack(fill="x", pady=(4, 14))
        for _key, line in COVER_STAGE_LINES:
            tk.Label(stages_box, text=line, bg=c["field"], fg=c["ok"],
                     font=(font_family, 10), anchor="w").pack(fill="x", pady=2)

        self.timer_var = tk.StringVar(value=controller.snapshot()["timer_text"])
        tk.Label(card, textvariable=self.timer_var, bg=c["panel"], fg=c["muted"],
                 font=(font_family, 10)).pack(anchor="w", pady=(0, 16))

        bottom = tk.Frame(card, bg=c["panel"])
        bottom.pack(fill="x")
        tk.Label(
            bottom,
            text="Crash guard has priority · Cover never sends input or locks logs",
            bg=c["panel"], fg=c["muted"], font=(font_family, 9),
        ).pack(side="left")
        self.cancel_button = ttk.Button(bottom, text="Cancel / Hide cover (Esc)", command=self.cancel)
        self.cancel_button.pack(side="right")
        self.win.bind("<Escape>", lambda _e: self.cancel())

        if controller.state == "idle":
            controller.start()
        self._schedule_tick()

    def _schedule_tick(self):
        if self._destroyed:
            return
        snap = self.controller.poll()
        self.timer_var.set(snap["timer_text"])
        try:
            self.win.attributes("-topmost", bool(snap["topmost"]))
        except Exception:
            pass
        if not snap["active"]:
            self.close()
            return
        self.win.after(POLL_INTERVAL_MS, self._schedule_tick)

    def cancel(self):
        snap = self.controller.cancel()
        self.close(snap)

    def close(self, snap=None):
        if self._destroyed:
            return
        self._destroyed = True
        final = snap or self.controller.snapshot()
        try:
            self.win.destroy()
        except Exception:
            pass
        if self._on_closed is not None:
            self._on_closed(final)
