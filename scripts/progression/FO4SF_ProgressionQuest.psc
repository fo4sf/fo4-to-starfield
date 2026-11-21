Scriptname FO4SF_ProgressionQuest extends Quest
{Player Creation & Progression Core controller (CF-6): 40-pt SPECIAL (with off-by-default 28-pt GLOB) in <= 7-button boxes, 3-try standard-spread fallback, 13 NV skills, 9 Backgrounds, 9 Traits (0..2 + 1 free exit respec), GLOB-driven Perk cadence, shared Karma in FO4SFCoreValues.esm, and read-only faction state queries from FO4SFReputation.esm.}

; Exact property order pinned by dotnet/ProgressionCore/Program.cs and tests/test_progression_core.py
FormList Property SpecialAVList Auto Const
FormList Property SkillAVList Auto Const
FormList Property BackgroundPerks Auto Const
FormList Property TraitPerks Auto Const
FormList Property PlayablePerks Auto Const
ActorValue Property KarmaAV Auto Const
GlobalVariable Property KarmaGlobal Auto Const
GlobalVariable Property Pool28Global Auto Const
GlobalVariable Property PerkCadenceGlobal Auto Const
GlobalVariable Property QueuedPerkPointsGlobal Auto Const
GlobalVariable Property QueuedSkillPointsGlobal Auto Const
GlobalVariable Property TraitRespecUsedGlobal Auto Const
ActorValue Property CarryWeightAV Auto Const
ActorValue Property HealthAV Auto Const
GlobalVariable Property TestModeGlobal Auto Const
Message Property SpecialPage1Msg Auto Const
Message Property SpecialPage2Msg Auto Const
Message Property SpecialDefaultMsg Auto Const
Message Property TagSkillsPage1Msg Auto Const
Message Property TagSkillsPage2Msg Auto Const
Message Property TagSkillsPage3Msg Auto Const
Message Property BackgroundPage1Msg Auto Const
Message Property BackgroundPage2Msg Auto Const
Message Property TraitsPage1Msg Auto Const
Message Property TraitsPage2Msg Auto Const
Message Property TraitsPage3Msg Auto Const
Message Property RespecRefusedMsg Auto Const
string[] Property SpecialBoxNames Auto Const
int[] Property SpecialBoxButtonCounts Auto Const
; Placeholder standard S.P.E.C.I.A.L. spreads summing to the active pool (40: 6/5/5/6/7/6/5; 28: 4/4/4/4/4/4/4); the owner may change these values.
int[] Property StandardSpread40 Auto Const
int[] Property StandardSpread28 Auto Const

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
bool creationCompleted = false
bool specialAllocatedOnce = false
int liftSpecialFailures = 0

bool ran10 = false
bool ran15 = false
bool ran20 = false
bool ran30 = false
bool ran40 = false
bool ran50 = false

Function LogLine(string kind, string kv)
    Debug.OpenUserLog("FO4SFProgression")
    Debug.TraceUser("FO4SFProgression", "FO4SFPROG rt=" + Utility.GetCurrentRealTime() + " " + kind + " " + kv + " end=true")
EndFunction

Function LogNewGameLine(string msg)
    Debug.OpenUserLog("fo4sf_newgame")
    Debug.TraceUser("fo4sf_newgame", "FO4SF_NEWGAME rt=" + Utility.GetCurrentRealTime() + " " + msg)
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

bool Function ApplyCreationSheet(Actor player, int bgIdx, int t0, int t1, int s0, int s1, int s2, int s3, int s4, int s5, int s6, int tag0, int tag1, int tag2, string source = "")
    int reqPool = ActiveSpecialPool()
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
    if source != ""
        int traitCount = 0
        if t0 >= 0
            traitCount += 1
        endif
        if t1 >= 0 && t1 != t0
            traitCount += 1
        endif
        LogLine("creation_applied", "source=" + source + " bg=" + bgIdx + " traits=" + traitCount + " special_sum=" + sum + " skills_count=13 tags=" + tag0 + "," + tag1 + "," + tag2 + " carry_mod=" + appliedCarryMod)
    endif
    return true
EndFunction

int Function ActiveSpecialPool()
    if Pool28Global != None && Pool28Global.GetValue() >= 0.5
        return 28
    endif
    return 40
EndFunction

int Function CountSelectedTags(int[] tags)
    int c = 0
    if tags[0] >= 0
        c += 1
    endif
    if tags[1] >= 0
        c += 1
    endif
    if tags[2] >= 0
        c += 1
    endif
    return c
