import json, subprocess, sys, numpy as np
from PIL import Image
PICK = {'down': 'a', 'left': 'b', 'right': 'b', 'up': 'b'}
RM = '/home/guleixin/.claude/skills/pixel-sprite-anim/scripts/rootmotion.py'
CYCLE, FPS, BLEND = 48.0, 15.0, 0.75
def clean(s):
    a = s.copy(); al = a[..., 3] > 0
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    pink = al & (r > 150) & (b > 120) & (g < 110)            # 洋红底残留
    a[pink] = 0; al = a[..., 3] > 0
    p = np.pad(al.astype(int), 1); nb = sum(p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) - al
    a[al & (nb == 0)] = 0                                     # 孤立像素
    return a
sheet = np.zeros((160, 256, 4), np.uint8); meta = {}
for r, d in enumerate(['down', 'left', 'right', 'up']):
    s = clean(np.array(Image.open(f'run/{d}_{PICK[d]}_lock.png').convert('RGBA')))
    Image.fromarray(s).save(f'run/{d}_final.png')
    sheet[40 * r:40 * r + 40] = s
    args = [sys.executable, RM, f'run/{d}_final.png', d, '--cycle', str(CYCLE), '--anim-fps', str(FPS), '--blend', str(BLEND)]
    if d in ('down', 'up'): args.append('--inplace')
    j = json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)
    meta[d] = j; print(d, j['root_motion_px'], 'min', j['min_step_px'], 'cv', j['cv'], 'slip', j['slip_mean_px'], 'meas', j['measured_px'])
Image.fromarray(sheet).save('../out/hero_run.png')
speed = CYCLE * FPS / 8
json.dump({"sheet": "hero_run.png", "frame": [32, 40], "anchor_feet": [16, 39], "rows": ["down", "left", "right", "up"], "frames_per_row": 8,
           "anim_fps": FPS, "cycle_px": CYCLE, "speed_px_per_s": speed,
           "movement": "F：跑步动画固定帧率播放，身体在换帧时按 root_motion_px[dir][k] 前进；头部与行走表同一个头、头顶固定第 2 行；飞跃帧脚离地",
           "root_motion_px": {d: meta[d]['root_motion_px'] for d in meta},
           "qc": {d: {k: meta[d][k] for k in ('min_step_px', 'cv', 'slip_mean_px', 'measured_px')} for d in meta}},
          open('../out/hero_run.json', 'w'), ensure_ascii=False, indent=1)
print('speed', speed)
