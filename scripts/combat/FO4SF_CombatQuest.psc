Scriptname FO4SF_CombatQuest extends Quest
{CF-8 Combat Core controller:
  1a. Unified 8-zone BPTD hit locations (Head 2.0x, Torso 1.0x, Arms/Legs 0.85x), crippled-limb penalties
      (slow walk -40/-60 SpeedMult, aim sway +35/+65, right-arm weapon drop), and Stimpak vs Hardcore Doctor's Bag cure.
  1b. Slow-time VATS targeting mode (25% time scale via FO4SF_VatsSlowTimeAb, limb picker with AP costs & hit chance
      from distance, weapon skill, and PER, and queued shot via Weapon.Fire).
  1c. Calibre-table New Vegas ammo subtypes (Standard, AP, JHP, +P; Shotgun Buckshot/Slug/Flechette/Magnum)
      resolved dynamically via Weapon.GetAmmo() with zero per-weapon edits.}

; Exact property order pinned by dotnet/CombatCore/Program.cs and tests/test_combat_core.py
GlobalVariable Property ActiveAmmoSubtypeGlobal Auto Const
GlobalVariable Property VatsSlowTimeActiveGlobal Auto Const
GlobalVariable Property CombatTitleRuleGlobal Auto Const
GlobalVariable Property HardcoreOverrideGlobal Auto Const
GlobalVariable Property VatsApPoolGlobal Auto Const
GlobalVariable Property HardcoreGlobal Auto Const
GlobalVariable Property TestModeGlobal Auto Const
ActorValue Property TargetDTAV Auto Const
ActorValue Property TargetDRAV Auto Const
ActorValue Property AimSwayPenaltyAV Auto Const
ActorValue Property LimbCrippleMaskAV Auto Const
ActorValue Property PerceptionAV Auto Const
ActorValue Property GunsSkillAV Auto Const
ActorValue Property HeadCondAV Auto Const
ActorValue Property TorsoCondAV Auto Const
ActorValue Property LeftArmCondAV Auto Const
ActorValue Property RightArmCondAV Auto Const
ActorValue Property LeftLegCondAV Auto Const
ActorValue Property RightLegCondAV Auto Const
ActorValue Property BrainCondAV Auto Const
ActorValue Property SpeedMultAV Auto Const
ActorValue Property HealthAV Auto Const
Potion Property DoctorsBag Auto Const
Potion Property CombatStimpak Auto Const
Spell Property VatsSlowTimeAb Auto Const
Message Property VatsLimbPickerMsg Auto Const
MiscObject Property VatsTriggerToken Auto Const
MiscObject Property AmmoCycleToken Auto Const
FormList Property ActionTokensList Auto Const
FormList Property CalibreBaseAmmoList Auto Const
FormList Property SubtypeAPList Auto Const
FormList Property SubtypeJHPList Auto Const
FormList Property SubtypePlusPList Auto Const
FormList Property ReloadingRecipesList Auto Const
Weapon Property StarterRifle Auto Const
Weapon Property StarterShotgun Auto Const
ObjectReference Property ZonePlateHeadRef Auto Const
ObjectReference Property ZonePlateTorsoRef Auto Const
ObjectReference Property ZonePlateLeftArmRef Auto Const
ObjectReference Property ZonePlateRightArmRef Auto Const
ObjectReference Property ZonePlateLeftLegRef Auto Const
ObjectReference Property ZonePlateRightLegRef Auto Const
ObjectReference Property ArmoredTargetRef Auto Const
ObjectReference Property VatsTargetRef Auto Const
ObjectReference Property AmmoCyclePedestalRef Auto Const
ObjectReference Property LegTrapSwitchRef Auto Const
ObjectReference Property HardcoreToggleSwitchRef Auto Const
ObjectReference Property SupplyRackRef Auto Const

int Property TimerIdApRegen = 1 AutoReadOnly

