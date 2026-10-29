"""Assemble the attributed KMI corpus into actual CPU/LoRA training files.

Source: Kim et al., NAACL 2025, Korean Motivational Interviewing (CC BY 4.0).
This corpus is synthetic expert-informed dialogue, not real patient counseling.
Written data files are gitignored and need no API keys.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "open_data"
EXPECTED = {"train":5997, "val":1267, "test":1294}


def prepare(source=SOURCE, output=None):
    source=Path(source)
    output=Path(output) if output else ROOT/"data"/"kmi"
    paths={
        "train":[source/f"kmi_train_{x:02d}.jsonl" for x in range(1,7)],
        "val":[source/"kmi_val.jsonl"],
        "test":[source/"kmi_test.jsonl"]
    }
    groups={}
    prepared={}
    for split, files in paths.items():
        rows, ids=[], set()
        for fp in files:
            if not fp.is_file():
                raise FileNotFoundError(fp)
            for i,line in enumerate(fp.open(encoding="utf-8"),1):
                if not line.strip():continue
                obj=json.loads(line)
                if obj.get("source")!="Kim et al. KMI NAACL 2025 CC BY 4.0":
                    raise ValueError(f"{fp}:{i}: source attribution mismatch")
                if not isinstance(obj.get("dialogue_id"),int):
                    raise ValueError(f"{fp}:{i}: missing source conversation ID")
                if not isinstance(obj.get("prompt"),str) or not isinstance(obj.get("completion"),str):
                    raise ValueError(f"{fp}:{i}: invalid prompt/completion schema")
                if not obj["prompt"].endswith("<|im_start|>assistant\n"):
                    raise ValueError(f"{fp}:{i}: invalid chat context")
                if not obj["completion"].endswith("<|im_end|>"):
                    raise ValueError(f"{fp}:{i}: invalid target")
                ids.add(obj["dialogue_id"])
                rows.append({"prompt":obj["prompt"],"completion":obj["completion"]})
        if len(rows)!=EXPECTED[split]:
            raise ValueError(f"{split}: expected {EXPECTED[split]} examples, got {len(rows)}")
        groups[split]=ids
        prepared[split]=rows
    if (groups["train"] & groups["val"] or
        groups["train"] & groups["test"] or
        groups["val"] & groups["test"]):
        raise ValueError("Source conversation leakage across splits")
    if len(groups["train"] | groups["val"] | groups["test"]) != 1000:
        raise ValueError("Expected exactly 1000 source dialogues")
    output.mkdir(parents=True,exist_ok=True)
    for split,rows in prepared.items():
        with (output/(split+".jsonl")).open("w",encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(row,ensure_ascii=False)+"\n")
    return {"status":"prepared_not_trained","source":"KMI Kim et al. CC BY 4.0",
            "counts":{k:len(v) for k,v in prepared.items()},
            "source_conversations":1000,"clinical_validation":False,
            "output_directory":str(output)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",default=str(ROOT/"data"/"kmi"))
    args=parser.parse_args()
    print(json.dumps(prepare(output=args.output),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
