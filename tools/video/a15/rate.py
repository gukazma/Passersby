import json, subprocess, shutil, re, os
ff = shutil.which('ffmpeg'); W = r'D:\games\passersby_work\a15video'
for s in json.load(open(os.path.join(W, 'script.json'), encoding='utf-8')):
    e = subprocess.run([ff, '-i', os.path.join(W, 'tts', s['id'] + '.mp3')], capture_output=True, text=True, encoding='utf-8', errors='ignore').stderr
    d = float(re.search(r'Duration: \d+:\d+:([0-9.]+)', e).group(1))
    print(s['id'], len(s['text']), round(d, 1), round(len(s['text']) / d, 2))
