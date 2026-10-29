"""마음결 한국어 심리·정서지원 AI 정책.
의료기기, 진단 도구, 면허 있는 상담사가 아니다.
본 프롬프트·패턴은 전문가 검증을 대체하지 않는다.
"""
import re

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"

COUNSELOR_PROMPT = """당신의 이름은 마음결이며, 일대일 한국어 심리상담 대화를 전문적으로 돕는 상담형 인공지능입니다. 말투와 접근법은 숙련된 심리상담 전문가처럼 차분하고 섬세해야 합니다. 실제 사람인 척하거나 상담사·의사 면허, 학위, 임상 경력, 치료 능력을 가졌다고 주장하지 마세요. 신분을 물으면 자동 상담 도우미라고 답하세요.

[상담 원칙]
- 사용자의 구체적인 상황을 먼저 이해하고 그 상황에 맞는 감정과 갈등을 조심스럽게 반영하세요. 사실과 해석, 감정과 욕구를 구분해 이해를 돕습니다.
- 사람중심적 경청, 동기강화상담, 인지행동적 접근, 수용과 가치 탐색을 상황에 맞춰 사용합니다. 기법 이름을 설명하거나 자동으로 연습을 강요하지 않습니다.
- 한 번에 한 가지 주제에 집중하세요. 지금 원하는 것이 경청인지, 정리인지, 해결책인지 맥락에 따라 맞춰 줍니다. '들어줘'라고 하면 조언하지 않습니다.
- 빈 공감문구, 근거 없는 안심, 도덕적 훈계, 무조건적인 칭찬, 연속 질문, 성급한 진단은 피하세요.
- 자신의 가치를 부정하거나 타인의 의도를 단정하는 말이 나오면 사실과 해석을 부드럽게 분리합니다. 판단을 강요하지 않고 선택권을 존중합니다.
- 주고받은 대화의 맥락을 기억한 것처럼 활용하되, 전달되지 않은 개인사나 감정을 지어내지 마세요.

[대화 방식]
답변은 원칙적으로 자연스러운 존댓말의 짧은 한국어 1~3문장, 약 50~150자입니다. 마지막에 필요한 경우에만 질문 하나를 합니다. 간단한 인사에는 짧게 답합니다. 사용자가 자세한 설명을 요청할 때만 길게 답합니다. 영어, 로마자, 외국어 문장, 분석 과정과 태그를 출력하지 않습니다.
예: '친구가 답장하지 않아 불안해요' → '답장이 없는 사실보다 그 침묵이 관계의 변화처럼 느껴지시는군요. 아직 상대방의 마음은 알 수 없지만, 그 생각이 떠오를 때 어떤 점이 가장 불안하신가요?'

[안전과 한계]
자살·자해·폭력·학대·급성 위험에는 상담식 탐색보다 즉각적인 안전 확인, 주변 사람의 도움, 한국의 119·112·109 안내를 우선합니다. 자해 방법이나 위험한 절차를 제공하지 않습니다. 진단, 처방, 약물 조정, 치료 보장을 하지 않고 필요하면 전문가 도움을 권합니다. 전문 상담을 대체한다거나 비밀유지가 완벽하다고 말하지 마세요.
"""

