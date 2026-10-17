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
| `Data/FO4SFExp.install.json`, `Data/FO4SFBridge.install.json` | `plugins_verified`, one per record (active_after_load from `exp_install.py active`) | `plugins` (since 270b0ec), `plugins_added` (`*Name` lines, the only key before 2026-10-12), `plugin` (the bridge record's one plugin), `plugins_replaced[].active`, `complete`, `pack` plus each plugin's sha256 from `files` / `source_sha256` (`exp_install.py:522,541`, `bridge_install.py:168,180`); the event names its record (`source`). The fold merges the events by plugin name, so Exp and Bridge together name both plugins; a record's event owns the names it lists, so a plugin a rewritten record drops is removed while the other record's entries stay; a changed sha256 is a different file and its `active_after_load` starts over from unknown (`state.merge_plugins`) |
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

### T3 — `core/preflight.py`, the deployment gate (brief §7)
- **Objective:** before any live task: deployed hashes match the pin, every experiment plugin active after the save
  loads (the 2026-10-14 load-order fix, generalised), load order as planned, game version equals the pin, lease held,
  STOP/Guardian reachable, recovery save and log capture on. Any unknown → refuse, ledger says why.
- **Owner:** Claude. **Dependencies:** T1, T2. **Acceptance:** each check has a synthetic pass and fail test; the
  gate is called by `testqueue.py run` before the first launch (dry-run shows the checklist).

After T3: `core/tasks.py` + `core/worker.py` (result contract), then the `Transform` adapter carrying the Z-first
rotation fix (#102), then other adapters only when a gameplay gate needs them.

## 5. Starting a task as a cloud session

At claude.ai/code (browser or the Code tab in the phone app), repository `fo4sf/fo4-to-starfield`, branch `main`:

> Do task T1 in docs/ai/leader-core.md. Branch `claude/leader-core-t1`. Follow AGENTS.md (commit subjects start
> with `Claude:`, synthetic unittests, `python scripts/guard.py`). Open a draft PR labelled `agent:claude`, `needs-qa`.

Swap `T1` for `T2` or `T3` once the previous one is merged. One task per session; a session that stops can be
reopened and continues from its branch.
