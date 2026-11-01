export const MAX_FILE_BYTES = 35 * 1024 * 1024;
export const MAX_DURATION = 12 * 60;
export const ANALYSIS_RATE = 11025;

export function makeAudioContext(): AudioContext {
  const win = window as Window & { webkitAudioContext?: typeof AudioContext };
  const Constructor = globalThis.AudioContext ?? win.webkitAudioContext;
  if (!Constructor) throw new Error('이 브라우저는 Web Audio API를 지원하지 않아요. 최신 Chrome 또는 Safari에서 실행해 주세요.');
  return new Constructor();
}

export function validateMp3(file: File): void {
  const mp3Name = /\.mp3$/i.test(file.name);
  const mp3Type = ['audio/mpeg', 'audio/mp3', 'audio/x-mp3', 'audio/mpeg3'].includes(file.type);
  if (!mp3Name && !mp3Type) throw new Error('MP3 파일만 업로드할 수 있어요. 확장자가 .mp3인 파일을 선택해 주세요.');
  if (file.size === 0) throw new Error('파일이 비어 있어요. 다른 MP3를 선택해 주세요.');
  if (file.size > MAX_FILE_BYTES) throw new Error('파일은 최대 35MB까지 지원해요. 더 작은 MP3로 다시 시도해 주세요.');
}

export function formatTime(seconds: number): string {
  const time = Math.max(0, Math.floor(seconds));
  return `${Math.floor(time / 60)}:${String(time % 60).padStart(2, '0')}`;
}

export function waveformPeaks(buffer: AudioBuffer, count = 100): number[] {
  const channels = Array.from({ length: buffer.numberOfChannels }, (_, i) => buffer.getChannelData(i));
  const chunk = Math.max(1, Math.floor(buffer.length / count));
  const peaks: number[] = [];
  for (let i = 0; i < count; i++) {
    const start = i * chunk;
    const end = Math.min(buffer.length, start + chunk);
    let peak = 0;
    const step = Math.max(1, Math.floor((end - start) / 220));
    for (let j = start; j < end; j += step) {
      for (const channel of channels) peak = Math.max(peak, Math.abs(channel[j]));
    }
    peaks.push(peak);
  }
  const peakMax = Math.max(...peaks, 0.001);
  return peaks.map((peak) => Math.max(0.1, Math.pow(peak / peakMax, 0.6)));
}

export async function downmixForAnalysis(
  buffer: AudioBuffer,
  onProgress: (progress: number) => void,
): Promise<Float32Array> {
  const channels = Array.from({ length: buffer.numberOfChannels }, (_, i) => buffer.getChannelData(i));
  const ratio = buffer.sampleRate / ANALYSIS_RATE;
  const output = new Float32Array(Math.ceil(buffer.length / ratio));
  const batch = 50000;

  for (let start = 0; start < output.length; start += batch) {
    const end = Math.min(output.length, start + batch);
    for (let i = start; i < end; i++) {
      const from = Math.floor(i * ratio);
      const to = Math.min(buffer.length, Math.max(from + 1, Math.floor((i + 1) * ratio)));
      let sum = 0;
      for (let j = from; j < to; j++) {
        for (const channel of channels) sum += channel[j];
      }
      output[i] = sum / ((to - from) * channels.length);
    }
    onProgress(22 + Math.round((end / output.length) * 10));
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
  }
  return output;
}