float appliedSpeedDelta = 0.0
float appliedSwayPenalty = 0.0
bool prevRightArmCrippled = false
bool vatsBusy = false
bool ran50 = false

Function TraceCombat(string line)
    Debug.OpenUserLog("FO4SFCombat")
    Debug.TraceUser("FO4SFCombat", "[FO4SF_Combat] " + line)
    Debug.Trace("[FO4SF_Combat] " + line)
EndFunction

Function CompleteTestStage(int aiStage)
    if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0
        SetStage(aiStage)
    endif
EndFunction

bool Function IsHardcoreMode()
    if HardcoreOverrideGlobal != None
        float ov = HardcoreOverrideGlobal.GetValue()
        if ov >= 0.5
            return true
        elseif ov >= -0.5 && ov < 0.5
            return false
        endif
    endif
    if HardcoreGlobal != None
        return HardcoreGlobal.GetValue() >= 0.5
    endif
    GlobalVariable hcGlob = Game.GetFormFromFile(0x000840, "FO4SFCoreValues.esm") as GlobalVariable
    if hcGlob != None
        return hcGlob.GetValue() >= 0.5
    endif
    return false
EndFunction

float Function ReadPlayerPerception()
    ; Read FO4SFCoreValues.esm 0x000811 FO4SF_Special_Perception ActorValue on player, else baseline 6.0
    Actor player = Game.GetPlayer()
    ActorValue perAv = PerceptionAV
    if perAv == None
        perAv = Game.GetFormFromFile(0x000811, "FO4SFCoreValues.esm") as ActorValue
    endif
    if player != None && perAv != None
        float v = player.GetValue(perAv)
        if v >= 1.0
            return v
        endif
    endif
    return 6.0
EndFunction

float Function ReadPlayerGunsSkill()
    ; Read FO4SFCoreValues.esm 0x000823 FO4SF_Skill_Guns ActorValue on player, else baseline 50.0
    Actor player = Game.GetPlayer()
    ActorValue gunsAv = GunsSkillAV
    if gunsAv == None
        gunsAv = Game.GetFormFromFile(0x000823, "FO4SFCoreValues.esm") as ActorValue
    endif
    if player != None && gunsAv != None
        float s = player.GetValue(gunsAv)
        if s > 0.0
            return s
        endif
    endif
    return 50.0
EndFunction

Function RegisterAllTargets()
    Actor player = Game.GetPlayer()
    if player != None
        RemoveAllInventoryEventFilters()
        if ActionTokensList != None
            AddInventoryEventFilter(ActionTokensList)
        endif
        RegisterForRemoteEvent(player, "OnPlayerLoadGame")
        RegisterForRemoteEvent(player, "OnItemEquipped")
        RegisterForRemoteEvent(player as ObjectReference, "OnItemRemoved")
        RegisterForHitEvent(player)
    endif

    if ZonePlateHeadRef != None
        RegisterForHitEvent(ZonePlateHeadRef)
    endif
    if ZonePlateTorsoRef != None
        RegisterForHitEvent(ZonePlateTorsoRef)
    endif
    if ZonePlateLeftArmRef != None
        RegisterForHitEvent(ZonePlateLeftArmRef)
    endif
    if ZonePlateRightArmRef != None
        RegisterForHitEvent(ZonePlateRightArmRef)
    endif
    if ZonePlateLeftLegRef != None
        RegisterForHitEvent(ZonePlateLeftLegRef)
    endif
    if ZonePlateRightLegRef != None
        RegisterForHitEvent(ZonePlateRightLegRef)
    endif
    if ArmoredTargetRef != None
        RegisterForHitEvent(ArmoredTargetRef)
    endif
    if VatsTargetRef != None
        RegisterForHitEvent(VatsTargetRef)
    endif

    if AmmoCyclePedestalRef != None
        RegisterForRemoteEvent(AmmoCyclePedestalRef, "OnActivate")
    endif
    if LegTrapSwitchRef != None
        RegisterForRemoteEvent(LegTrapSwitchRef, "OnActivate")
    endif
    if HardcoreToggleSwitchRef != None
        RegisterForRemoteEvent(HardcoreToggleSwitchRef, "OnActivate")
    endif
    if SupplyRackRef != None
        RegisterForRemoteEvent(SupplyRackRef, "OnActivate")
    endif
