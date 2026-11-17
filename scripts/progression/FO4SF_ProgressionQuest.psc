Scriptname FO4SF_ProgressionQuest extends Quest
{Player Creation & Progression Core controller (CF-6): 40-pt SPECIAL (with off-by-default 28-pt GLOB), 13 NV skills, 9 Backgrounds, 9 Traits (0..2 + 1 free exit respec), GLOB-driven Perk cadence, and decoupled Karma + 16-state REPU faction disposition sync.}

; Exact property order pinned by dotnet/ProgressionCore/Program.cs and tests/test_progression_core.py
FormList Property SpecialAVList Auto Const
FormList Property SkillAVList Auto Const
FormList Property BackgroundPerks Auto Const
FormList Property TraitPerks Auto Const
FormList Property PlayablePerks Auto Const
FormList Property RepuGlobalsList Auto Const
FormList Property FactionList Auto Const
ActorValue Property KarmaAV Auto Const
GlobalVariable Property KarmaGlobal Auto Const
GlobalVariable Property Pool28Global Auto Const
GlobalVariable Property PerkCadenceGlobal Auto Const
GlobalVariable Property QueuedPerkPointsGlobal Auto Const
GlobalVariable Property QueuedSkillPointsGlobal Auto Const
GlobalVariable Property TraitRespecUsedGlobal Auto Const
ActorValue Property CarryWeightAV Auto Const
ActorValue Property HealthAV Auto Const

int Property TimerIdPoll = 1 AutoReadOnly

int activeBackgroundIdx = -1
int activeTraitIdx0 = -1
int activeTraitIdx1 = -1
int tagSkillIdx0 = -1
int tagSkillIdx1 = -1
int tagSkillIdx2 = -1
float appliedCarryMod = 0.0
float appliedHpMod = 0.0
int lastTrackedLevel = 1

bool ran10 = false
bool ran20 = false
bool ran30 = false
bool ran40 = false
bool ran50 = false

Function LogLine(string kind, string kv)
    Debug.OpenUserLog("FO4SFProgression")
    Debug.TraceUser("FO4SFProgression", "FO4SFPROG rt=" + Utility.GetCurrentRealTime() + " " + kind + " " + kv + " end=true")
EndFunction

ActorValue Function GetSpecialAV(int idx)
    return SpecialAVList.GetAt(idx) as ActorValue
EndFunction

ActorValue Function GetSkillAV(int idx)
    return SkillAVList.GetAt(idx) as ActorValue
EndFunction

int Function GoverningSpecialForSkill(int skillIdx)
    ; 0 Barter(CHA=3), 1 EWp(PER=1), 2 Exp(PER=1), 3 Guns(AGI=5), 4 Lockpick(PER=1),
    ; 5 Med(INT=4), 6 Melee(STR=0), 7 Repair(INT=4), 8 Sci(INT=4), 9 Sneak(AGI=5),
    ; 10 Speech(CHA=3), 11 Survival(END=2), 12 Unarmed(END=2)
    if skillIdx == 0 || skillIdx == 10
        return 3
    elseif skillIdx == 1 || skillIdx == 2 || skillIdx == 4
        return 1
    elseif skillIdx == 3 || skillIdx == 9
        return 5
    elseif skillIdx == 5 || skillIdx == 7 || skillIdx == 8
        return 4
    elseif skillIdx == 6
        return 0
    endif
    return 2
EndFunction

bool Function IsBackgroundSignatureSkill(int bgIdx, int skillIdx)
    ; Matches BACKGROUNDS_TABLE in src/fo4sf/progression/tables.py
    ; 0 Vault Dweller: Science(8), Medicine(5), Speech(10)
    if bgIdx == 0
        return skillIdx == 8 || skillIdx == 5 || skillIdx == 10
    elseif bgIdx == 1
        return skillIdx == 7 || skillIdx == 4 || skillIdx == 11
    elseif bgIdx == 2
        return skillIdx == 3 || skillIdx == 0 || skillIdx == 11
    elseif bgIdx == 3
        return skillIdx == 5 || skillIdx == 8 || skillIdx == 11
    elseif bgIdx == 4
        return skillIdx == 1 || skillIdx == 8 || skillIdx == 7
    elseif bgIdx == 5
        return skillIdx == 1 || skillIdx == 10 || skillIdx == 8
    elseif bgIdx == 6
        return skillIdx == 6 || skillIdx == 9 || skillIdx == 11
    elseif bgIdx == 7
        return skillIdx == 3 || skillIdx == 9 || skillIdx == 11
    elseif bgIdx == 8
        return skillIdx == 3 || skillIdx == 7 || skillIdx == 10
    endif
    return false
