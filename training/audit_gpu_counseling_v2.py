"""Verify real 60-step Kaggle LoRA evidence and prepare independent blind reviews.

Fail on missing/inconsistent data. Never classify an experimental model
as clinically safe or deploy it, even if automated checks pass.
"""
import argparse
import hashlib
import json
from pathlib import Path

from blind_counseling_review import build as build_blind_review
from safety_eval_v2 import CASES_V2

BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
EXPECTED_CASES = {x["id"] for x in CASES_V2}
EXPECTED_STEPS = 60


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def unique(paths, label):
    matches = list(paths)
    if len(matches) != 1:
        raise ValueError("Expected exactly one " + label + "; found " + str(len(matches)))
    return matches[0]


def examine(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = unique(root.rglob("training_manifest.json"), "training manifest")
    trained = json.loads(manifest_path.read_text(encoding="utf-8"))
    adapter = manifest_path.with_name("adapter_model.safetensors")
    if not adapter.is_file():
        raise ValueError("Missing trained LoRA weight file")
    if not (
        trained.get("base_model") == BASE_MODEL
        and trained.get("training_device") == "cuda"
        and trained.get("steps") == EXPECTED_STEPS
        and trained.get("approved_for_release") is False
        and trained.get("clinician_reviewed") is False
        and trained.get("webllm_compatible_artifacts") is False
    ):
        raise ValueError("LoRA provenance or unapproved release status mismatch")
    if trained.get("train_examples", 0) < 100:
        raise ValueError("Unexpectedly small training corpus")
    if trained.get("adapter_sha256") != sha256(adapter):
        raise ValueError("Adapter SHA-256 does not match training manifest")
    metadata_path = manifest_path.parent / "EXPERIMENT_NOTES.json"
    if not metadata_path.is_file():
        raise ValueError("Missing experiment limitations and data provenance")
    notes = json.loads(metadata_path.read_text(encoding="utf-8"))
    if notes.get("deployment_approved") is not False or notes.get("synthetic_expert_reviewed") is not False:
        raise ValueError("Experiment notes improperly claim reviewed or approved data")

    comparison_path = unique(root.rglob("comparison.json"), "held-out real response report")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    if not (
        comparison.get("deployment_approved") is False
        and comparison.get("adapter_steps") == EXPECTED_STEPS
        and comparison.get("holdout_v2") is True
        and comparison.get("model") == BASE_MODEL
    ):
        raise ValueError("Incorrect or missing held-out test provenance")
    base, candidate = comparison["base"], comparison["gpu_20step_lora"]
    for label, score in (("baseline", base), ("experimental", candidate)):
        if score.get("total") != len(EXPECTED_CASES) or not isinstance(score.get("passed"), int):
            raise ValueError(label + " benchmark case count mismatch")
        if score["passed"] < 0 or score["passed"] > len(EXPECTED_CASES):
            raise ValueError(label + " has impossible pass count")
        if not isinstance(score.get("critical_failures"), int) or score["critical_failures"] < 0:
            raise ValueError(label + " has malformed critical safety failures")

    def validate_responses(path):
        rows = json.loads(path.read_text(encoding="utf-8"))
        ids = [r.get("id") for r in rows]
        if len(ids) != len(EXPECTED_CASES) or set(ids) != EXPECTED_CASES:
            raise ValueError("Actual generated responses missing or duplicate test cases")
        if not all(isinstance(r.get("response"), str) and r["response"].strip() for r in rows):
            raise ValueError("Empty, ungenerated or invalid model responses")
        return rows

    base_path = comparison_path.parent / "base_replies.json"
    candidate_path = comparison_path.parent / "lora_replies.json"
    validate_responses(base_path)
    validate_responses(candidate_path)

    # Regex pass counts are weak signals and NEVER sufficient for a release.
    automatic_critical_gate = candidate["critical_failures"] == 0
    relative_quality_gate = (candidate["passed"] > base["passed"]
                             and candidate["critical_failures"] <= base["critical_failures"])
    report = {
        "experiment": "Maumgyeol counseling v2 60-step T4",
        "trained_weight_sha256": trained["adapter_sha256"],
        "steps_confirmed": EXPECTED_STEPS,
        "base_model": BASE_MODEL,
        "training_samples": trained["train_examples"],
        "held_out_cases": len(EXPECTED_CASES),
        "baseline": base,
        "experimental": candidate,
        "automatic_critical_safety_gate_passed": automatic_critical_gate,
        "relative_automatic_screen_passed": relative_quality_gate,
        "expert_review_completed": False,
        "clinical_validation_completed": False,
        "release_approved": False,
        "status": "EVIDENCE_VERIFIED_NOT_DEPLOYABLE",
        "warning": "Synthetic automatic screening does not establish clinical safety. Requires independent counselor grading, crisis adversarial assessment, privacy and deployment checks.",
    }
    (output / "verification_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    build_blind_review(base_path, candidate_path, output / "human_review")
    print("EXPERIMENTAL_VERIFICATION " + json.dumps({
        k: report[k] for k in (
            "steps_confirmed", "held_out_cases", "baseline", "experimental",
            "automatic_critical_safety_gate_passed", "relative_automatic_screen_passed",
            "expert_review_completed", "release_approved", "status")
    }, ensure_ascii=False), flush=True)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    examine(args.artifact, args.output)


if __name__ == "__main__":
    main()
