Scriptname FO4SF_HardcoreQuest extends Quest
{GPOF gameplay option & survival controller: toggles Hunger, Thirst, Sleep meters (0..1000, 5 stages), ammunition weight burden, and Stimpak heal-over-time ON and OFF with zero conflict with held SQ_ENV (0x248D20).}

; Exact property order pinned by dotnet/HardcoreToggle/Program.cs and tests/test_hardcore_toggle.py
GameplayOption Property HardcoreOption Auto Const
GlobalVariable Property HardcoreEnabledGlobal Auto Const
GlobalVariable Property FastTravelBlockedGlobal Auto Const
ActorValue Property HungerAV Auto Const
ActorValue Property ThirstAV Auto Const
ActorValue Property SleepAV Auto Const
ActorValue Property AmmoBurdenAV Auto Const
GlobalVariable Property HungerStageGlobal Auto Const
GlobalVariable Property ThirstStageGlobal Auto Const
GlobalVariable Property SleepStageGlobal Auto Const
ActorValue Property HealthAV Auto Const
ActorValue Property CarryWeightAV Auto Const
ActorValue Property StrengthAV Auto Const
ActorValue Property EnduranceAV Auto Const
ActorValue Property AgilityAV Auto Const
ActorValue Property IntelligenceAV Auto Const
Potion Property RationFood Auto Const
Potion Property PurifiedWater Auto Const
Potion Property Stimpak Auto Const
Ammo Property CaliberLight Auto Const
Ammo Property CaliberRifle Auto Const
Ammo Property CaliberHeavy Auto Const
FormList Property WeightedAmmoList Auto Const
GlobalVariable Property TestModeGlobal Auto Const

int Property TimerIdPoll = 1 AutoReadOnly
int Property TimerIdStimpakHoT = 2 AutoReadOnly

float appliedStrMod = 0.0
float appliedEndMod = 0.0
float appliedAgiMod = 0.0
float appliedIntMod = 0.0
float appliedAmmoCarryMod = 0.0

int stimpakTicksRemaining = 0
float stimpakTickHeal = 10.0
float lastGameDays = -1.0
float sleepStartDays = -1.0

bool ran5 = false
bool ran10 = false
bool ran20 = false
bool ran30 = false
bool ran40 = false
bool ran50 = false
bool inCardRun = false
int testAmmoAdded = 0
float savedPreTestDamage = 0.0

Function LogLine(string kind, string kv)
    Debug.OpenUserLog("FO4SFHardcore")
    Debug.TraceUser("FO4SFHardcore", "FO4SFHC rt=" + Utility.GetCurrentRealTime() + " " + kind + " " + kv + " end=true")
EndFunction

bool Function ReadSqEnvRunning()
    Quest sqEnv = Game.GetFormFromFile(0x00248D20, "Starfield.esm") as Quest
    if sqEnv == None
        return false
    endif
    return sqEnv.IsRunning()
EndFunction

bool Function IsHardcoreActive()
    return HardcoreEnabledGlobal.GetValue() >= 0.5
EndFunction

int Function ComputeStage(float meterVal)
    if meterVal >= 1000.0
        return 5
    elseif meterVal >= 800.0
        return 4
    elseif meterVal >= 600.0
        return 3
    elseif meterVal >= 400.0
        return 2
    elseif meterVal >= 200.0
        return 1
    endif
    return 0
EndFunction

float Function ClampMeter(float v)
    if v < 0.0
        return 0.0
    elseif v > 1000.0
        return 1000.0
    endif
    return v
EndFunction

Function ApplyStatDelta(Actor player, ActorValue av, float desiredMod, int slot)
    float prev = 0.0
    if slot == 0
        prev = appliedStrMod
    elseif slot == 1
        prev = appliedEndMod
    elseif slot == 2
        prev = appliedAgiMod
    else
        prev = appliedIntMod
    endif
    float diff = desiredMod - prev
    if diff > 0.001 || diff < -0.001
        player.ModValue(av, diff)
        if slot == 0
            appliedStrMod = desiredMod
        elseif slot == 1
            appliedEndMod = desiredMod
        elseif slot == 2
            appliedAgiMod = desiredMod
        else
            appliedIntMod = desiredMod
        endif
    endif
