"""四足动物侧面行走/快步姿势模特（朝右，8 帧，2 行 × 4 列），按真实步态数据画，给 AI 照着画。
11-27 用户：「狗和猫猫的步态都有问题，你这个得好好研究一下」。旧 dogguide 的三个错（见 references/animals_notes.md）：
  1 支撑期爪子相对躯干后移 S，但身体每周期前进也写成 S —— 支撑只占 62% 周期，爪子必然往后滑；
     正确：步长 L（身体每周期前进），支撑期爪子后移 = L × duty，根运动每帧 = L / 8。
  2 腿只有两节：前腿没有向后的肘、后腿没有向前的膝 + 向后的跗关节；
  3 步长只有 0.62 倍肩高（实测猫走 ≈1.8–2.0、狗走 ≈1.6–1.8），猫还用的是狗的模特。
腿三节：前腿 肩关节→肘（向后凸）→腕→爪；后腿 髋→膝（向前凸）→跗（向后凸）→爪（趾行）。
步序：走 = 侧序四拍 LH→LF→RH→RF；快步 = 对角两拍 LH+RF / RH+LF。浅灰 = 近侧（左）腿，深灰 = 远侧（右）腿。

    python quadguide.py out.png out.json --species dog|cat|puppy --gait walk|trot [--hs 230]
"""
import argparse, json, math
from PIL import Image, ImageDraw

SPECIES = {
    # 比例都以肩高 Hs 为单位：J* = 肩/髋关节离地，body = 肩点到坐骨的长度，seg = 各节长度
    "dog":   dict(Jf=0.60, Jh=0.58, body=1.10, chest=0.45, back=1.0, rump=0.97,
                  fore=(0.25, 0.28, 0.10), hind=(0.25, 0.27, 0.16), head=0.30, neck=0.18, ears="prick", tail="curl",
                  walk=dict(L=1.70, duty=0.62, lag=0.25, lift_f=0.20, lift_h=0.15, fps=10),
                  trot=dict(L=2.10, duty=0.45, lag=0.50, lift_f=0.26, lift_h=0.20, fps=16)),
    "puppy": dict(Jf=0.48, Jh=0.47, body=1.15, chest=0.40, back=1.0, rump=0.98,
                  fore=(0.20, 0.22, 0.09), hind=(0.20, 0.21, 0.13), head=0.34, neck=0.22, ears="drop", tail="up",
                  walk=dict(L=1.45, duty=0.62, lag=0.25, lift_f=0.18, lift_h=0.14, fps=11),
                  trot=dict(L=1.80, duty=0.45, lag=0.50, lift_f=0.24, lift_h=0.18, fps=17)),
    # 猫：躯干长、肚子收、后腿长（臀比肩略高）、头低平、尾巴竖起末端弯；走路近似侧序，偏“溜步”（同侧前后腿接近），直接踩点
    # 11-27 第一版猫模特按“真猫”画得太瘦长（躯干 1.45、腿长），AI 照着画成了细长猫，和游戏里圆滚滚的设定对不上 → 按设定稿比例
    "cat":   dict(Jf=0.50, Jh=0.53, body=1.22, chest=0.36, back=1.0, rump=1.03,
                  fore=(0.20, 0.23, 0.09), hind=(0.22, 0.25, 0.15), head=0.36, neck=0.15, ears="cat", tail="cat",
                  walk=dict(L=1.80, duty=0.60, lag=0.20, lift_f=0.18, lift_h=0.14, fps=10),
                  trot=dict(L=2.20, duty=0.45, lag=0.50, lift_f=0.22, lift_h=0.18, fps=15)),
}

ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("meta")
ap.add_argument("--species", default="dog", choices=list(SPECIES)); ap.add_argument("--gait", default="walk", choices=["walk", "trot"])
ap.add_argument("--hs", type=float, default=230, help="肩高（图像像素）"); ap.add_argument("--grid", default="4x2")
a = ap.parse_args()
sp = SPECIES[a.species]; gt = sp[a.gait]; Hs = a.hs
COLS, ROWS = map(int, a.grid.split("x")); N = COLS * ROWS
CW, CH = 768, 768
L = gt["L"] * Hs; DUTY = gt["duty"]; SW = L * DUTY          # 支撑期爪子相对关节的后移量
if a.gait == "walk":
    PH = {"LH": 0.0, "LF": gt["lag"], "RH": 0.5, "RF": 0.5 + gt["lag"]}
else:
    PH = {"LH": 0.0, "RF": 0.0, "RH": 0.5, "LF": 0.5}


def lerp_keys(keys, t):
    for i in range(len(keys) - 1):
        if keys[i][0] <= t <= keys[i + 1][0]:
            u = (t - keys[i][0]) / (keys[i + 1][0] - keys[i][0] + 1e-9)
            u = u * u * (3 - 2 * u)
            return keys[i][1] + (keys[i + 1][1] - keys[i][1]) * u
    return keys[-1][1]


