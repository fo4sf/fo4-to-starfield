"""#458 task 7: every src/fo4sf/launcher/ module imports with python -I, stdlib only, no Data/ read."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = "--probe-launcher-imports"


def _is_allowed(name, stdlib):
    top = name.split(".")[0]
    if top in {"fo4sf", "__main__", "__mp_main__"}:
        return True
    if top in stdlib:
        return True
    if name.startswith("_frozen_importlib"):
        return True
    return False


def non_stdlib_tops(names, stdlib):
    return sorted({n.split(".")[0] for n in names if not _is_allowed(n, stdlib)})


def probe(root):
    """Run inside `python -I`. Print non-stdlib modules or Data/ opens, then exit 1 if any."""
    before = set(sys.modules)
    src = os.path.join(root, "src")
    sys.path.insert(0, src)
    data_opens = []

    def hook(event, args):
        if event != "open":
            return
        path = args[0]
        if isinstance(path, int):
            return
        try:
            text = os.fsdecode(path)
        except (TypeError, ValueError):
            return
        parts = os.path.normpath(text).replace("\\", "/").split("/")
        if "Data" in parts:
            data_opens.append(text)

    sys.addaudithook(hook)

    import pkgutil
    import fo4sf.launcher as pkg
    loaded = []
    for info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        __import__(info.name)
        loaded.append(info.name)

    stdlib = set(sys.stdlib_module_names)
    bad = non_stdlib_tops(set(sys.modules) - before, stdlib)
    print("loaded:" + ",".join(loaded))
    if bad:
        print("non-stdlib:" + ",".join(bad))
    if data_opens:
        print("data-open:" + "\n".join(data_opens))
    if bad or data_opens:
        raise SystemExit(1)


class LauncherStdlibTests(unittest.TestCase):
    def test_preloaded_sitecustomize_is_ignored(self):
        stdlib = set(sys.stdlib_module_names)
        before = {"sitecustomize", "_distutils_hack", "os", "sys"}
        after = before | {"fo4sf.launcher", "fo4sf.launcher.settings", "pkgutil"}
        self.assertEqual(non_stdlib_tops(after - before, stdlib), [])

    def test_new_non_stdlib_after_imports_is_reported(self):
        stdlib = set(sys.stdlib_module_names)
        before = {"os", "sys"}
        after = before | {"numpy", "fo4sf.launcher"}
        self.assertEqual(non_stdlib_tops(after - before, stdlib), ["numpy"])

    def test_every_launcher_module_imports_stdlib_only_in_isolated_python(self):
        r = subprocess.run(
            [sys.executable, "-I", os.path.abspath(__file__), PROBE, ROOT],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(r.returncode, 0, r.stdout + "\n" + r.stderr)
        self.assertIn("loaded:", r.stdout)
        self.assertNotIn("non-stdlib:", r.stdout)
        self.assertNotIn("data-open:", r.stdout)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == PROBE:
        probe(sys.argv[2])
    else:
        unittest.main()
