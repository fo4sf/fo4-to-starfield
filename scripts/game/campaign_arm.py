"""Arm a chain of planned queues only when it can not swap the installed set, go where the owner said not to go, or run
without the crash and disk caps (docs/testing/campaign-arm.md). Offline: it reads queue.json files and a campaign
manifest, it never launches the game, installs or types anything.

usage:
  python scripts/game/campaign_arm.py check --campaign <campaign.json> [--release HOLD,...] [--sha256 HEX]
      every queue of the campaign, refused with the reason when:
        - its queue folder or staging is not a full path, its queue.json is missing, or its tests name no coc;
        - (for the whole campaign) the Starfield folder does not hold installed_exp with exactly installed_plugins,
          intact and active as exp_install.py reads it, with or without a pre_launch;
        - a test travels by anything but coc <cell>, or types FO4SF_Probe.MoveTo (both go where the holds can not see);
        - it pins another FO4Port staging than the campaign's, or that staging's FO4Port.esm changed since the plan;
        - its pinned bridge is not the campaign's, changed since the plan, or is not that bridge already installed and
          active in the campaign's Starfield folder (the runner would install or activate it);
        - its pre_launch would install anything but the campaign's installed experiment with its installed plugins
          (a walk queue's exp_install.py install of the set already installed is allowed: it changes nothing; the
          Starfield folder's FO4SFExp.install.json must show that experiment with exactly its plugins, and exp_install.py's
          own relaunch checks must pass), or runs
          another program than the campaign's python;
        - a test marked fresh would launch the game again (any but the first test left, or any retry of one);
        - a test starts in or goes to a held cell (campaign "holds", e.g. the Red Rocket arrival; a travel test's
          dest_cell and a door_trip's "inside" cell count) not named in --release;
        - its state.json has used every launch the caps allow while tests are left (the run would stop at once);
      and the campaign is refused when its caps are not the night-run caps (one launch, stop at the first crash, at
      least 40 GB free on the dump drive). Exit 0 only when every queue can be armed.
  python scripts/game/campaign_arm.py script --campaign <campaign.json> --out <NEW chain.ps1> [--release HOLD,...]
      after the same check, the PowerShell chain: the campaign's launch mode (FO4SF_LAUNCH), the check again at run
      time against the sha256 of the manifest it was written from, then per queue the check of that queue again
      (check --only NAME --queue-sha256 HEX: its queue.json and the rounds or presence file its judge reads must
      still be the files the chain was armed with), the run
      with the caps, its judge, and the gate; the chain stops at the first queue the recheck or the gate refuses.
  python scripts/game/campaign_arm.py run --campaign <campaign.json>
      the same chain without PowerShell: the check (holds
      lifted only by the campaign's "released" list), then per queue the check again with its queue.json pinned,
      testqueue.py run with the caps, its judge and the gate, stopping at the first refusal. The campaign's "launch" ("steam", the default, or "exe") becomes
      FO4SF_LAUNCH for cycle.ps1. Every step runs in the campaign's checkout with its python. Every step is logged to <campaign>.run.log. Exit 0 only when every queue passed.
  python scripts/game/campaign_arm.py gate --queue <queue> --run-exit N [--judge-exit N]
      exit 0 only when the run ended with exit 0, the judge (when given) with exit 0, and the queue's state.json
      exists, says finished and counts no crash and no dead start.

campaign.json:
  {"name": "v6e", "checkout": "D:\\Modding\\wt_nightrun", "commit": "<the checkout's full git sha>", "python": "C:\\Modding\\venv-render\\Scripts\\python.exe",
   "staging": "<the installed FO4Port staging>", "bridge": "<the installed bridge staging>",
   "starfield": "<the Starfield folder; testqueue.py's default when left out>",
   "installed_exp": "<the installed experiment folder>", "installed_plugins": ["FO4TerrainCore.esm", ...],
   "caps": {"max_attempts": 1, "max_relaunch": 1, "crash_budget": 1, "min_free_gb": 43, "dump_drive": "D:\\"},
   "holds": {"red_rocket": ["FO4Core_RedRocketSpawn"]},
   "queues": [{"name": "doors_out", "queue": "<queue folder>", "judge": ["scripts/bridge/door_rounds.py", "judge",
               "--queue", "<queue folder>"]}]}
"""
import argparse
import ast
import hashlib
import json
import math
import ntpath
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import console_plan as cp  # noqa: E402
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402

STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"   # testqueue.py's default --starfield
FLOOR_GB = 40.0                  # the coordinator's night-run floor (2026-10-19): at least 40 GB free on D:
JUDGES = ("scripts/bridge/door_rounds.py", "scripts/bridge/presence.py", "scripts/game/testqueue.py")
JUDGE_CMDS = {"scripts/bridge/door_rounds.py": ("judge",), "scripts/bridge/presence.py": ("judge",),
              "scripts/game/testqueue.py": ("report",)}


def norm(p):
    """A Windows path compared without case, slash direction or a trailing separator."""
    return str(p).replace("/", "\\").rstrip("\\").casefold()


# each judge's own argparse options after its subcommand: (how many times it may be given, a value pattern)
JUDGE_OPTS = {"scripts/bridge/door_rounds.py": {"--queue": (1, r".+"), "--rounds": (1, r".+"),
                                                "--world-instance": (None, r"[^=]+=[^=]+")},
              "scripts/bridge/presence.py": {"--queue": (1, r".+"), "--presence": (1, r".+")},
              "scripts/game/testqueue.py": {"--queue": (1, r".+")}}
# exp_install.py install's options (its argparse): None as the pattern is a flag
EXP_INSTALL_OPTS = {"--exp-dir": (1, r".+"), "--starfield": (1, r".+"), "--plugins": (1, r".+"),
                    "--pack": (1, None), "--needs": (1, r".+")}


def options_why(args, opts, what):
    """(why the options in args are not ones opts takes, else None; {option: [values]}). Every option spelled out,
    given at most as often as it may be, and followed by a value unless it is a flag: what the command's own argparse
    accepts, read the same way, so a typo stops the arming instead of the run (Codex on #391)."""
    seen, rest = {}, list(args)
    while rest:
        opt = rest.pop(0)
        if opt not in opts:
            return f"{what} option {opt!r} is not one it takes ({', '.join(opts)})", seen
        most, pattern = opts[opt]
        if pattern is None:
            seen.setdefault(opt, []).append(True)
        elif not rest or rest[0].startswith("-") or not re.fullmatch(pattern, rest[0]):
            return f"{what} option {opt} needs a value" + (f", not {rest[0]!r}" if rest else ""), seen
        else:
            seen.setdefault(opt, []).append(rest.pop(0))
        if most is not None and len(seen[opt]) > most:
            return f"{what} gives {opt} {len(seen[opt])} times: at most {most}", seen
    return None, seen


