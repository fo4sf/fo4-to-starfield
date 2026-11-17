"""Structured log parser, CMPO -> IRES reference math, and verdict reporter for FO4SFWorkshop.esm
(FO4SFWorkshopCore.0.log, written by scripts/workshop/FO4SF_WorkshopCoreQuest.psc; docs/workshop/workshop-camps.md).

Log format:
  FO4SFWSCORE rt=<real time s> <event> key=value ... end=true

Across a save-quit-reload cycle, Starfield rotates the pre-reload session log to FO4SFWorkshopCore.1.log and writes
post-reload events (OnPlayerLoadGame -> reload_audit, stage 50, stage 40 pack-up, stage 60 cleanup) to
FO4SFWorkshopCore.0.log. `load_session_lines(primary_path)` stitches the latest pre-reload session from `.1.log` (when
present and `.0.log` begins with post-reload events) together with `.0.log` so one `make_workshop_core.py log` call
evaluates the full save-quit-reload verification chain.
"""
import os
import re

LINE = re.compile(r"FO4SFWSCORE rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")

EVENTS = (
    "init",
    "bench_placed",
    "camp_deployed",
    "camp_blocked",
    "camp_packed",
    "station_placed",
    "station_removed",
    "scrap_run",
    "recipe_audit",
    "read",
    "reload_audit",
    "cleanup",
    "say",
)

STAGES = (15, 10, 20, 30, 50, 40, 60)

# Locked 18 Fallout 4 CMPO scrap archetypes [0..17] -> primary Starfield.esm IRES & MISC EditorIDs
CMPO_TABLE = (
    (0, "Steel", "ResInorgCommonIron", "InorgCommonIron"),
    (1, "Wood", "ResOrgCommonStructural", "OrgCommonStructural"),
    (2, "Aluminum", "ResInorgCommonAluminum", "InorgCommonAluminum"),
    (3, "Adhesive", "ResOrgRareAdhesive", "OrgRareAdhesive"),
    (4, "Screws", "ResInorgUncommonTungsten", "InorgUncommonTungsten"),
    (5, "Copper", "ResInorgCommonCopper", "InorgCommonCopper"),
    (6, "Circuitry", "ResMfg_Tier01_ZeroWire", "Mfg_Tier01_ZeroWire"),
    (7, "NuclearMaterial", "ResInorgCommonUranium", "InorgCommonUranium"),
    (8, "Lead", "ResInorgCommonLead", "InorgCommonLead"),
    (9, "Gears", "ResMfg_Tier01_AdaptiveFrame", "Mfg_Tier01_AdaptiveFrame"),
    (10, "Springs", "ResInorgRareTitanium", "InorgRareTitanium"),
    (11, "Oil", "ResOrgExoticLubricant", "OrgExoticLubricant"),
    (12, "Cloth", "ResOrgCommonFiber", "OrgCommonFiber"),
    (13, "Glass", "ResOrgUncommonCosmetic", "OrgUncommonCosmetic"),
    (14, "Plastic", "ResOrgExoticPolymer", "OrgExoticPolymer"),
    (15, "Rubber", "ResOrgCommonSealant", "OrgCommonSealant"),
    (16, "Ceramic", "ResInorgUncommonChlorosilanes_L", "InorgUncommonChlorosilanes"),
    (17, "Antiseptic", "ResOrgUncommonAntimicrobial", "OrgUncommonAntimicrobial"),
)

# Clean-room FO4 scrap junk yields: {edid: ((cmpo_index, count), ...)}
JUNK_YIELDS = {
    "FO4SF_Junk_DeskFan": ((0, 2), (9, 2), (4, 2)),
    "FO4SF_Junk_DuctTape": ((3, 2), (12, 1)),
    "FO4SF_Junk_HotPlate": ((5, 2), (6, 1), (4, 1)),
    "FO4SF_Junk_TinCan": ((0, 2), (2, 2)),
}


def expected_scrap_yields(counts_by_edid):
    """Return {cmpo_index: total_count} for a dict of {junk_edid: count}."""
    totals = {}
    for edid, item_count in counts_by_edid.items():
        if item_count <= 0:
            continue
        for cmpo_idx, per_item in JUNK_YIELDS.get(edid, ()):
            totals[cmpo_idx] = totals.get(cmpo_idx, 0) + int(item_count) * per_item
    return totals


def _parse_value(key, text):
    low = text.lower()
    if low == "none":
        return None
    if low == "na":
        return "na"
    if low in ("true", "false"):
        return low == "true"
    if key == "pos":
        try:
            xyz = tuple(float(v) for v in text.split(","))
            return xyz if len(xyz) == 3 else text
        except ValueError:
            return text
    if key == "rt":
        return float(text)
    if "/" in text and key.endswith("_ok"):
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
    """Parse one FO4SFWSCORE line into a dict, or None for non-matching lines."""
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
        elif kl in ("when", "kind", "mode", "reason"):
            d[kl] = v.lower()
        else:
            d[kl] = _parse_value(kl, v)
    return d


