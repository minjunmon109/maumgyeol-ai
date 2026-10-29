"""Merge a genuinely trained LoRA adapter into a full HF model for MLC conversion.

This is a separate, memory-intensive CPU operation. It does NOT produce a
WebGPU-compatible artifact by itself. Do not upload model/chat data publicly.
"""
import argparse
import hashlib
import json
from pathlib import Path

BASE = "Qwen/Qwen2.5-1.5B-Instruct"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter", required=True)
    p.add_argument("--output", default="training/outputs/merged-qwen25-counselor")
    args = p.parse_args()
    adapter = Path(args.adapter)
    manifest = json.loads((adapter/"training_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "trained_not_safety_validated":
        raise SystemExit("Adapter was not produced by the supervised training pipeline")
    if manifest.get("base_model") != BASE or not manifest.get("base_compatible_with_site"):
        raise SystemExit("This adapter does not match the production Qwen2.5 1.5B model")
    weights = adapter / "adapter_model.safetensors"
    if not weights.is_file() or sha256(weights) != manifest.get("adapter_sha256"):
        raise SystemExit("Adapter weights are absent or their checksum is invalid")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    base = AutoModelForCausalLM.from_pretrained(
        BASE, torch_dtype=torch.float32, low_cpu_mem_usage=True, trust_remote_code=False)
    merged = PeftModel.from_pretrained(base, str(adapter)).merge_and_unload()
    out = Path(args.output);out.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(out, safe_serialization=True, max_shard_size="2GB")
    tokenizer = AutoTokenizer.from_pretrained(BASE,trust_remote_code=False)
    tokenizer.save_pretrained(out)
    (out/"merge_provenance.json").write_text(json.dumps({
        "base_model": BASE, "adapter_sha256": manifest["adapter_sha256"],
        "status": "HF-merged-only-not-MLC-compiled-not-validated",
        "release_approved": False
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print("Merged HF checkpoint saved:",out)
    print("Next: MLC convert_weight / gen_config / compile webgpu, host artifacts; verify on iPhone.")


if __name__ == "__main__":
    main()
