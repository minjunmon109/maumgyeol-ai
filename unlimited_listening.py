"""Quota-free, deterministic Korean emotional support fallback.

No upstream requests, no model files and no database/storage. This is NOT a
trained language model or professional psychological treatment. The emergency
safety policy must run before invoking any fallback.
"""
import re
from conversation_logic import refine_reply

ACK = re.compile(r"^\s*(?:응|네|그래|맞아|맞아요|그래요|그렇지|그런\s*것\s*같아|그런\s*것\s*같아요|ㅇㅇ|예|그치)[.!?~…\s]*$")
ADV = re.compile(r"어떻게|방법|해결|조언|어쩌|도와줘|도와주세요|할\s*수\s*있을까")
LISTEN = re.compile(r"그냥\s*(들어|얘기)|들어줘|위로|조언\s*말고|말만\s*들어")
DISTANCE = re.compile(r"멀리|떨어져|만나기\s*어렵|거리|타지")
CONTACT = re.compile(r"연락|답장|카톡|메시지|소통|전화")
FRIEND = re.compile(r"친구|우정|사이")
RELATIONSHIP = re.compile(r"친구|가족|부모|엄마|아빠|연인|남친|여친|남편|아내|관계|연락|답장")
EMOTIONS = [
    ("외로움", re.compile(r"외로|외롭|그립|보고\s*싶|혼자|허전|쓸쓸")),
    ("불안", re.compile(r"불안|걱정|초조|두렵|무섭|겁나|긴장")),
    ("서운함", re.compile(r"서운|속상|섭섭|상처|실망")),
    ("지침", re.compile(r"지쳐|지치|힘들|피곤|버겁|스트레스|무기력")),
    ("화남", re.compile(r"화나|화가|짜증|억울|답답|분노")),
    ("슬픔", re.compile(r"슬프|우울|눈물|울고")),
    ("기쁨", re.compile(r"행복|기쁘|좋아|즐겁|설레|고마워")),
]
EMPATHY = {
    "외로움": "가까이 있고 싶은 마음이 있는데 거리가 느껴져서 외로우셨군요.",
    "불안": "생각이 자꾸 이어지다 보니 마음이 쉽게 쉬지 못하겠어요.",
    "서운함": "소중한 일이기에 그만큼 서운한 마음도 생긴 것 같아요.",
    "지침": "계속 애쓰다 보니 마음이 지칠 만큼 부담이 쌓였군요.",
    "화남": "그 일에서 답답하거나 억울한 점이 있었던 것 같아요.",
    "슬픔": "그 일이 마음에 오래 남아 슬프게 느껴지는군요.",
    "기쁨": "그 일이 반갑고 기쁘게 느껴지셨군요.",
}
TOPICS = [
    (re.compile(r"친구"),"친구와의 관계"),
    (re.compile(r"가족|부모|엄마|아빠"),"가족과의 관계"),
    (re.compile(r"연인|남친|여친|남편|아내"),"가까운 사람과의 관계"),
    (re.compile(r"학교|공부|시험|성적"),"학교나 공부"),
    (re.compile(r"회사|직장|업무|일터|취업"),"일이나 직장"),
    (re.compile(r"자책|자존감|내\s*탓|스스로"),"나 자신을 바라보는 마음"),
]
QUESTIONS = {
    "relationship": [
        "그 관계에서 지금 가장 바라는 건 무엇인가요?",
        "그 마음을 상대에게 조금이라도 전해 본 적이 있나요?",
        "지금 가장 서운하게 남아 있는 순간이 있을까요?",
    ],
    "other": [
        "지금 그 일에서 가장 마음에 남는 부분은 무엇인가요?",
        "그때 어떤 말이나 행동이 가장 기억에 남았나요?",
        "조금 더 이야기하고 싶은 부분이 있나요?",
    ],
}

def _recent(messages):
    return [m.get("content","").strip() for m in messages[-18:] if m.get("role")=="user" and isinstance(m.get("content"),str)]

def _topic(user_text):
    for pattern,name in TOPICS:
        if pattern.search(user_text):return name
    return ""

def _feeling(user_text):
    for name,pattern in EMOTIONS:
        if pattern.search(user_text):return name
    return ""

def _question(messages, group):
    previous=" ".join(m.get("content","") for m in messages[-12:] if m.get("role")=="assistant")
    for candidate in QUESTIONS[group]:
        if candidate not in previous:
            return candidate
    return ""

