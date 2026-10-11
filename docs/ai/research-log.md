# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: QA round on PR #49 (trusted_gh.py): a fail-open edge and an enforcement gap
- Question: does trusted_gh.py hide everything its docstring says it hides, and does the fo4-lead.md permission set
  keep untrusted text away from the Lead on its own? (QA (local) reviewed PR #49 on 2026-10-11: pass with notes.)
- Method: re-read the two code paths QA named, fixed them, added 9 synthetic tests (tests/test_ai_trusted_gh.py, now
  34), and re-ran read-only gh calls against the repository on 2026-10-11 (the scratch GraphQL query is not in the
  repo).
- Fail-open edge, **verified** (a unit test reproduces it on ec7b42e): a comment flagged `includesCreatedEdit` whose
  GraphQL node came back as `{"editor": null, "userContentEdits": null}` gave `_editors` an empty set, `edit_ok`
  passed and the text was printed. Fix: the query asks for `__typename` and `lastEditedAt`; `_editors` returns
  unknown (hidden) when `__typename` is missing, when `userContentEdits` (and `timelineItems` for Issue/PullRequest)
  is not a connection with a `nodes` list, or when `lastEditedAt` is set with no editor on record; `edit_ok` also
  treats an item gh marks edited that has an empty editor set as unknown. Not observed live (GitHub answered empty
  connections, never null, in every call below).
- Live after the fix, read-only: `issues --state all --limit 100` lists all 34 issues (27 with edited bodies), 0
  hidden; `pr 49` shows the body and QA's review; `issue 32 --last 2` prints 2 of 106 trusted comments (104 omitted,
  0 hidden) in 3.3 s. **Verified** that the stricter rule hides nothing of the owner's.
- `includesCreatedEdit` vs `lastEditedAt`: one GraphQL query over 34 issues, 19 PRs, 6 reviews and the first 100 of
  106 comments on #32 (159 items, 2.4 s): 0 mismatches; all 30 edited items have at least one `userContentEdits` row
  and the only editor login on record is `fo4sf`. **Verified for this repository**; GitHub documents the flag as
  "edited and includes an edit with the creation data", so it is not claimed as a general property of the API.
- Enforcement gap, **verified** live by QA (`gh issue list --json number,body --limit 2` printed full bodies): the
  `allow` globs `gh issue list*` / `gh pr list*` in fo4-lead.md cover `--json body`, so the `ask` on `view` can be
  bypassed by a list call, and `gh pr diff*` is allowed too. The task kept listing allowed, so this is documented
  (README; fo4-lead.md procedure step 1 now starts with `trusted_gh.py issues`, and lists are for numbers, labels and
  states only) and stays **unresolved**, together with the Research/QA agents' raw `gh`, the remote agents' `gh`, and
  inline PR review comments (`PullRequestReviewComment`), which `pr <n>` neither shows nor counts because
  `gh pr view --json` has no field for them.

## 2026-10-10 Claude: what can a trusted-author filter for GitHub reads rely on? (tools/ai-team/trusted_gh.py)
- Question: which facts from the GitHub API let a wrapper drop outsiders' text before a local model reads an issue
  or PR, and what is the owner's API login (docs/ai/admin-node-review-2026-10-10.md asked for the filter in code)?
- Method: read-only `gh api`, `gh ... --json` and `gh api graphql` calls against the repository on 2026-10-10; the
  tool's own `fetch_edit_history` run on real node ids; unit tests on synthetic gh JSON (`tests/test_ai_trusted_gh.py`).
- Owner login: the repository owner, the authenticated shared account, the author of all 34 issues (`--state all`) and
  of all 104 comments on #32 report the login `fo4sf`. The former login returns HTTP 404 from `users/<login>` while
  the old repo URL redirects to `fo4sf/fo4-to-starfield`: **verified**. A retired username can be re-registered, so
  the tool resolves the repo slug from the checkout (as PR #47 does for team.py) and trusts logins, not URLs.
- `gh issue view 32 --json comments` returns 104 comments, equal to the REST `comments` count (pagination past 100
  works): **verified**.
- gh's `--json` exposes `includesCreatedEdit` for comments and reviews (GitHub documents it as "edited and includes
  an edit with the creation data", so it is an edited flag only where edit history exists; see the 2026-10-11 entry
  for its match with `lastEditedAt` in this repository), no editor, and no edit flag at all for the issue/PR body or
  title. GraphQL `nodes(ids:) { ... on Comment { editor userContentEdits } }` answers
  for Issue, IssueComment and PullRequest nodes (6 nodes checked), and on the 27 issues whose bodies were edited
  (2 edits each) `fetch_edit_history` returns `{'fo4sf'}`: **verified**.
