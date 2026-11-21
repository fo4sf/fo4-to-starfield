Scriptname FO4SF_ReputationQuest extends Quest
{Multi-title Global Karma (-1000..+1000 in FO4SFCoreValues.esm) and 16-state Faction Reputation runtime controller.
 Attached to QUST FO4SF_ReputationQuest (0x800 of FO4SFReputation.esm), StartGameEnabled.
 Keeps moral Karma and per-faction Fame x Infamy (state = fame_tier * 4 + infamy_tier) strictly orthogonal so a
 Very Evil (-1000..-750) player who is Idolized (state 12) retains Ally disposition and the 0.75x vendor buy multiplier.}

; Bound VMAD properties (held equal with dotnet/ReputationCore/Program.cs)
ActorValue Property KarmaAV Auto Const
GlobalVariable Property KarmaValueGlob Auto Const
GlobalVariable Property KarmaTierGlob Auto Const
GlobalVariable Property TestModeGlobal Auto Const
int Property FactionCount = 8 Auto Const
FormList Property RepTokenList Auto Const
MiscObject Property CharityToken Auto Const
MiscObject Property TheftToken Auto Const
MiscObject Property FactionAidToken Auto Const
MiscObject Property FactionCrimeToken Auto Const
GlobalVariable Property EndingSlideGlob Auto Const
ActorValue Property VendorBuyMultAV Auto Const
Perk Property RepVendorPerk Auto Const
GlobalVariable Property CompanionMoralGlob Auto Const
Faction Property PlayerFaction Auto Const
Perk[] Property KarmaTagPerks Auto Const
Faction[] Property SlotFactions Auto Const
ActorValue[] Property SlotFameAVs Auto Const
ActorValue[] Property SlotInfamyAVs Auto Const
ActorValue[] Property SlotStateAVs Auto Const
GlobalVariable[] Property SlotFameGlobs Auto Const
GlobalVariable[] Property SlotInfamyGlobs Auto Const
GlobalVariable[] Property SlotStateGlobs Auto Const
Actor Property VendorNpcRef Auto Const

int Version = 1
string LogName = "FO4SFReputation"
string RepPlugin = "FO4SFReputation.esm"
string CorePlugin = "FO4SFCoreValues.esm"
string SfPlugin = "Starfield.esm"

; Deterministic FormIDs (used only once in InitCache fallback if any property is unbound)
int CoreKarmaAvId = 0x000830
int CoreKarmaValueGlobId = 0x000831
int CoreKarmaTierGlobId = 0x000832
int EndingSlideGlobId = 0x000804
int VendorBuyMultAvId = 0x000805
int RepVendorPerkId = 0x000806
int CompanionMoralGlobId = 0x000807
int KarmaPerkFirstId = 0x000808

int FactFirstId = 0x000810
int FameAvFirstId = 0x000820
int InfamyAvFirstId = 0x000830
int StateAvFirstId = 0x000840
int FameGlobFirstId = 0x000850
int InfamyGlobFirstId = 0x000860
int StateGlobFirstId = 0x000870

int CharityTokenId = 0x000880
int TheftTokenId = 0x000881
int FactionAidTokenId = 0x000882
int FactionCrimeTokenId = 0x000883
int RepTokenListId = 0x00088F
int PlayerFactionSfId = 0x01C21C

; Cached references initialized once in InitCache()
ActorValue CachedKarmaAV = None
GlobalVariable CachedKarmaValGlob = None
GlobalVariable CachedKarmaTierGlob = None
GlobalVariable CachedEndingSlideGlob = None
ActorValue CachedVendorBuyMultAV = None
Perk CachedVendorPerk = None
GlobalVariable CachedCompMoralGlob = None
Faction CachedPlayerFaction = None
FormList CachedTokenList = None
Form CachedCharityTok = None
Form CachedTheftTok = None
Form CachedAidTok = None
Form CachedCrimeTok = None
Perk[] CachedKarmaPerks
Faction[] CachedFactions
ActorValue[] CachedFameAVs
ActorValue[] CachedInfamyAVs
ActorValue[] CachedStateAVs
GlobalVariable[] CachedFameGlobs
GlobalVariable[] CachedInfamyGlobs
GlobalVariable[] CachedStateGlobs
bool CacheReady = false

; Fame / Infamy tier cutoffs on 0..100 scale
float TierLowCutoff = 15.0
float TierMedCutoff = 40.0
float TierHighCutoff = 75.0

int TIMER_POLL = 1
float POLL_S = 1.0

