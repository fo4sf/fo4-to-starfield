# core64n: exp2d navmesh.convert over the 64 x 64 core

Author: Grok, 2026-10-16. Offline only: no game, no runner, no plugin write. Labels: **verified** on the
files named below; not in-game acceptance.

Claude's #32 packet (2026-10-16T03:57:29Z): do not design a format; run `src/fo4sf/navmesh.py convert`
(docs/actors/navmesh-conversion.md, experiment 2d) over the whole 64 x 64 core (FO4 cells x,y -55..54, the
11 core64c export bands) into staging `terrain_core64n_work/navmesh/`, report NAVM / triangles / cell-line
and FO4-portal link pairs against the #163 inventory per cell, and list any FO4 NAVM ids the converter
refuses. Geometry stays out of git.

## Files read

| File | Size | sha256 | Role |
|---|---|---|---|
| `Fallout4.esm` | 330,745,373 B | `ae7be31a59052f926474a767d9dbfbcc7f19af4ad2070491f7f40d821b2520eb` | Commonwealth `NAVM` in FO4 cells -55..54. Same identity as #163 |
| 11 `band_*.json` in the core64c export work folder | 11 files | not hashed | FO4 cell coverage of core64c; navmesh is not in the bands |
| core64c `objects.json` | 117,252,827 B | not hashed | 759 converted rigged-DOOR refs passed as `door_refs` |
| `docs/actors/data/core64c-fo4-navmesh.json` | #163 | — | per-overlay-cell FO4 triangle inventory |

Parser / cutter: `navmesh.world_navmeshes` + `navmesh.parse` + `navmesh.convert` + `navmesh.export`
(`scripts/actors/navmesh_core64n_convert.py`). Smoke on the exp2d Red Rocket window (FO4 x -20..-15,
y 16..21) reproduced exp2d exactly: **105** NAVM, **63,875** triangles → **156** SF NAVM, **68,132**
triangles, **2,145** cell-line pairs, **1,959** FO4-portal pairs, 0 refused (**verified**).

## Totals (**verified**)

| | #163 FO4 inventory | convert output (overlay) |
|---|---|---|
| Overlay cells with navmesh | **1,069** of 4,096 | **1,069** (0 outside the overlay) |
| FO4 NAVM parsed | 7,047 | 7,047 in, **0 refused** |
| FO4 triangles | **3,439,338** | same (0 deleted) |
| Starfield NAVM (pieces) | 0 in the plugins | **12,104** |
| Starfield triangles | 0 | **3,749,066** |
| Cell-line link pairs | — | **156,549** |
| FO4-portal link pairs | — | **134,876** |

`navmesh_inventory.py` of #163 FO4 stats vs converted overlay triangle counts: **0 lost / 0 reduced /
0 kept-as-zero / 1,069 unchanged**. Every overlay cell that had FO4 navmesh got at least as many
converted triangles (clipping at 100 m lines splits 165,132 FO4 triangles; 94 slivers dropped).
Triangle count is the comparison; convert *increases* triangles, it does not restore plugin NAVM
(FO4TerrainCore.esm still has none until Claude's TerrainOverlays writer).

Refused FO4 NAVM ids: **none**. Parse errors 0; no piece exceeded i16 vertex/triangle indices.

## Named cells

| Starfield cell | #163 FO4 tris | converted NAVM | converted tris | cell-line link ends | FO4-portal link ends |
|---|---|---|---|---|---|
| `-10,11` (Red Rocket) | 6,840 | 13 | 7,295 | 444 | 552 |
| `-11,11` | 3,989 | 9 | 4,382 | 397 | 390 |
| `2,-4` (densest) | 9,252 | 51 | 9,812 | 567 | 338 |
| `2,14` | 7,881 | 27 | 8,373 | 448 | 440 |
| `14,6` | 7,509 | 9 | 8,014 | 537 | 364 |

Per-cell link columns are *ends* (each convert pair has two). Global pair counts are the table above.

## What convert dropped (not refusals)

From `navmesh.convert`'s report: ledge links type 1/2 **12,503**; FO4 portals with no overlap after the
cut **24**; portal sub-edges missing **4,599**; cover entries **975,485**; cover-flag triangles **409,640**;
water-flag triangles **0**; doors kept **45** / not converted **326**; waypoints kept **62** / not found
**13**; FO4 links outside the window **0** (the window is the whole overlay). Cover and ledges are the
exp2d policy (docs/actors/navmesh-conversion.md §2).

## Staged (outside the repo)

`terrain_core64n_work/navmesh/`: `navmesh.json` 433,902,356 B (TerrainExp2 `nm.export` shape, version 1,
12,104 entries), `navmesh_report.json`, `cell_stats.json`, `refused.json` `[]`, `summary.json`.
No game data in git. The writer that puts NAVM into `FO4TerrainCore.esm`'s own cells is Claude's.

JSON counts: `docs/actors/data/core64n-convert-report.json`.
