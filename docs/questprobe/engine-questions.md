# Quest engine probe (N1): five questions in one plugin

Groundwork for the people-and-story phase. This is N1 of the NPC and quest research
(`research/next-phase/npcs-ai-factions-dialogue-quests.md`, section 9). Owner: Claude-cloud (the Vault 111 new game
thread). Status: staged on the PC at `D:\Modding\staging\questprobe_v1` (19 Oct, commit 7d5ad61): offline check
passes, all three scripts compile. Nothing is installed. It goes in only on the owner's word, after the current v6e test.

## Why

Converting Fallout 4's quests at full scale rests on five engine behaviours the mission could not settle:

| # | Question | Why it matters | What the mission saw |
|---|----------|----------------|----------------------|
| E1 | Does a stage **fragment** run when its stage is set? | FO4's quest logic lives in stage fragments; a converter recompiles them as fragments | not tried |
| E2 | Does **OnStageSet** fire on a quest script? | the mission's never did (18 Oct, unresolved why) | FAIL once |
| E3 | Does a quest **marker** follow a forced reference **alias**? | every FO4 objective points at an alias | alias existed, marker unchecked |
| E4 | Does **our own quest type** keyword get its own Missions-tab heading? | Main, Minutemen, Brotherhood, Railroad and Institute tabs | the mission used Starfield's side-quest type |
| E5 | Can a plugin hang **its own Story Manager branch** under Starfield's Script Event node and start a quest from it? | radiant quests, and fencing Starfield's own events out of our world | not tried |

## What the plugin is

`FO4SFQuestProbe.esm`. Its only master is Starfield.esm. It adds six records and overrides none:

- **QUST FO4SF_QProbe.** Start game enabled and run once. Stages 10, 20 and 100, where 100 completes the quest.
  Objective 10 is "Reach the marked door", targeting alias 0. Alias 0, Target, is optional and empty; the script fills
  it with ForceRefTo. Stage 10 carries a fragment (`FO4SF_QProbeFragments.Fragment_Stage_0010_Item_00`). Its quest
  type is our keyword. It carries the script `FO4SF_QProbeQuest`.
- **KYWD FO4SF_QuestTypeCommonwealth "Commonwealth".** It copies the keyword type of Starfield's QuestTypeSideQuest
  (047600).
- **KYWD FO4SF_QProbeEvent.** The story event the script sends.
- **QUST FO4SF_QProbeSM.** Event SCPT, not start game enabled. Only our branch can start it, and starting it only logs
  one line.
- **SMBN FO4SF_QProbeBranch.** It sits under Starfield's one Script Event SMEN, after that node's last child. Its
  condition is GetEventData GetIsID Keyword1 == FO4SF_QProbeEvent, so no Starfield event passes it.
- **SMQN FO4SF_QProbeNode.** It starts FO4SF_QProbeSM. It has **Shares Event** set, so even a match never takes an
  event away from Starfield's own nodes.

The writer copies three shapes from vanilla records in Starfield.esm rather than guessing them. `check` prints each one
as evidence:

- MQ00's VMAD versions and its stage-10 fragment layout. On the PC, 19 Oct, MQ00's only fragment was confirmed to be on
  stage 10. The writer also copies whether the fragment script is listed among the quest's scripts.
- QuestTypeSideQuest's keyword type.
- The Script Event node, its last child, and one vanilla GetEventData condition.

**Where it runs.** The quest idles, checking every 5 s, until the player shares a parent cell with the COC marker of
`FO4Port_BostonPublicLibrary02`. That is the safest outdoor route in the memory notes, far from Red Rocket,
Sanctuary and the museum. The marker's target is that cell's load door farthest from the COC marker. The installed
port's library has no load door (PC, 19 Oct), so the writer falls back to the farthest door, then the farthest object,
on the marker's floor (within 3 m of its height) and between 8 and 60 m away, so the player can walk to it. Both are
FO4Port.esm plugin-local ids, resolved at run time with `Game.GetFormFromFile`, the same contract as the new game
and FO4SF_LoadDoor. `--cell` picks another interior.

## The run (later, on the owner's word)

1. `coc FO4Port_BostonPublicLibrary02` (a cell editor id the port writes; the command is the one the tests already
   use).
2. Wait 15 s. A notification says the probe is done.
3. Take a screenshot of the compass for E3, then open the Missions tab and take a screenshot for E4.
4. Walk to the marked door: the objective completes and the quest ends at stage 100.
5. On the PC, run `python scripts\questprobe\make_questprobe.py log`. It prints the five answers. E1, E2 and E5 come
   from the log. E3 is FILLED in the log and its marker is confirmed by the compass screenshot. E4 is the Missions-tab
   screenshot.

The log is `My Games\Starfield\Logs\Script\User\fo4sf_qprobe.0.log`. Its result line looks like:

```
FO4SF_QPROBE rt=... result E1_fragment=PASS E2_onstageset=FAIL (0:) E3_alias=FILLED E4_questtype=LOOK E5_storymanager=PASS
```