EndFunction

Function ToggleTagSkill(int[] tags, int skillIdx)
    if tags[0] == skillIdx
        tags[0] = tags[1]
        tags[1] = tags[2]
        tags[2] = -1
        return
    elseif tags[1] == skillIdx
        tags[1] = tags[2]
        tags[2] = -1
        return
    elseif tags[2] == skillIdx
        tags[2] = -1
        return
    endif
    if tags[0] < 0
        tags[0] = skillIdx
    elseif tags[1] < 0
        tags[1] = skillIdx
    elseif tags[2] < 0
        tags[2] = skillIdx
    else
        Debug.Notification("3 Tag Skills already selected")
    endif
EndFunction

int Function CountSelectedTraits(int[] traits)
    int c = 0
    if traits[0] >= 0
        c += 1
    endif
    if traits[1] >= 0
        c += 1
    endif
    return c
EndFunction

Function ToggleTraitPick(int[] traits, int traitIdx)
    if traits[0] == traitIdx
        traits[0] = traits[1]
        traits[1] = -1
        return
    elseif traits[1] == traitIdx
        traits[1] = -1
        return
    endif
    if traits[0] < 0
        traits[0] = traitIdx
    elseif traits[1] < 0
        traits[1] = traitIdx
    else
        Debug.Notification("At most 2 Traits can be selected")
    endif
EndFunction

int Function AdjustSpecialStat(int[] stats, int statIdx, int unspent, int step)
    if step > 0
        if unspent <= 0
            Debug.Notification("0 unspent points (toggle +1 / -1 to lower a stat)")
        elseif stats[statIdx] >= 10
            Debug.Notification("10 is the maximum for one S.P.E.C.I.A.L. stat")
        else
            stats[statIdx] += 1
            unspent -= 1
        endif
    else
        if stats[statIdx] <= 1
            Debug.Notification("1 is the minimum for one S.P.E.C.I.A.L. stat")
        else
            stats[statIdx] -= 1
            unspent += 1
        endif
    endif
    return unspent
EndFunction

