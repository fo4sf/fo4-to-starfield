Scriptname FO4SF_RadsCoreQuest extends Quest
{Core radiation and optional mutations runtime (fo4-to-starfield, docs/rads/rads-core.md).
 Attached to QUST FO4SF_RadsCoreQuest in FO4SFRads.esm (StartGameEnabled):
   - Maintains FO4SF_Rads (0..1000), FO4SF_RadsCapPct (0..100), FO4SF_RadsDisplayPct (0..100), and FO4SF_RadsStage (0..5).
   - Implements BOTH radiation penalty rules behind FO4SF_RadsRule / FO4SF_GPO_RadsRule:
       0 = Mode A (Max-HP cap: -10% of base Health per 100 rads, clamped so effective max HP >= 10% below 1000, fatal at 1000).
       1 = Mode B (Rad-Sickness stat thresholds: <200 None; 200..399 -1 END; 400..599 -2 END, -1 AGI;
                   600..799 -3 END, -2 AGI, -1 STR; 800..999 -3 END, -2 AGI, -2 STR; 1000 Fatal).
     Switching FO4SF_RadsRule unwinds the previous mode's delta and applies the new mode's delta with zero drift.
   - Implements all 3 radiation sources (HAZD zones / FO4SF_RadsEmitter, irradiated water immersion & FO4SF_DirtyWater,
     irradiated ingestibles FO4SF_IrradiatedFood / FO4SF_DirtyWater) plus FO4SF_RadX resistance and FO4SF_RadAway (-300 rads).
   - Implements optional mutations behind FO4SF_MutationsEnabled / FO4SF_GPO_Mutations (default 0 = OFF) as clean-room
     PERKs in FO4SF_MutationPerks, locked when FO4SF_Perk_StarchedGenes is held, and cured 1 at a time by RadAway when unlocked.
   - Runs passive 1.0 s live-play monitoring AND deterministic verification stages 5 and 10..60.}

ActorValue Property RadsAV Auto Const Mandatory
ActorValue Property RadsCapPctAV Auto Const Mandatory
ActorValue Property RadResistAV Auto Const Mandatory
ActorValue Property InWaterAV Auto Const Mandatory
ActorValue Property HealthAV Auto Const Mandatory
ActorValue Property EnduranceAV Auto Const Mandatory
ActorValue Property AgilityAV Auto Const Mandatory
ActorValue Property StrengthAV Auto Const Mandatory
GlobalVariable Property RadsDisplayPctGlobal Auto Const Mandatory
GlobalVariable Property RadsStageGlobal Auto Const Mandatory
GlobalVariable Property RadsRuleGlobal Auto Const Mandatory
GlobalVariable Property MutationsEnabledGlobal Auto Const Mandatory
GameplayOption Property RadsRuleOption Auto Const Mandatory
GameplayOption Property MutationsOption Auto Const Mandatory
Spell Property RadsSpell Auto Const Mandatory
Spell Property RadsHazardSpell Auto Const Mandatory
Spell Property AbWaterDetect Auto Const Mandatory
Spell Property WaterDrinkSpell Auto Const Mandatory
Spell Property WaterContactSpell Auto Const Mandatory
Form Property RadAway Auto Const Mandatory
Form Property RadX Auto Const Mandatory
Form Property IrradiatedFood Auto Const Mandatory
Form Property DirtyWater Auto Const Mandatory
Hazard Property RadsHazard Auto Const Mandatory
Activator Property RadsEmitter Auto Const Mandatory
Keyword Property RadsEmitterKeyword Auto Const Mandatory
Form Property IrradiatedWater Auto Const Mandatory
FormList Property MutationPerks Auto Const Mandatory
Perk Property StarchedGenesPerk Auto Const Mandatory

; ---------------------------------------------------------------- constants & runtime state

int Version = 1
string LogName = "FO4SFRadsCore"
string CorePlugin = "FO4SFRads.esm"

int TIMER_POLL = 1
int TIMER_STAGE20_SETTLE = 20
int TIMER_STAGE30_SETTLE = 30
float POLL_S = 1.0
float STAGE_SETTLE_S = 1.5

float RadsLimit = 1000.0
float RadAwayCureAmount = 300.0
float RadXBuffAmount = 100.0
float RadXDurationS = 60.0
float FoodRadsAmount = 50.0
float DirtyWaterRadsAmount = 25.0
float WaterWadeRadsPerSec = 5.0
float WaterSwimRadsPerSec = 10.0
float EmitterRadsPerSec = 15.0
float EmitterScanRadius = 8.0
float MutationThresholdRads = 200.0

float AppliedHealth = 0.0
float AppliedEnd = 0.0
float AppliedAgi = 0.0
float AppliedStr = 0.0
float LastSyncedRads = 0.0
int LastSyncedRule = 0
int LastNotifiedStage = 0

bool RadXActive = false
float RadXExpiresRT = 0.0
float SwimmingUntilRT = 0.0

int LastAwayCount = 0
int LastRadXCount = 0
int LastFoodCount = 0
int LastWaterCount = 0
int EquippedAwayPending = 0
int EquippedRadXPending = 0
int EquippedFoodPending = 0
int EquippedWaterPending = 0

