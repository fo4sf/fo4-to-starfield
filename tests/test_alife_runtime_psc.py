"""The standalone A-Life runtime scripts (scripts/alife/FO4SF_ALifeSimQuest.psc, FO4SF_ALifeAPI.psc,
FO4SF_ALifeBeaconEffect.psc): property parity with the plugin writer and the schema payload, Papyrus string sizes,
every engine call declared in Starfield's ContentResources.zip base scripts, and a real PapyrusCompiler.exe compile.

The game-file checks run only with FO4SF_STARFIELD set to the Starfield folder (Tools/ContentResources.zip and
Tools/Papyrus Compiler/PapyrusCompiler.exe under it); they never write into it. Offline checks are not in-game
acceptance.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "scripts", "alife")
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "src"))
from test_papyrus_strings import LIMIT, papyrus_texts, size  # noqa: E402

SIM = "FO4SF_ALifeSimQuest"
API = "FO4SF_ALifeAPI"
BEACON = "FO4SF_ALifeBeaconEffect"
SCRIPTS = (SIM, API, BEACON)

# (type, name, default or None): the exact Auto Const contract with the writer (dotnet/ALifeMod) and the schema
SIM_PROPERTIES = (
    ("ActorBase[]", "SquadTemplates", None), ("Faction[]", "SquadFactions", None),
    ("int[]", "FactionSquadSize", None), ("float[]", "FactionPower", None), ("int[]", "FactionRelationsFlat", None),
    ("ObjectReference[]", "Waymarkers", None),
    ("float[]", "NodeX", None), ("float[]", "NodeY", None), ("float[]", "NodeZ", None),
    ("int[]", "NodeCap", None), ("int[]", "NodeKind", None), ("int[]", "NodeInitialOwner", None),
    ("int[]", "NodeSpawnFaction", None),
    ("int[]", "EdgeU", None), ("int[]", "EdgeV", None), ("float[]", "EdgeLen", None),
    ("float", "MergeOffsetX", None), ("float", "MergeOffsetY", None),
    ("float", "OnlineSpawnRadiusM", "450.0"), ("float", "OfflineDespawnRadiusM", "620.0"),
    ("float", "OfflineSpeedMps", "1.35"), ("float", "TickIntervalS", "2.0"), ("int", "MaxActiveSquads", "8"),
    ("float", "RespawnCooldownS", "120.0"),
    ("GlobalVariable", "SimEnabledGlobal", None), ("GlobalVariable", "OnlineRadiusGlobal", None),
    ("GlobalVariable", "MaxSquadsGlobal", None), ("GlobalVariable", "NotificationsGlobal", None),
    ("GameplayOption", "OptEnabled", None), ("GameplayOption", "OptMaxSquads", None),
    ("GameplayOption", "OptNotifications", None),
    ("Potion", "FieldTransponder", None),
)
BEACON_PROPERTIES = ((SIM, "SimQuest", None), ("Potion", "FieldTransponder", None))

API_FUNCTIONS = ("GetController", "IsRunning", "SetEnabled", "SpawnSquadAtNode", "OrderRaid", "GetNodeOwner",
                 "SetNodeOwner", "GetActiveSquadCount", "PrintStatusSummary")
CONSOLE = ("Status", "StatusFor", "Enable", "Disable", "Spawn", "Raid", "Capture")

# log steps published to the packager's log-audit (board #70)
STEPS = {"init", "load_game", "options", "squad_spawn", "replenish", "order", "node_arrive", "garrison", "reroute",
         "materialize", "dematerialize", "stuck_relink", "marker_replace", "battle", "battle_end", "squad_defeated",
         "capture", "status", "api", "tick", "warn", "error"}
STATES = ("garrisoned", "marching_offline", "online_3d", "in_combat_offline", "dead_cooldown")

# every engine function the three scripts call, by the base script that declares it (or an ancestor of it)
NATIVES = {
    ("ActiveMagicEffect", "OnEffectStart"), ("Actor", "EvaluatePackage"), ("Actor", "IsDead"),
    ("Actor", "IsInCombat"), ("Actor", "SetGroupFaction"), ("Actor", "OnPlayerLoadGame"),
    ("Debug", "MessageBox"), ("Debug", "Notification"), ("Debug", "OpenUserLog"), ("Debug", "Trace"),
    ("Debug", "TraceUser"), ("Form", "GetFormID"), ("Game", "GetForm"), ("Game", "GetFormFromFile"),
    ("Game", "GetPlayer"), ("GameplayOption", "GetValue"), ("GameplayOption", "NotifyGameplayOptionUpdateFinished"),
    ("GlobalVariable", "GetValue"), ("GlobalVariable", "GetValueInt"), ("GlobalVariable", "SetValue"),
    ("Math", "abs"), ("Math", "Ceiling"), ("Math", "sqrt"),
    ("ObjectReference", "AddItem"), ("ObjectReference", "Delete"), ("ObjectReference", "DisableNoWait"),
    ("ObjectReference", "GetItemCount"), ("ObjectReference", "GetPositionX"), ("ObjectReference", "GetPositionY"),
    ("ObjectReference", "GetPositionZ"), ("ObjectReference", "GetWorldSpace"), ("ObjectReference", "IsInInterior"),
    ("ObjectReference", "MoveTo"), ("ObjectReference", "MoveToNearestNavmeshLocation"),
    ("ObjectReference", "PlaceActorAtMe"), ("ObjectReference", "SetLinkedRef"),
    ("Quest", "IsRunning"), ("Quest", "OnQuestInit"), ("Quest", "OnQuestStarted"),
    ("ScriptObject", "CancelTimer"), ("ScriptObject", "OnGameplayOptionChanged"), ("ScriptObject", "OnTimer"),
    ("ScriptObject", "RegisterForGameplayOptionChangedEvent"), ("ScriptObject", "RegisterForRemoteEvent"),
    ("ScriptObject", "StartTimer"), ("Utility", "GetCurrentRealTime"), ("Utility", "RandomFloat"),
    ("Utility", "RandomInt"),
}
# words followed by "(" that are syntax or array methods, not calls into the engine
SYNTAX = {"if", "elseif", "while", "return", "find", "new", "not"}


def read(name):
    with open(os.path.join(HERE, name + ".psc"), encoding="utf-8") as f:
        return f.read()


def code_only(src):
    """The source with ; comments, ;/ /; blocks, {doc comments} and string literals blanked."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == ";":
            if src.startswith(";/", i):
                end = src.find("/;", i + 2)
                end = n if end < 0 else end + 2
            else:
                end = src.find("\n", i)
                end = n if end < 0 else end
            out.append("\n" * src.count("\n", i, end))
            i = end
        elif c == "{":
            end = src.find("}", i + 1)
            end = n if end < 0 else end + 1
            out.append("\n" * src.count("\n", i, end))
            i = end
        elif c == '"':
            j = i + 1
            while j < n and src[j] not in '"\n':
                j += 2 if src[j] == "\\" else 1
            out.append('""')
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


