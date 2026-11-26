"""8 帧行走的根运动测量 + 去卡顿 + 脚滑校验（F 方案：身体只在换帧时按该帧位移前进）。

    python rootmotion.py <strip.png> <right|left|down|up> [--blend 0.5 --cycle 30 --anim-fps 12.5] [--inplace]
strip = 8 帧横排（每帧 32x40）。输出 JSON：
  measured_px     实测：帧 k→k+1 落地脚后移量（= 身体应前进量）
  root_motion_px  最终表：缩放到统一循环、向平均值收拢 blend 后的位移（游戏/视频用这个）
  min_step_px/cv  最终表的最小一步和离散系数（min ≥ 2.4、cv ≤ 0.25 才不顿）
  slip_mean_px    最终表播放时落地脚平均滑动（≤ 0.5 合格）
"""
import argparse, json
import numpy as np
from PIL import Image

AX = {"right": ("x", 1), "left": ("x", -1), "down": ("y", 1), "up": ("y", -1)}


def blobs(al, axis, foot_rows):
    """脚：最下面 foot_rows 行里的不透明列段。返回 [(x中心, 沿运动轴的位置)]：横向 = x 中心；纵向 = 该段的最低行。"""
    ys = np.nonzero(al.any(1))[0]
    yb = ys.max()
    band = al[yb - foot_rows + 1:yb + 1]
    xs = np.nonzero(band.any(0))[0]
    out = []
    for r in np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1):
        if len(r) == 0:
            continue
        xc = (r[0] + r[-1]) / 2
        if axis == "x":
            out.append((xc, xc))
        else:
            col = al[:, r[0]:r[-1] + 1]
            out.append((xc, float(np.nonzero(col.any(1))[0].max())))
    return out


def measure(frames, direction, foot_rows):
    axis, sg = AX[direction]
    B = [blobs(f, axis, foot_rows) for f in frames]
    n = len(frames)
    e = 3.0
    for _ in range(4):  # 期望步距迭代：在合理范围内选最接近期望的配对
        ds = []
        for k in range(n):
            cands = []
            for xa, pa in B[k]:
                for xb, pb in B[(k + 1) % n]:
                    if axis == "y" and abs(xa - xb) > 4:  # 纵向：只和同一只脚配对
                        continue
                    d = sg * (pa - pb)
                    if -1.5 <= d <= 9:
                        cands.append(d)
            ds.append(min(cands, key=lambda d: abs(d - e)) if cands else e)
        e = max(1.0, float(np.mean(ds)))
    return [max(0.0, round(d * 2) / 2) for d in ds], B


def slip(frames, direction, d, foot_rows, speed=38.0, fps=25, secs=20):
    axis, sg = AX[direction]
    cyc = sum(d)
    if cyc <= 0:  # 原地踏步全为 0：没有可模拟的位移
        return 0.0, 0.0, 0.0
    L = np.concatenate([[0], np.cumsum(d)])
    anim = speed / cyc * len(frames)
    prev, s = None, []
    for i in range(int(secs * fps)):
        n = int(i / fps * anim)
        k = n % len(frames)
        pos = round((n // len(frames)) * cyc + L[k])
        world = [(xc, pa + sg * pos) for xc, pa in blobs(frames[k], axis, foot_rows)]
        if prev is not None:
            best = min((abs(a[1] - b[1]) for a in world for b in prev if axis == "x" or abs(a[0] - b[0]) <= 4), default=0)
            s.append(best)
        prev = world
    return float(np.mean(s)), float(np.max(s)), anim


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("strip"); ap.add_argument("direction", choices=list(AX))
    ap.add_argument("--fw", type=int, default=32); ap.add_argument("--speed", type=float, default=38)
    ap.add_argument("--rows", type=int, default=0, help="脚的取样行数；0 = 横向 3 / 纵向 6")
    ap.add_argument("--blend", type=float, default=0.5, help="去卡顿：实测位移向平均值收拢的比例（0 = 纯实测，1 = 均匀）")
    ap.add_argument("--cycle", type=float, default=30.0, help="统一的一循环位移（像素），所有方向相同 → 速度一致")
    ap.add_argument("--anim-fps", type=float, default=12.5, help="动画帧率（视频 25fps 用 12.5；Godot 60fps 用 12）")
    ap.add_argument("--inplace", action="store_true", help="原地踏步的正背面：不测，直接均匀 cycle/8")
    a = ap.parse_args()
    al = np.array(Image.open(a.strip).convert("RGBA"))[..., 3] > 0
    frames = [al[:, i * a.fw:(i + 1) * a.fw] for i in range(al.shape[1] // a.fw)]
    fr = a.rows or (3 if AX[a.direction][0] == "x" else 6)
    d, B = measure(frames, a.direction, fr)
    m, mx, anim = slip(frames, a.direction, d, fr, a.speed)
    # 最终表：缩放到统一循环 → 向平均值收拢 → 再归一（末项补差，保证总和 = cycle）
    if a.inplace or sum(d) < 8:
        fin = [round(a.cycle / 8, 3)] * 8
    else:
        arr = np.array(d) * a.cycle / sum(d)
        arr = (1 - a.blend) * arr + a.blend * arr.mean()
        arr = np.round(arr * a.cycle / arr.sum(), 2)
        arr[-1] = round(a.cycle - arr[:-1].sum(), 2)
        fin = arr.tolist()
    speed = a.cycle * a.anim_fps / 8
    fm, fmx, _ = slip(frames, a.direction, fin, fr, speed)
    fa = np.array(fin)
    print(json.dumps({"direction": a.direction, "measured_px": d, "measured_cycle_px": sum(d),
                      "measured_cv": round(float(np.std(d) / max(np.mean(d), 1e-6)), 2),
                      "root_motion_px": fin, "cycle_px": a.cycle, "anim_fps": a.anim_fps, "speed_px_per_s": speed,
                      "min_step_px": float(fa.min()), "cv": round(float(fa.std() / fa.mean()), 2),
                      "slip_mean_px": round(fm, 2), "slip_max_px": fmx, "slip_pure_measured_px": round(m, 2),
                      "feet": [[(round(x, 1), p) for x, p in b] for b in B]}, ensure_ascii=False))