def judge_args_why(judge):
    """Why the judge would refuse its options (exit 2, or door_rounds.py's own --world-instance check) after the run,
    else None."""
    opts = next((v for k, v in JUDGE_OPTS.items() if norm(k) == norm(judge[0])), {})
    why, seen = options_why(judge[2:], opts, f"judge {judge[0]} {judge[1]}")
    if why or not seen.get("--world-instance"):
        return why
    # Codex on #391: door_rounds.py judge reads the pins with world_pairs, which stops on a malformed one
    import importlib.util
    spec = importlib.util.spec_from_file_location("_fo4sf_door_rounds_arm",
                                                  os.path.join(os.path.dirname(HERE), "bridge", "door_rounds.py"))
    dr = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(dr)
        dr.world_pairs(seen["--world-instance"])
    except (ValueError, ImportError, OSError) as error:
        return f"judge {error}"
    return None


def judge_bound(judge, qdir):
    """Whether a judge's argv names exactly one --queue, and that it is the campaign entry's own queue folder."""
    if any(str(x).startswith("--queue=") for x in judge):
        return False
    at = [i for i, x in enumerate(judge) if x == "--queue"]
    return len(at) == 1 and at[0] + 1 < len(judge) and norm(judge[at[0] + 1]) == norm(qdir or "")


def cell_key(c):
    """A cell compared without case or the FO4Port_ prefix. Codex on #391: the runner adds FO4Port_ to a planned cell,
    a dest_cell and the launch cell (Runner.ensure_game, coc.ps1), so "Vault95" in a queue enters FO4Port_Vault95, and
    a hold may name either form."""
    c = str(c).casefold()
    return c[len("fo4port_"):] if c.startswith("fo4port_") else c


def cells(q):
    """The cells every test of a queue starts in or goes to (a plan kind's cell, coc, plan-terrain's world_coc, which
    an empty travel starts at, a "coc X" travel, a travel test's dest_cell behind its load door, and a door_trip's
    sides, the "inside" cell the door leads to), in order, no repeats. A test with no cell launches into the queue's launch cell first (Runner.ensure_game:
    launch_cell, else Vault111Cryo), so that cell is listed too."""
    out = []
    tests = q.get("tests") or []
    if any(not t.get("cell") for t in tests):
        out.append(q.get("launch_cell") or "Vault111Cryo")       # Codex on #391
    for t in tests:
        # Codex on #391: a door_trip enters its "inside" cell through the door, so a held interior is checked too
        sides = [t[k].get("cell") for k in ("outside", "inside") if isinstance(t.get(k), dict)]
        # Codex on #391: a travel test goes through its load door into dest_cell
        for c in (t.get("cell"), t.get("coc"), t.get("world_coc"), t.get("dest_cell"), *sides,
                  *re.findall(r"(?i)\bcoc\s+([A-Za-z0-9_]+)", str(t.get("travel") or ""))):
            if c and c not in out:
                out.append(c)
    return out


def check_caps(caps):
    """Reasons the caps are not the night-run caps."""
    c, bad = caps or {}, []
    def one(k):                          # Codex on #391: JSON true equals 1 in Python, and testqueue refuses "True"
        return type(c.get(k)) is int and c.get(k) == 1
    if not one("max_relaunch"):
        bad.append(f"max_relaunch {c.get('max_relaunch')!r}, want 1 (one launch, no relaunch after a crash)")
    if not one("crash_budget"):
        bad.append(f"crash_budget {c.get('crash_budget')!r}, want 1 (stop at the first crash or dead start)")
    g = c.get("min_free_gb")
    if not (isinstance(g, (int, float)) and not isinstance(g, bool) and math.isfinite(g) and g >= FLOOR_GB):
        bad.append(f"min_free_gb {g!r}, want {FLOOR_GB:g} or more")
    if not (type(c.get("max_attempts")) is int and c.get("max_attempts") in (1, 2)):
        bad.append(f"max_attempts {c.get('max_attempts')!r}, want 1 or 2")
    if not re.fullmatch(r"[A-Za-z]:\\", str(c.get("dump_drive") or "")):
        bad.append(f"dump_drive {c.get('dump_drive')!r}, want a drive root such as D:\\")
    return bad


def pre_launch_why(pre, camp):
    """Why a queue's pre_launch is not allowed, else None."""
    if not pre:
        return None
    py = camp.get("python") or "python"
    if norm(pre[0]) != norm(py):
        # Codex on #391: the runner runs pre_launch verbatim, so its first element is the program that runs
        return f"pre_launch runs {pre[0]!r}, not the campaign's python {py!r}"
    args = [str(x) for x in pre[1:]]
    script = norm(args[0]) if args else ""
    if script == norm(os.path.join("scripts", "game", "runner_features.py")) and args[1:2] == ["check"]:
        return None if len(args) == 3 else f"pre_launch runs runner_features.py with {args[1:]}, want check <features>"
    if script != norm(os.path.join("scripts", "game", "exp_install.py")) or args[1:2] != ["install"]:
        return f"pre_launch runs {' '.join(args[:2])}, not a runner check or the installed experiment"

    # Codex on #391: argparse keeps the last of a repeated option (this check read the first), and exits 2 on one it
    # does not take: each option once, as --option value, and only exp_install.py install's own
    why, _ = options_why(args[2:], EXP_INSTALL_OPTS, "pre_launch exp_install.py install")
    if why:
        return why

    def opt(name):
        return args[args.index(name) + 1] if name in args[:-1] else None
    exp, plugins = opt("--exp-dir"), opt("--plugins")
    if not camp.get("installed_exp") or exp is None or norm(exp) != norm(camp["installed_exp"]):
        return f"pre_launch would install {exp}, not the installed experiment {camp.get('installed_exp')}"
    want = {p.casefold() for p in camp.get("installed_plugins") or []}
    got = {p.strip().casefold() for p in (plugins or "").split(",") if p.strip()}
    if not got or got != want:
        return f"pre_launch would activate {sorted(got)}, the installed set is {sorted(want)}"
    sf = camp.get("starfield") or STARFIELD
    if opt("--starfield") is None or norm(opt("--starfield")) != norm(sf):
        # Codex on #391: the experiment and the launch must go to the same Starfield folder
        return f"pre_launch installs into {opt('--starfield')}, the campaign runs {sf}"
    # Codex on #391: the reinstall is a no-op only while that same experiment is installed, in its packing mode
    names = [p.strip() for p in (plugins or "").split(",") if p.strip()]
    why = installed_exp_why(camp, names, "--pack" in args)
    return f"pre_launch would not be a no-op: {why}" if why else None


