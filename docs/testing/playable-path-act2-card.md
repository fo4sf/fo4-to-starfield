Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (13-plugin playable path) & Track 2 (22-plugin experimental core + W7 Open Mode)

# Playable Path Act II Session Card (*Reunions* `MQ106`, *Dangerous Minds* `MQ203`, *The Glowing Sea* `MQ204`, *The Molecular Level* `MQ206` & Pip-Boy `0x800..0xBFF` — `Round 9` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Titles: **Fallout 4** | Modes: **Story** (`--profile player`, `13` Track-1 plugins; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`) & **Track 2 / Open Mode** (`--profile test`, `22` plugins including `FO4SFRads.esm` & `FO4SFWorkshop.esm`, still WITHOUT `FO4SFRouteLoot.esm` or `FO4SFBridge.esm`) | Track: **Track 1 playable path** (`Cards Act2-1..Act2-4`).
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME` (`R15`):** Every Act II quest state machine (`FO4SF_MQ106` `09000AD0`, `FO4SF_MQ203` `09000AF0`, `FO4SF_MQ204` `09000B10`, `FO4SF_MQ206` `09000B30`), Pip-Boy `0x800..0xBFF` scan bump, and `interiors_b10` Act II spot check on this card is **`TEST-STATION` (`prototype, offline` / OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs it in Starfield.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## Runtime Load-Order Prefix Table (`13`-Plugin `--profile player` vs `22`-Plugin `--profile test`, `FO4SFBridge.esm` & `FO4SFRouteLoot.esm` OFF)

| Plugin | `13`-Plugin Slot (`--profile player`) | `22`-Plugin Slot (`--profile test`) | Key Act II Runtime FormIDs (`<XX>000...`) |
|---|---|---|---|
| `FO4Port.esm` (+ `FO4PortTextures2.esm`) | `02` | `02` | **`0200BA4B`** `FortHagen01`, **`0200CFC6`** `FortHagen02`, **`0200ED4A`** `GoodneighborTheMemoryDen`, **`0200F23E`** `MQ203KelloggsBrain`, **`02069B10`** `VirgilsLab01`, **`02056471`** `GreenetechGenetics01`, **`0204BE53`** `GreenetechGenetics02`, **`0203C790`** `OldNorthChurch01`, **`0203CC9F`** `RailroadHQ01`, **`02003846`** `PrydwenHull01` (wired door `020045AD` / marker `0200E183` <-> `040A774D`), **`0203D252`** `InstituteConcourse` |
| `FO4TerrainCore.esm` | `04` | `04` | `04005C50` Sanctuary workbench (`FO4SF_MQ206` universal build bench), `040A775A` Sanctuary Hills marker, `040A775B` Commonwealth `WorldSpace` anchor, `040A774D` Prydwen exterior marker |
| `FO4SFCoreValues.esm` | `06` | `06` | `06000800` `FO4SF_Rads` AVIF, `06000804` `FO4SF_RadResist` AVIF, `06000865` `FO4SF_PipboyAcquired`, `06000870` `FO4SF_GameMode` (`1`=Story, `2`=Warfare) |
| `FO4SFMission.esm` | **`09`** | **`09`** | **`09000AD0`** `FO4SF_MQ106` (*Reunions*: Kellogg `09000AD1`/`09000AD2`, `09000AD3` `FO4SF_CyberBrain`, `09000AD4` `FO4SF_KelloggPassword`, `09000AD5` `FO4SF_MQ106_TerminalProxyActi`, `09000AD6` `FO4SF_PrydwenArrived`, `09000AD7` `FO4SF_MQ203Armed`), **`09000AF0`** `FO4SF_MQ203` (*Dangerous Minds*: Amari `09000AF1`/`09000AF2`, `09000AF3` `FO4SF_MQ203_LoungerProxyActi`, `09000AF4` `FO4SF_MemoriesCompleted`, `09000AF5` `FO4SF_MQ204Armed`), **`09000B10`** `FO4SF_MQ204` (*The Glowing Sea*: Isolde `09000B11`/`09000B12`, Virgil `09000B13`/`09000B14`, `09000B15` `FO4SF_VirgilNote`, `09000B16` `FO4SF_MQ204_LabTerminalProxyActi`, `09000B17` `FO4SF_GlowingSeaRadsActive`, `09000B18` `FO4SF_MQ206Armed`), **`09000B30`** `FO4SF_MQ206` (*The Molecular Level*: Courser `09000B31`/`09000B32`, Desdemona `09000B33`/`09000B34`, Tinker Tom `09000B35`/`09000B36`, Proctor Ingram `09000B37`/`09000B38`, `09000B39` `FO4SF_CourserChip`, `09000B3A` `FO4SF_CourserChipHolotape`, `09000B3B` `FO4SF_SignalInterceptorPlans`, `09000B3C` `FO4SF_MQ206_ScannerProxyActi`, `09000B3D` `FO4SF_MQ206_ConsoleProxyActi`, `09000B40..09000B47` build/faction/relay `GLOB`s) |
| `FO4SFRads.esm` | *Omitted (Track 1)* | **`0B`** | Track 2 environmental rads hazards (`FO4SF_MQ204` auto-defers its Track 1 SW ticker when `FO4SFRads.esm` is installed) |
| `FO4SFWorkshop.esm` | **`0B`** | **`0D`** | Track 2 live workshop `COBJ` placement alongside `FO4SF_MQ206`'s console-free Workbench Signal Interceptor Assembly Menu (`09000B55`) |
| `FO4SFFortHagen.esm` | **`0D`** | **`15`** | `0D0547B0` / `150547B0` Fort Hagen roof load door, `0D00DE53` / `1500DE53` Command Center roof elevator, `0D0A774C` / `150A774C` Fort Hagen roof marker |
| `FO4SFMapMarkers.esm` | **`10`** | **`19`** | Persistent `0x400` exterior arrival refs (enabled after `FO4SF_MapMarkers` settles): **`1000090A`** / `1900090A` Fort Hagen `(-2456.84, -2781.07, 81.83)`, **`10000990`** / `19000990` Water Street Apartments `(-889.50, -2913.52, 9.71)` (`45 m` SE of Goodneighbor gate), **`10000A00`** / `19000A00` Edge of the Glowing Sea `(-2001.32, -3821.65, 51.85)`, **`100009C9`** / `190009C9` Crater of Atom `(-2624.44, -4357.85, 107.64)`, **`100009D9`** / `190009D9` Rocky Cave `(-2862.81, -4653.27, 143.19)`, **`1000099A`** / `1900099A` Greenetech Genetics `(-1238.10, -2687.39, 12.18)`, **`10000980`** / `19000980` Old North Church `(-785.19, -2684.39, 11.15)` (`51 m` from Railroad exterior), **`1000099B`** / `1900099B` Boston Airport `(-513.23, -2747.60, 10.27)` |

### Border Safety (`< 200 m` / Axis) & `P3` Zero-`M`/`N`/`V` Console Rule
1. **Never run a single `player.setpos` jump `> 200 m` on X or Y** (`docs/terrain/core64c.md`, `docs/terrain/border.md`). For Act II long-distance travel across the Commonwealth, either walk/fast-travel via Pip-Boy `MAP` (or `player.moveto` to the verified persistent `0x400` `FO4SFMapMarkers.esm` refs above once `FO4SF_MapMarkers` settles, stepping `< 180 m` per axis from the arrival ref to any nearby door/NPC!).
2. Every ```` ```console ```` block below contains **zero `M`, `N`, or `V` letters** (case-insensitive) and **zero stripped mod `GLOB`/`QUST` EditorIDs**. All `moveto`, `coc`, `kill`, `setstage`, and `sqv` calls live inside `P3`-safe `<starfield-dir>/<bat-id>.txt` batch files.

