# Codex / Claude / Grok status

Owner: project owner. Goal: Red Rocket -> Sanctuary -> nearby interiors -> wider Commonwealth (#31). Keep interior failures as regressions.

## Acceptance

Walk Red Rocket-Sanctuary and its bridge/cell borders both ways; prove terrain remains loaded. Then enter source-linked interiors normally and return to the same exterior with correct position/facing, stairs and closed/open door collision. Cave triggers and Vault111 lift/sliding doors need explicit tests. Initial COC/ray hops are setup/loading evidence, not walking or door acceptance. Pin code, plan, plugin/archive hashes and persistent IDs; unreached/unreadable results are inconclusive. Preserve FO4 gameplay and native Starfield physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / locks

- Claude: collision/Havok, convert_static.py, pipeline.py, convert_batch.py, PluginSpike, terrain/actors, game scripts/staging/live control. No concurrent edits or other game input.
- Codex: deployment/recovery, identities/checkpoints/cache/output QA, Fo4Export/ReferenceLinks, animation/door bridge modules and tests, this status/archive. Shared sfnif.py changes need a scope claim; Codex owns exp_install compatibility and #89 exit protocol. Claude retains live controls.
- Grok: acceptance oracle, route_eval.judge, terrain_evidence.py/tests. #69 still needs capture-provenance QA correction; identical XYZ may be independent stationary captures. No other game/control files without a new claim.

## Latest evidence / open work

Claude reports core64b NW hops through Sanctuary/Vault111 to2km with matching heights (#32,6118693845); continuous walking/all directions remain open, older large-jump seam claims need reruns. Red Rocket ground/objects align. N1c moved with156 converted NAVM; commanded arrival/cross-cell paths remain unproven (#32,6121240178).

Open regressions: Fort Hagen shutter/frame collision and load-door prompt, Vault114 cinder-block step and movable physics. Cave/native playback need live proof; interior acceptance remains incomplete.

#34/#35 (main): degraded checkpoint retries and streamed archive SHA; sources remain immutable. #86 is in #66 at85e342f: four filesystem lookups,360 Windows tests (5 skips), Linux CI38306629144 and23-probe independent QA pass; reports/counts unchanged.

Reviewed #81/#80 are merged into #79 at29f3b83: generated skeleton/Open/Close dependencies remain tracked and small authored bind rotations are preserved.814 Windows tests (28 skips), Linux CI38307142896 and independent cache/matrix QA pass. Reviewed #83 is merged into #78 at75598ed: verified BA2 packing, recovery, --needs/order/plugin-only support, and install/order/uninstall guards for interrupted main recovery.883 Windows tests (38 skips), Linux CI38307143001 and independent QA pass. Parent trees match tested child heads.

#89 budget-resume fix is merged into #78 at02cfa8e: paused work returns4, completed/dry-run returns0;887 Windows tests (38 skips), Linux CI38319797231 and independent QA pass. Old batch_full hit12h and exited0 with1109 left; its chain ended. Remaining non-movable work estimates15-18 active hours plus waits/retries. An offline133-test diagnostic plan retains all16 cells/all49 failures and old2470f876 pin (~3-4h); independently checked, not scheduled/run. Live runner needs adoption before resume. The full batch remains backfill; old movable checks need corrected re-planning.

Parents #66/#78/#79 remain open; parent integrations are not main feature merges or runtime proof. Native moving collision and cave entry/return/save need live tests. #84 final replace/unlink races remain; helpers assume one controller. No live install changed.

## Coordination

GitHub #29-32 is the inbox/status source. [History](handoff-archive/2026-10-07-codex-history.md). Keep below4KB; link experiments. Preserve staging/multi. No automation/local-team or live-control changes.
