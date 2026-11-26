"""城市素材还原的公共函数（从 process_city.py 抽出）。"""
import pathlib, subprocess, sys
import numpy as np
from PIL import Image
S = pathlib.Path.home() / ".claude/skills/pixel-sprite-anim/scripts"
PY = sys.executable
out = pathlib.Path("godot/assets")


def drop_thin(im):
    """去掉格子线残留：1-2 像素粗的细长连通块。"""
    a = np.array(im)
    al = a[..., 3] > 0
    h, w = al.shape
    seen = np.zeros_like(al)
    for y0 in range(h):
        for x0 in range(w):
            if al[y0, x0] and not seen[y0, x0]:
                st, comp = [(y0, x0)], []
                seen[y0, x0] = True
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and al[yy, xx] and not seen[yy, xx]:
                                seen[yy, xx] = True
                                st.append((yy, xx))
                ys = [c[0] for c in comp]
                xs = [c[1] for c in comp]
                bh, bw = max(ys) - min(ys) + 1, max(xs) - min(xs) + 1
                if (bh <= 2 and bw >= 5) or (bw <= 2 and bh >= 5):
                    for y, x in comp:
                        a[y, x, 3] = 0
    return Image.fromarray(a)


def bbox_crop(p):
    im = drop_thin(Image.open(p).convert("RGBA")); a = np.array(im)[..., 3] > 0
    ys, xs = np.nonzero(a); return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def src_bbox(img, box):
    a = np.array(Image.open(img).convert("RGBA"))[..., 3]
    a = a[box[1]:box[3], box[0]:box[2]] >= 128
    a[:12], a[-12:], a[:, :12], a[:, -12:] = False, False, False, False
    ys, xs = np.nonzero(a); return xs.max() - xs.min() + 1, ys.max() - ys.min() + 1


def pix(src, od, rows, cols, pixel, cell, colors=32, keep=0.01, extra=()):
    subprocess.run([PY, str(S / "pixelize.py"), src, od, "--rows", str(rows), "--cols", str(cols), "--uniform", "--fixed",
                    "--pixel", str(pixel), "--cell", cell, "--colors", str(colors), "--keep", str(keep), *extra], check=True, capture_output=True)
