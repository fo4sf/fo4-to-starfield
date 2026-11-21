# Candidate 2f — Track 1 Pool of 40 (`A1(b)`), Kept Fallout-Look Vault 111 `E` (`A1(c)`), Real Voiced `DialogueMenu` Talk (`A1(d)`), Border-Safe Concord Travel (`A1(e)`), Console-Free Walk (`A2`) & Full-Path Save/Reload (`A6`) Session Card (`Round 9` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`--profile player`, `13` Track-1 plugins; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`) & **Warfare** (`--profile test`, `22` plugins, Track 2 experimental core, still WITHOUT `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) | Track: **Track 1 playable path** (`Cards 2f-1..2f-3`) + optional **Track 2 test spot checks** (`Card 2f-4`).
> - **PASSED IN GAME (`21 Nov 09:03Z–09:14Z`, Candidate `2d-r7` `de2c3f8c`, `13`-plugin Story path):** Direct Vault 111 Story start (`FadeHold=false`, no white room, no first-box stall — `T3` sidestepped), single `"Character Appearance"` box (`Quick start` first), `stage 20` live status lines, `0A00080F.Activate 14` & `0A000819.Activate 14` batch activation (`pipboy pickup equipped flag=1 worn=true`, `cog door console activated before=3 after=2`, `stage 30 by=vault_console`), `28`-pt lift `FO4SF_NewGameSpecial` fallback (`Continue` -> ascent), **clean Commonwealth surface landing with zero arrival crash (`3/3` clean with `FO4SFRouteLoot.esm` OFF)** (`surface setposition ok=true`, `stage 40 by=Trigger`, `landed z=127.45 confirmed=True fallback=false`, `stage 200`, `mission gate mode=1 started=true`, `landing quests started min00=true keeper=true codsworth01=true`), outdoor `M`-key Pip-Boy MAP + `Tab` close (`MapBlockStarMap=0`), and Codsworth keeper `state=at spot, held`.
> - **`OFFLINE ONLY — UNPROVEN IN GAME` (Candidate `2e` + Candidate `2f` Round 9):** Every Round-8 and Round-9 change — **`V1`** Story exterior landing automatic fade-in, **`A1(b)`** Vault 111 lift **Pool of 40 (`33` points to spend)**, **`A1(c)`** kept Fallout-look first-person `E` on the Pip-Boy itself (`0A00080F`) and gear-door console itself (`0A000819` / `02001319`), **`V4`** post-console catwalk hint, **`A1(d)`** real voiced Starfield `DialogueMenu` scenes for Codsworth (`09000940`) and Preston (`09000900`) with `V2` message-box fallback, **`A1(e)`** `< 180 m`-per-axis Concord hops / persistent Museum ref `100009EC`, **`A2`** console-free walk (`docs/testing/console-free-walk-list.md`), and **`A6`** save/reload at surface, Sanctuary, Concord, mid-mission, and post-completion — is **`TEST-STATION` (OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs this card. Do not call any item fixed until it runs and passes in game.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## Runtime Load-Order Hex Table (`FO4SFBridge.esm` & `FO4SFRouteLoot.esm` OFF)

> **Runtime Slot Pin (`candidate-2f`):** When `Starfield.esm` (`00`), `BlueprintShips-Starfield.esm` (`01`), and `FO4Port.esm` (`02`) precede the bundle and both `FO4SFBridge.esm` and `FO4SFRouteLoot.esm` stay OFF, slots `03`–`0A` are identical in both the `13`-plugin `--profile player` bundle and the `22`-plugin `--profile test` bundle:

| Hex Slot (`<XX>`) | `13`-Plugin `--profile player` (Track 1 Default) | `22`-Plugin `--profile test` (Track 2 Experimental) | Key Runtime FormIDs (`<XX>000...`) |
|---|---|---|---|
| `03` | `FO4ActorRaider.esm` | `FO4ActorRaider.esm` | Raider bases (`03F04800`, `03F04801`) |
| `04` | `FO4TerrainCore.esm` | `FO4TerrainCore.esm` | `04005C50` Sanctuary workbench ref (`0x005C50`), `040A2ECD` workbench base, `040A7759` Red Rocket marker, `040A775A` Sanctuary marker, `040A775B` Vault 111 marker, **`040A775C` Concord marker** (`persistent 0x400`, `64.2 m` NW of Museum door) |
| `05` | `FO4TerrainCore_Mars.esm` | `FO4TerrainCore_Mars.esm` | Commonwealth Mars registration |
| `06` | `FO4SFCoreValues.esm` | `FO4SFCoreValues.esm` | `06000801` `Radiation Health Cap`, `06000860` `FO4SF_TestModeEnabled`, **`06000865` `FO4SF_PipboyAcquired`**, `06000870` `FO4SF_GameMode` (`1`=Story, `2`=Warfare), `06000890..06000897` `H00` switches |
| `07` | `FO4SFVaultGearDoor.esm` | `FO4SFVaultGearDoor.esm` | Vault 111 gear door rig |
| `08` | `FO4SFExitLift.esm` | `FO4SFExitLift.esm` | Vault 111 animated exit lift |
| `09` | `FO4SFMission.esm` | `FO4SFMission.esm` | **`09000800` `FO4SF_Min00`**, `09000801` `FO4_PrestonGarvey` (`NPC_`), **`09000802` `FO4SF_Min00_PrestonREF` (`ACHR`)**, `09000803..09000807` `5` Concord raiders, `09000810` `FO4_Codsworth` (`NPC_`), **`09000811` `FO4SF_CodsworthREF` (`ACHR`)**, `09000814` `FO4SF_CodsworthKeeper`, `09000815` `FO4SF_COMPreston`, **`09000816` `FO4SF_Codsworth01`**, **`09000817` `FO4SF_Sanctuary01`**, `09000819` `FO4SF_CodsworthVoice`, **`09000900` Preston talk `SCEN`**, **`09000940` Codsworth talk `SCEN`**, **`09000970` `FO4SF_CodsworthTalkActi`**, `09000971..09000978` `V2` fallback talk `MESG`s, **`09000979` `FO4SF_MissionTalkUseMessageBox`** (`GLOB`, default `0.0`) |
| `0A` | `FO4SFNewGame.esm` | `FO4SFNewGame.esm` | **`0A000800` `FO4SF_NewGame`**, `0A00080D` `FO4SF_PipboyWrist`, `0A00080E` `FO4SF_PipboyCorpsePickup`, **`0A00080F` `FO4SF_PipboyCorpsePickupRef`**, `0A000818` `FO4SF_GearDoorConsole`, **`0A000819` `FO4SF_GearDoorConsoleRef`**, `0A000820`/`0A000821` Vault 111 pistol + ammo |
| `0B..10` | `0B` `Workshop`, `0C` `PowerArmor`, `0D` `FortHagen`, `0E` `PipboyProbe`, `0F` `PipboyTravel`, **`10` `FO4SFMapMarkers.esm`** | `0B` `Rads`, `0C` `Hardcore`, `0D` `Workshop`, `0E` `PowerArmor`, `0F` `Progression` | Track 1 ends at `0F` + **`10` `FO4SFMapMarkers.esm`** (**`100009EC` `"Museum of Freedom"`** `persistent 0x400`, `4.6 m` from Museum door!) |
| `10..19` | *Omitted in `--profile player`* | **`10` `FO4SFListDialogue.esm` (`10000810`)**, `11` `Combat`, `12` `Reputation`, `13` `Companions`, `14` `ALife`, `15` `FortHagen`, `16` `CoreCandidate`, `17` `PipboyProbe`, `18` `PipboyTravel`, `19` `FO4SFMapMarkers.esm` (`190009EC`) | Card A quest is **`10000810`** in `22`-plugin `--profile test` |

### Console Batch & `P3` Zero-`M`/`N`/`V` Rules (`P2` / `P3`)

1. **Zero `M`, `N`, or `V` in interactive Console, and zero stripped mod `GLOB`/`QUST` EditorIDs:** Every ```` ```console ```` block below contains **zero `M`, `N`, or `V` letters** (case-insensitive). Every command that needs `M`, `N`, or `V` (`Activate`, `getglobalvalue`, `sqv`, `player.moveto`, `startquest`, `coc`) lives inside a `<starfield-dir>/<bat-id>.txt` batch file invoked as `bat <bat-id>` (whose `<bat-id>` also avoids `m`, `n`, and `v`).
2. **Confirm load indices cleanly (`0` `M`/`N`/`V`):**
   - `FO4SFCoreValues.esm` (`06`): `help "Health Cap" 4` -> `AVIF: (06000801) 'Radiation Health Cap'` (or check `step=core_value_resolve ... form=0x06000865` in `FO4SFPipboyMenu.log`).
   - `FO4SFMission.esm` (`09`): `help "Calls" 4 QUST` -> `QUST: (09000800) 'When Freedom Calls'`.
   - `FO4SFNewGame.esm` (`0A`): `help "Pip-Boy 3000" 4 ACTI` -> `ACTI: (0A00080E) 'Pip-Boy 3000'` and `help "Gear Door" 4` -> `ACTI: (0A000818)`.
   - `FO4SFListDialogue.esm` (`10`, test profile only): `help "List Dialogue" 4 QUST` -> `QUST: (10000810) 'FO4SF Silent-Player List Dialogue'`.

---

## Card 2f-1 — Swap from `2e` / `2d-r7` to Candidate `2f` (`13`-Plugin `--profile player`) & Exact Undo (`TOOLING` / `TEST-STATION`)

- **Starting Game State:** Prior Candidate `2e` (or `2d-r7`) `13`-plugin player bundle is installed with `sidecar-install` (`Data/FO4SFSidecar.install.json` present) and `FO4SFBridge.esm` held off. Run `sidecar-undo` and `plugin_toggle.py on` before uninstalling. Leave `candidate-2e` and all older candidate folders untouched.
- **Stage Placeholders:** `<cand2f-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`sfse_sidecar/reputation/` is reference-only and **not installed**; shipped `FO4SFPipboyMenu.ini` keeps `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`).
- **Track 1 `--profile player` Plugin List (`Plugins.txt`, `13` plugins WITHOUT `FO4SFRouteLoot.esm` and WITHOUT `FO4SFBridge.esm`, plus `*FO4SFMapMarkers.esm`):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2f-session-bridge-off
```

### Exact Undo Command (Game Closed — Clean Uninstall Back to Pre-Session State)
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
- CLI: `this bundle was built at `, `sidecar install refused:`, `plugins held off by plugin_toggle.py`, `FO4SFRouteLoot.esm` or `FO4SFBridge.esm` active in `Plugins.txt`, or `block_starmap=1` in startup `FO4SFPipboyMenu.log`.

---

## Card 2f-2 — `A1(b)` + `A1(c)` + `V4` + `V1`: Console-Free Vault 111 (`E` on Fallout Pip-Boy & Console -> Catwalk -> Pool-of-40 Lift -> Automatic Surface Fade-In) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2f-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2f-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).
- **Console-Free Goal (`A2`):** Complete Steps `1`–`4` below using **keyboard and mouse only** (zero `~` Console, zero `bat`). Record any `FAIL` (`R15`) before touching a diagnostic fallback.

### Install Command (Same Installed `13`-Plugin Bundle as Card 2f-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Step-by-Step In-Game Walkthrough (Keyboard + Mouse Only; Stop & Log Evidence on Any Break)

1. **Direct Vault 111 Story Start (`A2` Row 1 — Verified in `2d-r7` `21 Nov`):**
   - Click **Main Menu -> New Game** without touching `~` Console.
   - Expect direct Vault 111 cryo entry (`mode choice mode=story survival=0`, `stage 10 by=Trigger`), single **`"Character Appearance"`** box (`Quick start` first) `2.0 s` later -> pick **`Quick start`** (`looks done: Quick start`, `stage 20 by=Trigger`, `pod settle ok=true`, `pipboy activator registered`, `console activator registered`).
   - Pick up the Vault 111 pistol (`0A000820`) + `48` rounds (`0A000821`) -> `pistol picked`.
2. **Kept Fallout-Look First-Person `E` on Pip-Boy (`0A00080F`, `A1(c)` / `A2` Row 2 — `OFFLINE ONLY — UNPROVEN IN GAME`):**
   - Walk onto the raised Vault 111 control-room floor (`Z = 0.59 m`) beside the Vault-Tec scientist skeleton (`(-55.05, -0.92, 0.78)` m).
   - **Aim Hint (`A1(c)` — `Data/meshes/fo4sf/newgame/v111_pipboy_pickup.nif`, `XSCL = 1.0`, `0` Starfield tris, `WallTech08.nif` completely removed):** Verify **no Starfield/Deimos `WallTech08` scanner box** sits on top of the Pip-Boy. Aim directly at the **Fallout 4 Pip-Boy 3000 on the floor** (`42 × 26 × 20 cm` root `layer 1` `COL_STATIC` hull aligned `0.5 mm` above `02001616`, `Z_world = [0.6209, 0.8209] m`, `100.0%` standing & crouching offline raycast hit rate across `7,200/7,200` rays) until the HUD prompts **`Take Pip-Boy 3000`**, then press **`E`**.
   - **Expected:** `pipboy pickup equipped flag=1 worn=true`, `FO4SF_PipboyAcquired` (`06000865`) = `1`, and both `0A00080F` and the static floor Pip-Boy (`02001616`) disable cleanly.
   - **Diagnostic fallback ONLY if `A1(c)` Pip-Boy `E` fails (`R15` record `A1(c) Pip-Boy FAIL` first):** Run `bat u1pick` (`0A00080F.Activate 14`).
3. **Kept Fallout-Look First-Person `E` on Gear-Door Console (`0A000819` / `02001319`, `A1(c)` + `V4` / `A2` Row 3 — `OFFLINE ONLY — UNPROVEN IN GAME`):**
   - Turn south toward the angled Vault 111 gear-door console (`(-54.36, -1.81, 1.75)` m).
   - **Aim Hint (`A1(c)` — `Data/meshes/fo4sf/newgame/v111_geardoor_console.nif`, `XSCL = 1.0`, `0` Starfield tris, dual-ref `02001319` registration retained):** Verify **no Starfield/Deimos `WallTech08` scanner prop** protrudes from the console deck. Aim directly at the **Fallout 4 Vault Door Console button/lid/deck** (`110 × 47 × 16 cm` root `layer 1` `COL_STATIC` hull aligned `0.4 mm` proud of `02001319` and `+2.61 cm` proud of `Lid:2`, `100.0%` offline raycast hit rate across `1,960/1,960` rays) until **`Activate Vault Door Controls`** (`0A000819`) or **`Vault Door Controls`** (`02001319`) appears, then press **`E`**.
   - **Expected:** `cog door console activated ref=<ref> before=3 after=2` (preceded by `console port ref activated ref=<port_ref>` if the crosshair hit `02001319`), `stage 30 by=vault_console`, gear door opens visually, and **`V4`** displays **`Vault door open - follow the catwalk to the elevator platform.`** (`catwalk hint shown`).
   - **Diagnostic fallback ONLY if `A1(c)` console `E` fails (`R15` record `A1(c) Console FAIL` first):** Run `bat u1cog` (`0A000819.Activate 14`).
4. **Console-Free Catwalk -> Exit Lift -> Pool of 40 (`33` Points to Spend, `A1(b)`) -> Automatic Surface Fade-In (`V1` / `A2` Rows 4–5 — `OFFLINE ONLY — UNPROVEN IN GAME`):**
   - Walk through the open cog door down the catwalk into the center of the waiting open elevator cage (`RespecMoveMarker` `(-77.742, -3.958, -1.751)` m; `PlatformRadius = 2.0 m` covers the `4.0 m`-diameter interior of the `2.714 m`-radius `b_Platform` floor, zero `player.setpos` needed!) -> `lift platform waiting cage_door=open`.
   - Confirm **`Continue`** refuses once until **`S.P.E.C.I.A.L.`** is confirmed (`elevator continue refused: special unconfirmed`).
   - Open **`S.P.E.C.I.A.L.`** (`FO4SF_NewGameSpecial` fallback): confirm the prompt displays **Pool of 40 (`7` base `1`s + `33` points to spend)** (`A1(b)` — NOT `21` / `28`!). Spend all `33` points (total `40`), confirm (`special set ...`, `elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=True confirmed=true`), and pick **`Continue`** to ride up (`ascent carried confirmed`, `surface setposition ok=true`, `stage 40 by=Trigger`, `landed z=<z> confirmed=True fallback=false`, `stage 200 by=Trigger`).
   - **`V1` PASS Check (NO console fade batch!):** Wait `0–7 s` after `stage 200` on the Commonwealth hilltop. `ReleaseStoryLandingFade()` calls `ForceFadeIn("story_landing")` and arms bounded Timer `5` (`story fade reassert tick=1..3` at `+1.5/+4.0/+6.5 s`). Daylight Commonwealth view and HUD must appear automatically.
   - Confirm `F7` opens `FO4SF_Fo4Shell` immediately (`Arm=0`, `BootOnFirstOpen=0`) and outdoor `M` opens the Commonwealth MAP page (`MapBlockStarMap=0`) with `Tab` closing cleanly.

```console
help "Health Cap" 4
help "Pip-Boy 3000" 4 ACTI
help "Gear Door" 4
sqs 0A000800
bat u1pick
bat u1cog
```

```bat
; <starfield-dir>/u1pick.txt (DIAGNOSTIC FALLBACK ONLY if first-person E on 0A00080F fails; R15 record FAIL first)
0A00080F.Activate 14