EndFunction

Event OnQuestInit()
    RegisterAllTargets()
    StartTimer(2.0, TimerIdApRegen)
    TraceCombat("init status=ready recipes=" + ReloadingRecipesList.GetSize() + " calibres=" + CalibreBaseAmmoList.GetSize())
EndEvent

Event Actor.OnPlayerLoadGame(Actor akSender)
    RegisterAllTargets()
    Actor player = Game.GetPlayer()
    if player != None
        SyncPlayerLimbPenalties(player)
    endif
    StartTimer(2.0, TimerIdApRegen)
    TraceCombat("reload status=ready slot=" + (ActiveAmmoSubtypeGlobal.GetValue() as int))
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == TimerIdApRegen
        if VatsApPoolGlobal != None && VatsSlowTimeActiveGlobal.GetValue() < 0.5
            float cur = VatsApPoolGlobal.GetValue()
            if cur < 100.0
                float nextAp = cur + 12.0
                if nextAp > 100.0
                    nextAp = 100.0
                endif
                VatsApPoolGlobal.SetValue(nextAp)
            endif
        endif
        if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0 && !ran50 && GetStageDone(50)
            ran50 = true
            TraceCombat("summary status=ok test_mode=1")
        endif
        StartTimer(2.0, TimerIdApRegen)
    endif
EndEvent

int Function FindCalibreIndex(Weapon akWeap)
    if akWeap == None || CalibreBaseAmmoList == None
        return 0
    endif
    Ammo baseAmmo = akWeap.GetAmmo()
    if baseAmmo == None
        return 0
    endif
    int idx = CalibreBaseAmmoList.Find(baseAmmo)
    if idx >= 0
        return idx
    endif
    return 0
EndFunction

bool Function IsShotgunCalibre(int calIdx)
    return calIdx == 2
EndFunction

bool Function IsEnergyCalibre(int calIdx)
    return calIdx == 3
EndFunction

string Function SubtypeKeyFor(int calIdx, int slot)
    if IsShotgunCalibre(calIdx)
        if slot == 1
            return "slug"
        elseif slot == 2
            return "flechette"
        elseif slot == 3
            return "magnum"
        endif
        return "buckshot"
    elseif IsEnergyCalibre(calIdx)
        if slot == 1
            return "overcharge"
        elseif slot == 2
            return "optimized"
        elseif slot == 3
            return "max_charge"
        endif
        return "standard_cell"
    endif
    if slot == 1
        return "ap"
    elseif slot == 2
        return "jhp"
    elseif slot == 3
        return "plus_p"
    endif
    return "standard"
EndFunction

Ammo Function ResolveActiveSubtypeAmmo(Weapon akWeap, int calIdx, int slot)
    if slot == 1 && SubtypeAPList != None && calIdx < SubtypeAPList.GetSize()
        return SubtypeAPList.GetAt(calIdx) as Ammo
    elseif slot == 2 && SubtypeJHPList != None && calIdx < SubtypeJHPList.GetSize()
        return SubtypeJHPList.GetAt(calIdx) as Ammo
    elseif slot == 3 && SubtypePlusPList != None && calIdx < SubtypePlusPList.GetSize()
        return SubtypePlusPList.GetAt(calIdx) as Ammo
    endif
    if akWeap != None
        return akWeap.GetAmmo()
    endif
    return CalibreBaseAmmoList.GetAt(calIdx) as Ammo
EndFunction

