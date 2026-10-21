"""Hold some of our installed plugins off for a test, and put them back (research/next-phase/testing-automation.md
2.3, task T-toggle): a crash split runs the core without the mission, or without the bridge, with nothing
uninstalled.

usage: python plugin_toggle.py off --plugins A.esm,B.esm --starfield <game dir> [--why "crash split"]
       python plugin_toggle.py on [--plugins A.esm] --starfield <game dir>      (default: every held plugin)
       python plugin_toggle.py status --starfield <game dir>

Only plugins our installers own can be held off: the experiment record's plugins (exp_install.py) and the bridge
(bridge_install.py). off refuses a plugin that is missing, inactive or duplicated in Plugins.txt, and one that another
of our plugins still active needs as a master. It writes Data\\FO4SF.toggle.json first, then unticks the lines (a
guarded Plugins.txt rewrite), so an interruption leaves the record ahead of Plugins.txt and `on` repairs it. While the
record holds a plugin: exp_install.py order and bridge_install.py order leave it unticked (and refuse, exit 6, when the
game ticked it again), exp_install.py active counts it as intended (and fails if it is ticked), the relaunch of the
same installed experiment or bridge (a campaign's pre_launch) keeps it off (and refuses it ticked), and a new install or any uninstall refuses until `on`. on ticks the lines
first, then empties the record; it refuses a plugin with a master (other than the game's implicit ones) that is
neither active nor coming back, and a plugin with no line or several; a held plugin the game cannot load (its Data
file gone or its header unreadable, or the same down its master chain) is released and unticked, and off refuses to
hold one. A hold recorded for another user's Plugins.txt is refused everywhere.
off run again unticks a held plugin the game ticked again. Run it with the game closed, as the installers.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_install  # noqa: E402
import bridge_install  # noqa: E402
from exp_install import deployment  # noqa: E402


def owned(data):
    """{casefolded name: file name} of the plugins our installers own here."""
    out = {}
    rec_p = os.path.join(data, exp_install.RECORD)
    if os.path.exists(rec_p):
        rec = exp_install.read_json(rec_p)
        plugins = rec.get("plugins")
        if plugins is None:
            plugins = [x.lstrip("*").strip() for x in rec.get("plugins_added", [])]
            plugins += [x["active"].lstrip("*").strip() for x in rec.get("plugins_replaced", [])]
        out.update({p.casefold(): p for p in plugins})
    if os.path.exists(os.path.join(data, bridge_install.RECORD)):
        out[bridge_install.PLUGIN.casefold()] = bridge_install.PLUGIN
    return out


def read_record(data):
    p = os.path.join(data, exp_install.TOGGLE)
    exp_install.held_off(data)                            # validates the record, and its profile
    return exp_install.read_json(p) if os.path.exists(p) else {"off": []}


def name(line):
    return line.strip().lstrip("*").strip().casefold()


def names(arg):
    return [x.strip() for x in (arg or "").split(",") if x.strip()]


def unloadable(data, plugin, memo=None):
    """Why the plugin cannot be loaded, else None: its Data file missing, its TES4 header unreadable, or the same for
    any master down its master chain (read from each master's own header in Data, held or not, active or not;
    implicit masters aside) (Codex on #407). off refuses to hold such a plugin and on releases it without ticking it.
    memo ({casefolded name: reason or None}) shares the walk between calls."""
    memo = {} if memo is None else memo
    key = plugin.casefold()
    if key in memo:
        return memo[key]
    memo[key] = None                                      # a master cycle is not this check's to judge
    try:
        path = exp_install.data_path(data, plugin)
    except ValueError as error:
        memo[key] = f"{plugin}: {error}"
        return memo[key]
    why = None
    if not os.path.isfile(path):
        why = f"{plugin}: the plugin file is missing ({path})"
    else:
        try:
            masters = exp_install.plugin_masters(path)
        except (OSError, ValueError) as error:
            why = f"{plugin}: the plugin file is unreadable ({error})"
        else:
            for m in masters:
                if not exp_install.implicit(m) and unloadable(data, m, memo):
                    why = f"{plugin}: needs {memo[m.casefold()]}"
                    break
    memo[key] = why
    return why


def off(a):
    data = os.path.join(a.starfield, "Data")
    rec = read_record(data)
    mine = owned(data)
    want = names(a.plugins)
    if not want:
        raise ValueError("off needs --plugins")
    bad = [p for p in want if p.casefold() not in mine]
    if bad:
        raise ValueError(f"not a plugin our installers own here: {', '.join(bad)} (owned: {', '.join(mine.values()) or 'none'})")
    p_txt = exp_install.plugins_txt()
    original = exp_install.read_bytes(p_txt)
    lines, bom, nl = exp_install.plugin_lines(original)
    held = {x.casefold() for x in rec["off"]}
    new = [p for p in want if p.casefold() not in held]
    for p in new:
        at = [k for k, ln in enumerate(lines) if name(ln) == p.casefold()]
        if len(at) != 1 or not lines[at[0]].strip().startswith("*"):
            raise ValueError(f"missing, inactive or duplicated in Plugins.txt: {p}")
        # a hold on a plugin the game cannot load could never be put back on (Codex on #407)
        why = unloadable(data, mine[p.casefold()])
        if why:
            raise ValueError(why)
    going = held | {p.casefold() for p in new}
    active = {name(ln) for ln in lines if ln.strip().startswith("*")}
    for k, p in mine.items():                             # what stays on must not need what goes off
        if k in going or k not in active:
            continue
        needs = [m for m in exp_install.plugin_masters(exp_install.data_path(data, p)) if m.casefold() in going]
        if needs:
            raise ValueError(f"{p} stays active and needs {', '.join(needs)} as a master: hold it off too")
    ticked = [p for p in rec["off"] if p.casefold() in active]   # held, but the game ticked it again
    if not new and not ticked:
        print(f"already held off: {', '.join(want)}")
        return
    if new:
        rec = {"off": rec["off"] + new, "plugins_txt": p_txt, "why": a.why or ""}
        deployment.write_manifest(os.path.join(data, exp_install.TOGGLE), rec)
    out = [ln.strip().lstrip("*").strip() if name(ln) in going and ln.strip().startswith("*") else ln for ln in lines]
    exp_install.write_plugins(p_txt, out, bom, nl, original)
    print(f"held off: {', '.join(rec['off'])}")


def on(a):
    data = os.path.join(a.starfield, "Data")
    rec = read_record(data)
    held = rec["off"]
    want = names(a.plugins) or list(held)
    stray = [p for p in want if p.casefold() not in {x.casefold() for x in held}]
    if stray:
        raise ValueError(f"not held off: {', '.join(stray)}")
    if not want:
        print("nothing held off")
        return
    back = {p.casefold() for p in want}
    still = {p.casefold() for p in held} - back
    mine = owned(data)
    # Every requested plugin that cannot load (unloadable: its file, its header, or anything down its master chain,
    # held or not) is released and unticked, never restored: its hold would otherwise block every uninstall for good.
    # A broken master that is not held is never ticked or unticked here (Codex on #407). Everything else requested
    # comes back under the checks below.
    memo = {}
    why = {p.casefold(): unloadable(data, mine[p.casefold()], memo) for p in want if p.casefold() in mine}
    lost = {k for k, w in why.items() if w}
    masters = {k: exp_install.plugin_masters(exp_install.data_path(data, mine[k])) for k in why if k not in lost}
    tick = back - lost
    p_txt = exp_install.plugins_txt()
    original = exp_install.read_bytes(p_txt)
    lines, bom, nl = exp_install.plugin_lines(original)
    active = {name(ln) for ln in lines if ln.strip().startswith("*")}
    for p in want:                                        # exactly one line to tick, as off requires (Codex on #407)
        if p.casefold() not in tick:
            continue
        count = sum(name(ln) == p.casefold() for ln in lines)
        if count == 0:
            raise ValueError(f"no Plugins.txt line left for {p}: restore it by hand, then run on again")
        if count > 1:
            raise ValueError(f"{p} has {count} lines in Plugins.txt: remove the extra ones by hand, then run on again")
    for p in want:                                        # what comes back must not need what stays off or unticked
        if p.casefold() not in tick or p.casefold() not in masters:
            continue
        needs = [m for m in masters[p.casefold()] if m.casefold() in still]
        if needs:
            raise ValueError(f"{p} needs {', '.join(needs)} as a master, which stays held off: "
                             f"bring them back together")
        # a master the game unticked meanwhile (exp_install.active), ours or not, is no master to load against: every
        # master but the implicit ones needs an active line or must come back too (Codex on #407)
        inactive = [m for m in masters[p.casefold()]
                    if not exp_install.implicit(m) and m.casefold() not in active | tick]
        if inactive:
            raise ValueError(f"{p} needs {', '.join(inactive)} as a master, which is not active in Plugins.txt: "
                             f"bring them back together or reinstall")
    out = []
    for ln in lines:                                      # tick what comes back, untick what is released
        ticked = ln.strip().startswith("*")
        if name(ln) in tick and not ticked:
            ln = "*" + ln.strip()
        elif name(ln) in lost and ticked:
            ln = ln.strip().lstrip("*").strip()
        out.append(ln)
    if out != lines:
        exp_install.write_plugins(p_txt, out, bom, nl, original)
    rec = dict(rec, off=[p for p in held if p.casefold() not in back])
    deployment.write_manifest(os.path.join(data, exp_install.TOGGLE), rec)
    print(f"back on: {', '.join(p for p in want if p.casefold() in tick) or 'none'}"
          + (f"; released, left unticked (cannot load): "
             f"{'; '.join(why[p.casefold()] for p in want if p.casefold() in lost)}" if lost else "")
          + (f"; still held off: {', '.join(rec['off'])}" if rec["off"] else ""))


def status(a):
    data = os.path.join(a.starfield, "Data")
    rec = read_record(data)
    print(json.dumps(dict(rec, owned=sorted(owned(data).values()))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("off", "on", "status"))
    ap.add_argument("--plugins", default="")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--why", default="")
    a = ap.parse_args(argv)
    try:
        {"off": off, "on": on, "status": status}[a.cmd](a)
    except (OSError, ValueError) as error:
        sys.exit(f"not changed: {error}")


if __name__ == "__main__":
    main()
