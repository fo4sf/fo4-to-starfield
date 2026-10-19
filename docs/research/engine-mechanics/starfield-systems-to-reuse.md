# Starfield systems to reuse: where FO4 data rides on CE2's own machinery

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19, on the owner's follow-up
(17:25Z): "Also think about building ties for certain Starfield engine mechanics we might want to reuse, like factions
and faction relationships." Labels: **verified** / **supported hypothesis** / **unresolved**.

## In short

- **Reuse the system, never Starfield's content.** A tie means FO4 data is written into a Starfield record type or
  engine feature that already works (saved, shown in the UI, run by the engine), filled with **our own** records. We
  do not put FO4 actors into Starfield's factions, quests or keyword sets; that is how Starfield's crime, crew and ship
  hooks would leak in (the fence in [factions-crime-relationships.md](factions-crime-relationships.md)).
- **Three kinds of tie.**
  1. *Same system, same shape*: FO4's records map field for field (factions and relations, vendors, Story Manager,
     condition functions). Pure converter work.
  2. *A Starfield system replaces an FO4 script*: Starfield moved things FO4 did in Papyrus into records (affinity,
     legendaries, quest rewards). Writing FO4's numbers into those records is cheaper than porting FO4's scripts and is
     saved and cooled down by the engine.
  3. *Borrow one Starfield record on purpose*: a short, named list (player faction, currency, digipick, template
     packages), each a decision with a test.
- **Factions are the strongest case** (section below): relations, combat reactions, crime values and vendors are the
  same record with the same bits (verified, xEdit), and Starfield adds group movement, faction voices and a working
  arrest and prison flow that FO4 had switched off. The relations carry now; the extras are optional later features.

## Factions and faction relationships: the ties

