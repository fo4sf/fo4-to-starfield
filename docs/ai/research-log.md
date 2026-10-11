# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: terrain experiment 2 staged
- Question: can the real Commonwealth terrain around Red Rocket be one native Starfield BTD at absolute positions,
  ready for the unattended runner, whichever BTD lookup experiment 1 finds?
  Write-up: [docs/terrain/experiment2.md](../terrain/experiment2.md).
- Method:
  - `src/fo4sf/terrain_grid.py`: grid rule, choice of n, separable bilinear resampling with edge clamping, and
    interpolation rules for check points.
  - `scripts/terrain/make_exp2.py`: reads the FO4 cells with the PR #56 `fo4land` module, writes the BTD with
    `btd.py`, then `plan.json` and `expected.json`.
  - `dotnet/TerrainExp2`: writes the plugin from experiment 1's template.
  - Survey of the LTEX quadrant maps of the 753 top-level vanilla BTDs (scratch).
  - Staged in `C:\Modding\staging\terrain_exp2`. Not deployed.
- Evidence (**verified** offline):
  - n = 29: Starfield cells -14..14, samples -1400..1499.22 m. That covers the PR #56 patch plus 300 m.
  - FO4 cells x/y -24..25 (2,500) read, so the whole BTD holds real heights.
  - BTD 27,612,888 B. Heights -114.46..140.67 m, header -116/142, step 3.937 mm.
  - Base texture `001235C2` LDirtFootprints01: the base of 2,334,675 quadrants in vanilla BTDs, and the only texture
    of TempJemisonWorld.
  - Plugin 36,742 B, checked with a raw walk:
    - WRLD `FO4CW_Commonwealth`, overlay `BNAM` pointing to SFBK `ANAM Data\TERRAIN\FO4CW_Commonwealth.btd`
      (record path and name both match), `DNAM` 29 x 29, `ENAM` -116/142;
    - `NAM0`/`NAM9` raw -1400/1500 m (Mutagen shows metres / 4096);
    - 841 cells;
    - COC cell `FO4CW_RedRocketSpawn` (-10, 11) with a marker at (-989.03, 1147.20, 107.14).
  - 14 check points at FO4 vertices (Red Rocket, flat, slope, both seam kinds, resampled). The decoded BTD returns
    every expected height within 3.221 mm under bilinear and both triangle splits.
  - Over all 4,225 patch vertices: median error 1.58 cm, p99 13.4 cm, max 1.42 m at a 75 deg cliff.
  - Rebuilds are byte-identical.
  - SFBK `FNAM[0]` = the BTD's SW corner raw height in 3 of 3 vanilla blocks.
- Status:
  - BTD, plugin and plan are **verified** offline.
  - H (BTD z = FO4 z / 70) and the grid rule remain **supported hypotheses** until experiment 1 or 2 runs in game.
  - **Unresolved**: `FNAM[1..7]`, whether `SmallWorld` or 841 empty cells matter, FO4's triangle split, and cliff
    accuracy at a 0.78 m grid.
  - Next (plan): an exterior exporter for the Red Rocket statics. Fo4Export is interior-only.
