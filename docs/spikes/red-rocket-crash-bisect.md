# Red Rocket crash bisect (v6, 2026-10-19)

Status: **in progress**. v6e is built and staged, waiting for the owner's swap line and test.

## The crash
- v6c crashes near Red Rocket and at the museum, seconds after the fight ends or the mission completes. All three dumps
  have the same fault: ACCESS_VIOLATION reading at Starfield.exe+0x2bf016b (rcx 0x3ca3d70a, r12 0x6666666666666600).
  **Verified** from the dumps.
- Ruled out by the owner's in-game tests: map markers (both disabled, still crashed). Workshop stations are unlikely:
  v5 had the same 29 stations and walked past Red Rocket.
- `scripts/terrain/near_changes.py`, run v5 against v6c within 300 m of Red Rocket: 404 newly movable props (1,168 kg)
  and 12 door changes. The door changes are the 4 RedRPedDoor side-door rigs (05632F, 056332, 056333, 056334), the
  counter door 0232E0 and safe door 1D1F0E rigs, resdoor and roofhatch load doors, and the truckdoor door_error.
  **Verified** (output D:\Modding\scratch\v6\near_redrocket.jsonl on the PC).
- Suspect order: props physics first, then the side-door rigs, then the counter and safe doors. This order is a
  **supported hypothesis** and has not been tested in game.

## Builds
Every build uses the same core pipeline and the port `integ_v6_specmask_doors_c`; only the `convert_batch` switches
differ. `movables.txt` lists the 448 meshes that v6c made movable, one per line
(D:\Modding\scratch\v6\movables.txt, taken from v6c's manifest).

| Build | Side-door rig (RedRPedDoor) | Movable props | Switches added to the v6c command |
|---|---|---|---|
| v6c (installed) | on | movable | none |
| v6e (staged) | off | static | `--no-rig-pattern "redrped" --static-pattern "@D:\Modding\scratch\v6\movables.txt"` |
| v6f (planned) | on | static | `--static-pattern "@D:\Modding\scratch\v6\movables.txt"` |
| v6g (planned) | off | movable | `--no-rig-pattern "redrped"` |

How to read the results:
- v6e stable: build v6f. If v6f is stable too, the props caused it and the side door is safe. If v6f crashes, the
  side-door rig is a cause; build v6g to see whether the props are a second one.
- v6e still crashes: neither change alone is the cause. Next, the counter and safe doors: add their meshes to
  `--no-rig-pattern` and keep the v6e switches.

## Building v6f cheaply
`checkpoint_signature` (scripts/convert_batch.py) digests every `src/fo4sf/*.py` file and `convert_batch.py` itself, so
any code change makes the next run reconvert all 11,887 meshes (about 35 to 48 minutes). Since 039a44e (the commit v6e
was built from, worktree wt_v6 at 5a93beb), only `convert_batch.py`'s help text has changed on main. So:
- Build v6f in wt_v6 **without** merging main. With `--resume`, only the RedRPedDoor meshes lose their `|no_rig` tag
  and reconvert; everything else is reused. Expect `reused` near 11,880.
- Building v6f from main also works, but it reconverts everything. Use main at e079ac9 or later: between 5f2a065 and
  e079ac9 `--max-tris` defaulted to 20000, which skips every model over 20,000 triangles and drops its base record.

Steps (PC install thread; D: needs room for one more staged core, and keeps its 40 GB floor):
1. Copy work_v6c2's manifest and checkpoints aside as `work_v6c2_before_v6f` (rollback for the work dir; v6e's staged
   output stays untouched in D:\Modding\staging).
2. In wt_v6 (5a93beb), run the v6e convert_batch command with `--resume` into work_v6c2, minus `--no-rig-pattern`.
3. Check: the manifest still has 0 entries with a `movable` key; RedRPedDoor has `door.rig` = `native` and no
   `door_not_opening`; `reused` is all meshes but the RedRPedDoor ones.
4. Stage `terrain_core64v6f_l125_mission_wfc10` the same way as v6e: normal cluster, CHECK, l125, compare-ids against
   v6c (identical, or stop), fold and verify the wfc10 mission.
5. Delete superseded builds per the drive rule (keep installed plus one rollback). The swap needs the owner's own line.

Nothing here has been tested in game.