bool Function RunSpecialMenu(Actor player, bool isRespec, int[] stats)
{Two-page <= 7-button S.P.E.C.I.A.L. allocation with Confirm reachable from Page 1; logs box Edid and button count from the writer's record table.}
    if SpecialPage1Msg == None || SpecialPage2Msg == None
        return false
    endif
    int reqPool = ActiveSpecialPool()
    int baseStat = 5
    if reqPool == 28
        baseStat = 4
    endif
    int sum = 0
    if isRespec
        int k = 0
        while k < 7
            int cur = player.GetValue(GetSpecialAV(k)) as int
            if cur < 1
                cur = 1
            elseif cur > 10
                cur = 10
            endif
            stats[k] = cur
            sum += cur
            k += 1
        endwhile
    endif
    if !isRespec || sum != reqPool
        int j = 0
        sum = 0
        while j < 7
            stats[j] = baseStat
            sum += baseStat
            j += 1
        endwhile
    endif
    int unspent = reqPool - sum
    int step = 1
    int pageIdx = 0
    int presses = 0
    while presses < 300
        presses += 1
        string boxName = SpecialBoxNames[pageIdx]
        int boxButtons = SpecialBoxButtonCounts[pageIdx]
        LogLine("special_box", "shown=1 box=" + boxName + " buttons=" + boxButtons + " unspent=" + unspent + " step=" + step)
        LogNewGameLine("special box shown box=" + boxName + " buttons=" + boxButtons + " unspent=" + unspent + " step=" + step)
        int btn = -1
        if pageIdx == 0
            btn = SpecialPage1Msg.Show(stats[0], stats[1], stats[2], stats[3], stats[4], stats[5], stats[6], unspent, step)
            if btn >= 0 && btn < 3
                unspent = AdjustSpecialStat(stats, btn, unspent, step)
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
            elseif btn == 3
                step = -step
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=3 unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=3 unspent=" + unspent + " step=" + step)
            elseif btn == 4
                pageIdx = 1
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=4 unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=4 unspent=" + unspent + " step=" + step)
            elseif btn == 5
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=5 unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=5 unspent=" + unspent + " step=" + step)
                if unspent != 0
                    Debug.Notification("Spend all S.P.E.C.I.A.L. points (" + unspent + " left)")
                else
                    return true
                endif
            else
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
                return false
            endif
        else
            btn = SpecialPage2Msg.Show(stats[0], stats[1], stats[2], stats[3], stats[4], stats[5], stats[6], unspent, step)
            if btn >= 0 && btn < 4
                unspent = AdjustSpecialStat(stats, 3 + btn, unspent, step)
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
            elseif btn == 4
                step = -step
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=4 unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=4 unspent=" + unspent + " step=" + step)
            elseif btn == 5
                pageIdx = 0
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=5 unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=5 unspent=" + unspent + " step=" + step)
            elseif btn == 6
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=6 unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=6 unspent=" + unspent + " step=" + step)
                if unspent != 0
                    Debug.Notification("Spend all S.P.E.C.I.A.L. points (" + unspent + " left)")
                else
                    return true
                endif
            else
                LogLine("special_press", "press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
                LogNewGameLine("special box press=" + presses + " box=" + boxName + " button=" + btn + " unspent=" + unspent + " step=" + step)
                return false
            endif
        endif
    endwhile
    return false
EndFunction

bool Function CommitSpecialAllocation(Actor player, int[] stats, string sourceTag, bool isDefault = false)
{Single shared write path for confirmed, native-menu, and standard-spread S.P.E.C.I.A.L. allocations.}
    int reqPool = ActiveSpecialPool()
    int sum = stats[0] + stats[1] + stats[2] + stats[3] + stats[4] + stats[5] + stats[6]
    if sum != reqPool
        LogLine("error", "reason=pool_mismatch sum=" + sum + " required=" + reqPool + " source=" + sourceTag)
        return false
    endif
    player.SetValue(GetSpecialAV(0), stats[0] as float)
    player.SetValue(GetSpecialAV(1), stats[1] as float)
    player.SetValue(GetSpecialAV(2), stats[2] as float)
    player.SetValue(GetSpecialAV(3), stats[3] as float)
    player.SetValue(GetSpecialAV(4), stats[4] as float)
    player.SetValue(GetSpecialAV(5), stats[5] as float)
    player.SetValue(GetSpecialAV(6), stats[6] as float)
    specialAllocatedOnce = true
    RecomputeSkillsAndDerived(player)
    LogLine("special", "set S=" + stats[0] + " P=" + stats[1] + " E=" + stats[2] + " C=" + stats[3] + " I=" + stats[4] + " A=" + stats[5] + " L=" + stats[6] + " sum=" + sum + " source=" + sourceTag)
    LogNewGameLine("special set S=" + stats[0] + " P=" + stats[1] + " E=" + stats[2] + " C=" + stats[3] + " I=" + stats[4] + " A=" + stats[5] + " L=" + stats[6] + " sum=" + sum + " source=" + sourceTag)
    if isDefault
        LogLine("special_default", "sum=" + sum + " source=" + sourceTag)
        LogNewGameLine("special default sum=" + sum + " source=" + sourceTag)
    endif
    return true
EndFunction

bool Function ApplyStandardSpread(Actor player, string sourceTag)
{Applies the active pool's standard spread (40: 6/5/5/6/7/6/5; 28: 4/4/4/4/4/4/4; placeholder values) through CommitSpecialAllocation.}
    if player == None
        return false
    endif
    int reqPool = ActiveSpecialPool()
    int[] stats = new int[7]
    int i = 0
    while i < 7
        if reqPool == 28
            stats[i] = StandardSpread28[i]
        else
            stats[i] = StandardSpread40[i]
        endif
        i += 1
    endwhile
    return CommitSpecialAllocation(player, stats, sourceTag, true)
EndFunction

bool Function OfferStandardSpread(string sourceTag, bool allowDecline = true)
{Offered after 3 failed S.P.E.C.I.A.L. tries on the lift or in Warfare; applies standard spread through CommitSpecialAllocation.}
    Actor player = Game.GetPlayer()
    if player == None
        return false
    endif
    int dBtn = 0
    if SpecialDefaultMsg != None
        dBtn = SpecialDefaultMsg.Show()
    endif
    if dBtn == 1 && allowDecline
        LogLine("special_default_declined", "source=" + sourceTag)
        LogNewGameLine("special default declined source=" + sourceTag)
        return false
    endif
    if sourceTag == "Lift" || sourceTag == "lift"
        liftSpecialFailures = 0
    endif
    return ApplyStandardSpread(player, sourceTag)
EndFunction

bool Function OpenSpecialAllocationOnly(string sourceTag)
{X3 / S5 / B3: Runs Progression's <= 7-button S.P.E.C.I.A.L. allocation; after 3 failed lift tries offers the standard spread.}
    Actor player = Game.GetPlayer()
    if player == None
        return false
    endif
    string normSource = sourceTag
    if normSource == "lift"
        normSource = "Lift"
    endif
    int[] stats = new int[7]
    if !RunSpecialMenu(player, specialAllocatedOnce, stats)
        LogLine("special_cancelled", "source=" + normSource)
        LogNewGameLine("special cancelled source=" + normSource)
        if normSource == "Lift"
            liftSpecialFailures += 1
            if liftSpecialFailures >= 3
                return OfferStandardSpread("Lift", true)
            endif
        endif
        return false
    endif
    if normSource == "Lift"
        liftSpecialFailures = 0
    endif
    return CommitSpecialAllocation(player, stats, normSource, false)
EndFunction

bool Function OpenAttributeAllocation(string sourceTag)
    return OpenSpecialAllocationOnly(sourceTag)
EndFunction

Function ApplyWarfareBackground(int bgIdx)
{S5: Sets the faction's background perk (e.g. 8 = Minuteman Volunteer) and recomputes derived skills.}
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif
    ClearListPerks(player, BackgroundPerks)
    activeBackgroundIdx = bgIdx
    if bgIdx >= 0 && bgIdx < BackgroundPerks.GetSize()
        Perk bgP = BackgroundPerks.GetAt(bgIdx) as Perk
        if bgP != None
            player.AddPerk(bgP)
        endif
    endif
    RecomputeSkillsAndDerived(player)
    LogLine("warfare_bg", "bg=" + bgIdx)
EndFunction

bool Function RunTagSkillsMenu(bool isRespec, int[] tags)
    if TagSkillsPage1Msg == None || TagSkillsPage2Msg == None || TagSkillsPage3Msg == None
        return false
    endif
    if isRespec && tagSkillIdx0 >= 0 && tagSkillIdx1 >= 0 && tagSkillIdx2 >= 0
        tags[0] = tagSkillIdx0
        tags[1] = tagSkillIdx1
        tags[2] = tagSkillIdx2
    else
        tags[0] = -1
        tags[1] = -1
        tags[2] = -1
    endif
    int page = 1
    int presses = 0
    while presses < 300
        presses += 1
        int sel = CountSelectedTags(tags)
        if page == 1
            int btn = TagSkillsPage1Msg.Show(sel)
            if btn >= 0 && btn < 4
                ToggleTagSkill(tags, btn)
            elseif btn == 4
                page = 2
            elseif btn == 5
                if CountSelectedTags(tags) == 3
                    return true
                endif
                Debug.Notification("Select 3 Tag Skills before confirming")
            else
                return false
            endif
        elseif page == 2
            int btn2 = TagSkillsPage2Msg.Show(sel)
            if btn2 >= 0 && btn2 < 5
                ToggleTagSkill(tags, 4 + btn2)
            elseif btn2 == 5
                page = 3
            elseif btn2 == 6
                page = 1
            else
                return false
            endif
        else
            int btn3 = TagSkillsPage3Msg.Show(sel)
            if btn3 >= 0 && btn3 < 4
                ToggleTagSkill(tags, 9 + btn3)
            elseif btn3 == 4
                page = 2
            elseif btn3 == 5
                tags[0] = -1
                tags[1] = -1
                tags[2] = -1
            elseif btn3 == 6
                if CountSelectedTags(tags) == 3
                    return true
                endif
                Debug.Notification("Select 3 Tag Skills before confirming")
            else
                return false
            endif
        endif
    endwhile
    return false
EndFunction

int Function RunBackgroundMenu()
    if BackgroundPage1Msg == None || BackgroundPage2Msg == None
        return -1
    endif
    int page = 1
    int presses = 0
    while presses < 100
        presses += 1
        if page == 1
            int btn = BackgroundPage1Msg.Show()
            if btn >= 0 && btn < 5
                return btn
            elseif btn == 5
                page = 2
            else
                return -1
            endif
        else
            int btn2 = BackgroundPage2Msg.Show()
            if btn2 >= 0 && btn2 < 4
                return 5 + btn2
            elseif btn2 == 4
                page = 1
            else
                return -1
            endif
        endif
    endwhile
    return -1
EndFunction

bool Function RunTraitsMenu(bool isRespec, int[] traits)
    if TraitsPage1Msg == None || TraitsPage2Msg == None || TraitsPage3Msg == None
        return false
    endif
    if isRespec
        traits[0] = activeTraitIdx0
        traits[1] = activeTraitIdx1
    else
        traits[0] = -1
        traits[1] = -1
    endif
    int page = 1
    int presses = 0
    while presses < 200
        presses += 1
        int sel = CountSelectedTraits(traits)
        if page == 1
            int btn = TraitsPage1Msg.Show(sel)
            if btn >= 0 && btn < 3
                ToggleTraitPick(traits, btn)
            elseif btn == 3
                page = 2
            elseif btn == 4
                traits[0] = -1
                traits[1] = -1
            elseif btn == 5
                return true
            else
                return false
            endif
        elseif page == 2
            int btn2 = TraitsPage2Msg.Show(sel)
            if btn2 >= 0 && btn2 < 3
                ToggleTraitPick(traits, 3 + btn2)
            elseif btn2 == 3
                page = 3
            elseif btn2 == 4
                page = 1
            elseif btn2 == 5
                return true
            else
                return false
            endif
        else
            int btn3 = TraitsPage3Msg.Show(sel)
            if btn3 >= 0 && btn3 < 3
                ToggleTraitPick(traits, 6 + btn3)
            elseif btn3 == 3
                page = 2
            elseif btn3 == 4
                traits[0] = -1
                traits[1] = -1
            elseif btn3 == 5
                return true
            else
                return false
            endif
        endif
    endwhile
    return false
EndFunction

bool Function OpenCreationSheetMenu()
{Interactive Creation Sheet via <= 7-button Message menus: 40-pt S.P.E.C.I.A.L., 3 of 13 Tag Skills, 1 Background, and 0..2 Traits.
 First completion applies creation (source=lift_menu); second completion performs the single Vault 111 lift respec; third is refused.}
    Actor player = Game.GetPlayer()
    if player == None
        return false
    endif
    if TraitRespecUsedGlobal != None && TraitRespecUsedGlobal.GetValue() >= 0.5
        LogLine("respec_refused", "source=lift_menu reason=limit_1")
        if RespecRefusedMsg != None
            RespecRefusedMsg.Show()
        endif
        return false
    endif
    bool isRespec = creationCompleted
    int[] stats = new int[7]
    if !RunSpecialMenu(player, isRespec, stats)
        LogLine("creation_cancelled", "step=special respec=" + isRespec)
        return false
    endif
    int[] tags = new int[3]
    if !RunTagSkillsMenu(isRespec, tags)
        LogLine("creation_cancelled", "step=tags respec=" + isRespec)
        return false
    endif
    int bgIdx = RunBackgroundMenu()
    if bgIdx < 0
        LogLine("creation_cancelled", "step=background respec=" + isRespec)
        return false
    endif
    int[] traits = new int[2]
    if !RunTraitsMenu(isRespec, traits)
        LogLine("creation_cancelled", "step=traits respec=" + isRespec)
        return false
    endif
    if !isRespec
        bool ok = ApplyCreationSheet(player, bgIdx, traits[0], traits[1], stats[0], stats[1], stats[2], stats[3], stats[4], stats[5], stats[6], tags[0], tags[1], tags[2], "lift_menu")
        if ok
            creationCompleted = true
        endif
        return ok
    endif
    bool baseOk = ApplyCreationSheet(player, bgIdx, activeTraitIdx0, activeTraitIdx1, stats[0], stats[1], stats[2], stats[3], stats[4], stats[5], stats[6], tags[0], tags[1], tags[2], "")
    bool respecOk = false
    if baseOk
        respecOk = ApplyExitTraitRespec(player, traits[0], traits[1])
    endif
    int sum = stats[0] + stats[1] + stats[2] + stats[3] + stats[4] + stats[5] + stats[6]
    LogLine("respec_applied", "source=lift_menu ok=" + respecOk + " bg=" + bgIdx + " t0=" + traits[0] + " t1=" + traits[1] + " special_sum=" + sum + " skills_count=13 respec_used=1")
    return respecOk
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

int Function ReadFactionRepState(int slotIndex)
    if slotIndex < 0 || slotIndex >= 15
        return -1
    endif
    GlobalVariable stateGlob = Game.GetFormFromFile(0x000870 + slotIndex, "FO4SFReputation.esm") as GlobalVariable
    if stateGlob == None
        return -1
    endif
    return stateGlob.GetValue() as int
EndFunction

bool Function ApplySpecialMenuCommit(Actor player)
    GlobalVariable reqGlob = Game.GetFormFromFile(0x000887, "FO4SFCoreValues.esm") as GlobalVariable
    if reqGlob == None || reqGlob.GetValue() < 0.5
        return false
    endif
    reqGlob.SetValue(0.0)

    GlobalVariable gS = Game.GetFormFromFile(0x000880, "FO4SFCoreValues.esm") as GlobalVariable
    GlobalVariable gP = Game.GetFormFromFile(0x000881, "FO4SFCoreValues.esm") as GlobalVariable
    GlobalVariable gE = Game.GetFormFromFile(0x000882, "FO4SFCoreValues.esm") as GlobalVariable
    GlobalVariable gC = Game.GetFormFromFile(0x000883, "FO4SFCoreValues.esm") as GlobalVariable
    GlobalVariable gI = Game.GetFormFromFile(0x000884, "FO4SFCoreValues.esm") as GlobalVariable
    GlobalVariable gA = Game.GetFormFromFile(0x000885, "FO4SFCoreValues.esm") as GlobalVariable
    GlobalVariable gL = Game.GetFormFromFile(0x000886, "FO4SFCoreValues.esm") as GlobalVariable
    if gS == None || gP == None || gE == None || gC == None || gI == None || gA == None || gL == None
        LogLine("error", "reason=special_menu_missing_globals source=fo4_menu")
        return false
    endif

    int s0 = gS.GetValue() as int
    int s1 = gP.GetValue() as int
    int s2 = gE.GetValue() as int
    int s3 = gC.GetValue() as int
    int s4 = gI.GetValue() as int
    int s5 = gA.GetValue() as int
    int s6 = gL.GetValue() as int
    if s0 < 1 || s0 > 10 || s1 < 1 || s1 > 10 || s2 < 1 || s2 > 10 || s3 < 1 || s3 > 10 || s4 < 1 || s4 > 10 || s5 < 1 || s5 > 10 || s6 < 1 || s6 > 10
        LogLine("error", "reason=special_menu_stat_range source=fo4_menu")
        return false
    endif

    int[] stats = new int[7]
    stats[0] = s0
    stats[1] = s1
    stats[2] = s2
    stats[3] = s3
    stats[4] = s4
    stats[5] = s5
    stats[6] = s6
    return CommitSpecialAllocation(player, stats, "fo4_menu", false)
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

Event OnStageSet(int auiStageID, int auiItemID)
    if auiStageID == 15 && !ran15
        ran15 = true
        OpenCreationSheetMenu()
    endif
EndEvent

Function PollStages()
    Actor player = Game.GetPlayer()
    if player == None
        return
    endif

    ApplySpecialMenuCommit(player)

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

    if !ran15 && GetStageDone(15)
        ran15 = true
        OpenCreationSheetMenu()
    endif

    if TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0
        ; Stage 10: Run Creation Flow (Vault Dweller + Good Natured & Small Frame + StandardSpread40 6/5/5/6/7/6/5 + Tags Speech/Guns/Lockpick)
        if !ran10 && GetStageDone(10)
            ran10 = true
            TraitRespecUsedGlobal.SetValue(0.0)
            Pool28Global.SetValue(0.0)
            bool ok = ApplyCreationSheet(player, 0, 6, 0, StandardSpread40[0], StandardSpread40[1], StandardSpread40[2], StandardSpread40[3], StandardSpread40[4], StandardSpread40[5], StandardSpread40[6], 10, 3, 4)
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

        ; Stage 40: Decoupled Karma (-800 Very Evil) + read-only faction state from FO4SFReputation.esm
        if !ran40 && GetStageDone(40)
            ran40 = true
            player.SetValue(KarmaAV, -800.0)
            KarmaGlobal.SetValue(-800.0)
            int repState = ReadFactionRepState(0)
            LogLine("karma_repu", "karma=" + player.GetValue(KarmaAV) + " karma_tier=" + KarmaTierToken(-800.0) + " faction_slot=0 rep_state=" + repState)
        endif

        ; Stage 50: Final summary line once all 4 checks executed
        if !ran50 && GetStageDone(50)
            ran50 = true
            bool allRan = ran10 && ran20 && ran30 && ran40
            LogLine("summary", "ok=" + allRan + " stages=10,20,30,40,50")
        endif
    endif
EndFunction

Event OnTimer(int aiTimerID)
    if aiTimerID != TimerIdPoll
        return
    endif
    PollStages()
    StartTimer(1.0, TimerIdPoll)
EndEvent
