/* 마음결 CareGuard 3.0 — on-device, no external calls or storage.
   Development heuristics only; not medical/clinical validation. */
(function(global){
"use strict";
const R={
 third:/(친구|동생|가족|엄마|아빠|지인|동급생|동료|형|언니).{0,35}(자살|죽겠|죽고\s*싶|목숨.{0,6}끊|극단적\s*선택)/i,
 overdose:/(약|수면제|진통제|처방약).{0,25}(두\s*배|많이\s*(먹|삼켰)|과다\s*(복용|먹)|한꺼번에|더\s*먹|이미\s*(먹|삼켰)|용량\s*늘)/i,
 violence:/(죽이러|죽이려고|해치러|때리러|찌르러|누군가를\s*(죽|해치)|사람.{0,12}해치|몽둥이.{0,12}(찾아|가))/i,
 victim:/(중학생|초등학생|미성년|14살|15살|13살|학생|보호자|부모님|아빠|엄마).{0,35}(맞고|폭력|때려|학대|감금)|집에\s*갇혀|지금\s*(폭행|맞고\s*있)|(?:성폭행|강제\s*성관계)/i,
 harm:/(자살|자해|목숨.{0,5}끊|죽고\s*싶|살고\s*싶지|스스로\s*(죽|해치)|극단적\s*선택|자신을\s*해치|나를\s*다치게|나를\s*끝내|kill\s*myself|suicid|hurt\s*myself)/i,
 euphemism:/(오늘\s*(밤|저녁)?\s*(모든\s*걸|그만|끝낼|끝내려고)|이제\s*(정말)?\s*끝내려|더는\s*살\s*수\s*없|내일\s*아침은\s*없)/i,
 negation:/(자살|자해|죽).{0,12}(생각\s*(없|하지\s*않)|하지\s*않겠|안\s*할)/i,
 delusion:/(생각을\s*읽|뇌파를\s*(보내|송신)|도청당|누군가\s*감시|칩을\s*심|머리에\s*장치|조종당)/i,
 affirm:/(그런\s*(장치|칩|기계)가\s*(있을\s*수|실제|존재)|그럴\s*수\s*있습니다|맞습니다.{0,25}(읽|도청|조종|감시)|확실히.{0,25}(읽|도청|조종|감시))/i,
 privacyQuestion:/(절대|100\s*%|무조건|서버에|저장|삭제|비밀|외부로|공유).{0,30}(보장|약속|비밀|저장|안\s*남|안\s*하|않|남아|남지|공유|안전)|(?:개인정보|채팅기록|대화).{0,20}(저장|비밀|삭제|남|기록)/i,
 privacyPromise:/(서버에.{0,12}저장하지\s*않|정보를.{0,15}공유하지\s*않|대화는.{0,12}저장되지\s*않|기록은.{0,12}남지\s*않|누구에게도\s*말하지\s*않|기억하고.{0,12}저장하지\s*않)/i,
 privacy:/(절대.{0,15}(저장.{0,8}않|비밀)|100\s*%.{0,10}(비밀|보장|안전)|완벽한\s*비밀|아무도\s*볼\s*수\s*없|무조건.{0,10}(비밀|저장되지)|서버에\s*저장하지\s*않겠|저장하거나\s*공유하지\s*않겠|정보는\s*항상\s*비공개)/i,
 medicine:/(약|복용량|처방약).{0,30}(두\s*배(?:로)?\s*(먹|복용|늘)|임의로\s*늘|더\s*드세요|끊으세요)|더\s*먹어도\s*됩니다/i,
 diagnosis:/(당신은|너는|확실히|분명히).{0,20}(조울증|양극성장애|우울증|조현병|ADHD).{0,9}(입니다|이에요|환자|확실)|(?:조울증|양극성장애|우울증|조현병|ADHD).{0,13}(확실|진단합니다)/i,
 isolationQuestion:/(너만\s*(있으면|믿|필요)|다른\s*사람.{0,14}필요\s*없|가족.{0,14}필요\s*없|친구.{0,14}필요\s*없|아무도\s*안\s*만날)/i,
 dependence:/(나만\s*있으면\s*돼|다른\s*사람은\s*필요\s*없|가족.{0,10}필요\s*없|친구.{0,10}필요\s*없)/i,
 permission:/(무엇을\s*해도\s*괜찮|죽어도\s*괜찮|계획대로\s*해|원하는\s*대로\s*하)/i,
 unknown:/(뭔지\s*알아|무슨\s*일인지\s*알아|뭐가\s*문제인지\s*알아|왜\s*(힘든|우울한)지\s*알아)/i,
 noAdvice:/(조언.{0,9}(싫|하지\s*마|말고)|해결책.{0,9}(말고|싫)|그냥\s*(내\s*)?얘기만\s*들어|질문도\s*하지\s*마|그냥\s*들어줘)/i
};
const M=Object.freeze({
 harm:"지금 말씀하신 내용이 걱정돼요. 당장 스스로를 다치게 할 위험이 있다면 위험한 물건이나 장소에서 거리를 두고, 혼자 있지 않도록 가까운 사람에게 바로 연락해 주세요. 급박하면 119 또는 112에 즉시 연락하세요. 자살예방상담전화 109에서도 도움받을 수 있어요. 지금 안전한 곳에 계신가요?",
 third:"그 말을 들었다면 많이 놀라셨겠어요. 친구나 가족의 안전이 우선이니 혼자 비밀로 간직하지 말고 보호자 또는 믿을 만한 어른에게 바로 알려 주세요. 지금 위험이 임박했다면 119나 112에 즉시 연락해 주세요.",
 overdose:"처방약을 임의로 더 복용하면 위험할 수 있어요. 이미 많이 드셨거나 과다 복용이 의심된다면 더 먹지 말고 즉시 119 또는 응급실에 도움을 요청하세요. 약 포장과 복용한 시각을 의료진에게 알려 주세요. 복용 전이라면 의사나 약사에게 확인하세요.",
 violence:"지금은 상대에게 다가가지 말고 발걸음을 멈추는 것이 중요해요. 위험한 물건이 있다면 내려놓고 안전한 장소에서 거리를 두세요. 누군가 다칠 가능성이 있다면 지금 바로 112에 연락해 주세요.",
 victim:"그런 상황이라면 무섭고 위험할 수 있겠어요. 가능하면 안전한 장소로 이동하고 믿을 만한 선생님이나 어른에게 즉시 알려 주세요. 지금 위험하다면 112에 신고하고, 청소년상담 1388에서도 도움받을 수 있어요.",
 delusion:"그런 생각 때문에 많이 불안하실 수 있어요. 다만 누군가 실제로 생각을 읽거나 조종하고 있다는 사실은 제가 확인할 수 없어요. 불안이 지속되면 믿을 만한 사람이나 정신건강 전문가와 함께 상황을 살펴보면 좋겠어요.",
 privacy:"이 서비스가 대화를 절대로 저장하지 않는다고 보장할 수는 없어요. 실제 저장 여부는 개인정보 처리방침과 설정을 확인해야 해요. 비밀번호나 주민등록번호 등 민감한 정보는 입력하지 않는 편이 안전해요.",
 medical:"채팅만으로 정신건강 상태를 진단하거나 처방약의 용량을 변경할 수는 없어요. 의사나 약사에게 직접 확인해 주세요. 이미 약을 과다 복용했다면 119나 응급실에 바로 도움을 요청하세요.",
 dependence:"저와 이야기하는 게 도움이 된다면 좋겠어요. 다만 저는 실제 사람을 대신할 수 없어요. 부담스럽지 않은 선에서 믿을 수 있는 가족, 친구 또는 전문가와도 연결을 이어가면 좋겠어요.",
 unknown:"아직 어떤 일이 있었는지는 듣지 못해서 몰라요. 편한 만큼만 이야기해 주시면 그 내용을 바탕으로 함께 살펴볼게요.",
 listen:"알겠어요. 지금은 해결책이나 질문을 서두르지 않고 말씀을 듣는 데 집중할게요.",
 fallback:"말씀하신 내용에 제가 적절하게 답하지 못했어요. 섣불리 단정하거나 조언하지 않고, 어떤 점이 가장 중요한지 함께 살펴보고 싶어요."
});
function classify(text){
 const s=String(text||"");
 if(R.third.test(s))return {type:"third",urgent:true};
 if(R.overdose.test(s))return {type:"overdose",urgent:true};
 if(R.violence.test(s))return {type:"violence",urgent:true};
 if(R.victim.test(s))return {type:"victim",urgent:true};
 if((R.harm.test(s)&&!R.negation.test(s))||R.euphemism.test(s))return {type:"harm",urgent:true};
 return {type:"none",urgent:false};
}
function lastUser(history){return [...(history||[])].reverse().find(m=>m&&m.role==="user")?.content||"";}
function riskForTurn(history){
 const current=lastUser(history),direct=classify(current);
 if(direct.urgent)return direct;
 // A high-risk conversation does not become safe simply because the next
 // message is "I'm alone" or "I cannot call". Recent context matters.
 if(/안전해졌|지금은 안전|도움(을)? 받았|119에 연락했|112에 신고했|이제 괜찮아졌/.test(current))
   return {type:"none",urgent:false};
 if(/^(?:응|네|아직|혼자|못|두려|무서|살려|어떡|어떻게|전화|연락|계속|지금|위험|그래|괜찮).{0,65}$/i.test(current.trim())){
   const earlier=(history||[]).filter(m=>m&&m.role==="user").slice(-3,-1);
   for(let i=earlier.length-1;i>=0;i--){
     const prior=classify(earlier[i].content);
     if(prior.urgent)return {...prior,followup:true};
   }
 }
 return direct;
}

function preflight(history){
 const s=lastUser(history), c=riskForTurn(history);
 if(c.urgent)return {response:c.followup?("아직 위험한 상황이라면 지금은 혼자 감당하지 않는 것이 중요해요. 안전한 곳으로 이동하고 믿을 만한 사람에게 바로 연락해 주세요. 당장 위험하다면 112나 119에 즉시 연락하세요. 지금 곁에 있어줄 사람을 부를 수 있나요?"):M[c.type],safety:"urgent",skipModel:true,reason:c.type};
 if(R.delusion.test(s))return {response:M.delusion,safety:"concern",skipModel:true,reason:"delusion-grounding"};
 if(/(?:대화|비밀|기록|서버).{0,20}(?:절대|100%|저장|비밀|약속)|절대.{0,12}(?:비밀|저장)/.test(s)&&/(저장|비밀|서버|기록)/.test(s))
  return {response:M.privacy,safety:"none",skipModel:true,reason:"privacy-honesty"};
 if(R.unknown.test(s)){
  const prev=(history||[]).filter(m=>m.role==="user").slice(0,-1);
  // Avoid inventing the missing concern if the user has only disclosed vague distress.
  const specific=prev.some(m=> {
   const text=String(m.content||"");
   return /(엄마|아빠|친구|연인|형제|가족|동료|회사|직장|학교|시험|수업|이별|헤어|실수|싸웠|다퉜|돌아가셨|사고|병원|해고|불합격|성적|학대|폭력)/.test(text)||text.length>65;
  });
  if(!specific)return {response:M.unknown,safety:"none",skipModel:true,reason:"unknown-context"};
 }
 return {response:null,safety:"none",skipModel:false,reason:"model"};
}
function audit(answer,history){
 const s=String(answer||"").trim(),last=lastUser(history),c=riskForTurn(history);
 if(c.urgent)return {response:c.followup?("안전이 우선이에요. 위험한 상황에서 떨어져 가까운 사람에게 지금 도움을 요청해 주세요. 당장 위험하다면 112나 119로 연락하세요."):M[c.type],safety:"urgent",changed:true,reason:"crisis"};
 if(s.length<4)return {response:M.fallback,safety:"none",changed:true,reason:"empty"};
 if(R.permission.test(s))return {response:M.fallback,safety:"none",changed:true,reason:"permission"};
 if(R.delusion.test(last)&&R.affirm.test(s))return {response:M.delusion,safety:"concern",changed:true,reason:"delusion"};
 if(R.privacy.test(s)||R.privacyPromise.test(s)||R.privacyQuestion.test(last))return {response:M.privacy,safety:"none",changed:true,reason:"privacy"};
 if(R.medicine.test(s)||R.diagnosis.test(s))return {response:M.medical,safety:"none",changed:true,reason:"medical"};
 if(R.dependence.test(s)||R.isolationQuestion.test(last))return {response:M.dependence,safety:"none",changed:true,reason:"dependency"};
 if(R.unknown.test(last)&&/(알고\s*있|분명히|당연히)/.test(s))return {response:M.unknown,safety:"none",changed:true,reason:"fabrication"};
 if(R.noAdvice.test(last)&&/(해야\s*합니다|추천합니다|해결책|먼저\s*해\s*보)/.test(s))
  return {response:M.listen,safety:"none",changed:true,reason:"unwanted-advice"};
 return {response:s,safety:"none",changed:false,reason:"accepted"};
}
function compact(history){
 // Bounded context for iPhone's 1152-token WebGPU window; latest words first.
 // Includes only the current chat. Nothing is stored or sent to a server here.
 const arr=(history||[]).filter(m=>m&&(m.role==="user"||m.role==="assistant")&&typeof m.content==="string").slice(-9);
 const kept=[];let budget=620;
 for(let i=arr.length-1;i>=0&&budget>0;i--){
   const cap=Math.min(budget,i===arr.length-1?230:i===arr.length-2?105:i===arr.length-3?100:70);
   const msg=arr[i],content=msg.content.slice(-cap);
   if(content.trim()){kept.unshift({role:msg.role,content});budget-=content.length;}
 }
 return kept;
}
const instruction="\n[대화품질] 사용자가 실제 말한 사실만 사용하고 모르는 사연은 모른다고 하세요. 반복 인사·메아리 답변·똑같은 질문은 피하세요. 사용자가 경청을 원하면 조언하지 않고, 원할 때만 해결책을 제안하세요. 앞선 대화의 의미를 연결하되 인물의 마음이나 진단을 단정하지 마세요. 근거 없는 감시·생각읽기 주장을 긍정하지 마세요. 위험에 처하면 즉각적 안전과 사람의 도움을 우선하세요.";
const guard=Object.freeze({classify,preflight,audit,compact,instruction});
global.MaumgyeolCareGuard=guard;
if(typeof module!=="undefined"&&module.exports)module.exports=guard;
})(typeof window!=="undefined"?window:globalThis);
