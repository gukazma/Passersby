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
PXDIR = pathlib.Path.home() / "pw/skill/passersby-dev/scripts"
ap = argparse.ArgumentParser()
ap.add_argument("ai"); ap.add_argument("guide"); ap.add_argument("out")
ap.add_argument("--height", type=int, default=110); ap.add_argument("--cell", type=int, default=100)
ap.add_argument("--colors", type=int, default=32); ap.add_argument("--blend", type=float, default=0.5)
ap.add_argument("--frames", type=int, default=8)
ap.add_argument("--keep", type=float, default=0.002, help="小于最大连通块该比例的碎块删掉；太大会把和腿断开的脚当碎块删掉（11-27 叶俊脚被切）")
a = ap.parse_args()
g = json.load(open(a.guide, encoding="utf-8"))
out = pathlib.Path(a.out); work = out.parent / (out.name + "_work"); work.mkdir(parents=True, exist_ok=True)
nf = a.frames
# 守门：原图背景必须是洋红；黑底/发光底的版本（AI 常见失败）直接淘汰，不进流水线
_src = np.array(Image.open(a.ai).convert("RGB")).astype(int)
_c = np.concatenate([_src[:12, :12].reshape(-1, 3), _src[:12, -12:].reshape(-1, 3), _src[-12:, :12].reshape(-1, 3), _src[-12:, -12:].reshape(-1, 3)])
_m = np.median(_c, axis=0)
if not (_m[0] > 170 and _m[2] > 170 and _m[1] < 110):
    sys.exit(f"FAIL 原图背景不是洋红（角落颜色 {_m.astype(int).tolist()}），淘汰这一版")
# 注：pixelize 默认清掉每格四周 2 像素（去网格残影），AI 把相邻两帧画得很近时会把脚尖当格边清掉（11-27 叶俊脚被切）。
# 这里用项目自带的 pixelize（加了 --no-border-clear），按间隙切帧本来就不需要清格边。
r = subprocess.run([sys.executable, str(PXDIR / "pixelize.py"), a.ai, str(work), "--rows", "1", "--cols", str(nf),
                    "--colors", str(a.colors), "--cell", f"{a.cell}x{a.height + 8}", "--height", str(a.height), "--fixed",
                    "--layout", "keep", "--anchor", "feet", "--keep", str(a.keep), "--no-border-clear"], capture_output=True, text=True)
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
# 行走：每帧脚底对齐到同一条底线（pixelize 的脚底对齐偶尔会错 5–10 px，人会一走一沉，11-27 叶俊）
if g.get("mode", "walk") != "run" and g.get("axis", "x") != "y":
    for i, f in enumerate(reg):
        al = f[..., 3] > 0; ys = np.nonzero(al.any(1))[0]
        sh = (Hh - 1) - ys.max()
        if sh:
            reg[i] = np.roll(f, sh, axis=0)
            if sh > 0: reg[i][:sh] = 0
            else: reg[i][sh:] = 0
S = np.concatenate(reg, axis=1)
Image.fromarray(S).save(str(out) + ".png")
def feet(fr):
    al = fr[..., 3] > 0; ys = np.nonzero(al.any(1))[0]; yb = ys.max()
    xs = np.nonzero(al[yb - 2:yb + 1].any(0))[0]
    return [(q[0] + q[-1]) / 2 for q in np.split(xs, np.nonzero(np.diff(xs) > 2)[0] + 1) if len(q)]
guide_rm = np.array(g["root_motion_img_px"], float) / P
DX = g["dir_screen"][0] if g.get("axis") == "dir" else 1.0   # 斜走：脚在画面上的横向位移 = 前进量 × cos
meas = []
for i in range(nf):
    A, B = feet(reg[i]), feet(reg[(i + 1) % nf])
    c = [xa - xb for xa in A for xb in B]
    meas.append((min(c, key=lambda d: abs(d - guide_rm[i] * DX)) if c else guide_rm[i] * DX) / DX)
meas = np.array(meas)
bad = np.abs(meas - guide_rm * 1.0) > 0.6 * np.abs(guide_rm)   # 腾空帧、测错的帧：用模特设计值
meas = np.where(bad, guide_rm, meas)
if g.get('axis') == 'y' or (g.get('axis') == 'dir' and (meas <= 0.5).any()):   # 正背面/测不准的斜走：用模特设计值
    meas = guide_rm.copy()
rm = meas * (1 - a.blend) + meas.mean() * a.blend
slips = []
for i in range(nf):
    A, B = feet(reg[i]), feet(reg[(i + 1) % nf])
    slips.append(round(float(min((abs(xb + rm[i] * DX - xa) for xa in A for xb in B), default=0)), 2))
# 守门：侧面走/跑每帧地面附近两只脚的大小要相近（腾空帧除外），否则多半是脚被切/被当碎块删了
cut_frames = []
for i, f in enumerate(reg):
    if i not in (0, nf // 2):          # 只查触地帧（双脚都该在地上）；经过帧抬起的脚本来就小
        continue
    al = f[..., 3] > 0; ys = np.nonzero(al.any(1))[0]
    band_ = al[max(0, ys.max() - 7):ys.max() + 1]; cols = np.nonzero(band_.any(0))[0]
    bl = [q for q in np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1) if len(q)]
    if len(bl) >= 2:
        sz = sorted(int(band_[:, q[0]:q[-1] + 1].sum()) for q in bl)
        if sz[-2] < 0.3 * sz[-1] and sz[-2] < 25:
            cut_frames.append(i)
if cut_frames and g.get("axis", "x") == "x" and g.get("mode", "walk") != "run":
    print("WARN 脚可能被切的帧:", cut_frames)
fps = g.get("fps", 12)
meta = {"frames": nf, "frame_w": W, "frame_h": Hh, "pixel_size_src": P, "fps": fps,
        "root_motion_px": [round(float(x), 3) for x in rm], "measured_px": [round(float(x), 2) for x in meas],
        "guide_px": [round(float(x), 2) for x in guide_rm], "cycle_px": round(float(rm.sum()), 2),
        "speed_px_s": round(float(rm.sum()) / nf * fps, 1), "slip_px": slips, "slip_mean_px": round(float(np.mean(slips)), 2),
        "origin": [cx, Hh - 1], "axis": g.get("axis", "x"), "dir_screen": g.get("dir_screen"), "profile": g.get("profile")}
json.dump(meta, open(str(out) + ".json", "w"), ensure_ascii=False, indent=1)
bg = Image.new("RGBA", (S.shape[1], S.shape[0]), (236, 226, 206, 255)); bg.alpha_composite(Image.fromarray(S))
bg.resize((S.shape[1] * 4, S.shape[0] * 4), Image.NEAREST).save(str(out) + "_x4.png")
print(json.dumps({k: meta[k] for k in ("measured_px", "guide_px", "cycle_px", "speed_px_s", "slip_mean_px")}, ensure_ascii=False))
