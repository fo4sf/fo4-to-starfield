# Continuous evidence audit

Author: Codex. Offline synthetic evidence only.

`scripts/testing/continuous_evidence.py` exposes:

```python
inspect_door_trip(test: dict, obs: dict, folder: Path) -> dict
inspect_walk(test: dict, obs: dict, folder: Path) -> dict
```

The parent Commonwealth auditor owns CLI integration and outer campaign/queue/result
pins. This module never imports game runners or judges, controls a game, installs
files, edits evidence, or trusts a reported PASS. Existing Commonwealth
`file_bytes`, `capture`, `xyz`, `finite` and `vector` helpers load lazily to avoid
circular imports.

The result contains `status`, `issues`, `rows`, `capture_identities`,
`file_identities`, `offset` and `check_scopes`. Issues contain `status`, `class`,
`detail` and optionally `label`. MATCH describes only the listed checks.
Missing evidence is INCONCLUSIVE; contradictory evidence and capture replay are
MISMATCH issues. Overall status matches the parent wrapper: INCONCLUSIVE if any
required evidence is missing, otherwise MISMATCH if issues remain, otherwise MATCH.
Mismatch issues are retained when the overall result is inconclusive.
`runtime_accepted` and `acceptance_gate` are always false.

## Source and experiment pins

The trusted normalized queued test adds:

```json
{
  "evidence_pins": {
    "source_commit": "<40 lowercase hex>",
    "source_files": {"runner-source.py": "<sha256>"},
    "plan": {"file": "plan.json", "sha256": "<sha256>"},
    "experiment_files": {"core.esm": "<sha256>", "core - Main.ba2": "<sha256>"},
    "experiment_source_files": {"Data/example.dat": "<sha256>"}
  }
}
```

Digests are 64 lowercase hexadecimal characters. Bundle pinned source snapshots
under safe flat filenames in the attempt folder; their bytes are checked without
execution. `plan.json` is a retained `{"test": ...}` snapshot of the entire
normalized queued test **excluding `evidence_pins`**, avoiding a self-referential
hash. The parent must bind this queued test/snapshot to its campaign and planner.

Observation metadata adds `source_commit` and `install_file`, a safe filename for
a retained JSON snapshot containing `complete: true`, `files` matching the planned
experiment file hashes, and `source_files` matching planned experiment source
hashes. Do not replace missing expected identities with whatever is installed.
Legacy receipts lacking these fields remain inconclusive.

This checks retained pin binding. It does **not** rehash current installed archives
or prove which inputs the engine loaded. Actual installation verification and
receipt provenance remain separate parent checks. No game assets need bundling.

## Independent read evidence

Every invocation retains a raw read event, including settled-pair members, route
steps, rereads, setup reads, diagnostic probes and reload reads:

```json
{
  "read": "120.00 17.00 2.00",
  "read_capture": "read-000.png",
  "read_ocr": "read-000.txt",
  "read_invocation": {
    "id": "attempt-1:read-000",
    "capture_id": "attempt-1:native-000",
    "source": "native_console",
    "session_marker": "FO4SF_READ_<64 lowercase hex SHA256 of UTF-8 invocation id>",
    "t": 3.0,
    "capture_sha256": "<sha256 of original PNG>",
    "ocr_sha256": "<sha256 of UTF-8 transcript>",
    "ocr_capture_id": "attempt-1:native-000"
  },
  "cmds": ["ClearConsole", "player.getpos x", "player.getpos y", "player.getpos z"]
}
```

`t` uses one monotonic attempt clock in seconds, bounded to one day. IDs are unique
across invocations; preserve original native capture IDs through copying and
preprocessing. The auditor verifies PNG containers/pixel decoding and hashes,
detecting physical-file, hardlink, invocation-ID, native-ID and OCR-file reuse.
Independent captures with equal pixels or equal XYZ are allowed. Prepared images
cannot replace original native captures. The parent must check returned physical
and invocation identities across attempts/tests too.

Every console invocation requires `read_invocation.session_marker`, defined as
`"FO4SF_READ_" + sha256(read_invocation.id.encode("utf-8")).hexdigest()`. The token
uses only the fixed prefix and 64 lowercase hexadecimal digits, and must match
that invocation ID exactly. The same rule applies to reread/start/away invocation
metadata. IDs must be fresh and unique for each actual read, never recycled.

