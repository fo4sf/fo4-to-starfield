"""Combined-core probe judges (probes.py) on synthetic outputs only: hand-written FOCC trace lines, SFSE JSON lines,
sidecar bodies and saves.json. Nothing here comes from a game; every PASS / FAIL / INCONCLUSIVE branch of each checker
is exercised, empty input is never a PASS, and the P1 sidecar name/hash rule mirrors sidecar.py."""
import contextlib
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import probes, sidecar  # noqa: E402
from fo4sf.combined.probes import PASS, FAIL, INCONCLUSIVE, Collection  # noqa: E402

INIT = "FOCC init variant=default"
RUNTIME_LOC = "50331649"       # a form id as Papyrus prints it (decimal); FF.. ids come out negative
P2_LOC, P3_NOPARENT, P3_CHAINED = (str(0x03000000 | n) for n in (2054, 2055, 2056))   # the probe LCTNs at load index 03


def col(**logs):
    """Collection from lists of lines keyed by log name (session1=..., session2=..., log=focc.0.log)."""
    names = {"session1": "focc_session1.log", "session2": "focc_session2.log", "log": "focc.0.log"}
    c = Collection()
    for k, lines in logs.items():
        c.logs[names.get(k, k)] = list(lines)
    return c


def saves(**sizes):
    return [{"Name": f"{k}.sfs", "Length": v} for k, v in sizes.items()]


class ParseTests(unittest.TestCase):
    def test_trace_line_shapes(self):
        e = probes.parse_line("[21:29:40] FOCC rt=12.345 p2 set loc=50331649 local=2054 value=37.000000 readback=37.000000")
        self.assertEqual((e.kind, e.rt), ("p2 set", 12.345))
        self.assertEqual(e.form("loc"), "03000001")
        self.assertEqual(e.num("local"), 2054)
        self.assertTrue(probes._close(e.num("value"), 37.0))
        e = probes.parse_line("FOCC init variant=p3cells")
        self.assertEqual((e.kind, e.rt, e.fields), ("init", None, {"variant": "p3cells"}))
        e = probes.parse_line("FOCC rt=3.5 p9 sample t=2.000000 actor=-16702651 pos=1.000000 2.500000 -3.000000 cell=none loaded=True dist=450.5")
        self.assertEqual(probes.pos(e), [1.0, 2.5, -3.0])
        self.assertEqual(e.form("actor"), "FF012345")
        self.assertIsNone(e.form("cell"))
        self.assertIs(e.flag("loaded"), True)
        self.assertEqual(probes.parse_line("FOCC p10 quest started id=-16702651 local=2080").kind, "p10 quest started")

    def test_non_focc_lines_are_ignored(self):
        for s in ("", "FO4SF rt=1.0 pos=1 2 3", "warning: Papyrus something", "FOCC", "[x] FOCCX p2 set a=1"):
            self.assertIsNone(probes.parse_line(s), s)
        evs = probes.parse_log(["junk", INIT, "torn FOCC", "FOCC p5 start ticks=10"], "f")
        self.assertEqual([(e.line, e.kind) for e in evs], [(2, "init"), (4, "p5 start")])

    def test_id_conversions(self):
        self.assertEqual(probes.hex2dec("FF012345"), -16702651)
        self.assertEqual(probes.hex2dec("0x03000001"), 50331649)
        self.assertEqual(probes.dec2hex(-16702651), "FF012345")
        self.assertEqual(probes.dec2hex("50331649"), "03000001")
        self.assertEqual(probes.hex2dec(probes.dec2hex(-1)), -1)

    def test_saves_json_shapes(self):
        one = json.dumps({"Name": "a.sfs", "Length": 5})
        many = json.dumps([{"Name": "a.sfs", "Length": 5}, {"Name": "b.sfs", "Length": 7}])
        self.assertEqual(probes.save_sizes(probes.load_saves(one)), {"a": 5})
        self.assertEqual(probes.save_sizes(probes.load_saves("﻿" + many)), {"a": 5, "b": 7})
        self.assertIsNone(probes.load_saves("not json"))
        self.assertIsNone(probes.load_saves("[1, 2]"))


class EmptyInputTests(unittest.TestCase):
    def test_nothing_is_never_pass(self):
        for p in probes.PROBES:
            v = probes.check(p, Collection())
            self.assertEqual(v.verdict, INCONCLUSIVE, p)
            self.assertTrue(v.reasons, p)
        for p in probes.PROBES:
            v = probes.check(p, col(log=[INIT], session1=[INIT], session2=[INIT]))
            self.assertEqual(v.verdict, INCONCLUSIVE, p)
        self.assertEqual(probes.check_all(Collection())["verdict"], INCONCLUSIVE)


# ----------------------------------------------------------------------------------------------- P1

def stub_sidecar(name, counter, tamper=None):
    ws = {"probe": "P1", "counter": counter}
    state = json.dumps(ws, sort_keys=True)
    body = {"format": sidecar.FORMAT, "schema": sidecar.SCHEMA, "save_name": name, "world_state": ws,
            "sha256": sidecar.checksum(state)}
    if tamper:
        body.update(tamper)
    return json.dumps(body, sort_keys=True)


def p1_collection(delete="focc_p1_b", sidecar_names=None, extra_sfse=(), saves_json=True, loads=True):
    log = [json.dumps({"event": "pre_save", "save": "focc_p1_a", "counter": 1, "written": True}),
           json.dumps({"event": "post_save", "save": "focc_p1_a"}),
           json.dumps({"event": "pre_load", "save": "Autosave1"}),
           json.dumps({"event": "post_load", "save": "Autosave1", "found": False, "valid": False}),
           json.dumps({"event": "pre_save", "save": "focc_p1_b", "counter": 2, "written": True}),
           json.dumps({"event": "post_save", "save": "focc_p1_b"})]
    if loads:
        log.append(json.dumps({"event": "post_load", "save": "focc_p1_a", "found": True, "valid": True, "counter": 1}))
    log.extend(extra_sfse)
    c = Collection(sfse_log=log, sidecars={})
    for name, k in (("focc_p1_a", 1), ("focc_p1_b", 2)):
        fn = (sidecar_names or {}).get(name, sidecar.sidecar_name(name))
        c.sidecars[fn] = stub_sidecar(name, k)
    if saves_json:
        names = {"Autosave1": 100, "focc_p1_a": 100, "focc_p1_b": 100}
        names.pop(delete, None)
        c.saves = saves(**names)
    return c


