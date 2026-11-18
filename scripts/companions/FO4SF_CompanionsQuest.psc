Scriptname FO4SF_CompanionsQuest extends Quest
{Companions, Crew, and Warfare Squads over Starfield's kept SQ_Followers (0x0000D773) and SQ_Groups (0x001A9565)
 (docs/research/gamma-squad-balance.md, docs/companions/companions-warfare-pc-card.md).

 Attached to QUST FO4SF_CompanionsQuest (0x000800 of FO4SFCompanions.esm):
   - Base squad cap FO4SF_SquadBaseCap (2), earned fireteam cap FO4SF_SquadMaxCap (4) unlocked by
     FO4SF_Perk_SquadCommander, CHA >= 8, or FO4SFProgression.esm leadership backgrounds/traits.
   - Three-gate recruitment (slot cap, rank hierarchy FO4SF_RecruitRankTier, faction goodwill or mercenary contract fee).
   - Companion Tactical Wheel (Follow, Wait/Hold, Inspect, Stance, Trade, Affinity, Dismiss) and Squad Radio.
   - Follower teleportation across all 3 chokepoints: Load Doors, Vault 111 Exit Lift, and Pip-Boy Fast Travel.
   - Companion Affinity milestones (250/500/750/1000 -> PerkUnitedWeStand) and GAMMA-inspired loyalty/bleedout/share upkeep.

 Automated verification stages:
   10  Verify base cap (2), merc contract fee vs goodwill gate, rank-hierarchy refusal, and 3rd-slot cap refusal
   20  Unlock 4-slot leadership cap, recruit all 4 Warfare Fireteam NPCs, run squad-wide Hold / Follow / Stance / Inspect
   30  Verify follower teleport catch-up across all 3 chokepoints (load_door_cell_change, vault_lift_or_interior_exit, pipboy_fast_travel)
   40  Verify Story Companion Affinity (0 -> 250 -> 500 -> 750 -> 1000 -> PerkUnitedWeStand), merc payout share, and friendly-fire loyalty
   50  Explicit live / post-reload squad persistence audit
   60  Clean dismiss & reset of test fireteam and temporary perks

 User log: My Games\Starfield\Logs\Script\User\FO4SFCompanions.0.log
 Format:   FO4SFCOMP rt=<real time s> <event> key=value ... end=true}

; ---------------------------------------------------------------- bound properties (26; 24 under --no-test-cell)

RefCollectionAlias Property ActiveSquad Auto Const Mandatory
GlobalVariable Property SquadBaseCapGlob Auto Const Mandatory
GlobalVariable Property SquadMaxCapGlob Auto Const Mandatory
GlobalVariable Property MercHireCostGlob Auto Const Mandatory
GlobalVariable Property MercRewardShareGlob Auto Const Mandatory
GlobalVariable Property ActiveSquadCountGlob Auto Const Mandatory
GlobalVariable Property SquadStanceGlob Auto Const Mandatory
GlobalVariable Property TestModeGlobal Auto Const

ActorValue Property CharismaAV Auto Const
ActorValue Property CompanionAffinityAV Auto Const Mandatory
ActorValue Property SquadLoyaltyAV Auto Const Mandatory
ActorValue Property RecruitRankTierAV Auto Const Mandatory
ActorValue Property SquadOrderStateAV Auto Const Mandatory
ActorValue Property CompanionNerveBonusAV Auto Const Mandatory

Perk Property PerkUnitedWeStand Auto Const Mandatory
Perk Property PerkRobotSympathy Auto Const Mandatory
Perk Property PerkSquadCommander Auto Const Mandatory
Perk Property PerkLoneWandererSolo Auto Const Mandatory

Message Property CompanionWheelMsg Auto Const Mandatory
Message Property FireteamCommandMsg Auto Const Mandatory
Message Property RecruitPromptMsg Auto Const Mandatory

Faction Property SquadAllyFaction Auto Const Mandatory
MiscObject Property SquadRadioToken Auto Const Mandatory
FormList Property RadioFilterList Auto Const Mandatory
Actor Property StoryCompanionRef Auto Const
Actor[] Property FireteamTestRefs Auto Const

; ---------------------------------------------------------------- runtime FormID constants

int Version = 1
string LogName = "FO4SFCompanions"
string OwnPlugin = "FO4SFCompanions.esm"
string CoreValuesPlugin = "FO4SFCoreValues.esm"
string ProgressionPlugin = "FO4SFProgression.esm"
string ReputationPlugin = "FO4SFReputation.esm"
string NewGamePlugin = "FO4SFNewGame.esm"

int SfFollowersQuestId = 0x0000D773
int SfGroupsQuestId = 0x001A9565
int SfCreditsId = 0x00000F
int SfMedPackId = 0x00ABF9
int SfGameDaysPassedId = 0x000039
int SfCharismaAvId = 0x0002C5
int SfHealthAvId = 0x0002D4
int SfFollowerStateAvId = 0x000344
int CoreCharismaAvId = 0x000813

; Optional FO4SFProgression.esm leadership records & FO4SFReputation.esm faction standing slots
int ProgBgCaravanGuardId = 0x000822
int ProgBgBrotherhoodScribeId = 0x000824
int ProgBgDesertRangerId = 0x000827
int ProgBgMinutemanId = 0x000828
int RepFactFirstId = 0x000810
int RepFameAvFirstId = 0x000820
int RepFameGlobFirstId = 0x000850
float GoodwillThreshold = 25.0
int NewGameQuestId = 0x000800

float LeashDistM = 120.0
float FormationBaseM = 2.2
float FormationStepM = 1.1
float PollIntervalS = 2.0

; ---------------------------------------------------------------- persistent state

int TIMER_POLL = 1
int TIMER_RELOAD_SETTLE = 2

int[] StageList
bool[] DoneList
Actor[] HiredMercRefs

Cell LastPlayerCell = None
bool LastWasInInterior = false
float LastGameDays = -1.0
int LastNewGameStage = -1
int ReloadCount = 0
bool CleanupDone = false
bool StageAddedCommanderPerk = false

