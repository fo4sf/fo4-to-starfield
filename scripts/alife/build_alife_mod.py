r"""Standalone Starfield A-Life mod builder: scaffold, validate, simulate, package, verify and audit a modder's
alife_config.json (docs/alife/MODDER-GUIDE.md).

usage:
  python build_alife_mod.py init --out <alife_config.json> [--template vanilla|custom] [--force]
      writes a starter config: `vanilla` copies the Starfield.esm-only preset (src/fo4sf/alife/presets), `custom`
      re-targets it at a placeholder custom worldspace plugin you then edit. Keys starting with "_" are comments.
  python build_alife_mod.py validate --config <alife_config.json> [--json]
      the schema validator's verdict plus graph connectivity, node/edge headroom (N/128), node kinds, the faction
      relation matrix and the plugin's master dependencies. Exit 0 only when the config is valid.
  python build_alife_mod.py simulate --config <alife_config.json> [--ticks 1000] [--seed 42] [--json-out <file>]
      the deterministic offline simulator (fo4sf.alife.sim_math): squads spawned, edges traversed, offline battles,
      captures per faction and garrison utilization, as an ASCII table. Never touches the game.
  python build_alife_mod.py package --config <cfg> --out <dist dir> --starfield-dir <Starfield folder>
                                    [--extra-data-dir <dir>] [--pack-ba2]
      refuses an --out inside any Git worktree or any game installation folder, or one that exists. Exports the
      writer payload, runs dotnet/ALifeMod build + check, compiles the three A-Life scripts with the game's
      PapyrusCompiler.exe against Tools/ContentResources.zip, optionally packs Data/Scripts into
      "<PluginStem> - Main.ba2" with Archive2.exe, and writes Data/<plugin>, Data/Scripts/*.pex (or the .ba2),
      Plugins.txt.snippet, README-MOD.txt, alife_config.json and manifest.sha256.json into <out>.partial-<time>-<pid>,
      renamed to <out> only when every step passed (a failed attempt is kept for inspection). The game folder is
      only read. With FO4SF_STARFIELD set, --starfield-dir defaults to it.
  python build_alife_mod.py verify-dist --dist-dir <dist dir> [--json]
      every manifest SHA-256 and size, no unlisted files, the plugin's TES4 header (Master flag, master list), the
      three scripts present (loose .pex or inside the .ba2) and the Plugins.txt snippet. Exit 0 only when all pass.
  python build_alife_mod.py log-audit --file <StarfieldALife.0.log> [--json]
      the runtime's `ALIFE_MOD rt=<t> step=<event> key=value ...` user-log lines counted independently of its own
      summaries: spawns, 3D materializations, offline dematerializations, battles, captures per faction, errors.
      Exit 0 only when the log holds A-Life lines, an init, and no error lines.
Nothing here starts the game or writes into its folder.
"""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(REPO, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
PROJECT = os.path.join(REPO, "dotnet", "ALifeMod")
PRESETS = os.path.join(SRC, "fo4sf", "alife", "presets")
SCRIPTS = ("FO4SF_ALifeSimQuest", "FO4SF_ALifeAPI", "FO4SF_ALifeBeaconEffect")
ARRAY_CAP = 128
NODE_KINDS = ("relay", "base", "checkpoint", "lair", "resource")
BASE_MASTER = "starfield.esm"
MANIFEST = "manifest.sha256.json"
MANIFEST_KIND = "alife-mod-dist"
SNIPPET = "Plugins.txt.snippet"
README = "README-MOD.txt"
CONFIG_COPY = "alife_config.json"
PEX_MAGIC = b"\xde\xc0\x57\xfa"          # 0xFA57C0DE little-endian
BA2_MAGIC = b"BTDX"
TES4_MASTER, TES4_SMALL = 0x1, 0x100
GAME_EXES = {"starfield.exe", "fallout4.exe", "skyrimse.exe", "fallout76.exe", "skyrim.exe", "oblivion.exe"}
GAME_PATH_PARTS = {"steamapps", "xboxgames", "windowsapps"}
LOG_LINE = re.compile(r"ALIFE_MOD rt=(?P<rt>[-\d.]+) step=(?P<step>\w+)(?P<rest>.*)$")
_UNC_PATH_RE = re.compile(r"(?<![:\w])(?:\\\\|//)[^\s\"'<>|/\\]+[\\/][^\s\"'<>|/\\]+(?:[\\/][^\s\"'<>|]*)?")
_WIN_PATH_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/][^\s\"'<>|]*")
_POSIX_PATH_RE = re.compile(r"(?<![\w.\\/])/(?:[^\s\"'<>|/\\]+[\\/])+[^\s\"'<>|/\\]*[\\/]*")


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


class Refused(Exception):
    """A request the packager will not carry out (message says why)."""


# ---------------------------------------------------------------- schema bridge

def _schema():
    try:
        from fo4sf.alife import schema
    except ImportError as e:            # pragma: no cover - only when the SDK package is missing
        raise Refused(f"fo4sf.alife.schema is not importable from {os.path.relpath(SRC, REPO)}: {e}")
    return schema


def _sim():
    try:
        from fo4sf.alife import sim_math
    except ImportError as e:            # pragma: no cover
        raise Refused(f"fo4sf.alife.sim_math is not importable: {e}")
    return sim_math


