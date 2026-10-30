"""Standard library, offline sanity tests for synthetic SFT and independent safety gate."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_counseling_safety_sft import build
from safety_eval_v2 import CASES_V2,evaluate_v2

def main():
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/"synthetic.jsonl"
        build(path)
        examples=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
        assert len(examples)>=35
        assert len({x["dialogue_id"] for x in examples})==len(examples)
        assert all(x["synthetic"] is True for x in examples)
        assert all(x["prompt"].startswith("<|im_start|>system") for x in examples)
        assert all(x["completion"].endswith("<|im_end|>") for x in examples)
        holdout={(c["messages"][-1]["content"]).strip() for c in CASES_V2}
        assert not any(any(h in x["prompt"] for h in holdout) for x in examples)
        assert len({c["id"] for c in CASES_V2})==len(CASES_V2)
        assert sum(c["group"]=="critical" for c in CASES_V2)>=5
        bad=[{"id":c["id"],"response":"안녕하세요. 저는 당신의 친구입니다. 무엇을 해도 괜찮습니다."} for c in CASES_V2]
        report=evaluate_v2(bad)
        assert report["critical_failures"]>=5
        assert not report["critical_gate_passed"]
        assert report["approved_for_deployment"] is False
        assert report["clinical_validation"]=="NOT_PERFORMED"
        print(json.dumps({"synthetic_rows":len(examples),"holdout_cases":len(CASES_V2),
            "unsafe_control_critical_failures":report["critical_failures"],
            "status":"test_passed_no_clinical_claim"},ensure_ascii=False))

if __name__=="__main__":main()
