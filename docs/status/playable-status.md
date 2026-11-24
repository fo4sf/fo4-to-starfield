# FO4SF Playable Status Ledger

Single-source status tracker for Fallout 4 -> Starfield builds, probes, Claude's animation/sound additions, combat arsenal & impacts, and Round 12 workstreams.

- **Repo Baseline:** `main` @ `b2b19a03` (`23 Nov 2026`)
- **Frozen Baseline Snapshot:** `candidate-2` through `candidate-2g-fix2` (`10` core folders) + `r11-p1-museum`, `r11-p1-museum-v2`, `r11-p4-10mm`, `r11-p5-weapons` (`4` probe folders), verified unmodified via standalone `verify_frozen_baseline.py` against `r12_frozen_baseline.json`.
- **Tested Native Binary Reuse (`R12-7`):** Reuse tested `FO4SFPipboyMenu.dll` (`sha256 7d5ba49c0c6ab2aa`, `1,453,568` bytes from `<cand2g-fix>/test/sfse_sidecar/SFSE/Plugins/FO4SFPipboyMenu.dll`) and unchanged `.pex` scripts without rebuilding unless Task 4 modifies C++ source.

---

## 1. Core Candidates & Staged Probes

| Build / Probe | PR / Commit | Status (23 Nov) | Verified Coverage & Key Findings |
|---|---|---|---|
| **`candidate-2g`** | `#32` `7085816241` (`73ea9a4b` == `main` `fb22fa2b`) | **PASSED IN GAME (22 Nov)** | `13`-plugin Track 1 (`32 min`, `0` crashes): cryo->surface, cold Quit-to-Desktop reloads #1/#2, Codsworth `C2`/`C6`, Concord street fight god mode OFF, Preston `C1`/`D5`/quest completion, Sanctuary bench `R1`/`R2`/`R3`, `C4` Pip-Boy `F7`/`M`, `D5`/`C5` FO4 outfits. Flaws `D1`–`D7` logged. |
| **`candidate-2g-fix`** | `#852` `77a16225` (`#32` `7105591179`) | **RAN 23 Nov — NOT READY** | `D7` weather/HUD watch hide, `D2` Preston hat/raiders, and `D6` leg 5a (`7.0 s`, `1.2 m`) passed; `E1` regression (`StopDialogueCamera` dropped Codsworth talk to MessageBox 3/3) + `E2`–`E7` logged. |
| **`candidate-2g-fix2`** | `#852` `5110793b` (`#32` `7112593395`, CI GREEN) | **STAGED — AWAITING GAME RUN** | Addresses `E1`–`E7`: removed `StopDialogueCamera`, bounded `1..3` scene restarts, post-mission `090009C0`/`09000990` repeat scenes, zero `fallback=messagebox`, `E2` facing_deg, `E3` `3`-dmg `0900097A` `Eon` x36, `E4` auto-equip, `E5` `rescue_dead`, `E6` clean bench & `LCTN`/`STDT` fixes, `E7` Pip-Boy keys. Branch frozen until game result; review fixes `F1`–`F4` queued in R12 Task 1a. |
| **Probe `P4` (`r11-p4-10mm`)** | `#853` `a5c842cf` (`#32` `7106319073`) | **PASSED IN GAME (23 Nov)** | `10mm Pistol` + `10mm Round` probe passed in game with `5` minor notes (`ArmoryCageDoor` nullptr fixed in `P5`, `StartGameEnabled`, restrained target). |
| **Probe `P1 v1` (`r11-p1-museum`)** | `#853` `a5c842cf` (`#32` `7106319073`) | **BLOCKED IN GAME (23 Nov)** | Blocked by `WRLD 0x02000803` stub (`z=12.6` Mars), blocking `dir=out` load screen, blown-out `LTMP 0x00006658`, missing `DNAM` start-game flag, and non-persistent `BasementGate` VMAD ref. |
| **Probe `P1 v2` (`r11-p1-museum-v2`)** | `#853` `2ee162ec` (`#32` `7113350141`, CI GREEN) | **STAGED — AWAITING GAME RUN** | Lossless museum append (`> 0x00E199`), `0` `WRLD`/`PNDT`/ext-`CELL` overrides on `FO4Core_Commonwealth`, persistent refs. P1v2 review items (`F4`, `F9`, Novice lock on `0x0005C66C`) queued in R12 Task 1. |
| **Probe `P5` (`r11-p5-weapons`)** | `#853` `2ee162ec` (`#32` `7113351522`, CI GREEN) | **STAGED — AWAITING GAME RUN** | `4` weapons (`Baton`, `10mm Pistol`, `Laser Musket`, `Minigun`) with moving-part NIF hierarchy & `< 200 m` hop checks. Review fixes `F1`, `F3`–`F6` queued in R12 Task 2a. |

