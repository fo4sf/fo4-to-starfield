"""Log parser and multi-session (.1.log + .0.log) stitcher for FO4SFReputation.esm runs."""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

PREFIX = "FO4SF_REPUTATION"
HEADER_RE = re.compile(
    r"FO4SF_REPUTATION\s+rt=(?P<rt>[-+0-9.eE]+)\s+(?P<event>[A-Za-z0-9_]+)(?P<rest>.*)$",
    re.IGNORECASE,
)
KV_RE = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")

KNOWN_EVENTS = {
    "init",
    "orthogonality_proof",
    "quest_hook",
    "kill_hook",
    "theft_hook",
    "token_hook",
    "karma_shift",
    "status_dump",
    "reload_audit",
}


def resolve_log_chain(primary_log: str, prev_log: Optional[str] = None) -> List[str]:
    """Return ordered log paths `[older_pre_quit_log, current_post_reload_log]` when applicable."""
    p0 = Path(primary_log)
    if prev_log:
        return [str(Path(prev_log)), str(p0)]
    if p0.name.lower().endswith(".0.log"):
        stem = p0.name[:-6]
        sibling_1 = p0.with_name(stem + ".1.log")
        if sibling_1.is_file() and p0.is_file():
            if sibling_1.stat().st_mtime <= p0.stat().st_mtime + 1.0:
                return [str(sibling_1), str(p0)]
    return [str(p0)]


def parse_single_log(text: str, session_index: int = 0, source_name: str = "") -> Tuple[List[Dict[str, object]], int]:
    """Parse all complete FO4SF_REPUTATION lines in one log text; count cut lines lacking end=true."""
    records: List[Dict[str, object]] = []
    truncated = 0
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if PREFIX.lower() not in raw_line.lower():
            continue
        stripped = raw_line.strip()
        if not re.search(r"\bend=true\s*$", stripped, re.IGNORECASE):
            truncated += 1
            continue
        m = HEADER_RE.search(stripped)
        if not m:
            truncated += 1
            continue
        ev = m.group("event").lower()
        fields: Dict[str, str] = {}
        for k, v in KV_RE.findall(m.group("rest")):
            fields[k.lower()] = v
        fields.pop("end", None)
        rec: Dict[str, object] = {
            "session": session_index,
            "source": source_name,
            "line": line_no,
            "rt": float(m.group("rt")),
            "event": ev,
            "known_event": ev in KNOWN_EVENTS,
            "fields": fields,
        }
        records.append(rec)
    return records, truncated


def scan_papyrus_errors(papyrus_text: str) -> List[str]:
    """Return lines in Papyrus.0.log reporting errors or stack faults on FO4SF_ReputationQuest."""
    hits: List[str] = []
    for raw in papyrus_text.splitlines():
        low = raw.lower()
        if "fo4sf_reputationquest" in low and ("error:" in low or "cannot " in low or "warning:" in low):
            hits.append(raw.strip())
    return hits


