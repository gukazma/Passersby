"""预览：地面网格按根运动滚动、人物居中（镜头跟随）。三栏：8 帧逐帧前进 / 8 帧连续前进（现游戏）/ 16 帧连续前进。"""
import sys
import numpy as np
from PIL import Image, ImageDraw

SC = 4; GIFFPS = 50; SECS = 2.3
ROWS = ['down', 'left', 'right', 'up']


def ground(w, h, off, axis):
    g = np.zeros((h, w, 3), np.uint8); g[:] = (214, 204, 184)
    for i in range(-2, (w if axis == 'x' else h) // 8 + 3):
        p = int(np.floor(i * 8 - off % 8))
        if axis == 'x' and 0 <= p < w: g[:, p] = (170, 160, 140)
        if axis == 'y' and 0 <= p < h: g[p, :] = (170, 160, 140)
    for i in range(-2, (h if axis == 'x' else w) // 8 + 3):
        p = i * 8
        if axis == 'x' and 0 <= p < h: g[p, :] = (190, 180, 160)
        if axis == 'y' and 0 <= p < w: g[:, p] = (190, 180, 160)
    return g


def panel(sheet, d, n, fps, step, mode, t):
    r = ROWS.index(d)
    axis = 'x' if d in ('left', 'right') else 'y'
    sg = 1 if d in ('right', 'down') else -1
    w, h = (96, 48) if axis == 'x' else (48, 72)
    nf = t * fps
    k = int(nf) % n
    dist = (int(nf) * step) if mode == 'F' else nf * step       # 身体前进距离
    g = ground(w, h, sg * dist, axis)
    img = Image.fromarray(g).convert('RGBA')
    fr = Image.fromarray(sheet[40 * r:40 * r + 40, 32 * k:32 * k + 32])
    img.alpha_composite(fr, ((w - 32) // 2, (h - 40) // 2 + (4 if axis == 'x' else 0)))
    return img.resize((w * SC, h * SC), Image.NEAREST)


if __name__ == '__main__':
    s8 = np.array(Image.open(sys.argv[1]).convert('RGBA')); s16 = np.array(Image.open(sys.argv[2]).convert('RGBA'))
    out = sys.argv[3]
    for d in ROWS:
        frames = []
        for i in range(int(SECS * GIFFPS)):
            t = i / GIFFPS
            ps = [panel(s8, d, 8, 14, 6, 'F', t), panel(s8, d, 8, 14, 6, 'C', t), panel(s16, d, 16, 28, 3, 'C', t)]
            W_ = sum(p.width for p in ps) + 20; H_ = ps[0].height + 22
            c = Image.new('RGBA', (W_, H_), (250, 246, 238, 255)); x = 0
            dr = ImageDraw.Draw(c)
            for p, lab in zip(ps, ['8f step-at-frame', '8f continuous (game)', '16f continuous']):
                c.paste(p, (x, 22)); dr.text((x + 4, 4), lab, fill=(60, 40, 30)); x += p.width + 10
            frames.append(c.convert('P', palette=Image.ADAPTIVE))
        frames[0].save(f'{out}_{d}.gif', save_all=True, append_images=frames[1:], duration=1000 // GIFFPS, loop=0)
