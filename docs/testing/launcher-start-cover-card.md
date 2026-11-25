# Launcher Three-Step Strip & Start Cover Desktop Verification Card (`Round 9` / `X8`)

> **Whole Scope & Honesty (`R15`):** `Title: All Fallout titles (Fallout 4 first) | Mode: Story & Warfare (+ Survival layer) | Track: Track 1 & Track 2 shared launcher — verification card (prototype, offline)`.
> All unit tests for `X8` (`tests/test_launcher_start_cover.py` and `tests/test_launcher_gui.py`) run headlessly or against synthetic signals without ever starting `Starfield.exe`. **Neither the three-step workflow strip nor `StartCoverWindow` over a real `Starfield.exe` boot has run in a live game session yet (`pushed, not run`).**

Truth labels: **`TOOLING`**, **`TEST-STATION`**, **`OWNER TEST`**.

---

## Preconditions & Safety Invariants

1. **Default OFF:** `start_cover` defaults to `false` (`start_cover.timeout_s = 90.0`) in `src/fo4sf/launcher/settings.py`. Existing `launcher.py play`, `settings`, `crashwatch.py`, install receipts, all 6 tabs (`Locations`, `Status`, `Settings`, `Tests`, `Mod tools`, `Log`), and both themes (`DARK_PALETTE` / `LIGHT_PALETTE`) behave identically when `start_cover` is `false`.
2. **Zero Game-Log Locking:** `StartCoverController` reads and immediately closes a tiny JSON sentinel file (`%LOCALAPPDATA%\FO4SF\start_ready.json` by default, or `--signal-file <path>`), **never** tailing or holding open `Documents\My Games\Starfield\Logs\Script\User\*.log`.
3. **Zero Focus Theft / Zero Input Injection:** `StartCoverWindow` applies `WS_EX_NOACTIVATE` on Windows, never calls `focus_force()` or `grab_set()`, never sends synthetic keystrokes or mouse clicks to `Starfield.exe`, and sizes to a single monitor (`winfo_screenwidth` x `winfo_screenheight`).
4. **Crash Watcher Always Wins:** If `crashwatch` reports a stop/dump or `Starfield.exe` exits after launch before `"ready"`, `StartCoverController.poll()` closes immediately (`reason="crash_detected"` or `"game_exited"`).

---

## Step 1 — Offline Headless & Synthetic Signal Suite (Game Closed, `TEST-STATION`)

```powershell
$env:TMP = "<archive-tmp-dir>"
$env:TEMP = "<archive-tmp-dir>"
python -m unittest tests.test_launcher_start_cover tests.test_launcher_gui tests.test_launcher_alife_tools -v
python scripts/guard.py
```

- **Expected PASS:**
  - `0` failures, `guard: ok`, `Starfield.exe` `0` processes spawned.
  - Verifies: `start_cover = false` default, 3-step workflow model (`1. Locate -> 2. Build or Update -> 3. Play`), clean-room Fallout-style terminal banner (`0` Bethesda logo/music/movie references), atomic fake `"ready"` signal close, nonce mismatch rejection, hard timeout auto-close, `Cancel` button dismissal, crash-watcher override priority over `"ready"`, `Alt+Tab` topmost yield, and `WS_EX_NOACTIVATE` style flag.

---

## Step 2 — Desktop Window & Standalone Cover Dry-Run (No `Starfield.exe` Needed, `TEST-STATION`)

1. **Open the GUI and inspect the 3-step strip + 6 tabs:**
   ```powershell
   python scripts/launcher.py gui --settings "<scratch-dir>/x8_settings.json"
   ```
   - Confirm the **3-step workflow strip** (`1. Locate`, `2. Build or Update`, `3. Play`) renders cleanly between the header and the 6-tab notebook (`Locations`, `Status`, `Settings`, `Tests`, `Mod tools`, `Log`) in your current Windows theme (dark or light).
   - Click Step `1. Locate` -> selects `Locations`; Step `2. Build or Update` -> selects `Status`.
   - Open `Settings` tab -> confirm `Start cover while Starfield boots` is **unchecked (`false`)** by default, with `Start cover timeout (s)` = `90.0`.
2. **Preview the Start Cover with fake `"ready"`, `Cancel`, and timeout (zero game launch):**
   - Click **`Preview cover`** (or run the standalone preview command below in a second shell to send a fake `"ready"` signal):
   ```powershell
   # Terminal A: open standalone cover watching a scratch signal file (15 s timeout)
   python scripts/launcher.py cover-preview --signal-file "<scratch-dir>/ready.json" --timeout 15

   # Terminal B (within 15 s): emit atomic fake ready signal -> cover closes within ~0.2 s
   python scripts/launcher.py cover-signal --signal-file "<scratch-dir>/ready.json" --stage "stage20_pod_settle"
   ```
   - **PASS criteria:**
     - Terminal A prints `cover closed: reason=ready stage=stage20_pod_settle`.
     - Re-run Terminal A alone for `5 s` (`--timeout 5`) -> closes automatically at `5 s` with `cover closed: reason=timeout`.
     - Re-run Terminal A and press `Esc` or click **`Cancel / Hide cover (Esc)`** -> closes immediately with `cover closed: reason=cancelled`.

---

## Step 3 — Live PC Boot Check Over Borderless `Starfield.exe` (Claude PC Idle Window Only, `TEST-STATION`)

> **Only for Claude (PC) during an authorized desktop test session (`StarfieldPrefs.ini` `bBorderless=1`, `bFull Screen=0`):**

1. Enable `start_cover=true` and `start_cover.timeout_s=60` in your test settings JSON:
   ```powershell
   python scripts/launcher.py settings --settings "<test-settings.json>" --set start_cover=true --set start_cover.timeout_s=60
   ```
2. Launch via GUI `► Play` (with `candidate-2e` / `candidate-2f` installed).
3. **Verify all 5 live desktop checks:**
   - **Cover hides Starfield logos & main menu:** Clean-room `FO4SF // PIP-OS STANDALONE TERMINAL` cover appears on the primary monitor; secondary monitor (if attached) remains uncovered.
   - **No focus theft:** Controller / keyboard input reaches `Starfield.exe` without clicking into the game first.
   - **Ready / Cancel / Timeout:** Emitting `launcher.py cover-signal` (or pressing `Cancel / Hide cover` once Vault 111 `stage 20` draws) removes the cover cleanly with zero flicker.
   - **`Alt+Tab` safety:** Pressing `Alt+Tab` to switch to PowerShell/Explorer drops topmost so desktop windows are never trapped behind the cover.
   - **Undo:** Reset `python scripts/launcher.py settings --settings "<test-settings.json>" --set start_cover=false`.
