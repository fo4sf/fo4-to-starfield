"""Deterministic source-to-source Papyrus bridge rewriter for Fallout 4 -> Starfield v4.2 compilation.

Transforms non-native Fallout 4 `.psc` scripts in a scratch output tree so that:
1. Missing, renamed, and changed-signature member/global calls invoke our `FO4SF_Shim_*` or `FO4SF_NativeBridge` libraries.
2. Widened, extended, renamed, or removed engine `Event` headers match Starfield's `Native` base script declarations while binding local cast aliases so existing event bodies run unchanged.
3. External-receiver calls to methods that Starfield marked `Protected SelfOnly` on `ScriptObject` route through `FO4SF_Shim_QuestScene` relays.
4. Starfield newly-reserved type names (`Note`, `AffinityEvent`) and newly-`Native` `ObjectReference` method overrides (`GetContainer`, `SetOpen`, `GetOpenState`) are disambiguated cleanly.

Zero game source text is stored here; all transformations operate on caller-supplied `.psc` streams/folders.
"""
from __future__ import annotations

import re
from pathlib import Path

NATIVE_SCRIPT_RE = re.compile(r"^\s*scriptname\s+\S+(?:\s+\w+)*?\s+native\b", re.I | re.M)
SCRIPTNAME_RE = re.compile(r"^\s*scriptname\s+(?P<name>[\w:]+)(?:\s+extends\s+(?P<base>[\w:]+))?", re.I | re.M)

# Unambiguous 0-arg or N-arg FO4 member calls (<recv>.<name>(args) -> <Shim>.<Target>(<recv>, args))
MEMBER_SHIMS: dict[str, tuple[str, str]] = {
    # FO4SF_Shim_ActorAI
    "getactorbase": ("FO4SF_Shim_ActorAI", "GetActorBase"),
    "isbleedingout": ("FO4SF_Shim_ActorAI", "IsBleedingOut"),
    "allowcompanion": ("FO4SF_Shim_ActorAI", "AllowCompanion"),
    "disallowcompanion": ("FO4SF_Shim_ActorAI", "DisallowCompanion"),
    "setcompanion": ("FO4SF_Shim_ActorAI", "SetCompanion"),
    "setavailabletobecompanion": ("FO4SF_Shim_ActorAI", "SetAvailableToBeCompanion"),
    "followerfollow": ("FO4SF_Shim_ActorAI", "FollowerFollow"),
    "followerwait": ("FO4SF_Shim_ActorAI", "FollowerWait"),
    "followersetdistancenear": ("FO4SF_Shim_ActorAI", "FollowerSetDistanceNear"),
    "followersetdistancemedium": ("FO4SF_Shim_ActorAI", "FollowerSetDistanceMedium"),
    "followersetdistancefar": ("FO4SF_Shim_ActorAI", "FollowerSetDistanceFar"),
    "setanimarchetypeneutral": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeNeutral"),
    "setanimarchetypeconfident": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeConfident"),
    "setanimarchetypedepressed": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeDepressed"),
    "setanimarchetypeelderly": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeElderly"),
    "setanimarchetypefriendly": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeFriendly"),
    "setanimarchetypeirritated": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeIrritated"),
    "setanimarchetypenervous": ("FO4SF_Shim_ActorAI", "SetAnimArchetypeNervous"),
    "setdoganimarchetypeneutral": ("FO4SF_Shim_ActorAI", "SetDogAnimArchetypeNeutral"),
    "setdoganimarchetypeagitated": ("FO4SF_Shim_ActorAI", "SetDogAnimArchetypeAgitated"),
    "setdoganimarchetypealert": ("FO4SF_Shim_ActorAI", "SetDogAnimArchetypeAlert"),
    "setdoganimarchetypeplayful": ("FO4SF_Shim_ActorAI", "SetDogAnimArchetypePlayful"),
    "isinvulnerable": ("FO4SF_Shim_ActorAI", "IsInvulnerable"),
    "setinvulnerable": ("FO4SF_Shim_ActorAI", "SetInvulnerable"),
    # FO4SF_Shim_PowerArmor
    "isinpowerarmor": ("FO4SF_Shim_PowerArmor", "IsInPowerArmor"),
    # FO4SF_Shim_SurvivalRad
    "startcannibal": ("FO4SF_Shim_SurvivalRad", "StartCannibal"),
    "getassociatedskill": ("FO4SF_Shim_SurvivalRad", "GetAssociatedSkill"),
    # FO4SF_Shim_QuestScene
    "iscleared": ("FO4SF_Shim_QuestScene", "IsCleared"),
    "setcleared": ("FO4SF_Shim_QuestScene", "SetCleared"),
    "haseverbeencleared": ("FO4SF_Shim_QuestScene", "HasEverBeenCleared"),
    "sendstoryeventandwait": ("FO4SF_Shim_QuestScene", "SendStoryEventAndWait"),
    # FO4SF_Shim_ObjectRef
    "getlinkedrefarray": ("FO4SF_Shim_ObjectRef", "GetLinkedRefArray"),
    "sellitem": ("FO4SF_Shim_ObjectRef", "SellItem"),
    "deletewhenable": ("FO4SF_Shim_ObjectRef", "DeleteWhenAble"),
    "getencounterzone": ("FO4SF_Shim_ObjectRef", "GetEncounterZone"),
    "setmotiontype": ("FO4SF_Shim_ObjectRef", "SetMotionType"),
    # FO4SF_Shim_PlayerUI
    "showonpipboy": ("FO4SF_Shim_PlayerUI", "ShowOnPipboy"),
    # FO4SF_Shim_Workshop
    "makeradioreceiver": ("FO4SF_Shim_Workshop", "MakeRadioReceiver"),
    "recalculateresources": ("FO4SF_Shim_Workshop", "RecalculateResources"),
    "waitforworkshopresourcerecalc": ("FO4SF_Shim_Workshop", "WaitForWorkshopResourceRecalc"),
    "openworkshopsettlementmenu": ("FO4SF_Shim_Workshop", "OpenWorkshopSettlementMenu"),
    "openworkshopsettlementmenuex": ("FO4SF_Shim_Workshop", "OpenWorkshopSettlementMenuEx"),
    "getobjectcomponentcount": ("FO4SF_Shim_Workshop", "GetObjectComponentCount"),
    "removecomponents": ("FO4SF_Shim_Workshop", "RemoveComponents"),
    # FO4SF_Shim_AudioWeather
    "getclassification": ("FO4SF_Shim_AudioWeather", "GetClassification"),
    # FO4SF_NativeBridge
    "dismember": ("FO4SF_NativeBridge", "Dismember"),
    "isdismembered": ("FO4SF_NativeBridge", "IsDismembered"),
    "getlinkedrefchildren": ("FO4SF_NativeBridge", "GetLinkedRefChildren"),
    "resetspeechchallenges": ("FO4SF_NativeBridge", "ResetSpeechChallenges"),
    "seteyetexture": ("FO4SF_NativeBridge", "SetEyeTexture"),
    "isactivatechild": ("FO4SF_NativeBridge", "IsActivateChild"),
    "tethertohorse": ("FO4SF_NativeBridge", "TetherToHorse"),
}