class P1Tests(unittest.TestCase):
    def test_pass_with_exact_orphan(self):
        v = probes.check_p1(p1_collection())
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertEqual(v.extra["orphans"], [sidecar.sidecar_name("focc_p1_b")])
        self.assertEqual(v.extra["deleted_saves"], ["focc_p1_b"])
        self.assertTrue(all(e["file"] == "sfse/focc_sidecar.log" and e["line"] for e in v.evidence))

    def test_name_rule_mismatch_fails(self):
        v = probes.check_p1(p1_collection(sidecar_names={"focc_p1_a": "focc_p1_a-deadbeef.focc"}))
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("no sidecar" in r for r in v.reasons))

    def test_tampered_body_fails(self):
        c = p1_collection()
        fn = sidecar.sidecar_name("focc_p1_a")
        c.sidecars[fn] = stub_sidecar("focc_p1_a", 1, tamper={"world_state": {"probe": "P1", "counter": 9}})
        self.assertEqual(probes.check_p1(c).verdict, FAIL)
        c.sidecars[fn] = stub_sidecar("focc_p1_a", 1, tamper={"schema": 2})
        self.assertEqual(probes.check_p1(c).verdict, FAIL)
        c.sidecars[fn] = stub_sidecar("focc_p1_a", 7)        # valid body, wrong counter for the pre_save
        self.assertEqual(probes.check_p1(c).verdict, FAIL)

    def test_a_failed_write_fails_even_with_an_old_sidecar_present(self):
        # Codex review of #431: written=false leaves an older sidecar (same name, counter 1) that would read back
        for written in (False, None):
            c = p1_collection()
            c.sfse_log = [l.replace('"written": true', f'"written": {json.dumps(written)}') if "focc_p1_a" in l else l
                          for l in c.sfse_log]
            v = probes.check_p1(c)
            self.assertEqual(v.verdict, FAIL, written)
            self.assertTrue(any("was not written" in r for r in v.reasons), v.reasons)

    def test_post_load_not_found_fails(self):
        c = p1_collection(loads=False, extra_sfse=[json.dumps({"event": "post_load", "save": "focc_p1_a",
                                                                "found": False, "valid": False})])
        v = probes.check_p1(c)
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("found=False" in r for r in v.reasons))

    def test_no_post_load_of_a_saved_name_is_not_a_pass(self):
        # the only post_load is the Autosave's (found=false): sidecars were written but never read back
        v = probes.check_p1(p1_collection(loads=False))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("read-back half was not exercised" in r for r in v.reasons), v.reasons)

    def test_an_older_attempts_load_does_not_count(self):
        # Codex P1 on #431: the log spans launches; a read-back before the latest pre_save is not this attempt's.
        c = p1_collection(loads=False)
        old = json.dumps({"event": "post_load", "save": "focc_p1_a", "found": True, "valid": True, "counter": 1})
        c.sfse_log = [old] + c.sfse_log
        v = probes.check_p1(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("read-back half was not exercised" in r for r in v.reasons), v.reasons)

    def test_inconclusive_branches(self):
        self.assertEqual(probes.check_p1(Collection()).verdict, INCONCLUSIVE)                      # no log
        self.assertEqual(probes.check_p1(Collection(sfse_log=["not json"])).verdict, INCONCLUSIVE)
        c = p1_collection(loads=False)
        c.sfse_log = [l for l in c.sfse_log if "post_load" not in l]                             # plugin never loaded a save
        self.assertEqual(probes.check_p1(c).verdict, INCONCLUSIVE)
        v = probes.check_p1(p1_collection(saves_json=False))                                      # orphan question open
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("orphan" in r for r in v.reasons))
        c = p1_collection()
        c.saves = saves(Save1=1, Save2=2)                                                        # names do not match stems
        v = probes.check_p1(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("unverified" in r for r in v.reasons))
        c = p1_collection()
        c.sidecars = None
        self.assertEqual(probes.check_p1(c).verdict, INCONCLUSIVE)

    def test_wrong_orphans_fail(self):
        c = p1_collection()
        c.sidecars["stale-00000000.focc"] = "{}"
        v = probes.check_p1(c)
        self.assertEqual(v.verdict, FAIL)
        self.assertIn("stale-00000000.focc", v.extra["orphans"])

    def test_sidecar_rule_mirror(self):
        names = ["focc_p1_a", "Quick Save", "a/b"]
        with tempfile.TemporaryDirectory() as d:
            for n in names:
                with open(os.path.join(d, sidecar.sidecar_name(n)), "w") as f:
                    f.write(stub_sidecar(n, 1))
            self.assertEqual(probes.orphans(os.listdir(d), names), [])
            self.assertEqual(probes.orphans(os.listdir(d), names[:1]),
                             [os.path.basename(p) for p in sidecar.orphans(d, names[:1])])
        self.assertEqual(probes.decode_stub_sidecar(stub_sidecar("x", 3), "x"), {"probe": "P1", "counter": 3})
        with self.assertRaises(ValueError):
            probes.decode_stub_sidecar(stub_sidecar("x", 3), "y")
        with self.assertRaises(ValueError):
            probes.decode_stub_sidecar("{]")


# ----------------------------------------------------------------------------------------------- P2

S1_P2 = [INIT, f"FOCC rt=5.0 p2 set loc={P2_LOC} local=2054 value=37.000000 readback=37.000000",
         f"FOCC rt=5.1 p2 link a={P2_LOC} b={P3_CHAINED} linked=True"]
S2_P2 = ["FOCC init variant=default", f"FOCC rt=4.0 p2 read loc={P2_LOC} local=2054 value=37.000000",
         f"FOCC rt=4.1 p2 linkread a={P2_LOC} b={P3_CHAINED} linked=True"]


class P2Tests(unittest.TestCase):
    def test_pass(self):
        v = probes.check_p2(col(session1=S1_P2, session2=S2_P2))
        self.assertEqual(v.verdict, PASS, v.reasons)
        files = {e["file"] for e in v.evidence}
        self.assertEqual(files, {"focc_session1.log", "focc_session2.log"})
        self.assertIn({"file": "focc_session2.log", "line": 2, "text": S2_P2[1]}, v.evidence)

    def test_one_session_is_never_pass(self):
        self.assertEqual(probes.check_p2(col(session1=S1_P2)).verdict, INCONCLUSIVE)
        one = S1_P2 + S2_P2[1:]
        v = probes.check_p2(col(session1=one, session2=one))                      # the same log copied twice
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("identical" in r for r in v.reasons), v.reasons)
        v = probes.check_p2(col(session1=S1_P2, session2=[INIT] + S1_P2[1:] + S2_P2[1:]))   # set, then read, one launch
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("same launch" in r for r in v.reasons), v.reasons)
        self.assertEqual(probes.check_p2(col(session1=S1_P2 + S2_P2[1:])).verdict, INCONCLUSIVE)   # read in the same session
        self.assertEqual(probes.check_p2(col(session1=S1_P2, session2=S2_P2[1:])).verdict, INCONCLUSIVE)  # no init: no relaunch proven

    def test_fail_branches(self):
        lost = [f"FOCC init", f"FOCC rt=4.0 p2 read loc={P2_LOC} local=2054 value=0.000000", f"FOCC rt=4.1 p2 linkread a={P2_LOC} b={P3_CHAINED} linked=True"]
        v = probes.check_p2(col(session1=S1_P2, session2=lost))
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("did not persist" in r for r in v.reasons))
        unlinked = S2_P2[:2] + [f"FOCC p2 linkread a={P2_LOC} b={P3_CHAINED} linked=False"]
        self.assertEqual(probes.check_p2(col(session1=S1_P2, session2=unlinked)).verdict, FAIL)
        bad_set = [INIT, f"FOCC p2 set loc={P2_LOC} local=2054 value=37.000000 readback=0.000000"]
        self.assertEqual(probes.check_p2(col(session1=bad_set, session2=S2_P2)).verdict, FAIL)
        nolink = S1_P2[:2] + [f"FOCC p2 link a={P2_LOC} b={P3_CHAINED} linked=False"]
        self.assertEqual(probes.check_p2(col(session1=nolink, session2=S2_P2)).verdict, FAIL)

    def test_inconclusive_branches(self):
        self.assertEqual(probes.check_p2(col(session1=[INIT, "FOCC p2 refused prop=P2Loc"], session2=S2_P2)).verdict,
                         INCONCLUSIVE)
        no_rb = [INIT, f"FOCC p2 set loc={P2_LOC} local=2054 value=37.000000"]
        self.assertEqual(probes.check_p2(col(session1=no_rb, session2=S2_P2)).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p2(col(session1=S1_P2, session2=["FOCC init"])).verdict, INCONCLUSIVE)
        v = probes.check_p2(col(session1=S1_P2, session2=S2_P2[:2]))     # link set, no linkread
        self.assertEqual(v.verdict, INCONCLUSIVE)

    def test_a_relink_in_the_second_launch_is_not_persistence(self):
        # Codex review of #431: P2Link again before P2LinkRead measures a fresh link, not a persisted one.
        relinked = S2_P2[:2] + [S1_P2[2], S2_P2[2]]
        v = probes.check_p2(col(session1=S1_P2, session2=relinked))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("same launch" in r for r in v.reasons), v.reasons)

    def test_other_locations_are_not_judged(self):
        # Codex review of #431: the literal local=2054 proves nothing; the logged form ids must be the probe LCTNs.
        other = [INIT, f"FOCC p2 set loc={RUNTIME_LOC} local=2054 value=37.000000 readback=37.000000"] + S1_P2[2:]
        self.assertEqual(probes.check_p2(col(session1=other, session2=S2_P2)).verdict, INCONCLUSIVE)
        read_other = [S2_P2[0], f"FOCC p2 read loc={RUNTIME_LOC} local=2054 value=37.000000"] + S2_P2[2:]
        self.assertEqual(probes.check_p2(col(session1=S1_P2, session2=read_other)).verdict, INCONCLUSIVE)
        link_other = S1_P2[:2] + [f"FOCC p2 link a={P2_LOC} b={P3_NOPARENT} linked=True"]
        self.assertEqual(probes.check_p2(col(session1=link_other, session2=S2_P2)).verdict, INCONCLUSIVE)
        linkread_other = S2_P2[:2] + [f"FOCC p2 linkread a={P3_CHAINED} b={P2_LOC} linked=True"]
        self.assertEqual(probes.check_p2(col(session1=S1_P2, session2=linkread_other)).verdict, INCONCLUSIVE)
        # A light plugin's ids print negative (FE + 12-bit slot + 12-bit local) and still name the probe LCTNs.
        light = {k: str((0xFE001000 | n) - (1 << 32)) for k, n in ((P2_LOC, 2054), (P3_CHAINED, 2056))}
        fe1, fe2 = ([ln.replace(P2_LOC, light[P2_LOC]).replace(P3_CHAINED, light[P3_CHAINED]) for ln in ss]
                    for ss in (S1_P2, S2_P2))
        self.assertEqual(probes.check_p2(col(session1=fe1, session2=fe2)).verdict, PASS)
        slot = str(0xFE003806 - (1 << 32))      # light slot 003 never leaks into the local
        self.assertEqual(probes._local(probes.parse_line(f"FOCC p2 set loc={slot}"), "loc"), 2054)

    def test_keyword_half_alone_is_inconclusive(self):
        v = probes.check_p2(col(session1=S1_P2[:2], session2=S2_P2[:2]))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertEqual(v.extra["linked_locations"], "not run")


