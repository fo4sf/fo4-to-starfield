"""Hold the producer's read/audit lease while the core checker reads a persistent generation."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading

from stage_outputs import LEASE, PENDING, require_ready_stage


def _command():
    project = Path(__file__).resolve().parents[1] / 'dotnet/TerrainOverlays'
    result = subprocess.run(['dotnet', 'build', str(project), '-c', 'Release', '--nologo', '--verbosity', 'quiet'],
                            capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError('identity checker build failed: ' + result.stdout + result.stderr)
    return ['dotnet', str(project / 'bin/Release/net9.0/TerrainOverlays.dll')]


class HeldIdentityAudit:
    def __init__(self, directory, command=None, timeout=120):
        self.root = Path(os.path.abspath(directory))
        self.timeout = timeout
        self.proc = None
        self.reader = None
        self.errors = tempfile.TemporaryFile(mode='w+t', encoding='utf-8')
        self.lines = queue.Queue()
        try:
            self.proc = subprocess.Popen([*(command or _command()), '--check-identities-held', str(self.root)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errors,
                                         text=True, encoding='utf-8',
                                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.reader = threading.Thread(target=self._read_lines, daemon=True)
            self.reader.start()
            self.report = self._phase('ready')
            if (self.report.get('mode') != 'persistent-identity-audit'
                    or type(self.report.get('checked_ids')) is not int or self.report['checked_ids'] <= 0
                    or self.report.get('artifacts_changed') is not False
                    or self.report.get('record_fields_checked') is not False
                    or self.report.get('native_acceptance') is not False):
                raise RuntimeError('invalid held identity audit report')
            self.require_held(self.root)
        except BaseException:
            self.close()
            raise

    def _read_lines(self):
        try:
            for line in self.proc.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def _phase(self, expected):
        try:
            line = self.lines.get(timeout=self.timeout)
        except queue.Empty as error:
            raise TimeoutError(f'identity audit did not reach {expected}') from error
        if line is None:
            self.errors.seek(0)
            raise RuntimeError(f'identity audit ended before {expected}: {self.errors.read()}')
        value = json.loads(line)
        if not isinstance(value, dict) or value.get('phase') != expected or not isinstance(value.get('report'), dict):
            raise RuntimeError(f'identity audit did not prove {expected}')
        return value['report']

    def require_held(self, directory):
        if Path(os.path.abspath(directory)) != self.root or self.proc.poll() is not None:
            raise RuntimeError('identity audit no longer owns this stage lease')
        if os.path.lexists(self.root / PENDING) or not os.path.lexists(self.root / LEASE):
            raise RuntimeError('identity audit lease/recovery state changed')

    def finish(self):
        self.require_held(self.root)
        self.proc.stdin.write('verify\n')
        self.proc.stdin.flush()
        if self._phase('verified') != self.report or self.proc.wait(timeout=self.timeout) != 0:
            raise RuntimeError('identity generation was not verified after raw checks')
        require_ready_stage(self.root)

    def close(self):
        if self.proc is not None:
            if self.proc.stdin and not self.proc.stdin.closed:
                try:
                    self.proc.stdin.close()  # EOF cancels the owned audit; it never signals verification.
                except OSError:
                    pass  # Preserve the original failure if the child already closed its pipe.
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()  # Only this process, created above; never a game or another controller.
                self.proc.wait(timeout=5)
            if self.reader is not None:
                self.reader.join(timeout=1)
            self.proc.stdout.close()
        self.errors.close()


@contextmanager
def persistent_verification(directory, command=None, timeout=120):
    require_ready_stage(directory)
    with open(Path(directory) / 'overlays_params.json', encoding='utf-8') as stream:
        params = json.load(stream)
    enabled = params.get('persistent_ids', False)
    if type(enabled) is not bool:
        raise ValueError('persistent_ids must be a boolean')
    if not enabled:
        if os.path.lexists(Path(directory) / 'terrain-stable-ids.json'):
            raise ValueError('an existing identity ledger requires explicit persistent_ids')
        yield None
        return
    audit = HeldIdentityAudit(directory, command=command, timeout=timeout)
    try:
        yield audit
        audit.finish()
    finally:
        audit.close()
