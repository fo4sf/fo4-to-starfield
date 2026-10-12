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
| movable | manifest `movable` items placed in the cell | item moved at least 5 cm when walked into | did not move although reached; fell | player missed it |
| travel | load doors whose XTEL partner is in the same build | arrived within 4 m of the arrival point | no prompt; E did nothing | start not reached, arrived elsewhere |
| terrain | `plan-terrain` (an experiment's plan.json) | heights within 0.5 m | NOTERRAIN, HEIGHTS | a height not read, moved |
| npc_nav | `plan-npc` (plan.json, below) | the actor walked to B (a baseline: stayed away without a command) | NONAV, STALLED, FELL, WANDER | spawn / handle / reads failed, warp or early arrival, control or precondition not met |

Every verdict needs its observations: a position that was not read or a screenshot that is missing makes the test
INCONCLUSIVE, never PASS. INCONCLUSIVE tests are retried once more at the end of the queue (`--max-attempts 2`); a FAIL
is final. A game crash during a test is recorded (class CRASH) and the game is relaunched (at most `--max-relaunch`).

## Controls (checked before every launch and every test)

- STOP file, Resource Guardian mode (`paused` / `stopped`, or an unreadable database) stop the run.
- The game is launched only after `--min-idle` seconds (default 900) without keyboard or mouse input, and only through
  `cycle.ps1`. A Starfield the runner did not start (the owner's own session) is never touched: the run stops.
- Owner activity: input the runner did not send, or another window in front of the game, stops the run (or waits with
  `--wait-for-idle`; with `--refocus` it then brings its own game window back to the front once, never another app).
  Every step runs with `FO4SF_NO_FOCUS_STEAL=1`, so `input.ps1` refuses to pull the game in front during a test.
- `queue.json` `"hours"` limits the allowed hours (default `[[0, 24]]`); `--max-hours` and `--max-tests` bound a run.
- The build is pinned: `queue.json` records the SHA-256 of `FO4Port.esm`; the runner will not launch a staging folder
  whose plugin changed. The dedicated save `fo4sf_test_<build id>` is created on the first launch and loaded on later ones.

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
  an older runner would judge such a queue by `min_progress` alone), and the runner refuses a queue whose needs its checkout lacks
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
- the time-of-day / weather lines: `SetLocalTime <h> [1]`, `cgf "Game.SetLocalTime" <h>` (h 0..23.99), `fw <8 hex> [1]`.

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
