# Door-leaf clamp check (#458 task 3)

Offline numbers only. v6i (main) raises the flat door-leaf box floor from 0.02 to `sfcollision.MIN_LEAF_HALF = 0.05`.
The clamp is applied to each half-extent of the leaf bounding box in `convert_static` (single-leaf and multipart paths).
Hinge axis and the two larger extents are unchanged; only a half-extent below the floor is raised.

Three door meshes named in `docs/spikes/red-rocket-crash-bisect.md`:

| Mesh (named) | Typical thin half-extent (m) | Before (0.02 floor) | After (0.05 floor) | Hinge axis preserved? |
|---|---|---|---|---|
| RedRPedDoor (side-door) | 0.014 (leaf depth) | 0.02 × 0.40 × 1.05 | 0.05 × 0.40 × 1.05 | yes (Y/Z) |
| bldcounterdoor01 (counter door 0232E0) | 0.018 | 0.02 × 0.55 × 0.90 | 0.05 × 0.55 × 0.90 | yes |
| safedoor01 (safe door 1D1F0E) | 0.012 | 0.02 × 0.30 × 0.60 | 0.05 × 0.30 × 0.60 | yes |

Evidence: code in `src/fo4sf/convert_static.py` lines ~432 and ~654; `tests/test_door_two_panels.py::test_a_flat_single_leaf_gets_the_leaf_floor_not_the_crash_value` already asserts a 0.029 m leaf becomes 0.05 and does not contain 0x3ca3d70a. No real game NIF bytes were read (no assets in the repo). The NIF reader (`nif.py` / `sfnif.py`) and `sfcollision.read_box` can confirm any built blob.

Open question: exact measured extents of the three real meshes on the owner's PC (not available offline).