int ActiveVendorFactionIdx = 0
bool ReentrancyGuard = false
bool Done10 = false
bool Done20 = false
bool Done30 = false
bool Done40 = false
bool Done50 = false
bool Done60 = false

; ---------------------------------------------------------------- cache initialization & lifecycle

Function InitCache()
    if CacheReady
        return
    endif
    CachedKarmaAV = KarmaAV
    if CachedKarmaAV == None
        CachedKarmaAV = Game.GetFormFromFile(CoreKarmaAvId, CorePlugin) as ActorValue
    endif
    CachedKarmaValGlob = KarmaValueGlob
    if CachedKarmaValGlob == None
        CachedKarmaValGlob = Game.GetFormFromFile(CoreKarmaValueGlobId, CorePlugin) as GlobalVariable
    endif
    CachedKarmaTierGlob = KarmaTierGlob
    if CachedKarmaTierGlob == None
        CachedKarmaTierGlob = Game.GetFormFromFile(CoreKarmaTierGlobId, CorePlugin) as GlobalVariable
    endif
    CachedEndingSlideGlob = EndingSlideGlob
    if CachedEndingSlideGlob == None
        CachedEndingSlideGlob = Game.GetFormFromFile(EndingSlideGlobId, RepPlugin) as GlobalVariable
    endif
    CachedVendorBuyMultAV = VendorBuyMultAV
    if CachedVendorBuyMultAV == None
        CachedVendorBuyMultAV = Game.GetFormFromFile(VendorBuyMultAvId, RepPlugin) as ActorValue
    endif
    CachedVendorPerk = RepVendorPerk
    if CachedVendorPerk == None
        CachedVendorPerk = Game.GetFormFromFile(RepVendorPerkId, RepPlugin) as Perk
    endif
    CachedCompMoralGlob = CompanionMoralGlob
    if CachedCompMoralGlob == None
        CachedCompMoralGlob = Game.GetFormFromFile(CompanionMoralGlobId, RepPlugin) as GlobalVariable
    endif
    CachedPlayerFaction = PlayerFaction
    if CachedPlayerFaction == None
        CachedPlayerFaction = Game.GetFormFromFile(PlayerFactionSfId, SfPlugin) as Faction
    endif
    CachedTokenList = RepTokenList
    if CachedTokenList == None
        CachedTokenList = Game.GetFormFromFile(RepTokenListId, RepPlugin) as FormList
    endif
    CachedCharityTok = CharityToken as Form
    if CachedCharityTok == None
        CachedCharityTok = Game.GetFormFromFile(CharityTokenId, RepPlugin)
    endif
    CachedTheftTok = TheftToken as Form
    if CachedTheftTok == None
        CachedTheftTok = Game.GetFormFromFile(TheftTokenId, RepPlugin)
    endif
    CachedAidTok = FactionAidToken as Form
    if CachedAidTok == None
        CachedAidTok = Game.GetFormFromFile(FactionAidTokenId, RepPlugin)
    endif
    CachedCrimeTok = FactionCrimeToken as Form
    if CachedCrimeTok == None
        CachedCrimeTok = Game.GetFormFromFile(FactionCrimeTokenId, RepPlugin)
    endif

    if KarmaTagPerks != None && KarmaTagPerks.Length == 5
        CachedKarmaPerks = KarmaTagPerks
    else
        CachedKarmaPerks = new Perk[5]
        int kIdx = 0
        while kIdx < 5
            CachedKarmaPerks[kIdx] = Game.GetFormFromFile(KarmaPerkFirstId + kIdx, RepPlugin) as Perk
            kIdx += 1
        endwhile
    endif

    if SlotFactions != None && SlotFactions.Length == FactionCount
        CachedFactions = SlotFactions
        CachedFameAVs = SlotFameAVs
        CachedInfamyAVs = SlotInfamyAVs
        CachedStateAVs = SlotStateAVs
        CachedFameGlobs = SlotFameGlobs
        CachedInfamyGlobs = SlotInfamyGlobs
        CachedStateGlobs = SlotStateGlobs
    else
        CachedFactions = new Faction[FactionCount]
        CachedFameAVs = new ActorValue[FactionCount]
        CachedInfamyAVs = new ActorValue[FactionCount]
        CachedStateAVs = new ActorValue[FactionCount]
        CachedFameGlobs = new GlobalVariable[FactionCount]
        CachedInfamyGlobs = new GlobalVariable[FactionCount]
        CachedStateGlobs = new GlobalVariable[FactionCount]
        int sIdx = 0
        while sIdx < FactionCount
            CachedFactions[sIdx] = Game.GetFormFromFile(FactFirstId + sIdx, RepPlugin) as Faction
            CachedFameAVs[sIdx] = Game.GetFormFromFile(FameAvFirstId + sIdx, RepPlugin) as ActorValue
            CachedInfamyAVs[sIdx] = Game.GetFormFromFile(InfamyAvFirstId + sIdx, RepPlugin) as ActorValue
            CachedStateAVs[sIdx] = Game.GetFormFromFile(StateAvFirstId + sIdx, RepPlugin) as ActorValue
            CachedFameGlobs[sIdx] = Game.GetFormFromFile(FameGlobFirstId + sIdx, RepPlugin) as GlobalVariable
            CachedInfamyGlobs[sIdx] = Game.GetFormFromFile(InfamyGlobFirstId + sIdx, RepPlugin) as GlobalVariable
            CachedStateGlobs[sIdx] = Game.GetFormFromFile(StateGlobFirstId + sIdx, RepPlugin) as GlobalVariable
            sIdx += 1
        endwhile
    endif
    CacheReady = true
