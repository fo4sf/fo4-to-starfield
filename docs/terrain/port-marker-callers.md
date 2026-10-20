# Pinned port-marker caller API (#280)

This is an offline caller-API proposal, stacked on #368/#279 and using reviewed
#281 store code. The owner authorized `make_cluster.port_index/doors` and
`vmad_patch.port_edits/check_port` plus tests. Other production functions are
unchanged. Claude retains stage orchestration, installation and game control.

## Contract

1. Explicitly initialize the dedicated store from checked original/patched plugin
   and map bytes using #281. Never recreate missing state during resume.
2. Open `port_marker_store.session(directory, expected_sha256)` using an
   independently preserved latest-state pin. Keep that lease open through BOTH
   real output publications and their checks.
3. Call `port_index(port, marker_writer=writer)` and `doors(...)`. It persists
   reservations before returning the proposed cluster. `port['_marker_plan']`
   exposes the exact Plan for the paired patcher. `doors_port` binds
   `marker_state_sha256`, `base_sha256` and `base_map_sha256`.
4. Supply that Plan, the producer receipt's state/map pins and original base
   bytes to `port_edits(..., marker_plan=plan, expected_sha256=...,
   base_raw=..., base_map_raw=..., base_map_sha256=...)`. It refuses mismatched
   assignments, source owners, destination cells/references, base lineage or pins.
   Preserve these pins externally with paired generation/recovery receipts.
5. Existing `patch_port` writes the checked edits. Call `check_port` with the
   same Plan/state/map pins and base map bytes. Planned mode permits retained
   gaps; unplanned mode still enforces legacy sequential allocation.

Removed marker IDs remain in the reservation ledger even when not emitted.
HEDR describes actual serialized records; it is not the ledger's high-water
mark. New sources allocate above retained reservations, including those absent
from the current output. Never infer future allocations from HEDR alone.

## Remaining gates

The current stage/patch CLI does not pass these optional API inputs. It retains
its existing sequential behavior. This proposal does NOT integrate the real
paired stage publication/recovery transaction or provide a resume adapter.
That needs a separate coordinated orchestration scope and fault tests at the
actual core-plugin/port-plugin publication boundaries. No whole-store rollback
protection exists without the independent latest-state pin. Publication across
two files is not made atomic by a reservation lease.

The new functional fault test writes cluster JSON followed by a raw patched port,
not a complete generated core plugin. It proves retained reservations, a real
competing process's exclusion while the lease is held, raw port verification
and retry within this API; it does not prove full-stage recovery. Native
outside/inside/return/save/reload testing remains with Claude.

## Validation

Original reproduction: after removing the first source, the old patcher refuses
retained marker `000805` because it expects `000804`; the old raw checker rejects
the valid gap's HEDR. Eleven new synthetic caller methods cover removal/reorder,
new source allocation without recycling, empty selection, legacy behavior,
wrong state/map pins (including byte-only map drift), tampered Plan assignments,
wrong destination source/owner/cell, closed writer, input drift, competing
process and failed-publication retry. Existing #281 identity/store tests remain.
No game assets, staging or installed files are used.

## Authorized stage command extension

The owner subsequently authorized the separate actual stage entrypoint and command/test edits.
See [paired generation protocol](paired-stage.md). The isolated implementation now calls
real core stage/check and port patch/check under the same lease; source QA and a
freshly pinned full-size paired build remain required. The earlier unwired-CLI
statements above describe #378 alone, not this later extension. No native verdict.
