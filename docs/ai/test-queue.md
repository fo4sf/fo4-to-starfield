# Queued game-test runner

Purpose: collect in-game evidence while no AI agent is running (usage limits, nights), so the next session starts from
results and a ranked problem list instead of spending its own time driving the game. Nothing in the loop calls a model.

## Use

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
# 1. plan: one pinned build (staging folder with FO4Port.esm, manifest, formids, cell exports, routes_<cell>.json)
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\<build> --out C:\Modding\testqueue\<batch> --per-cell 12
# 2. run (resumable: run the same command again to continue)
& $py scripts\game\testqueue.py run --queue C:\Modding\testqueue\<batch> --wait-for-idle --refocus --max-hours 8
# 3. read
& $py scripts\game\testqueue.py report --queue C:\Modding\testqueue\<batch>
```

Stop it at any time: create the file `C:\Modding\testqueue\<batch>\STOP` (or `%LOCALAPPDATA%\fo4-ai-team\state\testqueue.STOP`
for every batch), or `python tools\ai-team\guardian\guardian.py pause` / `stop`. Using the keyboard or mouse, or putting
another window in front of the game, also stops it (or makes it wait for an idle PC with `--wait-for-idle`).

## What it tests (owner's priority order)

| kind | from | PASS | FAIL | INCONCLUSIVE |
|---|---|---|---|---|
| stairs | `routes_<cell>.json` (routes.py) | rose at least 80% of the flight | STUCK, FALL | start not reached, misread |
| fall | `probe_points.py` floor points | landed within 0.6 m | dropped more than 3 m | landed 0.6-3 m lower, held above, pushed away |
| door | `routes_<cell>.json`, both sides | crossed the plane after an OPEN this attempt | BLOCKED, NOPROMPT, FALL | already open, misread |
| movable | manifest `movable` items placed in the cell | item moved at least 5 cm when walked into; with `--impulse`: PASS IMPULSE when only the impulse moved it | did not move although reached (NOTMOVED); STUCK (no impulse moved it either); fell | player missed it; ELEVATED (more than 0.5 m above the player's feet: on furniture; final) |
| movable_control | `plan-movable` (plan.json, below) | the item placed in a vanilla cell moved when walked over (WALKED) or only under ApplyHavokImpulse (IMPULSE) | STUCK, NOTMOVED, ITEMFELL | start, spawn handle, SetRigidBodyMass refused, the item not at rest before the walk (SETTLE), missed, a read missing |
| travel | load doors whose XTEL partner is in the same build | arrived within 4 m of the arrival point | no prompt; E did nothing | start not reached, arrived elsewhere |
| terrain | `plan-terrain` (an experiment's plan.json) | heights within 0.5 m | NOTERRAIN, HEIGHTS | a height not read, moved |
| npc_nav | `plan-npc` (plan.json, below) | the actor walked to B (a baseline: stayed away without a command); with `combat_reads`: ENGAGED, in combat with the player | NONAV, STALLED, FELL, WANDER; NOCOMBAT | spawn / handle / reads failed, warp or early arrival, control or precondition not met; combat replies unreadable |
| door_trip | `plan-door` (plan.json, below) | walked through a load door into an interior and back, saved and loaded, every arrival read where expected (frame and, when planned, facing) | NOLOAD, UNMERGED, REMERGED, WRONGCELL, ELSEWHERE, FELL, RELOAD, OFFGROUND, FACING | offset, start, a read, the door not reached (NOREACH), loaded only from the last try (NEARONLY), no known frame (ELSEWHERE), a heading not read (NOFACING), the save file or the reload not seen |

Every verdict needs its observations: a position that was not read or a screenshot that is missing makes the test
INCONCLUSIVE, never PASS. INCONCLUSIVE tests are retried once more at the end of the queue (`--max-attempts 2`); a FAIL
is final. A game crash during a test is recorded (class CRASH) and the game is relaunched (at most `--max-relaunch`).

### Stairs routes (`routes.py`, 2026-10-13; amended after QA on PR #111)

`routes.py` keeps a stairs route only when an offline walk (`src/fo4sf/walksim.py`, a 0.35 x 1.8 m capsule over FO4's
own collision of the stair and its neighbours) stands free at the start and climbs at least 80 % of the flight; it tries
lanes across the flight and closer starts, takes a lane that would touch a movable object last, ends the walk 0.6 m
past the top (less when a drop is that close), plans no flight that rises less than 0.2 m, and skips a stair with no
such lane with the reason (`skipped_stairs_without_ramp`, per stair in `stairs_checked`). Route entries carry `lane`,
`sim_end` (where the offline walk ended), `emerges`, `tight` (a lane that fits only the bare capsule),
`helper_crossing` (the walk meets a converted stair helper coming up through the floor, moved from FO4's: batch_full
0002 / 0003 stopped at such a place, cause unresolved) and `movable_near`; the runner and the judge ignore them.
`--probes-out` writes probes for each route with a helper crossing (`probe`: `through_crossing`, `runup`,
`past_crossing`). Why and what the probes decide: [docs/testing/stairs-routes.md](../testing/stairs-routes.md).

Routes planned again for the same pinned build (a newer `routes.py`) live in their own new folder; plan from it
without copying or rebuilding the build, so the plugin hash, save and deploy stay the pinned build's:

```powershell
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\integ_1011 --out C:\Modding\testqueue\<batch> `
  --kinds stairs --routes-prefix routesfull_ --routes-dir C:\Modding\staging\stairs_fix_1014 [--first 0EBEDE,0EBEE3] [--refs ...]
```
The queue copies the route files it uses into `<queue>\routes`, points each test's `routes_file` there and records
`routes_dir` and `routes_sha256` in `queue.json`: re-planning the routes folder cannot change how a planned queue runs
or is judged. `--refs A,B` keeps only those references' tests (in that order); `--first A,B` runs them first.

`scripts/game/stairs_calib.py results --queue <queue> [--queue ...] --staging <build> --fo4-data <FO4 Data>` replays a
queue's decided stairs results with the offline walk and counts a stop as agreeing only at the same place;
`stairs_calib.py routes --routes-dir <dir> ...` replays route files (a consistency check: the planner keeps only lanes
the walk climbs).

## Controls (checked before every launch and every test)

- STOP file, Resource Guardian mode (`paused` / `stopped`, or an unreadable database) stop the run.
- The game is launched only after `--min-idle` seconds (default 900) without keyboard or mouse input, and only through
  `cycle.ps1`. A Starfield the runner did not start (the owner's own session) is never touched: the run stops.
- Owner activity: input the runner did not send, or another window in front of the game, stops the run (or waits with
  `--wait-for-idle`; with `--refocus` it then brings its own game window back to the front once, never another app).
  Every step runs with `FO4SF_NO_FOCUS_STEAL=1`, so `input.ps1` refuses to pull the game in front during a test.
- `queue.json` `"hours"` limits the allowed hours (default `[[0, 24]]`); `--max-hours` and `--max-tests` bound a run.
- The build is pinned: `queue.json` records the SHA-256 of `FO4Port.esm`; the runner will not launch a staging folder
  whose plugin changed. The dedicated save `fo4sf_test_<build id>` is created on the first launch and loaded on later ones. After god mode the
  session disables the save's companion (Vasco, Starfield.esm ACHR `000057BE`; qstep kind `companion_off`, confirmed by
  `GetDisabled >> 1`): it stood in front of FortHagen01's load door (NOPROMPT, 2026-10-12) and in every NPC sample shot.
  The save itself is not changed; queue.json `"companion": "keep"` leaves the companion.

## Output (in the queue folder)

`queue.json` (tests, build, save), `state.json` (checkpoint), `results.jsonl` (one line per attempt), `run.log`,
`tests/<id>/a<n>/` (spec, raw `obs.json`, screenshots, step log), `report.md` / `report.json` (tally per kind and the
ranked problem list: FAIL groups by severity x count, then INCONCLUSIVE groups). Tests planned with an `"expect"`
(npc_nav) get a section "Expectations written before the run": expected verdict, result, as expected yes / no, basis.

## Time of day and weather (`terrain`, `npc_nav`)

Where an overlay worldspace is registered on Mars decides the time of day of the arrival (the runner always loads the
same save). C:\Modding\testqueue, 2026-10-11, 31 Mars arrivals (read-only): every arrival at the raw PNDT `CNAM` pair
(0.3, -1.2) was at night (exp2b, exp2b2, exp2b3, exp2c, exp2d and core64: 18 of 18), every arrival at (0.2, 1.2) in
daylight (exp1_mars, exp1b_mars, exp1c_mars, exp1d, terrain_B_w01 and exp3 at (0.2008..0.2012, 1.1989..1.1993): 13 of
13). PR #70's exp2t variants (commit 5f09a1d) therefore moved their registration to (0.2, 1.2) to be judged in daylight;
the night site is still where core64, exp2b2 and the NPC runs on it are. A test can ask for a local time of day and/or a
weather; the step sets them right after the arrival, before any other screenshot, and records the light before and
after (and on every terrain probe shot), so the judge can tell a daylight run from one where the commands changed
nothing, and from one that was in daylight anyway (then the commands were not tested).

| plan.json field (per test) | meaning | default |
|---|---|---|
| `time_of_day` | local hour on the planet, 0 <= h <= 23.99 after rounding to two decimals (12 = noon on every planet, whatever its day length); `true` / `false` are refused | none |
| `time_methods` | ladder of time commands, tried in order until the sky reads as asked: `slt` (`SetLocalTime <h>`), `slt_galaxy` (`SetLocalTime <h> 1`), `cgf` (`cgf "Game.SetLocalTime" <h>`) | all three, in that order |
| `time_repin` | terrain: type the command that worked again before every probe (in the probe's teleport session), so the probes stay at the asked hour while game time runs | true |
| `weather` | weather form id (8 hex digits), typed `fw <id>` before the time | none |
| `weather_lock` | `fw <id> 1`: the weather stays until `rwo` (ReleaseWeatherOverride) | false |
| `light_wait_ms` | wait with the console closed after each command, before its screenshot (and again before a second shot) | 4000 |
| `need_daylight` | a PASS whose run did not read as daylight becomes INCONCLUSIVE `NIGHT`, or `LIGHT` when nothing was read; both are retried up to `--max-attempts` (another arrival of the same test can read differently: exp1d a1 fell into a pit, sky 7.3, a2 read 131.0) and `NIGHT` does not count towards the circuit breaker. A FAIL stays a FAIL | false |

The same for every test of a queue from the command line (it wins over plan.json):

```powershell
& $py scripts\game\testqueue.py plan-terrain ... --time-of-day 12 [--time-methods slt,cgf] [--weather <id>] [--need-daylight]
& $py scripts\game\testqueue.py plan-npc ... --time-of-day 12
```

`plan-terrain` / `plan-npc` validate the fields (`sky_light.light_fields`: hour range after rounding, the three method
names, 8 hex digits, booleans) and `qstep.ps1` checks them again before the travel (exit 4, nothing typed); nothing else
from these fields is ever typed.

What the step does (`qstep.ps1` `Apply-Light`): the arrival's own screenshot is the "before" sky (terrain: `spawn.png`
after the arrival read; npc_nav: `arrival.png` after the arrival settled). Then the weather command, then the time
ladder. Each command has its own console session: typed, the console captured and OCR'd (`sky_<k>_console.png`, so a
refused command such as "SetLocalTime only works on a planet." is told apart from one without a visible effect), closed;
then `light_wait_ms`, a screenshot `sky_<k>.png` and its sky. A time command whose shot does not read as the requested
hour gets a second shot after another `light_wait_ms` (`sky_<k>_late.png`), so a slow change is credited to the command
that made it and not to the next one. The ladder stops at the first command after which the sky reads as the requested
hour (`sky_light.done`: daylight for 7..17 h, night before 5 or after 19 h, any change of at least 15 in between).
Terrain then types that command again before every probe (`time_repin`) and measures every probe shot. `obs.json`
`light`: `time_of_day`, `weather`, `before` {`shot`, `sky`}, `tries` [{`method`, `cmd`, `ocr`, `console`, `shot`, `sky`,
`class`, `done`, and `shot_late` / `sky_late` when taken}], `repin`; every terrain point gets `sky`, `corners` and
`repin`.

