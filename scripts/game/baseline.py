"""The vanilla baseline (docs/testing/baseline.md): one plain Starfield New Game with every plugin the game does not
ship turned off, so its Papyrus log says which errors Starfield makes on its own. A run of ours is then compared with
it (fo4sf.core.papyrus_log), and only what is new is ours to chase.

usage: python -I scripts\\game\\baseline.py check   --starfield <game dir> [--allow-off]
       python -I scripts\\game\\baseline.py prepare --starfield <game dir> --out <folder> [--allow-off]
         (then start Starfield the plain way, Steam's Play or Starfield.exe, never the FO4SF Launcher or
          sfse_loader.exe; New Game, about 10 minutes, quit to the desktop)
       python -I scripts\\game\\baseline.py collect --out <folder>
       python -I scripts\\game\\baseline.py restore --out <folder> [--force]
       python -I scripts\\game\\baseline.py status  --out <folder>
       python -I scripts\\game\\baseline.py compare --out <folder> --run-log <a run's Papyrus.0.log> [--report <json>]
       (--my-games <My Games\\Starfield folder>: that one instead of the usual two places, OneDrive's Documents first)

check    reads the PC and writes nothing: the plugins prepare would turn off, the deployment gate's loaders and start
         checks (fo4sf.core.preflight) as they will read once those are off, the [Papyrus] logging keys, whether the
         open-baseline note names a baseline that may be open (noted(); prepare also looks in the folders next to its
         --out), and whether our plugins are off already with nothing else on (an earlier baseline never restored?
         --allow-off when no baseline turned them off).
prepare  refuses while Starfield runs, when --out holds a baseline (one never restored: restore it first) or is in
         the game folder, a My Games folder or Plugins.txt's folder, when the open-baseline note names a baseline that
         may be open (one never restored, or one whose note or record cannot be read: prepare would write over the
         only pointer to it, wherever its folder is), when a baseline of this Plugins.txt in a folder next to --out was
         never restored, or when check would refuse; records in <out>\\baseline.json Plugins.txt as it is (its bytes),
         the built-in plugins (names, sizes, sha256), Starfield.exe's identity, the sha256 of the Papyrus logs already
         there and the time; when it turns plugins off, notes the baseline as open (<the test runner's state
         folder>\\baseline-open.json), then unticks every active plugin the game does not ship (loadset.built_in: the
         official plugins and any SFBGS* or BlueprintShips-* plugin stay on; a guarded rewrite: nothing is written
         when Plugins.txt changed after it was read, and a write that fails removes the record and the note again).
collect  refuses while Starfield runs, after a restore that stopped before its record, and when the game folder is not
         readable; joins every Papyrus log of the My Games folders written after prepare and before restore
         (Papyrus.0.log, and the older ones the game has moved on), oldest first, into <out>, once. A log that was
         there at prepare (its sha256) is never taken, whatever its time. The session was not vanilla when its log
         names any of ours (FO4* or FOCC*), when Plugins.txt has a plugin the game does not ship ticked again (now, or
         when restore ran), or when SFSE wrote a log meanwhile (a start through sfse_loader.exe; found now, or when
         restore ran); and it is no baseline either when the game changed since prepare (the built-in plugins by name
         and size, Starfield.exe by size and sha256: a Steam update, and which build the session ran on is not known).
         The log is then kept as Papyrus.0.log.not-vanilla instead, and the baseline has none.
restore  refuses while Starfield runs; puts Plugins.txt back byte for byte, and ends the time collect takes logs from.
         The game rewrites Plugins.txt at startup (verified: docs/research/framework/launcher-sources/sfstack.md), so a
         rewrite that ticked no plugin is restored over; one that ticked a plugin the game does not ship refuses
         unless --force. Either way the file restore writes over is kept in <out> first (Plugins.txt.at-restore, then
         .2, .3: a copy an earlier restore kept is never written over). It records the plugins that were ticked and
         the SFSE logs of the baseline's time, and collect after it takes no log as the baseline when there were any.
         Before it writes Plugins.txt, it checks the record's copy against its sha256 and notes in the record what it
         found and when. A restore that stops before its record ended the baseline's time: the next one finishes the
         record with the first one's findings and time, and writes the recorded bytes back (keeping the file) also
         when Plugins.txt has the same plugins on in other bytes since (the game's rewrite at startup, or another
         program's order); other plugins on refuse unless --force.
status   what the record holds and where Plugins.txt stands, a restore that stopped before its record included.
compare  a run's Papyrus log against the baseline's: the groups of fo4sf.core.papyrus_log (only ours, only the run's
         Starfield scripts, the same message at the same script line in both, the same kind in both, only the
         baseline's), the most frequent kinds of each to stdout, every kind to --report (a .json file, never one of
         the baseline's own files, the run's log, Plugins.txt or the open-baseline note, nor in the game folder, a My
         Games folder or Plugins.txt's folder, and new or an earlier compare report); says whether the built-in
         plugins and Starfield.exe are still the recorded ones, and names the plugins not ours that the baseline
         turned off too. Refuses a baseline without a vanilla log.

prepare, collect and restore run one at a time, whatever their --out: each takes baseline.lock in the runner's state
folder, and one that finds it taken waits LOCK_WAIT_S, then refuses and changes nothing (fo4sf.core.filelock: the lock
of one that stopped is taken over after LOCK_STALE_S; on Windows, one whose command still runs cannot be).

Nothing here touches a plugin file, an archive or an INI. Outside <out> it writes only Plugins.txt and the
open-baseline note (each through a temp file beside it), the lock, and compare's --report where it is given; it makes
the state folder when it is not there, and Plugins.txt's folder when restore finds it gone.
"""
import argparse
import base64
import contextlib
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf.core import filelock, loadset, papyrus_log, preflight  # noqa: E402
from fo4sf.launcher import files, loadprobe  # noqa: E402
from fo4sf.launcher import restore as launcher_restore  # noqa: E402

