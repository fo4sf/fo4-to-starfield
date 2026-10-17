"""Starfield map-marker LCSR layout (docs/terrain/map-markers.md).

Map markers are REFR of STAT MapMarker (00000010) with an empty XMRK. A Location points at them with LCSR
(MasterSpecialReferences) in a 5 x u32 stride and usually LCID (MasterInitiallyDisabledReferences) = that REFR.
Synthetic only: no game files.
"""
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
