"""Judges for the combined-core PC probes P1 to P10 (docs/spikes/combined-core-probes.md is the runbook).

The probes themselves run on the owner's PC (the plugin FO4SFCombinedProbe.esm with its Papyrus scripts, and the SFSE
plugin FOCCSidecar.dll for P1); what comes back is text: the user log the scripts write, the SFSE plugin's JSON-lines
log and sidecar files, a `saves.json` listing, and the stage's compile receipts. This module reads that text and gives
one verdict per probe, by the queue's rule (scripts/game/README.md, docs/terrain/door-rounds.md): **PASS only from the
attempt's own evidence, FAIL from contradicting evidence, INCONCLUSIVE whenever a read, log or file is missing.** Empty
input is never a PASS. Every verdict quotes the lines it rests on with file and line number, and labels the thresholds
it used as placeholders (they are not design numbers). Nothing here touches a game.

Trace format (the contract group A's scripts write; `Trace()` in FOCC_ProbeQuest.psc):

    [21:29:40] FOCC rt=12.345 p2 set loc=50331649 local=2054 value=37.000000 readback=37.000000
    FOCC init variant=default
    FOCC p10 quest started id=-16707575 local=2080

An optional `[clock]` prefix (the game's clock), the word `FOCC`, an optional `rt=<seconds>` (Utility.GetCurrentRealTime),
then words naming the event (`p2 set`, `init`, `where`, ...) and `key=value` fields. Papyrus prints a form id as a SIGNED
decimal int (a runtime id FFxxxxxx comes out negative), floats with six decimals, bools as True / False; `pos=x y z` is
three numbers. `hex2dec` / `dec2hex` convert ids both ways for the console (`cgf` takes ints, `prid` takes hex).

P1's inputs are the SFSE plugin's log, one JSON object per line, e.g. `{"event":"pre_save","save":"focc_p1_a","counter":3}`,
`{"event":"post_load","save":"focc_p1_a","found":true,"valid":true,"counter":3}`, its `sidecars/*.focc` files (the
sidecar.py envelope with the stub world state `{"probe":"P1","counter":k}`), and `saves.json` (`Get-ChildItem ... *.sfs |
Select Name,Length | ConvertTo-Json`: a list of {"Name","Length"}, or one object when PowerShell saw one file).

Collection folder (`python -m fo4sf.combined.probes pN DIR`, or `pN --collect DIR`): `focc_session1.log` and
`focc_session2.log` for the two-launch probes P2 and P3, `focc.0.log` (or `focc_session1.log`) for the one-launch probes,
`saves.json` for P1, P4 and P8, `compile_p5_array129.txt` for P5, `offline_check.txt`, `plan.json` and `FOCC_Probe.psc`
(copied from the stage) for P10, and `sfse/focc_sidecar.log` plus `sfse/sidecars/` for P1. `pN FILE` with a single
log file works for the one-launch probes; a two-launch probe given one file is INCONCLUSIVE by construction.

Exit codes: 0 PASS, 1 FAIL, 2 INCONCLUSIVE (for `all`: the worst of the probes that had any input).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from dataclasses import dataclass, field

from . import sidecar

PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"
_RANK = {PASS: 0, FAIL: 1, INCONCLUSIVE: 2}
PROBES = ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10")

# Placeholder thresholds (plan item 8): labelled in every verdict that uses them, never design numbers.
PLACEHOLDERS = {
    "save_growth_bytes": 2 * 1024 * 1024,     # P4, P8: after - before may grow by at most max(2 MB, 5 % of before)
    "save_growth_share": 0.05,
    "p4_min_loaded_cycles": 18,               # P4: actors seen loaded in at least 18 of 20 cycles
    "p4_max_unloaded_cycles": 2,              # P4: loaded=0 in more than 2 cycles is a spawn problem (INCONCLUSIVE)
    "p5_max_tick_ms": 1000.0,                 # P5: a single tick above this fails
    "p9_arrive_m": 10.0,                      # P9: arrived when dist < 10 m
    "p9_seconds": 600.0,                      # P9: within 600 s
    "p9_start_m": 400.0,                      # P9: the route must start at least 400 m out
    "p9_min_cells": 4,                        # P9: distinct parent cells among the samples
    "p9_stuck_m": 2.0,                        # P9: dist unchanged within 2 m ...
    "p9_stuck_s": 120.0,                      # ... for 120 s while loaded = stuck
    "p9_jump_m_per_s": 15.0,                  # P9: faster than this between samples reads as a teleport, not a walk
    "p10_start_window_s": 10.0,               # P10: the quest must start within 10 s (rt) of the send
    "float_eq": 1e-3,                         # readback equals value within this
}

# Plugin-local ids of the probe records (plan "records"); the scripts log the local id they resolved, we only compare.
LOCAL = {"p2_loc": 2054, "p3_noparent": 2055, "p3_chained": 2056, "p10_quest": 2080,
         "p4_marker": 0x80B, "p8_parent0": 0x80C, "p8_child0": 0x80F, "p9_dest": 0x81B, "p10_event": 0x81F,
         "holder": 0x805, "p6_list": 0x81C, "p7_list": 0x81D, "p7_rep": 0x81E,
         "route": 0x809, "p5_first": 0x823, "p5_last": 0x854}   # dotnet/CombinedProbe ids
# what the cards ask for (docs/spikes/combined-core-probes.md P4 / P5): a shorter run is INCONCLUSIVE, not a PASS, so
# a typo in `cgf "FOCC_Probe.P4Run" 3 8.0` is never recorded as the 20-cycle bloat answer
P4_CYCLES = 20
P5_TICKS = 10

_NUM = r"-?\d+(?:\.\d+)?"
_LINE = re.compile(r"^(?:\[[^\]]*\]\s*)?FOCC(?:\s+rt=(?P<rt>" + _NUM + r"))?(?P<rest>(?:\s+\S+)*)\s*$")
_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


# ----------------------------------------------------------------------------------------------- id conversions

def hex2dec(h: str) -> int:
    """`FF012345` (the console's spelling) -> the SIGNED int Papyrus prints and `cgf` wants."""
    v = int(h.strip().lower().removeprefix("0x"), 16) & 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def dec2hex(d) -> str:
    """A Papyrus signed int (as int or text) -> eight upper-case hex digits."""
    return f"{int(d) & 0xFFFFFFFF:08X}"


# ----------------------------------------------------------------------------------------------- trace parsing

@dataclass
class Event:
    file: str
    line: int
    text: str
    kind: str                          # the words before the first key=value, lower case, e.g. "p2 set", "init"
    rt: float | None
    fields: dict = field(default_factory=dict)

    def cite(self) -> dict:
        return {"file": self.file, "line": self.line, "text": self.text}

    def num(self, key: str):
        v = self.fields.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    def flag(self, key: str):
        v = self.fields.get(key)
        if isinstance(v, str) and v.lower() in ("true", "false", "1", "0"):
            return v.lower() in ("true", "1")
        return None

    def form(self, key: str):
        """A form id field as 8 hex, None for `none` or a missing / unparsable value."""
        v = self.fields.get(key)
        if v is None or v == "none":
            return None
        try:
            return dec2hex(v)
        except ValueError:
            return None


def parse_line(text: str, file: str = "-", line: int = 0) -> Event | None:
    """One trace line as an Event, or None for anything that is not a FOCC line (Papyrus warnings, a torn line)."""
    m = _LINE.match(text.rstrip("\r\n"))
    if not m:
        return None
    words, fields, key = [], {}, None
    for tok in m.group("rest").split():
        k, eq, v = tok.partition("=")
        if eq and _WORD.match(k):
            key = k.lower()
            fields[key] = v
        elif key is None:
            words.append(tok.lower())
        else:
            fields[key] = (fields[key] + " " + tok).strip()      # `pos=x y z`: the bare numbers after a value
    if not words and not fields:
        return None
    rt = float(m.group("rt")) if m.group("rt") else None
    return Event(file, line, text.rstrip("\r\n"), " ".join(words), rt, fields)


def parse_log(lines, file: str = "-") -> list[Event]:
    out = []
    for n, s in enumerate(lines, 1):
        e = parse_line(s, file, n)
        if e is not None:
            out.append(e)
    return out


def pos(e: Event, key: str = "pos"):
    v = e.fields.get(key)
    if not v:
        return None
    parts = v.split()
    if len(parts) != 3:
        return None
    try:
        return [float(x) for x in parts]
    except ValueError:
        return None


# ----------------------------------------------------------------------------------------------- inputs

@dataclass
class Collection:
    """Everything a checker may read, as text already loaded: logs by name (lists of lines), the SFSE log, sidecar
    bodies by file name, saves.json parsed, and other text files by name. Tests build one from strings; `collect()`
    reads a folder."""
    logs: dict = field(default_factory=dict)        # name -> list[str]
    sfse_log: list | None = None                    # lines of sfse/focc_sidecar.log
    sidecars: dict | None = None                    # file name -> text (None when the folder is missing)
    saves: list | None = None                       # [{"Name": "x.sfs", "Length": 123}, ...]
    files: dict = field(default_factory=dict)       # other text files by name
    plan: dict | None = None                        # plan.json parsed
    source: str = ""

    def events(self, name: str) -> list[Event]:
        return parse_log(self.logs.get(name, []), name)

    def session(self, n: int) -> list[Event] | None:
        """Events of focc_session<n>.log; for n == 1 also focc.0.log. None when the file is absent."""
        for name in ([f"focc_session{n}.log", "focc.0.log"] if n == 1 else [f"focc_session{n}.log"]):
            if name in self.logs:
                return self.events(name)
        return None

    def any_logs(self) -> list[list[Event]]:
        return [self.events(n) for n in sorted(self.logs)]


_LOG_NAMES = ("focc_session1.log", "focc_session2.log", "focc.0.log")
_TEXT_NAMES = ("compile_p5_array129.txt", "offline_check.txt", "FOCC_Probe.psc")


def _read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def collect(path: str) -> Collection:
    """Load a collection folder (module docstring layout) or a single log file."""
    c = Collection(source=path)
    if os.path.isfile(path):
        c.logs[os.path.basename(path)] = _read_lines(path)
        return c
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    for name in _LOG_NAMES:
        p = os.path.join(path, name)
        if os.path.isfile(p):
            c.logs[name] = _read_lines(p)
    for name in _TEXT_NAMES:
        p = os.path.join(path, name)
        if os.path.isfile(p):
            c.files[name] = "\n".join(_read_lines(p))
    p = os.path.join(path, "saves.json")
    if os.path.isfile(p):
        c.saves = load_saves("\n".join(_read_lines(p)))
    p = os.path.join(path, "plan.json")
    if os.path.isfile(p):
        try:
            c.plan = json.loads("\n".join(_read_lines(p)))
        except ValueError:
            c.plan = None
    p = os.path.join(path, "sfse", "focc_sidecar.log")
    if os.path.isfile(p):
        c.sfse_log = _read_lines(p)
    d = os.path.join(path, "sfse", "sidecars")
    if os.path.isdir(d):
        c.sidecars = {}
        for name in sorted(os.listdir(d)):
            if name.endswith(sidecar.EXTENSION):
                c.sidecars[name] = "\n".join(_read_lines(os.path.join(d, name)))
    return c


def load_saves(text: str) -> list | None:
    """saves.json as a list of {"Name", "Length"}; PowerShell writes one object (not a list) for a single file. None
    when the text is not that shape."""
    text = text.lstrip("﻿")
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(x, dict) and "Name" in x for x in data):
        return None
    return data


