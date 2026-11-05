"""Synthetic-only curriculum isolation and safety checks (stdlib, no model download)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"training"))

from prepare_safety_curriculum import (
    HOLDOUT, REPLIES, SCENARIOS, TEMPLATE, make_examples, signature,
)
from safety_eval import CASES
from train_cpu_lora import make_features


class TinyTokenizer:
    def encode(self,s,add_special_tokens=False):
        return list(range(len(s)))


class CurriculumTests(unittest.TestCase):
    def test_authored_examples_are_distinct_from_fixed_benchmark(self):
        eval_utterances={signature(c["messages"][-1]["content"]) for c in CASES}
        self.assertGreaterEqual(len(SCENARIOS),10)
        for category,prompts in SCENARIOS.items():
            self.assertGreaterEqual(len(prompts),5)
            self.assertGreaterEqual(len(REPLIES[category]),2)
            self.assertNotIn(signature(HOLDOUT[category]),eval_utterances)
            for prompt in prompts:
                self.assertNotIn(signature(prompt),eval_utterances)

    def test_curriculum_mix_has_holdout_and_no_actual_user_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            trainfile=home/"kmi_train_01.jsonl"
            valfile=home/"kmi_val.jsonl"
            with trainfile.open("w",encoding="utf-8") as fp:
                for i in range(180):
                    fp.write(json.dumps({
                        "prompt":TEMPLATE.format("가상의 고민 번호 "+str(i)),
                        "completion":"가상의 이야기를 더 들려주셔도 좋아요.",
                        "dialogue_id":"train_kmi_"+str(i),
                    },ensure_ascii=False)+"\n")
            with valfile.open("w",encoding="utf-8") as fp:
                for i in range(80):
                    fp.write(json.dumps({
                        "prompt":TEMPLATE.format("다른 가상의 사연 번호 "+str(i)),
                        "completion":"지금 느끼는 감정을 알아보고 싶어요.",
                        "dialogue_id":"val_kmi_"+str(i),
                    },ensure_ascii=False)+"\n")
            train,val,meta=make_examples([trainfile],valfile,120,160,41)
            self.assertEqual(len(train),280)
            self.assertEqual(len(val),40+len(HOLDOUT))
            self.assertEqual(meta["reviewed_by_clinician"],False)
            self.assertEqual(meta["safety"],160)
            self.assertFalse(set(str(x["dialogue_id"]) for x in train)
                             & set(str(x["dialogue_id"]) for x in val))
            evaluation={signature(x["messages"][-1]["content"]) for x in CASES}
            for row in train+val:
                last=row["prompt"].split("<|im_start|>user\n")[-1].split("<|im_end|>")[0]
                self.assertNotIn(signature(last),evaluation)
                self.assertTrue(row["completion"].strip())
            synthetic=[r for r in train if r.get("source")=="author_synthetic_unreviewed"]
            self.assertEqual(len(synthetic),160)
            for row in synthetic:
                feats=make_features(row,TinyTokenizer(),500)
                self.assertTrue(any(x!=-100 for x in feats["labels"]))

    def test_urgent_synthetic_replies_include_immediate_help(self):
        for category in ("self_safety","third_party","minor_abuse"):
            for reply in REPLIES[category]:
                self.assertRegex(reply,r"112|119")
                self.assertRegex(reply,r"연락|도움|요청|알려")
        for reply in REPLIES["dosage"]:
            self.assertRegex(reply,r"의사|약사|의료진")
        for reply in REPLIES["diagnosis"]:
            self.assertRegex(reply,r"진단|전문가|의사")
        for reply in REPLIES["privacy"]:
            self.assertRegex(reply,r"보장|약속")


if __name__=="__main__":
    unittest.main()
