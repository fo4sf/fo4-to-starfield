"""Smallest INFO set for DialogueConcordArea 000179F3 (FAL-865). Names, form ids and counts only.

Nothing converted: the four player prompts are ONE/TWO/THREE/FOUR, not Fallout 4 RNAM or response text.
This module is the slice contract. A later translator may fill the same four slots from the player's install;
it must not land those strings in Git.
"""

QUEST_EDID = "DialogueConcordArea"
QUEST_FORMID = 0x000179F3
QUEST_STAGES = 9
# FAL-844 / phase-plan row 2: 8 scenes. Spike B4 counted 15. PC READ on this card confirms which census holds.
QUEST_SCENES_INVENTORY = 8
QUEST_SCENES_B4 = 15
MEETING_SCENE = "006"  # B4: meeting and quest; 36 player INFOs in that scene — this slice takes one turn of four
SLOTS = ("N", "E", "S", "W")
PLACEHOLDERS = ("ONE", "TWO", "THREE", "FOUR")
KEEP_MENU = "DialogueMenu"
KEEP_EVENTS = (
    "DialogueMenu_OnDialogueSelect",
    "DialogueMenu_OnListVisibilityChange",
)
REPLACE_MOVIE = "Interface/DialogueMenu.swf"
CONDITIONS = ("GetIsID", "GetStage")  # names only; first talk after stage 5 (B4: Preston's first line)
OPEN_STAGE = 5


class InfoSetError(ValueError):
    pass


def slot_index(name):
    try:
        return SLOTS.index(name)
    except ValueError as e:
        raise InfoSetError(f"slot {name!r} is not one of {SLOTS}") from e


def infos():
    """One NPC open + four player choices. No fifth slot in this slice."""
    rows = [{"role": "open", "kind": "npc_greeting", "slot": None, "prompt": None, "index": None}]
    for i, slot in enumerate(SLOTS):
        rows.append({"role": "player", "kind": "choice", "slot": slot, "prompt": PLACEHOLDERS[i], "index": i})
    return rows


def info_set():
    rows = infos()
    return {
        "quest_edid": QUEST_EDID,
        "quest_formid": QUEST_FORMID,
        "quest_stages": QUEST_STAGES,
        "scenes_inventory": QUEST_SCENES_INVENTORY,
        "scenes_b4": QUEST_SCENES_B4,
        "meeting_scene": MEETING_SCENE,
        "open_stage": OPEN_STAGE,
        "keep_menu": KEEP_MENU,
        "keep_events": list(KEEP_EVENTS),
        "replace_movie": REPLACE_MOVIE,
        "conditions": list(CONDITIONS),
        "dial_count": 1,
        "info_count": len(rows),
        "player_info_count": 4,
        "infos": rows,
    }


def check(payload):
    """Refuse a set that is not this slice (too many player INFOs, game text, wrong quest)."""
    if payload.get("quest_formid") != QUEST_FORMID:
        raise InfoSetError(f"quest form id {payload.get('quest_formid')!r}, expected {QUEST_FORMID:#08x}")
    if payload.get("quest_edid") != QUEST_EDID:
        raise InfoSetError(f"quest edid {payload.get('quest_edid')!r}, expected {QUEST_EDID}")
    player = [r for r in payload.get("infos") or [] if r.get("role") == "player"]
    if len(player) != 4:
        raise InfoSetError(f"this slice is four player INFOs, not {len(player)}")
    if [r.get("slot") for r in player] != list(SLOTS):
        raise InfoSetError("player slots must be N E S W in that order")
    if [r.get("prompt") for r in player] != list(PLACEHOLDERS):
        raise InfoSetError("prompts must be the stand-in ONE TWO THREE FOUR; Fallout lines stay out of Git")
    if payload.get("keep_menu") != KEEP_MENU:
        raise InfoSetError("KEEP the DialogueMenu class; do not add a second menu class")
    if payload.get("replace_movie") != REPLACE_MOVIE:
        raise InfoSetError("REPLACE is Interface/DialogueMenu.swf")
    return payload
