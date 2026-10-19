# Supporting records not covered by a mechanism file (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: **verified** /
**supported hypothesis** / **unresolved**.

A sweep of every record type in Fallout4.esm against the mechanism files found these left over. Counts are
**verified** (docs/measurements, base games only); record names and whether each game defines the record are
**verified** from xEdit's `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`. The "role" column is the record's purpose
as the CK uses it, labelled per row.

| record | FO4 / SF count | Starfield defines it | role | verdict |
|---|---:|---|---|---|
| RFGP Reference Group | 6,116 / 80,584 | yes; adds RSGD resource generation data (biome resources) | groups placed refs, for pack-ins placed as one unit (supported hypothesis) | translate; leave the resource block empty (fences planet resources out) |
| LAYR Layer | 3,832 / 6,348 | yes | editor layers that refs belong to (supported hypothesis) | data copy, optional; useful to keep for debugging converted cells |
| TRNS Transform | 949 / 712 | yes | position, rotation, scale and zoom of an item in inventory and inspect views (supported hypothesis) | translate; wrong values only make inventory previews look off |
| ADDN Addon Node | 255 / 77 | yes, **without** FO4's SNAM sound field | effects (particles, lights) attached to meshes by node index | translate; sounds move to Wwise ([radio-music-sound.md](radio-music-sound.md)) |
| SCCO Scene Collection | 199 / 0 | yes (empty in Starfield.esm) | groups a quest's scenes with editor layout coordinates (verified fields: quest, scenes, coordinates) | drop or data copy; editor data, no runtime role expected (supported hypothesis) |
| CLFM Color | 166 / 12 | yes | named colors for hair, tints and UI | translate with faces ([actors-and-npcs.md](actors-and-npcs.md)) |
| GRAS Grass, TREE Tree | 82 / 189, 1 / 0 | GRAS yes, TREE **no** | ground cover and (legacy) trees; FO4's trees are mostly STAT | see [../next-phase/trees-grass-terrain.md](../next-phase/trees-grass-terrain.md) |
| FLOR Flora | 53 / 300 | yes | harvestable plants (tato, mutfruit, corn) giving an ingredient | translate; harvest yields point at converted ALCH/MISC |
| AMDL Aim Model | 51 / 110 | yes | weapon recoil, cone of fire, sway | translate with weapons ([items-crafting-modding.md](items-crafting-modding.md)) |
| EQUP Equip Type | 38 / 25 | yes | hand and slot rules for equipping | map to Starfield's equip types by role |
| ZOOM Zoom | 16 / 118 | yes | scope and iron-sight zoom and overlay | translate; scope overlays enum differs slightly (xEdit `wbZoomOverlayEnum`) |
| BNDS Bendable Spline | 12 / 14 | yes; FO4's CMPO scrap fields replaced by a material path | **power wires** and ropes, used by workshop power lines | translate the mesh side; scrap yields are ours ([workshop-and-settlements.md](workshop-and-settlements.md)) |
| AORU Attraction Rule | 8 / 11 | yes | radius, delays, line of sight, combat target: objects that draw NPC attention (the Story Manager has an Attraction Object event in both games) | translate (supported hypothesis on the runtime use) |
| AECH Audio Effect Chain, SCSN Audio Category Snapshot | 26 / 0, 11 / 0 | **no** | FO4 audio DSP chains and mix snapshots | rebuild in Wwise ([radio-music-sound.md](radio-music-sound.md)) |
| INGR Ingredient | 1 / 0 | yes (unused) | Skyrim leftover in FO4 | drop |
| PMIS placed missile | 1 / 0 | no | one placed projectile ref | drop or convert to a static |
| OVIS Object Visibility Manager | 1 / 1 | yes | engine visibility settings (supported hypothesis) | leave Starfield's own |

Records that the doors, physics and materials file covers (TXST, MATT, COLL, EXPL, DEBR, MSTT, PHZD, PGRE, MATO, GDRY,
WATR) are listed in [doors-activators-furniture.md](doors-activators-furniture.md),
[physics-and-collision.md](physics-and-collision.md) and
[materials-textures-lighting.md](materials-textures-lighting.md) once those land.

## Open questions and cheap checks

- SCCO: confirm no runtime reader (Starfield.esm has none, which supports dropping it).
- RFGP: does Starfield need RFGP for pack-ins placed by our converter, or do plain REFRs suffice? The converter
  writes plain REFRs today and they load (verified in game for the port), so RFGP is optional.

## Sources

- xEdit: https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas , .../wbDefinitionsSF1.pas
- Repo: docs/measurements/fo4_esm.json, sf_esm.json.
