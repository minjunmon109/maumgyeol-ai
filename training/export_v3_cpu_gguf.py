"""Export the EXACT private Kaggle-trained Maumgyeol V3 LoRA to a CPU GGUF.

Experimental artifact only. CPU/WASM execution is not clinical validation.
Hugging Face base weights never become a different or substitute model.
Requires real merge weights, original manifest SHA and actual llama.cpp toolchain.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXPECTED_BASE="Qwen/Qwen2.5-1.5B-Instruct"
EXPECTED_STEPS=90

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fp:
        for block in iter(lambda:fp.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def check_adapter(path):
    p=Path(path)
    cfg=json.loads((p/"training_manifest.json").read_text(encoding="utf-8"))
    if not (cfg.get("base_model")==EXPECTED_BASE and cfg.get("steps")==EXPECTED_STEPS
            and cfg.get("training_device")=="cuda" and cfg.get("train_examples",0)>=200
            and cfg.get("approved_for_release") is False
            and cfg.get("clinician_reviewed") is False
            and cfg.get("webllm_compatible_artifacts") is False):
        raise ValueError("Not the exact 90-step experimental Maumgyeol V3 trained adapter")
    weight=p/"adapter_model.safetensors"
    if not weight.is_file() or sha256(weight)!=cfg.get("adapter_sha256"):
        raise ValueError("Trained LoRA weight hash did not match provenance")
    return cfg

def run(*args):
    print("CPU_GGUF_STEP="+str(args[0])+" args="+str(len(args)),flush=True)
    subprocess.run([str(x) for x in args],check=True)

def build(adapter, output, llama_dir):
    adapter=Path(adapter).resolve();output=Path(output).resolve()
    llama_dir=Path(llama_dir).resolve()
    info=check_adapter(adapter)
    output.mkdir(parents=True,exist_ok=True)
    merged=output/"hf-merged"
    fp16=output/"maumgyeol-v3-f16-intermediate.gguf"
    quant=output/"maumgyeol-v3-q4_k_m.gguf"
    run(sys.executable,Path(__file__).with_name("merge_cpu_adapter.py"),
        "--adapter",adapter,"--output",merged)
    merge_manifest=json.loads((merged/"merge_provenance.json").read_text(encoding="utf-8"))
    if merge_manifest.get("adapter_sha256")!=info["adapter_sha256"] or merge_manifest.get("release_approved") is not False:
        raise ValueError("Merged HF checkpoint provenance mismatch")
    converter=llama_dir/"convert_hf_to_gguf.py"
    if not converter.is_file():
        raise FileNotFoundError("A real llama.cpp converter is required")
    run(sys.executable,converter,merged,"--outfile",fp16,"--outtype","f16")
    quantizer=llama_dir/"build/bin/llama-quantize"
    if not quantizer.is_file():
        raise FileNotFoundError("Compiled llama-quantize is required")
    run(quantizer,fp16,quant,"Q4_K_M")
    if not quant.is_file() or quant.stat().st_size<300_000_000:
        raise RuntimeError("CPU GGUF export too small/incomplete")
    assert fp16.stat().st_size>quant.stat().st_size,"Quantization did not reduce size"
    report={
      "model":"Maumgyeol V3 90-step experimental CPU GGUF",
      "format":"GGUF","quantization":"Q4_K_M",
      "base_model":EXPECTED_BASE,
      "adapter_train_steps":EXPECTED_STEPS,
      "adapter_sha256":info["adapter_sha256"],
      "gguf_sha256":sha256(quant),
      "gguf_size_bytes":quant.stat().st_size,
      "cpu_execution_possible":True,
      "gpu_required_for_inference":False,
      "browser_runtime":"llama.cpp WebAssembly via wllama",
      "expert_review_completed":False,
      "clinical_safety_validated":False,
      "release_approved":False,
      "default_counseling_deployment_allowed":False,
      "warning":"This V3 model failed critical counseling evaluations. CPU export does not make its answers safe."
    }
    (output/"cpu-gguf-provenance.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    fp16.unlink() # Save disk space; keep merged model only locally within this job
    print("V3_CPU_GGUF_SUCCESS="+json.dumps({
      "quantized_bytes":report["gguf_size_bytes"],
      "gguf_sha256":report["gguf_sha256"],
      "released":False
    }),flush=True)
    return quant

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--llama-dir",type=Path,required=True)
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args()
    if a.verify_only:
        conf=check_adapter(a.adapter)
        print("V3_EXACT_ADAPTER_VERIFIED="+str(conf["adapter_sha256"]),flush=True)
    else:
        build(a.adapter,a.output,a.llama_dir)
if __name__=="__main__":main()
