"""`launcher.py play`: apply the launcher settings, start Starfield, and (when the crash watcher is on) watch it from
start to exit (owner, 2026-10-21: "rebuild the crash watcher to be allowed to start and close with the game").

The old watcher (C:\\Modding\\tools\\crashwatch.cmd on the owner's PC) was a loop the player started by hand:
`procdump64.exe -accepteula -e 1 -f "80000003" -ma -n 1 -w Starfield.exe <folder>`, again and again, all day. It
caught the museum crashes (three full dumps, ACCESS_VIOLATION at Starfield.exe+0x2bf016b), but:
  - it ran whether or not anyone was playing, and only stopped when someone killed it;
  - `-w` attached the instant Starfield.exe appeared, the leading lead for Steam's "ERROR 84" launch failures;
  - full dumps only (about 18 GB each);
  - a silent exit (no exception, no Windows error report: 21 Oct 11:03:25) left nothing behind at all.

Here the watcher lives exactly as long as one game:
  1. the settings are applied with the game closed (bridge held off or put back, Papyrus logging);
  2. the game is started (Steam or Starfield.exe, `route`);
  3. once Starfield.exe has stayed up `settle_s` seconds, ProcDump attaches to that process id (no `-w`), with the
     old watcher's triggers (`-e 1 -f 80000003`: the assertion stop, and unhandled exceptions, which caught the three
     museum dumps) and, when asked, `-t` (a dump at any exit);
  4. this process holds its own handle on the game, so when the game ends, by a crash, a silent exit or a quit, it
     logs the exit code and its name to crashwatch.log, with the dumps written in that run;
  5. ProcDump detaches and exits by itself when the game ends. It is never killed here: a dump cut short is useless
     (docs/PLAY-AND-TEST.md); if it is still writing after `dump_wait_s`, play says so and leaves it running.
With the watcher off, play still starts the game and prints its exit code (a handle costs nothing).

Everything Windows-specific goes through a `System` object, so the flow is tested on synthetic stand-ins.
"""
import datetime
import os
import subprocess
import sys
import time

from . import detect, settings as settings_mod

STEAM_URL = "steam://rungameid/1716740"
ATTACH_CHECK_S = 5.0               # how long ProcDump must stay up after attaching before the watcher counts as armed
GAME_EXE = "Starfield.exe"
BRIDGE = "FO4SFBridge.esm"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PLUGIN_TOGGLE = os.path.join(REPO, "scripts", "game", "plugin_toggle.py")

# Windows NTSTATUS / exception codes a game exit is likely to carry (winnt.h / ntstatus.h names)
EXIT_NAMES = {
    0: "normal exit (also what a silent ExitProcess gives)",
    1: "exit code 1",
    0xC0000005: "ACCESS_VIOLATION",
    0x80000003: "BREAKPOINT (the engine's assertion stop)",
    0xC0000409: "STACK_BUFFER_OVERRUN (a fast fail)",
    0xC00000FD: "STACK_OVERFLOW",
    0xC0000374: "HEAP_CORRUPTION",
    0xC000001D: "ILLEGAL_INSTRUCTION",
    0xC0000017: "NO_MEMORY",
    0xC000013A: "CONTROL_C_EXIT (closed from outside)",
    0x40010004: "DBG_TERMINATE_PROCESS (ended by a debugger)",
}


def exit_name(code):
    if code is None:
        return "unknown (no handle on the game)"
    code &= 0xFFFFFFFF
    return f"0x{code:08X} {EXIT_NAMES.get(code, 'not a known crash code')}"


def procdump_argv(values, pid):
    """ProcDump's command line for one game process."""
    cw = lambda k: values["crash_watch." + k]          # noqa: E731
    argv = [cw("procdump"), "-accepteula", "-ma" if cw("dump") == "full" else "-mm"]
    if cw("catch_assertion"):
        argv += ["-e", "1", "-f", "80000003"]
    else:
        argv += ["-e"]
    if cw("dump_on_exit"):
        argv += ["-t"]
    # one dump per game; -t needs room for the exit dump after an exception dump
    argv += ["-n", "2" if cw("dump_on_exit") else "1", str(pid), cw("folder")]
    return argv


class System:
    """The real Windows calls. Tests pass a stand-in with the same methods."""

    def now(self):
        return time.time()

    def sleep(self, s):
        time.sleep(s)

    def pids(self, image=GAME_EXE):
        """Process ids running `image` (tasklist, no extra package)."""
        if os.name != "nt":
            return []
        r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True)
        out = []
        for line in r.stdout.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[0].casefold() == image.casefold() and parts[1].isdigit():
                out.append(int(parts[1]))
        return out

    def start_game(self, route, starfield):
        if route == "steam":
            os.startfile(STEAM_URL)                         # noqa: the Windows shell opens Steam's URL
        else:
            subprocess.Popen([os.path.join(starfield, GAME_EXE)], cwd=starfield)

    def open_process(self, pid):
        """A handle that stays valid after the process ends, so its exit code can be read; None if refused."""
        import ctypes
        SYNCHRONIZE, QUERY_LIMITED = 0x00100000, 0x1000
        h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE | QUERY_LIMITED, False, pid)
        return h or None

    def wait_exit(self, handle):
        """Blocks until the process ends; returns its exit code."""
        import ctypes
        k = ctypes.windll.kernel32
        k.WaitForSingleObject(handle, 0xFFFFFFFF)
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(handle, ctypes.byref(code))
        k.CloseHandle(handle)
        return code.value if ok else None

    def spawn(self, argv, log_path):
        with open(log_path, "ab") as log:                 # the child keeps its own copy of the handle
            return subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)

    def run(self, argv):
        r = subprocess.run(argv, capture_output=True, text=True)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def free_gb(self, path):
        return detect.free_gb(path)


