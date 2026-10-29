"""The planet master (our own star system with one planet) and the registration override, cloned from the user's own
Starfield.esm at stage time, plus the census of the vanilla records they come from (docs/planet/planet-probe.md).

FO4SFPlanet.esm (master Starfield.esm only; adds records, overrides none):
  0x800 STDT  a clone of Sol's star: our EditorID and name, our own system id (DNAM) and map position (BNAM),
              "Starts Hidden" cleared; every other subrecord (sun preset, time of day data, sound, ...) kept as is
  0x801 LCTN  the system location   LocTypeStarSystem               parent Universe        XNAM system, YNAM 0
  0x802 LCTN  the planet location   LocTypePlanet, LocTypeMajorOrbital  parent 0x801       XNAM system, YNAM planet
  0x803 LCTN  the orbit location    LocTypeOrbit                    parent 0x802           XNAM system, YNAM planet
  0x804 LCTN  the surface location  LocTypeSurface                  parent 0x802           XNAM system, YNAM planet
  0x805 PNDT  a clone of Jemison (selected by its body name): our EditorID and name (FULL and body ANAM), GNAM =
              (our system, parent 0, our planet), no master worldspaces (Jemison's CNAM registers New Atlantis), no
              edited worldspaces, no unique space cell, and (by default) no fauna or flora in its biomes; the
              physical values (gravity, orbit, day length, atmosphere, temperature) stay Jemison's
The location records follow the layout of SFStarEditor's star and planet locations (EDID, FULL, KSIZ/KWDA, DATA,
PNAM, XNAM, YNAM; CC BY-NC-SA source read as a layout reference only, no code copied); their keywords and the
Universe location are Starfield.esm form ids that the build checks by EditorID.
FO4SFPlanetProbe_Reg.esm (masters Starfield.esm, FO4SFPlanet.esm, the world's plugin): the planet record again with
one master worldspace (CNAM: f64 latitude, f64 longitude, world form id; the layout of FO4TerrainCore_Mars.esm's
Mars override, which loads in game): the separate registration plugin the terrain core also uses.

Strings: Starfield.esm is localized (its FULL fields are string ids); our plugins are not, so every FULL a clone
carries is replaced by our own name.
"""
import math
import struct

from . import esm

KEYWORDS = {                       # KYWD, Starfield.esm (checked by EditorID at stage time)
    "LocTypeStarSystem": 0x00149F,
    "LocTypePlanet": 0x0014A0,
    "LocTypeMoon": 0x016010,
    "LocTypeMajorOrbital": 0x070A54,
    "LocTypeSurface": 0x016503,
    "LocTypeOrbit": 0x016504,
    "LocTypeOverlay": 0x2CA99D,    # docs/terrain/overlay-records.md (verified)
}
UNIVERSE = 0x01A53A                # LCTN Universe (checked by EditorID)
UNIVERSE_EDID = "Universe"
STARTS_HIDDEN = 1 << 28            # STDT record flag (xEdit SF1)

STAR, SYSTEM_LOC, PLANET_LOC, ORBIT_LOC, SURFACE_LOC, PLANET = 0x800, 0x801, 0x802, 0x803, 0x804, 0x805
MASTER = "FO4SFPlanet.esm"
REGISTRATION = "FO4SFPlanetProbe_Reg.esm"
DEFAULT_SYSTEM_ID = 0x000F04F1     # above every vanilla system id seen (largest about 0x1D1B9); checked at stage time
DEFAULT_PLANET_ID = 1
DEFAULT_STAR = "Sol"
DEFAULT_PLANET = "Jemison"
DEFAULT_STAR_NAME = "FO4SF Probe Star"
DEFAULT_PLANET_NAME = "FO4SF Probe"
STAR_OFFSET_PC = (2.0, 2.0, 1.0)   # our star's map position = the template star's + this (parsecs)
MIN_STAR_GAP_PC = 0.5
# LCTN DATA when no vanilla template is found: no owner, faction rank -1, level 1..255, no flags
DEFAULT_LOCATION_DATA = struct.pack("<IbBBB", 0, -1, 1, 0, 255)


class PlanetError(ValueError):
    pass


def tag(name):
    """A name as an EditorID part: letters and digits only."""
    t = "".join(c for c in name if c.isalnum())
    if not t:
        raise PlanetError(f"name {name!r} has no letters or digits")
    return t


def u32(b, off=0):
    return struct.unpack_from("<I", b, off)[0]


def fid_hex(fid):
    return f"{fid:08X}"