float Function SubtypeDmgMult(int calIdx, int slot)
    if IsShotgunCalibre(calIdx)
        if slot == 1
            return 1.15
        elseif slot == 2
            return 0.95
        elseif slot == 3
            return 1.30
        endif
        return 1.20
    elseif IsEnergyCalibre(calIdx)
        if slot == 1
            return 1.25
        elseif slot == 2
            return 1.30
        elseif slot == 3
            return 1.50
        endif
        return 1.00
    endif
    if slot == 1
        return 0.95
    elseif slot == 2
        return 1.65
    elseif slot == 3
        return 1.25
    endif
    return 1.00
EndFunction

float Function SubtypeDtPierce(int calIdx, int slot)
    if IsShotgunCalibre(calIdx)
        if slot == 1
            return 10.0
        elseif slot == 2
            return 14.0
        elseif slot == 3
            return 4.0
        endif
        return 0.0
    elseif IsEnergyCalibre(calIdx)
        if slot == 1
            return 10.0
        elseif slot == 2
            return 5.0
        elseif slot == 3
            return 15.0
        endif
        return 0.0
    endif
    if slot == 1
        return 15.0
    elseif slot == 2
        return 0.0
    elseif slot == 3
        return 5.0
    endif
    return 0.0
EndFunction

float Function SubtypeDtMult(int calIdx, int slot)
    if IsShotgunCalibre(calIdx) && slot == 0
        return 1.50
    elseif !IsShotgunCalibre(calIdx) && !IsEnergyCalibre(calIdx) && slot == 2
        return 2.00
    endif
    return 1.00
EndFunction

Function CycleAmmoSubtype()
    Actor player = Game.GetPlayer()
    Weapon weap = None
    if player != None
        weap = player.GetEquippedWeapon(0)
    endif
    int calIdx = FindCalibreIndex(weap)
    int curSlot = ActiveAmmoSubtypeGlobal.GetValue() as int
    int nextSlot = curSlot + 1
    if nextSlot >= 4
        nextSlot = 0
    endif
    ActiveAmmoSubtypeGlobal.SetValue(nextSlot as float)
    string subKey = SubtypeKeyFor(calIdx, nextSlot)
    string calName = "cal_" + calIdx
    CompleteTestStage(20)
    Debug.Notification("Ammo Subtype: " + subKey)
    TraceCombat("PASS step=ammo_cycle calibre=" + calName + " slot=" + nextSlot + " subtype=" + subKey)
EndFunction

float Function ZoneDamageMult(string zone)
    if zone == "head"
        return 2.00
    elseif zone == "torso"
        return 1.00
    elseif zone == "special_core"
        return 1.50
    elseif zone == "special_optic"
        return 2.20
    endif
    return 0.85
EndFunction

float Function ComputePostDtDamage(float baseDamage, float targetDt, float targetDrPct, int calIdx, int slot, float outEffDtHint)
    float dmgMult = SubtypeDmgMult(calIdx, slot)
    float scaledRaw = baseDamage * dmgMult
    float clampedDr = targetDrPct
    if clampedDr < 0.0
        clampedDr = 0.0
    elseif clampedDr > 85.0
        clampedDr = 85.0
    endif
    float afterDr = scaledRaw * (1.0 - (clampedDr / 100.0))
    float effDt = (targetDt * SubtypeDtMult(calIdx, slot)) - SubtypeDtPierce(calIdx, slot)
    if effDt < 0.0
        effDt = 0.0
    endif
    float floorDmg = scaledRaw * 0.20
    float postDt = afterDr - effDt
    if postDt < floorDmg
        postDt = floorDmg
    endif
    return postDt
EndFunction