EndFunction

bool Function HasSelectedTrait(int traitIdx)
    return activeTraitIdx0 == traitIdx || activeTraitIdx1 == traitIdx
EndFunction

Function ClearListPerks(Actor player, FormList list)
    int n = list.GetSize()
    int i = 0
    while i < n
        Perk p = list.GetAt(i) as Perk
        if p != None && player.HasPerk(p)
            player.RemovePerk(p)
        endif
        i += 1
    endwhile
EndFunction

Function RecomputeSkillsAndDerived(Actor player)
    int strVal = player.GetValue(GetSpecialAV(0)) as int
    int perVal = player.GetValue(GetSpecialAV(1)) as int
    int endVal = player.GetValue(GetSpecialAV(2)) as int
    int chaVal = player.GetValue(GetSpecialAV(3)) as int
    int intVal = player.GetValue(GetSpecialAV(4)) as int
    int agiVal = player.GetValue(GetSpecialAV(5)) as int
    int lckVal = player.GetValue(GetSpecialAV(6)) as int

    if HasSelectedTrait(0) && agiVal < 10
        agiVal += 1 ; Small Frame
    endif
    if HasSelectedTrait(4) && lckVal > 1
        lckVal -= 1 ; Heavy Handed
    endif
    if HasSelectedTrait(5) && perVal > 1
        perVal -= 1 ; Four Eyes
    endif

    int luckHalfCeil = (lckVal + 1) / 2
    int sIdx = 0
    while sIdx < 13
        int govIdx = GoverningSpecialForSkill(sIdx)
        int govVal = endVal
        if govIdx == 0
            govVal = strVal
        elseif govIdx == 1
            govVal = perVal
        elseif govIdx == 3
            govVal = chaVal
        elseif govIdx == 4
            govVal = intVal
        elseif govIdx == 5
            govVal = agiVal
        endif

        int val = 2 + (2 * govVal) + luckHalfCeil
        if IsBackgroundSignatureSkill(activeBackgroundIdx, sIdx)
            val += 10
        endif
        if sIdx == tagSkillIdx0 || sIdx == tagSkillIdx1 || sIdx == tagSkillIdx2
            val += 15
        endif
        if HasSelectedTrait(7) ; Skilled
            val += 5
        endif
        if HasSelectedTrait(6) ; Good Natured
            if sIdx == 0 || sIdx == 5 || sIdx == 7 || sIdx == 8 || sIdx == 10
                val += 5
            elseif sIdx == 1 || sIdx == 2 || sIdx == 3 || sIdx == 6 || sIdx == 12
                val -= 5
            endif
        endif
        if val < 1
            val = 1
        elseif val > 100
            val = 100
        endif
        player.SetValue(GetSkillAV(sIdx), val as float)
        sIdx += 1
    endwhile

    ; Derived CarryWeight delta relative to baseline 150
    float targetCarry = 150.0 + (10.0 * (strVal as float))
    if HasSelectedTrait(0)
        targetCarry -= 15.0
    endif
    float carryDelta = (targetCarry - 150.0) - appliedCarryMod
    if carryDelta > 0.01 || carryDelta < -0.01
        player.ModValue(CarryWeightAV, carryDelta)
        appliedCarryMod += carryDelta
    endif
EndFunction

bool Function ApplyCreationSheet(Actor player, int bgIdx, int t0, int t1, int s0, int s1, int s2, int s3, int s4, int s5, int s6, int tag0, int tag1, int tag2)
    int reqPool = 40
    if Pool28Global.GetValue() >= 0.5
        reqPool = 28
    endif
    int sum = s0 + s1 + s2 + s3 + s4 + s5 + s6
    if sum != reqPool
        LogLine("error", "reason=pool_mismatch sum=" + sum + " required=" + reqPool)
        return false
    endif

    ClearListPerks(player, BackgroundPerks)
    ClearListPerks(player, TraitPerks)

    activeBackgroundIdx = bgIdx
    activeTraitIdx0 = t0
    activeTraitIdx1 = t1
    tagSkillIdx0 = tag0
    tagSkillIdx1 = tag1
    tagSkillIdx2 = tag2

    if bgIdx >= 0 && bgIdx < BackgroundPerks.GetSize()
        Perk bgP = BackgroundPerks.GetAt(bgIdx) as Perk
        if bgP != None
            player.AddPerk(bgP)
        endif
    endif
    if t0 >= 0 && t0 < TraitPerks.GetSize()
        Perk tr0 = TraitPerks.GetAt(t0) as Perk
        if tr0 != None
            player.AddPerk(tr0)
        endif
    endif
    if t1 >= 0 && t1 != t0 && t1 < TraitPerks.GetSize()
        Perk tr1 = TraitPerks.GetAt(t1) as Perk
        if tr1 != None
            player.AddPerk(tr1)
        endif
    endif

    player.SetValue(GetSpecialAV(0), s0 as float)
    player.SetValue(GetSpecialAV(1), s1 as float)
    player.SetValue(GetSpecialAV(2), s2 as float)
    player.SetValue(GetSpecialAV(3), s3 as float)
    player.SetValue(GetSpecialAV(4), s4 as float)
    player.SetValue(GetSpecialAV(5), s5 as float)
    player.SetValue(GetSpecialAV(6), s6 as float)

    RecomputeSkillsAndDerived(player)
    return true