def installed_exp_why(camp, names=None, pack=None):
    """Why the campaign's Starfield folder does not hold its declared experiment (installed_exp with exactly
    installed_plugins, intact and active as exp_install.py's own relaunch check reads it), else None. Codex on #391:
    checked for every campaign, with or without a pre_launch, since cycle.ps1 launches whatever is installed.
    names and pack are a pre_launch's --plugins order and --pack; by default the record's own."""
    import types
    import exp_install as ei
    exp, want = camp.get("installed_exp"), {str(p).casefold() for p in camp.get("installed_plugins") or []}
    if not exp or not want:
        return "the campaign names no installed_exp and installed_plugins: what it runs on can not be checked"
    data = os.path.join(camp.get("starfield") or STARFIELD, "Data")
    rec_p = os.path.join(data, "FO4SFExp.install.json")
    try:
        with open(rec_p, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError) as error:
        return f"no readable install record {rec_p} ({error.__class__.__name__}): the experiment is not installed"
    if not isinstance(rec, dict) or not rec.get("complete", True) or rec.get("cleanup_pending"):
        return f"the install record {rec_p} is incomplete"
    files = {str(k).casefold() for k in (rec.get("files") or {})}
    if norm(rec.get("exp_dir") or "") != norm(exp) or not want <= files:
        return f"another experiment is installed: {rec.get('exp_dir')} ({rec_p}), the campaign's is {exp}; it would replace it"
    # Codex on #391: cycle.ps1 orders every plugin the record selected, so the selected set must be the campaign's
    # (the same reading as exp_install.py: "plugins", else a legacy record's added and replaced lines)
    sel = rec.get("plugins")
    if sel is None:
        sel = [str(x).lstrip("*").strip() for x in rec.get("plugins_added") or []]
        sel += [str(x.get("active", "")).lstrip("*").strip() for x in rec.get("plugins_replaced") or []
                if isinstance(x, dict)]
    have = {str(x).casefold() for x in sel} if isinstance(sel, list) else set()
    if have != want:
        return f"the install record {rec_p} selects {sorted(have)}, the installed set is {sorted(want)}"
    if pack is None:
        pack = bool(rec.get("pack", False))
    elif pack != bool(rec.get("pack", False)):
        # Codex on #391: exp_install.py stops when the packing mode differs from the installed one
        return (f"pre_launch asks for {'a packed' if pack else 'a loose'} experiment, the install record "
                f"{rec_p} has {'a packed' if rec.get('pack') else 'a loose'} one")
    if names is None:
        names = [str(x) for x in sel]
    # Codex on #391: exp_install.py's own relaunch checks (held plugins, activation, packing policy, installed file
    # digests, staged inputs) rather than copies of them
    try:
        if not all(p in rec["files"] for p in names):
            return f"another experiment is installed: {rec.get('exp_dir')} ({rec_p}); it would replace it"
        held = ei.held_off(data)
        packed = pack and any(rel not in names for _, rel in ei.staged_files(exp, names))
        ei.verify_relaunch(types.SimpleNamespace(exp_dir=exp), data, names, packed, rec, held)
        # Codex on #391: cycle.ps1 runs exp_install.py order after deploying FO4Port.esm, and stops (exit 7) on a
        # master that is not active: its own read-only check on the lines it will order
        order = [p for p in names if p.casefold() not in held]
        lines = ei.read_plugins(ei.plugins_txt())[0]
        if not any(ln.strip().lstrip("*").strip().casefold() == "fo4port.esm" for ln in lines):
            lines = lines + ["*FO4Port.esm"]
        _, _, missing = ei.order_lines(lines, order, {p: ei.plugin_masters(ei.data_path(data, p)) for p in order})
        if missing:
            return "exp_install.py order would stop: " + "; ".join(f"{p} needs active master {m}" for p, m in missing)
    except SystemExit as stop:
        return f"exp_install.py would stop: {stop}"
    except (OSError, ValueError, KeyError, TypeError) as error:
        return f"the installed experiment can not be checked: {error}"
    return None


def bridge_installed_why(br, camp):
    """Why the campaign's Starfield folder does not already hold the queue's bridge, installed and active, else None.
    Codex on #391: Runner.ensure_game runs bridge_install.py install, which installs or reactivates one that is not."""
    import bridge_install as bi
    import exp_install as ei
    data = os.path.join(camp.get("starfield") or STARFIELD, "Data")
    rec_p = os.path.join(data, bi.RECORD)
    try:
        with open(rec_p, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError) as error:
        return f"the bridge is not installed: no readable {rec_p} ({error.__class__.__name__}); install it first"
    if not isinstance(rec, dict) or rec.get("complete") is not True or rec.get("cleanup_pending"):
        return f"the bridge install record {rec_p} is incomplete"
    files = rec.get("files")
    if not isinstance(files, dict) or set(files) != {bi.PLUGIN, bi.ARCHIVE}:
        return f"the bridge install record {rec_p} does not cover {bi.PLUGIN} and its archive"
    try:
        if rec.get("source_sha256") != bi.source_inventory(br["dir"]):
            return f"the installed bridge ({rec.get('dir')}) is not the queue's {br['dir']}: install it first"
        for rel, h in files.items():
            t = os.path.join(data, rel)
            if not os.path.isfile(t) or ei.digest(t) != h:
                return f"the installed bridge file {t} changed since its install"
        lines, _, _ = ei.read_plugins(ei.plugins_txt())
        held = bi.PLUGIN.casefold() in ei.held_off(data)
    except (OSError, ValueError, SystemExit) as error:
        return f"the installed bridge can not be checked: {error}"
    if held:
        # Codex on #391: bridge_install.py refuses a held-off bridge that is active, and leaves an inactive one off
        return f"{bi.PLUGIN} is held off by plugin_toggle.py: the queue's bridge would not run; release it first"
    if bi.plugin_line_present(lines, bi.PLUGIN) is None:
        return f"{bi.PLUGIN} is installed but not active: the runner would activate it; order or activate it first"
    return None