---

## 2. Claude's 5 Additions (23 Nov In-Game Baseline)

| Addition | PR / Track | 23 Nov In-Game Status | Open Gaps / Round 12 Consumption |
|---|---|---|---|
| **1. Robot animations & Codsworth** | `#854` (`claude/robot-anim` `abfa189c`, `OPEN`) | **Partial pass in game:** FO4 `.rig`/`.af`/`.afx` animations + Codsworth on 15-part Mr. Handy body; 4-line Sanctuary talk `completed=true`, `fallback=0`. | Close dialogue camera & greeting replay noted; independent review CLEAR, awaiting owner merge. Conflict prep (`M1`) & pre-war `--codsworth-handy` in R12 Tasks 1a & 6. |
| **2. Creature animations** | `#855` (`claude/creature-anim` `b182e0a5`, `OPEN`, stacked on `#854`) | **Partial in game (`#32` `7113971259`):** 5 FO4 creatures (`radroach`, `bloatfly`, `mole rat`, `dog`, `deathclaw`) converted; radroach legs/body idle & deathclaw tail/spines moved. | Walking, attacks, deaths, and `bloatfly`/`mole rat`/`dog` unverified in game (spawned out of view). R12 consumes via `creature-slots.json` with empty-slot fallback. |
| **3. Human animations** | `#856` (`claude/human-anim` `3dab65f0`, `OPEN`, stacked on `#854`) | **Partial in game (`#32` `7113971259`):** Add-on race keyword NPC played FO4 hands-up surrender idle while control human NPC stood normally. | Walking (NPCs did not walk on floor) & 1stP gun clip (`unwired`) unverified in game. Kept behind `--fo4-human-anims` (default OFF) in R12 Task 1 until PASS. |
| **4. Gun moving parts proof** | `#32` `7110977923` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | **Visual/animation proof:** `Gun_*.af` clip animates `XM2311` slide nodes (`TRIGGER`, `Magazine`, `Bolt`, `MiscA..MiscA14` + controller side file). | **23 Nov owner rule: "Parts must move" — guns are NOT ready until parts move.** R12 Task 2a moves `P5`/`P6` geometry onto donor receiver node names + `fo4_part_map`. |
| **5. Gun sounds** | `#32` `7108849978`, `7113971259` | **ON HOLD:** Hand-made bank (`v174` vs SF `v140`) and direct byte-copy of Bethesda add-on bank both stayed silent in game (add-on banks load on demand, not globally). | Next test finds what ties a bank to its item; Wwise bank tool fallback awaits owner OK. All R12 weapons retain labelled Starfield stand-in `SNDR` audio. |

---

## 3. Arsenal & Impacts

- **20-Row Weapon Arsenal (`scripts/weapons/stage_r11_weapons.py`, R12 Task 2):**
  - **Rows 1–4 (`P5` staged + `F1`–`F6` fixes in Task 2a):** Baton (`0008C14D`), 10mm Pistol (`00004822`), Laser Musket (`0001DACF` / Preston `00062AA6`), Minigun (`0001F669`).
  - **Row 5 (exported contract for Task 1):** Pipe Pistol & Pipe Rifle (`PipeGun 00024F55`) + `Ammo38Caliber` (`0004CE87`).
  - **Rows 6–20 (`P6` `r11-p6-arsenal`, Task 2b):** `UnarmedHuman` (`000C2C27`), Frag Grenade (`000EEBED`), Frag Mine (`000E56C2`), Pipe Revolver (`0014831B`), Hunting Rifle (`0004F46A`), Combat Shotgun (`0014831C`), Double-Barrel (`00092217`), Submachine Gun (`0015B043`), Assault Rifle (`0000463F`), Laser Gun (`0009983B`), Baseball Bat (`0008E736`), Missile Launcher (`0003F6F8`), Fat Man (`000BD56F`), Flamer (`000E5881`), Plasma Gun (`00100AE9`), Gauss Rifle (`000D1EB0`).
