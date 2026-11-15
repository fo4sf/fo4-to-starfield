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

Map preparation from inside the vault is still unverified. Its result determines the
preparation route; a visible wait or black hold does not meet the exit requirement.
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
