# Starfield Hold Group 5 PC Card (`HoldRadiant` 9, `HoldShips` 21, `HoldSystem` 4)

## Purpose

Complete S13 row 5's cold-start quest hold-off (`docs/newgame/vault111-start.md` section 4i) on top of Group 4 (`#802`, `165` quests) by adding the final `34` holdable Starfield quests:
- **`HoldRadiant` (`9`):** `MB_Parent` (`015300`), `SQ_PlayerClearedReward` (`0394C5`), `SE_AC01` (`05B4B0`), `RE_Parent` (`05F193`), `RQ_Parent` (`08D848`), `OE_Dialogue` (`10AC08`), `SEDebug` (`160C29`), `Rad01_LIST` (`192DD7`), `RQ_Dialogue` (`1C439D`).
- **`HoldShips` (`21`):** `DialogueCrimeGuardShips` (`05BD6F`), `DialogueCrimsonFleetShips` (`063085`), `DialogueGenericCitizensShips_MuddledChatter` (`13E3C8`), `DialogueGenericGuardsShips_MuddledChatter` (`13E3C9`), `DialogueGenericVendor_LIST` (`1A2D28`), `DialogueGenericPiracyShips` (`1A5509`), `DialogueGenericSpacersShips` (`1BA199`), `DialogueGenericStarbornShips_Unique` (`20EC5A`), `DialogueShipServices` (`22E153`), `SQ_ShipVendors` (`23DE4E`), `DialogueGenericGuardsShips` (`24411E`), `DialogueGenericHouseVaruunShips` (`24411F`), `DialogueTheFirstShips` (`255EAF`), `SE_Player_Attack_SharedLines` (`261767`), `SQ_OutpostCargoLink` (`2A6C44`), `DialogueGenericCitizensShips` (`2BCB81`), `DialogueGenericEclipticANDSoldierShips` (`2BCB83`), `DialogueGenericScumShips` (`2BCB86`), `DialogueGenericStarbornShips` (`2BCB87`), `DialogueGenericUCGuardsShips` (`2BCB88`), `SQ_CargoShips` (`2CFDEC`).
- **`HoldSystem` (`4`):** `SQ_GravitationalTraits` (`07C6A9`), `SQ_Traits` (`146687`), `SQ_ApplyVoices_OBSOLETE` (`1D307F`), `LDMasterQuest` (`257DE5`).

`DefaultHold` now totals **`199` quests** (`4` non-running `MQ*` + `195` of the `207` cold-start running quests), leaving **only** the `5` Warfare boundary quests and `7` core engine quests running (`195 + 12 = 207`).

---

## Step 1 — Offline Stage, Fold into Clean Core & Verify (Game Closed)

1. Stage `FO4SFNewGame.esm` with default Group 5 holds (`199` quests):
   ```powershell
   python scripts/newgame/make_newgame.py stage `
     --out <STAGE_ROOT>/newgame-g5 `
     --fo4 <FO4_DATA>/Fallout4.esm `
     --port <PORT_DIR>/FO4Port.esm `
     --port-ids <PORT_DIR>/formids.json `
     --core <CORE_SET_DIR>/FO4TerrainCore.esm `
     --starfield <SF_DATA>/Starfield.esm `
     --compiler <PAPYRUS_COMPILER> `
     --content-resources <CONTENT_ZIP>
   ```

2. Check `<STAGE_ROOT>/newgame-g5/offline_check.txt` and `plan.json`:
   - `offline_check.txt` contains `hold 199` and ends with `check: ok`.
   - `plan.json` `options.hold` has length `199` ending with `LDMasterQuest`.