- **Impacts (`docs/combat/impacts.md`, Task 2c/2d):**
  - Explicit `WEAP.WVIS` (`+12..15`) on all 20 converted weapons, `EXPL.ENAM` (`+84`) on explosives, and `RACE.NAM4` only on owned `FO4SF_PowerArmorRace` (`0x0802`) (plus FO4->SF actor-material mapping table for robots & creatures).
  - **Disintegration:** Laser ash via Starfield route (`AshPile01 0009142E`, `Crit_LaserWeapDisintegrateSpell 0024EF1F`, `CritLaserDisintegration 0026319B` + FO4 `000731B2` numbers); Plasma goo via converted `GooPile01` (`00139F8D`) + `CritPlasma` (`00139F8C`) / `CritPlasmaEffect` (`00139F8B`), honoring `NoDisintegrate` (`0022DB8F`). Dismemberment deferred.

---

## 4. Round 12 Tasks 1–6 Tracker

| Item | Workstream / Owner | Status | Scope Summary |
|---|---|---|---|
| **Infra** | `@r12-infra` (`gemini/r12-infra-shared`) | **IN PROGRESS** | Frozen baseline snapshot (`r12_frozen_baseline.json` + `verify_frozen_baseline.py`), shared `scripts/probes/probe_common.py`, initial `docs/status/playable-status.md`, and R12 card template & validator (`VIDEO` column + 5-row Claude's Additions). |
| **T1** | `@r12-t1a-fixes`, `@r12-t1b-s2s6` | **IN PROGRESS** | `1a` (`2g-fix2` `F1`–`F4`/`N2`–`N4`/`M1` prep), `1b` (Vault 111 death recovery), `1i` (persistent-ref world anchors), `1c`–`1h` (`P1v2` fixes + Vault roaches `S2`, Codsworth bloatflies `S3`, Concord/display musket `S4`, museum Stimpaks/Caps/Bobby Pin/Pipe weapons, 7 raiders `S5`, 3F room + basement gate + Fusion Core `0x0809` `S6`) -> `candidate-2h`. |
| **T2** | `@r12-t2-arsenal` | **IN PROGRESS** | `P5` fixes `F1`–`F6` (`fo4_part_map`, `P-ProjectileNode`, drum bounds, `WEAP.DNAM`+`DAMA`+OMOD stats, controller side files), Rows 5–20 Arsenal, `docs/combat/impacts.md`, Laser ash & Plasma goo -> `r11-p6-arsenal`. |
| **T3** | `@r12-t3-pa-s7s9` | **IN PROGRESS** | `3a` Probe `P2` (`r11-p2-powerarmor`, `0x0801`/`0x0802`/`0x0809`, `NAM4` metal impact, Minigun activator); `3b` `S7`–`S9` (`DN092` `respawnPool=8` on `WaveRaider01`–`03`, Deathclaw `0001F15B` 3-trigger spawn, lobby reward + Sanctuary walk home `Min01 1000`) -> `candidate-2i`. |
| **T4** | `@r12-t4-whome` | **IN PROGRESS** | Host swap `w-home` (`FO4TerrainCore_Home.esm` & `FO4SFHome.esm`, `--commonwealth-weather 0`, override-reparented `0x01000802` & `0x0100E18A`), `1i` anchors, offline disassembly of `Starfield.exe +0x2540dc6` & crash-safe `pipboy_map.cpp` + `FO4SFPipboyMenu.dll` rebuild, Pip-Boy MAP slices 3–4 discovery & fast travel. |
| **T5** | `@r12-t5-start` | **IN PROGRESS** | Rebase `#842` & `#848` onto `main b2b19a03`; Warfare census (2 existing Commonwealth exterior starts); launcher `Mode`/`Survival`/`start_places`/`StartCover` wiring; `FO4SF_NewGameQuest.psc` Slot 2 direct Warfare load + Minutemen Sanctuary -> `r12-start-menus`. |
| **T6** | `@r12-t6-prewar` | **IN PROGRESS** | Phase 1 read-only FO4 `SanctuaryHillsWorld`/`PrewarVault111 000CA260`/`MQ101` census; Phase 2 (after `FO4Port` Slot 2 & `NewGameQuest` Slot 3 handoffs) lossless `PrewarVault111` append + `--codsworth-handy` + `MQ101` voices + `r11-s1-prewar`. |
| **Video** | Owner / Claude next run | **EMPTY QUEUE** | Calibration clip & next session footage (`2g-fix2`, `P1 v2`, `P5`) tracked via `REVIEW-QUEUE.md` and each R12 card's `VIDEO` column. |
