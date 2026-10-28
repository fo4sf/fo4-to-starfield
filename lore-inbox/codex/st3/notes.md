# st3 second read — first 12 unchecked entries

## Scope and provenance

Pinned input: `research/lore-inbox/store/build/lore.json`, built `2026-10-24T17:20:34Z`, SHA-256 content hash `49e9df39b23185f0b82e578eb401af7f2a9c63cdfbfe62cc1e86a269d788ac00`, 3,844 entries. Selected the first 12 entries with `added.batch == "st3"` and `check == "unchecked"` in original export order. The local `data/entries` mirror is incomplete and contains only `gwe`; this output is pinned review input, not a canonical rebuild. The current raw batch is absent. Folding requires comparison with the current lore-thread batch; this file does not claim current-store completeness.

## Reviewed IDs

ST-MT-0001, ST-MT-0002, ST-MT-0003, ST-MT-0004, ST-MT-0005, ST-MT-0006, ST-MT-0007, ST-MT-0008, ST-MT-0009, ST-NE-0001, ST-NV-0001, ST-NV-0002

## Corrections

- **ST-MT-0002**: The transcript says he was born in Montana and worked coal mines from fifteen; it does not say he grew up there or locate the mines. The wiki background's Montana-mines claim was not retained.
- **ST-MT-0003**: The dialogue identifies a guitar and a gun from his father but does not establish these were the only things his father left; removed the exhaustive 'only' claim.
- **ST-MT-0004**: The cited responses say he may not have felt he belonged back home and ask about finding a job; they do not say he is tired of wandering.
- **ST-MT-0006**: Narrowed the text to the dialogue record. The claim that the exchange jokes about the Courier fathering a child is an interpretation and was removed from this entry.
- **ST-MT-0008**: The inspected dialogue record supports the line and named bunker, but the inspected source does not establish the original claim that it was unused or never heard; narrowed to the record's content.
- **ST-MT-0009**: The inspected dialogue record attributes the statement to Patrocolus, but does not establish the original claim that the line was unused; narrowed to the inspected record.

## Unsupported / left unchecked

- **ST-MT-0007** — the cited Sawyer/Formspring statement is represented through a fan-wiki page; no original developer post was inspected. No primary-source verification.
- **ST-NE-0001** — cited TV dialogue is transcribed on a fan wiki; no episode primary artifact was inspected.
- **ST-NV-0001** — game setting/map summary is wiki-reported; no primary game map or in-game evidence inspected.
- **ST-NV-0002** — sign/slogan is wiki-reported; no primary game image or in-game evidence inspected.

These four rows retain their original fields and `check: unchecked`; labels were not upgraded. No other row was reviewed in this pass.

## Exact stopping point

Stopped after the first 12 originally unchecked `st3` entries, ending at **ST-NV-0002**. No later `st3` entries were reviewed. No current raw batch was available for fold comparison.

## Evidence

Targeted transcript sections only were inspected and cached privately at `the private local source cache (not distributed in this PR)`:

- `lonesome-drifter-dialogue-topics.json`, revision 4820252, Topics section; matched cited FNV dialogue topic IDs for ST-MT-0001–0006.
- `montana-bunker-background.json`, revision 5136003, Background passage; matched Fallout 3 dialogue record `CitElderLyonsMealBlessing1` for ST-MT-0008–0009. This passage does not substantiate the claim that the record was unused.

Ledger additions for these targeted reads are in adjacent `sources.jsonl` with partial coverage. No broad ledger page refresh was performed. New evidence excerpts stay in the private evidence folder; no long dialogue was reproduced in this inbox note.

Parent QA: cached dialogue and military note excerpts rechecked, no refetch. ST-MT-0008/0009 corrected from the older export’s tier3 to owner-required tier2/hold for cut content; playability unresolved. ST-MT-0003 note now acknowledges the approximate “just about the only thing” wording. Local store inbox is the working copy; original helper output retained outside it.

VALIDATION LIMITATION: the old PC tools/lore.py still maps cut to tier3 and rejects the two owner-required tier2 corrections. Unmodified validation reports2problems, exclusively this stale policy table. The source tool was not changed. A read-only in-memory check with cut/cancelled allowed in tier2 passes; this is not a claim the original validator passed. Retained other unchecked rows may still contain older-policy classifications and require the current lore-thread migration at fold-in.
