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
The game rewrites the log on every launch (Papyrus.0.log rotation applies to user logs too): callers note the line
count or rt they start from, never the file's mtime alone. Papyrus prints floats with six decimals and bools as True /
False; both forms are accepted, as are missing fields (older script versions).
"""
import argparse
import json
import os
import re
import sys
import time

LINE = re.compile(r"^FO4SF rt=(?P<rt>-?\d+(?:\.\d+)?)"
                  r"(?: pos=(?P<x>-?\d+(?:\.\d+)?) (?P<y>-?\d+(?:\.\d+)?) (?P<z>-?\d+(?:\.\d+)?))?"
                  r"(?: ang=(?P<ang>-?\d+(?:\.\d+)?))?"
                  r"(?: cell=(?P<cell>\d+|none))?"
                  r"(?: world=(?P<world>\d+|none))?"
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


def latest(path, max_age=3.0):
    """The newest line, with ok False when the log is missing, empty or older than max_age seconds (file mtime: the
    game writes a line every half second while it runs, so a stale file means the game or the quest is not running)."""
    lines = read_lines(path)
    if not lines:
        return {"ok": False, "why": "no bridge lines in " + path}
    age = time.time() - os.path.getmtime(path)
    if max_age is not None and age > max_age:
        return {"ok": False, "why": f"log {age:.1f} s old (max {max_age})", "last": lines[-1]}
    return dict(lines[-1], ok=True)


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
    a = ap.parse_args(argv)
    log = a.log or default_log()
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
