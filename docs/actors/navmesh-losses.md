# R06 navmesh-loss inventory

Converter sources: `src/fo4sf/navmesh.py`, `docs/actors/navmesh-conversion.md` on `origin/main` at `d628b56`.
`convert()` cuts FO4 exterior NAVM at Starfield 100 m cells and writes NVNM / NVMI. Cover, ledge types 1/2, unlisted doors, and NVMI traversals are dropped. Do not patch `navmesh.py`.

## Retain vs drop

| Class | Converter | Pin | Red Rocket sample | Proposed Starfield translation |
| --- | --- | --- | --- | --- |
| Triangles and edges | retain | `navmesh.py:516-599` `convert()`; `798-819` `piece_arrays()` | 63,875 FO4 tris → 68,132 SF tris in 156 NAVM | Already: verts/70, adjacency, cell-line edges |
| Cover records and cover flags | drop | `navmesh.py:542` `cover_entries`; `550-551` cover flags; `836` `piece_nvnm` writes `cover=[]` | 11,947 entries, 5,830 triangles | Map FO4 8 B cover + left/right flags onto SF 12 B cover arrays |
| Ledge-link types | drop | `navmesh.py:659-661` `type != 0` → `fo4_links_ledge_type1_2` | 396 dropped | Map FO4 types 1/2 (jump up/down) onto SF NVMI 60 B traversals (SF links are type 0 only) |
| Door links | retain if `door_refs` else drop | `navmesh.py:692-703` | 1 kept (`0007895C`), 8 dropped | Keep door triangle + NVMI linked door when the REFR is a converted rigged DOOR |
| NVMI traversal data | drop | `navmesh.py:840-851` `piece_nvmi(..., traversals=[])`; `convert()` never reads FO4 NVMI | not counted here | Map FO4 ledge / preferred-path traversals onto NVMI 60 B entries; outlines still omitted |
| Cell cuts and portal links | retain | `navmesh.py:635-638` cell-line; `639-686` type-0 portals | 2,145 cell-line; 1,959 portals (2 no overlap); 749 outside | Already: cell-line pairs + type-0 portal if sub-edges overlap ≥ 1 cm |

## Labels

- **verified:** `convert()` / `piece_nvnm` / `piece_nvmi` on the six fixtures in `tests/test_navmesh_losses.py`. Import of `fo4sf.navmesh` succeeds on this head.
- **supported hypothesis:** Red Rocket counts from `docs/actors/navmesh-conversion.md` §2 (sample not in git; game not run).
- **unresolved:** cover semantics (doc §1.1); FO4 ledge → SF traversal mapping; FO4 NVMI input is unused; per-class door/NVMI/triangle counts beyond the doc table.

## Fixtures

`tests/test_navmesh_losses.py`: one tiny NAVM per class for geometry, cover, ledge, unmapped-door and cell-cut; those
assert retain or drop on `convert()` output. `test_piece_nvmi_emits_empty_traversals` does not feed an FO4 NVMI row
(`convert()` never reads FO4 NVMI); it asserts `piece_nvmi` emits empty traversals/outline.

## Resume note

1. Done: re-pinned this table to `navmesh.py` on `d628b56`. Six fixtures now call `convert()`, not `None`.
2. Cover, ledge types 1/2, doors missing from `door_refs`, and NVMI traversals stay drops.
3. Next: a converter owner maps ledges → NVMI traversals and cover arrays; Grok does not patch `navmesh.py`.
4. Fixtures: `tests/test_navmesh_losses.py`.
5. Historical: PR #69 (pos/xyz aliases) is already merged; this note does not depend on it.
