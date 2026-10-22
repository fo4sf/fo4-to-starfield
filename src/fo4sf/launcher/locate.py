"""locate: find the player's Steam installs of Fallout 4 and Starfield, so detect needs no typed paths (framework
item 4, section 1). Read only.

The route is the one MO2 takes (stores.md, gamegamebryo.cpp:456-485): Steam's folder from the registry
(HKCU\\Software\\Valve\\Steam, SteamPath), its libraries from config\\libraryfolders.vdf, and each game from the
library's steamapps\\appmanifest_<appid>.acf ("installdir", under steamapps\\common). Depot downloads (the owner's
Fallout 4 sits in steamapps\\content\\app_377160\\depot_*) are listed too: detect accepts several data folders.

Version 1 supports Steam Starfield only (owner, RE-12) and Steam, then GOG, Fallout 4 (LA-5). GOG Fallout 4 is found
the way LOOT finds it (stores.md, gog.cpp:36-45): HKLM\\Software\\GOG.com\\Games\\1998527297 value "path", else the
uninstall key 1998527297_is1 value "InstallLocation". GOG ships only 1.10.163.0.
"""
import os
import re

FALLOUT4_APPID = "377160"
STARFIELD_APPID = "1716740"
GOG_FALLOUT4_ID = "1998527297"
_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*')


def parse_vdf(text):
    """Valve KeyValues text (libraryfolders.vdf, appmanifest_*.acf) as nested dicts; keys keep their case."""
    stack, cur, key = [], {}, None
    for m in _TOKEN.finditer(text):
        s, brace = m.group(1), m.group(2)
        if s is None and brace is None:
            continue                                  # a comment
        if brace == "{":
            if key is None:
                raise ValueError("vdf: '{' without a key")
            new = {}
            cur[key] = new
            stack.append(cur)
            cur, key = new, None
        elif brace == "}":
            if not stack:
                raise ValueError("vdf: unbalanced '}'")
            cur, key = stack.pop(), None
        elif key is None:
            key = s.replace("\\\\", "\\")
        else:
            cur[key] = s.replace("\\\\", "\\")
            key = None
    if stack:
        raise ValueError("vdf: unclosed '{'")
    return cur


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _get_ci(d, name):
    for k, v in (d or {}).items():
        if k.casefold() == name.casefold():
            return v
    return None


def steam_path_from_registry():
    """SteamPath from the Windows registry, or None (not Windows, or no Steam)."""
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return os.path.normpath(winreg.QueryValueEx(k, "SteamPath")[0])
    except OSError:
        return None


