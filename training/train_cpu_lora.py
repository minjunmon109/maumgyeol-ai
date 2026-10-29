"""CPU-only supervised LoRA fine-tuning for the *same* base model as the web app.

Intentionally never uses bitsandbytes/CUDA or downloads private data.
Requires independently authorized, de-identified, reviewed JSONL datasets.
No professional evaluation or website deployment is implied by successful training.

CPU with >=24 GiB RAM recommended for Qwen2.5-1.5B-Instruct (much more for
long sequences). Runtime may be hours/days; choose a smaller --model only for
experiments, NOT for shipping an incompatible website adapter.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

BASE = "Qwen/Qwen2.5-1.5B-Instruct"
ROOT = Path(__file__).resolve().parent


def sha256(path):
    block = hashlib.sha256()
    with Path(path).open("rb") as fp:
        for part in iter(lambda: fp.read(1024 * 1024), b""):
            block.update(part)
    return block.hexdigest()


def read_examples(path):
    examples = []
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        d = json.loads(raw)
        if not isinstance(d.get("prompt"), str) or not isinstance(d.get("completion"), str):
            raise ValueError(f"{path}:{n}: prompt/completion strings required")
        if not d["prompt"].strip() or not d["completion"].strip():
            raise ValueError(f"{path}:{n}: empty example")
        if len(d["prompt"]) > 18000 or len(d["completion"]) > 2400:
            raise ValueError(f"{path}:{n}: unusually long example")
        examples.append({"prompt": d["prompt"], "completion": d["completion"]})
    if len(examples) < 2:
        raise ValueError(f"{path}: need >=2 examples")
    return examples


def parse(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--train", default=str(ROOT / "data" / "approved" / "train.jsonl"))
    p.add_argument("--val", default=str(ROOT / "data" / "approved" / "val.jsonl"))
    p.add_argument("--model", default=BASE)
    p.add_argument("--output", default=str(ROOT / "outputs" / "maumgyeol-qwen25-cpu-lora"))
    p.add_argument("--max-steps", type=int, default=100)
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
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
    if args.max_steps < 1 or args.max_length < 64:
        raise SystemExit("max-steps >=1 and max-length >=64 required")
    train, val = read_examples(args.train), read_examples(args.val)
    if Path(args.train).resolve() == Path(args.val).resolve():
        raise SystemExit("Training and validation must be separate files")
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
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
    from peft import LoraConfig, get_peft_model

    if torch.cuda.is_available():
        raise SystemExit("This is a CPU-only training command; use the GPU pipeline for CUDA")
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 2)))
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base_model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float32, low_cpu_mem_usage=True,
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
        output_dir=str(output), use_cpu=True, fp16=False, bf16=False,
        optim="adamw_torch", per_device_train_batch_size=1, gradient_accumulation_steps=4,
        per_device_eval_batch_size=1, learning_rate=args.learning_rate,
        max_steps=args.max_steps, save_strategy="no", eval_strategy="no",
        logging_steps=5, report_to="none", seed=args.seed, remove_unused_columns=False,
        dataloader_num_workers=0, gradient_checkpointing=False,
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=CPUData(train),
                      eval_dataset=CPUData(val), data_collator=collator)
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
        "training_device": "cpu", "method": "LoRA FP32",
        "train_examples": len(train), "validation_examples": len(val),
        "train_sha256": sha256(args.train), "val_sha256": sha256(args.val),
        "adapter_sha256": sha256(adapter), "steps": int(result.global_step),
        "train_loss": result.training_loss,
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
