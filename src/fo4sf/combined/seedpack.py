"""Turn a seed draft (seed.py) into a pack that runs: holders, factions, homes, routes and settlement stats by rules.

generate(draft, rules) returns (pack, report). The pack passes pack.validate_pack, loads into a WorldState and runs
under sim.run with the balance invariants kept (homes and story locks never change hands, which the simulation
enforces by construction). Deterministic: the same draft and rules give byte-identical JSON (sorted walks, no
randomness, no clock).

Every number and name in DEFAULT_RULES is a PLACEHOLDER to argue with, except where a comment names the first real
run (owner's PC, 2026-10-21, Fallout4.esm + DLCRobot.esm + DLCworkshop01.esm) as support. Keyword and faction
editor ids are read from the draft; nothing here states what a game's records contain beyond the keyword names that
run listed (LocTypeWorkshop, LocTypeWorkshopSettlement, LocTypeSettlement, LocEncRaiders, LocEncSuperMutants,
LocEncGhouls) and the ref type WorkshopRefType. The pack's factions are its own small set (settlers plus each enemy
the rules map), not the draft's hundreds of FACT records; FACT relation data is carried only where an edid matches a
rules pattern, otherwise the placeholder relations apply.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
from collections import Counter

from . import seed as _seed
from .model import STRENGTH_CAP
from .pack import validate_pack

# LocEnc<X> keywords: the <X> part names what is encountered at the place; the first run listed Raiders (39),
# SuperMutants (24) and Ghouls (27). Which other <X> values exist is unknown here; an unmapped one is reported, not
# guessed. The pack faction ids on the right are our own names.
ENC_KEYWORD = re.compile(r"^LocEnc(\w+)$")

DEFAULT_RULES = {
    # Pack faction that holds every settlement candidate at the start (our name; placeholder).
    "settlers": "settlers",
    # LocEnc<X> -> pack faction id. Raiders, SuperMutants and Ghouls are supported by the first run's keyword counts;
    # Gunners is a PLACEHOLDER guess at a keyword name, kept so a real draft that has it is mapped and one that does
    # not reports nothing (an absent keyword costs nothing).
    "enc_factions": {"Raiders": "raiders", "SuperMutants": "supermutants", "Ghouls": "ghouls", "Gunners": "gunners"},
    # PLACEHOLDER regex guesses on FACT editor ids -> pack faction id, for carrying the drafted XNAM relations
    # (seed.REACTION_RELATION). UNVERIFIED: the first run's report counts locations' keywords, not faction names.
    # Where no FACT matches, the placeholder relations below apply.
    "fact_patterns": {"raiders": r"raider", "supermutants": r"supermutant", "ghouls": r"ghoul|feral",
                      "gunners": r"gunner"},
    # PLACEHOLDER relations: each mapped enemy is an enemy of the settlers, enemies are neutral to one another
    # unless FACT data says otherwise.
    "enemy_of_settlers": -80,
    # PLACEHOLDER strength: base + per place held, capped by the model (sim needs 6 or more to attack at all).
    "strength_base": 8,
    "strength_per_place": 2,
    # PLACEHOLDER aggression (0..100 chance weight, model.Faction): settlers defend, enemies push.
    "aggression": {"settlers": 20, "default": 70},
    # PLACEHOLDER defence per kind (model.Place.defence; the fixtures use 1..4 for settlements and camps).
    "defence": {"settlement": 2, "base": 4, "landmark": 0},
    # Routes: each place with a marker joins its k nearest in the same world. PLACEHOLDER k and speed; speed is in
    # the marker's own position units per game hour, with no claim about what a unit measures. To tune once a real
    # draft's distances are seen (seedpack_report.json lists the hour distribution).
    "k_nearest": 3,
    "units_per_hour": 20000.0,
    # Settlement stats: the same starting numbers the fixtures' farm_a uses (fixtures.REGION_1), PLACEHOLDERS.
    "settlement": {"population": 5, "roles": {"farmer": 3, "guard": 1, "trader": 1, "crafter": 0, "scavenger": 0,
                                               "doctor": 0},
                   "stock": {"food": 20, "water": 20, "scrap": 0, "ammo": 10, "medicine": 0},
                   "morale": 50, "stage": 0, "beds": 20},
}


def _enc_faction(place: dict, rules: dict, unmapped: Counter) -> str | None:
    """The pack faction a place's LocEnc<X> keywords map to (first mapped keyword in sorted order), or None."""
    for kw in sorted(place.get("keywords", [])):
        m = ENC_KEYWORD.match(kw)
        if not m:
            continue
        fid = rules["enc_factions"].get(m.group(1))
        if fid is not None:
            return fid
        unmapped[kw] += 1
    return None