# ------------------------------------------------------------------------------------------------ components
def component_spans(subs):
    """[(name, start, end)] of the base form component blocks: BFCB <name> ... BFCE, end = the BFCE's index."""
    spans, i = [], 0
    while i < len(subs):
        if subs[i][0] == b"BFCB":
            j = i + 1
            while j < len(subs) and subs[j][0] != b"BFCE":
                if subs[j][0] == b"BFCB":
                    raise PlanetError(f"component {esm.zstring(subs[i][1])!r} has no BFCE")
                j += 1
            if j == len(subs):
                raise PlanetError(f"component {esm.zstring(subs[i][1])!r} has no BFCE")
            spans.append((esm.zstring(subs[i][1]), i, j))
            i = j + 1
            continue
        i += 1
    return spans


def components_end(subs):
    """The index just after the last component block (0 after the EDID when there is none)."""
    spans = component_spans(subs)
    if spans:
        return spans[-1][2] + 1
    return 1 if subs and subs[0][0] == b"EDID" else 0


def set_full_name(subs, name):
    """Put a plain FULL (our name) into the TESFullName_Component block, adding the block after the last component
    when the record has none. Returns the new list."""
    subs = list(subs)
    for cname, start, end in component_spans(subs):
        if cname == "TESFullName_Component":
            body = [s for s in subs[start + 1:end] if s[0] != b"FULL"]
            return subs[:start + 1] + [(b"FULL", esm.zbytes(name))] + body + subs[end:]
    at = components_end(subs)
    block = [(b"BFCB", esm.zbytes("TESFullName_Component")), (b"FULL", esm.zbytes(name)), (b"BFCE", b"")]
    return subs[:at] + block + subs[at:]


def plain_names(subs, name):
    """Every FULL our name: a clone of a localized Starfield.esm record carries string ids in its FULL fields, which a
    plugin that is not localized would show as text; set_full_name puts the main one, this the rest (none is known
    on the planet: the copy of Mars in FO4TerrainCore_Mars.esm has one FULL)."""
    return [(sig, esm.zbytes(name) if sig == b"FULL" else data) for sig, data in subs]


def full_names(subs):
    """The FULL subrecords (raw) inside TESFullName_Component blocks and outside any block."""
    out = []
    inside = None
    for sig, data in subs:
        if sig == b"BFCB":
            inside = esm.zstring(data)
        elif sig == b"BFCE":
            inside = None
        elif sig == b"FULL":
            out.append((inside, data))
    return out


# ------------------------------------------------------------------------------------------------ planet (PNDT)
def planet_spans(subs):
    """(bdst, bded): the indices of the body markers. Raises PlanetError without both."""
    bdst = next((i for i, s in enumerate(subs) if s[0] == b"BDST"), -1)
    bded = next((i for i, s in enumerate(subs) if s[0] == b"BDED"), -1)
    if bdst < 0 or bded < bdst:
        raise PlanetError("planet record without its BDST ... BDED body")
    return bdst, bded


def body_get(subs, sig):
    bdst, bded = planet_spans(subs)
    return next((d for s, d in subs[bdst + 1:bded] if s == sig), None)


def body_set(subs, sig, data, after=None):
    """Replace the body's `sig` subrecord, or insert it after the body's `after` (else at the body's end)."""
    subs = list(subs)
    bdst, bded = planet_spans(subs)
    for i in range(bdst + 1, bded):
        if subs[i][0] == sig:
            subs[i] = (sig, data)
            return subs
    at = bded
    if after is not None:
        for i in range(bdst + 1, bded):
            if subs[i][0] == after:
                at = i + 1
    subs.insert(at, (sig, data))
    return subs


def planet_name(rec):
    d = body_get(rec.subs, b"ANAM")
    return esm.zstring(d) if d is not None else ""


def galaxy(rec):
    """Body GNAM: (star system id, parent planet id, planet id)."""
    d = body_get(rec.subs, b"GNAM")
    if d is None or len(d) < 12:
        raise PlanetError(f"planet {rec.edid}: no 12-byte body GNAM")
    return struct.unpack_from("<III", d)


def master_worldspaces(rec):
    """The top-level CNAM (before BDST): [(latitude, longitude, world form id)] in radians."""
    bdst, _ = planet_spans(rec.subs)
    for sig, data in rec.subs[:bdst]:
        if sig == b"CNAM":
            if len(data) % 20:
                raise PlanetError(f"planet {rec.edid}: master worldspace CNAM of {len(data)} bytes (not 20 per entry)")
            return [struct.unpack_from("<ddI", data, i) for i in range(0, len(data), 20)]
    return []


def pack_worldspaces(entries):
    for lat, lon, wid in entries:
        if not (math.isfinite(lat) and math.isfinite(lon)) or abs(lat) > math.pi / 2 or abs(lon) > math.pi:
            raise PlanetError(f"latitude/longitude ({lat}, {lon}) out of range (radians)")
    return b"".join(struct.pack("<ddI", lat, lon, wid) for lat, lon, wid in entries)