# 즉각적인 위험을 암시하는 표현. 키워드 규칙만으로 위험도 진단을 하지 않는다.
SELF_HARM = re.compile(
    r"자살|자해|목숨(?:을|을\s*)끊|죽고\s*싶|살고\s*싶지|"
    r"스스로\s*(?:죽|해치)|극단적\s*선택|"
    r"suicid|kill\s*myself|end\s*my\s*life|hurt\s*myself|"
    r"뛰어내리|목을\s*매|약을\s*(?:잔뜩|한꺼번에|많이)\s*(?:먹|삼켰)",
    re.I
)
IMMEDIATE_HARM = re.compile(
    r"누군가(?:를|에게)\s*(?:죽|해치)|살인\s*하고\s*싶|칼로\s*찌르|"
    r"폭행(?:을)?\s*당하|맞고\s*있|감금|강제로\s*성관계|"
    r"someone\s*is\s*hurting\s*me|kill\s*someone",
    re.I
)
DISTRESS = re.compile(r"불안|초조|걱정|공황|두려|떨리|긴장", re.I)
LOW_MOOD = re.compile(r"우울|슬프|외롭|공허|무기력|지쳤|힘들|절망", re.I)
RELATIONSHIP = re.compile(r"친구|연인|가족|부모|이별|헤어|관계|왕따|따돌림", re.I)
STRESS = re.compile(r"학교|학업|시험|취업|직장|회사|성적|실패|과제|압박|번아웃", re.I)
ANGER = re.compile(r"화가\s*나|분노|짜증|억울|배신|미움", re.I)
DIAGNOSIS = re.compile(r"진단|병명|우울증\s*인가|공황장애\s*인가|adhd\s*인가|약\s*(?:복용|처방|용량)", re.I)

def safety_response(text):
    if SELF_HARM.search(text):
        return (
            "말씀하신 내용에서 안전이 걱정돼요. 지금 자신을 해칠 가능성이 있거나 이미 다쳤다면 "
            "즉시 119 또는 112에 연락하고, 곁에 있는 믿을 만한 사람에게 함께 있어 달라고 부탁해 주세요. "
            "한국에서는 자살예방상담전화 109에서도 도움을 받을 수 있습니다. 지금은 안전한 장소에 계신가요?",
            "concern"
        )
    if IMMEDIATE_HARM.search(text):
        return (
            "지금 안전이 우선입니다. 직접적인 위협을 받고 있다면 가능할 때 안전한 장소로 이동해 "
            "112 또는 119에 연락하고, 신뢰할 수 있는 사람에게 즉각적인 도움을 요청하세요. "
            "지금 안전한 곳에서 이야기하고 계신가요?",
            "concern"
        )
    return None

def demo_reply(messages):
    """규칙 기반 상담 대화 *체험*. 생성형 LLM이나 임상 상담사를 사칭하지 않는다."""
    text=messages[-1]["content"].strip()
    s=text.lower()
    if re.search(r"누구야|ai야|너\s*뭐야|정체|사람이야|상담사야", s):
        return ("저는 마음결의 AI 정서지원 도우미를 위한 **안내 체험 모드**예요. "
                "아직 학습된 언어모델이 연결되지 않아 준비된 문장으로 반응하고 있습니다. "
                "진단이나 치료를 제공할 수는 없지만 마음을 정리하는 대화를 시작할 수 있어요.")
    if re.search(r"안녕|반가워|hello", s):
        return "안녕하세요. 지금 어떤 이야기를 나누고 싶으세요? 편한 곳부터 시작해도 좋습니다."
    if re.search(r"그냥\s*들어|조언\s*하지\s*마|들어줘", s):
        return "알겠어요. 해결책을 서둘러 제안하지 않고 이야기를 듣겠습니다. 이어서 말씀해 주세요."
    if DIAGNOSIS.search(s):
        return ("말씀만으로 특정 질환을 진단하거나 약을 결정할 수는 없어요. "
                "증상이나 일상에서 겪는 어려움을 정리해 드릴 수는 있습니다. "
                "정확한 평가나 약물 관련 결정은 정신건강 전문가와 상담해 주세요.")
    if RELATIONSHIP.search(s):
        return ("가까운 관계에서 일어난 일이라 더 복잡하게 느껴질 수 있겠어요. "
                "상대의 의도를 추측하기보다는, 어떤 일이 있었고 그때 어떤 마음이 들었는지부터 나눠볼까요?")
    if DISTRESS.search(s):
        return ("불안이나 걱정이 이어지면 몸과 마음이 동시에 긴장될 수 있어요. "
                "지금 가장 크게 걸리는 상황은 무엇인가요? 원하신다면 그 마음을 하나씩 정리해 볼 수 있어요.")
    if LOW_MOOD.search(s):
        return ("그만큼 지치고 힘든 마음이 있다는 이야기를 들었어요. "
                "당장 괜찮아져야 한다고 재촉하지 않을게요. 어떤 일이 가장 무겁게 느껴지나요?")
    if ANGER.search(s):
        return ("많이 속상하고 화가 나는 상황인 것 같아요. "
                "무엇이 가장 부당하거나 마음에 걸렸는지 말해 주시겠어요?")
    if STRESS.search(s):
        return ("해야 할 일이나 기대가 많을 때는 압박이 커질 수 있어요. "
                "지금 가장 부담스러운 한 가지를 골라본다면 무엇일까요?")
    if len(messages)>2:
        return ("계속 이야기해 주셔서 고마워요. 지금 느끼는 감정과 그 감정이 생긴 상황을 "
                "구분해 보면 도움이 될 수도 있어요. 방금 이야기에서 가장 중요한 부분은 무엇인가요?")
    return ("무슨 이야기를 해야 할지 정해두지 않아도 괜찮아요. "
            "지금 마음에 가장 먼저 떠오르는 일부터 들려주시겠어요? "
            "현재는 학습된 모델이 아닌 대화 체험 모드로 답하고 있습니다.")

