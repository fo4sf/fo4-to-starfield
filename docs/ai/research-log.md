# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: ground textures fix pass (QA review of PR #70)
- Question: the QA review found that the exp2t dirt spot was mislabelled, that every Commonwealth overlay run was at
  night, and that exp2t departed from every vanilla LTEX table in untested ways. Which of that holds, and what fixes
  it? Write-up: [docs/terrain/ground-textures.md](../terrain/ground-textures.md) sections 2.2, 5.1-5.3.
- Method: `ground_textures.py survey` (all BTD tables of the Starfield and add-on archives, BIOM `LNAM`/`ANAM`);
  `ground_textures.py lighting` over every earlier terrain queue (spawn sky, probe-shot corners); queue/obs files for
  save, start times and merge offsets; raw PNDT `CNAM` pairs of the staged Mars plugins; `Fallout4.exe` strings; VCLR
  over the footprint and the region of interest; decoded-BTD shares over each spot's view window and disk.
- Evidence:
  - **verified**: the old `ground_dirt` spot was one `LDirtPath01` vertex in mostly `LRootsEroded01` (two different
    Starfield targets); spots are now chosen per single target and must hold >= 90 % of the decoded view window and of
    a 6 m disk (all four do: 91-96 % / 95-100 %). `check` tests that window, not the nearest sample.
  - **verified**: 2,112 vanilla BTDs, 659 with an LTEX table, all 659 with the six `LDefault*` placeholders (11 index
    patterns); sizes 0: 1,453, 6: 256, 7: 341, 8: 37, 9: 20, 11: 1, 12: 1, 17: 1, 18: 2; largest gameplay table
    akilacity (11). 20 of the 24 textures of the full mapping (22 of the first 27) are in no vanilla table, 5 in no
    BIOM, `LGravelRoad01` and `LDebrisPile01` in neither. The earlier "a table may name any LTEX" is **corrected**.
  - **verified**: every Commonwealth overlay arrival (exp2b .. exp2c, 8 attempts) was at night (spawn sky 6.4-19.9 of
    255); the runner has no time-of-day control. From the same save (`fo4sf_test_2470f876`) the overlays registered at
    longitude 1.2 (exp1_mars, exp1d, exp3) arrived in daylight (103-131), exp2's at -1.2 never.
    **Supported**: local time follows the registration longitude. Fix: every new variant registers at exp1's site
    (0.2, 1.2); only the PNDT entry's 16 bytes changed (checked).
  - **downgraded**: "the exp2b 'Mars dirt' is `LDirtFootprints01`'s own albedo" (was supported) is now
    **unresolved**: the screenshots were lamp-lit at night. The control variant exp2t0 shows it in daylight.
  - **verified** (upgraded from supported): FO4's default land texture is `Ground\CommonwealthDefault01_d.dds`, the
    `Fallout4.exe` default of `sDefaultLandDiffuseTexture:Landscape` (bytes 46,682,039 / 46,682,072).
  - **verified**: VCLR over the 1,490 footprint cells is mean 0.996 / p5 0.992 of white (0.998 / 0.996 in the 175
    cells of the region of interest); alpha search on today's input 0.0306 / 99.04 % -> 0.0289 / 99.25 % (plain
    rounding vs search, reproducible with `--alpha-rounding plain`); the palette now reads `TilingDistance` (220 of
    416 materials; colours unchanged).
- Staged: five variants that change one thing at a time (t0 control, ta vanilla-shaped 11 entries, tb 11 entries with
  never-in-a-BTD LTEX, tc template + full mapping 31, t full mapping 24); all `check` PASS, all accepted by a dry
  `plan-terrain`. Not run in game.
- Status: offline findings **verified**; daylight at the new site **supported**; what the game draws **unresolved**.

## 2026-10-11 Claude: FO4 ground textures in the BTD (exp2t staged)
- Question: how do FO4 LAND texture layers and Starfield BTD texture sections work, and can the native Commonwealth
  terrain (exp2b2, heights verified in game) get Fallout 4's ground look? Write-up:
  [docs/terrain/ground-textures.md](../terrain/ground-textures.md).
- Method: FO4 `BTXT/ATXT/VTXT/VCLR` read for the 2,500 cells of the exp2 footprint (`fo4land` + new `landtex`);
  quadrant bytes and 3-bit alphas of five vanilla overlay BTDs, the BTDs of Shattered Space and the earlier 753-file
  LTEX survey; LTEX / BIOM / WRLD records of Starfield.esm and the 8 add-on plugins; terrain `.mat` files of the
  Creation Kit's ContentResources.zip; run-time `materialsbeta.cdb`; average albedo of every FO4 and Starfield land
  texture from low mips (new LZ4 block reader). Then `src/fo4sf/landtex.py`, `ground_map.py`, `texpreview.py`,
  `lz4block.py`, `scripts/terrain/ground_textures.py`, `tests/test_landtex.py`. Staged
  `C:\Modding\staging\terrain_exp2t`. Not deployed, not run in game.
