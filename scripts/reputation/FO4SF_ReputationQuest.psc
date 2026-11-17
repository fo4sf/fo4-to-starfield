Scriptname FO4SF_ReputationQuest extends Quest
{Multi-title Global Karma (-1000..+1000) and 16-state New Vegas Faction Reputation runtime controller.
 Attached to QUST FO4SF_ReputationQuest (0x800 of FO4SFReputation.esm), StartGameEnabled, zero properties.
 Keeps moral Karma and per-faction Fame x Infamy strictly orthogonal so a Very Evil (-1000..-750) player who is
 Idolized by a faction retains Ally disposition and the 0.75x vendor buy multiplier.}

int Version = 1
string LogName = "FO4SFReputation"
string RepPlugin = "FO4SFReputation.esm"
string SfPlugin = "Starfield.esm"
string ProgPlugin = "FO4SFProgression.esm"

; Deterministic local FormIDs in FO4SFReputation.esm
int RepKarmaAvId = 0x000801
int KarmaValueGlobId = 0x000802
int KarmaTierGlobId = 0x000803
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
int FactionCount = 8

int CharityTokenId = 0x000880
int TheftTokenId = 0x000881
int FactionAidTokenId = 0x000882
int FactionCrimeTokenId = 0x000883
int VendorNpcRefId = 0x000893

; Starfield.esm & optional FO4SFProgression.esm FormIDs
int PlayerFactionSfId = 0x01C21C
int ProgKarmaAvId = 0x000807
int ProgKarmaGlobId = 0x00080C

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

; ---------------------------------------------------------------- lifecycle & remote events

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    RegisterHooks(p)
    SyncAllFromActorValues(p, false)
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(RepPlugin) + " prog_installed=" + Game.IsPluginInstalled(ProgPlugin) + " states=" + BuildStatesCsv(p))
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function RegisterHooks(Actor akPlayer)
    if akPlayer != None
        RegisterForRemoteEvent(akPlayer, "OnPlayerLoadGame")
        RegisterForRemoteEvent(akPlayer, "OnKill")
        RegisterForRemoteEvent(akPlayer, "OnPlayerCrimeGold")
        ObjectReference playerObj = akPlayer as ObjectReference
        RegisterForRemoteEvent(playerObj, "OnItemAdded")
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
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

; ---------------------------------------------------------------- stage polling (stages 10..60)

Function PollStages()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif

    if !Done10 && GetStageDone(10)
        Done10 = true
        ; Stage 10: Prove Evil (-800 Very Evil) + Idolized (Minutemen Fame=85, Infamy=0 -> Ally + 0.75x buy_mult) orthogonality
        SetKarmaAbsolute(p, -800.0)
        SetFactionScoresAbsolute(p, 0, 85.0, 0.0)
        ActiveVendorFactionIdx = 0
        SyncAllFromActorValues(p, false)
        int react0 = GetSlotReaction(p, 0)
        float bm0 = ReadVendorBuyMult(p)
        int st0 = ReadSlotState(p, 0)
        string orthOk = "false"
        if (ReadKarmaValue(p) as int) <= -750 && st0 == 3 && react0 == 2 && bm0 > 0.74 && bm0 < 0.76
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
        ; Witnessed theft from Settlers (slot 4): Karma drops AND Settlers Infamy rises to Shunned (state 4)
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
        if rivalIdx >= 0
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
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif

    Form charityTok = Game.GetFormFromFile(CharityTokenId, RepPlugin)
    Form theftTok = Game.GetFormFromFile(TheftTokenId, RepPlugin)
    Form aidTok = Game.GetFormFromFile(FactionAidTokenId, RepPlugin)
    Form crimeTok = Game.GetFormFromFile(FactionCrimeTokenId, RepPlugin)

    if akBaseItem == charityTok || akBaseItem == theftTok || akBaseItem == aidTok || akBaseItem == crimeTok
        ReentrancyGuard = true
        string tokKind = "unknown"
        if akBaseItem == charityTok
            tokKind = "charity"
            ModifyKarma(p, 300.0 * (aiItemCount as float))
        elseif akBaseItem == theftTok
            tokKind = "theft"
            ModifyKarma(p, -350.0 * (aiItemCount as float))
        elseif akBaseItem == aidTok
            tokKind = "faction_aid"
            ModifyFactionScores(p, 0, 80.0 * (aiItemCount as float), 0.0)
            ActiveVendorFactionIdx = 0
            SyncVendorMult(p)
        elseif akBaseItem == crimeTok
            tokKind = "faction_crime"
            ModifyFactionScores(p, 7, 0.0, 80.0 * (aiItemCount as float))
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
            Actor repNpc = Game.GetFormFromFile(VendorNpcRefId, RepPlugin) as Actor
            if repNpc != None && p.IsDetectedBy(repNpc)
                seen = true
            endif
            OnTheftObserved(akSourceContainer, 20 * aiItemCount, slotIdx, seen)
        endif
    endif
EndEvent

