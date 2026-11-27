"""像素城市 v4：AI 整块街区拼城市（3 列 × 3 行街区 + 林荫大道 + 两条横路 + 两条纵路 + 滨河步道）。

街区图：godot/assets/blocks/<名>.png/.json（process_blocks.py 产出：w,h,base,alley）。
程序只画：道路、人行道、斑马线、街区之间的铺装、河；放行道树/路灯/红绿灯/设施；算碰撞、遮挡分层、车道、NPC、主角路线。
"""
import json
import math
import pathlib

import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from occ import south_top, runs      # noqa: E402  后巷南侧楼顶凸起的逐列遮挡/碰撞

A = pathlib.Path("godot/assets")
SZ = json.load(open(A / "sizes.json"))
rng = np.random.default_rng(5)
Rn = lambda a, b: float(rng.uniform(a, b))

LAYOUT = [["cbd_a", "cbd_b", "cbd_c"], ["shop_a", "plaza", "food"], ["apt_a", "shop_b", "apt_b"]]
B = {n: json.load(open(A / f"blocks/{n}.json")) for row in LAYOUT for n in row}
MARGIN, VW, SWV = 40, 20, 22            # 地图边人行道、纵路半宽、纵路人行道宽（A1.1 加宽：行道树种在人行道上，不压马路）
COLW = [max(B[LAYOUT[r][c]]["w"] for r in range(3)) for c in range(3)]
colx = [MARGIN]
for c in range(1, 3):
    colx.append(colx[-1] + COLW[c - 1] + 2 * (VW + SWV))
W = colx[-1] + COLW[2] + MARGIN
VR = [colx[c] - VW - SWV for c in (1, 2)]   # 纵路中心
# 行：CBD 底对齐 ROW0_BOTTOM；大道；行 1；路 2；行 2；路 3；滨河；河
ROW0_BOTTOM = max(B[n]["h"] for n in LAYOUT[0]) + 20
AV_HW, AV_SW = 36, 16                    # 林荫大道半宽、人行道
HR_HW, HR_SW = 20, 14
av_c = ROW0_BOTTOM + AV_SW + AV_HW
row1_top = av_c + AV_HW + AV_SW
row1_h = max(B[n]["h"] for n in LAYOUT[1])
r2_c = row1_top + row1_h + HR_SW + HR_HW
row2_top = r2_c + HR_HW + HR_SW
row2_h = max(B[n]["h"] for n in LAYOUT[2])
r3_c = row2_top + row2_h + HR_SW + HR_HW
prom0 = r3_c + HR_HW + HR_SW
RIVER_Y = prom0 + 70
H = RIVER_Y + 80
HROADS = [(av_c, AV_HW, AV_SW, True), (r2_c, HR_HW, HR_SW, False), (r3_c, HR_HW, HR_SW, False)]
print("world", W, H, "VR", VR, "HR", [h[0] for h in HROADS])

PAL = {"asphalt": [(78, 80, 86), (72, 74, 80), (84, 86, 92)], "walk": (196, 190, 178), "walk_line": (170, 164, 152), "curb": (140, 136, 128),
       "plaza": (214, 204, 184), "plaza_line": (190, 178, 158), "lane": (232, 196, 80), "white": (236, 236, 230),
       "water": [(70, 130, 150), (62, 120, 140), (84, 146, 164)], "grass": [(112, 162, 80), (100, 150, 70), (124, 172, 88)]}
img = np.zeros((H, W, 3), np.uint8)


def clip(x0, y0, x1, y1):
    return max(0, int(x0)), max(0, int(y0)), min(W, int(x1)), min(H, int(y1))


def noise(x0, y0, x1, y1, cols, p=(0.08, 0.93)):
    x0, y0, x1, y1 = clip(x0, y0, x1, y1)
    if x1 <= x0 or y1 <= y0:
        return
    m = rng.random((y1 - y0, x1 - x0))
    blk = np.empty((y1 - y0, x1 - x0, 3), np.uint8)
    blk[:] = cols[0]
    blk[m < p[0]] = cols[1]
    blk[m > p[1]] = cols[2]
    img[y0:y1, x0:x1] = blk


