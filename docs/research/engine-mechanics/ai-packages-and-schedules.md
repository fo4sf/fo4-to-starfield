# AI packages and schedules (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Scope: PACK (procedures, templates via PKCU, schedules, targets, flags), package stacks (actor, alias, quest, default
lists, override lists), sandboxing, idle markers and furniture, patrols, travel, follow, force greet, eat and sleep,
EvaluatePackage, and what Starfield changed. "xEdit" = TES5Edit dev-4.1.6 `wbDefinitionsFO4.pas` /
`wbDefinitionsSF1.pas` / `wbDefinitionsCommon.pas`.

## In short
- **PACK is the closest layout match of any record** (subrecord overlap 0.87, verified, docs/FORMAT-GAP.md). PKDT,
  PSDT schedule, conditions, PKCU template link, data inputs, procedure tree, OnBegin/OnEnd/OnChange are all present
  in both (verified, xEdit).
- **Same templates by editor id**: Travel, Sandbox, ForceGreet, HoldPosition, UseWeapon, UseWeaponMultipleTargets,
  PatrolAndGuard, TravelSuspicious exist in Starfield.esm; FO4's AmbushTemplate does not (verified,
  docs/spikes/B4-mission-anatomy.md 1.6).
- **Differences are in flags and extras**: package-flag bit 29 means `Wear Sleep Outfit` in FO4 but
  `Weapon Drawn: Ready` in Starfield; Starfield adds flag bits 5, 11, 16, 19, 30, 31, a Package Group byte (XNAM), an
  animation flavor keyword (FLAV) and a Scene data input (STSC); FO4's Topic data input (TPIC) is gone (verified,
  xEdit).
- **Verdict: translate.** Map template link (PKCU) to the Starfield template with the same editor id, remap
  FormIDs in data inputs and conditions, rewrite the flag word bit by bit. Rebuild only packages on AmbushTemplate or
  other FO4-only templates.
- **Stack mechanics are shared CE lineage**: topmost package whose conditions pass runs; default package list sits at
  the bottom; aliases add packages at run time; combat preempts packages unless an override list says otherwise
  (Skyrim CK wiki, supported hypothesis for both games).

## How Fallout 4 does it

**PACK (3,828 in Fallout4.esm, verified count; layout verified, xEdit):**

