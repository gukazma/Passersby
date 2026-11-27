"""洋红底 AI 图 → 真像素 RGBA，按灰色比例人（1.7 m = 110 px）定像素尺寸，可拆成单个物件。

    python pxsprite.py <raw.png> <out_prefix> [--split] [--colors 64] [--target 110] [--minpart 40]
输出 <out>_1x.png、<out>.json（像素尺寸、比例人原生高度、各部件 bbox 与脚点）、--split 时 <out>_parts/NN.png。
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pixelize as P

ap = argparse.ArgumentParser()
ap.add_argument("raw"); ap.add_argument("out")
ap.add_argument("--split", action="store_true")
ap.add_argument("--colors", type=int, default=64)
ap.add_argument("--target", type=float, default=110)
ap.add_argument("--minpart", type=int, default=40)
ap.add_argument("--pixel", type=float, default=0, help="强制像素尺寸")
ap.add_argument("--opaque", action="store_true", help="整图不透明（室内/远景）")
ap.add_argument("--crop", help="原图坐标 x,y,w,h：只处理这一块（单个物件重定尺寸用）")
ap.add_argument("--fit", help="目标原生高度：配合 --crop，按物件高度反推像素尺寸")
a = ap.parse_args()
rgb = np.array(Image.open(a.raw).convert("RGB"))
if a.crop:
    cx, cy, cw, ch = map(int, a.crop.split(",")); rgb = rgb[max(cy, 0):cy + ch, max(cx, 0):cx + cw]
Hh, Ww = rgb.shape[:2]
r, g, b = (rgb[..., i].astype(int) for i in range(3))
if a.opaque:
    fg = np.ones((Hh, Ww), bool)
else:
    mag = ((r > 140) & (b > 140) & (g < 120) & (np.abs(r - b) < 90)) | ((r - g > 70) & (b - g > 70) & (np.abs(r - b) < 70))
    mag = ndimage.binary_dilation(mag, iterations=2)      # 吃掉洋红过渡边
    fg = ~mag
# 灰色比例人：低饱和、亮度 100..160 的大连通块，高 > 图高 8%
mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
grey = (mx - mn < 14) & (mx > 100) & (mx < 165)
lab, n = ndimage.label(grey)
sil = None
for k, sl in enumerate(ndimage.find_objects(lab), 1):
    h = sl[0].stop - sl[0].start; w = sl[1].stop - sl[1].start
    cnt = (lab[sl] == k).sum()
    if h > 0.08 * Hh and 0.15 < w / h < 0.6 and cnt > 0.3 * w * h:
        if sil is None or h > sil[1]:
            sil = (k, h, sl)
sx, sy = P.edge_signals(rgb, fg)
p_ai = P.global_period([sx, sy], 2.0, 9.0)
if a.fit:
    ys_, xs_ = np.nonzero(fg); p_use = (ys_.max() - ys_.min() + 1) / float(a.fit); why = "fit"
elif a.pixel:
    p_use = a.pixel; why = "forced"
elif sil:
    p_t = sil[1] / a.target
    p_use, why = (p_ai, "ai-grid") if abs(p_ai - p_t) / p_t <= 0.08 else (p_t, "scale-figure")
else:
    p_use, why = p_ai, "no-figure"
p, phx, phy = P.detect_grid(rgb, fg, p_use, 0.0)
sil_mask = (lab == sil[0]) if sil else np.zeros_like(fg)
if sil is not None and not a.opaque:
    fg = fg & ~ndimage.binary_dilation(sil_mask, iterations=3)
small, alpha = P.downsample(rgb, fg, p, phx, phy)
flat = small[alpha].astype(float)
pal = P.kmeans(flat, a.colors)
idx = np.zeros(alpha.shape, int)
d = ((small.reshape(-1, 3)[:, None, :].astype(float) - pal[None].astype(float)) ** 2).sum(-1)
idx = d.argmin(1).reshape(alpha.shape)
for _ in range(2):  # 孤点（四邻 ≥3 同色）
    pad = np.pad(idx, 1, mode="edge")
    nb = np.stack([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]])
    for k in range(4):
        fix = ((nb == nb[k]).sum(0) >= 3) & (nb[k] != idx)
        idx = np.where(fix, nb[k], idx)
out = np.dstack([pal[idx].astype(np.uint8), np.where(alpha, 255, 0).astype(np.uint8)])
if not a.opaque:  # 去小碎块
    lab2, n2 = ndimage.label(alpha, structure=np.ones((3, 3)))
    sizes = ndimage.sum(alpha, lab2, range(1, n2 + 1))
    for k, s in enumerate(sizes, 1):
        if s < 12:
            out[lab2 == k, 3] = 0
sil_native = round(sil[1] / p, 1) if sil else None
meta = {"raw": a.raw, "pixel": round(p, 3), "pixel_ai": round(p_ai, 3), "why": why, "scale_figure_native_h": sil_native,
        "size": [out.shape[1], out.shape[0]], "parts": []}
if sil and a.opaque:  # 室内：记下比例人位置，后面补图
    ys, xs = np.nonzero(sil_mask)
    meta["scale_figure_box_native"] = [int(xs.min() / p), int(ys.min() / p), int(np.ceil(xs.max() / p)) + 1, int(np.ceil(ys.max() / p)) + 1]
pre = pathlib.Path(a.out)
if a.split and not a.opaque:
    al = out[..., 3] > 0
    lab3, n3 = ndimage.label(ndimage.binary_closing(al, iterations=2), structure=np.ones((3, 3)))
    pd = pathlib.Path(str(pre) + "_parts"); pd.mkdir(exist_ok=True)
    objs = ndimage.find_objects(lab3); order = sorted(range(len(objs)), key=lambda i: (objs[i][0].start // 60, objs[i][1].start))
    for j, i in enumerate(order):
        sl = objs[i]
        if (sl[0].stop - sl[0].start) < a.minpart and (sl[1].stop - sl[1].start) < a.minpart:
            continue
        crop = out[sl].copy(); crop[lab3[sl] != i + 1, 3] = 0
        fn = pd / f"{j:02d}.png"; Image.fromarray(crop).save(fn)
        meta["parts"].append({"file": fn.name, "bbox": [sl[1].start, sl[0].start, sl[1].stop - sl[1].start, sl[0].stop - sl[0].start]})
Image.fromarray(out).save(str(pre) + "_1x.png")
json.dump(meta, open(str(pre) + ".json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: meta[k] for k in ("pixel", "pixel_ai", "why", "scale_figure_native_h", "size")}), "parts", len(meta["parts"]))
