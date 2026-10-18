"""make_bridge.py: the StarfieldCustom.ini [Papyrus] edit (pure text; the stage command needs the game's tools), the
compile step over every .psc of scripts/bridge (the compiler call replaced) and the probe script's functions."""
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "bridge"))
import make_bridge  # noqa: E402


class IniTests(unittest.TestCase):
    def test_empty_file_gets_the_section(self):
        new, changed = make_bridge.ensure_ini("")
        self.assertTrue(changed)
        self.assertEqual(new, "[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n")

    def test_other_sections_kept_and_section_appended(self):
        old = "[General]\nsLanguage=ENGLISH\n\n[Display]\nfGamma=1.0\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertTrue(changed)
        self.assertTrue(new.startswith(old))
        self.assertIn("\n[Papyrus]\nbEnableLogging=1\n", new)

    def test_existing_section_updated_in_place(self):
        old = "[Papyrus]\nbEnableLogging=0\nbEnableProfiling=0\n[Display]\nfGamma=1.0\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertTrue(changed)
        self.assertEqual(new, "[Papyrus]\nbEnableLogging=1\nbEnableProfiling=0\nbEnableTrace=1\nbLoadDebugInformation=1\n"
                              "[Display]\nfGamma=1.0\n")

    def test_already_set_is_unchanged(self):
        old = "[Papyrus]\nbEnableLogging=1\nbEnableTrace=1\nbLoadDebugInformation=1\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertFalse(changed)
        self.assertEqual(new, old)

    def test_case_insensitive_keys_and_section(self):
        old = "[papyrus]\nBENABLELOGGING = 1\nbenabletrace=0\n"
        new, changed = make_bridge.ensure_ini(old)
        self.assertTrue(changed)
        self.assertEqual(new, "[papyrus]\nBENABLELOGGING = 1\nbEnableTrace=1\nbLoadDebugInformation=1\n")


PSC = os.path.join(os.path.dirname(__file__), "..", "scripts", "bridge")
# FO4SF_Probe.Pos as verified in game (2026-10-14/15, nine R05 runs): the door probe must leave it as it is
POS_BODY = """Function Pos(int formId) global
    Form f = Game.GetForm(formId)
    ObjectReference r = f as ObjectReference
    if r == None
        Debug.TraceUser("fo4sf", "FO4SF ref=" + formId + " none")
        return
    endif
    string line = "FO4SF ref=" + formId + " pos=" + r.GetPositionX() + " " + r.GetPositionY() + " " + r.GetPositionZ()
    line += " ang=" + r.GetAngleZ()
    Cell c = r.GetParentCell()
    if c
        line += " cell=" + c.GetFormID()
    else
        line += " cell=none"
    endif
    line += " disabled=" + r.IsDisabled() + " loaded=" + r.Is3DLoaded()
    Debug.TraceUser("fo4sf", line)
EndFunction
"""


