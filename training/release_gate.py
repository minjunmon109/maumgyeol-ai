"""Release decision: default deny unless objective evaluation + real human/device evidence exists."""
import argparse,json
from pathlib import Path

def validate(report, reviews, device):
    reasons=[]
    if not report or report.get("evaluation_type")!="automated_safety_screen_only":
        reasons.append("Missing comparable automatic safety evaluation")
    elif not report.get("all_critical_cases_pass"):
        reasons.append("Critical safety regression")
    if len(reviews.get("independent_reviewers",[]))<2 or not reviews.get("credentials_verified"):
        reasons.append("Two independently credential-verified human reviewers are required")
    if reviews.get("critical_safety_findings",1)!=0 or not reviews.get("all_cases_scored",False):
        reasons.append("Human review incomplete or critical findings present")
    if not device.get("physical_iphone_tested") or not device.get("safari_tested") or not device.get("privacy_review_passed"):
        reasons.append("Physical iPhone/Safari/privacy evidence missing")
    if not device.get("memory_measurement_mb") or not device.get("latency_measurement_ms"):
        reasons.append("iPhone memory and latency measurements missing")
    if not reviews.get("explicit_release_approval") or not device.get("explicit_release_approval"):
        reasons.append("Release approvals missing")
    return {"approved":not reasons,"reasons":reasons}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--automated-report",required=True)
    ap.add_argument("--human-review",required=True)
    ap.add_argument("--device-review",required=True)
    ap.add_argument("--output",default="release-decision.json")
    args=ap.parse_args()
    def load(p):
        path=Path(p)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    result=validate(load(args.automated_report),load(args.human_review),load(args.device_review))
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    if not result["approved"]: raise SystemExit("RELEASE BLOCKED")
if __name__=="__main__":main()
