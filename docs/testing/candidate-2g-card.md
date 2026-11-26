Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (13-plugin playable path) & Track 2 (22-plugin experimental core)

# Candidate 2g — Opening Regression + `C1`–`C6` Fixes, `R1`–`R8` Repairs, Cold Reload, Sanctuary Workbench & `A4` Walking Headings Session Card (`Round 10` / `A3` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`--profile player`, `13` Track-1 plugins; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`) & **Warfare** (`--profile test`, `22` plugins, Track 2 experimental core, still WITHOUT `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) | Track: **Track 1 playable path** (`Cards 2g-1..2g-3`) + **`C4`/`C5`/`R6` & optional Track 2 spot checks** (`Card 2g-4`).
> - **PASSED IN GAME (`22 Nov 16:08Z–16:28Z`, Candidate `2f` `9b5327ff`, `#32` comment `7082117074`, `13`-plugin Story path, `20 min`, `0` crashes, `0` dumps):** First run from New Game to completed first mission (*When Freedom Calls*): **`B1`, `B2`, `B3`, `B4` FIXED IN GAME**; `33` `S.P.E.C.I.A.L.` points (`Pool of 40`); kept Fallout-look first-person `E` on Pip-Boy (`0A00080F`) and Vault Door Console (`0A000819`) with zero Starfield scanner box; `V4` catwalk hint; exit lift ride (reached by short `setpos`, not on foot; `V1` auto landing fade-in passed in `2e` `086edc15` `#issuecomment-7071239979`); Codsworth real `DialogueMenu` with 4 full FO4 choices and `"New mission: When Freedom Calls"` on HUD; Preston reading `stage 30`, stages `35 -> 40 -> 200`, `100` credits, `"New mission: First Settlement"`; border-safe `r9hop2` & `r9hop3`; in-session save/load after completion (`reload mission stage=200 relocate_fails=0`, no duplicate reward; cold quit-to-desktop reload not tested in `2f`); `F7` Pip-Boy & `M` map open/close.
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME` (Candidate `2g` Round 10):** Every Round-10 fix on this card — **`C1`** Preston single real `DialogueMenu` talk first (never double-talk), **`C2`** Codsworth & Preston zero greeting replay, **`C3`** Concord street fight with god mode OFF & zero `2.85 km` raider return, **`C4`** opaque Pip-Boy `F7` background + real `HP`/`AP` + `"10.23.2287"` date + closed-Pip-Boy `Tab`, **`C5`** Fallout-look Preston & Concord raiders (`09000980..0900098A`, triple-lock spacesuit strip; `outfit/hat = FO4 meshes [offline-proven]`, `face = Starfield chargen approximation` because the FO4 FaceGen head is not converted), **`C6`** Codsworth `0.6 m` vs `2.0 m` camera safety, **`R1`–`R8`** opening-protection repairs (`MQ103` no longer starts at `Min00` `stage 200`, zero messagebox over Sanctuary workshop, `InitiallyDisabled` `0x800` on ~20 later-mission actors, native Pip-Boy scan cache & vector locks), **cold Quit-to-Desktop reload** at surface & mid-mission, and **`A4`** console-free walking headings — is **`TEST-STATION` (`prototype, offline` / OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs this card.
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
| `09` | `FO4SFMission.esm` | `FO4SFMission.esm` | **`09000800`** `FO4SF_Min00`, **`09000802`** `FO4SF_Min00_PrestonREF`, **`09000803..09000807`** `5` Concord raiders (merged Concord coords `C3`), **`09000811`** `FO4SF_CodsworthREF`, `09000814` `FO4SF_CodsworthKeeper` (`09000820` `FO4SF_CodsworthHellos`), **`09000816`** `FO4SF_Codsworth01`, **`09000817`** `FO4SF_Sanctuary01`, **`09000900`** Preston talk `SCEN`, **`09000940`** Codsworth talk `SCEN`, `09000970` `FO4SF_CodsworthTalkActi`, **`09000979`** `FO4SF_MissionTalkUseMessageBox` (default `0.0`), **`09000980..0900098A`** `C5` Preston & Concord raider FO4 outfits/armors |
| `0A` | `FO4SFNewGame.esm` | `FO4SFNewGame.esm` | **`0A000800`** `FO4SF_NewGame`, **`0A00080F`** `FO4SF_PipboyCorpsePickupRef`, **`0A000819`** `FO4SF_GearDoorConsoleRef`, `0A000820`/`0A000821` Vault 111 pistol + ammo |
| `0B..10` | `0B` `Workshop`, `0C` `PowerArmor`, `0D` `FortHagen`, `0E` `PipboyProbe`, `0F` `PipboyTravel`, **`10` `FO4SFMapMarkers.esm`** (`100009EC` Museum of Freedom) | `0B` `Rads`, `0C` `Hardcore`, `0D` `Workshop`, `0E` `PowerArmor`, `0F` `Progression`, **`10` `FO4SFListDialogue.esm` (`10000810`)** ... `19` `FO4SFMapMarkers.esm` (`190009EC`) | Track 1 stays `13` plugins; `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` stay OFF in both profiles |

### `P3` Typed-Console & Batch-Filename Zero-`M`/`N`/`V` & `< 200 m`/Axis Hop Rules
1. The zero-`M`/`N`/`V` (`P3`) rule applies **ONLY to typed interactive ```` ```console ```` lines and `<bat-id>.txt` batch filenames** (case-insensitive, because typing `M`, `N`, or `V` in the console can trigger menu hotkeys) — it does **NOT** apply to `.txt` batch file contents (```` ```bat ```` blocks intentionally contain `getglobalvalue`, `sqv`, `player.moveto`, etc., executed from disk without keystrokes). Both ```` ```console ```` and ```` ```bat ```` still forbid stripped mod `GLOB`/`QUST` EditorIDs (`set`/`help FO4SF_*`).
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
   - Walk (or `bat r9hop2` -> wait `3–5 s` -> `bat r9hop3`, both strictly `< 180 m`/axis) to the Museum of Freedom door `(-2011.14, -1697.54, 89.09)` m. Play with **god mode OFF** (do NOT enable god mode in the console; leave normal player damage active).
   - **`C3` Stay-Put PASS:** Raiders `0`–`4` (`09000803..09000807`) are authored at merged Concord coordinates (`(-2029, -1698)`), NOT unmerged `(-829, +1002)` — verify `fo4sf_mission.0.log` shows **ZERO `before=2846..2868` `2.85 km` snap-back re-placement passes**!
   - **`C3` Live Combat PASS (God Mode OFF):** Raiders arm with `WEAP 0900097B` `"Coachman"` (`dmg=4.0`) + `0900097A` `"Eon"` (`dmg=1.5`) (`arm raider 0..4 ammo=60`, `Aggression=2`, `Confidence=4`, `SetRestrained(False)`) and receive `startcombat raider 0..4 d=<d>` (all `5`). Standing idle (god mode OFF) drops **HP `>= 20` within `10 s` while remaining alive at `10 s`**, and taking cover while shooting back clears **`5/5` raiders cleanly to `stage 30` within `60` rounds** (`FAIL`: idle death in `< 10 s`, or running out of ammo). Defeat `1–2` raiders (`stage 20`), then run Cold Reload #2 before killing the rest! *(See [`Card 2g-fix7`](#card-2g-fix7--wave-a-playable-01-blockers).)*
4. **Cold Quit-to-Desktop & Reload #2 — Mid-Mission (`Throwaway_2g_MidWFC`):**
   - Save **`Throwaway_2g_MidWFC`** at `stage 20` (with `1–4` raiders dead) OR at `stage 30` (all `5` dead, before talking to Preston), **`Quit to Desktop`**, relaunch via SFSE, and load `Throwaway_2g_MidWFC`.
   - **Expected:** `reload mission stage=<20|30> relocate_fails=0`, dead raiders stay dead, living raiders stay at Concord, and Preston (`09000802`) stays held at the Museum door. Finish remaining raiders to reach `stage 30` (`Talk to Preston Garvey`).
5. **`C1` & `C2` — Preston's SINGLE Real Voiced `DialogueMenu` Talk (`09000900` First, NEVER Both!):**
   - Aim at **Preston (`09000802`)** at `stage 30` and press **`E`**.
   - **`C1` PASS:** `ResolvePrestonScene()` resolves `09000900` (`preston scene resolved via=<property|file> scene=<ref>` — either `via=property` **OR** `via=file` satisfies `C1`, never requiring both in one run) -> logs **`preston activated at stage 30`**, **`preston scene talk requested scene=<ref> stage=30`**, **`preston talk scene started stage=30`**, **`preston talk scene phase=0 stage=30`**, **`preston talk scene phase=1 stage=30`**, and **`preston dialogue menu opened`** — opens Starfield's real `DialogueMenu` FIRST with **ZERO `preston talk fallback=messagebox reason=no_scene`** and **ZERO four-button messagebox** before or after!
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

### Required PASS Log Lines (`fo4sf_mission.0.log`; for `C1`, either `via=property` OR `via=file` passes, never both)
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
FO4SF_MISSION rt=<rt> preston scene resolved via=<property|file> scene=<ref>
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
2. **`C5` Fallout-Look Actors & Wrist HUD Audit (`docs/actors/c5-actor-and-hud-looks-report.md`):**
   - **Offline-Proven vs In-Game Truth (`R15`):** Triple-lock spacesuit/helmet strip (`ActorShouldForceHideSpacesuit_AV = 1.0` + `DOFT` & `SOFT` set to non-spacesuit clothes `OTFT`s **`09000980`** on Preston & **`09000988`** on `FO4_LvlRaider` override); **`outfit/hat = FO4 meshes (offline-proven: 3 .nif, 8 .mesh, 3 Preston .mat, 9 Preston .dds verified by stage_c5_actor_looks.py --verify-only; 27 Data files [3/8/4/12] packed)`**; **`face = Starfield chargen approximation`** (`EncFreestarSecurityFaceM04` morphs/tints + `ClassicBeard` + `Faded_Afro` `0x006852` + FO4 `0x00019FD9` weight/colors, because the FO4 FaceGen head is not converted; `HumanRace` `SkinAttach` deformation & live outfit evaluation are `prototype, offline` until run).
   - Inspect **Preston (`09000802`)** and all `5` **Concord raiders (`09000803..09000807`)**: confirm **ZERO Starfield spacesuits or helmets**, Preston wearing his Minuteman duster & hat (`09000980..09000985`) with African-American face/beard, and raiders wearing Fallout 4 raider underarmor/armor (`09000988..0900098A`); note wrist HUD (`MARS` dynamic `PNDT ANAM` vs hardcoded `O2`/`CO2` movie clips per `docs/actors/c5-actor-and-hud-looks-report.md`).
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

---

## Card 2g-fix6 — Earth Gravity, Paused Exit Lift, Concord Raiders, Pip-Boy Gate, Codsworth & 10mm (`2026-11-25`)

- **Stage Placeholders:** `<cand2g-fix6-player>`, `<cand2g-fix6-test>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`13`-plugin player bundle or `22`-plugin test bundle without `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) + `~5 MB` `FO4SFPipboyMenu.dll` sidecar.

### Install Command (`<cand2g-fix6-player>`, Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix6-player> --require-map-markers
python scripts/game/exp_install.py install --exp-dir <cand2g-fix6-player> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix6-player> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --dir <cand2g-fix6-player>/map-markers --starfield <starfield-dir>
```

| Fix Item | What Changed in `candidate-2g-fix6` | Acceptance / Evidence Requirement |
|---|---|---|
| **1. Earth Gravity (`1.00 g`)** | `FO4TerrainCore_Mars.esm` (`PNDT 0x0003F59A` `OrbitedData` `FNAM`) patched to `1.0000g` (`9.81 m/s^2`); verified in `make_core_bundle.py verify` and `check_beginning_pilot.py check-bundle`. | **`VIDEO`:** Drop an inventory object outdoors in Sanctuary/Commonwealth; falls crisply at `~9.8 m/s^2` (no Mars slow-float). |
| **2. Paused Exit Lift + Smooth Ride + Last-Resort FastTravel** | Paused `FO4SF_LiftMenu` (`FO4SF_LiftScreen.swf`, `0x19 \| kPauseFlag`) with unified 40-pt S.P.E.C.I.A.L. Pool, `0.2 s` ascent poll + overlap fade-out (`LiftSeconds - 1.1`) into `ReleaseStoryLandingFade`, removed immediate interior `TrySurfaceExteriorFallbacks` from `Surface()`, moved last-resort fallback to `FinishSurface`, removed `AddToMap`/`SetMarkerDiscovered` from `TryFastTravelSurface`. Preserve `fix5` death-reload Vault safety. | **`VIDEO` + 2-run proof:** Pod -> cog door -> paused Lift Menu (`S.P.E.C.I.A.L.` / `Change Appearance` / `Ride`) -> smooth faded ascent -> Commonwealth (Vault 111 NOT prematurely discovered via fast-travel); plus pod death-reload & reload-then-exit logs. |
| **3. Concord Raiders (Player Target, Grip, Clean Death)** | Removed FO4 `malehands.nif` from `concord_raider_m.nif` (`0x28` bare-handed BO64 letting Starfield `AA_Naked_Hands` grip guns), mapped `Belly`/`UpperBelly` to `C_Spine1`/`C_Spine2`, aligned FO4 forearm/wrist cuffs to Starfield A-pose (`<= 3 cm`), cleared `TemplateActorType.AiData` + explicit `Aggressive`/`Brave` on `0x986`, set `abPreventRemoval=False` on `0x97A`. | **`VIDEO`:** Raiders visibly lock onto & shoot the player (Preston held out), hands hold guns cleanly without forearm/vertex stretching on death ragdoll. |
| **4. Pip-Boy Pickup Gate & Examine Idle** | Shipped `RequirePickup=1`; native gate checks `FO4SF_PipboyAcquired >= 0.5` AND live owned+worn `FO4SFNewGame.esm:0x00080D`; `HandlePipboyPickup` triggers `IdleExamineWatch` (`Starfield.esm:0x000C154F`). | **`VIDEO`:** `F7` refused before corpse pickup & when unequipped/dropped; looting wrist plays watch-examine idle and unlocks `F7`/`M`. |
| **5. Codsworth (`#854` & Framing)** | Documented in `docs/design/codsworth-handy-status.md` (`#854` `claude/robot-anim` fixes 58 `.af` clips on 112-bone `.rig`, 5 `.mat`/`.dds`, `DirectAt` `z=0.984447 m`); `02b-mission` built with `--codsworth-race-framing 1`. | Sanctuary Codsworth talk frames cleanly; full `#854` animation/material integration ready once `#854` merges. |
| **6. Vault 111 10mm Pistol (`0x822` & `#853`)** | Created `WEAP 0x000822` (`FO4SF_Vault111_10mm`, Name `"10mm Pistol"`, capacity `12`, damage `18`), pointed `0x820` to `0x822` (keeping `VaultPistolBase` `B5` parity); comparison & `#853` notes in `docs/design/10mm-comparison-and-853-notes.md`. | Vault 111 desk weapon displays `"10mm Pistol"` with 12-round mag & 18 dmg and triggers `pistol picked` auto-equip. |

### Undo Command (Game Closed)
```bash
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Verification & Log Lines (`2g-fix6`)
```log
step=lift_open confirmed=<confirmed>
step=lift_confirm action=<action> confirmed=<confirmed> values=<s>,<p>,<e>,<c>,<i>,<a>,<l>
FO4SF_NEWGAME rt=<rt> lift menu action=ride
FO4SF_NEWGAME rt=<rt> ascent fade_out elapsed=<t>
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=<worn>
FO4SF_NEWGAME rt=<rt> pipboy pickup examine_idle=<idle>
FO4SF_NEWGAME rt=<rt> pistol picked item=<form> count=<n> equipped=<eq>
```

---

## Card 2g-fix7 — Wave A Playable-0.1 Blockers (`candidate-2g-fix7b`)

- **Stage Placeholders:** `<cand2g-fix7b-player>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`13`-plugin player bundle without `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) + `~5 MB` `FO4SFPipboyMenu.dll` (`Arm=1`, loose `Interface/Translate_en.txt`) sidecar.
- **Plugin List (`Plugins.txt`, `13` Track-1 plugins + `*FO4SFMapMarkers.esm`; `FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`
- **Codsworth Framing (`G1` / `fix6` parity):** `FO4SFMission.esm` stages with `--codsworth-race-framing 1` (`codsworth_race_framing=true`, restoring `fix6` look parity; choice-list camera still aims low until `#854` H3).

### Install Command (`<cand2g-fix7b-player>`, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix7b-player> --port <starfield-dir>\Data\FO4Port.esm --require-map-markers
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2g-fix7b-player>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix7b-player> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack --textures-archive
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix7b-player> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --dir <cand2g-fix7b-player>/map-markers --starfield <starfield-dir>
```

### Wave A & Wave B Playable-0.1 Verification Matrix (`Items 0–8` + `4b` + `G4`–`G13`)

> **Save / Reload Rule (`G11`):** Manual saving is locked inside Vault 111 (`vault_death_recovery=save_locked`). Never ask for a manual save inside the vault — use the automatic **pickup autosave** (`TriggerVaultPickupAutosave` right after picking up `0A00080F`) inside Vault 111, and make a manual **surface save** only after landing on the Commonwealth hilltop.

| Wave Item | Truth Label | Requirement & Console-Free Verification | Evidence / **`VIDEO`** Requirement |
|---|---|---|---|
| **0. Preflight — Papyrus INI & 10 s Log Gate (`G3`)** | **`TEST-STATION`** | Confirm all three `[Papyrus]` keys (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`, set by Claude with `python scripts/bridge/make_bridge.py ini`, game closed) are active BEFORE playing. Check that `fo4sf_newgame.0.log` has a **new non-empty timestamp within `10 s` of clicking New Game**, else stop. | Non-empty `fo4sf_newgame.0.log` `< 10 s` from New Game launch. |
| **1. Wrist Pip-Boy (`0A00080D`, `0x823`, `0x824`, `0x867`, `0x868`) (`G5`, `G12(a)/(b)`)** | **`TEST-STATION`** / **`REACHABLE`** | TX/DX10 `- Textures.ba2` + housing `0x823` (bit `54`) + screen `0x824` (bit `55`) + keyword `FO4SF_Kw_Pipboy` (`0x000867`) + 3-state `FO4SF_PipboyScreenSource` (`0x000868`: `0=INI`, `1=2D`, `2=3D`) in `FO4SFCoreValues.esm` (`pipboyGranted` bool, `ForceFirstPerson` + `SheatheWeapon` + `IdleExamineWatch` on pickup, female `*_1st_f.nif`). **Two reload cases (`G5(d)` / `G12(a)`):** (a) **Pickup-autosave reload:** die after picking up `0A00080F` -> reload restores Pip-Boy on wrist, `F7` works, `stage 20` pickup does not repeat (`vault_death_recovery=autosave stage=<n> after=pipboy_pickup`); (b) **Surface-save reload:** `pipboy wrist reequip on_load=load acquired=true worn=true`. **Wrist raise (`G12(b)`):** **`Arm=1`** default raises wrist first on **`F7`** (`step=pipboy_raise mode=<idle\|arm> ms=<n> opened=<0\|1>`), skipping raise in PA/swimming/menus. **Spacesuit & PA torso (`G5(b)`):** Chronomark bits `54\|55` stripped from all non-Pip-Boy FO4SF armor addons; verify 1st/3rd person with spacesuit and PA torso equipped. | **`VIDEO`:** Left-wrist Pip-Boy in **1st person** (`Arm=1` raise -> 2D menu) and **3rd person** (including spacesuit + PA torso check), plus **pickup-autosave death-reload**, **surface-save reload**, and **exit lift arrival** (`v111-wrist-pipboy`). |
| **2. Toasts & `QUEST` Label (`G9`, `G12(d)/(f)`)** | **`TEST-STATION`** / **`REACHABLE`** | `landing_handoff=single_quest` default keeps *"Out of Time"* single-quest on surface arrival (`landing handoff mode=single_quest`), `ShowObjectiveOnce` + `MuteDuplicateObjectiveToasts` VMAD on `0x816`/`0x800` mute duplicate Objective `10`/`85`/`86` toasts (`codsworth01 objective10_toast skipped=true reason=already_displayed`), loose 20-key `Interface/Translate_en.txt` (`source_ba2` pinned) rewrites `$MISSION*`/`$Mission*` menu & HUD keys to **`QUEST` / `Quests` / `Quest Log`** (`step=hud_quest_label` + `step=hud_quest_label_runtime`). | Confirm single *"Out of Time"* flow on arrival + after Codsworth talk, zero `"MISSION"` toast headers (`QUEST` shown). |
| **3. Silent Arrival, Silent Strip, Single-Pass Fade & Red Rocket Fix (`G9(e)`, `G10`)** | **`REACHABLE`** / **`TEST-STATION`** | `FO4SF_MapMarkers` sets `HoldDark=False` and `ReturnAnchor=0x000800` (eliminating the `~25 s` black hold + Red Rocket `Markers[0]` hop/banner!). `DiscoverSingleMarkerSilent` silently discovers `0x0A775B` via `AddToMap(True)` (`SilentArrivalDiscovery=True`, `ArrivalDiscoveryMethod=add_to_map`), shared `StripStarterItemsSilently` clears starter gear on both Story & Warfare, and `RegisterStartLoadingHook` (`landingMode=True`) runs a single-pass fade-in cleanly. **REACHABLE:** fast-travel back to Vault 111 from Sanctuary. **TEST-STATION:** test `AddToMap(True)` via existing `FO4SF_MarkerProbeQuest` stage `80` (`FO4SFMARK ... addtomap stage=80 name=TEST3 allowfasttravel=true`). | Confirm silent cryo -> surface transition with zero Vault 111 or Red Rocket discovery banner, clean Sanctuary -> Vault 111 fast travel, and zero item-strip spam. |
| **4. Lift Flow, Unspent S.P.E.C.I.A.L. Lock & Rising Arrival (`G7`, `G8`, `G12(c)/(e)`)** | **`TEST-STATION`** | Unified `ShowPausedExitLiftMenu` (`0x19 \| kPauseFlag`) drives both Vault exit and hilltop/Vault return. **`G12(c)`:** `FO4SF_LiftMenu` refuses Ride while unspent pool `> 0` (`"RIDE LIFT TO SURFACE (SPEND <n> POINTS FIRST)"`, opening S.P.E.C.I.A.L. editor instead; `step=lift_confirm action=ride pool=0`). **`G7`:** no Starfield loading screen during up transfer (`RegisterStartLoadingHook` landing mode + `2 s` guard), top arrivals (first & repeat) rise cleanly through opening surface hatches (`StateB_Play`), every abort path lifts any held fade. | **`VIDEO`:** Continuous clip of boarding platform -> spending all `33` S.P.E.C.I.A.L. points -> `Ride` -> smooth transfer -> rising through opening surface hatches into Commonwealth daylight (`v111-lift-flow`). |
| **4b. Direct-Override Surface Lift Cog Bidirectional Up/Down (`G4`, `G7`, `G8`)** | **`TEST-STATION`** | **`G4`:** `FO4SFExitLift.esm` overrides `ACTI 0x0A2D4B` directly (zero `PlaceAtMe`, zero duplicate cog `0x802`, `FO4TerrainCore.esm` master); runtime cog re-resolves static REFR within `0.05 m` at landing elevation. `lift_pairs.json` supplies both interior & surface timings plus `cog_pad_radius_m=3.2`, interior lift rides down when needed (3-try cap on down transfer), and emits `LiftPairArrived` `CustomEvent`. | **`VIDEO`:** Side view of surface cog descending (rider sinking with platform before fade), interior descent/floor arrival, and ride back up from below (`v111-cog-bidirectional`). |
| **5. Pod Safe Exit + Stage-15 Hook (`G6`)** | **`TEST-STATION`** | `RunPodExitHook` sets `Stage 15` BEFORE `stage 20` on all routes (`FO4SF_NewGameLooks`, `LooksWait`, `no-looks`, `preworld`), steps via `pod_entry_step_m` + `PodSafeStep` onto clear footing, uses safe spawn on `OnDying` reset, and logs actual `moved=<bool>`. | **`VIDEO`:** Clip from `"Character Appearance"` close -> cryo pod open -> clean footing outside pod (`v111-pod-safe-exit`). |
| **6. 10mm Pistol (`0A000820`/`0A000822`, `XM-2311` Stand-In Until `H4`) & Falling Objects (`G11`)** | **`REACHABLE`** / **`TEST-STATION`** | **`0A000822` is a `Starfield stand-in (XM-2311 / .45) until H4`** (`18 dmg`, `12-round` mag). **Armory walk (`L10`, status: `pushed, not run`):** from Pip-Boy spot `(-54.50, 0.00, 0.59)`, follow verified Leg `L10` (`10a`-`10f`, `74.65 m`, `302/302` Vault 111 `NAVM` hits in [`walk_headings.py`](../../scripts/newgame/walk_headings.py) & [`console-free-walk-list.md`](console-free-walk-list.md)) east through unlocked doors `02001607` & `02001609`, north to `y = 14.63`, west & north through unlocked `0200160A`, and west through open gate `02001539` to `(-56.25, 30.00, 0.00)` -> press **`E`** on `0A000820` (`(-57.0338, 30.006, 1.29)`, `0.86 m` reach) & `0A000821` (`(-57.0522, 30.3703, 0.696)`, `1.30 m` reach). **Hypothesis for earlier `moveto 0A000820` failure:** `0x820`/`0x821` lacked Persistent flag `0x400` (`bat r15p10` added `0x400`; run `bat r15p10` ONLY on a **throwaway save**). **Falling objects (`G11`):** carry/spawn real Starfield item `0000FBDB` (`Deskfan03`, via inventory or `bat r15drp`), stand at a **`5 m+`** outdoor drop (e.g. hilltop cliff edge or Concord ledge), press `I -> R`, and film at **`30+ fps`**: crisp **`1.00 g`** drop (`~1.01 s` for `5 m` vs `~1.64 s` at `0.38 g`). | **`VIDEO`:** (a) Hand-play `L10` armory walk -> `0A000820`/`0A000821` pickup (`v111-10mm-armory`); (b) **`5 m+`** timed drop of `0000FBDB` (`Deskfan03`) filmed at **`30+ fps`** outdoors (`1.00 g`, `~1.01 s`). |
| **7. Updated Concord Fight (`G11`, God Mode OFF)** | **`TEST-STATION`** | Raiders (`09000803..09000807`) engage & fire at the player (**god mode OFF**). **PASS:** standing idle drops **HP `>= 20` within `10 s` while staying alive at `10 s`**, and cover + shooting clears **`5/5` raiders cleanly to `stage 30` within `60` rounds**. **FAIL:** idle death in **`< 10 s`**, or running out of ammo. | **`VIDEO`:** Uninterrupted Concord fight (`god mode OFF`) showing `>= 20` idle HP loss in `10 s` (alive at `10 s`) + cover fight clearing `5/5` raiders to `stage 30` within `60` rounds (`concord-fight-10mm`). |
| **8. Structured Papyrus & SFSE Logs (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`) (`G3`)** | **`TEST-STATION`** | All three `[Papyrus]` keys (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`, set by Claude with `python scripts/bridge/make_bridge.py ini`, game closed) active; every row below verified against actual `.psc` / C++ format strings (`Workshop` attack/pop tables remain **not wired yet until H6**). | Preflight `< 10 s` log check + verified PASS log block. |
| **G13. Invisible Talk Proxy, Navmesh Snap, Weather & Jump Fallback** | **`TEST-STATION`** | Codsworth talk proxy `09000970` has `Model=null` (`codsworth talk proxy model=none visible=false`), camera centers/frames Codsworth (`StartDialogueCameraOrCenterOnTarget`); Preston (`z 89.086 -> 89.131`), Raiders (`88.093 -> 88.335`), and Codsworth (`111.734 -> 111.776`) snap to core navmesh (`hold <actor> ground_dz=<m>`); Preston faces player on talk (`preston face player angle_z=<deg>`); surface weather pins `NewAtlantisWeather50` (`0x0027CF9B`); vault suit fallback uses `Clothes_Miner_Jumpsuit` (`0x0001D1D7`). Safe Preston console approach: `bat g13p`. | Confirm invisible proxy box, grounded feet on steps/street, Preston facing player, clear hilltop weather. |