def strip_comments(obj):
    """The config without its "_" comment keys (at any depth)."""
    if isinstance(obj, dict):
        return {k: strip_comments(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [strip_comments(v) for v in obj]
    return obj


def read_config(path):
    """The config through the schema loader (comment keys removed first, so a commented starter loads)."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise Refused(f"{path}: {e}")
    return read_config_obj(raw, path)


def read_config_obj(raw, path=None):
    """A raw config dict through the schema loader: a loader that takes a dict gets the comment-free dict; one that
    takes only a path gets the original file (no comments) or a comment-free temporary copy."""
    schema = _schema()
    clean = strip_comments(raw)
    loader = getattr(schema, "load_alife_config", None)
    if loader is None:
        return clean
    try:
        try:
            return loader(clean)
        except (TypeError, AttributeError, OSError):
            pass
        if path and clean == raw:
            return loader(path)
    except ValueError as e:             # the schema's AlifeConfigError: not a readable config object
        raise Refused(str(e))
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="alife_cfg_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean, f)
        return loader(tmp)
    finally:
        os.remove(tmp)


def as_dict(cfg):
    """A plain dict view of a loaded config (the loader may return a dataclass)."""
    if isinstance(cfg, dict):
        return cfg
    for name in ("to_dict", "as_dict", "asdict"):
        fn = getattr(cfg, name, None)
        if callable(fn):
            return fn()
    import dataclasses
    if dataclasses.is_dataclass(cfg):
        return dataclasses.asdict(cfg)
    return dict(vars(cfg))


def validation_problems(cfg):
    """The schema validator's problems (empty: valid). Accepts a validator that returns a list, a (ok, problems)
    pair or None, or raises ValueError."""
    schema = _schema()
    try:
        res = schema.validate_alife_config(cfg)
    except ValueError as e:
        return [str(e)]
    if res is None or res is True:
        return []
    if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], bool):
        return [] if res[0] else [str(p) for p in (res[1] or ["invalid"])]
    if isinstance(res, dict):
        return [str(p) for p in res.get("problems", res.get("errors", []))]
    return [str(p) for p in res]


def writer_payload(cfg):
    return _schema().export_writer_payload(cfg)


# ---------------------------------------------------------------- config facts (independent of the schema module)

def _idx_map(nodes):
    m = {}
    for i, n in enumerate(nodes):
        m[i] = i
        if isinstance(n, dict):
            if "index" in n:
                m[n["index"]] = i
            if "id" in n:
                m[str(n["id"])] = i
    return m


def graph_facts(c):
    """Node/edge counts, headroom, connected components, degree range and node kinds of a config dict."""
    nodes, edges = c.get("nodes", []), c.get("edges", [])
    idx = _idx_map(nodes)
    adj = {i: set() for i in range(len(nodes))}
    bad = []
    for k, e in enumerate(edges):
        u, v = idx.get(e.get("u")), idx.get(e.get("v"))
        if u is None or v is None or u == v:
            bad.append(k)
            continue
        adj[u].add(v)
        adj[v].add(u)
    seen, comps = set(), []
    for s in range(len(nodes)):
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        comps.append(sorted(comp))
    kinds = {}
    for n in nodes:
        kinds[n.get("kind", "?")] = kinds.get(n.get("kind", "?"), 0) + 1
    deg = [len(adj[i]) for i in adj]
    total_len = sum(float(e.get("len_m", 0) or 0) for e in edges)
    return {"nodes": len(nodes), "edges": len(edges), "node_cap": ARRAY_CAP, "edge_cap": ARRAY_CAP,
            "node_headroom": ARRAY_CAP - len(nodes), "edge_headroom": ARRAY_CAP - len(edges),
            "components": len(comps), "connected": len(comps) == 1 and bool(nodes),
            "isolated": [nodes[c[0]].get("id", c[0]) for c in comps if len(c) == 1] if len(comps) > 1 else [],
            "bad_edges": bad, "degree_min": min(deg, default=0), "degree_max": max(deg, default=0),
            "kinds": kinds, "total_edge_m": round(total_len, 1),
            "garrison_capacity": sum(int(n.get("capacity", 0) or 0) for n in nodes)}


def faction_matrix(c):
    """(ids, rows): rows[i][j] in {"ally", "neutral", "enemy", "self"} from each faction's relations dict;
    unspecified pairs are neutral. Also each faction's player relation."""
    facs = sorted(c.get("factions", []), key=lambda f: f.get("index", 0))
    ids = [str(f.get("id")) for f in facs]
    rel_of = {str(f.get("id")): (f.get("relations", {}) or {}) for f in facs}
    rows = []
    for f in facs:
        me = str(f.get("id"))
        row = []
        for g in ids:          # a pair stated on one side only holds both ways (the schema symmetrizes)
            row.append("self" if g == me else
                       str(rel_of[me].get(g) or rel_of.get(g, {}).get(me) or "neutral").lower())
        rows.append(row)
    return ids, rows, {str(f.get("id")): str(f.get("player_relation", "neutral")) for f in facs}


def _plugin_of(ref):
    if isinstance(ref, dict):
        return ref.get("plugin")
    return None


def referenced_plugins(c):
    """Plugins the config's records reference: the worldspace and every faction's NPC template."""
    out = []
    for p in [_plugin_of(c.get("worldspace"))] + [_plugin_of(f.get("npc_template")) for f in c.get("factions", [])]:
        if p and p.lower() not in [o.lower() for o in out]:
            out.append(p)
    return out


def master_facts(c):
    """Declared masters, referenced plugins, the masters the writer should emit (Starfield.esm first, then the
    referenced plugins in declared order) and any referenced plugin the config does not declare."""
    declared = list(c.get("masters", []) or [])
    refs = referenced_plugins(c)
    lower_decl = [d.lower() for d in declared]
    undeclared = [r for r in refs if r.lower() not in lower_decl]
    expected = ["Starfield.esm"]
    for d in declared + refs:
        if d.lower() not in [e.lower() for e in expected] and d.lower() in [r.lower() for r in refs]:
            expected.append(d)
    unused = [d for d in declared if d.lower() != BASE_MASTER and d.lower() not in [r.lower() for r in refs]]
    return {"declared": declared, "referenced": refs, "expected": expected, "undeclared": undeclared,
            "unused_declared": unused, "standalone": [e.lower() for e in expected] == [BASE_MASTER]}


# ---------------------------------------------------------------- ascii tables

def table(headers, rows):
    cols = [[str(h)] + [str(r[i]) for r in rows] for i, h in enumerate(headers)]
    w = [max(len(x) for x in col) for col in cols]
    sep = "+" + "+".join("-" * (n + 2) for n in w) + "+"

    def line(vals):
        return "| " + " | ".join(str(v).rjust(w[i]) if _numeric(v) else str(v).ljust(w[i])
                                 for i, v in enumerate(vals)) + " |"
    out = [sep, line(headers), sep] + [line(r) for r in rows] + [sep]
    return "\n".join(out)


def _numeric(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    return bool(re.fullmatch(r"-?[\d.,]+%?", str(v)))


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 10 else f"{v:,.1f}"
    if isinstance(v, (list, tuple)):
        return ",".join(str(x) for x in v) if len(v) <= 8 else f"[{len(v)} items]"
    if isinstance(v, dict):
        return f"{{{len(v)} keys}}"
    return str(v)


# ---------------------------------------------------------------- init

def _load_preset(name):
    path = os.path.join(PRESETS, name)
    if not os.path.isfile(path):
        raise Refused(f"preset {os.path.relpath(path, REPO)} is missing")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def starter_config(template):
    """The starter config dict for `init` (comments under "_" keys)."""
    base = strip_comments(_load_preset("vanilla_new_atlantis.json"))
    cfg = copy.deepcopy(base)
    if template == "custom":
        cfg["mod_name"] = "My A-Life Mod"
        cfg["plugin_name"] = "MyALifeMod.esm"
        ws = dict(cfg.get("worldspace", {}))
        ws.update({"plugin": "MyWorldspace.esm", "form_id": "000800", "editor_id": "MyWorldspace",
                   "merge_offset_xy": [0.0, 0.0]})
        cfg["worldspace"] = ws
        masters = [m for m in cfg.get("masters", ["Starfield.esm"])]
        if "MyWorldspace.esm" not in masters:
            masters.append("MyWorldspace.esm")
        cfg["masters"] = masters
    comments = {
        "_comment": "A-Life mod config (docs/alife/MODDER-GUIDE.md has every field). Keys starting with _ are "
                    "comments and are ignored. Workflow: validate -> simulate -> package.",
        "_worldspace": "plugin/form_id/editor_id of the exterior WRLD the squads live in. merge_offset_xy is added "
                       "to every node x/y (metres) to get in-game world coordinates; 0,0 for vanilla worlds.",
        "_simulation": "online_spawn_radius_m (450) materializes squads near the player; offline_despawn_radius_m "
                       "(620) must exceed it by more than 50 m. waymarker_pool_size 4..16, max_active_squads 1..16.",
        "_factions": "1..8 factions. npc_template is the NPC_ cloned for squad members; relations maps other "
                     "faction ids to ally|neutral|enemy; player_relation is how they treat the player.",
        "_nodes": "2..128 smart terrains, kind relay|base|checkpoint|lair|resource. spawn_faction >= 0 makes a "
                  "node spawn squads; capacity 0 never garrisons (relay).",
        "_edges": "1..128 undirected edges between node indices, len_m metres along the walkable route.",
    }
    if template == "custom":
        comments["_custom"] = ("Replace MyWorldspace.esm, form_id, editor_id and every node position with your "
                               "world's values, and keep it in masters.")
    out = dict(comments)
    out.update(cfg)
    return out


def cmd_init(a):
    out = os.path.abspath(a.out)
    if os.path.exists(out) and not a.force:
        raise Refused(f"{out} exists (use --force to overwrite)")
    cfg = starter_config(a.template)
    problems = validation_problems(read_config_obj(cfg))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    c = strip_comments(cfg)
    print(f"wrote {out}: template {a.template}, {len(c.get('nodes', []))} nodes, {len(c.get('edges', []))} edges, "
          f"{len(c.get('factions', []))} factions, plugin {c.get('plugin_name')}")
    if problems:
        print("note: the starter needs editing before it validates:")
        for p in problems:
            print("  - " + p)
    print("next: build_alife_mod.py validate --config " + path_basename(out))
    return 0


# ---------------------------------------------------------------- validate

def _spawns(node):
    """Whether a node spawns squads: spawn_faction a faction index >= 0 or a faction id string."""
    v = node.get("spawn_faction")
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v >= 0
    return str(v).strip().lower() not in ("", "-1", "none", "null")


def validate_report(path):
    cfg = read_config(path)
    problems = validation_problems(cfg)
    c = as_dict(cfg)
    g = graph_facts(c)
    ids, rows, player = faction_matrix(c)
    m = master_facts(c)
    warnings = []
    if m["undeclared"]:
        warnings.append(f"referenced but not in masters: {m['undeclared']}")
    if m["unused_declared"]:
        warnings.append(f"declared masters no record references (the writer omits them): {m['unused_declared']}")
    if not g["connected"]:
        warnings.append(f"graph has {g['components']} components")
    spawners = [n for n in c.get("nodes", []) if _spawns(n)]
    if not spawners:
        warnings.append("no node has spawn_faction >= 0: no squad will ever spawn")
    return {"config": path_basename(path), "valid": not problems, "problems": problems, "warnings": warnings,
            "mod_name": c.get("mod_name"), "plugin_name": c.get("plugin_name"),
            "light_master": bool(c.get("light_master")), "worldspace": c.get("worldspace"),
            "graph": g, "factions": ids, "relations": rows, "player_relation": player, "masters": m,
            "spawn_nodes": len(spawners)}


def cmd_validate(a):
    rep = validate_report(a.config)
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
        return 0 if rep["valid"] else 1
    g, m = rep["graph"], rep["masters"]
    ws = rep["worldspace"] or {}
    print(f"A-Life config {rep['config']}: {rep['mod_name']} -> {rep['plugin_name']}"
          f"{' (light master)' if rep['light_master'] else ''}")
    print(f"worldspace {ws.get('editor_id')} {ws.get('plugin')}:{ws.get('form_id')} "
          f"merge_offset_xy={ws.get('merge_offset_xy')}")
    print(table(["graph", "value"], [
        ["nodes", f"{g['nodes']}/{ARRAY_CAP} ({g['node_headroom']} free)"],
        ["edges", f"{g['edges']}/{ARRAY_CAP} ({g['edge_headroom']} free)"],
        ["connected", f"{'yes' if g['connected'] else 'NO'} ({g['components']} component(s))"],
        ["degree min..max", f"{g['degree_min']}..{g['degree_max']}"],
        ["total edge length m", g["total_edge_m"]],
        ["garrison capacity", g["garrison_capacity"]],
        ["spawn nodes", rep["spawn_nodes"]],
        ["node kinds", ", ".join(f"{k}={v}" for k, v in sorted(g["kinds"].items()))],
    ]))
    if rep["factions"]:
        print("faction relations (row treats column):")
        print(table(["faction", "player"] + rep["factions"],
                    [[f, rep["player_relation"].get(f, "?")] + r for f, r in zip(rep["factions"], rep["relations"])]))
    print(f"masters the plugin will carry: {m['expected']}"
          f"{'  (standalone: Starfield.esm only)' if m['standalone'] else ''}")
    for w in rep["warnings"]:
        print("WARN  " + w)
    for p in rep["problems"]:
        print("FAIL  " + p)
    print("validate: ok" if rep["valid"] else f"validate: {len(rep['problems'])} problem(s)")
    return 0 if rep["valid"] else 1


# ---------------------------------------------------------------- simulate

def run_simulation(cfg, ticks, seed):
    sim = _sim()
    for name in ("simulate", "run_simulation", "run"):
        fn = getattr(sim, name, None)
        if callable(fn):
            break
    else:
        raise Refused("fo4sf.alife.sim_math has no simulate()/run_simulation()/run()")
    try:
        res = fn(cfg, ticks=ticks, seed=seed)
    except TypeError:
        res = fn(cfg, ticks, seed)
    if not isinstance(res, dict):
        res = as_dict(res)
    return res


def _first(res, *keys, default=None):
    for k in keys:
        if k in res:
            return res[k]
    return default


def cmd_simulate(a):
    cfg = read_config(a.config)
    problems = validation_problems(cfg)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        raise Refused(f"{a.config} is not valid; fix it before simulating")
    t0 = time.perf_counter()
    res = run_simulation(cfg, a.ticks, a.seed)
    ms = (time.perf_counter() - t0) * 1000.0
    c = as_dict(cfg)
    captures = _first(res, "captures", "captures_by_faction", default={}) or {}
    total_caps = sum(captures.values()) if isinstance(captures, dict) else captures
    util = _first(res, "garrison_utilization", "garrison_util", default=None)
    summary = [
        ["ticks", _first(res, "ticks", default=a.ticks)],
        ["seed", _first(res, "seed", default=a.seed)],
        ["squads spawned", _first(res, "squads_spawned", "spawned", default="?")],
        ["edges traversed", _first(res, "edges_traversed", "edge_traversals", default="?")],
        ["offline battles", _first(res, "battles", "battles_fought", "offline_battles", default="?")],
        ["territory captures", total_caps],
        ["garrison utilization", f"{util * 100:.1f}%" if isinstance(util, (int, float)) else _fmt(util)],
        ["wall time ms", f"{ms:.1f}"],
    ]
    known = {"ticks", "seed", "squads_spawned", "spawned", "edges_traversed", "edge_traversals", "battles",
             "battles_fought", "offline_battles", "captures", "captures_by_faction", "garrison_utilization",
             "garrison_util", "per_faction", "factions", "events", "timeline", "node_owner", "final_owners"}
    for k, v in res.items():
        if k not in known and not isinstance(v, (list, dict)):
            summary.append([k.replace("_", " "), _fmt(v)])
    print(f"A-Life offline simulation: {c.get('mod_name')} ({len(c.get('nodes', []))} nodes, "
          f"{len(c.get('edges', []))} edges, {len(c.get('factions', []))} factions)")
    print(table(["metric", "value"], summary))
    per = _first(res, "per_faction", "factions", default=None)
    if isinstance(per, dict) and per and all(isinstance(v, dict) for v in per.values()):
        cols = []
        for v in per.values():
            for k in v:
                if k not in cols and not isinstance(v[k], (list, dict)):
                    cols.append(k)
        rows = []
        for fid, v in per.items():
            row = [fid] + [_fmt(v.get(k, "")) for k in cols]
            if "captures" not in cols and isinstance(captures, dict):
                row.append(captures.get(fid, 0))
            rows.append(row)
        hdr = ["faction"] + [k.replace("_", " ") for k in cols]
        if "captures" not in cols and isinstance(captures, dict):
            hdr.append("captures")
        print(table(hdr, rows))
    elif isinstance(captures, dict) and captures:
        print(table(["faction", "captures"], [[k, v] for k, v in captures.items()]))
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=1, default=str)
            f.write("\n")
        print(f"wrote {a.json_out}")
    return 0


# ---------------------------------------------------------------- refusal guard

def _ancestors(path):
    p = os.path.abspath(path)
    out = [p]
    while True:
        q = os.path.dirname(p)
        if q == p:
            return out
        out.append(q)
        p = q


def _inside(path, root):
    try:
        path, root = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(root))
        return os.path.commonpath([path, root]) == root
    except ValueError:                  # different drives
        return False


def git_root_of(path):
    """The nearest ancestor holding .git (a folder or a worktree's .git file), or None."""
    for anc in _ancestors(path):
        if os.path.exists(os.path.join(anc, ".git")):
            return anc
    return None


def game_root_of(path, starfield_dir=None):
    """The game installation folder `path` lies in (or None): the given Starfield folder, an ancestor holding a game
    executable or Data/Starfield.esm, or a store library folder (steamapps, XboxGames, WindowsApps)."""
    if starfield_dir and _inside(path, starfield_dir):
        return os.path.abspath(starfield_dir)
    for anc in _ancestors(path):
        if os.path.basename(anc).lower() in GAME_PATH_PARTS:
            return anc
        if os.path.isdir(anc):
            try:
                names = {n.lower() for n in os.listdir(anc)}
            except OSError:
                continue
            if names & GAME_EXES or os.path.isfile(os.path.join(anc, "Data", "Starfield.esm")):
                return anc
    return None


def refuse_out(out, starfield_dir=None):
    """Raises Refused when `out` (or its .partial sibling) would land in a Git worktree, a game folder, or exists."""
    out = os.path.abspath(out)
    g = git_root_of(out)
    if g:
        raise Refused(f"--out {out} is inside the Git worktree {g}: package outside any repository")
    if _inside(out, REPO):
        raise Refused(f"--out {out} is inside this repository")
    game = game_root_of(out, starfield_dir)
    if game:
        raise Refused(f"--out {out} is inside the game installation {game}: never write into a game folder")
    if os.path.exists(out):
        raise Refused(f"--out {out} exists: package into a new folder")


# ---------------------------------------------------------------- hashing, plugin and pex readers

def scrub_paths(text):
    """`text` with every absolute Windows, UNC, or POSIX path cut to its file name (the manifest is shipped publicly)."""
    rep = lambda m: path_basename(m.group(0)) or "<path>"
    text = _UNC_PATH_RE.sub(rep, text)
    text = _WIN_PATH_RE.sub(rep, text)
    return _POSIX_PATH_RE.sub(rep, text)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_tes4(path):
    """The plugin header: {"flags", "masters", "hedr_records"}; raises ValueError for a non-TES4 file."""
    with open(path, "rb") as f:
        head = f.read(24)
        if len(head) < 24 or head[:4] != b"TES4":
            raise ValueError(f"{path_basename(path)}: not a TES4 plugin")
        size, flags = struct.unpack_from("<II", head, 4)
        data = f.read(size)
    if len(data) != size:
        raise ValueError(f"{path_basename(path)}: truncated TES4 header")
    masters, records, pos, big = [], None, 0, None
    while pos + 6 <= len(data):
        sig, n = data[pos:pos + 4], struct.unpack_from("<H", data, pos + 4)[0]
        pos += 6
        if big is not None:
            n, big = big, None
        body = data[pos:pos + n]
        pos += n
        if sig == b"XXXX":
            big = struct.unpack_from("<I", body)[0]
        elif sig == b"MAST":
            masters.append(body.split(b"\0", 1)[0].decode("utf-8", "replace"))
        elif sig == b"HEDR" and len(body) >= 8:
            records = struct.unpack_from("<I", body, 4)[0]
    return {"flags": flags, "masters": masters, "hedr_records": records,
            "master_flag": bool(flags & TES4_MASTER), "small_flag": bool(flags & TES4_SMALL)}


def is_pex(path):
    with open(path, "rb") as f:
        return f.read(4) == PEX_MAGIC


def ba2_names(path):
    """Lower-cased forward-slash entry names of a General BA2."""
    from fo4sf import ba2
    arc = ba2.Ba2(path)
    names = getattr(arc, "names", None) or [e.name for e in arc.entries]
    return {n.replace("\\", "/").lower() for n in names}


# ---------------------------------------------------------------- package

def run(cmd, cwd=None, log=None, timeout=900):
    shown = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
    print("+ " + shown, flush=True)
    tool_name = path_basename(str(cmd[0]))
    try:                                # no console input: a tool that waits for a key must fail, not hang
        r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, errors="replace",
                           stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Refused(f"{tool_name} did not finish within {timeout} s")
    if log is not None:                 # the manifest records tools and plain arguments only, never machine paths
        words = [str(c) for c in cmd[1:] if not re.search(r"[\\/:]", str(c))]
        log.append({"tool": tool_name, "args": words, "rc": r.returncode})
    if r.returncode != 0:
        sys.stdout.write((r.stdout or "")[-4000:])
        sys.stdout.write((r.stderr or "")[-4000:])
        raise Refused(f"{tool_name} exited {r.returncode}")
    return r.stdout or ""


def new_partial(final):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    base = f"{final}.partial-{stamp}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    os.makedirs(out)
    return out


def extract_sources(zip_path, work):
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        raise Refused(f"{path_basename(zip_path)}: no Scripts/Source base scripts or flags file")
    return src


def compile_scripts(compiler, src_dir, out_dir, log):
    os.makedirs(out_dir, exist_ok=True)
    pex = []
    for s in SCRIPTS:
        if not os.path.isfile(os.path.join(HERE, s + ".psc")):
            raise Refused(f"scripts/alife/{s}.psc is missing")
        out = run([compiler, s + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}",
                   f"-o={out_dir}"], cwd=HERE, log=log)
        p = os.path.join(out_dir, s + ".pex")
        if "Compilation succeeded" not in out or not os.path.isfile(p) or not is_pex(p):
            raise Refused(f"the Papyrus compile did not produce {s}.pex")
        pex.append(p)
    return pex


