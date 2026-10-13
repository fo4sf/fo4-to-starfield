"""Read-only audit of completed Commonwealth phase observations.

--campaign <prepared folder> --phase <phase name>
Exit0: observations match; exit1: mismatch; exit2: incomplete/unusable evidence.
These exits never establish walking, visual quality or runtime acceptance.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image


NAME = re.compile(r"[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_-])?\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
XY_TOLERANCE_M = 2.0
HEIGHT_TOLERANCE_M = 0.5


def file_bytes(root, name):
    """Evidence filenames are relative and confined to the selected result tree."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("unsafe evidence filename")
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("linked evidence outside its result directory")
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("evidence changed while reading")
    return data, {"file": name, "physical_identity": [after.st_dev, after.st_ino],
                  "sha256": hashlib.sha256(data).hexdigest(),
                  "bytes": len(data), "mtime_ns": after.st_mtime_ns}


def snapshot(root, name):
    raw, identity = file_bytes(root, name)
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError('expected an evidence object')
    return value, identity


def xyz(read):
    if not isinstance(read, str):
        return None
    try:
        values = [float(v) for v in read.split()]
    except ValueError:
        return None
    return values if len(values) == 3 and all(math.isfinite(v) for v in values) else None


def vector(values):
    return isinstance(values, list) and len(values) == 3 and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def valid_plan(points):
    return isinstance(points, list) and bool(points) and all(
        isinstance(p, dict) and isinstance(p.get('label'), str) and p['label']
        and vector([p.get('x'), p.get('y'), p.get('expect')]) for p in points)


def capture(root, name):
    data, identity = file_bytes(root, name)
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG":
            raise ValueError("capture is not PNG")
        identity["dimensions"] = list(image.size)
        image.verify()
    # verify() checks the container; load() also decodes the pixel data.
    with Image.open(io.BytesIO(data)) as image:
        image.load()
    return identity


