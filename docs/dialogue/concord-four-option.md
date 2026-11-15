# Concord four-option talk (first slice)

Scribe. First slice of the dialogue core: KEEP the host `DialogueMenu` class, REPLACE its movie with a four-slot
stand-in generated here. Nothing converted from the game is in Git. The four prompts are ONE, TWO, THREE, FOUR.

This change reaches the owner's normal game only after independent review of this branch, required checks, and a PC
session that shows four options on one Concord talk (or on any talk, for the movie half). Until then it is draft
source. Vault 111 exit is a separate card; until that lands, the PC uses the usual console jump to Concord.

## What this slice is

- `scripts/ui/make_dialogue_wheel_swf.py` writes a four-slot movie (N/E/S/W, named `fo4sfOptN` … `fo4sfOptW`).
- `scripts/dialogue/make_concord_talk.py stage` writes an empty plugin and twins that movie at
  `Interface/DialogueMenu.swf`.
- `scripts/dialogue/concord_info_set.py` is the smallest INFO set for DialogueConcordArea `000179F3`: one greeting
  plus four player INFOs. No Fallout lines.

## What this slice is not

- Not converted DialogueConcordArea records (255 DIAL / 397 INFO stay on the player's install).
- Not a second menu class, not F10, not the faction-device kit.
- Not in-game proof. Offline tests do not open the game.

## What the first PC dump showed

The host fills `DialogueList_mc` through the movie's data shuttle, not by clip name. Fallout 4's four clips
(`Question`, `Neutral`, `Negative`, `Positive`) are a different native path. The no-code `fo4sfOpt*` stand-in
cannot take host text or the select path; do not install it. Next movie must bind the shuttle (or a native bind).
DialogueConcordArea `000179F3` has 8 scenes.
