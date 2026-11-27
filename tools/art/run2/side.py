import sys, json
import numpy as np
from PIL import Image
sys.path.insert(0, '.')
from legs import *

SRC = np.array(Image.open('/home/guleixin/pw/a11/sprites/out/hero_run.png').convert('RGBA'))
HIP_Y = 28.0
GROUND_ANK = 34          # 落地时脚踝行（鞋底填充到 37，描边 38）
STEP = 6                 # 每帧根运动
# 一条腿在 8 帧里的脚踝位置（相对髋部 x）与靴子形态；0-2 着地（前→后各移 6），3-7 空中
PATH = [(+6, GROUND_ANK, 'flat'), (0, GROUND_ANK, 'flat'), (-6, GROUND_ANK, 'flat'),
        (-9, 32, 'lift'), (-6, 30, 'lift'), (-1, 30, 'lift'), (+4, 31, 'lift'), (+7, 33, 'flat')]


def upper(frame, keep_rows=26, side_keep=(9, 21)):
    u = frame.copy()
    u[keep_rows + 2:] = 0
    lo, hi = side_keep
    u[keep_rows:keep_rows + 2, lo + 1:hi] = 0     # 腿区里 AI 的大腿/膝盖去掉
    return u


def skirt(img, cx, face, k):
    """裙摆：26–30 行，后摆随步伐摆 1 像素"""
    sway = [0, 0, 1, 1, 0, 0, 1, 1][k]
    rows = {26: (-5, 5), 27: (-6, 5), 28: (-6, 6), 29: (-7 - sway, 6), 30: (-7 - sway, 6)}
    m = np.zeros((H, W), bool)
    for y, (a, b) in rows.items():
        for x in range(cx + a * face if face > 0 else cx - b, (cx + b if face > 0 else cx - a * 1) + 1):
            pass
    for y, (a, b) in rows.items():
        xa, xb = (cx + a, cx + b) if face > 0 else (cx - b, cx - a)
        m[y, max(0, xa):min(W, xb + 1)] = True
    img[m] = rgba(C['olive'])
    back = [y for y in rows]
    for y, (a, b) in rows.items():   # 后侧暗、底边奶油色衬裙
        xa, xb = (cx + a, cx + b) if face > 0 else (cx - b, cx - a)
        img[y, xa if face > 0 else xb] = rgba(C['olive_dk'])
    for x in range(W):
        if m[30, x]:
            img[30, x] = rgba(C['cream'])
    outline(img, m, C['out'])
    return m


def frame_right(k, src_k, hx=16):
    img = np.zeros((H, W, 4), np.uint8)
    a = PATH[k]; b = PATH[(k + 4) % 8]
    hip = (hx + .5, HIP_Y)
    # 远侧腿 = B（先画）、近侧腿 = A
    bmB = draw_leg(img, hip, (hx + b[0], b[1]), +1, False, b[2])
    bmA = draw_leg(img, hip, (hx + a[0], a[1]), +1, True, a[2])
    sk = np.zeros((H, W, 4), np.uint8)
    skirt(sk, hx, +1, k)
    al = sk[..., 3] > 0
    img[al] = sk[al]
    u = upper(SRC[80:120, 32 * src_k:32 * src_k + 32])
    al = u[..., 3] > 0
    img[al] = u[al]
    return img


if __name__ == '__main__':
    order = [int(c) for c in (sys.argv[1] if len(sys.argv) > 1 else '01234567')]
    strip = np.concatenate([frame_right(k, order[k]) for k in range(8)], 1)
    Image.fromarray(strip).save('right_strip.png')
    big = Image.fromarray(strip).resize((strip.shape[1] * 8, H * 8), Image.NEAREST)
    bg = Image.new('RGBA', big.size, (235, 235, 235, 255)); bg.alpha_composite(big); bg.save('/tmp/yh/r2_right.png')