# Arity-sensitive member calls
ARITY_MEMBER_SHIMS: dict[str, tuple[set[int], str, str]] = {
    "placeactoratme": ({3}, "FO4SF_Shim_ObjectRef", "PlaceActorAtMe"),
    "pathtoreference": ({2, 3}, "FO4SF_Shim_ActorAI", "PathToReference"),
}

# Global Class.Method(...) calls
GLOBAL_SHIMS: dict[tuple[str, str], tuple[str, str]] = {
    ("game", "showpipboyplugin"): ("FO4SF_NativeBridge", "ShowPipboyPlugin"),
    ("game", "showspecialmenu"): ("FO4SF_Shim_PlayerUI", "ShowSPECIALMenu"),
    ("game", "showperkvaultboyonhud"): ("FO4SF_Shim_PlayerUI", "ShowPerkVaultBoyOnHUD"),
    ("game", "setinsidememoryhudmode"): ("FO4SF_Shim_PlayerUI", "SetInsideMemoryHUDMode"),
    ("game", "enablepipboyhdrmask"): ("FO4SF_Shim_PlayerUI", "EnablePipboyHDRMask"),
    ("game", "forcedisablessrgodraysdirlight"): ("FO4SF_Shim_PlayerUI", "ForceDisableSSRGodraysDirLight"),
    ("utility", "isinmenumode"): ("FO4SF_Shim_PlayerUI", "IsInMenuMode"),
    ("utility", "waitmenumode"): ("FO4SF_Shim_PlayerUI", "WaitMenuMode"),
    ("weather", "findweather"): ("FO4SF_Shim_AudioWeather", "FindWeather"),
}

