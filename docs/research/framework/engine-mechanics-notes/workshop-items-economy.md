# Workshop, items and economy: research findings and question framework

Area: FO4 settlements and workshop (build mode, ratings, settlers, supply lines, attacks) against Starfield outposts and
build mode; Sim Settlements and Starfield outpost frameworks; Automatron's robot workbench and the DLC workshop packs;
weapons, armor, object mods, attach points, benches, junk and components, legendaries (LGDI); caps, vendors, barter,
leveled lists, loot and encounter levels. Author: Claude (research agent), 2026-10-19.

Builds on, and does not repeat: `../../engine-mechanics/workshop-and-settlements.md`, `items-crafting-modding.md`,
`economy-vendors-barter.md`, `leveled-lists-and-encounter-zones.md`, `dlc-mechanics.md`,
`starfield-systems-to-reuse.md`, and `../../next-phase/doors-activators-workshops.md` (checks P1 to P8; this file
refers to them as "P1" and so on). Labels: **verified** (read on the source page or in a file), **supported
hypothesis**, **unresolved**.

Pages I could not read: the Nexus Mods proxy rate-limited me (HTTP 429) on gamingbolt.com "Everything you need to
know about Fallout London", nexusmods.com/fallout4london/mods/547 and nexusmods.com/fallout4/articles/1597 (SKK
Settlement Attack System notes). Nothing in this file comes from those pages.

## What the community and tools offer today

