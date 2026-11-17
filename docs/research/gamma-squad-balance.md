# Research Note: S.T.A.L.K.E.R. Anomaly & GAMMA Companion / Squad Balance and Proposed FO4SF Warfare Model

**Clean-Room & No-Download Disclosure:** Zero files, archives, scripts, or configuration tables were downloaded from the internet for this note. All findings below are synthesized strictly in clean-room prose from published *S.T.A.L.K.E.R. Anomaly* and *GAMMA* gameplay documentation and design rules, followed by our `GLOB`-tunable balancing proposal implemented in `FO4SFCompanions.esm`.

---

## 1. How S.T.A.L.K.E.R. Anomaly & GAMMA Balance Companions and Squads

In *S.T.A.L.K.E.R. Anomaly* and the *GAMMA* survival/progression overhaul, squad recruitment is treated as a mid-to-late-game tactical responsibility rather than free permanent firepower. Four interlocking rules prevent players from assembling an invincible firing line at level 1:

### 1.1 Hard Squad Cap & Earned Leadership Scaling
- **Base Cap (`2` Companions):** Starting characters can field at most **2** generic squad followers at once.
- **Earned Maximum (`4` Companions):** The active cap expands to **4** slots only after earning top-tier progression recognition (*Zone Legend* / high rank achievement), turning a full 4-man fireteam into a milestone reward for established leaders.
- **Rank-Hierarchy Gate:** NPCs carry explicit experience ranks (*Rookie*, *Trainee*, *Experienced*, *Professional*, *Veteran*, *Expert*, *Master*, *Legend*). Generic stalkers whose rank exceeds the player's current rank refuse to take orders from a junior leader, preventing a low-level player from hiring endgame heavies to clear high-tier zones for them.
- **Story / Escort Separation:** Temporary quest escorts track separately from voluntary permanent recruits so escort missions do not soft-lock when the player already leads a buddy pair.

### 1.2 Dual Recruitment Paths (Faction Goodwill vs. Paid Contracts)
- **Faction Goodwill Recruits:** Recruiting a friendly faction stalker for free requires building positive **faction goodwill** through completed radiant/story tasks for that faction. Losing faction goodwill locks out free recruitment.
- **Paid Mercenary / Escort Contracts:** Mercenary or paid-escort squads charge an **upfront hiring fee** plus **recurring contract pay / reward splits**, turning squad firepower into an ongoing currency sink rather than a one-time unlock.

### 1.3 Loyalty, Goodwill Erosion & Friendly Fire
- **Friendly-Fire & Abandonment Penalties:** Shooting squadmates in crossfire or letting recruited faction members die repeatedly degrades personal attitude and faction goodwill. Below threshold, squadmates break contract, refuse orders, or turn hostile.
- **Faction Alignment Conflicts:** Bringing recruits from rival factions into hostile territory triggers immediate firefights with local patrols unless disguised or held outside the settlement perimeter.

### 1.4 How GAMMA Stops a 4-NPC Squad from Trivializing Fights
GAMMA's combat and scarcity loops turn a careless 4-man squad from an "I win" button into a tactical liability unless actively commanded:
1. **Mortal Generic Recruits & Bleedout Pressure:** Generic stalker followers are **mortal**, not invulnerable damage sponges. High ballistic lethality, grenades, and apex mutants rapidly down or kill exposed companions, forcing the player to spend scarce medical supplies reviving downed teammates or permanently lose veteran recruits and faction standing.
2. **Interior Chokepoints, Stealth & Environmental Hazards:** Four armed NPCs break stealth immediately if left on aggressive posture, block narrow bunker corridors and doorways, and walk into environmental hazards unless ordered to **Wait / Hold Position** outside tight interiors and switched to **Hold Fire / Passive** during stealth approaches.
3. **Resource, Medical & Carry-Weight Sinks:** Followers have finite carry-weight limits (preventing infinite dungeon vacuuming), require functional ammunition/medical supplies, and reduce net profit through contract shares and gear upkeep.
4. **Active Tactical Wheel Micro-Management:** Squad effectiveness depends on constant stance switching through a fast companion wheel:
   - **Movement:** *Follow Me* / *Wait Here (Hold Position)* / *Move to Point*
   - **Combat Posture:** *Aggressive (Engage at Will)* / *Defensive (Return Fire Only)* / *Passive (Ignore Combat / Hold Fire for Stealth)*
   - **Logistics:** *Open Inventory / Trade Gear & Ammo*, *Inspect Health & Status*, *Dismiss*

---

## 2. Owner Read-Approval Request Queue (No Downloads Performed)

No external pages or files were fetched during this task. If the owner later wants exact numeric sub-mod curve comparisons beyond the clean-room `GLOB` defaults below, the following read-only documentation items are queued for **per-item owner approval**:

