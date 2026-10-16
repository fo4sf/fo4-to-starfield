# Scripted load doors: the record writer

The native XTEL door did not merge in the overlay world (JOURNAL 2026-10-13 slice_door_1013 a2, 2026-10-15 cave_fixA,
cave_probes11, 2026-10-16 cave_ofst: a persistent reference reads its unmerged position, an add-on cell override moves
the arrival or crashes). The fallback is a scripted activator: Codex's `scripts/door_bridge/FO4SF_LoadDoor.psc`
(PR #243) on a temporary reference, `OnActivate` -> `Game.GetFormFromFile(DestinationId, DestinationPlugin)` ->
`MoveTo`. This page is the writer of the records that script needs, built so every placed load door into a converted
interior follows by data. First pair: Super Duper Mart (exterior FO4 `0EE661`, interior FO4 `0EE5D6`), chosen in the
design pass as the nearest pair whose both sides are real converted door meshes with nothing unusual on either record.

## The contract (the .psc)

`Scriptname FO4SF_LoadDoor extends ObjectReference`, `string Property DestinationPlugin Auto`, `int Property
DestinationId Auto` (the destination's plugin-local id, 1..0xFFFFFF; the load-order byte never enters a record: the
owner's and the runner's load indices differ). `make_core64c.DOOR_SCRIPT / DOOR_PLUGIN_PROPERTY / DOOR_ID_PROPERTY`
hold the three names; `tests/test_make_core64c.py` reads the .psc and fails when they drift. The `.pex` is compiled by
`scripts/door_bridge/compile_load_door.py` and must ship in an archive of an active plugin (loose scripts are not read
on this install); the writer below does not stage it.

## The records

Exterior (FO4TerrainCore.esm, written by dotnet/TerrainOverlays inside the core build, as every core64 object):

| record | what | identity |
|---|---|---|
| ACTI `FO4Core_door_<6 hex>_<plugin>` | one per FO4 door base: FULL = the FO4 door's name ("Door", "Hatch", "Manhole", read from Fallout4.esm + Strings), MODL = the converted mesh core64c placed, OBND = the collision bounds of that mesh (`make_core64c.model_bounds`; the FO4 base's OBND / 70 when it has none), PNAM `cc4c3300`, FNAM 0, JNAM 360 (the vanilla majority), no VMAD | NEW, after every record of the build without doors (the NAVMs included), first-use order |
| REFR (the door) | the door's own placed reference: same slot, same cell (temporary), position / rotation / scale as objects.json, base = the ACTI, VMAD = `FO4SF_LoadDoor` Local with `DestinationPlugin` "FO4Port.esm" and `DestinationId` = the interior door REFR's FO4Port local id | the slot core64c gave it (ReferenceIdentityPlan, as containers and items: "doors" is a promoted class) |
| REFR (arrival) | XMarker `00003B:Starfield.esm`, temporary, in the cell of the FO4 outside arrival point (the interior door's XTEL / 70, its rotation): where the interior door's `MoveTo` lands the player | NEW, after the ACTIs, doors order |

`formids.json` gains `"doors": {src: {"base", "ref", "arrival"}}`; every other section of a build with doors is
identical to the build without them (verified on core64i_doors against core64h: bases, refs, containers, items,
navmeshes, navi).

Interior (FO4Port.esm): `scripts/terrain/make_port_doors.py stage` hard-links the pinned interiors staging into a NEW
folder, copies the plugin and inserts, with `scripts/terrain/vmad_patch.py`, the same script into the interior door
REFR (`DestinationPlugin` = "FO4TerrainCore.esm", `DestinationId` = the arrival marker's local id). No record is
added, no id changes: the record's size and the five enclosing GRUP sizes grow by the VMAD, nothing else moves. The
forward trip lands on the interior door reference itself (the brief's choice: the pinned Port has no marker and a
new Port id would collide with #251's reservation); the FO4 inside arrival point is kept in the cluster entry
(`arrival_in`) for a marker should the player materialise inside the door panel.

## VMAD layout

Starfield.esm 1.16.244, 60 REFR VMADs read raw (design pass): `int16 version 6 | uint16 object format 2 | uint16
script count | per script: uint16 name length + name, uint8 status (0 Local), uint16 property count | per property:
uint16 name length + name, uint8 type (2 string, 3 int, 1 object = uint16 0 + int16 -1 + uint32 FormID, 4 float, 5 bool,
11..15 arrays), uint8 status (1 Edited), value`. Mutagen 0.55.0-alpha.67 writes a Starfield REFR
`VirtualMachineAdapter` with exactly that layout (verified in the design pass and again by
`tests/test_terrain_doors_writer.py`: the writer's bytes equal `vmad_patch.encode`'s), so the core side is written by
Mutagen and the Port side by the raw patch, and both plugins carry one layout. The 80-byte VMAD of the Super Duper
Mart door: `0600 0200 0100 0e00 "FO4SF_LoadDoor" 00 0200 1100 "DestinationPlugin" 02 01 0b00 "FO4Port.esm" 0d00
"DestinationId" 03 01 <int32>`.

## Commands

```
# the doors list (every exterior load door into a converted interior; both sides checked against the plugins)
python scripts/terrain/make_cluster.py doors --work <core64c_work> --build <terrain_core64h> --port <integ_1016>
       --exports <exports_1011> --fo4 <Fallout4.esm> --fo4-data <FO4 Data> --out commonwealth_doors.json [--only 0EE661:Fallout4.esm]
# the core (containers + items + doors + navmesh), then its check
python scripts/terrain/make_core64c.py stage --work <core64c_work> --core <terrain_core64> --out <terrain_core64i_doors>
       --sf-esm <Starfield.esm> --cluster commonwealth_cluster_h.json,commonwealth_doors_sdm.json --navmesh <navmesh.json>
python scripts/terrain/make_core64c.py check --work <core64c_work> --core <terrain_core64> --out <terrain_core64i_doors> --sf-data <Starfield Data>
# the interior side, then its check
python scripts/terrain/make_port_doors.py stage --port <integ_1016> --core <terrain_core64i_doors> --out <integ_1016_doors>
python scripts/terrain/make_port_doors.py check --port <integ_1016> --out <integ_1016_doors> --core <terrain_core64i_doors>
```

The census over the pinned builds (2026-10-16): 1,286 Door references in the 11 bands, 373 with an XTEL, 18 into
converted interiors, 15 placed on both sides (11 FO4 door bases, 11 interiors), 3 not promotable (the Red Rocket cave
and the two Vault 111 autoload doors: editor-marker models on both sides, listed under `unplaced` with the reason).

## Checks

`make_core64c.py check`: the door slots are retained (check_reference_slots), the ACTI and marker ids are new and
consecutive after everything else (check_door_identities), ACTI count = distinct door bases, every door REFR's VMAD
parses back to the right script and property values (door_record_check, via vmad_patch), the markers stand at the
arrival points in their cells, the REFR-per-cell count includes doors and markers. `make_port_doors.py check`: every
other record of FO4Port.esm byte-identical, the GRUP tree unchanged but for the sizes on the patched chain, each
patched REFR's VMAD decoded back to the core's entry.

## What the in-game run decides

Step 0 of the design plan: whether `GetFormFromFile` resolves a temporary reference of an unloaded exterior cell from
inside the interior, and whether a persistent one lands merged. If the return trip needs a persistent marker plus the
(-1200, -2700, 0) merge offset, the writer changes in two places: the arrival marker gets a persistent twin in the
world's persistent cell (TerrainOverlays, `w.TopCell.Persistent`, flag 0x400, one more new id per door) and the Port
VMAD points at the twin with three float properties `OffsetX/Y/Z` (Codex's amendment to the .psc) that
`vmad_patch.encode` already serialises (type 4). The cluster entries and the checks carry both arrival points today.