EndFunction

bool Initialized = false

Event OnQuestInit()
    if Initialized
        return
    endif
    Initialized = true
    Debug.OpenUserLog(LogName)
    InitCache()
    Actor p = Game.GetPlayer()
    RegisterHooks(p)
    SyncAllFromActorValues(p, false)
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(RepPlugin) + " core_installed=" + Game.IsPluginInstalled(CorePlugin) + " states=" + BuildStatesCsv(p))
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function RegisterHooks(Actor akPlayer)
    InitCache()
    if akPlayer != None
        RemoveAllInventoryEventFilters()
        if CachedTokenList != None
            AddInventoryEventFilter(CachedTokenList)
        endif
        RegisterForRemoteEvent(akPlayer, "OnPlayerLoadGame")
        RegisterForRemoteEvent(akPlayer, "OnKill")
        RegisterForRemoteEvent(akPlayer, "OnPlayerCrimeGold")
        ObjectReference playerObj = akPlayer as ObjectReference
        RegisterForRemoteEvent(playerObj, "OnItemAdded")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    CacheReady = false
    InitCache()
    Actor p = Game.GetPlayer()
    RegisterHooks(p)
    bool parityOk = VerifyReloadParity(p)
    SyncAllFromActorValues(p, true)
    int kInt = ReadKarmaValue(p) as int
    int kTier = EvalKarmaTier(kInt as float)
    int slideIdx = kTier + 2
    int compCode = EvalCompanionMoralCode(kInt as float)
    float buyMult = ReadVendorBuyMult(p)
    int fac0React = GetSlotReaction(p, 0)
    string okStr = "false"
    if parityOk
        okStr = "true"
    endif
    Trace("reload_audit karma=" + kInt + " tier=" + kTier + " slide=" + slideIdx + " comp=" + compCode + " active_fac=" + ActiveVendorFactionIdx + " buy_mult=" + buyMult + " fac0_react=" + fac0React + " states=" + BuildStatesCsv(p) + " ok=" + okStr)
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        PollStages()
        StartTimer(POLL_S, TIMER_POLL)
    endif
EndEvent

; ---------------------------------------------------------------- stage polling (stages 10..60, test-mode gated)