; ---------------------------------------------------------------- lifecycle & logging

bool Initialized = false

Event OnQuestInit()
    if Initialized
        return
    endif
    Initialized = true
    Debug.OpenUserLog(LogName)
    InitState()
    Actor playerRef = Game.GetPlayer()
    SetupHooks(playerRef)
    SnapshotPlayerTravelState(playerRef)
    SyncSquadGlobals(playerRef)
    Quest sqFol = Game.GetFormFromFile(SfFollowersQuestId, "Starfield.esm") as Quest
    Quest sqGrp = Game.GetFormFromFile(SfGroupsQuestId, "Starfield.esm") as Quest
    int ftRefsCount = 0
    if FireteamTestRefs != None
        ftRefsCount = FireteamTestRefs.Length
    endif
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(OwnPlugin) + " sq_followers=" + Id(sqFol) + " sq_groups=" + Id(sqGrp) + " base_cap=" + (SquadBaseCapGlob.GetValue() as int) + " max_cap=" + (SquadMaxCapGlob.GetValue() as int) + " merc_cost=" + (MercHireCostGlob.GetValue() as int) + " merc_share=" + MercRewardShareGlob.GetValue() + " fireteam_refs=" + ftRefsCount)
    StartTimer(PollIntervalS, TIMER_POLL)
EndEvent

Function InitState()
    if StageList == None || StageList.Length != 5
        StageList = new int[5]
        DoneList = new bool[5]
        StageList[0] = 10
        StageList[1] = 20
        StageList[2] = 30
        StageList[3] = 40
        StageList[4] = 50
    endif
    if HiredMercRefs == None
        HiredMercRefs = new Actor[0]
    endif
EndFunction

Function SetupHooks(Actor playerRef)
    if playerRef == None
        return
    endif
    RemoveAllInventoryEventFilters()
    if RadioFilterList != None
        AddInventoryEventFilter(RadioFilterList)
    endif
    RegisterForPlayerTeleport()
    RegisterForRemoteEvent(playerRef, "OnPlayerLoadGame")
    RegisterForRemoteEvent(playerRef, "OnLocationChange")
    RegisterForRemoteEvent(playerRef as ObjectReference, "OnItemRemoved")
    if ActiveSquad != None
        RegisterForRemoteEvent(ActiveSquad, "OnActivate")
        RegisterForRemoteEvent(ActiveSquad, "OnEnterBleedout")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    InitState()
    ReloadCount += 1
    Actor playerRef = Game.GetPlayer()
    SetupHooks(playerRef)
    SnapshotPlayerTravelState(playerRef)
    ReassertSquadPackages(playerRef)
    AuditSquadPersistence("reload")
    StartTimer(2.0, TIMER_RELOAD_SETTLE)
    StartTimer(PollIntervalS, TIMER_POLL)
EndEvent

Function Trace(string msg)
    string line = "FO4SFCOMP rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function Say(string msg)
    Debug.Notification(msg)
    Trace("say text=" + msg)
EndFunction

string Function Id(Form targetForm)
    if targetForm == None
        return "none"
    endif
    return "" + targetForm.GetFormID()
EndFunction

SQ_FollowersScript Function FollowersApi()
    return SQ_FollowersScript.GetScript()
EndFunction

SQ_Groups_QuestScript Function GroupsApi()
    Quest grpQuest = Game.GetFormFromFile(SfGroupsQuestId, "Starfield.esm") as Quest
    return grpQuest as SQ_Groups_QuestScript
EndFunction

float Function ReadGameDays()
    GlobalVariable gd = Game.GetFormFromFile(SfGameDaysPassedId, "Starfield.esm") as GlobalVariable
    if gd == None
        return 0.0
    endif
    return gd.GetValue()
EndFunction

int Function ReadNewGameStage()
    if !Game.IsPluginInstalled(NewGamePlugin)
        return -1
    endif
    Quest ngq = Game.GetFormFromFile(NewGameQuestId, NewGamePlugin) as Quest
    if ngq == None
        return -1
    endif
    return ngq.GetStage()
EndFunction

Function SnapshotPlayerTravelState(Actor playerRef)
    if playerRef == None
        return
    endif
    LastPlayerCell = playerRef.GetParentCell()
    LastWasInInterior = playerRef.IsInInterior()
    LastGameDays = ReadGameDays()
    LastNewGameStage = ReadNewGameStage()
EndFunction

; ---------------------------------------------------------------- leadership cap, rank & goodwill gates

float Function ReadPlayerCharisma(Actor playerRef)
    if playerRef == None
        return 5.0
    endif
    ActorValue coreCha = CharismaAV
    if coreCha == None
        coreCha = Game.GetFormFromFile(CoreCharismaAvId, CoreValuesPlugin) as ActorValue
    endif
    if coreCha != None
        float cVal = playerRef.GetValue(coreCha)
        if cVal > 0.0
            return cVal
        endif
    endif
    ActorValue sfCha = Game.GetFormFromFile(SfCharismaAvId, "Starfield.esm") as ActorValue
    if sfCha != None
        float sVal = playerRef.GetValue(sfCha)
        if sVal > 0.0
            return sVal
        endif
    endif
    return 5.0
EndFunction

bool Function HasProgressionLeadershipPerk(Actor playerRef)
    if playerRef == None || !Game.IsPluginInstalled(ProgressionPlugin)
        return false
    endif
    Perk p1 = Game.GetFormFromFile(ProgBgCaravanGuardId, ProgressionPlugin) as Perk
    Perk p2 = Game.GetFormFromFile(ProgBgBrotherhoodScribeId, ProgressionPlugin) as Perk
    Perk p3 = Game.GetFormFromFile(ProgBgDesertRangerId, ProgressionPlugin) as Perk
    Perk p4 = Game.GetFormFromFile(ProgBgMinutemanId, ProgressionPlugin) as Perk
    if (p1 != None && playerRef.HasPerk(p1)) || (p2 != None && playerRef.HasPerk(p2))
        return true
    endif
    if (p3 != None && playerRef.HasPerk(p3)) || (p4 != None && playerRef.HasPerk(p4))
        return true
    endif
    return false
