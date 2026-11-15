"""Overlay four slots on the player's DialogueMenu movie (FAL-865).

The installer copies Interface/DialogueMenu.swf from the player's Starfield archives at install time and
adds fo4sfOptN/E/S/W on the DialogueMenu sprite, next to DialogueList_mc. Host ABC stays. Nothing of the
game is written into Git. Replacing the host movie with a movie of our own is killed (PC FAIL 48a3eb3d,
69ee810a).
"""
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "ui"))
sys.path.insert(0, HERE)
from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402
import dialogue_menu_host as host  # noqa: E402
import make_dialogue_wheel_swf as wheel  # noqa: E402
import make_probe_swf as swf  # noqa: E402

HOST_PATH = host.host_names()["host_movie"]
HOST_ARCHIVE_HINT = "Starfield - Interface.ba2"
DEFINE_IDS = (
    2, 6, 7, 11, 14, 20, 21, 22, 32, 33, 34, 35, 36, 37, 39, 46, 48, 73, 75, 83, 84, 87, 90, 91,
)


class OverlayError(ValueError):
    pass


def overlay_plan():
    return {
        "document_class": None,
        "root_frame_count": 1,
        "dialogue_menu_frame_count": 1,
        "menu_mc_role": "child",
        "root_instances": [host.HOST_ROOT],
        "menu_mc_class": host.KEEP_MENU,
        "menu_mc_children": list(host.HOST_CHILDREN),
        "dialogue_list_first_frame": 1,
        "slots_go": "inside Menu_mc next to DialogueList_mc",
        "shuttle_in_movie": True,
        "kill_replace_host_movie": True,
        "kill_root_named_menu_mc": True,
        "exported": [
            "DialogueMenu", "DialogueList", "DialogueScrollingListEntry", "DialogueButtonBar",
            "PersuasionList", "PersuasionListEntry", "PersuasionData",
        ],
    }


def check_overlay_plan(payload):
    if payload.get("document_class") is not None:
        raise OverlayError("host document class is none; the root is a plain timeline")
    if payload.get("menu_mc_role") != "child":
        raise OverlayError("Menu_mc is a child of the root, not the document")
    if not payload.get("shuttle_in_movie"):
        raise OverlayError("shuttle classes are compiled into the host movie")
    if not payload.get("kill_root_named_menu_mc"):
        raise OverlayError("naming the document Menu_mc is not the host layout")
    if payload.get("slots_go") != "inside Menu_mc next to DialogueList_mc":
        raise OverlayError("four slots go on Menu_mc next to DialogueList_mc")
    return payload


def root_instances(movie):
    return [t.get("instance") for t in movie.get("tags") or [] if t.get("instance")]


def sprite_instances(movie):
    out = []
    for t in movie.get("tags") or []:
        if t.get("code") != swf.DEFINE_SPRITE:
            continue
        names = [c.get("instance") for c in t.get("tags") or [] if c.get("instance")]
        out.append({"id": t.get("id"), "frame_count": t.get("frame_count"), "instances": names})
    return out


def inspect_host(movie):
    if isinstance(movie, (bytes, bytearray, str)):
        movie = swf.read_movie(movie)
    root = root_instances(movie)
    sprites = sprite_instances(movie)
    list_sprite = next((s for s in sprites if host.HOST_LIST in s["instances"]), None)
    return {
        "document_class": None,
        "root_frame_count": movie.get("frame_count"),
        "menu_mc_role": "child" if host.HOST_ROOT in root else "missing",
        "root_instances": root,
        "menu_mc_children": (list_sprite or {}).get("instances") or [],
        "dialogue_list_sprite_id": (list_sprite or {}).get("id"),
        "shuttle_in_movie": True,
        "has_dialogue_list": list_sprite is not None,
    }


def _raw_tags(blob, pos=0):
    tags = []
    while pos < len(blob):
        code_len = struct.unpack_from("<H", blob, pos)[0]
        code, n = code_len >> 6, code_len & 0x3F
        pos += 2
        if n == 0x3F:
            n = struct.unpack_from("<I", blob, pos)[0]
            pos += 4
        data = blob[pos:pos + n]
        if len(data) != n:
            raise OverlayError(f"tag {code} runs past the end")
        pos += n
        tags.append((code, data))
        if code == swf.END:
            break
    return tags


def _place_instance(data):
    parsed = swf.read_place(data)
    return parsed.get("instance"), parsed.get("depth")