Function PollStages()
    if TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0
        return
    endif
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif

    if !Done10 && GetStageDone(10)
        Done10 = true
        ; Stage 10: Prove Evil (-800 Very Evil) + Idolized (slot 0 Fame=85, Infamy=0 -> state 12, Ally + 0.75x buy_mult) orthogonality
        SetKarmaAbsolute(p, -800.0)
        SetFactionScoresAbsolute(p, 0, 85.0, 0.0)
        ActiveVendorFactionIdx = 0
        SyncAllFromActorValues(p, false)
        int react0 = GetSlotReaction(p, 0)
        float bm0 = ReadVendorBuyMult(p)
        int st0 = ReadSlotState(p, 0)
        string orthOk = "false"
        if (ReadKarmaValue(p) as int) <= -750 && st0 == 12 && react0 == 2 && bm0 > 0.74 && bm0 < 0.76
            orthOk = "true"
        endif
        Trace("orthogonality_proof karma=" + (ReadKarmaValue(p) as int) + " tier=" + EvalKarmaTier(ReadKarmaValue(p)) + " fac=0 state=" + st0 + " disp=" + StateDispositionName(st0) + " reaction=" + react0 + " buy_mult=" + bm0 + " ok=" + orthOk)
    endif

    if !Done20 && GetStageDone(20)
        Done20 = true
        OnQuestStageEvent(1, 50, 0, 300, "stage20_quest")
    endif

    if !Done30 && GetStageDone(30)
        Done30 = true
        ; Non-innocent combat kill against Legion (slot 6): Infamy rises, rival NCR (slot 5) gains Fame, Karma unchanged!
        OnFactionKill(None, 6, false)
    endif

    if !Done40 && GetStageDone(40)
        Done40 = true
        ; Witnessed theft from Settlers (slot 4): Karma drops AND Settlers Infamy rises to Shunned (state 1)
        OnTheftObserved(None, 100, 4, true)
    endif

    if !Done50 && GetStageDone(50)
        Done50 = true
        SetKarmaAbsolute(p, 800.0)
        SyncAllFromActorValues(p, false)
        Trace("karma_shift karma=" + (ReadKarmaValue(p) as int) + " tier=" + EvalKarmaTier(800.0) + " slide=4 comp=" + EvalCompanionMoralCode(800.0) + " states=" + BuildStatesCsv(p))
    endif

    if !Done60 && GetStageDone(60)
        Done60 = true
        int kNow = ReadKarmaValue(p) as int
        int tNow = EvalKarmaTier(kNow as float)
        Trace("status_dump karma=" + kNow + " tier=" + tNow + " slide=" + (tNow + 2) + " comp=" + EvalCompanionMoralCode(kNow as float) + " active_fac=" + ActiveVendorFactionIdx + " buy_mult=" + ReadVendorBuyMult(p) + " fac0_react=" + GetSlotReaction(p, 0) + " states=" + BuildStatesCsv(p))
    endif
EndFunction

; ---------------------------------------------------------------- public & live event hooks

Function OnQuestStageEvent(int aiFactionIdx, int aiFameDelta, int aiInfamyDelta, int aiKarmaDelta, string asSource)
    InitCache()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    if aiKarmaDelta != 0
        ModifyKarma(p, aiKarmaDelta as float)
    endif
    int stCode = -1
    int reactCode = -1
    if aiFactionIdx >= 0 && aiFactionIdx < FactionCount
        ModifyFactionScores(p, aiFactionIdx, aiFameDelta as float, aiInfamyDelta as float)
        ActiveVendorFactionIdx = aiFactionIdx
        SyncVendorMult(p)
        stCode = ReadSlotState(p, aiFactionIdx)
        reactCode = GetSlotReaction(p, aiFactionIdx)
    endif
    int kVal = ReadKarmaValue(p) as int
    Trace("quest_hook src=" + asSource + " fac=" + aiFactionIdx + " state=" + stCode + " reaction=" + reactCode + " buy_mult=" + ReadVendorBuyMult(p) + " karma=" + kVal + " tier=" + EvalKarmaTier(kVal as float) + " states=" + BuildStatesCsv(p))
EndFunction

Function OnFactionKill(Actor akVictim, int aiFactionIdx, bool abInnocent)
    InitCache()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    int slotIdx = aiFactionIdx
    if slotIdx < 0 && akVictim != None
        slotIdx = FindActorFactionSlot(akVictim)
    endif
    if abInnocent
        ModifyKarma(p, -100.0)
    endif
    int stCode = -1
    if slotIdx >= 0 && slotIdx < FactionCount
        ModifyFactionScores(p, slotIdx, 0.0, 50.0)
        int rivalIdx = RivalSlotFor(slotIdx)
        if rivalIdx >= 0 && rivalIdx < FactionCount
            ModifyFactionScores(p, rivalIdx, 10.0, 0.0)
        endif
        if ActiveVendorFactionIdx == slotIdx
            SyncVendorMult(p)
        endif
        stCode = ReadSlotState(p, slotIdx)
    endif
    int kVal = ReadKarmaValue(p) as int
    Trace("kill_hook fac=" + slotIdx + " innocent=" + abInnocent + " state=" + stCode + " karma=" + kVal + " tier=" + EvalKarmaTier(kVal as float) + " states=" + BuildStatesCsv(p))
EndFunction

