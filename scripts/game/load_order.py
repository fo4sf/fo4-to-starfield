"""One target load order for our plugins in Plugins.txt (docs/testing/load-order.md): check it, or put it right.

usage: python load_order.py check|fix --starfield <game dir>

The target keeps every line that is not ours where it is, in its own order, and puts our lines after them in five
groups, each group in its current order:
  1. the cores (FO4Terrain*.esm, FO4Actor*.esm),
  2. other FO4SF*.esm plugins (the experiments: FO4SFMission.esm and the like),
  3. FO4Port.esm,
  4. FO4SFMapMarkers.esm,
  5. FO4SFBridge.esm, last.
That is the order the game itself wrote on the owner's PC on 2026-10-22, 25 s after a start (TerrainCore,
TerrainCore_Mars, ActorRaider, Mission, Port, MapMarkers, Bridge), so a game that writes its own order again should
find nothing to change; that the game keeps this order is inferred, not traced. A plugin whose master (one of ours)
would load after it moves to just after that master. Inactive lines keep their place in their group and stay
inactive: a plugin held off by plugin_toggle.py is never ticked here.

check exits 0 when the order is the target, 9 when it is not (the changes are printed), 6 when it cannot be judged
(an active plugin of ours missing from Data, an active plugin whose master is neither active nor loaded by the game,
a master cycle, a duplicated line). fix writes the target with the same BOM and line ending, after copying the old
file to Plugins.txt.bak-<time>, and refuses (6) as check does. Neither touches a line that is not ours.
"""
import argparse
import datetime
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # isolated Python omits the script's directory
import exp_install  # noqa: E402

CORE_PREFIXES = ("fo4terrain", "fo4actor")
PORT, MARKERS, BRIDGE = "fo4port.esm", "fo4sfmapmarkers.esm", "fo4sfbridge.esm"


def name(line):
    return line.strip().lstrip("*").strip()


def group(plugin):
    """0-4 for our plugins (module doc), None for any other line."""
    low = plugin.casefold()
    if not low.endswith((".esm", ".esp", ".esl")):
        return None
    if low.startswith(CORE_PREFIXES):
        return 0
    if low == PORT:
        return 2
    if low == MARKERS:
        return 3
    if low == BRIDGE:
        return 4
    if low.startswith("fo4sf"):
        return 1
    return None


def target(lines, masters):
    """(new lines, problems). masters: {plugin casefold: [master, ...]} for our plugins. Lines that are blank,
    comments or not ours stay first, in order; ours follow by group (module doc), then after their masters."""
    problems, seen = [], set()
    other, ours = [], []
    for ln in lines:
        p = name(ln)
        g = group(p) if p and not ln.strip().startswith("#") else None
        if g is None:
            other.append(ln)
            continue
        if p.casefold() in seen:
            problems.append(f"{p} is listed more than once")
        seen.add(p.casefold())
        ours.append((g, len(ours), ln))
    ours = [ln for _g, _i, ln in sorted(ours)]
    active = {name(ln).casefold() for ln in lines if ln.strip().startswith("*")}
    for ln in ours:
        p = name(ln)
        if not ln.strip().startswith("*"):
            continue
        for m in masters.get(p.casefold(), []):
            if m.casefold() not in active and not exp_install.implicit(m):
                problems.append(f"{p} needs master {m}, which is not active")
    for _ in range(len(ours) + 1):                        # a chain of masters settles within len(ours) passes
        changed = False
        for p in [name(ln) for ln in ours]:
            i = next(k for k, ln in enumerate(ours) if name(ln).casefold() == p.casefold())
            last = max((k for k, ln in enumerate(ours) for m in masters.get(p.casefold(), [])
                        if name(ln).casefold() == m.casefold()), default=-1)
            if last > i:
                ours.insert(last, ours.pop(i))
                changed = True
        if not changed:
            break
    at = {name(ln).casefold(): k for k, ln in enumerate(ours)}
    for p, ms in masters.items():
        for m in ms:
            if p in at and m.casefold() in at and at[m.casefold()] > at[p]:
                problems.append(f"{p} and its master {m} need each other first (a cycle)")
    return other + ours, problems


def changes(old, new):
    """Our plugins, in their new order, that moved: [(plugin, old position, new position)] (1-based)."""
    pos = {name(ln).casefold(): k for k, ln in enumerate(old)}
    return [(name(ln), pos[name(ln).casefold()] + 1, k + 1) for k, ln in enumerate(new)
            if pos.get(name(ln).casefold()) != k]


def read_masters(data, lines):
    """({plugin casefold: [master, ...]}, problems) for our plugins on a line; an inactive one may be absent."""
    out, problems = {}, []
    for ln in lines:
        p = name(ln)
        if not p or ln.strip().startswith("#") or group(p) is None:
            continue
        f = os.path.join(data, p)
        if not os.path.isfile(f):
            if ln.strip().startswith("*"):
                problems.append(f"{p} is active but not in {data}")
            continue
        try:
            out[p.casefold()] = exp_install.plugin_masters(f)
        except (OSError, ValueError) as e:
            problems.append(f"{p}: {e}")
    return out, problems


def run(cmd, starfield, plugins_txt=None, say=print):
    local = os.environ.get("LOCALAPPDATA", "")
    if not plugins_txt and not os.path.isabs(local):
        say("no LOCALAPPDATA folder (not Windows): no Plugins.txt to order")
        return 0
    p_txt = plugins_txt or os.path.join(local, "Starfield", "Plugins.txt")
    original = exp_install.read_bytes(p_txt)
    if original is None:
        say(f"no Plugins.txt at {p_txt}: nothing to order")
        return 0
    try:
        lines, bom, nl = exp_install.plugin_lines(original)
    except UnicodeDecodeError:
        say(f"{p_txt} is not UTF-8: not judged")
        return 6
    masters, problems = read_masters(os.path.join(starfield, "Data"), lines)
    new, more = target(lines, masters)
    problems += more
    if problems:
        say("load order not judged: " + "; ".join(problems))
        return 6
    moved = changes(lines, new)
    if not moved:
        say("load order ok: our plugins are in the target order")
        return 0
    for p, a, b in moved:
        say(f"  {p}: line {a} -> {b}")
    if cmd == "check":
        say(f"load order differs from the target in {len(moved)} line(s) (fix puts it right)")
        return 9
    bak = p_txt + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copyfile(p_txt, bak)
    exp_install.write_plugins(p_txt, new, bom, nl, expected_current=original)
    say(f"load order fixed: {len(moved)} line(s) moved; the old file is {bak}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("check", "fix"))
    ap.add_argument("--starfield", required=True)
    a = ap.parse_args(argv)
    try:
        return run(a.cmd, a.starfield)
    except (OSError, ValueError) as e:
        print(f"load order not changed: {e}")
        return 6


if __name__ == "__main__":
    sys.exit(main())
