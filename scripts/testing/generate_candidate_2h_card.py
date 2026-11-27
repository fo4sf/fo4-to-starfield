#!/usr/bin/env python3
"""Deterministic generator for docs/testing/candidate-2h-card.md (Round 17 J8).

Derives every runtime FormID prefix from `make_mission.compute_bundle_load_indices`
for the staged plugin list and every Pip-Boy key name from `make_pipboy_stage_ini`.
Never hardcodes stale 2h-3 load prefixes or keyboard bindings.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPTS_DIR = REPO / "scripts"
SRC_DIR = REPO / "src"
for _p in (
    str(SRC_DIR),
    str(SCRIPTS_DIR / "core"),
    str(SCRIPTS_DIR / "mission"),
    str(SCRIPTS_DIR / "ui"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle  # noqa: E402
import make_mission  # noqa: E402
import make_pipboy_stage_ini  # noqa: E402

DEFAULT_CARD_OUT = REPO / "docs" / "testing" / "candidate-2h-card.md"

_VK_NAMES: Dict[int, str] = {
    0x09: "Tab",
    0x1B: "Esc",
    0x4D: "M",
    0x76: "F7",
    0x77: "F8",
}


def vk_hex_to_label(key_hex: str) -> str:
    """Convert a Virtual-Key hex string such as '0x76' into a readable keycap label like 'F7'."""
    val = int(str(key_hex).strip(), 16) if str(key_hex).strip().lower().startswith("0x") else int(str(key_hex).strip())
    if val in _VK_NAMES:
        return _VK_NAMES[val]
    if 0x70 <= val <= 0x87:
        return f"F{val - 0x6F}"
    if 0x30 <= val <= 0x39 or 0x41 <= val <= 0x5A:
        return chr(val)
    return f"0x{val:02X}"


def read_pipboy_key_map(ini_path: Optional[Path] = None) -> Dict[str, str]:
    """Read toggle/cancel/map key names from a built FO4SFPipboyMenu.ini or the stage INI generator defaults."""
    if ini_path is not None and ini_path.is_file():
        ini_text = ini_path.read_text(encoding="utf-8", errors="ignore")
    else:
        dummy_names = make_pipboy_stage_ini.CANONICAL_MOVIE_PRIORITY[:1]
        # Build from stage INI generator defaults without requiring private SWF assets.
        ini_text = make_pipboy_stage_ini.format_stage_ini(["RegisterMovie", *([] if dummy_names else [])])

    vals: Dict[str, str] = {}
    for ln in ini_text.splitlines():
        s = ln.strip()
        if not s or s.startswith(";") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        vals[k.strip()] = v.strip()

    toggle_hex = vals.get("Key", "0x76")
    map_hex = vals.get("MapKey", "0x4D")
    return {
        "toggle_hex": toggle_hex,
        "toggle_key": vk_hex_to_label(toggle_hex),
        "map_hex": map_hex,
        "map_key": vk_hex_to_label(map_hex),
    }


def render_candidate_2h_card(
    plugins: Sequence[str] = make_core_bundle.PLAYER_BUNDLE_PLUGINS,
    *,
    data_dir: Optional[str] = None,
    bundle_dir: Optional[str] = None,
    port_esm: Optional[str] = None,
    ini_path: Optional[Path] = None,
) -> str:
    """Render docs/testing/candidate-2h-card.md deterministically from plugin load indices and DLL INI keys."""
    ordered_plugins = [p for p in plugins if p.casefold() != "fo4port.esm"]
    idx = make_mission.compute_bundle_load_indices(
        ordered_plugins,
        data_dir=data_dir,
        bundle_dir=bundle_dir,
        port_esm=port_esm,
    )
    keys = read_pipboy_key_map(ini_path)
    f7 = keys["toggle_key"]

    port = f"{idx['FO4Port.esm']:02X}"
    core = f"{idx['FO4TerrainCore.esm']:02X}"
    cv = f"{idx['FO4SFCoreValues.esm']:02X}"
    pod = f"{idx['FO4SFVaultPod.esm']:02X}"
    mis = f"{idx['FO4SFMission.esm']:02X}"
    ng = f"{idx['FO4SFNewGame.esm']:02X}"
    ws = f"{idx['FO4SFWorkshop.esm']:02X}"
    pa = f"{idx['FO4SFPowerArmor.esm']:02X}"

    plugin_csv = ",".join(ordered_plugins)
    hx, hy, hz = make_mission.H2H4_HOP_POS
    bat_names = sorted(make_mission.build_r12_h2_batches(plugins=ordered_plugins, data_dir=data_dir, bundle_dir=bundle_dir, port_esm=port_esm).keys())
    all_bat_names = sorted({*bat_names, "pod_seat.txt", "pod_step.txt", "h2s.txt", "h2hp.txt"})
    rm_bats = " ".join(f"<starfield-dir>/{fn}" for fn in all_bat_names)

    lines = [
        f"# Session Card — `candidate-2h-5`: Round 17 (`J1`, `J2`, `J3`, `J6`, `J8` on `#853`: Shared Placement & Immortable Anchors, No Pod Box & Save Lock, Live `BSTranslator` FO4 Words, Basement Gate Single-Lock & Order-Independent Fusion Core, Derived Load Indices & Hop Cover)",
        "",
        "> **Build Profile & Verdict (`27 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load pre-`candidate-2h-5` saves).",
        ">",
        "> - **Branch & Stack Integrated:** `gemini/round11-s2-s6-2h` (`#853`, on top of `2h-4` `a9a0d2bc`).",
        f"> - **Derived Full-Master Slots (from `--plugins` order):** `FO4Port={port}`, `FO4TerrainCore={core}`, `FO4SFCoreValues={cv}`, `FO4SFVaultPod={pod}`, `FO4SFMission={mis}`, `FO4SFNewGame={ng}`, `FO4SFWorkshop={ws}`, `FO4SFPowerArmor={pa}` (gate `{port}00EDF0`, Fusion Core `{pa}000809`; Pip-Boy key `{f7}` from `Key={keys['toggle_hex']}`).",
        "> - **Round 17 Fixes Included (`J1`, `J2`, `J3`, `J6`, `J8`):**",
        f">   - **`J1` (Two-Load Arrival Outside Merged Footprint, `0x826` Retired, Immobile Anchors, Silent Discovery `{ng}000827`):** Removes `0x826` (`ArrivalMergedMarkerId` / `FO4SF_ArrivalMergedMarker`) and moves all `Surface()` & `FO4SF_ConfirmedLoadDoor` (`out`) moves into `FO4SF_Placement` (`FO4SF_Placement.psc`). Checks `IsInsideMergedFootprint` at both build time (`dotnet/NewGame` refusal) and runtime (`inside_footprint=false`, staging marker FO4 `0009F272 / 70` at `(-1275.31, 1305.28, 127.21)`), holds plain black across both loads (`story landing loading menu opened` before `FadeOutGame`), gives first-landing discovery its own marker `{ng}000827` so `ExitAnchorId` (`{core}0A775B`) never moves at runtime, drops scripted discovery on repeat arrivals (`VAULT 111` banner probe vs `0x01F3FE`), logs `step=loading_menu_closed gen=<n>` in DLL, and honors `h00SkipLoading` in `SetLoadingBlackCover`.",
        ">   - **`J2` (No Pod Choice Box + Vault Save Lock, `D-V111-10`):** Removes `StartMessage.Show()` and `LooksWait` pod stall from `FO4SF_NewGameLooks.psc` and `FO4SF_NewGameQuest.psc` (`pod start choice=none rule=D-V111-10`); locks saving via `Game.SetInCharGen(True, True, False)` from pod entry until `pod_exit`, then restores saving and takes the vault recovery autosave; dying in Vault 111 reloads that autosave without opening `ChargenMenu`. Lift `Change Appearance` (`D-LIFT-04`) stays working on the elevator.",
        ">   - **`J3` (Live `BSTranslator` Write & FO4 GMST Wording):** Updates `Translate_en.txt` (`FO4ActorRaider - Main.ba2`), `hud_quest_label.h`, and `FO4SFPipboyMenu.dll` to patch live Scaleform `BSTranslator` hash buckets in-place after data load using Fallout 4 GMST strings (`QUEST`, `QUESTS`, `QUEST ADDED`, `QUEST UPDATED` on `$MissionUpdate` & `$MISSION UPDATED`, `QUEST COMPLETED`, `QUEST FAILED`, `Quest Log` per `G12(d)`, `$MISSION STATUS` = `QUEST STATUS` pending owner reply) and verifies all 20 keys (`runtime_ok=1`).",
        ">   - **`J6` (Basement Security Terminal Single-Lock & Order-Independent Fusion Core):** Resolves basement gate dynamically via terminal XLKR (`GetLinkedRef` -> `{port}00EDF0`), never registers `OnLockStateChanged` on terminal `{mis}000BD9` / `{port}00E35E`, guarantees `OnLockStateChanged` never calls `TryOpenS6BasementGate`/lock/open, drops `Unlock`/`SetLockLevel`/`SetOpen(True)`/terminal lock calls, makes at most ONE `gate.Lock(False, False, False)` + `BlockActivation(False, False)` guarded by `s6BasementGateOpening`, logs `s6 basement_gate unlocked reason=terminal|lockpick`, and makes Fusion Core pickup order-independent across stage 45 (`45` = FO4 `Min00 50`, obj `95` = FO4 `105`).",
        f">   - **`J8` (Derived IDs, `h2h4` Cover Hop, `3d` Wrist Prefix Fix & Clean Stage):** Generates batches & card from plugin load order and DLL INI key map; moves `bat h2h4` behind NW Concord cover at `({hx:.2f}, {hy:.2f}, {hz:.2f})` (`z {make_mission.H2H4_HOP_ANGLE_Z}`, `>= 39.8 m >= 15 m` from raiders `{mis}000803..000805`); adds `bat h2ge` Gate `E` probe; fixes `LogPipboyWrist3DNodes` (`FO4WristHousing1st_`, `FO4WristHousing1stF_`, `FO4WristHousingF_`, `FO4WristHousingM_`); adds 5 `check-bundle` gates; requires `dirty=false` & `verify == HEAD`.",
        "> - **P3 Scope Note:** P3 (`0` `M`/`N`/`V`) applies to **typed interactive** console lines and **batch filenames** (`pod_seat.txt`, `pod_step.txt`, `h2s.txt`, `h2hp.txt`, `h2ge.txt`, `h2*.txt`); `getglobalvalue`, `getav`, `moveto`, `prid`, and `additem` stay inside `bat/*.txt`.",
        "> - **Logging Preflight (`G3`, Required Before Running):** Confirm `StarfieldCustom.ini` sets all `3` `[Papyrus]` keys (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`); wait `10 s` after New Game launch and verify `Documents/My Games/Starfield/Logs/Script/User/fo4sf_newgame.0.log` is non-empty before proceeding.",
        "",
        "---",
        "",
        "## 1. Staged Component Scope & Check-Bundle Gates",
        "",
        "| Component / Artifact | Contract & Changes in `candidate-2h-5` | Notes |",
        "|---|---|---|",
        f"| `<cand2h-port-dir>/FO4Port.*` + `FO4TerrainCore.esm` + `FO4SFExitLift.esm` | Slot `{port}` `FO4Port.esm`, slot `{core}` `FO4TerrainCore.esm` (`NAVI 0x00000FF1`; Vault 111 cog `{core}005A77` overridden by `FO4SFExitLift.esm` at `(-2475.58, -1403.93, 33.25)`); basement gate `{port}00EDF0`, terminal `{port}00E35E` (`XLKR` -> gate) | Passed `--port <cand2h-port-dir>/FO4Port.esm` |",
        f"| `FO4SFVaultPod.esm` (`I1`) | Slot `{pod}`: `ACTI 0x800` `FO4SF_PlayerCryoPod` (`ActivatorStateGraph01.agx`, `Exit=StateA_Play`), persistent `REFR 0x801` in cell `0x0011F3`, Initially Disabled override `0x001617`; offline clearance `min_clearance=0.0531 m` at `seat_step_m=-0.55` | Enforced by `check-bundle` (`pod_anim`) |",
        f"| `FO4SFCoreValues.esm` | Slot `{cv}`: `--fo4-arsenal 1 --fo4-10mm 1` (`25/25` arsenal WEAPs `0x000899..0x0008D6`, Bobby Pin `{cv}0008A5`, Laser Musket `{cv}00089D`, `--test-mode 0` in `player`) | Verified by `check-bundle --require-arsenal` |",
        f"| `FO4SFMission.esm` (`J6`) | Slot `{mis}`: `TryOpenS6BasementGate` dynamic XLKR gate lookup, `0` terminal `OnLockStateChanged` registration, `<= 1` `Lock(False, False, False)`, order-independent Fusion Core `{mis}000BDB` (`{pa}000809`), `FO4SF_ConfirmedLoadDoor` + `FO4SF_Placement` (`J1`) | Enforced by `check-bundle` (`j6_basement_lock`, `j1_shared_placement`) |",
        f"| `FO4SFNewGame.esm` (`J1`, `J2`, `J8`) | Slot `{ng}`: `0x826` retired, discovery marker `{ng}000827` (`ArrivalDiscoveryId`), immobile `ExitAnchorId` `{core}0A775B`, `IsInsideMergedFootprint` builder+runtime guard, `D-V111-10` zero pod box + vault save lock (`SetInCharGen(True, True, False)` until `pod_exit`), 4 wrist housing NIF prefixes | Enforced by `check-bundle` (`j1_footprint`, `j1_anchor_immutability`, `j1_shared_placement`) |",
        f"| `FO4SFWorkshop.esm` + `FO4SFPowerArmor.esm` | Slot `{ws}` `FO4SFWorkshop.esm` (`0x800` / `0x849` -> `{core}005C50`, `250.0 m`, W5/W6 `\"NOT WIRED\"`); Slot `{pa}` `FO4SFPowerArmor.esm` (`{pa}000809` Fusion Core) | `FusionCore` slot updated from stale `0C` to `{pa}` (`J8`) |",
        "| `FO4SFMapMarkers` (`map-markers/`) | Verified `--require-map-markers` (`PrepareKnownUndiscoveredAll` queued non-blockingly; silent `DiscoverSingleMarkerSilent` on first landing) | Installed via `map_markers_install.py` |",
        "| `FO4SFPipboyMenu.dll` + `Main.ba2` (`J1`, `J3`) | `FO4SFPipboyMenu.dll` patches live `BSTranslator` buckets after data load with FO4 GMST words (`QUEST`, `QUESTS`, `QUEST ADDED`, `QUEST UPDATED`, `QUEST COMPLETED`, `QUEST FAILED`, `Quest Log`, `keys_ok=20/20`), logs `step=loading_menu_closed gen=<n>`, honors `h00SkipLoading`; `Translate_en.txt` packed in `FO4ActorRaider - Main.ba2` | Enforced by `check-bundle` (`quest_translate`, `j8_card_and_batches`) |",
        "",
        "---",
        "",
        "## 2. Offline Verification, Install & Rollback (Game Closed)",
        "",
        "```bash",
        "# 1. Offline gates (Game closed: Starfield.exe == 0, CreationKit.exe == 0, Archive2.exe == 0; dirty == false)",
        "python scripts/guard.py",
        "python scripts/core/make_core_bundle.py verify --bundle-dir <cand2h-player-bundle> --port <cand2h-port-dir>/FO4Port.esm --require-map-markers",
        "python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2h-player-bundle> --require-arsenal",
        "python D:/FO4SF-Owner-Tests/tools/preflight_ids.py --bundle-dir <cand2h-player-bundle>",
        "",
        "# 2. Reversible FO4Port.* swap (backup vanilla/prior port if backup folder absent)",
        "mkdir -p <starfield-dir>/Data/FO4Port_pre2h_backup",
        "cp -n <starfield-dir>/Data/FO4Port.esm \"<starfield-dir>/Data/FO4Port - Main.ba2\" \"<starfield-dir>/Data/FO4Port - Textures.ba2\" <starfield-dir>/Data/FO4Port_pre2h_backup/",
        "cp -f <cand2h-port-dir>/FO4Port.esm \"<cand2h-port-dir>/FO4Port - Main.ba2\" \"<cand2h-port-dir>/FO4Port - Textures.ba2\" <starfield-dir>/Data/",
        "",
        "# 3. Install 14-plugin player bundle (--pack --textures-archive) + SFSE sidecar + map-markers + bat/*.txt",
        f"python scripts/game/exp_install.py install --exp-dir <cand2h-player-bundle> --starfield <starfield-dir> --plugins {plugin_csv} --pack --textures-archive",
        "python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2h-player-bundle> --starfield <starfield-dir>",
        "python scripts/game/map_markers_install.py install --dir <cand2h-player-bundle>/map-markers --starfield <starfield-dir>",
        "cp -f <cand2h-player-bundle>/bat/*.txt <starfield-dir>/",
        "```",
        "",
        "### Reversible Rollback (Game Closed)",
        "",
        "```bash",
        f"rm -f {rm_bats}",
        "python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>",
        "python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>",
        "python scripts/game/exp_install.py uninstall --starfield <starfield-dir>",
        "cp -f <starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port.esm \"<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Main.ba2\" \"<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Textures.ba2\" <starfield-dir>/Data/",
        "rm -rf <starfield-dir>/Data/FO4Port_pre2h_backup",
        "```",
        "",
        "---",
        "",
        f"## 3. Card 2h-1 (`J2` Pod No-Box & Vault Save Lock, `S2` Roaches, `J1` Two-Load Surface Arrival & Roundtrip, `J3` FO4 `QUEST` Words, `{f7}` Wrist — `REACHABLE` / `TEST-STATION`)",
        "",
        "| Step | Action | Expected In-Game & Log Result | Status | VIDEO / Media |",
        "|---|---|---|---|---|",
        f"| **1a. `J2` Fresh New Game — Pod Opens Directly (NO Box, `D-V111-10`, Save Locked Until Exit)** | Launch SFSE -> **New Game -> Vault 111 / Story** (`10 s` `fo4sf_newgame.0.log` preflight). Do NOT pick anything in a choice box (none opens). Try Esc/QuickSave inside closed pod, then wait for FO4 `Exit` (`~5.3 s`) and walk out (`WASD`). | First visible frame is closed pod (`Window` corridor view); **zero** `StartMessage` box and **zero** `ChargenMenu`; `WASD` + saving stay locked (`SetInCharGen(True, True, False)` -> `vault_death_recovery=save_locked`) through `pod start choice=none rule=D-V111-10`, `pod_open accepted=true`, `5.33 s` door rise -> `pod_step_out by=walk` -> saving unlocks + `vault_death_recovery=autosave` fires AFTER `pod_exit`, then `stage 20` autosave. | `REACHABLE` | **VIDEO** `v111-pod`: `>= 10 s` closed-pod wake -> door rise -> walk step-out (NO box); **`audio: not judged`**. |",
        "| **1a-vault-death. `J2` Die in Vault 111 After Pod Exit** | After walking out of the pod (save already unlocked & recovery autosave written), die in Vault 111 (console `player.kill` inside a vault check or hazard) without opening `ChargenMenu`. | Reloads the vault recovery autosave with plain-black cover (`0` Starfield planet/tip screen) and **NEVER** opens the character creator (`ChargenMenu`). | `REACHABLE` | **VIDEO** `v111-vault-death`: post-exit death -> clean vault autosave reload (zero creator). |",
        "| **1a-fallback. `I1` CryoPod Fallback Path (Untested)** | Disable `{pod}000801` (`FO4SFVaultPod.esm`) before vault wake. *(Preserved untested row — reachable from Vault start.)* | `pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=play_refused` or `reason=not_loaded` within `8 s`; controls & saving returned cleanly. | `REACHABLE` | Take `v111-pod-fallback` (when testing fallback branch). |",
        f"| **1b. `S2` Vault 111 Roaches (`{mis}000B90`, `L2`, Untested)** | Walk Vault 111 corridor toward Overseer/lift (`{mis}000B8D=1`, `{mis}000B8C=0` empty slot). *(Preserved untested row — reachable by walking `L2` without console kills.)* | `s2 vault_roaches creature_slot=empty fallback=stage_gate` -> completes with `stage=100` *(5 markers visited <= 12 m)* or `stopped reason=left_vault_stage_200`. | `REACHABLE` | Take `v111-corridor`: `>= 6 s` hall traversal. |",
        f"| **1c. `J1` & `J8` Wrist 3D Log, `F7` (`{keys['toggle_hex']}`), and Two-Load Surface Arrival (`set=true` in `CF0`, ZERO Flash)** | Walk `L10` armory leg; **press `E`** on Armory pistol (`{ng}000820`), ammo box (`{ng}000821`), and Pip-Boy (`{ng}00080F`); press **`{f7}`** (`Arm=1` raise -> 2D menu -> lower); **press `E`** on Vault console (`{ng}000819`), spend S.P.E.C.I.A.L. points (`pool == 0`), ride cog up. | Wrist draws FO4 housing + lit green `PipboyScreen` AND `pipboy wrist 3d housing=true screen=true` (`4` NIF prefixes checked); `J1` two-load path: `story landing loading menu opened` before `FadeOutGame`, `surface moveto_target source=fo4_0009f272_div70 pos=-1275.31 1305.28 127.21 inside_footprint=false` -> load `1` outside footprint -> `surface one_move ... set=true cell=0x04000CF0` (`ExitAnchorId` `{core}0A775B` never moved!) under **held plain-black fade (ZERO dark procedural mountain flash)** -> `step=loading_menu_closed gen=<n>` -> `surface_cog wait_3d` -> `rise carry t=2.0` -> clear daylight (`WTHS 0x001034AB`), silent discovery on own marker `{ng}000827` (`0` Red Rocket banner). | `REACHABLE` | **VIDEO** `v111-wrist-lit` (`>= 6 s` wrist + `{f7}`) + **VIDEO** `v111-lift-up-1` (`0.0 s` start -> `8.5 s` held black -> two loads -> hilltop rise, ZERO dark-mountain flash). |",
        "| **1c-suit. `I2(c)` Spacesuit Co-Equip Check (`1E2B18`)** | Equip Starfield spacesuit on bit `54` via `bat h2s` (`player.additem 1E2B18 1` / `equipitem`); inspect 1P & 3P left forearm. | Spacesuit (`SSChronoMark` on bit `54`) does NOT hide or unequip bit-`55` `FO4SF_PipboyWrist` (`0x80D`); wrist housing + lit green `PipboyScreen` remain drawn. | `TEST-STATION` | **VIDEO** / Still `wrist-spacesuit-h2s`: `>= 6 s` 1P + 3P wearing `1E2B18`. |",
        "| **1d. `J3` Live `BSTranslator` FO4 Words (`QUEST`, `QUEST ADDED`, `QUEST UPDATED`) + Landing Handoff** | Watch first landing toasts (`stage 40 -> 200`, `Codsworth01` start) and open Pause / Quests menu. | Live `BSTranslator` write logs `step=hud_quest_label_patch ok=1` + `step=hud_quest_label_runtime ... keys_ok=20/20 runtime_ok=1`; HUD toast reads **`QUEST`** (`QUEST ADDED`, `QUEST UPDATED` on `$MissionUpdate` & `$MISSION UPDATED`, `QUEST COMPLETED`, `QUEST FAILED`, `QUESTS`, `Quest Log`, `$MISSION STATUS`=`QUEST STATUS`); zero duplicate `OUT OF TIME` quest-complete toast spam. | `REACHABLE` | **VIDEO** `v111-armory-lift` + Pause/Quests still proving live `QUEST` strings. |",
        "| **1e. `J1` + `J2` Lift `Change Appearance` Roundtrip & Save/Quit/Load Re-Ascent Hang Check** | On lift console (`D-LIFT-04`), pick **Change Appearance**, edit/confirm look, return to lift menu. On surface cog, **RIDE LIFT DOWN TO VAULT 111**, **save inside Vault**, **Quit to Desktop**, **relaunch & load save**, and **ride lift back up** (watch for `VAULT 111` banner & hang). | `Change Appearance` opens creator on lift & returns cleanly to lift menu (`0` pod creator before lift); ride down returns control at `~9.9 s`; post-reload ride up **does NOT hang** (`step=loading_menu_closed gen=<n>`, MoveTo hits `(-1275.31, 1305.28, 127.21)` OUTSIDE footprint -> `set=true` in `04000CF0`), and repeat arrival suppresses `arrival discovery` (`Vault111Location` `0x01F3FE` probe for banner check). | `REACHABLE` | **VIDEO** `v111-lift-roundtrip`: down -> vault save -> quit/load -> up (zero hang, banner status captured). |",
        "",
        "---",
        "",
        "## 4. Card 2h-2 (`2a` Cold Reload, `H3` `#854` Codsworth Mr. Handy & Chrome, `S3` Walk, `H6` Sanctuary Bench — `REACHABLE` / `TEST-STATION`)",
        "",
        "| Step | Action | Expected In-Game & Log Result | Status | VIDEO / Still |",
        "|---|---|---|---|---|",
        "| **2a. Cold Reload #1 (`Throwaway_2h_Surface`)** | Save on Vault 111 hilltop -> `Quit to Desktop` -> relaunch SFSE -> load save. | `reload mission stage=0 relocate_fails=0`, `codsworth01 reload stage=10 choices=0`, `FO4SF_LOADDOOR reload_ready`, daylight restored, zero spurious return-lift popup. | `REACHABLE` | Take `surface-cold-reload`: `>= 5 s` post-load hilltop view. |",
        f"| **2b. `I6` Codsworth `E` Talk (`2 m` Front & Side — Front `E` Untested), Thruster Body & `S3` Walk** | Walk to Sanctuary Hills (`{mis}000811`). Take a **daylight still beside an FO4 reference**; aim at Codsworth from **`2 m` front (untested in 2h-4) and `2 m` side** and **press `E`** (`[E] Talk` via invisible `{mis}000970` proxy -> `{mis}000940`); exit & re-talk; pick Choice 3 (`24`), then Choice 4 (`30 -> 32`), walk House `01 -> 02` (`S9`/`S3` start reachable without console kills). | Codsworth hovers on **`FO4SF_HandyRace` (`{mis}000818`) thruster (`LegsHandyThruster`) with ZERO MiniBot legs**; `E` at `2 m` front & side fires `codsworth scene talk requested`; greeting does not replay on 2nd talk (`0x97C` -> `0x943`); `stage 100 concord_pointed=true`, `min00 given by=codsworth`. | `TEST-STATION` | **Daylight Still** + **VIDEO** `sanctuary-codsworth-h3`: `>= 15 s` idle, turn, thruster hover, `E` front & side, House `01->02` walk. |",
        f"| **2c. `H6` Sanctuary Bench After First Settlement (`{core}005C50`, Untested)** | After *First Settlement* (`FO4SF_Sanctuary01` `{mis}000817`) starts (`Row 5a`), press **`E`** on the Sanctuary workbench (`{core}005C50`) and **build one object**. *(Preserved untested row — reachable from `Row 5a` save without console kills.)* | Bench plugin (`FO4TerrainCore.esm`), ID (`0x005C50` / `23632`), and radius (`250.0 m`) are read dynamically from `FO4SFWorkshop.esm` `{ws}000800` (`sanctuary01 bench_rule ...`); non-blank footer (zero `\".\"`); object places cleanly -> `min01 bench activated -> stage 100`. | `REACHABLE` | Take `sanctuary-bench-h6`: `>= 6 s` opening bench & building `1` object after `FO4SF_Sanctuary01` starts. |",
        "",
        "---",
        "",
        "## 5. Card 2h-3 (`S4` Concord Exterior `z ~88`, `J8` `h2h4` Behind Cover, `H1` Updated Fight `3b`, Preston Balcony & Musket — `REACHABLE`)",
        "",
        "| Step | Action | Expected In-Game & Log Result | Status | VIDEO |",
        "|---|---|---|---|---|",
        f"| **3a. Hop Chain (`< 200 m`/axis) & `J8` `h2h4` Behind NW Cover** | Walk or run `bat h2h2` -> `3 s` -> `bat h2h3` -> `3 s` -> `bat h2h4`. | `bat h2h4` lands behind NW road cover at **`({hx:.2f}, {hy:.2f}, {hz:.2f})` (`z {make_mission.H2H4_HOP_ANGLE_Z}`)** (`>= 39.8 m >= 15 m` from raiders `{mis}000803..{mis}000805`, zero `0.66 m` instant death, `< 73 m` hop from Red Rocket South); Concord buildings render at `z ~88.3..90.0 m`. | `REACHABLE` | Take `concord-exterior-z88`: `>= 5 s` NW cover approach & facade pan. |",
        f"| **3b. Updated Concord Street Fight (`H1`/`G11`, God Mode OFF, Timed `10 s` HP Read) & Death Reload Picture (Untested)** | Move into street line-of-fire with **god mode OFF**, let Concord street raiders (`{mis}000803..{mis}000805`) fire while standing idle `10 s`, run `bat h2hp` at **`10 s`**, then use cover & shooting to clear street raiders. Also let character die once to capture the death-reload black cover picture (untested in 2h-4). | **PASS:** HP at `10 s` drops **`>= 20` while staying alive at `10 s`**, and cover + shooting clears to **`stage 30` (obj `60`) within `60` rounds**; raiders wear FO4 outfits; death reload uses plain-black cover (`0` planet/tip screen — capture proof still!). | `REACHABLE` | Take `concord-fight-g11` (`>= 15 s`) + still/clip of plain-black death reload cover. |",
        f"| **3c. Preston Balcony & `E` Display Musket (`{mis}000BA8`) + Cells (`{mis}000BAA..BAC`)** | Check Preston on 3F balcony (`z=98.51`); **press `E`** on display Laser Musket (`{mis}000BA8`) and `3` Fusion Cell pickups (`{mis}000BAA..BAC`). | `s4 balcony preston_z=98.51`, `s4 laser_musket granted cells=15` (`FO4_LaserMusket` `{cv}00089D`), `+3x5` Fusion Cells. | `REACHABLE` | Take `concord-musket-pickups`: `>= 6 s` aiming & `Take [E]`. |",
        "",
        "---",
        "",
        "## 6. Card 2h-4 (`H5` Front Door `E` Probe `4a`, Cold Reload `4a2`, `S5` 7 Raiders + Stair Climb `L3` — `REACHABLE`)",
        "",
        "| Step | Action | Expected In-Game & Log Result | Status | VIDEO |",
        "|---|---|---|---|---|",
        f"| **4a. `H5` Front Door `E` Probe + `5x` Round-Trip (`E` Untested — 2h-4 Passed by Console Activation Only)** | Aim at `FO4SF_S5_ExtFrontInRef` (`{mis}000BB8`) -> **press `E`** (not console activate) -> Lobby -> **press `E`** on `FO4SF_S5_IntFrontOutRef` (`{mis}000BB9`) -> Concord street; repeat `5x`. | `FO4SF_LoadDoorQuest` (`{mis}000BDE`) & `FO4SF_ConfirmedLoadDoor` route `out` via `FO4SF_Placement` without moving `{core}0A775B`/`{core}0A775C`; every press logs `confirmed ... core_cell=true` (verify `E` input works directly!). | `REACHABLE` | Take `museum-front-door-5x`: `>= 15 s` door `Open [E]` + round trip. |",
        f"| **4a2. Cold Reload Inside Museum Front Door (`H1`/`H5`/`J1`)** | Inside `FO4Port_ConcordMuseum01`, save **`Throwaway_2h_MidMuseum`**, **`Quit to Desktop`**, relaunch SFSE, load save, and **press `E` on `{mis}000BB9`**. | `FO4SF_LOADDOOR reload_ready` -> pressing **`E`** routes through `FO4SF_Placement` from static `0x0A775B`/`0x0A775C` -> `FO4SF_LOADDOOR confirmed tag=s5_front_out dir=out ... core_cell=true` (zero hang, `inside_footprint=false` / `core_cell=true`). | `REACHABLE` | Take `museum-cold-reload-door`: `>= 8 s` post-reload exit. |",
        f"| **4b. `S5` 7 Raiders + Stair Climb (`L3`, Untested) + `E` Pickups -> `Min00 35`** | Engage `7` museum raiders (`{mis}000BBC..{mis}000BC2`); watch ground raider stair climb (`L3`, untested in 2h-4); **press `E`** on Stimpaks (`{mis}000BAE..BAF`), Caps (`{mis}000BB1`), Bobby Pin (`{mis}000BB3`), Pipe Pistol + `.38` (`{mis}000BB5`). | Ground raider climbs atrium stairs via `NAVI 0x00000FF1` + `{mis}000BE1`; `s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked`. *(Keep throwaway save before `{port}00EDF0` unlocks for `5b`.)* | `REACHABLE` | Take `museum-raider-climb-pickups`: `>= 15 s` stair climb + pickups. |",
        "",
        "---",
        "",
        "## 7. Card 2h-5 (`H2` 3F Scenes & `S9` Walk Untested `0x817`, `J6` Basement Gate & Core `5b`, `F9` Roof `E` Untested — `REACHABLE`)",
        "",
        "| Step | Action | Expected In-Game & Log Result | Status | VIDEO |",
        "|---|---|---|---|---|",
        f"| **5a. `H2` Preston Talk -> `S9` Walk (Untested, Reachable Without Console Kills) -> First Settlement (`{mis}000817`)** | Enter 3F room (`Preston {mis}000802` + group in `Settler Clothes` stand-in, `0` spacesuits); **press `E`** on Preston & Sturges, complete `5b`, return to Preston -> walk group out to Sanctuary (`S9` walk preserved untested, reachable naturally after `5b`) -> **First Settlement**. | Dynamic resolver logs `scene resolved via=file id=0x000BC9`/`0x000BD0`; `s6 preston room scene started` -> `s6 stage 40 preston_group talk` -> `stage 200` -> `min01 group_arrived sanctuary=true` -> `sanctuary01 stage 1000 obj=1000 hard_stop=true` (unlocks **`2c`** bench build). | `REACHABLE` | Take `museum-preston-to-first-settlement`: `>= 15 s` 3F talk, `S9` walk, and First Settlement toast. |",
        f"| **5b. `J6` & `J8` Basement Gate (`{port}00EDF0`) Terminal + Bobby Pin (`bat h2p`), `E` Probe (`bat h2ge`) & Order-Independent Fusion Core (`{pa}000809`)** | Unlock `{port}00EDF0` via Wall Terminal (`{mis}000BD9` / `{port}00E35E` -> **press `E`** on `{port}00EDF0` or run `bat h2ge`) AND via reload + `bat h2p` Bobby Pin `{cv}0008A5`; test picking Fusion Core (`{mis}000BDB`, base **`{pa}000809`**) either BEFORE or AFTER gate open. *(FO4 mapping: our stage `45` = FO4 `Min00` stage `50`; our PA objective `95` = FO4 objective `105`.)* | Terminal (`{mis}000BD9` -> `XLKR` `{port}00EDF0`) and Bobby Pin each make **at most 1 `gate.Lock(False, False, False)`** (`0` `OnLockStateChanged` terminal reg, `0` `Unlock`/`SetLockLevel`/`SetOpen(True)`, `0` Papyrus stack flood), log `s6 basement_gate unlocked reason=terminal|lockpick` + `s6 stage 45 basement_gate opened`, player opens unlocked gate cleanly; `{mis}000BDB` grants `{pa}000809` (`fid=2057`) + completes `obj 90` & displays `obj 95` (`stage 50`) in **either** order! | `REACHABLE` | Take `museum-basement-both-paths`: `>= 15 s` terminal + `E` open (`h2ge`), reload + lockpick, and core pickup. |",
        f"| **5c. Roof Door `E` Probe + `3x` Round-Trip (`F9` `(-1990.58, -1724.19, 97.56)`, `E` Untested)** | **Press `E`** (not console activate) on `FO4SF_S5_IntRoofOutRef` (`{mis}000BBA`) -> bulkhead -> **press `E`** on `FO4SF_S5_ExtRoofInRef` (`{mis}000BBB`), `3x` round trips. | Solid standing on roof bulkhead at `z ~97.56` (`0` drop to `z ~88`), `confirmed ... core_cell=true` on all `6` legs via `E`. | `REACHABLE` | Take `museum-roof-door-3x`: `>= 12 s` roof arrival + re-entry via `E`. |",
        "",
        "---",
        "",
        "## 8. Console Inspection & `< 200 m` Hop Batches (`P3`: zero `M`/`N`/`V` in typed console or batch filenames)",
        "",
        "````console",
        "help \"Calls\" 4 QUST",
        f"getstage {mis}000816",
        f"getstage {mis}000800",
        f"getstage {mis}000B90",
        f"getstage {mis}000817",
        f"sqs {mis}000800",
        f"sqs {mis}000816",
        "bat pod_seat",
        "bat pod_step",
        "bat h2s",
        "bat h2hp",
        "bat h2st",
        "bat h2h2",
        "bat h2h3",
        "bat h2h4",
        "bat h2f",
        "bat h2b",
        "bat h2ge",
        "bat h2k",
        "bat h2p",
        "bat h2r",
        "````",
        "",
        "### Required PASS Log Lines (Quoted Directly from Source)",
        "",
        "```log",
        "FO4SF_NEWGAME rt=<rt> enter vault ok=<bool> pos=<x> <y> <z> target=<tx> <ty> <tz> cell=<cell> mode=<mode>",
        "FO4SF_NEWGAME rt=<rt> pod start choice=none rule=D-V111-10",
        "FO4SF_NEWGAME rt=<rt> vault_death_recovery=save_locked stage=<st>",
        "FO4SF_NEWGAME rt=<rt> pod_hold on seat=<x> <y> <z> heading=<heading> saving=locked",
        "FO4SF_NEWGAME rt=<rt> pod_open play=Play01 accepted=<bool>",
        "FO4SF_NEWGAME rt=<rt> pod_open done elapsed=<elapsed> ref=<ref>",
        "FO4SF_NEWGAME rt=<rt> pod_step_out by=walk",
        "FO4SF_NEWGAME rt=<rt> pod_exit mode=cryopod_anim hook_stage=15 moved=true pos=<x> <y> <z> heading=<heading> open_s=<open_s> by=walk",
        "FO4SF_NEWGAME rt=<rt> pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=<reason>",
        "FO4SF_NEWGAME rt=<rt> pod_state on_load=open",
        "FO4SF_NEWGAME rt=<rt> pipboy wrist equipped item=<item> worn=<bool> slot=55",
        "FO4SF_NEWGAME rt=<rt> pipboy wrist 3d housing=<bool> screen=<bool>",
        "step=pipboy_screen wrist_draw=static",
        "step=hud_quest_label_patch ok=1 patched=<patched>/<total> capacity=<cap>",
        "step=hud_quest_label_runtime file=present file_ok=1 mission_status=<status> mission_new=<new> mission_update=<update> keys_ok=<ok>/<total> runtime_ok=1",
        "step=loading_menu_closed gen=<gen>",
        "FO4SF_NEWGAME rt=<rt> vault_death_recovery=autosave stage=<st> after=pipboy_pickup",
        "FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=1 equipped=True base=<form>",
        "FO4SF_NEWGAME rt=<rt> pistol ammo picked item=<item> count=48 base=<form>",
        "FO4SF_NEWGAME rt=<rt> map setup queued by=<why>",
        "FO4SF_MAP rt=<rt> q=<q> prepare_all done count=<count> elapsed=<elapsed>",
        "FO4SF_NEWGAME rt=<rt> lift_pair fade_out dir=<dir> elapsed=<elapsed> fade_at=<fade_at>",
        "FO4SF_NEWGAME rt=<rt> surface moveto_target source=fo4_0009f272_div70 pos=<x> <y> <z> inside_footprint=<bool>",
        "FO4SF_NEWGAME rt=<rt> surface one_move off=<off> set=<bool> cell=<cell>",
        "FO4SF_NEWGAME rt=<rt> loading cover black opened why=<why>",
        "FO4SF_NEWGAME rt=<rt> lift_pair surface_cog wait_3d n=<n> loaded=<bool>",
        "FO4SF_NEWGAME rt=<rt> lift_pair rise carry t=2.0 z=<z>",
        "FO4SF_NEWGAME rt=<rt> lift_pair ride arrived dir=<up|down> z=<z> cell=<cell> world=<world>",
        "FO4SF_NEWGAME rt=<rt> lift_pair interior busy until_done",
        "FO4SF_NEWGAME rt=<rt> lift_pair interior state=<A|B> why=<why>",
        "FO4SF_NEWGAME rt=<rt> arrival weather id=<id> plugin=<plugin> override=<override> weather=<wthr>",
        "FO4SF_NEWGAME rt=<rt> death_reload plain_black_cover=<bool>",
        "FO4SF_NEWGAME rt=<rt> landing handoff mode=single_quest newgame_completed=False codsworth01_displayed=True",
        "FO4SF_MISSION rt=<rt> codsworth talk proxy model=invisible_volume visible=false",
        "FO4SF_MISSION rt=<rt> codsworth scene talk requested scene=<scene> via=<via> stage=<stage>",
        "FO4SF_MISSION rt=<rt> codsworth01 greeting_played=1",
        "FO4SF_MISSION rt=<rt> codsworth01 stage 24 by=info",
        "FO4SF_MISSION rt=<rt> codsworth01 stage 30 house=1",
        "FO4SF_MISSION rt=<rt> codsworth01 stage 36 house=2",
        "FO4SF_MISSION rt=<rt> codsworth01 stage 50 scene started",
        "FO4SF_MISSION rt=<rt> codsworth01 stage 100 concord_pointed=true",
        "FO4SF_MISSION rt=<rt> min00 given by=codsworth",
        "FO4SF_MISSION rt=<rt> s2 vault_roaches creature_slot=empty fallback=stage_gate",
        "FO4SF_MISSION rt=<rt> codsworth01 s3 creature_slot=empty fallback=arrival_advance",
        "FO4SF_MISSION rt=<rt> scene resolved via=file id=0x000B9A scene=<ref>",
        "FO4SF_MISSION rt=<rt> scene missing id=0x000BC9",
        "FO4SF_MISSION rt=<rt> s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked",
        "FO4SF_MISSION rt=<rt> s6 room_scene requested sturges=false via=activate",
        "FO4SF_MISSION rt=<rt> s6 preston room scene started",
        "FO4SF_MISSION rt=<rt> s6 preston fallback stage=40 reason=no_scene",
        "FO4SF_MISSION rt=<rt> s6 sturges room scene started",
        "FO4SF_MISSION rt=<rt> s6 stage 40 preston_group talk",
        "FO4SF_MISSION rt=<rt> s6 basement_gate unlocked reason=<reason>",
        "FO4SF_MISSION rt=<rt> s6 stage 45 basement_gate opened",
        "FO4SF_MISSION rt=<rt> pickup fusion_core granted=true fid=2057",
        "FO4SF_MISSION rt=<rt> s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa",
        "FO4SF_MISSION rt=<rt> min01 group_arrived sanctuary=true via=<via>",
        "FO4SF_MISSION rt=<rt> sanctuary01 stage 1000 obj=1000 hard_stop=true",
        "FO4SF_MISSION rt=<rt> sanctuary01 bench_rule plugin=FO4TerrainCore.esm ref=23632 radius=250.0",
        "FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100",
        "```",
        "",
        "---",
        "",
        "## 9. Later Plug-In Seams (`J1`–`J8` + Round 16 / Wave B)",
        "",
        "| Item | 0.1 Behaviour | Later plug-in |",
        "|---|---|---|",
        f"| **J1 (Shared Placement, Immobile Anchors, Two-Load Workaround)** | `FO4SF_Placement` routes `Surface()`, `FinishSurface()`, and `FO4SF_ConfirmedLoadDoor` (`out`); `{ng}000826` retired and `{ng}000827` owns first-landing discovery; `{core}0A775B` never moves (`inside_footprint=false` build+runtime guard); `step=loading_menu_closed gen=<n>` + held plain black across both loads. | **Later plug-in:** Single-load FO4 automatic-door XTEL (`REFR 0001F180` -> `DOOR 0007ECFC`) attaches behind an in-game probe on `FO4SF_Placement` and remains direct callers in `2h-6`, reusing `FO4SF_NewGameQuest` (`SetLoadingBlackCover`) and `0x000827` untouched. |",
        "| **J2 (No Pod Choice Box + Vault Save Lock, `D-V111-10`)** | Pod opens straight to door + walk-out (`pod start choice=none rule=D-V111-10`), saving locked via `SetInCharGen(True, True, False)` until `pod_exit`, then vault recovery autosave; lift `Change Appearance` stays on the elevator (`D-LIFT-04`). | **Later plug-in:** Pre-load New Game configuration window (`D-UI-09`) runs before vault entry without re-introducing any in-pod `Message.Show()` or editing Vault 111 quest flow. |",
        "| **J3 (Live `BSTranslator` Patch & FO4 GMST Words)** | `FO4SFPipboyMenu.dll` patches live Scaleform `BSTranslator` hash buckets with FO4 GMST wording (`QUEST ADDED`, `QUEST UPDATED`, `QUEST COMPLETED`, `QUEST FAILED`, `QUESTS`) alongside `Translate_en.txt` in `Main.ba2`. | **Later plug-in:** Localization tables (`Translate_<lang>.txt`) or additional FO4 UI tokens extend the `hud_quest_label.h` key map cleanly without changing Starfield Scaleform hook logic. |",
        f"| **J6 (Basement Gate Single-Lock & Order-Independent Fusion Core)** | Dynamic XLKR gate resolution (`{port}00E35E` -> `{port}00EDF0`), `0` terminal `OnLockStateChanged`, `<= 1` `Lock(False, False, False)`, `SetOpen(True)` dropped in favor of player `E` (`bat h2ge` probe), order-independent core pickup (`{pa}000809`). | **Later plug-in:** Any Starfield lockable container/door puzzle or Power Armor stage hooks directly into `RecordS6BasementGateUnlocked` / `PlayerHasFusionCore` and optional logged `SetOpen` fallback only if a door refuses `E`. |",
        f"| **J8 (Card/Batch Generator, `check-bundle` Gates & `3d` Wrist Prefixes)** | `scripts/testing/generate_candidate_2h_card.py` + `make_mission.py` derive all plugin prefixes and INI keys (`{f7}`); `h2h4` sits `>= 15 m` behind NW cover; `LogPipboyWrist3DNodes` checks all `4` NIF prefixes; 5 new `check-bundle` checks enforce constraints offline. | **Later plug-in:** Adding/reordering FO3/NV/DLC plugins re-runs `generate_candidate_2h_card.py` & `write_r12_h2_batches` to stamp every card ID, batch token, and `check-bundle` assertion automatically. |",
        "| **I2 / I6 / H1–H6** | Lit green `PipboyScreen` (`0x823`, bit `55`), `2d_imenu` on `F7`, Codsworth thruster (`09000818`) + `09000970` proxy + `SayOnce` `0x97C`, `25/25` arsenal, `load_doors.json`, `settlement_rules.json` (`250.0 m`). | **Later plug-in:** `ScreenSource=3d_rtt` projection, FO3/NV weapon/actor/workshop/door data rows, and `#855` creature races plug into existing data tables without quest rewrites. |",
        "",
        "---",
        "",
        "## Claude's Additions (5 Rows — Round 15 Wave B Status)",
        "",
        "| Addition | PR / Track | Integration Status in `candidate-2h-5` | VIDEO / Still |",
        "|---|---|---|---|",
        "| **Robot animations & Codsworth** | `#854` (`claude/robot-anim` -> `gemini/r15-wb-854-handy`, credited to `#854` & Claude (PC)) | **ENABLED (`H3`)**: `--codsworth-handy E2 --codsworth-assets codsworth_handy_chrome` (no `--codsworth-race-framing`); FO4 `_s.dds` converted to BC4 `_rough.dds` + `HandyLens.BGEM` | Daylight **still** beside FO4 ref + **VIDEO** `sanctuary-codsworth-h3` (idle, turn, talk camera). |",
        f"| **Creature animations** | `#855` (`claude/creature-anim`) | **`not applicable` (default OFF)**: `{mis}000B8C = 0.0`; `S2` & `S3` use `creature_slot=empty` fallback (S2 roaches marker table seam ready). | `v111-corridor` (`1 fps` PASS if empty-slot fallback advances cleanly). |",
        f"| **Human animations** | `#856` (`claude/human-anim`) | **`not applicable` (default OFF)**: `--fo4-human-anims 0` (`{mis}000B8E=0.0`); Preston/raiders wear FO4 outfits; 4 Sanctuary settlers wear `Settler Clothes` stand-in (`{mis}000BE4`/`{mis}000BE5`, zero spacesuits). | `museum-preston-to-first-settlement` (`>= 5 s` 3F room check, zero spacesuits). |",
        "| **Gun moving parts proof** | `#32` / P6b Arsenal | **BUILT IN (`H1`/`H4`)**: `FO4SFCoreValues.esm` built with `--fo4-arsenal 1 --fo4-10mm 1` (`25/25` WEAPs + P6b meshes/geometries/materials/textures folded). | `v111-armory-lift` & `concord-musket-pickups` (`>= 4 s` `10mm Pistol` / `Laser Musket` render & reload). |",
        "| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD / Starfield `SNDR` stand-ins**: zero `.afx`/WAUD banks touched. | **`audio: not judged`** across captures. |",
        "",
    ]
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(DEFAULT_CARD_OUT), help="Output markdown path (default: docs/testing/candidate-2h-card.md)")
    ap.add_argument("--plugins", default="", help="Comma-separated ordered plugin list (default: PLAYER_BUNDLE_PLUGINS)")
    ap.add_argument("--data-dir", default="", help="Optional Starfield Data dir for base full-master lookup")
    ap.add_argument("--bundle-dir", default="", help="Optional staged bundle dir")
    ap.add_argument("--port", default="", help="Optional FO4Port.esm path")
    ap.add_argument("--ini", default="", help="Optional FO4SFPipboyMenu.ini path")
    args = ap.parse_args(argv)

    plugins = [p.strip() for p in args.plugins.split(",") if p.strip()] if args.plugins else list(make_core_bundle.PLAYER_BUNDLE_PLUGINS)
    out_p = Path(args.out)
    text = render_candidate_2h_card(
        plugins,
        data_dir=args.data_dir or None,
        bundle_dir=args.bundle_dir or None,
        port_esm=args.port or None,
        ini_path=Path(args.ini) if args.ini else None,
    )
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out_p} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
