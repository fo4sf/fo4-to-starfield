"""The observation bridge's log reader (docs/ai/test-queue.md "Bridge"): the Papyrus quest script FO4SF_Bridge
(dotnet/Bridge, experiment bridge_*) writes one line every half second to the user log
  <My Games>/Starfield/Logs/Script/User/fo4sf.0.log
    FO4SF init rt=12.345
    FO4SF rt=12.845 pos=-2189.263428 -1553.490112 105.260002 ang=181.914001 cell=33556480 world=50331649 loaded=True cmd=7 n=12
rt is the game's real-time clock (seconds since launch), pos / ang the player's position and heading in the game's
units (metres in Starfield; a converted world's merged frame, so no OCR and no merge offset guessing), cell / world the
parent cell's and worldspace's form ids in decimal (as Papyrus prints an int; hex here), loaded whether the player's 3D
is loaded, cmd the value of the global FO4SF_Cmd when it changed since the previous line (the console's
"set FO4SF_Cmd to 7" acknowledged by the game itself), n the line count since the quest started.

usage: bridge_log.py latest [--log <file>] [--max-age 3]      the newest line as JSON, or {"ok": false, "why": ...}
       bridge_log.py wait-cmd <value> [--log <file>] [--timeout 10]    wait until a line echoes cmd=<value>
       bridge_log.py wait-move [--log <file>] [--timeout 10] [--min 0.5]  wait until pos moved >= min from the first line
       bridge_log.py events [--log <file>] [--all]     every probe line (ack, ref, player, resolve, target, moveto, init)
The game rewrites the log on every launch (Papyrus.0.log rotation applies to user logs too): callers note the line
count or rt they start from, never the file's mtime alone. Papyrus prints floats with six decimals and bools as True /
False; both forms are accepted, as are missing fields (older script versions).
FO4SF_Probe.Resolve / MoveTo (the scripted door's Step 0, 2026-10-16) write key=value lines:
    FO4SF resolve plugin=FO4TerrainCore.esm id=2048 form=33556480 ref=true pos=-989.257080 1146.514282 105.142899
          ang=0.000000 cell=33560581 cellname= world=-16707575 worldname= disabled=false loaded=true
    FO4SF resolve plugin=FO4TerrainCore.esm id=184876 form=none
    FO4SF target ...   (MoveTo's own lookup of its destination, the same fields)
    FO4SF moveto plugin=FO4TerrainCore.esm id=2048 offset=-1200.000000 -2700.000000 0.000000 phase=after pos=.. ang=..
          cell=.. cellname=.. world=.. worldname=.. loaded=..       (phase before | after | settled | refused)
"""
import argparse
import json
import os
import re
import sys
import time

LINE = re.compile(r"^(?:\[(?P<clock>[^\]]*)\]\s*)?FO4SF rt=(?P<rt>-?\d+(?:\.\d+)?)"   # "[21:29:40] " prefix: the game's clock
                  r"(?: pos=(?P<x>-?\d+(?:\.\d+)?) (?P<y>-?\d+(?:\.\d+)?) (?P<z>-?\d+(?:\.\d+)?))?"
                  r"(?: ang=(?P<ang>-?\d+(?:\.\d+)?))?"
                  r"(?: cell=(?P<cell>-?\d+|none))?"             # Papyrus prints a form id as a SIGNED int: a planet
                  r"(?: world=(?P<world>-?\d+|none))?"           # worldspace of load index FF.. is negative (1015b)
                  r"(?: loaded=(?P<loaded>True|False|true|false|1|0))?"
                  r"(?: cmd=(?P<cmd>-?\d+))?"
                  r"(?: n=(?P<n>\d+))?\s*$")


def default_log():
    home = os.path.expanduser("~")
    for base in (os.path.join(home, "OneDrive", "Documents"), os.path.join(home, "Documents")):
        p = os.path.join(base, "My Games", "Starfield", "Logs", "Script", "User", "fo4sf.0.log")
        if os.path.exists(p):
            return p
    return os.path.join(home, "OneDrive", "Documents", "My Games", "Starfield", "Logs", "Script", "User", "fo4sf.0.log")


