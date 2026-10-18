"""The Guardian proxy forwards upstream header values only after removing control characters
(CodeQL py/http-response-splitting on proxy.py)."""
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARDIAN = os.path.join(HERE, "..", "tools", "ai-team", "guardian")


def _load_proxy():
    sys.path.insert(0, GUARDIAN)
    try:
        spec = importlib.util.spec_from_file_location("guardian_proxy_under_test", os.path.join(GUARDIAN, "proxy.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(GUARDIAN)


class HeaderValueTests(unittest.TestCase):
    def test_crlf_and_control_characters_are_removed(self):
        proxy = _load_proxy()
        self.assertEqual(proxy.header_value("text/plain\r\nX-Injected: 1"), "text/plainX-Injected: 1")
        self.assertEqual(proxy.header_value("a\x00b\x7fc"), "abc")

    def test_missing_value_gives_the_default(self):
        proxy = _load_proxy()
        self.assertEqual(proxy.header_value(None, "application/json"), "application/json")
        self.assertIsNone(proxy.header_value(None))

    def test_plain_value_is_unchanged(self):
        proxy = _load_proxy()
        self.assertEqual(proxy.header_value("application/json; charset=utf-8"), "application/json; charset=utf-8")


if __name__ == "__main__":
    unittest.main()
