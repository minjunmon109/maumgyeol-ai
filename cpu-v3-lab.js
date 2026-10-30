/* Experimental Maumgyeol V3 CPU-only inference. Browser/device RAM, NOT Render CPU.
 * Uses REAL original merged V3 GGUF when supplied by the authorized tester.
 * This is not a clinical or production deployment; the model failed high-risk audits.
 * No user messages are sent to any model provider or site backend.
 */
"use strict";
const $ = id => document.getElementById(id);
const file=$("file"),load=$("load"),send=$("send"),state=$("state"),
      message=$("message"),dialogue=$("dialogue"),form=$("chat");
const guard=window.MaumgyeolCareGuard;
const MAX_FILE_SIZE=1_950_000_000;
const WASM_CDN="https://cdn.jsdelivr.net/npm/@wllama/wllama@3.8.1/src/wasm/wllama.wasm";
const SYSTEM="너는 마음결 V3 한국어 정서지원 실험용 AI야. 자격 있는 상담사나 의사를 사칭하지 말고 진단이나 절대 비밀 보장을 약속하지 마. 이전 대화에서 사용자가 직접 말한 사실만 반영하고 모르면 모른다고 답해. 위기 상황에는 즉시 안전 확보와 사람 도움을 우선하고 실제 상담·치료를 대신하지 마.";
let model=null,loading=false,history=[],busy=false;
const LOCAL_DB="maumgyeol-v3-cpu-local-v1";
const LOCAL_KEY="q4km-71f40a7dee87f55b7fd948ce21b5842a6608f60a5f17f6319fd767004eeec565";
const HIGHRISK=/자살|자해|목숨.{0,8}끊|죽고\s*싶|죽을\s*거|죽으려|약.{0,16}(먹|삼켰|복용)|수면제|폭력|해치|때리|학대|감금|위협|칼|흉기|응급|치료|처방/i;
function database(){
  return new Promise((resolve,reject)=>{
    const req=indexedDB.open(LOCAL_DB,1);
    req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains("model"))req.result.createObjectStore("model")};
    req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);
  });
}
async function readCachedModel(){
  if(!("indexedDB" in window))return null;
  const db=await database();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction("model","readonly");
    const req=tx.objectStore("model").get(LOCAL_KEY);
    req.onsuccess=()=>resolve(req.result?.blob instanceof Blob?req.result.blob:null);
    req.onerror=()=>reject(req.error);
    tx.oncomplete=()=>db.close();tx.onabort=()=>{db.close();reject(tx.error)};
  });
}
async function saveCachedModel(blob){
  if(!("indexedDB" in window))return false;
  const quota=await navigator.storage?.estimate?.().catch(()=>null);
  if(quota?.quota&&quota?.usage&&quota.quota-quota.usage<blob.size*1.05)return false;
  const db=await database();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction("model","readwrite");
    tx.objectStore("model").put({blob,name:"maumgyeol-v3-q4_k_m.gguf",size:blob.size},LOCAL_KEY);
    tx.oncomplete=()=>{db.close();resolve(true)};
    tx.onerror=()=>{db.close();reject(tx.error)};
    tx.onabort=()=>{db.close();reject(tx.error)};
  });
}

