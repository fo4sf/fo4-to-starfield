# Map markers: overlay location chain (playtest row 7)

Author: Grok, 2026-10-17. Status: **implemented, offline**. TerrainOverlays restores one MapMarker + LCSR/LCID per
overlay (`grok/map-marker-restore`). Nothing deployed; nothing run in game. Labels as in the other terrain docs: **verified** = read from files, **supported** = hypothesis with
evidence, **unresolved** = open. Owner playtest row 7 (fast travel to The Frontier from the overlay map hung). Plan
section 5 of [commonwealth-build-plan.md](commonwealth-build-plan.md): "FO4 map markers -> LCTN/REFR".

## What hangs today

The overlay has a Location (`FO4Core_CommonwealthLocation`) with `LocTypeOverlay` and parent `SSol_PMars_Surface`, so
it shows as a Mars overlay. It has **none** of the map-marker / fast-travel records a vanilla unique overlay or
landing overlay carries.

Pinned `FO4TerrainCore.esm` (`terrain_core64k`, read-only):

- LCTN `01000802` `FO4Core_CommonwealthLocation`: `LCSR` and `LCID` present with 0-byte payloads, `FULL` "Commonwealth 00 (FO4
  terrain)", `KWDA` `002CA99D` (`LocTypeOverlay`), `PNAM` `0001B736` (`SSol_PMars_Surface`).
- WRLD `FO4Core_Commonwealth` `XLCN` that location (already documented in [overlay-records.md](overlay-records.md) §2).
- 654,600 `REFR`: **0** carry `XMRK`, **0** `NAME` a MapMarker STAT (`00000010` / long / short / medium-long).
- One `COCMarkerHeading` `FO4Core_RedRocketSpawnMarker` at overlay-local (−989.257, 1146.514, 107.143).

The writer **does** Duplicate vanilla `LC172WorldLocation` (`3807BE`), then
`MasterSpecialReferences.Clear()` and `MasterInitiallyDisabledReferences.Clear()`
(`dotnet/TerrainOverlays/Program.cs`). Mutagen 0.55 names those lists for `LCSR` and `LCID`. Overlay-records.md
already noted the two `LCSR` statics and `LCID` were dropped; that drop is the map-marker chain.

## Starfield has no MAPM group (**verified**, Starfield.esm 1.16.244)

176 top groups. `LCRT` and `LCTN` exist. There is no `MAPM` (or `MAPR`) group.

Map markers are **placed references**: `REFR` whose `NAME` is STAT `MapMarker` `00000010` (also
`MapMarker_LongRange` `00254244`, `MapMarker_ShortRange` `00254245`, `MapMarker_MediumLongRange` `0031FB3E`).

A typical unique-overlay marker (LC172 persistent `REFR` `003E5E12`):

| Field | Value |
|---|---|
| flags | `00000C00` (Persistent `0x400` + Initially Disabled `0x800`) |
| `NAME` | `00000010` MapMarker |
| `XMRK` | empty payload |
| `FNAM` | `1b000000` (u32 `0x1B`) |
| `FULL` | null lstring |
| `TNAM` | `1700` (u16 `0x17` = 23) |
| `UNAM` | `00000000` |
| `DATA` | (37.4, 57.2, 7.6) m in `LC172World` |
| `XLKR` | `00000000 -> 0028DC51` |

`TNAM` is the marker type. What each type id draws, and the `FNAM` bits, are **unresolved**.

## LCTN links the marker through LCSR + LCID (**verified**)

`LCSR` is a repeated 20-byte (5 × u32) stride:

```
LCRT formid, REFR formid, WRLD formid, grid (two i16, Y then X), 0xFFFFFFFF
```

The 4th dword is the marker's cell as two i16, Y then X (Mutagen `LocationCellStaticReference.Grid`). The 5th is
Mutagen `Unknown = -1` (`0xFFFFFFFF` on every vanilla MapMarkerRefType row). The constructor default is 0; the
writer sets Grid from `spawn_cell` and Unknown to -1.

`LCID` is often the map-marker `REFR`. Mutagen: `MasterSpecialReferences` = `LCSR`,
`MasterInitiallyDisabledReferences` = `LCID`.

Helpers and the LC172 / landing fixtures live in `src/fo4sf/map_markers.py` (synthetic tests,
`tests/test_map_markers.py`).

### Unique overlay template: LC172WorldLocation `003807BE`