def stitch_and_evaluate_logs(
    log_paths: Sequence[str],
    papyrus_log_path: Optional[str] = None,
    require_hooks: bool = False,
) -> Dict[str, object]:
    """Stitch ordered log files (.1.log then .0.log) and evaluate orthogonality, hooks, and save/reload parity."""
    all_records: List[Dict[str, object]] = []
    total_truncated = 0
    used_paths: List[str] = []

    for idx, p_str in enumerate(log_paths):
        p = Path(p_str)
        if not p.is_file():
            raise FileNotFoundError(f"missing reputation log file: {p}")
        txt = p.read_text(encoding="utf-8", errors="replace")
        recs, trunc = parse_single_log(txt, session_index=idx, source_name=p.name)
        all_records.extend(recs)
        total_truncated += trunc
        used_paths.append(str(p))

    papyrus_errors: List[str] = []
    if papyrus_log_path:
        pp = Path(papyrus_log_path)
        if not pp.is_file():
            raise FileNotFoundError(f"missing Papyrus log file: {pp}")
        papyrus_errors = scan_papyrus_errors(pp.read_text(encoding="utf-8", errors="replace"))

    reasons: List[str] = []
    hard_fail = False

    if total_truncated > 0:
        hard_fail = True
        reasons.append(f"{total_truncated} truncated FO4SF_REPUTATION line(s) missing end=true")
    if papyrus_errors:
        hard_fail = True
        reasons.append(f"{len(papyrus_errors)} Papyrus error/warning line(s) mentioning FO4SF_ReputationQuest")

    # 1. Orthogonality check: Very Evil (karma <= -750, tier == -2) while Idolized (state 12, reaction 2, buy_mult ~0.75)
    orthogonality_ok = False
    for r in all_records:
        f = r["fields"]
        assert isinstance(f, dict)
        try:
            karma_v = float(f["karma"]) if "karma" in f else 0.0
            tier_v = int(float(f["tier"])) if "tier" in f else 0
            bm_v = float(f["buy_mult"]) if "buy_mult" in f else 1.0
        except ValueError:
            continue
        if r["event"] == "orthogonality_proof":
            st_v = f.get("state", "12")
            if f.get("ok", "").lower() == "true" and st_v == "12" and karma_v <= -750.0 and tier_v == -2 and 0.74 < bm_v < 0.76:
                orthogonality_ok = True
            else:
                hard_fail = True
                reasons.append("orthogonality_proof logged ok=false or out-of-spec values")
        else:
            states_csv = f.get("states", "")
            first_state = states_csv.split(",")[0] if states_csv else ""
            react0 = f.get("fac0_react", f.get("reaction", ""))
            if karma_v <= -750.0 and tier_v == -2 and first_state == "12" and react0 == "2" and 0.74 < bm_v < 0.76:
                orthogonality_ok = True

    if not orthogonality_ok:
        reasons.append("missing Evil+Idolized orthogonality proof (karma <= -750, state=12, reaction=2, buy_mult=0.75)")

    # 2. Optional strict hooks check (quest_hook, kill_hook combat Karma decoupling, theft_hook)
    seen_events = {str(r["event"]) for r in all_records}
    hooks_seen = sorted(seen_events & {"quest_hook", "kill_hook", "theft_hook", "token_hook"})
    if require_hooks:
        for req_ev in ("quest_hook", "kill_hook", "theft_hook"):
            if req_ev not in seen_events:
                reasons.append(f"missing required hook event: {req_ev}")

    # Verify non-innocent kill_hook never changes Karma relative to immediately preceding state-bearing record
    prev_karma: Optional[int] = None
    for r in all_records:
        f = r["fields"]
        assert isinstance(f, dict)
        cur_k = int(float(f["karma"])) if "karma" in f else None
        if r["event"] == "kill_hook" and f.get("innocent", "").lower() == "false":
            if prev_karma is not None and cur_k is not None and cur_k != prev_karma:
                hard_fail = True
                reasons.append(f"non-innocent kill_hook unexpectedly changed karma ({prev_karma} -> {cur_k})")
        if cur_k is not None:
            prev_karma = cur_k

    # 3. Save & reload parity check across reload_audit
    reload_indices = [i for i, r in enumerate(all_records) if r["event"] == "reload_audit"]
    reload_ok = False
    pre_reload_snapshot: Optional[Dict[str, str]] = None
    post_reload_snapshot: Optional[Dict[str, str]] = None

    if not reload_indices:
        reasons.append("missing reload_audit event (save, quit, and reload required)")
    else:
        r_idx = reload_indices[-1]
        reload_rec = all_records[r_idx]
        rf = reload_rec["fields"]
        assert isinstance(rf, dict)
        post_reload_snapshot = {
            "karma": rf.get("karma", ""),
            "tier": rf.get("tier", ""),
            "states": rf.get("states", ""),
            "buy_mult": rf.get("buy_mult", ""),
            "ok": rf.get("ok", ""),
        }
        if rf.get("ok", "").lower() != "true":
            hard_fail = True
            reasons.append("reload_audit reported ok=false (ActorValue/Global drift on reload)")
        else:
            # Find last state-bearing pre-reload event before reload_audit
            for j in range(r_idx - 1, -1, -1):
                pf = all_records[j]["fields"]
                assert isinstance(pf, dict)
                if "karma" in pf and "states" in pf:
                    pre_reload_snapshot = {
                        "event": str(all_records[j]["event"]),
                        "karma": pf.get("karma", ""),
                        "tier": pf.get("tier", ""),
                        "states": pf.get("states", ""),
                        "buy_mult": pf.get("buy_mult", ""),
                    }
                    break
            if pre_reload_snapshot is None:
                reasons.append("no pre-reload event found before reload_audit (pass --prev-file or keep .1.log)")
            else:
                k_match = pre_reload_snapshot["karma"] == post_reload_snapshot["karma"]
                s_match = pre_reload_snapshot["states"] == post_reload_snapshot["states"]
                if not (k_match and s_match):
                    hard_fail = True
                    reasons.append(
                        f"save/reload state mismatch: pre=({pre_reload_snapshot['karma']}, {pre_reload_snapshot['states']}) "
                        f"vs post=({post_reload_snapshot['karma']}, {post_reload_snapshot['states']})"
                    )
                else:
                    reload_ok = True

    if hard_fail:
        verdict = "FAIL"
    elif orthogonality_ok and reload_ok and not reasons:
        verdict = "PASS"
    else:
        verdict = "INCONCLUSIVE"

    return {
        "verdict": verdict,
        "files": used_paths,
        "record_count": len(all_records),
        "truncated": total_truncated,
        "papyrus_errors": papyrus_errors,
        "orthogonality_ok": orthogonality_ok,
        "hooks_seen": hooks_seen,
        "reload_ok": reload_ok,
        "pre_reload": pre_reload_snapshot,
        "post_reload": post_reload_snapshot,
        "reasons": reasons,
        "records": all_records,
    }


def format_log_summary(report: Dict[str, object]) -> str:
    lines = [
        f"verdict: {report['verdict']}",
        f"files: {', '.join(os.path.basename(str(p)) for p in report['files'])}",
        f"events: {report['record_count']} complete, {report['truncated']} truncated",
        f"orthogonality_ok: {report['orthogonality_ok']}",
        f"hooks_seen: {', '.join(report['hooks_seen']) if report['hooks_seen'] else 'none'}",
        f"reload_ok: {report['reload_ok']}",
    ]
    if report.get("pre_reload") and report.get("post_reload"):
        pre = report["pre_reload"]
        post = report["post_reload"]
        assert isinstance(pre, dict) and isinstance(post, dict)
        lines.append(
            f"reload_parity: karma {pre['karma']} -> {post['karma']}, states [{pre['states']}] -> [{post['states']}]"
        )
    for r in report.get("reasons", []):
        lines.append(f"note: {r}")
    return "\n".join(lines)