Retained UTF-8 OCR must show exactly one standalone line containing that token
after the final `ClearConsole` context and **before** all accepted XYZ/angle
replies. Replies before the challenge are ignored. Missing, wrong, unsafe,
duplicated or unbound challenges leave freshness unverified/INCONCLUSIVE.
`ClearConsole` alone does not prove freshness: it can belong to a complete older
session when the new marker/echo is lost.

Accepted position replies are complete, separate, labelled X/Y/Z lines in order,
with exactly two decimal places (`GetPos: X >> 120.00`). Split numbers such as
`-1 593.51`, trailing numeric/text residue, variable decimal counts, bare columns,
duplicates and partial coordinate sets remain inconclusive. No earlier axis is
borrowed. Reported XYZ must agree with this parser within 0.011 m.

**Producer/runtime protocol remains pending Claude verification.** The producer
must demonstrate a safe way to make the invocation challenge visibly appear in
the native console capture before its XYZ/angle replies and retain the exact OCR
transcript and original PNG. This document specifies a consumer contract and
synthetic fixture format; it asserts no untested game command for emitting the
token. Current legacy records without a visible invocation-bound challenge cannot
qualify as fresh evidence. Actual marker emission, console retention and heading
capture still need native captures/runtime proof; the auditor neither performs
fresh OCR nor authenticates the capture service.

This contract is **not integrated** with Claude PR107 at
`2e3c961104af9301e020ef22d398755add3b7e51`, whose reported producer format uses
`fo4sfr<8hex>`, separate angle capture/nonce, and per-invocation Work `read.json`.
Those raw outputs do not supply this normalized evidence contract and must not
be claimed accepted. Missing normalized nonce/facing evidence stays INCONCLUSIVE;
normalization/protocol agreement and native producer proof remain pending Claude.

Command lists must begin with exactly one `ClearConsole`, followed by player
`getpos` X/Y/Z in order and, for facing reads, `player.getangle z`. Validated turn
commands remain allowed after the clear. Extra actor selections, duplicated or
reversed read commands cannot establish the recorded session. Only explicitly
planned diagnostic probes may use ordered `prid <ref>` and unqualified `getpos`;
anchors, route steps, arrivals and reloads require player position evidence.

Facing reads also retain numeric `heading`, a recorded `player.getangle z` command
and one complete two-decimal `GetAngle: Z >> ...` reply after the same challenge.
Split/trailing angle values are also refused. Both metadata and parsed OCR
headings must be finite in 0..360 before modulo comparison;
comparisons wrap at 360 and allow 20 degrees. Actual producer angle capture remains
pending Claude/runtime proof.

Scalar keys `start_read`, `away_read` and `reread` use matching metadata prefixes:
`start_read_capture`, `start_read_ocr`, `start_read_invocation`, etc. Settled
`spawn_reads`, `arrival_reads`, setup `reads` and reload `reads` become lists of full
normal read-event objects. Their final two consecutive reads must agree within
0.3 m on every axis, be at least 3 seconds apart and match the summary XYZ.
Summary values or `settled: true` alone do not establish settling.
Facing summaries and expected/saved facing checks use the final settled read's
heading, bound to the same read as the selected XYZ and time. Setup and arrival
read windows must begin after the preceding spawn/route stage; their last read
alone cannot hide an earlier invocation from before that stage.

Each step/leg adds `hud: true`, `hud_capture` and `hud_invocation` using the same
ID/hash/time fields with `source: "native_screen"`. HUD capture must be independent
of the console capture, within 120 seconds of its read. HUD recognition and popup
interpretation remain reported observations/manual review; recorded popup text is
inconclusive. Missing per-read proof is never inferred from an arrival/event shot.

## Walk

- Finite XYZ spawn/local/offset values agree, `offset_from: "spawn"` is present,
  and the arrival has independent settled reads.
- There are 2..401 leg objects with integer `n` contiguous from zero. Explicit
  `used_from` selects `read` or `reread`, and `used` matches that actual raw event.
  Rereads retain separate later captures/OCR/metadata. A disagreeing replacement
  needs `read_rejected: "implausible"` and a first displacement actually violating
  the allowance while the replacement does not. `confirmed: true` requires
  independently agreeing raw reads within 1 m. Every retained reread must follow
  its primary within 120 seconds, even when `used_from` selects the primary.
  The following leg's hold/read chronology begins after completion of the reread.
- The first leg is within 3 m of settled arrival/setup. Setup has a later
  independent settled pair and reaches its planned XYZ start.
