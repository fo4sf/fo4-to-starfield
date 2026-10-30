"""Load the team's model in LM Studio with memory-lean settings (LM Studio Python SDK, `pip install --user lmstudio`).

  python load_model.py [--model qwen3.6-35b-a3b] [--context 65536] [--kv f16] [--gpu <0..1>]

`lms load` has no switch for memory mapping; with it on, LM Studio kept ~10.5 GB of system RAM for a model that sits
fully in VRAM (measured 2026-10-09), which pushed RAM to 88-90% and made the guardian hold every request. This loads
with tryMmap=False and keepModelInMemory=False. Run it only when no request is running (`guardian.py status`):
unloading cuts an active generation.

Qwen3.6-35B-A3B (Q4_K_M, 21.2 GB) does not fit in 12 GB of VRAM, so LM Studio places the layers (no --gpu) and the
K/V cache stays unquantized. Measured 2026-10-29 at 131072: RAM peak 83.4%, VRAM 10.9 GB at load, but 87-91% RAM and
92.5% VRAM once the Lead worked, so the guardian held its requests; at 65536 the PC sat at 78.8% RAM / 10.6 GB VRAM.
With memory mapping on, 16K alone reached 98.5% RAM. `--context 131072` still loads the long window by hand. The SDK's
default idle TTL (1 h) stays: it frees the GPU for game tests when the team is idle, and run-lead.ps1's reload comes back
at this default. The 14B fallback loads as before with `--model qwen3-14b --context 32768 --gpu 1 --kv q8_0` (all on the
GPU, q8 K/V cache, flash attention).
"""
import argparse
import json

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--context", type=int, default=DEFAULT_CONTEXT)
    ap.add_argument("--kv", default="f16", help="K/V cache quantization ('f16' for none, the default; q8_0 halves the cache)")
    ap.add_argument("--gpu", type=float, default=None, help="GPU offload ratio 0..1 (default: LM Studio decides)")
    a = ap.parse_args()
    cfg = load_config(a.context, a.kv, a.gpu)
    import lmstudio as lms                # here, so the tests import this module without the SDK installed
    client = lms.get_default_client()
    for m in client.llm.list_loaded():
        if m.identifier == a.model:
            m.unload()
    model = client.llm.load_new_instance(a.model, a.model, config=cfg)
    print(json.dumps({"loaded": model.identifier, "config": cfg}))


if __name__ == "__main__":
    main()
