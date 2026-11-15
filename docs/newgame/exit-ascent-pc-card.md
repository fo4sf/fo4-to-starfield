# S3 carrying-ascent component: PC evidence card

Author: Codex / Lone Wanderer, Ubuntu 26.04.1 LTS. Reviewer: Courier Copy.
Record the actual full reviewed remote #790 head and all generated hashes.
Windows, .NET writer, Papyrus, game and install are NOT_RUN by the author.
This source recipe is pending independent review. It grants no install or game
control and does not replace exit-arrival-pc-card Section A now queued on the PC.

## Offline stage after review

Use the owner's recorded animL12 inputs from FAL-489 moving-platform note rev 40,
not a different model or a patched probe. Record the original model/hash, port,
Starfield, converter DLL/template/tools and complete command. Build in new folders:

```text
python scripts/newgame/make_anim_console.py stage --production-lift --out <lift-stage>
  --starfield-data <Starfield-Data> --port-data <port-build>
  --fo4-data <Fallout4-Data> --door-anim-dll <converter-dll>
  --collision-template <template> --texconv <texconv>
  --edid FO4Port_acti_0244ef_fallout4
  --states stage3=StateA_Play,stage2=StateB_Play --idles toggle --rest-after stage2
```

The displayed command spans lines for readability; pass all arguments to one
invocation. Require all checks pass, a single original-lift ACTI override in
FO4SFExitLift.esm, four clips, floor/top idle provenance, twelve moving bodies,
21.6 m up over 9.8667 s and down over 23.8333 s. No probe quest or script.
Keep anim_manifest.json, offline_check.txt and plan.json. A mismatch stops staging.

Run make_newgame.py precheck on the actual ContentResources; missing animation
native/event declarations stop staging. Use the established new-game stage command
and its recorded owner options, adding `--exit-lift <lift-stage>`. Record the
lift reference/base IDs resolved from the port. Require write/check and Papyrus
compile to pass. Use fold into a **new** core-set folder, then verify. The README's
plugin list must include FO4SFExitLift.esm before FO4SFNewGame.esm. Retain complete
hashes; do not use anim_console_install.py or silently promote a session probe.

## Runtime component observation, only under a separate PC release

Use the established guarded session install, game-closed before receipt, normal
owner-build/settings/saves preservation and cleanup. A fresh throwaway normal
start is required. If the pod obstruction prevents reaching the hall/console,
record the separate pod failure; no tcl/teleport result counts as the normal path.

Reach the floor lift through the vault console/door/gates. This commit still uses
the existing proximity-based console action: it does **not** establish final
console activation or gate collision. Record those limitations independently.
Confirm the platform already waits at the floor, then choose the ride prompt:

- Capture player/lift cell and position before, during and after upward motion,
  including the player's height rise. No player movement command or test stage.
- Require one `ascent play accepted=True`, reject early Done, then a valid
  `ascent done` and later `ascent carried confirmed`. A bool or Done alone is
  not carrying proof. No floor snap, fall, duplicate play, black hold or slowdown.
- Require the existing later-tick exterior arrival and landed confirmation, no
  `exit failed`. Discovery requests are judged only by the named discovered Vault
  111 icon and usable Fast Travel offer, with landing/other locations undiscovered,
  as detailed in exit-arrival-pc-card; proxies are not a substitute.
- Return exact heads, asset/plugin/PEX hashes, compile/precheck/check outputs,
  logs/video positions, failure cases observed, save/load observations and matching
  cleanup receipt. A missing check remains NOT_RUN or unresolved.

This indoor ride reaches the arrival path **after** motion ends. It cannot prove
map preparation hidden during an exterior ascent. Section B remains gated on
exterior/all-marker integration, measured timing, pod walkability, console/gates
and full normal-build acceptance. Keep the draft open and make no S3 completion claim.
