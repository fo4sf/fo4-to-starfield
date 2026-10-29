"""The planet probe's user log (FO4SFPlanetProbe.0.log, written by scripts/planet/FO4SF_PlanetProbeQuest.psc) read
back into arrivals, readings and a verdict per test reference (docs/planet/planet-probe.md section 5).

Every line the script writes holds "FO4SFPP rt=<real time s> <event> key=value ...", anywhere in the line (the game
puts a time stamp in front). Values: form ids as Papyrus prints them (signed decimal, so a load index of 0x80 or more
and the runtime FF ids are negative), floats, bools, "none" for a None form, and lists of form ids joined by commas
("none" for an empty list). Events: init (once per new script instance: the quest's own id gives the probe plugin's
load index), chain (the location chain as the game resolves it), arrive, then player / planet / ref / location
lines at 2, 10, 30 and 60 s after each arrival.

The chain line (chain_reading): Starfield's Location.IsChild "Returns whether the other location is a child of this
one" (Location.psc, ContentResources.zip, read 29 Oct), so version 2 of the script asks each parent about its child
(surface_has_probe, planet_has_surface) and lists the parents the game gives each of our three locations
(probe_parents, surface_parents, planet_parents: GetParentLocations, which Starfield's own scripts use to find the
planet and star system of a site's or an outpost's location, SQ_ParentScript.psc and SQ_OutpostAttackScript.psc, so
a list may hold every ancestor). The reader checks each location's own parent in our records in that location's own
list, so the answer does not depend on how far a list goes, and says whether the probe location's list goes past its
parent (ancestors). Version 1 (probe run 1, 29 Oct) asked the child about its parent (probe_child_of_surface,
surface_child_of_planet): those two values are no evidence, and the reader says so instead of judging them.

Case: Starfield's Papyrus prints a bool as "true" / "false" (verified: the bridge log of 14 Oct and the new game log
of 28 Oct, docs/ai/test-queue.md and docs/newgame/vault111-start.md), Fallout 4's as "True" / "False". It also keeps
one spelling per string, so literal text can come back in another case (the 28 Oct log printed "FO4Port.esm" as
"fo4port.esm"). So the reader ignores case: in the prefix, the events, the keys, the bools, "none" and the tags
(read as upper case: T1 .. T6, MERGE, LC172COC).

The verdict a reference gets at an arrival, from its last reading there:
  with player   found, in the player's worldspace (sameworld true, the worldspace not None)
  left behind   found, in another worldspace (for ours: the base probe world the game never plays)
  not loaded    GetFormFromFile returned None: a temporary reference whose cell is not loaded, or a missing record
  not installed its plugin is not loaded
  unknown       the line lacks a value the verdict needs (a cut line), or both are in interiors
The offset is the reference's position minus its position in the plugin (plan.json "refs" / "merge"): (0, 0) is a
reference where the plugin put it; a merged reference moves with its world (LC172World's COC marker moved by about
(-500, -2300) on 11 Oct). The distance is GetDistance to the player; for a reference in another worldspace the game
returns the largest float, 3.4e38 (verified: probe run 1, 31 of 33 readings), which the table leaves out.
"""
import re

