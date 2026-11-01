"""The FO4SF game folder: a separate copy of Starfield that is always FO4SF, beside the player's own Starfield and its mod
packs (owner, 2026-11-01: "stay FO4SF all the time make a separate area then actual starfield so people can keep their
own mod packs for that"). Design and the steps after this one: docs/ai/fo4sf-instance.md.

This module plans and makes the folder; it never writes in the player's install.
* Every file of the install is hard-linked into the new folder, so it costs no disk (a hard link is the same file under a
  second name). That needs the same drive: on another drive it refuses, since a copy would cost the whole game.
* INI files in the game folder (Starfield.ini, the Low to Ultra presets, ...) are copied instead, so the FO4SF folder's
  settings can change without changing the player's (an edit through a hard link would change both).
* Data keeps only the game's own files: the plugins the game loads by itself (fo4sf.core.loadset.built_in) and the files
  named after them ("Starfield - Textures01.ba2", "SFBGS003 - Main.ba2", ...). Everything else in Data (the player's
  mods, our own installs, loose folders, SFSE plugins) is left out and listed, unless a Data folder is kept by name.
* The record FO4SF-instance.json in the new folder lists what was made; a run that stopped goes on from there, and a
  file that is already there and is not the one it would make is refused, never overwritten.
Read-only `plan` says all of it first: what is linked, copied and left out, and the disk it costs.
"""
import os
import shutil

from . import files
from fo4sf.core.loadset import built_in, is_plugin

RECORD = "FO4SF-instance.json"
SCHEMA = 1
GAME_EXE = "Starfield.exe"
COPY_EXT = (".ini",)                         # changed per folder: copied, never linked
# where a game folder should not be made (a Steam library, Program Files, a synced folder: the same advice the Starfield
# Launchpad Wabbajack instance gives, nexusmods.com/starfield/mods/18644)
BAD_PARTS = ("steamapps", "program files", "program files (x86)", "onedrive")


class InstanceRefused(ValueError):
    pass


def _parts(path):
    return [p.casefold() for p in os.path.normpath(os.path.abspath(path)).split(os.sep) if p]


def _inside(child, parent):
    c, p = os.path.normcase(os.path.realpath(child)), os.path.normcase(os.path.realpath(parent))
    try:
        return os.path.commonpath((c, p)) == p
    except ValueError:                        # another drive
        return False


def game_file(rel_in_data):
    """True for a file directly in Data that belongs to the game: a plugin it loads by itself, or a file named after one
    ("<stem> - anything", "<stem>.<ext>")."""
    name = rel_in_data.casefold()
    if is_plugin(name):
        return built_in(name)
    stem = name.split(" - ", 1)[0] if " - " in name else os.path.splitext(name)[0]
    return any(built_in(stem + ext) for ext in (".esm", ".esp", ".esl"))


def plan(source, target, keep_data_dirs=()):
    """{"link": [rel], "copy": [rel], "left_out": [rel], "link_bytes", "copy_bytes"} for making target from source
    (rel: "/" separators, relative to the game folder). Read only."""
    source = os.path.abspath(source)
    if not os.path.isfile(os.path.join(source, GAME_EXE)):
        raise InstanceRefused(f"{source} is not a Starfield game folder (no {GAME_EXE})")
    keep = {k.casefold().strip("/\\") for k in keep_data_dirs}
    out = {"link": [], "copy": [], "left_out": [], "link_bytes": 0, "copy_bytes": 0}
    for d, dirs, names in os.walk(source):
        dirs.sort()
        rel_d = os.path.relpath(d, source).replace(os.sep, "/")
        rel_d = "" if rel_d == "." else rel_d
        parts = rel_d.split("/") if rel_d else []
        if len(parts) == 1 and parts[0].casefold() == "data":
            for sub in list(dirs):                           # Data's folders: left out unless kept by name
                if sub.casefold() not in keep:
                    out["left_out"].append(f"{rel_d}/{sub}/")
                    dirs.remove(sub)
        for n in sorted(names):
            rel = f"{rel_d}/{n}" if rel_d else n
            size = os.path.getsize(os.path.join(d, n))
            if len(parts) == 1 and parts[0].casefold() == "data" and not game_file(n):
                out["left_out"].append(rel)
            elif not parts and n.casefold().endswith(COPY_EXT):
                out["copy"].append(rel)
                out["copy_bytes"] += size
            else:
                out["link"].append(rel)
                out["link_bytes"] += size
    return out


