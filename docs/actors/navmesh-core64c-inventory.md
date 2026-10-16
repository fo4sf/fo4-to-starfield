# R06: core64c navmesh coverage inventory (real numbers)

Author: Grok, 2026-10-16. Offline only: no game, no runner. Labels: **verified** on the files named
below; not in-game acceptance.

core64c is the 64 x 64 Starfield-cell overlay `FO4Core_Commonwealth` (cells x,y in [-32, 31], 6.4 km;
docs/terrain/core64c.md). This pass runs `scripts/actors/navmesh_inventory.py` on per-cell stats built
from the staged plugins and Fallout4.esm.

## Files read

| File | Size | sha256 | What was counted |
|---|---|---|---|
| `Fallout4.esm` | 330,745,373 B | `ae7be31a59052f926474a767d9dbfbcc7f19af4ad2070491f7f40d821b2520eb` | Commonwealth `NAVM` in FO4 cells x,y -55..54 (12,100 cells). 7,047 NAVM, 7,047 NVNM parsed, 0 parse errors |
| `FO4TerrainCore.esm` (`C:\Modding\staging\terrain_core64c`) | 46,114,630 B | `924e182bb9b8c7894ed9ef4e743a328d8961955547debb5888e47a8a901fd927` | every record: **0 NAVM**, 1 WRLD `FO4Core_Commonwealth`, 4,097 CELL, 648,360 REFR, 11,699 STAT, 70 DOOR |
| `FO4SliceRedRocketCore.esm` (`C:\Modding\staging\slice_cave_core64c`) | 1,563 B | `a44a4c3761089d8aa08692ef36f56bfe6386c25487ee9a3e854ee27cc3cf5ec8` | every record: **0 NAVM**, 1 WRLD `FO4Core_Commonwealth`, 3 CELL (`FO4Port_RedRocket01`, `FO4Core_RedRocketSpawn`, one unnamed `01001805`), 4 REFR |

FO4 grid bounds are the FO4 cells whose 4096-unit squares overlap overlay metres [-3200, 3200), matching
the 12,100-cell window in docs/terrain/core64c.md. Parser: `fo4land.iter_subrecords` via
`navmesh.world_navmeshes`, then `navmesh.parse` on each `NVNM`. Triangle area is XY m² after FO4 units / 70;
each triangle is binned by XY centroid into a 100 m Starfield cell.

## First finding (**verified**)

The exterior plugin carries **no NAVM at all**. The slice plugin also has **no NAVM**. Starfield-side
coverage in the overlay is zero triangles in zero cells. The loss is every authored Fallout 4 exterior
navmesh that lands in those 64 x 64 cells.

## Totals

| | FO4 (binned into overlay cells) | Starfield plugins |
|---|---|---|
| Overlay cells with any navmesh | **1,069** of 4,096 | **0** |
| Triangles | **3,439,338** | **0** |
| XY area | **9,079,629.822 m²** | **0** |
| NAVM records | 7,047 (Commonwealth cells -55..54) | 0 + 0 |

`navmesh_inventory.py` (default tols 0.5): **1,069 lost, 0 reduced, 0 kept**. 3,027 overlay cells had no
FO4 navmesh to lose (ocean / empty). JSON: `docs/actors/data/core64c-fo4-navmesh.json`,
`core64c-sf-navmesh.json` (`{}`), `core64c-navmesh-report.json`, `core64c-navmesh-meta.json`.

## Three worst overlay cells (FO4 triangles, all missing in SF)

| Starfield cell | FO4 triangles |
|---|---|
| `2,-4` | 9,252 |
| `2,14` | 7,881 |
| `14,6` | 7,509 |

Downtown Boston is in this band: docs/terrain/core64c.md already names cell `(0, -4)` as the densest
*object* cell (6,049 refs). The densest *navmesh* cell in this inventory is the neighbour `2,-4`.

## What this does not say

- Not a claim about runtime-generated navmesh on BTD (R0 / N1a). This count is authored `NAVM` records
  in the plugins.
- Not a conversion of the 7,047 FO4 navmeshes. exp2d converted 16 FO4 cells around Red Rocket
  (105 navmeshes, 63,875 triangles) into 156 Starfield NAVM; that plugin is not core64c.
- Commonwealth-scale production of exterior NAVM is the next R06 question, given the exterior plugin
  has none.
