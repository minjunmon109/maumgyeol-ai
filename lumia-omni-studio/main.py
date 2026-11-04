import os, io, json, re, csv, uuid, time, zipfile
from pathlib import Path
from collections import defaultdict, deque
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
import httpx

HERE = Path(__file__).resolve().parent
BASE = os.getenv("LUMIA_BASE_URL", "https://lumiarouter.com/v1").rstrip("/")
API_KEY = os.getenv("LUMIA_API_KEY", "").strip()
PASSWORD = os.getenv("APP_PASSWORD", "").strip()
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-sonnet-5")
ARTIFACTS = Path("/tmp/lumia-omni-artifacts")
ARTIFACTS.mkdir(exist_ok=True)
app = FastAPI(title="LUMIA OMNI STUDIO", docs_url=None, redoc_url=None)
hits = defaultdict(deque)

def guard(req):
    if not PASSWORD:
        raise HTTPException(503, "서버 관리자가 APP_PASSWORD를 설정해야 합니다.")
    if req.headers.get("x-studio-password", "") != PASSWORD:
        raise HTTPException(401, "스튜디오 비밀번호가 틀렸습니다.")
    ip = req.client.host if req.client else "unknown"
    q = hits[ip]
    now = time.time()
    while q and now - q[0] > 60: q.popleft()
    if len(q) >= 30: raise HTTPException(429, "요청 제한을 초과했습니다.")
    q.append(now)

def getkey():
    if not API_KEY:
        raise HTTPException(503, "LUMIA_API_KEY가 아직 Render 환경변수에 등록되지 않았습니다.")

async def complete(messages, model):
    getkey()
    model = (model or DEFAULT_MODEL)[:110]
    body = {"model": model, "messages": messages[-30:], "max_tokens": 6000, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=150) as client:
            resp = await client.post(BASE + "/chat/completions", headers={"Authorization": "Bearer " + API_KEY}, json=body)
        if resp.status_code >= 400:
            raise HTTPException(502, "LumiaRouter 오류 " + str(resp.status_code) + ": " + resp.text[:500])
        msg = resp.json()["choices"][0]["message"].get("content", "")
        if isinstance(msg, list): msg = "\n".join(i.get("text", "") for i in msg if isinstance(i, dict))
        return str(msg).strip()
    except httpx.RequestError as e:
        raise HTTPException(502, "LumiaRouter 연결 실패: " + str(e)[:180])
    except (ValueError, KeyError, IndexError):
        raise HTTPException(502, "LumiaRouter 응답 형식을 확인해 주세요.")

def strip_fences(s):
    s = s.strip()
    s = re.sub(r"^\\s*\\\`{3}(?:\\w+)?\\s*\\n", "", s)
    return re.sub(r"\\n\\\`{3}\\s*$", "", s).strip()

def decode_json(s):
    s = strip_fences(s)
    try: return json.loads(s)
    except Exception:
        i = s.find("{"); j = s.rfind("}")
        if i >= 0 and j > i:
            try: return json.loads(s[i:j+1])
            except: pass
    return {}

def filename(raw):
    return (re.sub(r"[^a-zA-Z0-9_가-힣.() -]", "_", str(raw)).strip(". ") or "result")[:70]

def artifact(name, b):
    if len(b) > 20_000_000: raise HTTPException(413, "파일 크기를 초과했습니다.")
    aid = uuid.uuid4().hex
    (ARTIFACTS / aid).write_bytes(b)
    (ARTIFACTS / (aid+".json")).write_text(json.dumps({"name": filename(name)}, ensure_ascii=False))
    return {"id": aid, "name": filename(name), "bytes":len(b)}

@app.get("/")
def home():
    return FileResponse(HERE / "index.html")

@app.get("/health")
def health():
    return {"ok":True, "api_configured":bool(API_KEY), "password_configured":bool(PASSWORD)}

@app.get("/api/status")
def status(req: Request):
    guard(req)
    return {"api_configured":bool(API_KEY), "model":DEFAULT_MODEL}

@app.get("/api/models")
async def models(req: Request):
    guard(req)
    if not API_KEY: return {"data":[{"id":DEFAULT_MODEL}], "warning":"API 키를 설정해 주세요."}
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r=await c.get(BASE+"/models",headers={"Authorization":"Bearer "+API_KEY})
        r.raise_for_status()
        return {"data":[{"id":x["id"]} for x in r.json().get("data", []) if isinstance(x,dict) and x.get("id")][:200]}
    except Exception:
        return {"data":[{"id":DEFAULT_MODEL}], "warning":"모델 목록을 가져올 수 없습니다."}

