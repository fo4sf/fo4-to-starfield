Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (13-plugin playable path) & Track 2 (22-plugin experimental core)

# Candidate 2g — Opening Regression + `C1`–`C6` Fixes, `R1`–`R8` Repairs, Cold Reload, Sanctuary Workbench & `A4` Walking Headings Session Card (`Round 10` / `A3` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`--profile player`, `13` Track-1 plugins; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`) & **Warfare** (`--profile test`, `22` plugins, Track 2 experimental core, still WITHOUT `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) | Track: **Track 1 playable path** (`Cards 2g-1..2g-3`) + **`C4`/`C5`/`R6` & optional Track 2 spot checks** (`Card 2g-4`).
> - **PASSED IN GAME (`22 Nov 16:08Z–16:28Z`, Candidate `2f` `9b5327ff`, `#32` comment `7082117074`, `13`-plugin Story path, `20 min`, `0` crashes, `0` dumps):** First run from New Game to completed first mission (*When Freedom Calls*): **`B1`, `B2`, `B3`, `B4` FIXED IN GAME**; `33` `S.P.E.C.I.A.L.` points (`Pool of 40`); kept Fallout-look first-person `E` on Pip-Boy (`0A00080F`) and Vault Door Console (`0A000819`) with zero Starfield scanner box; `V4` catwalk hint; exit lift ride (reached by short `setpos`, not on foot; `V1` auto landing fade-in passed in `2e` `086edc15` `#issuecomment-7071239979`); Codsworth real `DialogueMenu` with 4 full FO4 choices and `"New mission: When Freedom Calls"` on HUD; Preston reading `stage 30`, stages `35 -> 40 -> 200`, `100` credits, `"New mission: First Settlement"`; border-safe `r9hop2` & `r9hop3`; in-session save/load after completion (`reload mission stage=200 relocate_fails=0`, no duplicate reward; cold quit-to-desktop reload not tested in `2f`); `F7` Pip-Boy & `M` map open/close.
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME` (Candidate `2g` Round 10):** Every Round-10 fix on this card — **`C1`** Preston single real `DialogueMenu` talk first (never double-talk), **`C2`** Codsworth & Preston zero greeting replay, **`C3`** Concord street fight with god mode OFF & zero `2.85 km` raider return, **`C4`** opaque Pip-Boy `F7` background + real `HP`/`AP` + `"10.23.2287"` date + closed-Pip-Boy `Tab`, **`C5`** Fallout-look Preston & Concord raiders *(only if W3 lands in the `2g` build; otherwise `NOT BUILT`)*, **`C6`** Codsworth `0.6 m` vs `2.0 m` camera safety, **`R1`–`R8`** opening-protection repairs (`MQ103` no longer starts at `Min00` `stage 200`, zero messagebox over Sanctuary workshop, `InitiallyDisabled` `0x800` on ~20 later-mission actors, native Pip-Boy scan cache & vector locks), **cold Quit-to-Desktop reload** at surface & mid-mission, and **`A4`** console-free walking headings — is **`TEST-STATION` (`prototype, offline` / OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs this card.
> - **`R8` Stand-In Truth Labels:** Any messagebox counter (`09000A15` opt-in Sanctuary helper, `09000B55` Signal Interceptor counter), single-`GLOB` *Prydwen* arrival (`09000AD6`), or missing-`FO4Port.esm` cell fallback is explicitly labeled a **stand-in** — never unqualified `"executable"`.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## Runtime Load-Order Hex Table (`FO4SFBridge.esm` & `FO4SFRouteLoot.esm` OFF)

| Hex Slot (`<XX>`) | `13`-Plugin `--profile player` (Track 1 Default) | `22`-Plugin `--profile test` (Track 2 Experimental) | Key Runtime FormIDs (`<XX>000...`) |
|---|---|---|---|
| `03` | `FO4ActorRaider.esm` | `FO4ActorRaider.esm` | Raider bases (`03F04800`, `03F04801`) |
| `04` | `FO4TerrainCore.esm` | `FO4TerrainCore.esm` | `04005C50` Sanctuary workbench, `040A775A` Sanctuary marker, `040A775B` Vault 111 / Commonwealth `WorldSpace` anchor, `040A775C` Concord marker |
| `05` | `FO4TerrainCore_Mars.esm` | `FO4TerrainCore_Mars.esm` | Commonwealth Mars registration |
| `06` | `FO4SFCoreValues.esm` | `FO4SFCoreValues.esm` | `06000801` `Radiation Health Cap`, `06000865` `FO4SF_PipboyAcquired`, `06000870` `FO4SF_GameMode` (`1`=Story, `2`=Warfare) |
| `07..08` | `07` `VaultGearDoor`, `08` `ExitLift` | `07` `VaultGearDoor`, `08` `ExitLift` | Vault 111 gear door rig & animated exit lift |
| `09` | `FO4SFMission.esm` | `FO4SFMission.esm` | **`09000800`** `FO4SF_Min00`, **`09000802`** `FO4SF_Min00_PrestonREF`, **`09000803..09000807`** `5` Concord raiders (merged Concord coords `C3`), **`09000811`** `FO4SF_CodsworthREF`, `09000814` `FO4SF_CodsworthKeeper` (`09000820` `FO4SF_CodsworthHellos`), **`09000816`** `FO4SF_Codsworth01`, **`09000817`** `FO4SF_Sanctuary01`, **`09000900`** Preston talk `SCEN`, **`09000940`** Codsworth talk `SCEN`, `09000970` `FO4SF_CodsworthTalkActi`, **`09000979`** `FO4SF_MissionTalkUseMessageBox` (default `0.0`) |
| `0A` | `FO4SFNewGame.esm` | `FO4SFNewGame.esm` | **`0A000800`** `FO4SF_NewGame`, **`0A00080F`** `FO4SF_PipboyCorpsePickupRef`, **`0A000819`** `FO4SF_GearDoorConsoleRef`, `0A000820`/`0A000821` Vault 111 pistol + ammo |
| `0B..10` | `0B` `Workshop`, `0C` `PowerArmor`, `0D` `FortHagen`, `0E` `PipboyProbe`, `0F` `PipboyTravel`, **`10` `FO4SFMapMarkers.esm`** (`100009EC` Museum of Freedom) | `0B` `Rads`, `0C` `Hardcore`, `0D` `Workshop`, `0E` `PowerArmor`, `0F` `Progression`, **`10` `FO4SFListDialogue.esm` (`10000810`)** ... `19` `FO4SFMapMarkers.esm` (`190009EC`) | Track 1 stays `13` plugins; `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` stay OFF in both profiles |

### `P3` Zero-`M`/`N`/`V` Console & `< 200 m`/Axis Hop Rules
1. Every ```` ```console ```` block and every batch filename below contains **zero `M`, `N`, or `V` letters** (case-insensitive) and **zero stripped mod `GLOB`/`QUST` EditorIDs**.
2. Every diagnostic `player.setpos` hop (`r9hop1`, `r9hop2`, `r9hop3`) moves strictly **`< 180 m` (`< 200 m`) per axis** to avoid Starfield's `BOUNDARY REACHED` border throw (`docs/terrain/core64c.md`, `docs/terrain/border.md`).

