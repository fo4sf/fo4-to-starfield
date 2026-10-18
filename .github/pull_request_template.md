## In plain words

<!-- Two or three sentences a non-programmer can follow: what this changes and why. -->

## What changed

<!-- The files and the user-visible or repository effect. Link the issue. -->

## Why

<!-- The problem it solves, with how you found it. -->

## AI assistance

<!-- Was an AI used to write or suggest this? Which tool, and what did you ask it? "None" is a fine answer.
     See docs/ai/for-ai-reviewers.md. -->

## Evidence

- [ ] In-game verified (include game/build and link to recorded evidence)
- [ ] Offline tested (list commands/results)
- [ ] Unverified hypothesis (say what remains to test)

## Safety and quality

- [ ] Synthetic tests added or updated where behavior changed
- [ ] `python -m unittest discover -s tests -v` passes
- [ ] `python scripts/guard.py` passes
- [ ] No game files, extracted assets, converted outputs, secrets, or machine-specific paths are included
- [ ] AI assistance and contribution roles are described accurately
- [ ] Legal or format claims are linked to authoritative sources or labeled as uncertain
