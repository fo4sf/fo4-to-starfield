"""Support bundle: one local zip a player attaches to a GitHub issue (framework A11; owner's answer RE-18, GitHub only).
Nothing is sent anywhere; the player looks inside and uploads it themselves (Nolvus's "safe to upload" log is the
model, ops.md §5).

What goes in, each only if present (and, in BUNDLE.txt, which launcher code made it: branch, commit, local changes):
    driver state      <state_dir>/state.json and the newest log of every step (logs/<step>.<n>.log)
    build manifest    and a detect report, when given
    install records   every record restore.COMPONENTS knows (FO4Port.deploy.json, FO4SFExp.install.json, the probes',
                      FO4SFMapMarkers.install.json, FO4SFBridge.install.json) from Starfield's Data
    load order        Plugins.txt
    INIs              Starfield.ini, StarfieldPrefs.ini, StarfieldCustom.ini from the game folder and My Games
    extra files       any --file given

Text is cleaned before it is written: the home folder becomes %USERPROFILE% and the user name becomes <user>
(Windows and POSIX spellings, any case, forward or back slashes). A file over the size cap keeps only its last part,
and the cut is said in the file. BUNDLE.txt lists every file, what was cut and what was not found. No game data,
plugins or archives go in: only the text files named above.
"""
import os
import re
import zipfile

from . import restore

CAP = 2 << 20                         # bytes kept per file (the tail of a longer log)
RECORDS = tuple(v[0] for v in restore.COMPONENTS.values())
INIS = ("Starfield.ini", "StarfieldPrefs.ini", "StarfieldCustom.ini")


def _user_patterns(home, user):
    pats = []
    if home:
        # separators as either slash, and doubled as JSON writes them
        h = r"[\\/]+".join(re.escape(p) for p in re.split(r"[\\/]+", home.rstrip("\\/")))
        pats.append((re.compile(h, re.IGNORECASE), "%USERPROFILE%"))
    if user and len(user) >= 3:                     # a two-letter name would hit ordinary words
        pats.append((re.compile(r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])", re.IGNORECASE), "<user>"))
    return pats


def clean(text, home=None, user=None):
    """The text with the home folder and user name taken out."""
    home = os.path.expanduser("~") if home is None else home
    user = (os.environ.get("USERNAME") or os.environ.get("USER") or os.path.basename(home)) if user is None else user
    for pat, rep in _user_patterns(home, user):
        text = pat.sub(rep, text)
    return text


def _newest_logs(state_dir):
    logs = os.path.join(state_dir, "logs")
    newest = {}
    if os.path.isdir(logs):
        for n in os.listdir(logs):
            m = re.match(r"^(.+)\.(\d+)\.log$", n)
            if m and (m.group(1) not in newest or int(m.group(2)) > newest[m.group(1)][0]):
                newest[m.group(1)] = (int(m.group(2)), n)
    return [os.path.join(logs, n) for _, n in sorted(newest.values(), key=lambda v: v[1])]


def collect(*, state_dirs=(), manifest=None, detect_report=None, starfield=None, plugins_txt=None, my_games=None,
            extra=()):
    """[(name in the zip, path on disk)] in a fixed order, and the names looked for and not found."""
    want, missing = [], []

    def add(arc, path):
        if path and os.path.isfile(path):
            want.append((arc, path))
        elif path:
            missing.append(arc)
    for i, sd in enumerate(state_dirs):
        base = f"driver{i + 1}" if len(state_dirs) > 1 else "driver"
        add(f"{base}/state.json", os.path.join(sd, "state.json"))
        for p in _newest_logs(sd):
            add(f"{base}/logs/{os.path.basename(p)}", p)
    add("build-manifest.json", manifest)
    add("detect-report.json", detect_report)
    if starfield:
        for r in RECORDS:
            add(f"starfield/Data/{r}", os.path.join(starfield, "Data", r))
        for n in INIS:
            p = os.path.join(starfield, n)
            if os.path.isfile(p):
                add(f"starfield/{n}", p)
    add("Plugins.txt", plugins_txt)
    if my_games:
        for n in INIS:
            add(f"my-games/{n}", os.path.join(my_games, n))
    for p in extra:
        add(f"extra/{os.path.basename(p)}", p)
    return want, missing


def write(out_zip, items, missing, *, home=None, user=None, cap=CAP, about=()):
    """Write the zip; returns the BUNDLE.txt lines. about: lines on the version it came from (cleaned like the files).
    Refuses to overwrite an existing file."""
    if os.path.exists(out_zip):
        raise FileExistsError(f"{out_zip} exists; pick a new name")
    lines = ["FO4SF support bundle. Made on this PC; nothing was sent. Look inside before you attach it to an issue.",
             "The home folder is written as %USERPROFILE% and the user name as <user>.",
             *(clean(a, home, user) for a in about), "", "files:"]
    tmp = out_zip + ".partial"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, path in items:
            with open(path, "rb") as f:
                raw = f.read()
            note, size = "", len(raw)
            if size > cap:
                note = f" (last {cap:,} of {size:,} bytes)"
                raw = raw[-cap:]
            text = clean(raw.decode("utf-8-sig", errors="replace"), home, user)
            if note:
                text = f"[... cut: only the last {cap:,} of {size:,} bytes are kept ...]\n" + text
            z.writestr(arc, text)
            lines.append(f"  {arc}{note}")
        if missing:
            lines += ["", "looked for, not found:"] + [f"  {m}" for m in missing]
        z.writestr("BUNDLE.txt", "\n".join(lines) + "\n")
    os.replace(tmp, out_zip)
    return lines


def make(out_zip, **kw):
    home, user, about = kw.pop("home", None), kw.pop("user", None), kw.pop("about", ())
    items, missing = collect(**kw)
    return write(out_zip, items, missing, home=home, user=user, about=about)


def manifest_of(zip_path):
    """{name: text} of a bundle, for tests and for a player who wants to read it here."""
    with zipfile.ZipFile(zip_path) as z:
        return {n: z.read(n).decode("utf-8") for n in z.namelist()}