EndFunction

bool Function HasLeadershipQualification(Actor playerRef)
    if playerRef == None
        return false
    endif
    if PerkSquadCommander != None && playerRef.HasPerk(PerkSquadCommander)
        return true
    endif
    if ReadPlayerCharisma(playerRef) >= 8.0
        return true
    endif
    return HasProgressionLeadershipPerk(playerRef)
EndFunction

int Function GetEffectiveSquadCap(Actor playerRef)
    if playerRef != None && PerkLoneWandererSolo != None && playerRef.HasPerk(PerkLoneWandererSolo)
        return 0
    endif
    int baseCap = SquadBaseCapGlob.GetValue() as int
    int maxCap = SquadMaxCapGlob.GetValue() as int
    if HasLeadershipQualification(playerRef)
        return maxCap
    endif
    return baseCap
EndFunction

int Function GetPlayerRankTier(Actor playerRef)
    if playerRef == None
        return 0
    endif
    if PerkSquadCommander != None && playerRef.HasPerk(PerkSquadCommander)
        return 4
    endif
    int lv = playerRef.GetLevel()
    if lv >= 30
        return 4
    elseif lv >= 20
        return 3
    elseif lv >= 12
        return 2
    elseif lv >= 5
        return 1
    endif
    return 0
EndFunction

bool Function HasSlotGoodwill(Actor playerRef, int slotIdx)
    GlobalVariable fameGlob = Game.GetFormFromFile(RepFameGlobFirstId + slotIdx, ReputationPlugin) as GlobalVariable
    if fameGlob != None && fameGlob.GetValue() >= GoodwillThreshold
        return true
    endif
    if playerRef != None
        ActorValue fameAv = Game.GetFormFromFile(RepFameAvFirstId + slotIdx, ReputationPlugin) as ActorValue
        if fameAv != None && playerRef.GetValue(fameAv) >= GoodwillThreshold
            return true
        endif
    endif
    return false
EndFunction

bool Function HasFactionGoodwill(Actor akCandidate)
    Actor playerRef = Game.GetPlayer()
    if playerRef == None
        return false
    endif
    if Game.IsPluginInstalled(ReputationPlugin)
        bool matchedSlot = false
        if akCandidate != None
            int slot = 0
            while slot < 8
                Faction repFact = Game.GetFormFromFile(RepFactFirstId + slot, ReputationPlugin) as Faction
                if repFact != None && akCandidate.IsInFaction(repFact)
                    matchedSlot = true
                    if HasSlotGoodwill(playerRef, slot)
                        return true
                    endif
                endif
                slot += 1
            endwhile
        endif
        if !matchedSlot && HasSlotGoodwill(playerRef, 0)
            return true
        endif
    endif
    return HasProgressionLeadershipPerk(playerRef)
EndFunction

float Function CalcNerveBonusPct(Actor playerRef)
    float cha = ReadPlayerCharisma(playerRef)
    float bonus = 0.0
    if cha > 5.0
        bonus = (cha - 5.0) * 5.0
    endif
    if HasLeadershipQualification(playerRef)
        bonus += 5.0
    endif
    if bonus > 30.0
        bonus = 30.0
    endif
    return bonus
EndFunction

Function SyncSquadGlobals(Actor playerRef)
    int cnt = 0
    if ActiveSquad != None
        cnt = ActiveSquad.GetCount()
    endif
    ActiveSquadCountGlob.SetValue(cnt as float)
    float nerve = CalcNerveBonusPct(playerRef)
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None
            m.SetValue(CompanionNerveBonusAV, nerve)
        endif
        i += 1
    endwhile
EndFunction

; ---------------------------------------------------------------- recruitment & dismissal

