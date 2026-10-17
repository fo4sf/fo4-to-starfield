"""Extra console commands of a queued terrain / npc_nav test: console_pre (typed after the save has loaded, before the
travel) and console_post (after the arrival, before the probes or the spawn). Only a strict whitelist is ever typed;
qstep.ps1 checks the same pattern again ($consoleOk) and OCRs the console after each command into obs.json "console".

Whitelist (docs/ai/test-queue.md "Console commands before and after the travel"; Starfield.exe 1.16.244 entries):
  GetINI "<name>:<Section>"             GetINISetting: "Prints an INI setting value to the console."
  SetINI "<name>:<Section>" <number>    SetINISetting: "Sets an INI setting value." (two String parameters)
  SetLocalTime <hour> [1]               the time-of-day commands of sky_light.py
  cgf "Game.SetLocalTime" <hour>
  fw <8 hex digits> [1]
  cgf "FO4SF_Probe.Pos" <decimal form id>   the bridge's probe (scripts/bridge/FO4SF_Probe.psc): a reference's
  cgf "FO4SF_Probe.Ack" "<tag>"             position / an acknowledgement / the player, as lines of the bridge's log
  cgf "FO4SF_Probe.Player"
  cgf "Debug.TraceUser" "fo4sf" "<text>"    a line of the bridge's log, the game's own acknowledgement of the console
  cgf "FO4SF_Probe.Resolve" "<plugin>" <id>     the scripted door's Step 0 (2026-10-16): what Game.GetFormFromFile
  cgf "FO4SF_Probe.MoveTo" "<plugin>" <id> <dx> <dy> <dz>   returns for a plugin-local id, and the player moved to it
                                            (plus the offset) as FO4SF_LoadDoor.psc moves the player: MoveTo can load
                                            another cell, so qstep.ps1 waits for the HUD after it (is_moveto)
  player.getav speedmult                    the run condition of a walk (2026-10-17): the first automated walk on
  player.setav speedmult 100                1d4591b6 moved about 14 m/s against the calibrated 4.6 m/s, a speedmult
                                            inherited from the save (supported hypothesis); the reset lasts the session
                                            only (the runner never saves after the start). speedmult_condition judges it
names and sections [A-Za-z0-9_]{1,64}, hours 0..23.99, numbers -?\\d{1,9}(.\\d{1,6})?, tags [A-Za-z0-9_.-]{1,40},
plugins [A-Za-z0-9_.-]{1,60}.esm|esp|esl, plugin-local ids \\d{1,8} (decimal), offsets -?\\d{1,5}(.\\d{1,3})? (metres).

Replies (parsed at judge time from the OCR, best effort; the raw OCR and the capture are always kept): GetINI prints
"INISetting <name:Section> >> <value>" (formats %i / %u / %.4f / '%s' / NOT FOUND in the exe: supported hypothesis);
SetINI's errors are 'INI setting "<name>" does not exist' / 'is not a boolean|int|float|string'; SetLocalTime's
"SetLocalTime only works on a planet." and "Invalid time %.2f passed to SetLocalTime".
"""
import re

