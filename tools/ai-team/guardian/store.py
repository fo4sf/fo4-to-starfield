"""SQLite history for the Resource Guardian: local inference jobs, throttling decisions, resource samples and the
pause / stop switch. One file (guardian.db), WAL mode so the proxy and the status command can read and write at once.

Runtime state lives OUTSIDE the repository (%LOCALAPPDATA%\\fo4-ai-team\\state, or $FO4_AI_TEAM_STATE): logs hold
machine paths, and scripts/guard.py scans the whole working tree, ignored files included.
"""
import json
import os
import sqlite3
import time

STATE = os.environ.get("FO4_AI_TEAM_STATE") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "fo4-ai-team", "state")
DB = os.path.join(STATE, "guardian.db")
PICK = "model_pick"                   # control rows tools/ai-team/models.py writes: the team's model,
HOLD = "model_hold"                   # and the swap that holds the proxy while the model changes
HOLD_FRESH_S = 900                    # a load takes a few minutes; a "loading" hold older than this lost its loader

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, model TEXT, kind TEXT, status TEXT,
  created REAL, started REAL, finished REAL, heartbeat REAL, queued_s REAL, latency_s REAL,
  prompt_tokens INTEGER, completion_tokens INTEGER, tokens_source TEXT, error TEXT, owner_pid INTEGER);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, job_id INTEGER, decision TEXT, level TEXT, reasons TEXT);
CREATE TABLE IF NOT EXISTS samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL, level TEXT, vram_pct REAL, ram_pct REAL, cpu_pct REAL,
  gpu_util REAL, lm_reachable INTEGER, simulated INTEGER);
CREATE TABLE IF NOT EXISTS control (key TEXT PRIMARY KEY, value TEXT, t REAL);
"""


def connect():
    os.makedirs(STATE, exist_ok=True)
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    return c


def get_mode(c):
    """running | paused | stopped (manual switch)."""
    r = c.execute("SELECT value FROM control WHERE key='mode'").fetchone()
    return r[0] if r else "running"


def set_mode(c, mode):
    c.execute("INSERT OR REPLACE INTO control VALUES ('mode', ?, ?)", (mode, time.time()))


def get_pick(c):
    """The setup tools/ai-team/models.py picked (a dict), or None: no pick yet, or a row it cannot read."""
    r = c.execute("SELECT value FROM control WHERE key=?", (PICK,)).fetchone()
    try:
        pick = json.loads(r[0]) if r else None
    except ValueError:
        return None
    if not isinstance(pick, dict) or not {"model", "context", "output", "kv", "gpu"} <= pick.keys():
        return None                                 # then models.py and the proxy both fall back to the default
    return pick


def set_pick(c, pick):
    c.execute("INSERT OR REPLACE INTO control VALUES (?, ?, ?)", (PICK, json.dumps(pick), time.time()))


def picked_model(c=None):
    """The LM Studio model id models.py picked, or None: the proxy then keeps config.json's agent map."""
    own = c is None
    c = connect() if own else c
    try:
        model = (get_pick(c) or {}).get("model")
    finally:
        if own:
            c.close()
    return model if isinstance(model, str) and model else None


def get_hold(c):
    """models.py's model swap: None, or (state, detail, age in s). "loading" while a load runs (the proxy queues),
    "failed" after a load that did not work (the proxy refuses until a load works). A "loading" hold older than
    HOLD_FRESH_S is a loader that died mid-load: it counts as failed, since the old model may already be unloaded."""
    r = c.execute("SELECT value, t FROM control WHERE key=?", (HOLD,)).fetchone()
    if not r:
        return None
    try:
        h = json.loads(r[0])
        state, detail = h["state"], str(h.get("detail", ""))
    except (ValueError, KeyError, TypeError):
        return "failed", "unreadable model hold", 0.0
    age = time.time() - r[1]
    if state == "loading" and age > HOLD_FRESH_S:
        return "failed", f"a load of {detail} did not finish (the loader stopped)", age
    return state, detail, age


def take_hold(c, model):
    """Start a swap: True, or False while another loader's fresh "loading" hold stands (one load at a time). One
    transaction, so two loaders cannot both take it."""
    c.execute("BEGIN IMMEDIATE")
    try:
        h = get_hold(c)
        if h and h[0] == "loading":
            c.execute("ROLLBACK")
            return False
        c.execute("INSERT OR REPLACE INTO control VALUES (?, ?, ?)",
                  (HOLD, json.dumps({"state": "loading", "detail": model}), time.time()))
        c.execute("COMMIT")
        return True
    except BaseException:
        c.execute("ROLLBACK")
        raise


def fail_hold(c, detail):
    c.execute("INSERT OR REPLACE INTO control VALUES (?, ?, ?)",
              (HOLD, json.dumps({"state": "failed", "detail": detail}), time.time()))


def clear_hold(c):
    c.execute("DELETE FROM control WHERE key=?", (HOLD,))


def log_decision(c, job_id, decision, lv, reasons):
    c.execute("INSERT INTO decisions (t, job_id, decision, level, reasons) VALUES (?,?,?,?,?)",
              (time.time(), job_id, decision, lv, json.dumps(reasons)))


def log_sample(c, snap, lv):
    g = snap.get("gpu", {})
    c.execute("INSERT INTO samples (t, level, vram_pct, ram_pct, cpu_pct, gpu_util, lm_reachable, simulated) "
              "VALUES (?,?,?,?,?,?,?,?)",
              (time.time(), lv, g.get("vram_pct"), snap["ram"]["used_pct"], snap["cpu"]["utilization_pct"],
               g.get("utilization_pct"), int(bool(snap["lmstudio"].get("reachable"))), int("simulated" in snap)))


def recover_stale(c, stale_after_s=120):
    """Restart recovery: jobs left 'running' or 'queued' by a proxy that died are marked 'abandoned'."""
    cut = time.time() - stale_after_s
    n = c.execute("UPDATE jobs SET status='abandoned', finished=?, error='proxy restarted or heartbeat lost' "
                  "WHERE status IN ('running','queued') AND COALESCE(heartbeat, created) < ?",
                  (time.time(), cut)).rowcount
    return n
