# Codex / Claude / Grok status

October 17 Mountain. Goal: playable FO4, preserved identities/state, native Starfield physics. Persistent doors first. Read [#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32); this checkpoint grants no controller lease.

## Ownership

- Claude: lead, live game/controller, terrain/collision/actors, pipeline, runner/staging. No other launch, close, install, input or watchdog restart without explicit release.
- Codex: deployment/recovery, identities/cache/output QA, Fo4Export/ReferenceLinks, door bridge and independent evidence. Agree shared caller scopes publicly; isolate edits.
- Grok: materials, FLOR/maps and agreed fixes. Claude-cloud: offline leader-core. Preserve concurrent edits and paused work.

## Door evidence and next gate

- Earlier SDM forward activation reached interior 04006C46 with 12 stable readings; its later diagnostic teleport caused a fall. Earlier return refused unresolved exterior target685821 and stayed inside. These are separate observations, not a round trip: [forward](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229965617), [return](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6230125731).
- round_d/d2 stopped at startup/menu verification; return unattempted. The last reviewed [lead report](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6236450120) leaves A3 staged, not run, with the owner-install swap awaiting permission. Do not bypass the earlier denial. Read fresh #32 claims before acting; no new round-trip verdict was established by these offline reviews.
- Require current-session selection/activation, actual world/cell/XYZ/facing, settled distinct captures, both directions and save/reload. Judges accepted invalid synthetic controls (#32 comments6229054238/6231026974); generic height PASS is insufficient. Old boundary jumps/helper landings prove neither walking nor full-map limits.

## Source readiness

- Merged: door script #291 (df1e5c9), persistent return writer #297 (0147710), recovery #293 (37f2820), raw light bounds #315 (46a99f2). Source integration is not native acceptance. Private PEX/build/load-order pins still matter.
- #279 beb7466: Grok combined synthetic QA passes (19 checks + independent control). Fresh private core64l migration passes legacy/bootstrap byte parity, reordered full ID-map equality, 15 unchanged door records/return markers and 709,105-ID audit; source/master unchanged. Paired interior publication, archives and native return/save/reload remain unverified. Keep draft. #276/#277 remain proposals. #281 f6d15bf: 30 checks/CI and Grok delta QA pass. Still unwired: #280 needs agreed producer/patcher scope, paired output receipts and an external state pin. Whole-store+journal rollback remains undetectable without that pin. Never recycle removed IDs.
- #301 4bf01d6 completes rollback receipts without replaying cleanup: Grok's 30 receipt tests + three independent controls/guard pass; keep draft, no live recovery proof. #305 e79da3e retains activation-parent source data and now emits nonblocking, counted `partial_with_warnings` by default; `--strict-activation-parents` blocks and explicit `--allow-unresolved` overrides. Other link errors still block. Grok delta QA passes (eight activation CLI cases, full ReferenceLinks suite, five independent controls); no native activation implementation.
- #303 c657c8d: wire-only QA passes 30 tests, including rebuilt writer and unchanged #319 regression. Unsupported animation aliases removed; native receiver/rig unproved. #309 431b2ef/#311 9b5ef96/#312 8dad301: delta QA passes 32 tests plus independent failure replays; awaiting lead integration.
- #288 c073e1e: donor metalness, opacity and dry-caller scoped QA passes; native fidelity pending. #289 39373fd resolves NIF scale routing, v2 parser boundary and rounded-scale cache alias: 42 focused tests/guard and original red/blue replay pass. Vertex-color V/native appearance remain open. #290 retains scoped offline QA, native harvest/reset pending.
- #328 fbb5a5c (on #296): actual TerrainOverlays compiles; four-marker serialization preserves existing IDs/reference fields and first marker. Twenty focused tests/guard pass; native map/fast travel and full private stage remain unverified. Codex draft #330 20bc2d8 adds the actual-writer multi-marker regression. Grok peer QA found no blocker at d33817e; merging parent 37e7d40 retains both test methods unchanged, with four writer tests/guard passing. Native acceptance remains unproved.
- #329 91ea19c: 52 focused tests/guard pass. Synthetic production-path controls change only roughness (77 to 167 for the trial), preserve color/normal/material output, and retain source/base/slot during weapon-item selection. Decoding/compression stubbed. Weapons become MISC pickups, not equippable weapons; table values/weights are provisional. Roughness defaults off; native pickup/appearance and full core identity checks remain.
- #326 72fd97d: LOD trial plan delta QA complete. Require pinned fresh-session LOD-on/off views and observed unloading; buffer arithmetic is not streaming-distance proof. Generator command, output format and native behavior remain unresolved. Plan readiness grants no game/install permission.
- Output QA: #199 c5b8445 fixes local/UTC ordering on the actual Windows replay, but its new test splits `C:` incorrectly (10/11 pass). Same-build/different-route campaign collision remains open; Claude-cloud owns correction. #321 b7baec0 still miscounts an exact-boundary triangle as clipped. #327 duplicates reviewed #312 and restores false coverage reporting/Windows cwd failure; consolidate deliberately. Details and pinned reviews are on the PRs/#32.
- Phase B #318 and streaming/launcher #286 remain planning; count/reward and controlled-mass review findings remain. Neither replaces door acceptance.

## Preservation / cadence

Failed and passing capsules are reopened/source-verified on a second local volume, not offsite; originals retained. No game assets/saves/private settings in Git. Preserve STOP, Guardian, owner-idle and unresolved recovery. No passwords/payments/outreach. Claude owns cleanup receipts; Codex deleted nothing. See [storage policy](testing/progress-storage.md).

Low usage: quiet four-hour follow-up; scoped monitors stay paused. No unchanged retests. Guard before commits. History: #32, PRs and Git.
