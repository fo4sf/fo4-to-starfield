# Fallout 4 creatures on their own rigs and clips (RA5, 23 Nov 2026)

Goal (owner): every Fallout 4 creature moves with its own Fallout 4 animations in Starfield. The Mr. Handy chain
(`robot-animation.md`, in game 23 Nov) is generalised here and run on five creatures: Radroach, Bloatfly, Mole Rat, Dog
and Deathclaw. Nothing below was run in game; everything was measured offline on the installed games.

Code: `src/fo4sf/creature_race.py` (records, clip maps, events, left / right pairs, manifests),
`scripts/actors/convert_creature.py` (rig and mesh), `scripts/probes/stage_ra5_creatures.py` (bundle, checks,
install / uninstall). Tests: `tests/test_creature_race.py`, `tests/test_convert_creature.py`,
`tests/test_stage_ra5_creatures.py`. Bundle (not in Git): `D:\FO4SF-Owner-Tests\robot-anim\RA5`.

## 1. Method (what is shared with the Handy, what is new)

Shared, reused from the Handy code unchanged: the Fallout 4 clip decoder (`hkanim`, `stage_ra2_handy.decode_fo4_clip`),
the rig / clip writer and read-back through CALUMI (`actor_anim`), the skinned mesh writer and its offline verifier
(`actor_skin`), the rest-rotation rebase (`actor_skin.rest_rotation_corrections`, `stage_ra2_handy.rebase_frames`),
turn cropping and left / right mirroring (`stage_ra2_handy.crop_turn`, `mirror_frames`), the vanilla-shaped `.afx`
(`afx_vanilla`), the manifest key and file formats (`handy_race`), the plugin and BA2 writers, the edge-stretch check
and the install / uninstall rules.

New for creatures:

- **COM.** Starfield rigs carry COM (map key 9) and actor meshes hang every bone below `COM_Twin`. Radroach, Bloatfly
  and Mole Rat have none: `convert_creature.insert_com` adds one under Root at the rest position of Root's body child
  (identity rotation) and moves Root's children under it; their poses are re-expressed in COM's frame in every clip
  (`insert_com_frames`, inverse `stage_ra5_creatures.remove_com_frames`). World poses are unchanged (checked, below).
- **Rebase by measurement.** Every bone whose clips move its translation (more than 0.1 mm in any frame of any clip
  used) gets an identity rest rotation, so no translation key depends on the unverified engine rule for a turned bone
  (the Handy chose its five bones by hand).
- **Names.** Prefix stripped (`Dogmeat_Root` -> `Root`), root `Root`, COM `COM`, then letters / digits / `_`.
- **Left / right pairs** by name (one `L` <-> `R` or `Left` <-> `Right` swap) checked against the mirrored rest
  position, with a positional fallback under paired parents (`Weapon` <-> `WeaponLeft`).
- **Root motion with two samples.** The deathclaw stores its extracted motion as 2 samples (start, end); it is
  interpolated to every frame (`resample_root`); `decode_fo4_clip` alone would have dropped it.