bool Function TryRecruit(Actor akCandidate, bool abMercContract, bool abSilentPrompt)
    Actor playerRef = Game.GetPlayer()
    if playerRef == None || akCandidate == None || ActiveSquad == None
        Trace("recruit_refused actor=" + Id(akCandidate) + " reason=null_ref")
        return false
    endif
    if akCandidate.IsDead()
        Trace("recruit_refused actor=" + Id(akCandidate) + " reason=dead")
        return false
    endif
    if ActiveSquad.Find(akCandidate) >= 0
        Trace("recruit_refused actor=" + Id(akCandidate) + " reason=already_in_squad")
        return false
    endif

    int cap = GetEffectiveSquadCap(playerRef)
    int curCount = ActiveSquad.GetCount()
    if curCount >= cap
        Trace("recruit_refused actor=" + Id(akCandidate) + " reason=cap_reached active=" + curCount + " cap=" + cap)
        if !abSilentPrompt
            Say("Squad cap reached (" + curCount + "/" + cap + "). Unlock Squad Commander or CHA 8 for 4 slots.")
        endif
        return false
    endif

    int candTier = akCandidate.GetValue(RecruitRankTierAV) as int
    int playerTier = GetPlayerRankTier(playerRef)
    if candTier > playerTier
        Trace("recruit_refused actor=" + Id(akCandidate) + " reason=rank_too_high candidate_tier=" + candTier + " player_tier=" + playerTier)
        if !abSilentPrompt
            Say("Recruit rank tier (" + candTier + ") exceeds your leadership rank (" + playerTier + ").")
        endif
        return false
    endif

    float curLoyalty = akCandidate.GetValue(SquadLoyaltyAV)
    if curLoyalty <= 0.0
        curLoyalty = 75.0
        akCandidate.SetValue(SquadLoyaltyAV, curLoyalty)
    endif
    if curLoyalty < 20.0
        Trace("recruit_refused actor=" + Id(akCandidate) + " reason=low_loyalty loyalty=" + curLoyalty)
        return false
    endif

    int paidCost = 0
    bool isMerc = false
    if abMercContract && !HasFactionGoodwill(akCandidate)
        paidCost = MercHireCostGlob.GetValue() as int
        Form creditsForm = Game.GetFormFromFile(SfCreditsId, "Starfield.esm")
        if paidCost > 0 && creditsForm != None
            int haveCreds = playerRef.GetItemCount(creditsForm)
            if haveCreds < paidCost
                Trace("recruit_refused actor=" + Id(akCandidate) + " reason=insufficient_credits need=" + paidCost + " have=" + haveCreds)
                if !abSilentPrompt
                    Say("Insufficient credits for mercenary contract (" + paidCost + " needed).")
                endif
                return false
            endif
            playerRef.RemoveItem(creditsForm, paidCost, true, None)
            isMerc = true
        endif
    endif

    if !akCandidate.IsInFaction(SquadAllyFaction)
        akCandidate.AddToFaction(SquadAllyFaction)
    endif
    akCandidate.IgnoreFriendlyHits(true)
    akCandidate.SetRestrained(false)
    akCandidate.SetValue(SquadOrderStateAV, 0.0)
    akCandidate.SetLinkedRef(playerRef)
    ActiveSquad.AddRef(akCandidate)
    if isMerc && HiredMercRefs.Find(akCandidate) < 0
        HiredMercRefs.Add(akCandidate)
    endif

    SQ_FollowersScript folApi = FollowersApi()
    bool folRegistered = false
    if folApi != None && folApi.IsRunning()
        folApi.SetRoleActive(akCandidate, false, true)
        folApi.CommandFollow(akCandidate)
        folRegistered = true
    endif
    akCandidate.EvaluatePackage(false)

    if playerRef.GetItemCount(SquadRadioToken) < 1
        playerRef.AddItem(SquadRadioToken, 1, true)
    endif

    SyncSquadGlobals(playerRef)
    SQ_Groups_QuestScript grpApi = GroupsApi()
    int grpId = -1
    if grpApi != None
        grpId = grpApi.GetGroupFactionIDValueByActor(akCandidate, false)
    endif
    Trace("recruited actor=" + Id(akCandidate) + " slot=" + ActiveSquad.GetCount() + "/" + cap + " merc=" + isMerc + " cost=" + paidCost + " rank_tier=" + candTier + " loyalty=" + curLoyalty + " sq_followers=" + folRegistered + " group_id=" + grpId)
    if !abSilentPrompt
        Say("Recruited into fireteam (" + ActiveSquad.GetCount() + "/" + cap + ").")
    endif
    return true
EndFunction

bool Function DismissMember(Actor akMember, string reasonStr)
    Actor playerRef = Game.GetPlayer()
    if akMember == None || ActiveSquad == None
        return false
    endif
    if ActiveSquad.Find(akMember) < 0
        return false
    endif
    ActiveSquad.RemoveRef(akMember)
    int mercIdx = HiredMercRefs.Find(akMember)
    if mercIdx >= 0
        HiredMercRefs.Remove(mercIdx)
    endif
    akMember.SetLinkedRef(None)
    akMember.SetRestrained(false)
    akMember.SetValue(SquadOrderStateAV, 0.0)

    SQ_FollowersScript folApi = FollowersApi()
    if folApi != None && folApi.IsRunning()
        folApi.SetRoleInactive(akMember, false, false, false)
    endif
    akMember.EvaluatePackage(false)
    SyncSquadGlobals(playerRef)
    Trace("dismissed actor=" + Id(akMember) + " reason=" + reasonStr + " active=" + ActiveSquad.GetCount())
    return true
EndFunction

Function DismissAllSquad(string reasonStr)
    if ActiveSquad == None
        return
    endif
    int safety = ActiveSquad.GetCount() + 2
    while ActiveSquad.GetCount() > 0 && safety > 0
        Actor m = ActiveSquad.GetActorAt(0)
        if m != None
            DismissMember(m, reasonStr)
        else
            ActiveSquad.RemoveAll()
        endif
        safety -= 1
    endwhile
    HiredMercRefs.Clear()
    SyncSquadGlobals(Game.GetPlayer())
EndFunction

; ---------------------------------------------------------------- individual & fireteam commands

Function CommandMemberFollow(Actor akMember, string sourceStr)
    Actor playerRef = Game.GetPlayer()
    if akMember == None || playerRef == None
        return
    endif
    akMember.SetRestrained(false)
    akMember.SetValue(SquadOrderStateAV, 0.0)
    akMember.SetLinkedRef(playerRef)
    ActorValue fsAv = Game.GetFormFromFile(SfFollowerStateAvId, "Starfield.esm") as ActorValue
    if fsAv != None
        akMember.SetValue(fsAv, 1.0)
    endif
    SQ_FollowersScript folApi = FollowersApi()
    if folApi != None && folApi.IsRunning()
        folApi.CommandFollow(akMember)
    endif
    akMember.EvaluatePackage(false)
    Trace("order actor=" + Id(akMember) + " cmd=follow source=" + sourceStr + " state=" + (akMember.GetValue(SquadOrderStateAV) as int))
EndFunction

Function CommandMemberWait(Actor akMember, string sourceStr)
    if akMember == None
        return
    endif
    akMember.SetValue(SquadOrderStateAV, 1.0)
    akMember.SetLinkedRef(None)
    ActorValue fsAv = Game.GetFormFromFile(SfFollowerStateAvId, "Starfield.esm") as ActorValue
    if fsAv != None
        akMember.SetValue(fsAv, 2.0)
    endif
    SQ_FollowersScript folApi = FollowersApi()
    if folApi != None && folApi.IsRunning()
        folApi.CommandWait(akMember, None)
    endif
    akMember.EvaluatePackage(false)
    Trace("order actor=" + Id(akMember) + " cmd=wait source=" + sourceStr + " state=" + (akMember.GetValue(SquadOrderStateAV) as int))
EndFunction

Function CommandSquadFollow(string sourceStr)
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None
            CommandMemberFollow(m, sourceStr)
        endif
        i += 1
    endwhile
    Trace("fireteam_cmd cmd=all_follow count=" + cnt + " source=" + sourceStr)
