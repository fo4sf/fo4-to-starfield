"""The quest-engine probe (docs/questprobe/engine-questions.md): the contract between dotnet/QuestProbe (the plugin),
the three probe scripts and make_questprobe.py (precheck, the log reader). Synthetic only; the C# writer's own
self-test runs when a dotnet SDK is on PATH."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "questprobe"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "newgame"))
import make_newgame as ng  # noqa: E402
import make_questprobe as qp  # noqa: E402

DIR = os.path.join(ROOT, "scripts", "questprobe")
PSC = os.path.join(DIR, "FO4SF_QProbeQuest.psc")
FRAG = os.path.join(DIR, "FO4SF_QProbeFragments.psc")
SMQ = os.path.join(DIR, "FO4SF_QProbeSMQuest.psc")
CS = os.path.join(ROOT, "dotnet", "QuestProbe", "Program.cs")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def cs_const(cs, name):
    m = re.search(rf'\b{name} = "([^"]+)"', cs)
    return m.group(1) if m else None


class ContractTests(unittest.TestCase):
    def test_properties_written_and_declared(self):
        cs, psc = read(CS), read(PSC)
        declared = ng.declared_properties(psc)
        body = cs[cs.index("public static List<(string Name, object Value)> Properties"):]
        written = set(re.findall(r'\("(\w+)",', body[:body.index("};")])) | set(re.findall(r'Obj\("(\w+)"', cs))
        mandatory = {n for n, m in declared.items() if m}
        self.assertEqual(mandatory - written, set(), "mandatory properties the plugin never fills")
        self.assertEqual(written - set(declared), set(), "properties the plugin writes that the script lacks")
        self.assertFalse(declared["SMEvent"] or declared["SMQuest"], "a --no-sm build leaves these unset")

    def test_names_match(self):
        cs = read(CS)
        self.assertEqual(cs_const(cs, "ScriptName"), qp.SCRIPT)
        self.assertEqual(cs_const(cs, "FragmentScript"), qp.FRAGMENTS)
        self.assertEqual(cs_const(cs, "SmScript"), qp.SM_SCRIPT)
        self.assertEqual(cs_const(cs, "Plugin"), qp.PLUGIN)
        self.assertEqual(cs_const(cs, "DefaultCell"), qp.DEFAULT_CELL)
        for path, name in ((PSC, qp.SCRIPT), (FRAG, qp.FRAGMENTS), (SMQ, qp.SM_SCRIPT)):
            self.assertRegex(read(path), rf"^Scriptname {name} extends Quest\b")

    def test_fragment_function_is_the_one_the_plugin_names(self):
        name = cs_const(read(CS), "FragmentName")
        self.assertEqual(name, "Fragment_Stage_0010_Item_00")
        self.assertRegex(read(FRAG), rf"Function {name}\(\)")
        self.assertIn("FragmentRan(10)", read(FRAG))
        self.assertIn("Function FragmentRan(int stage)", read(PSC))

    def test_stages_and_objective(self):
        cs, psc = read(CS), read(PSC)
        self.assertIn("Stages = { " + ", ".join(str(s) for s in qp.STAGES) + " }", cs)
        for s in qp.STAGES:
            self.assertIn(f"SetStage({s})", psc)
        self.assertIn("SetObjectiveDisplayed(10)", psc)
        self.assertIn("SetObjectiveCompleted(10)", psc)
        self.assertIn("Objective = 10", cs)

    def test_one_log_for_all_scripts(self):
        for path in (PSC, SMQ):
            self.assertIn('"fo4sf_qprobe"', read(path))
        self.assertTrue(qp.LOG.endswith("fo4sf_qprobe.0.log"))

    def test_every_call_is_prechecked(self):
        listed = {f for bases in qp.NATIVES[qp.SCRIPT].values() for f in bases}
        own = set(re.findall(r"^\s*\w*\s*Function\s+(\w+)", read(PSC), re.M))
        array = {"Find", "RFind", "Add", "Insert", "Remove", "Clear"}            # array intrinsics, not natives
        self.assertEqual(set(re.findall(r"\.(\w+)\(", read(PSC))) - listed - own - array, set())
        sm_listed = {f for bases in qp.NATIVES[qp.SM_SCRIPT].values() for f in bases}
        self.assertEqual(set(re.findall(r"\.(\w+)\(", read(SMQ))) - sm_listed, set())
        events = {e for es in qp.EVENTS.values() for e in es}
        for path in (PSC, SMQ):
            self.assertEqual(set(re.findall(r"^Event (\w+)\(", read(path), re.M)) - events, set())

    def test_no_locals_named_after_types(self):
        """Papyrus refuses a variable named like a type or script (the new game's "door", PC 19 Oct)."""
        types = {"door", "actor", "quest", "keyword", "form", "cell", "message", "location", "objectreference",
                 "referencealias", "debug", "game", "utility", "spell", "faction", "scene", "topic"}
        for path in (PSC, FRAG, SMQ):
            names = re.findall(r"^\s*(?:\w+)(?:\[\])?\s+(\w+)\s*(?:=|$)", read(path), re.M)
            self.assertEqual({n.lower() for n in names} & types, set(), path)

    def test_no_unparenthesized_chained_cast(self):
        """Papyrus refuses "x as A as B" (the fragment's first compile, PC 19 Oct): the inner cast needs parentheses."""
        for path in (PSC, FRAG, SMQ):
            self.assertNotRegex(read(path), r"\bas\s+\w+\s+as\b", path)

    def test_story_event_returns_quests(self):
        """Starfield's SendStoryEventAndWait returns Quest[] (PC precheck, 19 Oct), FO4's a bool."""
        psc = read(PSC)
        self.assertIn("Quest[] startedBy = SMEvent.SendStoryEventAndWait()", psc)
        self.assertNotRegex(psc, r"bool\s+\w+\s*=\s*SMEvent\.SendStoryEventAndWait")

    def test_scripts_for(self):
        self.assertEqual(qp.scripts_for(True), [qp.SCRIPT, qp.FRAGMENTS, qp.SM_SCRIPT])
        self.assertEqual(qp.scripts_for(False), [qp.SCRIPT, qp.FRAGMENTS])


def fake_zip(path, drop=None):
    lines = {}
    for bases in qp.NATIVES.values():
        for b, fs in bases.items():
            lines.setdefault(b, set()).update(f"Function {f}() native" for f in fs)
    for b, es in qp.EVENTS.items():
        lines.setdefault(b, set()).update(f"Event {e}(int a, int b)" for e in es)
    with zipfile.ZipFile(path, "w") as z:
        for b, ls in lines.items():
            z.writestr(f"Scripts/Source/{b}.psc", "\n".join(sorted(x for x in ls if x != drop)) + "\n")
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.zip = os.path.join(self.tmp, "cr.zip")

    def test_all_found(self):
        fake_zip(self.zip)
        r = qp.precheck_zip(self.zip)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["signatures"]["Quest.OnStageSet"].startswith("Event OnStageSet("))

    def test_missing_native(self):
        fake_zip(self.zip, drop="Function SendStoryEventAndWait() native")
        self.assertEqual(qp.precheck_zip(self.zip)["missing"], ["Keyword.SendStoryEventAndWait"])

    def test_missing_event(self):
        fake_zip(self.zip, drop="Event OnStageSet(int a, int b)")
        self.assertEqual(qp.precheck_zip(self.zip)["missing"], ["Quest.OnStageSet"])


