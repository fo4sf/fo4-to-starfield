# Human animation: Fallout 4 clips on Starfield's human rig (human-animation lane, 23 Nov 2026)

Goal: converted humans (raiders, Preston, settlers) move with Fallout 4's own animations while they stay on Starfield's
HumanRace (faces, outfits, dialogue, AI), and later the player's first-person gun animations (10mm first). Mr. Handy
works with his own Fallout 4 skeleton on a race of his own (robot-animation.md); humans cannot do that, so Fallout 4
clips are retargeted onto Starfield's human rig.

Code: `src/fo4sf/human_retarget.py` (retarget, checks, manifests), `scripts/probes/stage_ra4_human.py` (probe bundle);
tests: `tests/test_human_retarget.py`. Generated data (never in Git): `D:\FO4SF-Owner-Tests\robot-anim\RA4\`
(`report.json` has every number below, `REPORT.md` the SHA-256 table).

Marks: **[measured]** = read from the installed game files with the repository's readers and reproducible with the
code; **[proposal]**; **[not proven]** = needs the game.

## 1. The two skeletons [measured]

| | Fallout 4 | Starfield |
|---|---|---|
| file | `meshes\actors\character\characterassets\skeleton.hkx` (`Fallout4 - Animations.ba2`) | `meshes\actors\human\characterassets\skeleton.rig` (`Starfield - Animations.ba2`; a female rig sits under `female\`) |
| bones | 95 (plus an 18-bone ragdoll skeleton in the same file) | 97; precision `default` |
| bones a clip addresses | 95 tracks | 82: all 468 full (kind 2) clips in a random 600 of the 13,766 human clips say 82 (partial layouts other counts); the 15 twist bones (map keys 142..156: thigh, biceps, wrist, neck twists) are the rig's last 15 and are never in a clip (`clip_bones`) |
| names in common | 8: Root, COM, Weapon, WeaponLeft, Camera, Camera Control, AnimObjectA, AnimObjectB | |
| hip-joint height / leg length / ankle height | 0.984 / 0.908 / 0.087 m | 0.942 / 0.835 / 0.115 m |
| spine | COM, Spine1, Spine2, Chest, Neck, Head | COM, C_Spine, C_Spine1, C_Spine2, C_Chest, C_Neck, C_Neck1, C_Head (two more joints) |
| gun | `Weapon` under `RArm_Hand` | `Weapon` under `C_Chest`; `R_HandIk` / `L_HandIk` under `Weapon` (hand IK targets) |

Both are Z up, +Y forward, +X right (Fallout 4 walkforward root motion +Y 113.9 units; Starfield relaxed_walkforward
Root +1.59 m on +Y), 30 fps, units x 1/70 = metres.

Bone-local axes differ and so do the rest poses, so local rotations cannot be copied. The angle between the two rest
world rotations of mapped bones once their anatomy is matched (`rest_anatomical_offsets_deg`): COM 90, C_Hips 180,
spine 1.6 to 9.6, every left limb bone 172 to 179 (mirrored axes), right limb bones 0.6 to 7.9, hands 86 / 94, fingers
62 to 119 deg.

## 2. How Starfield composes a human clip [measured]

A clip key is an offset from the rig bind. On the human rig **rotations compose as q = q_bind q_offset and
translations as t = t_bind + t_offset (not rotated by the bind rotation)**. Evidence: in vanilla
`melee\unarmed\relaxed_idle`, `relaxed_walkforward` and `gun\grippistol\ready_idle`, R_HandIk and L_HandIk (children
of the rotated `Weapon` bone) sit on the wrists within 0.2 to 0.4 mm and the pistol 7 to 9 cm from the right wrist
with that rule; with the rotated rule that `actor_anim.offset_to_local` uses they are 0.61 to 0.86 m away. The rotation
rule is the same in both (the IK bones match the wrists' rotation within 0.01 to 0.19 deg). `actor_anim` is not
changed (the Handy rebases every translated bone to an identity rest, where both rules agree);
`human_retarget.offsets_from_local` / `local_from_offsets` implement the measured rule.

## 3. Method

1. **Anatomical frames.** Each mapped bone gets, in each skeleton, a frame from rest-pose landmarks held rigidly by the
   bone: primary axis = the bone towards its next joint; secondary = the elbow plane (upper arm, forearm), the palm
   (hand: index base to pinky base; thumb: palm normal), world forward (thighs, calves, clavicles), world up (feet),
   or the world frame itself (COM, hips, spine, neck, head, toes: the world rotation change from rest is copied).
   C = W_rest^-1 F_rest per bone. Per frame: W_sf = W_fo4 C_fo4 C_sf^-1. Map (`BODY_MAP`): COM<-COM, C_Hips<-Pelvis,
   C_Spine<-Spine1, C_Spine1<-slerp(Spine1, Spine2), C_Spine2<-Spine2, C_Chest<-Chest, C_Neck<-Neck,
   C_Neck1<-slerp(Neck, Head), C_Head<-Head, *_Thigh/Calf/Foot/Toe <- *Leg_Thigh/Calf/Foot/Toe1, *_Clavicle <-
   *Arm_Collarbone, *_Biceps <- *Arm_UpperArm, *_Forearm <- *Arm_ForeArm1, *_Wrist <- *Arm_Hand (Fallout 4's
   ForeArm2/3 twist ends up in the wrist), fingers 1:1 (thumb/index/middle/ring/pinky <- Finger1x..5x). Unmapped:
   L/R_Cup (vanilla constant), twist bones (not in clips).
2. **Hips and root.** k = Starfield hip height / Fallout 4 hip height = 0.9568. COM is placed so that the hip-joint
   centre is k x Fallout 4's (in the root's frame); root motion (FO4 reference frame x, y, z, yaw) is scaled by k.
3. **Legs.** Starfield's legs are shorter for its hip height and its ankle joint sits 2.8 cm higher, so plain FK slides
   planted feet (walk 5 to 8 mm per frame, jog 10 to 11, run 16 = 0.47 m/s). Two-bone IK puts each ankle at k x the
   Fallout 4 ankle (height re-based on each rig's own rest ankle height, sideways spacing kept relative to the hips)
   while the Fallout 4 ankle is within 3 cm of its rest height, blending to plain FK by 10 cm (swing phase keeps
   Fallout 4's leg motion).
4. **Gun clips** (`hold_weapon`). Both games' Weapon bones point the barrel along local +Y, up +Z (FO4 pistol ready
   idle and Starfield grippistol ready_idle: weapon world rotation within 2 deg of the identity). The gun takes
   Fallout 4's world rotation, sits at Starfield chest + k x (FO4 gun - FO4 chest); the right wrist goes on the grip with
   Starfield's own hand-to-gun transform (from vanilla `gun\grippistol\ready_idle` frame 0: t (0.062, 0.021, -0.018) m);
   the left wrist where Fallout 4 holds its left hand relative to the gun (unscaled); both arms by two-bone IK.
   Without this the barrels differ by 9.9 deg (the two games grip differently).
5. **Other bones.** DirectAt keeps a world rotation equal to the root's (vanilla: identity within 0.08 deg in all
   three clips checked); R_HandIk / L_HandIk on the wrists (so a graph that runs hand IK changes nothing); Weapon,
   WeaponLeft, C_Waist, L/R_Arm, L/R_Cup, CameraTarget, Camera keep the shadowed vanilla clip's frame-0 value; Camera
   Control and Camera Control FP cancel the root motion (vanilla: their translation is minus the Root's).
6. **Events.** Measured on Starfield's walk, jog and run: FootLeft / FootRight sit at the foot strike, the foley 3
   frames before it, Sync<Side>Foot about mid-stance. Fallout 4 annotates FootLeft and SyncLeft on the same strike
   frame. Rule used: FootX = Fallout 4's own annotation frame; SyncXFoot = the frame where the foot passes under the
   hip centre + 0.07 of the cycle (reproduces Starfield's own six sync frames within 1 frame); foley = FootX - 3.
   tag, prefix, rampout and is_state come from the shadowed vanilla .afx.
7. **Writing.** CALUMI writes each clip against the 82-bone prefix of the rig (header bone count 82 as vanilla), precision
   default; read back with the full 97-bone rig and composed with the measured rule.

## 4. Numbers (RA4 build, read back through the DLL, every frame) [measured]

Clips: Fallout 4 `mt\neutral\posea_idle1` (134 frames), `walkforward` (38), `jogforward` (23), `runforward` (20),
`weapon\pistol\wpnidleready` (401). Metrics per chain, max / mean over frames and joints:
- direction: angle between the bone segments of the two skeletons (proportion-free);
- motion: each joint's movement from frame 0 against k x Fallout 4's;
- position: joint position against k x Fallout 4's in the root frame (includes the rigs' different proportions:
  Starfield's hips-to-neck is 6.2 cm shorter after scaling, its shoulders 2.3 cm lower, shoulder width and finger
  lengths differ; the hands end up about 15 cm from k x Fallout 4's);
- stance slide: horizontal foot movement against k x Fallout 4's while the Fallout 4 foot is planted.

| clip | chain | direction deg | motion m | position m | stance slide m (max) |
|---|---|---|---|---|---|
| posea_idle1 | spine | 2.68 / 2.64 | 0.001 / 0.000 | 0.019 / 0.009 | |
| posea_idle1 | head | 7.34 / 7.20 | 0.005 / 0.002 | 0.073 / 0.053 | |
| posea_idle1 | L / R arm | 0.03 / 0.01 | 0.004 / 0.002 | 0.167 / 0.155 | |
| posea_idle1 | L / R fingers | 0.03 / 0.02 | 0.004 / 0.002 | 0.148 / 0.142 | |
| posea_idle1 | L / R leg | 2.39 / 0.90 | 0.007 / 0.001 | 0.043 / 0.040 | 0.0003 |
| walkforward | spine | 1.84 / 1.69 | 0.004 / 0.001 | 0.023 / 0.011 | |
| walkforward | head | 6.41 / 6.20 | 0.005 / 0.002 | 0.073 / 0.054 | |
| walkforward | L / R arm | 0.02 / 0.01 | 0.011 / 0.006 | 0.168 / 0.155 | |
| walkforward | L / R fingers | 0.03 / 0.01 | 0.022 / 0.009 | 0.154 / 0.143 | |
| walkforward | L / R leg | 6.91 / 1.10 | 0.057 / 0.029 | 0.070 / 0.044 | 0.0017 |
| jogforward | spine | 1.21 / 0.87 | 0.008 / 0.002 | 0.030 / 0.014 | |
| jogforward | head | 8.23 / 8.13 | 0.011 / 0.006 | 0.076 / 0.054 | |
| jogforward | L / R arm | 0.02 / 0.01 | 0.037 / 0.016 | 0.173 / 0.160 | |
| jogforward | L / R fingers | 0.02 / 0.01 | 0.052 / 0.025 | 0.183 / 0.169 | |
| jogforward | L / R leg | 4.00 / 0.67 | 0.086 / 0.027 | 0.078 / 0.049 | 0.0003 |
| runforward | spine | 1.20 / 0.75 | 0.005 / 0.001 | 0.032 / 0.015 | |
| runforward | head | 10.74 / 9.64 | 0.017 / 0.009 | 0.075 / 0.052 | |
| runforward | L / R arm | 0.02 / 0.01 | 0.034 / 0.016 | 0.173 / 0.160 | |
| runforward | L / R fingers | 0.02 / 0.01 | 0.055 / 0.027 | 0.188 / 0.171 | |
| runforward | L / R leg | 5.04 / 0.89 | 0.104 / 0.035 | 0.087 / 0.052 | 0.0006 |
| wpnidleready | spine | 0.66 / 0.58 | 0.001 / 0.000 | 0.038 / 0.018 | |
| wpnidleready | head | 11.94 / 11.77 | 0.002 / 0.001 | 0.078 / 0.054 | |
| wpnidleready | L / R arm | 28.69 / 12.69 | 0.006 / 0.002 | 0.151 / 0.104 | |
| wpnidleready | R fingers | 12.50 / 11.32 | 0.001 / 0.000 | 0.041 / 0.034 | |
| wpnidleready | L / R leg | 4.25 / 2.51 | 0.001 / 0.000 | 0.051 / 0.045 | 0.0004 |

L / R rows give the worse side. Every single-bone anatomical frame matches Fallout 4's within 0.04 deg except the
IK-solved legs (up to 6.9 deg) and the gun clip's arms (IK, up to 28.7 deg) and right hand (Starfield's grip, 14 deg);
spine and head "direction" is the rest-curvature difference of the two rigs (their orientations are copied).
Gun clip: barrel 0.02 deg from Fallout 4's, gun position relative to the chest within 0.3 mm of k x Fallout 4's,
left-wrist-to-gun distance within 0.2 mm of Fallout 4's, arm IK always reached.
Speeds (k-scaled root motion): walk 1.26, jog 3.08, run 5.10 m/s (Starfield's own: 1.49, 2.64, 5.03).
Read-back against the poses written (quantisation): at most 0.27 mm local translation, 0.08 deg, 0.61 mm in model space.

## 5. In-game route

### What HumanRace holds [measured]

- HumanRace `0000347D`: 2,074 subrecords, **158 sub-graph rows, 695 SAPT folder entries**. A row is `SAKD`* (actor
  keywords) `STKD`* (target keywords: the weapon's or furniture's) `SGNM` (graph) `SAPT`+ (clip folders, first wins)
  `SRAF`. By graph: 48 movement rows (NPC / Player / 1stPerson MT with their ZeroG graphs, Inventory, CharGen), 34
  weapon rows (melee and gun), 76 furniture rows. The default NPC MT row (no keywords, SRAF 5) uses
  `melee\unarmed`, `melee\common`, `common`;
  `generatedsubgraphdata\humanrace.txt` expands them to **1,607 rows** (868 weapon 3rd, 551 furniture 3rd, 148 weapon
  1st, 36 MT 3rd, 4 furniture 1st) over 569 distinct folders by adding the `female`, `player`, `pirate`, `armorbulky`
  subfolders and ZeroG graphs. Each row has a manifest key (`handy_race.manifest_key`) and four files.
- Actor keywords choose a style: `AnimArchetype*` keywords on NPC_ records (KWDA: Pirate 108 NPCs, Confident 100,
  Friendly 64, Executive 29 ...) select rows whose first folder is a subfolder (`melee\unarmed\angry`, ...).
- **Override rule.** A row's clip list (`animationfiledata`) is the default row's list with every file whose name
  (case ignored) exists in the earlier folder replaced by that file: AnimArchetypeAngry's list equals, as a set, the
  default NPC MT list with its five same-named files (relaxed_additivepose, relaxed_walkforward, _start,
  _stop_leftfoot, _stop_rightfoot) swapped in. Its `animationoffsets` and `dynamicidledata` are byte-identical to the
  default row's. The list order is the graph's, not sorted.
- `animationstancedata` holds model-space bone transforms (w, x, y, z quaternion, translation, rig index) in 8 blocks;
  they match frames of `ready_idle`, `sneak_idle`, `covercrouching_idle` and `coverstanding_idle` within 2.6 to 20 mm
  (reference poses per stance, not of the relaxed clips RA4 replaces).
- Starfield's own add-on SFBGS003 adds its plasma cutter without touching vanilla: KYWD `AnimSFBGS003_PlasmaCutter`
  on the weapon, a RACE `SFBGS003_HumanRace` (590 subrecords: HumanRace's head, morph and body data, `SADD 0000347D`)
  with 5 rows gated by that target keyword, its clips under `Actors\SFBGS003\Human\...` first and the vanilla grip
  folders after them, `generatedsubgraphdata\sfbgs003_humanrace.txt` (14 rows) and 19 per-key manifest sets.

### Options and their cost

| option | records | data | what it breaks | verdict |
|---|---|---|---|---|
| **(a) add-on race + actor keyword** (SFBGS003's pattern with an actor keyword like the AnimArchetype rows) | 1 KYWD, 1 RACE (template copy, rows replaced), the keyword on each converted NPC | per row: clips that differ + 4 manifests (3 copied from the vanilla row) + 1 gsd line. MT only: 1 row (male, clothes), about 4 with Female / ArmorBulky / ZeroG; per weapon grip 1 to 4 more (Angry: 8 rows; Pirate, a full style: 429) | nothing: NPCs without the keyword keep every vanilla row | **recommended** |
| (b) copy of HumanRace with its own folders | 1 RACE of 2,074 subrecords; 586 of 1,106 ARMA list HumanRace and `HeadPartsHumanRace` lists head parts: each outfit, skin and head part the copy wears needs an override | the copy's manifests | every `GetIsRace HumanRace` condition, the race's dialogue / faction / crime checks, outfits and heads until patched | test only; costly and fragile |
| (c) override HumanRace's default NPC MT row | 1 RACE override (2,074 subrecords) | same 4 manifests as (a) | every human NPC (the player keeps its Player rows) | diagnostic only: proves clip loading if (a)'s row is not picked |

Route (a) for real use: one keyword `AnimArchetypeFO4`-style per Fallout 4 animation style (FO4's own `mt\neutral`,
`confident`, `irritated`, `nervous` ... folders map naturally to archetypes), given to converted NPCs through their
NPC_ keywords (or their templates); weapon rows add a weapon keyword (as SFBGS003) or the actor keyword plus the grip
keyword.

### Probe RA4 [built, not run]

`D:\FO4SF-Owner-Tests\robot-anim\RA4` (`stage_ra4_human.py build`):

| record (local id) | what |
|---|---|
| `01000800` KYWD `FO4SF_AnimArchetypeFO4` | copy of AnimArchetypeAngry (type 7) |
| `01000801` RACE `FO4SF_RA4HumanAddRace` | SFBGS003_HumanRace copy, `SADD 0000347D`, one row: SAKD 01000800, `NPC_MT_Wrapping.agx`, folders `Actors\FO4SF\Human\Animations\Melee\Unarmed`, then the default NPC MT row's three, SRAF 0 (as HumanRace's Angry / Macho rows) |
| `01000802` NPC_ `FO4 Clip Test` | FC_Clinic_GennadyAyton `0014A813` (male HumanRace, no template, no script) with the keyword, no factions, Unaggressive, package `defaultFollowPlayerPKG` `00021E76` |
| `01000803` NPC_ `Starfield Clip Test` | the same without the keyword (control) |

Clips in the archive: relaxed_idle, relaxed_walkforward, jogforward, runforward (replacing the four same-named
vanilla files for this row only); manifests under key 8914403262593618420 (default NPC MT key 5584118799897580020) and
`generatedsubgraphdata\fo4sf_ra4humanaddrace.txt`. The pistol ready idle is written to `work\pistol` only (no gun row).
SHA-256s: `RA4\REPORT.md` and `manifest.json`.

In-game steps (owner's machine, test save, god mode): `stage_ra4_human.py install --starfield <game dir>`, start the
game, `bat ra4ac` (spawns both NPCs; `ra4a` / `ra4c` one each), watch them idle side by side, then walk, jog and run
away: both follow. Expected: `FO4 Clip Test` stands in Fallout 4's neutral idle and walks / jogs / runs with Fallout
4's gait; `Starfield Clip Test` moves as vanilla. Look for: feet planted while standing and walking, no sinking or
floating (ankle height 2.8 cm different between rigs, compensated), hands and fingers, head facing forward,
transitions into the vanilla start / stop / turn clips. Then `uninstall`. Readings: both vanilla = the add-on row is
not picked or its manifests are not read (next: option (c) for one session); FO4 NPC with Fallout 4 motion = route (a)
proven for MT.

## 6. First-person gun clips (10mm): plan [proposal]

1. Rigs: Starfield `meshes\actors\human\_1stperson\characterassets\skeleton.rig` (87 bones, 76 in clips, no legs,
   precision first_person, Weapon under C_Chest with R/L_HandIk, L/R_Elbow helpers, C_BackPack); Fallout 4
   `_1stperson\characterassets\skeleton.hkx` (94 bones, Weapon under RArm_Hand with WeaponBolt / Magazine / Trigger part
   bones). The body map above applies to arms, hands, fingers, spine and head.
2. Retarget in camera space, not body space: place the gun relative to Starfield's Camera as Fallout 4 has it
   relative to its Camera (sight line on the view axis), then `hold_weapon`'s grip and two-arm IK.
3. The 10mm uses Fallout 4's `_1stperson\animations\pistol` set (50 clips: equip, idle ready / sighted, fire single
   ready / sighted, reload, run, sprint, plus additive pitch / turn / jiggle clips); Starfield's
   `_1stperson\animations\gun\grippistol` has the matching tags (equip, idle, sighted_idle, firesingle,
   sighted_firesingle, reload, runforward, pitchup / down, jiggle*). Additive (`*Add.hkx`) clips need an additive
   writer or baking onto the idle (not built).
4. Gun parts: Fallout 4 moves slide, magazine and trigger in the same clip; Starfield plays them as separate `gun_*.af`
   clips (gun_reload, gun_firesingle ...) on the weapon's own rig, so the converted 10mm needs a weapon rig and those
   clips cut from the Fallout 4 part-bone tracks.
5. Routing: SFBGS003's five-row pattern exactly (1stPerson_Gun + ZeroG, Player_Gun, NPC_Gun, gated by a weapon keyword
   on the 10mm WEAP), our folders first, grippistol folders after.
6. Checks: barrel along the camera forward axis in sighted clips, hands on the gun, per frame; then the owner's look
   test.

## 7. Not proven (to settle in game)

1. That an add-on race's actor-keyword MT row is picked over HumanRace's default row (vanilla proves add-on weapon
   rows and in-record archetype rows; this combination is untested), and that SRAF 0 is the right value for it.
2. That the game reads the plugin's own manifests from its archive for the new key (the Mini Bot own-folder probe
   shipped manifests and worked, but whether they were needed was not separated); copying the default row's
   offsets, stance and dynamic idle data is correct for Angry, assumed for ours.
3. Translation offsets on the human rig follow t_bind + t_offset (strong offline evidence, untested in motion).
4. Event placement (Sync frames fitted on vanilla within 1 frame), clip speeds against the graph's speed control,
   blends between Fallout 4 loops and vanilla start / stop / turn clips.
5. The female rig (not handled: the probe NPC is male; female NPCs need `female` rows and the female rig).
6. Twist bones are driven by the engine (vanilla clips never key them).
7. The pistol clip is offline only; the gun-space hold assumes the hand IK targets are honoured by NPC_Gun.
