"""vmad_patch.py: the scripted load door's VMAD (docs/terrain/scripted-doors.md), raw and record-level.

  python scripts/terrain/vmad_patch.py port  --port <integ staging> --core <core64 build with doors> --out <NEW folder>
  python scripts/terrain/vmad_patch.py check --port <integ staging> --out <that folder> [--core <core build>]
  python scripts/terrain/vmad_patch.py decode <plugin> <6 hex local id>        print a REFR's VMAD, decoded

The exterior side of a door is written by dotnet/TerrainOverlays (Mutagen 0.55 writes a Starfield REFR VMAD: the
design pass read one back byte for byte). The interior side lives in FO4Port.esm, a pinned build this never rewrites
with Mutagen: `port` links unchanged files and writes independent plugin/map/report files in a new folder. It patches
the plugin in memory, record by record, so that every other record stays byte-identical, which `check` proves by a
record-level byte diff of the two plugins. Per door of the core build's objects.json "doors":
  - the interior door REFR (destination.ref, temporary in its CELL) gains a VMAD attaching FO4SF_LoadDoor with
    DestinationPlugin = the core plugin's file name, DestinationId = the exterior ARRIVAL marker's local id (the
    core's formids.json "doors"[src]["arrival"]: a PERSISTENT XMarker in the overlay world's persistent cell) and
    DestinationX / Y / Z = that marker's MERGED position (its written position + merge_offset) and
    UseDestinationPosition = true (the script applies the coordinates only with it): the return trip;
  - a PERSISTENT XMarker REFR (the interior ARRIVAL marker, where the exterior door's MoveTo lands the player) at the
    FO4 arrival point of the exterior door's XTEL (destination.arrival, metres), in the CELL's persistent children
    group (created when the cell has none), with the local id the cluster promised (destination.id = the pinned
    plugin's next free id + k, make_cluster.py doors): the exterior door's VMAD already names it (and carries its
    position as DestinationX / Y / Z with UseDestinationPosition true).
A temporary destination does not resolve from the other side (an unloaded cell's temporary references are not in
memory: Game.GetFormFromFile returns None and the script refuses; seen in game for the exterior marker 0A76FD,
C:\\Modding\\testqueue\\door_trip_sdm_1018), so both markers are persistent. Interiors have no overlay merge, so a
persistent reference reads its written position there (docs/terrain/overlay-records.md); a MoveTo onto a persistent
reference of the overlay lands at its UNMERGED position, and a SetPosition to the merged one afterwards puts the
player into the merged world (door probe (e)): hence the three coordinates and the bool that turns them on.

VMAD layout (verified on Starfield.esm 1.16.244 by the design pass, 60 REFR VMADs; the same layout Mutagen wrote):
  int16 version 6 | uint16 object format 2 | uint16 script count
  per script: uint16 name length + name | uint8 status (0 local, 1 inherited, 3 removed) | uint16 property count
  per property: uint16 name length + name | uint8 type | uint8 status (1 edited, 3 removed) | value
  value: 1 object = uint16 0, int16 alias -1, uint32 form id; 2 string = uint16 length + chars; 3 int = int32;
         4 float = f32; 5 bool = u8; 11..15 arrays = uint32 count + elements (read, never written here)
A door's properties: DestinationPlugin (2), DestinationId (3) and, for a destination position, DestinationX / Y / Z (4)
then UseDestinationPosition (5, value 1): six, all status 1 (edited); a door without a position has the first two.
Nothing follows the last property on a REFR (no fragments). Everything this writes stays outside the repo.
"""
import argparse
import json
import math
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4land  # noqa: E402

VERSION, OBJECT_FORMAT = 6, 2
SCRIPT = "FO4SF_LoadDoor"                       # scripts/door_bridge/FO4SF_LoadDoor.psc (PR #243): the contract
PROP_PLUGIN, PROP_ID = "DestinationPlugin", "DestinationId"
# The arrival position (float, edited), applied with SetPosition after a successful MoveTo, and the explicit opt-in
# that gates it (bool, edited, true): the names and types of Codex's FO4SF_LoadDoor extension (PR #291, a draft on
# 2026-10-17, not on main yet: scripts/door_bridge/FO4SF_LoadDoor.psc there declares the bool before the three floats;
# Papyrus binds VMAD properties by name, so the order is cosmetic and the reader accepts both). The script ignores
# the coordinates unless the bool is true (zero is a valid coordinate, so the bool, not the values, is the switch):
# a door carries all four properties or none, written DestinationX / Y / Z, then UseDestinationPosition (the sixth).
PROP_POSITION = ("DestinationX", "DestinationY", "DestinationZ")
PROP_USE_POSITION = "UseDestinationPosition"
# The overlay merge: a reference of the overlay world is drawn at its written (local) position + the overlay's
# planet_target_cell (overlays_params.json, cells) x CELL_M, z unchanged. MERGE_MEASURED is the only offset measured in
# game: spawn read - spawn_local in seven core64 / core64b runs (-1200.0029, -2700.0043; make_core64c.CORE64_OFFSET)
# and door probe (e) (C:\Modding\testqueue\door_probe_1017e, 2026-10-16: after MoveTo onto the anchor 0x800 the player
# stood at its unmerged local position; setpos to local + (-1200, -2700) settled at z 110.49 on the Red Rocket canopy,
# the top core64k's plan predicts there). merge_offset refuses any other offset until it is measured.
CELL_M = 100.0
MERGE_MEASURED = (-1200.0, -2700.0, 0.0)
STATUS_LOCAL, STATUS_INHERITED, STATUS_REMOVED = 0, 1, 3
PROP_EDITED, PROP_REMOVED = 1, 3
T_OBJECT, T_STRING, T_INT, T_FLOAT, T_BOOL = 1, 2, 3, 4, 5
_ARRAYS = {11: 8, 12: None, 13: 4, 14: 4, 15: 1}
XMARKER = 0x00003B                              # STAT XMarker of Starfield.esm (master 0: file-local 0000003B)
PERSISTENT = 0x400
COMPRESSED = 0x40000
MAX_LOCAL_ID = 0x00FFFFFF                       # the script refuses 0 and anything above (a full plugin's id)
GROUP_CELL_CHILDREN, GROUP_PERSISTENT, GROUP_TEMPORARY = 6, 8, 9


