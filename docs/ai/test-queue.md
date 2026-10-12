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

## Staged experiments: `exp_install.py --pack`

Loose files are not read on this install, so `--pack` puts the experiment's whole `Data\` tree, textures included, into
the first plugin's own `<plugin> - Main.ba2` (Archive2 `-format=General`, stored uncompressed), recorded, installed and
uninstalled like the plugin files and never written over an existing file. The archive is built in a temporary folder;
the staged experiment folder (often another track's) is only read.

Why General for textures too (verified, read-only BA2 name scan of Starfield's Data, 2026-10-11): all 7,761
`textures/terrain/*` files, the 463 vanilla overlay masks among them, are in General archives (`Starfield -
DensityMaps.ba2`); SFBGS00D's 44 overlay masks are in `SFBGS00D - Main.ba2` although `SFBGS00D - Textures.ba2` exists; no
DDS (DX10) archive holds `textures/terrain/`. Terrain experiments 1d / 2b were measured with this packing. (A first
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
`plan-npc` and again by `qstep.ps1` (a bad value ends the step with exit 4 before anything is typed).

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
| `drop`, `settle_ms` | the player is dropped this high above A and B (god mode), then waits | 0.5, 1500 |
| `pre`, `pre_wait_ms` | probes after reaching A, before the spawn: only `gnm` (GenerateNavMesh, ladder run N2) | `[]`, 5000 |
| `spawn_wait_ms` | game time with the console closed between `placeatme` and reading the handle (below) | 2000 |
| `handle_tol` | the ref PickLastRef names must stand this close (horizontal, metres) to the player's read at A | 2.0 |
| `path_line` | `tpl` (path display) on for the walk, off at the end | false |
| `control` | a control test: gates the FAIL verdicts of the other tests | false |
| `requires` | `{"queue": "<queue dir>", "test": "<test id>", "verdict": "PASS"}`: run only when that test has that verdict; `plan-npc` checks that the queue tested the very folder `--install-exp` installs | none |
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
| PASS | PASS | min d <= R (arrived, not already at the first read), or d0 - d_end >= M (walked M towards B); reads may be missing after that |
| PASS | PASS (baseline) | `none`: never within R of B and not M closer, all planned reads confirmed |
| FAIL | FELL | a read below min(start z, B z) - 3 m: world, not navigation |
| FAIL | WANDER | baseline: came to B (or M closer) without a command |
| FAIL | NONAV | all planned reads confirmed, spawn and command succeeded, never moved `nomove` m from t = 0 |
| FAIL | STALLED | moved, but neither PASS rule |
| INCONCLUSIVE | ANCHOR / SPAWN / HANDLE / TARGET / UNREAD | no frame offset; spawn not confirmed or more than 3 m from A; selection lost before the command; player not read at B; a planned read missing for a FAIL |
| INCONCLUSIVE | WARP / EARLY | faster than `max_speed` between reads; at B by the first read |
| INCONCLUSIVE | CONTROL | a FAIL of a non-control test while no control with the same method and actor passed, or the actor's baseline (when planned) did not pass (this queue or `--control-queue`). Final for the runner, raw verdict kept (`raw` in `results.jsonl` / `state.json`); `report` applies the gate again, so a control that passes later (retried at the end of its queue, or its queue run afterwards) still counts. PASS is never gated |
| INCONCLUSIVE | PRECONDITION | `requires` not met: not run, the game not launched for it; final (plan the queue again once the required test passed) |

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
that reads its local position, an arrival read mid-fall, an arrival that never lands, the baseline. Opt-in, 30-60 s a
scenario: `$env:FO4SF_QSTEP_SANDBOX = '1'`.
