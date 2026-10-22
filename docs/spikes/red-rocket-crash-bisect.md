# Red Rocket crash bisect (v6, 2026-10-19)

Status: **cause found, fix in test**. The crash is Codsworth's converted model (meshes\fo4port\actors\codsworth\
codsworth.nif): every crashing thread was loading it, and v6i without it walks Red Rocket and back with no crash. Next:
find which part of the model the loader misreads (see "Codsworth's model").

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
| v6h (installed, crashes) | off | static | v6e's, with `--no-rig-pattern "redrped\|bldcounterdoor01\|safedoor01"` |

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

## v6h build (2026-10-21)
- Staged as D:\Modding\staging\terrain_core64v6h_l125_mission_wfc11 with the mission restaged against it
  (mission_wfc11_v6h); nothing is installed. The CHECK, l125 and fold steps passed, and compare-ids is identical to v6e.
  FO4TerrainCore is DC751664. **Verified** (PC report).
- `--resume` reconverted 62 meshes, not 3. `checkpoints.reusable_result` never reuses a result that has fallback
  materials or a `door_error`, so every resume retries those (16 with fallbacks this run, plus the doors with rig
  errors). With the same code and inputs, the retries should come out unchanged (**inference**; compare-ids agrees). A manifest check on the PC sorted all 62: 2 targets, 55 with fallback
  materials, 5 with door errors, 0 unexplained. **Verified.**

