# Robot animation: Handy race, graph tags, clip mapping and manifests (task D, 23 Nov 2026)

Goal: Mr. Handy (Codsworth, every Mr. Gutsy) moves with his own Fallout 4 clips in Starfield. This note covers the race
side: which tags Starfield's generic creature graph asks for, which Fallout 4 clip fills each, the RACE/BPTD records and
the animation manifests. Code: `src/fo4sf/handy_race.py`; tests: `tests/test_handy_race.py`; generated data (never in
git): `D:\FO4SF-Owner-Tests\robot-anim\D\`.

Each statement is marked **[measured]** (read from the installed game files with the repo's readers, reproducible with
the code) or **[proposal]** / **[not proven]**.

## 1. What the Mini Bot race uses [measured]

MiniBotARace `00227705` (full dump: `D:\FO4SF-Owner-Tests\robot-anim\D\minibot_records.txt`):

| field | value |
|---|---|
| ANAM | `Actors\minibota\CharacterAssets\skeleton.nif` |
| NAM5 (rig) | `actors\minibota\characterassets\skeleton.rig` |
| NAM6 (root graph) | `AnimTextData\Tables\Graphs\Creature_Root.agx` |
| DNAM (clip folder) | `Actors\MiniBotA\Animations` |
| SGNM / SAPT / SRAF | `Creature_Strafing.agx` / `Actors\MiniBotA\Animations` / 1; `Furniture.agx` / `Actors\MiniBotA\Animations\Furniture`, `Actors\MiniBotA\Animations` / 7 |
| GNAM | MiniBotABodyPartData `00227704` |
| ZNAM (x3, after QNAM) | `C_Chassis` |
| FULL, DESC, SNAM | localized string ids 0x1ED1, 0x1ECF, 0x1ED0 (consecutive: SNAM is a localized string too) |
| ATKD/ATKE | 19 attack entries (MeleeAttack01/02, _Claw01/02, _Head01/02, _Bite01/02, _Tail01/02, power variants, _Left/Right90/180) |
| WED0/WED1 | 40 bytes each, not path hashes (tested), kept |

MiniBotABodyPartData: six parts C_Chassis, C_Base (ENAM C_Base, FNAM C_Axle), C_Arm1, C_Body, COM, Root; part names
(BPTN) are localized ids; NAM4/ENAM/FNAM otherwise hold `BASE Meshes\Actors\minibota\CharacterAssets\skeleton_ref.nif`.

Creature_Root.agx only references `ActorStateController` and carries the tags FurnitureDeath/None. Every clip tag the
Mini Bot plays comes from the sub-graphs. The graph XML names a clip through an `NT_ANIMATION_NODE` property `TagName`;
graphs with `Enumerate Tag = True` (Creature_Deaths, Creature_IdleTurning, Creature_Strafing_Pathing, IdleBack, IdleFace,
NPC_IdleFlavor, Furniture) build tags from their state names (Death_Backward01, Idle_Flavor01, WalkDeparture_Left90...),
so the full list below combines (a) every `TagName` reached through `Graph Ref` nodes and (b) every .afx tag in the
folders of the six races that use Creature_Strafing (CCT_Dummy, HexapodA, MantidA, MiniBotA, OctopedeA, Terrormorph).

### 1a. TagName values per sub-graph (walked from the race's graphs) [measured]

**creature_root** (sub-graphs: ActorStateController)
- creature_root: FurnitureDeath

**creature_strafing** (sub-graphs: Creature_Actions, Creature_BleedOut, Creature_CriticalHits, Creature_Deaths, Creature_Dodges, Creature_EquipUnequip, Creature_Flinches, Creature_Graze, Creature_Hide, Creature_IdleTurning, Creature_Knockdowns, Creature_LimbCripple, Creature_Melee, Creature_Staggers, Creature_Strafing_IdleLocomotion, Creature_Strafing_Pathing, DirectAt, DirectAt_Tail, IdleBack, IdleFace, LookAt, NPC_Jumping, SprintEvents, Tunneling)
- Creature_Actions: FireSingle_Mouth1, FireSingle_Mouth2, FireSingle_Tail
- Creature_BleedOut: Idle, RunForward, Start, Stop, TurnInPlace_Left180, TurnInPlace_Left90, TurnInPlace_Right180, TurnInPlace_Right90, WalkForward
- Creature_Dodges: DodgeBack, DodgeLeft, DodgeRight, EvadeLeft, EvadeRight
- Creature_Graze: Idle, Start, Stop
- Creature_Hide: Idle, Start, Stop
- Creature_IdleTurning: Idle, TurnInPlace_Left180, TurnInPlace_Left30, TurnInPlace_Left90, TurnInPlace_Right180, TurnInPlace_Right30, TurnInPlace_Right90
- Creature_Melee: CastSelf, CastTarget, MeleeAttack01, MeleeAttack02, MeleeAttackPower01, MeleeAttackPower_Bite01, MeleeAttackPower_Bite02, MeleeAttackPower_Claw01, MeleeAttackPower_Head01, MeleeAttackPower_Tail01, MeleeAttack_Bite01, MeleeAttack_Bite02, MeleeAttack_Bite03, MeleeAttack_Claw01, MeleeAttack_Claw02, MeleeAttack_Head01, MeleeAttack_Head02, MeleeAttack_Head03, MeleeAttack_Left180, MeleeAttack_Left90, MeleeAttack_Right180, MeleeAttack_Right90, MeleeAttack_Tail01, MeleeAttack_Tail02
- Creature_Strafing_IdleLocomotion: JogBackward, JogForward, JogLeft, JogRight, RunBackward, RunForward, RunLeft, RunRight, Sprint, WalkBackward, WalkForward, WalkLeft, WalkRight
- DirectAt: LookDirections
- DirectAt_Tail: LookDirections_Tail
- IdleBack: IdleBack
- IdleFace: IdleFace
- LookAt: LookDirections
- NPC_Jumping: JumpInPlaceLand, JumpRunForward, JumpRunForwardBoost, JumpRunForwardFall, JumpRunForwardFallLoop, JumpRunLand, JumpTraversal
- Tunneling: TunnelStart, TunnelStop
- creature_strafing: Tail_BoneWeights, UpperBody_BoneWeights

**furniture** (sub-graphs: GunActions, NPC_IdleFlavor)
- GunActions: BoltCharge, CastSelf, CastTarget, ChargeDown, ChargeHold, ChargeUp, Equip, FireAuto, FireAutoPush, FireSingle, FireSingleBinary, GunDown, MeleeAttackBash, Reload, ReloadEnd, ThrowGrenade, ThrowMine, Unequip
- furniture: Activate, EnterFromStand, EnterInstant, ExitToDead, ExitToStand, FrontEnterFromStand, FrontEnterFromWalk, FrontExitToRun, FrontExitToStand, FrontExitToWalk, GravJumpInitiate, Idle, LeftEnterFromStand, LeftEnterFromWalk, LeftExitToRun, LeftExitToStand, LeftExitToWalk, LeftQuickExitToStand, PoseBToPoseA, QuickExitToStand, RearEnterFromStand, RearEnterFromWalk, RearExitToRun, RearExitToStand, RearExitToWalk, RearQuickExitToStand, RightEnterFromStand, RightEnterFromWalk, RightExitToRun, RightExitToStand, RightExitToWalk, RightQuickExitToStand, Sit_Start, Stand_Start, Start


### 1b. All tags the Creature_Strafing races ship clips for (208) [measured]

CastTarget, CriticalHit, CriticalHit_Arms, CriticalHit_Head01, CriticalHit_Head02, CriticalHit_LeftArm, CriticalHit_LeftLeg, CriticalHit_Legs, CriticalHit_RightArm, CriticalHit_RightLeg, CriticalHit_Torso, CriticalHit_Torso01, CriticalHit_Torso02, Death, Death_Backward01, Death_Backward02, Death_Backward03, Death_Backward04, Death_Backward05, Death_Backward06, Death_Forward01, Death_Forward02, Death_Forward03, Death_Forward04, Death_Forward05, Death_Forward06, Death_Left01, Death_Left02, Death_Left03, Death_Moving_Forward01, Death_Moving_Forward02, Death_Right01, Death_Right02, Death_Right03, Diversion, Diversion01, DodgeBack, DodgeLeft, DodgeRight, EvadeLeft, EvadeRight, FireSingle_Mouth1, FireSingle_Mouth2, FireSingle_Tail, Flinch_Head01, Flinch_Head02, Flinch_LeftArm, Flinch_LeftArm2, Flinch_LeftLeg, Flinch_RightArm, Flinch_RightArm2, Flinch_RightLeg, Flinch_Torso01, Flinch_Torso02, GetUp_Back, GetUp_Front, GetUp_Left, GetUp_Right, Idle, Idle02, IdleBack, IdleBack_Flavor01, IdleBack_Flavor02, IdleBack_Flavor03, IdleBack_Flavor04, IdleBack_Flavor05, IdleBack_Flavor06, IdleBack_Flavor07, IdleBack_Flavor08, IdleBack_Flavor09, IdleBack_Flavor10, IdleBack_Flavor11, IdleBack_Flavor12, IdleFace, IdleFace_Flavor01, IdleFace_Flavor02, IdleFace_Flavor03, IdleFace_Flavor04, IdleFace_Flavor05, Idle_Flavor01, Idle_Flavor02, Idle_Flavor03, Idle_Flavor04, Idle_Flavor05, Idle_Flavor06, Idle_Flavor07, Idle_Flavor08, Idle_Flavor09, Idle_Howl01, Idle_LookingUp01, Idle_RakingGround01, Idle_Taunt01, Idle_Taunt02, Idle_Taunt03, Idle_Taunt04, Idle_Taunt05, Idle_Taunt06, JogBackward, JogForward, JogLeft, JogRight, JumpInPlace, JumpInPlaceFallLoop, JumpInPlaceLand, JumpRunForward, JumpRunForwardFall, JumpRunForwardFallLoop, JumpRunLand, JumpTraversal, Knockdown, LookDirections, LookDirections_Head, LookDirections_Tail, MeleeAttack01, MeleeAttack02, MeleeAttackPower01, MeleeAttackPower_Bite01, MeleeAttackPower_Bite02, MeleeAttackPower_Claw01, MeleeAttackPower_Head01, MeleeAttackPower_Tail01, MeleeAttack_180, MeleeAttack_Bite01, MeleeAttack_Bite02, MeleeAttack_Claw01, MeleeAttack_Claw02, MeleeAttack_Claw03, MeleeAttack_Head01, MeleeAttack_Head02, MeleeAttack_Left180, MeleeAttack_Left90, MeleeAttack_Right180, MeleeAttack_Right90, MeleeAttack_Tail01, MeleeAttack_Tail02, PairedKill_Bite_Head_01_Killer, PairedKill_Bite_Head_02_Killer, PairedKill_Slam_Head_01_Killer, PairedKill_Slam_Head_02_Killer, RigTest_Posing, RigTest_WalkFwd, RunBackward, RunBackward_Start, RunDeparture_Left180, RunDeparture_Left90, RunDeparture_Right180, RunDeparture_Right90, RunForward, RunForward_Start, RunForward_Stop, RunForward_Stop_LeftFoot, RunForward_Stop_RightFoot, RunLeft, RunLeft_Start, RunRight, RunRight_Start, Sprint, StaggerBackwardLarge, StaggerBackwardLarge_Left, StaggerBackwardLarge_Right, StaggerBackwardMedium, StaggerBackwardMedium_Left, StaggerBackwardMedium_Right, StaggerBackwardSmall, StaggerBackwardSmall_Left, StaggerBackwardSmall_Right, StaggerForward, StaggerForwardMedium, StaggerLeft, StaggerRight, Start, Stop, Tail_BoneWeights, Threat_Assess01, Threat_Assess02, Threat_Backdown01, Threat_Backdown02, Threat_Curious01, Threat_Intimidate01, Threat_Intimidate02, Threat_Intimidate03, Threat_Listen01, Threat_Listen02, Traversal_Door, TunnelStart, TunnelStop, TurnInPlace_Left180, TurnInPlace_Left30, TurnInPlace_Left90, TurnInPlace_Right180, TurnInPlace_Right30, TurnInPlace_Right90, UpperBody_BoneWeights, WalkBackward, WalkDeparture_Left180, WalkDeparture_Left30, WalkDeparture_Left90, WalkDeparture_Right180, WalkDeparture_Right30, WalkDeparture_Right90, WalkForward, WalkForward_ManualExport, WalkForward_Start, WalkForward_Stop, WalkForward_Stop_LeftFoot, WalkForward_Stop_RightFoot, WalkLeft, WalkRight

### 1c. Required tags by function, and the Mini Bot's clips with their events [measured]

- idle: Idle, Idle_Flavor01/02 (Furniture graph's NPC_IdleFlavor plays the flavors), LookDirections (DirectAt / LookAt
  pose grid).
- locomotion: WalkForward/Backward/Left/Right, JogForward, RunForward, *_Start/*_Stop, Walk/RunDeparture_Left/Right
  90/180, TurnInPlace_Left/Right 30/90/180, JumpRunForwardFall(+Loop).
- combat: MeleeAttack01 (the race's ATKE events pick the tag), FireSingle_Mouth1.
- hit reaction: StaggerForward, StaggerBackwardSmall/Medium/Large, StaggerLeft/Right (Mini Bot has no Flinch_* clips).
- death: Death_Backward01/Forward01/Left01/Right01/Moving_Forward01; Knockdown (two clips share the tag); getup
  GetUp_Back/Front/Left/Right.
- Events the engine relies on: sync (SyncLeftFoot/SyncRightFoot on loops), pathing (PathingBegin/PathingEnd on
  departures and start/stop), SetOrientEnd on turns, PreHitFrame/WeaponSwing/HitFrame on melee, WeaponFire on fire,
  AddRagdollToWorld + RemoveCharacterControllerFromWorld on deaths and knockdowns. Foley is per frame in `<audios>`.

| Mini Bot clip | tag | is_state | events (frame) | foley (frame) |
|---|---|---|---|---|
| death_backward01 | Death_Backward01 | 1 | AddRagdollToWorld 9, RemoveCharacterControllerFromWorld 9 | NPC_MiniBotA_Death 1 |
| death_forward01 | Death_Forward01 | 1 | RemoveCharacterControllerFromWorld 14, AddRagdollToWorld 14 | NPC_MiniBotA_Death 1 |
| death_left01 | Death_Left01 | 1 | AddRagdollToWorld 7, RemoveCharacterControllerFromWorld 7 | NPC_MiniBotA_Death 1 |
| death_moving_forward01 | Death_Moving_Forward01 | 1 | AddRagdollToWorld 18, RemoveCharacterControllerFromWorld 18 | NPC_MiniBotA_Death 1 |
| death_right01 | Death_Right01 | 1 | RemoveCharacterControllerFromWorld 12, AddRagdollToWorld 12 | NPC_MiniBotA_Death 1 |
| diversion01 | Diversion01 | 1 |  | NPC_MiniBotA_MeleeAttack 8 |
| firesingle_mouth1 | FireSingle_Mouth1 | 0 | WeaponFire 10 | NPC_MiniBotA_Movement_Stop_NoFX 0 |
| getup_back | GetUp_Back | 0 |  | NPC_MiniBotA_MeleeAttack 9 |
| getup_front | GetUp_Front | 0 |  | NPC_MiniBotA_MeleeAttack 9 |
| getup_left | GetUp_Left | 0 |  | NPC_MiniBotA_MeleeAttack 10 |
| getup_right | GetUp_Right | 0 |  | NPC_MiniBotA_MeleeAttack 9 |
| idle | Idle | 1 |  | NPC_MiniBotA_Movement_Stop_NoFX 0 |
| jogforward | JogForward | 1 | SyncLeftFoot 15, SyncRightFoot 30 | NPC_MiniBotA_Run_Start 0 |
| jumprunforwardfall | JumpRunForwardFall | 0 |  |  |
| jumprunforwardfallloop | JumpRunForwardFallLoop | 1 |  |  |
| knockdown_backward | Knockdown | 0 | AddRagdollToWorld 38, RemoveCharacterControllerFromWorld 38 |  |
| knockdown_forward | Knockdown | 0 | AddRagdollToWorld 36, RemoveCharacterControllerFromWorld 36 |  |
| lookdirections | LookDirections | 1 |  | NPC_MiniBotA_Movement_Stop_NoFX 1 |
| meleeattack01 | MeleeAttack01 | 0 | PreHitFrame 8, WeaponSwing 8, HitFrame 13 | NPC_MiniBotA_MeleeAttack 0 |
| relaxed_idle_flavor01 | Idle_Flavor01 | 0 |  | NPC_MiniBotA_Idle_Up 12, NPC_MiniBotA_Idle_Down 27 |
| relaxed_idle_flavor02 | Idle_Flavor02 | 0 |  | NPC_MiniBotA_Idle_Up 13, NPC_MiniBotA_Idle_Down 27 |
| rundeparture_left180 | RunDeparture_Left180 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 55 | NPC_MiniBotA_Run_Start 29, NPC_MiniBotA_Turn_180 3 |
| rundeparture_left90 | RunDeparture_Left90 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 55 | NPC_MiniBotA_Run_Start 31, NPC_MiniBotA_Turn_90 4 |
| rundeparture_right180 | RunDeparture_Right180 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 55 | NPC_MiniBotA_Run_Start 32, NPC_MiniBotA_Turn_180 4 |
| rundeparture_right90 | RunDeparture_Right90 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 55 | NPC_MiniBotA_Run_Start 29, NPC_MiniBotA_Turn_90 3 |
| runforward | RunForward | 1 | SyncRightFoot 0, SyncLeftFoot 15 | NPC_MiniBotA_Run_Start 0 |
| runforward_start | RunForward_Start | 0 | PathingBegin 5, PathingEnd 26, SyncLeftFoot 30 | NPC_MiniBotA_Run_Start 7 |
| runforward_stop | RunForward_Stop | 0 | PathingBegin 0, SyncLeftFoot 0, SyncRightFoot 15, PathingEnd 21 | NPC_MiniBotA_Movement_Stop 7 |
| staggerbackwardlarge | StaggerBackwardLarge | 0 |  | NPC_MiniBotA_Stagger 0 |
| staggerbackwardmedium | StaggerBackwardMedium | 0 |  | NPC_MiniBotA_Stagger 0 |
| staggerbackwardsmall | StaggerBackwardSmall | 0 |  | NPC_MiniBotA_Stagger 0 |
| staggerforward | StaggerForward | 0 |  | NPC_MiniBotA_Stagger 0 |
| staggerleft | StaggerLeft | 0 |  | NPC_MiniBotA_Stagger 0 |
| staggerright | StaggerRight | 0 |  | NPC_MiniBotA_Stagger 0 |
| tunnelstart | TunnelStart | 0 |  | NPC_MiniBotA_Turn_180 5, NPC_MiniBotA_Turn_90 25 |
| tunnelstop | TunnelStop | 0 |  | NPC_MiniBotA_Turn_180 1 |
| turninplace_left180 | TurnInPlace_Left180 | 0 | SetOrientEnd 28 | NPC_MiniBotA_Movement_Stop_NoFX 1, NPC_MiniBotA_Turn_180 1 |
| turninplace_left30 | TurnInPlace_Left30 | 0 | SetOrientEnd 14 | NPC_MiniBotA_Movement_Stop_NoFX 1, NPC_MiniBotA_Turn_90 1 |
| turninplace_left90 | TurnInPlace_Left90 | 0 | SetOrientEnd 28 | NPC_MiniBotA_Movement_Stop_NoFX 1, NPC_MiniBotA_Turn_90 3 |
| turninplace_right180 | TurnInPlace_Right180 | 0 | SetOrientEnd 28 | NPC_MiniBotA_Movement_Stop_NoFX 1, NPC_MiniBotA_Turn_180 1 |
| turninplace_right30 | TurnInPlace_Right30 | 0 | SetOrientEnd 14 | NPC_MiniBotA_Movement_Stop_NoFX 1, NPC_MiniBotA_Turn_90 1 |
| turninplace_right90 | TurnInPlace_Right90 | 0 | SetOrientEnd 29 | NPC_MiniBotA_Movement_Stop_NoFX 1, NPC_MiniBotA_Turn_90 3 |
| walkbackward | WalkBackward | 1 | SyncLeftFoot 15, SyncRightFoot 30 |  |
| walkdeparture_left180 | WalkDeparture_Left180 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 60 | NPC_MiniBotA_Walk_Start 31, NPC_MiniBotA_Turn_180 3 |
| walkdeparture_left90 | WalkDeparture_Left90 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 60 | NPC_MiniBotA_Walk_Start 33, NPC_MiniBotA_Turn_90 3 |
| walkdeparture_right180 | WalkDeparture_Right180 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 60 | NPC_MiniBotA_Walk_Start 33, NPC_MiniBotA_Turn_180 4 |
| walkdeparture_right90 | WalkDeparture_Right90 | 1 | PathingBegin 5, PathingEnd 30, SyncLeftFoot 60 | NPC_MiniBotA_Walk_Start 34, NPC_MiniBotA_Turn_90 3 |
| walkforward | WalkForward | 1 | SyncLeftFoot 15, SyncRightFoot 30 | NPC_MiniBotA_Walk_Start 0 |
| walkforward_start | WalkForward_Start | 0 | PathingBegin 5, SyncRightFoot 15, PathingEnd 19, SyncLeftFoot 30 | NPC_MiniBotA_Walk_Start 8 |
| walkforward_stop | WalkForward_Stop | 0 | PathingBegin 0, SyncLeftFoot 0, SyncRightFoot 15, PathingEnd 21 | NPC_MiniBotA_Movement_Stop 10 |
| walkleft | WalkLeft | 1 | SyncLeftFoot 15, SyncRightFoot 30 |  |
| walkright | WalkRight | 1 | SyncLeftFoot 15, SyncRightFoot 30 |  |

Diversion01 is in the folder but not in the Creature_Strafing clip list (its tag is not one the graph plays).

## 2. Fallout 4 Mr. Handy clips (84) [measured]

`meshes\actors\robot\animations\` of `Fallout4 - Animations.ba2`; all hk_2014.1.0-r1 64-bit, `hkaSplineCompressedAnimation`,
111 transform tracks, 0 float tracks unless noted; (frames - 1) x frame duration = duration on all 84. Root motion =
an `hkaDefaultAnimatedReferenceFrame` is attached (81 of 84). Events: gameplay annotations (sounds `SoundPlay.*` left out,
they become foley). Full data with every annotation: `D:\FO4SF-Owner-Tests\robot-anim\D\fo4_handy_clips.json`.

| Fallout 4 clip | s | frames | root motion | gameplay events | Starfield tag(s) / why not |
|---|---|---|---|---|---|
| Claw/Attack_1.hkx | 1.600 | 49 | yes | HitFrame, preHitFrame, weaponSwing | MeleeAttack01 |
| Claw/Attack_2.hkx | 1.600 | 49 | yes | HitFrame, preHitFrame, weaponSwing | MeleeAttack02 |
| Claw/Attack_3.hkx | 1.600 | 49 | yes | HitFrame, preHitFrame, weaponSwing | MeleeAttackPower01 |
| Claw/Recoil_1.hkx | 1.667 | 51 | yes |  | not expressible: melee recoil (blocked hit): Creature_Melee has no recoil tag |
| Death1.hkx | 1.100 | 34 | yes |  | Death_Backward01 |
| Death2.hkx | 0.867 | 27 | yes |  | Death_Forward01; Death_Moving_Forward01 (reuse) |
| Death3.hkx | 0.933 | 29 | yes |  | Death_Left01; Death_Right01 (mirror) |
| DialogueIdle_Long1.hkx | 5.167 | 156 | yes |  | not expressible: as above |
| DialogueIdle_Long2.hkx | 7.667 | 231 | yes |  | not expressible: as above |
| DialogueIdle_Medium1.hkx | 4.333 | 131 | yes |  | not expressible: as above |
| DialogueIdle_Medium2.hkx | 4.333 | 131 | yes |  | not expressible: as above |
| DialogueIdle_Short1.hkx | 3.000 | 91 | yes |  | not expressible: talking idles: Starfield dialogue on a creature graph not checked |
| DialogueIdle_Short2.hkx | 3.000 | 91 | yes |  | not expressible: as above |
| DodgeLeft.hkx | 0.833 | 26 | yes |  | DodgeLeft; EvadeLeft (reuse) |
| DodgeRight.hkx | 0.833 | 26 | yes |  | DodgeRight; EvadeRight (reuse) |
| FlameThrower/RangedAttack_1.hkx | 5.567 | 168 | yes |  | not expressible: 5.6 s held flamethrower stream: no hold/loop fire state in Creature_Actions |
| FlameThrower/RangedAttackSingleFire_1.hkx | 0.667 | 21 | yes |  | not expressible: flamethrower burst; would need FireSingle_* and a flame weapon |
| FurnitureBar/EnterFromStand.hkx | 1.667 | 51 | yes |  | not expressible: furniture: needs FURN records + Furniture.agx keyword rows |
| FurnitureBar/ExitToStand.hkx | 2.333 | 71 | yes |  | not expressible: as above |
| FurnitureBar/PoseA_Idle1.hkx | 10.333 | 311 | yes |  | not expressible: as above |
| FurnitureBar/PoseA_IdleFlavor1.hkx | 10.333 | 311 | yes | AnimObjDraw.AnimObjMrHandyGlass, AnimObjLoad.AnimObjMrHandyGlass, AnimObjUnequip, HeadTrackingOff, HeadTrackingOn | not expressible: as above |
| FurnitureWashingDishes/EnterFromStand.hkx | 1.600 | 49 | yes | AnimObjDraw.AnimObjectMrHandyPlate, AnimObjLoad.AnimObjectMrHandyPlate, UncullBone.ArmPalmBone3|0 | not expressible: as above |
| FurnitureWashingDishes/LeftExitToStand.hkx | 1.333 | 41 | yes | AnimObjUnequip | not expressible: as above |
| FurnitureWashingDishes/PoseA_Idle1.hkx | 3.667 | 111 | no | AnimObjDraw.AnimObjectMrHandyPlate, AnimObjLoad.AnimObjectMrHandyPlate, AnimObjUnequip | not expressible: as above |
| GetFood.hkx | 2.500 | 76 | yes | AnimObjDraw.AnimObjectMrHandyFoodSugarBombs, AnimObjLoad.AnimObjectMrHandyFoodSugarBombs | not expressible: as above |
| GetUpRight.hkx | 2.500 | 76 | yes |  | GetUp_Right; GetUp_Left (mirror) |
| GiveFood.hkx | 6.000 | 181 | yes |  | not expressible: scene idles with props (AnimObjLoad/Draw); need IDLE records + Starfield anim objects |
| GiveHolotape.hkx | 12.000 | 361 | yes | AnimObjDraw.AnimObjectMrHandyHolotape, AnimObjLoad.AnimObjectMrHandyHolotape, disableLeftEye, disableRightEye, enableLeftEye, enableRightEye | not expressible: as above |
| GivePurifiedWater.hkx | 12.000 | 361 | yes | AnimObjDraw.AnimObjectMrHandyWater, AnimObjLoad.AnimObjectMrHandyWater, disableLeftEye, disableRightEye, enableLeftEye, enableRightEye | not expressible: as above |
| GiveStimpak.hkx | 12.000 | 361 | yes | AnimObjDraw.AnimObjectMrHandyStimpak, AnimObjLoad.AnimObjectMrHandyStimpak, disableLeftEye, disableRightEye, enableLeftEye, enableRightEye | not expressible: as above |
| HeadAutoFire.hkx | 2.200 | 67 | yes | WeaponFire | not expressible: as above |
| HitReactionLeftArm.hkx | 2.000 | 61 | yes |  | Flinch_LeftArm |
| HitReactionLeftEye.hkx | 0.933 | 29 | yes |  | Flinch_Head02 |
| HitReactionMidArm.hkx | 2.000 | 61 | yes |  | Flinch_LeftArm2 |
| HitReactionMidEye.hkx | 0.933 | 29 | yes |  | Flinch_Head01 |
| HitReactionRightArm.hkx | 2.000 | 61 | yes |  | Flinch_RightArm |
| HitReactionRightEye.hkx | 0.933 | 29 | yes |  | Flinch_Torso02 |
| HitReactionThruster.hkx | 2.000 | 61 | yes |  | Flinch_Torso01 |
| Idle.hkx | 10.333 | 311 | yes |  | Idle; JumpRunForwardFall (reuse); JumpRunForwardFallLoop (reuse) |
| Idle_BabyRattle.hkx | 7.167 | 216 | yes | AnimObjDraw.AnimObjectMrHandyBabyRattle, AnimObjLoad.AnimObjectMrHandyBabyRattle, AnimObjUnequip | not expressible: as above |
| Idle_CoffePot.hkx | 10.333 | 311 | yes |  | not expressible: as above |
| Idle_Dusting.hkx | 6.000 | 181 | yes |  | not expressible: as above |
| Idle_EyeFocus.hkx | 7.667 | 231 (7 tracks) | no |  | not expressible: 7-track partial (eye stalks only) layered on idle |
| Idle_GardeningTablePlot_1.hkx | 10.333 | 311 | yes | disableMidEye | not expressible: as above |
| Idle_GardeningTablePlot_2.hkx | 10.333 | 311 | yes | disableMidEye | not expressible: as above |
| Idle_Maintenance.hkx | 5.000 | 151 | yes | disableMidEye | not expressible: as above |
| Idle_ScanHigh.hkx | 4.667 | 141 | yes | disableMidEye, enableMidEye | Idle_Flavor02 |
| Idle_ScanLow.hkx | 4.667 | 141 | yes | disableMidEye, enableMidEye | Idle_Flavor03 |
| Idle_Welding.hkx | 10.333 | 311 (112 tracks) | yes | AnimObjDraw.AnimObjectHandyWelding, AnimObjLoad.AnimObjectHandyWelding, disableMidEye | not expressible: as above |
| IdleSearch.hkx | 14.000 | 421 | yes |  | Idle_Flavor01 |
| Injured/Idle.hkx | 10.333 | 311 | yes |  | not expressible: crippled-thruster set: needs Creature_LimbCripple tags and an Injured SAPT |
| Injured/RunForward.hkx | 6.333 | 191 | yes |  | not expressible: as above |
| InjuredArmIdle.hkx | 4.000 | 121 | yes |  | not expressible: as above |
| LeftArmAutoFire.hkx | 2.200 | 67 | yes | WeaponFire | not expressible: as above |
| LeftArmSingleFire.hkx | 0.333 | 11 | yes | WeaponFire | FireSingle_Mouth2 |
| LeftShoulderAutoFire.hkx | 2.200 | 67 | yes | WeaponFire | not expressible: as above |
| LeftShoulderSingleFire.hkx | 1.000 | 31 | yes | WeaponFire | not expressible: fifth fire mount; no free FireSingle tag |
| OnVertibird/EnterFromStand.hkx | 4.000 | 121 | yes |  | not expressible: vertibird riding: no vertibirds |
| OnVertibird/ExitToStand.hkx | 3.667 | 111 | yes | DesyncInteraction | not expressible: as above |
| OnVertibird/PoseA_Idle1.hkx | 3.000 | 91 | no |  | not expressible: as above |
| PickUp_Low.hkx | 2.500 | 76 | yes | PickUp, disableMidEye, enableMidEye | not expressible: as above |
| PickUp_Medium.hkx | 2.500 | 76 | yes | PickUp, disableMidEye, enableMidEye | not expressible: as above |
| RightArmAutoFire.hkx | 2.200 | 67 | yes | WeaponFire | not expressible: automatic fire per mount (weaponFire.0..5 picks the arm/shoulder/head); Creature_Actions only has FireSingle_Mouth1/Mouth2/Tail |
| RightArmSingleFire.hkx | 0.333 | 11 | yes | WeaponFire | FireSingle_Mouth1 |
| RightShoulderAutoFire.hkx | 2.200 | 67 | yes | WeaponFire | not expressible: as above |
| RightShoulderSingleFire.hkx | 1.000 | 31 | yes | WeaponFire | FireSingle_Tail |
| RotateRingCCW_Add.hkx | 0.600 | 19 | yes |  | not expressible: as above |
| RotateRingCW_Add.hkx | 0.600 | 19 | yes |  | not expressible: additive ring spin layered by HandyBehavior; Starfield graph has no additive layer for it |
| RunForward.hkx | 6.333 | 191 | yes |  | WalkForward (reuse); JogForward (reuse); RunForward; WalkBackward (reuse); WalkLeft (reuse); WalkRight (reuse) |
| SawBlade/Attack_1.hkx | 1.400 | 43 | yes | HitFrame, preHitFrame, weaponSwing | MeleeAttack_Claw01 |
| SawBlade/Attack_2.hkx | 1.400 | 43 | yes | HitFrame, preHitFrame, weaponSwing | MeleeAttack_Claw02 |
| SawBlade/Attack_3.hkx | 1.933 | 59 | yes | HitFrame, preHitFrame, weaponSwing | MeleeAttackPower_Claw01 |
| SawBlade/Recoil_1.hkx | 1.667 | 51 | yes |  | not expressible: as above |
| SawingIdle.hkx | 7.000 | 211 (112 tracks) | yes | AnimObjDraw.AnimObjectHandyHedgeFX, AnimObjLoad.AnimObjectHandyHedgeFX, AnimObjUnequip, SawSwipeLeft, SawSwipeRight | not expressible: as above |
| StaggerForwardMedium.hkx | 1.200 | 37 | yes |  | StaggerForward |
| StaggerForwardSmall.hkx | 0.600 | 19 | yes |  | not expressible: spare: only one StaggerForward tag |
| StaggerLarge.hkx | 2.333 | 71 | yes |  | StaggerBackwardLarge |
| StaggerMedium.hkx | 1.200 | 37 | yes |  | StaggerBackwardMedium; StaggerLeft (reuse); StaggerRight (reuse) |
| StaggerSmall.hkx | 0.600 | 19 | yes |  | StaggerBackwardSmall |
| ToUnconscious.hkx | 1.333 | 41 | yes |  | Knockdown |
| TurnLeft.hkx | 2.033 | 62 | yes |  | TurnInPlace_Left90; TurnInPlace_Left30 (reuse); TurnInPlace_Right90 (mirror); TurnInPlace_Right30 (mirror) |
| TurnLeft180.hkx | 1.600 | 49 | yes |  | TurnInPlace_Left180; TurnInPlace_Right180 (mirror) |
| TurnLeft180ToMove.hkx | 2.333 | 71 | yes |  | WalkDeparture_Left180; RunDeparture_Left180 (reuse); WalkDeparture_Right180 (mirror); RunDeparture_Right180 (mirror) |
| UnconsciousToConscious.hkx | 3.167 | 96 | yes |  | GetUp_Back; GetUp_Front (reuse) |

Fallout 4's HandyRace `000359F4` loads them through HandyBehavior.hkx with SAPT sets per weapon arm (FlameThrower, Claw,
SawBlade, each with or without Injured) and three furniture behaviors; there is only one RunForward (hover locomotion
is that clip played at speed) and only left turns (the behavior mirrors them).

## 3. Proposed mapping FO4 clip -> Starfield tag [proposal]

`how`: direct = the clip as is; reuse = same source as another tag; mirror = left/right mirrored copy to build (Starfield
tags are fixed per file, the Fallout 4 behavior mirrored at run time); none = no Fallout 4 clip, the tag stays empty
(behaviour of the graph with a missing tag is **not proven**).

| Starfield tag | Handy clip file | Fallout 4 source | how | note |
|---|---|---|---|---|
| Idle | Idle.af | Idle.hkx | direct |  |
| Idle_Flavor01 | Relaxed_Idle_Flavor01.af | IdleSearch.hkx | direct | 14 s look-around |
| Idle_Flavor02 | Relaxed_Idle_Flavor02.af | Idle_ScanHigh.hkx | direct |  |
| Idle_Flavor03 | Relaxed_Idle_Flavor03.af | Idle_ScanLow.hkx | direct |  |
| LookDirections | LookDirections.af | - | none | Starfield samples a pose grid; Fallout 4 aimed the eye stalks by head tracking. Needs a built pose clip |
| WalkForward | WalkForward.af | RunForward.hkx | reuse | sync foot events not needed |
| JogForward | JogForward.af | RunForward.hkx | reuse |  |
| RunForward | RunForward.af | RunForward.hkx | direct |  |
| WalkBackward | WalkBackward.af | RunForward.hkx | reuse | hover body pose is the same; root motion must be rewritten backwards |
| WalkLeft | WalkLeft.af | RunForward.hkx | reuse | root motion rewritten sideways |
| WalkRight | WalkRight.af | RunForward.hkx | reuse | root motion rewritten sideways |
| WalkForward_Start | WalkForward_Start.af | - | none | no start clip; graph falls to WalkForward? |
| WalkForward_Stop | WalkForward_Stop.af | - | none |  |
| RunForward_Start | RunForward_Start.af | - | none |  |
| RunForward_Stop | RunForward_Stop.af | - | none |  |
| TurnInPlace_Left90 | TurnInPlace_Left90.af | TurnLeft.hkx | direct |  Events added: SetOrientEnd |
| TurnInPlace_Left180 | TurnInPlace_Left180.af | TurnLeft180.hkx | direct |  Events added: SetOrientEnd |
| TurnInPlace_Left30 | TurnInPlace_Left30.af | TurnLeft.hkx | reuse | crop to the first third or keep 90 deg Events added: SetOrientEnd |
| TurnInPlace_Right90 | TurnInPlace_Right90.af | TurnLeft.hkx | mirror |  Events added: SetOrientEnd |
| TurnInPlace_Right180 | TurnInPlace_Right180.af | TurnLeft180.hkx | mirror |  Events added: SetOrientEnd |
| TurnInPlace_Right30 | TurnInPlace_Right30.af | TurnLeft.hkx | mirror |  Events added: SetOrientEnd |
| WalkDeparture_Left180 | WalkDeparture_Left180.af | TurnLeft180ToMove.hkx | direct |  |
| RunDeparture_Left180 | RunDeparture_Left180.af | TurnLeft180ToMove.hkx | reuse |  |
| WalkDeparture_Right180 | WalkDeparture_Right180.af | TurnLeft180ToMove.hkx | mirror |  |
| RunDeparture_Right180 | RunDeparture_Right180.af | TurnLeft180ToMove.hkx | mirror |  |
| WalkDeparture_Left90 | WalkDeparture_Left90.af | - | none |  |
| WalkDeparture_Right90 | WalkDeparture_Right90.af | - | none |  |
| RunDeparture_Left90 | RunDeparture_Left90.af | - | none |  |
| RunDeparture_Right90 | RunDeparture_Right90.af | - | none |  |
| JumpRunForwardFall | JumpRunForwardFall.af | Idle.hkx | reuse | hovers: no fall pose |
| JumpRunForwardFallLoop | JumpRunForwardFallLoop.af | Idle.hkx | reuse |  |
| MeleeAttack01 | MeleeAttack01.af | Claw/Attack_1.hkx | direct | Fallout 4 picks Claw or SawBlade by weapon |
| MeleeAttack02 | MeleeAttack02.af | Claw/Attack_2.hkx | direct |  |
| MeleeAttackPower01 | MeleeAttackPower01.af | Claw/Attack_3.hkx | direct |  |
| MeleeAttack_Claw01 | MeleeAttack_Claw01.af | SawBlade/Attack_1.hkx | direct |  |
| MeleeAttack_Claw02 | MeleeAttack_Claw02.af | SawBlade/Attack_2.hkx | direct |  |
| MeleeAttackPower_Claw01 | MeleeAttackPower_Claw01.af | SawBlade/Attack_3.hkx | direct |  |
| FireSingle_Mouth1 | FireSingle_Mouth1.af | RightArmSingleFire.hkx | direct | weaponFire.0 -> WeaponFire; FO4 fires from 5 mounts, Starfield has 3 FireSingle tags |
| FireSingle_Mouth2 | FireSingle_Mouth2.af | LeftArmSingleFire.hkx | direct |  |
| FireSingle_Tail | FireSingle_Tail.af | RightShoulderSingleFire.hkx | direct |  |
| DodgeLeft | DodgeLeft.af | DodgeLeft.hkx | direct |  |
| DodgeRight | DodgeRight.af | DodgeRight.hkx | direct |  |
| EvadeLeft | EvadeLeft.af | DodgeLeft.hkx | reuse |  |
| EvadeRight | EvadeRight.af | DodgeRight.hkx | reuse |  |
| StaggerForward | StaggerForward.af | StaggerForwardMedium.hkx | direct |  |
| StaggerBackwardSmall | StaggerBackwardSmall.af | StaggerSmall.hkx | direct |  |
| StaggerBackwardMedium | StaggerBackwardMedium.af | StaggerMedium.hkx | direct |  |
| StaggerBackwardLarge | StaggerBackwardLarge.af | StaggerLarge.hkx | direct |  |
| StaggerLeft | StaggerLeft.af | StaggerMedium.hkx | reuse | no side stagger in Fallout 4 |
| StaggerRight | StaggerRight.af | StaggerMedium.hkx | reuse |  |
| Flinch_Head01 | Flinch_Head01.af | HitReactionMidEye.hkx | direct |  |
| Flinch_Head02 | Flinch_Head02.af | HitReactionLeftEye.hkx | direct |  |
| Flinch_Torso01 | Flinch_Torso01.af | HitReactionThruster.hkx | direct |  |
| Flinch_Torso02 | Flinch_Torso02.af | HitReactionRightEye.hkx | direct |  |
| Flinch_LeftArm | Flinch_LeftArm.af | HitReactionLeftArm.hkx | direct |  |
| Flinch_RightArm | Flinch_RightArm.af | HitReactionRightArm.hkx | direct |  |
| Flinch_LeftArm2 | Flinch_LeftArm2.af | HitReactionMidArm.hkx | direct |  |
| Death_Backward01 | Death_Backward01.af | Death1.hkx | direct |  Events added: AddRagdollToWorld, RemoveCharacterControllerFromWorld |
| Death_Forward01 | Death_Forward01.af | Death2.hkx | direct |  Events added: AddRagdollToWorld, RemoveCharacterControllerFromWorld |
| Death_Left01 | Death_Left01.af | Death3.hkx | direct |  Events added: AddRagdollToWorld, RemoveCharacterControllerFromWorld |
| Death_Right01 | Death_Right01.af | Death3.hkx | mirror |  Events added: AddRagdollToWorld, RemoveCharacterControllerFromWorld |
| Death_Moving_Forward01 | Death_Moving_Forward01.af | Death2.hkx | reuse |  Events added: AddRagdollToWorld, RemoveCharacterControllerFromWorld |
| Knockdown | Knockdown_Backward.af | ToUnconscious.hkx | direct |  Events added: AddRagdollToWorld, RemoveCharacterControllerFromWorld |
| GetUp_Back | GetUp_Back.af | UnconsciousToConscious.hkx | direct |  |
| GetUp_Front | GetUp_Front.af | UnconsciousToConscious.hkx | reuse |  |
| GetUp_Right | GetUp_Right.af | GetUpRight.hkx | direct |  |
| GetUp_Left | GetUp_Left.af | GetUpRight.hkx | mirror |  |
| TunnelStart | TunnelStart.af | - | none | burrowing; never used by a Handy |
| TunnelStop | TunnelStop.af | - | none |  |

Event conversion: `preHitFrame`, `weaponSwing`, `HitFrame` keep their names (the Mini Bot's baked offsets use exactly
these spellings), `weaponFire.N` becomes `WeaponFire`, `SoundPlay.X` becomes foley work (the Wwise names differ),
`AnimObj*`, `enable/disable*Eye`, `UncullBone`, `PickUp`, `SawSwipe*`, `DesyncInteraction` are dropped.
Per-clip sidecar data (tag, is_state, events by frame, Fallout 4 sounds): `D:\FO4SF-Owner-Tests\robot-anim\D\handy_afx_specs.json`;
`handy_race.afx_bytes()` writes the .afx in the vanilla shape.

### Tags with no good Fallout 4 clip

LookDirections (Fallout 4 aimed eye stalks by head tracking: a pose-grid clip must be built), WalkForward_Start/Stop,
RunForward_Start/Stop, Walk/RunDeparture_Left90/Right90, TunnelStart/Stop, DodgeBack, Jump* (hovering: reuses Idle),
StaggerLeft/Right (reuse StaggerMedium), all CriticalHit_*, Threat_*, IdleBack/IdleFace, PairedKill_*.

### Fallout 4 behaviour the generic graph cannot express

- Hover height and the thruster: Fallout 4 hovers via HandyBehavior + the character controller; Starfield's creature
  graph is ground locomotion with sync foot events. The body height must live in the skeleton/clips themselves.
- The three-arm weapon loadout: Fallout 4 picks Claw/SawBlade/FlameThrower clip folders per arm weapon (SAPT sets keyed
  by weapon). Creature_Strafing has one SAPT folder; the proposal puts Claw on MeleeAttack01/02/Power01 and SawBlade on
  MeleeAttack_Claw01/02/Power_Claw01 so the race's ATKD entries can choose.
- Five fire mounts (`weaponFire.0..5`: right/left arm, right/left shoulder, head) and automatic fire: Creature_Actions
  has only FireSingle_Mouth1/Mouth2/Tail.
- Flamethrower: a 5.6 s held stream (RangedAttack_1) has no hold/loop fire state.
- Additive ring rotation (RotateRingCW/CCW_Add), eye-stalk partial idle (Idle_EyeFocus, 7 tracks), melee recoil,
  injured/crippled set, dialogue idles, prop idles (food, holotape, stimpak, welding...), furniture (bar, dishes,
  vertibird). Full list in `FO4_NOT_EXPRESSIBLE`.

## 4. The Handy race records [proposal, built]

`build_race()` clones MiniBotARace and changes only: EDID `FO4SF_HandyRace`; FULL/SNAM `Mr. Handy` and DESC empty (our
plugin is not localized, the Starfield string ids would not resolve); GNAM -> the new BPTD; ANAM
`FO4SF\Actors\Handy\CharacterAssets\skeleton.nif`; NAM5 `FO4SF\Actors\Handy\CharacterAssets\skeleton.rig`; DNAM and the
three SAPT -> `Actors\FO4SF\Handy\Animations` (`...\Furniture` for the first Furniture SAPT); ZNAM C_Chassis -> Chest.
Every other subrecord (170 in all, ATKD/ATKE, MTNM, WED0/WED1, QNAM...) is kept byte for byte (test asserts the changed
set). Paths live in `HandyPaths`; change them there.

`build_bptd()` clones MiniBotABodyPartData: MODL and every `BASE Meshes\...skeleton_ref.nif` -> the Handy skeleton_ref;
bones from Fallout 4's own MrHandyBodyPartData `0004B368`, whose parts target Chest, Pelvis, SPINE2, Arm1|0..2,
EyeArm3|0..2 and Root:

| Mini Bot part | Handy bone | why |
|---|---|---|
| C_Chassis | Chest | Fallout 4 part "Chest" (main shell; also the race's ZNAM) |
| C_Base (ENAM C_Base, FNAM C_Axle) | Pelvis | Fallout 4 part "Pelvis" (thruster end, the bottom of the body) |
| C_Arm1 | Arm1\|0 | Fallout 4 part "P-ArmsTypeA1\|0" targets Arm1\|0 |
| C_Body | Spine2 | Fallout 4 part "SPINE2" |
| COM, Root | COM, Root | same names in the Handy skeleton |
| (added) | Arm1\|1, Arm1\|2, EyeArm3\|0..2 | the other two arms and the three eyes, as Fallout 4's BPTD (copies of the C_Arm1 part data) |

These are the hkx / skeletonref.nif names (pipe names). They must exist in the converted `skeleton.rig` and
`skeleton_ref.nif`; mrhandy.nif uses other names (LArm_1.., REyeArm1..) and that mapping is still open (builder of the
rig). Pass `bone_map=` / `extra_parts=` to change them.

Built test plugin: `D:\FO4SF-Owner-Tests\robot-anim\D\FO4SF_HandyRace.esm` (masters Starfield.esm; RACE 01000800, BPTD
01000801; dump in `handy_records.txt`). Note: PluginWriter writes unknown groups alphabetically (BPTD before RACE);
Starfield.esm has RACE at top group 13 and BPTD at 81. Load order of groups is **not proven** to matter.

## 5. Animation manifests and the u64 file name [measured]

`Starfield - Animations.ba2` holds, under `meshes\animtextdata\`: `animationfiledata\` (1,889), `animationstancedata\`
(1,889), `animationoffsets\` (1,901 + `persistantsubgraphinfoandoffsetdata.txt`), `dynamicidledata\` (1,901),
`generatedsubgraphdata\<race edid>.txt` (28), `animationfiles.txt` (every clip path), plus tables/animeventinfo/
clipgeneratordata. The four per-subgraph folders share one name per (graph, folder list).

**The name:**

    key = (BSCRC32(lower("|".join(folders))) << 32) | BSCRC32(lower(graph))

BSCRC32 is the standard reflected CRC-32 table (poly 0xEDB88320) run with **init 0 and no final xor** (=
`zlib.crc32(s, 0xFFFFFFFF) ^ 0xFFFFFFFF`), over cp1252 bytes, backslashes kept. graph = the SGNM/NAM6 string
(`AnimTextData\Tables\Graphs\X.agx`); folders = the SGNM's SAPT strings in record order, or the last column of a
generatedsubgraphdata row split at ", ". Root graphs have no folder list and high word 0.

Evidence: the low 32 bits are constant per graph (43 graphs, ShipRoot has 3 spellings) and equal BSCRC32 of the lower
graph path; candidates tested and rejected for the high word: CRC32 (zlib), CRC32C, bzip2/MPEG-2 CRC, FNV-1/1a 32/64,
joins with "", ",", ", ", ";", NUL, LF, "\", space, chained or xor/sum of per-folder CRCs, original case (1,679 hits only).
"|" + lower case reproduces **all 1,889** clip-list keys from 1,963 (graph, folders) sets read from every RACE in
Starfield.esm and every generatedsubgraphdata row; the 11 remaining keys are the root graphs with high word 0. Mini Bot:
Creature_Strafing + `Actors\MiniBotA\Animations` = 15280412852093574592; Furniture + `...\Furniture`, `...\Animations` =
4101133081575975552; Furniture + `actors\minibota\animations\furniture\ambush`, `...\Animations` = 10432078471184280192.

**File formats** (writers in handy_race; byte-exact on the Mini Bot's files, tested):

- `animationfiledata\<key>.txt`: `3\n1\n<key>\n<count>\n` then `<SAPT folder>\<afx filename>` per line, plain ASCII
  sort, LF. Lists only clips whose tag the graph plays.
- `dynamicidledata\<key>.txt`: `Version 1\n` (+ dynamic idle clip paths, used by Human sets).
- `animationoffsets\<key>.txt`: `V5\n`, lstr graph, u32 N + N x (lstr tag, lstr clip without extension), u32 M + M x
  (lstr clip, f32 duration, u32 flags, u32 0, u32 0, u32 nkeys + nkeys x 5 f32, u32 nevents + (f32 time s, lstr name)).
  lstr = u8 length incl. NUL + text + NUL. Flags seen: 0x400000 (has events), 0x20, 0x0; records with 0x8/0x10/0x80
  carry more blocks (not decoded; 116 of 1,900 files parse fully with this layout, all Mini Bot ones included). The
  Mini Bot's Strafing file bakes only 4 clips: TunnelStart/Stop (root rotation keys) and MeleeAttack01 /
  FireSingle_Mouth1 (events `weaponSwing`, `preHitFrame`, `HitFrame`, `WeaponFire`, from the .afx frames / 30).
- `animationstancedata\<key>.txt`: lstr `AnimationTransformedBoneArray_AnimationBoneTransform`, u32 2, u32 1, u32 0,
  u32 count, count x (7 f32: quaternion + translation, u16 rig bone index, u16 0xFFFF), then a trailer (16 bytes `u32
  2|3, 0, -1, 0` in the minimal files; larger files have more blocks). The Mini Bot's lists rig bones 2..10 with
  different values per sub-graph: probably a reference pose of the set's clips. **Not proven** what pose; not written
  for the Handy (stance_data() is ready once known).
- `generatedsubgraphdata\<edid lower>.txt`: tab table `Role, Perspective, Actor Keyword(s), Target Keyword(s), Behavior
  Path, Animation Path(s)`; only keyword-conditioned extra sets (Mini Bot: Furniture + AnimFurnAmbush).
- `persistantsubgraphinfoandoffsetdata.txt` lists 1,078 of the 1,901 keys (Mini Bot Strafing included); not extended.

`race_manifests()` writes for the Handy (`D:\FO4SF-Owner-Tests\robot-anim\D\Data\Meshes\AnimTextData\`):
Strafing key 9788993363940859328 (58 clips, offsets with the 9 melee/fire clips and their Fallout 4 event times),
Furniture key 18356569646593763968 (Idle + 3 flavors, minimal offsets), dynamic idle files, and an empty
`fo4sf_handyrace.txt`.

## 6. Not proven, to test in game

1. Whether Starfield needs these manifests for a new race at all, or rebuilds them; whether loose files under
   `Data\Meshes\AnimTextData\` are read (they normally live in the archive).
2. Whether a missing animationstancedata file breaks the sub-graph; whether a tag with no clip stalls the graph.
3. Whether the offsets events are what fires HitFrame/WeaponFire, or the .afx events (ship both).
4. The Handy rig bone names (BPTD and ZNAM use the hkx names). Superseded by section 7: since the robot-anim fix
   every rig, clip, mesh, skeleton NIF and BPTD name is the letters / digits / '_' form below.
5. Group order in the test plugin.

## 7. Rig and mesh fixes before the in-game probe (robot-anim fix, 23 Nov 2026) [built, bundle E2]

Review F found four things that could make the Handy probe (ra2a) fail for avoidable reasons. All are fixed in
`convert_handy.finish_skeleton` / `convert_parts` and `stage_ra2_handy.py`; the bundle is
`D:\FO4SF-Owner-Tests\robot-anim\E2` (E2\CHANGES.md has every measurement and SHA-256).

1. **COM rest rotation.** skeleton.hkx turns COM -90 deg about Y; no vanilla Starfield rig (386 checked) turns COM or
   Pelvis by more than 30 deg, and how the engine applies a translation offset on a turned bone is unknown (the two
   rules differ by up to 1.27 m on COM). `REBASE` = COM, Pelvis, C-ModSlotB|0..2 (the only other bones with a turned
   rest and real translation keys, up to 0.146 m between the rules) now have an identity rest rotation:
   `actor_skin.rest_rotation_corrections` / `rebase_skeleton` fold the turn into the children's rest poses and the mesh
   bind, `stage_ra2_handy.rebase_frames` into every clip (t' = C_p^-1 t, q' = C_p^-1 q C_j). World positions are
   unchanged in every frame; the rule difference left over every bone and frame is in the report.
2. **Bone names.** 80 of 112 names had '|' or '-' (no vanilla actor rig has either). `actor_skin.starfield_bone_names`
   replaces both with '_' (case-insensitive collisions refused) in the .rig, every clip block, the mesh skin bone
   lists and nodes, skeleton.nif, skeleton_ref.nif and the BPTD / RACE ZNAM (`renamed_body_parts`). The clips are still
   decoded, cropped and mirrored on the hkx names (pairing |1 <-> |2) and renamed when written. Map:

| Fallout 4 (hkx) -> rig | | | |
|---|---|---|---|
| `C-ArmsTypeA1\|0` -> `C_ArmsTypeA1_0` | `ArmHub1\|0` -> `ArmHub1_0` | `ArmHub2\|0` -> `ArmHub2_0` | `Arm1\|0` -> `Arm1_0` |
| `Arm2\|0` -> `Arm2_0` | `Arm3\|0` -> `Arm3_0` | `Arm4\|0` -> `Arm4_0` | `Arm5\|0` -> `Arm5_0` |
| `Arm6\|0` -> `Arm6_0` | `Arm7\|0` -> `Arm7_0` | `C-ModHands\|0` -> `C_ModHands_0` | `ArmPalm\|0` -> `ArmPalm_0` |
| `ArmPalmBone1\|0` -> `ArmPalmBone1_0` | `C-ArmsTypeA1\|1` -> `C_ArmsTypeA1_1` | `ArmHub1\|1` -> `ArmHub1_1` | `ArmHub2\|1` -> `ArmHub2_1` |
| `Arm1\|1` -> `Arm1_1` | `Arm2\|1` -> `Arm2_1` | `Arm3\|1` -> `Arm3_1` | `Arm4\|1` -> `Arm4_1` |
| `Arm5\|1` -> `Arm5_1` | `Arm6\|1` -> `Arm6_1` | `Arm7\|1` -> `Arm7_1` | `C-ModHands\|1` -> `C_ModHands_1` |
| `ArmPalm\|1` -> `ArmPalm_1` | `ArmPalmBone1\|1` -> `ArmPalmBone1_1` | `C-ArmsTypeA1\|2` -> `C_ArmsTypeA1_2` | `ArmHub1\|2` -> `ArmHub1_2` |
| `ArmHub2\|2` -> `ArmHub2_2` | `Arm1\|2` -> `Arm1_2` | `Arm2\|2` -> `Arm2_2` | `Arm3\|2` -> `Arm3_2` |
| `Arm4\|2` -> `Arm4_2` | `Arm5\|2` -> `Arm5_2` | `Arm6\|2` -> `Arm6_2` | `Arm7\|2` -> `Arm7_2` |
| `C-ModHands\|2` -> `C_ModHands_2` | `ArmPalm\|2` -> `ArmPalm_2` | `ArmPalmBone1\|2` -> `ArmPalmBone1_2` | `C-ModSlotB\|0` -> `C_ModSlotB_0` |
| `EyeArm1\|0` -> `EyeArm1_0` | `EyeArm2\|0` -> `EyeArm2_0` | `EyeArm3\|0` -> `EyeArm3_0` | `EyeArm_Flap\|0` -> `EyeArm_Flap_0` |
| `EyeArmPalm\|0` -> `EyeArmPalm_0` | `C-ModSlotB\|1` -> `C_ModSlotB_1` | `EyeArm1\|1` -> `EyeArm1_1` | `EyeArm2\|1` -> `EyeArm2_1` |
| `EyeArm3\|1` -> `EyeArm3_1` | `EyeArm_Flap\|1` -> `EyeArm_Flap_1` | `EyeArmPalm\|1` -> `EyeArmPalm_1` | `C-ModSlotB\|2` -> `C_ModSlotB_2` |
| `EyeArm1\|2` -> `EyeArm1_2` | `EyeArm2\|2` -> `EyeArm2_2` | `EyeArm3\|2` -> `EyeArm3_2` | `EyeArm_Flap\|2` -> `EyeArm_Flap_2` |
| `EyeArmPalm\|2` -> `EyeArmPalm_2` | `ArmPalmBone2\|0` -> `ArmPalmBone2_0` | `ArmPalmBone3\|0` -> `ArmPalmBone3_0` | `ArmPalmSawBlade\|0` -> `ArmPalmSawBlade_0` |
| `ArmPalmBone2\|1` -> `ArmPalmBone2_1` | `ArmPalmBone3\|1` -> `ArmPalmBone3_1` | `ArmPalmSawBlade\|1` -> `ArmPalmSawBlade_1` | `ArmPalmBone2\|2` -> `ArmPalmBone2_2` |
| `ArmPalmBone3\|2` -> `ArmPalmBone3_2` | `ArmPalmSawBlade\|2` -> `ArmPalmSawBlade_2` | `EyeArmPalm_Lens\|0` -> `EyeArmPalm_Lens_0` | `EyeArmPalm_Iris\|0` -> `EyeArmPalm_Iris_0` |
| `EyeArmPalm_IrisSC\|0` -> `EyeArmPalm_IrisSC_0` | `EyeArmPalm_Lens\|1` -> `EyeArmPalm_Lens_1` | `EyeArmPalm_Iris\|1` -> `EyeArmPalm_Iris_1` | `EyeArmPalm_IrisSC\|1` -> `EyeArmPalm_IrisSC_1` |
| `EyeArmPalm_Lens\|2` -> `EyeArmPalm_Lens_2` | `EyeArmPalm_Iris\|2` -> `EyeArmPalm_Iris_2` | `EyeArmPalm_IrisSC\|2` -> `EyeArmPalm_IrisSC_2` | `C-Head` -> `C_Head` |
| `C-ArmLeft` -> `C_ArmLeft` | `C-ArmRight` -> `C_ArmRight` | `C-HandLeft` -> `C_HandLeft` | `C-HandRight` -> `C_HandRight` |

   Unchanged (32): Root, COM, Pelvis, Ring, RingMesh, Spine1, Spine2, Chest, CombatInhibitor, L/RClavicle,
   L/RClavicleTwist, L/RUpperArm, L/RUpperArmShoulderTwist, L/RUpperArmTwist, L/RForearm1, L/RForearmTwist, L/RHandTurn,
   L/RHandTurnTilt, Neck, HeadNod, HeadTwist, Visor, AnimObjectA; plus the new DirectAt. BPTD parts: C_Arm1 -> Arm1_0,
   added Arm1_1, Arm1_2, EyeArm3_0..2 (the section 4 table with these names). The build also writes the map to
   `<bundle>\work\bone_names.json`.
3. **DirectAt (map key 137).** The vanilla Mini Bot rig has DirectAt under C_Body at C_Body's origin, identity rotation,
   and C_Body sits on COM unturned, so DirectAt stands on COM; 26 of 29 vanilla actor rigs carry key 137. The Handy has
   no C_Body: `EXTRA_BONES` puts DirectAt directly under the rebased COM at (0, 0, 0), identity, appended as the 113th
   bone (every other index unchanged). No clip animates it. As in vanilla, it is in skeleton_ref.nif but not in the
   mesh NIF (`MESH_EXCLUDE`).
4. **Mesh: Codsworth's own parts.** Fallout4.esm NPC_ 000179FF Codsworth has no skin and no outfit: his object template
   (OBTS, 15 includes) attaches robot-part object mods whose MODL is the part NIF, and each arm mod forces a hand weapon
   whose embedded mod (WEAP NNAM) is the hand. Parts (`convert_handy.CODSWORTH_PARTS`, instance N = attach index = the
   |N bone copy): TorsoHandy, LegsHandyThruster, ModTorsoFloatType1AR1A (top armour), ModTorsoHandyEye x3 (|0 |1 |2),
   LegsHandyThrusterAR1A, LegsHandyThrusterAR1B, HandyFrontArmor, HandyRearArmor, ArmsTypeA1 x3, ModArmsTypeA1AR1A on
   |0 and |1, PincherHand |0 (middle), FlameThrowerHand |1 (right), SawHand |2 (left). Each part binds on skeleton.hkx's
   reference pose up to one rigid offset per shape (spread <= 0.0001 FO4 units); each vertex is posed on the rig bind
   with its own Fallout 4 weights (up to 4; vanilla Starfield actor meshes use 1 to 8). The five texture sets are the
   same as mrhandy.nif's, so the shapes keep the names and the Codsworth .mat files of the current conversion. The eye
   lens (ModTorsoHandyEye:2, 25 vertices x3, BSEffectShaderProperty HandyLens.BGEM) has no Starfield material yet and is
   left out. Deformation check (all 58 clips, every frame): the mrhandy.nif palm / Arm7 tear (25x) is gone; 19 clips stay
   under 1.6x (Idle 1.13, Walk/Run 1.26); 39 do not, all on seams Fallout 4's own parts have (TorsoHandy's 112
   Chest/Ring/RingMesh junction triangles when the turn clips spin Ring up to 125 deg; 13 rigid Arm4/Arm5 hinge triangles
   per arm, up to 7.7x; 12 pincher finger-hinge triangles, 2.4x). Proof: skinning every placed part the way Fallout 4
   does (its own skin-to-bone transforms and weights) on the poses written gives the same worst ratio in every clip and
   frame within 0.72 %, and the same 39 clips over 1.6x (`stage_ra2_handy.native_vs_staged`, report "fo4_native").
   Whether these slivers show on screen, and whether FO4's behaviour graph masks Ring in its turns, only the game can say.

## 8. In-game result (23 Nov 2026, Claude (PC), game on main `b2b19a03` plus the probe plugins only)

Three probe NPCs, spawned with `placeatme` in the Vault 111 test area, god mode on, test mods removed afterwards:

| Probe | What it isolates | Result |
|---|---|---|
| `000808` Mini Bot on a renamed copy of MiniBotARace | does a plugin's own copy of a robot race animate | **Pass**: idles, turns, walks |
| `00080C` Mini Bot on the plugin's own rig and clip folder | does the game load a rig, clips and manifests from a plugin | **Pass** (the manifests were shipped too, so whether they are needed is not yet separated) |
| `000804` Mr. Handy (bundle E2) on his own Fallout 4 skeleton, converted Fallout 4 clips, Codsworth's 15 parts | the whole chain in this document | **Pass**: body turns and hovers, all three eye stalks and all three arms (pincer, flamer, saw) move, the death clip plays (arms fling, body drops) |

The welded Codsworth that ships today is frozen because its mesh is welded, not because Starfield refuses a robot
race. Whether the seams of section 7 item 4 are visible in play is for the owner's look test; they are Fallout 4's own
deformation, and changing weights to hide them is a separate decision not taken here.

Next: put Codsworth himself on this race and mesh; check whether the manifests are needed; then the other robots and
creatures in first-mission order.
