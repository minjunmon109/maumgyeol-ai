"""Verify a real CPU-trained LoRA checkpoint. Refuses to claim clinical validation."""
import argparse, hashlib, json, math
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    ap.add_argument("--expected-steps",type=int,default=6)
    args=ap.parse_args()
    d=Path(args.output)
    manifest=json.loads((d/"training_manifest.json").read_text(encoding="utf-8"))
    path=d/"adapter_model.safetensors"
    if not path.is_file() or path.stat().st_size<1024:
        raise SystemExit("ACTUAL_ADAPTER_MISSING")
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    checks={
       "base_matches_website":manifest.get("base_model")=="Qwen/Qwen2.5-1.5B-Instruct",
       "steps":manifest.get("steps")==args.expected_steps,
       "finite_train_loss":isinstance(manifest.get("train_loss"),(float,int)) and math.isfinite(manifest["train_loss"]),
       "finite_val_loss":isinstance(manifest.get("val_loss"),(float,int)) and math.isfinite(manifest["val_loss"]),
       "matching_weight_hash":digest==manifest.get("adapter_sha256"),
       "not_clinically_validated":manifest.get("approved_for_release") is False and manifest.get("clinician_reviewed") is False
    }
    print(json.dumps({"checks":checks,"base_model":manifest.get("base_model"),
      "steps":manifest.get("steps"),"train_loss":manifest.get("train_loss"),
      "validation_loss":manifest.get("val_loss"),
      "adapter_size_bytes":path.stat().st_size,"adapter_sha256":digest,
      "clinical_validation":"NOT_PERFORMED","released_to_site":False},
      ensure_ascii=False,indent=2))
    if not all(checks.values()):
        raise SystemExit("TRAINED_WEIGHTS_VERIFICATION_FAILED")

if __name__=="__main__":main()
