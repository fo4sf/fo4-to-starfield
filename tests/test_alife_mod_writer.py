"""Standalone A-Life plugin writer (dotnet/ALifeMod): its contract with the runtime scripts and the schema, and an
independent TES4 header reader that confirms what the writer's own check reports.

Static tests always run. With FO4SF_DOTNET_TESTS=1 and a dotnet SDK on PATH, the writer is compiled (zero warnings
allowed) and its synthetic self-test runs; the plugins it leaves behind are re-read here without Mutagen. With
FO4SF_STARFIELD_ESM pointing at a local Starfield.esm as well, the vanilla preset is exported, built and checked
against it (read-only) and must master Starfield.esm alone. No game file is ever written."""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT = os.path.join(ROOT, "dotnet", "ALifeMod")
CS = os.path.join(PROJECT, "Program.cs")
CSPROJ = os.path.join(PROJECT, "ALifeMod.csproj")
SIM_PSC = os.path.join(ROOT, "scripts", "alife", "FO4SF_ALifeSimQuest.psc")
BEACON_PSC = os.path.join(ROOT, "scripts", "alife", "FO4SF_ALifeBeaconEffect.psc")
PRESETS = os.path.join(ROOT, "src", "fo4sf", "alife", "presets")
DOTNET = os.environ.get("FO4SF_DOTNET_TESTS") == "1" and shutil.which("dotnet") is not None

