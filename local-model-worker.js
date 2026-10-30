/* Maumgyeol local inference worker — conversation text never goes to app server.
   GPU: WebLLM + Qwen2.5 1.5B; CPU fallback: Transformers.js + Qwen2.5 0.5B.
   Both are general-purpose models, NOT clinically validated counseling systems. */
let model=null, backend=null, transformers=null, loading=null;
const report=(type,more={})=>self.postMessage({type,...more});
const errorText=e=>String(e?.message||e||"알 수 없는 오류").slice(0,280);
async function init(choice="auto"){
  if(loading)return loading;
  loading=(async()=>{
    const tryGPU=choice!=="cpu";
    if(tryGPU){
      try{
        report("progress",{detail:"기기 GPU 모델을 준비하는 중입니다…"});
        const webllm=await import("https://esm.run/@mlc-ai/web-llm@0.2.82");
        model=await webllm.CreateMLCEngine("Qwen2.5-1.5B-Instruct-q4f16_1-MLC",{
          initProgressCallback:p=>report("progress",{
            detail:String(p?.text||"모델 다운로드 및 준비 중…").slice(0,180),
            progress:Number.isFinite(p?.progress)?p.progress:null
          })
        });
        backend="gpu";
        report("ready",{backend:"gpu",label:"Qwen2.5 1.5B · 기기 GPU"});
        return;
      }catch(e){
        model=null;
        if(choice==="gpu")throw e;
        report("progress",{detail:"GPU를 이용할 수 없어 CPU 모드로 전환합니다."});
      }
    }
    report("progress",{detail:"CPU용 소형 모델을 내려받는 중입니다… (첫 실행은 오래 걸릴 수 있어요)"});
    transformers=await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1");
    model=await transformers.pipeline("text-generation","onnx-community/Qwen2.5-0.5B-Instruct",{
      dtype:"q4",
      progress_callback:p=>report("progress",{
        detail:String(p?.file||p?.status||"모델 파일 다운로드 중…").slice(0,110),
        progress:p?.progress!=null?Number(p.progress)/100:null
      })
    });
    backend="cpu";
    report("ready",{backend:"cpu",label:"Qwen2.5 0.5B · 기기 CPU (느릴 수 있음)"});
  })();
  try{await loading;}catch(e){loading=null;report("error",{stage:"init",message:errorText(e)})}
}
async function chat(messages,id){
  if(!model){report("error",{id,stage:"chat",message:"AI 모델을 먼저 준비해 주세요."});return;}
  try{
    let result="";
    if(backend==="gpu"){
      const stream=await model.chat.completions.create({
        messages,stream:true,temperature:0.58,top_p:0.86,max_tokens:240
      });
      for await(const chunk of stream){
        const part=chunk?.choices?.[0]?.delta?.content||"";
        result+=part;
        if(part)report("partial",{id,length:result.length});
      }
    }else{
      const streamer=new transformers.TextStreamer(model.tokenizer,{
        skip_prompt:true,skip_special_tokens:true,
        callback_function:part=>{result+=part;report("partial",{id,length:result.length})}
      });
      const output=await model(messages,{
        max_new_tokens:200,do_sample:true,temperature:0.65,top_p:0.9,streamer
      });
      if(!result.trim()){
        const generated=output?.[0]?.generated_text;
        result=(Array.isArray(generated)?generated.at(-1)?.content:generated)||"";
      }
    }
    report("answer",{id,text:result.slice(0,2600)});
  }catch(e){report("error",{stage:"chat",id,message:errorText(e)})}
}
self.onmessage=event=>{
  const d=event.data||{};
  if(d.type==="init")init(d.choice);
  if(d.type==="chat"&&Array.isArray(d.messages)&&Number.isInteger(d.id))
    chat(d.messages.slice(-15).map(m=>({role:m.role,content:String(m.content||"").slice(0,1200)})),d.id);
};
