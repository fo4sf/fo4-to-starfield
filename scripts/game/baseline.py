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
         checks (fo4sf.core.preflight) as they will read once those are off, the [Papyrus] logging keys, and whether
         our plugins are off already with nothing else on (an earlier baseline never restored? --allow-off when no
         baseline turned them off).
prepare  refuses while Starfield runs, when --out holds a baseline (one never restored: restore it first), when a
         folder next to --out holds a baseline of this Plugins.txt that was never restored, or when check would
         refuse; records in <out>\\baseline.json Plugins.txt as it is (its bytes), the built-in plugins (names, sizes,
         sha256), Starfield.exe's identity and the time; then unticks every active plugin the game does not ship (a
         guarded rewrite: nothing is written when Plugins.txt changed after it was read, and a write that fails
         removes the record again).
collect  refuses while Starfield runs; copies the newest Papyrus.0.log of the My Games folders into <out>, only one
         written after prepare and before restore, and only once. A log that names any of ours (FO4* or FOCC*: the
         session loaded something of ours) is kept as Papyrus.0.log.not-vanilla instead, and the baseline has no log.
restore  refuses while Starfield runs; puts Plugins.txt back byte for byte. The game rewrites Plugins.txt at startup
         (verified: docs/research/framework/launcher-sources/sfstack.md), so a rewrite that ticked no plugin is
         restored over; one that ticked a plugin the game does not ship refuses unless --force, which keeps the
         current file in <out> first.
status   what the record holds and where Plugins.txt stands.
compare  a run's Papyrus log against the baseline's: the groups of fo4sf.core.papyrus_log (only ours, only the run's
         Starfield scripts, both), the most frequent kinds of each to stdout, every kind to --report; says whether the
         built-in plugins are still the recorded ones. Refuses a baseline without a vanilla log.

