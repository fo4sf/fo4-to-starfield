Scriptname FO4SF_NativeBridge Native Hidden
{SFSE native declarations for the 8 Fallout 4 engine functions that have no pure-Papyrus Starfield equivalent (5 called across all FO4 scripts: Dismember, GetLinkedRefChildren, ShowPipboyPlugin, ResetSpeechChallenges, IsDismembered; plus 3 zero-call completeness stubs).}

Function Dismember(Actor akActor, string asBodyPart, bool abForceExplode = false, bool abForceDismember = false, bool abForceBloodyMess = false) Global Native

bool Function IsDismembered(Actor akActor, string asBodyPart = "") Global Native

ObjectReference[] Function GetLinkedRefChildren(ObjectReference akRef, Keyword apKeyword = None) Global Native

Function ShowPipboyPlugin() Global Native

Function ResetSpeechChallenges(Quest akQuest) Global Native

Function SetEyeTexture(Actor akActor, TextureSet akNewTexture) Global Native

bool Function IsActivateChild(ObjectReference akParent, ObjectReference akChild) Global Native

Function TetherToHorse(ObjectReference akRef, ObjectReference akHorse) Global Native