---

## Card Act2-1 — *Reunions* (`FO4SF_MQ106`, `09000AD0..09000AE3`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<interiors-b10-port>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.4 GB` (`interiors_b10` `FO4Port.esm` + `FO4PortTextures2.esm`, zero reconversion) + `~4.2 GB` `13`-plugin Track-1 bundle (`0 B` extra on installed bundle).
- **Plugin List (`Plugins.txt`):** `FO4Port.esm`, `FO4PortTextures2.esm`, plus the `13` Track-1 plugins (`FO4SFMission.esm` at `09`, `FO4SFFortHagen.esm` at `0D`, `FO4SFMapMarkers.esm` at `10`; `FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF).
- **Mission Gate Rule:** Runs ONLY in Story mode (`FO4SF_GameMode == 1`); Warfare mode stops silently (`mission gate mode=2 started=false quest=mq106`).

### Offline Audit & Install Commands (Game Closed)
```bash
python scripts/terrain/a7b_reunions_places.py audit-a7b
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Walkthrough, Open-Mode Dead-Giver Fallbacks & Save/Reload (`A6`)
1. **Start & Arrival (`09000AD0`, stages `10, 50, 75, 100, 125, 150, 200, 500`):** Starts automatically from *Getting a Clue* (`09000AB0` `stage 200` -> `mq106 start_requested ok=True`) OR out-of-order within `150 m` of Fort Hagen `(-2456.84, -2781.07, 81.83)` (`bat a2fh` uses persistent `1000090A` / `1900090A`, `mq106 started by=proximity`, `mq106 init stage=<st> forthagen_plugin=True`).
2. **Fort Hagen Confrontation & Hostile Boss Kellogg (`09000AD1`/`09000AD2`):** Enter via `FO4SFFortHagen.esm` (`0D0547B0` -> `FO4Port_FortHagen01` `0200BA4B` -> `FO4Port_FortHagen02` `0200CFC6`). Defeat hostile armed Kellogg (`09000AD2`, `!Essential`, `!Protected`, `mq106 kellogg placed forthagen=true`) to receive `FO4SF_CyberBrain` (`09000AD3`, `mq106 cyber_brain granted=true by=<why>`) and `FO4SF_KelloggPassword` (`09000AD4`, `mq106 kellogg_password granted=true by=<why>`).
3. **Open-Mode Backup (`REUN-03` / `REUN-05`):** If Kellogg's corpse is unreachable or Nick/Piper are dead at debrief, activate **`FO4SF_MQ106_TerminalProxyActi` (`09000AD5`)** (`mq106 terminal proxy spawned`) for backup augmenter/password/dossier completion (`stage 150 -> 200 -> 500`).
4. **Mid-Mission Save/Reload (`A6`):** Save **`Throwaway_Act2_FortHagen`** at `stage 100` (before/during Kellogg) -> **`Quit to Desktop`** -> relaunch -> load -> verify `mq106 reload stage=100 complete=False` and zero Kellogg misplacement.
5. **Roof Exit & *Prydwen* Arrival (`REUN-04`):** Exit to Commonwealth exterior (`0D00DE53 -> 0D0A774C` or fast travel) -> sets `FO4SF_PrydwenArrived` (`09000AD6=1`, `mq106 prydwen_arrived=1 by=<why>`) -> debrief -> `mq106 complete stage=500 mq203_armed=1 mq203_started=True prydwen=1 by=<cause>` (`09000AD7=1`).

```console
sqs 09000AD0
bat a2fh
bat a2r1
bat a2r2
bat a2r3
bat a2r4
```

```bat
; <starfield-dir>/a2fh.txt — Persistent 0x400 Fort Hagen arrival ref (1000090A in 13-plugin; use 1900090A in 22-plugin)
player.moveto 1000090A

; <starfield-dir>/a2r1.txt — W6 Reunions out-of-order direct Fort Hagen arrival (bypasses Dogmeat)
coc FO4Port_FortHagen01

; <starfield-dir>/a2r2.txt — W6 Reunions giver/NPC dead + Kellogg pre-attack & backup terminal proxy
09000AD2.kill
sqs 09000AD0

; <starfield-dir>/a2r3.txt — W6 Reunions save/reload verification
sqs 09000AD0

; <starfield-dir>/a2r4.txt — W6 Reunions fast-travel-away Prydwen arrival check
player.moveto 040A775A
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
FO4SF_MISSION rt=<rt> mq106 start_requested ok=<bool>
FO4SF_MISSION rt=<rt> mq106 init stage=<st> forthagen_plugin=<bool>
FO4SF_MISSION rt=<rt> mq106 kellogg placed forthagen=true
FO4SF_MISSION rt=<rt> mq106 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq106 cyber_brain granted=true by=<why>
FO4SF_MISSION rt=<rt> mq106 kellogg_password granted=true by=<why>
FO4SF_MISSION rt=<rt> mq106 prydwen_arrived=1 by=<why>
FO4SF_MISSION rt=<rt> mq106 complete stage=500 mq203_armed=1 mq203_started=<bool> prydwen=1 by=<cause>
FO4SF_MISSION rt=<rt> mq106 reload stage=<st> complete=<bool>
```

### Negative / FAIL Conditions
- `FO4SF_MQ106` firing in Warfare mode, Kellogg (`09000AD2`) non-hostile or stuck Essential/Protected, missing `FO4SF_CyberBrain`/`FO4SF_KelloggPassword` soft-locking `stage 150`, or `FO4SF_PrydwenArrived` (`09000AD6`) failing to set on roof/fast-travel exit.

---

## Card Act2-2 — *Dangerous Minds* (`FO4SF_MQ203`, `09000AF0..09000B03`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<interiors-b10-port>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.4 GB` (`interiors_b10`, zero reconversion) + `~4.2 GB` `13`-plugin bundle (`0 B` extra on Card Act2-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins (`FO4SFMission.esm` at `09`, `FO4SFMapMarkers.esm` at `10`).

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Walkthrough, Open-Mode Dead-Giver Fallbacks & Save/Reload (`A6`)
1. **Start & Goodneighbor Arrival (`09000AF0`, stages `5, 10, 100, 110, 120, 300`):** Starts automatically from *Reunions* `stage 500` OR out-of-order within `150 m` of Goodneighbor gate `(-902.48, -2870.07, 19.20)` (`bat a2gd` uses persistent `10000990` Water Street Apartments, `45 m` SE of Goodneighbor gate -> `45 m` walk NW, strictly `< 180 m`/axis; logs `mq203 started by=proximity`, `mq203 init stage=<st> memory_den=0x00ED4A brain_cell=0x00F23E`).
2. **Doctor Amari (`09000AF1`/`09000AF2`) & Memory Lounger (`09000AF3`):** Speak with **Doctor Amari (`09000AF2`, female voice/template, `!Essential`, `mq203 amari placed goodneighbor=true`)** -> activate **`FO4SF_MQ203_LoungerProxyActi` (`09000AF3`)** (`mq203 lounger proxy spawned`) -> enters `FO4Port_MQ203KelloggsBrain` (`0200F23E`) via binary-verified persistent (`0x400`) `COCMarkerHeading` **`0x00F2D3`** (`mq203 brain_move dest=0x00F2D3 ok=true`, or `mq203 brain_move fallback=inline_scan` if `FO4Port.esm` cell is unavailable), and on completion returns cleanly out of `0200F23E` (`R10` never-strand) to persistent (`0x400`) Memory Den `COCMarkerHeading` **`0x00F23D`** inside `FO4Port_GoodneighborTheMemoryDen` (`0200ED4A`).
3. **Open-Mode Dead-Giver Fallback (`MIND-01` / `MIND-05`):** If Doctor Amari (`09000AF2`) is dead, activating `FO4SF_MQ203_LoungerProxyActi` (`09000AF3`) runs the autonomous brain-pod self-scan and completes `stage 110 -> 120 -> 300` cleanly without soft-locking.
4. **Mid-Mission Save/Reload (`A6`):** Save **`Throwaway_Act2_MemoryDen`** at `stage 110` -> **`Quit to Desktop`** -> relaunch -> load -> verify `mq203 reload stage=110 complete=False` and `talkSessionId` modal recovery.
5. **Completion (`stage 300`):** Sets `FO4SF_MemoriesCompleted` (`09000AF4=1`) and `FO4SF_MQ204Armed` (`09000AF5=1`) -> `mq203 complete stage=300 memories=1 mq204_armed=1 mq204_started=True by=<cause>`.

```console
sqs 09000AF0
bat a2gd
bat a2d1
bat a2d2
bat a2d3
bat a2d4
```

```bat
; <starfield-dir>/a2gd.txt — Persistent 0x400 Water Street Apartments (45 m SE of Goodneighbor gate; 19000990 in 22-plugin)
player.moveto 10000990

; <starfield-dir>/a2d1.txt — W6 Dangerous Minds giver-dead (Open Mode Amari dead -> lounger self-scan)
09000AF2.kill
sqs 09000AF0

; <starfield-dir>/a2d2.txt — W6 Dangerous Minds diagnostic cell check (GoodneighborTheMemoryDen / MQ203KelloggsBrain)
coc FO4Port_GoodneighborTheMemoryDen

; <starfield-dir>/a2d3.txt — W6 Dangerous Minds save/reload verification
sqs 09000AF0

; <starfield-dir>/a2d4.txt — W6 Dangerous Minds brain dreamscape spot check (0200F23E)
coc FO4Port_MQ203KelloggsBrain
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log`)
```log
FO4SF_MISSION rt=<rt> mq203 init stage=<st> memory_den=0x00ED4A brain_cell=0x00F23E
FO4SF_MISSION rt=<rt> mq203 amari placed goodneighbor=true
FO4SF_MISSION rt=<rt> mq203 lounger proxy spawned
FO4SF_MISSION rt=<rt> mq203 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq203 complete stage=300 memories=1 mq204_armed=1 mq204_started=<bool> by=<cause>
FO4SF_MISSION rt=<rt> mq203 reload stage=<st> complete=<bool>
```