def tiles(x0, y0, x1, y1, col, line, t=8):
    x0, y0, x1, y1 = clip(x0, y0, x1, y1)
    if x1 <= x0 or y1 <= y0:
        return
    img[y0:y1, x0:x1] = col
    for y in range(y0, y1):
        if y % t == 0:
            img[y, x0:x1] = line
        off = t // 2 if (y // t) % 2 else 0
        img[y, [x for x in range(x0 - x0 % t + off, x1, t) if x >= x0]] = line


# 底：整片人行道铺装（街区之间、街区旁的空地都是铺装）
tiles(0, 0, W, prom0, PAL["walk"], PAL["walk_line"])
# 横路
for y, hw, sw, med in HROADS:
    noise(0, y - hw, W, y + hw, PAL["asphalt"])
    img[y - hw - 1, :] = PAL["curb"]
    img[y + hw, :] = PAL["curb"]
    if med:
        noise(0, y - 5, W, y + 5, PAL["grass"])
        img[y - 6, :] = PAL["curb"]
        img[y + 5, :] = PAL["curb"]
# 纵路（全高，到滨河步道为止）
for x in VR:
    noise(x - VW, 0, x + VW, prom0 - HR_SW, PAL["asphalt"])
    img[:prom0 - HR_SW, x - VW - 1] = PAL["curb"]
    img[:prom0 - HR_SW, x + VW] = PAL["curb"]
INTERS = []
for x in VR:
    for y, hw, sw, med in HROADS:
        noise(x - VW, y - hw, x + VW, y + hw, PAL["asphalt"])
        INTERS.append([x - VW, y - hw, 2 * VW, 2 * hw])
inter = lambda x, y, pad=0: any(abs(x - vx) <= VW + SWV + pad for vx in VR) and any(abs(y - hy) <= hw + sw + pad for hy, hw, sw, _ in HROADS)
for y, hw, sw, med in HROADS:
    for yy in ([y] if not med else [y - 18, y + 18]):
        for x in range(0, W, 12):
            if not inter(x, y, 2):
                img[yy - 1:yy + 1, x:x + 6] = PAL["white"] if med else PAL["lane"]
for x in VR:
    for y in range(0, prom0 - HR_SW, 12):
        if not inter(x, y, 2):
            img[y:y + 6, x - 1:x + 1] = PAL["lane"]
    # 停止线
    for y, hw, sw, med in HROADS:
        img[y - hw - sw - 2:y - hw - sw, x - VW:x] = PAL["white"]
        img[y + hw + sw:y + hw + sw + 2, x:x + VW] = PAL["white"]
CROSS_H, CROSS_V = [], []                # 斑马线：横穿横路（x 位置）、横穿纵路（y 位置）
for x in VR:
    for y, hw, sw, med in HROADS:
        for xc in (x - VW - SWV - 14, x + VW + SWV + 14):
            for k in range(-10, 11, 5):
                img[y - hw:y + hw, xc + k:xc + k + 3] = PAL["white"]
            CROSS_H.append((xc, y, hw))
        for yc in (y - hw - sw - 14, y + hw + sw + 14):
            for k in range(-10, 11, 5):
                img[yc + k:yc + k + 3, x - VW:x + VW] = PAL["white"]
            CROSS_V.append((x, yc))
for _ in range(80):   # 井盖、补丁
    y, hw, sw, med = HROADS[int(rng.integers(3))]
    x, yy = int(Rn(10, W - 10)), int(y + Rn(-hw + 6, hw - 6))
    if inter(x, yy, 4) or (med and abs(yy - y) < 8):
        continue
    if rng.random() < 0.4:
        img[yy - 3:yy + 3, x - 3:x + 3] = (60, 62, 66)
        img[yy - 2:yy + 2, x - 2:x + 2] = (92, 94, 98)
    else:
        noise(x - Rn(6, 14), yy - Rn(3, 6), x + Rn(6, 14), yy + Rn(3, 6), [(66, 68, 74), (62, 64, 70), (70, 72, 78)])
# 滨河步道 + 河
tiles(0, prom0, W, RIVER_Y - 6, PAL["plaza"], PAL["plaza_line"], 10)
noise(0, RIVER_Y - 6, W, RIVER_Y, [(150, 140, 120), (140, 130, 112), (160, 150, 130)])
noise(0, RIVER_Y, W, H, PAL["water"])
for x in range(0, W, 2):
    img[RIVER_Y + 6 + int(3 * math.sin(x / 17)), x] = (110, 166, 180)