# ----------------------------------------------------------------------------------------------- P3

S1_P3 = [INIT, f"FOCC rt=6.0 p3 set a={P3_NOPARENT} va=5.000000 ra=5.000000 b={P3_CHAINED} vb=6.000000 rb=6.000000"]
S2_P3 = ["FOCC init", f"FOCC rt=4.0 p3 read a={P3_NOPARENT} ra=5.000000 b={P3_CHAINED} rb=6.000000"]
CELLS = ["FOCC init variant=p3cells",
         f"FOCC rt=9.0 where cell=50333000 cellname=FO4Port_RedRocket01 loc={P3_NOPARENT} local=2055",
         f"FOCC rt=19.0 where cell=50333001 cellname=FO4Port_SuperDuperMart01 loc={P3_CHAINED} local=2056"]


class P3Tests(unittest.TestCase):
    def test_keyword_half_needs_a_relaunch(self):
        one = S1_P3 + S2_P3[1:]
        v = probes.check_p3(col(session1=one, session2=one))
        self.assertEqual((v.verdict, v.extra["keyword_half"]), (INCONCLUSIVE, INCONCLUSIVE))
        v = probes.check_p3(col(session1=S1_P3, session2=[INIT] + S1_P3[1:] + S2_P3[1:]))
        self.assertEqual((v.verdict, v.extra["keyword_half"]), (INCONCLUSIVE, INCONCLUSIVE))
        self.assertTrue(any("same launch" in r for r in v.reasons), v.reasons)

    def test_keyword_half(self):
        v = probes.check_p3(col(session1=S1_P3, session2=S2_P3))
        self.assertEqual((v.verdict, v.extra["keyword_half"]), (PASS, PASS))
        self.assertEqual(v.extra["explored_state"]["status"], "unresolved")
        self.assertNotIn("cell_half", v.extra)
        half = ["FOCC init", f"FOCC p3 read a={P3_NOPARENT} ra=0.000000 b={P3_CHAINED} rb=6.000000"]      # unparented one lost its datum
        self.assertEqual(probes.check_p3(col(session1=S1_P3, session2=half)).verdict, FAIL)
        self.assertEqual(probes.check_p3(col(session1=S1_P3)).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p3(col(session1=S1_P3, session2=S2_P3[1:])).verdict, INCONCLUSIVE)
        bad = [INIT, f"FOCC p3 set a={P3_NOPARENT} va=5.000000 ra=0.000000 b={P3_CHAINED} vb=6.000000 rb=6.000000"]
        self.assertEqual(probes.check_p3(col(session1=bad, session2=S2_P3)).verdict, FAIL)

    def test_keyword_half_checks_both_locations(self):
        # Codex review of #431: swapped or foreign a/b ids never pass the keyword half.
        swapped = [INIT, f"FOCC p3 set a={P3_CHAINED} va=5.000000 ra=5.000000 b={P3_NOPARENT} vb=6.000000 rb=6.000000"]
        v = probes.check_p3(col(session1=swapped, session2=S2_P3))
        self.assertEqual((v.verdict, v.extra["keyword_half"]), (INCONCLUSIVE, INCONCLUSIVE))
        for read in ("FOCC p3 read ra=5.000000 rb=6.000000",                  # the old shape: no identities
                     "FOCC p3 read a=50331649 ra=5.000000 b=50331650 rb=6.000000",
                     f"FOCC p3 read a={P3_CHAINED} ra=5.000000 b={P3_NOPARENT} rb=6.000000"):
            v = probes.check_p3(col(session1=S1_P3, session2=["FOCC init", read]))
            self.assertEqual((v.verdict, v.extra["keyword_half"]), (INCONCLUSIVE, INCONCLUSIVE), read)
        foreign = [INIT, f"FOCC p3 set a={RUNTIME_LOC} va=5.000000 ra=5.000000 b={P3_CHAINED} vb=6.000000 rb=6.000000"]
        self.assertEqual(probes.check_p3(col(session1=foreign, session2=S2_P3)).verdict, INCONCLUSIVE)

    def test_cell_half(self):
        v = probes.check_p3(col(log=CELLS))
        self.assertEqual((v.verdict, v.extra["cell_half"]), (PASS, PASS))
        wrong = CELLS[:2] + ["FOCC where cell=50333001 cellname=FO4Port_SuperDuperMart01 loc=none local=none"]
        self.assertEqual(probes.check_p3(col(log=wrong)).verdict, FAIL)
        other = CELLS[:2] + ["FOCC where cell=50333001 cellname=FO4Port_SuperDuperMart01 loc=16779266 local=2055"]
        self.assertEqual(probes.check_p3(col(log=other)).verdict, FAIL)
        self.assertEqual(probes.check_p3(col(log=CELLS[:2])).verdict, INCONCLUSIVE)
        labelled = [CELLS[0], "FOCC where cell=1 cellname=FO4Port_RedRocket01 loc=1 local=2055",
                    "FOCC where cell=2 cellname=FO4Port_SuperDuperMart01 loc=2 local=2056"]
        self.assertEqual(probes.check_p3(col(log=labelled)).verdict, FAIL)    # the label alone never passes
        self.assertEqual(probes.check_p3(col(log=[INIT] + CELLS[1:])).verdict, INCONCLUSIVE)   # default variant: no cell half

    def test_cell_half_retry_does_not_borrow_the_older_second_cell(self):
        # Codex P1 on #431: a retry interrupted after the new Red Rocket `where` stays inconclusive.
        v = probes.check_p3(col(log=CELLS + [CELLS[1]]))
        self.assertEqual(v.extra["cell_half"], INCONCLUSIVE)

    def test_both_halves_worst_wins(self):
        c = col(session1=S1_P3, session2=S2_P3, log=CELLS[:2])
        v = probes.check_p3(c)
        self.assertEqual((v.extra["keyword_half"], v.extra["cell_half"], v.verdict), (PASS, INCONCLUSIVE, INCONCLUSIVE))