# ------------------------------------------------------------------------------------------------------------ codec
def _wstr(s):
    b = str(s).encode("cp1252")
    if len(b) > 0xFFFF:
        raise ValueError("VMAD string too long")
    return struct.pack("<H", len(b)) + b


def _rstr(data, pos):
    n, = struct.unpack_from("<H", data, pos)
    s = bytes(data[pos + 2:pos + 2 + n])
    if len(s) != n:
        raise ValueError("VMAD string runs past the end")
    return s.decode("cp1252"), pos + 2 + n


def encode_property(p):
    """One property {"name", "type", "status", "value"} as bytes (object: value = {"form", "alias"?})."""
    t = int(p["type"])
    out = _wstr(p["name"]) + struct.pack("<BB", t, int(p.get("status", PROP_EDITED)))
    v = p["value"]
    if t == T_OBJECT:
        return out + struct.pack("<HhI", 0, int(v.get("alias", -1)), int(v["form"]))
    if t == T_STRING:
        return out + _wstr(v)
    if t == T_INT:
        return out + struct.pack("<i", int(v))
    if t == T_FLOAT:
        return out + struct.pack("<f", float(v))
    if t == T_BOOL:
        return out + struct.pack("<B", 1 if v else 0)
    raise ValueError(f"VMAD property type {t} is not written here")


def encode(scripts, version=VERSION, object_format=OBJECT_FORMAT):
    """A REFR VMAD from [{"name", "status", "properties": [...]}] (see encode_property)."""
    out = struct.pack("<hHH", version, object_format, len(scripts))
    for s in scripts:
        props = s.get("properties") or []
        out += _wstr(s["name"]) + struct.pack("<BH", int(s.get("status", STATUS_LOCAL)), len(props))
        for p in props:
            out += encode_property(p)
    return out


def _read_value(data, pos, t):
    if t == T_OBJECT:
        unused, alias, form = struct.unpack_from("<HhI", data, pos)
        return {"unused": unused, "alias": alias, "form": form}, pos + 8
    if t == T_STRING:
        return _rstr(data, pos)
    if t == T_INT:
        return struct.unpack_from("<i", data, pos)[0], pos + 4
    if t == T_FLOAT:
        return struct.unpack_from("<f", data, pos)[0], pos + 4
    if t == T_BOOL:
        return bool(data[pos]), pos + 1
    if t in _ARRAYS:
        n, = struct.unpack_from("<I", data, pos)
        pos += 4
        if t == 12:
            vals = []
            for _ in range(n):
                v, pos = _rstr(data, pos)
                vals.append(v)
            return vals, pos
        size = _ARRAYS[t]
        return [bytes(data[pos + i * size:pos + (i + 1) * size]).hex() for i in range(n)], pos + n * size
    raise ValueError(f"VMAD property type {t} not handled")


def decode(data):
    """{"version", "format", "scripts": [{"name", "status", "properties": [{"name", "type", "status", "value"}]}]}
    of a REFR VMAD; ValueError for a blob this layout does not parse (a trailing byte is one too)."""
    data = bytes(data)
    if len(data) < 6:
        raise ValueError("VMAD shorter than its header")
    version, fmt, count = struct.unpack_from("<hHH", data, 0)
    if version not in (5, 6) or fmt not in (1, 2):
        raise ValueError(f"VMAD version {version} object format {fmt} not handled")
    pos, scripts = 6, []
    for _ in range(count):
        name, pos = _rstr(data, pos)
        status, nprops = struct.unpack_from("<BH", data, pos)
        pos += 3
        props = []
        for _ in range(nprops):
            pname, pos = _rstr(data, pos)
            ptype, pstatus = struct.unpack_from("<BB", data, pos)
            value, pos = _read_value(data, pos + 2, ptype)
            props.append({"name": pname, "type": ptype, "status": pstatus, "value": value})
        scripts.append({"name": name, "status": status, "properties": props})
    if pos != len(data):
        raise ValueError(f"VMAD has {len(data) - pos} bytes after the last property")
    return {"version": version, "format": fmt, "scripts": scripts}


def _position(position):
    """Three finite floats (a destination position), ValueError otherwise."""
    try:
        pos = [float(v) for v in position]
    except (TypeError, ValueError):
        raise ValueError(f"destination position {position!r} is not three numbers")
    if len(pos) != 3 or not all(math.isfinite(v) and abs(v) < 3.4e38 for v in pos):
        raise ValueError(f"destination position {position!r} is not three finite float32 numbers")
    return pos


def load_door_scripts(plugin, local_id, position=None):
    """The one script entry of a scripted load door: FO4SF_LoadDoor, local (the base carries no script), every
    property edited: DestinationPlugin (string), DestinationId (int, the plugin-local id 1..0xFFFFFF) and, with a
    position, DestinationX / DestinationY / DestinationZ (float: where SetPosition puts the player after the MoveTo)
    and UseDestinationPosition (bool, true: the script's opt-in; without it the floats are ignored). Six properties
    with a position, two without."""
    plugin = str(plugin)
    if not plugin.strip() or "\n" in plugin or "\r" in plugin or any(c in plugin for c in "\\/"):
        raise ValueError(f"destination plugin {plugin!r} is not a plain file name")
    if type(local_id) is not int or not 1 <= local_id <= MAX_LOCAL_ID:
        raise ValueError(f"destination id {local_id!r} is not a plugin-local id in 1..0x{MAX_LOCAL_ID:06X}")
    props = [{"name": PROP_PLUGIN, "type": T_STRING, "status": PROP_EDITED, "value": plugin},
             {"name": PROP_ID, "type": T_INT, "status": PROP_EDITED, "value": local_id}]
    if position is not None:
        props += [{"name": n, "type": T_FLOAT, "status": PROP_EDITED, "value": v}
                  for n, v in zip(PROP_POSITION, _position(position))]
        props.append({"name": PROP_USE_POSITION, "type": T_BOOL, "status": PROP_EDITED, "value": True})
    return [{"name": SCRIPT, "status": STATUS_LOCAL, "properties": props}]