def parse_biome(data):
    """One PPBD: biome, chance, an unknown u32, resource generation, fauna, keywords, flora (entry size 9:
    flora, resource, frequency u8), unknown 16-byte entries (xEdit SF1; parsed exactly on 8 real records)."""
    p = 0

    def take(fmt):
        nonlocal p
        v = struct.unpack_from(fmt, data, p)
        p += struct.calcsize(fmt)
        return v

    try:
        biome, chance, unk, rsgd = take("<IfII")
        n, = take("<I")
        fauna = list(take(f"<{n}I"))
        n, = take("<I")
        keywords = list(take(f"<{n}I"))
        n, size = take("<II")
        if size < 9:
            raise PlanetError(f"PPBD flora entry size {size}")
        flora = []
        for _ in range(n):
            flora.append(bytes(data[p:p + size]))
            p += size
            if p > len(data):
                raise struct.error("flora runs past the record")
        n, = take("<I")
        extra = [bytes(data[p + 16 * i:p + 16 * i + 16]) for i in range(n)]
        p += 16 * n
    except struct.error as e:
        raise PlanetError(f"PPBD of {len(data)} bytes: {e}") from None
    if p != len(data):
        raise PlanetError(f"PPBD of {len(data)} bytes: {len(data) - p} bytes left after the last field")
    return {"biome": biome, "chance": chance, "unknown": unk, "resource_generation": rsgd, "fauna": fauna,
            "keywords": keywords, "flora_entry_size": size, "flora": flora, "extra": extra}


def pack_biome(b):
    out = [struct.pack("<IfII", b["biome"], b["chance"], b["unknown"], b["resource_generation"]),
           struct.pack(f"<I{len(b['fauna'])}I", len(b["fauna"]), *b["fauna"]),
           struct.pack(f"<I{len(b['keywords'])}I", len(b["keywords"]), *b["keywords"]),
           struct.pack("<II", len(b["flora"]), b["flora_entry_size"])]
    for f in b["flora"]:
        if len(f) != b["flora_entry_size"]:
            raise PlanetError("flora entry of the wrong size")
        out.append(f)
    out.append(struct.pack("<I", len(b["extra"])))
    out += b["extra"]
    return b"".join(out)


def biomes(rec):
    return [parse_biome(d) for d in rec.all(b"PPBD")]


def orbital(rec):
    """Body ENAM (orbital data) and FNAM (orbited data), decoded where xEdit names the fields."""
    out = {}
    e = body_get(rec.subs, b"ENAM")
    if e is not None and len(e) >= 66:
        major, minor, aph, ecc, inc, mean = struct.unpack_from("<6d", e)
        tilt, rot, start, peri = struct.unpack_from("<4f", e, 48)
        out.update(major_axis=major, minor_axis=minor, aphelion=aph, eccentricity=ecc, incline=inc, mean_orbit=mean,
                   axial_tilt=tilt, rotational_velocity=rot, start_angle=start, perihelion_angle=peri,
                   apply_orbital_velocity=e[64], geostationary=e[65])
    f = body_get(rec.subs, b"FNAM")
    if f is not None and len(f) >= 20:
        well, = struct.unpack_from("<d", f)
        mass, radius, gravity = struct.unpack_from("<3f", f, 8)
        out.update(gravity_well=well, mass_earths=mass / 5.972e24 if mass > 1e10 else mass, mass_raw=mass,
                   radius_km=radius, surface_gravity=gravity)
    for sig in (b"TEMP", b"DENS", b"PHLA"):
        d = rec.get(sig)
        if d is not None and len(d) == 4:
            out[sig.decode().lower()] = struct.unpack("<f", d)[0]
    return out