@app.post("/api/chat")
async def chat(req: Request):
    guard(req)
    d = await req.json()
    messages = d.get("messages", [])
    if not isinstance(messages,list) or not messages or len(messages)>45:
        raise HTTPException(400, "메시지 목록이 올바르지 않습니다.")
    history = []
    for m in messages:
        if not isinstance(m,dict) or m.get("role") not in ("user","assistant","system"): continue
        c = m.get("content","")
        if isinstance(c,str): c=c[:38000]
        if isinstance(c,list):
            c = c[:8]
        history.append({"role":m["role"],"content":c})
    answer=await complete([{"role":"system","content":"당신은 정확하고 유용한 한국어 AI 비서입니다. 코딩, 문서, 학습, 분석 등 다양한 업무를 돕고 불확실한 내용은 명시하세요."}]+history, d.get("model"))
    return {"answer":answer}

@app.post("/api/upload")
async def upload(req: Request, file: UploadFile = File(...)):
    guard(req)
    data = await file.read(10_000_001)
    if len(data)>10_000_000: raise HTTPException(413, "첨부 파일은 10MB 이하여야 합니다.")
    name = filename(file.filename or "attachment")
    ext = Path(name).suffix.lower()
    result = ""
    try:
        if ext in (".txt",".md",".csv",".json",".xml",".html",".py",".js",".ts",".css",".yaml",".yml",".sql",".log"):
            result = data.decode("utf-8-sig", errors="replace")
        elif ext == ".pdf":
            from pypdf import PdfReader
            p = PdfReader(io.BytesIO(data))
            result = "\n".join(x.extract_text() or "" for x in p.pages[:30])
        elif ext == ".docx":
            from docx import Document
            result = "\n".join(x.text for x in Document(io.BytesIO(data)).paragraphs)
        elif ext == ".xlsx":
            from openpyxl import load_workbook
            book=load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            result="\n".join("["+w.title+"]\n"+"\n".join(" | ".join(str(x or "") for x in row[:25]) for row in list(w.values)[:150]) for w in book.worksheets[:6])
            book.close()
        elif ext == ".pptx":
            from pptx import Presentation
            p=Presentation(io.BytesIO(data))
            result="\n".join("\n".join(s.text for s in slide.shapes if s.has_text_frame) for slide in p.slides[:40])
        elif ext in (".png",".jpg",".jpeg",".webp"):
            import base64
            mime = "image/jpeg" if ext in (".jpg",".jpeg") else ("image/webp" if ext==".webp" else "image/png")
            return {"name":name,"image":"data:"+mime+";base64,"+base64.b64encode(data).decode(),"text":""}
        else:
            raise HTTPException(415, "지원하지 않는 파일입니다.")
    except HTTPException: raise
    except Exception as e: raise HTTPException(422, "파일 해석 실패: "+str(e)[:130])
    return {"name":name, "text": result[:32000], "truncated":len(result)>32000}