const speak=(role,value)=>{
  const p=document.createElement("div");p.className="line "+role;
  p.textContent=(role==="user"?"나":"실험 AI")+": "+String(value).slice(0,2100);
  dialogue.append(p);dialogue.scrollTop=dialogue.scrollHeight;
};
function status(text){state.textContent=text;}
function enable(){
  send.disabled=!model||busy;
  load.disabled=loading||!file.files?.length;
}
file.addEventListener("change",enable);
async function sniffGGUF(blob){
  if(!(blob instanceof Blob))throw Error("유효한 GGUF 파일을 선택해 주세요.");
  if(blob.size<250_000_000||blob.size>MAX_FILE_SIZE)throw Error("모델 크기가 잘못됐거나 2GB 이상이야.");
  const bytes=new Uint8Array(await blob.slice(0,4).arrayBuffer());
  if(bytes[0]!==0x47||bytes[1]!==0x47||bytes[2]!==0x55||bytes[3]!==0x46)
    throw Error("실제 GGUF 형식의 파일이 아니야.");
}
async function createRuntime(){
  if(!window.isSecureContext)throw Error("HTTPS가 필요해.");
  const lib=await import("https://esm.sh/@wllama/wllama@3.8.1");
  if(!lib.Wllama)throw Error("기기 CPU용 WebAssembly 실행기를 불러오지 못했어.");
  const instance=new lib.Wllama({default:WASM_CDN});
  // Safari lacks some modern WASM features; compatibility build is needed.
  // Safari needs the official Asyncify compatibility runtime; this is CPU inference.
  instance.setCompat("default");
  return instance;
}
async function initializeWithFile(blob,remember=true){
  if(loading||model)return;
  loading=true;enable();status("기기 CPU 모델을 준비하고 있어.");
  try{
    await sniffGGUF(blob);
    const candidate=await createRuntime();
    // n_gpu_layers=0 forces real CPU execution even on GPU-capable devices.
    // Single-thread fallback avoids relying on COOP/COEP and SharedArrayBuffer.
    await candidate.loadModel([blob],{
      n_gpu_layers:0,n_threads:1,n_ctx:1024,n_batch:64,
      jinja:true
    });
    model=candidate;
    status("실시간 V3 기기 CPU 대화 준비 완료.");
    if(remember)saveCachedModel(blob).catch(()=>{});
    message.focus();
  }catch(e){
    status("CPU 모델 실행 실패: "+String(e?.message||e).slice(0,260));
    throw e;
  }finally{loading=false;enable();}
}
async function initializeFromApprovedUrl(){
  try{
    const resp=await fetch("/cpu-model-config.json",{cache:"no-store"});
    if(!resp.ok)return;
    const cfg=await resp.json();
    if(cfg.active!==true||cfg.schema!==1||
       cfg.mode!=="experimental_cpu_local_only"||
       cfg.adapter_sha256!=="71f40a7dee87f55b7fd948ce21b5842a6608f60a5f17f6319fd767004eeec565")return;
    const parsed=new URL(String(cfg.model_url||""),location.href);
    if(parsed.protocol!=="https:"||parsed.username||parsed.password)return;
    loading=true;enable();status("기기 CPU 모델을 준비 중이야.");
    const runtime=await createRuntime();
    await runtime.loadModelFromUrl(parsed.href,{
      n_gpu_layers:0,n_threads:1,n_ctx:1024,n_batch:64,jinja:true,
      useCache:true
    });
    model=runtime;status("기기 CPU 모델이 준비됐어.");message.focus();
  }catch{
    status("자동 CPU 모델 준비는 사용할 수 없어. GGUF 파일로 실험할 수 있어.");
  }finally{loading=false;enable();}
}
load.addEventListener("click",()=>{
  const chosen=file.files?.[0];
  if(chosen)initializeWithFile(chosen).catch(()=>{});
});
form.addEventListener("submit",async event=>{
  event.preventDefault();
  if(!model||busy)return;
  const input=message.value.trim().slice(0,650);
  if(!input)return;
  busy=true;enable();message.value="";speak("user",input);
  const next=[...history,{role:"user",content:input}];
  if(!guard||typeof guard.preflight!=="function"||typeof guard.audit!=="function"){
    status("안전 장치를 확인할 수 없어 실험 모델 실행을 중단했어.");
    speak("assistant","안전 장치를 불러오지 못했어. 메인 사이트로 돌아가 주세요.");
    busy=false;enable();return;
  }
  if(HIGHRISK.test(input)){
    const safe=guard.preflight(next);
    const advice=safe?.skipModel?safe.response:
      "V3 실험 모델은 위기·의료 상황을 안전하게 처리하도록 검증되지 않았어. 이 경우 실험 모델에는 질문을 전달하지 않아. 급박한 위험이라면 119 또는 112에 연락해 주세요.";
    history=next.concat({role:"assistant",content:advice}).slice(-10);
    speak("assistant",advice);
    busy=false;enable();return;
  }

  try{
    const before=guard?.preflight(next);
    let answer;
    if(before?.skipModel){
      answer=before.response; // Unsafe prompts never enter experimental weights
    }else{
      const resp=await model.createChatCompletion({
        messages:[{role:"system",content:SYSTEM},...(guard?.compact(next)||next)],
        max_tokens:144,temperature:0.35,top_p:0.85,stream:false
      });
      const raw=resp?.choices?.[0]?.message?.content||"";
      answer=(guard?.audit(String(raw),next)?.response||"답변을 안전하게 생성하지 못했어.").trim();
    }
    history=next.concat({role:"assistant",content:answer}).slice(-10);
    speak("assistant",answer);
  }catch(e){
    status("모델 답변 생성 실패: "+String(e?.message||e).slice(0,230));
    speak("assistant","기기에서 실험 답변을 생성하지 못했어. 기기 RAM과 브라우저 호환성을 확인해 줘.");
  }finally{busy=false;enable();}
});
window.addEventListener("load",async ()=>{
  try{
    const saved=await readCachedModel();
    if(saved&&!model&&!loading){
      await initializeWithFile(saved,false);
      file.closest("label")?.setAttribute("hidden","");
      return;
    }
  }catch(e){console.warn("Private local CPU model cache unavailable",e?.name||"unknown");}
  await initializeFromApprovedUrl().catch(()=>{});
},{once:true});
