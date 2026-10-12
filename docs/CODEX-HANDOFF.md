# Codex / Claude / Grok status

Owner: project owner. Priority: connected Red Rocket -> Sanctuary -> nearby interiors -> wider Commonwealth ([owner direction in #31](https://github.com/fo4sf/fo4-to-starfield/issues/31#issuecomment-6117671801)). Keep existing interior failures as regressions.

## Acceptance

Walk Red Rocket-Sanctuary and its bridge/cell borders both ways; prove terrain remains loaded. Then enter source-linked interiors normally and return to the same exterior with correct position/facing, stairs and closed/open door collision. Cave triggers and Vault111 lift/sliding doors need explicit tests. Initial COC/ray hops are setup/loading evidence, not walking or door acceptance. Pin code, plan, plugin/archive hashes and persistent IDs; unreached/unreadable results are inconclusive. Preserve FO4 gameplay and native Starfield physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / locks

- Claude: collision/Havok, convert_static.py, pipeline.py, convert_batch.py, PluginSpike, terrain/actors, game scripts/staging/live control. No concurrent edits or other game input.
- Codex: deployment/recovery, identities/checkpoints/cache/output QA, Fo4Export/ReferenceLinks, animation/door bridge modules and tests, this status/archive. Shared sfnif.py changes need an exact scope claim. Codex owns exp_install.py compatibility with #78; Claude retains cycle/qstep and all live tests.
- Grok: acceptance oracle, route_eval.judge, terrain_evidence.py/tests. #69 still needs capture-provenance QA correction; identical XYZ may be independent stationary captures. No other game/control files without a new claim.

## Latest evidence / open work

Claude reports core64b NW short hops through Sanctuary/Vault111 to2km with matching terrain heights (#32, 6118693845). Earlier large-jump Boundary/seam conclusions need hop reruns; full continuous traversal and all directions remain open. Red Rocket objects/ground align in exp2c/exp2d. N1c NPC moved with156 converted NAVM records; N0/commanded arrival and cross-cell navigation remain unproven (#32, 6121240178).

Claude's supervised_1011:10 PASS/5 FAIL/2 inconclusive. Open: multi-part shutter motion, load-door activation, Vault114 cinder-block step and movable item. #78 cave entry/return is staged, not runtime-accepted. #79 multi-part rigs/clips/body fix is offline; native playback/moving-body linkage needs in-game proof. Eight-interior acceptance is incomplete; never combine builds.

Codex #34/#35 are on main: degraded checkpoints retry and immutable archive sources use streamed SHA. #86's four terrain dependency filesystem lookups are merged into #66 at85e342f:360 Windows tests (5 skips), Linux CI38306629144 and independent23-probe QA pass; resource reports/counts unchanged.

Reviewed #81/#80 are merged into #79 at29f3b83: generated skeleton/Open/Close dependencies remain tracked and small authored bind rotations are preserved.814 Windows tests (28 skips), Linux CI38307142896 and independent cache/matrix QA pass. Reviewed #83 is merged into #78 at75598ed: verified BA2 packing, recovery, --needs/order/plugin-only support, and install/order/uninstall guards for interrupted main recovery.883 Windows tests (38 skips), Linux CI38307143001 and independent QA pass. Parent trees match tested child heads.

#66/#78/#79 remain open for broader acceptance; these are parent-branch integrations, not runtime proof or main feature merges. Native playback/moving collision and cave entry/return/save still need live tests. #84 is the next independent deployment task: preserve edits at final replace/unlink boundaries; helpers assume one controller. No live install changed.

## Coordination

GitHub #29-32 is the inbox/status source. [History](handoff-archive/2026-10-07-codex-history.md). Keep below4KB; link experiments. Preserve staging/multi. No automation/local-team or live-control changes.
