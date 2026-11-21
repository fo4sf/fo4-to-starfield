"""Game-closed vanilla overlay identity read; JSON stdout only, no staging or game action.

python -I scripts/planet/read_overlay_control.py --starfield-esm <Starfield.esm>
    --world 001187EA --marker 003A866E --expect-sha256 <pinned SHA-256>

Composes the existing census world/cell/COC reader. A candidate is a static identity
pair, not proof that coc succeeds, that its marker lists, or that any runtime fix works.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.planet import census, esm, probe  # noqa: E402


def vanilla_id(text: str) -> int:
    if not re.fullmatch(r"(?:0[xX])?00[0-9a-fA-F]{6}", text):
        raise argparse.ArgumentTypeError("need eight stored hex digits in the vanilla 00 namespace")
    return int(text, 16)


def read_control(path: str, world_id: int, marker_id: int, expected_sha256: str) -> dict:
    """Only this world's file identities, from one read-only mapping pinned before/after."""
    if any(type(v) is not int or not 0 < v <= 0xFFFFFF for v in (world_id, marker_id)):
        raise ValueError("world and marker must be nonzero vanilla stored IDs")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("expected SHA-256 must be 64 hex digits")
    with esm.Plugin(path) as sf:
        before = hashlib.sha256(sf.buf).hexdigest()
        if before != expected_sha256.lower():
            raise ValueError("Starfield.esm SHA-256 does not match pinned input")
        if os.path.basename(path).lower() != "starfield.esm" or sf.masters:
            raise ValueError("need original Starfield.esm with no masters")
        # Count target headers across the file before parsing the chosen world. A duplicate
        # outside the selected world must not masquerade as a unique identity.
        hits = Counter()
        for spans in sf.groups.values():
            for start, end in spans:
                for it in sf.walk(start, end):
                    if it[0] == "REC":
                        fid = struct.unpack_from("<I", sf.buf, it[1] + 12)[0]
                        if fid in (world_id, marker_id):
                            hits[fid] += 1
        for fid in (world_id, marker_id):
            if hits[fid] != 1:
                raise ValueError(f"{fid:08X}: {hits[fid]} matches (need one)")
        items, cells, _, _ = census.world_refs(sf, world_id)
        duplicate = [fid for fid, count in Counter(x["rec"].formid for x in items).items() if count != 1]
        if duplicate:
            raise ValueError("duplicate identities in selected world")
        worlds = [x["rec"] for x in items if x["group"] == "world" and x["rec"].sig == b"WRLD"]
        if len(worlds) != 1 or census.overlay_of(worlds[0]) is None:
            raise ValueError("selected world is not a unique overlay WRLD")
        markers = [x for x in items if x["rec"].formid == marker_id]
        if len(markers) != 1:
            raise ValueError("selected marker is not in selected world")
        m = markers[0]
        rec = m["rec"]
        if (rec.sig != b"REFR" or m["group"] != "persistent" or
                not rec.flags & esm.PERSISTENT or rec.flags & 0x800 or
                census.u32_or_none(rec.get(b"NAME")) != 0x10 or rec.get(b"XMRK") is None):
            raise ValueError("need persistent, not initially-disabled REFR with MapMarker NAME and XMRK")
        by_id = {x["rec"].formid: x for x in items}
        pairs = []
        for edid, cell_id, grid, coc_id in census.coc_cells(items, cells):
            cell = by_id[int(cell_id, 16)]["rec"]
            coc = by_id[int(coc_id, 16)]
            # A named CELL plus XCLC and its actual COC ref is the existing census
            # candidate rule. Return raw DATA too; no successful runtime arrival is inferred.
            if coc["rec"].flags & 0x800:
                continue
            pairs.append({"cell": cell_id, "cell_edid": edid, "grid": grid,
                          "cell_offset": cell.offset, "cell_data_hex": (cell.get(b"DATA") or b"").hex(),
                          "coc_ref": coc_id, "coc_offset": coc["rec"].offset,
                          "coc_base": f"{probe.COC_MARKER:08X}", "coc_flags": f"{coc['rec'].flags:08X}"})
        if len({x["cell_edid"].lower() for x in pairs}) != len(pairs):
            raise ValueError("ambiguous repeated CELL EditorID among candidates")
        after = hashlib.sha256(sf.buf).hexdigest()
        if after != before:
            raise ValueError("Starfield.esm changed during read")
        return {"plugin": os.path.basename(path), "masters": sf.masters, "sha256": before, "sha256_after": after,
                "world": {"stored_id": f"{world_id:08X}", "edid": worlds[0].edid,
                          "offset": worlds[0].offset, "overlay": census.overlay_of(worlds[0])},
                "marker": {"stored_id": f"{marker_id:08X}", "offset": rec.offset,
                           "flags": f"{rec.flags:08X}", "base": "00000010", "xmrk": True,
                           "cell": census.fid(m["cell"]), "initially_disabled": False},
                "coc_candidates": pairs,
                "decision": "CANDIDATE_IDENTITY_ONLY" if pairs else "UNRESOLVED_NO_COC_CANDIDATE",
                "limits": "File identities only; no coc/listing/runtime membership/discovery/native proof."}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--starfield-esm", required=True)
    ap.add_argument("--world", required=True, type=vanilla_id)
    ap.add_argument("--marker", required=True, type=vanilla_id)
    ap.add_argument("--expect-sha256", required=True)
    a = ap.parse_args(argv)
    try:
        report = read_control(a.starfield_esm, a.world, a.marker, a.expect_sha256)
    except (OSError, ValueError, struct.error) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