NAME = r"[A-Za-z0-9_]{1,64}:[A-Za-z0-9_]{1,64}"
HOUR = r"(?:1?\d|2[0-3])(?:\.\d{1,2})?"
PLUGIN = r"[A-Za-z0-9_.-]{1,60}\.es[mpl]"
OFFSET = r"-?\d{1,5}(?:\.\d{1,3})?"
PATTERN = (rf'GetINI "{NAME}"|SetINI "{NAME}" -?\d{{1,9}}(?:\.\d{{1,6}})?|SetLocalTime {HOUR}(?: 1)?'
           rf'|cgf "Game\.SetLocalTime" {HOUR}|fw [0-9A-Fa-f]{{8}}(?: 1)?'
           # the bridge's probe functions and a TraceUser acknowledgement (docs/ai/test-queue.md "Bridge"): they only
           # write lines to the bridge's user log; the decimal form id, a tag of letters, digits, _ . -
           rf'|cgf "FO4SF_Probe\.Pos" \d{{1,10}}|cgf "FO4SF_Probe\.Ack" "[A-Za-z0-9_.-]{{1,40}}"|cgf "FO4SF_Probe\.Player"'
           rf'|cgf "Debug\.TraceUser" "fo4sf" "[A-Za-z0-9_ .-]{{1,60}}"'
           # the scripted door's Step 0 (FO4SF_Probe.Resolve / MoveTo): a plugin file name in quotes, the plugin-local
           # decimal id, and for MoveTo three offsets in metres (typed with a decimal point: whether the console turns
           # "0" into a float argument is not known)
           rf'|cgf "FO4SF_Probe\.Resolve" "{PLUGIN}" \d{{1,8}}'
           rf'|cgf "FO4SF_Probe\.MoveTo" "{PLUGIN}" \d{{1,8}} {OFFSET} {OFFSET} {OFFSET}'
           # the player's movement speed multiplier: read it, and set it back to the default 100 (nothing else)
           r'|player\.getav speedmult|player\.setav speedmult 100')
CONSOLE_RE = re.compile(PATTERN)
MOVETO_PREFIX = 'cgf "FO4SF_Probe.MoveTo" '
PROBE_TRAVEL_PREFIXES = ('cgf "FO4SF_Probe.Resolve" ', MOVETO_PREFIX)
SPEEDMULT_GET = "player.getav speedmult"
SPEEDMULT_SET = "player.setav speedmult 100"
# console_pre of a test planned with --speedmult: the value the save brought (reported), the reset, the value the test
# starts with (judged: speedmult_condition)
SPEEDMULT_PRE = [SPEEDMULT_GET, SPEEDMULT_SET, SPEEDMULT_GET]
SPEEDMULT_DEFAULT = 100.0
SPEEDMULT_TOL = 0.5
CONSOLE_KEYS = ("console_pre", "console_post")
MAX_COMMANDS = 12


def allowed(cmd):
    return isinstance(cmd, str) and CONSOLE_RE.fullmatch(cmd) is not None


def is_moveto(cmd):
    """A whitelisted FO4SF_Probe.MoveTo line: it may load another cell, so the step waits for the HUD after it."""
    return allowed(cmd) and cmd.startswith(MOVETO_PREFIX)


def uses_probe_travel(test):
    """Whether a planned test types FO4SF_Probe.Resolve / MoveTo (runner feature probe_moveto)."""
    return any(isinstance(c, str) and c.startswith(PROBE_TRAVEL_PREFIXES)
               for k in CONSOLE_KEYS for c in (test.get(k) or []))


def uses_speedmult(test):
    """Whether a planned test reads the player's speedmult before the travel (runner feature speedmult)."""
    return any(c in (SPEEDMULT_GET, SPEEDMULT_SET) for k in CONSOLE_KEYS for c in (test.get(k) or []))


def with_speedmult(test):
    """The test with SPEEDMULT_PRE first in its console_pre (plan-walk / plan-movable --speedmult)."""
    pre = SPEEDMULT_PRE + [c for c in test.get("console_pre") or [] if c not in (SPEEDMULT_GET, SPEEDMULT_SET)]
    if len(pre) > MAX_COMMANDS:
        raise ValueError(f"console_pre with the speedmult lines has {len(pre)} commands, at most {MAX_COMMANDS}")
    return dict(test, console_pre=pre)


