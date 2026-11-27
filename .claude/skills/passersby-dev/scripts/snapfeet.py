"""把侧面走/跑每一帧的最低点贴到地线（origin y），腾空帧再抬高 lift 像素。
用户 11-27：「跑步的时候影子是悬空的，看起来人悬空一样」——原因是按躯干对齐、按全部帧最低点定地线，
其余帧的脚离地 10–19 px。走路任何时刻都有一只脚着地，所以每帧最低点都必须在地线上。
用法：snapfeet.py <char_dir> <anim> [--flight 2,6] [--lift 3]
"""
import json, sys, argparse
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("char_dir"); ap.add_argument("anim")
ap.add_argument("--flight", default=""); ap.add_argument("--lift", type=int, default=3)
a = ap.parse_args()
cj = json.load(open(f"{a.char_dir}/char.json", encoding="utf-8"))
A = cj["anims"][a.anim]
im = np.array(Image.open(f"{a.char_dir}/{A['file']}").convert("RGBA"))
fw, fh, n = A["frame_w"], A["frame_h"], A["frames"]
flight = {int(x) for x in a.flight.split(",") if x != ""}
frames, lows, tops = [], [], []
for f in range(n):
    fr = im[:, f * fw:(f + 1) * fw]
    ys = np.where((fr[:, :, 3] > 0).any(1))[0]
    frames.append(fr); lows.append(int(ys.max())); tops.append(int(ys.min()))
# 目标：最低点 = base（腾空帧 base - lift）。新画布要装得下最高的头
heights = [lows[f] - tops[f] + (a.lift if f in flight else 0) for f in range(n)]
base = max(heights) + 1
H = base + 1
out = np.zeros((H, fw * n, 4), np.uint8)
for f in range(n):
    dy = (base - (a.lift if f in flight else 0)) - lows[f]
    src = frames[f]
    for y in range(fh):
        ny = y + dy
        if 0 <= ny < H:
            out[ny, f * fw:(f + 1) * fw] = src[y]
Image.fromarray(out).save(f"{a.char_dir}/{A['file']}")
A["frame_h"] = H
A["origin"] = [A["origin"][0], base]
json.dump(cj, open(f"{a.char_dir}/char.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(a.anim, "lows before", lows, "-> base", base, "H", H, "flight", sorted(flight))