- Update (in game, 2026-10-11; `C:\Modding\testqueue\terrain_*`): this staging (loose BTD, no registration) cannot
  show the heights: loose files are not read on this install and a BTD only applies to an overlay activated on a
  planet (both **verified**, experiment 1). H is **refuted** in its absolute form (activation adds a whole-cell XY
  offset and a Z offset; vanilla LC172World -500 / -2300 m, Z -3.62 m); its relative form matched vanilla
  LC172World within 0.02 m. The successor exp2b (PR #64) read a flat -116.00 m (raw 0) at all 14 probes; the cause,
  a compressed BTD in the BA2, is a **supported hypothesis**, rerun pending. `FNAM[1..7]` is moot: FNAM is one value
  per BTD cell (PR #64).

## 2026-10-11 Claude: Starfield terrain architecture
- Question: how can native Starfield terrain carry the exact Commonwealth geography (S5 / WP-12)?
  Full write-up: [docs/terrain/architecture.md](../terrain/architecture.md).
- Method: raw record walk of both ESMs; new read-only SfInspect commands (`wrld`, `sfbk`, `planetworlds`, `wcells`,
  `form`); index-only listing of the terrain BA2s and a 44-byte header survey of all 2,112 `.btd`; BTD decoder after
  fo76utils (MIT) checked byte-for-byte on vanilla files; ref-vs-terrain fits; xEdit's Starfield definitions read for
  field names; FO4 `LAND.VHGT` decoded for all Commonwealth cells.
- Evidence: Starfield.esm has 0 `LAND` (Fallout4.esm 37,020). 430/433 WRLD point through an overlay component to an
  SFBK whose `ANAM` is `Data\TERRAIN\<EditorID>.btd`; 72 WRLD are registered by planets (`PNDT.MasterWorldspaces`,
  lat/long). BTD: 128 samples per 100 m cell, u16 heights linear in metres between a per-file min/max, LOD0-4,
  vanilla up to 100 x 100 cells. Commonwealth LAND: 192 x 192 cells, -118.86..641.03 m.
- Status: format, record chain and sizes **verified**; height scale in metres and grid alignment (BTD cell i = world
  cell i - n//2) **supported hypothesis** (pad at 111.4 m vs refs at 112-113.5 m; 130/133 NewAtlantis object cells inside
  the predicted footprint); whether a plugin worldspace with its own BTD loads, and whether it needs a planet entry,
  **unresolved** until experiment 1 (staged in `C:\Modding\staging\terrain_exp1`, not deployed). Recommendation:
  option A, a dedicated worldspace with a native BTD.

## 2026-10-11 Claude: FO4 terrain source patch
- Question: can we read absolute Fallout 4 terrain heights for a small patch, and prove them right, by reusing
  existing work before writing a LAND parser?
- Method:
  - Read fo76utils `fo4land` (MIT, commit `c52da18`) as the reference. It cannot be built here: there is no
    compiler or scons, and nothing was installed.
  - Wrote `src/fo4sf/fo4land.py`, which follows its VHGT algorithm, and `dotnet/Fo4Land`, a Mutagen-based second
    decode.
  - Extracted cells x -18..-17, y 18..19 of `Commonwealth` around the Red Rocket Truck Stop
    (REFR `000211C0`, `RedRExt_Workshop01`).
  - Details and commands: [docs/terrain/source-patch.md](../terrain/source-patch.md).
- Evidence (report.json; all **verified**):
  - Python vs Mutagen decode: max abs difference 0.0 over 4,356 vertices, and the same 1,315 refs.
  - All 1,315 temporary refs lie inside their XCLC cell (min margin 0.21 units).
  - Patch seams: max difference 0.0.
  - The Red Rocket floor z 7360 equals the terrain at its origin (residual 0). Over its footprint the max abs
    residual is 8 units.
  - 100 rocks, stumps, saplings and shrubs: z minus terrain median -7.4 units. Flipped or transposed grids give
    367-653.
  - Patch relief 1840 units, slope median 11.3 deg, max 76.5 deg.
  - Whole world: 36,864 cells. 649 of 73,344 neighbour seams (0.88%) do not match, the worst by 13,056 units in the
    far north-west (x -68..-62, y 76..77).
- Status: VHGT layout and orientation (row 0 = south, col 0 = west, height = 8 * (offset + accumulated gradient),
  origin = XCLC * 4096) are **verified** for Fallout4.esm.
  - The large maple trees sit 266 units deep. That they are planted deep on purpose is a **supported hypothesis**.
  - **Unresolved**: FO4's triangle split (bilinear vs either diagonal differs by up to 19 units at the refs),
    whether the big seams matter (are they in the playable area), and how any of this maps to Starfield terrain
    scale or format. 70 units/m is only the object scale.

## 2026-10-09 Claude: which FO4 collision bodies are movable?
- Question: how does an FO4 `bhkPhysicsSystem` mark a body as movable (pushable), so the converter can stop turning
  physics objects into fixed obstacles (Vault 114 door `05C7DC` is blocked by a ragdoll skeleton)?
- Method: compared `SkeletonClothed01.nif` (ragdoll) with `SubPlatformWall01.nif` (static) in the
  `hknpPhysicsSystemData` packfile, then scanned all 4,014 converted models (local script, not in the repo).
- Evidence: body cinfo +12 (u32) is a motion index: skeleton bodies 0..16 with 17 motion entries and 16 constraints
  (`hkpRagdollConstraintData`, `hkpLimitedHingeConstraintData`), layer 10; static wall `0x7FFFFFFF`, layer 1.
- Scan (motion index != 0x7FFFFFFF): 490 models / 5,340 placements with one moving body; 59 / 345 with several and no
  joints (cryo pods, roof hatches); 29 / 167 ragdolls with joints (skeletons, V111 gear-room gates, gurney).
- Status: "+12 = motion index, 0x7FFFFFFF = static": **supported hypothesis** (2 files). "Motion index means
  pushable": **refuted as stated**: placed Statics like `BldgShellWoodStairsRailing01` also have one, so it also covers
  keyframed / animated bodies. **Unresolved:** the motion entries' mass / motion type, which separates pushable
  (dynamic) from keyframed bodies.
- Follow-up (same day): system +32 holds motion *properties* (present only for dynamic bodies; values like 104.375 /
  31.57 / 0.1 / 0.05 identical in skeleton and pencil) and +48 the motion *cinfos*: u16 motion-properties id at +0,
  inverse mass f32 at +4. Skeleton: id 0, inverse mass 0.1 (10 kg); pencil: id 0, 2.0 (0.5 kg); stair railing and cryo
  pod: id 0xFFFF, inverse mass 0 (keyframed). Rule "dynamic = motion index != 0x7FFFFFFF, its cinfo id != 0xFFFF and
  inverse mass > 0": **supported hypothesis** (4 files, consistent across the scan). Rescan of 4,014 models: 373 single
  dynamic (4,642 placements: loose items), 22 multi-body without joints (156: breakable railings, gore), 29 ragdolls
  (167). Railings and cryo pods move to static, which is correct for them.

## 2026-10-09 Starfield `.af` animation header (door rigs)
- Question: what are the u16 fields at 0x28 of `open.af`?
- Method: compared four door families' `open.af` with their `characterassets\skeleton.rig` name tables
  (docs/spikes/WP-doors-research.md, "Header fields vs rig bone tables").
- Evidence: Akila 6 bones / field 6; generic 21/21; ship small 24/24; ship large 49/49.
- Status: field 2 = rig bone count: **verified** (4 of 4). Field 1 = format version: **supported hypothesis**.
  Field 3 = frame count: **supported hypothesis** (30 fps unconfirmed). Field 4: **unresolved**.

## 2026-10-09 FO4 precombine collision bodies with "shared vertex index out of range"
- Question: what primitive encoding do these `SCOL\CM*.NIF` bodies use?
- Evidence: 0 packed vertices, shared-index entries in triples (2130, start, x), primitives like (3,2,2,2);
  docs/JOURNAL.md "Precombine debris parts" and its correction.
- Status: **unresolved**. The "thin rods" reading was **refuted** (groups up to ~3 m in every axis).
