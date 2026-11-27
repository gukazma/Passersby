"""正面（走向镜头）/背面（走离镜头）步态模特：同一套步态常模（见 poseguide.py），按游戏俯视角投影。
地面俯视系数 0.4（人行道 3 m 深在画面上 ≈ 76 px），竖直方向系数 0.92。

    python poseguide_fb.py out.png out.json --view front|back [--profile p.json] [--cell 384x1024] [--height 700]
浅灰 = 角色自己的左侧肢体，深灰 = 右侧。根运动 = 支撑脚在画面上的纵向位移（正面向下为正）。
"""
import argparse, json, math
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("meta")
ap.add_argument("--view", choices=["front", "back"], required=True)
ap.add_argument("--profile"); ap.add_argument("--cell", default="384x1024"); ap.add_argument("--height", type=float, default=700)
a = ap.parse_args()
PF = {"stride": 1.0, "knee_load": 1.0, "knee_swing": 1.0, "ankle": 1.0, "lean": 2.0, "head_fwd": 0.0, "stoop": 0.0,
      "arm_swing": 1.0, "elbow": 12.0, "arm_mode": "swing", "girth": 1.0, "leg_len": 1.0, "head": 1.0, "torso": 1.0, "fps": 12, "height_m": 1.7}
if a.profile:
    PF.update(json.load(open(a.profile, encoding="utf-8")))
CW, CH = map(int, a.cell.split("x")); N = 8; H = a.height * PF["height_m"] / 1.7
SIN, COS = 0.4, 0.92
HIP = [(0, 30), (10, 28), (30, 8), (50, -10), (56, -9), (62, -2), (75, 20), (87, 32), (100, 30)]
KNEE = [(0, 5), (15, 18), (30, 7), (40, 4), (50, 9), (62, 38), (72, 60), (80, 52), (90, 20), (97, 5), (100, 5)]
ANK = [(0, 0), (7, -6), (30, 5), (45, 10), (52, 6), (62, -16), (70, -10), (80, 0), (90, 2), (100, 0)]
def curve(kp, p):
    p %= 100; xs = [k[0] for k in kp]; ys = [k[1] for k in kp]
    for i in range(len(kp) - 1):
        if xs[i] <= p <= xs[i + 1]: break
    n = len(kp) - 1
    p0 = ys[i - 1] if i > 0 else ys[n - 1]; p3 = ys[i + 2] if i + 2 <= n else ys[1]
    t = (p - xs[i]) / (xs[i + 1] - xs[i]); p1, p2 = ys[i], ys[i + 1]
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
def joint(pct):
    h = 10 + (curve(HIP, pct) - 10) * PF["stride"]; k = curve(KNEE, pct)
    k *= PF["knee_swing"] if 55 <= pct % 100 <= 95 else PF["knee_load"]
    return h, k, curve(ANK, pct) * PF["ankle"]
u = H / 7.0; L = PF["leg_len"]
thigh, shin, foot_l = 1.6 * u * L, 1.55 * u * L, 0.8 * u
def V(ang, l): return (l * math.sin(math.radians(ang)), l * math.cos(math.radians(ang)))   # (前, 下)
def sag(pct):
    """矢状面：相对髋的 (前, 下)：膝、踝、脚跟、脚尖。"""
    h, k, an = joint(pct); kn = V(h, thigh); s = h - k
    ak = (kn[0] + V(s, shin)[0], kn[1] + V(s, shin)[1]); f = s + 90 + an
    fv = V(f, foot_l); dn = V(s, 0.16 * u)
    he = (ak[0] - 0.22 * fv[0] + dn[0], ak[1] - 0.22 * fv[1] + dn[1]); to = (ak[0] + 0.78 * fv[0] + dn[0], ak[1] + 0.78 * fv[1] + dn[1])
    return kn, ak, he, to
sgn = 1 if a.view == "front" else -1          # 正面：向前 = 画面向下
def proj(base, lat, p):  # base = 髋在画面上的点；p = (前, 下)
    return (base[0] + lat, base[1] + p[1] * COS + sgn * p[0] * SIN)
img = Image.new("RGB", (CW * N, CH), (255, 0, 255)); d = ImageDraw.Draw(img)
LEFT, RIGHT, BODY = (215, 215, 215), (90, 90, 90), (165, 165, 165)
def cap(p, q, w, c):
    d.line([p, q], fill=c, width=int(w)); r = w / 2
    for z in (p, q): d.ellipse([z[0] - r, z[1] - r, z[0] + r, z[1] + r], fill=c)