Function ApplyZoneHitToTarget(ObjectReference akTarget, string zone, float targetDt, float targetDrPct, bool isHighDtStation)
    Actor player = Game.GetPlayer()
    Weapon weap = None
    if player != None
        weap = player.GetEquippedWeapon(0)
    endif
    int calIdx = FindCalibreIndex(weap)
    int slot = ActiveAmmoSubtypeGlobal.GetValue() as int
    string subKey = SubtypeKeyFor(calIdx, slot)

    float baseDmg = 24.0
    if IsShotgunCalibre(calIdx)
        baseDmg = 30.0
    endif
    float effDt = (targetDt * SubtypeDtMult(calIdx, slot)) - SubtypeDtPierce(calIdx, slot)
    if effDt < 0.0
        effDt = 0.0
    endif
    float postDt = ComputePostDtDamage(baseDmg, targetDt, targetDrPct, calIdx, slot, effDt)
    float zMult = ZoneDamageMult(zone)
    float applied = postDt * zMult

    Actor targetActor = akTarget as Actor
    if targetActor != None
        targetActor.DamageValue(HealthAV, applied)
        ActorValue limbAv = TorsoCondAV
        if zone == "head"
            limbAv = HeadCondAV
        elseif zone == "left_arm"
            limbAv = LeftArmCondAV
        elseif zone == "right_arm"
            limbAv = RightArmCondAV
        elseif zone == "left_leg"
            limbAv = LeftLegCondAV
        elseif zone == "right_leg"
            limbAv = RightLegCondAV
        endif
        if limbAv != None
            targetActor.DamageValue(limbAv, applied * 1.25)
        endif
    endif

    if isHighDtStation
        CompleteTestStage(20)
        TraceCombat("PASS step=high_dt_hit subtype=" + subKey + " target_dt=" + targetDt + " eff_dt=" + effDt + " damage=" + applied)
    else
        CompleteTestStage(10)
        TraceCombat("PASS step=zone_hit zone=" + zone + " mult=" + zMult + " applied=" + applied + " subtype=" + subKey)
    endif
EndFunction

Function SyncPlayerLimbPenalties(Actor player)
    if player == None
        return
    endif
    bool lLeg = player.GetValue(LeftLegCondAV) <= 0.0
    bool rLeg = player.GetValue(RightLegCondAV) <= 0.0
    bool lArm = player.GetValue(LeftArmCondAV) <= 0.0
    bool rArm = player.GetValue(RightArmCondAV) <= 0.0
    bool headC = player.GetValue(HeadCondAV) <= 0.0

    int cLegs = 0
    if lLeg
        cLegs += 1
    endif
    if rLeg
        cLegs += 1
    endif

    int cArms = 0
    if lArm
        cArms += 1
    endif
    if rArm
        cArms += 1
    endif

    float wantSpeedDelta = 0.0
    if cLegs >= 2
        wantSpeedDelta = -60.0
    elseif cLegs == 1
        wantSpeedDelta = -40.0
    endif

    float diffSpeed = wantSpeedDelta - appliedSpeedDelta
    if diffSpeed > 0.01 || diffSpeed < -0.01
        player.ModValue(SpeedMultAV, diffSpeed)
        appliedSpeedDelta = wantSpeedDelta
    endif

    float wantSway = 0.0
    if cArms >= 2
        wantSway = 65.0
    elseif cArms == 1
        wantSway = 35.0
    endif
    if headC
        wantSway += 20.0
    endif
    player.SetValue(AimSwayPenaltyAV, wantSway)
    appliedSwayPenalty = wantSway

    if rArm && !prevRightArmCrippled
        Weapon eq = player.GetEquippedWeapon(0)
        if eq != None
            player.UnequipItem(eq, false, false)
            TraceCombat("PASS step=weapon_dropped zone=right_arm")
        endif
    endif
    prevRightArmCrippled = rArm

    int mask = 0
    if headC
        mask += 1
    endif
    if lArm
        mask += 4
    endif
    if rArm
        mask += 8
    endif
    if lLeg
        mask += 16
    endif
    if rLeg
        mask += 32
    endif
    player.SetValue(LimbCrippleMaskAV, mask as float)
EndFunction