def _keep(place: dict) -> str | None:
    """Why a draft place is dropped, or None to keep it: settlement candidates and places with a marker position
    stay; the rest (quest and virtual locations, unplaced parents) go."""
    if place.get("kind") == "settlement" or place.get("marker"):
        return None
    return "no marker position" if not place.get("has_marker") else "marker position not found"


def _distance(a: dict, b: dict) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _hours(dist: float, rules: dict) -> int:
    """Travel hours for a marker distance: distance / speed, rounded half up, at least 1."""
    return max(1, int(dist / rules["units_per_hour"] + 0.5))


def _routes(places: list[dict], rules: dict) -> tuple[list[dict], list[str], Counter]:
    """k-nearest routes per world among marker places, undirected and deduplicated; a place without a marker joins
    its parent when the parent is kept. Returns (routes, isolated place ids, drop reasons for unlinked places)."""
    by_id = {p["id"]: p for p in places}
    edges: dict[frozenset, int] = {}
    worlds: dict[str | None, list[dict]] = {}
    for p in places:
        if p.get("marker"):
            worlds.setdefault(p["marker"].get("world"), []).append(p)
    k = rules["k_nearest"]
    for world in sorted(worlds, key=lambda w: (w is None, w or "")):
        group = sorted(worlds[world], key=lambda p: p["id"])
        for p in group:
            others = sorted(((_distance(p["marker"], q["marker"]), q["id"]) for q in group if q is not p))
            for dist, qid in others[:k]:
                edge = frozenset((p["id"], qid))
                if edge not in edges:
                    edges[edge] = _hours(dist, rules)
    unlinked = Counter()
    for p in places:
        if p.get("marker"):
            continue
        parent = p.get("parent")
        if parent in by_id and parent != p["id"]:
            edges.setdefault(frozenset((p["id"], parent)), 1)   # PLACEHOLDER: one hour to the parent location
        else:
            unlinked["no marker and parent not kept"] += 1
    routes = sorted(({"a": min(e), "b": max(e), "hours": h} for e, h in edges.items()),
                    key=lambda r: (r["a"], r["b"]))
    linked = {r["a"] for r in routes} | {r["b"] for r in routes}
    isolated = sorted(p["id"] for p in places if p["id"] not in linked)
    return routes, isolated, unlinked