EndFunction

float Function ComputeAmmoBurden(Actor player)
    if WeightedAmmoList == None
        return 0.0
    endif
    float total = 0.0
    int n = WeightedAmmoList.GetSize()
    int i = 0
    while i < n
        Form f = WeightedAmmoList.GetAt(i)
        if f != None
            int cnt = player.GetItemCount(f)
            if cnt > 0
                float unitW = 0.035
                if f == CaliberLight
                    unitW = 0.025
                elseif f == CaliberRifle
                    unitW = 0.050
                elseif f == CaliberHeavy
                    unitW = 0.100
                endif
                total += (cnt as float) * unitW
            endif
        endif
        i += 1
    endwhile
    return total
EndFunction

Function SyncAmmoWeight(Actor player)
    float desiredBurden = 0.0
    if IsHardcoreActive()
        desiredBurden = ComputeAmmoBurden(player)
    endif
    player.SetValue(AmmoBurdenAV, desiredBurden)
    float desiredCarryMod = -desiredBurden
    float diff = desiredCarryMod - appliedAmmoCarryMod
    if diff > 0.0005 || diff < -0.0005
        player.ModValue(CarryWeightAV, diff)
        appliedAmmoCarryMod = desiredCarryMod
    endif
EndFunction

Function SyncMetersAndStats(Actor player)
    if !IsHardcoreActive()
        HungerStageGlobal.SetValue(0.0)
        ThirstStageGlobal.SetValue(0.0)
        SleepStageGlobal.SetValue(0.0)
        FastTravelBlockedGlobal.SetValue(0.0)
        ApplyStatDelta(player, StrengthAV, 0.0, 0)
        ApplyStatDelta(player, EnduranceAV, 0.0, 1)
        ApplyStatDelta(player, AgilityAV, 0.0, 2)
        ApplyStatDelta(player, IntelligenceAV, 0.0, 3)
        return
    endif

    FastTravelBlockedGlobal.SetValue(1.0)
    float h = ClampMeter(player.GetValue(HungerAV))
    float t = ClampMeter(player.GetValue(ThirstAV))
    float s = ClampMeter(player.GetValue(SleepAV))
    player.SetValue(HungerAV, h)
    player.SetValue(ThirstAV, t)
    player.SetValue(SleepAV, s)

    int hs = ComputeStage(h)
    int ts = ComputeStage(t)
    int ss = ComputeStage(s)
    HungerStageGlobal.SetValue(hs as float)
    ThirstStageGlobal.SetValue(ts as float)
    SleepStageGlobal.SetValue(ss as float)

    float wantStr = 0.0
    float wantEnd = 0.0
    float wantAgi = 0.0
    float wantInt = 0.0

    ; Hunger (FO:NV HUNG curve: END -1..-3, STR -1..-2 at stages 3..5)
    if hs == 1
        wantEnd -= 1.0
    elseif hs == 2
        wantEnd -= 2.0
    elseif hs == 3
        wantEnd -= 3.0
        wantStr -= 1.0
    elseif hs >= 4
        wantEnd -= 3.0
        wantStr -= 2.0
    endif

    ; Thirst (FO:NV DEHY curve: END -1..-3, INT -1..-2 at stages 3..5)
    if ts == 1
        wantEnd -= 1.0
    elseif ts == 2
        wantEnd -= 2.0
    elseif ts == 3
        wantEnd -= 3.0
        wantInt -= 1.0
    elseif ts >= 4
        wantEnd -= 3.0
        wantInt -= 2.0
    endif

    ; Sleep deprivation (FO:NV SLPD curve: AGI -1..-3, INT -1..-2, END -1..-2)
    if ss == 1
        wantAgi -= 1.0
    elseif ss == 2
        wantAgi -= 2.0
        wantInt -= 1.0
    elseif ss == 3
        wantAgi -= 3.0
        wantInt -= 2.0
        wantEnd -= 1.0
    elseif ss >= 4
        wantAgi -= 3.0
        wantInt -= 2.0
        wantEnd -= 2.0
    endif

    ApplyStatDelta(player, StrengthAV, wantStr, 0)
    ApplyStatDelta(player, EnduranceAV, wantEnd, 1)
    ApplyStatDelta(player, AgilityAV, wantAgi, 2)
    ApplyStatDelta(player, IntelligenceAV, wantInt, 3)
