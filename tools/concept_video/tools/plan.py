# 用法: python plan.py <id>  —— TTS 每句旁白（缓存），排时间线，写 out/<id>/plan.json
import json, sys, os, hashlib, subprocess, struct
ID = sys.argv[1]; ROOT = os.path.expanduser('~/gdemo'); FF = os.path.expanduser('~/tools/vid/ffmpeg')
S = json.load(open(f'{ROOT}/scripts/{ID}.json')); OUT = f'{ROOT}/out/{ID}'; os.makedirs(f'{OUT}/a', exist_ok=True)
voice, rate = S.get('voice', 'zh-CN-YunxiNeural'), S.get('rate', '+5%'); FPS = S.get('fps', 30)
def tts(text, v=None, ctx=''):
    v = v or voice
    if v.startswith('doubao:'):
        h = hashlib.md5(f'{v}|{text}|{ctx}'.encode()).hexdigest()[:12]; wav = f'{OUT}/a/{h}.wav'
        if not os.path.exists(wav): raise SystemExit('missing doubao tts, run tools/doubao_tts.py: ' + text)
        n = (os.path.getsize(wav) - 44) // 2; return wav, n / 48000
    h = hashlib.md5(f'{v}|{rate}|{text}'.encode()).hexdigest()[:12]; wav = f'{OUT}/a/{h}.wav'
    if not os.path.exists(wav):
        mp3 = wav[:-4] + '.mp3'
        for k in range(4):
            r = subprocess.run([os.path.expanduser('~/tools/vid/bin/edge-tts'), '--proxy', os.environ['HTTPS_PROXY'], '-v', v, f'--rate={rate}', '-t', text, '--write-media', mp3], capture_output=True, timeout=90)
            if r.returncode == 0 and os.path.getsize(mp3) > 1000: break
        else: raise SystemExit('TTS failed: ' + text)
        subprocess.run([FF, '-v', 'error', '-y', '-i', mp3, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', wav], check=True)
    n = (os.path.getsize(wav) - 44) // 2
    return wav, n / 48000
t = 0.0; scenes = []
for sc in S['scenes']:
    lead, tail, gap = sc.get('lead', 0.45), sc.get('tail', 0.7), sc.get('gap', 0.32)
    s = {k: v for k, v in sc.items() if k != 'lines'}; s['start'] = round(t, 4); s['lines'] = []
    lt = t + lead
    for i, L in enumerate(sc.get('lines', [])):
        if isinstance(L, str): L = {'text': L}
        lt += L.get('pre', 0)
        wav, d = tts(L['text'], L.get('voice'), L.get('ctx', '')); d_trim = d - (0.12 if not (L.get('voice') or voice).startswith('doubao:') else 0.0)  # edge 末尾自带少量静音
        s['lines'].append({'text': L['text'], 'start': round(lt, 4), 'dur': round(d_trim, 4), 'wav': wav, 'who': L.get('voice', '')})
        lt += d_trim + gap
    end = (lt - gap + tail) if s['lines'] else t
    dur = max(end - t, sc.get('min', 0)); dur = round(dur * FPS) / FPS
    s['dur'] = dur; t += dur; scenes.append(s)
plan = {'id': ID, 'title': S['title'], 'fps': FPS, 'aa': S.get('aa', False), 'sub': S.get('sub'), 'total': round(t, 4), 'bgm': S.get('bgm', 'eerie'), 'scenes': scenes}
json.dump(plan, open(f'{OUT}/plan.json', 'w'), ensure_ascii=False, indent=1)
print(f'{ID}: {len(scenes)} scenes, {sum(len(s["lines"]) for s in scenes)} lines, total {t:.1f}s')
for s in scenes: print(f'  {s["start"]:7.2f} +{s["dur"]:6.2f}  {s["scene"]}')