def paw_and_meta(ph, front):
    """ph = 0 着地。返回 爪相对关节的 (dx, 离地高度) 和 掌骨/跖骨与竖直的夹角（正 = 爪在腕/跗后面）。"""
    ph %= 1.0
    off = 0.06 * Hs if front else -0.04 * Hs
    lift = (gt["lift_f"] if front else gt["lift_h"]) * Hs
    if ph < DUTY:
        t = ph / DUTY
        dx = off + SW / 2 - SW * t; h = 0.0
        ang = lerp_keys([(0, -8), (0.5, 4), (1.0, 32 if front else 38)], t)
    else:
        t = (ph - DUTY) / (1 - DUTY)
        s = t * t * (3 - 2 * t)
        dx = off - SW / 2 + SW * s
        h = lift * math.sin(math.pi * min(1.0, t * 1.08)) ** 1.2
        if front:   # 前腿抬起时腕关节折叠，爪子翻向后上方；落地前伸直前探
            ang = lerp_keys([(0, 32), (0.3, 95), (0.65, 40), (1.0, -8)], t)
        else:
            ang = lerp_keys([(0, 38), (0.35, 70), (0.7, 20), (1.0, -8)], t)
    return dx, h, ang


def ik(p, q, l1, l2, bend):
    dx, dy = q[0] - p[0], q[1] - p[1]; dist = min(math.hypot(dx, dy), l1 + l2 - 1e-3)
    a0 = math.atan2(dy, dx); c = (l1 ** 2 + dist ** 2 - l2 ** 2) / (2 * l1 * dist); c = max(-1.0, min(1.0, c))
    ang = a0 + bend * math.acos(c)        # 画面 y 向下：bend=+1 关节在连线的左侧（后方），-1 右侧（前方）
    return (p[0] + l1 * math.cos(ang), p[1] + l1 * math.sin(ang))


img = Image.new("RGB", (CW * COLS, CH * ROWS), (255, 0, 255)); d = ImageDraw.Draw(img)
NEAR, FAR, BODY = (218, 218, 218), (88, 88, 88), (160, 160, 160)


def cap(p, q, w, c):
    d.line([p, q], fill=c, width=max(1, int(w))); r = w / 2
    for z in (p, q): d.ellipse([z[0] - r, z[1] - r, z[0] + r, z[1] + r], fill=c)