PROP_RE = re.compile(r"^(\w+(?:\[\])?)\s+Property\s+(\w+)(?:\s*=\s*([-\w.]+))?\s+Auto\s+Const\b", re.M | re.I)
DEF_RE = re.compile(r"^\s*(?:[\w\[\]]+\s+)?(?:Function|Event)\s+(?:\w+\.)?(\w+)\s*\(", re.M | re.I)
CALL_RE = re.compile(r"\b(\w+)\s*\(")


def properties(src):
    return tuple((t, n, d or None) for t, n, d in PROP_RE.findall(code_only(src)))


def defined(src):
    return {m.lower() for m in DEF_RE.findall(code_only(src))}


def starfield_dir():
    d = os.environ.get("FO4SF_STARFIELD", "")
    return d if d and os.path.isdir(d) else None


def base_sources(zip_path):
    out = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and parts[2].lower().endswith(".psc"):
                out[parts[2][:-4].lower()] = z.read(name).decode("utf-8", errors="replace")
    return out


def declares(sources, script, name, depth=8):
    seen = set()
    while script and script.lower() not in seen and len(seen) < depth:
        seen.add(script.lower())
        src = sources.get(script.lower(), "")
        if re.search(r"^\s*(?:[\w\[\]]+\s+)?(?:Function|Event)\s+" + re.escape(name) + r"\s*\(", src, re.M | re.I):
            return True
        m = re.search(r"^\s*Scriptname\s+\w+\s+extends\s+(\w+)", src, re.M | re.I)
        script = m.group(1) if m else None
    return False