# ── 街区 ──
blocks, solids = [], []
rows_top = [None, row1_top, row2_top]
for r, row in enumerate(LAYOUT):
    for c, n in enumerate(row):
        b = B[n]
        bx = colx[c] + (COLW[c] - b["w"]) // 2
        by = (ROW0_BOTTOM - b["h"]) if r == 0 else rows_top[r]
        occ = None
        if b["alley"]:
            a0, a1 = b["alley"]
            parts = [[0, a0, a0], [a1, b["base"], b["base"]]]
            solids.append([bx, by, b["w"], a0 - 3])
            solids.append([bx, by + a1 + 2, b["w"], b["base"] - a1 - 2])
            # 南排楼顶伸进后巷带的东西：单独一层（跟南排楼一起排序，挡住后巷里的人）+ 碰撞跟着轮廓走
            bim = np.array(Image.open(A / f"blocks/{n}.png").convert("RGBA"))
            top = south_top(bim, a0, a1)
            if (top < a1).any():
                y0 = int(top.min())
                ov = bim[y0:a1].copy()
                rows = np.arange(y0, a1)[:, None]
                ov[..., 3] = np.where(rows >= top[None, :], ov[..., 3], 0)
                Image.fromarray(ov).save(A / f"blocks/{n}_occ.png")
                occ = [y0, a1, b["base"]]
                for x0, t, rw in runs(top, a1):
                    if rw >= 18:          # 窄的（地沟盖之类）只做遮挡不做碰撞，免得出现"空气墙"
                        solids.append([bx + x0, by + t + 3, rw, a1 + 2 - t - 3])
        else:
            parts = [[0, b["base"], b["base"]]]
            solids.append([bx, 0, b["w"], by + b["base"]])
        blocks.append({"img": n, "x": bx, "y": by, "w": b["w"], "h": b["h"], "base": b["base"], "alley": b["alley"], "parts": parts, "occ": occ})
Image.fromarray(img).save(A / "ground.png")

# ── 道具 ──
FOOT = {"street_tree": [8, 6], "lamp2": [4, 4], "bench2": [46, 8], "bus_stop2": [60, 10], "vending2": [30, 10], "kiosk": [30, 10],
        "bikes": [58, 8], "planter": [28, 10], "traffic_light": [4, 4]}
props, vendings = [], []


def prop(name, x, y, **kw):
    d = {"sprite": name, "x": round(x), "y": round(y), "foot": FOOT[name]}
    d.update(kw)
    props.append(d)


def blocked(x, y, r=10):
    for s in solids:
        if s[0] - r < x < s[0] + s[2] + r and s[1] - r < y < s[1] + s[3] + r:
            return True
    return any(abs(x - p["x"]) < 18 and abs(y - p["y"]) < 10 for p in props)


