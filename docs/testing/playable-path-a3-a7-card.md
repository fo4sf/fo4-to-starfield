# Playable Path Post-2f Session Card (`A3` Places, `A4` Next Story Missions, `A5` Pip-Boy Quests/MAP/INV/Arm, `A7` *Unlikely Valentine* & *Getting a Clue* — `Round 9` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Titles: **Fallout 4** | Modes: **Story** (`--profile player`, `13` Track-1 plugins; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`) | Track: **Track 1 playable path** (post-`candidate-2f` expansion cards).
> - **`OFFLINE ONLY — UNPROVEN IN GAME` (`R15` / `R8` Stand-In Truth Labels):** Every slice covered by this card — **`A3`** staged interior two-way doors (`ConcordMuseum01`, `SanctuaryBasementJahani`, `RedRocket01`, `ConcordCivicAccess01`, `ConcordFactory`, `ConcordSpeakeasy`), **`A4`** next three Story missions (*Sanctuary* `09000817`, *The First Step* `09000A20`, *Jewel of the Commonwealth* `09000A50`), **`A5`** Pip-Boy live `DATA / Quests` (`0x800..0xBFF`), `MAP` current-objective markers (`FO4SFPipboyQuestObjectives.tsv`), `INV` readiness (`--a5-playable`), and non-blocking `Arm=1` watchdog, and **`A7`** *Unlikely Valentine* (`MQ104` `09000A80`) & *Getting a Clue* (`MQ105` `09000AB0`) — is **`TEST-STATION` (OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs these cards.
> - **`R8` Stand-In Disclosure:** The **Sanctuary build menu (`09000A15`)** is a **stand-in** (a messagebox counter updating resource `GLOB`s `09000A02..09000A0D`, strictly opt-in / NEVER popped over the workshop on bench activation per `R2`; the real version requires full `FO4SFWorkshop.esm` physical build-object counting and settlement resource graphs). Non-`DEVT` NPC talks (`Sturges`, `Spokesman`, `Piper`/`Mayor`, `Ellie`, `Nick`, `Malone`, `Geneva`) currently use messagebox **stand-ins** with `360°` talk proxies / timed proximity fallbacks (`R4`); the real version requires voiced Starfield `DEVT` `SCEN` dialogue like Codsworth. Every `A4`/`A7` placed actor starts **`InitiallyDisabled` (`0x800`, `R3`)** and enables only when its owning mission reaches the stage that needs it.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## Runtime Load-Order Hex Table (`13`-Plugin `--profile player` + `FO4Port.esm` `interiors_b10`)

| Hex Slot (`<XX>`) | Plugin | Key Post-`2f` Runtime FormIDs (`A3` / `A4` / `A5` / `A7`) |
|---|---|---|
| `02` | `FO4Port.esm` (+ `FO4PortTextures2.esm` for `interiors_b10` textures) | **`02012540`** `ConcordMuseum01`, **`02011918`** `SanctuaryBasementJahani`, **`02002338`** `RedRocket01`, **`020119AF`** `ConcordCivicAccess01`, **`0201202C`** `ConcordFactory`, **`02012245`** `ConcordSpeakeasy`, **`0201535A`** `CorvegaAssemblyPlant01`, **`02006B30`** `DmndValentines01`, **`02002593`** `Vault114`, **`020109FA`** `Vault11402`, **`0206B72C`** `DmndStandsKellogg01`, **`0200BA4B`** `FortHagen01`, **`0200CFC6`** `FortHagen02` |
| `04` | `FO4TerrainCore.esm` | `04004B2B`/`04005054`/`0400677F` Museum exterior doors, `04005119` roof Minigun `ACTI`, `0401EC87` Vertibird, `04008913` roof PA spot, `04005C50` Sanctuary workbench, `0401CF77` Root Cellar hatch, `0400D271` Red Rocket workbench, `0400DCC6`/`0400D9B7` Red Rocket garage button/door, `0401A793` Tenpines Bluff workbench, `04013E79` Diamond City `DmndGateREF` |
| `06` | `FO4SFCoreValues.esm` | `06000860` `FO4SF_TestModeEnabled`, `06000865` `FO4SF_PipboyAcquired`, `06000870` `FO4SF_GameMode` (`1`=Story, `2`=Warfare) |
| `09` | `FO4SFMission.esm` | **`09000800`** `FO4SF_Min00`, **`09000816`** `FO4SF_Codsworth01`, **`09000817`** `FO4SF_Sanctuary01` (*Sanctuary* expanded in place: Sturges `09000A01`, `Min01` `GLOB`s `09000A02..09000A0D`, workbench build menu `09000A15`), **`09000A20`** `FO4SF_MinRecruit00` (*The First Step*: Tenpines spokesman `09000A22`, hostile armed raider boss `FO4_CorvegaBoss` `09000A23` / ref `09000A24`, Flare Gun `09000A25`), **`09000A50`** `FO4SF_MQ103` (*Jewel of the Commonwealth*: Piper `09000A52`, Mayor `09000A54`, post-gate Ellie `09000A56`, gate `GLOB` `09000A57`, persistent `FO4SF_MQ103_GateProxyActi` `09000A59`), **`09000A80`** `FO4SF_MQ104` (*Unlikely Valentine*: Nick `09000A82`, Malone `09000A84`, Darla `09000A86`, `09000A89` `MQ105` arm), **`09000AB0`** `FO4SF_MQ105` (*Getting a Clue*: Geneva `09000AB2`, Dogmeat `09000AB4`, cigar `09000AB5`, `09000AB8` `MQ106` arm) |
| `0B..0F` | `0B` `Workshop`, `0C` `PowerArmor` (`0C000801`/`0C000809`), `0D` `FortHagen`, `0E` `PipboyProbe`, `0F` `PipboyTravel` | `FO4SFPipboyMenu.dll` + `FO4SFPipboyQuestObjectives.tsv` (`A5`), `FO4SFFortHagen.esm` (`0D` roof door `0x0547B0` & marker `0x0A774C`) |

### `P3` Zero-`M`/`N`/`V` Console Rule
Every ```` ```console ```` block below contains **zero `M`, `N`, or `V` letters** (case-insensitive) and **zero stripped mod `GLOB`/`QUST` EditorIDs**. All `coc`, `Activate`, `set`, `sqv`, and `moveto` calls live inside `P3`-safe `<starfield-dir>/<bat-id>.txt` batch files.

---

## Card A3 — First-Missions Places on the Path (`ConcordMuseum01`, Sanctuary Root Cellar, Red Rocket & Concord Route) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<interiors-b10-port>`, `<cand-core-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.4 GB` for staged `interiors_b10` (`FO4Port.esm` + `FO4PortTextures2.esm` BA2s, zero reconversion) plus `~4.2 GB` for the `13`-plugin Track-1 player bundle under `<starfield-dir>/Data`.
- **Plugin List (`Plugins.txt`):** `FO4Port.esm`, `FO4PortTextures2.esm`, plus the `13` Track-1 player plugins (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).

### Offline Audit & Install Commands (Game Closed)
```bash
python scripts/terrain/a3_path_places.py audit-stage --port <interiors-b10-port> --core <cand-core-dir>
python scripts/terrain/a3_path_places.py plan --groups a3_all --out <scratch-dir>/a3_doors_plan.json
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand-a3-bridge-off
```

### Place-by-Place Verification Rows (`docs/quests/first-missions-places.md`)
1. **Museum of Freedom (`ConcordMuseum01` `02012540` — 3 two-way doors, locks/terminals/generator, roof set-piece & Deathclaw):**
   - **Front door (`04004B2B` <-> `0201303B`):** Walk up to exterior front doors at `(-2011.14, -1697.54, 89.09)` m, press **`E`** -> land inside lobby `(8.06, 0.00, -0.91)` m -> press **`E`** on `0201303B` to return cleanly outside.
   - **Interior locks, terminals & Fusion Core generator:** Inspect `PrestonDoorREF` (`02013047`, lock `255`), `PrestonExitDoor` (`02013046`, lock `255`), basement security gate (`02013042`, Novice lock `25`) + `ConcordMuseumBasementTerminal` (`020125AB`, Novice `25`), `MQ102SturgesTerminal` (`02013040`, Novice `25`), and `PowerGenerator01` (`02012585`, Fusion Core `0C000809` swap point).
   - **Balcony (`04005054` <-> `02013045`, interior lock `255`) & Roof (`0400677F` <-> `02013048`):** Exit roof door onto `(-1990.58, -1724.18, 97.56)` m; confirm crashed `Vertibird03` (`0401EC87`), `MQ102MinigunREF` (`04005119`), roof `T-45` Power Armor spot (`04008913` / `(-1995.73, -1723.10, 97.54)` m), and Concord sewer Deathclaw emergence pit (`(-2068.22, -1640.18, 88.22)` m).
2. **Sanctuary Hills & Root Cellar (`SanctuaryBasementJahani` `02011918`):**
   - Verify Sanctuary houses are open exterior shells (no interior load doors) around workbench `04005C50`; press **`E`** on rear cellar hatch (`0401CF77`) -> land at `(-2.97, 3.10, 0.00)` m inside `02011918` (inspect Advanced safe `0201195B`, lock `50`) -> exit via ladder (`020119AE`) back to `(-2288.80, -1364.04, 110.82)` m.
3. **Red Rocket Truck Stop & Mole Rat Den (`RedRocket01` `02002338`):**
   - Verify exterior workbench (`0400D271`), `XLKR`-wired garage button (`0400DCC6` -> `0400D9B7`), and Mole Rat Den cell load (`bat a3rr` until companion `autoload_activator` door plugin installs; verify Novice safe `020024D7` and cave Fusion Core spot).
4. **Concord Route (`Civic Access` `020119AF`, `Workhouse` `0201202C`, `Speakeasy` `02012245`, `Church` open shell):**
   - Test one two-way door round trip per cell (`040072A9` south pipe -> `02012024` + chained door `02012027`/`02012028`; `0402AD42` Workhouse east -> `02012241` + safe `020120DD`; `04013FCE` Speakeasy east -> `02012537` + locked door `0201228D`/safe `02012342`) and walk through Concord Church open stairs (`(-2017.14, -1726.79, 88.55)` m).

```console
bat a3sf
bat a3rr
```

```bat
; <starfield-dir>/a3sf.txt (diagnostic cell check ONLY when testing staged FO4Port.esm without wired doors)
coc FO4Port_ConcordMuseum01

; <starfield-dir>/a3rr.txt
coc FO4Port_RedRocket01
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`Papyrus.0.log` / `fo4sf.0.log`)
```log
FO4SF_LoadDoor requested <plugin>:<id>
FO4SF_LoadDoor MoveTo returned
```

### Negative / FAIL Conditions
- `FO4SF_LoadDoor refused:`, `FO4SF_LoadDoor load door arrival failed n=3`, missing magenta textures (indicates `FO4PortTextures2.esm` archive load failure), or falling through interior/exterior floor on door exit.

---

## Card A4 — Next Story Missions in Order (*Sanctuary* `09000817`, *The First Step* `09000A20`, *Jewel of the Commonwealth* `09000A50`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed `13`-plugin player bundle once `A4` builds into `FO4SFMission.esm`).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins (`FO4SFMission.esm` at slot `09`, `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).
- **Mission Gate Rule (`SANC-05`):** All three quests run ONLY in Story mode (`FO4SF_GameMode == 1`) and stop silently in Warfare mode (`mission gate mode=2 started=false quest=<sanctuary01|minrecruit00|mq103>`).

