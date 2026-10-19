# BACUP's Fallout 4 to Starfield pair compared with our builder (2026-10-19)

BACUP is github.com/Bryant-21/bacup (GPL-3), with its library py-creation-lib. Its files were read on GitHub only; nothing
was cloned, run or copied. Below, `S` means `py_bacup_lib/native/conversion/src`, and BACUP line numbers are approximate.

## What it is
- BACUP's own files call the `fo4:starfield` pair a "world-only MVP" that is "record-only"
  (`S/embedded/translation_maps/fo4_to_starfield.yaml`). Its README lists only the fo76, fnv/fo3 and skyrimse to fo4
  pairs as working. **Verified.**
- Nothing shows that its Starfield output was ever loaded in game. The repo has no issues or screenshots, and its tests
  only check its own output by reading it back. **Unresolved.**

## Compared with ours
| Area | BACUP | Ours |
|---|---|---|
| Terrain heights | `S/phase/terrain_btd.rs`: bicubic (Catmull-Rom) resample to 128 samples per 100 m cell, BTDB v6, LOD by stride decimation | `src/fo4sf/btd.py`, `terrain_grid.py:79`: same layout and LOD, bilinear resample |
| Land textures | from FO4 BTXT/ATXT/VTXT on the 17x17 alpha grid: up to 6 layers per quadrant (base and 5 blends), palette capped at 255 LTEX | quadrant LTEX tables copied from a template (`btd.py:11`); make_core64c reads no VTXT/ATXT |
| Placed objects | REFR only; ACHR, PGRE and NAVM dropped; no DOOR section in the map, so door references are dropped (**supported hypothesis**) | doors converted with rigs or as load doors, actors and markers handled separately |
| Movable props, collision | MSTT record fields only; no meshes, havok, mass or collision | meshes converted, FO4 collision kept, movable props get a dynamic body |
| Teleports | drops an XTEL whose door does not resolve ("a dangling teleport can crash cell loading") | XTEL only between placed pairs (PluginSpike TeleportLinks); outdoors via FO4SF_LoadDoor VMAD |
| Scale | 1/69.99125 (one FO4 cell = 58.5216 m), rotations and XSCL unchanged | 1/70; the difference is 3.75 m over 30 km, uniform, not a crash cause |

## Worth borrowing
1. **FO4 land-texture layering from VTXT/ATXT** with the 255-LTEX cap: our terrain uses a template, so FO4 roads and
   dirt patches do not show. This is a later-phase terrain item; we would write it ourselves from the published format,
   not copy GPL code without the owner's decision (AP-60).
2. **The dangling-teleport rule.** It matches what our interior writer already does. Unresolved: whether the core's
   FO4SF_LoadDoor VMAD or an XTEL can point at a reference that does not exist (check make_core64c's load-door writer). It is
   cheap to check offline and belongs on the crash list after props and door rigs.
3. Its LIGH, WATR and LGTM byte relayouts are checked against vanilla Starfield data; compare them with
   `scripts/terrain/fo4light.py` when lighting comes back.

## For the Red Rocket crash
BACUP converts no meshes, collision or doors for this pair, so it says nothing about our suspects (props physics and door
rigs). The bisect plan stands (red-rocket-crash-bisect.md).
