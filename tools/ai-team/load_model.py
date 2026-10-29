"""Load the team's model in LM Studio with memory-lean settings (LM Studio Python SDK, `pip install --user lmstudio`).

  python load_model.py [--model qwen3.6-35b-a3b] [--context 131072] [--kv f16] [--gpu <0..1>]

`lms load` has no switch for memory mapping; with it on, LM Studio kept ~10.5 GB of system RAM for a model that sits
fully in VRAM (measured 2026-10-09), which pushed RAM to 88-90% and made the guardian hold every request. This loads
with tryMmap=False and keepModelInMemory=False. Run it only when no request is running (`guardian.py status`):
unloading cuts an active generation.

Qwen3.6-35B-A3B (Q4_K_M, 21.2 GB) does not fit in 12 GB of VRAM, so LM Studio places the layers (no --gpu) and the
K/V cache stays unquantized. Measured 2026-10-29 at 131072: RAM peak 83.4%, VRAM 10.9 GB; with memory mapping on,
16K alone reached 98.5% RAM. The 14B fallback loads as before with
`--model qwen3-14b --context 32768 --gpu 1 --kv q8_0` (all on the GPU, q8 K/V cache, flash attention).
"""
import argparse
import json

DEFAULT_MODEL = "qwen3.6-35b-a3b"
DEFAULT_CONTEXT = 131072


def load_config(context=DEFAULT_CONTEXT, kv="f16", gpu=None):
    """The LM Studio load config. gpu=None leaves the GPU split to LM Studio; kv other than f16 quantizes the K/V cache
    and turns flash attention on (V-cache quantization needs it)."""
    cfg = {"contextLength": context, "tryMmap": False, "keepModelInMemory": False}
    if gpu is not None:
        cfg["gpu"] = {"ratio": gpu}
    if kv != "f16":
        cfg["flashAttention"] = True
        cfg["llamaKCacheQuantizationType"] = kv
        cfg["llamaVCacheQuantizationType"] = kv
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