def _device(path):
    return os.stat(path).st_dev


def check_target(source, target, min_free_gb, copy_bytes, disk_usage=shutil.disk_usage):
    """Problems with making target (refused before anything is written)."""
    target = os.path.abspath(target)
    if _inside(target, source) or _inside(source, target):
        raise InstanceRefused("the FO4SF folder must be outside the Starfield install (and not hold it)")
    bad = [p for p in _parts(target) if p in BAD_PARTS]
    if bad:
        raise InstanceRefused(f"{target} is inside {bad[0]!r}: put the FO4SF folder elsewhere, for example D:\\FO4SF\\"
                              "Starfield (Steam, Program Files and synced folders can move or lock its files)")
    if os.path.exists(target) and not os.path.isdir(target):
        raise InstanceRefused(f"{target} is a file")
    if os.path.isdir(target) and os.listdir(target) and not os.path.isfile(os.path.join(target, RECORD)):
        raise InstanceRefused(f"{target} is not empty and is no FO4SF game folder (no {RECORD}): pick an empty one")
    parent = target
    while not os.path.isdir(parent):
        parent = os.path.dirname(parent)
    if _device(parent) != _device(source):
        raise InstanceRefused(f"{target} is on another drive than {source}: hard links need the same drive (a copy "
                              "would cost the whole game)")
    free = disk_usage(parent).free - copy_bytes
    if free < min_free_gb * 1024 ** 3:
        raise InstanceRefused(f"{free / 1024 ** 3:.1f} GB would be left free, under {min_free_gb:g} GB")


def create(source, target, keep_data_dirs=(), min_free_gb=40.0, say=print, disk_usage=shutil.disk_usage, link=os.link):
    """Make (or finish) the FO4SF game folder; returns the plan. Never writes in source, never overwrites a file."""
    source, target = os.path.abspath(source), os.path.abspath(target)
    p = plan(source, target, keep_data_dirs)
    rec_p = os.path.join(target, RECORD)
    rec = files.load_json(rec_p) if os.path.isfile(rec_p) else None
    if rec is not None and os.path.normcase(os.path.abspath(rec.get("source", ""))) != os.path.normcase(source):
        raise InstanceRefused(f"{target} was made from {rec.get('source')}, not {source}")
    check_target(source, target, min_free_gb, p["copy_bytes"], disk_usage)
    os.makedirs(target, exist_ok=True)
    rec = rec or {"schema": SCHEMA, "source": source, "made": [], "complete": False}
    rec.update({"left_out": p["left_out"], "keep_data_dirs": sorted(keep_data_dirs), "complete": False})
    made = set(rec["made"])
    files.save_json(rec_p, rec)
    todo = [(r, "link") for r in p["link"]] + [(r, "copy") for r in p["copy"]]
    for k, (rel, how) in enumerate(todo):
        src = os.path.join(source, *rel.split("/"))
        dst = os.path.join(target, *rel.split("/"))
        if os.path.lexists(dst):
            same = os.path.samefile(src, dst) if how == "link" else (
                rel in made and os.path.getsize(dst) == os.path.getsize(src))
            if not same:
                raise InstanceRefused(f"{dst} is already there and is not the game's file; nothing overwritten")
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if how == "link":
            link(src, dst)
        else:
            shutil.copy2(src, dst)
        rec["made"].append(rel)
        if k % 200 == 199:
            files.save_json(rec_p, rec)              # a stop loses at most these: the rerun finds them by samefile
    rec["complete"] = True
    files.save_json(rec_p, rec)
    say(f"FO4SF game folder ready: {target} ({len(p['link'])} files linked, {len(p['copy'])} copied, "
        f"{len(p['left_out'])} left out)")
    return p


def summary(p):
    """Lines that say what a plan would do."""
    gb = 1024 ** 3
    lines = [f"linked (no extra disk): {len(p['link'])} files, {p['link_bytes'] / gb:.1f} GB",
             f"copied: {len(p['copy'])} files, {p['copy_bytes'] / 1024:.0f} KB ({', '.join(p['copy']) or 'none'})",
             f"left out of Data (not the game's own): {len(p['left_out'])}"]
    lines += [f"    {r}" for r in p["left_out"][:40]]
    if len(p["left_out"]) > 40:
        lines.append(f"    ... and {len(p['left_out']) - 40} more")
    return lines
