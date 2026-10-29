"""GPU-hosted inference API for Maumgyeol's fine-tuned Qwen3-4B LoRA adapter.

This server DOES NOT train. Training first creates an adapter in
training/outputs/maumgyeol-qwen3-lora and a verified manifest.
Exposes OpenAI Chat Completions compatible POST /v1/chat/completions.
Run on an HTTPS-proxied CUDA GPU host, NOT the CPU-only Render web service.
"""
import argparse, hmac, os, time, uuid
from contextlib import asynccontextmanager
from threading import Lock
from pathlib import Path
import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from peft import PeftConfig, PeftModel
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

STATE={}
LOCK=Lock()
class Message(BaseModel):
    role:str
    content:str=Field(min_length=1,max_length=6000)
class CompletionRequest(BaseModel):
    model:str="maumgyeol-qwen3-lora"
    messages:list[Message]=Field(min_length=1,max_length=20)
    max_tokens:int=Field(default=512,ge=1,le=896)
    temperature:float=Field(default=.6,ge=0,le=1.5)
    stream:bool=False

def authorize(token):
    secret=os.environ.get("MODEL_API_KEY","")
    if not secret or len(secret)<24 or not token or not hmac.compare_digest(token,"Bearer "+secret):
        raise HTTPException(401,detail="Authentication required")

def load_model(adapter):
    if not torch.cuda.is_available(): raise RuntimeError("CUDA GPU is required")
    adapter=Path(adapter)
    if not (adapter/"adapter_config.json").is_file():
        raise FileNotFoundError("LoRA adapter not found. Train first using training/train_qlora.py")
    if not (adapter/"training_manifest.json").is_file():
        raise RuntimeError("Missing proof-of-training manifest")
    import json
    metadata=json.loads((adapter/"training_manifest.json").read_text(encoding="utf-8"))
    if not metadata.get("weight_file_present"):raise RuntimeError("Training weights not verified")
    conf=PeftConfig.from_pretrained(str(adapter))
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer=AutoTokenizer.from_pretrained(conf.base_model_name_or_path)
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",
                            bnb_4bit_compute_dtype=dtype,bnb_4bit_use_double_quant=True)
    base=AutoModelForCausalLM.from_pretrained(conf.base_model_name_or_path,
        quantization_config=quant,device_map={"":torch.cuda.current_device()},
        torch_dtype=dtype)
    model=PeftModel.from_pretrained(base,str(adapter))
    model.eval()
    STATE.update(model=model,tokenizer=tokenizer,metadata=metadata)

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)

@app.get("/health")
def health(authorization:str|None=Header(None)):
    authorize(authorization)
    return {"ready":"model" in STATE,"type":"qwen3-4b-lora","fine_tuned":bool(STATE.get("metadata"))}

@app.post("/v1/chat/completions")
def chat(req:CompletionRequest,authorization:str|None=Header(None)):
    authorize(authorization)
    if req.stream:raise HTTPException(400,"stream must be false")
    if not STATE:raise HTTPException(503,"GPU model not loaded")
    if req.messages[-1].role!="user" or any(m.role not in {"system","user","assistant"} for m in req.messages):
        raise HTTPException(400,"Invalid roles")
    tokenizer=STATE["tokenizer"]
    model=STATE["model"]
    with LOCK:
        try:
            batch=tokenizer.apply_chat_template(
                [m.model_dump() for m in req.messages],tokenize=True,
                add_generation_prompt=True,return_dict=True,return_tensors="pt")
            if batch["input_ids"].shape[1]>4096:raise HTTPException(413,"context too long")
            batch={k:v.to(model.device) for k,v in batch.items()}
            opts={"max_new_tokens":req.max_tokens,"do_sample":req.temperature>0,
                  "pad_token_id":tokenizer.eos_token_id}
            if req.temperature>0:opts.update(temperature=req.temperature,top_p=.92)
            with torch.inference_mode():
                output=model.generate(**batch,**opts)
            text=tokenizer.decode(
                output[0,batch["input_ids"].shape[1]:],skip_special_tokens=True).strip()
        except HTTPException:raise
        except Exception:raise HTTPException(503,"Model inference failed")
    return {"id":"chatcmpl-"+uuid.uuid4().hex[:12],"object":"chat.completion",
            "created":int(time.time()),"model":"maumgyeol-qwen3-lora",
            "choices":[{"index":0,"finish_reason":"stop",
                        "message":{"role":"assistant","content":text}}]}

if __name__=="__main__":
    import uvicorn
    parser=argparse.ArgumentParser()
    parser.add_argument("--adapter",default="training/outputs/maumgyeol-qwen3-lora")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8000)
    args=parser.parse_args()
    if len(os.getenv("MODEL_API_KEY",""))<24:
        raise SystemExit("Set a strong random MODEL_API_KEY on GPU and Render.")
    load_model(args.adapter)
    uvicorn.run(app,host=args.host,port=args.port,access_log=False)
