# Candidate 2e — Track 1 Story Fade-In, Vault 111 `E` Activation, First-Mission Path & Save/Reload Session Card (`Round 8` / `X1`–`X3` / `V1`–`V4` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & `21 Nov` Honesty Banner:** Candidate 2e (`--profile player`: **`13` Track-1 playable-path plugins** with safe defaults — `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`; `--profile test`: **`22` plugins** including Track 2 experimental core, still WITHOUT `FO4SFRouteLoot.esm`) requires a **NEW GAME**.
> - **PASSED IN GAME (`21 Nov 09:03Z–09:14Z`, Candidate `2d-r7` `de2c3f8c`, `13`-plugin Story path):** Direct Vault 111 Story start (no white room, no first-box stall — `T3` sidestepped), single `"Character Appearance"` box (`Quick start` first), `stage 20` live status lines, `0A00080F.Activate 14` & `0A000819.Activate 14` batch activation (`pipboy pickup equipped flag=1 worn=true`, `cog door console activated before=3 after=2`, `stage 30 by=vault_console`), `28`-pt lift `FO4SF_NewGameSpecial` fallback (`Continue` -> ascent), **clean Commonwealth surface landing with zero arrival crash (`3/3` clean with `FO4SFRouteLoot.esm` OFF)** (`surface setposition ok=true`, `stage 40 by=Trigger`, `landed z=127.45 confirmed=True fallback=false`, `stage 200`, `mission gate mode=1 started=true`, `landing quests started min00=true keeper=true codsworth01=true`), outdoor `M`-key Pip-Boy MAP + `Tab` close (`MapBlockStarMap=0`), and Codsworth keeper `state=at spot, held`.
> - **`OFFLINE ONLY — UNPROVEN IN GAME` (Candidate `2e` Round 8):** Every change in Round 8 — **`V1`** Story exterior landing automatic fade-in, **`V2`** Codsworth & Preston first-person `E`-talk in the `13`-plugin player bundle, **`V3`** first-person `E` collision/activation on Vault 111 Pip-Boy (`0A00080F`) and gear-door console (`0A000819`), **`V4`** post-console catwalk hint, **surface save/reload**, **Concord walk**, and ***When Freedom Calls*** completion — is **`TEST-STATION` (OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs this card. Do not call any `V1`–`V4` or `X2` item fixed until it runs and passes in game.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## Runtime Load-Order Hex Table (`21 Nov` Order — `FO4SFBridge.esm` & `FO4SFRouteLoot.esm` OFF)

> **Runtime Slot Pin (`21 Nov`):** When `Starfield.esm` (`00`), `BlueprintShips-Starfield.esm` (`01`), and `FO4Port.esm` (`02`) precede the bundle and both `FO4SFBridge.esm` and `FO4SFRouteLoot.esm` stay OFF, slots `03`–`0A` are identical in both the `13`-plugin `--profile player` bundle and the `22`-plugin `--profile test` bundle:

| Hex Slot (`<XX>`) | `13`-Plugin `--profile player` (Track 1 Default) | `22`-Plugin `--profile test` (Track 2 Experimental) | Key Runtime FormIDs (`<XX>000...`) |
|---|---|---|---|
| `03` | `FO4ActorRaider.esm` | `FO4ActorRaider.esm` | Raider bases (`03F04800`, `03F04801`) |
| `04` | `FO4TerrainCore.esm` | `FO4TerrainCore.esm` | `04005C50` Sanctuary workbench ref (`0x005C50`), `040A2ECD` workbench base |
| `05` | `FO4TerrainCore_Mars.esm` | `FO4TerrainCore_Mars.esm` | Commonwealth Mars registration |
| `06` | `FO4SFCoreValues.esm` | `FO4SFCoreValues.esm` | `06000801` `Radiation Health Cap`, `06000860` `FO4SF_TestModeEnabled`, **`06000865` `FO4SF_PipboyAcquired`**, `06000870` `FO4SF_GameMode` (`1`=Story, `2`=Warfare), `06000890..06000897` `H00` switches |
| `07` | `FO4SFVaultGearDoor.esm` | `FO4SFVaultGearDoor.esm` | Vault 111 gear door rig |
| `08` | `FO4SFExitLift.esm` | `FO4SFExitLift.esm` | Vault 111 animated exit lift |
| `09` | `FO4SFMission.esm` | `FO4SFMission.esm` | **`09000800` `FO4SF_Min00`**, `09000801` `FO4_PrestonGarvey` (`NPC_`), **`09000802` `FO4SF_Min00_PrestonREF` (`ACHR`)**, `09000803..09000807` `5` Concord raiders, `09000810` `FO4_Codsworth` (`NPC_`), **`09000811` `FO4SF_CodsworthREF` (`ACHR`)**, `09000814` `FO4SF_CodsworthKeeper`, `09000815` `FO4SF_COMPreston`, **`09000816` `FO4SF_Codsworth01`**, **`09000817` `FO4SF_Sanctuary01`**, **`09000970` `FO4SF_CodsworthTalkActi`**, `09000971..09000974` Codsworth `V2` talk `MESG`s, `09000975..09000978` Preston `V2` talk `MESG`s |
| `0A` | `FO4SFNewGame.esm` | `FO4SFNewGame.esm` | **`0A000800` `FO4SF_NewGame`**, `0A00080D` `FO4SF_PipboyWrist`, `0A00080E` `FO4SF_PipboyCorpsePickup`, **`0A00080F` `FO4SF_PipboyCorpsePickupRef`**, `0A000818` `FO4SF_GearDoorConsole`, **`0A000819` `FO4SF_GearDoorConsoleRef`**, `0A000820`/`0A000821` Vault 111 pistol + ammo |
| `0B..0F` | `0B` `Workshop`, `0C` `PowerArmor`, `0D` `FortHagen`, `0E` `PipboyProbe`, `0F` `PipboyTravel` (`10` `MapMarkers`) | `0B` `Rads`, `0C` `Hardcore`, `0D` `Workshop`, `0E` `PowerArmor`, `0F` `Progression` | Track 1 ends at `0F` (+ `10` `FO4SFMapMarkers.esm`) |
| `10..18` | *Omitted in `--profile player`* | **`10` `FO4SFListDialogue.esm` (`10000810`)**, `11` `Combat`, `12` `Reputation`, `13` `Companions`, `14` `ALife`, `15` `FortHagen`, `16` `CoreCandidate`, `17` `PipboyProbe`, `18` `PipboyTravel` | Card A quest is **`10000810`** in `22`-plugin `--profile test` |

### Console Batch & `P3` Zero-`M`/`N`/`V` Rules (`P2` / `P3`)

1. **Zero `M`, `N`, or `V` in interactive Console, and zero stripped mod `GLOB`/`QUST` EditorIDs:** Every ```` ```console ```` block below contains **zero `M`, `N`, or `V` letters** (case-insensitive). Every command that needs `M`, `N`, or `V` (`Activate`, `getglobalvalue`, `sqv`, `player.moveto`, `startquest`, `coc`) lives inside a `<starfield-dir>/<bat-id>.txt` batch file invoked as `bat <bat-id>` (whose `<bat-id>` also avoids `m`, `n`, and `v`).
2. **Confirm load indices cleanly (`0` `M`/`N`/`V`):**
   - `FO4SFCoreValues.esm` (`06`): `help "Health Cap" 4` -> `AVIF: (06000801) 'Radiation Health Cap'` (or check `step=core_value_resolve ... form=0x06000865` in `FO4SFPipboyMenu.log`).
   - `FO4SFMission.esm` (`09`): `help "Calls" 4 QUST` -> `QUST: (09000800) 'When Freedom Calls'`.
   - `FO4SFNewGame.esm` (`0A`): `help "Pip-Boy 3000" 4 ACTI` -> `ACTI: (0A00080E) 'Pip-Boy 3000'` and `help "Gear Door" 4` -> `ACTI: (0A000818)`.
   - `FO4SFListDialogue.esm` (`10`, test profile only): `help "List Dialogue" 4 QUST` -> `QUST: (10000810) 'FO4SF Silent-Player List Dialogue'`.

---

## Card 2e-1 — Swap from `2d-r7` to Candidate `2e` (`13`-Plugin `--profile player`) & Exact Undo (`TOOLING` / `TEST-STATION`)

- **Starting Game State:** Prior Candidate `2d-r7` (`13`-plugin player bundle) is installed with `sidecar-install` (`Data/FO4SFSidecar.install.json` present) and `FO4SFBridge.esm` held off. Run `sidecar-undo` and `plugin_toggle.py on` before uninstalling.
- **Stage Placeholders:** `<cand2e-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`sfse_sidecar/reputation/` is reference-only and **not installed**; shipped `FO4SFPipboyMenu.ini` keeps `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`).
- **Track 1 `--profile player` Plugin List (`Plugins.txt`, `13` plugins WITHOUT `FO4SFRouteLoot.esm` and WITHOUT `FO4SFBridge.esm`, plus `*FO4SFMapMarkers.esm`):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2e-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2e-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2e-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2e-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2e-session-bridge-off
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

