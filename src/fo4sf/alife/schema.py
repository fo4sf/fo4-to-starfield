"""A-Life modder config: load, strict validation, normalization and the writer payload.

A config is one JSON object (schema_version 1) that describes a whole A-Life mod for ONE exterior worldspace,
vanilla or custom:

  schema_version  1
  mod_name        free text, 1..64 characters
  plugin_name     the plugin to build, e.g. "StarfieldALife.esm" (.esm/.esp/.esl, no path)
  light_master    bool: ask the writer for a small (light) master when the record count fits
  masters         ["Starfield.esm", ...]: Starfield.esm first; the writer keeps only the referenced ones
  editor_prefix   optional EditorID prefix (default: the plugin stem's letters and digits)
  worldspace      {plugin, form_id, editor_id, merge_offset_xy [x, y]}
  simulation      {default_enabled, tick_real_s, offline_step_m_per_s, online_spawn_radius_m (450),
                   offline_despawn_radius_m (620), waymarker_pool_size 4..16, max_active_squads 1..16,
                   respawn_cooldown_s, show_notifications}
  factions        1..8 x {id, index, name, npc_template {plugin, form_id}, player_relation ally|neutral|enemy,
                   relations {other_id: ally|neutral|enemy}, squad_size 1..8, combat_power}
  nodes           2..128 x {index, id, kind relay|base|checkpoint|lair|resource, x, y, z, capacity,
                   initial_owner, spawn_faction}
  edges           1..128 x {u, v, len_m}

FormIDs are hex strings local to their plugin ("0x0001251B", "1251B", or an xEdit load-order id whose top byte is
stripped). Positions are worldspace-local metres; the runtime adds merge_offset_xy. Relations flatten into
FactionRelationsFlat[a * F + b] (1 ally, 0 neutral, -1 enemy, diagonal 1), the int arrays the Papyrus runtime
(FO4SF_ALifeSimQuest) and the Mutagen writer (dotnet/ALifeMod) consume.

usage:
  python -m fo4sf.alife.schema validate <config.json>
  python -m fo4sf.alife.schema export <config.json> <payload.json>
exit 0 valid, 2 invalid (one problem per line on stderr).
"""
import copy
import json
import math
import os
import re
import sys

SCHEMA_VERSION = 1
PAYLOAD_VERSION = 1
ARRAY_CAP = 128                      # a Papyrus array holds at most 128 elements
MAX_FACTIONS, MAX_SQUAD_SIZE = 8, 8
MIN_POOL, MAX_POOL = 4, 16
MAX_SQUADS = 16
MAX_CAPACITY = 16
HYSTERESIS_M = 50.0                  # offline_despawn_radius_m must exceed online_spawn_radius_m by more than this
MIN_ROAD_RATIO = 0.75                # an edge may be shorter than the straight line only by this much (re-spotted
                                     # nodes keep their extracted road length, e.g. nw_subgraph's map-marker spots)
BASE_MASTER = "Starfield.esm"
NODE_KINDS = {"relay": 0, "base": 1, "checkpoint": 2, "lair": 3, "resource": 4}
RELATIONS = {"ally": 1, "neutral": 0, "enemy": -1}
SIM_DEFAULTS = {
    "default_enabled": True,
    "tick_real_s": 2.0,
    "offline_step_m_per_s": 1.35,
    "online_spawn_radius_m": 450.0,
    "offline_despawn_radius_m": 620.0,
    "waymarker_pool_size": 8,
    "max_active_squads": 8,
    "respawn_cooldown_s": 120.0,
    "show_notifications": True,
}
TOP_KEYS = {"schema_version", "mod_name", "plugin_name", "light_master", "masters", "editor_prefix", "worldspace",
            "simulation", "factions", "nodes", "edges", "description", "author", "version", "$schema",
            # derived keys of an exported writer payload: accepted (so a payload re-validates) and recomputed
            "payload_version", "waymarker_pool_size", "globals", "properties"}
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")
PRESETS = ("vanilla_new_atlantis", "fo4sf_commonwealth")

_PLUGIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-.]{0,59}\.(esm|esp|esl)$", re.I)
_FORMID_RE = re.compile(r"^(0[xX])?([0-9A-Fa-f]{1,8})$")
_EDID_RE = re.compile(r"^[A-Za-z0-9_]{1,96}$")
_PREFIX_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,23}$")
_FACTION_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")


