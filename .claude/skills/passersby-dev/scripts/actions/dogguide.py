"""四足（狗）侧面行走姿势模特，朝右，8 帧。四拍步态（lateral sequence）：左后 0、左前 25%、右后 50%、右前 75%；
每条腿支撑占 62%，支撑期爪子相对躯干匀速后移 = 身体前进；摆动期抬起前送。
浅灰 = 近侧（左）腿，深灰 = 远侧（右）腿。前腿腕关节向前凸，后腿跗关节向后凸。

    python dogguide.py out.png out.json [--cell 384x1024] [--shoulder 180]
"""
import argparse, json, math
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("meta")
ap.add_argument("--cell", default="384x1024"); ap.add_argument("--shoulder", type=float, default=110)
ap.add_argument("--stride", type=float, default=0.62, help="步幅 / 肩高")
ap.add_argument("--gait", default="walk", choices=["walk", "trot"])
a = ap.parse_args()
CW, CH = map(int, a.cell.split("x")); N = 8; Hs = a.shoulder
L1, L2 = Hs * 0.55, Hs * 0.55           # 腿两节
body_len = Hs * 1.25
S = Hs * a.stride                        # 一个周期里每只脚的步幅（支撑期后移量）
DUTY = 0.62 if a.gait == "walk" else 0.45
PH = {"LH": 0.0, "LF": 0.25, "RH": 0.5, "RF": 0.75} if a.gait == "walk" else {"LH": 0.0, "RF": 0.0, "RH": 0.5, "LF": 0.5}
def foot(ph):
    """相对髋/肩的爪子位置 (dx, 离地高度)。"""
    ph %= 1.0
    if ph < DUTY:
        t = ph / DUTY
        return S / 2 - S * t, 0.0
    t = (ph - DUTY) / (1 - DUTY)
    return -S / 2 + S * t, math.sin(math.pi * t) * Hs * (0.16 if a.gait == "walk" else 0.24)
def ik(hip, paw, bend):
    dx, dy = paw[0] - hip[0], paw[1] - hip[1]; dist = min(math.hypot(dx, dy), L1 + L2 - 1e-3)
    a0 = math.atan2(dy, dx); c = (L1 ** 2 + dist ** 2 - L2 ** 2) / (2 * L1 * dist); c = max(-1, min(1, c))
    ang = a0 - bend * math.acos(c)        # bend=+1 关节向前凸（画面右），-1 向后
    return (hip[0] + L1 * math.cos(ang), hip[1] + L1 * math.sin(ang))
img = Image.new("RGB", (CW * N, CH), (255, 0, 255)); d = ImageDraw.Draw(img)
NEAR, FAR, BODY = (215, 215, 215), (90, 90, 90), (165, 165, 165)
def cap(p, q, w, c):
    d.line([p, q], fill=c, width=int(w)); r = w / 2
    for z in (p, q): d.ellipse([z[0] - r, z[1] - r, z[0] + r, z[1] + r], fill=c)
ground = CH - 80; W = Hs * 0.12
for i in range(N):
    ph = i / N
    cx = CW * i + CW * 0.45
    bob = 0.0
    hip_y = ground - (L1 + L2) * 0.93 + bob
    shoulder = (cx + body_len / 2, hip_y); hip = (cx - body_len / 2, hip_y)
    legs = {}
    for k, off in PH.items():
        base = shoulder if k.endswith("F") else hip
        fx, fy = foot(ph + 1 - off)
        paw = (base[0] + fx, ground - fy - W / 2)
        knee = ik(base, paw, +1 if k.endswith("F") else -1)
        legs[k] = (base, knee, paw)
    for k in ("RH", "RF"):
        b, kn, p = legs[k]; cap(b, kn, W * 1.2, FAR); cap(kn, p, W, FAR); cap(p, (p[0] + W * 1.2, p[1]), W, FAR)
    d.ellipse([hip[0] - Hs * 0.22, hip_y - Hs * 0.28, shoulder[0] + Hs * 0.22, hip_y + Hs * 0.2], fill=BODY)   # 躯干
    hd = (shoulder[0] + Hs * 0.35, hip_y - Hs * 0.42)
    cap((shoulder[0] + Hs * 0.05, hip_y - Hs * 0.1), hd, Hs * 0.22, BODY)                                   # 脖子
    d.ellipse([hd[0] - Hs * 0.2, hd[1] - Hs * 0.2, hd[0] + Hs * 0.2, hd[1] + Hs * 0.2], fill=BODY)           # 头
    cap(hd, (hd[0] + Hs * 0.3, hd[1] + Hs * 0.08), Hs * 0.15, BODY)                                         # 嘴
    d.polygon([(hd[0] - Hs * 0.12, hd[1] - Hs * 0.12), (hd[0] - Hs * 0.02, hd[1] - Hs * 0.42), (hd[0] + Hs * 0.06, hd[1] - Hs * 0.1)], fill=BODY)  # 耳
    tail = [(hip[0] - Hs * 0.15, hip_y - Hs * 0.15), (hip[0] - Hs * 0.32, hip_y - Hs * 0.42), (hip[0] - Hs * 0.18, hip_y - Hs * 0.55)]
    d.line(tail, fill=BODY, width=int(Hs * 0.09), joint="curve")
    for k in ("LH", "LF"):
        b, kn, p = legs[k]; cap(b, kn, W * 1.2, NEAR); cap(kn, p, W, NEAR); cap(p, (p[0] + W * 1.2, p[1]), W, NEAR)
rm = [round(S / N, 2)] * N   # 支撑爪匀速后移：每帧身体前进 S/8
json.dump({"gait": a.gait, "frames": N, "fps": 12, "cell": [CW, CH], "root_motion_img_px": rm, "axis": "x", "shoulder_img_px": Hs,
           "note": "狗四拍步态 LH-LF-RH-RF，浅灰近侧"}, open(a.meta, "w"), ensure_ascii=False, indent=1)
img.save(a.out); print("rm", rm)
