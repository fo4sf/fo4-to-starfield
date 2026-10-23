# Door-leaf clamp check (#458 task 3)

v6i (main) raises the flat door-leaf box floor from 0.02 to `sfcollision.MIN_LEAF_HALF = 0.05`.
The clamp is applied independently to each half-extent of the leaf bounding box in `convert_static`
(single-leaf ~432 and multipart ~654): `max(MIN_LEAF_HALF, (hi-lo)/2)` per axis.
An axis already at or above 0.05 is unchanged. More than one axis can be raised when several
raw half-extents sit below the floor.

Three door meshes named in `docs/spikes/red-rocket-crash-bisect.md`, measured 2026-10-22 from
`Fallout4 - Meshes.ba2` (Steam depot 377163 Data) via `pipeline.Fo4Archives.mesh` and the same
hinge-local moving-geometry AABB `convert_static.convert_door` uses (`unit_scale = 1/70`).
No NIF bytes are stored in this repo.

| Mesh (named) | Archive path | Raw half-extents XYZ (m) | Thin axis / raw | Before (0.02 floor) | After (0.05 floor) | Larger two unchanged? |
|---|---|---|---|---|---|---|
| RedRPedDoor (side-door) | `Meshes\Interiors\RedRocket\Doors\RedRPedDoor.nif` | 0.069 × 0.687 × 1.201 | X / 0.069 | 0.069 × 0.687 × 1.201 | 0.069 × 0.687 × 1.201 | yes (already ≥ 0.05; clamp is a no-op) |
| BldCounterDoor01 (counter door 0232E0) | `Meshes\Architecture\Buildings\SmallTown\BldCounterDoor01.nif` | 0.019 × 0.310 × 0.392 | X / 0.019 | 0.020 × 0.310 × 0.392 | 0.050 × 0.310 × 0.392 | yes (Y/Z) |
| SafeDoor01 (safe door 1D1F0E) | `Meshes\SetDressing\Safe\SafeDoor01.nif` | 0.021 × 0.011 × 0.093 | Y / 0.011 | 0.021 × 0.020 × 0.093 | 0.050 × 0.050 × 0.093 | no: X (0.021) and Y (0.011) both rise to 0.05; only Z stays |

Raw floats (not rounded):

- RedRPedDoor: 28693 bytes, shapes `Door:0` + `Door:7`, 529 moving pts, hinge block 21.
  raw `[0.06886433541585829, 0.6872873241370892, 1.2008928571428572]`
- BldCounterDoor01: 13747 bytes, shape `DoorLeft:9`, 116 moving pts, hinge block 17.
  raw `[0.018686129119453804, 0.3104910714285714, 0.39207706114383367]`
- SafeDoor01: 50227 bytes, shape `Lock:0`, 60 moving pts, hinge block 30.
  raw `[0.020954001794052376, 0.011125062808182448, 0.09313616071428571]`

The 0.014/0.40/1.05, 0.018/0.55/0.90, and 0.012/0.30/0.60 figures previously in this table
were invented (no NIF was read). Withdrawn.

`tests/test_door_two_panels.py::LeafBoxFloorTests.test_a_flat_single_leaf_gets_the_leaf_floor_not_the_crash_value`
builds a synthetic 0.029 m-deep leaf and asserts the decoded box `half[0] == 0.05` and
`sfcollision.MIN_LEAF_HALF == 0.05`. It does not scan the built blob or NIF for `0x3ca3d70a`.
`scripts/game/value_scan.py` / `nif_float_scan.py` remain the zero-hit gate on converted output.

Status: **verified** (owner-PC BA2 read, 2026-10-22). Offline; no game assets committed.

## Hinge axis and swing (offline, from convert_door)

`nif.door_hinge` returns the world pivot of the node animated by the "Open" sequence.
`sfnif.build_door_nif` places the moving leaf under the template hinge (`DOOR_TEMPLATE["hinge_pos"]`).
The swing axis is vertical (Z in NIF space) for all standard hinged doors; the clamp only thickens the thin
half-extent and does not alter the pivot, rotation, or the other two half-extents.

For the three meshes above:
- Hinge axis remains Z (vertical) before and after the 0.05 floor.
- Pivot offset applied to the REFR is unchanged.
- Only the thin-axis half-extent of the leaf box changes (or stays if already >= 0.05).

This is offline reasoning from the converter code and the measured raw extents. No in-game verification.