def map_markers_why(camp):
    """Why cycle.ps1's map_markers_install.py order would stop every launch, else None (no receipt: nothing to order).
    Codex on #391: the same read-only master and core pin check order runs before it moves or reactivates the line."""
    import map_markers_install as mm
    data = os.path.join(camp.get("starfield") or STARFIELD, "Data")
    rec_p = os.path.join(data, mm.RECORD)
    if not os.path.exists(rec_p):
        return None
    try:
        mm.require_masters(os.path.join(data, mm.PLUGIN), data, "ordered", mm.receipt_pins(rec_p))
    except (OSError, ValueError, SystemExit) as error:
        return f"map_markers_install.py order would stop every launch: {error}"
    return None


def checkout_features(checkout):
    """The runner features the campaign checkout's runner_features.py declares (read, never run), or None."""
    p = os.path.join(checkout or "", "scripts", "game", "runner_features.py")
    try:
        with open(p, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FEATURES" for t in node.targets):
                v = ast.literal_eval(node.value)
                return set(v) if isinstance(v, (tuple, list)) and all(isinstance(x, str) for x in v) else None
    except (OSError, ValueError, SyntaxError):
        return None
    return None


def rooted(p):
    """Whether p is a full path (a Windows drive path, or absolute here)."""
    return bool(p) and bool(re.match(r"[A-Za-z]:[\\/]", str(p)) or os.path.isabs(str(p)))


def check_queue(entry, camp, release):
    """(queue.json or None, [reasons it is refused], [notes])."""
    qdir, why, notes = entry.get("queue") or "", [], []
    if not rooted(qdir):
        # Codex on #391: run and the chain work in the checkout, a relative folder would name another queue there
        return None, [f"queue {qdir!r} is not a full path"], notes
    q = tq.load(os.path.join(qdir, "queue.json"))
    if not isinstance(q, dict) or not q.get("tests"):
        return None, [f"no planned queue at {qdir}"], notes
    if not rooted(q.get("staging")):
        # Codex on #391: the check reads the staging where it runs, the runner in the checkout: one path, two folders
        why.append(f"pins the staging {q.get('staging')!r}, not a full path")
    elif norm(q.get("staging") or "") != norm(camp.get("staging") or ""):
        why.append(f"pins the staging {q.get('staging')}, the campaign's is {camp.get('staging')}")
    else:
        esm = os.path.join(q["staging"], "FO4Port.esm")
        if not os.path.exists(esm):
            why.append(f"{esm} is missing")
        elif tq.sha256(esm) != q.get("plugin_sha256"):
            why.append(f"{esm} changed since the plan (build {q.get('build_id')})")
    # Codex on #391: the runner's own checks before its first test, so an armed chain is not stopped by them
    from types import SimpleNamespace
    for m in (tq.Runner.staging_mismatch(SimpleNamespace(q=q)), tq.Runner.experiment_mismatch(SimpleNamespace(q=q))):
        if m:
            why.append(m)
    loose = sorted({str(t["routes_file"]) for t in q["tests"] if t.get("routes_file") and not rooted(t["routes_file"])})
    if loose:
        # Codex on #391: the pin hashes the routes where the check runs, the runner reads them in the checkout
        why.append(f"routes_file {', '.join(loose[:3])} is not a full path")
    gone = sorted({str(t["routes_file"]) for t in q["tests"] if t.get("routes_file") and rooted(t["routes_file"])
                   and not os.path.isfile(t["routes_file"])})
    if gone:
        # Codex on #391: a missing routes_file would pin as "missing" and reach the game with no route
        why.append(f"routes_file {', '.join(gone[:3])} is missing")
    planned = q.get("routes_sha256")
    if isinstance(planned, dict):
        # Codex on #391: the pin hashes the route as it is at arming; the plan recorded the route it planned with
        moved = sorted({os.path.basename(str(t["routes_file"])) for t in q["tests"] if t.get("routes_file")
                        and rooted(t["routes_file"]) and os.path.isfile(t["routes_file"])
                        and planned.get(os.path.basename(str(t["routes_file"]))) != tq.sha256(t["routes_file"])})
        if moved:
            why.append(f"routes_file {', '.join(moved[:3])} changed since the queue was planned (routes_sha256)")
    br = q.get("bridge")
    if br and not camp.get("bridge"):
        # Codex on #391: the runner installs a queue's bridge before launch: a campaign that names none would get one
        why.append(f"pins the bridge {br.get('dir')}, and the campaign names no bridge")
    elif br:
        if norm(br.get("dir") or "") != norm(camp["bridge"]):
            why.append(f"pins the bridge {br.get('dir')}, the campaign's is {camp['bridge']}")
        else:
            m = tq.bridge_mismatch(br) or bridge_installed_why(br, camp)
            if m:
                why.append(m)
    p = pre_launch_why(q.get("pre_launch"), camp)
    if p:
        why.append(p)
    # Codex on #391: the runner in the campaign checkout stops (exit 3) on a feature it lacks, after the chain was armed
    need = set(q.get("needs") or runner_features.needs(q["tests"]))
    pre = [str(x) for x in q.get("pre_launch") or []]
    if len(pre) > 3 and norm(pre[1]) == norm(os.path.join("scripts", "game", "runner_features.py")):
        need |= {x.strip() for x in pre[3].split(",") if x.strip()}
    if "--needs" in pre[:-1]:
        need |= {x.strip() for x in pre[pre.index("--needs") + 1].split(",") if x.strip()}
    if need:
        have = checkout_features(camp.get("checkout"))
        if have is None:
            why.append(f"needs runner features {sorted(need)}: the checkout {camp.get('checkout')} has no readable "
                       "scripts\\game\\runner_features.py")
        elif need - have:
            why.append(f"needs runner features {sorted(need - have)} the checkout {camp.get('checkout')} lacks: "
                       "update it first")
    starts = cells(q)
    odd = sorted({str(t.get("travel")).strip() for t in q["tests"] if str(t.get("travel") or "").strip()
                  and not re.fullmatch(r"(?i)coc\s+[A-Za-z0-9_]+", str(t["travel"]).strip())})
    moves = sorted({t["id"] for t in q["tests"] for k in cp.CONSOLE_KEYS for c in (t.get(k) or [])
                    if isinstance(c, str) and c.startswith(cp.MOVETO_PREFIX)})
    if moves:
        # Codex on #391: FO4SF_Probe.MoveTo moves the player to a reference and can load a cell the holds never see
        why.append(f"FO4SF_Probe.MoveTo in {', '.join(moves[:3])}: its cell can not be checked against the holds; "
                   "run such a queue by hand")
    if odd:
        # Codex on #391: a cow or player.moveto travel goes where the holds can not see
        why.append(f"travel other than coc <cell> can not be checked against the holds: {', '.join(odd[:3])}")
    if not starts:
        why.append("no test names a coc: where it starts can not be checked")
    for hold, names in (camp.get("holds") or {}).items():
        if not (isinstance(names, list) and all(isinstance(n, str) and re.fullmatch(r"[A-Za-z0-9_]+", n)
                                                for n in names)):
            # Codex on #391: a string was read letter by letter and held nothing
            why.append(f"hold {hold!r} is not a list of cell editor ids: {names!r}")
            continue
        held = {cell_key(n) for n in names}
        hit = [c for c in starts if cell_key(c) in held]
        if hit and hold not in release:
            why.append(f"starts at {', '.join(hit)}: held ({hold}); --release {hold} once the owner allows it")
        elif hit:
            notes.append(f"starts at {', '.join(hit)}: {hold} released for this run")
    judge = entry.get("judge")
    if judge is not None:
        if not (isinstance(judge, list) and judge and all(isinstance(x, str) for x in judge)) or \
                norm(judge[0]) not in {norm(j) for j in JUDGES} or \
                tuple(judge[1:2]) not in {JUDGE_CMDS[j] for j in JUDGES if norm(j) == norm(judge[0])}:
            why.append(f"judge {judge!r} is not door_rounds.py judge, presence.py judge or testqueue.py report")
        elif not judge_bound(judge, entry.get("queue")):
            # Codex on #391: a judge of another folder would leave this queue unjudged while its gate passed
            why.append(f"judge {judge!r} does not judge this queue: it needs exactly one --queue {entry.get('queue')}")
        else:
            path, bad = judge_def(judge, q)
            bad = bad or judge_args_why(judge)
            if bad:
                why.append(bad)
            elif path and not os.path.isfile(path):
                why.append(f"the judge's definition file {path} is missing")
    st = tq.load(os.path.join(qdir, "state.json"), {}) or {}
    left = len([t for t in q["tests"] if t["id"] not in (st.get("done") or {})])
    if st.get("crashes") or st.get("start_deaths"):
        why.append(f"state.json counts {st.get('crashes', 0)} crash(es) and {st.get('start_deaths', 0)} dead start(s): "
                   f"plan a new queue folder for a clean budget")
    todo = [t for t in q["tests"] if t["id"] not in (st.get("done") or {})]
    tries = (camp.get("caps") or {}).get("max_attempts")
    first = next(iter(camp.get("queues") or []), None)
    first = isinstance(first, dict) and first.get("name") == entry.get("name") and \
        norm(first.get("queue") or "") == norm(entry.get("queue") or "")
    fresh = [t["id"] for i, t in enumerate(todo) if t.get("fresh") and (i or tries != 1 or not first)]
    if fresh:
        # Codex on #391: a fresh test closes a used game and launches again, outside --max-relaunch (Runner.run);
        # only a first test with one attempt starts on the one launch, and only in the chain's first queue: a later
        # queue's runner reuses the game the queue before it left running (its own game_used is unset)
        why.append(f"fresh test(s) {', '.join(fresh[:3])} would launch the game again outside the one-launch cap, "
                   f"or run in the game the queue before left: plan without --fresh, or one fresh test with "
                   f"max_attempts 1 as the chain's first queue")
    cap = (camp.get("caps") or {}).get("max_relaunch")
    if left and isinstance(cap, int) and (st.get("relaunches") or 0) >= cap:
        # Codex on #391: a queue that stopped after its launch has no launch left under --max-relaunch
        why.append(f"state.json has used {st.get('relaunches')} of {cap} launch(es): the run would stop at once; "
                   f"plan a new queue folder for the {left} test(s) left")
    if not left:
        why.append("every test is already done")
    notes.append(f"{left} of {len(q['tests'])} tests to run; starts: {', '.join(starts[:6])}"
                 + (" ..." if len(starts) > 6 else ""))
    return q, why, notes


JUDGE_DEFS = {"scripts/bridge/door_rounds.py": ("--rounds", "rounds.json"),
              "scripts/bridge/presence.py": ("--presence", "presence.json")}


def judge_def(judge, q):
    """(the definition file a judge reads at judge time, else None; why it can not be pinned, else None).
    door_rounds.py judge reads --rounds, else the queue's experiment rounds.json; presence.py judge --presence,
    else presence.json there; testqueue.py report reads only the queue folder."""
    if not (isinstance(judge, list) and judge and isinstance(judge[0], str)):
        return None, None
    d = next((v for k, v in JUDGE_DEFS.items() if norm(k) == norm(judge[0])), None)
    if d is None:
        return None, None
    opt, name = d
    at = [i for i, x in enumerate(judge) if x == opt]
    if any(str(x).startswith(opt + "=") for x in judge) or len(at) > 1 or (at and at[0] + 1 >= len(judge)):
        return None, f"judge gives {opt} more than once or as {opt}=value: once, as {opt} <file>"
    if at:
        path = judge[at[0] + 1]
        if not re.match(r"[A-Za-z]:[\\/]", path) and not os.path.isabs(path):
            return None, f"judge {opt} {path!r} is relative: give the full path"
        return path, None
    exp = (q or {}).get("experiment")
    if not exp:
        return None, f"judge reads {name} from the queue's experiment folder, and the queue names none"
    if not (re.match(r"[A-Za-z]:[\\/]", exp) or os.path.isabs(exp)):
        # Codex on #391: the judge runs in the checkout, the check where it was started: one path, two files
        return None, f"judge reads {name} from the queue's experiment folder {exp!r}, which is not a full path"
    return os.path.join(exp, name), None


def queue_sha256(entry):
    """The pin of a campaign entry: the sha256 of its queue.json, of the definition file its judge reads (Codex on
    #391: the judge loads it only at judge time) and of every routes_file its tests read, or None when the queue.json
    is missing."""
    p = os.path.join(entry.get("queue") or "", "queue.json")
    if not os.path.isfile(p):
        return None
    h = hashlib.sha256(campaign_sha256(p).encode())
    try:
        q = tq.load(p)
    except ValueError:
        q = None
    path, _ = judge_def(entry.get("judge"), q if isinstance(q, dict) else None)
    files = [path] if path else []
    # Codex on #391: a stairs or door test reads its route from routes_file when it runs and when it is judged
    files += sorted({str(t["routes_file"]) for t in (q or {}).get("tests") or []
                     if isinstance(t, dict) and t.get("routes_file")} if isinstance(q, dict) else set())
    for f in files:
        h.update(b"\0" + norm(f).encode() + b"\0" + (campaign_sha256(f) if os.path.isfile(f) else "missing").encode())
    return h.hexdigest()


def checkout_rev_why(camp):
    """Why the campaign checkout is not the commit the campaign names, clean, else None. Codex on #391: the pins cover
    the campaign, queue, route and judge files; the runner, judge and PowerShell code are the checkout's commit."""
    want, co = str(camp.get("commit") or ""), str(camp.get("checkout") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", want):
        return f"commit {camp.get('commit')!r}: name the checkout's full git sha the campaign was armed on"
    try:
        head = subprocess.run(["git", "-C", co, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60)
        dirty = subprocess.run(["git", "-C", co, "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                               text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        return f"the checkout {co} can not be read with git: {error}"
    if head.returncode or dirty.returncode:
        return f"the checkout {co} is not a git checkout"
    if head.stdout.strip() != want:
        return f"the checkout {co} is at {head.stdout.strip()[:8]}, the campaign was armed on {want[:8]}"
    if dirty.stdout.strip():
        return f"the checkout {co} has uncommitted changes to tracked files"
    return None


def game_running():
    """The Starfield process id, else None (None where tasklist does not exist)."""
    try:
        return tq.Controls.game_pid()
    except OSError:
        return None


def recheck(entry, camp, release, pin):
    """Reasons a queue checked at the start of the chain may not run now: the full check again and the installed
    experiment, right before its run, and its queue.json and its judge's definition file still the files the chain
    was armed with (pin)."""
    _, why, _ = check_queue(entry, camp, release)
    inst = installed_exp_why(camp)
    if inst:
        # Codex on #391: an earlier queue's hours can change the installed experiment before this one launches
        why = why + [inst]
    mm = map_markers_why(camp)
    if mm:
        why = why + [mm]
    rev = checkout_rev_why(camp)
    if rev:
        why = why + [rev]
    if queue_sha256(entry) != pin:
        # Codex on #391: a queue re-planned or edited while an earlier one ran was never armed
        why = [f"{os.path.join(entry.get('queue') or '', 'queue.json')} or its judge's definition file changed since "
               "the chain was armed"] + why
    return why


def check(camp, release):
    """({"caps": [...], "queues": [(entry, why, notes)]}, ok)."""
    caps = check_caps(camp.get("caps"))
    for k in ("checkout", "staging") + tuple(k for k in ("bridge", "starfield") if camp.get(k)):
        if not rooted(camp.get(k)):
            # Codex on #391: the chain's Set-Location and the runner resolve a relative path where they are started
            caps.append(f"{k} {camp.get(k)!r} is not a full path")
    if camp.get("launch", "steam") not in LAUNCHES:
        # Codex on #391: chain() and run_chain() refuse it; the check must not pass it
        caps.append(f"launch {camp.get('launch')!r}, want one of {LAUNCHES}")
    py = str(camp.get("python") or "python")
    if re.search(r"[\\/]", py) and not rooted(py):
        # Codex on #391: the chain checks the python before Set-Location and runs it after; a bare command is found
        # on PATH both times, a relative path would not be the same file
        caps.append(f"python {py!r} is a relative path: give a full path or a bare command name")
    elif rooted(py) and re.split(r"[\\/]", py)[-1].lower() not in ("python", "python.exe"):
        # Codex on #391: cycle.ps1 runs a bare `python`; the chain puts this python's folder first on PATH for it
        caps.append(f"python {py!r} is not named python.exe: cycle.ps1's own python calls would not find it")
    why = installed_exp_why(camp)
    if why:
        caps.append(why)
    why = map_markers_why(camp)
    if why:
        caps.append(why)
    why = checkout_rev_why(camp)
    if why:
        caps.append(why)
    unknown = sorted(set(release) - set(camp.get("holds") or {}))
    if unknown:
        caps.append(f"--release names holds the campaign does not have: {unknown}")
    rows, names = [], set()
    for e in camp.get("queues") or []:
        _, why, notes = check_queue(e, camp, release)
        if e.get("name") in names or not re.fullmatch(r"[A-Za-z0-9_.-]+", str(e.get("name") or "")):
            why.append(f"queue name {e.get('name')!r} is missing, repeated or not plain")
        names.add(e.get("name"))
        rows.append((e, why, notes))
    if not rows:
        caps.append("the campaign has no queues")
    return {"caps": caps, "queues": rows}, not caps and all(not w for _, w, _ in rows)


def load_campaign(path):
    """(campaign, sha256 of the very bytes parsed). Codex on #391: a digest read again from disk could pin a manifest
    edited after the one the chain's commands were written from."""
    with open(path, "rb") as f:
        raw = f.read()
    return json.loads(raw.decode("utf-8-sig")), hashlib.sha256(raw).hexdigest()


def read_campaign(path):
    return load_campaign(path)[0]


def releases(s):
    return {x.strip() for x in (s or "").split(",") if x.strip()}


def show(res):
    for c in res["caps"]:
        print(f"REFUSED campaign: {c}")
    for e, why, notes in res["queues"]:
        print(f"{'REFUSED' if why else 'OK':8s} {e.get('name')}: {e.get('queue')}")
        for w in why:
            print(f"    - {w}")
        for n in notes:
            print(f"    . {n}")


def ps(s):
    """A PowerShell single-quoted string; exits on a quote."""
    if "'" in str(s) or "\n" in str(s):
        sys.exit(f"{s!r}: a quote or a line break in a path or argument")
    return f"'{s}'"


def psa(args):
    """A PowerShell array of single-quoted strings, for Py."""
    return "@(" + ", ".join(ps(x) for x in args) + ")"


def run_args(qdir, caps, starfield=STARFIELD):
    return ["scripts\\game\\testqueue.py", "run", "--queue", qdir, "--starfield", starfield,
            "--max-attempts", str(caps["max_attempts"]),
            "--max-relaunch", str(caps["max_relaunch"]), "--crash-budget", str(caps["crash_budget"]),
            "--min-free-gb", f"{caps['min_free_gb']:g}", "--dump-drive", caps["dump_drive"], "--wait-for-idle"]


def campaign_sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def chain(camp, path, release, digest=None):
    caps, py = camp["caps"], camp.get("python") or "python"
    launch = camp.get("launch", "steam")
    if launch not in LAUNCHES:
        sys.exit(f"launch {launch!r}, want one of {LAUNCHES}")
    rel = ",".join(sorted(release))
    path = os.path.abspath(path)          # Codex on #391: the chain changes into the checkout before the check
    digest = digest or campaign_sha256(path)
    # Codex on #391: no time in the chain, the same manifest and inputs write the same file
    lines = [f"# {camp.get('name')} chain, written by scripts/game/campaign_arm.py from {path}"
             + (f"; released: {rel}" if rel else ""),
             "# Every queue runs with one launch, stops at the first crash or dead start, and keeps "
             f"{caps['min_free_gb']:g} GB free on {caps['dump_drive']}.",
             "# The chain stops at the first queue whose run or gate fails. It types nothing itself.",
             f"$py = {ps(py)}",
             # Codex on #391: a python that can not be run leaves $LASTEXITCODE as it was (cycle.ps1's lease gate):
             # every step goes through Py, which clears it, catches the invocation error and fails closed
             # ('Stop' makes an invocation error catchable; a native exit code never throws, also on PowerShell 7.4+)
             "function Py([string[]]$argv) { $ErrorActionPreference = 'Stop'; "
             "$PSNativeCommandUseErrorActionPreference = $false; $global:LASTEXITCODE = $null; "
             "try { & $py -I @argv | Out-Host; $c = $global:LASTEXITCODE } "
             "catch { Write-Host \"$py could not be run: $_\"; $c = $null }; if ($null -eq $c) { 1 } else { $c } }",
             f"if (-not (Get-Command $py -ErrorAction SilentlyContinue)) {{ Write-Host 'no python at {py}: nothing run'; "
             "exit 1 }",
             # Codex on #391: Set-Location's error does not stop a script; never run the caller's checkout's scripts
             f"try {{ Set-Location -LiteralPath {ps(camp['checkout'])} -ErrorAction Stop }} catch {{ "
             f"Write-Host 'no checkout at {camp['checkout']}: nothing run'; exit 1 }}",
             # Codex on #391: the runner reuses a game it started earlier; the first queue must launch the armed build
             "if (Get-Process Starfield -ErrorAction SilentlyContinue) { Write-Host 'Starfield is running: close it "
             "so the first queue launches the armed build; nothing run'; exit 1 }",
             # Codex on #391: the launch mode is the campaign's, never the caller's environment
             f"$env:FO4SF_LAUNCH = {ps(launch)}",
             # Codex on #391: the runner's helpers use FO4SF_PYTHON; it is the campaign's python, never the caller's
             "$env:FO4SF_PYTHON = $py",
             # Codex on #391: cycle.ps1 deploys and orders plugins with a bare `python`: this python's folder first
             "if (Split-Path -Parent $py) { $env:PATH = (Split-Path -Parent $py) + ';' + $env:PATH }",
             # Codex on #391: the commands below were written from this exact manifest; a changed one runs nothing
             "if ((Py " + psa(["scripts\\game\\campaign_arm.py", "check", "--campaign", path, "--sha256",
                                digest] + (["--release", rel] if rel else [])) + ") -ne 0) "
             "{ Write-Host 'campaign check refused: nothing run'; exit 1 }"]
    for e, _, _ in check(camp, release)[0]["queues"]:
        pin = ["scripts\\game\\campaign_arm.py", "check", "--campaign", path, "--sha256", digest,
               "--only", e["name"], "--queue-sha256", queue_sha256(e)] + (["--release", rel] if rel else [])
        lines += ["", f"# {e['name']}",
                  f"if ((Py {psa(pin)}) -ne 0) {{ Write-Host 'stopped before {e['name']}: it changed since the chain "
                  "was armed'; exit 1 }",
                  "$rc = Py " + psa(run_args(e["queue"], caps, camp.get("starfield") or STARFIELD))]
        judge = ""
        if e.get("judge"):
            # Codex on #391: the judge reads queue.json and its definition file when it runs, hours after the check
            lines += [f"if ((Py {psa(pin + ['--pin-only'])}) -ne 0) {{ Write-Host 'stopped after {e['name']}''s run: "
                      "its queue or judge definition changed during the run: not judged'; exit 1 }",
                      "$jr = Py " + psa([x.replace("/", "\\") if i == 0 else x for i, x in enumerate(e["judge"])])]
            judge = " --judge-exit $jr"
        gate_argv = psa(["scripts\\game\\campaign_arm.py", "gate", "--queue", e["queue"], "--run-exit"])[:-1]
        gate_argv += ', "$rc"' + (', \'--judge-exit\', "$jr"' if judge else "") + ")"
        lines += [f"if ((Py {gate_argv}) -ne 0) {{ Write-Host 'stopped after {e['name']}'; exit 1 }}"]
    lines += ["", "Write-Host 'chain finished: every queue ran clean (the verdicts are in each judge report)'"]
    return "\r\n".join(lines) + "\r\n"


def gate(qdir, rc, judge_rc=None):
    """(ok, why) for one run: ok only for exit 0, a judge (when one ran) that exited 0, and a state.json that
    says finished with no crash and no dead start. A missing or unfinished state is no proof the queue ran.
    The gate decides whether the night goes on to the next queue, not whether the tests passed: a FAIL or
    INCONCLUSIVE verdict is a result for the judge's report, and the next queue still runs."""
    try:
        st = tq.load(os.path.join(qdir, "state.json"))
    except ValueError:
        st = None
    if not isinstance(st, dict):
        return False, f"no readable state.json in {qdir}: nothing proves the queue ran"
    if rc != 0:
        return False, f"the run ended with exit {rc} ({st.get('status')})"
    if judge_rc not in (None, 0):
        return False, f"the judge exited {judge_rc}"
    if st.get("status") != "finished":
        return False, f"the queue is {st.get('status')!r}, not finished"
    if st.get("crashes") or st.get("start_deaths"):
        return False, f"{st.get('crashes', 0)} crash(es), {st.get('start_deaths', 0)} dead start(s)"
    return True, "ran clean: finished (the verdicts are in the judge's report)"


LAUNCHES = ("steam", "exe")


def run_chain(camp, log=print, call=None):
    """The chain in Python: 0 when every queue ran clean, else 1. call(argv, env) runs one step and returns its exit
    code (by default a subprocess in the campaign's checkout, the same as the PowerShell chain's Set-Location)."""
    import subprocess
    if call is None:
        # Codex on #391: the runner and the judges are the campaign checkout's, with its Python, not this module's
        if not (camp.get("checkout") and os.path.isdir(camp["checkout"])):
            log(f"REFUSED campaign: checkout {camp.get('checkout')!r} is not a folder here")
            return 1

        def call(argv, env):
            return subprocess.run(argv, cwd=camp["checkout"], env=env).returncode
    launch = camp.get("launch", "steam")
    if launch not in LAUNCHES:
        log(f"REFUSED campaign: launch {launch!r}, want one of {LAUNCHES}")
        return 1
    released = camp.get("released") or []
    if not (isinstance(released, list) and all(isinstance(x, str) for x in released)):
        log(f"REFUSED campaign: released {released!r} is not a list of hold names")
        return 1
    res, ok = check(camp, set(released))
    for c in res["caps"]:
        log(f"REFUSED campaign: {c}")
    for e, why, notes in res["queues"]:
        log(f"{'REFUSED' if why else 'OK'} {e.get('name')}: " + "; ".join(why + notes))
    if not ok:
        return 1
    py, caps = camp.get("python") or "python", camp["caps"]
    # Codex on #391: the runner's helpers use FO4SF_PYTHON; it is the campaign's python, never the caller's
    env = dict(os.environ, FO4SF_LAUNCH=launch, FO4SF_PYTHON=py)
    if ntpath.dirname(py):                                # Codex on #391: cycle.ps1's bare `python` is this one
        env["PATH"] = ntpath.dirname(py) + os.pathsep + env.get("PATH", "")
    if game_running():
        # Codex on #391: the runner reuses a game it started earlier; the first queue must launch the armed build
        log("REFUSED campaign: Starfield is running: close it so the first queue launches the armed build")
        return 1
    pins = [queue_sha256(e) for e, _, _ in res["queues"]]
    for (e, _, _), pin in zip(res["queues"], pins):
        why = recheck(e, camp, set(released), pin)
        if why:
            log(f"{e['name']}: STOP before the run: " + "; ".join(why))
            return 1
        rc = call([py, "-I", os.path.join("scripts", "game", "testqueue.py")] + run_args(e["queue"], caps, camp.get("starfield") or STARFIELD)[1:],
                  env)
        log(f"{e['name']}: run exit {rc}")
        jr = None
        if e.get("judge"):
            rev = checkout_rev_why(camp)
            if rev:
                log(f"{e['name']}: STOP after the run: {rev}: not judged")
                return 1
            if queue_sha256(e) != pin:
                # Codex on #391: the judge reads queue.json and its definition file now, hours after the check
                log(f"{e['name']}: STOP after the run: its queue.json or its judge's definition file changed during "
                    "the run: not judged")
                return 1
            jr = call([py, "-I", e["judge"][0].replace("/", os.sep)] + e["judge"][1:], env)
            log(f"{e['name']}: judge exit {jr}")
        good, why = gate(e["queue"], rc, jr)
        log(f"{e['name']}: {'OK' if good else 'STOP'} {why}")
        if not good:
            return 1
    log("chain finished: every queue ran clean (the verdicts are in each judge's report)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rn = sub.add_parser("run")
    rn.add_argument("--campaign", required=True)
    for name in ("check", "script"):
        s = sub.add_parser(name)
        s.add_argument("--campaign", required=True)
        s.add_argument("--release", default="", help="holds the owner lifted, comma-separated")
        if name == "check":
            s.add_argument("--sha256", default="", help="refuse unless the campaign file still has this sha256 "
                                                        "(the generated chain passes the one it was written from)")
            s.add_argument("--only", default="", help="check this one queue of the campaign (the chain, before its run)")
            s.add_argument("--queue-sha256", default="", help="with --only: refuse unless that queue.json still has "
                                                              "this sha256 (the one the chain was armed with)")
            s.add_argument("--pin-only", action="store_true", help="with --only: compare only the pin (the chain, "
                                                                   "after the run and before the judge)")
        if name == "script":
            s.add_argument("--out", required=True)
    g = sub.add_parser("gate")
    g.add_argument("--queue", required=True)
    g.add_argument("--run-exit", type=int, required=True)
    g.add_argument("--judge-exit", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "gate":
        ok, why = gate(a.queue, a.run_exit, a.judge_exit)
        print(("OK " if ok else "STOP ") + why)
        return 0 if ok else 1
    if a.cmd == "run":
        logp = a.campaign + ".run.log"

        def log(msg):
            line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}"
            print(line)
            with open(logp, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        camp = read_campaign(a.campaign)
        here = os.path.dirname(os.path.dirname(HERE))
        if norm(os.path.abspath(here)) != norm(os.path.abspath(str(camp.get("checkout") or ""))):
            # Codex on #391: the checks below are this checkout's, the runner the campaign's: one checkout for both
            log(f"REFUSED campaign: run campaign_arm.py from the campaign checkout {camp.get('checkout')}, not {here}")
            return 1
        return run_chain(camp, log)
    camp, digest = load_campaign(a.campaign)
    release = releases(a.release)
    if a.cmd == "check" and a.sha256 and digest != a.sha256.lower():
        print(f"REFUSED campaign: {a.campaign} changed since the chain was written from it: write the chain again")
        return 1
    if a.cmd == "check" and (a.only or a.queue_sha256):
        entry = next((e for e in camp.get("queues") or [] if e.get("name") == a.only), None)
        if entry is None or not a.queue_sha256:
            print(f"REFUSED campaign: --only {a.only!r} needs a queue of the campaign and its --queue-sha256")
            return 1
        if a.pin_only:
            # Codex on #391: after the run its state.json counts the launch; only the files the judge reads must hold
            why = ([] if queue_sha256(entry) == a.queue_sha256.lower() else
                   [f"{os.path.join(entry.get('queue') or '', 'queue.json')} or its judge's definition file changed "
                    "since the chain was armed"]) + [w for w in [checkout_rev_why(camp)] if w]
        else:
            why = check_caps(camp.get("caps")) + recheck(entry, camp, release, a.queue_sha256.lower())
        print(f"{'REFUSED' if why else 'OK':8s} {a.only}: {entry.get('queue')}")
        for w in why:
            print(f"    - {w}")
        return 1 if why else 0
    res, ok = check(camp, release)
    show(res)
    if a.cmd == "check" or not ok:
        return 0 if ok else 1
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists: the script writes a new file only")
    if not camp.get("checkout"):
        sys.exit("the campaign names no checkout to run from")
    text = chain(camp, a.campaign, release, digest)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
