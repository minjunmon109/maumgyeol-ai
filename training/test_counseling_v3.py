"""Sanity tests only: do not confuse synthetic regression checks with clinical approval."""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_counseling_v3_data import make_rows
from build_counseling_safety_sft import SAMPLES as OLD_SYNTHETIC
from safety_eval_v3 import CASES_V3, evaluate_v3

def main():
    examples=make_rows()
    assert len(examples)>=45
    assert len({x["dialogue_id"] for x in examples})==len(examples)
    assert all(x["synthetic"] is True and x["clinician_reviewed"] is False for x in examples)
    assert all(x["prompt"].startswith("<|im_start|>system") and x["completion"].endswith("<|im_end|>") for x in examples)
    assert sum("role" in x["prompt"] for x in examples)==0
    assert len(CASES_V3)>=20
    assert len({x["id"] for x in CASES_V3})==len(CASES_V3)
    assert sum(c["group"]=="critical" for c in CASES_V3)>=5
    holdout_prompts={c["messages"][-1]["content"] for c in CASES_V3}
    old_inputs={row[1].split("\n")[-1] for row in OLD_SYNTHETIC}
    for sample in examples:
        assert not any(prompt in sample["prompt"] for prompt in holdout_prompts)
    for prompt in holdout_prompts:
        assert prompt not in old_inputs
    danger=[{"id":x["id"],"response":"걱정하지 않아도 돼요. 기분을 전환해 보세요."} for x in CASES_V3]
    report=evaluate_v3(danger)
    assert report["critical_failures"]==report["critical_count"]
    assert report["critical_count"]>=5
    assert report["deployment_approved"] is False
    assert report["clinical_validation"]=="NOT_PERFORMED"
    affirmative=[]
    for case in CASES_V3:
        parts=[group[0] for group in case["require_all_groups"]]
        if case["group"]=="critical":
            parts.append("지금 즉시 안전을 확보하고 사람에게 연락하세요")
        affirmative.append({"id":case["id"],"response":"상황을 살펴볼게요. "+" ".join(parts)+" 도움을 요청하세요."})
    ok=evaluate_v3(affirmative)
    assert ok["critical_failures"]==0,ok
    assert ok["deployment_approved"] is False
    print(json.dumps({"new_synthetic_train":len(examples),"fresh_holdout":len(CASES_V3),
      "critical_cases":report["critical_count"],"unsafe_fixture_fails":report["critical_failures"],
      "gate_is_conservative":True,"clinical_approval":False},ensure_ascii=False))

if __name__=="__main__":
    main()
