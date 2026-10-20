"""Starfield map-marker LCSR layout (docs/terrain/map-markers.md).

Map markers are REFR of STAT MapMarker (00000010) with an empty XMRK. A Location points at them with LCSR
(MasterSpecialReferences) in a 5 x u32 stride and usually LCID (MasterInitiallyDisabledReferences) = that REFR.
Synthetic only: no game files.
"""
import math
import struct

MAPMARKER_STAT = 0x00000010
MAPMARKER_REF_TYPE = 0x0002271F
SHIP_LANDING_MARKER_REF_TYPE = 0x00009105
SHIP_LANDING_MARKER_REF_TYPE_LARGE = 0x00009102
LOC_TYPE_OVERLAY = 0x002CA99D

# LC172WorldLocation 003807BE, Starfield.esm 1.16.244 (raw LCSR / LCID walk).
LC172_WORLD = 0x0002DF8C
LC172_LOCATION = 0x003807BE
LC172_MAP_MARKER = 0x003E5E12
LC172_FNAM = 0x1B
LC172_TNAM = 0x17
LANDMARK_SNOW_GLOBE_REF_TYPE = 0x00009A42

LCSR_STRIDE = 20
LCSR_PAD = 0
LCSR_TAIL = 0xFFFFFFFF


def parse_lcsr(data):
    """Decode an LCSR payload into dicts {lcrt, refr, wrld, pad, tail}."""
    if len(data) % LCSR_STRIDE:
        raise ValueError(f"LCSR length {len(data)} is not a multiple of {LCSR_STRIDE}")
    out = []
    for i in range(0, len(data), LCSR_STRIDE):
        lcrt, refr, wrld, pad, tail = struct.unpack_from("<5I", data, i)
        out.append({"lcrt": lcrt, "refr": refr, "wrld": wrld, "pad": pad, "tail": tail})
    return out


def pack_lcsr(entries):
    """Encode LCSR dicts (parse_lcsr output, or lcrt/refr/wrld with default pad/tail)."""
    chunks = []
    for e in entries:
        chunks.append(struct.pack(
            "<5I",
            e["lcrt"],
            e["refr"],
            e["wrld"],
            e.get("pad", LCSR_PAD),
            e.get("tail", LCSR_TAIL),
        ))
    return b"".join(chunks)


def map_marker_lcsr(refr, wrld):
    """One MapMarkerRefType LCSR row for a marker REFR in wrld."""
    return pack_lcsr([{"lcrt": MAPMARKER_REF_TYPE, "refr": refr, "wrld": wrld}])


# Commonwealth map markers of the core overlay (docs/terrain/map-markers.md, "Commonwealth markers"). FO4 positions in
# FO4 units from Fallout4.esm (the landmarks scripts/terrain/make_cw_overlays.py already uses: the Sanctuary, Vault 111
# and Concord map-marker REFRs). Red Rocket sits on the COC arrival (the flat vertex at the station), so its icon and
# the tested spawn are one place. The overlay's local frame is the CW frame: position = FO4 position / 70.
FO4_UNITS_PER_M = 70.0
COMMONWEALTH_MARKERS = (
    # (tag, map name, FO4 source REFR, FO4 x, FO4 y); None position = the COC arrival
    ("RedRocket", "Red Rocket Truck Stop", 0x000211C0, None, None),
    ("Sanctuary", "Sanctuary Hills", 0x00072A48, -80768.19, 88174.80),
    ("Vault111", "Vault 111", 0x0009F272, -89271.98, 91369.30),
    ("Concord", "Concord", 0x00082138, -60286.01, 72977.79),
)
EDGE_KEEP_M = 200.0     # two cells inside the overlay, as the ray plans keep their probes


def sf_cell(x, y, cell_m=100.0):
    return [int(math.floor(x / cell_m)), int(math.floor(y / cell_m))]


def overlay_markers(spawn, bounds_m, ground, markers=COMMONWEALTH_MARKERS, keep=EDGE_KEEP_M):
    """The overlay's "map_markers" params entries: {tag, name, src, pos [x, y, z], cell}, local metres.

    spawn: the COC marker position (x, y, z); bounds_m: (min, max) of the overlay's square in local metres; ground:
    f(x, y) -> terrain height (the BTD). A marker outside the overlay (less than `keep` from its edge) raises: the core
    always contains these four, and a silent drop would ship a map without one of them."""
    lo, hi = bounds_m
    out = []
    for tag, name, src, fx, fy in markers:
        if fx is None:
            x, y, z = (float(v) for v in spawn)
        else:
            x, y = fx / FO4_UNITS_PER_M, fy / FO4_UNITS_PER_M
            if not (lo + keep <= x <= hi - keep and lo + keep <= y <= hi - keep):
                raise ValueError(f"map marker {tag} at ({x:.1f}, {y:.1f}) m is not {keep:.0f} m inside the overlay "
                                 f"[{lo}, {hi}]")
            z = float(ground(x, y))
        out.append({"tag": tag, "name": name, "src": f"{src:06X}:Fallout4.esm",
                    "pos": [round(x, 4), round(y, 4), round(z, 4)], "cell": sf_cell(x, y)})
    if len({m["tag"] for m in out}) != len(out):
        raise ValueError("map marker tags repeat")
    return out