class AlifeConfigError(ValueError):
    """An invalid config; .problems lists every reason."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("invalid A-Life config:\n  " + "\n  ".join(self.problems))


# ------------------------------------------------------------------------------------------------ small checks
def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_form_id(value, plugin=None):
    """'0x%06X' local FormID of a hex string, or raise ValueError. An 8-digit id's top (load-order) byte is
    dropped; the local id must be non-zero, and below Starfield.esm a plugin's own ids start at 0x800."""
    if not isinstance(value, str):
        raise ValueError(f"form_id {value!r} must be a hex string")
    m = _FORMID_RE.match(value.strip())
    if not m:
        raise ValueError(f"form_id {value!r} is not 1..8 hex digits")
    local = int(m.group(2), 16) & 0xFFFFFF
    if local == 0:
        raise ValueError(f"form_id {value!r} is a null id")
    if plugin is not None and plugin.lower() != BASE_MASTER.lower() and local < 0x800:
        raise ValueError(f"form_id {value!r}: ids below 0x800 are reserved to {BASE_MASTER}, not {plugin}")
    return f"0x{local:06X}"


def path_basename(path):
    """Cross-OS file name of a Windows drive, UNC, POSIX, or mixed-separator path string."""
    s = str(path).rstrip("\\/")
    if not s:
        return ""
    m_unc = re.match(r"^(?:\\\\|//)[^\\/]+[\\/][^\\/]+(.*)$", s)
    if m_unc is not None:
        s = m_unc.group(1).lstrip("\\/")
        return re.split(r"[\\/]+", s)[-1] if s else ""
    if len(s) >= 2 and s[0].isascii() and s[0].isalpha() and s[1] == ":":
        s = s[2:].lstrip("\\/")
        return re.split(r"[\\/]+", s)[-1] if s else ""
    s = s.lstrip("\\/")
    return re.split(r"[\\/]+", s)[-1] if s else ""


def default_prefix(plugin_name):
    stem = os.path.splitext(path_basename(plugin_name))[0]
    p = "".join(ch for ch in stem if ch.isascii() and ch.isalnum())
    if not p:
        return "ALife"
    if not p[0].isalpha():
        p = "M" + p
    return p[:24]


def camel(slug):
    return "".join(part[:1].upper() + part[1:] for part in str(slug).split("_") if part)


def xy_dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


# ------------------------------------------------------------------------------------------------ loading
def load_alife_config(path):
    """The config at path (or a deep copy of a dict) with simulation defaults filled in. Raises AlifeConfigError
    only when the input is not a readable JSON object; call validate_alife_config for everything else. Keys that
    start with "_" (comments) are ignored at every depth by validation and dropped from the normalized config."""
    if isinstance(path, dict):
        raw = copy.deepcopy(path)
    else:
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise AlifeConfigError([f"{path_basename(path)}: {e}"]) from None
    if not isinstance(raw, dict):
        raise AlifeConfigError([f"{path_basename(path)}: the top level is not a JSON object"])
    sim = raw.get("simulation")
    if sim is None:
        raw["simulation"] = dict(SIM_DEFAULTS)
    elif isinstance(sim, dict):
        for k, v in SIM_DEFAULTS.items():
            sim.setdefault(k, v)
    return raw


def preset_path(name):
    if name not in PRESETS:
        raise KeyError(f"unknown preset {name!r}; presets: {', '.join(PRESETS)}")
    return os.path.join(PRESETS_DIR, name + ".json")


def load_preset(name):
    return load_alife_config(preset_path(name))


def template_config():
    """A fresh, valid starting config to edit (a deep copy of the vanilla New Atlantis preset)."""
    return copy.deepcopy(load_preset("vanilla_new_atlantis"))


# ------------------------------------------------------------------------------------------------ validation
def _faction_ref(v, ids, n_factions):
    """Faction index of an owner/spawn reference (int index, faction id string, None or -1), or raise."""
    if v is None:
        return -1
    if _is_int(v):
        if v == -1 or 0 <= v < n_factions:
            return v
        raise ValueError(f"faction index {v} is not -1 or 0..{n_factions - 1}")
    if isinstance(v, str):
        if v in ids:
            return ids[v]
        raise ValueError(f"unknown faction id {v!r}")
    raise ValueError(f"faction reference {v!r} is not an index, a faction id or null")


