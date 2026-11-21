# Karma and Faction Reputation (`FO4SFReputation.esm`)

## 1. Design Direction: Two Orthogonal Axes

`FO4SFReputation.esm` implements **Global Karma (`-1000..+1000`)** and **per-faction Fame x Infamy (`0..100` x `0..100`)** as strictly independent runtime axes:

- **Faction Reputation (`Fame` x `Infamy` on New Vegas's 4x4 = 16-state matrix)** drives `FACT` combat/ally disposition (`Ally`, `Friend`, `Neutral`, `Enemy`), faction vendor buy/sell price multipliers and trade-refusal gates, and `CTDA` standing globals (`0..15`).
- **Global Karma (`-1000..+1000` across 5 moral tiers)** drives `[Perk]`/`[Trait]` dialogue tags (`0x808..0x80C`), moral companion warning/desertion thresholds (`0x807`), and ending moral slide selection (`0x804`, `0..4`).
- **Strict Orthogonality Invariant:** Faction disposition (`ApplyFactionDisposition`) and vendor price scaling (`StateVendorBuyMult`) never read `FO4SF_RepKarma`. A `Very Evil` player (`Karma <= -750`, tier `-2`) who has earned `Idolized` standing (`Fame >= 75, Infamy < 15`, state `3`) with a faction retains `Ally` reaction (`GetFactionReaction == 2`) and the `0.75x` vendor buy discount.

---

## 2. Measured Multi-Title Source Evidence (Counts & Record Identifiers Only)

Direct binary header/record walks across source masters establish how each title represents moral alignment and group standing:

| Master File | `FACT` Count | `REPU` Count | Karma `GMST` Count | `PlayerFaction` FormID | Runtime Mapping in `FO4SFReputation.esm` |
| :--- | ---: | ---: | ---: | :--- | :--- |
| `Fallout3.esm` | `326` | `0` | `10` | `0x01B2A4` | Global Karma (`-1000..+1000`) + Capital Wasteland faction standing table |
| `FalloutNV.esm` | `682` | `13` | `10` | `0x01B2A4` | `1:1` 16-state `REPU` matrix across all `13` `REPU` records + Global Karma |
| `Fallout4.esm` | `699` | `0` | `2` (stubs) | `0x01C21C` | Restored Global Karma (theft/innocent murder/charity) + 8-faction 16-state standing |
| `SeventySix.esm` | `954` | `0` | `0` | `0x01C21C` | 7-tier `Hostile..Ally` curve projected onto the 16-state matrix + optional Karma |
| `Starfield.esm` | `812` | `0` | `0` | `0x01C21C` | Host engine: `FACT.SetAlly`/`SetEnemy`, `AVIF`, `GLOB`, `PERK` (`ModBuyPrices` + `PcTrait`) |

Classic isometric/tactical titles (`FO1`, `FO2`, `Tactics`) map town and regional standings (`ShadySands`, `Junktown`, `Hub`, `Boneyard`, `Arroyo`, `Klamath`, `VaultCity`, `NewReno`, `NCR_Classic`, `Brotherhood_Midwest`) onto the per-faction `Fame`/`Infamy` axis alongside Global Karma (`src/fo4sf/reputation/tables.py`).

All `13` measured `FalloutNV.esm` `REPU` EditorIDs and source FormIDs in `TITLE_REPUTATION_TABLES["FNV"]`:
`0x0F2406` `RepNVPrimm`, `0x0F43DD` `RepNVCaesarsLegion`, `0x0F43DE` `RepNVNCR`, `0x0FFAE8` `RepNVBoomer`, `0x104C22` `RepNVGoodsprings`, `0x116F16` `RepNVWhiteGloveSociety`, `0x118F61` `RepNVTheStrip`, `0x11989B` `RepNVGreatKhans`, `0x11E662` `RepNVBrotherhood`, `0x124AD1` `RepNVFollowers`, `0x129A79` `RepNVNovac`, `0x129A7A` `RepNVFreeside`, `0x1558E6` `RepNVPowderGanger`.

---

## 3. Exact 16-State New Vegas Fame x Infamy Matrix

Both `Fame` and `Infamy` clamp to `0..100` and bucket into 4 tiers using configurable cutoffs `(15.0, 40.0, 75.0)`:
- `0` (`None`): `< 15`
- `1` (`Low`): `15 .. 39.999`
- `2` (`Medium`): `40 .. 74.999`
- `3` (`High`): `>= 75`

State code `code = infamy_tier * 4 + fame_tier` (`0..15`):

| Code | Infamy Tier | Fame Tier | Title | `FACT` Disposition | Buy Mult | Sell Mult | Trade Allowed | Dialogue Gate Tags |
| ---: | :--- | :--- | :--- | :--- | ---: | ---: | :---: | :--- |
| `0` | None (`0`) | None (`0`) | `Neutral` | `Neutral` | `1.00` | `1.00` | Yes | `[Neutral]` |
| `1` | None (`0`) | Low (`1`) | `Accepted` | `Friend` | `0.95` | `1.05` | Yes | `[Accepted+]` |
| `2` | None (`0`) | Medium (`2`) | `Liked` | `Friend` | `0.85` | `1.15` | Yes | `[Accepted+]`, `[Liked+]` |
| `3` | None (`0`) | High (`3`) | `Idolized` | `Ally` | `0.75` | `1.25` | Yes | `[Accepted+]`, `[Liked+]`, `[Idolized]` |
| `4` | Low (`1`) | None (`0`) | `Shunned` | `Neutral` | `1.25` | `0.80` | No | `[Shunned]` |
| `5` | Low (`1`) | Low (`1`) | `Mixed` | `Neutral` | `1.00` | `1.00` | Yes | `[Mixed]` |
| `6` | Low (`1`) | Medium (`2`) | `Good-Natured Rascal` | `Friend` | `0.90` | `1.10` | Yes | `[Accepted+]`, `[Liked+]` |
| `7` | Low (`1`) | High (`3`) | `Smiling Troublemaker` | `Ally` | `0.85` | `1.15` | Yes | `[Accepted+]`, `[Liked+]` |
| `8` | Medium (`2`) | None (`0`) | `Hated` | `Enemy` | `1.50` | `0.50` | No | `[Hated]` |
| `9` | Medium (`2`) | Low (`1`) | `Sneering Punk` | `Neutral` | `1.25` | `0.80` | No | `[Shunned]` |
| `10` | Medium (`2`) | Medium (`2`) | `Unpredictable` | `Neutral` | `1.05` | `0.95` | Yes | `[Mixed]` |
| `11` | Medium (`2`) | High (`3`) | `Dark Hero` | `Friend` | `0.95` | `1.05` | Yes | `[Accepted+]`, `[Liked+]` |
| `12` | High (`3`) | None (`0`) | `Vilified` | `Enemy` | `1.50` | `0.00` | No | `[Hated]`, `[Vilified]` |
| `13` | High (`3`) | Low (`1`) | `Merciful Thug` | `Enemy` | `1.40` | `0.00` | No | `[Hated]` |
| `14` | High (`3`) | Medium (`2`) | `Soft-Hearted Devil` | `Neutral` | `1.15` | `0.85` | Yes | `[Mixed]` |
| `15` | High (`3`) | High (`3`) | `Wild Child` | `Neutral` | `1.00` | `1.00` | Yes | `[Mixed]` |

---

## 4. Global Karma Thresholds (`-1000..+1000`)

| Karma Range | `FO4SF_KarmaTier` | Title | Dialogue Tag Perk (`PcTrait`) | `FO4SF_EndingMoralSlide` | Moral Companion Reaction (`FO4SF_CompanionMoralReaction`) |
| :--- | ---: | :--- | :--- | ---: | :--- |
| `-1000 .. -750` | `-2` | `Very Evil` | `0x808` `FO4SF_KarmaTag_VeryEvil` | `0` | `-2` (`Good` companion deserts at `<= -500`) |
| `-749 .. -250` | `-1` | `Evil` | `0x809` `FO4SF_KarmaTag_Evil` | `1` | `-2` (`<= -500` deserts) / `-1` (`-499..-250` warns) |
| `-249 .. +249` | `0` | `Neutral` | `0x80A` `FO4SF_KarmaTag_Neutral` | `2` | `0` (`Steady`; `Neutral` companions ignore Karma) |
| `+250 .. +749` | `+1` | `Good` | `0x80B` `FO4SF_KarmaTag_Good` | `3` | `0` (`< +500`) / `+1` (`Evil` companion warns at `>= +500`) |
| `+750 .. +1000` | `+2` | `Very Good` | `0x80C` `FO4SF_KarmaTag_VeryGood` | `4` | `+1` (`Evil` companion warns at `>= +500`) |

When `FO4SFProgression.esm` is installed alongside `FO4SFReputation.esm`, `SyncKarmaOutputs` also mirrors clamped Karma into `FO4SFProgression.esm` `0x807` (`FO4SF_Karma`) and `0x80C` (`FO4SF_KarmaGlobal`) via `Game.GetFormFromFile`.

---

## 5. Deterministic FormID Map (`FO4SFReputation.esm`)

Sole master `Starfield.esm`, `0` overrides on vanilla records (`dotnet/ReputationCore/Program.cs`):

| Local FormID(s) | Signature | EditorID(s) | Purpose |
| :--- | :--- | :--- | :--- |
| `0x800` | `QUST` | `FO4SF_ReputationQuest` | `StartGameEnabled`, stages `10, 20, 30, 40, 50, 60`, script `FO4SF_ReputationQuest` (0 properties) |
| `0x801` | `AVIF` | `FO4SF_RepKarma` | Persisted Global Karma (`-1000..+1000`, default `0`) |
| `0x802..0x804` | `GLOB` | `FO4SF_KarmaValue`, `FO4SF_KarmaTier`, `FO4SF_EndingMoralSlide` | Non-constant `CTDA` dialogue and ending globals |
| `0x805..0x806` | `AVIF`, `PERK` | `FO4SF_VendorBuyMult`, `FO4SF_RepVendorPerk` | `ModBuyPrices` (`MultiplyAVMult`) scaled by active faction standing |
| `0x807` | `GLOB` | `FO4SF_CompanionMoralReaction` | Moral companion state (`-2` desert, `-1` good warn, `0` steady, `+1` evil warn) |
| `0x808..0x80C` | `PERK` | `FO4SF_KarmaTag_VeryEvil..VeryGood` | `5` `PcTrait \| PcPlayable` perks swapped live for Starfield `[Trait]`/`[Perk]` dialogue tags |
| `0x810..0x817` (`0x81F`) | `FACT` (`FLST`) | `FO4SF_RepFact_*` (`FO4SF_RepFactList`) | `Minutemen`, `Brotherhood`, `Railroad`, `Institute`, `Settlers`, `NCR`, `Legion`, `Outlaws` |
| `0x820..0x827` (`0x82F`) | `AVIF` (`FLST`) | `FO4SF_Fame_*` (`FO4SF_FameAvList`) | Per-faction `0..100` Fame ActorValues |
| `0x830..0x837` (`0x83F`) | `AVIF` (`FLST`) | `FO4SF_Infamy_*` (`FO4SF_InfamyAvList`) | Per-faction `0..100` Infamy ActorValues |
| `0x840..0x847` (`0x84F`) | `AVIF` (`FLST`) | `FO4SF_RepState_*` (`FO4SF_RepStateAvList`) | Per-faction `0..15` 16-state matrix code ActorValues |
| `0x850..0x877` (`0x85F..0x87F`) | `GLOB` (`FLST`) | `FO4SF_FameGlob_*`, `FO4SF_InfamyGlob_*`, `FO4SF_StateGlob_*` | Non-constant `CTDA` condition globals per faction |
| `0x880..0x883` | `MISC` | `FO4SF_CharityToken`, `FO4SF_TheftToken`, `FO4SF_FactionAidToken`, `FO4SF_FactionCrimeToken` | Console-free field walk tokens (`+300` Karma, `-350` Karma, `+80` Fame, `+80` Infamy) |
| `0x888`, `0x890` | `NPC_`, `CELL` | `FO4SF_RepVendorNpc`, `FO4SF_RepTestCell` | Self-contained interior test room (`coc FO4SF_RepTestCell`) with placed vendor NPC and walk tokens |

---

## 6. Pip-Boy `STAT` and `DATA` Integration (`#817`)

Both Pip-Boy UI routes in `#817` read the exact same `AVIF` records (`src/fo4sf/reputation/pipboy_bridge.py` and `scripts/reputation/make_reputation_core.py`):

1. **`Stage=5` Kit Pages (`FO4SFPipboyMenu.reputation.ini`):**
   - Injects `[Page STAT/KARMA]` (`GLOBAL KARMA|av:<XX>000801`, `VENDOR BUY MULT|av:<XX>000805`, `Footer=KARMA|av:<XX>000801`) and `[Page DATA/REPUTATION]` (`24` rows: `<FACTION> FAME`, `<FACTION> INFAMY`, `<FACTION> STATE` across slots `0..7`), validated against `scripts/ui/make_pipboy_kit.py` (`parse_kit` uppercase `KIT_FONT` and column-width rules).
2. **`Stage=2` Fallout 4 AS3 Shell (`FO4SFPipboyReputation.tsv` & `FO4SFPipboyReputation.json`):**
   - Feeds `Menu_mc.DataObj.PerksList` (`STAT` page: `Karma: <Title> (<+N/-N>)` + rank `1..5` + moral description) and `Menu_mc.DataObj.StatsList` (`DATA` page `Reputation` category: `Karma (<Title>)` + `<Faction>: <16-State Title>` with `<Fame>/<Infamy>`).
