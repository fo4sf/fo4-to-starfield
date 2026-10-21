"""Launcher settings: the optional pieces the player turns on and off before playing, each with what it costs
(owner, 2026-10-21: "let the launcher be where I can toggle it off and on, and more settings of that sort that cause
RAM use"). One JSON file per player, written only by `launcher.py settings --set` and read by `launcher.py play`.

Every setting starts at the value that changes nothing on the PC (crash watcher off, bridge and Papyrus logging left
as they are), so a fresh install plays exactly as before until the player turns something on.
"""
import json
import os

from . import files

DUMP_KINDS = ("mini", "full")
TRISTATE = ("unchanged", "on", "off")

# (key, default, allowed values or type, what it costs)
SPEC = (
    ("crash_watch.enabled", False, bool,
     "watch the game from launch to exit: ProcDump attached while it runs, the exit code logged when it ends. "
     "ProcDump itself is small; the cost is the dump."),
    ("crash_watch.dump", "mini", DUMP_KINDS,
     "mini (-mm: threads, stacks and loaded modules, small) or full (-ma, the whole game's memory, about 18 GB on the owner's PC; "
     "the game is paused while it is written)."),
    ("crash_watch.catch_assertion", True, bool,
     "also dump on the engine's assertion stop (first-chance 0x80000003), the flags the old crashwatch.cmd used."),
    ("crash_watch.dump_on_exit", False, bool,
     "also dump when the game ends without an exception (ProcDump -t), for silent exits; it writes one dump on every "
     "exit, a normal quit included."),
    ("crash_watch.folder", "", str, "where dumps and crashwatch.log go (required when the watcher is on)."),
    ("crash_watch.procdump", "", str, "path to procdump64.exe (required when the watcher is on)."),
    ("crash_watch.min_free_gb", 25.0, float, "the watcher is not armed when the dump folder's drive has less free."),
    ("crash_watch.settle_s", 20.0, float,
     "seconds the game must stay up before ProcDump attaches. The old watcher attached at the instant of start (-w), "
     "the leading lead for Steam's ERROR 84."),
    ("bridge", "unchanged", TRISTATE,
     "the test bridge plugin (FO4SFBridge.esm): its script runs all the time and writes the heartbeat and position "
     "log. off holds it off through plugin_toggle.py; on puts it back."),
    ("papyrus_logging", "unchanged", TRISTATE,
     "Papyrus logging, trace and debug information in StarfieldCustom.ini ([Papyrus] bEnableLogging, bEnableTrace, "
     "bLoadDebugInformation): memory and disk for every script. The bridge needs it on."),
    ("my_games", "", str, "Documents\\My Games\\Starfield (required when papyrus_logging is on or off)."),
    ("route", "steam", ("steam", "exe"),
     "how play starts the game: steam (steam://rungameid/1716740, as the test runner does) or exe (Starfield.exe "
     "directly, as the owner does)."),
)
KEYS = {k: (d, t, why) for k, d, t, why in SPEC}


def defaults():
    return {k: d for k, d, _t, _w in SPEC}


def load(path):
    """The settings at path over the defaults; unknown keys are refused, so a typo is never silently ignored."""
    out = defaults()
    if path and os.path.isfile(path):
        saved = files.load_json(path)
        bad = sorted(set(saved) - set(KEYS))
        if bad:
            raise ValueError(f"{path}: unknown setting(s) {', '.join(bad)}")
        for k, v in saved.items():
            out[k] = coerce(k, v)
    return out


def save(path, values):
    """Only the settings that differ from the defaults are written."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    d = defaults()
    files.save_json(path, {k: v for k, v in sorted(values.items()) if v != d[k]})


def coerce(key, value):
    if key not in KEYS:
        raise ValueError(f"unknown setting {key!r}; known: {', '.join(KEYS)}")
    _d, t, _w = KEYS[key]
    if t is bool:
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("1", "true", "on", "yes"):
            return True
        if s in ("0", "false", "off", "no"):
            return False
        raise ValueError(f"{key}: {value!r} is not on or off")
    if t is float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key}: {value!r} is not a number") from None
        if v < 0:
            raise ValueError(f"{key}: must not be negative")
        return v
    if t is str:
        return str(value)
    s = str(value).strip().lower()
    if s not in t:
        raise ValueError(f"{key}: {value!r} is not one of {', '.join(t)}")
    return s


def assign(values, pairs):
    """Apply "key=value" strings; returns the new settings (values is not changed)."""
    out = dict(values)
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"--set {p!r}: expected key=value")
        k, v = p.split("=", 1)
        out[k.strip()] = coerce(k.strip(), v)
    return out


def problems(values):
    """[problems] that stop `play` with these settings."""
    out = []
    if values["crash_watch.enabled"]:
        for k in ("crash_watch.folder", "crash_watch.procdump"):
            if not values[k]:
                out.append(f"{k} is not set (needed while the crash watcher is on)")
    # the bridge reads only what Papyrus logs: turning logging off is allowed only with the bridge held off, and
    # putting the bridge back only with logging turned on, whatever the INI or Plugins.txt hold today (Codex, #449)
    if values["papyrus_logging"] == "off" and values["bridge"] != "off":
        out.append("papyrus_logging=off needs bridge=off: an active bridge would be left blind")
    if values["bridge"] == "on" and values["papyrus_logging"] != "on":
        out.append("bridge=on needs papyrus_logging=on: the bridge only sees what Papyrus logs")
    if values["papyrus_logging"] != "unchanged" and not values["my_games"]:
        out.append("my_games is not set (needed to change Papyrus logging)")
    return out


def describe(values):
    """Lines for `settings --show`: each key, its value, and what it costs."""
    d = defaults()
    lines = []
    for k, _d, _t, why in SPEC:
        mark = "" if values[k] == d[k] else "  (changed)"
        lines.append(f"{k} = {json.dumps(values[k])}{mark}\n    {why}")
    return lines