- Every leg has full commands/HUD/capture evidence, including terminal reads.
  Nonterminal legs use `action: "aim"`, a matching typed finite Z heading, and
  `hold_ms` in 100..10000. The final leg uses `action: "done"` with
  `walk_stopped: "goal"`. Only validated reads/turns are allowed during routes.
  Setpos and other recovery commands fail.
- Consecutive XYZ moves allow at most 9 m/s over the previous hold, plus 2 seconds
  and 1 m slack. Read times account for holds with at most 120 extra seconds.
  Ordered retained XYZ witnesses reach kept waypoints and the goal.
- Borders are recomputed analytically from translated route geometry, supporting
  arbitrary offsets and repeated occurrences. Ordered neighboring-cell read
  transitions must match exactly. One transition cannot satisfy two occurrences.
  Sparse/multiple/simultaneous ambiguous crossings stay inconclusive. Optional
  declared local inventories must also agree with route geometry.
- `ground_path` names the **exact planned file**, or `ground` names a safe flat
  file in the attempt folder. `ground_sha256` is mandatory and exact bytes are
  read. Absolute planned paths are supported; relative traversal and linked final
  files are refused. Invalid/nonfinite terrain schema cannot supply evidence.
- Bridge witnesses use only matching owner nodes in pinned ground: spatial
  tolerance 0.75 m, height tolerance 0.6 m. At least two ordered contacts span the
  bridge within 3 m, bracketed by earlier/later route reads. Stationary contacts
  do not establish progression. Full terrain interpolation/contact, collision
  loading and material acceptance remain explicitly out of scope.

## Door trip

Planned `outside.route` and `inside.route` each have 2..64 finite XYZ waypoints.
Legs are ordered `in`, `out` with `mode: "route"`, explicit zero `teleports`,
matching route coordinates, independently read starts and nonempty readable
`steps` numbered from zero. Exterior routes add the offset; interiors do not.
Each step retains a normal read, HUD evidence, `state: "here"` and `ms` in
100..10000. `walked_ms` equals the holds, at most 600000. Unread load-terminal
steps cannot be filled from a later arrival.

Checks cover ordered route/activation-range XYZ witnesses, interior in-arrival,
merged exterior out-arrival, independent settled pairs, expected
`inside.arrival_heading` / `outside.arrival_heading`, and arrival-facing summaries.
Reload needs an independently read position over 5 m away followed by later
settled restoration of saved XYZ/facing and the named save record. Actual save
contents and engine save/load execution remain outside this interface's scope.
The away read must follow the settled out-arrival, and the restoration read
window must begin after the away read.
Door ground/contact validation is also out of scope. If a door test explicitly
supplies a ground identity, its exact file/hash/schema is checked rather than ignored.

`trigger: "near"` remains inconclusive NEARONLY even if the door loads; ordinary
triggers are `walk` or `e`. Planned `probes` and observed `probe_reads` retain full
events and matching `ref` IDs. Object commands use `prid <ref>` and unqualified
`getpos`. Rows expose local/merged XYZ residuals as **diagnostics**, not proof of
arrival frames or engine persistent-reference semantics.

## Validation

```text
python -B -m unittest discover -s tests -p test_continuous_evidence.py -v
python -B scripts/guard.py
```

Synthetic fixtures cover positive schemas, independent equal-pixel images, replay,
hardlinks, sparse legacy records, raw/used disagreements, omitted legs, anchors,
setup, source/install/ground pins, stale OCR, NaN/malformed fields, commands/holds,
route/goal witnesses, bridge progression, repeated borders, door frames/facing
and last-try NEARONLY. Tool output establishes neither engine/material acceptance
nor authority to control the current game. This module does not implement STOP
controls or modify any Claude runner/judge.
Focused protocol regressions additionally cover complete stale sessions, wrong or
absent challenges, challenge ordering, split/trailing numeric residue, exact
two-decimal position/angle replies, and parent-compatible status precedence.
Independent QA regressions cover object reads credited as player travel,
reversed commands, primary-selected confirmations before/after their route
window, pre-trip reloads, arrival windows overlapping approach steps, facing
borrowed from a different position/read, changed final arrival/reload facing,
and out-of-range OCR angles disguised by wrapping.

Current-session OCR must retain the ordered actor-qualified XYZ query echoes;
player reads require `player.getpos x/y/z`, including confirmation rereads.
Explicit object commands cannot be overridden by player-command metadata.
Missing query echoes leave actor binding inconclusive. Diagnostic probes permit
unqualified object queries; any visible selection must match their planned ref.
