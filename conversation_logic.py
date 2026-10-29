"""Conversation modes and question-repetition guardrails for Maumgyeol.

Stateless: incoming conversation is never saved on the server. This logic improves
conversation quality but does not constitute clinical validation.
"""
import difflib
import re

MODES = {
    "listen": (
        "지금의 대화 방식은 '그냥 들어주기'입니다. 말의 내용을 구체적으로 되짚고 "
        "사용자가 말한 감정을 조심스럽게 반영하세요. 사용자가 조언을 직접 요청하지 "
        "않았다면 해결책이나 질문을 먼저 꺼내지 마세요. '계속 말씀해 주세요'처럼 "
        "대답을 재촉하지 않는 짧은 문장으로 마칠 수 있습니다."
    ),
    "reflect": (
        "지금의 대화 방식은 '마음 정리하기'입니다. 사건과 해석, 감정과 원하는 것을 "
        "구별하여 조심스럽게 반영하세요. 사용자의 상황을 임의로 추정하지 마세요. "
        "정말 필요한 경우에만 아직 묻지 않은 구체적인 질문 하나를 덧붙이세요."
    ),
    "steps": (
        "지금의 대화 방식은 '함께 방법 찾기'입니다. 감정을 먼저 인정한 뒤 사용자가 "
        "시도할 수 있는 현실적인 작은 행동 하나 또는 두 가지를 제시하세요. "
        "사용자가 스스로 선택할 수 있도록 하고 진단·치료처럼 표현하지 마세요."
    ),
}

ACKNOWLEDGMENT = re.compile(r"^\s*(?:응|네|맞아|맞아요|그래|그래요|그런\s*것\s*같아|그런\s*것\s*같아요|그렇지|그렇죠|네네|ㅇㅇ|응응|그치|예)\s*[.!,~…\s]*$", re.I)
ASKING_FOR_ADVICE = re.compile(r"어떻게\s*(?:해야|할까|하면)|조언|해결책|방법을\s*(?:알려|찾)|도와\s*줘", re.I)


def normalize_mode(value):
    return value if isinstance(value,str) and (value=="auto" or value in MODES) else ("auto" if value is None else "reflect")


def effective_mode(mode, last_user_text):
    if ASKING_FOR_ADVICE.search(last_user_text or ""):
        return "steps"
    if re.search(r"그냥\s*(?:내\s*)?(?:들어|얘기|말하고)|조언\s*(?:말고|하지)", last_user_text or ""):
        return "listen"
    selected=normalize_mode(mode)
    if selected!="auto":
        return selected
    # One integrated counseling mode. Listen first, explore thoughts and
    # emotions when helpful; give concrete options only when asked.
    spoken=(last_user_text or "").strip()
    if ACKNOWLEDGMENT.search(spoken) or re.fullmatch(r"(?:응|네)\s+그런\s*것\s*같아[.!~ ]*", spoken):
        return "listen"
    if re.search(r"그냥\s*(?:내\s*)?(?:들어|얘기|말하고)|조언\s*(?:말고|하지)|위로\s*(?:해|해줘)|털어놓", spoken):
        return "listen"
    return "reflect"


def conversation_instruction(messages, mode="auto"):
    selected = effective_mode(mode, messages[-1]["content"] if messages else "")
    rule = MODES[selected]
    recent_questions = []
    for message in messages[-8:]:
        if message.get("role") != "assistant":
            continue
        recent_questions.extend(re.findall(r"[^.!?。\n]{4,}[?？]", message.get("content", "")))
    prior = " / ".join(q.strip()[-110:] for q in recent_questions[-3:])
    note = ("최근 이미 물어본 질문: " + prior) if prior else "아직 최근 질문 없음."
    if normalize_mode(mode)=="auto":
        rule += (
            " 사용자가 감정만 털어놓을 때는 서둘러 문제를 해결하지 말고 경청으로 시작합니다."
            " 대화가 충분히 이어지고 원한다면 의미를 정리하거나 선택지를 함께 찾습니다."
            " 질문할 필요가 없으면 질문하지 않습니다."
        )
    acknowledgment = messages and ACKNOWLEDGMENT.search(messages[-1]["content"])
    return (
        "\n\n[이번 응답의 운영 지침]\n" + rule +
        "\n대화가 이어지면 이전 응답의 질문을 거의 같은 의미로 반복하지 말고, "
        "사용자가 새로 알려준 정보를 한 단계 더 이해하세요. "
        "감정을 단정하거나 묻지 않은 상대방의 동기를 만들어내지 마세요. "
        "보통 1~3문장으로 말하고 질문을 남발하지 마세요.\n" +
        note +
        ("\n사용자는 방금 간단히 동의하거나 확인했습니다. 같은 질문을 다시 묻지 말고 "
         "그 의미를 짧게 반영하고 잠시 머무르세요." if acknowledgment else "")
    )


def _question_parts(text):
    return re.findall(r"[^.!?。\n]{4,}[?？]", text or "")


def _normalized_question(text):
    return re.sub(r"[^가-힣0-9]", "", re.sub(
        r"혹시|요즘|그런|어떤|느껴지시나요|생각하시나요|싶으신가요|말씀해주실수있나요",
        "", text or ""
    ))


def _repeated_question(question, previous_questions):
    a = _normalized_question(question)
    if not a:
        return False
    for prev in previous_questions:
        b = _normalized_question(prev)
        if not b:
            continue
        similarity = difflib.SequenceMatcher(None, a, b).ratio()
        grams_a = {a[i:i+3] for i in range(max(0,len(a)-2))}
        grams_b = {b[i:i+3] for i in range(max(0,len(b)-2))}
        overlap = len(grams_a & grams_b)/max(1,min(len(grams_a),len(grams_b)))
        if similarity >= .52 or overlap >= .58:
            return True
    return False


def refine_reply(text, messages, mode="auto"):
    """Remove repetitive/leading questions without fabricating user details."""
    if not text:
        return text
    selected = effective_mode(mode, messages[-1]["content"] if messages else "")
    previous_questions = [
        q for m in messages[-8:] if m.get("role") == "assistant"
        for q in _question_parts(m.get("content", ""))
    ]
    acknowledged = bool(messages and ACKNOWLEDGMENT.search(messages[-1]["content"]))
    parts = re.findall(r"[^.!?。？\n]+[.!?。？]?|\n+", text)
    kept = []
    questions = 0
    for part in parts:
        if "?" in part or "？" in part:
            if selected == "listen" or acknowledged or questions >= 1 or _repeated_question(part, previous_questions):
                continue
            questions += 1
        kept.append(part)
    result = "".join(kept).strip()
    result = re.sub(r"\s{2,}", " ", result).strip()
    if not result or not re.search(r"[가-힣]", result):
        return "그렇군요. 지금 마음에 걸리는 이야기를 서둘러 정리하지 않고 함께 살펴보겠습니다."
    return result
