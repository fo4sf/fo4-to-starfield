# Door exits that land in the wrong place (v6e, 2026-10-21)

Status: **unresolved**. The terrain, object and conversion checks all ran on the PC (2026-10-21); what is left needs a look
in game.

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

## Terrain check, run on the PC
`scripts/terrain/arrival_ground.py` (#445) ran on the v6e core's staging folder (terrain_core64v6e_l125_mission_wfc11,
06C0DECD) against the judge file above. The positions are core-local metres. The results are **verified**:

| Test | Marker (local) | Ground under it | Read position (local) | Ground under it |
|---|---|---|---|---|
| 0004 Cambridge | (-369.9, -33.5, 13.87) | on the ground (13.76) | (-392.3, -60.0, 13.37) | on the ground |
| 0012 Museum | (1212.2, 1052.9, 10.31) | 1.1 m above (9.25) | same xy, z 26.67 | 17.4 m above |
| 0013 Fort Hagen 02 | (-1270.5, -74.8, 95.09) | 14.1 m above (81.00) | same xy, z 82.90 | 1.9 m above |

What this narrows (**supported hypotheses**, not tested):
- **Fort Hagen 02:** the marker floats 14 m over the terrain, so FO4 put it on something raised (a roof, a deck or a
  walkway). The player fell almost to the ground, so that object is missing in the core or has no collision there.
- **Museum:** the marker is close to the ground, and the player ended up 17 m above it. Something placed over the arrival
  carried the player up: an object whose collision covers the spot, or a lift out of geometry.
- **Cambridge:** both points are on the ground, 34.6 m apart. This is not a height problem. The engine moved the player
  off a blocked arrival, or the arrival marker points at the wrong place.

### Object check results
arrival_objects.py ran on the same core at 4df9c1d (radius 20 m; skipped.json present). The nearest objects are
**verified**. No reference near any arrival is disabled. Collision "fo4-none" means FO4 itself ships the model with no
collision (scripts/oracles/placed_collision.py), so those are not conversion losses.
- **Fort Hagen 02:** the marker stands on a rooftop elevator exit. The roof piece decoroof1x1str01 (FO4 1958F3, collision
  fo4-native) sits 0.4 m away at exactly the marker's height (95.09). The elevator door utilmetalelevatorout01 (16852D,
  rigged-door-box) is 1.2 m away at the same height, with its buttons and meters. The player still fell 12.2 m.
- **Museum:** the marker stands on the floor piece bldwlpsmflronly01 (16D3E0, fo4-native, z 10.31, the marker's exact
  height), between wall pieces at the same height. The ceiling piece bldwlpsmceilonly01 (16D3EC, fo4-native) is 1.8 m
  above the floor (z 12.14). The player ended at z 26.67.
- **Cambridge:** the marker stands at the double door frame decomaina1x2doordouble01 (0AAD19, fo4-native, 0.4 m away),
  next to the load door itself (058D90, 0.6 m). The player ended 34.6 m away, on the ground.
- Skipped references nearby are mostly texture sets, sound and acoustic markers, and a few models with no mesh; none is a
  floor or roof piece. That is **verified** by type only, since skipped refs carry no position.

What this narrows (**supported hypotheses**, not tested):
- **Museum:** the room's clear height is 1.8 m (the ceiling's origin minus the floor's). If the converted player capsule
  is taller than that, the arrival overlaps the ceiling's collision and the engine pushes the player out, here up onto the
  building. That would also explain the same +16.4 m on v6c.
- **Fort Hagen 02:** the roof piece is listed as native collision, so either its converted collision does not cover the
  arrival spot (a part left out, or offset), or the player arrives before that body is in the world and falls through.
- **Cambridge:** the arrival overlaps the door frame's collision, and the engine moves the player to the nearest open spot.

### Conversion reports of those pieces
From the convert manifest the v6e core was built with (terrain_core64c_work_v6c2, 11,768 items), **verified**:
decoroof1x1str01, decoroof1x1str01full01, bldwlpsmflronly01, bldwlpsmceilonly01 and decomaina1x2doordouble01 each have
FO4 native collision converted as one body, with nothing left out. The Fort Hagen elevator exit utilmetalelevatorout01
has no static collision report; it is a native door rig (two moving bodies, bounds 3.17 x 0.46 x 2.51 m, its panels slide
about 0.64 m sideways when it opens).

So no collision is missing at the manifest level, and the offline checks stop here. What remains (**supported
hypotheses**, to be told apart in game):
- **Timing:** the player is moved before the arrival's collision is in the world and falls (Fort Hagen) or is pushed
  out (museum). A look in game after the exit would show whether the roof is solid when walked onto from the elevator.
- **Overlap:** the player capsule overlaps a body at the arrival (the museum ceiling 1.8 m up; the Cambridge door frame;
  the Fort Hagen elevator rig 1.2 m away), and the engine resolves it by moving the player.

## Object check (read-only, PC)
`scripts/terrain/arrival_objects.py <core staging dir> <arrival_ground.json> [--radius 20]` reads the core's
objects.json and skipped.json around each marker and read position. It lists every placed reference within the radius
nearest first, with its class, model, recorded collision kind, z and height relative to both points. It also lists the
skipped references in the FO4 cells the radius touches (these carry no position, so they are candidates only). What to
look for:
- Fort Hagen 02: an object near z 95 with collision "none", or a skipped one in the cell (a model over --max-tris, or
  one that failed to convert).
- Museum: an object under the read position whose top could be near z 26.7 (positions are origins; there are no bounds).
- Cambridge: an object at the marker that would block the arrival.

## The terrain check's script
`scripts/terrain/arrival_ground.py <core staging dir> <door_rounds_judge.json>` takes each WRONG_PLACE marker and read
position back into the core's local frame, by subtracting the build's merge offset. It prints the core BTD's ground
height under each, under all three in-quad rules (one verdict only when they agree; "in" legs are skipped). Reading it:
- Got z on the ground: the player stood on terrain.
- Marker above the ground: the marker floats, or it stands on an object that is not terrain.
- Marker below the ground: the marker is buried.
- Got above the ground: the player is on an object.

The script reads terrain only. If the ground agrees with the marker, the cause is an object: a missing or extra
collision mesh at the arrival, which a look in game or a check of the placed objects there would show.
