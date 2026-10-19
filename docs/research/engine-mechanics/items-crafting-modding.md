# Items, crafting and modding (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `Core/wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`.

## In short
- Both engines share the item record family (WEAP, ARMO/ARMA, AMMO, MISC, ALCH, BOOK, KEYM), OMOD object mods with
  attach points, and COBJ recipes gated by a workbench keyword (**verified**, xEdit). Layouts differ a lot: WEAP is one
  of the least similar records (similarity 0.30, **verified**, docs/FORMAT-GAP.md:19).
- FO4's junk economy rests on CMPO components (31 in Fallout4.esm, FO4-only); MISC junk lists CMPO in CVPA and scraps
  into them. Starfield has no CMPO; crafting inputs are IRES resources (332) and the xEdit note says the CK allows only
  IRES in a Starfield CVPA (**verified**, xEdit). Verdict: **translate** (CMPO to our own resource items).
- Starfield COBJ gains required perks (RQPK), a tier, amount produced and repair components; it loses FO4's
  ANAM menu art and FNAM category array (**verified**, xEdit). Verdict: **translate** each FO4 COBJ.
- Legendaries: FO4 rolls them in Papyrus (`LegendaryItemQuest`) from OMODs; Starfield has a native LGDI record
  (84) with rank slots of OMODs (**verified** record, xEdit). Verdict: **rebuild** on LGDI or keep a script shim.
- Starfield adds research (RSPJ, 82) and bench types Extractor (10) and Research (11); FO4's Power Armor bench (8)
  has no vanilla Starfield bench (**verified**, xEdit enum + docs/terrain/stations.md:84). Power armor is its own
  later system.