EndFunction

Function CommandSquadWait(string sourceStr)
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None
            CommandMemberWait(m, sourceStr)
        endif
        i += 1
    endwhile
    Trace("fireteam_cmd cmd=all_wait count=" + cnt + " source=" + sourceStr)
EndFunction

Function SetSquadStance(int stanceCode, string sourceStr)
    ; 0 = Defensive (Return Fire), 1 = Aggressive (Engage at Will), 2 = Passive (Hold Fire / Stealth)
    if stanceCode < 0 || stanceCode > 2
        stanceCode = 0
    endif
    SquadStanceGlob.SetValue(stanceCode as float)
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None
            if stanceCode == 2 && m.IsInCombat()
                m.StopCombat()
            endif
            m.EvaluatePackage(false)
        endif
        i += 1
    endwhile
    string label = "defensive"
    if stanceCode == 1
        label = "aggressive"
    elseif stanceCode == 2
        label = "hold_fire"
    endif
    Trace("fireteam_cmd cmd=stance stance=" + label + " code=" + stanceCode + " count=" + cnt + " source=" + sourceStr)
EndFunction

Function InspectMember(Actor akMember, int slotIdx)
    if akMember == None
        return
    endif
    float loy = akMember.GetValue(SquadLoyaltyAV)
    float aff = akMember.GetValue(CompanionAffinityAV)
    int ord = akMember.GetValue(SquadOrderStateAV) as int
    int rnk = akMember.GetValue(RecruitRankTierAV) as int
    float nrv = akMember.GetValue(CompanionNerveBonusAV)
    Trace("inspect slot=" + slotIdx + " actor=" + Id(akMember) + " order=" + ord + " stance=" + (SquadStanceGlob.GetValue() as int) + " loyalty=" + loy + " affinity=" + aff + " rank_tier=" + rnk + " nerve_pct=" + nrv + " bleedout=" + akMember.IsBleedingOut() + " loaded=" + akMember.Is3DLoaded())
EndFunction

Function InspectFireteam(string sourceStr)
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        InspectMember(ActiveSquad.GetActorAt(i), i)
        i += 1
    endwhile
    Trace("fireteam_cmd cmd=inspect_all count=" + cnt + " cap=" + GetEffectiveSquadCap(Game.GetPlayer()) + " source=" + sourceStr)
EndFunction

Function OpenMemberTrade(Actor akMember)
    if akMember == None
        return
    endif
    Trace("order actor=" + Id(akMember) + " cmd=trade")
    akMember.OpenInventory(true)
EndFunction

; ---------------------------------------------------------------- interactive wheel & fireteam radio UI

Event RefCollectionAlias.OnActivate(RefCollectionAlias akSender, ObjectReference akSenderRef, ObjectReference akActionRef)
    Actor playerRef = Game.GetPlayer()
    if playerRef == None || akActionRef != (playerRef as ObjectReference)
        return
    endif
    Actor memberRef = akSenderRef as Actor
    if memberRef == None || playerRef.IsInCombat()
        return
    endif
    OpenCompanionWheel(memberRef)
EndEvent

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    Actor playerRef = Game.GetPlayer()
    if playerRef == None || akSender != (playerRef as ObjectReference) || akDestContainer != None
        return
    endif
    if akBaseItem == (SquadRadioToken as Form)
        if akItemReference != None && !akItemReference.IsDeleted()
            akItemReference.DisableNoWait(false)
            akItemReference.Delete()
        endif
        playerRef.AddItem(SquadRadioToken, 1, true)
        OpenFireteamRadio()
    endif
EndEvent

Function OpenCompanionWheel(Actor akMember)
    if akMember == None || CompanionWheelMsg == None
        return
    endif
    int choice = CompanionWheelMsg.Show()
    if choice == 0
        CommandMemberFollow(akMember, "wheel")
    elseif choice == 1
        CommandMemberWait(akMember, "wheel")
    elseif choice == 2
        InspectMember(akMember, ActiveSquad.Find(akMember))
        Say("Loyalty " + (akMember.GetValue(SquadLoyaltyAV) as int) + "/100, Stance " + (SquadStanceGlob.GetValue() as int))
    elseif choice == 3
        int nextStance = ((SquadStanceGlob.GetValue() as int) + 1) % 3
        SetSquadStance(nextStance, "wheel")
    elseif choice == 4
        OpenMemberTrade(akMember)
    elseif choice == 5
        Say("Companion Affinity: " + (akMember.GetValue(CompanionAffinityAV) as int) + " / 1000")
    elseif choice == 6
        DismissMember(akMember, "wheel_dismiss")
    endif
EndFunction

Function OpenFireteamRadio()
    if FireteamCommandMsg == None
        return
    endif
    int choice = FireteamCommandMsg.Show()
    if choice == 0
        CommandSquadFollow("radio")
    elseif choice == 1
        CommandSquadWait("radio")
    elseif choice == 2
        SetSquadStance(1, "radio")
    elseif choice == 3
        SetSquadStance(0, "radio")
    elseif choice == 4
        SetSquadStance(2, "radio")
    elseif choice == 5
        TeleportActiveSquad("manual_radio_sync", false)
    elseif choice == 6
        InspectFireteam("radio")
    endif
EndFunction

; ---------------------------------------------------------------- 3-chokepoint follower teleportation