def save_sizes(saves: list | None) -> dict:
    """{stem: Length} for every entry whose Length is an int; a missing Length is left out."""
    out = {}
    for s in saves or []:
        name = str(s.get("Name", ""))
        stem = name[:-4] if name.lower().endswith(".sfs") else name
        if isinstance(s.get("Length"), int):
            out[stem] = s["Length"]
    return out


# ----------------------------------------------------------------------------------------------- verdicts

@dataclass
class Verdict:
    probe: str
    verdict: str
    reasons: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def cite(self, *events: Event) -> None:
        for e in events:
            if e is not None and e.cite() not in self.evidence:
                self.evidence.append(e.cite())

    def to_dict(self) -> dict:
        d = {"probe": self.probe, "verdict": self.verdict, "reasons": self.reasons, "evidence": self.evidence}
        d.update(self.extra)
        return d


def _worst(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: _RANK[v]) if verdicts else INCONCLUSIVE


def _by_kind(events: list[Event], kind: str) -> list[Event]:
    return [e for e in events if e.kind == kind]


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= PLACEHOLDERS["float_eq"]


def _has_init(events: list[Event]) -> Event | None:
    inits = _by_kind(events, "init")
    return inits[0] if inits else None


def _growth(v: Verdict, sizes: dict, before: str, after: str) -> str:
    """Save growth judged against the placeholder bound; records the numbers. Returns a verdict for that part."""
    v.extra["save_growth"] = {"before": sizes.get(before), "after": sizes.get(after),
                              "bound_placeholder": {"bytes": PLACEHOLDERS["save_growth_bytes"],
                                                    "share": PLACEHOLDERS["save_growth_share"]}}
    if before not in sizes or after not in sizes:
        v.reasons.append(f"saves.json lacks {before!r} or {after!r} (or their Length)")
        return INCONCLUSIVE
    growth = sizes[after] - sizes[before]
    bound = max(PLACEHOLDERS["save_growth_bytes"], PLACEHOLDERS["save_growth_share"] * sizes[before])
    v.extra["save_growth"]["growth"] = growth
    v.extra["save_growth"]["bound"] = int(bound)
    if growth > bound:
        v.reasons.append(f"save grew by {growth} bytes, above the placeholder bound {int(bound)}")
        return FAIL
    v.reasons.append(f"save growth {growth} bytes within the placeholder bound {int(bound)} (the number is the finding)")
    return PASS


# ----------------------------------------------------------------------------------------------- P1

def _sfse_events(lines: list[str] | None) -> list[tuple[int, dict, str]]:
    out = []
    for n, s in enumerate(lines or [], 1):
        s = s.strip()
        if not s:
            continue
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict) and "event" in d:
            out.append((n, d, s))
    return out


def decode_stub_sidecar(text: str, save_name: str | None = None) -> dict:
    """The P1 sidecar envelope with its stub world state: checks what sidecar.decode checks (format, schema, save
    name, sha256 over the sorted-keys JSON of world_state) without model.WorldState. Returns world_state; ValueError
    on any mismatch."""
    try:
        body = json.loads(text)
    except ValueError as e:
        raise ValueError(f"not JSON: {e}") from None
    if not isinstance(body, dict) or body.get("format") != sidecar.FORMAT:
        raise ValueError("format is not focc-sidecar")
    if body.get("schema") != sidecar.SCHEMA:
        raise ValueError(f"schema {body.get('schema')!r} is not {sidecar.SCHEMA}")
    if save_name is not None and body.get("save_name") != save_name:
        raise ValueError(f"save_name {body.get('save_name')!r} is not {save_name!r}")
    if "world_state" not in body or "sha256" not in body:
        raise ValueError("lacks world_state or sha256")
    state = json.dumps(body["world_state"], sort_keys=True)
    if sidecar.checksum(state) != body["sha256"]:
        raise ValueError("sha256 mismatch over the sorted-keys JSON of world_state")
    return body["world_state"]


def orphans(sidecar_names, save_names) -> list[str]:
    """Sidecar file names whose save is not among `save_names` (stems without .sfs), sorted; mirrors
    sidecar.orphans on names instead of a folder and never deletes."""
    wanted = {sidecar.sidecar_name(s) for s in save_names if s}
    return sorted(n for n in sidecar_names if n.endswith(sidecar.EXTENSION) and n not in wanted)


