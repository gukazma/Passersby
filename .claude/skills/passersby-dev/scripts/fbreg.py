"""正/背面行走条：按头顶对齐每帧（纵向），去掉小碎块。AI 把身体上下放得不一致时，脚底对齐会让人上下跳。

    python fbreg.py <strip_prefix> <out_prefix>
"""
import json, sys
import numpy as np
from PIL import Image

def small_blobs(mask, minsz=12):
    H, W = mask.shape; seen = np.zeros_like(mask); comps = []
    for sy, sx in zip(*np.nonzero(mask)):
        if seen[sy, sx]: continue
        st = [(sy, sx)]; seen[sy, sx] = True; pts = []
        while st:
            y, x = st.pop(); pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True; st.append((yy, xx))
        comps.append(pts)
    big = max(len(c) for c in comps) if comps else 0
    return [q for c in comps if len(c) < max(minsz, 0.08 * big) for q in c]
if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    m = json.load(open(src + ".json")); S = np.array(Image.open(src + ".png").convert("RGBA"))
    n, fw = m["frames"], m["frame_w"]; H = S.shape[0]; PAD = 60
    frs = []
    for i in range(n):
        f = S[:, i * fw:(i + 1) * fw].copy()
        for y, x in small_blobs(f[..., 3] > 0):
            f[y, x] = 0
        frs.append(f)
    tops = [np.nonzero((f[..., 3] > 0).any(1))[0].min() for f in frs]
    t0 = int(np.median(tops))
    out = []
    for f, t in zip(frs, tops):
        cv = np.zeros((H + 2 * PAD, fw, 4), np.uint8)
        dy = PAD + (t0 - t)
        cv[dy:dy + H] = f
        out.append(cv)
    O = np.concatenate(out, axis=1)
    al = O[..., 3] > 0; rows = np.nonzero(al.any(1))[0]; y0, y1 = rows.min(), rows.max() + 1
    O = O[y0:y1]
    Image.fromarray(O).save(dst + ".png")
    m2 = dict(m); m2["frame_h"] = int(O.shape[0]); m2["origin"] = [m["origin"][0], int(O.shape[0] - 1)]
    m2["registration"] = "head-top"; m2["head_shift_px"] = [int(t0 - t) for t in tops]
    json.dump(m2, open(dst + ".json", "w"), ensure_ascii=False, indent=1)
    print(dst, "shifts", m2["head_shift_px"])
