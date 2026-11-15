# Vault exit lift

The production exit is being built in reviewable slices. It must wait at the vault floor,
carry the player upward, complete map preparation within the exit sequence, discover only
Vault 111 on confirmed arrival, and make that destination available for fast travel.
The door opens through its console; gates must have collision.

The first slice adds an optional initial pose to the animated-object converter.
`rest_after` names a mapped source sequence whose last pose becomes `StateA_Idle`.
The two-state stager exposes it as `--rest-after`; the existing moving clips, rig and
collision bindings are retained. Without the option the existing output is retained.
The manifest records the selected source sequence and the idle's provenance.
This is an offline-tested candidate for a floor start; native height, graph transitions,
walk-on collision and carrying still require an exact-build game result.

The normal owner build receives the lift only after its production controller, console
activation, map preparation and arrival discovery are implemented and independently
reviewed, and the complete exit passes in game. The existing animation and marker probes
remain temporary session tools. This source slice is not an owner-installable exit.

Cold map preparation from inside the vault failed the PC card's world-attachment
criterion. The next route is described below; a visible wait or black hold does not meet the exit requirement.
The F10 interface and the pre-war start design remain separate work.

## Arrival discovery slice (FAL-848, 15 November)

PC result d6a04cf2 (main `6ebb7a0d`, 14 November 23:34–23:49 UTC) rejects the
cold indoor route: TEST reached the requested XYZ but its world and cell were None.
The later outdoor mover repaired it in a runtime Mars world. That repair is not
indoor preparation. Indoor discovery left every observed surface-map marker UNKNOWN;
visible/canfast had already been true before the call. The reported 26 seconds includes
a 24.4-second dark hold and a reload, so it is not a measured placement-only budget.

The production startup quest now confirms its arrival before requesting discovery:

- The loaded exterior cell must belong to the core; pin its runtime world. A failed
  SetPosition budget ends with `exit failed`, without stage 40 or discovery.
- After settling, require that world and a position within 5 m horizontally and 3 m
  vertically of the primary arrival. A fall requests the existing fallback once;
  only a later tick can confirm that move. A wrong world or failed fallback cannot
  complete. The existing landing check adds no blackout or input freeze.
- Resolve the canonical Vault 111 marker only (`ArrivalDiscoveryId`, written by
  NewGame; custom exit anchors disable discovery). Wait at most 30 loaded landing
  checks for it to attach to the same world at its merged location, within 5 m XY
  and 3 m Z. Recheck the player before calling SetMarkerDiscovered once.
- `arrival discovery requested` records a void native call and global fast-travel
  readings. It makes no discovered-state claim. The log reader retains the request
  and terminal failure separately. Stage 200 is physical arrival plus the request,
  not proof of map listing, completed S3, or a fast-travel unlock.

The all-marker timing route remains an **unresolved hypothesis**: attach the exterior
world at the beginning of the final exterior segment of the ascent, and run marker
movement while the unchanged upward motion finishes. Its available time starts at
world attachment, not at the start of the indoor ride. No added wait, slowed animation,
black hold or hidden reload is accepted. The old map `Ready` budget-exhaustion result
cannot certify preparation. Source for that ascent/attachment integration is still
outstanding; this commit does not pretend that the present teleport is a carrying ride.

The [PC evidence card](exit-arrival-pc-card.md) first isolates exterior discovery and
map listing with the existing diagnostic kit. A listing failure without reload rejects
this timing route regardless of speed. If that check passes, the full final-segment
integration must be built and measured at all-marker scale before choosing it. No
source-only measurement can claim those 26 seconds are already hidden.

## Carrying ascent slice (FAL-848, 15 November)

The next opt-in component reuses the original V111ElevatorREF, not a spawned
test platform. `make_anim_console.py stage --production-lift` builds
FO4SFExitLift.esm with one ACTI override and its converted assets, without the
animation probe quest or PEX. The pinned two-state recipe is stage3 in
StateA_Play (up, 9.8667 s, 21.6 m), stage2 in StateB_Play (down, 23.8333 s),
`--idles toggle --rest-after stage2`. StateA_Idle holds the downward clip's
floor pose; StateB_Idle holds the upward clip's top pose. The stager checks
the clip map, lengths, vertical platform travel and twelve moving bodies.
These recipe numbers come from FAL-489's moving-platform note rev 40,
sections 10 and 26; its old native carrying result is not a pass for this build.

`make_newgame.py stage --exit-lift <component>` verifies asset hashes and the
same port/Starfield inputs, then enables the controller and includes the
component. The writer resolves exactly one original lift mapping/reference
in the vault, the port-owned lift ACTI, unit scale and vertical orientation.
The normal new-game stage remains opt-in; the earlier exit stays selected
when no component is supplied. Fold/verify carry and hash-check the assets
and list the lift plugin before FO4SFNewGame.esm. They refuse output collisions.

The rider chooses the existing elevator prompt at the floor. Start requires
the loaded player and original lift in the same vault cell. Register for
Done, play Play01 once, and leave player motion to the platform's collision.
Ignore early Done events (the prior PC session heard a stale event near
0.068 s). A later tick requires a Done no earlier than 8.8667 s and the rider
within the original footprint, 21.6 m above their starting height (0.75 m
vertical tolerance). Only then enter the reviewed Surface/FinishSurface/
CheckLanding path. Wrong identity/cell, refused playback, missing completion
or missing rise fail; the watchdog ends after the clip length plus 30 s.
No animation is slowed and no hold, input freeze or blackout is added.

This is the **indoor carrying and arrival component**. It does not attach an
exterior world while the platform still moves, or implement the all-marker
coordinator. Therefore it provides no exterior-motion map-preparation window
and is not the runnable full Section B build. Keep #790 draft. Console-driven
cog opening, colliding gates, floor-label flicker, marker timing/listing and
normal owner-build acceptance remain gates. See [the ascent card](exit-ascent-pc-card.md).

## Start-of-vault prerequisite: pod placement

Claude PC's FAL-858 comment 2979c931, relayed on FAL-848 as bce87625,
reports a collision-enabled walking obstruction after creator closure in
fresh main and #791 games: pod settle drop -1.41/-1.38 (earlier -0.86).
Walking moved centimetres, while tcl allowed metres. This is PC-reported
placement/collision evidence; its root cause remains unresolved.

Treat pod settle as a separate small S3 source slice before full exit acceptance.
It reproduces without #790 and has its own spawn/creator/geometry oracle.
The existing CheckPod only bounds a fall and runs once before creator closure;
a negative drop with ok=true does not prove walkability. Do not lower Z blindly:
an earlier low start fell through the floor. Pin the actual installed heads and
points, read position before/after creator closure, and diagnose the obstruction.
Normal creator and quick-start controls must both allow collision-enabled walking
from pod through the hall to the console. Preserve #791's creator work. The earlier
"not a defect" classification in vault111-start.md described a session without
reported obstruction; this new report supersedes that classification.
