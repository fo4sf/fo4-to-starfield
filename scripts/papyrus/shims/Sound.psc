Scriptname Sound extends Form
{Pure-Papyrus Starfield adapter for Fallout 4's removed Sound native form class, forwarding playback and instance controls to Starfield WwiseEvent.}

WwiseEvent Property MappedEvent Auto

int Function Play(ObjectReference akSource)
    if MappedEvent != None && akSource != None
        return MappedEvent.Play(akSource)
    endif
    return 0
EndFunction

bool Function PlayAndWait(ObjectReference akSource)
    if MappedEvent != None && akSource != None
        return MappedEvent.PlayAndWait(akSource)
    endif
    return true
EndFunction

Function StopInstance(int aiPlaybackInstance) Global
    if aiPlaybackInstance != 0
        WwiseEvent.StopInstance(aiPlaybackInstance)
    endif
EndFunction

Function SetInstanceVolume(int aiPlaybackInstance, float afVolume) Global
    if aiPlaybackInstance != 0
        WwiseEvent.UpdateInstanceRTPC(aiPlaybackInstance, "FO4SF_InstanceVolume", afVolume)
    endif
EndFunction
