Scriptname SoundCategory extends Form
{Pure-Papyrus Starfield adapter for Fallout 4's removed SoundCategory native form class, forwarding bus volume and frequency controls to Wwise global RTPCs/states.}

Function Pause()
    WwiseEvent.SetGlobalState("FO4SF_AudioBusState", "Paused")
EndFunction

Function UnPause()
    WwiseEvent.SetGlobalState("FO4SF_AudioBusState", "Active")
EndFunction

Function Mute()
    WwiseEvent.SetGlobalRTPC("FO4SF_CategoryMute", 1.0)
EndFunction

Function UnMute()
    WwiseEvent.SetGlobalRTPC("FO4SF_CategoryMute", 0.0)
EndFunction

Function SetVolume(float afVolume)
    WwiseEvent.SetGlobalRTPC("FO4SF_CategoryVolume", afVolume)
EndFunction

Function SetFrequency(float afFrequencyCoeff)
    WwiseEvent.SetGlobalRTPC("FO4SF_CategoryFrequency", afFrequencyCoeff)
EndFunction
