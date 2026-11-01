export type Screen = 'idle' | 'analyzing' | 'ready' | 'playing' | 'paused' | 'result' | 'error';
export type Difficulty = 'easy' | 'normal' | 'hard';
export type Judgment = 'perfect' | 'great' | 'good' | 'miss';
export type Lane = 0 | 1 | 2 | 3;

export interface Onset {
  time: number;
  strength: number;
  bass: number;
  mid: number;
  high: number;
}

export interface Note {
  id: number;
  time: number;
  lane: Lane;
}

export interface AnalysisResult {
  bpm: number;
  confidence: number;
  onsets: Onset[];
}

export type WorkerMessage =
  | { type: 'progress'; progress: number; message: string }
  | { type: 'done'; result: AnalysisResult }
  | { type: 'error'; message: string };

export interface ScoreState {
  score: number;
  combo: number;
  maxCombo: number;
  judged: number;
  weighted: number;
  counts: Record<Judgment, number>;
}

export function emptyScore(): ScoreState {
  return {
    score: 0, combo: 0, maxCombo: 0, judged: 0, weighted: 0,
    counts: { perfect: 0, great: 0, good: 0, miss: 0 },
  };
}