3. Prepare a clean-core hardlink copy (if `<INSTALLED_SET_DIR>` already has an older `FO4SFNewGame.esm`), fold, and verify:
   ```powershell
   python -c "
   import os, re, sys
   from pathlib import Path
   src, dst = Path(sys.argv[1]), Path(sys.argv[2])
   drop_esm = {'fo4sfnewgame.esm'}
   drop_pex = {f'data/scripts/fo4sf_newgame{s}.pex' for s in ('quest', 'looks', 'special', 'version')}
   for dp, _, fns in os.walk(src):
       out_d = dst / Path(dp).relative_to(src)
       out_d.mkdir(parents=True, exist_ok=True)
       for fn in fns:
           s = Path(dp) / fn
           r = s.relative_to(src).as_posix().lower()
           if r == 'readme.txt' or r in drop_esm or r in drop_pex:
               continue
           os.link(s, out_d / fn)
   rx = re.compile(r'(exp_install\.py install\b.*--plugins )(\S+)')
   lines = (src / 'README.txt').read_text(encoding='utf-8').splitlines()
   fix = lambda ln: rx.sub(lambda m: m.group(1) + ','.join(p for p in m.group(2).split(',') if p.lower() not in drop_esm), ln)
   (dst / 'README.txt').write_text('\n'.join(fix(ln) for ln in lines) + '\n', encoding='utf-8', newline='\n')
   " <INSTALLED_SET_DIR> <STAGE_ROOT>/clean-core

   python scripts/newgame/make_newgame.py fold `
     --stage <STAGE_ROOT>/newgame-g5 `
     --core-dir <STAGE_ROOT>/clean-core `
     --port <PORT_DIR>/FO4Port.esm `
     --out <STAGE_ROOT>/folded-g5

   python scripts/newgame/make_newgame.py verify `
     --exp-dir <STAGE_ROOT>/folded-g5 `
     --plan <STAGE_ROOT>/newgame-g5/plan.json `
     --port <PORT_DIR>/FO4Port.esm
   ```
   **Expected offline PASS line:** `verify: ok`

---

## Step 2 — In-Game Run & Two `GetQuestRunning` Batches + Controls (Claude PC Only)

1. Install `<STAGE_ROOT>/folded-g5` via `scripts/game/exp_install.py` and start a fresh **New Game** (*Quick start* or *Create character*).
2. Once `stage 20` is reached inside Vault 111 (and again after reaching `stage 200` + ~3 minutes on the Commonwealth surface), run the two Group 5 `GetQuestRunning` batches and the controls batch in the console:

### Batch 1 (`17` Group 5 Quests: `HoldRadiant` 9 + `HoldShips` first 8 — every line must print `>> 0.00`)
```text
GetQuestRunning 015300
GetQuestRunning 0394C5
GetQuestRunning 05B4B0
GetQuestRunning 05F193
GetQuestRunning 08D848
GetQuestRunning 10AC08
GetQuestRunning 160C29
GetQuestRunning 192DD7
GetQuestRunning 1C439D
GetQuestRunning 05BD6F
GetQuestRunning 063085
GetQuestRunning 13E3C8
GetQuestRunning 13E3C9
GetQuestRunning 1A2D28
GetQuestRunning 1A5509
GetQuestRunning 1BA199
GetQuestRunning 20EC5A
```

### Batch 2 (`17` Group 5 Quests: `HoldShips` remaining 13 + `HoldSystem` 4 — every line must print `>> 0.00`)
```text
GetQuestRunning 22E153
GetQuestRunning 23DE4E
GetQuestRunning 24411E
GetQuestRunning 24411F
GetQuestRunning 255EAF
GetQuestRunning 261767
GetQuestRunning 2A6C44
GetQuestRunning 2BCB81
GetQuestRunning 2BCB83
GetQuestRunning 2BCB86
GetQuestRunning 2BCB87
GetQuestRunning 2BCB88
GetQuestRunning 2CFDEC
GetQuestRunning 07C6A9
GetQuestRunning 146687
GetQuestRunning 1D307F
GetQuestRunning 257DE5
```

### Controls Batch (`12` Protected Running Quests = `>> 1.00`; `5` Prior-Group Held Quests = `>> 0.00`)
```text
; --- 5 Warfare boundary quests (MUST ALL READ >> 1.00) ---
GetQuestRunning 00D773
GetQuestRunning 1A9565
GetQuestRunning 0709A7
GetQuestRunning 1D3081
GetQuestRunning 046617
; --- 7 Core engine quests never to stop (MUST ALL READ >> 1.00) ---
GetQuestRunning 0174A2
GetQuestRunning 07092C
GetQuestRunning 2C59E4
GetQuestRunning 05C8C4
GetQuestRunning 010B4B
GetQuestRunning 0128D0
GetQuestRunning 29E183
; --- 5 Prior-group held controls (MUST ALL READ >> 0.00) ---
GetQuestRunning 248D20
GetQuestRunning 009E99
GetQuestRunning 012996
GetQuestRunning 24AFED
GetQuestRunning 01E3F9
```

---

## Step 3 — PASS Criteria & Narrowing Fallback

- **PASS:**
  1. `python scripts/newgame/make_newgame.py log` exits `0`; `fo4sf_newgame.0.log` records `HoldOffPass` stopping `196` of `199` quests across pass 1 + pass 2 (`195` cold-start running quests + `MQ00`; `MQ101`, `MQ101PostQuest`, `MQ_TutorialQuest_Misc04` never started), with `0` still running after pass 2.
  2. All `34` quests in Batch 1 and Batch 2 print `GetQuestRunning >> 0.00` at both `stage 20` and `stage 200 + 3 min`.
  3. All `12` protected quests (`5` Warfare + `7` core engine) print `GetQuestRunning >> 1.00`, and all `5` prior-group held controls print `>> 0.00`.
  4. HUD/damage audio/follower follow-wait commands work normally, with `0` crashes and `0` Starfield quest popups.
- **Narrowing if anything breaks:** Re-stage using `--omit-hold-group` (`system` = `195` quests, `ships` = `178` quests, or `radiant` = `190` quests — `DEFAULT_HOLD` minus that single Group 5 list) to isolate the responsible subset in one run:
  ```powershell
  # Omit HoldSystem (4):
  python scripts/newgame/make_newgame.py stage --out <STAGE_ROOT>/newgame-nosystem --omit-hold-group system --fo4 <FO4_DATA>/Fallout4.esm --port <PORT_DIR>/FO4Port.esm --port-ids <PORT_DIR>/formids.json --core <CORE_SET_DIR>/FO4TerrainCore.esm --starfield <SF_DATA>/Starfield.esm --compiler <PAPYRUS_COMPILER> --content-resources <CONTENT_ZIP>

  # Omit HoldShips (21):
  python scripts/newgame/make_newgame.py stage --out <STAGE_ROOT>/newgame-noships --omit-hold-group ships --fo4 <FO4_DATA>/Fallout4.esm --port <PORT_DIR>/FO4Port.esm --port-ids <PORT_DIR>/formids.json --core <CORE_SET_DIR>/FO4TerrainCore.esm --starfield <SF_DATA>/Starfield.esm --compiler <PAPYRUS_COMPILER> --content-resources <CONTENT_ZIP>

  # Omit HoldRadiant (9):
  python scripts/newgame/make_newgame.py stage --out <STAGE_ROOT>/newgame-noradiant --omit-hold-group radiant --fo4 <FO4_DATA>/Fallout4.esm --port <PORT_DIR>/FO4Port.esm --port-ids <PORT_DIR>/formids.json --core <CORE_SET_DIR>/FO4TerrainCore.esm --starfield <SF_DATA>/Starfield.esm --compiler <PAPYRUS_COMPILER> --content-resources <CONTENT_ZIP>
  ```