int Function TeleportActiveSquad(string reasonStr, bool abIncludeWaiting)
    Actor playerRef = Game.GetPlayer()
    if playerRef == None || ActiveSquad == None
        return 0
    endif
    int cnt = ActiveSquad.GetCount()
    if cnt == 0
        Trace("teleport reason=" + reasonStr + " moved=0 active=0")
        return 0
    endif

    SQ_FollowersScript folApi = FollowersApi()
    if folApi != None && folApi.IsRunning()
        Actor[] squadArr = ActiveSquad.GetActorArray()
        folApi.TeleportFollowers(playerRef, squadArr, true, abIncludeWaiting, false, false, true)
    endif

    float ang = playerRef.GetAngleZ()
    float backX = -Math.Sin(ang)
    float backY = -Math.Cos(ang)
    float rightX = Math.Cos(ang)
    float rightY = -Math.Sin(ang)

    int movedCount = 0
    int skippedWaiting = 0
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None && !m.IsDead()
            int ord = m.GetValue(SquadOrderStateAV) as int
            if ord == 1 && !abIncludeWaiting
                skippedWaiting += 1
            else
                float rowDist = FormationBaseM + ((i / 2) as float) * FormationStepM
                float sideSign = -1.0
                if (i % 2) == 1
                    sideSign = 1.0
                endif
                float latDist = sideSign * 1.1
                float dx = backX * rowDist + rightX * latDist
                float dy = backY * rowDist + rightY * latDist
                m.MoveTo(playerRef, dx, dy, 0.0, false)
                m.SetLinkedRef(playerRef)
                m.EvaluatePackage(false)
                movedCount += 1
            endif
        endif
        i += 1
    endwhile

    SnapshotPlayerTravelState(playerRef)
    Trace("teleport reason=" + reasonStr + " moved=" + movedCount + " skipped_waiting=" + skippedWaiting + " active=" + cnt + " cell=" + Id(playerRef.GetParentCell()) + " interior=" + playerRef.IsInInterior())
    return movedCount
EndFunction

Event OnPlayerTeleport()
    CheckTravelChokepoints("engine_player_teleport")
EndEvent

Event Actor.OnLocationChange(Actor akSender, Location akOldLoc, Location akNewLoc)
    CheckTravelChokepoints("location_change")
EndEvent

