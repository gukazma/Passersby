"""动作帧：AI 横排 n 帧 → specbuild（真像素、按下半身对齐）→ 补充游戏字段。

    python actbuild.py <ai.png> <out_prefix> --frames 6 --height 110 --fps 6 --view side|front [--loop 1] [--seat bench|stool]
                      [--hand-dog] [--cell 100] [--target-h H]
--height = 原图人物（本动作帧）高度中位数对应的像素高：站立 = 角色身高；坐 ≈ 0.74×；蹲 ≈ 0.62×。
输出 <out>.png/.json：frames fps frame_w frame_h origin loop view prop seat_point hand_point。
"""
import argparse, json, subprocess, sys, pathlib
import numpy as np
from PIL import Image
H = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("ai"); ap.add_argument("out")
ap.add_argument("--frames", type=int, required=True); ap.add_argument("--height", type=int, required=True)
ap.add_argument("--fps", type=float, default=6); ap.add_argument("--view", default="side"); ap.add_argument("--loop", type=int, default=1)
ap.add_argument("--seat", default=""); ap.add_argument("--hand-dog", action="store_true"); ap.add_argument("--cell", type=int, default=100)
ap.add_argument("--char-h", type=int, default=110, help="角色站立身高（用于坐姿座高估计）")
ap.add_argument("--anchor", default="feet", help="none = 保留帧间上下位置（跳跃）")
a = ap.parse_args()
r = subprocess.run([sys.executable, str(H / "specbuild.py"), a.ai, a.out, "--frames", str(a.frames), "--height", str(a.height),
                    "--fps", str(a.fps), "--cell", str(a.cell), "--view", a.view, "--anchor", a.anchor], capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-1500:] + r.stdout[-500:])
m = json.load(open(a.out + ".json")); S = np.array(Image.open(a.out + ".png").convert("RGBA"))
W, Hh = m["frame_w"], m["frame_h"]; ox, oy = m["origin"]
m.update(loop=bool(a.loop), view=a.view, prop=None, axis="x", root_motion_px=[0] * a.frames)
f0 = S[:, 0:W, 3] > 0
if a.seat:
    sh = int(round(0.27 * a.char_h))         # 座面高约 0.27×身高（0.45 m）
    band = f0[max(0, Hh - 1 - sh - 5):Hh - sh + 5]
    xs = np.nonzero(band.any(0))[0]
    if a.view == "side" and len(xs):
        m["seat_point"] = [int(xs.min() + 10 - ox), -sh]   # 屁股后沿往前 10 px = 凳面中心
    else:
        m["seat_point"] = [0, -sh]
    m["seat"] = a.seat
    m["note"] = "只画人不画座位：道具保持显示，把 seat_point 对准道具座面中心；人物画在道具前面（y_foot 比道具大 1–6 px）"
if a.hand_dog:
    # 蹲下抚摸：所有帧里，人物高度 30%–85% 区间（避开头）最靠前（右）的不透明点 = 手
    best = None
    for i in range(a.frames):
        fa = S[:, i * W:(i + 1) * W, 3] > 0
        ys = np.nonzero(fa.any(1))[0]; top, bot = ys.min(), ys.max()
        lo, hi = top + int((bot - top) * 0.30), top + int((bot - top) * 0.85)
        yy, xx = np.nonzero(fa[lo:hi])
        if len(xx):
            k = xx.argmax()
            if best is None or xx[k] > best[0]:
                best = (int(xx[k]), int(yy[k] + lo))
    if best:
        m["hand_point"] = [best[0] - ox, best[1] - oy]
json.dump(m, open(a.out + ".json", "w"), ensure_ascii=False, indent=1)
bg = Image.new("RGBA", (S.shape[1], S.shape[0]), (236, 226, 206, 255)); bg.alpha_composite(Image.fromarray(S))
bg.resize((S.shape[1] * 4, S.shape[0] * 4), Image.NEAREST).save(a.out + "_x4.png")
print(json.dumps({k: m.get(k) for k in ("frames", "frame_w", "frame_h", "seat_point", "hand_point", "pixel_size_src")}, ensure_ascii=False))
