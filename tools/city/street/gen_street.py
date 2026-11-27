"""试验街「永安街」：整排 AI 楼（抠底透明、高低错落、两端完整）+ 程序画的路。

输入：rows/yongan_N.png/.json、rows/yongan_S.png/.json（街景美术分支产出，真像素 RGBA）
输出：out/ground.png、out/city.json、out/blocks/（拷贝行图）
city.json 里每排楼是一个 "rows" 条目：按楼切片排序/淡出，每栋楼的碰撞只算主体（楼顶上伸出来的水箱、楼梯间只遮挡）。
"""
import json
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "rows")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out")
(OUT / "blocks").mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)

PAL = {"asphalt": [(78, 80, 86), (72, 74, 80), (84, 86, 92)], "curb": (140, 136, 128), "walk": (204, 196, 180), "walk_line": (184, 176, 160),
       "yard": (186, 176, 158), "yard_line": (168, 158, 140), "plaza": (214, 204, 184), "plaza_line": (190, 178, 158),
       "lane": (232, 196, 80), "white": (236, 236, 230), "water": [(70, 130, 150), (62, 120, 140), (84, 146, 164)]}

ROWS = {}
for k in ("N", "S"):
    m = json.load(open(SRC / f"yongan_{k}.json"))
    m["img"] = f"yongan_{k}"
    shutil.copy(SRC / f"yongan_{k}.png", OUT / "blocks" / f"yongan_{k}.png")
    m["alpha"] = np.array(Image.open(SRC / f"yongan_{k}.png").convert("RGBA"))[..., 3] > 0
    ROWS[k] = m