### Negative / FAIL Conditions
- `FO4SF_MQ203` firing in Warfare mode, furniture sit-lock on Memory Lounger (`MIND-03`), dead Doctor Amari (`09000AF2`) soft-locking `stage 10 -> 120 -> 300`, or `FO4SF_MQ204Armed` (`09000AF5`) failing to arm on completion.

---

## Card Act2-3 — *The Glowing Sea* (`FO4SF_MQ204`, `09000B10..09000B23`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<cand2f-test-bundle>`, `<interiors-b10-port>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.4 GB` (`interiors_b10`, zero reconversion) + `~4.2 GB` player or test bundle (`0 B` extra on Card Act2-1).
- **Plugin List (`Plugins.txt`):** Track 1 `13`-plugin bundle (`FO4SFRads.esm` absent -> `rads_plugin=False`, Track 1 SW rads ticker active via `FO4SF_GlowingSeaRadsActive` `09000B17`) OR Track 2 `22`-plugin bundle (`FO4SFRads.esm` at `0B` -> `rads_plugin=True`, Track 1 ticker automatically defers).

### Offline Audit & Install Commands (Game Closed)
```bash
python scripts/terrain/a7d_glowing_sea_places.py audit-a7d
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Walkthrough, Track 1 vs Track 2 Rads, Open-Mode Dead-Giver Fallbacks & Save/Reload (`A6`)
1. **Start & Glowing Sea Entry (`09000B10`, stages `10, 15, 20, 50, 200`):** Starts automatically from *Dangerous Minds* `stage 300` OR out-of-order entering the SW Glowing Sea (`bat a2gs` -> persistent `10000A00` Edge of the Glowing Sea, then `bat a2cr` -> persistent `100009C9` Crater of Atom; logs `mq204 started by=proximity`, `mq204 init stage=<st> rads_plugin=<bool>`).
   - **Track 1 vs Track 2 Rads Check:** In `13`-plugin Track 1 (`rads_plugin=False`), confirm `FO4SF_GlowingSeaRadsActive` (`09000B17`) ticks radiation onto `06000800` scaled by `06000804` RadResist; in `22`-plugin Track 2 (`rads_plugin=True`), confirm the quest defers cleanly to `FO4SFRads.esm` (`0B`).
2. **Crater of Atom (`FO4_MotherIsolde` `09000B11`/`09000B12`) + Open-Mode `FO4SF_VirgilNote` (`09000B15`):** Speak with **Mother Isolde (`09000B12`, female, `!Essential`, `mq204 isolde placed crater=true`)** — OR if Mother Isolde is dead, collect **`FO4SF_VirgilNote` (`09000B15`)** (`mq204 virgil_note granted=true by=<why>`) OR walk directly to Rocky Cave (`bat a2rc` -> persistent `100009D9` `(-2862.81, -4653.27, 143.19)`).
3. **Rocky Cave / Virgil's Lab (`FO4Port_VirgilsLab01` `02069B10`) & `GLOW-04` PA Targeting Guard:** Speak with **Virgil (`09000B14`, `!Essential`, `mq204 virgil placed rocky_cave=true`)** — verify wearing Power Armor does NOT trigger permanent hostility (`IgnoreFriendlyHits(True)` + `mq204 virgil stopcombat reason=pa_targeting_guard`). If Virgil is dead in Open Mode, activate **`FO4SF_MQ204_LabTerminalProxyActi` (`09000B16`)** (`mq204 lab terminal proxy spawned`) to complete `stage 50 -> 200`.
4. **Mid-Mission Save/Reload (`A6`):** Save **`Throwaway_Act2_GlowingSea`** at `stage 20` -> **`Quit to Desktop`** -> relaunch -> load -> verify `mq204 reload stage=20 complete=False` and `Virgil.IgnoreFriendlyHits(True)` re-applied.
5. **Completion (`stage 200`):** Sets `FO4SF_MQ206Armed` (`09000B18=1`) -> `mq204 complete stage=200 mq206_armed=1 mq206_started=True rads_plugin=<bool> by=<cause>`.

```console
sqs 09000B10
bat a2gs
bat a2cr
bat a2rc
bat a2g1
bat a2g2
bat a2g3
bat a2g4
```

```bat
; <starfield-dir>/a2gs.txt — Persistent 0x400 Edge of the Glowing Sea (10000A00 in 13-plugin; 19000A00 in 22-plugin)
player.moveto 10000A00

