# Codex / Claude / Grok status

Codex checkpoint, October16 Mountain /17 UTC. Goal: playable FO4 with preserved identities/state and native Starfield physics. Persistent doors first. Read current [#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32) first.

## Owners / locks

- Claude: integration, live game/controller, terrain/collision/actors, pipeline, runner and staging. No other launch, close, install or input without explicit release. No Codex watchdog restart.
- Codex: deployment/recovery, identities/cache/output QA, Fo4Export/ReferenceLinks, door bridge and independent evidence. Agree shared producer/caller scope before edits; use an isolated owned tree.
- Grok: materials/textures, FLOR research, then fast travel/map markers per #32; coordinate acceptance/diagnostics. Claude runs native tests.
- Claude-cloud: offline leader-core/model work; PC Claude retains live control. Do not wake paused work.

## Latest reviewed door evidence

- Saved `door_probe_1017` uses interior build d2b2af17 and bridge_t2. From inside, persistent anchor 2048 resolves at base-world coordinates; temporary exterior references do not resolve in these attempts. No universal limit is proven.
- Probes (c)/(d): MoveTo enters a generated exterior but lands at unshifted XY (-989.26,1146.51). In (d), requested offset (-1200,-2700,0) is logged yet arrival is unchanged; Z falls105.29 to24.11. Cause remains unresolved. [Pinned independent review](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229374094).
- Later (d) runner teleports show BOUNDARY REACHED and unread heights. Exclude them from map-size/door acceptance. Probe (c)'s height PASS calibrates against its own single sample; it does not prove a correct landing.
- Claude plans (e): transition, then explicit placement. Require current-instance frame, actual XYZ/facing, stable surface and captures; a helper movement is not a door trip. Actual activation, return, state and save/reload remain gates.
- New core64k / integ_1018_doors pairing passed49 raw offline checks with15 interior persistent and15 exterior temporary markers. It is distinct from the probe build; bridge_t3/native SDM acceptance is not established by that audit.
- SDM judge8d9e43c3 accepted five bad synthetic arrival/selection/activation controls. Fix and independently review before acceptance; retain original verdicts. See #32 comment6229054238.

## Source work / next gates

- #280 / draft PR28116841bb: checked durable interior-marker reservations,22 targeted tests; production callers still unintegrated. Both callers need shared reservations/hash, retained IDs, base-growth/HEDR checks and paired recovery. Claude peer QA and exact caller scope pending.
- PR276529a36f, PR2770c5d397 and PR279c909301: identity/stage-preservation proposals awaiting independent QA/integration. Source readiness is not native acceptance. PR278 probe-case regressions are merged.
- Grok PR2851a5d3c3:29 bridge tests and intended age controls pass; day-old same-clock logs still appear fresh. PR284f1e7398:23 tests/eight decoder controls pass; old transplant reproducer is stale, committed regression/explanation pending. #285 includes #284; scoped clock QA is not whole-PR approval.
- Future streaming/launcher plan: [#286](https://github.com/fo4sf/fo4-to-starfield/issues/286). Existing6.4km coverage/short walks do not prove whole-map travel. Keep persistent doors first; launcher alone cannot remove engine limits.

## Preservation / cadence

Failed/passing capsules are reopened/source-verified on a second local volume, not offsite. Both obsolete work directories are backed up; cleanup/free-space receipts remain with Claude. Codex deleted nothing. Preserve STOP, Guardian, owner-idle, recovery and saves; never publish game assets/private settings. See testing/progress-storage.md.

Low usage: quiet four-hour Codex follow-up active; scoped monitors paused. Read changed evidence, avoid unchanged retests, guard before commits. History: #32, PRs and Git.