@app.post("/api/generate")
async def generate(req: Request):
    guard(req)
    d = await req.json()
    kind = str(d.get("kind","txt")).lower()
    prompt = str(d.get("prompt","")).strip()[:12000]
    model = d.get("model")
    if not prompt: raise HTTPException(400,"무엇을 만들지 입력해 주세요.")
    extension = {"pdf":"pdf","docx":"docx","xlsx":"xlsx","pptx":"pptx","html":"html","py":"py","js":"js","md":"md","txt":"txt","csv":"csv","zip":"zip"}.get(kind)
    if not extension: raise HTTPException(400,"지원하지 않는 파일 유형")
    name = filename(d.get("name") or ("lumia_result."+extension))
    if not name.lower().endswith("."+extension): name+="."+extension
    extra=""
    if kind=="xlsx": extra='{"sheets":[{"name":"Sheet1","rows":[["항목","내용"],["예시","내용"]]}]} 형식의 유효한 JSON만 출력해. 사용자의 요청에 맞는 유용한 표를 작성해.'
    elif kind=="pptx": extra='{"slides":[{"title":"제목","bullets":["설명 1","설명 2"]}]} 형식의 유효한 JSON만 출력해. 5~10장의 실질적인 슬라이드를 만들어.'
    elif kind=="zip": extra='{"files":[{"path":"index.html","content":"<!doctype html>..."},{"path":"readme.md","content":"..."}]} 형식의 유효한 JSON만 출력해. 실행 가능한 복수 소스 파일을 작성해. 상대 경로만 사용해.'
    elif kind in ("html","py","js","csv"): extra="파일 본문 전체만 출력하고 설명이나 코드펜스는 쓰지 마. 코드를 빠뜨리지 마."
    else: extra="실제로 파일에 담길 완성된 한국어 본문만 출력해. 제목, 소제목, 구체적인 내용을 포함해."
    body=await complete([{"role":"system","content":"요청받은 완성된 파일을 제작하는 전문 작성자다. 다른 설명 없이 지정된 형식만 출력해. "+extra},{"role":"user","content":prompt}],model)
    if kind=="pdf":
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
        stream=io.BytesIO()
        c=canvas.Canvas(stream,pagesize=(595,842))
        x,y=48,793
        for line in body.splitlines():
            line=line.replace("# ","").replace("**","").replace("\t","    ")
            chunks=[line[i:i+49] for i in range(0,len(line),49)] or [""]
            for chunk in chunks:
                if y<55: c.showPage();y=793
                c.setFont("HYSMyeongJo-Medium",10.5)
                c.drawString(x,y,chunk);y-=17
            y-=5
        c.save()
        contents=stream.getvalue()
    elif kind=="docx":
        from docx import Document
        document=Document()
        for line in body.splitlines():
            if line.startswith("# "): document.add_heading(line[2:],level=1)
            elif line.startswith("## "):document.add_heading(line[3:],level=2)
            else:document.add_paragraph(line)
        out=io.BytesIO();document.save(out);contents=out.getvalue()
    elif kind=="xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        raw=decode_json(body)
        book=Workbook();book.remove(book.active)
        for spec in (raw.get("sheets") or [{"name":"Data","rows":[["내용"],[body[:25000]]]}])[:12]:
            sh=book.create_sheet(title=filename(spec.get("name","Data"))[:31])
            for row in spec.get("rows",[])[:1500]:
                sh.append([v if isinstance(v,(int,float,str)) else json.dumps(v,ensure_ascii=False) for v in row][:40])
            for cell in sh[1]:
                cell.font=Font(bold=True,color="FFFFFF")
                cell.fill=PatternFill("solid",fgColor="17365D")
            for col in sh.columns:
                letter=col[0].column_letter
                sh.column_dimensions[letter].width=min(48,max(12,max(len(str(cell.value or "")) for cell in list(col)[:150])+3))
        out=io.BytesIO();book.save(out);contents=out.getvalue()
    elif kind=="pptx":
        from pptx import Presentation
        from pptx.util import Inches,Pt
        raw=decode_json(body)
        deck=Presentation()
        deck.slide_width=Inches(13.333);deck.slide_height=Inches(7.5)
        slides=raw.get("slides") or [{"title":"문서","bullets":body.splitlines()[:8]}]
        for spec in slides[:24]:
            slide=deck.slides.add_slide(deck.slide_layouts[1])
            slide.shapes.title.text=str(spec.get("title","제목"))
            box=slide.placeholders[1].text_frame;box.clear()
            for i,bullet in enumerate(spec.get("bullets",[])[:10]):
                p=box.paragraphs[0] if i==0 else box.add_paragraph()
                p.text=str(bullet);p.font.size=Pt(21)
        out=io.BytesIO();deck.save(out);contents=out.getvalue()
    elif kind=="zip":
        raw=decode_json(body);out=io.BytesIO()
        with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
            for f in (raw.get("files") or [])[:35]:
                path=str(f.get("path","")).replace("\\","/")
                if not path or path.startswith("/") or ".." in path.split("/"):continue
                z.writestr(path[:150],str(f.get("content",""))[:250000])
        contents=out.getvalue()
    else: contents=strip_fences(body).encode("utf-8")
    result=artifact(name,contents)
    if kind in ("html","py","js","md","txt","csv"):result["preview"]=contents.decode("utf-8",errors="replace")[:100000]
    return result

@app.get("/api/download/{aid}")
def download(aid: str, req: Request):
    guard(req)
    if not re.fullmatch("[a-f0-9]{32}",aid):raise HTTPException(400,"잘못된 파일 식별자")
    meta=ARTIFACTS/(aid+".json");content=ARTIFACTS/aid
    if not meta.exists() or not content.exists():raise HTTPException(404,"파일이 없거나 서버가 재시작되었습니다.")
    from urllib.parse import quote
    name=json.loads(meta.read_text()).get("name","result.txt")
    return FileResponse(content,headers={"Content-Disposition": "attachment; filename*=UTF-8''"+quote(name)},media_type="application/octet-stream")
