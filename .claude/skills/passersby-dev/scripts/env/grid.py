"""放大 + 网格叠图，方便量门高。python grid.py in.png out.png [--scale 2] [--step 20] [--crop x,y,w,h]"""
import argparse
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--scale", type=int, default=2); ap.add_argument("--step", type=int, default=20); ap.add_argument("--crop")
a = ap.parse_args()
im = Image.open(a.inp).convert("RGBA"); ox = oy = 0
if a.crop:
    x, y, w, h = map(int, a.crop.split(",")); im = im.crop((x, y, x + w, y + h)); ox, oy = x, y
bg = Image.new("RGBA", im.size, (40, 40, 40, 255)); bg.alpha_composite(im); im = bg.convert("RGB")
s = a.scale; w, h = im.size; im = im.resize((w * s, h * s), Image.NEAREST); d = ImageDraw.Draw(im)
for x in range((-ox) % a.step, w, a.step):
    big = (x + ox) % 100 == 0
    d.line([(x * s, 0), (x * s, h * s)], fill=(255, 0, 255) if big else (0, 200, 200))
    if big: d.text((x * s + 2, 2), str(x + ox), fill=(255, 255, 0))
for y in range((-oy) % a.step, h, a.step):
    big = (y + oy) % 100 == 0
    d.line([(0, y * s), (w * s, y * s)], fill=(255, 0, 255) if big else (0, 200, 200))
    if big: d.text((2, y * s + 2), str(y + oy), fill=(255, 255, 0))
im.save(a.out)
