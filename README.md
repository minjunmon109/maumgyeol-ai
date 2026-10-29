# 마음결 | Maumgyeol

한국어 정서지원 대화 웹사이트 시제품. 대화형 공개 가중치 AI 모델 연결 인터페이스를 제공하지만, 학습·전문성 검증은 완료되지 않았습니다. 내장된 안내 체험 모드는 언어모델이 아닙니다.

시작: `python app.py`. Render에 배포할 때 ACCESS_CODE와 AUTH_SECRET을 비밀 환경 변수로 설정하세요. 실제 모델은 MODEL_URL, MODEL_NAME, MODEL_API_KEY, MODEL_PROVIDER 환경 변수로 별도 연결해야 합니다.


API 키 없이 본인 컴퓨터에서 실행하려면 [로컬 AI 안내](FREE_AI_SETUP.md)를 참고하세요. `python run_local.py` 실행 전 Ollama 모델을 준비해야 합니다.
