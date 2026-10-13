# Fallout 4 → Starfield: a measured conversion toolchain

**Bring Fallout 4 into Starfield's Creation Engine 2 through a measured, repeatable conversion toolchain.** The goal is to preserve Fallout 4 gameplay while using Starfield's native physics and modern engine capabilities. Experimental interiors already load in Starfield; the full game conversion is unfinished.

Converters read **your own copies of both games** and generate local outputs. No game files or conversion pack are distributed. Existing in-game screenshots depict Bethesda-owned visuals and are excluded from the project's code license.

[Latest progress](#latest-progress--2026-10-13) · [Run an installed build](#run-an-installed-build-windows) · [Cell commands](#visit-converted-cells) · [Live updates](https://github.com/fo4sf/fo4-to-starfield/issues/32) · [Contribute](CONTRIBUTING.md)

## Latest progress — 2026-10-13

**Commonwealth structures and terrain now have sampled in-game loading and landing evidence.** In Starfield `1.16.244.0`, the pinned nearby run recorded 29 matching heights out of 30 readable samples. Sanctuary, Red Rocket and Concord each supported two landings at their expected roof height. One northeast landing remains 1.8939 m above its ground expectation. [Today's results and remaining work](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6138582480) were recorded October 12 evening in Mountain time / October 13 UTC.

This covers nearby sampled landings within 510 m of the arrival. Continuous walking, connected interiors and full-map streaming remain open.

| Work | Evidence and current limit |
|---|---|
| **Interiors, materials and native collision** | Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public Library and Parsons load in experimental builds. Stairs and hinged doors have recorded in-game passes; the complete interior acceptance gate remains open. |
| **Queued in-game tests** | [Claude's runner, #59](https://github.com/fo4sf/fo4-to-starfield/pull/59), recorded 7/7 matching smoke heights and 29/30 matching nearby baseline heights across four fresh launches (runner `af27ce9`, interior `2470f876`). All four unscored final diagnostic jumps used the wrong coordinate frame and are excluded; phase 03 remains held pending a reviewed fix and fresh pins. The earlier large interior queue still has unfinished work. |
| **Commonwealth terrain and structures** | [Core64c, #76](https://github.com/fo4sf/fo4-to-starfield/pull/76), stages 648,358 references in 1,708 populated cells across a 6.4 km extent. Source heights, terrain and structure landings have nearby evidence; that placement count is not tested map coverage. [Pinned runtime handoff](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6136825108). |
| **Independent evidence checks** | [Codex's checker, #94](https://github.com/fo4sf/fo4-to-starfield/pull/94), is merged: 25 new regressions, 302 Windows tests (2 skips), independent QA and Linux CI pass. It verifies completed attempts, XYZ/reference heights and captures, and detects misplaced final diagnostics. [Read-only audit command](docs/testing/commonwealth-evidence.md). |
| **Movable objects and connected interiors** | [Native movable bodies, #41](https://github.com/fo4sf/fo4-to-starfield/pull/41), and [load-door links, #50](https://github.com/fo4sf/fo4-to-starfield/pull/50), are under review. Movement and teleport acceptance are still pending for the integration build. |
| **Recoverable experiment installs** | #62 closed unmerged; its recovery/packing work was superseded by [#83](https://github.com/fo4sf/fo4-to-starfield/pull/83), integrated into the still-open experimental cave branch [#78](https://github.com/fo4sf/fo4-to-starfield/pull/78). Copy/activation failures roll back and interrupted cleanup retains its record in that reviewed integration. |
| **NPC navigation and actors** | [Claude's research, #61](https://github.com/fo4sf/fo4-to-starfield/pull/61), maps navigation formats and proposes a minimal NPC test. Research and a plan, not a working actor port. |

Merged code and experimental branches are identified separately above. A fresh checkout of `main` does not install game assets or reproduce an experimental build automatically.
Follow [the shared update thread](https://github.com/fo4sf/fo4-to-starfield/issues/32) for exact revisions, results and corrections.

### Recent in-game route results

Earlier results reported by Claude on 2026-10-10 for one pinned test build (code `1d3d5bf`; details and limitations in [shared status #32](https://github.com/fo4sf/fo4-to-starfield/issues/32)). These are separate from the newer integration batch above:

| Test area | Result |
|---|---|
| Vault 111 | 12/12 routes passed, including stairs and a switch door from both sides |
| Parsons | 11 hinged doors passed from both sides with an `OPEN` prompt recorded |
| Vault 114 | 28 routes passed; three doors still failed on both sides and three passed on one side only |
| Hotel Rexford | 28 routes passed; one door failed on both sides and three passed on one side only |
| Prydwen | Partial run: 11 passes, 7 falls, and 14 unread results among 33 reported attempts (one attempt is unclassified in the status summary) |
| Vault 81 and Boston Public Library | Not yet run on that pinned route build |

These are reports for a particular build, not a guarantee about other builds or a finished conversion. Offline tests and screenshots are not substitutes for in-game acceptance.

### See the work

**New queued stair test in Starfield** — captured by Claude for the `2470f876` integration build.

![Queued stair test in Starfield](https://raw.githubusercontent.com/fo4sf/fo4-to-starfield/d28abe77151d4af7c5acc228a10fd31928d6c9cf/docs/media/2026-10-11-queue-stairs-pass.jpg)

**Hotel Rexford: native hinged door**

![Hotel Rexford door opened in Starfield](docs/media/rexford-door-native.jpg)

**Parsons: both-side door evidence**

![Parsons hinged door route, side A](docs/media/route-parsons-door-bothsides-a.jpg)

[Opposite-side capture](docs/media/route-parsons-door-bothsides-b.jpg) · [First textured chair](docs/media/fo4-chair-textured-in-starfield.png) · [Vault 111 stairs](docs/media/vault111-stairs-catwalk-in-starfield.png)

More captured work: [Vault 111](docs/spikes/WP10-vault111-first-light.md) · [additional interiors](docs/spikes/WP10-more-interiors.md) · [collision](docs/spikes/S6-collision.md) · [door routes and test evidence](https://github.com/fo4sf/fo4-to-starfield/issues/32).

## What remains

The interior slice still needs reliable stairs, clear openings, both-side door operation, pushable objects and repeatable deployment. Some route failures come from test positioning; others require geometry or physics fixes. Nearby terrain loading has sampled evidence; continuous travel, larger regional coverage, navigation and actor behavior still need pinned in-game tests. Quests, dialogue, combat systems and full-game parity remain unfinished. See [the issue tracker](https://github.com/fo4sf/fo4-to-starfield/issues) and [risk register](docs/RISKS.md).

## Run an installed build (Windows)

If your converted build is **already installed and enabled** in Starfield, this PowerShell command launches the Steam game:

```powershell
Start-Process "steam://rungameid/1716740"
```

Load a dedicated test save, then use the console commands below. Downloading this repository alone does not install converted cells.

For an existing converted staging folder, deploy it from the repository folder before launching. Replace the two placeholders with your local paths; see [setup](docs/SETUP.md) for prerequisites, including the Creation Kit's Archive2 tool:

```powershell
python -I scripts/deploy_starfield.py install --staging "<converted-staging>" --starfield "<Starfield-install>"
```

The installer refuses to overwrite an existing deployment. Its paired cleanup command is:

```powershell
python -I scripts/deploy_starfield.py uninstall --starfield "<Starfield-install>"
```

## Visit converted cells

Open Starfield's console with the tilde/backtick key and enter **one** command. Each destination must be included in your installed build; an unbuilt cell is unavailable.

| Destination | Starfield console command |
|---|---|
| Vault 111 | `coc FO4Port_Vault111Cryo` |
| Vault 81 | `coc FO4Port_Vault81` |
| Red Rocket cave | `coc FO4Port_RedRocket01` |
| Vault 114 | `coc FO4Port_Vault114` |
| Prydwen | `coc FO4Port_PrydwenHull01` |
| Hotel Rexford | `coc FO4Port_GoodneighborHotelRexford` |
| Boston Public Library | `coc FO4Port_BostonPublicLibrary02` |
| Parsons State | `coc FO4Port_ParsonsState01` |

These are prototype cells for testing, not a campaign start or a completed playthrough.

## Why conversion is difficult

| Format area | Fallout 4 | Starfield |
|---|---|---|
| Plugin form version | 131 | 581 |
| Shared record fields | Sampled overlap is mostly 25–60% | Different record model and fields |
| Terrain | 37,020 `LAND` records in the measured sample | `.btd` terrain and procedural planets |
| Meshes | NIF geometry | NIF metadata plus external `.mesh` geometry |
| Materials | `.bgsm` / `.bgem` | JSON `.mat`, compiled into `.cdb` |
| Collision | Havok 2014 packfile | Havok tagfile and `hknp` shapes |

These are measured research notes, not promises of complete format support. Methods and sources: [format gap](docs/FORMAT-GAP.md), [spikes](docs/spikes/), and [measurement scripts](scripts/).

## Try it

```powershell
git clone https://github.com/fo4sf/fo4-to-starfield.git
cd fo4-to-starfield
python -m pip install -r requirements-ci.txt
python -m unittest discover -s tests -v
python scripts/guard.py
```

`scripts/convert_batch.py` converts groups of statics and now prints the top failure reasons by count after a run, making common issues easier to spot.

To reproduce measurements, install the tools listed in [setup](docs/SETUP.md), use your own game installations, and provide local input paths to the recon scripts. Keep generated data and converted assets outside this repository. Read [contributing](CONTRIBUTING.md) before opening a pull request.

## Safety and project rules

- **No raw game assets or extracted files in Git or releases.** Do not submit `.esm`, `.ba2`, `.nif`, `.dds`, `.mesh`, `.hkx`, audio, executables, or converted outputs. The repository currently includes a limited set of screenshots captured in-game; these depict third-party visuals, are excluded from the MIT grant, and do not establish permission for reuse. The guard and CI check for raw assets and local paths.
- Converters read local files selected by the user; generated outputs stay local. The project does not distribute a conversion pack.
- Tests use synthetic fixtures. Offline passes do not prove that an asset works in-game.
- This is for offline, single-player modding research. It does not modify either game's executable.
- Do not commit credentials, personal machine paths, or private game data. Report suspected vulnerabilities using [GitHub's private reporting option](https://github.com/fo4sf/fo4-to-starfield/security/advisories/new) when available; see [SECURITY.md](SECURITY.md).

## Legal and license

This repository is unofficial and is not affiliated with or endorsed by Bethesda Softworks or ZeniMax Media. Fallout, Starfield, Creation Engine, and related names and materials belong to their respective owners. **The MIT license in this repository applies only to original project code and documentation; it does not grant rights to Bethesda software, game assets, trademarks, screenshots, or user-generated outputs.**

The project does not provide legal advice or establish that any particular extraction, conversion, or use is permitted. Check the current [Bethesda Terms of Service](https://bethesda.net/data/tos/en.html), the applicable [game EULA](https://bethesda.net/data/eula/en.html), and laws where you live; seek qualified legal advice if you need a determination for your circumstances. Avoid uploading or sharing game-derived outputs unless you have confirmed you have the necessary rights.

## Contributing and attribution

Read [CONTRIBUTING.md](CONTRIBUTING.md), choose an open issue, and use its acceptance criteria. Every change must pass the synthetic tests and asset guard. Identify whether a result is **in-game verified**, **offline tested**, or an **unverified hypothesis**.

The project is led by the repository owner. AI-assisted contributions are acknowledged by role: **Claude** (conversion pipeline and in-game testing), **Codex** (deployment, recovery, persistent identities, and output verification), and **Grok** (acceptance criteria and evidence gates). Agent labels and commit subjects identify work; these names do not represent separate human contributors or endorsements.