def inspect_test(test, obs, folder):
    issues, rows, captures = [], [], set()
    offset, spawn, local = obs.get("offset"), xyz(obs.get("spawn_read")), test.get("spawn_local")
    if obs.get("offset_from") != "spawn" or not vector(offset) or not vector(local) or spawn is None:
        return {"id": test["id"], "issues": [{"status": "INCONCLUSIVE", "class": "FRAME"}], "points": []}
    if any(abs(a - b - c) > 0.00001 for a, b, c in zip(spawn, local, offset)):
        return {"id": test["id"], "issues": [{"status": "INCONCLUSIVE", "class": "FRAME"}], "points": []}
    expected, observed = test.get("points") or [], obs.get("points") or []
    if not valid_plan(expected):
        raise ValueError('invalid planned points')
    if not isinstance(observed, list) or not all(isinstance(o, dict) for o in observed) \
            or len(expected) != len(observed):
        return {"id": test["id"], "issues": [{"status": "INCONCLUSIVE", "class": "POINT_COUNT"}], "points": []}
    if len({p['label'] for p in expected}) != len(expected) or any(
            p.get("label") != o.get("label") for p, o in zip(expected, observed)):
        return {"id": test["id"], "issues": [{"status": "INCONCLUSIVE", "class": "POINT_LABEL"}], "points": []}
    ref_index = next((i for i, p in enumerate(expected) if p.get("label") == test.get("z_ref")), None)
    ref_read = xyz(observed[ref_index].get("read")) if ref_index is not None else None
    if ref_read is None:
        return {"id": test["id"], "issues": [{"status": "INCONCLUSIVE", "class": "REFERENCE"}], "points": []}
    reference_shift = ref_read[2] - expected[ref_index]["expect"]
    for plan, actual in zip(expected, observed):
        row = {"label": plan["label"], "expected_local": [plan["x"], plan["y"], plan["expect"]]}
        read = xyz(actual.get("read"))
        row["observed"] = read
        try:
            image = capture(folder, actual.get("shot"))
            capture_id = tuple(image['physical_identity'])
            if capture_id in captures:
                raise ValueError("one capture path reused for different probe invocations")
            captures.add(capture_id)
            row["capture"] = image
        except (OSError, ValueError, TypeError, SyntaxError, Image.DecompressionBombError) as error:
            row["capture_error"] = str(error)
        if read is None or "capture_error" in row:
            row.update(status="INCONCLUSIVE", classification="CAPTURE" if "capture_error" in row else "UNREAD")
        else:
            xy_error = math.hypot(read[0] - plan["x"] - offset[0], read[1] - plan["y"] - offset[1])
            z_error = read[2] - reference_shift - plan["expect"]
            row.update(xy_error_m=xy_error, relative_z_error_m=z_error)
            if xy_error > XY_TOLERANCE_M:
                row.update(status="INCONCLUSIVE", classification="MOVED")
            elif abs(z_error) > HEIGHT_TOLERANCE_M:
                row.update(status="MISMATCH", classification="HEIGHTS")
            else:
                row.update(status="MATCH", classification="MATCH")
        if row["status"] != "MATCH":
            issues.append({"status": row["status"], "class": row["classification"], "label": plan["label"]})
        rows.append(row)
    # A misplaced reference must invalidate every relative height, not silently normalize them.
    if rows[ref_index]["status"] == "INCONCLUSIVE":
        issues.append({"status": "INCONCLUSIVE", "class": "REFERENCE"})
        for row in rows:
            row["status"] = "INCONCLUSIVE"
            row["classification"] = "REFERENCE"
    post = {"acceptance_gate": False, "observed": xyz(obs.get("beyond_read"))}
    target = test.get("beyond")
    if target:
        if not isinstance(target, dict) or not vector([target.get('x'), target.get('y'), 0]):
            raise ValueError('invalid planned post-probe position')
        post["expected_merged_xy"] = [target["x"] + offset[0], target["y"] + offset[1]]
        if post["observed"] is None:
            post.update(status="INCONCLUSIVE", classification="POST_UNREAD")
        else:
            post["xy_error_m"] = math.dist(post['expected_merged_xy'], post['observed'][:2])
            post.update(status="MATCH" if post["xy_error_m"] <= XY_TOLERANCE_M else "MISMATCH",
                        classification="POST_FRAME")
        try:
            post["capture"] = capture(folder, obs.get("beyond_shot"))
            if tuple(post['capture']['physical_identity']) in captures:
                raise ValueError("post-probe capture reuses a point capture")
        except (OSError, ValueError, TypeError, SyntaxError, Image.DecompressionBombError) as error:
            post.update(status="INCONCLUSIVE", classification="POST_CAPTURE", capture_error=str(error))
        if post["status"] != "MATCH":
            issues.append({"status": post["status"], "class": post["classification"]})
    else:
        post["status"] = "NOT_REQUESTED"
    return {"id": test['id'], "offset": offset, "reference_z_shift": reference_shift,
            "issues": issues, "points": rows, "post_probe": post}