def find_master(name, starfield_dir, extra_dir):
    """A master by file name: the extra data folder (its root or Data/) first, then the game's Data folder."""
    cands = []
    if extra_dir:
        cands += [os.path.join(extra_dir, name), os.path.join(extra_dir, "Data", name)]
    cands.append(os.path.join(starfield_dir, "Data", name))
    for p in cands:
        if os.path.isfile(p):
            return p
    raise Refused(f"master {name} not found in --extra-data-dir or the game's Data folder")


def pack_ba2(archive2, pex_files, stem, work, dest_data, log):
    root = os.path.join(work, "ba2root")
    scripts = os.path.join(root, "Scripts")
    os.makedirs(scripts, exist_ok=True)
    for p in pex_files:
        shutil.copy2(p, scripts)
    ba2 = os.path.join(dest_data, f"{stem} - Main.ba2")
    run([archive2, "Scripts", f"-create={ba2}", f"-root={root}", "-format=General", "-compression=None"],
        cwd=root, log=log)
    names = ba2_names(ba2)
    want = {f"scripts/{path_basename(p).lower()}" for p in pex_files}
    if names != want:
        raise Refused(f"{path_basename(ba2)} entries {sorted(names)} differ from {sorted(want)}")
    return ba2


def readme_text(c, info):
    masters = ", ".join(info["masters"])
    content = (f"Data/{info['ba2']}   (holds Scripts/*.pex)" if info["ba2"] else
               "Data/Scripts/" + ", Data/Scripts/".join(s + ".pex" for s in SCRIPTS))
    extra = "" if info["standalone"] else (
        "\nThis build also requires these plugins, loaded before it: "
        + ", ".join(m for m in info["masters"] if m.lower() != BASE_MASTER) + ".\n")
    loose = ("The scripts are inside the .ba2, so no ini change is needed." if info["ba2"] else
             "Loose scripts: the game reads loose Data/Scripts only with StarfieldCustom.ini [Archive]\n"
             "  bInvalidateOlderFiles=1 and sResourceDataDirsFinal= (or rebuild with --pack-ba2).")
    return f"""{c.get('mod_name')} - a Starfield A-Life mod
Built {info['built']} by build_alife_mod.py (FO4SF A-Life Modder SDK).

Files
  Data/{info['plugin']}          the plugin (masters: {masters})
  {content}
  {SNIPPET}           the line to add to Plugins.txt
  {CONFIG_COPY}             the A-Life config this build came from
  {MANIFEST}       SHA-256 of every file (check: build_alife_mod.py verify-dist)
{extra}
Install
  Mod manager (MO2 / Vortex): install this archive as a mod and enable {info['plugin']}.
  Manual: copy the contents of Data into the game's Data folder, then add the line from {SNIPPET} to
  Plugins.txt (%LOCALAPPDATA%\\Starfield\\Plugins.txt; the leading * enables the plugin).
  {loose}

Play
  Squads ({len(c.get('factions', []))} factions, {len(c.get('nodes', []))} smart terrains) simulate offline on the
  world graph and appear in 3D within {info['online_m']:.0f} m of you, returning offline beyond {info['offline_m']:.0f} m.
  Settings -> Gameplay holds the A-Life options (enabled, maximum squads, notifications).
  The Field Transponder aid item reports the nearest squad and territory status.
  Log (when Papyrus user logging is on): Documents/My Games/Starfield/Logs/Script/User/StarfieldALife.0.log

Uninstall
  Disable A-Life in Settings -> Gameplay and save before removing the plugin; scripted mods leave data in saves.
"""


