import type { Difficulty, Lane, Note, Onset } from '../types';

const SETTINGS: Record<Difficulty, { density: number; gap: number; chords: boolean }> = {
  easy: { density: 1.7, gap: 0.24, chords: false },
  normal: { density: 3.2, gap: 0.135, chords: true },
  hard: { density: 4.4, gap: 0.09, chords: true },
};

interface ScoredOnset extends Onset { rank: number }

export function makeChart(onsets: Onset[], bpm: number, duration: number, difficulty: Difficulty): Note[] {
  const settings = SETTINGS[difficulty];
  const interval = 60 / Math.max(60, bpm);
  const subdivisions = interval / (difficulty === 'easy' ? 2 : 4);
  const valid = onsets.filter((o) => o.time >= 0.12 && o.time < duration - 0.08);
  if (!valid.length) return [];

  // Strong peaks define an approximate beat phase; timestamps stay at actual detected onsets.
  const strongest = [...valid].sort((a, b) => b.strength - a.strength).slice(0, 150);
  const buckets = new Float64Array(32);
  for (const onset of strongest) {
    const phase = ((onset.time % interval) + interval) % interval;
    buckets[Math.floor((phase / interval) * 32) % 32] += Math.min(8, onset.strength);
  }
  let bestBucket = 0;
  for (let i = 1; i < buckets.length; i++) if (buckets[i] > buckets[bestBucket]) bestBucket = i;
  const phase = ((bestBucket + 0.5) / buckets.length) * interval;

  const scored: ScoredOnset[] = valid.map((o) => {
    const gridDistance = Math.abs(((o.time - phase + subdivisions / 2) % subdivisions + subdivisions) % subdivisions - subdivisions / 2);
    const proximity = Math.max(0, 1 - gridDistance / Math.min(0.09, subdivisions / 2));
    return { ...o, rank: Math.log1p(o.strength) * (1 + proximity * 0.3) };
  });
  scored.sort((a, b) => b.rank - a.rank);

  const maxEvents = Math.min(scored.length, Math.ceil(duration * settings.density));
  const gap = Math.max(settings.gap, interval * (difficulty === 'easy' ? 0.27 : 0.13));
  const accepted: ScoredOnset[] = [];
  for (const item of scored) {
    if (accepted.length >= maxEvents) break;
    if (accepted.some((other) => Math.abs(other.time - item.time) < gap)) continue;
    accepted.push(item);
  }
  accepted.sort((a, b) => a.time - b.time);

  const notes: Note[] = [];
  const laneUsage = [0, 0, 0, 0];
  let previousLane = -1;
  let previousTime = -10;
  let id = 0;

  for (const [index, onset] of accepted.entries()) {
    // Timbre influences preferred side, and lane balancing ensures all four lanes are used.
    const mainBand = onset.bass > onset.mid && onset.bass > onset.high ? 0
      : onset.high > onset.mid ? 3 : 2;
    const preferred = (mainBand + (index % 3 === 0 ? 1 : 0)) % 4;
    const options = [0, 1, 2, 3].sort((a, b) => {
      const cost = (lane: number) => {
        const similarity = Math.min(Math.abs(lane - preferred), 4 - Math.abs(lane - preferred));
        const repeatPenalty = lane === previousLane && onset.time - previousTime < 0.38 ? 1.7 : 0;
        return laneUsage[lane] * 0.9 + similarity * 0.82 + repeatPenalty;
      };
      return cost(a) - cost(b);
    });
    const lane = options[0] as Lane;
    notes.push({ id: id++, time: onset.time, lane });
    laneUsage[lane]++;
    previousLane = lane;
    previousTime = onset.time;

    const diverseBands = Math.min(onset.bass, onset.high) > 0.17;
    const chordProbability = difficulty === 'hard' ? 0.36 : 0.2;
    const chordSignature = ((index * 37 + Math.round(onset.time * 100)) % 100) / 100;
    if (settings.chords && diverseBands && chordSignature < chordProbability && onset.strength > 0.5) {
      const opposite = ([0, 1, 2, 3] as Lane[])
        .filter((candidate) => candidate !== lane && Math.abs(candidate - lane) >= 2)
        .sort((a, b) => laneUsage[a] - laneUsage[b])[0];
      if (opposite !== undefined) {
        notes.push({ id: id++, time: onset.time, lane: opposite });
        laneUsage[opposite]++;
      }
    }
  }

  return notes.sort((a, b) => a.time - b.time || a.lane - b.lane);
}
