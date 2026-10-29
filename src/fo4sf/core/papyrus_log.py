"""Starfield's Papyrus log (<My Games>/Starfield/Logs/Script/Papyrus.0.log) read into events, and two runs compared:
which errors are Starfield's own (they come in a vanilla run too) and which come only with us (docs/testing/
baseline.md, the vanilla baseline).

The format (verified: Install's copy of the 28 Oct new game run 3 log, Starfield 1.16.244):
  [18:07:42] error: Cannot call Disable() on a None object, aborting function call
  stack:
  	[SFBGS003_BountyScannerQuest (FD00556E)].SFBGS003:SFBGS003_ShutdownQuestScript.Shutdown() - "SFBGS003_ShutdownQuestScript.psc" Line 51
  	[Patch_Update7_1_SFBGS003 (FD00FFDF)].SFBGS003:Fragments:...Fragment_Stage_0000_Item_00() - "QF_...psc" Line 13
* One message per line, after the time of day in brackets (no date). "error: " starts an error, "warning: " a
  warning; any other message is a note here ("Cannot open store for class ...", "VM is freezing...", "Papyrus log
  opened (PC-64)", Debug.Trace lines).
* An error or a warning can be followed by "stack:" and its frames, one per line, each indented with a tab, the
  innermost call first. A native call ends - "<native>" Line ?; an object can have no name ("[ (0016E1D6)]") or be an
  alias ("[alias DerelictShips on quest SFFL_SE_EC08 (01058CDB)]").
* Form ids print as 8 hex digits. An FF id is made while the game runs, so the same thing gets another id in another
  run: the comparison reads every FF id as FF??????. Other ids are kept: Bethesda's own plugins load first, in a
  fixed order, so their ids are the same in two runs on the same built-in plugin set (scripts/game/baseline.py
  compare says when the built-in plugins' names or sizes differ from the baseline's).

A kind is one message with one stack; the count says how often it came. compare() puts each kind of the run in the
first group that fits: "both" (the baseline has the same kind), "ours" (it names one of our records or scripts:
fo4sf.core.loadset's prefixes, FO4 and FOCC), "both_place" (the baseline has the same message at the same script
line, from another caller or object) or "starfield" (Starfield's own scripts, but only in this run: the cost of what
we change). A kind of ours keeps how many baseline lines came at its script line. The baseline's kinds that the run
does not have, at a script line no "both_place" kind of the run has, are "baseline". Every baseline line is counted
in one group only. A group says where a message came, not why: a Starfield error only in our run can still be one
Starfield makes later in its own intro, which the baseline did not reach.
"""
import json
import re
from collections import Counter
from dataclasses import dataclass, field

from .loadset import OUR_PREFIXES

LEVELS = ("error", "warning", "note")
GROUPS = ("ours", "starfield", "both_place", "both", "baseline")
GROUP_TITLES = {
    "ours": "only in this run, naming one of ours",
    "starfield": "only in this run, Starfield's own scripts",
    "both_place": "in both runs at the same script line (other callers or objects)",
    "both": "in both runs (Starfield's own, or the game's)",
    "baseline": "only in the baseline",
}
_LINE = re.compile(r"^\[(?P<time>[^\]]{1,40})\] ?(?P<text>.*)$")
_FRAME = re.compile(r'^\s*\[(?P<obj>.*?)\]\.(?P<call>\S.*?) - "(?P<file>[^"]*)" Line (?P<line>\S+)\s*$')
_RUNTIME = re.compile(r"(?<![0-9A-Fa-f])FF[0-9A-Fa-f]{6}(?![0-9A-Fa-f])")
_ID = re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{8}(?![0-9A-Za-z])")
_NUMBER = re.compile(r"(?<![0-9A-Za-z#])\d+(?![0-9A-Za-z])")
_OURS = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(map(re.escape, OUR_PREFIXES)) + r")[A-Za-z0-9_]*", re.IGNORECASE)


@dataclass
class Event:
    level: str                  # error | warning | note
    text: str                   # the message after its level, as printed
    frames: list = field(default_factory=list)
    line: int = 0               # where the message is in the file (1-based)
    time: str = ""

    @property
    def key(self):
        """The kind: the level, the message and the stack, FF ids read as FF??????."""
        return (self.level, runtime_free(self.text), tuple(runtime_free(f) for f in self.frames))

    @property
    def place(self):
        """The same message at the same script line: ids and numbers in the message read as #, the innermost frame
        that is not a native call without its object; a message without a stack is its own place."""
        where = ""
        for f in self.frames:
            m = _FRAME.match(f)
            if m and m.group("file") != "<native>":
                where = f'{m.group("call")} - "{m.group("file")}" Line {m.group("line")}'
                break
        return (self.level, template(self.text), where)

    def ours(self):
        """Our names in the message or its stack (sorted, unique): our EditorIDs and scripts start with FO4 or FOCC
        (fo4sf.core.loadset.OUR_PREFIXES)."""
        found = set(_OURS.findall(self.text))
        for f in self.frames:
            found.update(_OURS.findall(f))
        return sorted(found, key=str.casefold)


@dataclass
class Log:
    path: str = ""
    events: list = field(default_factory=list)
    lines: int = 0
    unparsed: int = 0           # lines that are neither a message, nor "stack:", nor a frame after one

    def counts(self):
        c = Counter(e.level for e in self.events)
        return {lv: c.get(lv, 0) for lv in LEVELS}

    def kinds(self):
        """{key: [events]} in the order each kind first came."""
        out = {}
        for e in self.events:
            out.setdefault(e.key, []).append(e)
        return out


