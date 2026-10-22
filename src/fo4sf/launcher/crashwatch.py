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
import re
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


FULL_DUMP_GB = 20.0          # one -ma dump of the game: about 18 GB on the owner's PC


def needed_free_gb(values):
    """Free space the watcher needs: the floor, and with full dumps room for every dump ProcDump may write (-n)."""
    n = 2 if values["crash_watch.dump_on_exit"] else 1
    full = FULL_DUMP_GB * n if values["crash_watch.dump"] == "full" else 0.0
    return max(values["crash_watch.min_free_gb"], full)


def free_floor_text(values):
    need = needed_free_gb(values)
    if need > values["crash_watch.min_free_gb"]:
        return (f"{need:g} GB, room for {int(need // FULL_DUMP_GB)} full dumps of about {FULL_DUMP_GB:g} GB "
                "(crash_watch.dump=full)")
    return f"crash_watch.min_free_gb {values['crash_watch.min_free_gb']:g}"


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


INFINITE, WAIT_OBJECT_0 = 0xFFFFFFFF, 0


def declare_kernel32(k):
    """Give the kernel32 calls their real types. Without them ctypes reads OpenProcess's HANDLE as a C int, which
    can cut a 64-bit handle short (Grok's review, #465)."""
    from ctypes import POINTER, wintypes
    k.OpenProcess.restype, k.OpenProcess.argtypes = wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.GetExitCodeProcess.restype = wintypes.BOOL
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, POINTER(wintypes.DWORD)]
    k.CloseHandle.restype, k.CloseHandle.argtypes = wintypes.BOOL, [wintypes.HANDLE]
    return k


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
        h = declare_kernel32(ctypes.windll.kernel32).OpenProcess(SYNCHRONIZE | QUERY_LIMITED, False, pid)
        return h or None

    def wait_exit(self, handle):
        """Blocks until the process ends; returns its exit code, or None when the wait or the read failed."""
        import ctypes
        from ctypes import wintypes
        k = declare_kernel32(ctypes.windll.kernel32)
        waited = k.WaitForSingleObject(handle, INFINITE)
        code = wintypes.DWORD()
        # only a wait that returned WAIT_OBJECT_0 means the game ended: after a failed wait GetExitCodeProcess
        # would give STILL_ACTIVE (259) for a game still running (Grok's review, #465)
        ok = waited == WAIT_OBJECT_0 and k.GetExitCodeProcess(handle, ctypes.byref(code))
        k.CloseHandle(handle)
        return code.value if ok else None

    def spawn(self, argv, out_path):
        with open(out_path, "wb") as log:                 # the child keeps its own copy of the handle
            return subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT)

    def run(self, argv):
        r = subprocess.run(argv, capture_output=True, text=True)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def free_gb(self, path):
        return detect.free_gb(path)

    def plugins_active(self):
        """Casefolded names ticked in the player's Plugins.txt, or None when it cannot be read."""
        local = os.environ.get("LOCALAPPDATA", "")
        try:
            with open(os.path.join(local, "Starfield", "Plugins.txt"), encoding="utf-8-sig", errors="replace") as f:
                return {ln.strip()[1:].strip().casefold() for ln in f if ln.strip().startswith("*")}
        except OSError:
            return None


def decode_mixed(data):
    """ProcDump's redirected output starts with 8-bit text (its banner) and goes on in UTF-16LE, at any byte offset
    (seen on the PC, 2026-10-22): 8-bit up to the first two-byte unit with a zero high byte, UTF-16LE from there on,
    so a character outside Latin-1 in a path keeps both its bytes (Codex, #449)."""
    i = 2 if data.startswith(b"\xff\xfe") else 0
    start = i
    while i + 1 < len(data) and not (data[i] != 0 and data[i + 1] == 0):
        i += 1
    if i + 1 >= len(data):                          # no UTF-16 at all
        return data[start:].replace(b"\x00", b"").decode("cp1252", errors="replace")
    return data[start:i].decode("cp1252", errors="replace") + data[i:].decode("utf-16-le", errors="replace")


def fold_output(out_path, log_path):
    """Append a finished child's output file to crashwatch.log, decoded (ProcDump writes UTF-16 when its output is
    redirected), then remove the side file. Returns the text ("" when there is no file)."""
    try:
        with open(out_path, "rb") as f:
            data = f.read()
    except (OSError, TypeError):
        return ""
    text = decode_mixed(data)
    with open(log_path, "a", encoding="utf-8") as f:
        for line in text.splitlines():
            if line.strip():
                f.write(f"  procdump: {line.rstrip()}\n")
    try:
        os.remove(out_path)
    except OSError:
        pass
    return text