# ----------------------------------------------------------------------------------------------- P4

def p4_log(cycles=20, loaded=3, short_at=None, mode="placeatme"):
    lines = [INIT, f"FOCC rt=0.5 p4 start cycles={cycles} settle=8.0 marker={0x0300080B} pos=0 0 0 mode=placeatme"]
    for n in range(1, cycles + 1):
        placed = 2 if short_at == n else 3
        lines.append(f"FOCC rt={n * 8.5:.1f} p4 cycle n={n} placed={placed} loaded={loaded} deleted=3 mode={mode}")
    lines.append(f"FOCC rt=200.0 p4 done cycles={cycles} placed={cycles * 3} deleted={cycles * 3}")
    return lines


class P4Tests(unittest.TestCase):
    def test_a_start_line_is_required(self):
        # Codex review of #431: cycles without a `p4 start` are not tied to one run.
        c = col(log=[l for l in p4_log() if " p4 start " not in l])
        c.saves = saves(focc_p4_before=1, focc_p4_after=1)
        self.assertEqual(probes.check_p4(c).verdict, INCONCLUSIVE)

    def test_another_marker_is_not_judged(self):
        # Codex review of #431: the logged marker must be FOCC_P4_SpawnMarker.
        log = [l.replace(f"marker={0x0300080B}", "marker=1") for l in p4_log()]
        c = col(log=log)
        c.saves = saves(focc_p4_before=1, focc_p4_after=1)
        self.assertEqual(probes.check_p4(c).verdict, INCONCLUSIVE)

    def test_only_the_latest_run_counts(self):
        # Codex P1 on #431: an older complete run must not fill the gaps of the latest one.
        partial = [l for l in p4_log() if " n=7 " not in l]
        c = col(log=p4_log() + partial[1:])
        c.saves = saves(focc_p4_before=1, focc_p4_after=1)
        v = probes.check_p4(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("cycles missing: [7]" in r for r in v.reasons), v.reasons)

    def test_pass_and_growth_record(self):
        v = probes.check_p4(col(log=p4_log()))
        self.assertEqual(v.verdict, INCONCLUSIVE)                        # no saves.json
        c = col(log=p4_log())
        c.saves = saves(focc_p4_before=10_000_000, focc_p4_after=10_300_000)
        v = probes.check_p4(c)
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertEqual(v.extra["save_growth"]["growth"], 300_000)
        self.assertIn("bound_placeholder", v.extra["save_growth"])
        self.assertEqual(v.extra["modes"], ["placeatme"])
        c.logs["focc.0.log"] = p4_log(mode="alias")
        self.assertEqual(probes.check_p4(c).verdict, PASS)

    def test_fail_branches(self):
        c = col(log=p4_log(short_at=7))
        c.saves = saves(focc_p4_before=10_000_000, focc_p4_after=10_000_000)
        v = probes.check_p4(c)
        self.assertEqual(v.verdict, FAIL)
        self.assertIn("7", v.reasons[0])
        c = col(log=p4_log())
        c.saves = saves(focc_p4_before=10_000_000, focc_p4_after=13_000_000)       # 3 MB > max(2 MB, 5 %)
        v = probes.check_p4(c)
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("placeholder" in r for r in v.reasons))

    def test_fewer_than_twenty_cycles_is_not_the_bloat_answer(self):
        c = col(log=p4_log(cycles=3))
        c.saves = saves(focc_p4_before=10_000_000, focc_p4_after=10_000_000)
        v = probes.check_p4(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("only 3 cycles" in r for r in v.reasons), v.reasons)
        self.assertEqual(probes.P4_CYCLES, 20)

    def test_inconclusive_branches(self):
        c = col(log=p4_log()[:-1])                                       # no done line
        c.saves = saves(focc_p4_before=1, focc_p4_after=1)
        self.assertEqual(probes.check_p4(c).verdict, INCONCLUSIVE)
        c = col(log=p4_log(loaded=0))
        c.saves = saves(focc_p4_before=1, focc_p4_after=1)
        v = probes.check_p4(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("never loaded" in r for r in v.reasons))
        c = col(log=p4_log())
        c.saves = saves(focc_p4_before=1)
        self.assertEqual(probes.check_p4(c).verdict, INCONCLUSIVE)
        lines = p4_log()
        del lines[5]                                                     # a missing cycle
        self.assertEqual(probes.check_p4(col(log=lines)).verdict, INCONCLUSIVE)


# ----------------------------------------------------------------------------------------------- P5

def p5_log(ticks=10, ms=(3.1, 2.9, 3.4, 3.0, 2.8, 3.3, 3.1, 2.7, 3.2, 3.0)):
    lines = [INIT, f"FOCC rt=1.0 p5 start ticks={ticks}"]
    for i in range(ticks):
        lines.append(f"FOCC rt={2 + i:.1f} p5 tick n={i + 1} places=50 ms={ms[i % len(ms)]:.6f} sum=123.456000")
    lines.append(f"FOCC rt={2 + ticks:.1f} p5 done ticks={ticks}")
    return lines