**Reading each answer:**

- **E1.** If the fragment ran, recompiling FO4's fragments is the route. If not, the converter must drive stage
  actions itself, as the mission and the new game already do with AdvanceTo.
- **E2.** An event for 10, 20 and 100 means OnStageSet works and the mission's failure has another cause. No events
  confirms that nothing should rely on OnStageSet.
- **E3.** A marker on the compass means FO4 objectives convert as they are. No marker, with the alias FILLED, means
  objective targets need more than an alias (a flag or a keyword, still unresolved).
- **E4.** A "Commonwealth" heading means we can have one quest type per faction. Anything else means a mapping onto
  Starfield's types.
- **E5.** FO4SF_QProbeSM started means our own Story Manager tree is possible, and Starfield's events never reach it.

**Installing and removing it.** The test PC's Starfield reads no loose files (`sResourceDataDirsFinal=STRINGS\`
only, install thread, 19 Oct), so the three scripts ship in `FO4SFQuestProbe - Main.ba2`. `exp_install.py` holds one
experiment, so the probe is its own small deployment, as the bridge is. `scripts/questprobe/questprobe_install.py`
reuses `bridge_install.py`'s record, packing (the game's Archive2), archive check, Plugins.txt journal and exact
uninstall under the probe's names, with its own record `Data\FO4SFQuestProbe.install.json`; it refuses a staged
folder whose files differ from its `plan.json`. `pack-check` builds and checks the archive in a temporary folder
without touching the game.

```
python scripts\questprobe\questprobe_install.py pack-check --dir D:\Modding\staging\questprobe_v1 --starfield <game dir>
python scripts\questprobe\questprobe_install.py install    --dir D:\Modding\staging\questprobe_v1 --starfield <game dir>
python scripts\questprobe\questprobe_install.py uninstall  --starfield <game dir>
```
It writes nothing to a save except its own quests.

## Build (offline, PC)

```
python scripts\questprobe\make_questprobe.py precheck
python scripts\questprobe\make_questprobe.py stage --out D:\Modding\staging\questprobe_v1 --port <installed FO4Port.esm>
```

`precheck` reads only ContentResources.zip. It confirms that every native and event the three scripts use exists in
Starfield's base sources: SetStage, OnStageSet, Keyword.SendStoryEventAndWait (which returns Quest[] in Starfield), ReferenceAlias.ForceRefTo and the
rest. It also prints the declarations of SetStage, OnStageSet and SendStoryEventAndWait. `stage` writes the plugin,
checks it, compiles the three scripts, and writes `plan.json` and `README.txt`. All of it lands in a fresh folder of a
few kilobytes, published only when every step passed. `--no-sm` drops E5 if the Script Event node is not unique.

## Tests

- `dotnet run --project dotnet/QuestProbe -- selftest <dir>` builds a synthetic Starfield.esm with QuestTypeSideQuest,
  an MQ00 fragment and a Script Event node with two children. It also builds a port with the library: a COC marker,
  a near and a far load door, and a door with no teleport. It writes and checks both variants, rejects each build
  under the other's options, catches 14 mutations, and refuses an unknown cell.
- `tests/test_questprobe.py` covers the contract between the plugin, the scripts and make_questprobe.py:
  - properties, names, the fragment function, stages and the log name;
  - every call and event is prechecked;
  - no local is named after a Papyrus type (the new game's `door` compile failure, 19 Oct);
  - the precheck reader on a fake zip;
  - the log summary.

## Unresolved until it runs (labelled for the research log)

- **E3 and E4 are judged by eye** from screenshots. The log can only say whether the alias filled.
- **SEQ files.** The plugin ships no SEQ (the list of a plugin's start-game-enabled quests that the Creation Kit's
  -GenerateSEQ writes). The log's `init` line shows that FO4SF_QProbe, a start-game-enabled quest, started without one.
  No `init` line means a SEQ may be needed: the next step is a SEQ written next to the plugin, not a code change. In
  Skyrim a missing SEQ is known to break such quests' dialogue; the probe has no dialogue, so that half waits for a
  plugin that has some.
- **The gate member, verified** (PC, 19 Oct, `check` on the real Starfield.esm): under the Script Event node (195
  nodes), 91 GetEventData conditions: GetIsID Keyword1 x80, GetValue Value1 x9, HasKeyword OldLocation x2; the first
  is MissionBranchCargo, GetIsID Keyword1 05BD85 == 1. Our branch gates exactly that way. 418 Starfield quests carry
  event SCPT, as our Story Manager quest does.
- **The fragment.** MQ00's real layout (PC, 19 Oct): VMAD v6/2/3, fragment `Fragments:Quests:QF_MQ00_00005790.
  Fragment_Stage_0010_Item_00`, stage 10, index 0, unknowns 0/1, and the fragment script NOT listed among the quest's
  scripts. Ours copies all of it. Whether an unprefixed fragment
  script name (no `Fragments:Quests:` namespace) binds is part of what E1 answers.