### Offline Reachability & Install Commands (Game Closed)
```bash
python scripts/terrain/a3_path_places.py audit-a4
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Console-Free Walkthrough + Mid-Mission Save/Reload (`A6`) + `W6` 4-Axis Break-It Checks

1. **Mission 1 — *Sanctuary* / *First Settlement* (`FO4SF_Sanctuary01` `09000817`, `R1`/`R2`/`R3`/`R8`):**
   - Starts automatically on `FO4SF_Min00` `stage 200` as the **sole active HUD mission** (`R1` — `FO4SF_MQ103` does NOT start at `Min00` `stage 200` or steal `SetActive(True)`!).
   - **`R2` Real Workshop First (NO Messagebox Over Workshop):** Activating the Sanctuary workbench (`04005C50`) opens Starfield's real workshop cleanly with **zero modal messagebox** over the workshop (`complete=true` is logged ONLY when `CompleteQuest()` has truly finished the quest). **Sturges (`09000A01`)** starts `InitiallyDisabled` (`R3`) and enables only when the quest reaches its Sturges stage.
   - **Stand-In Workbench Build Menu (`09000A15` `FO4SF_Sanctuary01_WorkbenchBuildMsg` — `R8` Stand-In, Opt-In Only):** Strictly opt-in (via explicit test global / Sturges fallback, NEVER on bench `OnActivate`) to exercise `5` Beds (`09000A02`), `5` Water (`09000A05`), `5` Food (`09000A08`), and `2` Defense (`09000A0B`) milestones (`1000->1050->...->1500`). Real version requires physical `FO4SFWorkshop.esm` object placement counting.
   - **Mid-Mission Save/Reload (`SANC-04`):** Save to **`Throwaway_A4_Sanctuary`** at `stage 1200`, **`Quit to Desktop`**, relaunch, load -> verify `sanctuary01 reload stage=1200 complete=False`, workbench `04005C50` re-binds, and resource counts persist.
   - **Completion (`stage 1500`):** `sanctuary01 finished stage=1500 by=<cause>` -> `sanctuary01 handoff minrecruit00=started`.
2. **Mission 2 — *The First Step* (`FO4SF_MinRecruit00` `09000A20`, `R3`/`R4`/`R5`):**
   - Starts sequentially behind *Sanctuary* completion (or out-of-order proximity on `KeeperOnly` Timer 2 within `150 m` of Tenpines Bluff `(-1517.0, -1423.63, 87.71)` m; Tenpines spokesman `09000A22` & Corvega boss `09000A24` start `InitiallyDisabled` `0x800` until enabled by the quest stage).
   - Talk to Tenpines spokesman (`09000A22` via `360°` proxy / timed proximity fallback `R4`, or activate Tenpines workbench `0401A793` in Open Mode if dead) -> clear hostile armed raider boss `FO4_CorvegaBoss` (`09000A23` / ref `09000A24` inside `FO4Port_CorvegaAssemblyPlant01` `0201535A`, `stage 100 -> 200`) -> return to Tenpines (`stage 200 -> 450`) -> report to Preston (`09000802`) -> `minrecruit00 complete stage=500 flare_gun=true min02_unlocked=1 by=<cause>` (`FO4SF_FlareGun` `09000A25` awarded).
   - **Mid-Mission Save/Reload (`STEP-03`):** Save/reload **`Throwaway_A4_FirstStep`** at `stage 100` (Corvega) -> verify `minrecruit00 reload stage=100 complete=False` and boss state intact.
3. **Mission 3 — *Jewel of the Commonwealth* (`FO4SF_MQ103` `09000A50`, `R1`/`R3`/`R4`/`R5`):**
   - **Deliberate One-Tracked-Opening Choice (`R1`):** In Fallout 4, `MQ103` starts when `MQ102` ends while `Min01` (*Sanctuary*) is still running; here we make a deliberate one-tracked-opening-mission design choice: **`FO4SF_MQ103` (`09000A50`) waits until `FO4SF_Sanctuary01` (`09000817`) completes; after that it can also start at the Diamond City gate** `(-1416.36, -3129.39, 19.20)` m (`<= 150 m`, without stealing `SetActive(True)` from an active opening objective; early starts stay dormant via `WakeFromPredecessor()` without burning `RunOnce`). Piper (`09000A52`), Mayor (`09000A54`), and Ellie (`09000A56`) start `InitiallyDisabled` (`0x800`, `R3`) until enabled by `FO4SF_MQ103`, with dedicated per-NPC `360°` talk proxies (`09000A5A`/`09000A5B`/`09000A5C`, `R4`).
   - Speak with Piper (`09000A52`) / Mayor (`09000A54`) outside `DmndGateREF` (`04013E79`, `STAT` cleared via `DisableNoWait` on unlock, with `R4` proxy/timed fallback), OR in Open Mode if both are dead press **`E`** on persistent **`FO4SF_MQ103_GateProxyActi` (`09000A59`)** (`mq103 gate proxy spawned`, or let `OnTimer(1)` auto-unlock -> `mq103 open_mode gate_npcs_dead -> unlocking gate` -> `mq103 gate unlocked by=<cause>`, `09000A57=1`) -> enter past the opened gate to **Ellie Perkins (`09000A56`, placed post-gate on the Valentine's Agency side at `(-1392.0, -3102.0, 19.3)` m, `mq103 ellie placed post_gate`, beside `FO4Port_DmndValentines01` `02006B30`)** -> speak with Ellie (or activate the proxy dossier in Open Mode if dead) -> `mq103 complete stage=100 mq104_armed=1 by=<cause>` (`09000A58=1`).
   - **Mid-Mission Save/Reload (`JOTC-04`):** Save/reload **`Throwaway_A4_DiamondCity`** at `stage 20` -> verify `mq103 reload stage=20 complete=False` and gate stays unlocked.

```console
sqs 09000817
sqs 09000A20
sqs 09000A50
bat a4s1
bat a4s2
bat a4s3
bat a4s4
bat a4r1
bat a4r2
bat a4r3
bat a4r4
bat a4q1
bat a4q2
bat a4q3
bat a4q4
```

```bat
; <starfield-dir>/a4s1.txt — W6 Sanctuary giver-dead (Open Mode)
09000A01.kill
04005C50.Activate 14

