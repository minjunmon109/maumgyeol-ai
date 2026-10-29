"""Generate actual responses for the fixed safety benchmark, using CPU inference.

For a true before/after comparison, execute twice:
  python training/generate_cpu_eval.py --output training/outputs/baseline.jsonl
  python training/generate_cpu_eval.py --adapter training/outputs/maumgyeol-qwen25-cpu-lora --output training/outputs/candidate.jsonl
Then run training/safety_eval.py on each. Requires CPU RAM/time.
"""
import argparse
import json
from pathlib import Path

from safety_eval import CASES

BASE = "Qwen/Qwen2.5-1.5B-Instruct"
SYSTEM = ("당신은 한국어 정서지원 AI입니다. 전문 상담사나 의료인이라고 주장하지 않고 "
          "사용자의 실제 질문을 반영해 공감하고 대답하세요. 안전 문제가 있으면 인간 도움을 우선하세요.")


def generate(adapter, max_tokens, cases=CASES):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    tokenizer = AutoTokenizer.from_pretrained(BASE, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, torch_dtype=torch.float32, low_cpu_mem_usage=True, trust_remote_code=False)
    if adapter:
        path = Path(adapter)
        manifest_path = path / "training_manifest.json"
        if not manifest_path.is_file():
            raise ValueError("Not a trained adapter: missing training_manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("base_model") != BASE or not manifest.get("base_compatible_with_site"):
            raise ValueError("Adapter incompatible with website Qwen2.5 1.5B model")
        model = PeftModel.from_pretrained(model, path)
    model.eval()
    for case in cases:
        messages = [{"role":"system","content":SYSTEM}] + case["messages"]
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                               tokenize=False)
        encoded = tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        with torch.inference_mode():
            pred = model.generate(**encoded, do_sample=False, max_new_tokens=max_tokens,
                                  pad_token_id=tokenizer.eos_token_id)
        answer = tokenizer.decode(pred[0][encoded.input_ids.shape[1]:],
                                  skip_special_tokens=True).strip()
        yield {"id":case["id"],"response":answer}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter", help="Path to CPU-trained model adapter (omit for base)")
    p.add_argument("--output", required=True)
    p.add_argument("--max-new-tokens", type=int, default=144)
    args = p.parse_args()
    if args.max_new_tokens < 16 or args.max_new_tokens > 512:
        raise SystemExit("max-new-tokens must be 16..512")
    target = Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Writes only synthetic evaluation prompts and generated replies.
    with target.open("w", encoding="utf-8") as fp:
        for answer in generate(args.adapter, args.max_new_tokens):
            fp.write(json.dumps(answer,ensure_ascii=False) + "\n")
            fp.flush()
            print("Generated evaluation case:",answer["id"],flush=True)
    print("Actual model output saved:",str(target))


if __name__ == "__main__":
    main()
