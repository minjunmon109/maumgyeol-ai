"""Offline unit tests with *fake* weights and fake answers; never clinical validation."""
import hashlib
import json
import tempfile
from pathlib import Path
from audit_gpu_counseling_v3 import examine
from safety_eval_v2 import CASES_V2,evaluate_v2
from safety_eval_v3 import CASES_V3,evaluate_v3

def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)/"artifact"/"experimental"
        root.mkdir(parents=True)
        weights=root/"adapter_model.safetensors"
        weights.write_bytes(b"FAKE-FIXTURE-NOT-A-TRAINED-MODEL")
        checksum=hashlib.sha256(weights.read_bytes()).hexdigest()
        write(root/"training_manifest.json",{
            "steps":90,"training_device":"cuda","base_model":"Qwen/Qwen2.5-1.5B-Instruct",
            "approved_for_release":False,"webllm_compatible_artifacts":False,
            "clinician_reviewed":False,"train_examples":203,"adapter_sha256":checksum
        })
        write(root/"EXPERIMENT_NOTES.json",{
            "training_steps":90,"expert_review_completed":False,
            "deployment_approved":False,"webllm_compatible_artifacts":False
        })
        for label,cases,checker in (("fresh_v3",CASES_V3,evaluate_v3),
                                    ("regression_v2",CASES_V2,evaluate_v2)):
            path=root/label
            rows=[{"id":case["id"],"response":"그런 일을 겪어 많이 힘드셨겠어요. 도움을 요청해 주세요."} for case in cases]
            base=checker(rows);candidate=checker(rows)
            write(path/"base_replies.json",rows)
            write(path/"lora_replies.json",rows)
            write(path/"comparison.json",{
                "adapter_steps":90,"model":"Qwen/Qwen2.5-1.5B-Instruct",
                "deployment_approved":False,
                "holdout_v3":label=="fresh_v3",
                "holdout_v2":label=="regression_v2",
                "base":{"passed":base["pass_count"],"total":base["total"],
                        "critical_failures":base["critical_failures"]},
                "gpu_20step_lora":{"passed":candidate["pass_count"],"total":candidate["total"],
                        "critical_failures":candidate["critical_failures"]}
            })
        out=Path(t)/"verified"
        report=examine(root,out)
        assert not report["release_approved"]
        assert not report["all_critical_heuristic_checks_passed"]
        assert (out/"blind_review/blind_pairs.json").is_file()
        assert (out/"blind_review/review_form.csv").is_file()
        weights.write_bytes(b"TAMPERED")
        try:
            examine(root,Path(t)/"tampered_out")
        except ValueError as e:
            assert "SHA-256" in str(e),str(e)
        else:
            raise AssertionError("Tampered adapter accepted")
        print("V3 artifact audit and fail-closed reviewer preparation tests passed (synthetic only)")
if __name__=="__main__":main()
