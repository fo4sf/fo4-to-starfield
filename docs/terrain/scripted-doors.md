# Scripted load doors: exterior FO4 load doors into the converted interiors

Author: Claude, 2026-10-16. Status: **offline only**. Nothing deployed, nothing run in game. Labels as in the other
terrain docs: **verified** = read from files, **supported** = hypothesis with evidence, **unresolved** = open.
Records read raw with `src/fo4sf/fo4land.py` and `scripts/terrain/vmad_patch.py`; the design pass (2026-10-16,
workflow wf_f78e6bf6) read the VMAD layout off `Starfield.esm` 1.16.244 and off a plugin Mutagen 0.55.0-alpha.67
wrote; this build reproduces its bytes exactly.

## What a door pair is

A Fallout 4 load door is a persistent DOOR reference with an XTEL (the destination door, an arrival point and a
heading); both ends point at each other. Our builds place both ends as plain STAT references without XTEL (the core
places the exterior one, FO4Port.esm the interior one), and a vanilla-style XTEL door failed in game because a
persistent reference of the overlay reads its unmerged position (docs/slice/door-frames.md, JOURNAL 2026-10-13 a2).
The scripted door keeps every record temporary and moves the player with Papyrus instead:
`scripts/door_bridge/FO4SF_LoadDoor.psc` (Codex, PR #243) attaches to the door reference; on the player's
activation it resolves `Game.GetFormFromFile(DestinationId, DestinationPlugin)` and calls `MoveTo` on it. The two
properties are the whole contract: `DestinationPlugin` (string, the plugin's file name) and `DestinationId` (int,
the destination reference's plugin-local id, 1..0xFFFFFF). No plugin masters the other.

Per door, this build writes:

| side | record | where | what |
| --- | --- | --- | --- |
| exterior (FO4TerrainCore.esm) | ACTI `FO4Core_door_<6 hex>_<plugin>` | appended after the lights, one per FO4 door base | the converted door mesh (collision as the STAT it replaces), FULL "Door" (FO4's door names are localized string ids; `--names` can give the FULL), PNAM cc4c3300, FNAM 0, JNAM 360 (the activators' vanilla majority) |
| exterior | the door REFR | **its original slot** (as every promoted class) | base = that ACTI; VMAD: one local script FO4SF_LoadDoor, `DestinationPlugin` = "FO4Port.esm", `DestinationId` = the interior arrival marker |
| exterior | arrival marker REFR | new id after every other record (lights included), in the cell of the point | XMarker 00003B:Starfield.esm, temporary, at the interior door's FO4 XTEL arrival / 70 with its heading: where the interior door's MoveTo lands the player |
| interior (FO4Port.esm, `vmad_patch.py port`) | the door REFR 01007D0B-style | unchanged record + VMAD | `DestinationPlugin` = "FO4TerrainCore.esm", `DestinationId` = the exterior arrival marker |
| interior | arrival marker REFR | the port plugin's next free id + k, in the CELL's **persistent** children group | XMarker, persistent, at the exterior door's FO4 XTEL arrival / 70 with its heading: where the exterior door's MoveTo lands the player |

Why the interior destination is a persistent marker and not the door itself: a temporary reference of an unloaded
cell is not in memory, so `GetFormFromFile` from outside would return None and the script refuses (the design pass's
risk 1 / 6; Skyrim and FO4 behaviour, **supported**, not yet seen in Starfield). Interiors have no overlay merge, so a
persistent reference reads its written position there (docs/terrain/overlay-records.md). The exterior destination
stays temporary on purpose: every temporary reference of the overlay reads merged (local + (-1200, -2700)), which is
where the door is drawn; whether a temporary marker resolves from inside the interior is the open question of Step 0
below.

## Path

```
python scripts/terrain/make_cluster.py doors --work <core64c work> --build <core64i> --port <integ_1017> --out doors.json
python scripts/terrain/make_cluster.py merge --out cluster_j.json commonwealth_cluster_i.json doors.json
python scripts/terrain/make_core64c.py stage --work <work> --core <terrain_core64> --out <core64j_doors> --sf-esm <Starfield.esm> --cluster cluster_j.json --navmesh <navmesh.json>
python scripts/terrain/make_core64c.py check --work <work> --core <terrain_core64> --out <core64j_doors> --sf-data <Starfield Data> --fo4 <Fallout4.esm>
python scripts/terrain/make_core64c.py compare-ids --out <core64j_doors> --against <core64i>
python scripts/terrain/vmad_patch.py port  --port <integ_1017> --core <core64j_doors> --out <integ_1017_doors>
python scripts/terrain/vmad_patch.py check --port <integ_1017> --out <integ_1017_doors>
```

1. **`make_cluster.py doors`** reads every exported Door reference with an XTEL (band exports) and keeps those whose
   destination door is a reference of a converted interior of the port staging (its `<cell>.json` exports); both
   sides must be placed (the exterior by the build's objects.json, the interior by the port's formids.json) and the
   interior door must link back. A door with a missing side goes to `door_skipped` with the reason and is never
   promoted. Each entry carries the FO4 base, editor id and model, the converted model, both arrival points (XTEL
   arrival / 70, rotation) and XTEL flags, the interior door's port id and CELL, and `destination.id` = the interior
   marker's id, which is the port plugin's HEDR next object id + k (read from the plugin; it must equal the highest
   own id + 1, else refused). `doors_port` records the plugin and that next id, so `vmad_patch.py port` can refuse a
   port that changed. `merge` accepts the two keys.
2. **`make_core64c.py stage --cluster`** promotes `doors` like the other classes (`cluster_doors`: one slot plan with
   containers, items, activators, terminals, workshops and benches; a source in two classes is refused, as are two
   doors sharing a destination or an interior door, a bad plugin name or id, an arrival outside the overlay's cells);
   the writer (dotnet/TerrainOverlays) places the door REFR in its reserved slot with the VMAD and, after the lights,
   the markers in `doors` order then the ACTIs in first-use order; formids.json gains `"doors": {src: {base, ref,
   arrival}}`. **Every id of the build without doors stays put** (compare-ids: every section identical but `refs`,
   which loses the promoted doors to `doors`, their REFR ids unchanged).
3. **`check`** adds: the door REFRs keep their slots (`check_reference_slots`), the markers and ACTIs come after
   every other record including the lights (`check_door_identities`, `doors_after`), ACTI count = distinct door
   edids (with the activators and workshops: one line per signature), and per door the ACTI fields, the REFR's VMAD
   decoded back to the script and both property values, the marker's base, position, rotation and temporary flags
   (`door_record_problems`); the markers count in the per-cell REFR totals.
4. **`vmad_patch.py port`** copies the pinned port folder into a NEW folder (every file hard-linked; the plugin and
   formids.json copied), patches the plugin record by record (the tree parser writes an untouched plugin back byte for
   byte, **verified** on FO4Port.esm) and writes doors.json + README.txt; **`check`** proves every other record
   byte-identical and in its group, each door REFR unchanged but for the inserted VMAD (which decodes to the core's
   arrival marker), the markers persistent in the persistent group at the arrival points and nothing else new, HEDR
   counts. formids.json gains `MARK:<cell edid>:<exterior door formkey>` keys.

Mutagen or a raw post-pass for the VMAD: Mutagen writes the exterior side (the design pass verified the written bytes
against vanilla; `tests/test_terrain_doors_writer.py` asserts the writer's VMAD equals `vmad_patch.load_door_vmad`
byte for byte). The interior side is a raw patch because the pinned FO4Port.esm must not be rewritten by a library
that normalizes records: the record-level byte diff is the proof that nothing else changed.

## VMAD layout (**verified**)

`int16 version 6 | uint16 object format 2 | uint16 script count`; per script `uint16 length + name | uint8 status
(0 local) | uint16 property count`; per property `uint16 length + name | uint8 type | uint8 status (1 edited) | value`
(2 string = `uint16 length + chars`, 3 int = int32). The 80-byte reference of the design pass (FO4Port.esm:0x2339):
`0600 0200 0100 0e00 "FO4SF_LoadDoor" 00 0200 1100 "DestinationPlugin" 02 01 0b00 "FO4Port.esm" 0d00 "DestinationId"
03 01 39230000`; `vmad_patch.encode` reproduces it and `decode` reads Starfield.esm's own
`DefaultRefOnTriggerEnter` example (101 bytes, an inherited script with int / object / int properties) back to the
same bytes (tests/test_vmad_patch.py). On the REFR the VMAD is the first field after EDID, before NAME (vanilla order).

## The 18 doors of the core (**verified** against the data; the design pass's census)

1,286 Door references in the 11 band exports, 373 with an XTEL, 18 into 13 of the 16 converted interiors (Vault81,
DmndValentines01, GoodneighborHotelRexford have no exterior load door in the Commonwealth worldspace). 15 are placed
on both sides and become scripted doors (11 FO4 door bases); 3 are editor-marker doors on both sides and are listed
in `door_skipped` (`08EB65` the Red Rocket cave AutoloadDoor, `0998E3` and `248AAE` the Vault 111 autoload / hidden
doors: "exterior side not placed by the build (editor_marker); interior side missing in the port (marker model)").
The first pair is Super Duper Mart `0EE661` <-> `0EE5D6`: the nearest pair whose both sides are real converted door
meshes (727.8 m from the Red Rocket spawn), nothing unusual on either record (no script, lock, owner or enable parent,
XTEL flags 0 both ways).

## Full-scale build (offline, **verified**, 2026-10-16)

`terrain_core64j_doors` = `terrain_core64c_work` + `terrain_core64` + `commonwealth_cluster_i.json` merged with
`make_cluster.py doors` (15 doors over 11 FO4 bases, 3 skipped) + core64i's navmesh.json (sha256 = core64h's).
The writer: 224 ACTI (211 activators + 2 workshops + 11 doors), 654,624 REFR (core64i's 654,609 + 15 markers), the
rest as core64i; next FormID 0xA772B (core64i 0xA7711 + 15 markers + 11 ACTI); 62 s placement, 23 s plugin, 43 s
plan. `check --sf-data --fo4`: 265 of 265 PASS (152 s), among them: slots retained over the seven classes, the 15
door REFRs keep their slots, markers 0A7711..0A771F then ACTIs 0A7720..0A772A after every other record (last other
0A7710 = the last LIGH), every door's VMAD decodes to its destination, every marker at its arrival point.
`compare-ids` against core64i: every section identical (`bases`, `containers`, `items`, `activators`, `terminals`,
`workshops`, `benches`, `lights`, `navmeshes`, `navi`, `plugin`, `world`), `refs` 628,065 same, 0 changed, 15 only in
core64i (the doors, now in `doors`, their REFR ids unchanged), `doors` added (15).

The Super Duper Mart pair (FO4 0EE661 <-> 0EE5D6), raw:

- ACTI `010A7725` FO4Core_door_018c8b_fallout4: EDID, OBND (24 zero bytes, as every promoted base), ODTY 0, FULL
  "Door", MODL fo4core\interiors\industrial\doors\indmetaldoorload01.nif, PNAM `cc4c3300`, FNAM `0000`, JNAM `6801`
  (360), no VMAD.
- REFR `0102D22C` (core64i's slot), temporary in cell (-5, 6), flags 0: VMAD
  `0600 0200 0100 0e00 "FO4SF_LoadDoor" 00 0200 1100 "DestinationPlugin" 02 01 0b00 "FO4Port.esm" 0d00 "DestinationId"
  03 01 ffde0000` (= FO4Port.esm:0x00DEFF), NAME `25770a01` (the ACTI), DATA (-469.8529, 636.7089, 42.356) rot z
  2.58121: the STAT reference's own position.
- marker REFR `010A7717`, temporary in cell (-5, 6), flags 0: NAME `3b000000` (XMarker), DATA (-469.4441, 636.0741,
  42.356) rot z 2.58121 (the interior door's FO4 XTEL arrival / 70), no XSCL.

`integ_1017_doors` = `integ_1017` with 20,395 files hard-linked; FO4Port.esm 4,083,513 -> 4,086,084 bytes;
`vmad_patch.py check`: PASS, 54,395 of 54,395 other records byte-identical and in their groups, the 15 door REFRs
unchanged but for the VMAD, the 15 markers (00DEF9..00DF07) the only new records, HEDR 54,480 -> 54,495 records,
next 0xDEF9 -> 0xDF08. The Super Duper Mart side:

- door REFR `01007D0B`, temporary in CELL 01006C46 FO4Port_SuperDuperMart01, flags 0: VMAD (87 bytes)
  `... "DestinationPlugin" 02 01 1200 "FO4TerrainCore.esm" 0d00 "DestinationId" 03 01 17770a00` (= 0x0A7717, the
  exterior marker), then NAME `5b680001` (DOOR FO4Port_indmetaldoorload02) and DATA (6.4, 17.3714, -3.6571) rot z
  4.712389 as before.
- marker REFR `0100DEFF`, flags 0x400, in the cell's new persistent children group: NAME XMarker, DATA (5.449,
  17.2909, -3.6536) rot z 4.71239 (the exterior door's FO4 XTEL arrival / 70).

## Open (Step 0 in game decides)

- Whether a temporary exterior marker resolves from inside the interior (the return trip). If not, the return
  destination must be a persistent exterior marker, which reads its unmerged position: the script would need the
  (-1200, -2700, 0) merge offset (three `OffsetX/Y/Z` properties passed to MoveTo, Codex's amendment (b)), the
  writer a persistent twin of each marker in the world's persistent cell (`w.TopCell.Persistent`, flag 0x400, the same
  local coordinates), formids.json a fourth id per door, and `vmad_patch.py port` would point the interior VMAD at
  the twin; the exterior side of the trip (into the interior) changes nothing.
- Whether `Game.GetFormFromFile` takes the plugin-local id (the FO4 convention) in Starfield.
- Whether MoveTo on the interior marker lands the player on the floor (arrival z = the door z on both sides of the
  first pair; FO4 put it there).
- FO4SF_LoadDoor.pex must be packed into an active plugin's archive (loose scripts are not read on this install): the
  stage does not place it; the deploy step must.

## Protecting the pinned interior source

The proposed door-stage preservation repair preflights every selected REFR for an
existing VMAD before modifying any door. Even an empty or matching load-door VMAD
is refused: merging existing behavior needs its own reviewed policy. Marker-map
collisions also refuse before creating output. A stage/report cannot be placed
inside either pinned input directory.

The plugin, formids.json, README.txt and door reports are generated independently;
reserved names are matched case-insensitively. Old doors_check.json is not carried
into a new stage. Each generated write replaces its destination through a new
file, so a checker run on an old hard-linked report cannot truncate the source.
Failed replacement preserves the old report and removes its temporary file.
This protects individual writes; it does not make the entire directory build a
transaction or authorize installation. Unchanged assets remain hard-linked.

Offline: nine new synthetic regressions plus seven existing codec/plugin tests
pass; successful plugin/map bytes match the parent writer exactly. No private
stage was rewritten and no native door/save test was run. Independent QA remains
required before integration.
