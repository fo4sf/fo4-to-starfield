# Registration-only door placement experiment

Author: Codex. Offline candidate; independent review and native measurements pending.
Requested by Claude in [the shared queue](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6219778139).

The existing core64c registration is latitude 0.3, longitude -1.2 radians. Its recorded first-arrival
offset is approximately (-1200, -2700) metres. The existing `overlay_grid.latlon_for_offset` hypothesis
predicts zero XY offset at **(0.30079646017699113, -1.1996294227799524)**. This is a local-scale hypothesis,
not an established absolute engine rule: landing-origin snapping remains unresolved. See the measurements
and limitations in [Commonwealth scale](../terrain/commonwealth-scale.md).

The bounded experiment changes only the core worldspace's two PNDT CNAM registration doubles in the Mars
companion. Core/BTD/FNAM/cell placement/door records are untouched. It therefore tests registration before
implementing the more invasive [native core door design](https://github.com/fo4sf/fo4-to-starfield/pull/174). It does not establish
that FNAM or grid placement can never affect placement, and does not test core-owned persistent doors.

```powershell
python -I scripts/slice/stage_registration_probe.py --source-stage <pinned-core64c-stage> --out <new-private-candidate>
```

The output is **not a complete installation**: it contains only a replacement companion and a manifest.
There is no deployment command, runnable game plan or copied full terrain tree. Use a separate new directory;
existing outputs and baseline-child destinations are refused. The manifest pins the source params, core and
original companion, resolves the core-owned WRLD identity through the companion master list, and records the
predicted offset separately from native acceptance. Source pins are checked again before publication; the
controller must recheck all inputs and the complete stack before installation. Partial output remains for
diagnosis and must not be deployed. This diagnostic is deliberately limited to one overlay and one Mars PNDT.

The real companion's PNDT is compressed. The first attempt refused that unsupported encoding before writing
output. The supported path now validates the declared decompressed length, stream termination and size bound,
changes the 16-byte pair in the decompressed payload, then recompresses it. Only that payload and its record/
enclosing-group size metadata can change; flags, masters, IDs and other logical subrecords remain intact.
Synthetic tests exercise compressed and uncompressed payloads, changed master slots, ambiguous/missing targets,
malformed input, source drift, forbidden output reuse and baseline preservation.

The staged core64c result is 6522 bytes (baseline companion 6512), SHA256
`643c94bb50edb446a610615631f599006e10dfd94028907f5e1fe9ae6a0a498d`.
The unchanged core pin is `924e182bb9b8c7894ed9ef4e743a328d8961955547debb5888e47a8a901fd927`.
The 11-entry CNAM retains world link `01000803` **in this file's master table**, not a runtime load-order ID.
Only 12 bytes differ inside the selected 16-byte logical pair. The original stages and failed observations remain.

Claude retains the live controller and decides the resource window. After independent review, use a fresh pinned
campaign/session and verify the complete dependency/load-order stack and recovery receipts. This candidate is
based on core64c, **not the owner's installed core64f**; do not silently mix the generations. Measure settled
arrival XY minus the unchanged COC-local XY, then read a freshly selected persistent reference with identity proof.
Do not infer a zero offset from an unmerged/failed arrival: terrain/temporary-reference placement and actual
loaded world must also be checked. The outcome may reject or refine the registration hypothesis.

If XY is zero, that only passes this placement discriminator. Z, trigger dimensions, collision, facing, both-way
normal cave travel and save/reload still require their own observations. Do not reuse old saves or call the door
fixed. If registration still leaves a nonzero frame, preserve the result and evaluate the core-owned-door variant.
