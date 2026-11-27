"""侧面（朝右）步态模特图 —— 关节角取自正常步态生物力学常模（Perry / Winter：髋屈伸、膝屈、踝背屈随步态周期%变化），
给 AI 当姿势参考，同时输出根运动（支撑脚触地点每帧后移量）。

    python poseguide.py out.png out.json [--frames 8] [--cell 384x1024] [--height 700] [--preview prev.png]
浅灰 = 近侧肢体（画在身体前），深灰 = 远侧（画在身体后）。近侧腿 0% = 脚跟着地；远侧腿相位 +50%。
脚是跟着小腿转的刚体（踝角 = 小腿方向 + 90° + 背屈），不会折叠到小腿上。
"""
import argparse, json, math
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("meta")
ap.add_argument("--frames", type=int, default=8)
ap.add_argument("--cell", default="384x1024")
ap.add_argument("--height", type=float, default=700)
ap.add_argument("--profile", help="步态档案 json（见 gait_profiles.json），覆盖默认值")
a = ap.parse_args()
PF = {"stride": 1.0, "knee_load": 1.0, "knee_swing": 1.0, "ankle": 1.0, "lean": 2.0, "head_fwd": 0.0, "stoop": 0.0,
      "arm_swing": 1.0, "elbow": 12.0, "arm_mode": "swing", "bob": 1.0, "girth": 1.0, "leg_len": 1.0, "head": 1.0,
      "torso": 1.0, "fps": 12, "height_m": 1.7}
if a.profile:
    PF.update(json.load(open(a.profile, encoding="utf-8")))
CW, CH = map(int, a.cell.split("x")); N = a.frames; H = a.height * PF["height_m"] / 1.7
# 常模关键点（步态周期 %，角度）。髋：+屈；膝：+屈；踝：+背屈。足趾离地 ≈ 62%。
HIP = [(0, 30), (10, 28), (30, 8), (50, -10), (56, -9), (62, -2), (75, 20), (87, 32), (100, 30)]
KNEE = [(0, 5), (15, 18), (30, 7), (40, 4), (50, 9), (62, 38), (72, 60), (80, 52), (90, 20), (97, 5), (100, 5)]
ANK = [(0, 0), (7, -6), (30, 5), (45, 10), (52, 6), (62, -16), (70, -10), (80, 0), (90, 2), (100, 0)]
STANCE_END = 62

def curve(kp, p):
    """周期 Catmull-Rom 插值。"""
    p %= 100
    xs = [k[0] for k in kp]; ys = [k[1] for k in kp]
    for i in range(len(kp) - 1):
        if xs[i] <= p <= xs[i + 1]:
            break
    def Y(j):
        n = len(kp) - 1
        return ys[j % n] if 0 <= j <= n else ys[j % n]
    x0, x1 = xs[i], xs[i + 1]; t = (p - x0) / (x1 - x0)
    p0, p1, p2, p3 = Y(i - 1 if i > 0 else len(kp) - 2), ys[i], ys[i + 1], Y(i + 2 if i + 2 < len(kp) else 1)
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)

u = H / 7.0
L = PF["leg_len"]
thigh, shin, foot_l = 1.6 * u * L, 1.55 * u * L, 0.8 * u
uarm, farm, torso_h, head_r = 1.05 * u * PF["torso"], 0.95 * u * PF["torso"], 2.0 * u * PF["torso"], 0.95 * u * PF["head"]
def vec(ang, L):  # 0 = 竖直向下，正 = 向前
    return (L * math.sin(math.radians(ang)), L * math.cos(math.radians(ang)))
def add(p, v, k=1.0):
    return (p[0] + v[0] * k, p[1] + v[1] * k)

def joint(pct):
    h = 10 + (curve(HIP, pct) - 10) * PF["stride"]          # 髋绕 10° 中心缩放：步幅
    k = curve(KNEE, pct)
    k = k * (PF["knee_swing"] if 55 <= pct % 100 <= 95 else PF["knee_load"])   # 摆动相膝屈 = 抬脚高度；承重相膝屈
    an = curve(ANK, pct) * PF["ankle"]
    return h, k, an

def leg(hip, pct):
    h, k, an = joint(pct)
    knee = add(hip, vec(h, thigh)); s = h - k
    ankle = add(knee, vec(s, shin))
    f = s + 90 + an                       # 脚背方向
    fv = vec(f, foot_l); down = vec(s, 0.16 * u)
    heel = add(add(ankle, fv, -0.22), down); toe = add(add(ankle, fv, 0.78), down)
    return knee, ankle, heel, toe