# 行道树（A1.1）：每条人行道一排、一棵一棵、等间距，不交错，树坑在人行道上，树冠不压马路。
# 横路：只种在北侧人行道（靠路缘，树冠往上盖人行道和楼脚）；南侧人行道放路灯（3/4 视角那边的树冠会盖住车道）。
TREE_DX = 120
for y, hw, sw, med in HROADS:
    for x in range(60, W, TREE_DX):
        if not inter(x, y, 30):
            prop("street_tree", x, y - hw - 1)
        if not inter(x + TREE_DX // 2, y, 30):
            prop("lamp2", x + TREE_DX // 2, y + hw + sw - 1)
# 纵路：两侧人行道各一排，树坑靠人行道外沿（离路缘 18 像素，树冠 36 宽正好不进车道），两侧对齐
for x in VR:
    for side in (-1, 1):
        xx = x + side * (VW + SWV - 4)
        for y in range(40, prom0 - HR_SW - 20, 120):
            if not inter(x, y, 34):
                prop("street_tree", xx, y)
for x in VR:   # 红绿灯（四角）：灯色由 main.gd 按相位控制
    for y, hw, sw, med in HROADS:
        prop("traffic_light", x - VW + 2, y - hw - 3, light=["ns", 6])
        prop("traffic_light", x + VW - 2, y + hw + 10, light=["ns", 6])
        prop("traffic_light", x - VW + 2, y + hw + 10, light=["ew", 6])
        prop("traffic_light", x + VW - 2, y - hw - 3, light=["ew", 6])
# 公交站、设施：放在街区旁的空地、广场边
prop("bus_stop2", colx[1] + 140, av_c - AV_HW - 2)
for c in range(3):
    for r in (1, 2):
        b = blocks[r * 3 + c]
        gap = (COLW[c] - b["w"]) // 2
        if gap >= 30:     # 街区两侧的空地：自行车架、售货机、报亭
            for gx, item in ((colx[c] + gap / 2, ["bikes", "vending2", "kiosk", "planter"][(r + c) % 4]),
                             (colx[c] + COLW[c] - gap / 2, ["kiosk", "planter", "vending2", "bikes"][(r + c) % 4])):
                gy = b["y"] + (b["alley"][0] - 10 if b["alley"] else b["base"])
                if item in ("bikes", "bench2") and gap < 62:
                    item = "planter"
                if not blocked(gx, gy, 4):
                    prop(item, gx, gy)
                    if item == "vending2":
                        vendings.append([round(gx), round(gy) + 8])
# 广场：长椅、售货机、花坛
pl = blocks[4]
pa0, pa1 = pl["alley"]
pcx, pcy = pl["x"] + pl["w"] / 2, pl["y"] + (pa0 + pa1) / 2
for dx in (-230, 230):
    prop("bench2", pcx + dx, pcy - 22)
prop("vending2", pl["x"] + 40, pl["y"] + pa0 + 34)
vendings.append([round(pl["x"] + 40), round(pl["y"] + pa0 + 42)])
prop("kiosk", pl["x"] + pl["w"] - 40, pl["y"] + pa0 + 34)
# 滨河：树、长椅、路灯
for x in range(50, W, 140):
    prop("street_tree", x, prom0 + 12)
for x in range(120, W, 280):
    prop("bench2", x, RIVER_Y - 10)
    prop("lamp2", x + 70, RIVER_Y - 8)
VX = VR[0] - VW - SWV - 14 - 130          # 河边售货机：在斑马线西边 130 像素，避开过马路的线
prop("vending2", VX, prom0 + 14)
vendings.append([VX, prom0 + 22])

# ── 行人护栏（路面，斑马线留口）──
barriers = []
for y, hw, sw, med in HROADS:
    opens = sorted(xc for xc, yy, _ in CROSS_H if yy == y)
    xs = [0] + [v for xc in opens for v in (xc - 13, xc + 13)] + [W]
    for a, b in zip(xs[0::2], xs[1::2]):
        if b > a:
            barriers.append([a, y - hw + 2, b - a, 2 * hw - 4])
for x in VR:
    opens = sorted(yc for xx, yc in CROSS_V if xx == x)
    ys = [0] + [v for yc in opens for v in (yc - 13, yc + 13)] + [prom0 - HR_SW]
    for a, b in zip(ys[0::2], ys[1::2]):
        if b > a:          # 最南边的斑马线口子会超出纵路尽头
            barriers.append([x - VW + 2, a, 2 * VW - 4, b - a])
polys = [[[0, RIVER_Y - 4], [W, RIVER_Y - 4], [W, H], [0, H]]]

# ── 车（右侧通行；环线只右转）──
x1, x2 = VR
e_av, w_av = av_c + 18, av_c - 18
e2, w2, e3, w3 = r2_c + 10, r2_c - 10, r3_c + 10, r3_c - 10
cars = [
    {"type": "taxi", "pts": [[x1 + 10, e_av], [x2 - 10, e_av], [x2 - 10, w2], [x1 + 10, w2]], "speed": 46, "loop": True},
    {"type": "car_red", "pts": [[x2 - 10, w2], [x1 + 10, w2], [x1 + 10, e_av], [x2 - 10, e_av]], "speed": 42, "loop": True},
    {"type": "car_red", "pts": [[x1 + 10, e2], [x2 - 10, e2], [x2 - 10, w3], [x1 + 10, w3]], "speed": 44, "loop": True},
    {"type": "bus", "pts": [[W + 80, w_av], [-80, w_av]], "speed": 32, "loop": False},
    {"type": "taxi", "pts": [[W + 500, w_av], [-80, w_av]], "speed": 48, "loop": False},
    {"type": "car_red", "pts": [[-60, e_av], [W + 60, e_av]], "speed": 46, "loop": False},
    {"type": "bus", "pts": [[-700, e_av], [W + 80, e_av]], "speed": 30, "loop": False},
    {"type": "taxi", "pts": [[-60, e3], [W + 60, e3]], "speed": 44, "loop": False},
    {"type": "car_red", "pts": [[W + 60, w3], [-60, w3]], "speed": 40, "loop": False},
    {"type": "taxi", "pts": [[x2 - 10, -60], [x2 - 10, prom0 - HR_SW - 30]], "speed": 42, "loop": False},
    {"type": "car_red", "pts": [[x1 + 10, prom0 - HR_SW - 30], [x1 + 10, -60]], "speed": 40, "loop": False},
]

# ── NPC ──
T = ["npc_office", "npc_student", "npc_office_b", "npc_student_g", "npc_student_r", "npc_office_c"]
sN = lambda y, hw, sw: y - hw - sw // 2 - 1      # 横路北侧人行道（避开路缘的树）
sS = lambda y, hw, sw: y + hw + 5
VL = VW + 8                                        # 纵路人行道行走线到路中心的距离
alley_y = lambda bi: blocks[bi]["y"] + (blocks[bi]["alley"][0] + blocks[bi]["alley"][1]) // 2
LINES = {
    "office": ["今天又要加班……", "楼下新开了家咖啡店，去试试？", "地铁太挤了，还是走路吧。", "你好！"],
    "student": ["放学啦！", "我要去买漫画书！", "这家面包超好吃！", "嘿，要一起去广场吗？"],
}
lines = lambda t: LINES["office" if "office" in t else "student"]
npcs = []


def walker(t, path):
    npcs.append({"type": t, "path": [[round(x), round(y)] for x, y in path], "lines": lines(t)})


def idler(t, x, y, face, ln=None):
    npcs.append({"type": t, "idle": face, "path": [[round(x), round(y)]], "lines": ln or lines(t)})


for i, (y, hw, sw, med) in enumerate(HROADS):
    for k, (side, x0, x1_) in enumerate([(sN, 40, x1 - 40), (sS, x1 + 40, x2 - 40), (sN, x2 + 40, W - 40), (sS, 40, x1 - 40)]):
        if i == 0 and side is sN:
            continue    # 大道北侧是 CBD 前人行道，下面单独安排
        walker(T[(i * 4 + k) % 6], [(x0, side(y, hw, sw)), (x1_, side(y, hw, sw))])
cbd_walk = ROW0_BOTTOM + 2
walker(T[0], [(60, cbd_walk), (x1 - 50, cbd_walk)])
walker(T[2], [(x1 + 50, cbd_walk), (x2 - 50, cbd_walk)])
walker(T[5], [(x2 + 50, cbd_walk), (W - 60, cbd_walk)])
walker(T[1], [(x2 - 50, cbd_walk + 2), (x1 + 50, cbd_walk + 2)])
for bi in (3, 5, 6, 7, 8):   # 后巷里各有人穿行
    b = blocks[bi]
    walker(T[bi % 6], [(b["x"] + 30, alley_y(bi)), (b["x"] + b["w"] - 30, alley_y(bi))])
walker(T[3], [(pl["x"] + 60, pl["y"] + pa1 - 16), (pl["x"] + pl["w"] - 60, pl["y"] + pa1 - 16)])
walker(T[4], [(pl["x"] + pl["w"] - 80, pl["y"] + pa0 + 18), (pl["x"] + 80, pl["y"] + pa0 + 18)])
walker(T[1], [(60, prom0 + 40), (x1 - 40, prom0 + 40)])
walker(T[2], [(x2 + 40, prom0 + 40), (W - 60, prom0 + 40)])
# 广场里站着聊天的人
idler(T[0], pcx - 60, pcy + 6, "right", ["听说周末广场有市集！", "嗯，我也想去看看。"])
idler(T[4], pcx - 30, pcy + 6, "left", ["真的吗？几点开始？", "那我们一起去吧！"])
idler(T[5], pcx + 120, pcy - 30, "down", ["等人呢，他总是迟到。"])
idler(T[3], pcx + 150, pcy + 30, "left", ["要不要来杯奶茶？"])
idler(T[1], 1400, prom0 + 44, "down", ["河边的风好舒服～"])
idler(T[2], 1430, prom0 + 44, "left", ["下班来这儿散散步正好。"])
idler(T[0], colx[1] + 200, ROW0_BOTTOM + 2, "down", ["公交怎么还不来……"])

birds = [{"x": pcx + 40, "y": pcy + 20, "n": 8}, {"x": 1200, "y": prom0 + 30, "n": 6}, {"x": colx[2] + 200, "y": cbd_walk + 4, "n": 5}]

# ── 主角路线：[x, y, 停留, 允许被挡, 动作] ──
sx_w1 = x1 - VW - SWV - 14     # 纵路 1 西侧的斑马线 x
P = []
add = lambda *a: P.append(list(a))
y_p = prom0 + 40
b6 = blocks[6]
ya = alley_y(6)
yc = pl["y"] + pa0 + 48
xe = x1 - VL                    # apt_a 东侧（纵路西人行道）
add(200, y_p, 0.3)
add(VX - 120, y_p, 0.2)
add(VX, prom0 + 30, 0.5, 0.6, "buy")                       # 河边售货机买饮料
add(sx_w1, prom0 + 30, 0.0)
add(sx_w1, sS(r3_c, HR_HW, HR_SW), 0, 0.6, "wait_ns")      # 等绿灯
add(sx_w1, sN(r3_c, HR_HW, HR_SW), 0.2)                    # 过路 3
add(xe, sN(r3_c, HR_HW, HR_SW), 0)
add(xe, ya, 0)
add(xe - 260, ya, 0.6)                                      # 走进 apt_a 的后巷（前排楼变半透明）
add(xe - 260, ya, 0.3, 0.6, "say:后巷好安静……")
add(xe, ya, 0)
add(xe, sS(r2_c, HR_HW, HR_SW), 0)
add(sx_w1, sS(r2_c, HR_HW, HR_SW), 0, 0.6, "wait_ns")
add(sx_w1, sN(r2_c, HR_HW, HR_SW), 0.2)                     # 过路 2
add(x1 - VL, sN(r2_c, HR_HW, HR_SW), 0)
add(x1 - VL, r2_c - HR_HW - HR_SW - 14, 0, 0.6, "wait_ew")
add(x1 + VL, r2_c - HR_HW - HR_SW - 14, 0.2)                # 过纵路（斑马线）
add(x1 + VL, yc, 0)
add(pl["x"] + 60, yc, 0)                                    # 进广场
add(pl["x"] + 60, pcy + 6, 0)
add(pcx - 90, pcy + 6, 0.3, 0.6, "talk:%d" % (len(npcs) - 7))   # 和聊天的人搭话
add(pcx - 90, pcy + 30, 0.6)
add(pcx + 60, pcy + 30, 0.2)
add(pcx + 60, pl["y"] + pa0 + 12, 0.3)
add(pcx + 60, pl["y"] + pa0 + 4, 0.8, 0.8)                  # 撞北排店铺的墙
add(pl["x"] + pl["w"] - 60, pl["y"] + pa0 + 12, 0)
add(pl["x"] + pl["w"] + 6, pl["y"] + pa0 + 12, 0)
add(x2 - VL, pl["y"] + pa0 + 12, 0)
add(x2 - VL, av_c + AV_HW + AV_SW // 2 + 2, 0)
add(x2 - VW - SWV - 14, av_c + AV_HW + AV_SW // 2 + 2, 0, 0.6, "wait_ns")
add(x2 - VW - SWV - 14, av_c - AV_HW - AV_SW // 2 - 1, 0.2)   # 过林荫大道
add(x2 - VW - SWV - 14, cbd_walk, 0)
add(colx[1] + 300, cbd_walk, 0.5, 0.6, "say:好高的楼！")
add(colx[1] + 260, cbd_walk, 2.0)
P = [p for p in P if p]
start = P[0][:2]

json.dump({"world": [W, H], "ground": "ground.png", "blocks": blocks, "solids": solids, "props": props, "polys": polys, "barriers": barriers,
           "intersections": INTERS, "vendings": vendings, "cars": cars, "npcs": npcs, "birds": birds, "river_y": RIVER_Y,
           "player": {"start": start, "route": P}}, open(A / "city.json", "w"), indent=1, ensure_ascii=False)
print(len(blocks), "blocks", len(props), "props", len(cars), "cars", len(npcs), "npcs", len(P), "route pts")
