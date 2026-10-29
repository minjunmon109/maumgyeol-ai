"""Generate tiny, entirely synthetic fixtures for CPU-only CI schema checks.

Never used for production training and not a substitute for licensed counseling data.
"""
import argparse
import json
from pathlib import Path


def write_fixture(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    for split, n in (("train", 4), ("val", 2)):
        with (root / (split + ".jsonl")).open("w", encoding="utf-8") as fp:
            for i in range(n):
                row = {
                    "prompt": (
                        "<|im_start|>system\n당신은 정서지원 AI입니다.<|im_end|>\n"
                        "<|im_start|>user\n가상 테스트 " + split + " " + str(i) +
                        "<|im_end|>\n<|im_start|>assistant\n"
                    ),
                    "completion": "가상 응답 " + split + " " + str(i) + "<|im_end|>",
                }
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="/tmp/maumgyeol-ci-fixtures")
    a = p.parse_args()
    write_fixture(a.output)
    print("Generated synthetic unit-test-only data:", a.output)
