"""为 8x4 行走表（32x40/帧，行 down/left/right/up）生成站立帧 <name>_idle.png（4 帧 128x40，同顺序）。
侧面：取两脚最并拢的帧，腿部区只保留着地那条腿，再在身后 2px 复制一条（稍暗）= 双脚并拢站立。
正/背面：取脚底一行像素最多（两脚都着地）的帧。"""
import sys, json, numpy as np
from PIL import Image
def side_idle(cell, back):  # back = +1 身后在右（面朝左），-1 身后在左
    a = cell[..., 3] > 0; rows = np.where(a.any(1))[0]; bot = rows.max()
    top = bot - 9                       # 腿部区：脚底往上 10 行
    out = cell.copy()
    gc = np.where(a[bot - 1:bot + 1].any(0))[0]        # 着地脚的列
    # 着地腿：从脚往上逐行连通（列跨度允许左右各扩 1）
    keep = np.zeros_like(a); lo, hi = gc.min(), gc.max()
    for y in range(bot, top - 1, -1):
        cols = [x for x in range(max(0, lo - 1), min(32, hi + 2)) if a[y, x]]
        if not cols: break
        # 只取与上一段相连的连续段
        seg = []; 
        for x in cols:
            if not seg or x == seg[-1] + 1: seg.append(x)
            else: break
        lo, hi = seg[0], seg[-1]; keep[y, lo:hi + 1] = True
    leg = np.zeros_like(cell); leg[keep] = cell[keep]
    out[top:bot + 1] = 0
    # 身后那条腿：着地腿平移 2px，稍暗，画在后面
    sh = np.roll(leg, 2 * back, axis=1); sh[..., :3] = (sh[..., :3] * 0.78).astype(np.uint8)
    m = sh[..., 3] > 0; region = np.zeros_like(m); region[top:bot + 1] = True
    out[m & region] = sh[m & region]
    m2 = keep; out[m2] = cell[m2]
    # 腿部区以上保持原帧
    return out
def main(path):
    im = np.array(Image.open(path).convert('RGBA')); res = np.zeros((40, 128, 4), np.uint8); pick = {}
    for r, d in enumerate(['down', 'left', 'right', 'up']):
        cells = [im[r * 40:(r + 1) * 40, k * 32:(k + 1) * 32] for k in range(8)]
        if d in ('left', 'right'):
            def span(c):
                a = c[..., 3] > 0; bot = np.where(a.any(1))[0].max(); cols = np.where(a[bot - 6:bot + 1].any(0))[0]; return cols.max() - cols.min()
            k = int(np.argmin([span(c) for c in cells])); cell = side_idle(cells[k], 1 if d == 'left' else -1)
        else:
            def ground(c):
                a = c[..., 3] > 0; bot = np.where(a.any(1))[0].max(); return int(a[bot].sum()) * 10 - abs(int(np.where(a.any(1))[0].max()) - 39)
            k = int(np.argmax([ground(c) for c in cells])); cell = cells[k]
        pick[d] = k; res[:, r * 32:(r + 1) * 32] = cell
    Image.fromarray(res).save(path[:-4] + '_idle.png'); return pick
if __name__ == '__main__':
    for p in sys.argv[1:]: print(p, main(p))