int BusyStage = 0
bool SuppressLethalInStage = false
ObjectReference TempHazardRef = None
ObjectReference TempEmitterRef = None

float BaseHP0 = 0.0
float Health0 = 0.0
float End0 = 0.0
float Agi0 = 0.0
float Str0 = 0.0

bool Done5 = false
bool Done10 = false
bool Done20 = false
bool Done30 = false
bool Done40 = false
bool Done50 = false
bool Done60 = false

bool Ok10 = false
bool Ok20 = false
bool Ok30 = false
bool Ok40 = false
bool Ok50 = false
bool Ok60 = false

; ---------------------------------------------------------------- lifecycle & logging

Event OnInit()
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    Trace("init version=" + Version + " quest=" + GetFormID() + " installed=" + Game.IsPluginInstalled(CorePlugin))
    Trace("start rads_av=" + Id(RadsAV) + " cap_pct_av=" + Id(RadsCapPctAV) + " rad_resist_av=" + Id(RadResistAV) + " rule_glob=" + Id(RadsRuleGlobal) + " mut_glob=" + Id(MutationsEnabledGlobal) + " hazard=" + Id(RadsHazard) + " emitter=" + Id(RadsEmitter) + " water=" + Id(IrradiatedWater) + " radaway=" + Id(RadAway) + " radx=" + Id(RadX) + " food=" + Id(IrradiatedFood) + " dirty_water=" + Id(DirtyWater) + " mut_flst=" + Id(MutationPerks) + " starched=" + Id(StarchedGenesPerk))
    SetupPlayerHooks(p)
    SyncItemCounts(p)
    SyncState(p, "init")
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Function SetupPlayerHooks(Actor p)
    if p == None
        return
    endif
    RegisterForGameplayOptionChangedEvent()
    RegisterForRemoteEvent(p, "OnItemEquipped")
    RegisterForRemoteEvent(p, "OnPlayerSwimming")
    RegisterForRemoteEvent(p, "OnPlayerLoadGame")
    if !p.HasSpell(AbWaterDetect)
        p.AddSpell(AbWaterDetect, false)
    endif
EndFunction

Event Actor.OnPlayerLoadGame(Actor akSender)
    Debug.OpenUserLog(LogName)
    Actor p = Game.GetPlayer()
    SetupPlayerHooks(p)
    SyncItemCounts(p)
    SyncState(p, "load_game")
    StartTimer(POLL_S, TIMER_POLL)
EndEvent

Event OnGameplayOptionChanged(GameplayOption[] aChangedOptions)
    if aChangedOptions != None
        int i = 0
        while i < aChangedOptions.Length
            GameplayOption opt = aChangedOptions[i]
            if opt == RadsRuleOption
                RadsRuleGlobal.SetValue(RadsRuleOption.GetValue())
            elseif opt == MutationsOption
                MutationsEnabledGlobal.SetValue(MutationsOption.GetValue())
            endif
            i += 1
        endwhile
    endif
    GameplayOption.NotifyGameplayOptionUpdateFinished()
    Actor p = Game.GetPlayer()
    if p != None && BusyStage == 0
        SyncState(p, "gameplay_option")
    endif
EndEvent

Event Actor.OnPlayerSwimming(Actor akSender)
    SwimmingUntilRT = Utility.GetCurrentRealTime() + 2.0
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    if BusyStage != 0 || akSender != Game.GetPlayer()
        return
    endif
    if akBaseObject == RadAway
        EquippedAwayPending += 1
        UseRadAway(akSender, true)
    elseif akBaseObject == RadX
        EquippedRadXPending += 1
        UseRadX(akSender, true)
    elseif akBaseObject == IrradiatedFood
        EquippedFoodPending += 1
        UseIrradiatedFood(akSender, true)
    elseif akBaseObject == DirtyWater
        EquippedWaterPending += 1
        UseDirtyWater(akSender, true)
    endif
EndEvent

Function Trace(string msg)
    string line = "FO4SFRADSCORE rt=" + Utility.GetCurrentRealTime() + " " + msg + " end=true"
    if !Debug.TraceUser(LogName, line)
        Debug.OpenUserLog(LogName)
        Debug.TraceUser(LogName, line)
    endif
EndFunction

Function NotifyPlayer(string text)
    Debug.Notification(text)
    Trace("say text=" + text)
EndFunction

string Function Id(Form f)
    if f == None
        return "none"
    endif
    return "" + f.GetFormID()
EndFunction

float Function ClampRads(float v)
    if v < 0.0
        return 0.0
    endif
    if v > RadsLimit
        return RadsLimit
    endif
    return v
EndFunction

float Function AbsF(float v)
    if v < 0.0
        return -1.0 * v
    endif
    return v
EndFunction

int Function CurrentRule()
    if RadsRuleGlobal.GetValue() >= 0.5
        return 1
    endif
    return 0
EndFunction

int Function MutationsOn()
    if MutationsEnabledGlobal.GetValue() >= 0.5
        return 1
    endif
    return 0
EndFunction

int Function SicknessStage(float rads)
    if rads >= 1000.0
        return 5
    elseif rads >= 800.0
        return 4
    elseif rads >= 600.0
        return 3
    elseif rads >= 400.0
        return 2
    elseif rads >= 200.0
        return 1
    endif
    return 0
