# 마음결 AI — Qwen3-4B GPU 학습과 연결

## 현재 실제 상태
GPU 학습 코드는 GitHub에 추가했지만 학습은 아직 실행되지 않았고, 학습된 가중치 및 학습 완료 기록이 없습니다. Render 사이트는 안내 체험 모드입니다.

## 1. 실제 학습하기
Colab 학습 노트북: https://colab.research.google.com/github/minjunmon109/maumgyeol-ai/blob/main/training/Train_Maumgyeol_Qwen3_GPU.ipynb

1. Colab의 런타임 > 런타임 유형 변경에서 NVIDIA GPU를 선택합니다. T4 16GB 이상 권장.
2. 런타임 > 모두 실행을 선택합니다.
3. 실제 CUDA 훈련 후 adapter_model.safetensors 및 training_manifest.json이 생성되었는지 확인합니다.
4. 훈련된 모델 어댑터 ZIP을 저장하고 공개 GitHub 저장소에 업로드하지 마세요.

현재 인공 데이터 생성기는 47건의 학습 대화와 10건의 검증 대화를 생성합니다. 매우 작은 인공 예시이므로 전문 상담 능력 확보를 보장하지 않습니다.

## 2. 항상 켜지는 GPU 서버
학습 완료된 LoRA 어댑터를 지속 실행 GPU 서버에 복사한 다음:

    python -m pip install -r training/requirements-gpu.txt
    export MODEL_API_KEY=YOUR_LONG_RANDOM_SECRET
    python training/serve_gpu.py --adapter training/outputs/maumgyeol-qwen3-lora --host 0.0.0.0 --port 8000

서버의 API는 인증이 필수이고 OpenAI Chat Completions 형식에 호환됩니다. 서버는 HTTPS 리버스 프록시 뒤에 두어야 합니다. 모델 가중치/개인정보/비밀키는 공개 저장소에 올리지 마세요.

## 3. Render 마음결 사이트에 연결
서비스 설정: https://dashboard.render.com/web/srv-dbhi8a8ae00c73drjdj0

Render > Environment에 환경 변수를 입력합니다:

    MODEL_URL=https://YOUR_GPU_HOST/v1/chat/completions
    MODEL_NAME=maumgyeol-qwen3-lora
    MODEL_PROVIDER=openai
    MODEL_API_KEY=GPU_SERVER_KEY_SAME_VALUE

GPU 서버 연결 테스트가 성공하면 마음결 사이트가 해당 모델의 응답을 이용합니다. 환경 변수 설정만으로 실제 접속이 확인된 것은 아니며, /api/chat으로 검증해야 합니다.

현재 연결된 Render 웹서비스에는 NVIDIA GPU가 없으며, 모델 서버 주소가 제공되지 않았습니다. 그래서 AI 생성형 응답은 아직 사이트에서 실행되고 있지 않습니다.

## 4. 보안과 전문가 검증
- 합성 데이터와 QLoRA만으로 자격·학위·상담 역량이 생기지는 않습니다.
- 실제 내담자 대화는 명시적 동의와 적절한 보호조치 없이 학습 데이터로 수집하지 않습니다.
- 자살·자해 위험 자동 탐지는 전문적 임상 평가를 대신하지 못합니다.
- 외부 GPU 서버가 인증·암호화·접근 제어 및 적절한 개인정보 처리를 갖추었는지 운영 전 검토합니다.
- 공개 배포 전 상담 전문가에 의한 안전 평가와 별도 품질 검증이 필요합니다.

## 출처
Qwen 모델 카드: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
Hugging Face TRL QLoRA: https://huggingface.co/docs/trl/main/en/peft_integration