Function InflictPlayerLimbCripple(string zone)
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    ActorValue av = LeftLegCondAV
    if zone == "right_leg"
        av = RightLegCondAV
    elseif zone == "left_arm"
        av = LeftArmCondAV
    elseif zone == "right_arm"
        av = RightArmCondAV
    elseif zone == "head"
        av = HeadCondAV
    endif
    float cur = player.GetValue(av)
    if cur > 0.0
        player.DamageValue(av, cur + 5.0)
    else
        player.SetValue(av, 0.0)
    endif
    SyncPlayerLimbPenalties(player)
    CompleteTestStage(30)
    Debug.Notification("Limb Crippled: " + zone + " (Speed " + appliedSpeedDelta + "%)")
    TraceCombat("PASS step=limb_crippled zone=" + zone + " speed_delta=" + appliedSpeedDelta + " sway=" + appliedSwayPenalty)
EndFunction

Function AttemptPlayerLimbCure(Actor player, string itemKind)
    if player == None
        return
    endif
    bool hc = IsHardcoreMode()
    int hcBit = 0
    if hc
        hcBit = 1
    endif
    if hc && itemKind == "stimpak"
        Debug.Notification("Hardcore Mode: Stimpaks do not mend crippled limbs (Doctor's Bag required).")
        TraceCombat("PASS step=limb_cure item=stimpak hardcore=1 cured=0")
        return
    endif

    player.RestoreValue(HeadCondAV, 100.0)
    player.RestoreValue(TorsoCondAV, 100.0)
    player.RestoreValue(LeftArmCondAV, 100.0)
    player.RestoreValue(RightArmCondAV, 100.0)
    player.RestoreValue(LeftLegCondAV, 100.0)
    player.RestoreValue(RightLegCondAV, 100.0)
    player.SetValue(HeadCondAV, 100.0)
    player.SetValue(TorsoCondAV, 100.0)
    player.SetValue(LeftArmCondAV, 100.0)
    player.SetValue(RightArmCondAV, 100.0)
    player.SetValue(LeftLegCondAV, 100.0)
    player.SetValue(RightLegCondAV, 100.0)
    SyncPlayerLimbPenalties(player)
    CompleteTestStage(30)
    Debug.Notification("All Crippled Limbs Restored (" + itemKind + ").")
    TraceCombat("PASS step=limb_cure item=" + itemKind + " hardcore=" + hcBit + " cured=1")
EndFunction

int Function ComputeVatsApCost(int calIdx, string zone)
    int baseAp = 28
    if IsShotgunCalibre(calIdx)
        baseAp = 30
    elseif IsEnergyCalibre(calIdx)
        baseAp = 25
    endif
    if zone == "head"
        return baseAp + 4
    elseif zone == "torso"
        return baseAp
    endif
    return baseAp + 2
EndFunction

int Function ComputeVatsHitChance(float distM, float skill, float per, string zone, int crippledArms)
    float factor = 1.00
    if zone == "head"
        factor = 0.65
    elseif zone == "left_arm" || zone == "right_arm"
        factor = 0.80
    elseif zone == "left_leg" || zone == "right_leg"
        factor = 0.82
    endif
    float raw = ((38.0 + (0.55 * skill) + (3.0 * per) - (1.60 * distM)) * factor) - (20.0 * (crippledArms as float))
    if raw < 5.0
        raw = 5.0
    elseif raw > 95.0
        raw = 95.0
    endif
    return (raw + 0.5) as int
EndFunction

