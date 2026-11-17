"""Parse and validate FO4SFProgression.0.log lines produced by FO4SF_ProgressionQuest.psc."""
from __future__ import annotations

import re
from typing import Iterable

LINE_RE = re.compile(r"FO4SFPROG\s+rt=(?P<rt>[0-9.eE+-]+)\s+(?P<kind>\w+)\s+(?P<body>.*?)\s+end=true")
KV_RE = re.compile(r"(?P<k>[A-Za-z0-9_]+)=(?P<v>\S+)")


def parse_lines(lines: Iterable[str]) -> list[dict]:
    events: list[dict] = []
    for raw in lines:
        m = LINE_RE.search(raw)
        if not m:
            continue
        kv = {km.group("k"): km.group("v") for km in KV_RE.finditer(m.group("body"))}
        events.append({"rt": float(m.group("rt")), "kind": m.group("kind"), "kv": kv})
    return events


def summarize(lines: Iterable[str]) -> dict:
    events = parse_lines(lines)
    creations = [e["kv"] for e in events if e["kind"] == "creation"]
    respecs = [e["kv"] for e in events if e["kind"] == "respec"]
    cadences = [e["kv"] for e in events if e["kind"] == "cadence"]
    repus = [e["kv"] for e in events if e["kind"] == "karma_repu"]
    summaries = [e["kv"] for e in events if e["kind"] == "summary"]

    c0 = creations[-1] if creations else None
    r0 = respecs[-1] if respecs else None
    cad0 = cadences[-1] if cadences else None
    kr0 = repus[-1] if repus else None

    checks = {
        "has_events": len(events) > 0,
        "special_40_and_13_skills_created": bool(
            c0
            and int(c0.get("special_sum", "0")) == 40
            and int(c0.get("skills_count", "0")) == 13
            and int(c0.get("speech", "0")) >= 45
        ),
        "exit_respec_once_and_locked": bool(
            r0
            and r0.get("first_ok", "").lower() == "true"
            and r0.get("second_refused", "").lower() == "true"
        ),
        "glob_perk_cadence_dynamic": bool(
            cad0
            and cad0.get("cad2_lvl2", "").lower() == "true"
            and cad0.get("cad2_lvl3", "").lower() == "false"
            and cad0.get("cad2_lvl4", "").lower() == "true"
            and cad0.get("cad1_lvl3", "").lower() == "true"
        ),
        "karma_and_repu_independent": bool(
            kr0
            and float(kr0.get("karma", "0")) <= -750.0
            and kr0.get("karma_tier") == "Very_Evil"
            and kr0.get("repu_title") == "Idolized"
            and kr0.get("disposition") == "Ally"
        ),
        "summary_ok": bool(summaries and summaries[-1].get("ok", "").lower() == "true"),
    }

    return {
        "passed": all(checks.values()),
        "event_count": len(events),
        "checks": checks,
    }


def report(summary: dict) -> list[str]:
    lines = [f"FO4SFProgression log: events={summary['event_count']}"]
    for name, ok in summary["checks"].items():
        lines.append(f"  {'PASS' if ok else 'FAIL'}  {name}")
    lines.append("verdict: PASS" if summary["passed"] else "verdict: FAIL")
    return lines