; ---------------------------------------------------------------- 16-state matrix & Karma math

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
    return (iTier * 4) + fTier
EndFunction

float Function StateVendorBuyMult(int aiStateCode)
    {Exact 16-state vendor buy price multiplier (strictly independent of Karma).}
    if aiStateCode == 0
        return 1.00
    elseif aiStateCode == 1
        return 0.95
    elseif aiStateCode == 2
        return 0.85
    elseif aiStateCode == 3
        return 0.75
    elseif aiStateCode == 4
        return 1.25
    elseif aiStateCode == 5
        return 1.00
    elseif aiStateCode == 6
        return 0.90
    elseif aiStateCode == 7
        return 0.85
    elseif aiStateCode == 8
        return 1.50
    elseif aiStateCode == 9
        return 1.25
    elseif aiStateCode == 10
        return 1.05
    elseif aiStateCode == 11
        return 0.95
    elseif aiStateCode == 12
        return 1.50
    elseif aiStateCode == 13
        return 1.40
    elseif aiStateCode == 14
        return 1.15
    endif
    return 1.00
EndFunction

string Function StateDispositionName(int aiStateCode)
    if aiStateCode == 3 || aiStateCode == 7
        return "Ally"
    elseif aiStateCode == 1 || aiStateCode == 2 || aiStateCode == 6 || aiStateCode == 11
        return "Friend"
    elseif aiStateCode == 8 || aiStateCode == 12 || aiStateCode == 13
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
    float k = ClampKarma(afKarma)
    ActorValue kAv = Game.GetFormFromFile(RepKarmaAvId, RepPlugin) as ActorValue
    if kAv != None
        akPlayer.SetValue(kAv, k)
    endif
    SyncKarmaOutputs(akPlayer, k)
EndFunction

Function SyncKarmaOutputs(Actor akPlayer, float afKarma)
    float k = ClampKarma(afKarma)
    int kTier = EvalKarmaTier(k)
    int slideIdx = kTier + 2
    int compCode = EvalCompanionMoralCode(k)

    GlobalVariable kValGlob = Game.GetFormFromFile(KarmaValueGlobId, RepPlugin) as GlobalVariable
    if kValGlob != None
        kValGlob.SetValue(k)
    endif
    GlobalVariable kTierGlob = Game.GetFormFromFile(KarmaTierGlobId, RepPlugin) as GlobalVariable
    if kTierGlob != None
        kTierGlob.SetValue(kTier as float)
    endif
    GlobalVariable slideGlob = Game.GetFormFromFile(EndingSlideGlobId, RepPlugin) as GlobalVariable
    if slideGlob != None
        slideGlob.SetValue(slideIdx as float)
    endif
    GlobalVariable compGlob = Game.GetFormFromFile(CompanionMoralGlobId, RepPlugin) as GlobalVariable
    if compGlob != None
        compGlob.SetValue(compCode as float)
    endif

    ; Grant active Karma tier dialogue tag perk (0x808..0x80C) and remove the other four
    int targetIdx = kTier + 2
    int i = 0
    while i < 5
        Perk tagPerk = Game.GetFormFromFile(KarmaPerkFirstId + i, RepPlugin) as Perk
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

    ; Cross-plugin sync with FO4SFProgression.esm when installed
    if Game.IsPluginInstalled(ProgPlugin)
        ActorValue progAv = Game.GetFormFromFile(ProgKarmaAvId, ProgPlugin) as ActorValue
        if progAv != None
            akPlayer.SetValue(progAv, k)
        endif
        GlobalVariable progGlob = Game.GetFormFromFile(ProgKarmaGlobId, ProgPlugin) as GlobalVariable
        if progGlob != None
            progGlob.SetValue(k)
        endif
    endif
EndFunction