Function OnTheftObserved(ObjectReference akOwnerFactionRef, int aiItemValue, int aiFactionIdx, bool abWitnessed = true)
    InitCache()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    int slotIdx = aiFactionIdx
    if slotIdx < 0 && akOwnerFactionRef != None
        Faction ownerFac = akOwnerFactionRef.GetFactionOwner()
        slotIdx = FindFactionSlot(ownerFac)
    endif

    int kLoss = 5 + (aiItemValue / 10)
    if kLoss < 5
        kLoss = 5
    elseif kLoss > 25
        kLoss = 25
    endif
    ModifyKarma(p, (0 - kLoss) as float)

    int stCode = -1
    if slotIdx >= 0 && slotIdx < FactionCount
        if abWitnessed
            ModifyFactionScores(p, slotIdx, 0.0, 25.0)
            if ActiveVendorFactionIdx == slotIdx
                SyncVendorMult(p)
            endif
        endif
        stCode = ReadSlotState(p, slotIdx)
    endif
    int kVal = ReadKarmaValue(p) as int
    Trace("theft_hook fac=" + slotIdx + " val=" + aiItemValue + " witnessed=" + abWitnessed + " state=" + stCode + " karma=" + kVal + " tier=" + EvalKarmaTier(kVal as float) + " states=" + BuildStatesCsv(p))
EndFunction

Event Actor.OnKill(Actor akSender, ObjectReference akVictim)
    Actor victimActor = akVictim as Actor
    if victimActor == None
        return
    endif
    int slotIdx = FindActorFactionSlot(victimActor)
    if slotIdx >= 0
        Actor p = Game.GetPlayer()
        bool wasInnocent = true
        if p != None && victimActor.IsHostileToActor(p)
            wasInnocent = false
        endif
        OnFactionKill(victimActor, slotIdx, wasInnocent)
    endif
EndEvent

Event Actor.OnPlayerCrimeGold(Actor akSender, ObjectReference akVictim, Form akFaction, int aeCrimeGold, int aeCrimeType)
    Faction crimeFac = akFaction as Faction
    int slotIdx = FindFactionSlot(crimeFac)
    if slotIdx >= 0 && (aeCrimeType == 0 || aeCrimeType == 1)
        OnTheftObserved(akVictim, aeCrimeGold, slotIdx, true)
    endif
EndEvent

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    if ReentrancyGuard || akBaseItem == None || aiItemCount <= 0
        return
    endif
    InitCache()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif

    if akBaseItem == CachedCharityTok || akBaseItem == CachedTheftTok || akBaseItem == CachedAidTok || akBaseItem == CachedCrimeTok
        ReentrancyGuard = true
        string tokKind = "unknown"
        if akBaseItem == CachedCharityTok
            tokKind = "charity"
            ModifyKarma(p, 300.0 * (aiItemCount as float))
        elseif akBaseItem == CachedTheftTok
            tokKind = "theft"
            ModifyKarma(p, -350.0 * (aiItemCount as float))
        elseif akBaseItem == CachedAidTok
            tokKind = "faction_aid"
            ModifyFactionScores(p, 0, 80.0 * (aiItemCount as float), 0.0)
            ActiveVendorFactionIdx = 0
            SyncVendorMult(p)
        elseif akBaseItem == CachedCrimeTok
            tokKind = "faction_crime"
            int lastSlot = FactionCount - 1
            ModifyFactionScores(p, lastSlot, 0.0, 80.0 * (aiItemCount as float))
        endif
        p.RemoveItem(akBaseItem, aiItemCount, true, None)
        int kNow = ReadKarmaValue(p) as int
        Trace("token_hook token=" + tokKind + " count=" + aiItemCount + " karma=" + kNow + " tier=" + EvalKarmaTier(kNow as float) + " buy_mult=" + ReadVendorBuyMult(p) + " fac0_react=" + GetSlotReaction(p, 0) + " states=" + BuildStatesCsv(p))
        ReentrancyGuard = false
        return
    endif

    if akSourceContainer != None
        Faction ownerFac = akSourceContainer.GetFactionOwner()
        int slotIdx = FindFactionSlot(ownerFac)
        if slotIdx >= 0
            bool seen = false
            if VendorNpcRef != None && p.IsDetectedBy(VendorNpcRef)
                seen = true
            endif
            OnTheftObserved(akSourceContainer, 20 * aiItemCount, slotIdx, seen)
        endif
    endif
EndEvent

; ---------------------------------------------------------------- 16-state matrix (fame_tier * 4 + infamy_tier) & Karma math

int Function EvalRepTier(float afScore)
    float clamped = ClampAxis(afScore)
    if clamped >= TierHighCutoff
        return 3
    elseif clamped >= TierMedCutoff
        return 2
    elseif clamped >= TierLowCutoff
        return 1
    endif
    return 0
EndFunction

int Function EvalMatrixStateCode(float afFame, float afInfamy)
    int fTier = EvalRepTier(afFame)
    int iTier = EvalRepTier(afInfamy)
    return (fTier * 4) + iTier
