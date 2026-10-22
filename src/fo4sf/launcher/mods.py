"""Mod manifests on the core, draft v0 (core-launcher plan task L2). A mod built on the core declares what it needs;
the launcher turns a set of them into one load order or refuses with a reason. Nothing here installs anything.

    {"id": "example.mod", "version": "1.2.0",
     "core": ">=0.1, <0.2",                  # the core's version range (comma = and)
     "starfield": "1.15.222.0",              # optional exact Starfield version pin
     "plugins": ["ExampleMod.esm"],          # in the mod's own order
     "requires": ["other.mod"],              # must be present, loads before this one
     "load_after": ["optional.mod"],         # loads before this one only if present
     "source": {"url": "https://...", "sha256": "..."}}   # where the launcher fetches it (GAMMA model), optional

Rules: ids are unique; a plugin belongs to one mod; the core's own plugins always load first, in the core's order;
then mods in dependency order, ties broken by id so every PC gets the same order. Mods ship their own content and
reference converted records by FormID, never converted assets (plan section 2).
"""
import re

ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
VERSION = re.compile(r"\d+(\.\d+){0,3}")
CONSTRAINT = re.compile(r"\s*(>=|<=|==|>|<)\s*(\d+(?:\.\d+){0,3})\s*")


class ModError(ValueError):
    pass


def vtuple(v):
    if not isinstance(v, str) or not VERSION.fullmatch(v):
        raise ModError(f"version {v!r}: digits and dots only, up to four parts")
    parts = [int(p) for p in v.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def satisfies(version, spec):
    """True if version meets every comma-separated constraint in spec (">=0.1, <0.2")."""
    v = vtuple(version)
    for part in spec.split(","):
        m = CONSTRAINT.fullmatch(part)
        if not m:
            raise ModError(f"constraint {part!r}: use >=, <=, ==, > or < with a version")
        op, w = m.group(1), vtuple(m.group(2))
        ok = {">=": v >= w, "<=": v <= w, "==": v == w, ">": v > w, "<": v < w}[op]
        if not ok:
            return False
    return True


def validate(m):
    """ModError unless m is a well-formed manifest."""
    if not isinstance(m, dict):
        raise ModError("a manifest is a JSON object")
    mid = m.get("id")
    if not isinstance(mid, str) or not ID.fullmatch(mid):
        raise ModError(f"id {mid!r}: lower-case letters, digits, _ . - (up to 64)")
    vtuple(m.get("version"))
    if not isinstance(m.get("core"), str):
        raise ModError(f"{mid}: no core version range")
    for part in m["core"].split(","):
        if not CONSTRAINT.fullmatch(part):
            raise ModError(f"{mid}: core constraint {part!r} is not valid")
    plugins = m.get("plugins")
    if not isinstance(plugins, list) or not plugins or not all(
            isinstance(p, str) and p.lower().endswith((".esm", ".esp", ".esl")) for p in plugins):
        raise ModError(f"{mid}: plugins must be a non-empty list of .esm/.esp/.esl names")
    for k in ("requires", "load_after"):
        if not isinstance(m.get(k, []), list) or not all(isinstance(x, str) for x in m.get(k, [])):
            raise ModError(f"{mid}: {k} must be a list of mod ids")
    if mid in m.get("requires", []) + m.get("load_after", []):
        raise ModError(f"{mid}: depends on itself")


def resolve(mods, *, core_version, core_plugins, starfield_version=None):
    """(load order of plugin names, mod order) or ModError naming every refusal found."""
    problems, by_id, owner = [], {}, {p.casefold(): "core" for p in core_plugins}
    for m in mods:
        try:
            validate(m)
        except ModError as e:
            problems.append(str(e))
            continue
        if m["id"] in by_id:
            problems.append(f"{m['id']}: listed twice")
            continue
        by_id[m["id"]] = m
    for mid, m in sorted(by_id.items()):
        if not satisfies(core_version, m["core"]):
            problems.append(f"{mid}: needs core {m['core']}, this core is {core_version}")
        if m.get("starfield") and starfield_version and m["starfield"] != starfield_version:
            problems.append(f"{mid}: pinned to Starfield {m['starfield']}, this game is {starfield_version}")
        for r in m.get("requires", []):
            if r not in by_id:
                problems.append(f"{mid}: requires {r}, which is not installed")
        for p in m["plugins"]:
            k = p.casefold()
            if k in owner:
                problems.append(f"{mid}: plugin {p} already belongs to {owner[k]}")
            else:
                owner[k] = mid
    # dependency order (Kahn), ties by id
    deps = {mid: sorted({d for d in m.get("requires", []) + m.get("load_after", []) if d in by_id})
            for mid, m in by_id.items()}
    order, done = [], set()
    while len(order) < len(by_id):
        ready = sorted(mid for mid in by_id if mid not in done and all(d in done for d in deps[mid]))
        if not ready:
            left = sorted(set(by_id) - done)
            problems.append("dependency cycle among: " + ", ".join(left))
            break
        order.append(ready[0])
        done.add(ready[0])
    if problems:
        raise ModError("; ".join(problems))
    plugins = list(core_plugins) + [p for mid in order for p in by_id[mid]["plugins"]]
    return plugins, order
