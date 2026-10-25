# Repository cleanup proposal — 25 October 2026

Codex audit for the owner. **Not approved or executed.** Independent review first, then a separate owner approval for exact actions. This updates the documentation-only scope of #552; it does not grant deletion or merge permission.

## What the audit found

- 474 remote branches; 452 PRs inspected: 129 open, 278 merged, 45 closed.
- 121 known worktrees across two local Git stores. Worktrees under evidence directories are especially protected.
- Main `5fa5c20575519f87e75f497bdf1507e7a7947e97` contains 2,229 reachable commits, including 750 merge commits.
- 168 remote branch refs satisfy the conservative first-batch criteria below. Removing these refs would leave 306 at this snapshot, without removing their commits from main.
- Six corresponding local branch refs in the Codex Git store match the same exact tips and are not checked out. They are a separate optional action.
- 24 open PRs target non-main branches. Automatic branch deletion stays disabled: stacked PR dependencies must not be broken.

## Batch A: proposed merged-branch ref cleanup

Every listed candidate has two agreeing remote-tip inventories, its exact tip reachable from main, and a MERGED PR whose recorded head matches that exact tip. It is neither default/protected, an open PR head/base, nor checked out in the 121 known worktrees. The other 306 branches are kept or need further review; not being listed is not a deletion recommendation.

[Exact full-SHA manifest](cleanup-candidates-2026-10-25.json). The names, full hashes and merged PR numbers below are the approval boundary. New candidates require a new review.

Before any approved execution: refresh remote tips, main ancestry, PR states/bases, branch protection, known worktrees and agent claims. Stop or skip any changed candidate. Other machines or clones may exist; coordinate an inactive window with the branch owners. Preserve the reviewed manifest and private audit first. No cleanup command is authorized by this document.

Recovery: these commits remain reachable from retained main history in GitHub and the local checkout. Recreate a deleted ref at its listed SHA if necessary. This is ref removal, not commit erasure, and the audit archive is metadata rather than a standalone Git-object backup.

