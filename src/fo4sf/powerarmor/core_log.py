"""Parse and summarize FO4SFPACore.0.log (written by scripts/powerarmor/FO4SF_PowerArmorCoreQuest.psc).

Every trace line emitted by the quest script matches:
  FO4SFPACORE rt=<real time s> <event> key=value ... end=true
anywhere on the line (Starfield prepends a timestamp). Lines lacking `end=true` were truncated and are counted in `cut`.
Reload events (`reload_sync`) join the active run across save-quit-reload sessions so a full climb-in -> drain ->
save/quit/reload -> exit -> salvaged-NCR session is evaluated as one coherent run.
"""
import re

LINE = re.compile(r"FO4SFPACORE rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = (
    "init",
    "say",
    "entry_refused",
    "enter_standin_begin",
    "exit_standin_begin",
    "fall_long",
    "terrain_dupes_disabled",
    "captured_worn",
    "outfit_saved",
    "climb_in",
    "drain",
    "core_reload",
    "core_depleted",
    "exit_complete",
    "frame_deployed",
    "salvaged_equip",
    "salvaged_unequip",
    "reload_sync",
    "status",
)
ID_KEYS = {
    "quest", "parace", "bptd", "framefurn", "core", "salvaged",
    "race", "orig_race", "item", "ref", "cell", "frame_static", "minigun_acti",
}
ACTIVE_EVENTS = {
    "climb_in",
    "drain",
    "core_reload",
    "core_depleted",
    "exit_complete",
    "salvaged_equip",
    "reload_sync",
}
OURS = re.compile(
    r"FO4SF_PA|FO4SF_PowerArmor|FO4SF_Salvaged|FO4SF_FusionCore|FO4SFPowerArmor|FO4SFPACore",
    re.IGNORECASE,
)


def u32(v):
    return None if v is None else int(v) & 0xFFFFFFFF


def parse_value(key, text):
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
    """Return parsed event dict for one FO4SFPACORE line, or None for unrelated lines."""
    m = LINE.search(line)
    if not m:
        return None
    try:
        rt = float(m.group("rt"))
    except ValueError:
        return None
    if not line.rstrip().lower().endswith("end=true"):
        return {"rt": rt, "event": m.group("event").lower(), "end": False}
    if m.group("event").lower() not in EVENTS:
        return None
    rest = m.group("rest")
    if m.group("event").lower() == "say":
        idx = rest.lower().rfind(" end=true")
        body = rest[:idx].strip() if idx >= 0 else rest.strip()
        text_val = body[5:] if body.lower().startswith("text=") else body
        return {"rt": rt, "event": "say", "text": text_val, "end": True}
    out = {"rt": rt, "event": m.group("event").lower()}
    for k, v in TOKEN.findall(rest):
        kl = k.lower()
        out[kl] = parse_value(kl, v)
    out["end"] = out.get("end") is True
    return out


def runs(lines):
    """Split log lines into runs at a fresh `init version=...` after active gameplay events; `reload_sync` stays in-run."""
    out, cur, cut = [], [], 0
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        if not p["end"]:
            cut += 1
            continue
        if p["event"] == "init" and p.get("version") is not None and any(e["event"] in ACTIVE_EVENTS for e in cur):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out, cut


def hexid(v):
    return "none" if v is None else f"{v:08X}" if isinstance(v, int) else str(v)


def papyrus_errors(lines):
    """Extract deduplicated error/warning lines from Papyrus.0.log referencing FO4SF Power Armor records/scripts."""
    out = []
    for line in lines:
        t = line.strip()
        m = re.search(r"\b(error|warning)\b", t, re.IGNORECASE)
        if not m or not OURS.search(t):
            continue
        t = t[m.start():]
        if t not in out:
            out.append(t)
    return out


