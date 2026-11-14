# Cog door walk card (PC): collision of the walkway, FAL-813

Author: Minuteman. Status: **card only, nothing run in game**. Run it after the head is reviewed and a fourth offline run passes (owner asks for the
session). Numbers are Claude's offline reads of 306faa71 (FAL-810 comment 3e2e35ee) in the cog's world frame (metres, placement
(-54.857, -2.743, -0.143), pi turn). Heights are deck TOPS. Expected values are predictions, not observations.

## Expected geometry (closed pose, bind pose)
- Floor the player stands on: z 0.60. Ramp top 0.75 (x -55.71 to -50.42, y -5.19 to -2.84): a 15 cm step, at the limit.
- WalkWay01Base top 0.83, WalkWay03Base top 0.85 (x about -52.6 to -48.6 closed, stowed over the ramp's east half): steps of 8 cm and 2 cm.
- Centre line: y about -4.0 (the ramp's middle). Closed cog blocks across it at x -63.03 to -61.28.
- Open pose (estimate from the clip's end travel, not sampled): first deck x -59.77 to -55.71 (meets the ramp's west end, no gap), second deck
  x -63.85 to -59.79 (2 cm overlap with the first, reaches past the cog face at -61.3). Tops unchanged 0.83 and 0.85 by translation alone; the ramp
  turns 7.25 degrees open, so ramp heights are not predicted.

## Card (one change at a time; write what you see, with `getpos` where asked)
1. Closed. Stand on the floor at the ramp's foot, y about -4.0. Walk onto the ramp (the 15 cm step). Record: stepped up, or blocked.
2. Closed. Walk the ramp's length on y -4.0; `getpos` at the west end. Record any snag.
3. Closed. Walk into the cog from the ramp; record: blocked (expected) or through. Look up at the key motor over the ramp; try the ramp
   with head height (the bind pose has it 1.06 to 1.77 m over the ramp top): record whether the head is stopped.
4. Run the open (quest stage 20 or the door's own open) and let it finish. `getpos` standing on the ramp, then on the first deck, then the second.
   Expect z about 0.83 and 0.85 plus the player's offset; write all three.
5. Open. Walk y -4.0 west: ramp to first deck to second deck to the cog face. Record each step up/down and any gap (expected none, 2 cm overlap).
6. Open. On each deck walk toward the left and right edge (y about -3.0 and -5.0): the railings should stop you at the deck edge. Record where
   you stopped (`getpos`) on both sides, both decks. Try to step off each side; record whether you fall off or are held by the rail.
7. Fall-through: stand still on each deck and jump twice; walk the deck joins; record any fall below the deck.
8. Open. Camera from the side, further back than before (at least 6 m from the line, about y -10 or y +2, the whole walkway in frame): shoot the
   bodies if the collision display is available, else the decks with the player on them. Say which.
9. Close again and repeat step 1: the decks should ride back (bodies are children of their bones; not seen moving).

Stop and report on the first fall-through, the first unexplained block, or a body left behind when the bones move.
