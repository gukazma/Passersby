"""高清街区批处理：像素尺寸按 新宽 = 旧原生宽 × R 反推；底线/后巷按实际比例从旧值换算。"""
import json, subprocess, sys
import numpy as np
from PIL import Image
R = 2.68
OLD = {  # 旧原生宽、底线、后巷（原生像素）
    "cbd_a": (230, 145, None), "cbd_b": (253, 159, None), "cbd_c": (238, 148, None),
    "shop_a": (250, 163, (73, 79)), "food": (251, 164, (73, 79)), "plaza": (264, 171, (65, 115)),
    "shop_b": (268, 172, (77, 84)), "apt_b": (278, 182, (82, 88)), "apt_a": (292, 188, (84, 90))}
names = sys.argv[1:] or list(OLD)
for n in names:
    ow, ob, oa = OLD[n]
    src = f"raw_hr/hr4k_{n}.png"
    a = np.array(Image.open(src).convert("RGBA")); r, g, b = (a[..., i].astype(int) for i in range(3))
    fg = (a[..., 3] >= 128) & ~((r > 150) & (b > 150) & (g < 110))
    xs = np.nonzero(fg.mean(0) > 0.2)[0]
    p = (xs.max() - xs.min() + 1) / (ow * R)
    def run(extra):
        out = subprocess.run([sys.executable, "process_blocks.py", src, n, "--k", "1", "--pixel", f"{p:.3f}"] + extra, capture_output=True, text=True, check=True).stdout
        return json.load(open(f"godot/assets/blocks/{n}.json"))
    m = run(["--single"] if oa is None else [])
    rr = m["w"] / ow
    extra = ["--base", str(round(ob * rr + (m["h"] - round(ob * rr)) * 0) )]
    if oa is None:
        extra.append("--single")
    else:
        extra += ["--alley", f"{round(oa[0] * rr)},{round(oa[1] * rr)}"]
    m = run(extra)
    print(n, f"p={p:.2f} r={rr:.2f}", m)
