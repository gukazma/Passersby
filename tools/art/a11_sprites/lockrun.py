# 跑步帧：头高固定（不乱跳）+ 换成行走表同一个头（走/跑/停切换脸不变）
import sys, numpy as np
from PIL import Image
N = 17                                   # hero 头部行数（含发顶，到围巾上沿）
W = np.array(Image.open('../out/hero.png').convert('RGBA'))
ROW = {'down': 0, 'left': 1, 'right': 2, 'up': 3}
def top(c): return int(np.where((c[..., 3] > 0).any(1))[0].min())
def lock(strip, d, T=2):
    s = np.array(Image.open(strip).convert('RGBA'))
    fr = [s[:, 32 * k:32 * k + 32].copy() for k in range(8)]
    out = []
    for c in fr:                           # 1) 整帧上下平移，头顶固定在 T 行（飞跃帧脚自然离地）
        dy = T - top(c)
        bot = int(np.where((c[..., 3] > 0).any(1))[0].max())
        dy = min(dy, 39 - bot)
        out.append(np.roll(c, dy, 0) if dy else c)
    r = ROW[d]; wh = W[40 * r:40 * r + N, 0:32]          # 行走表（已锁头）第 0 帧的头
    whm = wh[..., 3] > 0
    for k, c in enumerate(out):            # 2) 每帧按头部轮廓找最佳横移，贴同一个头
        best = None
        for dx in range(-3, 4):
            m = np.roll(whm, dx, 1); sc = (m ^ (c[:N, :, 3] > 0)).sum()
            if best is None or sc < best[0]: best = (sc, dx)
        out[k] = (c, best[1])
    # 横移取众数，所有帧同一位置（头不左右抖）
    dxs = [o[1] for o in out]; dx = max(set(dxs), key=dxs.count)
    res = np.zeros((40, 256, 4), np.uint8)
    for k, (c, _) in enumerate(out):
        c = c.copy(); c[:N] = np.roll(wh, dx, 1)
        res[:, 32 * k:32 * k + 32] = c
    return res, dxs
if __name__ == '__main__':
    pass
