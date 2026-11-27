"""整排楼收尾：裁到内容、找地面线、找空白招牌、烘焙中文。

    python rowfinish.py detect <row_1x.png> <out_prefix>        → <out>_boards.png（编号标注）+ <out>_boards.json
    python rowfinish.py bake   <row_1x.png> <out_prefix> <map.json>   map: [{"i":0,"text":"陈记云吞面"} | {"box":[x,y,w,h],"text":..}]
输出 <out>.png（裁好、底边 = 地面线）、<out>_meta.json（尺寸、ground_y、招牌）。
"""
import json, sys, pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
mode, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
A = np.array(Image.open(src).convert("RGBA"))
al = A[..., 3] > 0
labc, nc = ndimage.label(al, structure=np.ones((3, 3)))       # 去掉比例人残渣等小碎块
if nc:
    sz = ndimage.sum(al, labc, range(1, nc + 1))
    for k, v in enumerate(sz, 1):
        if v < 60: A[labc == k, 3] = 0
al = A[..., 3] > 0
ys, xs = np.nonzero(al)
A = A[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy(); al = A[..., 3] > 0
H, W = al.shape
# 地面线：各列最低不透明像素的众数（楼底是一条直线）
low = np.array([np.nonzero(al[:, x])[0].max() if al[:, x].any() else -1 for x in range(W)])
vals, cnt = np.unique(low[low >= 0], return_counts=True)
ground = int(vals[cnt.argmax()])
A = A[:ground + 1]; al = A[..., 3] > 0; H = A.shape[0]
key = A[..., 0].astype(int) * 65536 + A[..., 1].astype(int) * 256 + A[..., 2]
boards = []
for c in np.unique(key[al]):
    lab, n = ndimage.label((key == c) & al)
    for k, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if w < 28 or h < 9 or w < 1.8 * h:
            continue
        fill = (lab[sl] == k).mean()
        if fill > 0.78:
            boards.append([int(sl[1].start), int(sl[0].start), int(w), int(h), round(float(fill), 2)])
boards.sort(key=lambda b: (b[0], b[1]))
font = ImageFont.truetype(str(pathlib.Path(__file__).resolve().parent / "px.woff2"), 12)
if mode == "detect":
    im = Image.fromarray(A).convert("RGBA"); bg = Image.new("RGBA", im.size, (40, 40, 40, 255)); bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    for i, b in enumerate(boards):
        d.rectangle([b[0], b[1], b[0] + b[2] - 1, b[1] + b[3] - 1], outline=(0, 255, 0)); d.text((b[0] + 2, b[1] + 1), str(i), fill=(255, 0, 0))
    bg.convert("RGB").save(out + "_boards.png")
    json.dump({"size": [W, H], "ground_y": H - 1, "boards": boards}, open(out + "_boards.json", "w", encoding="utf-8"), indent=1)
    print("size", W, H, "boards", len(boards)); [print(i, b) for i, b in enumerate(boards)]
    sys.exit()
mp = json.load(open(sys.argv[4], encoding="utf-8"))
img = Image.fromarray(A); signs = []
for m in mp:
    x, y, w, h = (boards[m["i"]][:4] if "i" in m else m["box"])
    bgc = np.array(A[y + h // 2, x + w // 2, :3], float); lum = bgc @ [0.3, 0.59, 0.11]
    fg = m.get("fg") or ("#fff4dc" if lum < 150 else "#3a2116"); sh = m.get("shadow", "#2a140c" if lum < 150 else None)
    chars = list(m["text"]); vert = m.get("vertical", 0); gap = 1; step = 12 + gap
    tw, th = (12, step * len(chars) - gap) if vert else (step * len(chars) - gap, 12)
    th += 1 if sh else 0
    k = max(1, min(m.get("maxscale", 2), (w - 6) // tw, (h - 4) // th))
    lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    for i, ch in enumerate(chars):
        cx, cy = (0, i * step) if vert else (i * step, 0)
        if sh: ld.text((cx, cy + 1), ch, font=font, fill=sh)
        ld.text((cx, cy), ch, font=font, fill=fg)
    la = np.array(lay); la[..., 3] = np.where(la[..., 3] > 127, 255, 0); lay = Image.fromarray(la).resize((tw * k, th * k), Image.NEAREST)
    if m.get("clear"):  # 板面有杂色时先涂平
        ImageDraw.Draw(img).rectangle([x + 1, y + 1, x + w - 2, y + h - 2], fill=tuple(int(v) for v in bgc) + (255,))
    img.paste(lay, (x + (w - lay.width) // 2, y + (h - lay.height) // 2), lay)
    signs.append({"text": m["text"], "box": [x, y, w, h], "scale": k})
img.save(out + ".png")
json.dump({"size": [W, H], "ground_y": H - 1, "signs": signs}, open(out + "_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("baked", len(signs), "size", W, H)