## Card 2e-2 — `X1` (`V3` + `V4` + `V1`): Vault 111 First-Person `E` -> Catwalk Hint -> Lift -> Story Surface Fade-In (`TEST-STATION`)

- **Stage Placeholders:** `<cand2e-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2e-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2e-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card 2e-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2e-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2e-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2e-player-bundle> --starfield <starfield-dir>
```

### Step-by-Step In-Game Walkthrough (No Batch Required for Normal Play; Stop and Log Evidence if Any `V1`/`V3`/`V4` Item Fails)

1. **Direct Vault 111 Story Start (Verified in `2d-r7` `21 Nov`):**
   - Click **Main Menu -> New Game** without touching `~` Console.
   - Expect direct Vault 111 cryo entry (`mode choice mode=story survival=0`, `stage 10 by=Trigger`), single **`"Character Appearance"`** box (`Quick start` first) `2.0 s` later -> pick **`Quick start`** (`looks done: Quick start`, `stage 20 by=Trigger`, `pod settle ok=true`, `pipboy activator registered`, `console activator registered`).
   - Pick up the Vault 111 pistol (`0A000820`) + `48` rounds (`0A000821`) -> `pistol picked`.
2. **First-Person `E` on Pip-Boy (`0A00080F`, `V3` — `OFFLINE ONLY — UNPROVEN IN GAME`):**
   - **Aim Hint (`V3`, `Starfield.esm:0x143492` single-convex `COL_STATIC` template, `XSCL = 1.25`):** Walk onto the raised Vault 111 control-room floor (`Z = 0.59 m`) beside the Vault-Tec scientist skeleton in front of the gear-door console; look down just right/west of the skeleton's outstretched left arm at the compact tech module resting directly on top of the floor Pip-Boy (`(-55.05, -0.92, 0.78..0.97) m`, `~38 × 35 × 20 cm` hitbox, strictly above the static floor mesh `02001616`'s `Z_max = 0.7722 m`, standing or crouched) until the HUD prompts **`Take Pip-Boy 3000`**, then press **`E`** (owner-friendly first-person play — **do NOT run `bat u1pick` unless first-person `E` still fails!**).
   - **Expected:** `pipboy pickup equipped flag=1 worn=true`, `FO4SF_PipboyAcquired` (`06000865`) = `1`, and both `0A00080F` and the static floor Pip-Boy (`02001616`) disable cleanly.
   - **Diagnostic fallback ONLY if `V3` fails (`R15` record `V3 Pip-Boy FAIL` first):** Run `bat u1pick` (`0A00080F.Activate 14` in `<starfield-dir>/u1pick.txt`) so the rest of the card can still be tested.