; <starfield-dir>/a2cr.txt — Persistent 0x400 Crater of Atom (100009C9 in 13-plugin; 190009C9 in 22-plugin)
player.moveto 100009C9

; <starfield-dir>/a2rc.txt — Persistent 0x400 Rocky Cave / Virgil's Lab (100009D9 in 13-plugin; 190009D9 in 22-plugin)
player.moveto 100009D9

; <starfield-dir>/a2g1.txt — W6 Glowing Sea giver-dead (Open Mode Isolde + Virgil dead -> VirgilNote + LabTerminal proxy)
09000B12.kill
09000B14.kill
sqs 09000B10

; <starfield-dir>/a2g2.txt — W6 Glowing Sea out-of-order direct Virgil's Lab cell check (02069B10)
coc FO4Port_VirgilsLab01

; <starfield-dir>/a2g3.txt — W6 Glowing Sea save/reload verification
sqs 09000B10

; <starfield-dir>/a2g4.txt — W6 Glowing Sea fast-travel-away Sanctuary check
player.moveto 040A775A
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log`)
```log
FO4SF_MISSION rt=<rt> mq204 init stage=<st> rads_plugin=<bool>
FO4SF_MISSION rt=<rt> mq204 isolde placed crater=true
FO4SF_MISSION rt=<rt> mq204 virgil placed rocky_cave=true
FO4SF_MISSION rt=<rt> mq204 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq204 complete stage=200 mq206_armed=1 mq206_started=<bool> rads_plugin=<bool> by=<cause>
FO4SF_MISSION rt=<rt> mq204 reload stage=<st> complete=<bool>
```

### Negative / FAIL Conditions
- `FO4SF_MQ204` firing in Warfare mode, Virgil turning permanently hostile in Power Armor (`GLOW-04`), dead Isolde/Virgil soft-locking Open Mode, or `FO4SF_MQ206Armed` (`09000B18`) failing to arm on completion.

---

## Card Act2-4 — *The Molecular Level* (`FO4SF_MQ206`, `09000B30..09000B56`) & Pip-Boy `0x800..0xBFF` Live Sync (`TEST-STATION`)

- **Stage Placeholders:** `<cand2f-player-bundle>`, `<pipboy-stage-dir>`, `<interiors-b10-port>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.4 GB` (`interiors_b10`, zero reconversion) + `~4.2 GB` `13`-plugin bundle + `~5 MB` `FO4SFPipboyMenu.dll` (`0x800..0xBFF` scan) & `FO4SFPipboyQuestObjectives.tsv`.
- **Plugin List (`Plugins.txt`):** `FO4Port.esm`, `FO4PortTextures2.esm`, plus the `13` Track-1 plugins (`FO4SFMission.esm` at `09`, `FO4SFWorkshop.esm` at `0B`, `FO4SFMapMarkers.esm` at `10`).

### Stage & Install Commands (Game Closed)
```bash
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --a5-playable
python scripts/ui/pipboy_mission_catalog.py --out <pipboy-stage-dir>/SFSE/Plugins/FO4SFPipboyQuestObjectives.tsv
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2f-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2f-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2f-player-bundle> --starfield <starfield-dir>
```

### Walkthrough, Faction Branches, Open-Mode Solo Build, Save/Reload (`A6`) & Pip-Boy `0xBFF` Check
1. **Courser Hunt (`MQ205` Bridge, `stage 10 -> 20`):** Starts from *The Glowing Sea* `stage 200` OR out-of-order near Greenetech Genetics (`bat a2gt` -> persistent `1000099A` `(-1238.10, -2687.39, 12.18)`, `mq206 started by=proximity`, `mq206 init stage=<st> institute_cell=0x03D252`). Defeat hostile armed **Courser `Z2-47` (`09000B31`/`09000B32`, `!Essential`, `!Protected`, `mq206 courser placed greenetech=true`)** at `FO4Port_GreenetechGenetics01` (`02056471`) -> grants `FO4SF_CourserChip` (`09000B39`).
2. **Railroad Chip Decode (`stage 20 -> 65 -> 100`) & Open-Mode Self-Decode (`MOL-05`):** Travel to Old North Church (`bat a2rr` -> persistent `10000980`, `51 m` from `FO4Port_RailroadHQ01` `0203CC9F`). Speak with **Desdemona (`09000B34`, female)** / **Tinker Tom (`09000B36`)** (`mq206 railroad actors placed=true`) — OR if Railroad is dead/hostile, activate **`FO4SF_MQ206_ScannerProxyActi` (`09000B3C`)** (`mq206 scanner proxy spawned`, `mq206 railroad_self_decode armed=true by=<by>`) -> grants `FO4SF_CourserChipHolotape` (`09000B3A`). Return to Virgil (`09000B14`, or lab terminal `09000B16` if dead) for **`FO4SF_SignalInterceptorPlans` (`09000B3B`)**.
3. **Faction Pick (`stage 200 -> 300`, `MOL-03`) & Console-Free Workbench Assembly Menu (`stage 350 -> 700`, `MOL-01`):**
   - Pick any faction engineer (`1`=Minutemen/Sturges, `2`=Railroad/Tinker Tom, `3`=BoS/**Proctor Ingram `09000B38`, female** at Boston Airport `bat a2ba` `1000099B` / `mq206 ingram placed airport=true`, or **`0`=Open-Mode Solo Self-Build** if all 3 engineers are dead -> `mq206 faction_selected=0 reason=open_mode_engineers_unavailable`; re-selectable until `stage 350` commit via `FO4SF_MQ206TeleporterFaction` `09000B40`).
   - Activate Sanctuary workbench (`04005C50`, universally valid across all branches) -> build all 4 parts via `FO4SF_MQ206_WorkbenchBuildMsg` (`09000B55`): **Reflector Platform** (`09000B41`, `mq206 built part=platform`), **Beam Emitter** (`09000B42`, `mq206 built part=beam`), **Relay Dish** (`09000B43`, `mq206 built part=dish`), **Console** (`09000B44`, `mq206 built part=console`), then atomic **Connect & Power (+27)** (`09000B45=1`, `09000B46=1`; trying to power early logs `mq206 power_refused reason=parts_incomplete`).
4. **Mid-Mission Save/Reload (`A6`):** Save **`Throwaway_Act2_Molecular`** at `stage 350` (mid-assembly) -> **`Quit to Desktop`** -> relaunch -> load -> verify `mq206 reload stage=350 complete=False`, built `GLOB`s (`09000B41..09000B46`) preserved, and `talkSessionId` modal recovery clean.
5. **Signal Interceptor Relay (`stage 1000 -> 1200`, `MOL-02`):** Activate **`FO4SF_MQ206_ConsoleProxyActi` (`09000B3D`)** (`mq206 console proxy spawned sanctuary=true`) -> direct `MoveTo` **`FO4Port_InstituteConcourse` (`0203D252`)** via binary-verified persistent (`0x400`) `COCMarkerHeading` **`0x03D52E`** (`mq206 relay_move dest=0x03D52E ok=true` or `mq206 relay_move cell=0x03D252 marker=fallback`) -> sets **`FO4SF_MQ207Armed` (`09000B47=1`)** -> `mq206 complete stage=1200 faction=<n> mq207_armed=1 institute_cell=0x03D252 by=<cause>`.
6. **Pip-Boy `0x800..0xBFF` Live Quest & `MAP` Verification:** Press **`F7`** -> **`DATA -> QUESTS`** and **`MAP`** across Act II -> verify all 4 Act II quests (`09000AD0`, `09000AF0`, `09000B10`, `09000B30`) appear inside `FO4SFPipboyMenu.dll`'s `0x800..0xBFF` scan (`step=quest_catalog`, `step=quests_collect`, `step=map_quest_markers`).

```console
sqs 09000B30
bat a2gt
bat a2rr
bat a2ba
bat a2ic
bat a2s1
bat a2s2
bat a2s3
bat a2s4
```

```bat
; <starfield-dir>/a2gt.txt — Persistent 0x400 Greenetech Genetics (1000099A in 13-plugin; 1900099A in 22-plugin)
player.moveto 1000099A