def inspect_phase(root, phase):
    root = Path(root).resolve()
    if not NAME.fullmatch(phase):
        raise ValueError("unsafe phase name")
    manifest, identity = snapshot(root, "campaign.json")
    details = manifest["phases"][phase]
    folder = root / phase
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise ValueError("linked phase outside the campaign")
    queue, queue_identity = snapshot(folder, "queue.json")
    if not isinstance(queue.get('commit'), str) or not COMMIT.fullmatch(queue['commit']) \
            or not isinstance(manifest.get('runner_commit'), str) or not COMMIT.fullmatch(manifest['runner_commit']) \
            or queue_identity["sha256"] != details["queue_sha256"] or queue["commit"] != manifest["runner_commit"]:
        raise ValueError("phase queue differs from campaign pins")
    tests = queue.get('tests')
    if not isinstance(tests, list) or not tests or any(not isinstance(t, dict)
            or not isinstance(t.get('id'), str) or not NAME.fullmatch(t['id'])
            or not valid_plan(t.get('points')) for t in tests) \
            or len({t['id'] for t in tests}) != len(tests) \
            or sum(len(t['points']) for t in tests) != details['points']:
        raise ValueError('invalid campaign test inventory')
    state, state_identity = snapshot(folder, "state.json")
    raw, result_identity = file_bytes(folder, "results.jsonl")
    records = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    if not isinstance(state.get('done', {}), dict) or not isinstance(state.get('attempts', {}), dict) \
            or any(not isinstance(r, dict) or type(r.get('attempt')) is not int or r['attempt'] < 1
                   for r in records):
        raise ValueError('invalid terminal attempt evidence')
    entries, issues = [], []
    for test in queue["tests"]:
        tid = test['id']
        done = state.get('done', {}).get(tid, {})
        if not isinstance(done, dict):
            raise ValueError('invalid terminal done entry')
        attempt = done.get('attempts')
        result = [r for r in records if r.get('id') == tid and r.get('attempt') == attempt]
        if not NAME.fullmatch(tid) or type(attempt) is not int or attempt < 1 or len(result) != 1 \
                or type(state.get('attempts', {}).get(tid)) is not int \
                or state['attempts'][tid] != attempt or state.get('status') != 'finished' \
                or any(r['attempt'] > attempt for r in records if r.get('id') == tid):
            entries.append({'id': tid, 'issues': [{'status': 'INCONCLUSIVE', 'class': 'ATTEMPT'}], 'points': []})
            continue
        record = result[0]
        if record.get('verdict') != done.get('verdict') or record.get('class') != done.get('class') \
                or record.get('verdict') not in ('PASS', 'FAIL', 'INCONCLUSIVE'):
            raise ValueError('terminal result and state disagree')
        attempt_folder = folder / 'tests' / tid / f'a{attempt}'
        if not attempt_folder.resolve().is_relative_to(folder.resolve()):
            raise ValueError('attempt escapes phase directory')
        try:
            obs, obs_identity = snapshot(attempt_folder, 'obs.json')
            entry = inspect_test(test, obs, attempt_folder)
            entry.update(attempt=attempt, observation=obs_identity, reported_verdict=record['verdict'])
            if record['verdict'] == 'INCONCLUSIVE':
                entry['issues'].append({'status': 'INCONCLUSIVE', 'class': 'REPORTED_INCONCLUSIVE'})
            elif record['verdict'] == 'FAIL':
                entry['issues'].append({'status': 'MISMATCH', 'class': 'REPORTED_FAILURE'})
            entries.append(entry)
        except (OSError, ValueError, TypeError, KeyError) as error:
            entries.append({'id': tid, 'issues': [{'status': 'INCONCLUSIVE', 'class': 'OBSERVATION', 'detail': str(error)}], 'points': []})
    issues = [i for entry in entries for i in entry['issues']]
    status = 'INCONCLUSIVE' if any(i['status'] == 'INCONCLUSIVE' for i in issues) else 'MISMATCH' if issues else 'MATCH'
    return {'phase': phase, 'status': status, 'runtime_accepted': False,
            'scope': 'sampled point/coordinate and artifact audit; manual capture review and installed-input verification still required',
            'campaign': identity, 'queue': queue_identity, 'state': state_identity, 'results': result_identity,
            'informational': not details['acceptance_gate'],
            'launch_hold': any(i['class'].startswith('POST_') for i in issues),
            'height_matches': sum(p['status'] == 'MATCH' for e in entries for p in e['points']),
            'expected_points': sum(len(t['points']) for t in queue['tests']), 'entries': entries}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--phase', required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect_phase(args.campaign, args.phase)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'status': 'INCONCLUSIVE', 'runtime_accepted': False, 'error': str(error)}))
        return 2
    print(json.dumps(report, indent=2, allow_nan=False))
    return {'MATCH': 0, 'MISMATCH': 1, 'INCONCLUSIVE': 2}[report['status']]


if __name__ == '__main__':
    sys.exit(main())