| subrecord | content |
|---|---|
| PKDT | general flags u32, type (18 Package / 19 Package Template), interrupt override (None, Spectator, ObserveDead, GuardWarn, Combat, Command Travel, Command Activate, Leave Workstation), preferred speed (Walk, Jog, Run, Fast Walk), interrupt flags u16 |
| PSDT | schedule: month, day of week, date, hour, minute, duration |
| CTDA... | conditions (when the package may run) |
| idle block | idle animations (xEdit `wbIdleAnimation`; signatures not listed here) |
| CNAM / QNAM | combat style while active / owner quest (gives access to that quest's aliases) |
| PKCU | data input count, **package template** (PACK), version counter |
| ANAM + CNAM/PLDT/PTDA/TPIC/PDTO | data input values: type is one of Bool, Float, Int, Location, ObjectList, SingleRef, TargetSelector, Topic |
| UNAM/BNAM/PNAM | data input index, name, public flag |
| XNAM | empty marker |
| procedure tree | per branch: ANAM branch type, conditions, PRCB root (branch count, Repeat when Complete), PNAM procedure type string, FNAM Success Completes Package, PKC2 input indexes, PFO2 flag overrides |
| POBA / POEA / POCA | OnBegin / OnEnd / OnChange: idle + topic; script fragments in VMAD (`wbVMADFragmentedPACK`) |

- **Interrupt flags** (verified, xEdit): Hellos to player, Random conversations, Observe combat behavior, Greet corpse
  behavior, Reaction to player actions, Friendly fire comments, Aggro Radius Behavior, Allow Idle Chatter, World
  Interactions, Off For Important Scene.
- **General flags** (verified, xEdit, FO4 names): 0 Offers Services, 2 Must Complete, 3 Maintain Speed At Goal,
  4 Treat As Player Follower, 6/7 Unlock Doors At Package Start/End, 8 Request Block Idles, 9 Continue If PC Near,
  10 Once Per Day, 12 Skip Load Into Furniture, 13 Preferred Speed, 17 Always Sneak, 18 Allow Swimming, 20 Ignore
  Combat, 21 Weapons Unequipped, 23 Weapon Drawn, 27 No Combat Alert, 29 Wear Sleep Outfit.
- **Templates and procedures.** A package takes its procedure tree from its template and only sets the template's
  public data inputs (falloutck Package page, verified). Procedure names are strings in PNAM; the full list is not
  checked here (the CK wiki category did not render; unresolved).
- **Sandbox** (falloutck Sandbox page, verified as documented): moves inside a Location and uses furniture, idle
  markers and conversation; never completes on its own (pair it with Wait in a Simultaneous node); toggles for
  eating, sleeping, conversation, idle markers, furniture, sitting, wandering, special furniture; Energy scales
  sub-procedure duration; UseOwnedOnly restricts to owned targets (used by workshop towns); AllowedTargets filter;
  meals and sleep times from game settings; it eats without consuming inventory food.
- **Package stack.**
  - Sources: actor PKID list, quest alias packages (added at run time), DPLT default package list at the bottom
    (ck.uesp.net Package page; supported hypothesis that FO4 keeps the Skyrim order, alias packages on top by quest
    priority).
  - Override lists on NPC_: SPOR spectator, OCOR observe dead body, GWOR guard warn, ECOR combat, FCPL follower
    command, RCLR follower elevator (verified, xEdit). The PKDT interrupt-override enum says which slot a package
    fits.
  - Evaluation: the topmost package whose conditions pass runs; re-evaluation is periodic and forced by
    `Actor.EvaluatePackage(bool abResetAI = false)` (falloutck EvaluatePackage, verified as documented).
- **Idle markers and furniture**: IDLM 39, FURN 598 (verified counts); FURN carries a marker list and an `Ignored By
  Sandbox` flag (verified, xEdit).
- **Vanilla example** (verified, B4 1.6): Preston has own Sandbox + Travel packages, 8 alias packages in
  DialogueConcordArea (ForceGreet, Travel x5, custom), and MQ102 adds a UseWeapon package and an override list of 3
  HoldPosition. The museum raiders use UseWeapon, HoldPosition, TravelSuspicious, PatrolAndGuard templates.

## How Starfield does it

**PACK (3,548 in Starfield.esm, verified count; layout verified, xEdit SF1):**
- **Same:** PKDT layout and enums (type, interrupt override, preferred speed, interrupt flags), PSDT, conditions, idle
  animations, CNAM, QNAM, PKCU, data inputs with the same type strings, UNAMs, procedure tree with the same branch
  subrecords, POBA / POEA / POCA.
- **New:** FLAV `Anim Flavor` keyword; STSC Scene
  as a data-input value; NNAM branch note; XNAM is now a `Package Group` byte (xEdit's value names are its own
  guesses: Sandbox, HoldPosition, Patrol, FollowPlayer, UseWeapon, TravelBetweenLandings, DefaultPassengerPackage
  ...).
- **Gone:** TPIC topic value and BNAM in data inputs; the PDTO topic list remains on OnBegin/OnEnd/OnChange
  (verified, xEdit).
- **Flag word changes** (verified, xEdit `wbPackageFlags`): new 5 After Combat Reset, 11 Low Priority, 16 Disable
  Headtracking, 19 Disable Advanced Traversals, 30 Group Package, 31 Weapon Drawn: Alert; **bit 29 is Weapon Drawn:
  Ready** (FO4: Wear Sleep Outfit). Bits 0-4, 6-10, 12, 13, 17, 18, 20, 21, 23, 27 keep their names.
- **New NPC_ package hooks** (verified, xEdit): RPLD sound detection and RPLI sight detection package lists; RDSA
  reaction-radius entries each carry an optional package list (FLST); FLEE settings. These sit next to the six
  FO4 override lists, which all remain.
- **Advanced traversal** (climb/jump navmesh links) is new in CE2: the flag "Disable Advanced Traversals" exists
  (verified); how the navmesh marks traversals is in [docs/actors/npc-navigation.md](../../actors/npc-navigation.md)
  territory (not re-checked here).
- **Counts:** IDLM 18, FURN 899, PKIN 11,281 (verified, sf_esm.json).

## Mapping for the port

| FO4 piece | Starfield counterpart | verdict | notes |
|---|---|---|---|
| PKDT | PKDT | data copy | identical layout and enums |
| general flags bit 29 Wear Sleep Outfit | bit 29 Weapon Drawn: Ready | translate | clear bit 29; Starfield has no sleep outfit (SOFT is space outfit) |
| other general flags | same bits | data copy | leave SF-only bits 5/11/16/19/30/31 at 0 |
| PSDT schedule | PSDT | data copy | game hours: our planet's day length must match FO4's 24 h clock or schedules drift (unresolved) |
| PKCU template link | PKCU | translate | map by template editor id (B4 1.6 table); AmbushTemplate has no counterpart |
| data inputs (refs, locations, target selectors) | same types | translate | deterministic FormID map, as the doors use |
| TPIC topic input | none | rebuild | move to a scene or OnBegin topic; count affected packages first |
| conditions | conditions | translate | CTDA function table diff still open (next-phase note) |
| procedure tree in FO4-only custom templates | procedure tree | translate | procedure type is a string; check each is a CE2 procedure |
| VMAD package fragments | VMAD | script shim | recompiled with the rest of Papyrus |
| PKID / DPLT / alias packages | same | translate | |
| SPOR/OCOR/GWOR/ECOR/FCPL/RCLR | same | translate | |
| (none) | RPLD / RPLI / RDSA package lists | leave empty | or fill from Starfield templates via inherited AI data |
| IDLM / FURN markers | IDLM / FURN | translate | furniture entry animations come from the animation track |
| XNAM marker | XNAM Package Group | translate | value semantics unresolved; copy from the matching Starfield template package |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Packages on FO4-only templates** (AmbushTemplate, any custom template Starfield lacks): copy the FO4 template
  itself as our own PACK template (type 19), provided its procedure strings exist in CE2 (unresolved per procedure).
- **Topic inputs:** packages that make an actor say a topic through TPIC need a scene or fragment instead.
- **Sleep and eat:** Sandbox toggles exist; whether CE2 sandboxers find FO4 beds and chairs depends on converted FURN
  markers and keywords (unresolved; one Concord settler test).
- **SFSE:** not needed. **CK:** not needed for conversion; useful to eyeball one converted package.

## Port status and links
- Mission packages use Starfield templates directly: Preston on Sandbox 00002CB1 (verified, B4 section 3 and the
  mission doc).
- Mutagen types PACK on both sides (verified, next-phase note section 1).
- Next steps already planned: N3 "faction and package converter", in-game check "one Concord settler sandboxing and
  one guard patrolling" ([next-phase note](../next-phase/npcs-ai-factions-dialogue-quests.md), section 9).
- Navigation side: docs/actors/npc-navigation.md, docs/actors/navmesh-conversion.md.

## Open questions and cheap checks
- Procedure strings: list distinct PNAM procedure types in both esm files and diff (Mutagen or raw scan, offline).
- Template coverage: list every PKCU target editor id in Fallout4.esm with counts; mark those missing in
  Starfield.esm.
- TPIC usage: count FO4 PACK data inputs of type Topic.
- Bit-29 usage: count FO4 PACK with Wear Sleep Outfit set.
- Alias-package order in CE2: one test quest with an alias Travel package over an actor Sandbox package.
- `EvaluatePackage` in Starfield: grep `Actor.psc` in Tools\ContentResources.zip for the signature.
- XNAM Package Group: histogram of values per template in Starfield.esm.

## Sources
- xEdit: https://github.com/TES5Edit/TES5Edit (dev-4.1.6, `Core/wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`,
  `wbDefinitionsCommon.pas`), read locally.
- Fallout 4 CK wiki: https://falloutck.uesp.net/wiki/Sandbox_Package,
  https://falloutck.uesp.net/wiki/EvaluatePackage_-_Actor, https://falloutck.uesp.net/wiki/Package.
- Skyrim CK wiki (same lineage, used as supported hypothesis): https://ck.uesp.net/wiki/Package.
- Repo: docs/FORMAT-GAP.md, docs/spikes/B4-mission-anatomy.md (1.6), docs/measurements/*.json,
  ../next-phase/npcs-ai-factions-dialogue-quests.md.