LINE = re.compile(r"FO4SFPP rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "chain", "arrive", "player", "planet", "ref", "location")
ID_KEYS = {"quest", "world", "loc", "planet", "surface", "planetloc", "cell", "id", "editorloc", "type", "atmos",
           "probe_planet", "surface_planet", "planet_location"}
LIST_KEYS = {"probe_parents", "surface_parents", "planet_parents"}
PARENT_LISTS = (("probe_parents", "the probe location", "our surface"),       # (key, whose list, that location's
                ("surface_parents", "our surface", "our planet location"),    # own parent in our records)
                ("planet_parents", "our planet location", "the system location"))
CHAIN_LINKS = ("surface_has_probe", "planet_has_surface")            # version 2: the parent asked about its child
CHAIN_V1 = ("probe_child_of_surface", "surface_child_of_planet")     # version 1: the child asked; no evidence
READINGS = (2, 10, 30, 60)
OTHER_WORLD_M = 1e30                     # GetDistance's answer for another worldspace is 3.4e38 (FLT_MAX)


def u32(v):
    """A form id as Papyrus printed it (signed decimal) as the unsigned 32-bit id, None for none."""
    return None if v is None else int(v) & 0xFFFFFFFF


def id_list(text):
    """A list of form ids as the script joins them ("<id>,<id>,...", signed decimal; "none" for an empty list),
    unsigned; a "none" entry is None and an entry that is no number stays text."""
    if text.lower() in ("none", ""):
        return []
    out = []
    for v in text.split(","):
        try:
            out.append(None if v.lower() == "none" else u32(int(v)))
        except ValueError:
            out.append(v)
    return out


def value(key, text):
    low = text.lower()
    if key in LIST_KEYS:
        return id_list(text)
    if low == "none":
        return None
    if low in ("true", "false"):
        return low == "true"
    if key in ID_KEYS or key in ("n", "at", "local", "version", "actors"):
        try:
            return int(text)
        except ValueError:
            pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_line(line):
    """{"rt", "event", key: value ...} of one probe line, None for any other line."""
    m = LINE.search(line)
    if not m or m.group("event").lower() not in EVENTS:
        return None
    try:
        rt = float(m.group("rt"))
    except ValueError:
        return None
    out = {"rt": rt, "event": m.group("event").lower()}
    for k, v in TOKEN.findall(m.group("rest")):
        k = k.lower()
        out[k] = value(k, v)
    if isinstance(out.get("tag"), str):
        out["tag"] = out["tag"].upper()
    for k in ID_KEYS & set(out):
        if isinstance(out[k], int):
            out[k] = u32(out[k])
    return out


def runs(lines):
    """[[parsed line]] split at each init line (each a new script instance); lines before the first init are kept
    as a run of their own (a log that lost its start)."""
    out, cur = [], []
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        if p["event"] == "init" and cur:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def hexid(v):
    return None if v is None else f"{v:08X}"


def load_index(init):
    """The probe plugin's load index from the init line's quest id (the quest is local id 0x814 of
    FO4SFPlanetProbe.esm), None without an init line."""
    q = (init or {}).get("quest")
    return None if q is None else q >> 24


def name_of(fid, names):
    """A known id's label ("probe world", "Mars", ...), "runtime FF instance" for an FF id, else the hex id."""
    if fid is None:
        return "none"
    if fid in names:
        return names[fid]
    if fid >> 24 == 0xFF:
        return f"runtime {fid:08X}"
    return f"{fid:08X}"


def known_names(plan, init):
    """{form id: label} of the ids the plan and the init line name (runtime ids of our plugins come from init)."""
    names = {}
    for label, fid in ((plan or {}).get("known_ids") or {}).items():
        if isinstance(fid, str):
            fid = int(fid, 16)
        names[fid] = label
    for key, label in (("world", "probe world"), ("loc", "probe location"), ("planet", "our planet"),
                       ("surface", "our surface"), ("planetloc", "our planet location")):
        v = (init or {}).get(key)
        if v is not None:
            names[v] = label
    planetloc = (init or {}).get("planetloc")
    if planetloc is not None and plan is not None and plan.get("system", "own") == "own":     # a stage before route
        names[(planetloc & 0xFF000000) | OWN_SYSTEM_LOC] = "our system location"     # B was route A's: in our master
    return names


OWN_SYSTEM_LOC = 0x801                   # records.SYSTEM_LOC: route A's system location in FO4SFPlanet.esm


def ids_named(names, label):
    """The ids names gives label; "the system location" is the star system's location under any name (route A's
    "our system location", from the init line; route B's "<EditorID> system location", from plan.json)."""
    if label == "the system location":
        return [f for f, n in names.items() if n.endswith("system location")]
    return [f for f, n in names.items() if n == label]


def chain_reading(chain, names):
    """What the chain line shows, None without one: its version's links; per location of ours the parents the game
    gives it, by name; holds: whether each list has that location's own parent in our records (None when that
    parent's id is not known: the system location needs plan.json); ancestors: whether the probe location's list
    goes past its own parent (None when unknown); and (problems, notes)."""
    if chain is None:
        return None, [], []
    problems, notes = [], []
    out = {"links": {k: chain.get(k) for k in CHAIN_LINKS if k in chain}}
    for k, v in out["links"].items():
        if v is False:
            problems.append(f"chain: {k} is false")
    if any(k in chain for k in CHAIN_V1):
        notes.append("chain: this log's script (version 1) asked IsChild the wrong way round (the child about its "
                     "parent), so " + " and ".join(k for k in CHAIN_V1 if k in chain) + " are no evidence either way")
    lists = [(key, whose, parent) for key, whose, parent in PARENT_LISTS if isinstance(chain.get(key), list)]
    if lists:
        out["parents"], out["holds"] = {}, {}
    for key, whose, parent in lists:
        got = chain[key]
        out["parents"][whose] = [p if isinstance(p, str) else name_of(p, names) for p in got]
        want = ids_named(names, parent)
        held = any(f in got for f in want) if want else None
        out["holds"][f"{whose} under {parent}"] = held
        if held is False:
            problems.append(f"chain: {parent} is not among {whose}'s parents")
    if isinstance(chain.get("probe_parents"), list):
        above = ids_named(names, "our planet location") + ids_named(names, "the system location")
        out["ancestors"] = any(f in chain["probe_parents"] for f in above) if above else None
    return out, problems, notes


def ref_verdict(r):
    if r.get("installed") is False:
        return "not installed"
    found = r.get("found")
    if found is False:
        return "not loaded"
    if found is True:
        same = r.get("sameworld")
        if same is True and r.get("world") is not None:
            return "with player"
        if same is False:
            return "left behind"
    return "unknown"


def local_positions(plan):
    """{tag: (x, y, z)} of the references' positions in their plugins (plan.json)."""
    out = {}
    for r in (plan or {}).get("refs", []):
        out[r["tag"]] = tuple(r["pos"])
    m = (plan or {}).get("merge") or {}
    if m.get("local"):
        out["MERGE"] = tuple(m["local"])
    c = (plan or {}).get("lc172_coc") or {}
    if c.get("local"):
        out["LC172COC"] = tuple(c["local"])
    return out


def summarize(lines, plan=None, run=-1):
    """The chosen run (default the last) as a JSON-ready summary: init, chain, and per arrival the player's world and
    planet and each reference's verdict at its last reading."""
    rs = runs(lines)
    if not rs:
        return {"runs": 0, "arrivals": [], "problems": ["no FO4SFPP line in the log"]}
    lines_ = rs[run]
    init = next((p for p in lines_ if p["event"] == "init"), None)
    chain = next((p for p in lines_ if p["event"] == "chain"), None)
    names = known_names(plan, init)
    reading, chain_problems, notes = chain_reading(chain, names)
    local = local_positions(plan)
    arrivals = {}
    order = []
    for p in lines_:
        if p["event"] == "arrive":
            n = p.get("n")
            arrivals[n] = {"n": n, "rt": p["rt"], "world": name_of(p.get("world"), names),
                           "world_id": hexid(p.get("world")), "cell_id": hexid(p.get("cell")),
                           "pos": [p.get("x"), p.get("y"), p.get("z")], "probeworld": p.get("probeworld"),
                           "readings": [], "player": None, "planet": None, "refs": {}, "location": None}
            order.append(n)
            continue
        n = p.get("n")
        if n not in arrivals:
            continue
        a = arrivals[n]
        if p["event"] == "player":
            a["readings"].append(p.get("at"))
            a["player"] = {"at": p.get("at"), "world": name_of(p.get("world"), names), "world_id": hexid(p.get("world")),
                           "planet": name_of(p.get("planet"), names), "planet_id": hexid(p.get("planet")),
                           "loc": name_of(p.get("loc"), names), "pos": [p.get("x"), p.get("y"), p.get("z")],
                           "ourplanet": p.get("ourplanet"), "probeloc": p.get("probeloc"),
                           "probeworld": p.get("probeworld")}
        elif p["event"] == "planet":
            a["planet"] = {k: p.get(k) for k in ("at", "gravity", "day", "temp", "pressure")}
            a["planet"].update(id=hexid(p.get("id")), type=hexid(p.get("type")), atmos=hexid(p.get("atmos")),
                               loc=name_of(p.get("loc"), names))
        elif p["event"] == "ref":
            tag = p.get("tag")
            if not isinstance(tag, str):                     # a cut line: nothing to file it under
                continue
            v = ref_verdict(p)
            r = {"at": p.get("at"), "verdict": v, "plugin": p.get("plugin"), "local_id": p.get("local")}
            if p.get("found") is True:
                pos = (p.get("x"), p.get("y"), p.get("z"))
                r.update(id=hexid(p.get("id")), world=name_of(p.get("world"), names), world_id=hexid(p.get("world")),
                         loc=name_of(p.get("loc"), names), editorloc=name_of(p.get("editorloc"), names),
                         pos=list(pos), dist=p.get("dist"), loaded=p.get("loaded"), disabled=p.get("disabled"),
                         actor=p.get("actor"))
                if tag in local and all(isinstance(v, float) for v in pos[:2]):
                    r["offset"] = [round(pos[0] - local[tag][0], 2) + 0.0, round(pos[1] - local[tag][1], 2) + 0.0]
            a["refs"][tag] = r
        elif p["event"] == "location":
            a["location"] = {"at": p.get("at"), "loaded": p.get("loaded"), "actors": p.get("actors")}
    out_arrivals = []
    for n in order:
        a = arrivals[n]
        pl = a["player"] or {}
        a["complete"] = all(t in a["readings"] for t in READINGS)
        ours = pl.get("ourplanet") is True or a["probeworld"] is True or pl.get("probeworld") is True
        a["kind"] = "our planet" if ours else pl.get("planet", "unknown")
        out_arrivals.append(a)
    problems = []
    if init is None:
        problems.append("no init line in this run (the log lost its start)")
    elif init.get("world") is None or init.get("planet") is None:
        problems.append("init: the probe world or our planet was not found by GetFormFromFile")
    problems += chain_problems
    if not any(a["kind"] == "our planet" for a in out_arrivals):
        problems.append("no arrival on our planet")
    return {"runs": len(rs), "run": run if run >= 0 else len(rs) + run, "load_index": load_index(init),
            "init": init, "chain": chain, "chain_reading": reading, "arrivals": out_arrivals, "problems": problems,
            "notes": notes}


def verdict_table(summary, tags=None):
    """Lines of a plain text table: one row per reference, one column per arrival (its verdict and offset)."""
    arr = summary.get("arrivals", [])
    if not arr:
        return ["no arrivals"]
    tags = tags or sorted({t for a in arr for t in a["refs"]}, key=lambda t: (not t.startswith("T"), t))
    head = ["tag"] + [f"#{a['n']} {a['kind']}" for a in arr]
    rows = [head]
    for t in tags:
        row = [t]
        for a in arr:
            r = a["refs"].get(t)
            if r is None:
                row.append("-")
                continue
            cell = r["verdict"]
            if r.get("offset") is not None:
                cell += f" ({r['offset'][0]:g}, {r['offset'][1]:g})"
            if isinstance(r.get("dist"), float) and r["dist"] < OTHER_WORLD_M:     # 3.4e38: another worldspace
                cell += f" {r['dist']:.0f} m"
            row.append(cell)
        rows.append(row)
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    return ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
