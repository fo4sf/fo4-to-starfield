"""Pick the model the local team runs on, and load it in LM Studio (LM Studio Python SDK, `pip install --user lmstudio`).

  python models.py list                     the presets (config.json "models"), the pick, and what LM Studio has
                                            loaded; JSON
  python models.py pick <preset>             load a preset and make it the pick (the proxy follows the pick at once,
                                            so the pick changes only with a load that worked)
  python models.py ensure                   load the pick unless LM Studio already has it loaded at its context
  python models.py opencode                 OpenCode's inline config for the pick (OPENCODE_CONFIG_CONTENT): the four
                                            agents' context and output limits
  python models.py opencode --cloud <name>   the same for Claude in the owner's terminal: the four agents on the named
                                            config.json "cloud" model (Anthropic API, the anthropic provider in
                                            opencode.json); .opencode/plugin/fo4-cloud-cap.js holds its spend

The pick is a row in the guardian's database (store.PICK, in the team's state folder); with no pick the default preset
is used. Only the presets can be picked (the owner's choice, 30 Oct: the measured setups only), and the row holds the
preset's name: its numbers are read from config.json each time, so a row from an older build or another name falls
back to the default. The guardian proxy sends every agent's requests to the picked model, and terminal.ps1 and run-lead.ps1 hand
the pick's limits to OpenCode, so OpenCode compacts at the window that is loaded and asks for no more output than fits.

A load holds the proxy while the model changes (store.HOLD): new requests wait in its queue and go to the new model
once it is in. The hold is taken before running requests are counted, so none starts in between; a load refuses while
one runs (unloading cuts an active generation) and while another load holds. It unloads the team's other models first
(ids a preset names, and the last pick: a model you loaded by hand for something else stays). If the load fails after
that, the hold stays as "failed" and the proxy refuses requests (HTTP 503, `guardian.py status` shows why) until a load
works, instead of sending them to a model that is not there. A loader that stops mid-load leaves a "loading" hold that
counts as failed after store.HOLD_FRESH_S. The owner's pause and stop switch are never touched.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                          # -I leaves the script's own folder off sys.path (load_model)
sys.path.insert(0, os.path.join(HERE, "guardian"))
import store       # noqa: E402
import load_model  # noqa: E402

CONFIG = os.path.join(HERE, "config.json")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/@-]{0,127}")
KV_TYPES = ("f16", "q8_0", "q4_0")


class PickError(Exception):
    pass


def read_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def setup(model, context, output=None, kv="f16", gpu=None, preset=None, key=None):
    """A checked setup. Output defaults to a quarter of the window, at most 16K; at least half the window stays for
    the conversation, since OpenCode compacts at context minus output."""
    if not isinstance(model, str) or not MODEL_ID.fullmatch(model):
        raise PickError(f"not an LM Studio model id: {model!r}")
    key = model if key is None else key           # the model LM Studio loads; model is the id it gets
    if not isinstance(key, str) or not MODEL_ID.fullmatch(key):
        raise PickError(f"not an LM Studio model key: {key!r}")
    if not isinstance(context, int) or not 4096 <= context <= 262144:
        raise PickError("context must be 4096..262144 tokens")
    output = min(16384, context // 4) if output is None else output
    if not isinstance(output, int) or not 1024 <= output <= context // 2:
        raise PickError("output must be 1024 tokens up to half the context")
    if kv not in KV_TYPES:
        raise PickError(f"kv must be one of {', '.join(KV_TYPES)}")
    if gpu is not None and not (isinstance(gpu, (int, float)) and 0 <= gpu <= 1):
        raise PickError("gpu must be 0..1")
    return {"preset": preset, "model": model, "key": key, "context": context, "output": output, "kv": kv, "gpu": gpu}


def preset(name, cfg=None):
    cfg = cfg or read_config()
    p = cfg["models"].get(name)
    if p is None:
        raise PickError(f"no preset {name!r}; presets: {', '.join(cfg['models'])}")
    return setup(p["model"], p["context"], p["output"], p["kv"], p["gpu"], preset=name, key=p.get("key"))


def current(cfg=None, c=None):
    """The picked preset, or the default preset when there is no pick or the row does not name a preset."""
    cfg = cfg or read_config()
    own = c is None
    c = store.connect() if own else c
    try:
        return preset(store.get_pick(c)["preset"], cfg)
    except (KeyError, TypeError, PickError):
        return preset(cfg["default_model"], cfg)
    finally:
        if own:
            c.close()


def save(s, c=None):
    """A database row, not a file: the proxy reads it while this writes, and on Windows a file the proxy has open
    cannot be replaced."""
    own = c is None
    c = store.connect() if own else c
    try:
        store.set_pick(c, s)
    finally:
        if own:
            c.close()


def opencode_config(s, cfg=None):
    """The inline OpenCode config for a setup: every team agent's model gets the setup's window and output. OpenCode
    merges it over opencode.json, so the names, tool_call and provider settings there stay."""
    cfg = cfg or read_config()
    limit = {"context": s["context"], "output": s["output"]}
    return {"provider": {"guardian": {"models": {a: {"limit": dict(limit)} for a in cfg["agents"]}}}}


def cloud_config(name, cfg=None):
    """The inline OpenCode config that puts the four agents on a config.json "cloud" model. OpenCode merges it after
    .opencode/agents, so each agent's model is this one; the limits are opencode.json's for that model."""
    cfg = cfg or read_config()
    model = cfg.get("cloud", {}).get("models", {}).get(name)
    if model is None:
        raise PickError(f"no cloud model {name!r}; cloud models: {', '.join(cfg.get('cloud', {}).get('models', {}))}")
    model = "anthropic/" + model
    return {"model": model, "agent": {a: {"model": model} for a in cfg["agents"]}}


def team_models(cfg):
    """The ids the team's models load under, and the keys LM Studio lists the presets under: a copy loaded by hand in
    LM Studio's window gets its key as its id (unsloth/qwen3.6-35b-a3b, say), and would sit beside the pick."""
    presets = cfg["models"].values()
    return ({p["model"] for p in presets} | {p["key"] for p in presets if p.get("key")} |
            set(cfg["agents"].values()))


