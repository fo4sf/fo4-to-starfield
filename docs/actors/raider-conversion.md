# The first converted Fallout 4 NPC: a Concord raider (2026-10-11)

Step 5 of the playable slice needs an NPC that walks and fights. "It does not walk" can come from the world (ground,
collision), from navigation (navmesh) or from the actor record itself. This page builds one converted actor and plans
tests that isolate the actor part: the converted record in a vanilla cell whose navmesh is known to be good, judged
against a vanilla actor with the same commands.

It builds on PR #61 (`docs/actors/npc-navigation.md`, section 4 "Minimal FO4 NPC conversion", ladder step N6) and
PR #68 (the `npc_nav` queue kind). Labels: **verified** (measured here, numbers given), **supported hypothesis**,
**unresolved**. Nothing was run in game, because the test chain was using Starfield. Every in-game statement below is
a hypothesis until N2a / N2b run.

Tools (all read-only on the game data): `dotnet/ActorRaider` (new, Claude's) and `scripts/actors/raider_map.py` (new).
Commands are at the end.

---

## 1. The source actor (verified, Fallout4.esm)

Red Rocket has no placed raider. `ActorRaider fo4-find <Fallout4.esm> -17 19 8 Raider` lists the placed actors within 8
cells of Red Rocket's cell (-17, 19) whose base EditorID contains "Raider". There are none in (-17, 19). The nearest
group is the Concord street fight at (-15, 17):

| ACHR | EditorID | base |
|---|---|---|
| **00046458** | **DN092concordRaider01** | **LvlRaider 0002898B** |
| 00046459 | DN092concordRaider03 | LvlRaider 0002898B |
| 0001D41F | DN092concordRaider02 | LvlRaider_Handmade_MG 0007B620 |
| 0008340B, 0008340C | (none) | LvlRaider 0002898B |
| 0001FA04 / 0004645F / 0004B2BA | (none) | LvlRaiderMelee / EncRaider01Melee / LvlRaider_Handmade_MG |

The chosen actor is **ACHR 00046458 `DN092concordRaider01`**. It is persistent, in the Commonwealth persistent cell
00018AA2, with location ref type `DN092_ConcordRaider` and level modifier Easy. Its position is
(-58,034.28, 70,581.68, 6,166.51), which is (-829.06, 1,008.31, 88.09) m at FO4 units / 70. With absolute alignment
that is Starfield cell (-9, 10). Its base `LvlRaider` is the generic leveled raider (PR #61 counts 210 placed raiders
using it).

Template chain (`ActorRaider export-fo4 <Fallout4.esm> 00046458 1`):

| step | record | contents |
|---|---|---|
| base | NPC_ 0002898B `LvlRaider` | ACBS template flags 0x19BF: Traits, Stats, Factions, SpellList, AiData, AiPackages, BaseData, Inventory, AttackData and Keywords come from templates. ModelOrAnimation, Script and DefPackList are its own. TPLT `LCharRaider`; TPTA Traits `LCharRaiderFaceAndGender`, every other slot `LCharRaider` |
| default | LVLN 00022E48 `LCharRaider` | "calculate from all levels <= player"; EncRaider01Template (level 1), EncRaider02 (4), EncRaider02b (9), EncRaider03 (14), EncRaider04 (21), EncRaider05 (30), EncRaider06 (39) |
| at player level 1-3 | NPC_ 0003183A `EncRaider01Template` | no template of its own: name "Raider", level 1 (AutoCalcStats), RaiderFaction rank 0, AI data, inventory |
| traits | LVLN 000FD3A3 `LCharRaiderFaceAndGender` | 14 faces, all at level 1 (encRaiderFaceM01..M09, F01..F05). The game picks one at random; the export takes the first, NPC_ 0004AF21 `encRaiderFaceM01` |

The Concord fight comes at the start of the game, so the player is at level 1-3 and only EncRaider01Template qualifies.
The chain itself is verified; that it is level 1 in practice is a supported hypothesis.

Effective values, each read from the record that its template category resolves to (verified):

- **Name:** "Raider".
- **Flags:** Respawn, AutoCalcStats.
- **Level:** 1. XP offset 5, disposition 35.
- **Faction:** RaiderFaction 0001CBED, rank 0.
- **AI:** VeryAggressive, Foolhardy, energy 50, AnyCrime, Neutral, HelpsFriendsAndAllies.
- **Combat:** combat style `csRaiderRanged`; package lists `DefaultMasterPackageList` / `DefaultCombatMasterPackageList`.
- **Inventory:** `LLI_Raider_Weapons`, which at level 1 holds `LL_HandmadeGun` x2 and `LL_DoubleBarrelShotgun` x1, plus
  grenades, stimpacks, caps and perk loot. Death item `LLD_Raider`.
- **Look:** outfit `Outfit_Raider`. Voice `RaiderMale01`, HumanRace, male, 14 head parts.
- **Other:** class `raiderClass`, perk `crDamage075`, keywords `AnimArchetypeIrritated` and `usePowerArmorFrameRaider`.

## 2. The Starfield template: Spacer, used without its leveled lists

**Spacer, not Ecliptic.**
- **Role:** Spacers are Starfield's lawless gangs, which is what FO4's raiders are. Ecliptic are mercenaries, which
  makes them FO4's Gunners.
- **Same structure (verified):**

  | | Fallout 4 | Starfield |
  |---|---|---|
  | leveled actor | NPC_ `LvlRaider` | NPC_ `LvlSpacer` 0027BB7B |
  | default template | LVLN `LCharRaider` (7 tiers) | LVLN `LCharSpacer` 0027BB7D (10 tiers: EncSpacer01Template at level 1 ... EncSpacer10 at 94) |
  | traits template | LVLN `LCharRaiderFaceAndGender` (14 faces) | LVLN `LCharSpacerFaceAndGender` 0027BB7C (7 faces: EncSpacerFaceF01-F03, M01-M04) |

  So the conversion can map tier to tier and face to face.
- **Hostile to the player (verified):** `SpacerFaction` 0027BB8C lists `PlayerFaction` 01C21C as Enemy and itself as
  Ally.

**Direct NPC_ templates, not the leveled lists.** The record templates on `EncSpacer01Template` (00270255, tier 1) and
`EncSpacerFaceM01` (0027BB78, the first male face), not on `LvlSpacer` / `LCharSpacer`. There are two reasons:
1. The look and level are the same in every test.
2. A template chain that goes through a leveled list makes the engine generate a base form for each spawned actor
   (supported hypothesis; Skyrim-era `GetLeveledActorBase` behaviour). If it does, `GetIsID <base>` may not confirm the
   spawn. PR #68's `N0_ptr_lvl` asks exactly this for the vanilla `LvlCitizen_NoOld`.

Whether `GetIsID` confirms a templated actor whose chain has no leveled list is **unresolved**. N2a measures it.

**Hostility works differently in the two games (verified).**
- **FO4:** `RaiderFaction` has 9 relations, none of them to `PlayerFaction`. FO4 raiders are hostile through AIDT
  Aggression VeryAggressive, which attacks on sight (CK semantics, supported hypothesis).
- **Starfield:** Spacers have Aggression Unaggressive and Confidence Brave. Their hostility comes from 6 RDSA
  reaction-radius entries (attack and warn radii, e.g. `RRadius_Enc_Attack_Enter`, `LinkReactionPrimitiveAttack`)
  plus the faction's Enemy relation.

The record inherits AiData, so the Starfield mechanism applies. The FO4 aggression value is recorded in the mapping
table but not used.

## 3. The record: `FO4ActorRaider.esm`

The plugin is one NPC_, 547 bytes, with Starfield.esm as its only master. It is staged at
`C:\Modding\staging\actor_raider1`.

| | |
|---|---|
| EditorID / local FormID | `FO4_LvlRaider` / F04800 (console 02F04800 at slot 02, see below) |
| inherited (template flags **0x7E3B**) | Traits from `EncSpacerFaceM01`. Stats, SpellList, AiData, AiPackages, Script, DefPackList, AttackData, Keywords and slots 13 / 14 from `EncSpacer01Template` |
| own (the Fallout 4 identity) | Factions, BaseData (name, flags), Inventory (weapon, outfits, death item) |

Mapping table (written by `raider_map.py spec`; the same as the staged `mapping.md`):

| Fallout 4 | value | Starfield | value | how |
|---|---|---|---|---|
| EDID | LvlRaider | EditorID | FO4_LvlRaider | prefixed |
| FULL | Raider | Name | Raider | copied (English string of the BaseData source) |
| RNAM race | HumanRace | Race | HumanRace 0000347D | mapped (Traits inherit the same race) |
| TPLT + TPTA | LCharRaider / LCharRaiderFaceAndGender | DefaultTemplate + TemplateActors | EncSpacer01Template / Traits EncSpacerFaceM01 | at player level 1, FO4 resolves to EncRaider01Template and encRaiderFaceM01; mapped tier for tier, without a leveled list |
| ACBS flags | Respawn, AutoCalcStats | Flags | Respawn | kept where Starfield has the flag; AutoCalcStats goes with the inherited Stats |
| ACBS level | 1 | Level | 8 | tier 1 -> tier 1: EncSpacer01Template's level (Stats inherited from it) |
| SNAM faction | RaiderFaction rank 0 | Factions | SpacerFaction + GroupFactionSpacers (rank 0); FormationFaction GroupFactionSpacers | mapped like EncSpacer01Template; hostility through SpacerFaction's Enemy relation to PlayerFaction |
| CNTO weapons | LL_HandmadeGun / LL_DoubleBarrelShotgun | Items | Coachman 0026D96B x1 | the double barrel shotgun entry: same weapon type. NPCs need no ammo (`NpcsUseAmmo` False in the WEAP record, verified). Pipe guns: no analog chosen |
| CNTO other | stimpacks, grenades, caps, perk loot, LLD_Raider | Items | none | dropped (loot comes from the death item) |
| INAM death item | LLD_Raider | DeathItem | LLD_Spacer | mapped |
| DOFT outfit | Outfit_Raider | DefaultOutfit | Outfit_Clothes_Mechanic_Tanktop_Brown | placeholder look (vanilla Spacers have no default outfit) |
| (none) | | SpaceOutfit | Outfit_Spacesuit_Spacer_AssaultOrNoRole | what the Spacer templates wear |
| ZNAM combat style | csRaiderRanged | CombatStyle | csSpacer_Assault | mapped |
| DPLT / ECOR | DefaultMasterPackageList / DefaultCombatMasterPackageList | DefaultPackageList / CombatOverridePackageList | DefaultMasterPackageList_Human / DefaultCombatMasterPackageList | mapped (DefPackList is inherited too, with the same list) |
| AIDT | VeryAggressive, Foolhardy, AnyCrime, HelpsFriendsAndAllies | AI data | inherited | from EncSpacer01Template: Unaggressive, Brave + 6 reaction radii |
| VTCK voice | RaiderMale01 | Voice | SpacerMale01 | inherited from EncSpacerFaceM01; the same value is also written, as vanilla templated NPC_ records do (LvlSpacer_Male) |
| CNAM class | raiderClass | Class | CrimsonFleetClass | inherited from EncSpacer01Template; the same value is written |
| PRPS, PRKR, KWDA | 12 actor values, crDamage075, 2 keywords | Properties, Perks, Keywords | inherited | from EncSpacer01Template |
| PNAM, face | 14 head parts | HeadParts, Tints, morphs | inherited | from EncSpacerFaceM01 (12 head parts): placeholder appearance |

### Details

**Template slots 13 and 14.** Starfield has 15 template slots. Mutagen 0.55.0-alpha.67 calls the last two
`TemplateActors.Unknown1` / `Unknown2`, and its `Npc.TemplateActorType` has no names for bits 13 and 14
(`ActorRaider sf-tplstats`).

In Starfield.esm, 5,445 of 7,131 NPC_ records use templates. Bit 13 is set in 2,825 of them and bit 14 in 4,253. In
records whose slots point at different templates, slots 13 and 14 almost always share the template of the behaviour
categories. The most common match is Stats + Factions + SpellList + AiData + AiPackages + Inventory + Script +
DefPackList + AttackData + Keywords (961 records for slot 13, 847 for slot 14). The exceptions:
- they never match Traits alone;
- they match Traits + BaseData in 1 record each;
- they point at a template that no other slot uses in 6 records (slot 13) and 26 records (slot 14).

So the record inherits them with the behaviour template (supported hypothesis). What they mean is unresolved.

**Raw layout (verified, `ActorRaider rawsubs`).** The subrecords in order:
`EDID OBND ODTY ACBS SNAM SNAM INAM VTCK TPLT TPTA(60 B) RNAM ECOR COCT CNTO AIDT STOP CNAM FULL DATA DNAM ZNAM NAM5 NAM6
NAM4 MWGT DOFT SOFT DPLT HEFA`. This is the order of vanilla `EncSpacer01Template`, minus the inherited PRPS / RDSA /
face blocks.

ACBS holds:
- flags 8 (Respawn)
- XP offset 5
- level 8
- disposition 35
- template flags 0x7E3B

**Console FormID.** The record is 02F04800 when `FO4ActorRaider.esm` is the first line of Plugins.txt.
`exp_install.py` appends the plugin, then `cycle.ps1` re-appends FO4Port.esm after it. The first user plugin is at slot
02 (supported hypothesis). Evidence for that:
- the S2 spike: `placeatme 02000800`; slots 01 and 03-0B returned "not found";
- the terrain queue's anchor `prid 02000800` read the anchor's position on 2026-10-11 (`terrain_exp2b2`, `obs.json`).

FO4Port.esm's highest local FormID is DE5C (verified, raw scan of the pinned build `integ_1011`). So a wrong slot finds
no form at all (INCONCLUSIVE SPAWN), never a different object.

## 4. What Mutagen can and cannot write (Starfield NPC_)

**Typed.** Every field this record sets has a typed property.

**Partly typed.**
- Template slots 13 and 14, and flag bits 13 and 14: written as raw bits.
- RDSA reaction radii: the fields have generic names (`UnknownInt`, `UnknownLink1..9`, `UnknownFloat1..6`).
- The last AIDT byte: `UnknownAIDT`.

**Raw bytes only.** `NAM5` (`FF00` in every sampled vanilla NPC_), `ONA2`, `XALG`, `EYEC`, `HCLR` / `BCLR`.

**Round trip (verified).** `ActorRaider roundtrip` copied 6 vanilla NPC_ records into an override plugin, wrote it and
compared every subrecord with Starfield.esm, decompressed. The records were EncSpacer01Template, EncSpacerFaceM01,
LvlSpacer_Male, LvlSpacer, EncCitizen01Template and LvlCitizen_NoOld.

- 1 record was byte-identical.
- 2 differ only in FULL. The localized string ID (4 B) comes back as an inline string. This is expected, because the
  override plugin is not localized.
- 3 get an empty `STOP` after RDSA, where vanilla has none. Mutagen always writes the marker. In vanilla, 4,310 of
  7,131 NPC_ records carry it before CNAM, 32 of them right after RDSA. That it is harmless is a supported hypothesis.
- Everything else matched byte for byte, including the partly typed and raw subrecords: TPTA (60 B), AIDT (7 B), RDSA
  (480 B), NAM5 and the face data.

**Other observations.**
- An unset voice or class link is still written, as a null VTCK / CNAM. That is why the record sets both.
- Re-reading a written plugin needs the master style (`BinaryReadParameters.MasterFlagsLookup`, as in
  `ReferenceLinks/PluginReader.cs`).

Nothing the record needs is missing from Mutagen. A faithful FO4 face would also need the face morph and tint mapping;
that is out of scope (traits are inherited).

## 5. In-game tests (npc_nav, PR #68's format)

N2a and N2b use the same cell, points, drop, reads and thresholds as N0 (`C:\Modding\staging\npc_nav_n0`):
- cell `coc QASmoke` (vanilla navmesh 002BE3AA);
- A (-8, -4, 0) and B (5, 10, 0), 19.1 m apart;
- reads at 0 / 3 / 8 / 15 / 30 s;
- PASS within 2.5 m of B, or 5 m closer to it.

There is one deviation from N0: `handle_tol` is 3 m instead of 2 m. Hostile actors may step away from the player's
feet while the runner confirms the handle, because game time runs between the console sessions. The check only
establishes which ref was spawned, and 3 m equals the judge's `spawn_tol`.

Every test relaunches the game (`--fresh`). The queue's pre-launch step installs `actor_raider1` (plugin only, no
archive).

