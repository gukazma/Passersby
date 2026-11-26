"""锁头：8 帧行走里每帧的头（头顶到围巾上沿）统一换成参考帧的头，只跟随每帧的头顶高度（上下起伏）和头部水平中心。
AI 每帧把脸画得略有不同（嘴一张一合、眼睛大小），播放时会闪。

    python headlock.py <strip.png> <out.png> [--ref 0] [--fw 32]
"""
import argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--ref", type=int, default=0); ap.add_argument("--fw", type=int, default=32)
ap.add_argument("--head-from", default="", help="从另一张同尺寸横排图的第 --ref 帧取头（该套的脸更好看时）")
a = ap.parse_args()
im = np.array(Image.open(a.src).convert("RGBA"))
n = im.shape[1] // a.fw
F = [im[:, i * a.fw:(i + 1) * a.fw].copy() for i in range(n)]


def head_box(f):
    al = f[..., 3] > 0
    top = np.nonzero(al.any(1))[0].min()
    r, g, b = (f[..., i].astype(int) for i in range(3))
    scarf = al & (r > 150) & (g < 115) & (b < 90) & (r - g > 70)  # 锈橙色围巾
    rows = np.nonzero(scarf.sum(1) >= 4)[0]  # 围巾横跨多格；嘴只有 1-2 格红色
    srow = rows.min() if len(rows) else top + 16
    cols = np.nonzero(al[top:srow].any(0))[0]
    return top, srow, (cols.min() + cols.max()) / 2


boxes = [head_box(f) for f in F]
if a.head_from:
    hf = np.array(Image.open(a.head_from).convert("RGBA"))
    RF = hf[:, a.ref * a.fw:(a.ref + 1) * a.fw].copy()
    rt, rs, rc = head_box(RF)
    boxes_all = boxes + [(rt, rs, rc)]
else:
    RF = F[a.ref]
    rt, rs, rc = boxes[a.ref]
    boxes_all = boxes
H = min(s - t for t, s, _ in boxes_all)  # 只换所有帧共有的头部高度，不盖住任何一帧的围巾
head = RF[rt:rt + H]
for k in range(n):
    t, s, c = boxes[k]
    dx = int(round(c - rc))
    blk = np.roll(head, dx, axis=1)
    if dx > 0:
        blk[:, :dx] = 0
    elif dx < 0:
        blk[:, dx:] = 0
    F[k][t:t + H] = blk
    print(k, "top", t, "scarf", s, "dx", dx)
Image.fromarray(np.concatenate(F, axis=1)).save(a.dst)
