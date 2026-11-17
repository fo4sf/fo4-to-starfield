# PC Verification Card: Karma & 16-State Faction Reputation (`FO4SFReputation.esm`)

## Scope & Safety Rules

- **Plugin under test:** `FO4SFReputation.esm` + `Data/Scripts/FO4SF_ReputationQuest.pex` (+ Pip-Boy `STAT`/`DATA` manifests).
- **Zero vanilla overrides:** `FO4SFReputation.esm` has sole master `Starfield.esm` and `0` overridden records.
- **Throwaway save rule:** Save **only** to a brand-new throwaway save named **`FO4SF_Throwaway_Reputation_DeleteMe`**, and **delete `FO4SF_Throwaway_Reputation_DeleteMe`** immediately after the `log` check passes so zero test state lingers.

---

## Part 1 — Offline Stage & Verify (Game Closed)

Run from the repository root in PowerShell using explicit local tool paths and a fresh staging folder outside Git:

```powershell
python -I -B scripts/reputation/make_reputation_core.py stage `
    --out <private-stage-dir>\stage `
    --starfield <Starfield-dir>\Data\Starfield.esm `
    --compiler "<Starfield-dir>\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
    --content-resources "<Starfield-dir>\Tools\ContentResources.zip" `
    --load-index 0x0A

python -I -B scripts/reputation/make_reputation_core.py verify `
    --stage <private-stage-dir>\stage `
    --starfield <Starfield-dir>\Data\Starfield.esm `
    --run-dotnet-check
```

**Expected offline output:**
- `staged FO4SFReputation.esm (7 files) -> ...`
- `verify: ok` (exit code `0`).

If testing with `FO4SFPipboyMenu` (`#817`) active, generate the INI matching `FO4SFReputation.esm`'s load-order slot `<XX>`:

```powershell
python -I -B scripts/reputation/make_reputation_core.py pipboy-ini `
    --out <private-stage-dir>\FO4SFPipboyMenu.ini `
    --load-index 0x<XX> `
    --tsv-out <private-stage-dir>\FO4SFPipboyReputation.tsv `
    --json-out <private-stage-dir>\FO4SFPipboyReputation.json
```

---

## Part 2 — In-Game Orthogonality, Hooks, Pip-Boy, and Save/Reload Walk

Ensure `[Papyrus] bEnableLogging=1` and `bEnableTrace=1` are enabled in `StarfieldCustom.ini`, enable `*FO4SFReputation.esm` in `Plugins.txt`, launch Starfield via SFSE, and enter the isolated test cell:

1. **Enter test cell:**
   - Open console and run `coc FO4SF_RepTestCell` (or pick up the placed walk tokens on the floor for a 100% console-free walk: `3x FO4SF_TheftToken` `-350 Karma` each -> `-1000 Very Evil`, plus `1x FO4SF_FactionAidToken` `+80 Fame` -> `Idolized` with `Minutemen`).
2. **Prove Evil + Idolized Orthogonality (`Karma <= -750` + `Ally` + `0.75x` Vendor Price):**
   - Pick up `3x FO4SF_TheftToken` and `1x FO4SF_FactionAidToken` in `FO4SF_RepTestCell` **OR** run `setstage <XX>000800 10` (`<XX>` = load-order hex prefix of `FO4SFReputation.esm`).
   - Verify `FO4SF_RepVendorNpc` (`Minutemen`) remains non-hostile (`Ally`, reaction `2`), `FO4SF_RepKarma <= -750` (`Very Evil`, tier `-2`), and `FO4SF_VendorBuyMult == 0.75`.
3. **Exercise Quest, Combat-Kill, and Theft Hooks:**
   - Run `setstage <XX>000800 20` (`Brotherhood` quest hook -> `Liked`, state `2`).
   - Run `setstage <XX>000800 30` (`Legion` non-innocent combat kill -> `Hated`, state `8` `Enemy`; `NCR` rival gains `+10` Fame; **Karma does not change**).
   - Run `setstage <XX>000800 40` (`Settlers` witnessed theft -> Karma drops and `Settlers` moves to `Shunned`, state `4`).
   - Run `setstage <XX>000800 60` to record the pre-save `status_dump` snapshot.
4. **Check Pip-Boy `STAT` & `DATA` Pages:**
   - Open the Pip-Boy (`#817` stack):
     - On `STAT` (`STAT/KARMA` or `PerksList`), verify Global Karma and `VENDOR BUY MULT` match the logged values.
     - On `DATA` (`DATA/REPUTATION` or `StatsList`), verify `MINUTEMEN` (`3` = `Idolized`), `BROTHERHOOD` (`2` = `Liked`), `SETTLERS` (`4` = `Shunned`), `NCR` (`0`/`1`), and `LEGION` (`8` = `Hated`).
5. **Save, Quit Completely to Desktop, and Reload:**
   - Save to a new throwaway save named **`FO4SF_Throwaway_Reputation_DeleteMe`** (`save FO4SF_Throwaway_Reputation_DeleteMe`).
   - Quit Starfield completely to desktop (`qqq`) so Starfield rotates `FO4SFReputation.0.log` -> `FO4SFReputation.1.log`.
   - Relaunch Starfield, load **`FO4SF_Throwaway_Reputation_DeleteMe`**, wait `5` seconds for `Actor.OnPlayerLoadGame` to write `reload_audit`, and quit to desktop.

---

## Part 3 — Multi-Session Log Verification & Cleanup

1. **Run the stitched `.1.log` + `.0.log` checker:**

```powershell
python -I -B scripts/reputation/make_reputation_core.py log --require-hooks
```

**Acceptance criteria (exit code `0`):**
- `verdict: PASS`
- `orthogonality_ok: True` (`Karma <= -750` `Very Evil` simultaneously with `state=3` `Idolized`, `reaction=2` `Ally`, `buy_mult=0.75`)
- `hooks_seen: kill_hook, quest_hook, theft_hook` (and `kill_hook` with `innocent=False` left Karma unchanged)
- `reload_ok: True` (`reload_audit` logged `ok=true` and post-reload `karma` + 8-slot `states` match the pre-quit snapshot in `.1.log` `1:1`).

2. **Delete the throwaway save:**
   - Delete `FO4SF_Throwaway_Reputation_DeleteMe` from the Starfield `Saves` folder and restore `Plugins.txt` / staged test files when finished.