SCHEMA = 1
RECORD = "baseline.json"
LOG_NAME = "Papyrus.0.log"
LOG_FILES = re.compile(r"Papyrus\.\d+\.log", re.IGNORECASE)
NOT_VANILLA = "Papyrus.0.log.not-vanilla"
COLLECTING = "Papyrus.0.log.collecting"
CHECKS = ("loaders", "start")
KEPT_AT_RESTORE = "Plugins.txt.at-restore"
OPEN_NOTE = "baseline-open.json"
LOCK = "baseline.lock"
# prepare, collect and restore wait LOCK_WAIT_S for each other; the lock of one that stopped is taken over after
# LOCK_STALE_S (fo4sf.core.filelock)
LOCK_WAIT_S, LOCK_STALE_S = 2.0, 900.0
BOM = b"\xef\xbb\xbf"


def game_running():
    return launcher_restore.game_running()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(raw):
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def b64(raw):
    return base64.b64encode(raw).decode("ascii")


def read_bytes(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def decoded(raw, tolerant=False):
    """Plugins.txt bytes as text, its BOM dropped. Text that is not UTF-8 refuses (prepare cannot untick bytes it
    cannot read; that the game writes UTF-8 is a hypothesis); tolerant replaces the bytes that do not decode instead
    (restore, looking for plugins ticked again)."""
    body = raw[len(BOM):] if raw.startswith(BOM) else raw
    if tolerant:
        return body.decode("utf-8", errors="replace")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as e:
        raise SystemExit(f"Plugins.txt is not UTF-8 ({e}): nothing changed") from None


def text_lines(raw, tolerant=False):
    return [] if raw is None else decoded(raw, tolerant).splitlines()


def turned_on(raw, tolerant=False):
    """The active plugins in Plugins.txt bytes that the game does not ship, in file order."""
    return [n for n in loadset.active_plugins(text_lines(raw, tolerant))
            if loadset.is_plugin(n) and not loadset.built_in(n)]


def same_on(rec, ticked):
    """True when the plugins ticked are the ones prepare turned off, in any order and case."""
    return {n.casefold() for n in ticked} == {n.casefold() for n in rec.get("turned_off") or []}


def untick(raw):
    """(the bytes with every active plugin the game does not ship unticked, [their names]); every other byte kept.
    A line that would still read as active afterwards refuses."""
    bom = BOM if raw.startswith(BOM) else b""
    out, off = [], []
    for line in decoded(raw).splitlines(keepends=True):
        body = line.rstrip("\r\n")
        name = loadset.name_of(body)
        if body.strip().startswith("*") and loadset.is_plugin(name) and not loadset.built_in(name):
            at = line.index("*")
            line = line[:at] + line[at:].lstrip("*")
            off.append(name)
        out.append(line)
    prepared = bom + "".join(out).encode("utf-8")
    left = turned_on(prepared)
    if left:
        raise SystemExit(f"Plugins.txt: a line naming {', '.join(left)} cannot be unticked (it still reads as active): "
                         f"nothing changed")
    return prepared, off


def off_already(lines):
    """Our plugins on inactive lines of Plugins.txt (comments aside)."""
    out = []
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith(("*", "#")) and loadset.ours(loadset.name_of(s)):
            out.append(loadset.name_of(s))
    return out


class AfterProbe(loadprobe.LoadProbe):
    """The PC as the checks will read it once prepare has unticked the plugins: Plugins.txt's lines are given."""

    def __init__(self, lines, *args, **kw):
        super().__init__(*args, **kw)
        self.lines = lines

    def plugins_txt_lines(self):
        return self.lines


def file_identity(path):
    if not os.path.isfile(path):
        return None
    return {"size": os.path.getsize(path), "sha256": files.sha256(path)}


def write_json(path, value):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=1)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())                          # on disk before it takes the name (a power cut)
        os.replace(tmp, path)
    except BaseException:
        remove(tmp)
        raise


def remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def load_record(out):
    p = os.path.join(out, RECORD)
    if not os.path.isfile(p):
        raise SystemExit(f"no baseline in {out} ({RECORD} is not there): prepare one first")
    try:
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
    except ValueError as e:
        raise SystemExit(f"{p}: not readable as a baseline record ({e})") from None
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA:
        raise SystemExit(f"{p}: not a baseline record of schema {SCHEMA}")
    return rec


def read_json(path):
    """The JSON object in path, None when there is none or it does not read as one."""
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def absent(path):
    """True only when path is known not to be there: a lookup that fails another way (no permission, a drive that
    does not answer) is not "absent" (os.path.lexists says False for both)."""
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return True
    except OSError:
        return False
    return False


def same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def under(path, folder):
    """True when path is folder or inside it."""
    p, f = (os.path.normcase(os.path.realpath(x)) for x in (path, folder))
    try:
        return os.path.commonpath([p, f]) == f
    except ValueError:                                    # another drive
        return False


def game_folder_of(path, starfield, my_games, plugins_txt):
    """The game's folder that path is in, as "<which>, <folder>", None when it is in none of them: the game folder, the
    My Games folders and Plugins.txt's folder hold the game's own files, which the baseline never writes over."""
    folders = [(starfield, "the game folder")] + [(d, "a My Games folder") for d in my_games or []]
    folders.append((os.path.dirname(plugins_txt or ""), "Plugins.txt's folder"))
    for folder, what in folders:
        if folder and under(path, folder):
            return f"{what}, {folder}"
    return None


def unrestored(rec):
    """True for a record whose prepare turned plugins off and whose restore has not run: it holds the only copy of
    Plugins.txt as it was."""
    return rec.get("prepared_sha256") is not None and not rec.get("restored_at")


def state_dir():
    """The test runner's state folder (testqueue.py Controls.state_dir): FO4_AI_TEAM_STATE, else
    %LOCALAPPDATA%\\fo4-ai-team\\state."""
    return os.environ.get("FO4_AI_TEAM_STATE") or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                                                                "fo4-ai-team", "state")


