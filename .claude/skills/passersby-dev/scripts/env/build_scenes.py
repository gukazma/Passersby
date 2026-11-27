"""组装 A1.3 横版场景：out/<id>/<id>.json + 同目录图片 + out/preview_<id>.png（原生比例，带 110 px 灰色比例人）。

    ~/tools/vid/bin/python tools/build_scenes.py        （在 ~/pw/a13/env 下运行）
json 字段（与游戏代码约定）：id,name,side,kind,width,band,layers[{img,x,y,parallax,z}],
props[{img,x,y_foot,solid:[w,h],ox?,oy?}]（x = 脚底中心，图片底边中点对齐 (x,y_foot)），doors[{id,label,x0,x1,interior?}],
exits{left,right}，zebras[{x0,x1,to,label}]，室内另有 entry{x,y}。
"""
import json, pathlib, shutil, subprocess, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFont

E = pathlib.Path(__file__).resolve().parent.parent
SRC, OUT, TOOLS = E / "src", E / "out", E / "tools"
FONT = ImageFont.truetype(str(TOOLS / "px.woff2"), 12)
PY = sys.executable
BASE, BAND1 = 392, 468


# ---------- 图像小工具（不依赖 scipy） ----------
def components(mask):
    H, W = mask.shape; lab = np.zeros((H, W), np.int32); comps = []
    for sy, sx in zip(*np.nonzero(mask)):
        if lab[sy, sx]:
            continue
        n = len(comps) + 1; q = deque([(sy, sx)]); lab[sy, sx] = n; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = n; q.append((yy, xx))
        comps.append(pts)
    return comps


def clean_crop(img, keep=0.02):
    """去小碎块（< 最大块的 keep 或 < 30 px），再裁到不透明范围。"""
    A = np.array(img.convert("RGBA")); al = A[..., 3] > 0
    comps = components(al)
    if comps:
        big = max(len(c) for c in comps)
        for c in comps:
            if len(c) < max(30, keep * big):
                ys, xs = zip(*c); A[list(ys), list(xs), 3] = 0
    al = A[..., 3] > 0; ys, xs = np.nonzero(al)
    return Image.fromarray(A[ys.min():ys.max() + 1, xs.min():xs.max() + 1])


def fix_pink(img):
    """洋红串色（如汤锅蒸汽被染粉）→ 浅灰白。"""
    A = np.array(img.convert("RGBA")); r, g, b = (A[..., i].astype(int) for i in range(3))
    pink = (r > 150) & (b > 140) & (r - g > 14) & (b - g > 8) & (np.abs(r - b) < 60) & (A[..., 3] > 0)
    lum = (r + g + b) / 3
    A[pink, 0] = np.clip(lum[pink] + 30, 0, 245); A[pink, 1] = np.clip(lum[pink] + 27, 0, 242); A[pink, 2] = np.clip(lum[pink] + 22, 0, 236)
    return Image.fromarray(A)


def find_board(img, min_w=24):
    """精灵里最大的平涂矩形（空白招牌）。"""
    A = np.array(img.convert("RGBA")); al = A[..., 3] > 0
    key = A[..., 0].astype(int) * 65536 + A[..., 1].astype(int) * 256 + A[..., 2]
    best = None
    vals, cnt = np.unique(key[al], return_counts=True)
    for v in vals[cnt > 80]:
        for c in components((key == v) & al):
            ys, xs = zip(*c); x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            w, h = x1 - x0 + 1, y1 - y0 + 1
            if w >= min_w and h >= 9 and w >= 1.6 * h and len(c) > 0.75 * w * h:
                if best is None or w * h > best[2] * best[3]:
                    best = (x0, y0, w, h)
    return best