def read_psc(name):
    with open(os.path.join(PSC, name), encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def function(src, name):
    """The text of one function, from its declaration line to EndFunction."""
    m = re.search(rf"(?m)^(?:\w+ )?Function {name}\(.*?^EndFunction\n", src, re.S)
    return m.group(0) if m else None


class ProbeScriptTests(unittest.TestCase):
    """FO4SF_Probe.psc (the scripted door's Step 0, 2026-10-16): Resolve and MoveTo beside the verified Pos / Ack / Player."""
    def test_resolve_and_moveto_are_global_functions(self):
        src = read_psc("FO4SF_Probe.psc")
        self.assertRegex(src, r"(?m)^Function Resolve\(string plugin, int id\) global$")
        self.assertRegex(src, r"(?m)^Function MoveTo\(string plugin, int id, float dx, float dy, float dz\) global$")
        lookup = function(src, "Lookup")
        self.assertIn("Game.GetFormFromFile(id, plugin)", lookup)          # FO4SF_LoadDoor's lookup: local id + file name
        self.assertIn('"FO4SF " + kind + " plugin=" + plugin + " id=" + id', lookup)
        for key in (' form=none', ' form=', ' ref=false', ' ref=true', ' disabled=', ' loaded='):
            self.assertIn(key, lookup)
        self.assertIn('Lookup("resolve", plugin, id)', function(src, "Resolve"))
        mv = function(src, "MoveTo")
        self.assertIn('Lookup("target", plugin, id)', mv)
        for phase in ("refused", "before", "after", "settled"):
            self.assertIn(f'" phase={phase}"', mv)
        # the door script's own call: offsets, match rotation, no rotated offset
        with open(os.path.join(PSC, "..", "door_bridge", "FO4SF_LoadDoor.psc"), encoding="utf-8") as f:
            door = f.read()
        self.assertIn("akActionRef.MoveTo(destination, 0.0, 0.0, 0.0, True, False)", door)
        self.assertIn("p.MoveTo(target, dx, dy, dz, True, False)", mv)
        where = function(src, "Where")
        for key in (' pos=', ' ang=', ' cell=', ' cell=none', ' cellname=', ' world=', ' world=none', ' worldname='):
            self.assertIn(key, where)

    def test_pos_ack_and_player_are_unchanged(self):
        src = read_psc("FO4SF_Probe.psc")
        self.assertEqual(function(src, "Pos"), POS_BODY)
        self.assertIn('Debug.TraceUser("fo4sf", "FO4SF ack " + tag)', function(src, "Ack"))
        self.assertIn('"FO4SF player pos="', function(src, "Player"))

    def test_the_editor_id_is_asked_in_its_own_function(self):
        # GetFormEditorID is DebugOnly: only EditorId calls it, so a failure there can only empty a name
        src = read_psc("FO4SF_Probe.psc")
        calls = [n for n in ("Ack", "Pos", "Player", "Where", "Lookup", "Resolve", "MoveTo")
                 if "GetFormEditorID" in function(src, n)]
        self.assertEqual(calls, [])
        self.assertIn("f.GetFormEditorID()", function(src, "EditorId"))


def script_types(src):
    """Capitalised type / script names a .psc uses (globals, declarations, casts, parameters, return types, extends)."""
    s = re.sub(r"\{[^}]*\}", "", src)                     # doc comments
    s = re.sub(r'"[^"\n]*"', '""', s)                     # strings
    s = re.sub(r";[^\n]*", "", s)                          # line comments
    found = set(re.findall(r"\b([A-Z]\w*)\.\w+\s*\(", s))
    found |= set(re.findall(r"\bas\s+([A-Z]\w*)", s))
    found |= set(re.findall(r"(?m)^[ \t]*([A-Z]\w*)[ \t]+[a-z]\w*[ \t]*=", s))
    found |= set(re.findall(r"(?m)^[ \t]*([A-Z]\w*)[ \t]+(?:Function|Property)\b", s))
    found |= set(re.findall(r"[(,][ \t]*([A-Z]\w*)[ \t]+[a-z]\w*", s))
    found |= set(re.findall(r"\bextends\s+(\w+)", s))
    found -= set(re.findall(r"\bProperty\s+(\w+)", s))      # a property used as FO4SF_Cmd.GetValueInt() is no type
    return found - {"String", "Int", "Float", "Bool", "None", "True", "False", "Self", "Parent"}


class CompileStepTests(unittest.TestCase):
    """make_bridge.py's compile step (no game tools: the compiler call is replaced, nothing else)."""
    def fake_run(self, fail=()):
        calls = []

        def run(cmd, cwd=None):
            calls.append((cmd, cwd))
            if cmd[1] in fail:
                return "Compilation failed."
            out_dir = next(a[3:] for a in cmd if a.startswith("-o="))
            open(os.path.join(out_dir, cmd[1][:-4] + ".pex"), "wb").close()
            return "Compilation succeeded."
        return run, calls

    def test_every_psc_of_the_folder_is_compiled(self):
        on_disk = sorted(f for f in os.listdir(make_bridge.HERE) if f.lower().endswith(".psc"))
        self.assertEqual(make_bridge.sources(), on_disk)
        self.assertIn("FO4SF_Probe.psc", on_disk)
        self.assertIn("FO4SF_Bridge.psc", on_disk)
        run, calls = self.fake_run()
        with mock.patch.object(make_bridge, "run", run), tempfile.TemporaryDirectory() as d:
            pex = make_bridge.compile_script("PapyrusCompiler.exe", os.path.join(d, "Source"), os.path.join(d, "Scripts"))
            self.assertEqual([c[0][1] for c in calls], on_disk)              # by bare name, one call each
            self.assertTrue(all(cwd == make_bridge.HERE for _, cwd in calls))
            self.assertTrue(all("-f=Starfield_Papyrus_Flags.flg" in c for c, _ in calls))
            self.assertEqual(sorted(os.listdir(os.path.join(d, "Scripts"))), [n[:-4] + ".pex" for n in on_disk])
            self.assertEqual(pex, os.path.join(d, "Scripts", "FO4SF_Bridge.pex"))

    def test_a_script_that_does_not_compile_stops_the_stage(self):
        run, _ = self.fake_run(fail=("FO4SF_Probe.psc",))
        with mock.patch.object(make_bridge, "run", run), tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                make_bridge.compile_script("PapyrusCompiler.exe", d, os.path.join(d, "Scripts"))

    def test_the_import_allowlist_covers_every_type_the_scripts_use(self):
        # the compile only sees the base scripts in IMPORTS (extract_sources): a type outside it would fail in game tools
        own = {n[:-4] for n in make_bridge.sources()}
        for name in make_bridge.sources():
            used = script_types(read_psc(name)) - own
            self.assertTrue(used, name)
            self.assertEqual(sorted(used - set(make_bridge.IMPORTS)), [], name)
        self.assertEqual(script_types(read_psc("FO4SF_Probe.psc")),
                         {"Actor", "Cell", "Debug", "Form", "Game", "ObjectReference", "Utility", "WorldSpace"})


if __name__ == "__main__":
    unittest.main()