### Optional `P3`-Safe Diagnostic Console & Batches (`ZERO M/N/V` in Typed Console & Filenames)
```console
sqs 0A000800
getstage 09000800
bat r15p10
bat r15drp
bat g13p
```

```bat
; <starfield-dir>/r15p10.txt — THROWAWAY SAVE ONLY diagnostic moveto (0x820/0x821 carry Persistent 0x400; hand-play Leg L10 needs zero console!)
player.moveto 0A000820

; <starfield-dir>/r15drp.txt — add real Starfield item 0000FBDB (Deskfan03) for 5 m+ 30+ fps drop test outdoors (I -> R)
player.additem 0000FBDB 1

; <starfield-dir>/g13p.txt — G13 safe Preston talk standoff (-2013.14, -1695.54, 89.20) in front of Museum steps (avoids Museum wall)
player.setpos x -2013.14
player.setpos y -1695.54
player.setpos z 89.20
```

### Item 8 — Code-Verified Papyrus & SFSE Log Lines (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`)

> Set all three `[Papyrus]` keys (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`, set by Claude with `python scripts/bridge/make_bridge.py ini`, game closed). Every pattern below is regex-checked against `scripts/**/*.psc` and `sfse/**/src`.

| Wave Item | Log File | Exact Code-Verified Log Pattern (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`) | Trigger / When Logged |
|---|---|---|---|
| **0. 10 s Preflight** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger` | Non-empty within `10 s` of clicking New Game (else stop) |
| **1. Wrist Pip-Boy (Equip)** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> pipboy wrist equipped item=<form> worn=<bool> slot=<slot>` | Immediately on `0A00080F` pickup |
| **1. Wrist Pip-Boy (Re-equip)** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> pipboy wrist reequip on_load=<reason> acquired=<bool> worn=<bool>` | Save/load & surface arrival |
| **1. Wrist Raise (`Arm=1`)** | `FO4SFPipboyMenu.log` | `step=pipboy_raise mode=<idle\|arm> ms=<n> opened=<0\|1>` | Pressing `F7` with `Arm=1` default |
| **1. Screen Source Seam** | `FO4SFPipboyMenu.log` | `step=pipboy_screen_source mode=<2d_imenu\|3d_rtt>` | Startup config & Pip-Boy toggle |
| **1. Pickup Autosave** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> vault_death_recovery=autosave stage=<st> after=pipboy_pickup` | Autosave written right after `0A00080F` pickup |
| **2. Objective 10 Shown** | `fo4sf_mission.0.log` | `FO4SF_MISSION rt=<rt> codsworth01 objective10_toast shown=true muted_duplicates=<bool> force=<bool>` | First `FO4SF_Codsworth01` Objective 10 toast |
| **2. Objective 10 Muted** | `FO4SF_MISSION` (`fo4sf_mission.0.log`) | `FO4SF_MISSION rt=<rt> codsworth01 objective10_toast skipped=true reason=already_displayed muted_duplicates=<bool>` | Duplicate Objective 10 toast suppressed |
| **2. HUD `QUEST` Label (INI)** | `FO4SFPipboyMenu.log` | `step=hud_quest_label mode=<quest\|mission> label=<lbl> active=<0\|1> file=<present\|absent> file_ok=<0\|1>` | Startup INI + loose `Translate_en.txt` check |
| **2. HUD `QUEST` Label (Scaleform)** | `FO4SFPipboyMenu.log` | `step=hud_quest_label_runtime file=<present\|absent> file_ok=<0\|1> mission_status=<txt> mission_new=<txt> runtime_ok=<0\|1>` | Scaleform `BSScaleformManager::Translate` probe |
| **3. Silent Arrival Discovery** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> arrival discovery silent=<bool> method=<method> visible=<bool> can_travel=<bool> ref=<ref> world=<world> fast_before=<bool> fast_after=<bool>` | Hilltop surface discovery (zero Red Rocket / Vault 111 banner) |
| **3. Silent Starter Strip** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> inventory starter_strip silent=<bool> stripped=<n> left=<n>` | Vault starter armor silent removal (Story & Warfare) |
| **3. Landing Handoff (`single_quest`)** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> landing handoff mode=<mode> newgame_completed=<bool> codsworth01_displayed=<bool>` | Surface landing `single_quest` handoff |
| **3. Single-Pass Landing Fade** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> story_fade single_pass=true path=<immediate\|loading_close\|guard> loading_menu_open=<bool>` | Surface fade-in after `LoadingMenu` close / immediate |
| **3. `AddToMap(True)` Probe** | `FO4SFMarkerProbe.0.log` | `addtomap stage=80 name=TEST3 allowfasttravel=true` | `FO4SF_MarkerProbeQuest` stage `80` check (`FO4SFMARK rt=<rt> ... end=true`) |
| **4. Lift Menu Open / Confirm** | `FO4SFPipboyMenu.log` | `step=lift_open confirmed=<0\|1> descending=<0\|1>` | Opening paused `FO4SF_LiftMenu` |
| **4. Lift Ride Confirm** | `FO4SFPipboyMenu.log` | `step=lift_confirm action=<action> pool=<n> confirmed=<0\|1> values=<s>,<p>,<e>,<c>,<i>,<a>,<l>` | Confirming action (`pool=0` required for `ride`) |
| **4. Lift Ride Refused (`pool > 0`)** | `FO4SFPipboyMenu.log` | `step=lift_confirm refused reason=unspent_pool pool=<n>` | Blocking `ride` while unspent S.P.E.C.I.A.L. points remain |
| **4. Black Gap Closed** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> ascent gap_closed=true fade_in_at_surface=true` | Ascent black gap closed on arrival |
| **4b. Surface Cog Ready** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair surface_cog ready pair=<pair> ref=<ref> base=<base> pos=<x> <y> <z> rotz=<deg>` | Static `0x0A2D4B` cog resolved & ready |
| **4b. Cog Hatch / Lift State** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair surface_cog state=<A\|B> player_z=<z>` | Cog rising from State A -> B through opening hatches |
| **4b. Bidirectional Ride Start** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair ride start dir=<up\|down> accepted=<bool> ref=<ref> from_z=<z> stage=<n>` | Starting paired up or down ride |
| **4b. Bidirectional Transfer** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair transfer dir=<up\|down> z=<z> drop=<d> elapsed=<t>` | Interior/exterior cell transfer telemetry |
| **4b. Bidirectional Ride Arrived** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair ride arrived dir=<up\|down> z=<z> cell=<cell> world=<world>` | Arrival in destination cell after ride / rise |
| **4b. Arrived CustomEvent** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair event name=LiftPairArrived pair=<pair> dir=<up\|down> z=<z>` | `SendCustomEvent("LiftPairArrived")` emitted |
| **4b. Reload Recovery** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> lift_pair reload recovered dir=<up\|down> stage=<n> interior=<bool>` | Mid-ride reload recovery |
| **5. Pod Safe Exit + Stage 15** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> pod_exit mode=<safe_spawn\|cryopod_anim_hook> hook_stage=15 moved=<bool> pos=<x> <y> <z> heading=<deg>` | Stage-15 pod-exit hook on every route |
| **6. 10mm Pistol Auto-Equip** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> pistol picked item=<form> count=<n> equipped=<bool>` | Picking up `0A000820` (`0A000822`) in armory cage |
| **G13. Invisible Proxy** | `fo4sf_mission.0.log` | `FO4SF_MISSION rt=<rt> codsworth talk proxy model=none visible=false` | Codsworth invisible `0x970` proxy verification |
| **G13. Actor Ground Snap** | `fo4sf_mission.0.log` | `FO4SF_MISSION rt=<rt> hold <actor> ground_dz=<m>` | Held actor grounded within `0.2 m` of navmesh |
| **G13. Preston Facing** | `fo4sf_mission.0.log` | `FO4SF_MISSION rt=<rt> preston face player angle_z=<deg>` | Preston turns to face player on talk |
| **G13. Arrival Weather & Suit** | `fo4sf_newgame.0.log` | `FO4SF_NEWGAME rt=<rt> arrival weather id=<id> plugin=<plg> override=<bool> weather=<wthr>` | Clear Commonwealth arrival weather (`0x0027CF9B`) |

