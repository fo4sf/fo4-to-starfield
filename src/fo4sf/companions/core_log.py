"""Structured log parser, squad cap/cost/upkeep reference math, and verdict reporter for FO4SFCompanions.esm
(FO4SFCompanions.0.log, written by scripts/companions/FO4SF_CompanionsQuest.psc;
docs/research/gamma-squad-balance.md, docs/companions/companions-warfare-pc-card.md).

Log format:
  FO4SFCOMP rt=<real time s> <event> key=value ... end=true
"""
import os
import re

LINE = re.compile(r"FO4SFCOMP rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")

EVENTS = (
    "init",
    "recruited",
    "recruit_refused",
    "dismissed",
    "order",
    "fireteam_cmd",
    "inspect",
    "teleport",
    "affinity",
    "loyalty",
    "contract_payout",
    "upkeep_revive",
    "upkeep_bleedout_unassisted",
    "reload_audit",
    "stage_result",
    "stage_error",
    "cleanup",
    "say",
)

TELEPORT_CHOKEPOINTS = (
    "load_door_cell_change",
    "vault_lift_or_interior_exit",
    "pipboy_fast_travel",
)

STAGES = (10, 20, 30, 40, 50, 60)


# ---------------------------------------------------------------- reference balance math (docs/research/gamma-squad-balance.md)


def player_rank_tier(level: int, has_squad_commander: bool = False) -> int:
    """Return player leadership rank tier [0..4] matching FO4SF_CompanionsQuest.GetPlayerRankTier."""
    if has_squad_commander or level >= 30:
        return 4
    if level >= 20:
        return 3
    if level >= 12:
        return 2
    if level >= 5:
        return 1
    return 0


def effective_squad_cap(
    base_cap: int = 2,
    max_cap: int = 4,
    charisma: float = 5.0,
    has_squad_commander: bool = False,
    has_leadership_background: bool = False,
    has_solo_lone_wanderer: bool = False,
) -> int:
    """Return active squad slot cap matching FO4SF_CompanionsQuest.GetEffectiveSquadCap."""
    if has_solo_lone_wanderer:
        return 0
    if has_squad_commander or charisma >= 8.0 or has_leadership_background:
        return int(max_cap)
    return int(base_cap)


def can_recruit_gate(
    active_count: int,
    cap: int,
    candidate_rank_tier: int,
    player_tier: int,
    loyalty: float = 75.0,
    merc_contract: bool = False,
    has_goodwill: bool = False,
    player_credits: int = 0,
    merc_hire_cost: int = 250,
):
    """Evaluate the 3-gate recruitment rule; return (allowed: bool, reason: str, fee_paid: int)."""
    if active_count >= cap:
        return False, "cap_reached", 0
    if candidate_rank_tier > player_tier:
        return False, "rank_too_high", 0
    if loyalty < 20.0:
        return False, "low_loyalty", 0
    if merc_contract and not has_goodwill and merc_hire_cost > 0:
        if player_credits < merc_hire_cost:
            return False, "insufficient_credits", 0
        return True, "hired_merc", int(merc_hire_cost)
    return True, "recruited_goodwill", 0


def net_contract_payout(gross_amount: int, active_mercs: int, share_per_merc: float = 0.15) -> int:
    """Compute player net contract payout after active mercenary shares (capped at 60%)."""
    if gross_amount <= 0:
        return 0
    total_share = min(0.60, max(0.0, float(active_mercs) * float(share_per_merc)))
    merc_cut = int(float(gross_amount) * total_share)
    return gross_amount - merc_cut


def companion_nerve_pct(charisma: float, has_leadership: bool = False) -> float:
    """Compute FNV-style Companion Nerve bonus percentage [0..30]."""
    bonus = max(0.0, (float(charisma) - 5.0) * 5.0)
    if has_leadership:
        bonus += 5.0
    return min(30.0, bonus)