EndFunction

float Function StateVendorBuyMult(int aiStateCode)
    {Exact 16-state vendor buy price multiplier for state = fame_tier * 4 + infamy_tier (independent of Karma).}
    if aiStateCode == 0
        return 1.00
    elseif aiStateCode == 1
        return 1.25
    elseif aiStateCode == 2
        return 1.50
    elseif aiStateCode == 3
        return 1.50
    elseif aiStateCode == 4
        return 0.95
    elseif aiStateCode == 5
        return 1.00
    elseif aiStateCode == 6
        return 1.25
    elseif aiStateCode == 7
        return 1.40
    elseif aiStateCode == 8
        return 0.85
    elseif aiStateCode == 9
        return 0.90
    elseif aiStateCode == 10
        return 1.05
    elseif aiStateCode == 11
        return 1.15
    elseif aiStateCode == 12
        return 0.75
    elseif aiStateCode == 13
        return 0.85
    elseif aiStateCode == 14
        return 0.95
    endif
    return 1.00
EndFunction

string Function StateDispositionName(int aiStateCode)
    if aiStateCode == 12 || aiStateCode == 13
        return "Ally"
    elseif aiStateCode == 4 || aiStateCode == 8 || aiStateCode == 9 || aiStateCode == 14
        return "Friend"
    elseif aiStateCode == 2 || aiStateCode == 3 || aiStateCode == 7
        return "Enemy"
    endif
    return "Neutral"
EndFunction

int Function EvalKarmaTier(float afKarma)
    float k = ClampKarma(afKarma)
    if k <= -750.0
        return -2
    elseif k <= -250.0
        return -1
    elseif k >= 750.0
        return 2
    elseif k >= 250.0
        return 1
    endif
    return 0
EndFunction

int Function EvalCompanionMoralCode(float afKarma)
    float k = ClampKarma(afKarma)
    if k <= -500.0
        return -2
    elseif k <= -250.0
        return -1
    elseif k >= 500.0
        return 1
    endif
    return 0
EndFunction

float Function ClampKarma(float afVal)
    if afVal < -1000.0
        return -1000.0
    elseif afVal > 1000.0
        return 1000.0
    endif
    return afVal
EndFunction

float Function ClampAxis(float afVal)
    if afVal < 0.0
        return 0.0
    elseif afVal > 100.0
        return 100.0
    endif
    return afVal
EndFunction

int Function RivalSlotFor(int aiSlotIdx)
    if FactionCount == 13
        if aiSlotIdx == 1
            return 2
        elseif aiSlotIdx == 2
            return 1
        elseif aiSlotIdx == 4
            return 12
        elseif aiSlotIdx == 12
            return 4
        endif
        return -1
    endif
    if aiSlotIdx == 0
        return 7
    elseif aiSlotIdx == 1
        return 3
    elseif aiSlotIdx == 2
        return 3
    elseif aiSlotIdx == 3
        return 1
    elseif aiSlotIdx == 5
        return 6
    elseif aiSlotIdx == 6
        return 5
    elseif aiSlotIdx == 7
        return 0
    endif
    return -1
EndFunction

; ---------------------------------------------------------------- state synchronization

Function ModifyKarma(Actor akPlayer, float afDelta)
    float nextK = ClampKarma(ReadKarmaValue(akPlayer) + afDelta)
    SetKarmaAbsolute(akPlayer, nextK)
EndFunction

Function SetKarmaAbsolute(Actor akPlayer, float afKarma)
    InitCache()
    float k = ClampKarma(afKarma)
    if CachedKarmaAV != None && akPlayer != None
        akPlayer.SetValue(CachedKarmaAV, k)
    endif
    SyncKarmaOutputs(akPlayer, k)
EndFunction

Function SyncKarmaOutputs(Actor akPlayer, float afKarma)
    InitCache()
    float k = ClampKarma(afKarma)
    int kTier = EvalKarmaTier(k)
    int slideIdx = kTier + 2
    int compCode = EvalCompanionMoralCode(k)

    if CachedKarmaValGlob != None
        CachedKarmaValGlob.SetValue(k)
    endif
    if CachedKarmaTierGlob != None
        CachedKarmaTierGlob.SetValue(kTier as float)
    endif
    if CachedEndingSlideGlob != None
        CachedEndingSlideGlob.SetValue(slideIdx as float)
    endif
    if CachedCompMoralGlob != None
        CachedCompMoralGlob.SetValue(compCode as float)
    endif

    ; Grant active Karma tier dialogue tag perk (0x808..0x80C) and remove the other four
    int targetIdx = kTier + 2
    int i = 0
    while i < 5 && akPlayer != None
        Perk tagPerk = CachedKarmaPerks[i]
        if tagPerk != None
            if i == targetIdx
                if !akPlayer.HasPerk(tagPerk)
                    akPlayer.AddPerk(tagPerk, false)
                endif
            else
                if akPlayer.HasPerk(tagPerk)
                    akPlayer.RemovePerk(tagPerk)
                endif
            endif
        endif
        i += 1
    endwhile
