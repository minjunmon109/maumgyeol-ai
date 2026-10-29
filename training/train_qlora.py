"""Train Maumgyeol Qwen3-4B-Instruct-2507 QLoRA on a CUDA GPU.
This script actually modifies/saves LoRA adapter weights when run, unlike prompt-only prototypes.
Running script without a GPU fails closed. Does not claim clinical or master's-level validation.

Suggested: Python 3.11/3.12, NVIDIA CUDA GPU >=16GB, torch GPU build.
Dependencies: requirements-gpu.txt
"""
import argparse, hashlib, json, math, os, random
from datetime import datetime, timezone
from pathlib import Path

BASE="Qwen/Qwen3-4B-Instruct-2507"
HERE=Path(__file__).resolve().parent

def hashfile(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model", default=BASE)
    parser.add_argument("--train", default=str(HERE/"data"/"train.jsonl"))
    parser.add_argument("--val", default=str(HERE/"data"/"val.jsonl"))
    parser.add_argument("--output", default=str(HERE/"outputs"/"maumgyeol-qwen3-lora"))
    parser.add_argument("--epochs",type=float,default=3)
    parser.add_argument("--learning-rate",type=float,default=1e-4)
    parser.add_argument("--max-length",type=int,default=1024)
    parser.add_argument("--max-steps",type=int,default=-1,help="Positive number for GPU smoke tests; -1 means full dataset epochs")
    parser.add_argument("--seed",type=int,default=37)
    opts=parser.parse_args()
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("학습을 시작하지 않았습니다: CUDA GPU가 필요합니다. Colab에서 GPU를 선택하세요.")
    from datasets import load_dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import SFTConfig, SFTTrainer
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    train, val=Path(opts.train),Path(opts.val)
    if not train.is_file() or not val.is_file():
        raise SystemExit("학습 자료가 없습니다. 먼저 python training/build_synthetic.py 실행")
    for path in (train,val):
        for line in path.read_text(encoding="utf-8").splitlines():
            obj=json.loads(line)
            if not obj.get("prompt") or not obj.get("completion"):
                raise ValueError("Malformed prompt/completion JSONL")
    cuda_name=torch.cuda.get_device_name(0)
    vram=torch.cuda.get_device_properties(0).total_memory/(1024**3)
    if vram<10:
        raise SystemExit("GPU memory insufficient for this preset; >=16 GB recommended, detected %.1f GiB" % vram)
    dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    print("Training NVIDIA GPU:",cuda_name,"VRAM:",round(vram,1),"GiB","compute:",str(dtype),flush=True)
    os.environ["TOKENIZERS_PARALLELISM"]="false"
    tokenizer=AutoTokenizer.from_pretrained(opts.model)
    if tokenizer.pad_token is None: tokenizer.pad_token=tokenizer.eos_token
    quant=BitsAndBytesConfig(load_in_4bit=True,
                            bnb_4bit_quant_type="nf4",
                            bnb_4bit_compute_dtype=dtype,
                            bnb_4bit_use_double_quant=True)
    model=AutoModelForCausalLM.from_pretrained(opts.model,
                                               quantization_config=quant,
                                               device_map={"":torch.cuda.current_device()},
                                               torch_dtype=dtype)
    model.config.use_cache=False
    model=prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora=LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,bias="none",
                    task_type="CAUSAL_LM",
                    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
    ds=load_dataset("json",data_files={"train":str(train),"validation":str(val)})
    output=Path(opts.output);output.mkdir(parents=True,exist_ok=True)
    cfg=SFTConfig(output_dir=str(output),
                  num_train_epochs=opts.epochs,max_steps=opts.max_steps,
                  per_device_train_batch_size=1, per_device_eval_batch_size=1,
                  gradient_accumulation_steps=8, learning_rate=opts.learning_rate,
                  lr_scheduler_type="cosine",warmup_ratio=.06,
                  max_grad_norm=.3,weight_decay=.01,
                  max_length=opts.max_length,
                  gradient_checkpointing=True,
                  gradient_checkpointing_kwargs={"use_reentrant":False},
                  bf16=(dtype==torch.bfloat16),fp16=(dtype==torch.float16),
                  eval_strategy="epoch" if opts.max_steps==-1 else "no",
                  save_strategy="epoch" if opts.max_steps==-1 else "no",
                  logging_steps=1,save_total_limit=2,
                  completion_only_loss=True,
                  eos_token="<|im_end|>",
                  packing=False,report_to="none",seed=opts.seed)
    trainer=SFTTrainer(model=model,args=cfg,train_dataset=ds["train"],
                       eval_dataset=ds["validation"],processing_class=tokenizer,
                       peft_config=lora)
    print("Data:",len(ds["train"]),"training,",len(ds["validation"]),"holdout. Starting CUDA fine-tuning",flush=True)
    output_result=trainer.train()
    trainer.save_model(str(output))
    tokenizer.save_pretrained(str(output))
    metrics=trainer.evaluate()
    manifest={
      "base_model":opts.model,
      "training_type":"CUDA 4-bit NF4 QLoRA",
      "device":cuda_name,"vram_gib":round(vram,2),
      "created_utc":datetime.now(timezone.utc).isoformat(),
      "training_data_sha256":hashfile(train),
      "validation_data_sha256":hashfile(val),
      "train_examples":len(ds["train"]),
      "validation_examples":len(ds["validation"]),
      "train_loss":float(output_result.training_loss),
      "validation_loss":float(metrics.get("eval_loss",-1)),
      "steps":int(output_result.global_step),
      "smoke_test_only":opts.max_steps>0,
      "weight_file_present":(output/"adapter_model.safetensors").is_file(),
      "expert_clinical_validation":False,
      "warning":"Unreviewed synthetic training set; never claim clinical competence or a master's degree"
    }
    (output/"training_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    if not manifest["weight_file_present"]:
        raise SystemExit("LoRA adapter_model.safetensors missing; training not verified")
    print("SAVED REAL TRAINED ADAPTER:",str(output.resolve()))
    print("Manifest:",json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