class RuntimeSourceTest(unittest.TestCase):
    def test_sim_quest_properties_are_the_writer_contract(self):
        src = read(SIM)
        self.assertTrue(src.startswith("Scriptname FO4SF_ALifeSimQuest extends Quest"))
        self.assertEqual(properties(src), SIM_PROPERTIES)

    def test_beacon_properties_and_base(self):
        src = read(BEACON)
        self.assertTrue(src.startswith("Scriptname FO4SF_ALifeBeaconEffect extends ActiveMagicEffect"))
        self.assertEqual(properties(src), BEACON_PROPERTIES)
        self.assertIn("Event OnEffectStart(ObjectReference akTarget, Actor akCaster, MagicEffect akBaseEffect, "
                      "float afMagnitude, float afDuration)", src)

    def test_api_is_global_and_complete(self):
        src = read(API)
        self.assertEqual(properties(src), ())
        for name in API_FUNCTIONS + CONSOLE:
            self.assertRegex(src, r"(?m)^[\w ]*Function " + name + r"\(.*\) global$", name)
        self.assertNotRegex(code_only(src), r"(?m)^\s*(?:[\w\[\]]+\s+)?Function\s+\w+\(.*\)\s*$")  # none non-global
        for name in CONSOLE:
            self.assertIn('cgf "FO4SF_ALifeAPI.' + name + '"', src)

    def test_api_calls_exist_on_the_quest(self):
        sim_defs = defined(read(SIM))
        api = code_only(read(API))
        for method in set(re.findall(r"\bq\.(\w+)\(", api)):
            self.assertIn(method.lower(), sim_defs, method)
        beacon = code_only(read(BEACON))
        for method in set(re.findall(r"\bq\.(\w+)\(", beacon)):
            self.assertIn(method.lower(), sim_defs, method)

    def test_strings_and_doc_comments_fit_the_loader_buffer(self):
        for name in SCRIPTS:
            for kind, line, text in papyrus_texts(read(name)):
                self.assertLessEqual(size(text), LIMIT, f"{name}.psc:{line} {kind}")

    def test_no_private_paths_or_names(self):
        for name in SCRIPTS:
            text = read(name)
            self.assertNotRegex(text, r"[A-Za-z]:[\\/](?:Users|Steam|FO4SF|Modding)", name)
            self.assertNotRegex(text, r"(?i)steamapps|\\Users\\", name)

    def test_log_steps_are_the_published_set(self):
        src = read(SIM)
        steps = set(re.findall(r'"step=(\w+)', src))
        self.assertEqual(steps, STEPS)
        self.assertIn('"ALIFE_MOD rt="', src)
        self.assertIn('string LOG_NAME = "StarfieldALife"', src)

    def test_state_machine_names_and_limits(self):
        src = read(SIM)
        for st in STATES:
            self.assertIn('"' + st + '"', src)
        self.assertIn("int MAX_SQ = 16", src)
        self.assertIn("int MAX_MEM = 8", src)
        self.assertIn("sqActors = new Actor[128]", src)              # 16 squads x 8 members, the array cap
        for size_expr in re.findall(r"new \w+\[(\w+)\]", code_only(src)):
            self.assertIn(size_expr, {"16", "128"})

    def test_idempotent_init_and_reload(self):
        src = code_only(read(SIM))
        self.assertRegex(src, r"Event OnQuestInit\(\)\s+InitOnce\(")
        self.assertRegex(src, r"Event OnQuestStarted\(\)\s+InitOnce\(")
        self.assertRegex(src, r"Function InitOnce\(string why\)\s+if inited\s+return\s+endif\s+inited = True")
        self.assertIn("Event Actor.OnPlayerLoadGame(Actor akSender)", src)
        self.assertIn("RebaseTimes(shift)", src)
        self.assertIn("GameplayOption.NotifyGameplayOptionUpdateFinished()", src)

    def test_no_reserved_words_as_names(self):
        # Starfield's compiler reserves these (a local named "guard" failed to compile on 18 Nov 2026)
        reserved = {"guard", "state", "auto", "property", "struct", "var", "length", "lockguard", "unlockguard",
                    "tryguard", "endguard"}
        for name in SCRIPTS:
            for decl in re.findall(r"(?m)^\s*(?:int|float|bool|string|Actor|Form|\w+(?:\[\])?)\s+(\w+)\s*=",
                                   code_only(read(name))):
                self.assertNotIn(decl.lower(), reserved, f"{name}: {decl}")

    def test_every_call_is_own_or_a_listed_native(self):
        own = set()
        for name in SCRIPTS:
            own |= defined(read(name))
        native_names = {n.lower() for _, n in NATIVES}
        for name in SCRIPTS:
            for call in set(CALL_RE.findall(code_only(read(name)))):
                low = call.lower()
                if low in SYNTAX or call in SCRIPTS or call[0].isupper() and low in {
                        "actor", "objectreference", "form"}:
                    continue
                self.assertTrue(low in own or low in native_names, f"{name}: {call}( is not defined or listed")