; <starfield-dir>/a2rr.txt — Persistent 0x400 Old North Church / Railroad HQ (10000980 in 13-plugin; 19000980 in 22-plugin)
player.moveto 10000980

; <starfield-dir>/a2ba.txt — Persistent 0x400 Boston Airport / Prydwen (1000099B in 13-plugin; 1900099B in 22-plugin)
player.moveto 1000099B

; <starfield-dir>/a2ic.txt — Diagnostic Institute Concourse cell check (0203D252)
coc FO4Port_InstituteConcourse

; <starfield-dir>/a2s1.txt — W6 Molecular Level giver/faction dead (Open Mode Railroad wiped + solo engineer fallback)
09000B34.kill
09000B36.kill
09000B38.kill
sqs 09000B30

; <starfield-dir>/a2s2.txt — W6 Molecular Level out-of-order Courser pre-clear
09000B32.kill
sqs 09000B30

; <starfield-dir>/a2s3.txt — W6 Molecular Level save/reload verification
sqs 09000B30

; <starfield-dir>/a2s4.txt — W6 Molecular Level fast-travel-away Sanctuary build bench check
player.moveto 040A775A
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log` / `FO4SFPipboyMenu.log`)
```log
FO4SF_MISSION rt=<rt> mq206 init stage=<st> institute_cell=0x03D252
FO4SF_MISSION rt=<rt> mq206 courser placed greenetech=true
FO4SF_MISSION rt=<rt> mq206 railroad actors placed=true
FO4SF_MISSION rt=<rt> mq206 ingram placed airport=true
FO4SF_MISSION rt=<rt> mq206 stage <n> by=<cause>
FO4SF_MISSION rt=<rt> mq206 faction_selected=<n>
FO4SF_MISSION rt=<rt> mq206 built part=platform
FO4SF_MISSION rt=<rt> mq206 built part=beam
FO4SF_MISSION rt=<rt> mq206 built part=dish
FO4SF_MISSION rt=<rt> mq206 built part=console
FO4SF_MISSION rt=<rt> mq206 console proxy spawned sanctuary=true
FO4SF_MISSION rt=<rt> mq206 complete stage=1200 faction=<n> mq207_armed=1 institute_cell=0x03D252 by=<cause>
FO4SF_MISSION rt=<rt> mq206 reload stage=<st> complete=<bool>
step=quest_catalog file=FO4SFPipboyQuestObjectives.tsv status=<loaded|defaults> rows=<rows> tsv_rows=<tsv>
step=quests_collect n=<n> active=<a> completed=<c> objectives=<o> quest_markers=<qm>
step=map_quest_markers n=<k> first_quest=<hex> obj=<num> x=<x> y=<y>
```

### Negative / FAIL Conditions
- `FO4SF_MQ206` firing in Warfare mode, Courser `Z2-47` (`09000B32`) non-hostile or stuck Essential, split power-grid or emitter alignment deadlock (`MOL-01`), scientist AI pathing hang (`MOL-02`), dead Railroad or engineers soft-locking Open Mode (`MOL-03`/`MOL-05`), relay failing to reach `FO4Port_InstituteConcourse` (`0203D252`), or Act II quests missing from Pip-Boy `DATA / Quests` (`0x800..0xBFF`).