- Evidence:
  - **verified**: FO4 field layouts (quadrant 0 = SW .. 3 = NE, 17 x 17 positions, row 0 = south); 1,701 of 10,000
    quadrants have no BTXT (default texture); VCLR is white (mean 0.998) around Red Rocket (0.996 over the whole
    footprint; see the fix-pass entry above).
  - **verified**: BTD quadrant = 8 bytes, bytes 0..4 slots with alpha group k, byte 6 base, bytes 5 / 7 and bit 15
    never set, textures in ascending table index; without byte 6 the last slot's alpha is 7 (100 % in four of five
    files, 99.97 % in newatlantis, 69-100 % in akilacity). Our decode -> encode reproduces five vanilla BTDs' effective
    weights exactly; every differing alpha is hidden below an opaque layer.
  - **verified**: vanilla BTDs paint with six `LDefault*` placeholders (+ `LDirtFootprints01`, BIOM's Path texture);
    no BIOM references the placeholders; Shattered Space's 108 BTDs use only them; no add-on plugin has an LTEX record.
    **Supported**: placeholders resolve to the planet biome's Solid/Talus/... texture; concrete LTEX render as
    themselves (akilacity uses both).
  - **supported**: blend reading (top slot over lower slots over base; fo76utils + the opaque bottom slot); FO4 default
    texture = CommonwealthDefault01 (fo76utils `-deftxt 0x000AB07E`; now **verified**, see above); the exp2b "Mars
    dirt" is `LDirtFootprints01`'s own reddish albedo (`#8F6C58`) (now **unresolved**: night shots, see above).
  - **verified** (offline): exp2t BTD heights byte-identical to exp2b2 (SHA-256 of header, cell min/max, LOD4 heights,
    every block's height half); 27-entry LTEX table; mean weight error 0.0289, dominant texture kept at 99.25 % of
    samples, 0.11 % weight dropped by the 6-texture limit; four ground spots decode to their mapped texture (at one
    sample only: the dirt and lot spots were wrong for the screenshot, see above); packed
    with Archive2 `-compression=None` the BTDs are stored and byte-identical.
- Status: format and writer **verified** offline; what the game draws (concrete LTEX on Mars, tint, blend model,
  option b: plugin terrain materials) **unresolved** until exp2t runs.

## 2026-10-11 Claude: overlay record fixes
- Question: in which records do our terrain experiment plugins differ from vanilla unique overlays, and what must
  SFBK `FNAM` hold? Write-up: [docs/terrain/overlay-records.md](../terrain/overlay-records.md).
- Method: raw walks of Starfield.esm (SFBK, WRLD, LCTN, PNDT, STAT) and per-cell statistics of the raw u16 heights of
  every decodable vanilla BTD with 1..30 cells (1,711 SFBK; scratch scripts, outputs not in the repo); vanilla overlay
  masks decoded with the new BC4 decoder. Then `src/fo4sf/overlay.py`, `scripts/terrain/overlay_records.py`,
  `dotnet/TerrainExp1` overlay mode, `dotnet/TerrainExp2` params, `make_exp2.py restage`, `tests/test_overlay.py`.
  Staged `C:\Modding\staging\terrain_exp1d` and `terrain_exp2b`. Not deployed, not run in game.
- Evidence:
  - **verified**: `FNAM` = `DNAM.x * DNAM.y` u16 in all 1,730 vanilla SFBK with an FNAM. **Supported (strong)**: value
    = raw height of each cell's south-west corner sample, cells from the south row: every cell exact in 1,464 of 1,711
    records, 94.6 % of all cells; min / max / mean / median / midrange / centre / north-first order: 0 records exact.
    lc172world 9/9, akilacity 89 % of cells, NewAtlantis 91 %, lc001world 4/25. Weaker for overlays (QA): 255 of
    430 overlay blocks and 29 of 72 registered ones exact.
  - **verified**: all 430 overlay WRLDs have `XLCN`; `LocTypeOverlay` on the location in 11 of the 72 registered
    ones (LC172World among them), city / settlement keywords on the rest. LC172WorldLocation: parent
    `SSol_PMars_Surface` 01B736.
  - **verified**: vanilla masks are DNAM cells x 100 px, legacy `BC4U`, one mip, in a General BA2; ours match the
    format. `INAM` 1 (Absolute) in 10 vanilla blocks, `HNAM` -239..0; 1,743 Relative.
  - **verified**: PNDT `CNAM` entry = f64 (Mutagen Longitude), f64 (Latitude), u32 WRLD; Mars 10 entries + ours.
  - **verified** (offline check, both folders PASS): FNAM 50 B / 1,682 B equal to the rule for every cell, XLCN ->
    LCTN (2CA99D, 01B736), INAM/HNAM 0/0 (exp1d) and 1/0 (exp2b), persistent XMarker anchor `01000800`
    (plan `02000800`), Mars entry, mask decodes exactly, plan points within one quantisation step.
- Status: records **verified** offline. Whether any of the four differences matters in game, the meaning of `HNAM`,
  the stale FNAM of 247 vanilla blocks, mask row order and the run-time load-order byte (02 assumed) are
  **unresolved**.
- Update (in game, 2026-10-11; `C:\Modding\testqueue\terrain_exp1d`, `terrain_exp2b`, `terrain_A2_lc172`):
  - activation and the whole-cell merge offset plus Z offset are now **verified** (LC172World -500 / -2300 m,
    Z -3.62 m; exp2b -1200 / -2700 m);
  - "the overlay mask is read only by procedural generation" is **refuted**: on vanilla LC172World the ground matched
    the BTD within 0.02 m where the mask is 0, 0.3-0.36 m next to it and 4-6 m off in mask-255 border cells, so the
    mask (or the outer ring) governs height blending;
  - our persistent anchors read back their unmerged local position (exp1d 50 50 10, exp2b -989.03 1147.20 105.14;
    **verified**), unlike vanilla's COC marker; load-order byte 02 held;
  - exp2b read -116.00 m (raw 0) at all 14 probes and exp1d -500.00 m (raw 0) at the arrival: flat, so the fixes are
    not tested yet. Cause, a compressed BTD in our BA2 (vanilla stores all 2,112), is a **supported hypothesis**;
    rerun with `-compression=None` pending.

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