def open_note_path():
    """The open-baseline note: the folder of the baseline prepare last turned plugins off for, until its restore."""
    return os.path.join(state_dir(), OPEN_NOTE)


def close_open_note(out, rec=None):
    """Removes the open-baseline note when it names this baseline: its folder, or (a folder moved since prepare) the
    same Plugins.txt and prepare time as its record."""
    note = read_json(open_note_path())
    if not note:
        return
    here = isinstance(note.get("out"), str) and same_path(note["out"], out)
    moved = (rec is not None and rec.get("prepared_at") and note.get("prepared_at") == rec["prepared_at"]
             and isinstance(note.get("plugins_txt"), str) and isinstance(rec.get("plugins_txt"), str)
             and same_path(note["plugins_txt"], rec["plugins_txt"]))
    if here or moved:
        remove(open_note_path())


def noted(state):
    """What the open-baseline note in the state folder says, read so that any unknown counts as open: None when it
    names no baseline that may be open (there is no note, the folder it names is there without a record, or that
    record's restore ran; absent(): a lookup that fails counts as there), else (out, rec): the folder it names, None
    when the note cannot be read, and that folder's record, None when it cannot be read (a drive not there, a damaged
    or missing file). testqueue.py's runner and prepare read it alike: the note is the only pointer to a baseline
    whose folder is anywhere."""
    path = os.path.join(state, OPEN_NOTE)
    if absent(path):
        return None
    note = read_json(path)
    out = note.get("out") if note else None
    if not isinstance(out, str):
        return None, None
    record = os.path.join(out, RECORD)
    if os.path.isdir(out) and absent(record):
        return None                                       # the baseline folder was emptied: nothing open there
    rec = read_json(record)
    if rec is not None and not unrestored(rec):
        return None
    return out, rec


def holds_open(folder, plugins_txt):
    """True when folder holds a baseline of this Plugins.txt that was never restored."""
    rec = read_json(os.path.join(folder, RECORD))
    return (rec is not None and unrestored(rec) and isinstance(rec.get("plugins_txt"), str)
            and same_path(rec["plugins_txt"], plugins_txt))


def open_problems(plugins_txt, out=None):
    """Why a baseline other than out's may be open, [] when none is: the one the open-baseline note names (noted(): an
    unreadable note or record counts, since prepare would write over the only pointer to it), then any baseline of
    this Plugins.txt next to out (the same parent folder: the note goes when the state folder does) that was never
    restored."""
    problems, seen = [], []
    found = noted(state_dir())
    if found is not None:
        d, rec = found
        if d is None:
            problems.append(f"the open-baseline note {open_note_path()} cannot be read, so a baseline may be open: "
                            f"restore it, or remove the note once you know none is")
        elif rec is None:
            seen.append(d)
            problems.append(f"the open-baseline note names {d}, whose record cannot be read (a drive not there, or a "
                            f"damaged {RECORD}?), so that baseline may be open: restore it first, or remove the note "
                            f"once you know it is not")
        else:
            seen.append(d)
            mine = isinstance(rec.get("plugins_txt"), str) and same_path(rec["plugins_txt"], plugins_txt)
            problems.append(f"{d} holds a baseline of {'this Plugins.txt' if mine else rec.get('plugins_txt')} that "
                            f"was never restored: restore it first (baseline.py restore --out {d})")
    if out:
        parent = os.path.dirname(out)
        try:
            names = sorted(os.listdir(parent))
        except OSError:
            names = []
        for n in names:
            d = os.path.join(parent, n)
            if not same_path(d, out) and not any(same_path(d, f) for f in seen) and holds_open(d, plugins_txt):
                seen.append(d)
                problems.append(f"{d} holds a baseline of this Plugins.txt that was never restored: restore it first "
                                f"(baseline.py restore --out {d})")
    return problems


def survey(a, out=None):
    """What prepare would do, read from the PC: {plugins_txt, raw, off, prepared, my_games, report, problems, probe}."""
    pt = loadprobe.plugins_txt_path()
    if pt is None:
        raise SystemExit("LOCALAPPDATA is not an absolute folder: Plugins.txt cannot be located (Windows only)")
    if not os.path.isdir(os.path.join(a.starfield, "Data")):
        raise SystemExit(f"no Data folder in {a.starfield}: --starfield is the game folder")
    raw = read_bytes(pt)
    prepared, off = untick(raw) if raw is not None else (None, [])
    my_games = loadprobe.my_games_dirs(a.my_games)
    probe = AfterProbe(text_lines(prepared), a.starfield, my_games, pt, (), {"start_overrides": []})
    rep = preflight.run_gate(probe, CHECKS)
    problems = [c.line() for c in rep.failing]
    where = game_folder_of(out, os.path.abspath(a.starfield), my_games, pt) if out else None
    if where:
        problems.append(f"{out} is in {where}: give the baseline a folder of its own, outside the game's folders")
    if not preflight.papyrus_logging_on(probe.ini_texts()):
        keys = " ".join(f"{k}={v}" for k, v in preflight.PAPYRUS_KEYS)
        problems.append(f"[Papyrus] {keys} not in effect (StarfieldCustom.ini overrides Starfield.ini): the session "
                        f"would write no log (scripts/bridge/make_bridge.py ini sets them)")
    problems += open_problems(pt, out)
    left_off = off_already(text_lines(raw)) if not any(loadset.ours(n) for n in off) else []
    if left_off and not getattr(a, "allow_off", False):
        problems.append(f"none of ours is on, and {', '.join(left_off)} are off in Plugins.txt already: an earlier "
                        f"baseline that was never restored? (restore it first; --allow-off if no baseline turned them "
                        f"off)")
    if off and not os.access(pt, os.W_OK):
        problems.append(f"{pt} is read-only: prepare cannot turn plugins off (clear its Read-only attribute first)")
    if off and os.path.islink(pt):
        problems.append(f"{pt} is a link: prepare would put a plain file in its place, and restore would bring the "
                        f"bytes back but not the link")
    if game_running():
        problems.append("Starfield is running (or its state is unknown): close it first")
    return {"plugins_txt": pt, "raw": raw, "off": off, "prepared": prepared, "my_games": my_games, "report": rep,
            "problems": problems, "probe": probe}