def dumps_confirmed(text, dumps):
    """True when ProcDump printed a "Dump N complete" line for every dump listed: a dump without one may be cut short
    (a full disk, a write error) and is not reported as usable (docs/PLAY-AND-TEST.md)."""
    return len(re.findall(r"Dump \d+ complete", text or "")) >= len(dumps)


def _log(path, line):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {line}\n")


def dump_names(folder):
    """The .dmp files in folder now."""
    if not folder or not os.path.isdir(folder):
        return set()
    return {n for n in os.listdir(folder) if n.lower().endswith(".dmp")}


def dumps_since(folder, before):
    """The dumps that appeared after the snapshot `before` (dump_names taken just before ProcDump attached): a dump
    of an earlier game is never listed, whatever its file time says (seen on the PC, 2026-10-21)."""
    return sorted(dump_names(folder) - set(before))


def apply_bridge(values, starfield, system, say):
    """bridge=off holds FO4SFBridge.esm off through plugin_toggle.py; bridge=on puts back a hold. Raises on refusal."""
    want = values["bridge"]
    if want == "unchanged":
        return
    import json
    # -I: plugin_toggle reads plugin headers and rewrites Plugins.txt, so no inherited PYTHONPATH or user site (AGENTS.md)
    code, out = system.run([sys.executable, "-I", PLUGIN_TOGGLE, "status", "--starfield", starfield])
    if code:
        raise ValueError(f"bridge: plugin_toggle.py status failed: {out.strip()}")
    st = json.loads(out.strip().splitlines()[-1])
    held = {p.casefold() for p in st.get("off", [])}
    owned = {p.casefold() for p in st.get("owned", [])}
    if BRIDGE.casefold() not in owned:
        say(f"bridge: {BRIDGE} is not installed; nothing to turn {want}")
        return
    if want == "off":
        # run off even for a recorded hold: the game may have ticked the bridge again, and a repeated off unticks it
        # (plugin_toggle.py prints "already held off" when nothing needs doing) (Codex, #449)
        argv = [sys.executable, "-I", PLUGIN_TOGGLE, "off", "--plugins", BRIDGE, "--starfield", starfield,
                "--why", "launcher setting bridge=off"]
    elif want == "on" and BRIDGE.casefold() in held:
        argv = [sys.executable, "-I", PLUGIN_TOGGLE, "on", "--plugins", BRIDGE, "--starfield", starfield]
    else:
        # not held is not proof of on: a restore that could not load the bridge releases the hold and leaves it
        # unticked (Codex, #449)
        active = system.plugins_active()
        if active is None or BRIDGE.casefold() not in active:
            raise ValueError(f"bridge=on: {BRIDGE} is installed and not held off, but "
                             + ("Plugins.txt cannot be read" if active is None else "it is not active in Plugins.txt")
                             + ": reinstall the bridge or tick it in the game, then play again")
        say(f"bridge: already {want}")
        return
    code, out = system.run(argv)
    if code:
        raise ValueError(f"bridge: plugin_toggle.py {want} refused: {out.strip()}")
    if want == "on" and not bridge_came_back(out):
        # plugin_toggle releases a hold it cannot restore (the plugin or a master cannot load) and still exits 0:
        # the bridge is then unticked, so the game must not start as if it ran (Codex, #449)
        raise ValueError(f"bridge: {BRIDGE} did not come back on: {out.strip()}")
    say(f"bridge: turned {want}")


