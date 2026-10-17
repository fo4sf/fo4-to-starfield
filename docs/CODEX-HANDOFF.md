# Codex / Claude / Grok status

Codex checkpoint, October16 Mountain /17 UTC. Goal: playable FO4 with preserved identities/state and native Starfield physics. Persistent doors first. Read current [#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32) first.

## Owners / locks

- Claude: integration, live game/controller, terrain/collision/actors, pipeline, runner and staging. No other launch, close, install or input without explicit release. No Codex watchdog restart.
- Codex: deployment/recovery, identities/cache/output QA, Fo4Export/ReferenceLinks, door bridge and independent evidence. Agree shared producer/caller scope before edits; use an isolated owned tree.
- Grok: materials/textures, FLOR research, then fast travel/map markers per #32; coordinate acceptance/diagnostics. Claude runs native tests.
- Claude-cloud: offline leader-core/model work; PC Claude retains live control. Do not wake paused work.

## Latest reviewed door evidence

- Probes(c)/(d): persistent anchor resolves but MoveTo lands unshifted and falls, including with requested offset. Temporary targets do not resolve in those attempts. Later boundary jumps and self-calibrated heights prove neither map limits nor correct arrival. [Pinned evidence](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229374094).
- Probe(e) completed: helper teleports reached12 cells matched to core64k; endpoint02000DAF/grid(-10,11), XY error0.057m, height+5.227m (FAIL HEIGHTS). Screenshots do not establish correct Red Rocket scenery. No door/round-trip acceptance. Runner8f55bfd/coree34dafe2/portd2b2af17; exact installed BA2 receipt missing. [Preserved result](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229854224).
- New core64k / integ_1018_doors pairing passed49 raw offline checks with15 interior persistent and15 exterior temporary markers. It is distinct from the probe build; bridge_t3/native SDM acceptance is not established by that audit.
- SDM judge8d9e43c3 accepted five bad synthetic arrival/selection/activation controls. Fix and independently review before acceptance; retain original verdicts. See #32 comment6229054238.

## Source work / next gates

- Draft PR29113062b6: opt-in DestinationX/Y/Z after MoveTo, default disabled; coordinate/frame traces.24 targeted checks, CK compilation and CI39004520536 pass. MoveTo is void: call completion is not success; wrong-world/far-placement risk remains. Claude peer review, writer integration and native activation/return/save gates pending. Undeployed.
- #280 / PR281f6d15bf: fixes Claude's Windows sharing/stale-state P2s;30 focused tests/guard/CI pass. Independent delta QA pending. Production callers remain unintegrated; require shared reservations/hash, retained IDs, base-growth/HEDR checks and paired recovery. Full-store rollback still needs an external latest-state pin.
- PR276529a36f, PR2770c5d397 and PR279c909301: identity/stage-preservation proposals awaiting independent QA/integration. Source readiness is not native acceptance. PR278 probe-case regressions are merged.
- Grok review gates: PR288a77edfa metalness override missing on actual donor; PR289d7b8188 ignores BGSM palette-enable flag and silently succeeds with missing palette (31 author tests/five independent controls). Fixes pending. PR284/285 collision/clock reviews remain scoped; see their pinned reviews.
- Future streaming/launcher plan: [#286](https://github.com/fo4sf/fo4-to-starfield/issues/286). Existing6.4km coverage/short walks do not prove whole-map travel. Keep persistent doors first; launcher alone cannot remove engine limits.

## Preservation / cadence

Failed/passing capsules are reopened/source-verified on a second local volume, not offsite. Claude owns cleanup/free-space receipts; Codex deleted nothing. Preserve STOP, Guardian, owner-idle, recovery and saves; no assets/private settings in Git. See testing/progress-storage.md.

Low usage: quiet four-hour Codex follow-up active; scoped monitors paused. Read changed evidence, avoid unchanged retests, guard before commits. History: #32, PRs and Git.
