"""任意朝向的步态模特（8 帧）：yaw=0 朝右侧面，90 走向镜头（正面），-90 走离镜头（背面），
45 = 右前斜（向右下走，3/4 正面），-45 = 右后斜（向右上走，3/4 背面）。朝左用镜像。
同一套步态常模（Perry/Winter）+ 游戏俯视投影：地面 SIN=0.4，竖直 COS=0.92。

    python poseguide_yaw.py out.png out.json --yaw 45 [--profile p.json] [--cell 384x1024] [--height 700]
浅灰 = 角色左侧肢体，深灰 = 右侧。json 里 root_motion_img_px = 沿行走方向的地面前进量（未投影），
dir_screen = [cos yaw, sin yaw * SIN]：游戏里每帧位移 = rm * dir_screen（x 乘朝向）。
"""
import argparse, json, math
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("meta")
ap.add_argument("--yaw", type=float, required=True)
ap.add_argument("--profile"); ap.add_argument("--cell", default="384x1024"); ap.add_argument("--height", type=float, default=700)
a = ap.parse_args()
PF = {"stride": 1.0, "knee_load": 1.0, "knee_swing": 1.0, "ankle": 1.0, "lean": 2.0, "head_fwd": 0.0, "stoop": 0.0,
      "arm_swing": 1.0, "elbow": 12.0, "arm_mode": "swing", "girth": 1.0, "leg_len": 1.0, "head": 1.0, "torso": 1.0, "fps": 12, "height_m": 1.7}
if a.profile:
    PF.update(json.load(open(a.profile, encoding="utf-8")))
CW, CH = map(int, a.cell.split("x")); N = 8; H = a.height * PF["height_m"] / 1.7
SIN, COS = 0.4, 0.92
yaw = math.radians(a.yaw)
FX, FZ = math.cos(yaw), math.sin(yaw)          # 前进方向（地面：x 向右，z 向镜头）
LX, LZ = -math.sin(yaw), math.cos(yaw)         # 角色左侧方向（朝右时左侧 = 朝镜头… 取 z 向镜头为左手侧）
# 朝右走时，角色左侧朝向镜头（近侧）——与侧面模特"浅灰=近侧"一致
HIP = [(0, 30), (10, 28), (30, 8), (50, -10), (56, -9), (62, -2), (75, 20), (87, 32), (100, 30)]
KNEE = [(0, 5), (15, 18), (30, 7), (40, 4), (50, 9), (62, 38), (72, 60), (80, 52), (90, 20), (97, 5), (100, 5)]
ANK = [(0, 0), (7, -6), (30, 5), (45, 10), (52, 6), (62, -16), (70, -10), (80, 0), (90, 2), (100, 0)]
STANCE_END = 62
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
    h, k, an = joint(pct); kn = V(h, thigh); s = h - k
    ak = (kn[0] + V(s, shin)[0], kn[1] + V(s, shin)[1]); f = s + 90 + an
    fv = V(f, foot_l); dn = V(s, 0.16 * u)
    he = (ak[0] - 0.22 * fv[0] + dn[0], ak[1] - 0.22 * fv[1] + dn[1]); to = (ak[0] + 0.78 * fv[0] + dn[0], ak[1] + 0.78 * fv[1] + dn[1])
    return kn, ak, he, to
def P3(base, fwd, lat, down):
    """三维点（相对髋：前、左、下）→ 画面坐标，并返回深度（越大越靠近镜头）。"""
    gx = fwd * FX + lat * LX; gz = fwd * FZ + lat * LZ
    return (base[0] + gx, base[1] + down * COS + gz * SIN), gz
img = Image.new("RGB", (CW * N, CH), (255, 0, 255)); d = ImageDraw.Draw(img)
LEFT, RIGHT, BODY = (215, 215, 215), (90, 90, 90), (165, 165, 165)
def cap(p, q, w, c):
    d.line([p, q], fill=c, width=int(max(1, w))); r = w / 2
    for z in (p, q): d.ellipse([z[0] - r, z[1] - r, z[0] + r, z[1] + r], fill=c)
