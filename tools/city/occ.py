"""后巷南侧楼顶凸起（楼梯间、水箱、女儿墙…）的逐列遮挡/碰撞。

街区图里后巷带 [a0, a1)：地面是铺装；南排楼的楼顶东西会从 a1 往上伸进这条带。
逐列从 a1 往上找"连着南排楼、不是地面"的像素 → top[x]；
这些像素画在南排楼的 y 排序层（主角在后巷时被它们挡住），碰撞也跟着这条轮廓走。
"""
import numpy as np


def floor_mask(a, a0, a1):
    """True = 和这一行的典型颜色一样（地面、墙脚阴影、女儿墙压线这些整行都有的东西）"""
    band = a[a0:a1, :, :3].astype(int)
    med = np.median(band, axis=1, keepdims=True)
    return np.abs(band - med).sum(-1) < 54


def south_top(a, a0, a1, min_run=4):
    fm = floor_mask(a, a0, a1)
    h, w = fm.shape
    top = np.full(w, a1)
    for x in range(w):
        r = h
        while r > 0 and not fm[r - 1, x]:
            r -= 1
        top[x] = a0 + r
    full = top <= a0 + 1                # 整列都不是地面：多半是北墙脚的杂物连到了一起，不算
    top[full] = a1
    dep = a1 - top
    dm = np.array([np.median(dep[max(0, x - 2):x + 3]) for x in range(w)])   # 去掉单列毛刺
    dep = np.where(np.abs(dep - dm) > 2, dm, dep).astype(int)
    dep[dep < 3] = 0                    # 太浅的（女儿墙压线）不算
    x = 0                               # 去掉太窄的
    while x < w:
        if dep[x] > 0:
            e = x
            while e < w and dep[e] > 0:
                e += 1
            if e - x < min_run:
                dep[x:e] = 0
            x = e
        else:
            x += 1
    return a1 - dep


def runs(top, a1, q=2):
    """连续列合并成碰撞矩形：[[x0, y_top, w], ...]（深度按 q 像素取整）"""
    out, x, w = [], 0, len(top)
    while x < w:
        if top[x] < a1:
            t = top[x]
            e = x
            while e < w and top[e] < a1 and abs(int(top[e]) - int(t)) <= q:
                t = min(t, top[e]); e += 1
            out.append([x, int(t), e - x])
            x = e
        else:
            x += 1
    return out