| Branch proposed for removal | Exact expected tip | Merged PR |
|---|---|---|
| `ai/32-archive-content-identity` | `dee2e7ee34a6688127e8245e716a203e77c2b6eb` | [#35](https://github.com/fo4sf/fo4-to-starfield/pull/35) |
| `ai/32-checkpoint-parity` | `115858f31483aa4d9cd8f0d794004f9451dae979` | [#34](https://github.com/fo4sf/fo4-to-starfield/pull/34) |
| `ai/36-github-readiness` | `a54d75173e7a1ef2a96fb3f551c7b41d2d90e339` | [#37](https://github.com/fo4sf/fo4-to-starfield/pull/37) |
| `claude/acti-term-promotion` | `0692604cd4506bbf43e778f9ce6170add05fd3ed` | [#241](https://github.com/fo4sf/fo4-to-starfield/pull/241) |
| `claude/activate-exit` | `dd57b2296f83adb529051552df68b7dd25bc9b1a` | [#157](https://github.com/fo4sf/fo4-to-starfield/pull/157) |
| `claude/activate-isid-ocr` | `d22144c3ef154d612b7b984b21c10232824420c5` | [#158](https://github.com/fo4sf/fo4-to-starfield/pull/158) |
| `claude/activate-step` | `eb50d7ad0420e37da508df8daaa589e1c3b36ea2` | [#145](https://github.com/fo4sf/fo4-to-starfield/pull/145) |
| `claude/ai-reviewer-guide` | `f6527404ffe4c962736c05e965bb0f9904fc2b31` | [#237](https://github.com/fo4sf/fo4-to-starfield/pull/237) |
| `claude/all-interiors-r0yte1` | `daea207be77289ba1c5d04435a862cec7a782431` | [#542](https://github.com/fo4sf/fo4-to-starfield/pull/542) |
| `claude/b4-mission-anatomy` | `0c64b49780c807144a60a063dede91758891da81` | [#318](https://github.com/fo4sf/fo4-to-starfield/pull/318) |
| `claude/bridge-log-case` | `59427b9172263058bb4360a6d7c81bab93e1539e` | [#282](https://github.com/fo4sf/fo4-to-starfield/pull/282) |
| `claude/bridge-ref-mark` | `4cb9a67aac07576f7dbc31680991d5fa1189e11f` | [#171](https://github.com/fo4sf/fo4-to-starfield/pull/171) |
| `claude/bridge-ref-reads` | `b58a4aefb301d617d4615af9dfb3a4df1c03346d` | [#164](https://github.com/fo4sf/fo4-to-starfield/pull/164) |
| `claude/cabinet-8c5f-selection` | `04d78e683c2562420a2a46b60e4e7c583ff77854` | [#249](https://github.com/fo4sf/fo4-to-starfield/pull/249) |
| `claude/check-overrides` | `83af56a9b4be2c6a5e676751b7bb8a468fc0b1d6` | [#172](https://github.com/fo4sf/fo4-to-starfield/pull/172) |
| `claude/cluster-items` | `3c71b963e9bd7827fb00a8c35a3a97240663d71b` | [#168](https://github.com/fo4sf/fo4-to-starfield/pull/168) |
| `claude/code-of-conduct` | `f2bb469edb799df7b1ee6789a81be2c11236d63e` | [#252](https://github.com/fo4sf/fo4-to-starfield/pull/252) |
| `claude/codeql-proxy-headers` | `657fc6233dbfe4cf3942230a8e34ce8d7c4cd4fa` | [#254](https://github.com/fo4sf/fo4-to-starfield/pull/254) |
| `claude/codsworth-model-voice-py0x8g` | `eab4b8df58eea1662839f548e64e8d1e425cef19` | [#361](https://github.com/fo4sf/fo4-to-starfield/pull/361) |
| `claude/commonwealth-build-plan` | `998f4bd278c0d30543ff8692adddadac3ce6c814` | [#162](https://github.com/fo4sf/fo4-to-starfield/pull/162) |
| `claude/community-issue-intake-wg8dtc` | `e31aad30d54f235fec48d44e8764cbd35ea94cf2` | [#350](https://github.com/fo4sf/fo4-to-starfield/pull/350) |
| `claude/compressed-mesh-keys` | `61c2480322e651074b12ce7879a8c8d2d40c666a` | [#274](https://github.com/fo4sf/fo4-to-starfield/pull/274) |
| `claude/containers-per-base` | `0f128805391803e7ec89c6e8706c716b7c93d3e1` | [#167](https://github.com/fo4sf/fo4-to-starfield/pull/167) |
| `claude/core-navmesh` | `2ed728b4c8865847d5cf3686efab99786f72f73a` | [#165](https://github.com/fo4sf/fo4-to-starfield/pull/165) |
| `claude/door-animations-y09s82` | `1886f3d0bd19be9037bb6d2e679490aa125e8556` | [#514](https://github.com/fo4sf/fo4-to-starfield/pull/514) |
| `claude/door-probe-step0-2` | `7ef291476478599d5e0c02a94a6fa7aec50d08b5` | [#271](https://github.com/fo4sf/fo4-to-starfield/pull/271) |
| `claude/door-records-writer-2` | `9cc6f0bd66c753540a11e25a30a1e4fc94806514` | [#272](https://github.com/fo4sf/fo4-to-starfield/pull/272) |
| `claude/door-return-writer` | `56d953eae6974a967cd381445d32dc41f63be25b` | [#297](https://github.com/fo4sf/fo4-to-starfield/pull/297) |
| `claude/exterior-lights` | `359c1f7c308139f5b176d0a85166e830179961f3` | [#246](https://github.com/fo4sf/fo4-to-starfield/pull/246) |
| `claude/interior-backlog` | `cb3c789c087fc1e5213169263879d17cc52b456a` | [#240](https://github.com/fo4sf/fo4-to-starfield/pull/240) |
| `claude/items-promotion` | `6cf22dcc589b404f41b35e506fe5f2a97033eb39` | [#235](https://github.com/fo4sf/fo4-to-starfield/pull/235) |
| `claude/journal-1015` | `d0d88d7e8b75a01d8d2763a452de329a5cb69fcc` | [#127](https://github.com/fo4sf/fo4-to-starfield/pull/127) |
| `claude/journal-1015b` | `bc4a612cb5c55375c4845fb6fcdcf6c578d5bb10` | [#140](https://github.com/fo4sf/fo4-to-starfield/pull/140) |
| `claude/journal-1015c` | `5892236aedfd2b0a335277871e808bce63fb80e3` | [#154](https://github.com/fo4sf/fo4-to-starfield/pull/154) |
| `claude/journal-1015d` | `047d098ea434c9e67e6a651fe1b90a9431f617dc` | [#159](https://github.com/fo4sf/fo4-to-starfield/pull/159) |
| `claude/journal-1016` | `9bab6ff1b1b17a531fc54c245ccb3b83481908bc` | [#170](https://github.com/fo4sf/fo4-to-starfield/pull/170) |
| `claude/journal-1016-doors` | `bfb3ef8a44755f8782d73b1fb0c9265866d81bd5` | [#295](https://github.com/fo4sf/fo4-to-starfield/pull/295) |
| `claude/journal-1016-evening` | `46d8d97a086974d09b4ce1cb0b4e1ff048f1eec8` | [#270](https://github.com/fo4sf/fo4-to-starfield/pull/270) |
| `claude/launcher-backbone-w5zv3n` | `5bfda491c2f447a34ab5c86d61d6a973174de649` | [#497](https://github.com/fo4sf/fo4-to-starfield/pull/497) |
| `claude/leader-core-import` | `98ba1e12712b1b03c00236edd3287a40b512b188` | [#199](https://github.com/fo4sf/fo4-to-starfield/pull/199) |
| `claude/leader-core-pin` | `6f0fa324c6a9aac6b4340f785e2222fb6b495f11` | [#193](https://github.com/fo4sf/fo4-to-starfield/pull/193) |
| `claude/leader-core-t2` | `d57c6645c36e65c6d8844caa681bdf30b8489594` | [#179](https://github.com/fo4sf/fo4-to-starfield/pull/179) |
| `claude/leader-core-t3` | `909ef7764f0ad17a4176d46e0f5256c56fbdd37a` | [#182](https://github.com/fo4sf/fo4-to-starfield/pull/182) |
| `claude/leader-core-t4` | `bc51a21ebeb476556fb6605667433d8a63d25194` | [#197](https://github.com/fo4sf/fo4-to-starfield/pull/197) |
| `claude/leader-core-tasks` | `63a4ea1ee32283069738d304df2d8f45ce2f3c98` | [#185](https://github.com/fo4sf/fo4-to-starfield/pull/185) |
| `claude/leader-core-transform` | `638ed2e2cbfff86fe2d042f092f97247dec0006f` | [#187](https://github.com/fo4sf/fo4-to-starfield/pull/187) |
| `claude/light-patch` | `1f016015cfd94516c9e97f9f5f980b9f0abc1509` | [#302](https://github.com/fo4sf/fo4-to-starfield/pull/302) |
| `claude/look-button` | `ba2de9a27ab087a936523d8fc6031226f7a32118` | [#228](https://github.com/fo4sf/fo4-to-starfield/pull/228) |
| `claude/look-tool` | `997a313cd95cd69fd0af6a3275be5646255bfe32` | [#175](https://github.com/fo4sf/fo4-to-starfield/pull/175) |
| `claude/make-cluster` | `c5fa56067c11fc9bf8591fb0f7e38bbb00d75427` | [#166](https://github.com/fo4sf/fo4-to-starfield/pull/166) |
| `claude/natural-light-textures-tmt0zb` | `f4ba8844b344ddaf27629891029df59c9a9ecbe1` | [#355](https://github.com/fo4sf/fo4-to-starfield/pull/355) |
| `claude/new-game-start-v75g3a` | `118d5d8e904df34778e5e4c391c90a8687a707c0` | [#435](https://github.com/fo4sf/fo4-to-starfield/pull/435) |
| `claude/next-phase-framework-bvomc8` | `50c195ba17edaf9edd5526b110d18166e730518f` | [#408](https://github.com/fo4sf/fo4-to-starfield/pull/408) |
| `claude/npc-mission-state-tr3t97` | `f959e67490be03f4a85c496cce7d7350bec4faa9` | [#432](https://github.com/fo4sf/fo4-to-starfield/pull/432) |
| `claude/papyrus-log-copy` | `f833164f3ec37a87508261aac60db749382fad95` | [#144](https://github.com/fo4sf/fo4-to-starfield/pull/144) |
| `claude/playtest-log` | `7ce8227c3f3b46a74642c728a405c5230910cb65` | [#225](https://github.com/fo4sf/fo4-to-starfield/pull/225) |
| `claude/playtest-row10` | `dfa0824f93eab2a35de0e1b4ee154300ce22f931` | [#257](https://github.com/fo4sf/fo4-to-starfield/pull/257) |
| `claude/playtest-row17-fix` | `e65eea496564d617184b260f9ed665443765be89` | [#264](https://github.com/fo4sf/fo4-to-starfield/pull/264) |
| `claude/playtest-rows12-14` | `5eeffaae2dfbafbcb81f9c8aaeb146b1275133c9` | [#258](https://github.com/fo4sf/fo4-to-starfield/pull/258) |
| `claude/playtest-rows15-16` | `369888d90468405f9948abc4985e520367b81f4e` | [#259](https://github.com/fo4sf/fo4-to-starfield/pull/259) |
| `claude/playtest-rows17-18` | `25bf594990d91c56621152ed6fea6198b888d725` | [#263](https://github.com/fo4sf/fo4-to-starfield/pull/263) |
| `claude/playtest-rows19-20` | `ad4ed4dca012e921dcbae59c099a97690e795e26` | [#298](https://github.com/fo4sf/fo4-to-starfield/pull/298) |
| `claude/playtest-rows21-25` | `bd3ebb9b10a296fa634ee368f3f49bf17f7e9292` | [#299](https://github.com/fo4sf/fo4-to-starfield/pull/299) |
| `claude/posed-props` | `ccfed58fb374f903a3714af45f8ef5d069716688` | [#244](https://github.com/fo4sf/fo4-to-starfield/pull/244) |
| `claude/pr199-bound-rows` | `eb35749c22aac59386a29c72242a459c6910f93f` | [#344](https://github.com/fo4sf/fo4-to-starfield/pull/344) |
| `claude/pr199-import-identity` | `6e2dfb3782611e5b75c6f3859a6d0ea46869ea2a` | [#342](https://github.com/fo4sf/fo4-to-starfield/pull/342) |
| `claude/project-thread-2u6xt3` | `dfce199d9eb1ce5a2ec62d971e8aff0bf94b1cb0` | [#136](https://github.com/fo4sf/fo4-to-starfield/pull/136) |
| `claude/project-thread-6yh1ex` | `0d572b76c5223b505a7798aaab87ccd72f992673` | [#431](https://github.com/fo4sf/fo4-to-starfield/pull/431) |
| `claude/project-thread-btuulb` | `f934bf8348c4e72fad5e1c21ab3078994089a6d9` | [#430](https://github.com/fo4sf/fo4-to-starfield/pull/430) |
| `claude/project-thread-su5jeg` | `3219e877550deed5c54d7f150100f9502a96b502` | [#379](https://github.com/fo4sf/fo4-to-starfield/pull/379) |
| `claude/project-thread-xcle9r` | `7f5547c674122df985e0b6f9962876cc1e9acaf4` | [#341](https://github.com/fo4sf/fo4-to-starfield/pull/341) |
| `claude/project-thread-xcle9r-askbox` | `20c3389a84825d8aeade4ad122597bb860521f3b` | [#463](https://github.com/fo4sf/fo4-to-starfield/pull/463) |
| `claude/project-thread-xcle9r-aspect` | `6159dcbc22d26dd9bacda87e8f6944fd25ee9dc8` | [#442](https://github.com/fo4sf/fo4-to-starfield/pull/442) |
| `claude/project-thread-xcle9r-cocagain` | `5dbfc9988cf9206cbba5cecbb9fb8123bba01252` | [#452](https://github.com/fo4sf/fo4-to-starfield/pull/452) |
| `claude/project-thread-xcle9r-cochop` | `5ddec9bea9e40674acadd2d40bb0d0c7dd8d27ff` | [#450](https://github.com/fo4sf/fo4-to-starfield/pull/450) |
| `claude/project-thread-xcle9r-consolecrop` | `0f23473a534c23647b4f171ec1923d09e1fcaa03` | [#447](https://github.com/fo4sf/fo4-to-starfield/pull/447) |
| `claude/project-thread-xcle9r-crashbudget` | `8eef39d366ee3eed29d31a012c8f834353af9357` | [#377](https://github.com/fo4sf/fo4-to-starfield/pull/377) |
| `claude/project-thread-xcle9r-crashfail` | `804a4edf0013fbfa60aa7ec81214e919d21eda78` | [#402](https://github.com/fo4sf/fo4-to-starfield/pull/402) |
| `claude/project-thread-xcle9r-cyclelog` | `411e60bf07bc768377b60be73c80f4f79e3509db` | [#439](https://github.com/fo4sf/fo4-to-starfield/pull/439) |
| `claude/project-thread-xcle9r-doorrounds` | `f86077005587da7f015c944fd6fe91a2961c6c7e` | [#358](https://github.com/fo4sf/fo4-to-starfield/pull/358) |
| `claude/project-thread-xcle9r-impulse` | `1ee687e6e890645c26a3f90844cfbefeae706695` | [#343](https://github.com/fo4sf/fo4-to-starfield/pull/343) |
| `claude/project-thread-xcle9r-inventory` | `18fc2d6ef755d8acc12b4d552ecc631b34c32d6d` | [#405](https://github.com/fo4sf/fo4-to-starfield/pull/405) |
| `claude/project-thread-xcle9r-launchexe` | `52b600c74a61cbe8761b940cc3ad694ac7c0ff3c` | [#391](https://github.com/fo4sf/fo4-to-starfield/pull/391) |
| `claude/project-thread-xcle9r-launchfix` | `16be1feb215226f2e5d45ff2fcb6dbf13769d14d` | [#446](https://github.com/fo4sf/fo4-to-starfield/pull/446) |
| `claude/project-thread-xcle9r-mainfix` | `c60d9a73267fe356e92e8d6ac090d3c5c0c24b53` | [#434](https://github.com/fo4sf/fo4-to-starfield/pull/434) |
| `claude/project-thread-xcle9r-maxtris` | `3a128518f19c6fb26f2bc736307971f5084f9909` | [#437](https://github.com/fo4sf/fo4-to-starfield/pull/437) |
| `claude/project-thread-xcle9r-nextphase` | `0a919139be862d688988ab1b1923cb24b872093c` | [#397](https://github.com/fo4sf/fo4-to-starfield/pull/397) |
| `claude/project-thread-xcle9r-nightrun` | `550826ae563a15dbe1b67ac15a05e44e7d0c9deb` | [#383](https://github.com/fo4sf/fo4-to-starfield/pull/383) |
| `claude/project-thread-xcle9r-preflightreport` | `74490fe272bf07bd505c7c7eb51d0ad6627b8393` | [#403](https://github.com/fo4sf/fo4-to-starfield/pull/403) |
| `claude/project-thread-xcle9r-probestage` | `fcf786dc5a2e0a4442daee0b7f994fb7294d09f4` | [#406](https://github.com/fo4sf/fo4-to-starfield/pull/406) |
| `claude/project-thread-xcle9r-regress` | `5312d04a2d354e8d6772bfba520f5c8c24dee08f` | [#401](https://github.com/fo4sf/fo4-to-starfield/pull/401) |
| `claude/project-thread-xcle9r-speedmult` | `cd2f19c7d902415d868be96609273d9fd0fe9c77` | [#335](https://github.com/fo4sf/fo4-to-starfield/pull/335) |
| `claude/project-thread-xcle9r-toggle` | `f38869fa9d11d88670f33552a1018d34d15a53a2` | [#407](https://github.com/fo4sf/fo4-to-starfield/pull/407) |
| `claude/project-thread-xcle9r-usables` | `9b6aa5e64da2de1ae682af1cac49239a4821423c` | [#357](https://github.com/fo4sf/fo4-to-starfield/pull/357) |
| `claude/project-thread-xcle9r-waits` | `8949a1d505ef52017507416503d434aee5ad5265` | [#441](https://github.com/fo4sf/fo4-to-starfield/pull/441) |
| `claude/r05-menu-media` | `3f29f639579cb99a3926441c68db14f0ac9dce62` | [#156](https://github.com/fo4sf/fo4-to-starfield/pull/156) |
| `claude/roadmap` | `5c611f1e3b7d0cf1653cf62581ccd524d140741e` | [#316](https://github.com/fo4sf/fo4-to-starfield/pull/316) |
| `claude/sheet-core64h` | `4ce3e0ece33b57be135f4130547750e11d31e0c4` | [#247](https://github.com/fo4sf/fo4-to-starfield/pull/247) |
| `claude/sheet-core64i` | `83bf0aee39d2871a75a0697c422ba94eb3d51d47` | [#268](https://github.com/fo4sf/fo4-to-starfield/pull/268) |
| `claude/sheet-core64k` | `5cbc816a178d1fd89a2bc13160e3c8b21858fc21` | [#283](https://github.com/fo4sf/fo4-to-starfield/pull/283) |
| `claude/slide-doors` | `c457df2581850e2ae2a62e319cf28254891c4433` | [#242](https://github.com/fo4sf/fo4-to-starfield/pull/242) |
| `claude/snapshot-root` | `5d0e3c42facd39ebb139ac03273b65d72ffdfd50` | [#238](https://github.com/fo4sf/fo4-to-starfield/pull/238) |
| `claude/stations-promotion` | `69174473a27df4f68ccd7b517231f50d09f63dbd` | [#266](https://github.com/fo4sf/fo4-to-starfield/pull/266) |
| `claude/test-sheet` | `566e84b0c8f66f759e2c0d5e3ae3718d0f20fb8e` | [#177](https://github.com/fo4sf/fo4-to-starfield/pull/177) |
| `claude/vault-water-plane` | `c31b6bc640da83c1c9dd40838522fc4983ecf5f8` | [#300](https://github.com/fo4sf/fo4-to-starfield/pull/300) |
| `codex/105-progress-storage` | `6c64c82eca7a1767e4c73cd8faa49a4a110a34d6` | [#106](https://github.com/fo4sf/fo4-to-starfield/pull/106) |
| `codex/117-archive-read-guard` | `d8ec38060c2b8da1bf6ae562621d3b5742ce7eea` | [#120](https://github.com/fo4sf/fo4-to-starfield/pull/120) |
| `codex/130-checkpoint-prefix` | `86ce3bed3a46c39d4bdee6ac1d6668c919da0179` | [#131](https://github.com/fo4sf/fo4-to-starfield/pull/131) |
| `codex/132-id-publication` | `2e0f67994ba9e6d168ec45a75203df6c82bd6287` | [#133](https://github.com/fo4sf/fo4-to-starfield/pull/133) |
| `codex/20261013-progress` | `13535d24b6086f95b9f652e559452cb36cd8dd03` | [#95](https://github.com/fo4sf/fo4-to-starfield/pull/95) |
| `codex/31-connected-status` | `a20d92278e6fc836df81a7b4dcf4f3289ab804dd` | [#82](https://github.com/fo4sf/fo4-to-starfield/pull/82) |
| `codex/64-terrain-ci-dependency` | `f3e4d6f263bca2e970b3e9452c8a42a6d73e9584` | [#65](https://github.com/fo4sf/fo4-to-starfield/pull/65) |
| `codex/66-portable-resource-paths` | `d3f065d404c8af3924b5413c27e36e6685b59e8b` | [#86](https://github.com/fo4sf/fo4-to-starfield/pull/86) |
| `codex/78-recoverable-slice` | `22dc1d5659878e689d88370c8a069c466bdf93f4` | [#83](https://github.com/fo4sf/fo4-to-starfield/pull/83) |
| `codex/79-door-cache` | `3bab378b64e8cd5320e8a50d2e873d76ec4843b3` | [#80](https://github.com/fo4sf/fo4-to-starfield/pull/80) |
| `codex/79-small-bind-rotation` | `74d8209428d6bb5d060ac1e192c91b552574b257` | [#81](https://github.com/fo4sf/fo4-to-starfield/pull/81) |
| `codex/83-deployment-status` | `27f21989bdf016ddd461894f0ff274129e11a9b7` | [#85](https://github.com/fo4sf/fo4-to-starfield/pull/85) |
| `codex/86-integration-status` | `6b37a72bab23335119b9f04247d0a8d9fc177ed4` | [#87](https://github.com/fo4sf/fo4-to-starfield/pull/87) |
| `codex/88-budget-resume` | `af27ce995902902214b5227c645e4f7102764c2d` | [#89](https://github.com/fo4sf/fo4-to-starfield/pull/89) |
| `codex/88-test-plan-status` | `220ef035ba925b25ce68381924c55b7187f91f3a` | [#90](https://github.com/fo4sf/fo4-to-starfield/pull/90) |
| `codex/bridge-recovery-124` | `e0f9615a2c7d804d48e2dddf66805bcf94636a85` | [#125](https://github.com/fo4sf/fo4-to-starfield/pull/125) |
| `codex/commonwealth-campaign` | `721cc7beaee99cbb68b8a1544e7c432fc6a52e26` | [#92](https://github.com/fo4sf/fo4-to-starfield/pull/92) |
| `codex/commonwealth-evidence` | `5b7a72290317195eaef86e41fcfc163ef661dbb0` | [#94](https://github.com/fo4sf/fo4-to-starfield/pull/94) |
| `codex/container-key-identity` | `cb3bacabf03f66e79574f8b731894d6c42a98e99` | [#176](https://github.com/fo4sf/fo4-to-starfield/pull/176) |
| `codex/detect-ini-coverage` | `bbeb58f48f894376df5c215ce62f9ce923031ed3` | [#429](https://github.com/fo4sf/fo4-to-starfield/pull/429) |
| `codex/door-arrival-position` | `06ade8df0ed9fb560fddceadd362202f71b8bd1d` | [#291](https://github.com/fo4sf/fo4-to-starfield/pull/291) |
| `codex/door-handoff-1017` | `a6c17c42855aacab2237204f0105250ee5d83f0a` | [#292](https://github.com/fo4sf/fo4-to-starfield/pull/292) |
| `codex/experiment-receipt-history` | `48e3a49e17d558ab78f859524e542d38d48d785c` | [#293](https://github.com/fo4sf/fo4-to-starfield/pull/293) |
| `codex/handoff-door-checkpoint-1016` | `dd7bcdb98962be2b04516e45a47cf0c207ede6b6` | [#287](https://github.com/fo4sf/fo4-to-starfield/pull/287) |
| `codex/id-map-validation` | `ecd6a33f834c7cc1ae2ff6aa632b4f745bd0a39c` | [#138](https://github.com/fo4sf/fo4-to-starfield/pull/138) |
| `codex/launcher-process-query-guard` | `40d9055233581d6842aafc34cc502454c57221b5` | [#475](https://github.com/fo4sf/fo4-to-starfield/pull/475) |
| `codex/light-patch-bounds` | `55a612f2c1a9ad20b263888ccd3b64b51ead9bf8` | [#315](https://github.com/fo4sf/fo4-to-starfield/pull/315) |
| `codex/native-door-bases` | `1756fc395b2bf4d384f6e1ecf45b363a5ab473b5` | [#245](https://github.com/fo4sf/fo4-to-starfield/pull/245) |
| `codex/native-probe-event-case` | `b9a7f6507e8daf5e2c559dcc9f1d46979bc433f4` | [#278](https://github.com/fo4sf/fo4-to-starfield/pull/278) |
| `codex/ordered-master-identity` | `9a9768283108cbb18532e5d0cddfebe85895a33a` | [#427](https://github.com/fo4sf/fo4-to-starfield/pull/427) |
| `codex/persistent-ref-inspector` | `72c4971418d5f3d5ca86024cc7ca923d3c1534c4` | [#248](https://github.com/fo4sf/fo4-to-starfield/pull/248) |
| `codex/progress-20261014` | `06af87e4d083eb3842e0303a92a07ec5d13bfcce` | [#128](https://github.com/fo4sf/fo4-to-starfield/pull/128) |
| `codex/reference-capture-dependency` | `0f81e08b83bab150db1a476613f85b5f5af94d9f` | [#97](https://github.com/fo4sf/fo4-to-starfield/pull/97) |
| `codex/restore-plugins-namespace` | `ba4617549dbb95cd2a0731acf6dfeb7655aea75f` | [#428](https://github.com/fo4sf/fo4-to-starfield/pull/428) |
| `codex/rollback-completion-receipt` | `01dcd5f03a76ecec72839787266f43bc1ad4fbdd` | [#301](https://github.com/fo4sf/fo4-to-starfield/pull/301) |
| `codex/scripted-door` | `5cb710134992313f40a095686dc90a01d69513e3` | [#243](https://github.com/fo4sf/fo4-to-starfield/pull/243) |
| `codex/staging-writer-callsite-regressions` | `9f1daab4e958f484042b72532bd65ba2eb5388ca` | [#478](https://github.com/fo4sf/fo4-to-starfield/pull/478) |
| `grok/ba2-packed-estimate` | `ca6aade682706ed20c1df41ce3da9050467c85d6` | [#348](https://github.com/fo4sf/fo4-to-starfield/pull/348) |
| `grok/batch-summary-enhance` | `fd9123ee35c73bf82df7a9b095c939a17e4a054e` | [#304](https://github.com/fo4sf/fo4-to-starfield/pull/304) |
| `grok/collision-bounds-359` | `045e4c9af97c4340eaac77731b47f0921dcc7a0c` | [#364](https://github.com/fo4sf/fo4-to-starfield/pull/364) |
| `grok/decal-flat-normal` | `339a62bc422765db7775e4295344f8c9bc50c869` | [#307](https://github.com/fo4sf/fo4-to-starfield/pull/307) |
| `grok/fix-bc-partial-blocks` | `0c62e301dfb92fc3b7080caf180bdc0d72e458ac` | [#250](https://github.com/fo4sf/fo4-to-starfield/pull/250) |
| `grok/fix-bridge-log-clock-age-213` | `de44fccd9179a5ea62f68a5f04fb6b25ea856ff2` | [#323](https://github.com/fo4sf/fo4-to-starfield/pull/323) |
| `grok/flor-research` | `2807b8686c29b62f3ecb850751926bce6cb63906` | [#290](https://github.com/fo4sf/fo4-to-starfield/pull/290) |
| `grok/hardlink-safe-writes-458-v2` | `500657f43cf398a4f5e22da5448350fff70a4c3f` | [#472](https://github.com/fo4sf/fo4-to-starfield/pull/472) |
| `grok/improve-failure-reporting` | `6deb2bb703b83a0a6e4358f64e9c99c7b5130556` | [#101](https://github.com/fo4sf/fo4-to-starfield/pull/101) |
| `grok/inventory-summary-reduced-tris` | `3601c9817a5ce4631b6140f6426d2882dfdb25fc` | [#310](https://github.com/fo4sf/fo4-to-starfield/pull/310) |
| `grok/launcher-cli-tests` | `cb40edeb777fb20d51583c961acb4ba5611b6b2f` | [#464](https://github.com/fo4sf/fo4-to-starfield/pull/464) |
| `grok/map-marker-restore` | `277606c86e2a2eb223a6baea42a0aaebf1933106` | [#296](https://github.com/fo4sf/fo4-to-starfield/pull/296) |
| `grok/map-markers` | `5ab0e7f789fa21bad5d31bac379e402c885de41f` | [#294](https://github.com/fo4sf/fo4-to-starfield/pull/294) |
| `grok/mass-scale-grab` | `569bf05c04e9c284a5e4a1a4d05cd125526c040b` | [#340](https://github.com/fo4sf/fo4-to-starfield/pull/340) |
| `grok/navmesh-losses` | `f5608fb0365533c3d3a31a764f4beee64de917c1` | [#314](https://github.com/fo4sf/fo4-to-starfield/pull/314) |
| `grok/playtest-palette` | `e4649a6c1b37316a6e05021144a2e366deb0bf11` | [#289](https://github.com/fo4sf/fo4-to-starfield/pull/289) |
| `grok/playtest-textures` | `1b8bcee7767ffa10634c2f5a4f56d6160a0943d9` | [#288](https://github.com/fo4sf/fo4-to-starfield/pull/288) |
| `grok/progress-reporting` | `0dad61c15420e9c713a64bcca223b7cec6c74df1` | [#311](https://github.com/fo4sf/fo4-to-starfield/pull/311) |
| `grok/r06-core64c-inventory` | `90428462df7d93f8aeaf03d722fcfb74cbe3fe77` | [#163](https://github.com/fo4sf/fo4-to-starfield/pull/163) |
| `grok/r06-core64n-convert` | `407368b473604ab1d4379262b81824dea856f3db` | [#169](https://github.com/fo4sf/fo4-to-starfield/pull/169) |
| `grok/retry-failures` | `550ef19508b36137dc0ecfe61c87d8c0adf91354` | [#333](https://github.com/fo4sf/fo4-to-starfield/pull/333) |
| `grok/summary-helpers` | `685942247d584ddc2adb20f486e0147df1a3b5b2` | [#309](https://github.com/fo4sf/fo4-to-starfield/pull/309) |
| `grok/surface-map-note` | `e6b0974020baf808dfea5ee3f592ce4b06fa7e4d` | [#317](https://github.com/fo4sf/fo4-to-starfield/pull/317) |
| `grok/terrain-evidence` | `831cf920a3bc02045fdedb10250f297ab356647d` | [#69](https://github.com/fo4sf/fo4-to-starfield/pull/69) |
| `grok/wp01-config-cli` | `ce68c9bb374f935629bd90465dcc53e6d4683614` | [#181](https://github.com/fo4sf/fo4-to-starfield/pull/181) |
| `grok/wp01-manifest-status` | `a62e716233a35a57fa1131577d8d58f641c6bab1` | [#312](https://github.com/fo4sf/fo4-to-starfield/pull/312) |

## Batch B: optional matching local refs

These six refs belong to the Codex Git store. Check out no branch and remove no worktree as part of this batch; revalidate each ref and all worktree bindings first.

- `codex/detect-ini-coverage` at `bbeb58f48f894376df5c215ce62f9ce923031ed3`.
- `codex/door-handoff-1017` at `a6c17c42855aacab2237204f0105250ee5d83f0a`.
- `codex/handoff-door-checkpoint-1016` at `dd7bcdb98962be2b04516e45a47cf0c207ede6b6`.
- `codex/native-probe-event-case` at `b9a7f6507e8daf5e2c559dcc9f1d46979bc433f4`.
- `codex/ordered-master-identity` at `9a9768283108cbb18532e5d0cddfebe85895a33a`.
- `codex/restore-plugins-namespace` at `ba4617549dbb95cd2a0731acf6dfeb7655aea75f`.

## Commit history, PRs and files

- Keep the existing commit graph, merge commits, PR discussions, tags and failed/passing evidence. No rebase, squash of published history, force-push, reset, garbage collection or history filtering is proposed. This preserves the source pins used by tests and saves.
- For future work, use one bounded purpose per PR, descriptive role-prefixed commits and a short final PR description. Consolidating duplicate proposals is a source review, not a history rewrite.
- Use [the preparation index](../research/framework/oct25-preparation.md) for overlapping BA2, version/status and door-clamp families. An author must identify unique code/tests and a reviewed successor before any old PR is proposed for closure. No PR closure list is approved here.
- Keep every worktree and its ignored/untracked files in this pass. A clean tracked Git status does not prove a worktree has no private assets, build outputs or recovery data. Filesystem cleanup requires its own inventory and verified preservation.
- Keep #544 as a lore intake PR, not a main-merge candidate. Keep visibility and branch-deletion settings unchanged.

## Review and approval checklist

- [x] Exact candidate names/hashes and matching merged PRs recorded; complete local main history used, not a shallow reachability guess.
- [x] Default/protected branches, open PR heads/bases and known checked-out branches excluded.
- [ ] Independent reviewer reproduces the candidate predicates and checks active ownership.
- [ ] Owner approves Batch A and, separately if desired, Batch B.
- [ ] Fresh pre-execution checks pass; changed candidates are withheld.
- [ ] Post-cleanup remote refs, retained main and open PR bases verified; recovery map retained.

No branches, commits, PRs, worktrees or files have been deleted by this proposal.
