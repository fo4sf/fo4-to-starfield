"""DialogueMenu data-shuttle bind contract (FAL-865).

Host fills DialogueList_mc through BSUIDataManager / UIDataShuttleConnector.
PC PASS §1b (FAL-879, file read, no install) named the payload. Four slots bind
DialogueListData.aChoices[0..3].sChoiceText; select sends DialogueMenu_OnDialogueSelect
with selectedIndex = that row's uEntryID. Nothing converted. No compiled ABC here.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "ui"))
import make_probe_swf as swf  # noqa: E402
import dialogue_menu_host as host  # noqa: E402

DOABC, DOABC2 = 72, 82
ABC_TAGS = (DOABC, DOABC2)

KEEP_SHUTTLE = host.KEEP_SHUTTLE
HOST_ROOT = host.HOST_ROOT
HOST_LIST = host.HOST_LIST
HOST_LIST_ENTRY = host.HOST_LIST_ENTRY
KEEP_EVENTS = host.KEEP_EVENTS
SLOT_ORDER = ("N", "E", "S", "W")
MAP_ROWS = 4
SUBSCRIBE = "Subscribe"
# PC PASS §1b, names only. Order is the Subscribe order in the host movie.
PROVIDERS = (
    "DialogueListData",
    "PersuasionListData",
    "PersuasionPointsData",
    "DialogueData",
)
LIST_PROVIDER = "DialogueListData"
CHOICES = "aChoices"
ROW_FIELDS = ("sChoiceText", "bCanBeChosen", "bWasAlreadySaid", "uEntryID")
CHOICE_TEXT = "sChoiceText"
ENTRY_ID = "uEntryID"
SELECT_EVENT = "DialogueMenu_OnDialogueSelect"
SELECT_KEY = "selectedIndex"  # PC reading: the handler key carries uEntryID
LIST_VIS_EVENT = "DialogueMenu_OnListVisibilityChange"
LIST_VIS_KEY = "isVisible"
DIALOGUE_DATA_FIELDS = (
    "sSpeakerName",
    "uType",
    "bAutoSkip",
    "bCanExitDialogueState",
    "bClosingMenu",
    "CrewmemberData",
)
OTHER_EVENTS = (
    "DialogueMenu_RequestExit",
    "DialogueMenu_CompleteExit",
    "DialogueMenu_RequestSkipDialogue",
    "DialogueScrollingListEntry_OnRollover",
)
PAYLOAD_FIELDS = (LIST_PROVIDER, CHOICES, CHOICE_TEXT, ENTRY_ID, SELECT_KEY)
ABC_REQUIRED = True
NATIVE_BIND_ALTERNATIVE = True
NO_ROW_INDEX_FIELD = True  # list position is the index


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
        "subscribe": SUBSCRIBE,
        "host_root": HOST_ROOT,
        "host_list": HOST_LIST,
        "host_list_entry": HOST_LIST_ENTRY,
        "providers": list(PROVIDERS),
        "list_provider": LIST_PROVIDER,
        "choices": CHOICES,
        "row_fields": list(ROW_FIELDS),
        "choice_text": CHOICE_TEXT,
        "entry_id": ENTRY_ID,
        "select_event": SELECT_EVENT,
        "select_key": SELECT_KEY,
        "list_vis_event": LIST_VIS_EVENT,
        "list_vis_key": LIST_VIS_KEY,
        "dialogue_data_fields": list(DIALOGUE_DATA_FIELDS),
        "other_events": list(OTHER_EVENTS),
        "map_rows": MAP_ROWS,
        "slot_order": list(SLOT_ORDER),
        "payload_fields": list(PAYLOAD_FIELDS),
        "payload_unread": False,
        "no_row_index_field": NO_ROW_INDEX_FIELD,
        "abc_required": ABC_REQUIRED,
        "kill_no_as3_named_clips": True,
        "native_bind_alternative": NATIVE_BIND_ALTERNATIVE,
        "fo4_slots_are_not_the_bind": True,
        "compiled_movie": False,
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
    if payload.get("payload_unread"):
        raise ShuttleError("payload field names were listed on FAL-879")
    if payload.get("payload_fields") != list(PAYLOAD_FIELDS):
        raise ShuttleError("payload fields must be DialogueListData aChoices sChoiceText uEntryID selectedIndex")
    if payload.get("list_provider") != LIST_PROVIDER or payload.get("choices") != CHOICES:
        raise ShuttleError("rows are DialogueListData.aChoices")
    if payload.get("choice_text") != CHOICE_TEXT:
        raise ShuttleError("prompt text is sChoiceText")
    if payload.get("select_event") != SELECT_EVENT or payload.get("select_key") != SELECT_KEY:
        raise ShuttleError("select is DialogueMenu_OnDialogueSelect selectedIndex = uEntryID")
    if payload.get("entry_id") != ENTRY_ID:
        raise ShuttleError("select id is uEntryID")
    if not payload.get("no_row_index_field"):
        raise ShuttleError("there is no index field on the row")
    if not payload.get("fo4_slots_are_not_the_bind"):
        raise ShuttleError("Fallout 4 Question/Neutral/Negative/Positive is not the host bind")
    if payload.get("compiled_movie"):
        raise ShuttleError("this slice has no compiled DoABC movie")
    return payload


def choices_from(data):
    """DialogueListData payload → aChoices. Accepts {aChoices: ...} or {data: {aChoices: ...}}."""
    if not isinstance(data, dict):
        return []
    blob = data.get("data")
    inner = blob if isinstance(blob, dict) else data
    rows = inner.get(CHOICES) if isinstance(inner, dict) else None
    return list(rows) if isinstance(rows, list) else []


def bind_slots(data):
    """Four slots N/E/S/W from aChoices[0..3].sChoiceText. Extra rows dropped; missing rows empty."""
    rows = choices_from(data)
    slots = []
    for i, name in enumerate(SLOT_ORDER):
        row = rows[i] if i < len(rows) and isinstance(rows[i], dict) else {}
        slots.append({
            "slot": name,
            "text": row.get(CHOICE_TEXT) or "",
            "uEntryID": row.get(ENTRY_ID),
            "bCanBeChosen": row.get("bCanBeChosen"),
            "bWasAlreadySaid": row.get("bWasAlreadySaid"),
        })
    return slots


def select_payload(row):
    """Host select event payload: selectedIndex carries uEntryID, not list position."""
    if not isinstance(row, dict) or ENTRY_ID not in row:
        raise ShuttleError("select needs uEntryID")
    return {SELECT_EVENT: {SELECT_KEY: row[ENTRY_ID]}}


def refuse_install_reason(movie):
    """None if the movie may be packed as the DialogueMenu twin; else a short refuse string."""
    parsed = swf.read_movie(movie) if not isinstance(movie, dict) else movie
    if not has_doabc(parsed):
        return "no DoABC: the no-AS3 named-clip movie is killed (host fills via the data shuttle)"
    return None
