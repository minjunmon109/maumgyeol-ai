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
OUT = WORK / "maumgyeol-kmi-gpu-experimental"

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
run(sys.executable, ROOT/"training/verify_training_license.py")
run(sys.executable, ROOT/"training/train_cpu_lora.py",
    "--train", str(ROOT/"training/open_data/kmi_train_*.jsonl"),
    "--val", str(ROOT/"training/open_data/kmi_val.jsonl"),
    "--dry-run")
run(sys.executable, "-u", ROOT/"training/train_cpu_lora.py",
    "--device", "cuda", "--max-steps", "20",
    "--gradient-accumulation-steps", "1",
    "--max-length", "128", "--max-training-examples", "64",
    "--max-eval-examples", "8", "--log-steps", "1",
    "--checkpoint-every", "5",
    "--train", str(ROOT/"training/open_data/kmi_train_*.jsonl"),
    "--val", str(ROOT/"training/open_data/kmi_val.jsonl"),
    "--output", OUT)

manifest = json.loads((OUT/"training_manifest.json").read_text(encoding="utf-8"))
assert manifest["training_device"] == "cuda" and manifest["steps"] == 20
assert manifest["approved_for_release"] is False
assert manifest["clinician_reviewed"] is False
assert manifest["webllm_compatible_artifacts"] is False
assert (OUT/"adapter_model.safetensors").is_file()

(OUT/"ATTRIBUTION.txt").write_text(
    "KMI synthetic motivational interviewing dataset — Kim et al., NAACL 2025.\n"
    "https://aclanthology.org/2025.naacl-long.541/\n"
    "CC BY 4.0; this is NOT clinician-reviewed and NOT approved for deployment.\n",
    encoding="utf-8")
print("GPU PILOT SUCCESS: 20/20 training steps; experimental artifact saved, NO DEPLOY", flush=True)
