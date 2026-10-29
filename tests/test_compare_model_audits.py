"""Unit tests for the non-clinical post-training model comparison gate."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from safety_eval import CASES
from compare_model_audits import compare, indexed, verified_adapter


class CompareAuditTests(unittest.TestCase):
    def rows(self, default="말씀해 주셔서 고맙습니다."):
        return [{"id": c["id"], "response": default} for c in CASES]

    def test_missing_duplicate_and_unexpected_ids_fail_closed(self):
        rows = self.rows()
        with self.assertRaisesRegex(ValueError, "exactly match"):
            indexed(rows[:-1])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            indexed(rows + [rows[0]])
        with self.assertRaisesRegex(ValueError, "exactly match"):
            indexed(rows + [{"id": "unknown", "response": "안녕하세요"}])
        with self.assertRaisesRegex(ValueError, "generated response text"):
            indexed([dict(x, response=None) if x["id"] == "hello" else x for x in rows])

    def test_critical_regression_detected_and_never_approved(self):
        base = self.rows()
        candidate = self.rows()
        for rows, value in ((base, "119에 연락해서 도움을 받으세요."),
                            (candidate, "그냥 참아도 됩니다.")):
            for item in rows:
                if item["id"] == "self_harm":
                    item["response"] = value
        report, base_audit, candidate_audit = compare(base, candidate, {"steps": 100})
        self.assertIn("self_harm", report["critical_regressions"])
        self.assertIn("self_harm", report["regressions"])
        self.assertFalse(report["automated_screen_passed"])
        self.assertIs(report["website_release_approved"], False)
        self.assertEqual(report["clinical_expert_review"], "NOT_DONE")
        self.assertGreater(candidate_audit["critical_failures"], base_audit["critical_failures"])

    def test_unvalidated_training_checkpoint_requires_real_matching_weights(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            weights = folder / "adapter_model.safetensors"
            weights.write_bytes(b"x" * 2048)
            digest = hashlib.sha256(weights.read_bytes()).hexdigest()
            record = {
                "status": "trained_not_safety_validated",
                "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
                "base_compatible_with_site": True,
                "steps": 100, "smoke_test_only": False,
                "adapter_sha256": digest,
                "train_loss": 2.7, "val_loss": 2.5,
                "approved_for_release": False, "clinician_reviewed": False,
            }
            manifest = folder / "training_manifest.json"
            manifest.write_text(json.dumps(record), encoding="utf-8")
            result = verified_adapter(folder)
            self.assertEqual(result["adapter_sha256"], digest)
            self.assertEqual(result["steps"], 100)
            record["steps"] = 6
            manifest.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Insufficient"):
                verified_adapter(folder)
            record["steps"] = 100
            record["adapter_sha256"] = "a" * 64
            manifest.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verified_adapter(folder)
            record["adapter_sha256"] = digest
            record["clinician_reviewed"] = True
            manifest.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "claim clinical approval"):
                verified_adapter(folder)


if __name__ == "__main__":
    unittest.main()
