"""Fail-closed dataset provenance/rights check before experimental model training."""
import argparse
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def check():
    manifest=json.loads((ROOT/"training/dataset_license_manifest.json").read_text(encoding="utf-8"))
    approved=[s for s in manifest["sources"] if s["allowed_for_experimental_training"]]
    if not approved: raise ValueError("No approved training sources")
    if manifest.get("deployment_authorization") is not False:
        raise ValueError("Experimental training manifest cannot authorize deployment")
    for source in approved:
        if source["license"]!="CC-BY-4.0" or not source.get("attribution"):
            raise ValueError(f"Rights/attribution not verified: {source['id']}")
        paths=sorted(glob.glob(str(ROOT/source["files_glob"])))
        if not paths: raise ValueError(f"Training source missing: {source['id']}")
        seen=0
        for path in paths:
            for line_number,line in enumerate(Path(path).open(encoding="utf-8"),1):
                if not line.strip(): continue
                obj=json.loads(line)
                if obj.get("source")!=source["required_source_field"]:
                    raise ValueError(f"Unapproved source at {path}:{line_number}")
                if not isinstance(obj.get("prompt"),str) or not isinstance(obj.get("completion"),str):
                    raise ValueError(f"Invalid example at {path}:{line_number}")
                # Detect basic accidental personal identifiers. Does not guarantee de-identification.
                if re.search(r"\\b01[016789][- ]?\\d{3,4}[- ]?\\d{4}\\b|[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}",obj["prompt"]+" "+obj["completion"]):
                    raise ValueError(f"Potential personal data at {path}:{line_number}")
                seen+=1
        print(json.dumps({"source":source["id"],"examples_checked":seen,"license":source["license"],"status":"passed_provenance_screen_not_legal_certification"},ensure_ascii=False))
    print("DEPLOYMENT BLOCKED: Expert review, iPhone real-device testing and final authorization are required")
if __name__=="__main__":
    check()
