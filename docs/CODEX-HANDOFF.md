# Codex / Claude / Grok status

Owner goal: connected Red Rocket-Sanctuary-cave slice with Fallout 4 gameplay and Starfield native physics; focus persistent doors. Coverage and offline checks are not gameplay acceptance. Latest issue32 claims override this snapshot.

## Ownership and controls

Claude leads and owns game/controller, collision/terrain/actors, pipeline and runner/staging. No Codex launch, close, install, input or active watchdog restart without explicit release; never adopt the owner's game. Codex owns deployment/recovery, identities/cache/output verification and door bridge. Use isolated trees and public exact scopes; preserve concurrent edits. Grok owns assigned oracle/export work. No extra agents or waking paused workers. Local inference only through Guardian in a coordinated no-game window.

Preserve STOP/Guardian/owner-idle/recovery controls, failed evidence and original stages. No game assets/saves/private settings in Git; no money/passwords/purchases/paid fallback/outreach/history rewriting. Guard before commits, independent QA before integration. Low usage: targeted checks, no unchanged broad reruns.

## Persistent-door work

- PR265 combines227/6e7fc62 and261/9f57a64 with main241/246; inherited by267. Stable door/ordinary ACTI, TERM/TMLM and light IDs, legacy light-before-door ordering, raw VMAD/marker checks and exact bootstrap pass offline. Combined allocator/publication integration still needs independent QA and native save validation.
- PR261 has three reproduced review findings: linked source README overwritten; low24 lookup accepts a master-owned reference; existing VMAD replaced before the later checker refuses. This integration inherits that source unchanged. Claude owns those fixes and the native Mart Step0/return/save-reload gate. Historical merge offsets are not current measurements.
- PR262/4ab2d99 count fix passes offline/CI; peer QA pending.260/255 remain proposals.256 carries the return patch toward main; native XTEL and scripted routes remain separate.
- PR227 persistent IDs still needs full-size/bootstrap resources, caller/checker integration and native save validation. Existing stages require explicit byte-identical migration; never reset ledgers or silently renumber old saves. Adding regional markers must preserve existing door destinations.
- PR267/0958585 audits source/map reservations and checksum/output generation under the writer lease. Includes main7200aa5 workshop IDs and benches' native FURN links/source REFRs.130 targeted tests and CI38972933294 pass; legacy station bytes match main, persistent reorder/growth/removal preserve doors and bootstrap is byte-identical. Draft, peer QA/full-size/native gates remain.
- PR269/3939dd0 binds check/verify-data receipts to source/map/ledger/plan contents.13 false acceptances reproduced;93 targeted tests and CI38974373514 pass. Old receipts require a fresh check. Freshness only; no active-stage upgrade.
- codex/persistent-check-lease at269 holds the .NET audit lease through Python raw checks, revalidates before reports and replaces only sequential-order assertions.111 unique targeted tests pass (9 new session cases); writer exclusion, missing VMAD, input drift, cancellation and child crash covered. Raw terrain body is stubbed in wrapper tests: full-stage check is still unverified. Independent QA, full-size/bootstrap and native door/save tests remain gates. Source-only; no core64i migration.

## Preservation / next

Private evidence: persistent-check-lease-20261016 and prior persistent-door-verification/stations packets under test-plans. Verify archives before cleanup; D: is local, not offsite. Originals retained. Next: peer QA, full-stage checker/full-size bootstrap and Claude's native return/save checks. Scoped monitors stay paused; low-usage follow-up stays active until owner pauses it.
