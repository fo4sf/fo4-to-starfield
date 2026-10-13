# Evidence journal

Newest last. Each entry: date, versions, what was done, the result, and where the evidence is.

## 2026-10-06: WP-00 recon (Fallout 4 1.10.163, Starfield 1.16.244)

**Done:** read-only scan of `Fallout4.esm` and `Starfield.esm` record trees, every BA2 name table in both games, and
sample NIF headers (`scripts/recon.py`, `scripts/recon_physics.py`). About 9 s runtime.

**Result:** see [FORMAT-GAP.md](FORMAT-GAP.md); raw data in [measurements/](measurements/).
Headlines: plugin form versions 131 vs 581; 116 of 137 record types shared but field overlap mostly
25â€“60%; no `LAND` or `SNDR` in Starfield; NIF BS 130 vs 175 with external `.mesh` geometry; Havok packfile vs
tagfile; `.bgsm` vs `.mat`/`.cdb`.

**Open questions it raised:** meaning of the `.mesh` header fields (S1); how Starfield custom worldspaces get
terrain (S5); whether Mutagen's Starfield alpha can write usable plugins (S2).

**Tooling gathered:** NifSkope (fo76utils) dev11 2025-12-30, xEdit 4.1.5f (includes `xSFEdit`),
PyNifly V29.1.0, Blender 5.2.2, .NET SDK 9, Starfield Creation Kit (Steam 2722710), SFSE 0.2.21 (manual from Nexus).

**Prior art search:** no public Fallout 4 â†’ Starfield conversion project was found on GitHub or the web.
Related open tooling is listed in the README.

**Source reading (no code run):** fo76utils/nifskope has `.mesh` readers (`src/io/MeshFile.cpp`), a meshlet
generator (`lib/meshlet.cpp`, spell *Generate Meshlets*), Havok spells (`src/spells/havok.cpp`) and the
full `nif.xml` with Starfield blocks; no `.mesh` writer was found. That is why S1 is the keystone spike.

## 2026-10-06: repo published

Public repo created. Pushing the CI workflow was rejected (token lacks the `workflow` scope), so it ships as `ci/github-actions-ci.yml` and is **not active**; the guard and tests were run locally (5 tests, guard ok, `um publish check` 21 files / 0 failures).

## 2026-10-07: S1 mesh writer (offline part)

Fallout 4 1.10.163, Starfield 1.16.244. Built `sfmesh`, `nif`, `sfnif`, `convert_static` and checked them against vanilla
files: 3,000/3,000 `.mesh` byte-identical round trips; meshlet rule verified on 4,000 meshes; NIF container 1,500 + 1,500;
`BSGeometry` 20,224/20,224; `MaterialID` hash found (CRC32, 60/60); tangent-sign mapping 98.8%. Converted the real FO4
`ChairPatio01.nif` (1,034 verts / 940 tris -> 12 meshlets, 0.91 x 0.83 x 1.04 m) and re-parsed the output successfully.
Details: [spikes/S1-mesh-writer.md](spikes/S1-mesh-writer.md). Corrected an earlier claim: base-game NIFs are BS 173, not 175.
Not done: NifSkope check (L1), in-game check (L2/L3), units (S4).
Environment: Creation Kit copied next to Starfield.exe; .NET 9 SDK installed; Blender still pending; SFSE 0.2.21 and the
Starfield Blender Extension 1.6.0 Beta 5 downloaded to `C:\Modding\tools`.

## 2026-10-07 (later): S2 / S4 / S9 offline results

Mutagen Starfield alpha writes a loadable-looking plugin (form version 576). Unit scale measured at ~70 units/m from
chair/stool/couch/barrel. Controlled Folder Access blocks writes to Documents, so loading uses a `- Main.ba2` built with the
official Archive2 instead of loose files + ini. Installed `FO4Port.esm` + `FO4Port - Main.ba2` into a Starfield test install
(reversible via `scripts/deploy_starfield.py`). **Next: launch the game and run the 5-step check in
[spikes/S2-S4-S9-plugin-units-loading.md](spikes/S2-S4-S9-plugin-units-loading.md).**

## 2026-10-07 (evening): first converted asset renders in Starfield

Launched Starfield 1.16.244 from Steam, loaded an existing save (backed up first to a folder outside the game), opened the
console and ran `player.placeatme 02000800`: the converted Fallout 4 patio chair appeared with correct orientation, size,
lighting and shadow. Plugin slot was 02. Lessons: (1) an early misreading of the console's "selected reference" label as our
FormID wasted two rounds; (2) Starfield ignores `SendInput` keyboard events but accepts `keybd_event`; (3) Windows Controlled
Folder Access blocks writes to Documents, so assets ship in `- Main.ba2`. Next: real materials (S3), collision (S6), then
a record translation framework (WP-08) and a bulk static converter.

## 2026-10-07 (night): S3 materials confirmed in game

Built `textures` (BC4/BC5 decode, DDS writers, texconv wrapper) and `convert_material` (BGSM parse, `.mat` cloning with fresh
object IDs). Archive2 `-includeFilters` ignored in practice (extracted 23 GB + 5 GB into scratch folders; deleted). Chair now
renders with its original texture in Starfield. Deploy script builds `FO4Port - Textures.ba2` (DDS format) as well. Note: first
console use after a launch shows an achievements warning; dismissed with E. See [spikes/S3-materials.md](spikes/S3-materials.md).

## 2026-10-07 (late): S6 box collision confirmed in game

Found a deterministic rule for patching a vanilla box-collision Havok blob (36 box-dependent float words, regressed over 369
vanilla blobs). Chair now has collision: two overlapping copies pushed each other apart and tipped; walking into them moved
them. Body is dynamic (inherited from the template). Lessons: the console achievements dialog needs a long E press and blocks
other input while open; `placeatme` spawns at the player's feet, so the player gets pushed out by the new collision.

## 2026-10-07 (play-test by the user)

Batch build (400 Set Dressing props) installed. Human play-test: shadows look good, props have collision, and they do **not**
move when pushed. Corrected the S6 note that called the bodies dynamic. Batch converter (`src/fo4sf/ba2.py`, `pipeline.py`,
`scripts/convert_batch.py`, manifest-driven plugin writer) committed with this entry: 400 converted in ~30 s, 6 skipped (no
static geometry), 146/151 materials full, 5 placeholder.

## 2026-10-08: Vault 111 first light

Exported `Vault111Cryo` with Mutagen (3,087 refs), converted its 268 models (234 ok), wrote a cell with 1,365 refs + 132 vanilla
lights and loaded it with `coc FO4Port_Vault111Cryo`: layout, scale and textures correct; over-exposed. Confirmed Starfield
placements are in metres. Lessons: Mutagen needs `WithKnownMasters` once Starfield.esm is a master; the achievements dialog
appears on the first console command of a session and steals keystrokes (close console, hold E, reopen); Shift must go through
the same legacy input path as the key. See [spikes/WP10-vault111-first-light.md](spikes/WP10-vault111-first-light.md).

## 2026-10-08: architecture collision (surface boxes)

Thin boxes behind flat surfaces, one body per box on child NiNodes; the player walks on the converted vault floor. Input guard
correctly refused to type when the user's window had focus.

## 2026-10-08: collision v2 (voxel boxes), effects excluded

See spikes/WP10-vault111-first-light.md. Automation lesson: chained keystrokes drift when a dialog or load intervenes; run console steps one at a time with a screenshot between them.


## 2026-10-08: Vault 111 in colour

Material tint strength (Color.w) was 1.0 and replaced every albedo; set to 0. Texture-set materials, effect-shape skipping, neutral fallback, bounded voxel size. See spikes/WP10-vault111-first-light.md.


## 2026-10-08: three interiors in one plugin

Vault 111, Vault 81, Red Rocket cave. Rock smoothness, alpha cutouts, blended overlays skipped, no collision on vegetation. See spikes/WP10-more-interiors.md.


## 2026-10-08: collision maps + glass

Probe maps (teleport + OCR height readback, `scripts/game/probe.ps1`): Vault 81 28 PASS / 2 HELD; Vault 111 17 PASS / 2 HELD / 6
small drops onto lower stair steps (0.6-1.6 m, now classed `LOWER`); Red Rocket cave 8 PASS / 10 HELD (platform and ramp tops
above their origin) / 1 MOVED / 1 unread. **No fall-through anywhere.**
Glass: FO4 effect-shader glass (textures inline in `BSEffectShaderProperty`, or a `.bgem`) is converted by cloning the vanilla
glass material `OPMineMaskBox01Glass.mat` (shader model `1LayerEffectGlassNoFrost`), opacity 0.15, smooth roughness. Vault 111
glass panes and cryo-pod windows convert. Vanilla shader-model survey: `1LayerStandardDecal` (1,133 mats) is the next target for
FO4 alpha-blended overlays/decals (Parsons wallpaper cracks, vault greebles).
In game (Vault 111): the cryo-pod window is see-through to the seat inside ([screenshot](media/vault111-cryopod-glass.jpg)); whether the glass surface itself is drawn (reflection/tint) is not yet confirmed at this distance. 2,551 models, 1,013 materials incl. 12 glass.


## 2026-10-08: interior lighting

Every converted interior looked washed out and pink. The cause was cells with no ImageSpace and no EnvironmentMap: auto-exposure
metered against a bright default sky reflection. The plugin writer now sets both, following vanilla `DR017UndergroundInterior`:
ImageSpace `LGT_LUT_Int_Gen_v01_curve` 122393, EnvironmentMap `Data\Textures\cubemaps\blackcube.dds`. The FO4 lights become
`LGT_ShipInterior_Omni_NS_Neutral_2k` (03D38C) omnis, merged within 2-3 m.

That fixed the wash and the tint but made big rooms very dark. Changing the lighting template to `ShipInteriorLT` (006658)
fixed Parsons, the Prydwen and Vault 114 ([before](media/lighting-parsons-before.jpg) / [after](media/lighting-parsons-after.jpg),
[Vault 114](media/lighting-vault114.jpg)). The same template over-lit Vault 111, which keeps the darker `KreetBase01LGTtemplate`.
Settings are now per cell through `<staging>/lighting.json` ([example](lighting.example.json)). Lookup order is cell, `"*"`,
environment variable, built-in default.
`SfInspect imgs` lists vanilla image spaces by how many cells use them. `LGT_LUT_Int_Gen_v00_curve` gave a green cast and was
rejected.
Open: Vault 111 metal still reads as chrome (likely FO4 spec/gloss -> roughness or metalness, to check next). The tour script
can walk off the edge of a cell into the void.

## 2026-10-08: every material was fully metallic

The "chrome" look on all converted surfaces (and part of the "weird textures" report) came from the template material
`MetalIronCast01.mat`. Its texture set enables a constant metalness of 1.0 (`BSMaterial::TextureReplacement` index 4).
`build_mat` only rewrote the `Summary` block, which is informational: the engine reads the component. `build_mat` now writes the
metalness value into the component (slot map: 0 albedo, 1 normal, 2 opacity, 3 roughness, 4 metalness, 5 AO), with a test.
1,002 staged materials were patched in place. The script is `C:\Modding\research\s3\zero_metal.py`; a full reconversion gives
the same result.
Vault 111 [before](media/metal-v111-before.jpg) / [after](media/metal-v111-after.jpg), [tour frame](media/metal-v111-tour.jpg):
cream walls, blue pipes and orange fittings now read like Fallout 4. [Hotel Rexford](media/rexford-lit.jpg) is readable but
greyer than the warm original (next: image-space LUT / colour check).

## 2026-10-08: doors (experimental, off by default)