## How Fallout 4 does it
| Piece | Record facts (**verified**, xEdit unless noted) |
|---|---|
| Items | WEAP 252, ARMO 682, ARMA 739, AMMO 57, MISC 2,176, ALCH 231, BOOK 327, KEYM 177 in Fallout4.esm (docs/measurements/fo4_esm.json) |
| MISC junk | `DATA` Value (s32) + Weight (float); `CVPA` Components = array of (Component form, Count u32); `CDIX` display indices, one per component; `FIMD` featured item message |
| CMPO | `DATA` auto-calc value, `MNAM` Scrap Item (a MISC, e.g. the "Steel" scrap object), `GNAM` Mod Scrap Scalar (GLOB), `CUSD` pickup sound |
| OMOD | `DATA`: Form Type, Max Rank, Level Tier Scaled Offset, `Attach Point` (KYWD), `Attach Parent Slots` (KYWD array), Includes (OMOD, min level, optional, don't-use-all), property list; `MNAM` target OMOD keywords, `FNAM` filter keywords, `LNAM` Loose Mod (the MISC you carry), `NAM1` priority |
| COBJ | `FVPA` components (form, count), `DESC`, `CTDA` conditions, `CNAM` created object, `BNAM` workbench keyword, `ANAM` menu art, `FNAM` category keywords, `INTV` created count + priority |
| Benches | FURN `WBDT` bench type: 2 Weapons, 5 Alchemy (chem and cooking), 7 Armor, 8 Power Armor, 9 Robot Mod (Automatron); 1 Create Object only for MS11Workbench |

- Recipe filters: the COBJ category keyword decides the bench sub-category (falloutck example `RecipeUtility`), and the
  workbench keyword decides which bench lists it; for object mods the attach point and mod association keywords decide
  placement rather than the workbench keyword (**verified**, https://falloutck.uesp.net/wiki/COBJ).
- Mod crafting: an OMOD's recipe is a COBJ whose created object is the OMOD; perks gate it through COBJ conditions
  (Gun Nut, Science!, Armorer; **supported hypothesis**, perk names from general knowledge, conditions not dumped).
- Scrap: scrapping a weapon/armor at a bench returns components scaled by the CMPO's `GNAM` scalar (**supported
  hypothesis**: field name only). Junk scrapped in workshop mode adds its CMPO to the workshop container
  ([workshop note](workshop-and-settlements.md)).
- Legendary items: `LegendaryItemQuest` with `LegendaryItemQuestScript`; base pool LVLI
  `LGND_PossibleLegendaryItemsBaseLists`; the item needs `ap_Legendary` in its attach parent slots; per-mod rules
  through FormLists such as `LegendaryModRule_allowedKeywords_ArmorBodyChest`; drop triggered by MGEF
  `abLegendaryCreatureItemEffect` on actors with `EncTypeLegendary` (**supported hypothesis**: one 2017 modder article,
  https://nexusmods.com/fallout4/articles/3418). Names come from instance naming rules (INNR, e.g. `dn_CommonArmor`).
- LVLI carries `LVSG` "Epic Loot Chance" (GLOB) (**verified**, xEdit); its role in legendary rolls is **unresolved**.
- Weight and carry: FO4 weight is a unitless float shown as pounds; carry weight is an actor value (**supported
  hypothesis**). Currency: Caps.
- Barter: FACT vendor data `VEND` buy/sell FLST, `VENC` merchant container REFR, `VENV` vendor values (**verified**,
  xEdit, same three subrecords in both games).
- Perk entry points for lockpicking/hacking/crafting are in [terminals-holotapes-locks.md](terminals-holotapes-locks.md).

## How Starfield does it
| Piece | Record facts (**verified**, xEdit unless noted) |
|---|---|
| Items | WEAP 406, ARMO 1,017, ARMA 1,106, AMMO 150, MISC 1,319, ALCH 353, BOOK 992, KEYM 242 (docs/measurements/sf_esm.json) |
| IRES (new, 332) | `FULL`, `KWDA`, `FNAM` Surface Item (LVLI), `SNAM` Rarity (Common, Uncommon, Rare, Exotic, Unique, Special, Everywhere), child resources, `NNAM` short name, `NAM1` Resource AV, `NAM2` Resource Item (LVLI/COBJ), `NAM3` production interval GLOB |
| MISC / ALCH / KEYM | `CVPA` (Component, Count, 4 unused bytes); xEdit comment "CK allows only IRES" |
| OMOD | same core as FO4 (attach point, attach parent slots, includes, properties, MNAM/FNAM/LNAM/NAM1) plus `VMAD`, a name string, `NAM2`/`NAM3` 3rd/1st person morphable object (MRPH) |
| COBJ (3,009) | `BNAM` workbench keyword (required), conditions, `FVPA` components with a curve table each, `RQPK` required perks (perk, rank), `CNAM` created object, `NNAM` amount produced, `SNAM` menu priority, `TNAM` tier 0-5, `REPR` repair components |
| RSPJ (82) | Research Project: `BNAM` workbench keyword, conditions, `FVPA` required items (ALCH/AMMO/ARMO/BOOK/COBJ/IRES/KEYM/LIGH/LVLI/MISC/WEAP), `RQPK` perks, `CNAM` created item, `TNAM` tier, `KNAM` category keyword, `RNAM` required researches |
| LGDI (84) | Legendary Item: `ANAM` base object list (LVLI), `ENAM` rank template, `MNAM` add-into legendary, `BNAM` rank-slot array of OMODs, `LNAM` condition index map, ranked mod conditions |
| LVLI | adds `LVLL` "Legendary Item Default List Rank", `LLRV` required resource vein (IRES), `LLRB` required biome |
| Benches | WBDT 2 Weapons, 5 Alchemy (cooking, industrial, pharmaceutical), 7 Armor (spacesuit), 10 Extractor, 11 Research |

- Vanilla benches the port already uses: WorkbenchWeapon 2B6A63, WorkbenchArmor 2B6A62 (Spacesuit Workbench),
  WorkbenchChem 2B6A61 (Pharmaceutical Lab), WorkbenchFood 2B6A65 (Cooking Station); armor, chem and cooking share
  the recipe keyword FormID with FO4 (0657FF, 102158, 102152); the weapon keyword 2CE1C0 is Starfield-only
  (**verified**, docs/terrain/stations.md:74-86).
- Gameplay: weapon and spacesuit mods are unlocked by research at the Research Lab and gated by skills; this matches
  RSPJ and COBJ `RQPK` (**supported hypothesis** from the record layout; flow not traced in scripts).
- Weight: Starfield shows mass in kg and has a carry capacity actor value (**supported hypothesis**); the project's
  item table already writes weights in kg (scripts/terrain/clusters/item_table.json note, **verified**). Currency:
  Credits `Starfield.esm:00000F` (**verified** use, scripts/terrain/clusters/container_table.json).
- Gone: CMPO, NOTE (holotape items), COBJ `ANAM`/`FNAM`. New: IRES, RSPJ, LGDI, per-component curve tables.

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| WEAP / AMMO | WEAP / AMMO | translate | layout differs; weapon stats, animation, projectile and sound fields need their own note. Today promoted as MISC pickups (docs/terrain/port-promotions.md:16) |
| ARMO / ARMA | ARMO / ARMA | translate | biped slots and skinning gate this (PLAN P1) |
| MISC junk + CVPA | MISC + CVPA | translate | CVPA must point at our resource items, not CMPO |
| CMPO (31) | own IRES or MISC "component" items | rebuild | IRES lets Starfield's crafting UI count them; whether an IRES works outside planets is **unresolved** |
| OMOD + attach points | OMOD | translate | same structure; FO4 property targets (WEAP/ARMO field enums) must be re-mapped per field |
| COBJ (craft) | COBJ | translate | FVPA keeps; add NNAM/SNAM/TNAM; FO4 perk conditions become RQPK or conditions on our own perks |
| COBJ (workshop) | COBJ in build mode | translate | see workshop note; category keywords map to our own menu |
| Benches | vanilla FURN by WBDT | data copy (done) | power armor (8) stays a static until a power-armor system exists |
| Legendary quest + OMODs | LGDI + LVLI LVLL | rebuild | LGDI is native; FO4 effects are OMODs, so the OMODs carry over |
| INNR naming rules (7) | INNR (5) | translate | counts **verified** (measurements); field diff **unresolved** |
| Vendors (FACT VEND/VENC/VENV) | same subrecords | data copy | caps vs credits: decide currency (own MISC "Caps" or reuse Credits) |
| Research | RSPJ | drop or reuse | FO4 has no research; an "own ecosystem" choice |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- A component layer: 31 FO4 components as our own items, and every MISC CVPA and COBJ FVPA re-pointed. Pure data,
  built on the PC from the user's Fallout4.esm.
- OMOD property re-mapping: FO4 OMOD properties name WEAP/ARMO fields by enum; Starfield's enums differ. Needs a field
  table checked against vanilla records (no SFSE).
- Legendaries: either write LGDI records from FO4 legendary OMODs (preferred, native) or port the quest logic as our
  own Papyrus (no FO4 .psc text copied; owner question P8 in ../next-phase/doors-activators-workshops.md).
- Power armor bench and frames: no Starfield bench; later system, likely needs CK-authored furniture and scripts.
- SFSE is not needed for any of this on current evidence.

## Port status and links
- Loose items: promoted as MISC with table names, values, weights (MiscItem / Ingestible / Weapon all as MISC); 492
  MISC bases in the full build (**verified**, docs/terrain/port-promotions.md:15-20, docs/terrain/stations.md:107).
- Benches: 269 bench REFRs on the four vanilla Starfield FURNs, no own FURN (docs/terrain/stations.md:107).
- NPC weapons: Raider conversion uses a Starfield WEAP analog (Coachman 0026D96B) until FO4 WEAP is converted
  (docs/actors/raider-conversion.md:134).
- Plan: P1 Items acceptance in docs/PLAN.md:96. Workshop build menu: ../next-phase/doors-activators-workshops.md.

## Open questions and cheap checks
- Does the Starfield CK really refuse non-IRES components, and does the engine? Dump CVPA targets of all vanilla MISC.
- Can a CMPO-like MISC be counted by the Starfield crafting menu? Check one vanilla COBJ whose FVPA names a MISC.
- OMOD property enums: diff the `wbObjectModProperties` value lists in both xEdit files (read-only).
- LGDI rank slots: dump 3 vanilla LGDI and their OMODs with SfInspect.
- FO4 legendary rule list: dump `LegendaryItemQuest` VMAD properties with Fo4Export to confirm the 2017 article.
- INNR layout diff in xEdit (both games define it).

## Sources
- xEdit definitions: https://github.com/TES5Edit/TES5Edit (Core/wbDefinitionsFO4.pas, Core/wbDefinitionsSF1.pas, dev-4.1.6)
- https://falloutck.uesp.net/wiki/COBJ
- https://nexusmods.com/fallout4/articles/3418 (legendary system, modder article)
- Repo: docs/measurements/fo4_esm.json, sf_esm.json; docs/FORMAT-GAP.md; docs/terrain/stations.md;
  docs/terrain/port-promotions.md; docs/actors/raider-conversion.md; scripts/terrain/clusters/*.json