def check(a):
    s = survey(a)
    print(f"Plugins.txt: {s['plugins_txt']}" + ("" if s["raw"] is not None else " (not there yet)"))
    print(f"prepare would turn off: {', '.join(s['off']) or 'nothing (only the game plugins are on)'}")
    print("My Games: " + (", ".join(s["my_games"]) or "none found"))
    for line in s["report"].lines()[1:]:
        print(line)
    for p in s["problems"]:
        print(f"refused: {p}")
    print("check: prepare would refuse" if s["problems"] else "check: prepare would go ahead")
    return 1 if s["problems"] else 0


def prepare(a):
    out = os.path.abspath(a.out)
    record = os.path.join(out, RECORD)
    if os.path.exists(record):
        if unrestored(load_record(out)):
            raise SystemExit(f"prepare: {out} holds a baseline that was never restored, and its record holds the only "
                             f"copy of Plugins.txt as it was: run restore --out {out} first")
        raise SystemExit(f"prepare: {out} already holds a baseline ({RECORD}); use a new --out folder")
    s = survey(a, out)
    if s["problems"]:
        raise SystemExit("prepare: refused, nothing changed:\n  " + "\n  ".join(s["problems"]))
    raw = s["raw"]
    rec = {"schema": SCHEMA, "prepared_at": now_iso(), "prepared_epoch": time.time(),
           "starfield": os.path.abspath(a.starfield), "my_games": s["my_games"], "plugins_txt": s["plugins_txt"],
           "plugins_txt_b64": None if raw is None else b64(raw), "plugins_txt_sha256": sha256_bytes(raw),
           "turned_off": s["off"], "prepared_sha256": sha256_bytes(s["prepared"]) if s["off"] else None,
           "builtins": s["probe"].builtin_plugins(digest=True),
           "starfield_exe": file_identity(os.path.join(a.starfield, "Starfield.exe")),
           "checks": s["report"].lines(), "log": None, "not_vanilla": None, "restored_at": None,
           "restored_epoch": None, "restore": None, "ticked_at_restore": None, "sfse_at_restore": None}
    if game_running():                                    # hashing the built-in plugins takes a while
        raise SystemExit("prepare: Starfield was started while prepare read the game folder, so nothing changed: close "
                         "it, then run prepare again")
    rec["prepared_at"], rec["prepared_epoch"] = now_iso(), time.time()   # collect takes logs from here on
    rec["logs_at_prepare"] = sorted({files.sha256(p) for _, p in session_logs(s["my_games"])})   # never the baseline's
    os.makedirs(out, exist_ok=True)
    write_json(record, rec)                               # the record first: an interruption leaves restore its bytes
    if s["off"]:
        try:
            note = open_note_path()
            os.makedirs(os.path.dirname(note), exist_ok=True)
            write_json(note, {"schema": SCHEMA, "out": out, "plugins_txt": s["plugins_txt"],
                              "prepared_at": rec["prepared_at"]})
        except OSError as e:
            remove(record)
            raise SystemExit(f"prepare: the open-baseline note {open_note_path()} could not be written ({e}), so "
                             f"nothing changed and the record is removed") from None
        if game_running():                                # again, last: one started meanwhile reads the file as it is
            remove(record)
            close_open_note(out)
            raise SystemExit("prepare: Starfield was started while prepare ran, so nothing changed and the record is "
                             "removed: close it, then run prepare again")
        try:
            launcher_restore.write_plugins_txt(s["plugins_txt"], b64(s["prepared"]), sha256_bytes(raw))
        except launcher_restore.RestoreRefused:          # Plugins.txt changed after it was read: nothing written
            remove(record)
            close_open_note(out)
            raise SystemExit("prepare: Plugins.txt changed after prepare read it (another program wrote it meanwhile?), "
                             "so nothing changed and the record is removed: run prepare again") from None
        except OSError as e:                              # nothing written either (the writer removed its temp file)
            remove(record)
            close_open_note(out)
            raise SystemExit(f"prepare: Plugins.txt could not be written ({e}), so nothing changed and the record is "
                             f"removed (is Plugins.txt read-only, or open in another program?)") from None
    print(f"recorded {record}: {len(rec['builtins'] or {})} built-in plugins")
    print(f"turned off: {', '.join(s['off']) or 'nothing (only the game plugins were on)'}")
    print("now start Starfield the plain way (Steam's Play, or Starfield.exe; never the FO4SF Launcher or "
          "sfse_loader.exe), play a New Game for about 10 minutes, quit to the desktop, then collect and restore")
    return 0


def session_logs(my_games):
    """[(mtime, path)] of the Papyrus logs in the My Games folders, oldest first: Papyrus.0.log is the newest, and
    Papyrus.1.log the one before (verified: docs/research/framework/newgame-notes/05-tools-ecosystem.md)."""
    found = []
    for d in my_games:
        folder = os.path.join(d, "Logs", "Script")
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if LOG_FILES.fullmatch(n) and os.path.isfile(p):
                found.append((os.path.getmtime(p), p))
    return sorted(found)


def sfse_logs(my_games, after, until=None):
    """[path] of the files in <My Games>\\SFSE\\Logs last written after `after` (and not after until). SFSE writes its
    own log there (sfse.log, per SFSE's readme: sfse/FOCCSidecar/README.md), and so do our SFSE plugins
    (sfse/FOCCPing/README.md), so one means a session started through sfse_loader.exe."""
    found = []
    for d in my_games:
        folder = os.path.join(d, "SFSE", "Logs")
        try:
            names = sorted(os.listdir(folder), key=str.casefold)
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if os.path.isfile(p) and after < os.path.getmtime(p) and (until is None or os.path.getmtime(p) <= until):
                found.append(p)
    return found