Hinged FO4 doors can be rebuilt on the vanilla Akila door rig. In game they sit in their frames, show "DOOR / Open (E)",
toggle Open/Close and block the player, but the leaf does not swing yet. Because a door that blocks the doorway is worse than a
walk-through one, rigging is off by default (`Converter(rig_doors=True)` to test). Details, clues and next steps are in
[WP-doors-research](spikes/WP-doors-research.md). New: `nif.door_hinge` / `descendants`, `sfnif.build_door_nif`,
`convert_static.convert_door`, DOOR records in the plugin writer (with origin offset and bounds), `tests/test_doors.py`,
`SfInspect doorprops`.

## 2026-10-08: doors, attempt 2

A vanilla Starfield door swings inside our converted cell, so the remaining problem is our door NIF or record.
`sfcollision.keyframed()` turns the leaf's static box into a vanilla-style keyframed body. With it the doorway is passable
again and the leaf rests in FO4's rest pose, but I could not aim scripted input at it to confirm a swing. Next: a
one-door test cell with a fixed spawn. Rigging stays off by default; the deployed build has walk-through static doors.

## 2026-10-08: doors open

FO4 hinged doors now open and close in Starfield (24 door models in our 8 cells). The missing piece was the leaf's
collision body: it must be keyframed like a vanilla door leaf, not static. Verified in a one-door test cell and in Hotel
Rexford: closed at rest, swings on E, walk through ([screenshot](media/door-rexford-opens.jpg)). Enable it with
`convert_batch.py --starfield-data`. Next for doors: sounds, frame collision, and a sliding template for vault doors.

## 2026-10-08: alpha-blended overlays become decals

FO4 materials with alpha blending (sign lettering, wall cracks, grime and greeble overlays) were skipped. They now convert
to Starfield decal materials. The diffuse alpha becomes the opacity map, and the `.mat` is cloned from the vanilla decal
`AKDecalPrintedTechWall01.mat` (shader model `1LayerStandardDecal`; `cm.DECAL_TEMPLATE_MAT`,
`Converter.decal_material`). Re-converted 222 models with blended shapes (141 new materials, 0 failures, 84 s).
In game, the Vault 81 wall placards now show their lettering, "OVERSEER / COMMISSARY"
([screenshot](media/decal-vault81-placard.jpg)). It reads dimmer than in FO4, probably because FO4 sign letters use glow
or emissive maps, which are not converted yet.
Seen on the way: FO4 double doors (`PaintedWoodDoorDouble01`, Parsons) rest with their moving leaf open
([comparison](media/decal-parsons-cmp.jpg)). Their FO4 rest pose is not the closed pose. Next door fix: take the leaf pose
from the end of the FO4 `Close` sequence.

## 2026-10-08: door rotation fix (offline; not yet verified in game)

The foreground guard tripped (another app was in front and Starfield was not running), so this tick was offline only.
- The Parsons double doors, which looked like they rested open, are not a rest-pose problem. New
  `nif.door_closed_rotation` reads the end of the FO4 `Close` sequence (Euler or quaternion keys, tested), and for every
  door checked the closed pose equals the rest pose.
- The real suspect is the reference-rotation direction used to shift door origins. Bethesda angles turn clockwise, and the
  plugin writer rotated counter-clockwise. Doors at 0 and 180 degrees (all the Rexford tests) are the same either way.
  Parsons' 135, 225 and 315 degree doors get shifted to the wrong spot.
- `RotateOffset` now uses the clockwise convention. Built in staging only and not deployed. Next in-game check: the Parsons
  double doors sit closed in their frames.

## 2026-10-08: four more interiors converted (offline; tours pending)

The guard tripped again (another app in front), so this was offline only. Exported and converted four more FO4 interiors:
Valentine's Detective Agency (`DmndValentines01`), `SuperDuperMart01`, `Vault95` and `CambridgePolymerLabs01`. Twelve cells
in total.
- Full batch over the 12 cells (with doors and decals on): 3,389 models converted, 18 failed, 408 s.
- Almost all failures are glass-only lab props (beakers, test tubes, chemistry set). Their effect textures are not named
  "glass", so they are skipped; next material fix.
- Plugin: 3,359 statics and 30 doors. New cells: Valentine's 268 refs / 8 lights, Super Duper Mart 4,185 / 113,
  Vault 95 4,353 / 172, Cambridge Polymer 3,206 / 165.
- Staged in `C:\Modding\staging\multi` but not deployed. In-game tours and the Parsons door-rotation check run when the PC
  is free.

## 2026-10-08: more glass (offline)

The guard tripped again, so this tick was offline. FO4 lab and household glass (beakers, test tubes, bottles) uses an
environment-mapped effect shader with its own normal map, and the base texture is not named "glass". Those shapes were
skipped. Glass detection now also accepts effect shaders with a cubemap and a normal map (never textures from the effects
folder).
- Glass materials: 12 -> 33. All are real glass: chemistry set, beakers, test tubes, Nuka bottle, watch and magnifier
  glass, jukebox front, water-cooler jug, light covers, vertibird canopy.
- Batch failures: 18 -> 10. Left: wall-stain gradient effects, a strobe flash, an oil puddle, and two plates without static
  geometry.
- Staged and not deployed yet.

## 2026-10-08: four new interiors toured; static collections; door rotation verified

There had been no user input for 18 minutes, so I ran the in-game checks. The guard still checks before every keystroke.
- **Door rotation fix verified.** The Parsons double doors (135 and 225 degrees) now sit closed in their frames
  ([screenshot](media/parsons-doubledoors-closed.jpg)). Bethesda reference rotations are clockwise.