def parse_line(s):
    """A dict for one bridge line, or None for anything else (the init line, Papyrus warnings, a torn last line)."""
    m = LINE.match(s.strip())
    if not m:
        return None
    d = {"rt": float(m.group("rt"))}
    if m.group("clock"):
        d["clock"] = m.group("clock")
    if m.group("x") is not None:
        d["pos"] = [float(m.group("x")), float(m.group("y")), float(m.group("z"))]
    if m.group("ang") is not None:
        d["ang"] = float(m.group("ang"))
    for k in ("cell", "world"):
        v = m.group(k)
        if v is not None:
            d[k] = None if v == "none" else f"{int(v) & 0xFFFFFFFF:08X}"
    if m.group("loaded") is not None:
        d["loaded"] = m.group("loaded").lower() in ("true", "1")
    if m.group("cmd") is not None:
        d["cmd"] = int(m.group("cmd"))
    if m.group("n") is not None:
        d["n"] = int(m.group("n"))
    return d


ACK = re.compile(r"^(?:\[[^\]]*\]\s*)?FO4SF ack (?P<tag>.+?)\s*$", re.I)
REF = re.compile(r"^(?:\[[^\]]*\]\s*)?FO4SF ref=(?P<id>-?\d+)(?: (?P<none>none)| pos=(?P<x>-?\d+(?:\.\d+)?) (?P<y>-?\d+(?:\.\d+)?)"
                 r" (?P<z>-?\d+(?:\.\d+)?)(?: ang=(?P<ang>-?\d+(?:\.\d+)?))?(?: cell=(?P<cell>-?\d+|none))?"
                 r"(?: disabled=(?P<disabled>True|False|true|false))?(?: loaded=(?P<loaded>True|False|true|false))?)\s*$")
PLAYER = re.compile(r"^(?:\[[^\]]*\]\s*)?FO4SF player pos=(?P<x>-?\d+(?:\.\d+)?) (?P<y>-?\d+(?:\.\d+)?) (?P<z>-?\d+(?:\.\d+)?)"
                    r"(?: ang=(?P<ang>-?\d+(?:\.\d+)?))?\s*$")


def parse_event(s):
    """Any bridge line as {"kind": ...}: "pos" (the timer's line, parse_line's fields), "ack" {tag} (FO4SF_Probe.Ack or
    cgf Debug.TraceUser), "ref" {id (hex), pos, ang, cell, disabled, loaded, or none True} (FO4SF_Probe.Pos),
    "player" {pos, ang} (FO4SF_Probe.Player), "init"; None for anything else."""
    d = parse_line(s)
    if d is not None:
        return dict(d, kind="pos")
    s = s.strip()
    m = ACK.match(s)
    if m:
        return {"kind": "ack", "tag": m.group("tag")}
    m = REF.match(s)
    if m:
        out = {"kind": "ref", "id": f"{int(m.group('id')) & 0xFFFFFFFF:08X}"}
        if m.group("none"):
            out["none"] = True
            return out
        out["pos"] = [float(m.group("x")), float(m.group("y")), float(m.group("z"))]
        if m.group("ang") is not None:
            out["ang"] = float(m.group("ang"))
        if m.group("cell") is not None:
            out["cell"] = None if m.group("cell") == "none" else f"{int(m.group('cell')) & 0xFFFFFFFF:08X}"
        for k in ("disabled", "loaded"):
            if m.group(k) is not None:
                out[k] = m.group(k).lower() == "true"
        return out
    m = PLAYER.match(s)
    if m:
        out = {"kind": "player", "pos": [float(m.group("x")), float(m.group("y")), float(m.group("z"))]}
        if m.group("ang") is not None:
            out["ang"] = float(m.group("ang"))
        return out
    if re.match(r"^(?:\[[^\]]*\]\s*)?FO4SF init\b", s):
        return {"kind": "init"}
    return parse_probe(s)


PROBE = re.compile(r"^(?:\[[^\]]*\]\s*)?FO4SF (?P<kind>resolve|target|moveto) (?P<rest>[a-z]+=.*?)\s*$", re.I)
_IDS = ("form", "cell", "world")                           # signed decimal form ids (or none) -> 8 hex
_BOOLS = ("ref", "disabled", "loaded")
_VECS = ("pos", "offset")
_NUM = r"-?\d+(?:\.\d+)?"


