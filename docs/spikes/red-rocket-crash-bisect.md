# Red Rocket crash bisect (v6, 2026-10-19)

Status: **in progress**. v6e (installed) still crashes at Red Rocket with the same fault; v6h is next.

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
| v6c (crashes) | on | movable | none |
| v6e (installed, crashes) | off | static | `--no-rig-pattern "redrped" --static-pattern "@D:\Modding\scratch\v6\movables.txt"` |
| v6f (dropped) | on | static | `--static-pattern "@D:\Modding\scratch\v6\movables.txt"` |
| v6g (dropped) | off | movable | `--no-rig-pattern "redrped"` |

How to read the results:
- v6e stable: build v6f. If v6f is stable too, the props caused it and the side door is safe. If v6f crashes, the
  side-door rig is a cause; build v6g to see whether the props are a second one.
- v6e still crashes: neither change alone is the cause. Next, the counter and safe doors: add their meshes to
  `--no-rig-pattern` and keep the v6e switches.

## v6e result (2026-10-21)
- v6e crashes 15 s after the walk test moves the player to Red Rocket. ProcDump caught it at 15:44:33 local (two dumps,
  identical). `scripts/game/minidump_read.py` (#451) gives: ACCESS_VIOLATION at **Starfield.exe+0x2bf016b** (game
  1.16.244.0), reading 0x19a87db9280, with **rcx 0x3ca3d70a** and **r12 0x6666666666666600**, the same as the three v6c
  dumps. **Verified.** The v6c dumps are gone, so the comparison uses the values recorded above.
- rcx 0x3ca3d70a is exactly the bit pattern of the float 0.02, so the game is handling a number where it expects a
  pointer or handle. That fits bad or mismatched record data more than low memory (**supported hypothesis**).
- Memory at the crash, from the dump (**verified**): the process at 12.78 GiB commit (peak 14.66), 9.77 GiB working set;
  the system at 3.51 GiB RAM available and 44.82 of 61.16 GiB commit, so 16 GiB of commit was still free. Physical RAM
  was low, which makes Windows page and can stutter the game, but an allocation only fails when commit runs out. The
  system's peak commit since boot is 75.23 GiB, above today's limit, so the page file grew at some earlier point
  (unchecked). Running out of memory does not fit this crash (**supported**); Card C's 1 s memory log around the Red
  Rocket move will confirm or rule it out.
- So neither change v6e made is the cause: the 448 movable props (static in v6e) and the RedRPedDoor side-door rigs (off
  in v6e) are both cleared, and v6f and v6g are dropped.

## v6h (next)
The bisect's own next step: v6e's switches plus no rig for the counter door 0232E0 and the safe door 1D1F0E.
- Their model names are in D:\Modding\scratch\v6\near_redrocket.jsonl (the rows for 0232E0 and 1D1F0E). Add each model's
  file name, without extension, to the v6e `--no-rig-pattern` value, joined with `|` (for example `redrped|name1|name2`).
- Build it cheaply, as below.
- Reading it: v6h stable means one of those two rigs is the cause (split them next). If v6h still crashes, no door rig
  near Red Rocket is left to blame; the next candidates are the remaining v5 to v6 differences near Red Rocket (the
  resdoor and roofhatch load doors and the truckdoor) and anything outside that 300 m list.

## Building v6h cheaply
`checkpoint_signature` (scripts/convert_batch.py) digests every `src/fo4sf/*.py` file and `convert_batch.py` itself, so
any code change makes the next run reconvert all 11,887 meshes (about 35 to 48 minutes). Since 039a44e (the commit v6e
was built from, worktree wt_v6 at 5a93beb), only `convert_batch.py`'s help text had changed on main when this was
written. So:
- Build v6h in wt_v6 **without** merging main. With `--resume`, only the two door meshes gain a `|no_rig` tag and
  reconvert; everything else is reused. Expect `reused` near 11,880.
- Building from main also works, but it reconverts everything. Use main at e079ac9 or later: between 5f2a065 and
  e079ac9 `--max-tris` defaulted to 20000, which skips every model over 20,000 triangles and drops its base record.

Steps (PC install thread; D: needs room for one more staged core, and keeps its 40 GB floor):
1. Copy work_v6c2's manifest and checkpoints aside as `work_v6c2_before_v6h` (rollback for the work dir; v6e's staged
   output stays untouched in D:\Modding\staging).
2. In wt_v6 (5a93beb), run the v6e convert_batch command with `--resume` into work_v6c2, with the two model names added
   to `--no-rig-pattern` as above and every other v6e switch kept.
3. Check: the manifest still has 0 entries with a `movable` key; RedRPedDoor and the two new doors have no `door.rig`
   of `native`; `reused` is all meshes but the two new ones.
4. Stage `terrain_core64v6h_l125_mission_wfc11` the same way as v6e: normal cluster, CHECK, l125, compare-ids against
   v6e (identical, or stop), fold and verify the wfc11 mission.
5. Superseded builds are listed for the owner's cleanup; nothing is deleted from here. The swap goes through the
   coordinator like v6e's.

v6c and v6e are tested in game (both crash at Red Rocket); v6h has not been built or tested yet.
