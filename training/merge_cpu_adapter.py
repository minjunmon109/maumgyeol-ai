"""Merge a genuinely trained CPU or GPU LoRA adapter into an HF-only checkpoint.

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
    if manifest.get("approved_for_release") is not False or manifest.get("clinician_reviewed") is not False:
        raise SystemExit("Experimental status missing or unexpected; refusing merge")
    if manifest.get("training_device") not in ("cpu","cuda") or int(manifest.get("steps",0)) < 50:
        raise SystemExit("Missing valid training device or inadequate experimental steps")
    if manifest.get("webllm_compatible_artifacts") is not False:
        raise SystemExit("Model must remain explicitly marked NOT web-compatible")
    weights = adapter / "adapter_model.safetensors"
    if not weights.is_file() or sha256(weights) != manifest.get("adapter_sha256"):
        raise SystemExit("Adapter weights are absent or their checksum is invalid")
    import torch
    if manifest.get("training_device") == "cuda" and not torch.cuda.is_available():
        print("GPU-trained adapter will be merged on CPU; this is memory-intensive")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    base = AutoModelForCausalLM.from_pretrained(
        BASE, dtype=torch.float16, low_cpu_mem_usage=True, trust_remote_code=False)
    merged = PeftModel.from_pretrained(base, str(adapter), is_trainable=False).merge_and_unload(safe_merge=True)
    out = Path(args.output);out.mkdir(parents=True, exist_ok=True)
    if out.resolve() == adapter.resolve(): raise SystemExit("Refusing to overwrite original adapter")
    merged.save_pretrained(out, safe_serialization=True, max_shard_size="2GB")
    tokenizer = AutoTokenizer.from_pretrained(BASE,trust_remote_code=False)
    tokenizer.save_pretrained(out)
    (out/"merge_provenance.json").write_text(json.dumps({
        "base_model": BASE, "adapter_sha256": manifest["adapter_sha256"],
        "status": "HF-merged-only-not-MLC-compiled-not-validated",
        "training_steps": manifest["steps"],
        "training_device": manifest["training_device"],
        "cpu_fp16_merge": True,
        "expert_review_completed": False,
        "release_approved": False
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print("Merged HF checkpoint saved:",out)
    print("HF checkpoint ONLY; no MLC conversion, no iPhone test, no approval or deployment.")


if __name__ == "__main__":
    main()
