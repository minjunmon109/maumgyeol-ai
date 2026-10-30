"""Offline synthetic test for GPU audit. Dummy weights are NOT a trained model."""
import hashlib
import json
import tempfile
from pathlib import Path
from audit_gpu_counseling_v2 import examine
from safety_eval_v2 import CASES_V2


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as t:
        root = Path(t) / "fake_artifact"
        model = root / "maumgyeol-experiment"
        model.mkdir(parents=True)
        weight = model / "adapter_model.safetensors"
        weight.write_bytes(b"SYNTHETIC FAKE WEIGHTS -- NO MODEL")
        manifest = {
            "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
            "training_device": "cuda",
            "steps": 60,
            "approved_for_release": False,
            "clinician_reviewed": False,
            "webllm_compatible_artifacts": False,
            "train_examples": 142,
            "adapter_sha256": hashlib.sha256(weight.read_bytes()).hexdigest(),
        }
        put(model / "training_manifest.json", manifest)
        put(model / "EXPERIMENT_NOTES.json", {
            "deployment_approved": False,
            "synthetic_expert_reviewed": False,
        })
        reports = model / "holdout_comparison"
        put(reports / "comparison.json", {
            "deployment_approved": False,
            "adapter_steps": 60,
            "holdout_v2": True,
            "model": "Qwen/Qwen2.5-1.5B-Instruct",
            "base": {"passed": 8, "total": 14, "critical_failures": 2},
            "gpu_20step_lora": {"passed": 12, "total": 14, "critical_failures": 1},
        })
        replies = [{"id": case["id"], "response": "Synthetic placeholder reply -- human testing pending."}
                   for case in CASES_V2]
        put(reports / "base_replies.json", replies)
        put(reports / "lora_replies.json", replies)
        result = examine(root, Path(t) / "out")
        assert result["steps_confirmed"] == 60
        assert result["automatic_critical_safety_gate_passed"] is False
        assert result["release_approved"] is False
        assert result["expert_review_completed"] is False
        assert (Path(t) / "out/human_review/blind_pairs.json").is_file()
        weight.write_bytes(weight.read_bytes() + b"TAMPERED")
        try:
            examine(root, Path(t) / "out2")
        except ValueError as exc:
            assert "SHA-256" in str(exc)
        else:
            raise AssertionError("Tampered model weights were accepted")
        print("GPU audit provenance, blind review and fail-closed safety tests PASS")


if __name__ == "__main__":
    main()
