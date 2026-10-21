# v6e test queues: walk, doors, stairs (PC plan scripts)

DRAFT by the cloud thread, 2026-10-21. Not run and not dry-run. The planner hashes the staged files and writes the identities, so every queue.json is made **on the PC** by these scripts. Each `plan.ps1` plans the queue and dry-runs it. With `-Run`, it also runs the queue with the caps and reports or judges.

**Repo assumed:** main **88c5aad** (c60d9a7 on top only changes convert_batch.py, not the runner). **Installed set** (install session): FO4Port 9AF962D2, FO4TerrainCore 06C0DECD, Mars 8BBA3EE9, Raider BED4EF1A, Mission 03C2A7A8, Bridge 63C746BB. Core experiment `D:\Modding\staging\terrain_core64v6e_l125_mission_wfc11`. Starfield 1.16.244.0. The scripts check the FO4Port, core and bridge prefixes, at least 40 GB free on D:, and that the game is closed.

| Folder | sha256 of plan.ps1 | Queue(s) written | Tests | What a PASS proves | Limits |
|---|---|---|---|---|---|
| walk/ | `3054a083c090c20e8af5834243c68f26279bbd5f51eef63f9a1f37a4d9fd278c` | `D:\Modding\testqueue_v6e\walk` | 2: Red Rocket -> Sanctuary, Sanctuary -> Red Rocket | Continuous walking over the NorthBridge and cell borders on v6e's own ground. Every read is on terrain or a converted surface. No fall, block or boundary. | **2 launches, not 1.** walk_route.py marks both tests fresh (walk_route.py:1108), and a fresh relaunch is not counted by --max-relaunch (testqueue.py:3512-3518). The reverse test makes ONE setup teleport before the walk, which is not walking evidence. No save/reload. |
| doors/ | `f1e9b528fc4c0ef28fc9ff0afd7275d38e262349c780bca578b140e56dc9a09c` | `...\doors_out`, then `...\doors_rounds` | OUT legs (as v6c doors_out2), then every door IN + OUT | The load door put the player within 3 m of the other side's marker, in the right cell/world, with activation, ack and resolve proven (door-rounds.md:42-47) | v6 baseline: 5/8 OUT PASS. FAIL: Vault95 STAYED, MuseumOfWitchcraft01 16.4 m in z, PrydwenHull01 71.7 m in z (research-log.md:1457-1486). No locks, prompts, auto-load doors. |
| stairs/ | `59bf5bc42290ac5d78607f12248b0ecdd6c92b8f0ddbfc5d6cf8954e3c482c6d` | `D:\Modding\testqueue_v6e\stairs` | the 20 BostonPublicLibrary02 stairs of queues-1019 | The player climbs at least 80 % of each flight with no STUCK or FALL | Interior only. A stair that routes.py now skips is dropped from the queue (the script prints n of 20). |

## RETEST NEEDED, with the crash watcher on (owner, 2026-10-21 19:05Z)
The owner will turn the crash watcher on when they test. These runs ended without a usable result, so each one is
flagged for a retest **with the crash watcher running**. The Launcher thread is rebuilding the watcher to start and stop
with the game, with an on/off toggle in the launcher; the retest cards assume it is running. The runner side is merged
in #446 and #447, so retest on a runner checkout at or after that merge.
| Queue | What happened | Retest |
|---|---|---|
| `D:\Modding\testqueue_v6e\doors_rounds` | Starfield exited silently as 0000_terrain_FO4Core_RedRocketSpawn began (11:03:25). There was no WER event and no dump, and the watcher was off. 1 INCONCLUSIVE, 29 NOT_RUN. | All 30 tests, re-planned into a NEW queue folder |
| `D:\Modding\testqueue_v6e\walk` | Held, never run. It starts at Red Rocket, the same area as the silent exit. | Both tests |
| `D:\Modding\testqueue_v6e\stairs` | All 20 tests were INCONCLUSIVE NOCELL. The player arrived, but the HUD's O2 dial spoiled the console OCR of each arrival (fixed by #447: the arrival is read from the bridge). | All 20 tests, in a NEW queue folder |

## Run order (one queue at a time, game closed, PC idle)
1. `doors\plan.ps1`, then `doors\plan.ps1 -Run`. doors_out runs first: its legs coc into interiors, away from the Red Rocket crash area. doors_rounds runs only if doors_out ended with exit 0, no crash and no dead start. doors_rounds' IN legs start at `FO4Core_RedRocketSpawn`.
2. `stairs\plan.ps1`, then `-Run`.
3. `walk\plan.ps1`, then `-Run`. It starts at Red Rocket, where v6c crashed (the v6e bisect question).

