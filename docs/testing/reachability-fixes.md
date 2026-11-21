# Reachability Fixes Ledger (`W6`)

> **Public-Surface & Clean-Room Policy:** Zero verbatim game dialogue, journal text, executable bytes, third-party mod names, or local drive paths appear in this document. Entries record functional reachability defects from original shipped titles and the clean multi-route fixes enforced by our port and `scripts/testing/check_quest_fragility.py`.

## Purpose & Enforcement Rule

Some items, cosmetics, perks, and optional systems in the original Fallout titles were designed to be discoverable rewards but ended up trapped behind a single unmarked dialogue chain, a fragile variable order, or a one-shot cell lockout.

Every confirmed entry in this ledger obeys two port rules:
1. **Multi-Route Reachability (Tier 1 Automated Check):** In `src/fo4sf/testing/quest_test_catalog.json`, every reward tracked here MUST expose **`>= 2` independent unlock routes** (`routes` length `>= 2` and `single_sequence_only: false`), so `scripts/testing/check_quest_fragility.py` flags any regression back to a single fragile sequence.
2. **`W7` Open Mode Survival Compatibility:** At least one route MUST remain completable in Survival/Hardcore **Open Mode** even if key quest-giver or faction NPCs are killed.

---

## Confirmed Owner Entries

