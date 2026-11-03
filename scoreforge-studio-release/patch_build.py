"""Reduce memory peaks when ScoreForge runs in a 512MB Render service."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def replace_once(relative: str, before: str, after: str) -> None:
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    if after in source:
        return
    if source.count(before) != 1:
        raise RuntimeError(f"Patch target changed: {relative}: {before[:80]}")
    path.write_text(source.replace(before, after, 1), encoding="utf-8")

replace_once(
    "web/engine.py",
    "import logging\nimport math\nimport shutil",
    "import logging\nimport math\nimport os\nimport shutil",
)
replace_once(
    "web/engine.py",
    "    config.validate()\n    directory.mkdir(parents=True, exist_ok=True)",
    "    config.validate()\n"
    "    if os.environ.get('SCOREFORGE_LOW_MEMORY', '1') == '1':\n"
    "        config = replace(config, sample_rate=11025, n_fft=2048, hop=256)\n"
    "    directory.mkdir(parents=True, exist_ok=True)",
)
replace_once(
    "web/engine.py",
    "    onset = librosa.onset.onset_strength(y=y, sr=config.sample_rate, hop_length=config.hop)",
    "    onset = memory_safe_onset(y, config)",
)
replace_once(
    "web/engine.py",
    "def convert(path: Path, directory: Path, config: Config, status: Status,",
    "def memory_safe_onset(y: np.ndarray, cfg: Config) -> np.ndarray:\n"
    "    \"\"\"Compute beat onsets in bounded 8-second windows.\"\"\"\n"
    "    window = cfg.sample_rate * 8\n"
    "    segments = []\n"
    "    for start in range(0, len(y), window):\n"
    "        clip = y[start:start + window]\n"
    "        if len(clip) < 1024 or np.max(np.abs(clip)) < 1e-7:\n"
    "            frames = max(1, int(math.ceil(len(clip) / cfg.hop)))\n"
    "            segments.append(np.zeros(frames, dtype=np.float32))\n"
    "            continue\n"
    "        part = librosa.onset.onset_strength(\n"
    "            y=clip, sr=cfg.sample_rate, hop_length=cfg.hop, n_fft=1024\n"
    "        )\n"
    "        frames = max(1, int(math.ceil(len(clip) / cfg.hop)))\n"
    "        if len(part) < frames:\n"
    "            part = np.pad(part, (0, frames - len(part)))\n"
    "        segments.append(np.asarray(part[:frames], dtype=np.float32))\n"
    "    return np.concatenate(segments) if segments else np.zeros(1, dtype=np.float32)\n\n\n"
    "def convert(path: Path, directory: Path, config: Config, status: Status,",
)
replace_once(
    "scoreforge/chunking.py",
    "chunk_seconds: float = 20.0,\n                         overlap_seconds: float = 1.2",
    "chunk_seconds: float = 8.0,\n                         overlap_seconds: float = 0.8",
)
replace_once(
    "web/static/app.js",
    "processing:false, maxUpload:45,",
    "processing:false, maxUpload:25,",
)
replace_once(
    "web/static/app.js",
    "  function upload(){if(!state.file || state.processing)return;",
    "  function upload(){if(!state.file || state.processing)return;\n"
    "    if(state.file.size > state.maxUpload*1048576){\n"
    "      fail('파일이 서버 제한 '+state.maxUpload+'MB를 초과했습니다. MP3로 압축하거나 짧게 잘라 다시 시도하세요.');return;}\n",
)
replace_once(
    "web/static/app.js",
    "    } catch(e){clearInterval(state.poll);state.poll=null;fail(e.message);}}",
    "    } catch(e){clearInterval(state.poll);state.poll=null;\n"
    "      const message=String(e.message||e);\n"
    "      fail(message.includes('작업을 찾을 수 없습니다')\n"
    "        ? '분석 중 서버가 재시작되어 작업 정보가 사라졌습니다. 짧은 MP3로 재시도해 주세요.' : message);}}",
)
print("ScoreForge low-memory build patch applied")
