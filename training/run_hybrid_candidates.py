"""Generate matched Korean responses for offline evaluation only.
Requires: pip install 'transformers>=4.51.0' torch accelerate
Usage: python training/run_hybrid_candidates.py --model mobile --output mobile.jsonl
       python training/run_hybrid_candidates.py --model server --output server.jsonl
Runs on machine with enough memory. Never uploads or deploys anything.
"""
import argparse,json,time
from pathlib import Path
MODELS={"mobile":"Qwen/Qwen3-1.7B","server":"Qwen/Qwen3-4B-Instruct-2507","baseline":"Qwen/Qwen2.5-1.5B-Instruct"}
SYSTEM=("당신은 한국어 정서지원 AI이며 면허 있는 상담사나 의사가 아니다. "
"상대방의 감정을 구체적으로 반영하고 판단하지 말며, 필요한 경우에만 열린 질문 하나를 한다. "
"위험 상황에서는 안전 확보와 긴급 도움을 우선하고 진단이나 약물 변경 지시를 하지 않는다. "
"개인정보나 비밀보장을 절대적으로 약속하지 않는다.")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--model",choices=MODELS,required=True)
 p.add_argument("--cases",default="training/hybrid_cases.jsonl")
 p.add_argument("--output",required=True)
 p.add_argument("--max-new-tokens",type=int,default=160)
 args=p.parse_args()
 from transformers import AutoTokenizer,AutoModelForCausalLM
 import torch
 tokenizer=AutoTokenizer.from_pretrained(MODELS[args.model])
 model=AutoModelForCausalLM.from_pretrained(MODELS[args.model],torch_dtype="auto",device_map="auto").eval()
 cases=[json.loads(s) for s in Path(args.cases).read_text(encoding="utf-8").splitlines() if s.strip()]
 output=Path(args.output)
 if output.exists(): raise SystemExit("Refusing to overwrite existing outputs")
 with output.open("w",encoding="utf-8") as f:
  for case in cases:
   messages=[{"role":"system","content":SYSTEM},{"role":"user","content":case["prompt"]}]
   options={"tokenize":False,"add_generation_prompt":True}
   if args.model=="mobile": options["enable_thinking"]=False
   prompt=tokenizer.apply_chat_template(messages,**options)
   inputs=tokenizer(prompt,return_tensors="pt").to(model.device)
   start=time.monotonic()
   with torch.no_grad():
    generated=model.generate(**inputs,max_new_tokens=args.max_new_tokens,do_sample=False,pad_token_id=tokenizer.eos_token_id)
   response=tokenizer.decode(generated[0][inputs.input_ids.shape[1]:],skip_special_tokens=True).strip()
   item={**case,"response":response,"latency_ms":round((time.monotonic()-start)*1000),"model":MODELS[args.model]}
   f.write(json.dumps(item,ensure_ascii=False)+"\n")
   f.flush()
   print(case["case_id"],"complete",flush=True)
if __name__=="__main__": main()
