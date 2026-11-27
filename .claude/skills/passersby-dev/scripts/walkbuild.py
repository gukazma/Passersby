"""横版行走/跑步帧：AI 照姿势模特画的 8 帧横排 → 真像素精灵条 + 根运动 + 脚滑检查。

    python walkbuild.py <ai.png> <guide.json> <out_prefix> [--height 110] [--cell 100] [--colors 32] [--blend 0.5]
1 pixelize（固定像素尺寸、按间隙切帧、脚底对齐）2 去洋红杂边 3 每帧按上半身质心横向对齐到格子中线
4 根运动 = 实测着地脚后移（每对帧取最接近模特设计值的那只脚），向均值收拢 blend 5 回放测脚滑 slip。
输出 <out>.png（横排，每帧 cell 宽）、<out>.json、<out>_x4.png。
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image
SK = pathlib.Path.home() / ".claude/skills/pixel-sprite-anim/scripts"
ap = argparse.ArgumentParser()
ap.add_argument("ai"); ap.add_argument("guide"); ap.add_argument("out")
ap.add_argument("--height", type=int, default=110); ap.add_argument("--cell", type=int, default=100)
ap.add_argument("--colors", type=int, default=32); ap.add_argument("--blend", type=float, default=0.5)
ap.add_argument("--frames", type=int, default=8)
a = ap.parse_args()
g = json.load(open(a.guide, encoding="utf-8"))
out = pathlib.Path(a.out); work = out.parent / (out.name + "_work"); work.mkdir(parents=True, exist_ok=True)
nf = a.frames
r = subprocess.run([sys.executable, str(SK / "pixelize.py"), a.ai, str(work), "--rows", "1", "--cols", str(nf),
                    "--colors", str(a.colors), "--cell", f"{a.cell}x{a.height + 8}", "--height", str(a.height), "--fixed",
                    "--layout", "keep", "--anchor", "feet", "--keep", "0.01"], capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-2000:])
P = json.load(open(work / "report.json"))["global_pixel_size"]
S = np.array(Image.open(work / "sheet.png").convert("RGBA"))
rr, gg, bb, aa = (S[..., i].astype(int) for i in range(4))
mag = (aa > 0) & (rr - gg > 35) & (bb - gg > 35) & (np.abs(rr - bb) < 110)
for y, x in zip(*np.nonzero(mag)):
    nb = [(y + dy, x + dx) for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)) if 0 <= y + dy < S.shape[0] and 0 <= x + dx < S.shape[1]]
    if any(S[q][3] == 0 for q in nb):
        S[y, x, 3] = 0
    else:
        ok = [q for q in nb if not mag[q] and S[q][3] > 0]
        if ok:
            S[y, x] = S[ok[0]]
S[..., 3] = np.where(S[..., 3] > 0, 255, 0)
fw0 = S.shape[1] // nf; Hh = S.shape[0]; W = a.cell; cx = W // 2
reg = []
for i in range(nf):
    f = S[:, i * fw0:(i + 1) * fw0]
    al = f[..., 3] > 0; ys = np.nonzero(al.any(1))[0]; top = ys.min(); hh = ys.max() - top
    xs = np.nonzero(al[top + int(hh * 0.12): top + int(hh * 0.5)])[1]
    dx = int(round(cx - xs.mean()))
    cv = np.zeros((Hh, W, 4), np.uint8)
    for x in range(fw0):
        if 0 <= x + dx < W:
            cv[:, x + dx] = f[:, x]
    reg.append(cv)
S = np.concatenate(reg, axis=1)
Image.fromarray(S).save(str(out) + ".png")
def feet(fr):
    al = fr[..., 3] > 0; ys = np.nonzero(al.any(1))[0]; yb = ys.max()
    xs = np.nonzero(al[yb - 2:yb + 1].any(0))[0]
    return [(q[0] + q[-1]) / 2 for q in np.split(xs, np.nonzero(np.diff(xs) > 2)[0] + 1) if len(q)]
guide_rm = np.array(g["root_motion_img_px"], float) / P
meas = []
for i in range(nf):
    A, B = feet(reg[i]), feet(reg[(i + 1) % nf])
    c = [xa - xb for xa in A for xb in B]
    meas.append(min(c, key=lambda d: abs(d - guide_rm[i])) if c else guide_rm[i])
meas = np.array(meas)
rm = meas * (1 - a.blend) + meas.mean() * a.blend
slips = []
for i in range(nf):
    A, B = feet(reg[i]), feet(reg[(i + 1) % nf])
    slips.append(round(float(min((abs(xb + rm[i] - xa) for xa in A for xb in B), default=0)), 2))
fps = g.get("fps", 12)
meta = {"frames": nf, "frame_w": W, "frame_h": Hh, "pixel_size_src": P, "fps": fps,
        "root_motion_px": [round(float(x), 3) for x in rm], "measured_px": [round(float(x), 2) for x in meas],
        "guide_px": [round(float(x), 2) for x in guide_rm], "cycle_px": round(float(rm.sum()), 2),
        "speed_px_s": round(float(rm.sum()) / nf * fps, 1), "slip_px": slips, "slip_mean_px": round(float(np.mean(slips)), 2),
        "origin": [cx, Hh - 1], "profile": g.get("profile")}
json.dump(meta, open(str(out) + ".json", "w"), ensure_ascii=False, indent=1)
bg = Image.new("RGBA", (S.shape[1], S.shape[0]), (236, 226, 206, 255)); bg.alpha_composite(Image.fromarray(S))
bg.resize((S.shape[1] * 4, S.shape[0] * 4), Image.NEAREST).save(str(out) + "_x4.png")
print(json.dumps({k: meta[k] for k in ("measured_px", "guide_px", "cycle_px", "speed_px_s", "slip_mean_px")}, ensure_ascii=False))
