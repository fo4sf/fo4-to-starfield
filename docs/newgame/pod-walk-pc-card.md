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

Install head: **draft #796 `4aaaa2c0cf5bb523dcac388e9f6d449dfb87690b`** (or #790 `34e62421`), not main. `looks_positions` and the
`looks position` lines exist only on #790/#796 (they enter at `815ec1a2`); main `091de52e` does not emit them, and main is the
build where the obstruction was first reported. The latest Courier CLEAR of the NewGame source is `5a24a65f`; `34e62421`
and `4aaaa2c0` change NewGame after it (the Scribe's note on #796 is merge-only), so say so in the receipt.

Use the guarded session installer, game-closed before and cleanup receipts, and the owner's settings and saves untouched.
Record the full head, the installed core hashes and the plugin/PEX hashes. Use fresh throwaway new games.

Run twice. The opening message from `dotnet/NewGame` has button 0 `Create character` and button 1 `Quick start`:
**(1) normal creator** = button 0, **(2) quick start** = button 1. Use the staged default race-menu mode. For each:

1. From the first controllable frame, with collision on and no tcl, no noclip and no teleport, walk from the pod through the
   hall toward the console, then toward the lift. Record a screen capture and the time of each of: first input, first
   blocked attempt, reaching the console, reaching the lift.
2. If blocked, stop and, without moving, record where: from the log (`make_newgame.py log`) the `pod_settle` and
   `looks_positions` lines. The blocked spot is a later position than `pod_settle` (the first loaded tick): read the player XYZ
   in place, without tcl. `make_newgame.py log` prints the JSON and then exits 1 unless stage 200 was reached without standing
   down; a blocked walk never reaches stage 200, so keep the JSON and treat that exit as the expected FAIL-path result. Name what
   the player is pushing against, if visible.
3. Do not lower Z, edit the pod, or change placement on the PC. Do not count a result reached with tcl.

## Report

For each of the two runs: PASS (reached console and lift by walking), or FAIL with the blocking position, the log lines
quoted verbatim, and the capture. Compare the settle sample, the `before creator` phase and `done: creator closed` / `done: quick start`: a drop that changes between them is
the first lead. Keep unresolved items unresolved. A PASS here shows walkability only: not the lift, map listing,
discovery, Fast Travel or S3.

## Variant B: stand 2.5 m in front of the pod (FAL-1007; Gemini (PC) pod read, FAL-1007 comment 6371ab99)

Hypothesis (Gemini (PC), relayed; the mechanism is **inferred**, not yet observed in game): the current start, `--pod-step 1.0`
(the points tool's default), places the player 1 m along +Y of `REFR 0004A011`, behind the pod in a pocket against the rear
wall; the pod's front exit faces -Y, and FO4's own post-pod marker `0001ED61` is about 2.5 m toward -Y. Only the step changes.

How to build it. `make_newgame.py stage` at #796 `4aaaa2c0` always ran `points` with the default step, so this card needs the
reviewed `--pod-step` flag on `stage` (branch `minuteman/fal848-pod-walk-card`, with a unit test; install head for Variant B is
that branch's head, which differs from #796 `4aaaa2c0` only by that flag, its unit tests (`tests/test_newgame.py`, which do not change the staged plugin) and this card; record the full head). Use the same
`stage` command and every other option as the +1.0 run, adding `--pod-step -2.5`. Do not run any other points path and do not
edit source on the PC. Before install, record the printed `stand` and `step_m` and the same two values in the staged
`points.json` (expect `step_m` -2.5 and stand about (9.143, -6.614, -1.029) for the pod at (9.143, -4.114, -1.029), read from `work/points.json` `pod.pos` and `pod.step_m` and from the printed stand line; `step_m` is only in the points file, not in the printed line). Do not use -1.0: Gemini (PC) reports it
lands in the pod's door canopy collision.

Run the card above once per start (creator = button 0, quick start = button 1), identical except the points file. The pod's
rotation and the written heading are unchanged (`Points` derives both the offset and the heading from `pod.Rotation.Z`), so
the player faces the wall and must turn; **a walk proves the step only**. Do not turn the pod's rotation to change the heading;
that is a separate, unproven change.

Compare with the +1.0 run on the same measurements: `pod_settle` and `looks_positions`, the settle height above target (+1.35
to +1.63 m before), and whether the player walks the hall to the console and lift. Record each start's own PASS or FAIL; if
one does not walk, record where it blocks and do not reject the other. PASS is walkability only, as above. If both walk, the
later source slice is the default `--pod-step` alone, with its own unit test; a heading change stays separate. If neither
walks, the variant is rejected and the converter's pod collision bodies are the next suspects.
