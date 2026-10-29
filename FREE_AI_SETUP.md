# API 키 없는 로컬 AI

기본 모델은 **Qwen3 8B**, 실행기는 **Ollama**입니다. 익명 외부 무료 API 자동 연결을 제거했습니다. 더 가벼운 기기에서는 `qwen3:4b`를 선택하세요. 한국어 상담 품질의 우월성은 아직 비교 검증하지 않았습니다.

1. https://ollama.com 에서 Ollama를 설치하고 실행합니다.
2. `ollama pull qwen3:8b`로 모델을 내려받습니다(수 GB 다운로드).
3. 서버 환경에 `ACCESS_CODE`와 충분히 긴 무작위 `AUTH_SECRET`을 설정합니다.
4. `python app.py`를 실행하고 http://localhost:10000 에 접속합니다.

기본값: `MODEL_PROVIDER=ollama`, `MODEL_NAME=qwen3:8b`, `MODEL_URL=http://127.0.0.1:11434/api/chat`.
4B 사용 시 `ollama pull qwen3:4b` 후 `MODEL_NAME=qwen3:4b`를 설정하세요.

API 키·호출 요금·제공업체의 일일 호출 할당량은 없습니다. 컴퓨터 메모리, 전력, 처리 속도, 동시 요청 수의 물리적 한계는 있습니다. 앱의 과도한 요청 방지 제한은 유지됩니다. 모델 다운로드 후 추론에 외부 모델 서비스는 필요하지 않습니다. Firebase를 구성했다면 로그인·기록 동기화는 별도의 외부 서비스입니다.

**Render 배포 주의:** Render 서버의 localhost는 사용자의 PC가 아닙니다. 기존 무료 웹 서버만으로 8B 모델이 동작한다고 보장할 수 없습니다. 모델을 실행할 충분한 자원이 있는 동일 머신에서 앱을 실행하거나 접근 가능한 별도 모델 서버를 구성해야 합니다. Ollama 포트를 인터넷에 그대로 공개하지 마세요. 기존 `MODEL_URL`, `MODEL_NAME`, `MODEL_PROVIDER` 환경 변수가 있으면 기본값보다 우선합니다. 기존 OPENROUTER_API_KEY와 KEYLESS_BACKEND 자동 선택은 제거되었습니다.

공식 참고: https://ollama.com/library/qwen3:8b · https://docs.ollama.com/api/chat
