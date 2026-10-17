# Codex / Claude / Grok status

Owner goal: connected Red Rocket-Sanctuary-cave slice with Fallout 4 gameplay and Starfield physics; current focus persistent doors. Offline checks are not native acceptance. Newest issue32 claims override this snapshot.

## Ownership and controls

Claude leads and owns game/controller, collision/terrain/actors, pipeline and runner/staging. No Codex launch, close, install, input or watchdog restart without explicit release. Codex owns identities, deployment/recovery, output verification and door bridge. Use isolated source trees and public exact scopes; preserve concurrent edits. No extra agents or waking paused workers. Local inference only through Guardian in a coordinated no-game window.

Preserve STOP/Guardian/owner-idle/recovery, failed evidence and original stages. No game assets/saves/private settings in Git, money/passwords/purchases/paid fallback/outreach/history rewriting. Guard before commits; independent QA before lead integration. Low usage: targeted checks, no unchanged broad reruns.

## Persistent doors

- PR273/d3581f7 holds the writer lease through raw checks and final verification; exact-head CI38976199567 passed. PR279/c909301 indexes full-size source lookups: 260 raw checks/709,154 IDs/15 doors pass on the byte-identical core64j bootstrap; hosted CI38983360793 passed. Optional FO4/Archive2 checks omitted; independent QA/native gates remain open.
- PR276/529a36f (CI38978799908 passed) integrates273 with272/b35c958: current destination schema, marker-before-ACTI legacy order, current cluster/VMAD APIs. Removed superseded duplicate helpers/CLI; preserved reservation/publication/held-audit controls and multi-cluster slot plans. Small exact272 plugin/map bytes match; explicit bootstrap is byte-identical and subsequent door/light reorder retains IDs. Old generic-script/OBND stages are NOT proven migratable. Targeted writer/mixed/raw/audit/session/receipt tests; no full suite or game run.
- PR272 is merged at57a5289. Proposed codex/door-stage-preservation fixes its README/report hardlink overwrite and existing-VMAD replacement: preflight every selected door, reserve generated names, replace output files without mutating linked sources, reject nested output.16 targeted tests (9 new) and guard pass; good plugin/map bytes match parent. Independent QA pending; no active stage repair or deployment. Low24 ownership was already fixed in272. Native Mart Step0/return/save gates remain Claude's.
- PR275/80b5da9 on256/35b7207 corrects253 refusal-fixture coverage: actual serialized winning return accepted; seven conflicting/deleted-cell controls refuse before publication. Production writer unchanged.253 merged into codex/missing-door-endpoints, not main;256 carries the return patch toward main. Peer QA pending.
- #280 reproduces interior marker ID swaps/shifts/reuse across door-set rebuilds. New owned port_marker_ids.py proposal imports checked raw markers and plans reservations with tombstones; 13 synthetic tests and read-only bootstrap of all15 real markers pass. Preserve 623 mapped-but-unemitted base IDs. No existing caller changed: durable state publication/lease, gap-aware producer/patcher integration and independent QA remain required. See docs/terrain/port-marker-identities.md.

## Preservation / next

Current source is the independent D: clone. Claude's cleanup removed other Codex worktrees; all58 surviving local Codex branch histories are on GitHub, and a verified private bundle/object recovery packet preserves surviving Git objects. Deleted uncommitted files are not certified recovered. core64k stage is missing: only its map was found; matching complete inputs are required for that migration, no substitute generation. Recent completed evidence is separately archived/source-verified on D: (second local volume, not offsite); originals retained. Current uncompleted proposal packet: port-marker-reservations-work. No cleanup, active-stage migration or game action. Next: coordinate #280 publication/callers and independent QA; retain Claude's native controller. Low-usage follow-up remains active.
