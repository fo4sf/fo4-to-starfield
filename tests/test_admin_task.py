"""scripts/game/admin_task/make_task.py: the elevated task's definition (written as XML; nothing is registered)."""
import io
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game", "admin_task"))
import make_task as mt  # noqa: E402

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
GOOD = ["--user", "CARLOSPC\\great", "--checkout", "D:\\Modding\\wt_nightrun",
        "--python", "C:\\Modding\\venv-render\\Scripts\\python.exe", "--campaign", "D:\\Modding\\campaigns\\job6.json"]


class TaskTests(unittest.TestCase):
    def test_on_demand_interactive_highest_one_fixed_action(self):
        out = os.path.join(tempfile.mkdtemp(), "task.xml")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(mt.main(GOOD + ["--out", out]), 0)
        with open(out, "rb") as f:
            raw = f.read()
        self.assertTrue(raw.startswith(b"\xff\xfe"))                       # UTF-16 with a BOM for schtasks /xml
        root = ET.fromstring(raw.decode("utf-16").replace('encoding="UTF-16"', ""))
        self.assertEqual(len(root.find("t:Triggers", NS)), 0)              # never starts on its own
        p = root.find("t:Principals/t:Principal", NS)
        self.assertEqual(p.find("t:LogonType", NS).text, "InteractiveToken")
        self.assertEqual(p.find("t:RunLevel", NS).text, "HighestAvailable")
        s = root.find("t:Settings", NS)
        self.assertEqual(s.find("t:MultipleInstancesPolicy", NS).text, "IgnoreNew")
        self.assertEqual(s.find("t:ExecutionTimeLimit", NS).text, "PT8H")
        execs = root.findall("t:Actions/t:Exec", NS)
        self.assertEqual(len(execs), 1)
        self.assertEqual(execs[0].find("t:Arguments", NS).text,
                         'scripts\\game\\campaign_arm.py run --campaign "D:\\Modding\\campaigns\\job6.json"')
        self.assertEqual(execs[0].find("t:WorkingDirectory", NS).text, "D:\\Modding\\wt_nightrun")
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):   # a new file only
            mt.main(GOOD + ["--out", out])

    def test_odd_paths_and_users_are_refused(self):
        cases = {"--user": "great", "--checkout": "D:\\a\\..\\b", "--python": "C:\\x\\cmd.exe",
                 "--campaign": "D:\\c\\job6.json\" & calc"}
        for flag, value in cases.items():
            args = list(GOOD)
            args[args.index(flag) + 1] = value
            with self.subTest(flag=flag), self.assertRaises(SystemExit):
                mt.main(args + ["--out", os.path.join(tempfile.mkdtemp(), "t.xml")])
        for v in ("D:\\x\\$env.json", "D:\\x\\%TEMP%.json", "\\\\server\\share\\c.json", "D:/x/c.json"):
            self.assertTrue(mt.check("A\\b", "D:\\x", "C:\\p\\python.exe", v), v)


if __name__ == "__main__":
    unittest.main()