def joined_logs(paths):
    """The logs' bytes as one log, in the order given: each starts on a new line, and the byte-order mark of each but
    the first is dropped (the reader reads past the first's)."""
    out = b""
    for i, p in enumerate(paths):
        with open(p, "rb") as f:
            raw = f.read()
        if i:
            raw = raw[len(BOM):] if raw.startswith(BOM) else raw
            if out and not out.endswith((b"\n", b"\r")):
                out += b"\n"
        out += raw
    return out


def not_vanilla(entry):
    """True when collect's entry shows a session that was not vanilla; False when it is no baseline only because the
    game changed since prepare."""
    return any(entry.get(k) for k in ("ours", "ticked", "sfse"))


def why_not_vanilla(entry):
    """What showed that the session is no baseline (collect's not_vanilla entry), as text."""
    parts = []
    if entry.get("ours"):
        parts.append(f"the log names ours: {', '.join(entry['ours'])}")
    if entry.get("ticked"):
        parts.append(f"Plugins.txt had {', '.join(entry['ticked'])} ticked again")
    if entry.get("sfse"):
        parts.append(f"SFSE wrote {', '.join(entry['sfse'])} (a start through sfse_loader.exe)")
    if entry.get("changed"):
        parts.append(f"the game changed since prepare ({', '.join(entry['changed'])}: a Steam update?), so which build "
                     f"the session ran on is not known")
    return "; ".join(parts) or "no reason recorded"