def gog_fallout4_from_registry():
    """GOG Fallout 4's install folder from the Windows registry, or None."""
    if os.name != "nt":
        return None
    import winreg
    keys = ((rf"Software\GOG.com\Games\{GOG_FALLOUT4_ID}", "path"),
            (rf"Software\WOW6432Node\GOG.com\Games\{GOG_FALLOUT4_ID}", "path"),
            (rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{GOG_FALLOUT4_ID}_is1", "InstallLocation"))
    for key, value in keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                p = os.path.normpath(winreg.QueryValueEx(k, value)[0])
        except OSError:
            continue
        if os.path.isdir(p):
            return p
    return None


def libraries(steam):
    """Every Steam library folder: Steam's own, then those libraryfolders.vdf lists (new and old layouts)."""
    out = [os.path.normpath(steam)]
    # Windows paths ignore case, and libraryfolders.vdf may list Steam's own folder in lower case ("c:\\program files
    # (x86)\\steam", seen on the PC 2026-10-22): compare by normcase, or every depot is listed twice
    seen = {os.path.normcase(out[0])}
    for rel in (os.path.join("config", "libraryfolders.vdf"), os.path.join("steamapps", "libraryfolders.vdf")):
        text = _read(os.path.join(steam, rel))
        if text is None:
            continue
        lf = _get_ci(parse_vdf(text), "libraryfolders") or {}
        for k, v in lf.items():
            if not k.isdigit():
                continue
            p = _get_ci(v, "path") if isinstance(v, dict) else v      # new layout: {"path": ...}; old: the path
            if p and os.path.normcase(os.path.normpath(p)) not in seen:
                seen.add(os.path.normcase(os.path.normpath(p)))
                out.append(os.path.normpath(p))
    return out


def find_app(steam, appid):
    """The install folder of a Steam app, from its appmanifest in any library, or None."""
    for lib in libraries(steam):
        text = _read(os.path.join(lib, "steamapps", f"appmanifest_{appid}.acf"))
        if text is None:
            continue
        state = _get_ci(parse_vdf(text), "AppState") or {}
        inst = _get_ci(state, "installdir")
        flags = _get_ci(state, "StateFlags")
        # StateFlags bit 4 is "fully installed"; a first download (the owner's Fallout 4, 1042, 2026-10-22) lacks it,
        # and its half-written files must not be read as the game. An update keeps the bit, so an updating game stays.
        if flags is not None and str(flags).isdigit() and not int(flags) & 4:
            continue
        if inst:
            p = os.path.join(lib, "steamapps", "common", inst)
            if os.path.isdir(p):
                return p
    return None


def depot_downloads(steam, appid):
    """Data folders of depot downloads (steamapps/content/app_<appid>/depot_*), in depot-number order: the fixed merge
    order the owner chose (LA-4); where two depots hold the same archive, detect uses the later one and says so."""
    out = []
    for lib in libraries(steam):
        root = os.path.join(lib, "steamapps", "content", f"app_{appid}")
        if not os.path.isdir(root):
            continue
        depots = [d for d in os.listdir(root) if d.startswith("depot_") and d[6:].isdigit()]
        for d in sorted(depots, key=lambda d: int(d[6:])):
            # a depot holds the game's file tree (Data inside); one that holds only data files is taken as Data
            data = os.path.join(root, d, "Data")
            if os.path.isdir(data):
                out.append(data)
            elif any(n.lower().endswith((".esm", ".ba2")) for n in os.listdir(os.path.join(root, d))):
                out.append(os.path.join(root, d))
    return out


def locate(steam=None, gog=None):
    """{"steam", "libraries", "fallout4", "fallout4_store", "fallout4_depots", "starfield", "notes"}. Steam's Fallout 4
    comes first; a GOG install (from `gog` or the registry) is used when Steam has none."""
    steam = steam or steam_path_from_registry()
    gog = gog if gog is not None else gog_fallout4_from_registry()
    gog = gog if gog and os.path.isdir(gog) else None
    if not steam or not os.path.isdir(steam):
        return {"steam": None, "libraries": [], "fallout4": gog, "fallout4_store": "gog" if gog else None,
                "fallout4_depots": [], "starfield": None,
                "notes": ["Steam not found (pass --steam with its folder); Starfield needs Steam"]}
    fo4 = find_app(steam, FALLOUT4_APPID)
    out = {"steam": os.path.normpath(steam), "libraries": libraries(steam), "fallout4": fo4 or gog,
           "fallout4_store": "steam" if fo4 else ("gog" if gog else None),
           "fallout4_depots": depot_downloads(steam, FALLOUT4_APPID),
           "starfield": find_app(steam, STARFIELD_APPID), "notes": []}
    if not out["fallout4"] and not out["fallout4_depots"]:
        out["notes"].append("Fallout 4 not found in any Steam library or GOG")
    if not out["starfield"]:
        out["notes"].append("Starfield not found in any Steam library")
    return out


def fo4_data_folders(found):
    """The --fo4-data folders detect should read: the depot downloads, then a normal install's Data."""
    out = list(found.get("fallout4_depots") or [])
    if found.get("fallout4") and os.path.isdir(os.path.join(found["fallout4"], "Data")):
        out.append(os.path.join(found["fallout4"], "Data"))
    return out
