# Door round trips per interior batch

Claude-cloud (bridge thread), 2026-10-19. For the "Convert all interiors" work: each conversion batch gets its door
tests from `scripts/bridge/door_batch.py`, run against the plugins actually installed.

## What the batch thread sends
- The installed port's staging folder.
- The list of interior cells the batch delivers. Either `{"name": "batch07", "cells": ["Vault81Main", ...]}` as JSON,
  or a text file with one cell per line. A cell may be given with or without the `FO4Port_` prefix.

## What comes back
`door_batch.py stage --batch <file> --core <core build> --core-plugin <installed core> --port <installed port staging> --core-index HH --port-index HH --out <new folder>`
writes three things:
- **coverage.json**, one state per cell:
  - `doors`: its load doors passed every check and are planned;
  - `doors_skipped`: it has doors, but each one failed a check, with the reason;
  - `no_door`: it is in the port, but no exterior door leads into it;
  - `not_in_port`: no cell of that name is in the installed port.
- **chunk_NN folders** of at most 20 tests. A door's two legs never split. `plan-terrain` and `door_rounds.py judge`
  read each one as it is.
- **README.txt**, with the plan, run and judge lines and the night-run caps.

## Choices
- **Legs:** OUT only is the default. Each OUT leg starts with a coc inside the interior and never at the Red Rocket
  arrival. The OUT legs kept are those whose exterior arrival is at least 1500 m from Red Rocket (`--min-out-m`).
  `--legs both` adds the IN legs, which all start at the Red Rocket arrival. Use it only once that area is cleared.
- **Checks:** every door is checked as in door_rounds.py stage: the door, its base, its VMAD destination and both
  markers in the installed plugins. Nothing is planned from the build's word alone.
- **Arming:** the chunks run through `campaign_arm.py`, with the same caps and holds as the v6e queues.

## Vault 111 new-game start check (for later; proposal)
The Vault 111 thread owns the new-game start. The test side, once that start exists:
- **Start:** a new game is begun from the main menu. That is input only the owner or the reviewed runner may send.
  The "coc from the main menu" path is not used, because cycle.ps1 notes the blank character is pulled into Starfield's
  own new-game start.
- **PASS needs all three:**
  1. the bridge's first loaded position line in the Vault 111 start cell named by the new-game build;
  2. that position within 3 m of the build's start marker (resolved with FO4SF_Probe.Resolve, as the door judge does);
  3. no loaded position in any cell the build lists as Starfield's intro.
- **Inputs:** the build supplies the start cell, the marker and the intro cell list. No intro cell name is assumed here
  (unresolved until that build exists).
- **Missing evidence** (no init line, no loaded line, no resolve) is INCONCLUSIVE, never a PASS.