def check_p1(c: Collection) -> Verdict:
    v = Verdict("p1", INCONCLUSIVE)
    v.extra["settles"] = "CC-02: sidecar viability and orphan handling (engine-feasibility.md P1)"
    if c.sfse_log is None:
        v.reasons.append("sfse/focc_sidecar.log missing: the plugin's log was not collected")
        return v
    evs = _sfse_events(c.sfse_log)
    for n, d, s in evs:
        v.evidence.append({"file": "sfse/focc_sidecar.log", "line": n, "text": s})
    if not evs:
        v.reasons.append("the SFSE log has no JSON event lines (the plugin did not load or did not log)")
        return v
    pre, pre_line = {}, {}
    for n, d, s in evs:
        if d.get("event") == "pre_save" and isinstance(d.get("save"), str):
            pre[d["save"]], pre_line[d["save"]] = d, n
    post_line = {}
    for n, d, s in evs:
        name = d.get("save")
        if (d.get("event") == "post_save" and isinstance(name, str) and name in pre_line and n > pre_line[name]
                and name not in post_line):
            post_line[name] = n
    post_saves = set(post_line)
    # The log is appended across launches: a load only counts for a saved name when it follows that name's completed
    # save (its last pre_save and the post_save after it), so neither an older attempt's read-back nor a read between
    # PreSave and the save's completion stands in for this one's (Codex review of #431).
    loads = [d for n, d, s in evs if d.get("event") == "post_load"
             and (d.get("save") not in pre_line or n > post_line.get(d.get("save"), float("inf")))]
    if not loads:
        v.reasons.append("no post_load line: the plugin never saw a load (check the SFSE loader output)")
        return v
    if not pre:
        v.reasons.append("no pre_save line: nothing was saved while the plugin ran")
        return v
    if c.sidecars is None:
        v.reasons.append("sfse/sidecars folder missing")
        return v
    failed = False
    for name, d in sorted(pre.items()):
        fn = sidecar.sidecar_name(name)
        if name not in post_saves:
            v.reasons.append(f"pre_save {name!r} without post_save")
            failed = True
        if not isinstance(d.get("counter"), int) or isinstance(d.get("counter"), bool):
            v.reasons.append(f"pre_save {name!r} logs no integer counter: its sidecar and read-back cannot be tied to "
                             "this save event")       # Codex review of #431
            failed = True
        if d.get("written") is not True:        # an older sidecar may still sit under that name (Codex, #431)
            v.reasons.append(f"pre_save {name!r} reports written={d.get('written')!r}: this run's sidecar was not "
                             "written, so any file under its name is not this run's")
            failed = True
        if fn not in c.sidecars:
            v.reasons.append(f"pre_save {name!r} has no sidecar {fn} (name rule mismatch or write failed)")
            failed = True
            continue
        try:
            ws = decode_stub_sidecar(c.sidecars[fn], name)
        except ValueError as e:
            v.reasons.append(f"sidecar {fn} does not decode: {e}")
            failed = True
            continue
        if ws.get("probe") != "P1" or not isinstance(ws.get("counter"), int):
            v.reasons.append(f"sidecar {fn} world_state is not the P1 stub")
            failed = True
        elif ws.get("counter") != d.get("counter"):
            v.reasons.append(f"sidecar {fn} counter {ws.get('counter')} differs from pre_save counter {d.get('counter')}")
            failed = True
    for d in loads:
        name = d.get("save")
        if name in pre:
            if d.get("found") is not True or d.get("valid") is not True:
                v.reasons.append(f"post_load {name!r} found={d.get('found')} valid={d.get('valid')} for a saved name")
                failed = True
            elif d.get("counter") != pre[name].get("counter"):
                v.reasons.append(f"post_load {name!r} counter {d.get('counter')} is not the last pre_save counter "
                                 f"{pre[name].get('counter')}")
                failed = True
    if failed:
        v.verdict = FAIL
        return v
    read_back = [d for d in loads if d.get("save") in pre]
    if not read_back:
        v.reasons.append("no post_load of a saved name: the read-back half was not exercised (the post_load names "
                         f"were {sorted({str(d.get('save')) for d in loads})}; the saved names {sorted(pre)})")
        return v
    # Orphans after the delete: needs the save names to match .sfs stems, which is unverified (plan P1 risks).
    if c.saves is None:
        v.reasons.append("saves.json missing: every save event has its sidecar, but the orphan question is open")
        return v
    stems = list(save_sizes(c.saves)) or [str(s.get("Name", ""))[:-4] for s in c.saves]
    matched = sorted(set(pre) & set(stems))
    v.extra["save_names_logged"] = sorted(pre)
    v.extra["save_files"] = sorted(stems)
    if not matched:
        v.reasons.append("no SFSE save name equals a .sfs stem: the mapping between the message's name and the file "
                         "name is unverified; orphan handling left open")
        return v
    deleted = sorted(set(pre) - set(stems))
    expected = sorted(sidecar.sidecar_name(n) for n in deleted)
    got = orphans(c.sidecars, stems)
    v.extra["deleted_saves"] = deleted
    v.extra["orphans"] = got
    if got != expected:
        v.reasons.append(f"orphans {got} are not the deleted saves' sidecars {expected}")
        v.verdict = FAIL
        return v
    v.reasons.append(f"every pre_save has its post_save and a valid sidecar; {len(read_back)} post_load(s) of a saved "
                     f"name found it valid with the right counter; orphans are exactly {expected}")
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P2

def _same_launch(c: Collection, v: Verdict) -> bool:
    """True (with the reason appended) when focc_session2.log is a copy of focc_session1.log: the card says to copy
    focc.0.log twice, so the same log under both names is an easy mistake and never proves a relaunch."""
    a, b = c.logs.get("focc_session1.log"), c.logs.get("focc_session2.log")
    if a is not None and a == b:
        v.reasons.append("focc_session1.log and focc_session2.log are identical: one launch copied twice, not a relaunch")
        return True
    return False


def _set_before(s2: list[Event], set_kind: str, rd: Event, v: Verdict) -> bool:
    """True (with the reason appended) when session2 holds a `<set_kind>` line before the read: the value read back
    was written in the same launch, so persistence across a relaunch is not what was measured."""
    before = [e for e in s2 if e.kind == set_kind and e.line < rd.line]
    if before:
        v.cite(before[-1])
        v.reasons.append(f"the read follows a `{set_kind}` in the same launch (session2 line {before[-1].line}): not a "
                         "relaunch")
        return True
    return False


def _local(e: Event, key: str):
    """The plugin-local id of a form id field, or None: a full plugin's ids carry its load index in the top byte
    (local = low 24 bits), a light plugin's are FE + a 12-bit slot (local = low 12 bits)."""
    f = e.form(key)
    if f is None:
        return None
    n = int(f, 16)
    return n & 0xFFF if n >> 24 == 0xFE else n & 0xFFFFFF


def _foreign(e: Event, ids: dict) -> list[str]:
    """The form id fields of `e` that are missing or not the probe record's local id (`ids`: field -> local). A
    stale or foreign property binding must never stand in for the probe's own record (Codex review of #431)."""
    return [f for f, n in ids.items() if _local(e, f) != n]


def _foreign_reason(what: str, e: Event, bad: list[str], ids: dict) -> str:
    return (f"{what}: " + ", ".join(f"{f}={e.fields.get(f, 'missing')}" for f in bad) + " is not the probe's record "
            "(locals " + ", ".join(f"{f} {hex(ids[f])}" for f in bad) + ")")


def _is_plan_form(e: Event, field: str, want) -> bool | None:
    """Whether the logged form id `field` is plan.json's `plugin:hexid`: a Starfield.esm form (load index 00) by its
    whole id, another plugin's by its local id. None when either side is missing or unparsable."""
    plugin, _, hexid = str(want or "").rpartition(":")
    got = e.form(field)
    try:
        want_id = int(hexid, 16)
    except ValueError:
        return None
    if not plugin or got is None:
        return None
    got_id = int(got, 16)
    if plugin.lower() == "starfield.esm":
        return got_id == want_id
    return _local(e, field) == (want_id & (0xFFF if got_id >> 24 == 0xFE else 0xFFFFFF))