3. **First-Person `E` on Gear-Door Console (`0A000819` or `02001319`, `V3` + `V4` — `OFFLINE ONLY — UNPROVEN IN GAME`):**
   - **Aim Hint (`V3`, dual-ref registration):** Turn south toward the angled Vault 111 gear-door console (`(-54.36, -1.81, 1.75) m`, chest height facing the cog door); aim at the center control module / red-button deck (**`Activate Vault Door Controls`** on `0A000819`, `+8.5 cm` proud of the `45°` deck) **or anywhere across the `1.08 m`-wide console housing** (**`Vault Door Controls`** on `FO4Port.esm` `02001319`), and press **`E`**.
   - **Expected:** `cog door console activated ref=<ref> before=3 after=2` (preceded by `console port ref activated ref=<port_ref>` if the crosshair hit `02001319`), `stage 30 by=vault_console`, gear door opens visually, and **`V4`** displays the HUD notification **`Vault door open - follow the catwalk to the elevator platform.`** (`catwalk hint shown`) guiding the player along the catwalk to `(-77.7, -3.9, -1.2)`.
   - **Diagnostic fallback ONLY if `V3` console `E` fails (`R15` record `V3 Console FAIL` first):** Run `bat u1cog` (`0A000819.Activate 14`).
4. **Catwalk -> Exit Lift -> `S.P.E.C.I.A.L.` -> Story Surface Automatic Fade-In (`V1` — `OFFLINE ONLY — UNPROVEN IN GAME`):**
   - Walk across the open cog door along the catwalk onto the exit lift platform (`lift platform waiting cage_door=open`).
   - Confirm **`Continue`** refuses once until **`S.P.E.C.I.A.L.`** (`28`-pt `FO4SF_NewGameSpecial` fallback) is confirmed -> pick **`Continue`** to ride up (`ascent carried confirmed`, `surface setposition ok=true`, `stage 40 by=Trigger`, `landed z=<z> confirmed=True fallback=false`, `stage 200 by=Trigger`).
   - **`V1` PASS Check (NO console fade batch!):** Wait `0–7 s` after `stage 200` on the Commonwealth hilltop. `ReleaseStoryLandingFade()` waits for exterior streaming (`Is3DLoaded()` + `0.5 s` settle), calls `ForceFadeIn("story_landing")` (bypassing Vault 111's earlier `faded = true` latch), and arms bounded Timer `5` (`story fade reassert tick=1..3` at `+1.5 s`, `+4.0 s`, `+6.5 s`, stopping immediately if indoors). The black screen and loading spinner must **lift automatically** with full daylight Commonwealth view and HUD active.
   - Confirm `F7` opens `FO4SF_Fo4Shell` instantly (`Arm=0`, `BootOnFirstOpen=0`) and outdoor `M` opens the Commonwealth MAP page (`MapBlockStarMap=0`) with `Tab` closing cleanly.

```console
help "Health Cap" 4
help "Pip-Boy 3000" 4 ACTI
help "Gear Door" 4
sqs 0A000800
bat u1pick
bat u1cog
```

```bat
; <starfield-dir>/u1pick.txt (DIAGNOSTIC FALLBACK ONLY if first-person E on 0A00080F fails; R15 record V3 FAIL first)
0A00080F.Activate 14

; <starfield-dir>/u1cog.txt (DIAGNOSTIC FALLBACK ONLY if first-person E on 0A000819 fails; R15 record V3 FAIL first)
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
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt> equipped=<equipped> base=<base>
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
- Black screen or loading spinner persisting `> 10 s` after `stage 200` (`V1`), missing first-person `E` prompt or dead `E` on `0A00080F` or `0A000819` (`V3`), missing catwalk hint (`V4`), double appearance prompt, or exterior arrival crash (`T1`).

---

## Card 2e-3 — `X2` (`V2` + Surface Save/Reload + First Mission Path As The Player Meets It) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2e-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Card 2e-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card 2e-1 (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card 2e-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2e-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2e-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2e-player-bundle> --starfield <starfield-dir>
```

### Step 0 — Surface Save & Reload (`V5` / `X2` — Directly After Card 2e-2 Hilltop Landing)

1. Standing outdoors on the Vault 111 hilltop after `V1` fades in (`stage 200`), open the pause menu and create manual throwaway save **`Throwaway_2e_Surface`**.
2. Choose **`Quit to Desktop`** (full process exit), relaunch Starfield via SFSE, and **Load `Throwaway_2e_Surface`**.
3. **What Claude should see on screen after reload:**
   - Player loads standing outdoors on the Vault 111 hilltop (same XYZ, daylight visible, zero stuck black fade or spinner, zero crash).
   - Pressing **`F7`** opens `FO4SF_Fo4Shell` immediately; pressing **`M`** opens the Commonwealth MAP page cleanly and **`Tab`** closes it.
   - `FO4SF_NewGame` (`0A000800`) stays at `stage 200`, `FO4SF_PipboyAcquired` (`06000865`) reads `1`, `FO4SF_GameMode` (`06000870`) reads `1`, `FO4SF_Codsworth01` (`09000816`) is running at `stage 10`, `FO4SF_Min00` (`09000800`) is running silently (waiting for Codsworth or Concord), and `FO4SF_CodsworthKeeper` (`09000814`) logs `keeper load preston ...` and `keeper load codsworth ...`.

### Step 1 — Walk Down to Sanctuary Hills & Talk to Codsworth (`09000811` / `09000970`, `V2` — `OFFLINE ONLY — UNPROVEN IN GAME`)

1. Follow the trail downhill from the Vault 111 pad into **Sanctuary Hills** toward Codsworth's merged spot **`(-2346.709, -1406.163, 111.734)`** m (`CodsworthLocal (-1146.709, 1293.837, 111.734)` + merge offset `(-1200.0, -2700.0, 0.0)`).
   - **What Claude should see on screen:** Codsworth (`09000811`, hovering robot outside the pre-war home) is enabled, animated, non-hostile, and held at his Sanctuary spot (`keeper status codsworth ... state=at spot, held`). `FO4SF_Codsworth01Quest` spawns an invisible eye-level `360°` sphere talk activator (`09000970` `FO4SF_CodsworthTalkActi`, `Scale 1.6`, centered on Codsworth's chrome body at `z + 1.36 m`, `+0.265 m` clear above `MiniBotARace`'s floor capsule) and logs `codsworth talk proxy ready ref=<ref> z=<z>` + `codsworth01 talk ready codsworth=<ref> proxy=<ref>`.
   - **How the `13`-plugin PLAYER bundle runs Story talk without `FO4SFListDialogue.esm`:** Neither `FO4SFListDialogue.esm` (Track-2 test-cell skill-check plugin) nor unmerged draft `#792` is in `--profile player`. In `V2`, `FO4SFMission.esm` (`09`) handles both Codsworth and Preston directly via `OnActivate` + `4`-button Fallout-4 `MessageBox` records (`09000971..09000974` `FO4SF_Codsworth01_TalkMsg`..`Reply2Msg` and `09000975..09000978` `FO4SF_Min00_PrestonTalkMsg`..`Reply2Msg`) with `EnsureActorTalkable` (`AllowPCDialogue(True)` + `BlockActivation(False, False)`) re-asserted after `SetRestrained(True)`.
   - **Why Preston reads `state=off, player away` here:** Preston's merged Museum of Freedom door spot is **`(-2011.14, -1697.54, 89.09)`** m — roughly **`444 m` south-east of Sanctuary Hills** (`~544 m` from Vault 111), outside `PlaceRadius = 300.0 m`. He is NOT disabled (`disabled=False`); he stays `off, player away` until the player walks outdoors south past Red Rocket into Concord within `300.0 m` (2D XY) of `(-2011.14, -1697.54)`.
2. Walk up to **Codsworth (`09000811`)**, aim straight at his hovering chrome body (HUD prompt **`Talk Codsworth`**), and press **`E`**:
   - **What Claude should see on screen (`V2`):** The `4`-button `FO4SF_Codsworth01_TalkMsg` (`09000971`) choice box opens immediately (`codsworth talk opened stage=10`):
     - Button `0` (date / what happened) -> `codsworth choice button=0` (`stage 20`), shows `FO4SF_Codsworth01_Reply0Msg` (`09000972`) and returns to the choice box.
     - Button `1` (Sanctuary / family) -> `codsworth choice button=1` (`stage 30`), shows `FO4SF_Codsworth01_Reply1Msg` (`09000973`) and returns.
     - Button `2` (nearby survivors) -> `codsworth choice button=2` (`stage 40`), shows `FO4SF_Codsworth01_Reply2Msg` (`09000974`) and returns.
     - Button `3` (**Concord lead** — finish conversation) -> `codsworth choice button=3` (`stage 100`) -> `codsworth talk end -> min00 stage 10` -> `min00 given by=codsworth` -> `stage 10 by=info` -> `codsworth01 complete choices=<cnt> concord_pointed=true`.
   - **What Claude should see on screen after button `3`:** *When Freedom Calls* (`09000800`) becomes active in the HUD and Pip-Boy `DATA` quest tab with Objective `10` (**`Find the Last Minutemen`**) pointing south-east toward Concord.

### Step 2 — Walk South Past Red Rocket into Concord (`FO4SF_Min00` `09000800`, Stages `10` -> `20` -> `30`)

1. Walk south-east across the Sanctuary bridge, past **Red Rocket**, down the road into **Concord** toward the **Museum of Freedom** front entrance at merged **`(-2011.14, -1697.54, 89.09)`** m (`PrestonLocal (-811.14, 1002.46, 89.09)` + merge offset `(-1200.0, -2700.0, 0.0)`):
   - **What turns Preston (`09000801` base `NPC_`, `09000802` placed `ACHR`) on:**
     - **Within `800.0 m` (`RelocateRadius`):** `FO4SF_Min00` `Relocate` moves the `5` Concord street raiders (`09000803..09000807`, base `FO4_LvlRaider` `03F04800`) into the merged Commonwealth.
     - **Within `300.0 m` (`PlaceRadius`, 2D XY of `(-2011.14, -1697.54)`):** `PlacePreston` (called every `1.0 s` by `FO4SF_Min00` and every `5.0 s` by `FO4SF_CodsworthKeeper` `09000814`) moves `09000802` to `(-2011.14, -1697.54, 89.09)` (`moved Preston to ... failed=False`, `state=placed, held` -> `at spot, held`) and calls `EnsureActorTalkable` immediately after `SetRestrained(True)`.
     - **Within `150.0 m` (`GiveConcordRadius`):** If Codsworth was skipped, `FO4SF_Min00` auto-reveals Objective `10` (`min00 given by=concord`, `stage 10 by=Trigger`).
     - **Within `60.0 m` (`EngageRadius`) of any living raider OR within `20.0 m` (`FindRadius`) of / pressing `E` on Preston:** The street fight starts (`found preston near d=<d>` / `found preston activated` or `startcombat raider <i> d=<d>`), advancing `FO4SF_Min00` to **`stage 20`**.
2. **Stage-by-Stage `FO4SF_Min00` (`09000800`) Reference Table (What Runs, What Logs, What Claude Sees):**

| `FO4SF_Min00` Stage | Trigger / Player Action | What Claude Sees on Screen | Key `fo4sf_mission.0.log` Lines |
|---|---|---|---|
| **Silent Start (`0`)** | Vault 111 surface landing (`0A000800` `stage 200`) | Quest running silently; no Concord objective yet until Codsworth or `<= 150 m` of Museum | `mission gate mode=1 started=true`, `init raiders=5` |
| **`10`** | Finish Codsworth (`09000816` `stage 100`) OR walk `<= 150 m` of Museum door | Active HUD objective **`Find the Last Minutemen`** (marker on Preston `09000802` outside Museum) | `min00 given by=codsworth` (or `by=concord`), `stage 10 by=info` (or `by=Trigger`) |
| **`20`** | Enter `<= 60 m` of a Concord raider (`09000803..09000807`), attack/kill one, or reach `<= 20 m` of / press `E` on Preston | Objective `10` completes; HUD updates to **`Kill the Raiders`** (`Objective 85`); `5` street raiders engage player; Preston is Ally (`IgnoreFriendlyHits=True`) and stays non-hostile | `found preston <how>` (if Preston reached first), `startcombat raider <i> d=<d>`, `stage 20 by=Trigger`, `status stage=20 dead=<d>/5 ...` (WFC-01 rescues/clears any subterranean or stuck raider after `60 s`) |
| **`30`** | All `5` Concord street raiders killed or WFC-01 cleared (`dead == 5`) | Objective `85` completes; HUD updates to **`Talk to Preston Garvey`** (`Objective 86`, marker on Preston `09000802`); Preston exits combat (`StopCombat`) and holds at the museum door (`Talk Preston Garvey`) | `stage 30 by=Trigger` |
| **`35`** | Press **`E`** on Preston (`09000802`) and finish `FO4SF_Min00_PrestonTalkMsg` (`09000975`, buttons `0..2` show `Reply0..2Msg` and loop; button `3` finishes) | `4`-button Preston choice box opens immediately (proximity fallback paused while open; zero `"No Dialogue Action on Player in First Phase"`) | `preston activated at stage 30`, `preston talk opened stage=30`, `preston choice button=<0..3>`, `stage 35 by=info`, `preston talk end info=0x092A -> stage 40` |
| **`40`** | Immediate transition from `35` on button `3` | Objective `86` completes; **`100` Credits** added to player inventory | `stage 40 by=info`, `reward credits=100` |
| **`200`** | Immediate `1.0 s` timer tick after `stage 40` | *When Freedom Calls* completes (Pip-Boy `DATA` quest tab marks complete); **`First Settlement`** (`FO4SF_Sanctuary01` `09000817`) starts automatically with Objective `10` pointing back to Sanctuary workbench (`04005C50`) | `stage 200 by=Trigger`, `sanctuary01 start_requested ok=True`, `complete stage=200`, `sanctuary01 init stage=10 bench_ref=0x005C50` |

> **Scope Honesty (`NOT BUILT` in cut-down `FO4SF_Min00`):** Interior Museum of Freedom raiders, rooftop Power Armor/minigun, Wave-2 sewer Deathclaw, and Preston's group marching to Sanctuary (`B11`) are `NOT BUILT` in this slice; Preston remains held outside the Museum front door after `stage 200` (and can be re-talked to at `stage >= 200`).

### Step 3 — Talk to Preston (`09000802`, `V2`), Complete *When Freedom Calls*, Check Pip-Boy `DATA` & Post-Completion Save/Reload

1. After all `5` street raiders fall (`stage 30`), approach **Preston Garvey (`09000802`)** outside the Museum front door (`Talk Preston Garvey`) and press **`E`**.
   - **What Claude should see on screen (`V2`):** The `4`-button `FO4SF_Min00_PrestonTalkMsg` (`09000975`) box opens immediately (`preston talk opened stage=30`). Buttons `0..2` display `FO4SF_Min00_PrestonReply0Msg`..`Reply2Msg` (`09000976..09000978`) and return; button `3` finishes the talk (`preston choice button=3` -> `stage 35 by=info` -> `preston talk end info=0x092A -> stage 40`).
   - **`100` Credits** are awarded (`reward credits=100`), **`complete stage=200`** fires, and **`FO4SF_Sanctuary01` (`09000817`)** starts (`sanctuary01 start_requested ok=True`, `sanctuary01 init stage=10 bench_ref=0x005C50`).
2. Open the Pip-Boy (**`F7`**) -> check **`DATA`** quests tab (*When Freedom Calls* completed, *First Settlement* active) and **`INV`** (`100` Credits added), then close with **`Tab`**.
3. Save to throwaway save **`Throwaway_2e_PostWFC`**, **`Quit to Desktop`**, relaunch, and load **`Throwaway_2e_PostWFC`**: verify `09000800` remains at `stage 200`, Preston stays held outside the Museum door (`off <= 25.0`), and optionally walk back to Sanctuary Hills to activate the workbench (`04005C50` -> `min01 bench activated -> stage 100`). Delete both throwaway saves when done.

### `21 Nov` Console Diagnostics & Teleport Helpers (`P3`-Safe: Zero `M`/`N`/`V` in Console!)

Use interactive `console` commands below ONLY for read-only stage/index checks or calling the pre-written `.txt` batch files in `<starfield-dir>` if a step needs teleporting/diagnostics. *(Important: when teleporting to Concord while Preston is still `state=off, player away`, ALWAYS use `bat r8prs` (`player.setpos x -2015`, `y -1700`, `z 89.5`) — **never** `player.moveto 09000802` before `PlacePreston` has moved him into the merged world!)*

```console
help "Calls" 4 QUST
getstage 0A000800
getstage 09000816
getstage 09000800
getstage 09000817
sqs 09000800
sqs 09000816
sqs 09000817
bat r8stat
bat r8csw
bat r8prs
```

```bat
; <starfield-dir>/r8stat.txt — read-only globals & keeper state (21 Nov slots: CoreValues=06, Mission=09, NewGame=0A)
getglobalvalue 06000865
getglobalvalue 06000870
sqv 09000814
sqv 09000800
sqv 09000816

; <starfield-dir>/r8csw.txt — diagnostic teleport beside Codsworth in Sanctuary (09000811)
player.moveto 09000811

; <starfield-dir>/r8prs.txt — diagnostic teleport to Concord Museum door (wakes PlacePreston <= 300 m; do NOT moveto 09000802 while off)
player.setpos x -2015
player.setpos y -1700
player.setpos z 89.5
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
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> codsworth01 init stage=10
FO4SF_MISSION rt=<rt> codsworth talk proxy ready ref=<ref> z=<z>
FO4SF_MISSION rt=<rt> codsworth01 talk ready codsworth=<ref> proxy=<proxy>
FO4SF_MISSION rt=<rt> <keeper-load-or-status> <codsworth-or-preston> d=<d> off=<off> state=<st> moves=<m> held=<h> holds=<hc> at <x> <y> <z> disabled=<dis> dead=<dead> fails=<f> player=<px> <py> <pz> interior=<int>
FO4SF_MISSION rt=<rt> codsworth01 reload stage=<st> choices=<cnt>
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=<rf>
FO4SF_MISSION rt=<rt> codsworth talk opened stage=10
FO4SF_MISSION rt=<rt> codsworth choice button=3
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> stage 10 by=info
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> preston activated at stage 30
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
```

### Negative / FAIL Conditions
- Surface save/reload crashing, resetting position/stage, or restoring a black fade; pressing `E` on Codsworth (`09000811`) or Preston (`09000802`) opening nothing or showing `"No Dialogue Action on Player in First Phase"` (`V2`); Preston never leaving `state=off, player away` inside `300 m` of `(-2011.14, -1697.54, 89.09)`; Preston turning hostile on stray hits (`WFC-03`); or raider counter stalling (`WFC-01`).

---

## Card 2e-4 — Optional Track 2 (`--profile test`, `22` Plugins Without `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) (`TEST-STATION`)

> **Track 2 Scope Note:** Run ONLY after Track 1 Cards 2e-1..2e-3 (or in a separate Track 2 session). `<cand2e-test-bundle>` stages `--fade-hold` Warfare setup, `FO4SFListDialogue.esm` (`10000810`), and Track 2 experimental slices while still keeping `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF.

- **Stage Placeholders:** `<cand2e-test-bundle>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Track 2 `--profile test` Plugin List (`Plugins.txt`, `22` plugins WITHOUT `FO4SFRouteLoot.esm`, `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (`<cand2e-test-bundle>`, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2e-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2e-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2e-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2e-test-bridge-off
```

### Track 2 Spot Checks (Warfare `T5` & Card A `10000810`)
1. **Warfare Fade-In (`T5`):** Start New Game under `--fade-hold` -> pick `Warfare` -> `Easy` -> `Minutemen` -> `Sanctuary Hills` -> `Survival: No` -> confirm `40`-pt `S.P.E.C.I.A.L.` -> `Quick start` -> confirm `warfare move ok=True`, `stage 210 by=Trigger`, and `warfare fade reassert tick=2` lift the black fade automatically (`mission gate mode=2 started=false`).
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
