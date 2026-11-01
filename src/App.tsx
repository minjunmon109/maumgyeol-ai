import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { DragEvent, ChangeEvent, KeyboardEvent as ReactKeyboardEvent } from 'react';
import { ANALYSIS_RATE, MAX_DURATION, downmixForAnalysis, formatTime, makeAudioContext, validateMp3, waveformPeaks } from './lib/audio';
import { makeChart } from './lib/chart';
import { emptyScore } from './types';
import type { AnalysisResult, Difficulty, Judgment, Lane, Note, ScoreState, Screen, WorkerMessage } from './types';

export const JUDGMENT_WINDOWS = { perfect: 0.05, great: 0.10, good: 0.17 } as const;
const APPROACH_TIME = 1.75;
const HIT_LINE_PERCENT = 82;
const TRAVEL_PERCENT = 92;
const LANES = [0, 1, 2, 3] as const;
const KEYS = ['D', 'F', 'J', 'K'] as const;
const LABELS: Record<Judgment, string> = { perfect: 'PERFECT', great: 'GREAT', good: 'GOOD', miss: 'MISS' };

interface Track {
  title: string;
  duration: number;
  waveform: number[];
  analysis: AnalysisResult;
}
interface Feedback { label: string; tone: Judgment | 'empty'; id: number }