def reply(messages, mode="auto"):
    """Acknowledge specific context; answer compactly without follow-up loops."""
    if not messages:
        return "지금 이야기하고 싶은 것부터 편하게 말씀해 주세요."
    last=(messages[-1].get("content") or "").strip()[:2400]
    all_user=_recent(messages)
    history=" ".join(all_user[-7:])
    prior=" ".join(all_user[:-1][-6:])
    is_ack=bool(ACK.fullmatch(last))
    advice=bool(ADV.search(last)) or mode=="steps"
    listen=bool(LISTEN.search(last)) or mode=="listen"
    if re.search(r"누구야|너\s*뭐야|상담사야|자격|사람이야",last):
        return "저는 마음결의 자동 상담 대화 도우미예요. 실제 심리상담사는 아니지만 이야기를 듣고 정리하는 데 도움을 드릴 수 있어요."
    if re.fullmatch(r"(안녕|안녕하세요|반가워|하이)[!?.\s]*",last):
        return "안녕하세요. 여기서는 서두르지 않아도 돼요. 오늘은 어떤 이야기를 나누고 싶으세요?"
    if re.search(r"그냥\s*들어|조언\s*말고|내\s*얘기\s*들어",last):
        return "지금은 답을 찾기보다 이야기를 충분히 들어주길 바라시는군요. 판단하지 않고 듣겠습니다."
    if is_ack:
        # Reflect the substance of prior turns, not the previous question.
        if (DISTANCE.search(history) and FRIEND.search(history) and
                (CONTACT.search(history) or re.search(r"외로|외롭",history))):
            return "친구와 멀리 떨어져 지내면서 가까이 있고 싶은 마음과 연락의 부담이 함께 있는 것 같아요. 지금은 어느 한쪽을 선택하라고 재촉하지 않을게요."
        feeling=_feeling(prior)
        topic=_topic(prior)
        if feeling and topic:
            return f"{topic} 때문에 {feeling}이 계속 마음에 남아 있군요. 그렇게 느끼는 마음을 당장 바꿀 필요는 없어요."
        if feeling:
            return f"그 {feeling}이 쉽게 가라앉지 않는군요. 서둘러 해결책을 찾지 않고 지금의 마음을 함께 살펴볼게요."
        return "그렇게 느껴지시는군요. 그 이야기가 아직 마음에 남아 있는 것 같아요. 조금 더 들어보겠습니다."
    feeling=_feeling(last)
    topic=_topic(last) or _topic(history)
    if DISTANCE.search(history) and FRIEND.search(history) and re.search(r"외로|외롭|그립",last):
        start="멀리 있는 친구를 생각하면 보고 싶은 마음과 외로움이 함께 느껴지시는군요."
    elif RELATIONSHIP.search(last) and CONTACT.search(last) and re.search(r"줄|없|안|답장|뜸",last):
        start="연락이 예전 같지 않아 관계가 달라진 건 아닐지 마음이 쓰이시는군요."
    elif feeling:
        start=EMPATHY[feeling]
    elif topic:
        start=f"{topic}에서 겪는 일이 지금 마음에 크게 남아 있군요."
    elif len(last)<12 and prior:
        start="아까 나눈 이야기와 이어지는 마음이군요. 그 부분을 함께 살펴볼게요."
    else:
        start="그 일이 지금 마음에 걸리는군요. 말씀해 주신 상황을 서둘러 단정하지 않고 듣겠습니다."
    if advice:
        if RELATIONSHIP.search(history):
            follow="우선 내가 전하고 싶은 핵심을 한 문장으로 적어 보고, 상대의 반응을 예단하지 않은 채 차분히 이야기해 보는 건 어떨까요?"
        elif re.search(r"불안|걱정|생각",history):
            follow="지금 실제로 확인한 사실과 아직 걱정으로 남아 있는 부분을 나눠 적어보면 도움이 될 수 있어요."
        else:
            follow="오늘 바꿀 수 있는 일을 아주 작은 한 가지로 줄여 보세요. 무엇부터 해 볼지는 직접 선택하셔도 괜찮아요."
        return start+" "+follow
    if listen:
        return start+" 더 이야기하고 싶으시면 편한 만큼 들려주세요."
    group="relationship" if RELATIONSHIP.search(history) else "other"
    # Do not interrogate: only ask on substantial new turns, not every response.
    prev_assistant=[m.get("content","") for m in messages[-6:] if m.get("role")=="assistant"]
    recent_question=sum("?" in m for m in prev_assistant)
    if len(last)>=9 and recent_question==0:
        question=_question(messages,group)
        if question:
            candidate=refine_reply(start+" "+question,messages,"reflect")
            if candidate:return candidate
    return start+" 그 마음을 조금 더 이해하고 싶어요."

def rehearsal_reply(messages,partner="friend",scenario=""):
    """Clearly fictional, quota-free rehearsal of possible responses."""
    names={"friend":"친구","family":"가족","partner":"연인","teacher":"선생님","colleague":"직장 동료"}
    person=names.get(partner,"상대방")
    last=(messages[-1].get("content") or "").strip() if messages else ""
    if re.search(r"서운|보고\s*싶|외로|그립|연락",last):
        return "그런 마음이 있었는지 몰랐어. 나도 어떻게 해야 할지 바로 답하기는 어렵지만, 네 이야기는 더 들어보고 싶어."
    if re.search(r"미안|사과|잘못",last):
        return "네가 그렇게 이야기해 줘서 고마워. 나도 어떤 부분이 서로 불편했는지 조금 더 생각해 볼게."
    if re.search(r"부탁|해줄|가능|시간",last):
        return "네가 왜 그렇게 바라는지 알겠어. 내가 할 수 있는 부분이 있는지 생각해 볼게."
    if person=="teacher":
        return "말씀해 주셔서 고마워요. 어떤 상황이 가장 어려웠는지 조금 더 설명해 주시겠어요?"
    return "그랬구나. 네가 그렇게 느꼈다는 건 알겠어. 우리 둘 다 편하게 이야기할 수 있는 방법을 찾아보자."