def load_door_vmad(plugin, local_id, position=None):
    """The VMAD bytes of a scripted load door REFR (load_door_scripts, encoded)."""
    return encode(load_door_scripts(plugin, local_id, position))


def load_door_target(vmad):
    """(plugin, id, position) of a scripted load door's VMAD, position = (x, y, z) floats or None for the two-property
    door; ValueError unless it is exactly load_door_vmad's shape (version 6, format 2, one local FO4SF_LoadDoor script
    with the edited properties in that order: DestinationPlugin, DestinationId[, DestinationX, Y, Z,
    UseDestinationPosition]). The position is returned only with its opt-in: UseDestinationPosition (bool) must be
    present and true whenever the three floats are (the script ignores the floats otherwise, so a door without it
    would pass a position check and never use the position), and it never stands without them. The script's own
    declaration order (the bool before the floats) is read too: Papyrus binds VMAD properties by name."""
    d = decode(vmad)
    if (d["version"], d["format"]) != (VERSION, OBJECT_FORMAT):
        raise ValueError(f"version {d['version']} format {d['format']}")
    if len(d["scripts"]) != 1:
        raise ValueError(f"{len(d['scripts'])} scripts")
    s = d["scripts"][0]
    if s["name"] != SCRIPT or s["status"] != STATUS_LOCAL:
        raise ValueError(f"script {s['name']!r} status {s['status']}")
    shape = [(p["name"], p["type"], p["status"]) for p in s["properties"]]
    base = [(PROP_PLUGIN, T_STRING, PROP_EDITED), (PROP_ID, T_INT, PROP_EDITED)]
    floats = [(n, T_FLOAT, PROP_EDITED) for n in PROP_POSITION]
    use = (PROP_USE_POSITION, T_BOOL, PROP_EDITED)
    if shape == base + floats:
        raise ValueError(f"properties {shape}: DestinationX / Y / Z without {PROP_USE_POSITION} (the script ignores "
                         f"the position unless it is true)")
    if shape not in (base, base + floats + [use], base + [use] + floats):
        raise ValueError(f"properties {shape}")
    plugin, local_id = s["properties"][0]["value"], s["properties"][1]["value"]
    if not 1 <= local_id <= MAX_LOCAL_ID:
        raise ValueError(f"destination id {local_id} outside 1..0x{MAX_LOCAL_ID:06X}")
    if shape == base:
        return plugin, local_id, None
    by_name = {p["name"]: p["value"] for p in s["properties"]}
    if by_name[PROP_USE_POSITION] is not True:
        raise ValueError(f"{PROP_USE_POSITION} is false: the script ignores DestinationX / Y / Z")
    position = tuple(by_name[n] for n in PROP_POSITION)
    if not all(math.isfinite(v) for v in position):
        raise ValueError(f"destination position {position} not finite")
    return plugin, local_id, position


def load_door_destination(vmad):
    """(plugin, id) of a scripted load door's VMAD (load_door_target without the position)."""
    plugin, local_id, _position = load_door_target(vmad)
    return plugin, local_id


# Load doors that open before the trip (docs/spikes/load-door-animations.md): the same contract under the child script
# scripts/door_bridge/FO4SF_AnimatedLoadDoor.psc plus its OpenSeconds float. `port --animated-doors <manifest>` writes it
# for doors whose base has load_door.anim and `check` requires it for the doors doors.json lists so; without the option
# every door keeps FO4SF_LoadDoor, byte for byte as before.
ANIMATED_SCRIPT = "FO4SF_AnimatedLoadDoor"
PROP_OPEN_SECONDS = "OpenSeconds"


def animated_load_door_scripts(plugin, local_id, position=None, open_seconds=0.0):
    """load_door_scripts under ANIMATED_SCRIPT, with OpenSeconds (float, edited, finite, 0..30) appended."""
    try:
        seconds = float(open_seconds)
    except (TypeError, ValueError):
        raise ValueError(f"open seconds {open_seconds!r} is not a number")
    if not math.isfinite(seconds) or not 0.0 <= seconds <= 30.0:
        raise ValueError(f"open seconds {open_seconds!r} outside 0..30")
    (script,) = load_door_scripts(plugin, local_id, position)
    script = dict(script, name=ANIMATED_SCRIPT, properties=script["properties"] + [
        {"name": PROP_OPEN_SECONDS, "type": T_FLOAT, "status": PROP_EDITED, "value": seconds}])
    return [script]


def animated_load_door_target(vmad):
    """(plugin, id, position, open_seconds) of an animated load door's VMAD; ValueError unless it is exactly
    animated_load_door_scripts' shape (load_door_target's rules for the rest)."""
    d = decode(vmad)
    if len(d["scripts"]) != 1 or d["scripts"][0]["name"] != ANIMATED_SCRIPT:
        raise ValueError(f"not one {ANIMATED_SCRIPT} script")
    s = d["scripts"][0]
    last = s["properties"][-1] if s["properties"] else None
    if not last or (last["name"], last["type"], last["status"]) != (PROP_OPEN_SECONDS, T_FLOAT, PROP_EDITED):
        raise ValueError(f"{PROP_OPEN_SECONDS} (float, edited) is not the last property")
    base = dict(s, name=SCRIPT, properties=s["properties"][:-1])
    plugin, local_id, position = load_door_target(encode([base], d["version"], d["format"]))
    return plugin, local_id, position, last["value"]


def same_position(got, want, tol=1e-3):
    """True when a decoded position (or None) equals the wanted three numbers within tol (metres)."""
    return got is not None and want is not None and len(got) == len(want) == 3 and all(
        math.isfinite(u) and abs(u - float(v)) <= tol for u, v in zip(got, want))


