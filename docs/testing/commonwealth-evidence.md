# Read completed Commonwealth evidence

Agent: Codex. Issue #93. This checker reads a prepared campaign and completed captures. It does not launch, install or control a game, change phase state, or approve the next phase.

First verify the campaign's source and runner pins with `commonwealth_campaign.py verify`. Record installed plugin/archive hashes, complete recovery receipts, load order and the game version separately. Then audit one completed phase:

```powershell
python -B scripts/testing/commonwealth_evidence.py --campaign <prepared-folder> --phase 02-nearby-baseline
```

The JSON report identifies the campaign, queue, terminal state, results, observation files and decoded native PNGs by SHA256. It requires valid commit pins, selects the terminal attempt recorded in state, rejects newer contradictory records, and checks every planned point's label, readable XYZ, spawn-derived merge offset and ground reference. Each observation needs a distinct physical capture file: case aliases and hardlinks cannot substitute for separate invocations. Independent stationary captures may have identical pixels and hashes. Recorded filesystem times support investigation; they do not prove a screenshot's game origin or freshness. Inspect the images and capture logs yourself.

The report distinguishes matching sampled heights from the final unscored diagnostic teleport. The latter is compared against its planned position plus the measured merge offset. An unintended distant jump can therefore be flagged even when every judged height matched and the old runner returned0. A missing, corrupt, reordered, displaced or skipped observation remains inconclusive. A displaced ground reference invalidates all relative height results in its entry.

The same reference rule applies after phase-wide capture checks. If another entry or the final diagnostic reuses a ground-reference capture, every height depending on that reference becomes inconclusive and is excluded from `height_matches`; the capture-reuse cause remains recorded. Dependent height-mismatch issues also become inconclusive, with `invalidated_class: HEIGHTS` preserving their original diagnostic. Reusing an unrelated roof capture affects those observations alone. Separate files with identical pixels remain usable. Synthetic reproduction and correction: [#96](https://github.com/fo4sf/fo4-to-starfield/issues/96).

| Exit | Report status | Meaning |
|---|---|---|
|0|MATCH|The sampled data and capture artifacts match the plan; acceptance remains open.|
|1|MISMATCH|A sampled height, reported failure or diagnostic movement differs. Inspect individual issues.|
|2|INCONCLUSIVE|Required evidence is missing, malformed, shifted, incomplete or inconsistent.|

`launch_hold` flags unusable or displaced post-probe evidence. This tool is an audit report, not a scheduler or automatic launch guard. All reports retain `runtime_accepted: false`. Informational phases remain informational even if their numerical readings match. Their expected object-top HEIGHTS failures cannot approve or gate terrain.

## Result motivating this check

The October13 Commonwealth smoke had7 matching samples and the baseline had29/30 matching heights, including six repeated roof landings. Retain the northeast probe's+1.8939m mismatch; a tree collision is a supported hypothesis until its source body/surface is traced. All four entries subsequently made an unscored post-probe jump in the wrong frame. The pinned runner's `qstep.ps1` applied the merge offset to judged points but omitted it from `beyond`. Setting the latter to the last local point did not suppress this jump. One native capture showed BOUNDARY REACHED afterwards; it does not measure the correctly placed Commonwealth's size. See [the pinned public handoff](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6136825108).

Keep that runner/campaign and evidence immutable. Claude owns the game-script fix. Require a nonzero-offset regression, independent review and a fresh campaign before further live phases. No sampled landing result establishes continuous walking, door activation, connected interiors, material quality or full-map streaming.
