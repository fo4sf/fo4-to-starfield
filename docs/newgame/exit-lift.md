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
