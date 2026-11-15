"""Host DialogueMenu names from the PC §1 dump (FAL-865 PARTIAL at 44ba71ac).

The no-AS3 four-slot stand-in cannot fill: Starfield pushes list rows through the movie's data shuttle,
not by instance name. Fallout 4's four clips are a different native path (BGSCodeObj). Nothing converted.
"""

KEEP_MENU = "DialogueMenu"
KEEP_EVENTS = (
    "DialogueMenu_OnDialogueSelect",
    "DialogueMenu_OnListVisibilityChange",
)
KEEP_SHUTTLE = ("BSUIDataManager", "UIDataShuttleConnector")
HOST_ROOT = "Menu_mc"
HOST_CHILDREN = (
    "DialogueList_mc",
    "PersuasionList_mc",
    "PersuasionData_mc",
    "ButtonBar_mc",
    "CrewSkillsWidget_mc",
    "PrecognitionData_mc",
)
HOST_LIST = "DialogueList_mc"
HOST_LIST_ENTRY = "DialogueScrollingListEntry"
FO4_ROOT = "Menu_mc"
FO4_HOLDER = "FadeHolder_mc"
FO4_SLOTS = ("Question", "Neutral", "Negative", "Positive")
STANDIN_SLOTS = ("fo4sfOptN", "fo4sfOptE", "fo4sfOptS", "fo4sfOptW")
QUEST_SCENES = 8  # DialogueConcordArea 000179F3, PC PARTIAL


class HostMenuError(ValueError):
    pass


def host_names():
    return {
        "keep_menu": KEEP_MENU,
        "keep_events": list(KEEP_EVENTS),
        "keep_shuttle": list(KEEP_SHUTTLE),
        "host_root": HOST_ROOT,
        "host_children": list(HOST_CHILDREN),
        "host_list": HOST_LIST,
        "host_list_entry": HOST_LIST_ENTRY,
        "fo4_slots": list(FO4_SLOTS),
        "standin_slots": list(STANDIN_SLOTS),
        "quest_scenes": QUEST_SCENES,
        "standin_matches_host": False,
        "standin_matches_fo4": False,
        "host_fills_by_name": False,
        "kill_no_as3_named_clips": True,
    }


def check(payload):
    if payload.get("host_fills_by_name"):
        raise HostMenuError("host fills the list from the data shuttle, not by clip name")
    if payload.get("standin_matches_host"):
        raise HostMenuError("stand-in fo4sfOpt* is not a host child")
    if set(payload.get("standin_slots") or []) & set(payload.get("fo4_slots") or []):
        raise HostMenuError("do not treat Fallout 4 clip names as the host shuttle")
    if payload.get("quest_scenes") != QUEST_SCENES:
        raise HostMenuError(f"scenes {payload.get('quest_scenes')!r}, PC read {QUEST_SCENES}")
    if payload.get("keep_menu") != KEEP_MENU:
        raise HostMenuError("KEEP the DialogueMenu class")
    if not payload.get("kill_no_as3_named_clips"):
        raise HostMenuError("the no-AS3 named-clip stand-in is killed")
    return payload
