# Cog door walk card (PC): collision of the walkway, FAL-813 (rev 2, after the PC check of ca86cd6d)

Author: Minuteman. Status: **card only, nothing run in game**. Run it after the head is reviewed and a fourth offline run passes (owner asks for the
session). Numbers are Claude's offline reads (FAL-810 comment 3e2e35ee; FAL-813 comment 119ad6e2) in the cog's world frame, metres, bind pose = closed.
Heights are deck TOPS. Everything marked "expect" is a prediction, not an observation.

## Geometry (closed)
- Ramp x -55.71 to -50.42, y -5.19 to -2.84, top 0.75. Stowed decks WalkWay01Base top 0.83 and WalkWay03Base top 0.85, x -52.63 to -48.57, y about
  -5.0 to -3.0: they reach 1.85 m past the ramp's EAST (vault-side) end, so a player coming from the vault side meets the decks, not the ramp.
- Floor z 0.60 was measured at one spot only (x -55.06, y -2.38). **Step A measures it on the vault side; the step heights below depend on it.**
  If the floor is 0.60: floor to stowed deck 23 to 25 cm (not 15). Report the number; do not assume it.
- Closed, the ramp's west end (-55.71) is 5.6 m from the cog face (-61.29): nothing between them. Walking west off the ramp falls (step 0: to z -2.38 at x -59.26).
- Railings stand on the deck edges along their length: WalkWay01Base clear width 1.89 m (y -4.96 to -3.07), WalkWay03Base 1.73 m (y -4.88 to -3.15),
  rail tops about 1.13 m above the deck. The ramp has a rail on its SOUTH side only (y -5.2); its north side (y -2.84) is open.
- Open (estimate from clip end travel, not sampled): first deck x -59.77 to -55.71, meets the ramp's west end, no gap; second deck x -63.85 to -59.79, 2 cm
  overlap, reaches past the cog face. Deck tops unchanged by translation (0.83, 0.85). b_Ramp turns 7.25 degrees about (0, -1, 0) about its WEST end
  (world x about -55.64): the east (vault-side) end moves about 0.67 m up or down; **the sign is not known**. Expect the floor-to-ramp step on the vault side
  to differ from the closed one; step 5 measures it.

## Console (from the PC's own report; the index and the spot frame are the two things to confirm first)
- Stage: `setstage 0E000800 20` (open) and `setstage 0E000800 30` (close). `0E` is the kit plugin's load index and holds only while the kit plugin is
  LAST in the load order (as in cogB2). `setstage FO4SF_CogDoorQuest <n>` does not work on this install. **Read the index before step E:** look at the
  plugin's position in the in-game load order list (the two hex digits are its slot, 0-based); if it is not 0E, use that prefix in both commands, and if
  the kit plugin is not last, say so and stop (the index can then differ from the card's). Not verified here: no console command is known that prints it.
- **tcl is OFF for every spot and every walking step** (collision must act). Turn it on only to get unstuck, then off again.
- **Spot frame.** The step-0 `getpos` (-59.26, -3.06, -2.38) sits in the same numbers as this card's cog-frame metres (the fall was in the gap between the
  ramp end -55.71 and the cog face -61.29). So `player.setpos x y z` takes the card's x y z as written. Check it once at spot 1: after the hop, `getpos`
  must read within about 0.3 of the typed x and y. If it does not, stop and report the offset; every other spot is wrong by that offset.