def check_p2(c: Collection) -> Verdict:
    v = Verdict("p2", INCONCLUSIVE)
    v.extra["settles"] = "CC-02: location keyword data persists across save/load, linked locations (P2)"
    s1, s2 = c.session(1), c.session(2)
    if s1 is None or s2 is None:
        v.reasons.append("needs focc_session1.log and focc_session2.log (two launches); persistence is never inferred "
                         "from one session")
        return v
    if _same_launch(c, v):
        return v
    sets, links = _by_kind(s1, "p2 set"), _by_kind(s1, "p2 link")
    refused = [e for e in s1 + s2 if e.kind.startswith("p2") and "refused" in e.kind.split()]
    v.cite(*refused)
    if refused:
        v.reasons.append("the script logged refused (a None property): the plugin's records did not resolve")
        return v
    if not sets:
        v.reasons.append("session1 has no `p2 set` line")
        return v
    st = sets[-1]
    v.cite(st)
    value, readback = st.num("value"), st.num("readback")
    if _local(st, "loc") != LOCAL["p2_loc"]:
        v.reasons.append(f"p2 set loc {st.fields.get('loc')} is not the probe location (local {LOCAL['p2_loc']})")
        return v
    for e, ids in ((st, {"holder": LOCAL["holder"]}),) + (((links[-1], {"route": LOCAL["route"]}),) if links else ()):
        bad = _foreign(e, ids)
        if bad:
            v.reasons.append(_foreign_reason(e.kind, e, bad, ids))
            return v
    if readback is None:
        v.reasons.append("p2 set has no readback")
        return v
    if not _close(value, readback):
        v.reasons.append(f"set value {value} and immediate readback {readback} differ: SetKeywordData did not take")
        v.verdict = FAIL
        return v
    link_ok = None
    want_link = (LOCAL["p2_loc"], LOCAL["p3_chained"])
    if links:
        v.cite(links[-1])
        if (_local(links[-1], "a"), _local(links[-1], "b")) != want_link:
            v.reasons.append(f"p2 link a/b are not the probe locations (locals {want_link[0]} and {want_link[1]})")
            return v
        link_ok = links[-1].flag("linked")
    init = _has_init(s2)
    if init is None:
        v.reasons.append("session2 has no `FOCC init` line: a relaunch is not proven")
        return v
    v.cite(init)
    reads = [e for e in s2 if e.kind == "p2 read" and e.line > init.line]
    linkreads = [e for e in s2 if e.kind == "p2 linkread" and e.line > init.line]
    if not reads:
        v.reasons.append("session2 has no `p2 read` line after init")
        return v
    rd = reads[-1]
    v.cite(rd)
    if _set_before(s2, "p2 set", rd, v):
        return v
    rv = rd.num("value")
    if _foreign(rd, {"holder": LOCAL["holder"]}):
        v.reasons.append(_foreign_reason("p2 read", rd, ["holder"], LOCAL))
        return v
    if _local(rd, "loc") != LOCAL["p2_loc"] or rv is None:
        v.reasons.append(f"p2 read is not on the probe location (local {LOCAL['p2_loc']}) or lacks a value")
        return v
    if not _close(rv, value):
        v.reasons.append(f"after relaunch the datum reads {rv}, set value was {value}: keyword data did not persist")
        v.verdict = FAIL
        return v
    v.reasons.append(f"datum {value} set in session1 (readback {readback}) read back as {rv} after a relaunch")
    if link_ok is True:
        if not linkreads:
            v.reasons.append("p2 link was True in session1 but session2 has no `p2 linkread`")
            return v
        v.cite(linkreads[-1])
        if _set_before(s2, "p2 link", linkreads[-1], v):   # relinked in the same launch (Codex review of #431)
            return v
        if _foreign(linkreads[-1], {"route": LOCAL["route"]}):
            v.reasons.append(_foreign_reason("p2 linkread", linkreads[-1], ["route"], LOCAL))
            return v
        if (_local(linkreads[-1], "a"), _local(linkreads[-1], "b")) != want_link:
            v.reasons.append(f"p2 linkread a/b are not the probe locations (locals {want_link[0]} and "
                             f"{want_link[1]})")
            return v
        if linkreads[-1].flag("linked") is not True:
            v.reasons.append("linked location was True in session1 and not True after relaunch")
            v.verdict = FAIL
            return v
        v.reasons.append("linked location survived the relaunch")
    elif link_ok is False:
        v.reasons.append("AddLinkedLocation did not link in session1 (IsLinkedLocation False)")
        v.verdict = FAIL
        return v
    else:
        v.reasons.append("no `p2 link` line: the linked-location half was not run, so P2 is not settled (run "
                         "P2Set in full; PASS needs set, link, read and linkread)")
        v.extra["linked_locations"] = "not run"
        return v
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P3

def check_p3(c: Collection) -> Verdict:
    v = Verdict("p3", INCONCLUSIVE)
    v.extra["settles"] = "CC-02 / interiors D1: keyword data on an unparented vs a chained LCTN; a cell's current location"
    v.extra["explored_state"] = {"status": "unresolved",
                                 "reason": "no verified Papyrus read of explored/cleared state in Starfield (FO4's "
                                           "IsCleared is missing, PC job 15); not judged"}
    parts = []
    # Keyword half: two sessions, default variant.
    s1, s2 = c.session(1), c.session(2)
    kw = None
    if s1 is not None and _by_kind(s1, "p3 set"):
        st = _by_kind(s1, "p3 set")[-1]
        v.cite(st)
        va, ra, vb, rb = st.num("va"), st.num("ra"), st.num("vb"), st.num("rb")
        if (_local(st, "a"), _local(st, "b")) != (LOCAL["p3_noparent"], LOCAL["p3_chained"]):
            v.reasons.append(f"p3 set a/b are not the probe locations (locals {LOCAL['p3_noparent']} and "
                             f"{LOCAL['p3_chained']})")
            kw = INCONCLUSIVE
        elif _foreign(st, {"holder": LOCAL["holder"]}):
            v.reasons.append(_foreign_reason("p3 set", st, ["holder"], LOCAL))
            kw = INCONCLUSIVE
        elif None in (va, ra, vb, rb):
            v.reasons.append("p3 set lacks va/ra/vb/rb")
            kw = INCONCLUSIVE
        elif not (_close(va, ra) and _close(vb, rb)):
            v.reasons.append(f"p3 set immediate readbacks ({ra}, {rb}) differ from the values ({va}, {vb})")
            kw = FAIL
        elif s2 is None:
            v.reasons.append("p3 keyword half needs focc_session2.log (a relaunch)")
            kw = INCONCLUSIVE
        elif _same_launch(c, v):
            kw = INCONCLUSIVE
        else:
            init = _has_init(s2)
            reads = [e for e in s2 if e.kind == "p3 read" and init is not None and e.line > init.line]
            if init is None or not reads:
                v.reasons.append("session2 lacks an init line or a `p3 read` after it")
                kw = INCONCLUSIVE
            else:
                rd = reads[-1]
                v.cite(init, rd)
                a_ok, b_ok = _close(rd.num("ra"), va), _close(rd.num("rb"), vb)
                if _set_before(s2, "p3 set", rd, v):
                    kw = INCONCLUSIVE
                elif _foreign(rd, {"holder": LOCAL["holder"]}):
                    v.reasons.append(_foreign_reason("p3 read", rd, ["holder"], LOCAL))
                    kw = INCONCLUSIVE
                elif (_local(rd, "a"), _local(rd, "b")) != (LOCAL["p3_noparent"], LOCAL["p3_chained"]):
                    # The relaunch read names its locations too (Codex review of #431).
                    v.reasons.append(f"p3 read a/b are missing or not the probe locations (locals "
                                     f"{LOCAL['p3_noparent']} and {LOCAL['p3_chained']})")
                    kw = INCONCLUSIVE
                elif a_ok and b_ok:
                    v.reasons.append("keyword data persisted on both the unparented and the chained location")
                    kw = PASS
                else:
                    v.reasons.append(f"after relaunch unparented reads {rd.num('ra')} (set {va}), chained reads "
                                     f"{rd.num('rb')} (set {vb})")
                    kw = FAIL
        v.extra["keyword_half"] = kw
        parts.append(kw)
    # Cell half: any log of the p3cells variant.
    cell = None
    for evs in c.any_logs():
        init = _has_init(evs)
        if init is None or init.fields.get("variant", "").lower() != "p3cells":
            continue
        v.cite(init)
        wheres = _by_kind(evs, "where")
        want = {"fo4port_redrocket01": LOCAL["p3_noparent"], "fo4port_superdupermart01": LOCAL["p3_chained"]}
        # One traversal = the latest Red Rocket `where` and the first Super Duper Mart `where` after it, so an
        # interrupted retry never borrows an older attempt's second cell (Codex review of #431).
        seen = {}
        firsts = [w for w in wheres if w.fields.get("cellname", "").lower() == "fo4port_redrocket01"]
        if firsts:
            seen["fo4port_redrocket01"] = firsts[-1]
            later = [w for w in wheres if w.line > firsts[-1].line
                     and w.fields.get("cellname", "").lower() == "fo4port_superdupermart01"]
            if later:
                seen["fo4port_superdupermart01"] = later[0]
        v.cite(*seen.values())
        if len(seen) < 2:
            v.reasons.append("cell half: both `where` lines (FO4Port_RedRocket01, FO4Port_SuperDuperMart01) are needed")
            cell = INCONCLUSIVE
        else:
            # The logged form id, not the script's local= label, names the location (Codex review of #431).
            bad = [n for n, w in seen.items() if _local(w, "loc") != want[n]]
            if bad:
                v.reasons.append(f"cell half: current location is none or another location for {bad}")
                cell = FAIL
            else:
                v.reasons.append("cell half: each overridden cell reports our location as the player's current one")
                cell = PASS
        v.extra["cell_half"] = cell
        parts.append(cell)
        break
    if not parts:
        v.reasons.append("neither the keyword half (p3 set / p3 read over two sessions) nor the p3cells variant was found")
        return v
    v.verdict = _worst(*parts)
    return v


