"""DialogueMenu data-shuttle bind contract (FAL-865, after PC PARTIAL at 44ba71ac).

The host fills DialogueList_mc through the movie's own AS3 (BSUIDataManager / UIDataShuttleConnector).
A no-DoABC named-clip twin cannot take that path. Payload field names are UNREAD: this module does not
guess them. Nothing converted. Four display slots stay ours (fo4sfOpt*) until a later bind names host rows.
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "ui"))
import make_probe_swf as swf  # noqa: E402
import dialogue_menu_host as host  # noqa: E402

# SWF tag codes (SWF 9+). DoABC = 72, DoABC2 = 82.
DOABC, DOABC2 = 72, 82
ABC_TAGS = (DOABC, DOABC2)

KEEP_SHUTTLE = host.KEEP_SHUTTLE
HOST_ROOT = host.HOST_ROOT
HOST_LIST = host.HOST_LIST
HOST_LIST_ENTRY = host.HOST_LIST_ENTRY
KEEP_EVENTS = host.KEEP_EVENTS
SLOT_ORDER = ("N", "E", "S", "W")
MAP_ROWS = 4
# UNREAD: names of fields on the shuttle payload. A later PC dump fills this tuple; do not invent it.
PAYLOAD_FIELDS = ()
ABC_REQUIRED = True
NATIVE_BIND_ALTERNATIVE = True  # listed, not this slice


class ShuttleError(ValueError):
    pass


def has_doabc(movie):
    """True when the SWF carries a DoABC / DoABC2 tag (real AS3, not only the FileAttributes bit)."""
    tags = movie["tags"] if isinstance(movie, dict) else swf.read_movie(movie)["tags"]
    return any(t.get("code") in ABC_TAGS for t in tags)


def shuttle_bind():
    return {
        "keep_menu": host.KEEP_MENU,
        "keep_events": list(KEEP_EVENTS),
        "keep_shuttle": list(KEEP_SHUTTLE),
        "host_root": HOST_ROOT,
        "host_list": HOST_LIST,
        "host_list_entry": HOST_LIST_ENTRY,
        "map_rows": MAP_ROWS,
        "slot_order": list(SLOT_ORDER),
        "payload_fields": list(PAYLOAD_FIELDS),
        "payload_unread": PAYLOAD_FIELDS == (),
        "abc_required": ABC_REQUIRED,
        "kill_no_as3_named_clips": True,
        "native_bind_alternative": NATIVE_BIND_ALTERNATIVE,
        "fo4_slots_are_not_the_bind": True,
    }


def check(payload):
    if not payload.get("abc_required"):
        raise ShuttleError("the next movie needs DoABC; the FileAttributes AS3 bit is not enough")
    if not payload.get("kill_no_as3_named_clips"):
        raise ShuttleError("the no-AS3 named-clip stand-in is killed")
    if payload.get("keep_shuttle") != list(KEEP_SHUTTLE):
        raise ShuttleError("KEEP the host data shuttle")
    if payload.get("host_list") != HOST_LIST:
        raise ShuttleError(f"host list is {HOST_LIST}")
    if payload.get("map_rows") != MAP_ROWS:
        raise ShuttleError("this slice maps four list rows")
    if payload.get("slot_order") != list(SLOT_ORDER):
        raise ShuttleError("slot order is N E S W")
    if payload.get("payload_fields"):
        raise ShuttleError("payload field names are UNREAD; do not invent them")
    if not payload.get("payload_unread"):
        raise ShuttleError("payload field names are UNREAD")
    if not payload.get("fo4_slots_are_not_the_bind"):
        raise ShuttleError("Fallout 4 Question/Neutral/Negative/Positive is not the host bind")
    return payload


def refuse_install_reason(movie):
    """None if the movie may be packed as the DialogueMenu twin; else a short refuse string."""
    parsed = swf.read_movie(movie) if not isinstance(movie, dict) else movie
    if not has_doabc(parsed):
        return "no DoABC: the no-AS3 named-clip movie is killed (host fills via the data shuttle)"
    return None