def clone_planet(src, formid, edid, name, system_id, planet_id=DEFAULT_PLANET_ID, parent_id=0,
                 no_fauna=True, no_flora=True):
    """Our planet record from a vanilla one (see the module docstring). Returns (record, change list)."""
    if src.sig != b"PNDT":
        raise PlanetError(f"{src!r} is not a planet")
    subs = list(src.subs)
    changes = []
    if not subs or subs[0][0] != b"EDID":
        raise PlanetError(f"planet {src.formid:08X} does not start with an EDID")
    subs[0] = (b"EDID", esm.zbytes(edid))
    subs = plain_names(set_full_name(subs, name), name)
    changes.append("FULL")
    bdst, _ = planet_spans(subs)
    pre, rest = subs[:bdst], subs[bdst:]
    kept = []
    for sig, data in pre:
        if sig == b"CNAM":
            changes.append(f"CNAM: {len(data) // 20} master worldspaces removed")
            continue
        if sig == b"EOVR":
            if data:
                changes.append(f"EOVR: {len(data)} bytes emptied")
            kept.append((sig, b""))
            continue
        if sig == b"PPBD" and (no_fauna or no_flora):
            b = parse_biome(data)
            if no_fauna and b["fauna"]:
                changes.append(f"PPBD {b['biome']:08X}: {len(b['fauna'])} fauna removed")
                b["fauna"] = []
            if no_flora and b["flora"]:
                changes.append(f"PPBD {b['biome']:08X}: {len(b['flora'])} flora removed")
                b["flora"] = []
            kept.append((sig, pack_biome(b)))
            continue
        kept.append((sig, data))
    subs = kept + rest
    subs = body_set(subs, b"ANAM", esm.zbytes(name))
    old = body_get(src.subs, b"DNAM")
    subs = body_set(subs, b"DNAM", struct.pack("<I", 0) + b"\0")
    if old is not None and old != struct.pack("<I", 0) + b"\0":
        changes.append("DNAM: unique space cell cleared")
    if body_get(subs, b"GNAM") is None:
        raise PlanetError(f"planet {src.edid}: no body GNAM to set")
    subs = body_set(subs, b"GNAM", struct.pack("<III", system_id, parent_id, planet_id))
    rec = esm.Record(b"PNDT", formid, subs, src.flags, src.vc, src.version, src.unknown)
    return rec, changes


def registration_record(planet, formid, worlds):
    """The planet record (as our master writes it) with one top-level CNAM listing `worlds`
    [(latitude, longitude, world form id)], placed after the components like the vanilla and Mutagen records."""
    subs = [s for s in planet.subs]
    bdst, _ = planet_spans(subs)
    if any(s[0] == b"CNAM" for s in subs[:bdst]):
        raise PlanetError("the planet already lists master worldspaces")
    at = components_end(subs)
    subs.insert(at, (b"CNAM", pack_worldspaces(worlds)))
    return esm.Record(b"PNDT", formid, subs, planet.flags, planet.vc, planet.version, planet.unknown)


# ------------------------------------------------------------------------------------------------ star (STDT)
def star_name(rec):
    d = rec.get(b"ANAM")
    return esm.zstring(d) if d is not None else ""


def star_system_id(rec):
    d = rec.get(b"DNAM")
    if d is None or len(d) < 4:
        raise PlanetError(f"star {rec.formid:08X} has no DNAM system id")
    return u32(d)


def star_position(rec):
    d = rec.get(b"BNAM")
    if d is None or len(d) < 12:
        raise PlanetError(f"star {rec.formid:08X} has no BNAM position")
    return struct.unpack_from("<3f", d)


def clone_star(src, formid, edid, name, system_id, position):
    if src.sig != b"STDT":
        raise PlanetError(f"{src!r} is not a star")
    subs = list(src.subs)
    if not subs or subs[0][0] != b"EDID":
        raise PlanetError(f"star {src.formid:08X} does not start with an EDID")
    for sig in (b"ANAM", b"BNAM", b"DNAM"):
        if src.get(sig) is None:
            raise PlanetError(f"star {src.edid} has no {sig.decode()}")
    if not all(math.isfinite(v) for v in position):
        raise PlanetError(f"star position {position} is not finite")
    subs[0] = (b"EDID", esm.zbytes(edid))
    subs = plain_names(set_full_name(subs, name), name)
    out = []
    for sig, data in subs:
        if sig == b"ANAM":
            data = esm.zbytes(name)
        elif sig == b"BNAM":
            data = struct.pack("<3f", *position) + data[12:]
        elif sig == b"DNAM":
            data = struct.pack("<I", system_id) + data[4:]
        out.append((sig, data))
    return esm.Record(b"STDT", formid, out, src.flags & ~STARTS_HIDDEN, src.vc, src.version, src.unknown)


# ------------------------------------------------------------------------------------------------ locations (LCTN)
def location_ids(rec):
    """(XNAM star id, YNAM planet id) as signed ints, None where absent."""
    x, y = rec.get(b"XNAM"), rec.get(b"YNAM")
    return (struct.unpack("<i", x[:4])[0] if x and len(x) >= 4 else None,
            struct.unpack("<i", y[:4])[0] if y and len(y) >= 4 else None)


