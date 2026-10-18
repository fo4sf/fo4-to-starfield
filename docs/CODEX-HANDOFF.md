# Codex / Claude / Grok status

October 18 Mountain. Goal: playable FO4 with preserved identities/state and native Starfield physics; persistent doors first. Priority: #323/#340/#349 reviews. Read newest [#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32) before acting. No controller lease granted. Details: Git history and pinned reviews.

## Ownership

- Claude: lead integration, game/controller, terrain/collision/actors, pipeline and runner/staging. No launch, close, install, input or watchdog restart without explicit release; no runner is not release. Never bypass or relay the A3 installation denial.
- Codex: deployment/recovery, identities/cache/output QA, Fo4Export/ReferenceLinks, door bridge and evidence. Coordinate shared scope; isolate work; preserve concurrent edits.
- Grok: materials, FLOR/maps and agreed fixes. Claude-cloud: offline leader-core, mission and agreed runner changes. Preserve paused work. No self-merge, force-push or rebase.

## Persistent-door gate

Last independently reviewed native observations remain separate: forward activation reached interior04006C46 (#32 comment6229965617); return refused exterior target685821 and stayed inside (6230125731). Diagnostic teleports are not door trips. Require selected-reference/activation proof, actual world/cell/XYZ/facing, distinct settled captures, both directions and save/reload.

#279beb7466 preserves709105 identities and15 door/marker records offline. Paired publication/native return remain unverified. #281f6d15bf store QA passes but callers remain unwired. #280 shared make_cluster.doors/port_index and vmad_patch.port_edits/check_port scope remains pending. Need one allocation, external latest-state pin, retained IDs/gaps/HEDR and paired recovery. No isolated substitute or uncoordinated caller edits.

## Current review queue

- #323f0ea03a: clear review5563341843; four clock-age tests/guard/CI pass, executable module matches prior review. Date-less24h alias remains; not current-session/native proof.
- #3401d0a96b: numeric P2 fixed, clear review5563374273.26 tests/guard plus actual CLI/API rejection, body serialization overflow/underflow and original cache/pose controls pass. CI pending; native mass/pickup unverified.
- #349c16d960: HOLD review5563368986. Installer ignores mission master/plugin pins; failed restage overwrites old plugin beside old plan/PEX; already-fighting raiders can leave quest at10. Synthetic install/stage reproductions; combat issue is static analysis. Seven tests including actual C# writer pass but miss these paths. Claude-cloud owns corrections.
- #305dbc99c7 and #277d2d8b3d ready with independent Grok QA/CI; preserve both handoff additions when integrating. #288733f906 and #289e392edf scoped reviews clear; #288 advanced by main merge1b8bcee, delta continuity pending. Combined material merge must retain two_sided AND greyscale/palette_scale plus roughness-mask APIs/tests.
- #290251bbf7 conflict resolution clear; maize-template/later-ID shifts need explicit fresh-build/paired-door/save decision before enabling. #348dcab489 payload sums pass; not disk/peak-RAM bounds. #345 duplicates it and counts compressed-empty payload as unpacked; consolidate.

Merged: #344 into #199, then #199290e0a3/#329da01aa6/#3418708692/#343b567d55; #33533b6289; #34628f2142; #3386ca24bd; #1761247730; #347a114d72. No deployment or native acceptance follows. Other proposals/findings: #32. Check current heads.

## Preservation / cadence

Verified private capsules are on a second local volume, not offsite; originals retained. Never alter frozen evidence or remove unresolved recovery. No game assets/saves/private settings in Git, credentials/payments/outreach or paid fallback. Preserve STOP, Guardian and owner-idle controls. Local inference only through Guardian in a coordinated no-game window. [Storage policy](testing/progress-storage.md).

Low usage: quiet four-hour follow-up; completed scoped monitors paused. Changed evidence and targeted tests only; guard before commits, independent QA before integration. Native acceptance needs pinned in-game evidence.
