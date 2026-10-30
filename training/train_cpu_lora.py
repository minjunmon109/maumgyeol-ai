"""CPU-only supervised LoRA fine-tuning for the *same* base model as the web app.

Intentionally never uses bitsandbytes/CUDA or downloads private data.
Requires independently authorized, de-identified, reviewed JSONL datasets.
No professional evaluation or website deployment is implied by successful training.

CPU with >=24 GiB RAM recommended for Qwen2.5-1.5B-Instruct (much more for
long sequences). Runtime may be hours/days; choose a smaller --model only for
experiments, NOT for shipping an incompatible website adapter.
"""
import argparse
import glob
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE = "Qwen/Qwen2.5-1.5B-Instruct"
ROOT = Path(__file__).resolve().parent


def sha256(path):
    block=hashlib.sha256()
    files=input_files(path)
    for file in files:
        if len(files)>1:
            block.update(file.name.encode("utf-8") + b"\0")
        with file.open("rb") as fp:
            for part in iter(lambda:fp.read(1024*1024),b""):
                block.update(part)
    return block.hexdigest()


def input_files(pattern):
    paths=sorted(glob.glob(str(pattern)))
    if not paths and Path(pattern).is_file(): paths=[str(pattern)]
    if not paths: raise FileNotFoundError("Missing approved dataset: "+str(pattern))
    return [Path(x) for x in paths]


def read_examples(path):
    examples=[]
    for file in input_files(path):
        with file.open(encoding="utf-8") as fp:
            for n,raw in enumerate(fp,1):
                if not raw.strip(): continue
                d=json.loads(raw)
                if not isinstance(d.get("prompt"),str) or not isinstance(d.get("completion"),str):
                    raise ValueError(f"{file}:{n}: expected prompt and completion text")
                if not d["prompt"].strip() or not d["completion"].strip():
                    raise ValueError(f"{file}:{n}: empty training data")
                if len(d["prompt"])>18000 or len(d["completion"])>2400:
                    raise ValueError(f"{file}:{n}: input too long")
                examples.append({"prompt":d["prompt"],"completion":d["completion"],
                                 "session":str(d.get("dialogue_id",""))})
    if len(examples)<2: raise ValueError(f"{path}: at least 2 examples needed")
    return examples

def parse(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train", default=str(ROOT / "open_data" / "kmi_train_*.jsonl"))
    p.add_argument("--val", default=str(ROOT / "open_data" / "kmi_val.jsonl"))
    p.add_argument("--model", default=BASE)
    p.add_argument("--output", default=str(ROOT / "outputs" / "maumgyeol-qwen25-cpu-lora"))
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--gradient-accumulation-steps", type=int, default=4,
                   help="CPU pilot speed tradeoff: 1 uses four times fewer microbatches than the default 4")
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--cpu-dtype", choices=["bfloat16","float32"], default="bfloat16")
    p.add_argument("--device", choices=["cpu","cuda"], default="cpu", help="Explicit GPU opt-in; CPU is the safe default")
    p.add_argument("--log-steps", type=int, default=5, help="Report training progress every N optimizer steps")
    p.add_argument("--checkpoint-every", type=int, default=0, help="Save recoverable checkpoints every N steps; 0 disables")
    p.add_argument("--max-training-examples",type=int,default=0,help="0 means all")
    p.add_argument("--max-eval-examples",type=int,default=0,help="0 means all")
    p.add_argument("--dry-run", action="store_true", help="Validate dataset without any Torch dependencies")
    return p.parse_args(argv)


def make_features(row, tokenizer, max_length):
    """Correct SFT loss masking: train on the *answer* only, not the prompt."""
    prompt_tokens = tokenizer.encode(row["prompt"], add_special_tokens=False)
    completion = row["completion"]
    if not completion.endswith("<|im_end|>"):
        completion += "<|im_end|>"
    answer_tokens = tokenizer.encode(completion, add_special_tokens=False)
    if not answer_tokens:
        raise ValueError("Tokenizer returned empty completion")
    # Preserve entire target whenever possible, clipping history first.
    if len(answer_tokens) >= max_length:
        answer_tokens = answer_tokens[:max_length - 1]
    budget = max_length - len(answer_tokens)
    prompt_tokens = prompt_tokens[-budget:]
    ids = prompt_tokens + answer_tokens
    labels = [-100] * len(prompt_tokens) + answer_tokens
    assert len(ids) == len(labels) <= max_length and any(x != -100 for x in labels)
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}


