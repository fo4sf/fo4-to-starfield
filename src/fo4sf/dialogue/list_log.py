"""Parse and validate FO4SFListDialogue.0.log lines produced by FO4SF_ListDialogueQuest.psc."""
from __future__ import annotations

import re
from typing import Iterable

LINE_RE = re.compile(r"FO4SFLIST\s+rt=(?P<rt>[0-9.eE+-]+)\s+(?P<kind>\w+)\s+(?P<body>.*?)\s+end=true")
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
    evals = [e["kv"] for e in events if e["kind"] == "eval"]
    choices = [e["kv"] for e in events if e["kind"] == "choice_stage"]
    summaries = [e["kv"] for e in events if e["kind"] == "summary"]

    low_eval = next((kv for kv in evals if kv.get("phase") == "baseline_low"), None)
    high_eval = next((kv for kv in evals if kv.get("phase") == "qualified_high"), None)
    reset_eval = next((kv for kv in evals if kv.get("phase") == "reset"), None)

    checks = {
        "has_events": len(events) > 0,
        "baseline_low_deterministic_fails": bool(
            low_eval
            and low_eval.get("speech50") == "fail"
            and low_eval.get("science40") == "fail"
            and low_eval.get("strength7") == "fail"
            and low_eval.get("bg_vaultdweller") == "locked"
            and low_eval.get("trait_goodnatured") == "locked"
        ),
        "qualified_high_deterministic_passes": bool(
            high_eval
            and high_eval.get("speech50") == "pass"
            and high_eval.get("science40") == "pass"
            and high_eval.get("strength7") == "pass"
            and high_eval.get("bg_vaultdweller") == "pass"
            and high_eval.get("trait_goodnatured") == "pass"
        ),
        "reset_restored_sheet": bool(
            reset_eval
            and reset_eval.get("bg_vaultdweller") == "locked"
            and reset_eval.get("trait_goodnatured") == "locked"
        ),
        "summary_ok": bool(summaries and summaries[-1].get("ok", "").lower() == "true"),
    }

    return {
        "passed": all(checks.values()),
        "event_count": len(events),
        "choice_stages": [int(c["stage"]) for c in choices if c.get("stage", "").isdigit()],
        "checks": checks,
    }


def report(summary: dict) -> list[str]:
    lines = [f"FO4SFListDialogue log: events={summary['event_count']} choice_stages={summary['choice_stages']}"]
    for name, ok in summary["checks"].items():
        lines.append(f"  {'PASS' if ok else 'FAIL'}  {name}")
    lines.append("verdict: PASS" if summary["passed"] else "verdict: FAIL")
    return lines
