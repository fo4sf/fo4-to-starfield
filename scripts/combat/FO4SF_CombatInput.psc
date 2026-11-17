Scriptname FO4SF_CombatInput Hidden
{Global zero-argument entry points dispatched by FO4SFCombat.dll (IVirtualMachine::DispatchStaticCall slot 0x2F)
 when the player presses VatsKey ('V') or AmmoKey ('N') during active gameplay.}

Function OnVatsKey() global
    FO4SF_CombatQuest q = Game.GetFormFromFile(0x000800, "FO4SFCombat.esm") as FO4SF_CombatQuest
    if q != None
        q.ToggleVats()
    endif
EndFunction

Function OnAmmoKey() global
    FO4SF_CombatQuest q = Game.GetFormFromFile(0x000800, "FO4SFCombat.esm") as FO4SF_CombatQuest
    if q != None
        q.CycleAmmoSubtype()
    endif
EndFunction