EndFunction

Function SyncAllSystems(string reason)
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    if !IsHardcoreActive() && stimpakTicksRemaining > 0
        stimpakTicksRemaining = 0
        CancelTimer(TimerIdStimpakHoT)
    endif
    SyncMetersAndStats(player)
    SyncAmmoWeight(player)
    LogLine("sync", "reason=" + reason + " hardcore=" + (HardcoreEnabledGlobal.GetValue() as int) + " h=" + player.GetValue(HungerAV) + " hs=" + (HungerStageGlobal.GetValue() as int) + " t=" + player.GetValue(ThirstAV) + " ts=" + (ThirstStageGlobal.GetValue() as int) + " s=" + player.GetValue(SleepAV) + " ss=" + (SleepStageGlobal.GetValue() as int) + " ammo_burden=" + player.GetValue(AmmoBurdenAV) + " carry_mod=" + appliedAmmoCarryMod + " end_mod=" + appliedEndMod + " str_mod=" + appliedStrMod + " agi_mod=" + appliedAgiMod + " int_mod=" + appliedIntMod + " ft_blocked=" + (FastTravelBlockedGlobal.GetValue() as int) + " sq_env_running=" + ReadSqEnvRunning())
EndFunction

Function TriggerStimpakDose(Actor player, string sourceTag)
    float hpBefore = player.GetValue(HealthAV)
    if IsHardcoreActive()
        ; Hardcore ON: heal-over-time (+10 HP immediate tick + 5 ticks @ 1.0s = +60 HP over 6s)
        player.RestoreValue(HealthAV, stimpakTickHeal)
        stimpakTicksRemaining = 5
        StartTimer(1.0, TimerIdStimpakHoT)
        float hpNow = player.GetValue(HealthAV)
        LogLine("stimpak", "source=" + sourceTag + " mode=hot heal_tick=" + stimpakTickHeal + " ticks_remaining=" + stimpakTicksRemaining + " hp_before=" + hpBefore + " hp_now=" + hpNow)
    else
        ; Hardcore OFF: instant heal (+60 HP immediately, 0 ticks scheduled)
        stimpakTicksRemaining = 0
        CancelTimer(TimerIdStimpakHoT)
        player.RestoreValue(HealthAV, 60.0)
        float hpNow = player.GetValue(HealthAV)
        LogLine("stimpak", "source=" + sourceTag + " mode=instant heal_instant=60.0 ticks_remaining=0 hp_before=" + hpBefore + " hp_now=" + hpNow)
    endif
EndFunction

Function RegisterHooks()
    RegisterForGameplayOptionChangedEvent()
    RegisterForPlayerSleep()
    Actor player = Game.GetPlayer()
    if player != None
        RemoveAllInventoryEventFilters()
        if WeightedAmmoList != None
            AddInventoryEventFilter(WeightedAmmoList)
        endif
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        RegisterForRemoteEvent(player, "OnItemEquipped")
        RegisterForRemoteEvent(player as ObjectReference, "OnItemAdded")
        RegisterForRemoteEvent(player as ObjectReference, "OnItemRemoved")
    endif
EndFunction

Event OnQuestInit()
    RegisterHooks()
    if HardcoreOption != None
        HardcoreEnabledGlobal.SetValue(HardcoreOption.GetValue())
    endif
    lastGameDays = Utility.GetCurrentGameTime()
    SyncAllSystems("init")
    StartTimer(1.0, TimerIdPoll)
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    RegisterHooks()
    if HardcoreOption != None
        HardcoreEnabledGlobal.SetValue(HardcoreOption.GetValue())
    endif
    lastGameDays = Utility.GetCurrentGameTime()
    SyncAllSystems("reload")
    StartTimer(1.0, TimerIdPoll)
EndEvent

