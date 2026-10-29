"""The planet probe's user log (FO4SFPlanetProbe.0.log, written by scripts/planet/FO4SF_PlanetProbeQuest.psc) read
back into arrivals, readings and a verdict per test reference (docs/planet/planet-probe.md section 5).

Every line the script writes holds "FO4SFPP rt=<real time s> <event> key=value ...", anywhere in the line (the game
puts a time stamp in front). Values: form ids as Papyrus prints them (signed decimal, so a load index of 0x80 or more
and the runtime FF ids are negative), floats, True / False, and "none" for a None form. Events: init (once per new
script instance: the quest's own id gives the probe plugin's load index), chain (the location chain as the game
resolves it), arrive, then player / planet / ref / location lines at 2, 10, 30 and 60 s after each arrival.

The verdict a reference gets at an arrival, from its last reading there:
  with player   found, in the player's worldspace (sameworld=True)
  left behind   found, in another worldspace (for ours: the base probe world the game never plays)
  not loaded    GetFormFromFile returned None: a temporary reference whose cell is not loaded, or a missing record
  not installed its plugin is not loaded
The offset is the reference's position minus its position in the plugin (plan.json "refs" / "merge"): (0, 0) is a
reference where the plugin put it; a merged reference moves with its world (LC172World's COC marker moved by about
(-500, -2300) on 11 Oct).
"""
import re

LINE = re.compile(r"FO4SFPP rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$")
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "chain", "arrive", "player", "planet", "ref", "location")
ID_KEYS = {"quest", "world", "loc", "planet", "surface", "planetloc", "cell", "id", "editorloc", "type", "atmos",
           "probe_planet", "surface_planet", "planet_location"}
READINGS = (2, 10, 30, 60)


def u32(v):
    """A form id as Papyrus printed it (signed decimal) as the unsigned 32-bit id, None for none."""
    return None if v is None else int(v) & 0xFFFFFFFF


def value(key, text):
    if text == "none":
        return None
    if text in ("True", "False"):
        return text == "True"
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
    if not m or m.group("event") not in EVENTS:
        return None
    out = {"rt": float(m.group("rt")), "event": m.group("event")}
    for k, v in TOKEN.findall(m.group("rest")):
        out[k] = value(k, v)
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
    return names


def ref_verdict(r):
    if r.get("installed") is False:
        return "not installed"
    if r.get("found") is not True:
        return "not loaded"
    return "with player" if r.get("sameworld") else "left behind"


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
            v = ref_verdict(p)
            r = {"at": p.get("at"), "verdict": v, "plugin": p.get("plugin"), "local_id": p.get("local")}
            if p.get("found"):
                pos = (p.get("x"), p.get("y"), p.get("z"))
                r.update(id=hexid(p.get("id")), world=name_of(p.get("world"), names), world_id=hexid(p.get("world")),
                         loc=name_of(p.get("loc"), names), editorloc=name_of(p.get("editorloc"), names),
                         pos=list(pos), dist=p.get("dist"), loaded=p.get("loaded"), disabled=p.get("disabled"),
                         actor=p.get("actor"))
                if tag in local and None not in pos[:2]:
                    r["offset"] = [round(pos[0] - local[tag][0], 2), round(pos[1] - local[tag][1], 2)]
            a["refs"][tag] = r
        elif p["event"] == "location":
            a["location"] = {"at": p.get("at"), "loaded": p.get("loaded"), "actors": p.get("actors")}
    out_arrivals = []
    for n in order:
        a = arrivals[n]
        pl = a["player"] or {}
        a["complete"] = all(t in a["readings"] for t in READINGS)
        a["kind"] = ("our planet" if pl.get("ourplanet") or a["probeworld"] or pl.get("probeworld")
                     else pl.get("planet", "unknown"))
        out_arrivals.append(a)
    problems = []
    if init is None:
        problems.append("no init line in this run (the log lost its start)")
    elif init.get("world") is None or init.get("planet") is None:
        problems.append("init: the probe world or our planet was not found by GetFormFromFile")
    if chain is not None:
        for k in ("probe_child_of_surface", "surface_child_of_planet"):
            if chain.get(k) is False:
                problems.append(f"chain: {k} is False")
    if not any(a["kind"] == "our planet" for a in out_arrivals):
        problems.append("no arrival on our planet")
    return {"runs": len(rs), "run": run if run >= 0 else len(rs) + run, "load_index": load_index(init),
            "init": init, "chain": chain, "arrivals": out_arrivals, "problems": problems}


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
            if r.get("dist") is not None:
                cell += f" {r['dist']:.0f} m"
            row.append(cell)
        rows.append(row)
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    return ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
