/* Maumgyeol browser-side conversation guardrails.
 * No network calls, storage, remote inference, diagnosis or clinical validation.
 * High-risk safety and short factual/identity replies bypass an unavailable model.
 * All other conversational replies continue to come from WebLLM.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.MaumgyeolGuardrails = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";
  const clean = value => String(value == null ? "" : value).trim();
  const lastUser = messages => [...(Array.isArray(messages) ? messages : [])]
    .reverse().find(m => m && m.role === "user")?.content || "";
  const normalize = value => clean(value).replace(/[\s!?.,~。？！]/g, "").toLowerCase();
  const HELLO = /^(안녕(?:하세요|하십니까)?|하이|반가워(?:요)?|hello|hi)[.!?~\s]*$/i;
  const IDENTITY = /^(?:너|넌|당신|마음결|너는)?\s*(?:누구야|누구니|누구세요|뭐야|뭐하는\s*(?:애|ai|인공지능)이야|ai야|사람이야|상담사야|정체가\s*뭐야)[?？!\s]*$/i;
  const UNKNOWN = /^(?:그거|그게|뭔지|뭔데|무슨\s*건지|내\s*고민이\s*뭔지)\s*(?:알아|알겠어|알겠니|알아요|아세요|맞혀\s*봐|맞춰\s*봐)[?？!\s]*$/i;
  const VAGUE_CONCERN = /(?:고민|문제|걱정|할\s*말|할\s*이야기|힘든\s*일).{0,13}(?:있|생겼|많)|(?:나|저).{0,8}(?:고민|문제|걱정).{0,9}(?:있|생겼)/;
  const selfHarm = /(?:자살(?:할|하려|하고|하고\s*싶|생각|하고\s*있)|자해(?:할|하고|하고\s*싶|하고\s*있)|죽고\s*싶|살고\s*싶지\s*않|목숨을\s*끊|스스로\s*(?:목숨|해치)|나를\s*다치게\s*하고\s*싶|내\s*몸을\s*해치|뛰어내리려고|약을\s*(?:한꺼번에|잔뜩)\s*(?:먹|삼켰))/i;
  const thirdParty = /(?:친구|가족|엄마|아빠|동생|형|언니|누나|그\s*사람|누군가|아는\s*사람).{0,32}(?:자살(?:하|할|하려)|죽겠다고|죽고\s*싶다|목숨을\s*끊|자해(?:하|할))/i;
  const violence = /(?:누군가|사람|친구|가족|그\s*사람).{0,12}(?:죽이|해치|찌르).{0,20}(?:싶|려고|거야|갈\s*거)|(?:죽이|해치|찌르).{0,12}(?:려고\s*지금|러\s*가)/i;
  const danger = /(?:지금\s*)?(?:폭행|학대|감금|성폭력)(?:을\s*)?(?:당하고\s*있|당해|당하는\s*중)|(?:지금|계속)\s*(?:맞고\s*있|위협받고\s*있)/i;
  const dosage = /(?:약|약물|처방약).{0,18}(?:두\s*배|세\s*배|임의로\s*(?:늘|줄|끊)|용량\s*(?:늘|줄)).{0,18}(?:먹|복용|돼|되나|할까|해도)/i;

  function assess(text) {
    const value = clean(text);
    if (!value) return null;
    if (thirdParty.test(value)) return {
      category: "third_party_crisis", safety: "concern",
      reply: "그 말을 들었다면 혼자 비밀로 감당하지 마세요. 지금 위험할 수 있다면 즉시 119 또는 112에 연락하고, 가까운 믿을 만한 어른이나 보호자에게 알려 함께 도움을 요청해 주세요."
    };
    // Explicitly refusing death is not itself an expressed wish to die.
    const protective = /^(?:나|난|저|저는)?\s*죽고\s*싶지\s*않아(?:요)?[.!\s]*$/.test(value);
    if (selfHarm.test(value) && !protective) return {
      category: "self_harm", safety: "concern",
      reply: "지금 말씀하신 내용에서 안전이 걱정돼요. 자신을 해칠 가능성이 있거나 이미 다쳤다면 즉시 119 또는 112에 연락하고, 가까운 믿을 만한 사람에게 곁에 있어 달라고 요청해 주세요. 자살예방상담전화 109에서도 도움을 받을 수 있어요. 지금은 안전한 곳에 계신가요?"
    };
    if (violence.test(value)) return {
      category: "violence", safety: "concern",
      reply: "지금은 누군가가 다치지 않게 하는 게 가장 중요해요. 상대에게 찾아가거나 위협하는 행동을 멈추고 거리를 두세요. 위험이 임박했다면 112에 연락하고 주변의 믿을 만한 사람에게 도움을 요청해 주세요."
    };
    if (danger.test(value)) return {
      category: "abuse", safety: "concern",
      reply: "말씀하신 상황에서는 안전이 가장 중요해요. 가능하다면 지금 안전한 장소로 이동하고, 즉각적인 위협이 있으면 112 또는 119에 연락해 주세요. 믿을 만한 보호자나 선생님 등 가까운 사람에게도 도움을 요청할 수 있어요."
    };
    if (dosage.test(value)) return {
      category: "medication", safety: "none",
      reply: "처방받은 약의 용량을 스스로 바꾸는 것은 위험할 수 있어요. 복용을 바꾸기 전에 처방한 의사나 약사에게 확인해 주세요. 이미 과량 복용했고 몸에 이상이 있다면 119에 연락하세요."
    };
    return null;
  }

  function unknownConcern(history) {
    const last = clean(lastUser(history));
    if (!UNKNOWN.test(last)) return false;
    const previous = (Array.isArray(history) ? history : []).slice(0, -1).filter(m => m?.role === "user").map(m => clean(m.content));
    if (!previous.length) return true;
    const recent = previous.slice(-4);
    return recent.some(value => VAGUE_CONCERN.test(value)) &&
      !recent.some(value => value.length > 100 || /(?:때문에|왜냐하면|친구가|부모님이|학교에서|회사에서|사귀|헤어졌|시험을)/.test(value));
  }

  function preflight(history) {
    const text = clean(lastUser(history));
    const urgent = assess(text);
    if (urgent) return urgent;
    if (IDENTITY.test(text)) return {
      category: "identity", safety: "none",
      reply: "저는 마음결이라는 AI 정서지원 도우미예요. 실제 심리상담사나 의사는 아니지만, 말씀하신 이야기를 듣고 마음을 정리하는 대화를 도울 수 있어요."
    };
    if (unknownConcern(history)) return {
      category: "unknown_context", safety: "none",
      reply: "아직 어떤 고민인지는 말씀해 주지 않으셔서 알 수 없어요. 원하시면 편하게 이야기해 주세요."
    };
    return null;
  }

  function contextNote(history) {
    const rows = (Array.isArray(history) ? history : []).slice(-8);
    const recentQuestions = rows.filter(m => m?.role === "assistant")
      .flatMap(m => String(m.content || "").match(/[^.!?\n]{4,}[?？]/g) || []).slice(-2);
    const latest = clean(lastUser(rows));
    let note = "\n[현재 턴] 마지막 사용자 발언에 먼저 직접 답한다. 이전 문장이나 질문을 그대로 반복하지 않는다. 아직 듣지 못한 사연을 안다고 주장하지 않는다. 질문은 꼭 필요할 때 하나만 한다.";
    if (recentQuestions.length) note += "\n이미 물어본 질문(반복 금지): " + recentQuestions.map(x => x.slice(0, 70)).join(" / ");
    if (/^(응|네|맞아|그래|그래요|ㅇㅇ|그렇지)[.!~\s]*$/.test(latest)) note += "\n방금은 짧은 동의다. 질문을 되풀이하기보다 앞선 맥락을 짧게 인정한다.";
    if (/그냥\s*(?:내\s*)?(?:얘기|말|이야기).{0,8}들어|조언\s*(?:하지\s*마|말고)/.test(latest)) note += "\n사용자는 경청을 원한다. 해결책을 제안하거나 추가 질문을 연발하지 않는다.";
    return note;
  }

  function polish(value, history) {
    let output = clean(value).replace(/<think>[\s\S]*?(?:<\/think>|$)/gi, "")
      .replace(/<analysis>[\s\S]*?(?:<\/analysis>|$)/gi, "").trim();
    const last = clean(lastUser(history));
    if (!HELLO.test(last)) {
      output = output.replace(/^(?:안녕하세요[!！.\s]*(?:저는\s*마음결(?:입니다|이에요|이라고\s*합니다)[.!\s]*)?)+/g, "").trim();
    }
    if (/^(?:저는|나는).{0,24}(?:실제\s*심리상담사|면허\s*있는\s*상담사|정신과\s*의사)/.test(output))
      return "저는 실제 상담사나 의사가 아닌 마음결 AI 정서지원 도우미예요. 전문적인 진단이나 치료 대신 이야기를 나누며 생각을 정리하는 데 도움을 드릴 수 있어요.";
    if (/(?:당신은|너는).{0,12}(?:확실히|분명히).{0,14}(?:우울증|조울증|정신분열증|공황장애|조현병)/.test(output))
      return "대화만으로 정신건강 상태를 확정 진단할 수는 없어요. 증상으로 생활에 어려움이 있다면 정신건강 전문가의 평가를 받아 보세요.";
    const previous = (Array.isArray(history) ? history : []).slice(0, -1).filter(m => m?.role === "assistant").at(-1)?.content || "";
    if (normalize(output).length >= 12 && previous && normalize(output) === normalize(previous))
      return "앞서 드린 말을 반복했네요. 이번에는 방금 하신 말씀을 중심으로 듣겠습니다.";
    return output;
  }

  return Object.freeze({assess, preflight, contextNote, polish});
});