; <starfield-dir>/u1cog.txt (DIAGNOSTIC FALLBACK ONLY if first-person E on 0A000819 fails; R15 record FAIL first)
0A000819.Activate 14
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`)
```log
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0
FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=none
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> looks done: <how>
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> pod settle ok=true pos=<x> <y> <z> dx=<dx> dy=<dy> drop=<drop> target=<tx> <ty> <tz> heading=<h> loaded=true cell=<cell> world=<world> sample_start=<t0> sample_end=<t1>
FO4SF_NEWGAME rt=<rt> pipboy activator registered ref=<ref> id=<id> pos=<x> <y> <z>
FO4SF_NEWGAME rt=<rt> console activator registered ref=<ref> id=<id> pos=<x> <y> <z>
FO4SF_NEWGAME rt=<rt> console port activator registered ref=<port_ref>
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt>
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<b0> after=<b1>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> catwalk hint shown
FO4SF_NEWGAME rt=<rt> elevator continue refused: special unconfirmed
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> readback=<r0> <r6>
FO4SF_NEWGAME rt=<rt> elevator attribute_allocation fallback=FO4SF_NewGameSpecial edited=<ed> confirmed=true
FO4SF_NEWGAME rt=<rt> ascent carried confirmed elapsed=<el> z=<z>
FO4SF_NEWGAME rt=<rt> surface setposition ok=true set=<n> pos=<x> <y> <z> target=<tx> <ty> <tz> core_cell=true cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> mission gate mode=1 started=true
FO4SF_NEWGAME rt=<rt> landing quests started min00=true keeper=true codsworth01=true
FO4SF_NEWGAME rt=<rt> fade in by=story_landing loaded=true cell=<cell>; saving and HUD on
FO4SF_NEWGAME rt=<rt> story fade reassert tick=1
FO4SF_NEWGAME rt=<rt> story fade reassert tick=2
FO4SF_NEWGAME rt=<rt> story fade reassert tick=3
```

### Negative / FAIL Conditions
- Lift `S.P.E.C.I.A.L.` offering `21` points (`28` total) instead of `33` points (`40` total) (`A1(b)`), Starfield `WallTech08` prop visible on Pip-Boy or console or dead first-person `E` (`A1(c)`), missing catwalk hint (`V4`), black screen or loading spinner persisting `> 10 s` after `stage 200` (`V1`), double appearance prompt, or exterior arrival crash (`T1`).

---

## Card 2f-3 — `A1(d)` + `A1(e)` + `A6`: Real Voiced Talk (`09000940` / `09000900`), Border-Safe Concord Travel (`< 180 m` Hops / Persistent `100009EC`) & Full-Path Save/Reload (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2f-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2f-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card 2f-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### `A6` Full-Path Save & Reload Matrix (Run At Every Step Below — Zero Reset, Zero Black Fade, Zero Double-Trigger)

| `A6` Checkpoint | Throwaway Save Name | Exact Game State Before Quit-to-Desktop & Reload | Expected Post-Reload Verification (On Screen & Logs) |
|---|---|---|---|
| **`A6-1` Surface** | `Throwaway_2f_Surface` | Outdoors on Vault 111 hilltop (`(-2467.78, -1406.92, 128.11)`) right after `V1` fades in (`0A000800` `stage 200`, `09000816` `stage 10`, `09000800` silent `stage 0`) | Same hilltop XYZ in daylight (zero stuck black fade/spinner); `F7` & `M` work; `0A000800=200`, `06000865=1`, `06000870=1`, `09000816=10`; logs `codsworth01 reload stage=10 choices=0`, `reload mission stage=0 relocate_fails=0`, `keeper load preston ...`, `keeper load codsworth ...`. |
| **`A6-2` Sanctuary** | `Throwaway_2f_Sanctuary` | Standing beside Codsworth (`09000811`) in Sanctuary Hills (`(-2346.71, -1406.16, 111.73)`) after talking to Codsworth (mid-talk at `stage 20` or right after `stage 100` -> `09000800` `stage 10`) | Codsworth remains held at spot (`off <= 25 m`) and re-talkable (`AllowPCDialogue(True)` + `09000970` proxy active); `09000816` preserves its exact stage & `choicesCount` (`codsworth01 reload stage=<st> choices=<cnt>`); `09000800` stays `stage 10` (`Find the Last Minutemen`, no duplicate `min00 given`). |
| **`A6-3` Concord** | `Throwaway_2f_Concord` | Outdoors in Concord within `<= 150 m` of Museum of Freedom door (`(-2011.14, -1697.54, 89.09)`) after `PlacePreston` has placed Preston (`state=at spot, held`) | Preston stays at Museum door (`off <= 25 m`, non-hostile); `reload mission stage=10 relocate_fails=0` (or `stage=20` if raiders already engaged); zero `BOUNDARY REACHED` popup. |
| **`A6-4` Mid-Mission** | `Throwaway_2f_MidWFC` | During *When Freedom Calls* (`09000800` `stage 20` with `1–4` raiders dead, OR `stage 30` with all `5` raiders dead before talking to Preston) | Exact `stage` (`20` or `30`) preserved; `reload mission stage=<20|30> relocate_fails=0`; dead raiders stay dead (WFC-01 checks living raiders on `stage 20` without advancing clock); at `stage 30`, Preston (`09000802`) stays `Talk Preston Garvey`, `prestonTalkBoxOpen` cleared, zero premature credit award. |
| **`A6-5` Post-Completion** | `Throwaway_2f_PostWFC` | After *When Freedom Calls* completes (`09000800` `stage 200`, `100` Credits awarded) and *First Settlement* (`09000817` `stage 10`) is active | `09000800` stays `stage 200` (no duplicate `100` Credits, no duplicate `sanctuary01` start); Preston stays held outside Museum door and re-talkable; `09000817` logs `sanctuary01 reload stage=10 complete=False` and re-binds Sanctuary workbench `04005C50` (`sanctuary01 bench_bound`). Delete all throwaway saves when finished. |

### Step 1 — Surface Reload (`A6-1`) -> Walk to Sanctuary Hills -> Talk to Codsworth (`09000940` Real Voiced `DialogueMenu`, `A1(d)` / `A2` Row 6)

1. Run **`A6-1` (`Throwaway_2f_Surface`)** save -> **`Quit to Desktop`** -> relaunch -> load on the Vault 111 hilltop.
2. Walk `~121 m` east downhill from the Vault 111 pad into **Sanctuary Hills** (`(-2346.71, -1406.16, 111.73)` m, zero console needed!).
   - Confirm Codsworth (`09000811`) is enabled, animated, non-hostile, and held at his Sanctuary spot (`state=at spot, held`), with `09000970` eye-level talk proxy ready (`codsworth talk proxy ready ref=<ref> z=<z>`).
3. Aim straight at Codsworth (`Talk Codsworth`) and press **`E`**:
   - **Primary Route (`A1(d)` — Real Voiced Starfield `DialogueMenu` `SCEN` `09000940`, default `FO4SF_MissionTalkUseMessageBox` `09000979 = 0`):** Uses Starfield `DEVT = true`, `Flags = 0x1814`, `SCPI = null`, full player lines in `Prompt` + `ResponseText`, and `8` sequential MQ102 `.wem` voice clips (`00f4c101..00f4c108` under `fo4sf_codsworthvoice/`, `09000819`). Opens Starfield's native `DialogueMenu` (`codsworth scene talk requested`, `codsworth talk scene started`, `codsworth dialogue menu opened`); choose through the conversation to the **Concord lead** (`codsworth01 stage 100 by=info` -> `codsworth talk scene ended stage=100 completed=True` -> `codsworth talk end -> min00 stage 10` -> **`Find the Last Minutemen`**).
   - **Fallback Route (`V2` `4`-Button `MESG` `09000971..09000974` — automatic `1.5 s` `R10` check OR `set 09000979 to 1` via `bat r9fb1`):** If real `SCEN` `09000940` fails to open `DialogueMenu` (`R15` record `A1(d) Codsworth SCEN FAIL` first!), `FO4SF_Codsworth01Quest` falls back automatically after `1.5 s` (or immediately when `09000979 == 1`), logging `codsworth talk fallback=messagebox reason=<reason>` -> `codsworth talk opened stage=10` -> button `3` -> `codsworth choice button=3` -> `codsworth talk end -> min00 stage 10`.
   - *(PR `#792` note: `#792` remains reference-only for Scaleform `DialogueMenu.swf` host/shuttle mechanics and provides no `QUST`/`SCEN`/`DIAL`/`INFO`/voice records; `A1(d)` lives natively inside `FO4SFMission.esm` in the `13`-plugin player bundle.)*
