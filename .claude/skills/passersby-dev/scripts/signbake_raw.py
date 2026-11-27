"""招牌 B 方案：先在 AI 高清原图上写字（粗体 TTF + 深色描边 + 1 像素投影），再整体转真像素，字和招牌一起被像素化，像画上去的。

    python signbake_raw.py <raw.png> <texts.json> <out_prefix> --font C:\\Windows\\Fonts\\simhei.ttf [--fill auto]
texts.json: [{"i": 招牌序号(从左到右), "text": "永安茶楼"}]
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pixelize as P
ap = argparse.ArgumentParser()
ap.add_argument("raw"); ap.add_argument("texts"); ap.add_argument("out")
ap.add_argument("--font", required=True); ap.add_argument("--fill", default="auto")
ap.add_argument("--hfrac", type=float, default=0.62)
a = ap.parse_args()
rgb = np.array(Image.open(a.raw).convert("RGB"))
fg = np.ones(rgb.shape[:2], bool)
sx, sy = P.edge_signals(rgb, fg)
p0 = P.global_period([sx, sy], 2.0, 9.0)
p, phx, phy = P.detect_grid(rgb, fg, p0, 0.15)
small, _ = P.downsample(rgb, fg, p, phx, phy)
flat = small.reshape(-1, 3).astype(float); pal = P.kmeans(flat, 48)
idx = ((flat[:, None] - pal[None].astype(float)) ** 2).sum(-1).argmin(1).reshape(small.shape[:2])
from scipy import ndimage
H, W = idx.shape; boards = []
for c in np.unique(idx):
    lab, n = ndimage.label(idx == c)
    for k, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if w < 30 or h < 9 or w < 2.0 * h or w > W * 0.4: continue
        if (lab[sl] == k).mean() > 0.8:
            boards.append([sl[1].start, sl[0].start, w, h])
boards.sort(key=lambda b: b[0])
# 合并重叠（同一块板被检测两次）
merged = []
for b in boards:
    if merged and b[0] < merged[-1][0] + merged[-1][2] and abs(b[1] - merged[-1][1]) < 10:
        continue
    merged.append(b)
boards = merged
mh = max(b[3] for b in boards)
boards = [b for b in boards if b[3] >= 0.6 * mh]   # 只要大招牌（门牌、小标牌另算）
print("pixel", round(p, 2), "boards", boards)
img = Image.open(a.raw).convert("RGB"); d = ImageDraw.Draw(img)
for t in json.load(open(a.texts, encoding="utf-8")):
    if t["i"] >= len(boards): print("no board", t); continue
    x, y, w, h = boards[t["i"]]
    X, Y, BW, BH = phx + x * p, phy + y * p, w * p, h * p
    bg = np.array(pal[idx[y + h // 2, x + w // 2]], float); lum = bg @ [0.3, 0.59, 0.11]
    fill = (255, 236, 196) if lum < 140 else (58, 30, 18)
    stroke = (40, 18, 10) if lum < 140 else (250, 238, 214)
    size = int(BH * a.hfrac)
    while True:
        f = ImageFont.truetype(a.font, size)
        bb = d.textbbox((0, 0), t["text"], font=f, stroke_width=max(2, int(p * 0.7)))
        if bb[2] - bb[0] <= BW * 0.86 or size < 10: break
        size -= 2
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    ox, oy = X + (BW - tw) / 2 - bb[0], Y + (BH - th) / 2 - bb[1]
    d.text((ox + p, oy + p), t["text"], font=f, fill=stroke, stroke_width=max(2, int(p * 0.7)), stroke_fill=stroke)
    d.text((ox, oy), t["text"], font=f, fill=fill, stroke_width=max(2, int(p * 0.7)), stroke_fill=stroke)
img.save(a.out + "_raw.png")
print("ok", a.out)