frames = []
for i in range(N):
    pn = 100.0 * i / N; pf = pn + 50
    ln, lf = leg((0, 0), pn), leg((0, 0), pf)
    low = max(ln[2][1], ln[3][1], lf[2][1], lf[3][1])
    frames.append((pn, pf, low, ln, lf))

rm = []
for i in range(N):   # 两帧都处于支撑相的那条腿，其踝关节相对髋的后移 = 身体前进
    j = (i + 1) % N; pn = 100.0 * i / N; pn2 = pn + 100.0 / N
    near_ok = pn < STANCE_END and pn2 <= STANCE_END + 1e-6
    k = 3 if near_ok else 4
    rm.append(round(frames[i][k][1][0] - frames[j][k][1][0], 2))
img = Image.new("RGB", (CW * N, CH), (255, 0, 255)); d = ImageDraw.Draw(img)
NEAR, FAR, BODY = (215, 215, 215), (90, 90, 90), (165, 165, 165)
def cap(p, q, w, c):
    d.line([p, q], fill=c, width=int(w)); r = w / 2
    for z in (p, q): d.ellipse([z[0] - r, z[1] - r, z[0] + r, z[1] + r], fill=c)
ground = CH - 70; W = u * 0.62
for i, (pn, pf, low, _, _) in enumerate(frames):
    cx = CW * i + CW * 0.45
    hip = (cx, ground - low)
    lean = PF["lean"] + PF["stoop"]
    sh = add(hip, vec(180 - lean, torso_h))          # 躯干按前倾角
    W = u * 0.62 * (0.85 + 0.15 * PF["girth"])
    def draw_leg(pct, c):
        kn, an, he, to = leg(hip, pct)
        cap(hip, kn, W, c); cap(kn, an, W * .85, c); cap(he, to, W * .55, c); cap(an, add(he, (0, 0)), W * .5, c)
    def draw_arm(pct_leg, c, w, near):
        mode = PF["arm_mode"]
        if mode == "behind_back":                     # 背着手：上臂后伸，前臂折到腰后
            shf, el_add = -30, 118
        elif mode == "bag_near" and near:             # 近侧手拎袋子：手臂几乎垂直、微摆
            shf, el_add = -0.15 * (joint(pct_leg)[0] - 10) + 3, 8
        elif mode == "pockets":
            shf, el_add = -8, 50
        else:
            shf = -0.6 * PF["arm_swing"] * (joint(pct_leg)[0] - 10) + 2
            el_add = PF["elbow"] + max(0, shf) * 0.6
        el = add(sh, vec(shf, uarm)); hd = add(el, vec(shf + el_add, farm))
        cap(sh, el, w, c); cap(el, hd, w * .9, c); d.ellipse([hd[0] - w * .6, hd[1] - w * .6, hd[0] + w * .6, hd[1] + w * .6], fill=c)
        if mode == "bag_near" and near:
            d.rectangle([hd[0] - 0.55 * u, hd[1] + 0.1 * u, hd[0] + 0.55 * u, hd[1] + 1.1 * u], fill=(120, 120, 120))
    draw_leg(pf, FAR); draw_arm(pf, FAR, W * .8, False)
    tw = u * 1.25 * PF["girth"]
    hip_l, hip_r = (hip[0] - tw / 2, hip[1] + .2 * u), (hip[0] + tw / 2, hip[1] + .2 * u)
    belly = 0.25 * u * max(0, PF["girth"] - 1) * 2
    d.polygon([hip_l, hip_r, (sh[0] + tw / 2 + belly, (sh[1] + hip[1]) / 2), (sh[0] + tw / 2, sh[1]), (sh[0] - tw / 2, sh[1])], fill=BODY)
    hc = add(sh, (u * (.1 + PF["head_fwd"]), -head_r * 1.25))
    d.ellipse([hc[0] - head_r, hc[1] - head_r, hc[0] + head_r, hc[1] + head_r], fill=BODY)
    d.polygon([(hc[0] + head_r * .85, hc[1] - head_r * .05), (hc[0] + head_r * 1.25, hc[1] + head_r * .2), (hc[0] + head_r * .8, hc[1] + head_r * .4)], fill=BODY)
    draw_leg(pn, NEAR); draw_arm(pn, NEAR, W * .8, True)
json.dump({"profile": PF, "fps": PF["fps"], "frames": N, "cell": [CW, CH], "figure_height_img_px": H, "ground_y": ground,
           "root_motion_img_px": rm, "cycle_img_px": round(sum(rm), 1),
           "source": "Perry/Winter normal gait sagittal joint angles; toe-off 62%",
           "note": "浅灰=近侧 深灰=远侧；朝右；近侧腿 0%=脚跟着地"}, open(a.meta, "w"), ensure_ascii=False, indent=1)
img.save(a.out); print("rm", rm, "cycle", round(sum(rm), 1))