VW, SWV = 20, 22                    # 纵路半宽、纵路人行道
HW, SW = 22, 24                     # 横路半宽、横路人行道
BACK, LANE = 70, 18                 # 北排楼后面的后院、南排楼后面的小巷
MARGIN = 30
rw = max(ROWS["N"]["w"], ROWS["S"]["w"])
xL = MARGIN + VW                    # 西纵路中心
x0 = xL + VW + SWV + 24             # 楼排可用区左边
W = x0 + rw + 24 + SWV + VW + VW + MARGIN
xR = W - MARGIN - VW                # 东纵路中心
rowx = {k: x0 + (rw - ROWS[k]["w"]) // 2 for k in ROWS}
yN_top = BACK
yN_base = yN_top + ROWS["N"]["base"]
y1 = yN_base + SW + HW              # 永安街中心
yS_top = y1 + HW + SW + LANE
yS_base = yS_top + ROWS["S"]["base"]
y2 = yS_base + SW + HW              # 滨江路中心
prom0 = y2 + HW + SW
RIVER_Y = prom0 + 70
H = RIVER_Y + 70
HROADS = [(y1, "永安街"), (y2, "滨江路")]
VR = [xL, xR]
print("world", W, H, "rows N", rowx["N"], yN_top, "S", rowx["S"], yS_top, "roads", y1, y2)

img = np.zeros((H, W, 3), np.uint8)


def noise(xa, ya, xb, yb, cols, p=(0.08, 0.93)):
    xa, ya, xb, yb = max(0, int(xa)), max(0, int(ya)), min(W, int(xb)), min(H, int(yb))
    if xb <= xa or yb <= ya:
        return
    r = rng.random((yb - ya, xb - xa))
    a = np.empty((yb - ya, xb - xa, 3), np.uint8)
    a[:] = cols[0]
    a[r < p[0]] = cols[1]
    a[r > p[1]] = cols[2]
    img[ya:yb, xa:xb] = a


def tiles(xa, ya, xb, yb, col, line, t=8):
    xa, ya, xb, yb = max(0, int(xa)), max(0, int(ya)), min(W, int(xb)), min(H, int(yb))
    img[ya:yb, xa:xb] = col
    for yy in range(ya, yb, t):
        img[yy, xa:xb] = line
    for yy in range(ya, yb, t):
        off = 0 if ((yy - ya) // t) % 2 == 0 else t // 2
        for xx in range(xa + off, xb, t):
            img[yy:min(yy + t, yb), xx] = line


# 地面：后院铺装（楼后面能走）→ 人行道 → 路
tiles(0, 0, W, H, PAL["yard"], PAL["yard_line"], 10)
for y, _ in HROADS:
    tiles(0, y - HW - SW, W, y + HW + SW, PAL["walk"], PAL["walk_line"], 8)
for x in VR:
    tiles(x - VW - SWV, 0, x + VW + SWV, prom0, PAL["walk"], PAL["walk_line"], 8)
for y, _ in HROADS:
    noise(0, y - HW, W, y + HW, PAL["asphalt"])
    img[y - HW - 1, :] = PAL["curb"]
    img[y + HW, :] = PAL["curb"]
for x in VR:
    noise(x - VW, 0, x + VW, prom0 - SW, PAL["asphalt"])
    img[:prom0 - SW, x - VW - 1] = PAL["curb"]
    img[:prom0 - SW, x + VW] = PAL["curb"]
INTERS = []
for x in VR:
    for y, _ in HROADS:
        noise(x - VW, y - HW, x + VW, y + HW, PAL["asphalt"])
        INTERS.append([x - VW, y - HW, 2 * VW, 2 * HW])
inter = lambda x, y, pad=0: any(abs(x - vx) <= VW + SWV + pad for vx in VR) and any(abs(y - hy) <= HW + SW + pad for hy, _ in HROADS)
for y, _ in HROADS:
    for x in range(0, W, 12):
        if not inter(x, y, 2):
            img[y - 1:y + 1, x:x + 6] = PAL["lane"]
for x in VR:
    for y in range(0, prom0 - SW, 12):
        if not inter(x, y, 2):
            img[y:y + 6, x - 1:x + 1] = PAL["lane"]
CROSS_H, CROSS_V = [], []
for x in VR:
    for y, _ in HROADS:
        for xc in (x - VW - SWV - 14, x + VW + SWV + 14):
            for k in range(-10, 11, 5):
                img[y - HW:y + HW, xc + k:xc + k + 3] = PAL["white"]
            CROSS_H.append((xc, y))
        for yc in (y - HW - SW - 14, y + HW + SW + 14):
            if yc < prom0 - SW:
                for k in range(-10, 11, 5):
                    img[yc + k:yc + k + 3, x - VW:x + VW] = PAL["white"]
                CROSS_V.append((x, yc))
tiles(0, prom0, W, RIVER_Y - 6, PAL["plaza"], PAL["plaza_line"], 10)
noise(0, RIVER_Y - 6, W, RIVER_Y, [(150, 140, 120), (140, 130, 112), (160, 150, 130)])
noise(0, RIVER_Y, W, H, PAL["water"])
Image.fromarray(img).save(OUT / "ground.png")

# ── 楼排：每栋楼一个切片；碰撞 = 楼主体（各列顶边的 75 分位以下），楼顶伸出来的东西只遮挡 ──
rows, solids, doors = [], [], []
for k, top in (("N", yN_top), ("S", yS_top)):
    m = ROWS[k]
    bx = rowx[k]
    a = m["alpha"]
    tops = np.where(a.any(0), a.argmax(0), m["h"])
    blds = []
    for b in m["buildings"]:
        c = tops[b["x0"]:b["x1"]]
        c = c[c < m["h"]]
        if len(c) == 0:
            continue
        body = int(b["solid_top_y"]) if "solid_top_y" in b else int(np.percentile(c, 75)) + 2   # 主体顶边（楼顶伸出来的东西不算）
        img_top = int(c.min())
        blds.append({"id": b["id"], "name": b.get("name", ""), "x0": b["x0"], "x1": b["x1"], "top": img_top, "body": body})
        solids.append([bx + b["x0"], top + body, b["x1"] - b["x0"], m["base"] - body])
    signs = [dict(s) for s in m.get("signs", [])]
    rows.append({"img": m["img"], "x": bx, "y": top, "w": m["w"], "h": m["h"], "base": m["base"], "buildings": blds, "signs": signs})
    for d in m.get("doors", []):
        doors.append({"id": d["id"], "x": bx + d["x"] + d["w"] // 2, "y": top + d["y"] + d["h"]})

# ── 道具：行道树（北侧人行道靠路缘一排，种在楼与楼之间，不挡门和招牌）、路灯（南侧人行道）、红绿灯 ──
FOOT = {"street_tree": [8, 6], "lamp2": [4, 4], "traffic_light": [4, 4], "bench2": [46, 8]}
props = []
prop = lambda n, x, y, **kw: props.append({"sprite": n, "x": round(x), "y": round(y), "foot": FOOT[n], **kw})
for y, _ in HROADS:
    k = "N" if y == y1 else "S"
    bx = rowx[k]
    edges = [bx + b["x1"] for b in ROWS[k]["buildings"][:-1]]
    doorx = [bx + d["x"] for d in ROWS[k].get("doors", [])] + [bx + d["x"] + d["w"] for d in ROWS[k].get("doors", [])]
    last = -999
    for ex in edges:
        if ex - last >= 70 and all(abs(ex - dx) > 6 for dx in doorx) and not inter(ex, y, 30):
            prop("street_tree", ex, y - HW - 1)
            last = ex
    for x in range(int(x0), int(x0 + rw), 120):
        if not inter(x + 60, y, 30):
            prop("lamp2", x + 60, y + HW + SW - 1)
for x in VR:
    for side in (-1, 1):
        for y in range(40, prom0 - SW - 20, 120):
            if not inter(x, y, 34):
                prop("street_tree", x + side * (VW + SWV - 4), y)
    for y, _ in HROADS:
        prop("traffic_light", x - VW + 2, y - HW - 3, light=["ns", 6])
        prop("traffic_light", x + VW - 2, y + HW + 10, light=["ns", 6])
        prop("traffic_light", x - VW + 2, y + HW + 10, light=["ew", 6])
        prop("traffic_light", x + VW - 2, y - HW - 3, light=["ew", 6])
for x in range(80, W, 160):
    prop("street_tree", x, prom0 + 12)
for x in range(160, W, 320):
    prop("bench2", x, RIVER_Y - 10)

# ── 路中护栏（只拦 NPC，主角随便过）──
barriers = []
for y, _ in HROADS:
    xs = [0] + [v for xc in sorted(xc for xc, yy in CROSS_H if yy == y) for v in (xc - 13, xc + 13)] + [W]
    for a_, b_ in zip(xs[0::2], xs[1::2]):
        if b_ > a_:
            barriers.append([a_, y - HW + 2, b_ - a_, 2 * HW - 4])
for x in VR:
    ys = [0] + [v for yc in sorted(yc for xx, yc in CROSS_V if xx == x) for v in (yc - 13, yc + 13)] + [prom0 - SW]
    for a_, b_ in zip(ys[0::2], ys[1::2]):
        if b_ > a_:
            barriers.append([x - VW + 2, a_, 2 * VW - 4, b_ - a_])
polys = [[[0, RIVER_Y - 4], [W, RIVER_Y - 4], [W, H], [0, H]]]

# ── 车（右侧通行）──
cars = [
    {"type": "taxi", "pts": [[-60, y1 + 11], [W + 60, y1 + 11]], "speed": 44, "loop": False},
    {"type": "car_red", "pts": [[W + 60, y1 - 11], [-60, y1 - 11]], "speed": 40, "loop": False},
    {"type": "bus", "pts": [[-500, y2 + 11], [W + 80, y2 + 11]], "speed": 30, "loop": False},
    {"type": "car_red", "pts": [[W + 60, y2 - 11], [-60, y2 - 11]], "speed": 42, "loop": False},
    {"type": "taxi", "pts": [[xR - 10, -60], [xR - 10, prom0 - SW - 30]], "speed": 42, "loop": False},
    {"type": "car_red", "pts": [[xL + 10, prom0 - SW - 30], [xL + 10, -60]], "speed": 40, "loop": False},
]

# ── NPC ──
T = ["npc_office", "npc_student", "npc_office_b", "npc_student_g", "npc_office_old", "npc_office_c", "hero_aunt", "npc_student_kid"]
LINES = ["早晨！今日去饮茶未？", "陈记的云吞面，真系一流。", "钟伯又在修那块怀表了。", "听讲新港计划要拆这条街……", "你好！"]
npcs = []
walker = lambda t, path: npcs.append({"type": t, "path": [[round(x), round(y)] for x, y in path], "lines": LINES})
idler = lambda t, x, y, face, ln: npcs.append({"type": t, "idle": face, "path": [[round(x), round(y)]], "lines": ln})
sN = lambda y: y - HW - SW // 2 - 2
sS = lambda y: y + HW + 6
for i, (y, _) in enumerate(HROADS):
    walker(T[i * 2], [(x0 + 40, sN(y)), (x0 + rw - 40, sN(y))])
    walker(T[i * 2 + 1], [(x0 + rw - 60, sS(y)), (x0 + 60, sS(y))])
walker(T[4], [(x0 + rw // 2, sN(y1) + 1), (x0 + 30, sN(y1) + 1)])
walker(T[5], [(60, prom0 + 40), (W - 60, prom0 + 40)])
walker(T[7], [(x0 + 30, yN_top - 30 + BACK // 2), (x0 + rw - 30, yN_top - 30 + BACK // 2)])
for d in doors[:3]:
    idler(T[6], d["x"] + 12, d["y"] + 8, "left", ["今日人好多啊。"])
    break

start = [x0 + rw // 2, sN(y1)]
route = [[start[0], start[1], 0.5], [x0 + 40, sN(y1), 0.3], [x0 + 40, sS(y1), 0.3], [x0 + rw - 40, sS(y1), 0.3],
         [x0 + rw - 40, sN(y1), 0.3], [start[0], start[1], 1.0]]
json.dump({"world": [W, H], "ground": "ground.png", "blocks": [], "rows": rows, "solids": solids, "props": props, "polys": polys,
           "barriers": barriers, "intersections": INTERS, "vendings": [], "cars": cars, "npcs": npcs, "birds": [], "river_y": RIVER_Y,
           "doors": doors, "player": {"start": start, "route": route}}, open(OUT / "city.json", "w"), indent=1, ensure_ascii=False)
print(len(rows), "rows", len(solids), "solids", len(props), "props", len(npcs), "npcs", len(doors), "doors")
