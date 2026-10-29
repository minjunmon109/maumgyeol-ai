"""Strict preparer for legally obtained, de-identified, expert-reviewed counseling dialogs.
No external network/API, no packaged patient records. Standard-library only.

Input JSONL (ONE conversation per line):
{"conversation_id":"anonymous-session-001","source":"AI-Hub 심리상담 데이터",
 "authorized":true,"deidentified":true,"expert_reviewed":true,
 "messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}

The flags are declarations by the data steward; automated processing CANNOT
verify licenses, professional review, or true de-identification.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

BASE_SYSTEM = (
    "당신은 마음결의 한국어 정서지원 AI입니다. 실제 자격 있는 상담사나 의사가 아니며 "
    "진단·치료·처방이나 절대적 비밀보장을 약속하지 않습니다. 상황에 맞춰 공감하고 "
    "판단하지 않고 경청하며, 원하지 않는 조언을 강요하지 않습니다. "
    "자해·자살 및 즉각적 위험에는 안전 확보와 사람·전문기관의 도움을 우선합니다."
)
PII = [
    ("email", re.compile(r"(?i)[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}")),
    ("phone", re.compile(r"(?<!\d)(?:01[016789])[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")),
    ("rrn", re.compile(r"(?<!\d)\d{6}[- ]?[1-8]\d{6}(?!\d)")),
]
ALLOWED = {"user", "assistant"}


def normalize_line(obj):
    if not isinstance(obj, dict):
        raise ValueError("Expected one JSON object per conversation")
    for k in ("conversation_id", "source"):
        if not isinstance(obj.get(k), str) or not obj[k].strip():
            raise ValueError("Missing " + k)
    for k in ("authorized", "deidentified", "expert_reviewed"):
        if obj.get(k) is not True:
            raise ValueError("Missing required data steward approval: " + k)
    dialog = obj.get("messages")
    if not isinstance(dialog, list) or len(dialog) < 2:
        raise ValueError("Need a conversation with at least two turns")
    norm = []
    for m in dialog:
        if not isinstance(m, dict) or m.get("role") not in ALLOWED:
            raise ValueError("Only 'user' and 'assistant' roles are permitted")
        text = m.get("content")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Empty or invalid turn")
        text = " ".join(text.strip().split())
        if len(text) > 1500:
            raise ValueError("Turn is too long")
        if any(rx.search(text) for _, rx in PII):
            raise ValueError("Detected possible identifying information; review and redact offline")
        if norm and norm[-1]["role"] == m["role"]:
            raise ValueError("Non-alternating roles: manually inspect the source")
        norm.append({"role": m["role"], "content": text})
    if norm[0]["role"] != "user" or not any(x["role"] == "assistant" for x in norm):
        raise ValueError("Conversation must begin with a user and contain a reply")
    return obj["conversation_id"].strip(), obj["source"].strip(), norm


def format_example(messages, assistant_index):
    context = messages[max(0, assistant_index - 8):assistant_index]
    parts = ["<|im_start|>system\n" + BASE_SYSTEM + "<|im_end|>"]
    for m in context:
        parts.append("<|im_start|>" + m["role"] + "\n" + m["content"] + "<|im_end|>")
    parts.append("<|im_start|>assistant\n")
    return {"prompt": "\n".join(parts),
            "completion": messages[assistant_index]["content"] + "<|im_end|>"}


def prepare(input_path, output_dir, seed="maumgyeol-v1"):
    input_path, output_dir = Path(input_path), Path(output_dir)
    if not input_path.is_file():
        raise FileNotFoundError("Approved data file not found; will NOT invent professional data")
    if input_path.stat().st_size > 250 * 1024 * 1024:
        raise ValueError("File exceeds 250MB review limit")
    if input_path.resolve() == output_dir.resolve():
        raise ValueError("Input and output path conflict")
    seen, datasets, counters = set(), {"train": [], "val": [], "test": []}, Counter()
    for line_idx, line in enumerate(input_path.open(encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            id_, source, turns = normalize_line(json.loads(line))
            hid = hashlib.sha256((source + "::" + id_).encode()).hexdigest()
            if hid in seen:
                raise ValueError("Duplicate conversation id")
            seen.add(hid)
            # Split whole conversations, never individual turns.
            bucket = int(hashlib.sha256((seed + hid).encode()).hexdigest()[:8], 16) % 100
            split = "test" if bucket < 15 else ("val" if bucket < 30 else "train")
            for i, m in enumerate(turns):
                if m["role"] != "assistant":
                    continue
                row = format_example(turns, i)
                row["group_hash"] = hid[:16]
                datasets[split].append(row)
                counters[split] += 1
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f"Line {line_idx}: {exc}") from exc
    if len(seen) < 30 or min(len(v) for v in datasets.values()) < 2:
        raise ValueError("Need at least 30 unique reviewed conversations and nonempty session-disjoint splits")
    sets = {key: {x["group_hash"] for x in vals} for key, vals in datasets.items()}
    if sets["train"] & sets["test"] or sets["train"] & sets["val"] or sets["val"] & sets["test"]:
        raise AssertionError("Conversation-level leakage detected")
    output_dir.mkdir(parents=True, exist_ok=True)
    for split, rows in datasets.items():
        # Do not put these derived patient texts in GitHub or public logs.
        dest = output_dir / (split + ".jsonl")
        with dest.open("w", encoding="utf-8") as out:
            for row in rows:
                row.pop("group_hash")
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        try:
            dest.chmod(0o600)
        except OSError:
            pass
    report = {
        "status": "prepared_not_trained",
        "data_source": "user-provided; no text exported to report",
        "conversation_count": len(seen),
        "sample_count": dict(counters),
        "split_method": "session-hash 70/15/15 approx",
        "source_rights_and_expert_review": "DECLARED BY USER, NOT INDEPENDENTLY VERIFIED",
        "privacy": "regular-expression screen only; human redaction audit required",
    }
    (output_dir / "preparation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="Locally authorized & reviewed, normalized JSONL")
    p.add_argument("--output", default="training/data/approved")
    args = p.parse_args()
    print(json.dumps(prepare(args.input, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