def console_fields(w, fail):
    """Validated console_pre / console_post of a plan.json entry; `fail(msg)` raises or exits."""
    out = {}
    for key in CONSOLE_KEYS:
        v = w.get(key) if isinstance(w, dict) else None
        if v is None or v == []:
            continue
        if not isinstance(v, list) or len(v) > MAX_COMMANDS:
            fail(f"{key} must be a list of at most {MAX_COMMANDS} console commands: {v!r}")
        for c in v:
            if not allowed(c):
                fail(f"{key}: {c!r} is not an allowed console command (GetINI \"<name>:<Section>\", "
                     f"SetINI \"<name>:<Section>\" <number>, SetLocalTime <h> [1], cgf \"Game.SetLocalTime\" <h>, "
                     f"fw <8 hex> [1], cgf \"FO4SF_Probe.Pos|Ack|Player\" ..., cgf \"Debug.TraceUser\" \"fo4sf\" \"<text>\", "
                     f"cgf \"FO4SF_Probe.Resolve\" \"<plugin>\" <id>, cgf \"FO4SF_Probe.MoveTo\" \"<plugin>\" <id> <dx> <dy> <dz>)")
        out[key] = list(v)
    return out


# ------------------------------------------------------------------------------------------------- reading replies
_MAP = str.maketrans({"i": "l", "|": "l", "!": "l", "1": "l", "0": "o", ";": ":"})
_DROP = set(" \t\r\n\"'“”‘’`")


def _norm(text):
    """(normalised string, original index of each of its characters): lower case, l / I / 1 / | alike, O / 0 alike,
    no whitespace and no quotes (the console OCR reads l for I, splits words and drops quotes, 2026-10-11)."""
    chars, idx = [], []
    for k, c in enumerate(text):
        if c in _DROP:
            continue
        chars.append(c.lower().translate(_MAP))
        idx.append(k)
    return "".join(chars), idx


def _after(text, needle, start=0):
    """Original index right after the LAST normalised occurrence of needle at or after original index start; None."""
    n, idx = _norm(text)
    s = next((j for j, k in enumerate(idx) if k >= start), len(idx))
    pos = n.rfind(_norm(needle)[0], s)
    if pos < 0:
        return None
    end = pos + len(_norm(needle)[0]) - 1
    return idx[end] + 1


VALUE_RE = re.compile(r"\s*>\s*>\s*(NOT\s*FOUND|'[^']*'|-?\d+(?:[.,]\d+)?)", re.I)


def reply(cmd, ocr):
    """{"status": value | not found | error | no reply | unread, "value": str or None, "note": str} for one command
    and the OCR text captured right after it. Only text after the command's last echo is read."""
    if not isinstance(ocr, str) or not ocr.strip():
        return {"status": "unread", "value": None, "note": "no OCR text"}
    echo = _after(ocr, cmd)
    start = echo if echo is not None else 0
    m = re.match(r'(GetINI|SetINI) "([^"]+)"', cmd)
    if m:
        setting = m.group(2)
        if m.group(1) == "GetINI":
            for needle in ("INISetting" + setting, setting):
                at = _after(ocr, needle, start)
                v = VALUE_RE.match(ocr, at) if at is not None else None
                if v:
                    val = v.group(1)
                    if re.fullmatch(r"NOT\s*FOUND", val, re.I):
                        return {"status": "not found", "value": None, "note": "INISetting >> NOT FOUND"}
                    return {"status": "value", "value": val.strip("'").replace(",", "."), "note": ""}
        err = re.search(r'INI\s*setting\s*"?([^"\n]*?)"?\s*(does\s*not\s*exist|is\s*not\s*an?\s*[a-z]+)', ocr[start:],
                        re.I)
        if err and _norm(err.group(1))[0].split(":")[0] == _norm(setting.split(":")[0])[0]:
            return {"status": "error", "value": None, "note": re.sub(r"\s+", " ", err.group(0))}
        if m.group(1) == "SetINI":
            return {"status": "no reply", "value": None, "note": "" if echo is not None else "echo not read"}
        return {"status": "unread", "value": None, "note": "no INISetting reply read" +
                ("" if echo is not None else " (echo not read)")}
    if cmd == SPEEDMULT_GET:
        # "GetActorValue: SpeedMult >> 100.00" (supported hypothesis: the form Fallout 4 and Skyrim print, not yet
        # seen in a Starfield capture); the number after ">>" behind the actor value's name, read after the echo
        at = _after(ocr, "SpeedMult >", start)
        v = VALUE_RE.match(ocr, at - 1) if at is not None else None
        if v and not re.fullmatch(r"NOT\s*FOUND", v.group(1), re.I):
            return {"status": "value", "value": v.group(1).replace(",", "."), "note": ""}
        return {"status": "unread", "value": None, "note": "no SpeedMult reply read" +
                ("" if echo is not None else " (echo not read)")}
    if cmd.startswith(("SetLocalTime", "cgf")):
        err = re.search(r"SetLocalTime\s*only\s*works\s*on\s*a\s*planet|Invalid\s*time\s*[-\d.,]*\s*passed", ocr[start:],
                        re.I)
        if err:
            return {"status": "error", "value": None, "note": re.sub(r"\s+", " ", err.group(0))}
    return {"status": "no reply", "value": None, "note": "" if echo is not None else "echo not read"}