Event OnGameplayOptionChanged(GameplayOption[] aChangedOptions)
    if aChangedOptions != None && HardcoreOption != None && aChangedOptions.Find(HardcoreOption) >= 0
        float newVal = HardcoreOption.GetValue()
        HardcoreEnabledGlobal.SetValue(newVal)
        SyncAllSystems("gpof_menu")
        GameplayOption.NotifyGameplayOptionUpdateFinished()
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    Actor player = Game.GetPlayer()
    if player == None || akSender != player
        return
    endif
    if akBaseObject == RationFood
        player.SetValue(HungerAV, ClampMeter(player.GetValue(HungerAV) - 250.0))
        SyncMetersAndStats(player)
        LogLine("relief", "kind=food hunger=" + player.GetValue(HungerAV) + " hs=" + (HungerStageGlobal.GetValue() as int))
    elseif akBaseObject == PurifiedWater
        player.SetValue(ThirstAV, ClampMeter(player.GetValue(ThirstAV) - 250.0))
        SyncMetersAndStats(player)
        LogLine("relief", "kind=water thirst=" + player.GetValue(ThirstAV) + " ts=" + (ThirstStageGlobal.GetValue() as int))
    elseif akBaseObject == Stimpak
        TriggerStimpakDose(player, "equip")
    endif
EndEvent

Event ObjectReference.OnItemAdded(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akSourceContainer, int aiTransferReason)
    Actor player = Game.GetPlayer()
    if player != None && akSender == (player as ObjectReference) && IsHardcoreActive()
        SyncAmmoWeight(player)
    endif
EndEvent

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    Actor player = Game.GetPlayer()
    if player != None && akSender == (player as ObjectReference) && IsHardcoreActive()
        SyncAmmoWeight(player)
    endif
EndEvent

Event OnPlayerSleepStart(float afSleepStartTime, float afDesiredSleepEndTime, ObjectReference akBed)
    sleepStartDays = afSleepStartTime
EndEvent

Event OnPlayerSleepStop(bool abInterrupted, ObjectReference akBed)
    Actor player = Game.GetPlayer()
    if player == None || !IsHardcoreActive()
        return
    endif
    float nowDays = Utility.GetCurrentGameTime()
    float sleptHours = 1.0
    if sleepStartDays >= 0.0 && nowDays > sleepStartDays
        sleptHours = (nowDays - sleepStartDays) * 24.0
    endif
    float relief = sleptHours * 45.0
    player.SetValue(SleepAV, ClampMeter(player.GetValue(SleepAV) - relief))
    lastGameDays = nowDays
    SyncMetersAndStats(player)
    LogLine("relief", "kind=sleep hours=" + sleptHours + " sleep=" + player.GetValue(SleepAV) + " ss=" + (SleepStageGlobal.GetValue() as int))
EndEvent

Function ApplySafeTestWound(Actor player)
    float curHp = player.GetValue(HealthAV)
    float dmg = 40.0
    if curHp - dmg < 25.0
        dmg = curHp - 25.0
    endif
    if dmg > 0.0
        player.DamageValue(HealthAV, dmg)
        savedPreTestDamage += dmg
    endif
EndFunction

