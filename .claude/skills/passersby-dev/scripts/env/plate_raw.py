"""小牌子兜底：在 AI 原图上用粗体 TTF + 描边写字（之后再整体像素化）。
    python plate_raw.py <raw.png> <out.png> x y w h <text> [--font C:\\Windows\\Fonts\\simhei.ttf]
"""
import sys, numpy as np
from PIL import Image, ImageDraw, ImageFont
raw, out, x, y, w, h, text = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7]), sys.argv[7]
font = sys.argv[sys.argv.index("--font") + 1] if "--font" in sys.argv else r"C:\Windows\Fonts\simhei.ttf"
img = Image.open(raw).convert("RGB"); a = np.array(img)
if "--newplate" in sys.argv:   # 原牌子太小：在原图上画一块更大的牌（深绿边框 + 米色板面 + 两根吊杆），再写字
    k = sys.argv.index("--newplate"); nx, ny, nw, nh = map(int, sys.argv[k + 1].split(","))
    face = tuple(int(v) for v in a[y + h // 2, x + w // 2]); frame = (38, 70, 48); dk = ImageDraw.Draw(img)
    dk.rectangle([x - 4, y - 4, x + w + 4, y + h + 4], fill=tuple(int(v) for v in a[y - 30, x + w + 40]))  # 抹掉旧牌（取背景色）
    for hx in (nx + nw // 5, nx + 4 * nw // 5): dk.rectangle([hx - 5, ny - 28, hx + 5, ny], fill=frame)
    dk.rounded_rectangle([nx, ny, nx + nw, ny + nh], radius=12, fill=frame)
    dk.rounded_rectangle([nx + 12, ny + 12, nx + nw - 12, ny + nh - 12], radius=8, fill=face)
    x, y, w, h = nx + 12, ny + 12, nw - 24, nh - 24; a = np.array(img)
bg = a[y + h // 3:y + 2 * h // 3, x + w // 4:x + 3 * w // 4].reshape(-1, 3).mean(0); lum = bg @ [0.3, 0.59, 0.11]
fill, stroke = ((58, 30, 18), (250, 238, 214)) if lum >= 140 else ((255, 236, 196), (40, 18, 10))
d = ImageDraw.Draw(img); size = int(h * 0.72); sw = max(2, h // 14)
while True:
    f = ImageFont.truetype(font, size); bb = d.textbbox((0, 0), text, font=f, stroke_width=sw)
    if bb[2] - bb[0] <= w * 0.86 or size < 10: break
    size -= 2
ox = x + (w - (bb[2] - bb[0])) / 2 - bb[0]; oy = y + (h - (bb[3] - bb[1])) / 2 - bb[1]
d.text((ox, oy), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
img.save(out); print("plate", text, size, "lum", int(lum))