def safe_model_output(text):
    """Prevent false credentials/unsafe medical assertions; deliver Korean-only text."""
    if not isinstance(text, str):
        return "말씀하신 내용을 조금 더 들려주실 수 있을까요?"
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    text = re.sub(r"(?is)`{3}[\s\S]*?`{3}", "", text)
    text = text.strip()
    if re.search(r"(?i)(나는|저는).{0,22}(석사\s*학위|면허\s*있는\s*(?:심리|상담)|실제\s*상담사|정신과\s*의사)", text):
        return "저는 마음결의 자동 심리상담 대화 도우미이며, 실제 자격을 가진 상담사가 아닙니다. 어떤 이야기를 나누고 싶으세요?"
    if re.search(r"(?i)확실히\s*(?:우울증|조현병|양극성|adhd)|(?:약|복용량).{0,12}(두\s*배|늘리세요|끊으세요)", text):
        return "대화만으로 질환을 확정하거나 약물 복용을 조정할 수는 없습니다. 관련 내용은 자격 있는 전문가에게 확인해 주세요."

    # Replace common foreign expressions without changing the user's meaning.
    dictionary = {
        "CBT": "인지행동적 접근",
        "ACT": "수용전념적 접근",
        "AI": "인공지능",
        "OK": "괜찮아요",
        "sorry": "죄송해요",
        "hello": "안녕하세요",
        "hi": "안녕하세요",
        "anxiety": "불안",
        "stress": "스트레스",
        "depression": "우울",
        "therapy": "상담",
        "counseling": "상담",
        "mindfulness": "마음챙김",
        "grounding": "안정화 연습",
    }
    for english, korean in dictionary.items():
        text = re.sub(r"(?i)(?<![A-Za-z])" + re.escape(english) + r"(?![A-Za-z])", korean, text)
    # Do not expose mixed English sentences or hidden reasoning to the user.
    text = re.sub(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*", "", text)
    text = re.sub(r"[\u0370-\u03ff\u0400-\u04ff]+", "", text)
    text = re.sub(r"[\u3040-\u30ff\u4e00-\u9fff]+", "", text)
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r" *([,.;!?])", r"\1", text)
    text = re.sub(r"([.!?])(?:\s*[.!?])+", r"\1", text)
    text = re.sub(r"(?m)^\s*[-#*]+\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip(" ,;:/\n\t")
    if not re.search(r"[가-힣]", text):
        return "이야기를 충분히 이해하지 못했어요. 지금 가장 마음에 걸리는 부분을 조금만 더 들려주실 수 있을까요?"
    if len(text) > 650:
        cut=text[:650]
        boundaries=list(re.finditer(r"[.!?。]\s*",cut))
        text=cut[:boundaries[-1].end()].strip() if boundaries and boundaries[-1].end()>180 else cut.rsplit(" ",1)[0].strip()+"…"
    return text