# ----------------------------------------------------------------------------------------------- P4

def check_p4(c: Collection) -> Verdict:
    v = Verdict("p4", INCONCLUSIVE)
    v.extra["settles"] = "L3 spawn reliability and save bloat over 20 materialize/dissolve cycles (P4, rule L3)"
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    starts = _by_kind(evs, "p4 start")
    if not starts:                              # no attempt boundary, no verdict (Codex review of #431)
        v.reasons.append("no `p4 start` line: the cycles cannot be tied to one run of the probe's marker")
        return v
    evs = [e for e in evs if e.line >= starts[-1].line]   # the latest run only: an older one never fills its gaps
    v.cite(starts[-1])
    if _local(starts[-1], "marker") != LOCAL["p4_marker"]:   # the probe's own marker (Codex review of #431)
        v.reasons.append(f"p4 start marker {starts[-1].fields.get('marker')} is not FOCC_P4_SpawnMarker "
                         f"(local {LOCAL['p4_marker']})")
        return v
    if _is_plan_form(starts[-1], "base", _plan_bases(c.plan).get("npc")) is not True:
        v.reasons.append(f"p4 start base {starts[-1].fields.get('base', 'missing')} is not plan.json's npc base "
                         f"({_plan_bases(c.plan).get('npc')}): cannot tell the spawns are the probe's")
        return v
    done = _by_kind(evs, "p4 done")[:1]         # the run's own done closes it: later rows never count (Codex, #431)
    cycles = [e for e in _by_kind(evs, "p4 cycle") if not done or e.line < done[0].line]
    v.cite(*cycles, *done)
    if not done:
        v.reasons.append("no `p4 done` line: the run did not finish")
        return v
    want = int(done[0].num("cycles") or 0)
    if want < P4_CYCLES:
        v.reasons.append(f"only {want} cycles, the probe asks {P4_CYCLES} (cgf \"FOCC_Probe.P4Run\" {P4_CYCLES} 8.0): "
                         "not the bloat answer")
        return v
    seen = {}
    for e in cycles:
        n = e.num("n")
        if n is not None:
            seen[int(n)] = e
    modes = sorted({e.fields.get("mode", "?") for e in cycles})
    v.extra["modes"] = modes
    missing = [n for n in range(1, want + 1) if n not in seen]
    if missing:
        v.reasons.append(f"cycles missing: {missing}")
        return v
    numbers = sorted(int(e.num("n")) for e in cycles if e.num("n") is not None)
    if numbers != list(range(1, want + 1)):        # P5's rule: one row per cycle, no extras (Codex review of #431)
        v.reasons.append(f"the cycle lines are not numbered 1..{want} once each: repeated or extra cycles")
        return v
    short = [n for n, e in seen.items() if (e.num("placed") or 0) < 3 or (e.num("deleted") or 0) < 3]
    unloaded = [n for n, e in seen.items() if (e.num("loaded") or 0) < 1]
    if short:
        v.reasons.append(f"cycles with placed<3 or deleted<3: {sorted(short)}")
        v.verdict = FAIL
        return v
    if len(unloaded) > PLACEHOLDERS["p4_max_unloaded_cycles"]:
        v.reasons.append(f"actors never loaded in cycles {sorted(unloaded)} (placeholder: more than "
                         f"{PLACEHOLDERS['p4_max_unloaded_cycles']} such cycles is a spawn problem, not a bloat answer)")
        return v
    v.reasons.append(f"{want} cycles each placed 3 and deleted 3; loaded in {want - len(unloaded)} cycles")
    sizes = save_sizes(c.saves)
    if c.saves is None:
        v.reasons.append("saves.json missing")
        return v
    v.verdict = _growth(v, sizes, "focc_p4_before", "focc_p4_after")
    return v


# ----------------------------------------------------------------------------------------------- P5

def array_cap(text: str | None) -> dict:
    """`compile_p5_array129.txt` -> {"array_cap": 128 | None | "unknown", "detail": ...}. None when the compiler
    reported 'Compilation succeeded'; 128 only when it did not AND one of its own lines names the array (`129`,
    `128` or `array`): a compile that failed for another reason (flags file missing, bad include path) is "unknown"
    with the first error line, never the cap. The stage's own header line (`FOCC_P5_Array129.psc: new float[129] ...`,
    make_combined_probe.compile_array129) is left out of the search."""
    if text is None:
        return {"array_cap": "unknown", "detail": "compile_p5_array129.txt missing"}
    if "Compilation succeeded" in text:
        return {"array_cap": None, "detail": "new float[129] compiled: no compile-time cap at 128 "
                                             "(runtime growth still open)"}
    own = re.compile(r"^FOCC_P5_Array129\.psc: new float\[129\]|^exit code \d+$|^(compiled|refused):")
    lines = [l for l in text.splitlines() if l.strip() and not own.search(l.strip())]
    about = [l for l in lines if re.search(r"\b129\b|\b128\b|array", l, re.I)]
    if about:
        return {"array_cap": 128, "detail": "compiler refused new float[129]: " + about[0].strip()}
    err = next((l for l in lines if re.search(r"error|unable|cannot|fail|no output", l, re.I)), lines[0] if lines else "")
    return {"array_cap": "unknown", "detail": "compile failed for another reason (not the array size): " + err.strip()}


def check_p5(c: Collection) -> Verdict:
    v = Verdict("p5", INCONCLUSIVE)
    v.extra["settles"] = "Papyrus tick latency baseline over 50 places (L2 fallback), array cap at compile time (P5)"
    v.extra.update(array_cap(c.files.get("compile_p5_array129.txt")))
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    starts = _by_kind(evs, "p5 start")
    if not starts:
        v.reasons.append("no `p5 start` line")
        return v
    start = starts[-1]
    # the run's own done line closes it: ticks after it (appended or reordered evidence) never count (Codex, #431)
    dones = [e for e in _by_kind(evs, "p5 done") if e.line > start.line]
    done = dones[0] if dones else None
    ticks = [e for e in _by_kind(evs, "p5 tick") if e.line > start.line and (done is None or e.line < done.line)]
    v.cite(start, *ticks)
    ids = {"first": LOCAL["p5_first"], "last": LOCAL["p5_last"]}
    bad = _foreign(start, ids)
    if bad or (start.num("places") or 0) != 50:
        v.reasons.append(_foreign_reason("p5 start", start, bad, ids) if bad else
                         f"p5 start places={start.fields.get('places')}, want the probe's 50 globals")
        return v
    want = int(start.num("ticks") or 0)
    if want < P5_TICKS:
        v.cite(*ticks)
        v.reasons.append(f"the run asked for {want} ticks, the probe asks {P5_TICKS} (cgf \"FOCC_Probe.P5Tick\" "
                         f"{P5_TICKS}): too few for a baseline")
        return v
    good = [e for e in ticks if e.num("ms") is not None and (e.num("places") or 0) == 50]
    ms = [e.num("ms") for e in good]
    if len(ms) >= want and sorted(e.num("n") for e in good) != [float(n) for n in range(1, want + 1)]:
        # exactly 1..want once each: an extra row would skew the recorded baseline (Codex review of #431)
        v.reasons.append(f"the tick lines are not numbered 1..{want} once each: repeated, extra or missing ticks")
        return v                                # P5's own form of the P8 duplicate-row finding (Codex, #431)
    if len(ms) < want:
        v.reasons.append(f"{len(ms)} tick lines with places=50 after start, want {want}")
        v.verdict = FAIL if ticks else INCONCLUSIVE
        return v
    if done is None or (done.num("ticks") or 0) < want:   # a truncated copy never settles P5 (Codex review of #431)
        v.reasons.append(f"no `p5 done ticks={want}` after the ticks: the run did not finish or the log was cut")
        return v
    v.cite(done)
    v.extra["baseline_ms"] = {"min": min(ms), "median": statistics.median(ms), "max": max(ms),
                              "per_place_median": statistics.median(ms) / 50, "ticks": len(ms),
                              "note": "record under docs/ai/optimization.md's before/after rule"}
    if max(ms) > PLACEHOLDERS["p5_max_tick_ms"]:
        v.reasons.append(f"a tick took {max(ms)} ms, above the placeholder {PLACEHOLDERS['p5_max_tick_ms']} ms")
        v.verdict = FAIL
        return v
    v.reasons.append(f"{len(ms)} ticks over 50 globals, median {statistics.median(ms):.3f} ms (recorded, not judged "
                     f"beyond the placeholder cap)")
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P6 / P7

