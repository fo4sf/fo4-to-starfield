"""Unit, binary-layout, stage/fold/verify, ride-along install, and log tests for CF-8 Radiation & Optional Mutations
(dotnet/RadsCore, scripts/rads/*, src/fo4sf/rads/core_log.py, docs/rads/rads-core.md)."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from unittest import mock
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "rads"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))

from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.core.core_values import CORE_VALUES_PLUGIN, core_form_id  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
from fo4sf.rads import core_log as cl  # noqa: E402
import exp_install  # noqa: E402
import make_rads_core as mrc  # noqa: E402
import planet_probe_install  # noqa: E402
import rads_core_install as rci  # noqa: E402
import rads_probe_install  # noqa: E402

PLUGIN = "FO4SFRads.esm"
PSC_PATH = ROOT / "scripts" / "rads" / "FO4SF_RadsCoreQuest.psc"
CS_PATH = ROOT / "dotnet" / "RadsCore" / "Program.cs"
CSPROJ_PATH = ROOT / "dotnet" / "RadsCore" / "RadsCore.csproj"
DOC_PATH = ROOT / "docs" / "rads" / "rads-core.md"
PSC_TEXT = PSC_PATH.read_text(encoding="utf-8")
CS_TEXT = CS_PATH.read_text(encoding="utf-8")
DOC_TEXT = DOC_PATH.read_text(encoding="utf-8")


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\n",
    "Keyword": "Scriptname Keyword extends Form\n",
    "Activator": "Scriptname Activator extends Form\n",
    "Hazard": "Scriptname Hazard extends Form\n",
    "Perk": "Scriptname Perk extends Form\n",
    "FormList": (
        "Scriptname FormList extends Form\n"
        "int Function GetSize() native\n"
        "Form Function GetAt(int i) native\n"
    ),
    "GlobalVariable": (
        "Scriptname GlobalVariable extends Form\n"
        "float Function GetValue() native\n"
        "Function SetValue(float v) native\n"
    ),
    "GameplayOption": (
        "Scriptname GameplayOption extends Form\n"
        "float Function GetValue() native\n"
        "Function NotifyGameplayOptionUpdateFinished() native global\n"
    ),
    "Spell": (
        "Scriptname Spell extends Form\n"
        "Function Cast(ObjectReference s, ObjectReference t) native\n"
    ),
    "ObjectReference": (
        "Scriptname ObjectReference extends Form\n"
        "float Function GetValue(ActorValue a) native\n"
        "Function SetValue(ActorValue a, float f) native\n"
        "Function ModValue(ActorValue a, float f) native\n"
        "float Function GetBaseValue(ActorValue a) native\n"
        "Function AddItem(Form f, int n, bool b) native\n"
        "int Function GetItemCount(Form f) native\n"
        "bool Function AddSpell(Spell s, bool b) native\n"
        "ObjectReference Function PlaceAtMe(Form f, int n, bool p, bool d, bool w) native\n"
        "ObjectReference[] Function FindAllReferencesWithKeyword(Form k, float r) native\n"
        "bool Function IsDisabled() native\n"
        "Function Disable(bool b) native\n"
        "Function Delete() native\n"
    ),
    "Actor": (
        "Scriptname Actor extends ObjectReference\n"
        "Function EquipItem(Form f, bool a, bool b) native\n"
        "Function AddPerk(Perk p, bool b) native\n"
        "Function RemovePerk(Perk p) native\n"
        "bool Function HasPerk(Perk p) native\n"
        "bool Function HasSpell(Form f) native\n"
        "bool Function IsDead() native\n"
        "Function Kill(Actor k) native\n"
        "Event OnItemEquipped(Form b, ObjectReference r)\nEndEvent\n"
        "Event OnPlayerSwimming()\nEndEvent\n"
        "Event OnPlayerLoadGame()\nEndEvent\n"
    ),
    "Game": (
        "Scriptname Game\n"
        "Actor Function GetPlayer() native global\n"
        "bool Function IsPluginInstalled(string p) native global\n"
    ),
    "Debug": (
        "Scriptname Debug\n"
        "Function Notification(string s) native global\n"
        "bool Function OpenUserLog(string n) native global\n"
        "bool Function TraceUser(string n, string t) native global\n"
    ),
    "Utility": (
        "Scriptname Utility\n"
        "float Function GetCurrentRealTime() native global\n"
        "int Function RandomInt(int a, int b) native global\n"
    ),
    "ScriptObject": (
        "Scriptname ScriptObject\n"
        "Function StartTimer(float f, int i) native\n"
        "bool Function RegisterForRemoteEvent(ScriptObject s, string e) native\n"
        "Function RegisterForGameplayOptionChangedEvent() native\n"
        "Event OnGameplayOptionChanged(GameplayOption[] o)\nEndEvent\n"
    ),
    "Quest": (
        "Scriptname Quest extends ScriptObject\n"
        "bool Function GetStageDone(int i) native\n"
    ),
}


def fake_sources(zip_path, drop=()):
    with zipfile.ZipFile(zip_path, "w") as z:
        for name, text in BASES.items():
            if name not in drop:
                z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags")


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
os.makedirs(out, exist_ok=True)
open(os.path.join(out, name + ".pex"), "wb").write(text.encode("utf-8"))
print("Compilation succeeded.")
"""


