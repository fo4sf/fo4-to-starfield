"""team.py board: community reports wait for the owner's triage and are never offered to an agent."""
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "ai-team"))
import team  # noqa: E402


def issue(n, *labels):
    return {"number": n, "title": f"t{n}", "labels": [{"name": l} for l in labels], "updatedAt": "", "closedAt": ""}


class BoardTriageTests(unittest.TestCase):
    def board(self, issues):
        def gh(args):
            if "pr" in args:
                return []
            return [] if "closed" in args else issues
        out = io.StringIO()
        with mock.patch.object(team, "_gh", gh), mock.patch.object(team, "contributions", lambda i, p: {}), \
                contextlib.redirect_stdout(out):
            team.board()
        return json.loads(out.getvalue())

    def test_a_community_report_is_only_in_triage(self):
        b = self.board([issue(1, "community", "needs-triage"), issue(2, "community", "needs-triage", "ready"),
                        issue(3, "ready"), issue(4)])
        self.assertEqual([i["number"] for i in b["community_triage"]], [1, 2])
        self.assertEqual([i["number"] for i in b["available"]], [3], "needs-triage beats ready")
        self.assertEqual([i["number"] for i in b["owner_inbox"]], [4])

    def test_a_triaged_community_report_becomes_an_ordinary_task(self):
        b = self.board([issue(5, "community", "ready")])
        self.assertEqual(b["community_triage"], [])
        self.assertEqual([i["number"] for i in b["available"]], [5])


if __name__ == "__main__":
    unittest.main()
