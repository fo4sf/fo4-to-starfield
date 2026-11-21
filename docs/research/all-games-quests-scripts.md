# Multi-Title Quest, Script, and Shared-Systems Census (`FO1`..`FO76` + `Starfield`)

Read-only binary and archive census across all eight installed titles (*Fallout*, *Fallout 2*, *Fallout Tactics*, *Fallout 3 GOTY*, *Fallout: New Vegas*, *Fallout 4*, *Fallout 76*, and *Starfield*), produced by [all_games_census.py](../../scripts/research/all_games_census.py) and covered by synthetic unit fixtures in [test_all_games_census.py](../../tests/test_all_games_census.py).

- **Evidence Hygiene:** Every count, record signature, subrecord layout, archive version, FormID/EditorID reference, and Top-40 function/event table below was measured directly from read-only vanilla archives and master files. Zero game prose, dialogue text, quest descriptions, decompiled script bodies, local paths, or third-party mod files are stored or reproduced.
- **Reproducible Invocation:**
  ```powershell
  <PYTHON_EXE> -I scripts/research/all_games_census.py --common-dir <GAMES_COMMON_DIR> --out-dir <CENSUS_OUT_DIR>
  ```

---

## 0. Cross-Title Executive Summary & Readability Notes

### 0.1 Master Quest, Dialogue, and Script Comparison Across All Eight Titles

*(Bethesda rows show **`Base ESM` (`All Official ESMs`)** where official DLC/update masters exist.)*

| Title | Archive Format | Quests / Missions | Stages (`INDX` / FSM) | Objectives (`QOBJ` / `quests.txt`) | Topics (`DIAL` / `.msg`) | Responses (`INFO` / `.msg` IDs) | Scenes (`SCEN`) | Script Runtime | Compiled Scripts | Source Scripts Shipped | Distinct Functions & Events Used |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: | ---: |
| **Fallout 1** | `DAT` v1 (BE + LZSS `0x40`) | `618` `GVAR`s (`VAULT13.GAM`) | Global int states | Journal via `MAP.MSG` / `QUESTS` | `621` dialog `.msg` (`648` total EN) | `36,292` `.msg` entries | `0` (`21` talking heads) | SSL VM (`.int` BE stack) | `952` `.int` (`17,321` procs) | `0` `.ssl` | `171` |
| **Fallout 2** | `DAT` v2 (LE + `zlib`) | `110` rows (`quests.txt`) / `696` `GVAR`s | `GVAR` threshold ranges | `110` Pip-Boy rows (`14` towns) | `802` dialog `.msg` (`833` total EN) | `69,112` `.msg` entries | `0` (talking heads) | SSL VM (`.int` BE stack) | `1,443` unique `.int` (`34,123` procs) | `0` `.ssl` | `195` |
| **Fallout Tactics** | `40` `.bos` (`PKZIP` + `<world>` `zlib`) | `103` `.mis` (`27` core, `4` tut, `42` rand, `30` other) | `1,310` `<Trigger>` FSMs (`3,370` vars) | `39` `Add Objective` actions | `1,248` `<speech_node>` | `29` `locale/game` `.txt` | `885` `<gameEvent>` | Binary `<Trigger>`/`<esh>` FSM | `103` `.mis` (`0` `.scb`) | `0` text | `63` |
| **Fallout 3 GOTY** | `16` `.bsa` (`v104` / `0x68`) + `6` `.esm` | `192` (`298`) `QUST` | `832` (`1,343`) | `301` (`542`) | `6,381` (`8,542`) | `22,327` (`28,607`) | `0` (`0`) | GECK ObScript (`SCPT` + embedded) | `1,257` (`2,320`) `SCPT` + `8,095` emb. | **`100%` unstripped `SCTX`** | `287` |
| **Fallout: New Vegas** | `21` `.bsa` (`v104` / `0x68`) + `10` `.esm` | `436` (`642`) `QUST` | `1,028` (`1,423`) | `1,045` (`1,479`) | `18,215` (`21,560`) | `23,247` (`28,933`) | `0` (`0`) | GECK ObScript (`SCPT` + embedded) | `2,576` (`3,715`) `SCPT` + `8,769` emb. | **`100%` unstripped `SCTX`** | `341` |
| **Fallout 4** | `95` `.ba2` (`v1`, `v7`, `v8`) + `7` `.esm` | `1,336` (`1,916`) `QUST` | `8,680` (`13,071`) | `1,198` (`1,924`) | `35,443` (`46,427`) | `78,087` (`102,462`) | `3,568` (`4,778`) | Papyrus VM `v3.9` (`game_id=2`) | `7,875` base (`10,271` w/ DLC `.pex`) | `7,854` base (`10,250` w/ DLC `.psc`) | `3,043` (`Base.zip`) / `4,361` (`.pex`) |
| **Fallout 76** | `43` `.ba2` (`v1`) + `2` `.esm` | `2,232` (`2,281`) `QUST` | `14,017` (`14,892`) | `4,495` (`4,863`) | `40,182` (`40,187`) | `65,818` (`65,824`) | `4,769` (`4,769`) | Papyrus VM `v3.15` (`game_id=3`, split) | `7,234` client `.pex` (`787` active) | `0` `.psc` | `876` (client bytecode) |
| **Starfield** | `79` `.ba2` (`v2`, `v3` LZ4) + `9` `.esm` | `2,077` (`2,235`) `QUST` | `14,537` (`15,937`) | `2,549` (`2,756`) | `68,154` (`73,461`) | `126,347` (`137,111`) | `7,613` (`8,286`) | Papyrus VM `v3.12` (`game_id=4`, Guards) | `4,740` base (`5,034` w/ `SFBGS*` `.pex`) | `5,033` `.psc` (`ContentResources.zip`) | `3,498` (`.psc`) / `3,443` (`.pex`) |

### 0.2 Direct Readability vs Format / Archive Limitations Encountered