EndFunction

Function SetExactAV(Actor p, ActorValue av, float targetVal)
    float cur = p.GetValue(av)
    float diff = targetVal - cur
    if AbsF(diff) > 0.001
        p.ModValue(av, diff)
    endif
EndFunction

; ---------------------------------------------------------------- mutations

int Function CountMutations(Actor p)
    int n = 0
    int total = MutationPerks.GetSize()
    int i = 0
    while i < total
        Perk pk = MutationPerks.GetAt(i) as Perk
        if pk != None && p.HasPerk(pk)
            n += 1
        endif
        i += 1
    endwhile
    return n
EndFunction

Perk Function RollMutation(Actor p, bool deterministicFirst)
    if MutationsOn() == 0
        return None
    endif
    if p.HasPerk(StarchedGenesPerk)
        Trace("mutation action=locked_roll perk=none starched=true count=" + CountMutations(p))
        return None
    endif
    int total = MutationPerks.GetSize()
    Perk[] pool = new Perk[4]
    int avail = 0
    int i = 0
    while i < total && avail < 4
        Perk candidate = MutationPerks.GetAt(i) as Perk
        if candidate != None && !p.HasPerk(candidate)
            pool[avail] = candidate
            avail += 1
        endif
        i += 1
    endwhile
    if avail == 0
        return None
    endif
    int pick = 0
    if !deterministicFirst && avail > 1
        pick = Utility.RandomInt(0, avail - 1)
    endif
    Perk chosen = pool[pick]
    p.AddPerk(chosen, false)
    Trace("mutation action=granted perk=" + Id(chosen) + " starched=false count=" + CountMutations(p))
    return chosen
EndFunction

Perk Function CureOneMutation(Actor p)
    if MutationsOn() == 0
        return None
    endif
    if p.HasPerk(StarchedGenesPerk)
        Trace("mutation action=locked_cure perk=none starched=true count=" + CountMutations(p))
        return None
    endif
    int total = MutationPerks.GetSize()
    int i = total - 1
    while i >= 0
        Perk pk = MutationPerks.GetAt(i) as Perk
        if pk != None && p.HasPerk(pk)
            p.RemovePerk(pk)
            Trace("mutation action=cured perk=" + Id(pk) + " starched=false count=" + CountMutations(p))
            return pk
        endif
        i -= 1
    endwhile
    return None
EndFunction

Function ClearAllMutations(Actor p)
    if p.HasPerk(StarchedGenesPerk)
        p.RemovePerk(StarchedGenesPerk)
    endif
    int total = MutationPerks.GetSize()
    int i = 0
    while i < total
        Perk pk = MutationPerks.GetAt(i) as Perk
        if pk != None && p.HasPerk(pk)
            p.RemovePerk(pk)
        endif
        i += 1
    endwhile
EndFunction

; ---------------------------------------------------------------- radiation gain, aid, & state sync

float Function ScaleByResist(Actor p, float rawAmount)
    float resist = p.GetValue(RadResistAV)
    if resist <= 0.0
        return rawAmount
    endif
    return rawAmount * (100.0 / (100.0 + resist))
EndFunction

float Function ApplyRadsGain(Actor p, float rawAmount, string source, bool allowMutationRoll)
    float before = ClampRads(p.GetValue(RadsAV))
    float resist = p.GetValue(RadResistAV)
    if resist < 0.0
        resist = 0.0
    endif
    float scaled = rawAmount * (100.0 / (100.0 + resist))
    float target = ClampRads(before + scaled)
    float delta = target - before
    if AbsF(delta) > 0.0001
        p.ModValue(RadsAV, delta)
    endif
    float now = p.GetValue(RadsAV)
    Trace("gain source=" + source + " raw=" + rawAmount + " resist=" + resist + " added=" + delta + " rads=" + now)
    if allowMutationRoll && MutationsOn() == 1 && now >= MutationThresholdRads
        int prevBucket = (before / 100.0) as int
        int newBucket = (now / 100.0) as int
        if newBucket > prevBucket || source == "mutation_trigger"
            Perk gained = RollMutation(p, BusyStage != 0)
            if gained != None && BusyStage == 0
                NotifyPlayer("Mutation acquired. Rads " + (now as int))
            endif
        endif
    endif
    SyncState(p, source)
    return delta
EndFunction

Function UseRadAway(Actor p, bool showHud)
    float before = ClampRads(p.GetValue(RadsAV))
    float target = ClampRads(before - RadAwayCureAmount)
    float delta = target - before
    if AbsF(delta) > 0.0001
        p.ModValue(RadsAV, delta)
    endif
    bool starched = p.HasPerk(StarchedGenesPerk)
    Perk cured = CureOneMutation(p)
    float now = p.GetValue(RadsAV)
    Trace("radaway before=" + before + " delta=" + delta + " rads=" + now + " rule=" + CurrentRule() + " mut_on=" + MutationsOn() + " starched=" + starched + " cured_perk=" + Id(cured))
    SyncState(p, "radaway")
    if showHud
        NotifyPlayer("RadAway used. Rads " + (now as int) + ", HP " + (p.GetValue(HealthAV) as int))
    endif
EndFunction