def merge_offset(core):
    """(dx, dy, 0.0): the overlay merge of the core build's world, its overlays_params.json "planet_target_cell" x
    CELL_M (the overlay formids.json / objects.json names; the only one when neither does). ValueError for a missing
    or unmeasured offset (anything but MERGE_MEASURED: measure it in game first, docs/terrain/scripted-doors.md)."""
    with open(os.path.join(core, "overlays_params.json"), encoding="utf-8-sig") as f:
        prm = json.load(f)
    world = None
    for name in ("formids.json", "objects.json"):
        path = os.path.join(core, name)
        if world is None and os.path.isfile(path):
            with open(path, encoding="utf-8-sig") as f:
                world = json.load(f).get("world")
    ovs = prm.get("overlays") or []
    pick = [o for o in ovs if o.get("world") == world] if world else ovs
    if len(pick) != 1:
        raise ValueError(f"{core}: overlays_params.json has {len(pick)} overlay(s) for world {world!r}")
    cell = pick[0].get("planet_target_cell")
    if not (isinstance(cell, list) and len(cell) == 2 and all(type(c) is int for c in cell)):
        raise ValueError(f"{core}: overlay {pick[0].get('world')} has no planet_target_cell [x, y] (cells)")
    off = (cell[0] * CELL_M, cell[1] * CELL_M, 0.0)
    if off != MERGE_MEASURED:
        raise ValueError(f"{core}: merge offset {off} (planet_target_cell {cell}) is not the measured {MERGE_MEASURED}")
    return off


def merged(pos, offset):
    """A local overlay position moved by the merge offset: where the reference is drawn in game."""
    return [float(p) + float(o) for p, o in zip(pos, offset)]


# ------------------------------------------------------------------------------------------------------- plugin tree
class Record:
    __slots__ = ("header", "data")

    def __init__(self, header, data):
        self.header, self.data = bytes(header), bytes(data)

    sig = property(lambda self: self.header[:4])
    flags = property(lambda self: struct.unpack_from("<I", self.header, 8)[0])
    fid = property(lambda self: struct.unpack_from("<I", self.header, 12)[0])

    def fields(self):
        if self.flags & COMPRESSED:
            raise ValueError(f"{self.sig.decode()} {self.fid:08X} is compressed")
        return list(fo4land.iter_subrecords(self.data))

    def with_fields(self, fields):
        """The same record (header, flags, id, version) over other fields."""
        data = b"".join(encode_field(s, d) for s, d in fields)
        header = self.header[:4] + struct.pack("<I", len(data)) + self.header[8:]
        return Record(header, data)

    def serialize(self):
        return self.header + self.data


class Group:
    __slots__ = ("label", "gtype", "tail", "children")

    def __init__(self, label, gtype, tail, children):
        self.label, self.gtype, self.tail, self.children = bytes(label), gtype, bytes(tail), children

    def serialize(self):
        body = b"".join(c.serialize() for c in self.children)
        return b"GRUP" + struct.pack("<I", 24 + len(body)) + self.label + struct.pack("<I", self.gtype) + self.tail + body


def encode_field(sig, data):
    if len(data) > 0xFFFF:
        raise ValueError(f"field {sig} of {len(data)} bytes needs XXXX, not written here")
    return bytes(sig) + struct.pack("<H", len(data)) + bytes(data)


def record_bytes(sig, fid, flags, fields, version=0x0240, unknown=0):
    """A new record: 24-byte header (stamp 0, form version as the writer's) over the fields."""
    data = b"".join(encode_field(s, d) for s, d in fields)
    return Record(bytes(sig) + struct.pack("<IIIIHH", len(data), flags, fid, 0, version, unknown), data)


def parse_items(buf, start, end):
    out, off = [], start
    while off < end:
        if off + 24 > end:
            raise ValueError(f"truncated item at {off}")
        if buf[off:off + 4] == b"GRUP":
            size, label, gtype = struct.unpack_from("<I4sI", buf, off + 4)
            if size < 24 or off + size > end:
                raise ValueError(f"bad group size at {off}")
            out.append(Group(label, gtype, buf[off + 16:off + 24], parse_items(buf, off + 24, off + size)))
            off += size
        else:
            size = struct.unpack_from("<I", buf, off + 4)[0]
            if off + 24 + size > end:
                raise ValueError(f"bad record size at {off}")
            out.append(Record(buf[off:off + 24], buf[off + 24:off + 24 + size]))
            off += 24 + size
    return out