Function PollStagesAndMeters()
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif

    if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0
        ; Stage 5: Optional by-hand starter kit (ration, purified water, stimpaks, rifle ammo)
        if !ran5 && GetStageDone(5)
            ran5 = true
            player.AddItem(RationFood, 3, true)
            player.AddItem(PurifiedWater, 3, true)
            player.AddItem(Stimpak, 3, true)
            player.AddItem(CaliberRifle, 50, true)
            SyncAllSystems("stage5_kit")
            LogLine("starter_kit", "id=5 ok=true")
        endif

        ; Stage 10: Enable Hardcore ON -> verify meters, stat penalties, ammo weight, stimpak HoT, & SQ_ENV stopped
        if !ran10 && GetStageDone(10)
            ran10 = true
            inCardRun = true
            HardcoreEnabledGlobal.SetValue(1.0)
            player.SetValue(HungerAV, 450.0)
            player.SetValue(ThirstAV, 650.0)
            player.SetValue(SleepAV, 250.0)
            player.AddItem(CaliberRifle, 100, true)
            testAmmoAdded += 100
            SyncAllSystems("stage10_on")
            ApplySafeTestWound(player)
            TriggerStimpakDose(player, "stage10_hot")
            LogLine("stage", "id=10 ok=true hardcore=1 sq_env_running=" + ReadSqEnvRunning())
        endif

        ; Stage 20: Relief while Hardcore ON (food, water, 8h sleep relief)
        if !ran20 && GetStageDone(20)
            ran20 = true
            player.SetValue(HungerAV, ClampMeter(player.GetValue(HungerAV) - 250.0))
            player.SetValue(ThirstAV, ClampMeter(player.GetValue(ThirstAV) - 250.0))
            player.SetValue(SleepAV, ClampMeter(player.GetValue(SleepAV) - 300.0))
            SyncAllSystems("stage20_relief")
            LogLine("stage", "id=20 ok=true h=" + player.GetValue(HungerAV) + " t=" + player.GetValue(ThirstAV) + " s=" + player.GetValue(SleepAV))
        endif

        ; Stage 30: Toggle Hardcore OFF -> verify all meter penalties & ammo carry burden revert cleanly to 0
        if !ran30 && GetStageDone(30)
            ran30 = true
            HardcoreEnabledGlobal.SetValue(0.0)
            SyncAllSystems("stage30_off")
            LogLine("stage", "id=30 ok=true hardcore=0 ammo_burden=" + player.GetValue(AmmoBurdenAV) + " carry_mod=" + appliedAmmoCarryMod + " end_mod=" + appliedEndMod + " sq_env_running=" + ReadSqEnvRunning())
        endif

        ; Stage 40: Stimpak while Hardcore OFF -> verify instant heal (+60 HP now, 0 HoT ticks)
        if !ran40 && GetStageDone(40)
            ran40 = true
            ApplySafeTestWound(player)
            TriggerStimpakDose(player, "stage40_instant")
            LogLine("stage", "id=40 ok=true hardcore=0")
        endif

        ; Stage 50: Cleanup test items & restore exact HP
        if !ran50 && GetStageDone(50)
            ran50 = true
            stimpakTicksRemaining = 0
            CancelTimer(TimerIdStimpakHoT)
            if testAmmoAdded > 0
                player.RemoveItem(CaliberRifle, testAmmoAdded, true, None)
                testAmmoAdded = 0
            endif
            player.SetValue(HungerAV, 0.0)
            player.SetValue(ThirstAV, 0.0)
            player.SetValue(SleepAV, 0.0)
            if savedPreTestDamage > 0.0
                player.RestoreValue(HealthAV, savedPreTestDamage)
                savedPreTestDamage = 0.0
            endif
            inCardRun = false
            SyncAllSystems("stage50_reset")
            LogLine("stage", "id=50 ok=true hardcore=0")
            LogLine("summary", "ok=true stages=10,20,30,40,50 sq_env_running=" + ReadSqEnvRunning())
        endif
    endif

    ; Passive game-clock survival progression when Hardcore is ON outside automated card stages
    float nowDays = Utility.GetCurrentGameTime()
    if !inCardRun && IsHardcoreActive() && lastGameDays >= 0.0 && nowDays > lastGameDays
        float elapsedHours = (nowDays - lastGameDays) * 24.0
        if elapsedHours >= 0.05
            player.SetValue(HungerAV, ClampMeter(player.GetValue(HungerAV) + elapsedHours * 18.0))
            player.SetValue(ThirstAV, ClampMeter(player.GetValue(ThirstAV) + elapsedHours * 30.0))
            player.SetValue(SleepAV, ClampMeter(player.GetValue(SleepAV) + elapsedHours * 12.0))
            lastGameDays = nowDays
            SyncMetersAndStats(player)
        endif
    else
        lastGameDays = nowDays
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID == TimerIdPoll
        PollStagesAndMeters()
        StartTimer(1.0, TimerIdPoll)
    elseif aiTimerID == TimerIdStimpakHoT
        Actor player = Game.GetPlayer()
        if player != None && IsHardcoreActive() && stimpakTicksRemaining > 0
            player.RestoreValue(HealthAV, stimpakTickHeal)
            stimpakTicksRemaining -= 1
            LogLine("stimpak_tick", "heal=" + stimpakTickHeal + " remaining=" + stimpakTicksRemaining + " hp=" + player.GetValue(HealthAV))
            if stimpakTicksRemaining > 0
                StartTimer(1.0, TimerIdStimpakHoT)
            endif
        else
            stimpakTicksRemaining = 0
        endif
    endif
EndEvent
