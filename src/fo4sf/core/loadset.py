"""Which plugins Starfield ships and loads on its own, which plugins and names are ours, and Starfield's start
records: the rules the deployment gate's loaders and start checks apply (fo4sf.core.preflight; docs/testing/
baseline.md). Pure: it reads nothing. fo4sf.launcher.loadprobe reads the PC for these rules.

Loader rules (verified: docs/research/framework/launcher-sources/sfstack.md, from Ortham's "Load order in Starfield"
(2024) and the libloot changelog):
* Starfield.ccc is read from My Games\\Starfield first, then the install folder; the plugins it lists load first.
* Any sTestFile1..10 in Starfield's INIs makes the game ignore Plugins.txt and Starfield.ccc.
* A plugin in My Games\\Starfield\\Data is loaded only if a same-named plugin is in the install's Data, so a copy
  there can stand in for the installed one (supported hypothesis: what the rule implies).
* The official plugins (Starfield, Constellation, OldMars, ShatteredSpace, SFBGS003 to 008, SFBGS00D, 047 and 050)
  load on their own, and BlueprintShips-X.esm with X; the game takes them out of Plugins.txt.
Built in here: those names, any SFBGS* plugin (scripts/game/exp_install.py implicit) and any BlueprintShips-* plugin.

Ours: every plugin, EditorID and script name of this project starts with FO4 or FOCC (FO4Port, FO4SF*, FO4Terrain*,
FO4Actor*, FO4Slice*, the FOCC sidecar), and none of the game's plugins does (built_in). That none of its EditorIDs or
script names does is a hypothesis, which the first baseline tests: scripts/game/baseline.py collect keeps no log that
names one as the baseline. fo4sf.core.papyrus_log reads names in a log by the same prefixes.

The start records, all in Starfield.esm (verified): StartupQuest_DO 00562D, the DefaultObject (DFOB) that names MQ101
as the startup quest (the NG-N4 records report, docs/research/framework/newgame.md); MQ101 003448, the opening (its
fragment file qf_mq101_00003448.psc, and the 28 Oct run 3 log); MQ101Debug 0A7D31, the GLOB its stage 0 reads (UESP,
and 28 Oct: our override to 10 started Starfield's pirate fight). A plugin overrides one when a record of that type
has a form id whose top byte indexes Starfield.esm in its master list and whose low 24 bits are the record's (verified
on SFBGS00D.esm, a full plugin, and SFBGS003.esm and SFBGS004.esm, medium and small: their own records carry FD and FE
in the file, their overrides of Starfield.esm records 00).
"""

STARFIELD = "starfield.esm"
START_RECORDS = ((b"DFOB", 0x00562D, "StartupQuest_DO"), (b"QUST", 0x003448, "MQ101"), (b"GLOB", 0x0A7D31, "MQ101Debug"))
IMPLICIT = ("starfield.esm", "blueprintships-starfield.esm", "constellation.esm", "oldmars.esm", "shatteredspace.esm")
OUR_PREFIXES = ("fo4", "focc")
PLUGIN_EXTENSIONS = (".esm", ".esp", ".esl")


def is_plugin(name):
    return name.casefold().endswith(PLUGIN_EXTENSIONS)


def built_in(name):
    """True for a plugin the game ships and loads on its own (module doc)."""
    low = name.casefold()
    return is_plugin(low) and (low in IMPLICIT or low.startswith(("sfbgs", "blueprintships-")))


def ours(name):
    """True for a plugin of ours (OUR_PREFIXES)."""
    low = name.casefold()
    return is_plugin(low) and low.startswith(OUR_PREFIXES)


def name_of(line):
    return line.strip().lstrip("*").strip()


def active_plugins(lines):
    """The plugins on active lines of Plugins.txt, in file order."""
    return [name_of(ln) for ln in lines if ln.strip().startswith("*") and name_of(ln)]


def start_record(sig, fid, masters):
    """(name, object id) of the start record that a record of type sig and form id fid overrides in a plugin with
    these masters, None when it overrides none: the id's top byte indexes Starfield.esm in the master list and its low
    24 bits are the start record's (module doc)."""
    top = fid >> 24
    if top >= len(masters) or masters[top].casefold() != STARFIELD:
        return None
    for s, obj, what in START_RECORDS:
        if s == sig and fid & 0xFFFFFF == obj:
            return what, obj
    return None