class P5Tests(unittest.TestCase):
    def test_a_cut_log_without_done_is_inconclusive(self):
        # Codex review of #431: ten good ticks without `p5 done` may be a truncated copy.
        self.assertEqual(probes.check_p5(col(log=p5_log()[:-1])).verdict, INCONCLUSIVE)

    def test_done_must_follow_the_ticks(self):
        # Codex review of #431: a done line ahead of the ticks closes the run; ticks after it never count
        log = p5_log()
        self.assertEqual(probes.check_p5(col(log=log[:2] + [log[-1]] + log[2:-1])).verdict, INCONCLUSIVE)

    def test_repeated_ticks_do_not_count(self):
        log = p5_log()
        self.assertEqual(probes.check_p5(col(log=log[:3] + [log[2]] * 9)).verdict, INCONCLUSIVE)

    def test_pass_records_baseline_and_cap(self):
        c = col(log=p5_log())
        c.files["compile_p5_array129.txt"] = "FOCC_P5_Array129.psc(3,9): array size 129 exceeds maximum of 128\nNo output generated"
        v = probes.check_p5(c)
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertEqual(v.extra["array_cap"], 128)
        self.assertEqual(v.extra["baseline_ms"]["ticks"], 10)
        self.assertAlmostEqual(v.extra["baseline_ms"]["median"], 3.05)
        self.assertAlmostEqual(v.extra["baseline_ms"]["per_place_median"], 3.05 / 50)
        c.files["compile_p5_array129.txt"] = "Starting 1 compile threads\nCompilation succeeded."
        self.assertIsNone(probes.check_p5(c).extra["array_cap"])
        del c.files["compile_p5_array129.txt"]
        self.assertEqual(probes.check_p5(c).extra["array_cap"], "unknown")

    def test_array_cap_needs_the_compiler_to_name_the_array(self):
        staged = ("FOCC_P5_Array129.psc: new float[129] (compile-only, never packed)\nexit code 1\n"
                  "Starting 1 compile threads for 1 files...\nFOCC_P5_Array129.psc(8,15): arrays cannot have more than "
                  "128 elements\nNo output generated for FOCC_P5_Array129\n\nrefused: the compiler did not accept new float[129]\n")
        self.assertEqual(probes.array_cap(staged)["array_cap"], 128)
        other = ("FOCC_P5_Array129.psc: new float[129] (compile-only, never packed)\nexit code 1\n"
                 "<unknown>(0,0): Unable to find flags file: Starfield_Papyrus_Flags.flg\nNo output generated\n"
                 "refused: the compiler did not accept new float[129] (see the output above)\n")
        r = probes.array_cap(other)
        self.assertEqual(r["array_cap"], "unknown")
        self.assertIn("flags file", r["detail"])
        self.assertEqual(probes.array_cap("exit code 1\n")["array_cap"], "unknown")

    def test_fewer_than_ten_ticks_is_not_a_baseline(self):
        v = probes.check_p5(col(log=p5_log(ticks=3)))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("asked for 3 ticks" in r for r in v.reasons), v.reasons)
        self.assertNotIn("baseline_ms", v.extra)

    def test_fail_and_inconclusive(self):
        self.assertEqual(probes.check_p5(col(log=p5_log()[:-3])).verdict, FAIL)               # 7 of 10 ticks
        self.assertEqual(probes.check_p5(col(log=p5_log(ms=(3.0,) * 9 + (1500.0,)))).verdict, FAIL)
        self.assertEqual(probes.check_p5(col(log=[INIT] + p5_log()[2:])).verdict, INCONCLUSIVE)   # no start
        self.assertEqual(probes.check_p5(col(log=p5_log()[:2])).verdict, INCONCLUSIVE)           # start, no ticks
        v = probes.check_p5(col(log=p5_log(ms=(3.0,) * 9 + (1500.0,))))
        self.assertTrue(any("placeholder" in r for r in v.reasons))


# ----------------------------------------------------------------------------------------------- P6 / P7

# the trial line exactly as FOCC_ProbeQuest.SpawnTrials writes it: `base=<signed decimal> baselocal=a|b|other|none`
# (BaseName()), no match= field. `baselocal=` may be given as a plugin:id to exercise the plan.json mapping instead.
P6_IDS = f"list={0x0300081C} holder={0x03000805}"     # FOCC_P6_HolderList, FOCC_Holder at load index 03
P7_IDS = f"list={0x0300081D} rep={0x0300081E}"        # FOCC_P7_RepList, FOCC_Rep_Test


def p6_log(pairs=((1.0, "A"), (2.0, "B")), loc=RUNTIME_LOC, baselocal=None, ids=P6_IDS):
    lines = [INIT]
    for datum, which in pairs:
        for k in range(1, 4):
            bl = (baselocal or {}).get(which, {"A": "a", "B": "b", "other": "other", "none": "none"}[which])
            base = {"none": "none", "B": "4660"}.get(which, "2826524")
            lines.append(f"FOCC rt=2.0 p6 datum={datum:.6f} loc={loc} readback={datum:.6f} {ids} trial={k} base={base} baselocal={bl}")
    return lines


def p7_log(pairs=((3.0, "A"), (9.0, "B")), glob=None, ids=P7_IDS):
    lines = [INIT]
    for tier, which in pairs:
        for k in range(1, 4):
            g = tier if glob is None else glob
            bl = {"A": "a", "B": "b", "other": "other", "none": "none"}[which]
            base = {"none": "none", "B": "4660"}.get(which, "2826524")
            lines.append(f"FOCC rt=1.0 p7 tier={tier:.6f} glob={g:.6f} {ids} trial={k} base={base} baselocal={bl}")
    return lines


PLAN67 = {"bases": {"lvln_a": "Starfield.esm:2B211C", "lvln_b": "Starfield.esm:1234"}}   # 2826524 and 4660


def pcol(log):
    """A P6/P7 collection with the stage's plan.json base mapping, which the judges require."""
    c = col(log=log)
    c.plan = copy.deepcopy(PLAN67)
    return c


class LatestAttemptTests(unittest.TestCase):
    """Codex review of #431: logs can hold retries; only the latest attempt is judged."""

    def test_p1_post_save_must_follow_the_latest_pre_save(self):
        c = p1_collection()
        retry = json.dumps({"event": "pre_save", "save": "focc_p1_b", "counter": 3, "written": True})
        c.sfse_log = c.sfse_log + [retry]                  # the newer save of b never finished
        v = probes.check_p1(c)
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("without post_save" in r for r in v.reasons), v.reasons)

    def test_p6_a_partial_retry_is_not_backfilled(self):
        retry = p6_log()[1:3]                              # datum 1: trials 1 and 2 only
        v = probes.check_p6(pcol(p6_log() + retry))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("want 1, 2, 3" in r for r in v.reasons), v.reasons)


# the two trial shapes the kit's sources promise: the script's Trace call and the fixture above must agree
SPAWN_TRACE = 'Trace(probe + " " + head + " trial=" + k + " base=" + Id(b) + " baselocal=" + BaseName(b))'


