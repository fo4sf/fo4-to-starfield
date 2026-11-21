# Concord four-option talk (first slice)

Scribe. KEEP the host `DialogueMenu` class, events, and movie. Overlay four slots; do not REPLACE
`Interface/DialogueMenu.swf`. Nothing converted from the game is in Git. The four prompts are ONE, TWO, THREE, FOUR.

This change reaches the owner's normal game only after independent review of this branch, required checks, and a PC
session. Replacing the host movie is killed: control (no kit) opened the Chunks vendor list with no crash; the same
talk with the kit crashed at 48a3eb3d and again at 69ee810a (host-root stubs, sha256 f6e58827…f4f2). Do not install
those heads. Concord DialogueConcordArea `000179F3` is not on the current set.

## What this slice is

- `scripts/ui/make_dialogue_wheel_swf.py` writes a four-slot overlay movie (N/E/S/W, named `fo4sfOptN` … `fo4sfOptW`).
- `scripts/dialogue/make_concord_talk.py stage` writes an empty plugin and `Interface/FO4SF_DialogueWheel.swf` only.
  It never writes `Interface/DialogueMenu.swf`.
- `scripts/dialogue/concord_talk_install.py` refuses a staged host `DialogueMenu.swf`.
- `scripts/dialogue/concord_info_set.py` is the smallest INFO set for DialogueConcordArea `000179F3`: one greeting
  plus four player INFOs. No Fallout lines.

## What this slice is not

- Not converted DialogueConcordArea records (255 DIAL / 397 INFO stay on the player's install).
- Not a second menu class, not F10, not the faction-device kit.
- Not a replacement of the host movie. Overlay load (SFSE after host LoadMovie) is the next native slice.
- Not in-game proof. Offline tests do not open the game.

## What the first PC dump showed

The host fills `DialogueList_mc` through the movie's data shuttle, not by clip name. Fallout 4's four clips
(`Question`, `Neutral`, `Negative`, `Positive`) are a different native path. The no-code `fo4sfOpt*` stand-in
cannot take host text or the select path; the installer refuses a movie with no DoABC. PC PASS §1b named
the payload: bind `DialogueListData.aChoices[0..3].sChoiceText`; select is `DialogueMenu_OnDialogueSelect`
with `selectedIndex` = `uEntryID`. DialogueConcordArea `000179F3` has 8 scenes.