def keywords_of(rec):
    d = rec.get(b"KWDA")
    if not d:
        return []
    return list(struct.unpack(f"<{len(d) // 4}I", d[:len(d) // 4 * 4]))


def new_location(formid, edid, name, keywords, parent, system_id, planet_id, data=DEFAULT_LOCATION_DATA,
                 version=0x245):
    if len(data) != 8:
        raise PlanetError(f"location DATA of {len(data)} bytes (8 expected)")
    subs = [(b"EDID", esm.zbytes(edid)), (b"FULL", esm.zbytes(name)),
            (b"KSIZ", struct.pack("<I", len(keywords))), (b"KWDA", struct.pack(f"<{len(keywords)}I", *keywords)),
            (b"DATA", data), (b"PNAM", struct.pack("<I", parent)),
            (b"XNAM", struct.pack("<i", system_id)), (b"YNAM", struct.pack("<i", planet_id))]
    return esm.Record(b"LCTN", formid, subs, 0, 0, version, 0)


# ------------------------------------------------------------------------------------------------ census
def keyword_edids(plugin):
    """{form id: EditorID} of every keyword of the plugin."""
    return {r.formid: r.edid for r in plugin.records("KYWD", [b"KYWD"])}


def find_star(plugin, name):
    hits = [r for r in plugin.records("STDT", [b"STDT"]) if star_name(r).lower() == name.lower()]
    if len(hits) != 1:
        raise PlanetError(f"{len(hits)} stars named {name!r} in {plugin.path} (exactly one expected)")
    return hits[0]


def find_planet(plugin, name):
    hits = []
    for r in plugin.records("PNDT", [b"PNDT"]):
        try:
            if planet_name(r).lower() == name.lower():
                hits.append(r)
        except PlanetError:
            continue
    if len(hits) != 1:
        raise PlanetError(f"{len(hits)} planets named {name!r} in {plugin.path} (exactly one expected)")
    return hits[0]


def stars(plugin):
    """[(form id, EditorID, name, system id, position)] of every star of the plugin."""
    out = []
    for r in plugin.records("STDT", [b"STDT"]):
        found = []
        for read in (star_system_id, star_position):          # one missing field keeps the other for the checks
            try:
                found.append(read(r))
            except PlanetError:
                found.append(None)
        out.append((r.formid, r.edid, star_name(r), *found))
    return out


def planets(plugin):
    """[(form id, EditorID, body name, (system, parent, planet))] of every planet of the plugin."""
    out = []
    for r in plugin.records("PNDT", [b"PNDT"]):
        try:
            out.append((r.formid, r.edid, planet_name(r), galaxy(r)))
        except PlanetError:
            out.append((r.formid, r.edid, "", None))
    return out


def system_locations(plugin, system_id):
    """Every location whose XNAM is the system id: [(form id, EditorID, YNAM, keywords, DATA, PNAM, record)]."""
    out = []
    for r in plugin.records("LCTN", [b"LCTN"]):
        x, y = location_ids(r)
        if x == system_id:
            p = r.get(b"PNAM")
            out.append((r.formid, r.edid, y, keywords_of(r), r.get(b"DATA"), u32(p) if p and len(p) >= 4 else None, r))
    return out


def subrecord_list(rec):
    return [(s.decode("latin1"), len(d)) for s, d in rec.subs]


def describe_star(rec):
    return {"formid": fid_hex(rec.formid), "edid": rec.edid, "name": star_name(rec), "flags": hex(rec.flags),
            "system_id": hex(star_system_id(rec)), "position_pc": list(star_position(rec)),
            "full": [(c, d.hex()) for c, d in full_names(rec.subs)], "version": rec.version,
            "subrecords": subrecord_list(rec)}


def describe_planet(rec, kw_names=None):
    kw_names = kw_names or {}
    b = biomes(rec)
    kws = []
    for cname, start, end in component_spans(rec.subs):
        if cname == "BGSKeywordForm_Component":
            for s, d in rec.subs[start + 1:end]:
                if s == b"KWDA":
                    kws = list(struct.unpack(f"<{len(d) // 4}I", d))
    dnam = body_get(rec.subs, b"DNAM")
    return {"formid": fid_hex(rec.formid), "edid": rec.edid, "name": planet_name(rec), "flags": hex(rec.flags),
            "galaxy": [hex(v) for v in galaxy(rec)], "version": rec.version,
            "master_worldspaces": [(lat, lon, fid_hex(w)) for lat, lon, w in master_worldspaces(rec)],
            "edited_worldspaces_bytes": len(rec.get(b"EOVR") or b""),
            "space_cell_dnam": dnam.hex() if dnam is not None else None,
            "keywords": [(fid_hex(k), kw_names.get(k, "")) for k in kws],
            "biomes": [{"biome": fid_hex(x["biome"]), "chance": x["chance"], "fauna": len(x["fauna"]),
                        "flora": len(x["flora"]), "keywords": len(x["keywords"])} for x in b],
            "physical": orbital(rec), "full": [(c, d.hex()) for c, d in full_names(rec.subs)],
            "subrecords": subrecord_list(rec)}


def check_keywords(kw_names, keywords=KEYWORDS):
    """{name: form id} after checking each against the plugin's keyword EditorIDs; a mismatch is looked up by
    name instead (printed). Raises PlanetError when a keyword is missing."""
    by_name = {v.lower(): k for k, v in kw_names.items()}
    out, notes = {}, []
    for name, fid in keywords.items():
        if kw_names.get(fid, "").lower() == name.lower():
            out[name] = fid
        elif name.lower() in by_name:
            out[name] = by_name[name.lower()]
            notes.append(f"{name}: {fid:06X} is {kw_names.get(fid, 'not a keyword')!r}; using {out[name]:06X}")
        else:
            raise PlanetError(f"keyword {name} not found (expected {fid:06X})")
    return out, notes


def free_position(base, taken, offset=STAR_OFFSET_PC, gap=MIN_STAR_GAP_PC):
    pos = tuple(b + o for b, o in zip(base, offset))
    near = [(math.dist(pos, p), p) for p in taken if p is not None]
    closest = min(near)[0] if near else math.inf
    if closest < gap:
        raise PlanetError(f"star position {pos} is {closest:.3f} pc from another star (at least {gap} wanted)")
    return pos, closest


def build_master(sf, opts=None, other_stars=()):
    """FO4SFPlanet.esm's records from Starfield.esm (an esm.Plugin). opts: star, planet (template names), star_name,
    planet_name, system_id, planet_id, no_fauna, no_flora, star_offset. other_stars: [(source, system id,
    position)] of the other plugins in Data (census.plugin_stars), checked for clashes too.
    Returns (esm.PluginWriter, report dict). Raises PlanetError on anything unexpected."""
    o = {"star": DEFAULT_STAR, "planet": DEFAULT_PLANET, "star_name": DEFAULT_STAR_NAME,
         "planet_name": DEFAULT_PLANET_NAME, "system_id": DEFAULT_SYSTEM_ID, "planet_id": DEFAULT_PLANET_ID,
         "no_fauna": True, "no_flora": True, "star_offset": STAR_OFFSET_PC}
    o.update(opts or {})
    if sf.masters:
        raise PlanetError(f"{sf.path} has masters {sf.masters}: the template must be Starfield.esm itself")
    kw_names = keyword_edids(sf)
    kw, kw_notes = check_keywords(kw_names)
    universe = [r for r in sf.records("LCTN", [b"LCTN"]) if r.formid == UNIVERSE]
    if not universe or universe[0].edid.lower() != UNIVERSE_EDID.lower():
        raise PlanetError(f"LCTN {UNIVERSE:06X} is {universe[0].edid if universe else 'missing'!r}, not {UNIVERSE_EDID}")
    star_src = find_star(sf, o["star"])
    planet_src = find_planet(sf, o["planet"])
    all_stars = stars(sf)
    ids = {}
    for fid, edid, name, sid, pos in all_stars:
        ids.setdefault(sid, []).append(f"Starfield.esm {edid or fid_hex(fid)}")
    for source, sid, pos in other_stars:
        ids.setdefault(sid, []).append(source)
    if o["system_id"] in ids:
        raise PlanetError(f"system id {o['system_id']:#x} is taken by {ids[o['system_id']]}")
    sys_planets = [p for p in planets(sf) if p[3] and p[3][0] == o["system_id"]]
    if sys_planets:
        raise PlanetError(f"system id {o['system_id']:#x} already has planets {[p[1] for p in sys_planets]}")
    taken = [p for _, _, _, _, p in all_stars] + [p for _, _, p in other_stars]
    position, gap = free_position(star_position(star_src), taken, o["star_offset"])

    w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
    own = w.own
    star_tag, planet_tag = tag(o["star_name"]), tag(o["planet_name"])
    sys_edid = f"S{star_tag}"
    pl_edid = f"S{star_tag}_P{planet_tag}"
    star = clone_star(star_src, own(STAR), star_tag, o["star_name"], o["system_id"], position)
    w.add(star)
    # vanilla templates for the location DATA: the template star's system location and the template planet's
    # planet / orbit / surface locations (same XNAM / YNAM and keyword)
    t_sys = system_locations(sf, star_system_id(star_src))
    p_sys, _, p_id = galaxy(planet_src)
    t_pl = system_locations(sf, p_sys) if p_sys != star_system_id(star_src) else t_sys

    def template(locs, keyword, ynam):
        for fid, edid, y, kws, data, parent, rec in locs:
            if keyword in kws and (ynam is None or y == ynam) and data is not None and len(data) == 8:
                return rec
        return None

    plan = [(SYSTEM_LOC, sys_edid, o["star_name"], [kw["LocTypeStarSystem"]], UNIVERSE, 0,
             template(t_sys, kw["LocTypeStarSystem"], None)),
            (PLANET_LOC, pl_edid, o["planet_name"], [kw["LocTypePlanet"], kw["LocTypeMajorOrbital"]], own(SYSTEM_LOC),
             o["planet_id"], template(t_pl, kw["LocTypePlanet"], p_id)),
            (ORBIT_LOC, pl_edid + "_Orbit", o["planet_name"], [kw["LocTypeOrbit"]], own(PLANET_LOC), o["planet_id"],
             template(t_pl, kw["LocTypeOrbit"], p_id)),
            (SURFACE_LOC, pl_edid + "_Surface", o["planet_name"], [kw["LocTypeSurface"]], own(PLANET_LOC),
             o["planet_id"], template(t_pl, kw["LocTypeSurface"], p_id))]
    locs = []
    for local, edid, name, kws, parent, ynam, tmpl in plan:
        data = tmpl.get(b"DATA") if tmpl is not None else DEFAULT_LOCATION_DATA
        version = tmpl.version if tmpl is not None else star_src.version
        rec = new_location(own(local), edid, name, kws, parent, o["system_id"], ynam, data, version)
        w.add(rec)
        locs.append({"formid": fid_hex(rec.formid), "edid": edid, "parent": fid_hex(parent),
                     "keywords": [kw_names.get(k, fid_hex(k)) for k in kws], "ynam": ynam, "data": data.hex(),
                     "data_from": f"{tmpl.edid} {fid_hex(tmpl.formid)}" if tmpl is not None else "default"})
    planet, changes = clone_planet(planet_src, own(PLANET), f"{planet_tag}PlanetData", o["planet_name"],
                                   o["system_id"], o["planet_id"], 0, o["no_fauna"], o["no_flora"])
    w.add(planet)
    report = {
        "master": MASTER, "system_id": hex(o["system_id"]), "planet_id": o["planet_id"],
        "star": {"formid": fid_hex(star.formid), "edid": star.edid, "name": o["star_name"],
                 "from": describe_star(star_src), "position_pc": list(position), "nearest_star_pc": gap},
        "planet": {"formid": fid_hex(planet.formid), "edid": planet.edid, "name": o["planet_name"],
                   "from": describe_planet(planet_src, kw_names), "changes": changes},
        "locations": locs, "keywords": {k: fid_hex(v) for k, v in kw.items()}, "keyword_notes": kw_notes,
        "universe": fid_hex(UNIVERSE),
        "template_locations": {
            "star_system": [(fid_hex(f), e, y, [kw_names.get(k, fid_hex(k)) for k in ks], d.hex() if d else None,
                             fid_hex(p) if p is not None else None) for f, e, y, ks, d, p, _ in t_sys],
            "planet_system": [(fid_hex(f), e, y, [kw_names.get(k, fid_hex(k)) for k in ks], d.hex() if d else None,
                               fid_hex(p) if p is not None else None) for f, e, y, ks, d, p, _ in t_pl
                              if y == p_id]},
        "stars_checked": len(all_stars) + len(other_stars),
    }
    return w, report


def build_registration(master_path, world_plugin, world_local, latitude=0.0, longitude=0.0):
    """FO4SFPlanetProbe_Reg.esm's writer: our planet (read back from the written master) registering the world
    `world_local` of `world_plugin` at (latitude, longitude) radians."""
    with esm.Plugin(master_path) as m:
        if m.masters != ["Starfield.esm"]:
            raise PlanetError(f"{master_path} has masters {m.masters}, expected ['Starfield.esm']")
        own = [r for r in m.records("PNDT", [b"PNDT"]) if r.formid == (1 << 24) | PLANET]
        if len(own) != 1:
            raise PlanetError(f"{master_path} has no planet {PLANET:#x}")
        planet = own[0]
    w = esm.PluginWriter(["Starfield.esm", MASTER, world_plugin], esm.ESM)
    world = (2 << 24) | (world_local & 0xFFFFFF)
    w.add(registration_record(planet, (1 << 24) | PLANET, [(latitude, longitude, world)]))
    return w


# ------------------------------------------------------------------------------------------------ offline check
def check_master(path, system_id=DEFAULT_SYSTEM_ID, planet_id=DEFAULT_PLANET_ID, star_name=DEFAULT_STAR_NAME,
                 planet_name=DEFAULT_PLANET_NAME):
    """Problems of a written planet master ([] = none) and a summary. Reads it back with the raw reader. Every FULL
    must be our plain name (the system location's the star's, the other locations' the planet's): a string id left
    from the localized original would pass a plain-string test, since an id below 0x01000000 ends in a zero byte."""
    problems, summary = [], {}
    with esm.Plugin(path) as p:
        if p.masters != ["Starfield.esm"]:
            problems.append(f"masters {p.masters}")
        if p.flags & esm.LOCALIZED:
            problems.append("the plugin is flagged localized")
        recs = {}
        for g in ("STDT", "LCTN", "PNDT"):
            for r in p.records(g):
                recs[r.formid] = r
        own = lambda local: (1 << 24) | local  # noqa: E731
        want = {own(STAR): b"STDT", own(SYSTEM_LOC): b"LCTN", own(PLANET_LOC): b"LCTN", own(ORBIT_LOC): b"LCTN",
                own(SURFACE_LOC): b"LCTN", own(PLANET): b"PNDT"}
        for fid, sig in want.items():
            if fid not in recs or recs[fid].sig != sig:
                problems.append(f"{sig.decode()} {fid:08X} missing")
        extra = sorted(set(recs) - set(want))
        if extra:
            problems.append(f"unexpected records {[fid_hex(f) for f in extra]}")
        if problems:
            return problems, summary
        star = recs[own(STAR)]
        if star_system_id(star) != system_id:
            problems.append(f"star DNAM {star_system_id(star):#x}")
        if star.flags & STARTS_HIDDEN:
            problems.append("star starts hidden")
        parents = {own(SYSTEM_LOC): UNIVERSE, own(PLANET_LOC): own(SYSTEM_LOC), own(ORBIT_LOC): own(PLANET_LOC),
                   own(SURFACE_LOC): own(PLANET_LOC)}
        for fid, parent in parents.items():
            r = recs[fid]
            x, y = location_ids(r)
            want_y = 0 if fid == own(SYSTEM_LOC) else planet_id
            if u32(r.get(b"PNAM")) != parent:
                problems.append(f"{r.edid}: parent {u32(r.get(b'PNAM')):08X}, expected {parent:08X}")
            if x != system_id or y != want_y:
                problems.append(f"{r.edid}: XNAM/YNAM {x}/{y}, expected {system_id}/{want_y}")
            if len(r.get(b"DATA") or b"") != 8:
                problems.append(f"{r.edid}: DATA not 8 bytes")
            problems += names_problems(r.edid, r.subs, star_name if fid == own(SYSTEM_LOC) else planet_name)
        planet = recs[own(PLANET)]
        g = galaxy(planet)
        if g != (system_id, 0, planet_id):
            problems.append(f"planet GNAM {g}")
        if master_worldspaces(planet):
            problems.append("planet lists master worldspaces (the registration plugin does that)")
        problems += names_problems("star", star.subs, star_name)
        problems += names_problems("planet", planet.subs, planet_name)
        biomes(planet)                                         # raises on a bad PPBD
        summary = {"star": describe_star(star), "planet": describe_planet(planet),
                   "locations": [(fid_hex(f), recs[f].edid) for f in parents]}
    return problems, summary


def names_problems(label, subs, name):
    """The problems of a record's FULL fields against our name: none at all, or any other bytes."""
    names = full_names(subs)
    if not names:
        return [f"{label}: no FULL"]
    want = esm.zbytes(name)
    return [f"{label}: FULL{' in ' + c if c else ''} is {d.hex()}, not {name!r}" for c, d in names if d != want]


def check_registration(path, world_plugin, world_local, master_path=None):
    problems = []
    with esm.Plugin(path) as p:
        if p.masters != ["Starfield.esm", MASTER, world_plugin]:
            problems.append(f"masters {p.masters}")
        recs = list(p.records("PNDT"))
        if len(recs) != 1 or recs[0].formid != (1 << 24) | PLANET:
            problems.append(f"records {[fid_hex(r.formid) for r in recs]}")
            return problems, {}
        ws = master_worldspaces(recs[0])
        want = (2 << 24) | world_local
        if len(ws) != 1 or ws[0][2] != want:
            problems.append(f"master worldspaces {ws}, expected one entry for {want:08X}")
        if master_path:
            with esm.Plugin(master_path) as m:
                base = [r for r in m.records("PNDT") if r.formid == (1 << 24) | PLANET]
            at = components_end(recs[0].subs)
            stripped = recs[0].subs[:at] + recs[0].subs[at + 1:]
            if not base or recs[0].subs[at][0] != b"CNAM" or stripped != base[0].subs:
                problems.append("the registration's planet differs from the master's beyond the added CNAM")
        return problems, {"worldspaces": [(lat, lon, fid_hex(w)) for lat, lon, w in ws]}
