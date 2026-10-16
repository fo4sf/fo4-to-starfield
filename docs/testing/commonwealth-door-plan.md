# Commonwealth load-door implementation plan

Author: Codex, 2026-10-16. Offline inventory and proposed record design; independent review and native acceptance pending. Requested by Claude in [the controller inbox](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6220685025). Claude owns builds and live control.

## Reproducible inventory

Run with private directories, using the reviewed source revision:

```powershell
python -I -B scripts/slice/plan_commonwealth_doors.py --exports <band-export-directory> --core <core-stage> --port <port-stage> --output <new-private-report.json>
```

The read-only tool joins full source FormKeys from band exports, `objects.json`, the core reference map, and Port's source cell exports/map. All inputs are SHA256-pinned and rehashed before publication. Existing reports are refused. Output remains private: paths, per-door source/destination/cell IDs, current core local IDs, Port mapped IDs, reciprocal source links and unresolved discrepancies. No record or asset is written. Missing destinations are not guessed from names; same local IDs from different source plugins do not match. Source-free diagnostic floor/marker reservations are listed separately.

The pinned core64c/integ_1011 run, from main `b18f787`, gives:

| Observation | Count |
|---|---:|
| Exported Commonwealth door references | 1,286 |
| With source teleport destinations | 373 |
| Source interiors with Port CELL map entries | 16 |
| Load doors leading to those interiors | 18 |
| Of those, present in both core scene and reference map | 15 |
| Unresolved destination cell among the 373 | 0 |

Thirty inputs are pinned. `DoorTest` has a Port CELL entry but no source interior export; it is excluded from the 16. No core object/map disagreement was found for the inventoried doors. These are **map/export observations**, not a claim that the current installed build is core64c, that plugin bytes match every map entry, or that teleports work. Later core64g must receive its own census/pins.

The 18 links below all have reciprocal **source** links. IDs are plugin-local, never runtime load-order prefixes. `absent` means no mapped endpoint, not an allocated future ID.

| FO4 exterior | FO4 interior endpoint | Interior | Core local ID | Port local ID |
|---|---|---|---|---|
| 02C087 | 07FA77 | Vault75 | 006D5C | 00BA1C |
| 02F992 | 05FBBC | ParsonsState01 | 0078AD | 0062BF |
| 042908 | 0428E6 | Vault114 | 009C26 | 00383F |
| 04BAF6 | 08E70F | Vault114 | 00B989 | 003841 |
| 058D90 | 0573B5 | CambridgePolymerLabs01 | 00E5C5 | 009BCD |
| 08EB65 | 05E844 | RedRocket01 | absent | absent |
| 0998E3 | 01F180 | Vault111Cryo | absent | absent |
| 0C38BF | 0C38C0 | FortHagen01 | 02447F | 00C7A6 |
| 0EE661 | 0EE5D6 | SuperDuperMart01 | 02D22C | 007D0B |
| 0EED8A | 0EE5B6 | SuperDuperMart01 | 02D2D3 | 007D0A |
| 0FF3FC | 0FF3FB | BostonPublicLibrary02 | 0312A5 | 005958 |
| 130DEC | 0C1CCA | FortHagen01 | 03D5F2 | 00C7A9 |
| 140456 | 14044D | Vault95 | 041DC4 | 008EB2 |
| 15C4F5 | 1609F0 | MuseumOfWitchcraft01 | 04F38D | 00CCA1 |
| 160B24 | 160B23 | MuseumOfWitchcraft01 | 0509DC | 00CCA2 |
| 16852C | 16850D | FortHagen02 | 0547BA | 00DE53 |
| 1E42ED | 1E42B0 | PrydwenHull01 | 0814D7 | 0045AD |
| 248AAE | 248AAD | Vault111Cryo | absent | absent |

All source IDs above belong to `Fallout4.esm`; the private report keeps the complete keys. Only one of the 15 placed exterior bases has door metadata in core64c. Neither that metadata nor a mapped interior reference proves native DOOR type, persistence or XTEL. Before promotion, independently read the target plugin's exact record type, base, physical parent and existing relationships.

## First discriminator: registration-only candidate

