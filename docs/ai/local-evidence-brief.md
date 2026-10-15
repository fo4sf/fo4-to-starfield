# Small evidence packets for Claude (#122)

Use the local helper for log triage: group repeated diagnostics, retain source
bytes/hashes/line anchors, then let Claude inspect the short packet and follow
only the relevant original evidence. This avoids another full Lead session and
its tool/history context. It is selective triage, not a full semantic summary.

```powershell
python tools/ai-team/evidence_brief.py --root <private-evidence-root> --input <run.log> --input <review.md> --out <new-private-packet-folder>
```

Open `brief.txt` first. `packet.json` retains every selected occurrence; `S1.txt`,
`S2.txt`, etc. preserve the captured bytes with hashes. Inputs are explicit UTF-8
text files under the chosen root (one to eight, at most256KiB each). Existing
packet folders refuse overwriting. No recursive harvesting or automatic posting.
Active logs are captured byte sequences, not an atomic snapshot of a live run.

`fo4sfr... not found` messages often come from the intentionally unknown command
used by the OCR reader as a session marker. Only complete marker-only messages
are collapsed. Wrapped commands keep their adjacent lines, and mixed, spoofed or
garbled messages stay distinct. Marker shape never proves nonce freshness or
permits the acceptance judge to ignore a refusal.

## Optional local model

Add `--local` in a coordinated local-inference window. The helper requires the
configured `fo4-qa` model already loaded and measured as loaded; it does not use
JIT, load/unload a model, download anything or start OpenCode. It checks Guardian
mode, admission, jobs and game-process observations, then sends one bounded,
tool-free request through `127.0.0.1:1235`, using the provider's documented
[JSON-schema response format](https://lmstudio.ai/docs/developer/openai-compat/structured-output).
Missing/malformed observations refuse.
No remote provider, paid fallback, model shell permissions or game control exists.

Model input contains the selected groups and source anchors, not a repository
tool inventory. Every group must appear exactly once in its JSON response; invented,
duplicate or omitted groups refuse publication. Summaries are trimmed and bounded
to280 characters. Raw replies (bounded prefix on overflow), measured API usage and
elapsed time are retained; `local-leads.json` is explicitly untrusted, acceptance=false.
Check any suggested interpretation against the captured source. A model summary
does not establish physics, command success or runtime acceptance.

When readiness fails, the deterministic packet remains and the CLI exits2 with
`local-error.txt`; no request is sent. `metrics.json` measures packet generation;
`local-request.json` separately records an attempted Guardian request. Guardian is
admission-only and does not preempt a generation already admitted. Coordinate with
Claude's controller before loading/using a model; this helper adds no new interlock.

## Measurement and current limits

On three retained probe logs,5795 input characters became3634 packet characters
(37.3% less text, including packet source metadata). The original2990-character
prototype was smaller but failed adversarial context/selection tests; that result
is preserved and superseded. The raw inputs are identical across both measurements.
This is a character comparison, not measured Claude subscription-token savings.
No live local-model quality or timing result is claimed yet: the game window was
reserved, and the real readiness check refused without sending a request.

The first optional model candidate is the already downloaded Qwen3-14B with a
smaller context and measured partial GPU offload. Do not reuse the old32K/full-GPU
profile without checking current resources. A bounded paired quality trial is the
remaining gate before recommending model summaries as a routine Claude input.
