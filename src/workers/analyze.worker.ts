/// <reference lib="webworker" />
import type { AnalysisResult, Onset, WorkerMessage } from '../types';

declare const self: DedicatedWorkerGlobalScope;

const FFT_SIZE = 1024;
const HOP = 256;
const EPS = 1e-9;

function send(message: WorkerMessage): void {
  self.postMessage(message);
}

function fft(re: Float32Array, im: Float32Array): void {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    while (j & bit) { j ^= bit; bit >>= 1; }
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let length = 2; length <= n; length *= 2) {
    const angle = -2 * Math.PI / length;
    const wr = Math.cos(angle);
    const wi = Math.sin(angle);
    for (let start = 0; start < n; start += length) {
      let cos = 1, sin = 0;
      for (let j = 0; j < length / 2; j++) {
        const even = start + j;
        const odd = even + length / 2;
        const tr = cos * re[odd] - sin * im[odd];
        const ti = cos * im[odd] + sin * re[odd];
        re[odd] = re[even] - tr;
        im[odd] = im[even] - ti;
        re[even] += tr;
        im[even] += ti;
        const nextCos = cos * wr - sin * wi;
        sin = cos * wi + sin * wr;
        cos = nextCos;
      }
    }
  }
}

function analyze(samples: Float32Array, sampleRate: number): AnalysisResult {
  if (samples.length < FFT_SIZE * 2) throw new Error('음원이 너무 짧아 리듬을 분석할 수 없어요.');
  const frameCount = Math.floor((samples.length - FFT_SIZE) / HOP) + 1;
  const frameSec = HOP / sampleRate;
  const raw = new Float32Array(frameCount);
  const bass = new Float32Array(frameCount);
  const mid = new Float32Array(frameCount);
  const high = new Float32Array(frameCount);
  const rms = new Float32Array(frameCount);
  const strength = new Float32Array(frameCount);
  const previousSpectrum = new Float32Array(FFT_SIZE / 2);
  const window = Float32Array.from({ length: FFT_SIZE }, (_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (FFT_SIZE - 1)));
  const re = new Float32Array(FFT_SIZE);
  const im = new Float32Array(FFT_SIZE);
  let lastProgress = -1;

  for (let frame = 0; frame < frameCount; frame++) {
    const begin = frame * HOP;
    let power = 0;
    for (let i = 0; i < FFT_SIZE; i++) {
      const sample = samples[begin + i];
      power += sample * sample;
      re[i] = sample * window[i];
      im[i] = 0;
    }
    rms[frame] = Math.sqrt(power / FFT_SIZE);
    fft(re, im);

    let b = 0, m = 0, h = 0;
    for (let bin = 3; bin < FFT_SIZE / 2; bin++) {
      const magnitude = Math.hypot(re[bin], im[bin]);
      const positive = Math.max(0, magnitude - previousSpectrum[bin]);
      const hz = (bin * sampleRate) / FFT_SIZE;
      if (hz < 220) b += positive;
      else if (hz < 1800) m += positive;
      else if (hz < 5100) h += positive;
      previousSpectrum[bin] = magnitude;
    }
    // Band-weighting prevents the numerous treble bins from always dominating.
    bass[frame] = b / 17;
    mid[frame] = m / 146;
    high[frame] = h / 307;
    raw[frame] = 0.45 * Math.sqrt(bass[frame])
      + 0.38 * Math.sqrt(mid[frame]) + 0.17 * Math.sqrt(high[frame]);

    const progress = 35 + Math.floor(((frame + 1) / frameCount) * 42);
    if (progress !== lastProgress) {
      lastProgress = progress;
      send({ type: 'progress', progress, message: '주파수 변화와 타격음을 찾고 있어요' });
    }
  }

  send({ type: 'progress', progress: 79, message: '음악의 박자 간격을 추정하고 있어요' });
  const prefix = new Float64Array(frameCount + 1);
  for (let i = 0; i < frameCount; i++) prefix[i + 1] = prefix[i] + raw[i];
  const windowRadius = Math.max(8, Math.round(0.7 / frameSec));
  let totalRms = 0;
  for (let i = 0; i < frameCount; i++) totalRms += rms[i];
  const averageRms = totalRms / frameCount;

  for (let i = 0; i < frameCount; i++) {
    const from = Math.max(0, i - windowRadius);
    const to = Math.min(frameCount, i + windowRadius);
    const localMean = (prefix[to] - prefix[from]) / (to - from);
    const normalized = raw[i] / (localMean + 0.0001);
    const rmsRise = i > 0 ? Math.max(0, rms[i] - rms[i - 1]) / (averageRms + EPS) : 0;
    strength[i] = rms[i] > Math.max(0.00035, averageRms * 0.055)
      ? Math.min(12, Math.max(0, normalized - 0.76) + Math.min(1.3, rmsRise * 1.6))
      : 0;
  }

  const onsetCandidates: Onset[] = [];
  let lastOnset = -10;
  for (let i = 2; i < frameCount - 2; i++) {
    const current = strength[i];
    if (current < 0.23 || current <= strength[i - 1] || current < strength[i + 1]
      || current < strength[i - 2] || current < strength[i + 2]) continue;
    const time = Math.max(0, (i * HOP + FFT_SIZE / 2) / sampleRate);
    if (time - lastOnset < 0.071) {
      if (onsetCandidates.length && current > onsetCandidates[onsetCandidates.length - 1].strength) {
        onsetCandidates.pop();
      } else continue;
    }
    const sum = bass[i] + mid[i] + high[i] + EPS;
    onsetCandidates.push({
      time,
      strength: current,
      bass: bass[i] / sum,
      mid: mid[i] / sum,
      high: high[i] / sum,
    });
    lastOnset = time;
  }

  // Tempo by autocorrelation of the measured onset envelope. Half/double tempo remains ambiguous.
  const tempoScores: { bpm: number; score: number }[] = [];
  for (let bpm = 65; bpm <= 195; bpm++) {
    const lag = Math.round((60 / bpm) / frameSec);
    let correlation = 0;
    for (let i = lag; i < frameCount; i += 2) {
      correlation += Math.min(5, strength[i]) * Math.min(5, strength[i - lag]);
    }
    tempoScores.push({ bpm, score: correlation / Math.max(1, frameCount - lag) });
  }
  tempoScores.sort((a, b) => b.score - a.score);
  const winner = tempoScores[0];
  // Refine the coarse FFT-hop tempo with intervals between high-confidence attacks.
  // This reduces a few BPM of discretization error without inventing new onsets.
  const rankedStrengths = onsetCandidates.map((o) => o.strength).sort((a, b) => a - b);
  const cutoff = rankedStrengths[Math.floor(rankedStrengths.length * 0.7)] ?? Infinity;
  const strongOnsets = onsetCandidates.filter((o) => o.strength >= cutoff);
  const period = 60 / winner.bpm;
  const measuredPeriods: number[] = [];
  for (let i = 1; i < strongOnsets.length; i++) {
    const difference = strongOnsets[i].time - strongOnsets[i - 1].time;
    const multiples = Math.round(difference / period);
    if (multiples < 1 || multiples > 4) continue;
    const measured = difference / multiples;
    if (Math.abs(measured - period) < period * 0.12) measuredPeriods.push(measured);
  }
  measuredPeriods.sort((a, b) => a - b);
  const refinedBpm = measuredPeriods.length >= 5
    ? Math.round(60 / measuredPeriods[Math.floor(measuredPeriods.length / 2)])
    : winner.bpm;
  const alternatives = tempoScores.filter((t) => Math.abs(t.bpm - winner.bpm) > 4);
  const competitor = alternatives[0]?.score ?? 0;
  const relative = winner.score / (competitor + EPS);
  const rhythmCount = onsetCandidates.length / (samples.length / sampleRate);
  const confidence = Math.max(0.05, Math.min(0.95,
    (relative - 0.9) * 1.7 + Math.min(0.45, rhythmCount / 12),
  ));

  send({ type: 'progress', progress: 94, message: '검출한 리듬으로 채보를 준비하고 있어요' });
  return {
    bpm: Number.isFinite(refinedBpm) ? refinedBpm : 120,
    confidence,
    onsets: onsetCandidates,
  };
}

self.onmessage = (event: MessageEvent<{ samples: Float32Array; sampleRate: number }>) => {
  try {
    send({ type: 'progress', progress: 35, message: '음원의 주파수 성분을 분석하고 있어요' });
    const result = analyze(event.data.samples, event.data.sampleRate);
    send({ type: 'done', result });
  } catch (error) {
    send({ type: 'error', message: error instanceof Error ? error.message : '음악 분석 중 문제가 발생했어요.' });
  }
};
