"""Data contracts, non-colliding FormID layout, 5 animation stand-in beat specs, and Stage 20 handoff rules for S1."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Sequence, Tuple

PLUGIN_PREWAR = "FO4SFPrewar.esm"
PLUGIN_PREWAR_WORLD = "FO4SFPrewar_Sanctuary.esm"
DEFAULT_SCRIPT_NAME = "FO4SF_PrewarQuest"
STANDINS_SCRIPT_NAME = "FO4SF_PrewarStandIns"

# Source Fallout 4 FormIDs (read-only reference constants; never committed asset bytes)
SANCTUARY_WRLD_FID = 0x000A7FF4
PREWAR_VAULT111_CELL_FID = 0x000CA260
MQ101_QUEST_FID = 0x0001ED86
MQ101_KELLOGG_QUEST_FID = 0x000D3997
DEFAULT_STRIP_RECT: Tuple[int, int, int, int] = (-23, -19, 19, 23)  # gx0, gx1, gy0, gy1 (5x5 FO4 cells)

# Slot 2 boundary on FO4Port.esm after Task 1 Slot 1 (292439a5)
MIN_PREWAR_PORT_START_ID = 0x00EFAB

# Built-in Starfield.esm IMAD FormIDs (Starfield IMAD uses REFL 8 KB blobs, not FO4 DNAM/*IAD subrecords)
SF_IMAD_EXPLOSION_FLASH = 0x00064C26      # ExplosionFlash
SF_IMAD_EXPLOSION_NUKE = 0x0002458E       # ExplosionNukeImod
SF_IMAD_FADE_TO_BLACK = 0x0001F60F        # FadetoBlackImod
SF_IMAD_FADE_IN = 0x0001C0B4              # mq101FadeInImod

# Key Pre-War Sanctuary & Vault 111 source coordinates in FO4 metres (FO4 units / 70.0)
SANCTUARY_KEY_COORDS_M: Dict[str, Tuple[float, float, float]] = {
    "player_start": (-1147.18, 1297.54, 112.23),
    "player_house_door": (-1143.58, 1299.30, 113.38),
    "vault_tec_rep_door": (-1142.68, 1298.27, 112.14),
    "west_bridge": (-1204.84, 1298.51, 105.34),
    "north_bridge": (-1096.34, 1190.51, 111.37),
    "military_gate_checker": (-1253.54, 1341.08, 119.66),
    "ext_elevator_center": (-1268.31, 1293.73, 127.50),
    "ext_elevator_base": (-1275.55, 1296.08, 33.30),
    "nuke_look_marker": (-1259.06, 1282.75, 130.05),
    "nuke_preload_ref": (-1284.60, 1290.71, 127.58),
    "vertibird_b_orbit": (-1136.00, 1216.71, 140.83),
    "vertibird_c_orbit": (-1117.97, 1236.39, 131.66),
    "vertibird_c_hover": (-1274.68, 1329.42, 148.11),
}

PREWAR_V111_KEY_COORDS_M: Dict[str, Tuple[float, float, float]] = {
    "int_autoload_door": (-77.77, -3.90, 47.56),
    "int_elevator_spawn": (-77.62, -3.81, 21.54),
    "int_elevator_base": (-70.40, -2.74, -0.11),
    "gear_door": (-54.86, -2.74, -0.14),
    "suit_furn": (-45.13, -7.81, -0.04),
    "player_cryopod": (9.14, -4.11, -1.03),
    "spouse_cryopod": (9.14, -10.51, -1.03),
    "cryo_terminal": (-1.09, -11.54, -1.06),
}

# FO4SFPrewar.esm non-colliding local FormIDs (0x000800..0x0008FF)
PREWAR_FORMS: Dict[str, Tuple[str, int]] = {
    "FO4SF_PrewarQuest": ("QUST", 0x000800),
    "FO4SF_PrewarCodsworthRace": ("RACE", 0x000801),
    "FO4SF_PrewarCodsworthBPTD": ("BPTD", 0x000802),
    "FO4SF_PrewarCodsworthNPC": ("NPC_", 0x000803),
    "FO4SF_PrewarCodsworthRef": ("ACHR", 0x000804),
    "FO4SF_PrewarSpouseMaleNPC": ("NPC_", 0x000805),
    "FO4SF_PrewarSpouseFemaleNPC": ("NPC_", 0x000806),
    "FO4SF_PrewarSpouseRef": ("ACHR", 0x000807),
    "FO4SF_PrewarVaultTecRepNPC": ("NPC_", 0x000808),
    "FO4SF_PrewarVaultTecRepRef": ("ACHR", 0x000809),
    "FO4SF_PrewarSoldierCheckerNPC": ("NPC_", 0x00080A),
    "FO4SF_PrewarSoldierCheckerRef": ("ACHR", 0x00080B),
    "FO4SF_PrewarVaultDoctorNPC": ("NPC_", 0x00080C),
    "FO4SF_PrewarVaultDoctorRef": ("ACHR", 0x00080D),
    "FO4SF_PrewarKelloggNPC": ("NPC_", 0x00080E),
    "FO4SF_PrewarKelloggRef": ("ACHR", 0x00080F),
    "FO4SF_PrewarInstAgentMNPC": ("NPC_", 0x000810),
    "FO4SF_PrewarInstAgentMRef": ("ACHR", 0x000811),
    "FO4SF_PrewarInstAgentFNPC": ("NPC_", 0x000812),
    "FO4SF_PrewarInstAgentFRef": ("ACHR", 0x000813),
    "FO4SF_PrewarFaction": ("FACT", 0x000814),
    "FO4SF_PrewarCrowdFaction": ("FACT", 0x000815),
    "FO4SF_PrewarCrowdRunnerNPC": ("NPC_", 0x000816),
    "FO4SF_PrewarCrowdRunner01Ref": ("ACHR", 0x000817),
    "FO4SF_PrewarCrowdRunner02Ref": ("ACHR", 0x000818),
    "FO4SF_PrewarCrowdRunner03Ref": ("ACHR", 0x000819),
    "FO4SF_PrewarCrowdRunner04Ref": ("ACHR", 0x00081A),
    "FO4SF_PrewarVertibird01Ref": ("REFR", 0x00081B),
    "FO4SF_PrewarVertibird02Ref": ("REFR", 0x00081C),
    "FO4SF_PrewarExtLiftPlatformRef": ("REFR", 0x00081D),
    "FO4SF_PrewarNukeAnchorRef": ("REFR", 0x00081E),
    "FO4SF_PrewarVaultArrivalMarker": ("REFR", 0x00081F),
    "FO4SF_PrewarKelloggMarkRef": ("REFR", 0x000820),
    "FO4SF_PrewarSpousePodMarkRef": ("REFR", 0x000821),
    "FO4SF_PrewarPlayerPodMarkRef": ("REFR", 0x000822),
    "FO4SF_PrewarCrowdGoalMarkRef": ("REFR", 0x000823),
    "FO4SF_PrewarHouseSpawnMarker": ("REFR", 0x000824),
    "FO4SF_PrewarUseMessageBoxGlob": ("GLOB", 0x000825),
    "FO4SF_PrewarHoldingCell": ("CELL", 0x000826),
    "FO4SF_PrewarVertibirdBase": ("STAT", 0x000827),
    "FO4SF_PrewarExtLiftBase": ("ACTI", 0x000828),
    "FO4SF_PrewarCodsworthOutfit": ("OTFT", 0x000829),
    "FO4SF_PrewarStageActiveGlob": ("GLOB", 0x00082A),
}

PREWAR_VOICE_START_ID = 0x000900

# Stage progression contract for FO4SF_PrewarQuest (hands off to FO4SF_NewGame Stage 20 in FO4Port_Vault111Cryo)
PREWAR_STAGE_CONTRACT: Dict[int, str] = {
    0: "idle / skipped (when fo4_vault111 Skip Pre-War is chosen)",
    10: "started in FO4SF_PrewarSanctuaryWorld (house talk with Spouse + Codsworth + Vault-Tec Rep)",
    20: "bombs drop / emergency broadcast -> evacuate Sanctuary with Beat (a) crowd + Beat (b) Vertibirds",
    30: "military gate cleared -> Beat (c) ExtVaultElevator descent & Beat (d) nuke flash + arrival in FO4Port_PrewarVault111",
    40: "Vault 111 processing (suit + doctor escort -> player cryo pod)",
    50: "Beat (e) pod-locked Kellogg sequence (MQ101KelloggSceneMain) + cryo refreeze fade",
    60: "Stage 20 handoff to FO4SF_NewGame in post-war FO4Port_Vault111Cryo",
    200: "pre-war complete",
}


@dataclass(frozen=True)
class BeatStandInSpec:
    """Explicit animation stand-in metadata required on cards and Papyrus traces."""

    code: str
    name: str
    status_label: str
    mechanism: str
    notes: str


STANDIN_BEATS: Tuple[BeatStandInSpec, ...] = (
    BeatStandInSpec(
        code="a",
        name="Running Sanctuary Crowd",
        status_label="animation stand-in",
        mechanism="HumanRace fleeing NPCs running Patrol/PathToReference along NAVM across bridge to hill markers + panic audio",
        notes="Replaces custom FO4 panic crowd .hkx choreography",
    ),
    BeatStandInSpec(
        code="b",
        name="Overhead Vertibirds",
        status_label="animation stand-in",
        mechanism="Converted Vertibird hull props driven along orbit/hover markers via timed Papyrus TranslateTo + flyby .wem audio",
        notes="Replaces FO4 Havok helicopter flight graph",
    ),
    BeatStandInSpec(
        code="c",
        name="ExtVaultElevator Platform Descent",
        status_label="animation stand-in",
        mechanism="Scripted platform TranslateTo (-21.6 m / 9.8 s) + OnTimer confirmed-arrival MoveTo + SetPosition into FO4Port_PrewarVault111",
        notes="Matches FO4SF_NewGameQuest non-blocking arrival pattern; zero OnActivate load hang",
    ),
    BeatStandInSpec(
        code="d",
        name="Distant Nuke Flash & Shockwave",
        status_label="animation stand-in",
        mechanism="Starfield.esm IMAD ExplosionFlash (0x064C26) + ExplosionNukeImod (0x02458E) + FadetoBlackImod (0x01F60F) + FadeOutGame + ShakeCamera + blast .wem",
        notes="Uses Starfield REFL IMADs rather than FO4 DNAM/*IAD blobs until mushroom particle NIFs are verified",
    ),
    BeatStandInSpec(
        code="e",
        name="Cryo-Pod View of Kellogg",
        status_label="animation stand-in",
        mechanism="Player locked at cryo pod facing Spouse pod + Kellogg/Institute agents at pod-front markers + MQ101KelloggSceneMain + gunshot .wem + freeze fade",
        notes="Replaces MultiActorFurniture 0x0016CA3D paired .hkx animation",
    ),
)


def validate_start_places_preserves_skip_prewar(start_places_doc: Dict[str, Any]) -> None:
    """Ensure `fo4_vault111` (Skip Pre-War) remains present, available, and pointed at `FO4Port_Vault111Cryo`."""
    places = start_places_doc.get("places")
    if not isinstance(places, list):
        raise ValueError("start_places.json missing 'places' list")
    v111 = next((p for p in places if isinstance(p, dict) and p.get("id") == "fo4_vault111"), None)
    if v111 is None:
        raise ValueError("start_places.json dropped required 'fo4_vault111' (Skip Pre-War) entry")
    if v111.get("space") != "FO4Port_Vault111Cryo":
        raise ValueError(f"fo4_vault111 space must remain FO4Port_Vault111Cryo, got {v111.get('space')!r}")
    if v111.get("plugin") != "FO4Port.esm" or v111.get("marker_source") != "vault_anchor":
        raise ValueError("fo4_vault111 FO4Port.esm / vault_anchor binding was modified")
    if not v111.get("available"):
        raise ValueError("fo4_vault111 (Skip Pre-War) must remain available=true")


def validate_stage20_handoff_contract(stage_contract: Dict[int, str], requested_stages: Sequence[int] = (10, 20, 30, 40, 200)) -> None:
    """Assert FO4SF_NewGame stage contract keeps every stage needed by Stage 20 handoff & S2."""
    missing = [s for s in requested_stages if s not in stage_contract]
    if missing:
        raise ValueError(f"FO4SF_NewGame STAGE_CONTRACT missing required handoff stages: {missing}")


def prewar_cross_plugin_entries() -> Dict[int, Tuple[str, str]]:
    """Return `{local_id: (sig, edid)}` for `FO4SFPrewar.esm` suitable for `cross_plugin_check.py`."""
    return {fid: (sig, edid) for edid, (sig, fid) in PREWAR_FORMS.items()}


def beat_summary_rows() -> Iterable[Dict[str, str]]:
    """Yield card-friendly dictionaries for the 5 animation stand-in beats."""
    for b in STANDIN_BEATS:
        yield {
            "code": b.code,
            "name": b.name,
            "label": b.status_label,
            "mechanism": b.mechanism,
            "notes": b.notes,
        }