---

## Card 2g-1 — Swap from `2f` to Candidate `2g` (`13`-Plugin `--profile player`) & Exact Undo (`TOOLING` / `TEST-STATION`)

- **Starting Game State:** Prior Candidate `2f` `13`-plugin player bundle installed with `sidecar-install` and `FO4SFBridge.esm` held off. Leave `candidate-2f` and all older candidate folders untouched.
- **Stage Placeholders:** `<cand2g-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`, `InvDataAnswers=0`).
- **Plugin List (`Plugins.txt`, `13` plugins + `*FO4SFMapMarkers.esm`, `FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2g-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2g-session-bridge-off
```

### Exact Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required Startup PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>
step=menu_guard registered=<menus> count=<n>/38
step=map_config map_key=<vk> map_page=3 menus=<menus> block_starmap=0 store=<store> markers=<cnt> travel=<script>.<fn> survival=<0|1> heading_at=<sign>+<off>
```

### Negative / FAIL Conditions
- `this bundle was built at `, `sidecar install refused:`, `FO4SFRouteLoot.esm` or `FO4SFBridge.esm` active, or `block_starmap=1`.

---

## Card 2g-2 — Short `2f` Opening Regression Pass (`ran in game` Protection) & `A4` Walking Headings (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`0 B` extra on installed Card 2g-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2g-1.

### Install Command (Same Installed `13`-Plugin Bundle as Card 2g-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-player-bundle> --starfield <starfield-dir>
```

### Short `2f` Regression Checklist (One Proof Line Per Step — Must NOT Regress!)
1. **New Game Story start:** Main Menu -> New Game -> single `"Character Appearance"` -> `Quick start` -> `stage 20 by=Trigger`.
2. **Fallout-look `E` Pip-Boy & Console (`A1(c)`):** Aim at floor Pip-Boy (`0A00080F`, `0` Starfield box) -> **`E`** -> `pipboy pickup equipped flag=1 worn=true`; aim at console (`0A000819`, `0` Starfield box) -> **`E`** -> `stage 30 by=vault_console` + `catwalk hint shown`.
3. **Pool-of-40 Lift & Auto Surface Fade (`A1(b)` / `V1` / `B3`):** Walk onto lift -> spend **`33`** points (`40` total) -> `Continue` -> `landed z=<z> confirmed=True fallback=false` -> `stage 200 by=Trigger` -> `fade in by=story_landing` (zero console line; zero hilltop return-lift popup through `FO4SF_MapMarkersHop` `100008F4`).
4. **Console-Free Walking (`A4` — `34` Navmesh-Verified Segments Across `5` Legs in [`docs/testing/console-free-walk-list.md`](console-free-walk-list.md); navmesh-verified offline, terrain on converted Commonwealth unproven in game):** Use Starfield compass headings (`GetAngle Z = degrees(atan2(dx, dy)) % 360.0`; `0° = N/+Y`, `90° = E/+X`; full table & optional diagnostic walk-marker JSON via `scripts/newgame/walk_headings.py table`):
   - **`L1` Cryo Pod -> Pip-Boy (`0A00080F`):** `69.37 m` (includes `E` stops at the `2` closed default Vault 111 interior doors `0200126E` & `02001234` and corridor pillar bypass `X = -41..-47`; `02001608` is open by default).
   - **`L2` Pip-Boy -> Vault Door Console (`0A000819`):** `0.60 m` turn & step.
   - **`L3` Console -> Gear Door -> Catwalk -> Exit Lift Platform:** `44.86 m` (includes north-stair landing turn at `(-65.10, -3.96)` avoiding the west railing).
   - **`L4` Hilltop Landing -> NNE Switchback -> Vault 111 Creek Footbridge (`04014BA7`) -> Codsworth (`09000811`):** `207.23 m` (`4a`–`4i`, `100%` Commonwealth navmesh) ending at a **`2.83 m` `C6`-safe standoff**.
   - **`L5` Codsworth -> Sanctuary North Bridge (`04005199`) -> Red Rocket -> Concord Marker (`040A775C`) -> Preston (`09000802`):** `501.73 m` (`5a`–`5k`, `100%` Commonwealth navmesh) ending at a **`2.83 m` standoff** outside the Museum of Freedom door.
   - *(If diagnosing later steps fast, use `< 180 m`/axis hops `bat r9hop1`, `bat r9hop2`, `bat r9hop3` — never a single `> 200 m` jump.)*

```console
help "Health Cap" 4
sqs 0A000800
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required Short Proof Log Lines (`fo4sf_newgame.0.log` — One Line Per Step)
```log
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> catwalk hint shown
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> readback=<r0> <r6>
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> fade in by=story_landing loaded=true cell=<cell>; saving and HUD on
```

### Negative / FAIL Conditions
- Any `2f` PASS item regressing (`Points left != 33`, Starfield scanner box returning, missing catwalk hint, stuck black landing screen, or hilltop `return lift armed` firing before walking off the pad).

---

## Card 2g-3 — New `2g` Rows: Cold Reload (`Surface` + `Mid-Mission`), `C2`/`C6` Codsworth, `C3` Concord Fight (God Mode OFF), `C1` Preston Single Real Talk & `R1`/`R2`/`R3` *First Settlement* Workbench (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`0 B` extra on installed Card 2g-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2g-1.

### Install Command (Same Installed `13`-Plugin Bundle as Card 2g-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-player-bundle> --starfield <starfield-dir>
```

### New `2g` Step-by-Step Verification Rows
1. **Cold Quit-to-Desktop & Reload #1 — Surface (`Throwaway_2g_Surface`):**
   - Right after `V1` fades in on the Vault 111 hilltop, save **`Throwaway_2g_Surface`**, **`Quit to Desktop`** (full process exit, NOT in-session load), relaunch via SFSE, and load `Throwaway_2g_Surface`.
   - **Expected:** Same hilltop XYZ in daylight (zero black fade), `0A000800=200`, `09000816=10`, `09000800=0`, `reload mission stage=0 relocate_fails=0`, `codsworth01 reload stage=10 choices=0`, and zero spurious hilltop return-lift popup.
2. **`C2` & `C6` — Codsworth Single-Play Greeting & Safe Close/Walk-Up Camera (`09000940`):**
   - Walk (or `bat r9hop1`) to Sanctuary Hills (`(-2346.71, -1406.16, 111.73)` m). Test **both** standing `~2.0 m` away AND close (`~0.6 m` via `P3`-safe **`bat cods06`** -> `player.moveto 09000811`) -> press **`E`** on Codsworth (`09000811`).
   - **`C6` PASS:** If activated `< 1.65 m` away, `EnsureSafeCodsworthCameraDistance()` steps the player back to `1.85 m` along the sightline (`codsworth talk camera_guard prev_d=<d> safe_d=1.85`, outside his `0.65 m` chassis hull; `>= 1.65 m` walk-ups untouched). Camera frames Codsworth cleanly and NEVER clips under or inside his body.
   - **`C2` PASS (`INTV=1` Phase-1 Jump — `offline, unproven in game`):** Greeting plays **ONCE** (`phase=0` -> `phase=1`, `codsworth dialogue menu opened`); select a non-ending choice (e.g. `"Where can I go?"`) -> verify Codsworth answers and returns straight to `codsworth talk scene phase=1 stage=<st>` with **ZERO repeat of `phase=0`** and **ZERO 45 s greeting replay**! Pick the Concord lead -> `codsworth01 stage 100 by=info`, `min00 given by=codsworth`, `codsworth01 complete choices=<cnt> concord_pointed=true`, HUD `"New mission: When Freedom Calls"`.
3. **`C3` — Concord Street Fight With GOD MODE OFF & Zero `2.85 km` Raider Return (`09000803..09000807`):**
   - Walk (or `bat r9hop2` -> wait `3–5 s` -> `bat r9hop3`, both strictly `< 180 m`/axis) to the Museum of Freedom door `(-2011.14, -1697.54, 89.09)` m. Confirm **god mode (`tgm`) is OFF**!
   - **`C3` Stay-Put PASS:** Raiders `0`–`4` (`09000803..09000807`) are authored at merged Concord coordinates (`(-2029, -1698)`), NOT unmerged `(-829, +1002)` — verify `fo4sf_mission.0.log` shows **ZERO `before=2846..2868` `2.85 km` snap-back re-placement passes**!
   - **`C3` Live Combat & Hits-To-Kill PASS (God Mode OFF):** All `5` live raiders arm with `WEAP 0026D96B` Coachman + `60` `AMMO 002B4AFB` `AmmoShotshell` (`arm raider 0..4 ammo=60`, `Aggression=2`, `Confidence=4`, `SetRestrained(False)`) and receive `startcombat raider 0..4 d=<d>` (all `5`, not just `raider 0`!). **Starting-Character Survivability (`offline record estimate` — armor, difficulty, and level scaling ignored; Level-1 Vault 111 player = `180 HP`):** Coachman deals `52.0` base damage (`<= 20 m`) falling linearly to `26.0` damage (`35 m`), giving an offline record estimate of **`4` close-range full blasts** (`<= 20 m`: `4 x 52 = 208 >= 180 HP`) up to **`7` max-range blasts** (`35 m`: `7 x 26 = 182 >= 180 HP`) to kill! Confirm raiders advance/fire and take real HP off the player; defeat `1–2` raiders (`stage 20`), then run Cold Reload #2 before killing the rest!
4. **Cold Quit-to-Desktop & Reload #2 — Mid-Mission (`Throwaway_2g_MidWFC`):**
   - Save **`Throwaway_2g_MidWFC`** at `stage 20` (with `1–4` raiders dead) OR at `stage 30` (all `5` dead, before talking to Preston), **`Quit to Desktop`**, relaunch via SFSE, and load `Throwaway_2g_MidWFC`.
   - **Expected:** `reload mission stage=<20|30> relocate_fails=0`, dead raiders stay dead, living raiders stay at Concord, and Preston (`09000802`) stays held at the Museum door. Finish remaining raiders to reach `stage 30` (`Talk to Preston Garvey`).
5. **`C1` & `C2` — Preston's SINGLE Real Voiced `DialogueMenu` Talk (`09000900` First, NEVER Both!):**
   - Aim at **Preston (`09000802`)** at `stage 30` and press **`E`**.
   - **`C1` PASS:** `ResolvePrestonScene()` resolves `09000900` (`preston scene resolved via=<property|file>`) -> logs **`preston activated at stage 30`**, **`preston scene talk requested scene=<ref> stage=30`**, **`preston talk scene started stage=30`**, **`preston talk scene phase=0 stage=30`**, **`preston talk scene phase=1 stage=30`**, and **`preston dialogue menu opened`** — opens Starfield's real `DialogueMenu` FIRST with **ZERO `preston talk fallback=messagebox reason=no_scene`** and **ZERO four-button messagebox** before or after!
   - **`C2` PASS (`INTV=1` — `offline, unproven in game`):** Choosing any non-ending question returns directly to `preston talk scene phase=1 stage=30` with **ZERO repeat of `phase=0`**. Finish Preston's dialogue -> `stage 35 by=info`, `preston talk end info=0x092A -> stage 40`, `reward credits=100`, `stage 200 by=Trigger`, `complete stage=200`.
6. **`R1` + `R2` + `R3` — *"First Settlement"* at Sanctuary Workbench (`09000817` & `04005C50`):**
   - **`R1` Sole HUD Mission PASS (Deliberate One-Tracked-Opening Choice):** In Fallout 4, `MQ103` starts when `MQ102` ends while `Min01` (*Sanctuary*) is still running; here we make a deliberate one-tracked-opening-mission design choice: **`FO4SF_MQ103` (`09000A50`) waits until `FO4SF_Sanctuary01` (`09000817`) completes; after that it can also start at the Diamond City gate.** After `FO4SF_Min00` reaches `stage 200`, verify ONLY **`"New mission: First Settlement"`** (`09000817`) tracks on the HUD — `09000A50` MUST stay `stage 0` (dormant if touched early, NOT stealing `SetActive(True)`). *(Note: with `InvDataAnswers=1`, an early-started dormant quest is still running with zero objectives and may appear by name on the A5 `DATA / Quests` page until its predecessor completes.)*
   - **`R3` Actor Gating PASS:** Verify **Sturges (`09000A01`)** and all `19` later-mission actors (`Kellogg` `09000AD2`, `CorvegaBoss` `09000A24`, `Courser` `09000B32`, etc.) start **`InitiallyDisabled` (`0x800`)** during the opening until their owning mission stage enables them.
   - **`R2` Real Workshop First PASS:** Walk (or `bat r9hop2` -> `bat r9hop1`) back to Sanctuary workbench **`04005C50`** (`(-2329.25, -1420.19, 112.09)` m) and press **`E`**. Verify Starfield's real workshop opens cleanly with **ZERO messagebox popup over the workshop** (`RunWorkbenchBuildMenu` MUST NOT hijack bench activation!), and `fo4sf_mission.0.log` logs an honest `sanctuary01 bench_activated=true ref=<ref> complete=<true|false>` matching whether `CompleteQuest()` actually ran. Delete throwaway saves when done.

```console
help "Calls" 4 QUST
getstage 09000816
getstage 09000800
getstage 09000817
getstage 09000A50
sqs 09000800
sqs 09000817
bat r10stat
bat cods06
bat r9hop1
bat r9hop2
bat r9hop3
bat r9door
```

```bat
; <starfield-dir>/r10stat.txt — read-only globals & quest state (09=Mission, 06=CoreValues)
getglobalvalue 06000865
getglobalvalue 06000870
sqv 09000800
sqv 09000816
sqv 09000817
sqv 09000A50

; <starfield-dir>/cods06.txt — C6 close-case check (~0.6 m onto Codsworth 09000811; tests camera_guard safe_d=1.85)
player.moveto 09000811

; <starfield-dir>/r9hop1.txt — <180 m/axis hop: Vault 111 hilltop -> Sanctuary Codsworth (wait 3-5 s)
player.setpos x -2347
player.setpos y -1406
player.setpos z 113.0

; <starfield-dir>/r9hop2.txt — <180 m/axis hop: Sanctuary -> Red Rocket open ground (wait 3-5 s)
player.setpos x -2185
player.setpos y -1561
player.setpos z 106.5

; <starfield-dir>/r9hop3.txt — <180 m/axis hop: Red Rocket -> Concord Museum door
player.setpos x -2015
player.setpos y -1700
player.setpos z 90.5

; <starfield-dir>/r9door.txt — persistent 0x400 Museum of Freedom marker 100009EC (run after r9hop2 & map-marker settle)
player.moveto 100009EC
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log`)
```log
FO4SF_MISSION rt=<rt> codsworth01 reload stage=<st> choices=<cnt>
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=0
FO4SF_MISSION rt=<rt> codsworth talk camera_guard prev_d=<d> safe_d=1.85
FO4SF_MISSION rt=<rt> codsworth scene talk requested scene=<ref> via=<actor|proxy> stage=10
FO4SF_MISSION rt=<rt> codsworth talk scene started stage=10
FO4SF_MISSION rt=<rt> codsworth talk scene phase=<n> stage=<st>
FO4SF_MISSION rt=<rt> codsworth dialogue menu opened
FO4SF_MISSION rt=<rt> codsworth01 stage 100 by=info
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> arm raider <i> ammo=<n>
FO4SF_MISSION rt=<rt> startcombat raider <i> d=<d>
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> preston activated at stage 30
FO4SF_MISSION rt=<rt> preston scene resolved via=property scene=<ref>
FO4SF_MISSION rt=<rt> preston scene resolved via=file scene=<ref>
FO4SF_MISSION rt=<rt> preston scene talk requested scene=<ref> stage=30
FO4SF_MISSION rt=<rt> preston talk scene started stage=30
FO4SF_MISSION rt=<rt> preston talk scene phase=<n> stage=30
FO4SF_MISSION rt=<rt> preston dialogue menu opened
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 start_requested ok=True
FO4SF_MISSION rt=<rt> complete stage=200
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=false stage=100
```

