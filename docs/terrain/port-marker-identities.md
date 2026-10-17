# Interior arrival-marker reservations

Issue [#280](https://github.com/fo4sf/fo4-to-starfield/issues/280) records an
unresolved cross-plugin identity gap. Current cluster production and port
patching allocate interior arrival markers by door order. Reorder, insertion
and removal can change or reuse IDs even when terrain IDs remain stable.

The planner and reservation store are **proposal components**, not an active
pipeline fix. Production callers, plugins, maps, installation and game are
unchanged. The explicit store API writes only its dedicated reservation
directory. Claude retains producer/staging ownership; independent QA is pending.

## Component contract

`bootstrap(base_raw, base_map_raw, patched_raw, patched_map_raw, doors,
plugin=..., core_plugin=...)` imports an existing generation's actual marker
IDs. It verifies the original and patched raw plugin with the existing port
checker, checks the complete map delta, source/reference ownership, emitted
destination cells, marker transforms, unique canonical sources and IDs. It
does not assign replacement IDs by the current input order.

`reserve(state_raw, expected_sha256, base_raw, base_map_raw, sources,
plugin=...)` requires an externally pinned state hash. It returns a `Plan`
containing serialized state bytes, their SHA256 and selected source-to-ID
assignments. Full source FormKeys and the target plugin owner distinguish
identities. Removed markers remain reserved; new sources allocate above the
reserved range, independent of the order in which new sources were supplied.
Malformed/duplicated state, changed owner, exhausted IDs and namespace
collisions refuse. Neither function performs I/O.

Base growth may append records while retaining prior source IDs, raw record
bytes and record placement. A changed existing base record needs a separately
reviewed migration. Both emitted base records and mapped-but-unemitted base
IDs remain unavailable to marker allocation. This matters in the current real
port: its 55,033 map entries include 623 IDs with no emitted record.

## Reservation storage

`port_marker_store.initialize(directory, ...bootstrap arguments...)` requires a
brand-new dedicated directory and runs the checked bootstrap. Existing and
partially initialized directories refuse; missing state is never recreated.
The prepared bootstrap bytes remain available if initialization is interrupted.
Partial initialization needs explicit reviewed restoration, not a reset flag.

`session(directory, expected_sha256)` acquires a nonblocking OS writer lock.
Keep that context open through the separate caller's paired-output transaction.
Its `writer.reserve(...)` returns assignments only after flushing and publishing
the new reservation state. No-op plans do not add journal entries. Prior state,
prepared state and intent evidence remain; completion appends another receipt.
The lock file is retained to prevent split locks between cooperating processes.

An interrupted reservation transaction refuses ordinary resume.
`recover(directory, before_sha256=..., after_sha256=...)` requires explicit pins
for exactly one unresolved intent. It verifies both preserved states and an
append-only transition, completes state publication if necessary, and records
completion without deleting evidence. Even a failure before state replacement
retains the proposed reservations after recovery. Old pins refuse after a new
generation commits. Restoring old state bytes and their old pin also refuses
when retained journal evidence shows a transition out of that state. A completion
without its intent refuses, and recovery cannot publish an endpoint superseded
by a later transition. Evidence is retained; the store does not silently choose
or restore a generation. This recovery never installs or repairs plugins.

A rollback of the entire store, including its journal, cannot be detected from
those rolled-back bytes alone. The production caller must bind the expected
latest state hash to independently preserved paired-output/recovery receipts.

Locks protect cooperating writers. A direct edit detected while the session
is active refuses without overwriting that edit; the final filesystem replace
is not a CAS against actors bypassing the lease. File fsync/flush and
same-directory replacement are used; process interruption tests do not establish
hardware power-loss or network-filesystem guarantees.

## Validation and remaining integration

Thirteen focused synthetic tests cover raw bootstrap, reorder/insert/remove/
reintroduction, full source ownership, retained reservations, append-only base
growth, actual and un-emitted namespace collisions, altered inputs, damaged
state, transform validation and range exhaustion. Nine store tests add actual
second-process exclusion, actual process termination before and after state
replacement, explicit recovery, missing/partial initialization, altered recovery
evidence, direct edits and hardlinked state refusal. A reproduced recovery gap
initially allowed newly assigned IDs below the prior reserved range; the fixed
transition check refuses it. Its failing and passing evidence is retained.
Four additional regressions reproduce and reject restored initial/intermediate
state, a completion whose intent is missing, and recovery to a superseded
endpoint. The first two formerly allowed a reserved ID to be issued again;
the latest intact state still advances without reusing those IDs.

A read-only production check imports all 15 markers from `integ_1017_doors`
against the original `integ_1017` and `terrain_core64j_doors` inputs. Reversing
the selected sources preserves the state bytes. All six source files retain
their pinned hashes. The initial prototype incorrectly required every base
map ID to have a record; that failed attempt is preserved alongside the
corrected result. A subsequent replay of those frozen inputs through the new
private store persists and reopens the exact same 15-marker state bytes.
Private packets: `port-marker-reservations-work` and `port-marker-store-work`
on D:. None of this changes the active staging or installation.

Required before a production fix:

- Wire the store into the caller under one writer lease **before** either paired
  output is published; retain reservations after a failed build. Bind its hash
  to paired-generation/recovery receipts, not merely reservation-only receipts.
- Make both cluster production and port patching consume the same allocation.
  The existing patcher still enforces sequential IDs and cannot consume plans
  containing retained gaps. Its HEDR and raw checks need coordinated updates.
- Add cross-process and interrupted-publication tests at those actual caller
  boundaries, then validate paired plugin/VMAD/marker output and obtain QA.
- Keep native outside/inside/return/save/reload acceptance with Claude.

The store process tests cover reservation publication; they do not cover either
plugin publication boundary. No native save-compatibility claim follows from
these offline results.
