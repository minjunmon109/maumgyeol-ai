"""Offline regression test for blinded counseling human-review protocol."""
import csv
import json
import tempfile
from pathlib import Path
from blind_counseling_review import CASES_V2,FIELDS,build,aggregate

def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        old=root/"old.json";new=root/"new.json";out=root/"review"
        old.write_text(json.dumps([{"id":c["id"],"response":"가상 A 응답"} for c in CASES_V2],ensure_ascii=False),encoding="utf-8")
        new.write_text(json.dumps([{"id":c["id"],"response":"가상 B 응답"} for c in CASES_V2],ensure_ascii=False),encoding="utf-8")
        build(old,new,out)
        blind=json.loads((out/"blind_pairs.json").read_text(encoding="utf-8"))
        assert len(blind)==len(CASES_V2)
        assert all("response_left" in c and "response_right" in c for c in blind)
        assert all("model" not in json.dumps(row,ensure_ascii=False).lower() for row in blind)
        template=list(csv.DictReader((out/"human_review_template.csv").open(encoding="utf-8-sig")))
        assert len(template)==2*len(CASES_V2)
        scoring=[]
        for reviewer in ["licensed-reviewer-1","licensed-reviewer-2"]:
            for case in CASES_V2:
                for side in ["left","right"]:
                    row={name:"4" for name in FIELDS}
                    row.update(case_id=case["id"],side=side,reviewer_id=reviewer,critical_unsafe="0",evidence_or_concern="")
                    scoring.append(row)
        scores=root/"scored.csv"
        with scores.open("w",encoding="utf-8",newline="") as fp:
            w=csv.DictWriter(fp,fieldnames=FIELDS);w.writeheader();w.writerows(scoring)
        result=aggregate(scores,out/"answer_key_PRIVATE.json")
        assert result["reviewers"]==2 and result["cases"]==len(CASES_V2)
        assert result["approved_for_deployment"] is False
        assert all(m["critical_safety_case_failures"]==0 for m in result["stats"].values())
        scoring[0]["critical_unsafe"]="1"
        with scores.open("w",encoding="utf-8",newline="") as fp:
            w=csv.DictWriter(fp,fieldnames=FIELDS);w.writeheader();w.writerows(scoring)
        result=aggregate(scores,out/"answer_key_PRIVATE.json")
        assert sum(m["critical_safety_case_failures"] for m in result["stats"].values())==1
        print("Blind counselor review workflow tests passed (human ratings simulated, NOT clinical approval)")
if __name__=="__main__":main()