### Build mode and build menu
- **The build menu category list is a FormList plus keywords on the build activators.** Community Categories
  (MrTrilB, v1.0.5, Sept 2024) exists because adding a category means hard-editing FLST `OutpostRecipeCategories`
  and the activators `OutpostBeaconActivator` 002C60E9, `OutpostPlayerHouseActivator` 00024DC7 and
  `SFBGS006_SBShipDecorationMarker` 002EF273. Keywords on those forms filter constructible objects into categories.
  The page says there is no Papyrus way to do this, and that mods editing the same forms overwrite each other.
  **verified** as described (https://allmods.net/starfield-mods/starfield-modders-resources/community-categories-v1-0-5/).
  This largely answers P5: a COBJ joins a category through a keyword that the FLST and the activator list. Which
  field on the COBJ (or on its created object) carries the keyword is still **unresolved** (the page does not say).
- The ship builder uses the same pattern: Ship Builder Categories (rux616, v1.21.0, updated 2026-04-11) adds `SBC_*`
  keywords to FLST `ShipModuleRecipeCategories` 002C2E94, has a failsafe since v1.21.0 so that its categories reappear
  at the end of the list if another mod overwrites the FLST, and was rebuilt in the Starfield CK in v1.10.0 after
  earlier Spriggit + xEdit builds. **verified** (https://www.nexusmods.com/starfield/mods/7310/).
- Extended Outpost Builder Categories (Javapower77, v1.2, March 2024, `OutpostBuildCategories.esm`) adds empty
  categories and needs one patch per outpost mod. The author reports many menu items losing titles after xEdit edits.
  **verified** as described (https://www.nexusmods.com/starfield/mods/8631).
- Build mode outside the outpost beacon is proven by Papyrus-only mods (SKK Player Homes Anywhere: interior
  decorator, about 250 m, refuses ship interiors and procedural cells). **verified** as described in the next-phase
  note (https://www.nexusmods.com/starfield/mods/7271).
- Build area radius and limits are routinely raised by mods: Outpost Stats Enhanced (lxyman, v1.11, Aug 2026) goes
  150 to 200, says 300 is the maximum and may hurt weaker PCs, and reports a build page that "spins continuously";
  ZeeOgre's AIO Gameplay Tweaks (v1.0.0, June 2025) also raises radius and build limits. **verified** as described
  (https://www.nexusmods.com/starfield/mods/17637, https://www.nexusmods.com/starfield/mods/10558).

### Settlement-scale frameworks
- **No Sim Settlements for Starfield exists that I could find.** kinggath said in Sept 2023 that Starfield's outposts
  make people "meaningless", that colonists only add production, and that he might build "Sim Colonies" after the CK
  if still interested; no firm plan. **verified** as reported
  (https://wccftech.com/starfields-outposts-meaningless/amp/). Whether anything followed: **unresolved** (searches
  found nothing).
- The largest Starfield outpost overhaul found: TG's Galactic Colonies Expanse (Tank-girl444, Nexus 8973): turrets and
  mechs for defence, production lines, farming with 40+ plants, a food printer bench; NPC survival needs were only
  "planned". **verified** as reported (https://www.dsogaming.com/mods/starfield-dlc-sized-expansion-mod-colonies-giant-mechs-defense-turrets-farming-system,
  https://www.pcgamesn.com/starfield/mod-city-builder). It shows outposts can carry defence and production; it does not
  show settler needs or happiness in CE2.
- Starfield vanilla (Free Lanes update, 2026-04-07) added a **Shared Outpost Container** that moves items and
  resources between outposts that have one. **verified** (https://bethesda.net/en/article/7IxZSKYwYm1oDr57rXDx4C/starfield-free-lanes-terran-armada).
  That is the nearest native analog to FO4 supply lines' shared workshop storage (**supported hypothesis** that it can
  be reused outside outposts; not tested).
- FO4 side: Workshop Framework (v2.6.1) is "a framework for other mods to alter features about the settlement system
  without having to overwrite vanilla files": bed-capped settlers, Charisma-scaled max NPCs, consuming linked
  settlements' resources, auto-assignment, layout import/export, F4SE power-grid scan and repair, a Max Threads
  setting (10 to 50) traded against stability. **verified** as described
  (https://wiki.simsettlements2.com/gameplay/basics/workshop-framework,
  https://wiki.simsettlements2.com/getting-started/known-issues).
- Sim Settlements 2 (v3.8.0, Oct 2026) requires Workshop Framework; plots, building plans by function, settler
  SPECIAL, add-on packs, city plans; permissions forbid converting its files to other games. **verified**
  (https://www.nexusmods.com/fallout4/mods/47976).

### Items, mods, legendaries
- LGDI is editable by modders: Legendary Effect Overhaul (DankRafft, v1.1.0, Nov 2023, made in SF1Edit) edits FLST,
  KYWD, **LGDI**, MGEF, ENCH, OMOD and PERK, adds research projects to unlock legendary crafting, and moved strings
  into string files so translations need no ESM override. **verified** as described
  (https://www.nexusmods.com/starfield/mods/1394).
- Starfield's own legendary system grew in 2026: Free Lanes added legendary rerolls (X-Tech + credits), a Tier 4
  effect slot once an item reaches rank three, an "Upgrade Module" slot, and quality tiers Superior and Exceptional;
  Terran Armada ($9.99, same day) added Delta, a robot companion. **verified** (Bethesda article above). Legend 'O'
  Matic expansions build on that and require Starfield 1.16.242 and Free Lanes. **verified**
  (https://www.nexusmods.com/starfield/mods/17225).
- OMOD basics in Starfield: one mod per attach point, adding to an occupied point replaces the old mod; weapon quality
  tiers have no attach point and stack cumulatively. **verified** as documented
  (https://starfieldwiki.net/wiki/Starfield:Object_Mods).
- Weapon balancing in xEdit: quality OMODs (`Quality_##`) carry the damage tiers, `Quality_TiersAny` includes them
  with minimum levels; craftable "internal" tiers are COBJs. **verified** as described in a tutorial
  (https://www.nexusmods.com/starfield/articles/659).
- Weapon animation remains the weak spot: a 2023 FO4-to-Starfield weapon port shipped only as a mesh replacer with
  hand-gap and animation issues; a May 2026 proof of concept drives a crude first-person animation through effect
  sequences. **verified** as described (https://www.nexusmods.com/starfield/mods/5219,
  https://www.nexusmods.com/starfield/mods/17294). Ties to the animations area.
- Robots: kine's Terran Robot Frames (June 2026) makes Terran robot frames moddable "at the workbench, like a
  spacesuit" (cosmetic only) and adds rebuilding frames from salvaged parts. **verified** as described
  (https://www.nexusmods.com/starfield/mods/16345). That is the closest Starfield precedent to Automatron's robot bench,
  and it uses the armor bench path rather than a native robot bench (**supported hypothesis**; the page does not say
  which bench type).
- Junk to resources: Galactic Junk Recycler is built from the outpost builder and works like a vending machine that
  turns weapons, armor, books and junk into resources. **verified** as described
  (https://starfieldportal.com/article/starfield-junk-now-become-useful-resources, Nexus 7538). Starfield has no native
  scrap-to-components loop for loose junk (**supported hypothesis**: the mod exists to add one).

### Economy, vendors, leveled lists
- Vendor restock: LarannKiar's SFSE plugin (v5.0, supports 1.16.244) changes restock to one day, from what its page
  calls the default 48 hours; no GMST named. **verified** as described (https://www.nexusmods.com/starfield/mods/6329).
- Leveled Vendor Credits (AllensProject, Nov 2023) scales vendor credits with player level by overriding leveled
  lists and, where the list level was capped, adding **conditions on player level** to entries; no new records.
  **verified** as described (https://www.nexusmods.com/starfield/mods/6868). So vendor currency lives in leveled lists
  in the merchant container, as in FO4.
- Starfield leveled list defaults: uniform pick among entries at the highest level not above the player, flags All
  Levels / Each / Use All. **verified** as documented (https://starfieldwiki.net/wiki/Starfield:Leveled_Lists).
- Currency look: mods change the credit item's mesh only (e.g. Nexus 4660, Oct 2023, "Replaces Cred Stick mesh"); I
  found no Starfield mod that renames "Credits" in the barter or HUD strings. **verified** for 4660
  (https://www.nexusmods.com/starfield/mods/4660); absence **unresolved** (search only).

### Project facts to build on (already measured, from the repo)
- Starfield Papyrus keeps `OnWorkshopObjectPlaced` (and, by omission from the FO4-only list, Moved and Grabbed), but
  lacks `OnWorkshopObjectDestroyed`, `OnWorkshopObjectRepaired`, `RecalculateResources`,
  `WaitForWorkshopResourceRecalc`, `RemoveComponents`, `StoreInWorkshop`, `SellItem`, `RaidTargetsAvailable`,
  `OpenWorkshopSettlementMenu(Ex)`; `WorkshopParentScript` and `WorkshopScript` are absent. **verified** (PC probe job
  15, docs/research/engine-mechanics/papyrus-and-script-extenders.md:142-170). This partly answers P4.
- FO4 DLC script sources on the owner's PC: DLC01 483, DLC02 43, DLC03 830, DLC04 908, DLC05 40, DLC06 92 `.psc`.
  **verified** (same file). Contraptions (DLC05) has only 40 scripts, which hints its logic is mostly native
  (**supported hypothesis**).

## Precedents and lessons
- **Workshop script overwrites are the main conflict source in FO4.** The SS2 known-issues list names mods that replace
  `Workshop.pex`, a weapon whose `WorkshopParentObject` script breaks Workshop Framework, and mods with their own
  workshop scripts (Conquest) where SS2 plots fail. **verified**
  (https://wiki.simsettlements2.com/getting-started/known-issues). Lesson: our settlement layer should be our own
  scripts with our own names, never named like vanilla, with a public extension API (Workshop Framework's model).
- **Script load near dense areas causes lag** (SS2 flags settlements near Sanctuary) and scrap-everything mods break
  precombines and performance. **verified** (same page). Lesson: settlement logic should be event-driven and cheap;
  scrapping pre-placed world objects is a precombine risk in CE2 too (**supported hypothesis**).
- **Load-order fights over shared FLSTs**: both the Community Categories and Ship Builder Categories authors built
  workarounds for menu FLST overwrites. **verified** (sources above). Lesson: we own the build activators we place, so
  give them our own category FLST and keywords and never touch Starfield's `OutpostRecipeCategories`.
- **Fallout London kept a workshop**: six settlements, a workshop object, scrap for materials; players report
  settlements as bugged (crashes, clipping). **verified** as reported
  (https://primagames.com/tips/best-base-and-settlement-locations-in-fallout-london). Lesson: a total conversion can
  ship a smaller settlement set; stability is what players judge.
- **kinggath's critique** of Starfield outposts (people don't matter) is the gap a Fallout settlement layer fills.
  **verified** as reported (wccftech above).
- **SS2 forbids conversion to other games** in its permissions. **verified** (Nexus 47976). Lesson: the launcher must
  convert only Bethesda's FO4 masters (and DLC), and skip third-party plugins unless their authors allow it.

## Possibilities and hard limits in CE2
- Possible: native placement, snapping and budget from a `WorkshopKeyword` activator anywhere, including interiors
  via script (**supported hypothesis**, SKK mod and project v6 data, not tested in our overlay).
- Possible: own build categories by keyword plus our own FLST on our own activators (**supported hypothesis** from the
  category mods; untested with a non-Starfield activator).
- Limit: no Papyrus path to add categories at run time (**verified** as reported by Community Categories).
- Limit: no native settler happiness, recruitment, attacks or supply lines; all script (**verified** by absence of
  the scripts, project probe).
- Limit: no `RemoveComponents` or `RecalculateResources` natives; any "pay components from workshop" logic must use
  `RemoveItem` on our resource items (**verified** names missing; workaround **supported hypothesis**).
- Possible: shared storage between build sites (Shared Outpost Container) (**supported hypothesis** for reuse).
- Possible: legendary effects as native LGDI with rank slots, now up to a Tier 4 slot and rerolls in vanilla
  (**verified** record and feature); whether LGDI rolls drive FO4's "one star" pattern unchanged is **unresolved**.
- Limit: no CMPO; Starfield crafting inputs are IRES and the CK reportedly allows only IRES in CVPA (**verified**
  layout note in xEdit, see the items page).
- Possible: vendor stock and credits through leveled lists with conditions (**verified**, mod 6868).
- Limit: renaming the currency in the UI has no known precedent (**unresolved**).
- Limit: no live robot bench station in Starfield (DONOTUSE station, see dlc-mechanics.md); armor-bench modding of
  robot frames is the community path (**supported hypothesis**).
- Possible: FO4's REFR power grid has no counterpart beyond `XPLK` "Power Links" (**verified**, xEdit, dlc page).

## Question framework

Phases: **NG** new game, **INT** interiors, **QP** quests/people, **FS** Fallout systems, **REL** release.

### 1. Build mode and build menu (placement engine)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| B1 | Which field links a COBJ to a build category: a keyword on the COBJ, on its created object, or a FLST? | Decides how the converter writes FO4's 1,000+ workshop recipes | categories are KYWDs listed in FLST `OutpostRecipeCategories` and on the activators (Community Categories page) | SfInspect dump of 5 vanilla outpost COBJ, their CNAM objects and that FLST (= P5) | blocks B2, B3 | FS | **key** |
| B2 | Does an activator we own, with our own FLST and keywords, show only our categories and none of Starfield's? | Keeps Starfield's outpost parts out (the fence) and avoids load-order fights | v6 ACTIs copy 00024DC7 with vanilla categories | CK test cell: one ACTI, one own keyword, two COBJ | needs B1 | FS | **key** |
| B3 | Can the FO4 menu tree (FLST `WorkshopMenuMain`, 2+ levels) be flattened into Starfield's category bar, and how deep can Starfield nest? | FO4 has nested submenus; Starfield appears flat | FO4 tree from one modder thread; Starfield depth unknown | Fo4Export dump of the tree; CK look at vanilla category FLST nesting | needs B1 | FS | |
| B4 | Where does Starfield take category icons and labels from (keyword name, ARTO, a Scaleform asset)? | FO4 uses icon keywords plus ARTO; missing icons break submenus in FO4 | unresolved | CK: open a vanilla category keyword; check Interface files list | B2 | FS | |
| B5 | Do player-built objects persist and stay in place in our overlay worldspace across save, reload and cell reset? | Without it the workshop is pointless | P7, unresolved | build-mode v0 at Red Rocket (next-phase step 5) | blocks all settlement work | FS | **key** |
| B6 | Can build mode scrap pre-placed FO4 references (cars, debris) and what happens to precombined geometry? | FO4 settlements depend on scrapping clutter | Starfield scrap of pre-placed refs unresolved; FO4 mods that scrap everything break precombines | CK test: mark one placed STAT with a scrap recipe; check in game with and without precombines | ties to the physics/precombine work | FS | **key** |
| B7 | What build budget do we use: Starfield's outpost limits or FO4's triangle/draw AVs 348-34B? | Too high crashes, too low feels un-Fallout | mods raise radius to 200-300 with side effects (17637, 5576) | read AV defaults in both masters; measure FPS at Sanctuary with 300 objects | B5 | FS | |
| B8 | Does build mode open inside FO4 interiors (Vault 88, Home Plate) on our converted cells? | Vault-Tec Workshop and player homes | SKK mod works in most interiors, not procedural ones | INT test after first interior lands | INT pipeline | INT | |
| B9 | Which FO4 workshop events can we drive from Starfield's kept events (Placed, Moved, Grabbed) and how do we replace Destroyed and Repaired? | Ratings must update on every change | Starfield lacks Destroyed/Repaired (probe job 15); `OnWorkshopObjectRemoved` reported | grep Starfield `ObjectReference.psc` for all `OnWorkshop*` names (P4 rest) | blocks S1 | FS | **key** |

### 2. Settlement rules layer (ratings, settlers, happiness, recruitment)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| S1 | Where do we store per-settlement ratings: actor values on the workbench ref (as FO4), globals, or a script struct? | Conditions, dialogue and UI read them | FO4 uses AVs on the workshop; Starfield has resource AVs (IRES NAM1) | CK: check whether our own AVIF on a REFR survives save/load; read FO4 workshop AV list from Fallout4.esm | B9 | FS | **key** |
| S2 | P8: may the launcher decompile or read the user's FO4 workshop scripts at install time, or must FO4SF scripts be written fresh? | Decides cost of the rules layer by weeks | sources exist on the PC (7,854 + DLC) | owner decision | blocks S3 | FS | **key** |
| S3 | Which FO4 numbers (happiness, recruitment, vendor income) live in GLOB or quest properties that the launcher can read from the user's files? | Lets us ship rules without Bethesda text | values documented on falloutck Workshop page | Fo4Export of `WorkshopParent` quest VMAD properties and GLOBs | S2 | FS | |
| S4 | How do settlers get assigned to beds, crops and guard posts in CE2: our own furniture ownership plus packages, or Starfield's crew assignment? | Crew assignment is fenced out; sandboxing must work | Workshop Framework auto-assigns; Starfield crew slots in outposts (mod 17637 adds slots) | CK test: an NPC with our faction and a package that uses owned furniture | AI packages area | FS | **key** |
| S5 | Can the recruitment beacon (radio) spawn and walk settlers to a settlement across our planet? | Core FO4 loop | none | prototype after AI basics; check navmesh across overlay landings | world/navmesh area | FS | |
| S6 | Is the settlement status shown on the workbench prompt, a message, or a custom UI (Scaleform/SWF)? | Players need ratings visible | FO4 uses workshop HUD; Starfield has no such HUD | decide UI path with the UI area; a message box first | UI area | FS | |
| S7 | Do we want a Workshop-Framework-like public API (events, registration) for future add-ons? | Avoids the FO4 script-overwrite mess | WF and SS2 lessons (verified) | design decision, written in docs/ai/decisions.md | S1 | REL | |
| S8 | How many settlements in the first release, and which ones (Sanctuary, Red Rocket, Abernathy...)? | Breadth vs stability (Fallout London players call settlements buggy) | 29 workshops exist as ACTIs in v6 | owner decision with a test list | B5 | FS | |

### 3. Supply lines, attacks, ownership and faction ties
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| T1 | How does FO4 implement supply lines (shared storage, caravan packages, linked refs)? | Rebuilding needs the model | unresolved on our pages | grep user's FO4 `WorkshopParentScript.psc` for caravan/link function names (names only) | S2 | FS | **key** |
| T2 | Can Starfield's Shared Outpost Container (Free Lanes) serve as linked workshop storage outside outposts? | Native, cheap supply-line storage | feature verified on bethesda.net | SfInspect the container base and its script; CK test with two of our workbenches | T1 | FS | **key** |
| T3 | How are FO4 settlement attacks chosen (timer, Story Manager event, defense formula) and which Story Manager events does Starfield still fire? | Starfield dropped several SM events (quests.md) | attack rate unresolved | grep FO4 workshop scripts and SMQN nodes; compare with Starfield's SM event list | quests area | FS | **key** |
| T4 | Do settlers and settlement ownership ride on FACT records (`WorkshopNPCFaction`, ally/enemy relations) that carry 1:1? | Ties to the faction framework the owner asked for; also the Preston hostility report | FACT carries (starfield-systems-to-reuse.md) | xEdit: dump `WorkshopNPCFaction` relations; check our converted copy | factions area | QP | |
| T5 | Should Minutemen settlement quests (radiant "help settlement") use our own Story Manager events or a script dispatcher? | Starfield lacks some SM events | unresolved | after T3 | T3 | QP | |
| T6 | Settlement map markers (FO4 type 13, Nuka-World 66-68): which Starfield marker types and icons do we use? | Players find settlements by map | enum verified in xEdit | dump Starfield marker type enum; pick icons | world/map area | FS | |
| T7 | Do settlement attack spawns need encounter levels per settlement location (LCTN Workshop flag)? | Attack difficulty scaling | LCTN keeps a `Workshop` flag (verified) | after ECZN fold (L2) | L2 | FS | |

### 4. DLC workshop packs and Automatron
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| D1 | Does a FURN with WBDT 9 "Robot Mod" open any menu in CE2, or do we rebuild the robot bench on the armor bench path (as kine's frames do)? | Automatron's core loop | station DONOTUSE; community mods robot frames at a workbench like a spacesuit | CK test cell: place a type-9 bench and activate; inspect mod 16345's records | robot NPC_ conversion | FS | **key** |
| D2 | Do OMODs apply to NPC_ actors at run time in Starfield (object template on NPC_)? | Robots are actors made of mods | fields exist (actors page); runtime unresolved | CK: put an OMOD on a vanilla robot NPC_ template; spawn | D1 | FS | **key** |
| D3 | Is Contraptions logic native (the 40 DLC05 scripts suggest so) and is any of it reachable through Starfield's `XPLK` power links? | Decides rebuild vs drop | REFR power grid gone in SF | read DLC05 script names; xEdit count of XWPN refs in DLCworkshop02 | owner installs the missing DLC | FS | |
| D4 | Which DLC workshop content is pure data (decor, Vault-Tec pieces) we can ship early? | Breadth first | dlc page lists | per-DLC COBJ count with CNAM types (census after install) | DLC census | FS | |
| D5 | Wasteland Workshop cages and taming: worth a script rebuild, or skip for release 1? | Scope | script rebuild needed | owner decision | S-layer | REL | |
| D6 | Nuka-World vassal settlements and raider outposts: same settlement layer with a gang flag? | Shared code with base settlements | marker types 66-68 verified | design after S1/T4 | S1, T4 | QP | |

### 5. Weapons, armor, object mods and attach points
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| W1 | Can a converted FO4 WEAP fire with Starfield's animation graph (a Starfield weapon type per FO4 weapon), and which FO4 weapons have no Starfield equivalent (melee types, Fat Man, flamer)? | Weapons are visible from minute one | WEAP similarity 0.30; ports so far are mesh replacers with hand gaps | one FO4 pistol as a WEAP on a Starfield pistol graph in a CK test cell | animations area, physics | NG | **key** |
| W2 | Do FO4 attach points (`ap_*` keywords) and OMOD includes carry, and how do we re-map OMOD property enums? | FO4's modding is attach-point based like Starfield's | same OMOD structure; property enums differ (items page) | diff `wbObjectModProperties` lists in both xEdit files | W1 | FS | **key** |
| W3 | Are FO4 weapon mod meshes (receivers, barrels) assembled at run time by attach nodes that Starfield's NIF format keeps? | Modded weapons must look right | unresolved | convert one weapon with two barrel mods; view in CK | mesh pipeline | FS | |
| W4 | Do FO4 loose mods (`LNAM` MISC) and swapping mods at the bench work with Starfield's bench UI? | FO4 lets players keep removed mods | Starfield replaces mods on occupied points (wiki) | CK test: an OMOD with LNAM set | W2 | FS | |
| W5 | How do FO4 perk gates on mod recipes (Gun Nut, Science!) map: COBJ conditions on our own perks, or RQPK? | Character system tie | perk entry points mostly keep numbers | read 10 FO4 mod COBJ conditions | perks area | FS | |
| W6 | Armor: FO4 layered clothing (underarmor plus pieces) against Starfield's spacesuit/apparel slots: which biped slots map? | Armor visible on every NPC | biped/skinning gate is PLAN P1 | slot table from both xEdit files | actors area | NG | **key** |
| W7 | Do we reuse Starfield's quality tiers (Calibrated...Exceptional) or keep FO4's per-mod model only? | Fence vs reuse | Starfield tiers are stacking OMODs (wiki) | design decision | W2 | FS | |

### 6. Benches, junk, components and scrap
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| C1 | Do our 31 FO4 components work as IRES records (counted by the crafting UI) outside a planet resource context? | The junk economy rests on it | CVPA "CK allows only IRES" (xEdit note) | CK: one own IRES, one COBJ using it, one MISC with CVPA to it; craft in game | blocks C2, B1 costs | FS | **key** |
| C2 | Can junk be scrapped to components at a bench and in build mode without a vending-machine workaround? | FO4's loop (pick up junk, scrap, build) | Galactic Junk Recycler needed a vending machine; no native loop known | CK: check whether Starfield's bench menu has any scrap command; test a MISC with CVPA | C1 | FS | **key** |
| C3 | Does build mode pull components from the workbench container and linked storage, and from the player? | FO4 pulls from workshop plus supply-linked storage | Starfield pulls from outpost storage and the ship? (unresolved) | CK test after C1 | C1, T2 | FS | |
| C4 | Which bench for each FO4 bench type: weapons, armor, chem, cooking map to vanilla FURNs (done); power armor (8) and robot (9) stay statics? | Bench function | 269 benches on 4 vanilla FURNs (stations.md) | none; confirm in game later | D1, power armor | FS | |
| C5 | Should we reuse Starfield's research (RSPJ) to gate FO4 perks' recipe unlocks, or keep FO4 perk conditions only? | Fence vs reuse | research is fenced by default | owner decision | perks area | FS | |
| C6 | Do Starfield's bench menus show a weight/value of components as FO4's "tag for search" does? | Players hunt components | unresolved | in-game look at a vanilla bench | C1 | FS | |

### 7. Legendary items
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| G1 | Can LGDI reproduce FO4's model (one legendary effect per item, from a pool filtered by item type) with FO4's legendary OMODs? | Native system instead of porting `LegendaryItemQuest` | LGDI editable (LEO edits it); FO4 rules via FLSTs (2017 article) | SfInspect 3 vanilla LGDI; write one LGDI from one FO4 OMOD in a test plugin | W2 | FS | **key** |
| G2 | How do legendary enemies get flagged and drop legendaries in Starfield (keyword, LVLN rank, `LVLL`)? | FO4 uses EncTypeLegendary + MGEF | LVLI `LVLL` exists | SfInspect a vanilla legendary enemy NPC_ and its loot | actors area | FS | **key** |
| G3 | Must Starfield's Tier 4 slot, rerolls and X-Tech (Free Lanes) be hidden from our world, and how? | Fence; they appear at Starfield benches | features verified (bethesda.net) | check which COBJ/RSPJ/keywords drive them; exclude in our benches | C4 | FS | |
| G4 | Do FO4 instance naming rules (INNR) translate to give "Furious Combat Shotgun" names? | Fallout feel | counts verified; field diff unresolved | xEdit INNR diff | G1 | FS | |

### 8. Currency, vendors, barter, restock
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| E1 | Can "Credits" be renamed to "Caps" everywhere (barter menu, HUD, loading tips, quest text) by renaming 0000000F plus string or translation files? | Option A of the currency decision | no Starfield precedent found; mesh-only mods exist | grep Starfield Interface and translation strings for "Credits"; rename 0000000F in a test plugin and screenshot barter | blocks E2 | NG | **key** |
| E2 | If E1 fails, can SFSE make the barter menu pay in another item? | Option B | unresolved | ask on SFSE/CommonLibSF Discord; read CommonLibSF barter menu classes | E1 | REL | |
| E3 | Does Starfield read FO4's barter GMSTs (`fBarterMax`, `fBarterMin`) and the vendor restock setting? | Prices and restock carry or need tuning | restock default reported as 48 h; SFSE needed to change it (mod 6329) | GMST name dump of both masters (existing walker) | none | QP | **key** |
| E4 | Do FO4 vendor FACTs plus merchant containers with leveled caps work unchanged once converted? | Every trader | same subrecords (verified); Leveled Vendor Credits uses leveled lists in containers | convert one Diamond City vendor; barter in game | E1, L1 | QP | **key** |
| E5 | Which FO4 quest rewards pay caps by script, and should new ones use QUST `QRCR`? | Cheap rewards | `QRCR` verified in xEdit | grep FO4 quest scripts for `AddItem(Caps001` | quests area | QP | |
| E6 | Settlement stores and vendor income: script payouts into the workbench container? | FO4 settlement economy | numbers verified on falloutck | after S1 | S1 | FS | |
| E7 | How do we keep Starfield's Trade Authority, ship sales and contraband scanning out of our world? | Fence | listed in economy page | audit for any Starfield vendor FACT or contraband keyword pulled in by references | factions area | REL | |

### 9. Leveled lists, loot and encounter levels
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| L1 | Once FO4 WEAP/ARMO/AMMO/ALCH convert, do FO4 LVLI resolve correctly with widened flags and no conditions? | Loot everywhere | container table stand-in today | convert 10 LVLI with targets; open containers | W1, W6 | INT | **key** |
| L2 | Does the ECZN to LCTN fold keep FO4's level locking (min/max, Match PC, Never Resets) in CE2? | Difficulty curve | fields verified; behaviour unresolved | one test location with min 20 / max 30 and a leveled raider | world/location area | INT | **key** |
| L3 | Do leveled actor chains break `GetIsID` and quest conditions, as feared in the raider conversion? | Quests check NPC ids | unresolved (raider-conversion.md) | one LVLN-based raider in a quest alias test | quests area | QP | **key** |
| L4 | Does Starfield's own scaling (system level, planet tier) leak into our planet's LCTN chain? | Fence | unresolved | read our planet LCTN parent chain; check level of a test spawn | world area | NG | |
| L5 | Cell reset timers (`iHoursToRespawnCell` etc.) in Starfield vs FO4: same names, values? | Respawn of loot and enemies | Skyrim values verified; FO4/SF unresolved | GMST dump (same as E3) | E3 | INT | |
| L6 | Should Starfield's LVLI conditions be used to replace FO4 script-driven loot (e.g. quest-stage lists)? | Cheaper than scripts | conditions on entries are new in SF (verified); used by mod 6868 | design note after L1 | L1 | FS | |

### 10. Cross-cutting (launcher, licensing, release)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| X1 | Does the launcher convert only Bethesda masters (Fallout4.esm, DLC) and refuse third-party plugins whose permissions forbid conversion (e.g. SS2)? | Legal and community trust | SS2 forbids conversion (verified) | write the rule into the launcher spec | launcher area | REL | **key** |
| X2 | Which DLC must the user own for each feature, and does the launcher degrade cleanly if one is missing? | Owner's PC lacks 4 DLC today | dlc page | launcher test with base game only | DLC census | REL | |
| X3 | How do we name our scripts and editor ids so no FO4 settlement mod name or Starfield name clashes? | Script names are global (README finding 5) | prefix rule exists | adopt `FO4SF_` prefix check in guard.py | none | FS | |
| X4 | Do we offer a modder API (keywords, FLST, events) so Starfield mod authors can add buildables to our settlements? | Community growth after release | Community Categories shows demand | decision after S7 | S7 | REL | |

## Sources
- https://allmods.net/starfield-mods/starfield-modders-resources/community-categories-v1-0-5/ (Community Categories)
- https://www.nexusmods.com/starfield/mods/7310/ (Ship Builder Categories)
- https://www.nexusmods.com/starfield/mods/8631 (Extended Outpost Builder Categories)
- https://www.nexusmods.com/starfield/mods/7271 (SKK Player Homes Anywhere, via next-phase note)
- https://www.nexusmods.com/starfield/mods/17637 (Outpost Stats Enhanced)
- https://www.nexusmods.com/starfield/mods/10558 (ZeeOgre's AIO Gameplay Tweaks)
- https://wccftech.com/starfields-outposts-meaningless/amp/ (kinggath on outposts)
- https://www.dsogaming.com/mods/starfield-dlc-sized-expansion-mod-colonies-giant-mechs-defense-turrets-farming-system ; https://www.pcgamesn.com/starfield/mod-city-builder (Galactic Colonies Expanse)
- https://bethesda.net/en/article/7IxZSKYwYm1oDr57rXDx4C/starfield-free-lanes-terran-armada (Free Lanes, Terran Armada)
- https://wiki.simsettlements2.com/gameplay/basics/workshop-framework ; https://wiki.simsettlements2.com/getting-started/known-issues
- https://www.nexusmods.com/fallout4/mods/47976 (Sim Settlements 2)
- https://www.nexusmods.com/starfield/mods/1394 (Legendary Effect Overhaul)
- https://www.nexusmods.com/starfield/mods/17225 (Legend 'O' Matic expansion patch)
- https://starfieldwiki.net/wiki/Starfield:Object_Mods ; https://starfieldwiki.net/wiki/Starfield:Leveled_Lists
- https://www.nexusmods.com/starfield/articles/659 (xEdit patching tutorial, weapons)
- https://www.nexusmods.com/starfield/mods/5219 (VSV rifle FO4 port) ; https://www.nexusmods.com/starfield/mods/17294 (effect-sequence weapon animation)
- https://www.nexusmods.com/starfield/mods/16345 (kine's Terran Robot Frames)
- https://starfieldportal.com/article/starfield-junk-now-become-useful-resources (Galactic Junk Recycler)
- https://www.nexusmods.com/starfield/mods/6329 (vendor restock SFSE) ; https://www.nexusmods.com/starfield/mods/6868 (Leveled Vendor Credits) ; https://www.nexusmods.com/starfield/mods/4660 (credit mesh)
- https://primagames.com/tips/best-base-and-settlement-locations-in-fallout-london (Fallout London settlements)
- Repo: docs/research/engine-mechanics/papyrus-and-script-extenders.md:135-175 (PC probe job 15)
- Shared: /mnt/project-files/research/engine-mechanics/ (five area pages above), /mnt/project-files/research/next-phase/doors-activators-workshops.md
