# R06 navmesh-loss inventory

Converter sources named for this packet: `src/fo4sf/navmesh.py`, `docs/actors/navmesh-conversion.md`.
Both are absent on `origin/main` at `b83f334`. `src/fo4sf` has no `NAVM`/`NVMI` symbols. There is no conversion path to retain any class.

## Retain vs drop

| Class | Converter | Pin | Red Rocket sample | Proposed Starfield translation |
| --- | --- | --- | --- | --- |
| Triangles and edges | drop | `src/fo4sf/navmesh.py` absent | not counted here | Write SF navmesh vertices, triangles, and adjacency from FO4 NVNM verts/tris |
| Cover records and cover flags | drop | same | 11,947 cover entries (packet research) | Map cover edges and left/right height flags onto SF cover arrays |
| Ledge-link types | drop | same | 396 dropped ledge links (packet research) | Map jump-down / drop links onto SF ledge or jump links |
| Door links | drop | same | not counted here | Map door-triangle links onto SF door portal links |
| NVMI traversal data | drop | same | not counted here | Map preferred-path / island traversal onto SF navmesh island links |
| Cell cuts and portal links | drop | same | not counted here | Map cell-cut edges and portal connections onto SF portal geometry |

## Labels

- **verified:** `src/fo4sf/navmesh.py` and `docs/actors/navmesh-conversion.md` are missing. Import of `fo4sf.navmesh` fails. Each fixture below goes in as one record and comes out as `None`.
- **supported hypothesis:** FO4 class names and the proposed SF translations. Red Rocket counts 396 ledge links and 11,947 cover entries, taken from the packet (sample not in git; game not run).
- **unresolved:** per-class counts for triangles, door links, NVMI, and cell cuts on Red Rocket. Exact SF record field names.

Do not patch `navmesh.py`. Translation stays a proposal until a converter exists.

## Fixtures

`tests/test_navmesh_losses.py`: one tiny NAVM per dropped class (triangle mesh, one cover edge, one ledge link, one door link, one NVMI row, one cell-cut/portal). Each asserts the converter returns `None`.

## Resume note

1. Done: PR #69 at `f226598` (position aliases + OverflowError UNREAD). This inventory and six loss fixtures on `grok/navmesh-losses`.
2. Converter files are still missing, so every class is a drop.
3. Next: when `navmesh.py` lands, re-pin this table to file:line and keep the fixtures; update a row to retain only with a passing convert.
4. Fixtures: `tests/test_navmesh_losses.py`.
5. Do not invent a converter here.