Wl = Hs * 0.10
rows_px = []
for i in range(N):
    ph = i / N
    col, row = i % COLS, i // COLS
    ox, ground = CW * col, CH * row + CH - 150
    cx = ox + CW * 0.47
    bob = -0.018 * Hs * math.cos(4 * math.pi * ph) if a.gait == "walk" else -0.035 * Hs * math.cos(4 * math.pi * ph)
    sh = (cx + sp["body"] * Hs / 2 - 0.12 * Hs, ground - sp["Jf"] * Hs + bob)
    hp = (cx - sp["body"] * Hs / 2 + 0.12 * Hs, ground - sp["Jh"] * Hs + bob)
    legs = {}
    for k, o in PH.items():
        front = k.endswith("F")
        dx, h, ang = paw_and_meta(ph - o, front)
        # 肩胛绕肩胛顶转动：肩关节跟着腿前后移（前腿 30%），髋关节随骨盆小幅移动（10%）——有效支点更高，腿摆角不会过大
        base = ((sh[0] + 0.30 * dx, sh[1]) if front else (hp[0] + 0.10 * dx, hp[1]))
        paw = (base[0] + dx, ground - h - Wl * 0.5)
        s1, s2, s3 = sp["fore"] if front else sp["hind"]
        s1, s2, s3 = s1 * Hs, s2 * Hs, s3 * Hs
        r = math.radians(ang)
        dist = (paw[0] + s3 * math.sin(r), paw[1] - s3 * math.cos(r))      # 腕/跗关节
        mid = ik(base, dist, s1, s2, +1 if front else -1)                 # 前腿肘向后，后腿膝向前
        legs[k] = (base, mid, dist, paw, ang)
    # 肩胛随着同侧前腿支撑起伏（猫的肩胛滚动最明显）
    roll = 0.0
    if a.species == "cat":
        _, _, _, pL, _ = legs["LF"]; roll = 0.04 * Hs * (1 if (ph - PH["LF"]) % 1 < DUTY else -0.5)

    def leg(k, col_):
        base, mid, dist, paw, ang = legs[k]; front = k.endswith("F")
        cap(base, mid, Wl * 1.45, col_); cap(mid, dist, Wl * 1.05, col_); cap(dist, paw, Wl * 0.9, col_)
        r = math.radians(ang)
        toe = (paw[0] + Wl * 1.1 * math.cos(r), paw[1] + Wl * 1.1 * math.sin(r))   # 爪垫：着地时平贴地面朝前
        cap(paw, toe, Wl * 0.95, col_)

    for k in ("RH", "RF"):
        leg(k, FAR)
    # 躯干
    top_f = ground - sp["back"] * Hs + bob - roll; top_h = ground - sp["rump"] * Hs + bob
    bot = ground - sp["chest"] * Hs + bob
    xf, xh = sh[0] + 0.16 * Hs, hp[0] - 0.16 * Hs
    body = [(xh, top_h + 0.08 * Hs), (xh + 0.10 * Hs, top_h), (sh[0] - 0.05 * Hs, top_f), (xf, top_f + 0.16 * Hs),
            (xf + 0.02 * Hs, bot - 0.08 * Hs), (sh[0] - 0.05 * Hs, bot), (hp[0] + 0.25 * Hs, bot - (0.06 if a.species == "cat" else 0.02) * Hs),
            (xh + 0.04 * Hs, top_h + 0.38 * Hs), (xh - 0.03 * Hs, top_h + 0.22 * Hs)]
    d.polygon(body, fill=BODY)
    cap(hp, (hp[0] - 0.04 * Hs, hp[1] - 0.12 * Hs), Hs * 0.34, BODY)     # 大腿根肌肉
    cap(sh, (sh[0] + 0.02 * Hs, sh[1] - 0.12 * Hs), Hs * 0.30, BODY)     # 肩
    # 脖子和头（狗头随前腿着地轻点头；猫头低、平稳）
    nod = 0.025 * Hs * math.cos(4 * math.pi * (ph - PH["LF"])) if a.species != "cat" else 0.006 * Hs * math.cos(4 * math.pi * ph)
    hr = sp["head"] * Hs
    if a.species == "cat":
        hc = (xf + 0.14 * Hs, top_f - 0.08 * Hs + nod)
    else:
        hc = (xf + 0.14 * Hs, top_f - sp["neck"] * Hs + nod)
    cap((sh[0], top_f + 0.15 * Hs), (hc[0] - 0.05 * Hs, hc[1] + 0.05 * Hs), Hs * 0.26, BODY)
    d.ellipse([hc[0] - hr * 0.55, hc[1] - hr * 0.5, hc[0] + hr * 0.55, hc[1] + hr * 0.5], fill=BODY)
    mz = (hc[0] + hr * 0.75, hc[1] + hr * 0.15)
    cap((hc[0] + hr * 0.2, hc[1] + hr * 0.1), mz, hr * (0.42 if a.species == "puppy" else 0.34 if a.species == "dog" else 0.30), BODY)
    if sp["ears"] in ("prick", "cat"):
        for ex in (-0.25, 0.08):
            e0 = (hc[0] + hr * ex, hc[1] - hr * 0.35)
            d.polygon([(e0[0] - hr * 0.18, e0[1]), (e0[0] + hr * 0.05, e0[1] - hr * (0.55 if sp["ears"] == "prick" else 0.45)), (e0[0] + hr * 0.22, e0[1])], fill=BODY)
    else:
        cap((hc[0] - hr * 0.2, hc[1] - hr * 0.3), (hc[0] - hr * 0.45, hc[1] + hr * 0.25), hr * 0.3, (140, 140, 140))
    # 尾巴
    tb = (xh + 0.02 * Hs, top_h + 0.06 * Hs); sway = math.sin(2 * math.pi * ph)
    if sp["tail"] == "curl":
        pts = [tb, (tb[0] - 0.12 * Hs, tb[1] - 0.22 * Hs), (tb[0] + 0.02 * Hs + 0.02 * Hs * sway, tb[1] - 0.36 * Hs), (tb[0] + 0.12 * Hs, tb[1] - 0.22 * Hs)]
        d.line(pts, fill=BODY, width=int(Hs * 0.10), joint="curve")
    elif sp["tail"] == "up":
        pts = [tb, (tb[0] - 0.10 * Hs, tb[1] - 0.22 * Hs), (tb[0] - 0.02 * Hs + 0.03 * Hs * sway, tb[1] - 0.34 * Hs)]
        d.line(pts, fill=BODY, width=int(Hs * 0.09), joint="curve")
    else:   # 猫：竖尾，末端问号弯，随步子轻摆
        pts = [tb, (tb[0] - 0.12 * Hs, tb[1] - 0.22 * Hs), (tb[0] - 0.13 * Hs + 0.03 * Hs * sway, tb[1] - 0.46 * Hs),
               (tb[0] - 0.05 * Hs + 0.04 * Hs * sway, tb[1] - 0.60 * Hs), (tb[0] + 0.03 * Hs + 0.04 * Hs * sway, tb[1] - 0.56 * Hs)]
        d.line(pts, fill=BODY, width=int(Hs * 0.10), joint="curve")
    for k in ("LH", "LF"):
        leg(k, NEAR)
rm = [round(L / N, 2)] * N
json.dump({"species": a.species, "gait": a.gait, "frames": N, "fps": gt["fps"], "grid": [COLS, ROWS], "cell": [CW, CH],
           "duty": DUTY, "stride_img_px": round(L, 1), "stance_sweep_img_px": round(SW, 1), "phase": PH,
           "root_motion_img_px": rm, "axis": "x", "shoulder_img_px": Hs, "mode": a.gait,
           "note": "侧序四拍（walk）/ 对角两拍（trot），浅灰近侧；根运动 = 步长/帧数（支撑爪相对地面不动）"},
          open(a.meta, "w"), ensure_ascii=False, indent=1)
img.save(a.out); print("stride", round(L, 1), "rm", rm[0], "fps", gt["fps"])