def parse_probe(s):
    """A FO4SF_Probe.Resolve / MoveTo line (module doc) as {"kind": resolve | target | moveto, "plugin", "id" (the
    plugin-local id, int), and what the line has of: "form" (8 hex, None for none), "ref", "pos", "ang", "cell" /
    "world" (8 hex or None), "cellname" / "worldname" (str, "" when the game kept no editor id), "disabled", "loaded",
    "offset", "phase"}; None for anything else or a torn line (a value that does not parse)."""
    m = PROBE.match(s.strip())
    if not m:
        return None
    fields, key = {}, None
    for tok in m.group("rest").split(" "):
        k, eq, v = tok.partition("=")
        if eq and re.fullmatch(r"[a-z]+", k):
            key = k
            fields[key] = [v] if v else []
        elif key is not None and tok:
            fields[key].append(tok)
    out = {"kind": m.group("kind").lower()}
    try:
        for k, vals in fields.items():
            v = " ".join(vals)
            if k == "id":
                out[k] = int(v)
            elif k in _IDS:
                out[k] = None if v == "none" else f"{int(v) & 0xFFFFFFFF:08X}"
            elif k in _BOOLS:
                if v.lower() not in ("true", "false"):
                    return None
                out[k] = v.lower() == "true"
            elif k in _VECS:
                if len(vals) != 3 or not all(re.fullmatch(_NUM, x) for x in vals):
                    return None
                out[k] = [float(x) for x in vals]
            elif k == "ang":
                out[k] = float(v)
            else:                                          # plugin, cellname, worldname, phase
                out[k] = v
    except ValueError:
        return None
    if "plugin" not in out or "id" not in out:
        return None
    return out


def read_events(path):
    """Every parsed event of the log in order (a missing log is an empty list)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read().splitlines()
    except OSError:
        return []
    return [e for e in (parse_event(s) for s in raw) if e is not None]


def line_count(path):
    """Raw lines in the log now: the mark a reference read takes before it types its command, so only a reply written
    after that counts (an older reply for the same reference never passes for a new read). A missing log is 0 (there
    is no older reply to mistake); a log that exists but cannot be read raises OSError, and the read must fail, never
    take 0 (Codex's review of #164: 0 would let the old reply pass)."""
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def wait_ref(path, ref_hex, timeout=10.0, since=None):
    """The FO4SF_Probe.Pos reply for this reference (8 hex, load index included) written at or after raw line `since`:
    {"ok": True, "pos", "ang", "cell", "disabled", "loaded", "line"} or {"ok": False, "why", ...}: "no such reference"
    (the script answered none: the id is not a loaded reference) or a timeout. Polls every 0.2 s; the reply comes
    within a second of the console closing (r05_medkit_1015: nine runs)."""
    want = ref_hex.upper()
    if since is None or since < 0:                        # no mark: nothing proves a reply is this read's
        return {"ok": False, "why": f"no mark for {want}: the read is not proven fresh"}
    t0 = time.time()
    while True:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read().splitlines()
        except OSError:
            raw = []
        for i in range(since, len(raw)):
            ev = parse_event(raw[i])
            if ev and ev["kind"] == "ref" and ev["id"] == want:
                if ev.get("none"):
                    return {"ok": False, "why": f"no such reference {want}", "line": i}
                return {"ok": True, "pos": ev["pos"], "ang": ev.get("ang"), "cell": ev.get("cell"),
                        "disabled": ev.get("disabled"), "loaded": ev.get("loaded"), "line": i}
        if time.time() - t0 > timeout:
            return {"ok": False, "why": f"no reply for {want} after line {since} in {timeout:g} s"}
        time.sleep(0.2)


def wait_ack(path, tag, timeout=10.0):
    """Wait until an ack line with this tag is in the log; True, or False after timeout seconds."""
    t0 = time.time()
    while True:
        if any(e["kind"] == "ack" and e["tag"] == tag for e in read_events(path)):
            return True
        if time.time() - t0 > timeout:
            return False
        time.sleep(0.2)


def read_lines(path):
    """Every parsed line of the log in order (a missing log is an empty list)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read().splitlines()
    except OSError:
        return []
    out = []
    for s in raw:
        d = parse_line(s)
        if d is not None:
            out.append(d)
    return out


def clock_age(clock, now=None):
    """Seconds between a line's "[HH:MM:SS]" stamp (the game's clock, the same PC) and now; None for no stamp. The
    stamp has whole seconds, so an age is 0..1 s coarse; a stamp ahead of now (midnight passed) counts as 24 h less."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})", clock or "")
    if not m:
        return None
    now = time.time() if now is None else now
    lt = time.localtime(now)
    secs_now = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec + (now % 1)
    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    age = secs_now - secs
    # Stamps are in the past. A negative age means the stamp is from the previous day
    # (or a small clock skew). Treat any negative as yesterday by adding 24h.
    # The old threshold of -12h missed afternoon stamps when now is early morning.
    if age < 0:
        age += 86400
    return age


