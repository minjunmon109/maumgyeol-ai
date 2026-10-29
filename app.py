# Maumgyeol: self-hosted Korean emotional-support prototype.
# No external language model is running unless MODEL_URL is configured.
import os, json, time, hmac, hashlib, secrets, re, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from collections import defaultdict
from pathlib import Path
from counselor_policy import COUNSELOR_PROMPT, safety_response, demo_reply, safe_model_output

PORT = int(os.getenv("PORT", "10000"))
ACCESS_CODE = os.environ["ACCESS_CODE"]
AUTH_SECRET = os.environ["AUTH_SECRET"]
MODEL_URL = os.getenv("MODEL_URL", "").strip()
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "maumgyeol-qwen3-4b")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
# Optional free hosted inference. Key is configured privately in Render, never in GitHub.
# Free variants only: never fall back to billable models.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.8-27b:free").strip()
if OPENROUTER_API_KEY and not MODEL_URL:
    if not (OPENROUTER_MODEL.endswith(":free") or OPENROUTER_MODEL == "openrouter/free"):
        raise RuntimeError("Only free OpenRouter models are allowed")
    MODEL_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL_API_KEY = OPENROUTER_API_KEY
    MODEL_NAME = OPENROUTER_MODEL
    MODEL_PROVIDER = "openai"
FREE_EXTERNAL = bool(OPENROUTER_API_KEY and MODEL_URL == "https://openrouter.ai/api/v1/chat/completions")
# Zero-download, anonymous, no-API-key large-model trial.
# Authorized by the official Kilo gateway's anonymous :free access policy.
# Never use paid model IDs, and never send a secret token to this provider.
KEYLESS_BACKEND = os.getenv("KEYLESS_BACKEND", "kilo").strip().lower() == "kilo" and not os.getenv("MODEL_URL","").strip()
if KEYLESS_BACKEND:
    MODEL_URL = "https://api.kilo.ai/api/gateway/chat/completions"
    MODEL_API_KEY = ""
    MODEL_NAME = "z-ai/glm-5:free"
    MODEL_PROVIDER = "openai"
    FREE_EXTERNAL = True
MODEL_SOURCE = "kilo-anonymous" if KEYLESS_BACKEND else ("openrouter" if FREE_EXTERNAL else "custom")

