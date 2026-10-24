# Workshop and settlements (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `Core/wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`.

**Read first:** [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md) (sections
2.4, 3.3, 4-6). It already covers: build mode opening on a `WorkshopKeyword` (054BA7, same id in both games) ACTI, the
`OutpostPlayerHouseActivator` pattern, `OutpostBuildAreaRadius`, the FO4 workbench CONT + `WorkshopScript`, FO4 link
keywords, ratings list, build budget AVs 348-34B, the hybrid recommendation and checks P1-P8. This file adds only the
mechanism detail that note lacks.

## In short
- FO4 settlements = a native build mode (placement, snapping, scrap, budget) plus a Papyrus rules layer
  (`WorkshopParentScript` quest, `WorkshopScript`, `WorkshopObjectScript`, `WorkshopNPCScript`) that computes ratings,
  happiness, recruitment, vendor income and attacks (**supported hypothesis** for the script names, see the next-phase
  note; rules **verified** from https://falloutck.uesp.net/wiki/Workshop).
- Starfield keeps the native layer and the workshop condition functions, and swaps the rules for outposts (beacon,
  extractors, cargo links, crew) (**verified** for condition functions and bench types, xEdit).
- FO4's build menu is a FLST tree (`WorkshopMenuMain`); Starfield's build menu is keyword categories
  (`OutpostCategory*`) on the activator (**supported hypothesis** for FO4, one modder thread; **verified** keyword set for
  Starfield, docs/terrain/stations.md:61-72).
- Verdict: native build mode **reused** as placement only; FO4 menu tree **translated** into our own category keywords;
  settlement rules **rebuilt** as own Papyrus; DLC packs are **data** on top. SFSE only for a measured gap.

## How Fallout 4 does it (detail beyond the next-phase note)

### Build menu structure
- `WorkshopMenuMain` (FLST) holds the top-level menus; each menu with children is a FLST; a leaf is a "recipe filter"
  KYWD; a COBJ shows in the leaf whose keyword is in its `FNAM` category array (**supported hypothesis**: modder report,
  https://forums.nexusmods.com/topic/5038065-adding-a-new-workshop-menu-via-the-creation-kit; COBJ `FNAM` "Category"
  array **verified**, xEdit).
- A submenu FLST needs an icon keyword as its first entry plus an art object for it, else the submenu does not open;
  a menu should hold either submenus or recipes, not both (**supported hypothesis**, same thread).
- Workshop recipes are COBJ like bench recipes: `FVPA` components (CMPO or items), `CNAM` the STAT/FURN/ACTI built,
  conditions (perks such as Local Leader, DLC ownership) (**verified** layout, xEdit; perk gating **supported**).
- Scrap: objects tagged by a `WorkshopRecipeFilterScrap` recipe can be scrapped, not moved; the recipe decides what goes
  into the workshop container (**verified**, falloutck Workshop page). Junk MISC break into CMPO via `CVPA`
  ([items note](items-crafting-modding.md)).

### Native hooks the rules layer uses
- ObjectReference events: `OnWorkshopObjectPlaced`, `OnWorkshopObjectMoved`, `OnWorkshopObjectGrabbed`,
  `OnWorkshopObjectDestroyed`, `OnWorkshopObjectRepaired` (**verified**: pages exist at
  https://falloutck.uesp.net/wiki/OnWorkshopObjectPlaced_-_ObjectReference and siblings).
- Condition functions: `GetWorkshopResourceDamage` (661), `GetWorkshopObjectCount` (691), `CanProduceForWorkshop`
  (734), `LocationHasPlayerOwnedWorkshop` (788), `IsInWorkshopMode` (792) (**verified**, xEdit FO4 condition table).
- Default objects `WMIK` "Workshop Misc Item Keyword" and `WPOK` "Workshop Player Ownership" (**verified**, xEdit DFOB
  list; both also in the Starfield list).
- Encounter zone flag `Workshop` on ECZN (**verified**, xEdit; meaning undocumented on falloutck, see
  [leveled lists note](leveled-lists-and-encounter-zones.md)).
- Map marker type 13 "Settlement" (**verified**, xEdit REFR marker enum).

### Rules (Papyrus layer), numbers from the falloutck Workshop page (**verified** as documented)
| Rule | Value |
|---|---|
| Per-settler happiness | food +20 (cap 30 if unmet), water +20 (cap 30), bed +10, sheltered bed +10 (cap 60 if unmet), safety +20 if defense >= population |
| Settlement happiness | average of settlers; bonus objects (bars, stores, clinics) divided by settler count; quest happiness clamped -50..+40, drifts to 0 daily |
| Recruitment | `iBaseMaxNPCs` 10 (+ Charisma), `attractNPCDailyChance` 0.1, `attractNPCHappinessMult` 0.5, `iMaxBonusAttractChancePopulation` 5, `iMaxSurplusNPCs` 5 |
| Vendor income | `minVendorIncomePopulation` 5, `maxVendorIncome` 50.0, `vendorIncomePopulationMult` 0.03, `vendorIncomeBaseMult` 2.0 |
| Defense | higher defense lowers attack chance and damage; attackers spawn at `WorkshopLinkAttackMarker` markers via radiant quests (rate **unresolved**) |
| Ownership | low happiness can make a settlement "unally" (lose ownership) |
| Supply lines | surplus shared with settlements linked by supply lines (provisioner settlers); mechanism detail **unresolved** (likely WorkshopParent script plus caravan packages) |

### DLC workshop packs
- Files `DLCworkshop01.esm`, `DLCworkshop02.esm`, `DLCworkshop03.esm` (**verified**, xEdit `wbOfficialDLC`); they are
  Wasteland Workshop (cages, arena), Contraptions (conveyors, logic, manufacturing) and Vault-Tec Workshop (Vault 88)
  (**supported hypothesis**: names from general knowledge, mapping not read from the files). Far Harbor and Nuka-World
  add their own settlements and menus. Record counts per DLC are not measured yet (only Fallout4.esm is,
  docs/measurements/fo4_esm.json).
- Contraptions need power/logic signal propagation, which is native workshop wiring (**unresolved** how much is native
  vs script).

## How Starfield does it
- Same native placement layer: `WorkshopKeyword` activation, snapping, budget actor values (next-phase note).
- Condition functions 661/691/734/788/792 keep their names (**verified**, xEdit SF table); default objects WMIK/WPOK
  kept (**verified**, xEdit).
- Perk entry points `Mod Workshop Production Timer` (161), `Mod Workshop Build Cost` (174), `Mod Workshop Repair Cost`
  (175) exist only in the Starfield list (**verified**, xEdit).
- Challenges/activities: a "Build Workshop Item" activity (`BGSBuildWorkshopActivity`, track target Structure / Other /
  Decoration / Furniture, only-unique-planets) (**verified**, xEdit) shows the engine counts built items by category.
- Bench types add Extractor (10) and Research (11) (**verified**, xEdit WBDT enum). Extractors pull IRES resources;
  IRES `NAM3` "Production Interval (hours)" GLOB and `NAM1` Resource AV (**verified**, xEdit) suggest production is
  data-driven per resource (**supported hypothesis**).
- `ObjectReference` workshop events in Starfield Papyrus: a modder registers for `OnWorkshopObjectRemoved` (**supported
  hypothesis**, https://forums.nexusmods.com/topic/13500841-can-outposts-be-deleted-in-a-papyrus-script); the full set
  is **unresolved** (next-phase check P4).
- Encounter leveling on LCTN keeps a `Workshop` flag (**verified**, xEdit SF LCTN DATA), so "this location is a
  workshop" still exists as data.
- Gone: settlers' happiness and attack rules, supply lines, FLST-driven menu. New: beacons, cargo links, crew
  assignment, outpost habs, research gating (all fenced out per the own-ecosystem decision).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| Workbench CONT + WorkshopScript | WorkshopKeyword ACTI (done, v6) | translate | next-phase note 2.4; P1 crash lead first |
| Build area primitives / radius | `OutpostBuildAreaRadius` PRPS | translate | primitive shapes have no counterpart: **unresolved**; radius only today |
| `WorkshopMenuMain` FLST tree | `OutpostCategory*` keywords on the ACTI + our own category keywords | rebuild | one own keyword per FO4 leaf; how a COBJ joins a category is next-phase P5 |
| Workshop COBJ (`FNAM` categories) | COBJ (no FNAM) | translate | category must move to the mechanism P5 finds |
| Scrap recipes | Starfield scrap in build mode | translate | **unresolved** whether Starfield scraps pre-placed refs |
| Workshop events | Starfield events (subset) | script shim | P4 decides; SFSE only if a needed event is missing |
| Ratings / happiness / recruitment / vendor income | none | rebuild (own Papyrus) | numbers above, read from the user's files at build time |
| Attacks (radiant) | none | rebuild | needs NPC/AI basics and our own quests |
| Supply lines | cargo links (different) | rebuild | provisioner packages later |
| Contraptions logic | outpost power/wiring | unresolved | per-object check |
| ECZN `Workshop` flag | LCTN `Workshop` flag | data copy | via the leveled-lists note's ECZN fold |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Own settlement quest and scripts implementing the table above (written fresh from documented behaviour; FO4 vanilla
  sources ship with the FO4 CK as `Data\Scripts\Base.zip`, **verified** via
  https://falloutck.uesp.net/wiki/Papyrus_FAQs, but the repo must not copy them; owner question P8).
- Menu tree conversion: FO4 FLST tree to own category keywords plus menu art; check whether Starfield's build UI takes
  icons from keywords or ARTO (**unresolved**).
- SFSE: only if Starfield lacks a placed/moved/destroyed event or a budget accessor (P4). The CK is useful to inspect
  vanilla outpost categories and to author menu art, not required for data writing.

## Port status and links
- 29 workshops promoted to WorkshopKeyword ACTIs with the vanilla category set and radius 250; 269 benches on vanilla
  FURNs; nothing tested in game (**verified** offline, docs/terrain/stations.md:104-129).
- Plan, options and checks: ../next-phase/doors-activators-workshops.md sections 4-6.
- Item/component side: [items-crafting-modding.md](items-crafting-modding.md).

## Open questions and cheap checks
- Dump `WorkshopMenuMain` and two levels of child FLSTs from Fallout4.esm with Fo4Export (confirms the menu model).
- Count COBJ in Fallout4.esm whose `BNAM` is the workshop keyword vs bench keywords (scope of the build menu).
- Grep Starfield `ObjectReference.psc` in `Tools\ContentResources.zip` for `OnWorkshop` (= P4).
- Grep FO4 `WorkshopParentScript.psc` (in Base.zip, user's PC only) for attack timer and supply-line functions; record
  names only.
- Per DLC: record counts of the three DLCworkshop esms (extend docs/measurements).

## Sources
- xEdit definitions: https://github.com/TES5Edit/TES5Edit (Core/wbDefinitionsFO4.pas, Core/wbDefinitionsSF1.pas)
- https://falloutck.uesp.net/wiki/Workshop
- https://falloutck.uesp.net/wiki/OnWorkshopObjectPlaced_-_ObjectReference (and Moved, Grabbed, Destroyed, Repaired)
- https://forums.nexusmods.com/topic/5038065-adding-a-new-workshop-menu-via-the-creation-kit
- https://forums.nexusmods.com/topic/13500841-can-outposts-be-deleted-in-a-papyrus-script
- https://falloutck.uesp.net/wiki/Papyrus_FAQs
- Repo: docs/terrain/stations.md; ../next-phase/doors-activators-workshops.md; docs/measurements/*.json