def main(argv=None):
    args = parse(argv)
    if args.log_steps < 1 or args.checkpoint_every < 0:
        raise SystemExit("log-steps >= 1 and checkpoint-every >= 0 required")
    if args.gradient_accumulation_steps < 1:
        raise SystemExit("gradient-accumulation-steps >= 1 required")
    if args.max_steps < 1 or args.max_length < 64:
        raise SystemExit("max-steps >=1 and max-length >=64 required")
    train, val = read_examples(args.train), read_examples(args.val)
    if args.max_training_examples>0: train=train[:args.max_training_examples]
    if args.max_eval_examples>0: val=val[:args.max_eval_examples]
    if {p.resolve() for p in input_files(args.train)} & {p.resolve() for p in input_files(args.val)}:
        raise SystemExit("Training and validation must be separate files")
    tr_ids={x["session"] for x in train if x.get("session")}
    vl_ids={x["session"] for x in val if x.get("session")}
    if tr_ids & vl_ids: raise SystemExit("Leaked conversation IDs across train/validation")
    sample_hashes = {hashlib.sha256((x["prompt"] + x["completion"]).encode()).hexdigest()
                     for x in train}
    if sample_hashes & {hashlib.sha256((x["prompt"] + x["completion"]).encode()).hexdigest()
                        for x in val}:
        raise SystemExit("Exact duplicate examples between training and validation")
    if args.dry_run:
        print(json.dumps({"status": "validated_not_trained", "train": len(train),
            "val": len(val), "model": args.model,
            "training_sha256": sha256(args.train), "val_sha256": sha256(args.val)},
            ensure_ascii=False, indent=2))
        return

    import torch
    from torch.utils.data import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainerCallback, TrainingArguments
    from peft import LoraConfig, get_peft_model

    if args.device == "cpu" and torch.cuda.is_available():
        raise SystemExit("This command defaults to CPU; pass --device cuda explicitly for GPU")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("Requested CUDA GPU is unavailable; refusing silent CPU fallback")
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 2)))
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.float16 if args.device == "cuda" else (torch.bfloat16 if args.cpu_dtype == "bfloat16" else torch.float32)
    print(json.dumps({"event":"training_device", "device":args.device, "gpu":torch.cuda.get_device_name(0) if args.device == "cuda" else None}), flush=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=dtype, low_cpu_mem_usage=True,
        trust_remote_code=False)
    base_model.config.use_cache = False
    base_model.gradient_checkpointing_enable()
    if hasattr(base_model, "enable_input_require_grads"):
        base_model.enable_input_require_grads()
    model = get_peft_model(base_model, LoraConfig(
        task_type="CAUSAL_LM", r=8, lora_alpha=16, lora_dropout=0.05,
        bias="none", target_modules=["q_proj", "v_proj", "o_proj"]))
    model.print_trainable_parameters()
    class CPUData(Dataset):
        def __init__(self, rows):
            self.rows = [make_features(x, tokenizer, args.max_length) for x in rows]
        def __len__(self):
            return len(self.rows)
        def __getitem__(self, i):
            return self.rows[i]
    def collator(rows):
        length = max(len(x["input_ids"]) for x in rows)
        ids = [x["input_ids"] + [tokenizer.pad_token_id] * (length - len(x["input_ids"]))
               for x in rows]
        masks = [x["attention_mask"] + [0] * (length - len(x["attention_mask"]))
                 for x in rows]
        labels = [x["labels"] + [-100] * (length - len(x["labels"]))
                  for x in rows]
        return {"input_ids": torch.tensor(ids), "attention_mask": torch.tensor(masks),
                "labels": torch.tensor(labels)}
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(output), use_cpu=(args.device == "cpu"), fp16=(args.device == "cuda"), bf16=False,
        optim="adamw_torch", per_device_train_batch_size=1, gradient_accumulation_steps=args.gradient_accumulation_steps,
        per_device_eval_batch_size=1, learning_rate=args.learning_rate,
        max_steps=args.max_steps, save_strategy=("steps" if args.checkpoint_every else "no"),
        save_steps=max(1, args.checkpoint_every), save_total_limit=2, eval_strategy="no",
        logging_steps=args.log_steps, report_to="none", seed=args.seed, remove_unused_columns=False,
        dataloader_num_workers=0, gradient_checkpointing=False,
    )
    class ProgressReporter(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if state.global_step:
                print(f"TRAIN_PROGRESS {state.global_step}/{state.max_steps} ({100 * state.global_step / state.max_steps:.1f}%)", flush=True)

    trainer = Trainer(model=model, args=training_args, train_dataset=CPUData(train),
                      eval_dataset=CPUData(val), data_collator=collator,
                      callbacks=[ProgressReporter()])
    result = trainer.train()
    metrics = trainer.evaluate()
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    adapter = output / "adapter_model.safetensors"
    if not adapter.is_file():
        raise SystemExit("CPU training did not produce adapter weights")
    manifest = {
        "status": "trained_not_safety_validated",
        "base_model": args.model, "target_website_base": BASE,
        "base_compatible_with_site": args.model == BASE,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_device": args.device, "method": "LoRA " + args.device.upper(),
        "base_weight_dtype": str(dtype),
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "checkpoint_every": args.checkpoint_every,
        "train_examples": len(train), "validation_examples": len(val),
        "train_sha256": sha256(args.train), "val_sha256": sha256(args.val),
        "adapter_sha256": sha256(adapter), "steps": int(result.global_step),
        "smoke_test_only": args.max_steps < 50,
        "training_data_provenance": "confirm source permission independently; data are not clinically validated",
        "train_loss": result.training_loss,
        "dataset_limited":bool(args.max_training_examples>0 or args.max_eval_examples>0),
        "experimental_smoke_training":bool(args.max_steps<20 or args.max_training_examples>0),
        "val_loss": metrics.get("eval_loss"),
        "data_license_independently_verified": False,
        "clinician_reviewed": False, "webllm_compatible_artifacts": False,
        "approved_for_release": False
    }
    (output / "training_manifest.json").write_text(json.dumps(
        manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