### Undo Command (Game Closed)
```bash
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required Core PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `FO4SFPipboyMenu.log`)
```log
step=shell_c4_config shell_backdrop=<0|1> shell_vitals_fill=<0|1> suppress_data_menu=<0|1> tab_opens_pipboy=<0|1> hide_starfield_watch=<0|1>
step=lift_open confirmed=<0|1> descending=<0|1>
step=lift_confirm action=<action> pool=<n> confirmed=<0|1> values=<s>,<p>,<e>,<c>,<i>,<a>,<l>
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=<worn>
FO4SF_NEWGAME rt=<rt> pipboy pickup examine_idle=<idle>
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt> equipped=<eq>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> complete stage=200
```

### `Later plug-in:` Attachment Map (Deferred Features Without Rebuilding Core)

| Wave Item / Seam | Current Playable-0.1 Behavior | `Later plug-in:` How Deferred Features Attach Without Rebuilding |
|---|---|---|
| **Item 1 — Wrist Pip-Boy (`0A00080D`, `0x823`, `0x824`, `0x867`, `0x868`)** | Separate housing (`0x823` bit `54`) & screen (`0x824` bit `55`), `FO4SF_Kw_Pipboy` keyword + 3-state `FO4SF_PipboyScreenSource` in `FO4SFCoreValues.esm`, `Arm=1` wrist raise + pickup autosave. | Custom 3D render-to-texture swaps screen `0x824` NIF/material & toggles `0x868`, while FO3/NV Pip-Boy ARMOs simply carry keyword `0x867` with zero DLL changes. |
| **Item 2 — Toasts & `QUEST` Label (`G9`, `G12(d)/(f)`)** | `landing_handoff=single_quest` default, `ShowObjectiveOnce` + VMAD `MuteDuplicateObjectiveToasts`, per-game `hud_label` table + 20-key loose `Translate_en.txt` (`source_ba2` pinned). | Future games (FO3/FNV) swap `hud_label`, `landing_handoff`, and `MuteDuplicateObjectiveToasts` in config with zero DLL/Papyrus rewrites. |
| **Item 3 — Silent Discovery, Strip & Fade (`G10`, `G9(e)`)** | `HoldDark=False` + `ReturnAnchor=0x000800`, silent `AddToMap(True)` (`SilentArrivalDiscovery`), shared `StripStarterItemsSilently`, single-pass fade-in (`LoadingMenu` landing hook). | Survival/per-game start rows set `arrival_discovery_method`, `silent_starter_strip`, and custom arrival vignettes without re-opening discovery or strip spam. |
| **Item 4 — Lift Flow & Unspent S.P.E.C.I.A.L. Lock (`G7`, `G8`, `G12(c)/(e)`)** | Unified `ShowPausedExitLiftMenu`, Ride blocked while unspent pool `> 0`, no loading screen during ride, top arrivals rise through opening hatches (`StateB_Play`). | Vault elevator audio/effects plug into `lift_pairs.json` fade/rise timings without touching chargen or `FinishSurface`. |
| **Item 4b — Direct-Override Surface Lift Cog (`G4`, `G7`, `G8`)** | Direct `ACTI 0x0A2D4B` override, paired interior+surface data from `lift_pairs.json` + `cog_pad_radius_m`, interior-down ride, `LiftPairArrived` CustomEvent. | FO3/FNV lift pairs & companion follow-through append rows in `lift_pairs.json` and subscribe to `LiftPairArrived`. |
| **Item 5 — Pod Safe Exit + Stage 15 (`G6`)** | `RunPodExitHook` sets `Stage 15` before `stage 20` on every start route (`pod_entry_step_m`, `moved=<bool>`, safe spawn on `OnDying`). | Cryopod animation hooks onto `PodExitMode="cryopod_anim"` at `hook_stage=15` without changing safe spawn math or fade logic. |
| **Item 6 — 10mm Pistol (`0A000822`) & Earth Gravity (`G11`)** | `Starfield stand-in (XM-2311 / .45) until H4` (`18 dmg`, `12-round` mag, `0x400` Persistent) + `1.00 g` timed drop (`0000FBDB`). | `#853` H4 replaces the weapon/ammo base cleanly via `game_start_config.json` without moving `0x820`/`0x821` or editing `NewGame` flow. |
| **Item 7 — Concord Fight (`G11`)** | Active raider fire (`>= 20` idle HP loss in `10 s`, alive at `10 s`; cover clears `5/5` within `60` rounds to `stage 30`). | `#853` P6b Pipe Guns and Museum interior wave (`L7`–`L9`) plug onto `0900097B`/`0900097A` and `Min00` `stage 30`. |
| **Item 8 — Logging (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`) (`G3`)** | All three `[Papyrus]` keys active, `10 s` `fo4sf_newgame.0.log` preflight, and CI source-regex verification over every card & PR log pattern. | Automated CI/PC log-judge parsers subscribe to these frozen source-verified log templates with zero script rewrites. |
| **Workshop Seam (`src/fo4sf/workshop/settlement_rules.json`)** | Data-driven `settlement_rules.json` validated by `WorkshopCore --settlement-rules` / `--self-test` (**not wired yet until H6**). | H6 (`2h-3`) wires Sanctuary bench properties (`0x005C50`) & radius from `settlement_rules.json` into `FO4SFWorkshop.esm`; W5/W6 rules stay appended as design rows. |