Light measures (`sky_light.py measure <png>`, the two measures of `scripts/terrain/ground_textures.py lighting`, PR #70):
`sky` = the mean RGB value (0..255) of the top 200 rows (the arrival camera); `corners` = the mean of the top fifth's
outer quarters (ground away from the helmet lamp: the probe shots). The 31 Mars arrivals above, by site:

| reading | night site (18) | daylight site (13) | threshold |
|---|---|---|---|
| arrival camera `sky` (spawn.png) | 6.4..19.9, and core64 41.1, 44.3 | 7.3 (exp1d a1, a pit), 49.9 (exp3 0003), 96.4, 103.0..131.6 | night <= 30, daylight >= 60 |
| median of the probe shots' `corners` | 6.7..37.0 | 47.5..154.4 | night <= 40, daylight >= 45 |

The arrival camera alone misreads 4 of 31 (two daylight arrivals as night / unclear, two night arrivals as unclear);
the probe-corner median separates all 31 (single probe shots do not: they range 6.4..61.4 at night and 33.6..170.9 by
day). So the run's light is the probe-corner median when probes were measured (terrain) and the arrival camera's last
reading after the commands otherwise (npc_nav). The thresholds sit between the groups: a heuristic, not a calibration.

Judge (`sky_light.verdict`): the light goes into the detail of every test that asked for it, e.g.
`[light: local hour 12: sky 12.3 -> 110.2 after SetLocalTime 12; daylight after SetLocalTime 12; probes: 18 measured,
corner median 96.0 -> daylight => daylight]`, `[light: local hour 12: sky 12.3 -> 12.4 after SetLocalTime 12;
SetLocalTime 12 1; cgf "Game.SetLocalTime" 12 (console: SetLocalTime 12: SetLocalTime only works on a planet; ...); no
effect: night; probes: ... -> night => night (asked for daylight)]` or `[light: local hour 12: sky 110.0 -> 112.0 after
SetLocalTime 12; already daylight at the arrival: the time commands were not tested => daylight]`. A shaded arrival
camera with daylight probes says "(the arrival camera read night: the probes decide)" and "whether the commands acted
is unknown". `results.jsonl` gets `light` (`daylight`, `night`, `unclear`, `unread`), `sky` [before, after],
`light_tested` (false: already as asked at the arrival), `light_credited` (the command after which the sky first read
as asked), `light_probes` {`n`, `corners`, `class`, `night`, `unclear`} and `light_detail`; `report.md` / `report.json`
get a section "Light" with the same columns. The step timeout grows by 50 s + 2 x `light_wait_ms` per command the test
may type, and for terrain by 4 s per probe (its measure) plus 8 s per probe with `time_repin`.

`ground_textures.py lighting` (PR #70) still classifies an attempt from `spawn.png`, taken before the time is set; for a
queue with `time_of_day` read `results.jsonl` `light` / `light_probes` instead (**unresolved** on #70's branch, not
changed here).

### A queue needs a runner that has these features

The unattended chain runs `testqueue.py run` from the integration worktree. A runner without this branch ignores test
fields it does not know, so a queue with `time_of_day` or `console_pre` would run at night without the commands and
without a word. Therefore:

- `plan-terrain` / `plan-npc` write `"needs"` into `queue.json` (`runner_features.needs`: `light` for a time of day or a
  weather, `console` for `console_pre` / `console_post`, `npc_t0` for an npc_nav `precommand_m` / `arrive_progress`:
  an older runner would judge such a queue by `min_progress` alone; `door_trip` for the kind, `door_check` for a
  door_trip test with `moved_m` / `activate_m`: the first door_trip runner could teleport after a load it did not see
  and judge NOLOAD from 5 m; `door_frames` for `reads: strict` (every door_trip test planned since 2026-10-13: strict
  reads, no load from one read, GetInCell not judged, facing, probes); `door_route` for a walked route), and the
  runner refuses a queue whose needs its checkout lacks
  (`runner_features.FEATURES`; run.log "stopped: this queue needs runner features ...", status "stopped: runner lacks
  ...", exit 3, nothing launched). It also notes in run.log when the queue was planned at a commit its checkout does not
  contain.
- `pre_launch` runs the RUNNER's own `scripts\game\exp_install.py` (a path relative to the runner's checkout; testqueue.py
  starts it there) with `--needs light,console`; a queue without plugins gets `scripts\game\runner_features.py check
  <needs>` instead. A runner from before this branch has an `exp_install.py` without `--needs`, which refuses the
  option (argparse, exit 2), so its `ensure_game` stops at "pre-launch exit 2" before launching the game (verified
  offline against the integration worktree at dcf8ad6, 2026-10-12). In the chain a required queue that stops this way
  stays first in `chain_queue.txt` and ends the chain; an optional one (`?name`) is skipped.
- Planning itself: a planner from before this branch refuses `--time-of-day` ("unrecognized arguments"), so the queue
  commands below carry `--time-of-day 12` even where plan.json has it.

So: merge this branch into the checkout the chain runs from, then plan from it and queue.

### Research: which command changes the local time on a planet (2026-10-11, offline, read-only)

Sources: the installed `Starfield.exe` 1.16.244.0 (command entries decoded as in `scripts/recon_console.py`; the ones
below are built on the stack, so they were read from their initialiser bytes), the Creation Kit's Papyrus sources in
`Tools\ContentResources.zip` (`Scripts/Source/*.psc`), a raw scan of `Starfield.esm` and Mutagen 0.55's PNDT decoding.

- **verified** (command entry decoded): `SetLocalTime`, short name `slt`, opcode 0x2D3, help "Sets the local time on the
  current planet, optionally updating the galaxy sim.", parameters `Local Time` (Float, required) and `(Optional) 1 to
  update Galaxy sim` (Integer, optional). Next to it: "SetLocalTime only works on a planet." It sits among the weather
  test commands (`TestAllWeathers` / `taw`, `TestClimateWeatherTransitions` / `tcwt`).
- **verified** (Papyrus source text): `Game.psc` "Rotates the current planet such that the local time will match the
  specified time" `Function SetLocalTime(float afLocalTime) native global`; `float Function GetLocalTime()` "Get the local
  time in normalized 24-hour day scale for this planet"; `Function PassTime(int aiHours)` "Pass time as if the player has
  waited the given number of hours". `Planet.psc` `float Function GetDayLength()` "the day length in hours".
  `Utility.psc` `GetHoursUntilLocalHour`: `Game.GetLocalTime()` "returns local time normalized to 24 hours, so 12 always
  = noon"; real (universal) hours until a local hour = local hours x day length / 24; off a planet, the time of day is
  the fraction of `GameDaysPassed` x 24.
- **supported hypothesis** that `SetLocalTime` changes the sky at once: Bethesda's own scripts use it for staged
  arrivals: the opening quest's fragment (`QF_MQ101_00003448.psc`) calls `Game.SetLocalTime(10)`, `(9)`, `(11.5)`, `(8)`;
  `SFBGS00D:OnLoadSetLocalTime` sets daytime on load when the local time is past evening. Whether the console form needs
  the galaxy-sim flag, and whether `cgf` reaches the native (CallGlobalFunction, short name `cgf` by string adjacency:
  "Calls a global papyrus function. First parameter is the function, the rest are parameters"), is **unresolved**: hence
  the ladder `slt`, `slt_galaxy`, `cgf`.
- **verified** (entries decoded): `PassTime` (one Integer, "Passes the given number of hours as if the player were
  sleeping."); `ForceWeather` / `fw` (opcode 0x112D, "Forces the active weather to the specified type, without
  transition.", parameters Form and an optional Int), `SetWeather` / `sw` (0x1104, two parameters),
  `ReleaseWeatherOverride` / `rwo` (0x1158, none). `PassTime` is not in the ladder: it moves the universal clock by whole
  hours, and which local hour that reaches depends on the local time, which the step cannot read yet.
- `Starfield.esm` globals (raw scan, FLTV): `GameYear` 00000035 = 330, `GameMonth` 00000036 = 5, `GameDay` 00000037 = 7,
  `GameHour` 00000038 = 8.0, `GameDaysPassed` 00000039 = 0, `TimeScale` 0000003A = 20 (**verified**). The exe also has the
  settings `fCalendarTimeScaleGround` / `fCalendarTimeScaleSpace`. `set gamehour to <h>` writes the universal clock, not
  the planet's rotation; whether the sky follows it is **unresolved** and it is not in the ladder. Community guides
  give only waiting, sleeping and the time scale: [dexerto](https://www.dexerto.com/starfield/starfield-how-to-change-the-time-of-day-2275088/)
  (read: wait or sleep; "the local hours may differ from UT"); [gfinity](https://www.gfinityesports.com/guides/starfield-change-time-of-day/)
  (search snippet only, **unverified**: `showmenu sleepwaitmenu`, `set 3a to x`, `setgs fCalendarTimeScaleGround x`).
- Day length (**supported hypothesis**): Mutagen decodes the PNDT orbital field `RotationalVelocity`: Earth 1, Mars 0.96,
  Jemison 0.48, Akila 0.857 (6/7), Venus -0.004115 (= -1/243), Luna, Phobos, Europa, Titan and Mercury 0. Read as
  rotations per 24 h: day length = 24 h / |v| (Earth 24 h, Mars 25 h, Akila 28 h, Venus 5,832 h = its 243-day sidereal
  rotation, retrograde; 0 = no own rotation). Not yet compared with `Planet.GetDayLength()` in game. With the Utility.psc
  formula one local hour on Mars is 25 / 24 universal hours, so `GameHour` (universal, 24 h) and the local hour drift
  apart by one hour per Mars day; a local hour is the phase of the planet's rotation at the site, which is why
  `SetLocalTime` "rotates the planet" instead of changing `GameHour`.
- Why one site was always night (**supported hypothesis**): every run loads the same save, so the universal time at
  arrival is always the same, and the local time at a site then depends only on where the overlay is registered
  (verified data, read-only: raw `CNAM` (0.3, -1.2) 18 of 18 arrivals at night, (0.2, 1.2) 13 of 13 in daylight, above;
  exp1d's daylight arrival 16:15 and exp2b's night arrival 16:27 were 12 minutes apart).
- Weather ids: `Starfield.esm` has only three WTHR records (raw scan): `DefaultWeather` 0000015E, `SpaceWeather`
  00249FA6, `NewAtlantisWeather50` 0027CF9B; none is a Mars weather, so no staged plan sets `weather` (how a planet
  surface gets its weather is **unresolved**). `fw` syntax in the earlier games: [ck.uesp.net
  ForceWeather](https://ck.uesp.net/wiki/ForceWeather), [geck.uesp.net FW](https://geck.uesp.net/wiki/FW) (override flag
  1 holds until ReleaseWeatherOverride).
- Community listing of `SetLocalTime` ("sets the local time on the current planet, optionally updating the galaxy sim"):
  [starfield.fandom.com Help_command](https://starfield.fandom.com/wiki/Help_command) (search snippet only, the page
  was not readable: **unverified**).

In game (**unresolved** until the first run at the night site, `terrain_exp2b2_noon` below): whether `SetLocalTime`
works inside an overlay worldspace merged into Mars (the exe also has "SetLocalTime only works on a planet."; the
reply is now read), whether the sky changes without a reload and within 4 s (8 s with the second shot), and whether a
Mars noon reads above the thresholds. Also **unresolved**: how fast the local time runs during the probes. `TimeScale`
is 20 (above): if it applied in full, the 18.6 minutes exp2b2 a1 took for 14 probes would be about 6 game hours; how
much of that the console pauses is unknown (the probe shots of exp3 0004, 49 minutes, kept the same corner reading
104.3, which suggests little drift but was not checked further). `time_repin` makes the answer irrelevant for terrain
probes; the probe readings show it either way.

### Staged time-of-day plan (night site)

`C:\Modding\staging\terrain_exp2b2_noon`: exp2b2's plugins and `Data\` byte for byte, so the worldspace registers at the
night site (0.3, -1.2), with exp2t0's single test (exp2b2's 14 height probes + the 4 ground-type spots pt14..pt17;
exp2t0's BTD is exp2b2's byte for byte, only its registration site differs) and `time_of_day` 12, without
`need_daylight` (the heights are judged as before, the light is recorded). It answers whether the ladder turns a night
arrival into daylight; its probe shots compare with exp2t0's at the daylight site. The core64 border plans below are
at the same night site and set `time_of_day` 12 too. Step timeout 2,316 s (18 probes, light, repin).

```powershell
& $py scripts\game\testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2b2_noon `
      --out C:\Modding\testqueue\terrain_exp2b2_noon --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh --time-of-day 12
```

Superseded: the five `C:\Modding\staging\terrain_exp2t*_day` copies of the first version of this branch register at
the daylight site like their PR #70 originals, so their arrival is already in daylight and they cannot test the
commands (each README now says so; not queued). For the exp2t looks queue PR #70's own folders.

## Console commands before and after the travel (`console_pre`, `console_post`; `terrain`, `npc_nav`)

core64 (2026-10-11): every probe more than about 4 cells (about 450 m) from the `coc` arrival raised Starfield's
"Boundary Reached" popup, although all 4,096 overlay cells exist; Starfield.exe has INI settings for that border. To test
such settings unattended, a test can carry two lists of console lines:

| plan.json field | typed | default |
|---|---|---|
| `console_pre` | after the save has loaded (the runner's `setup_session`), before the travel (`coc`) | `[]` |
| `console_post` | after the arrival (and after the time of day / weather), before the probes or the spawn | `[]` |

Only these lines pass (`console_plan.py` `PATTERN`, checked by `plan-terrain` / `plan-npc` and again by `qstep.ps1`
`$consoleOk`, case-sensitive, whole line; a bad line ends planning, or the step with exit 4 before anything is typed;
at most 12 per list):

- `GetINI "<name>:<Section>"` and `SetINI "<name>:<Section>" <number>` (names and sections `[A-Za-z0-9_]{1,64}`, numbers
  `-?\d{1,9}(.\d{1,6})?`);
- the time-of-day / weather lines: `SetLocalTime <h> [1]`, `cgf "Game.SetLocalTime" <h>` (h 0..23.99), `fw <8 hex> [1]`;
- the bridge's lines (2026-10-14, "Bridge" below): `cgf "FO4SF_Probe.Pos" <decimal form id>`, `cgf "FO4SF_Probe.Ack" "<tag>"`,
  `cgf "FO4SF_Probe.Player"`, `cgf "Debug.TraceUser" "fo4sf" "<text>"` (tags `[A-Za-z0-9_.-]{1,40}`); their replies are
  lines of the bridge's log, not console text (the OCR'd reply is kept as for any line).

Anything else (`qqq`, `player.additem ...`, `coc ...`, `tgm`, a `;` or `|` inside a line, unquoted names, curly quotes, a
trailing newline) is refused; `tests/test_console_plan.py` lists the cases.

Each line is its own console session: open, type, capture the console region and OCR it (as the god-mode reply), close.
`obs.json` `console`: [{`phase` (`pre` / `post`), `cmd`, `ocr`, `shot` (`console_<k>.png`)}]. The judge reads each reply
from the text after the command's last echo (`console_plan.reply`: `value`, `not found`, `error`, `no reply`, `unread`;
OCR tolerant of l / I / 1, `> >`, dropped quotes; a reply that is not there is `unread`, never an older line's value),
appends `[console pre: GetINI bBorderRegionsEnabled:General = 1; ...] [console post: ...]` to the detail (shown, never
judged; `n of m typed` when the step ended early), and `results.jsonl` `console`, `report.md` "Console replies" and
`report.json` `console` list them. Each line adds 35 s to the step timeout.

Evidence (Starfield.exe 1.16.244.0, read-only):
- **verified** (command entries decoded): `SetINISetting` (short `SetINI`, "Sets an INI setting value.", parameters String,
  String), `GetINISetting` (short `GetINI`, "Prints an INI setting value to the console.", String), `RefreshINI`
  (`REFINI`, "Refresh INI settings from file.", none).
- **verified** (strings): the settings `bBorderRegionsEnabled:General`, `fPlayableAreaX:General`, `fPlayableAreaY:General`,
  `fPlayableAreaZ:General`, `uMaximumPlayableAreaWorldCoord:General`, `uPlayableSpaceOverlayCellBuffer:Planet`.
- **supported hypothesis** (format strings, which command prints them not traced): GetINI replies `INISetting %s >> %i` /
  `%u` / `%.4f` / `'%s'` / `NOT FOUND`; errors `INI setting "%s" does not exist` / `is not a boolean|int|float|string`.
- **unresolved**: whether `SetINI "bBorderRegionsEnabled:General" 0` typed in a running game (before the `coc`) removes
  the landing border for the next arrival (the "Border Regions Unlock" mod sets the INI value instead, community report
  relayed by the lead, not checked here); the staged runs below answer it.

### Staged border plans (core64)

`C:\Modding\staging\terrain_core64_border0` and `terrain_core64b_border0` are copies of `terrain_core64` (rays) and
`terrain_core64b` (rays with 300 m hops); plugins, `Data\` and reference files are unchanged and only `plan.json`
differs. Every test keeps its ray and adds:
`console_pre` = `GetINI "bBorderRegionsEnabled:General"`, `GetINI "fPlayableAreaX:General"`,
`GetINI "uPlayableSpaceOverlayCellBuffer:Planet"`, `SetINI "bBorderRegionsEnabled:General" 0`,
`GetINI "bBorderRegionsEnabled:General"`; `console_post` = `GetINI "bBorderRegionsEnabled:General"` (does the value survive
the travel?); `time_of_day` 12 (recorded only, no `need_daylight`: the heights decide as before; core64 is at the
night site, so this tests the time commands as well).

```powershell
& $py scripts\game\testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_core64_border0 `
      --out C:\Modding\testqueue\terrain_core64_border0 --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --fresh --time-of-day 12
& $py scripts\game\testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_core64b_border0 `
      --out C:\Modding\testqueue\terrain_core64b_border0 --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --fresh --time-of-day 12
```

Both install the core64 plugins from their own folder; `exp_install.py` refuses while core64 (or any experiment) is still
installed, so the chain's uninstall between queues has to run first.

Does the `SetINI` outlive the run? **Supported hypothesis**: no. `SetINI` changes the running game's setting;
Starfield writes only its preference settings back (`StarfieldPrefs.ini` under Documents\My Games\Starfield, whose
`[General]` held only `uiMarketplaceUpdatedHash` on 2026-10-12, read-only check), and every border test starts from a
fresh launch. After the border queues, `findstr /i BorderRegions` on that file (read-only) settles it.

Terrain step timeout (fix in this branch): measured core64 steps took 103-114 s a point (7 points 722-798 s against
870 s), and hops (`hop_m`) were not counted at all. The timeout is now 150 + (90 + settle surplus) x (points + 1) + 40 s and
`hop_wait_ms` for every intermediate hop (`terrain_hops`, the same count as `qstep.ps1`) + the light and console
commands, and the light of every probe shot (4 s) and the time command typed again before every probe (8 s):
core64_border0 1,167-1,394 s, core64b_border0 1,355-1,770 s (planned 2026-10-12).

## Staged experiments: `exp_install.py --pack`

Loose files are not read on this install, so `--pack` puts the experiment's whole `Data\` tree, textures included, into
the first plugin's own `<plugin> - Main.ba2` (Archive2 `-format=General`, stored uncompressed), recorded, installed and
uninstalled like the plugin files and never written over an existing file. The archive is built in a temporary folder;
the staged experiment folder (often another track's) is only read.

Why General for textures too (verified, read-only BA2 name scan of Starfield's Data, 2026-10-11): all 7,761
`textures/terrain/*` files, the 463 vanilla overlay masks among them, are in General archives (`Starfield -
DensityMaps.ba2`); SFBGS00D's 44 overlay masks are in `SFBGS00D - Main.ba2` although `SFBGS00D - Textures.ba2` exists; no
DDS (DX10) archive holds `textures/terrain/`. Terrain experiments 1d / 2b were measured with this packing. A staged folder without a `Data\` tree (a plugin-only experiment, e.g. `actor_raider1`) installs its plugins and no archive. (A first
version of this branch split `Data\textures` into a DDS `- Textures.ba2`; it was never run and is reverted.)

## Load door trips (`door_trip`) and experiment plugins that master FO4Port.esm (`plugin_order`)

The slice's "working door -> converted interior -> save/reload" (docs/slice/redrocket-door.md, which has the step, the
obs.json fields and every verdict). One test: `coc` into a world, the settled arrival gives the overlay's merge offset
(as npc_nav's `spawn_local`); "in": teleport to `outside.start` + offset facing the door, walk at it in steps with a HUD
check and a position read after each (an automatic door fades and loads within 3 m; a read more than `moved_m` from
the start is a load the HUD checks missed, and ends the walk at once), E if a prompt shows, a teleport to
`outside.near` as the last try, E and the last try only after a read on this side of the door; the arrival read
until it settles, `player.GetInCell <inside.cell>` (parse_npc.py `incell`), a screenshot; "out" the same from
`inside.start`; then `save <save>` (its file must appear in the Saves folder), a teleport back to the coc arrival and
`load <save>` (the player must come back; a loading screen is looked for), the position and GetInCell read again.
PASS needs every arrival observed where expected and both legs walked (a load from the last try alone is INCONCLUSIVE
NEARONLY); NOLOAD needs the player standing within `activate_m` of the door with GetInCell not saying the far side;
a leg that fails ends the step. With `outside.ref` the door's own getpos is read after the coc (a diagnostic).

Since the first live runs (2026-10-13, [docs/slice/door-frames.md](../slice/door-frames.md)): every read is strict
(`readpos -Strict`), a load is never taken from one read (a second far read must agree within 1 m; a read whose axes
look swapped is rejected), GetInCell is typed only with `inside.cell_id` and never judged (the console refused the
cell's EditorID), the side of the door comes from position frames, and each arrival also reads the heading. With
`outside.route` / `inside.route` a leg walks from where the player stands (the coc arrival, the interior arrival)
through the waypoints to the door, steering with `player.setangle z` and timed W holds: no start teleport.

| plan.json field | meaning | default |
|---|---|---|
| `travel` | `coc <cell editor id>` into the world | required |
| `spawn_local` | the arrival in the world's own frame: offset = settled arrival - spawn_local | required |
| `outside` | `start`, `door`, `arrival` (where the interior door's XTEL puts the player), `near`, `ground` (what the returning player stands on): the world's own frame; `ref` (8 hex digits, the door's runtime form id: getpos diagnostic) | required (near, ground, ref optional) |
| `inside` | `cell` (EditorID, typed for GetInCell), `start`, `door`, `arrival`, `near`, `floor`: the interior's frame | required |
| `save` | save name, `fo4sf_` + letters / digits / `_`, never a `fo4sf_test_` session save | required |
| `radius`, `start_tol`, `reload_tol`, `ground_tol` | arrival, start, reload and ground tolerances (m) | 4, 3, 1, 1 |
| `walk_ms`, `walk_step_ms`, `near_wait_ms`, `load_wait_s`, `settle_ms`, `drop` | the walk, the last try, the load wait, the settle after a teleport, the drop | 8000, 500, 6000, 90, 6000, 0.5 |
| `moved_m`, `activate_m` | a read farther than this from a leg's start is the other side of the door; the door's range for NOLOAD | 30, 3 |
| `outside.route`, `inside.route` | 2 to 64 waypoints (x, y, z, the side's frame) from where the player stands to the door (the last within `activate_m` + 1 m of it); `moved_m` must exceed the route's reach + 10 m | none (straight walk from `start`) |
| `route_hold_ms`, `route_reach_m`, `route_speed`, `route_walk_ms`, `route_max_steps`, `route_final_steps` | the longest W hold, when a waypoint counts as reached, the first speed guess (m/s), the W budget, the step budget, the steps at the door itself | 2000, 0.8, 4.6, 60000, 40, 6 |
| `outside.arrival_heading`, `inside.arrival_heading`, `facing_tol` | the facing the door's XTEL gives on arrival (degrees, as getangle z); tolerance | none (not judged), 20 |
| `inside.cell_id` | 8 hex digits: `player.GetInCell <id>` after each arrival, reported only | none (not typed) |
| `frame_m` | a position within this of a side's door is in that side's frame | 150 |
| `probes` | up to 8 {ref, local, what}: getpos after the arrival, reported as merged / local / neither | none |
| `fresh`, `expect`, `basis`, time of day / weather, `console_pre` / `console_post` | as for npc_nav | |

```powershell
& $py scripts\game\testqueue.py plan-door --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\slice_redrocket_door `
      --out C:\Modding\testqueue\slice_redrocket_door --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm,FO4SliceRedRocket.esm --fresh
```

`plugin_order`: `pre_launch` appends the experiment's plugins to Plugins.txt, then cycle.ps1's deploy removes and
re-appends `*FO4Port.esm`, so an experiment plugin that masters FO4Port.esm (the slice door plugin) would load before
its master. cycle.ps1 now runs `exp_install.py order` after the deploy: every plugin in `FO4SFExp.install.json` moves
right after the last of its masters that Plugins.txt lists (lines are moved only; both uninstalls still find theirs);
a master neither listed nor one of the game's own files stops the launch (cycle exit 7, the runner stops). Queues
whose plugins master something outside the install and the game get the need `plugin_order` (`plan-*`,
`plugin_order_needed`), so a runner without it refuses them before launching. Tests: `tests/test_door_trip.py`
(plan, judge, order), `QstepDoorSandboxTests` in `tests/test_qstep_sandbox.py` (the real step against simulated
automatic doors, loading screens, GetInCell and save files: a full trip, an unmerged return, a door that does nothing,
a blocked walk loaded from the last-try spot (NEARONLY), a blocked walk without one (NOREACH), a load no HUD check saw
(found by the position: 2 loads, no last-try teleport), the door's getpos, a load that lands elsewhere, a save that is
not written, refused specs).

## Continuous walks (`walk`)

The owner's first acceptance step: walk Red Rocket <-> Sanctuary over the bridge and cell borders both ways, with no
teleport between start and goal (docs/terrain/walk-redrocket-sanctuary.md has the route, the step, every verdict and
how to read a result). `scripts/terrain/walk_route.py` plans the route offline from Fallout 4's own navmesh and the
staged overlay's converted collision and writes plan.json (two tests) and walk_ground.json (the judge's ground, pinned
by sha256). One test: `coc`, the settled arrival gives the merge offset (as `spawn_local` elsewhere); a test with
`setup` makes ONE teleport to the route's start before the walk (setup, not evidence); then legs: one console session
(`ClearConsole`, `player.getpos x/y/z`, OCR with parse_npc.py, then `player.setangle z <heading>` from
`walk_eval.py steer`), W held with `input.ps1`'s guarded `holdg` (released at once when the game loses the
foreground or a STOP file appears), a screenshot checked for the HUD and, by OCR of the screen centre, the "BOUNDARY
REACHED" box (which leaves the HUD on screen). The STOP files and the Resource Guardian are checked inside the walk
too (spec `stop`), since the runner is blocked in the step; a stop ends it like a guard stop (exit 2, no attempt). Nothing else is typed during the walk; the judge checks every leg's typed lines. PASS: the
goal reached, every leg read, every move plausible, every read on the terrain or a converted surface (0.6 m), every
planned cell border crossed between two reads, at least two reads on the bridge deck, no popup, the screenshots.
FAIL: BOUNDARY, FELL, HEIGHTS, JUMP, OFFROUTE, STUCK; anything missing is INCONCLUSIVE. `plan-walk` needs
`--install-exp` / `--plugins`: it pins the experiment's staged inputs (`queue.json` `experiment_identity`); the runner
stops before a launch when that folder changed and records the install record with every walk result (`results.jsonl`
`install`); a PASS or FAIL whose record is missing, incomplete or not the pinned experiment is INCONCLUSIVE INSTALL and
stops the run.

| plan.json field | meaning | default |
|---|---|---|
| `travel`, `spawn_local` | as for door_trip | required |
| `waypoints` | `[x, y, z, reach, keep]` in the world's own frame; z the expected ground; keep 1: a read there (else it may be walked past in a straight leg) | required |
| `setup`, `start`, `drop`, `settle_ms`, `start_tol` | the reverse test's one teleport to `start` (the first waypoint) before the walk | false, -, 1, 6000, 3 |
| `ground`, `ground_sha256` | walk_ground.json next to plan.json and its sha256 (checked when planning and when judging) | required |
| `goal_radius`, `z_tol`, `fell_m`, `offroute_m` | judge tolerances (m) | 3, 0.6, 3, 10 |
| `bridge` | `{src, edid, span: [s0, s1], min_reads}`: reads needed on that object's surface, with reads before and after | none |
| `crossings` | the planned cell borders `{from, to}` (local cells) | none |
| `max_legs`, `max_leg_m`, `speed`, `stuck_m`, `stuck_k`, `shot_every` | controller budget and settings | 60, 15, 4.6, 0.6, 3, 3 |
| `fresh`, `expect`, `basis`, time of day / weather, `console_pre` / `console_post` | as for npc_nav | |

```powershell
& $py scripts\game\testqueue.py plan-walk --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\walk_core64c `
      --install-exp C:\Modding\staging\terrain_core64c --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm `
      --out C:\Modding\testqueue\walk_core64c --fresh
```
Needs the runner feature `walk`. Tests: `tests/test_terrain_walk_route.py`, `tests/test_walk_eval.py`,
`QstepWalkSandboxTests` in `tests/test_qstep_sandbox.py`.

## NPC navigation (`npc_nav`)

The NPC step of the playable slice (PR #61, `docs/actors/npc-navigation.md` sections 3.3 / 3.4): a vanilla actor is
spawned at A and told to walk to the player standing at B; its position is sampled, then it is removed. Run N0 in a
vanilla navmeshed cell first (a baseline without a command and the controls: is the command chain right?), then N1 with
the same actor and commands in a test worldspace, so world, navigation and actor conversion stay apart.

```powershell
# plan.json in the experiment folder; --install-exp/--plugins install a world before launch (the staged terrain
# experiment whose terrain queue the N1 tests "require"); --control-queue: the N0 queue that gates this queue's FAILs;
# --fresh: a new game launch before every test (no actor or console state left over from the previous test)
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<build> --exp-dir C:\Modding\staging\npc_nav_n0 `
      --out C:\Modding\testqueue\npc_nav_n0 --fresh
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<build> --exp-dir C:\Modding\staging\npc_nav_n1 `
      --out C:\Modding\testqueue\npc_nav_n1 --install-exp C:\Modding\staging\terrain_exp2b2 `
      --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh
```

`plan-npc` writes only `queue.json`: a queue folder that already ran keeps its `state.json` (attempts, verdicts) and
`results.jsonl`. After a change to the step, move the old folder aside (for example to `npc_nav_n0_a1`) before planning
into its name again, so the new run starts with no attempts used.

`plan.json`: a list of tests (baselines are moved first, then controls). Everything the step types is validated by
`plan-npc` and again by `qstep.ps1` (a bad value ends the step with exit 4 before anything is typed). A key that is not
in the table below stops the planning (an older runner dropped unknown keys silently; `scripts/actors/raider_map.py
check-queue` compares a planned queue with its plan.json).

| field | meaning | default |
|---|---|---|
| `label` | test name (id suffix) | `npc<n>` |
| `travel` | `coc <cell editor id>`, the console travel that works into exteriors too | required |
| `npc` | vanilla `NPC_` form id, 8 hex digits (`002B211C` EncCitizen01Template: no template; `0000CF96` LvlCitizen_NoOld: templated) | required |
| `a`, `b` | spawn point and walk target, metres, in the worldspace's own frame | required |
| `anchor` / `spawn_local` | frame offset as in the terrain kind: `{"ref": "<8 hex>", "local": [x, y, z]}` read with prid + getpos, else the arrival point | none |
| `method` | `none` (no command: the baseline), `ptr_player` (`PathToRef player`), `cf_pathto_player` (`cf "Actor.PathToReference" player 1.0`), `follow_player` (`SetPlayerTeammate 1`, `EvaluatePackage`), `combat_player` (`StartCombat player`, hostile actors) | `ptr_player` |
| `reads_s` | game seconds of the reads after the command; 0 is the read right before it | `[0, 3, 8, 15, 30]` |
| `radius` R, `min_progress` M, `nomove`, `max_speed` | judge thresholds, metres and m/s | 2.5, 5, 0.5, 8 |
| `precommand_m` | a commanded test whose actor came this far towards B between the spawn read and t0 is INCONCLUSIVE PRECOMMAND; needs runner feature `npc_t0` | M |
| `arrive_progress` | an arrival within R is a PASS only after this much approach from t0 (d0 - min d), else INCONCLUSIVE SHORT; with it a baseline FAILs WANDER on the largest approach between any two of its reads (spawn read and t0 included); needs runner feature `npc_t0` (N0b, docs/actors/npc-navigation.md 5.4) | none (as before) |
| `combat_reads` | `true`: every sample's session also asks the combat manager and the verdict is ENGAGED / NOCOMBAT ("Combat engagement" below); methods `none` / `combat_player` only, never a control; needs runner feature `npc_combat` | false |
| `drop`, `settle_ms` | the player is dropped this high above A and B (god mode), then waits | 0.5, 1500 |
| `pre`, `pre_wait_ms` | probes after reaching A, before the spawn: only `gnm` (GenerateNavMesh, ladder run N2) | `[]`, 5000 |
| `spawn_wait_ms` | game time with the console closed between `placeatme` and reading the handle (below) | 2000 |
| `handle_tol` | the ref PickLastRef names must stand this close (horizontal, metres) to the player's read at A | 2.0 |
| `path_line` | `tpl` (path display) on for the walk, off at the end | false |
| `control` | a control test: gates the FAIL verdicts of the other tests | false |
| `control_npc` | the actor (8 hex) whose control (same method) and baseline gate this test's FAIL instead of the test's own actor: a calm converted actor in the vanilla control cell is judged against the calm vanilla actor's control there (N2a's calm probe: `002B211C`, docs/actors/raider-conversion.md); not on a control or a baseline | the test's `npc` |
| `requires` | `{"queue": "<queue dir>", "test": "<test id or label>", "verdict": "PASS" \| "FAIL" \| "DECIDED"}`: run only when that test has that verdict (DECIDED: PASS or FAIL, i.e. it was judged at all). Without `queue`: a test of this queue (one level: it may not itself wait for one), which this one waits for in the same run (N2: every test waits for N2a_base's spawn). For another queue, `plan-npc` checks that it installed the very folder `--install-exp` installs | none |
| `fresh` | relaunch the runner's game before this test, as `plan-terrain --fresh` (a repeated `coc` into a merged planet world arrives erratically, 2026-10-11); `plan-npc --fresh` sets it on every test | false |
| `expect`, `basis` | the verdict expected before the run and why (verified / supported hypothesis); shown in the report | none |

What one test does (`qstep.ps1`, kind `npc_nav`):

1. `coc <cell>`, wait for the HUD, read the arrival until two reads 3 s apart agree within 0.3 m (up to 5 reads: exp1d
   read its arrival mid-fall). Frame offset from the anchor; when the anchor reads back its own local position (an
   all-zero XY offset: our persistent markers do, exp1d 50 50 10 and exp2b -989.03 1147.20 105.14, 2026-10-11) or
   cannot be read, from the settled arrival. No offset when one was asked for, or an arrival that never settles: stop
   before anything is spawned (INCONCLUSIVE ANCHOR).
2. Player to A (dropped from `drop`), optional `pre` probes, then the spawn and its handle (next section):
   `player.placeatme <npc> 1` in its own console session, the console closed for `spawn_wait_ms`, then three sessions:
   `plr` (PickLastRef's reply gives the runtime id `FFxxxxxx`), `prid <id>` + `GetSelf`, `GetIsID <npc>` + `getpos x/y/z`.
   Everything read goes to `obs.json` `spawn` (`ref`, `self`, `isid`, `read`, `dist_a`, `confirmed`, `why`, the OCR of
   each session); the captures stay as `place_*`, `spawn_plr_*`, `spawn_self_*`, `spawn_isid_*` (`_cap.png`,
   `_ocr.txt`).
3. Only with a confirmed handle: player to B, facing A (the walk target is the player).
4. The walk command, typed in a session that selected the actor with `prid <id>` and read `GetIsID` 1, with the t = 0
   position read in that session (`none`: nothing typed).
5. For each time in `reads_s`: wait while the console is closed, open it, `prid <id>`, `GetIsID <npc>` (must read 1),
   `getpos x/y/z`, close, screenshot. `obs.json` is saved after every read. `t_game` counts closed-console time (the
   console pauses the game: supported hypothesis), `t_wall` the clock; both are kept (about +-2 s). The step gets a
   budget (`budget_s`, the runner's timeout minus 60 s) and stops sampling (`samples_cut`) when fewer than 300 s would
   be left for step 6.
6. Remove the actor: `disable`, `GetDisabled` (recorded), `markfordelete`, on a selection confirmed in the same session
   only (next section), whether or not the spawn was confirmed.

Typing: `qstep.ps1` passes every key sequence to `input.ps1` as a native argument. Windows PowerShell 5.1 drops the
double quotes inside such an argument (verified: `cf "Actor.PathToReference" player 1.0` arrived as
`cf Actor.PathToReference player 1.0`), so `Send` writes them as `\"`; the sandbox checks that the console receives the
quoted line.

Step timeout (`step_timeout`): a worst case, every read needing both Select-Npc sessions and the spawn four sessions
(about 45 s each: console open, ClearConsole and ~60 characters at 0.24-0.32 s, waits, OCR at up to four thresholds),
Read-Pos up to three tries, plus the 300 s removal reserve (Select-Npc twice, PickLastRef again: three sessions, the
removal): 1,852 s for N0's plans, 1,893 s for N1's (five reads up to 60 s), against a typical run of about 550 s.

### Combat engagement (`combat_reads`)

An approach is the wrong measure of combat: in QASmoke on 2026-10-13 the hostile vanilla Spacer (`00270255`,
N0b_spacer_base) did not come 18 m towards the player in 30 s (PASS "stayed away" as a baseline), and `StartCombat
player` froze the calm citizen (`002B211C`, N0b_combat: FAIL NONAV). With `"combat_reads": true` a test asks the combat
manager instead. At every sample, once the selection is confirmed (`prid <id>`, `GetIsID` 1, `getpos x/y/z`),
`qstep.ps1` makes a second capture in the same console open (the selection stays on the prid'ed ref while the console
is open, as the spawn's captures rely on): `ClearConsole`, `GetIsID <npc>` again, then exactly `GetCombatState`,
`GetCombatTarget` and `GetLineOfSight player` (`testqueue.NPC_COMBAT_READS`; Starfield.exe condition functions,
verified in its help strings: "Test the state of this actor in the combat manager", "Gets the current actor's combat
target (ref ID)"). Nine lines: what the console shows; all of it in one capture scrolled the position replies off
(sandbox). Each sample gets `combat_isid` (that capture's GetIsID; 0 drops its values), `combat` (a small integer),
`target` (an 8-hex form id; the player is `00000014`), `los` (0 / 1) and `combat_ocr` (its raw OCR; the capture stays
as `npc_combat_cap.png` / `_ocr.txt`). The reply formats are **unverified**
until the first run: `parse_npc.py` reads a condition function's decimal or an integer after the label (`GetCombatState
>> 1.00`, `>> 1`) and an id in parentheses, bare or `0x` after `GetCombatTarget` (never an id the session typed
itself), and leaves anything else `null`. An unreadable reply is never a value.

Verdict (`testqueue.judge_npc_combat`): PASS ENGAGED when any confirmed sample read state >= 1 with target `00000014`;
FAIL NOCOMBAT when every expected sample read state 0; INCONCLUSIVE COMBATREAD when the replies were not readable (the
format hypothesis failed, or only some samples read), OTHERTARGET when it fought another ref. The walk judge's
preconditions (spawn confirmed, player at B, command typed) still hold, and its verdict is appended as `walk: ...`
(a method `none` test's walk read as a baseline's) for information only. A combat test is neither a wander baseline nor
a control: it gates nothing and no control gate applies. Methods: `none` (a hostile actor engages on its own) or
`combat_player`. Staged as experiment `npc_combat_c1` (plan.json: the Spacer as the positive control, the calm citizen
as the negative one, the converted raider `02F04800` as the question), planned with `--install-exp` for the raider
plugin and `--fresh`.

### Reading the console (`parse_npc.py`)

What the console showed the runner (verified, N0_base attempt 1, 2026-10-11, QASmoke: `obs.json`, `npc_ocr.txt`,
`npc_cap.png`, `C:\Modding\testqueue\npc_nav_n0\tests\0000_npc_nav_N0_base\a1`):

- about nine lines (the capture and the console in a full screenshot both hold nine);
- `ClearConsole` does not clear them: the last capture shows the previous session's `GetPos: X >> -7.82`,
  `GetPos: Y >> -5.25`, `GetPos: Z >> 0.00` above `ClearConsole`, `disable`, `GetDisabled`, `GetDisabled >> 1`;
- the game prints lines of its own into a session: three `GetInFaction >> 0.00` after `player.placeatme 002B211C 1`;
- replies: `PickLastRef: (FF010D65)`, `GetIsID >> 0.00` (a decimal), `GetSelf >> (0024a824)` (a parenthesised form id,
  lower case), `GetPos: X >> -7.82`, `GetDisabled >> 1` (an integer);
- OCR misreadings: l for I (`GetlsID 002B211C`, `GetlslD 0.00`, `GetlnFaction`), split words (`Get Po s`,
  `Clear Console`, `Get Disabled`), `-7 82` for -7.82, `> >` for `>>`.

Every session still types `ClearConsole` first: its echo marks where the session begins. `qstep.ps1` tells the parser
what its commands produce, in typing order (`--expect ref,isid,x,y,z,self,disabled`; `--typed` the id a `prid` typed).
The session start is the later of the last `ClearConsole` echo and the echo of the session's first expected command
(the n-th last echo when the session typed it n times); nothing before it is read, ever (the previous parser counted
an older session's `getpos` echoes and read its values). The OCR lays the lines out in two ways (verified, OCR texts
of the runner's sessions): inline (`GetIsID > > 1.00`, `Get Pos: X > > -10.07`, sometimes without arrows) and column
(all labels and echoes first, then all values; echo arguments drift into the value column or are lost:
`Get Pos: Z > > player.getpos ... GetPos: Z > > tgm 3.66 x -10.07 43.95 z -10.95`).

Two readings, the first that holds is used. *Order*: the session's values are the decimals after the session start in
typing order; it holds only when there are exactly as many as expected, no `>>` stands before the session start (in the
column layout older values would be counted), no more `>>` follow than reply labels (a line the game printed), and the
labels are in the expected order; a GetIsID / GetDisabled value other than 0 or 1 drops it. *Inline*: label, arrows and
value next to each other after the session start; GetIsID / GetDisabled also as an integer after `>>` or `:`. Echoed
integers and form ids are never values, and there is no bare-number fallback. `ref`: the last `FFxxxxxx` id after this
session's last `PickLastRef` label (`plr` is typed alone in its session, so that is its reply in both layouts). `self`:
the last id after this session's `GetSelf` echo, any form id (`(0024a824)` too), an id the session typed itself only
when on screen twice (echoed argument and reply). In ids, O / o for 0 and l / I / | for 1 are mapped back. A screen
whose lines cannot be told apart is not read (UNREAD, retried).

### The actor handle: choice and risks

What N0_base attempt 1 showed (2026-10-11, the first version of the step typed `ClearConsole`,
`player.placeatme 002B211C 1`, `plr`, `GetIsID 002B211C`, `GetSelf` in one session): the citizen spawned (`spawn.png`:
"Citizen: Howdy."); PickLastRef named `FF010D65`; but `GetIsID` read 0.00 and `GetSelf` named `0024A824`, and the
console's own selection label read `STAT '' (0024A824)` in a later full screenshot (`_session\recover\recover.png`): the
selection was a static, not the new actor (verified: the same id twice). Three minutes later, in the removal session,
`plr` + `GetIsID` read 1.00 at -7.82, -5.25, 0.00, 1.3 m from A, and `GetDisabled` read 1 after `disable`. So `GetSelf`
was right and `GetIsID` was right; what failed was the selection. Supported hypotheses: opening the console selects
what is under the crosshair (the floor static, the player looking 10 degrees down, at A and at B), and an actor placed
while the console is open (the game paused) is not selectable by `plr` until the game has run.

Choice: the handle is PickLastRef's runtime id, read after the game ran, and confirmed by evidence before anything acts
on it.

1. `player.placeatme <npc> 1` in its own session (OCR kept as `place_ocr`), then the console is closed for
   `spawn_wait_ms` (2 s) of game time.
2. `plr` alone: the id in `PickLastRef: (FFxxxxxx)` after this session's start, 8 hex digits starting `FF`; nothing
   further is typed without it.
3. `prid <id>`, `GetSelf`: GetSelf must not name another ref (N0_base's `0024A824`); unread is allowed.
4. `GetIsID <npc>` must read 1; `getpos x/y/z` must put the ref within `handle_tol` (2 m) of the player's read at A
   (placeatme puts it at the player's feet).

All four hold: `confirmed`, the walk and the samples follow; any fails: INCONCLUSIVE SPAWN with the reason in `why`.
Every later session selects the actor by that id (`prid <id>`) and confirms `GetIsID` 1 in the same session before it
reads the position or types the walk command, `disable` or `markfordelete`; the console's own selection and `plr` are
never relied on after the spawn. The alternative, a persistent actor placed by a plugin (known ref id, `prid`), needs a
plugin in the control cell; it is the route for the converted actor (ladder N6), not for the vanilla control.

Removal: by the confirmed id first. Without one (or when it cannot be read), `plr` again, now that the game has run: the
ref it names is removed only when `GetSelf` after `prid` names no other ref, it stands within 40 m of A or B, and either
`GetIsID` reads 1, or it is the very ref PickLastRef named at the spawn (then within `handle_tol` of the player) and
`GetSelf` names it. A selection that stayed on a static never gets `disable`.

| risk | effect | mitigation / label |
|---|---|---|
| `GetIsID` compares a leveled actor's generated base, not the placed one: `0000CF96` LvlCitizen_NoOld has a template (TPLT 002B2120 and TPTA, verified by a raw walk of Starfield.esm) | every test of that actor INCONCLUSIVE SPAWN | unresolved; the staged plans use `002B211C` EncCitizen01Template (HumanRace, no TPLT / TPTA, not unique: verified, same walk; `GetIsID` read 1.00 on it in N0_base's removal: verified) and keep one N0 test of `0000CF96` to answer the question; the spawn OCR is saved; the actor is still removed as the ref PickLastRef named at the spawn, at the player's feet, that `GetSelf` names |
| the console keeps another selection (a static under the crosshair) | reads and commands would go to that ref | verified in N0_base; the handle is selected by `prid <id>` in every session, `GetSelf` must not name another ref, `GetIsID` must read 1 |
| `plr` names a ref that is not the actor (the actor not yet created, or another ref created after it, e.g. fauna in an exterior) | no handle | the console is closed for `spawn_wait_ms` first; the ref must be of the base (`GetIsID` 1) and at the player's feet: INCONCLUSIVE SPAWN otherwise, never assumed |
| OCR misreads the id (B / 8, D / 0) | `prid` selects nothing or another ref | O / l / I mapped back; a wrong id fails `GetSelf` / `GetIsID` / the position check |
| the step is cut off (owner input, a menu over the HUD) | the actor stays in the session | the runner never saves after the session start, so a relaunch drops it; recorded as `cleanup` in `obs.json`; the step budget keeps 300 s for the removal before the timeout |
| the actor's own package brings it near the player (QASmoke is about 24 x 24 m) | a false control PASS would make N1's FAILs count | the baseline (method `none`): a control counts for the gate only when the baseline of that actor passed (it did not come to B) |
| a warp to the player (teammate catch-up, script moveto) | a false PASS | faster than `max_speed` + 2 s slack between reads: INCONCLUSIVE WARP (gross jumps only); at B by the first read: INCONCLUSIVE EARLY (the walk itself was not seen) |
| OCR | a read missing | four thresholds per session, both layouts; a missing read is INCONCLUSIVE, never PASS |

### Judge (positions in metres; d = horizontal distance to the player at B)

| verdict | class | rule |
|---|---|---|
| PASS | PASS | min d <= R (arrived, not already at the first read; with `arrive_progress` A: also d0 - min d >= A), or d0 - d_end >= M (walked M towards B); reads may be missing after that |
| PASS | PASS (baseline) | `none`: never within R of B and not M closer, all planned reads confirmed |
| FAIL | FELL | a read below min(start z, B z) - 3 m: world, not navigation |
| FAIL | WANDER | baseline: came to B (or M closer) without a command, measured from t0 and from the spawn read (the actor at the player's feet at A, before the player went to B: an actor that closed in before t0 counts); with `arrive_progress`: M closer between any two reads |
| FAIL | NONAV | all planned reads confirmed, spawn and command succeeded, never moved `nomove` m from t = 0 |
| FAIL | STALLED | moved, but neither PASS rule |
| INCONCLUSIVE | ANCHOR / SPAWN / HANDLE / TARGET / UNREAD | no frame offset; spawn not confirmed or more than 3 m from A; selection lost before the command; player not read at B; a planned read missing for a FAIL |
| INCONCLUSIVE | WARP / EARLY | faster than `max_speed` between reads; at B by the first read |
| INCONCLUSIVE | PRECOMMAND | a commanded test whose actor came `precommand_m` (default M) towards B (or within R of it) between the spawn read and t0: what follows is not the command's walk alone (a hostile actor, or a citizen that walks up to the player: N0_cf, N1c) |
| INCONCLUSIVE | SHORT | `arrive_progress` A: arrived within R, but less than A closer than at t0 (too little after the command to tell from wander; it did arrive, so no FAIL) |
| INCONCLUSIVE | CONTROL | a FAIL of a non-control test while no control with the same method and actor (`control_npc` when set) passed (this queue or `--control-queue`), or the baselines of that actor planned in the control's own queue did not pass or one of them came to B (a baseline of the other queue neither opens nor closes the gate). Final for the runner, raw verdict kept (`raw` in `results.jsonl` / `state.json`); `report` applies the gate again, so a control that passes later (retried at the end of its queue, or its queue run afterwards) still counts. PASS is never gated |
| INCONCLUSIVE | PRECONDITION | `requires` not met: not run, the game not launched for it; final (plan the queue again once the required test passed). A required test of the same queue that is still to be run or retried is waited for first; a dry run records nothing |

A PASS of a commanded test carries a note from the same actor's baseline (this queue or `--control-queue`): "the
command moved it" when the baseline stayed away, "not credited to the command" when it came to B on its own.

### Evidence used (Starfield.exe 1.16.244, read-only, `scripts/recon_console.py`)

Verified (command entries decoded: name, short name, help, parameters):
`PathToRef` (`PTR`, "Force actor to path to reference.", one optional TESObjectREFR), `PickLastRef` (`PLR`, "Select the
last created ref for the console."), `PickRefByID` (`PRID`, optional ObjectReferenceID), `ClearConsole` (`clear`, "Clears
the console log"), `TogglePathLine` (`TPL`, optional String). Names present, help paired by string adjacency (supported
hypothesis): `GetSelf` (alias `this`, "Gets the ref ID for the current reference."), `GetIsID` ("Is the reference a ref
to the specified base object?"), `GetDisabled`, `MarkForDelete`, `PlaceAtMe` ("[object][count][distance][direction]
[forcepersist]"), `EvaluatePackage` (`evp`), `SetPlayerTeammate`, `StartCombat`, `GenerateNavMesh` (`gnm`: no command
entry decoded, weaker than the others; the decoder also pairs ToggleNavMesh with "Toggle blocked display.", so some
help pairings are wrong). `gnm` stays whitelisted for N2 but no staged plan uses it.
Verified in game (N0_base attempt 1, 2026-10-11, above): the reply formats of `PickLastRef`, `GetIsID`, `GetSelf`,
`GetPos`, `GetDisabled`; `ClearConsole` leaves the lines on screen; `placeatme` spawns `002B211C` at the player;
`disable` works on it.
Unresolved until N0 runs again: whether `PathToRef player` and `cf "Actor.PathToReference" player 1.0` start a walk,
whether `GetIsID` matches a templated actor's placed base, whether the console pauses the game, and whether 2 s of game
time are enough for `plr` to select a new actor.

Sandbox: `tests/test_qstep_sandbox.py` runs the real step against a simulated console (`tests/qstep_sandbox`, whose
`input.ps1` never sends input). Its defaults model what N0_base met: `ClearConsole` leaves the lines, opening the
console selects a floor static, an actor placed with the console open is not selectable until it closes, the game's
`GetInFaction` lines, the real reply formats, l-for-I OCR. Scenarios: walk, no walk, the 2026-10-11 spawn, `plr` that
never selects, a selection that stays on the static (no walk, no `disable`, the static never touched), an unconfirmed
spawn removed by its id, the anchor frame, a failed spawn, `cf` typed with its quotes, the column OCR layout, an anchor
that reads its local position, an arrival read mid-fall, an arrival that never lands, the baseline. Time of day
(`QstepLightSandboxTests`: the simulated game arrives at night, local time 22, and its screenshots carry the simulated
sky in their top rows): `SetLocalTime 12` gives daylight before the spawn; a ladder that only `cgf` (typed with its
quotes) moves; no command with an effect (INCONCLUSIVE NIGHT with `need_daylight`, "no effect: night"); `fw <id> 1`
before the time; the terrain step setting the time after the arrival and before the first probe; an arrival already
in daylight ("the time commands were not tested"); `SetLocalTime` refused with "only works on a planet." (read from
the console, `cgf` credited and typed again before the probe); a sky that follows one screenshot late (credited to
`SetLocalTime 12` on its second shot, `SetLocalTime 12 1` never typed); game time that moves 3 h per console session
(with `time_repin` every probe reads daylight, without it the third probe reads night and is named). Console commands
(`QstepConsoleSandboxTests`, simulated INI settings answering in the exe's reply formats, OCR reading `GetlNl`,
`lNlSetting`, `EnabIed`, `> >`): the five border lines before the `coc` and the read after the arrival (values 1,
3200.0000, 2, no reply, 0; then 0), npc_nav with an unknown setting (NOT FOUND, does not exist), and lines off the
whitelist (`qqq`, `player.additem`, `tgm`, a `|key:` injection, `coc` in `console_post`): exit 4, nothing typed. Opt-in,
30-60 s a scenario: `$env:FO4SF_QSTEP_SANDBOX = '1'`.

## Movable items: walk, then impulse (`movable --impulse`, `movable_control`)

Why (docs/ai/research-log.md 2026-10-13): most converted items that did not move lay where the walk could not push
them, not in bodies that cannot move: a cigarette pack on a desk 0.83 m above the player's feet (the walk ends at the
desk 0.67 m from it), a pin box the player was blocked 1.45 m short of, three books flat on the floor that the walk
passed over. One does not fit: a 50 kg pin box 0.81 m above the feet at the stand point that the walk passed 0.26 m
from (the player rose 0.28 m on the way) did not move. Every motion, layer and flag field of these bodies matches
vanilla Starfield items; the masses do not (FO4's are 2-10 times as heavy). So (verifier of PR #110, 2026-10-13):

- **Only the walk passes a movable test.** It asks whether the player pushes the item. A walk whose closest approach
  came within reach (1 m) and left the item in place is FAIL NOTMOVED, with or without the impulse ladder.
- **ELEVATED** (`movable`): an item that did not move, more than 0.5 m above the player's feet (the higher of the reads
  before and after the walk, so a player who climbed onto the furniture counts at its height) while the walk came no
  closer than 0.5 m to it (`CONTACT_M`), or more than 1.8 m above them (`OVERHEAD_M`), is INCONCLUSIVE ELEVATED: final
  at once and not counted by the circuit breaker (`FINAL_INCONCLUSIVE`). An item the walk passed within 0.5 m of is
  judged by reach as any other, however high it lies. `CONTACT_M` and `OVERHEAD_M` are not measured from Starfield's
  capsule (supported hypothesis: a radius of about 0.3-0.4 m plus the item's half-width, a height of about 1.8 m);
  `CONTACT_M` lies between the readings it must separate, 0.26 m (batch_full 0100, walked through) and 0.67 m
  (supervised_1011 0007, stopped at the desk).
- **The impulse ladder** (diagnostic): when the walk moved the item less than 5 cm, `ApplyHavokImpulse <x> <y> <z>
  <magnitude>` is typed on the item, in its own console session after `prid <ref>` and `GetIsID <base>` read 1 (the
  npc_nav handle rules), the console is closed for `impulse_wait_ms` (3 s) and the item is read again (same
  confirmation). Axis: back along the walk (the path the player has just walked, so free) and 45 degrees up.
  Magnitudes: mass x dv for dv 1.5, 6 and 24 m/s, stopping at the first that moves the item 5 cm (kg m/s: supported
  hypothesis, `LC012NASAGravTrigger.psc` scales its impulses by `GetMass()`). An impulse that moves it adds "the body
  is simulated" to the detail of NOTMOVED / ELEVATED / MISSED; FAIL STUCK: every impulse was typed on a confirmed
  selection and none moved it either. The magnitudes scale with the mass, so the ladder cannot show whether the mass
  stops the player: `movable_control`'s vanilla items and its `SetRigidBodyMass` copies can.
- `testqueue.py plan --kinds movable --impulse` adds the ladder to every movable test whose item has a base record in
  `formids.json` (`MSTT:<EditorID>`, the confirmation's `GetIsID`) and a mass in the manifest. Runner features
  `impulse` and `push_judge` (the first impulse runner, 91f3d17, passed such an item as PASS IMPULSE).

`movable_control` places an item in a vanilla cell, so a converted item can be compared with vanilla items on the same
floor. `plan-movable` reads `plan.json` (a list):

```powershell
& $py scripts\game\testqueue.py plan-movable --staging C:\Modding\staging\<pinned build> `
      --exp-dir C:\Modding\staging\<experiment with plan.json> --out C:\Modding\testqueue\<queue> --fresh
```

| field | meaning | default |
|---|---|---|
| `label`, `model` | test name; what the item is (the report groups by it) | `item<n>`; the label (a converted item: its FO4 source) |
| `travel` | `coc <cell editor id>` | required |
| `base` / `base_edid` | the item's base form id in the load order (8 hex, a vanilla item) or the EditorID of a converted MoveableStatic of the pinned build (its id from `formids.json` and `--plugin-index`, its mass from the manifest) | one of them |
| `mass_kg` | the body's mass (vanilla: from its NIF) | the manifest's for `base_edid` |
| `spot`, `heading` | where the item is placed (metres, the cell's frame) and the walk's heading (degrees, as `setangle z`) | required, 0 |
| `stand_m`, `park_m` | the player starts `stand_m` before the item's read position; waits `park_m` behind the spot while it settles | 1.1, 3.0 |
| `set_mass_kg` | `SetRigidBodyMass <kg>` on the confirmed selection before the walk, with the `GetMass` probe before it and again after it (the console closed `mass_wait_ms`, a second confirmed selection). A refusal in the console reply is INCONCLUSIVE SETMASS; unless the probe after it reads the mass set (within 5 %, at least 0.25 kg) the test is INCONCLUSIVE MASS, whatever the walk did | none |
| `mass_probe` | `cf "ObjectReference.GetMass"` on the confirmed selection (always with `set_mass_kg`; `mass_probe: false` with it stops the planning); without `set_mass_kg` its reading is only shown | false |
| `mass_wait_ms` | the console closed after `SetRigidBodyMass` before the reading | 1000 |
| `impulse_dv`, `impulse_wait_ms` | the ladder's speed steps (m/s, up to 4; `[]`: none) and the wait after each | [1.5, 6, 24], 3000 |
| `walk_ms`, `settle_ms`, `drop`, `spawn_wait_ms`, `handle_tol` | hold W; wait after a teleport; teleport height; console closed after `placeatme`; how close to the spot the placed item must lie | 900, 1500, 0.3, 3000, 2.0 |
| `moved_m`, `reach_m`, `settle_m` | moved; the walk reached the item; at rest before the walk (spawn read vs the read before the walk) | 0.05, 0.6, 0.1 |
| `console_pre`, `console_post` | whitelisted console lines (section above), e.g. `GetINI "fCharacterMaxSlope:HAVOK"` | none |
| `fresh`, `expect`, `basis` | as npc_nav; an expectation names the PASS class (`PASS WALKED`, `PASS IMPULSE`) | |

`movable_control` results: PASS WALKED (the walk moved it); PASS IMPULSE (the walk came within `reach_m` and did not
move it, an impulse did: a measurement of the control, the body is simulated and the walk did not push it); FAIL
STUCK; FAIL NOTMOVED (no ladder); FAIL ITEMFELL; INCONCLUSIVE MISSED (the walk never came within `reach_m`, whatever an
impulse did), IMPULSE (the ladder did not finish), START (the player not read at the spot, or not within 0.4 m of its
height there or at the stand point: not the open floor the plan assumed), SPAWN (handle not confirmed, or the item at
rest more than 0.5 m from the spot's height), SETMASS, MASS, SETTLE, UNREAD.

One test (`qstep.ps1` kind `movable_control`): `coc`, the arrival read until it settles; the player dropped at the spot;
(nothing is placed when the player is not within 1 m of the spot and 0.4 m of its height)
`player.placeatme <base> 1` in its own session and, in the same session (the game paused), the player moved to the
park point, then the console closed for `spawn_wait_ms` so the item drops onto a free floor; the handle as npc_nav's
(`plr` alone, `prid <id>` + `GetSelf` must not name another ref, `GetIsID <base>` 1, within `handle_tol` of the spot:
else INCONCLUSIVE SPAWN and nothing acts on any selection); the `GetMass` probe and `SetRigidBodyMass`, then the
console closed `mass_wait_ms` and `GetMass` again on a second confirmed selection; the player
`stand_m` before the item's read position facing `heading`; the item read (confirmed), the walk, the player's and the
item's reads; the ladder; then `disable`, `GetDisabled`, `markfordelete` on a confirmed selection only. `movable` tests
never remove anything: their items belong to the build. Runner feature `impulse` (`runner_features.py`): an older
runner refuses such a queue before launching the game.

Staged (2026-10-13, offline, not run): `movable_control_1013b` (staging and queue folders of that name; planned with
`--fresh` on `integ_1011`, build 2470f876; it replaces `movable_control_1013`, planned before the verifier's fixes, whose
5 kg tests would have been judged without a mass reading): in QASmoke on lanes 1.8 m apart (x -12 .. 6, y 4, walking
north), vanilla TrashbinGeneric01 / ContemporaryCigarettesPack01 / Office_NotePad_Stack02 (5.7 cm) /
Office_NotePad_Stack01 (3.8 cm) / Office_Folder01 (0.7 cm) next to the converted TrashcanMetalOffice01 / CigarettePack /
BobbyPinBox / BurntBook01, and the book and the box again at 5 kg (judged only when `GetMass` reads 5 kg back). Each
test writes its expectation and basis first. Open floor along the lanes is a supported hypothesis: the offline count
of QASmoke's 156 references for N0 (docs/actors/npc-navigation.md 5.2) leaves nothing in its south room (navmesh x
-14.8 .. 8.9, y -8.8 .. 14.8, z 0, on 6 x 6 m gravel floor tiles) but the border walls (x -15, x 9, y -8.7), the
pillars in its two south corners and the ceiling 6 m up, and the lanes (x -12 .. 6, y about 2.9 .. 6) lie 3 m or more
inside the walls. They were not checked lane by lane nor walked in game; the START / SPAWN height checks turn a lane
that is not open floor at z 0 into INCONCLUSIVE instead of a result.

Evidence used (Starfield.exe 1.16.244, `scripts/recon_console.py`, which decodes the stack-built script-function entries
too since 2026-10-13): `ApplyHavokImpulse` opcode 0x1251, Float x4, "Applies an impulse of the passed magnitude to the
reference along a passed axis."; `SetRigidBodyMass` 0x1156, Float, "Sets the Havok mass for an object."; `SetPos`
0x1007 (Axis, Float), `PlaceAtMe` 0x1025 (ObjectID, optional Count, Distance, Direction), `GetIsID` (ObjectID),
`GetSelf` (`this`), `GetDisabled`, `Disable` (optional Integer), `MarkForDelete`, `ForceWeather` (`fw`, Form, optional
Int) decoded the same way. `CallFunction` (`cf`) is a console command of the same table (decoded 2026-10-14: "Calls a
papyrus function on the targeted ref. First parameter is the function, the rest are parameters", one String and up to
seven optional Strings); `GetMass` has no console entry of its own (`recon_console.py` decodes none; `--near` finds its
name among the ObjectReference Papyrus natives, between `GetLocRefTypes` and `GetNthLinkedRef`), so `cf
"ObjectReference.GetMass"` is the only console route to the mass, and the judge never assumes its reply: a 5 kg test is
judged on the number read back, else INCONCLUSIVE MASS. Unresolved until the queue runs: whether the console accepts
`ApplyHavokImpulse` and `SetRigidBodyMass` on a selected item, the magnitude's unit, and whether `cf
"ObjectReference.GetMass"` reaches the native function and prints its value at all: `cf "Actor.PathToReference"`
replied "No script named Actor is attached to the object" (N0_cf, verified), so the same reply for `ObjectReference` is
a supported hypothesis; it would leave the 5 kg tests INCONCLUSIVE MASS. They stay in the queue (two tests of a few
minutes each): a reading settles the mass question that nothing else in the queue can, and no reading costs no verdict.

Sandbox (`QstepMovableSandboxTests`; the simulated game pushes an item at least 8 cm tall that the walk passes within
0.35 m of, walks over a thinner one, and moves an item by an impulse when magnitude / mass reaches 1 m/s): a tall
vanilla bin pushed by the walk and removed (the `GetINI` line typed before the `coc`, its reply in the verdict); a flat
book walked over and moved by the first impulse, typed on the confirmed selection; the ladder climbing to its second
step; a fixed item (FAIL STUCK after three impulses); a 50 kg box not pushed, pushed after `SetRigidBodyMass 5`
(`GetMass` 50 before, 5 after in a session of its own on a selection confirmed again); a `SetRigidBodyMass` that
changes nothing and a `GetMass` answered "No script named ObjectReference ..." (both INCONCLUSIVE MASS); a refused
`SetRigidBodyMass`; a spot 1 m above the floor (nothing placed, START); a failed spawn (nothing acts on any
selection); bad specs, among them a set mass without its probe (exit 4, nothing typed); a `movable` test of the
build's own book with the ladder (walked over, moved by the impulse: FAIL NOTMOVED; never disabled).

## Bridge: the game reports its own state (`scripts/bridge`, `dotnet/Bridge`, `bridge_log.py`; 2026-10-14)
The owner's decision D1 of the 14 Oct review: position reads stop going through a screenshot and Windows OCR of the
console (every read failure of 13-14 Oct was that channel: a lost digit group, a garbled read taken for a load, the
runner's E on the load-order dialog, the HUD dial splitting console lines into a label column and a value column).
Instead the game writes a file:
- `FO4SFBridge.esm` (`dotnet/Bridge build`): GLOB `FO4SF_Cmd` (0x800, not Constant) and QUST `FO4SF_BridgeQuest`
  (0x801, StartGameEnabled, no stages) carrying the Papyrus script `FO4SF_Bridge` with properties `FO4SF_Cmd` -> the
  global and `Interval` (0.5 s). VMAD shape as vanilla quests (version 6, object format 2, extra-bind-data 3).
- `scripts/bridge/FO4SF_Bridge.psc`: `OnInit` opens the user log `fo4sf` and starts a timer; every `OnTimer` writes one
  line `FO4SF rt=<real time> pos=<x> <y> <z> ang=<heading> cell=<form id> world=<form id> loaded=<bool> [cmd=<n>] n=<count>`
  with `Debug.TraceUser`; `cmd=` appears on the line after the global changed, so `set FO4SF_Cmd to 7` typed in the
  console is acknowledged by the game, not by a capture. Compiled with the game's `Tools\Papyrus Compiler` against the
  base scripts in `Tools\ContentResources.zip` (`make_bridge.py stage` extracts them); the `.pex` ships in
  `Data\Scripts` of the experiment folder, packed by `exp_install.py --pack` (loose scripts are not read here).
- Log: `<My Games>\Starfield\Logs\Script\User\fo4sf.0.log`; needs `[Papyrus] bEnableLogging=1 bEnableTrace=1
  bLoadDebugInformation=1` in `StarfieldCustom.ini` (`make_bridge.py ini`, idempotent, keeps a .bak).
- `scripts/game/bridge_log.py latest | wait-cmd <n> | wait-move`: the newest line as JSON (stale after 3 s: the game or
  the quest is not running), a wait for the echo of a command, a wait for the player to move. Form ids come back as hex.
- Staged: `C:\Modding\staging\bridge_t0` (plugin, pex, offline_check.txt all checks pass, plan.json, README.txt).
- **Go/no-go: GO (in game, 2026-10-14 21:28-21:36, the owner watching; evidence in `C:\Modding\staging\bridge_t0\evidence`,
  docs/media/bridge-*.jpg).** Pinned build 2470f876 + FO4SFBridge.esm, launched by cycle.ps1 into FO4Port_Vault111Cryo.
  - **Lines (verified):** `[21:29:40] FO4SF rt=99.711006 pos=1.531505 -7.385632 -0.851672 ang=0.000000 cell=50336243
    world=none loaded=true n=32`: one line every 0.66 s (0.5 s timer plus frame alignment), six decimals, `true` in
    lower case, `none` for the worldspace in an interior, the game's `[HH:MM:SS]` prefix. `OnInit` ran at the main menu
    (a 93-byte log, rotated to .1) and again when the save loaded. 473 lines in 8 minutes, no Papyrus error for the script.
  - **Walk (verified):** W held 2 s through input.ps1: y -7.3856 -> -5.7418 (1.64 m) on the log, no capture involved.
  - **Save and load (verified):** `save fo4sf_bridge_t0` then `load` of it: the quest's state and timer come back
    (`n` continued at 411, `rt` at 424 s); `OnInit` fires again on the load, so the user log **rotates on every load**
    (.0 is always the newest; a reader notes `n` / `rt`, never the file).
  - **Console acknowledgement (verified):** `cgf "Debug.TraceUser" "fo4sf" "ack 7"` typed in the console wrote
    `[21:33:44] ack 7` into the same log within a second: a console command batch can prove its own execution by
    ending with such a line (a nonce), and `cgf` is already on the console whitelist.
  - **The global channel does NOT work (verified, refuted):** `set FO4SF_Cmd to 7` -> "Unknown variable 'FO4SF_Cmd'",
    `set 04000800 to 7` -> "Unknown variable '04000800'", `help FO4SF_Cmd 4` -> "VIEWER STRINGS NOT AVAILABLE", no
    match: the game keeps no EditorID strings for this plugin's GLOB (coc still resolves cell EditorIDs). The script
    reads the global fine (`cmd=0` on its first line), only the console cannot set it. The `FO4SF_Cmd` property stays
    for a later route (a Papyrus-side setter); the runner uses the TraceUser acknowledgement.
  - **Keys (verified the hard way):** input.ps1 needs `LEGACY=1` (keybd_event) for the console key and typed text, as
    every runner script sets; a plain SendInput W still walks. **StarfieldCustom.ini cannot be written by our scripts:**
    Windows Controlled Folder Access blocks python.exe and powershell.exe in Documents (Defender event 1123), so the
    `[Papyrus]` keys went into the game folder's `Starfield.ini` (backup `Starfield.ini.bak-20261014-212734`);
    `make_bridge.py ini` reports the block and names that fallback.
- **Runner feature `bridge`** (`plan`, `plan-terrain`, `plan-npc`, `plan-door`, `plan-walk`, `plan-movable` with
  `--bridge <staged bridge dir>`): every test of the queue carries `bridge_reads: true` (`bridge` is a walk plan's
  deck); qstep.ps1's `Read-Pos` for the
  player and the walk's `Walk-Read` / `Walk-Session` return the newest log line (`bridge_log.py latest`, not older
  than 2 s; `bridge_max_age_s` in a test raises that for the sandbox), listed in `obs.read_log` with `via: bridge`
  and the line's `rt` / `n` instead of a readpos nonce; reads of other references (doors, probes, NPCs) still go
  through readpos. The queue pins the staged bridge (`queue.json "bridge"`: folder, plugin, sha256 of the plugin and
  the .pex); before every launch the runner checks those hashes and runs `bridge_install.py install` (its own record
  `Data\FO4SFBridge.install.json`, "FO4SFBridge - Main.ba2" packed like an experiment, "*FO4SFBridge.esm" last in
  Plugins.txt; idempotent, re-activates after a deploy rewrote Plugins.txt; `exp_install.py uninstall` leaves it).
  Sandbox: the fake game appends a bridge line to `$FO4SF_BRIDGE_LOG` after every call
  (`test_the_walk_reads_the_bridge_log_and_types_no_getpos`). Still to come: console batches ending with a TraceUser
  nonce (`cgf "Debug.TraceUser" "fo4sf" "<nonce>"`) in place of OCR confirmation; OCR stays for pop-ups and HUD checks.
- **`FO4SF_Probe.psc` (staged with the bridge, unverified):** global functions for the console's `cgf`:
  `cgf "FO4SF_Probe.Pos" <decimal form id>` logs that reference's position, heading, cell, disabled and loaded flags
  (`FO4SF ref=<id> pos=.. ang=.. cell=.. disabled=.. loaded=..`), `cgf "FO4SF_Probe.Ack" "<tag>"` logs `FO4SF ack <tag>`,
  `cgf "FO4SF_Probe.Player"` the player. If the VM loads an unattached script for cgf (supported hypothesis; the first
  window tells), door and probe reads of `door_trip` and the NPC reads of `npc_nav` can leave OCR too.

## Activate (terrain, 2026-10-15)

A terrain test may carry `"activate": {"ref": "<8 hex>", "expect": ["First Aid Kit", "Credits", "Digipick"]}` (R05 slice 1:
the native container's reference, load index included). After the probes and before the beyond teleport, the step opens one
console session, types `prid <ref>` and `activate player`, closes the console (the menu opens with the player as the
activator: no facing, no E), captures the whole screen as `activate.png`, OCRs it, and closes the menu with Tab
(`activate_closed.png`). The verdict detail gets `[activate <ref>: read [...] of [...]]`, the expected words the OCR found;
it is shown and never judged, and the owner's own E-press stays the interaction acceptance. Runner feature `activate`
(`runner_features.py`): an older runner refuses such a queue instead of running it without the step.

### teleport_console (terrain diagnostic, 2026-10-15)

`"teleport_console": true` on a terrain test makes every probe teleport capture its own console session before closing it
(`tp<n>.png`, OCR in `obs.teleports[n]` with the typed target): the game's reply to `player.setpos` / `setangle`, which
nothing else records. Added for r05_medkit_1015/b/c/e, where the player stayed at the Red Rocket arrival through every
probe while the bridge read fresh. Off by default; no effect on the verdict.