def latest(path, max_age=3.0):
    """The newest line, with ok False when the log is missing, empty or older than max_age seconds. The age is the
    line's own clock stamp against now (the game stops writing while it is paused: a loading screen, the console open;
    measured 2026-10-14: a new line is on disk within a second otherwise, the file is not buffered), so a position
    from before a pause is never taken for a current one; a line without a stamp falls back to the file's mtime."""
    lines = read_lines(path)
    if not lines:
        return {"ok": False, "why": "no bridge lines in " + path}
    last = lines[-1]
    age = clock_age(last.get("clock"))
    if age is None:
        age = time.time() - os.path.getmtime(path)
    if max_age is not None and age > max_age:
        return {"ok": False, "why": f"newest line {age:.1f} s old (max {max_age})", "last": last}
    return dict(last, ok=True)


def wait_cmd(path, value, timeout=10.0, since_n=None):
    """Wait until a line after since_n echoes cmd=value; the line, or None after timeout seconds."""
    t0 = time.time()
    while True:
        for d in read_lines(path):
            if since_n is not None and d.get("n", 0) <= since_n:
                continue
            if d.get("cmd") == value:
                return d
        if time.time() - t0 > timeout:
            return None
        time.sleep(0.2)


def wait_move(path, min_m=0.5, timeout=10.0):
    """Wait until the player's position differs from the first line read by at least min_m; (first, moved) or
    (first, None) after timeout seconds."""
    first = latest(path, max_age=None)
    if not first.get("ok") or "pos" not in first:
        return first, None
    t0 = time.time()
    while time.time() - t0 <= timeout:
        cur = latest(path, max_age=None)
        if cur.get("ok") and "pos" in cur:
            if sum((a - b) ** 2 for a, b in zip(cur["pos"], first["pos"])) ** 0.5 >= min_m:
                return first, cur
        time.sleep(0.2)
    return first, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("latest")
    p.add_argument("--log", default=None)
    p.add_argument("--max-age", type=float, default=3.0)
    p = sub.add_parser("wait-cmd")
    p.add_argument("value", type=int)
    p.add_argument("--log", default=None)
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--since-n", type=int, default=None)
    p = sub.add_parser("wait-move")
    p.add_argument("--log", default=None)
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--min", type=float, default=0.5)
    p = sub.add_parser("wait-ack")
    p.add_argument("tag")
    p.add_argument("--log", default=None)
    p.add_argument("--timeout", type=float, default=10.0)
    p = sub.add_parser("mark")                             # the log's raw line count now (wait-ref --since)
    p.add_argument("--log", default=None)
    p = sub.add_parser("wait-ref")                         # FO4SF_Probe.Pos reply for a reference (8 hex)
    p.add_argument("ref")
    p.add_argument("--log", default=None)
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--since", type=int, required=True, help="the mark (bridge_log.py mark) taken before the command")
    p = sub.add_parser("events")                           # every parsed line but the timer's, as JSON lines
    p.add_argument("--log", default=None)
    p.add_argument("--all", action="store_true", help="the timer's pos lines too")
    a = ap.parse_args(argv)
    log = a.log or default_log()
    if a.cmd == "mark":
        try:
            print(line_count(log))
        except OSError as e:
            print(f"fail {e}")                            # exit 2: the caller must not read through the bridge
            return 2
        return 0
    if a.cmd == "wait-ref":
        r = wait_ref(log, a.ref, a.timeout, a.since)
        print(json.dumps(r))
        return 0 if r["ok"] else 1
    if a.cmd == "wait-ack":
        ok = wait_ack(log, a.tag, a.timeout)
        print(json.dumps({"ok": ok, "tag": a.tag}))
        return 0 if ok else 1
    if a.cmd == "events":
        for e in read_events(log):
            if a.all or e["kind"] != "pos":
                print(json.dumps(e))
        return 0
    if a.cmd == "latest":
        print(json.dumps(latest(log, a.max_age)))
    elif a.cmd == "wait-cmd":
        d = wait_cmd(log, a.value, a.timeout, a.since_n)
        print(json.dumps(d if d else {"ok": False, "why": f"no cmd={a.value} within {a.timeout} s"}))
        return 0 if d else 1
    else:
        first, moved = wait_move(log, a.min, a.timeout)
        print(json.dumps({"first": first, "moved": moved, "ok": moved is not None}))
        return 0 if moved else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
