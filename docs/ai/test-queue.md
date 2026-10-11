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
| npc_nav | `plan-npc` (plan.json, below) | the actor reached B or walked towards it | NONAV, STALLED, FELL | spawn / handle / reads failed, control not passed |

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

Loose files are not read on this install, so `--pack` puts the experiment's `Data\` tree into the first plugin's own
archives, the same split `deploy_starfield.py` uses for FO4Port: `Data\textures` goes into `<plugin> - Textures.ba2`
(Archive2 `-format=DDS`, `.dds` files only, refused otherwise) and every other top-level folder (`Terrain`, `meshes`, ...)
into `<plugin> - Main.ba2` (`-format=General`). Both are recorded, installed and uninstalled like the plugin files and are
never written over an existing file. That a plugin's `- Textures.ba2` loads with it is verified for FO4Port (journal,
2026-10-07); for an overlay mask it is the vanilla layout (textures in DDS archives), not yet measured. Change against
the first `--pack` (terrain experiments 1d / 2b): their overlay mask went into `- Main.ba2`.

## NPC navigation (`npc_nav`)

The NPC step of the playable slice (PR #61, `docs/actors/npc-navigation.md` sections 3.3 / 3.4): a vanilla actor is
spawned at A and told to walk to the player standing at B; its position is sampled, then it is removed. Run N0 in a
vanilla navmeshed cell first (the control: is the command chain right?), then N1 with the same actor and commands in a
test worldspace, so world, navigation and actor conversion stay apart.

```powershell
# plan.json in the experiment folder; --install-exp/--plugins install a world (e.g. terrain exp2b) before launch;
# --control-queue: the N0 queue whose control tests gate this queue's FAIL verdicts
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<build> --exp-dir C:\Modding\staging\npc_nav_n0 `
      --out C:\Modding\testqueue\npc_nav_n0
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<build> --exp-dir C:\Modding\staging\npc_nav_n1 `
      --out C:\Modding\testqueue\npc_nav_n1 --install-exp C:\Modding\staging\terrain_exp2b `
      --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --control-queue C:\Modding\testqueue\npc_nav_n0
```

`plan.json`: a list of tests (controls are moved first). Everything the step types is validated by `plan-npc` and again
by `qstep.ps1` (a bad value ends the step with exit 4 before anything is typed).

| field | meaning | default |
|---|---|---|
| `label` | test name (id suffix) | `npc<n>` |
| `travel` | `coc <cell editor id>`, the console travel that works into exteriors too | required |
| `npc` | vanilla `NPC_` form id, 8 hex digits (`0000CF96` LvlCitizen_NoOld) | required |
| `a`, `b` | spawn point and walk target, metres, in the worldspace's own frame | required |
| `anchor` / `spawn_local` | frame offset as in the terrain kind: `{"ref": "<8 hex>", "local": [x, y, z]}` read with prid + getpos, else the arrival point | none |
| `method` | `ptr_player` (`PathToRef player`), `cf_pathto_player` (`cf "Actor.PathToReference" player 1.0`), `follow_player` (`SetPlayerTeammate 1`, `EvaluatePackage`), `combat_player` (`StartCombat player`, hostile actors) | `ptr_player` |
| `reads_s` | game seconds of the reads after the command; 0 is the read right before it | `[0, 3, 8, 15, 30]` |
| `radius` R, `min_progress` M, `nomove` | judge thresholds, metres | 2.5, 5, 0.5 |
| `drop`, `settle_ms` | the player is dropped this high above A and B (god mode), then waits | 0.5, 1500 |
| `pre`, `pre_wait_ms` | probes after reaching A, before the spawn: only `gnm` (GenerateNavMesh, ladder run N2) | `[]`, 5000 |
| `path_line` | `tpl` (path display) on for the walk, off at the end | false |
| `control` | a control test: gates the FAIL verdicts of the other tests | false |
| `expect`, `basis` | the verdict expected before the run and why (verified / supported hypothesis); shown in the report | none |

What one test does (`qstep.ps1`, kind `npc_nav`):

1. `coc <cell>`, wait for the HUD, read the arrival; frame offset from the anchor (or the arrival). No offset when one
   was asked for: stop before anything is spawned (INCONCLUSIVE ANCHOR).
2. Player to A (dropped from `drop`), optional `pre` probes, then one console session: `ClearConsole`,
   `player.placeatme <npc> 1`, `plr` (PickLastRef selects it), `GetIsID <npc>`, `GetSelf`; OCR. Then `GetIsID` + `getpos`
   for the spawn position.
3. Player to B, facing A (the walk target is the player).
4. The walk command, typed only on a confirmed selection (below), with the t = 0 position read in the same session.
5. For each time in `reads_s`: wait while the console is closed, open it, confirm the selection, `getpos x/y/z`, close,
   screenshot. `obs.json` is saved after every read. `t_game` counts closed-console time (the console pauses the game:
   supported hypothesis), `t_wall` the clock; both are kept (about +-2 s).
6. Remove the actor: `disable`, `GetDisabled` (recorded), `markfordelete`, on a confirmed selection only.

### The actor handle: choice and risks

Choice: `placeatme` + PickLastRef + `GetIsID` confirmation. Every console session that reads the actor or types a command
that acts on the selection (the walk command, `disable`, `markfordelete`) first confirms the selection in that same
session: `GetIsID <npc>` must read 1 by OCR, otherwise nothing more is typed. The selection is looked for in this order:
`prid <id>` with the runtime id `GetSelf` returned at spawn (when it parsed as `FFxxxxxx`), the console selection as it is,
then `plr` again. Each session starts with `ClearConsole`, and `parse_npc.py` takes a value only from the text after the
last echo of its own command, so a reply left on screen by an earlier session is never read as new (both checked with a
simulated console that does not clear). The alternative, a persistent actor placed by a plugin (known ref id, `prid`),
needs a plugin in the control cell; it is the route for the converted actor (ladder N6), not for the vanilla control.

| risk | effect | mitigation / label |
|---|---|---|
| `GetIsID` compares a leveled actor's generated base, not `0000CF96` (the citizen has a template) | every test INCONCLUSIVE SPAWN | supported hypothesis that the placed base is compared (FO4 / Skyrim: the ref keeps the placed base); the spawn OCR text is saved; the actor is still removed by its `GetSelf` id when `GetSelf` reads that id back; else pick a non-template NPC |
| `GetSelf`'s reply format is unknown | no id: reads use the selection and `plr` | unresolved; hex, `(hex)`, `0x`, a bare id line and a decimal id are parsed; only `FFxxxxxx` (runtime refs) is used |
| another runtime ref is created after the spawn (fauna in an exterior), `plr` picks it | that read fails the confirmation (UNREAD) | confirmed by `GetIsID`, never assumed |
| the step is cut off (owner input, a menu over the HUD, timeout) | the actor stays in the session | the runner never saves after the session start, so a relaunch drops it; recorded as `cleanup` in `obs.json` |
| cleanup by id disables a runtime ref that is not ours | only if `placeatme` failed and `plr` picked another runtime ref | `FFxxxxxx` refs only, never authored refs; the test save is not overwritten |
| OCR | a read missing | four thresholds per session; a missing read is INCONCLUSIVE, never PASS |

### Judge (positions in metres; d = horizontal distance to the player at B)

| verdict | class | rule |
|---|---|---|
| PASS | PASS | min d <= R (arrived), or d0 - d_end >= M (walked M towards B); reads may be missing after that |
| FAIL | FELL | a read below min(start z, B z) - 3 m: world, not navigation |
| FAIL | NONAV | all planned reads confirmed, spawn and command succeeded, never moved `nomove` m from t = 0 |
| FAIL | STALLED | moved, but neither rule above |
| INCONCLUSIVE | ANCHOR / SPAWN / HANDLE / TARGET / UNREAD | no frame offset; spawn not confirmed or more than 3 m from A; selection lost before the command; player not read at B; a planned read missing for a FAIL |
| INCONCLUSIVE | CONTROL | a FAIL of a non-control test while no control with the same method and actor passed (this queue or `--control-queue`); final, raw verdict kept in the detail. PASS is never gated |

### Evidence used (Starfield.exe 1.16.244, read-only, `scripts/recon_console.py`)

Verified (command entries decoded: name, short name, help, parameters):
`PathToRef` (`PTR`, "Force actor to path to reference.", one optional TESObjectREFR), `PickLastRef` (`PLR`, "Select the
last created ref for the console."), `PickRefByID` (`PRID`, optional ObjectReferenceID), `ClearConsole` (`clear`, "Clears
the console log"), `TogglePathLine` (`TPL`, optional String). Names present, help paired by string adjacency (supported
hypothesis): `GetSelf` (alias `this`, "Gets the ref ID for the current reference."), `GetIsID` ("Is the reference a ref
to the specified base object?"), `GetDisabled`, `MarkForDelete`, `PlaceAtMe` ("[object][count][distance][direction]
[forcepersist]"), `EvaluatePackage` (`evp`), `SetPlayerTeammate`, `StartCombat`.
Unresolved until N0 runs: whether `PathToRef player` and `cf "Actor.PathToReference" player 1.0` start a walk, the
replies of `GetIsID` / `GetSelf` / `ClearConsole` in this console, and whether the console pauses the game.

Sandbox: `tests/test_qstep_sandbox.py` runs the real step against a simulated console (`tests/qstep_sandbox`, whose
`input.ps1` never sends input): walk, no walk, a log that is not cleared with a lost selection, an unconfirmed spawn, the
anchor frame, a failed spawn. Opt-in, about 25 s a scenario: `$env:FO4SF_QSTEP_SANDBOX = '1'`.
