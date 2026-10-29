"""Minimal non-clinical guardrail tests for the Maumgyeol conversation policy."""
import unittest
from counselor_policy import safety_response, demo_reply, safe_model_output, COUNSELOR_PROMPT

class CounselorPolicyTests(unittest.TestCase):
    def test_self_harm(self):
        result=safety_response("자살 생각이 들어요")
        self.assertIsNotNone(result)
        self.assertIn("109",result[0])
    def test_imminent_threat(self):
        result=safety_response("지금 폭행을 당하고 있어요")
        self.assertIsNotNone(result)
        self.assertIn("112",result[0])
    def test_normal_greeting(self):
        self.assertIsNone(safety_response("안녕하세요"))
    def test_anxiety(self):
        self.assertIn("걱정",demo_reply([{"role":"user","content":"걱정이 너무 많아요"}]))
    def test_listening_request(self):
        self.assertIn("서둘러",demo_reply([{"role":"user","content":"그냥 들어줘"}]))
    def test_not_impostor(self):
        self.assertIn("체험",demo_reply([{"role":"user","content":"너 누구야?"}]))
    def test_model_disclaimer(self):
        self.assertIn("실제",safe_model_output("저는 실제 상담사입니다."))
    def test_medical_certainty(self):
        self.assertIn("확정",safe_model_output("당신은 확실히 우울증 환자입니다."))
    def test_prompt_non_diagnostic(self):
        self.assertIn("진단",COUNSELOR_PROMPT)
    def test_prompt_collaborative(self):
        self.assertIn("동기강화상담",COUNSELOR_PROMPT)

if __name__=="__main__":
    unittest.main()