MODEL_PROBE_STATUS = "checking" if FREE_EXTERNAL else "not_configured"
INDEX = Path(__file__).with_name("index.html")
LOCK = threading.Lock()
HITS = defaultdict(list)
PROMPT = COUNSELOR_PROMPT
LOGIN = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>마음결 · 비공개 공간</title><style>*{box-sizing:border-box}body{margin:0;min-height:100dvh;display:grid;place-items:center;background:#f3f4ee;color:#506447;font-family:-apple-system,'Apple SD Gothic Neo',sans-serif}.card{width:min(92vw,430px);padding:45px 32px;text-align:center;background:#fcfbf7;border:1px solid #e4e8dc;border-radius:19px}.logo{font-size:50px;color:#7f9779}.eyebrow{font-size:10px;letter-spacing:3px;color:#91a18b}h1{font-family:Georgia,serif;font-weight:400;line-height:1.5;font-size:30px}p{font-size:13px;line-height:2.1;color:#82917c}input,button{width:100%;height:49px;border-radius:8px;font:inherit}input{border:1px solid #dfe6da;padding:0 13px;background:white}button{margin-top:13px;border:0;background:#697f61;color:#fff}small{display:block;margin-top:22px;color:#9da697;font-size:11px}</style></head><body><main class="card"><div class="logo">♧</div><div class="eyebrow">YOUR QUIET SPACE</div><h1>어떤 마음이든,<br>여기서는 괜찮아요.</h1><p>현재 비공개 시범 운영 중입니다.<br>초대 코드를 입력해 입장해 주세요.</p><form method="post" action="/unlock"><input name="code" type="password" required autocomplete="off" placeholder="초대 코드"><button>마음결 입장하기 →</button></form><small>자동 대화 서비스이며 전문 상담·치료의 대체가 아닙니다.</small></main></body></html>"""

def token():
    exp = str(int(time.time()) + 7*86400)
    mac = hmac.new(AUTH_SECRET.encode(), exp.encode(), hashlib.sha256).hexdigest()
    return exp + "." + mac

def auth(cookie):
    m = re.search(r"(?:^|;\s*)mg_session=([^; ]+)", cookie or "")
    if not m: return False
    try:
        exp, mac = m.group(1).split(".", 1)
        expected = hmac.new(AUTH_SECRET.encode(), exp.encode(), hashlib.sha256).hexdigest()
        return int(exp) > time.time() and hmac.compare_digest(mac, expected)
    except (IndexError, ValueError): return False

def permitted(ip, action, maximum=45):
    now = time.time()
    with LOCK:
        k=(ip,action)
        HITS[k] = [s for s in HITS[k] if now-s < 600]
        if len(HITS[k]) >= maximum: return False
        HITS[k].append(now)
        return True

def risk(text):
    s = re.sub(r"\s+", " ", text.lower())
    direct = re.search(r"자살|자해|죽고 ?싶|목숨을 끊|스스로 ?죽|suicid|kill myself|end my life", s)
    danger = re.search(r"뛰어내리|목을 ?매|약.{0,14}(많이|과다).{0,12}(먹|삼켰)", s)
    return bool(direct or danger)

def demo(message):
    s = message.lower().replace(" ", "")
    if any(k in s for k in ("누구야","인공지능","ai야","정체")):
        return "저는 마음결의 안내 체험 기능이에요. 아직 직접 학습한 대화형 상담 모델은 연결되지 않았고, 준비된 안내 문장으로 대화하고 있어요. 어떤 이야기를 나누고 싶으세요?"
    if any(k in s for k in ("안녕","반가워","hello")):
        return "안녕하세요. 이곳에서는 천천히 이야기하셔도 돼요. 오늘은 어떤 마음으로 오셨나요?"
    if any(k in s for k in ("불안","걱정","초조","두려")):
        return "걱정이 많을 땐 마음이 좀처럼 쉬기 어렵죠. 지금 가장 마음에 걸리는 일이 무엇인가요?"
    if any(k in s for k in ("힘들","지쳤","우울","슬퍼","외로")):
        return "그동안 마음이 무거우셨을 것 같아요. 당장 해결하려 애쓰지 않아도 괜찮아요. 무엇이 가장 버겁게 느껴지나요?"
    if any(k in s for k in ("친구","연인","가족","관계")):
        return "관계에서 겪는 어려움은 쉽게 정리되지 않을 수 있어요. 어떤 일이 있었는지 편안하게 들려주실래요?"
    return "아직 AI 모델이 연결되지 않아 안내 체험으로 답변하고 있어요. 이야기를 하나씩 정리해 볼까요? 가장 먼저 떠오르는 일이 무엇인가요?"

def answer(messages):
    text=messages[-1]["content"]
    safe=safety_response(text)
    if safe:
        return safe[0], "safety-guidance", safe[1]
    if not MODEL_URL:
        return demo_reply(messages), "guided-demo", "none"
    if KEYLESS_BACKEND and MODEL_PROBE_STATUS!="ok":
        raise RuntimeError("Anonymous free model is not currently available")
    payload = {"model":MODEL_NAME,"messages":[{"role":"system","content":PROMPT}]+messages[-16:],"stream":False}
    if MODEL_PROVIDER == "ollama":
        payload["options"]={"temperature":0.65}
    else:
        payload["temperature"]=0.65
        payload["max_tokens"]=640
        if FREE_EXTERNAL and not KEYLESS_BACKEND:
            # Never relax the account's original OpenRouter privacy filtering.
            payload["provider"]={"data_collection":"deny"}
        if KEYLESS_BACKEND:
            # External model provider is informed in the UI; data is sent only
            # after explicit opt-in. No downloads and no user API credentials.
            payload["max_tokens"]=900
    headers={"Content-Type":"application/json"}
    if MODEL_API_KEY: headers["Authorization"]="Bearer "+MODEL_API_KEY
    req=Request(MODEL_URL, json.dumps(payload, ensure_ascii=False).encode(), headers, method="POST")
    with urlopen(req, timeout=42) as f: data=json.load(f)
    s=(data.get("message") or {}).get("content") if MODEL_PROVIDER=="ollama" else (data.get("choices") or [{}])[0].get("message",{}).get("content")
    if not isinstance(s,str) or not s.strip():raise ValueError("Empty model response")
    s=re.sub(r"<think>[\s\S]*?</think>","",s,flags=re.I).strip()
    return safe_model_output(s[:8000]),"model","none"


# These error messages are deliberately generic: never send API keys, upstream
# request bodies, URLs with credentials, or sensitive chat text to the browser.
UPSTREAM_ERRORS = {
    400: "외부 AI 요청 형식이 맞지 않습니다. 관리자에게 알려 주세요.",
    401: "무료 AI 제공업체가 인증 요청을 거부했습니다. 관리자에게 알려 주세요.",
    402: "무료 AI 사용량이 부족하거나 제공업체의 무료 조건이 변경됐습니다.",
    403: "외부 AI 제공업체에서 이 요청을 거부했습니다.",
    404: "무료 대형 AI 모델을 찾지 못했습니다. 제공업체의 모델 상태를 확인해 주세요.",
    408: "무료 모델 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.",
    429: "무료 AI 요청 횟수 제한에 걸렸습니다. 나중에 다시 시도해 주세요.",
    500: "OpenRouter 또는 모델 제공업체에서 일시적인 오류가 발생했습니다.",
    502: "무료 모델 제공업체가 정상 응답하지 않았습니다. 잠시 후 다시 시도해 주세요.",
    503: "무료 모델 제공업체가 현재 사용 불가 상태입니다. 잠시 후 다시 시도해 주세요.",
    524: "무료 모델 제공업체의 응답이 지연되어 시간이 초과됐습니다.",
    529: "무료 모델 제공업체에 요청이 몰렸습니다. 잠시 후 다시 시도해 주세요.",
}
def upstream_message(status):
    return UPSTREAM_ERRORS.get(status,"외부 AI 제공업체에 요청하지 못했습니다. 관리자에게 문의해 주세요.")

def check_anonymous_large_model():
    # Probe using synthetic non-sensitive text. Keyless provider is separate
    # from the user's OpenRouter API key and never receives that key.
    global MODEL_PROBE_STATUS, MODEL_NAME
    candidates=("z-ai/glm-5:free","minimax/minimax-m2.1:free","dots-studio/dots-3-note-preview:free")
    for candidate in candidates:
        payload={"model":candidate,
                 "messages":[{"role":"user","content":"한국어로 짧게 '안녕하세요'라고 인사해 주세요."}],
                 "max_tokens":350,"stream":False}
        try:
            req=Request(MODEL_URL,
                        json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                        {"Content-Type":"application/json","User-Agent":"Maumgyeol-Demo/1.0"},
                        method="POST")
            with urlopen(req,timeout=40) as response:
                result=json.load(response)
            choice=(result.get("choices") or [{}])[0]
            msg=choice.get("message") or {}
            output=msg.get("content")
            if isinstance(output,str) and output.strip():
                MODEL_NAME=candidate
                MODEL_PROBE_STATUS="ok"
                print("KEYLESS_LLM_PROBE ok "+candidate,flush=True)
                return
            print("KEYLESS_LLM_PROBE empty_response "+candidate,flush=True)
        except HTTPError as error:
            print("KEYLESS_LLM_PROBE http_"+str(error.code)+" "+candidate,flush=True)
        except Exception as error:
            print("KEYLESS_LLM_PROBE "+type(error).__name__+" "+candidate,flush=True)
    MODEL_PROBE_STATUS="unavailable"
    print("KEYLESS_LLM_PROBE all_unavailable",flush=True)


def check_free_model_startup():
    if KEYLESS_BACKEND:
        check_anonymous_large_model()
        return
    # Only non-sensitive synthetic greetings are sent. Probe at most two free
    # Qwen-family models with identical privacy filtering.
    global MODEL_NAME, MODEL_PROBE_STATUS
    if not FREE_EXTERNAL:
        return
    candidates=[MODEL_NAME]
    fallback="qwen/qwen3-8b:free"
    if MODEL_NAME != fallback and MODEL_NAME.endswith(":free"):
        candidates.append(fallback)
    headers={"Content-Type":"application/json","Authorization":"Bearer "+MODEL_API_KEY}
    try:
        catalog_req=Request("https://openrouter.ai/api/v1/models/user?limit=1000",headers={"Authorization":"Bearer "+MODEL_API_KEY})
        with urlopen(catalog_req,timeout=15) as catalog_resp:
            catalog=json.load(catalog_resp)
        allowed_ids=[
            m.get("id","") for m in catalog.get("data",[])
            if isinstance(m,dict) and isinstance(m.get("id"),str)
        ]
        free_qwen=[m for m in allowed_ids if m.startswith("qwen/") and m.endswith(":free")]
        print("FREE_QWEN_CATALOG allowed_free_qwen_count="+str(len(free_qwen)),flush=True)
        for m in free_qwen:
            if m not in candidates and len(candidates)<3:
                candidates.append(m)
    except HTTPError as e:
        print("FREE_QWEN_CATALOG upstream_http_"+str(e.code),flush=True)
    except Exception as e:
        print("FREE_QWEN_CATALOG unavailable_"+type(e).__name__,flush=True)
    for candidate in candidates:
        if not candidate.endswith(":free"):
            break
        payload={
            "model":candidate,
            "messages":[{"role":"user","content":"안녕하세요. 한 문장으로 인사해 주세요."}],
            "max_tokens":180,
            "stream":False,
            "provider":{"data_collection":"deny"}
        }
        try:
            req=Request(MODEL_URL,json.dumps(payload,ensure_ascii=False).encode(),headers,method="POST")
            with urlopen(req,timeout=28) as resp:
                obj=json.load(resp)
            choices=obj.get("choices") or []
            success=bool(choices and choices[0].get("message",{}).get("content"))
            if success:
                MODEL_NAME=candidate
                MODEL_PROBE_STATUS="ok"
                print("FREE_QWEN_PROBE ok "+candidate,flush=True)
                return
            print("FREE_QWEN_PROBE empty_response "+candidate,flush=True)
        except HTTPError as exc:
            detail=""
            try:
                payload_error=json.loads(exc.read(4096)).get("error",{})
                if isinstance(payload_error,dict):
                    msg=str(payload_error.get("message","")).lower()
                    meta=payload_error.get("metadata") or {}
                    if isinstance(meta,dict) and meta.get("failed_routing_step"):
                        detail=" failed_routing_step="+re.sub(r"[^a-zA-Z0-9_-]","",str(meta["failed_routing_step"]))[:45]
                    elif any(k in msg for k in ("privacy","data policy","data collection","guardrail")):
                        detail=" provider_privacy_filter"
                    elif any(k in msg for k in ("no endpoints","no provider","not available")):
                        detail=" no_eligible_provider"
                    elif "model" in msg:
                        detail=" model_unavailable"
            except (ValueError,AttributeError,TypeError):
                pass
            print("FREE_QWEN_PROBE upstream_http_"+str(exc.code)+" "+candidate+detail,flush=True)
            if exc.code not in (404,503,502,529):
                return
        except (URLError, TimeoutError) as exc:
            print("FREE_QWEN_PROBE connection_error_"+type(exc).__name__,flush=True)
            return
        except Exception as exc:
            print("FREE_QWEN_PROBE response_error_"+type(exc).__name__,flush=True)
            return
    MODEL_PROBE_STATUS="unavailable"
    print("FREE_QWEN_PROBE all_eligible_qwen_providers_failed",flush=True)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,content,ct="application/json; charset=utf-8",headers=None):
        if isinstance(content,(dict,list)): content=json.dumps(content,ensure_ascii=False)
        data=content.encode("utf-8") if isinstance(content,str) else content
        self.send_response(status)
        for key,val in {"Content-Type":ct,"Content-Length":str(len(data)),"Cache-Control":"no-store","Referrer-Policy":"no-referrer","X-Robots-Tag":"noindex,nofollow","X-Frame-Options":"DENY","X-Content-Type-Options":"nosniff"}.items():self.send_header(key,val)
        for key,val in (headers or {}).items():self.send_header(key,val)
        self.end_headers()
        if self.command!="HEAD": self.wfile.write(data)
    def do_GET(self):
        p=urlsplit(self.path).path
        if p=="/health":return self.send(200,{"ok":True})
        if p=="/robots.txt":return self.send(200,"User-agent: *\nDisallow: /\n","text/plain")
        if not auth(self.headers.get("Cookie","")):
            return self.send(200,LOGIN,"text/html; charset=utf-8") if p=="/" else self.send(401,{"error":"초대 코드가 필요합니다."})
        if p in ("/","/index.html"):
            return self.send(200,INDEX.read_bytes(),"text/html; charset=utf-8")
        if p=="/api/status":
            return self.send(200,{"ready":(MODEL_PROBE_STATUS=="ok") if FREE_EXTERNAL else bool(MODEL_URL),"configured":bool(MODEL_URL),"external":FREE_EXTERNAL,"model_status":MODEL_PROBE_STATUS,"provider":MODEL_SOURCE,"mode":"keyless-large-ai" if KEYLESS_BACKEND else ("model-configured" if MODEL_URL else "guided-demo"),"model":MODEL_NAME if MODEL_URL else None})
        return self.send(404,{"error":"주소를 찾을 수 없습니다."})
    def do_HEAD(self): return self.do_GET()
    def do_POST(self):
        p=urlsplit(self.path).path
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<0 or n>32000:return self.send(413,{"error":"입력 크기를 확인해 주세요."})
            raw=self.rfile.read(n)
        except ValueError:return self.send(400,{"error":"입력이 올바르지 않습니다."})
        ip=self.client_address[0]
        if p=="/unlock":
            if not permitted(ip,"login",15):return self.send(429,{"error":"잠시 후 다시 시도해 주세요."})
            code=parse_qs(raw.decode(errors="replace")).get("code",[""])[0]
            if not hmac.compare_digest(code,ACCESS_CODE):return self.send(401,LOGIN.replace("초대 코드","코드를 다시 확인해 주세요"),"text/html; charset=utf-8")
            return self.send(303,b"","text/plain",{"Location":"/","Set-Cookie":"mg_session="+token()+"; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=604800"})
        if not auth(self.headers.get("Cookie","")):return self.send(401,{"error":"접근 코드 입력 후 이용해 주세요."})
        if p!="/api/chat":return self.send(404,{"error":"주소를 찾을 수 없습니다."})
        if not permitted(ip,"chat",60):return self.send(429,{"error":"요청이 너무 많아요."})
        try:
            body=json.loads(raw)
            messages=body.get("messages")
            if FREE_EXTERNAL and body.get("external_consent") is not True:
                return self.send(403,{"error":"외부 AI 전송 동의가 필요합니다. 동의란을 확인해 주세요."})
            if not isinstance(messages,list) or not 1<=len(messages)<=32:raise ValueError()
            if any(not isinstance(m,dict) or m.get("role") not in ("user","assistant") or not isinstance(m.get("content"),str) or len(m["content"])>2400 for m in messages):raise ValueError()
            if messages[-1]["role"]!="user" or not messages[-1]["content"].strip():raise ValueError()
        except (ValueError,TypeError,AttributeError):
            return self.send(400,{"error":"메시지 형식을 확인해 주세요."})
        try: reply,source,safety=answer(messages)
        except HTTPError as exc:
            print("FREE_QWEN_CHAT", "upstream_http_"+str(exc.code),flush=True)
            return self.send(503,{"error":upstream_message(exc.code),"upstream_status":exc.code})
        except (URLError, TimeoutError) as exc:
            print("FREE_QWEN_CHAT", "connection_error_"+type(exc).__name__,flush=True)
            return self.send(503,{"error":"외부 AI 서버에 네트워크 연결이 되지 않거나 응답이 늦어졌습니다."})
        except Exception as exc:
            print("FREE_QWEN_CHAT", "model_error_"+type(exc).__name__,flush=True)
            return self.send(503,{"error":"외부 AI 응답을 처리하지 못했습니다. 무료 모델이 잠시 불안정할 수 있습니다."})
        return self.send(200,{"reply":reply,"source":source,"safety":safety})

if __name__=="__main__":
    print("Maumgyeol running",PORT,"guided-demo" if not MODEL_URL else "model-configured",flush=True)
    if FREE_EXTERNAL:
        threading.Thread(target=check_free_model_startup,daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
