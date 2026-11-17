Scriptname FO4SF_Shim_AudioWeather Hidden
{Pure-Papyrus Starfield shim library for Fallout 4 Sound, SoundCategory, SoundCategorySnapshot, and Weather classification helpers.}

int Function Play(Sound akSound, ObjectReference akSource) Global
    if akSound != None
        return akSound.Play(akSource)
    endif
    return 0
EndFunction

bool Function PlayAndWait(Sound akSound, ObjectReference akSource) Global
    if akSound != None
        return akSound.PlayAndWait(akSource)
    endif
    return true
EndFunction

Function StopInstance(int aiPlaybackInstance) Global
    Sound.StopInstance(aiPlaybackInstance)
EndFunction

Function SetInstanceVolume(int aiPlaybackInstance, float afVolume) Global
    Sound.SetInstanceVolume(aiPlaybackInstance, afVolume)
EndFunction

Function PushSnapshot(SoundCategorySnapshot akSnapshot, float afTransitionSecs = 1.0) Global
    if akSnapshot != None
        akSnapshot.Push(afTransitionSecs)
    endif
EndFunction

Function RemoveSnapshot(SoundCategorySnapshot akSnapshot) Global
    if akSnapshot != None
        akSnapshot.Remove()
    endif
EndFunction

Weather Function FindWeather(int aiType) Global
    return Weather.GetCurrentWeather()
EndFunction

int Function GetClassification(Weather akWeather) Global
    if akWeather == None
        return -1
    endif
    Keyword[] tags = akWeather.GetClassification()
    if tags == None || tags.Length == 0
        return 0
    endif
    return 1
EndFunction