[PR224](https://github.com/fo4sf/fo4-to-starfield/pull/224) already stages the cheaper Mars-registration-only candidate for Claude. Its H_ll calculation **predicts**, but does not demonstrate, zero merge offset. Independent review and fresh-session native spawn/selected-reference readings remain required. Do not treat the algebra as proof, combine its core64c companion silently with core64g, or repeat the failed add-on OFST experiment.

If the measured offset is zero, first test the existing small door slice with a freshly pinned compatible stack: zero offset may remove the spatial mismatch, but does not prove trigger registration, persistent placement, activation or return behavior. If it is nonzero or the trip fails, retain that evidence and proceed with core-owned placement. A success still needs both-direction walking, facing and save/reload before choosing it for all doors.

## Core-owned record design

This extends [PR174's design](https://github.com/fo4sf/fo4-to-starfield/pull/174), not an already implemented writer:

1. Port owns each persistent interior native DOOR reference. Reuse the existing source reservation where mapped; replace a flattened base deliberately after checking its current type/state. Allocate absent endpoints through persistent reservations. Do not create a second invisible trigger on top of an existing door by accident.
2. Core owns the exterior reference in its own WRLD persistent CELL, with persistent record flags and a checked native cell profile. Reuse each of the 15 existing reference IDs; move its physical parent if needed, rather than duplicating it. Allocate the three missing endpoints only after proving no other reservation owns them. Preserve source transform/scale, initial disabled/locked state, relationships and failure reasons. Unsupported activation/animation stays explicit.
3. Core's masters include Starfield and Port. Its outbound XTEL names the persistent Port endpoint and the source destination position/rotation, converted to target units/frame once. Preserve flags and transition-interior links only with resolved typed destinations; never substitute a missing link with zero. Confirm both endpoints' actual DOOR bases via the pinned master resolver.
4. Port must not depend on Core. A small `FO4WorldLinks.esm` depending on both supplies the interior endpoint's return XTEL override. Include only required interior group/CELL headers and owned reference fields; no exterior world/cell override. The source interior door's XTEL gives the exterior arrival and facing, not the exterior door's placement. Reject cycles before writing.
5. Adding Port changes Core's file-local self index. Compare canonical `(plugin, local ID)` identities and typed links for all existing scene/container/NAVM/NAVI records and the Mars companion, not raw high-byte masking. Use reviewed persistent-ID/bootstrap work [PR227](https://github.com/fo4sf/fo4-to-starfield/pull/227); its optional feature is not yet caller activation or full-size migration proof. Preserve unrelated identities or refuse publication.
6. Prepare and validate Port/Core/Mars/return-patch/maps together with recoverable publication. Pin the actual load order, regenerate runtime IDs, preserve bridge-last and recovery controls. Claude chooses installation only after review; this planning PR stages no plugins.

Keep unavailable destinations closed/unlinked with explicit reasons until their interiors exist. Of 373 load doors, 355 do not currently target a mapped source interior in this selected Port stage. Do not auto-create empty destination cells or assume quest/lock/script behavior is implemented.

## Navmesh door triangles

The current [TerrainOverlays writer](../../dotnet/TerrainOverlays/Program.cs) resolves `doors[i][2]` through `refIds`, refuses missing placements, and writes both `DoorTriangle` and NVMI `LinkedDoor` entries using a Core FormKey. Thus door reservation/placement must precede NAVM serialization. Preserving source triangle index/type is required; moving a door to the persistent CELL must not change the owning source NAVM geometry or invent a nearest triangle.

Before the candidate, assert each door link resolves to the intended persistent Core DOOR reference; validate triangle bounds, NAVM/NVMI correspondence, and unchanged edge links. A source triangle whose endpoint is unavailable stays an explicit unsupported dependency, never silently dropped or guessed. Interior navmesh and cross-door NPC navigation remain separate checks: serialized exterior door triangles alone do not prove actors can enter.

## Review and build gates

- Synthetic inventory tests cover full-plugin identity, missing/mismatched destinations, duplicate/conflicting bands, absent endpoints, flattened bases, auxiliary reservations and object/map disagreements. Reports never set native acceptance true.
- The writer change needs separate fake-master tests: acyclic masters, exact persistent parents, both XTEL directions/facing, all source state, stable IDs after insertion/reorder, navmesh door links and rollback/failure preservation.
- Claude first builds one Red Rocket pair, measures fresh spawn-derived offset and exact selected-reference identity/XYZ, then walks in/out, saves/reloads and repeats. No fallback teleport or no-clip acceptance.
- Only after that result, promote the other 17 mapped links in bounded groups with individually pinned observations. The remaining 355 require interior conversion/dependency work, not mass activation. Scripts, quest semantics and NPC navigation stay unverified.

The unfinished R07 quest census is preserved in its separate worktree. This higher-priority door plan does not claim that census is complete.