def _plan_bases(plan: dict | None) -> dict:
    """plan.json's base mapping: make_combined_probe nests lvln_a / lvln_b under `bases`; a flat plan is accepted too."""
    if not plan:
        return {}
    bases = plan.get("bases")
    return bases if isinstance(bases, dict) else plan


def _skipped(plan: dict | None, group: str, flag: str) -> bool:
    """True when the stage left a record group out: plan.json `"<flag>": false` (the runbook's spelling) or `group`
    in its `skip` list (what make_combined_probe writes from --skip)."""
    if not plan:
        return False
    skip = plan.get("skip")
    return plan.get(flag) is False or (isinstance(skip, list) and group in skip)


def _base_match(e: Event, plan: dict | None, key_a: str, key_b: str):
    """Which list entry a spawned actor's base is. FOCC_ProbeQuest.SpawnTrials writes `baselocal=a|b|other|none`
    (its BaseName(): the base compared with the P6BaseA / P6BaseB properties), which decides on its own; an explicit
    `match=A|B|none` field is honoured too; a `baselocal=<plugin:hexid>` is mapped through plan.json's bases
    (`lvln_a` / `lvln_b`). "other" is a base that is neither entry; None when it cannot be told."""
    m = e.fields.get("match")
    if m is not None:
        m = m.upper()
        return m if m in ("A", "B") else "none"
    bl = e.fields.get("baselocal", "none")
    if bl.lower() == "none" or e.fields.get("base", "none").lower() == "none":
        return "none"
    bases = _plan_bases(plan)
    if bl.lower() in ("a", "b"):
        # The label is only the script's comparison with its own properties, so the logged runtime id must agree with
        # plan.json's base (Codex review of #431): a Starfield.esm base (load index 00) by its whole id, a base in
        # another plugin by its local id. No plan, no base mapping or a mismatch: cannot be told.
        ok = _is_plan_form(e, "base", bases.get(key_a if bl.lower() == "a" else key_b))
        return bl.upper() if ok else None
    if bl.lower() == "other":
        return "other"
    if bases.get(key_a) and bases.get(key_b):
        if bl.lower() == str(bases[key_a]).lower():
            return "A"
        if bl.lower() == str(bases[key_b]).lower():
            return "B"
    return None


def _conditioned_list(v: Verdict, evs: list[Event], kind: str, key: str, cases: dict, plan, pa, pb, readback_key,
                      ids: dict):
    """Shared P6/P7 judge: for each value in `cases` (value -> expected entry), 3 trials naming that entry. `ids` maps
    a trial line's form id field to the probe record's local id (the list and what its conditions read)."""
    trials = _by_kind(evs, kind)
    refused = [e for e in evs if e.kind == f"{kind} refused"]
    v.cite(*trials, *refused)
    if refused:
        v.reasons.append("the script refused: " + "; ".join(e.text for e in refused))
        return INCONCLUSIVE
    if not trials:
        v.reasons.append(f"no `{kind}` trial lines")
        return INCONCLUSIVE
    for value, want in cases.items():
        mine = [e for e in trials if _close(e.num(key), value)][-3:]     # the latest call's trials only
        if len(mine) < 3 or [e.num("trial") for e in mine] != [1.0, 2.0, 3.0]:
            v.reasons.append(f"{key}={value}: the latest trials are {[e.num('trial') for e in mine]}, want 1, 2, 3 "
                             "from one call")
            return INCONCLUSIVE
        for e in mine:
            # the script's properties must be the probe's own records, or a stale or foreign binding passes without
            # exercising our LVLN / KYWD / GLOB (Codex review of #431)
            bad = _foreign(e, ids)
            if bad:
                v.reasons.append(_foreign_reason(f"{key}={value}", e, bad, ids))
                return INCONCLUSIVE
            rb = e.num(readback_key)
            if rb is not None and not _close(rb, value):
                v.reasons.append(f"{key}={value}: readback {rb} differs ({readback_key})")
                return INCONCLUSIVE
            if e.form("loc") is None and "loc" in e.fields:
                v.reasons.append(f"{key}={value}: loc=none, the player had no current location")
                return INCONCLUSIVE
        got = [_base_match(e, plan, pa, pb) for e in mine]
        if any(g is None for g in got):
            v.reasons.append(f"{key}={value}: cannot tell which entry spawned (baselocal is neither a/b/other nor a "
                             f"plugin:id that plan.json's bases {pa}/{pb} name)")
            return INCONCLUSIVE
        if any(g == "none" for g in got):
            v.reasons.append(f"{key}={value}: a spawn resolved to no base")
            return FAIL
        if any(g == "other" for g in got):
            v.reasons.append(f"{key}={value}: a spawn resolved to a base that is neither entry A nor B")
            return FAIL
        if any(g != want for g in got):
            v.reasons.append(f"{key}={value}: expected entry {want}, got {got}")
            return FAIL
    v.reasons.append("every trial spawned the entry its condition selects: " +
                     ", ".join(f"{key}={k} -> {w}" for k, w in cases.items()))
    return PASS


def check_p6(c: Collection) -> Verdict:
    v = Verdict("p6", INCONCLUSIVE)
    v.extra["settles"] = "data-only territory spawns: LVLN entries conditioned on GetKeywordDataForCurrentLocation (P6)"
    if _skipped(c.plan, "lvln", "lvln_conditions_written"):
        v.reasons.append("the stage says the LVLN entry conditions could not be written (Mutagen): P6 blocked")
        v.extra["blocked"] = True
        return v
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    v.verdict = _conditioned_list(v, evs, "p6", "datum", {1.0: "A", 2.0: "B"}, c.plan, "lvln_a", "lvln_b", "readback",
                                 {"list": LOCAL["p6_list"], "holder": LOCAL["holder"]})
    return v


def check_p7(c: Collection) -> Verdict:
    v = Verdict("p7", INCONCLUSIVE)
    v.extra["settles"] = "conditions read our reputation global (P7 minimal form)"
    v.extra["p7b_vendor"] = {"status": "deferred",
                             "reason": "a vendor refusing service needs an NPC_ with VEND/PLVD, a merchant container "
                                       "and conditioned dialogue; no converter of ours produces them yet"}
    if _skipped(c.plan, "lvln", "lvln_conditions_written"):
        v.reasons.append("the stage says the LVLN entry conditions could not be written (Mutagen): P7 blocked")
        v.extra["blocked"] = True
        return v
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    v.verdict = _conditioned_list(v, evs, "p7", "tier", {3.0: "A", 9.0: "B"}, c.plan, "lvln_a", "lvln_b", "glob",
                                 {"list": LOCAL["p7_list"], "rep": LOCAL["p7_rep"]})
    return v


# ----------------------------------------------------------------------------------------------- P8

