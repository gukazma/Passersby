"""《我亦是行人》A1.3 讲解+演示视频合成（在 114 上跑）。
    python build_video.py <workdir> <out.mp4>
workdir: script.json, tts/*.mp3, stills/*.png, clips/*.avi, bgm/*.ogg"""
import json, os, re, shutil, subprocess, sys
W, OUT = sys.argv[1], sys.argv[2]
FF = shutil.which('ffmpeg'); FP = shutil.which('ffprobe') or FF.replace('ffmpeg', 'ffprobe')
FONT = 'C\\:/Windows/Fonts/msyhbd.ttc'
S = json.load(open(os.path.join(W, 'script.json'), encoding='utf-8'))
seg_dir = os.path.join(W, 'seg'); os.makedirs(seg_dir, exist_ok=True)
def dur_of(f):
    r = subprocess.run([FP, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True)
    return float(r.stdout.strip())
def chunks(text):
    parts = [p for p in re.split(r'(?<=[，。；：！？、])', text) if p.strip()]
    out, cur = [], ''
    for p in parts:
        if len(cur) + len(p) > 24 and cur:
            out.append(cur); cur = p
        else:
            cur += p
    if cur: out.append(cur)
    return [c.rstrip('，、；') for c in out]
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-1500:]); sys.exit(1)
segs = []
# 封面 3 秒
cover = os.path.join(seg_dir, 's00.mp4')
run([FF, '-y', '-loglevel', 'error', '-loop', '1', '-t', '3', '-i', os.path.join(W, 'stills', 'cover.png'), '-i', os.path.join(W, 'bgm', 'yongan_day.ogg'),
     '-filter_complex', '[0]fps=25,format=yuv420p[v];[1]atrim=0:3,afade=t=in:d=1,volume=0.5,aresample=48000[a]', '-map', '[v]', '-map', '[a]',
     '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-t', '3', cover])
segs.append(cover)
bgm_off = 3.0
for s in S:
    tts = os.path.join(W, 'tts', s['id'] + '.mp3'); nd = dur_of(tts)
    D = max(s.get('dur', 0), nd + 0.9)
    kind, *rest = s['vis'].split(':')
    inputs, vf = [], ''
    if kind == 'clip':
        clip, st = rest[0], float(rest[1])
        cf = os.path.join(W, 'clips', clip + '.avi'); cd = dur_of(cf)
        inputs = ['-ss', str(st), '-i', cf]
        pad = max(0.0, D - (cd - st))
        vf = f'[0:v]fps=25,scale=1920:1080:flags=neighbor,tpad=stop_mode=clone:stop_duration={pad:.2f},trim=0:{D:.2f},setpts=PTS-STARTPTS'
        bg = f'[0:a]aresample=48000,apad,atrim=0:{D:.2f},asetpts=PTS-STARTPTS,volume=0.9[bg0]'
    else:
        im = os.path.join(W, 'stills', rest[0] + '.png')
        inputs = ['-loop', '1', '-t', f'{D:.2f}', '-i', im, '-ss', f'{bgm_off:.2f}', '-i', os.path.join(W, 'bgm', 'yongan_day.ogg')]
        vf = f'[0:v]fps=25,trim=0:{D:.2f},setpts=PTS-STARTPTS'
        bg = f'[1:a]aresample=48000,atrim=0:{D:.2f},asetpts=PTS-STARTPTS,volume=0.7[bg0]'
        bgm_off += D
    ti = 1 if kind == 'clip' else 2
    # 字幕：按字数分配时长
    cs = chunks(s['text']); tot = sum(len(c) for c in cs); t0 = 0.3
    draws = []
    for k, c in enumerate(cs):
        d = nd * len(c) / tot
        tf = os.path.join(seg_dir, f"{s['id']}_{k}.txt"); open(tf, 'w', encoding='utf-8').write(c)
        tfe = tf.replace('\\', '/').replace(':', '\\:')
        draws.append(f"drawtext=fontfile='{FONT}':textfile='{tfe}':fontsize=46:fontcolor=0xfff4dc:borderw=3:bordercolor=0x2a140c:box=1:boxcolor=0x1a110c@0.82:boxborderw=16:x=(w-text_w)/2:y=h-112:enable='between(t,{t0:.2f},{t0 + d:.2f})'")
        t0 += d
    vchain = vf + (',' + ','.join(draws) if draws else '') + ',format=yuv420p[v]'
    achain = (bg + f';[{ti}:a]aresample=48000,adelay=300|300,apad,atrim=0:{D:.2f},asplit=2[vo][vo2];'
              f'[bg0][vo]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];[duck][vo2]amix=inputs=2:normalize=0,'
              f'afade=t=in:d=0.25,afade=t=out:st={D - 0.3:.2f}:d=0.3[a]')
    out = os.path.join(seg_dir, s['id'] + '.mp4')
    run([FF, '-y', '-loglevel', 'error', *inputs, '-i', tts, '-filter_complex', vchain + ';' + achain, '-map', '[v]', '-map', '[a]',
         '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-t', f'{D:.2f}', out])
    segs.append(out); print(s['id'], f'{D:.1f}s')
lst = os.path.join(seg_dir, 'list.txt')
open(lst, 'w', encoding='utf-8').write(''.join(f"file '{p.replace(chr(92), '/')}'\n" for p in segs))
tmp = os.path.join(seg_dir, 'joined.mp4')
run([FF, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', tmp])
coverjpg = os.path.splitext(OUT)[0].rsplit('_v', 1)[0] + '_封面.jpg'
run([FF, '-y', '-loglevel', 'error', '-i', os.path.join(W, 'stills', 'cover.png'), '-q:v', '2', coverjpg])
run([FF, '-y', '-loglevel', 'error', '-i', tmp, '-i', coverjpg, '-map', '0', '-map', '1', '-c:v:0', 'copy', '-c:v:1', 'mjpeg', '-disposition:v:1', 'attached_pic',
     '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', OUT])
print('OUT', OUT, f'{dur_of(OUT):.1f}s')
