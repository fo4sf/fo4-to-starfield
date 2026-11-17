# PC Verification Card — Combat Core (`FO4SFCombat.esm` + `FO4SFCombat.dll`)

Target runner: **Claude (PC)** (with Starfield closed during install and rollback).
Specification: `docs/combat/combat-core.md`.

---

## 1. Stage & Offline Verify (Game Closed)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File sfse/FO4SFCombat/build.ps1 `
  -Out <SCRATCH_ROOT>/combat-sfse `
  -Lib <LIBXSE_COMMONLIBSF_DIR> `
  -Env <MSVC_ENV_PS1>

python scripts/combat/make_combat_core.py stage `
  --out <SCRATCH_ROOT>/combat-stage `
  --starfield-dir "<STARFIELD_DIR>" `
  --sfse-build <SCRATCH_ROOT>/combat-sfse

python scripts/combat/make_combat_core.py verify `
  --stage-dir <SCRATCH_ROOT>/combat-stage `
  --starfield "<STARFIELD_DIR>/Data/Starfield.esm"
```

Expected offline line:
- `PASS: verified FO4SFCombat.esm (3 outputs)` (plus `FO4SFCombat.dll` + `FO4SFCombat.ini` in `sfse_sidecar/`).

---

## 2. Install (Game Closed)

```powershell
python scripts/game/exp_install.py install `
  --exp-dir "<SCRATCH_ROOT>/combat-stage" `
  --starfield "<STARFIELD_DIR>" `
  --plugins FO4SFCombat.esm --pack
```

If testing live `V` / `N` SFSE hotkeys, copy `sfse_sidecar/FO4SFCombat.dll` and `sfse_sidecar/FO4SFCombat.ini` beside `versionlib-1-16-244-0.bin` in `<STARFIELD_DIR>/Data/SFSE/Plugins/`. (Every check below also works console-free via the firing-range pedestals and droppable slates if SFSE is omitted.)

---

## 3. In-Game Firing Range Walk (`coc FO4SF_CombatTestCell`)

1. **Draw Starter Kit:** Activate **Combat Core Weapon & Medical Supply Rack** (`-1.5, -1.5`). Equips `Grendel` (`7.77mm`), adds `Breach` (`12g Shotgun`), subtype ammo (`AP`, `JHP`, `+P`, `Slug`, `Flechette`, `Magnum`), `6x` `Wasteland Stimpak`, and `6x` `Doctor's Bag`.
2. **Step 1a — Shoot Each Silhouette Zone (Lane A):**
   - Fire one round into each of the six anatomical silhouette plates (`Head`, `Torso`, `Left Arm`, `Right Arm`, `Left Leg`, `Right Leg`).
   - **PASS lines (`FO4SFCombat.0.log`):**
     - `[FO4SF_Combat] PASS step=zone_hit zone=head mult=2.0 applied=48.0 subtype=standard`
     - `[FO4SF_Combat] PASS step=zone_hit zone=torso mult=1.0 applied=24.0 subtype=standard`
     - `[FO4SF_Combat] PASS step=zone_hit zone=left_arm mult=0.85 applied=20.4 subtype=standard`
     - `[FO4SF_Combat] PASS step=zone_hit zone=right_arm mult=0.85 applied=20.4 subtype=standard`
     - `[FO4SF_Combat] PASS step=zone_hit zone=left_leg mult=0.85 applied=20.4 subtype=standard`
     - `[FO4SF_Combat] PASS step=zone_hit zone=right_leg mult=0.85 applied=20.4 subtype=standard`
3. **Step 1c — Cycle Ammo Against High-DT Target (Lane B, `DT=18, DR=15%`):**
   - Shoot **High-DT Armored Target** once with `Standard` ammo, then press **`N`** (or activate **Ammo Subtype Cycler**) to select `AP` (`-15 DT`), shoot again, cycle to `JHP` (`2.0x target DT`), and shoot again.
   - **PASS lines (`FO4SFCombat.0.log`):**
     - `[FO4SF_Combat] PASS step=high_dt_hit subtype=standard target_dt=18.0 eff_dt=18.0 damage=4.8`
     - `[FO4SF_Combat] PASS step=ammo_cycle calibre=cal_0 slot=1 subtype=ap`
     - `[FO4SF_Combat] PASS step=high_dt_hit subtype=ap target_dt=18.0 eff_dt=3.0 damage=16.38`
     - `[FO4SF_Combat] PASS step=ammo_cycle calibre=cal_0 slot=2 subtype=jhp`
     - `[FO4SF_Combat] PASS step=high_dt_hit subtype=jhp target_dt=18.0 eff_dt=36.0 damage=7.92`
4. **Step 1a (Cripple & Cure) — Cripple Left Leg & Cure (Normal vs Hardcore):**
   - Activate **Leg-Cripple Fracture Rig** (`SpeedMult -40%` slow walk).
   - Use **Wasteland Stimpak** in Normal mode (`cured=1`); then activate **Hardcore Cure Rule Toggle**, re-trigger **Leg-Cripple Fracture Rig**, verify **Wasteland Stimpak** refuses limb cure (`cured=0`), and use **Doctor's Bag** (`cured=1`, walk speed restored).
   - **PASS lines (`FO4SFCombat.0.log`):**
     - `[FO4SF_Combat] PASS step=limb_crippled zone=left_leg speed_delta=-40.0 sway=0.0`
     - `[FO4SF_Combat] PASS step=limb_cure item=stimpak hardcore=0 cured=1`
     - `[FO4SF_Combat] PASS step=limb_cure item=stimpak hardcore=1 cured=0`
     - `[FO4SF_Combat] PASS step=limb_cure item=doctors_bag hardcore=1 cured=1`
5. **Step 1b — Toggle Slow-Time VATS & Fire Queued Limb Shot (Lane C):**
   - Face **VATS Combat Target Dummy**, press **`V`** (or drop `VATS Targeting Slate`), verify slow-time engages (`25%` time scale) and `V.A.T.S. Tactical Targeting` opens, pick **Head (2.0x Dmg, +4 AP)**, and observe queued weapon fire + normal time restoration.
   - **PASS line (`FO4SFCombat.0.log`):**
     - `[FO4SF_Combat] PASS step=vats_shot slow_time=1 zone=head ap_cost=32 chance=<5..95> queued=1`

---

## 4. Automated Log Verdict & Rollback (Game Closed)

```powershell
python scripts/combat/make_combat_core.py log --file "<USER_LOG_DIR>/FO4SFCombat.0.log"
python scripts/game/exp_install.py uninstall --starfield "<STARFIELD_DIR>"
```

`make_combat_core.py log` exits `0` with `"all_pass": true` when all four steps (`zones_pass`, `ammo_dt_pass`, `cripple_cure_pass`, `vats_pass`) pass.