Nothing here touches a plugin file, an archive or an INI; the only file written outside <out> is Plugins.txt.
"""
import argparse
import base64
import hashlib
import json
import os
import shutil
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
NOT_VANILLA = "Papyrus.0.log.not-vanilla"
COLLECTING = "Papyrus.0.log.collecting"
CHECKS = ("loaders", "start")
KEPT_AT_RESTORE = "Plugins.txt.at-restore"
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
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1)
        f.write("\n")
    os.replace(tmp, path)


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


def unrestored(rec):
    """True for a record whose prepare turned plugins off and whose restore has not run: it holds the only copy of
    Plugins.txt as it was."""
    return rec.get("prepared_sha256") is not None and not rec.get("restored_at")


def unrestored_next_to(out, plugins_txt):
    """The folders next to out (the same parent) whose baseline turned plugins of this Plugins.txt off and was never
    restored."""
    parent = os.path.dirname(out)
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return []
    found = []
    for n in names:
        d = os.path.join(parent, n)
        p = os.path.join(d, RECORD)
        if os.path.normcase(d) == os.path.normcase(out) or not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                rec = json.load(f)
        except (OSError, ValueError):
            continue
        if (isinstance(rec, dict) and unrestored(rec) and isinstance(rec.get("plugins_txt"), str)
                and os.path.normcase(rec["plugins_txt"]) == os.path.normcase(plugins_txt)):
            found.append(d)
    return found


def survey(a):
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
    s = survey(a)
    problems = s["problems"] + [f"{d} holds a baseline of this Plugins.txt that was never restored: restore it first "
                                f"(baseline.py restore --out {d})" for d in unrestored_next_to(out, s["plugins_txt"])]
    if problems:
        raise SystemExit("prepare: refused, nothing changed:\n  " + "\n  ".join(problems))
    os.makedirs(out, exist_ok=True)
    raw = s["raw"]
    rec = {"schema": SCHEMA, "prepared_at": now_iso(), "prepared_epoch": time.time(),
           "starfield": os.path.abspath(a.starfield), "my_games": s["my_games"], "plugins_txt": s["plugins_txt"],
           "plugins_txt_b64": None if raw is None else b64(raw), "plugins_txt_sha256": sha256_bytes(raw),
           "turned_off": s["off"], "prepared_sha256": sha256_bytes(s["prepared"]) if s["off"] else None,
           "builtins": s["probe"].builtin_plugins(digest=True),
           "starfield_exe": file_identity(os.path.join(a.starfield, "Starfield.exe")),
           "checks": s["report"].lines(), "log": None, "not_vanilla": None, "restored_at": None,
           "restored_epoch": None, "restore": None}
    write_json(record, rec)                               # the record first: an interruption leaves restore its bytes
    if s["off"]:
        try:
            launcher_restore.write_plugins_txt(s["plugins_txt"], b64(s["prepared"]), sha256_bytes(raw))
        except launcher_restore.RestoreRefused as e:      # Plugins.txt changed after it was read: nothing written
            remove(record)
            raise SystemExit(f"prepare: {e}") from None
        except OSError as e:                              # nothing written either (the writer removed its temp file)
            remove(record)
            raise SystemExit(f"prepare: Plugins.txt could not be written ({e}), so nothing changed and the record is "
                             f"removed (is Plugins.txt read-only, or open in another program?)") from None
    print(f"recorded {record}: {len(rec['builtins'] or {})} built-in plugins")
    print(f"turned off: {', '.join(s['off']) or 'nothing (only the game plugins were on)'}")
    print("now start Starfield the plain way (Steam's Play, or Starfield.exe; never the FO4SF Launcher or "
          "sfse_loader.exe), play a New Game for about 10 minutes, quit to the desktop, then collect and restore")
    return 0


def newest_log(my_games):
    found = []
    for d in my_games:
        p = os.path.join(d, "Logs", "Script", LOG_NAME)
        if os.path.isfile(p):
            found.append((os.path.getmtime(p), p))
    return max(found) if found else None


def collect(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("log"):
        raise SystemExit(f"collect: this baseline's log is collected already ({rec['log']['collected_at']}), and a "
                         f"baseline is one session: prepare a new one for another")
    if rec.get("not_vanilla"):
        raise SystemExit(f"collect: this baseline's session loaded ours ({', '.join(rec['not_vanilla']['ours'])}), so "
                         f"it is no baseline: restore, then prepare a new one")
    if game_running():
        raise SystemExit("collect: Starfield is running (or its state is unknown): quit to the desktop first, so the "
                         "log is complete")
    got = newest_log(rec.get("my_games") or [])
    if got is None:
        raise SystemExit(f"collect: no {LOG_NAME} in {', '.join(rec.get('my_games') or []) or 'any My Games folder'}")
    mtime, src = got
    if mtime <= rec["prepared_epoch"]:
        raise SystemExit(f"collect: {src} was last written before prepare: the baseline session wrote no log "
                         f"(did it run, with the [Papyrus] logging keys on?)")
    if rec.get("restored_epoch") and mtime > rec["restored_epoch"]:
        raise SystemExit(f"collect: {src} was written after restore, by a session with the plugins back on: not the "
                         f"baseline session's log")
    tmp = os.path.join(out, COLLECTING)                  # read whole before it takes the log's name
    try:
        shutil.copy2(src, tmp)
        log = papyrus_log.read(tmp)
        mine = sorted({n for e in log.events for n in e.ours()}, key=str.casefold)
        c = log.counts()
        entry = {"source": src, "sha256": files.sha256(tmp), "size": os.path.getsize(tmp), "mtime": mtime,
                 "collected_at": now_iso(), "counts": c, "ours": mine}
        kept = os.path.join(out, NOT_VANILLA if mine else LOG_NAME)
        os.replace(tmp, kept)
    except BaseException:
        remove(tmp)
        raise
    rec["not_vanilla" if mine else "log"] = dict(entry, file=os.path.basename(kept))
    write_json(os.path.join(out, RECORD), rec)
    print(f"collected {src} -> {kept}: {c['error']} errors, {c['warning']} warnings, {c['note']} notes")
    if mine:
        print(f"collect: the log names ours ({', '.join(mine)}): the session loaded something of ours, so it is no "
              f"baseline (was the game started through the FO4SF Launcher or sfse_loader.exe?). Kept as "
              f"{NOT_VANILLA}; restore, then prepare a new baseline")
        return 1
    return 0


def restore(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("prepared_sha256") is None:
        print("restore: prepare turned nothing off: nothing to put back")
        return 0
    if rec.get("restored_at"):
        print(f"restore: already restored at {rec['restored_at']} ({rec.get('restore')})")
        return 0
    if game_running():
        raise SystemExit("restore: Starfield is running (or its state is unknown): close it first")
    pt = rec["plugins_txt"]
    cur = read_bytes(pt)
    if sha256_bytes(cur) == rec["plugins_txt_sha256"]:
        how = "already the recorded one (nothing written)"
    elif sha256_bytes(cur) == rec["prepared_sha256"]:
        how = "byte for byte"
    elif cur is None:
        how = "written back (the file was gone)"
    else:
        ticked = turned_on(cur, tolerant=True)            # the game may write a name in another encoding
        if ticked and not a.force:
            raise SystemExit(f"restore: refused, nothing written: since prepare, {', '.join(ticked)} were ticked in "
                             f"Plugins.txt (the baseline session may not have been vanilla); --force keeps the current "
                             f"file as {KEPT_AT_RESTORE} in {out} and writes the recorded one back")
        if ticked:
            with open(os.path.join(out, KEPT_AT_RESTORE), "wb") as f:
                f.write(cur)
            how = f"forced over a file with {', '.join(ticked)} ticked (kept as {KEPT_AT_RESTORE})"
        else:
            how = "over the game's own rewrite (it ticked no plugin)"
    if sha256_bytes(cur) != rec["plugins_txt_sha256"]:
        try:
            launcher_restore.write_plugins_txt(pt, rec["plugins_txt_b64"], sha256_bytes(cur))
        except launcher_restore.RestoreRefused as e:
            raise SystemExit(f"restore: {e} (another program wrote it meanwhile?): run restore again") from None
        except OSError as e:
            raise SystemExit(f"restore: Plugins.txt could not be written ({e}), nothing written (is it read-only, or "
                             f"open in another program?): run restore again") from None
    rec["restored_at"], rec["restored_epoch"], rec["restore"] = now_iso(), time.time(), how
    write_json(os.path.join(out, RECORD), rec)
    print(f"restored {pt} {how}: {', '.join(rec['turned_off'])} back on")
    return 0


def status(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    print(f"baseline {out}: prepared {rec['prepared_at']}, turned off {', '.join(rec['turned_off']) or 'nothing'}")
    log, bad = rec.get("log"), rec.get("not_vanilla")
    if log:
        c = log["counts"]
        print(f"log: {log['file']} from {log['source']}: {c['error']} errors, {c['warning']} warnings")
    elif bad:
        print(f"log: the session's log names ours ({', '.join(bad['ours'])}), kept as {bad['file']}: no baseline")
    else:
        print("log: not collected yet")
    now = sha256_bytes(read_bytes(rec["plugins_txt"]))
    if rec.get("restored_at"):
        where = "the recorded one" if now == rec["plugins_txt_sha256"] else "changed since the restore"
        print(f"Plugins.txt: restored {rec['restored_at']} ({rec['restore']}); now {where}")
    elif rec.get("prepared_sha256") is None:
        print("Plugins.txt: never changed (nothing was turned off)")
    elif now == rec["plugins_txt_sha256"]:
        print("Plugins.txt: the recorded original already (nothing is off); restore records that")
    else:
        where = ("as prepared, our plugins off" if now == rec["prepared_sha256"] else
                 "changed since prepare (the game's rewrite at startup, or another tool)")
        print(f"Plugins.txt: {where}; restore puts it back")
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


def compare(a):
    out = os.path.abspath(a.out)
    rec = load_record(out)
    if rec.get("not_vanilla") or (rec.get("log") or {}).get("ours"):
        bad = rec.get("not_vanilla") or rec["log"]
        raise SystemExit(f"compare: the baseline session's log names ours ({', '.join(bad['ours'])}): it is no "
                         f"baseline (prepare a new one)")
    if not rec.get("log"):
        raise SystemExit("compare: the baseline's log is not collected yet (baseline.py collect)")
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
    sys.exit(main())