def loaded_contexts():
    """{identifier: context length} of what LM Studio has loaded; None for a length the SDK does not report."""
    import lmstudio as lms                         # here, so the tests import this module without the SDK installed
    out = {}
    for m in lms.get_default_client().llm.list_loaded():
        try:
            out[m.identifier] = m.get_context_length()
        except Exception:                          # an older SDK: the id still counts
            out[m.identifier] = None
    return out


def load(s, cfg, force=False):
    """Load a setup and make it the pick, holding the proxy meanwhile (see the module notes)."""
    c = store.connect()
    try:
        prev = store.take_hold(c, s["model"])
        if prev is None:
            raise PickError("another model load is running (guardian.py status shows it): wait for it to finish")
        # The hold is in before this count, and the proxy starts a job only while no hold stands.
        busy = c.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]
        if busy and not force:
            store.restore_hold(c, prev)            # nothing was unloaded: a "failed" hold before this stays
            raise PickError(f"{busy} request(s) running: load when they finish (guardian.py status), or pass --force "
                            "to cut them")
        unload = (team_models(cfg) | {current(cfg, c)["model"]}) - {s["model"]}
        try:
            loaded = load_model.load(s["model"], load_model.load_config(s["context"], s["kv"], s["gpu"]), unload=unload,
                                     key=s["key"])
        except Exception as err:
            why = f"loading {s['model']} failed ({type(err).__name__}: {err})"
            store.fail_hold(c, why)
            raise PickError(why + "; the guardian refuses requests until a load works (models.py ensure, or pick "
                            "another model)") from err
        save(s, c)                                 # after a load that worked, so a failed one keeps the old pick
        store.clear_hold(c)
        return loaded
    finally:
        c.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("pick")
    p.add_argument("preset")
    p.add_argument("--force", action="store_true", help="load even while requests run (cuts them)")
    e = sub.add_parser("ensure")
    e.add_argument("--force", action="store_true")
    o = sub.add_parser("opencode")
    o.add_argument("--cloud", help="a config.json \"cloud\" model, for the owner's terminal")
    a = ap.parse_args(argv)
    cfg = read_config()
    try:
        if a.cmd == "opencode":
            oc = cloud_config(a.cloud, cfg) if a.cloud else opencode_config(current(cfg), cfg)
            print(json.dumps(oc, separators=(",", ":")))
        elif a.cmd == "list":
            c = store.connect()
            try:
                hold = store.get_hold(c)
                out = {"picked": current(cfg, c), "default": cfg["default_model"], "presets": cfg["models"],
                       "hold": None if hold is None else {"state": hold[0], "detail": hold[1]}}
            finally:
                c.close()
            try:
                import lmstudio as lms
            except ImportError:                    # the presets still list
                out["lmstudio"] = ("lmstudio SDK not importable by this Python (python -I hides a pip install --user; "
                                   "install it for all users)")
            else:
                try:
                    out["loaded"] = [m.identifier for m in lms.get_default_client().llm.list_loaded()]
                except Exception as err:           # LM Studio off
                    out["lmstudio"] = f"not reachable ({type(err).__name__})"
            print(json.dumps(out, indent=1))
        elif a.cmd == "pick":
            s = preset(a.preset, cfg)
            print(json.dumps({"picked": s, "loaded": load(s, cfg, a.force)}))
        else:                                      # ensure
            s = current(cfg)
            c = store.connect()
            try:
                hold = store.get_hold(c)
            finally:
                c.close()
            loaded = loaded_contexts()
            if hold is None and s["model"] in loaded and loaded[s["model"]] in (s["context"], None):
                print(json.dumps({"picked": s, "loaded": s["model"], "action": "already loaded"}))
            else:                                  # missing, at another context, or after a load that failed
                print(json.dumps({"picked": s, "loaded": load(s, cfg, a.force), "action": "loaded"}))
    except PickError as why:
        print(json.dumps({"error": str(why)}))
        return 1
    except Exception as err:                       # LM Studio off, the SDK missing, a load that failed
        print(json.dumps({"error": f"{type(err).__name__}: {err}"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
