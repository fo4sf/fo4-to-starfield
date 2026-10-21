# Door exits that land in the wrong place (v6e, 2026-10-21)

Status: **unresolved**. The offline check below has not run on the PC yet.

## Results
The v6e door rounds ran on core 06C0DECD and port 9AF962D2, judged with `--world-instance FF005511=02000803`, on
6159dcb. They gave PASS 10, FAIL 3 and INCONCLUSIVE 2. Vault 95 and the Prydwen hull door pass now; both failed on
v6c. The three FAILs (**verified**, from the PC's `testqueue_v6e\doors_out\door_rounds_judge.json`):

| Test | Exterior arrival (core id) | Off in xy | Off in z |
|---|---|---|---|
| 0004 CambridgePolymerLabs01 (FO4 door 058D90) | 0A7743 | 34.6 m (x -22.3, y -26.5) | -0.5 m |
| 0012 MuseumOfWitchcraft01 (FO4 door 160B24) | 0A774B | 0.0 m | +16.4 m (the same as on v6c) |
| 0013 FortHagen02 (FO4 door 16852C) | 0A774C | 0.0 m | -12.2 m |

## What the numbers suggest
These are **supported hypotheses**. None is tested.
- **Museum and Fort Hagen:** xy is exact, so the MoveTo reached the marker and only the height changed afterwards.
  Below a floating marker, the player falls until something stops them (Fort Hagen, -12.2 m). From a marker inside
  geometry or under the ground, the engine lifts the player out (museum, +16.4 m). In both cases the FO4 arrival height
  does not match the converted ground or object under it at that spot.
- **Cambridge:** z is almost right and xy is 34.6 m off. That looks like the engine moving the player off a blocked
  arrival to the nearest open spot, not like a height mismatch.

## Offline check (read-only, PC)
`scripts/terrain/arrival_ground.py <core staging dir> <door_rounds_judge.json>` takes each WRONG_PLACE marker and read
position back into the core's local frame, by subtracting the build's merge offset. It prints the core BTD's ground
height under each. Reading it:
- Got z on the ground: the player stood on terrain.
- Marker above the ground: the marker floats, or it stands on an object that is not terrain.
- Marker below the ground: the marker is buried.
- Got above the ground: the player is on an object.

The script reads terrain only. If the ground agrees with the marker, the cause is an object: a missing or extra
collision mesh at the arrival, which a look in game or a check of the placed objects there would show.
