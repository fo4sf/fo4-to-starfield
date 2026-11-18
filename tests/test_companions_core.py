"""Unit, balance-doc, math, 3-chokepoint teleport, log-stitching, binary, stage/fold/verify, and installer tests
for JOB 3 Companions, Crew, and Warfare Squads (docs/research/gamma-squad-balance.md + FO4SFCompanions.esm)."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "companions"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))

from ba2_fixture import archive_from_tree  # noqa: E402
import exp_install  # noqa: E402
import make_companions_core as mcc  # noqa: E402
import companions_core_install as cci  # noqa: E402
from fo4sf.companions import core_log  # noqa: E402

RESEARCH_DOC = ROOT / "docs" / "research" / "gamma-squad-balance.md"
PC_CARD_DOC = ROOT / "docs" / "companions" / "companions-warfare-pc-card.md"
CS_PATH = ROOT / "dotnet" / "CompanionsCore" / "Program.cs"
PSC_PATH = ROOT / "scripts" / "companions" / "FO4SF_CompanionsQuest.psc"

RESEARCH_TEXT = RESEARCH_DOC.read_text(encoding="utf-8")
PC_CARD_TEXT = PC_CARD_DOC.read_text(encoding="utf-8")
CS_TEXT = CS_PATH.read_text(encoding="utf-8")
PSC_TEXT = PSC_PATH.read_text(encoding="utf-8")

DOTNET_ENABLED = os.environ.get("FO4SF_DOTNET_TESTS", "") == "1" and shutil.which("dotnet") is not None

PAPYRUS_RESERVED_TYPES = {
    "race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug",
    "utility", "int", "float", "string", "bool", "math", "location", "activator", "message",
    "armor", "weapon", "formlist", "objectreference", "globalvariable", "worldspace", "package",
    "faction", "perk", "miscobject", "actorvalue", "refcollectionalias",
}

BANNED_FALLOUT_MOD_PATTERNS = [
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("Fallout" + r"\s+" + "London") + r"\b", re.I),
    re.compile(r"\b" + ("Tale" + r"\s+of\s+Two\s+" + "Wastelands") + r"\b", re.I),
]
DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")


def cs_const_uints(text):
    return {
        m.group(1): int(m.group(2), 16)
        for m in re.finditer(r"\bconst\s+uint\s+(\w+)\s*=\s*(0x[0-9A-Fa-f]+)\s*;", text)
    }


def parse_tes4_header(plugin_bytes):
    sig, size, flags = struct.unpack_from("<4sII", plugin_bytes, 0)
    assert sig == b"TES4"
    pos, end = 24, 24 + size
    masters = []
    while pos < end:
        sub_sig, sub_len = struct.unpack_from("<4sH", plugin_bytes, pos)
        pos += 6
        payload = plugin_bytes[pos : pos + sub_len]
        pos += sub_len
        if sub_sig == b"MAST":
            masters.append(payload.rstrip(b"\x00").decode("utf-8"))
    return flags, masters


def make_fake_content_resources(zip_path):
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags {\n}\n")
        z.writestr(
            "Scripts/Source/ScriptObject.psc",
            "\n".join(
                [
                    "Scriptname ScriptObject Native",
                    "Function StartTimer(float afInterval, int aiTimerID = 0) native",
                    "Function RegisterForPlayerTeleport() native",
                    "Event OnPlayerTeleport()",
                    "bool Function RegisterForRemoteEvent(ScriptObject akEventSource, string asEventName) native",
                    "Function AddInventoryEventFilter(Form akFilter) native",
                    "Function RemoveAllInventoryEventFilters() native",
                ]
            )
            + "\n",
        )
        z.writestr("Scripts/Source/Form.psc", "Scriptname Form extends ScriptObject Native\nint Function GetFormID() native\n")
        z.writestr(
            "Scripts/Source/Quest.psc",
            "\n".join(
                [
                    "Scriptname Quest extends Form Native",
                    "int Function GetStage()",
                    "bool Function GetStageDone(int aiStage)",
                    "bool Function IsRunning() native",
                ]
            )
            + "\n",
        )
        z.writestr("Scripts/Source/Alias.psc", "Scriptname Alias extends ScriptObject Native\n")
        z.writestr(
            "Scripts/Source/RefCollectionAlias.psc",
            "\n".join(
                [
                    "Scriptname RefCollectionAlias extends Alias Native",
                    "Function AddRef(ObjectReference akNewRef) native",
                    "Function RemoveRef(ObjectReference akRemoveRef) native",
                    "Function RemoveAll() native",
                    "int Function Find(ObjectReference akFindRef) native",
                    "int Function GetCount() native",
                    "Actor Function GetActorAt(int aiIndex)",
                    "Actor[] Function GetActorArray() native",
                    "Event OnActivate(ObjectReference akSenderRef, ObjectReference akActionRef)",
                    "Event OnEnterBleedout(ObjectReference akSenderRef)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/ObjectReference.psc",
            "\n".join(
                [
                    "Scriptname ObjectReference extends Form Native",
                    "Function MoveTo(ObjectReference akTarget, float afX = 0.0, float afY = 0.0, float afZ = 0.0, bool abMatch = true) native",
                    "Function SetLinkedRef(ObjectReference akRef, Keyword akKw = None) native",
                    "bool Function Is3DLoaded() native",
                    "bool Function IsDisabled() native",
                    "bool Function IsDeleted() native",
                    "Function DisableNoWait(bool abFade = false) native",
                    "Function Delete() native",
                    "int Function GetItemCount(Form akItem = None) native",
                    "Function AddItem(Form akItem, int aiCount = 1, bool abSilent = false) native",
                    "int Function RemoveItem(Form akItem, int aiCount = 1, bool abSilent = false, ObjectReference akOther = None) native",
                    "Cell Function GetParentCell() native",
                    "float Function GetDistance(ObjectReference akOther) native",
                    "float Function GetAngleZ() native",
                    "bool Function IsInInterior() native",
                    "Event OnItemRemoved(Form akBaseItem, int aiCount, ObjectReference akItemRef, ObjectReference akDest, int aiReason)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/Actor.psc",
            "\n".join(
                [
                    "Scriptname Actor extends ObjectReference Native",
                    "float Function GetValue(ActorValue akAV) native",
                    "Function SetValue(ActorValue akAV, float afValue) native",
                    "Function RestoreValue(ActorValue akAV, float afAmount) native",
                    "int Function GetLevel() native",
                    "bool Function HasPerk(Perk akPerk) native",
                    "Function AddPerk(Perk akPerk, bool abNotify = false) native",
                    "Function RemovePerk(Perk akPerk) native",
                    "bool Function IsDead() native",
                    "bool Function IsInCombat() native",
                    "Function StopCombat() native",
                    "int Function IsBleedingOut() native",
                    "bool Function IsInFaction(Faction akFaction) native",
                    "Function AddToFaction(Faction akFaction) native",
                    "Function IgnoreFriendlyHits(bool abIgnore = true) native",
                    "bool Function SetRestrained(bool abRestrained = true) native",
                    "Function EvaluatePackage(bool abResetAI = false) native",
                    "Function OpenInventory(bool abForceOpen = false) native",
                    "Event OnPlayerLoadGame()",
                    "Event OnLocationChange(Location akOldLoc, Location akNewLoc)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/SQ_ActorRolesScript.psc",
            "\n".join(
                [
                    "Scriptname SQ_ActorRolesScript extends Quest",
                    "Function SetRoleActive(Actor ActorToUpdate, bool DisplayMessageIfChanged = true, bool AlsoSetAvailable = true)",
                    "Function SetRoleInactive(Actor ActorToUpdate, bool DisplayMessageIfChanged = true, bool AlsoSetUnavailable = false, bool AlsoDisplayUnavailableMessage = true)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/SQ_FollowersScript.psc",
            "\n".join(
                [
                    "Scriptname SQ_FollowersScript extends SQ_ActorRolesScript",
                    "SQ_FollowersScript Function GetScript() global",
                    "Function CommandFollow(Actor Follower)",
                    "Function CommandWait(Actor Follower, ObjectReference WaitAtRef = None)",
                    "Actor[] Function TeleportFollowers(ObjectReference DestinationRef, Actor[] SpecificFollowers = None, bool IncludeFollowing = true, bool IncludeWaiting = true, bool StartFollowing = false, bool StartWaiting = false, bool SkipObj = false)",
                ]
            )
            + "\n",
        )
        z.writestr(
            "Scripts/Source/SQ_Groups_QuestScript.psc",
            "Scriptname SQ_Groups_QuestScript extends Quest\nint Function GetGroupFactionIDValueByActor(Actor ActorToGetGroupFor, bool ValidateActor = true)\n",
        )
        z.writestr("Scripts/Source/ActorValue.psc", "Scriptname ActorValue extends Form Native\n")
        z.writestr("Scripts/Source/GlobalVariable.psc", "Scriptname GlobalVariable extends Form Native\nfloat Function GetValue() native\nFunction SetValue(float v) native\n")
        z.writestr("Scripts/Source/Message.psc", "Scriptname Message extends Form Native\nint Function Show() native\n")
        z.writestr("Scripts/Source/Math.psc", "Scriptname Math Native\nfloat Function Sin(float v) native global\nfloat Function Cos(float v) native global\n")
        z.writestr("Scripts/Source/Game.psc", "Scriptname Game Native\nActor Function GetPlayer() native global\nForm Function GetFormFromFile(int id, string f) native global\nbool Function IsPluginInstalled(string f) native global\n")
        z.writestr("Scripts/Source/Debug.psc", "Scriptname Debug Native\nbool Function OpenUserLog(string s) native global\nbool Function TraceUser(string l, string t, int s = 0) native global\nFunction Notification(string s) native global\n")
        z.writestr("Scripts/Source/Utility.psc", "Scriptname Utility Native\nfloat Function GetCurrentRealTime() native global\n")


def make_fake_compiler(work_dir):
    py_script = Path(work_dir) / "fake_papyrus_compiler.py"
    py_script.write_text(
        "import os, pathlib, sys\n"
        "psc = sys.argv[1]\n"
        "out = [a[3:] for a in sys.argv[2:] if a.startswith('-o=')][0]\n"
        "os.makedirs(out, exist_ok=True)\n"
        "stem = os.path.splitext(os.path.basename(psc))[0]\n"
        "pathlib.Path(out, stem + '.pex').write_bytes(b'FAKAPEX-COMPANIONSCORE')\n"
        "print('Compilation succeeded.')\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        cmd = Path(work_dir) / "fake_compiler.cmd"
        cmd.write_text(f'@"{sys.executable}" "{py_script}" %*\r\n', encoding="utf-8")
        return str(cmd)
    sh = Path(work_dir) / "fake_compiler.sh"
    sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py_script}" "$@"\n', encoding="utf-8")
    sh.chmod(0o755)
    return str(sh)


class GammaBalanceDocAndContractTests(unittest.TestCase):
    def test_gamma_squad_balance_doc_completeness_and_approval_queue(self):
        self.assertTrue(RESEARCH_DOC.is_file())
        self.assertIn("Zero files, archives, scripts, or configuration tables were downloaded", RESEARCH_TEXT)
        self.assertIn("S.T.A.L.K.E.R. Anomaly", RESEARCH_TEXT)
        self.assertIn("GAMMA", RESEARCH_TEXT)
        for required_topic in (
            "Base Cap (`2` Companions)",
            "Earned Maximum (`4` Companions)",
            "Rank-Hierarchy Gate",
            "Faction Goodwill Recruits",
            "Paid Mercenary / Escort Contracts",
            "Mortal Generic Recruits",
            "FO4SF_SquadBaseCap",
            "FO4SF_SquadMaxCap",
            "FO4SF_MercHireCost",
            "FO4SF_MercRewardShare",
        ):
            self.assertIn(required_topic, RESEARCH_TEXT)

        reqs = re.findall(r"^\|\s*`(REQ-GSB-\d{2})`\s*\|.+\|\s*\*\*Awaiting Owner Approval\*\*\s*\|", RESEARCH_TEXT, re.M)
        self.assertGreaterEqual(len(reqs), 3)

    def test_form_ids_properties_stages_and_chokepoints_align(self):
        ids = cs_const_uints(CS_TEXT)
        expected = {
            "SqFollowersQuestId": 0x0000D773,
            "SqGroupsQuestId": 0x001A9565,
            "QuestId": 0x800,
            "SquadBaseCapGlobId": 0x801,
            "SquadMaxCapGlobId": 0x802,
            "MercHireCostGlobId": 0x803,
            "MercRewardShareGlobId": 0x804,
            "ActiveSquadCountGlobId": 0x805,
            "SquadStanceGlobId": 0x806,
            "CompanionAffinityAvifId": 0x807,
            "SquadLoyaltyAvifId": 0x808,
            "RecruitRankTierAvifId": 0x809,
            "SquadOrderStateAvifId": 0x80A,
            "CompanionNerveBonusAvifId": 0x80B,
            "PerkUnitedWeStandId": 0x810,
            "PerkRobotSympathyId": 0x811,
            "PerkSquadCommanderId": 0x812,
            "PerkLoneWandererSoloId": 0x813,
            "CompanionWheelMsgId": 0x815,
            "FireteamCommandMsgId": 0x816,
            "RecruitPromptMsgId": 0x817,
            "SquadAllyFactionId": 0x818,
            "SquadRadioTokenId": 0x820,
            "SquadTestCellId": 0x830,
            "FireteamAlphaNpcId": 0x831,
            "FireteamDeltaNpcId": 0x834,
            "FireteamAlphaRefId": 0x835,
            "FireteamDeltaRefId": 0x838,
            "StoryCompanionNpcId": 0x839,
            "StoryCompanionRefId": 0x83A,
        }
        for k, v in expected.items():
            self.assertEqual(ids.get(k), v, k)

        psc_props = re.findall(r"^\s*[A-Za-z0-9_\[\]]+\s+Property\s+(\w+)\s+Auto\b", PSC_TEXT, re.M)
        cs_props = re.findall(r'ObjProp\("(\w+)"', CS_TEXT) + re.findall(r'ScriptObjectListProperty\s*\{\s*Name\s*=\s*"(\w+)"', CS_TEXT)
        cs_props = [p for p in cs_props if p]
        self.assertEqual(len(psc_props), 26)
        self.assertEqual(sorted(psc_props), sorted(cs_props))
        self.assertEqual(mcc.PLUGIN_MASTERS, ("Starfield.esm", "FO4SFCoreValues.esm"))
        self.assertEqual(mcc.SHARED_CORE_FORM_IDS, {"CharismaAV": 0x000813, "TestModeGlobal": 0x000860})
        self.assertNotIn("RepGoodwillGlobId", PSC_TEXT)
        self.assertNotIn("ProgChaAvId", PSC_TEXT)
        self.assertIn("akMember.RestoreValue(healthAv, 50.0)", PSC_TEXT)
        self.assertIn("TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0", PSC_TEXT)

        for cp in core_log.TELEPORT_CHOKEPOINTS:
            self.assertIn(f'"{cp}"', PSC_TEXT)
            self.assertIn(cp, PC_CARD_TEXT)

        self.assertIn("FO4SF_Throwaway_CompanionsSquad_DeleteMe", PC_CARD_TEXT)
        self.assertIn("Delete `FO4SF_Throwaway_CompanionsSquad_DeleteMe`", PC_CARD_TEXT)

    def test_no_papyrus_variable_shadows_reserved_type_and_zero_redaction_hits(self):
        decls = [
            m.group(1)
            for ln in PSC_TEXT.splitlines()
            if " Property " not in ln
            for m in [re.match(r"^\s*(?:[A-Za-z0-9_]+(?:\[\])?)\s+([A-Za-z0-9_]+)\s*(?:=|$)", ln)]
            if m
        ]
        params = [
            p
            for sig in re.findall(r"(?:Function|Event)\s+[A-Za-z0-9_.]+\(([^)]*)\)", PSC_TEXT)
            for p in re.findall(r"\s([A-Za-z0-9_]+)\s*(?:,|=|$)", " " + sig)
        ]
        bad = [n for n in decls + params if n.lower() in PAPYRUS_RESERVED_TYPES]
        self.assertEqual(bad, [])

        checked_files = [
            RESEARCH_DOC,
            PC_CARD_DOC,
            CS_PATH,
            ROOT / "dotnet" / "CompanionsCore" / "CompanionsCore.csproj",
            PSC_PATH,
            ROOT / "scripts" / "companions" / "make_companions_core.py",
            ROOT / "scripts" / "companions" / "companions_core_install.py",
            ROOT / "src" / "fo4sf" / "companions" / "core_log.py",
            Path(__file__),
        ]
        for p in checked_files:
            txt = p.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"PC drive path found in {p.name}")
            for rx in BANNED_FALLOUT_MOD_PATTERNS:
                self.assertIsNone(rx.search(txt), f"banned Fallout mod name matched {rx.pattern} in {p.name}")


class BalanceMathAndLogEvaluatorTests(unittest.TestCase):
    def test_cap_rank_gate_merc_payout_nerve_and_affinity_math(self):
        self.assertEqual(core_log.effective_squad_cap(2, 4, charisma=5.0), 2)
        self.assertEqual(core_log.effective_squad_cap(2, 4, charisma=8.0), 4)
        self.assertEqual(core_log.effective_squad_cap(2, 4, charisma=4.0, has_squad_commander=True), 4)
        self.assertEqual(core_log.effective_squad_cap(2, 4, charisma=4.0, has_leadership_background=True), 4)
        self.assertEqual(core_log.effective_squad_cap(2, 4, charisma=10.0, has_solo_lone_wanderer=True), 0)

        self.assertEqual(core_log.player_rank_tier(1), 0)
        self.assertEqual(core_log.player_rank_tier(12), 2)
        self.assertEqual(core_log.player_rank_tier(3, has_squad_commander=True), 4)

        self.assertEqual(core_log.can_recruit_gate(2, 2, 0, 1), (False, "cap_reached", 0))
        self.assertEqual(core_log.can_recruit_gate(1, 2, 3, 1), (False, "rank_too_high", 0))
        self.assertEqual(core_log.can_recruit_gate(1, 2, 0, 1, loyalty=15.0), (False, "low_loyalty", 0))
        self.assertEqual(
            core_log.can_recruit_gate(1, 2, 0, 1, merc_contract=True, has_goodwill=False, player_credits=100, merc_hire_cost=250),
            (False, "insufficient_credits", 0),
        )
        self.assertEqual(
            core_log.can_recruit_gate(1, 2, 0, 1, merc_contract=True, has_goodwill=False, player_credits=500, merc_hire_cost=250),
            (True, "hired_merc", 250),
        )
        self.assertEqual(
            core_log.can_recruit_gate(1, 2, 0, 1, merc_contract=True, has_goodwill=True, player_credits=0, merc_hire_cost=250),
            (True, "recruited_goodwill", 0),
        )

        self.assertEqual(core_log.net_contract_payout(1000, active_mercs=0, share_per_merc=0.15), 1000)
        self.assertEqual(core_log.net_contract_payout(1000, active_mercs=2, share_per_merc=0.15), 700)
        self.assertEqual(core_log.net_contract_payout(1000, active_mercs=4, share_per_merc=0.15), 400)
        self.assertEqual(core_log.net_contract_payout(1000, active_mercs=6, share_per_merc=0.15), 400)

        self.assertEqual(core_log.companion_nerve_pct(5.0, False), 0.0)
        self.assertEqual(core_log.companion_nerve_pct(8.0, True), 20.0)
        self.assertEqual(core_log.affinity_tier(249.0), "neutral")
        self.assertEqual(core_log.affinity_tier(500.0), "trusted")
        self.assertEqual(core_log.affinity_tier(1000.0), "idolized")

    def test_rotated_log_stitching_evaluates_4npc_fireteam_and_3_teleport_chokepoints(self):
        pre_reload = [
            "[22:10:01] FO4SFCOMP rt=2.0 init version=1 quest=167774208 installed=true sq_followers=55155 sq_groups=1742181 base_cap=2 max_cap=4 merc_cost=250 merc_share=0.15 fireteam_refs=4 end=true\n",
            "[22:10:03] FO4SFCOMP rt=4.0 recruit_refused actor=167774264 reason=rank_too_high candidate_tier=4 player_tier=0 end=true\n",
            "[22:10:04] FO4SFCOMP rt=5.0 recruited actor=167774261 slot=1/2 merc=false cost=0 rank_tier=0 loyalty=75.0 sq_followers=true group_id=-1 end=true\n",
            "[22:10:05] FO4SFCOMP rt=6.0 recruited actor=167774262 slot=2/2 merc=true cost=250 rank_tier=0 loyalty=75.0 sq_followers=true group_id=-1 end=true\n",
            "[22:10:06] FO4SFCOMP rt=7.0 recruit_refused actor=167774263 reason=cap_reached active=2 cap=2 end=true\n",
            "[22:10:06] FO4SFCOMP rt=7.1 stage_result stage=10 cap=2 active=2 r1=true r2=true third_blocked=true rank_blocked=true pass=true end=true\n",
            "[22:10:09] FO4SFCOMP rt=10.0 recruited actor=167774263 slot=3/4 merc=false cost=0 rank_tier=0 loyalty=75.0 sq_followers=true group_id=-1 end=true\n",
            "[22:10:10] FO4SFCOMP rt=11.0 recruited actor=167774264 slot=4/4 merc=false cost=0 rank_tier=0 loyalty=75.0 sq_followers=true group_id=-1 end=true\n",
            "[22:10:11] FO4SFCOMP rt=12.0 fireteam_cmd cmd=all_wait count=4 source=stage20 end=true\n",
            "[22:10:12] FO4SFCOMP rt=13.0 fireteam_cmd cmd=all_follow count=4 source=stage20 end=true\n",
            "[22:10:13] FO4SFCOMP rt=14.0 fireteam_cmd cmd=stance stance=aggressive code=1 count=4 source=stage20 end=true\n",
            "[22:10:14] FO4SFCOMP rt=15.0 fireteam_cmd cmd=stance stance=hold_fire code=2 count=4 source=stage20 end=true\n",
            "[22:10:15] FO4SFCOMP rt=16.0 fireteam_cmd cmd=stance stance=defensive code=0 count=4 source=stage20 end=true\n",
            "[22:10:16] FO4SFCOMP rt=17.0 fireteam_cmd cmd=inspect_all count=4 cap=4 source=stage20 end=true\n",
            "[22:10:20] FO4SFCOMP rt=21.0 teleport reason=load_door_cell_change moved=3 skipped_waiting=1 active=4 cell=100 interior=true end=true\n",
            "[22:10:21] FO4SFCOMP rt=22.0 teleport reason=vault_lift_or_interior_exit moved=3 skipped_waiting=1 active=4 cell=101 interior=false end=true\n",
            "[22:10:22] FO4SFCOMP rt=23.0 teleport reason=pipboy_fast_travel moved=3 skipped_waiting=1 active=4 cell=102 interior=false end=true\n",
            "[22:10:25] FO4SFCOMP rt=26.0 affinity actor=167774266 before=750.0 after=1000.0 tier=idolized perk_granted=true reason=stage40_idolized end=true\n",
            "[22:10:26] FO4SFCOMP rt=27.0 contract_payout gross=1000 active_mercs=1 merc_cut=150 player_net=850 end=true\n",
            "[22:10:27] FO4SFCOMP rt=28.0 loyalty actor=167774261 before=75.0 after=60.0 deserted=false reason=stage40_friendly_fire end=true\n",
        ]
        post_reload = [
            "[22:12:02] FO4SFCOMP rt=3.0 reload_audit when=reload reload_count=1 squad_ok=4/4 following=4 waiting=0 stance=0 united_perk=true pass=true end=true\n",
            "[22:12:08] FO4SFCOMP rt=9.0 reload_audit when=stage50 reload_count=1 squad_ok=4/4 following=4 waiting=0 stance=0 united_perk=true pass=true end=true\n",
            "[22:12:12] FO4SFCOMP rt=13.0 cleanup active=0 pass=true end=true\n",
        ]
        with tempfile.TemporaryDirectory(prefix="comp-log-") as tmp:
            log0 = Path(tmp) / "FO4SFCompanions.0.log"
            log1 = Path(tmp) / "FO4SFCompanions.1.log"
            log1.write_text("".join(pre_reload), encoding="utf-8")
            log0.write_text("".join(post_reload), encoding="utf-8")

            stitched = core_log.load_session_lines(str(log0), include_rotated=True)
            s = core_log.summarize(stitched)
            self.assertTrue(s["passed"])
            for k, ok in s["checks"].items():
                self.assertTrue(ok, k)
            rep = "\n".join(core_log.report(s))
            self.assertIn("PASS fireteam_4npc_commands", rep)
            self.assertIn("PASS teleport_3_chokepoints", rep)
            self.assertIn("VERDICT: PASS", rep)

            # Negative check: dropping pipboy_fast_travel fails teleport_3_chokepoints
            without_ft = [ln for ln in stitched if "pipboy_fast_travel" not in ln]
            s_bad = core_log.summarize(without_ft)
            self.assertFalse(s_bad["checks"]["teleport_3_chokepoints"])
            self.assertFalse(s_bad["passed"])

            self.assertEqual(mcc.main(["console", "--file", str(log0)]), 0)


class StageFoldVerifyAndDotnetTests(unittest.TestCase):
    def test_precheck_detects_missing_sq_followers_method(self):
        with tempfile.TemporaryDirectory(prefix="comp-pre-") as tmp:
            cr = Path(tmp) / "ContentResources.zip"
            make_fake_content_resources(cr)
            sources = mcc.read_sources(str(cr))
            self.assertEqual(mcc.precheck_sources(sources)["missing"], [])

            sources["sq_followersscript"] = "Scriptname SQ_FollowersScript extends SQ_ActorRolesScript\n"
            bad = mcc.precheck_sources(sources)
            self.assertIn("SQ_FollowersScript.TeleportFollowers", bad["missing"])

    @unittest.skipUnless(DOTNET_ENABLED, "requires FO4SF_DOTNET_TESTS=1 and dotnet")
    def test_dotnet_selftest_binary_header_stage_hardlink_fold_and_ridealong_install(self):
        with tempfile.TemporaryDirectory(prefix="comp-e2e-") as tmp:
            tmp_path = Path(tmp)

            # 1. CompanionsCore selftest (full + minimal + options + 7 tamper controls)
            selftest_dir = tmp_path / "selftest"
            r = subprocess.run(
                ["dotnet", "run", "-c", "Release", "--project", str(ROOT / "dotnet" / "CompanionsCore"), "--", "selftest", str(selftest_dir)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest: ok", r.stdout)

            # 2. Raw binary TES4 header & GRUP checks (both full and --no-test-cell)
            plugin_bytes = (selftest_dir / "b_full" / "FO4SFCompanions.esm").read_bytes()
            flags, masters = parse_tes4_header(plugin_bytes)
            self.assertTrue(flags & 0x01, "TES4 Master flag 0x01 not set")
            self.assertEqual(masters, ["Starfield.esm", "FO4SFCoreValues.esm"])
            for sig in (b"QUST", b"GLOB", b"AVIF", b"PERK", b"MESG", b"FACT", b"MISC", b"FLST", b"CELL", b"NPC_"):
                self.assertIn(sig, plugin_bytes)

            player_bytes = (selftest_dir / "b_player" / "FO4SFCompanions.esm").read_bytes()
            _, player_masters = parse_tes4_header(player_bytes)
            self.assertEqual(player_masters, ["Starfield.esm", "FO4SFCoreValues.esm"])
            self.assertNotIn(b"FO4SF_SquadTestCell", player_bytes)
            self.assertNotIn(b"FO4SF_Fireteam_Alpha", player_bytes)

            # 3. Stage + verify + hardlink fold
            sf_esm = selftest_dir / "m_full" / "Starfield.esm"
            cr_zip = tmp_path / "ContentResources.zip"
            make_fake_content_resources(cr_zip)
            fake_comp = make_fake_compiler(tmp_path)
            stage_dir = tmp_path / "stage_out"

            self.assertEqual(
                mcc.main(
                    [
                        "stage",
                        "--out",
                        str(stage_dir),
                        "--starfield",
                        str(sf_esm),
                        "--compiler",
                        fake_comp,
                        "--content-resources",
                        str(cr_zip),
                    ]
                ),
                0,
            )
            self.assertEqual(
                mcc.main(["verify", "--exp-dir", str(stage_dir), "--plan", str(stage_dir / "plan.json"), "--starfield", str(sf_esm)]),
                0,
            )
            self.assertEqual(
                mcc.main(["verify", "--exp-dir", str(stage_dir), "--plan", str(stage_dir / "plan.json"), "--no-test-cell"]),
                1,
            )

            stage_player = tmp_path / "stage_player"
            self.assertEqual(
                mcc.main(
                    [
                        "stage",
                        "--out",
                        str(stage_player),
                        "--starfield",
                        str(sf_esm),
                        "--compiler",
                        fake_comp,
                        "--content-resources",
                        str(cr_zip),
                        "--no-test-cell",
                    ]
                ),
                0,
            )
            self.assertEqual(
                mcc.main(["verify", "--exp-dir", str(stage_player), "--plan", str(stage_player / "plan.json"), "--starfield", str(sf_esm), "--no-test-cell"]),
                0,
            )

            core_dir = tmp_path / "clean_core"
            (core_dir / "Data" / "Scripts").mkdir(parents=True)
            (core_dir / "FO4TerrainCore.esm").write_bytes(b"CORE-ESM")
            (core_dir / "README.txt").write_text(
                "Core set.\n  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins FO4TerrainCore.esm --pack\n",
                encoding="utf-8",
            )
            before_sha = hashlib.sha256((core_dir / "README.txt").read_bytes()).hexdigest()

            folded_dir = tmp_path / "folded_core"
            self.assertEqual(
                mcc.main(
                    [
                        "fold",
                        "--stage",
                        str(stage_dir),
                        "--core-dir",
                        str(core_dir),
                        "--out",
                        str(folded_dir),
                        "--starfield",
                        str(sf_esm),
                        "--hardlink",
                    ]
                ),
                0,
            )
            self.assertEqual(before_sha, hashlib.sha256((core_dir / "README.txt").read_bytes()).hexdigest())
            self.assertIn("FO4TerrainCore.esm,FO4SFCompanions.esm", (folded_dir / "README.txt").read_text(encoding="utf-8"))

            # 4. Ride-along installer check in isolated LOCALAPPDATA
            game_dir = tmp_path / "fake_game"
            (game_dir / "Data").mkdir(parents=True)
            (game_dir / "Starfield.exe").write_bytes(b"MZ")
            shutil.copy2(sf_esm, game_dir / "Data" / "Starfield.esm")
            existing_exp = game_dir / "Data" / "FO4SFExp.install.json"
            existing_exp.write_text('{"keep": true}\n', encoding="utf-8")
            local_dir = tmp_path / "localappdata"
            (local_dir / "Starfield").mkdir(parents=True)
            plugins_txt = local_dir / "Starfield" / "Plugins.txt"
            plugins_txt.write_text("# header\r\n*FO4TerrainCore.esm\r\n*FO4SFCoreValues.esm\r\n", encoding="utf-8")

            old_local = os.environ.get("LOCALAPPDATA")
            old_build = exp_install.build_ba2

            def stub_build(args_ns, root_dir, out_ba2):
                Path(out_ba2).write_bytes(archive_from_tree(Path(root_dir)))
                return out_ba2

            def run_cci(*argv):
                try:
                    return cci.main(list(argv)) or 0
                except SystemExit as exc:
                    return exc.code if isinstance(exc.code, int) else 1

            os.environ["LOCALAPPDATA"] = str(local_dir)
            exp_install.build_ba2 = stub_build
            try:
                self.assertEqual(run_cci("install", "--dir", str(stage_dir), "--starfield", str(game_dir)), 0)
                self.assertTrue((game_dir / "Data" / "FO4SFCompanions.install.json").is_file())
                self.assertTrue((game_dir / "Data" / "FO4SFCompanions.esm").is_file())
                self.assertTrue((game_dir / "Data" / "FO4SFCompanions - Main.ba2").is_file())
                self.assertEqual(existing_exp.read_text(encoding="utf-8"), '{"keep": true}\n')
                self.assertEqual(run_cci("active", "--starfield", str(game_dir)), 0)
                self.assertEqual(run_cci("uninstall", "--starfield", str(game_dir)), 0)
                self.assertFalse((game_dir / "Data" / "FO4SFCompanions.esm").exists())
                self.assertEqual(existing_exp.read_text(encoding="utf-8"), '{"keep": true}\n')
            finally:
                exp_install.build_ba2 = old_build
                if old_local is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    unittest.main()
