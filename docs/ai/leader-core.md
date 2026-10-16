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

After T3: `core/tasks.py` + `core/worker.py` (result contract), then the `Transform` adapter carrying the Z-first
rotation fix (#102), then other adapters only when a gameplay gate needs them.

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
  `FO4SF_LEASE_OWNER` (default `Claude`) holds the lease; the runner puts its own effective folder and owner into
  the environment of every PowerShell step (`Runner.ps_env`), so `--lease-dir` / `--lease-owner` given as flags
  reach it too.
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
