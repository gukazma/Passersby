"""A1.5 讲解视频：旧/新动画对比片段（1920x1080 25fps PNG 序列 → mp4）。"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
H = os.path.expanduser('~/pw/a13'); C = H + '/game/side_data/chars'; B = H + '/gait2/backup'; T = '/tmp/yh3/cmp'
FONT = os.path.expanduser('~/gdemo/web/fonts/NotoSansSC-VF.ttf')
def font(sz):
    f = ImageFont.truetype(FONT, sz)
    try: f.set_variation_by_axes([700])
    except Exception: pass
    return f
BG = (238, 228, 208); INK = (52, 34, 22); ACC = (190, 110, 40); RED = (196, 70, 50)
def load(png, meta):
    im = Image.open(png).convert('RGBA'); fw, fh = meta['frame_w'], meta['frame_h']
    fr = [im.crop((i * fw, 0, (i + 1) * fw, fh)) for i in range(meta['frames'])]
    gap = []
    for f in fr:
        bb = f.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox()
        gap.append(meta['origin'][1] - (bb[3] - 1) if bb else 0)
    return dict(fr=fr, fps=meta['fps'], org=meta['origin'], gap=gap)
def anim_of(char_dir, name):
    j = json.load(open(char_dir + '/char.json', encoding='utf-8-sig'))['anims'][name]
    return load(char_dir + '/' + j['file'], j)
def draw_sprite(img, a, t, cx, gy, sc, show_gap):
    k = int(t * a['fps']) % len(a['fr']); f = a['fr'][k]
    d = ImageDraw.Draw(img, 'RGBA')
    d.line([(cx - 260, gy), (cx + 260, gy)], fill=INK + (255,), width=4)
    sw = int(f.width * sc * 0.42)
    d.ellipse([cx - sw // 2, gy - 9, cx + sw // 2, gy + 9], fill=(60, 40, 25, 110))
    s = f.resize((f.width * sc, f.height * sc), Image.NEAREST)
    img.alpha_composite(s, (cx - a['org'][0] * sc, gy - a['org'][1] * sc))
    if show_gap:
        g = a['gap'][k] * sc
        if g > 2:
            d.line([(cx + sw // 2 + 30, gy), (cx + sw // 2 + 30, gy - g)], fill=RED + (255,), width=5)
            d.text((cx + sw // 2 + 44, gy - g // 2), f'离地 {a["gap"][k]} 像素', font=font(34), fill=RED, anchor='lm')
def render(name, rows, secs, title, sc):
    out = f'/tmp/yh3/{name}'; os.makedirs(out, exist_ok=True)
    n = int(secs * 25); rh = 810 // len(rows)   # 底部 150 px 留给字幕
    for i in range(n):
        t = i / 25; img = Image.new('RGBA', (1920, 1080), BG + (255,)); d = ImageDraw.Draw(img)
        d.text((960, 40), title, font=font(46), fill=INK, anchor='mm')
        d.text((480, 95), 'A1.4（旧）', font=font(36), fill=RED, anchor='mm')
        d.text((1440, 95), 'A1.5（新）', font=font(36), fill=ACC, anchor='mm')
        d.line([(960, 80), (960, 930)], fill=(200, 184, 160), width=3)
        for r, (label, old, new, gap) in enumerate(rows):
            gy = 120 + rh * (r + 1) - 10
            d.text((40, gy - rh + 40), label, font=font(32), fill=INK, anchor='lm')
            draw_sprite(img, old, t, 480, gy, sc, gap)
            draw_sprite(img, new, t, 1440, gy, sc, gap)
        img.convert('RGB').save(f'{out}/{i:04d}.png')
    subprocess.run([os.path.expanduser('~/bin/ffmpeg'), '-y', '-loglevel', 'error', '-framerate', '25', '-i', f'{out}/%04d.png',
                    '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', f'/tmp/yh3/{name}.mp4'], check=True)
    for f in os.listdir(out): os.remove(f'{out}/{f}')
    print(name, n)
def old_meta(path):
    return json.load(open(path, encoding='utf-8-sig'))
oh = old_meta(T + '/old_hero_char.json')['anims']['run_side']; oy = old_meta(T + '/old_yejun_char.json')['anims']['walk_side']
feet = [('主角 跑步', load(T + '/old_run.png', oh), anim_of(C + '/hero', 'run_side'), True),
        ('叶俊 走路', load(T + '/old_yejun.png', oy), anim_of(C + '/yejun', 'walk_side'), True)]
render('cmp_feet', feet, 16, '脚贴地：每一帧最低点都在地面线上', 3)
rows = []
for cid, an, lab in [('wangcai', 'walk_side', '旺财 慢走（四拍）'), ('wangcai', 'run_side', '旺财 小跑（对角步）'), ('dog2', 'walk_side', '滨江的黑白狗 慢走'),
                     ('cat_orange', 'walk_side', '橘猫 走路'), ('cat_calico', 'walk_side', '三花猫 走路')]:
    rows.append((lab, load(f'{B}/{cid}_{an}.png', old_meta(f'{B}/{cid}_{an}.json')), anim_of(f'{C}/{cid}', an), False))
render('cmp_gait', rows, 18, '猫狗步态：按真实四足步态重画', 3)
