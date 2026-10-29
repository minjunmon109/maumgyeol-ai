"""Create CPU-feasible, conversation-disjoint KMI train/validation subsets.

Uses only research KMI synthetic dialogues; does NOT imply clinical validation.
Files excluded by .gitignore.
"""
import argparse, hashlib, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def select(paths, limit):
    chosen=[]; used=set()
    for path in paths:
        with Path(path).open("r",encoding="utf-8") as inp:
            for line in inp:
                if not line.strip(): continue
                row=json.loads(line)
                sid=str(row.get("dialogue_id", ""))
                if not sid: raise ValueError("Missing KMI dialogue ID")
                if sid in used: continue
                if not isinstance(row.get("prompt"),str) or not isinstance(row.get("completion"),str):continue
                chosen.append({"prompt":row["prompt"],"completion":row["completion"]})
                used.add(sid)
                if len(chosen)>=limit:return chosen
    raise ValueError(f"Insufficient distinct KMI dialogues: requested {limit}, found {len(chosen)}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default=str(HERE/"data"/"cpu-trial"))
    p.add_argument("--train-count",type=int,default=32)
    p.add_argument("--val-count",type=int,default=8)
    args=p.parse_args()
    paths=sorted((HERE/"open_data").glob("kmi_train_*.jsonl"))
    if not paths:raise SystemExit("KMI train shards missing")
    sets={"train":select(paths,args.train_count),
          "val":select([HERE/"open_data"/"kmi_val.jsonl"],args.val_count)}
    dest=Path(args.output);dest.mkdir(parents=True,exist_ok=True)
    for key,rows in sets.items():
        with (dest/(key+".jsonl")).open("w",encoding="utf-8") as out:
            for row in rows:out.write(json.dumps(row,ensure_ascii=False)+"\n")
    manifest={"source":"Kim et al. KMI (NAACL 2025), CC BY 4.0, LLM-synthetic expert-reviewed study",
              "counts":{k:len(v) for k,v in sets.items()},
              "split":"upstream KMI conversation-disjoint split; one reply per dialogue",
              "clinical_validation":False}
    (dest/"provenance.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False))

if __name__=="__main__":main()