class WriterAndSchemaParityTest(unittest.TestCase):
    def test_writer_names_every_property(self):
        program = os.path.join(ROOT, "dotnet", "ALifeMod", "Program.cs")
        if not os.path.exists(program):
            self.skipTest("dotnet/ALifeMod/Program.cs not present yet")
        with open(program, encoding="utf-8") as f:
            cs = f.read()
        missing = [n for _, n, _ in SIM_PROPERTIES + BEACON_PROPERTIES if f'"{n}"' not in cs]
        self.assertEqual(missing, [])
        for script in (SIM, BEACON):
            self.assertIn(f'"{script}"', cs)

    def test_schema_payload_properties_match_types(self):
        try:
            from fo4sf.alife import schema
        except Exception as e:  # noqa: BLE001 - the schema lands separately
            self.skipTest(f"fo4sf.alife.schema not importable: {e}")
        try:
            cfg = schema.load_preset("vanilla_new_atlantis")
            payload = schema.export_writer_payload(cfg)
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"schema preset/export not ready: {e}")
        types = {n: t for t, n, _ in SIM_PROPERTIES}
        props = payload["properties"]
        for key, value in props.items():
            self.assertIn(key, types, key)
            t = types[key]
            if t.endswith("[]"):
                self.assertIsInstance(value, list, key)
                want = int if t == "int[]" else (int, float)
                self.assertTrue(all(isinstance(v, want) and not isinstance(v, bool) for v in value), key)
                self.assertLessEqual(len(value), 128, key)
            else:
                self.assertIsInstance(value, int if t == "int" else (int, float), key)
        f = len(props["FactionPower"])
        self.assertEqual(len(props["FactionRelationsFlat"]), f * f)
        n = len(props["NodeX"])
        for key in ("NodeY", "NodeZ", "NodeCap", "NodeKind", "NodeInitialOwner", "NodeSpawnFaction"):
            self.assertEqual(len(props[key]), n, key)
        self.assertGreater(props["OfflineDespawnRadiusM"], props["OnlineSpawnRadiusM"] + 50)


@unittest.skipUnless(starfield_dir(), "set FO4SF_STARFIELD to the Starfield folder for the game-file checks")
class GameFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = starfield_dir()
        cls.zip = os.path.join(d, "Tools", "ContentResources.zip")
        cls.compiler = os.path.join(d, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe")
        if not os.path.isfile(cls.zip):
            raise unittest.SkipTest("no Tools/ContentResources.zip")
        cls.sources = base_sources(cls.zip)

    def test_every_native_is_declared(self):
        missing = sorted(f"{s}.{n}" for s, n in NATIVES if not declares(self.sources, s, n))
        self.assertEqual(missing, [])

    def test_property_types_exist(self):
        for t, _, _ in SIM_PROPERTIES + BEACON_PROPERTIES:
            base = t.rstrip("[]")
            if base not in ("int", "float", "bool", "string", SIM):
                self.assertIn(base.lower(), self.sources, base)

    def test_compiles_with_papyrus_compiler(self):
        if not os.path.isfile(self.compiler):
            self.skipTest("no Tools/Papyrus Compiler/PapyrusCompiler.exe")
        tmp_root = os.environ.get("TMP") or None
        work = tempfile.mkdtemp(prefix="alife-runtime-", dir=tmp_root)
        try:
            src = os.path.join(work, "Source")
            os.makedirs(src)
            with zipfile.ZipFile(self.zip) as z:
                for name in z.namelist():
                    parts = name.split("/")
                    if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                            parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                        with open(os.path.join(src, parts[2]), "wb") as o:
                            o.write(z.read(name))
            out = os.path.join(work, "pex")
            for name in SCRIPTS:
                r = subprocess.run([self.compiler, name + ".psc", "-f=Starfield_Papyrus_Flags.flg",
                                    f"-i={HERE};{src}", f"-o={out}"], cwd=HERE, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("Compilation succeeded", r.stdout)
                self.assertTrue(os.path.isfile(os.path.join(out, name + ".pex")))
        finally:
            shutil.rmtree(work, ignore_errors=True)


class UntouchedSliceOneTest(unittest.TestCase):
    def test_slice_one_files_are_unchanged(self):
        if not shutil.which("git") or not os.path.isdir(os.path.join(ROOT, ".git")) and not os.path.isfile(
                os.path.join(ROOT, ".git")):
            self.skipTest("not a git checkout")
        files = ["scripts/alife/FO4SF_ALifeControllerQuest.psc", "scripts/alife/make_alife.py", "tests/test_alife.py"]
        r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"] + files, cwd=ROOT)
        self.assertEqual(r.returncode, 0, "slice 1 files changed")


if __name__ == "__main__":
    unittest.main()
