# Known unknowns

Open questions that block or risk work. Remove an entry only with a link to the evidence that resolved it.

| # | Question | Blocks | Where it's tracked |
|---|---|---|---|
| 1 | `.af` per-bone channel layout (which bytes hold each bone's translation/rotation) | sliding vault / elevator doors | docs/spikes/WP-doors-research.md |
| 2 | Primitive encoding of FO4 precombine bodies with shared-index triples | 36 models on guessed collision boxes | research-log.md, journal |
| 3 | Do the one-sided door blocks disappear with E pressed outside the swing arc for all doors? | door acceptance (#32) | journal, route runs |
| 4 | Effect-shader wall stains as decals: dark sheets or correct? (FO4 gradient palette not reproduced) | material quality | journal |
| 5 | Does Qwen3-14B Q4_K_M (chosen by Claude + Codex, #32) do reliable OpenCode tool calls at 16K context, and what VRAM does it use? | local team | validation pending (game must be closed) |
| 6 | Pushable in game: **verified 2026-10-10** (can, compound cone, rigid skeleton moved; door `05C7DC` passes both sides). Small items that "did not move" (2026-10-12) were mostly out of reach (a pack on a desk, a box the player was blocked short of) or flat and walked over; the same book body moved on a Vault 114 bench (research-log 2026-10-13). Open: a 50 kg pin box the walk passed 0.26 m from did not move (batch_full 0100); whether vanilla flat items are walked over the same way and whether FO4's 2-10x heavier small items matter (staged queue `movable_control_1013b`, its 5 kg tests judged only when GetMass reads 5 back); ragdoll joints; the FO4 placement pose (XRGD) is applied by the converter since 2026-10-16 (articulated models get a posed model per reference; research-log 2026-10-16): do the posed skeletons lie as in FO4 and stay put in game, and what frame does a single-body item's entry use (214 such references are left unposed); whether `*Dest` breakables merged rigid match their intact mesh. | skeleton pose, breakables | research-log.md 2026-10-09 / 10 / 11, journal 2026-10-10 |
| 7 | REFR `DATA` rotation Euler order: the offline resting test prefers Rx(-x)Ry(-y)Rz(-z) (129 of 164 tilted Vault 114 placements rest on their support) over the `routes.ref_matrix` order Rz(-z)Ry(-y)Rx(-x) (100). Which does the game use? | route planning, offline floor checks, posed-skeleton placement | research-log.md 2026-10-11 |
