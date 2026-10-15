"""Overlay manifest: a pinned build's manifest with the items of a partial re-conversion swapped in.

usage: python scripts/overlay_manifest.py <pinned manifest.json> <partial manifest.json> <out manifest.json> [--native-doors-only]

For a partial rebuild (docs/spikes/WP-doors-research.md, "Multi-part doors"): copy the pinned staging to a new folder,
re-convert a subset into another folder, copy its meshes/ and geometries/ over the copy, write the overlay manifest
there and run the plugin writer on it. Items are matched by source path (case-insensitive) and keep the pinned
form_index; an item whose EditorID changed, or that the pinned build does not have, stops the overlay (FormIDs are keyed
by EditorID, so a renamed item would get a new record). --native-doors-only swaps only doors that now carry their own
rig ("rig": "native"); the other re-converted items are expected to be identical and are left as pinned.
"""
import argparse
import json
import sys


def overlay(pinned, partial, native_doors_only=False):
    """(merged manifest, swapped sources). Raises ValueError on EditorID changes or items absent from the pinned build."""
    updates = {}
    for item in partial["items"]:
        if native_doors_only and (item.get("door") or {}).get("rig") != "native":
            continue
        updates[item["source"].lower()] = item
    merged = dict(pinned)
    merged["items"] = []
    swapped = []
    for item in pinned["items"]:
        new = updates.pop(item["source"].lower(), None)
        if new is None:
            merged["items"].append(item)
            continue
        if new["editor_id"] != item["editor_id"]:
            raise ValueError(f"EditorID changed for {item['source']}: {item['editor_id']} -> {new['editor_id']}")
        merged["items"].append({**new, "form_index": item["form_index"]})
        swapped.append(item["source"])
    if updates:
        raise ValueError(f"not in the pinned build: {sorted(updates)}")
    merged["overlay"] = {"swapped": swapped}
    return merged, swapped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pinned")
    ap.add_argument("partial")
    ap.add_argument("out")
    ap.add_argument("--native-doors-only", action="store_true")
    a = ap.parse_args()
    with open(a.pinned, encoding="utf-8-sig") as f:
        pinned = json.load(f)
    with open(a.partial, encoding="utf-8-sig") as f:
        partial = json.load(f)
    try:
        merged, swapped = overlay(pinned, partial, a.native_doors_only)
    except ValueError as e:
        print(f"overlay refused: {e}")
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=1)
    print(f"{len(swapped)} items swapped")
    for source in swapped:
        print("  " + source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
