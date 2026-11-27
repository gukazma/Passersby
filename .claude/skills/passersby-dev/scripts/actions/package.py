"""挑定的动作条 → out/<角色>/<动作>.png/json（去洋红杂边、补字段），旺财 char.json，总览图。"""
import json, shutil, pathlib
import numpy as np
from PIL import Image, ImageDraw
A = pathlib.Path(__file__).resolve().parent; W = A / "work"; O = A / "out"
def clean(arr):
    for _ in range(12):
        r, g, b, a = (arr[..., i].astype(int) for i in range(4))
        mag = (a > 0) & (r - g > 30) & (b - g > 30) & (np.abs(r - b) < 120)
        H, Wd = mag.shape
        if not mag.any(): break
        for y, x in zip(*np.nonzero(mag)):
            nb = [(y + dy, x + dx) for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)) if 0 <= y + dy < H and 0 <= x + dx < Wd]
            if any(arr[q][3] == 0 for q in nb):
                arr[y, x, 3] = 0
            else:
                ok = [q for q in nb if not mag[q] and arr[q][3] > 0]
                if ok: arr[y, x] = arr[ok[0]]
    arr[..., 3] = np.where(arr[..., 3] > 0, 255, 0)
    return arr
def put(cid, anim, src_png, meta, extra=None):
    d = O / cid; d.mkdir(parents=True, exist_ok=True)
    arr = clean(np.array(Image.open(src_png).convert("RGBA")))
    Image.fromarray(arr).save(d / f"{anim}.png")
    m = dict(meta); m["file"] = f"{anim}.png"
    if extra: m.update(extra)
    json.dump(m, open(d / f"{anim}.json", "w"), ensure_ascii=False, indent=1)
    return arr, m
def spec(name, **extra):
    m = json.load(open(W / f"{name}.json")); return W / f"{name}.png", m, extra
CH = {"hero": 110, "luobo": 104, "yeyonghe": 108, "huangli": 101, "lele": 83, "yejun": 114, "wangcai": 52}
PLAN = [
 ("hero", "sit_bench", "hero_sitbench_b", {"loop": True, "seat": "bench", "prop": None}),
 ("hero", "photo", "hero_photo_a", {"loop": False, "shutter_frame": 3}),
 ("hero", "laugh", "hero_laugh_b", {"loop": True}),
 ("hero", "pet_dog", "hero_petdog_a", {"loop": True}),
 ("luobo", "sit_tea", "luobo_sittea_a", {"loop": True, "seat": "stool", "prop": None}),
 ("yeyonghe", "smoke", "yeyonghe_smoke_a", {"loop": True, "smoke_frame": 4}),
 ("yeyonghe", "sit_stool", "yeyonghe_sitstool_b", {"loop": True, "seat": "stool", "prop": None}),
 ("huangli", "laugh", "huangli_laugh_b", {"loop": True}),
 ("lele", "pet_dog", "lele_petdog_a", {"loop": True}),
 ("lele", "jump", "lele_jump_b", {"loop": False}),
 ("yejun", "phone", "yejun_phone_a", {"loop": True}),
 ("wangcai", "idle_side", "wangcai_wag_b", {"loop": True}),
 ("wangcai", "sit", "wangcai_sit_b", {"loop": True}),
 ("wangcai", "happy", "wangcai_happy2_b", {"loop": True}),
]
rows = []
for cid, anim, src, extra in PLAN:
    png, m, _ = spec(src)
    arr, mm = put(cid, anim, png, m, extra)
    if anim == "smoke":   # 嘴的位置（第 2 帧烟在嘴边）：头部高度 12–20% 处最右点
        f = arr[:, 2 * mm["frame_w"]:3 * mm["frame_w"], 3] > 0
        ys = np.nonzero(f.any(1))[0]; t, b = ys.min(), ys.max(); lo, hi = t + int((b - t) * .12), t + int((b - t) * .2)
        yy, xx = np.nonzero(f[lo:hi]); k = xx.argmax()
        mm["mouth_point"] = [int(xx[k] - mm["origin"][0]), int(yy[k] + lo - mm["origin"][1])]
        mm["note_fx"] = "烟由游戏用灰色像素粒子在 smoke_frame 从 mouth_point 冒出（AI 画的烟带洋红，已去掉）"
        json.dump(mm, open(O / cid / f"{anim}.json", "w"), ensure_ascii=False, indent=1)
    rows.append((f"{cid}/{anim}", arr, mm))
# 旺财走/跑（walkbuild 输出，含根运动）
for anim, src, fps in (("walk_side", "wangcai_walk2_a", 14), ("run_side", "wangcai_trot_a", 18)):
    m = json.load(open(W / f"{src}.json")); m["fps"] = fps; m["loop"] = True; m["view"] = "side"
    m["speed_px_s"] = round(sum(m["root_motion_px"]) / m["frames"] * fps, 1)
    arr, mm = put("wangcai", anim, W / f"{src}.png", m); rows.append((f"wangcai/{anim}", arr, mm))
for v in ("front", "back"):
    m = json.load(open(W / "wangcai_idle" / f"idle_{v}.json")); m["loop"] = True
    arr, mm = put("wangcai", f"idle_{v}", W / "wangcai_idle" / f"idle_{v}.png", m); rows.append((f"wangcai/idle_{v}", arr, mm))
# 旺财 char.json
anims = {}
for f in sorted((O / "wangcai").glob("*.json")):
    if f.name == "char.json": continue
    m = json.load(open(f)); k = f.stem
    anims[k] = {"file": m["file"], "frames": m["frames"], "fps": m["fps"], "frame_w": m["frame_w"], "frame_h": m["frame_h"],
                "origin": m["origin"], "root_motion_px": m.get("root_motion_px", [0] * m["frames"]), "axis": m.get("axis", "x"), "loop": m.get("loop", True)}
json.dump({"id": "wangcai", "name": "旺财", "height_px": 52, "kind": "dog", "anims": anims}, open(O / "wangcai" / "char.json", "w"), ensure_ascii=False, indent=1)
# 总览
pics = []
for n, arr, m in rows:
    im = Image.fromarray(arr); bg = Image.new("RGBA", im.size, (236, 226, 206, 255)); bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    for i in range(m["frames"]):
        ox, oy = m["origin"]; d.point((i * m["frame_w"] + ox, oy), fill=(255, 0, 0))
        if m.get("hand_point"):
            hx, hy = m["hand_point"]; d.rectangle([i * m["frame_w"] + ox + hx - 1, oy + hy - 1, i * m["frame_w"] + ox + hx + 1, oy + hy + 1], outline=(0, 0, 255))
        if m.get("mouth_point"):
            hx, hy = m["mouth_point"]; d.rectangle([i * m["frame_w"] + ox + hx - 1, oy + hy - 1, i * m["frame_w"] + ox + hx + 1, oy + hy + 1], outline=(0, 160, 0))
    pics.append((n, bg.resize((bg.width * 2, bg.height * 2), Image.NEAREST), m))
Wd = max(p.width for _, p, _ in pics) + 170; Ht = sum(p.height + 8 for _, p, _ in pics)
sheet = Image.new("RGB", (Wd, Ht), "white"); y = 0; d = ImageDraw.Draw(sheet)
for n, p, m in pics:
    sheet.paste(p, (170, y)); d.text((4, y + 4), n, fill=(180, 0, 0)); d.text((4, y + 18), f"{m['frames']}f {m['fps']}fps {'loop' if m.get('loop', True) else 'once'}", fill=(60, 60, 60)); y += p.height + 8
sheet.save(O / "actions_sheet.png"); print(sheet.size, len(pics))
