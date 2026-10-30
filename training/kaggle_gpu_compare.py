"""Private Kaggle T4 same-question comparison, never deploy."""
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path("/kaggle/working/maumgyeol-eval-src")
ADAPTER=Path("/kaggle/input/maumgyeol-lora20-private-eval")
OUTPUT=Path("/kaggle/working/maumgyeol-eval-result")
def command(*args):
    print("RUN",args[0],flush=True)
    subprocess.run([str(x) for x in args],check=True)

import torch
if not torch.cuda.is_available():
    raise RuntimeError("Kaggle GPU is not allocated; refusing CPU fallback")
print("EVAL_GPU="+torch.cuda.get_device_name(0),flush=True)
if not ADAPTER.is_dir():
    raise RuntimeError("Private trained adapter dataset is not mounted")
command("git","clone","--depth","1","--branch","main",
        "https://github.com/minjunmon109/maumgyeol-ai.git",ROOT)
command(sys.executable,"-m","pip","install","-q",
        "transformers>=4.51,<5","peft","accelerate","safetensors")
command(sys.executable,"-m","pip","uninstall","-y","torchao")
command(sys.executable,"-u",ROOT/"training/compare_gpu_lora.py",
        "--artifact",ADAPTER,"--output",OUTPUT,"--device","cuda","--max-new-tokens","96")
if not (OUTPUT/"comparison.json").is_file():
    raise RuntimeError("Missing actual answer comparison report")
print("GPU_MODEL_COMPARISON_COMPLETE; no deployment authorized",flush=True)