ground = CH - 90; W = u * 0.62 * (0.85 + 0.15 * PF["girth"]); hw = u * 0.32 * PF["girth"]
lean = PF["lean"] + PF["stoop"]
for i in range(N):
    pl = 100.0 * i / N; pr = pl + 50
    Ls, Rs = sag(pl), sag(pr)
    st = Ls if (pl % 100) < STANCE_END else Rs
    hip_h = max(st[2][1], st[3][1])
    base = (CW * i + CW / 2, ground - hip_h * COS)
    items = []    # (depth, drawfn)
    for side, S, c, pct in ((+1, Ls, LEFT, pl), (-1, Rs, RIGHT, pr)):
        lat = side * hw
        hp, zh = P3(base, 0, lat, 0); kn, zk = P3(base, S[0][0], lat, S[0][1]); ak, za = P3(base, S[1][0], lat, S[1][1])
        he, _ = P3(base, S[2][0], lat, S[2][1]); to, zt = P3(base, S[3][0], lat, S[3][1])
        items.append(((zh + za) / 2, lambda hp=hp, kn=kn, ak=ak, he=he, to=to, c=c: (cap(hp, kn, W, c), cap(kn, ak, W * .85, c), cap(he, to, W * .55, c), cap(ak, he, W * .5, c))))
        # 手臂：肩在髋上方 torso；摆角与同侧腿反向
        mode = PF["arm_mode"]
        sw = -0.6 * PF["arm_swing"] * (joint(pct)[0] - 10) + lean
        sh_down = -2.0 * u * PF["torso"]
        shp, zs = P3(base, math.sin(math.radians(lean)) * 2.0 * u, side * hw * 1.9, sh_down)
        if mode == "behind_back":
            elf, eld, hdf, hdd = -0.45 * u, sh_down + 0.9 * u, -0.35 * u, sh_down + 1.5 * u
            lat2 = side * hw * 0.6
        elif mode == "pockets":
            elf, eld, hdf, hdd = -0.15 * u, sh_down + 0.95 * u, 0.15 * u, sh_down + 1.8 * u
            lat2 = side * hw * 1.5
        else:
            if mode == "bag_near" and side > 0:
                sw = -0.15 * (joint(pct)[0] - 10)
            e = V(sw, 1.05 * u); hnd = V(sw + PF["elbow"] + max(0, sw) * 0.6, 0.95 * u)
            elf, eld = e[0], sh_down + e[1]; hdf, hdd = e[0] + hnd[0], sh_down + e[1] + hnd[1]
            lat2 = side * hw * 1.9
        el, ze = P3(base, elf, lat2, eld); hd, zd = P3(base, hdf, lat2, hdd)
        items.append(((zs + zd) / 2 + 0.01, lambda shp=shp, el=el, hd=hd, c=c: (cap(shp, el, W * .8, c), cap(el, hd, W * .72, c),
                      d.ellipse([hd[0] - W * .48, hd[1] - W * .48, hd[0] + W * .48, hd[1] + W * .48], fill=c))))
    # 躯干：四边形（髋左右、肩左右），深度 0
    def torso():
        tw = hw * 1.9 * PF["girth"]
        pts = [P3(base, 0, tw, 0.2 * u)[0], P3(base, 0, -tw, 0.2 * u)[0],
               P3(base, math.sin(math.radians(lean)) * 2.0 * u, -tw, -2.0 * u * PF["torso"])[0],
               P3(base, math.sin(math.radians(lean)) * 2.0 * u, tw, -2.0 * u * PF["torso"])[0]]
        # 侧面朝向时躯干在画面上很窄：至少保持一定宽度
        xs = [p[0] for p in pts]; cx = sum(xs) / 4; minw = u * 1.0
        if max(xs) - min(xs) < minw:
            pts = [((p[0] - cx) * minw / max(1e-3, max(xs) - min(xs)) + cx, p[1]) if max(xs) - min(xs) > 1e-3 else (cx + (minw / 2 if k in (0, 3) else -minw / 2), p[1]) for k, p in enumerate(pts)]
        d.polygon(pts, fill=BODY)
        hc, _ = P3(base, math.sin(math.radians(lean)) * 2.0 * u + PF["head_fwd"] * u, 0, -2.0 * u * PF["torso"] - 1.2 * 0.95 * u * PF["head"])
        hr = 0.95 * u * PF["head"]
        d.ellipse([hc[0] - hr, hc[1] - hr, hc[0] + hr, hc[1] + hr], fill=BODY)
        # 鼻子/眼睛标朝向：鼻尖沿前进方向
        nose = (hc[0] + FX * hr * 1.15, hc[1] + FZ * SIN * hr * 1.15 + hr * 0.15)
        d.polygon([(hc[0] + FX * hr * 0.8, hc[1] - hr * 0.05), nose, (hc[0] + FX * hr * 0.75, hc[1] + hr * 0.35)], fill=BODY)
        if FZ > 0.3:   # 看得到脸：画两只眼
            for s in (-1, 1):
                ex = hc[0] + FX * hr * 0.45 + s * LX * hr * 0.35; ey = hc[1] + hr * 0.12
                d.ellipse([ex - hr * .08, ey - hr * .1, ex + hr * .08, ey + hr * .1], fill=(60, 60, 60))
    items.append((0.0, torso))
    for _, fn in sorted(items, key=lambda t: t[0]):
        fn()
rm = []
for i in range(N):
    pl, pl2 = 100.0 * i / N, 100.0 * (i + 1) / N
    off = 0 if (pl < STANCE_END and pl2 <= STANCE_END + 1e-6) else 50
    rm.append(round(sag(pl + off)[1][0] - sag(pl2 + off)[1][0], 2))
json.dump({"yaw": a.yaw, "profile": PF, "fps": PF["fps"], "frames": N, "cell": [CW, CH], "ground_y": ground,
           "root_motion_img_px": rm, "axis": "dir", "dir_screen": [round(FX, 4), round(FZ * SIN, 4)],
           "note": "浅灰=角色左侧 深灰=右侧；rm 为沿行走方向的地面前进量，屏幕位移 = rm × dir_screen"}, open(a.meta, "w"), ensure_ascii=False, indent=1)
img.save(a.out); print("yaw", a.yaw, "rm", rm, "dir", [round(FX, 3), round(FZ * SIN, 3)])
