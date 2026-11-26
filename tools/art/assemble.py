"""把各方向的 8 帧横排（已锁头）拼成总表，并生成 sprites.json 条目（含每个方向的最终根运动表）。

    python assemble.py <out_dir> --name hero_walk8 --down d.png --left l.png --right r.png --up u.png [--blend 0.5 --cycle 30 --anim-fps 12.5]
行顺序固定：down, left, right, up；每帧 32x40，脚底锚点 (16, 39)。正背面一律按原地踏步（均匀 cycle/8）。
"""
import argparse, json, pathlib, subprocess, sys
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--name", default="hero_walk8")
for d in ("down", "left", "right", "up"):
    ap.add_argument(f"--{d}", required=True)
ap.add_argument("--blend", type=float, default=0.5); ap.add_argument("--cycle", type=float, default=30.0)
ap.add_argument("--anim-fps", type=float, default=12.5)
a = ap.parse_args()
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
rows = ["down", "left", "right", "up"]
sheet = Image.new("RGBA", (256, 160))
rm, qc = {}, {}
for i, d in enumerate(rows):
    p = getattr(a, d)
    sheet.paste(Image.open(p).convert("RGBA"), (0, i * 40))
    args = [sys.executable, str(HERE / "rootmotion.py"), p, d, "--blend", str(a.blend), "--cycle", str(a.cycle), "--anim-fps", str(a.anim_fps)]
    if d in ("down", "up"):
        args.append("--inplace")
    r = json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)
    rm[d] = r["root_motion_px"]
    qc[d] = {"min_step_px": r["min_step_px"], "cv": r["cv"], "slip_mean_px": r["slip_mean_px"], "measured_px": r["measured_px"]}
sheet.save(out / f"{a.name}.png")
sheet.resize((256 * 8, 160 * 8), Image.NEAREST).save(out / f"{a.name}_x8.png")
entry = {"sheet": f"{a.name}.png", "frame": [32, 40], "anchor_feet": [16, 39], "rows": rows, "frames_per_row": 8,
         "anim_fps": a.anim_fps, "cycle_px": a.cycle, "speed_px_per_s": a.cycle * a.anim_fps / 8,
         "movement": "F：动画固定帧率播放，身体只在换帧时按 root_motion_px[dir][k]（帧 k→k+1）前进；朝向变化时从第 0 帧重新开始",
         "root_motion_px": rm, "qc": qc}
(out / f"{a.name}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(qc, ensure_ascii=False))
bad = [d for d in ("left", "right") if qc[d]["min_step_px"] < 2.3 or qc[d]["slip_mean_px"] > 0.5]
print("QC", "FAIL " + ",".join(bad) if bad else "PASS")