### `RF-FNV-001` — *Fallout: New Vegas*: Pimp-Boy 3 Billion (Special Pip-Boy Styles Unlock)
- **Logged By:** Owner (`20 Nov 2026`)
- **Game / Quest Scope:** *Fallout: New Vegas* (`VMS38` *How Little We Know* + Mick & Ralph's in Freeside)
- **Target Reward & System Link:** Unlocks the gilded **Pimp-Boy 3 Billion** special Pip-Boy style and serves as the canonical New Vegas test case for the shared Track 2 **Pip-Boy Styles** architecture (`docs/core/port-requirements.md`).

#### Why the Original Sequence Was Fragile (Functional Root Cause)
In vanilla *Fallout: New Vegas*, both designers and community bug lists note that obtaining the Pimp-Boy 3 Billion is far harder and easier to lock out permanently than intended because it sat behind a single unmarked chain with multiple state-ordering bugs:
1. **Unmarked Visit-Order Gate:** The player had to ask Mick (at Mick & Ralph's in Freeside) specifically about his slow business / lost Omerta arms contract **before** finishing *How Little We Know* (`VMS38`). Resolving Gomorrah first and talking to Mick afterward commonly failed to arm the unmarked reward hook.
2. **Narrow Faction & Sub-Stage Path:** Inside *How Little We Know*, the player had to side with Cachino **and** resolve Troike's contract with Big Sal (freeing Troike from his blackmail contract / sabotaging the Omerta arms cache while keeping Mick's gun-supply flag intact). Siding with Big Sal & Nero, killing the Gomorrah bosses outright, or killing Cachino permanently locked Mick out of ever offering the reward.
3. **Unmarked Variable & Dialogue Lockout Bugs:** Even on the intended Cachino + Troike path, vanilla `VMS38` suffered from unmarked state faults — including `bTroikeFreed` failing to latch if Troike was persuaded before the expected Big Sal dialogue step, Cachino's post-quest dialogue failing to update Mick's Omerta-deal condition, and corpse-cleanup / cell-reset clearing quest references before returning to Mick — leaving Mick permanently silent on the reward line.
4. **Vanilla Equip Rigging Defect:** On female player characters, equipping the vanilla Pimp-Boy 3 Billion also suffered a misaligned/tilted first-person wrist-mesh angle.

#### Proposed Multi-Route Unlock Design in Our Port (`3` Clean Routes)
Our port eliminates the unmarked lockout and gives players **three independent, clean ways** to earn and equip the Pimp-Boy 3 Billion across Story and `W7` Open Mode playthroughs:

1. **Route 1 — Fixed Standard Story Path (Mick & Ralph's Omerta Arms Restoration):**
   - Preserve the classic Freeside -> Gomorrah story reward while fixing its state machine: whenever *How Little We Know* concludes with legitimate Omerta trade restored under Cachino (via any valid Troike contract resolution — Speech, caps, or blackmail — and **regardless of whether the player spoke to Mick before or after `VMS38`**), set a single persistent global `FO4SF_FNV_MickOmertaRestored = 1`.
   - Gate Mick's Pimp-Boy gift dialogue strictly on `FO4SF_FNV_MickOmertaRestored == 1` (decoupled from transient corpse/cell cleanup or unmarked Troike sub-vars), so post-quest turn-in never locks out.
2. **Route 2 — Skill / Economy Commission OR Freeside King's Favor (Works Even If Omertas Are Wiped Out in Open Mode):**
   - Even if the player wipes out Gomorrah or skips *How Little We Know*, allow commissioning the gilded casing directly from Mick via either:
     - a high **`Barter >= 75`** or **`Repair >= 75`** skill check plus **`5,000` Caps**, **OR**
     - redeeming **The King's Freeside favor** earned from `VMS29` (*G.I. Blues*) at Mick & Ralph's.
   - Guarantees non-diplomatic, independent, and Open Mode players who neutralize the Omertas still have a fair in-world Freeside route.
3. **Route 3 — Hostile / Independent Vault Recovery + Workbench Fit (Works Even If Mick Dies in Open Mode):**
   - Place a lootable **Gilded Pip-Boy Casing** (plus fitting schematic note) inside Big Sal's / Gomorrah's locked boss safe (or Gomorrah vault).
   - A player on a hostile, stealth, or mass-elimination Open Mode run can recover the casing and either pay Mick to install it **or** fit it directly onto their Pip-Boy at any armor/tinker workbench (`Repair >= 50` or schematic unlocked), permanently unlocking the style even if Mick, Cachino, and all Omerta bosses are dead.

#### Track 2 Pip-Boy Style Interface Hook (`FO4SFPipboyMenu` / `FO4SF_PipboyWrist`)
- **Shared Globals (`FO4SFCoreValues.esm` — design-only, matching `docs/core/port-requirements.md` Sec 6):**
  - `FO4SF_PipboyStyle` (proposed `0x000898`: currently equipped style index; `0` = Standard, `2` = Pimp-Boy 3 Billion; toggled freely at Mick & Ralph's, a workbench, or the Pip-Boy settings drawer without losing inventory or quest state).
  - `FO4SF_PipboyStyleUnlockedMask` (proposed `0x000899`: bitmask of unlocked styles; bit `0` = Standard, bit `2` = Pimp-Boy 3 Billion, remaining bits reserved for future FO4/FO3/FNV styles).
- **Visual & Rigging Parity:** Bind `[Style <n>]` in `FO4SFPipboyMenu.ini` to a unified left-wrist mesh/material swap (`FO4SF_PipboyWrist` `0x00080D` + `FO4SFPipboyMenu` shell theme hook) using one normalized 1st-person transform across all body types, eliminating the vanilla female-rig tilt defect.
- **Verification Gate:** Offline verified in `src/fo4sf/testing/quest_test_catalog.json` (`VMS38` reward `pimp_boy_3_billion` lists all `3` routes and passes `check_quest_fragility.py --open-mode`); in-game verified in Tier 4 feel testing.

---

## Structured Expansion Slots (For Owner Play-Memory Additions)

The slots below are structured placeholders for additional single-sequence or permanently missable rewards across Fallout 4, Fallout 3, and Fallout: New Vegas. None of these candidate slots are implemented until confirmed or replaced by the owner from play memory.

### Reusable Entry Template
```markdown
### `RF-<GAME>-<NNN>` — *<Title>*: <Item / Reward / Unlock Name>
- **Status:** `PROPOSED — Awaiting Owner Confirmation` | `CONFIRMED`
- **Game / Quest Scope:** `<Title>` (`<QuestID>`)
- **Why Vanilla Is Fragile:** <Single unmarked sequence, one-shot cell lockout, or bug pattern>
- **Proposed Multi-Route Fix (`>= 2` Routes):**
  1. Route 1 (Fixed standard route): ...
  2. Route 2 (Alternate skill / faction / economy route): ...
  3. Route 3 (`W7` Open Mode / hostile recovery route): ...
- **Catalog & Test Link:** `<QuestID>` reward entry in `src/fo4sf/testing/quest_test_catalog.json`
```

### Pending Candidate Slots (Awaiting Owner Review & Additions)

| Slot ID | Game | Candidate Content / Unlock | Vanilla Single-Sequence / Lockout Risk | Proposed Multi-Route Fix Concept | Status |
|---|---|---|---|---|---|
| `RF-FO4-001` | `FO4` | *Institute / Prydwen / Railroad HQ* missable collectible magazines & bobbleheads inside faction HQs | Destroying a faction in Act III permanently deletes interior cells before collection | Allow recovery from post-destruction ruin caches or faction vendor/salvage crates | **PROPOSED — Awaiting Owner Input** |
| `RF-FO4-002` | `FO4` | *Bunker Hill / Covenant* settlement workbench unlocks | Narrow dialogue sequence (`Human Error` / `MQ206`) can permanently lock workshop ownership | Add post-quest settlement-claim fallback terminal / Minutemen charter route in Open Mode | **PROPOSED — Awaiting Owner Input** |
| `RF-FO4-003` | `FO4` | *Fallout 4* special Pip-Boy paint / shell styles | Tied to DLC/store hooks unavailable in clean-room port | Register unlockable Pip-Boy styles in `FO4SF_PipboyStyleUnlockedMask` via in-world schematics/workbenches | **PROPOSED — Awaiting Owner Input** |
| `RF-FO3-001` | `FO3` | *Vault 101* Medicine Bobblehead & *Raven Rock* Energy Weapons Bobblehead | One-shot interior cells that lock permanently if missed on first visit (`CG04`, late main spine) | Provide a return-access / salvage-locker recovery route (e.g. *Trouble on the Homefront* / Enclave salvage crate) | **PROPOSED — Awaiting Owner Input** |
| `RF-FO3-002` | `FO3` | *Megaton* Strength Bobblehead (Lucas Simms's house) post-`MS11` detonation | Permanently destroyed if Megaton is detonated before collection | Relocate salvageable bobblehead into Megaton crater rubble cache after `MS11` detonation | **PROPOSED — Awaiting Owner Input** |
| `RF-FNV-002` | `FNV` | *Brotherhood of Steel / NCR Truce* (`VMQ05`) | Silently locked out if Brotherhood leadership was changed earlier (`Still in the Dark`) | Document explicit pre-choice warning + alternate diplomatic/reputation speech check (`CF-1`) | **PROPOSED — Awaiting Owner Input** |
| `RF-FNV-003` | `FNV` | *Unique companion quest triggers* (history-point counters across unmarked locations) | Unmarked point-counter triggers can stall permanently if locations were cleared before recruitment | Allow idempotent retroactive credit for already-cleared locations/quests upon recruiting companion | **PROPOSED — Awaiting Owner Input** |
