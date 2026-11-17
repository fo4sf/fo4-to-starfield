Scriptname SoundCategorySnapshot extends Form
{Pure-Papyrus Starfield adapter for Fallout 4's removed SoundCategorySnapshot native form class.}

Function Push(float afTransitionSecs = 1.0)
    WwiseEvent.SetGlobalState("FO4SF_MixSnapshot", "Pushed")
EndFunction

Function Remove()
    WwiseEvent.SetGlobalState("FO4SF_MixSnapshot", "Default")
EndFunction