EndFunction

bool Function ApplyExitTraitRespec(Actor player, int newT0, int newT1)
    if TraitRespecUsedGlobal.GetValue() >= 0.5
        return false
    endif
    ClearListPerks(player, TraitPerks)
    activeTraitIdx0 = newT0
    activeTraitIdx1 = newT1
    if newT0 >= 0 && newT0 < TraitPerks.GetSize()
        Perk tr0 = TraitPerks.GetAt(newT0) as Perk
        if tr0 != None
            player.AddPerk(tr0)
        endif
    endif
    if newT1 >= 0 && newT1 != newT0 && newT1 < TraitPerks.GetSize()
        Perk tr1 = TraitPerks.GetAt(newT1) as Perk
        if tr1 != None
            player.AddPerk(tr1)
        endif
    endif
    TraitRespecUsedGlobal.SetValue(1.0)
    RecomputeSkillsAndDerived(player)
    return true
EndFunction

bool Function GrantsPerkAtLevel(int levelNum)
    int cad = PerkCadenceGlobal.GetValue() as int
    if cad < 1
        cad = 1
    endif
    if levelNum < 2
        return false
    endif
    if cad == 1
        return true
    endif
    return (levelNum % cad) == 0
EndFunction

string Function KarmaTierToken(float k)
    if k <= -750.0
        return "Very_Evil"
    elseif k <= -250.0
        return "Evil"
    elseif k < 250.0
        return "Neutral"
    elseif k < 750.0
        return "Good"
    endif
    return "Very_Good"
EndFunction

int Function RepuAxisTier(float v)
    if v >= 75.0
        return 3
    elseif v >= 45.0
        return 2
    elseif v >= 15.0
        return 1
    endif
    return 0
EndFunction

string Function SyncFactionRepu(int factionIdx, float fame, float infamy)
    int pairBase = factionIdx * 2
    GlobalVariable fameG = RepuGlobalsList.GetAt(pairBase) as GlobalVariable
    GlobalVariable infamyG = RepuGlobalsList.GetAt(pairBase + 1) as GlobalVariable
    if fameG != None
        fameG.SetValue(fame)
    endif
    if infamyG != None
        infamyG.SetValue(infamy)
    endif

    int ft = RepuAxisTier(fame)
    int it = RepuAxisTier(infamy)
    Faction fac = FactionList.GetAt(factionIdx) as Faction
    Faction playerFac = Game.GetFormFromFile(0x0001C21C, "Starfield.esm") as Faction

    string disp = "Neutral"
    if it >= 2 && ft <= 1
        disp = "Enemy"
        if fac != None && playerFac != None
            fac.SetEnemy(playerFac, false, false)
        endif
    elseif ft >= 2 && it == 0
        disp = "Ally"
        if fac != None && playerFac != None
            fac.SetAlly(playerFac, false, false)
        endif
    else
        if fac != None && playerFac != None
            fac.SetEnemy(playerFac, true, true) ; Neutral
        endif
    endif

    if ft == 3 && it == 0
        return "Idolized:" + disp
    elseif ft == 0 && it == 3
        return "Vilified:" + disp
    elseif ft == 3 && it == 3
        return "Wild_Child:" + disp
    endif
    return "Standing_" + ft + "_" + it + ":" + disp
EndFunction

Event OnQuestInit()
    Actor player = Game.GetPlayer()
    if player != None
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        lastTrackedLevel = player.GetLevel()
    endif
    LogLine("init", "pool28=" + (Pool28Global.GetValue() as int) + " cadence=" + (PerkCadenceGlobal.GetValue() as int) + " respec_used=" + (TraitRespecUsedGlobal.GetValue() as int))
    StartTimer(1.0, TimerIdPoll)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    StartTimer(1.0, TimerIdPoll)
EndEvent

