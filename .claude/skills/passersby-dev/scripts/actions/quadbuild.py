"""四足动物行走/快步：AI 照 quadguide 模特画的 8 帧（2 行 × 4 列，洋红底）→ 真像素横排条 + 根运动 + 爪滑检查。

    python quadbuild.py <ai.png> <guide.json> <out_prefix> --height H [--cell W] [--colors 24] [--fps F] [--blend 0.5]

1 守门：原图背景必须是洋红（黑底/发光底淘汰）
2 pixelize（项目版，固定像素尺寸，2×4 按间隙切格，不清格边）→ 8 帧
3 去洋红杂边；每帧按躯干（高度 30–62% 的行）质心横向对齐；所有帧最低点对齐到同一底线
4 根运动 = 实测着地爪后移（每对帧取最接近设计值的那只爪），向均值收拢 blend；测不准的帧用设计值
5 回放测爪滑 slip（着地爪相对地面的移动，px）；触地爪团数 < 2 的帧报警（腿糊在一起/爪被切）
输出 <out>.png/.json/_x4.png。
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image
PXDIR = pathlib.Path(__file__).resolve().parent.parent          # scripts/（项目版 pixelize.py）
ap = argparse.ArgumentParser()
ap.add_argument("ai"); ap.add_argument("guide"); ap.add_argument("out")
ap.add_argument("--height", type=int, required=True); ap.add_argument("--cell", type=int, default=0)
ap.add_argument("--colors", type=int, default=24); ap.add_argument("--blend", type=float, default=0.5)
ap.add_argument("--fps", type=float, default=0); ap.add_argument("--keep", type=float, default=0.002)
ap.add_argument("--torso", default="0.30,0.62", help="躯干对齐用的行范围（占身高比例，从顶上算）")
a = ap.parse_args()
g = json.load(open(a.guide, encoding="utf-8"))
cols, rows = g.get("grid", [8, 1]); nf = cols * rows
out = pathlib.Path(a.out); work = out.parent / (out.name + "_work"); work.mkdir(parents=True, exist_ok=True)
_im = Image.open(a.ai)
_al = np.array(_im.convert("RGBA"))[..., 3]
if (_al < 128).mean() > 0.5:
    # 透明底出图（extra background=transparent，11-27 起首选）：没有洋红光晕问题；半透明的晕 alpha<128 直接当背景
    pass
else:
    src = np.array(_im.convert("RGB")).astype(int)
    c = np.concatenate([src[:12, :12].reshape(-1, 3), src[:12, -12:].reshape(-1, 3), src[-12:, :12].reshape(-1, 3), src[-12:, -12:].reshape(-1, 3)])
    m = np.median(c, axis=0)
    if not (m[0] > 170 and m[2] > 170 and m[1] < 110):
        sys.exit(f"FAIL 原图背景不是洋红（角落 {m.astype(int).tolist()}），淘汰")
    # 光晕守门：洋红底上 AI 常给动物加一圈暗紫/发光的晕（11-27 两批 32 张里 22 张），角落还是洋红，必须看整张的纯洋红占比
    pure = ((src[..., 0] > 200) & (src[..., 2] > 200) & (src[..., 1] < 80)).mean()
    if pure < 0.6:
        sys.exit(f"FAIL 纯洋红只占 {pure:.0%}（有光晕/暗底），淘汰")
r = subprocess.run([sys.executable, str(PXDIR / "pixelize.py"), a.ai, str(work), "--rows", str(rows), "--cols", str(cols),
                    "--colors", str(a.colors), "--height", str(a.height), "--fixed", "--layout", "keep", "--anchor", "feet",
                    "--keep", str(a.keep), "--no-border-clear"], capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-2000:])
rep = json.load(open(work / "report.json"))
P = rep["global_pixel_size"]
S = np.array(Image.open(work / "sheet.png").convert("RGBA"))
for _ in range(12):   # 洋红杂边：贴透明的删掉，里面的换成邻色
    rr, gg, bb, aa = (S[..., i].astype(int) for i in range(4))
    mag = (aa > 0) & (rr - gg > 35) & (bb - gg > 35) & (np.abs(rr - bb) < 110)
    if not mag.any():
        break
    for y, x in zip(*np.nonzero(mag)):
        nb = [(y + dy, x + dx) for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)) if 0 <= y + dy < S.shape[0] and 0 <= x + dx < S.shape[1]]
        if any(S[q][3] == 0 for q in nb):
            S[y, x, 3] = 0
        else:
            ok = [q for q in nb if not mag[q] and S[q][3] > 0]
            if ok:
                S[y, x] = S[ok[0]]
S[..., 3] = np.where(S[..., 3] > 0, 255, 0)
fw0 = S.shape[1] // nf; Hh = S.shape[0]
wid = max(int(np.ptp(np.nonzero((S[:, i * fw0:(i + 1) * fw0, 3] > 0).any(0))[0])) + 1 for i in range(nf))
W = a.cell or int(wid + 10 + (wid + 10) % 2); cx = W // 2
t0, t1 = map(float, a.torso.split(","))
def specks(f, maxsz=6, gap=2):
    """离主体 > gap 像素的小碎点（≤ maxsz 像素）删掉：相邻帧的尾巴尖、杂点（11-27 猫帧旁的橙色小竖条）。"""
    al = f[..., 3] > 0; H, Wd = al.shape; seen = np.zeros_like(al); comps = []
    for sy, sx in zip(*np.nonzero(al)):
        if seen[sy, sx]: continue
        st = [(sy, sx)]; seen[sy, sx] = True; pts = []
        while st:
            y, x = st.pop(); pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < Wd and al[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True; st.append((yy, xx))
        comps.append(pts)
    if len(comps) < 2: return f
    comps.sort(key=len, reverse=True); main = np.array(comps[0])
    for c in comps[1:]:
        if len(c) <= maxsz:
            d = min(np.abs(main - np.array(p)).max(1).min() for p in c)
            if d > gap:
                for y, x in c: f[y, x] = 0
    return f


reg = []
for i in range(nf):
    f = specks(S[:, i * fw0:(i + 1) * fw0].copy())
    al = f[..., 3] > 0; ys = np.nonzero(al.any(1))[0]; top = ys.min(); hh = ys.max() - top
    xs = np.nonzero(al[top + int(hh * t0): top + int(hh * t1)])[1]
    dx = int(round(cx - xs.mean()))
    cv = np.zeros((Hh, W, 4), np.uint8)
    for x in range(fw0):
        if 0 <= x + dx < W:
            cv[:, x + dx] = f[:, x]
    sh = (Hh - 1) - np.nonzero((cv[..., 3] > 0).any(1))[0].max()
    if sh:
        cv = np.roll(cv, sh, axis=0)
        if sh > 0: cv[:sh] = 0
        else: cv[sh:] = 0
    reg.append(cv)


def paws(fr, band=2):
    al = fr[..., 3] > 0; yb = np.nonzero(al.any(1))[0].max()
    xs = np.nonzero(al[yb - band:yb + 1].any(0))[0]
    return [(q[0] + q[-1]) / 2 for q in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1) if len(q)]


guide_rm = np.array(g["root_motion_img_px"], float) / P
meas = []
for i in range(nf):
    A, B = paws(reg[i]), paws(reg[(i + 1) % nf])
    cand = [xa - xb for xa in A for xb in B]
    meas.append(min(cand, key=lambda d: abs(d - guide_rm[i])) if cand else guide_rm[i])
meas = np.array(meas)
bad = np.abs(meas - guide_rm) > 0.6 * np.abs(guide_rm)
meas = np.where(bad, guide_rm, meas)
rm = meas * (1 - a.blend) + meas.mean() * a.blend
slips = []
for i in range(nf):
    A, B = paws(reg[i]), paws(reg[(i + 1) % nf])
    slips.append(round(float(min((abs(xb + rm[i] - xa) for xa in A for xb in B), default=0)), 2))
few = [i for i in range(nf) if len(paws(reg[i], 1)) < 2]
S2 = np.concatenate(reg, axis=1)
al = S2[..., 3] > 0; ys = np.nonzero(al.any(1))[0]
S2 = S2[max(0, ys.min() - 1):]; Hh = S2.shape[0]
Image.fromarray(S2).save(str(out) + ".png")
fps = a.fps or g.get("fps", 10)
meta = {"frames": nf, "fps": fps, "frame_w": W, "frame_h": Hh, "origin": [cx, Hh - 1], "root_motion_px": [round(float(x), 3) for x in rm],
        "axis": "x", "loop": True, "view": "side", "pixel_size_src": P, "measured_px": [round(float(x), 2) for x in meas],
        "guide_px": [round(float(x), 2) for x in guide_rm], "bad_frames": [int(i) for i in np.nonzero(bad)[0]],
        "cycle_px": round(float(rm.sum()), 2), "speed_px_s": round(float(rm.sum()) / nf * fps, 1),
        "slip_px": slips, "slip_mean_px": round(float(np.mean(slips)), 2), "few_paw_frames": few,
        "gait": g.get("gait"), "species": g.get("species"), "duty": g.get("duty")}
json.dump(meta, open(str(out) + ".json", "w"), ensure_ascii=False, indent=1)
bg = Image.new("RGBA", (S2.shape[1], S2.shape[0]), (236, 226, 206, 255)); bg.alpha_composite(Image.fromarray(S2))
bg.resize((S2.shape[1] * 4, S2.shape[0] * 4), Image.NEAREST).save(str(out) + "_x4.png")
print(json.dumps({k: meta[k] for k in ("frame_w", "frame_h", "measured_px", "guide_px", "bad_frames", "speed_px_s", "slip_mean_px", "few_paw_frames")}, ensure_ascii=False))