Function ToggleVats()
    if vatsBusy
        return
    endif
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    vatsBusy = true
    player.AddSpell(VatsSlowTimeAb, false)
    VatsSlowTimeActiveGlobal.SetValue(1.0)

    ObjectReference target = VatsTargetRef
    if target == None || player.GetDistance(target) > 60.0
        target = ArmoredTargetRef
    endif
    float distM = 6.0
    if target != None
        distM = player.GetDistance(target)
        if distM > 35.0
            distM = 8.0
        endif
    endif

    int choice = VatsLimbPickerMsg.Show()
    if choice >= 0 && choice <= 5
        string zone = "torso"
        if choice == 0
            zone = "head"
        elseif choice == 1
            zone = "torso"
        elseif choice == 2
            zone = "left_arm"
        elseif choice == 3
            zone = "right_arm"
        elseif choice == 4
            zone = "left_leg"
        elseif choice == 5
            zone = "right_leg"
        endif

        Weapon weap = player.GetEquippedWeapon(0)
        int calIdx = FindCalibreIndex(weap)
        int slot = ActiveAmmoSubtypeGlobal.GetValue() as int
        int apCost = ComputeVatsApCost(calIdx, zone)
        float curAp = VatsApPoolGlobal.GetValue()
        int cArms = 0
        if player.GetValue(LeftArmCondAV) <= 0.0
            cArms += 1
        endif
        if player.GetValue(RightArmCondAV) <= 0.0
            cArms += 1
        endif
        int chance = ComputeVatsHitChance(distM, ReadPlayerGunsSkill(), ReadPlayerPerception(), zone, cArms)

        if curAp >= (apCost as float)
            VatsApPoolGlobal.SetValue(curAp - (apCost as float))
            if weap != None
                Ammo activeAmmo = ResolveActiveSubtypeAmmo(weap, calIdx, slot)
                weap.Fire(player, activeAmmo)
            endif
            int roll = Utility.RandomInt(1, 100)
            if roll <= chance
                ApplyZoneHitToTarget(target, zone, 4.0, 5.0, false)
            endif
            CompleteTestStage(40)
            TraceCombat("PASS step=vats_shot slow_time=1 zone=" + zone + " ap_cost=" + apCost + " chance=" + chance + " queued=1")
        else
            Debug.Notification("V.A.T.S.: Insufficient Action Points (" + (curAp as int) + "/" + apCost + ")")
            TraceCombat("vats_refused reason=insufficient_ap ap=" + curAp + " need=" + apCost)
        endif
    else
        TraceCombat("vats_cancelled slow_time=0")
    endif

    player.RemoveSpell(VatsSlowTimeAb)
    VatsSlowTimeActiveGlobal.SetValue(0.0)
    vatsBusy = false
EndFunction

Event OnHit(ObjectReference akTarget, ObjectReference akAggressor, Form akSource, Projectile akProjectile, bool abPowerAttack, bool abSneakAttack, bool abBashAttack, bool abHitBlocked, string asMaterialName)
    ; Re-register immediately because RegisterForHitEvent is single-shot per firing
    if akTarget != None
        RegisterForHitEvent(akTarget)
    endif

    Actor player = Game.GetPlayer()
    if player != None && akTarget == (player as ObjectReference)
        SyncPlayerLimbPenalties(player)
        return
    endif

    if akTarget == ZonePlateHeadRef
        ApplyZoneHitToTarget(akTarget, "head", 0.0, 0.0, false)
    elseif akTarget == ZonePlateTorsoRef
        ApplyZoneHitToTarget(akTarget, "torso", 0.0, 0.0, false)
    elseif akTarget == ZonePlateLeftArmRef
        ApplyZoneHitToTarget(akTarget, "left_arm", 0.0, 0.0, false)
    elseif akTarget == ZonePlateRightArmRef
        ApplyZoneHitToTarget(akTarget, "right_arm", 0.0, 0.0, false)
    elseif akTarget == ZonePlateLeftLegRef
        ApplyZoneHitToTarget(akTarget, "left_leg", 0.0, 0.0, false)
    elseif akTarget == ZonePlateRightLegRef
        ApplyZoneHitToTarget(akTarget, "right_leg", 0.0, 0.0, false)
    elseif akTarget == ArmoredTargetRef
        ApplyZoneHitToTarget(akTarget, "torso", 18.0, 15.0, true)
    elseif akTarget == VatsTargetRef
        ApplyZoneHitToTarget(akTarget, "torso", 4.0, 5.0, false)
    endif
