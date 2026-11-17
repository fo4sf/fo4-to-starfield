"""Structured user-log parser, rule evaluator, and verdict report for FO4SFRadsCore.0.log (docs/rads/rads-core.md).

Every line written by scripts/rads/FO4SF_RadsCoreQuest.psc has the shape:
  FO4SFRADSCORE rt=<real time s> <event> key=value ... end=true
Lines lacking end=true were truncated and are counted separately as cut lines.

Also exposes pure Python reference functions for Mode A (Max-HP cap), Mode B (Rad-Sickness stat thresholds),
sickness stage classification, and Rad-X resistance scaling, held equal against FO4SF_RadsCoreQuest.psc by
tests/test_rads_core.py.
"""
import re

LINE = re.compile(r"FO4SFRADSCORE rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
SAY_TEXT = re.compile(r" text=(?P<text>.*) end=true\s*$", re.IGNORECASE)

EVENTS = (
    "init", "start", "control", "set", "gain", "radaway", "radx",
    "mutation", "sync", "mode_switch", "stage_done", "fatal", "say", "verdict",
)
ID_KEYS = {
    "quest", "rads_av", "cap_pct_av", "rad_resist_av", "rule_glob", "mut_glob",
    "hazard", "emitter", "water", "radaway", "radx", "food", "dirty_water",
    "mut_flst", "starched", "av", "perk", "cured_perk",
}
STAGES = (10, 20, 30, 40, 50, 60)
ALL_STAGES = (5, 10, 20, 30, 40, 50, 60)
STAGE_NAMES = {
    0: "None",
    1: "Minor",
    2: "Advanced",
    3: "Critical",
    4: "Deadly",
    5: "Fatal",
}
RADS_MAX = 1000.0
RADAWAY_CURE = 300.0
RADX_BUFF = 100.0
CONTROL_DELTA = 10.0
WRITE_TEST = 50.0
EPS = 0.05


def clamp_rads(v):
    return max(0.0, min(RADS_MAX, float(v)))


def sickness_stage(rads):
    """0 (<200), 1 (200..399), 2 (400..599), 3 (600..799), 4 (800..999), 5 (>=1000)."""
    r = float(rads)
    if r >= 1000.0:
        return 5
    if r >= 800.0:
        return 4
    if r >= 600.0:
        return 3
    if r >= 400.0:
        return 2
    if r >= 200.0:
        return 1
    return 0


def scale_by_resist(raw_amount, resist):
    """Incoming rads scaled by FO4SF_RadResist: raw * (100 / (100 + max(0, resist)))."""
    r = max(0.0, float(resist))
    return float(raw_amount) * (100.0 / (100.0 + r))


def mode_a_health_delta(rads, base_hp):
    """Mode A (rule 0): -10% of base_hp per 100 rads, clamped so effective max HP >= 10% below 1000 rads."""
    r = clamp_rads(rads)
    b = max(10.0, float(base_hp))
    frac = min(0.90, r / 1000.0)
    pen = int(frac * b + 0.001)
    if (b - pen) < (b * 0.10):
        pen = int(b * 0.90)
    return float(-pen)


def mode_b_stat_deltas(rads):
    """Mode B (rule 1): (end_delta, agi_delta, str_delta) for sickness stage."""
    st = sickness_stage(rads)
    if st == 1:
        return (-1.0, 0.0, 0.0)
    if st == 2:
        return (-2.0, -1.0, 0.0)
    if st == 3:
        return (-3.0, -2.0, -1.0)
    if st >= 4:
        return (-3.0, -2.0, -2.0)
    return (0.0, 0.0, 0.0)


def target_deltas(rads, rule, base_hp):
    """(hp_delta, end_delta, agi_delta, str_delta) for rule 0 (Mode A) or rule 1 (Mode B)."""
    if int(rule) == 0:
        return (mode_a_health_delta(rads, base_hp), 0.0, 0.0, 0.0)
    e, a, s = mode_b_stat_deltas(rads)
    return (0.0, e, a, s)


def u32(v):
    return None if v is None else int(v) & 0xFFFFFFFF


def _parse_val(key, text):
    low = text.lower()
    if low == "none":
        return None
    if low == "na":
        return "na"
    if low in ("true", "false"):
        return low == "true"
    if key in ID_KEYS:
        try:
            return u32(int(text))
        except ValueError:
            return text
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def parse_line(line):
    """Parsed dict for one FO4SFRADSCORE line, or None for unrelated lines."""
    m = LINE.search(line)
    if not m:
        return None
    ev = m.group("event").lower()
    if ev not in EVENTS:
        return None
    try:
        rt = float(m.group("rt"))
    except ValueError:
        return None
    rest = m.group("rest")
    out = {"rt": rt, "event": ev}
    if ev == "say":
        sm = SAY_TEXT.search(rest)
        if sm:
            out["text"] = sm.group("text")
            out["end"] = True
            return out
    for k, v in TOKEN.findall(rest):
        k = k.lower()
        out[k] = _parse_val(k, v)
    out["end"] = out.get("end") is True
    return out


def runs(lines):
    """([[parsed event]], cut_count) split on each init line carrying a version."""
    out, cur, cut = [], [], 0
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        if not p["end"]:
            cut += 1
            continue
        if p["event"] == "init" and cur and p.get("version") is not None:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out, cut


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt(v):
    if v is None:
        return "none"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def control_check(ctl):
    if ctl is None:
        return False, "no control line: stage 10 never ran"
    if ctl.get("called") is not True:
        return False, "Actor.ModValue control call was not made"
    b, a, r = ctl.get("before"), ctl.get("after"), ctl.get("restored")
    if not (num(b) and num(a) and num(r)):
        return False, f"control readings are not numeric ({fmt(b)}, {fmt(a)}, {fmt(r)})"
    d = ctl.get("delta", CONTROL_DELTA)
    if abs((a - b) - d) > EPS:
        return False, f"Health moved {fmt(b)} to {fmt(a)}, expected +{fmt(d)}"
    if abs(r - b) > EPS:
        return False, f"Health restored to {fmt(r)}, expected {fmt(b)}"
    return True, f"Health {fmt(b)} -> {fmt(a)} -> {fmt(r)} (ModValue +10/-10)"


def summarize(lines, run=-1):
    """Summarize the selected run (default latest) into structured status + PASS/INCONCLUSIVE/FAIL verdict."""
    rs, cut = runs(lines)
    out = {
        "runs": len(rs),
        "run": 0,
        "cut": cut,
        "init": None,
        "start": None,
        "control": (False, "no log"),
        "stages": {},
        "syncs": [],
        "gains": [],
        "radaways": [],
        "mutations": [],
        "mode_switches": [],
        "fatals": [],
        "problems": [],
        "passed": False,
        "verdict": "INCONCLUSIVE: no log lines",
    }
    if not rs:
        return out

    r = rs[run]
    out["run"] = run if run >= 0 else len(rs) + run
    out["init"] = next((e for e in r if e["event"] == "init"), None)
    out["start"] = next((e for e in r if e["event"] == "start"), None)
    out["syncs"] = [e for e in r if e["event"] == "sync"]
    out["gains"] = [e for e in r if e["event"] == "gain"]
    out["radaways"] = [e for e in r if e["event"] == "radaway"]
    out["mutations"] = [e for e in r if e["event"] == "mutation"]
    out["mode_switches"] = [e for e in r if e["event"] == "mode_switch"]
    out["fatals"] = [e for e in r if e["event"] == "fatal"]

    if cut:
        out["problems"].append(f"{cut} truncated line(s) without end=true ignored")
    if len(rs) > 1:
        out["problems"].append(f"{len(rs)} runs in log; showing run {out['run']}")

    if out["start"] is None:
        out["control"] = (False, "no start line")
        out["verdict"] = "INCONCLUSIVE: no start line"
        return out

    stage_events = {int(e["stage"]): e for e in r if e["event"] == "stage_done" and num(e.get("stage"))}
    out["stages"] = stage_events

    ctl = next((e for e in r if e["event"] == "control"), None)
    if ctl is None and not stage_events:
        # Passive live-play log without stage 10: report passive summary cleanly
        out["control"] = (True, f"passive live session ({len(out['syncs'])} syncs, {len(out['gains'])} gains, {len(out['radaways'])} RadAway)")
        out["passed"] = True
        out["verdict"] = f"PASS (passive): {len(out['syncs'])} sync(s), {len(out['gains'])} gain(s), {len(out['radaways'])} RadAway use(s)"
        return out

    ok_ctl, why_ctl = control_check(ctl)
    out["control"] = (ok_ctl, why_ctl)
    if not ok_ctl:
        out["verdict"] = f"INCONCLUSIVE: control failed: {why_ctl}"
        return out

    missing = [s for s in STAGES if s not in stage_events]
    failed = [s for s in STAGES if s in stage_events and stage_events[s].get("ok") is not True]
    verdict_ev = next((e for e in reversed(r) if e["event"] == "verdict"), None)

    if missing:
        out["verdict"] = f"INCONCLUSIVE: stages missing {missing} (completed: {sorted(stage_events)})"
        return out
    if failed or (verdict_ev is not None and verdict_ev.get("pass") is not True):
        out["verdict"] = f"FAIL: stage failure in {failed}"
        return out

    drift = verdict_ev.get("drift", 0.0) if verdict_ev else 0.0
    out["passed"] = True
    out["verdict"] = (
        f"PASS: stages 10..60 verified ({why_ctl}; "
        f"sources={len(out['gains'])}, mode_switches={len(out['mode_switches'])}, "
        f"mutations={len(out['mutations'])}, radaways={len(out['radaways'])}, drift={fmt(drift)})"
    )
    return out


def table(summary):
    syncs = summary.get("syncs", [])
    if not syncs:
        return ["no sync readings"]
    rows = [["reason", "rule", "rads", "cap%", "stage", "hp", "base_hp", "end", "agi", "str", "mut_on", "muts"]]
    for s in syncs:
        rows.append([
            fmt(s.get("reason")), fmt(s.get("rule")), fmt(s.get("rads")), fmt(s.get("cap_pct")),
            fmt(s.get("stage")), fmt(s.get("hp")), fmt(s.get("base_hp")),
            fmt(s.get("end")), fmt(s.get("agi")), fmt(s.get("str")),
            fmt(s.get("mut_on")), fmt(s.get("mut_count")),
        ])
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]


def report(summary):
    lines = table(summary)
    lines.append("control: " + ("ok: " if summary["control"][0] else "FAILED: ") + summary["control"][1])
    for st in ALL_STAGES:
        if st in summary.get("stages", {}):
            e = summary["stages"][st]
            lines.append(
                f"stage {st}: ok={e.get('ok')} rads={fmt(e.get('rads'))} rule={fmt(e.get('rule'))} "
                f"cap_pct={fmt(e.get('cap_pct'))} sick_stage={fmt(e.get('sick_stage'))} mut_count={fmt(e.get('mut_count'))}"
            )
    for ms in summary.get("mode_switches", []):
        lines.append(
            f"mode_switch: {ms.get('from_rule')}->{ms.get('to_rule')} ok={ms.get('ok')} "
            f"drift=({fmt(ms.get('drift_hp'))},{fmt(ms.get('drift_end'))},{fmt(ms.get('drift_agi'))},{fmt(ms.get('drift_str'))})"
        )
    for p in summary.get("problems", []):
        lines.append("note: " + p)
    lines.append(summary["verdict"])
    return lines