- `timelineItems(itemTypes: [RENAMED_TITLE_EVENT]).totalCount` counts all timeline items (PR #33: 15, with 0 filtered
  nodes), so page completeness is read from `pageInfo.hasPreviousPage`, never from totalCount: **verified** (13 PRs).
- No edited comment, renamed title or non-owner author exists in the repository today, so the hide-on-untrusted-author
  and hide-on-untrusted-editor paths are exercised by the 25 synthetic tests only; that GraphQL reports an outsider's
  edit through the same `editor` / `userContentEdits` fields is a **supported hypothesis** (API schema, not observed).
- Cost: filtered read of #32 (104 comments, one GraphQL round for the body) 2.6 s vs raw `gh issue view --json` 1.5 s.
- **Unresolved** (follow-up): the Lead's allowed `gh issue list --json body` / `gh pr list --json body` and `gh pr
  diff`, and the Research/QA agents' raw `gh issue view` / `gh pr view`, still print anyone's text (see 2026-10-11);
  the remote agents' own `gh` is outside this filter.

## 2026-10-09 Claude: which FO4 collision bodies are movable?
- Question: how does an FO4 `bhkPhysicsSystem` mark a body as movable (pushable), so the converter can stop turning
  physics objects into fixed obstacles (Vault 114 door `05C7DC` is blocked by a ragdoll skeleton)?
- Method: compared `SkeletonClothed01.nif` (ragdoll) with `SubPlatformWall01.nif` (static) in the
  `hknpPhysicsSystemData` packfile, then scanned all 4,014 converted models (local script, not in the repo).
- Evidence: body cinfo +12 (u32) is a motion index: skeleton bodies 0..16 with 17 motion entries and 16 constraints
  (`hkpRagdollConstraintData`, `hkpLimitedHingeConstraintData`), layer 10; static wall `0x7FFFFFFF`, layer 1.
- Scan (motion index != 0x7FFFFFFF): 490 models / 5,340 placements with one moving body; 59 / 345 with several and no
  joints (cryo pods, roof hatches); 29 / 167 ragdolls with joints (skeletons, V111 gear-room gates, gurney).
- Status: "+12 = motion index, 0x7FFFFFFF = static": **supported hypothesis** (2 files). "Motion index means
  pushable": **refuted as stated**: placed Statics like `BldgShellWoodStairsRailing01` also have one, so it also covers
  keyframed / animated bodies. **Unresolved:** the motion entries' mass / motion type, which separates pushable
  (dynamic) from keyframed bodies.
- Follow-up (same day): system +32 holds motion *properties* (present only for dynamic bodies; values like 104.375 /
  31.57 / 0.1 / 0.05 identical in skeleton and pencil) and +48 the motion *cinfos*: u16 motion-properties id at +0,
  inverse mass f32 at +4. Skeleton: id 0, inverse mass 0.1 (10 kg); pencil: id 0, 2.0 (0.5 kg); stair railing and cryo
  pod: id 0xFFFF, inverse mass 0 (keyframed). Rule "dynamic = motion index != 0x7FFFFFFF, its cinfo id != 0xFFFF and
  inverse mass > 0": **supported hypothesis** (4 files, consistent across the scan). Rescan of 4,014 models: 373 single
  dynamic (4,642 placements: loose items), 22 multi-body without joints (156: breakable railings, gore), 29 ragdolls
  (167). Railings and cryo pods move to static, which is correct for them.

## 2026-10-09 Starfield `.af` animation header (door rigs)
- Question: what are the u16 fields at 0x28 of `open.af`?
- Method: compared four door families' `open.af` with their `characterassets\skeleton.rig` name tables
  (docs/spikes/WP-doors-research.md, "Header fields vs rig bone tables").
- Evidence: Akila 6 bones / field 6; generic 21/21; ship small 24/24; ship large 49/49.
- Status: field 2 = rig bone count: **verified** (4 of 4). Field 1 = format version: **supported hypothesis**.
  Field 3 = frame count: **supported hypothesis** (30 fps unconfirmed). Field 4: **unresolved**.

## 2026-10-09 FO4 precombine collision bodies with "shared vertex index out of range"
- Question: what primitive encoding do these `SCOL\CM*.NIF` bodies use?
- Evidence: 0 packed vertices, shared-index entries in triples (2130, start, x), primitives like (3,2,2,2);
  docs/JOURNAL.md "Precombine debris parts" and its correction.
- Status: **unresolved**. The "thin rods" reading was **refuted** (groups up to ~3 m in every axis).
