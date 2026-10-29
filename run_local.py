"""Run with Ollama locally; no hosted inference key required."""
import os
import runpy
import secrets

if __name__ == "__main__":
    os.environ["MODEL_URL"] = "http://127.0.0.1:11434/v1/chat/completions"
    os.environ["MODEL_PROVIDER"] = "openai"
    os.environ.setdefault("MODEL_NAME", "qwen3:8b")
    os.environ["MODEL_API_KEY"] = ""
    os.environ["KEYLESS_BACKEND"] = "off"
    os.environ["HOST"] = "127.0.0.1"
    os.environ.setdefault("AUTH_SECRET", secrets.token_urlsafe(48))
    if not os.environ.get("ACCESS_CODE"):
        os.environ["ACCESS_CODE"] = secrets.token_urlsafe(12)
        print("이번 실행의 초대 코드:", os.environ["ACCESS_CODE"], flush=True)
    print("http://127.0.0.1:" + os.getenv("PORT", "10000"), flush=True)
    runpy.run_path(str(__import__("pathlib").Path(__file__).with_name("app.py")), run_name="__main__")