| run | test | actor | method | expect | basis |
|---|---|---|---|---|---|
| N2a | N2a_base | raider 02F04800 | none (baseline) | FAIL WANDER | supported hypothesis: SpacerFaction is Enemy to PlayerFaction and the Spacer reaction radii are inherited, so it comes for the player without a command |
| N2a | N2a_ptr | raider | `PathToRef player` | PASS | verified: the navmesh covers A and B (PR #61 3.1); supported hypothesis: the converted actor walks |
| N2a | N2a_cf | raider | `cf "Actor.PathToReference" player 1.0` | PASS | as N2a_ptr; the `cf` syntax is settled by N0_cf |
| N2a | N2a_follow | raider | `SetPlayerTeammate 1` + `EvaluatePackage` | PASS | supported hypothesis: a teammate follows, even one that was hostile |
| N2b | N2b_spacer_combat | EncSpacer01Template 00270255 (vanilla, not templated; rifle from its leveled list) | `StartCombat player` | PASS | supported hypothesis; the **control** of N2b |
| N2b | N2b_combat | raider | `StartCombat player` | PASS | supported hypothesis: inherited Spacer combat AI with a short-range shotgun closes in |

**Gate.** A new plan field, `control_npc` (`scripts/game/testqueue.py`), names the actor whose control (same method)
and baseline gate a test's FAIL. Without it, that is the test's own actor.

- N2a_ptr / _cf / _follow carry `control_npc` 002B211C. Their FAIL counts only if the matching N0 control
  (EncCitizen01Template, same method) and N0_base passed in `npc_nav_n0`.
- N2b_combat carries 00270255. Its FAIL counts only if N2b_spacer_combat passed.
- In every other case the result is INCONCLUSIVE CONTROL, and `report` applies the gate again later.
- PASS is never gated.

Without `control_npc`, a converted actor would always be INCONCLUSIVE CONTROL, because the vanilla cell has no control
of that actor.

Reading the results:

| result | meaning |
|---|---|
| INCONCLUSIVE SPAWN everywhere, and N0_ptr_lvl also INCONCLUSIVE SPAWN | `GetIsID` does not confirm templated actors. This is a runner question, not an actor failure |
| INCONCLUSIVE SPAWN, with the place OCR showing an unknown form | the plugin did not load, or it is not at slot 02 (check Plugins.txt order) |
| N2a NONAV / STALLED, with N0's control and baseline passed | **actor conversion failure** (template, AI, animation) |
| N2a PASS | the converted actor spawns, takes a handle, moves on a known navmesh and is removed. It is hostile (N2a_base WANDER), so this shows that it moves, not that the command moved it (N0 shows the command works) |
| N2a_base PASS (stayed away) | the hostility did not carry over (faction or reaction radii) |
| N2b_combat PASS | it engages and closes in |
| N2b_combat FAIL, N2b_spacer_combat PASS | the vanilla Spacer closes in and the raider does not: actor conversion (weapon, inventory, inherited AI) |
| both FAIL | the approach rule does not show engagement (a ranged fighter can hold its distance). Look at the `npc*.png` screenshots |

Plan the queues from the checkout that runs the chain, once this branch is merged into it. That checkout needs
`control_npc` and the plugin-only install. `npc_nav_n0` must be planned first.

```powershell
$py = "C:\Modding\venv-render\Scripts\python.exe"
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\npc_nav_n2a `
      --out C:\Modding\testqueue\npc_nav_n2a --install-exp C:\Modding\staging\actor_raider1 --plugins FO4ActorRaider.esm `
      --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\npc_nav_n2b `
      --out C:\Modding\testqueue\npc_nav_n2b --install-exp C:\Modding\staging\actor_raider1 --plugins FO4ActorRaider.esm `
      --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh
```

Chain lines, after `npc_nav_n0`: `?npc_nav_n2a`, then `?npc_nav_n2b`. Both commands were checked by planning into a
scratch folder: 4 + 2 tests on build 2470f876, with the pre-launch install of `FO4ActorRaider.esm`.

## 6. What was checked offline, and what was not

**Checked (verified).**
- The writer validated every Starfield link: FormID, EditorID and record type, 25 links to 14 records.
- `check` re-read the plugin with Mutagen: one NPC_, master Starfield.esm, every link and every inherited category
  resolves, the template targets are NPC_ records (not leveled lists), and there were 0 problems.
- 17 synthetic tests (`tests/test_actor_raider.py`) cover:
  - the mapping;
  - the spec / writer contract (keys and template slots read from `Writer.cs`);
  - the plans passing `plan-npc` validation;
  - the `control_npc` gate;
  - the plugin-only install.
- The full suite passes (415 tests).

**Not checked.** Anything in game: whether Starfield loads the record, spawns it, shows the face, or runs the inherited
AI.

## 7. Next

- **N2c**, after N2a passes and the converted navmesh passes N1 (PR #71): the raider at its converted Concord position
  (-829.06, 1,008.31, 88.09) m, on the core64 overlay (PR #72, which reaches Concord).
- **More of the raider ladder:** EncRaider02.. mapped to EncSpacer02.. by tier; random faces through
  `LCharSpacerFaceAndGender` once the GetIsID question is settled; an own `FO4_RaiderFaction`; FO4 weapons and outfits
  after the weapon / skinning milestones.

## Commands

`$f4` and `$sf` are the two games' Data folders; output goes to the staging folder, never the game folder.

```powershell
dotnet run --project dotnet\ActorRaider -c Release -- fo4-find $f4\Fallout4.esm -17 19 8 Raider
dotnet run --project dotnet\ActorRaider -c Release -- export-fo4 $f4\Fallout4.esm 00046458 1 C:\Modding\staging\actor_raider1\work\fo4_raider.json
& $py scripts\actors\raider_map.py spec --fo4 C:\Modding\staging\actor_raider1\work\fo4_raider.json `
      --out C:\Modding\staging\actor_raider1\spec.json --table C:\Modding\staging\actor_raider1\mapping.md
dotnet run --project dotnet\ActorRaider -c Release -- write $sf\Starfield.esm C:\Modding\staging\actor_raider1\spec.json C:\Modding\staging\actor_raider1
dotnet run --project dotnet\ActorRaider -c Release -- check $sf\Starfield.esm C:\Modding\staging\actor_raider1\FO4ActorRaider.esm C:\Modding\staging\actor_raider1\check.json
& $py scripts\actors\raider_map.py plans --stage C:\Modding\staging\actor_raider1 --n2a C:\Modding\staging\npc_nav_n2a --n2b C:\Modding\staging\npc_nav_n2b
# evidence
dotnet run --project dotnet\ActorRaider -c Release -- roundtrip $sf\Starfield.esm 00270255,0027BB78,0010DD71,0027BB7B,002B211C,0000CF96 <scratch> <out.json>
dotnet run --project dotnet\ActorRaider -c Release -- sf-tplstats $sf\Starfield.esm
dotnet run --project dotnet\ActorRaider -c Release -- rawcount $sf\Starfield.esm NPC_ STOP
dotnet run --project dotnet\ActorRaider -c Release -- sf-dump $sf\Starfield.esm 00270255,0027BB78,0027BB8C,0026D96B
```