- Every hop below is under 12 m on every axis (limit 200 m). Type `player.setpos x y z`, then `player.setangle z 90` to face west (the card's walking
  direction; the angle sign is the PC's call, only the facing matters). Spots drop the player about 0.4 m onto the surface; if a spot lands in the
  void (z below -1), `tcl`, `player.setpos` back to spot 1, `tcl` off, and report the spot.
- **Console closed from the stage command until 45 s later.** The console pauses the clip clock, so any console use during the ~44 s clip stretches it
  and mixes the poses. Open it to type the stage command, close it, wait, count 45 s, then `getpos`.

## Spots (cog-frame metres, tcl off; z is 0.4 above the expected surface)
| # | Spot | x | y | z | Expected surface under it |
|---|---|---|---|---|---|
| 1 | Vault side, floor, in front of the stowed decks | -46.50 | -4.00 | 1.00 | floor at about 0.60 (unmeasured here; the only floor read is x -55.06, y -2.38 = 0.60) |
| 2 | Stowed decks, east end, between the rails | -49.00 | -4.00 | 1.25 | deck top 0.83 (WalkWay01Base), 0.85 where WalkWay03Base overlaps |
| 3 | Ramp, west end, closed | -55.30 | -4.00 | 1.15 | ramp top 0.75 |
| 4 | Ramp, middle, closed | -53.00 | -4.00 | 1.15 | ramp top 0.75, bare (the stowed decks start at x -52.63, east of this spot) |
| 5 | Deck edge, south rail test | -51.00 | -4.70 | 1.25 | deck 0.83-0.85; rail at y -4.96 |
| 6 | Deck edge, north rail test | -51.00 | -3.30 | 1.25 | same; rail at y -3.07 |

For the open steps use spot 1 as the start (floor, vault side) and walk west by foot; do not setpos onto the open pose (its heights are unknown).

## Ramp tilt: what the card can and cannot predict
Not predicted. b_Ramp turns 7.25 degrees about (0, -1, 0) in its own frame, bone origin at the ramp's west end; no clip data and no open-pose sample is on
the machine that wrote this card, and the axis frame is changed by the cog's pi turn in its placement, so the sign cannot be fixed from the numbers.
**It is a measured line (step E).** What each outcome means (east end 5.3 m from the hinge: 5.3 x sin 7.25 = 0.67 m):
- East end UP: ramp top there about 0.75 + 0.67 = 1.42. With the floor at 0.60 the ramp is a 0.8 m wall from the vault side: not climbable. West end stays 0.75.
- East end DOWN: ramp top about 0.08, 0.5 m below the floor; it is a drop of about 0.5 m onto it from the vault side, then it rises to 0.75 at the west
  end, a slope of 7.25 degrees (steeper than the usual walkable limit; a slide back is possible).
Either way the vault-side step is not the closed 15 cm. Record `getpos` standing on the ramp's east end, middle and west end, and the direction.

## Card (one change at a time; write what you see, with `getpos` where asked)
A. Closed. Spot 1. `getpos` right after the hop (checks the frame), then again once standing: this is the floor z. Record it first; it decides B.
B. Closed. From spot 1 walk west into the stowed decks (the first step is the decks, 23 to 25 cm if the floor reads 0.60; predicted from the card's heights, not seen): record whether you step up onto them (23 to 25 cm expected if floor 0.60) or are stopped. If stopped, try
   again from y -3.5 and y -4.5; record the lowest approach that works. `getpos` on the deck top.
C. Closed. Spot 2 to spot 4 to spot 3 (or walk it): the decks west to the ramp's east end, then the ramp west to its end at x about -55.7. **Stop at the edge; do not walk off.** `getpos`
   at the stop. Record any snag, and whether the key motor over the ramp (bind pose: 1.06 to 1.77 m above the ramp top) stops your head (the clip's first frame was not
   read; the unit was not seen over the ramp closed, so no obstruction is also a valid result).
D. Closed. Spots 5 and 6, then walk the south edge of the stowed decks (y about -4.9): the railing should stop you. Same north (y about -3.1). Record where each stops (`getpos`).
   Ramp: south side stops you at y about -5.1; north side is open by design (expect to fall off: only try with `tcl` off from the ramp's low edge, and say so).
E. Open: stand on spot 1 (floor, not on a deck), read the index (see Console), `setstage 0E000800 20`, close the console, wait 45 s without opening it. Then `getpos` standing on the ramp's east (vault-side) end, in the middle of the ramp, and at the west end.
   These are the open-state heights. Record the vault-side floor to ramp step (differs from closed by up to 0.67 m; the sign is the answer).
F. Open. Walk y -4.0 west: ramp, first deck, second deck, toward the cog face. Record each step up/down and any gap (expect none; 2 cm overlap).
   `getpos` on each deck: z about 0.83 and 0.85 plus the player's offset.
G. Open. Rails on each deck: walk to each edge (y about -3.0 and -5.0) on both decks; record where you stop (`getpos`), and try to step off each side.
H. Fall-through: stand still on each deck and jump twice; walk the joins; record any fall below the deck.
I. Open. Camera from the side, at least 6 m back (about y -11 or y +4, the whole walkway in frame): shoot with the player on a deck.
J. Close: `setstage 0E000800 30`, standing on a deck is optional and risky: say if you did. Console closed 45 s. If standing on a deck, record
   whether it rode back with you (bodies are children of their bones; not seen moving), and the closed cog block (the cog body now carried matches the old
   fallback to 7 cm and still blocks: walking into the cog is only possible from a deck while open, not from the closed ramp).

Stop and report on the first unexplained fall-through, an unexplained block, or a body left behind when the bones move. Report the floor z (step A) first:
it decides whether the stowed-deck step is within the limit.