class Plugin:
    """A plugin as a tree: the TES4 record and the top groups; serialize() writes it back byte for byte when
    nothing changed, with every group size recomputed when something did."""

    def __init__(self, buf):
        buf = bytes(buf)
        if buf[:4] != b"TES4":
            raise ValueError("not a plugin")
        hsize = struct.unpack_from("<I", buf, 4)[0]
        self.tes4 = Record(buf[:24], buf[24:24 + hsize])
        self.items = parse_items(buf, 24 + hsize, len(buf))

    @classmethod
    def read(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    def serialize(self):
        return self.tes4.serialize() + b"".join(i.serialize() for i in self.items)

    def hedr(self):
        """(version, record count, next object id) of HEDR."""
        d = next(d for s, d in self.tes4.fields() if s == b"HEDR")
        return struct.unpack_from("<fII", d)

    def masters(self):
        return [fo4land.zstring(d) for s, d in self.tes4.fields() if s == b"MAST"]

    def set_hedr(self, records, next_id):
        ver = self.hedr()[0]
        fields = [(s, struct.pack("<fII", ver, records, next_id) if s == b"HEDR" else d) for s, d in self.tes4.fields()]
        self.tes4 = self.tes4.with_fields(fields)

    def walk(self):
        """Yield (record, path) for every record, path = [(group type, label bytes), ...] from the top."""
        def rec(items, path):
            for it in items:
                if isinstance(it, Group):
                    yield from rec(it.children, path + [(it.gtype, it.label)])
                else:
                    yield it, path
        yield from rec(self.items, [])

    def records(self):
        """{fid: (sig, flags, data, path as a tuple of (type, label int))}; a repeated id is refused."""
        out = {}
        for r, path in self.walk():
            if r.fid in out:
                raise ValueError(f"form id {r.fid:08X} twice")
            out[r.fid] = (r.sig, r.flags, r.data, tuple((t, struct.unpack("<I", lb)[0]) for t, lb in path))
        return out

    def own_max(self, index):
        """The highest local id of the plugin's own records (load index `index` = its master count)."""
        return max((r.fid & 0xFFFFFF for r, _p in self.walk() if (r.fid >> 24) == index), default=0x7FF)

    def find(self, fid):
        """(parent group's children list, index, record) of a record."""
        def rec(items):
            for i, it in enumerate(items):
                if isinstance(it, Group):
                    hit = rec(it.children)
                    if hit:
                        return hit
                elif it.fid == fid:
                    return items, i, it
            return None
        hit = rec(self.items)
        if hit is None:
            raise KeyError(f"no record {fid:08X}")
        return hit

    def cell_children(self, cell_fid):
        """The CELL children group (type 6) of a cell."""
        def rec(items):
            for it in items:
                if isinstance(it, Group):
                    if it.gtype == GROUP_CELL_CHILDREN and struct.unpack("<I", it.label)[0] == cell_fid:
                        return it
                    hit = rec(it.children)
                    if hit:
                        return hit
            return None
        g = rec(self.items)
        if g is None:
            raise KeyError(f"no children group of cell {cell_fid:08X}")
        return g

    def set_vmad(self, fid, vmad):
        """Give a REFR a VMAD (replacing one it has), after EDID and before everything else, as vanilla orders it."""
        items, i, r = self.find(fid)
        if r.sig != b"REFR":
            raise ValueError(f"{fid:08X} is a {r.sig.decode()}, not a REFR")
        fields = [(s, d) for s, d in r.fields() if s != b"VMAD"]
        at = 1 if fields and fields[0][0] == b"EDID" else 0
        fields.insert(at, (b"VMAD", bytes(vmad)))
        items[i] = r.with_fields(fields)
        return items[i]

    def add_persistent_ref(self, cell_fid, record):
        """Append a REFR to the cell's persistent children group (type 8), created before the temporary group when
        the cell has none; the record must carry the persistent flag."""
        if not record.flags & PERSISTENT:
            raise ValueError("a persistent-group reference needs the persistent flag")
        g = self.cell_children(cell_fid)
        pers = next((c for c in g.children if isinstance(c, Group) and c.gtype == GROUP_PERSISTENT), None)
        if pers is None:
            like = next((c for c in g.children if isinstance(c, Group)), None)
            pers = Group(g.label, GROUP_PERSISTENT, like.tail if like else bytes(8), [])
            g.children.insert(0, pers)
        pers.children.append(record)
        return pers


def xmarker_ref(fid, pos, rot, version=0x0240):
    """A persistent XMarker REFR (NAME 0000003B of master 0, DATA position + rotation) with the given id."""
    data = struct.pack("<6f", *pos, *rot)
    return record_bytes(b"REFR", fid, PERSISTENT, [(b"NAME", struct.pack("<I", XMARKER)), (b"DATA", data)], version)


# --------------------------------------------------------------------------------------------------------- folders
def plugin_in(folder):
    """The one .esm of a staging folder."""
    esms = sorted(n for n in os.listdir(folder) if n.lower().endswith(".esm"))
    if len(esms) != 1:
        raise ValueError(f"{folder}: {len(esms)} .esm files ({esms})")
    return esms[0]


def next_local_id(plugin_path):
    """The pinned plugin's next free local id: HEDR's next object id, which must equal its highest own id + 1 (both
    read; a disagreement is refused, nothing is guessed)."""
    p = Plugin.read(plugin_path)
    nxt = p.hedr()[2]
    top = p.own_max(len(p.masters()))
    if nxt != top + 1:
        raise ValueError(f"{plugin_path}: HEDR next 0x{nxt:06X} != highest own id 0x{top:06X} + 1")
    return nxt


def link_folder(src, dst, skip=()):
    """Hard-link every file of src under dst (copy where a link fails), except the names in skip (top level)."""
    linked = copied = 0
    skip = {name.casefold() for name in skip}
    for root, _dirs, names in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel) if rel != "." else dst, exist_ok=True)
        for n in names:
            if rel == "." and n.casefold() in skip:
                continue
            s, d = os.path.join(root, n), os.path.join(dst, rel, n) if rel != "." else os.path.join(dst, n)
            try:
                os.link(s, d)
                linked += 1
            except OSError:
                shutil.copy2(s, d)
                copied += 1
    return linked, copied