def _plugin(v, where, problems):
    if not isinstance(v, str) or not _PLUGIN_RE.match(v):
        problems.append(f"{where}: {v!r} is not a plugin file name (.esm/.esp/.esl, no path)")
        return None
    return v


def normalize_alife_config(cfg):
    """(normalized config, problems). The normalized config keeps the raw field names with every default filled:
    form ids '0x%06X', owner/spawn references as faction indices (-1 none), node/edge references as node indices,
    relations completed for every other faction, masters reduced to Starfield.esm plus the referenced plugins."""
    problems = []
    P = problems.append
    if not isinstance(cfg, dict):
        return None, ["the config is not a JSON object"]
    out = {}
    for k in cfg:
        if k not in TOP_KEYS and not str(k).startswith("_"):
            P(f"unknown top-level key {k!r}")
    if cfg.get("schema_version") != SCHEMA_VERSION or isinstance(cfg.get("schema_version"), bool):
        P(f"schema_version must be {SCHEMA_VERSION}, not {cfg.get('schema_version')!r}")
    out["schema_version"] = SCHEMA_VERSION
    name = cfg.get("mod_name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
        P("mod_name must be 1..64 characters")
    out["mod_name"] = name if isinstance(name, str) else ""
    plugin_name = _plugin(cfg.get("plugin_name"), "plugin_name", problems)
    if plugin_name and plugin_name.lower() == BASE_MASTER.lower():
        P(f"plugin_name cannot be {BASE_MASTER}")
    out["plugin_name"] = plugin_name or ""
    light = cfg.get("light_master", False)
    if not isinstance(light, bool):
        P("light_master must be true or false")
    out["light_master"] = bool(light) if isinstance(light, bool) else False
    prefix = cfg.get("editor_prefix")
    if prefix is None:
        prefix = default_prefix(out["plugin_name"])
    elif not isinstance(prefix, str) or not _PREFIX_RE.match(prefix):
        P(f"editor_prefix {prefix!r}: a letter then up to 23 letters/digits")
        prefix = default_prefix(out["plugin_name"])
    out["editor_prefix"] = prefix

    # masters
    masters = cfg.get("masters")
    master_set = {}
    if not isinstance(masters, list) or not masters:
        P(f"masters must be a non-empty list starting with {BASE_MASTER}")
        masters = [BASE_MASTER]
    for i, m in enumerate(masters):
        m = _plugin(m, f"masters[{i}]", problems)
        if m is None:
            continue
        if m.lower() in master_set:
            P(f"masters[{i}]: {m} listed twice")
        master_set.setdefault(m.lower(), m)
    if not masters or not isinstance(masters[0], str) or masters[0].lower() != BASE_MASTER.lower():
        P(f"masters[0] must be {BASE_MASTER}")
    if plugin_name and plugin_name.lower() in master_set:
        P(f"{plugin_name} cannot be its own master")
    referenced = {BASE_MASTER.lower()}

    def ref_plugin(v, where):
        p = _plugin(v, where, problems)
        if p is None:
            return ""
        if p.lower() not in master_set and p.lower() != BASE_MASTER.lower():
            P(f"{where}: {p} is not in masters")
        if plugin_name and p.lower() == plugin_name.lower():
            P(f"{where}: a template or worldspace cannot come from {plugin_name} itself")
        referenced.add(p.lower())
        return master_set.get(p.lower(), p)

    def ref_form(v, plugin, where):
        try:
            return parse_form_id(v, plugin or None)
        except ValueError as e:
            P(f"{where}: {e}")
            return ""

    # worldspace
    ws = cfg.get("worldspace")
    nws = {"plugin": "", "form_id": "", "editor_id": "", "merge_offset_xy": [0.0, 0.0]}
    if not isinstance(ws, dict):
        P("worldspace must be an object {plugin, form_id, editor_id, merge_offset_xy}")
    else:
        for k in ws:
            if k not in nws and not str(k).startswith("_"):
                P(f"worldspace: unknown key {k!r}")
        nws["plugin"] = ref_plugin(ws.get("plugin"), "worldspace.plugin")
        nws["form_id"] = ref_form(ws.get("form_id"), nws["plugin"], "worldspace.form_id")
        edid = ws.get("editor_id")
        if not isinstance(edid, str) or not _EDID_RE.match(edid):
            P(f"worldspace.editor_id {edid!r} is not an EditorID")
        else:
            nws["editor_id"] = edid
        off = ws.get("merge_offset_xy", [0.0, 0.0])
        if not (isinstance(off, list) and len(off) == 2 and all(_is_num(v) for v in off)):
            P("worldspace.merge_offset_xy must be [x, y] finite numbers")
        else:
            nws["merge_offset_xy"] = [float(off[0]), float(off[1])]
    out["worldspace"] = nws

    # simulation
    sim = cfg.get("simulation", {})
    nsim = dict(SIM_DEFAULTS)
    if not isinstance(sim, dict):
        P("simulation must be an object")
        sim = {}
    for k in sim:
        if k not in SIM_DEFAULTS and not str(k).startswith("_"):
            P(f"simulation: unknown key {k!r}")
    for k, d in SIM_DEFAULTS.items():
        v = sim.get(k, d)
        if isinstance(d, bool):
            if not isinstance(v, bool):
                P(f"simulation.{k} must be true or false")
                continue
        elif isinstance(d, int):
            if not _is_int(v):
                P(f"simulation.{k} must be an integer")
                continue
        elif not _is_num(v):
            P(f"simulation.{k} must be a finite number")
            continue
        else:
            v = float(v)
        nsim[k] = v
    ranges = {"tick_real_s": (0.25, 60.0), "offline_step_m_per_s": (0.05, 50.0),
              "online_spawn_radius_m": (25.0, 5000.0), "offline_despawn_radius_m": (25.0, 10000.0),
              "respawn_cooldown_s": (0.0, 86400.0), "waymarker_pool_size": (MIN_POOL, MAX_POOL),
              "max_active_squads": (1, MAX_SQUADS)}
    for k, (lo, hi) in ranges.items():
        if not lo <= nsim[k] <= hi:
            P(f"simulation.{k} {nsim[k]} is outside {lo}..{hi}")
    if not nsim["offline_despawn_radius_m"] > nsim["online_spawn_radius_m"] + HYSTERESIS_M:
        P(f"simulation: offline_despawn_radius_m {nsim['offline_despawn_radius_m']} must exceed "
          f"online_spawn_radius_m {nsim['online_spawn_radius_m']} + {HYSTERESIS_M:g} (hysteresis)")
    out["simulation"] = nsim

    # factions
    facs = cfg.get("factions")
    nfacs = []
    if not isinstance(facs, list) or not 1 <= len(facs) <= MAX_FACTIONS:
        P(f"factions must be a list of 1..{MAX_FACTIONS} entries")
        facs = facs if isinstance(facs, list) else []
        facs = facs[:MAX_FACTIONS * 4]
    ids = {}
    for i, f in enumerate(facs):
        if isinstance(f, dict) and isinstance(f.get("id"), str):
            if f["id"] in ids:
                P(f"factions[{i}]: id {f['id']!r} is used twice")
            ids.setdefault(f["id"], i)
    F = len(facs)
    fkeys = {"id", "index", "name", "npc_template", "player_relation", "relations", "squad_size", "combat_power",
             "editor_id", "player_reaction"}                 # the last two: payload-derived, recomputed
    for i, f in enumerate(facs):
        w = f"factions[{i}]"
        if not isinstance(f, dict):
            P(f"{w} is not an object")
            nfacs.append(None)
            continue
        for k in f:
            if k not in fkeys and not str(k).startswith("_"):
                P(f"{w}: unknown key {k!r}")
        fid = f.get("id")
        if not isinstance(fid, str) or not _FACTION_ID_RE.match(fid):
            P(f"{w}.id {fid!r}: lower-case letter then up to 23 of a-z, 0-9, _")
            fid = f"faction{i}"
        if f.get("index", i) != i or isinstance(f.get("index"), bool):
            P(f"{w}.index must be {i} (its position in the list)")
        fname = f.get("name")
        if not isinstance(fname, str) or not 1 <= len(fname.strip()) <= 64:
            P(f"{w}.name must be 1..64 characters")
            fname = fid
        tpl = f.get("npc_template")
        ntpl = {"plugin": "", "form_id": ""}
        if not isinstance(tpl, dict):
            P(f"{w}.npc_template must be an object {{plugin, form_id}}")
        else:
            ntpl["plugin"] = ref_plugin(tpl.get("plugin"), f"{w}.npc_template.plugin")
            ntpl["form_id"] = ref_form(tpl.get("form_id"), ntpl["plugin"], f"{w}.npc_template.form_id")
            if "editor_id" in tpl:
                if isinstance(tpl["editor_id"], str) and _EDID_RE.match(tpl["editor_id"]):
                    ntpl["editor_id"] = tpl["editor_id"]
                else:
                    P(f"{w}.npc_template.editor_id {tpl['editor_id']!r} is not an EditorID")
        pr = f.get("player_relation")
        if pr not in RELATIONS:
            P(f"{w}.player_relation {pr!r}: one of {', '.join(RELATIONS)}")
            pr = "neutral"
        size = f.get("squad_size")
        if not _is_int(size) or not 1 <= size <= MAX_SQUAD_SIZE:
            P(f"{w}.squad_size must be an integer 1..{MAX_SQUAD_SIZE}")
            size = 1
        power = f.get("combat_power")
        if not _is_num(power) or not 0 < power <= 100:
            P(f"{w}.combat_power must be a number in (0, 100]")
            power = 1.0
        rel = f.get("relations", {})
        if not isinstance(rel, dict):
            P(f"{w}.relations must be an object {{faction_id: ally|neutral|enemy}}")
            rel = {}
        rel = {k: v for k, v in rel.items() if not str(k).startswith("_")}
        for k, v in rel.items():
            if k not in ids:
                P(f"{w}.relations: unknown faction id {k!r}")
            elif k == fid:
                P(f"{w}.relations: a faction has no relation to itself")
            if v not in RELATIONS:
                P(f"{w}.relations[{k!r}] {v!r}: one of {', '.join(RELATIONS)}")
        nfacs.append({"id": fid, "index": i, "name": fname, "editor_id": f"{prefix}_Faction_{camel(fid)}",
                      "npc_template": ntpl, "player_relation": pr, "player_reaction": RELATIONS[pr],
                      "relations": {k: v for k, v in rel.items() if k in ids and k != fid and v in RELATIONS},
                      "squad_size": size, "combat_power": float(power)})
    # complete and symmetrize relations
    valid = [f for f in nfacs if f is not None]
    for a in valid:
        for b in valid:
            if a is b:
                continue
            ab, ba = a["relations"].get(b["id"]), b["relations"].get(a["id"])
            if ab is not None and ba is not None and ab != ba:
                P(f"factions {a['id']} and {b['id']}: relations disagree ({ab} vs {ba})")
    for a in valid:
        full = {}
        for b in valid:
            if a is b:
                continue
            full[b["id"]] = a["relations"].get(b["id"]) or b["relations"].get(a["id"]) or "neutral"
        a["relations"] = full
    out["factions"] = nfacs

    # nodes
    nodes = cfg.get("nodes")
    nnodes = []
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= ARRAY_CAP:
        P(f"nodes must be a list of 2..{ARRAY_CAP} entries (one Papyrus array each)")
        nodes = nodes if isinstance(nodes, list) else []
    node_ids = {}
    nkeys = {"index", "id", "kind", "x", "y", "z", "capacity", "initial_owner", "spawn_faction"}
    for i, n in enumerate(nodes):
        w = f"nodes[{i}]"
        if not isinstance(n, dict):
            P(f"{w} is not an object")
            nnodes.append(None)
            continue
        for k in n:
            if k not in nkeys and not str(k).startswith("_"):
                P(f"{w}: unknown key {k!r}")
        nid = n.get("id")
        if not isinstance(nid, str) or not _NODE_ID_RE.match(nid):
            P(f"{w}.id {nid!r}: 1..64 of letters, digits, _ . : -")
            nid = f"node{i}"
        if nid in node_ids:
            P(f"{w}.id {nid!r} is used twice")
        node_ids.setdefault(nid, i)
        if n.get("index", i) != i or isinstance(n.get("index"), bool):
            P(f"{w}.index must be {i} (its position in the list)")
        kind = n.get("kind")
        if kind not in NODE_KINDS:
            P(f"{w}.kind {kind!r}: one of {', '.join(NODE_KINDS)}")
            kind = "relay"
        pos = {}
        for k in ("x", "y", "z"):
            if not _is_num(n.get(k)):
                P(f"{w}.{k} must be a finite number")
                pos[k] = 0.0
            else:
                pos[k] = float(n[k])
        cap = n.get("capacity", 0 if kind == "relay" else None)
        if not _is_int(cap) or not 0 <= cap <= MAX_CAPACITY:
            P(f"{w}.capacity must be an integer 0..{MAX_CAPACITY}")
            cap = 0
        elif kind == "relay" and cap != 0:
            P(f"{w}: a relay node has capacity 0 (squads pass through, never garrison)")
        elif kind != "relay" and cap == 0:
            P(f"{w}: a {kind} node needs capacity >= 1 (use kind relay for pass-through)")
        try:
            spawn = _faction_ref(n.get("spawn_faction"), ids, F)
        except ValueError as e:
            P(f"{w}.spawn_faction: {e}")
            spawn = -1
        try:
            owner = _faction_ref(n.get("initial_owner", spawn if "initial_owner" not in n else None), ids, F)
        except ValueError as e:
            P(f"{w}.initial_owner: {e}")
            owner = -1
        if kind == "relay" and (owner >= 0 or spawn >= 0):
            P(f"{w}: a relay node cannot be owned or spawn squads")
        if spawn >= 0 and cap <= 0:
            P(f"{w}: a spawn base needs capacity >= 1")
        nnodes.append({"index": i, "id": nid, "kind": kind, **pos, "capacity": cap, "initial_owner": owner,
                       "spawn_faction": spawn})
    out["nodes"] = nnodes
    N = len(nnodes)
    for f in valid:
        if not any(nd and nd["spawn_faction"] >= 0 and nd["initial_owner"] == f["index"] for nd in nnodes):
            P(f"faction {f['id']} owns no spawn base (initial_owner == it and spawn_faction set); it would never "
              "spawn")
    if nnodes and not any(nd and nd["capacity"] > 0 for nd in nnodes):
        P("no node can garrison a squad (every capacity is 0)")

    # edges
    edges = cfg.get("edges")
    nedges = []
    if not isinstance(edges, list) or not 1 <= len(edges) <= ARRAY_CAP:
        P(f"edges must be a list of 1..{ARRAY_CAP} entries (one Papyrus array each)")
        edges = edges if isinstance(edges, list) else []
    seen = {}

    def node_ref(v, where):
        if _is_int(v) and 0 <= v < N:
            return v
        if isinstance(v, str) and v in node_ids:
            return node_ids[v]
        P(f"{where} {v!r} is not a node index 0..{N - 1} or node id")
        return None

    for i, e in enumerate(edges):
        w = f"edges[{i}]"
        if not isinstance(e, dict):
            P(f"{w} is not an object")
            continue
        for k in e:
            if k not in ("u", "v", "len_m") and not str(k).startswith("_"):
                P(f"{w}: unknown key {k!r}")
        u, v = node_ref(e.get("u"), f"{w}.u"), node_ref(e.get("v"), f"{w}.v")
        if u is None or v is None:
            continue
        if u == v:
            P(f"{w} joins node {u} to itself")
            continue
        key = (min(u, v), max(u, v))
        if key in seen:
            P(f"{w} duplicates edges[{seen[key]}] ({key[0]}-{key[1]})")
            continue
        seen[key] = i
        a, b = nnodes[u], nnodes[v]
        straight = xy_dist(a, b) if a and b else 0.0
        length = e.get("len_m")
        if length is None:
            length = round(math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"])), 2) if a and b else 1.0
        if not _is_num(length) or length <= 0:
            P(f"{w}.len_m must be a positive finite number")
            continue
        if length < straight * MIN_ROAD_RATIO - 1.0:
            P(f"{w}.len_m {length} is far shorter than the straight-line distance {straight:.2f} m")
        nedges.append({"u": u, "v": v, "len_m": float(length)})
    out["edges"] = nedges
    if N >= 2 and nedges and all(nnodes):
        reach = connected_from(N, nedges, 0)
        if len(reach) != N:
            lost = sorted(set(range(N)) - reach)
            P(f"the graph is not connected: nodes {lost[:12]}{' ...' if len(lost) > 12 else ''} are unreachable "
              "from node 0")
    # masters actually needed, config order
    out["masters"] = [m for m in (masters if isinstance(masters, list) else [])
                      if isinstance(m, str) and m.lower() in referenced]
    if not out["masters"] or out["masters"][0].lower() != BASE_MASTER.lower():
        out["masters"] = [BASE_MASTER] + [m for m in out["masters"] if m.lower() != BASE_MASTER.lower()]
    return out, problems


def connected_from(n, edges, src):
    adj = [[] for _ in range(n)]
    for e in edges:
        adj[e["u"]].append(e["v"])
        adj[e["v"]].append(e["u"])
    seen, stack = {src}, [src]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return seen


def validate_alife_config(cfg):
    """Every reason the config cannot be built (empty list: it can)."""
    try:
        return normalize_alife_config(cfg)[1]
    except Exception as e:                          # a validator never raises on bad input
        return [f"validator error: {type(e).__name__}: {e}"]


def checked(cfg):
    """The normalized config, or raise AlifeConfigError."""
    norm, problems = normalize_alife_config(cfg)
    if problems:
        raise AlifeConfigError(problems)
    return norm


def relations_flat(norm):
    facs = norm["factions"]
    flat = []
    for a in facs:
        for b in facs:
            flat.append(1 if a is b else RELATIONS[a["relations"][b["id"]]])
    return flat


def export_writer_payload(cfg):
    """The JSON payload for dotnet/ALifeMod and the Papyrus runtime: the normalized config (raw field names) plus
    "properties" (the flat FO4SF_ALifeSimQuest arrays and scalars) and "globals" (GLOB start values).
    Raises AlifeConfigError when the config is invalid."""
    norm = checked(cfg)
    sim, nodes, edges, facs = norm["simulation"], norm["nodes"], norm["edges"], norm["factions"]
    props = {
        "FactionSquadSize": [f["squad_size"] for f in facs],
        "FactionPower": [f["combat_power"] for f in facs],
        "FactionRelationsFlat": relations_flat(norm),
        "NodeX": [n["x"] for n in nodes],
        "NodeY": [n["y"] for n in nodes],
        "NodeZ": [n["z"] for n in nodes],
        "NodeCap": [n["capacity"] for n in nodes],
        "NodeKind": [NODE_KINDS[n["kind"]] for n in nodes],
        "NodeInitialOwner": [n["initial_owner"] for n in nodes],
        "NodeSpawnFaction": [n["spawn_faction"] for n in nodes],
        "EdgeU": [e["u"] for e in edges],
        "EdgeV": [e["v"] for e in edges],
        "EdgeLen": [e["len_m"] for e in edges],
        "MergeOffsetX": norm["worldspace"]["merge_offset_xy"][0],
        "MergeOffsetY": norm["worldspace"]["merge_offset_xy"][1],
        "OnlineSpawnRadiusM": sim["online_spawn_radius_m"],
        "OfflineDespawnRadiusM": sim["offline_despawn_radius_m"],
        "OfflineSpeedMps": sim["offline_step_m_per_s"],
        "TickIntervalS": sim["tick_real_s"],
        "MaxActiveSquads": sim["max_active_squads"],
        "RespawnCooldownS": sim["respawn_cooldown_s"],
    }
    for k, v in props.items():
        if isinstance(v, list) and len(v) > ARRAY_CAP:
            raise AlifeConfigError([f"{k} has {len(v)} elements, more than a Papyrus array holds"])
    payload = dict(norm)
    payload["payload_version"] = PAYLOAD_VERSION
    payload["waymarker_pool_size"] = sim["waymarker_pool_size"]
    payload["globals"] = {"SimEnabled": 1.0 if sim["default_enabled"] else 0.0,
                          "OnlineRadius": float(sim["online_spawn_radius_m"]),
                          "MaxSquads": float(sim["max_active_squads"]),
                          "Notifications": 1.0 if sim["show_notifications"] else 0.0}
    payload["properties"] = props
    return payload


# ------------------------------------------------------------------------------------------------ CLI
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] not in ("validate", "export") or (argv[0] == "export" and len(argv) != 3):
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    try:
        cfg = load_alife_config(argv[1])
    except AlifeConfigError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 2
    problems = validate_alife_config(cfg)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    if argv[0] == "validate":
        norm = checked(cfg)
        print(f"valid: {norm['mod_name']} -> {norm['plugin_name']}: {len(norm['factions'])} factions, "
              f"{len(norm['nodes'])} nodes, {len(norm['edges'])} edges; masters {', '.join(norm['masters'])}")
        return 0
    payload = export_writer_payload(cfg)
    with open(argv[2], "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=1)
        f.write("\n")
    print(f"wrote {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
