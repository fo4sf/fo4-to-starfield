# `mil` second-read pass 1

## Scope and provenance

Input is the pinned `build/lore.json` export, built `2026-10-24T17:20:34Z`, containing 3,844 entries with `content_hash` `49e9df39b23185f0b82e578eb401af7f2a9c63cdfbfe62cc1e86a269d788ac00`. The local `data/entries` mirror is incomplete (it contains only `gwe`); this output is not a completeness claim. The current raw `mil` batch is absent, so folding requires comparison with the current lore-thread batch.

Whole-batch output preserves the original export order and all original fields/IDs, except the two evidence-backed label/check updates below. Total `mil` rows included: 86.

## Reviewed IDs

MIL-0001, MIL-0002, MIL-0003, MIL-0004, MIL-0005, MIL-0006, MIL-0007, MIL-0008, MIL-0009, MIL-0010, MIL-0011, MIL-0012

Checked: `MIL-0004`, `MIL-0005`.

## Corrections

- `MIL-0004`: label changed from `as-reported` to `verified-source`; checked. Fallout 76 Soldier's certificate transcript and FormID `0033c775` support Camp McClintock, completion of basic training, and award of Private rank.
- `MIL-0005`: label changed from `as-reported` to `verified-source`; checked. Fallout 76 War game orders transcript and FormID `0051e22e` support an Army war game involving Marines as opposing forces.

## Unsupported or unresolved IDs

`MIL-0001`, `MIL-0002`, `MIL-0003`, `MIL-0006`, `MIL-0007`, `MIL-0008`, `MIL-0009`, `MIL-0010`, `MIL-0011`, `MIL-0012`. These remain unchecked and otherwise unchanged. The available local citations and targeted wiki pointers did not provide inspected primary material with a record ID for these claims. No checked status was inferred from a wiki summary alone.

## Stopping point

Stopped after the first 12 unchecked `mil` entries in original export order (`MIL-0001`–`MIL-0012`). No later `mil` entry was reviewed.


## Pass 2: MIL-0013 through MIL-0032 (2026-10-28)

Authoritative input was the parent-reconciled working `verified-1.jsonl`, SHA-256 `f7e0bf113897d5f97cdf949e6fe8e650c9edbf474b6257c4777a77647b8f3ed6`; the older export was not used to reconstruct it. The earlier export provenance and missing-current-raw-batch limitation above still apply. Compare against the current lore-thread batch before folding; no current-store completeness claim.

Reviewed exactly 20 IDs: MIL-0013, MIL-0014, MIL-0015, MIL-0016, MIL-0017, MIL-0018, MIL-0019, MIL-0020, MIL-0021, MIL-0022, MIL-0023, MIL-0024, MIL-0025, MIL-0026, MIL-0027, MIL-0028, MIL-0029, MIL-0030, MIL-0031, MIL-0032. Stopped at MIL-0032; no MIL-0033+ review. All 86 rows remain in order; 66 unassigned rows are byte-identical to the working input, including all parent and first-pass edits.

Results: 10 checked, 10 corrected; 16 verified-source and 4 as-reported (MIL-0018, MIL-0019, MIL-0020, MIL-0032). No assigned row remains unchecked after the documented narrowing of unsupported claims. Primary text was inspected as transcribed; record IDs are retained when supplied and are not a prerequisite under the owner's updated instruction. Wiki-only rows remain explicitly as-reported.

Corrections and review evidence:

- **MIL-0013** (corrected, verified-source): Cached Boston Bugle Article 3 reports at least four confirmed dead and eight injured; preserve the lower bound.
- **MIL-0014** (corrected, verified-source): Inspected the Vertibird exhibit placard transcript. The placard describes the scale model; service by 2085 is a projection, not an achieved date. Shortened inherited quotation.
- **MIL-0015** (checked, verified-source): M199 message-box transcript confirms official Army infantry weapon; MQ02MuseumPlaqueArmsMessage02 / 000C77C4.
- **MIL-0016** (checked, verified-source): Inspected the Mister Gutsy line in Fallout 3 loading-screen text, Robots section.
- **MIL-0017** (checked, verified-source): Inspected Assaultron loading-screen text: RobCo, military sale, close combat, laser and stealth are all explicit. Shortened inherited quotation.
- **MIL-0018** (checked, as-reported): Wiki-only confirmation of the full claim: United States Army, Post-War, expressly gives the 121st/Firebats identity and deployment. The inspected 11.15.77 terminal text supports the post-bomb posting but does not itself name the platoon or nickname. No primary upgrade; inherited coordinates not independently checked.
- **MIL-0019** (corrected, as-reported): United States Army, Behind the Scenes, supports the limited statement that Van Buren planned the Department of the Army. Design document itself not inspected. Owner policy requires tier 2 / cancelled / hold, replacing tier 3 / noncanon; origin normalized to lore. Local validator has a stale tier mapping.
- **MIL-0020** (checked, as-reported): Only the Mariposa page quotation attributed to NPC Pack p.14 was inspected; the book itself was not. It supports precisely the claim about what the book says, not real-world geographic accuracy. Tier 2 retained; inherited coordinates not independently verified. Shortened inherited quotation.
- **MIL-0021** (corrected, verified-source): The 2077 FEV research transcript says a large facility was built at the Mariposa military installation, not that the entire base was founded there that year. Clouds Rest is absent. Removed that unsupported location, its tag and inherited mountain coordinates; no replacement coordinates inferred.
- **MIL-0022** (corrected, verified-source): GPWRTERM.MSG messages 242-243 directly support the claim. Corrected attribution from ZAX dialogue to the Glow mainframe Base Information text; shortened inherited quotation.
- **MIL-0023** (corrected, verified-source): January 7 log records a transfer order and staff opposition; it does not confirm a completed transfer on that date.
- **MIL-0024** (checked, verified-source): Read diary October 10 for the discovery and Maxson identity, plus Maxson log for Colonel Robert Spindel, succession of command and base security team. Those texts jointly support the claim.
- **MIL-0025** (corrected, verified-source): The diary presents the colonel's breakdown as Maxson's impression on October 10. On October 12 Maxson stopped one execution and demanded interrogation; the original compressed sequence overstated certainty and timing.
- **MIL-0026** (corrected, verified-source): October 13 diary says Chief Scientist Anderson claimed government orders and military status, and Maxson killed him. Removed the first name Robert, which appears only in the wiki link target in this inspected transcript, and tightened the date.
- **MIL-0027** (checked, verified-source): Diary October 15 and 18 supports the suicide and subsequent executions. Maxson log separately supplies Colonel Robert Spindel's name.
- **MIL-0028** (checked, verified-source): Diary October 20 records secession and expectation of a response; October 22 records that nothing happened. Expanded locator to include the latter entry.
- **MIL-0029** (corrected, verified-source): October 23 diary dates the family move to the day before yesterday, meaning October 21, not October 22. It says the families had been moved, without attributing a specific order to Maxson. Corrected text, date and source locator.
- **MIL-0030** (checked, verified-source): Diary October 23 records the bombs; the order is signed October 24 and directs departure by 0800 October 25; diary October 25 records Platner's readings. The order's deadline is distinct from the diary's later actual departure. Sources directly inspected.
- **MIL-0031** (corrected, verified-source): October 26 says Maxson persuaded the men to bury the scientists, not explicitly that burial was completed outside. October 27 records departure for Lost Hills but gives no southward direction. Narrowed to what the diary actually states.
- **MIL-0032** (checked, as-reported): Wiki-only confirmation: Mariposa Military Base, Structure > Fallout 1, supports the listed layout. The game maps were not opened or independently inspected; retained as-reported and made no primary-source upgrade.

Unsupported original details are not silently dropped: MIL-0021 whole-base founding/Clouds Rest/coordinates; MIL-0023 completed rather than ordered transfer; MIL-0025 certain breakdown and compressed command sequence; MIL-0026 first name Robert; MIL-0029 October 22 move date/specific personal order; MIL-0031 completed burial outside/southward destination. They were narrowed to the inspected text above. Unverified inherited coordinates in other rows remain unchanged and are not newly certified.

MIL-0019 remains hold under the owner's current tier-2 cancelled-content rule. Its inherited status field remains adopted; that does not override the hold ruling or authorize use as canon. Any local-validator rejection of tier 2/cancelled is a stale mapping, not a reason to reinstate tier 3.

New evidence and before snapshots: the private local source cache. Frozen first-pass caches were only read. `review-proof.json` records per-ID outcomes and changed fields; `requests.jsonl` records cache URLs/hashes. A GPWRTERM whitespace split initially hid the sought phrase; messages 242-243 were subsequently inspected. A ZAX.MSG locator check supplied no evidence and was not used for verification. No source files or canonical ledger were changed.

### Pass 2 validation

Ran `python tools/lore.py validate inbox/codex/mil/verified-1.jsonl` from the store root. Exit 1, exactly one problem: MIL-0019 source_kind `cancelled` rejected at tier 2 by the stale local mapping. The owner's tier-2/hold policy is retained; no validator source change or policy rollback. All other fields passed that validator.

Independent preservation check confirms all 86 IDs and order, all original field keys, exactly the assigned 20-row scope, 66 unassigned rows byte-identical, and prior notes/source-ledger bytes preserved as prefixes. Evidence: `validator.txt`, `preservation-check.json`, and `review-proof.json` in the second-pass evidence folder. Output SHA-256: `bd4134f8f5f6d17e3b0b54f5173483833d23dfedc37bf734157cf09aba250bc8`.