def bridge_came_back(out):
    """True when plugin_toggle.py on reports the bridge among those ticked back ("back on: A, B; ...")."""
    for line in out.splitlines():
        if line.startswith("back on:"):
            names = line[len("back on:"):].split(";", 1)[0]
            return BRIDGE.casefold() in {n.strip().casefold() for n in names.split(",")}
    return False


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
    try:
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
        # written beside it and swapped in whole: a failed write never leaves the live INI cut short (Codex, #449)
        tmp = path + ".fo4sf-tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(new)
            os.replace(tmp, path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
    except OSError as e:
        raise ValueError(f"papyrus logging: cannot read or write {path} ({e.strerror or e}); Windows Controlled "
                         "Folder Access may block Python in Documents") from None
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
            if free < needed_free_gb(values):
                bad.append(f"crash watcher: {free:.1f} GB free for dumps, under {free_floor_text(values)}")
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
            "crash watcher: " + (f"on, {values['crash_watch.dump']} dumps to {values['crash_watch.folder']}, "
                                 + ("a dump on every exit" if values["crash_watch.dump_on_exit"]
                                    else "log only when the game exits without a crash")
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
    # never a blind bridge, even half way: logging goes on before the bridge comes back, and off only after the
    # bridge is held (Codex, #449)
    if values["bridge"] == "on":
        apply_papyrus(values, say)
        apply_bridge(values, starfield, system, say)
    else:
        apply_bridge(values, starfield, system, say)
        apply_papyrus(values, say)

    t0 = system.now()
    try:
        system.start_game(values["route"], starfield)
    except OSError as e:                            # no steam:// handler, or the exe would not start (Codex, #465)
        why = f"could not start the game by {values['route']} ({e.strerror or e})"
        if cw:
            _log(log_path, f"play: {why}")
        raise ValueError(why) from None
    return _follow(values, system, say, t0, log_path, start_timeout_s, dump_wait_s)


def _follow(values, system, say, t0, log_path, start_timeout_s, dump_wait_s, only_pid=None, seen=()):
    """Find a Starfield.exe that stays up settle_s, attach ProcDump when the watcher is on, wait for its end and log
    it. only_pid follows that one process; seen are process ids already watched (never picked again)."""
    cw = values["crash_watch.enabled"]
    early = list(seen)             # processes that ended before they settled (a first launch can end within ~2 s)
    pid = handle = proc = None
    while pid is None and system.now() - t0 < start_timeout_s:
        found = [p for p in system.pids() if p not in early and (only_pid is None or p == only_pid)]
        if not found:
            system.sleep(1)
            continue
        cand = found[0]
        seen_at = system.now()                     # "after S s" counts from here, not from when the watch began
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
        pid, handle, up_since = cand, h, seen_at
    if pid is None:
        say(f"Starfield did not stay up within {start_timeout_s:g} s; nothing to watch")
        if log_path:
            _log(log_path, "game did not stay up; watcher not armed")
        return {"started": False, "early": [p for p in early if p not in seen]}
    say(f"Starfield running (process {pid})")
    armed = False
    out_path = None
    pd_text = ""                    # ProcDump's report, folded at the attach check if it quit by then, else at the end
    if cw:
        argv = procdump_argv(values, pid)
        # ProcDump's own output goes to a side file first: it writes UTF-16 when redirected, which would leave
        # crashwatch.log spaced out; fold_output appends it decoded once ProcDump has ended
        # one name per run: a report a timed-out ProcDump left behind on a reused process id stays as it is (Codex, #449)
        out_path = os.path.join(values["crash_watch.folder"], f"procdump_{pid}_{int(system.now())}.out")
        before = dump_names(values["crash_watch.folder"])
        try:
            proc = system.spawn(argv, out_path)
        except OSError as e:
            proc = None
            why = f"ProcDump did not start ({e.strerror or e})"
        else:
            # ProcDump stays up while it is attached; one that exits while the game still runs refused the
            # arguments or could not attach (its own message is in crashwatch.log)
            system.sleep(ATTACH_CHECK_S)
            rc = proc.poll()
            why = ""
            if rc is not None:
                pd_text = fold_output(out_path, log_path)
                if pid in system.pids():
                    why = f"ProcDump exited at once (code {rc})"
                elif not re.search(r"Dump \d+ complete|Dump count (not )?reached", pd_text):
                    # the game ended inside the check too: only this run's own report shows its ProcDump had attached,
                    # by a finished dump or by its end-of-watch line (a normal quit prints "Dump count not reached");
                    # a new file in the folder may be an earlier ProcDump's (Codex, #449)
                    why = f"ProcDump ended with the game inside the attach check and reported no watch (code {rc})"
            armed = not why
        if armed:
            _log(log_path, f"armed: process {pid}: " + " ".join(argv[1:-2]))
            say(f"crash watcher armed on process {pid} ({values['crash_watch.dump']} dumps)")
        else:
            _log(log_path, f"NOT armed on process {pid}: {why}; only the exit code will be logged")
            say(f"crash watcher NOT armed: {why}; only the exit code will be logged (see crashwatch.log)")
    if handle:
        code = system.wait_exit(handle)
    else:                           # Windows refused a handle: follow the process id; the exit code stays unknown
        say(f"no handle on process {pid}: following it by process id, the exit code will be unknown")
        while pid in system.pids():
            system.sleep(2)
        code = None
    result = {"started": True, "pid": pid, "early": [p for p in early if p not in seen], "exit_code": code, "exit": exit_name(code),
              "seconds": round(system.now() - up_since), "armed": armed}
    say(f"Starfield ended after {result['seconds']} s up: {result['exit']}")
    if proc is not None:
        try:
            result["procdump_exit"] = proc.wait(timeout=dump_wait_s)
            pd_text += fold_output(out_path, log_path)
        except subprocess.TimeoutExpired:
            say(f"ProcDump is still running {dump_wait_s:g} s after the game ended (a dump still being written?); "
                "left running: never kill it mid-dump")
            result["procdump_running"] = True
    if cw:
        new = dumps_since(values["crash_watch.folder"], before)
        if result.get("procdump_running"):     # no report yet: every new file is listed, and marked unconfirmed below
            result["dumps"] = new
        else:
            # only the dumps this run's ProcDump names in its report ("Dump 1 initiated: <path>"): a file another
            # ProcDump, left running after an earlier timeout, wrote meanwhile is not this game's (Codex, #449)
            result["dumps"] = [d for d in new if d in pd_text]
            if len(result["dumps"]) < len(new):
                result["dumps_other"] = [d for d in new if d not in result["dumps"]]
        note = " (a crash code and no dump)" if code not in (None, 0) and not result["dumps"] else ""
        if result["dumps"] and result.get("procdump_running"):
            result["dumps_unconfirmed"] = True
            note += " (still being written: not usable until ProcDump says it is complete)"
        elif result["dumps"] and not dumps_confirmed(pd_text, result["dumps"]):
            result["dumps_unconfirmed"] = True
            note += " (ProcDump did not report every dump complete: may be cut short, see the procdump lines)"
        _log(log_path, f"ended: process {pid}, {result['exit']}, after {result['seconds']} s up, dumps: "
                       f"{', '.join(result['dumps']) or 'none'}{note}"
                       + (f", ProcDump exit {result['procdump_exit']}" if "procdump_exit" in result else "")
                       + (f"; not this run's: {', '.join(result['dumps_other'])}" if result.get("dumps_other") else ""))
        if result["dumps"]:
            say("dumps: " + ", ".join(result["dumps"])
                + (" (NOT confirmed complete)" if result.get("dumps_unconfirmed") else "")
                + " (never upload a dump; docs/PLAY-AND-TEST.md)")
    return result


def watch(values, system=None, say=print, pid=None, repeat=False, start_timeout_s=600.0, dump_wait_s=3600.0,
          dry_run=False):
    """Watch a game something else starts (the test runner's own launch): wait for Starfield.exe (or process pid),
    let it settle, attach ProcDump as play does and log its end. Changes no setting and starts nothing. With repeat,
    goes on to the next game until none appears within start_timeout_s. Returns the list of results; raises
    ValueError on a refusal."""
    system = system or System()
    if not values["crash_watch.enabled"]:
        raise ValueError("crash watcher is off in the launcher settings (crash_watch.enabled): nothing to watch with")
    bad = [p for p in settings_mod.problems(values) if p.startswith("crash_watch.")]
    if values["crash_watch.procdump"] and not os.path.isfile(values["crash_watch.procdump"]):
        bad.append(f"crash_watch.procdump: {values['crash_watch.procdump']} not found")
    if values["crash_watch.folder"]:
        free = system.free_gb(values["crash_watch.folder"])
        if free < needed_free_gb(values):
            bad.append(f"crash watcher: {free:.1f} GB free for dumps, under {free_floor_text(values)}")
    if bad:
        raise ValueError("; ".join(bad))
    log_path = os.path.join(values["crash_watch.folder"], "crashwatch.log")
    what = f"process {pid}" if pid is not None else "the next Starfield.exe" + (" and each one after" if repeat else "")
    plan = [f"watch: {what}, attaching after {values['crash_watch.settle_s']:g} s",
            f"crash watcher: on, {values['crash_watch.dump']} dumps to {values['crash_watch.folder']}, "
            + ("a dump on every exit" if values["crash_watch.dump_on_exit"]
               else "log only when the game exits without a crash")]
    if dry_run:
        for p in plan:
            say(p)
        return [{"dry_run": True, "plan": plan}]
    try:
        os.makedirs(values["crash_watch.folder"], exist_ok=True)
        _log(log_path, f"watch: waiting for {what}")
    except OSError as e:
        raise ValueError(f"crash watcher: cannot write to {values['crash_watch.folder']} ({e.strerror or e})") from None
    results, seen = [], []
    while True:
        if results:                                 # each dump takes room: the floor holds for every game (Codex, #449)
            free = system.free_gb(values["crash_watch.folder"])
            if free < needed_free_gb(values):
                why = f"{free:.1f} GB free for dumps, under {free_floor_text(values)}; not watching the next game"
                _log(log_path, f"watch stopped: {why}")
                say(f"crash watcher stopped: {why}")
                results.append({"started": False, "stopped": why})
                return results
        t0 = system.now()
        r = _follow(values, system, say, t0, log_path, start_timeout_s, dump_wait_s, only_pid=pid, seen=seen)
        results.append(r)
        seen += r.get("early", []) + ([r["pid"]] if r.get("started") else [])
        if repeat and r.get("procdump_running"):    # never attach again while the last dump may still grow (Codex, #449)
            why = f"ProcDump on process {r['pid']} is still running; not watching the next game"
            _log(log_path, f"watch stopped: {why}")
            say(f"crash watcher stopped: {why}")
            results.append({"started": False, "stopped": why})
            return results
        if not (repeat and r.get("started") and pid is None):
            return results