def short(cmd):
    return cmd.replace('"', "")


def summary(test, obs):
    """'[console pre: GetINI bBorderRegionsEnabled:General = 1; SetINI ... (no reply)] [console post: ...]' for a test
    with console commands, and the parsed list for results.jsonl; ('', []) when it planned none."""
    planned = {k: test.get(k) or [] for k in CONSOLE_KEYS}
    if not any(planned.values()):
        return "", []
    got = [x for x in (obs or {}).get("console") or [] if isinstance(x, dict)]
    rows, parts = [], []
    for key, phase in (("console_pre", "pre"), ("console_post", "post")):
        if not planned[key]:
            continue
        mine = [x for x in got if x.get("phase") == phase]
        items = []
        for x in mine:
            r = reply(str(x.get("cmd", "")), x.get("ocr"))
            rows.append({"phase": phase, "cmd": x.get("cmd"), "status": r["status"], "value": r["value"],
                         "note": r["note"], "shot": x.get("shot")})
            items.append(short(str(x.get("cmd"))) + (f" = {r['value']}" if r["status"] == "value" else
                                                     f" ({r['status']}{': ' + r['note'] if r['note'] else ''})"))
        if len(mine) < len(planned[key]):
            items.append(f"{len(mine)} of {len(planned[key])} typed")
        parts.append(f"[console {phase}: " + "; ".join(items) + "]")
    return " ".join(parts), rows


def speedmult_condition(test, obs):
    """The run condition of a test whose console_pre reads the speedmult: None when it reads none; else
    (ok, detail): ok when the LAST read before the travel is the default 100 (within SPEEDMULT_TOL). Every read is
    named in the detail (the first one, before a reset, is what the save brought). An unread value is not ok: the
    walk's speed model and its JUMP / STUCK limits assume 100 (docs/terrain/walk-redrocket-sanctuary.md)."""
    if SPEEDMULT_GET not in (test.get("console_pre") or []):
        return None
    got = [x for x in (obs or {}).get("console") or [] if isinstance(x, dict) and x.get("phase") == "pre"]
    reads = []
    for x in got:
        if x.get("cmd") == SPEEDMULT_GET:
            r = reply(SPEEDMULT_GET, x.get("ocr"))
            reads.append(float(r["value"]) if r["status"] == "value" else None)
        elif x.get("cmd") == SPEEDMULT_SET:
            reads.append("set 100")
    shown = ", ".join("unread" if r is None else r if isinstance(r, str) else f"{r:g}" for r in reads) or "nothing typed"
    last = next((r for r in reversed(reads) if not isinstance(r, str)), "none")
    if last == "none":
        return False, f"speedmult not read before the travel ({shown})"
    if last is None:
        return False, f"speedmult unread at the start ({shown})"
    if abs(last - SPEEDMULT_DEFAULT) > SPEEDMULT_TOL:
        return False, f"speedmult {last:g} at the start, not {SPEEDMULT_DEFAULT:g} ({shown})"
    return True, f"speedmult {last:g} at the start ({shown})"
