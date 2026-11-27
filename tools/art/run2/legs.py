"""跑步腿部程序绘制：上身（头、躯干、手臂、背篓）用 AI 跑步帧（已锁头），裙摆和两条腿按步幅表画。
落地脚每帧后移量 = 根运动（像素级精确），保证不打滑。"""
import math
import numpy as np
from PIL import Image

C = dict(out=(61, 21, 10), out2=(49, 17, 7), skin=(248, 189, 134), skin_sh=(215, 131, 82), skin_dk=(191, 106, 59),
         boot=(135, 67, 46), boot_hi=(153, 76, 48), boot_dk=(100, 43, 28), cream=(249, 219, 169),
         olive=(130, 117, 43), olive_dk=(78, 95, 30), olive_hi=(136, 146, 50))
W, H = 32, 40


def rgba(c, a=255):
    return np.array(list(c) + [a], np.uint8)


def disk_line(mask, p0, p1, r):
    """粗线（胶囊）光栅化"""
    (x0, y0), (x1, y1) = p0, p1
    n = int(max(abs(x1 - x0), abs(y1 - y0)) * 3) + 1
    for i in range(n + 1):
        t = i / n
        cx, cy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for yy in range(int(cy - r - 1), int(cy + r + 2)):
            for xx in range(int(cx - r - 1), int(cx + r + 2)):
                if 0 <= xx < W and 0 <= yy < H and (xx + .5 - cx - .5) ** 2 + (yy + .5 - cy - .5) ** 2 <= r * r:
                    mask[yy, xx] = True


def ik(hip, ank, a, b, bend):
    """两段腿：膝盖朝 bend（+1 = 朝 +x）"""
    hx, hy = hip; fx, fy = ank
    dx, dy = fx - hx, fy - hy
    d = max(1e-6, math.hypot(dx, dy)); d2 = min(d, a + b - 1e-3)
    ang = math.atan2(dy, dx)
    cosA = (a * a + d2 * d2 - b * b) / (2 * a * d2)
    A = math.acos(max(-1, min(1, cosA)))
    k = ang - bend * A          # y 向下：减角 = 膝盖朝 +x（对朝右的腿）
    return (hx + a * math.cos(k), hy + a * math.sin(k))


def outline(img, mask, col):
    p = np.pad(mask, 1)
    nb = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    ring = nb & ~mask
    img[ring] = rgba(col)
    return ring


def boot_mask(ank, face, kind):
    """靴子：ank = 脚踝像素；face = +1 朝右 / -1 朝左 / 0 正面；kind: flat（平踩）/ lift（离地，脚尖略下垂）"""
    m = np.zeros((H, W), bool)
    ax, ay = int(round(ank[0])), int(round(ank[1]))
    if face == 0:
        rows = [(-1, 1), (-1, 1), (-1, 2), (-2, 2)] if kind == "flat" else [(-1, 1), (-1, 1), (-1, 2), (-1, 1)]
        for i, (a, b) in enumerate(rows):
            for x in range(ax + a, ax + b + 1):
                if 0 <= x < W and 0 <= ay + i < H:
                    m[ay + i, x] = True
        return m
    shape = [(-1, 1), (-1, 1), (-1, 2), (-1, 3)] if kind == "flat" else [(-1, 1), (-1, 2), (-1, 2), (0, 3)]
    for i, (a, b) in enumerate(shape):
        for x in range(a, b + 1):
            xx = ax + x * face
            if 0 <= xx < W and 0 <= ay + i < H:
                m[ay + i, xx] = True
    return m


def draw_leg(img, hip, ank, face, near, kind, a=5.0, b=5.2, r=1.25, hide_rows=None):
    """一条腿 + 靴子画到 img（RGBA）；返回靴子掩码"""
    bend = 1 if face >= 0 else -1
    if face == 0:
        knee = (hip[0] + (ank[0] - hip[0]) * .5, hip[1] + (ank[1] - hip[1]) * .5)
    else:
        knee = ik(hip, ank, a, b, bend)
    m = np.zeros((H, W), bool)
    disk_line(m, hip, knee, r)
    disk_line(m, knee, (ank[0], ank[1] - .5), r)
    bm = boot_mask(ank, face, kind)
    sk = C["skin"] if near else C["skin_sh"]
    img[m & ~bm] = rgba(sk)
    if face != 0:   # 腿的后侧一列阴影
        for y in range(H):
            xs = np.nonzero(m[y] & ~bm[y])[0]
            if len(xs) >= 3:
                img[y, xs[0] if face > 0 else xs[-1]] = rgba(C["skin_sh"] if near else C["skin_dk"])
    img[bm] = rgba(C["boot"] if near else C["boot_dk"])
    ys = np.nonzero(bm.any(1))[0]
    if len(ys):    # 鞋底一行深色、鞋帮一行亮色
        img[ys[-1]][bm[ys[-1]]] = rgba(C["boot_dk"] if near else C["out2"])
        if near:
            top = bm[ys[0]]
            img[ys[0]][top] = rgba(C["boot_hi"])
    outline(img, m | bm, C["out"])
    return bm