| Request ID | Public Documentation Target (Read-Only, Zero Binary Download) | Specific Balancing Question | Status |
|---|---|---|---|
| `REQ-GSB-01` | Public *S.T.A.L.K.E.R. Anomaly* wiki / documentation reference on companion goodwill & rank-tier thresholds | Confirm exact vanilla Anomaly goodwill thresholds per rank tier (`Rookie`..`Legend`) for optional strict parity presets. | **Awaiting Owner Approval** |
| `REQ-GSB-02` | Public *GAMMA* gameplay guide / changelog notes on paid companion escort fees and contract duration | Compare daily vs. per-contract fee scaling against FO4SF's caps economy (`250` upfront + `15%` reward share). | **Awaiting Owner Approval** |
| `REQ-GSB-03` | Public *GAMMA* companion combat/healing sub-mod documentation notes (plain rules text only) | Compare bleedout recovery timers and AI cover-seeking posture modifiers against Starfield's `Confidence` / `Assistance` actor values. | **Awaiting Owner Approval** |

---

## 3. Proposed FO4SF Squad Cap & Cost Model (`GLOB`-Tunable Proposal)

> **Owner Balancing Note:** Every numeric threshold below is exposed as a non-constant `GLOB` or `AVIF` in `FO4SFCompanions.esm` (`0x801..0x80B`) so the owner can tune caps, costs, and loyalty decay live in game or at stage time without editing Papyrus or C#.

### 3.1 Squad Slot Cap (`N = 2` Base, `4` Earned Fireteam Max)

| Parameter | Record (`FO4SFCompanions.esm`) | Default | Rule |
|---|---|---:|---|
| Base Squad Cap | `GLOB FO4SF_SquadBaseCap` (`0x801`) | `2` | Default active slot limit for any character (`1` story companion + `1` recruit, or `2` Warfare recruits). |
| Earned Fireteam Cap | `GLOB FO4SF_SquadMaxCap` (`0x802`) | `4` | Unlocked when the player holds `FO4SF_Perk_SquadCommander` (`0x812`), Charisma `>= 8`, **or** any `#815` (`FO4SFProgression.esm`) leadership background/trait (`MinutemanVolunteer` `0x828`, `DesertRanger` `0x827`, `CaravanGuard` `0x822`, `BrotherhoodScribe` `0x824`). |
| Solo Override | *Lone Wanderer* Perk Check | `0` (opt-in) | If a player opts into a dedicated solo *Lone Wanderer* mode, active squad recruitment is voluntarily capped at `0` while solo bonuses apply. |

### 3.2 Three-Gate Recruitment Check (`TryRecruit`)
1. **Rank-Hierarchy Gate (`AVIF FO4SF_RecruitRankTier` `0x809`, `0..4`):**
   - Tiers: `0` Rookie (Lv 1+), `1` Regular (Lv 5+), `2` Veteran (Lv 12+), `3` Elite (Lv 20+), `4` Legend (Lv 30+ or `FO4SF_Perk_SquadCommander`).
   - Recruits whose `FO4SF_RecruitRankTier` exceeds the player's effective rank tier refuse recruitment until the player advances or holds `FO4SF_Perk_SquadCommander`.
2. **Goodwill or Mercenary Contract Gate (`GLOB FO4SF_MercHireCost` `0x803` = `250`):**
   - Allied faction recruits join for `0` Credits/Caps when faction standing (`FO4SFReputation.esm` / `FO4SFProgression.esm` goodwill) meets threshold.
   - Independent/mercenary Warfare recruits charge `FO4SF_MercHireCost` (`250` Credits/Caps) upfront on recruitment.
3. **Loyalty & Moral Alignment Gate (`AVIF FO4SF_SquadLoyalty` `0x808`, `0..100`, default `75`):**
   - Recruits start at `75` loyalty. Friendly-fire hits subtract `-15` loyalty; reviving a downed teammate grants `+10` loyalty. Dropping below `20` loyalty breaks contract and dismisses the member immediately.

### 3.3 Upkeep, Mortality & Anti-Trivialization Rules
- **Mortal Fireteam Recruits vs. Story Companions:** Generic Warfare fireteam recruits (`Rifleman Alpha`, `Medic Bravo`, `Heavy Charlie`, `Scout Delta`) are `Protected` / mortal during combat bleedout unless stabilized, whereas named story companions remain `Essential` outside Hardcore mode.
- **Bleedout Stabilization Sink:** When a squadmate enters bleedout (`IsBleedingOut()`), `TickSquadUpkeep()` checks squad/player medical stock (`Aid_MedPack`) to stabilize them or warns the player before contract loss.
- **Contract Reward Share (`GLOB FO4SF_MercRewardShare` `0x804` = `0.15`):** Each active hired mercenary claims a `15%` share of contract payouts (up to `60%` for a full 4-merc fireteam), balancing raw firepower against economic progression.
- **Companion Nerve (`AVIF FO4SF_CompanionNerveBonus` `0x80B`):** FNV-style leadership scaling (`+5%` squad damage/resistance bonus per player Charisma point above `5`, up to `+25%` at `CHA 10`).
- **Companion Affinity (`AVIF FO4SF_CompanionAffinity` `0x807`, `0..1000`):** Story companions track affinity milestones at `250` (*Warm*), `500` (*Trusted*), `750` (*Admired*), and `1000` (*Idolized* -> permanently grants `PERK FO4SF_CompPerk_UnitedWeStand` `0x810`).
