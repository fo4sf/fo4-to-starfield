# S3 pod walkability: PC evidence card

Minuteman Copy, Ubuntu. FAL-1007 slice 2 (FAL-858, FAL-911, FAL-848). Reviewer: Scribe, Courier Copy or Sole Survivor.
**Pending review. Windows, Papyrus and game are NOT_RUN by the author.** Grants no install or game control.
It is an observation card: no placement fix exists yet, and none is inferred from this text.

## Why this card

The exit lift cannot be tested in a new game if the player cannot walk from the pod to the console and lift without
tcl (FAL-858 comment 2979c931). The recorded C1 settle readings are in [pod-position-evidence](pod-position-evidence.md):
the player settles 1.35-1.63 m above target, then moves only centimetres while walking. Cause unresolved. The source
already logs coherent samples (`pod settle`, `looks position` before ShowRaceMenu and at Done). This card collects them on
the head under test and adds the walking observation the logs cannot give.

## Procedure (PC, separate release required)

Use the guarded session installer, game-closed before and cleanup receipts, and the owner's settings and saves untouched.
Record the full head, the installed core hashes and the plugin/PEX hashes. Use fresh throwaway new games.

Run twice: **(1) normal creator**, **(2) quick start**. For each:

1. From the first controllable frame, with collision on and no tcl, no noclip and no teleport, walk from the pod through the
   hall toward the console, then toward the lift. Record a screen capture and the time of each of: first input, first
   blocked attempt, reaching the console, reaching the lift.
2. If blocked, stop and, without moving, record where: from the log (`make_newgame.py log`) the `pod_settle` and
   `looks_positions` lines, and in the game the player XYZ (the existing log is fine; do not use `tcl` to move). Name what
   the player is pushing against, if visible.
3. Do not lower Z, edit the pod, or change placement on the PC. Do not count a result reached with tcl.

## Report

For each of the two runs: PASS (reached console and lift by walking), or FAIL with the blocking position, the log lines
quoted verbatim, and the capture. Compare settle, before-creator and Done samples: a drop that changes between them is
the first lead. Keep unresolved items unresolved. A PASS here shows walkability only: not the lift, map listing,
discovery, Fast Travel or S3.
