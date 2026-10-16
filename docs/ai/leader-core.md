# Leader core: the state model and the bounded tasks that build it

Owner's brief: the final leader build (project topic, 2026-10-15), implementation order step 1 "document and enforce
the core state model". This page is the *document* half; the *enforce* half is the task cards in §4, each sized for
one cloud session. Prior analysis: the owner's research note of 2026-10-14 (leader core and Starfield modding).
Written by Claude (cloud). Nothing here changes a running script; `src/fo4sf/core/` does not exist yet.

## 1. What the leader must know (the state model)

One append-only ledger, `leader/ledger.jsonl`, kept beside the test queues (outside the repo, like
`C:\Modding\testqueue\`). Every line is one event: `{"t": <utc iso>, "ev": <type>, "by": <agent>, ...fields}`.
Current state is a fold over the ledger, so a leader interrupted by a power cut or a reclaimed VM resumes by reading
it, never by guessing. Existing files are **imported as events, never rewritten** (§3), so every original campaign
record stays where it is.

| State the brief names | Ledger event(s) | Fields |
|---|---|---|
| Current leader build and commit | `leader_started` | `commit`, `branch`, `host`, `session` |
| Active game build, experiment plugins, load order | `build_pinned`, `plugins_verified` | `build_id`, `plugin_sha256`, `staging`, `plugins[]` (name, sha256, active_after_load), `load_order[]`, `game_version` |
| Worker assignments and controller ownership | `task_assigned`, `controller_claimed` / `controller_renewed` / `controller_released` | `task`, `owner`, `purpose`, `expires` |
| Verified / failed / inconclusive / untested capabilities | `capability_result` | `capability`, `outcome`, `source`, `build_id`, `evidence[]` (untested = no event for that capability on that build) |
| Known blockers and their evidence | `blocker_opened` / `blocker_closed` | `blocker`, `evidence[]`, `owner` |
| Queued, running, skipped, circuit-broken, completed tasks | `task_queued`, `task_started`, `task_finished` | `task`, `outcome` (§2), `attempt`, `detail` |
| Original versus new campaign results | every imported or new result carries `campaign` | `campaign` (`batch_full`, `supervised_1011`, … for imports; `final-<date>` for the new build) |
| Recovery points, saves, logs, pinned artifacts | `recovery_point` | `kind` (save, log, capsule, screenshot), `path`, `sha256`, `build_id` |

Rules the fold enforces:
- A task whose last event is `task_started` with no `task_finished` is **running or lost**, never done.
- `SKIPPED` and `CIRCUIT_BROKEN` are terminal but **undecided**: they never count toward a capability being verified.
- A capability is `verified` only by an `IN_GAME` `PASS` on the pinned build; an `OFFLINE`, `SIMULATED` or
  `HYPOTHESIS` result can mark it `failed`/`inconclusive`-pending but never `verified` (brief §6).
- A controller lease that expired without `controller_released` makes ownership **ambiguous**; nothing that sends game
  input runs until a fresh claim is logged (brief §7).
- The work-period report (the owner's eight bullets) is generated from the fold, so it cannot drift from the state;
  its "next queue" bullet lists the queued tasks of the **pinned build** (a task that names no build is listed too),
  so the leftovers of a stopped historic campaign do not follow the owner forever.
- Task ids in the ledger are `<campaign>/<test id>` (the queue folder's name and the runner's id), because the
  planners repeat test ids across campaigns (`0000_terrain_<coc>` in every terrain campaign) and two campaigns must
  never merge in the fold. A card's own id (§8) is already unique.
- An event of a type this checkout does not know is read as an opaque line (kept, counted, not folded), so a ledger
  written by a newer checkout stays readable; a known type without its key field (`task`, `capability`, `blocker`)
  is a corrupt line. Every writer takes the ledger's lock file (`ledger.jsonl.lock`, `filelock.py`) around the
  repair of a torn tail and the append, so two processes never interleave inside one write.

## 2. The enums, once

```
Outcome  = PASS | FAIL | INCONCLUSIVE | SKIPPED | CIRCUIT_BROKEN      # only PASS / FAIL are decided
Source   = IN_GAME | OFFLINE | SIMULATED | HYPOTHESIS                   # brief §6
Capability state (derived, per build_id) = verified | failed | inconclusive | untested
```

Mapping from today's `testqueue.py` records (`verdict`, `class`): `PASS`→`PASS`; `FAIL`→`FAIL`;
`INCONCLUSIVE` with class `BREAKER`→`CIRCUIT_BROKEN`; `INCONCLUSIVE` with class `PRECONDITION`→`SKIPPED`;
any other `INCONCLUSIVE` class (`CONTROL`, `UNREAD`, `NOSHOT`, `NIGHT`, …) →`INCONCLUSIVE`, class kept in `detail`.
Every queue record is `source = IN_GAME`; `walksim` and `route_eval` results are `SIMULATED` / `OFFLINE`.

## 3. What gets imported, from where (verified field names, repo `main` d628b56; re-checked on 16a1d2d, 2026-10-16)

| File | Event | Fields read |
|---|---|---|
| `<queue>/queue.json` | `build_pinned`, `task_queued` per test | `build_id`, `plugin_sha256`, `staging`, `commit`, `created`, `tests[].id/kind/cell/ref` (`scripts/game/testqueue.py:422`) |
| `<queue>/results.jsonl` | `task_finished` per row | `id, kind, cell, ref, attempt, verdict, class, detail, dir, t` (`testqueue.py:2681`); last row per id is final |
| `<queue>/state.json` | nothing (reviewed 2026-10-16) | the runner writes a `results.jsonl` row for every attempt, PRECONDITION and BREAKER included, and checkpoints `state.json` in the same step (`testqueue.py` `Runner.run`), so `done`/`attempts` repeat the rows; a task in flight is visible only in the ledger's own `task_started` (T2); the breaker counters, `status` and `updated` are the runner's bookkeeping |
| `Data/FO4Port.deploy.json` | `build_pinned` | `artifacts[FO4Port.esm].sha256` → `plugin_sha256`, `build_id` = its first 8 hex digits (the derivation of `testqueue.py plan`), `complete` (`scripts/deploy_starfield.py` `install`, `artifact_identity`; the manifest carries no `build_id` of its own) |
| `Data/FO4SFExp.install.json`, `Data/FO4SFBridge.install.json` | `plugins_verified` (active_after_load from `exp_install.py active`) | `plugins`, `plugins_replaced[].active/original`, `complete`, `pack` (`exp_install.py:492`) |
| `watchdog_state.json` | `controller_*` (historic, best effort) | heartbeat and hand-over times (`watchdog.ps1:22`) |

Imports are idempotent: an event carries `src` (file path + line for a file that only grows; the queue.json path +
a digest of the pin fields, so a pin rewritten in place by `pin-game-version` or a re-plan is a new event; file path
+ content sha256 + mtime for the deploy and install records, which are rewritten in place by every deploy, so a
re-deploy of a build imported earlier is a new pin), and a re-import skips events already present. The importer
never writes to the files it reads; it reads them as `utf-8-sig` like the runner (a hand-edited queue may carry a
BOM) and stores the runner's local wall-clock times (`testqueue.now()`, no zone) as UTC, converted on the machine
that wrote them.

## 4. Bounded, resumable tasks (one cloud session each)

Each card has the fields the brief requires. Status is kept on the task's GitHub issue, not here.

### T1 — `core/model.py` + `core/state.py` + importer (this is "enforce the state model")
- **Objective:** `src/fo4sf/core/model.py` (the enums above, `Event` dataclass, `decided()` guard),
  `src/fo4sf/core/state.py` (append, fold, `LeaderState` with the eight report bullets), `src/fo4sf/core/import_queue.py`
  (§3 import of a queue folder, deploy and install records). Pure Python, no numpy, no game or engine imports.
- **Owner:** Claude. **Inputs:** this page; `scripts/game/testqueue.py` record shapes (§3); `tests/test_testqueue.py`
  fixtures for synthetic queue folders.
- **Dependencies:** none. **Timeout / retry:** one session, two attempts at most.
- **Acceptance:** `python -m unittest discover -s tests` green including new `tests/test_core_state.py` (synthetic
  ledger: fold after a truncated last line; SKIPPED/CIRCUIT_BROKEN never verify; expired lease → ambiguous; import is
  idempotent); `python scripts/guard.py` ok; a `decisions.md` entry (already written, 2026-10-15); report generator
  prints the eight bullets from a synthetic ledger.
- **Evidence required:** test output in the PR body; no in-game claim.
- **Recovery:** the branch is the checkpoint; a second session continues from the last commit.
- **Not in scope:** wiring into `testqueue.py`, the lease file, preflight (T2, T3).

### T2 — controller lease, wired into the runner and the watchdog
- **Objective:** `core/controller.py` (lease file: owner, purpose, expiry; every claim/renew/release is a ledger
  event); `testqueue.py run`, `chain`/`cycle.ps1` and `watchdog.ps1` refuse to send input without a valid lease in
  their name; the watchdog reads the lease instead of "last `Claude:` commit on any branch" (cloud sessions trip it).
- **Owner:** Claude (live scripts). **Dependencies:** T1 merged. **Acceptance:** synthetic tests for claim/renew/
  release/expiry; a dry-run `testqueue.py run` with no lease exits with the reason; nothing in game.
- **Recovery:** lease and ledger are files; a crash leaves an expired lease, which is the ambiguous state by design.
- **Switch (2026-10-16):** every part of the wiring is behind `FO4SF_LEASE_DIR` (the watchdog: `lease_dir` in
  `watchdog.json`), unset by default, so nothing on the PC changes until the PC session turns it on (§6).
  Implemented by Claude-cloud in #178 (`src/fo4sf/core/controller.py`, `scripts/game/lease.py`).

### T3 — `core/preflight.py`, the deployment gate (brief §7)
- **Objective:** before any live task: deployed hashes match the pin, every experiment plugin active after the save
  loads (the 2026-10-14 load-order fix, generalised), load order as planned, game version equals the pin, lease held,
  STOP/Guardian reachable, recovery save and log capture on. Any unknown → refuse, ledger says why.
- **Owner:** Claude. **Dependencies:** T1, T2. **Acceptance:** each check has a synthetic pass and fail test; the
  gate is called by `testqueue.py run` before the first launch (dry-run shows the checklist).
- **Switch (2026-10-16):** `testqueue.py run --preflight` / `FO4SF_PREFLIGHT=1`, off by default; nothing on the PC
  changes until the PC session turns it on (§7). Implemented by Claude-cloud in #180 (`src/fo4sf/core/preflight.py`).

After T3: `core/tasks.py` + `core/worker.py` (result contract; done 2026-10-16 by Claude-cloud, #183, §8), then the
`Transform` adapter carrying the Z-first rotation fix (#102; done 2026-10-16 by Claude-cloud, #186, §9), then other
adapters only when a gameplay gate needs them.

## 5. Starting a task as a cloud session

At claude.ai/code (browser or the Code tab in the phone app), repository `fo4sf/fo4-to-starfield`, branch `main`:

> Do task T1 in docs/ai/leader-core.md. Branch `claude/leader-core-t1`. Follow AGENTS.md (commit subjects start
> with `Claude:`, synthetic unittests, `python scripts/guard.py`). Open a draft PR labelled `agent:claude`, `needs-qa`.

Swap `T1` for `T2` or `T3` once the previous one is merged. One task per session; a session that stops can be
reopened and continues from its branch.

## 6. The controller lease (T2) and its switch

**Files.** The leader folder, e.g. `C:\Modding\testqueue\leader`, holds `ledger.jsonl` (§1) and `controller.json`,
the lease: `owner`, `purpose`, `claimed`, `expires`, `ttl_s`, `renewed`, `released`, `forced`, `reason`, every time
an aware UTC timestamp. The ledger is the record and the file its cache: `src/fo4sf/core/controller.py` appends the
`controller_claimed` / `controller_renewed` / `controller_released` event first and then replaces the file atomically,
so a crash between the two leaves the event in the ledger and the file behind, never a lease without its event.

**Rules** (`Controller.claim` / `renew` / `release` / `valid_for`, the fold agrees with them):
- a lease is `held` until `expires`; `renew` moves `expires` by the lease's own `ttl_s` (or a new one);
- expired without a release = `ambiguous`: nothing that sends input runs on it, `renew` is refused; the holder may
  claim again (the gap goes into the ledger as `expired_for_s`) or release it; anyone else needs `--force --reason`,
  and the reason and the previous owner go into the ledger;
- another owner's claim is refused while a lease is `held`, unless forced with a reason;
- only the holder releases, unless forced with a reason; after a release anyone claims without force;
- an unreadable lease file counts as ambiguous: nothing renews it or takes it quietly, `--force --reason` takes or
  releases it and the ledger records `unreadable`;
- every claim, renewal and release reads, decides and writes under the lease's lock file (`controller.json.lock`,
  `filelock.py`), so two processes reading the same expired lease cannot both walk away with it; on Windows the
  atomic replace of `controller.json` is retried while another process has the file open for reading, and the
  runner treats a renewal that failed while the lease on disk is still its own as a warning, not a stop.

**CLI** (what the PowerShell scripts call; `python -I` finds the package through the wrapper):
```
python scripts\game\lease.py claim   --dir <leader> --owner Claude --purpose "walk gate" --ttl 28800
python scripts\game\lease.py renew   --dir <leader> --owner Claude
python scripts\game\lease.py release --dir <leader> --owner Claude
python scripts\game\lease.py status  --dir <leader> [--require Claude] [--json]    # --require: exit 0 only while held by Claude
```

**The switch, default off.** Nothing consults the lease unless told where it is:
- `testqueue.py run --lease-dir <leader>` (default `FO4SF_LEASE_DIR`; `--lease-owner`, default `FO4SF_LEASE_OWNER`,
  else `Claude`): checked before every launch and every test, renewed before every test, the run stops (resumable,
  `stopped: lease ...`) when the lease is missing, someone else's, released or expired; a `--dry-run` reports the same.
- `cycle.ps1`: with `FO4SF_LEASE_DIR` set it exits 9 before closing, redeploying or launching anything unless
  `FO4SF_LEASE_OWNER` (default `Claude`) holds the lease.
- `watchdog.ps1`: with `lease_dir` in `watchdog.json` (or `FO4SF_LEASE_DIR` as set when the watchdog started),
  Claude's activity is the lease's last claim / renewal / release plus the heartbeat file, not the last `Claude:`
  commit on any branch (the cloud sessions' commits tripped that); a lease held by the watchdog's own `lease_owner`
  does not count as Claude's activity, and a chain that stopped early is restarted by claiming that lease again;
  the chain is started only after the watchdog claims the lease as `lease_owner` (default `watchdog`) for
  `lease_hours` (default 8), never while someone else holds one; the chain inherits the two variables, so its
  runner and `cycle.ps1` check that lease.
- Unset, every script behaves as before this task; the test suite covers both states.

**Turning it on (the PC session, in a window it watches):** create the leader folder; claim the lease for the window
(`claim --owner Claude --purpose ... --ttl <seconds>`); set `FO4SF_LEASE_DIR` for the shell that starts the chain, or
`"lease_dir"` in `watchdog.json` for the watchdog; release at the end of the window. Turning it off is unsetting the
variable / removing the key; the ledger keeps the history either way.

## 7. The preflight gate (T3) and its switch

`src/fo4sf/core/preflight.py` is pure Python: its checks read nothing, a *probe* supplies the readings (the runner's
`PreflightProbe` in `scripts/game/testqueue.py` reads the PC; the tests use a fake), so every Windows-only reading
(Plugins.txt under `%LOCALAPPDATA%`, `Starfield.exe`'s version, the Saves folder, the ini files, the Guardian
database) sits in the adapter. Every check is `PASS`, `FAIL` or `UNKNOWN`; **one `FAIL` or `UNKNOWN` refuses** (the
brief's "any unknown → refuse"), and a reading that raises is `UNKNOWN` for that check, never a crash.

| Check | PASS when | FAIL / UNKNOWN when |
|---|---|---|
| `pin` | the staged `FO4Port.esm` has the queue's `plugin_sha256` | another hash / staging missing or no pin (UNKNOWN) |
| `deploy` | nothing deployed (cycle.ps1 deploys at the launch) or `Data\FO4Port.deploy.json` complete with the pinned `artifacts[FO4Port.esm].sha256` | interrupted install, another build / no sha in the manifest (UNKNOWN) |
| `experiment` | no experiment pinned and none installed, or the staged experiment's inputs equal the queue's `experiment_identity` and any install record is complete and the same | changed since planning, incomplete or other record, an experiment installed although the queue pins none (it would load with the build) / `pre_launch` without a pin, unreadable record (UNKNOWN) |
| `plugins_active` | every pinned experiment plugin, `FO4Port.esm` and the bridge are active where they are already listed in Plugins.txt (the rest install at the launch) | a listed plugin inactive (Starfield deactivated it on a load) or duplicated / Plugins.txt not locatable (UNKNOWN) |
| `load_order` | every non-implicit master of a pinned plugin is active, or is itself a pinned plugin or `FO4Port.esm` (both installed at the launch, and `order` moves the dependant after them); notes what `exp_install.py order` / `bridge_install.py order` will move | a master neither active, nor implicit, nor installed at the launch (cycle.ps1 would exit 7) / Plugins.txt not locatable (UNKNOWN). The planned `plugin_index` is **not** verified against the game's implicit plugins (which of them the owner's install loads is unresolved) |
| `game_version` | `Starfield.exe`'s file version equals the pin (`queue.json` `game_version`, else the ledger's `build_pinned.game_version`) | differs / no pin or not readable, e.g. not Windows (UNKNOWN) |
| `lease` | the runner's owner holds the lease (§6) | missing, someone else's, released, expired / no lease folder (UNKNOWN) |
| `stop_controls` | the queue's `STOP` and the chain's `STOP_ALL` can be created (folders writable); the state folder's too when it exists | a folder missing or not writable / no locations (UNKNOWN) |
| `guardian` | `guardian.db` present, readable, mode `running` | missing, unreadable, `paused`, `stopped` |
| `recovery_save` | the dedicated save `fo4sf_test_<build>` present, or not yet created (first launch) | created by an earlier run and gone / Saves folder missing or no save named (UNKNOWN) |
| `log_capture` | no bridge pinned, or the `[Papyrus]` logging keys in effect after the game folder's `Starfield.ini` is overridden key by key by `StarfieldCustom.ini` in My Games (`make_bridge.py ini`) | a key off or missing after the overrides / no ini found (UNKNOWN) |

The planners write no `game_version` today: the PC session adds `"game_version": "<Starfield.exe file version>"` to
`queue.json` (or a `build_pinned` event with it) before turning the gate on; until then the check is UNKNOWN by
design and the gate refuses.

**The switch, default off:** `testqueue.py run --preflight` (or `FO4SF_PREFLIGHT=1`) runs the gate once, right
after the lease line and before the first launch; the checklist goes to `run.log`, a refusal sets
`state.json` `status` to `stopped: preflight refused (<check> <status>, ...)` (exit 3, resumable) and appends
`blocker_opened` (`blocker: preflight`, the failing lines as `evidence`) to the ledger when a lease folder is set;
a `--dry-run` prints the checklist and refuses the same way; a later pass closes that blocker (`blocker_closed`),
so the report does not carry a refusal that no longer holds. Unset, the gate is not built and the runner is the one
of §6. The after-load activation check stays where it is (cycle.ps1 exit 8 after `exp_install.py active`).

## 8. Task cards and the worker result contract

**The card** (`src/fo4sf/core/tasks.py`, `TaskCard`): data with exactly the fields of the §4 cards: `id`,
`objective`, `owner`, `inputs[]`, `dependencies[]` (task ids whose PASS must be in the ledger), `timeout_s`,
`max_attempts`, `acceptance[]`, `evidence_required[]`, `recovery`, `not_in_scope[]`, and optionally `capability`
(what a decided IN_GAME result verifies or fails) and `campaign`. A card is refused with the field named when it
lacks an objective, an owner, an acceptance line or an evidence rule (`"none"` is a choice, an empty list is not),
when a number is not positive, when it depends on itself or carries an unknown field. `card.events(by)` is the
`task_queued` line that queues it, the card riding along so a resumed leader re-reads it; `card.not_ready(state)`
says why it cannot start.

**The result** (`src/fo4sf/core/worker.py`, `WorkerResult`): `task`, `attempt`, `outcome` (§2), `source` (§2),
`detail`, `evidence[]` (paths, hashes, URLs, read lines), `pins{}` (`commit`, `build_id`, `plugin_sha256`, ...),
`started`, `finished`, `by`, `verified` (the worker's claim). `violations(card, result)` lists every breach and
`Worker.finish` writes nothing while one exists:

| Rule | Refused when |
|---|---|
| the attempt is the card's | `attempt` < 1, beyond `max_attempts`, or not the attempt the ledger shows running |
| only PASS / FAIL are decided | an undecided outcome marked `completed` (model.Event refuses the line itself) |
| a verdict rests on evidence | a PASS or FAIL with no `evidence` while the card requires some |
| only an IN_GAME PASS verifies | `verified` claimed from any other outcome or source, or for a card without a capability; an OFFLINE PASS is recorded and the fold keeps the capability inconclusive |
| one attempt at a time | `start` while an attempt is running (or lost), after the task completed, or before its dependencies passed |
| nothing is lost silently | `Worker.expire` turns an attempt past `timeout_s` into an INCONCLUSIVE `task_finished` that says so (`expired: true`) |

What a task leaves in the ledger: `task_queued` (the card), `task_started` (`attempt`, `timeout_s`, `started`),
`task_finished` (`outcome`, `source`, `detail`, `evidence`, `pins`, `completed`), and for a card with a capability
one `capability_result` per decided or inconclusive attempt (a SKIPPED attempt says nothing about the capability).

**The report CLI:** `python scripts/leader_report.py --ledger <leader dir or ledger.jsonl> [--now <ISO>] [--json]`
prints the owner's eight bullets from the fold (§1), exit 1 with the reason when the ledger is missing or corrupt.
The capability bullets are those of the pinned build (`build_pinned`); results pinned to another `build_id` stay out
of "newly worked in game" until that build is the pin.

## 9. The Transform adapter: one reference matrix, in #102's order

`src/fo4sf/core/adapters/transform.py` holds the core's only `ref_matrix(rot)`: Bethesda angles turn clockwise seen
from the positive axis, so the matrix uses the negated angles, and the model turns about **Z first, then Y, then X**
(fixed axes), `R = Rx(-x) Ry(-y) Rz(-z)`. That is the order PR #102 verified on FO4's own precombined references
(146,463 of 146,728 tilted references with a unique instance; 52 of 52 core64c in-game readings within 0.05 m under
it, the X-first plan missing `ne_500m` by 1.89 m). With it: `apply`, `to_world`, `to_local` (the inverse is the
transpose), `metres` / `units` (70 per metre) and a frozen `Transform(pos m, rot rad, scale)` with `world()` /
`local()`. Pure Python; every new core consumer places a reference through it and nowhere else.

**Parity today** (`tests/test_core_transform.py` keeps this true on every push):

| Copy | Order | Agrees with the adapter |
|---|---|---|
| `scripts/game/routes.py` `ref_matrix` (used by `scripts/game/stairs_calib.py`) | Z first since 2026-10-13 | on every rotation (grid of 512, and #102's RockCliff05 example) |
| `src/fo4sf/exterior.py` `ref_matrix` / `to_world` (used by the exterior placement, `scripts/actors/navmesh_points.py`, `scripts/terrain/make_exp2d.py`) | X first, `R = Rz(-z) Ry(-y) Rx(-x)` | on heading-only rotations; differs on tilted ones (the 24 m top of RockCliff05 lands 10.2 m apart, 0.42 in the matrix) |
| `dotnet/PluginSpike/Program.cs` `RotateOffset` (door-local offsets: rigged door hinges) | X first (applied X, then Y, then Z) | same as `exterior.ref_matrix`; **not changed here** |

**What is deliberately not changed, and what each switch costs (the PC session's calls, one PR and one rebuild each):**
- `exterior.ref_matrix`: switching it to the adapter is one line, but every placement and navmesh point of a tilted
  reference moves (332,641 of core64c's 648,358 references have an x or y rotation): the core build, the exp2d-style
  navmesh input and every plan made from `objects.json` have to be re-staged and re-pinned, and the campaigns that
  read tilted objects (the northeast probe, the maples, the cliffs) re-planned. The 52-reading agreement in #102 says
  the adapter's order is the game's, so the switch is a correction, not a guess.
- `PluginSpike.RotateOffset`: port the order (apply Z, then Y, then X, i.e. `y1`/`z1` about Z first) with a C# test
  against the adapter's numbers; #102 counts 156 of core64c's 759 rigged doors off by more than 1 cm (up to 9.17 m,
  the tipped-over boxcar doors), so the interior and door plugins are rebuilt and their door campaigns re-pinned.
- `routes.ref_matrix` can call the adapter whenever `scripts/game` starts importing `fo4sf.core`; nothing moves.
- 85 references of 7 models whose precombined matrix matches no order (#102): unresolved; the adapter does not claim them.