- **Events.** Fallout 4 `FootLeft` / `FootRight` keep their names (Starfield's own Hexapod clips use exactly these);
  `FootFront` / `FootBack` (mole rat, dog) become `FootLeft` / `FootRight`; loops get `SyncLeftFoot` / `SyncRightFoot`
  at their first foot frames; turns `SetOrientBegin` / `SetOrientEnd`; deaths `AddRagdollToWorld` +
  `RemoveCharacterControllerFromWorld` at Fallout 4's `Ragdoll` annotation, else at the last frame; getups `GetUpEnd`;
  flinches `FlinchEnd`; melee and fire events as the Handy. Mirrored clips swap the foot events.
- **Race from a template** (`build_creature_race`): every clip folder (DNAM, SAPT) re-pointed at ours, attack bones
  (ZNAM) mapped to our bones, attack entries (ATKD + ATKE + ATKW) whose tag has no clip dropped, sub-graph sets whose
  folders hold none of our clips get our main folder appended (the Mini Bot / Handy Furniture set lists both).
- **Manifests** for the race's own (graph, folders) keys list only clips whose tag the graph plays, measured from the
  vanilla clip lists of every creature race with that graph (`graph_tag_sets`, cached in `work\graph_tags.json`); every
  key is checked against every vanilla manifest name of the four per-sub-graph folders (no collision).
- **Materials**: the real converted look, through the converter Codsworth's materials came from
  (`pipeline.Converter._shape_material`: Fallout 4 BGSM / textures -> Starfield `.mat` + BC1 / BC5 / BC4 DDS with
  texconv), under `materials\fo4sfcreatures\` and `textures\fo4sfcreatures\` in the bundle's own archive.
  `--no-materials` writes the vanilla stand-in `MetalIronCast01.mat` instead (labelled in the report).
- **Test actor**: a copy of `EncMiniBotA01Template` (killable, no template, aggressive) with our race and skin, factions
  dropped, Very Aggressive + Foolhardy (`stage_ra2_handy.copy_npc`), bounds from the mesh.

## 2. Per creature

| | Radroach | Bloatfly | Mole Rat | Dog | Deathclaw |
|---|---|---|---|---|---|
| Fallout 4 race / skeleton | RadRoachRace, 38 bones, no COM | BloatflyRace, 46, no COM | MoleratRace, 39, no COM | ViciousDogRace (Dogmeat skeleton), 65 | DeathclawRace, 86 |
| Rig (bones; rebased) | 40 (COM, DirectAt added); 8 | 48; 3 | 41; 15 | 66 (DirectAt); 25 | 87 (DirectAt); 6 |
| Mesh shapes kept | RadRoach (3,082 v, 34 bones), Wings | Bloatfly (4,034 v, 38 bones) | Molerat (1,798 v), eyes / hairs | ViciousDog (4,500 v, 51 bones) | DeathclawFX body (15,992 v, 75 bones), Eyes, tongue |
| Shapes left out | 3 dismemberment caps | wing FX, 1 effect shape | 2 caps, dirt overlay | 2 caps | 3 caps, Hots, MouthDarkener (effect) |
| Template race (graph) | HexapodARace (Creature_Strafing) | MantaARace (Creature_Flying) | HexapodARace (Creature_Strafing) | QuadrupedCRace (Creature_NonStrafing) | BipedARace (Creature_NonStrafing) |
| Physics (skeleton.nif body) | MiniBotA | MantaA | MiniBotA | QuadrupedC | BipedA |
| Clips written | 51 | 36 | 58 | 42 | 45 |
| Attacks kept / dropped | 6 / 13 | 1 / 20 | 12 / 7 | 6 / 18 | 9 / 15 |
| Attack bones (ZNAM) | C_spine4 -> Head, C_Tail -> RadRoachTail1 | Head, Tail1 | Head, Tail1 | C_Spine5 -> Ribcage, Tail1 | C_Spine2 -> Spine02, Tail1 |
| Form ids (local) RACE..NPC_ | 800-804 | 805-809 | 80A-80E | 80F-813 | 814-818 |
| Batch file | `bat ra5roach` | `bat ra5fly` | `bat ra5rat` | `bat ra5dog` | `bat ra5claw` |

Why each template (Starfield.esm and the animation archive): HexapodARace is a six-legged melee biter on
Creature_Strafing, the graph the Mini Bot and the Handy proved in game, and its own clips carry `FootLeft` / `FootRight`
like Fallout 4's (radroach); the same graph plays `TunnelStart` / `TunnelStop`, which the mole rat's
`TunnelEnter` / `TunnelExit` fill, and its bite / head / 90 / 180 degree attacks cover the mole rat's ten. MantaARace is
the only Creature_Flying race whose clips include `FireSingle_Mouth1` (FlyerA has none), so the bloatfly's spit has a
tag. QuadrupedCRace is the dog-sized quadruped (COM 0.66 m), BipedARace the deathclaw-sized biped (COM 2.0 m against
1.93 m), both biting / clawing races on Creature_NonStrafing.

Clip -> tag maps (full lists in `creature_race.*_CLIPS`; the report lists source, how, events and errors per clip):

- **Radroach**: Idle, 4 idle flavours (clean antennas, look, clean legs, feed), walk / run forward and backward,
  side step (Left, mirrored for right), turns 90 / 180 (left from Fallout 4, right mirrored; 30 = the 90 cropped),
  Attack1-4 -> MeleeAttack01 / 02 / Power01 / Bite01, dodge back, evade left / right, five staggers, HitReaction_Left ->
  Flinch_Torso01 / 02, Death1-3 -> five deaths, GetUp_Left / Back, JunpFall -> fall loop, Aggro_* -> Threat_*.
- **Bloatfly**: Idle + Idle_1-4, its three forward flight loops (all 5.7 m/s), backward, left / right, Soar, turns
  90 / 180 / 30 and TurnLeft / TurnRight, RangedAttack -> FireSingle_Mouth1 and MeleeAttack01 (hit at the spit frame),
  four staggers; no Fallout 4 death clip: deaths are two idle frames with the ragdoll at frame 0.
- **Mole Rat**: Idle, sniff / yawn / stand / dig flavours, Warning1 / 2 -> Threat_*, walk / walk back / run, every turn
  from Fallout 4's own left AND right in-place turns (no mirroring), Attack1-9 on MeleeAttack01 / 02, Bite01 / 02,
  Power01, Power_Bite01, Head01 / 02, Left / Right 90 and 180 (right ones mirrored), evades, staggers, seven critical
  hits, eight deaths, getups left / right, TunnelEnter / Exit.
- **Dog**: idle, head tilt / inspect, growling AttackIdle -> Idle_Taunt01, walk, walk back, trot (jog), run, trot fast
  (sprint), all six in-place turns (Fallout 4 has both sides), Attack1 / 2, power attacks standing and running, four
  staggers, three critical hits, seven deaths, getup left (right mirrored), fall / fall loop / land.
- **Deathclaw**: idle, three special idles, roar / stomp / taunt, walk four ways, run, sprint, run start, turns
  left / right 90 (30 cropped; Fallout 4 has no in-place 180), nine attacks (left, right, power forward, two running
  swipes, horn ram, jump slash, tail combo, spin slash), evades, four staggers, four critical hits, two deaths, two
  getups, jump fall / loop / land.

Graph manifests: one key per (graph, folders) set (Radroach 3, Bloatfly 2, Mole Rat 3, Dog 3, Deathclaw 3); none
collides with a vanilla manifest file. Tags written but not played by the graph (so not listed): Threat_* on
Creature_Strafing; Sprint, WalkLeft / WalkRight and Threat_* on the deathclaw's NonStrafing set; Sprint on the dog's;
Death_Forward / Left / Right01, JogForward and TurnLeft on Creature_Flying.

## 3. Checks (every creature, every clip, every frame)

| | Radroach | Bloatfly | Mole Rat | Dog | Deathclaw |
|---|---|---|---|---|---|
| Rig read back through CALUMI (m / deg) | 6.4e-9 / 4.2e-6 | 6.8e-9 / 4.8e-6 | 1.5e-8 / 4.2e-6 | 2.9e-8 / 3.4e-6 | 5.4e-8 / 4.5e-6 |
| Read-back clip vs written poses (local m, deg, model mm) | 1.7e-4, 0.057, 0.59 | 1.7e-4, 0.009, 0.42 | 1.7e-4, 0.054, 1.19 | 1.7e-4, 0.054, 0.61 | 1.7e-4, 1.35, 4.66 |
| Read-back clip vs decoded Fallout 4 clip (model mm) | 0.59 | 0.42 | 1.19 | 0.61 | 4.66 |
| Rig poses vs source poses, world (m) | 1.1e-15 | 1.8e-15 | 1.8e-15 | 3.6e-15 | 5.4e-15 |
| Translation-rule exposure (m) | 7.5e-4 (mirrored clips) | 2.7e-6 | 7.5e-5 | 1.9e-6 | 9.3e-5 |
| Mesh bind error (mm) | 0.019 | 0.014 | 0.032 | 0.026 | 0.096 |
| Worst edge stretch (clip, bones) | 29.1x meleeattack01, Head / RMandible | 2.39x, Tail3 | 4.45x, Front_RLeg2 / Chest | 12.9x runforward, Front_LLeg1 | 4.02x, NeckRoot / RUpperarmTwist1 |
| Clips at or over 1.6x | 51 / 51 | 36 / 36 | 58 / 58 | 41 / 42 | 45 / 45 |
| Fallout 4's own skinning, same frames: max difference (abs, rel) | 0.094, 0.45 % | 0.0016, 0.08 % | 0.0047, 0.18 % | 0.028, 0.41 % | 0.013, 0.42 % |
| Same over-limit clip set as Fallout 4's own skinning | yes | yes | yes | yes | yes |
| Rigid pieces (one bone, full weight) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

The stretch is Fallout 4's: skinning the Fallout 4 shapes with their own stored positions, skin-to-bone transforms and
weights on the decoded clips gives the same worst ratio per frame within the figures above, in every clip. The
radroach's 16.8x in every clip is a 4 mm triangle between Head and a mandible that Fallout 4's clips hold 6 cm apart
(16.8x in Fallout 4 too). The deathclaw's 1.35 deg / 4.7 mm is one LFoot key in Death_Backward01 near a 180 degree
offset, where the format rebuilds w from x, y, z (starfield-actor-anim-format.md, "Quantisation").

Bundle checks (`verify`): every loose file byte-equal inside the BA2 (580 entries, Archive2), entry hashes, plugin
masters (Starfield.esm only), the 25 records and every reference inside the plugin, record paths present in the archive,
bone names letters / digits / `_` in the rig, the NIFs, the BPTD and ZNAM, rig keys Root / COM / DirectAt, every clip's
header and read-back frame count, the batch-file rule. `deform` recomputes the stretch from the staged files.

## 4. Not proven (needs the game)

1. That a template race's graph plays a converted rig's clips. Proven only for Creature_Strafing with the Handy (Mini
   Bot graph). Radroach and Mole Rat use Creature_Strafing (HexapodA template); Bloatfly uses Creature_Flying (MantaA),
   Dog and Deathclaw Creature_NonStrafing (QuadrupedC, BipedA): those graphs have never run a converted rig.
2. The character controller: each skeleton.nif copies the physics template's controller and COM body byte for byte
   (Radroach and Mole Rat: the Mini Bot's, which the Handy ran with; Bloatfly Manta, Dog QuadrupedC, Deathclaw BipedA).
   Its size against the creature is not checked.
3. Whether the race still fights with the attack entries we dropped, and whether attacks hit: the attack weapons
   (ATKW) and the hit bones (ZNAM, mapped to Head / Spine / Ribcage / Tail1) are the template's.
4. The bloatfly: its only attack is the spit; MeleeAttack01 is that clip with the hit at the fire frame, and
   FireSingle_Mouth1 needs a ranged weapon the test NPC does not carry. Its deaths are two idle frames with the
   ragdoll at frame 0 (Fallout 4 has no bloatfly death clip). Whether the Manta's flight keeps it in the air with
   Fallout 4's hover clips is unknown.
5. The test NPC copies the Mini Bot encounter template: its class, combat style, keywords and inventory are a robot's.
6. Tags the graphs do not list (Threat_* on Creature_Strafing) are written but not in the manifests; whether a tag
   with no clip (departures, LookDirections, Knockdown) stalls a graph is unknown (it did not for the Handy).
7. Rig map keys are Root / COM / DirectAt only (the Handy's); vanilla creatures also key spine, head and leg bones
   (look-at, foot IK). Bone names starting with a digit (radroach `1LLeg1`) are kept: no vanilla rig has one.
8. Everything `robot-animation.md` section 6 lists (manifests needed at all, stance data, offsets events).

## 5. In-game test asked for (not run by this lane)

With Starfield closed: `python scripts/probes/stage_ra5_creatures.py install --starfield <game dir>` (verifies the
bundle, copies the plugin and archive, appends the plugin to Plugins.txt with a backup, writes `ra5*.txt` stamped with
the real load-order slot, writes a receipt; refuses to overwrite anything). In game, in an open test area with god mode:
`bat ra5roach`, then `ra5rat`, `ra5dog`, `ra5claw`, `ra5fly`, one at a time. For each: does it stand on the ground at
its size with the Fallout 4 texture; idle and idle flavours; walk / run / turn toward the player; attack (and does the
player take damage); stagger when hit; die (death clip, then ragdoll) and stay dead. Bloatfly: does it stay in the
air. Afterwards `uninstall --starfield <game dir>` (restores Plugins.txt byte for byte, removes only unchanged files).

Shared modules: `hkanim`, `actor_anim`, `actor_skin`, `handy_race` and `stage_ra2_handy` are unchanged; the creature
code only imports them.