4. Run **`A6-2` (`Throwaway_2f_Sanctuary`)** save -> **`Quit to Desktop`** -> relaunch -> load.

### Step 2 — Border-Safe Travel to Concord (`A1(e)` / `A2` Row 7) -> `A6-3` & `A6-4` -> Talk to Preston (`09000900`, `A1(d)`) -> Complete *When Freedom Calls* & `A6-5`

1. **Primary Route (Console-Free Walk — `A2` Row 7):** Walk `~444 m` south-east from Sanctuary across the bridge, past **Red Rocket Truck Stop**, down the road into **Concord** toward the **Museum of Freedom** front entrance at **`(-2011.14, -1697.54, 89.09)`** m.
   - **Why `2e`'s `bat r8prs` was replaced (`A1(e)`):** `r8prs.txt` jumped directly to `(-2015, -1700, 89.5)` from Sanctuary (`dx = +335.6 m`, `dy = -291.4 m`) or Vault 111 (`dx = +452.8 m`, `dy = -293.1 m`). Per `docs/terrain/core64c.md` and `docs/terrain/border.md`, any `player.setpos` move `> 200 m` (`>= 3` cells) on a single axis risks Starfield's `BOUNDARY REACHED` relocation (`8–12 km` away).
   - **Safe Diagnostic Option A (`< 180 m` per-axis `setpos` hops — unconditionally border-safe, works even before `FO4SF_MapMarkers` settles):** Run **`bat r9hop1`** (if at Vault 111 -> Sanctuary `(-2347, -1406, 113.0)`, `dx=+120.8 m, dy=+0.9 m`), wait `3–5 s`, run **`bat r9hop2`** (Sanctuary -> Red Rocket open ground `zref_ground` `(-2185, -1561, 106.5)`, `dx=+161.7 m, dy=-154.8 m`), wait `3–5 s`, then run **`bat r9hop3`** (Red Rocket -> Concord Museum door `(-2015, -1700, 90.5)`, `dx=+170.0 m, dy=-139.0 m`, `4.6 m` from Preston's door spot). Every single leg stays strictly `< 180 m` (`<= 2` cells) on BOTH X and Y!
   - **Safe Diagnostic Option B (Verified Persistent `0x400` Ref Beside Museum Door):** `FO4SFMapMarkers.esm` carries persistent enabled ref **`100009EC`** (`FO4Core_CommonwealthMapMarkerM10985B`, `"Museum of Freedom"`, `flags=0x0400`, `Initially Disabled=False`, merged `(-2014.45, -1694.40, 89.89) m` — `4.6 m` from Preston's door spot; `040A775C` `"Concord"` in `FO4TerrainCore.esm` is `64.2 m` NW). Once `FO4SF_MapMarkers` has settled (`~10–35 s` after surface arrival in `fo4sf_map.0.log`), `100009EC` is already at its final merged Museum coordinates even while Preston (`09000802`) is still `"off, player away"`. For guaranteed `< 180 m`-per-axis border safety, run `bat r9hop2` (to Red Rocket) then **`bat r9door`** (`player.moveto 100009EC`, `dx=+170.6 m, dy=-133.4 m`).
2. Run **`A6-3` (`Throwaway_2f_Concord`)** save/reload upon entering Concord (`<= 150 m` of Museum door, Preston `state=at spot, held`).
3. Fight the `5` Concord street raiders (`09000803..09000807`, `stage 20`), run **`A6-4` (`Throwaway_2f_MidWFC`)** mid-mission save/reload (`stage 20` or `stage 30` after all `5` fall).
4. At `stage 30` (`Talk to Preston Garvey`), walk up to **Preston (`09000802`)** outside the Museum door and press **`E`**:
   - **Primary Route (`A1(d)` — Real Voiced Starfield `DialogueMenu` `SCEN` `09000900`, `7` Concord `.wem` clips `00f4c201..00f4c207` under `genericmaleeventoned/`):** Opens `DialogueMenu` (`preston talk scene triggered stage=30`, `preston scene talk requested`, `preston talk scene started stage=30`, `preston dialogue menu opened`) -> full Fallout 4 lines with voice -> `stage 35 by=info` -> `preston talk end info=0x092A -> stage 40` -> `reward credits=100` -> `preston talk scene ended stage=<35|40> end_info=True` -> `stage 200 by=Trigger` -> `complete stage=200` -> `FO4SF_Sanctuary01` (`09000817`) `stage 10`.
   - **Fallback Route (`V2` `4`-Button `MESG` `09000975..09000978` — automatic `1.5 s` Timer `3` check OR `bat r9fb1` `09000979 = 1`):** If `09000900` `SCEN` fails (`R15` record `A1(d) Preston SCEN FAIL` first!), falls back to `preston talk fallback=messagebox reason=<reason>` -> `preston talk opened stage=30` -> button `3` -> `preston choice button=3` -> `stage 35` -> `stage 40` -> `stage 200`.
5. Open Pip-Boy (**`F7`**) -> verify **`DATA`** (*When Freedom Calls* complete, *First Settlement* active) and **`INV`** (`100` Credits added), close with **`Tab`**.
6. Run **`A6-5` (`Throwaway_2f_PostWFC`)** save -> **`Quit to Desktop`** -> relaunch -> load, verify `09000800=200`, `09000817=10`, and optionally walk back to Sanctuary workbench (`04005C50` -> `min01 bench activated -> stage 100`). Delete all throwaway saves when done.

### `A1(e)` Border-Safe Console Diagnostics & Hop Helpers (`P3`-Safe: Zero `M`/`N`/`V` in Console!)

```console
help "Calls" 4 QUST
getstage 0A000800
getstage 09000816
getstage 09000800
getstage 09000817
sqs 09000800
sqs 09000816
sqs 09000817
bat r9stat
bat r9hop1
bat r9hop2
bat r9hop3
bat r9door
bat r9fb1
bat r9fb0
```

```bat
; <starfield-dir>/r9stat.txt — read-only globals & keeper state (slots: CoreValues=06, Mission=09, NewGame=0A)
getglobalvalue 06000865
getglobalvalue 06000870
sqv 09000814
sqv 09000800
sqv 09000816
sqv 09000817

; <starfield-dir>/r9hop1.txt — A1(e) Hop 1 (<180 m/axis from Vault 111 hilltop -> Sanctuary Codsworth; wait 3-5 s)
player.setpos x -2347
player.setpos y -1406
player.setpos z 113.0

; <starfield-dir>/r9hop2.txt — A1(e) Hop 2 (<180 m/axis from Sanctuary -> Red Rocket open ground zref_ground; wait 3-5 s)
player.setpos x -2185
player.setpos y -1561
player.setpos z 106.5

; <starfield-dir>/r9hop3.txt — A1(e) Hop 3 (<180 m/axis from Red Rocket -> Concord Museum door; wakes PlacePreston <= 300 m)
player.setpos x -2015
player.setpos y -1700
player.setpos z 90.5

; <starfield-dir>/r9door.txt — A1(e) Option B: persistent Museum of Freedom marker 100009EC (4.6 m from door; run after r9hop2 & map-marker settle)
player.moveto 100009EC

; <starfield-dir>/r9fb1.txt — A1(d) diagnostic switch: force V2 4-button MessageBox fallback if real DialogueMenu SCEN fails (R15 record FAIL first)
set 09000979 to 1

; <starfield-dir>/r9fb0.txt — A1(d) restore default real voiced DialogueMenu SCEN path
set 09000979 to 0
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log` — Route A `DialogueMenu` `SCEN` Primary + Route B `MessageBox` Fallback)
```log
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> codsworth01 init stage=10
FO4SF_MISSION rt=<rt> codsworth talk proxy ready ref=<ref> z=<z>
FO4SF_MISSION rt=<rt> codsworth01 talk ready codsworth=<ref> proxy=<proxy>
FO4SF_MISSION rt=<rt> <keeper-load-or-status> <codsworth-or-preston> d=<d> off=<off> state=<st> moves=<m> held=<h> holds=<hc> at <x> <y> <z> disabled=<dis> dead=<dead> fails=<f> player=<px> <py> <pz> interior=<int>
FO4SF_MISSION rt=<rt> codsworth01 reload stage=<st> choices=<cnt>
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=<rf>
FO4SF_MISSION rt=<rt> codsworth scene talk requested scene=<ref> via=<actor|proxy> stage=10
FO4SF_MISSION rt=<rt> codsworth talk scene started stage=10
FO4SF_MISSION rt=<rt> codsworth dialogue menu opened
FO4SF_MISSION rt=<rt> codsworth01 stage <20|30|40|100> by=info
FO4SF_MISSION rt=<rt> codsworth01 choice=<1|2|3> choices=<cnt>
FO4SF_MISSION rt=<rt> codsworth dialogue menu closed stage=<stage>
FO4SF_MISSION rt=<rt> codsworth talk scene ended stage=100 completed=True
FO4SF_MISSION rt=<rt> codsworth talk fallback=messagebox reason=<glob|scene_inactive|scene_incomplete|dialogue_menu_timeout|no_scene>
FO4SF_MISSION rt=<rt> codsworth talk opened stage=10
FO4SF_MISSION rt=<rt> codsworth choice button=3
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> stage 10 by=info
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> preston activated at stage 30
FO4SF_MISSION rt=<rt> preston talk scene triggered stage=30
FO4SF_MISSION rt=<rt> preston scene talk requested scene=<ref> stage=30
FO4SF_MISSION rt=<rt> preston talk scene started stage=30
FO4SF_MISSION rt=<rt> preston dialogue menu opened
FO4SF_MISSION rt=<rt> preston dialogue menu closed stage=<stage>
FO4SF_MISSION rt=<rt> preston talk scene ended stage=<35|40> end_info=True
FO4SF_MISSION rt=<rt> preston talk fallback=messagebox reason=<glob|scene_inactive|scene_incomplete|dialogue_menu_timeout|no_scene>
FO4SF_MISSION rt=<rt> preston talk opened stage=30
FO4SF_MISSION rt=<rt> preston choice button=3
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 start_requested ok=True
FO4SF_MISSION rt=<rt> complete stage=200
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 reload stage=<st> complete=<c>
```

### Negative / FAIL Conditions
- Any `A6-1..A6-5` save/reload crashing, resetting position/stage, restoring a black fade, or double-granting credits/quests; any `< 180 m` hop (`r9hop1..3`) raising `BOUNDARY REACHED`; pressing `E` on Codsworth (`09000811`) or Preston (`09000802`) opening nothing or showing `"No Dialogue Action on Player in First Phase"`; Preston never leaving `state=off, player away` inside `300 m` of `(-2011.14, -1697.54, 89.09)`; Preston turning hostile on stray hits (`WFC-03`); or raider counter stalling (`WFC-01`).

---

## Card 2f-4 — Optional Track 2 (`--profile test`, `22` Plugins Without `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) (`TEST-STATION`)

> **Track 2 Scope Note:** Run ONLY after Track 1 Cards 2f-1..2f-3 (or in a separate Track 2 session). `<cand2f-test-bundle>` stages `--fade-hold` Warfare setup (Pool of 40 everywhere per `A1(b)`), `FO4SFListDialogue.esm` (`10000810`), and Track 2 experimental slices while still keeping `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF.

- **Stage Placeholders:** `<cand2f-test-bundle>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Track 2 `--profile test` Plugin List (`Plugins.txt`, `22` plugins WITHOUT `FO4SFRouteLoot.esm`, `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (`<cand2f-test-bundle>`, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2f-test-bridge-off
```

### Track 2 Spot Checks (Warfare `T5` & Card A `10000810`)
1. **Warfare Fade-In (`T5`):** Start New Game under `--fade-hold` -> pick `Warfare` -> `Easy` -> `Minutemen` -> `Sanctuary Hills` -> `Survival: No` -> confirm `40`-pt `S.P.E.C.I.A.L.` (`33` points to spend) -> `Quick start` -> confirm `warfare move ok=True`, `stage 210 by=Trigger`, and `warfare fade reassert tick=2` lift the black fade automatically (`mission gate mode=2 started=false`).
2. **Card A (`10000810`):** Confirm `help "List Dialogue" 4 QUST` -> `10000810`, then run `bat carda0`, `bat carda1` (`stage 10`), `bat carda2` (`stage 15`), `bat carda3` (`stage 70`).

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

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `FO4SFListDialogue.0.log`)
```log
FO4SF_NEWGAME rt=<rt> warfare move ok=True marker=FO4Core_CommonwealthMapMarkerSanctuary dist=<d> z=<z>
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_NEWGAME rt=<rt> warfare fade reassert tick=2
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false
FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true
FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true
```

### Negative / FAIL Conditions
- Black screen / loading spinner lasting `> 10 s` after `stage 210` (`T5`), `"No Dialogue Action on Player in First Phase"` on `Relay Operator` (`T6`), or `FO4SFRouteLoot.esm` / `FO4SFBridge.esm` active.
