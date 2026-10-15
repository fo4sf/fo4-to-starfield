"""Budget pauses must remain resumable; controls and observations are synthetic."""
import json
from pathlib import Path
import tempfile
import unittest

import test_testqueue as fixtures


class QueueBudgetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        fixtures.make_queue(str(self.folder))
        self.original_queue = (self.folder / 'queue.json').read_bytes()
        self.calls = []

    def runner(self, **options):
        def step(test, out):
            self.calls.append(test['id'])
            fixtures.jdump({'end_read': '0 0 0.1', 'shot': fixtures.touch(out, 'fall.png')},
                           str(Path(out) / 'obs.json'))
            return 0

        run = fixtures.tq.Runner(str(self.folder), fixtures.args(**options),
                                ctl=fixtures.FakeControls(), step=step)
        run.session, run.cell = True, 'C'
        run._ps = lambda *args, **kwargs: self.fail('the simulated cell needs no game setup')
        return run

    def state(self):
        return json.loads((self.folder / 'state.json').read_text())

    def test_test_limit_returns_pause_and_resume_only_runs_pending_tests(self):
        self.assertEqual(self.runner(max_tests=1).run(), 4)
        self.assertEqual(self.calls, ['0000_fall'])
        self.assertEqual(self.state()['status'], 'paused (2 left)')
        report = json.loads((self.folder / 'report.json').read_text())
        self.assertEqual(report['pending'], 2)
        self.assertEqual(self.runner().run(), 0)
        self.assertEqual(self.calls, ['0000_fall', '0001_fall', '0002_fall'])
        self.assertEqual(self.state()['status'], 'finished')
        self.assertEqual((self.folder / 'queue.json').read_bytes(), self.original_queue)

    def test_expired_time_budget_returns_pause_without_game_input(self):
        self.assertEqual(self.runner(max_hours=0).run(), 4)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state()['done'], {})
        self.assertEqual(self.state()['status'], 'paused (3 left)')

    def test_dry_run_remains_a_successful_preview_without_completing_tests(self):
        self.assertEqual(self.runner(dry_run=True, max_tests=1).run(), 0)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state()['done'], {})
        self.assertNotEqual(self.state()['status'], 'finished')

    def test_already_completed_queue_succeeds_even_with_no_budget(self):
        self.assertEqual(self.runner().run(), 0)
        self.calls.clear()
        self.assertEqual(self.runner(max_hours=0, max_tests=0).run(), 0)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.state()['status'], 'finished')
