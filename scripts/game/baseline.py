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
         checks (fo4sf.core.preflight) as they will read once those are off, the [Papyrus] logging keys, any baseline
         of this Plugins.txt that was never restored, and whether our plugins are off already with nothing else on (an
         earlier baseline never restored? --allow-off when no baseline turned them off).
prepare  refuses while Starfield runs, when --out holds a baseline (one never restored: restore it first), when a
         baseline of this Plugins.txt was never restored (the open-baseline note names it, wherever it is, or it is in
         a folder next to --out), or when check would refuse; records in <out>\\baseline.json Plugins.txt as it is (its
         bytes), the built-in plugins (names, sizes, sha256), Starfield.exe's identity and the time; when it turns
         plugins off, notes the baseline as open (<the test runner's state folder>\\baseline-open.json), then unticks
         every active plugin the game does not ship (a guarded rewrite: nothing is written when Plugins.txt changed
         after it was read, and a write that fails removes the record and the note again).
collect  refuses while Starfield runs; joins every Papyrus log of the My Games folders written after prepare and
         before restore (Papyrus.0.log, and the older ones the game has moved on), oldest first, into <out>, once. The
         session was not vanilla when its log names any of ours (FO4* or FOCC*), when Plugins.txt has a plugin the game
         does not ship ticked again (now, or when restore ran), or when SFSE wrote a log meanwhile (a start through
         sfse_loader.exe): the log is then kept as Papyrus.0.log.not-vanilla instead, and the baseline has none.
restore  refuses while Starfield runs; puts Plugins.txt back byte for byte, and ends the time collect takes logs from.
         The game rewrites Plugins.txt at startup (verified: docs/research/framework/launcher-sources/sfstack.md), so a
         rewrite that ticked no plugin is restored over; one that ticked a plugin the game does not ship refuses
         unless --force. Either way the file restore writes over is kept in <out> first. It records the plugins that
         were ticked, and collect after it takes no log as the baseline when there were any.
status   what the record holds and where Plugins.txt stands.
compare  a run's Papyrus log against the baseline's: the groups of fo4sf.core.papyrus_log (only ours, only the run's
         Starfield scripts, the same message at the same script line in both, the same kind in both, only the
         baseline's), the most frequent kinds of each to stdout, every kind to --report (never over the baseline's own
         files, the run's log or Plugins.txt); says whether the built-in plugins are still the recorded ones. Refuses a
         baseline without a vanilla log.

Nothing here touches a plugin file, an archive or an INI; outside <out> it writes only Plugins.txt and the
open-baseline note.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf.core import loadset, papyrus_log, preflight  # noqa: E402
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
    """Plugins.txt bytes as text, its BOM dropped. Text that is not UTF-8 refuses (the game's own file is UTF-8);
    tolerant replaces the bytes that do not decode instead (restore, looking for plugins ticked again)."""
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


def same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


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


def close_open_note(out):
    note = read_json(open_note_path())
    if note and isinstance(note.get("out"), str) and same_path(note["out"], out):
        remove(open_note_path())


def holds_open(folder, plugins_txt):
    """True when folder holds a baseline of this Plugins.txt that was never restored."""
    rec = read_json(os.path.join(folder, RECORD))
    return (rec is not None and unrestored(rec) and isinstance(rec.get("plugins_txt"), str)
            and same_path(rec["plugins_txt"], plugins_txt))


def open_baselines(plugins_txt, out=None):
    """The folders other than out that hold a baseline of this Plugins.txt that was never restored: the one the
    open-baseline note names (it can be anywhere), then any next to out (the same parent folder: the note goes when
    the state folder does)."""
    note = read_json(open_note_path())
    folders = [note["out"]] if note and isinstance(note.get("out"), str) else []
    if out:
        parent = os.path.dirname(out)
        try:
            folders += [os.path.join(parent, n) for n in sorted(os.listdir(parent))]
        except OSError:
            pass
    found = []
    for d in folders:
        if not (out and same_path(d, out)) and not any(same_path(d, f) for f in found) and holds_open(d, plugins_txt):
            found.append(d)
    return found


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
    if not preflight.papyrus_logging_on(probe.ini_texts()):
        keys = " ".join(f"{k}={v}" for k, v in preflight.PAPYRUS_KEYS)
        problems.append(f"[Papyrus] {keys} not in effect (StarfieldCustom.ini overrides Starfield.ini): the session "
                        f"would write no log (scripts/bridge/make_bridge.py ini sets them)")
    problems += [f"{d} holds a baseline of this Plugins.txt that was never restored: restore it first (baseline.py "
                 f"restore --out {d})" for d in open_baselines(pt, out)]
    left_off = off_already(text_lines(raw)) if not off else []
    if left_off and not getattr(a, "allow_off", False):
        problems.append(f"nothing to turn off, but {', '.join(left_off)} are off in Plugins.txt already: an earlier "
                        f"baseline that was never restored? (restore it first; --allow-off if no baseline turned them "
                        f"off)")
    if off and not os.access(pt, os.W_OK):
        problems.append(f"{pt} is read-only: prepare cannot turn plugins off (clear its Read-only attribute first)")
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
           "restored_epoch": None, "restore": None, "ticked_at_restore": None}
    if game_running():                                    # hashing the built-in plugins takes a while
        raise SystemExit("prepare: Starfield was started while prepare read the game folder, so nothing changed: close "
                         "it, then run prepare again")
    rec["prepared_at"], rec["prepared_epoch"] = now_iso(), time.time()   # collect takes logs from here on
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
        try:
            launcher_restore.write_plugins_txt(s["plugins_txt"], b64(s["prepared"]), sha256_bytes(raw))
        except launcher_restore.RestoreRefused as e:      # Plugins.txt changed after it was read: nothing written
            remove(record)
            close_open_note(out)
            raise SystemExit(f"prepare: {e}") from None
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


def why_not_vanilla(entry):
    """What showed that the session was not vanilla (collect's not_vanilla entry), as text."""
    parts = []
    if entry.get("ours"):
        parts.append(f"the log names ours: {', '.join(entry['ours'])}")
    if entry.get("ticked"):
        parts.append(f"Plugins.txt had {', '.join(entry['ticked'])} ticked again")
    if entry.get("sfse"):
        parts.append(f"SFSE wrote {', '.join(entry['sfse'])} (a start through sfse_loader.exe)")
    return "; ".join(parts) or "no reason recorded"


def collect(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("log"):
        raise SystemExit(f"collect: this baseline's log is collected already ({rec['log']['collected_at']}), and a "
                         f"baseline is collected once: prepare a new one for another session")
    if rec.get("not_vanilla"):
        raise SystemExit(f"collect: this baseline's session was not vanilla ({why_not_vanilla(rec['not_vanilla'])}), "
                         f"so it is no baseline: restore, then prepare a new one")
    if game_running():
        raise SystemExit("collect: Starfield is running (or its state is unknown): quit to the desktop first, so the "
                         "log is complete")
    my_games = rec.get("my_games") or []
    logs = session_logs(my_games)
    if not logs:
        raise SystemExit(f"collect: no {LOG_NAME} in {', '.join(my_games) or 'any My Games folder'}")
    start, end = rec["prepared_epoch"], rec.get("restored_epoch")
    inside = [(t, p) for t, p in logs if start < t and (end is None or t <= end)]
    if not inside:
        if end is not None and any(t > end for t, _ in logs):
            raise SystemExit("collect: the only Papyrus logs written after prepare were written after restore, by "
                             "sessions with the plugins back on: none is the baseline session's")
        raise SystemExit(f"collect: every Papyrus log in {', '.join(my_games)} was last written before prepare: the "
                         f"baseline session wrote no log (did it run, with the [Papyrus] logging keys on?)")
    ticked = (turned_on(read_bytes(rec["plugins_txt"]), tolerant=True) if end is None else
              rec.get("ticked_at_restore") or [])
    sfse = sfse_logs(my_games, start, end)
    tmp = os.path.join(out, COLLECTING)                  # written whole before it takes the log's name
    try:
        with open(tmp, "wb") as f:
            f.write(joined_logs([p for _, p in inside]))
        log = papyrus_log.read(tmp)
        mine = sorted({n for e in log.events for n in e.ours()}, key=str.casefold)
        c = log.counts()
        entry = {"sources": [{"path": p, "mtime": t, "size": os.path.getsize(p)} for t, p in inside],
                 "sha256": files.sha256(tmp), "size": os.path.getsize(tmp), "collected_at": now_iso(), "counts": c,
                 "ours": mine, "ticked": ticked, "sfse": sfse}
        bad = bool(mine or ticked or sfse)
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
        print(f"collect: not a vanilla session ({why_not_vanilla(entry)}), so it is no baseline. Kept as "
              f"{NOT_VANILLA}; restore, then prepare a new baseline and start the game the plain way (Steam's Play or "
              f"Starfield.exe, never the FO4SF Launcher or sfse_loader.exe)")
        return 1
    return 0


def restore(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("restored_at"):
        close_open_note(out)
        print(f"restore: already restored at {rec['restored_at']} ({rec.get('restore')})")
        return 0
    if game_running():
        raise SystemExit("restore: Starfield is running (or its state is unknown): close it first")
    pt = rec["plugins_txt"]
    cur = read_bytes(pt)
    now = sha256_bytes(cur)
    ticked = turned_on(cur, tolerant=True)                # the game may write a name in another encoding
    keep = False
    if rec.get("prepared_sha256") is None:
        how = "nothing to put back (prepare turned nothing off)"
    elif now == rec["plugins_txt_sha256"]:
        how = "already the recorded one (nothing written)"
    elif now == rec["prepared_sha256"]:
        how = "byte for byte"
    elif cur is None:
        how = "written back (the file was gone)"
    else:
        if ticked and not a.force:
            raise SystemExit(f"restore: refused, nothing written: since prepare, {', '.join(ticked)} were ticked in "
                             f"Plugins.txt (the baseline session may not have been vanilla); --force keeps the current "
                             f"file as {KEPT_AT_RESTORE} in {out} and writes the recorded one back")
        keep = True
        how = (f"forced over a file with {', '.join(ticked)} ticked (kept as {KEPT_AT_RESTORE})" if ticked else
               f"over the game's own rewrite (it ticked no plugin; kept as {KEPT_AT_RESTORE})")
    if keep:
        with open(os.path.join(out, KEPT_AT_RESTORE), "wb") as f:
            f.write(cur)
    if rec.get("prepared_sha256") is not None and now != rec["plugins_txt_sha256"]:
        try:
            launcher_restore.write_plugins_txt(pt, rec["plugins_txt_b64"], now)
        except launcher_restore.RestoreRefused as e:
            raise SystemExit(f"restore: {e} (another program wrote it meanwhile?): run restore again") from None
        except OSError as e:
            raise SystemExit(f"restore: Plugins.txt could not be written ({e}), nothing written (is it read-only, or "
                             f"open in another program?): run restore again") from None
    rec.update(restored_at=now_iso(), restored_epoch=time.time(), restore=how, ticked_at_restore=ticked)
    write_json(os.path.join(out, RECORD), rec)
    close_open_note(out)
    if rec.get("prepared_sha256") is None:
        print("restore: prepare turned nothing off: nothing to put back (from now on, collect takes no log)")
    else:
        print(f"restored {pt} {how}: {', '.join(rec['turned_off'])} back on")
    if ticked and not (rec.get("log") or rec.get("not_vanilla")):
        print(f"restore: {', '.join(ticked)} were ticked in Plugins.txt before restore, so the session may have loaded "
              f"them: collect will not take its log as the baseline")
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
        print(f"log: not vanilla ({why_not_vanilla(bad)}), kept as {bad['file']}: no baseline")
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
    elif now == rec["plugins_txt_sha256"]:
        print("Plugins.txt: the recorded original already (nothing is off); restore records that")
    elif now == rec["prepared_sha256"]:
        print("Plugins.txt: as prepared, the plugins off; restore puts it back")
    elif cur is None:
        print("Plugins.txt: gone; restore writes the recorded one back")
    else:
        on = turned_on(cur, tolerant=True)
        why = f"{', '.join(on)} ticked again" if on else "the game's rewrite at startup, or another tool"
        print(f"Plugins.txt: changed since prepare ({why}); restore puts it back")
    if rec.get("ticked_at_restore"):
        print(f"restore found {', '.join(rec['ticked_at_restore'])} ticked: collect takes no log as the baseline "
              f"after it")
    return 0


def builtins_note(rec):
    now = loadprobe.builtin_plugins(os.path.join(rec["starfield"], "Data"))
    was = rec.get("builtins") or {}
    if now is None:
        return f"built-in plugins: the game folder {rec['starfield']} is not readable here, not compared"
    a = {n.casefold(): n for n in now}
    b = {n.casefold(): n for n in was}
    added = sorted(a[k] for k in set(a) - set(b))
    gone = sorted(b[k] for k in set(b) - set(a))
    resized = sorted(a[k] for k in set(a) & set(b) if now[a[k]]["size"] != was[b[k]]["size"])
    if not (added or gone or resized):
        return f"built-in plugins: the same {len(now)} as at the baseline (names and sizes)"
    parts = [f"{what} {', '.join(names)}" for what, names in (("added", added), ("gone", gone),
                                                                ("changed size", resized)) if names]
    return f"built-in plugins differ from the baseline's: {'; '.join(parts)} (a Starfield update? re-run the baseline)"


def report_clash(report, out, rec, run_log):
    """What --report would write over, None when nothing of the baseline's: its record and the files it keeps, the
    run's log, Plugins.txt or the open-baseline note."""
    named = [(os.path.join(out, n), f"the baseline's {n}")
             for n in (RECORD, RECORD + ".tmp", LOG_NAME, NOT_VANILLA, COLLECTING, KEPT_AT_RESTORE)]
    named += [(run_log, "the run's log"), (rec.get("plugins_txt") or "", "Plugins.txt"),
              (open_note_path(), "the open-baseline note")]
    for p, what in named:
        if p and same_path(p, report):
            return what
    return None


def compare(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    log = rec.get("log") or {}
    bad = rec.get("not_vanilla") or (log if log.get("ours") or log.get("ticked") or log.get("sfse") else None)
    if bad:
        raise SystemExit(f"compare: the baseline session was not vanilla ({why_not_vanilla(bad)}): it is no baseline "
                         f"(prepare a new one)")
    if not log:
        raise SystemExit("compare: the baseline's log is not collected yet (baseline.py collect)")
    if not os.path.isfile(a.run_log):
        raise SystemExit(f"compare: {a.run_log} is not there (--run-log is the run's Papyrus.0.log)")
    clash = report_clash(a.report, out, rec, a.run_log) if a.report else None
    if clash:
        raise SystemExit(f"compare: --report {a.report} would write over {clash}: give the report a file of its own, "
                         f"such as {os.path.join(out, 'compare_<run>.json')}")
    base_p = os.path.join(out, rec["log"]["file"])
    if not os.path.isfile(base_p) or files.sha256(base_p) != rec["log"]["sha256"]:
        raise SystemExit(f"compare: {base_p} changed since collect")
    rep = papyrus_log.compare(papyrus_log.read(a.run_log), papyrus_log.read(base_p))
    rep["baseline_record"] = os.path.join(out, RECORD)
    rep["builtins"] = builtins_note(rec)
    for line in papyrus_log.report_lines(rep, a.top):
        print(line)
    print("")
    print(rep["builtins"])
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
    return {"check": check, "prepare": prepare, "collect": collect, "restore": restore, "status": status,
            "compare": compare}[a.cmd](a)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):              # a name the console cannot print never fails a finished step
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
