"""paths: the file locations the launcher needs, found on the PC and checked, so the player confirms them instead of
typing them (owner, 2026-10-22: "detect anything it needs file location wise and ask the user if it's right").
Read only: finding and checking never writes; the window saves what the player confirms through `settings --set`.
"""
import os
import shutil

from . import locate

# (setting, label, kind, what it is). kind: dir, file, dirs (several folders, one per line in the window, ";" saved)
LOCATIONS = (
    ("starfield", "Starfield game folder", "dir", "the folder that holds Starfield.exe"),
    ("fo4_data", "Fallout 4 Data folders", "dirs", "the Data folder(s) that hold Fallout4.esm and its DLC"),
    ("my_games", "My Games folder", "dir", "Documents\\My Games\\Starfield (StarfieldCustom.ini lives here)"),
    ("crash_watch.procdump", "ProcDump", "file", "procdump64.exe from Microsoft Sysinternals"),
    ("crash_watch.folder", "Dump folder", "dir", "where crash dumps and crashwatch.log go (made on first use)"),
)
KEYS = tuple(k for k, *_ in LOCATIONS)
PROCDUMP_NAMES = ("procdump64.exe", "procdump.exe")


def split_dirs(value):
    return [p.strip() for p in str(value or "").replace("\n", ";").split(";") if p.strip()]


def join_dirs(folders):
    return ";".join(split_dirs(";".join(folders)))


def check(key, value):
    """"" when value is usable for key, else what is wrong with it."""
    if not value:
        return "not set"
    if key == "starfield":
        if not os.path.isdir(value):
            return "folder not found"
        return "" if os.path.isfile(os.path.join(value, "Starfield.exe")) else "no Starfield.exe in this folder"
    if key == "fo4_data":
        folders = split_dirs(value)
        missing = [f for f in folders if not os.path.isdir(f)]
        if missing:
            return "folder not found: " + missing[0]
        if not any(os.path.isfile(os.path.join(f, "Fallout4.esm")) for f in folders):
            return "no Fallout4.esm in these folders"
        return ""
    if key == "my_games":
        return "" if os.path.isdir(value) else "folder not found"
    if key == "crash_watch.procdump":
        if not os.path.isfile(value):
            return "file not found"
        return "" if os.path.basename(value).lower() in PROCDUMP_NAMES else "not procdump64.exe"
    if key == "crash_watch.folder":
        # play makes the missing folders (os.makedirs), so any path under an existing folder will do (Codex, #481)
        p = os.path.abspath(value)
        while not os.path.exists(p):
            up = os.path.dirname(p)
            if up == p:
                return "no part of this path exists"
            p = up
        return "" if os.path.isdir(p) else f"{p} is a file, not a folder"
    raise KeyError(key)


def _first(candidates, key):
    for c in candidates:
        if c and not check(key, c):
            return os.path.normpath(c)
    return ""


def _documents(env):
    home = env.get("USERPROFILE") or os.path.expanduser("~")
    out = []
    if os.name == "nt":
        try:                                           # the real Documents folder, even when OneDrive moved it
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:   # CSIDL_PERSONAL
                out.append(buf.value)
        except (OSError, AttributeError):
            pass
    out += [os.path.join(home, "Documents"), os.path.join(home, "OneDrive", "Documents")]
    if env.get("OneDrive"):
        out.append(os.path.join(env["OneDrive"], "Documents"))
    return out


def detect(*, env=None, find=None, which=None):
    """{setting: (found path or "", how it was found)} for every location; nothing is written."""
    env = os.environ if env is None else env
    find = find or locate.locate
    which = which or shutil.which
    try:
        games = find()
    except (OSError, ValueError):
        games = {}
    out = {}
    sf = games.get("starfield") or ""
    out["starfield"] = (sf, "Steam library") if sf and not check("starfield", sf) else ("", "")
    data = join_dirs(locate.fo4_data_folders(games)) if games else ""
    out["fo4_data"] = (data, "Steam or GOG install") if data and not check("fo4_data", data) else ("", "")
    mg = _first([os.path.join(d, "My Games", "Starfield") for d in _documents(env)], "my_games")
    out["my_games"] = (mg, "Documents") if mg else ("", "")
    on_path = [which(n) for n in ("procdump64", "procdump64.exe")]
    folders = [env.get("ProgramFiles", ""), env.get("ProgramFiles(x86)", "")]
    beside = [os.path.join(f, sub, PROCDUMP_NAMES[0]) for f in folders if f
              for sub in ("Sysinternals", "SysinternalsSuite", "ProcDump", "Procdump")]
    store = [os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", PROCDUMP_NAMES[0])]
    pd = _first(on_path, "crash_watch.procdump")
    how = "PATH"
    if not pd:
        pd, how = _first(beside + store, "crash_watch.procdump"), "Program Files"
    out["crash_watch.procdump"] = (pd, how) if pd else ("", "")
    base = env.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    out["crash_watch.folder"] = (os.path.join(base, "FO4SF", "crashdumps"), "suggested")
    return out


def rows(saved, found, prefer=()):
    """One row per location for the window: the value to show and whether the player still has to confirm it.
    status: "saved" (a usable saved value), "found" (detected, waiting for the player), "missing" or "problem".
    prefer: keys whose found value was given on purpose (the command line): offered even over a good saved value."""
    out = []
    for key, label, kind, what in LOCATIONS:
        value, problem = saved.get(key) or "", check(key, saved.get(key) or "")
        det = found.get(key, ("", ""))[0]
        if key in prefer and det and det != value:      # an explicit argument beats the saved path (Codex, #481)
            problem = "given on the command line"
        if value and not problem:
            out.append({"key": key, "label": label, "kind": kind, "what": what, "value": value, "status": "saved",
                        "note": "saved"})
            continue
        det, how = found.get(key, ("", ""))
        if det:
            out.append({"key": key, "label": label, "kind": kind, "what": what, "value": det, "status": "found",
                        "note": f"found ({how}): is this right?"})
        elif value:
            out.append({"key": key, "label": label, "kind": kind, "what": what, "value": value, "status": "problem",
                        "note": problem})
        else:
            out.append({"key": key, "label": label, "kind": kind, "what": what, "value": "", "status": "missing",
                        "note": "not found: choose it"})
    return out


def needed(values):
    """Locations play needs with these settings."""
    out = ["starfield"]
    if values.get("crash_watch.enabled"):
        out += ["crash_watch.procdump", "crash_watch.folder"]
    if values.get("papyrus_logging", "unchanged") != "unchanged":
        out.append("my_games")
    return out