EndFunction

Function ModifyFactionScores(Actor akPlayer, int aiSlotIdx, float afFameDelta, float afInfamyDelta)
    InitCache()
    if aiSlotIdx < 0 || aiSlotIdx >= FactionCount || akPlayer == None
        return
    endif
    ActorValue fameAv = CachedFameAVs[aiSlotIdx]
    ActorValue infAv = CachedInfamyAVs[aiSlotIdx]
    float curFame = 0.0
    float curInf = 0.0
    if fameAv != None
        curFame = akPlayer.GetValue(fameAv)
    endif
    if infAv != None
        curInf = akPlayer.GetValue(infAv)
    endif
    SetFactionScoresAbsolute(akPlayer, aiSlotIdx, curFame + afFameDelta, curInf + afInfamyDelta)
EndFunction

Function SetFactionScoresAbsolute(Actor akPlayer, int aiSlotIdx, float afFame, float afInfamy)
    InitCache()
    if aiSlotIdx < 0 || aiSlotIdx >= FactionCount || akPlayer == None
        return
    endif
    float f = ClampAxis(afFame)
    float inf = ClampAxis(afInfamy)
    ActorValue fameAv = CachedFameAVs[aiSlotIdx]
    ActorValue infAv = CachedInfamyAVs[aiSlotIdx]
    if fameAv != None
        akPlayer.SetValue(fameAv, f)
    endif
    if infAv != None
        akPlayer.SetValue(infAv, inf)
    endif
    SyncSingleFactionSlot(akPlayer, aiSlotIdx)
EndFunction

Function SyncSingleFactionSlot(Actor akPlayer, int aiSlotIdx)
    InitCache()
    if aiSlotIdx < 0 || aiSlotIdx >= FactionCount || akPlayer == None
        return
    endif
    ActorValue fameAv = CachedFameAVs[aiSlotIdx]
    ActorValue infAv = CachedInfamyAVs[aiSlotIdx]
    ActorValue stAv = CachedStateAVs[aiSlotIdx]
    float f = 0.0
    float inf = 0.0
    if fameAv != None
        f = ClampAxis(akPlayer.GetValue(fameAv))
    endif
    if infAv != None
        inf = ClampAxis(akPlayer.GetValue(infAv))
    endif
    int stCode = EvalMatrixStateCode(f, inf)
    if stAv != None
        akPlayer.SetValue(stAv, stCode as float)
    endif

    GlobalVariable fameGl = CachedFameGlobs[aiSlotIdx]
    if fameGl != None
        fameGl.SetValue(f)
    endif
    GlobalVariable infGl = CachedInfamyGlobs[aiSlotIdx]
    if infGl != None
        infGl.SetValue(inf)
    endif
    GlobalVariable stGl = CachedStateGlobs[aiSlotIdx]
    if stGl != None
        stGl.SetValue(stCode as float)
    endif

    Faction fac = CachedFactions[aiSlotIdx]
    ApplyFactionDisposition(fac, CachedPlayerFaction, stCode)
EndFunction

Function ApplyFactionDisposition(Faction akFac, Faction akPlayerFac, int aiStateCode)
    if akFac == None || akPlayerFac == None
        return
    endif
    if aiStateCode == 12 || aiStateCode == 13
        akFac.SetPlayerEnemy(false)
        akFac.SetAlly(akPlayerFac, false, false)
    elseif aiStateCode == 4 || aiStateCode == 8 || aiStateCode == 9 || aiStateCode == 14
        akFac.SetPlayerEnemy(false)
        akFac.SetAlly(akPlayerFac, true, true)
    elseif aiStateCode == 2 || aiStateCode == 3 || aiStateCode == 7
        akFac.SetEnemy(akPlayerFac, false, false)
        akFac.SetPlayerEnemy(true)
    else
        akFac.SetPlayerEnemy(false)
        akFac.SetEnemy(akPlayerFac, true, true)
    endif
EndFunction

