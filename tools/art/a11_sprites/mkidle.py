# 站立帧合成：AI 正侧面站姿（双脚着地）→ 调色板对齐 → 头对齐到行走参考帧 → 头部行直接用行走参考头（走/停切换不跳）
import sys, json, numpy as np
from PIL import Image
sys.path.insert(0, '.')
from recolor import palette, to_pal
NECK = {'hero': 17, 'npc_office': 19, 'npc_student': 18}
REFK = {'hero': {1: 0, 2: 0}, 'npc_office': {1: 0, 2: 3}, 'npc_student': {1: 0, 2: 0}}
def headmask(c, N): return c[:N, :, 3] > 0
def build(base, d, v, cell=0):
    r = 1 if d == 'left' else 2; N = NECK[base]
    W = np.array(Image.open(f'../out/{base}.png').convert('RGBA'))
    ref = W[40 * r:40 * r + 40, 32 * REFK[base][r]:32 * REFK[base][r] + 32]
    sh = np.array(Image.open(f'px/{base}_idle{d}_{v}/sheet.png').convert('RGBA'))
    c = sh[40 * (cell // 4):40 * (cell // 4) + 40, 32 * (cell % 4):32 * (cell % 4) + 32]
    c = to_pal(c, palette(base))
    best = None
    for dx in range(-4, 5):
        s = np.roll(c, dx, 1); sc = (headmask(s, N) ^ headmask(ref, N)).sum()
        if best is None or sc < best[0]: best = (sc, dx)
    c = np.roll(c, best[1], 1)
    out = c.copy(); out[:N] = ref[:N]
    # 头下第一行若与身体脱节（参考头的脖子列下面空），补一行身体像素
    return out, best
if __name__ == '__main__':
    S = Image.new('RGBA', (32 * 9, 40 * 6), (190, 190, 190, 255))
    for j, base in enumerate(['hero', 'npc_office', 'npc_student']):
        for i, d in enumerate(['left', 'right']):
            r = 1 if d == 'left' else 2
            W = Image.open(f'../out/{base}.png').convert('RGBA')
            S.alpha_composite(W.crop((32 * REFK[base][r], 40 * r, 32 * REFK[base][r] + 32, 40 * r + 40)), (0, 40 * (2 * j + i)))
            for k, v in enumerate('ab'):
                for cell in (0, 5):
                    o, b = build(base, d, v, cell); print(base, d, v, cell, b)
                    S.alpha_composite(Image.fromarray(o), (32 * (1 + k * 2 + (cell > 0)), 40 * (2 * j + i)))
    S.resize((S.width * 5, S.height * 5), Image.NEAREST).save('/home/guleixin/pw/a11/sprites/qc/idle_comp.png')