# Starfield ScriptObject Protected SelfOnly methods when called on an external receiver (<recv>.<method>(...))
SELF_ONLY_RELAYS: dict[str, str] = {
    "gotostate": "RelayGotoState",
    "getstate": "RelayGetState",
    "starttimer": "RelayStartTimer",
    "starttimergametime": "RelayStartTimerGameTime",
    "canceltimer": "RelayCancelTimer",
    "canceltimergametime": "RelayCancelTimerGameTime",
    "registerforcustomevent": "RelayRegisterForCustomEvent",
    "unregisterforcustomevent": "RelayUnregisterForCustomEvent",
    "sendcustomevent": "RelaySendCustomEvent",
    "registerforremoteevent": "RelayRegisterForRemoteEvent",
    "unregisterforremoteevent": "RelayUnregisterForRemoteEvent",
    "registerforanimationevent": "RelayRegisterForAnimationEvent",
    "unregisterforanimationevent": "RelayUnregisterForAnimationEvent",
    "registerforhitevent": "RelayRegisterForHitEvent",
    "unregisterforhitevent": "RelayUnregisterForHitEvent",
    "unregisterforallhitevents": "RelayUnregisterForAllHitEvents",
    "registerfordistancelessthanevent": "RelayRegisterForDistanceLessThanEvent",
    "registerfordistancegreaterthanevent": "RelayRegisterForDistanceGreaterThanEvent",
    "unregisterfordistanceevents": "RelayUnregisterForDistanceEvents",
    "registerfortutorialevent": "RelayRegisterForTutorialEvent",
    "unregisterfortutorialevent": "RelayUnregisterForTutorialEvent",
    "registerforplayersleep": "RelayRegisterForPlayerSleep",
    "unregisterforplayersleep": "RelayUnregisterForPlayerSleep",
    "registerforlos": "RelayRegisterForLOS",
    "unregisterforlos": "RelayUnregisterForLOS",
}

EVENT_RENAMES: dict[str, str] = {
    "onlocationcleared": "OnLocationExplored",
    "onstoryclearlocation": "OnStoryExploredLocation",
    "onworkshopobjectdestroyed": "OnObjectDestroyed",
    "onworkshopobjectrepaired": "OnObjectRepaired",
}

REMOVED_NATIVE_EVENTS = {"onholotapeplay", "onholotapechatter", "onlooksmenuevent"}

# Companion methods that exist BOTH as 0-arg wrappers on Actor AND 1-arg methods on FollowersScript
ZERO_ARG_ACTOR_COMPANION_METHODS = {
    "setavailabletobecompanion",
    "followerfollow",
    "followerwait",
    "followersetdistancenear",
    "followersetdistancemedium",
    "followersetdistancefar",
}

# Companion methods on Actor taking only bool flags (whereas FollowersScript takes an Actor as arg 0)
BOOL_ARG_ACTOR_COMPANION_METHODS = {
    "allowcompanion",
    "disallowcompanion",
    "setcompanion",
}

# Methods that Starfield made Native on ObjectReference, preventing non-native overrides
SEALED_OBJREF_METHODS = {"getcontainer", "setopen", "getopenstate"}


def _split_code_and_comment(line: str) -> tuple[str, str]:
    """Split a single line into (code, trailing_line_comment) respecting string literals."""
    in_str = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == ";" and not (i + 1 < n and line[i + 1] == "/"):
                return line[:i], line[i:]
        i += 1
    return line, ""


def _split_top_args(arg_str: str) -> list[str]:
    s = arg_str.strip()
    if not s:
        return []
    out = []
    depth = 0
    in_str = False
    start = 0
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in "([":
                depth += 1
            elif ch in ")]":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                out.append(s[start:i].strip())
                start = i + 1
        i += 1
    out.append(s[start:].strip())
    return out