; <starfield-dir>/a4s2.txt — W6 Sanctuary out-of-order pre-built resources
set 09000A02 to 5
set 09000A05 to 5
set 09000A08 to 5
set 09000A0B to 2

; <starfield-dir>/a4s3.txt — W6 Sanctuary save/reload check
sqs 09000817

; <starfield-dir>/a4s4.txt — W6 Sanctuary fast-travel-away check
sqs 09000817

; <starfield-dir>/a4r1.txt — W6 First Step giver-dead (Open Mode)
09000A22.kill
0401A793.Activate 14

; <starfield-dir>/a4r2.txt — W6 First Step out-of-order Corvega pre-clear
09000A24.kill
setstage 09000A20 100

; <starfield-dir>/a4r3.txt — W6 First Step save/reload check
sqs 09000A20

; <starfield-dir>/a4r4.txt — W6 First Step fast-travel-away check
sqs 09000A20

; <starfield-dir>/a4q1.txt — W6 Jewel of the Commonwealth giver-dead (Open Mode; STAT gate 04013E79 opens via OnTimer / FO4SF_MQ103_GateProxyActi 09000A59)
09000A52.kill
09000A54.kill
sqs 09000A50

; <starfield-dir>/a4q2.txt — W6 Jewel of the Commonwealth out-of-order direct Ellie
09000A56.Activate 14

