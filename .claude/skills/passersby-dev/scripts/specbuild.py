"""原地循环动作（干活、吃面等）：AI 横排 n 帧 → 真像素，按下半身（脚/凳）横向对齐，去洋红杂边和碎块。

    python specbuild.py <ai.png> <out_prefix> --frames 6 --height 106 --fps 6 [--cell 90] [--view front|side]
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fbreg import small_blobs
SK = pathlib.Path.home() / ".claude/skills/pixel-sprite-anim/scripts"
ap = argparse.ArgumentParser()
ap.add_argument("ai"); ap.add_argument("out")
ap.add_argument("--frames", type=int, required=True); ap.add_argument("--height", type=int, required=True)
ap.add_argument("--fps", type=float, default=6); ap.add_argument("--cell", type=int, default=90); ap.add_argument("--view", default="front")
ap.add_argument("--colors", type=int, default=32)
ap.add_argument("--anchor", default="feet")
a = ap.parse_args()
out = pathlib.Path(a.out); work = out.parent / (out.name + "_work"); work.mkdir(parents=True, exist_ok=True)
r = subprocess.run([sys.executable, str(SK / "pixelize.py"), a.ai, str(work), "--rows", "1", "--cols", str(a.frames), "--colors", str(a.colors),
                    "--height", str(a.height), "--fixed", "--layout", "keep", "--anchor", a.anchor, "--keep", "0.01"], capture_output=True, text=True)
if r.returncode: sys.exit(r.stderr[-1500:])
P = json.load(open(work / "report.json"))["global_pixel_size"]
S = np.array(Image.open(work / "sheet.png").convert("RGBA"))
rr, gg, bb, aa = (S[..., i].astype(int) for i in range(4))
mag = (aa > 0) & (rr - gg > 35) & (bb - gg > 35) & (np.abs(rr - bb) < 110)
S[mag, 3] = 0
S[..., 3] = np.where(S[..., 3] > 0, 255, 0)
n = a.frames; fw0 = S.shape[1] // n; Hh = S.shape[0]; W = a.cell
reg = []
for i in range(n):
    f = S[:, i * fw0:(i + 1) * fw0].copy()
    for y, x in small_blobs(f[..., 3] > 0): f[y, x] = 0
    al = f[..., 3] > 0; ys = np.nonzero(al.any(1))[0]; top, bot = ys.min(), ys.max()
    xs = np.nonzero(al[top + int((bot - top) * 0.72):bot + 1])[1]
    dx = int(round(W / 2 - xs.mean()))
    cv = np.zeros((Hh, W, 4), np.uint8)
    for x in range(fw0):
        if 0 <= x + dx < W: cv[:, x + dx] = f[:, x]
    reg.append(cv)
O = np.concatenate(reg, axis=1)
al = O[..., 3] > 0; rows = np.nonzero(al.any(1))[0]; O = O[rows.min():rows.max() + 1]
Image.fromarray(O).save(str(out) + ".png")
meta = {"frames": n, "fps": a.fps, "frame_w": W, "frame_h": int(O.shape[0]), "origin": [W // 2, int(O.shape[0]) - 1],
        "root_motion_px": [0] * n, "axis": "x" if a.view == "side" else "y", "pixel_size_src": P, "view": a.view}
json.dump(meta, open(str(out) + ".json", "w"), ensure_ascii=False, indent=1)
print(out, P, O.shape)