EndEvent

Event Actor.OnItemEquipped(Actor akSender, Form akBaseObject, ObjectReference akReference)
    Actor player = Game.GetPlayer()
    if player == None || akSender != player
        return
    endif
    if akBaseObject == DoctorsBag
        AttemptPlayerLimbCure(player, "doctors_bag")
    elseif akBaseObject == CombatStimpak
        AttemptPlayerLimbCure(player, "stimpak")
    endif
EndEvent

Event ObjectReference.OnItemRemoved(ObjectReference akSender, Form akBaseItem, int aiItemCount, ObjectReference akItemReference, ObjectReference akDestContainer, int aiTransferReason)
    Actor player = Game.GetPlayer()
    if player == None || akSender != (player as ObjectReference) || akDestContainer != None
        return
    endif
    if akBaseItem == VatsTriggerToken
        if akItemReference != None
            akItemReference.Delete()
        endif
        player.AddItem(VatsTriggerToken, 1, true)
        ToggleVats()
    elseif akBaseItem == AmmoCycleToken
        if akItemReference != None
            akItemReference.Delete()
        endif
        player.AddItem(AmmoCycleToken, 1, true)
        CycleAmmoSubtype()
    endif
EndEvent

Event ObjectReference.OnActivate(ObjectReference akSender, ObjectReference akActionRef)
    Actor player = Game.GetPlayer()
    if player == None || akActionRef != (player as ObjectReference)
        return
    endif
    if akSender == AmmoCyclePedestalRef
        CycleAmmoSubtype()
    elseif akSender == LegTrapSwitchRef
        InflictPlayerLimbCripple("left_leg")
    elseif akSender == HardcoreToggleSwitchRef
        float cur = HardcoreOverrideGlobal.GetValue()
        if cur >= 0.5
            HardcoreOverrideGlobal.SetValue(0.0)
            Debug.Notification("Combat Cure Rule: Normal Mode (Stimpak cures limbs)")
            TraceCombat("mode hardcore_override=0")
        else
            HardcoreOverrideGlobal.SetValue(1.0)
            Debug.Notification("Combat Cure Rule: Hardcore Mode (Doctor's Bag required)")
            TraceCombat("mode hardcore_override=1")
        endif
    elseif akSender == SupplyRackRef
        if StarterRifle != None
            player.AddItem(StarterRifle, 1, false)
            player.EquipItem(StarterRifle, false, false)
            Ammo baseRifleAmmo = StarterRifle.GetAmmo()
            if baseRifleAmmo != None
                player.AddItem(baseRifleAmmo, 200, true)
            endif
        endif
        if StarterShotgun != None
            player.AddItem(StarterShotgun, 1, false)
            Ammo baseSgAmmo = StarterShotgun.GetAmmo()
            if baseSgAmmo != None
                player.AddItem(baseSgAmmo, 80, true)
            endif
        endif
        int i = 0
        while i < SubtypeAPList.GetSize()
            player.AddItem(SubtypeAPList.GetAt(i), 120, true)
            player.AddItem(SubtypeJHPList.GetAt(i), 120, true)
            player.AddItem(SubtypePlusPList.GetAt(i), 120, true)
            i += 1
        endwhile
        player.AddItem(CombatStimpak, 6, false)
        player.AddItem(DoctorsBag, 6, false)
        if player.GetItemCount(VatsTriggerToken) < 1
            player.AddItem(VatsTriggerToken, 1, true)
        endif
        if player.GetItemCount(AmmoCycleToken) < 1
            player.AddItem(AmmoCycleToken, 1, true)
        endif
        TraceCombat("supply_rack equipped=1 stimpaks=6 doctors_bags=6")
    endif
EndEvent
