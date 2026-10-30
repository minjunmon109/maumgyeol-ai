"""PRIVATE experimental Kaggle CUDA training + two independent model-answer benchmarks.
Original synthetic dialogues, licensed KMI subset, no site user conversations.
This script MUST NEVER deploy, mark clinically validated, or auto-approve weights.
"""
import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

WORK=Path("/kaggle/working")
ROOT=WORK/"maumgyeol-counseling-v3-src"
OUT=WORK/"maumgyeol-counseling-v3-NOT-APPROVED"
SOURCE_COMMIT="__SOURCE_COMMIT__"
REPO="https://github.com/minjunmon109/maumgyeol-ai.git"

def run(*args,cwd=None):
    cmd=[str(v) for v in args]
    print("RUN_TOOL="+cmd[0]+" args_count="+str(len(cmd)),flush=True)
    subprocess.run(cmd,cwd=cwd,check=True)

os.environ["TOKENIZERS_PARALLELISM"]="false"
os.environ["HF_HUB_DISABLE_TELEMETRY"]="1"
os.environ["OMP_NUM_THREADS"]="2"
os.environ["MKL_NUM_THREADS"]="2"
import torch
if not torch.cuda.is_available():
    raise RuntimeError("CUDA is unavailable; never fall back to CPU")
print("GPU_DEVICE="+torch.cuda.get_device_name(0),flush=True)
run("git","clone","--depth","1","--branch","main",REPO,ROOT)
if SOURCE_COMMIT!="__SOURCE_COMMIT__":
    run("git","fetch","--depth","1","origin",SOURCE_COMMIT,cwd=ROOT)
    run("git","checkout","--detach",SOURCE_COMMIT,cwd=ROOT)
actual_sha=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
print("TRAINING_SOURCE_COMMIT="+actual_sha,flush=True)
run(sys.executable,"-m","pip","install","-q",
    "transformers>=4.51,<5","peft","accelerate","safetensors")
run(sys.executable,"-m","pip","uninstall","-y","torchao")
# Spawn new process for training after optional torchao uninstall.
run(sys.executable,ROOT/"training/verify_training_license.py")
V2=WORK/"v2_synthetic.jsonl"
V3=WORK/"v3_synthetic.jsonl"
MIX=WORK/"approved_kmi_plus_unreviewed_synthetic_v3.jsonl"
run(sys.executable,ROOT/"training/build_counseling_safety_sft.py","--output",V2)
run(sys.executable,ROOT/"training/build_counseling_v3_data.py","--output",V3)
v2=[json.loads(s) for s in V2.read_text(encoding="utf-8").splitlines() if s.strip()]
v3=[json.loads(s) for s in V3.read_text(encoding="utf-8").splitlines() if s.strip()]
kmi=[]
for p in sorted((ROOT/"training/open_data").glob("kmi_train_*.jsonl")):
    kmi.extend(json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip())
if len(kmi)<64 or len(v2)!=39 or len(v3)<45:
    raise RuntimeError("Unexpected training corpus; refusing incomplete experiment")
from sys import path as sys_path
sys_path.insert(0,str(ROOT/"training"))
from safety_eval_v2 import CASES_V2
from safety_eval_v3 import CASES_V3
heldouts=[x["messages"][-1]["content"] for x in CASES_V2+CASES_V3]
rows=kmi[:64]+v2+v3*2
for row in rows:
    if any(prompt in row["prompt"] for prompt in heldouts):
        raise RuntimeError("Held-out evaluation question leaked into training data")
random.Random(24017).shuffle(rows)
MIX.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
print("TRAINING_DATA="+json.dumps({"kmi":64,"v2_unreviewed":len(v2),
  "v3_unreviewed_unique":len(v3),"v3_oversampling":2,"total_rows":len(rows),
  "clinician_review_completed":False},ensure_ascii=False),flush=True)
run(sys.executable,ROOT/"training/train_gpu_lora.py",
    "--train",MIX,"--val",ROOT/"training/open_data/kmi_val.jsonl",
    "--dry-run")
run(sys.executable,"-u",ROOT/"training/train_gpu_lora.py",
    "--device","cuda","--max-steps","90","--gradient-accumulation-steps","1",
    "--max-length","512","--max-eval-examples","8","--log-steps","5",
    "--checkpoint-every","30","--learning-rate","6e-5",
    "--train",MIX,"--val",ROOT/"training/open_data/kmi_val.jsonl",
    "--output",OUT)
manifest=json.loads((OUT/"training_manifest.json").read_text(encoding="utf-8"))
if not (manifest.get("steps")==90 and manifest.get("training_device")=="cuda"
        and manifest.get("approved_for_release") is False
        and manifest.get("webllm_compatible_artifacts") is False
        and (OUT/"adapter_model.safetensors").is_file()):
    raise RuntimeError("Missing valid 90-step GPU adapter or provenance")
comparisons={}
for label,flag in (("fresh_v3","--holdout-v3"),("regression_v2","--holdout-v2")):
    target=OUT/label
    run(sys.executable,"-u",ROOT/"training/compare_gpu_lora.py",
        "--artifact",OUT,"--output",target,"--device","cuda",
        "--steps","90",flag,"--max-new-tokens","200")
    comparison=json.loads((target/"comparison.json").read_text(encoding="utf-8"))
    if comparison.get("adapter_steps")!=90 or comparison.get("deployment_approved") is not False:
        raise RuntimeError("Invalid benchmark metadata")
    comparisons[label]={"baseline":comparison["base"],"candidate":comparison["gpu_20step_lora"]}
    print("BENCHMARK_"+label.upper()+"="+json.dumps(comparisons[label],ensure_ascii=False),flush=True)
critical_zero=all(data["candidate"]["critical_failures"]==0 for data in comparisons.values())
outcome={
  "version":"v3_90step_experimental","source_commit":actual_sha,
  "training_steps":90,"training_cases":len(rows),
  "new_synthetic_cases":len(v3),"new_synthetic_clinician_reviewed":False,
  "independent_fresh_holdout":"training/safety_eval_v3.py",
  "previous_holdout_regression":"training/safety_eval_v2.py",
  "scores":comparisons,
  "critical_keyword_gate_passed":critical_zero,
  "expert_review_completed":False,"clinical_validation_completed":False,
  "webllm_compatible_artifacts":False,"deployment_approved":False,
  "warning":"Even zero keyword flags would NOT certify clinical safety; independent professional and privacy review required."
}
(OUT/"EXPERIMENT_NOTES.json").write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding="utf-8")
print("EXPERIMENT_COMPLETE_90_STEPS_V3="+json.dumps({
  "trained":True,"fresh_evaluation_complete":True,
  "critical_gate":critical_zero,"deployment_approved":False
},ensure_ascii=False),flush=True)
