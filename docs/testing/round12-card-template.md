Titles: Fallout 4 | Modes: Story & Warfare | Track: Round 12 Session Card Template

# Round 12 Test / Probe Card — `<probe-or-slice-title>`

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Scope:** `<probe-id-or-candidate>` | **Mode:** `<Story | Warfare | Both>` | **Baseline Target:** `candidate-2g-fix2` (`baseline != 2g-fix2` triggers warning at install time)
> - **Version Tag:** `<probe-version-tag>`
> - **Stage Placeholders:** `<stage-dir>`, `<starfield-dir>`, `<probes-root>`
> - **Disk Need:** `~<size> MB` under `<starfield-dir>/Data` (`>= 60.0 GiB` free required before staging/install; `Starfield.exe` closed)
> - **Truth & Stand-In Policy (`R8` / `R15`):** Label every unverified item **`OFFLINE ONLY — UNPROVEN IN GAME`** and every donor/scripted animation, sound, mesh, or UI substitute as a **stand-in**. Zero `FO4SF ` prefix in user-facing `FULL` names.

---

## Staged Artifacts & Baseline Verification

| Artifact (`Data/...`) | Source / Reuse Status | Expected SHA-256 | Notes |
|---|---|---|---|
| `<plugin>.esm` | Rebuilt / appended (`st_nlink == 1` copied) | `<sha256>` | Verified clean (`0` `FO4Core_Commonwealth` `WRLD`/`PNDT`/ext-`CELL` overrides; `0` non-persistent cross-plugin `ObjectReference` VMAD props) |
| `SFSE/Plugins/FO4SFPipboyMenu.dll` | Reused tested `7d5ba49c0c6ab2aa` (or Task 4 rebuilt) | `<sha256>` | Ship tested DLL unchanged whenever C++ source is unchanged |

---

## `P3` Console, Batch & `< 200 m`/Axis Hop Rules

1. Every batch filename and interactive ```` ```console ```` / `bat <name>` activation contains **zero `m`, `n`, or `v` letters** (case-insensitive) and **zero stripped mod `GLOB`/`QUST` EditorIDs**.
2. Every exterior `setpos` hop from a named anchor moves strictly **`< 200 m` per axis** (`< 180 m` recommended); interior cells use explicit `interior` cell checks (no cross-domain interior/exterior `setpos`).

---

## Verification Rows (Every Row Has a `VIDEO` Column)

| Row | Step / Focus | Batch / Console (`P3` Clean) | Expected Result / PASS Log | Stand-In / Truth | Result | VIDEO |
|---|---|---|---|---|---|---|
| `R12-1` | `<step-title>` | `bat p6a` | `<expected-log-or-observation>` | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `<yyyy-mm-dd>/<clip>.mp4` or `needed (<short focus>)` |

---

## Install, Status & Exact Undo Commands (Game Closed)

```bash
# Inspect staged package / verify BA2 hashes (never use bundle_install.py)
python <stager-script.py> verify --stage-dir <stage-dir>

# Atomic install (checks Starfield.exe==0, *.txt collisions, baseline!=2g-fix2 warning, writes receipt before swap)
python <stager-script.py> install --stage-dir <stage-dir> --starfield <starfield-dir>

# Read-only status check
python <stager-script.py> status --starfield <starfield-dir>

# One-command atomic rollback (restores Plugins.txt + pre-existing files by SHA-256)
python <stager-script.py> uninstall --starfield <starfield-dir>
```

### Interactive Console & Batches (`P3` Zero-`M`/`N`/`V`)

```console
bat p6a
```

```bat
; <starfield-dir>/p6a.txt (filename and console invoke have zero M/N/V)
```

### Required PASS Log Lines (`<log-file>`)

```log
<expected_pass_line>
```

---

## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)

| Addition | PR / Track | 23 Nov In-Game Status | Integration / Dependency in This Card | Guard / Note |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | Partial pass: FO4 Mr. Handy body + animations; 4-line Sanctuary talk `completed=true`, `fallback=0` (close camera & greeting replay noted) | `<how used/unaffected here>` | Review CLEAR; awaiting owner merge |
| **Creature animations** | `#855` (`claude/creature-anim`) | Partial: radroach idle & deathclaw tail/spines moved in game; walk/attack/death & bloatfly/mole rat/dog unverified | `<creature_slot contract or slot=empty fallback>` | Stacked on `#854` |
| **Human animations** | `#856` (`claude/human-anim`) | Partial: add-on race keyword NPC played FO4 surrender idle vs normal control; walk & 1stP gun unverified | `<flag default OFF unless #856 passed>` | Stacked on `#854` |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | Proved `Gun_*.af` moves `XM2311` slide nodes | `<donor receiver node names: TRIGGER, Magazine, Bolt, MiscA..MiscA14 + controller side file>` | Owner rule: guns NOT ready until parts move |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD**: hand-made bank (`v174` vs SF `v140`) & direct override silent (add-on banks load on demand) | `<keeps labelled Starfield SNDR stand-ins>` | Next probe tests per-item bank link |
