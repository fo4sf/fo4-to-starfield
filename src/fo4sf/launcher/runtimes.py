"""Known-good Starfield runtimes: which Starfield.exe builds the launcher builds and launches against, and the SFSE
files each one needs.

Owner decisions, 2026-10-19: refuse until a runtime is listed as good (LA-15); players keep Steam on "update only
when launched" (LA-16); SFSE is required (NG-1); Steam only for version 1 (RE-12). So detect refuses an unlisted
Starfield.exe, a missing SFSE, and an SFSE whose files are not the ones listed for that runtime.

The table (scripts/launcher_recipes/known_runtimes.json) maps a Starfield.exe sha256 to a label and the SFSE files
measured with it (sfse_loader.exe and every sfse_*.dll next to it, by sha256). Entries come from a real install's
build manifest (`launcher.py runtimes-add --manifest <build manifest> --label <text>`), never made up: no version
number, DLL name or hash is written here by hand.
"""
import os

from . import files

DEFAULT_TABLE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "scripts", "launcher_recipes", "known_runtimes.json")
# path parts of a Microsoft Store / Game Pass install (stores.md §6: XboxGames\Starfield\Content; WindowsApps)
STORE_PARTS = ("xboxgames", "windowsapps")


def load_runtimes(path=None):
    path = DEFAULT_TABLE if path is None else path
    if not path or not os.path.isfile(path):
        return {"schema": 1, "runtimes": []}
    return files.load_json(path)


def _sha(identity):
    return (identity or {}).get("sha256")


def add_runtime(table, man, label):
    """Add the Starfield runtime a build manifest recorded, with the SFSE files it found. Returns 1 if added, 0 if
    that executable is already listed. Refuses a manifest without a hashed Starfield.exe or without SFSE."""
    game = man.get("game") or {}
    exe = _sha((game.get("files") or {}).get("Starfield.exe"))
    if not exe:
        raise ValueError("the manifest records no hashed Starfield.exe (run `launcher.py manifest --starfield ...`)")
    loader = _sha((game.get("files") or {}).get("sfse_loader.exe"))
    dlls = {n: _sha(i) for n, i in sorted((game.get("sfse_dlls") or {}).items()) if _sha(i)}
    if not loader or not dlls:
        raise ValueError("the manifest records no SFSE loader and DLL; SFSE is required (NG-1), so a runtime is "
                         "listed only with the SFSE build that works on it")
    if any(r["exe_sha256"] == exe for r in table["runtimes"]):
        return 0
    table["runtimes"].append({"label": label, "exe_sha256": exe,
                              "exe_size": ((game.get("files") or {}).get("Starfield.exe") or {}).get("size"),
                              "sfse": {"loader_sha256": loader, "dlls": dlls}})
    return 1


def match_runtime(table, exe_sha256):
    for r in table["runtimes"]:
        if exe_sha256 and r["exe_sha256"] == exe_sha256:
            return r
    return None


def sfse_problems(runtime, game):
    """[problems] with the installed SFSE against what the listed runtime was measured with."""
    want = runtime.get("sfse") or {}
    out = []
    have_loader = _sha((game.get("files") or {}).get("sfse_loader.exe"))
    if want.get("loader_sha256") and have_loader != want["loader_sha256"]:
        out.append("sfse_loader.exe is not the SFSE build listed for this runtime"
                   if have_loader else "sfse_loader.exe missing")
    have = {n.casefold(): _sha(i) for n, i in (game.get("sfse_dlls") or {}).items()}
    for name, sha in sorted((want.get("dlls") or {}).items()):
        got = have.get(name.casefold())
        if got is None:
            out.append(f"{name} missing (the SFSE build listed for this runtime has it)")
        elif got != sha:
            out.append(f"{name} is not the SFSE build listed for this runtime")
    listed = {n.casefold() for n in (want.get("dlls") or {})}
    for name in sorted(n for n in (game.get("sfse_dlls") or {}) if n.casefold() not in listed):
        out.append(f"{name} is not part of the SFSE build listed for this runtime (another SFSE build left behind?)")
    return out


def store_install(starfield_dir):
    """True when the folder looks like a Microsoft Store / Game Pass install (by its path)."""
    parts = [p.casefold() for p in os.path.abspath(starfield_dir).replace("\\", "/").split("/")]
    return any(p in STORE_PARTS for p in parts)