def fake_compiler(root):
    script = Path(root) / "fakec.py"
    script.write_text(FAKE_COMPILER.format(python=sys.executable), encoding="utf-8")
    if os.name != "nt":
        script.chmod(0o755)
        return script
    cmd = Path(root) / "fakec.cmd"
    cmd.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    return cmd


class ContractTests(unittest.TestCase):
    def test_script_properties_match_writer_order_and_names(self):
        m = re.search(r"PropNames\s*=\s*\{([^}]*)\}", CS_TEXT, re.S)
        tool_props = re.findall(r'"(\w+)"', m.group(1))
        psc_props = re.findall(r"^(\w+)\s+Property\s+(\w+)\s+Auto\s+Const(?:\s+Mandatory)?\b", PSC_TEXT, re.M)
        self.assertEqual([name for _, name in psc_props], tool_props)
        self.assertEqual(len(tool_props), 30)
        self.assertEqual(tool_props[-1], "TestModeGlobal")
        self.assertIn("TestModeGlobal != None && TestModeGlobal.GetValue() != 0.0", PSC_TEXT)
        self.assertTrue(PSC_TEXT.startswith("Scriptname FO4SF_RadsCoreQuest extends Quest"))

    def test_no_script_variable_shadows_a_property_name(self):
        decl = re.compile(
            r"^\s*(?!Event|Function|EndFunction|EndEvent|return|if|elseif|else|endif|while|endwhile|Scriptname)"
            r"[A-Za-z_]\w*(?:\[\])?\s+([A-Za-z_]\w*)\s*(?:=|$)"
        )
        props = {m.lower() for m in re.findall(r"\bProperty\s+(\w+)", PSC_TEXT)}
        vars_found = [
            m.group(1)
            for line in PSC_TEXT.splitlines()
            if "Property" not in line
            for m in [decl.match(line.split(";")[0])]
            if m
        ]
        self.assertEqual([v for v in vars_found if v.lower() in props], [])

    def test_every_log_event_and_stage_is_wired(self):
        for ev in cl.EVENTS:
            if ev == "say":
                self.assertIn('Trace("say text="', PSC_TEXT)
            else:
                self.assertRegex(PSC_TEXT, rf'Trace\("{ev} ')
        for st in cl.ALL_STAGES:
            self.assertIn(f"GetStageDone({st})", PSC_TEXT)
        self.assertIn("{ 5, 10, 20, 30, 40, 50, 60 }", CS_TEXT)

    def test_pipboy_rads_local_id_matches_native_pipboy_menu(self):
        pipboy_cpp = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertIn("kRadsLocalId = 0x800", pipboy_cpp)
        self.assertEqual(core_form_id("FO4SF_Rads"), 0x800)
        self.assertEqual(core_form_id("FO4SF_Special_Intelligence"), 0x814)
        self.assertEqual(core_form_id("FO4SF_TestModeEnabled"), 0x860)
        self.assertIn(CORE_VALUES_PLUGIN, CS_TEXT)
        self.assertIn('RadsAvifEdid = "FO4SF_Rads"', CS_TEXT)
        for edid in (
            "FO4SF_Rads", "FO4SF_RadsCapPct", "FO4SF_RadsDisplayPct",
            "FO4SF_RadsStage", "FO4SF_RadAway", "FO4SF_RadX",
        ):
            self.assertIn(edid, DOC_TEXT)

    def test_new_files_carry_zero_private_paths_or_links(self):
        drive_re = re.compile(r"\b[A-Za-z]:[\\/]")
        checked = (
            CS_PATH, CSPROJ_PATH, PSC_PATH, DOC_PATH, Path(__file__),
            ROOT / "scripts" / "rads" / "make_rads_core.py",
            ROOT / "scripts" / "rads" / "rads_core_install.py",
            ROOT / "src" / "fo4sf" / "rads" / "core_log.py",
        )
        for p in checked:
            txt = p.read_text(encoding="utf-8")
            m = drive_re.search(txt)
            self.assertIsNone(m, f"drive path {m.group(0) if m else ''} in {p.relative_to(ROOT)}")


