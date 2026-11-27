"""设定稿（单行站姿）→ 真像素站立帧 → 4 帧呼吸循环（上半身第 1、2 帧下沉 1 px）。

    python idlebuild.py <sheet.png> <out_dir> --height 110 --cols 3 --views front,side,back [--crop-top 0.5] [--colors 32]
背景只从边界连通区域抠（容差 40），白衣服不会被当成背景。和走路同一身高 → 同一像素尺寸。
输出 out_dir/idle_<view>.png（4 帧横排）+ .json；side 朝右。
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
SK = pathlib.Path.home() / ".claude/skills/pixel-sprite-anim/scripts"
ap = argparse.ArgumentParser()
ap.add_argument("sheet"); ap.add_argument("out")
ap.add_argument("--height", type=int, required=True); ap.add_argument("--cols", type=int, default=3)
ap.add_argument("--views", default="front,side,back"); ap.add_argument("--crop-top", type=float, default=0)
ap.add_argument("--colors", type=int, default=32); ap.add_argument("--fps", type=float, default=4)
ap.add_argument("--chest", type=float, default=0.42, help="从头顶算起，这个比例以上的行随呼吸下沉")
a = ap.parse_args()
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True); work = out / "_idle_work"; work.mkdir(exist_ok=True)
im = Image.open(a.sheet).convert("RGB")
if a.crop_top:
    im = im.crop((0, 0, im.width, int(im.height * a.crop_top)))
m = im.copy(); W0, H0 = m.size
seeds = [(x, y) for x in range(0, W0, 16) for y in (0, H0 - 1)] + [(x, y) for y in range(0, H0, 16) for x in (0, W0 - 1)]
KEY = (255, 0, 255)
for s in seeds:
    if m.getpixel(s) != KEY:
        ImageDraw.floodfill(m, s, KEY, thresh=40)
arr = np.array(m); bg = np.all(arr == KEY, -1)
BGC = np.median(np.array(im)[bg], axis=0) if bg.any() else np.array([239, 230, 214])
rgba = np.dstack([np.array(im), np.where(bg, 0, 255).astype(np.uint8)])
tmp = work / "keyed.png"; Image.fromarray(rgba).save(tmp)
r = subprocess.run([sys.executable, str(SK / "pixelize.py"), str(tmp), str(work), "--rows", "1", "--cols", str(a.cols),
                    "--colors", str(a.colors), "--height", str(a.height), "--fixed", "--layout", "keep", "--anchor", "feet", "--keep", "0.02"],
                   capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-1500:])
rep = json.load(open(work / "report.json"))
views = a.views.split(",")
res = {}
for i, v in enumerate(views):
    if v in ("", "-", "skip"):
        continue
    f = np.array(Image.open(work / "frames" / f"f{i}.png").convert("RGBA"))
    al = f[..., 3] > 0; ys, xs = np.nonzero(al)
    f = f[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
    # 设定稿里的地面阴影：最下面几行里和底色接近、偏亮的像素 → 透明
    hb = f.shape[0]
    for y in range(max(0, hb - 6), hb):
        for x in range(f.shape[1]):
            c = f[y, x, :3].astype(float)
            if f[y, x, 3] and np.linalg.norm(c - BGC) < 75 and c.mean() > 150 and (c.max() - c.min()) < 60:
                f[y, x, 3] = 0
    al = f[..., 3] > 0; ys, xs = np.nonzero(al)
    f = f[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = f.shape[:2]; FW = w + 8; FH = h + 3
    base = np.zeros((FH, FW, 4), np.uint8); base[FH - h:, 4:4 + w] = f
    top = FH - h; cut = top + int(h * a.chest)
    dn = base.copy(); dn[top + 1:cut + 1] = base[top:cut]; dn[top] = 0
    # 下沉后 cut 行被覆盖；cut 行原内容若有而上一行空，补回避免断开
    frames = [base, dn, dn, base]
    strip = np.concatenate(frames, axis=1)
    Image.fromarray(strip).save(out / f"idle_{v}.png")
    meta = {"frames": 4, "fps": a.fps, "frame_w": FW, "frame_h": FH, "origin": [4 + w // 2, FH - 1],
            "root_motion_px": [0, 0, 0, 0], "axis": "x" if v == "side" else "y", "pixel_size_src": rep["global_pixel_size"], "view": v}
    json.dump(meta, open(out / f"idle_{v}.json", "w"), ensure_ascii=False, indent=1)
    res[v] = [FW, FH]
print(json.dumps({"pixel": rep["global_pixel_size"], "frames": res}))
