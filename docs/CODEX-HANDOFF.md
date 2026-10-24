# Codex / Claude / Grok status

October 18 Mountain. Goal: playable converted FO4 with preserved source identities/state and native Starfield physics. **Persistent interior/exterior doors first.** Latest [#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32) override this snapshot. No game controller release recorded.

## Owners / file locks

- Claude: lead integration, live game/controller, pipeline, terrain/collision/actors and runner/staging. No other launch, close, install, input or watchdog restart without explicit release; no runner is not release. Never bypass or relay the denied A3 installation.
- Codex: deployment/recovery, identities/cache/output QA, Fo4Export/ReferenceLinks and door bridge. Isolated owned trees; publicly agree shared producer/caller scope before changes.
- Grok: materials, FLOR/maps and agreed independent QA. Claude-cloud: offline leader-core, mission and agreed fixes. Preserve concurrent edits and paused work. No self-merge, force-push or rebase.

## Last independently reviewed native door result

Forward console activation reached interior04006C46 with twelve stable readings and visible interior ([forward evidence](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229965617)). A separate return attempt refused exterior target685821 and remained inside ([return evidence](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6230125731)). Diagnostic teleports and generic height PASS are not native door trips.

Both directions, selected-reference/activation proof, actual world/cell/XYZ/facing, settled captures and save/reload remain required. Preserve failed observations; offline tests do not establish native acceptance.

## Current source / integration gates

- Owner review batch merged: #344 into #199, then #199/#329/#341/#343; #323/#340/#349; #288/#289/#290; #176/#305/#277; #338/#346/#347 and #335. Main2906601 includes #277. Scope-specific native mass, materials, harvest and mission gates remain; #349 requires separate pinned verification before an owner install.
- **#224b92e310 ready for lead integration**: [Grok current-head QA](https://github.com/fo4sf/fo4-to-starfield/pull/224#issuecomment-6251626898), CI39139659288 and CodeQL pass. Twelve focused tests/guard; CLI keeps full details in the private manifest. Existing core64c/core64h candidates unchanged; zero-offset placement is an unverified hypothesis, and a companion is not a complete installation/campaign.
- **#350b754bce ready for lead integration**: [correction review](https://github.com/fo4sf/fo4-to-starfield/pull/350#pullrequestreview-5563661329), CI39139993510 and CodeQL pass. Failed captures skip submission and only enabled port plugins are listed. Windows synthetic dry-run tests pass; actual clipboard/player UI remains unverified.
- **#280 paired identity publication remains unwired.** #281f6d15bf store QA passes; shared make_cluster.doors/port_index and vmad_patch.port_edits/check_port scope remains pending. Require one allocation, external latest-state pin, retained IDs/gaps/HEDR and paired recovery. #279beb7466 offline full-size identity/door parity is not paired/native return acceptance. No extra isolated helper or uncoordinated shared caller edit.
- #337 is explicitly held for an owner target replacement. #286 streaming research is complete; implementation follows the persistent-door slice. Neither short routes nor a launcher establish seamless whole-map travel.

## Preservation / work rules

Private index: 278 verified capsules /175623 files on D:, a second local volume, not offsite; originals retained. Failed and passing #224/#350 evidence is preserved. Never modify frozen sources or remove unresolved recovery; verify preservation before authorized cleanup. See [storage policy](testing/progress-storage.md).

Preserve STOP, Guardian, owner-idle, controller and recovery controls. No game assets/saves/private settings in Git, credentials/payments/outreach or paid fallback. Local inference only through Guardian in a coordinated no-game window. Targeted regressions and guard before commits; independent QA before integration. Quiet four-hour Codex follow-up active; completed scoped monitors paused. Use changed evidence and avoid unchanged retests.