def check_p8(c: Collection) -> Verdict:
    v = Verdict("p8", INCONCLUSIVE)
    v.extra["settles"] = "build stages without player building: enable-parent swap and its save cost (P8)"
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    moves = _by_kind(evs, "p8 move")
    firsts = [e for e in moves if e.num("stage") == 0.0]
    if firsts:                                  # judge only the latest P8Move: an older run's lines never count
        evs = [e for e in evs if e.line >= firsts[-1].line]
    elif moves:
        evs = [e for e in evs if e.line >= moves[-1].line]
    move = _by_kind(evs, "p8 move")
    v.cite(*move)
    if not move:
        v.reasons.append("no `p8 move` line: the refs were not brought into the player's merged frame")
        return v
    # P8Move logs stage 0, 1, 2 in one call; a call that stopped early leaves stages unmoved (Codex review of #431).
    moved = [e.num("stage") for e in move]
    if moved[:3] != [0.0, 1.0, 2.0]:
        v.reasons.append(f"the latest P8Move logged stages {moved}, want 0, 1, 2: not every stage was moved")
        return v
    wrong = [k for k, e in enumerate(move[:3]) if _local(e, "parent") != LOCAL["p8_parent0"] + k]
    if wrong:                                   # the probe's own parents, by logged id (Codex review of #431)
        v.reasons.append(f"p8 move stage {wrong}: parent is not FOCC_P8_Stage<k>Parent (locals "
                         f"{LOCAL['p8_parent0']}..{LOCAL['p8_parent0'] + 2})")
        return v
    evs = [e for e in evs if e.line > move[2].line]
    stages = [e for e in evs if e.kind == "p8" and set(e.fields) == {"stage"}]      # `FOCC p8 stage=<s>`
    children = _by_kind(evs, "p8 child")
    v.cite(*stages, *children)
    if len(stages) < 3 or len(children) < 36:
        v.reasons.append(f"{len(stages)} stage lines and {len(children)} child lines, want 3 and 36")
        return v
    seq = [st.num("stage") for st in stages[-3:]]
    if seq != [1.0, 2.0, 0.0]:
        v.reasons.append(f"the last three stage commands were {seq}, the card asks for 1, 2, 0 in that order")
        return v
    stages = stages[-3:]
    children = [e for e in children if e.line > stages[0].line]
    failed = []
    for i, st in enumerate(stages):
        s = st.num("stage")
        end = stages[i + 1].line if i + 1 < len(stages) else float("inf")
        rows = [e for e in children if st.line < e.line < end]
        if len(rows) != 12:
            v.reasons.append(f"stage={s}: {len(rows)} child lines, want 12")
            return v
        pairs = {(e.num("stage"), e.num("j")) for e in rows}
        if pairs != {(float(k), float(j)) for k in range(3) for j in range(4)}:   # every child once (Codex, #431)
            v.reasons.append(f"stage={s}: the child lines do not name each of the 12 children once")
            return v
        for e in rows:
            k, dis, pdis = e.num("stage"), e.flag("disabled"), e.flag("parent_disabled")
            if dis is None or pdis is None:
                v.reasons.append(f"stage={s}: child line without disabled/parent_disabled")
                return v
            j = e.num("j")
            if k is None or j is None or _local(e, "id") != LOCAL["p8_child0"] + 4 * int(k) + int(j):
                v.reasons.append(f"stage={s}: child k={k} j={j} id={e.fields.get('id')} is not FOCC_P8_Child_<k>_<j>")
                return v
            if dis != pdis:
                failed.append(f"stage={s} child k={k} j={e.num('j')}: disabled={dis} but parent_disabled={pdis}")
            elif dis != (k != s):
                failed.append(f"stage={s} child k={k} j={e.num('j')}: disabled={dis}, expected {k != s}")
    if failed:
        v.reasons.append("enable parents not honoured: " + "; ".join(failed[:6]))
        v.verdict = FAIL
        return v
    v.reasons.append("all 36 child lines follow their parent's state across the three stage swaps")
    if c.saves is None:
        v.reasons.append("saves.json missing")
        return v
    v.verdict = _growth(v, save_sizes(c.saves), "focc_p8_before", "focc_p8_after")
    return v


# ----------------------------------------------------------------------------------------------- P9

def check_p9(c: Collection) -> Verdict:
    v = Verdict("p9", INCONCLUSIVE)
    v.extra["settles"] = "long-route pathing on the converted navmesh over >= 4 exterior cells (P9)"
    P = PLACEHOLDERS
    v.extra["placeholders"] = {k: P[k] for k in P if k.startswith("p9_")}
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    starts = _by_kind(evs, "p9 start")
    if not starts:                              # no attempt boundary, no verdict (Codex review of #431)
        v.reasons.append("no `p9 start` line: the samples cannot be tied to one walk to the destination")
        return v
    # judge only the latest attempt: a retry in one launch drops the old one
    dest = [e for e in _by_kind(evs, "p9 dest") if e.line < starts[-1].line][-1:]   # P9Dest runs before P9Track
    evs = [e for e in evs if e.line >= starts[-1].line]
    done = _by_kind(evs, "p9 done")[:1]         # the tracker's own done closes it: later samples never count
    samples = [e for e in _by_kind(evs, "p9 sample") if not done or e.line < done[0].line]
    v.cite(*dest, *done)
    if not dest:
        v.reasons.append("no `p9 dest` line")
        return v
    if _local(dest[-1], "id") != LOCAL["p9_dest"]:  # the probe's own destination (Codex review of #431)
        v.reasons.append(f"p9 dest id {dest[-1].fields.get('id')} is not FOCC_P9_Dest (local {LOCAL['p9_dest']})")
        return v
    actor = starts[-1].form("actor")
    if actor is None:
        v.reasons.append("p9 start names no actor")
        return v
    others = [e for e in samples if e.form("actor") != actor]
    if others:                                  # every sample is the started actor's (Codex review of #431)
        v.cite(*others[:3])
        v.reasons.append(f"{len(others)} p9 sample line(s) name another actor than the start's "
                         f"{starts[-1].fields.get('actor')}")
        return v
    if starts[-1].rt is None or any(e.rt is None for e in samples):
        v.reasons.append("a p9 start or sample line carries no rt=: the walk's real time is unknown")
        return v
    rows = []
    for e in samples:
        # real seconds since the start, not the script's nominal t: late timers must not shorten the walk
        # (Codex review of #431)
        t = e.rt - starts[-1].rt
        d, p, cell, loaded = e.num("dist"), pos(e), e.form("cell"), e.flag("loaded")
        if None in (t, d, p):
            continue
        rows.append((t, d, p, cell, loaded, e))
    if len(rows) < 2:
        v.reasons.append("fewer than 2 parsable `p9 sample` lines")
        return v
    v.cite(rows[0][5], rows[-1][5])
    if not done:
        v.reasons.append("no `p9 done` line: the tracker did not finish")
        return v
    start = rows[0][1]
    v.extra["start_dist_m"] = start
    if start < P["p9_start_m"]:
        v.reasons.append(f"start dist {start} m < {P['p9_start_m']} (the card asked for 450)")
        return v
    loaded_share = sum(1 for r in rows if r[4] is True) / len(rows)
    v.extra["loaded_share"] = round(loaded_share, 3)
    if loaded_share < 0.5:
        v.reasons.append(f"loaded=True in only {loaded_share:.0%} of samples: the actor unloaded (setup problem)")
        return v
    # Continuity: a jump faster than a walk between two samples is a teleport, never a pass for pathing.
    for (t0, _, p0, _, _, e0), (t1, _, p1, _, _, e1) in zip(rows, rows[1:]):
        dt = t1 - t0
        if dt <= 0:                             # repeated or backward time cannot show a walk (Codex review of #431)
            v.cite(e0, e1)
            v.reasons.append(f"p9 sample real times are not strictly increasing ({t0} then {t1} s after the start)")
            return v
        step = sum((a - b) ** 2 for a, b in zip(p0, p1)) ** 0.5
        if step / dt > P["p9_jump_m_per_s"]:
            v.cite(e0, e1)
            v.reasons.append(f"a {step:.1f} m jump in {dt:.1f} s between samples: teleport-like, not a continuous "
                             f"walk (placeholder {P['p9_jump_m_per_s']} m/s)")
            return v
    cells = {r[3] for r in rows if r[3]}
    v.extra["distinct_cells"] = len(cells)
    first_cell = rows[0][3]
    arrived = [r for r in rows if r[1] < P["p9_arrive_m"] and r[0] <= P["p9_seconds"]]
    if len(cells) <= 1 and rows[-1][0] >= P["p9_seconds"]:
        v.reasons.append(f"the actor never left its first cell {first_cell} within {P['p9_seconds']} s")
        v.verdict = FAIL
        return v
    # Stuck: dist within 2 m of a value for 120 s while loaded.
    anchor = rows[0]
    for r in rows:
        if abs(r[1] - anchor[1]) > P["p9_stuck_m"] or r[4] is not True:
            anchor = r
        elif r[0] - anchor[0] >= P["p9_stuck_s"]:
            v.cite(anchor[5], r[5])
            v.reasons.append(f"dist stayed within {P['p9_stuck_m']} m of {anchor[1]:.1f} for {r[0] - anchor[0]:.0f} s "
                             f"while loaded: stuck")
            v.verdict = FAIL
            return v
    if not arrived:
        v.reasons.append(f"dist never fell below {P['p9_arrive_m']} m within {P['p9_seconds']} s (last {rows[-1][1]} m)")
        return v
    if len(cells) < P["p9_min_cells"]:
        v.reasons.append(f"only {len(cells)} distinct cells among the samples, want {P['p9_min_cells']}")
        return v
    v.cite(arrived[0][5])
    v.extra["arrived_at_s"] = arrived[0][0]
    v.reasons.append(f"walked from {start:.0f} m to under {P['p9_arrive_m']} m in {arrived[0][0]:.0f} s through "
                     f"{len(cells)} cells with no jump")
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P10

