# API 키 없이 로컬 AI 실행하기

외부 무료 호스팅은 사용량 제한·모델 변경·중단 가능성이 있어 무제한을 보장할 수 없습니다. 본인 컴퓨터에서 Ollama를 실행하면 외부 추론 API 키와 제공업체 사용량 과금 없이 사용할 수 있습니다. 모델 다운로드, 저장 공간, 메모리, 전력과 실행 시간은 필요합니다. 앱의 요청 보호 제한은 유지됩니다.

## 권장 선택지: Qwen3 8B

공식 Ollama 목록의 `qwen3:8b`는 약 5.2GB, `qwen3:4b`는 약 2.5GB 다운로드입니다. 실제 실행 메모리는 이보다 많으며 하드웨어에 따라 속도가 달라집니다. 8B가 모든 한국어 상담에서 더 낫다고 검증한 것은 아닙니다. 작은 컴퓨터는 4B부터 시험하세요.

1. https://ollama.com 에서 Ollama를 설치하고 실행합니다.
2. 터미널에서 `ollama pull qwen3:8b`를 실행합니다.
3. 이 저장소에서 `python run_local.py`를 실행합니다.
4. 표시된 로컬 주소를 열고 터미널의 이번 실행 초대 코드를 입력합니다.

4B를 쓰려면 먼저 `ollama pull qwen3:4b` 후 macOS/Linux에서 `MODEL_NAME=qwen3:4b python run_local.py`를 실행합니다. Windows PowerShell에서는 `$env:MODEL_NAME="qwen3:4b"` 후 실행하세요.

이 실행기는 웹 서버와 모델 연결을 이 컴퓨터로 제한합니다. 대화 추론은 Ollama에서 실행되지만, 기존 Firebase 설정이나 브라우저 음성 인식은 별도 서비스이므로 완전한 오프라인 서비스를 뜻하지 않습니다. 공개 배포 서버의 localhost는 방문자의 PC가 아닙니다. Render 무료 서버에서 이 모델이 자동 실행되지는 않습니다.

## 기존 호스팅 유지

`python app.py`는 기존 설정을 유지합니다. 우선순위는 명시적 MODEL_URL → OPENROUTER_API_KEY → 기본 Kilo 익명 연결입니다. OpenRouter 기본 모델은 코드와 동일한 `qwen/qwen3-8b:free`이며 가용성은 보장하지 않습니다. `openrouter/free`도 허용합니다. KEYLESS_BACKEND=off로 익명 연결을 끌 수 있습니다. 키는 환경 변수로만 설정하세요.

공식 참고: https://ollama.com/library/qwen3 · https://docs.ollama.com/api/openai-compatibility
