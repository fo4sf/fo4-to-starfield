"""Parse and validate FO4SFHardcore.0.log lines produced by FO4SF_HardcoreQuest.psc."""
from __future__ import annotations

import re
from typing import Iterable

LINE_RE = re.compile(r"FO4SFHC\s+rt=(?P<rt>[0-9.eE+-]+)\s+(?P<kind>\w+)\s+(?P<body>.*?)\s+end=true")
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
    syncs = [e for e in events if e["kind"] == "sync"]
    stimpaks = [e for e in events if e["kind"] == "stimpak"]
    stages = [int(e["kv"]["id"]) for e in events if e["kind"] == "stage" and e["kv"].get("id", "").isdigit()]
    summaries = [e for e in events if e["kind"] == "summary"]

    sq_env_ever_started = any(e["kv"].get("sq_env_running", "").lower() == "true" for e in events if "sq_env_running" in e["kv"])

    on_sync = next((e["kv"] for e in syncs if e["kv"].get("reason") == "stage10_on"), None)
    relief_sync = next((e["kv"] for e in syncs if e["kv"].get("reason") == "stage20_relief"), None)
    off_sync = next((e["kv"] for e in syncs if e["kv"].get("reason") == "stage30_off"), None)

    hot_stimpak = next((e["kv"] for e in stimpaks if e["kv"].get("mode") == "hot"), None)
    instant_stimpak = next((e["kv"] for e in stimpaks if e["kv"].get("mode") == "instant"), None)

    checks = {
        "has_events": len(events) > 0,
        "sq_env_never_conflicted": not sq_env_ever_started,
        "stage10_meters_and_ammo_on": bool(
            on_sync
            and on_sync.get("hardcore") == "1"
            and int(on_sync.get("hs", "0")) == 2
            and int(on_sync.get("ts", "0")) == 3
            and int(on_sync.get("ss", "0")) == 1
            and float(on_sync.get("ammo_burden", "0")) >= 4.99
            and float(on_sync.get("carry_mod", "0")) <= -4.99
            and float(on_sync.get("end_mod", "0")) <= -5.0
        ),
        "stage20_relief_reduced_meters": bool(
            relief_sync
            and float(relief_sync.get("h", "999")) <= 200.01
            and float(relief_sync.get("t", "999")) <= 400.01
            and float(relief_sync.get("s", "999")) <= 0.01
        ),
        "stage30_off_reverted_cleanly": bool(
            off_sync
            and off_sync.get("hardcore") == "0"
            and int(off_sync.get("hs", "-1")) == 0
            and int(off_sync.get("ts", "-1")) == 0
            and int(off_sync.get("ss", "-1")) == 0
            and abs(float(off_sync.get("ammo_burden", "1"))) < 0.001
            and abs(float(off_sync.get("carry_mod", "1"))) < 0.001
            and abs(float(off_sync.get("end_mod", "1"))) < 0.001
            and abs(float(off_sync.get("str_mod", "1"))) < 0.001
            and abs(float(off_sync.get("agi_mod", "1"))) < 0.001
            and abs(float(off_sync.get("int_mod", "1"))) < 0.001
        ),
        "stimpak_hot_when_on": bool(hot_stimpak and int(hot_stimpak.get("ticks_remaining", "0")) == 5),
        "stimpak_instant_when_off": bool(instant_stimpak and int(instant_stimpak.get("ticks_remaining", "-1")) == 0),
        "all_stages_completed": stages == [10, 20, 30, 40, 50] and bool(summaries and summaries[-1]["kv"].get("ok", "").lower() == "true"),
    }

    passed = all(checks.values())
    return {
        "passed": passed,
        "event_count": len(events),
        "stages": stages,
        "checks": checks,
    }


def report(summary: dict) -> list[str]:
    lines = [f"FO4SFHardcore log: events={summary['event_count']} stages={summary['stages']}"]
    for name, ok in summary["checks"].items():
        lines.append(f"  {'PASS' if ok else 'FAIL'}  {name}")
    lines.append("verdict: PASS" if summary["passed"] else "verdict: FAIL")
    return lines
