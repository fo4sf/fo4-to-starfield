# Launcher Mod Tools (`X5`) & UI Polish (`X6`) Verification Card

> **R15 Honesty / Status Banner (21 Nov 2026)**
> - **Offline proof only:** Unit tests (`tests/test_launcher_alife_tools.py`, `tests/test_launcher_gui.py`, `tests/test_launcher_no_syntax_warnings.py`), the 107 A-Life SDK tests (`tests/test_alife_*.py`), a real 5-step `scripts/alife/build_alife_mod.py` CLI package + `verify-dist` run into a scratch folder outside Git and outside the game folder, and a window-only Tkinter preview render (saved privately outside Git) have passed offline.
> - **UNPROVEN IN GAME / PENDING PC INTERACTIVE CHECK:** Interactive desktop layout inspection, real-PC button clicks inside the launcher's `"Mod tools"` tab, live Windows `AppsUseLightTheme` toggle visual check, and any in-game loading of a packaged A-Life mod remain **Claude (PC)** checks. Nothing in this card starts `Starfield.exe` or writes into the Starfield installation folder.

## Scope

- **`X5a` (`gemini/alife-standalone-mod`, Draft PR #841):** Standalone Starfield A-Life Mod & Modder SDK (`src/fo4sf/alife/`, `scripts/alife/build_alife_mod.py`, `scripts/alife/FO4SF_ALife*.psc`, `dotnet/ALifeMod/`, `docs/alife/`, `tests/test_alife_*.py`).
- **`X5b` (`src/fo4sf/launcher/alife_tools.py` + `"Mod tools"` tab in `src/fo4sf/launcher/gui.py`):**
  - `ModToolsModel` + `StepRunParser` in `src/fo4sf/launcher/alife_tools.py` (pure stdlib, zero `tkinter` import).
  - `ModToolsSession` + `"Mod tools"` tab in `src/fo4sf/launcher/gui.py`, invoking `scripts/alife/build_alife_mod.py` via `run_command(..., cwd=repo_dir)` on a worker thread with live stdout/stderr streaming into the `Log` tab, no shell, and every path passed as a separate argv element.
  - Controls for `init` (`vanilla` or `custom` template picker, output folder + `Browse…`, optional `Overwrite config`), `validate`, `simulate` (`Ticks` and `Seed` fields + `ttk.Treeview` faction summary table), `package` (reads Starfield folder from saved `Locations`, refuses Git checkouts and Starfield/game folders, optional `Pack .ba2 archive` checkbox), `verify-dist`, and one `Open output folder` button (`os.startfile` on Windows only after verifying the folder exists).
  - Each of the 5 steps renders as a row with a status mark (`○ not run`, `◐ running`, `✓ passed`, `✗ failed`), a step progress bar, plus an overall `0..5` progress strip and live key numbers (`nodes N/128`, `spawns`, `battles`, `captures`).
- **`X6` (Launcher UI Polish in `src/fo4sf/launcher/gui.py`):**
  - `DARK_PALETTE` (preserving the existing `#0d1117` / `#161b22` / `#58a6ff` terminal palette and `MONO` font) + high-contrast `LIGHT_PALETTE` selected automatically via `detect_windows_light_theme(reg_reader=...)` reading Windows `AppsUseLightTheme` (`apply_theme(root, ttk, tkfont, *, light=None)`).
  - Monospace tab marks (`TAB_MARKS` / `tab_label`) across `Locations`, `Status`, `Settings`, `Tests`, `Mod tools`, and `Log` (plus `Play`).
  - Read-only top header strip (`format_header_state`) displaying live Starfield process state (`Game: checking` / `closed` / `running`) and crash-watcher / recovery state (`Watcher: off` / `armed` / `setup needed`, `Recovery: needed`) in `ok` / `warn` / `bad` / `muted` tones.
  - Improved spacing and larger hit targets (`TButton` `padding=(14, 7)`, `TNotebook.Tab` `padding=(16, 8)`, padded entries and card panels).
  - First-run checklist panel (`first_run_checklist`) on the `Locations` tab tracking confirmation status of `Fallout 4 Data`, `Starfield`, and `My Games`.
  - Dismissible, auto-updating readable error banner (`format_error_banner`) stripping raw Python tracebacks while preserving full raw output in the `Log` tab.
  - Zero behaviour change to `Play`, `Settings`, `Locations`, `Tests`, `Recover install`, or the crash watcher.

## Automated Offline Proof Commands

Run from the repository root (no game launch, no writes into Git or game folders):

```powershell
python -m unittest tests.test_launcher_alife_tools tests.test_launcher_gui tests.test_launcher_no_syntax_warnings
python -m unittest tests.test_alife_sdk_schema tests.test_alife_runtime_psc tests.test_alife_mod_writer tests.test_alife_mod_packager
python scripts/guard.py
```

Expected:
- `tests/test_launcher_alife_tools.py` (`11` tests) + `tests/test_launcher_gui.py` (`48` tests) + `tests/test_launcher_no_syntax_warnings.py` (`1` test): `Ran 60 tests ... OK`, covering:
  - AST check confirming `src/fo4sf/launcher/alife_tools.py` never imports `tkinter`, and subprocess check confirming `import fo4sf.launcher.gui` + `launcher.py gui --help` run with `tkinter` blocked.
  - Windows light/dark theme detection (`detect_windows_light_theme`), `LIGHT_PALETTE` / `DARK_PALETTE` parity, and headless `apply_theme` hit-target and style assertions.
  - Header game + watcher/recovery state formatting (`format_header_state`), `Locations` first-run checklist (`first_run_checklist`), and traceback-free readable error banners (`format_error_banner`).
  - Argv construction and `ModToolsSession` worker execution (`run_command(..., cwd=repo_dir)` with no shell), `not_run -> running -> passed/failed` transitions, live key numbers (`nodes N/128`, `spawns`, `battles`, `captures`), `simulate` faction table rows, Git-checkout and Starfield-folder output refusal (`0` subprocesses spawned on refusal), and `Open output folder` validation.
  - Real 5-step subprocess pipeline (`init` -> `validate` -> `simulate` -> `package` -> `verify-dist`) into a temporary folder outside Git and outside the game folder, plus real-Tk subprocess window tests (`GuiWindowTests`).
- `tests/test_alife_*.py`: `107` tests `OK`.
- `python scripts/guard.py`: `guard: ok`.

## Claude (PC) Interactive Verification Checklist

Prerequisites: `Starfield.exe` is NOT running. Confirm `Locations` points to the read-only Starfield folder on this PC.

1. **Open the Launcher Window (`python scripts/launcher.py gui`):**
   - Verify the window opens cleanly with no console traceback.
   - Confirm the top header strip shows live game state (`● Game: closed`) and crash-watcher state (`○ Watcher: off` or `● Watcher: armed (...)`).
   - Confirm all 6 tabs render with monospace marks (`⌂  Locations`, `●  Status`, `≡  Settings`, `◊  Tests`, `♦  Mod tools`, `▸  Log`) and comfortable button/tab hit targets.
   - Confirm the `Locations` tab displays the first-run checklist (`Fallout 4 Data`, `Starfield`, `My Games`).
   - Confirm the light/dark palette matches Windows `AppsUseLightTheme` with clear contrast.
2. **Safety Refusal Check (`Mod tools` tab):**
   - Set **Output folder** to a path inside this Git checkout and click **Init** or **Package** -> expect the readable error banner refusing output inside a Git checkout (no traceback, nothing written) and verify `× Dismiss` hides the banner.
   - Set **Output folder** to a path inside the Starfield game folder and click **Init** or **Package** -> expect the readable error banner refusing output inside the game folder (no traceback, nothing written).
3. **Real 5-Step Package Run (`Mod tools` tab):**
   - Choose a fresh scratch output folder outside Git and outside the Starfield folder.
   - Select template `vanilla`, ticks `200`, seed `42`. Leave `Pack .ba2 archive` unchecked (or test a second fresh folder with `Pack .ba2 archive` checked).
   - Run **Init** -> row mark turns `✓ passed`, progress updates `1/5 steps passed`, `nodes 16/128` appears, live output streams into `Log`.
   - Run **Validate** -> row mark turns `✓ passed`, progress `2/5 steps passed`, `nodes 16/128`.
   - Run **Simulate** -> row mark turns `✓ passed`, progress `3/5 steps passed`, key numbers (`nodes 16/128`, `spawns`, `battles`, `captures`) update, and the `ttk.Treeview` simulation table populates with per-faction rows (`uc_security`, `spacers`, `ecliptic`).
   - Run **Package** -> row mark turns `✓ passed`, progress `4/5 steps passed`, builds `<output>/dist/Data/StarfieldALife.esm` + compiled `.pex` scripts (or `.ba2` when checked) reading Starfield read-only from saved `Locations`.
   - Run **Verify dist** -> row mark turns `✓ passed`, progress `5/5 steps passed`, reports `verify-dist: ok` in `Log`.
   - Click **Open output folder** -> opens the output folder in File Explorer.
4. **Regression Check (No Behaviour Change):**
   - Confirm `Play`, `Settings`, `Locations`, `Tests`, and `Recover install` controls behave identically to `origin/main` (do not launch `Starfield.exe` unless performing a separate game session).
