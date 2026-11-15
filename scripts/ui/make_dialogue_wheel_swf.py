"""Four-option DialogueMenu stand-in (FAL-865): four named slots, no Flash tool, no font file, no ActionScript.

usage: python scripts/ui/make_dialogue_wheel_swf.py --out <file.swf>
       python scripts/ui/make_dialogue_wheel_swf.py --read <file.swf>

KEEP the host DialogueMenu class; this file is only the movie. REPLACE is the twin at Interface/DialogueMenu.swf
(make_concord_talk.py). Nothing converted from the game: the four prompts are ONE TWO THREE FOUR, not Fallout lines.
The instance names (fo4sfOptN/E/S/W) are ours until a PC read names the host movie's children. Same SWF shape as
make_probe_swf.py: compressed CWS, version 12, ActionScript 3 flag, no code, no background colour. Deterministic.
"""
import argparse
import json
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_probe_swf as swf  # noqa: E402

SLOTS = ("N", "E", "S", "W")
PLACEHOLDERS = ("ONE", "TWO", "THREE", "FOUR")
SLOT_NAMES = tuple(f"fo4sfOpt{s}" for s in SLOTS)
HUB_LABEL = "FOUR OPTIONS"
WHEEL_GREEN = swf.PIPBOY_GREEN
INK = swf.INK
HUB_ID, HUB_LABEL_ID, FONT_ID = 1, 2, 3
# each slot: rect, edit text, sprite
SLOT_RECT0, SLOT_TEXT0, SLOT_SPRITE0 = 10, 11, 12


def slot_boxes(W, H):
    """N/E/S/W boxes in twips around the stage centre. Width 420 px, height 90 px."""
    cx, cy = W // 2, H // 2
    bw, bh = 420 * swf.TWIPS, 90 * swf.TWIPS
    arm = 280 * swf.TWIPS
    return {
        "N": (cx - bw // 2, cy - arm - bh, bw, bh),
        "E": (cx + arm, cy - bh // 2, bw, bh),
        "S": (cx - bw // 2, cy + arm, bw, bh),
        "W": (cx - arm - bw, cy - bh // 2, bw, bh),
    }


def hub_box(W, H):
    bw, bh = 360 * swf.TWIPS, 90 * swf.TWIPS
    return (W // 2 - bw // 2, H // 2 - bh // 2, bw, bh)


def movie_bytes(width=1920, height=1080, color=WHEEL_GREEN, ink=INK, compressed=True):
    if width <= 0 or height <= 0:
        raise swf.SwfError("the stage needs a positive size")
    W, H = width * swf.TWIPS, height * swf.TWIPS
    hub = hub_box(W, H)
    boxes = slot_boxes(W, H)
    body = swf.rect(0, W, 0, H) + struct.pack("<HH", swf.FRAME_RATE << 8, 1)
    body += swf.tag(swf.FILE_ATTRIBUTES, bytes([swf.AS3, 0, 0, 0]))
    body += swf.define_shape3(HUB_ID, [hub], color)
    body += swf.define_shape3(HUB_LABEL_ID, swf.label_squares(HUB_LABEL, hub), ink)
    body += swf.define_font3(FONT_ID)
    places = [swf.place_object2(HUB_ID, 1), swf.place_object2(HUB_LABEL_ID, 2)]
    height_px = swf.FIELD_PX * swf.TWIPS
    for i, slot in enumerate(SLOTS):
        rect_id = SLOT_RECT0 + i * 3
        text_id = SLOT_TEXT0 + i * 3
        sprite_id = SLOT_SPRITE0 + i * 3
        box = boxes[slot]
        body += swf.define_shape3(rect_id, [box], ink)
        body += swf.define_edit_text(text_id, box, FONT_ID, height_px, color, PLACEHOLDERS[i])
        body += swf.define_sprite(sprite_id, [swf.place_object2(rect_id, 1), swf.place_object2(text_id, 2)])
        places.append(swf.place_named(sprite_id, 3 + i, SLOT_NAMES[i]))
    body += b"".join(places) + swf.tag(swf.SHOW_FRAME) + swf.tag(swf.END)
    length = 8 + len(body)
    if compressed:
        return b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", length) + zlib.compress(body, 9)
    return b"FWS" + bytes([swf.VERSION]) + struct.pack("<I", length) + body


def write_movie(path, **kw):
    data = movie_bytes(**kw)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return data


def named_places(movie):
    """Instance names on PlaceObject2 tags, in tag order."""
    return [t["instance"] for t in movie["tags"] if t.get("instance")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--out", help="write the movie here; nothing is written into the repo")
    g.add_argument("--read", help="print the header and tags as JSON")
    ap.add_argument("--uncompressed", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.read:
            print(json.dumps(swf.summary(swf.read_movie(a.read)), indent=2))
        else:
            data = write_movie(a.out, compressed=not a.uncompressed)
            print(f"wrote {a.out} ({len(data)} bytes)")
    except (swf.SwfError, OSError) as e:
        print(f"make_dialogue_wheel_swf: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
