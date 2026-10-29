"""CPU-free unit tests for the guarded model preparation, training and release pipeline."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

from counselor_data import prepare, normalize_line
from train_cpu_lora import read_examples, make_features
from safety_eval import CASES, evaluate
from promote_browser import gate, BASE


class MinimalTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(range(1,len(text)+1))


class PipelineTests(unittest.TestCase):
    def test_data_rejects_unreviewed_and_personal_data(self):
        x = {"conversation_id":"session", "source":"original",
             "authorized":True, "deidentified":True, "expert_reviewed":False,
             "messages":[{"role":"user","content":"안녕하세요"},
                         {"role":"assistant","content":"네 안녕하세요"}]}
        with self.assertRaises(ValueError):
            normalize_line(x)
        x["expert_reviewed"] = True
        x["messages"][0]["content"] = "전화번호는 010-1234-5678 입니다"
        with self.assertRaises(ValueError):
            normalize_line(x)

    def test_approved_sessions_prepare_without_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"approved.jsonl"
            with src.open("w",encoding="utf-8") as fp:
                for i in range(80):
                    fp.write(json.dumps({"conversation_id":f"case-{i}","source":"synthetic-unit-test",
                        "authorized":True,"deidentified":True,"expert_reviewed":True,
                        "messages":[{"role":"user","content":f"가상 테스트 사례 {i}"},
                                    {"role":"assistant","content":f"가상 테스트 답변 {i}"}]},
                        ensure_ascii=False)+"\n")
            out=root/"splits"
            report=prepare(src,out)
            self.assertEqual(report["status"],"prepared_not_trained")
            data={name:read_examples(out/(name+".jsonl"))
                  for name in ("train","val","test")}
            self.assertTrue(all(data.values()))
            combined=[x["prompt"]+x["completion"] for rows in data.values() for x in rows]
            self.assertEqual(len(combined),80)
            self.assertEqual(len(set(combined)),80)

    def test_correct_target_only_sft_masking(self):
        features=make_features({"prompt":"abcdefghijklmnopqrstuvwxyz"*4,
                                 "completion":"응답"},MinimalTokenizer(),64)
        self.assertEqual(len(features["labels"]),len(features["input_ids"]))
        self.assertIn(-100,features["labels"])
        self.assertTrue(all(label==-100 for label in features["labels"][:-8]))

    def test_auto_audit_rejects_missing_and_unsafe_responses(self):
        r=evaluate([])
        self.assertEqual(r["case_count"],len(CASES))
        self.assertFalse(r["automatic_gate_passed"])
        self.assertGreater(r["critical_failures"],0)
        rows=[{"id":c["id"],"response":"언제든 안녕하세요! 상담을 하죠!"}
              for c in CASES]
        r=evaluate(rows)
        self.assertFalse(r["automatic_gate_passed"])
        self.assertFalse(r["independent_clinical_validation"])

    def test_release_is_fail_closed_without_expert_and_webgpu(self):
        fake={"status":"trained_not_safety_validated","base_model":BASE,
              "base_compatible_with_site":True,"steps":30,"adapter_sha256":"a"*64}
        audit={"automatic_gate_passed":True,"critical_failures":0,
               "case_count":len(CASES),
               "cases":[{"id":x["id"],"pass":True} for x in CASES]}
        with self.assertRaisesRegex(ValueError,"approvals"):
            gate(fake,audit,{},{})

    def test_no_release_activated(self):
        release=json.loads((ROOT/"model-release.json").read_text(encoding="utf-8"))
        self.assertFalse(release["active"])


if __name__ == "__main__":
    unittest.main()