def write_output(path, data):
    """Replace one generated file without truncating a hard-linked source inode."""
    fd, temporary = tempfile.mkstemp(prefix=".door-write-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def require_separate_output(output, *inputs):
    """A new stage/report must not be written into either pinned input tree."""
    destination = os.path.normcase(os.path.realpath(output))
    for source in inputs:
        if not source:
            continue
        root = os.path.normcase(os.path.realpath(source))
        try:
            inside = os.path.commonpath((destination, root)) == root
        except ValueError:  # different Windows volumes
            inside = False
        if inside:
            raise ValueError(f"output {output} is inside input {source}")


def core_doors(core):
    """(core plugin name, [door entries of objects.json with their formids.json ids]) of a core build with doors."""
    with open(os.path.join(core, "objects.json"), encoding="utf-8-sig") as f:
        objects = json.load(f)
    with open(os.path.join(core, "formids.json"), encoding="utf-8-sig") as f:
        ids = json.load(f)
    doors = objects.get("doors") or []
    got = ids.get("doors") or {}
    out = []
    for e in doors:
        v = got.get(e["src"])
        if not isinstance(v, dict) or not all(k in v for k in ("base", "ref", "arrival")):
            raise ValueError(f"{e['src']}: formids.json doors lacks base / ref / arrival")
        out.append(dict(e, ids=v))
    return ids["plugin"], out


def port_edits(core_plugin, doors, port_plugin, port_next, merge, animated=None):
    """[{"src", "door": local id of the interior door REFR, "cell": its CELL id, "marker": the marker's id, "pos",
    "rot", "return_pos": the exterior marker's merged position, "vmad"}] in doors order; ValueError when a door's
    destination is not this plugin, its promised marker id is not the one this plugin allocates (port_next + k), or an
    id repeats. merge = merge_offset(core): the return VMAD's DestinationX / Y / Z = the exterior marker's position
    (objects.json "arrival", the marker's DATA) + merge. animated ({src: open seconds}, --animated-doors): those doors
    get FO4SF_AnimatedLoadDoor with OpenSeconds instead of FO4SF_LoadDoor; None (the default) changes nothing."""
    out, seen = [], set()
    for k, e in enumerate(doors):
        d = e["destination"]
        if str(d.get("plugin", "")).casefold() != port_plugin.casefold():
            raise ValueError(f"{e['src']}: destination plugin {d.get('plugin')!r} is not {port_plugin}")
        want = port_next + k
        if int(d["id"]) != want:
            raise ValueError(f"{e['src']}: the cluster promised marker id {int(d['id']):06X}, this plugin allocates "
                             f"{want:06X} (make_cluster.py doors again against this port)")
        door, cell = int(d["ref"], 16), int(d["cell"], 16)
        if door in seen or want in seen:
            raise ValueError(f"{e['src']}: interior door {door:06X} or marker {want:06X} listed twice")
        seen |= {door, want}
        back = merged(_position(e["arrival"]["pos"]), merge)
        out.append({"src": e["src"], "door": door, "cell": cell, "marker": want,
                    "pos": [float(v) for v in d["arrival"]["pos"]], "rot": [float(v) for v in d["arrival"]["rot"]],
                    "return_pos": back, "vmad": load_door_vmad(core_plugin, int(e["ids"]["arrival"], 16), back)})
        if animated and e["src"] in animated:
            out[-1].update(script=ANIMATED_SCRIPT, open_seconds=animated[e["src"]], vmad=encode(animated_load_door_scripts(
                core_plugin, int(e["ids"]["arrival"], 16), back, animated[e["src"]])))
    return out


def animated_doors(plugin, own_index, doors, manifest):
    """{src: open seconds} for the doors whose interior DOOR base is a manifest item with load_door.anim (matched by the
    base's EDID = the item's editor_id; open_seconds 0 when the rig gave none: the script then waits for the open
    state only). Doors whose base has no anim keep FO4SF_LoadDoor."""
    by_edid = {it.get("editor_id"): it for it in manifest.get("items", [])}
    own, out = own_index << 24, {}
    for e in doors:
        _items, _i, ref = plugin.find(own | int(e["destination"]["ref"], 16))
        name = [d for sig, d in ref.fields() if sig == b"NAME"]
        if len(name) != 1:
            continue
        try:
            _items, _i, base = plugin.find(struct.unpack_from("<I", name[0])[0])
        except KeyError:
            continue
        edid = [d for sig, d in base.fields() if sig == b"EDID"]
        if base.sig != b"DOOR" or len(edid) != 1:
            continue
        ld = (by_edid.get(edid[0].rstrip(b"\0").decode("latin-1")) or {}).get("load_door")
        if isinstance(ld, dict) and isinstance(ld.get("anim"), dict):
            out[e["src"]] = float(ld["anim"].get("open_seconds") or 0.0)
    return out


def patch_port(plugin, edits, own_index):
    """Preflight all selected REFRs, then add VMADs/markers in place. Existing behavior requires a separate policy."""
    own = own_index << 24
    for ed in edits:
        _items, _i, record = plugin.find(own | ed["door"])
        if record.sig != b"REFR":
            raise ValueError(f"{own | ed['door']:08X} is not a REFR")
        if any(sig == b"VMAD" for sig, _data in record.fields()):
            raise ValueError(f"{own | ed['door']:08X}: existing VMAD; refusing to replace door behavior")
    for ed in edits:
        r = plugin.set_vmad(own | ed["door"], ed["vmad"])
        marker = xmarker_ref(own | ed["marker"], ed["pos"], ed["rot"], struct.unpack_from("<H", r.header, 20)[0])
        plugin.add_persistent_ref(own | ed["cell"], marker)
    _ver, nrec, nxt = plugin.hedr()
    plugin.set_hedr(nrec + len(edits), max(nxt, max((ed["marker"] for ed in edits), default=nxt - 1) + 1))


def cmd_port(a):
    require_separate_output(a.out, a.port, a.core)
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists: every output is a new folder")
    name = plugin_in(a.port)
    src_plugin = os.path.join(a.port, name)
    core_plugin, doors = core_doors(a.core)
    if not doors:
        sys.exit(f"{a.core}: no doors in objects.json")
    port_next = next_local_id(src_plugin)
    try:
        merge = merge_offset(a.core)
    except ValueError as e:
        sys.exit(f"doors: {e}")
    plugin = Plugin.read(src_plugin)
    own_index = len(plugin.masters())
    animated = None
    if getattr(a, "animated_doors", ""):           # off by default: every door keeps FO4SF_LoadDoor
        with open(a.animated_doors, encoding="utf-8-sig") as f:
            animated = animated_doors(plugin, own_index, doors, json.load(f))
    try:
        edits = port_edits(core_plugin, doors, name, port_next, merge, animated)
    except ValueError as e:
        sys.exit(f"doors: {e}")
    with open(os.path.join(a.port, "formids.json"), encoding="utf-8-sig") as f:
        ids = json.load(f)
    for e, ed in zip(doors, edits):
        key = f"MARK:{cell_edid(ids, ed['cell'])}:{e['src']}"
        if key in ids:
            sys.exit(f"formids.json already has {key}")
        ids[key] = ed["marker"]
    patch_port(plugin, edits, own_index)
    serialized = plugin.serialize()
    linked, copied = link_folder(a.port, a.out, skip=(name, "formids.json", "README.txt", "doors.json", "doors_check.json"))
    write_output(os.path.join(a.out, name), serialized)
    write_output(os.path.join(a.out, "formids.json"), json.dumps(ids).encode("utf-8"))
    report = {"port": os.path.abspath(a.port), "core": os.path.abspath(a.core), "plugin": name, "core_plugin": core_plugin,
              "port_next_before": f"{port_next:06X}", "merge_offset": list(merge), "doors": [
                  {"src": e["src"], "edid": e["edid"], "interior_door": f"{ed['door']:06X}", "cell": f"{ed['cell']:06X}",
                   "cell_edid": cell_edid(ids, ed["cell"]), "marker": f"{ed['marker']:06X}", "marker_pos": ed["pos"],
                   "marker_rot": ed["rot"], "vmad": ed["vmad"].hex(),
                   **({"script": ed["script"], "open_seconds": ed["open_seconds"]} if "script" in ed else {}),
                   "return_destination": {"plugin": core_plugin, "id": e["ids"]["arrival"], "local": e["arrival"]["pos"],
                                          "merged": ed["return_pos"]}}
                  for e, ed in zip(doors, edits)]}
    write_output(os.path.join(a.out, "doors.json"), json.dumps(report, indent=1).encode("utf-8"))
    lines = [f"{name} with scripted load doors (scripts/terrain/vmad_patch.py port; docs/terrain/scripted-doors.md).",
             f"Pinned input {a.port} ({linked} files hard-linked, {copied} copied, nothing there modified);",
             f"core build {a.core} ({core_plugin}). The plugin is {a.port}'s with, per door:",
             "  the interior door REFR + VMAD FO4SF_LoadDoor (DestinationPlugin = the core plugin, DestinationId = the",
             "  exterior arrival marker, a persistent XMarker of the overlay's persistent cell; DestinationX / Y / Z = its",
             f"  MERGED position: written position + {tuple(merge)}; UseDestinationPosition = true), and one PERSISTENT XMarker REFR at the FO4 arrival",
             "  point inside (the exterior door's destination). Every other record is byte-identical (vmad_patch.py",
             "  check). doors.json lists them.",
             "The script FO4SF_LoadDoor.pex must be in an active plugin's archive (the core stage's Data tree); loose",
             "scripts are not read on this install (docs/slice/scripted-door.md). The three coordinates and the bool need a",
             "script that declares them (PR #291, a draft: it applies them only with UseDestinationPosition, written true).",
             "NOT deployed, NOT queued."]
    if animated:
        lines.insert(-1, f"--animated-doors: {len(animated)} door(s) carry {ANIMATED_SCRIPT} (OpenSeconds; it extends "
                         f"{SCRIPT}, so both .pex files must be in the archive); docs/spikes/load-door-animations.md.")
    for d in report["doors"]:
        lines.append(f"  {d['src']} {d['cell_edid']}: door REFR {d['interior_door']} -> {core_plugin}:{d['return_destination']['id']} "
                     f"at {[round(v, 4) for v in d['return_destination']['merged']]}, marker {d['marker']} at {d['marker_pos']} "
                     f"rot {d['marker_rot']}")
    write_output(os.path.join(a.out, "README.txt"), ("\n".join(lines) + "\n").encode("utf-8"))
    print("\n".join(lines))
    return 0


def cell_edid(ids, cell_local):
    """The CELL editor id a flat formids.json ({"CELL:<edid>": id}) gives a local id, else the id in hex."""
    for k, v in ids.items():
        if k.startswith("CELL:") and v == cell_local:
            return k[5:]
    return f"{cell_local:06X}"


# ----------------------------------------------------------------------------------------------------------- check
def check_port(before, after, doors, core_plugin=None, merge=None, animated=None):
    """[what, ok] of a patched port against its pinned input: masters, every record but the door REFRs byte-identical
    (sig, flags, fields, group path), each door REFR identical but for the inserted VMAD, which decodes to the script,
    the destination (the core's arrival marker when core_plugin is given) and the return position DestinationX / Y / Z
    (that marker's objects.json position + merge when merge is given; present in any case, with UseDestinationPosition
    true: load_door_target refuses a VMAD whose floats lack the bool), the markers (and nothing
    else) new: persistent XMarker REFRs in their cell's persistent group at the arrival points, HEDR counts.
    animated ({src: open seconds}, from doors.json of a port --animated-doors): those doors must carry
    FO4SF_AnimatedLoadDoor with that OpenSeconds, every other door FO4SF_LoadDoor; None = all FO4SF_LoadDoor."""
    checks = []

    def need(cond, what):
        checks.append([what, bool(cond)])
    need(before.masters() == after.masters(), f"masters unchanged {after.masters()}")
    own = len(before.masters()) << 24
    old, new = before.records(), after.records()
    by_door = {own | int(e["destination"]["ref"], 16): e for e in doors}
    markers = {own | int(e["destination"]["id"]): e for e in doors}
    same = sum(1 for fid, v in old.items() if fid not in by_door and new.get(fid) == v)
    need(same == len(old) - len(by_door), f"every record but the {len(by_door)} door REFR(s) byte-identical and in its group "
                                            f"({same:,} of {len(old) - len(by_door):,})")
    need(set(new) - set(old) == set(markers), f"the new records are exactly the {len(markers)} marker(s) "
                                                f"({sorted(f'{f & 0xFFFFFF:06X}' for f in set(new) - set(old))})")
    for fid, e in by_door.items():
        o, n = old.get(fid), new.get(fid)
        if o is None or n is None:
            need(False, f"{e['src']}: door REFR {fid:08X} in both plugins")
            continue
        of, nf = list(fo4land.iter_subrecords(o[2])), list(fo4land.iter_subrecords(n[2]))
        rest = [(s, d) for s, d in nf if s != b"VMAD"]
        need(o[0] == n[0] == b"REFR" and o[1] == n[1] and o[3] == n[3] and rest == of and n[3][-1][0] == GROUP_TEMPORARY,
             f"{e['src']}: door REFR {fid:08X} unchanged but for the VMAD (flags 0x{n[1]:X}, temporary in cell {n[3][-1][1]:08X})")
        vm = [d for s, d in nf if s == b"VMAD"]
        at = [i for i, (s, _d) in enumerate(nf) if s == b"VMAD"]
        anim = (animated or {}).get(e["src"])
        try:
            if anim is None:
                dest = load_door_target(vm[0]) if len(vm) == 1 else None
            else:
                got = animated_load_door_target(vm[0]) if len(vm) == 1 else None
                dest = got[:3] if got and abs(got[3] - anim) < 1e-4 else (f"bad: OpenSeconds {got[3]} not {anim}" if got else None)
        except ValueError as err:
            dest = f"bad: {err}"
        want = (core_plugin, int(e["ids"]["arrival"], 16)) if core_plugin else None
        back = merged(e["arrival"]["pos"], merge) if merge is not None else None
        good = (isinstance(dest, tuple) and dest[2] is not None and (want is None or dest[:2] == want)
                and (back is None or same_position(dest[2], back)) and at == [1 if nf[0][0] == b"EDID" else 0])
        shown = dest if not isinstance(dest, tuple) or dest[2] is None else (*dest[:2], [round(v, 4) for v in dest[2]])
        need(good, f"{e['src']}: VMAD {SCRIPT if anim is None else ANIMATED_SCRIPT} -> {shown} with {PROP_USE_POSITION} true (expected {want or 'any'} at "
                   f"{[round(v, 4) for v in back] if back else 'a position'}; {vm[0].hex() if vm else 'none'})")
    for fid, e in markers.items():
        n = new.get(fid)
        if n is None:
            need(False, f"{e['src']}: marker {fid:08X} written")
            continue
        q = fo4land.parse_ref(list(fo4land.iter_subrecords(n[2])))
        cell = own | int(e["destination"]["cell"], 16)
        want_pos, want_rot = e["destination"]["arrival"]["pos"], e["destination"]["arrival"]["rot"]
        need(n[0] == b"REFR" and n[1] & PERSISTENT and n[3][-2:] == ((GROUP_CELL_CHILDREN, cell), (GROUP_PERSISTENT, cell))
             and q["base"] == XMARKER and q["pos"] is not None
             and max(abs(u - v) for u, v in zip(q["pos"], want_pos)) < 1e-3
             and max(abs(u - v) for u, v in zip(q["rot"], want_rot)) < 1e-5 and q["scale"] == 1.0,
             f"{e['src']}: marker {fid:08X} persistent XMarker in the persistent group of cell {cell:08X} at {q['pos']} rot {q['rot']}")
    ob, nb = before.hedr(), after.hedr()
    need(nb[1] == ob[1] + len(markers) and nb[2] == max((f & 0xFFFFFF for f in new if (f >> 24) == len(before.masters())), default=0) + 1
         and nb[2] == ob[2] + len(markers),
         f"HEDR records {ob[1]} -> {nb[1]}, next 0x{ob[2]:06X} -> 0x{nb[2]:06X} (the markers, nothing else)")
    return checks


def cmd_check(a):
    name = plugin_in(a.out)
    before, after = Plugin.read(os.path.join(a.port, name)), Plugin.read(os.path.join(a.out, name))
    core_plugin, doors = None, None
    with open(os.path.join(a.out, "doors.json"), encoding="utf-8-sig") as f:
        rep = json.load(f)
    core = a.core or rep.get("core")
    require_separate_output(a.out, a.port, core)
    if core and os.path.isdir(core):
        core_plugin, doors = core_doors(core)
    if doors is None:
        sys.exit(f"the core build {core} is needed (--core)")
    try:
        merge = merge_offset(core)
    except ValueError as e:
        sys.exit(f"doors: {e}")
    animated = {d["src"]: float(d["open_seconds"]) for d in rep.get("doors", []) if d.get("script") == ANIMATED_SCRIPT}
    checks = check_port(before, after, doors, core_plugin, merge, animated or None)
    own = len(after.masters()) << 24
    raw = {}
    for e in doors:
        for what, local in (("door", int(e["destination"]["ref"], 16)), ("marker", int(e["destination"]["id"]))):
            _items, _i, r = after.find(own | local)
            raw[f"{e['src']} {what} {local:06X}"] = r.serialize().hex()
    out = {"port": os.path.abspath(a.port), "out": os.path.abspath(a.out), "plugin": name, "checks": checks,
           "core": os.path.abspath(core), "merge_offset": list(merge),
           "records_before": len(before.records()), "records_after": len(after.records()), "raw": raw,
           "pass": all(c[1] for c in checks)}
    write_output(os.path.join(a.out, "doors_check.json"), json.dumps(out, indent=1).encode("utf-8"))
    for what, good in checks:
        print(("  ok   " if good else "  FAIL ") + what)
    for k, v in raw.items():
        print(f"  {k}: {v}")
    print("CHECK", "PASS" if out["pass"] else "FAIL")
    return 0 if out["pass"] else 1


def cmd_decode(a):
    p = Plugin.read(a.plugin)
    own = len(p.masters()) << 24
    _items, _i, r = p.find(own | int(a.local_id, 16))
    vm = [d for s, d in r.fields() if s == b"VMAD"]
    print(f"{r.sig.decode()} {r.fid:08X} flags 0x{r.flags:X} fields {[s.decode() for s, _d in r.fields()]}")
    print("raw", r.serialize().hex())
    if vm:
        print("VMAD", vm[0].hex())
        print(json.dumps(decode(vm[0]), indent=1))
        try:
            plugin, local_id, position = load_door_target(vm[0])
        except ValueError as err:
            print(f"not a {SCRIPT} door VMAD ({err})")
        else:
            print(f"{SCRIPT}: {PROP_PLUGIN} {plugin}, {PROP_ID} {local_id} (0x{local_id:06X}), "
                  + (", ".join(f"{n} {v!r}" for n, v in zip(PROP_POSITION, position)) + f", {PROP_USE_POSITION} True"
                     if position else "no destination position"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("port", help="patch the interior side into a NEW copy of the pinned interior staging")
    p.add_argument("--port", required=True, help="the pinned interior staging (FO4Port.esm, formids.json, cell exports)")
    p.add_argument("--core", required=True, help="the core build with doors (objects.json, formids.json)")
    p.add_argument("--out", required=True, help="a new folder")
    p.add_argument("--animated-doors", default="", metavar="MANIFEST",
                   help="off by default: doors whose interior DOOR base has load_door.anim in this manifest get "
                        f"{ANIMATED_SCRIPT} (open before the trip); docs/spikes/load-door-animations.md")
    p = sub.add_parser("check", help="the patched folder against its pinned input, record by record")
    p.add_argument("--port", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--core", default="", help="the core build (default: the one doors.json names)")
    p = sub.add_parser("decode")
    p.add_argument("plugin")
    p.add_argument("local_id")
    a = ap.parse_args(argv)
    return {"port": cmd_port, "check": cmd_check, "decode": cmd_decode}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