def _neighbours(routes: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in routes:
        out.setdefault(r["a"], set()).add(r["b"])
        out.setdefault(r["b"], set()).add(r["a"])
    return out


def _home(fid: str, held: list[str], holder: dict[str, str | None], nbrs: dict[str, set[str]]) -> str:
    """The held place with the most neighbours held by the same faction; ties go to the smaller id."""
    return min(held, key=lambda pid: (-sum(holder.get(n) == fid for n in nbrs.get(pid, ())), pid))


def _fact_relations(draft: dict, rules: dict) -> tuple[dict[str, dict[str, int]], dict[str, list[str]]]:
    """Relations between pack factions carried from the drafted FACT records whose editor ids match
    rules["fact_patterns"]: for each pair, the first matching FACT (sorted by id) that has a relation to any FACT
    matching the other side, mapped through seed.REACTION_RELATION. Also returns which FACT ids matched."""
    rx = {fid: re.compile(pat, re.I) for fid, pat in sorted(rules["fact_patterns"].items())}
    matched: dict[str, list[str]] = {fid: [] for fid in rx}
    facts = {f["id"]: f for f in draft.get("factions", [])}
    for name in sorted(facts):
        for fid, r in rx.items():
            if r.search(name):
                matched[fid].append(name)
    rel: dict[str, dict[str, int]] = {}
    for a, names_a in sorted(matched.items()):
        for b, names_b in sorted(matched.items()):
            if a == b:
                continue
            for name in names_a:
                hits = [facts[name]["relations"][o] for o in sorted(facts[name]["relations"]) if o in names_b]
                if hits:
                    rel.setdefault(a, {})[b] = _seed.REACTION_RELATION.get(hits[0]["reaction"], 0)
                    break
    return rel, {k: v for k, v in matched.items() if v}


def generate(draft: dict, rules: dict | None = None) -> tuple[dict, dict]:
    """(pack, report) from a seed draft by DEFAULT_RULES (or `rules`, same keys). See the module docstring."""
    rules = copy.deepcopy(DEFAULT_RULES if rules is None else rules)
    settlers = rules["settlers"]
    drops, unmapped, holder, kinds = Counter(), Counter(), {}, {}
    kept = []
    for p in sorted(draft.get("places", []), key=lambda p: p["id"]):
        why = _keep(p)
        if why:
            drops[why] += 1
            continue
        kept.append(p)
        if p["kind"] == "settlement":
            holder[p["id"]], kinds[p["id"]] = settlers, "settlement"
        else:
            enemy = _enc_faction(p, rules, unmapped)
            holder[p["id"]] = enemy
            kinds[p["id"]] = "base" if enemy else ("landmark" if p["kind"] not in ("base", "landmark") else p["kind"])
    routes, isolated, unlinked = _routes(kept, rules)
    nbrs = _neighbours(routes)

    places = [{"id": p["id"], "region": p["region"], "kind": kinds[p["id"]], "holder": holder[p["id"]],
               "defence": rules["defence"][kinds[p["id"]]]} for p in kept]
    settlements = [dict(place=p["id"], **copy.deepcopy(rules["settlement"])) for p in kept
                   if kinds[p["id"]] == "settlement"]

    held: dict[str, list[str]] = {}
    for pid in sorted(holder):
        if holder[pid]:
            held.setdefault(holder[pid], []).append(pid)
    fact_rel, fact_matched = _fact_relations(draft, rules)
    factions, factions_dropped = [], []
    wanted = sorted({settlers, *rules["enc_factions"].values()})
    for fid in wanted:
        if fid not in held:
            factions_dropped.append(fid)          # holds nothing, so it can have no home
            continue
        rel = {}
        for other in wanted:
            if other == fid or other not in held:
                continue
            if other in fact_rel.get(fid, {}):
                rel[other] = fact_rel[fid][other]
            elif settlers in (fid, other):
                rel[other] = rules["enemy_of_settlers"]
        factions.append({
            "id": fid,
            "strength": min(STRENGTH_CAP, rules["strength_base"] + rules["strength_per_place"] * len(held[fid])),
            "home": _home(fid, held[fid], holder, nbrs),
            "aggression": rules["aggression"].get(fid, rules["aggression"]["default"]),
            "relations": rel,
        })
    pack = {"places": places, "settlements": settlements, "factions": factions, "routes": routes}
    problems = validate_pack(pack)
    report = {
        "source_plugins": draft.get("source_plugins", []),
        "draft_places": len(draft.get("places", [])), "kept": len(kept), "dropped": dict(sorted(drops.items())),
        "kinds": dict(sorted(Counter(kinds.values()).items())),
        "holders": {fid: len(v) for fid, v in sorted(held.items())},
        "unheld": sum(1 for v in holder.values() if v is None),
        "unmapped_enc_keywords": dict(sorted(unmapped.items())),
        "factions": [f["id"] for f in factions], "factions_dropped_no_place": factions_dropped,
        "fact_relations_carried": {a: dict(sorted(b.items())) for a, b in sorted(fact_rel.items())
                                   if a in {f["id"] for f in factions}},
        "fact_ids_matched": fact_matched,
        "homes": {f["id"]: f["home"] for f in factions},
        "routes": len(routes), "route_hours": dict(sorted(Counter(r["hours"] for r in routes).items())),
        "isolated": isolated, "unlinked": dict(sorted(unlinked.items())),
        "worlds": dict(sorted(Counter(p["marker"]["world"] for p in kept if p.get("marker")).items(),
                              key=lambda kv: (kv[0] is None, kv[0] or ""))),
        "validation_problems": problems,
        "rules": rules,
    }
    return pack, report


def write(out_dir: str, pack: dict, report: dict) -> dict:
    """Write commonwealth.pack.json and seedpack_report.json into out_dir; return the two paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {"pack": os.path.join(out_dir, "commonwealth.pack.json"),
             "report": os.path.join(out_dir, "seedpack_report.json")}
    with open(paths["pack"], "w", encoding="utf-8") as f:
        f.write(dumps(pack))
    with open(paths["report"], "w", encoding="utf-8") as f:
        f.write(dumps(report))
    return paths


def dumps(obj) -> str:
    """The canonical JSON text: sorted keys, one-space indent, trailing newline (byte-identical for equal input)."""
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def summary(report: dict) -> str:
    """One line for the command line."""
    return (f"seed-pack: {report['kept']} of {report['draft_places']} places kept, "
            f"{len(report['factions'])} factions, {report['routes']} routes, {len(report['isolated'])} isolated, "
            f"{len(report['validation_problems'])} validation problems")