def bake(img, box, text, maxscale=2, lines=None, fg=None):
    img = img.convert("RGBA"); A = np.array(img); x, y, w, h = box
    bgc = A[y + h // 2, x + w // 2, :3].astype(float); lum = bgc @ [0.3, 0.59, 0.11]
    fgc = fg or ("#fff4dc" if lum < 150 else "#3a2116"); sh = "#2a140c" if lum < 150 else None
    rows = lines or [text]
    adv = lambda ch: (13 if ord(ch) > 0x2e80 else int(FONT.getlength(ch)) + 1)
    rw = lambda r: sum(adv(c) for c in r) - 1
    tw = max(rw(r) for r in rows); th = 13 * len(rows) + (1 if sh else 0)
    k = max(1, min(maxscale, (w - 6) // tw, (h - 4) // th))
    lay = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    for li, r in enumerate(rows):
        cx = (tw - rw(r)) // 2
        for ch in r:
            if sh: ld.text((cx, li * 13 + 1), ch, font=FONT, fill=sh)
            ld.text((cx, li * 13), ch, font=FONT, fill=fgc); cx += adv(ch)
    la = np.array(lay); la[..., 3] = np.where(la[..., 3] > 127, 255, 0)
    lay = Image.fromarray(la).resize((tw * k, th * k), Image.NEAREST)
    img.paste(lay, (x + (w - lay.width) // 2, y + (h - lay.height) // 2), lay)
    return img


def trim_edges(img):
    """不透明大图：边缘行/列若与相邻行/列差异很大（降采样相位留下的暗边），裁掉。"""
    a = np.array(img.convert("RGB")).astype(int); x0, y0, x1, y1 = 0, 0, a.shape[1], a.shape[0]
    diff = lambda u, v: np.abs(u - v).mean()
    while diff(a[:, x0], a[:, x0 + 1]) > 25: x0 += 1
    while diff(a[:, x1 - 1], a[:, x1 - 2]) > 25: x1 -= 1
    while diff(a[y0], a[y0 + 1]) > 25: y0 += 1
    while diff(a[y1 - 1], a[y1 - 2]) > 25: y1 -= 1
    return img.crop((x0, y0, x1, y1))


def ground(id_, width, kind):
    subprocess.run([PY, str(TOOLS / "ground.py"), str(OUT / id_), id_, str(width), "--kind", kind], check=True, capture_output=True)


# ---------- 共用素材 ----------
SIGN = json.load(open(E / "maps" / "sign_choice.json", encoding="utf-8"))   # 选定的 AI 写字版本
def P(name):
    return Image.open(SRC / name).convert("RGBA")

lib = {
    "tree": clean_crop(P("props_street_parts/00.png")), "lamp": clean_crop(P("props_street_parts/01.png")),
    "stall": clean_crop(P("props_street_parts/02.png")), "kiosk": clean_crop(P("props_street_parts/05.png")),
    "light": clean_crop(P("props_street_parts/06.png")), "post": clean_crop(P("props_street_parts/07.png")),
    "pot_s": clean_crop(P("props_street_parts/10.png")), "pot_m": clean_crop(P("props_street_parts/08.png")),
    "pot_l": clean_crop(P("props_street_parts/09.png")), "hydrant": clean_crop(P("props_street_parts/11.png")),
    "bench": clean_crop(P("fit_bench_1x.png")), "bicycle": clean_crop(P("fit_bicycle_1x.png")),
    "gate": clean_crop(P(SIGN["gate"])), "teakiosk": clean_crop(P(SIGN["kiosk"])),
    "slamp": clean_crop(P("props_pier_parts/09.png")), "lifebuoy": clean_crop(P("fit_lifebuoy_1x.png")),
    "bollard": clean_crop(P("fit_bollard_1x.png")), "railing": clean_crop(P("fit_railing_1x.png")),
    "counter": clean_crop(fix_pink(P("furn_chenji_parts/01.png"))), "table": clean_crop(P("fit_table_1x.png")),
    "stool_r": clean_crop(P("fit_stool_red_1x.png")), "stool_w": clean_crop(P("fit_stool_wood_1x.png")),
    "fridge": clean_crop(P("fit_fridge_1x.png")), "shelf": clean_crop(P("fit_shelf_1x.png")), "fan": clean_crop(P("fit_fan_1x.png")),
}
# 11-27 起：所有招牌字都在 AI 原图上完成（AI 编辑写字 / 小牌子在原图上用黑体描边写），像素化之后不再贴字
lib["post_yongan"] = clean_crop(P("fit_post_yongan_1x.png"))
lib["post_binjiang"] = clean_crop(P("fit_post_binjiang_1x.png"))

SOLID = {"tree": (22, 8), "lamp": (8, 4), "stall": None, "kiosk": None, "light": (8, 4), "post_yongan": (6, 4), "post_binjiang": (6, 4),
         "pot_s": None, "pot_m": None, "pot_l": None, "hydrant": None, "bench": None, "bicycle": None, "gate": None, "teakiosk": None,
         "slamp": (8, 4), "lifebuoy": (6, 4), "bollard": None, "railing": None, "counter": None, "table": None, "stool_r": None,
         "stool_w": None, "fridge": None, "shelf": None, "fan": (10, 6)}
DEPTH = {"stall": 18, "kiosk": 20, "bench": 10, "bicycle": 6, "gate": 0, "teakiosk": 20, "bollard": 8, "railing": 6, "counter": 16,
         "table": 14, "stool_r": 8, "stool_w": 8, "fridge": 12, "shelf": 10, "pot_s": 6, "pot_m": 8, "pot_l": 10, "hydrant": 6}


class Scene:
    def __init__(self, id_, name, kind, width, side=None, band=(BASE, BAND1)):
        self.d = {"id": id_, "name": name, "side": side, "kind": kind, "width": width, "band": list(band), "layers": [], "props": [],
                  "doors": [], "exits": {"left": None, "right": None}, "zebras": []}
        self.dir = OUT / id_; self.dir.mkdir(parents=True, exist_ok=True); self.used = set()

    def img(self, name, im):
        if name not in self.used:
            im.save(self.dir / f"{name}.png"); self.used.add(name)
        return f"{name}.png"

    def layer(self, name, im, x, y, parallax=1.0, z=-10):
        self.d["layers"].append({"img": self.img(name, im), "x": x, "y": y, "parallax": parallax, "z": z, "w": im.width, "h": im.height})

    def prop(self, name, x, y_foot, solid="auto"):
        im = lib[name]
        if solid == "auto":
            s = SOLID.get(name, None)
            solid = list(s) if s else ([max(4, im.width - 8), DEPTH.get(name, 8)] if name in DEPTH else None)
        p = {"img": self.img(name, im), "x": x, "y_foot": y_foot, "w": im.width, "h": im.height}
        if solid: p["solid"] = solid
        self.d["props"].append(p)

    def save(self):
        json.dump(self.d, open(self.dir / f"{self.d['id']}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def preview(self, figures=(), notes=()):
        W = self.d["width"]; can = Image.new("RGBA", (W, 540), (22, 16, 13, 255))
        for L in sorted(self.d["layers"], key=lambda l: l["z"]):
            im = Image.open(self.dir / L["img"]).convert("RGBA")
            xs = range(int(L["x"]), W, im.width) if L["parallax"] < 1 else [int(L["x"])]   # 预览里远景直接平铺
            for xx in xs:
                can.paste(im, (xx, int(L["y"])), im)
        items = [("p", p) for p in self.d["props"]] + [("f", f) for f in figures]
        for kind, it in sorted(items, key=lambda t: t[1]["y_foot"] if t[0] == "p" else t[1][1]):
            if kind == "p":
                im = Image.open(self.dir / it["img"]).convert("RGBA")
                can.paste(im, (int(it["x"] - im.width // 2), int(it["y_foot"] - im.height + 1)), im)
            else:
                x, yf = it; d = ImageDraw.Draw(can)
                d.rectangle([x - 11, yf - 85, x + 11, yf], fill=(128, 128, 128, 255)); d.ellipse([x - 12, yf - 110, x + 12, yf - 84], fill=(128, 128, 128, 255))
        d = ImageDraw.Draw(can)
        for z in self.d["zebras"]:
            d.rectangle([z["x0"], 530, z["x1"], 538], outline=(0, 255, 0, 255))
        for dr in self.d["doors"]:
            d.line([(dr["x0"], BASE + 2), (dr["x1"], BASE + 2)], fill=(255, 220, 0, 255), width=2)
        for x, y, t in notes:
            d.text((x, y), t, fill=(255, 255, 0, 255))
        can.convert("RGB").save(OUT / f"preview_{self.d['id']}.png")


def zebra_layer(sc, x0):
    sc.layer(f"zebra", Image.open(OUT / "zebra.png").convert("RGBA"), x0, 476, 1.0, -9)


def street_ground(sc, kind):
    ground(sc.d["id"], sc.d["width"], kind)
    g = OUT / sc.d["id"] / f"ground_{sc.d['id']}.png"
    sc.d["layers"].append({"img": g.name, "x": 0, "y": 0, "parallax": 1.0, "z": -10, "w": sc.d["width"], "h": 540})
    sc.used.add(g.stem)


# ---------- 永安街北侧 ----------
subprocess.run([PY, str(TOOLS / "ground.py"), str(OUT), "tmp", "64"], check=True, capture_output=True)   # zebra.png / alley.png
alley = Image.open(OUT / "alley.png").convert("RGBA")
bg_old = trim_edges(P("bg_oldtown_1x.png")); bg_hb = trim_edges(P("bg_harbour_1x.png"))
r1, r2, r3, rs = P("row_yn_block1.png"), P("row_yn_block2.png"), P("row_yn_block3.png"), P("row_ys_block1.png")

X1 = 200; X2 = X1 + r1.width + 44; X3 = X2 + r2.width + 44; WN = X3 + r3.width + 270
yn = Scene("yongan_n", "永安街（北侧）", "street", WN, side="north")
yn.layer("bg_oldtown", bg_old, 0, BASE - bg_old.height, round((bg_old.width - 960) / (WN - 960), 3), -20)
street_ground(yn, "oldtown")
yn.layer("row_yn_block1", r1, X1, BASE - r1.height); yn.layer("alley", alley, X1 + r1.width, BASE - alley.height)
yn.layer("row_yn_block2", r2, X2, BASE - r2.height); yn.layer("alley", alley, X2 + r2.width, BASE - alley.height)
yn.layer("row_yn_block3", r3, X3, BASE - r3.height)
zx = X1 + r1.width + 22 - 48
zebra_layer(yn, zx)
yn.d["zebras"].append({"x0": zx, "x1": zx + 96, "to": "yongan_s", "label": "过马路 → 永安街南侧"})
D = [("L01-1", "陈记云吞面", X1 + 212, X1 + 302, "chenji"), ("L02-1", "福安堂凉茶", X1 + 668, X1 + 722, None),
     ("L03-1", "钟记钟表行", X1 + 925, X1 + 978, None), ("L04-1", "永和五金", X2 + 100, X2 + 230, None),
     ("L05-1", "何记烧腊", X2 + 400, X2 + 510, None), ("L05-2", "何家唐楼（楼梯）", X2 + 530, X2 + 580, None),
     ("L06-1", "永安茶楼", X2 + 785, X2 + 880, None), ("L07-1", "新华理发", X3 + 165, X3 + 225, None),
     ("L08-1", "永安街坊会", X3 + 440, X3 + 485, None), ("L09-1", "天后古庙", X3 + 715, X3 + 800, None)]
for i, l, a, b, it in D:
    dd = {"id": i, "label": l, "x0": a, "x1": b}
    if it: dd["interior"] = it
    yn.d["doors"].append(dd)
yn.d["exits"]["right"] = {"to": "binjiang", "label": "转入滨江路", "x": WN - 60, "y": 430}
for x in (X1 + 440, X2 + 300, X3 + 70, X3 + r3.width + 30):
    yn.prop("tree", x, 462)
for x in (X1 + 800, X2 + 700, X3 + 600):
    yn.prop("lamp", x, 464)
yn.prop("kiosk", 100, 420); yn.prop("post_yongan", 170, 464)
yn.prop("bicycle", X1 + 790, 398); yn.prop("stall", X2 + 300, 414)
yn.prop("hydrant", X2 + 60, 462); yn.prop("bench", X3 + 340, 404); yn.prop("pot_l", X2 + 980, 398)
yn.prop("light", WN - 120, 466); yn.prop("post_binjiang", WN - 60, 464)
yn.save(); yn.preview(figures=[(X1 + 245, 430), (X2 + 830, 420), (X3 + 760, 440)])

# ---------- 永安街南侧 ----------
XS = 160; WS = XS + rs.width + 260
ys = Scene("yongan_s", "永安街（南侧）", "street", WS, side="south")
ys.layer("bg_oldtown", bg_old, 0, BASE - bg_old.height, round((bg_old.width - 960) / (WS - 960), 3), -20)
street_ground(ys, "oldtown")
ys.layer("row_ys_block1", rs, XS, BASE - rs.height)
zx = XS + 560
zebra_layer(ys, zx)
ys.d["zebras"].append({"x0": zx, "x1": zx + 96, "to": "yongan_n", "label": "过马路 → 永安街北侧"})
for i, l, a, b in (("L10-1", "永安街市", XS + 230, XS + 410), ("L11-1", "拾光书店", XS + 765, XS + 800), ("L12-1", "永安小学", XS + 965, XS + 1100)):
    ys.d["doors"].append({"id": i, "label": l, "x0": a, "x1": b})
for x in (XS + 140, XS + 880, XS + rs.width + 120):
    ys.prop("tree", x, 462)
for x in (XS + 450, XS + 1150):
    ys.prop("lamp", x, 464)
ys.prop("bench", XS + 1180, 404); ys.prop("pot_m", XS + 860, 398); ys.prop("post_yongan", 90, 464)
ys.save(); ys.preview(figures=[(XS + 320, 430), (XS + 1030, 440)])

# ---------- 滨江路 ----------
WB = 1900
bj = Scene("binjiang", "滨江路", "street", WB, side="river")
bj.layer("bg_harbour", bg_hb, 0, BASE - bg_hb.height + 40, 0.3, -20)
street_ground(bj, "promenade")
rw = lib["railing"].width; step = rw - 14; G0, G1 = 1004, 1268          # 渡口门两侧栏杆贴门排，不留缺口
x = G0 - rw // 2
while x + rw // 2 > -step:
    bj.prop("railing", x, 393, [rw, 6]); x -= step
x = G1 + rw // 2
while x - rw // 2 < WB:
    bj.prop("railing", x, 393, [rw, 6]); x += step
bj.prop("gate", 1136, 396, None)
bj.d["doors"].append({"id": "M01-1", "label": "旧港渡轮码头", "x0": 1080, "x1": 1192})
bj.prop("teakiosk", 1580, 412)
for x in (300, 880, 1760):
    bj.prop("slamp", x, 398)
for x in (430, 1380):
    bj.prop("bollard", x, 400)
bj.prop("lifebuoy", 700, 396)
for x in (560, 1840):
    bj.prop("bench", x, 404)
bj.prop("post_binjiang", 150, 464); bj.prop("light", 70, 466)
bj.d["exits"]["left"] = {"to": "yongan_n", "label": "回永安街", "x": 60, "y": 430}
bj.save(); bj.preview(figures=[(640, 430), (1136, 420), (1500, 440)])

# ---------- 陈记云吞面 室内 ----------
room = P(SIGN["room"] + "_1x.png"); meta = json.load(open(SRC / (SIGN["room"] + ".json")))
A = np.array(room); bx0, by0, bx1, by1 = meta["scale_figure_box_native"]
bx0 -= 2; bx1 += 2; by0 -= 3; by1 += 2; w = bx1 - bx0
A[by0:by1, bx0:bx1] = A[by0:by1, bx0 - w:bx0]                 # 比例人：用左侧同一行的墙/地砖补上
room = Image.fromarray(A)
FLOOR0, FLOOR1 = 333, 397                                      # 房间图里：后墙脚 / 前墙截面上沿
OX, OY = (960 - room.width) // 2, BASE - FLOOR0
can = Image.new("RGBA", (960, 540), (22, 16, 13, 255)); can.alpha_composite(room, (OX, OY))
ch = Scene("chenji", "陈记云吞面", "interior", 960, side=None, band=(BASE, BASE + FLOOR1 - FLOOR0 - 2))
ch.layer("room_chenji", can, 0, 0, 1.0, -10)
ch.d["entry"] = {"x": OX + 384, "y": BASE + FLOOR1 - FLOOR0 - 6}
ch.d["exits"] = {"left": None, "right": None, "bottom": {"to": "yongan_n", "door": "L01-1", "label": "出门（永安街）", "x0": OX + 356, "x1": OX + 411}}
ch.d["doors"].append({"id": "chenji-kitchen", "label": "后厨（店家专用）", "x0": OX + 631, "x1": OX + 715})
ch.prop("counter", OX + 535, BASE + 10); ch.prop("fridge", OX + 40, BASE + 4)   # 货架放哪都挡菜单牌，去掉
for tx in (OX + 150, OX + 290):
    ch.prop("table", tx, BASE + 44)
    ch.prop("stool_r", tx - 42, BASE + 48); ch.prop("stool_w", tx + 42, BASE + 48); ch.prop("stool_r", tx, BASE + 26)
ch.prop("fan", OX + 220, BASE + 20)
ch.d["npc_spots"] = {"owner": {"x": OX + 575, "y_foot": BASE + 4, "face": "front", "note": "陈伯在柜台后"}, "diner": {"x": OX + 128, "y_foot": BASE + 48, "pose": "sit", "note": "食客坐红凳吃面"}}
ch.d["props"] = [p for p in ch.d["props"] if not (p["img"].startswith("stool") and abs(p["x"] - 224) <= 22)]   # 食客精灵自带凳子
ch.save()
tb = lib["table"]; st = lib["stool_r"]; ct = lib["counter"]
ch.preview(figures=[(OX + 680, BASE + 30), (OX + 440, BASE + 56)],
           notes=[(8, 8, f"scale: figure 110 | door(kitchen) 150 | table {tb.height} | stool {st.height} | counter top ~65 | fridge {lib['fridge'].height} | ceiling ~175")])
shutil.rmtree(OUT / "tmp", ignore_errors=True)
print("ok", {s.d["id"]: s.d["width"] for s in (yn, ys, bj, ch)})
