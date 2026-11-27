"""把各动作的精灵条 + json 装成 char.json（游戏读取格式）。
    python make_char.py <out_dir> <id> <name> anim=prefix[:fps] ...
prefix = walkbuild 输出前缀（有 .png/.json）。没有站立帧时用 idle_x=prefix@帧号 从行走条取一帧临时代替。"""
import json, shutil, sys, pathlib
from PIL import Image
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
cid, name = sys.argv[2], sys.argv[3]
anims = {}
for arg in sys.argv[4:]:
    k, v = arg.split("=", 1)
    if "@" in v:
        src, f = v.split("@"); f = int(f)
        m = json.load(open(src + ".json")); im = Image.open(src + ".png")
        fw = m["frame_w"]; im.crop((f * fw, 0, (f + 1) * fw, m["frame_h"])).save(out / f"{k}.png")
        anims[k] = {"file": f"{k}.png", "frames": 1, "fps": 1, "frame_w": fw, "frame_h": m["frame_h"], "origin": m["origin"]}
        continue
    fps = None
    if ":" in v:
        v, fps = v.split(":"); fps = float(fps)
    m = json.load(open(v + ".json"))
    shutil.copy(v + ".png", out / f"{k}.png")
    anims[k] = {"file": f"{k}.png", "frames": m["frames"], "fps": fps or m["fps"], "frame_w": m["frame_w"], "frame_h": m["frame_h"],
                "origin": m["origin"], "root_motion_px": m.get("root_motion_px", []), "axis": m.get("axis", "x")}
    if m.get("dir_screen"):
        anims[k]["dir_screen"] = m["dir_screen"]
    if "slip_mean_px" in m:
        anims[k]["qc"] = {"slip_mean_px": m["slip_mean_px"], "speed_px_s": round(sum(m["root_motion_px"]) / m["frames"] * (fps or m["fps"]), 1)}
json.dump({"id": cid, "name": name, "height_px": 110, "anims": anims}, open(out / "char.json", "w"), ensure_ascii=False, indent=1)
print({k: a.get("qc") for k, a in anims.items()})