Record: FACT, identical in both games for everything FO4 uses (verified, xEdit `wbDefinitionsSF1.pas` FACT at line
11863 against FO4's FACT; details in [factions-crime-relationships.md](factions-crime-relationships.md)).

| FO4 piece | Starfield system it rides on | tie | label |
|---|---|---|---|
| 699 factions with XNAM relations (Neutral / Enemy / Ally / Friend) | Starfield's combat reaction engine, same XNAM | data copy into our own FACTs | verified layout |
| hostility to the player (raiders, creatures) | an explicit Enemy relation to the player's faction, as Starfield's Spacers do | converter rule: FO4 Very Aggressive with no player relation becomes Enemy | verified (raider conversion) |
| condition checks on factions: GetInFaction (71), GetFactionRank (73), SameFaction (42), GetFactionRelation (449), GetFactionCombatReaction (410), GetPCEnemyofFaction (197), GetCrimeGold (459), GetRelationshipRank (403) and the rest | the same functions at the same indices | carry by name | verified (both condition tables) |
| major faction standing (Brotherhood, Institute, Railroad, Minutemen): quest stages, globals and "set enemy" calls | Starfield's own faction storylines also run on quests; no reputation meter in either game | translate the quests; standing stays quest data | supported hypothesis (no reputation field in either FACT) |
| Attack on Sight towns (Diamond City, Goodneighbor) | Track Crime + Attack On Sight in CRVA, same fields | data copy | verified fields |
| vendors on factions (VEND, VENC, VENV, hours) | the same vendor block; Starfield's barter menu | data copy (radius u16 to float) | verified |
| companion crime factions (Preston's `CompanionCrimeFaction_Preston`) | affinity events (AFFE) for approval; our own crime faction for "turn hostile on assault" | rebuild light | supported hypothesis |
| RELA relationships (64) | RELA still defined in CE2, unused by Starfield.esm; GetRelationshipRank kept | data copy, one in-game check | supported hypothesis |

**Starfield extras FO4 never had (optional, later, owner's call):**

| Starfield feature | what it could give the Commonwealth | how | label |
|---|---|---|---|
| **Herd** block on FACT (search radius, min and max members, idle chatter times) and conditions IsHerdLeader (833), HasHerdLeader (834) | packs that move and chatter together: mirelurks, mole rats, raider groups | fill the block on our creature and gang factions | field names verified (xEdit); behaviour supported hypothesis; conditions verified Starfield-only |
| **Create Group** with a formation radius, NPC_ HEFA formation faction, IsInSameGroup (945), GetGroupMembersInRadiusCount (899) | Brotherhood squads, Minutemen patrols and Gunner teams that keep formation | our factions with a formation radius; patrol NPCs point HEFA at them | fields verified; behaviour supported hypothesis |
| **VTCK faction voice** (a voice type or list per faction) | generic barks for faction members without setting every NPC | point at FO4's own voice types | field verified; use unresolved |
| **DNAM faction type keyword** | grouping our factions for scripts and conditions | our own keywords only | field verified; what Starfield uses it for unresolved |
| **Arrest, bounty and prison** (CRVA Arrest, PRIS prison door marker, GetArrestedState, GetPlayerBountyCrimeFaction (905)) | real crime in Diamond City: guards arrest, a cell in the security office, bounty paid at the gate | our town faction with Arrest on and one PRIS entry whose ship and contraband markers are empty | fields verified; whether empty ship markers are accepted is unresolved; **not FO4 behaviour** (FO4's crime was switched off), so a feature, not a port |

Default for the port: relations, reactions, Attack on Sight and vendors now; herds and formations once creatures and
patrols are in (they cost data only); arrest and prison only if the owner wants it, behind an option.

## Other Starfield systems worth tying to

| Starfield system | FO4 thing that rides on it | kind | verdict | page |
|---|---|---|---|---|
| **AFFE affinity events** (reactions per companion, cooldown, distance, chaining) | FO4 companion likes and dislikes, `CA_Affinity` | 2 | **reuse** (recommended) with FO4's numbers and tiers | [companions.md](companions.md) |
| **INFO speech challenge field**; SPCH points minigame | FO4 Charisma checks | 1 (field); SPCH optional | field carries; SPCH for later set pieces only | [dialogue.md](dialogue.md) |
| **Quest stage rewards** (QUST stage data) and stage timers | FO4 reward scripts (caps, items, XP) | 2 | reuse where a stage only hands out items | [quests.md](quests.md) |
| **Story Manager** (Script Event, Change Location, Location Loaded, Player Add Item ...) | FO4 radiant quests and triggers; the dropped events (Kill, Arrest, Craft) are sent as Script Events | 1 | reuse | [quests.md](quests.md) |
| **Missions menu** (quest log, objectives, markers) | the Pip-Boy quest page | 1 | reuse first; a Pip-Boy UI is a later job | [quests.md](quests.md), [ui-pipboy-hud-menus.md](ui-pipboy-hud-menus.md) |
| **LGDI legendary records** (rank slots of object mods) | FO4's scripted `LegendaryItemQuest` | 2 | reuse, filled with FO4's legendary mods | [items-crafting-modding.md](items-crafting-modding.md) |
| **Object mods (OMOD) and attach points** | FO4 weapon and armor mods | 1 | translate | [items-crafting-modding.md](items-crafting-modding.md) |
| **Outpost build mode** (placement, snapping) | FO4 workshop placement | 2 (placement only) | reuse; FO4's menu tree becomes our own category keywords; settlement rules are ours | [workshop-and-settlements.md](workshop-and-settlements.md) |
| **Barter menu with currency 0000000F** | caps | 3 | decision A in the currency table (rename to Caps) | [economy-vendors-barter.md](economy-vendors-barter.md) |
| **Digipick lock minigame** | lockpicking | 3 | reuse the minigame; bobby pins as Digipick or our own item (decision) | [terminals-holotapes-locks.md](terminals-holotapes-locks.md) |
| **Character creator** | FO4's mirror scene | 1 | open Starfield's creator from our Vault 111 quest | [saves-and-new-game.md](saves-and-new-game.md) |
| **Package templates** (Sandbox, Travel, Patrol) | FO4 packages | 3 | already used by the mission (Preston on Sandbox 00002CB1) | [ai-packages-and-schedules.md](ai-packages-and-schedules.md) |
| **Animation graphs** | all FO4 actors | 1 | reuse (settled: Starfield animations first) | [animations.md](animations.md) |
| **Atmospheres, weather visuals, day length** | the one Earth-like planet, FO4 weathers | 2 | reuse vanilla sky sets, our own climate | [weather-time-climate.md](weather-time-climate.md) |
| **Oxygen** | Action Points | 3 | decision: reuse O2 as AP or add our own | [vats.md](vats.md) |
| **Afflictions and environmental damage** | radiation sickness, survival diseases | 2 | optional; fenced by default | [health-damage-effects.md](health-damage-effects.md) |
| **Encounter level fields on LCTN** | FO4 encounter zones | 1 | translate into our own location chain | [leveled-lists-and-encounter-zones.md](leveled-lists-and-encounter-zones.md) |

**Kept out (the fence):** crew assignment, ships, star map, outpost habs and research, Starfield's skills, traits and
backgrounds, contraband scans, Starfield's crime factions and its own radiant boards. Each would pull Starfield's
progression into our world.

## How a tie stays safe

1. Our plugins create their own FACT, AFFE, LGDI, KYWD and QUST records; a converter never writes a Starfield FormID
   into our data unless it is on the borrowed list below.
2. **The borrowed list** (each needs one test, and the list lives here): the player's faction (relations to the player
   must point at it), currency 0000000F (if decision A), the digipick (if chosen), Starfield package templates, and
   Starfield's animation graphs and race skeletons. Adding to the list is a decision recorded in docs/ai/decisions.md.
3. A borrowed record is overridden only where the change is needed (a name, a model), never deleted, so Starfield's
   own game still loads.
4. Optional Starfield extras (herds, formations, arrest) are off in the first builds and switched on per faction,
   so a regression is one record away from undone.

## Open questions and cheap checks

- Starfield's `Faction`, `AffinityEvent`, `Keyword` and `GlobalVariable` scripts: which natives they declare (SetEnemy,
  SetAlly, crime gold calls). Read-only PC probe (the same tool as job 15, with these scripts added).
- Do empty ship landing and contraband markers in PRIS keep an arrest working? One test faction, later, offline first.
- What the herd and group blocks do in game: one vanilla creature faction with a Herd block, compared with its
  actors' behaviour (one scan of Starfield.esm, read-only).
- Which Starfield faction is the player's, by FormID, and that FO4 relations re-pointed at it behave as in FO4 (part
  of the N3 faction conversion).

## Sources

- xEdit dev-4.1.6 `wbDefinitionsSF1.pas` (FACT at line 11863, AFFE, LGDI, QUST, INFO) and `wbDefinitionsFO4.pas`;
  condition tables extracted from both.
- The other pages of this reference, linked in the tables above.
