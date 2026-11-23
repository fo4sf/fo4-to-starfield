Scriptname FO4SF_ALifeBeaconEffect extends ActiveMagicEffect
{Field Transponder effect: shows the nearest A-Life squad and the nearest node's owner and territory counts in a
 message box, without console commands, and has the simulation quest return the item after use.}

FO4SF_ALifeSimQuest Property SimQuest Auto Const
{The A-Life simulation quest (plugin-local 0x800).}
Potion Property FieldTransponder Auto Const
{The transponder item itself.}

Event OnEffectStart(ObjectReference akTarget, Actor akCaster, MagicEffect akBaseEffect, float afMagnitude, float afDuration)
    Actor player = Game.GetPlayer()
    FO4SF_ALifeSimQuest q = SimQuest
    if q == None
        q = QuestFromOwnPlugin(akBaseEffect)
    endif
    if q == None
        Debug.MessageBox("A-Life transponder: no signal (simulation quest not found).")
        return
    endif
    Debug.MessageBox(q.BeaconReport(player))
    if akTarget == player
        q.OnTransponderUsed()
    endif
EndEvent

FO4SF_ALifeSimQuest Function QuestFromOwnPlugin(MagicEffect akEffect)
    ; the quest is local ID 0x800 of the plugin that holds this effect: keep the effect's load-order prefix
    ; (0xFE light: 12-bit local ID, 0xFD medium: 16-bit, otherwise 24-bit) and add 0x800. Papyrus has no bitwise
    ; operators, so the low bits are taken off with a non-negative remainder.
    if akEffect == None
        return None
    endif
    int id = akEffect.GetFormID()
    int low24 = id % 16777216
    if low24 < 0
        low24 += 16777216
    endif
    int top = (id - low24) / 16777216
    int span = 16777216
    if top == -2
        span = 4096
    elseif top == -3
        span = 65536
    endif
    int low = id % span
    if low < 0
        low += span
    endif
    return Game.GetForm(id - low + 2048) as FO4SF_ALifeSimQuest
EndFunction
