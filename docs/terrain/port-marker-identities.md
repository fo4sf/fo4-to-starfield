# Interior arrival-marker reservations

Issue [#280](https://github.com/fo4sf/fo4-to-starfield/issues/280) records an
unresolved cross-plugin identity gap. Current cluster production and port
patching allocate interior arrival markers by door order. Reorder, insertion
and removal can change or reuse IDs even when terrain IDs remain stable.

`scripts/terrain/port_marker_ids.py` is a **proposal component**, not an active
pipeline fix. It changes no producer, plugin, map, ledger, installation or game.
Claude retains producer/staging ownership. Independent review is pending.

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

## Validation and remaining integration

Thirteen focused synthetic tests cover raw bootstrap, reorder/insert/remove/
reintroduction, full source ownership, retained reservations, append-only base
growth, actual and un-emitted namespace collisions, altered inputs, damaged
state, transform validation and range exhaustion.

A read-only production check imports all 15 markers from `integ_1017_doors`
against the original `integ_1017` and `terrain_core64j_doors` inputs. Reversing
the selected sources preserves the state bytes. All six source files retain
their pinned hashes. The initial prototype incorrectly required every base
map ID to have a record; that failed attempt is preserved alongside the
corrected result. Private evidence: `port-marker-reservations-work` on D:.

Required before a production fix:

- Persist the returned reservation state durably under one writer lease **before**
  either paired output is published; retain reservations after a failed build.
- Bind its hash to generation/recovery receipts. Missing state beside prior
  outputs must refuse; bootstrap is explicit, not automatic recovery.
- Make both cluster production and port patching consume the same allocation.
  The existing patcher still enforces sequential IDs and cannot consume plans
  containing retained gaps. Its HEDR and raw checks need coordinated updates.
- Add cross-process and interrupted-publication tests at those actual caller
  boundaries, then validate paired plugin/VMAD/marker output and obtain QA.
- Keep native outside/inside/return/save/reload acceptance with Claude.

The pure planner's retry test is not a crash-durability or concurrency test.
No native save-compatibility claim follows from these offline results.
