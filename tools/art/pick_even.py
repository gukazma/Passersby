"""从若干 8 帧行走候选里挑"间距最均匀"的一版。每个候选：还原真像素 → 横排 → 锁头 → 测根运动。

    python pick_even.py <right|left|down|up> <out_dir> <cand1.png> [cand2.png ...] [--height 37]
候选为 gpt-image 出的 4x2 网格图。输出：<out_dir>/<候选名>/strip_hl.png 和按 (离散系数, -最小步) 排序的评分表。
侧面行走选 cv 最小、min 最大的；正背面（原地踏步）测不出位移，主要看画面，加 --inplace 只做还原和锁头。
"""
import argparse, json, pathlib, subprocess, sys
import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("direction", choices=["right", "left", "down", "up"])
ap.add_argument("out")
ap.add_argument("cands", nargs="+")
ap.add_argument("--height", type=float, default=37)
ap.add_argument("--inplace", action="store_true")
a = ap.parse_args()
vertical = a.direction in ("down", "up")
res = []
for c in a.cands:
    od = pathlib.Path(a.out) / pathlib.Path(c).stem
    args = [sys.executable, str(HERE / "pixelize.py"), c, str(od), "--rows", "2", "--cols", "4", "--uniform", "--fixed",
            "--height", str(a.height), "--cell", "32x40"]
    if vertical:  # 正背面：保留原位置，不按脚底对齐（否则落地脚的上下位移被抹掉）
        args += ["--layout", "keep", "--anchor", "none", "--colors", "16", "--keep", "0.04"]
    subprocess.run(args, check=True, capture_output=True)
    strip = Image.new("RGBA", (256, 40))
    sh = Image.open(od / "sheet.png")
    if vertical:
        fw, fh = json.load(open(od / "report.json"))["frame_size"]
        for i in range(8):
            f = sh.crop((i * fw, 0, (i + 1) * fw, fh))
            strip.paste(f, (i * 32 + (32 - fw) // 2, 40 - fh), f)
    else:
        for i in range(8):
            strip.paste(sh.crop(((i % 4) * 32, (i // 4) * 40, (i % 4) * 32 + 32, (i // 4) * 40 + 40)), (i * 32, 0))
    strip.save(od / "strip.png")
    subprocess.run([sys.executable, str(HERE / "headlock.py"), str(od / "strip.png"), str(od / "strip_hl.png"), "--ref", "1"],
                   check=True, capture_output=True)
    rmargs = [sys.executable, str(HERE / "rootmotion.py"), str(od / "strip_hl.png"), a.direction] + (["--inplace"] if a.inplace else [])
    r = json.loads(subprocess.run(rmargs, capture_output=True, text=True, check=True).stdout)
    r.pop("feet")
    res.append(dict(cand=c, strip=str(od / "strip_hl.png"), measured_cv=r["measured_cv"], measured_min=min(r["measured_px"]),
                    measured=r["measured_px"], final=r["root_motion_px"], final_min=r["min_step_px"], slip=r["slip_mean_px"]))
for x in sorted(res, key=lambda x: (x["measured_cv"], -x["measured_min"])):
    print(json.dumps(x, ensure_ascii=False))
