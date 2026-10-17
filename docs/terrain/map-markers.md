# Map markers: overlay location chain (playtest row 7)

Author: Grok, 2026-10-17. Status: **research + plan, offline**. Nothing written into the overlay plugin; nothing run
in game. Labels as in the other terrain docs: **verified** = read from files, **supported** = hypothesis with
evidence, **unresolved** = open. Owner playtest row 7 (fast travel to The Frontier from the overlay map hung). Plan
section 5 of [commonwealth-build-plan.md](commonwealth-build-plan.md): "FO4 map markers -> LCTN/REFR".

## What hangs today

The overlay has a Location (`FO4Core_CommonwealthLocation`) with `LocTypeOverlay` and parent `SSol_PMars_Surface`, so
it shows as a Mars overlay. It has **none** of the map-marker / fast-travel records a vanilla unique overlay or
landing overlay carries.

Pinned `FO4TerrainCore.esm` (`terrain_core64k`, read-only):

- LCTN `01000802` `FO4Core_CommonwealthLocation`: `LCSR` absent (0 bytes), `LCID` absent, `FULL` "Commonwealth 00 (FO4
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
| flags | `00000C00` |
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
LCRT formid, REFR formid, WRLD formid, 0, 0xFFFFFFFF
```

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

### GO (next PR, writer + synthetic tests; Claude scratch overlay for in-game)

One persistent MapMarker `REFR` in the Commonwealth overlay:

- `NAME` STAT `00000010`, empty `XMRK`, `FNAM` `0x1B` and `TNAM` `0x17` (LC172, because we Duplicate that location, not
  a landing overlay).
- Position: the Red Rocket COC (`FO4Core_RedRocketSpawnMarker`), overlay-local metres, same cell.
- After the existing `MasterSpecialReferences.Clear()` (that drop of LC172's snow-globe `LCSR` and LC172's own marker
  form id stays; those refs are not in our world), append one `LCSR` `MapMarkerRefType` → that `REFR` → our WRLD, and
  `LCID` that `REFR`.
- Tests: `LCSR` 20-byte stride, empty `XMRK`, `LCID` matches the marker; the snow-globe `LCSR` is not copied.

Do **not** stamp a PCM 3 × 3 landing overlay over the unique 64-cell Commonwealth overlay. Do **not** add ship pads
or `LinkShipLandingOverlayMapMarker` in this first change.

### NOT go yet

- Full FO4 map-marker promotion class (needs `Fallout4.esm` `XMRK`).
- Ship landing pads / `ShipLandingMarkerRefType` `LCSR`.
- Replacing the unique overlay with a landing overlay.

### If the Frontier hang remains after the first overlay

Second PR: add the landing-overlay `XLKR` (`LinkShipLandingOverlayMapMarker` from a pad to the marker) **without**
swapping the world type. Still no PCM stamp. Claude runs the game.

## Acceptance

Claude: scratch overlay from this writer, `coc` Red Rocket, open the planet / overlay map, confirm one icon at the
station, then retry Frontier fast travel. Offline `check` cannot see a hang.
