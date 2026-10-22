"""Read-only: answer the new-game framework's offline script questions from Starfield's own Papyrus sources.

research/framework/newgame.md (project files) lists questions that the vanilla sources settle without the game:
NG-M1 and NG-A3 (when MQ00 writes MQ101Debug), NG-M2 (what MQ101's stage 9000 "Run on Stop" does), NG-A1
(StartupQuest_DO), NG-M7 and NG-C6 (SetInChargen), NG-C5 (RegisterForMenuOpenCloseEvent), NG-L3 (OnPlayerLoadGame),
NG-B4 (GetShipRef). This reads Scripts/Source of the Creation Kit's ContentResources.zip, copies the whole MQ00 and
MQ101 quest fragments and any StartupQuest script, and lists every line that names a term, with context.

usage: python start_read.py [--zip <ContentResources.zip>] --out <report.txt>
It opens the zip read-only and writes only --out. Nothing in the game folder changes.
"""
import argparse
import os
import re
import sys
import zipfile

STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
# whole files copied into the report: the opening quests' fragments and anything named for the start-up quest
WHOLE = re.compile(r"(^|[/\\:_])(QF_MQ00_|QF_MQ101_|StartupQuest)", re.I)
TERMS = ("MQ101Debug", "SustenanceAllowed", "SetInChargen", "SetCharGenHUDMode", "PrecacheCharGen",
         "ShowRaceMenu", "RegisterForMenuOpenCloseEvent", "OnMenuOpenCloseEvent", "OnPlayerLoadGame",
         "GetShipRef", "StartupQuest")
CONTEXT = 2


def sources(z):
    """(name, text) for every .psc under Scripts/Source, sorted by name."""
    for name in sorted(n for n in z.namelist() if n.lower().endswith(".psc") and "source" in n.lower()):
        yield name, z.read(name).decode("utf-8", errors="replace")


def read(zip_path, terms=TERMS):
    """{'whole': {name: text}, 'hits': {term: [(name, line_no, context_text)]}, 'files': n}"""
    whole, hits, n = {}, {t: [] for t in terms}, 0
    with zipfile.ZipFile(zip_path) as z:
        for name, text in sources(z):
            n += 1
            if WHOLE.search(os.path.basename(name)):
                whole[name] = text
            lines = text.splitlines()
            for i, line in enumerate(lines):
                low = line.lower()
                for t in terms:
                    if t.lower() in low:
                        lo, hi = max(0, i - CONTEXT), min(len(lines), i + CONTEXT + 1)
                        hits[t].append((name, i + 1, "\n".join(lines[lo:hi])))
    return {"whole": whole, "hits": hits, "files": n}


def report(r):
    out = [f"start_read: {r['files']} source files read",
           "terms: " + ", ".join(f"{t} {len(h)}" for t, h in r["hits"].items()), ""]
    for name, text in r["whole"].items():
        out += [f"===== WHOLE {name} ({len(text.splitlines())} lines)", text.rstrip(), ""]
    for t, hs in r["hits"].items():
        out.append(f"===== TERM {t}: {len(hs)} line(s)")
        for name, no, ctx in hs:
            out += [f"--- {name}:{no}", ctx]
        out.append("")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=os.path.join(STARFIELD, "Tools", "ContentResources.zip"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not os.path.isfile(a.zip):
        sys.exit(f"{a.zip} missing")
    r = read(a.zip)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(report(r))
    print(f"start_read ok: {r['files']} files, {len(r['whole'])} copied whole ({', '.join(r['whole']) or 'none'}); "
          + ", ".join(f"{t} {len(h)}" for t, h in r["hits"].items()) + f"; report {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