Function PollStages()
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif

    ; Passive level-up watcher queueing skill & GLOB-cadence perk points
    int curLv = player.GetLevel()
    while lastTrackedLevel < curLv
        lastTrackedLevel += 1
        int intStat = player.GetValue(GetSpecialAV(4)) as int
        int spGain = 10 + (intStat / 2)
        Perk edu = PlayablePerks.GetAt(0) as Perk
        if edu != None && player.HasPerk(edu)
            spGain += 2
        endif
        QueuedSkillPointsGlobal.SetValue(QueuedSkillPointsGlobal.GetValue() + (spGain as float))
        if GrantsPerkAtLevel(lastTrackedLevel)
            QueuedPerkPointsGlobal.SetValue(QueuedPerkPointsGlobal.GetValue() + 1.0)
        endif
    endwhile

    ; Stage 10: Run Creation Flow (Vault Dweller + Good Natured & Small Frame + 40-pt SPECIAL 6/5/5/6/7/6/5 + Tags Speech/Guns/Lockpick)
    if !ran10 && GetStageDone(10)
        ran10 = true
        TraitRespecUsedGlobal.SetValue(0.0)
        Pool28Global.SetValue(0.0)
        bool ok = ApplyCreationSheet(player, 0, 6, 0, 6, 5, 5, 6, 7, 6, 5, 10, 3, 4)
        float spc = player.GetValue(GetSkillAV(10))
        float sci = player.GetValue(GetSkillAV(8))
        float med = player.GetValue(GetSkillAV(5))
        LogLine("creation", "ok=" + ok + " bg=Vault_Dweller traits=2 special_sum=40 skills_count=13 speech=" + (spc as int) + " science=" + (sci as int) + " medicine=" + (med as int) + " carry_mod=" + appliedCarryMod)
    endif

    ; Stage 20: Vault Exit Free Trait Respec (1st succeeds -> Trigger Discipline only; 2nd is refused because respec_used == 1)
    if !ran20 && GetStageDone(20)
        ran20 = true
        bool firstOk = ApplyExitTraitRespec(player, 1, -1)
        bool secondOk = ApplyExitTraitRespec(player, 2, -1)
        LogLine("respec", "first_ok=" + firstOk + " second_refused=" + (!secondOk) + " active_traits=1")
    endif

    ; Stage 30: GLOB-Driven Perk Cadence (default 2 -> true/false/true at lv 2/3/4; switch GLOB to 1 -> true at lv 3)
    if !ran30 && GetStageDone(30)
        ran30 = true
        PerkCadenceGlobal.SetValue(2.0)
        bool c2_2 = GrantsPerkAtLevel(2)
        bool c2_3 = GrantsPerkAtLevel(3)
        bool c2_4 = GrantsPerkAtLevel(4)
        PerkCadenceGlobal.SetValue(1.0)
        bool c1_3 = GrantsPerkAtLevel(3)
        PerkCadenceGlobal.SetValue(2.0)
        LogLine("cadence", "cad2_lvl2=" + c2_2 + " cad2_lvl3=" + c2_3 + " cad2_lvl4=" + c2_4 + " cad1_lvl3=" + c1_3)
    endif

    ; Stage 40: Decoupled Karma (-800 Very Evil) + Minutemen REPU (Fame 85, Infamy 0 -> Idolized & Ally)
    if !ran40 && GetStageDone(40)
        ran40 = true
        player.SetValue(KarmaAV, -800.0)
        KarmaGlobal.SetValue(-800.0)
        string kt = KarmaTierToken(-800.0)
        string repuOut = SyncFactionRepu(0, 85.0, 0.0)
        string rTitle = "Idolized"
        string rDisp = "Ally"
        if repuOut != "Idolized:Ally"
            rTitle = repuOut
            rDisp = "Mismatch"
        endif
        LogLine("karma_repu", "karma=-800.0 karma_tier=" + kt + " faction=Minutemen fame=85.0 infamy=0.0 repu_title=" + rTitle + " disposition=" + rDisp)
    endif

    ; Stage 50: Clean Reset
    if !ran50 && GetStageDone(50)
        ran50 = true
        ClearListPerks(player, BackgroundPerks)
        ClearListPerks(player, TraitPerks)
        if appliedCarryMod > 0.01 || appliedCarryMod < -0.01
            player.ModValue(CarryWeightAV, -appliedCarryMod)
            appliedCarryMod = 0.0
        endif
        player.SetValue(KarmaAV, 0.0)
        KarmaGlobal.SetValue(0.0)
        SyncFactionRepu(0, 0.0, 0.0)
        TraitRespecUsedGlobal.SetValue(0.0)
        LogLine("summary", "ok=true stages=10,20,30,40,50")
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TimerIdPoll
        PollStages()
        StartTimer(1.0, TimerIdPoll)
    endif
EndEvent