def _log(path, line):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {line}\n")


def dumps_since(folder, t0):
    if not folder or not os.path.isdir(folder):
        return []
    return sorted(n for n in os.listdir(folder)
                  if n.lower().endswith(".dmp") and os.path.getmtime(os.path.join(folder, n)) >= t0 - 1)


def apply_bridge(values, starfield, system, say):
    """bridge=off holds FO4SFBridge.esm off through plugin_toggle.py; bridge=on puts back a hold. Raises on refusal."""
    want = values["bridge"]
    if want == "unchanged":
        return
    import json
    code, out = system.run([sys.executable, PLUGIN_TOGGLE, "status", "--starfield", starfield])
    if code:
        raise ValueError(f"bridge: plugin_toggle.py status failed: {out.strip()}")
    st = json.loads(out.strip().splitlines()[-1])
    held = {p.casefold() for p in st.get("off", [])}
    owned = {p.casefold() for p in st.get("owned", [])}
    if BRIDGE.casefold() not in owned:
        say(f"bridge: {BRIDGE} is not installed; nothing to turn {want}")
        return
    if want == "off" and BRIDGE.casefold() not in held:
        argv = [sys.executable, PLUGIN_TOGGLE, "off", "--plugins", BRIDGE, "--starfield", starfield,
                "--why", "launcher setting bridge=off"]
    elif want == "on" and BRIDGE.casefold() in held:
        argv = [sys.executable, PLUGIN_TOGGLE, "on", "--plugins", BRIDGE, "--starfield", starfield]
    else:
        say(f"bridge: already {want}")
        return
    code, out = system.run(argv)
    if code:
        raise ValueError(f"bridge: plugin_toggle.py {want} refused: {out.strip()}")
    say(f"bridge: turned {want}")


PAPYRUS = ("bEnableLogging", "bEnableTrace", "bLoadDebugInformation")


def set_papyrus(text, on):
    """StarfieldCustom.ini text with the three [Papyrus] keys set to 1 (on) or 0 (off); everything else kept.
    Returns (new_text, changed)."""
    v = "1" if on else "0"
    lines, out, in_sec, seen, found, changed = text.splitlines(), [], False, set(), False, False

    def close():
        nonlocal changed
        for k in PAPYRUS:
            if k.lower() not in seen:
                out.append(f"{k}={v}")
                changed = True
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if in_sec:
                close()
            in_sec = s.lower() == "[papyrus]"
            found = found or in_sec
            out.append(line)
            continue
        if in_sec and "=" in s:
            k, old = (x.strip() for x in s.split("=", 1))
            hit = next((p for p in PAPYRUS if p.lower() == k.lower()), None)
            if hit:
                seen.add(hit.lower())
                if old != v:
                    out.append(f"{hit}={v}")
                    changed = True
                    continue
        out.append(line)
    if in_sec:
        close()
    if not found:
        out += ["[Papyrus]"] + [f"{k}={v}" for k in PAPYRUS]
        changed = True
    return "\n".join(out) + "\n", changed


def apply_papyrus(values, say):
    want = values["papyrus_logging"]
    if want == "unchanged":
        return
    path = os.path.join(values["my_games"], "StarfieldCustom.ini")
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            old = f.read()
    new, changed = set_papyrus(old, want == "on")
    if not changed:
        say(f"papyrus logging: already {want} in {path}")
        return
    if os.path.exists(path):
        bak = path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        with open(bak, "w", encoding="utf-8") as f:
            f.write(old)
        say(f"papyrus logging: kept {bak}")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    except OSError as e:
        raise ValueError(f"papyrus logging: cannot write {path} ({e.strerror or e}); Windows Controlled Folder Access "
                         "may block Python in Documents") from None
    say(f"papyrus logging: turned {want} in {path}")