def affinity_tier(value: float) -> str:
    """Map affinity [0..1000] to tier label."""
    if value >= 1000.0:
        return "idolized"
    if value >= 750.0:
        return "admired"
    if value >= 500.0:
        return "trusted"
    if value >= 250.0:
        return "warm"
    return "neutral"


# ---------------------------------------------------------------- structured log parser & stitcher


def _parse_value(key, text):
    low = text.lower()
    if low == "none":
        return None
    if low in ("true", "false"):
        return low == "true"
    if key == "rt":
        return float(text)
    if "/" in text and key in ("slot", "squad_ok"):
        parts = text.split("/", 1)
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return text
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def parse_line(line):
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
    rest = m.group("rest").strip()
    if ev == "say":
        if not rest.lower().endswith("end=true"):
            return {"rt": rt, "event": ev, "end": False}
        body = rest[:-8].strip()
        if body.lower().startswith("text="):
            body = body[5:]
        return {"rt": rt, "event": ev, "text": body, "end": True}

    d = {"rt": rt, "event": ev, "end": False}
    for k, v in TOKEN.findall(rest):
        kl = k.lower()
        if kl == "end":
            d["end"] = v.lower() == "true"
        elif kl in ("reason", "cmd", "stance", "tier", "when", "source", "trigger"):
            d[kl] = v.lower()
        else:
            d[kl] = _parse_value(kl, v)
    return d


def load_session_lines(primary_path, include_rotated=True):
    """Read primary_path (FO4SFCompanions.0.log) and stitch FO4SFCompanions.1.log when post-reload events appear
    without a new `init` line in `.0.log`."""
    with open(primary_path, encoding="utf-8", errors="replace") as f:
        cur_lines = f.readlines()
    if not include_rotated:
        return cur_lines

    parsed_cur = [parse_line(ln) for ln in cur_lines]
    valid_cur = [d for d in parsed_cur if d and d.get("end")]
    has_init = any(d["event"] == "init" for d in valid_cur)
    has_reload = any(d["event"] == "reload_audit" for d in valid_cur)
    if has_init or not has_reload:
        return cur_lines

    base_dir = os.path.dirname(os.path.abspath(primary_path))
    stem = os.path.basename(primary_path)
    prev_name = stem[:-6] + ".1.log" if stem.lower().endswith(".0.log") else ""
    prev_path = os.path.join(base_dir, prev_name) if prev_name else ""
    if not prev_path or not os.path.isfile(prev_path):
        return cur_lines

    with open(prev_path, encoding="utf-8", errors="replace") as f:
        prev_lines = f.readlines()
    last_init_idx = 0
    for idx, ln in enumerate(prev_lines):
        d = parse_line(ln)
        if d and d.get("end") and d["event"] == "init":
            last_init_idx = idx
    return prev_lines[last_init_idx:] + cur_lines


def runs(lines):
    all_runs = []
    cur = []
    cut = 0
    for ln in lines:
        d = parse_line(ln)
        if d is None:
            continue
        if not d.get("end"):
            cut += 1
            continue
        if d["event"] == "init" and cur:
            all_runs.append(cur)
            cur = [d]
        else:
            cur.append(d)
    if cur:
        all_runs.append(cur)
    return all_runs, cut


