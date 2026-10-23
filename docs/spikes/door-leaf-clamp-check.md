# Door-leaf clamp check (offline, issue #458 task 3)

v6i raised the flat-leaf half-extent floor from 0.02 to 0.05 (`sfcollision.MIN_LEAF_HALF`).

Using the repo's NIF reader and `convert_door` / `convert_multipart_door` on synthetic leaves that match the thin-leaf pattern of the named meshes (RedRPedDoor, bldcounterdoor01, safedoor01):

| Mesh (synthetic stand-in) | Natural half (m) | After 0.02 floor | After 0.05 floor | Hinge axis | Extent change |
|---------------------------|------------------|------------------|------------------|------------|---------------|
| RedRPedDoor-like          | 0.014            | 0.02             | 0.05             | unchanged  | thickness only |
| bldcounterdoor01-like     | 0.012            | 0.02             | 0.05             | unchanged  | thickness only |
| safedoor01-like           | 0.015            | 0.02             | 0.05             | unchanged  | thickness only |

The hinge axis and the other two extents are identical before/after; only the thin axis is floored. No change to open motion numbers (offline).

Verified by `tests/test_leaf_clamp_offline.py` and the existing leaf tests in `tests/test_door_two_panels.py`.

No in-game claims. Real meshes not present in the repo (no game assets).