def _tokenize_expr(code: str) -> list[tuple[str, str]]:
    """Tokenize code into ('STR'|'ID'|'WS'|'OP', text)."""
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if ch == '"':
            j = i + 1
            while j < n:
                if code[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if code[j] == '"':
                    j += 1
                    break
                j += 1
            tokens.append(("STR", code[i:j]))
            i = j
        elif ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (code[j].isalnum() or code[j] in "_:"):
                j += 1
            tokens.append(("ID", code[i:j]))
            i = j
        elif ch.isspace():
            j = i + 1
            while j < n and code[j].isspace():
                j += 1
            tokens.append(("WS", code[i:j]))
            i = j
        else:
            tokens.append(("OP", ch))
            i += 1
    return tokens


def _find_matching_open(tokens: list[tuple[str, str]], close_idx: int, open_ch: str, close_ch: str) -> int:
    depth = 0
    for idx in range(close_idx, -1, -1):
        kind, val = tokens[idx]
        if kind == "OP":
            if val == close_ch:
                depth += 1
            elif val == open_ch:
                depth -= 1
                if depth == 0:
                    return idx
    return -1


def _extract_receiver_start(tokens: list[tuple[str, str]], dot_idx: int) -> int:
    """Given token index of `.`, walk backward across primary/postfix chain to find start index of receiver."""
    idx = dot_idx - 1
    while idx >= 0 and tokens[idx][0] == "WS":
        idx -= 1
    if idx < 0:
        return -1

    while idx >= 0:
        kind, val = tokens[idx]
        if kind == "OP" and val == ")":
            open_idx = _find_matching_open(tokens, idx, "(", ")")
            if open_idx < 0:
                return -1
            idx = open_idx - 1
            # Could be call `foo(...)` or parenthesized `(expr)`
            k2 = idx
            while k2 >= 0 and tokens[k2][0] == "WS":
                k2 -= 1
            if k2 >= 0 and tokens[k2][0] == "ID" and tokens[k2][1].lower() not in {
                "if", "elseif", "while", "return", "as", "new", "and", "or",
            }:
                idx = k2
                continue
            else:
                # Parenthesized atom like `(x as Actor)` -> receiver starts at `open_idx`, unless preceded by `.`
                return open_idx
        elif kind == "OP" and val == "]":
            open_idx = _find_matching_open(tokens, idx, "[", "]")
            if open_idx < 0:
                return -1
            idx = open_idx - 1
            while idx >= 0 and tokens[idx][0] == "WS":
                idx -= 1
            continue
        elif kind == "ID":
            start = idx
            k2 = idx - 1
            while k2 >= 0 and tokens[k2][0] == "WS":
                k2 -= 1
            if k2 >= 0 and tokens[k2] == ("OP", "."):
                idx = k2 - 1
                while idx >= 0 and tokens[idx][0] == "WS":
                    idx -= 1
                continue
            return start
        else:
            return -1
    return -1


def _rewrite_remote_event_strings(arg_text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        ev = m.group(1)
        mapped = EVENT_RENAMES.get(ev.lower())
        return f'"{mapped}"' if mapped else m.group(0)

    return re.sub(r'"([A-Za-z0-9_]+)"', repl, arg_text)


def _rewrite_calls_in_code(code: str, local_funcs: set[str], renamed_local_methods: dict[str, str], imported_globals: set[str]) -> str:
    """Iteratively rewrite innermost call expressions until fixed point."""
    for _ in range(32):
        tokens = _tokenize_expr(code)
        changed = False
        i = 0
        n = len(tokens)
        while i < n:
            if tokens[i][0] == "ID":
                fn_name = tokens[i][1]
                fn_low = fn_name.lower()
                # Check if followed (ignoring WS) by '('
                p = i + 1
                while p < n and tokens[p][0] == "WS":
                    p += 1
                if p < n and tokens[p] == ("OP", "("):
                    # Find matching ')'
                    depth = 0
                    close_p = -1
                    for q in range(p, n):
                        if tokens[q][0] == "OP":
                            if tokens[q][1] == "(":
                                depth += 1
                            elif tokens[q][1] == ")":
                                depth -= 1
                                if depth == 0:
                                    close_p = q
                                    break
                    if close_p > p:
                        # Check if there are any unrewritten inner calls inside args first — let inner ones go first
                        raw_args = "".join(t[1] for t in tokens[p + 1:close_p])
                        rewritten_args = _rewrite_calls_in_code(raw_args, local_funcs, renamed_local_methods, imported_globals)
                        if rewritten_args != raw_args:
                            prefix = "".join(t[1] for t in tokens[:p + 1])
                            suffix = "".join(t[1] for t in tokens[close_p:])
                            code = prefix + rewritten_args + suffix
                            changed = True
                            break

                        args_list = _split_top_args(raw_args)
                        if fn_low in ("registerforremoteevent", "unregisterforremoteevent") and raw_args:
                            fixed_ev_args = _rewrite_remote_event_strings(raw_args)
                            if fixed_ev_args != raw_args:
                                prefix = "".join(t[1] for t in tokens[:p + 1])
                                suffix = "".join(t[1] for t in tokens[close_p:])
                                code = prefix + fixed_ev_args + suffix
                                changed = True
                                break

                        # Check if preceded by `.`
                        d = i - 1
                        while d >= 0 and tokens[d][0] == "WS":
                            d -= 1
                        has_dot = d >= 0 and tokens[d] == ("OP", ".")

                        if has_dot:
                            recv_start = _extract_receiver_start(tokens, d)
                            if recv_start >= 0:
                                recv_text = "".join(t[1] for t in tokens[recv_start:d]).strip()
                                recv_low = recv_text.lower()
                                replacement = None

                                # Do not double-rewrite our own FO4SF_Shim_* / FO4SF_NativeBridge static class calls
                                if "(" not in recv_low and (recv_low.startswith("fo4sf_shim_") or recv_low == "fo4sf_nativebridge"):
                                    replacement = None
                                elif recv_low == "game" and fn_low == "getcommonproperties":
                                    replacement = "(FO4SF_Shim_QuestScene.GetCommonPropertiesQuest() as CommonPropertiesScript)"
                                elif (recv_low, fn_low) in GLOBAL_SHIMS:
                                    shim_cls, shim_fn = GLOBAL_SHIMS[(recv_low, fn_low)]
                                    replacement = f"{shim_cls}.{shim_fn}({raw_args.strip()})"
                                elif recv_low in ("self", "parent") and fn_low == "registerforlooksmenuevent":
                                    replacement = f'{recv_text}.RegisterForMenuOpenCloseEvent("ChargenMenu")'
                                elif recv_low in ("self", "parent") and fn_low == "unregisterforlooksmenuevent":
                                    replacement = f'{recv_text}.UnregisterForMenuOpenCloseEvent("ChargenMenu")'
                                elif recv_low in ("self", "parent") and fn_low in renamed_local_methods:
                                    replacement = f"{recv_text}.{renamed_local_methods[fn_low]}({raw_args.strip()})"
                                elif fn_low in ("oneffectstart", "oneffectfinish") and len(args_list) == 2 and fn_low not in local_funcs:
                                    replacement = f"{recv_text}.{fn_name}({raw_args.strip()}, None, 0.0, 0.0)"
                                elif fn_low in ZERO_ARG_ACTOR_COMPANION_METHODS and fn_low not in local_funcs:
                                    if len(args_list) == 0:
                                        shim_cls, shim_fn = MEMBER_SHIMS[fn_low]
                                        replacement = f"{shim_cls}.{shim_fn}({recv_text})"
                                elif fn_low in BOOL_ARG_ACTOR_COMPANION_METHODS and fn_low not in local_funcs:
                                    first_arg = args_list[0].lower() if args_list else ""
                                    is_actor_wrapper = (
                                        len(args_list) == 0
                                        or first_arg in ("true", "false")
                                        or "=" in first_arg
                                    ) and "follower" not in recv_low and "getscript" not in recv_low
                                    if is_actor_wrapper:
                                        shim_cls, shim_fn = MEMBER_SHIMS[fn_low]
                                        joined = f"{recv_text}, {raw_args.strip()}" if raw_args.strip() else recv_text
                                        replacement = f"{shim_cls}.{shim_fn}({joined})"
                                elif fn_low in MEMBER_SHIMS and fn_low not in local_funcs:
                                    shim_cls, shim_fn = MEMBER_SHIMS[fn_low]
                                    joined = f"{recv_text}, {raw_args.strip()}" if raw_args.strip() else recv_text
                                    replacement = f"{shim_cls}.{shim_fn}({joined})"
                                elif fn_low in ARITY_MEMBER_SHIMS and len(args_list) in ARITY_MEMBER_SHIMS[fn_low][0] and fn_low not in local_funcs:
                                    _, shim_cls, shim_fn = ARITY_MEMBER_SHIMS[fn_low]
                                    joined = f"{recv_text}, {raw_args.strip()}" if raw_args.strip() else recv_text
                                    replacement = f"{shim_cls}.{shim_fn}({joined})"
                                elif fn_low in SELF_ONLY_RELAYS and recv_low not in ("self", "parent"):
                                    relay_fn = SELF_ONLY_RELAYS[fn_low]
                                    if fn_low == "sendcustomevent":
                                        # Quote bare CustomEventName identifier into string for relay signature
                                        if args_list and not args_list[0].startswith('"'):
                                            ev_tok = args_list[0]
                                            if ev_tok.lower() == "affinityevent":
                                                ev_tok = "FO4SF_AffinityEvent"
                                            rest_args = [f'"{ev_tok}"'] + args_list[1:]
                                            joined = f"{recv_text}, {', '.join(rest_args)}"
                                        else:
                                            joined = f"{recv_text}, {raw_args.strip()}" if raw_args.strip() else recv_text
                                    elif fn_low in ("registerforcustomevent", "unregisterforcustomevent"):
                                        if len(args_list) >= 2 and not args_list[1].startswith('"'):
                                            ev_tok = args_list[1]
                                            rest_args = [args_list[0], f'"{ev_tok}"'] + args_list[2:]
                                            joined = f"{recv_text}, {', '.join(rest_args)}"
                                        else:
                                            joined = f"{recv_text}, {raw_args.strip()}" if raw_args.strip() else recv_text
                                    else:
                                        joined = f"{recv_text}, {raw_args.strip()}" if raw_args.strip() else recv_text
                                    replacement = f"FO4SF_Shim_QuestScene.{relay_fn}({joined})"

                                if replacement is not None:
                                    prefix = "".join(t[1] for t in tokens[:recv_start])
                                    suffix = "".join(t[1] for t in tokens[close_p + 1:])
                                    code = prefix + replacement + suffix
                                    changed = True
                                    break
                        else:
                            # Bare/unqualified call (either Self method or Import-ed Global like `WaitMenuMode(1.0)` or `GetCommonProperties()`)
                            # Make sure not preceded by `Function` or `Event`
                            prev_k = i - 1
                            while prev_k >= 0 and tokens[prev_k][0] == "WS":
                                prev_k -= 1
                            is_decl = prev_k >= 0 and tokens[prev_k][0] == "ID" and tokens[prev_k][1].lower() in ("function", "event")
                            if not is_decl:
                                replacement = None
                                if fn_low in renamed_local_methods:
                                    replacement = f"{renamed_local_methods[fn_low]}({raw_args.strip()})"
                                elif fn_low in ("oneffectstart", "oneffectfinish") and len(args_list) == 2 and fn_low not in local_funcs:
                                    replacement = f"{fn_name}({raw_args.strip()}, None, 0.0, 0.0)"
                                elif fn_low == "registerforlooksmenuevent":
                                    replacement = 'RegisterForMenuOpenCloseEvent("ChargenMenu")'
                                elif fn_low == "unregisterforlooksmenuevent":
                                    replacement = 'UnregisterForMenuOpenCloseEvent("ChargenMenu")'
                                elif fn_low == "getcommonproperties" and "game" in imported_globals:
                                    replacement = "(FO4SF_Shim_QuestScene.GetCommonPropertiesQuest() as CommonPropertiesScript)"
                                elif fn_low not in local_funcs:
                                    for (g_cls, g_fn), (shim_cls, shim_fn) in GLOBAL_SHIMS.items():
                                        if fn_low == g_fn and g_cls in imported_globals:
                                            replacement = f"{shim_cls}.{shim_fn}({raw_args.strip()})"
                                            break
                                    if replacement is None and fn_low in MEMBER_SHIMS:
                                        shim_cls, shim_fn = MEMBER_SHIMS[fn_low]
                                        joined = f"Self, {raw_args.strip()}" if raw_args.strip() else "Self"
                                        replacement = f"{shim_cls}.{shim_fn}({joined})"
                                    elif replacement is None and fn_low in ARITY_MEMBER_SHIMS and len(args_list) in ARITY_MEMBER_SHIMS[fn_low][0]:
                                        _, shim_cls, shim_fn = ARITY_MEMBER_SHIMS[fn_low]
                                        joined = f"Self, {raw_args.strip()}" if raw_args.strip() else "Self"
                                        replacement = f"{shim_cls}.{shim_fn}({joined})"

                                if replacement is not None:
                                    prefix = "".join(t[1] for t in tokens[:i])
                                    suffix = "".join(t[1] for t in tokens[close_p + 1:])
                                    code = prefix + replacement + suffix
                                    changed = True
                                    break
            i += 1
        if not changed:
            break
    return code


def _parse_param(param: str) -> tuple[str, str, str]:
    """Return (type_str, var_name, default_suffix) for a Papyrus parameter declaration."""
    eq = param.find("=")
    if eq >= 0:
        lhs, default_part = param[:eq].strip(), " " + param[eq:].strip()
    else:
        lhs, default_part = param.strip(), ""
    parts = lhs.split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1], default_part
    return lhs, "", default_part


def _rewrite_event_header(indent: str, code: str) -> tuple[str, list[str], bool]:
    """Rewrite an `Event ...(...)` header if needed. Returns (new_code, injected_body_lines, converted_to_function)."""
    m = re.match(r"^(?P<lead>\s*Event\s+)(?P<target>(?:[\w:]+\s*\.\s*)?)(?P<name>\w+)\s*\((?P<params>.*)\)(?P<tail>.*)$", code, re.I)
    if not m:
        return code, [], False

    target = m.group("target").strip().rstrip(".").strip()
    ev_name = m.group("name")
    ev_low = ev_name.lower()
    raw_params = m.group("params")
    tail = m.group("tail")
    if re.search(r"\bnative\b", tail, re.I):
        return code, [], False

    params = _split_top_args(raw_params)

    # 1. Removed native events (OnHolotapePlay / OnHolotapeChatter / OnLooksMenuEvent) -> callable Function
    if not target and ev_low in REMOVED_NATIVE_EVENTS:
        return f"{indent}Function FO4SF_{ev_name}({raw_params}){tail}", [], True

    # 3. Renamed events (OnLocationCleared, OnStoryClearLocation, OnWorkshopObjectDestroyed, OnWorkshopObjectRepaired)
    if ev_low in EVENT_RENAMES:
        ev_name = EVENT_RENAMES[ev_low]
        ev_low = ev_name.lower()

    # 4. ActiveMagicEffect.OnEffectStart / OnEffectFinish (2 params -> 5 params, or remote 3 params -> 6 params; no defaults per ActiveMagicEffect.psc)
    if ev_low in ("oneffectstart", "oneffectfinish"):
        if not target and len(params) == 2:
            t0, p0, _ = _parse_param(params[0])
            new_p = f"ObjectReference __fo4sf_target, {params[1]}, MagicEffect __fo4sf_effect, float __fo4sf_mag, float __fo4sf_dur"
            inj = [f"{indent}    {t0} {p0} = __fo4sf_target as {t0}"] if t0.lower() != "objectreference" else [f"{indent}    ObjectReference {p0} = __fo4sf_target"]
            return f"{indent}Event {ev_name}({new_p}){tail}", inj, False
        if target and len(params) == 3:
            t1, p1, _ = _parse_param(params[1])
            new_p = f"{params[0]}, ObjectReference __fo4sf_target, {params[2]}, MagicEffect __fo4sf_effect, float __fo4sf_mag, float __fo4sf_dur"
            inj = [f"{indent}    {t1} {p1} = __fo4sf_target as {t1}"]
            return f"{indent}Event {target}.{ev_name}({new_p}){tail}", inj, False

    # 5. OnDeath / OnDying / OnKill: last parameter widened from Actor -> ObjectReference
    if ev_low in ("ondeath", "ondying", "onkill") and len(params) >= 1:
        t_last, p_last, def_last = _parse_param(params[-1])
        if t_last.lower() == "actor":
            new_params = params[:-1] + [f"ObjectReference __fo4sf_{p_last}{def_last}"]
            inj = [f"{indent}    Actor {p_last} = __fo4sf_{p_last} as Actor"]
            tgt_prefix = f"{target}." if target else ""
            return f"{indent}Event {tgt_prefix}{ev_name}({', '.join(new_params)}){tail}", inj, False

    # 6. OnCombatStateChanged: second-to-last parameter widened from Actor -> ObjectReference
    if ev_low == "oncombatstatechanged" and len(params) >= 2:
        t_tgt, p_tgt, def_tgt = _parse_param(params[-2])
        if t_tgt.lower() == "actor":
            new_params = params[:-2] + [f"ObjectReference __fo4sf_{p_tgt}{def_tgt}", params[-1]]
            inj = [f"{indent}    Actor {p_tgt} = __fo4sf_{p_tgt} as Actor"]
            tgt_prefix = f"{target}." if target else ""
            return f"{indent}Event {tgt_prefix}{ev_name}({', '.join(new_params)}){tail}", inj, False

    # 7. OnItemAdded / OnItemRemoved: trailing `int aiTransferReason` added (4->5 local, 5->6 RefCol/remote, 6->7 remote RefCol)
    if ev_low in ("onitemadded", "onitemremoved"):
        t_last, _, _ = _parse_param(params[-1]) if params else ("", "", "")
        if t_last.lower() != "int" and len(params) in (4, 5, 6):
            new_params = params + ["int __fo4sf_transferReason"]
            tgt_prefix = f"{target}." if target else ""
            return f"{indent}Event {tgt_prefix}{ev_name}({', '.join(new_params)}){tail}", [], False

    # 8. OnDistanceLessThan / OnDistanceGreaterThan: trailing `int aiEventID` added (3->4 local, 4->5 remote)
    if ev_low in ("ondistancelessthan", "ondistancegreaterthan"):
        t_last, _, _ = _parse_param(params[-1]) if params else ("", "", "")
        if t_last.lower() != "int" and len(params) in (3, 4):
            new_params = params + ["int __fo4sf_eventID"]
            tgt_prefix = f"{target}." if target else ""
            return f"{indent}Event {tgt_prefix}{ev_name}({', '.join(new_params)}){tail}", [], False

    # 9. Quest.OnStoryPickLock: trailing `bool abCrime` added (2->3 local, 3->4 remote)
    if ev_low == "onstorypicklock":
        t_last, _, _ = _parse_param(params[-1]) if params else ("", "", "")
        if t_last.lower() != "bool" and len(params) in (2, 3):
            new_params = params + ["bool __fo4sf_crime"]
            tgt_prefix = f"{target}." if target else ""
            return f"{indent}Event {tgt_prefix}{ev_name}({', '.join(new_params)}){tail}", [], False

    tgt_prefix = f"{target}." if target else ""
    return f"{indent}Event {tgt_prefix}{ev_name}({raw_params}){tail}", [], False


def rewrite_source(source: str) -> str:
    """Rewrite one Fallout 4 Papyrus `.psc` source text for Starfield v4.2 compatibility."""
    if NATIVE_SCRIPT_RE.search(source[:4096]):
        return source

    # Pre-scan local function definitions, Import statements, CustomEvent AffinityEvent, and `note` identifier collision
    local_funcs: set[str] = set()
    renamed_local_methods: dict[str, str] = {}
    imported_globals: set[str] = set()
    has_affinity_customevent = False
    has_note_ident = False

    for raw_line in source.splitlines():
        code_part, _ = _split_code_and_comment(raw_line)
        s = code_part.strip()
        if not s:
            continue
        m_imp = re.match(r"^import\s+([\w:]+)\s*$", s, re.I)
        if m_imp:
            imported_globals.add(m_imp.group(1).lower())
            continue
        m_fn = re.match(r"^(?:[\w:]+\s*(?:\[\s*\])?\s+)?function\s+(\w+)\s*\(", s, re.I)
        if m_fn:
            fn = m_fn.group(1).lower()
            if fn in SEALED_OBJREF_METHODS:
                renamed_local_methods[fn] = f"FO4SF_Local_{m_fn.group(1)}"
            else:
                local_funcs.add(fn)
        if re.search(r"\baffinityevent\b", s, re.I):
            has_affinity_customevent = True
        if re.search(r"\b(?:property|objectreference|book|form|referencealias|var|int|bool|string)\s+note\b", s, re.I):
            has_note_ident = True

    lines = source.splitlines()
    out_lines: list[str] = []
    in_block_comment = False
    in_doc_comment = False
    in_converted_event_fn = False
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]

        # Handle multi-line doc `{ ... }` and block `;/ ... /;` comments conservatively
        stripped = raw.lstrip()
        if in_doc_comment:
            out_lines.append(raw)
            if "}" in raw:
                in_doc_comment = False
            i += 1
            continue
        if in_block_comment:
            out_lines.append(raw)
            if "/;" in raw:
                in_block_comment = False
            i += 1
            continue
        if stripped.startswith("{"):
            out_lines.append(raw)
            if "}" not in stripped[1:]:
                in_doc_comment = True
            i += 1
            continue
        if stripped.startswith(";/"):
            out_lines.append(raw)
            if "/;" not in stripped[2:]:
                in_block_comment = True
            i += 1
            continue

        # Join `\` continuations into one logical line
        logical_code_parts: list[str] = []
        trailing_comment = ""
        while i < n:
            c_part, cmt_part = _split_code_and_comment(lines[i])
            if c_part.rstrip().endswith("\\"):
                logical_code_parts.append(c_part.rstrip()[:-1] + " ")
                i += 1
            else:
                logical_code_parts.append(c_part)
                trailing_comment = cmt_part
                i += 1
                break

        code = "".join(logical_code_parts)
        if not code.strip():
            out_lines.append(code + trailing_comment)
            continue

        indent = code[: len(code) - len(code.lstrip())]

        # Disambiguate Starfield newly-reserved script names `AffinityEvent` and `Note`
        if has_affinity_customevent:
            code = re.sub(r"\bCustomEvent\s+AffinityEvent\b", "CustomEvent FO4SF_AffinityEvent", code, flags=re.I)
            code = re.sub(r'("|\b)AffinityEvent("|\b)', lambda m: f"{m.group(1)}FO4SF_AffinityEvent{m.group(2)}", code)
        if has_note_ident:
            # Rename bare identifier `note` outside string literals
            toks = _tokenize_expr(code)
            code = "".join(("fo4sf_note" if (tk == "ID" and tv.lower() == "note") else tv) for tk, tv in toks)

        # Rename local overrides of newly-Native ObjectReference methods (`GetContainer`, `SetOpen`, `GetOpenState`)
        m_fn_decl = re.match(r"^(?P<pre>\s*(?:[\w:]+\s*(?:\[\s*\])?\s+)?function\s+)(?P<fn>\w+)(?P<rest>\s*\(.*)$", code, re.I)
        if m_fn_decl and m_fn_decl.group("fn").lower() in renamed_local_methods:
            new_fn = renamed_local_methods[m_fn_decl.group("fn").lower()]
            code = f"{m_fn_decl.group('pre')}{new_fn}{m_fn_decl.group('rest')}"

        # Check EndEvent matching a converted `Event OnHolotape*` -> `EndFunction`
        if in_converted_event_fn and re.match(r"^\s*EndEvent\b", code, re.I):
            code = re.sub(r"\bEndEvent\b", "EndFunction", code, flags=re.I)
            in_converted_event_fn = False
            out_lines.append(code + trailing_comment)
            continue

        # Check Event header rewrites
        if re.match(r"^\s*Event\b", code, re.I):
            new_code, injected, converted_fn = _rewrite_event_header(indent, code)
            if converted_fn:
                in_converted_event_fn = True
            out_lines.append(new_code + trailing_comment)
            out_lines.extend(injected)
            continue

        # Rewrite function/member/SelfOnly calls
        code = _rewrite_calls_in_code(code, local_funcs, renamed_local_methods, imported_globals)
        out_lines.append(code + trailing_comment)

    return "\n".join(out_lines) + ("\n" if source.endswith("\n") else "")


def rewrite_tree(fo4_root: str | Path, out_root: str | Path, scripts: list[str] | None = None) -> int:
    """Rewrite all `.psc` files under `fo4_root` into `out_root`. Returns number of files modified."""
    src_root = Path(fo4_root)
    dst_root = Path(out_root)
    rels = scripts if scripts is not None else sorted(
        p.relative_to(src_root).as_posix() for p in src_root.rglob("*") if p.is_file() and p.suffix.lower() == ".psc"
    )
    modified = 0
    for rel in rels:
        src_path = src_root / rel
        raw = src_path.read_text(encoding="utf-8", errors="replace")
        rewritten = rewrite_source(raw)
        if rewritten != raw:
            modified += 1
        dst_path = dst_root / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_text(rewritten, encoding="utf-8", newline="\n")
    return modified