All **8 of 8** installed games were read directly in pure Python stdlib (+ `src/fo4sf/ba2.py`) with **zero failed files**:
1. **Fallout 1 (`MASTER.DAT` `19,784` entries + `CRITTER.DAT` `5,459` entries):** Read directly via big-endian `DAT` v1 directory parser and 4 KB ring-buffer LZSS block decompressor (`attrs == 0x40` positive LZSS chunks and negative literal chunks). **Limitation:** Vanilla archives ship `952` compiled `.int` SSL binaries and `0` `.ssl` text sources; `all_games_census.py` therefore parses `.int` procedure headers and big-endian SSL stack opcodes (`0x80A1..0x8155`) directly.
2. **Fallout 2 (`master.dat` `23,140` + `critter.dat` `7,120` + `patch000.dat` `489` -> `30,262` unique entries, `487` overrides):** Read directly via little-endian `DAT` v2 footer and `zlib` streams. Same `.int`-only limitation (`1,443` unique `.int`, `0` `.ssl` text); solved by stepping SSL bytecode directly.
3. **Fallout Tactics (`40` `core/*.bos` PKZIP archives, `36,470` entries):** Read directly via `zipfile` plus inner `<world>\x0068\x00` `zlib` decompression across all `103` `.mis` files. **Limitation:** Missions use compiled binary `<Trigger>` / `<esh>` FSM records (`0` text scripts); solved by reading the length-prefixed `<uint32_len><NodeName><esh>\x00` node headers directly.
4. **Fallout 3 GOTY (`6` `.esm`s + `16` `.bsa` v104, `159,030` unique archive files) & Fallout: New Vegas (`10` `.esm`s + `21` `.bsa` v104, `181,642` unique archive files):** Read `100%` directly, including bit `0x0100` embedded BString filenames in texture BSAs and **`100%` unstripped plain-text `SCTX` ObScript sources** on every `SCPT` record (`2,320 / 2,320` in FO3+DLC; `3,715 / 3,715` in FNV+DLC) plus embedded `INFO`/`PACK`/`TERM`/`PERK` `SCTX` blocks.
5. **Fallout 4 (`7` official `.esm`s + `Base.zip` / `DLC01..06.zip` `.psc` + `7` `GNRL` `.ba2`s v1/v8):** Read `100%` directly (`10,271 / 10,271` `.pex` files parsed byte-for-byte). Creation Club `cc*` plugins present in `Data/` were intentionally excluded from vanilla counts.
6. **Fallout 76 (`SeventySix.esm` + `NW.esm` + `SeventySix - MiscClient.ba2`):** `100%` of `SeventySix.esm` records and `7,234 / 7,234` client `.pex` files (`v3.15`, `game_id=3`, including trailing networked variable index tables) parsed with `0` errors. **Format / Architecture Limitation:** Because Fallout 76 uses a client/server split, `0` `.psc` sources ship and **`2,652` of the `7,234` `.pex` files in `SeventySix - MiscClient.ba2` are zero-instruction server-stripped quest/fragment stubs** (`3,795` are `Native` headers and `787` carry active client-side bytecode). Server-authoritative quest scripts cannot be read from a client install and would require clean-room reconstruction from `SeventySix.esm` `QUST`/`DIAL`/`INFO`/`VMAD` property bindings if FO76 conversion is ever authorized (`REL-60` gate).
7. **Starfield (`9` official `.esm`s + `Tools/ContentResources.zip` + `8` `GNRL` `.ba2`s v2):** `100%` of official `.esm`s, `5,033` `.psc` files, and `5,034 / 5,034` `.pex` files (`v3.12`, `game_id=4`, including Starfield's `Guard` lock tables and `0x2F..0x32` opcodes) parsed directly. Experiment `FO4*` `.esm`s staged in `Data/` were strictly excluded from vanilla baseline counts. *(Note: `ba2.py` intentionally raises on Starfield `v3` `LZ4`-compressed `DX10` texture chunks, which is irrelevant to `.esm`/`.psc`/`.pex` quest and script analysis.)*

---

## 1. Fallout 1 (`MASTER.DAT` + `CRITTER.DAT`)

### 1.1 Quest & Dialogue Model
- **No `QUST` Record Type:** Quest state is stored purely as integer global variables (`GVAR_*`) initialized in `DATA\VAULT13.GAM` (`618` `GVAR` assignments) and per-map state variables (`MVAR_*`) across `35` `MAPS\*.GAM` files (`310` `MVAR` assignments across `36` `.gam` files total).
- **Maps & Journal:** `72` `.map` files (`72 / 72` carry a header map-script ID). Unlike Fallout 2, Fallout 1 has **no `data/quests.txt` table** (`0` rows); the Pip-Boy 2000 Status pane hardcodes location quest headers in the executable and reads display lines from `TEXT\ENGLISH\GAME\MAP.MSG` / `QUESTS` keyed on fixed `GVAR` indices (`0` = inactive, `1` = active, `2` = completed).
- **Dialogue Storage:** `621` English character dialogue `.msg` tables (`648` English `.msg` files total containing `36,292` numbered `{id}{}{...}` entries) paired with `952` `.int` scripts using `start_gdialog` (`449`), `gsay_start` (`437`), `gsay_reply` (`3,512`), `gsay_message` (`2,888`), and `giq_option` (`8,636`). `21` characters use animated talking heads (`1,601` `.lip` phoneme files).

### 1.2 Script Runtime & Measured Top 40 Functions / Events
- **Runtime:** Interplay SSL Virtual Machine (`.int` big-endian stack bytecode; `42`-byte startup stub + `24`-byte procedure descriptors + identifier table + string table + `16`-bit opcode stream).
- **Counts:** `952` compiled `.int` scripts (`0` `.ssl` sources), `17,321` total procedures, **`171` distinct engine functions and `*_p_proc` callbacks** used.

| Rank | Function / Callback | Uses | Rank | Function / Callback | Uses | Rank | Function / Callback | Uses | Rank | Function / Callback | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `global_var` | `14,269` | 11 | `gsay_reply` | `3,512` | 21 | `proc:start` | `952` | 31 | `game_time` | `588` |
| 2 | `set_local_var` | `9,638` | 12 | `gsay_message` | `2,888` | 22 | `game_time_hour` | `893` | 32 | `move_to` | `492` |
| 3 | `giq_option` | `8,636` | 13 | `display_msg` | `2,778` | 23 | `has_trait` | `880` | 33 | `anim` | `480` |
| 4 | `local_var` | `8,167` | 14 | `create_object_sid` | `1,476` | 24 | `is_success` | `832` | 34 | `attack_complex` | `477` |
| 5 | `dude_obj` | `7,303` | 15 | `tile_num` | `1,387` | 25 | `add_obj_to_inven` | `720` | 35 | `game_ticks` | `450` |
| 6 | `self_obj` | `6,134` | 16 | `source_obj` | `1,199` | 26 | `tile_num_in_direction` | `710` | 36 | `start_gdialog` | `449` |
| 7 | `message_str` | `5,598` | 17 | `get_critter_stat` | `1,133` | 27 | `roll_vs_skill` | `697` | 37 | `end_dialogue` | `449` |
| 8 | `set_global_var` | `4,657` | 18 | `float_msg` | `1,118` | 28 | `elevation` | `679` | 38 | `gsay_start` | `437` |
| 9 | `random` | `3,978` | 19 | `script_overrides` | `1,072` | 29 | `map_var` | `638` | 39 | `gsay_end` | `437` |
| 10 | `script_action` | `3,522` | 20 | `critter_add_trait` | `986` | 30 | `set_map_var` | `631` | 40 | `add_timer_event` | `425` |

### 1.3 Shared-Systems Storage Model (`Fallout 1`)
- **Reputation & Karma:** Stored in `DATA\VAULT13.GAM` `GVAR` slots (`GVAR_PLAYER_REPUTATION` for global Karma, title/reputation `GVAR`s such as `GVAR_CHILDKILLER_REPUATION` / `GVAR_BERSERKER_REPUTATION`, and per-town `GVAR_TOWN_REP_*` integer variables) plus `local_var` NPC reaction scores (`dialogue_reaction`).
- **Companions & Followers:** Script-driven (`party_add` / `party_remove` opcodes `0x8124`/`0x8125` + `dest_tile` follow loops in `critter_p_proc`); no dedicated companion-command UI or armor-swap inventory rules.
- **Hardcore / Needs:** None (`0` hunger/thirst/sleep meters; overland travel consumes `game_time` against Vault 13's `GVAR` water deadline).
- **Radiation:** Stored on critter state; mutated via `radiation_inc` (`0x80FD`) and `radiation_dec` (`0x80FE`) plus timed drug/rad-sickness queue events (`14` `drug` `.pro` items).
- **VATS & Hit Locations:** Turn-based AP called-shot overlay (`8` zones: Head, Eyes, Right Arm, Left Arm, Torso, Groin, Right Leg, Left Leg) checked against `312` `PROTO\CRITTERS\*.PRO` records; limb cripples stored as `critter_injure` (`0x8127`) bitflags (`DAM_CRIP_LEG_LEFT`, etc.).
- **Ammo & DT/DR:** `242` `PROTO\ITEMS\*.PRO` (`43` `weapon`, `16` `ammo`, `9` `armor`). Armor `.pro` stores `7` damage-type `(DT, DR%)` pairs (`Normal`, `Laser`, `Fire`, `Plasma`, `Electrical`, `EMP`, `Explosion`); ammo `.pro` stores `ac_adjust`, `dr_adjust`, `dam_mult`, `dam_div`.
- **Perks & Skills:** `7` S.P.E.C.I.A.L. stats (`get_critter_stat`), `18` skills (`0–200%`), `3` Tag Skills, `0–2` Traits (`TRAIT.MSG`), Perks every `3` levels (`PERK.MSG`, queried via `has_trait` `0x80F3`).
- **Workshop / Settlements:** None (`0` buildable areas or crafting recipes).
- **Dialogue Skill Checks:** Evaluated inside `.int` `talk_p_proc` procedures via `giq_option(iq_test, msg_list, msg_id, target_proc, reaction)` (negative `iq_test` like `-3` gates low-`INT` options), `roll_vs_skill` (`697`), `is_success` (`832`), `has_skill`, and `get_critter_stat` (`1,133`).

---

## 2. Fallout 2 (`master.dat` + `critter.dat` + `patch000.dat`)

### 2.1 Quest & Dialogue Model
- **Data-Driven Pip-Boy Quest Table (`data\quests.txt`):** Introduces `data\quests.txt` (`110` active quest rows across `14` location groups), where each row maps `(location_msg_id, desc_msg_id, gvar_index, display_threshold, complete_threshold)` against `data\vault13.gam` (`696` `GVAR`s) and `87` `maps\*.gam` files (`564` `MVAR`s across `88` `.gam` files).
- **Maps & Dialogue:** `155` `.map` files (`155 / 155` carry header map scripts); `802` English character dialogue `.msg` files (`833` total English `.msg` files, `69,112` numbered entries) and `1,029` `.lip` talking-head lip-sync files.

### 2.2 Script Runtime & Measured Top 40 Functions / Events
- **Runtime:** Extended Interplay SSL VM (`1,443` unique `.int` scripts across `master.dat` + `487` `patch000.dat` overrides; `0` `.ssl` sources; `34,123` procedures; **`195` distinct engine functions and `*_p_proc` callbacks**).

| Rank | Function / Callback | Uses | Rank | Function / Callback | Uses | Rank | Function / Callback | Uses | Rank | Function / Callback | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `self_obj` | `97,635` | 11 | `set_local_var` | `16,339` | 21 | `game_time_hour` | `5,463` | 31 | `obj_name` | `3,146` |
| 2 | `set_global_var` | `60,533` | 12 | `metarule` | `15,524` | 22 | `obj_carrying_pid_obj` | `5,153` | 32 | `elevation` | `2,966` |
| 3 | `global_var` | `57,607` | 13 | `obj_is_carrying_obj_pid` | `14,681` | 23 | `create_object_sid` | `5,073` | 33 | `has_trait` | `2,754` |
| 4 | `party_member_obj` | `55,533` | 14 | `debug_msg` | `14,464` | 24 | `tile_num_in_direction` | `4,808` | 34 | `obj_item_subtype` | `2,480` |
| 5 | `message_str` | `32,183` | 15 | `critter_inven_obj` | `11,026` | 25 | `is_critical` | `4,442` | 35 | `add_obj_to_inven` | `2,472` |
| 6 | `giq_option` | `26,115` | 16 | `gsay_reply` | `10,356` | 26 | `obj_pid` | `4,293` | 36 | `set_light_level` | `2,466` |
| 7 | `tile_distance_objs` | `26,083` | 17 | `random` | `9,120` | 27 | `destroy_object` | `4,217` | 37 | `add_mult_objs_to_inven` | `2,416` |
| 8 | `dude_obj` | `23,681` | 18 | `source_obj` | `8,409` | 28 | `script_overrides` | `4,198` | 38 | `rm_mult_objs_from_inven` | `2,288` |
| 9 | `local_var` | `20,014` | 19 | `tile_num` | `7,814` | 29 | `float_msg` | `4,000` | 39 | `add_timer_event` | `2,266` |
| 10 | `display_msg` | `17,021` | 20 | `get_critter_stat` | `5,952` | 30 | `is_success` | `3,634` | 40 | `rm_obj_from_inven` | `2,109` |

*(Standard engine procedure entry counts across `1,443` scripts: `start` `1,441`, `map_enter_p_proc` `1,065`, `look_at_p_proc` `977`, `description_p_proc` `972`, `use_skill_on_p_proc` `931`, `damage_p_proc` `894`, `pickup_p_proc` `776`, `destroy_p_proc` `772`, `talk_p_proc` `753`, `critter_p_proc` `751`, `timed_event_p_proc` `688`, `map_update_p_proc` `500`.)*

### 2.3 Shared-Systems Storage Model (`Fallout 2`)
- **Reputation & Karma:** Driven by `data\karmavar.txt` (`17` Karma title/threshold rows) and `data\genrep.txt` (`9` town reputation tier thresholds: *Idolized* down to *Vilified*) backed by `GVAR_PLAYER_REPUTATION` and per-town `GVAR_TOWN_REP_*` slots in `data\vault13.gam`.
- **Companions & Followers:** Data-driven in `data\party.txt` (`302` active config lines defining AI packet presets, distance, chem use, weapon preference, and level-up stages), capped by `floor(CHA / 2)` (`Magnetic Personality` adds `+1`), with ubiquitous `party_member_obj` (`55,533` opcode uses via header macros) and trunk storage in the Highwayman car (`city.txt` `525` lines).
- **Hardcore / Needs & Radiation:** Same critter radiation/poison timers as FO1 (`28` `drug` `.pro`s); no hunger/thirst/sleep meters.
- **VATS, Hit Locations & Ammo/DT/DR:** `483` `critters\*.pro` and `531` `items\*.pro` (`110` `weapon`, `25` `ammo`, `16` `armor`, `115` `container`, `229` `misc_item`, `8` `key`), expanding JHP vs AP `dr_adjust` / `dam_mult` / `dam_div` differentiation.
- **Perks, Skills & Dialogue Checks:** `18` skills (`0–300%`), `0–2` Traits, Perks every `3` levels (`4` with `Skilled`), deterministic and rolled skill/stat/Karma/town-rep checks in `giq_option` (`26,115`).

---

## 3. Fallout Tactics (`40` `core/*.bos` PKZIP Archives)

### 3.1 Mission, Objective & Speech Model
- **Mission FSMs (`103` `.mis` files):** `27` `campaigns/missions/core/` story & bunker hub missions, `4` tutorials, `42` `random/` encounters, and `30` multiplayer/other maps. Each `.mis` starts with `<world>\x0068\x00` followed by a `zlib`-compressed stream containing `1,310` `<Trigger>` finite-state blocks, `885` `<gameEvent>` entries, `39` explicit `Add Objective` actions (`45` `Complete Objective`), `1,248` `<speech_node>` entries, and `3,370` distinct `CVAR_*` / `M0*_*` campaign and mission variable identifiers.
- **Dialogue Model:** No branching player dialogue tree (`0` `DIAL`/`INFO`); uses mission briefings/debriefings (`Add text to Debrief text list` `86`, `Display Debrief window and text` `26`) and floating real-time speech barks (`Set Random Speech` `329`, `Set Click Speech` `292`, `Force Speech` `165`).

### 3.2 Script Runtime & Measured Top 40 FSM Trigger Conditions / Actions
- **Runtime:** C++ binary `<Trigger>` / `<esh>` condition-action FSM embedded inside `.mis` (`0` `.scb` or text scripts; **`63` distinct FSM node & event types** measured across all `103` `.mis` files).

| Rank | FSM Node / Event | Uses | Rank | FSM Node / Event | Uses | Rank | FSM Node / Event | Uses | Rank | FSM Node / Event | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `Event:<Trigger>` | `1,310` | 11 | `Speech Occured` | `209` | 21 | `End Mission` | `88` | 31 | `Set Random Encounter Enable` | `36` |
| 2 | `Event:<gameEvent>` | `885` | 12 | `Force Speech` | `165` | 22 | `Add text to Debrief text list` | `86` | 32 | `Kill Entity` | `34` |
| 3 | `Set Variable` | `663` | 13 | `Always` | `160` | 23 | `Player Move State - Deactivate` | `74` | 33 | `Lock/Unlock Door` | `31` |
| 4 | `Variable` | `441` | 14 | `Player Move State - WayPoint` | `134` | 24 | `Player Priority - Move State` | `56` | 34 | `Mission Complete` | `27` |
| 5 | `Set Random Speech` | `329` | 15 | `Display World Text` | `112` | 25 | `Set Team Alignment Matrix` | `55` | 35 | `Modify RecruitPool list` | `27` |
| 6 | `Set Click Speech` | `292` | 16 | `Object Script State` | `110` | 26 | `Quantity - Team` | `54` | 36 | `Display Debrief window and text` | `26` |
| 7 | `Wait` | `281` | 17 | `Toggle Exit Grids` | `107` | 27 | `Complete Objective` | `45` | 37 | `Play Wav` | `24` |
| 8 | `Quantity - Unit` | `251` | 18 | `All Alive at Exit Grid` | `104` | 28 | `Can See` | `43` | 38 | `Center View` | `23` |
| 9 | `Quantity - Player` | `238` | 19 | `Add Experience To Player` | `99` | 29 | `Change Team` | `40` | 39 | `Player Priority - Aggression` | `23` |
| 10 | `Set object script state` | `228` | 20 | `Player Move State - Stationary` | `93` | 30 | `Add Objective` | `39` | 40 | `Set Death Text` | `22` |

### 3.3 Shared-Systems Storage Model (`Fallout Tactics`)
- **Entities (`1,498` unique `.ent` files):** `70` `recruits`, `7` `vehicles`, `197` `weapons`, `152` `items`, `146` `Actors`, `90` `characters`, `34` `containers`, `33` `doors`, `210` `lights`, `18` `misc`, `541` `Special`; plus `839` `.zar` sprite/UI bitmaps and `29,957` `.til` tiles.
- **Reputation, Ranks & Squads:** Military rank progression + Karma/reputation modify bunker quartermaster stock and `Modify RecruitPool list` (`27` FSM actions) gating the `70` `entities/recruits/*.ent` squad candidates (`6`-unit tactical squad bar, posture stances `Aggressive`/`Defensive`/`Hold`). Team hostility uses `Set Team Alignment Matrix` (`55`).
- **Combat, VATS, Ammo, Perks & Races:** Continuous Turn-Based (CTB) or Turn-Based modes with `8`-zone aimed shots; `locale/game/` key tables define `ammo.txt` (`44` keys), `weapon.txt` (`49`), `chems.txt` (`18`), `perk.txt` (`202`), `trait.txt` (`81`), `skill.txt` (`57`, `18` skills), and `race.txt` (`53`, `6` playable races: Human, Super Mutant, Ghoul, Deathclaw, Dog, Robot).

---

## 4. Fallout 3 GOTY (`Fallout3.esm` + `5` Official DLC `.esm`s + `16` `.bsa` v104)

### 4.1 Quest & Dialogue Model
- **Quests (`QUST`):** `192` in `Fallout3.esm` (`832` `INDX` stages, `301` `QOBJ` objectives, `101` `SCRI`-scripted, `141` `StartGameEnabled`, `26` `AllowRepeatedStages`, `0` aliases); **`298` `QUST` across all `6` official `.esm`s** (`1,343` `INDX` stages, `542` `QOBJ` objectives, `175` scripted, `202` `StartGameEnabled`, `53` repeatable).
- **Dialogue (`DIAL` / `INFO`):** Top-level `DIAL` group with Topic Children (`gtype == 7`) `INFO` records (`0` `SCEN` scenes). `Fallout3.esm` has `6,381` `DIAL` and `22,327` `INFO` (`44,436` `CTDA` conditions: `650` `GetActorValue` skill/stat checks, `2,414` `GetInFaction`, `2,076` `GetStage`, `717` `GetStageDone`, `7,884` `GetQuestVariable`); all `6` `.esm`s total **`8,542` `DIAL` and `28,607` `INFO`** (`55,321` `CTDA`s, `816` skill/AV checks).

### 4.2 Script Runtime & Measured Top 40 GECK Functions / Blocks
- **Runtime:** GECK ObScript (`fver = 2`). Every single `SCPT` record carries **`100%` unstripped plain-text `SCTX` source** alongside compiled `SCDA` bytecode:
  - `Fallout3.esm`: `1,257 / 1,257` `SCPT` (`1,118` `Object`, `101` `Quest`, `38` `MagicEffect`; `5,111` local vars) + embedded `SCTX` on `5,276` `INFO`, `510` `PACK`, `371` `TERM`, `3` `PERK`.
  - All `6` official `.esm`s: **`2,320 / 2,320` `SCPT`** (`2,074` `Object`, `176` `Quest`, `70` `MagicEffect`; `10,127` local vars) + embedded `SCTX` on `6,718` `INFO`, `863` `PACK`, `511` `TERM`, `3` `PERK` (**`287` distinct GECK functions and `Begin` blocks**).

| Rank | GECK Function / Block (`All 6 ESMs`) | Uses | Rank | GECK Function / Block | Uses | Rank | GECK Function / Block | Uses | Rank | GECK Function / Block | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `SetStage` | `2,132` | 11 | `MoveTo` | `952` | 21 | `IsActionRef` | `567` | 31 | `Begin:OnDeath` | `333` |
| 2 | `EvaluatePackage` | `1,595` | 12 | `Activate` | `860` | 22 | `GetActorValue` | `466` | 32 | `PlaceLeveledActorAtMe` | `325` |
| 3 | `Disable` | `1,565` | 13 | `ShowMessage` | `820` | 23 | `SetObjectiveDisplayed` | `437` | 33 | `GetSelf` | `307` |
| 4 | `Enable` | `1,357` | 14 | `PlaceAtMe` | `791` | 24 | `Say` | `429` | 34 | `GetDisabled` | `279` |
| 5 | `GetSecondsPassed` | `1,108` | 15 | `Begin:OnTriggerEnter` | `712` | 25 | `IsAnimPlaying` | `425` | 35 | `Unlock` | `278` |
| 6 | `AddItem` | `1,089` | 16 | `GetDead` | `707` | 26 | `Kill` | `424` | 36 | `GetDistance` | `277` |
| 7 | `PlayGroup` | `1,077` | 17 | `GetStage` | `684` | 27 | `StartCombat` | `374` | 37 | `SetOpenState` | `269` |
| 8 | `RemoveItem` | `1,060` | 18 | `Begin:OnActivate` | `679` | 28 | `Begin:OnLoad` | `365` | 38 | `GetStageDone` | `265` |
| 9 | `Begin:GameMode` | `1,032` | 19 | `GetItemCount` | `618` | 29 | `GetLinkedRef` | `364` | 39 | `AddScriptPackage` | `263` |
| 10 | `SetActorValue` | `1,015` | 20 | `SayTo` | `575` | 30 | `SetObjectiveCompleted` | `363` | 40 | `SetUnconscious` | `256` |

### 4.3 Shared-Systems Storage Model (`Fallout 3 GOTY`, Base / All 6 ESMs)
- **Reputation & Karma:** Global `Karma` (`ActorValue` `23`, `[-1000..+1000]`, `10` Karma `GMST`s, mutated via `RewardKarma` `144` calls) + `326` (`451`) `FACT` records (`XNAM` combat/disposition relations); `0` `REPU` records.
- **Companions & Followers:** `1` humanoid (`Followers` quest variables + `SetPlayerTeammate` + Karma alignment gates on recruitment) + `1` creature (`Dogmeat`), driven by `PACK` (`3,266` / `4,567`) and dialogue topics (`Wait`/`Follow`/`Trade`).
- **Hardcore / Needs & Radiation:** `0` hunger/thirst/sleep tables; `5`-stage radiation sickness (`200/400/600/800/1000` `RadiationRads` thresholds applying SPECIAL stat penalties, `53`/`62` `WATR`, `0` standalone `HAZD` records — radiation zones use placed triggers/spells).
- **VATS, Hit Locations & Ammo/DT/DR:** `32` (`46`) `BPTD`, `229` (`230`) `CAMS`, `307` (`308`) `CPTH`; `30` (`33`) `AMMO`, pure `DR%` (`85%` cap, `0` DT, `0` `AMEF`, `0` `IMOD`). Power Armor is worn `ARMO` gated by `PERK` `PowerArmorTraining`.
- **Perks, Skills, Workshop & Dialogue Checks:** `60` `AVIF` (`7` SPECIAL, `13` Skills w/ `Big Guns` & `Small Guns`), `87` (`115`) `PERK` (`61` / `93` playable, `1` per level, `0` creation traits); `0` settlements (`0` `COBJ`/`RCPE`; weapon schematics use scripted notes + `MESG` menus); `%`-roll Speech checks + deterministic Skill/SPECIAL/Perk `CTDA`s (`816` `GetActorValue` on `INFO`).

---

## 5. Fallout: New Vegas (`FalloutNV.esm` + `9` Official DLC/Pack `.esm`s + `21` `.bsa` v104)

### 5.1 Quest & Dialogue Model
- **Quests (`QUST`):** `436` in `FalloutNV.esm` (`1,028` `INDX` stages, `1,045` `QOBJ` objectives, `301` `SCRI`-scripted, `281` `StartGameEnabled`, `34` repeatable, `0` aliases); **`642` `QUST` across all `10` official `.esm`s** (`1,423` stages, `1,479` objectives, `466` scripted, `363` `StartGameEnabled`, `48` repeatable). Many town NPC topics live on hub `VFreeform*` quests and advance main/side `VMQ*`/`VMS*` quests cross-quest via `SCRO` + `SetStage`.
- **Dialogue (`DIAL` / `INFO`):** `18,215` (`21,560`) `DIAL` and `23,247` (`28,933`) `INFO` (`0` `SCEN`), carrying `59,664` (`69,332`) `CTDA` conditions (`1,264` / `1,679` deterministic `GetActorValue` skill/stat threshold checks, `3,464` `GetInFaction`, `2,792` / `2,804` `GetGlobalValue`, plus `GetReputation` / `GetReputationThreshold`).

### 5.2 Script Runtime & Measured Top 40 GECK Functions / Blocks
- **Runtime:** Extended GECK ObScript (`fver = 2`, adding reputation, ammo-effect, recipe, caravan, and companion-wheel opcodes). **`100%` unstripped plain-text `SCTX` source** on every `SCPT`:
  - `FalloutNV.esm`: `2,576 / 2,576` `SCPT` (`2,106` `Object`, `322` `Quest`, `148` `MagicEffect`; `9,546` local vars) + embedded `SCTX` on `6,367` `INFO`, `479` `PACK`, `208` `TERM`, `5` `PERK`.
  - All `10` official `.esm`s: **`3,715 / 3,715` `SCPT`** (`2,959` `Object`, `490` `Quest`, `266` `MagicEffect`; `13,927` local vars) + embedded `SCTX` on `7,768` `INFO`, `587` `PACK`, `407` `TERM`, `7` `PERK` (**`341` distinct GECK functions and `Begin` blocks**).

| Rank | GECK Function / Block (`All 10 ESMs`) | Uses | Rank | GECK Function / Block | Uses | Rank | GECK Function / Block | Uses | Rank | GECK Function / Block | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `Enable` | `3,076` | 11 | `RemoveItem` | `1,374` | 21 | `PlayGroup` | `862` | 31 | `Say` | `611` |
| 2 | `Disable` | `3,071` | 12 | `Activate` | `1,295` | 22 | `GetDisabled` | `823` | 32 | `MarkForDelete` | `579` |
| 3 | `SetObjectiveDisplayed` | `2,448` | 13 | `AddScriptPackage` | `1,163` | 23 | `GetItemCount` | `822` | 33 | `GetLinkedRef` | `529` |
| 4 | `SetStage` | `2,297` | 14 | `GetObjectiveCompleted` | `1,143` | 24 | `GetSecondsPassed` | `821` | 34 | `AddToFaction` | `527` |
| 5 | `EvaluatePackage` | `2,206` | 15 | `RewardXP` | `1,112` | 25 | `Begin:OnActivate` | `770` | 35 | `GetActorValue` | `511` |
| 6 | `SetObjectiveCompleted` | `2,049` | 16 | `GetObjectiveDisplayed` | `1,082` | 26 | `SetActorValue` | `730` | 36 | `PlaySound` | `501` |
| 7 | `ShowMessage` | `1,680` | 17 | `Begin:GameMode` | `1,025` | 27 | `GetStage` | `722` | 37 | `Resurrect` | `493` |
| 8 | `AddItem` | `1,649` | 18 | `Begin:OnTriggerEnter` | `1,008` | 28 | `ResetAI` | `680` | 38 | `SetDestroyed` | `470` |
| 9 | `GetDead` | `1,478` | 19 | `SayTo` | `960` | 29 | `RemoveFromFaction` | `674` | 39 | `Begin:OnDeath` | `468` |
| 10 | `MoveTo` | `1,421` | 20 | `StartCombat` | `937` | 30 | `IsActionRef` | `616` | 40 | `PlaceAtMe` | `468` |

### 5.3 Shared-Systems Storage Model (`Fallout: New Vegas`, Base / All 10 ESMs)
- **Reputation & Karma:** **`13` `REPU` records** (`4x4 = 16`-state Fame x Infamy matrix mutated via `AddReputation` `421` base calls, `SetReputation`, and faction-armor disguise scripts) running **orthogonally** alongside Global `Karma` (`[-1000..+1000]`) and `682` (`772`) `FACT` records.
- **Companions & Followers:** `1` humanoid + `1` non-humanoid slot, `8`-slice `companion_wheel_menu.xml` (`Melee/Ranged`, `Aggressive/Passive`, `Near/Far`, `Wait/Follow`, `Inventory`, `Stim`, `Talk`, `Back`), `Companion Nerve` (`+5%` dmg/DT per `CHA`), companion `PERK`s, and `PACK` (`4,163` / `4,888`).
- **Hardcore / Needs & Radiation:** Opt-in `IsHardcore` flag driving `5`-stage `DEHY` (Dehydration), `HUNG` (Hunger), and `SLPD` (Sleep Deprivation) tables (`0..1000`), weighted `AMMO`, Stimpak heal-over-time, crippled limbs requiring `Doctor's Bag` / `Hydra` / physician, and mortal companions; `5`-stage `RADS` sickness (`78` / `83` `WATR`).
- **VATS, Hit Locations & Ammo/DT/DR:** `49` (`58`) `BPTD`, `276` `CAMS`, `418` `CPTH`; **`92` (`145`) `AMMO` + `54` (`80`) `AMEF` ammo effects** + **`50` (`112`) `IMOD` weapon mods**, hotkey ammo swap (`AP`, `HP`, `JSP`, `+P`, `Slug`, `Flechette`, `Max Charge`) against `DT` + `DR` (`20%` `fMinDamMultiplier` floor). Salvaged NCR Power Armor is plain worn `ARMO` requiring no `PowerArmorTraining`.
- **Perks, Skills, Crafting & Dialogue Checks:** `64` (`65`) `AVIF` (`40`-point SPECIAL, `13` Skills replacing `Big Guns` with `Survival`), `176` (`259`) `PERK` (`101` / `175` playable at `1 / 2` levels + `10` creation Traits in `trait_menu.xml`); `0` settlements, **`105` (`291`) `RCPE` recipes** (`recipe_menu.xml` reloading/campfire/workbench); deterministic `[Skill N]` `CTDA` pairs (`GetActorValue >= N` pass / `< N` fail).

---

## 6. Fallout 4 (`Fallout4.esm` + `6` Gameplay DLC `.esm`s + `Base.zip` / `BA2`)

### 6.1 Quest & Dialogue Model
- **Quests (`QUST`):** `1,336` in `Fallout4.esm` (`8,680` `INDX` stages, `1,198` `QOBJ` objectives, `11,573` `ALST`/`ALLS` aliases, `920` `VMAD`-scripted, `274` `StartGameEnabled`, `53` repeatable `DNAM 0x08`, `45` alias-driven radiant); **`1,916` `QUST` across all `7` official `.esm`s** (`13,071` stages, `1,924` objectives, `16,380` aliases, `1,362` scripted, `462` `StartGameEnabled`, `80` repeatable, `67` radiant).
- **Dialogue & Scenes (`DIAL` / `INFO` / `SCEN`):** Nested inside `QUST` Quest Children (`gtype == 10`). `Fallout4.esm` has `35,443` `DIAL`, `78,087` `INFO`, and `3,568` `SCEN` (`71,341` `INFO` `CTDA`s: `1,810` `GetValue`, `126` `HasPerk`, `7,218` `GetInFaction`, `8,458` `GetStageDone`); all `7` `.esm`s total **`46,427` `DIAL`, `102,462` `INFO`, and `4,778` `SCEN`**.

### 6.2 Script Runtime & Measured Top 40 Papyrus Functions / Events
- **Runtime:** 64-bit Papyrus VM `v3.9` (`0xFA57C0DE`, `game_id=2`).
- **Counts:**
  - `Data/Scripts/Source/Base/Base.zip`: `7,854` `.psc` files (`91` `Native` headers + `7,763` non-native scripts; **`3,043` distinct case-folded functions and events**). Adding `DLC01..06.zip` yields `10,250` `.psc` files.
  - `Fallout4 - Misc.ba2` + `6` DLC `Main.ba2`s: `7,875` base `.pex` (`10,271` unique `.pex` across base + DLC: `439` `Native` headers, `9,606` active compiled scripts, `226` empty stubs; `267,349` bytecode instructions; `4,361` distinct bytecode targets).

| Rank | Papyrus Function / Event (`Base.zip`) | Uses | Rank | Papyrus Function / Event | Uses | Rank | Papyrus Function / Event | Uses | Rank | Papyrus Function / Event | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `SetStage` | `6,046` | 11 | `SetObjectiveCompleted` | `1,495` | 21 | `GetActorReference` | `890` | 31 | `Trace` | `420` |
| 2 | `Debug.Trace` | `5,274` | 12 | `Stop` | `1,440` | 22 | `AddItem` | `858` | 32 | `ForceRefTo` | `415` |
| 3 | `GetActorRef` | `3,952` | 13 | `GetLinkedRef` | `1,413` | 23 | `GoToState` | `708` | 33 | `wsTrace` | `410` |
| 4 | `Game.GetPlayer` | `2,998` | 14 | `Start` | `1,405` | 24 | `PlayAnimation` | `679` | 34 | `RemoveItem` | `402` |
| 5 | `GetStageDone` | `2,689` | 15 | `EvaluatePackage` | `1,343` | 25 | `StartTimer` | `466` | 35 | `AddToFaction` | `401` |
| 6 | `GetOwningQuest` | `2,672` | 16 | `GetValue` | `1,281` | 26 | `Play` | `445` | 36 | `SetOpen` | `387` |
| 7 | `SetValue` | `2,253` | 17 | `Enable` | `1,271` | 27 | `UpdateRadio` | `437` | 37 | `X688_Neutral` | `363` |
| 8 | `GetRef` | `2,048` | 18 | `Disable` | `1,248` | 28 | `IsDead` | `429` | 38 | `Hancock_Neutral` | `355` |
| 9 | `GetReference` | `1,978` | 19 | `MoveTo` | `1,154` | 29 | `Event:OnActivate` | `427` | 39 | `GetCount` | `352` |
| 10 | `SetObjectiveDisplayed` | `1,856` | 20 | `Utility.Wait` | `1,070` | 30 | `BlockActivation` | `424` | 40 | `Startup` | `348` |

### 6.3 Shared-Systems Storage Model (`Fallout 4`, Base / All 7 ESMs)
- **Reputation & Karma:** `0` `REPU`, `0` active Karma (`699` / `851` `FACT` records + quest stage flags); companion reactions use `CA_*` custom affinity events (`0..1000`).
- **Companions & Followers:** `1` active companion (`FollowersScript` on `Followers` quest + `CA_*` affinity perks + command mode); `3,828` (`4,890`) `PACK`.
- **Hardcore / Needs & Radiation:** `HC_ManagerScript` Survival mode (hunger, thirst, sleep, diseases, adrenaline, ammo weight, fast-travel lock); `Rads` caps Max HP (`10 Rads = -1%`, `59`/`78` `HAZD`, `42`/`47` `WATR`).
- **VATS, Hit Locations, Ammo & Power Armor:** Slow-time VATS + manual crit bar (`40`/`58` `BPTD`, `772` `CAMS`, `447` `CPTH`); `57` (`106`) `AMMO`, `2,409` (`3,990`) `OMOD`, `8` `DMGT` power-law DR (`0` `AMEF` ammo subtypes); climb-in `FURN` Power Armor frames (`598`/`783` `FURN`, `45`/`110` `RACE` incl. `PowerArmorRace` + `FusionCore`).
- **Perks, Skills, Workshop & Dialogue Checks:** `359` (`433`) `AVIF` (`28`-point SPECIAL, `0` Skills), `538` (`656`) `PERK` (`323`/`384` playable on 70-cell chart, `NNAM` rank chains); `29` Commonwealth workshops + `2,161` (`4,152`) `COBJ` + `31` (`33`) `CMPO` scrap components; 4-button voiced `SCEN` dialogue wheel with `CHA` `%` speech challenges.

---

## 7. Fallout 76 (`SeventySix.esm` + `NW.esm` + `SeventySix - MiscClient.ba2`)

### 7.1 Quest & Dialogue Model
- **Quests (`QUST`):** `2,232` in `SeventySix.esm` (`14,017` `INDX` stages, `4,495` `QOBJ` objectives, `26,692` aliases, `1,770` `VMAD`-scripted); **`2,281` `QUST` across `SeventySix.esm` + `NW.esm`** (`14,892` stages, `4,863` objectives, `27,798` aliases, `1,819` scripted). Note that `DNAM` `StartGameEnabled` is `1` because quest lifecycle activation is server-authoritative rather than cold-start client-autostarted.
- **Dialogue & Scenes (`DIAL` / `INFO` / `SCEN`):** `40,182` (`40,187`) `DIAL`, `65,818` (`65,824`) `INFO`, and `4,769` `SCEN`. Wastelanders/BoS silent-player list conversations drive **`8,330` `GetValue` (`AVIF` / SPECIAL) `CTDA` checks** on `INFO` (`39,171` total `INFO` `CTDA`s, `117` `HasPerk`, `559` faction checks).

### 7.2 Script Runtime & Measured Top 40 Client `.pex` Functions / Events
- **Runtime:** Papyrus VM `v3.15` (`0xFA57C0DE`, `game_id=3`), adding a trailing `uint16` networked-variable index table at the end of `ObjectData` and network events (`OnSyncVariableNetworkChanged`).
- **Client/Server `.pex` Breakdown (`SeventySix - MiscClient.ba2`):**
  - Total `.pex` files: **`7,234`** (`38,816` unique string-table identifiers; `0` `.psc` sources).
  - `Native` engine headers (`userFlags & 0x01`, `0` instructions): **`3,795`** (`52.46%`).
  - Zero-instruction server-stripped client stubs (quest/scene classes whose bodies execute only on the server): **`2,652`** (`36.66%`).
  - Active client-side bytecode scripts: **`787`** (`10.88%`, `17,983` instructions, **`876` distinct case-folded functions and events**).

| Rank | Client `.pex` Function / Event | Uses | Rank | Client `.pex` Function / Event | Uses | Rank | Client `.pex` Function / Event | Uses | Rank | Client `.pex` Function / Event | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `PlayAnimation` | `528` | 11 | `GetValue` | `100` | 21 | `HasKeyword` | `60` | 31 | `IsLocalPlayer` | `42` |
| 2 | `Event:OnBeginState` | `330` | 12 | `SetValue` | `99` | 22 | `Utility.RandomFloat` | `52` | 32 | `CancelTimer` | `42` |
| 3 | `Play` | `307` | 13 | `Event:OnActivate` | `97` | 23 | `PlaceAtMe` | `51` | 33 | `SetSubGraphFloatVariable` | `41` |
| 4 | `Event:OnLoad` | `284` | 14 | `Debug.Trace` | `94` | 24 | `RegisterForAnimationEvent` | `50` | 34 | `BlockActivation` | `39` |
| 5 | `Utility.Wait` | `275` | 15 | `Event:OnTimer` | `82` | 25 | `Event:OnInit` | `48` | 35 | `CreateCoord` | `39` |
| 6 | `GoToState` | `232` | 16 | `Game.GetLocalPlayer` | `78` | 26 | `Check` | `46` | 36 | `SetAnimationVariableFloat` | `36` |
| 7 | `Is3DLoaded` | `195` | 17 | `Dismember` | `72` | 27 | `GetTargetActor` | `45` | 37 | `Disable` | `36` |
| 8 | `Event:OnEffectStart` | `131` | 18 | `Sound.StopInstance` | `68` | 28 | `Cast` | `45` | 38 | `Remove` | `35` |
| 9 | `GetLinkedRef` | `121` | 19 | `Event:OnEffectFinish` | `67` | 29 | `RegisterForHitEvent` | `44` | 39 | `Event:OnUnload` | `33` |
| 10 | `StartTimer` | `118` | 20 | `Stop` | `60` | 30 | `Activate` | `43` | 40 | `ModValue` | `33` |

### 7.3 Shared-Systems Storage Model (`Fallout 76`, `SeventySix.esm` / `+ NW.esm`)
- **Reputation & Karma:** `954` `FACT` (`0` `REPU`, `0` Karma); Wastelanders faction standing (*Hostile*..*Ally*, `7` tiers) is tracked via faction quest/currency `AVIF`s (`3,284` / `3,287` `AVIF`, `5,885` / `5,892` `GLOB`).
- **Companions, Needs & Radiation:** `1` C.A.M.P. Lite Ally (`2,708` / `2,710` `PACK`); real-time food/water meters (`well-fed` buff model) + diseases; FO4 Max-HP rad cap (`179` `HAZD`, `47` `WATR`) **plus** `Mutation_*` `PERK`/`SPEL`s locked by `Starched Genes` and granted by radiation or Serums.
- **VATS, Ammo, Perks & C.A.M.P.:** Real-time VATS (`117` `BPTD`, `773` `CAMS`, `448` `CPTH`); `176` (`177`) `AMMO`, `12,736` (`12,743`) `OMOD`, `10` `DMGT`; **`401` `PCRD` Perk Cards + `13` `LOUT` Punch-Card Loadout slots** (`1,992` / `1,997` `PERK`, `0` Skills); portable **C.A.M.P.** module + `14,797` `COBJ` + `44` `CMPO` + `1,877` `FURN` (incl. inventory-recalled Power Armor chassis).

---

## 8. Starfield Engine Baseline (`Starfield.esm` + `8` Official `.esm`s) & Reuse / Hold Map

### 8.1 Quest, Dialogue & Cold-Start Hold Boundary
- **Quests (`QUST`) & Dialogue:** `Starfield.esm` contains `2,077` `QUST` (`14,537` `INDX` stages, `2,549` `QOBJ` objectives, `22,190` aliases, `1,349` `VMAD`-scripted, `223` `StartGameEnabled` flags in `DNAM`, `51` repeatable, `47` radiant), `68,154` `DIAL`, `126,347` `INFO` (`43,292` `CTDA`s: `809` `GetValue`, `469` `HasPerk`, `1,142` `GetInFaction`), and `7,613` `SCEN`. Across all `9` official `.esm`s (`Starfield.esm`, `BlueprintShips-Starfield.esm`, `SFBGS003/004/006/007/008/00D/047.esm`), totals are **`2,235` `QUST`, `73,461` `DIAL`, `137,111` `INFO`, `8,286` `SCEN`, and `30` `GPOF` Gameplay Options** (added in `SFBGS007.esm`).
- **Cold-Start Hold vs Protected Engine Floor (`CF-2`):**
  - Of `207` quests observed running on a vanilla cold start (`223` `DNAM` `StartGameEnabled` minus conditioned non-starting quests), **`DefaultHold` stops `195` running Starfield quests** (`199` entries total including `4` non-running `MQ*` guards: `HoldCore = 5`, `HoldCompanions = 18`, `HoldAudioTutorials = 14`, `HoldCityFaction = 80`, `HoldGenericDialogue = 32`, `HoldActivities = 16`, `HoldRadiant = 9`, `HoldShips = 21`, `HoldSystem = 4`).
  - Exactly **`12` Starfield quests (`12 / 12` verified `StartGameEnabled` in `Starfield.esm`) remain protected and running**:
    - **5 Warfare Squad & Follower Quests:** `SQ_Followers` (`0x00D773`), `SQ_Groups` (`0x1A9565`), `SQ_COM_CREW_AngerCombatOverride`, `SQ_Captive`, `SQ_Airlock`.
    - **7 Core Engine Plumbing Quests:** `SQ_PlayerShip`, `SQ_Parent`, `PlayerSkills` (`0x2C59E4`), `DialogueGeneric`, `DialogueGenericPlayer`, `SpeechChallenge` (`0x0128D0`), `Achievements_Quest`.

### 8.2 Script Runtime & Measured Top 40 Starfield Papyrus Functions / Events
- **Runtime:** Papyrus VM `v3.12` / source `v4.2` (`0xFA57C0DE`, `game_id=4`), introducing `Guard` re-entrant lock declarations (stored immediately after `variables` in `ObjectData`) and `LockGuards` / `UnlockGuards` / `TryLockGuards` (`0x30..0x32`) plus `ArrayGetAllMatchingStructs` (`0x2F`).
- **Counts:** `Tools/ContentResources.zip` ships **`5,033` `.psc` sources** (`101` `Native` headers + `4,932` non-native scripts; **`3,498` distinct case-folded functions and events**). `Starfield - Misc.ba2` (`4,740` `.pex`) + `SFBGS00D - Main.ba2` (`293`) + `SFBGS047 - Main.ba2` (`1`) total **`5,034` unique `.pex` files** (`196` `Native` headers, `4,745` active compiled scripts, `93` empty stubs; `175,279` instructions).

| Rank | Papyrus Function / Event (`ContentResources.zip`) | Uses | Rank | Papyrus Function / Event | Uses | Rank | Papyrus Function / Event | Uses | Rank | Papyrus Function / Event | Uses |
|---:|:---|---:|---:|:---|---:|---:|:---|---:|---:|:---|---:|
| 1 | `SetStage` | `9,358` | 11 | `MoveTo` | `1,933` | 21 | `Disable` | `1,048` | 31 | `CompleteAllObjectives` | `479` |
| 2 | `GetRef` | `6,630` | 12 | `EvaluatePackage` | `1,925` | 22 | `GetShipRef` | `839` | 32 | `BlockActivation` | `465` |
| 3 | `GetActorRef` | `4,390` | 13 | `Stop` | `1,842` | 23 | `RemoveItem` | `774` | 33 | `HasKeyword` | `426` |
| 4 | `SetObjectiveDisplayed` | `4,059` | 14 | `Trace` | `1,816` | 24 | `GetValueInt` | `628` | 34 | `GetLocation` | `422` |
| 5 | `SetObjectiveCompleted` | `3,897` | 15 | `GetValue` | `1,551` | 25 | `AddToFaction` | `538` | 35 | `Show` | `418` |
| 6 | `Game.GetPlayer` | `3,689` | 16 | `GetOwningQuest` | `1,300` | 26 | `RegisterForRemoteEvent` | `527` | 36 | `EnableNoWait` | `407` |
| 7 | `GetStageDone` | `3,473` | 17 | `AddItem` | `1,185` | 27 | `DisableNoWait` | `499` | 37 | `Play` | `403` |
| 8 | `SetValue` | `2,931` | 18 | `GetLinkedRef` | `1,148` | 28 | `IsObjectiveDisplayed` | `495` | 38 | `GotoState` | `393` |
| 9 | `Debug.Trace` | `2,893` | 19 | `Enable` | `1,100` | 29 | `ForceRefTo` | `484` | 39 | `DefaultScriptFunctions.Trace` | `392` |
| 10 | `Start` | `1,943` | 20 | `Utility.Wait` | `1,076` | 30 | `Utility.RandomInt` | `483` | 40 | `GetCount` | `386` |

### 8.3 Starfield Forms, Quests, and Scripts: Reused vs Replaced / Held by System

| Shared System | Reused Starfield Engine Forms, Quests & APIs | Held / Replaced / Rebuilt Starfield Layer |
| :--- | :--- | :--- |
| **New Game & Travel** | `DFOB StartupQuest_DO` (`0x00562D`, overridden once by `FO4SFNewGame.esm`), `COCMarkerHeading` (`0x000032`), `GameDaysPassed` (`0x000039`), `AutoloadDoor_Cave` (`0x24F9CE`), `Game.ShowRaceMenu(uiMode=2)` | `MQ00`, `MQ101`, `MQ101PostQuest`, `MQ_TutorialQuest_Misc04` **held**; Starfield surface/planet/galaxy Star Map **blocked** (`FO4SFPipboyMenu.dll` + `FO4SFPipboyTravel.esm`) |
| **Reputation & Karma** | `FACT` (`SetAlly` / `SetEnemy` / `GetFactionReaction`), `PlayerFaction` (`0x01C21C`), `AVIF`, `GLOB`, `PERK` (`ModBuyPrices` + `PcTrait`) | Vanilla UC/Freestar/Crimson Fleet bounty quests **held**; replaced by `FO4SFReputation.esm` (`FO4SF_RepKarma` + 16-state `Fame`/`Infamy` `AVIF`/`GLOB` arrays) |
| **Companions & Warfare Squads** | **`SQ_Followers` (`0x00D773`, `ActiveFollowers` collection)**, **`SQ_Groups` (`0x1A9565`)**, `DefaultMaster_FollowPackage` (`0x0301C5`), `SQ_Followers_Wait` (`0x29D080`), `FollowerState` (`0x000344`) | `COM_Companion_*`, `SQ_Companions`, `SQ_Crew`, `CREW_*` (`18` quests) **held**; wrapped by `FO4SFCompanions.esm` (`2 -> 4` `GLOB`-capped squad, rank/goodwill/loyalty gates, `CA_*` affinity) |
| **Hardcore / Survival** | `GPOF` (`GameplayOption`) & `GPOG` (`GameplayOptionsGroup`), `OnGameplayOptionChanged`, `CarryWeight`, `Utility.GetCurrentGameTime()` | **`SQ_ENV` (`0x248D20`)** & `SQ_PEO_SustenanceDialogue` **held** (`0` `ENV_*` suit/O2 soak); replaced by `FO4SFHardcore.esm` (`FO4SF_Hunger`/`Thirst`/`SleepDeprivation` `0..1000`, weighted ammo, Stimpak HoT) |
| **Radiation & Mutations** | `AVIF` (`DefaultToZero \| DamageIsPositive`), `HAZD` (`ENV_PoolHazard_Radiation` template), `WATR` (`ConsumeSpell`/`ContactSpell`), `IsInWater` `SPEL`, `Actor.ModValue` on `Health` (`0x0002D4`) & SPECIAL (`0x0002C2..0x0002C8`) | Vanilla `ENV_*` thermal/corrosive/airborne afflictions **held**; replaced by `FO4SFRads.esm` (`FO4SF_Rads` `0x800`, Mode A HP-cap <-> Mode B 5-stage stat sickness `GPOF`, optional `FO4SF_Mut_*` `PERK`s) |
| **VATS, Hit Locations & Ammo** | Live limb `AVIF`s (`PerceptionCondition` `0x00036C` .. `BrainCondition` `0x000372`), `HumanBodyPartData` (`0x003481`), `ModelABodyPartData` (`0x00562C`), `TerrormorphBodyPartData` (`0x21E736`), `SlowTimeChem` (`0x2A34F1` via `abBoostAssaultSlowTime` `0x0B0885`), `Weapon.GetAmmo()` & `Weapon.Fire()`, base `AMMO` (`0x04AD3E`, `0x04AD3F`, `0x0547A1`, `0x00E8EC`, `0x2B559A`) | Unmigrated FO4 `0x00038A..0x00038F` `BPTD` links **repaired on cloned `FO4SF_Combat*Bptd` records** (`0` vanilla overrides); missing `AMEF` replaced by `FO4SFCombat.esm` calibre `FLST` tables + `FO4SFCombat.dll` `V`/`N` hotkeys |
| **Progression (SPECIAL, Skills, Perks, Traits)** | `PlayerSkills` (`0x2C59E4` engine perk evaluator), `AVIF` (`1,107` base), multi-rank `PERK` entry points (`0..157`, `156/158` FO4 parity) | Starfield `21` space `Background*`, `17` space `TRAIT_*`, and `84` 4-rank `Skill_*` **unused/hidden**; replaced by `FO4SFProgression.esm` (`40`-pt SPECIAL, `13` NV Skills, Wasteland Backgrounds, `0..2` Traits w/ `1` exit respec, `GLOB` Perk cadence) |
| **Workshop, C.A.M.P. & Power Armor** | `WorkshopKeyword` (`0x054BA7`), `OutpostBeaconActivator` (`0x2C60E9`), `WorkbenchIndustrialKeyword` (`0x0AA209`), `332` `IRES` & `MISC` resources, `COBJ`, `Actor.SwitchToPowerArmor`, `isPowerArmorFrame` (`0x15503F`), `isPowerArmorBattery` (`0x05BDAA`) | `OutpostTutorial` & `SQ_OutpostCargoLink` **held**; FO4 `CMPO` (`31`) mapped `18:18` onto Starfield `IRES` in `FO4SFWorkshop.esm`; empty PA `DFOB`s replaced cleanly by `FO4SFPowerArmor.esm` (`6`-limb `BPTD` climb-in `FURN` + worn NCR `ARMO`) |
| **Dialogue & Papyrus Bridge** | Native `DialogueMenu.swf` (`DialogueListData.aChoices` list host + `[Perk]`/`[Trait]` tags), `SpeechChallenge` (`0x0128D0`), `97.32%` identical Papyrus base calls, `WwiseEvent`, `Location`, `Resource` | `DialogueMenu.swf` **never replaced**; 4-option FO4 turns use `#792` `FO4SF_DialogueWheel.swf`, list checks use `FO4SFListDialogue.esm`; deleted FO4 `Native` classes (`Sound`, `EncounterZone`, `Component`, `Holotape`, etc.) bridged by `16` `FO4SF_Shim_*` / adapter `.psc` scripts + `FO4SF_NativeBridge` |
