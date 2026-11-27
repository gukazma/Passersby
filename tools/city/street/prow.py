"""永安街样张：AI 整排楼（洋红底、四周留白）→ 抠底（只从边界连通的洋红区）→ 按指定像素尺寸还原真像素 → 透明边干净。

    python prow.py <raw.png> <out_name> --pixel P [--colors 64]
输出 out/<name>.png（RGBA，alpha 只有 0/255）、work/<name>_chk.png（带刻度放大检查图）、打印尺寸与底线。
"""
import argparse, pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = pathlib.Path.home() / ".claude/skills/pixel-sprite-anim/scripts"
sys.path.insert(0, str(S))
ap = argparse.ArgumentParser()
ap.add_argument("raw"); ap.add_argument("name")
ap.add_argument("--pixel", type=float, required=True)
ap.add_argument("--colors", type=int, default=64)
a = ap.parse_args()
H = pathlib.Path(__file__).resolve().parent
(H / "out").mkdir(exist_ok=True); (H / "work").mkdir(exist_ok=True)

im = np.array(Image.open(a.raw).convert("RGB"))
r, g, b = (im[..., i].astype(int) for i in range(3))
mag = (r > 140) & (b > 140) & (g < 120) & (np.abs(r - b) < 90)
m = Image.fromarray(np.where(mag, 255, 0).astype(np.uint8))
m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))     # 洋红里的噪点也算背景
W0, H0 = m.size
mp = m.load()
for x in range(W0):
    for y in (0, H0 - 1):
        if mp[x, y] == 255:
            ImageDraw.floodfill(m, (x, y), 128, thresh=0)
for y in range(H0):
    for x in (0, W0 - 1):
        if mp[x, y] == 255:
            ImageDraw.floodfill(m, (x, y), 128, thresh=0)
bgm = Image.fromarray(np.where(np.array(m) == 128, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))  # 往里吃 2 像素去掉洋红过渡
fg = np.array(bgm) == 0
ys, xs = np.nonzero(fg)
y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
rgba = np.dstack([im, np.where(fg, 255, 0).astype(np.uint8)])[y0:y1, x0:x1]
tmp = H / "work" / f"{a.name}_matte.png"
Image.fromarray(rgba).save(tmp)
w = H / "work" / f"px_{a.name}"
cw, ch = int(rgba.shape[1] / a.pixel) + 8, int(rgba.shape[0] / a.pixel) + 8
subprocess.run([sys.executable, str(S / "pixelize.py"), str(tmp), str(w), "--rows", "1", "--cols", "1", "--cell", f"{cw}x{ch}",
                "--colors", str(a.colors), "--keep", "0.002", "--pixel", str(a.pixel), "--fixed", "--layout", "keep", "--anchor", "none"],
               check=True, capture_output=True)
A = np.array(Image.open(w / "sheet.png").convert("RGBA"))
al = A[..., 3] > 0
ys, xs = np.nonzero(al)
A = A[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
# 洋红残边 → 透明；内部小洞补齐；alpha 只留 0/255
rr, gg, bb = (A[..., i].astype(int) for i in range(3))
fringe = (rr > 150) & (bb > 130) & (gg < 120)
A[fringe, 3] = 0
for _ in range(2):
    holes = A[..., 3] == 0
    for y, x in zip(*np.nonzero(holes)):
        if 0 < x < A.shape[1] - 1 and 0 < y < A.shape[0] - 1 and A[y, x - 1, 3] and A[y, x + 1, 3] and A[y - 1, x, 3] and A[y + 1, x, 3]:
            A[y, x] = A[y, x - 1]
A[..., 3] = np.where(A[..., 3] > 0, 255, 0)
# 孤立的不透明碎点去掉（和主体不连通、面积 < 6）
def components(mask):
    lab = np.zeros(mask.shape, int); n = 0; out = []
    H, W = mask.shape
    for sy, sx in zip(*np.nonzero(mask)):
        if lab[sy, sx]:
            continue
        n += 1; st = [(sy, sx)]; lab[sy, sx] = n; pts = []
        while st:
            y, x = st.pop(); pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; st.append((yy, xx))
        out.append(pts)
    return out
for pts in components(A[..., 3] > 0):
    if len(pts) < 6:
        for y, x in pts:
            A[y, x, 3] = 0
h, wd = A.shape[:2]
cov = (A[..., 3] > 0).mean(1)
base = int(np.nonzero(cov > 0.6)[0].max()) + 1                 # 最下面一行"大部分有楼"的行之下 = 底线
Image.fromarray(A).save(H / "out" / f"{a.name}.png")
# 检查图：×3，每 10 像素刻度
K = 3
big = Image.new("RGBA", (wd * K + 40, h * K + 40), (214, 204, 184, 255))
big.alpha_composite(Image.fromarray(A).resize((wd * K, h * K), Image.NEAREST), (40, 40))
d = ImageDraw.Draw(big)
for y in range(0, h, 10):
    d.line((0, 40 + y * K, 12 if y % 50 else 30, 40 + y * K), fill=(200, 0, 0)); d.text((2, 40 + y * K + 1), str(y), fill=(200, 0, 0)) if y % 50 == 0 else None
for x in range(0, wd, 10):
    d.line((40 + x * K, 0, 40 + x * K, 12 if x % 50 else 30), fill=(200, 0, 0)); d.text((40 + x * K + 2, 14), str(x), fill=(200, 0, 0)) if x % 50 == 0 else None
d.line((40, 40 + base * K, 40 + wd * K, 40 + base * K), fill=(255, 0, 0))
big.save(H / "work" / f"{a.name}_chk.png")
print(a.name, "size", wd, h, "base", base, "pixel", a.pixel)