# How the writer fills each FO4SF_ALifeSimQuest property, by Papyrus type.
PROPERTY_TYPES = {
    "SquadTemplates": "actorbase[]", "SquadFactions": "faction[]", "FactionSquadSize": "int[]", "FactionPower": "float[]",
    "FactionRelationsFlat": "int[]", "Waymarkers": "objectreference[]", "NodeX": "float[]", "NodeY": "float[]",
    "NodeZ": "float[]", "NodeCap": "int[]", "NodeKind": "int[]", "NodeInitialOwner": "int[]", "NodeSpawnFaction": "int[]",
    "EdgeU": "int[]", "EdgeV": "int[]", "EdgeLen": "float[]", "MergeOffsetX": "float", "MergeOffsetY": "float",
    "OnlineSpawnRadiusM": "float", "OfflineDespawnRadiusM": "float", "OfflineSpeedMps": "float", "TickIntervalS": "float",
    "MaxActiveSquads": "int", "RespawnCooldownS": "float", "SimEnabledGlobal": "globalvariable",
    "OnlineRadiusGlobal": "globalvariable", "MaxSquadsGlobal": "globalvariable", "NotificationsGlobal": "globalvariable",
    "OptEnabled": "gameplayoption", "OptMaxSquads": "gameplayoption", "OptNotifications": "gameplayoption",
    "FieldTransponder": "potion",
}
BEACON_TYPES = {"SimQuest": "fo4sf_alifesimquest", "FieldTransponder": "potion"}
FORM_IDS = {
    "QuestId": 0x800, "SimEnabledId": 0x801, "OnlineRadiusId": 0x802, "MaxSquadsId": 0x803, "NotificationsId": 0x804,
    "OptEnabledId": 0x805, "OptMaxSquadsId": 0x806, "OptNotificationsId": 0x807, "GpogId": 0x808, "EffectId": 0x809,
    "TransponderId": 0x80A, "FirstWaymarkerId": 0x810, "FirstFactionId": 0x820, "FirstNpcId": 0x828,
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def cs_string_array(src, name):
    m = re.search(r"\b" + name + r"\s*=\s*\{(.*?)\};", src, re.S)
    if not m:
        raise AssertionError(f"{name} not found in Program.cs")
    return re.findall(r'"([^"]*)"', m.group(1))


def psc_properties(path):
    """(name, lower-cased type) for each property declaration, in order."""
    out = []
    for line in read(path).splitlines():
        line = line.split(";", 1)[0]
        m = re.match(r"\s*([A-Za-z_][\w:]*(?:\[\])?)\s+Property\s+(\w+)", line, re.I)
        if m:
            out.append((m.group(2), m.group(1).lower()))
    return out


def read_tes4_header(path):
    """Independent of Mutagen: the TES4 record's flags and MAST list. Starfield record headers are 24 bytes."""
    with open(path, "rb") as f:
        head = f.read(24)
        if len(head) < 24 or head[:4] != b"TES4":
            raise ValueError(f"{os.path.basename(path)} has no TES4 header")
        size, flags = struct.unpack_from("<II", head, 4)
        data = f.read(size)
    if len(data) != size:
        raise ValueError("truncated TES4 record")
    masters, pos = [], 0
    while pos + 6 <= len(data):
        sig, sub = data[pos:pos + 4], struct.unpack_from("<H", data, pos + 4)[0]
        body = data[pos + 6:pos + 6 + sub]
        if sig == b"MAST":
            masters.append(body.split(b"\0", 1)[0].decode("utf-8"))
        pos += 6 + sub
    return {"flags": flags, "masters": masters}


def tes4_blob(flags, masters):
    subs = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fII", 0.96, 1, 0x800)
    for m in masters:
        name = m.encode() + b"\0"
        subs += b"MAST" + struct.pack("<H", len(name)) + name + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    return b"TES4" + struct.pack("<II", len(subs), flags) + b"\0" * 12 + subs


class ContractTests(unittest.TestCase):
    def test_properties_cover_the_contract_in_order(self):
        props = cs_string_array(read(CS), "Properties")
        self.assertEqual(props, list(PROPERTY_TYPES))
        self.assertEqual(len(props), 32)
        self.assertEqual(cs_string_array(read(CS), "BeaconProperties"), list(BEACON_TYPES))

    @unittest.skipUnless(os.path.exists(SIM_PSC), "runtime script not present")
    def test_sim_quest_script_declares_exactly_what_the_writer_fills(self):
        self.assertEqual(psc_properties(SIM_PSC), list(PROPERTY_TYPES.items()))

    @unittest.skipUnless(os.path.exists(BEACON_PSC), "beacon script not present")
    def test_beacon_script_declares_exactly_what_the_writer_fills(self):
        self.assertEqual(psc_properties(BEACON_PSC), list(BEACON_TYPES.items()))

    def test_script_names(self):
        src = read(CS)
        self.assertIn('QuestScript = "FO4SF_ALifeSimQuest"', src)
        self.assertIn('BeaconScript = "FO4SF_ALifeBeaconEffect"', src)
        if os.path.exists(SIM_PSC):
            self.assertRegex(read(SIM_PSC), r"(?im)^\s*ScriptName\s+FO4SF_ALifeSimQuest\s+extends\s+Quest")
        if os.path.exists(BEACON_PSC):
            self.assertRegex(read(BEACON_PSC), r"(?im)^\s*ScriptName\s+FO4SF_ALifeBeaconEffect\s+extends\s+ActiveMagicEffect")

    def test_form_id_layout(self):
        src = read(CS)
        found = {k: int(v, 16) for k, v in re.findall(r"\b(\w+Id) = 0x([0-9A-Fa-f]+)", src)}
        for name, value in FORM_IDS.items():
            self.assertEqual(found.get(name), value, name)
        self.assertIn("MaxPool = 16", src)
        self.assertIn("MaxFactions = 8", src)
        # waymarkers 0x810..0x81F, factions 0x820..0x827, squads 0x828..0x82F: no overlap, all light-range
        self.assertEqual(FORM_IDS["FirstWaymarkerId"] + 16, FORM_IDS["FirstFactionId"])
        self.assertEqual(FORM_IDS["FirstFactionId"] + 8, FORM_IDS["FirstNpcId"])
        self.assertLessEqual(FORM_IDS["FirstNpcId"] + 8 - 1, 0xFFF)
        self.assertEqual(sorted(FORM_IDS.values())[:11], list(range(0x800, 0x80B)))

    def test_vanilla_anchors(self):
        src = read(CS)
        self.assertIn("PlayerFactionId = 0x01C21C", src)
        self.assertIn("XMarkerHeadingId = 0x000034", src)
        self.assertIn('TravelPackageEdid = "DefaultTravelToLinkedRef"', src)
        self.assertEqual(cs_string_array(src, "NodeKinds"), ["relay", "base", "checkpoint", "lair", "resource"])

    def test_quest_and_squad_flags(self):
        src = read(CS)
        self.assertIn("SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.StartsEnabled | SF.Quest.Flag.AllowRepeatedStages", src)
        for flag in ("Respawn", "Unique", "Essential", "Protected"):
            self.assertIn(f"SF.Npc.Flag.{flag}", src)
        self.assertIn("npc.VirtualMachineAdapter = null;", src)
        self.assertIn("npc.Factions.Clear();", src)

    def test_project_pins_and_warnings(self):
        proj = read(CSPROJ)
        self.assertIn("<TreatWarningsAsErrors>true</TreatWarningsAsErrors>", proj)
        self.assertIn("<TargetFramework>net9.0</TargetFramework>", proj)
        ref = re.search(r'Mutagen\.Bethesda\.Starfield" Version="([^"]+)"', read(os.path.join(ROOT, "dotnet", "ALife", "ALife.csproj")))
        self.assertIsNotNone(ref)
        self.assertIn(f'Mutagen.Bethesda.Starfield" Version="{ref.group(1)}"', proj)

    def test_no_local_paths_or_names(self):
        for path in (CS, CSPROJ, os.path.abspath(__file__)):
            text = read(path)
            self.assertIsNone(re.search(r"(?i)\b[a-z]:[\\/]", text.replace(r"\b[a-z]:[\\/]", "")), path)
            for word in ("Users" + "\\", "Steam" + "Library", "Desktop" + "\\"):
                self.assertNotIn(word, text, path)
            self.assertTrue(all(ord(c) < 128 for c in text), f"{path} is not ASCII")

    def test_slice1_writer_untouched(self):
        if shutil.which("git") is None:
            self.skipTest("git not on PATH")
        r = subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "dotnet/ALife", "tests/test_alife.py"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest("not a git checkout")
        self.assertEqual(r.stdout.strip(), "", "dotnet/ALife or tests/test_alife.py changed")


class HeaderReaderTests(unittest.TestCase):
    def test_reads_flags_and_masters(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.esm")
            with open(p, "wb") as f:
                f.write(tes4_blob(0x101, ["Starfield.esm", "Custom.esm"]))
            h = read_tes4_header(p)
            self.assertEqual(h["masters"], ["Starfield.esm", "Custom.esm"])
            self.assertEqual(h["flags"] & 0x101, 0x101)

    def test_refuses_non_plugins(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.esm")
            with open(p, "wb") as f:
                f.write(b"GRUP" + b"\0" * 40)
            with self.assertRaises(ValueError):
                read_tes4_header(p)


def run_writer(*args):
    return subprocess.run(["dotnet", "run", "-c", "Release", "--no-build", "--project", PROJECT, "--", *args],
                          capture_output=True, text=True)


@unittest.skipUnless(DOTNET, "set FO4SF_DOTNET_TESTS=1 with a dotnet SDK on PATH to run the C# writer")
class DotnetWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["dotnet", "build", "-c", "Release", "--no-incremental", PROJECT], capture_output=True, text=True)
        cls.build = r

    def test_compiles_without_warnings(self):
        out = self.build.stdout + self.build.stderr
        self.assertEqual(self.build.returncode, 0, out[-3000:])
        self.assertRegex(out, r"\b0 Warning\(s\)")
        self.assertRegex(out, r"\b0 Error\(s\)")

    def test_selftest_and_independent_headers(self):
        self.assertEqual(self.build.returncode, 0)
        with tempfile.TemporaryDirectory() as d:
            r = run_writer("selftest", d)
            self.assertEqual(r.returncode, 0, r.stdout[-4000:] + r.stderr[-2000:])
            m = re.search(r"selftest ok: (\d+) builds checked, (\d+) refusals, (\d+) mutations rejected", r.stdout)
            self.assertIsNotNone(m, r.stdout[-2000:])
            builds, refusals, mutations = map(int, m.groups())
            self.assertGreaterEqual(builds, 4)
            self.assertGreaterEqual(refusals, 15)
            self.assertGreaterEqual(mutations, 15)
            self.assertNotIn("FAIL  check passed", r.stdout)
            self.assertNotIn("FAIL  build accepted", r.stdout)

            vanilla = read_tes4_header(os.path.join(d, "vanilla", "StarfieldALife.esm"))
            self.assertEqual(vanilla["masters"], ["Starfield.esm"])
            self.assertEqual(vanilla["flags"] & 0x1, 0x1)
            self.assertEqual(vanilla["flags"] & 0x100, 0)
            light = read_tes4_header(os.path.join(d, "light", "MyLightALife.esm"))
            self.assertEqual(light["masters"], ["Starfield.esm"])
            self.assertEqual(light["flags"] & 0x101, 0x101)
            custom = read_tes4_header(os.path.join(d, "custom", "CustomALife.esm"))
            self.assertEqual(custom["masters"], ["Starfield.esm", "SynthCustomWorld.esm"])
            big = read_tes4_header(os.path.join(d, "payload128", "StarfieldALife.esm"))
            self.assertEqual(big["masters"], ["Starfield.esm"])
            # the atomic writer leaves no temporary directories behind
            for sub in ("vanilla", "light", "custom", "payload128"):
                self.assertEqual([x for x in os.listdir(os.path.join(d, sub)) if x.startswith(".partial")], [])

    def test_usage_and_refusal_exit_codes(self):
        self.assertEqual(self.build.returncode, 0)
        self.assertEqual(run_writer().returncode, 2)
        self.assertEqual(run_writer("build", "only-two").returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "bad.json")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("{not json")
            r = run_writer("build", os.path.join(d, "Starfield.esm"), cfg, os.path.join(d, "out"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("refused:", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(d, "out")))


STARFIELD_ESM = os.environ.get("FO4SF_STARFIELD_ESM", "")


@unittest.skipUnless(DOTNET and os.path.isfile(STARFIELD_ESM) and os.path.isfile(os.path.join(PRESETS, "vanilla_new_atlantis.json")),
                     "set FO4SF_DOTNET_TESTS=1 and FO4SF_STARFIELD_ESM=<local Starfield.esm> to build the vanilla preset")
class VanillaPresetTests(unittest.TestCase):
    def test_vanilla_preset_masters_starfield_only(self):
        sys.path.insert(0, os.path.join(ROOT, "src"))
        from fo4sf.alife import schema  # noqa: E402
        r = subprocess.run(["dotnet", "build", "-c", "Release", PROJECT], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])
        with tempfile.TemporaryDirectory() as d:
            payload = os.path.join(d, "payload.json")
            cfg = schema.load_alife_config(os.path.join(PRESETS, "vanilla_new_atlantis.json"))
            import json
            with open(payload, "w", encoding="utf-8") as f:
                json.dump(schema.export_writer_payload(cfg), f)
            out = os.path.join(d, "out")
            r = run_writer("build", STARFIELD_ESM, payload, out)
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            with open(payload, encoding="utf-8") as f:
                plugin = os.path.join(out, json.load(f)["plugin_name"])
            r = run_writer("check", plugin, STARFIELD_ESM, payload)
            self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
            self.assertIn("all checks pass", r.stdout)
            self.assertEqual(read_tes4_header(plugin)["masters"], ["Starfield.esm"])


if __name__ == "__main__":
    unittest.main()
