"""Small synthetic native captures, labelled OCR and retained identities; no game/queue execution."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/testing"))
import continuous_evidence as ce


def fmt(p):
    return " ".join(str(v) for v in p)


class ContinuousFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.offset = [30, 7, 2]
        self.installed = {"core.esm": "c" * 64, "core - Main.ba2": "d" * 64}
        self.inputs = {"Data/synthetic.dat": "b" * 64}
        self.write("runner-source.py", b"# synthetic source snapshot\n")
        self.write("install.json", {"complete": True, "files": self.installed, "source_files": self.inputs})

    def write(self, name, data):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        if isinstance(data, str):
            data = data.encode()
        (self.root / name).write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def event(self, label, p, t, key="read", heading=None, hud=False):
        cap, ocr = label + ".png", label + ".txt"
        Image.new("RGB", (4, 4), (20, 30, 40)).save(self.root / cap)
        cmds = ["ClearConsole"] + ["player.getpos " + k for k in "xyz"]
        marker = "FO4SF_READ_" + hashlib.sha256(label.encode("utf-8")).hexdigest()
        text = "ClearConsole\n" + marker + "\n" + "\n".join(
            "player.getpos " + k + "\nGetPos: " + k.upper() + " >> " + f"{v:.2f}"
            for k, v in zip("xyz", p))
        if heading is not None:
            cmds.append("player.getangle z")
            text += "\nplayer.getangle z\nGetAngle: Z >> " + f"{heading:.2f}"
        digest = self.write(ocr, text)
        event = {key: fmt(p), key + "_capture": cap, key + "_ocr": ocr, "cmds": cmds,
                 key + "_invocation": {"id": label, "capture_id": label + ":native",
                                      "source": "native_console", "t": t, "session_marker": marker,
                                      "capture_sha256": hashlib.sha256((self.root / cap).read_bytes()).hexdigest(),
                                      "ocr_sha256": digest, "ocr_capture_id": label + ":native"}}
        if heading is not None:
            event["heading"] = heading
        if hud:
            hudfile = label + "-hud.png"
            Image.new("RGB", (4, 4), (20, 30, 40)).save(self.root / hudfile)
            event.update(hud=True, hud_capture=hudfile, hud_invocation={
                "id": label + ":hud", "capture_id": label + ":hud-native", "source": "native_screen",
                "t": t + 2.5, "capture_sha256": hashlib.sha256((self.root / hudfile).read_bytes()).hexdigest()})
        return event

    def anchor(self, local):
        p = [a + b for a, b in zip(local, self.offset)]
        return {"offset": list(self.offset), "offset_from": "spawn", "spawn_read": fmt(p),
                "spawn_settled": True, "spawn_reads": [self.event("spawn0", p, 0), self.event("spawn1", p, 3)],
                "source_commit": "a" * 40, "install_file": "install.json"}

    def bind(self):
        normalized = {k: v for k, v in self.test.items() if k != "evidence_pins"}
        sha = self.write("plan.json", {"test": normalized})
        self.test["evidence_pins"] = {"source_commit": "a" * 40,
                                     "source_files": {"runner-source.py": hashlib.sha256(
                                         (self.root / "runner-source.py").read_bytes()).hexdigest()},
                                     "plan": {"file": "plan.json", "sha256": sha},
                                     "experiment_files": dict(self.installed),
                                     "experiment_source_files": dict(self.inputs)}

    def rewrite_ocr(self, event, transform, key="read"):
        name = event[key + "_ocr"]
        raw = (self.root / name).read_text(encoding="utf-8")
        event[key + "_invocation"]["ocr_sha256"] = self.write(name, transform(raw))

    def classes(self, report=None):
        if report is None:
            report = self.inspect()
        json.dumps(report, allow_nan=False)
        return {i["class"] for i in report["issues"]}


class WalkEvidenceTests(ContinuousFixture):
    def setUp(self):
        super().setUp()
        self.points = [[x, 10, 0] for x in [90, 99, 101, 110, 120, 130, 140]]
        ground = {"terrain": {"x0": 80, "y0": 0, "step": 1, "rows": [[0, 0], [0, 0]]},
                  "surfaces": {"x0": 90, "y0": 10, "step": 1,
                               "nodes": {"30,0": [[0, 0]], "40,0": [[0, 0]]}},
                  "owners": [{"src": "bridge"}], "path": [p[:2] for p in self.points]}
        self.test = {"id": "synthetic_walk", "kind": "walk", "spawn_local": self.points[0],
                     "waypoints": [p + [2.5, 1] for p in self.points], "goal_radius": 3, "start": self.points[0],
                     "ground": "ground.json", "ground_sha256": self.write("ground.json", ground),
                     "bridge": {"src": "bridge", "span": [30, 40], "min_reads": 2},
                     "crossings": [{"from": [0, 0], "to": [1, 0]}]}
        self.obs = self.anchor(self.points[0])
        self.obs.update(walk_stopped="goal", legs=[])
        for n, p in enumerate(self.points):
            q = [a + b for a, b in zip(p, self.offset)]
            leg = self.event("leg" + str(n), q, 4 + 6 * n, hud=True)
            leg.update(n=n, used=leg["read"], used_from="read",
                       action="done" if n == len(self.points) - 1 else "aim")
            if leg["action"] == "aim":
                leg.update(hold_ms=2000, heading=90)
                leg["cmds"].append("player.setangle z 90")
            self.obs["legs"].append(leg)
        self.bind()

    def inspect(self):
        return ce.inspect_walk(self.test, self.obs, self.root)

    def test_positive_arbitrary_offset_and_equal_pixel_independent_captures(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        r = self.inspect()
        self.assertEqual(r["status"], "MATCH", r["issues"])
        self.assertFalse(r["runtime_accepted"])
        caps = r["capture_identities"]
        self.assertEqual(len({c["sha256"] for c in caps}), 1)
        self.assertEqual(len({tuple(c["physical_identity"]) for c in caps}), len(caps))
        self.assertIn("out of scope", r["check_scopes"]["ground"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_used_cannot_manufacture_movement_from_stationary_reads(self):
        for n, leg in enumerate(self.obs["legs"]):
            p = [a + b for a, b in zip(self.points[0], self.offset)]
            replacement = self.event("leg" + str(n), p, 4 + 6 * n)
            for key in ["read", "read_capture", "read_ocr", "read_invocation"]:
                leg[key] = replacement[key]
        self.assertIn("READ_SELECTION", self.classes())
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertTrue(any(i["class"] == "READ_SELECTION" and i["status"] == "MISMATCH"
                            for i in self.inspect()["issues"]))

    def test_sparse_missing_numbered_leg_is_not_credited(self):
        del self.obs["legs"][2]
        self.assertIn("LEG_SEQUENCE", self.classes())

    def test_object_ocr_cannot_override_player_command_metadata(self):
        leg = self.obs["legs"][1]
        self.rewrite_ocr(leg, lambda text: text.replace("player.getpos ", "getpos "))
        self.assertIn("OCR_ACTOR", self.classes())
        self.assertNotEqual(self.inspect()["status"], "MATCH")

    def test_selected_reread_also_requires_player_query_echoes(self):
        leg = self.obs["legs"][1]
        point = [float(value) for value in leg["read"].split()]
        extra = self.event("leg1-confirm", point, 11, key="reread")
        leg.update({key: value for key, value in extra.items() if key.startswith("reread")})
        leg["used_from"] = "reread"
        self.assertEqual(self.inspect()["status"], "MATCH")
        self.rewrite_ocr(leg, lambda text: text.replace("player.getpos ", "getpos "), key="reread")
        self.assertIn("OCR_ACTOR", self.classes())
        self.assertNotEqual(self.inspect()["status"], "MATCH")

    def test_missing_query_echoes_leave_actor_unverified(self):
        leg = self.obs["legs"][1]
        self.rewrite_ocr(leg, lambda text: "\n".join(line for line in text.splitlines()
                                                     if not line.startswith("player.getpos ")))
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("OCR_ACTOR", self.classes())

    def test_missing_commands_hud_and_per_read_capture_stays_inconclusive(self):
        for leg in self.obs["legs"]:
            for key in ["cmds", "hud", "hud_capture", "hud_invocation", "read_capture", "read_invocation"]:
                leg.pop(key)
        r = self.inspect()
        self.assertEqual(r["status"], "INCONCLUSIVE")
        self.assertTrue({"COMMANDS", "HUD", "CAPTURE", "PROVENANCE"} <= self.classes(r))

    def test_missing_unsettled_or_inconsistent_spawn_not_accepted(self):
        original = copy.deepcopy(self.obs)
        for change in [lambda o: o.pop("spawn_read"), lambda o: o.update(spawn_settled=False),
                       lambda o: o["spawn_reads"].pop(),
                       lambda o: o["spawn_reads"][-1]["read_invocation"].update(t=1),
                       lambda o: o["offset"].__setitem__(2, 3)]:
            self.obs = copy.deepcopy(original)
            change(self.obs)
            self.assertNotEqual(self.inspect()["status"], "MATCH")

    def test_origin_to_first_leg_gap_not_guessed(self):
        leg = self.obs["legs"][0]
        leg.update(self.event("leg0", [124, 17, 2], 4, hud=True))
        leg.update(used=leg["read"])
        leg["cmds"].append("player.setangle z 90")
        self.assertIn("START_CONTINUITY", self.classes())

    def test_setup_needs_independent_pair_and_first_leg_continuity(self):
        self.test["setup"] = True
        p = [120, 17, 2]
        self.obs["setup"] = {"read": fmt(p), "settled": True,
                             "reads": [self.event("setup0", p, 3.2), self.event("setup1", p, 6.2)]}
        for leg in self.obs["legs"]:
            leg["read_invocation"]["t"] += 4
            leg["hud_invocation"]["t"] += 4
        self.bind()
        self.assertEqual(self.inspect()["status"], "MATCH")
        self.obs["setup"]["read"] = "126 17 2"
        self.assertIn("START", self.classes())

    def test_capture_path_hardlink_and_invocation_replay_fail(self):
        original = copy.deepcopy(self.obs)
        for field in ["read_capture", "read_invocation"]:
            self.obs = copy.deepcopy(original)
            self.obs["legs"][1][field] = copy.deepcopy(self.obs["legs"][0][field])
            self.assertIn("CAPTURE_REUSE", self.classes())
            self.assertEqual(self.inspect()["status"], "INCONCLUSIVE" if field == "read_invocation" else "MISMATCH")
        self.obs = copy.deepcopy(original)
        os.link(self.root / "leg0.png", self.root / "linked.png")
        self.obs["legs"][1]["read_capture"] = "linked.png"
        self.assertIn("CAPTURE_REUSE", self.classes())

    def test_stale_axis_missing_current_session_value_is_unread(self):
        leg = self.obs["legs"][1]
        raw = ("GetPos: Z >> 2.00\nClearConsole\n" + leg["read_invocation"]["session_marker"]
               + "\nGetPos: X >> 129.00\nGetPos: Y >> 17.00\nplayer.getpos z")
        leg["read_invocation"]["ocr_sha256"] = self.write(leg["read_ocr"], raw)
        self.assertIn("OCR_SESSION", self.classes())
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")

    def test_pins_receipt_and_exact_ground_file_are_required(self):
        original_test, original_obs = copy.deepcopy(self.test), copy.deepcopy(self.obs)
        for change in [lambda t, o: t.pop("evidence_pins"), lambda t, o: o.pop("install_file"),
                       lambda t, o: t.pop("ground_sha256"), lambda t, o: o.update(source_commit="b" * 40)]:
            self.test, self.obs = copy.deepcopy(original_test), copy.deepcopy(original_obs)
            change(self.test, self.obs)
            self.assertNotEqual(self.inspect()["status"], "MATCH")
        self.test, self.obs = original_test, original_obs
        (self.root / "ground.json").write_bytes(b"{}")
        self.assertIn("GROUND_PIN", self.classes())
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertTrue(any(i["class"] == "GROUND_PIN" and i["status"] == "MISMATCH"
                            for i in self.inspect()["issues"]))

    def test_complete_stale_session_cannot_use_an_old_clearconsole_marker(self):
        leg = self.obs["legs"][1]
        old = self.event("prior-session", [129, 17, 2], 0)
        raw = (self.root / old["read_ocr"]).read_text()
        # Equal XYZ cannot establish a new invocation; only its visible challenge can.
        leg["read_invocation"]["ocr_sha256"] = self.write(leg["read_ocr"], raw)
        r = self.inspect()
        self.assertEqual(r["status"], "INCONCLUSIVE")
        self.assertIn("FRESHNESS", self.classes(r))

    def test_wrong_token_cannot_be_rebound_by_relabeling_metadata(self):
        leg = self.obs["legs"][1]
        meta = leg["read_invocation"]
        wrong = "FO4SF_READ_" + hashlib.sha256(b"other-invocation").hexdigest()
        raw = (self.root / leg["read_ocr"]).read_text().replace(meta["session_marker"], wrong)
        meta["session_marker"] = wrong
        meta["ocr_sha256"] = self.write(leg["read_ocr"], raw)
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("FRESHNESS", self.classes())

    def test_missing_session_marker_does_not_infer_freshness_from_clearconsole(self):
        self.obs["legs"][1]["read_invocation"].pop("session_marker")
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("FRESHNESS", self.classes())

    def test_challenge_after_xyz_does_not_authenticate_earlier_replies(self):
        leg = self.obs["legs"][1]
        meta = leg["read_invocation"]
        raw = (self.root / leg["read_ocr"]).read_text().replace(meta["session_marker"] + "\n", "")
        meta["ocr_sha256"] = self.write(leg["read_ocr"], raw + "\n" + meta["session_marker"])
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("OCR_SESSION", self.classes())

    def test_challenge_before_last_clearconsole_is_not_current_session_proof(self):
        leg = self.obs["legs"][1]
        meta = leg["read_invocation"]
        raw = (self.root / leg["read_ocr"]).read_text().replace(meta["session_marker"] + "\n", "")
        meta["ocr_sha256"] = self.write(leg["read_ocr"], meta["session_marker"] + "\n" + raw)
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("FRESHNESS", self.classes())

    def test_complete_two_decimal_replies_refuse_split_and_trailing_numeric_residue(self):
        leg = self.obs["legs"][1]
        meta = leg["read_invocation"]
        original = (self.root / leg["read_ocr"]).read_text()
        for value in ["-1 593.51", "17.00 593.51", "17", "17.0", "17.000", "17.00junk",
                      "17.00.00", "NaN", "1.7e1", "-1 593.51\nGetPos: Y >> 17.00"]:
            with self.subTest(reply=value):
                raw = original.replace("GetPos: Y >> 17.00", "GetPos: Y >> " + value)
                meta["ocr_sha256"] = self.write(leg["read_ocr"], raw)
                r = self.inspect()
                self.assertEqual(r["status"], "INCONCLUSIVE")
                self.assertIn("OCR_SESSION", self.classes(r))

    def test_independent_finish_matches_parent_status_precedence(self):
        for statuses, expected in [([], "MATCH"), (["MISMATCH"], "MISMATCH"),
                                   (["INCONCLUSIVE"], "INCONCLUSIVE"),
                                   (["MISMATCH", "INCONCLUSIVE"], "INCONCLUSIVE")]:
            audit = ce._Audit({"id": "fixture", "kind": "walk"}, {}, self.root, "walk")
            for status in statuses:
                audit.issue("FIXTURE", "explicit protocol issue", mismatch=status == "MISMATCH")
            self.assertEqual(audit.finish()["status"], expected)

    def test_changed_source_plan_and_install_receipt_fail(self):
        for name, data, cls in [("runner-source.py", b"# changed", "SOURCE_PIN"),
                                ("plan.json", b"{}", "PLAN_PIN"),
                                ("install.json", {"complete": True, "files": {}, "source_files": {}}, "INSTALL_PIN")]:
            before = (self.root / name).read_bytes()
            self.write(name, data)
            self.assertIn(cls, self.classes())
            self.assertEqual(self.inspect()["status"], "MISMATCH")
            self.write(name, before)

    def test_no_route_time_teleport_or_unknown_command_is_waived(self):
        self.obs["legs"][2]["cmds"].append("player.setpos x 123")
        self.assertIn("TYPED", self.classes())
        self.assertEqual(self.inspect()["status"], "MISMATCH")

    def test_nan_malformed_and_extreme_fields_never_match_or_raise(self):
        original = copy.deepcopy(self.obs)
        for key, value in [("hold_ms", float("nan")), ("hold_ms", True), ("heading", float("inf")),
                           ("n", False), ("used", "nan 17 2"), ("cmds", 3),
                           ("read", [1, 2, 3]), ("read", "1e999 17 2")]:
            self.obs = copy.deepcopy(original)
            self.obs["legs"][1][key] = value
            r = self.inspect()
            self.assertNotEqual(r["status"], "MATCH")
            self.classes(r)

    def test_time_bounds_jumps_and_goal_are_checked(self):
        self.obs["legs"][1]["read_invocation"]["t"] = 3
        self.assertIn("TIME", self.classes())
        self.obs["legs"][1]["read_invocation"]["t"] = 10
        self.obs["legs"][0]["hold_ms"] = 100000
        self.assertIn("NUMBER", self.classes())
        self.obs["legs"][0]["hold_ms"] = 2000
        last = self.obs["legs"][-1]
        last.update(self.event("leg6", [500, 17, 2], 40, hud=True))
        last["used"] = last["read"]
        self.assertTrue({"JUMP", "OFFROUTE"} <= self.classes())

    def test_stationary_bridge_contacts_are_not_progression(self):
        leg = self.obs["legs"][5]
        leg.update(self.event("leg5", [150, 17, 2], 34, hud=True))
        leg.update(used=leg["read"])
        leg["cmds"].append("player.setangle z 90")
        self.assertIn("BRIDGE_PROGRESS", self.classes())

    def test_repeated_crossing_inventory_cannot_reuse_one_witness(self):
        self.test["crossings"] *= 2
        self.bind()
        self.assertIn("CROSSING_PLAN", self.classes())
        loop = [[90, 10, 0], [110, 10, 0], [90, 10, 0], [110, 10, 0]]
        self.assertEqual(ce._borders(loop), [((0, 0), (1, 0)), ((1, 0), (0, 0)), ((0, 0), (1, 0))])
        self.assertEqual(ce._borders([[100, 0, 0], [90, 0, 0]]), [((1, 0), (0, 0))])
        self.assertEqual(ce._borders([[110, 0, 0], [100, 0, 0]]), [])

    def test_confirmed_reread_must_agree_and_bind_its_own_capture(self):
        leg = self.obs["legs"][1]
        p = [129, 17, 2]
        repeat = self.event("leg1again", p, 11, "reread")
        for key, value in repeat.items():
            if key != "cmds":
                leg[key] = value
        leg.update(used_from="reread", confirmed=True)
        self.assertEqual(self.inspect()["status"], "MATCH")
        leg["reread"] = "140 17 2"
        self.assertIn("CONFIRMATION", self.classes())

    def test_player_route_cannot_use_diagnostic_object_reads(self):
        for event in self.obs["spawn_reads"] + self.obs["legs"]:
            event["ref"] = "01000001"
            event["cmds"] = ["ClearConsole", "prid 01000001"] + ["getpos " + k for k in "xyz"] + [
                c for c in event["cmds"] if "setangle" in c]
            self.rewrite_ocr(event, lambda s: s.replace("player.getpos", "getpos").replace(
                "\ngetpos x", "\nprid 01000001\ngetpos x"))
        report = self.inspect()
        self.assertNotEqual(report["status"], "MATCH")
        self.assertTrue(any(i["class"] == "COMMANDS" and i["status"] == "MISMATCH"
                            for i in report["issues"]))

    def test_reversed_command_sequence_cannot_authenticate_read_session(self):
        self.obs["legs"][1]["cmds"].reverse()
        report = self.inspect()
        self.assertEqual(report["status"], "MISMATCH")
        self.assertIn("COMMANDS", self.classes(report))

    def test_confirming_reread_before_primary_is_refused_even_when_primary_used(self):
        leg = self.obs["legs"][1]
        repeat = self.event("early-confirmation", [129, 17, 2], 1, "reread")
        leg.update({k: v for k, v in repeat.items() if k != "cmds"})
        leg.update(confirmed=True)
        report = self.inspect()
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertIn("TIME", self.classes(report))

    def test_confirming_reread_after_next_leg_is_refused_even_when_primary_used(self):
        leg = self.obs["legs"][1]
        repeat = self.event("late-confirmation", [129, 17, 2], 11, "reread")
        leg.update({k: v for k, v in repeat.items() if k != "cmds"})
        leg.update(confirmed=True)
        for time in (80000, 17):  # outside the reread window, then inside it but after leg 2
            with self.subTest(time=time):
                leg["reread_invocation"]["t"] = time
                report = self.inspect()
                self.assertEqual(report["status"], "INCONCLUSIVE")
                self.assertIn("TIME", self.classes(report))

    def test_later_confirmation_allows_primary_selection_and_hold_after_reread(self):
        leg = self.obs["legs"][1]
        repeat = self.event("valid-confirmation", [129, 17, 2], 11, "reread")
        leg.update({k: v for k, v in repeat.items() if k != "cmds"})
        leg.update(confirmed=True)
        self.assertEqual(self.inspect()["status"], "MATCH")

    def test_selected_reread_cannot_hide_primary_before_prior_confirmation(self):
        first = self.obs["legs"][0]
        repeat = self.event("prior-confirmation", [120, 17, 2], 7, "reread")
        first.update({k: v for k, v in repeat.items() if k != "cmds"})
        first.update(confirmed=True)
        leg = self.obs["legs"][1]
        leg["read_invocation"]["t"] = 6
        repeat = self.event("selected-confirmation", [129, 17, 2], 11, "reread")
        leg.update({k: v for k, v in repeat.items() if k != "cmds"})
        leg.update(confirmed=True, used_from="reread")
        report = self.inspect()
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertIn("TIME", self.classes(report))

    def test_sparse_legacy_geometry_with_retained_shots_is_inconclusive(self):
        for event in self.obs["spawn_reads"] + self.obs["legs"]:
            for key in list(event):
                if key.endswith(("_capture", "_ocr", "_invocation")):
                    event.pop(key)
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")

    def test_missing_actual_xyz_and_used_remain_inconclusive(self):
        self.obs["legs"][1]["read"] = None
        self.obs["legs"][1]["used"] = None
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("UNREAD", self.classes())

    def test_nonfinite_or_malformed_pinned_ground_is_not_geometry_acceptance(self):
        ground = json.loads((self.root / "ground.json").read_text())
        for terrain in [[], {"x0": 0, "y0": 0, "step": float("nan"), "rows": [[0, 0], [0, 0]]},
                        {"x0": 0, "y0": 0, "step": 1, "rows": [[float("nan"), 0], [0, 0]]}]:
            ground["terrain"] = terrain
            self.test["ground_sha256"] = self.write("ground.json", ground)
            self.bind()
            self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
            self.assertIn("GROUND_PIN", self.classes())

    def test_bridge_identity_cannot_be_invented_from_anonymous_nodes(self):
        self.test["bridge"].pop("src")
        self.bind()
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("BRIDGE", self.classes())

    def test_confirmation_flag_alone_is_not_independent_evidence(self):
        self.obs["legs"][1]["confirmed"] = True
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("CONFIRMATION", self.classes())

    def test_full_repeated_border_route_matches_and_missing_occurrence_cannot(self):
        points = [[x, 10, 0] for x in [60, 80, 60, 80, 100, 110, 120]]
        self.test.update(spawn_local=points[0], start=points[0],
                         waypoints=[p + [2.5, 1] for p in points],
                         bridge={"src": "bridge", "span": [80, 90], "min_reads": 2},
                         crossings=[{"from": list(a), "to": list(b)} for a, b in ce._borders(points)])
        ground = json.loads((self.root / "ground.json").read_text())
        ground["surfaces"].update(x0=60, nodes={"40,0": [[0, 0]], "50,0": [[0, 0]]})
        ground["path"] = [p[:2] for p in points]
        self.test["ground_sha256"] = self.write("ground.json", ground)
        self.obs = self.anchor(points[0])
        self.obs.update(legs=[], walk_stopped="goal")
        for n, p in enumerate(points):
            leg = self.event("loop" + str(n), [p[k] + self.offset[k] for k in range(3)], 4 + n * 6, hud=True)
            leg.update(n=n, used=leg["read"], used_from="read", action="done" if n == 6 else "aim")
            if n < 6:
                leg.update(hold_ms=3000, heading=90)
                leg["cmds"].append("player.setangle z 90")
            self.obs["legs"].append(leg)
        self.bind()
        r = self.inspect()
        self.assertEqual(r["status"], "MATCH", r["issues"])
        del self.obs["legs"][2]
        for n, leg in enumerate(self.obs["legs"]):
            leg["n"] = n
        self.assertIn("CROSSING", self.classes())

    def test_unsafe_missing_or_corrupt_capture_is_inconclusive(self):
        original = self.obs["legs"][1]["read_capture"]
        for name in ["../leg0.png", "missing.png", "bad.png"]:
            self.write("bad.png", b"not a png")
            self.obs["legs"][1]["read_capture"] = name
            self.assertIn("CAPTURE", self.classes())
        self.obs["legs"][1]["read_capture"] = original


class DoorEvidenceTests(ContinuousFixture):
    def setUp(self):
        super().setUp()
        outside = {"route": [[0, 0, 10], [5, 0, 10], [10, 0, 10]],
                   "door": [10, 0, 10], "arrival": [0, 0, 10], "arrival_heading": 350}
        inside = {"route": [[0, 0, 0], [5, 0, 0], [10, 0, 0]],
                  "door": [10, 0, 0], "arrival": [0, 0, 0], "arrival_heading": 90}
        self.test = {"id": "synthetic_door", "kind": "door_trip", "spawn_local": [0, 0, 10],
                     "outside": outside, "inside": inside, "radius": 4, "save": "fo4sf_synthetic",
                     "probes": [{"ref": "01000001", "local": [5, 5, 10]}]}
        self.obs = self.anchor(self.test["spawn_local"])
        self.obs["legs"] = []
        for name, side, start_t, arrival, arrival_t, heading in [
                ("in", outside, 4, [0, 0, 0], 20, 90),
                ("out", inside, 24, [30, 7, 12], 40, 350)]:
            shift = self.offset if name == "in" else [0, 0, 0]
            route = [[p[k] + shift[k] for k in range(3)] for p in side["route"]]
            leg = self.event(name + "start", route[0], start_t, "start_read")
            leg.update(name=name, mode="route", teleports=0, trigger="walk", route=route,
                       walked_ms=4000, arrival_read=fmt(arrival), arrival_settled=True,
                       arrival_heading=heading, arrival_reads=[
                           self.event(name + "arr0", arrival, arrival_t, heading=heading),
                           self.event(name + "arr1", arrival, arrival_t + 3, heading=heading)], steps=[])
            for n, p in enumerate(route[1:]):
                step = self.event(name + "step" + str(n), p, start_t + 3 * (n + 1), hud=True)
                step.update(n=n, ms=2000, state="here")
                leg["steps"].append(step)
            self.obs["legs"].append(leg)
        reload = self.event("away", [60, 7, 12], 44, "away_read")
        reload.update(read="30 7 12", settled=True, heading=350, reads=[
            self.event("reload0", [30, 7, 12], 50, heading=350),
            self.event("reload1", [30, 7, 12], 53, heading=350)])
        self.obs["reload"] = reload
        self.obs["save"] = {"found": True, "name": self.test["save"]}
        probe = self.event("probe", [35, 12, 12], 5)
        probe.update(ref="01000001", cmds=["ClearConsole", "prid 01000001", "GetSelf"] + ["getpos " + k for k in "xyz"])
        self.rewrite_ocr(probe, lambda text: text.replace("player.getpos ", "getpos ").replace(
            "\ngetpos x", "\nprid 01000001\nGetSelf\nGetSelf >> (01000001)\ngetpos x", 1))
        self.obs["probe_reads"] = [probe]
        self.bind()

    def inspect(self):
        return ce.inspect_door_trip(self.test, self.obs, self.root)

    def test_diagnostic_object_cannot_use_player_command_ocr(self):
        probe = self.obs["probe_reads"][0]
        self.rewrite_ocr(probe, lambda text: text.replace("\ngetpos ", "\nplayer.getpos "))
        self.assertIn("OCR_ACTOR", self.classes())
        self.assertNotEqual(self.inspect()["status"], "MATCH")

    def test_positive_in_out_reload_and_diagnostic_residuals(self):
        r = self.inspect()
        self.assertEqual(r["status"], "MATCH", r["issues"])
        probe = next(x for x in r["rows"] if x["label"] == "merge_probe.0")
        self.assertEqual(probe["merged_residual_m"], 0)
        self.assertGreater(probe["local_residual_m"], 30)
        self.assertTrue(probe["selection_verified"])
        self.assertTrue(probe["diagnostic"])
        self.assertFalse(r["runtime_accepted"])

    def test_diagnostic_reference_requires_a_successful_current_selection(self):
        original = copy.deepcopy(self.obs)
        text = (self.root / "probe.txt").read_text(encoding="utf-8")
        changes = {
            "no native prid": text.replace("prid 01000001\n", ""),
            "no GetSelf": text.replace("GetSelf\nGetSelf >> (01000001)\n", ""),
            "echo only": text.replace("GetSelf >> (01000001)\n", ""),
            "refused prid": text.replace("prid 01000001\n", "prid 01000001\nInvalid object reference.\n"),
            "wrong selected object": text.replace("GetSelf >> (01000001)", "GetSelf >> (01000002)"),
            "reply is not echo": text.replace("GetSelf\n", "", 1),
            "trailing ID residue": text.replace("GetSelf >> (01000001)", "GetSelf >> (01000001) 2"),
            "ambiguous duplicate": text.replace("GetSelf >> (01000001)", "GetSelf >> (01000001)\nGetSelf >> (01000002)"),
            "selection changed after proof": text.replace("getpos x\n", "prid 01000002\ngetpos x\n"),
            "hidden unknown command": text.replace("getpos x\n", "selectanything\ngetpos x\n"),
            "replayed proof before selection": text.replace("prid 01000001\nGetSelf\nGetSelf >> (01000001)",
                                                             "GetSelf\nGetSelf >> (01000001)\nprid 01000001"),
            "late selection proof": text.replace("GetSelf\nGetSelf >> (01000001)\n", "") + "\nGetSelf\nGetSelf >> (01000001)",
            "fuzzy hex": text.replace("GetSelf >> (01000001)", "GetSelf >> (O1OOOOO1)"),
        }
        for label, value in changes.items():
            with self.subTest(label=label):
                self.obs = copy.deepcopy(original)
                probe = self.obs["probe_reads"][0]
                self.rewrite_ocr(probe, lambda old: value)
                r = self.inspect()
                self.assertNotEqual(r["status"], "MATCH", r)
                self.assertIn("REFERENCE_SELECTION", self.classes(r))
                row = next(x for x in r["rows"] if x["label"] == "merge_probe.0")
                self.assertFalse(row["selection_verified"])
                self.assertIsNone(row["observed"])
                self.assertNotIn("merged_residual_m", row)
        self.obs = original

    def test_stale_selection_proof_before_challenge_is_not_borrowed(self):
        probe = self.obs["probe_reads"][0]
        proof = "GetSelf\nGetSelf >> (01000001)\n"
        marker = probe["read_invocation"]["session_marker"]
        self.rewrite_ocr(probe, lambda text: text.replace(proof, "").replace(marker, proof + marker))
        self.assertIn("REFERENCE_SELECTION", self.classes())

    def test_typed_selection_proof_is_required_and_not_a_player_command(self):
        probe = self.obs["probe_reads"][0]
        probe["cmds"].remove("GetSelf")
        self.assertIn("COMMANDS", self.classes())
        probe["cmds"].insert(2, "GetSelf")
        for event in self.obs["spawn_reads"]:
            event["cmds"].insert(1, "GetSelf")
        self.assertIn("COMMANDS", self.classes())

    def test_invalid_diagnostic_command_metadata_cannot_supply_residuals(self):
        original = copy.deepcopy(self.obs)
        for cmds in [
                ["ClearConsole", "prid 01000001", "getpos x", "getpos y", "getpos z"],
                ["ClearConsole", "prid 01000002", "GetSelf", "getpos x", "getpos y", "getpos z"],
                ["ClearConsole", "prid 01000001", "GetSelf", "prid 01000002", "getpos x", "getpos y", "getpos z"],
                ["ClearConsole", "prid 01000001", "getpos x", "getpos y", "getpos z", "GetSelf"]]:
            with self.subTest(cmds=cmds):
                self.obs = copy.deepcopy(original)
                self.obs["probe_reads"][0]["cmds"] = cmds
                r = self.inspect()
                self.assertIn("COMMANDS", self.classes(r))
                row = next(x for x in r["rows"] if x["label"] == "merge_probe.0")
                self.assertFalse(row["selection_verified"])
                self.assertIsNone(row["observed"])
                self.assertNotIn("merged_residual_m", row)

    def test_diagnostic_xyz_disagreement_cannot_supply_residuals(self):
        probe = self.obs["probe_reads"][0]
        probe["read"] = "35 12 13"
        r = self.inspect()
        self.assertIn("READ_SELECTION", self.classes(r))
        row = next(x for x in r["rows"] if x["label"] == "merge_probe.0")
        self.assertFalse(row["selection_verified"])
        self.assertIsNone(row["observed"])
        self.assertNotIn("merged_residual_m", row)

    def test_unbound_diagnostic_capture_cannot_supply_residuals(self):
        original = copy.deepcopy(self.obs)
        for key, value in [("ocr_sha256", "0" * 64), ("capture_sha256", "0" * 64),
                           ("ocr_capture_id", "unrelated"), ("source", "not-native"), ("t", None)]:
            with self.subTest(key=key):
                self.obs = copy.deepcopy(original)
                self.obs["probe_reads"][0]["read_invocation"][key] = value
                r = self.inspect()
                self.assertNotEqual(r["status"], "MATCH")
                row = next(x for x in r["rows"] if x["label"] == "merge_probe.0")
                self.assertFalse(row["selection_verified"])
                self.assertIsNone(row["observed"])
                self.assertNotIn("merged_residual_m", row)
    def test_diagnostic_canonical_case_and_command_prompts_are_supported(self):
        probe = self.obs["probe_reads"][0]
        self.rewrite_ocr(probe, lambda text: "\n".join(
            "> " + line.upper() if line.startswith(("prid ", "getpos ")) or line == "GetSelf"
            else line.upper() if line.startswith("GetSelf >>") else line for line in text.splitlines()))
        self.assertEqual(self.inspect()["status"], "MATCH")

    def test_route_mode_zero_teleports_and_readable_steps_required(self):
        original = copy.deepcopy(self.obs)
        for key, value in [("mode", "straight"), ("teleports", 1), ("teleports", None),
                           ("steps", []), ("steps", [{"state": "loaded", "read": None}])]:
            self.obs = copy.deepcopy(original)
            self.obs["legs"][0][key] = value
            self.assertNotEqual(self.inspect()["status"], "MATCH")

    def test_nearonly_stays_inconclusive(self):
        self.obs["legs"][0].update(trigger="near", teleports=1)
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("NEARONLY", self.classes())

    def test_wrong_interior_or_unmerged_outside_arrival_mismatch(self):
        for n, p in [(0, [30, 7, 12]), (1, [0, 0, 10])]:
            original = copy.deepcopy(self.obs)
            leg = self.obs["legs"][n]
            t = 20 if n == 0 else 40
            heading = 90 if n == 0 else 350
            leg.update(arrival_read=fmt(p), arrival_reads=[
                self.event(leg["name"] + "arr0", p, t, heading=heading),
                self.event(leg["name"] + "arr1", p, t + 3, heading=heading)])
            self.assertIn("ARRIVAL", self.classes())
            self.assertEqual(self.inspect()["status"], "INCONCLUSIVE" if n == 0 else "MISMATCH")
            self.obs = original

    def test_arrival_facing_and_reload_facing_are_checked(self):
        self.test["inside"]["arrival_heading"] = 180
        self.bind()
        self.assertIn("FACING", self.classes())
        self.assertEqual(self.inspect()["status"], "MISMATCH")

    def test_reload_requires_away_read_and_saved_xyz(self):
        self.obs["reload"]["away_read"] = self.obs["legs"][1]["arrival_read"]
        self.assertIn("RELOAD", self.classes())

    def test_angle_capture_also_refuses_partial_two_decimal_replies(self):
        event = self.obs["reload"]["reads"][0]
        original = (self.root / event["read_ocr"]).read_text()
        for value in ["350.0", "350.000", "350.00 999.00", "3 50.00"]:
            event["read_invocation"]["ocr_sha256"] = self.write(
                event["read_ocr"], original.replace("GetAngle: Z >> 350.00", "GetAngle: Z >> " + value))
            self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
            self.assertIn("FACING", self.classes())

    def test_reload_wrong_xyz_and_facing_do_not_match(self):
        reload = self.obs["reload"]
        reload.update(read="50 7 12", heading=180, reads=[
            self.event("reload0", [50, 7, 12], 50, heading=180),
            self.event("reload1", [50, 7, 12], 53, heading=180)])
        self.assertEqual(self.inspect()["status"], "MISMATCH")
        self.assertTrue({"RELOAD", "FACING"} <= self.classes())

    def test_reload_before_completed_trip_cannot_establish_restoration(self):
        reload = self.obs["reload"]
        reload["away_read_invocation"]["t"] = 0.5
        reload["reads"][0]["read_invocation"]["t"] = 1
        reload["reads"][1]["read_invocation"]["t"] = 4
        report = self.inspect()
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertIn("TIME", self.classes(report))

    def test_arrival_window_must_begin_after_last_route_step(self):
        self.obs["legs"][0]["arrival_reads"][0]["read_invocation"]["t"] = 5
        report = self.inspect()
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertIn("TIME", self.classes(report))

    def test_final_arrival_facing_cannot_borrow_first_read_heading(self):
        event = self.obs["legs"][0]["arrival_reads"][-1]
        event["heading"] = 270
        self.rewrite_ocr(event, lambda s: s.replace("GetAngle: Z >> 90.00", "GetAngle: Z >> 270.00"))
        report = self.inspect()
        self.assertNotEqual(report["status"], "MATCH")
        self.assertIn("FACING", self.classes(report))

    def test_ocr_heading_outside_bounds_cannot_wrap_to_planned_heading(self):
        event = self.obs["legs"][0]["arrival_reads"][0]
        original = (self.root / event["read_ocr"]).read_text()
        for angle in (450, -270, 810):
            with self.subTest(angle=angle):
                event["read_invocation"]["ocr_sha256"] = self.write(event["read_ocr"], original.replace(
                    "GetAngle: Z >> 90.00", f"GetAngle: Z >> {angle:.2f}"))
                report = self.inspect()
                self.assertEqual(report["status"], "MISMATCH")
                self.assertIn("FACING", self.classes(report))

    def test_arrival_facing_cannot_come_from_an_unrelated_position(self):
        leg = self.obs["legs"][0]
        leg["arrival_reads"] = [self.event("unrelated-facing", [900, 900, 900], 20, heading=90),
                                self.event("actual-arrival-a", [0, 0, 0], 21, heading=270),
                                self.event("actual-arrival-b", [0, 0, 0], 24, heading=270)]
        report = self.inspect()
        self.assertNotEqual(report["status"], "MATCH")
        self.assertIn("FACING", self.classes(report))

    def test_final_reload_facing_must_restore_saved_facing(self):
        event = self.obs["reload"]["reads"][-1]
        event["heading"] = 170
        self.rewrite_ocr(event, lambda s: s.replace("GetAngle: Z >> 350.00", "GetAngle: Z >> 170.00"))
        report = self.inspect()
        self.assertNotEqual(report["status"], "MATCH")
        self.assertIn("FACING", self.classes(report))

    def test_capture_reuse_issue_retained_when_legacy_fields_missing(self):
        self.obs["legs"][1]["arrival_reads"][0]["read_capture"] = \
            self.obs["legs"][0]["arrival_reads"][0]["read_capture"]
        self.obs["reload"].pop("settled")
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("CAPTURE_REUSE", self.classes())
        self.assertTrue(any(i["class"] == "CAPTURE_REUSE" and i["status"] == "MISMATCH"
                            for i in self.inspect()["issues"]))

    def test_route_must_match_expected_frame_and_order(self):
        self.obs["legs"][0]["route"] = self.test["outside"]["route"]
        self.assertIn("ROUTE_MODE", self.classes())
        self.assertEqual(self.inspect()["status"], "MISMATCH")

    def test_missing_per_read_provenance_never_inferred_from_arrival_shot(self):
        for leg in self.obs["legs"]:
            leg["arrival_reads"] = [e["read"] for e in leg["arrival_reads"]]
            leg["shot"] = "spawn0.png"
        self.assertEqual(self.inspect()["status"], "INCONCLUSIVE")
        self.assertIn("PROVENANCE", self.classes())

    def test_missing_facing_nan_step_and_malformed_schema_are_bounded(self):
        for test, obs in [(None, None), ([], {}), ({"id": float("nan")}, {}),
                          (self.test, {"offset": [float("nan"), 0, 0]}),
                          (self.test, {"legs": "bad"})]:
            r = ce.inspect_door_trip(test, obs, self.root)
            self.assertNotEqual(r["status"], "MATCH")
            json.dumps(r, allow_nan=False)
        self.obs["legs"][0]["arrival_reads"][0]["heading"] = float("nan")
        self.assertIn("FACING", self.classes())


if __name__ == "__main__":
    unittest.main()
