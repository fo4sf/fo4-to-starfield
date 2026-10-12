# The first converted Fallout 4 NPC: a Concord raider (2026-10-11, revised 2026-10-12)

Step 5 of the playable slice needs an NPC that walks and fights. "It does not walk" can come from the world (ground,
collision), from navigation (navmesh) or from the actor record itself. This page builds one converted actor and plans
tests that isolate the actor part: the converted record in a vanilla cell whose navmesh is known to be good, judged
against vanilla actors that are in the same situation (calm against calm, hostile against hostile).

It builds on PR #61 (`docs/actors/npc-navigation.md`, section 4 "Minimal FO4 NPC conversion", ladder step N6) and
PR #68 (the `npc_nav` queue kind). Labels: **verified** (measured here, numbers given), **supported hypothesis**,
**unresolved**, **refuted**. Nothing was run in game, because the test chain was using Starfield. Every in-game
statement below is a hypothesis until N2a / N2b run.

Tools (all read-only on the game data): `dotnet/ActorRaider` (new, Claude's) and `scripts/actors/raider_map.py` (new).
Commands are at the end. Section 8 lists what the first version of this page (2026-10-11) got wrong.

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
2. A template chain that goes through a leveled list may make the engine generate a base form for each spawned actor
   (supported hypothesis; Skyrim-era `GetLeveledActorBase` behaviour). If it does, `GetIsID <base>` may not confirm the
   spawn. PR #68's `N0_ptr_lvl` asks this for the vanilla `LvlCitizen_NoOld`, whose TPLT is the LVLN 002B2120
   `LCharCitizen`: it tests a chain WITH a leveled list.

**Whether `GetIsID` confirms a templated actor whose chain has no leveled list is unresolved.** Nothing measured so
far bears on it (N0_ptr_lvl tests the other case). Every N2 test needs `GetIsID 02F0480x` to read 1, at the spawn and
at every sample. N2a_base answers the question first: its spawn is confirmed or not. Every other N2 test requires
N2a_base to be decided (PASS or FAIL), waits for it, and is not run (INCONCLUSIVE PRECONDITION, no launch spent) when it
never is. Avoiding the leveled lists keeps the chain as simple as it can be; it does not by itself show that no
generated base is involved.

**Hostility works differently in the two games (verified).**
- **FO4:** `RaiderFaction` has 9 relations, none of them to `PlayerFaction`. FO4 raiders are hostile through AIDT
  Aggression VeryAggressive, which attacks on sight (CK semantics, supported hypothesis).
- **Starfield:** Spacers have Aggression Unaggressive and Confidence Brave. Their hostility comes from 6 RDSA
  reaction-radius entries (attack and warn radii, e.g. `RRadius_Enc_Attack_Enter`, `LinkReactionPrimitiveAttack`)
  plus the faction's Enemy relation.

The record inherits AiData, so the Starfield mechanism applies. The FO4 aggression value is recorded in the mapping
table but not used.

## 3. The plugin: `FO4ActorRaider.esm` (actor_raider2)

One plugin, 1,288 bytes, Starfield.esm its only master, staged at `C:\Modding\staging\actor_raider2` (actor_raider1,
the first build, is kept unchanged for reference). Two records:

| record | local FormID (console at slot 02) | what |
|---|---|---|
| `FO4_LvlRaider` | F04800 (02F04800) | **the conversion**: SpacerFaction + GroupFactionSpacers, formation faction GroupFactionSpacers. Judged in N2b |
| `FO4_LvlRaider_Calm` | F04801 (02F04801) | **the calm probe**: the same record without factions and formation faction, so nothing gives it an Enemy relation to the player. Judged in N2a |

The two differ only in EDID, the two SNAM and HEFA (verified, raw subrecord comparison).

| | |
|---|---|
| inherited (template flags **0x7E3B**) | Traits from `EncSpacerFaceM01`. Stats, SpellList, AiData, AiPackages, Script, DefPackList, AttackData, Keywords and slots 13 / 14 from `EncSpacer01Template` |
| own (the Fallout 4 identity) | Factions, BaseData (name, flags), Inventory (weapon, outfits, death item) |
| carried like every vanilla NPC_ | PRPS (the Stats template's 12 values), STON 0 and PRON Unspecified (the Traits template's), EDCT 0; record header form version 581 |

Mapping table (written by `raider_map.py spec`; the same as the staged `mapping.md`):

| Fallout 4 | value | Starfield | value | how |
|---|---|---|---|---|
| EDID | LvlRaider | EditorID | FO4_LvlRaider | prefixed |
| FULL | Raider | Name | Raider | copied (English string of the BaseData source) |
| RNAM race | HumanRace | Race | HumanRace 0000347D | mapped (Traits inherit the same race) |
| TPLT + TPTA | LCharRaider / LCharRaiderFaceAndGender | DefaultTemplate + TemplateActors | EncSpacer01Template / Traits EncSpacerFaceM01 | at player level 1, FO4 resolves to EncRaider01Template and encRaiderFaceM01; mapped tier for tier, without a leveled list |
| ACBS flags | Respawn, AutoCalcStats | Flags | Respawn | kept where Starfield has the flag; AutoCalcStats goes with the inherited Stats |
| ACBS level | 1 | Level | 8 | tier 1 -> tier 1: EncSpacer01Template's level (Stats inherited from it) |
| SNAM faction | RaiderFaction rank 0 | Factions | SpacerFaction + GroupFactionSpacers (rank 0); FormationFaction GroupFactionSpacers | mapped like EncSpacer01Template; hostility through SpacerFaction's Enemy relation to PlayerFaction. The calm probe has none |
| CNTO weapons | LL_HandmadeGun / LL_DoubleBarrelShotgun | Items | Coachman 0026D96B x1 | the double barrel shotgun entry: same weapon type. No ammo given: **supported hypothesis** that an NPC needs none (`NpcsUseAmmo` False in the WEAP, verified; 74 of 84 vanilla NPC_ with a WEAP directly in CNTO carry no AMMO, the companions among them, verified). Pipe guns: no analog chosen |
| CNTO other | stimpacks, grenades, caps, perk loot, LLD_Raider | Items | none | dropped (loot comes from the death item) |
| INAM death item | LLD_Raider | DeathItem | LLD_Spacer | written, but **probably overridden** (supported hypothesis, below): the effective death item may be none |
| DOFT outfit | Outfit_Raider | DefaultOutfit | Outfit_Clothes_Mechanic_Tanktop_Brown | placeholder look (vanilla Spacers have no default outfit) |
| (none) | | SpaceOutfit | Outfit_Spacesuit_Spacer_AssaultOrNoRole | what the Spacer templates wear |
| ZNAM combat style | csRaiderRanged | CombatStyle | csSpacer_Assault | written, but **probably taken from AI Data** (supported hypothesis, below); the inherited value is the same csSpacer_Assault (verified) |
| DPLT / ECOR | DefaultMasterPackageList / DefaultCombatMasterPackageList | DefaultPackageList / CombatOverridePackageList | DefaultMasterPackageList_Human / DefaultCombatMasterPackageList | mapped (DefPackList is inherited too, with the same list) |
| AIDT | VeryAggressive, Foolhardy, AnyCrime, HelpsFriendsAndAllies | AI data | inherited | from EncSpacer01Template: Unaggressive, Brave + 6 reaction radii |
| VTCK voice | RaiderMale01 | Voice | SpacerMale01 | inherited from EncSpacerFaceM01; the same value is also written, as vanilla templated NPC_ records do (LvlSpacer_Male) |
| CNAM class | raiderClass | Class | CrimsonFleetClass | inherited from EncSpacer01Template; the same value is written |
| PRPS | 12 actor values | Properties | EncSpacer01Template's 12, copied | inherited with Stats; written too, because every vanilla NPC_ carries PRPS (below) |
| (none) | | STON, PRON, EDCT | 0, Unspecified (EncSpacerFaceM01's), 0 | in every vanilla NPC_ (below) |
| PRKR, KWDA | crDamage075, 2 keywords | Perks, Keywords | inherited | from EncSpacer01Template |
| PNAM, face | 14 head parts | HeadParts, Tints, morphs | inherited | from EncSpacerFaceM01 (12 head parts): placeholder appearance |

### Details

**Subrecords every vanilla NPC_ carries (verified, raw scan of Starfield.esm, `ActorRaider rawcount` and an independent
Python scan).** 16 subrecord types are in all 7,131 NPC_ (EDID in 7,130): EDID, OBND, ODTY, ACBS, RNAM, PRPS, AIDT,
DATA, DNAM, NAM5, NAM6, NAM4, MWGT, EDCT, STON, PRON. That includes all 2,821 that inherit Traits (2,019 of them with
a TPLT). The first build lacked PRPS, STON, EDCT and PRON. Mutagen writes them only when told:
- PRPS (`Properties`): copied from the Stats template. Vanilla templated records carry their template's values: PRPS
  equals the Stats template's in 2,692 of 4,046 Stats-templated NPC_ whose Stats template is an NPC_ (verified).
- STON (`SkinToneIndex`, 1 byte) and PRON (`Pronoun`, 1 byte): copied from the Traits template. They equal the Traits
  template's in 2,287 and 2,317 of 2,318 Traits-templated NPC_ whose template is an NPC_ (verified).
- EDCT (1 byte): the number of tint blocks (MNAM TNAM QNAM VNAM NNAM INTV). It equals the number of MNAM in all 7,131
  records (verified). Mutagen writes it from `Tints`, but only when the list is set: an empty list writes EDCT 0 and no
  block, as in EncSpacer01Template and 4,110 other vanilla NPC_ (verified on the written plugin).
`ActorRaider check` now reports any written NPC_ that lacks one of the 16; it reports 2 problems for actor_raider1 and
0 for actor_raider2. Whether the game needed them is **unresolved** (nothing was tested without them); they are written
so that this is not one of the suspects.

**Form version (verified).** All 7,131 vanilla NPC_ have record header form version 581. Mutagen writes 576 unless
told; the first build was 576. Other plugins with version 576 records load (FO4Port.esm, the terrain plugins), but no
576 NPC_ was ever tested. The records are now 581. Mutagen's round trip of 6 vanilla NPC_ keeps 581 and writes their
subrecords back byte for byte (below), so the layout it writes is 581's (supported hypothesis).

**Death item and combat style.** Which template category owns INAM and ZNAM in Starfield is **unresolved**. In the
template semantics xEdit documents for Skyrim and Fallout 4 (the same CK lineage; a **supported hypothesis** for
Starfield), the death item goes with Traits and the combat style with AI Data, and both are inherited here:
- the Traits template EncSpacerFaceM01 has no INAM, so the effective death item may be none. Vanilla LvlSpacer has the
  same shape (its own INAM LLD_Spacer, Traits from faces without one), and 65 vanilla NPC_ inherit Traits from an NPC_
  without INAM while carrying their own (verified). If the death item matters, the next step is a Traits template
  with one, or an own Traits category;
- the AI Data template EncSpacer01Template's combat style is csSpacer_Assault (verified), the value written, so the
  effective combat style is the same either way.

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

**Raw layout (verified, `ActorRaider rawsubs`).** The conversion, in order:
`EDID OBND ODTY ACBS SNAM SNAM INAM VTCK TPLT TPTA(60 B) RNAM ECOR PRPS(144 B) COCT CNTO AIDT STOP CNAM FULL DATA DNAM
ZNAM NAM5 NAM6 NAM4 MWGT DOFT SOFT DPLT HEFA EDCT STON PRON`. The calm probe is the same without the two SNAM and HEFA.
Compared with vanilla `EncSpacer01Template` (`... HEFA EDCT MRSV BMPN BMPV STON PRON`), the record has no RDSA (AI Data
inherited), no MRSV / BMPN / BMPV (body morphs: in 766 / 3,122 / 3,122 of 7,131 vanilla NPC_, not universal) and
no face blocks (Traits inherited; vanilla templated records usually carry a copy of the Traits template's face, the
record does not). It has a STOP, see the round trip.

ACBS holds:
- flags 8 (Respawn)
- XP offset 5
- level 8
- disposition 35
- template flags 0x7E3B

**Console FormIDs.** The records are 02F04800 / 02F04801 when `FO4ActorRaider.esm` is the first line of Plugins.txt.
`exp_install.py` appends the plugin, then `cycle.ps1` re-appends FO4Port.esm after it. The first user plugin is at slot
02 (supported hypothesis). Evidence for that:
- the S2 spike: `placeatme 02000800`; slots 01 and 03-0B returned "not found";
- the terrain queue's anchor `prid 02000800` read the anchor's position on 2026-10-11 (`terrain_exp2b2`, `obs.json`).

FO4Port.esm's highest local FormID is DE5C (verified, raw scan of the pinned build `integ_1011`). So a wrong slot finds
no form at all (INCONCLUSIVE SPAWN), never a different object.

## 4. What Mutagen can and cannot write (Starfield NPC_)

**Typed.** Every field this record sets has a typed property, PRPS / STON / PRON / EDCT included (`Properties`,
`SkinToneIndex`, `Pronoun`, `Tints` as EDCT's counter).

**Partly typed.**
- Template slots 13 and 14, and flag bits 13 and 14: written as raw bits.
- RDSA reaction radii: the fields have generic names (`UnknownInt`, `UnknownLink1..9`, `UnknownFloat1..6`).
- The last AIDT byte: `UnknownAIDT`.

**Raw bytes only.** `NAM5` (`FF00` in every sampled vanilla NPC_), `ONA2`, `XALG`, `EYEC`, `HCLR` / `BCLR`.

**What Mutagen does not do by itself (verified).** A new `Npc` gets none of PRPS, STON, PRON, EDCT, and the record
header form version 576; a link set to `FormKey.Null` is written as a null subrecord (the probe's HEFA was 00000000 in
a first write; no vanilla NPC_ has a null HEFA), so the writer leaves unset links unset. Nothing the record needs is
beyond Mutagen, but the writer has to set these explicitly.

**Round trip (verified).** `ActorRaider roundtrip` copied 6 vanilla NPC_ records into an override plugin, wrote it and
compared every subrecord with Starfield.esm, decompressed. The records were EncSpacer01Template, EncSpacerFaceM01,
LvlSpacer_Male, LvlSpacer, EncCitizen01Template and LvlCitizen_NoOld.

- 1 record was byte-identical (EncSpacerFaceM01).
- 2 differ only in FULL. The localized string ID (4 B) comes back as an inline string. This is expected, because the
  override plugin is not localized.
- 3 get an empty `STOP` where vanilla has none: LvlSpacer_Male and LvlSpacer after RDSA, LvlCitizen_NoOld after KWDA
  (its subrecords go `AIDT KSIZ KWDA CNAM`; it has no RDSA). Mutagen always writes the marker; the converted records
  have it after AIDT.
- Everything else matched byte for byte, including the partly typed and raw subrecords: TPTA (60 B), AIDT (7 B), RDSA
  (480 B), NAM5 and the face data. The form version stays 581.

**STOP.** In vanilla, 4,310 of 7,131 NPC_ carry an empty STOP, before CNAM or DATA: 1,722 right after AIDT (1,293 of
them followed by CNAM, 429 by DATA), 32 after RDSA (verified). Those 4,310 are exactly the NPC_ that do **not** inherit
Traits; none of the 2,821 that inherit Traits has one (verified). The three round-trip records that gained a STOP all
inherit Traits, and so do the converted records. That a STOP is harmless remains a **supported hypothesis**: the game
reads a lone STOP right after AIDT in 1,722 vanilla records, but never in a record that inherits Traits. Removing it would
need a byte patch after Mutagen; it is the first thing to try if N2a's calm probe fails to spawn.

**Other observations.**
- Re-reading a written plugin needs the master style (`BinaryReadParameters.MasterFlagsLookup`, as in
  `ReferenceLinks/PluginReader.cs`).
- A faithful FO4 face would also need the face morph and tint mapping; that is out of scope (traits are inherited).

## 5. In-game tests (npc_nav, PR #68's format)

N2a and N2b use the same cell, points, drop, reads and thresholds as N0 (`C:\Modding\staging\npc_nav_n0`):
- cell `coc QASmoke` (vanilla navmesh 002BE3AA);
- A (-8, -4, 0) and B (5, 10, 0), 19.1 m apart;
- reads at 0 / 3 / 8 / 15 / 30 s;
- PASS within 2.5 m of B, or 5 m closer to it.

Every test relaunches the game (`--fresh`). The queue's pre-launch step installs `actor_raider2` (plugin only, no
archive).

**The design: calm against calm, hostile against hostile.** A commanded walk only says something about the command
when nothing else moves the actor. The conversion is hostile, so its combat AI, not `PathToRef` or `SetPlayerTeammate`,
would drive any walk, and N0's calm citizen would be no fair control for it: a shotgunner holding its distance or
taking cover would read as NONAV / STALLED, a conversion failure. So:
- **N2a (navigation on command)** runs the calm probe, which is calm like N0's citizen, with N0's methods. N0's
  controls and baseline gate its FAILs (`control_npc` 002B211C), and its own baseline (N2a_base, no command) says
  whether a PASS is the command's doing.
- **N2b (hostility)** runs the conversion and the vanilla Spacer template it inherits its behaviour from, both without
  a command. The vanilla Spacer is the reference: the hostility carried over when both come for the player. N2b sends
  no `StartCombat`: on actors that are already hostile it cannot be told apart from their own hostility.

| run | test | actor | method | expect | basis |
|---|---|---|---|---|---|
| N2a | N2a_base | calm probe 02F04801 | none (baseline) | PASS (stays away) | supported hypothesis: no Enemy relation (no factions), AI data Unaggressive (verified). Its spawn also answers the GetIsID question |
| N2a | N2a_ptr | calm probe | `PathToRef player` | PASS | verified: the navmesh covers A and B (PR #61 3.1); supported hypothesis: the converted record walks on command like N0's citizen |
| N2a | N2a_cf | calm probe | `cf "Actor.PathToReference" player 1.0` | PASS | as N2a_ptr; the `cf` syntax is settled by N0_cf |
| N2a | N2a_follow | calm probe | `SetPlayerTeammate 1` + `EvaluatePackage` | PASS | supported hypothesis: it follows as N0's citizen does (N0_follow); no claim about a hostile actor |
| N2b | N2b_spacer_base | EncSpacer01Template 00270255 (vanilla, not templated; rifle; no head parts, so a default look, cosmetic only) | none | FAIL WANDER (comes) | supported hypothesis: SpacerFaction is Enemy to PlayerFaction (verified); the reference |
| N2b | N2b_base | conversion 02F04800 | none | FAIL WANDER (comes) | supported hypothesis: the same faction and the inherited Spacer AI data |

N2a keeps N0's `handle_tol` (2 m). N2b uses 3 m: a hostile actor may step away from the player's feet while the runner
confirms the handle, because game time runs between the console sessions. The check only establishes which ref was
spawned, and 3 m equals the judge's `spawn_tol`.

**Runner changes for these runs (`scripts/game/testqueue.py`, with tests).**
- `control_npc` (plan field): the actor whose control (same method) and baseline gate a test's FAIL instead of its own.
  N2a_ptr / _cf / _follow carry 002B211C: their FAIL counts only if the matching N0 control and N0_base passed in
  `npc_nav_n0`; otherwise INCONCLUSIVE CONTROL, re-applied by `report`. PASS is never gated.
- `requires` may name a test of the same queue (no `queue` key) by label, and `verdict` may be `DECIDED` (PASS or
  FAIL). N2a_ptr / _cf / _follow require N2a_base DECIDED; N2b_base requires N2a's N2a_base DECIDED (a cross-queue
  requires, resolved by label, whose queue must install the same staged folder). A test whose required test of the
  same queue is still to be run or retried waits for it in the same run; one whose required test never got there is
  INCONCLUSIVE PRECONDITION without a launch. A dry run records no PRECONDITION.
- The approach is also measured from the spawn read. t0 is read after the player was moved to B, settled 1.5 s and
  was read in two console sessions, so a hostile actor may have closed most of the gap by then and hold its distance.
  A baseline that came 5 m closer between the spawn read and t0 (or was within 2.5 m of B at t0) is FAIL WANDER; a
  commanded test that did is INCONCLUSIVE PRECOMMAND (the walk after it is not the command's alone). An actor that
  stayed put until t0 is judged exactly as before.
- A PASS gets a note from the same actor's baseline: "the command moved it" when the baseline stayed away, "not
  credited to the command" when it came.
- Unknown plan.json keys stop the planning. An older testqueue.py drops keys it does not know (`control_npc`, a
  same-queue `requires`), which would make every N2a FAIL INCONCLUSIVE CONTROL and run tests meant to wait;
  `raider_map.py check-queue` compares a planned queue with its plan.json and fails on any lost key.

**N0 so far (interim, the chain is running it, 2026-10-12).** N0_base FAIL WANDER: the citizen came 5.4 m towards B
without a command (path 16.1 m). N0_ptr PASS (6.8 m). With N0's baseline WANDER, every N2a FAIL stays INCONCLUSIVE
CONTROL until a citizen baseline passes; N2a's PASSes still count.

Reading the results:

| result | meaning |
|---|---|
| N2a_base INCONCLUSIVE SPAWN, detail "GetIsID 02F04801 read 0" with GetSelf naming PickLastRef's ref | GetIsID does not confirm an actor whose template chain has no leveled list (the unresolved question). The other N2 tests are then INCONCLUSIVE PRECONDITION, no launch spent |
| INCONCLUSIVE SPAWN, detail "stands X m from the player at A" | the actor stepped away during `spawn_wait` (more likely for N2b's hostile actors); retried |
| INCONCLUSIVE SPAWN, place OCR showing an unknown form | the plugin did not load, or it is not at slot 02 (check Plugins.txt order) |
| N2b INCONCLUSIVE SPAWN "GetIsID read 0" while N2a_base was decided | GetIsID works for this plugin's records, so PickLastRef named a ref created after the actor (a hostile actor may fire during `spawn_wait`: **unresolved** risk, N0 never had a firing actor) |
| N2a_base PASS and a commanded PASS ("the command moved it") | the converted record spawns, takes a handle and walks on a known navmesh on command |
| N2a NONAV / STALLED with N0's control and baseline passed | **actor conversion failure** (template, AI, animation) |
| N2a_base FAIL WANDER | the calm probe comes on its own (inherited packages or residual hostility): its commanded PASSes are "not credited" |
| N2b: both FAIL WANDER | the hostility carried over: the conversion comes for the player like the vanilla Spacer |
| N2b: conversion PASS (stayed away), Spacer WANDER | its hostility or pursuit did not carry over (faction, AI data, weapon) |
| N2b: both PASS | the approach rule does not show hostility here (both may shoot from range): look at the `npc*.png` screenshots |
| N2b: conversion WANDER, Spacer PASS | the shotgun conversion comes, the rifle Spacer holds: hostile, not a failure |

Plan the queues from the checkout that runs the chain, once this branch is merged into it. That checkout needs
`control_npc`, the same-queue `requires` and the plugin-only install; `check-queue` fails if it lacks them.
`npc_nav_n0` must be planned first, and N2a before N2b (N2b_base's requires is resolved against N2a's queue).

```powershell
$py = "C:\Modding\venv-render\Scripts\python.exe"
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\npc_nav_n2a `
      --out C:\Modding\testqueue\npc_nav_n2a --install-exp C:\Modding\staging\actor_raider2 --plugins FO4ActorRaider.esm `
      --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh
& $py scripts\actors\raider_map.py check-queue --plan C:\Modding\staging\npc_nav_n2a\plan.json --queue C:\Modding\testqueue\npc_nav_n2a
& $py scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\npc_nav_n2b `
      --out C:\Modding\testqueue\npc_nav_n2b --install-exp C:\Modding\staging\actor_raider2 --plugins FO4ActorRaider.esm --fresh
& $py scripts\actors\raider_map.py check-queue --plan C:\Modding\staging\npc_nav_n2b\plan.json --queue C:\Modding\testqueue\npc_nav_n2b
```

Chain lines, after `npc_nav_n0`: `?npc_nav_n2a`, then `?npc_nav_n2b`. All four commands were checked by planning into a
scratch folder (with `--n2a-queue` pointing there): 4 + 2 tests on build 2470f876, `check-queue` clean, and a dry run
of N2a (the base would run; the other three would wait for it).

## 6. What was checked offline, and what was not

**Checked (verified).**
- The writer validated every Starfield link: FormID, EditorID and record type.
- `check` re-read the plugin with Mutagen: two NPC_, master Starfield.esm, every link and every inherited category
  resolves, the template targets are NPC_ records (not leveled lists), each record has the 16 subrecords every vanilla
  NPC_ has and form version 581: 0 problems. An independent Python raw scan agrees.
- 32 synthetic tests (`tests/test_actor_raider.py`) cover the mapping, the calm probe, the spec / writer contract
  (keys, template slots, copied values and the always-present list read from `Writer.cs`), the plans and their
  planning (including `check-queue`), the `control_npc` gate and the PASS note, plan keys, same-queue `requires` in a
  run, the judging from the spawn read, and the plugin-only install. Their temporary folders are removed.
- The full suite passes (430 tests). `scripts/guard.py`: ok.

**Not checked.** Anything in game: whether Starfield loads the records, spawns them, confirms them with GetIsID, shows
the face, or runs the inherited AI.

## 7. Next

- **2026-10-12: N2 against N0b.** N0 could not tell a commanded walk from wandering (its citizen came 5-9 m towards
  the old B whatever was typed; docs/actors/npc-navigation.md section 5). The re-plans `npc_nav_n2a_b` (N2a_base,
  N2a_ptr, N2a_combat) and `npc_nav_n2b_b` move N2 to N0b's pair A (-12, 12, 0) -> B (6, 12, 0) and rule (within 3 m of
  the player or 12 m closer), drop `cf` / `follow` (no control left for them) and gate against `npc_nav_n0b`; the
  staged READMEs have the commands. The queues above stay as they are.
- **N2c**, after N2a passes and the converted navmesh passes N1 (PR #71): the raider at its converted Concord position
  (-829.06, 1,008.31, 88.09) m, on the core64 overlay (PR #72, which reaches Concord).
- **A direct hostility read.** The approach rule only sees movement. A console read of the combat state or the faction
  relation (e.g. `GetCombatState`, `GetFactionRelation`) would show hostility directly; it needs the parser and a
  Starfield.exe command-table check first (unresolved).
- **More of the raider ladder:** EncRaider02.. mapped to EncSpacer02.. by tier; random faces through
  `LCharSpacerFaceAndGender` once the GetIsID question is settled; an own `FO4_RaiderFaction`; FO4 weapons and outfits
  after the weapon / skinning milestones; a Traits template with a death item if the loot matters.

## 8. Corrections to the first version (2026-10-11), from QA on PR #75

- **Refuted:** "Nothing the record needs is missing from Mutagen" and the raw-layout note "minus the inherited PRPS /
  RDSA / face blocks". The record lacked PRPS, STON, EDCT and PRON, which all 7,131 vanilla NPC_ carry, and the doc
  did not say so; PRPS was called inherited without evidence. Fixed in actor_raider2 (section 3).
- **Refuted:** N2a's design. Its FAILs were gated by N0's calm citizen while the raider is hostile, and the judge
  measured the approach only from t0. Replaced by the calm probe in N2a and the hostile pair in N2b (section 5).
- **Refuted:** N2b's StartCombat tests: sent to actors that are already hostile, without a baseline. Replaced by the
  two baselines.
- **Corrected label:** docs/ai/research-log.md called "a direct NPC_ template keeps GetIsID working" a supported
  hypothesis, and PR #75's body said "no generated base is involved", while this page said unresolved. It is
  **unresolved**; nothing cited supported it, and N0_ptr_lvl tests a chain with a leveled list.
- **Corrected:** "3 gain an empty STOP after RDSA": LvlCitizen_NoOld has no RDSA and gains it after KWDA. And the
  vanilla counts hide that no Traits-inheriting NPC_ has a STOP (section 4).
- **Corrected labels:** the death item and the combat style were listed as the record's own without saying that the
  inherited Traits / AI Data probably override them; "NPCs need no ammo (verified)" is a supported hypothesis (the flag
  value is verified, the inference is not); the form version 576 was not mentioned; the N2a_follow basis about a
  hostile raider cited nothing (that test now runs the calm probe).

## Commands

`$f4` and `$sf` are the two games' Data folders; output goes to the staging folder, never the game folder.

```powershell
dotnet run --project dotnet\ActorRaider -c Release -- fo4-find $f4\Fallout4.esm -17 19 8 Raider
dotnet run --project dotnet\ActorRaider -c Release -- export-fo4 $f4\Fallout4.esm 00046458 1 C:\Modding\staging\actor_raider2\work\fo4_raider.json
& $py scripts\actors\raider_map.py spec --fo4 C:\Modding\staging\actor_raider2\work\fo4_raider.json `
      --out C:\Modding\staging\actor_raider2\spec.json --table C:\Modding\staging\actor_raider2\mapping.md
dotnet run --project dotnet\ActorRaider -c Release -- write $sf\Starfield.esm C:\Modding\staging\actor_raider2\spec.json C:\Modding\staging\actor_raider2
dotnet run --project dotnet\ActorRaider -c Release -- check $sf\Starfield.esm C:\Modding\staging\actor_raider2\FO4ActorRaider.esm C:\Modding\staging\actor_raider2\check.json
& $py scripts\actors\raider_map.py plans --stage C:\Modding\staging\actor_raider2 --n2a C:\Modding\staging\npc_nav_n2a `
      --n2b C:\Modding\staging\npc_nav_n2b --n2a-queue C:\Modding\testqueue\npc_nav_n2a
# evidence
dotnet run --project dotnet\ActorRaider -c Release -- roundtrip $sf\Starfield.esm 00270255,0027BB78,0010DD71,0027BB7B,002B211C,0000CF96 <scratch> <out.json>
dotnet run --project dotnet\ActorRaider -c Release -- sf-tplstats $sf\Starfield.esm
dotnet run --project dotnet\ActorRaider -c Release -- rawcount $sf\Starfield.esm NPC_ STOP      # also PRPS, STON, EDCT, PRON
dotnet run --project dotnet\ActorRaider -c Release -- rawsubs C:\Modding\staging\actor_raider2\FO4ActorRaider.esm NPC_ 00F04800,00F04801
dotnet run --project dotnet\ActorRaider -c Release -- sf-dump $sf\Starfield.esm 00270255,0027BB78,0027BB8C,0026D96B
```

The per-record counts that `rawcount` does not print (STOP against the Traits bit, PRPS / STON / PRON / EDCT against the
template's, NPC_ carrying a WEAP and AMMO in CNTO) came from a read-only Python scan of the raw records (record headers,
zlib-decompressed data, subrecords; the same parsing as `Roundtrip.ReadGroup`), not kept in the repo.
