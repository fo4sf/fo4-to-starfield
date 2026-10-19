"""Mod manifest resolver draft (src/fo4sf/launcher/mods.py) on synthetic manifests."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import mods  # noqa: E402

CORE = ["FO4TerrainCore.esm", "FO4Port.esm"]


def mod(mid, plugins=None, **kw):
    m = {"id": mid, "version": "1.0", "core": ">=0.1, <0.2", "plugins": plugins or [f"{mid}.esm"]}
    m.update(kw)
    return m


def resolve(ms, **kw):
    kw.setdefault("core_version", "0.1.3")
    return mods.resolve(ms, core_plugins=CORE, **kw)


class ModTests(unittest.TestCase):
    def test_core_first_then_dependency_order_with_id_ties(self):
        plugins, order = resolve([mod("zeta"), mod("alpha", requires=["zeta"]), mod("beta")])
        self.assertEqual(order, ["beta", "zeta", "alpha"])
        self.assertEqual(plugins[:2], CORE)
        self.assertEqual(plugins[2:], ["beta.esm", "zeta.esm", "alpha.esm"])

    def test_same_order_whatever_the_input_order(self):
        ms = [mod("c", load_after=["a"]), mod("a"), mod("b", requires=["a"])]
        self.assertEqual(resolve(ms)[0], resolve(list(reversed(ms)))[0])

    def test_load_after_absent_mod_is_ignored(self):
        self.assertEqual(resolve([mod("a", load_after=["missing"])])[1], ["a"])

    def test_refusals(self):
        cases = [
            ([mod("a", requires=["b"])], "requires b"),
            ([mod("a", requires=["b"]), mod("b", requires=["a"])], "cycle"),
            ([mod("a", core=">=0.2")], "needs core"),
            ([mod("a", starfield="1.0.0")], "pinned to Starfield"),
            ([mod("a"), mod("a")], "listed twice"),
            ([mod("a", plugins=["FO4Port.esm"])], "belongs to core"),
            ([mod("a", plugins=["x.esm"]), mod("b", plugins=["X.ESM"])], "belongs to a"),
            ([mod("Bad Id")], "id"),
            ([mod("a", plugins=["readme.txt"])], "plugins"),
            ([mod("a", version="1.x")], "version"),
            ([mod("a", core="~1")], "constraint"),
            ([mod("a", requires=["a"])], "itself"),
        ]
        for ms, why in cases:
            with self.subTest(why=why):
                with self.assertRaisesRegex(mods.ModError, why):
                    resolve(ms, starfield_version="1.15.222.0")

    def test_all_refusals_reported_together(self):
        with self.assertRaises(mods.ModError) as e:
            resolve([mod("a", requires=["x"]), mod("b", core=">=9")])
        self.assertIn("requires x", str(e.exception))
        self.assertIn("needs core", str(e.exception))

    def test_version_compare(self):
        self.assertTrue(mods.satisfies("0.1.10", ">=0.1.2, <0.2"))
        self.assertFalse(mods.satisfies("0.2", ">=0.1, <0.2"))
        self.assertTrue(mods.satisfies("1", "==1.0.0.0"))


if __name__ == "__main__":
    unittest.main()
