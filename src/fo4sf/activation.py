"""Helpers to extract activation-related fields from a REFR field list.

Uses existing fo4land.iter_subrecords and fo4station.vmad_scripts where possible.
"""
import struct
from fo4sf import fo4land, fo4station

def parse_activation(fields):
    """Return dict with activation-relevant data from REFR fields.
    
    Keys: scripts (list of names or error), linked_refs (list of (keyword_or_0, target_fid)),
    activate_parents (list of (parent_fid, delay)), enable_parent (fid, flags) or None,
    xapd (ubyte flags or None).
    """
    out = {
        "scripts": [],
        "linked_refs": [],
        "activate_parents": [],
        "enable_parent": None,
        "xapd": None,
    }
    for sig, d in fields:
        if sig == b"VMAD":
            try:
                out["scripts"] = fo4station.vmad_scripts(d)
            except ValueError as e:
                out["scripts"] = [f"error: {e}"]
        elif sig == b"XLKR" and len(d) >= 8:
            kw, target = struct.unpack_from("<II", d)
            out["linked_refs"].append((kw, target))
        elif sig == b"XAPR" and len(d) >= 8:
            parent, delay = struct.unpack_from("<If", d)
            out["activate_parents"].append((parent, delay))
        elif sig == b"XESP" and len(d) >= 8:
            parent, flags = struct.unpack_from("<II", d)
            out["enable_parent"] = (parent, flags)
        elif sig == b"XAPD" and len(d) >= 1:
            out["xapd"] = d[0]
    return out
