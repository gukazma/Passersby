"""像素城市 v3 布局（周边式街区、楼朝向各条街、沿街紧凑）。由 gen_city2 的绘制函数改来：路网分级 + 街区多排错落 + 地面细节与阴影 + 河/池塘/跑道 + 更多 NPC/车/鸽子。

输出 godot/assets/ground.png + city.json（main.gd 读取）。单位 = 游戏像素。
"""
import json
import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw

OUT = pathlib.Path("godot/assets")
SZ = json.load(open(OUT / "sizes.json"))
W, H = 1920, 1440
rng = np.random.default_rng(11)
R = lambda a, b: float(rng.uniform(a, b))

PAL = {
    "grass": [(106, 154, 74), (95, 143, 66), (116, 164, 82)],
    "grass2": [(112, 162, 80), (100, 150, 70), (124, 172, 88)],
    "asphalt": [(78, 80, 86), (72, 74, 80), (84, 86, 92)],
    "walk": (196, 190, 178), "walk_line": (170, 164, 152), "curb": (140, 136, 128),
    "plaza": (214, 204, 184), "plaza_line": (190, 178, 158),
    "brick": (190, 150, 120), "brick_line": (160, 120, 96),
    "yard": (198, 170, 120), "path": [(186, 156, 110), (176, 146, 100), (196, 166, 120)],
    "lane": (232, 196, 80), "white": (236, 236, 230),
    "water": [(70, 130, 150), (62, 120, 140), (84, 146, 164)],
    "track": [(178, 92, 70), (168, 84, 62), (188, 102, 80)],
}
img = np.zeros((H, W, 3), np.uint8)


def clip(x0, y0, x1, y1):
    return max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))


def noise_fill(x0, y0, x1, y1, cols, p=(0.06, 0.965), mask=None):
    x0, y0, x1, y1 = clip(x0, y0, x1, y1)
    if x1 <= x0 or y1 <= y0:
        return
    m = rng.random((y1 - y0, x1 - x0))
    blk = np.empty((y1 - y0, x1 - x0, 3), np.uint8)
    blk[:] = cols[0]
    blk[m < p[0]] = cols[1]
    blk[m > p[1]] = cols[2]
    if mask is None:
        img[y0:y1, x0:x1] = blk
    else:
        mm = mask[y0:y1, x0:x1]
        img[y0:y1, x0:x1][mm] = blk[mm]


def tiles(x0, y0, x1, y1, col, line, t=16):
    x0, y0, x1, y1 = clip(x0, y0, x1, y1)
    if x1 <= x0 or y1 <= y0:
        return
    img[y0:y1, x0:x1] = col
    for y in range(y0, y1):
        if y % t == 0:
            img[y, x0:x1] = line
        off = t // 2 if (y // t) % 2 else 0
        for x in range(x0 - (x0 % t) + off, x1, t):
            if x0 <= x < x1:
                img[y, x] = line


def shade(mask, amount=0.72, tint=(0.95, 0.9, 1.0)):
    """把 mask 区域压暗（阴影）。"""
    f = np.array([amount * tint[0], amount * tint[1], amount * tint[2]])
    img[mask] = (img[mask] * f).clip(0, 255).astype(np.uint8)


def poly_mask(pts):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).polygon([(float(x), float(y)) for x, y in pts], fill=1)
    return np.array(m, bool)


def ellipse_mask(cx, cy, rx, ry):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=1)
    return np.array(m, bool)


def line_mask(pts, width):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.line([(float(x), float(y)) for x, y in pts], fill=1, width=int(width), joint="curve")
    for x, y in pts:
        d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=1)
    return np.array(m, bool)


