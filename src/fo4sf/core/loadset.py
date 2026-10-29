"""What Starfield will load on this PC, read without changing anything (docs/testing/baseline.md): the built-in
plugins in Data, the loader files that override Plugins.txt, plugins in My Games\\Starfield\\Data that can stand in
for installed ones, and the plugins that will load and override Starfield's start. The deployment gate's loaders and
start checks (fo4sf.core.preflight) take these readings through a probe: LoadProbe is that probe for one game folder
(scripts/game/baseline.py, which also records the built-in plugins), and the test runner's PreflightProbe hands its
readings to one.

Loader rules (verified: docs/research/framework/launcher-sources/sfstack.md, from Ortham's "Load order in Starfield"
(2024) and the libloot changelog):
* Starfield.ccc is read from My Games\\Starfield first, then the install folder; the plugins it lists load first.
* Any sTestFile1..10 in Starfield's INIs makes the game ignore Plugins.txt and Starfield.ccc.
* A plugin in My Games\\Starfield\\Data is loaded only if a same-named plugin is in the install's Data, so a copy
  there can stand in for the installed one (supported hypothesis: what the rule implies).
* The official plugins (Starfield, Constellation, OldMars, ShatteredSpace, SFBGS003 to 008, SFBGS00D, 047 and 050)
  load on their own, and BlueprintShips-X.esm with X; the game takes them out of Plugins.txt.
Built in here: those names, any SFBGS* plugin (scripts/game/exp_install.py implicit) and any BlueprintShips-* plugin.

The start records, all in Starfield.esm (verified): StartupQuest_DO 00562D, the DefaultObject (DFOB) that names MQ101
as the startup quest (the NG-N4 records report, docs/research/framework/newgame.md); MQ101 003448, the opening (its
fragment file qf_mq101_00003448.psc, and the 28 Oct run 3 log); MQ101Debug 0A7D31, the GLOB its stage 0 reads (UESP,
and 28 Oct: our override to 10 started Starfield's pirate fight). A plugin overrides one when a record of that type
has a form id whose top byte indexes Starfield.esm in its master list and whose low 24 bits are the record's (verified
on SFBGS00D.esm, a full plugin, and SFBGS003.esm and SFBGS004.esm, medium and small: their own records carry FD and FE
in the file, their overrides of Starfield.esm records 00).
"""
import hashlib
import os
import struct

STARFIELD = "starfield.esm"
START_RECORDS = ((b"DFOB", 0x00562D, "StartupQuest_DO"), (b"QUST", 0x003448, "MQ101"), (b"GLOB", 0x0A7D31, "MQ101Debug"))
IMPLICIT = ("starfield.esm", "blueprintships-starfield.esm", "constellation.esm", "oldmars.esm", "shatteredspace.esm")
OUR_PREFIXES = ("fo4terrain", "fo4actor", "fo4sf", "fo4port")      # scripts/game/load_order.py, the same tuple
PLUGIN_EXTENSIONS = (".esm", ".esp", ".esl")
MY_GAMES = ("OneDrive", "Documents"), ("Documents",)                 # under the home folder, OneDrive first


def is_plugin(name):
    return name.casefold().endswith(PLUGIN_EXTENSIONS)


def built_in(name):
    """True for a plugin the game ships and loads on its own (module doc)."""
    low = name.casefold()
    return is_plugin(low) and (low in IMPLICIT or low.startswith(("sfbgs", "blueprintships-")))


def ours(name):
    low = name.casefold()
    return is_plugin(low) and low.startswith(OUR_PREFIXES)


def my_games_dirs(explicit=None, home=None):
    """The My Games\\Starfield folders to read: the one given, else those of the two usual places that exist
    (Documents in OneDrive, then plain Documents: the test runner's rule, testqueue.py PreflightProbe)."""
    if explicit:
        return [explicit] if os.path.isdir(explicit) else []
    home = home or os.path.expanduser("~")
    return [p for p in (os.path.join(home, *base, "My Games", "Starfield") for base in MY_GAMES) if os.path.isdir(p)]


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


def name_of(line):
    return line.strip().lstrip("*").strip()


def active_plugins(lines):
    """The plugins on active lines, in file order."""
    return [name_of(ln) for ln in lines if ln.strip().startswith("*") and name_of(ln)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


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
    first), then the install folder's."""
    out = []
    for folder in list(my_games) + [game_dir]:
        p = os.path.join(folder, "Starfield.ccc")
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                out.append((p, [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]))
    return out


def test_files(game_dir, my_games):
    """[(ini path, line number, key, value)] for every non-empty sTestFileN in the INIs of the game folder and the My
    Games folders (the launcher's own reader, fo4sf.launcher.detect)."""
    from fo4sf.launcher.detect import ini_test_files
    return ini_test_files([game_dir] + list(my_games))


def shadow_plugins(data, my_games):
    """[(path, name)] of the plugins in My Games\\Starfield\\Data whose name is also a plugin in the install's Data."""
    if not os.path.isdir(data):
        return []
    installed = {n.casefold() for n in os.listdir(data) if is_plugin(n)}
    out = []
    for folder in my_games:
        d = os.path.join(folder, "Data")
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d), key=str.casefold):
            if is_plugin(n) and n.casefold() in installed and os.path.isfile(os.path.join(d, n)):
                out.append((os.path.join(d, n), n))
    return out


def start_overrides(plugins):
    """(hits, unreadable) for the plugins given as [(name, path)]: hits [(name, record, "00562D")] for every start
    record (START_RECORDS) one overrides, unreadable [(name, why)]. A plugin whose file is not there is skipped: the
    game cannot load it either."""
    from fo4sf.planet import esm
    hits, bad = [], []
    for name, path in plugins:
        if not os.path.isfile(path):
            continue
        try:
            with esm.Plugin(path) as pl:
                masters = [m.casefold() for m in pl.masters]
                for sig, obj, what in START_RECORDS:
                    for start, end in pl.groups.get(sig.decode("ascii"), []):
                        for item in pl.walk(start, end, groups=frozenset()):
                            if item[0] != "REC" or item[2] != sig:
                                continue
                            fid = struct.unpack_from("<I", pl.buf, item[1] + 12)[0]
                            top = fid >> 24
                            if top < len(masters) and masters[top] == STARFIELD and fid & 0xFFFFFF == obj:
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
    read where they are staged (an experiment, the port's staging), queue the queue the checks read their pins from.
    Read only."""

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
