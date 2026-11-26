# 用法: python mix.py <id> [video.mp4] [final.mp4] —— 旁白 + 合成 BGM（旁白时自动压低）→ 与视频合成
import json, sys, os, subprocess, numpy as np
ID = sys.argv[1]; ROOT = os.path.expanduser('~/gdemo'); FF = os.path.expanduser('~/tools/vid/ffmpeg'); OUT = f'{ROOT}/out/{ID}'
plan = json.load(open(f'{OUT}/plan.json')); SR = 48000; N = int((plan['total'] + 0.5) * SR)
vo = np.zeros(N, np.float32); talk = np.zeros(N, np.float32)
for sc in plan['scenes']:
    for L in sc['lines']:
        a = np.frombuffer(open(L['wav'], 'rb').read()[44:], np.int16).astype(np.float32) / 32768
        i = int(L['start'] * SR); a = a[: max(0, min(len(a), N - i))]; vo[i:i + len(a)] += a; talk[i:i + len(a)] = 1
# 旁白占用包络（平滑），用于压低 BGM
k = int(0.25 * SR); env = np.convolve(talk, np.ones(k) / k, 'same'); env = np.clip(env * 1.6, 0, 1)
t = np.arange(N) / SR; rs = np.random.RandomState(7)
def note(f): return 440 * 2 ** ((f - 69) / 12)
def adsr(n, a=0.01, d=0.3):
    e = np.exp(-np.arange(n) / (d * SR)); ai = int(a * SR); e[:ai] *= np.linspace(0, 1, ai); return e
def pad(chords, beat, voices=3, amp=0.05):
    y = np.zeros(N, np.float32); L = int(beat * SR)
    for j in range(0, N, L):
        ch = chords[(j // L) % len(chords)]; n = min(L + SR, N - j); tt = np.arange(n) / SR
        e = np.minimum(1, tt / 1.2) * np.exp(-np.maximum(0, tt - beat) * 2.5)
        for m in ch[:voices]:
            f = note(m); y[j:j + n] += amp * e * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 1.004 * tt + 1) + 0.15 * np.sin(2 * np.pi * 2 * f * tt))
    return y
def plucks(scale, bpm, amp=0.06, seed=3, density=0.6, octave=72):
    r = np.random.RandomState(seed); y = np.zeros(N, np.float32); step = 60 / bpm / 2; L = int(step * SR)
    for j in range(0, N, L):
        if r.rand() > density: continue
        f = note(octave + scale[r.randint(len(scale))]); n = min(int(0.6 * SR), N - j); tt = np.arange(n) / SR
        y[j:j + n] += amp * np.exp(-tt * 7) * (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt))
    return y
def pulse(bpm, f0=41, amp=0.08):
    y = np.zeros(N, np.float32); L = int(60 / bpm / 2 * SR)
    for c, j in enumerate(range(0, N, L)):
        n = min(int(0.22 * SR), N - j); tt = np.arange(n) / SR; f = note(f0 + (0 if (c // 8) % 2 == 0 else -2))
        y[j:j + n] += amp * np.exp(-tt * 14) * np.tanh(3 * np.sin(2 * np.pi * f * tt))
        if c % 2 == 1:  # 滴答
            m = min(int(0.03 * SR), N - j); y[j:j + m] += 0.03 * rs.randn(m) * np.exp(-np.arange(m) / 200)
    return y
style = plan.get('bgm', 'eerie')
if style == 'eerie':   # 观测者：低沉、悬疑
    bgm = pad([[45, 52, 60], [43, 50, 58], [41, 48, 57], [40, 47, 55]], 4.0, amp=0.055) + plucks([0, 3, 7, 10, 12], 70, 0.025, density=0.35, octave=69)
elif style == 'island':  # 借尸还魂：岛屿、诡秘
    bgm = pad([[50, 57, 62], [48, 55, 60], [46, 53, 58], [45, 52, 57]], 3.2, amp=0.045) + plucks([0, 2, 5, 7, 9], 96, 0.05, density=0.55, octave=67)
elif style == 'upbeat':  # 爽文：明快、大调、轻节拍
    bgm = pad([[48, 55, 64], [45, 52, 60], [41, 48, 57], [43, 50, 59]], 2.2, amp=0.04) + plucks([0, 2, 4, 7, 9, 12], 112, 0.05, density=0.7, octave=72) + pulse(112, f0=36, amp=0.045)
elif style == 'city':  # 烟火之城：温暖、轻松的城市生活感
    bgm = pad([[48, 52, 55, 59], [45, 48, 52, 55], [41, 45, 48, 52], [43, 47, 50, 53]], 2.5, voices=4, amp=0.032) + plucks([0, 2, 4, 7, 9, 12], 96, 0.042, seed=11, density=0.5, octave=72) + plucks([0, 4, 7], 48, 0.03, seed=5, density=0.8, octave=48) + pulse(96, f0=36, amp=0.022)
else:  # 时停公约：紧张脉冲
    bgm = pad([[40, 47, 52], [40, 46, 52], [38, 45, 50], [39, 46, 51]], 4.0, amp=0.04) + pulse(118)
bgm = bgm.astype(np.float32); bgm *= (1 - 0.62 * env)
sfxp = f'{OUT}/sfx.json'
if os.path.exists(sfxp):
    import wave as _w
    for e in json.load(open(sfxp)):
        w = _w.open(e['wav']); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; w.close()
        n = min(len(a), int(e['dur'] * SR)); a = a[:n].copy(); f = int(0.25 * SR); a[:f] *= np.linspace(0, 1, f)[:len(a[:f])]; a[-f:] *= np.linspace(1, 0, f)[-len(a[-f:]):]
        i = int(e['start'] * SR); n = min(n, N - i); bgm[i:i + n] += a[:n] * e['gain'] * (1 - 0.5 * env[i:i + n])
fade = np.minimum(1, t / 1.5) * np.minimum(1, (plan['total'] - t) / 2.0).clip(0, 1)
mix = vo * 1.0 + bgm * fade; mix /= max(1.0, np.abs(mix).max() / 0.95)
wav = f'{OUT}/mix.wav'
with open(wav, 'wb') as f:
    import wave; w = wave.open(f, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes()); w.close()
vid = sys.argv[2] if len(sys.argv) > 2 else f'{OUT}/video.mp4'; fin = sys.argv[3] if len(sys.argv) > 3 else f'{OUT}/final.mp4'
subprocess.run([FF, '-v', 'error', '-y', '-i', vid, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest', '-movflags', '+faststart', fin], check=True)
print('final ->', fin)