Function ModifyFactionScores(Actor akPlayer, int aiSlotIdx, float afFameDelta, float afInfamyDelta)
    ActorValue fameAv = Game.GetFormFromFile(FameAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
    ActorValue infAv = Game.GetFormFromFile(InfamyAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
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
    float f = ClampAxis(afFame)
    float inf = ClampAxis(afInfamy)
    ActorValue fameAv = Game.GetFormFromFile(FameAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
    ActorValue infAv = Game.GetFormFromFile(InfamyAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
    if fameAv != None
        akPlayer.SetValue(fameAv, f)
    endif
    if infAv != None
        akPlayer.SetValue(infAv, inf)
    endif
    SyncSingleFactionSlot(akPlayer, aiSlotIdx)
EndFunction

Function SyncSingleFactionSlot(Actor akPlayer, int aiSlotIdx)
    ActorValue fameAv = Game.GetFormFromFile(FameAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
    ActorValue infAv = Game.GetFormFromFile(InfamyAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
    ActorValue stAv = Game.GetFormFromFile(StateAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
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

    GlobalVariable fameGl = Game.GetFormFromFile(FameGlobFirstId + aiSlotIdx, RepPlugin) as GlobalVariable
    if fameGl != None
        fameGl.SetValue(f)
    endif
    GlobalVariable infGl = Game.GetFormFromFile(InfamyGlobFirstId + aiSlotIdx, RepPlugin) as GlobalVariable
    if infGl != None
        infGl.SetValue(inf)
    endif
    GlobalVariable stGl = Game.GetFormFromFile(StateGlobFirstId + aiSlotIdx, RepPlugin) as GlobalVariable
    if stGl != None
        stGl.SetValue(stCode as float)
    endif

    Faction fac = Game.GetFormFromFile(FactFirstId + aiSlotIdx, RepPlugin) as Faction
    Faction playerFac = Game.GetFormFromFile(PlayerFactionSfId, SfPlugin) as Faction
    ApplyFactionDisposition(fac, playerFac, stCode)
EndFunction

Function ApplyFactionDisposition(Faction akFac, Faction akPlayerFac, int aiStateCode)
    if akFac == None || akPlayerFac == None
        return
    endif
    if aiStateCode == 3 || aiStateCode == 7
        akFac.SetPlayerEnemy(false)
        akFac.SetAlly(akPlayerFac, false, false)
    elseif aiStateCode == 1 || aiStateCode == 2 || aiStateCode == 6 || aiStateCode == 11
        akFac.SetPlayerEnemy(false)
        akFac.SetAlly(akPlayerFac, true, true)
    elseif aiStateCode == 8 || aiStateCode == 12 || aiStateCode == 13
        akFac.SetEnemy(akPlayerFac, false, false)
        akFac.SetPlayerEnemy(true)
    else
        akFac.SetPlayerEnemy(false)
        akFac.SetEnemy(akPlayerFac, true, true)
    endif
EndFunction

Function SyncVendorMult(Actor akPlayer)
    Perk vPerk = Game.GetFormFromFile(RepVendorPerkId, RepPlugin) as Perk
    if vPerk != None && !akPlayer.HasPerk(vPerk)
        akPlayer.AddPerk(vPerk, false)
    endif
    int slotIdx = ActiveVendorFactionIdx
    if slotIdx < 0 || slotIdx >= FactionCount
        slotIdx = 0
    endif
    int stCode = ReadSlotState(akPlayer, slotIdx)
    float mult = StateVendorBuyMult(stCode)
    ActorValue vAv = Game.GetFormFromFile(VendorBuyMultAvId, RepPlugin) as ActorValue
    if vAv != None
        akPlayer.SetValue(vAv, mult)
    endif
EndFunction

Function SyncAllFromActorValues(Actor akPlayer, bool abIsReload)
    if akPlayer == None
        return
    endif
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
    float k = ReadKarmaValue(akPlayer)
    GlobalVariable kTierGlob = Game.GetFormFromFile(KarmaTierGlobId, RepPlugin) as GlobalVariable
    if kTierGlob != None
        int wantTier = EvalKarmaTier(k)
        int gotTier = kTierGlob.GetValueInt()
        if wantTier != gotTier
            return false
        endif
    endif
    int i = 0
    while i < FactionCount
        ActorValue fameAv = Game.GetFormFromFile(FameAvFirstId + i, RepPlugin) as ActorValue
        ActorValue infAv = Game.GetFormFromFile(InfamyAvFirstId + i, RepPlugin) as ActorValue
        ActorValue stAv = Game.GetFormFromFile(StateAvFirstId + i, RepPlugin) as ActorValue
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
    ActorValue kAv = Game.GetFormFromFile(RepKarmaAvId, RepPlugin) as ActorValue
    if kAv == None || akPlayer == None
        return 0.0
    endif
    return ClampKarma(akPlayer.GetValue(kAv))
EndFunction

float Function ReadVendorBuyMult(Actor akPlayer)
    ActorValue vAv = Game.GetFormFromFile(VendorBuyMultAvId, RepPlugin) as ActorValue
    if vAv == None || akPlayer == None
        return 1.0
    endif
    return akPlayer.GetValue(vAv)
EndFunction

int Function ReadSlotState(Actor akPlayer, int aiSlotIdx)
    ActorValue stAv = Game.GetFormFromFile(StateAvFirstId + aiSlotIdx, RepPlugin) as ActorValue
    if stAv == None || akPlayer == None
        return 0
    endif
    return akPlayer.GetValue(stAv) as int
EndFunction

int Function GetSlotReaction(Actor akPlayer, int aiSlotIdx)
    Faction fac = Game.GetFormFromFile(FactFirstId + aiSlotIdx, RepPlugin) as Faction
    if fac == None || akPlayer == None
        return -1
    endif
    return fac.GetFactionReaction(akPlayer)
EndFunction

int Function FindFactionSlot(Faction akFac)
    if akFac == None
        return -1
    endif
    int i = 0
    while i < FactionCount
        Faction slotFac = Game.GetFormFromFile(FactFirstId + i, RepPlugin) as Faction
        if slotFac == akFac
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
    int i = 0
    while i < FactionCount
        Faction slotFac = Game.GetFormFromFile(FactFirstId + i, RepPlugin) as Faction
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
