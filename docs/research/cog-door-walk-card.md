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

## Console (assumptions to confirm on the PC, from the PC's own report)
- Stage: `setstage 0E000800 20` (open) and `setstage 0E000800 30` (close). The `0E` holds only while the kit plugin is last in the load order. `setstage
  FO4SF_CogDoorQuest <n>` does not work on this install.
- `tcl` off for every walking step (collision must act). Use `tcl` only to reposition if stuck, then turn it off again.
- Spots by `player.setpos x y z` (world metres are NOT console units: the console takes game units; use the PC's `getpos` reading at the spot and
  `player.setangle`). Where this card gives coordinates they are the metre values above; convert with the PC's known placement before typing.
- Open the console only to give the stage command; **keep it closed from the stage command until 45 s after** (the clip is about 44 s). `getpos` only after that.
- Collision view: no working command is known in this build. Do not plan on it; stand on the decks and report what you stand on.

## Card (one change at a time; write what you see, with `getpos` where asked)
A. Closed. Vault side, in front of the stowed decks, walking west at y -4.0. `getpos` on the floor; this is the floor z. Record it.
B. Closed. Walk west into the stowed decks: record whether you step up onto them (23 to 25 cm expected if floor 0.60) or are stopped. If stopped, try
   again from y -3.5 and y -4.5; record the lowest approach that works. `getpos` on the deck top.
C. Closed. Walk the decks west to the ramp's east end, then the ramp west to its end at x about -55.7. **Stop at the edge; do not walk off.** `getpos`
   at the stop. Record any snag, and whether the key motor over the ramp (bind pose: 1.06 to 1.77 m above the ramp top) stops your head (the clip's first frame was not
   read; the unit was not seen over the ramp closed, so no obstruction is also a valid result).
D. Closed. Walk the south edge of the stowed decks (y about -4.9): the railing should stop you. Same north (y about -3.1). Record where each stops (`getpos`).
   Ramp: south side stops you at y about -5.1; north side is open by design (expect to fall off: only try with `tcl` off from the ramp's low edge, and say so).
E. Open: `setstage 0E000800 20`, console closed 45 s. Then `getpos` standing on the ramp's east (vault-side) end, in the middle of the ramp, and at the west end.
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
