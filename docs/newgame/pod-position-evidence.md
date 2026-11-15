# Pod position evidence after C1

Codex / Lone Wanderer, Ubuntu 26.04.1 LTS. FAL-848; reviewer: Courier Copy.
This is an evidence-only source slice of draft #790, not a placement correction or a PC session card.

Owner comment `01a11d0b-41a3-48aa-86c2-fc9862614dc8` transcribes the completed C1 logs at
`0391417bb664b27192d162d6e9838e31df2ba613`. No new session was run for that transcription.
The Scribe's FAL-911 trace identified the one-time stage10 CheckPod and found no proven placement patch.
The supplied lines now answer the earlier request for three existing position observations.
The owner identifies these settle reads as pre-creator. Separate quest/Looks timers alone do not guarantee that
ordering for every run; the new before-creator trace records the actual boundary rather than inferring it.

| Observation | m1 | m2 |
|---|---|---|
| Entry XYZ | 9.223081, -3.117420, -0.527535 | same |
| Printed target XYZ | 9.142858, -3.114286, -0.728571 | same |
| Settle XYZ | 9.603027, -3.157175, 0.899567 | 9.659125, -3.265042, 0.620462 |
| Logged settle dx / dy / drop | 0.485682 / -0.080276 / -1.407521 | 0.531086 / -0.097811 / -1.376682 |
| First stage20 XYZ | 9.425324, -3.060196, 1.650133 | 9.423760, -3.062771, 1.649664 |
| Printed settle Z minus target Z (m) | +1.628138 | +1.349033 |
| Stage20 Z minus target Z (m) | +2.378704 | +2.378235 |
| Stage20 Z minus printed settle Z (m) | +0.750566 | +1.029202 |
| Settle to creator-close interval (s) | 135.927002 | 152.955017 |
| Creator close to first status interval (s) | 2.239014 | 2.418976 |

The final positions nearly coincide, but the cause of the obstruction remains unresolved. The logged branch reason
is `creator closed`; the introductory description also says Quick start. Keep the verbatim reason rather than
silently classifying these as creator-skipped runs. Later m2 position changes are the owner's reported tcl/noclip
actions and are excluded from the normal-placement comparison.

## What the source establishes

Old CheckPod reads XYZ to compute dx/dy/drop, then reads XYZ again for the printed position. Its printed values do
not reproduce its deltas in C1: using the printed target and settle XYZ gives drops -1.628138 / -1.349033, not the
logged -1.407521 / -1.376682. Different readings while the actor moves could explain this discrepancy; no engine
mechanism is proven by the transcription. The long interval also prevents attributing the later rise to creator
close specifically. The actor was already above target before the creator.

The new CheckPod reads each coordinate once, uses those cached values for its existing evidence threshold and its
printed deltas, and appends target, heading, loaded/cell/world and sample_start/sample_end. The criterion remains
unchanged: a player high above target can still read ok=true. It is not a walkability verdict.

The optional Looks script records the same coordinate/heading/world context immediately before ShowRaceMenu and
at Done(how), before the existing stage20 transition. Creator close and quick start keep distinct reasons; the
existing Done guard prevents duplicate close events from sampling again. There are no new movement/control
setters, waits, properties, records, thresholds, race-menu defaults, or lift/map changes.

These are sequential native readings within an explicitly logged interval, not atomic engine snapshots. Added
logging has execution cost; no native timing or overhead claim is made. Optional/no-looks compilation remains
independent: no new cross-script reference. A no-looks/LooksWait fallback has no invented creator-boundary sample.

`make_newgame.py log` retains `pod_settle` and adds `looks_positions`, all current-run boundary samples in order.
Older or no-looks logs yield an empty list. Duplicate samples remain visible to review; the reader does not infer
a placement/discovery/ride PASS from these lines.

## Verification and gates

Synthetic tests execute the actual straight-line evidence functions and Done guard with changing native-read
substitutes. They check arithmetic consistency, one read per coordinate, intervals, reasons, duplicate closure,
event placement, no setters, and latest-run/older-log behavior. The existing newgame and Papyrus string checks and
guard also apply. These are source/logic checks, not Papyrus compilation or physics simulation.

Courier Copy reviews this exact source delta before integration. The merged #791 creator default2 has now been carried into this author branch with its writer/Python/Looks
parity checks; explicit mode0 remains available. This source integration is not a new creator or native acceptance. No PC build,
install, or game release follows from this document. A later bounded session recipe must pin the actual integrated
source and installed inputs, preserve the owner's configuration, and obtain its own PC release.

Future observations must compare coherent settle, before-creator and Done samples and show normal collision-on
pod-to-hall walking for both creator and quick start. A changed position, ok=true, and tcl movement alone cannot
certify a placement fix. Native/Windows/Papyrus/game/install remain NOT_RUN here. Full S3, map listing/discovery,
Fast Travel, unchanged-exit marker timing, native carrying and normal packaging remain open. No hold or slowdown.