### Negative / FAIL Conditions
- **`C1` FAIL:** `preston talk fallback=messagebox reason=no_scene` firing at stage 30 OR both messagebox and `DialogueMenu` opening; **`C2` FAIL:** Codsworth or Preston replaying the greeting after a choice; **`C3` FAIL:** raiders standing idle without moving/firing with god mode OFF OR `before=2846..2868` `2.85 km` return between passes; **`C6` FAIL:** camera clipping inside Codsworth at `0.6 m`; **`R1` FAIL:** `09000A50` (`FO4SF_MQ103`) starting at `Min00` `stage 200` or stealing HUD tracking; **`R2` FAIL:** any messagebox popping over the Sanctuary workshop on `04005C50` activation OR `complete=true` logged when quest did not complete; **`R3` FAIL:** Sturges or Act II bosses enabled on frame 1; or any cold-reload reset/crash.

---

## Card 2g-4 — `C4` Pip-Boy Screen, `C5` Fallout-Look Actors, `R6` Native Cache/Locks & Optional Track 2 (`--profile test`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-player-bundle>`, `<cand2g-test-bundle>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`13`-plugin player bundle or `22`-plugin test bundle without `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) + `~5 MB` `FO4SFPipboyMenu.dll` sidecar.
- **Plugin List (`Plugins.txt`):** Run `C4`/`C5`/`R6` on the `13`-plugin player bundle first; optionally swap to `<cand2g-test-bundle>` (`22` plugins without `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) for Track 2 spot checks.

### Install Command (`<cand2g-test-bundle>` Optional Track 2 Swap, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2g-test-bridge-off
```

### `C4`, `C5`, `R6` & Track 2 Spot Checks
1. **`C4` Pip-Boy Screen (`F7`, `M`, `Tab` — `docs/ui/pipboy-c4-fixes.md`):**
   - **Shipped `2g` Sidecar INI & One-Line Rollbacks:** `candidate-2g` ships **`ShellBackdrop=1`**, **`ShellVitalsFill=1`**, **`SuppressDataMenu=0`**, **`TabOpensPipboy=0`** under `[FO4SFPipboyMenu]` (`MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0` untouched; startup logs `step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0`), so pressing **`F7`** shows both the opaque CRT background and real `HP`/`AP` immediately out of the box! **One-line rollbacks** to the exact `2f` path (no DLL rebuild): set **`ShellVitalsFill=0`** and/or **`ShellBackdrop=0`**. To test hiding Starfield's closed-Pip-Boy `DataMenu` on `Tab`, opt in with **`SuppressDataMenu=1`** (`TabOpensPipboy=0`).
   - Press **`F7`**: verify the Pip-Boy page renders over an **opaque dark CRT background** (ZERO 3D world bleed-through! `step=shell_backdrop movie=<hex> ok=1 target=root_graphics color=0x041409 alpha=0.97`).
   - Verify **`HP`** shows real numeric `cur/max` (`> 0`, NEVER `HP 0/0`!) and **`AP`** shows real numeric `cur/max` (NEVER `AP --/--`! `step=shell_vitals when=kShow page=0 tab=0 hp=<cur>/<max> ap=<cur>/<max> ...`).
   - Press **`M`** outdoors: verify the map footer date reads **`10.23.2287`** (full 4-digit year, NOT cut `"10.23.228"`! `step=shell_date_fix ... old_w=150.0 new_w=<w>`) and **`Tab`** closes cleanly.
   - With the Pip-Boy **closed**, press **`Tab`** (and confirm closing `DialogueMenu` / `WorkshopMenu` with `Tab` never accidentally pops the Pip-Boy thanks to the `500 ms` blocking-menu cooldown): `SuppressDataMenu=1` hides Starfield's `"Mars - Commonwealth 00"` `DataMenu` (`step=data_menu_suppress ... menu=DataMenu sent=hide`).
2. **`C5` Fallout-Look Actors & HUD Audit (`docs/design/c5-actor-and-hud-looks.md` — only if W3 lands in the `2g` build; otherwise `NOT BUILT`):**
   - *(R15 status: run this row only if W3 lands in the `2g` build; otherwise mark `NOT BUILT`.)* Inspect **Preston (`09000802`)** and all `5` **Concord raiders (`09000803..09000807`)**: confirm **ZERO Starfield spacesuits or helmets**, dressed in converted Fallout 4 outfits/faces; note wrist HUD `MARS` O2/CO2 status per `c5-actor-and-hud-looks.md`.
3. **`R6` Native Quest-Scan Cache & Vector Locks:**
   - With `InvDataAnswers=0` (default player INI), confirm `FO4SFPipboyMenu.log` logs **`step=quest_cache_build`** **ONCE** after `PostDataLoad` (zero repeated `1,024`-lookup storm per 500 ms vitals tick) and rapid `M` / fast-travel / close cycles never race or crash (`g_pushedIndicesLock` leaf mutex).
4. **Optional Track 2 (`--profile test`, `22` plugins):** Card A (`10000810`) via `bat carda0..carda3`.

```console
help "List Dialogue" 4 QUST
sqs 10000810
bat carda0
bat carda1
bat carda2
bat carda3
```

```bat
; <starfield-dir>/carda0.txt (10000810 in 22-plugin test order without FO4SFRouteLoot.esm)
sqv 10000810
startquest 10000810
coc FO4SF_ListTalkCell

; <starfield-dir>/carda1.txt
setstage 10000810 10

; <starfield-dir>/carda2.txt
setstage 10000810 15

; <starfield-dir>/carda3.txt
setstage 10000810 70
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log`, `FO4SFListDialogue.0.log`)
```log
step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0
step=shell_backdrop movie=<hex> ok=1 target=root_graphics color=0x041409 alpha=0.97
step=shell_vitals when=kShow page=0 tab=0 hp=<cur>/<max> ap=<cur>/<max> lvl=<n> hp_src=<av|formula> ap_src=<av|formula>
step=shell_date_fix when=<when> old_w=150.0 new_w=<w> auto_size=1 word_wrap=1 width_set=1
step=quest_cache_build plugins=<n> quests=<m> workshop=<0|1> scanned=<k>
step=map_config map_key=<vk> map_page=3 menus=<menus> block_starmap=0 store=<store> markers=<cnt> travel=<script>.<fn> survival=<0|1> heading_at=<sign>+<off>
FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true
FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true
```

### Negative / FAIL Conditions
- Transparent `F7` Pip-Boy background showing 3D world bleed-through, `HP 0/0`, `AP --/--`, cut `"10.23.228"` date, Starfield spacesuits/helmets on Preston or raiders, or `FO4SFRouteLoot.esm`/`FO4SFBridge.esm` active.