def summarize(lines):
    all_runs, cut = runs(lines)
    events = all_runs[-1] if all_runs else []

    inits = [e for e in events if e["event"] == "init"]
    recruits = [e for e in events if e["event"] == "recruited"]
    refusals = [e for e in events if e["event"] == "recruit_refused"]
    dismissals = [e for e in events if e["event"] == "dismissed"]
    fireteam_cmds = [e for e in events if e["event"] == "fireteam_cmd"]
    teleports = [e for e in events if e["event"] == "teleport"]
    affinities = [e for e in events if e["event"] == "affinity"]
    loyalties = [e for e in events if e["event"] == "loyalty"]
    payouts = [e for e in events if e["event"] == "contract_payout"]
    reloads = [e for e in events if e["event"] == "reload_audit"]
    stage_results = {e.get("stage"): e for e in events if e["event"] == "stage_result"}
    cleanups = [e for e in events if e["event"] == "cleanup"]

    cap_gate_ok = (
        any(r.get("reason") == "cap_reached" for r in refusals)
        and any(r.get("reason") == "rank_too_high" for r in refusals)
    ) or (stage_results.get(10, {}).get("pass") is True)

    cmds_seen = {c.get("cmd") for c in fireteam_cmds}
    stances_seen = {c.get("stance") for c in fireteam_cmds if c.get("cmd") == "stance"}
    max_slot_seen = max((r["slot"][0] for r in recruits if isinstance(r.get("slot"), tuple)), default=0)
    fireteam_4npc_ok = (
        max_slot_seen >= 4
        and {"all_wait", "all_follow", "stance", "inspect_all"}.issubset(cmds_seen)
        and {"aggressive", "defensive", "hold_fire"}.issubset(stances_seen)
    )

    tp_reasons = {t.get("reason") for t in teleports if (t.get("moved") or 0) > 0}
    teleport_ok = set(TELEPORT_CHOKEPOINTS).issubset(tp_reasons)

    affinity_ok = any(a.get("tier") == "idolized" and a.get("perk_granted") is True for a in affinities)
    upkeep_ok = bool(payouts) and any(l.get("after") == 60.0 for l in loyalties)
    reload_ok = any(
        rl.get("pass") is True and (rl.get("reload_count") or 0) >= 1 and rl.get("when") in ("reload", "reload+2s", "stage50")
        for rl in reloads
    )
    dismiss_ok = any(c.get("pass") is True and c.get("active") == 0 for c in cleanups) or len(dismissals) >= 4

    checks = {
        "base_cap_and_gates": cap_gate_ok,
        "fireteam_4npc_commands": fireteam_4npc_ok,
        "teleport_3_chokepoints": teleport_ok,
        "affinity_perk_grant": affinity_ok,
        "upkeep_and_loyalty": upkeep_ok,
        "save_reload_persistence": reload_ok,
        "clean_dismiss": dismiss_ok,
    }
    return {
        "events": events,
        "cut": cut,
        "init": inits[-1] if inits else None,
        "recruits": recruits,
        "refusals": refusals,
        "dismissals": dismissals,
        "fireteam_cmds": fireteam_cmds,
        "teleports": teleports,
        "affinities": affinities,
        "loyalties": loyalties,
        "payouts": payouts,
        "reloads": reloads,
        "stage_results": stage_results,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, tuple) and len(v) == 2:
        return f"{v[0]}/{v[1]}"
    return "none" if v is None else str(v)


def report(s):
    out = []
    init = s.get("init")
    if init:
        out.append(
            f"init: quest={_fmt(init.get('quest'))} sq_followers={_fmt(init.get('sq_followers'))} "
            f"sq_groups={_fmt(init.get('sq_groups'))} cap={_fmt(init.get('base_cap'))}..{_fmt(init.get('max_cap'))} "
            f"merc={_fmt(init.get('merc_cost'))}/{_fmt(init.get('merc_share'))}"
        )
    out.append(
        f"counts: recruits={len(s['recruits'])} refusals={len(s['refusals'])} cmds={len(s['fireteam_cmds'])} "
        f"teleports={len(s['teleports'])} affinities={len(s['affinities'])} reloads={len(s['reloads'])}"
    )
    for key, ok in s["checks"].items():
        out.append(f"{'PASS' if ok else 'FAIL'} {key}")
    if s["cut"]:
        out.append(f"note: {s['cut']} truncated line(s) without end=true ignored")
    out.append("VERDICT: PASS" if s["passed"] else "VERDICT: FAIL")
    return out