class P6P7Tests(unittest.TestCase):
    def test_fixture_is_the_scripts_contract(self):
        with open(os.path.join(ROOT, "scripts", "combined_probes", "FOCC_ProbeQuest.psc"), encoding="utf-8") as f:
            quest = f.read()
        self.assertIn(SPAWN_TRACE, quest)
        for name in ('return "a"', 'return "b"', 'return "other"', 'return "none"'):
            self.assertIn(name, quest)
        self.assertNotIn("match=", quest)

    def test_p6_pass_fail_inconclusive(self):
        v = probes.check_p6(pcol(p6_log()))
        self.assertEqual(v.verdict, PASS, v.reasons)
        v = probes.check_p6(col(log=p6_log()))                     # Codex review of #431: no plan.json, no base check
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p6(pcol(p6_log(pairs=((1.0, "A"), (2.0, "A"))))).verdict, FAIL)
        self.assertEqual(probes.check_p6(pcol(p6_log(pairs=((1.0, "A"), (2.0, "none"))))).verdict, FAIL)
        v = probes.check_p6(pcol(p6_log(pairs=((1.0, "A"), (2.0, "other")))))              # neither entry
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("neither entry" in r for r in v.reasons), v.reasons)
        upper = [l.replace("baselocal=a", "baselocal=A").replace("baselocal=b", "baselocal=B") for l in p6_log()]
        self.assertEqual(probes.check_p6(pcol(upper)).verdict, PASS)
        self.assertEqual(probes.check_p6(pcol(p6_log()[:5])).verdict, INCONCLUSIVE)          # 3 + 1 trials
        self.assertEqual(probes.check_p6(pcol(p6_log(loc="none"))).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p6(pcol([INIT, "FOCC p6 refused loc=none"])).verdict, INCONCLUSIVE)
        for plan in ({"lvln_conditions_written": False}, {"skip": ["lvln"]}, {"skip": ["lvln", "sm"]}):
            c = col(log=p6_log())
            c.plan = plan
            v = probes.check_p6(c)
            self.assertEqual((v.verdict, v.extra.get("blocked")), (INCONCLUSIVE, True), plan)
            v = probes.check_p7(c)
            self.assertEqual((v.verdict, v.extra.get("blocked")), (INCONCLUSIVE, True), plan)
        c = col(log=p6_log())
        c.plan = {"skip": ["sm"], "lvln_conditions_written": True, **PLAN67}
        self.assertEqual(probes.check_p6(c).verdict, PASS)
        bad_rb = [INIT] + [l.replace("readback=1.000000", "readback=0.000000") for l in p6_log()[1:]]
        self.assertEqual(probes.check_p6(pcol(bad_rb)).verdict, INCONCLUSIVE)

    def test_a_label_must_agree_with_a_starfield_base_id(self):
        # Codex review of #431 (the literal-label findings): a Starfield.esm entry's runtime id is its file id.
        plan = {"bases": {"lvln_a": "Starfield.esm:2B211C", "lvln_b": "Other.esm:000800"}}
        line = lambda base, label: probes.parse_line(f"FOCC p6 trial=1 base={base} baselocal={label}")  # noqa: E731
        self.assertEqual(probes._base_match(line(0x2B211C, "a"), plan, "lvln_a", "lvln_b"), "A")
        self.assertIsNone(probes._base_match(line(0x2B211D, "a"), plan, "lvln_a", "lvln_b"))
        self.assertEqual(probes._base_match(line(0x05000800, "b"), plan, "lvln_a", "lvln_b"), "B")   # other plugin: local id
        self.assertIsNone(probes._base_match(line(123, "b"), plan, "lvln_a", "lvln_b"))
        self.assertIsNone(probes._base_match(line(0x2B211C, "a"), None, "lvln_a", "lvln_b"))         # no plan: cannot tell

    def test_explicit_match_field_is_honoured(self):
        lines = [l + " match=" + ("A" if "datum=1" in l else "B") for l in p6_log(baselocal={"A": "x", "B": "y"})[1:]]
        self.assertEqual(probes.check_p6(pcol([INIT] + lines)).verdict, PASS)

    def test_p6_plugin_id_baselocal_needs_plan_mapping(self):
        ids = {"A": "Starfield.esm:2B211C", "B": "Starfield.esm:1234"}
        c = col(log=p6_log(baselocal=ids))
        v = probes.check_p6(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("cannot tell" in r for r in v.reasons))
        c.plan = {"bases": {"npc": "x", "lvln_a": "Starfield.esm:2B211C", "lvln_b": "Starfield.esm:1234"}}   # the builder's shape
        self.assertEqual(probes.check_p6(c).verdict, PASS)
        c.plan = {"lvln_a": "Starfield.esm:2B211C", "lvln_b": "Starfield.esm:1234"}                       # flat
        self.assertEqual(probes.check_p6(c).verdict, PASS)
        c.plan = {"bases": {"lvln_a": "Starfield.esm:1234", "lvln_b": "Starfield.esm:2B211C"}}            # swapped
        self.assertEqual(probes.check_p6(c).verdict, FAIL)

    def test_p7(self):
        v = probes.check_p7(pcol(p7_log()))
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertEqual(probes.check_p7(pcol(p7_log(pairs=((3.0, "A"), (9.0, "other"))))).verdict, FAIL)
        self.assertEqual(v.extra["p7b_vendor"]["status"], "deferred")
        self.assertEqual(probes.check_p7(pcol(p7_log(pairs=((3.0, "B"), (9.0, "B"))))).verdict, FAIL)
        self.assertEqual(probes.check_p7(pcol(p7_log(glob=0.0))).verdict, INCONCLUSIVE)     # GLOB readback differs
        self.assertEqual(probes.check_p7(pcol(p7_log()[:4])).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p7(pcol([INIT])).verdict, INCONCLUSIVE)

    def test_the_lists_and_what_they_read_must_be_the_probes_own(self):
        # Codex review of #431: a stale or foreign P6List/Holder or P7List/P7Rep binding never passes
        for ids in (f"list={0x0300081D} holder={0x03000805}", f"list={0x0300081C} holder={0x03000806}",
                    f"list={0x0300081C}", ""):
            v = probes.check_p6(pcol(p6_log(ids=ids)))
            self.assertEqual(v.verdict, INCONCLUSIVE, ids)
            self.assertTrue(any("not the probe's record" in r for r in v.reasons), v.reasons)
        for ids in (f"list={0x0300081C} rep={0x0300081E}", f"list={0x0300081D} rep={0x03000805}", ""):
            self.assertEqual(probes.check_p7(pcol(p7_log(ids=ids))).verdict, INCONCLUSIVE, ids)
        fe = f"list={0xFE00181C - (1 << 32)} holder={0xFE001805 - (1 << 32)}"      # a light plugin's signed ids
        self.assertEqual(probes.check_p6(pcol(p6_log(ids=fe))).verdict, PASS)


# ----------------------------------------------------------------------------------------------- P8

def p8_log(order=(1, 2, 0), swap=None, detach=None):
    lines = [INIT] + [f"FOCC rt=1.0 p8 move stage={k} parent={0x0300080C + k} pos=0 {6 * k} 0" for k in range(3)]
    for s in order:
        lines.append(f"FOCC rt=2.0 p8 stage={s}")
        for k in range(3):
            for j in range(4):
                dis = k != s
                pdis = dis
                if swap == (s, k, j):
                    dis = not dis
                    pdis = dis
                if detach == (s, k, j):
                    dis = not dis
                lines.append(f"FOCC rt=3.0 p8 child stage={k} j={j} id={0x0300080F + 4 * k + j} disabled={dis} "
                             f"parent_disabled={pdis}")
    return lines


class P8Tests(unittest.TestCase):
    def test_an_older_run_before_the_latest_move_does_not_count(self):
        c = col(log=p8_log() + p8_log()[1:-1])                # latest run lost its last child line
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        self.assertEqual(probes.check_p8(c).verdict, INCONCLUSIVE)

    def test_parents_and_children_are_the_probe_refs(self):
        # Codex review of #431: foreign refs with consistent rows never settle P8.
        for old, new in ((f"parent={0x0300080D}", f"parent={0x03000820}"), (f"id={0x03000814}", "id=1")):
            c = col(log=[l.replace(old, new) for l in p8_log()])
            c.saves = saves(focc_p8_before=1, focc_p8_after=1)
            self.assertEqual(probes.check_p8(c).verdict, INCONCLUSIVE, new)

    def test_each_child_must_be_observed(self):
        # Codex review of #431: twelve copies of one valid row are not twelve children.
        log = p8_log()
        first = [i for i, l in enumerate(log) if " p8 stage=" in l][0]
        row = log[first + 1]
        c = col(log=log[:first + 1] + [row] * 12 + log[first + 13:])
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        v = probes.check_p8(c)
        self.assertEqual(v.verdict, INCONCLUSIVE, v.reasons)

    def test_every_stage_must_be_moved(self):
        # Codex review of #431: a P8Move that stopped after stage 0 never moved stages 1 and 2.
        c = col(log=p8_log()[:2] + p8_log()[4:])
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        v = probes.check_p8(c)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("want 0, 1, 2" in r for r in v.reasons), v.reasons)

    def test_pass(self):
        c = col(log=p8_log())
        c.saves = saves(focc_p8_before=5_000_000, focc_p8_after=5_010_000)
        v = probes.check_p8(c)
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertEqual(v.extra["save_growth"]["growth"], 10_000)
        self.assertGreaterEqual(len(v.evidence), 40)

    def test_fail_branches(self):
        c = col(log=p8_log(detach=(1, 1, 2)))               # child disagrees with its parent
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        v = probes.check_p8(c)
        self.assertEqual(v.verdict, FAIL)
        self.assertIn("not honoured", v.reasons[0])
        c = col(log=p8_log(swap=(2, 0, 0)))                 # parent and child both in the wrong state
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        self.assertEqual(probes.check_p8(c).verdict, FAIL)
        c = col(log=p8_log())
        c.saves = saves(focc_p8_before=1_000_000, focc_p8_after=9_000_000)
        self.assertEqual(probes.check_p8(c).verdict, FAIL)

    def test_inconclusive_branches(self):
        c = col(log=p8_log()[:1] + p8_log()[4:])            # no move line
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        self.assertEqual(probes.check_p8(c).verdict, INCONCLUSIVE)
        c = col(log=p8_log()[:-1])                          # 35 child lines
        c.saves = saves(focc_p8_before=1, focc_p8_after=1)
        self.assertEqual(probes.check_p8(c).verdict, INCONCLUSIVE)
        c = col(log=p8_log())
        c.saves = saves(focc_p8_before=1)
        self.assertEqual(probes.check_p8(c).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p8(col(log=p8_log())).verdict, INCONCLUSIVE)

    def test_needs_the_1_2_0_sequence(self):
        # Codex P1 on #431: one stage repeated three times passed without exercising stages 1 and 2.
        for order in ((0, 0, 0), (0, 1, 2), (1, 1, 0)):
            c = col(log=p8_log(order=order))
            c.saves = saves(focc_p8_before=1, focc_p8_after=1)
            v = probes.check_p8(c)
            self.assertEqual(v.verdict, INCONCLUSIVE, order)
            self.assertTrue(any("1, 2, 0" in r for r in v.reasons), v.reasons)


