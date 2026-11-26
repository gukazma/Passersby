"""v4 街区图：AI 整块街区 → 原生像素还原 → ×K 最近邻放大 → 自动找前排楼底线 base、后巷/广场 [a0,a1]。

    python process_blocks.py <raw.png> <name> [--k 3] [--single] [--alley a0,a1] [--base y]（覆盖值用原生像素坐标）
输出 godot/assets/blocks/<name>.png / .json，以及 /tmp/blkchk_<name>.png（标注检查图）。
"""
import argparse, colorsys, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

S = pathlib.Path.home() / ".claude/skills/pixel-sprite-anim/scripts"
OUT = pathlib.Path("godot/assets/blocks"); OUT.mkdir(parents=True, exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument("raw"); ap.add_argument("name")
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--single", action="store_true")
ap.add_argument("--alley", default=""); ap.add_argument("--base", type=int, default=0)
ap.add_argument("--pixel", type=float, default=0)
a = ap.parse_args()
work = pathlib.Path(f"/tmp/blkw_{a.name}")
subprocess.run([sys.executable, str(S / "pixelize.py"), a.raw, str(work), "--rows", "1", "--cols", "1", "--cell", "900x700",
                "--colors", "64", "--keep", "0.002"] + (["--pixel", str(a.pixel), "--fixed"] if a.pixel else []), check=True, capture_output=True)
px = Image.open(work / "sheet.png").convert("RGBA")
al = np.array(px)[..., 3] > 0
ys, xs = np.nonzero(al)
px = px.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
A = np.array(px)
for _ in range(2):   # 补内部小洞
    holes = A[..., 3] == 0
    for y, x in zip(*np.nonzero(holes)):
        if 0 < x < A.shape[1] - 1 and 0 < y < A.shape[0] - 1 and A[y, x - 1, 3] and A[y, x + 1, 3] and A[y - 1, x, 3]:
            A[y, x] = A[y, x - 1]
# 左右、底边对齐（去掉参差的 1-2 像素）；顶边保留透明的天际线
al = A[..., 3] > 0
cols = np.nonzero(al.mean(0) > 0.5)[0]
rows = np.nonzero(al.mean(1) > 0.9)[0]
A = A[:rows.max() + 1, cols.min():cols.max() + 1].copy()
A[A[..., 3] > 0, 3] = 255
w, h = A.shape[1], A.shape[0]
rgb = A[..., :3].astype(float) / 255
# 前排楼底线：底部 30% 里最强的整行水平边缘
gy = np.abs(np.diff(rgb, axis=0)).sum(-1).mean(1)
lo = int(h * 0.7)
base = a.base or lo + int(np.argmax(gy[lo:h - 2])) + 1
alley = None
if a.alley:
    alley = [int(v) for v in a.alley.split(",")]
elif not a.single:
    sat = np.array([[colorsys.rgb_to_hsv(*rgb[y, x])[1] for x in range(w)] for y in range(h)])
    val = rgb.max(-1)
    grey = ((sat < 0.2) & (val > 0.3) & (val < 0.85)).mean(1)
    best, cur = (0, 0, 0), None
    for y in range(int(h * 0.2), int(h * 0.75)):
        if grey[y] > 0.45:
            cur = (cur[0], y + 1) if cur else (y, y + 1)
            if cur[1] - cur[0] > best[2]:
                best = (cur[0], cur[1], cur[1] - cur[0])
        else:
            cur = None
    if best[2] >= 3:
        alley = [best[0], best[1]]
K = a.k
big = Image.fromarray(A).resize((w * K, h * K), Image.NEAREST)
big.save(OUT / f"{a.name}.png")
meta = {"w": w * K, "h": h * K, "base": base * K, "alley": [alley[0] * K, alley[1] * K] if alley else None, "native": [w, h]}
json.dump(meta, open(OUT / f"{a.name}.json", "w"))
chk = big.convert("RGB"); d = ImageDraw.Draw(chk)
d.line((0, base * K, w * K, base * K), fill=(255, 0, 0), width=3)
if alley:
    d.rectangle((0, alley[0] * K, w * K, alley[1] * K), outline=(0, 255, 255), width=3)
chk.resize((chk.width // 2, chk.height // 2)).save(f"/tmp/blkchk_{a.name}.png")
print(a.name, meta)