def collect(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("log"):
        raise SystemExit(f"collect: this baseline's log is collected already ({rec['log']['collected_at']}), and a "
                         f"baseline is collected once: prepare a new one for another session")
    if rec.get("not_vanilla"):
        raise SystemExit(f"collect: this baseline's session is no baseline ({why_not_vanilla(rec['not_vanilla'])}): "
                         f"restore, then prepare a new one")
    if stopped(rec):
        raise SystemExit("collect: a restore of this baseline stopped before it updated the record: run restore again "
                         "first (it finishes the record), then collect")
    if game_running():
        raise SystemExit("collect: Starfield is running (or its state is unknown): quit to the desktop first, so the "
                         "log is complete")
    changed = game_changes(rec)
    if changed is None:
        raise SystemExit(f"collect: the game folder {rec['starfield']} is not readable here, so whether the game "
                         f"changed since prepare is not known: run collect again with it there")
    my_games = rec.get("my_games") or []
    logs = session_logs(my_games)
    if not logs:
        raise SystemExit(f"collect: no {LOG_NAME} in {', '.join(my_games) or 'any My Games folder'}")
    start, end = rec["prepared_epoch"], rec.get("restored_epoch")
    before = set(rec.get("logs_at_prepare") or [])        # a log the game moved on by copying keeps no time
    inside = [(t, p) for t, p in logs if start < t and (end is None or t <= end) and files.sha256(p) not in before]
    if not inside:
        if end is not None and any(t > end for t, _ in logs):
            raise SystemExit("collect: the only Papyrus logs written after prepare were written after restore, by "
                             "sessions with the plugins back on: none is the baseline session's")
        raise SystemExit(f"collect: every Papyrus log in {', '.join(my_games)} was last written before prepare: the "
                         f"baseline session wrote no log (did it run, with the [Papyrus] logging keys on?)")
    ticked = (turned_on(read_bytes(rec["plugins_txt"]), tolerant=True) if end is None else
              rec.get("ticked_at_restore") or [])
    sfse = sfse_logs(my_games, start, end)
    if end is not None:                                   # what restore found, before a later start rewrote a log
        sfse = list(dict.fromkeys((rec.get("sfse_at_restore") or []) + sfse))
    tmp = os.path.join(out, COLLECTING)                  # written whole before it takes the log's name
    try:
        with open(tmp, "wb") as f:
            f.write(joined_logs([p for _, p in inside]))
            f.flush()
            os.fsync(f.fileno())                          # on disk before the record names it (a power cut)
        log = papyrus_log.read(tmp)
        mine = sorted({n for e in log.events for n in e.ours()}, key=str.casefold)
        c = log.counts()
        entry = {"sources": [{"path": p, "mtime": t, "size": os.path.getsize(p)} for t, p in inside],
                 "sha256": files.sha256(tmp), "size": os.path.getsize(tmp), "collected_at": now_iso(), "counts": c,
                 "ours": mine, "ticked": ticked, "sfse": sfse, "changed": changed}
        bad = bool(mine or ticked or sfse or changed)
        kept = os.path.join(out, NOT_VANILLA if bad else LOG_NAME)
        os.replace(tmp, kept)
    except BaseException:
        remove(tmp)
        raise
    rec["not_vanilla" if bad else "log"] = dict(entry, file=os.path.basename(kept))
    write_json(os.path.join(out, RECORD), rec)
    print(f"collected {' + '.join(p for _, p in inside)} -> {kept}: {c['error']} errors, {c['warning']} warnings, "
          f"{c['note']} notes")
    if len(inside) > 1:
        print(f"collect: {len(inside)} sessions wrote a log after prepare; their logs are joined, oldest first")
    if bad:
        what = "not a vanilla session" if not_vanilla(entry) else "not a session of the recorded game"
        print(f"collect: {what} ({why_not_vanilla(entry)}), so it is no baseline. Kept as {NOT_VANILLA}; restore, "
              f"then prepare a new baseline and start the game the plain way (Steam's Play or Starfield.exe, never the "
              f"FO4SF Launcher or sfse_loader.exe)")
        return 1
    return 0


def recorded_bytes(rec):
    """The record's copy of Plugins.txt, None when it is not the one whose sha256 prepare recorded."""
    try:
        raw = base64.b64decode(rec.get("plugins_txt_b64") or "", validate=True)
    except (ValueError, TypeError):
        return None
    return raw if sha256_bytes(raw) == rec.get("plugins_txt_sha256") else None


def stopped(rec):
    """The note a restore that stopped before its record left there ({ticked, how, sfse, epoch, at}), None when there
    is none. restore, status and collect read it alike: an empty or hand-edited one counts as none."""
    done = rec.get("restoring")
    return done if isinstance(done, dict) and done and rec.get("prepared_sha256") is not None else None


def unmark(record, rec):
    """The record back as it was before restore noted what it found there, when restore wrote nothing (best effort: a
    record left with the note only makes collect wait for a restore that finishes)."""
    try:
        write_json(record, rec)
    except OSError:
        pass


def kept_name(out):
    """The first free name for the file restore writes over: Plugins.txt.at-restore, then .2, .3 and so on, so a rerun
    never writes over a copy an earlier one kept (it can hold the owner's own edits)."""
    n = 1
    while os.path.exists(os.path.join(out, KEPT_AT_RESTORE + (f".{n}" if n > 1 else ""))):
        n += 1
    return KEPT_AT_RESTORE + (f".{n}" if n > 1 else "")


def restore(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("restored_at"):
        close_open_note(out, rec)
        print(f"restore: already restored at {rec['restored_at']} ({rec.get('restore')})")
        return 0
    if game_running():
        raise SystemExit("restore: Starfield is running (or its state is unknown): close it first")
    at, at_iso = time.time(), now_iso()                   # the end of the baseline's time
    pt = rec["plugins_txt"]
    cur = read_bytes(pt)
    now = sha256_bytes(cur)
    ticked = turned_on(cur, tolerant=True)                # the game may write a name in another encoding
    done = stopped(rec)
    if done:                                              # a restore that stopped before its record ended the time
        at, at_iso = done.get("epoch") or at, done.get("at") or at_iso
    sfse = sfse_logs(rec.get("my_games") or [], rec["prepared_epoch"], at)   # before a later start rewrites one
    found = ticked                                        # the plugins ticked in the baseline's time
    if done:                                              # what the stopped one found then; later changes came after
        found = done.get("ticked") or []
        sfse = list(dict.fromkeys((done.get("sfse") or []) + sfse))
    # since the stopped one, the same plugins on in other bytes: the game's rewrite at startup, another program's order
    rewritten = bool(done) and cur is not None and now != rec["plugins_txt_sha256"] and same_on(rec, ticked)
    kept = None
    if rec.get("prepared_sha256") is None:
        how = "nothing to put back (prepare turned nothing off)"
    elif done and now == rec["plugins_txt_sha256"]:
        how = done.get("how") or "written back (by the restore that stopped)"
    elif rewritten:                                       # what the stopped one found counts, not this: written back
        kept = kept_name(out)
        how = (f"written back over a file with the same plugins on in other bytes (kept as {kept}), after a restore "
               f"that stopped at {at_iso}")
    elif now == rec["plugins_txt_sha256"]:
        how = "already the recorded one (nothing written)"
    elif now == rec["prepared_sha256"]:
        how = "byte for byte"
    elif cur is None:
        how = "written back (the file was gone)"
    else:
        kept = kept_name(out)
        if ticked and not a.force:
            if done:
                raise SystemExit(f"restore: refused, nothing written: a restore of this baseline at {at_iso} stopped "
                                 f"before it updated the record, and Plugins.txt has changed since: {', '.join(ticked)} "
                                 f"are ticked now, not the same set as the plugins prepare turned off; --force keeps "
                                 f"the current file as {kept} in {out} and writes the recorded one back (the "
                                 f"baseline's time ended at that restore either way)")
            raise SystemExit(f"restore: refused, nothing written: since prepare, {', '.join(ticked)} were ticked in "
                             f"Plugins.txt (the baseline session may not have been vanilla); --force keeps the current "
                             f"file as {kept} in {out} and writes the recorded one back")
        how = (f"forced over a file with {', '.join(ticked)} ticked (kept as {kept})" if ticked else
               f"over the game's own rewrite (it ticked no plugin; kept as {kept})")
    record, wrote = os.path.join(out, RECORD), False
    if rec.get("prepared_sha256") is not None and now != rec["plugins_txt_sha256"]:
        if recorded_bytes(rec) is None:
            raise SystemExit(f"restore: refused, nothing written: the record's copy of Plugins.txt does not match its "
                             f"sha256, so {record} was changed or damaged since prepare")
        if kept:
            with open(os.path.join(out, kept), "xb") as f:
                f.write(cur)
                f.flush()
                os.fsync(f.fileno())                      # on disk before Plugins.txt is written over
        try:                                              # what this restore found, for a rerun after a failed record
            write_json(record, dict(rec, restoring={"ticked": found, "how": how, "sfse": sfse, "epoch": at,
                                                    "at": at_iso}))
        except OSError as e:
            raise SystemExit(f"restore: {record} could not be written ({e}), so nothing was written: run restore "
                             f"again") from None
        try:
            if cur is None:                               # the game's own folder may be gone too
                os.makedirs(os.path.dirname(pt), exist_ok=True)
            launcher_restore.write_plugins_txt(pt, rec["plugins_txt_b64"], now)
        except (launcher_restore.RestoreRefused, OSError) as e:
            unmark(record, rec)                           # nothing written: what it found need not hold any more
            if isinstance(e, launcher_restore.RestoreRefused):
                raise SystemExit(f"restore: {e} (another program wrote it meanwhile?): run restore again") from None
            raise SystemExit(f"restore: Plugins.txt could not be written ({e}), nothing written (is it read-only, or "
                             f"open in another program?): run restore again") from None
        wrote = True
    rec.pop("restoring", None)
    rec.update(restored_at=at_iso, restored_epoch=at, restore=how, ticked_at_restore=found, sfse_at_restore=sfse)
    try:
        write_json(record, rec)
    except OSError as e:
        back = "Plugins.txt is back, but " if wrote else ""
        raise SystemExit(f"restore: {back}{record} could not be written ({e}): run restore again, which finishes the "
                         f"record") from None
    close_open_note(out, rec)
    if rec.get("prepared_sha256") is None:
        print("restore: prepare turned nothing off: nothing to put back (from now on, collect takes no log)")
    else:
        print(f"restored {pt} {how}: {', '.join(rec['turned_off'])} back on")
    if not (rec.get("log") or rec.get("not_vanilla")):
        if found:
            print(f"restore: {', '.join(found)} were ticked in Plugins.txt before restore, so the session may have "
                  f"loaded them: collect will not take its log as the baseline")
        if sfse:
            print(f"restore: SFSE wrote {', '.join(sfse)} during the baseline's time (a start through sfse_loader.exe): "
                  f"collect will not take its log as the baseline")
    return 0


def status(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    print(f"baseline {out}: prepared {rec['prepared_at']}, turned off {', '.join(rec['turned_off']) or 'nothing'}")
    log, bad = rec.get("log"), rec.get("not_vanilla")
    if log:
        c = log["counts"]
        src = " + ".join(s["path"] for s in log.get("sources") or [])
        print(f"log: {log['file']} from {src}: {c['error']} errors, {c['warning']} warnings")
    elif bad:
        print(f"log: {'not vanilla' if not_vanilla(bad) else 'not of the recorded game'} ({why_not_vanilla(bad)}), "
              f"kept as {bad['file']}: no baseline")
    else:
        print("log: not collected yet")
    cur = read_bytes(rec["plugins_txt"])
    now = sha256_bytes(cur)
    if rec.get("prepared_sha256") is None:
        done = f"; restore ran {rec['restored_at']}" if rec.get("restored_at") else ""
        print(f"Plugins.txt: never changed (nothing was turned off){done}")
    elif rec.get("restored_at"):
        where = "the recorded one" if now == rec["plugins_txt_sha256"] else "changed since the restore"
        print(f"Plugins.txt: restored {rec['restored_at']} ({rec['restore']}); now {where}")
    elif now != rec["plugins_txt_sha256"] and recorded_bytes(rec) is None:   # restore checks it before any write
        print("Plugins.txt: not the recorded original, and the record's copy of it does not match its sha256 (the "
              "record was changed or damaged since prepare): restore refuses to write it")
    elif stopped(rec):                                    # what restore will do, as its own branches read it
        on = turned_on(cur, tolerant=True) if cur is not None else []
        if now == rec["plugins_txt_sha256"]:
            state, then = "back", "finishes the record"
        elif cur is None:
            state, then = "gone", "writes the recorded one back and finishes the record"
        elif now == rec["prepared_sha256"]:
            state, then = "as prepared, the plugins off", "puts it back and finishes the record"
        elif same_on(rec, on):
            state, then = ("the same plugins on in other bytes (the game's rewrite at startup?)",
                           "writes the recorded one back, keeping this file, and finishes the record")
        elif on:
            state, then = (f"{', '.join(on)} ticked, not the same set as the plugins prepare turned off",
                           "refuses unless --force (which keeps this file and writes the recorded one back)")
        else:
            state, then = ("rewritten, with no plugin the game does not ship ticked",
                           "writes the recorded one back, keeping this file, and finishes the record")
        print(f"Plugins.txt: {state}. A restore at {stopped(rec).get('at') or 'an unknown time'} stopped before it "
              f"updated the record, and the baseline's time ended then; collect waits for the record: restore again "
              f"{then}")
    elif now == rec["plugins_txt_sha256"]:
        print("Plugins.txt: the recorded original already (nothing is off); restore records that")
    elif now == rec["prepared_sha256"]:
        print("Plugins.txt: as prepared, the plugins off; restore puts it back")
    elif cur is None:
        print("Plugins.txt: gone; restore writes the recorded one back")
    else:
        on = turned_on(cur, tolerant=True)
        if on:
            print(f"Plugins.txt: changed since prepare ({', '.join(on)} ticked again); restore refuses unless --force "
                  f"(which keeps this file and writes the recorded one back)")
        else:
            print("Plugins.txt: changed since prepare (the game's rewrite at startup, or another tool); restore puts "
                  "it back, keeping this file")
    if rec.get("ticked_at_restore"):
        print(f"restore found {', '.join(rec['ticked_at_restore'])} ticked: collect takes no log as the baseline "
              f"after it")
    if rec.get("sfse_at_restore"):
        print(f"restore found SFSE logs of the baseline's time ({', '.join(rec['sfse_at_restore'])}): collect takes no "
              f"log as the baseline after it")
    return 0


def builtins_diff(rec):
    """(how many there are now, [what differs from prepare's]) of the built-in plugins by name and size, None when the
    game folder is not readable here."""
    now = loadprobe.builtin_plugins(os.path.join(rec["starfield"], "Data"))
    if now is None:
        return None
    was = rec.get("builtins") or {}
    a = {n.casefold(): n for n in now}
    b = {n.casefold(): n for n in was}
    added = sorted(a[k] for k in set(a) - set(b))
    gone = sorted(b[k] for k in set(b) - set(a))
    resized = sorted(a[k] for k in set(a) & set(b) if now[a[k]]["size"] != was[b[k]]["size"])
    return len(now), [f"{what} {', '.join(names)}" for what, names in (("added", added), ("gone", gone),
                                                                         ("changed size", resized)) if names]


def game_changes(rec):
    """What of the game changed since prepare recorded it ([] for nothing): the built-in plugins by name and size, and
    Starfield.exe by size and sha256. None when the game folder is not readable here."""
    found = builtins_diff(rec)
    if found is None:
        return None
    parts = [f"built-in plugins {p}" for p in found[1]]
    if file_identity(os.path.join(rec["starfield"], "Starfield.exe")) != rec.get("starfield_exe"):
        parts.append("Starfield.exe")
    return parts


def builtins_note(rec):
    found = builtins_diff(rec)
    if found is None:
        return f"built-in plugins: the game folder {rec['starfield']} is not readable here, not compared"
    n, parts = found
    if not parts:
        return f"built-in plugins: the same {n} as at the baseline (names and sizes)"
    return f"built-in plugins differ from the baseline's: {'; '.join(parts)} (a Starfield update? re-run the baseline)"


def exe_note(rec):
    """Whether Starfield.exe is still the one prepare recorded (size and sha256): a Starfield update brings a new one
    (its version is what the launcher's runtime gate checks), and the built-in plugins' sizes alone may not show it."""
    was = rec.get("starfield_exe")
    now = file_identity(os.path.join(rec["starfield"], "Starfield.exe"))
    if not was or now is None:
        return "Starfield.exe: not compared (not recorded, or not readable here)"
    if now == was:
        return "Starfield.exe: the same as at the baseline (size and sha256)"
    return "Starfield.exe differs from the baseline's (a Starfield update? re-run the baseline)"


def report_refused(report, out, rec, run_log):
    """Why --report may not be written there, None when it may: a .json file of its own, which is none of the
    baseline's files, the run's log, Plugins.txt or the open-baseline note, is outside the game folder, the My Games
    folders and Plugins.txt's folder, and is new or an earlier compare report."""
    named = [(os.path.join(out, n), f"the baseline's {n}")
             for n in (RECORD, RECORD + ".tmp", LOG_NAME, NOT_VANILLA, COLLECTING, KEPT_AT_RESTORE)]
    named += [(run_log, "the run's log"), (rec.get("plugins_txt") or "", "Plugins.txt"),
              (open_note_path(), "the open-baseline note")]
    for p, what in named:
        if p and same_path(p, report):
            return f"it would write over {what}"
    if not report.casefold().endswith(".json"):
        return "it is not a .json file"
    where = game_folder_of(report, rec.get("starfield"), rec.get("my_games"), rec.get("plugins_txt"))
    if where:
        return f"it is in {where}"
    if os.path.exists(report) and "baseline_record" not in (read_json(report) or {}):
        return "it would write over a file that is not a compare report"     # another baseline's record, a queue
    return None


def compare(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    log = rec.get("log") or {}
    bad = rec.get("not_vanilla") or (log if any(log.get(k) for k in ("ours", "ticked", "sfse", "changed")) else None)
    if bad:
        what = "was not vanilla" if not_vanilla(bad) else "was not of the recorded game"
        raise SystemExit(f"compare: the baseline session {what} ({why_not_vanilla(bad)}): it is no baseline "
                         f"(prepare a new one)")
    if not log:
        raise SystemExit("compare: the baseline's log is not collected yet (baseline.py collect)")
    if not os.path.isfile(a.run_log):
        raise SystemExit(f"compare: {a.run_log} is not there (--run-log is the run's Papyrus.0.log)")
    why = report_refused(a.report, out, rec, a.run_log) if a.report else None
    if why:
        raise SystemExit(f"compare: --report {a.report} refused ({why}): give the report a .json file of its own, "
                         f"such as {os.path.join(out, 'compare_<run>.json')}")
    base_p = os.path.join(out, rec["log"]["file"])
    if not os.path.isfile(base_p) or files.sha256(base_p) != rec["log"]["sha256"]:
        raise SystemExit(f"compare: {base_p} changed since collect")
    rep = papyrus_log.compare(papyrus_log.read(a.run_log), papyrus_log.read(base_p))
    rep["baseline_record"] = os.path.join(out, RECORD)
    rep["builtins"], rep["starfield_exe"] = builtins_note(rec), exe_note(rec)
    others = [n for n in rec.get("turned_off") or [] if not loadset.ours(n)]
    rep["also_off"] = (f"the baseline also turned off plugins not ours ({', '.join(others)}): in a run with any of "
                       f"them on, their errors count as Starfield's own" if others else "")
    for line in papyrus_log.report_lines(rep, a.top):
        print(line)
    print("")
    for line in (rep["builtins"], rep["starfield_exe"], rep["also_off"]):
        if line:
            print(line)
    if a.report:
        papyrus_log.write_report(rep, a.report)
        print(f"report: {a.report}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "prepare"):
        s = sub.add_parser(name)
        s.add_argument("--starfield", required=True, help="the game folder (the one with Starfield.exe and Data)")
        s.add_argument("--my-games", default="", help="the My Games\\Starfield folder (default: the usual places)")
        s.add_argument("--allow-off", action="store_true",
                       help="go ahead when nothing is on and our plugins are off, but no baseline turned them off")
        if name == "prepare":
            s.add_argument("--out", required=True, help="a new folder for the record and the log")
    for name in ("collect", "restore", "status", "compare"):
        s = sub.add_parser(name)
        s.add_argument("--out", required=True, help="the baseline's folder (prepare --out)")
        if name == "restore":
            s.add_argument("--force", action="store_true", help="restore over a Plugins.txt that has plugins ticked")
        if name == "compare":
            s.add_argument("--run-log", required=True, help="the Papyrus.0.log of the run to compare")
            s.add_argument("--report", default="", help="write every kind to this JSON file")
            s.add_argument("--top", type=int, default=12, help="kinds shown per group (default 12)")
    a = ap.parse_args(argv)
    run = {"check": check, "prepare": prepare, "collect": collect, "restore": restore, "status": status,
           "compare": compare}[a.cmd]
    if a.cmd not in ("prepare", "collect", "restore"):
        return run(a)
    lock = os.path.join(state_dir(), LOCK)                # one at a time, whatever their --out: none reads a record
    with contextlib.ExitStack() as held:                  # or Plugins.txt another is about to change
        try:
            os.makedirs(os.path.dirname(lock), exist_ok=True)
            held.enter_context(filelock.locked(lock, timeout_s=LOCK_WAIT_S, stale_s=LOCK_STALE_S))
        except TimeoutError as e:
            raise SystemExit(f"{a.cmd}: another baseline.py prepare, collect or restore is running ({e}): run this "
                             f"again when it is done (the lock of one that stopped is taken over after "
                             f"{LOCK_STALE_S / 60:.0f} minutes, unless its age cannot be read: then remove {lock} by "
                             f"hand once none runs); nothing changed") from None
        except OSError as e:
            raise SystemExit(f"{a.cmd}: the baseline lock {lock} could not be made ({e}); nothing changed") from None
        return run(a)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):              # a name the console cannot print never fails a finished step
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