def cmd_package(a):
    starfield = os.path.abspath(a.starfield_dir) if a.starfield_dir else None
    if not starfield:
        raise Refused("--starfield-dir is required (or set FO4SF_STARFIELD)")
    final = os.path.abspath(a.out)
    refuse_out(final, starfield)
    sf_esm = os.path.join(starfield, "Data", "Starfield.esm")
    compiler = a.compiler or os.path.join(starfield, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe")
    zip_path = os.path.join(starfield, "Tools", "ContentResources.zip")
    archive2 = a.archive2 or os.path.join(starfield, "Tools", "Archive2", "Archive2.exe")
    need = [sf_esm, compiler, zip_path] + ([archive2] if a.pack_ba2 else [])
    missing = [p for p in need if not os.path.isfile(p)]
    if missing:
        raise Refused(f"missing tool or master: {missing}")
    if a.extra_data_dir and not os.path.isdir(a.extra_data_dir):
        raise Refused(f"--extra-data-dir {a.extra_data_dir} is not a folder")
    cfg = read_config(a.config)
    problems = validation_problems(cfg)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        raise Refused(f"{a.config} is not valid; run validate")
    c = as_dict(cfg)
    m = master_facts(c)
    if m["undeclared"]:
        raise Refused(f"plugins referenced but not declared in masters: {m['undeclared']}")
    plugin = c.get("plugin_name") or "StarfieldALife.esm"
    if re.search(r"[\\/:]", plugin) or path_basename(plugin) != plugin or \
            not plugin.lower().endswith((".esm", ".esp", ".esl")):
        raise Refused(f"plugin_name {plugin!r} must be a bare .esm/.esp/.esl file name")
    stem = os.path.splitext(plugin)[0]
    extra_masters = {n: find_master(n, starfield, a.extra_data_dir) for n in m["expected"]
                     if n.lower() != BASE_MASTER}
    pinned = {"Starfield.esm": sha256(sf_esm)}
    pinned.update({n: sha256(p) for n, p in extra_masters.items()})
    out = new_partial(final)
    try:
        return _build_into(out, final, a, cfg, c, m, plugin, stem, sf_esm, compiler, zip_path, archive2, extra_masters, pinned)
    except (Refused, OSError, ValueError) as ex:
        msg = str(ex)
        raise Refused(msg if "attempt kept in" in msg else f"{msg} (attempt kept in {out})")


def _build_into(out, final, a, cfg, c, m, plugin, stem, sf_esm, compiler, zip_path, archive2, extra_masters, pinned):
    """package's build steps inside the .partial folder `out`; renamed to `final` when all passed."""
    log = []
    print(f"building into {out}")
    work = os.path.join(out, "_work")
    data = os.path.join(out, "Data")
    os.makedirs(work)
    os.makedirs(data)
    payload = writer_payload(cfg)
    payload_path = os.path.join(work, "payload.json")
    with open(payload_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=1, default=str)
    tool = [a.dotnet, "run", "-c", "Release", "--project", PROJECT, "--"]
    esm_dir = os.path.join(work, "esm")
    os.makedirs(esm_dir)
    build_cmd = tool + ["build", sf_esm, payload_path, esm_dir]
    for p in extra_masters.values():
        build_cmd += ["--extra-master", p]
    run(build_cmd, log=log)
    built = os.path.join(esm_dir, plugin)
    if not os.path.isfile(built):
        raise Refused(f"dotnet/ALifeMod build did not write {plugin} (attempt kept in {out})")
    check_cmd = tool + ["check", built, sf_esm, payload_path]
    for p in extra_masters.values():
        check_cmd += ["--extra-master", p]
    check_out = run(check_cmd, log=log)
    hdr = read_tes4(built)
    if not hdr["master_flag"]:
        raise Refused(f"{plugin} lacks the Master flag")
    want = [x.lower() for x in m["expected"]]
    if not hdr["masters"] or hdr["masters"][0].lower() != BASE_MASTER or \
            any(x.lower() not in want for x in hdr["masters"]):
        raise Refused(f"{plugin} masters {hdr['masters']} are not within {m['expected']}")
    shutil.copy2(built, os.path.join(data, plugin))
    src = extract_sources(zip_path, work)
    pex = compile_scripts(compiler, src, os.path.join(work, "pex"), log)
    ba2 = None
    if a.pack_ba2:
        ba2 = pack_ba2(archive2, pex, stem, work, data, log)
    else:
        os.makedirs(os.path.join(data, "Scripts"))
        for p in pex:
            shutil.copy2(p, os.path.join(data, "Scripts"))
    drift = [n for n, p in [("Starfield.esm", sf_esm)] + list(extra_masters.items()) if sha256(p) != pinned[n]]
    if drift:
        raise Refused(f"a master changed during the build ({drift}); attempt kept in {out}")
    sim = c.get("simulation", {}) or {}
    info = {"plugin": plugin, "masters": hdr["masters"], "standalone": [x.lower() for x in hdr["masters"]] ==
            [BASE_MASTER], "ba2": path_basename(ba2) if ba2 else None,
            "built": datetime.date.today().isoformat(),
            "online_m": float(sim.get("online_spawn_radius_m", 450.0)),
            "offline_m": float(sim.get("offline_despawn_radius_m", 620.0))}
    with open(os.path.join(out, SNIPPET), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"*{plugin}\n")
    with open(os.path.join(out, README), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(readme_text(c, info))
    shutil.copy2(a.config, os.path.join(out, CONFIG_COPY))
    shutil.rmtree(work)
    check_lines = [ln for ln in check_out.splitlines() if ln.strip()]
    write_manifest(out, {
        "mod_name": c.get("mod_name"), "plugin": plugin, "masters": hdr["masters"],
        "light_master": bool(c.get("light_master")), "plugin_flags": hdr["flags"],
        "scripts": list(SCRIPTS), "ba2": info["ba2"],
        "inputs": {"config_sha256": sha256(a.config), "masters_sha256": pinned,
                   "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, default=str)
                                                    .encode()).hexdigest()},
        "writer_check_tail": [scrub_paths(ln) for ln in check_lines[-5:]], "steps": log})
    problems = verify_dist(out)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        raise Refused(f"the packaged folder failed verify-dist; attempt kept in {out}")
    os.replace(out, final)
    print(f"packaged {final}: Data/{plugin} (masters {hdr['masters']}), "
          f"{info['ba2'] or 'Data/Scripts/*.pex'}, {SNIPPET}, {README}, {MANIFEST}; verify-dist ok")
    return 0


# ---------------------------------------------------------------- manifest, verify-dist

def _walk_files(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for n in sorted(fn):
            rel = os.path.relpath(os.path.join(dp, n), root).replace("\\", "/")
            if rel != MANIFEST:
                out.append(rel)
    return out


def write_manifest(dist, fields):
    """manifest.sha256.json for every file under `dist` (relative forward-slash paths, no machine paths)."""
    files = {rel: {"sha256": sha256(os.path.join(dist, rel)), "bytes": os.path.getsize(os.path.join(dist, rel))}
             for rel in _walk_files(dist)}
    man = {"kind": MANIFEST_KIND, "manifest_version": 1}
    man.update(fields)
    man["files"] = files
    with open(os.path.join(dist, MANIFEST), "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, indent=1, sort_keys=False)
        f.write("\n")
    return man


def verify_dist(dist):
    """Problems with a packaged folder (empty: it verifies)."""
    p = []
    mpath = os.path.join(dist, MANIFEST)
    if not os.path.isfile(mpath):
        return [f"{MANIFEST} missing"]
    try:
        with open(mpath, encoding="utf-8") as f:
            man = json.load(f)
    except ValueError as e:
        return [f"{MANIFEST} unreadable: {e}"]
    if man.get("kind") != MANIFEST_KIND:
        p.append(f"{MANIFEST} kind {man.get('kind')!r} is not {MANIFEST_KIND}")
    files = man.get("files") or {}
    for rel, want in sorted(files.items()):
        if rel.startswith(("/", "\\")) or ".." in rel.replace("\\", "/").split("/") or ":" in rel:
            p.append(f"{rel}: unsafe manifest path")
            continue
        path = os.path.join(dist, rel)
        if not os.path.isfile(path):
            p.append(f"{rel}: missing")
            continue
        if os.path.getsize(path) != want.get("bytes"):
            p.append(f"{rel}: {os.path.getsize(path)} bytes, manifest says {want.get('bytes')}")
        if sha256(path) != want.get("sha256"):
            p.append(f"{rel}: sha256 differs from the manifest")
    extra = [r for r in _walk_files(dist) if r not in files]
    if extra:
        p.append(f"files not in the manifest: {extra}")
    plugin = man.get("plugin")
    ppath = os.path.join(dist, "Data", plugin or "")
    if not plugin or not os.path.isfile(ppath):
        p.append(f"Data/{plugin}: plugin missing")
    else:
        try:
            hdr = read_tes4(ppath)
            if not hdr["master_flag"]:
                p.append(f"{plugin}: Master flag not set")
            if [x.lower() for x in hdr["masters"]] != [x.lower() for x in man.get("masters", [])]:
                p.append(f"{plugin}: masters {hdr['masters']} differ from the manifest {man.get('masters')}")
            if not hdr["masters"] or hdr["masters"][0].lower() != BASE_MASTER:
                p.append(f"{plugin}: first master is not Starfield.esm ({hdr['masters']})")
            if man.get("light_master") and not hdr["small_flag"]:
                p.append(f"{plugin}: light_master requested but the Small (0x100) flag is not set")
        except ValueError as e:
            p.append(str(e))
    scripts = man.get("scripts") or list(SCRIPTS)
    if man.get("ba2"):
        bpath = os.path.join(dist, "Data", man["ba2"])
        if not os.path.isfile(bpath):
            p.append(f"Data/{man['ba2']}: archive missing")
        else:
            with open(bpath, "rb") as f:
                magic = f.read(4)
            if magic != BA2_MAGIC:
                p.append(f"{man['ba2']}: not a BA2 archive")
            else:
                try:
                    names = ba2_names(bpath)
                    for s in scripts:
                        if f"scripts/{s.lower()}.pex" not in names:
                            p.append(f"{man['ba2']}: Scripts/{s}.pex missing")
                except Exception as e:  # noqa: BLE001 - any reader failure is a verify failure
                    p.append(f"{man['ba2']}: unreadable ({e})")
        stem = os.path.splitext(plugin or "")[0]
        if man["ba2"].lower() != f"{stem} - main.ba2".lower():
            p.append(f"{man['ba2']}: Starfield only loads '{stem} - Main.ba2' for {plugin}")
    else:
        for s in scripts:
            sp = os.path.join(dist, "Data", "Scripts", s + ".pex")
            if not os.path.isfile(sp):
                p.append(f"Data/Scripts/{s}.pex missing")
            elif not is_pex(sp):
                p.append(f"Data/Scripts/{s}.pex is not a compiled Papyrus script")
    snip = os.path.join(dist, SNIPPET)
    if not os.path.isfile(snip):
        p.append(f"{SNIPPET} missing")
    else:
        with open(snip, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if plugin and f"*{plugin}" not in lines:
            p.append(f"{SNIPPET} does not enable *{plugin}")
    return p


def cmd_verify_dist(a):
    problems = verify_dist(a.dist_dir)
    if a.json:
        print(json.dumps({"dist": path_basename(os.path.abspath(a.dist_dir)), "ok": not problems,
                          "problems": problems}, indent=1))
    else:
        for x in problems:
            print("FAIL  " + x)
        if not problems:
            with open(os.path.join(a.dist_dir, MANIFEST), encoding="utf-8") as f:
                man = json.load(f)
            print(f"{len(man['files'])} files match their SHA-256; Data/{man['plugin']} masters {man['masters']}; "
                  f"scripts in {man.get('ba2') or 'Data/Scripts'}")
        print("verify-dist: ok" if not problems else f"verify-dist: {len(problems)} problem(s); do not ship")
    return 0 if not problems else 1


# ---------------------------------------------------------------- log-audit

# the runtime's step names (FO4SF_ALifeSimQuest.psc): init, load_game, options, squad_spawn, replenish, order,
# node_arrive, garrison, reroute, materialize, dematerialize, stuck_relink, marker_replace, battle, battle_end,
# squad_defeated, capture, status, api, tick, warn, error. Steps not listed here are counted under "other".
CATEGORIES = (            # (category, exact step names, fallback pattern)
    ("init", {"init"}, r"^init"),
    ("load", {"load_game"}, r"load_game|reload"),
    ("spawn", {"squad_spawn"}, r"^squad_spawn"),
    ("replenish", {"replenish"}, r"^replenish"),
    ("materialize", {"materialize"}, r"^materializ"),
    ("dematerialize", {"dematerialize"}, r"^dematerializ"),
    ("battle", {"battle"}, r"^battle(_start)?$"),
    ("battle_end", {"battle_end"}, r"^battle_(end|result|resolved)"),
    ("capture", {"capture"}, r"captur"),
    ("squad_dead", {"squad_defeated"}, r"defeat|eliminat"),
    ("stuck", {"stuck_relink"}, r"stuck"),
    ("error", {"error"}, r"^error|fatal"),
    ("warn", {"warn"}, r"^warn"),
)


def categorize(step):
    s = step.lower()
    for cat, exact, _ in CATEGORIES:
        if s in exact:
            return cat
    for cat, _, pat in CATEGORIES:
        if re.search(pat, s):
            return cat
    return None


def parse_log(lines):
    out = []
    for n, line in enumerate(lines, 1):
        m = LOG_LINE.search(line)
        if not m:
            continue
        kv = dict(re.findall(r"(\w+)=(\S+)", m.group("rest")))
        try:
            rt = float(m.group("rt"))
        except ValueError:
            rt = math.nan
        out.append({"line": n, "rt": rt, "step": m.group("step"), "kv": kv})
    return out


def audit_log(lines):
    ev = parse_log(lines)
    steps, cats = {}, {c: 0 for c, _, _ in CATEGORIES}
    caps_by_faction, spawns_by_faction, errors, unknown = {}, {}, [], {}
    sessions, back_in_time, last_rt = 0, 0, None
    online = {}
    max_online = 0
    unmatched_demat = 0
    for e in ev:
        steps[e["step"]] = steps.get(e["step"], 0) + 1
        cat = categorize(e["step"])
        kv = e["kv"]
        if cat is None:
            unknown[e["step"]] = unknown.get(e["step"], 0) + 1
            continue
        cats[cat] += 1
        if cat in ("init", "load"):
            sessions += 1               # a load rebases rt and drops every 3D squad
            online.clear()
        elif last_rt is not None and e["rt"] < last_rt - 1e-6:
            back_in_time += 1
        if not math.isnan(e["rt"]):
            last_rt = e["rt"]
        fac = kv.get("owner_to") or kv.get("faction") or kv.get("winner")
        squad = kv.get("squad")
        if cat == "spawn":
            spawns_by_faction[kv.get("faction", "?")] = spawns_by_faction.get(kv.get("faction", "?"), 0) + 1
        elif cat == "capture":
            caps_by_faction[fac or "?"] = caps_by_faction.get(fac or "?", 0) + 1
        elif cat == "materialize":
            online[squad] = True
            max_online = max(max_online, len(online))
        elif cat == "dematerialize":
            if squad in online:
                online.pop(squad, None)
            else:
                unmatched_demat += 1
        elif cat == "error":
            errors.append({"line": e["line"], "step": e["step"], "kv": kv})
    res = {"alife_lines": len(ev), "sessions": sessions, "steps": steps, "counts": cats,
           "spawns_by_faction": spawns_by_faction, "captures_by_faction": caps_by_faction,
           "max_squads_online": max_online, "still_online_at_end": len(online),
           "dematerialize_without_materialize": unmatched_demat, "rt_backwards": back_in_time,
           "unknown_steps": unknown, "errors": errors[:50], "error_count": len(errors)}
    crit = {"has_alife_lines": bool(ev), "has_init": cats["init"] + cats["load"] > 0, "no_errors": not errors,
            "time_monotonic": back_in_time == 0}
    res["criteria"] = crit
    res["pass"] = crit["has_alife_lines"] and crit["has_init"] and crit["no_errors"]
    return res


def cmd_log_audit(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        res = audit_log(f)
    if a.json:
        print(json.dumps(res, indent=1))
        return 0 if res["pass"] else 1
    c = res["counts"]
    print(f"A-Life log {path_basename(a.file)}: {res['alife_lines']} ALIFE_MOD lines, {res['sessions']} session(s)")
    print(table(["event", "count"], [
        ["init", c["init"]], ["save loads", c["load"]], ["squads spawned", c["spawn"]],
        ["squads replenished", c["replenish"]], ["3D materializations", c["materialize"]],
        ["offline dematerializations", c["dematerialize"]], ["offline battles", c["battle"]],
        ["battles resolved", c["battle_end"]], ["captures", c["capture"]], ["squads defeated", c["squad_dead"]],
        ["stuck relinks (3D)", c["stuck"]],
        ["warnings", c["warn"]], ["errors", c["error"]], ["max squads online", res["max_squads_online"]],
    ]))
    if res["captures_by_faction"] or res["spawns_by_faction"]:
        facs = sorted(set(res["captures_by_faction"]) | set(res["spawns_by_faction"]))
        print(table(["faction", "spawned", "captures"],
                    [[f, res["spawns_by_faction"].get(f, 0), res["captures_by_faction"].get(f, 0)] for f in facs]))
    if res["unknown_steps"]:
        print("other steps: " + ", ".join(f"{k}={v}" for k, v in sorted(res["unknown_steps"].items())))
    for e in res["errors"][:10]:
        print(f"ERROR line {e['line']}: {e['step']} {' '.join(f'{k}={v}' for k, v in e['kv'].items())}")
    if res["rt_backwards"]:
        print(f"WARN  rt went backwards {res['rt_backwards']} time(s) within a session")
    print("log-audit: ok" if res["pass"] else "log-audit: FAILED " +
          ", ".join(k for k, v in res["criteria"].items() if not v and k != "time_monotonic"))
    return 0 if res["pass"] else 1


# ---------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--out", required=True)
    i.add_argument("--template", choices=("vanilla", "custom"), default="vanilla")
    i.add_argument("--force", action="store_true")
    v = sub.add_parser("validate")
    v.add_argument("--config", required=True)
    v.add_argument("--json", action="store_true")
    s = sub.add_parser("simulate")
    s.add_argument("--config", required=True)
    s.add_argument("--ticks", type=int, default=1000)
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--json-out")
    k = sub.add_parser("package")
    k.add_argument("--config", required=True)
    k.add_argument("--out", required=True)
    k.add_argument("--starfield-dir", default=os.environ.get("FO4SF_STARFIELD"))
    k.add_argument("--extra-data-dir")
    k.add_argument("--pack-ba2", action="store_true")
    k.add_argument("--dotnet", default="dotnet", help="dotnet executable (default: dotnet on PATH)")
    k.add_argument("--compiler", help="PapyrusCompiler.exe (default: under --starfield-dir/Tools)")
    k.add_argument("--archive2", help="Archive2.exe (default: under --starfield-dir/Tools)")
    d = sub.add_parser("verify-dist")
    d.add_argument("--dist-dir", required=True)
    d.add_argument("--json", action="store_true")
    lg = sub.add_parser("log-audit")
    lg.add_argument("--file", required=True)
    lg.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    fn = {"init": cmd_init, "validate": cmd_validate, "simulate": cmd_simulate, "package": cmd_package,
          "verify-dist": cmd_verify_dist, "log-audit": cmd_log_audit}[a.cmd]
    try:
        return fn(a)
    except Refused as e:
        print(f"{a.cmd} refused: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
