# 60-Minute Playable-Beginning Soak Card (Console-Free)

This PC card defines the 60-minute console-free stability and log soak for the playable-beginning candidate. Game control, installation, and live execution belong exclusively to the authorized PC runner or the owner.

## Safety & Save Rules

1. **Zero permanent save overwrites:** Do not overwrite any existing permanent or manual save slot during the soak. Start from **New Game** (or a dedicated disposable test profile) and exit cleanly to desktop at the end.
2. **No developer console:** Keep the tilde (`~`) console closed for all 60 minutes so input routing, quest timers, and SFSE menu hooks run exactly as an unassisted player experiences them.
3. **Logging precheck (game closed):**
   - Ensure `[Papyrus]` logging (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`) is enabled in the active profile INI.
   - Ensure the crash watcher (`launcher.py play`) or dump folder is armed before starting.

---

## 60-Minute Route Schedule

| Window | Area & Activity | Expected Slice & Quest Signals |
| :--- | :--- | :--- |
| **00–10 min** | **Vault 111 Exit:** Start a New Game, step out of the pod, activate the gear-door console, ride the exit platform to the Commonwealth surface. | `FO4SF_NewGame` runs hold-off passes 1 & 2 (`running_after=false`), advances `10 -> 20 -> 30 -> 40 -> 200` in under 300 s per stage. |
| **10–20 min** | **Sanctuary Hills:** Walk down the hill into Sanctuary, check residential interiors/exteriors, confirm keeper actor placement, cycle Pip-Boy tabs (`STAT`, `INV`, `DATA`, `MAP`, `RADIO`). | `FO4SFPipboyMenu` registers and updates cleanly (`0` `refuse step=`, `0` `fault`); keeper status lines log steady 5–6 s ticks. |
| **20–30 min** | **Red Rocket Truck Stop:** Walk south-east across the bridge to Red Rocket, inspect exterior/interior transitions and workshop bench proximity, open/close Pip-Boy map (verifying starmap block). | Cell border transitions complete without crash dumps or timer gaps `> 3x` nominal interval. |
| **30–45 min** | **Concord Encounter:** Continue south into Concord, engage the exterior raiders, clear the ambush, approach the balcony/museum arrival spot to finish the encounter. | `FO4SF_Min00` advances `10 -> 20 -> 30 -> 40 -> 200` without stalling `> 300 s` on any intermediate stage. |
| **45–60 min** | **Travel, Workshop & Squad Idle Cycles:** Rotate between Concord, Red Rocket, and Sanctuary; idle 3 minutes per stop while cycling Pip-Boy pages, workshop checks, and observing squad/keeper stability; quit cleanly to desktop at minute 60. | Steady periodic `rt=` heartbeats, `0` unexpected process exits, clean `Quit to Desktop` (`0x00000000`). |

---

## Post-Run Log Reader Command

After Starfield closes completely, generate the phone-readable summary card (and optional JSON receipt) read-only:

```powershell
python -I scripts/testing/soak_log_reader.py "<starfield-user-dir>/Logs" `
  --sfse-log-dir "<starfield-user-dir>/SFSE/Logs" `
  --crash-dir "<crash-dump-dir>" `
  --out "<scratch-output-dir>/soak-60min-report.txt"
```

For machine-readable archiving alongside the phone card:

```powershell
python -I scripts/testing/soak_log_reader.py "<starfield-user-dir>/Logs" `
  --sfse-log-dir "<starfield-user-dir>/SFSE/Logs" `
  --crash-dir "<crash-dump-dir>" `
  --json --out "<scratch-output-dir>/soak-60min-report.json"
```

---

## Acceptance Thresholds (`PASS` / `WARN` / `FAIL`)

- **`PASS` (Required for soak sign-off):**
  - `Duration >= 60m 00s` (`3600s`) and clean exit to desktop (`0` `.dmp` crash files, `0` unexpected `alive=False` or non-zero exits, `0` SFSE loader errors).
  - `0` Papyrus VM errors or missing `.pex` stores naming project scripts/records (`FO4*`, `FOCC*`), and `0` VM stack dumps / suspended-stack overloads.
  - `0` SFSE plugin `refuse step=...`, `fault`, or `[E]` error lines.
  - Hold-off passes stop active vanilla start quests with `0` `running_after=true` survivors; `FO4SF_NewGame` and `FO4SF_Min00` reach stage `200` with `0` stage stalls `> 300 s`.
  - `0` unpaused periodic timer dips `> 3x` nominal interval and `0` VM budget alerts.
- **`WARN` (Needs triage before promotion):**
  - Intermediate quest stage or A-Life waypoint stall `> 300 s` without crash.
  - Unheld vanilla start/companion quest noise in `Papyrus.0.log`, `Assigning None` warnings on project scripts, or unpaused timer spike `> 3x` nominal interval.
- **`FAIL` (Blocks sign-off):**
  - Any `.dmp` crash dump, unexpected process exit (`alive=False` without clean quit), or SFSE loader failure.
  - Any project Papyrus runtime/stack error, missing `.pex` store, or VM suspended-stack overload.
  - Any SFSE `refuse step=...`, `fault`, or `[E]` error.
  - Any held-off quest reporting `running_after=true` or an explicit `FO4SF_ALife` `result=FAIL` summary.
