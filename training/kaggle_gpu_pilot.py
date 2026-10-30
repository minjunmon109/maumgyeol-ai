"""Private Kaggle T4 experiment for Maumgyeol. Runs only after explicit Kaggle authorization.
Data used: repo's licensed KMI subset; do not ingest website conversation logs.
Never deploy the experimental adapter to a live counseling site.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/minjunmon109/maumgyeol-ai.git"
BRANCH = "experiment/hybrid-counseling-safety-20261030"
WORK = Path("/kaggle/working")
ROOT = WORK / "maumgyeol-ai-gpu"
OUT = WORK / "maumgyeol-counseling-v2-experimental"

def run(*cmd, cwd=None):
    print("$", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=cwd, check=True)

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

# Fail instead of silently running expensive CPU training.
import torch
if not torch.cuda.is_available():
    raise RuntimeError("NVIDIA GPU is unavailable: check Kaggle account quota / accelerator")

print("GPU:", torch.cuda.get_device_name(0), flush=True)
run("git", "clone", "--depth", "1", "--branch", BRANCH, REPO, ROOT)
run(sys.executable, "-m", "pip", "install", "-q",
    "transformers>=4.51,<5", "peft", "accelerate", "safetensors")
# Kaggle 2026 preinstalls torchao 0.10; recent Transformers rejects it (<0.16).
# torchao is optional for regular FP16 LoRA, so remove it instead of changing torch.
run(sys.executable, "-m", "pip", "uninstall", "-y", "torchao")
import importlib.util
if importlib.util.find_spec("torchao") is not None:
    raise RuntimeError("Unsupported torchao remains installed; cannot train safely")
print("Optional torchao compatibility issue resolved", flush=True)
print("PyTorch version:", torch.__version__, flush=True)
print("CUDA GPU:", torch.cuda.get_device_name(0), flush=True)
run(sys.executable, ROOT/"training/verify_training_license.py")
# Build a separate, transparently labeled synthetic counseling supplement.
# Use KMI training examples only; independent safety_eval_v2 holdout is NEVER trained.
SYNTH = WORK / "synthetic_counseling_train.jsonl"
MIX = WORK / "kmi_plus_synthetic_training.jsonl"
run(sys.executable, ROOT/"training/build_counseling_safety_sft.py",
    "--output", SYNTH)
import random
kmi = []
for input_path in sorted((ROOT/"training/open_data").glob("kmi_train_*.jsonl")):
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            kmi.append(json.loads(line))
synthetic = [json.loads(x) for x in SYNTH.read_text(encoding="utf-8").splitlines() if x.strip()]
if len(kmi) < 64 or len(synthetic) < 30:
    raise RuntimeError("Insufficient KMI or synthetic training inputs")
# Controlled mix: 64 licensed KMI train examples + 2x 39 unreviewed synthetic examples.
mixed = kmi[:64] + synthetic * 2
random.Random(42).shuffle(mixed)
MIX.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in mixed),encoding="utf-8")
print(json.dumps({"event":"training_mix","kmi":64,"synthetic_unique":len(synthetic),
                  "synthetic_repeated":2,"total":len(mixed),
                  "synthetic_expert_reviewed":False}),flush=True)
run(sys.executable, ROOT/"training/train_cpu_lora.py",
    "--train", MIX, "--val", str(ROOT/"training/open_data/kmi_val.jsonl"),
    "--dry-run")
run(sys.executable, "-u", ROOT/"training/train_cpu_lora.py",
    "--device", "cuda", "--max-steps", "60",
    "--gradient-accumulation-steps", "1",
    "--max-length", "320", "--max-eval-examples", "8", "--log-steps", "5",
    "--checkpoint-every", "15",
    "--train", MIX, "--val", str(ROOT/"training/open_data/kmi_val.jsonl"),
    "--output", OUT)

manifest = json.loads((OUT/"training_manifest.json").read_text(encoding="utf-8"))
assert manifest["training_device"] == "cuda" and manifest["steps"] == 60
assert manifest["approved_for_release"] is False
assert manifest["clinician_reviewed"] is False
assert manifest["webllm_compatible_artifacts"] is False
assert (OUT/"adapter_model.safetensors").is_file()

# Evaluate actual new adapter replies against a distinct hold-out benchmark.
# Do not train on these prompts. Scores are heuristic, NEVER clinical approval.
run(sys.executable, "-u", ROOT/"training/compare_gpu_lora.py",
    "--artifact", OUT, "--output", OUT/"holdout_comparison",
    "--device", "cuda", "--steps", "60",
    "--holdout-v2", "--max-new-tokens", "160")
comparison = json.loads((OUT/"holdout_comparison/comparison.json").read_text(encoding="utf-8"))
assert comparison["holdout_v2"] is True and comparison["adapter_steps"] == 60
print("HOLDOUT_14_BASE=",json.dumps(comparison["base"],ensure_ascii=False),flush=True)
print("HOLDOUT_14_V2=",json.dumps(comparison["gpu_20step_lora"],ensure_ascii=False),flush=True)
if comparison["gpu_20step_lora"]["critical_failures"]:
    print("CRITICAL SAFETY SCREEN FAILED — DEPLOYMENT REMAINS BLOCKED",flush=True)
else:
    print("AUTOMATIC SAFETY SCREEN ONLY — EXPERT APPROVAL STILL REQUIRED",flush=True)

(OUT/"ATTRIBUTION.txt").write_text(
    "KMI synthetic motivational interviewing dataset — Kim et al., NAACL 2025.\n"
    "https://aclanthology.org/2025.naacl-long.541/\n"
    "CC BY 4.0; this is NOT clinician-reviewed and NOT approved for deployment.\n",
    encoding="utf-8")
(OUT/"EXPERIMENT_NOTES.json").write_text(json.dumps({
  "version":"counseling_safety_v2","synthetic_examples":len(synthetic),
  "synthetic_expert_reviewed":False,
  "independent_holdout":"training/safety_eval_v2.py",
  "clinical_validation":"NOT_DONE",
  "deployment_approved":False
},ensure_ascii=False,indent=2),encoding="utf-8")
print("GPU COUNSELING V2 SUCCESS: 60/60 training steps; synthetic examples are NOT clinician reviewed; NO DEPLOY", flush=True)