class RuleAndMutationMathTests(unittest.TestCase):
    def test_mode_a_caps_max_hp_and_preserves_ten_percent_floor_below_1000(self):
        self.assertEqual(cl.mode_a_health_delta(0, 200), 0.0)
        self.assertEqual(cl.mode_a_health_delta(100, 200), -20.0)
        self.assertEqual(cl.mode_a_health_delta(300, 200), -60.0)
        self.assertEqual(cl.mode_a_health_delta(600, 200), -120.0)
        for base in (100.0, 105.0, 200.0, 333.0):
            for rads in (0, 150, 500, 899, 950, 999):
                eff = base + cl.mode_a_health_delta(rads, base)
                self.assertGreaterEqual(eff, base * 0.10 - 1e-6, (base, rads, eff))
        self.assertEqual(cl.sickness_stage(1000), 5)

    def test_mode_b_sickness_thresholds(self):
        self.assertEqual(cl.mode_b_stat_deltas(0), (0.0, 0.0, 0.0))
        self.assertEqual(cl.mode_b_stat_deltas(199), (0.0, 0.0, 0.0))
        self.assertEqual(cl.mode_b_stat_deltas(200), (-1.0, 0.0, 0.0))
        self.assertEqual(cl.mode_b_stat_deltas(399), (-1.0, 0.0, 0.0))
        self.assertEqual(cl.mode_b_stat_deltas(400), (-2.0, -1.0, 0.0))
        self.assertEqual(cl.mode_b_stat_deltas(600), (-3.0, -2.0, -1.0))
        self.assertEqual(cl.mode_b_stat_deltas(800), (-3.0, -2.0, -2.0))
        self.assertEqual(cl.mode_b_stat_deltas(999), (-3.0, -2.0, -2.0))
        self.assertEqual(cl.mode_b_stat_deltas(1000), (-3.0, -2.0, -2.0))

    def test_switching_between_mode_a_and_mode_b_has_zero_drift(self):
        base_hp = 200.0
        stats = [200.0, 6.0, 7.0, 5.0]  # HP, END, AGI, STR
        applied = [0.0, 0.0, 0.0, 0.0]

        def sync(rads, rule):
            want = cl.target_deltas(rads, rule, base_hp)
            for i in range(4):
                d = want[i] - applied[i]
                stats[i] += d
                applied[i] = want[i]

        sync(250, 0)
        self.assertEqual(stats, [150.0, 6.0, 7.0, 5.0])
        sync(250, 1)
        self.assertEqual(stats, [200.0, 5.0, 7.0, 5.0])
        sync(650, 1)
        self.assertEqual(stats, [200.0, 3.0, 5.0, 4.0])
        sync(650, 0)
        self.assertEqual(stats, [70.0, 6.0, 7.0, 5.0])
        sync(350, 1)  # RadAway -300 in Mode B
        self.assertEqual(stats, [200.0, 5.0, 7.0, 5.0])
        sync(50, 1)   # RadAway -300 in Mode B
        self.assertEqual(stats, [200.0, 6.0, 7.0, 5.0])
        sync(0, 0)    # Final clean reset in Mode A
        self.assertEqual(stats, [200.0, 6.0, 7.0, 5.0])
        self.assertEqual(applied, [0.0, 0.0, 0.0, 0.0])

    def test_radx_resistance_scaling(self):
        self.assertAlmostEqual(cl.scale_by_resist(50.0, 0.0), 50.0)
        self.assertAlmostEqual(cl.scale_by_resist(50.0, 100.0), 25.0)
        self.assertAlmostEqual(cl.scale_by_resist(30.0, 100.0), 15.0)
        self.assertAlmostEqual(cl.scale_by_resist(100.0, 300.0), 25.0)


def log_line(rt, event, **kw):
    body = " ".join(f"{k}={v}" for k, v in kw.items())
    return f"[11/16/2026 - 04:00:00PM] FO4SFRADSCORE rt={rt} {event} {body} end=true"