# ----------------------------------------------------------------------------------------------- P9

def p9_log(start=450.0, speed=2.0, seconds=600, cells_every_m=100.0, stuck_from=None, jump_at=None, unload=False,
           done=True):
    lines = [INIT, f"FOCC rt=1.0 p9 dest id={0x0300081B} pos=450.000000 0.000000 0.000000",
             f"FOCC rt=1.5 p9 start actor=-16711680 seconds={seconds} dist={start:.6f}"]
    x = 0.0
    t = 0
    while t <= seconds:
        if t > 0 and not (stuck_from is not None and t >= stuck_from):
            x = min(start, x + speed * 2)
        if jump_at is not None and t == jump_at:
            x = min(start, x + 200.0)
        dist = start - x
        cell = 50333000 + int(x // cells_every_m)
        loaded = "False" if unload else "True"
        lines.append(f"FOCC rt={t + 2:.1f} p9 sample t={t:.6f} actor=-16711680 pos={x:.6f} 0.000000 0.000000 cell={cell} loaded={loaded} dist={dist:.6f}")
        if dist < 10.0:
            break
        t += 2
    if done:
        lines.append(f"FOCC rt={t + 3:.1f} p9 done t={t:.6f} dist={start - x:.6f}")
    return lines


class P9Tests(unittest.TestCase):
    def test_a_start_line_is_required(self):
        # Codex review of #431: samples without a `p9 start` are not tied to one walk.
        self.assertEqual(probes.check_p9(col(log=[l for l in p9_log() if " p9 start " not in l])).verdict,
                         INCONCLUSIVE)

    def test_another_destination_is_not_judged(self):
        # Codex review of #431: the logged destination must be FOCC_P9_Dest.
        log = [l.replace(f"id={0x0300081B}", "id=1") for l in p9_log()]
        self.assertEqual(probes.check_p9(col(log=log)).verdict, INCONCLUSIVE)

    def test_pass(self):
        v = probes.check_p9(col(log=p9_log()))
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertGreaterEqual(v.extra["distinct_cells"], 4)
        self.assertEqual(v.extra["start_dist_m"], 450.0)
        self.assertIn("placeholders", v.extra)

    def test_teleport_is_never_pass(self):
        v = probes.check_p9(col(log=p9_log(jump_at=100)))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("teleport" in r for r in v.reasons))
        # arrived at once, no walking: one sample pair with a huge jump
        instant = [INIT, f"FOCC p9 dest id={0x0300081B} pos=450.000000 0.000000 0.000000",
                   "FOCC p9 sample t=0.000000 actor=2 pos=0.000000 0.000000 0.000000 cell=1 loaded=True dist=450.000000",
                   "FOCC p9 sample t=2.000000 actor=2 pos=449.000000 0.000000 0.000000 cell=5 loaded=True dist=1.000000",
                   "FOCC p9 done t=2.000000 dist=1.000000"]
        self.assertNotEqual(probes.check_p9(col(log=instant)).verdict, PASS)

    def test_fail_branches(self):
        v = probes.check_p9(col(log=p9_log(stuck_from=100)))
        self.assertEqual(v.verdict, FAIL)
        self.assertTrue(any("stuck" in r for r in v.reasons))
        never = p9_log(speed=0.0, seconds=600)                # never leaves the first cell
        self.assertEqual(probes.check_p9(col(log=never)).verdict, FAIL)

    def test_inconclusive_branches(self):
        self.assertEqual(probes.check_p9(col(log=p9_log(done=False))).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p9(col(log=p9_log(start=300.0))).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p9(col(log=p9_log(unload=True))).verdict, INCONCLUSIVE)
        nodest = p9_log()
        del nodest[1]
        self.assertEqual(probes.check_p9(col(log=nodest)).verdict, INCONCLUSIVE)             # no dest line
        self.assertEqual(probes.check_p9(col(log=p9_log()[:3])).verdict, INCONCLUSIVE)      # one sample
        slow = p9_log(speed=0.5, seconds=600)                 # moves, leaves cells, never arrives
        v = probes.check_p9(col(log=slow))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("never fell below" in r for r in v.reasons))
        few_cells = p9_log(cells_every_m=1000.0)              # arrives but through 1 cell id
        self.assertEqual(probes.check_p9(col(log=few_cells)).verdict, INCONCLUSIVE)

    def test_only_the_latest_attempt_counts(self):
        # Codex P1 on #431: an old successful run in the same log must not pass an interrupted retry.
        retry = p9_log() + p9_log(done=False)[1:6]
        self.assertEqual(probes.check_p9(col(log=retry)).verdict, INCONCLUSIVE)
        self.assertEqual(probes.check_p9(col(log=p9_log(done=False)[:8] + p9_log()[1:])).verdict, PASS)


# ----------------------------------------------------------------------------------------------- P10

P10_QUEST = str(0x03000820)                 # FOCC_P10_Quest, local 2080, at load index 03
P10 = [INIT, f"FOCC rt=10.0 p10 sent event={0x0300081F}", f"FOCC rt=10.4 p10 quest started id={P10_QUEST} local=2080",
       f"FOCC rt=20.0 p10 state id={P10_QUEST} local=2080 running=True"]
PSC = "Scriptname FOCC_Probe Hidden\nFunction P10Send() global\n  bool r = Q().P10Event.SendStoryEvent(None, Game.GetPlayer(), None, 0, 0)\nEndFunction\n"


