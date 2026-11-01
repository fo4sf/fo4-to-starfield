"""P9's package driver (FOCC_P9Drive.Travel): Starfield.esm's DefaultTraveltoLinkedRef on the probe quest's alias. Its
go says driver=package, it has no return line, and its `p9 package` line names the package the actor ran two seconds
later. Synthetic logs; no game."""
import re
import unittest

from tests.test_combined_probes import BASE, col, p9_log  # noqa: E402  (puts src on the path)
from fo4sf.combined import probes  # noqa: E402

ACTOR = -16711680
TRAVEL = 2174939                    # 0x00212FDB as the log's signed decimal


def drive(*, driver="package", package=TRAVEL, offset=0.0, stray_return=False, **kwargs):
    """A p9_log rung with a go at rt 1.5 (+offset) by the given driver, and for a package its `p9 package` line."""
    lines = p9_log(**kwargs)
    lines = [re.sub(r"rt=([0-9.]+)", lambda m: f"rt={float(m[1]) + offset:.1f}", line) for line in lines]
    start = next(i for i, line in enumerate(lines) if " p9 start " in line)
    origin, dist = offset + 1.5, kwargs.get("start", 450.0)
    extra = f" driver={driver}" if driver == "package" else ""
    add = [f"FOCC rt={origin} p9 go actor={ACTOR} call={origin} target=dest id=50333723 dist={dist}{extra}"]
    if driver == "package" and package is not None:
        add.append(f"FOCC rt={origin + 2.0} p9 package actor={ACTOR} call={origin} linked=50333723 package={package} "
                   f"dist={dist}")
    if stray_return:                # a return line never belongs to a package go, even with its call=
        add.append(f"FOCC rt={origin + 1.0} p9 path returned actor={ACTOR} call={origin} target=dest result=1 "
                   f"after=1.0 dist={dist}")
    return lines[:start + 1] + add + lines[start + 1:]


class P9PackageDriverTests(unittest.TestCase):
    def test_a_package_walk_that_arrives_passes_and_names_its_driver(self):
        v = probes.check_p9(col(log=drive()))
        self.assertEqual(v.verdict, probes.PASS, v.to_dict())
        last = v.extra["attempts"][-1]
        self.assertEqual(last["driver"], "package")
        self.assertEqual(last["package_after_go"], "00212FDB")
        self.assertIsNone(last["path_result"])
        self.assertIn("DefaultTraveltoLinkedRef", v.extra["driver"])

    def test_a_package_that_did_not_take_is_inconclusive(self):
        v = probes.check_p9(col(log=drive(package=0x2B2000)))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("did not take" in r for r in v.reasons), v.reasons)

    def test_a_package_go_never_takes_a_return_line(self):
        v = probes.check_p9(col(log=drive(stray_return=True)))
        self.assertEqual(v.verdict, probes.PASS, v.to_dict())
        self.assertIsNone(v.extra["attempts"][-1]["path_return_line"])

    def test_a_stall_needs_a_package_control_not_a_scripted_one(self):
        stalled = drive(speed=0.0, offset=200.0)
        package_ctl = drive(start=20.0, seconds=60, offset=100.0)
        v = probes.check_p9(col(log=BASE + package_ctl[1:] + stalled[1:]))
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())
        self.assertTrue(any("package commanded rung" in r for r in v.reasons), v.reasons)
        script_ctl = drive(driver="script", start=20.0, seconds=60, offset=100.0)
        v = probes.check_p9(col(log=BASE + script_ctl[1:] + stalled[1:]))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())   # a PathToReference control proves nothing here

    def test_the_old_scripted_go_reads_as_before(self):
        v = probes.check_p9(col(log=drive(driver="script")))
        self.assertEqual(v.extra["attempts"][-1]["driver"], "script")
        self.assertIsNone(v.extra["attempts"][-1]["package_after_go"])


if __name__ == "__main__":
    unittest.main()
