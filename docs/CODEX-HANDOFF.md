# Codex / Claude / Grok status

Owner goal: connected Red Rocket-Sanctuary-cave slice with Fallout 4 gameplay and Starfield native physics; focus persistent doors. Coverage and offline checks are not gameplay acceptance. Latest issue32 claims override this snapshot.

## Ownership and controls

Claude leads and owns game/controller, collision/terrain/actors, pipeline and runner/staging. No Codex launch, close, install, input or active watchdog restart without explicit release; never adopt the owner's game. Codex owns deployment/recovery, identities/cache/output verification and door bridge. Use isolated trees and public exact scopes; preserve concurrent edits. Grok owns assigned oracle/export work. No extra agents or waking paused workers. Local inference only through Guardian in a coordinated no-game window.

Preserve STOP/Guardian/owner-idle/recovery controls, failed evidence and original stages. No game assets/saves/private settings in Git; no money/passwords/purchases/paid fallback/outreach/history rewriting. Guard before commits, independent QA before integration. Low usage: targeted checks, no unchanged broad reruns.

## Persistent-door work

- PR265, isolated codex/scripted-door-identities, combines227/6e7fc62 and261/9f57a64 with pinned main edd2400 (241/246). Durable keys cover door ACTI/arrival plus ordinary ACTI, TERM/TMLM and LIGH/light references. Four mixed persistent cases refused before the added keys; mixed reorder/growth/removal/reintroduction and byte-identical explicit bootstrap now pass. Legacy light IDs precede scripted bases/arrivals; raw checks count both ACTI kinds and check VMADs/markers. Original branches/stages untouched. Independent QA required; production caller/checker and native save gates remain open.
- PR261 has three reproduced review findings: linked source README overwritten; low24 lookup accepts a master-owned reference; existing VMAD replaced before the later checker refuses. This integration inherits that source unchanged. Claude owns those fixes and the native Mart Step0/return/save-reload gate. Historical merge offsets are not current measurements.
- PR262/4ab2d99 persistence-count fix:9 state/repeat controls and3 byte-identical CLI comparisons; CI/CodeQL pass, independent QA pending. PR260 transform reuse and255 CLI refusal remain source proposals. PR256 carries the reviewed return patch to main after253 merged only into a branch; native XTEL and scripted routes remain separate.
- PR227 persistent IDs still needs full-size/bootstrap resources, caller/checker integration and native save validation. Existing stages require explicit byte-identical migration; never reset ledgers or silently renumber old saves. Adding regional markers must preserve existing door destinations.
- PR267 codex/persistent-door-audit adds --check-identities: existing checksum/output generation plus source/map reservations under the writer lease; no artifact/recovery writes.9 original actual-CLI cases and be19ac6 CI38971463420 passed. Integrated pinned main7200aa5 (266): workshop semantic IDs, benches keep master FURN bases and source REFR reservations, audit checks their kind/owner. Four new mixed station/door cases pass; reorder/growth/removal preserve old destinations, explicit bootstrap is byte-identical. Legacy station output also matches main7200aa5 byte for byte. Source-only, peer QA/caller integration pending; no core64i migration or native acceptance.

## Preservation / next

Private evidence: test-plans/persistent-stations-integration-20261016, persistent-door-audit-20261016 and earlier265/242/261 packets. Verify archives before cleanup; D: is local, not offsite. Originals retained. Next: peer review267/265, persistent caller/checker integration, full-size bootstrap and Claude's native return/save checks. Scoped monitors stay paused; low-usage follow-up stays active until owner pauses it.