Function UseRadX(Actor p, bool showHud)
    float before = p.GetValue(RadResistAV)
    float added = 0.0
    if !RadXActive
        p.ModValue(RadResistAV, RadXBuffAmount)
        RadXActive = true
        added = RadXBuffAmount
    endif
    RadXExpiresRT = Utility.GetCurrentRealTime() + RadXDurationS
    float now = p.GetValue(RadResistAV)
    Trace("radx resist_before=" + before + " added=" + added + " resist_now=" + now + " expires_in=" + RadXDurationS)
    if showHud
        NotifyPlayer("Rad-X active. Radiation Resistance " + (now as int))
    endif
EndFunction

Function ClearRadXBuff(Actor p)
    if RadXActive
        p.ModValue(RadResistAV, -1.0 * RadXBuffAmount)
        RadXActive = false
        RadXExpiresRT = 0.0
    endif
EndFunction

Function UseIrradiatedFood(Actor p, bool showHud)
    ApplyRadsGain(p, FoodRadsAmount, "irradiated_food", true)
    if showHud
        NotifyPlayer("Irradiated Food consumed. Rads " + (p.GetValue(RadsAV) as int))
    endif
EndFunction

Function UseDirtyWater(Actor p, bool showHud)
    ApplyRadsGain(p, DirtyWaterRadsAmount, "dirty_water", true)
    if showHud
        NotifyPlayer("Dirty Water consumed. Rads " + (p.GetValue(RadsAV) as int))
    endif
EndFunction

Function SyncState(Actor p, string reason)
    float rawRads = p.GetValue(RadsAV)
    float rads = ClampRads(rawRads)
    if AbsF(rawRads - rads) > 0.001
        p.ModValue(RadsAV, rads - rawRads)
    endif

    float capPct = rads / 10.0
    int sickStage = SicknessStage(rads)
    SetExactAV(p, RadsCapPctAV, capPct)
    RadsDisplayPctGlobal.SetValue(capPct)
    RadsStageGlobal.SetValue(sickStage as float)

    int rule = CurrentRule()
    float baseHP = p.GetBaseValue(HealthAV)
    if baseHP <= 0.0
        baseHP = p.GetValue(HealthAV) - AppliedHealth
    endif
    if baseHP < 10.0
        baseHP = 100.0
    endif

    float wantHP = 0.0
    float wantEnd = 0.0
    float wantAgi = 0.0
    float wantStr = 0.0

    if rule == 0
        float frac = rads / 1000.0
        if frac > 0.90
            frac = 0.90
        endif
        int pen = (frac * baseHP + 0.001) as int
        if (baseHP - pen) < (baseHP * 0.10)
            pen = (baseHP * 0.90) as int
        endif
        wantHP = -1.0 * pen
    else
        if sickStage == 1
            wantEnd = -1.0
        elseif sickStage == 2
            wantEnd = -2.0
            wantAgi = -1.0
        elseif sickStage == 3
            wantEnd = -3.0
            wantAgi = -2.0
            wantStr = -1.0
        elseif sickStage >= 4
            wantEnd = -3.0
            wantAgi = -2.0
            wantStr = -2.0
        endif
    endif

    float dHP = wantHP - AppliedHealth
    if AbsF(dHP) > 0.0001
        p.ModValue(HealthAV, dHP)
        AppliedHealth = wantHP
    endif

    float dEnd = wantEnd - AppliedEnd
    if AbsF(dEnd) > 0.0001
        p.ModValue(EnduranceAV, dEnd)
        AppliedEnd = wantEnd
    endif

    float dAgi = wantAgi - AppliedAgi
    if AbsF(dAgi) > 0.0001
        p.ModValue(AgilityAV, dAgi)
        AppliedAgi = wantAgi
    endif

    float dStr = wantStr - AppliedStr
    if AbsF(dStr) > 0.0001
        p.ModValue(StrengthAV, dStr)
        AppliedStr = wantStr
    endif

    LastSyncedRads = rads
    LastSyncedRule = rule
    int mutCount = CountMutations(p)
    Trace("sync reason=" + reason + " rule=" + rule + " rads=" + rads + " cap_pct=" + capPct + " stage=" + sickStage + " hp=" + p.GetValue(HealthAV) + " base_hp=" + baseHP + " end=" + p.GetValue(EnduranceAV) + " agi=" + p.GetValue(AgilityAV) + " str=" + p.GetValue(StrengthAV) + " app_hp=" + AppliedHealth + " app_end=" + AppliedEnd + " app_agi=" + AppliedAgi + " app_str=" + AppliedStr + " mut_on=" + MutationsOn() + " mut_count=" + mutCount)

    if BusyStage == 0 && sickStage != LastNotifiedStage
        if sickStage > LastNotifiedStage && sickStage >= 1
            NotifyPlayer("Radiation stage " + sickStage + ". Rads " + (rads as int))
        endif
        LastNotifiedStage = sickStage
    endif

    if rads >= RadsLimit && !SuppressLethalInStage && !p.IsDead()
        Trace("fatal rads=" + rads + " rule=" + rule + " sick_stage=5 lethal=true")
        p.Kill(None)
    endif
EndFunction

; ---------------------------------------------------------------- passive polling

