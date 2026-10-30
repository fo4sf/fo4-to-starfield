"""Pick the model the local team runs on, and load it in LM Studio (LM Studio Python SDK, `pip install --user lmstudio`).

  python models.py list                     the presets (config.json "models"), the pick, and what LM Studio has
                                            loaded and downloaded; JSON
  python models.py pick <preset> [--no-load]
  python models.py pick --model <id> --context <tokens> [--output <tokens>] [--kv f16|q8_0] [--gpu <0..1>] [--no-load]
                                            any other model LM Studio has downloaded (`list` names them)
  python models.py ensure                   load the pick unless LM Studio already has it loaded
  python models.py opencode                 OpenCode's inline config for the pick (OPENCODE_CONFIG_CONTENT): the four
                                            agents' context and output limits

The pick is a file in the team's state folder (model.json, beside guardian.db); with no pick the default preset is
used. The guardian proxy sends every agent's requests to the picked model, and terminal.ps1 and run-lead.ps1 hand the
pick's limits to OpenCode, so OpenCode compacts at the window that is loaded and asks for no more output than fits.
Loading unloads the team's other models first (only ids that a preset or the pick names: a model you loaded by hand for
something else stays) and refuses while a request is running, since unloading cuts an active generation.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
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


def setup(model, context, output=None, kv="f16", gpu=None, preset=None):
    """A checked setup. Output defaults to a quarter of the window, at most 16K; at least half the window stays for
    the conversation, since OpenCode compacts at context minus output."""
    if not isinstance(model, str) or not MODEL_ID.fullmatch(model):
        raise PickError(f"not an LM Studio model id: {model!r}")
    if not isinstance(context, int) or not 4096 <= context <= 262144:
        raise PickError("context must be 4096..262144 tokens")
    output = min(16384, context // 4) if output is None else output
    if not isinstance(output, int) or not 1024 <= output <= context // 2:
        raise PickError("output must be 1024 tokens up to half the context")
    if kv not in KV_TYPES:
        raise PickError(f"kv must be one of {', '.join(KV_TYPES)}")
    if gpu is not None and not (isinstance(gpu, (int, float)) and 0 <= gpu <= 1):
        raise PickError("gpu must be 0..1")
    return {"preset": preset, "model": model, "context": context, "output": output, "kv": kv, "gpu": gpu}


def preset(name, cfg=None):
    cfg = cfg or read_config()
    p = cfg["models"].get(name)
    if p is None:
        raise PickError(f"no preset {name!r}; presets: {', '.join(cfg['models'])}")
    return setup(p["model"], p["context"], p["output"], p["kv"], p["gpu"], preset=name)


def pick_file():
    return os.path.join(store.STATE, store.PICK)


def current(cfg=None):
    """The picked setup, or the default preset when there is no pick or the file does not hold a valid one."""
    cfg = cfg or read_config()
    try:
        with open(pick_file(), encoding="utf-8") as f:
            p = json.load(f)
        return setup(p["model"], p["context"], p["output"], p["kv"], p["gpu"], p.get("preset"))
    except (OSError, ValueError, KeyError, TypeError, PickError):
        return preset(cfg["default_model"], cfg)


def save(s):
    os.makedirs(store.STATE, exist_ok=True)
    tmp = pick_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f)
    os.replace(tmp, pick_file())                   # the proxy reads the file on every request: never a half-written one


def opencode_config(s, cfg=None):
    """The inline OpenCode config for a setup: every team agent's model gets the setup's window and output. OpenCode
    merges it over opencode.json, so the names, tool_call and provider settings there stay."""
    cfg = cfg or read_config()
    limit = {"context": s["context"], "output": s["output"]}
    return {"provider": {"guardian": {"models": {a: {"limit": dict(limit)} for a in cfg["agents"]}}}}


def team_models(cfg):
    return {p["model"] for p in cfg["models"].values()} | set(cfg["agents"].values())


def loaded_ids():
    import lmstudio as lms                         # here, so the tests import this module without the SDK installed
    return [m.identifier for m in lms.get_default_client().llm.list_loaded()]


def load(s, cfg, force=False):
    """Load a setup and make it the pick. The guardian is paused meanwhile, so no request starts against a model that
    is being swapped out (requests wait in its queue and run once the new model is in)."""
    c = store.connect()
    busy = c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('running', 'queued')").fetchone()[0]
    if busy and not force:
        raise PickError(f"{busy} request(s) running or queued: load when they finish (guardian.py status), or pass "
                        "--force to cut them")
    mode = store.get_mode(c)
    if mode == "running":
        store.set_mode(c, "paused")
    try:
        cfg_lm = load_model.load_config(s["context"], s["kv"], s["gpu"])
        loaded = load_model.load(s["model"], cfg_lm, unload=team_models(cfg) - {s["model"]})
        save(s)                                    # after a load that worked, so a failed one keeps the old pick
        return loaded
    finally:
        if mode == "running":
            store.set_mode(c, "running")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("pick")
    p.add_argument("preset", nargs="?")
    p.add_argument("--model")
    p.add_argument("--context", type=int)
    p.add_argument("--output", type=int)
    p.add_argument("--kv", default="f16")
    p.add_argument("--gpu", type=float)
    p.add_argument("--no-load", action="store_true")
    p.add_argument("--force", action="store_true", help="load even while requests run (cuts them)")
    e = sub.add_parser("ensure")
    e.add_argument("--force", action="store_true")
    sub.add_parser("opencode")
    a = ap.parse_args(argv)
    cfg = read_config()
    try:
        if a.cmd == "opencode":
            print(json.dumps(opencode_config(current(cfg), cfg), separators=(",", ":")))
        elif a.cmd == "list":
            out = {"picked": current(cfg), "default": cfg["default_model"], "presets": cfg["models"]}
            try:
                import lmstudio as lms
                client = lms.get_default_client()
                out["loaded"] = [m.identifier for m in client.llm.list_loaded()]
                out["downloaded"] = sorted(m.model_key for m in client.llm.list_downloaded())
            except Exception as err:               # LM Studio off or the SDK missing: the presets still list
                out["lmstudio"] = f"not reachable ({type(err).__name__})"
            print(json.dumps(out, indent=1))
        elif a.cmd == "pick":
            if bool(a.preset) == bool(a.model):
                raise PickError("pick takes a preset name, or --model with --context")
            if a.preset:
                s = preset(a.preset, cfg)
            else:
                if a.context is None:
                    raise PickError("--model needs --context")
                s = setup(a.model, a.context, a.output, a.kv, a.gpu)
            if a.no_load:
                save(s)
                print(json.dumps({"picked": s, "loaded": None}))
            else:
                print(json.dumps({"picked": s, "loaded": load(s, cfg, a.force)}))
        else:                                      # ensure
            s = current(cfg)
            if s["model"] in loaded_ids():
                print(json.dumps({"picked": s, "loaded": s["model"], "action": "already loaded"}))
            else:
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