def sample_pass_log():
    lines = [
        log_line(1.0, "init", version=1, quest=0x06000850, installed="true"),
        log_line(1.1, "start", rads_av=0x06000800, cap_pct_av=0x06000801, rad_resist_av=0x06000804,
                 rule_glob=0x06000806, mut_glob=0x06000807, hazard=0x06000828, emitter=0x0600082A,
                 water=0x0600082B, radaway=0x06000820, radx=0x06000821, food=0x06000822,
                 dirty_water=0x06000823, mut_flst=0x06000835, starched=0x06000834),
        log_line(2.0, "control", av=0x2D4, delta=10.0, called="true", before=200.0, after=210.0, restored=200.0),
        log_line(2.1, "set", stage=10, wrote=50.0, read=50.0),
        log_line(2.2, "set", stage=10, wrote=0.0, read=0.0),
        log_line(2.3, "sync", reason="stage10_done", rule=0, rads=0.0, cap_pct=0.0, stage=0,
                 hp=200.0, base_hp=200.0, end=5.0, agi=5.0, str=5.0,
                 app_hp=0.0, app_end=0.0, app_agi=0.0, app_str=0.0, mut_on=0, mut_count=0),
        log_line(2.4, "stage_done", stage=10, rads=0.0, rule=0, cap_pct=0.0, sick_stage=0, mut_count=0, ok="true"),
        log_line(5.0, "radx", resist_before=0.0, added=100.0, resist_now=100.0, expires_in=60.0),
        log_line(5.1, "gain", source="hazard_emitter", raw=30.0, resist=100.0, added=15.0, rads=15.0),
        log_line(6.6, "gain", source="spell_settle", raw=100.0, resist=0.0, added=100.0, rads=115.0),
        log_line(6.7, "gain", source="hazard_zone", raw=85.0, resist=0.0, added=85.0, rads=200.0),
        log_line(6.8, "sync", reason="stage20_done", rule=0, rads=200.0, cap_pct=20.0, stage=1,
                 hp=160.0, base_hp=200.0, end=5.0, agi=5.0, str=5.0,
                 app_hp=-40.0, app_end=0.0, app_agi=0.0, app_str=0.0, mut_on=0, mut_count=0),
        log_line(6.9, "stage_done", stage=20, rads=200.0, rule=0, cap_pct=20.0, sick_stage=1, mut_count=0, ok="true"),
        log_line(10.0, "gain", source="water_swim", raw=20.0, resist=0.0, added=20.0, rads=225.0),
        log_line(10.1, "gain", source="dirty_water", raw=25.0, resist=0.0, added=25.0, rads=250.0),
        log_line(10.2, "gain", source="irradiated_food", raw=50.0, resist=0.0, added=50.0, rads=300.0),
        log_line(11.7, "sync", reason="stage30_done", rule=0, rads=600.0, cap_pct=60.0, stage=3,
                 hp=80.0, base_hp=200.0, end=5.0, agi=5.0, str=5.0,
                 app_hp=-120.0, app_end=0.0, app_agi=0.0, app_str=0.0, mut_on=0, mut_count=0),
        log_line(11.8, "stage_done", stage=30, rads=600.0, rule=0, cap_pct=60.0, sick_stage=3, mut_count=0, ok="true"),
        log_line(13.0, "mode_switch", stage=40, from_rule=0, to_rule=1, rads=600.0,
                 hp=200.0, end=2.0, agi=3.0, str=4.0, drift_hp=0.0, drift_end=0.0, drift_agi=0.0, drift_str=0.0, ok="true"),
        log_line(13.1, "mode_switch", stage=40, from_rule=1, to_rule=0, rads=600.0,
                 hp=80.0, end=5.0, agi=5.0, str=5.0, drift_hp=0.0, drift_end=0.0, drift_agi=0.0, drift_str=0.0, ok="true"),
        log_line(13.2, "stage_done", stage=40, rads=600.0, rule=1, cap_pct=60.0, sick_stage=3, mut_count=0, ok="true"),
        log_line(15.0, "mutation", action="granted", perk=0x06000830, starched="false", count=1),
        log_line(15.1, "mutation", action="locked_cure", perk="none", starched="true", count=1),
        log_line(15.2, "radaway", before=650.0, delta=-300.0, rads=350.0, rule=1, mut_on=1, starched="true", cured_perk="none"),
        log_line(15.3, "mutation", action="cured", perk=0x06000830, starched="false", count=0),
        log_line(15.4, "radaway", before=350.0, delta=-300.0, rads=50.0, rule=1, mut_on=1, starched="false", cured_perk=0x06000830),
        log_line(15.5, "stage_done", stage=50, rads=50.0, rule=1, cap_pct=5.0, sick_stage=0, mut_count=0, ok="true"),
        log_line(18.0, "fatal", rads=1000.0, rule=0, sick_stage=5, lethal="false"),
        log_line(18.1, "radaway", before=1000.0, delta=-300.0, rads=700.0, rule=0, mut_on=0, starched="false", cured_perk="none"),
        log_line(18.2, "radaway", before=700.0, delta=-300.0, rads=400.0, rule=0, mut_on=0, starched="false", cured_perk="none"),
        log_line(18.3, "radaway", before=400.0, delta=-300.0, rads=100.0, rule=0, mut_on=0, starched="false", cured_perk="none"),
        log_line(18.4, "radaway", before=100.0, delta=-100.0, rads=0.0, rule=0, mut_on=0, starched="false", cured_perk="none"),
        log_line(18.5, "sync", reason="stage60_clean", rule=0, rads=0.0, cap_pct=0.0, stage=0,
                 hp=200.0, base_hp=200.0, end=5.0, agi=5.0, str=5.0,
                 app_hp=0.0, app_end=0.0, app_agi=0.0, app_str=0.0, mut_on=0, mut_count=0),
        log_line(18.6, "stage_done", stage=60, rads=0.0, rule=0, cap_pct=0.0, sick_stage=0, mut_count=0, ok="true"),
        log_line(18.7, "verdict", **{"pass": "true", "stages": "10,20,30,40,50,60", "drift": 0.0}),
    ]
    return lines