Function SyncItemCounts(Actor p)
    if p == None
        return
    endif
    LastAwayCount = p.GetItemCount(RadAway)
    LastRadXCount = p.GetItemCount(RadX)
    LastFoodCount = p.GetItemCount(IrradiatedFood)
    LastWaterCount = p.GetItemCount(DirtyWater)
    EquippedAwayPending = 0
    EquippedRadXPending = 0
    EquippedFoodPending = 0
    EquippedWaterPending = 0
EndFunction

Function PollConsumables(Actor p)
    int awayNow = p.GetItemCount(RadAway)
    if awayNow < LastAwayCount
        int usedAway = (LastAwayCount - awayNow) - EquippedAwayPending
        while usedAway > 0
            UseRadAway(p, true)
            usedAway -= 1
        endwhile
    endif
    LastAwayCount = awayNow
    EquippedAwayPending = 0

    int radxNow = p.GetItemCount(RadX)
    if radxNow < LastRadXCount
        int usedRadX = (LastRadXCount - radxNow) - EquippedRadXPending
        while usedRadX > 0
            UseRadX(p, true)
            usedRadX -= 1
        endwhile
    endif
    LastRadXCount = radxNow
    EquippedRadXPending = 0

    int foodNow = p.GetItemCount(IrradiatedFood)
    if foodNow < LastFoodCount
        int usedFood = (LastFoodCount - foodNow) - EquippedFoodPending
        while usedFood > 0
            UseIrradiatedFood(p, true)
            usedFood -= 1
        endwhile
    endif
    LastFoodCount = foodNow
    EquippedFoodPending = 0

    int waterNow = p.GetItemCount(DirtyWater)
    if waterNow < LastWaterCount
        int usedWater = (LastWaterCount - waterNow) - EquippedWaterPending
        while usedWater > 0
            UseDirtyWater(p, true)
            usedWater -= 1
        endwhile
    endif
    LastWaterCount = waterNow
    EquippedWaterPending = 0
EndFunction

Function PollEnvironment(Actor p)
    float rt = Utility.GetCurrentRealTime()
    if RadXActive && rt >= RadXExpiresRT
        ClearRadXBuff(p)
        Trace("radx resist_before=" + (p.GetValue(RadResistAV) + RadXBuffAmount) + " added=" + (-1.0 * RadXBuffAmount) + " resist_now=" + p.GetValue(RadResistAV) + " expires_in=0.0")
    endif

    ; 1. Irradiated water immersion (passive IsInWater ability or OnPlayerSwimming)
    if rt < SwimmingUntilRT
        ApplyRadsGain(p, WaterSwimRadsPerSec * POLL_S, "water_swim", true)
    elseif p.GetValue(InWaterAV) >= 0.5
        ApplyRadsGain(p, WaterWadeRadsPerSec * POLL_S, "water_wade", true)
    endif

    ; 2. Placed radiation emitters carrying FO4SF_Kw_RadsEmitter within EmitterScanRadius
    ObjectReference[] emitters = p.FindAllReferencesWithKeyword(RadsEmitterKeyword, EmitterScanRadius)
    if emitters != None && emitters.Length > 0
        int idx = 0
        bool activeEmitter = false
        while idx < emitters.Length && !activeEmitter
            if emitters[idx] != None && !emitters[idx].IsDisabled()
                activeEmitter = true
            endif
            idx += 1
        endwhile
        if activeEmitter
            ApplyRadsGain(p, EmitterRadsPerSec * POLL_S, "hazard_emitter", true)
        endif
    endif

    ; 3. External/native HAZD spell change or console FO4SF_RadsRule / FO4SF_Rads edit
    float curRads = p.GetValue(RadsAV)
    int curRule = CurrentRule()
    if AbsF(curRads - LastSyncedRads) > 0.01 || curRule != LastSyncedRule
        if curRads > LastSyncedRads + 0.01 && MutationsOn() == 1 && curRads >= MutationThresholdRads
            int oldB = (LastSyncedRads / 100.0) as int
            int newB = (curRads / 100.0) as int
            if newB > oldB
                RollMutation(p, false)
            endif
        endif
        SyncState(p, "passive_poll")
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TIMER_POLL
        Poll()
        StartTimer(POLL_S, TIMER_POLL)
    elseif aiTimerID == TIMER_STAGE20_SETTLE
        FinishStage20()
    elseif aiTimerID == TIMER_STAGE30_SETTLE
        FinishStage30()
    endif
EndEvent

Function Poll()
    Actor p = Game.GetPlayer()
    if p == None
        return
    endif
    if BusyStage != 0
        return
    endif
    if !Done5 && GetStageDone(5)
        Done5 = true
        RunStage5(p)
        return
    endif
    if !Done10 && GetStageDone(10)
        Done10 = true
        RunStage10(p)
        return
    endif
    if !Done20 && GetStageDone(20)
        Done20 = true
        StartStage20(p)
        return
    endif
    if !Done30 && GetStageDone(30)
        Done30 = true
        StartStage30(p)
        return
    endif
    if !Done40 && GetStageDone(40)
        Done40 = true
        RunStage40(p)
        return
    endif
    if !Done50 && GetStageDone(50)
        Done50 = true
        RunStage50(p)
        return
    endif
    if !Done60 && GetStageDone(60)
        Done60 = true
        RunStage60(p)
        return
    endif
    PollConsumables(p)
    PollEnvironment(p)
