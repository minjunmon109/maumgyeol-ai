"""Fail-closed, non-clinical comparison of real baseline and fine-tuned model replies.

A successful automated report is NOT evidence of clinical competence, professional
validation, or authorization for deployment. Only synthetic fixed prompts are used.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from safety_eval import CASES, evaluate, load_jsonl

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_adapter(directory, min_steps=50):
    folder = Path(directory)
    manifest = json.loads((folder / "training_manifest.json").read_text(encoding="utf-8"))
    weights = folder / "adapter_model.safetensors"
    if not weights.is_file() or weights.stat().st_size < 1024:
        raise ValueError("Trained LoRA adapter weights missing or implausibly small")
    actual_hash = sha256_file(weights)
    if actual_hash != manifest.get("adapter_sha256"):
        raise ValueError("Trained LoRA SHA-256 does not match training provenance")
    if manifest.get("status") != "trained_not_safety_validated":
        raise ValueError("Training status must be unvalidated")
    if manifest.get("base_model") != BASE_MODEL or manifest.get("base_compatible_with_site") is not True:
        raise ValueError("Fine-tuning base model incompatible with website")
    steps = manifest.get("steps")
    if type(steps) is not int or steps < min_steps or manifest.get("smoke_test_only") is True:
        raise ValueError("Insufficient training steps or smoke-only checkpoint")
    for key in ("train_loss", "val_loss"):
        value = manifest.get(key)
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("Missing finite " + key)
    if manifest.get("approved_for_release") is not False or manifest.get("clinician_reviewed") is not False:
        raise ValueError("Training output must never claim clinical approval")
    return {
        "base_model": BASE_MODEL,
        "steps": steps,
        "train_examples": manifest.get("train_examples"),
        "validation_examples": manifest.get("validation_examples"),
        "train_loss": manifest["train_loss"],
        "val_loss": manifest["val_loss"],
        "adapter_sha256": actual_hash,
        "adapter_size_bytes": weights.stat().st_size,
        "dataset_limited": manifest.get("dataset_limited"),
    }


def indexed(rows):
    expected = {case["id"] for case in CASES}
    by_id = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Every generated response requires a string id")
        identifier = row["id"]
        if identifier in by_id:
            raise ValueError("Duplicate benchmark response id: " + identifier)
        if not isinstance(row.get("response"), str):
            raise ValueError("Missing generated response text: " + identifier)
        by_id[identifier] = row["response"]
    if set(by_id) != expected:
        raise ValueError("Benchmark IDs do not exactly match current cases: missing=%s extra=%s"
                         % (sorted(expected - set(by_id)), sorted(set(by_id) - expected)))
    return by_id


def compare(base_rows, candidate_rows, provenance):
    """Only compare measured generated outputs; do not invent counseling scores."""
    base = indexed(base_rows)
    candidate = indexed(candidate_rows)
    base_report = evaluate([{"id": key, "response": val} for key, val in base.items()])
    candidate_report = evaluate([{"id": key, "response": val} for key, val in candidate.items()])
    base_cases = {entry["id"]: entry for entry in base_report["cases"]}
    candidate_cases = {entry["id"]: entry for entry in candidate_report["cases"]}
    changes = []
    for case in CASES:
        id_ = case["id"]
        first, second = base_cases[id_], candidate_cases[id_]
        changes.append({
            "id": id_, "category": case["category"], "severity": case["severity"],
            "base_pass": first["pass"], "candidate_pass": second["pass"],
            "base_flags": first["flags"], "candidate_flags": second["flags"],
            "regressed": first["pass"] and not second["pass"],
            "improved": not first["pass"] and second["pass"],
        })
    regressions = [x["id"] for x in changes if x["regressed"]]
    critical_regressions = [x["id"] for x in changes
                            if x["regressed"] and x["severity"] == "critical"]
    screen_pass = (candidate_report["automatic_gate_passed"]
                   and not regressions and not critical_regressions)
    summary = {
        "status": "automated_comparison_only_not_clinically_validated",
        "benchmark_cases": len(CASES),
        "baseline_passed": base_report["passed_count"],
        "candidate_passed": candidate_report["passed_count"],
        "baseline_critical_failures": base_report["critical_failures"],
        "candidate_critical_failures": candidate_report["critical_failures"],
        "regressions": regressions,
        "critical_regressions": critical_regressions,
        "automated_screen_passed": bool(screen_pass),
        "clinical_expert_review": "NOT_DONE",
        "real_device_iphone_test": "NOT_DONE",
        "website_release_approved": False,
        "evidence_level": "small synthetic checklist; not a clinical validation or human preference study",
        "limitations": [
            "Regex screening is insufficient for reliable empathy, quality, or safety judgment",
            "Fixed synthetic benchmark is not representative of real clinical conversations",
            "Improvement in a pass count does not establish improved counseling ability",
            "Raw CPU generations are not identical to iPhone WebLLM inference or browser guardrails",
        ],
        "model_provenance": provenance,
        "cases": changes,
    }
    return summary, base_report, candidate_report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True, help="Actual, generated base-model JSONL")
    p.add_argument("--candidate", required=True, help="Actual, generated LoRA-model JSONL")
    p.add_argument("--adapter", required=True, help="Verified trained checkpoint directory")
    p.add_argument("--output", required=True, help="Directory for non-clinical evaluation evidence")
    p.add_argument("--min-steps", type=int, default=50)
    args = p.parse_args(argv)
    if args.min_steps < 1:
        raise SystemExit("--min-steps must be positive")
    provenance = verified_adapter(args.adapter, args.min_steps)
    summary, baseline, candidate = compare(
        load_jsonl(args.baseline), load_jsonl(args.candidate), provenance)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("comparison.json", summary),
                       ("baseline_safety.json", baseline),
                       ("candidate_safety.json", candidate)):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"},
                     ensure_ascii=False, indent=2), flush=True)
    if not summary["automated_screen_passed"]:
        raise SystemExit("AUTOMATED_SCREEN_FAILED: results saved, no release authorized")
    print("Automated screen passed; clinical review and iPhone checks STILL required.")


if __name__ == "__main__":
    main()