`KWDA` `LocTypeOverlay` `002CA99D`, `PNAM` `SSol_PMars_Surface` `0001B736`. Two `LCSR` entries (40 bytes) and
`LCID` `003E5E12`:

| LCRT | REFR | WRLD |
|---|---|---|
| `Landmark_SnowGlobe_RefType` `00009A42` | `00009A32` | `LC172World` `0002DF8C` |
| `MapMarkerRefType` `0002271F` | MapMarker `003E5E12` | `LC172World` `0002DF8C` |

WRLD `LC172World` `0002DF8C` `XLCN` this location. The snow-globe `LCSR` is LC172 flavour, not a map marker.

### Landing overlay: LandingOverlay01Location `003807CF`

Three `LCSR` (60 bytes). Same 5-dword stride. The extra two bind the **ship pad**, not a second map icon:

| LCRT | REFR | WRLD |
|---|---|---|
| `MapMarkerRefType` `0002271F` | `003A866E` | `LandingOverlay01` `001187EA` |
| `ShipLandingMarkerRefType` `00009105` | pad `00093DC9` | `001187EA` |
| `ShipLandingMarkerRefType_Large` `00009102` | same pad `00093DC9` | `001187EA` |

The pad `REFR` also carries `XLKR` `LandingZoneTriggerKeyword` `00267F4D` → trigger and
`LinkShipLandingOverlayMapMarker` `003A866F` → the map-marker `REFR`. Marker `FNAM` `0x33`, `TNAM` `0x2D`, flags
`00000400` (persistent only). DefaultSpaceshipLandingOverlayLocation and PCMGenericLandingOverlayLocation use the
same three-`LCSR` shape.

Related keywords (named in Starfield.esm, not required for the first writer change): `DMP_ShipLandingMarker`
`000D40EA`, `LandingZoneTriggerKeyword` `00267F4D`.

### Unique cities

`NewAtlantis` `0001251B` is a large unique overlay (hundreds of cells, many persistent MapMarker STAT). City location
editor ids are `CityNewAtlantisLocation` `0001295A` and `CityAkilaCityLocation` `00010DFB`. A 64-cell Commonwealth
overlay is the LC172 unique-overlay family, not a 3 × 3 PCM landing overlay.

## Cause of the missing chain (**verified** records)

`TerrainOverlays` (and the exp1 / exp2 writers) Duplicate `LC172WorldLocation` then clear both special-ref lists.
That throws away LC172's `MapMarkerRefType` `LCSR` and `LCID`. The Duplicate also does not copy LC172's persistent
MapMarker `REFR` into our world (cells are rebuilt empty, then objects). The pinned plugin matches: empty `LCSR` /
`LCID`, no MapMarker `REFR`.

## Playtest row 7 (**supported hypothesis**)

Fast travel to The Frontier from the overlay map started a load that never finished (bridge log rotated, game still
running). The overlay is a Mars `LocTypeOverlay` with no map-marker / ship-landing chain.

Two things can be true together:

1. Missing MapMarker + `LCSR` is why the overlay does not behave like LC172 or a landing site on the planet map
   (**supported**; records match).
2. The hang itself may be "fast travel *out of* the overlay *into a ship*" (`ConstellationFrontierShipLocation`), a
   different engine path than "show an icon on the overlay" (**unresolved** until an in-game overlay with the restored
   marker).

Restoring LC172's one MapMarker may only add a local icon. That is still the first writer change: it makes our
location match the template we already Duplicate.

## FO4 map markers

`Fallout4.esm` is not on this machine. Byte-level FO4 `XMRK` is **unresolved**.

`scripts/terrain/make_cw_overlays.py` already names FO4 landmark refs (Commonwealth, FO4 units): Red Rocket building
`0x000211C0`, Sanctuary map marker `0x00072A48`, Vault 111 `0x0009F272`, Concord `0x00082138`. `fo4land.parse_ref`
reads `NAME` / `DATA` / `XSCL` only, so a later promotion class needs `XMRK` / `TNAM` / `FNAM` on the FO4 `REFR`.
Core `selected.json` does not list a MapMarker type (FO4 markers are not a converted STAT class).

## Plan

### GO (this PR, writer; Claude scratch overlay for in-game)

One persistent MapMarker `REFR` in the Commonwealth overlay, written **after** doors/lights so reserved object FormIDs
stay:

- Duplicate LC172's persistent MapMarker `REFR` `003E5E12` (keeps empty `XMRK`, `FNAM` `0x1B`, `TNAM` `0x17`), `NAME`
  STAT `00000010`.
- Position: the Red Rocket COC spawn, overlay-local metres; persistent in the world's `TopCell` (same list as the
  XMarker anchor). `FULL` "Red Rocket". LC172's `XLKR` is cleared.
- After the existing `MasterSpecialReferences.Clear()` (LC172's snow-globe `LCSR` and LC172's own marker form id stay
  dropped; those refs are not in our world), append one `LCSR` `MapMarkerRefType` → that `REFR` → our WRLD, and `LCID`
  that `REFR`. `formids.json` `"map_markers"` maps world editor id → REFR id.

Do **not** stamp a PCM 3 × 3 landing overlay over the unique 64-cell Commonwealth overlay. Do **not** add ship pads
or `LinkShipLandingOverlayMapMarker` in this first change.

### NOT go yet

- Full FO4 map-marker promotion class (needs `Fallout4.esm` `XMRK`).
- Ship landing pads / `ShipLandingMarkerRefType` `LCSR`.
- Replacing the unique overlay with a landing overlay.

### If the Frontier hang remains after the first overlay

Second PR: add the landing-overlay `XLKR` (`LinkShipLandingOverlayMapMarker` from a pad to the marker) **without**
swapping the world type. Still no PCM stamp. Claude runs the game.

## Commonwealth markers (Claude-cloud, 2026-10-17, stacked on #296)

Status: **offline, verified by synthetic tests only**; the writer change is not built in the cloud (no .NET there) and
nothing has run in game.

`make_core64c.py stage` now writes the overlay's `map_markers` into `overlays_params.json`
(`fo4sf.map_markers.overlay_markers`), and `TerrainOverlays` writes one MapMarker REFR, one `LCSR` MapMarkerRefType row
and one `LCID` entry per entry, in this order, after every other record:

| Tag | Map name | FO4 source | Position (local m) |
|---|---|---|---|
| RedRocket | Red Rocket Truck Stop | building `000211C0` | the COC arrival (`FO4Core_RedRocketSpawnMarker`), as #296 |
| Sanctuary | Sanctuary Hills | map marker `00072A48` | FO4 position / 70, z = BTD ground |
| Vault111 | Vault 111 | map marker `0009F272` | FO4 position / 70, z = BTD ground |
| Concord | Concord | map marker `00082138` | FO4 position / 70, z = BTD ground |

FO4 positions are the ones `make_cw_overlays.py` already uses as probe landmarks (read from Fallout4.esm). A marker less
than 200 m inside the overlay stops the stage. Without `map_markers` (core64 itself, exp builds) the writer keeps #296's
single marker at the COC. The first marker keeps #296's EditorID and `formids.json` `map_markers`; all of them are in
`formids.json` `map_marker_refs` {world: {tag: id}}.

`make_core64c.py check` judges them (`map_marker_problems`): MapMarker NAME, XMRK, persistent, position, one `LCSR` row per
marker with tail `0xFFFFFFFF`, no `LCID` (see the correction below), ids after every other record. It also stops counting the markers against the
door rules (doors after everything, the persistent cell holds anchor + door markers) and compares core64's Location
without its `LCSR` / `LCID`: before this, a door build with #296's marker would have failed `check`.

The FO4 map names, the `FNAM` bits (fast travel, discovered) and the `TNAM` icon type stay LC172's (`0x1B`, `0x17`):
whether the icons show undiscovered, and which icon they draw, is **unresolved** until the in-game check.

### Correction (Claude-cloud, 2026-10-18): the markers were written initially disabled

