"""Content receipts for core64c's identity and test inputs; no allocation or semantic acceptance."""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat

from stage_outputs import require_ready_stage


def _ordinary(path, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ValueError(f'linked check input is unsupported: {path.name}')
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError(f'check input is not an ordinary {"directory" if directory else "file"}: {path.name}')
    return info


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'duplicate check-input parameter: {key}')
        value[key] = item
    return value


def identity_inputs(directory):
    """Hash the exact local inputs used by core64c check, plus its retained identity ledger.

    This is a freshness receipt under the existing immutable-stage/cooperating-writer protocol,
    not a ledger validator or an atomic snapshot against arbitrary concurrent file edits.
    """
    require_ready_stage(directory)
    root = Path(os.path.abspath(directory))
    _ordinary(root, directory=True)
    files = {}

    def read(name, content=False):
        if not isinstance(name, str) or not name or PureWindowsPath(name).drive or name.startswith(('/', '\\')):
            raise ValueError('check inputs must be relative stage paths')
        parts = name.replace('\\', '/').split('/')
        if any(p in ('', '.', '..') or ':' in p for p in parts):
            raise ValueError('check input path escapes or aliases the stage')
        path = root
        for part in parts[:-1]:
            path = path / part
            _ordinary(path, directory=True)
        path = path / parts[-1]
        before = _ordinary(path)
        digest = hashlib.sha256()
        data = []
        with path.open('rb') as stream:
            if _signature(before) != _signature(os.fstat(stream.fileno())):
                raise ValueError(f'check input changed before reading: {name}')
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                if content:
                    data.append(chunk)
            if _signature(before) != _signature(os.fstat(stream.fileno())):
                raise ValueError(f'check input changed while reading: {name}')
        if _signature(before) != _signature(_ordinary(path)):
            raise ValueError(f'check input replaced while reading: {name}')
        files['/'.join(parts)] = {'bytes': before.st_size, 'sha256': digest.hexdigest()}
        return b''.join(data) if content else None

    params = json.loads(read('overlays_params.json', content=True), object_pairs_hook=_unique)
    if not isinstance(params, dict):
        raise ValueError('check parameters must be an object')
    if 'persistent_ids' in params and type(params['persistent_ids']) is not bool:
        raise ValueError('persistent_ids must be a boolean')
    names = {'formids.json', 'objects.json', 'plan.json', 'expected.json'}
    for key in ('objects', 'navmesh'):
        if params.get(key) is not None:
            if not isinstance(params[key], str) or not params[key]:
                raise ValueError(f'{key} must name a stage file')
            names.add(params[key])
    ledger = 'terrain-stable-ids.json'
    if params.get('persistent_ids') is True:
        names.add(ledger)
    elif os.path.lexists(root / ledger):
        raise ValueError('an existing identity ledger requires explicit persistent_ids')
    for name in sorted(names):
        read(name)
    require_ready_stage(directory)
    return {'schema': 1, 'files': files}
