"""Load the team's model in LM Studio with memory-lean settings (LM Studio Python SDK, `pip install --user lmstudio`).

  python load_model.py [--model qwen3.6-35b-a3b] [--key <as LM Studio lists it>] [--context 65536] [--kv f16]
                       [--gpu <0..1>]

--model is the id it loads under; --key defaults to the config.json preset's key for that id (the 3-bit trial:
--model qwen3.6-35b-a3b-q3 loads unsloth/qwen3.6-35b-a3b).

`lms load` has no switch for memory mapping; with it on, LM Studio kept ~10.5 GB of system RAM for a model that sits
fully in VRAM (measured 2026-10-09), which pushed RAM to 88-90% and made the guardian hold every request. This loads
with tryMmap=False and keepModelInMemory=False. Run it only when no request is running (`guardian.py status`):
unloading cuts an active generation.

Qwen3.6-35B-A3B (Q4_K_M, 21.2 GB) does not fit in 12 GB of VRAM, so LM Studio places the layers (no --gpu) and the
K/V cache stays unquantized. Measured 2026-10-29 at 131072: RAM peak 83.4%, VRAM 10.9 GB at load, but 87-91% RAM and
92.5% VRAM once the Lead worked, so the guardian held its requests; at 65536 the PC sat at 78.8% RAM / 10.6 GB VRAM
idle after the load and up to 90.3% RAM / 10.85 GB VRAM while the Lead worked.
With memory mapping on, 16K alone reached 98.5% RAM. `--context 131072` still loads the long window by hand. The SDK's
default idle TTL (1 h) stays: it frees the GPU for game tests when the team is idle, and run-lead.ps1's reload comes back
at this default. The 14B fallback loads as before with `--model qwen3-14b --context 32768 --gpu 1 --kv q8_0` (all on the
GPU, q8 K/V cache, flash attention).
"""
import argparse
import json
import os

DEFAULT_MODEL = "qwen3.6-35b-a3b"
DEFAULT_CONTEXT = 65536


def load_config(context=DEFAULT_CONTEXT, kv="f16", gpu=None):
    """The LM Studio load config. gpu=None leaves the GPU split to LM Studio. Flash attention and both K/V cache types
    are always sent, so settings saved in LM Studio cannot change them. kv f16 keeps the K/V cache unquantized."""
    cfg = {"contextLength": context, "tryMmap": False, "keepModelInMemory": False, "flashAttention": True,
           "llamaKCacheQuantizationType": kv, "llamaVCacheQuantizationType": kv}
    if gpu is not None:
        cfg["gpu"] = {"ratio": gpu}
    return cfg


def named(identifier, ids):
    """Whether a loaded instance is one of ids: LM Studio names a second instance of a model id:2, id:3, ..."""
    base, _, n = identifier.rpartition(":")
    return identifier in ids or (n.isdigit() and base in ids)


def load(model, cfg, unload=(), key=None):
    """Load the model LM Studio lists as key (model if none) with cfg under the id model, after unloading that id and
    any loaded model whose id is in unload (with their id:2, ... instances). Two downloads of one model get publisher
    keys in LM Studio (lmstudio-community/..., unsloth/...), while the id the team sends requests to stays short."""
    import lmstudio as lms                # here, so the tests import this module without the SDK installed
    client = lms.get_default_client()
    for m in client.llm.list_loaded():
        if named(m.identifier, {model, *unload}):
            m.unload()
    return client.llm.load_new_instance(key or model, model, config=cfg).identifier


def preset_key(model, config=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")):
    """The key LM Studio lists a preset's model under (config.json "models" ... "key"), or None."""
    try:
        with open(config, encoding="utf-8") as f:
            presets = json.load(f)["models"].values()
    except (OSError, ValueError, KeyError, AttributeError):
        return None
    return next((p.get("key") for p in presets if isinstance(p, dict) and p.get("model") == model), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="the id to load it under")
    ap.add_argument("--key", help="the model as LM Studio lists it (default: the preset's key for --model, if any)")
    ap.add_argument("--context", type=int, default=DEFAULT_CONTEXT)
    ap.add_argument("--kv", default="f16", help="K/V cache quantization ('f16' for none, the default; q8_0 halves the cache)")
    ap.add_argument("--gpu", type=float, default=None, help="GPU offload ratio 0..1 (default: LM Studio decides)")
    a = ap.parse_args()
    cfg = load_config(a.context, a.kv, a.gpu)
    print(json.dumps({"loaded": load(a.model, cfg, key=a.key or preset_key(a.model)), "config": cfg}))


if __name__ == "__main__":
    main()