In game on FO4TerrainCore fdd3f0a5 (markers 0A7759 to 0A775C), **no icon showed on the map** (owner). The writer
Duplicated LC172's 003E5E12 with its flags 0xC00, which include Initially Disabled 0x800. LC172's quest enables that marker.
Ours have nothing to enable them, and the writer also listed them in `LCID` (the Location's initially disabled
references). The landing-overlay marker 003A866E is 0x400 (persistent only). The writer now writes 0x400 and no `LCID`,
and `check` fails a marker that is initially disabled or listed in `LCID`. **Supported hypothesis** until the
in-game confirmation (`prid 030A7759`, `enable`, then open the map; `03` is FO4TerrainCore's load-order slot).

## Every Commonwealth marker (Claude-cloud, 2026-10-19, offline only)

Status: **built and tested on synthetic plugins; the PC export ran (2026-10-19)**: 310 Commonwealth markers, all
named; 307 left after the fixed four's own records, all inside the overlay. Nothing has run in game.

1. On the PC, `dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-mapmarkers <out.json>` lists
   every placed object of the Commonwealth worldspace that carries map-marker data (`MapMarkersExport.cs`):
   its FormID, editor id, name, FO4 position and whether it is persistent, in FormID order. The name is the marker's
   own FULL, which Mutagen reads from the Strings files next to the localized plugin, as `export-names` does. The
   output is derived game data and stays outside the repository.
2. `make_core64c.py stage ... --fo4-map-markers <out.json>` adds every named marker that lies more than 200 m inside
   the overlay (`map_markers.load_fo4_markers`, `extra_markers`, FO4 position / 70, z = BTD ground). The fixed four
   come first, so their FormIDs stay. The others follow in FO4 FormID order, tagged `M<FO4 id>`. Markers left out
   (no name, one of the fixed four, no finite position, outside the overlay, or within 100 m of a fixed marker of the
   same name: FO4's Red Rocket Truck Stop marker 024FBE, since the core's Red Rocket sits on the COC arrival) go to `map_markers_left_out.json` with
   their reason. `check` judges every marker the same way as the four.
3. `dotnet/MapMarkers` splits the core's markers into quests of at most 100 (`FO4SF_MapMarkersQuest`,
   `FO4SF_MapMarkersQuest2`, ...: 0x800, 0x801, ...). Papyrus arrays made in script hold at most 128 entries;
   whether a plugin-filled property may hold more is **unresolved**, so no quest goes near that limit. Above 20
   markers, a quest's `MaxMoves` is twice its marker count, so one session can place them all. `check` matches the
   quests, in FormID order, against the core.

Every new marker keeps LC172's `FNAM` 0x1B and `TNAM` 0x17, so they all draw one icon type; FO4's own marker types
are not mapped yet. The export carries each FO4 marker's type (`type`, `type_id`) for that later table.

Marker data in the two games (Claude-cloud, 2026-10-19). Mutagen 0.55.0-alpha.67, read by reflection on
`PlacedObjectMapMarker`:
- Fallout 4: `Flags` (Visible 1, CanTravelTo 2, ShowAllIsHidden 4, UseLocationName 8), `Name`, `Type` (an enum of
  66 FO4 icons: Cave 0, City 1, DiamondCity 2, MetroStation 6, Vault 15, ... Minutemen 57, ...), then one unknown
  byte. This is **verified** as Mutagen's layout. The byte widths on disk are **unresolved** (no `Fallout4.esm` here;
  the synthetic test writes `FNAM` 1 byte and `TNAM` 2 bytes).
- Starfield: the same `Flags`, plus `Name`, `Type` as a bare signed byte (no enum), one unknown byte, `VNAM` (u16),
  `UNAM` (a string) and `VISI` (a byte). LC172's bytes above agree: `FNAM` is u32, and `TNAM` `1700` is type 0x17
  plus the unknown 0x00 (**verified**).
- The Interiors thread reports that no Starfield marker type matches FO4's Vault, Metro or Diamond City icons. That
  is **unresolved**: Mutagen names no Starfield types, so checking it takes a census of `TNAM` values in
  `Starfield.esm` or the in-game check. Either way, a lossy FO4-to-Starfield type table is the likely shape. This takes a new core build, so it waits for the current phase's tests.

## Acceptance

Claude: scratch overlay from this writer, `coc` Red Rocket, open the planet / overlay map, confirm one icon at the
station, then retry Frontier fast travel. Offline `check` cannot see a hang.

## Markers in the merged world (2026-10-19, supported hypothesis)