## The 0.02 in the door boxes
- `scripts/research/nif_float_scan.py` (#453) over the core's 11,768 NIFs finds 0x3ca3d70a in 6 of them. All 6 are door
  leaf boxes whose half-extent was clamped: `convert_static` gives a flat leaf (no depth on one axis) a box half-extent
  of `max(0.02, ...)`. **Verified.**
- Within 300 m of both crash sites (Red Rocket and the museum), only bldcounterdoor01 (the counter door 0232E0) holds
  it: block 9, a bhkPhysicsSystem, half-extent x. v6h removed that door's rig but kept the box. **Verified.**
- Door boxes with a real thickness never show up in a crash, and every crash reads exactly 0.02. So the thin, clamped
  box itself looks like the cause, not door boxes in general (**supported hypothesis**). A possible mechanism, not
  checked: a half-extent below the Havok box's convex radius leaves the shape inconsistent.
- Reading Card E: if v6h is stable, the counter or safe door rig was the cause and the box is cleared. If it crashes with
  rcx 0x3ca3d70a again, the rigs are cleared and the box is the lead. In that case, build v6i with the leaf floor raised
  (`sfcollision.MIN_LEAF_HALF`, 0.05) and rescan: 0 hits is the gate. That is a code change, so v6i reconverts all 11,887
  meshes. Staging it needs about 10 GB on D:, and D: is at 45.5 GB against its 40 GB floor, so it waits on the owner's
  cleanup list.

## v6h result (2026-10-21)
- v6h crashes about 16 s after the walk test's move to Red Rocket (17:22:04 local), within 2 s of arrival. The dump
  matches the others: Starfield.exe+0x2bf016b, rcx 0x3ca3d70a, r12 0x6666666666666600. Process commit was 12.79 GiB,
  the system had 3.78 GiB available and 45.53 of 61.16 GiB commit, and the 1 s memory log is flat through the load.
  **Verified** (PC report).
- So the counter and safe door rigs are cleared too, and no door rig near Red Rocket is left. The counter door's 0.02
  leaf box is still in v6h, so it remains the lead (**supported hypothesis**).

## Mission-off control (Card D, 2026-10-21)
- v6h with FO4SFMission.esm off crashes the same way, about 16 s after the move to Red Rocket (17:39:41 local).
  Starfield.exe+0x2bf016b, rcx 0x3ca3d70a, r12 0x6666666666666600; process commit 13.29 GiB, 3.99 GiB available.
  The plugin was confirmed off before launch and in the cycle's active line. **Verified** (PC report).
- So the mission script (and its MoveTo of Preston, the raiders and Codsworth) is ruled out.
- Side note: after the game exited, Plugins.txt had FO4SFMission.esm ticked again while the toggle still read off,
  so the runner or the game rewrote it on exit (unchecked which).

## v6i (next): the leaf floor alone
v6h with one change: flat door leaves get a 0.05 half-extent, not 0.02 (this PR's `sfcollision.MIN_LEAF_HALF`).
- Build it in wt_v6, not from main. main has moved a long way since 039a44e (2,600 lines in src/fo4sf), and a build
  from main would change more than one thing. In wt_v6's `src\fo4sf\convert_static.py`, replace `max(0.02, ` with
  `max(0.05, `: exactly 2 replacements, at lines 432 and 654, and nothing else.
- First break the work folder's hard links (see "Hard links" above).
- That edit changes `checkpoint_signature`, so `--resume` reconverts all 11,887 meshes (35 to 48 min) in place in
  work_v6c2. Run v6h's exact convert command, switches included.
- Gate: `nif_float_scan.py` over the v6i convert output finds 0x3ca3d70a in 0 NIFs. Any hit, stop.
- Stage `terrain_core64v6i_l125_mission_wfc11` as v6h was staged (CHECK, l125, compare-ids against v6h identical,
  mission restaged as mission_wfc11_v6i). This needs about 10 GB, and D: is at 45.5 GB against its 40 GB floor, so it
  waits for the owner's cleanup.
- Reading it, with the same walk: v6i stable means the thin box caused the crash, and this PR ships the fix. A crash
  with rcx 0x3ca3d70a and 0 scan hits would mean the 0.02 comes from somewhere else (not a NIF float); a crash with a
  different rcx would mean the game still misreads the box, now with 0.05.

## Hard links: the work folder writes through to staged builds (found 2026-10-21)
- `make_core64c.py stage` hard-links each staged core's Data tree to `work_v6c2\convert` (`link_tree`), and the
  converter wrote its files in place (`open(..., "wb")`, `shutil.copy2`). So v6h's `--resume` rewrote its 62 meshes inside
  every staged build that shares them: the v6c and v6e stagings, l125 included, now hold v6h's counter and safe doors.
  **Verified** (PC: fsutil shows one file across work and six staged folders). The installed tests are unaffected: they
  ran from archives packed at install time.
- Fix (this PR): `pipeline.write_staged` writes a new file and renames it over the old one, so a rewrite gets its own
  file and every other link keeps the old bytes. Every converter write into staging goes through it.
- The v6c and v6e stagings are no longer what they were checked as (`make_core64c.py verify-data` will say so). Both
  crash anyway, so they are retired, not repaired, and go on the owner's cleanup list. v6h's staging is the rollback.
- v6i is built in wt_v6, which does not have the fix, so break the links first: in `work_v6c2\convert`, give every file
  with more than one link its own copy. Copy it to a temporary name in the same folder, then move that copy over the
  original (a rename). Never copy onto the existing file: that writes through the link too. About 3.65 GB.

## v6i result (2026-10-22)
- v6i (the 0.05 leaf floor, `nif_float_scan.py` finds 0x3ca3d70a in 0 of its 11,768 collision NIFs) still crashes about 16
  s after the move to Red Rocket (19:34:40 local). The dump is the same: Starfield.exe+0x2bf016b, rcx 0x3ca3d70a, r12
  0x6666666666666600. Memory is flat (working set peak 9.88 GB, 3.52 GB free at the lowest). **Verified** (PC report).
- So the door-leaf boxes are cleared too: the 0.02 the loader reads comes from somewhere else. The floor change (#455)
  stays, as it is harmless. Only codsworth.nif's shader properties still hold the value among the NIFs, and Codsworth
  is in the mission plugin, which the mission-off run left out, so he is unlikely (**inference**).
- Places not yet scanned: the `.mesh` geometry files under geometries\, the plugins (FO4TerrainCore.esm, FO4Port.esm),
  and a value the game computes at run time, which no file scan finds.

## After v6i: name the file being read
- `minidump_read.py --strings 80` lists the text in the faulting thread's stack and around what its registers point
  at, paths first. A loader usually has the file name it is reading on its stack. This needs no build and no install.
- `scripts/game/value_scan.py` finds the value in any file: plugins record by record (type, form id, editor id, field),
  everything else as raw bytes. Run it over the plugins first (few hits expected), then over the `.mesh` files.
  Geometry is full of floats, so a `.mesh` hit only matters when the mesh is placed near both crash sites.

## Codsworth's model (2026-10-22)
- `minidump_read.py --strings` on the v6i dumps (and Card D's): the crashing thread holds
  `meshes\fo4port\actors\codsworth\codsworth.nif` on its stack and at [rsi] and [r14]. **Verified.**
- `value_scan.py` on the plugins: 4 hits, all REFR position or rotation floats (coincidence, **inference**). Only the
  mission plugin names Codsworth; no sTestFile line loads it. Why the model loaded in the mission-off run is open.
- The model's five BSLightingShaderProperty blocks are byte for byte the mini bot template's block (166 bytes, 0.02 at
  +144), except the name. **Verified** (PC dump of both files).
- So the 0.02 is vanilla data. That the loader reads that block (or what surrounds it) differently in our file is a
  **supported hypothesis**, not shown: the 0.02 may also come from somewhere else in the model. The switches below test it.
- v6i with the mission restaged without `--codsworth-assets` (Codsworth on the vanilla robot body, no codsworth.nif in
  any archive): Red Rocket to Sanctuary and back both PASS, about 9 minutes each, no access violation, memory flat.
  **Verified.** So the model alone causes the crash.
- Two switches on `convert_codsworth.py` split what is left. `--plain-shader` writes the shader blocks as the static
  converter does (the .mat name only, 12 bytes, as vanilla props have). `--one-material` puts every shape on one
  material, so the model keeps only the template's own geometry set, with no copied blocks. Test `--plain-shader`
  first: if it walks clean, it is the fix and Codsworth keeps his materials. If it still crashes, `--one-material`
  tests the copied geometry, shader and skin blocks.

v6c, v6e, v6h and v6i are tested in game (all crash at Red Rocket).