Run command, the same in every script (testqueue.py:3876-3891; caps as campaign_arm.py's night-run caps on the launchexe branch):
`testqueue.py run --queue <Q> --wait-for-idle --refocus --max-attempts 1 --max-relaunch 1 --crash-budget 1 --min-free-gb 40 --dump-drive D:\`
- Exit 0 means every test is decided, 4 means a budget pause. Running the same command again resumes the queue.
- A queue that already has results.jsonl is resumed and is not planned again.
- To stop: create `<Q>\STOP`.

Report and judge:
- walk: `testqueue.py report --queue <Q>`. The verdict is the runner's judge (walk_eval.judge). After it, the script audits typed lines: it re-reads every `tests\*\a*\obs.json` legs[].cmds with walk_eval.py:60's whitelist (ClearConsole, `player.getpos x|y|z`, `player.setangle x|z <n>`).
- doors: `scripts\bridge\door_rounds.py judge --queue <Q>`, which writes door_rounds_judge.json, then `testqueue.py report`. If OUT legs come back INCONCLUSIVE WORLD with one runtime/plugin world pair, judge again with `$WorldPin = @('--world-instance','FF......=02......')` set to that run's pair. v6c's pair was FF00552F=02000803; it is not valid here without re-reading (door_rounds.py:341-346).
- stairs: `testqueue.py report --queue <Q>`.

## Why a teleport can never be a walk PASS (verified from source)
- walk_eval.py:433 collects every typed line of every leg that is not in the whitelist (walk_eval.py:60). Any such line makes the result INCONCLUSIVE TYPED (walk_eval.py:506): never PASS.
- A relocation the reads confirm is FAIL JUMP (more than 9 m/s, read twice).
- The only teleport is the reverse test's setup. It happens before leg 0 and is recorded under `setup`. walk-redrocket-sanctuary.md:18-20 says it is not evidence.

## Placeholders to fill at the top of each plan.ps1
| Variable | In | Value now | Fill with |
|---|---|---|---|
| `$PortStaging` | all 3 | `<FILL...>` (the script stops) | Full path of integ_v6_specmask_doors_c. It is in neither the repo nor real-records. Its FO4Port.esm must hash 9AF962D2. |
| `$Repo` | all 3 | `D:\Modding\wt_nightrun` | Supported only: from campaign_arm.py's example (launchexe branch). Use a checkout at 88c5aad or later; the script prints HEAD. |
| `$OutMinM` | doors | `<FILL: metres>` (the script stops) | doors_out2's min distance for door_out_legs.py, for a like-for-like comparison, or 0 to keep every exit |
| `$CoreBuild` | doors | the v6e core staging | The script stops unless it holds objects.json, formids.json, plan.json and overlays_params.json (door_rounds.py stage --core). If it does not, give the core build folder. |
| `$WorldPin` | doors | empty | Only after a first judge (above) |

Read from the PC, not typed:
- **Walk plugins:** the experiment folder and plugin list come from `Data\FO4SFExp.install.json` (`exp_dir`, `plugins`). They must match the pin exactly (testqueue.py install_mismatch). The record must have `pack: true`, because pre_launch passes --pack (exp_install.py:592). Reinstalling the same set is a no-op (exp_install.py:591).
- **Load indices:** from `door_rounds.py order --plugins-txt %LOCALAPPDATA%\Starfield\Plugins.txt` (door-rounds.md:33). They are used for `--core-index`/`--port-index` and `--plugin-index`. A wrong index gave NOBASE on movable_1019.

## Other pins and sources
- Python: `C:\Modding\venv-render\Scripts\python.exe` (test-queue.md:9; campaign_arm.py example).
- Starfield: `D:\SteamLibrary\steamapps\common\Starfield` (real-records INDEX.md; testqueue.py default).
- Bridge: `C:\Modding\staging\bridge_t4` (real-records FO4SFBridge.install.json `dir`).
- FO4 Data: the depot path from the install session.
- New folders written on the PC: `D:\Modding\staging\walk_core64v6e`, `doors_v6e_rounds`, `doors_v6e_out`, `stairs_bpl_v6e`.
- Commands come from: walk-redrocket-sanctuary.md:64 (walk_route.py plan); test-queue.md:504-508 (plan-walk); door-rounds.md:33-39 and door_rounds.py docstring (order/stage/plan-terrain/run/judge); door_out_legs.py:1-10,58-66; stairs-routes.md:250-253 (routes.py); test-queue.md:72-75 (plan --routes-dir).

## Game claims
- **Verified (source):** the typed-line rule, the cap flags, that a fresh launch does not count against --max-relaunch, and the v6c door verdicts (re-judged at daff232).
- **Supported:**
  - v6e still has `FO4Core_RedRocketSpawn` and the route ground walk_route.py expects (planned on core64c).
  - The save `fo4sf_test_9af962d2` exists (v6c's doors_out2 ran on build 9af962d2).
  - The 20 stairs here are the 20 that the v6 result (19 of 20 passed) counted.
- **Unresolved:** whether v6e crashes at Red Rocket, which is what walk and doors_rounds will show.