def load_session_lines(primary_path, include_rotated=True):
    """Read primary_path (FO4SFWorkshopCore.0.log) and, if it holds post-reload events without an `init` line and
    sibling `.1.log` exists, prepend the latest `init` session from `.1.log`."""
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
    """Split parsed lines on `init` boundaries; post-reload lines without a new `init` stay attached to the active run."""
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
    """Evaluate the latest workshop-camps verification session and return structured check verdicts."""
    all_runs, cut = runs(lines)
    events = all_runs[-1] if all_runs else []

    inits = [e for e in events if e["event"] == "init"]
    benches = [e for e in events if e["event"] == "bench_placed" and e.get("ref") is not None]
    camps = [e for e in events if e["event"] == "camp_deployed" and e.get("ref") is not None]
    blocks = [e for e in events if e["event"] == "camp_blocked" and e.get("refunded") is True]
    packs = [e for e in events if e["event"] == "camp_packed" and e.get("refunded_kit") is True and e.get("ref") is not None]
    stations = [e for e in events if e["event"] == "station_placed" and e.get("ref") is not None]
    scraps = [e for e in events if e["event"] == "scrap_run"]
    recipes = [e for e in events if e["event"] == "recipe_audit"]
    reloads = [e for e in events if e["event"] == "reload_audit"]
    reads = [e for e in events if e["event"] == "read"]

    bench_ok = any(b.get("moved") is True and b.get("loaded") is True and b.get("haskw") is True for b in benches)
    camp_ok = any(c.get("moved") is True and c.get("loaded") is True for c in camps)
    excl_ok = any(
        b.get("reason") == "exclusion_zone"
        and isinstance(b.get("nearest_dist"), (int, float))
        and isinstance(b.get("min_dist"), (int, float))
        and b["nearest_dist"] < b["min_dist"]
        for b in blocks
    )
    scrap_ok = any(
        s.get("pass") is True and (s.get("junk_removed") or 0) >= 4 and (s.get("components_added") or 0) > 0
        for s in scraps
    )
    recipe_ok = any(
        r.get("pass") is True
        and r.get("cmpo_pairs") == 18
        and r.get("recipes_total") == 8
        and r.get("valid_forms") == 8
        for r in recipes
    )
    reload_ok = any(
        rl.get("pass") is True
        and (rl.get("reload_count") or 0) >= 1
        and rl.get("when") in ("reload", "reload+2s", "stage50")
        for rl in reloads
    )
    pack_ok = len(packs) >= 1

    checks = {
        "settlement_bench": bench_ok,
        "portable_camp": camp_ok,
        "camp_exclusion": excl_ok,
        "cmpo_scrap": scrap_ok,
        "bench_recipes": recipe_ok,
        "save_reload_persistence": reload_ok,
        "camp_packup": pack_ok,
    }
    passed = all(checks.values())
    return {
        "events": events,
        "cut": cut,
        "init": inits[-1] if inits else None,
        "benches": benches,
        "camps": camps,
        "blocks": blocks,
        "packs": packs,
        "stations": stations,
        "scraps": scraps,
        "recipes": recipes,
        "reloads": reloads,
        "reads": reads,
        "checks": checks,
        "passed": passed,
    }


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, tuple) and len(v) == 2:
        return f"{v[0]}/{v[1]}"
    return "none" if v is None else str(v)


def report(s):
    """Format a concise human-readable verification table with deterministic PASS / FAIL lines."""
    out = []
    init = s.get("init")
    if init:
        out.append(
            f"init: quest={_fmt(init.get('quest'))} core={_fmt(init.get('core'))} "
            f"cmpo_ires={_fmt(init.get('cmpo_ires'))} cmpo_misc={_fmt(init.get('cmpo_misc'))} "
            f"recipes={_fmt(init.get('recipes'))}"
        )
    out.append(
        f"counts: benches={len(s['benches'])} camps={len(s['camps'])} blocks={len(s['blocks'])} "
        f"stations={len(s['stations'])} scraps={len(s['scraps'])} reloads={len(s['reloads'])} packs={len(s['packs'])}"
    )
    for rl in s["reloads"]:
        out.append(
            f"  reload_audit when={rl.get('when')} reload_count={rl.get('reload_count')} "
            f"benches_ok={_fmt(rl.get('benches_ok'))} beacons_ok={_fmt(rl.get('beacons_ok'))} "
            f"stations_ok={_fmt(rl.get('stations_ok'))} pass={_fmt(rl.get('pass'))}"
        )
    for key, ok in s["checks"].items():
        out.append(f"{'PASS' if ok else 'FAIL'} {key}")
    if s["cut"]:
        out.append(f"note: {s['cut']} truncated line(s) without end=true ignored")
    out.append("VERDICT: PASS" if s["passed"] else "VERDICT: FAIL")
    return out