function Icon({ name, size = 20 }: { name: 'music' | 'upload' | 'play' | 'pause' | 'restart' | 'exit' | 'shield' | 'sound' | 'spark' | 'headphones'; size?: number }) {
  const paths: Record<typeof name, ReactNode> = {
    music: <><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5"/><path d="M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></>,
    play: <path d="m8 5 12 7-12 7z"/>,
    pause: <><path d="M8 5v14M16 5v14"/></>,
    restart: <><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/></>,
    exit: <><path d="M10 17l5-5-5-5m5 5H3"/><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/></>,
    shield: <><path d="m12 22 7-4V6l-7-4-7 4v12z"/><path d="m9 12 2 2 4-4"/></>,
    sound: <><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9a5 5 0 0 1 0 6M20 6a9 9 0 0 1 0 12"/></>,
    spark: <path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/>,
    headphones: <><path d="M3 14v-3a9 9 0 0 1 18 0v3"/><rect x="3" y="13" width="4" height="7" rx="2"/><rect x="17" y="13" width="4" height="7" rx="2"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Waveform({ values, progress = 0 }: { values: number[]; progress?: number }) {
  return <div className="waveform" aria-hidden="true">
    {values.map((value, index) => <span
      key={index}
      className={index / values.length <= progress ? 'wave-bar played' : 'wave-bar'}
      style={{ height: `${Math.round(14 + value * 86)}%` }}
    />)}
  </div>;
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="stat-tile"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('idle');
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('파일을 준비하고 있어요');
  const [track, setTrack] = useState<Track | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty>('normal');
  const [bpmInput, setBpmInput] = useState('120');
  const [appliedBpm, setAppliedBpm] = useState(120);
  const [notes, setNotes] = useState<Note[]>([]);
  const [time, setTime] = useState(0);
  const [stats, setStats] = useState<ScoreState>(emptyScore);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [pulsing, setPulsing] = useState<number[]>([]);
  const [completed, setCompleted] = useState(false);

  const audioRef = useRef<AudioContext | null>(null);
  const bufferRef = useRef<AudioBuffer | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const jobRef = useRef(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const screenRef = useRef<Screen>('idle');
  const notesRef = useRef<Note[]>([]);
  const trackRef = useRef<Track | null>(null);
  const judgedRef = useRef(new Set<number>());
  const missCursorRef = useRef(0);
  const statsRef = useRef<ScoreState>(emptyScore());
  const offsetRef = useRef(0);
  const originRef = useRef(0);
  const startingRef = useRef(false);
  const pulseTimers = useRef(new Map<number, number>());
  const feedbackTimer = useRef<number | null>(null);

  const switchScreen = useCallback((next: Screen) => {
    screenRef.current = next;
    setScreen(next);
  }, []);

  const stopSource = useCallback(() => {
    const source = sourceRef.current;
    sourceRef.current = null;
    if (source) {
      source.onended = null;
      try { source.stop(); } catch { /* Already stopped. */ }
      source.disconnect();
    }
  }, []);

  const playbackPosition = useCallback(() => {
    if (screenRef.current === 'playing' && audioRef.current) {
      return Math.max(0, audioRef.current.currentTime - originRef.current);
    }
    return offsetRef.current;
  }, []);

  const applyJudgments = useCallback((items: Judgment[]) => {
    if (!items.length) return;
    const previous = statsRef.current;
    const next: ScoreState = { ...previous, counts: { ...previous.counts } };
    for (const judgment of items) {
      next.counts[judgment]++;
      next.judged++;
      if (judgment === 'miss') {
        next.combo = 0;
      } else {
        next.combo++;
        next.maxCombo = Math.max(next.maxCombo, next.combo);
        next.score += judgment === 'perfect' ? 1000 : judgment === 'great' ? 700 : 350;
        next.weighted += judgment === 'perfect' ? 1 : judgment === 'great' ? 0.75 : 0.4;
      }
    }
    statsRef.current = next;
    setStats(next);
  }, []);

  const finishGame = useCallback((fullyPlayed: boolean) => {
    if (screenRef.current !== 'playing' && screenRef.current !== 'paused') return;
    if (fullyPlayed) {
      const misses: Judgment[] = [];
      for (const note of notesRef.current) {
        if (!judgedRef.current.has(note.id)) {
          judgedRef.current.add(note.id);
          misses.push('miss');
        }
      }
      applyJudgments(misses);
    }
    offsetRef.current = Math.min(playbackPosition(), trackRef.current?.duration ?? 0);
    setTime(offsetRef.current);
    stopSource();
    setCompleted(fullyPlayed);
    switchScreen('result');
  }, [applyJudgments, playbackPosition, stopSource, switchScreen]);

  const startPlayback = useCallback(async (fromBeginning: boolean) => {
    if (startingRef.current || !audioRef.current || !bufferRef.current || !trackRef.current || notesRef.current.length === 0) return;
    startingRef.current = true;
    try {
      const context = audioRef.current;
      await context.resume(); // Happens after a real click/tap, per autoplay policy.
      stopSource();
      if (fromBeginning) {
        judgedRef.current = new Set();
        missCursorRef.current = 0;
        statsRef.current = emptyScore();
        setStats(statsRef.current);
        setFeedback(null);
        offsetRef.current = 0;
        setTime(0);
      }
      const offset = Math.min(offsetRef.current, bufferRef.current.duration - 0.001);
      const when = context.currentTime + 0.08;
      const source = context.createBufferSource();
      source.buffer = bufferRef.current;
      source.connect(context.destination);
      sourceRef.current = source;
      originRef.current = when - offset;
      source.onended = () => {
        if (sourceRef.current === source && screenRef.current === 'playing') finishGame(true);
      };
      source.start(when, offset);
      switchScreen('playing');
    } catch {
      stopSource();
      setError('음악을 재생할 수 없어요. 기기의 음량과 브라우저 오디오 권한을 확인한 후 다시 시도해 주세요.');
      switchScreen('error');
    } finally {
      startingRef.current = false;
    }
  }, [finishGame, stopSource, switchScreen]);

  const pauseGame = useCallback(() => {
    if (screenRef.current !== 'playing') return;
    offsetRef.current = Math.min(playbackPosition(), trackRef.current?.duration ?? 0);
    setTime(offsetRef.current);
    stopSource();
    switchScreen('paused');
  }, [playbackPosition, stopSource, switchScreen]);

  const resumeGame = useCallback(() => {
    if (screenRef.current === 'paused') void startPlayback(false);
  }, [startPlayback]);

  const pulseLane = useCallback((lane: Lane) => {
    setPulsing((current) => [...new Set([...current, lane])]);
    const earlier = pulseTimers.current.get(lane);
    if (earlier !== undefined) window.clearTimeout(earlier);
    const timer = window.setTimeout(() => {
      setPulsing((current) => current.filter((item) => item !== lane));
      pulseTimers.current.delete(lane);
    }, 115);
    pulseTimers.current.set(lane, timer);
  }, []);

  const showFeedback = useCallback((label: string, tone: Judgment | 'empty') => {
    setFeedback({ label, tone, id: performance.now() });
    if (feedbackTimer.current !== null) window.clearTimeout(feedbackTimer.current);
    feedbackTimer.current = window.setTimeout(() => setFeedback(null), 540);
  }, []);

  const hitLane = useCallback((lane: Lane) => {
    if (screenRef.current !== 'playing') return;
    pulseLane(lane);
    const position = playbackPosition();
    let closest: Note | null = null;
    let nearest = Infinity;
    for (const note of notesRef.current) {
      if (note.time > position + JUDGMENT_WINDOWS.good) break;
      if (note.lane !== lane || judgedRef.current.has(note.id)) continue;
      const distance = Math.abs(note.time - position);
      if (distance <= JUDGMENT_WINDOWS.good && distance < nearest) {
        closest = note;
        nearest = distance;
      }
    }
    if (!closest) { showFeedback('EMPTY', 'empty'); return; }
    judgedRef.current.add(closest.id);
    const judgment: Judgment = nearest <= JUDGMENT_WINDOWS.perfect ? 'perfect'
      : nearest <= JUDGMENT_WINDOWS.great ? 'great' : 'good';
    applyJudgments([judgment]);
    showFeedback(LABELS[judgment], judgment);
  }, [applyJudgments, playbackPosition, pulseLane, showFeedback]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      const lane = LANES.find((item) => event.code === `Key${KEYS[item]}`);
      if (lane !== undefined && screenRef.current === 'playing') {
        event.preventDefault();
        hitLane(lane);
      } else if (event.code === 'Escape') {
        if (screenRef.current === 'playing') pauseGame();
        else if (screenRef.current === 'paused') resumeGame();
      }
    };
    const onVisibility = () => { if (document.hidden) pauseGame(); };
    window.addEventListener('keydown', onKeyDown);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [hitLane, pauseGame, resumeGame]);

  useEffect(() => {
    if (screen !== 'playing') return;
    let frame = 0;
    const tick = () => {
      if (screenRef.current !== 'playing') return;
      const position = playbackPosition();
      offsetRef.current = position;
      setTime(position);
      const misses: Judgment[] = [];
      while (missCursorRef.current < notesRef.current.length
        && notesRef.current[missCursorRef.current].time < position - JUDGMENT_WINDOWS.good) {
        const note = notesRef.current[missCursorRef.current++];
        if (!judgedRef.current.has(note.id)) {
          judgedRef.current.add(note.id);
          misses.push('miss');
        }
      }
      if (misses.length) {
        applyJudgments(misses);
        showFeedback('MISS', 'miss');
      }
      if (position >= (trackRef.current?.duration ?? Infinity)) {
        finishGame(true);
      } else frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [screen, playbackPosition, applyJudgments, finishGame, showFeedback]);

  useEffect(() => () => {
    ++jobRef.current;
    workerRef.current?.terminate();
    if (feedbackTimer.current !== null) window.clearTimeout(feedbackTimer.current);
    pulseTimers.current.forEach((timer) => window.clearTimeout(timer));
    stopSource();
    void audioRef.current?.close().catch(() => undefined);
  }, [stopSource]);

  const resetToUpload = useCallback(() => {
    ++jobRef.current;
    workerRef.current?.terminate();
    workerRef.current = null;
    stopSource();
    void audioRef.current?.close().catch(() => undefined);
    audioRef.current = null;
    bufferRef.current = null;
    trackRef.current = null;
    notesRef.current = [];
    judgedRef.current = new Set();
    setTrack(null);
    setNotes([]);
    setTime(0);
    setFeedback(null);
    setError('');
    offsetRef.current = 0;
    if (fileInputRef.current) fileInputRef.current.value = '';
    switchScreen('idle');
  }, [stopSource, switchScreen]);

  const receiveFile = useCallback(async (file?: File) => {
    if (!file) return;
    const job = ++jobRef.current;
    workerRef.current?.terminate();
    workerRef.current = null;
    stopSource();
    setError('');
    setProgress(0);
    setProgressMessage('파일을 확인하고 있어요');
    switchScreen('analyzing');
    try {
      validateMp3(file);
      if (!audioRef.current || audioRef.current.state === 'closed') audioRef.current = makeAudioContext();
      const bytes = await file.arrayBuffer();
      if (job !== jobRef.current) return;
      setProgress(12);
      setProgressMessage('MP3를 오디오 데이터로 변환하고 있어요');
      let buffer: AudioBuffer;
      try { buffer = await audioRef.current.decodeAudioData(bytes); }
      catch { throw new Error('MP3 디코딩에 실패했어요. 손상되지 않은 MP3인지 확인해 주세요.'); }
      if (job !== jobRef.current) return;
      if (buffer.duration > MAX_DURATION) throw new Error('곡 길이는 최대 12분까지 지원해요. 더 짧은 MP3를 사용해 주세요.');
      if (buffer.duration < 2) throw new Error('최소 2초 이상의 MP3를 선택해 주세요.');
      bufferRef.current = buffer;
      const peaks = waveformPeaks(buffer);
      setProgress(22);
      setProgressMessage('파형을 분석용 데이터로 변환하고 있어요');
      const samples = await downmixForAnalysis(buffer, (value) => {
        if (job === jobRef.current) setProgress(value);
      });
      if (job !== jobRef.current) return;
      const worker = new Worker(new URL('./workers/analyze.worker.ts', import.meta.url), { type: 'module' });
      workerRef.current = worker;
      worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
        if (job !== jobRef.current) return;
        const message = event.data;
        if (message.type === 'progress') {
          setProgress(message.progress);
          setProgressMessage(message.message);
        } else if (message.type === 'error') {
          worker.terminate();
          workerRef.current = null;
          setError(message.message);
          switchScreen('error');
        } else {
          worker.terminate();
          workerRef.current = null;
          const title = file.name.replace(/\.mp3$/i, '').replace(/[_-]+/g, ' ').trim() || '제목 없는 곡';
          const song: Track = { title, duration: buffer.duration, waveform: peaks, analysis: message.result };
          const bpm = message.result.bpm;
          const generated = makeChart(message.result.onsets, bpm, buffer.duration, 'normal');
          trackRef.current = song;
          notesRef.current = generated;
          setTrack(song);
          setNotes(generated);
          setDifficulty('normal');
          setBpmInput(String(bpm));
          setAppliedBpm(bpm);
          setProgress(100);
          switchScreen('ready');
        }
      };
      worker.onerror = () => {
        if (job !== jobRef.current) return;
        worker.terminate();
        workerRef.current = null;
        setError('분석 작업이 중단됐어요. 브라우저 메모리를 확인하고 다시 시도해 주세요.');
        switchScreen('error');
      };
      worker.postMessage({ samples, sampleRate: ANALYSIS_RATE }, [samples.buffer]);
    } catch (caught) {
      if (job !== jobRef.current) return;
      setError(caught instanceof Error ? caught.message : '파일을 불러오지 못했어요. 다시 시도해 주세요.');
      switchScreen('error');
    }
  }, [stopSource, switchScreen]);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    void receiveFile(event.target.files?.[0]);
    event.target.value = '';
  };
  const onDrop = (event: DragEvent<HTMLElement>) => {
    event.preventDefault();
    void receiveFile(event.dataTransfer.files[0]);
  };
  const onUploadKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      fileInputRef.current?.click();
    }
  };

  const rebuildChart = useCallback((nextBpm: number, nextDifficulty: Difficulty) => {
    if (!trackRef.current) return;
    const bpm = Math.round(Math.max(60, Math.min(220, nextBpm)));
    const generated = makeChart(trackRef.current.analysis.onsets, bpm, trackRef.current.duration, nextDifficulty);
    notesRef.current = generated;
    setNotes(generated);
    setAppliedBpm(bpm);
    setBpmInput(String(bpm));
  }, []);

  const applyBpm = () => {
    const bpm = Number(bpmInput);
    if (!Number.isFinite(bpm) || bpm < 60 || bpm > 220) {
      setError('BPM은 60부터 220 사이의 숫자를 입력해 주세요.');
      return;
    }
    setError('');
    rebuildChart(bpm, difficulty);
  };

  const changeDifficulty = (next: Difficulty) => {
    setDifficulty(next);
    rebuildChart(appliedBpm, next);
  };

  const ratio = track ? Math.min(1, time / track.duration) : 0;
  const accuracyBase = screen === 'result' && completed ? notes.length : stats.judged;
  const accuracy = accuracyBase ? (stats.weighted / accuracyBase) * 100 : 100;
  const visibleNotes = notes.filter((note) => !judgedRef.current.has(note.id)
    && note.time >= time - JUDGMENT_WINDOWS.good - 0.05
    && note.time <= time + APPROACH_TIME + 0.25);
  const playingArea = screen === 'playing' || screen === 'paused';

  return <div className="app-shell">
    <div className="ambient ambient-one"/><div className="ambient ambient-two"/>
    <header className="site-header">
      <div className="brand" aria-label="네온 펄스">
        <span className="brand-mark"><span/><span/><span/><span/></span>
        <span>NEON<span className="brand-accent">PULSE</span><small>RHYTHM STUDIO</small></span>
      </div>
      <div className="header-right"><span className="status-dot"/> <span>LOCAL AUDIO ENGINE</span><span className="header-version">V1.0</span></div>
    </header>

    {!playingArea && screen !== 'result' && <main className="studio-main">
      <section className="studio-heading">
        <div className="eyebrow"><span className="eyebrow-line"/> YOUR MUSIC. YOUR GAME.</div>
        <h1>당신의 음악이<br/><em>게임이 되는 순간.</em></h1>
        <p>좋아하는 MP3를 불러오세요. 타격음과 박자를 브라우저에서 분석해<br className="desktop-break"/> 나만의 4레인 리듬 게임을 만듭니다.</p>
      </section>

      <div className="studio-grid">
        <div className="studio-primary">
          {(screen === 'idle' || screen === 'error') && <div className="panel upload-panel">
            <div className="panel-label"><span className="step-indicator">01</span> TRACK INPUT <span className="panel-decoration">MP3 / LOCAL</span></div>
            <div className="upload-zone" role="button" tabIndex={0} aria-label="MP3 파일 업로드: 클릭 또는 드래그 앤 드롭"
              onClick={() => fileInputRef.current?.click()} onKeyDown={onUploadKeyDown}
              onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
              <div className="upload-icon"><Icon name="upload" size={32}/></div>
              <strong>MP3 파일을 여기에 놓으세요</strong>
              <p>또는 눌러서 기기에 저장된 음악을 선택하세요</p>
              <span className="upload-cta">음악 파일 선택 <span>↗</span></span>
              <small>MP3 · 최대 35MB · 최대 12분</small>
            </div>
            {screen === 'error' && <div className="error-message" role="alert"><strong>파일을 처리하지 못했어요</strong><span>{error}</span></div>}
          </div>}

          {screen === 'analyzing' && <div className="panel analysis-panel" aria-live="polite">
            <div className="panel-label"><span className="step-indicator">02</span> AUDIO ANALYSIS <span className="panel-decoration">PROCESSING</span></div>
            <div className="analysis-animation"><div className="analysis-orbit"><Icon name="sound" size={38}/></div></div>
            <span className="analysis-kicker">AUDIO ENGINE ACTIVE</span>
            <h2>음악 속 리듬을 찾고 있어요</h2>
            <p>{progressMessage}</p>
            <div className="progress-number">{progress}<span>%</span></div>
            <div className="progress-track" role="progressbar" aria-label="음악 분석 진행률" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}><div style={{ width: `${progress}%` }}/></div>
            <p className="analysis-caption">분석에는 음악 길이와 기기 성능에 따라 시간이 걸릴 수 있어요.</p>
            <button className="button subtle" onClick={resetToUpload}>분석 취소</button>
          </div>}

          {screen === 'ready' && track && <div className="panel ready-panel">
            <div className="panel-label"><span className="step-indicator ready-check">✓</span> TRACK READY <span className="ready-status"><span className="status-dot"/> ANALYZED</span></div>
            <div className="track-header"><div className="track-art"><Icon name="music" size={38}/></div><div className="track-title"><span>NOW LOADED</span><h2 title={track.title}>{track.title}</h2><p>나만의 리듬 차트가 준비됐어요</p></div></div>
            <Waveform values={track.waveform}/>
            <div className="track-details"><Stat label="DURATION" value={formatTime(track.duration)}/><Stat label="EST. BPM" value={String(track.analysis.bpm)} detail="추정값"/><Stat label="NOTES" value={notes.length.toLocaleString('ko-KR')}/></div>
            <div className="configure-title">플레이 설정 <span>PLAY CONFIGURATION</span></div>
            <div className="config-row">
              <div className="field-group"><label htmlFor="difficulty">난이도</label><select id="difficulty" value={difficulty} onChange={(e) => changeDifficulty(e.target.value as Difficulty)}><option value="easy">EASY · 입문</option><option value="normal">NORMAL · 기본</option><option value="hard">HARD · 도전</option></select></div>
              <div className="field-group"><label htmlFor="bpm">BPM 조정 (60–220)</label><div className="bpm-control"><input id="bpm" type="number" inputMode="numeric" min={60} max={220} value={bpmInput} onChange={(e) => setBpmInput(e.target.value)}/><button className="button compact secondary" onClick={applyBpm}>차트 재생성</button></div></div>
            </div>
            {error && <div className="inline-error" role="alert">{error}</div>}
            <div className="track-warning"><Icon name="spark" size={17}/><span>{track.analysis.confidence < 0.38 || notes.length < track.duration * 0.8 ? '리듬 신뢰도가 낮거나 검출된 타격음이 적어요. BPM을 바꾸어 차트를 다시 생성해 보세요.' : '온셋 검출 기반 자동 채보예요. 실제 악기별 정확한 채보나 박자 일치를 보장하지는 않아요.'}</span></div>
            <button className="button primary start-button" disabled={notes.length === 0} onClick={() => void startPlayback(true)}><Icon name="play"/> 게임 시작 <span>LET'S PLAY ↗</span></button>
            <button className="button quiet change-track" onClick={resetToUpload}>다른 음악 선택</button>
          </div>}
        </div>

        <aside className="studio-aside">
          <div className="panel guide-panel"><div className="panel-label">QUICK GUIDE <span className="panel-decoration">HOW TO PLAY</span></div><h3>4개의 레인, 하나의 비트.</h3><p>노트가 아래 판정선에 닿는 순간 같은 레인의 키를 누르세요.</p><div className="guide-keys">{KEYS.map((key, i) => <div key={key} className={`guide-key lane-color-${i}`}><kbd>{key}</kbd><span>LANE 0{i + 1}</span></div>)}</div><div className="guide-tip"><span className="tip-dot"/> 키보드 또는 화면 하단 터치 버튼 사용 가능</div></div>
          <div className="panel privacy-panel"><div className="privacy-icon"><Icon name="shield"/></div><div><strong>음악은 기기 밖으로 나가지 않아요</strong><p>업로드한 MP3는 브라우저 메모리에서만 디코딩·분석·재생됩니다. 서버 전송이나 저장 기능은 없습니다.</p></div></div>
          <div className="engine-info"><span>ENGINE / FFT + SPECTRAL FLUX</span><span>WEB AUDIO API <span className="engine-light">●</span></span></div>
        </aside>
      </div>
    </main>}

    {playingArea && track && <main className="game-main">
      <div className="game-topbar"><div><span className="game-kicker">NOW PLAYING <span className="live-dot"/></span><h2 title={track.title}>{track.title}</h2></div><div className="game-controls"><button className="button secondary" onClick={screen === 'paused' ? resumeGame : pauseGame}><Icon name={screen === 'paused' ? 'play' : 'pause'} size={17}/>{screen === 'paused' ? '계속하기' : '일시정지'}</button><button className="button subtle" onClick={() => finishGame(false)}><Icon name="exit" size={17}/> 종료</button></div></div>
      <div className="game-timeline"><div className="game-progress"><div style={{ width: `${ratio * 100}%` }}/></div><div className="game-times"><span>{formatTime(time)}</span><span>{formatTime(track.duration)}</span></div></div>
      <div className="game-grid"><div className="playfield-wrapper"><div className="playfield" role="group" aria-label="4레인 리듬 게임 영역">
        <div className="board-glow"/>
        {LANES.map((lane) => <div key={lane} className={`board-lane board-lane-${lane}${pulsing.includes(lane) ? ' pressed' : ''}`} style={{ left: `${lane * 25}%` }}><span className="lane-heading">0{lane + 1}</span></div>)}
        <div className="hit-line" style={{ top: `${HIT_LINE_PERCENT}%` }}><span/><span/><span/><span/></div>
        {visibleNotes.map((note) => <div key={note.id} className={`falling-note note-lane-${note.lane}`} style={{ left: `${(note.lane + 0.5) * 25}%`, top: `${HIT_LINE_PERCENT - ((note.time - time) / APPROACH_TIME) * TRAVEL_PERCENT}%` }}/>) }
        <div className="center-combo" aria-live="off">{stats.combo > 1 && <><strong>{stats.combo}</strong><span>COMBO</span></>}</div>
        {feedback && <div key={feedback.id} className={`judgment-popup judge-${feedback.tone}`} style={{ top: `${HIT_LINE_PERCENT - 19}%` }}>{feedback.label}</div>}
        {screen === 'paused' && <div className="pause-overlay"><div className="pause-symbol"><Icon name="pause" size={32}/></div><span>GAME PAUSED</span><h2>잠깐 쉬어가요.</h2><p>음악과 노트가 함께 멈췄어요.</p><button className="button primary" onClick={resumeGame}><Icon name="play"/> 계속 플레이</button></div>}
      </div><div className="touch-keys">{LANES.map((lane) => <button key={lane} type="button" className={`touch-key touch-key-${lane}${pulsing.includes(lane) ? ' pressed' : ''}`} aria-label={`${KEYS[lane]} 레인 터치 판정`} onPointerDown={(event) => { if (event.pointerType !== 'mouse' || event.button === 0) hitLane(lane); }} onClick={(event) => { if (event.detail === 0) hitLane(lane); }} disabled={screen === 'paused'}><span>{KEYS[lane]}</span></button>)}</div><div className="playfield-note"><Icon name="headphones" size={14}/> 유선 이어폰 사용 시 지연을 줄일 수 있어요 · ESC로 일시정지</div></div>
      <aside className="game-sidebar"><div className="panel score-panel"><span className="game-stat-label">CURRENT SCORE</span><strong className="game-score">{stats.score.toLocaleString('ko-KR')}</strong><div className="score-separator"/><div className="score-mini-grid"><div><span>ACCURACY</span><strong>{accuracy.toFixed(1)}%</strong></div><div><span>MAX COMBO</span><strong>{stats.maxCombo}</strong></div></div></div><div className="panel judgment-panel"><div className="panel-label">LIVE JUDGMENT</div>{(['perfect', 'great', 'good', 'miss'] as Judgment[]).map((judgment) => <div className={`judgment-row judge-text-${judgment}`} key={judgment}><span>{LABELS[judgment]}</span><strong>{stats.counts[judgment]}</strong></div>)}</div><div className="game-hint"><div className="game-hint-pill">{appliedBpm} BPM</div><div className="game-hint-pill">{difficulty.toUpperCase()}</div><p>정확한 타이밍으로 더 높은 점수를 획득하세요.</p></div></aside></div>
    </main>}

    {screen === 'result' && track && <main className="result-main"><div className="result-eyebrow"><Icon name="spark" size={18}/> SESSION COMPLETE</div><h1>{completed ? '플레이 완료!' : '플레이 종료'}</h1><p className="result-subtitle">{track.title}</p><div className="panel result-panel"><span className="result-score-label">FINAL SCORE</span><strong className="result-score">{stats.score.toLocaleString('ko-KR')}</strong><div className="result-metrics"><Stat label="정확도" value={`${accuracy.toFixed(1)}%`}/><Stat label="최대 콤보" value={String(stats.maxCombo)}/><Stat label="판정한 노트" value={`${stats.judged} / ${notes.length}`}/></div><div className="result-judgments">{(['perfect', 'great', 'good', 'miss'] as Judgment[]).map((judgment) => <div className={`result-judgment judge-text-${judgment}`} key={judgment}><span>{LABELS[judgment]}</span><strong>{stats.counts[judgment]}</strong></div>)}</div>{!completed && <p className="result-notice">중도 종료한 플레이입니다. 정확도는 판정한 노트만 기준으로 계산했습니다.</p>}<div className="result-actions"><button className="button primary" onClick={() => void startPlayback(true)}><Icon name="restart"/> 재도전</button><button className="button secondary" onClick={resetToUpload}><Icon name="upload"/> 새 곡 선택</button></div></div></main>}

    <input ref={fileInputRef} type="file" accept=".mp3,audio/mpeg" className="visually-hidden" onChange={onFileChange} aria-label="MP3 파일 선택" />
    <footer className="site-footer"><span>© NEON PULSE · AUDIO STAYS ON YOUR DEVICE</span><span>MADE FOR THE BEAT, NOT THE UPLOAD.</span></footer>
  </div>;
}