class P10Tests(unittest.TestCase):
    def test_pass_with_compile_receipt(self):
        c = col(log=P10)
        c.files = {"FOCC_Probe.psc": PSC, "offline_check.txt": "compile FOCC_Probe.psc\n  Compilation succeeded.\ncompile FOCC_P10Quest.psc\n  Compilation succeeded.\n"}
        v = probes.check_p10(c)
        self.assertEqual(v.verdict, PASS, v.reasons)
        self.assertIs(v.extra["sendstoryevent_compiles"], True)
        c.files = {"FOCC_Probe.psc": PSC}
        c.plan = {"sha256": {"Data/Scripts/FOCC_Probe.pex": "ab" * 32}}
        self.assertIs(probes.check_p10(c).extra["sendstoryevent_compiles"], True)
        c.plan = {"compiled": {"FOCC_Probe": False}}
        self.assertIs(probes.check_p10(c).extra["sendstoryevent_compiles"], False)
        c.files, c.plan = {}, None
        self.assertIsNone(probes.check_p10(c).extra["sendstoryevent_compiles"])

    def test_fail_branches(self):
        self.assertEqual(probes.check_p10(col(log=[INIT, f"FOCC rt=1.0 p10 sent event={0x0300081F} result=False"])).verdict, FAIL)
        self.assertEqual(probes.check_p10(col(log=[P10[0], P10[1], f"FOCC rt=25.0 p10 state id={P10_QUEST} local=2080 running=False"])).verdict, FAIL)
        self.assertEqual(probes.check_p10(col(log=P10[:3] + [f"FOCC rt=25.0 p10 state id={P10_QUEST} local=2080 running=False"])).verdict, FAIL)

    def test_inconclusive_branches(self):
        self.assertEqual(probes.check_p10(col(log=[INIT, P10[2]])).verdict, INCONCLUSIVE)               # no sent line
        self.assertEqual(probes.check_p10(col(log=P10[:2])).verdict, INCONCLUSIVE)                      # sent, nothing after
        v = probes.check_p10(col(log=P10[:3]))                                                            # started, no state line
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("P10State" in r for r in v.reasons), v.reasons)
        late = [INIT, P10[1], f"FOCC rt=40.0 p10 quest started id={P10_QUEST} local=2080",
                f"FOCC rt=41.0 p10 state id={P10_QUEST} local=2080 running=True"]
        v = probes.check_p10(col(log=late))
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertTrue(any("window" in r for r in v.reasons))
        wrong_quest = [INIT, P10[1], "FOCC rt=10.5 p10 quest started id=1 local=2048", P10[3]]
        self.assertEqual(probes.check_p10(col(log=wrong_quest)).verdict, INCONCLUSIVE)   # another quest's start line does not count
        # Codex review of #431: the literal local=2080 never stands in for the logged id.
        labelled = [INIT, P10[1], "FOCC rt=10.5 p10 quest started id=1 local=2080", "FOCC rt=20.0 p10 state id=1 local=2080 running=True"]
        self.assertEqual(probes.check_p10(col(log=labelled)).verdict, INCONCLUSIVE)
        foreign = [INIT, "FOCC rt=10.0 p10 sent event=1"] + P10[2:]   # Codex review of #431: another keyword
        self.assertEqual(probes.check_p10(col(log=foreign)).verdict, INCONCLUSIVE)
        early = P10[:2] + [f"FOCC rt=10.2 p10 state id={P10_QUEST} local=2080 running=False", P10[2]]
        v = probes.check_p10(col(log=early))            # read before OnQuestInit: says nothing (Codex review of #431)
        self.assertEqual(v.verdict, INCONCLUSIVE, v.reasons)
        other_state = P10[:3] + ["FOCC rt=20.0 p10 state id=1 local=2080 running=True"]
        self.assertEqual(probes.check_p10(col(log=other_state)).verdict, INCONCLUSIVE)
        for plan in ({"sm_nodes_written": False}, {"skip": ["sm"]}):
            c = col(log=P10)
            c.plan = plan
            v = probes.check_p10(c)
            self.assertEqual((v.verdict, v.extra["blocked"]), (INCONCLUSIVE, True), plan)
        c = col(log=P10)
        c.plan = {"skip": ["lvln"], "sm_nodes_written": True}
        self.assertEqual(probes.check_p10(c).verdict, PASS)


# ----------------------------------------------------------------------------------------------- folder + CLI

def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = probes.main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CollectAndCliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_collect_reads_the_layout(self):
        self.write("focc_session1.log", "\n".join(S1_P2) + "\n")
        self.write("focc_session2.log", "\r\n".join(S2_P2) + "\r\n")
        self.write("saves.json", "﻿" + json.dumps(saves(focc_p4_before=1, focc_p4_after=2)))
        self.write("compile_p5_array129.txt", "Compilation succeeded.")
        self.write("plan.json", json.dumps({"lvln_a": "x"}))
        self.write("sfse/focc_sidecar.log", json.dumps({"event": "pre_save", "save": "s", "counter": 1, "written": True}) + "\n")
        self.write("sfse/sidecars/" + sidecar.sidecar_name("s"), stub_sidecar("s", 1))
        self.write("sfse/sidecars/readme.txt", "ignored")
        c = probes.collect(self.dir)
        self.assertEqual(set(c.logs), {"focc_session1.log", "focc_session2.log"})
        self.assertEqual(c.saves[1]["Name"], "focc_p4_after.sfs")
        self.assertEqual(c.plan, {"lvln_a": "x"})
        self.assertEqual(list(c.sidecars), [sidecar.sidecar_name("s")])
        self.assertEqual(len(c.sfse_log), 1)
        self.assertEqual(probes.check_p2(c).verdict, PASS)
        single = probes.collect(self.write("focc.0.log", "\n".join(p5_log())))
        self.assertEqual(probes.check_p5(single).verdict, PASS)
        with self.assertRaises(FileNotFoundError):
            probes.collect(os.path.join(self.dir, "nope"))

    def test_cli_exit_codes_and_json(self):
        self.write("focc_session1.log", "\n".join(S1_P2))
        self.write("focc_session2.log", "\n".join(S2_P2))
        code, out, _ = run(["p2", self.dir])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["verdict"], PASS)
        code, out, _ = run(["P2", "--collect", self.dir])
        self.assertEqual(code, 0)
        code, out, _ = run(["p4", self.dir])
        self.assertEqual((code, json.loads(out)["verdict"]), (2, INCONCLUSIVE))
        lost = self.write("sub/focc_session2.log", f"FOCC init\nFOCC p2 read loc={P2_LOC} local=2054 value=0.000000\n")
        shutil.copy(os.path.join(self.dir, "focc_session1.log"), os.path.dirname(lost))
        code, out, _ = run(["p2", os.path.dirname(lost)])
        self.assertEqual((code, json.loads(out)["verdict"]), (1, FAIL))
        code, out, _ = run(["all", self.dir])
        d = json.loads(out)
        self.assertEqual(d["probes"]["p2"]["verdict"], PASS)
        self.assertEqual(d["verdict"], PASS)                # the only probe with evidence
        self.assertEqual(code, 0)
        code, out, _ = run(["p3", os.path.join(self.dir, "missing")])
        self.assertEqual((code, json.loads(out)["verdict"]), (2, INCONCLUSIVE))
        code, out, _ = run(["hex2dec", "FF012345"])
        self.assertEqual((code, out.strip()), (0, "-16702651"))
        code, out, _ = run(["dec2hex", "-16702651"])
        self.assertEqual((code, out.strip()), (0, "FF012345"))
        code, _, _ = run(["p42", self.dir])
        self.assertEqual(code, 2)
        code, _, _ = run(["p2"])
        self.assertEqual(code, 2)

    def test_module_runs_as_main(self):
        import subprocess
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
        self.write("focc.0.log", "\n".join(p5_log()))
        r = subprocess.run([sys.executable, "-m", "fo4sf.combined.probes", "p5", self.dir], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["verdict"], PASS)


if __name__ == "__main__":
    unittest.main()