- **Tours of the four new cells:**
  - [Valentine's](media/tour-valentines.jpg): office, beams, peeling posters as decals.
  - [Super Duper Mart](media/tour-superdupermart.jpg): Nuka-Cherry sign, posters, carts, Protectron pod. The sales floor
    is very dark.
  - [Vault 95](media/tour-vault95.jpg): reads like FO4.
- **Cambridge Polymer Labs: the player fell through the floor at the spawn.** The floor there is inside a FO4
  `StaticCollection` (SCOL, merged mesh `meshes\SCOL\Fallout4.esm\CM*.nif`), and SCOLs were never in the batch's
  `--types`. The 12 cells hold 245 SCOL references (93 meshes), all missing until now.
  - Fix: `StaticCollection` is now a default type, and `meshes\scol\` gets the architecture surface collision.
  - All SCOL meshes convert (3,490 models in total).
  - Cambridge now spawns and stays on the floor (OCR z 3.87, stable after 6 s), and the atrium renders
    ([screenshot](media/cambridge-atrium.jpg)).
  - Earlier cells may also have had gaps from missing SCOLs; worth a re-probe.

## 2026-10-08: FO4's own collision transplanted into Starfield (built; in-game check pending)

The user's report: collision, doors, stairs, "everything". The root cause is that every converted body was an axis-aligned box
guessed from the render mesh, so stairs, ramps and angled surfaces could not be represented. New approach: use the collision
Bethesda authored for FO4.
- `hkpackfile.py` reads FO4's Havok 2014 packfiles and `fo4collision.py` decodes their shapes (compressed meshes, convex
  polytopes, body transforms). Verified: the decoded PryCatwalkStairs01 mesh matches the render bounds exactly, and its
  stair is a 40-degree ramp.
- `hktagfile.py` reads Starfield's Havok 2019 tagfiles, with type layouts taken from the file's own TYPE section.
  Finding: Starfield's `hknpCompressedMeshShapeTree` has the same layout as FO4's (sections, primitives, packed/shared
  vertices, compressed AABB trees). Only a few section fields are packed differently.
- `meshcollision.transplant` rebuilds a Starfield tagfile around FO4's mesh data. A vanilla Starfield static from the
  user's install is the container; the optional SIMD tree is off.
- 1,960 of 3,490 models now carry FO4's exact collision mesh (0 errors). 317 still use oriented/axis boxes (collision not on
  the root or a moved body), and 1,213 props keep a single box or none.
- Oriented-box tools were also added (`sfcollision.oriented_surface_boxes`, `convex_obb`). They are not used by default.

In game: **not verified.** The first launch with this build ended with Starfield gone twice, with no crash log. It may be
a startup crash caused by the new collision, or the user closing it. The mod was uninstalled so the user's game starts
clean. Also: `cycle.ps1` closed the user's own open Starfield session (sitting in the character menu). It now refuses to
close a game it did not launch (PID file).
Next: confirm whether the transplanted collision crashes the game, using a test cell holding one transplanted model.

## 2026-10-08: transplant fixed against vanilla Starfield (offline)

The user was active, so this was offline only. Compared the transplant with 246 vanilla Starfield mesh shapes:
- `numShapeKeyBits` equals the tree's `bitsPerKey` in vanilla (224 of 246; the other 22 not yet examined); the transplant
  had kept the template's 2 (the stair needs 10), a likely cause of the suspected crash.
- `numTriangles` is 0 in vanilla, and the interior bit field holds `maxKeyValue + 1` bits.
- Every vanilla mesh has a SIMD tree. It is now generated (`build_simd_tree`): a 4-wide AABB tree whose leaves are
  triangle shape keys `section << 8 | primitive << 1 | quad half`. That formula reproduces FO4's `maxKeyValue` exactly.
- New `decode_sf_mesh` reads a Starfield blob back. Round trip on the Prydwen stair: 756 / 756 triangles, max vertex
  difference 0.0 m. New tests cover the section mapping, the SIMD tree and the varints.
Reconverted and staged; not deployed. Next: in-game check (startup, a single transplanted model in the test cell, then
stairs and doorways).

## 2026-10-08: native FO4 collision verified in game (Prydwen stairs)

First in-game run of the native collision build (the user freed the PC). The game starts, the Prydwen loads, and the
player stands on native floors.
- **Stair climb (2 flights, PryCatwalkStairs01 + PryCatwalkStairsEnt01):** OCR positions go from z -10.97 at the bottom
  to z -7.31 on the upper deck (3.66 m), then along the deck to y 42.3, where the player is stopped by a crate stack (solid,
  as in FO4). ([stairs](media/prydwen-stairs-native.jpg), [deck](media/prydwen-upper-deck-crates.jpg))
- **What it took** (each found from a failed climb):
  1. Several FO4 collision objects can share one physics system. Each owns one body, given by the body index stored in
     the object, so each object now gets only its own body.
  2. FO4 shapes live in the space of the object's node. The body cinfo transform is not a placement (a vault crate's
     shape already matches its render mesh but carries a 0.29 m body offset). So bodies go on child nodes with the FO4
     node transform, and the Starfield body is identity, as in vanilla.
  3. Collision layers are kept. FO4 and Starfield share layer indices except 37 and 43, which are rejected explicitly.
     The stair's `C_Ramp` body is `L_STAIRHELPER` (31); copied as static, it acted as a wall at the foot of the stairs.
  4. The template is Bethesda's own multi-shape test file (`test_fbx_collision_same_node01.nif`), whose type table covers
     every shape.
- Coverage across 3,490 models: 2,648 native, 154 boxes, 688 single box or none. Recorded fallbacks:
  hknpDynamicCompoundShape 266 (Codex's compounds work), hull topology 60, sphere 9, and an IndexError in 44 (to fix).
- **Doorway (Hotel Rexford door 10AD60) with the native build:** closed at rest, opens on E, and the player walks through
  into the bathroom (OCR x 46.90; the door is at 44.32). ([sheet](media/rexford-door-native.jpg))

## 2026-10-08: route runner (owner issues #29, #30)

A movement test that FO4 data scores, replacing "press W, read once".
- `scripts/game/routes.py` builds routes per cell from FO4's own collision. Stairs use the `L_STAIRHELPER` ramp body, or
  the 20-50 degree collision triangles if there is none: start 0.8 m before the low end, face the high end, expect a rise.
  Doors start 1.6 m in front, press E, and must end 1 m past the door plane.
- `route_run.ps1` walks each route (guarded input, OCR position, screenshot). `route_eval.py` scores PASS / STUCK / FALL /
  BLOCKED / UNREAD and rejects impossible OCR reads.
- Lessons from the first runs, all bugs in the test rather than the port:
  - a long walk crosses mirrored flights (up one, down the other), so walk time is sized to the run at running speed
    (~4.6 m/s);
  - OCR can drop a minus sign or shift columns;
  - the repo's `readpos` needs the numpy venv (`FO4SF_PYTHON`).
- **Prydwen, first 12 stair routes (PryCatwalkStairs01 x10 at 90/180/270 degrees, PryCatwalkStairsEnt01):** 9 PASS (each
  climbs 1.87 m to the landing; the 180-degree flight 2.6 m). 2 UNREAD (OCR misreads x around +0.5, the same end point as
  the passes). 1 harness flake (the console reply was not printed before the screenshot); rerun needed. No STUCK and no
  FALL attributable to collision. ([foot](media/route-prydwen-stair-foot.jpg), [top](media/route-prydwen-stair-top.jpg))
- Collision decoder: degenerate primitives and invalid shared indices are skipped or rejected (the merged-SCOL IndexErrors).

## 2026-10-08: routes for the whole slice (offline)

The user was in the game, so this tick was offline. Reconverted with the decoder fixes: 2,716 native, 137 boxes, 637 single
box or none. 7 merged SCOL meshes carry junk shared-vertex tables and are rejected (recorded), not decoded. Routes built
for 11 cells: about 279 (127 stairs, 102 doors). Red Rocket has none; it is checked with the probe map instead. Stairs
whose FO4 collision has no ramp are listed per model for a separate check: Vault 111 `V111RPit2StairsRaisedMid02` x4,
Rexford `BldWoodBSmStairs03TrimL/R`, Vault 114 `VltStairWellCorIn01`/`VltStairWellDoorHalf01`, Cambridge
`BldWoodPSmStairs02TrimL`. Staged, not deployed; the in-game runs follow when the PC is free.

## 2026-10-08: Vault 111 routes

Ran all 11 Vault 111 routes on the current native build: **8 PASS**, 1 UNREAD (OCR column swap), **2 STUCK**.
- PASS: the pit stairs (`V111RPit2StairsRaisedMid01`, rise ~1.0 m, five copies), the wall stairs (`V111RPitWallStairs01`,
  two), and the door `SwitchDoorExSmLatch01` (opens, player 1.41 m past the plane).
  ([pit stairs](media/route-v111-pit-stairs.jpg), [door](media/route-v111-door.jpg))
- STUCK: both `V111HallStairs01`, rise 0.26 m of 1.55 m ([stuck](media/route-v111-hallstairs-stuck.jpg)). Its FO4 stair
  helper is placed correctly (unrotated `rampdummy` node), but it is about 46 degrees: rise 1.93 m over 1.85 m. The
  passing Prydwen helpers are about 31 degrees. Likely Starfield's character controller does not walk slopes that steep,
  where FO4's did.
- Experiment queued (not run; the user came back): rebuild without the helper (`FO4PORT_DROP_STAIRHELPER=1`, diagnostic
  only) and check whether the 0.30 m treads can be stepped. If not, flatten steep helpers to a walkable angle.
  **The installed build currently has that diagnostic version of V111HallStairs01.**

## 2026-10-08: compound, capsule and sphere collision (offline)

The user had been active within 10 minutes, so this tick was offline.
- **Compounds:** `hknpDynamicCompoundShape` bodies are flattened. Each instance becomes its own native Starfield body, with
  the instance transform baked into the shape: convex children fully, mesh children translation only (a rotated mesh
  instance is rejected and recorded). Instance layout from Codex's `fo4_compounds.py`, which is cross-checked against
  PyNifly and real FO4 files.
- **Capsules:** FO4 capsules carry a full polytope hull plus radius, so they take the convex path.
- **Spheres:** native `hknpSphereShape` from Bethesda's test-file template (one centre vertex, radius as convex radius).
- Coverage: **3,006 of 3,490 models native** (up from 2,716), 117 boxes, 367 single box or none. Recorded errors: 9
  open hulls, 16 junk shared-vertex tables, 2 `hknpConvexShape`.
- **Not yet verified in game.** Next with a free PC: startup, then a prop-heavy room (compounds are mostly props), then the
  Vault 111 hall-stair experiment.

## 2026-10-08: steep FO4 stair helpers flattened; Vault 111 hall stairs climb

In game: the compound / capsule / sphere build starts and loads Vault 111.
- `V111HallStairs01` without its helper is still stuck: the 0.30 m treads are too tall for Starfield's step-up.
- Fix: `meshcollision._flatten_helper`. An `L_STAIRHELPER` hull steeper than 40 degrees (measured in its collision
  node's orientation) is stretched: its whole bottom edge moves by one vector along the ramp, so the top stays where FO4
  put it, the width is unchanged and the slab stays planar. Planes are recomputed from the faces. This helper went from
  44.7 to 38.9 degrees. Starfield's controller stops at roughly 45 degrees; FO4 allowed steeper.
- **Both hall staircases now PASS** (rise 1.94 / 1.95 m) ([screenshot](media/route-v111-hallstairs-pass.jpg)). Vault 111 is
  10 of 11 routes passing; the 11th was an OCR misread.
- New tests: slope limit reached, top and width kept, gentle helpers untouched, plane orientation. Also: `route_eval`
  reads BOM-prefixed route files.

## 2026-10-08: Vault 81 routes; door routes from the leaf

Deployed the full build with stair-helper flattening and ran Vault 81's 16 routes.
- **Stairs: 11 of 11 readable PASS** (2 more UNREAD from OCR). Hall stairs `VltHallResStairs01` / `VltHallUtilStairs01`
  rise 1.83 m; catwalk flights `VltCatwalkStairsFront01` / `...FrontBottom01` rise 1.6-2.8 m.
  ([catwalk](media/route-v81-catwalk-stairs.jpg), [hall](media/route-v81-hall-stairs.jpg))
- **Doors: the three cave stall doors (`BRStallDoor01`) failed because the route was wrong**, not the door: routes assumed
  every door faces along local +x (true for the Rexford wooden doors), and these face along y, so the runner started
  inside rock. Door routes now take the facing from the **closed leaf** (the moving branch's bounds; the leaf spans the
  opening, so its thinnest horizontal axis is the normal), cross the middle of the opening, and run once from each side
  (a leaf may swing towards the player). The verified Rexford door still gets its proven route (x 42.75, heading 90).
- The rerun of the 6 Vault 81 door routes is pending (the user was back).

## 2026-10-08: broken FO4 hull topology rebuilt (offline)

The user had been active within 5 minutes, so this tick was offline. Some FO4 convex hulls have faces that don't close
(an edge without its opposite), so they fell back to boxes. `meshcollision.convex_hull_faces` rebuilds the faces from the
same vertices (convex hull, coplanar points merged into one polygon, wound counter-clockwise from outside as in vanilla
Starfield hulls), then planes and links are recomputed. Test: a cube plus an interior point gives 6 closed outward quads.
Coverage 3,012 native (+6). Left: 3 hulls that are probably flat, 16 merged SCOL meshes with the same junk shared-vertex
index (2130), and 2 `hknpConvexShape` bodies. Staged only; not yet in game.

## 2026-10-09: overnight routes: Vault 81 doors, Vault 114 (partial)

- **Vault 81 stall doors** (corrected door routes: facing from the closed leaf, both sides): 1 of 3 doors passes from both
  sides (1.25 m / 2.95 m through); the other two are BLOCKED from both sides (-0.4 to -0.6 m, i.e. stopped at the door).
  ([pass](media/route-v81-stalldoor-pass.jpg))
- **Vault 114** (24 of 47 routes ran before the user came back; run stopped):
  - Stairs: 7 PASS (subway hall stairs, subway platform, cinder block, stairwell; rise 0.9-5 m)
    ([subway stairs](media/route-v114-subway-stairs.jpg)).
  - 2 STUCK: `IndCatStairsFull01` (rise 0.08) and `VltGearDoorStairs01` (1.41 of 3.22)
    ([stuck](media/route-v114-catwalk-stuck.jpg)).
  - 5 UNREAD (OCR). One "PASS" with an implausible 31 m rise must be treated as unread: the plausibility check has to cover
    the scored rise too.
  - Doors: stall doors and `SubDoor01Right` BLOCKED from both sides ([blocked](media/route-v114-stalldoor-blocked.jpg)).
- Next: why these doors block, from the converted files (leaf swing, frame collision covering the opening), and the
  two stuck staircases.
- Correction: with the rise plausibility check, the Vault 114 "PASS" with a 31 m rise is UNREAD. Vault 114 stairs are
  **6 PASS**, 2 STUCK, 6 UNREAD. Route runner now saves `r<k>_pre.png` (just before E, shows whether the Open prompt is up)
  and `r<k>_open.png` (2.2 s after E) for every door route.

## 2026-10-09: no collision where FO4 has none; Vault 114 doors

- **Invisible walls removed.** 284 converted models have no collision at all in FO4 (rubble, debris, paper, signs,
  posters, plants, ponds, some vault trim). The converter still gave them a guessed bounding box, or surface boxes for
  architecture, which made walk-through clutter into invisible walls. Now they get none, as in FO4
  (`report.source = "fo4-none"`, 243 models in the current batch). Coverage: 3,012 native, 243 none as in FO4, 199
  single box, 36 surface boxes.
- **Found by the door test:** a stall door was blocked by the guessed box of a rubble pile in front of it. After the fix,
  stall door `04BDD2` passes from both sides (2.6 m through). Door results in Vault 114: subway door `SubDoor01Right`
  passes from both sides; stall doors `04BDDA` and `04BDD2` pass from both sides.
- **Evidence screenshots** (runner now steps in before pressing E, and looks straight ahead on doors): the passing doors
  show "DOOR / Open" ([prompt](media/route-v114-stalldoor-prompt.jpg)). Two stall doors placed at 90 degrees
  (`04BF66`, `04BF9D`) stop 0.45 m short from both sides with no prompt; the door's lower edge is at eye height
  ([raised](media/route-v114-stalldoor-raised.jpg)), so these instances seem to sit ~1.3 m too high. Their 270-degree
  twins are fine; suspect the door origin offset vs this placement. Open.
- One game exit without a crash record during a door route (the rerun of the same route was fine): watching for repeats.
- Correction: the "door raised ~1.3 m" reading for stall doors `04BF66` / `04BF9D` is unconfirmed. Follow-up views with pitch 0 looked steeply at the floor, so camera pitch from `setangle x` is not reliable enough to judge door height from one screenshot. These two doors stay open as BLOCKED, cause unknown.

## 2026-10-09: doors are fine, the test runner wasn't (Hotel Rexford 21/26)

Most door "BLOCKED" results today were runner bugs:
1. **Camera pitch.** `player.setangle x` turns the actor, but the first-person camera keeps its own mouse-look pitch.
   After some routes it was left looking at the floor, so E never reached the door; the "door raised 1.3 m" impression
   came from that too. The runner now levels the camera before every route (mouse fully up, which clamps, then down 700
   counts, calibrated in game).
2. **Console desync.** On a failed read the runner pressed the console key "in case it was open". If it was closed, the
   next route's typing went to the game ("p" opened Skills). Removed; `readpos` always leaves the console closed.
3. A brief `setangle x 0` for door routes made it worse; reverted to `x 10`.

With those fixed, **Hotel Rexford doors: 21 PASS / 4 BLOCKED / 1 UNREAD.** Every one of the 13 doors lets the player
through from at least one side ([prompt](media/route-rexford-door-prompt.jpg), [open](media/route-rexford-door-open.jpg)).
The 4 one-sided blocks (refrigerator, `UtilMetalDoor01`, `BldWoodPDoor02`, the entrance load door) are probably the side
the leaf swings towards. To confirm with the open-screenshot, then rerun all earlier door verdicts (Vault 81, Vault
114) with the fixed runner.
Rexford stairs (same session): 8 PASS; `BldWoodBSmRailStairs03L` reached 2.74 of 2.93 m.
- Reruns with the fixed runner: **Vault 114 stall doors `04BF66` / `04BF9D` pass from both sides** (the "raised door" was
  the camera); every Vault 114 door now passes. **Vault 81:** stall doors `19DA3A` (both sides) and `19DA38` pass;
  `19DA36` still BLOCKED (one side never moved, so the start is probably inside cave rock). Open.

## 2026-10-08 (evening): Parsons State Insane Asylum, prompt-seeking runner, load doors

First Parsons run: 26 of 36 door routes BLOCKED at almost exactly -0.48 m (standing at the closed door). Not the doors:
the screenshots show no "DOOR / Open" prompt because the levelled camera aimed over the door
([aim high](media/route-parsons-door-aimhigh.jpg)). Tilting 500 counts lower shows the prompt
([prompt](media/route-parsons-door-prompt.jpg)), so the fixed "up, then down 700" calibration does not carry between
sessions.

Runner changes (`scripts/game`):
- `prompt_visible.py`: detects the prompt's white title bar in a screenshot. `route_run.ps1` tilts down 150 counts at a
  time (up to 9 tries) until the prompt is on screen, then presses E. Results record `prompt`; `route_eval.py` reports
  a door that never showed a prompt as **NOPROMPT** instead of BLOCKED.
- Start reads far from the teleport target are re-read once. The runner stops if the start read equals the last route's
  end (stale read, console out of step). It happened once tonight: a "p" opened the Skills menu and 12 routes read
  the same position; closed with Tab, no skill points touched (0 available).
- `route_eval.py`: a start more than 3 m from the route start is UNREAD ("start not reached"). Starts under the floor
  (sunken `RWResStairs02` retaining-wall stairs, z -2.2) are moved by the engine to the cell entrance.

**Parsons rerun: every hinged door that was tested opens and lets the player through from at least one side**
([open](media/route-parsons-door-open.jpg)). Doors 13/14 to 47/48 pass on one side; the other side stops 0.6-1.7 m short
after the door opened ([swing side](media/route-parsons-door-swingside.jpg)). Same one-sided pattern as Rexford. No
Starfield door graph opens both ways (all 26 `*openclose*.agx` graphs have a single Open/Close), so the next experiment is
whether the runner stands inside the leaf's swing arc when it presses E.

**Real bug found: load doors swung open onto the void.** From the entrance the player walked through the entrance
load door (`BldWoodPDbDoorLoad01`) and fell to z -72. FO4 load doors never swing into the next space: activating one
teleports, and destinations are not ported yet. Fix in `pipeline.py`: `LOAD_DOOR_RE` load doors are not rigged and keep
their native collision (solid and shut). Each is reported per asset as `load_door: teleport not ported`, so the
missing behaviour is listed rather than silently dropped.

Stairs: 7 PASS; `RWResStairs02` STUCK twice (one ends in the dead tree's branches in the atrium); 5 routes start under the
floor (route generator to fix: needs a floor check).
- **Load door fix verified in game.** Rebuilt all 12 cells (only the 9 load-door models changed; no existing FormID moved)
  and deployed. The Parsons entrance double door now fills the doorway and is solid: walking into it stops the player at
  y 5.90, 0.4 m before the door plane ([before](media/route-parsons-loaddoor-before.jpg),
  [after](media/route-parsons-loaddoor-after.jpg)).
- **Test-environment trap: saves keep old references.** The save the test cycle loads still held the entrance door at
  its old rigged position (3.07, 6.37), because doors opened under the previous build are saved as changed references.
  The plugin itself had the right position (0, 5.486), checked by reading the REFR from the deployed ESM. For this
  test I moved the reference to its plugin position in the console. Results after a base-record change need a save
  made before the cell was visited.
- **One-sided door blocks: likely the runner, not the doors.** In each pair the first route opened the door and was
  blocked, and the second found the door already open (no prompt through the doorway) and walked through. With E pressed
  from the route start (no 350 ms step-in, so outside the leaf's swing arc) and only when the prompt says OPEN, the
  first blocked side tried, Parsons door `060990`, **passes (3.83 m through)**. The step-in had put the player inside the
  swing arc. The remaining blocked sides are still to rerun (stopped: another window came to the front).
  A 600 ms back-off after E fixed only 2 of 9, which fits a door stopped by the player mid-swing.
- **Runner safety, second Skills-menu incident, now prevented.** `console_open.ps1` + `hud_visible.py`: the console is
  opened only from plain gameplay (oxygen ring and health bar bright) and must be confirmed open (HUD dimmed) before
  anything is typed. `readpos` and `route_run` stop instead of typing otherwise. Checked both ways in game: a normal
  read works; with the console already open, `readpos` returns `fail console 3` and types nothing.
- Runner options: `-StepIn` (0 = press E from the start), `-BackOff`, `-Only 13,15`. Results record the prompt verb.

## 2026-10-08 (night): door-named walls and grass mounds had no collision (offline, in game next)

While making stair routes start where a sunken ramp leaves the ground, the ground probe found nothing around Parsons'
retaining-wall stairs: the grass mounds there had no collision. An old rule from before native collision ("doors and
vegetation: keep walk-through, a guessed box would be an invisible wall") was also dropping FO4's own collision.
It matched by file name, so it hit **every wall piece around a doorway** (`Bld*WallPlug*Door01`), the vault hall
pieces with door openings (`VltHallResDoorWide`, `VltHallUtilCorInDoorR01`), `PrySmRoomDoorway01`, the trapdoor ladder,
grass mounds, maple trees and hanging lights. That fits the falls to z -56 in the Parsons atrium and walls beside
doors you could walk through.

Fix: these models keep FO4's own collision but never get a guessed box (`convert_static(allow_guess=False)`). The only
deliberately passable models are door leaves that animate in FO4 but aren't rigged here (vault sliding doors,
elevator doors). Each is reported as `door_not_opening: open animation not ported: passable` (collision source
`passable-door`). Rebuild: **114 models gain FO4-native collision**, 41 stay without (none in FO4 either), 8 passable
doors, 1 failed (`SubLight02Hanging`, open). Editor IDs and all 38,314 FormIDs unchanged. Not deployed yet: the
game running now is the owner's session. Next: deploy, rerun Parsons/Vault 111/Vault 114 routes.

`routes.py`: stair routes now start where the ramp comes out of the surrounding ground (sampling the neighbours'
walkable FO4 collision along the ramp; `buried_fraction` per route). Load doors no longer get door routes.
- Route files regenerated for all 12 cells against the new build (in the side staging, ready for deploy). Stair routes
  whose ramp looks almost fully buried (2 Prydwen platform stairs that passed in game before, 1 library stair) keep
  their plain start and are flagged "looks buried, route kept": more likely an overlapping piece than real burial.
- **Broken FO4 hulls: exact rebuild.** `SubLight02Hanging` (a lampshade hull of 60 nearly coplanar points) failed:
  the polygon rebuild made overlapping near-coplanar faces, and a float incremental hull gave 165 faces for 58 points.
  New `meshcollision.convex_hull_triangles` snaps to a 0.1 mm integer grid and uses exact integer orientation tests:
  112 faces (2n - 4, closed). It is only used when the polygon rebuild can't close. Flat point sets become a 1 cm slab
  (`thicken_if_flat`). Side build now: 3,139 models with FO4-native collision (was 3,021 live), 284 with none as in FO4,
  8 passable doors; FormIDs unchanged. Still waiting to deploy (the running game is not mine to restart).
- **Three more interiors converted (item 3, offline):** Vault 75 (6,456 references + 353 lights), Fort Hagen 01
  (3,277 + 165), Museum of Witchcraft (1,176 + 74). 518 new models: 479 with FO4-native collision, 26 none as in FO4,
  2 passable doors (open animation not ported). Existing 3,490 models byte-for-byte unchanged in the manifest; all
  38,314 existing FormIDs unchanged (50,339 total). New routes: Vault 75 48, Fort Hagen 61, Museum 12. Build waits in
  the side staging with the collision fixes; deploying needs a game restart the owner has to OK.
- **Wall stains as decals (item 4, offline, unverified):** FO4 draws its wall streaks (`DecoStain*`, 6 models, 244
  placements) with effect shaders, so they were skipped. Effect shaders whose base texture is grime
  (stain/streak/grime/leak/blood/decal, not from `textures\Effects`) now become Starfield decal materials
  (`effect_decal_material`; flat normal when the effect has none). Caveat: FO4 also maps these through a gradient
  palette (`BldStreakGrad01`) that isn't reproduced; the texture is dark and mostly opaque, so they may render as dark
  sheets. First thing to check in game. Still skipped, and listed as build failures: the animated oil puddle, the
  glowing "Open" sign and the strobe flash (emissive and animated effects aren't ported). Side build: 4,014 models,
  6 failures (was 12), all FormIDs stable.
- **Both-side door activation (runner, offline):** saved runs could never show a door opening from both sides, because
  the first route left it open and the second side saw no OPEN prompt (traversal, not activation; Grok's `632c4dc`).
  `routes.py --formids` now records each door's Starfield ref id (`sf_ref_local`). `route_run.ps1` closes that door
  (`prid <PluginIndex><id>`, `setopenstate 0`) before every door route, so each side records its own OPEN. `-StepIn`
  now defaults to 0 (press E from outside the swing arc). Routes regenerated for all 15 cells in `multi_next`.
  Coordination posted to #32: asking Grok for a deploy window, Codex for the batch-invalidation case.
- **Precombine debris parts (offline):** 36 of the remaining guessed-box models are FO4 precombines (`SCOL\CM*.NIF`) that
  fail with "shared vertex index 2130 out of range". This isn't junk data: those bodies use another primitive encoding
  (packed 0, 4 shared vertices per primitive, shared-index triples (2130, start, x)), thin debris rods ~1 cm thick.
  Such a part is now skipped and reported (`skipped_parts`), and the rest of the model keeps native bodies. Gain is small:
  2 models move from guessed boxes to native (`CM00075A6C` had 182 boxes). 38 guessed remain, mostly precombines made only
  of these rods. Next: decode the encoding (each primitive as the convex hull of its 4 shared vertices is the working guess).
- **Vault 111 guessed boxes cleared (offline):** `V111Glass01` uses FO4's plain `hknpConvexShape` (vertices only, a flat
  pane 3.56 x 0.87 m): it's now converted with the hull rebuild, the flat pane as a 1 cm slab. `V111Generator02OnBroken`
  has compound mesh instances with a rotation: the compressed mesh stays in its own space and the instance transform goes
  on the body's child node (node * instance), instead of re-quantising. Convention check against the render mesh: mean
  distance from collision points to the nearest render vertex is 0.185 m as coded vs 0.24 m transposed. Side build: 3,625
  native, 36 guessed (all precombines made only of the undecoded rod primitives). Unverified in game.
- **Corrections (Grok, #32):** (1) "Vault 111 has no guessed boxes left" (`3a165fa`) was wrong: Vault 111 still places two
  rod-encoding precombines (`CM00140617`, `CM001405FD`) on guessed boxes. (2) The "thin debris rods" reading of that
  encoding is wrong too: of 412 four-vertex groups across the 36 models, many are not thin (`CM00163A1B` has groups
  ~3 m in every axis; median middle extent 0.66 m). So these parts must not be dropped as harmless; they stay
  reported (`skipped_parts`) with guessed boxes until the encoding is decoded. The grouping by 4 is itself unconfirmed.

## 2026-10-09 (evening): Parsons doors open from both sides (pinned build)

Pinned build: `multi_next` deployed with plugin `AC379C53...`, Main.ba2 `B8080348...`, code `1d3d5bf`
(`staging\multi_next\deployed_hashes.txt`). Runner: per-route door reset (`setopenstate 0`), E pressed from the route
start, OPEN read from the prompt (`94d6dcb`), idle-camera wake (`76488be`).

- First full run (45 routes): 3 hinged doors passed both sides with a recorded OPEN, 8 one side, 5 none; stairs 7 PASS,
  1 STUCK, 5 starts not reached (sunken `RWResStairs02`). 9 of the 12 door blocks had the prompt on screen but OCR read
  no verb, so E was never pressed: a runner bug, fixed in `94d6dcb` (crop + enlarge + threshold; 37/37 saved shots read).
- Door re-run (same build, routes 4-35; stopped by the foreground guard at 36 when another window came up):
  **11 hinged doors pass both sides with OPEN recorded on each side** (22 of 25 door routes; all 24 verbs read "OPEN",
  none from the unread fallback) ([side A](media/route-parsons-door-bothsides-a.jpg),
  [side B](media/route-parsons-door-bothsides-b.jpg)). Left: `06CF29` double door stops 0.30 m past the plane (needs 0.8),
  `IndMetalDoor02` blocked on one side, its other start not reached. Routes 36-44 still to run.
- **Vault 111 and Vault 114 on the same pinned build** (`AC379C53...`), cells entered with the verified `coc.ps1`
  (`957ddf2`): **Vault 111: 12 of 12 routes pass** (10 stairs + the caged switch door from both sides,
  [open](media/route-v111-switchdoor-open.jpg)). **Vault 114:** 28 PASS, 1 STUCK, 3 BLOCKED, 1 UNOPENED, 12 UNREAD
  (swapped OCR columns); doors 5 both sides ([subway door](media/route-v114-subdoor-open.jpg)), 3 one side, 3 none
  (`SubDoor01Right` `05C7DC` and two stall doors). A first Vault 111 attempt used a blind console toggle for `coc`,
  missed, and ran inside Parsons (falls to z -4990); those 5 lines were removed from the results before scoring.
- Runner safety this session: routes whose start the engine relocated are skipped (`2794e07`; E at the entrance had
  opened a dialogue with the companion); cells change only through `coc.ps1`, which verifies arrival at the COC
  marker. The companion (Vasco) was told to wait in Vault 81 for this session (in-game dialogue, nothing saved).
- **Finding: FO4 physics objects become fixed obstacles.** Vault 114 door `05C7DC` (`SubDoor01Right`) opens but
  blocks from both sides: a `SkeletonClothed01` lies in the doorway. In FO4 it is a MovableStatic, a physics
  object the player pushes aside. `convert_bodies` gives every FO4 body a static Starfield body, so here it is an
  immovable wall. This is a systematic gameplay change for all FO4 dynamic objects (MovableStatic, loose items), not
  a door bug. Not fixed yet. Plan: read each FO4 body's motion (dynamic vs static), and give dynamic ones a movable
  Starfield body from a vanilla donor (as the keyframed door leaves do), with mass from FO4. Until then they're
  reported, not silently changed.

## 2026-10-09 â€” Codex: checkpoint success-validation parity (#32)

- Verified with synthetic generated NIF/material/texture outputs: a checkpoint with intact output hashes but `fallback_materials: 1` or `door_error` was reused although save rejects it. The new regression fails both cases against baseline `cd94162`.
- Load and save now share the same success predicate; degraded cached results cause reconversion and do not enter batch expectations.
- Validation with the numpy-enabled render venv: `python -m unittest discover -s tests -p test_checkpoints.py` (13 pass), `python -m unittest discover -s tests` (253 tests, one skipped), `python scripts/guard.py` (ok). Tests ran outside the sandbox after temporary-directory permission errors inside it.
- Synthetic/offline only; game versions not applicable, no game assets or live installation changed. QA required before merge.
## 2026-10-10 Session end (owner powering down)
Status summary posted on #32 (comment 6094545513): pinned-build route results per cell, open problems by owner,
open PRs (#34 QA PASS, #35 in progress), local team state, next steps. Removed a stray `needs-qa` label from #32.
docs/ai/agent-status.md refreshed from live sources. Shut down: guardian proxy stopped, local model unloaded, no
background jobs left. Next session: re-run Vault 81 and the library, finish the Prydwen (same pinned build), then
movable bodies for loose items.

## 2026-10-10 Movable loose items (offline; owner at the PC, so no game input)
FO4 loose items (one dynamic body: pencils, cans, clipboards) now convert as movable Starfield objects instead of
fixed obstacles. Evidence and field meanings: docs/ai/research-log.md "how Starfield makes a body movable".
- **Starfield side, decoded by name** with `hktagfile`: motionType 2, flags 0x8a, mass, a motion-properties entry and
  a mass distribution (centre, volume of the shape grown by its convex radius, inertia per kg x 1.5: 30 of 30 vanilla
  boxes). Movable set dressing is a **MoveableStatic** record (a Static never moves; the clutter layer alone does
  nothing) and the NIF has BSXFlags 0x42.
- **Converter:** `meshcollision.convert_bodies` writes a lone dynamic FO4 convex body on a vanilla dynamic item's
  template (`fooddrink_set_container01_empty_lid.nif`, read from the user's install), with FO4's mass and layer and a
  computed mass distribution; `convert_static` puts it on the root node; the manifest marks the item `movable`; the
  plugin writer makes it a MoveableStatic (`DATA 4` as vanilla). Default on with `--starfield-data`;
  `--static-items` turns it off.
- **Not converted (reported, not hidden):** ragdolls and breakables (several bodies: need constraints, e.g. the Vault
  114 skeleton), dynamic compound / mesh / sphere bodies, and dynamic bodies on child nodes stay static, listed in
  `collision_report.dynamic_kept_static`.
- **Correction:** an old comment in `sfcollision.py` called offset 240 the motion type; it is the collision layer
  (232 flags, 264 motionType).
- Offline check: TinCan01 5 kg, Clipboard01 4 kg, Pencil01 0.5 kg read back as dynamic bodies; the skeleton stays
  static with 17 reasons. Tests 262 OK, guard OK. **Not yet seen in game** (next: build, deploy, push a can).
- **First in-game attempt (2026-10-10 16:2x), aborted, nothing learned about pushing yet.** Test build
  `C:\Modding\staging\movable_v111` (Vault 111 only: 219 models, 13 movable = coffee cups, beer bottles, folding chairs,
  clipboards, tools; 10 dynamic-in-FO4 models kept static with reasons: skeletons, gear-room gate, and compound shapes
  such as the cardboard box and traffic cone). `cycle.ps1` loaded the save but Starfield's "console commands disable
  achievements" popup swallowed the `coc`; the follow-up `coc.ps1` was blocked by the focus guard (Explorer had focus;
  also `FO4SF_PYTHON` was unset, so the HUD check had no Pillow). The owner closed the game. The pinned build
  (`AC379C53` / `B8080348`) was redeployed and its hashes verified. Next attempt: set `FO4SF_PYTHON`, dismiss the
  popup inside `cycle.ps1`, and only when the owner is away. Follow-up found by the build: dynamic **compound** bodies
  (several convex parts: boxes, cones, hammers) are common and need one dynamic compound body, not several.
- **Movable compounds (offline, owner at the PC).** FO4 loose items made of several convex pieces (cardboard boxes,
  traffic cones, hammers, wrenches) now convert to one dynamic `hknpCompoundShape` body, laid out exactly as Starfield's
  273 vanilla movable compounds (research log "Starfield dynamic compound bodies"); their mass distribution is the
  compound's bounding box as a solid box, as vanilla. Dynamic bodies now use a vanilla compound item as the template
  (`cb_blackmarketantiquities.nif`). Offline: the cardboard box (9 pieces, 5 kg), traffic cone (8), hammer (2) and
  wrench (4) read back with bounds, tree leaves and mass matching to 1e-8. Vault 111 test build: **18** movable models
  (was 13); only multi-body objects stay fixed (3 skeletons, gear-room gate, oxygen tank: they need joints). Tests 266
  OK. Still not seen in game (the next test waits until the owner is away or says go).

## 2026-10-10 In game: movable items and the Vault 114 skeleton door (owner away, said go)
Test build `movable_v114` (Vault 114 only, PR #41 code: 97 movable models, 7 of them merged multi-body), entered with
the fixed `cycle.ps1` (PR #42) and verified at the COC marker (0.0 m).
- **Door `05C7DC` passes from both sides** (routes 26 and 27, OPEN prompt both): 25.60 -69.71 -> 25.80 -74.80 and
  25.64 -72.95 -> 25.64 -67.63 (5.1 m and 5.3 m through). Before: blocked from both sides by the skeleton.
- **The skeleton moved** (one rigid 115 kg body, phase A): placed at 25.39 -72.55 -15.82 (FO4 position / 70), read
  back with `prid 02002E61` + `getpos` at 24.50 -72.89 -16.70: about 1 m sideways and 0.88 m down. The drop needs a
  visual check (a lower area, or partly through the floor?); the spot is too dark in screenshots. Open question.
- **A tin can is pushed by walking into it**: `02002CCB` 25.30 -67.10 -1.31 -> 24.74 -67.17 -1.30 after the
  player walked into it for 1.6 s. Screenshots are too dark to show it; the console read-back is the evidence.
- Status: dynamic bodies, MoveableStatic records and the walk-push are **verified in game** (one item, one ragdoll);
  the skeleton's resting height is **unresolved**.
- Popup (PR #42): it opens with the console; while the console is open, keys go to the console line; closing the
  console and pressing E closes it. `coc` from the main menu loads cells without a save, but the blank character is
  pulled into the new-game start after a few minutes (load screen, hang), so tests keep using the autosave.
- **Skeleton drop explained (offline; someone was using the PC, so no game input).** The converted skeleton is drawn in
  its skinned bind pose (standing, 1.88 m tall), while FO4 lays placed skeletons down with per-reference ragdoll data
  (`XRGD`, 28 bytes per body; research log). So the phase A rigid skeleton spawns standing and topples, which is the
  ~1 m slide and 0.88 m drop measured in game. Needed: `XRGD` in Fo4Export (Codex) and a posed bake on the converter
  side (skin weights). Until then skeletons are movable but in the wrong pose; reported, not hidden.
## 2026-10-10 Claude: load doors between converted cells get their teleport (offline)
FO4 load doors were kept shut since 2026-10-08. Now `dotnet/PluginSpike` makes every manifest `load_door` a graph-less
DOOR record (collision unchanged) and, after all cells of a build are placed, writes the Starfield XTEL on both ends of
every pair whose destination is placed in the same build; both references become persistent, as all 964 vanilla XTEL
references are (docs/ai/research-log.md 2026-10-10). Unlinked doors stay shut and are listed in `<out>/teleports.json`;
`PluginSpike teleports FO4Port.esm` lists the written links. Offline only: the pinned 15 cells + a scratch export of
FortHagen02 give one pair (FortHagen01 `0CD469` <-> FortHagen02 `0CD46A`), read back from the written plugin. Not yet in
game. Note for the next build: 12 of the 15 pinned cell exports predate the persistent-reference export and hold no
load-door XTEL at all; re-export them before expecting any door to teleport. Branch `claude/load-door-teleport`.

## 2026-10-11 Claude: load-door teleports checked on the re-exported 16 cells
Follow-up to 2026-10-10. With the 15 pinned cells and FortHagen02 re-exported (schema 2, C:\Modding\staging\exports_1011),
the branch writer reports "2 references linked (1 mutual pairs), 28 destinations not in this build, 4 sources not placed,
0 issues": 34 XTELs, one pair (FortHagen01 `0CD469` <-> FortHagen02 `0CD46A`), the rest lead out of the set or sit on
marker doors the converter never places. Read back from the written plugin; 0 existing FormIDs changed against the staging
map. `teleports.json` now lists the unplaced sources too (PluginSpike.Tests asserts it). Still offline, not in game; PR #50
(docs/ai/research-log.md 2026-10-11).
## 2026-10-10: the Prydwen's 7 small falls (offline diagnosis, fix not yet built)
The 7 `FALL` routes of the pinned Prydwen run are two problems, neither a hole in the converted collision
(details and evidence: docs/ai/research-log.md, same date).
- Routes 12, 13, 15, 18: the "stairs" `PryPlatformInCornerStairs01/02` are railing frames. Their post bevels gave the
  planner a fake ramp (ends 0.03 m apart under a 0.91 m rise), and the walk went down the real stair next to them
  (`PryCatwalkStairsEnt01`), ending where FO4's own steps are. `routes.py` now rejects ramps steeper than 60 degrees
  end to end (all real ones are at most 46.4).
- Routes 20, 28, 29: `PryCatwalkStairsEnt02` was converted facing the wrong way. Its NIF root node is turned
  180 degrees, and the game ignores a root node's transform: FO4's precombined physics matches 89 placements of 15 such
  models only without it. The converter applied it, so the first flight climbed away from the second and the routes
  started in mid-air. Now geometry, collision nodes and door pivots leave the root out (`nif.world_transforms
  placed=True`). This also turns back 43 other models (232 placements across the slice), among them diner counters,
  Vault 114/95 catwalk frames, desk lamps, posters and the Cambridge `HitDoorSm01/Lg01` doors.
Next: rebuild, then rerun the Prydwen (routes 12-32 and the regenerated Ent02 routes) and the Cambridge doors in game.
## 2026-10-10 Launch script hardened after QA (offline; owner at the PC)
PR #42's QA agent found that `cycle.ps1` pressed E blind when its screen check could not run. Fixed: a failed prompt
or popup check now stops with exit 5; an activation prompt that stays under the crosshair stops with exit 6; a `coc`
the popup swallowed is retried only after the console is closed and the popup cleared, with the console line emptied
first; the cell name is validated before it is typed. New tests: every `scripts/game/*.ps1` must parse (PowerShell's
parser, skipped where there is none) and `prompt_visible.py` is checked on synthetic screenshots. 258 tests OK on
this branch.
- **Launch script waits on the screen, not timers (offline).** `cycle.ps1` now polls a screenshot every 3 s for the main
  menu text, then for the HUD after Continue and after a blind `coc`, instead of sleeping 30 + 45 + 37 s. The checks
  were validated on today's saved screenshots (menu text read on the menu shot only; HUD seen in game only). Before:
  195-210 s per cycle; after: to be measured on the next run (docs/ai/optimization.md).

## 2026-10-11 Overnight: library and Vault 81 re-run on the pinned build (Lead task 4)
Owner away (PC idle 4.7 h); normal build restored (`AC379C53`), entered with the verified cycle (168 s, from 195-210).
**Boston Public Library, 67 routes (110 min):** 42 PASS, 10 STUCK, 4 FALL, 5 BLOCKED, 6 UNREAD. Doors 12 of 16 both
sides, 1 one side (`0FFCA5`), 3 none: the wooden double doors `100196` and `10019C` block from both sides. The deco
rail stairs (`BldDecoSmRailStairs01L/R`, `03L/R`, `Short01R`) account for 7 STUCK/FALL; brick and block stairs pass.
**Vault 81, 19 routes:** 16 PASS, 2 BLOCKED, 1 UNOPENED; all 13 stair routes pass; stall doors `19DA38` both sides,
`19DA3A` / `19DA36` one side each. Results: `run_lib_1011`, `run_v81_1010` (local). Posted on #32.
## 2026-10-11 Route planner: railings are not stairs; double doors are twins (offline)
Two findings from the library run, both test-side, not converter bugs:
- The 7 STUCK/FALL "rail stairs" routes (`BldDecoSmRailStairs*`) were routes on railings: their FO4 collision has no
  treads at all (6 flat vertices on one level) and no helper; the steps are a separate model. A scan of all 74 "stair"
  models in the pinned build: 45 carry FO4's RampDummy helper, the other 29 are railings, trims and stairwell walls, and
  NONE has treads without a helper, so a synthesized helper (built and then dropped today) has no target. The planner
  now requires 3 tread levels for a model without a helper and skips the rest with a reason (`tread_levels`).
- The library's "double doors" `100196` + `10019C` are two single-leaf `BldWoodPDbDoor01` references on one spot,
  rotated 180 degrees, each hinged at its own jamb; the route activated one and hit the other leaf. The planner marks
  such pairs (`door_twins`, within 0.1 m) and the runner resets and activates the twin leaf too (`+twin:` in the verb).
Tests: tread levels (steps, railing, helper and underside ignored, 4 cm merge) and twins; 260 OK, guard OK. The
twin step is untested in game until the next library run.

## 2026-10-11 Queued test runner verified in game; terrain kickoff (Claude)
- **Runner (PR #59)**: `scripts/game/testqueue.py` + `qstep.ps1`. Supervised batch on the integration build `2470f876`
  (main + #41 #50 #51 #42 #54, local branch `claude/integration-1011`): launch, dedicated save `fo4sf_test_2470f876`
  created and loaded, god mode read from the console ("God Mode enabled."), cell arrival verified; 2 stairs PASS,
  2 falls PASS, 2 doors FAIL (`BldWoodPDoorShutter01` open but the route aims beside the doorway). Six runner bugs found
  and fixed (kind mapping, tgm reply, ceiling pieces as probe floors, OCR without ">>", Steam popup taking the focus,
  HUD recovery). The owner closed the game mid-run; movable and travel steps are not verified in game yet.
- **Queued**: the rest of the supervised batch, then 753 tests on 16 cells (`C:\Modding\testqueue\overnight.ps1`),
  starting only after 15 min without input.
- **Terrain**: PR #56 (FO4 2x2 patch at Red Rocket, two decoders agree exactly, borders match, the building sits on the
  terrain) and PR #57 (Starfield: 430/433 worldspaces use `Data\TERRAIN\<EditorID>.btd`; BTD decoded and re-encoded;
  experiment 1 staged in `C:\Modding\staging\terrain_exp1`, not deployed). Next blocker: the in-game BTD load test.

## 2026-10-11 afternoon: terrain experiment 1 in game (unattended runner)
- **Run 1:** loose BTDs. World01 and World02 (record path; record path + name) load on Mars with procedural ground. The heights are identical in both worlds (4.18 / 11.86 / 15.98 / 10.68 m at our 10 / 35 / 22.5 / 5 m pads), so neither used its BTD. World03 (name only, no surface block) hangs on the loading screen.
- **Cause of run 1:** the loose files were never read. `Starfield.ini` has `sResourceDataDirsFinal=STRINGS\` and there is no StarfieldCustom.ini. The experiment installer now packs the BTDs into the plugin's own `<plugin> - Main.ba2` (`exp_install.py --pack`).
- **Run 1b:** BTDs packed. World01 reads the same procedural heights again, so the packed BTD isn't used either. Registering World01 on Mars (run 1) moves the spawn onto a real Mars mountainside; the pads read flat at about -2.5 m, still procedural.
- **Next (queued):** control drops in two vanilla worldspaces via `cow`, at lc001world and akilacity points whose BTD heights are known. These show whether `coc`/`cow` gives BTD terrain at all, or only the planet landing does. Then the Mars-registration variant with packed BTDs, then the test batches.

## 2026-10-11 late afternoon: terrain measuring method validated on vanilla terrain
- **Console routes into vanilla exteriors:** `coc <exterior cell EditorID>` works (`LC172Ext01`, `LC001Outpost`). `cow`, `coc <worldspace>` and `player.moveto <non-persistent ref>` do not.
- **Control LC172World** (the template our test worlds are cloned from): the overlay is merged into Mars at offset (-500, -2300, -3.62), read from the persistent COC marker 0010238E. Probes in the overlay's own frame:
  - match its BTD within **0.02 m** in the centre cell, which the vanilla overlay mask marks as authored;
  - within 0.3-0.36 m just outside it;
  - 4-6 m off in the border cells, where the mask blends in procedural terrain.
- **Method:** anchor-relative probing measures BTD heights exactly where the overlay is authored, and the overlay mask decides where that is.
- **Research** (`C:\Modding\research\terrain\binding\findings.md`, PR #64): a worldspace's own BTD only applies to an overlay activated on a planet (PNDT CNAM). Our records also differed from vanilla in FNAM size, Location, mask and alignment. The fixed experiments exp1d and exp2b (real Red Rocket heights) are queued after test B.

## 2026-10-11 evening: why our overlay terrain came out flat
- **In game:** every registered overlay test was perfectly flat at exactly its BTD's minimum height:
  - exp2b (29x29 Red Rocket BTD, absolute alignment) read -116.00 m at all 14 probes;
  - World01 / exp1d read -500 m (with relative alignment, -13.94 m).
  The overlay itself was activated (cells merged at whole-cell offsets).
- **Offline diagnosis** (two agents; scratch data in `C:\Modding\research\terrain\zero`):
  - Our BTD layout matches vanilla section by section, and the heights are in every LOD.
  - The one difference is that all 2,112 vanilla BTDs (Shattered Space's 108 included) and every official plugin Main.ba2 are stored **uncompressed**. Ours were zlib-compressed by Archive2 `-compression=Default`.
  - The engine reads BTD blocks by offset straight from the archive, so it decoded nothing and used raw 0.
  - Fix: `exp_install.py` now packs with `-compression=None`.
- **Next candidates** if that is not all:
  - `lodsettings/<edid>.lod` (every vanilla overlay has one);
  - the 29x29 size (the largest vanilla overlay is 14x14).
- **Queued:** exp2b3 (Red Rocket, stored), then exp1f (World01, stored), then the batches.

## 2026-10-11 evening: native Starfield terrain carries the real Commonwealth heights (Red Rocket)
- **exp2b3**, our FO4CW_Commonwealth overlay (29x29 Starfield cells of FO4 LAND around Red Rocket, Absolute alignment, registered on Mars, BTD stored uncompressed in the plugin's Main.ba2): 13 of 14 probes match FO4 height / 70 within 0.08 m, including the Red Rocket origin (105.14 m), slopes, an FO4 cell seam and a Starfield block seam. Overlay Z offset 0.01 m.
  - The 14th probe (resampled_sw) ended 142 m from its target, so it was not measured.
  - Absolute alignment keeps the real world heights.
- **Cause of all the earlier flat results:** a zlib-compressed BTD in the BA2. Stored (uncompressed), as vanilla ships it, works.
- **Next (queued, each test from a fresh launch):**
  - exp2c: 8,069 real FO4 objects around Red Rocket on this terrain (PR #66);
  - exp3: four edge-to-edge 14x14 overlays with seam probes (PR #67);
  - World01 stored; the vanilla NPC navigation control; then the batches.
- **exp2c, same evening:** the real FO4 objects around Red Rocket (8,069 references, 1,385 converted models, one plugin) stand on the native terrain in game. Textures load from the stored plugin archive.
  - Test 1 PASS: the terrain probes are still within 0.08 m with the objects placed.
  - Test 2 PASS: object tops land where FO4 put them, so their collision works: Red Rocket roof 109.73 m (want 109.74), brick building roof 103.87 (103.88), road piece 88.20 (88.21).
  - Probing 100 m past the overlay raised Starfield's "Boundary Reached" popup, the landing area's limit.
- **exp3** (four adjacent 14x14-cell overlays, each registered on Mars): probes in the arrival tile read real terrain. Every probe 500-700 m away, in or near a neighbouring tile, hung at the drop height even after 24 s of re-reads, so nothing loads there.
  - Taken with the "Boundary Reached" popup at the edge of the 29-cell overlay, a landing seems to load only the overlay it arrives in. A Commonwealth made of many small overlays would not be walkable across seams.
  - The candidate is one large overlay. **terrain_core64** (PR #72: 64x64 cells = 6.4 km covering Sanctuary, Vault 111, Red Rocket and Concord, 6 rays of probes out to 3 km) is queued.
- **Navmesh (PR #71):** FO4's navmesh around Red Rocket is converted to 156 Starfield NAVM records with a NAVI override. The N1 NPC tests are queued after the vanilla control N0:
  - N1a: terrain only;
  - N1c: converted navmesh;
  - N1b: the runtime generator.
- **Ground textures (PR #70):** staged. They need a daytime run; every Mars arrival so far was at night.

## 2026-10-11 night: dead man's switch and the huge batch (owner's request)
- **`scripts/game/watchdog.ps1`** runs detached. It is not reboot-proof yet (the owner was asked about a scheduled task).
  - After 3 h with no "Claude:" commit and no heartbeat (`C:\Modding\testqueue\claude_heartbeat.txt`), it starts `C:\Modding\testqueue\chain.ps1` itself. No AI is needed; the runner keeps every owner control.
  - At most every 6 h it calls Codex (`codex exec`, sandbox workspace-write) to follow `docs/ai/codex-runbook.md`: status, reports, one #32 comment, no code changes or game input.
  - At most 3 chain starts per 6 h. An unfinished required queue goes back to the front of `chain_queue.txt`.
  - AGENTS.md records the exception.
- **`batch_full`**, queued last: 1,764 tests on the 16 cells. It covers every route (routes.py `--max 400` -> `routesfull_*.json`) plus 40 falls and 40 movable items per cell, about 30 h.
- **core64** (one 64x64-cell overlay, 6.4 km) in game: every probe within ~500 m of the arrival is exact (Sanctuary 110.27/110.29, Vault 111 127.09/127.09). Single 1-2 km setpos jumps do not load in time, so a hop variant (300 m steps) is queued next.

## 2026-10-11 late night: the "far terrain does not load" result is a 9x9-cell playable border
- **core64, all six rays** (one arrival at Red Rocket each, from a fresh launch): every probe up to ~380 m from the arrival reads the FO4 height within 0.01 m (arrival 105.14, Sanctuary 110.27, Vault 111 127.09, Concord 87.09, se_500m 56.92/56.91, ne_500m 113.38/113.37).
  - The first probe at 500 m straight east, south or west (and 700 m diagonally) raises Starfield's **"Boundary Reached"** popup (screenshot in the test folder). Its position read is garbled, and every later probe stays at its drop height.
  - The allowed probes span local cells x -14..-7 and y 8..14, and the blocked ones sit 5 cells out. That is a window of about 4 cells around the arrival cell (-10, 11), inside an overlay whose 4,096 cells all exist and whose worldspace bounds (NAM0/NAM9) cover the whole 6.4 km.
- **Supported hypothesis:** the limit is Starfield's landing-area border, not our data. Starfield.exe has `bBorderRegionsEnabled:General` (set to 0 by the "Border Regions Unlock" mod), `fPlayableAreaX/Y/Z:General`, `uMaximumPlayableAreaWorldCoord:General` and `uPlayableSpaceOverlayCellBuffer:Planet`. The console has `SetINI` and `GetINI`, so a test can change the border for one session without touching an ini file.
- **This also confounds exp3's "neighbouring overlays do not load" result (500-700 m probes).** That needs a re-run with the border off before the many-overlays option is ruled out.
- **Runner:** core64b (300 m hops) is paused with a queue STOP. Its second hop would only reach the same border. The next queue reads the settings (`GetINI`), sets `bBorderRegionsEnabled` to 0 after the save loads and before the coc, then repeats the rays and hops.
- **Fixed:** an open breaker now skips a test before the "fresh" relaunch (one wasted launch per tripped breaker).
- **Correction, 2026-10-12 00:01: travelling works, so the border limits jumps, not the world.** core64b's north-west ray reached every probe in 300 m hops (11 hops) and PASSED to 2 km:
  - arrival 105.14, Sanctuary 110.27, Vault 111 127.09, 500 m 114.17 (want 114.17), 1,000 m 202.54 (202.51), 2,000 m 188.45 (188.46);
  - no "Boundary Reached" on the way.
- So the popup comes from a **single teleport more than ~4 cells from the current position**, not from a fixed window around the arrival. The 6.4 km overlay streams in as the player moves.
- exp3's neighbouring-overlay probes were single 500-700 m jumps too, so the seam question is open again and needs a hop run.
- The other five core64b rays are pending: its STOP is removed, and it needs to go back into `chain_queue.txt`. terrain_core64e (PR #74, one pebble per cell) now only asks whether content changes the single-jump limit, which is low priority.

## 2026-10-12 early morning: navmesh plugin terrain check passes; the vanilla NPC control is not a control yet
- **exp2d PASS** (Red Rocket terrain + objects + the converted navmesh plugin, PR #71): the ground under all four N1 NPC points (A, B, and A2/B2 across a cell line) reads the expected height within 0.01 m, 5 of 5. The navmesh plugin does not disturb the terrain.
- **N0, the vanilla NPC control in QASmoke** (actor 002B211C, levelled 0000CF96; A (-8, -4) to B (5, 10), 20 m):
  - 2 PASS, 3 FAIL, but **no test shows a commanded walk**. Every actor, with or without a command, stayed in the same patch (x -11..0, y -6..2) and never came within 10.8 m of B.
  - Baseline (no command): wandered 5.4 m towards B, FAIL WANDER.
  - `PathToRef player`: 6.8 m and 9.0 m towards B, counted as PASS, but that is within the wander.
  - `cf "Actor.PathToReference" player 1.0`: the console replied "No script named Actor is attached to the object".
  - `SetPlayerTeammate 1` + `EvaluatePackage`: the actor stood still for 30 s.
  - The robot visible next to the camera in the sample shots is also there in the no-command baseline. It is most likely the save's companion, not the test actor.
- **Next for the NPC tests:**
  - B must be reachable on navmesh from A (supported hypothesis: it is not in QASmoke, or the package overrides PathToRef).
  - The judge must require arrival (end within a few metres of B) or progress beyond the baseline's wander.
  - Add `StartCombat player` (a script command in Starfield.exe: "Forces the currently selected reference to initiate combat with the provided actor") as a control method.
  - The N1 queues still run (moving at all on our terrain with and without navmesh is useful), but their "towards B" verdicts carry the same caveat.

## 2026-10-12 ~02:00: three slice pieces built and reviewed; integration-1012 ready (not yet the chain's runner)
- **Built and adversarially reviewed overnight.** Each reviewer found blocking problems, and each was fixed.
  - **PR #73 (daylight, plus the console hook).** `SetLocalTime` is the runner's time-of-day command, with the reply captured.
    - Light is judged from every probe shot, and NIGHT is retried.
    - A queue lists the runner features it `needs`, so an older runner refuses it at pre-launch instead of running it without the time.
    - The test is staged at the site that was night 18 of 18 times (`terrain_exp2b2_noon`); the daylight site was day 13 of 13.
  - **PR #75 (first converted FO4 NPC):** the Concord raider (FO4 ACHR 00046458, LvlRaider) as one Starfield NPC_ on the Spacer templates.
    - The record now carries PRPS/STON/EDCT/PRON, which all 7,131 vanilla NPC_ have.
    - A calm copy is used for the walk tests (N2a), so the peaceful vanilla control is fair. The hostile copy goes to N2b.
  - **PR #76 (every FO4 exterior object on the 6.4 km core):** 648,358 references of 11,769 models, a 46.1 MB plugin and a 3.63 GiB stored archive (textures capped per kind to stay under 4 GiB).
    - Object z matches FO4's own terrain at the median, +0.22 m.
    - The plan uses waypoints so that every teleport moves at most 2 cells per axis.
- **Teleport rule:** at most 2 cells per axis landed 144 of 145 times; 3 or more cells per axis failed 11 of 28 times (all 6 in core64). The rule is a supported hypothesis from `scripts/terrain/teleport_audit.py`, and "~4 cells" is refuted.
- **`claude/integration-1012`** merges test-queue, daylight, raider and core64-objects. The unit suite and guard pass.
  - It has one semantic fix: NPC plans accept the light and console keys.
  - Queues planned with it: `terrain_core64c`, `terrain_exp2b2_noon` (needs: light), `npc_nav_n2a`, `npc_nav_n2b`. They are not in the chain yet.
  - The chain still runs integration-1011 (N1c, N1b, then the supervised and full batches). Switching the chain's checkout and adding the queues is the owner's call.
- **N1a** (vanilla NPC on our terrain, no navmesh): the NPC never moved (0.0 m), as expected without a navmesh. It counts as INCONCLUSIVE only because N0's control did not pass.
- **N1 (vanilla NPC 002B211C on our Red Rocket terrain, ~03:10): the converted FO4 navmesh carries Starfield's AI.**
  - **N1a (terrain only, no navmesh):** the NPC never moved in 4 of 4 tests. Every read was the same position to 0.1 m for 30 s.
  - **N1c (with the converted navmesh, PR #71):** the NPC moved in 4 of 4 tests, 10.5, 7.2, 11.0 and 14.1 m (paths up to 27.6 m), and its z followed the terrain (105.0 to 105.5 m). It also walked about 9.5 m towards the player before any command.
  - These are **verified movement on converted navmesh**, not commanded navigation: it wandered, as in QASmoke, and never reached B.
  - The cross-cell test stayed in its own cell (x -2194..-2183, cell line at -2200), so the NAVI edge links across cells are still **unresolved**.
  - All N1 verdicts read INCONCLUSIVE CONTROL because N0's control is not a control yet. N0b (navmesh-connected points, StartCombat, arrival judging) is being built and reviewed.
- **N0b, the NPC control redesign (PR #77, reviewed and fixed; merged into integration-1012 at f3dcf5d):**
  - **Why N0 could not tell commands from wandering:** QASmoke's navmesh (one NAVM, 002BE3AA) is a single 555 m2 area. The old pair was connected by a clear straight path. The actors' own drift (up to 14.06 m from t0, measured in N1c) covered most of the 19 m.
  - **New design:** a 24 m pair. The approach before the command is capped at 3 m (otherwise INCONCLUSIVE PRECOMMAND). A PASS needs 18 m of approach from t0 or arrival within 3 m. A control counts only with its own queue's baselines.
  - **Tests:** two citizen baselines, the Spacer baseline, PathToRef and StartCombat.
  - **Queue:** `npc_nav_n0b` (needs runner feature npc_t0, so integration-1012 or later).
  - **Re-plans:** the N1 and N2 re-plans are staged as `npc_nav_*_b`. They are planned only after `npc_control.py ready` confirms N0b passed. The earlier `npc_nav_n2a` / `npc_nav_n2b` queues carry a STOP note (superseded).
- **N1b (the same NPC on our terrain after Starfield's runtime generator `gnm`, no shipped navmesh):** it never moved in 3 of 3 tests where it spawned. The 4th test did not confirm its spawn, twice (INCONCLUSIVE SPAWN, a runner reason).
  - Reading so far: no navmesh means no movement; `gnm` also gives no movement; the converted FO4 navmesh gives movement in 4 of 4 tests.
  - Shipping the converted navmesh is the supported route; `gnm` in a plugin worldspace is refuted for this use, to be rechecked with N1b_b against the N0b control.
  - The chain now runs supervised_1011, then batch_full (integration-1011 runner).
- **supervised_1011 finished (17 tests: 10 PASS, 5 FAIL, 2 INCONCLUSIVE).** Ranked:
  1. **Door BLOCKED, 2 tests:** FortHagen01's wooden shutter door (BldWoodPDoorShutter01, 0BD6A1). It shows OPEN, activates and swings, and the prompt flips to CLOSE. But the panel still covers part of the opening, and the player stops 0.9 m before the door plane. Candidates: the door swings only part of the way, or its collision does not follow the animation. Unresolved.
  2. **Travel NOPROMPT:** FortHagen01 load door 0CD469. The companion stood at the door; the runner now disables it per session (bf01e51, not yet in the chain's runner).
  3. **Stairs STUCK:** Vault 114 CinderBlockStairs02 (rose 0.10 m, needed 0.12 m).
  4. **Movable NOTMOVED:** FortHagen01 CigarettePack. The player reached it, but it moved 0.000 m.
  - The two INCONCLUSIVEs: a fall held 1.5 m above a cave floor, and a movable test the player missed by 2.39 m.
- The chain now runs **batch_full** (1,764 tests, about 30 h) on integration-1011.

## 2026-10-12 morning: multi-part FO4 doors lost every panel but the first (fixed offline, PR #79)
- **Cause (verified offline):**
  - `nif.door_hinge` read only the first node the FO4 `Open` sequence moves.
  - `convert_door` hung that node alone under the Akila template hinge. Every other panel went under the static frame, with no bone and no body.
  - The Akila clip has one track.
  - The FortHagen01 shutter's `Right` panel is one example of a panel that stayed behind.
- **Blast radius:**
  - In the 16 pinned cells: 10 door models, 38 placed doors and 76 batch_full door tests. They include the Parsons double door 06CF29, plus high-tech doors with 3 of 4 sliding panels frozen.
  - In Fallout4.esm: 80 models move geometry outside their first node.
- **Fix:**
  - These doors get their own rig plus Open/Close clips built from FO4's keys with CALUMI: one bone, one track and one keyframed collision box per moving part.
  - Clip keys are offsets from the rest pose, as in 126 vanilla door rigs.
  - Offline result: 40 of 40 moving parts have tracks and bodies (was 23 of 40). 47 of 57 door models are byte-identical. The overlay plugin differs from integ_1011 in exactly 48 records.
- **Review notes (pass-with-notes):**
  - Nested motion is not detected yet (`RRMegaSecurityDoor01` and `Prewar_Locker_Door01`; neither is in the build).
  - One physics system per panel has no vanilla precedent: every vanilla double door shares one system. This is the largest in-game risk.
  - Three rigs use FO4's `@#0` name suffix as bone names.
- **Also:**
  - The FortHagen shutters are windows (the wall is solid to about 1.03 m), so their walk tests cannot pass; the route planner should skip openings above step height.
  - It all needs a new pinned build (overlay `integ_1011_doors`) after batch_full. Commands are in docs/spikes/WP-doors-research.md.
- **Slice: the Red Rocket cave door (PR #78, fixed after review; merged into integration-1012):**
  - **Source (verified):** in FO4, RedRocket01's door 05E844 and the exterior door 08EB65 are AutoloadDoors (the player walks into a marker) linked to each other. Neither end existed in our build: markers are never placed.
  - **Plugin:** FO4SliceRedRocket.esm places the vanilla AutoloadDoor_Cave (24F9CE) at both FO4 spots. Its marker is the FO4 marker / 70 within 0.013 %, and the two doors are persistent and teleport-linked both ways.
    - It sits in the cave mouth 38 m south of exp2d's arrival.
    - Offline checks pass: 27/27 and 28/28.
  - **Runner:**
    - A `door_trip` kind: coc, walk in, read the cell and position, walk out, save, move away, load, read again.
    - FAIL NOLOAD needs the player still within 3 m of the door with no load seen.
    - The position is read after every walk step, so a fast loading screen cannot send the player into the void.
    - `exp_install.py order` puts experiment plugins after their masters.
  - **Queue:** `slice_redrocket_door_b` (needs door_trip, door_check, plugin_order: integration-1012 at 16e21a4 or later).
  - **integration-1012 now (16e21a4):** test-queue + #73 + #75 + #76 + #77 + #78 + #79. The unit suite passes (37 opt-in skipped) and guard passes. Its planned queues wait for the owner to switch the chain's runner.


## 2026-10-12 - Codex: recoverable installer compatibility for the cave slice (#78/#62)

Offline tested, synthetic files only; no game version/runtime acceptance claimed. #62 rejected the cave queue's --needs and cycle's order command. Combining the original ordering code with recovery also skipped pre-existing/reactivated plugins, accepted disabled masters/cycles and could overwrite a concurrent Plugins.txt edit. The new synthetic compatibility suite reproduced these failures plus plugin-only --pack trying to build an empty archive.

Carried #62's independently reviewed journaled publication, pinned SHA inputs and stored General BA2 coverage/content verifier onto #78. Retained the runner feature gate and ordering CLI; receipts now name every selected plugin. Ordering requires complete/non-cleanup state, unchanged selected plugin files, active masters and satisfiable dependencies; its atomic rewrite compares the original snapshot and refuses concurrent edits. Completed-install cleanup restores owned activation lines by text, so ordering requires no whole-file rollback snapshot update. Install/order/uninstall all refuse an interrupted or cleanup-pending main deployment before mutating its activation snapshot or experiment receipt. Plugin-only --pack keeps its requested mode for relaunch checks and builds no archive. Truncated TES4 headers/subrecords cannot hide a master. Two newer upstream packing fixtures now emit valid synthetic BA2 resources; runner implementation is untouched.

Validation: 14 new compatibility tests, 43 recovery, 9 packed-verifier, 4 terrain/mask packing, 18 upstream door-trip and 81 queue tests pass. Final current-main Windows suite: 882 tests, OK (38 skipped); guard/diff checks pass. Independent Codex QA reproduced both order and uninstall invalidating interrupted main recovery; install/order/uninstall now share the refusal guard. Independent final PASS includes distinct activation snapshots, master recovery and later uninstall retry. Hosted CI at e661977 ran 881 tests and failed solely on the existing #66 Linux filesystem separator lookup; terrain file remains Claude-owned. #84 records inherited final compare/replace/unlink race gaps; no interprocess isolation is claimed. No staging, Plugins.txt, game installation, live input, automation or local-model changes.

## 2026-10-11 Public README and About refresh (Codex)

Owner requested immediate publication of the README and GitHub information. Refreshed the existing #36/#37 work
with Claude's latest pinned evidence, queued runner, offline terrain/NPC research and Codex's #62 recovery tests.
Earlier route results and the newer integration batch remain separate. Added the already-installed Steam launch
command, staging deploy/uninstall examples and eight COC commands checked against PluginSpike's naming and the
staged cell filenames. Reused existing published screenshots; no game outputs or new media added.

GitHub About now links the live #32 status and describes experimental interiors, native physics, queued tests and
terrain research; topics retain existing labels and add terrain/game-conversion. Claude, Codex and Grok attribution
is retained. Main publication uses #37 and its required CI, with protections unchanged. No live game changes.
Validation: 254 synthetic tests OK (1 skipped), guard and diff checks OK; all 18 local README links exist.
QA caught a case-insensitive fallback symlink escaping staging in the existing Linux compatibility change.
The resolver now rechecks containment after every component; a synthetic Linux symlink regression covers both
directory and file requests. It is skipped on Windows because that fallback requires case-sensitive lookup.
Final Windows suite: 255 tests OK (2 skipped); guard and diff checks OK. Linux CI executes the new regression.

## 2026-10-11 Terrain CI preview dependency (Codex)

#64's hosted run38177486495 reproduced ModuleNotFoundError: PIL in the synthetic FO4 plane extractor's preview.
CI installed only NumPy; local testing already had Pillow12.3.0. Added the tested public Pillow release range
to requirements-ci.txt without changing terrain records, scripts or tests. Coordination and file claim: #32/#64.
This fixes the missing dependency, not the unresolved in-game terrain binding. No game assets added.
Validation: main-based255 tests OK (2 Windows skips), guard OK. At #64 head1600603, all11 FO4 LAND synthetic
tests pass with Pillow12.3.0, including the failing end-to-end plane/preview case. Hosted dependency CI pending.


## 2026-10-12 Codex: native-door checkpoints follow rig and clip references
- Reproduced on #79 (612b78e), using its production synthetic two-panel converter: dropping the skeleton from both the saved files list and output hashes allowed reuse after the staged skeleton was removed.
- Inventory now independently follows native DOOR skeleton and Open/Close .af/.afx references; missing, changed or invalid dependencies invalidate reuse. Optional extra outputs remain tracked; template doors keep their existing behavior.
- Preserved reviewed main #34/#35 and staging containment when integrating #79 in a separate Codex worktree. New regressions failed before the fix; seven focused tests and 808 full-suite tests pass (28 skipped, including opt-in sandbox checks). Guard/diff checks pass. No game data, staging, installation or input was touched; runtime multi-part animation remains unverified.
- Independent Claude review passed the initial fix and identified an optional rig-tag omission: generated references are now followed even without that tag. Added omission and vanilla-template compatibility regressions; final independent review passes (including custom prefixes and mixed vanilla/generated references). Hosted Linux CI separately exposed an existing make_exp2c dependency path issue; a four-lookup patch passed POSIX-only synthetic probes and was prepared for the Claude-owned file without editing it.

## 2026-10-12 Codex: small authored door binds are rotations
- Synthetic NIF/controller repro: a0.1-degree leaf bind was classified identity by quaternion w alone, so the native first offset retained0.1 degrees even when the closed pose equalled the bind.
- Identity detection now also checks the vector norm; native preparation shares the predicate. Meaningful small binds get a static parent and identity animated bind; sign-equivalent identity/tiny numerical noise remain supported.
- Five regression tests failed before correction and now pass. Independent matrix evaluation agrees at every Open/Close frame for three axes, small/large binds, translation and both possible bind/offset composition orders. Full813 tests OK (28 skipped), guard/diff checks pass. Independent QA PASS (boundary/sign, nested hierarchy, cross-axis and synthetic converter routing probes); no DLL, game assets, staging, install or input touched. Runtime playback remains unverified.


## 2026-10-12 - Codex: portable terrain dependency filesystem lookups (#66)

Offline tested. The owner says Codex is the only agent currently able to work; the exact dependency_check takeover was announced on #66/#32 before editing. Mesh/NIF, geometry, material and own-texture identifiers carry game-resource backslashes, which Linux treats as literal filename characters. Normalize separators only at the four filesystem lookup boundaries; resource/report names, counts, vanilla membership and terrain/converter behavior remain unchanged.

A synthetic POSIX filesystem regression reproduces both failure modes on Windows: backslash NIF lookup raises FileNotFoundError, and a forward-slash NIF still reports a material missing because its derived lookup contains backslashes. After the fix, both resource separator styles cover missing geometry/own texture/material/NIF, complete coverage and missing/unverified vanilla textures. Existing real-filesystem fixture is retained. 18 focused tests OK (3 skips); full current-main Windows suite 360 tests OK (5 skips), 4.775s; guard/diff checks pass. Linux CI and independent review follow in the PR. No game assets, staging, deployment, game input or automation changed.


## 2026-10-12 - Codex: budget-paused game queues must request resume (#88)

Read-only observation: batch_full stopped at its12-hour run budget with1109 tests pending (655 terminal entries included216 BREAKER skips). Runner.run wrote paused state/report but returned0; the existing required-queue chain treats that as completion, rather than retaining it for a later resume. The exact Runner.run exit-status scope was claimed on #88/#32 under current Codex-only availability.

Change: pending work after a budget pause returns4; completed runs and dry-run previews keep0. A complete run can still contain failed/inconclusive tests. Checkpointing, retries, owner/STOP/idle/Guardian checks and game control are unchanged. Two synthetic budget failures reproduce return0 before the fix; four new tests verify test/time limits, pending-only resume, completed/no-budget and dry-run controls. Four focused and81 existing runner tests pass; full suite/independent QA follow.

Measured prior-result intervals: stairs median85s, floors60s, doors100s. Remaining non-movable work estimates~15 active hours, plus waits/retries; the broken movable lane would add more after corrected re-planning. A separate offline133-test diagnostic artifact retains all16 cells and all49 recorded failures, unchanged source payloads/IDs and the old2470f876 plugin pin; estimated3.14 active hours/~3.92 with25% retry margin. This reduced pass does not replace exhaustive acceptance or verify newly staged assets. Source queue/state, live chain/runner/staging/game and automations were not edited or run.