LOGTEXT = """[10/20/2026 - 10:00:00AM] FO4SF_QPROBE rt=1.0 init anchor=FO4Port.esm:4920 target=FO4Port.esm:4950 sm=True
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.0 probe start cell=[Cell <FO4Port_BostonPublicLibrary02>]
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.1 fragment ran stage=10 after=0.01
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.1 setstage 10 stage=10 done10=True fragment_by_now=10
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.2 alias target=[ObjectReference] filled=True distance=40.0
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.3 sm quest started
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.3 story event started=1 ours=True sm_running=True
[10/20/2026 - 10:00:05AM] FO4SF_QPROBE rt=6.4 onstageset stage=20 item=0 after=0.3
[10/20/2026 - 10:00:10AM] FO4SF_QPROBE rt=11.0 result E1_fragment=PASS E2_onstageset=PASS (1: 20) E3_alias=FILLED E4_questtype=LOOK E5_storymanager=PASS
[10/20/2026 - 10:00:10AM] FO4SF_NEWGAME rt=11.0 status stage=200
[10/20/2026 - 10:01:00AM] FO4SF_QPROBE rt=60.0 reached target distance=2.5
"""


class LogTests(unittest.TestCase):
    def test_summary(self):
        s = qp.summarize(LOGTEXT.splitlines())
        self.assertTrue(s["started"] and s["sm_started"] and s["reached"])
        self.assertEqual(s["fragment"], 10)
        self.assertEqual(s["stage_events"], [20])
        self.assertEqual(s["result"], {"E1_fragment": "PASS", "E2_onstageset": "PASS", "E3_alias": "FILLED",
                                       "E4_questtype": "LOOK", "E5_storymanager": "PASS"})

    def test_no_result_line(self):
        s = qp.summarize(LOGTEXT.splitlines()[:3])
        self.assertIsNone(s["result"])
        self.assertFalse(s["reached"])

    def test_the_result_line_names_every_answer(self):
        psc = read(PSC)
        for answer in qp.ANSWERS:
            self.assertIn(f"{answer}=", psc)


@unittest.skipUnless(shutil.which("dotnet"), "no dotnet SDK on PATH")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "QuestProbe"), "--",
                            "selftest", tmp], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
