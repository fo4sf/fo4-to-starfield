Scriptname FO4SF_Shim_PlayerUI Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 Utility menu-pause queries, Game HUD/SPECIAL/SSR helpers, Terminal.ShowOnPipboy, and LooksMenu event helpers.}

bool Function IsInMenuMode() Global
    return Utility.IsGameMenuPaused()
EndFunction

Function WaitMenuMode(float afSeconds) Global
    Utility.WaitMenuPause(afSeconds)
EndFunction

Function ForceDisableSSRGodraysDirLight(bool abDisableSSR, bool abDisableGodrays, bool abDisableDirLight) Global
    Game.ForceDisableSSRDirLight(abDisableSSR, abDisableDirLight)
EndFunction

Function ShowSPECIALMenu() Global
    Message specialMsg = Game.GetFormFromFile(0x00000804, "FO4SFNewGame.esm") as Message
    if specialMsg != None
        specialMsg.Show()
    endif
EndFunction

Function EnablePipboyHDRMask(bool abEnable = true) Global
EndFunction

Function SetInsideMemoryHUDMode(bool abInsideMemory) Global
EndFunction

Function ShowPerkVaultBoyOnHUD(string asVaultBoySwf, Sound akSound = None) Global
    if akSound != None
        akSound.Play(Game.GetPlayer())
    endif
EndFunction

Function ShowOnPipboy(Terminal akTerminal) Global
    FO4SF_NativeBridge.ShowPipboyPlugin()
EndFunction
