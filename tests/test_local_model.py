import os
import unittest
from unittest.mock import patch
with patch.dict(os.environ, {'ACCESS_CODE':'test','AUTH_SECRET':'test-secret','MODEL_PROVIDER':'ollama','MODEL_NAME':'qwen3:8b','MODEL_URL':'http://127.0.0.1:11434/api/chat'}):
    import app

class LocalModelTests(unittest.TestCase):
    def test_local_payload(self):
        payload = app.build_chat_payload([{'role':'user','content':'안녕하세요'}], stream=True)
        self.assertFalse(payload['think'])
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['options']['num_predict'],512)
        self.assertNotIn('provider',payload)
        self.assertNotIn('max_tokens',payload)

    def test_no_external_default(self):
        self.assertFalse(app.FREE_EXTERNAL)
        self.assertFalse(app.KEYLESS_BACKEND)
        self.assertNotIn('Authorization',app.model_stream_request([{'role':'user','content':'안녕'}]).headers)