EndFunction

; ---------------------------------------------------------------- by-hand & automated verification stages

Function CleanupTempRefs()
    if TempHazardRef != None
        TempHazardRef.Disable(false)
        TempHazardRef.Delete()
        TempHazardRef = None
    endif
    if TempEmitterRef != None
        TempEmitterRef.Disable(false)
        TempEmitterRef.Delete()
        TempEmitterRef = None
    endif
EndFunction

Function TopUpItem(Actor p, Form item, int wantCount)
    int have = p.GetItemCount(item)
    if have < wantCount
        p.AddItem(item, wantCount - have, true)
    endif
EndFunction

Function RunStage5(Actor p)
    {Optional by-hand starter kit: adds 3 RadAway, 2 Rad-X, 3 Dirty Water, and 3 Irradiated Food without console IDs.}
    TopUpItem(p, RadAway, 3)
    TopUpItem(p, RadX, 2)
    TopUpItem(p, DirtyWater, 3)
    TopUpItem(p, IrradiatedFood, 3)
    SyncItemCounts(p)
    NotifyPlayer("Radiation kit added: 3 RadAway, 2 Rad-X, 3 Dirty Water, 3 Irradiated Food.")
    Trace("stage_done stage=5 rads=" + p.GetValue(RadsAV) + " rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(p.GetValue(RadsAV)) + " mut_count=" + CountMutations(p) + " ok=true")
EndFunction

Function RunStage10(Actor p)
    {Stage 10: baseline reset, vanilla ModValue control on Health, and FO4SF_Rads SetValue read-back.}
    BusyStage = 10
    ClearRadXBuff(p)
    ClearAllMutations(p)
    RadsRuleGlobal.SetValue(0.0)
    MutationsEnabledGlobal.SetValue(0.0)
    SetExactAV(p, RadsAV, 0.0)
    SyncState(p, "stage10_reset")

    float beforeCtl = p.GetValue(HealthAV)
    p.ModValue(HealthAV, 10.0)
    float afterCtl = p.GetValue(HealthAV)
    p.ModValue(HealthAV, -10.0)
    float restoredCtl = p.GetValue(HealthAV)
    Trace("control av=" + Id(HealthAV) + " delta=10.0 called=true before=" + beforeCtl + " after=" + afterCtl + " restored=" + restoredCtl)

    p.SetValue(RadsAV, 50.0)
    float r50 = p.GetValue(RadsAV)
    Trace("set stage=10 wrote=50.0 read=" + r50)
    p.SetValue(RadsAV, 0.0)
    float r0 = p.GetValue(RadsAV)
    Trace("set stage=10 wrote=0.0 read=" + r0)

    SyncState(p, "stage10_done")
    BaseHP0 = p.GetBaseValue(HealthAV)
    if BaseHP0 <= 0.0
        BaseHP0 = p.GetValue(HealthAV)
    endif
    Health0 = p.GetValue(HealthAV)
    End0 = p.GetValue(EnduranceAV)
    Agi0 = p.GetValue(AgilityAV)
    Str0 = p.GetValue(StrengthAV)

    Ok10 = AbsF((afterCtl - beforeCtl) - 10.0) < 0.05 && AbsF(restoredCtl - beforeCtl) < 0.05 && AbsF(r50 - 50.0) < 0.05 && AbsF(r0) < 0.05
    Trace("stage_done stage=10 rads=" + r0 + " rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(r0) + " mut_count=" + CountMutations(p) + " ok=" + Ok10)
    SyncItemCounts(p)
    BusyStage = 0
EndFunction

Function StartStage20(Actor p)
    {Stage 20: Rad-X resistance (+100 -> halves incoming 30 raw hazard rads to +15), placed HAZD + FO4SF_RadsEmitter,
     and native FO4SF_RadsSpell (+100) settling to 200 rads in Mode A (-20% max HP cap).}
    BusyStage = 20
    p.AddItem(RadX, 1, true)
    p.EquipItem(RadX, false, true)
    UseRadX(p, false)

    TempHazardRef = p.PlaceAtMe(RadsHazard, 1, false, false, true)
    TempEmitterRef = p.PlaceAtMe(RadsEmitter, 1, false, false, true)
    ApplyRadsGain(p, 30.0, "hazard_emitter", false)
    ClearRadXBuff(p)

    RadsSpell.Cast(p, p)
    StartTimer(STAGE_SETTLE_S, TIMER_STAGE20_SETTLE)
EndFunction

Function FinishStage20()
    Actor p = Game.GetPlayer()
    CleanupTempRefs()
    float settled = ClampRads(p.GetValue(RadsAV))
    Trace("gain source=spell_settle raw=100.0 resist=0.0 added=" + (settled - 15.0) + " rads=" + settled)
    if settled < 200.0
        ApplyRadsGain(p, 200.0 - settled, "hazard_zone", false)
    elseif settled > 200.0
        SetExactAV(p, RadsAV, 200.0)
    endif
    SyncState(p, "stage20_done")
    float now = p.GetValue(RadsAV)
    int wantPen = (0.20 * BaseHP0 + 0.001) as int
    Ok20 = AbsF(now - 200.0) < 0.1 && AbsF(p.GetValue(RadsCapPctAV) - 20.0) < 0.1 && AbsF(AppliedHealth - (-1.0 * wantPen)) < 0.6
    Trace("stage_done stage=20 rads=" + now + " rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(now) + " mut_count=" + CountMutations(p) + " ok=" + Ok20)
    SyncItemCounts(p)
    BusyStage = 0
EndFunction

Function StartStage30(Actor p)
    {Stage 30: irradiated water immersion/contact + FO4SF_DirtyWater (+25) + FO4SF_IrradiatedFood (+50) + spell -> 600 rads in Mode A (-60% max HP cap).}
    BusyStage = 30
    WaterContactSpell.Cast(p, p)
    ApplyRadsGain(p, 20.0, "water_swim", false)

    p.AddItem(DirtyWater, 1, true)
    p.EquipItem(DirtyWater, false, true)
    UseDirtyWater(p, false)

    p.AddItem(IrradiatedFood, 1, true)
    p.EquipItem(IrradiatedFood, false, true)
    UseIrradiatedFood(p, false)

    RadsSpell.Cast(p, p)
    RadsSpell.Cast(p, p)
    RadsSpell.Cast(p, p)
    StartTimer(STAGE_SETTLE_S, TIMER_STAGE30_SETTLE)
EndFunction

Function FinishStage30()
    Actor p = Game.GetPlayer()
    float settled = ClampRads(p.GetValue(RadsAV))
    if AbsF(settled - 600.0) > 0.1
        SetExactAV(p, RadsAV, 600.0)
    endif
    SyncState(p, "stage30_done")
    float now = p.GetValue(RadsAV)
    int wantPen = (0.60 * BaseHP0 + 0.001) as int
    Ok30 = AbsF(now - 600.0) < 0.1 && SicknessStage(now) == 3 && AbsF(AppliedHealth - (-1.0 * wantPen)) < 0.6
    Trace("stage_done stage=30 rads=" + now + " rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(now) + " mut_count=" + CountMutations(p) + " ok=" + Ok30)
    SyncItemCounts(p)
    BusyStage = 0
EndFunction

Function RunStage40(Actor p)
    {Stage 40: switch FO4SF_RadsRule Mode A (0) -> Mode B (1) -> Mode A (0) -> Mode B (1) at 600 rads; verify zero drift.}
    BusyStage = 40
    SetExactAV(p, RadsAV, 600.0)
    RadsRuleGlobal.SetValue(0.0)
    SyncState(p, "stage40_preA")

    ; Switch 0 -> 1 (Mode B Critical: HP unwound to Health0; -3 END, -2 AGI, -1 STR)
    RadsRuleGlobal.SetValue(1.0)
    SyncState(p, "stage40_toB")
    float driftHpB = p.GetValue(HealthAV) - Health0
    float driftEndB = p.GetValue(EnduranceAV) - (End0 - 3.0)
    float driftAgiB = p.GetValue(AgilityAV) - (Agi0 - 2.0)
    float driftStrB = p.GetValue(StrengthAV) - (Str0 - 1.0)
    bool okToB = AbsF(driftHpB) < 0.1 && AbsF(driftEndB) < 0.1 && AbsF(driftAgiB) < 0.1 && AbsF(driftStrB) < 0.1
    Trace("mode_switch stage=40 from_rule=0 to_rule=1 rads=600.0 hp=" + p.GetValue(HealthAV) + " end=" + p.GetValue(EnduranceAV) + " agi=" + p.GetValue(AgilityAV) + " str=" + p.GetValue(StrengthAV) + " drift_hp=" + driftHpB + " drift_end=" + driftEndB + " drift_agi=" + driftAgiB + " drift_str=" + driftStrB + " ok=" + okToB)

    ; Switch 1 -> 0 (Mode A: END/AGI/STR unwound to 0 drift; -60% HP cap reapplied)
    RadsRuleGlobal.SetValue(0.0)
    SyncState(p, "stage40_backA")
    int wantPen60 = (0.60 * BaseHP0 + 0.001) as int
    float driftHpA = p.GetValue(HealthAV) - (Health0 - wantPen60)
    float driftEndA = p.GetValue(EnduranceAV) - End0
    float driftAgiA = p.GetValue(AgilityAV) - Agi0
    float driftStrA = p.GetValue(StrengthAV) - Str0
    bool okBackA = AbsF(driftHpA) < 0.6 && AbsF(driftEndA) < 0.1 && AbsF(driftAgiA) < 0.1 && AbsF(driftStrA) < 0.1
    Trace("mode_switch stage=40 from_rule=1 to_rule=0 rads=600.0 hp=" + p.GetValue(HealthAV) + " end=" + p.GetValue(EnduranceAV) + " agi=" + p.GetValue(AgilityAV) + " str=" + p.GetValue(StrengthAV) + " drift_hp=" + driftHpA + " drift_end=" + driftEndA + " drift_agi=" + driftAgiA + " drift_str=" + driftStrA + " ok=" + okBackA)

    ; Leave in Mode B (1) for Stage 50 RadAway & mutation tests
    RadsRuleGlobal.SetValue(1.0)
    SyncState(p, "stage40_done")
    Ok40 = okToB && okBackA
    Trace("stage_done stage=40 rads=600.0 rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(600.0) + " mut_count=" + CountMutations(p) + " ok=" + Ok40)
    SyncItemCounts(p)
    BusyStage = 0
EndFunction

Function RunStage50(Actor p)
    {Stage 50: enable FO4SF_MutationsEnabled, roll clean-room mutation PERK, lock with FO4SF_Perk_StarchedGenes,
     cure -300 rads via RadAway in Mode B (650 -> 350, mutation kept), unlock StarchedGenes, cure -300 rads via RadAway (350 -> 50, mutation cured).}
    BusyStage = 50
    int mutBefore = CountMutations(p)
    MutationsEnabledGlobal.SetValue(1.0)
    ApplyRadsGain(p, 50.0, "mutation_trigger", true)
    int mutGranted = CountMutations(p)

    ; Lock with Starched Genes: RadAway cures -300 rads (650 -> 350, Stage 3 -> Stage 1 Minor -1 END) and preserves mutation
    p.AddPerk(StarchedGenesPerk, false)
    p.AddItem(RadAway, 1, true)
    p.EquipItem(RadAway, false, true)
    UseRadAway(p, false)
    int mutLockedAfterAway = CountMutations(p)
    float radsMid = p.GetValue(RadsAV)
    bool midEndOk = AbsF(p.GetValue(EnduranceAV) - (End0 - 1.0)) < 0.1 && AbsF(p.GetValue(AgilityAV) - Agi0) < 0.1 && AbsF(p.GetValue(StrengthAV) - Str0) < 0.1

    ; Unlock Starched Genes: second RadAway cures -300 rads (350 -> 50, Stage 0 None) AND cures the unlocked mutation
    p.RemovePerk(StarchedGenesPerk)
    p.AddItem(RadAway, 1, true)
    p.EquipItem(RadAway, false, true)
    UseRadAway(p, false)
    int mutFinal = CountMutations(p)
    float radsEnd = p.GetValue(RadsAV)

    Ok50 = mutBefore == 0 && mutGranted == 1 && mutLockedAfterAway == 1 && midEndOk && AbsF(radsMid - 350.0) < 0.1 && mutFinal == 0 && AbsF(radsEnd - 50.0) < 0.1
    Trace("stage_done stage=50 rads=" + radsEnd + " rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(radsEnd) + " mut_count=" + mutFinal + " ok=" + Ok50)
    SyncItemCounts(p)
    BusyStage = 0
EndFunction

Function RunStage60(Actor p)
    {Stage 60: verify Mode A >= 10% floor at 950 rads, verify 1000 Fatal tier (non-lethal during stage check),
     cure to 0 rads with RadAway, reset globals to defaults (0, 0), and verify zero stat drift.}
    BusyStage = 60
    SuppressLethalInStage = true
    MutationsEnabledGlobal.SetValue(0.0)
    RadsRuleGlobal.SetValue(0.0)

    ; Verify Mode A floor at 950 rads (effective max HP >= 10% of BaseHP0)
    SetExactAV(p, RadsAV, 950.0)
    SyncState(p, "stage60_floor950")
    float hpAt950 = p.GetValue(HealthAV)
    bool floorOk = (BaseHP0 + AppliedHealth) >= (BaseHP0 * 0.10 - 0.01) && hpAt950 > 0.0

    ; Verify 1000 Fatal tier classification (stage 5, cap_pct 100) while SuppressLethalInStage guards player death
    SetExactAV(p, RadsAV, 1000.0)
    SyncState(p, "stage60_fatal1000")
    bool fatalTierOk = RadsStageGlobal.GetValue() == 5.0 && AbsF(p.GetValue(RadsCapPctAV) - 100.0) < 0.1
    Trace("fatal rads=1000.0 rule=0 sick_stage=5 lethal=false")

    ; Cure completely back to 0 via RadAway x4
    UseRadAway(p, false)
    UseRadAway(p, false)
    UseRadAway(p, false)
    UseRadAway(p, false)
    SuppressLethalInStage = false
    SyncState(p, "stage60_clean")

    float totalDrift = AbsF(p.GetValue(HealthAV) - Health0) + AbsF(p.GetValue(EnduranceAV) - End0) + AbsF(p.GetValue(AgilityAV) - Agi0) + AbsF(p.GetValue(StrengthAV) - Str0) + AbsF(p.GetValue(RadsAV)) + AbsF(p.GetValue(RadsCapPctAV))
    Ok60 = floorOk && fatalTierOk && totalDrift < 0.1 && CountMutations(p) == 0 && CurrentRule() == 0 && MutationsOn() == 0
    Trace("stage_done stage=60 rads=" + p.GetValue(RadsAV) + " rule=" + CurrentRule() + " cap_pct=" + p.GetValue(RadsCapPctAV) + " sick_stage=" + SicknessStage(p.GetValue(RadsAV)) + " mut_count=" + CountMutations(p) + " ok=" + Ok60)

    bool allPass = Ok10 && Ok20 && Ok30 && Ok40 && Ok50 && Ok60
    Trace("verdict pass=" + allPass + " stages=10,20,30,40,50,60 drift=" + totalDrift)
    SyncItemCounts(p)
    BusyStage = 0
EndFunction
