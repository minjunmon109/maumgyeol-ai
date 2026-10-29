"""Import consented/public-domain AnnoMI *demonstrations* for research experiments.

AnnoMI: Wu et al. (2022/2023), https://github.com/uccollab/AnnoMI
133 expert-annotated motivational-interviewing demonstrations, English only.
Demonstrations are not proof of real patient clinical encounters.
DO NOT represent training on these as clinical training/validation.
No raw transcripts are checked into the Maumgyeol repository.
"""
import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen

SOURCE = "https://raw.githubusercontent.com/uccollab/AnnoMI/main/AnnoMI-simple.csv"
ROOT = Path(__file__).resolve().parent


def convert_csv(text, out_dir, seed="maumgyeol-annomi-v1"):
    if len(text) > 15_000_000:
        raise ValueError("AnnoMI source unexpectedly large")
    dialogs = defaultdict(list)
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("mi_quality") != "high":
            continue  # No intentional imitation of low-quality MI demonstrations.
        if r.get("interlocutor") not in ("client", "therapist"):
            continue
        sid = str(r.get("transcript_id","")).strip()
        utterance = str(r.get("utterance_text","")).strip()
        if not sid or not utterance or len(utterance) > 2500:
            continue
        try: order = int(r["utterance_id"])
        except (ValueError, KeyError): continue
        dialogs[sid].append((order, r["interlocutor"], utterance))
    data = {"train":[], "val":[], "test":[]}
    source_sessions = {k:set() for k in data}
    for sid, rows in sorted(dialogs.items()):
        order = sorted(rows)
        gate = int(hashlib.sha256((seed + sid).encode()).hexdigest()[:8],16)%100
        split = "test" if gate < 15 else ("val" if gate < 30 else "train")
        history = []
        source_sessions[split].add(sid)
        for _, speaker, utterance in order:
            role = "user" if speaker=="client" else "assistant"
            if role=="assistant" and history and history[-1][0]=="user":
                prefix = "<|im_start|>system\n" + (
                    "You are a non-clinical emotional support AI. Respond with reflective "
                    "listening and open questions where relevant, never diagnose or prescribe. "
                    "Never claim to be a human therapist."
                ) + "<|im_end|>\n"
                for previous_role, previous_text in history[-6:]:
                    prefix += f"<|im_start|>{previous_role}\n{previous_text}<|im_end|>\n"
                prefix += "<|im_start|>assistant\n"
                data[split].append({"prompt":prefix,"completion":utterance+"<|im_end|>",
                                    "source_id":sid,"original_language":"English"})
            history.append((role,utterance))
    if min(map(len,data.values())) < 2:
        raise ValueError("Not enough high-quality samples for session-disjoint train/val/test")
    if any(source_sessions[a]&source_sessions[b]
           for a,b in (("train","val"),("train","test"),("val","test"))):
        raise AssertionError("Conversation leakage")
    output = Path(out_dir)
    output.mkdir(parents=True,exist_ok=True)
    for split, rows in data.items():
        with (output/(split+".jsonl")).open("w",encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps({k:row[k] for k in ("prompt","completion")},
                                    ensure_ascii=False)+"\n")
    return {"source":"AnnoMI, Wu et al., public-domain demonstrations",
            "high_quality_sessions":len(dialogs),
            "samples":{k:len(v) for k,v in data.items()},
            "status":"dataset_prepared_no_model_training",
            "clinical_validation":False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",help="Previously downloaded CSV. Omit to download original official CSV.")
    parser.add_argument("--out",default=str(ROOT/"data"/"annomi"))
    args=parser.parse_args()
    if args.input:
        text=Path(args.input).read_text(encoding="utf-8-sig")
    else:
        with urlopen(SOURCE,timeout=45) as response:
            data=response.read(15_000_001)
        text=data.decode("utf-8-sig")
    print(json.dumps(convert_csv(text,args.out),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