def runtime_free(text):
    return _RUNTIME.sub("FF??????", text)


def template(text):
    """The message with every form id, runtime or not, read as #id and every other number as #."""
    return _NUMBER.sub("#", _ID.sub("#id", text))


def parse(text, path=""):
    """A Log of the text: every message with its stack."""
    log = Log(path=path)
    current, in_stack = None, False
    rows = text.splitlines()
    log.lines = len(rows)
    for n, raw in enumerate(rows, 1):
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        m = _LINE.match(line)
        if m:
            body = m.group("text")
            level, msg = "note", body
            for lv in ("error", "warning"):
                if body.startswith(lv + ": "):
                    level, msg = lv, body[len(lv) + 2:]
                    break
            current = Event(level, msg, [], n, m.group("time"))
            log.events.append(current)
            in_stack = False
            continue
        if line.strip() == "stack:" and current is not None:
            in_stack = True
            continue
        if in_stack and line[:1] in ("\t", " ") and current is not None:
            current.frames.append(line.strip())
            continue
        log.unparsed += 1
    return log


def read(path):
    """The log at path, read as UTF-8 (a byte-order mark dropped); a byte that does not decode is replaced, so one odd
    byte never stops the read."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return parse(f.read(), path)


def compare(run, baseline, levels=("error", "warning")):
    """The run's kinds against the baseline's, as {"kinds": [...], "summary": {...}}, each kind in one group (module
    doc). Only the levels given are grouped (notes are counted, not grouped, by default: they are the log's own
    housekeeping and trace lines). A kind has run_count and baseline_count, its lines in each log ("both_place": the
    baseline's lines at its script line), and place_count, the baseline's lines at its script line from kinds the run
    does not have. A summary's baseline_lines count every baseline line once: the groups add up to the baseline's
    lines of those levels."""
    rk = {k: v for k, v in run.kinds().items() if k[0] in levels}
    bk = {k: v for k, v in baseline.kinds().items() if k[0] in levels}
    at_place = Counter()                  # the baseline's lines at each place, of the kinds the run does not have
    for k, evs in bk.items():
        if k not in rk:
            at_place[evs[0].place] += len(evs)
    kinds, shared = [], set()
    for k, evs in rk.items():
        e = evs[0]
        n = at_place.get(e.place, 0)
        if k in bk:
            kinds.append(_kind("both", e, len(evs), len(bk[k]), n))
        elif e.ours():
            kinds.append(_kind("ours", e, len(evs), 0, n))
        elif n:
            kinds.append(_kind("both_place", e, len(evs), n, n))
            shared.add(e.place)
        else:
            kinds.append(_kind("starfield", e, len(evs), 0, 0))
    for k, evs in bk.items():
        if k not in rk and evs[0].place not in shared:
            kinds.append(_kind("baseline", evs[0], 0, len(evs), 0))
    order = {g: i for i, g in enumerate(GROUPS)}
    kinds.sort(key=lambda x: (order[x["group"]], -max(x["run_count"], x["baseline_count"]), x["line"]))
    summary = {}
    for g in GROUPS:
        ks = [x for x in kinds if x["group"] == g]
        base = sum(at_place[p] for p in shared) if g == "both_place" else sum(x["baseline_count"] for x in ks)
        summary[g] = {"kinds": len(ks), "run_lines": sum(x["run_count"] for x in ks), "baseline_lines": base}
    return {"run": _about(run), "baseline": _about(baseline), "levels": list(levels), "summary": summary,
            "kinds": kinds}


def _kind(group, e, run_count, baseline_count, place_count):
    return {"group": group, "level": e.level, "text": e.text, "frames": list(e.frames), "place": e.place[2],
            "ours": e.ours(), "run_count": run_count, "baseline_count": baseline_count, "place_count": place_count,
            "line": e.line}


def _about(log):
    return {"path": log.path, "lines": log.lines, "unparsed": log.unparsed, **log.counts(),
            "kinds": len(log.kinds())}


def report_lines(rep, top=12):
    """The comparison as text: the totals, then each group's most frequent kinds (top per group; the rest are
    counted, and every kind is in the JSON report)."""
    r, b = rep["run"], rep["baseline"]
    out = [f"run:      {r['path']}: {r['error']} errors, {r['warning']} warnings, {r['note']} notes "
           f"({r['kinds']} kinds; {r['unparsed']} unparsed lines)",
           f"baseline: {b['path']}: {b['error']} errors, {b['warning']} warnings, {b['note']} notes "
           f"({b['kinds']} kinds; {b['unparsed']} unparsed lines)",
           f"compared: {', '.join(rep['levels'])}"]
    for g in GROUPS:
        s = rep["summary"][g]
        lines = s["baseline_lines"] if g == "baseline" else s["run_lines"]
        out.append("")
        out.append(f"{GROUP_TITLES[g]}: {s['kinds']} kinds, {lines} lines")
        ks = [x for x in rep["kinds"] if x["group"] == g]
        for x in ks[:top]:
            n = x["baseline_count"] if g == "baseline" else x["run_count"]
            where = f" at {x['place']}" if x["place"] else ""
            here = f"; {x['place_count']} baseline lines at this place" if g == "ours" and x["place_count"] else ""
            mine = f" [ours: {', '.join(x['ours'])}{here}]" if x["ours"] else ""
            out.append(f"  {n:4}x {x['level']}: {x['text'][:160]}{where}{mine}")
        if len(ks) > top:
            out.append(f"  ... and {len(ks) - top} more kinds (all in the JSON report)")
    return out


def write_report(rep, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
