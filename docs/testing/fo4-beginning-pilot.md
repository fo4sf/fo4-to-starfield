# Fallout 4 Beginning Pilot Lead Card (`B1`–`B8`, `V1`)

> **NEW GAME needed (`A16` / `R15`):** Candidate 2b requires a **NEW GAME** (`FO4SFNewGame.esm` masters `FO4SFCoreValues.esm`; old saves are not carried).

## Status Labels & Cut Content
- **`REACHABLE`**: Encountered in normal console-free play with `FO4SF_TestModeEnabled == 0`.
- **`TEST-STATION`**: Works only via a test station, test cell, or `FO4SF_TestModeEnabled == 1` command (e.g., `FO4SF_COMPreston.FollowTest`).
- **`RECORDS ONLY`**: ESM records or converted assets exist offline without runtime gameplay wiring.
- **`TOOLING`**: Offline bundle verifier and multi-session rotated log judge (`src/fo4sf/beginning_pilot.py`, `scripts/testing/check_beginning_pilot.py`).
- **`NOT BUILT`**: Explicitly cut from this round and absent in gameplay:
  - **`laser musket`** (`NOT BUILT`)
  - **`balcony talk`** (`NOT BUILT`)
  - **`power armor + fusion core`** on the museum roof (`NOT BUILT` for `REACHABLE`; test-cell station only)
  - **`minigun`** (`NOT BUILT`)
  - **`second wave`** raiders (`NOT BUILT`)
  - **`deathclaw`** civic-access emergence (`NOT BUILT`)
  - **`Preston's group moving to Sanctuary`** (`NOT BUILT` — Preston stays held at the Concord museum door after stage `200`)
- **Explicit Placeholders:** Starfield ballistic pistol + ammo **placeholder** (`0x24561C` / `0x2B559C`), Codsworth `OutpostRobotMiniBotA_Garden` skeleton reskinned with brushed-steel `codsworth.nif`, and Preston `HumanRace` (`0x00347D`) + colonial outfit + `Orion` **placeholder** with `100` Starfield `Credits` (`0x00000F`) **placeholder** reward.

---

## Card Pilot — Console-Free Beginning Walk (`B1_pod` .. `B8_sanctuary_bench`)

- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`, `<log-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data`.
- **Plugin List (`Plugins.txt`, `--profile player`, `22` plugins + `FO4SFMapMarkers.esm`):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (plus `*FO4SFMapMarkers.esm`).

### Install & Verifier Commands (Game Closed)
```bash
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <player-bundle-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/testing/check_beginning_pilot.py check-logs --log-dir <log-dir> --require-all-pass
```

### Step Matrix (`B1`–`B8`)
1. **`B1_pod` (`REACHABLE`):** Pick `Story` + `Survival: No` over the held black fade (`request=1` + `request=2` `1.0 s` after `LoadingMenu` closes), settle at the cryo pod (`stage 10 by=Trigger`), and complete looks (`stage 20 by=scene`).
2. **`B2_gear_door` (`REACHABLE`):** Pick up Vault pistol (`0x24561C`) and Pip-Boy (`0x00080F`), then activate `FO4SF_GearDoorConsoleRef` (`0x000819`, `ACTI` `0x000818`) to open the gear door (`stage 30 by=vault_console`).
3. **`B3_exit_lift` (`REACHABLE`):** Confirm `40` S.P.E.C.I.A.L. points across the `<= 7`-button boxes (`source=Lift`), press `Continue`, and complete `+21.6 m` ascent (`ascent carried confirmed`) with `map setup done`.
4. **`B4_surface_landing` (`REACHABLE`):** Reach `stage 40 by=Trigger` -> `landed ... fallback=false` -> `stage 200 by=Trigger` on the Commonwealth hilltop.
5. **`B5_codsworth_sanctuary` (`REACHABLE`):** After `stage 200`, talk to Codsworth (`0x000811`) in Sanctuary and complete Choice 4 (`codsworth talk end -> min00 stage 10`, `stage 10 by=info`).
6. **`B6_concord_raiders` (`REACHABLE`):** Fight Concord raiders (`stage 20 by=Trigger`), save, **`Quit to Desktop`**, relaunch & reload (`reload mission stage=20 relocate_fails=0`), and clear hostiles (`stage 30 by=Trigger`).
7. **`B7_preston_turnin` (`REACHABLE`):** Complete all 3 exchanges on Preston (`0x000802`) so `0x092A` sets `stage 35 by=info` -> `preston talk end info=0x092A -> stage 40` -> `stage 40 by=info` -> `100` Credits -> `stage 200 by=Trigger`.
8. **`B8_sanctuary_bench` (`REACHABLE`):** Activate Sanctuary workbench `0x005C50` (`0250FE`) to complete `sanctuary01 stage 100 by=bench` (`min01 bench activated -> stage 100`).

### Undo Command (Game Closed)
```bash
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.*.log` & `fo4sf_mission.*.log`)
```log
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0
FO4SF_NEWGAME rt=<rt> hold-off pass 2 stopped=<stopped> of <total>
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> pod settle ok=true pos=<x> <y> <z> dx=<dx> dy=<dy> drop=<drop> target=<tx> <ty> <tz> heading=<h> loaded=true cell=<cell> world=<world> sample_start=<t0> sample_end=<t1>
FO4SF_NEWGAME rt=<rt> stage 20 by=scene
FO4SF_NEWGAME rt=<rt> pistol picked item=<form> count=<n>
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<s0> after=<s1>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=Lift
FO4SF_NEWGAME rt=<rt> ascent play accepted=true ref=<lift> from=<z0> rise=21.6 seconds=<sec>
FO4SF_NEWGAME rt=<rt> map setup done markers=<n> elapsed=<sec>
FO4SF_NEWGAME rt=<rt> ascent carried confirmed elapsed=<sec> z=<z1>
FO4SF_NEWGAME rt=<rt> surface pre_setposition target=<tx> <ty> <tz> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> stage 10 by=info
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> reload mission stage=20 relocate_fails=0
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 stage 100 by=bench
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
```
