"""整张 AI 场景图 → 真像素（检测网格、块众数取色、统一调色板、去孤点），可选烘焙中文招牌。

    python pxscene.py <in.png> <out_prefix> [--colors 48] [--signs signs.json] [--font px.woff2] [--show 3]
signs.json: [{"text":"陈记云吞面","box":[x,y,w,h],"fg":"#fff3d6","bold":1,"shadow":"#5a2a1a","vertical":0}]（坐标为真像素）
输出 <out>_1x.png（真像素）、<out>_show.png（整数倍放大预览）、打印检测到的像素尺寸。
"""
import argparse, json, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pixelize as P

ap = argparse.ArgumentParser()
ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--colors", type=int, default=48)
ap.add_argument("--pixel", type=float, default=0)
ap.add_argument("--signs"); ap.add_argument("--font")
ap.add_argument("--show", type=int, default=3)
ap.add_argument("--autosigns", help="逗号分隔，按从左到右顺序填进检测到的空白招牌")
ap.add_argument("--bold", type=int, default=0)
a = ap.parse_args()

rgb = np.array(Image.open(a.inp).convert("RGB"))
fg = np.ones(rgb.shape[:2], bool)
sx, sy = P.edge_signals(rgb, fg)
p0 = a.pixel or P.global_period([sx, sy], 2.0, 9.0)
p, phx, phy = P.detect_grid(rgb, fg, p0, 0.15)
small, _ = P.downsample(rgb, fg, p, phx, phy)
print(f"pixel={p:.2f} phase=({phx:.2f},{phy:.2f}) native={small.shape[1]}x{small.shape[0]}")
flat = small.reshape(-1, 3).astype(float)
pal = P.kmeans(flat, a.colors)
d = ((flat[:, None, :] - pal[None].astype(float)) ** 2).sum(-1)
idx = d.argmin(1).reshape(small.shape[:2])
# 孤点：上下左右四邻里有 ≥3 个同色且与自己不同 → 改成那个颜色（去噪，不动线条）
for _ in range(2):
    pad = np.pad(idx, 1, mode="edge")
    nb = np.stack([pad[:-2, 1:-1], pad[2:, 1:-1], pad[1:-1, :-2], pad[1:-1, 2:]])
    for k in range(4):
        same = (nb == nb[k]).sum(0)
        fix = (same >= 3) & (nb[k] != idx)
        idx = np.where(fix, nb[k], idx)
img = Image.fromarray(pal[idx].astype(np.uint8))

def find_boards(idx):
    """同一调色板色、近似实心矩形、够宽够高的连通块 = 空白招牌。"""
    from scipy import ndimage
    H, W = idx.shape; found = []
    for c in np.unique(idx):
        lab, n = ndimage.label(idx == c)
        for k, sl in enumerate(ndimage.find_objects(lab), 1):
            h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            if w < 40 or h < 13 or w < 2.2 * h or w > W * 0.4:
                continue
            fill = (lab[sl] == k).mean()
            if fill > 0.8 and sl[0].stop < 0.62 * H and sl[0].start > 0.15 * H:
                found.append([sl[1].start, sl[0].start, w, h, float(fill)])
    found.sort(key=lambda b: b[0])
    return found

signs = []
if a.autosigns:
    boards = find_boards(idx)
    print("boards", boards)
    texts = json.load(open(a.autosigns, encoding="utf-8")) if a.autosigns.endswith(".json") else a.autosigns.split(",")
    for t, b in zip(texts, boards):
        bg = np.array(pal[idx[b[1] + b[3] // 2, b[0] + b[2] // 2]], float)
        lum = bg @ [0.3, 0.59, 0.11]
        fgc = "#fff4dc" if lum < 140 else "#3a2116"
        sh = "#2a140c" if lum < 140 else None
        signs.append({"text": t, "box": b[:4], "fg": fgc, "shadow": sh, "bold": a.bold})
elif a.signs:
    signs = json.load(open(a.signs, encoding="utf-8"))

if signs:
    font = ImageFont.truetype(a.font or str(pathlib.Path(__file__).resolve().parent / "px.woff2"), 12)
    for s in signs:
        x, y, w, h = s["box"]
        dr = ImageDraw.Draw(img)
        if s.get("bg"):
            dr.rectangle([x, y, x + w - 1, y + h - 1], fill=s["bg"])
        chars = list(s["text"]); gap = s.get("gap", 1); vert = s.get("vertical", 0)
        step = 12 + gap
        tw, th = (12, step * len(chars) - gap) if vert else (step * len(chars) - gap, 12)
        tw += s.get("bold", 0); th += 1 if s.get("shadow") else 0
        # 整数倍放大：板子够大就用 2 倍（甚至 3 倍）粗字，四周至少留 3 个像素
        k = max(1, min(3, (w - 8) // tw, (h - 6) // th)) if s.get("scale", 0) == 0 else s["scale"]
        lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
        for i, ch in enumerate(chars):
            cx, cy = (0, i * step) if vert else (i * step, 0)
            for dx in range(s.get("bold", 0) + 1):
                if s.get("shadow"):
                    ld.text((cx + dx, cy + 1), ch, font=font, fill=s["shadow"])
            for dx in range(s.get("bold", 0) + 1):
                ld.text((cx + dx, cy), ch, font=font, fill=s["fg"])
        al = np.array(lay); al[..., 3] = np.where(al[..., 3] > 127, 255, 0); lay = Image.fromarray(al)
        lay = lay.resize((tw * k, th * k), Image.NEAREST)
        img.paste(lay, (x + (w - lay.width) // 2, y + (h - lay.height) // 2), lay)
        print("sign", s["text"], "scale", k)
img.save(a.out + "_1x.png")
img.resize((img.width * a.show, img.height * a.show), Image.NEAREST).save(a.out + "_show.png")