def play(values, starfield, system=None, say=print, start_timeout_s=180.0, dump_wait_s=3600.0, dry_run=False):
    """Apply the settings, start the game and watch it to its end. Returns a result dict; raises ValueError on a
    refusal (nothing started)."""
    system = system or System()
    bad = settings_mod.problems(values)
    cw = values["crash_watch.enabled"]
    if cw:
        if values["crash_watch.procdump"] and not os.path.isfile(values["crash_watch.procdump"]):
            bad.append(f"crash_watch.procdump: {values['crash_watch.procdump']} not found")
        if values["crash_watch.folder"]:
            free = system.free_gb(values["crash_watch.folder"])
            if free < values["crash_watch.min_free_gb"]:
                bad.append(f"crash watcher: {free:.1f} GB free for dumps, under crash_watch.min_free_gb "
                           f"{values['crash_watch.min_free_gb']:g}")
    if values["route"] == "exe" and not os.path.isfile(os.path.join(starfield, GAME_EXE)):
        bad.append(f"route=exe: {GAME_EXE} not found in {starfield}")
    if system.pids():
        bad.append("Starfield is already running: close it first (settings change only with the game closed, and "
                   "the watcher follows a game it started)")
    if bad:
        raise ValueError("; ".join(bad))
    log_path = os.path.join(values["crash_watch.folder"], "crashwatch.log") if cw else None
    plan = [f"bridge: {values['bridge']}", f"papyrus logging: {values['papyrus_logging']}",
            f"start: {values['route']}",
            "crash watcher: " + (f"on, {values['crash_watch.dump']} dumps to {values['crash_watch.folder']}"
                                 if cw else "off")]
    if dry_run:
        for p in plan:
            say(p)
        return {"dry_run": True, "plan": plan}
    if cw:
        try:                                        # before the game starts: the log must be writable (Codex, #449)
            os.makedirs(values["crash_watch.folder"], exist_ok=True)
            _log(log_path, "play: starting the game")
        except OSError as e:
            raise ValueError(f"crash watcher: cannot write to {values['crash_watch.folder']} ({e.strerror or e})") \
                from None
    apply_bridge(values, starfield, system, say)
    apply_papyrus(values, say)

    t0 = system.now()
    system.start_game(values["route"], starfield)
    early = []                     # processes that ended before they settled (a first launch can end within ~2 s)
    pid = handle = proc = None
    while pid is None and system.now() - t0 < start_timeout_s:
        found = [p for p in system.pids() if p not in early]
        if not found:
            system.sleep(1)
            continue
        cand = found[0]
        h = system.open_process(cand)
        settle_end = system.now() + values["crash_watch.settle_s"]
        while system.now() < settle_end and cand in system.pids():
            system.sleep(1)
        if cand not in system.pids():
            early.append(cand)
            code = system.wait_exit(h) if h else None
            say(f"process {cand} ended within {values['crash_watch.settle_s']:g} s ({exit_name(code)}); "
                "looking for the next one")
            if log_path:
                _log(log_path, f"process {cand} ended before it settled: {exit_name(code)}")
            continue
        pid, handle = cand, h
    if pid is None:
        say(f"Starfield did not stay up within {start_timeout_s:g} s; nothing to watch")
        if log_path:
            _log(log_path, "game did not stay up; watcher not armed")
        return {"started": False, "early": early}
    say(f"Starfield running (process {pid})")
    armed = False
    if cw:
        argv = procdump_argv(values, pid)
        try:
            proc = system.spawn(argv, log_path)
        except OSError as e:
            proc = None
            why = f"ProcDump did not start ({e.strerror or e})"
        else:
            # ProcDump stays up while it is attached; one that exits while the game still runs refused the
            # arguments or could not attach (its own message is in crashwatch.log)
            system.sleep(ATTACH_CHECK_S)
            rc = proc.poll()
            why = f"ProcDump exited at once (code {rc})" if rc is not None and pid in system.pids() else ""
            armed = not why
        if armed:
            _log(log_path, f"armed: process {pid}: " + " ".join(argv[1:-2]))
            say(f"crash watcher armed on process {pid} ({values['crash_watch.dump']} dumps)")
        else:
            _log(log_path, f"NOT armed on process {pid}: {why}; only the exit code will be logged")
            say(f"crash watcher NOT armed: {why}; only the exit code will be logged (see crashwatch.log)")
    code = system.wait_exit(handle) if handle else None
    result = {"started": True, "pid": pid, "early": early, "exit_code": code, "exit": exit_name(code),
              "seconds": round(system.now() - t0), "armed": armed}
    say(f"Starfield ended after {result['seconds']} s: {result['exit']}")
    if proc is not None:
        try:
            result["procdump_exit"] = proc.wait(timeout=dump_wait_s)
        except subprocess.TimeoutExpired:
            say(f"ProcDump is still running {dump_wait_s:g} s after the game ended (a dump still being written?); "
                "left running: never kill it mid-dump")
            result["procdump_running"] = True
    if cw:
        result["dumps"] = dumps_since(values["crash_watch.folder"], t0)
        note = " (a crash code and no dump)" if code not in (None, 0) and not result["dumps"] else ""
        _log(log_path, f"ended: process {pid}, {result['exit']}, after {result['seconds']} s, dumps: "
                       f"{', '.join(result['dumps']) or 'none'}{note}"
                       + (f", ProcDump exit {result['procdump_exit']}" if "procdump_exit" in result else ""))
        if result["dumps"]:
            say("dumps: " + ", ".join(result["dumps"]) + " (never upload a dump; docs/PLAY-AND-TEST.md)")
    return result
