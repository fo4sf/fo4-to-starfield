# Door-leaf clamp check (offline, #458 task 3)

v6i changed the door-leaf clamp from 0.02 to 0.05 (`MIN_LEAF_HALF`). Using synthetic leaves that match the thickness pattern of the named meshes in docs/spikes/red-rocket-crash-bisect.md (RedRPedDoor side doors, bldcounterdoor01, safedoor01), the hinge axis and extents after the clamp are:

| Mesh pattern | Original half (x,y,z) | After clamp (leaf floor 0.05) | Hinge axis preserved |
|--------------|------------------------|-------------------------------|----------------------|
| RedRPedDoor (thin leaf) | (0.02, 0.45, 1.2) | (0.05, 0.45, 1.2) | yes (rotation identity) |
| bldcounterdoor01 | (0.015, 0.6, 1.8) | (0.05, 0.6, 1.8) | yes |
| safedoor01 | (0.03, 0.4, 1.5) | (0.05, 0.4, 1.5) | yes |

All numbers from `sfcollision.box_blob` after the same `max(MIN_LEAF_HALF, half)` applied in `convert_static` for door leaves. No 0.02 pattern remains. Hinge axis is the first component in these axis-aligned synthetics; rotation is applied separately and unchanged by the half clamp.

Offline only. No game assets used.
