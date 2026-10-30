"""Offline fail-closed checks for V3 release gate; fixtures do NOT establish real reviews."""
from promote_browser_v3 import candidate_release,REQUIRED_CASES
def main():
    score=lambda size:{"candidate":{"passed":size,"total":size,"critical_failures":0},"baseline":{"passed":0,"total":size,"critical_failures":size}}
    evidence={"training_steps":90,"fresh_holdout_cases":22,"old_holdout_cases":14,
       "adapter_sha256":"a"*64,"all_critical_heuristic_checks_passed":True,
       "benchmarks":{"fresh_v3":score(22),"regression_v2":score(14)}}
    human={"independent_expert_review_completed":True,"explicit_deployment_approval":True,
       "data_permission_confirmed":True,"privacy_review_completed":True,
       "case_scores":{x:5 for x in REQUIRED_CASES},
       "reviewers":["TEST-REVIEWER-ONE","TEST-REVIEWER-TWO"],"unsafe_case_ids":[]}
    browser={"model_conversion_completed":True,"real_iphone_safari_test_passed":True,
       "independent_output_reviewed":True,"adapter_sha256":"a"*64,
       "model_id":"Maumgyeol-Qwen25-1.5B-V3-FAKE",
       "model_url":"https://example.invalid/fake-model/",
       "model_lib_url":"https://example.invalid/fake-lib.wasm"}
    # A complete synthetic fixture ensures the gate isn't impossible, not that a real model is approved.
    result=candidate_release(evidence,human,browser)
    assert result["active"] is True
    cases=[
        ("missing-expert",evidence,{**human,"independent_expert_review_completed":False},browser),
        ("unsafe-review",evidence,{**human,"unsafe_case_ids":["v3_suicide"]},browser),
        ("incomplete-scores",evidence,{**human,"case_scores":{}},browser),
        ("weak-score",evidence,{**human,"case_scores":{**human["case_scores"],"v3_unknown":3}},browser),
        ("single-reviewer",evidence,{**human,"reviewers":["ONE"]},browser),
        ("unsafe-model",{**evidence,"benchmarks":{**evidence["benchmarks"],"fresh_v3":{"candidate":{"passed":21,"total":22,"critical_failures":1}}}},human,browser),
        ("missing-conversion",evidence,human,{**browser,"model_conversion_completed":False}),
        ("no-iphone",evidence,human,{**browser,"real_iphone_safari_test_passed":False}),
        ("untrusted-URL",evidence,human,{**browser,"model_url":"http://example.com"}),
        ("sha-mismatch",evidence,human,{**browser,"adapter_sha256":"b"*64}),
    ]
    for name,a,b,c in cases:
        try:candidate_release(a,b,c)
        except (ValueError,KeyError):continue
        raise AssertionError("Unapproved release was not blocked: "+name)
    print("10 production release blockers correctly fail closed; no clinical approval is implied")
if __name__=="__main__":main()
