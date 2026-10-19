"""extract_door_graphs.py (framework question A1): pulls door .agx graphs and the base graphs they name out of a
synthetic Starfield BA2 and summarises them. Synthetic XML only; the real graphs never enter the repository."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ba2_fixture import general_archive  # noqa: E402

spec = importlib.util.spec_from_file_location("extract_door_graphs", os.path.join(ROOT, "scripts", "door_bridge", "extract_door_graphs.py"))
edg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edg)

G = "meshes\\animtextdata\\tables\\graphs\\"
LOAD = b"""<root Name="SimpleOpenClose02_Load" Category="Doors"><node><node_type>Reference</node_type>
<graph>AnimTextData\\Tables\\Graphs\\SimpleOpenClose_Base01.agx</graph></node>
<node><node_type>Event</node_type><output>LoadReady</output></node></root>"""
SIMPLE = b"""<root Name="SimpleOpenClose01"><node><node_type>Reference</node_type><input>SimpleOpenClose_Base01</input></node></root>"""
BASE = b"""<root Name="SimpleOpenClose_Base01"><node><node_type>State</node_type><input>Open</input></node>
<node><node_type>State</node_type><input>Close</input></node><property_sheet AnimSpeed="1.0">OpenCloseFormState</property_sheet>
<node><node_type>Reference</node_type><graph>Missing_Sub.agx</graph></node></root>"""


def archive(d):
    path = os.path.join(d, "Starfield - Animations.ba2")
    with open(path, "wb") as f:
        f.write(general_archive({G + "SimpleOpenClose02_Load.agx": LOAD, G + "SimpleOpenClose01.agx": SIMPLE,
                                 G + "SimpleOpenClose_Base01.agx": BASE, G + "CharacterIdle.agx": b"<root/>",
                                 "meshes\\other.nif": b"x"}))
    return d


class ExtractDoorGraphsTests(unittest.TestCase):
    def test_follows_base_graphs_and_summarises(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "Data"))
            data, out = archive(os.path.join(d, "Data")), os.path.join(d, "out")
            with redirect_stdout(io.StringIO()) as o:
                self.assertEqual(edg.main(["--starfield-data", data, "--out", out]), 0)
            self.assertIn("3 graphs", o.getvalue())
            with open(os.path.join(out, "summary.json"), encoding="utf-8") as f:
                s = json.load(f)
            names = {k.rpartition("\\")[2] for k in s["graphs"]}
            self.assertEqual(names, {"SimpleOpenClose02_Load.agx", "SimpleOpenClose01.agx", "SimpleOpenClose_Base01.agx"})
            base = s["graphs"][G + "SimpleOpenClose_Base01.agx"]
            self.assertEqual(base["node_types"], {"State": 2, "Reference": 1})
            self.assertTrue({"Open", "Close", "OpenCloseFormState"} <= set(base["strings"]))
            self.assertIn("LoadReady", s["graphs"][G + "SimpleOpenClose02_Load.agx"]["strings"])
            self.assertEqual(s["named_but_not_found"], ["Missing_Sub.agx"])
            self.assertTrue(os.path.isfile(os.path.join(out, "meshes", "animtextdata", "tables", "graphs", "SimpleOpenClose01.agx")))

    def test_refuses_existing_or_repo_output(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "Data"))
            data = archive(os.path.join(d, "Data"))
            with self.assertRaises(SystemExit):
                edg.main(["--starfield-data", data, "--out", d])
            with self.assertRaises(SystemExit):
                edg.main(["--starfield-data", data, "--out", os.path.join(ROOT, "graphs_out_test")])
            self.assertFalse(os.path.exists(os.path.join(ROOT, "graphs_out_test")))

    def test_bad_xml_is_reported(self):
        self.assertIn("error", edg.summarise(b"\x00not xml"))


if __name__ == "__main__":
    unittest.main()
