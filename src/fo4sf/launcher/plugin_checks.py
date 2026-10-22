"""Checks on built plugins before they are installed, read from each plugin's TES4 header only (fast on the core's
683,870 records).

    blueprint master   a plugin that lists BlueprintShips-Starfield.esm as a master is refused: blueprint plugins load
                       last and cannot be overridden, and depending on one shifts the load order (sfstack §3, T7)
    missing master     every master must be another plugin in the same build or a plugin in the Starfield Data folder
                       given (no list of the game's own masters is assumed); without that folder, only "Starfield.esm"
                       is taken as given
    self master        a plugin may not list itself
"""
import os
import struct

from . import files
from .same_ids import PluginError, subrecords

BLUEPRINT = "blueprintships-starfield.esm"


def masters(path):
    """The ordered master list from a plugin's TES4 header."""
    with open(path, "rb") as f:
        head = f.read(24)
        if head[:4] != b"TES4" or len(head) < 24:
            raise PluginError(f"{path}: not a TES4 plugin")
        size, flags = struct.unpack_from("<II", head, 4)
        body = f.read(size)
    if len(body) != size:
        raise PluginError(f"{path}: truncated TES4 header")
    return [v.split(b"\0", 1)[0].decode("utf-8", "replace") for t, v in subrecords(body) if t == "MAST"]


def _plugins(folder):
    return sorted(n for n in os.listdir(folder) if n.lower().endswith(files.PLUGIN_EXT)
                  and os.path.isfile(os.path.join(folder, n)))


def check(folder, starfield_data=None, also=()):
    """{"plugins": {name: [masters]}, "problems": [...]} for every plugin directly in folder."""
    names = _plugins(folder)
    game = _plugins(starfield_data) if starfield_data and os.path.isdir(starfield_data) else ["Starfield.esm"]
    known = {n.casefold() for n in list(names) + list(game) + list(also)}
    out, problems = {}, []
    for n in names:
        try:
            ms = masters(os.path.join(folder, n))
        except PluginError as e:
            problems.append(str(e))
            continue
        out[n] = ms
        for m in ms:
            if m.casefold() == BLUEPRINT:
                problems.append(f"{n}: lists {m} as a master (blueprint plugins load last and cannot be depended on)")
            elif m.casefold() == n.casefold():
                problems.append(f"{n}: lists itself as a master")
            elif m.casefold() not in known:
                problems.append(f"{n}: master {m} is neither a Starfield master nor in this build")
    return {"plugins": out, "problems": problems}