def sendstoryevent_compiles(files: dict, plan: dict | None):
    """True when the staged FOCC_Probe.psc calls SendStoryEvent and the stage's receipts say FOCC_Probe compiled;
    False when the receipts show the compile failed; None when either file is missing."""
    psc = files.get("FOCC_Probe.psc")
    if psc is None or "SendStoryEvent" not in psc:
        return None
    if plan:
        comp = plan.get("compiled")
        if isinstance(comp, dict) and "FOCC_Probe" in comp:
            return bool(comp["FOCC_Probe"])
        outs = plan.get("sha256") or plan.get("outputs") or {}
        if isinstance(outs, dict) and any(k.replace("\\", "/").endswith("Scripts/FOCC_Probe.pex") for k in outs):
            return True
    oc = files.get("offline_check.txt")
    if oc is None:
        return None
    for block in re.split(r"\n(?=\S)", oc):
        if "FOCC_Probe.psc" in block or "FOCC_Probe " in block:
            if "Compilation succeeded" in block:
                return True
            if "failed" in block.lower() or "error" in block.lower():
                return False
    return None


def check_p10(c: Collection) -> Verdict:
    v = Verdict("p10", INCONCLUSIVE)
    v.extra["settles"] = "event plumbing: Keyword.SendStoryEvent compiles; our SM branch starts our quest (P10)"
    v.extra["sendstoryevent_compiles"] = sendstoryevent_compiles(c.files, c.plan)
    if _skipped(c.plan, "sm", "sm_nodes_written"):
        v.reasons.append("the stage says the SMBN/SMQN nodes were not written: only the compile verdict is given")
        v.extra["blocked"] = True
        return v
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    sent = _by_kind(evs, "p10 sent")
    started = _by_kind(evs, "p10 quest started")
    state = _by_kind(evs, "p10 state")
    v.cite(*sent, *started, *state)
    if not sent:
        v.reasons.append("no `p10 sent` line")
        return v
    s = sent[-1]
    if _local(s, "event") != LOCAL["p10_event"]:   # the probe's own keyword was sent (Codex review of #431)
        v.reasons.append(f"p10 sent event={s.fields.get('event')} is not FOCC_P10_Event (local {LOCAL['p10_event']})")
        return v
    if s.flag("result") is False:           # older stages logged a bool result; Starfield's is not a bool (2d53642)
        v.reasons.append("SendStoryEvent returned False")
        v.verdict = FAIL
        return v
    # Only lines whose logged id is FOCC_P10_Quest count: local=2080 is a literal the scripts print (Codex, #431).
    after = [e for e in started if e.line > s.line and _local(e, "id") == LOCAL["p10_quest"]]
    state = [e for e in state if _local(e, "id") == LOCAL["p10_quest"]]
    running = state[-1].flag("running") if state and state[-1].line > s.line else None
    if after:
        e = after[0]
        # IsRunning counts only when read after that OnQuestInit; an earlier read says nothing (Codex review of #431).
        running = state[-1].flag("running") if state and state[-1].line > e.line else None
        if s.rt is not None and e.rt is not None and e.rt - s.rt > PLACEHOLDERS["p10_start_window_s"]:
            v.reasons.append(f"the quest started {e.rt - s.rt:.1f} s after the send, outside the placeholder "
                             f"{PLACEHOLDERS['p10_start_window_s']} s window")
            return v
        if running is False:
            v.reasons.append("OnQuestInit fired but IsRunning read False afterwards")
            v.verdict = FAIL
            return v
        if running is None:
            v.reasons.append("SendStoryEvent ran and FOCC_P10_Quest's OnQuestInit fired, but there is no "
                             "`p10 state` line after the send: run cgf \"FOCC_Probe.P10State\" (the card's PASS needs "
                             "running=True)")
            return v
        v.reasons.append("SendStoryEvent ran, FOCC_P10_Quest's OnQuestInit fired and IsRunning is True")
        v.verdict = PASS
        return v
    if running is False:
        v.reasons.append("SendStoryEvent ran but the quest never started and IsRunning is False")
        v.verdict = FAIL
        return v
    v.reasons.append("SendStoryEvent ran; no `p10 quest started` line and no state line")
    return v


CHECKS = {"p1": check_p1, "p2": check_p2, "p3": check_p3, "p4": check_p4, "p5": check_p5,
          "p6": check_p6, "p7": check_p7, "p8": check_p8, "p9": check_p9, "p10": check_p10}


def check(probe: str, c: Collection) -> Verdict:
    return CHECKS[probe.lower()](c)


def _attempted(p: str, c: Collection) -> bool:
    """Whether the collection holds any input for probe `p`: one of its own log lines (kind `p<n> ...`, or P3's
    p3cells `where` lines), the SFSE log for P1, the array-cap compile output for P5. Decided from the inputs, not
    from what a checker cited, so a probe that stops before citing still counts (Codex review of #431)."""
    if p == "p1" and c.sfse_log is not None:
        return True
    if p == "p5" and c.files.get("compile_p5_array129.txt") is not None:
        return True
    for evs in c.any_logs():
        cells = any(e.kind == "init" and e.fields.get("variant", "").lower() == "p3cells" for e in evs)
        if any(e.kind.split()[:1] == [p] or (p == "p3" and cells and e.kind == "where") for e in evs):
            return True
    return False


def check_all(c: Collection) -> dict:
    """Every probe; the summary verdict is the worst among probes that saw any input (an untouched probe is listed as
    INCONCLUSIVE but does not drag `all` down on its own)."""
    out, touched = {}, []
    for p in PROBES:
        v = check(p, c)
        out[p] = v.to_dict()
        if v.evidence or _attempted(p, c):
            touched.append(v.verdict)
    return {"probes": out, "verdict": _worst(*touched) if touched else INCONCLUSIVE,
            "note": "verdict is the worst of the probes with any evidence; the others had no input"}


# ----------------------------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fo4sf.combined.probes",
                                 description="judge a combined-core probe from its collected text; exit 0 PASS, "
                                             "1 FAIL, 2 INCONCLUSIVE")
    ap.add_argument("check", help="p1..p10, all, hex2dec, dec2hex")
    ap.add_argument("path", nargs="?", help="collection folder or a single log file (or the id to convert)")
    ap.add_argument("--collect", help="collection folder (same as the positional path)")
    a = ap.parse_args(argv)
    cid = a.check.lower()
    if cid in ("hex2dec", "dec2hex"):
        if a.path is None:
            ap.error(f"{cid} needs a value")
        try:
            print(hex2dec(a.path) if cid == "hex2dec" else dec2hex(a.path))
        except ValueError:
            ap.error(f"not a form id: {a.path!r}")
        return 0
    if cid not in CHECKS and cid != "all":
        ap.error(f"unknown check {a.check!r}; want one of {', '.join(PROBES)} or all")
    path = a.collect or a.path
    if not path:
        ap.error("a collection folder or log file is needed")
    try:
        c = collect(path)
    except FileNotFoundError:
        print(json.dumps({"probe": cid, "verdict": INCONCLUSIVE, "reasons": [f"{path}: not found"], "evidence": []},
                         indent=1, sort_keys=True))
        return 2
    result = check_all(c) if cid == "all" else check(cid, c).to_dict()
    print(json.dumps(result, indent=1, sort_keys=True))
    return _RANK[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