With #356 the markers are enabled, yet v6 showed no icon (owner, 19 Oct). The markers are **persistent** references of
the overlay world, and a persistent reference of that world stays at its **local** position in the base world
(`0x02000803`: door probe (a), 16 Oct, docs/JOURNAL.md), while the player walks in a world made at run time that places
the core's records at local + the merge offset (`vmad_patch.MERGE_MEASURED`, (-1200, -2700)). The mission's actors hit
the same wall (#353 moves them). So the map of the world the player is in has no marker in it.

`FO4SFMapMarkers.esm` (`dotnet/MapMarkers`, `scripts/mapmarkers/make_map_markers.py stage --core <core> --out <dir>`)
is one start-game-enabled quest carrying `FO4SF_MapMarkers`: every 2 s, with the player outdoors inside the overlay's
merged extent (x -4400..2000, y -5900..500), each marker that is not at its merged spot in the player's world is
enabled and moved there (`MoveTo` onto the player with the difference as the offset, the form the door script and
the mission use), at most 40 moves per session, each logged to `fo4sf_map.0.log`. The plugin names the core's marker
REFRs by FormID, so it is rebuilt with every core build. **Verified in game** (owner, 2026-10-22, core dc751664,
plugin 46d4ca26, `fo4sf_map.0.log`): the quest started 55 s into the session, moved all four markers 15 s later
(`before=` FLT_MAX is the expected other-world reading, not a failed read; `d=` matched the player's distance), and
the four icons drew on the surface map after the owner left the area and came back. Why not at once is
**unresolved** (the map may hold its marker list until the area reloads). Still unverified: the
extent check cannot tell another world with the same coordinates apart (as the mission).

Install: `scripts/game/map_markers_install.py install --dir <staged> --starfield <game>` (game closed). It keeps its
own record, `Data\FO4SFMapMarkers.install.json`, beside exp_install's one experiment record (the core set), the way
`bridge_install.py` does, and packs the .pex into `FO4SFMapMarkers - Main.ba2` (this install reads no loose scripts).
It refuses unless the core is an active Plugins.txt line and its file in Data has the sha256 the stage pinned in
`core.json` (the plugin names that core build's records by FormID; a stage from before the pin is staged again).
`order` repeats those checks before it writes, and cycle.ps1 stops with exit 7 when it refuses. After the save loads,
cycle.ps1 runs `active` (read-only) and stops with exit 8 if the save's load order turned the plugin off. Its `order` command moves its line to the end; cycle.ps1
runs it before the bridge's, so the experiment's and FO4Port's load indexes stay as they were. Before a core swap,
`uninstall` it (its only master leaves Plugins.txt for the length of the swap, and exp_install refuses missing
masters), then install it again after; and keep it out of runner runs on a commit older than this installer.

### Overrides (Claude-cloud, 2026-10-22): the marker's own name, a lifted arrival

The owner's play test (core dc751664, plugin 46d4ca26; Install's Ctrl+Alt+K captures) found two defects once the
markers drew. (1) Every icon read "COMMONWEALTH 00 (FO4 TERRAIN)", the cell's location, not the marker's name:
the core copies LC172's marker flags `FNAM 0x1B`, which include UseLocationName (`0x8`). (2) Fast travel to
Concord put the player half in the ground: the marker sits at the terrain height `make_core64c` sampled (86.93 m),
and the arrival there has ground above it; the Red Rocket arrival, 1.9 m above its marker's landing, dropped
without harm. FO4's own marker heights are no reference (its Sanctuary marker floats 6.9 m up).

Fix, in `FO4SFMapMarkers.esm` rather than a core rebuild: `dotnet/MapMarkers build` adds an override of every core
marker REFR (the same FormKeys, so Starfield.esm joins the core as a master): flags without UseLocationName and
with Visible, enabled, the position lifted `--z-lift` metres (default 2.5, the smallest round figure above the
proven 1.9 m drop with a margin for Concord; **unresolved** until the owner's next test), name and base as the
core wrote them. The quest's `LocalZ` holds the lifted height, so the mover places the marker where the override
says; a save made before a lifted build keeps the markers at the old height (moved references outlive their
records), so the script also re-moves a marker whose height is off by more than `ZTolerance` (0.05 m), and the
build takes `--z-lift` in steps of 0.1 m only, so every change between builds reaches a saved game while a landed
move (within 0.01 m) stays. The move budget (`MaxMoves`) is saved state too, so the script starts it over when a
build changes the markers' count or height: a save whose budget the first placement spent still takes a later
lift. `check` reads the overrides back (`override <FormKey> "<name>" flags 13 at (...)`) and fails one that still
uses the location name, is Initially Disabled, is at another height, or overrides anything that is not a core
marker (the override's parents arrive as copies of the worldspace and its persistent cell; the build prunes
them to the markers). Those two copies are overrides too, and this plugin loads after the core, so `check` also
fails when either differs from the core's record: a core rebuilt after the stage (a changed world flag, as the
border fix of 2026-10-22 makes) needs a new stage, or the plugin would put the old record back. The icon (`TNAM 0x17`, a plain diamond) stays **unresolved**: which Starfield type values
draw which icons needs a survey of the vanilla markers on the PC.

Console check (no plugin needed): `prid 030A775A`, `getpos x`, `getpos y`: about (-1154, 1260) is the local spot,
about (-2354, -1440) the merged one. `prid 030A775A` then `moveto player` moves the Sanctuary marker onto the player by
hand, then the map shows whether a moved marker draws.

**Can a writer fix exist? (`dotnet/MergeProbe`, offline-checked, not run in game).** Two writer-side candidates
failed in game: the vanilla persistent-cell shape (fix A, cave_fixA_1015, refuted: the door still read local) and
WRLD OFST / CLSZ (fix E, cave_ofst_1015, FAIL NOLOAD only, which does not isolate an unmerged position). Neither
rules out every writer fix. `MergeProbe build <Starfield.esm> <out>` writes `FO4SFMergeProbe.esm`: one persistent XMarker
`FO4SF_MergeProbeMarker` (0x800) in an override of vanilla LC172World's persistent cell, 3 m east of the COC marker
0010238E, which reads merged in game (offset -500, -2300, -3.62). In game, with only this plugin added:
`coc LC172Ext01`, then `prid <its load index>000800`, `getpos x`, `getpos y`, and in the same session `prid 0010238E`,
`getpos x`, `getpos y` as the vanilla control (it must read merged, or the session proves nothing). One read is scoped
to that world, build, load order, save and session. A merged probe read says a plugin's persistent reference can
merge there, so the cause is likely in our WRLD / LCTN records (diff them next). A local read with a merged control
says persistent references this plugin adds did not merge in that setup; it supports keeping the runtime moves (the
door script, #353, this quest) as the design, but does not prove no record shape can merge.

## BACUP's FO4 to Starfield world writer (Claude-cloud, 2026-10-19, read only)

[BACUP](https://github.com/Bryant-21/bacup) (GPL-3) was read at commit `cfa3d0d` (2026-10-17). Nothing was run, and
no code is copied here. Its `fo4:starfield` pair has no evidence of loading in game; its own test is a synthetic
2x2-cell slice (`bacup_lib/tests/test_fo4_starfield_vertical_slice.py`). Findings below are **verified** against its
source:
- **Its own world, no overlay.** `native/conversion/src/phase/starfield_cells.rs` writes the FO4 worldspace as a new
  `WRLD`: a world persistent cell plus a re-latticed 100 m exterior grid (FO4's 4096-unit cells do not divide into
  100 m, so refs are bucketed by position and `XCLC` is rebuilt). It notes `Starfield.esm` measurements: block =
  grid div 32, sub-block = grid div 8, label `[y, x]` (its claim, not rechecked here).
- **Persistent refs keep their own position.** The persistent cell "never re-lattices; its children keep their
  (rescaled) positions verbatim" (FO4 position / 69.99125, our 70). No world is merged into another, so it never
  meets our case: an overlay whose runtime world places records at local + (-1200, -2700). It has no answer for the
  merge probe's question.
- **No map markers and no locations.** `embedded/translation_maps/fo4_to_starfield.yaml` drops `XMRK`, `FNAM`,
  `TNAM` and `XLOC` from every `REFR` ("codec differs between games") and drops `WRLD` `XLCN`, `TNAM`, `UNAM`,
  `ICON`. `LCTN` is not translated. Its marker-type code (`fullscreen_map_markers.py`) is for FO76 to FO4 and draws
  icons in a map mod, not in Starfield.
- **Scale.** 69.99125 FO4 units per metre against our 70 is a 0.0125 % difference: about 0.4 m across the core's
  6.4 km. Not worth a change on its own; **unresolved** which figure is exact.

Nothing to borrow for markers, locations or the merge question. Its standalone-world approach would sidestep the
offset entirely, but it is a different design from our overlay and is a decision for the world threads.

**Decided by the owner, 2026-10-19 (22:04Z, in the next-phase talk-through):** reuse BACUP's GPL-3 code, with credit,
for three ideas rather than writing our own: zero a door's transition cell when that cell is not built, keep each
cell's FO4 lighting template, and texture land per quadrant from `VTXT` / `ATXT`. None of them touches markers,
locations or the merge probe; they belong to the doors, lighting and terrain work.