def summarize(lines, run=-1, papyrus=None):
    """Summarize the selected run across climb-in, FusionCore drain, save/reload, exit outfit restore, and salvaged NCR."""
    rs, cut = runs(lines)
    errs = papyrus_errors(papyrus) if papyrus is not None else []
    summary = {
        "runs": len(rs),
        "run": 0,
        "cut": cut,
        "papyrus": errs,
        "papyrus_read": papyrus is not None,
        "init": None,
        "climb_in": {"ok": False, "detail": "not run"},
        "fusion_core": {"ok": False, "detail": "no drain/reload/deplete events"},
        "reload_sync": {"ok": False, "detail": "not run"},
        "exit_restore": {"ok": False, "detail": "not run"},
        "salvaged_ncr": {"ok": False, "detail": "not run"},
        "events": [],
        "problems": [],
        "verdict": "INCONCLUSIVE: no log lines",
    }
    if not rs:
        return summary

    r = rs[run]
    summary["run"] = run if run >= 0 else len(rs) + run
    summary["events"] = [e for e in r if e["event"] != "say"]
    init = next((e for e in r if e["event"] == "init"), None)
    summary["init"] = init

    climbs = [e for e in r if e["event"] == "climb_in"]
    outfit_saves = [e for e in r if e["event"] == "outfit_saved"]
    refusals = [e for e in r if e["event"] == "entry_refused"]
    falls = [e for e in r if e["event"] == "fall_long"]
    summary["entry_refused"] = refusals
    summary["fall_long"] = falls
    if climbs:
        c = climbs[-1]
        eq = c.get("equipped_pa", 0)
        inpa = c.get("inpa", 0.0)
        limbs = c.get("limbs_min", 0.0)
        saved_n = outfit_saves[-1].get("saved_worn", 0) if outfit_saves else 0
        ok = eq >= 4 and float(inpa) >= 1.0 and float(limbs) >= 100.0
        summary["climb_in"] = {
            "ok": ok,
            "detail": f"equipped_pa={eq} inpa={inpa} limbs_min={limbs} charge={c.get('charge')} saved_worn={saved_n} race={hexid(c.get('race'))}",
        }

    drains = [e for e in r if e["event"] == "drain"]
    reloads = [e for e in r if e["event"] == "core_reload"]
    depleted = [e for e in r if e["event"] == "core_depleted"]
    if drains or reloads or depleted:
        min_charge = min([float(e.get("charge", 100.0)) for e in drains] + ([0.0] if depleted else [100.0]))
        slow_ok = any(e.get("slow_walk") is True for e in depleted)
        summary["fusion_core"] = {
            "ok": bool(drains) or bool(reloads) or slow_ok,
            "detail": f"drain_ticks={len(drains)} min_charge={min_charge:.1f} reloads={len(reloads)} depleted={len(depleted)} slow_walk={slow_ok}",
        }

    syncs = [e for e in r if e["event"] == "reload_sync"]
    if syncs:
        s = syncs[-1]
        inpa = s.get("inpa")
        eq = s.get("equipped_pa", 0)
        ok = (inpa is True and eq >= 4 and float(s.get("pa_av", 0.0)) >= 1.0) or (
            inpa is False and eq == 0 and float(s.get("pa_av", 0.0)) == 0.0
        )
        summary["reload_sync"] = {
            "ok": ok,
            "detail": f"count={len(syncs)} inpa={inpa} equipped_pa={eq} charge={s.get('charge')} saved_worn={s.get('saved_worn')} limbs_min={s.get('limbs_min')}",
        }

    exits = [e for e in r if e["event"] == "exit_complete"]
    if exits:
        x = exits[-1]
        eq = x.get("equipped_pa", -1)
        inpa = float(x.get("inpa", 1.0))
        standing = x.get("frame_standing") is True
        restored = x.get("restored_worn", 0)
        ok = eq == 0 and inpa == 0.0 and standing
        summary["exit_restore"] = {
            "ok": ok,
            "detail": f"restored_worn={restored} equipped_pa={eq} inpa={inpa} frame_standing={standing} race={hexid(x.get('race'))}",
        }

    salv = [e for e in r if e["event"] == "salvaged_equip"]
    if salv:
        se = salv[-1]
        no_pa = se.get("inpa") is False and float(se.get("pa_av", 1.0)) == 0.0
        summary["salvaged_ncr"] = {
            "ok": no_pa,
            "detail": f"item={hexid(se.get('item'))} inpa={se.get('inpa')} pa_av={se.get('pa_av')} agi={se.get('agi')}",
        }

    if cut:
        summary["problems"].append(f"{cut} truncated line(s) lacking end=true were ignored")
    if errs:
        summary["problems"].append(f"{len(errs)} Papyrus error/warning line(s) mention FO4SF Power Armor forms")

    checks = ("climb_in", "fusion_core", "reload_sync", "exit_restore", "salvaged_ncr")
    passed = [k for k in checks if summary[k]["ok"]]
    if len(passed) == len(checks) and not errs:
        summary["verdict"] = "PASS: climb-in, FusionCore drain, save/reload, exit outfit restore, and salvaged NCR worn ARMO all verified"
    elif passed:
        missing = [k for k in checks if not summary[k]["ok"]]
        summary["verdict"] = f"PARTIAL ({len(passed)}/{len(checks)} verified): passed={','.join(passed)}; pending={','.join(missing)}"
    else:
        summary["verdict"] = "INCONCLUSIVE: quest initialized but no climb-in or salvaged-armor checks completed yet"
    return summary


def quest_lines(summary):
    q = (summary.get("init") or {}).get("quest")
    if not isinstance(q, int):
        return ["quest form id: not in log (no init line with quest=)"]
    return [f"quest form id {q:08X}: setstage {q:08X} 10 (climb-in) / 20 (drain/status) / 30 (exit) / 40 (deploy frame)"]


def report(summary):
    lines = list(quest_lines(summary))
    for key, label in (
        ("climb_in", "climb_in"),
        ("fusion_core", "fusion_core"),
        ("reload_sync", "reload_sync"),
        ("exit_restore", "exit_restore"),
        ("salvaged_ncr", "salvaged_ncr"),
    ):
        item = summary[key]
        lines.append(f"{'PASS' if item['ok'] else 'PEND'}  {label:14s}: {item['detail']}")
    if summary.get("papyrus"):
        lines += ["papyrus: " + e for e in summary["papyrus"]]
    lines += ["note: " + p for p in summary.get("problems", [])]
    lines.append(summary["verdict"])
    return lines