def next_character_id(tags):
    """One past the highest Define* character id, any sprite depth."""
    used = [0]

    def walk(items):
        for code, data in items:
            if code in DEFINE_IDS and len(data) >= 2:
                used.append(struct.unpack_from("<H", data, 0)[0])
            if code == swf.DEFINE_SPRITE and len(data) >= 4:
                walk(_raw_tags(data, 4))

    walk(tags)
    return max(used) + 1


def overlay_inject(host_bytes, width=1920, height=1080):
    """Keep host ABC; add fo4sfOpt* on the sprite that already has DialogueList_mc."""
    raw = bytes(host_bytes)
    if raw[:3] not in (b"CWS", b"FWS"):
        raise OverlayError("host is not a SWF")
    body = zlib.decompress(raw[8:]) if raw[:3] == b"CWS" else raw[8:]
    r = swf.BitReader(body)
    frame = swf.read_rect(r)
    pos = r.align()
    rate, count = struct.unpack_from("<HH", body, pos)
    pos += 4
    header = body[:pos]
    tags = _raw_tags(body, pos)
    target = None
    for i, (code, data) in enumerate(tags):
        if code != swf.DEFINE_SPRITE:
            continue
        nested = _raw_tags(data, 4)
        if any(_place_instance(nd)[0] == host.HOST_LIST for nc, nd in nested if nc == swf.PLACE_OBJECT2):
            target = i
            break
    if target is None:
        raise OverlayError("host has no sprite that places DialogueList_mc")
    sprite_id, frame_count = struct.unpack_from("<HH", tags[target][1], 0)
    nested = _raw_tags(tags[target][1], 4)
    depths = [d for nc, nd in nested if nc == swf.PLACE_OBJECT2 for d in [_place_instance(nd)[1]] if d]
    depth = (max(depths) if depths else 0) + 1
    W, H = width * swf.TWIPS, height * swf.TWIPS
    boxes = wheel.slot_boxes(W, H)
    extras = []
    places = []
    cid = next_character_id(tags)
    for i, name in enumerate(wheel.SLOT_NAMES):
        box = boxes[wheel.SLOTS[i]]
        extras.append(swf.define_shape3(cid, [box], swf.PIPBOY_GREEN))
        places.append(swf.place_named(cid, depth + i, name))
        cid += 1
    new_nested = []
    inserted = False
    for nc, nd in nested:
        if nc == swf.SHOW_FRAME and not inserted:
            new_nested.extend(places)
            inserted = True
        new_nested.append(swf.tag(nc, nd))
    if not inserted:
        raise OverlayError("DialogueMenu sprite has no ShowFrame")
    new_sprite = swf.tag(swf.DEFINE_SPRITE, struct.pack("<HH", sprite_id, frame_count) + b"".join(new_nested))
    out_tags = []
    for i, (code, data) in enumerate(tags):
        if i == target:
            out_tags.extend(extras)
            out_tags.append(new_sprite)
        else:
            out_tags.append(swf.tag(code, data))
    new_body = header + b"".join(out_tags)
    length = 8 + len(new_body)
    return b"CWS" + bytes([raw[3]]) + struct.pack("<I", length) + zlib.compress(new_body, 9)


def archive_search_order(names):
    """Starfield - Interface.ba2 first when present; never first-sorted AAA-mod.ba2."""
    ba2 = [n for n in names if n.lower().endswith(".ba2")]
    hint = [n for n in ba2 if n.lower() == HOST_ARCHIVE_HINT.lower()]
    rest = sorted(n for n in ba2 if n.lower() != HOST_ARCHIVE_HINT.lower())
    return hint + rest


def extract_host_movie(starfield):
    """Player's Interface/DialogueMenu.swf from their archives. Never written to Git."""
    data = os.path.join(starfield, "Data") if os.path.basename(starfield) != "Data" else starfield
    if not os.path.isdir(data):
        raise OverlayError(f"no Data folder at {starfield}")
    last_err = None
    for name in archive_search_order(os.listdir(data)):
        path = os.path.join(data, name)
        try:
            archive = Ba2(path)
        except (Ba2Error, OSError, struct.error, ValueError) as e:
            last_err = e
            continue
        if archive.find(HOST_PATH) is None:
            continue
        return archive.read(HOST_PATH)
    raise OverlayError(f"{HOST_PATH} not in the player's archives" + (f" ({last_err})" if last_err else ""))


def refuse_own_replacement(movie):
    """None if this is a host (or host+overlay) movie; else a short refuse."""
    info = inspect_host(movie)
    if info["menu_mc_role"] != "child":
        return "Menu_mc is not a child of a plain root; do not pack a replacement movie"
    if not info["has_dialogue_list"]:
        return "host sprite must still place DialogueList_mc"
    return None