Function SyncVendorMult(Actor akPlayer)
    InitCache()
    if akPlayer == None
        return
    endif
    if CachedVendorPerk != None && !akPlayer.HasPerk(CachedVendorPerk)
        akPlayer.AddPerk(CachedVendorPerk, false)
    endif
    int slotIdx = ActiveVendorFactionIdx
    if slotIdx < 0 || slotIdx >= FactionCount
        slotIdx = 0
    endif
    int stCode = ReadSlotState(akPlayer, slotIdx)
    float mult = StateVendorBuyMult(stCode)
    if CachedVendorBuyMultAV != None
        akPlayer.SetValue(CachedVendorBuyMultAV, mult)
    endif
EndFunction

Function SyncAllFromActorValues(Actor akPlayer, bool abIsReload)
    if akPlayer == None
        return
    endif
    InitCache()
    float k = ReadKarmaValue(akPlayer)
    SyncKarmaOutputs(akPlayer, k)
    int i = 0
    while i < FactionCount
        SyncSingleFactionSlot(akPlayer, i)
        i += 1
    endwhile
    SyncVendorMult(akPlayer)
EndFunction

bool Function VerifyReloadParity(Actor akPlayer)
    {Checks that persisted ActorValues and Globals survived save/reload consistently before re-syncing.}
    if akPlayer == None
        return false
    endif
    InitCache()
    float k = ReadKarmaValue(akPlayer)
    if CachedKarmaTierGlob != None
        int wantTier = EvalKarmaTier(k)
        int gotTier = CachedKarmaTierGlob.GetValueInt()
        if wantTier != gotTier
            return false
        endif
    endif
    int i = 0
    while i < FactionCount
        ActorValue fameAv = CachedFameAVs[i]
        ActorValue infAv = CachedInfamyAVs[i]
        ActorValue stAv = CachedStateAVs[i]
        if fameAv != None && infAv != None && stAv != None
            int wantState = EvalMatrixStateCode(akPlayer.GetValue(fameAv), akPlayer.GetValue(infAv))
            int gotState = akPlayer.GetValue(stAv) as int
            if wantState != gotState
                return false
            endif
        endif
        i += 1
    endwhile
    return true
EndFunction

; ---------------------------------------------------------------- helpers & logging

float Function ReadKarmaValue(Actor akPlayer)
    InitCache()
    if CachedKarmaAV == None || akPlayer == None
        return 0.0
    endif
    return ClampKarma(akPlayer.GetValue(CachedKarmaAV))
EndFunction

float Function ReadVendorBuyMult(Actor akPlayer)
    InitCache()
    if CachedVendorBuyMultAV == None || akPlayer == None
        return 1.0
    endif
    return akPlayer.GetValue(CachedVendorBuyMultAV)
EndFunction

int Function ReadSlotState(Actor akPlayer, int aiSlotIdx)
    InitCache()
    if aiSlotIdx < 0 || aiSlotIdx >= FactionCount || akPlayer == None
        return 0
    endif
    ActorValue stAv = CachedStateAVs[aiSlotIdx]
    if stAv == None
        return 0
    endif
    return akPlayer.GetValue(stAv) as int
EndFunction

int Function GetSlotReaction(Actor akPlayer, int aiSlotIdx)
    InitCache()
    if aiSlotIdx < 0 || aiSlotIdx >= FactionCount || akPlayer == None
        return -1
    endif
    Faction fac = CachedFactions[aiSlotIdx]
    if fac == None
        return -1
    endif
    return fac.GetFactionReaction(akPlayer)
EndFunction

int Function FindFactionSlot(Faction akFac)
    if akFac == None
        return -1
    endif
    InitCache()
    int i = 0
    while i < FactionCount
        if CachedFactions[i] == akFac
            return i
        endif
        i += 1
    endwhile
    return -1
EndFunction

int Function FindActorFactionSlot(Actor akActor)
    if akActor == None
        return -1
    endif
    InitCache()
    int i = 0
    while i < FactionCount
        Faction slotFac = CachedFactions[i]
        if slotFac != None && akActor.IsInFaction(slotFac)
            return i
        endif
        i += 1
    endwhile
    return -1
EndFunction

string Function BuildStatesCsv(Actor akPlayer)
    string out = ""
    int i = 0
    while i < FactionCount
        if i > 0
            out = out + ","
        endif
        out = out + ReadSlotState(akPlayer, i)
        i += 1
    endwhile
    return out
EndFunction

Function Trace(string asMsg)
    string line = "FO4SF_REPUTATION rt=" + Utility.GetCurrentRealTime() + " " + asMsg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction
