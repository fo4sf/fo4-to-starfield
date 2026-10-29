"""What Starfield will load on this PC, read without changing anything (docs/testing/baseline.md): the built-in
plugins in Data, the loader files that override Plugins.txt, plugins in My Games\\Starfield\\Data that can stand in
for installed ones, and the plugins that will load and override Starfield's start. The rules are fo4sf.core.loadset's;
this module only reads.

The deployment gate's loaders and start checks (fo4sf.core.preflight) take these readings through a probe: LoadProbe
is that probe for one game folder (scripts/game/baseline.py, which also records the built-in plugins), and the test
runner's PreflightProbe (scripts/game/testqueue.py) hands its readings to one.
"""
import os
import struct

from fo4sf.core.loadset import START_RECORDS, active_plugins, built_in, is_plugin, start_record

from .detect import ini_test_files
from .files import sha256

MY_GAMES = ("OneDrive", "Documents"), ("Documents",)                 # under the home folder, OneDrive first


def distinct_folders(paths):
    """paths without a folder named twice: one a link or junction to another (Documents linked to OneDrive's) is read
    once, as the first one found."""
    out, seen = [], set()
    for p in paths:
        key = os.path.normcase(os.path.realpath(p))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def my_games_dirs(explicit=None, home=None):
    """The My Games\\Starfield folders to read, absolute: the one given, else those of the two usual places that exist
    (Documents in OneDrive, then plain Documents: the test runner's rule, testqueue.py PreflightProbe), each once."""
    if explicit:
        return [os.path.abspath(explicit)] if os.path.isdir(explicit) else []
    home = home or os.path.expanduser("~")
    return distinct_folders(p for p in (os.path.join(home, *base, "My Games", "Starfield") for base in MY_GAMES)
                            if os.path.isdir(p))


def plugins_txt_path(env=None):
    """%LOCALAPPDATA%\\Starfield\\Plugins.txt, None where LOCALAPPDATA is not an absolute folder (not Windows)."""
    local = (os.environ if env is None else env).get("LOCALAPPDATA", "")
    return os.path.join(local, "Starfield", "Plugins.txt") if local and os.path.isabs(local) else None


def read_lines(path):
    """The lines of a Plugins.txt (its BOM dropped), [] when it does not exist."""
    if not os.path.exists(path):
        return []
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8").splitlines()


def builtin_plugins(data, digest=False):
    """{file name: {"size": bytes, "sha256": hex (with digest)}} of the built-in plugins in the game's Data folder;
    None when the folder is not there."""
    if not os.path.isdir(data):
        return None
    out = {}
    for name in sorted(os.listdir(data), key=str.casefold):
        p = os.path.join(data, name)
        if built_in(name) and os.path.isfile(p):
            row = {"size": os.path.getsize(p)}
            if digest:
                row["sha256"] = sha256(p)
            out[name] = row
    return out


def ccc_files(game_dir, my_games):
    """[(path, [listed plugins])] for every Starfield.ccc there is, the My Games ones first (the game reads them
    first), then the install folder's. A byte-order mark is not part of the first name."""
    out = []
    for folder in list(my_games) + [game_dir]:
        p = os.path.join(folder, "Starfield.ccc")
        if os.path.isfile(p):
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                out.append((p, [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]))
    return out


def test_files(game_dir, my_games):
    """[(ini path, line number, key, value)] for every non-empty sTestFileN in the INIs of the game folder and the My
    Games folders (the launcher's own reader, fo4sf.launcher.detect)."""
    return ini_test_files([game_dir] + list(my_games))


def same_folder(a, b):
    """True when the two folders are one (a junction or a link: Vortex can link My Games\\Starfield\\Data to the game's
    Data, sfstack.md)."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def shadow_plugins(data, my_games):
    """[(path, name)] of the plugins in My Games\\Starfield\\Data whose name is also a plugin in the install's Data. A
    My Games Data folder that is the game's Data itself holds no copies."""
    if not os.path.isdir(data):
        return []
    installed = {n.casefold() for n in os.listdir(data) if is_plugin(n)}
    out = []
    for folder in my_games:
        d = os.path.join(folder, "Data")
        if not os.path.isdir(d) or same_folder(d, data):
            continue
        for n in sorted(os.listdir(d), key=str.casefold):
            if is_plugin(n) and n.casefold() in installed and os.path.isfile(os.path.join(d, n)):
                out.append((os.path.join(d, n), n))
    return out


def start_overrides(plugins):
    """(hits, unreadable) for the plugins given as [(name, path)]: hits [(name, record, "00562D")] for every start
    record (START_RECORDS) one overrides (fo4sf.core.loadset.start_record), unreadable [(name, why)]. A plugin whose
    file is not there is skipped: the game cannot load it either."""
    from fo4sf.planet import esm
    hits, bad = [], []
    for name, path in plugins:
        if not os.path.isfile(path):
            continue
        try:
            with esm.Plugin(path) as pl:
                for sig, obj, what in START_RECORDS:
                    for start, end in pl.groups.get(sig.decode("ascii"), []):
                        for item in pl.walk(start, end, groups=frozenset()):
                            if item[0] != "REC" or item[2] != sig:
                                continue
                            fid = struct.unpack_from("<I", pl.buf, item[1] + 12)[0]
                            if start_record(sig, fid, pl.masters) == (what, obj):
                                hits.append((name, what, f"{obj:06X}"))
        except (esm.EsmError, OSError, struct.error) as e:
            bad.append((name, str(e)))
    return hits, bad


def papyrus_ini_texts(game_dir, my_games):
    """The texts of the INIs that set the [Papyrus] keys, lowest precedence first: the game folder's Starfield.ini,
    then StarfieldCustom.ini in My Games (the test runner's rule, testqueue.py PreflightProbe.ini_texts)."""
    out = []
    for p in [os.path.join(game_dir, "Starfield.ini")] + [os.path.join(d, "StarfieldCustom.ini") for d in my_games]:
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                out.append(f.read())
    return out


class LoadProbe:
    """The readings of the loaders and start checks for one game folder (fo4sf.core.preflight's probe interface,
    those methods), and the built-in plugins: starfield the game folder, my_games the My Games\\Starfield folders,
    plugins_txt the Plugins.txt path (None: not locatable), extra [(name, path)] the plugins installed at the launch,
    read where they are staged (an experiment, the port's staging, the bridge), queue the queue the checks read their
    pins from. Read only."""

    def __init__(self, starfield, my_games=(), plugins_txt=None, extra=(), queue=None):
        self.starfield = starfield
        self.data = os.path.join(starfield, "Data")
        self.my_games = list(my_games)
        self.plugins_txt = plugins_txt
        self.extra = list(extra)
        self.queue = dict(queue or {})
        self.state = {}

    def plugins_txt_lines(self):
        return None if not self.plugins_txt else read_lines(self.plugins_txt)

    def builtin_plugins(self, digest=False):
        return builtin_plugins(self.data, digest)

    def my_games_known(self):
        return bool(self.my_games)

    def ccc_files(self):
        return ccc_files(self.starfield, self.my_games)

    def ini_test_files(self):
        return test_files(self.starfield, self.my_games)

    def shadow_plugins(self):
        return shadow_plugins(self.data, self.my_games)

    def loading(self):
        """[(name, path)] of the plugins that will load and that the game does not ship, None when Plugins.txt cannot
        be located: those a Starfield.ccc lists, the active ones in Plugins.txt, then the ones installed at the launch
        (their staged file replaces the one in Data, so it is the one read)."""
        lines = self.plugins_txt_lines()
        if lines is None:
            return None
        names = [n for _, listed in self.ccc_files() for n in listed] + active_plugins(lines)
        out = {}
        for n in names:
            if is_plugin(n) and not built_in(n):
                out.setdefault(n.casefold(), (n, os.path.join(self.data, n)))
        for n, p in self.extra:
            out[n.casefold()] = (n, p)
        return list(out.values())

    def start_overrides(self):
        plugins = self.loading()
        return None if plugins is None else start_overrides(plugins)

    def ini_texts(self):
        return papyrus_ini_texts(self.starfield, self.my_games)