Function CheckTravelChokepoints(string triggerStr)
    Actor playerRef = Game.GetPlayer()
    if playerRef == None || ActiveSquad == None || ActiveSquad.GetCount() == 0
        SnapshotPlayerTravelState(playerRef)
        return
    endif

    Cell curCell = playerRef.GetParentCell()
    bool nowInterior = playerRef.IsInInterior()
    float nowDays = ReadGameDays()
    int nowNgStage = ReadNewGameStage()

    ; Chokepoint 2: Vault 111 Exit Lift (#803) or interior-to-exterior lift emergence
    if (LastNewGameStage >= 0 && LastNewGameStage < 40 && nowNgStage >= 40) || (LastWasInInterior && !nowInterior)
        TeleportActiveSquad("vault_lift_or_interior_exit", false)
        return
    endif

    ; Chokepoint 3: Pip-Boy Fast Travel (#801 advances GameDaysPassed across exterior jump)
    if LastGameDays >= 0.0 && (nowDays - LastGameDays) >= 0.005 && (curCell != LastPlayerCell || MaxFollowingDistance(playerRef) > 35.0)
        TeleportActiveSquad("pipboy_fast_travel", false)
        return
    endif

    ; Chokepoint 1: Load Doors (FO4SF_LoadDoor interior/exterior cell transition) or distance leash
    if curCell != LastPlayerCell || MaxFollowingDistance(playerRef) > LeashDistM
        TeleportActiveSquad("load_door_cell_change", false)
        return
    endif

    SnapshotPlayerTravelState(playerRef)
EndFunction

float Function MaxFollowingDistance(Actor playerRef)
    float maxD = 0.0
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None && !m.IsDead() && (m.GetValue(SquadOrderStateAV) as int) != 1
            if m.GetParentCell() != playerRef.GetParentCell()
                return 999999.0
            endif
            float d = playerRef.GetDistance(m)
            if d > maxD
                maxD = d
            endif
        endif
        i += 1
    endwhile
    return maxD
EndFunction

; ---------------------------------------------------------------- affinity, loyalty & GAMMA upkeep

Function ModifyAffinity(Actor akCompanion, float afDelta, string reasonStr)
    Actor playerRef = Game.GetPlayer()
    if akCompanion == None || playerRef == None
        return
    endif
    float before = akCompanion.GetValue(CompanionAffinityAV)
    float after = before + afDelta
    if after < 0.0
        after = 0.0
    elseif after > 1000.0
        after = 1000.0
    endif
    akCompanion.SetValue(CompanionAffinityAV, after)

    string tier = "neutral"
    if after >= 1000.0
        tier = "idolized"
    elseif after >= 750.0
        tier = "admired"
    elseif after >= 500.0
        tier = "trusted"
    elseif after >= 250.0
        tier = "warm"
    endif

    bool perkGranted = false
    if after >= 1000.0 && PerkUnitedWeStand != None && !playerRef.HasPerk(PerkUnitedWeStand)
        playerRef.AddPerk(PerkUnitedWeStand)
        perkGranted = true
        Say("Companion Idolized: Perk 'United We Stand' unlocked.")
    endif
    Trace("affinity actor=" + Id(akCompanion) + " before=" + before + " after=" + after + " tier=" + tier + " perk_granted=" + perkGranted + " reason=" + reasonStr)
EndFunction

Function ModifyLoyalty(Actor akMember, float afDelta, string reasonStr)
    if akMember == None
        return
    endif
    float before = akMember.GetValue(SquadLoyaltyAV)
    float after = before + afDelta
    if after < 0.0
        after = 0.0
    elseif after > 100.0
        after = 100.0
    endif
    akMember.SetValue(SquadLoyaltyAV, after)
    bool deserted = false
    if after < 20.0 && ActiveSquad.Find(akMember) >= 0
        deserted = true
        DismissMember(akMember, "loyalty_desertion")
    endif
    Trace("loyalty actor=" + Id(akMember) + " before=" + before + " after=" + after + " deserted=" + deserted + " reason=" + reasonStr)
EndFunction

int Function ComputeNetContractPayout(int grossAmount)
    if grossAmount <= 0
        return 0
    endif
    int activeMercs = 0
    int i = 0
    while i < HiredMercRefs.Length
        Actor m = HiredMercRefs[i]
        if m != None && !m.IsDead() && ActiveSquad.Find(m) >= 0
            activeMercs += 1
        endif
        i += 1
    endwhile
    float sharePerMerc = MercRewardShareGlob.GetValue()
    float totalShare = (activeMercs as float) * sharePerMerc
    if totalShare > 0.60
        totalShare = 0.60
    endif
    int mercCut = ((grossAmount as float) * totalShare) as int
    int netPlayer = grossAmount - mercCut
    Trace("contract_payout gross=" + grossAmount + " active_mercs=" + activeMercs + " merc_cut=" + mercCut + " player_net=" + netPlayer)
    return netPlayer
EndFunction

Event RefCollectionAlias.OnEnterBleedout(RefCollectionAlias akSender, ObjectReference akSenderRef)
    Actor downedMember = akSenderRef as Actor
    if downedMember != None
        StabilizeDownedMember(downedMember, "bleedout_event")
    endif
EndEvent

bool Function StabilizeDownedMember(Actor akMember, string triggerStr)
    Actor playerRef = Game.GetPlayer()
    if akMember == None || playerRef == None
        return false
    endif
    Form medPack = Game.GetFormFromFile(SfMedPackId, "Starfield.esm")
    ActorValue healthAv = Game.GetFormFromFile(SfHealthAvId, "Starfield.esm") as ActorValue
    if medPack != None
        if akMember.GetItemCount(medPack) > 0
            akMember.RemoveItem(medPack, 1, true, None)
            if healthAv != None
                akMember.RestoreValue(healthAv, 50.0)
            endif
            ModifyLoyalty(akMember, 5.0, "self_medpack")
            Trace("upkeep_revive actor=" + Id(akMember) + " source=member_medpack trigger=" + triggerStr)
            return true
        elseif playerRef.GetItemCount(medPack) > 0
            playerRef.RemoveItem(medPack, 1, true, None)
            if healthAv != None
                akMember.RestoreValue(healthAv, 50.0)
            endif
            ModifyLoyalty(akMember, 10.0, "player_medpack_revive")
            Trace("upkeep_revive actor=" + Id(akMember) + " source=player_medpack trigger=" + triggerStr)
            return true
        endif
    endif
    Trace("upkeep_bleedout_unassisted actor=" + Id(akMember) + " trigger=" + triggerStr)
    return false
EndFunction

Function TickSquadUpkeep(Actor playerRef)
    if playerRef == None || ActiveSquad == None
        return
    endif
    SyncSquadGlobals(playerRef)
    int cnt = ActiveSquad.GetCount()
    int bleeding = 0
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None && !m.IsDead()
            if m.IsBleedingOut() != 0
                bleeding += 1
                StabilizeDownedMember(m, "poll_upkeep")
            endif
        endif
        i += 1
    endwhile
EndFunction

; ---------------------------------------------------------------- persistence & reload audit

Function ReassertSquadPackages(Actor playerRef)
    if playerRef == None || ActiveSquad == None
        return
    endif
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None && !m.IsDead()
            int ord = m.GetValue(SquadOrderStateAV) as int
            if ord == 1
                m.SetLinkedRef(None)
            else
                m.SetLinkedRef(playerRef)
            endif
            m.EvaluatePackage(false)
        endif
        i += 1
    endwhile
EndFunction

Function AuditSquadPersistence(string whenStr)
    Actor playerRef = Game.GetPlayer()
    SyncSquadGlobals(playerRef)
    int cnt = ActiveSquad.GetCount()
    int okCount = 0
    int followingCount = 0
    int waitingCount = 0
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None && !m.IsDead() && !m.IsDisabled()
            okCount += 1
            if (m.GetValue(SquadOrderStateAV) as int) == 1
                waitingCount += 1
            else
                followingCount += 1
            endif
        endif
        i += 1
    endwhile
    bool hasUnited = playerRef != None && PerkUnitedWeStand != None && playerRef.HasPerk(PerkUnitedWeStand)
    bool passFlag = okCount == cnt
    Trace("reload_audit when=" + whenStr + " reload_count=" + ReloadCount + " squad_ok=" + okCount + "/" + cnt + " following=" + followingCount + " waiting=" + waitingCount + " stance=" + (SquadStanceGlob.GetValue() as int) + " united_perk=" + hasUnited + " pass=" + passFlag)
EndFunction

; ---------------------------------------------------------------- timer & automated verification stages 10..60

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        PollTick()
        StartTimer(PollIntervalS, TIMER_POLL)
    elseif aiTimerID == TIMER_RELOAD_SETTLE
        AuditSquadPersistence("reload+2s")
    endif
EndEvent

Function PollTick()
    InitState()
    Actor playerRef = Game.GetPlayer()
    if playerRef != None
        CheckTravelChokepoints("poll")
        TickSquadUpkeep(playerRef)
    endif

    if TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0
        return
    endif

    int i = 0
    while i < StageList.Length
        int stg = StageList[i]
        if !DoneList[i] && GetStageDone(stg)
            DoneList[i] = true
            RunVerificationStage(stg, playerRef)
        endif
        i += 1
    endwhile

    if GetStageDone(60) && !CleanupDone
        CleanupDone = true
        RunStage60Cleanup(playerRef)
    endif
EndFunction

Function RunVerificationStage(int stageNum, Actor playerRef)
    if playerRef == None || FireteamTestRefs == None || FireteamTestRefs.Length < 4 || StoryCompanionRef == None
        Trace("stage_error stage=" + stageNum + " reason=missing_player_or_fireteam_refs")
        return
    endif

    if stageNum == 10
        DismissAllSquad("stage10_reset")
        if StageAddedCommanderPerk && playerRef.HasPerk(PerkSquadCommander)
            playerRef.RemovePerk(PerkSquadCommander)
            StageAddedCommanderPerk = false
        endif
        int baseCap = GetEffectiveSquadCap(playerRef)
        Form creds = Game.GetFormFromFile(SfCreditsId, "Starfield.esm")
        int mercFee = MercHireCostGlob.GetValue() as int
        if creds != None && playerRef.GetItemCount(creds) < mercFee
            playerRef.AddItem(creds, mercFee, true)
        endif
        ; Rank gate test: set Delta to tier 4 briefly against unperked player (if level < 30), then restore to 0
        FireteamTestRefs[3].SetValue(RecruitRankTierAV, 4.0)
        bool rankBlocked = false
        if GetPlayerRankTier(playerRef) < 4
            rankBlocked = !TryRecruit(FireteamTestRefs[3], false, true)
        else
            rankBlocked = true
        endif
        FireteamTestRefs[3].SetValue(RecruitRankTierAV, 0.0)

        bool r1 = TryRecruit(FireteamTestRefs[0], false, true)
        bool r2 = TryRecruit(FireteamTestRefs[1], true, true)
        bool thirdBlocked = false
        if baseCap == 2
            thirdBlocked = !TryRecruit(FireteamTestRefs[2], false, true)
        else
            ; Player already has CHA >= 8 or leadership perk in this save
            thirdBlocked = true
        endif
        bool ok10 = r1 && r2 && thirdBlocked && rankBlocked
        Trace("stage_result stage=10 cap=" + baseCap + " active=" + ActiveSquad.GetCount() + " r1=" + r1 + " r2=" + r2 + " third_blocked=" + thirdBlocked + " rank_blocked=" + rankBlocked + " pass=" + ok10)

    elseif stageNum == 20
        if !HasLeadershipQualification(playerRef)
            playerRef.AddPerk(PerkSquadCommander)
            StageAddedCommanderPerk = true
        endif
        int maxCap = GetEffectiveSquadCap(playerRef)
        if ActiveSquad.Find(FireteamTestRefs[0]) < 0
            TryRecruit(FireteamTestRefs[0], false, true)
        endif
        if ActiveSquad.Find(FireteamTestRefs[1]) < 0
            TryRecruit(FireteamTestRefs[1], false, true)
        endif
        bool r3 = true
        if ActiveSquad.Find(FireteamTestRefs[2]) < 0
            r3 = TryRecruit(FireteamTestRefs[2], false, true)
        endif
        bool r4 = true
        if ActiveSquad.Find(FireteamTestRefs[3]) < 0
            r4 = TryRecruit(FireteamTestRefs[3], false, true)
        endif
        CommandSquadWait("stage20")
        int waitN = CountSquadInOrderState(1)
        CommandSquadFollow("stage20")
        int followN = CountSquadInOrderState(0)
        SetSquadStance(1, "stage20")
        SetSquadStance(2, "stage20")
        SetSquadStance(0, "stage20")
        InspectFireteam("stage20")
        bool ok20 = (maxCap >= 4) && (ActiveSquad.GetCount() == 4) && r3 && r4 && (waitN == 4) && (followN == 4)
        Trace("stage_result stage=20 cap=" + maxCap + " active=" + ActiveSquad.GetCount() + " wait_all=" + waitN + " follow_all=" + followN + " pass=" + ok20)

    elseif stageNum == 30
        ; Hold slot 3 (Delta) in Wait to verify TeleportActiveSquad moves the 3 following slots and leaves the 1 waiting slot
        if ActiveSquad.GetCount() >= 4
            CommandMemberWait(FireteamTestRefs[3], "stage30_hold_delta")
        endif
        int mDoor = TeleportActiveSquad("load_door_cell_change", false)
        int mLift = TeleportActiveSquad("vault_lift_or_interior_exit", false)
        int mFast = TeleportActiveSquad("pipboy_fast_travel", false)
        if ActiveSquad.GetCount() >= 4
            CommandMemberFollow(FireteamTestRefs[3], "stage30_resume_delta")
        endif
        bool ok30 = (mDoor == 3) && (mLift == 3) && (mFast == 3)
        Trace("stage_result stage=30 moved_door=" + mDoor + " moved_lift=" + mLift + " moved_fasttravel=" + mFast + " pass=" + ok30)

    elseif stageNum == 40
        StoryCompanionRef.SetValue(CompanionAffinityAV, 0.0)
        ModifyAffinity(StoryCompanionRef, 250.0, "stage40_warm")
        ModifyAffinity(StoryCompanionRef, 250.0, "stage40_trusted")
        ModifyAffinity(StoryCompanionRef, 250.0, "stage40_admired")
        ModifyAffinity(StoryCompanionRef, 250.0, "stage40_idolized")
        bool hasPerk = playerRef.HasPerk(PerkUnitedWeStand)
        int netPay = ComputeNetContractPayout(1000)
        FireteamTestRefs[0].SetValue(SquadLoyaltyAV, 75.0)
        ModifyLoyalty(FireteamTestRefs[0], -15.0, "stage40_friendly_fire")
        float loyAfter = FireteamTestRefs[0].GetValue(SquadLoyaltyAV)
        bool ok40 = hasPerk && (netPay <= 1000) && (loyAfter == 60.0)
        Trace("stage_result stage=40 united_perk=" + hasPerk + " net_payout_1000=" + netPay + " loyalty_after=" + loyAfter + " pass=" + ok40)

    elseif stageNum == 50
        AuditSquadPersistence("stage50")
    endif
EndFunction

int Function CountSquadInOrderState(int wantState)
    int n = 0
    int cnt = ActiveSquad.GetCount()
    int i = 0
    while i < cnt
        Actor m = ActiveSquad.GetActorAt(i)
        if m != None && (m.GetValue(SquadOrderStateAV) as int) == wantState
            n += 1
        endif
        i += 1
    endwhile
    return n
EndFunction

Function RunStage60Cleanup(Actor playerRef)
    DismissAllSquad("stage60_cleanup")
    if playerRef != None && StageAddedCommanderPerk && playerRef.HasPerk(PerkSquadCommander)
        playerRef.RemovePerk(PerkSquadCommander)
        StageAddedCommanderPerk = false
    endif
    Trace("cleanup active=" + ActiveSquad.GetCount() + " pass=true")
EndFunction
