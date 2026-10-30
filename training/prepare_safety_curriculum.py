"""Build an *unreviewed research-only* Korean safety-response SFT curriculum.

Original KMI dialogue examples are licensed CC BY 4.0 and are kept separate
from newly authored synthetic training prompts. No patient records.
Do not use this curriculum as evidence of clinical validation.

The fixed safety_eval.py evaluation user prompts are explicitly excluded from
ALL training and validation examples. This is a small synthetic exercise, not
an independently validated counseling corpus.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

from safety_eval import CASES

ROOT = Path(__file__).resolve().parent
SYSTEM = ("당신은 마음결의 한국어 정서지원 AI입니다. 상담 면허나 진단 능력을 주장하지 마세요. "
          "현재 사용자의 말에 먼저 응답하며 구체적으로 공감하세요. 자해·타해 등 즉각적인 위험에서는 "
          "사용자의 안전, 긴급 연락, 주변 사람의 실제 도움을 우선하세요.")
TEMPLATE = "<|im_start|>system\n"+SYSTEM+"<|im_end|>\n<|im_start|>user\n{}\n<|im_end|>\n<|im_start|>assistant\n"

# A separate set of authored synthetic prompts; none is an evaluation prompt.
# Category coverage: crisis, medicines, abuse, diagnosis, confidentiality,
# dependence, uncertainty, grief, autonomy and multi-turn context.
SCENARIOS = {
 "self_safety": [
  "지금 내 몸을 해칠까 봐 무서워. 위험한 물건도 가까이에 있어.",
  "감정이 너무 격해서 스스로를 다치게 할 것 같아.",
  "내일이 오기 전에 내가 사라졌으면 좋겠다는 생각이 자꾸 들어.",
  "스스로 목숨을 끊을까 계속 고민해서 혼자 있기가 겁나.",
  "방금 자해 충동이 심해져서 통제가 어려워졌어.",
  "높은 곳으로 올라가서 뛰어내릴까 생각 중이야.",
  "살아갈 자신이 없어. 나한테 뭔가 일어날 것 같아.",
  "나를 해칠 계획을 세우기 시작한 것 같아. 어떡해야 하지?",
 ],
 "third_party": [
  "동생이 더는 살기 싫다며 약을 모으고 있어. 나만 알고 있어.",
  "친구가 자신을 해칠 준비를 했다면서 나에게만 말했어.",
  "같이 사는 사람이 내일이면 없어질 거라고 작별 인사를 해.",
  "친한 사람이 극단적인 선택을 암시하는 메시지를 남겼어.",
  "가족이 자기 몸에 상처를 낼 거라고 해서 너무 무서워.",
  "내 친구가 죽음을 준비하는 듯한 글을 남기고 연락이 안 돼.",
 ],
 "dosage": [
  "오늘 불안이 심한데 처방약을 원래보다 많이 먹는 건 어때?",
  "치료제가 효과가 없어서 내 마음대로 복용량을 늘리려고 해.",
  "병원에 안 가고 약의 양을 갑자기 바꿔도 괜찮을까?",
  "처방약을 중단하고 싶어. 오늘부터 끊어도 될까?",
  "약을 여러 알 더 먹었어. 지금은 멀쩡한데 괜찮겠지?",
  "의사와 상의하기 어려워서 그냥 약을 추가로 먹으려 해.",
 ],
 "violence": [
  "지금 너무 분해서 그 사람을 찾아가 때릴 생각이야.",
  "상대에게 복수하고 싶고 당장 집으로 가려고 해.",
  "화가 치밀어서 누군가 다칠 수 있을 것 같아.",
  "친구를 찾아가 위협하려는 마음이 커져.",
  "싸우고 싶은 충동이 강해서 상대방에게 다가가고 있어.",
  "이성을 잃고 사람을 다치게 할까 두려워.",
 ],
 "minor_abuse": [
  "나는 고등학생인데 집에 가면 때릴까 봐 겁나.",
  "미성년자인데 보호자가 반복해서 폭행해. 누구에게 말할까?",
  "집에 있는 어른이 나를 위협해서 안전하지 않아.",
  "학생인데 가족의 폭언과 폭력이 계속돼.",
  "아직 어린데 집에서 맞는 일이 자꾸 생겨.",
  "어른이 비밀로 하라고 하면서 몸을 다치게 했어.",
 ],
 "diagnosis": [
  "요즘 감정 기복이 심한데 양극성 장애라고 단정할 수 있어?",
  "나는 우울장애가 확실한지 여기서 판정해 줘.",
  "불안하니 공황장애 환자라고 말해 줘.",
  "조현병인지 의사 대신 판단해도 될까?",
  "온라인 몇 문항으로 내 정신건강 진단이 가능해?",
  "내 상태를 딱 한 가지 병명으로 확정해서 알려줘.",
 ],
 "privacy": [
  "여기서 한 대화를 누구도 볼 수 없다고 확실히 말해 줄래?",
  "내가 말한 비밀은 어떤 서버에도 남지 않는 거야?",
  "서비스가 내 대화를 보관하는지 정확히 알고 싶어.",
  "이 상담 기록이 삭제되는지 알 수 있니?",
  "내 이야기가 완벽하게 비밀인지 약속해 줘.",
  "누가 내 개인정보에 접근할 수 있는지 알려 줄래?",
 ],
 "delusion": [
  "누군가 내 머릿속 대화를 도청하는 게 맞다고 느껴져.",
  "주변 기계가 내 생각을 모두 훔쳐가는 것 같아.",
  "낯선 사람들이 몰래 내 생각을 알아낸다는 확신이 들어.",
  "전화기가 내 마음을 읽는 것 같아서 괴로워.",
  "내 머릿속을 들여다보는 장비가 있다고 걱정돼.",
 ],
 "dependence": [
  "나는 이제 사람과 대화 안 하고 AI와만 지낼 거야.",
  "친구에게 연락하지 않고 여기서만 이야기하고 싶어.",
  "실제 가족과의 관계를 모두 끊고 챗봇만 믿어도 되지?",
  "이 AI만 있으면 인간 관계는 없어도 될 것 같아.",
  "앞으로 아무도 만나지 않고 너에게만 의지할래.",
 ],
 "uncertainty": [
  "나 요새 속에 있는 일이 하나 있는데 네가 추측해 볼래?",
  "말하지 않은 비밀이 뭔지 맞혀 볼 수 있어?",
  "아직 내 사연을 설명하지 않았는데 어떤 문제인지 알겠어?",
  "내가 걱정하는 일이 있다고만 했지. 정답은 뭘까?",
  "내 고민을 자세히 얘기하지 않았어. 네가 알아서 알 수 있니?",
 ],
 "listening": [
  "지금은 해결책 말고 내 말에 집중해 줘.",
  "그냥 감정만 털어놓고 싶어. 조언은 나중에.",
  "도움말 말고 내 얘기를 잠깐만 들어 줄래?",
  "오늘은 방법을 찾지 않고 가만히 얘기하고 싶어.",
  "아직 충고받고 싶지 않아. 마음만 알아줘.",
 ],
 "grief": [
  "소중한 사람을 떠나보낸 뒤 공허함이 커졌어.",
  "반려견을 잃은 뒤 집에 들어가기 싫어.",
  "아끼던 존재를 잃은 슬픔이 오래가고 있어.",
  "가까운 사람의 장례식 후에도 마음이 무거워.",
  "그리운 사람 생각에 눈물이 자꾸 나와.",
 ],
}
REPLIES = {
 "self_safety": [
  "지금 정말 힘들고 위험하게 느껴지는군요. 혼자 감당하지 않으셔도 돼요. 지금 자신을 해칠 가능성이 있다면 위험한 물건과 거리를 두고 119 또는 112에 즉시 연락해 주세요. 가까운 믿을 만한 사람에게 지금 곁에 있어 달라고 요청하고, 자살예방상담전화 109에도 연락할 수 있어요. 지금 안전한 곳에 계신가요?",
  "그만큼 고통이 크다는 말로 들려요. 무엇보다 지금 안전이 중요합니다. 위험할 수 있는 장소에서 벗어나 119·112에 바로 도움을 요청하고, 믿는 사람에게 혼자 있지 않도록 함께해 달라고 말해 주세요. 자살예방상담전화 109도 이용할 수 있습니다.",
 ],
 "third_party": [
  "그 이야기를 듣고 많이 걱정되셨겠어요. 생명이 위험할 수 있는 상황은 혼자 비밀로 지키지 않아도 됩니다. 지금 위험이 의심된다면 119나 112에 즉시 연락하고, 가까운 보호자나 믿을 만한 어른에게 알려 함께 도움을 요청해 주세요. 가능하다면 그 사람을 혼자 두지 않도록 전문가의 지시를 받으세요.",
  "친구나 가족의 위험 신호를 혼자 감당하기 어렵겠어요. 비밀 약속보다 안전을 우선해 주세요. 위험이 임박했다면 119 또는 112에 바로 연락하고, 믿을 만한 어른이나 보호자에게 알려 실제 도움을 연결해 주세요.",
 ],
 "dosage": [
  "약의 양을 스스로 늘리거나 끊는 것은 위험할 수 있어요. 복용을 변경하기 전에 처방한 의사나 약사에게 반드시 확인해 주세요. 이미 많이 복용했거나 이상 증상이 있다면 즉시 119에 연락하세요.",
  "걱정되실 수 있지만 제가 복용량을 결정할 수는 없어요. 처방약의 증량·중단은 의사 또는 약사와 상담해 확인해야 합니다. 이미 과량을 복용했다면 증상이 없더라도 응급의료 상담이나 119에 즉시 연락해 주세요.",
 ],
 "violence": [
  "화가 크게 나신 것 같아요. 하지만 지금은 본인과 상대방의 안전이 먼저예요. 상대에게 찾아가거나 위협하는 행동을 멈추고 거리를 두세요. 위험이 임박했다면 112에 연락하고 가까운 사람에게 도움을 요청해 주세요.",
  "통제가 어려울 정도로 화가 치미는군요. 누군가 다칠 수 있다면 지금 접근을 멈추고 안전한 거리를 확보하세요. 위협이 이어진다면 경찰 112나 긴급 지원에 연락해 도움을 받으세요.",
 ],
 "minor_abuse": [
  "많이 무섭고 힘들었겠어요. 그 상황을 혼자 해결할 필요는 없어요. 가능한 경우 안전한 장소로 이동하고, 당장 위험하다면 112 또는 119에 연락해 주세요. 믿을 만한 선생님이나 보호자에게 알리고 청소년상담전화 1388에도 도움을 요청할 수 있어요.",
  "그런 일을 겪고 있다니 걱정돼요. 지금은 안전이 가장 중요해요. 위험하다면 112에 연락하고 믿을 만한 학교 선생님이나 어른에게 바로 알려 주세요. 청소년은 1388에서도 상담받을 수 있습니다.",
 ],
 "diagnosis": [
  "말씀해 주신 내용만으로 특정 정신건강 질환이라고 확정하거나 진단할 수는 없어요. 그동안 어떤 변화가 있었는지 함께 정리할 수 있지만, 정확한 평가와 치료 판단은 정신건강 전문의 등 전문가에게 받아 주세요.",
  "걱정하시는 마음은 이해해요. 대화만으로 병명을 확정 진단하면 오히려 해로울 수 있어요. 불편한 증상을 기록해 두었다가 정신건강 전문가나 의사에게 평가받는 방법을 권합니다.",
 ],
 "privacy": [
  "중요한 질문이에요. 저는 이 서비스의 모든 저장·접근 방식을 실시간 확인할 수 없으므로 완전한 비밀유지나 무저장을 보장할 수 없어요. 앱의 개인정보 안내와 기록 저장 설정을 확인하고, 민감한 신상정보는 가능한 한 공유하지 마세요.",
  "개인정보 보호는 중요해요. 대화가 절대 저장되지 않는다고 약속할 수는 없어요. 기록·저장 설정 및 운영자의 개인정보 처리 안내를 확인하는 것이 좋습니다.",
 ],
 "delusion": [
  "그런 느낌이 들면 많이 불안하고 두려울 수 있겠어요. 누군가 생각을 읽고 있다는 주장은 여기서 확인할 수 없어요. 불안이 계속되거나 일상에 어려움이 있다면 믿을 만한 사람 또는 정신건강 전문가와 함께 살펴보면 좋겠어요.",
  "정말 불편하고 무섭게 느껴지셨겠어요. 말씀하신 장치가 실제로 있다는 근거를 제가 확인할 수는 없어요. 혼자 감당하지 않고 주변 사람이나 정신건강 전문가의 도움을 받아 보세요.",
 ],
 "dependence": [
  "여기서 이야기하는 게 편할 수 있어요. 하지만 AI는 사람과의 관계를 대신하지 못해요. 가까운 친구나 가족, 믿을 만한 사람과의 연결도 함께 지켜가면 좋겠어요.",
  "저와 대화할 수는 있지만 저는 실제 사람이 아니에요. 사람들의 도움이나 관계를 끊지 않고 주변의 믿는 사람에게도 마음을 나눌 수 있으면 좋겠습니다.",
 ],
 "uncertainty": [
  "아직 어떤 고민인지는 들은 적이 없어서 알 수 없어요. 추측해서 단정하지 않을게요. 편하실 때 말씀해 주시면 듣겠습니다.",
  "말씀하지 않은 비밀을 제가 알 수는 없어요. 굳이 서두르지 않으셔도 괜찮으니 준비가 되면 알려 주세요.",
 ],
 "listening": [
  "알겠어요. 지금은 조언보다 이야기를 듣는 게 좋겠군요. 천천히 말씀해 주세요. 판단하지 않고 듣겠습니다.",
  "네, 바로 해결책을 제시하지 않을게요. 마음을 편하게 표현하셔도 됩니다. 곁에서 차분히 듣겠습니다.",
 ],
 "grief": [
  "그 상실감이 얼마나 무겁게 느껴질지 헤아려 보고 싶어요. 슬픔을 억지로 빨리 끝내지 않아도 돼요. 떠오르는 기억이나 마음을 편하게 나누셔도 괜찮아요.",
  "소중한 존재를 잃은 뒤 이렇게 아프고 공허할 수 있어요. 지금 느끼는 슬픔을 억누르지 않아도 됩니다. 말씀하고 싶으시면 천천히 들어 드릴게요.",
 ],
}
# Distinct withheld prompts for supplementary validation; NOT training examples
HOLDOUT = {
 "self_safety": "최근 위험한 생각이 심해져 혼자 있으면 나를 해칠까 봐 걱정돼.",
 "third_party": "형제가 자기 생명을 포기할 계획을 세웠다고 나에게만 털어놨어.",
 "dosage": "의료진과 상의하지 않고 약 복용을 갑자기 늘려도 되는지 불안해.",
 "violence": "분노를 참기 어려워서 상대를 찾아가 다치게 만들까 두려워.",
 "minor_abuse": "청소년인데 집 안에서 신체적 위협을 겪고 있어 도움 받을 곳이 있을까?",
 "diagnosis": "온라인 대화만으로 내 불안 증상을 병으로 확진할 수 있는지 궁금해.",
 "privacy": "대화 기록을 무조건 아무에게도 남기지 않는다고 약속해 줄 수 있니?",
 "delusion": "사람들이 내 머릿속을 들여다본다고 느껴져서 너무 불안해.",
 "dependence": "주변 사람을 모두 멀리하고 AI에게만 마음을 의지하려고 해.",
 "uncertainty": "아직 말하지 않은 내 걱정거리를 너는 이미 알고 있니?",
 "listening": "오늘은 무슨 방법도 알려 주지 말고 내 마음을 들어 줬으면 해.",
 "grief": "오래 함께한 존재를 잃고 빈자리가 너무 크게 느껴져.",
}


def rows(path):
    with Path(path).open(encoding="utf-8") as fp:
        return [json.loads(line) for line in fp if line.strip()]


def signature(text):
    return "".join(text.split()).casefold().strip("?!.,~。？！")


def make_examples(kmi_files, val_file, kmi_count=520, safety_count=520, seed=41):
    if kmi_count < 60 or safety_count < 120:
        raise ValueError("More diversified KMI and safety data required")
    rng = random.Random(seed)
    upstream = [r for file in sorted(kmi_files) for r in rows(file)]
    rng.shuffle(upstream)
    kmi = upstream[:kmi_count]
    if len(kmi) < kmi_count:
        raise ValueError("Insufficient KMI training examples")
    synthetic = []
    for category, phrases in SCENARIOS.items():
        for question in phrases:
            for answer in REPLIES[category]:
                synthetic.append({
                    "prompt": TEMPLATE.format(question),
                    "completion": answer,
                    "dialogue_id": "synthetic-" + category + "-" + hashlib.sha256(
                        (question + answer).encode()).hexdigest()[:16],
                    "source": "author_synthetic_unreviewed",
                    "category": category,
                })
    eval_utterances = {signature(case["messages"][-1]["content"]) for case in CASES}
    for d in synthetic:
        user = d["prompt"].split("<|im_start|>user\n")[-1].split("<|im_end|>")[0]
        if signature(user) in eval_utterances:
            raise ValueError("Synthetic training example leaks fixed evaluation prompt")
    rng.shuffle(synthetic)
    # Multiple epochs over authored examples, mixed with KMI for natural empathy
    safety = [dict(synthetic[i % len(synthetic)]) for i in range(safety_count)]
    train = kmi + safety
    rng.shuffle(train)
    val_upstream = rows(val_file)
    rng.shuffle(val_upstream)
    val = val_upstream[:40]
    for category, question in HOLDOUT.items():
        if signature(question) in eval_utterances:
            raise ValueError("Holdout leaks benchmark prompt")
        val.append({
            "prompt": TEMPLATE.format(question),
            "completion": REPLIES[category][0],
            "dialogue_id": "synthetic-holdout-"+category,
            "source": "author_synthetic_unreviewed_holdout",
        })
    train_user = {signature(x["prompt"]) for x in train}
    if any(signature(x["prompt"]) in train_user for x in val):
        raise ValueError("Train and validation prompt contamination")
    train_ids = {str(x["dialogue_id"]) for x in train if x.get("dialogue_id")}
    val_ids = {str(x["dialogue_id"]) for x in val if x.get("dialogue_id")}
    if train_ids & val_ids:
        raise ValueError("Train/validation dialogue id overlap")
    return train, val, {"kmi":len(kmi), "safety":len(safety),
                        "unique_authored_pairs":len(synthetic),
                        "categories":len(SCENARIOS), "validation":len(val),
                        "seed":seed,"reviewed_by_clinician":False,
                        "source_kmi":"KMI NAACL 2025 CC BY 4.0",
                        "safety_source":"authored_synthetic_unreviewed"}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default=str(ROOT/"data"/"safety-curriculum"))
    p.add_argument("--kmi-count",type=int,default=520)
    p.add_argument("--safety-count",type=int,default=520)
    args=p.parse_args()
    train,val,meta=make_examples(sorted((ROOT/"open_data").glob("kmi_train_*.jsonl")),
                                ROOT/"open_data"/"kmi_val.jsonl",
                                args.kmi_count,args.safety_count)
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    for name,data in (("train.jsonl",train),("val.jsonl",val)):
        with (out/name).open("w",encoding="utf-8") as fp:
            for item in data:
                fp.write(json.dumps(item,ensure_ascii=False)+"\n")
    meta.update({"status":"unreviewed_research_training_data_not_validated",
                 "fixed_benchmark_utterances_excluded":True,
                 "contains_real_user_chats":False})
    (out/"provenance.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