ground = CH - 90; W = u * 0.62 * (0.85 + 0.15 * PF["girth"]); hw = u * 0.32 * PF["girth"]
STANCE_END = 62
info = []
for i in range(N):
    pl = 100.0 * i / N; pr = pl + 50        # 左腿 0% 脚跟着地
    Ls, Rs = sag(pl), sag(pr)
    st = Ls if (pl % 100) < STANCE_END else Rs
    hip_h = max(st[2][1], st[3][1])          # 支撑脚最低点离髋的竖直距离
    st_fwd = (st[2][0] + st[3][0]) / 2       # 支撑脚在髋前方多少
    cx = CW * i + CW / 2
    # 髋的画面位置：支撑脚站在 ground 线上（纵向位置随支撑脚前后平移被吸收进根运动）
    base = (cx, ground - hip_h * COS)   # 身体原地（只有上下起伏），脚相对身体前后移动
    info.append((pl, base, Ls, Rs))
    legs = [(-hw, Ls, LEFT, pl), (hw, Rs, RIGHT, pr)]   # 画面左 = 角色右（正面），背面相反
    if a.view == "front":
        legs = [(hw, Ls, LEFT, pl), (-hw, Rs, RIGHT, pr)]
    # 离镜头近的腿后画：正面 = 更靠前的那条；背面 = 更靠后的那条
    legs.sort(key=lambda t: sgn * t[1][1][0])
    sh_y = base[1] - 2.0 * u * PF["torso"] * COS
    tw = u * 1.25 * PF["girth"]
    def draw_leg(lat, S, c):
        hp = (base[0] + lat, base[1]); kn = proj(base, lat, S[0]); ak = proj(base, lat, S[1])
        he = proj(base, lat, S[2]); to = proj(base, lat, S[3])
        cap(hp, kn, W, c); cap(kn, ak, W * .85, c)
        # 正背面的脚：一个横向的鞋块，脚尖朝镜头时向下伸
        fy = max(he[1], to[1]); d.rounded_rectangle([ak[0] - W * .55, min(he[1], to[1]) - W * .3, ak[0] + W * .55, fy + W * .3], radius=W * .3, fill=c)
    def draw_arm(lat, pct_leg, c):
        mode = PF["arm_mode"]
        if mode == "swing" or (mode == "bag_near" and lat < 0):
            sw = -0.6 * PF["arm_swing"] * (joint(pct_leg)[0] - 10)
        else:
            sw = 0
        shp = (base[0] + lat * 1.9, sh_y + u * .1)
        if mode == "behind_back":
            hand = (base[0] + lat * 0.6, base[1] - u * .3); el = (base[0] + lat * 2.0, base[1] - u * .9)
        elif mode == "pockets":
            hand = (base[0] + lat * 1.5, base[1] + u * .1); el = (base[0] + lat * 2.3, base[1] - u * .7)
        else:
            el = (shp[0] + lat * .15, shp[1] + 1.0 * u * COS + sgn * V(sw, 1.0 * u)[0] * SIN)
            hand = (el[0], el[1] + 0.95 * u * COS + sgn * V(sw + PF["elbow"], 0.95 * u)[0] * SIN)
        cap(shp, el, W * .8, c); cap(el, hand, W * .72, c)
        d.ellipse([hand[0] - W * .48, hand[1] - W * .48, hand[0] + W * .48, hand[1] + W * .48], fill=c)
        if mode == "bag_near" and lat < 0:
            d.rectangle([hand[0] - .5 * u, hand[1], hand[0] + .5 * u, hand[1] + u], fill=(120, 120, 120))
    behind_arms = a.view == "back" and PF["arm_mode"] == "behind_back"
    for lat, S, c, p in legs:
        draw_leg(lat, S, c)
    d.rectangle([base[0] - tw / 2, sh_y, base[0] + tw / 2, base[1] + .25 * u], fill=BODY)
    hr = 0.95 * u * PF["head"]; hc = (base[0], sh_y - hr * 1.15 + PF["head_fwd"] * u * SIN * sgn + PF["stoop"] * 0.6)
    d.ellipse([hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr], fill=BODY)
    if a.view == "front":
        d.ellipse([hc[0] - hr * .35, hc[1] + hr * .05, hc[0] - hr * .2, hc[1] + hr * .25], fill=(60, 60, 60))   # 眼睛：标明朝向
        d.ellipse([hc[0] + hr * .2, hc[1] + hr * .05, hc[0] + hr * .35, hc[1] + hr * .25], fill=(60, 60, 60))
    for lat, S, c, p in sorted(legs, key=lambda t: t[0]):
        draw_arm(lat, p, c)
# 根运动：两帧都处于支撑相的腿，其脚相对髋后移多少，身体就前进多少；画面纵向 = 前进 × SIN
rm = []
for i in range(N):
    pl, pl2 = 100.0 * i / N, 100.0 * (i + 1) / N
    off = 0 if (pl < STANCE_END and pl2 <= STANCE_END + 1e-6) else 50
    f0 = sag(pl + off)[1][0]; f1 = sag(pl2 + off)[1][0]
    rm.append(round((f0 - f1) * SIN, 2))
json.dump({"view": a.view, "profile": PF, "fps": PF["fps"], "frames": N, "cell": [CW, CH], "ground_y": ground,
           "root_motion_img_px": rm, "axis": "y", "sign": "front=向下(+y) back=向上(-y)",
           "note": "浅灰=角色左侧 深灰=右侧；投影 SIN=0.4 COS=0.92"}, open(a.meta, "w"), ensure_ascii=False, indent=1)
img.save(a.out); print(a.view, "rm", rm, "cycle", round(sum(rm), 1))