; <starfield-dir>/a4q3.txt — W6 Jewel of the Commonwealth save/reload check
sqs 09000A50

; <starfield-dir>/a4q4.txt — W6 Jewel of the Commonwealth fast-travel-away check
sqs 09000A50
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
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 min01_mode full_min01=True
FO4SF_MISSION rt=<rt> sanctuary01 bench build menu opened stage=<st>
FO4SF_MISSION rt=<rt> sanctuary01 bench build item=bed count=<n>
FO4SF_MISSION rt=<rt> sanctuary01 bench build item=water count=<n>
FO4SF_MISSION rt=<rt> sanctuary01 bench build item=food count=<n>
FO4SF_MISSION rt=<rt> sanctuary01 bench build item=defense count=<n>
FO4SF_MISSION rt=<rt> sanctuary01 finished stage=1500 by=<cause>
FO4SF_MISSION rt=<rt> sanctuary01 handoff minrecruit00=started
FO4SF_MISSION rt=<rt> sanctuary01 reload stage=<st> complete=<bool>
FO4SF_MISSION rt=<rt> minrecruit00 init stage=50 tenpines_bench=0x01A793
FO4SF_MISSION rt=<rt> minrecruit00 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> minrecruit00 corvega pre_cleared -> stage 200
FO4SF_MISSION rt=<rt> minrecruit00 complete stage=500 flare_gun=true min02_unlocked=1 by=<cause>
FO4SF_MISSION rt=<rt> minrecruit00 reload stage=<st> complete=<bool>
FO4SF_MISSION rt=<rt> mq103 started by=proximity
FO4SF_MISSION rt=<rt> mq103 init stage=10 gate_ref=0x013E79
FO4SF_MISSION rt=<rt> mq103 gate unlocked by=<cause>
FO4SF_MISSION rt=<rt> mq103 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq103 complete stage=100 mq104_armed=1 by=<cause>
FO4SF_MISSION rt=<rt> mq103 reload stage=<st> complete=<bool>
```

### Negative / FAIL Conditions
- Any `A4` quest firing in Warfare mode (`FO4SF_GameMode == 2`), workbench `04005C50` failing to open `09000A15` build menu, `DmndGateREF` (`04013E79`) soft-locking when Piper/Mayor die (`JOTC-01`), or save/reload resetting resource counters or stages.

---

## Card A5 — Pip-Boy Live Quests, MAP Objective Markers, INV Readiness & Non-Blocking `Arm` (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<pipboy-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini`, `FO4SFPipboyQuestObjectives.tsv`) on top of the installed `~4.2 GB` `13`-plugin player bundle.
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins (`FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).
- **Safe Default Preservation (`W1` / `T7`):** Shipped defaults stay `InvDataAnswers=0`, `Arm=0`, `MapBlockStarMap=0`, `BootOnFirstOpen=0`; opt in with `--a5-playable` (sets `PopulateInCall=1`, `StatActions=1`, `InvDataAnswers=1` and writes `FO4SFPipboyQuestObjectives.tsv` while keeping `Arm=0` & `MapBlockStarMap=0`) and test non-blocking arm raise separately with `--arm 1`.

### Stage & Install Commands (Game Closed)
```bash
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --a5-playable
python scripts/ui/pipboy_mission_catalog.py --out <pipboy-stage-dir>/SFSE/Plugins/FO4SFPipboyQuestObjectives.tsv
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### In-Game Pip-Boy Verification Steps (Keyboard + Mouse Only)
1. **Startup Catalog Load:** Launch via SFSE and verify `FO4SFPipboyMenu.log` logs `step=quest_catalog file=FO4SFPipboyQuestObjectives.tsv status=<loaded|defaults> ...`.
2. **`DATA / Quests` Live Objectives (`0x800..0xAFF`):** After reaching the Commonwealth hilltop (`FO4SF_Codsworth01` `09000816` active, then *When Freedom Calls* `09000800` with binary-matched default objective IDs `10, 85, 86` & `A4` quests active), press **`F7`** -> switch to **`DATA -> QUESTS`**. Verify only player-facing missions appear (silent helper quests like `FO4SF_CodsworthKeeper` are filtered out), active objectives (`state == 1`) display on top, and selecting a quest logs `step=quest_select form=<hex> objectives=<o>`.
3. **`MAP` Current Objective Marker & `ShowQuestOnMap`:** Switch to **`MAP`** (or trigger **`Show on Map`** from `DATA -> QUESTS`) -> verify the current objective marker (`markerId=0xF00000+i`, `isQuestTarget=true`) draws at the objective's Commonwealth coordinates (`step=map_quest_markers`) and `ShowQuestOnMap` centers on it (`step=map_center idx=<idx> quest=<hex> called=1`).
4. **`INV` Page Readiness (`13`-Plugin Bundle):** Switch to **`INV`** -> verify Vault 111 pistol (`WEAP`), Vault suit/Pip-Boy (`ARMO`), Stimpaks (`ALCH`), ammo (`AMMO`), and misc items populate cleanly (`step=inv_fill`) and **`Tab`** closes cleanly.
5. **Optional Non-Blocking `Arm=1` Check (Separate INI Switch `--a5-playable --arm 1`):** Press **`F7`** once -> wait for arm raise OR double-tap **`F7`** to confirm immediate wait skip (`step=arm_raise_skip_wait`); open-cycle fencing (`g_armPendingOpenN`) ensures a canceled/closed cycle never late-opens the shell, and if the idle ever stalls, confirm the `R10` hard watchdog (`ArmRaiseMs + ArmRetryMs + 500 ms`) force-opens `FO4SF_Fo4Shell` (`step=arm_watchdog_open`) so the Pip-Boy is NEVER blocked.

```console
help "Health Cap" 4
sqs 09000800
sqs 09000816
sqs 09000817
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=quest_catalog file=FO4SFPipboyQuestObjectives.tsv status=<loaded|defaults> rows=<rows> tsv_rows=<tsv>
step=quests_collect n=<n> active=<a> completed=<c> objectives=<o> quest_markers=<qm>
step=quests_fill when=<when> tab=<tab> n=<n> active=<a> completed=<c>
step=quest_select form=<hex> objectives=<o>
step=map_quest_markers n=<k> first_quest=<hex> obj=<num> x=<x> y=<y>
step=map_center idx=<idx> quest=<hex> called=1
step=inv_fill when=<when> tab=<tab> filter=<hex> n=<n> total_count=<cnt>
step=arm_raise_skip_wait n=<n> t_ms=<ms>
step=arm_watchdog_open n=<n> elapsed_ms=<ms>
```

### Negative / FAIL Conditions
- Silent helper quests (`FO4SF_CodsworthKeeper`, `FO4SF_COMPreston`) leaking into `DATA / Quests`, missing objective marker on `MAP`, `INV` crash on `13`-plugin player items, or `Arm=1` stalling `FO4SF_Fo4Shell` open past the watchdog limit.

---

## Card A7 — Next Two Story Missions & Places: *Unlikely Valentine* (`MQ104` `09000A80`) & *Getting a Clue* (`MQ105` `09000AB0`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<interiors-b10-port>`, `<starfield-dir>`
- **Disk Need:** `~4.4 GB` (`interiors_b10` already holds all `6` interiors — zero reconversion) + `~4.2 GB` `13`-plugin player bundle under `<starfield-dir>/Data`.
- **Plugin List (`Plugins.txt`):** `FO4Port.esm`, `FO4PortTextures2.esm`, plus the `13` Track-1 player plugins (`FO4SFMission.esm` at slot `09` with `0x000A80..0x000AC4`, `FO4SFFortHagen.esm` at slot `0D`, `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF).
- **Mission Gate Rule (`UVAL-05` / `CLUE-05`):** Both `FO4SF_MQ104` (`09000A80`) and `FO4SF_MQ105` (`09000AB0`) run ONLY in Story mode (`FO4SF_GameMode == 1`) and stop silently in Warfare mode (`mission gate mode=2 started=false quest=<mq104|mq105>`). All `6` interiors are already staged in `interiors_b10` (`FO4Port_Vault114` `02002593`, `FO4Port_Vault11402` `020109FA`, `FO4Port_DmndValentines01` `02006B30`, `FO4Port_DmndStandsKellogg01` `0206B72C`, `FO4Port_FortHagen01` `0200BA4B`, `FO4Port_FortHagen02` `0200CFC6`).

### Offline Verification & Install Commands (Game Closed)
```bash
python scripts/terrain/a7_valentine_places.py audit-a7
python scripts/terrain/a7_valentine_places.py emit-tsv
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Console-Free Walkthrough + Mid-Mission Save/Reload (`A6`) + `W6` 4-Axis Checks (`docs/quests/next-story-missions-a7.md`)
1. **Mission 4 — *Unlikely Valentine* (`FO4SF_MQ104` `09000A80`, stages `10, 20, 40, 60, 85, 100, 200`):**
   - Starts automatically on `FO4SF_MQ103` `stage 100` (`mq104 start_requested ok=True`) OR out-of-order by approaching Park Street Station `(-987.46, -2927.73)` / Vault 114 `(-1085.43, -2958.22)` (`mq104 started by=proximity`, `mq104 init stage=10 vault114_cell=0x002593`).
   - Enter `FO4Port_Vault114` (`02002593`) -> `FO4Port_Vault11402` (`020109FA`), free **Nick Valentine (`09000A82`)** (or read Open-Mode case notes if Nick is dead -> `mq104 open_mode nick_unavailable -> case_notes stage 60`), resolve **Skinny Malone (`09000A84`)** / **Darla (`09000A86`)** by persuasion or combat (if pre-cleared -> `mq104 malone pre_cleared -> stage 100`), and exit Vault 114 (`UVAL-02` `R10` `5 s` exit-door override guarantees zero lock-in: `mq104 uval02 r10_override exit_doors unlocked after=<sec>`).
   - **Mid-Mission Save/Reload (`A6`):** Save/reload **`Throwaway_A7_Vault114`** at `stage 60` -> verify `mq104 reload stage=60 complete=False`.
   - **Completion (`stage 200`):** `mq104 complete stage=200 mq105_armed=1 by=<cause>` -> `mq105 start_requested ok=True` (`09000A89=1`).
2. **Mission 5 — *Getting a Clue* (`FO4SF_MQ105` `09000AB0`, stages `10, 30, 60, 80, 100, 200`):**
   - Starts automatically from *Unlikely Valentine* `stage 200` OR out-of-order near Kellogg's House / Fort Hagen `(-2456.84, -2781.07)` (`mq105 started by=proximity`, `mq105 init stage=10 kellogg_cell=0x06B72C forthagen_door=0x0547B0`).
   - Brief at `FO4Port_DmndValentines01` (`02006B30`) with Nick (`09000A82`, or agency dossier in Open Mode) -> obtain key from **Geneva (`09000AB2`)** (or pick/unlock `0206B72C`) -> inspect `FO4Port_DmndStandsKellogg01` (`0206B72C`), open Kellogg's secret room (`mq105 secret_room unlocked by=<cause>`), collect Kellogg's cigar (`09000AB5`, `mq105 kellogg_cigar granted=true`), hand trail to **Dogmeat (`09000AB4`)** (or proceed directly to Fort Hagen in Open Mode -> `mq105 open_mode dogmeat_unavailable -> direct fort_hagen stage 100`).
   - **Mid-Mission Save/Reload (`A6`):** Save/reload **`Throwaway_A7_Kellogg`** at `stage 60` -> verify `mq105 reload stage=60 complete=False`.
   - **Fort Hagen Handoff (`0D` `FO4SFFortHagen.esm` `0x0547B0` -> `FO4Port_FortHagen01` `0200BA4B` / `FO4Port_FortHagen02` `0200CFC6`):** Reach Fort Hagen roof/entry -> `mq105 complete stage=200 mq106_armed=1 forthagen_plugin=<bool> by=<cause>` (`09000AB8=1`, ready for `MQ106` *Reunions*).

```console
sqs 09000A80
sqs 09000AB0
bat a7p1
bat a7p2
bat a7fh
bat a7u1
bat a7u2
bat a7u3
bat a7u4
bat a7c1
bat a7c2
bat a7c3
bat a7c4
```

```bat
; <starfield-dir>/a7p1.txt — A7 diagnostic check: Park Street Station / Vault 114 (02002593)
coc FO4Port_Vault114

; <starfield-dir>/a7p2.txt — A7 diagnostic check: Kellogg's House (0206B72C)
coc FO4Port_DmndStandsKellogg01

; <starfield-dir>/a7fh.txt — A7 diagnostic check: Fort Hagen Command Center handoff (0200BA4B)
coc FO4Port_FortHagen01

; <starfield-dir>/a7u1.txt — W6 Unlikely Valentine giver-dead (Open Mode Nick unavailable)
09000A82.kill
setstage 09000A80 60

; <starfield-dir>/a7u2.txt — W6 Unlikely Valentine out-of-order Malone pre-clear
09000A84.kill
setstage 09000A80 100

; <starfield-dir>/a7u3.txt — W6 Unlikely Valentine save/reload check
sqs 09000A80

; <starfield-dir>/a7u4.txt — W6 Unlikely Valentine fast-travel-away check
sqs 09000A80

; <starfield-dir>/a7c1.txt — W6 Getting a Clue giver-dead (Open Mode Nick/Geneva/Dogmeat unavailable)
09000AB2.kill
09000AB4.kill
setstage 09000AB0 100

; <starfield-dir>/a7c2.txt — W6 Getting a Clue out-of-order direct Fort Hagen arrival
setstage 09000AB0 200

; <starfield-dir>/a7c3.txt — W6 Getting a Clue save/reload check
sqs 09000AB0

; <starfield-dir>/a7c4.txt — W6 Getting a Clue fast-travel-away check
sqs 09000AB0
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log` / `Papyrus.0.log` / `FO4SFPipboyMenu.log`)
```log
FO4SF_MISSION rt=<rt> mq104 start_requested ok=<bool>
FO4SF_MISSION rt=<rt> mq104 init stage=<st> vault114_cell=0x002593
FO4SF_MISSION rt=<rt> mq104 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq104 uval02 r10_override exit_doors unlocked after=<sec>
FO4SF_MISSION rt=<rt> mq104 complete stage=200 mq105_armed=1 by=<cause>
FO4SF_MISSION rt=<rt> mq104 reload stage=<st> complete=<bool>
FO4SF_MISSION rt=<rt> mq105 start_requested ok=<bool>
FO4SF_MISSION rt=<rt> mq105 init stage=<st> kellogg_cell=0x06B72C forthagen_door=0x0547B0
FO4SF_MISSION rt=<rt> mq105 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq105 kellogg_cigar granted=true
FO4SF_MISSION rt=<rt> mq105 complete stage=200 mq106_armed=1 forthagen_plugin=<bool> by=<cause>
FO4SF_MISSION rt=<rt> mq105 reload stage=<st> complete=<bool>
FO4SF_LoadDoor requested <plugin>:<id>
step=quest_catalog file=FO4SFPipboyQuestObjectives.tsv status=<loaded|defaults> rows=<rows> tsv_rows=<tsv>
```

### Negative / FAIL Conditions
- Either `A7` quest firing in Warfare mode (`FO4SF_GameMode == 2`), Vault 114 exit doors soft-locking past `5 s` (`UVAL-02`), dead Nick/Geneva/Dogmeat soft-locking Open Mode, any of the `6` staged `interiors_b10` cells failing to load or missing textures, or FormID collision with `0x800..0xA7F`.
