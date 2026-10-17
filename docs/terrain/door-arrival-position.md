# Optional merged arrival position (candidate)

Codex, requested by Claude in issue32/comment6229835852. This extends the
`FO4SF_LoadDoor` script only. Writer integration, persistent exterior markers,
deployment and native acceptance remain Claude's separate work.

Existing `DestinationPlugin` and `DestinationId` properties keep their contract.
An absent or false `UseDestinationPosition` boolean preserves MoveTo-only travel.
When true, three float properties `DestinationX`, `DestinationY`, `DestinationZ`
are passed to SetPosition after MoveTo returns. Zero is a valid coordinate; the
boolean distinguishes unset from an intended origin. The writer must serialize
all three floats and the boolean together. Do not enable this on ordinary
interior arrivals or infer the toggle from nonzero coordinates.

The arrival is in the measured **current runtime world's** coordinate frame.
Do not bake one session's merge offset into a generally reusable door build
without proving that assumption. No angle change is added: MoveTo still requests
the marker's rotation. This candidate makes one SetPosition call; it does not
implement staged hops or suppress boundary dialogs.

MoveTo has no success return. This source implements call ordering, not a
verified-success gate. Both MoveTo and SetPosition completion can leave an
incorrect arrival. The new properties must remain disabled outside a reviewed
experiment until native tests establish the target instance, safe displacement
and persistent destination behavior. If either call is refused, the script
cannot currently infer that from a return value. Independent QA must assess this
limitation before integration; a success check must not use guessed cell-ID or
height equivalence.

Traces record the marker, player before MoveTo, player after MoveTo and (when
enabled) player after SetPosition, plus requested coordinates, destination
plugin/local ID, reference ID, XYZ, heading, parent cell and world. They go to
the normal trace and the `fo4sf` user log. These are observations, not settled
positions or PASS verdicts. No producer parser/evidence schema changes here.

Native acceptance still requires actual door activation, correct scene and
runtime frame, settled surface and facing, a return trip, state preservation and
save/reload on a freshly pinned build. Probe(e)'s converted-cell endpoint and
height mismatch do not satisfy that gate. Source-contract tests and compilation
only check the offline interface; neither executes the game.