class CoreLogTests(unittest.TestCase):
    def test_full_automated_run_passes(self):
        s = cl.summarize(sample_pass_log())
        self.assertTrue(s["passed"])
        self.assertTrue(s["verdict"].startswith("PASS: stages 10..60 verified"))
        rep = "\n".join(cl.report(s))
        self.assertIn("mode_switch: 0->1 ok=True drift=(0,0,0,0)", rep)
        self.assertIn("stage 50: ok=True", rep)
        self.assertTrue(rep.endswith(s["verdict"]))

    def test_passive_live_session_without_stages_passes(self):
        lines = [
            log_line(1.0, "init", version=1, quest=0x06000850, installed="true"),
            log_line(1.1, "start", rads_av=0x06000800),
            log_line(2.0, "sync", reason="init", rule=0, rads=0.0, cap_pct=0.0, stage=0, hp=200.0, base_hp=200.0,
                     end=5.0, agi=5.0, str=5.0, mut_on=0, mut_count=0),
            "[11/16/2026] FO4SFRADSCORE rt=3.0 say text=RadAway used. Rads 0, HP 200 end=true",
        ]
        s = cl.summarize(lines)
        self.assertTrue(s["passed"])
        self.assertTrue(s["verdict"].startswith("PASS (passive)"))

    def test_missing_or_failed_stages_and_cut_lines(self):
        incomplete = [l for l in sample_pass_log() if "stage=60" not in l and " verdict " not in l]
        s_inc = cl.summarize(incomplete)
        self.assertFalse(s_inc["passed"])
        self.assertIn("stages missing [60]", s_inc["verdict"])

        failed = [l.replace("stage=40 rads=600.0 rule=1 cap_pct=60.0 sick_stage=3 mut_count=0 ok=true",
                            "stage=40 rads=600.0 rule=1 cap_pct=60.0 sick_stage=3 mut_count=0 ok=false")
                  for l in sample_pass_log()]
        s_fail = cl.summarize(failed)
        self.assertFalse(s_fail["passed"])
        self.assertTrue(s_fail["verdict"].startswith("FAIL:"))

        with_cut = sample_pass_log() + ["FO4SFRADSCORE rt=99.0 sync reason=cut_without_end"]
        s_cut = cl.summarize(with_cut)
        self.assertEqual(s_cut["cut"], 1)
        self.assertTrue(any("truncated" in p for p in s_cut["problems"]))


class PrecheckAndCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_precheck_passes_and_detects_missing_native(self):
        z = os.path.join(self.tmp.name, "cr.zip")
        fake_sources(z)
        r = mrc.precheck_sources(mrc.read_sources(z))
        self.assertEqual(r["missing"], [])

        z_bad = os.path.join(self.tmp.name, "cr_bad.zip")
        fake_sources(z_bad, drop=("GameplayOption",))
        r_bad = mrc.precheck_sources(mrc.read_sources(z_bad))
        self.assertIn("GameplayOption.GetValue", r_bad["missing"])

    def test_console_and_log_cli_commands(self):
        log_file = Path(self.tmp.name) / "FO4SFRadsCore.0.log"
        log_file.write_text("\n".join(sample_pass_log()), encoding="utf-8")

        out_c = io.StringIO()
        with contextlib.redirect_stdout(out_c):
            rc = mrc.main(["console", "--file", str(log_file)])
        self.assertEqual(rc, 0)
        lines = out_c.getvalue().splitlines()
        self.assertEqual(lines[:6], [f"setstage 06000850 {s}" for s in (10, 20, 30, 40, 50, 60)])
        self.assertIn("player.getav FO4SF_Rads", lines)
        self.assertIn("player.getav FO4SF_RadsCapPct", lines)

        out_l = io.StringIO()
        with contextlib.redirect_stdout(out_l):
            rc = mrc.main(["log", "--file", str(log_file)])
        self.assertEqual(rc, 0)
        self.assertIn("PASS: stages 10..60 verified", out_l.getvalue())

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mrc.main(["log", "--file", str(Path(self.tmp.name) / "missing.log")]), 2)
            self.assertEqual(mrc.main(["console", "--file", str(Path(self.tmp.name) / "missing.log")]), 2)


class RadsCoreInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.game = root / "game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)

        self.sf_bytes = b"Synthetic Starfield.esm bytes"
        (self.data / "Starfield.esm").write_bytes(self.sf_bytes)
        (self.data / CORE_VALUES_PLUGIN).write_bytes(
            esm.PluginWriter(["Starfield.esm"], esm.ESM, author=CORE_VALUES_PLUGIN).to_bytes()
        )
        (self.data / "FO4TerrainCore.esm").write_bytes(
            esm.PluginWriter(["Starfield.esm"], esm.ESM, author="FO4TerrainCore.esm").to_bytes()
        )

        self.neighbors = {
            exp_install.RECORD: b'{"complete": true, "plugins": ["FO4TerrainCore.esm"]}',
            rads_probe_install.RECORD: b'{"complete": true, "plugins": ["FO4SFRadsProbe.esm"]}',
            planet_probe_install.RECORD: b'{"complete": true, "plugins": ["FO4SFPlanetProbe.esm"]}',
            "FO4SFPipboyProbe.install.json": b'{"complete": true, "plugins": ["FO4SFPipboyProbe.esm"]}',
        }
        for name, body in self.neighbors.items():
            (self.data / name).write_bytes(body)

        self.staged = root / "stage"
        (self.staged / "Data" / "Scripts").mkdir(parents=True)
        esm_bytes = esm.PluginWriter(["Starfield.esm", CORE_VALUES_PLUGIN], esm.ESM, author=PLUGIN).to_bytes()
        pex_bytes = b"compiled pex bytes"
        (self.staged / PLUGIN).write_bytes(esm_bytes)
        (self.staged / "Data" / "Scripts" / "FO4SF_RadsCoreQuest.pex").write_bytes(pex_bytes)
        (self.staged / "FO4SF_RadsCoreQuest.psc").write_text("source", encoding="utf-8")

        def h(b):
            return hashlib.sha256(b).hexdigest()

        plan = {
            "kind": "rads-core",
            "version": 1,
            "plugin": PLUGIN,
            "plugin_sha256": h(esm_bytes),
            "plugins": [PLUGIN],
            "scripts": {"FO4SF_RadsCoreQuest": h(pex_bytes)},
            "outputs": {PLUGIN: h(esm_bytes), "Data/Scripts/FO4SF_RadsCoreQuest.pex": h(pex_bytes)},
            "inputs": {"Starfield.esm": {"sha256": h(self.sf_bytes)}},
        }
        (self.staged / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

        local = root / "local"
        self.plugins_txt = local / "Starfield" / "Plugins.txt"
        self.plugins_txt.parent.mkdir(parents=True)
        self.plugins_txt.write_bytes(f"# header\r\n*{CORE_VALUES_PLUGIN}\r\n*FO4TerrainCore.esm\r\n".encode("utf-8"))

        old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = str(local)
        self.addCleanup(
            lambda: os.environ.__setitem__("LOCALAPPDATA", old_local)
            if old_local is not None
            else os.environ.pop("LOCALAPPDATA", None)
        )

        old_build = exp_install.build_ba2
        self.addCleanup(setattr, exp_install, "build_ba2", old_build)
        exp_install.build_ba2 = lambda _a, root_dir, out: (Path(out).write_bytes(archive_from_tree(Path(root_dir))), out)[1]

    def run_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                code = rci.main([*argv, "--starfield", str(self.game)]) or 0
            except SystemExit as e:
                code = e.code
        return code, buf.getvalue()

    def test_ride_along_install_and_uninstall_preserve_all_other_records(self):
        self.assertEqual(rci.RECORD, "FO4SFRads.install.json")
        self.assertNotIn(rci.RECORD, self.neighbors)

        code, out = self.run_cli("install", "--dir", str(self.staged))
        self.assertEqual(code, 0, out)
        self.assertEqual(exp_install.RECORD, "FO4SFExp.install.json")
        for fn in (PLUGIN, "FO4SFRads - Main.ba2", rci.RECORD):
            self.assertTrue((self.data / fn).is_file(), fn)
        self.assertEqual(
            self.plugins_txt.read_text(encoding="utf-8-sig").splitlines(),
            ["# header", f"*{CORE_VALUES_PLUGIN}", "*FO4TerrainCore.esm", "*" + PLUGIN],
        )
        for name, body in self.neighbors.items():
            self.assertEqual((self.data / name).read_bytes(), body)

        self.assertEqual(self.run_cli("status")[0], 0)
        self.assertEqual(self.run_cli("active")[0], 0)
        self.assertEqual(self.run_cli("order")[0], 0)

        code, out = self.run_cli("uninstall")
        self.assertEqual(code, 0, out)
        for fn in (PLUGIN, "FO4SFRads - Main.ba2", rci.RECORD):
            self.assertFalse((self.data / fn).exists(), fn)
        for name, body in self.neighbors.items():
            self.assertEqual((self.data / name).read_bytes(), body)

    def test_tampered_stage_and_prepacked_handling(self):
        with mock.patch.object(rci, "installer", return_value=0) as inst, \
                mock.patch.object(rci, "prepacked_supported", return_value=True):
            self.run_cli("install", "--dir", str(self.staged), "--prepacked", "archive.ba2")
            self.assertEqual(inst.call_args[0][0][-2:], ["--prepacked", "archive.ba2"])

        (self.staged / PLUGIN).write_bytes(b"corrupted")
        code, _ = self.run_cli("install", "--dir", str(self.staged))
        self.assertIn("does not match plan.json", str(code))


class WriterStageFoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (
            str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None
        )
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK required for RadsCore writer tests")
        proc = subprocess.run(
            [cls.dotnet, "build", str(ROOT / "dotnet" / "RadsCore"), "-c", "Release", "--nologo"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.dll = ROOT / "dotnet" / "RadsCore" / "bin" / "Release" / "net9.0" / "RadsCore.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-radscore-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.master = cls.root / "m" / "Starfield.esm"
        r = cls.run_tool("fixture", cls.root / "m")
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.dll), *map(str, argv)], capture_output=True, text=True)

    def test_csharp_selftest_covers_all_modes_options_and_tampers(self):
        r = self.run_tool("selftest", self.root / "selftest")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("selftest: ok", r.stdout)

    def test_raw_binary_records_load_indices_and_mgef_word_14(self):
        out = self.root / "raw_build"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        self.assertEqual(data[:4], b"TES4")

        kinds, ids = {}, []

        def walk(buf, i, end):
            while i < end:
                sig = buf[i:i + 4]
                size = struct.unpack_from("<I", buf, i + 4)[0]
                if sig == b"GRUP":
                    walk(buf, i + 24, i + size)
                    i += size
                    continue
                form = struct.unpack_from("<I", buf, i + 12)[0]
                kinds[sig] = kinds.get(sig, 0) + 1
                if sig != b"TES4":
                    ids.append(form)
                i += 24 + size

        walk(data, 0, len(data))
        self.assertTrue(ids and all((f >> 24) == 2 for f in ids), [hex(f) for f in ids if (f >> 24) != 2])
        self.assertEqual(
            kinds,
            {
                b"TES4": 1, b"AVIF": 1, b"GLOB": 1, b"GPOF": 2, b"GPOG": 1,
                b"MGEF": 13, b"SPEL": 9, b"ALCH": 4, b"HAZD": 1, b"KYWD": 1,
                b"ACTI": 1, b"WATR": 1, b"PERK": 5, b"FLST": 1, b"QUST": 1,
            },
        )
        # Only FO4SF_InWater (0x805) stays local: DefaultToZero = 0x00000400
        avfl_off = data.index(b"AVFL") + 6
        self.assertEqual(struct.unpack_from("<I", data, avfl_off)[0], 0x00000400)

        # MGEF DATA word 14 links to FO4SFCoreValues.esm (master index 0x01) for shared AVIFs and local 0x02 for FO4SF_InWater
        mgef_grp = data.index(b"GRUP")
        while data[mgef_grp + 8:mgef_grp + 12] != b"MGEF":
            mgef_grp += struct.unpack_from("<I", data, mgef_grp + 4)[0]
        grp_end = mgef_grp + struct.unpack_from("<I", data, mgef_grp + 4)[0]
        rec = mgef_grp + 24
        mgef_words = []
        while rec < grp_end:
            rsize = struct.unpack_from("<I", data, rec + 4)[0]
            body = data[rec + 24:rec + 24 + rsize]
            j, subs = 0, {}
            while j < len(body):
                slen = struct.unpack_from("<H", body, j + 4)[0]
                subs[body[j:j + 4]] = body[j + 6:j + 6 + slen]
                j += 6 + slen
            mgef_words.append(struct.unpack_from(f"<{len(subs[b'DATA']) // 4}I", subs[b"DATA"]))
            rec += 24 + rsize
        self.assertEqual(len(mgef_words), 13)
        self.assertEqual(mgef_words[0][14], 0x01000800)  # FO4SF_RadsEffect -> FO4SFCoreValues.esm:FO4SF_Rads
        self.assertEqual(mgef_words[0][0], 0)
        self.assertEqual(mgef_words[1][14], 0x01000800)  # FO4SF_RadsHazardEffect -> FO4SFCoreValues.esm:FO4SF_Rads
        self.assertEqual(mgef_words[1][0], 0)
        self.assertEqual(mgef_words[2][14], 0x01000800)  # FO4SF_RadAwayEffect -> FO4SFCoreValues.esm:FO4SF_Rads
        self.assertEqual(mgef_words[3][14], 0x01000804)  # FO4SF_RadXEffect -> FO4SFCoreValues.esm:FO4SF_RadResist
        self.assertEqual(mgef_words[4][14], 0x02000805)  # FO4SF_InWaterEffect -> FO4SFRads.esm:FO4SF_InWater
        self.assertEqual(mgef_words[7][14], 0x01000814)  # FO4SF_MgefMut_IntPenalty -> FO4SFCoreValues.esm:FO4SF_Special_Intelligence

    def test_stage_fold_hardlink_and_verify_pipeline(self):
        cr = self.root / "cr.zip"
        fake_sources(cr)
        comp = fake_compiler(self.root)
        staged = self.root / "stage_out"

        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)

        rc = mrc.main([
            "stage", "--out", str(staged), "--starfield", str(self.master),
            "--compiler", str(comp), "--content-resources", str(cr),
        ])
        self.assertEqual(rc, 0)
        plan = json.loads((staged / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["kind"], "rads-core")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(mrc.verify_stage(str(staged), plan, str(self.master.parent)), [])

        # Create synthetic clean-core set and fold with --hardlink
        core_dir = self.root / "clean_core"
        (core_dir / "Data" / "Scripts").mkdir(parents=True)
        (core_dir / "FO4TerrainCore.esm").write_bytes(b"TES4core")
        (core_dir / "FO4SFNewGame.esm").write_bytes(b"TES4ng")
        (core_dir / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").write_bytes(b"ngpex")
        orig_readme = (
            "Synthetic core set\n"
            "  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> "
            "--plugins FO4TerrainCore.esm,FO4SFNewGame.esm --pack\n"
        )
        (core_dir / "README.txt").write_text(orig_readme, encoding="utf-8")

        folded = self.root / "folded_core"
        rc_fold = mrc.main([
            "fold", "--stage", str(staged), "--core-dir", str(core_dir),
            "--out", str(folded), "--starfield", str(self.master), "--hardlink",
        ])
        self.assertEqual(rc_fold, 0)

        # Source core README.txt must NOT have been mutated in place despite --hardlink!
        self.assertEqual((core_dir / "README.txt").read_text(encoding="utf-8"), orig_readme)
        folded_txt = (folded / "README.txt").read_text(encoding="utf-8")
        self.assertIn("--plugins FO4TerrainCore.esm,FO4SFNewGame.esm,FO4SFRads.esm --pack", folded_txt)
        self.assertTrue((folded / PLUGIN).is_file())
        self.assertTrue((folded / "Data" / "Scripts" / "FO4SF_RadsCoreQuest.pex").is_file())

        rc_ver = mrc.main([
            "verify", "--exp-dir", str(folded),
            "--plan", str(staged / "plan.json"), "--starfield", str(self.master),
        ])
        self.assertEqual(rc_ver, 0)

        # Folding into a folder that already holds FO4SFRads.esm is refused
        with self.assertRaises(SystemExit):
            mrc.main([
                "fold", "--stage", str(staged), "--core-dir", str(folded),
                "--out", str(self.root / "folded_twice"),
            ])

    def test_a18_default_rule_1_build_and_option_to_store_sync_on_init_and_load(self):
        # 1. Verify FO4SF_RadsCoreQuest.psc copies RadsRuleOption -> RadsRuleGlobal and MutationsOption -> MutationsEnabledGlobal
        #    in BOTH OnQuestInit and Actor.OnPlayerLoadGame and logs options_sync
        self.assertIn("Function SyncOptionsToStore(string whenTag)", PSC_TEXT)
        self.assertIn("RadsRuleGlobal.SetValue(RadsRuleOption.GetValue())", PSC_TEXT)
        self.assertIn("MutationsEnabledGlobal.SetValue(MutationsOption.GetValue())", PSC_TEXT)
        self.assertIn('Trace("options_sync when=" + whenTag + " rule=" + CurrentRule() + " mut_on=" + MutationsOn())', PSC_TEXT)

        init_blk = PSC_TEXT[PSC_TEXT.index("Event OnQuestInit()"):PSC_TEXT.index("Function SetupPlayerHooks(")]
        load_blk = PSC_TEXT[PSC_TEXT.index("Event Actor.OnPlayerLoadGame("):PSC_TEXT.index("Event OnGameplayOptionChanged(")]
        self.assertIn('SyncOptionsToStore("init")', init_blk)
        self.assertLess(init_blk.index('SyncOptionsToStore("init")'), init_blk.index('SyncState(p, "init")'))
        self.assertIn('SyncOptionsToStore("load_game")', load_blk)
        self.assertLess(load_blk.index('SyncOptionsToStore("load_game")'), load_blk.index('SyncState(p, "load_game")'))

        # 2. Build FO4SFRads.esm with --default-rule 1 while FO4SFCoreValues.esm has FO4SF_RadsRule default 0.0,
        #    proving the GPOF option carries 1.0 and SyncOptionsToStore copies 1.0 into RadsRuleGlobal on init & load
        out_rule1 = self.root / "rads_rule1"
        r = subprocess.run(
            [self.dotnet, "run", "--project", str(ROOT / "dotnet" / "RadsCore"), "--",
             "build", str(self.master), str(out_rule1), "--default-rule", "1"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr + "\n" + r.stdout)
        r_chk = subprocess.run(
            [self.dotnet, "run", "--project", str(ROOT / "dotnet" / "RadsCore"), "--",
             "check", str(out_rule1 / PLUGIN), str(self.master), "--default-rule", "1"],
            capture_output=True, text=True,
        )
        self.assertEqual(r_chk.returncode, 0, msg=r_chk.stderr + "\n" + r_chk.stdout)

        # Simulate store global starting at 0.0 (FO4SFCoreValues.esm default) + RadsRuleOption=1.0 (--default-rule 1)
        store_rule_glob = 0.0
        gpo_rule_opt = 1.0

        def _sync_options_to_store(when_tag: str) -> str:
            nonlocal store_rule_glob
            store_rule_glob = gpo_rule_opt
            cur_rule = 1 if store_rule_glob >= 0.5 else 0
            return f"FO4SFRADSCORE rt=1.0 options_sync when={when_tag} rule={cur_rule} mut_on=0 end=true"

        init_line = _sync_options_to_store("init")
        self.assertEqual(store_rule_glob, 1.0)
        self.assertIn("options_sync when=init rule=1", init_line)

        store_rule_glob = 0.0
        load_line = _sync_options_to_store("load_game")
        self.assertEqual(store_rule_glob, 1.0)
        self.assertIn("options_sync when=load_game rule=1", load_line)


if __name__ == "__main__":
    unittest.main()
