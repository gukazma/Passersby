"""把 gpt-image 出的"像素风"精灵表还原成真像素精灵表。

    python pixelize.py <sheet.png> <out_dir> [--rows 4 --cols 4 --colors 16 --cell 32x40]

步骤：按格切开 → 洋红背景抠透明 → 每格检测像素网格（周期+相位）→ 每个块取众数色降采样
→ 全表统一 K-means 调色板 → 去孤立像素 → 每帧按脚底基线 + 上半身质心对齐到固定画布。
输出：sheet.png（1 倍真像素）、sheet_x8.png（放大预览）、frames/rX_cY.png、palette.png、report.json。
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
from PIL import Image


def key_background(rgb: np.ndarray) -> np.ndarray:
    """洋红及其附近色（含模型画出来的偏色/过渡）当背景，返回前景 alpha 掩码。"""
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    magenta = (r > 150) & (b > 150) & (g < 110) & (np.abs(r - b) < 90)
    # 与四角采样的背景色接近的也算背景
    corners = np.concatenate([rgb[:6, :6].reshape(-1, 3), rgb[-6:, -6:].reshape(-1, 3),
                              rgb[:6, -6:].reshape(-1, 3), rgb[-6:, :6].reshape(-1, 3)]).astype(int)
    bg = np.median(corners, axis=0)
    near = np.sqrt(((rgb.astype(int) - bg) ** 2).sum(-1)) < 60
    return ~(magenta | near)


def edge_signals(rgb: np.ndarray, fg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    diff = np.abs(np.diff(rgb.astype(int), axis=1)).sum(-1)  # 水平相邻差
    diff = np.where(fg[:, 1:] | fg[:, :-1], diff, 0)
    sx = np.concatenate([[0], (diff > 40).sum(0)]).astype(float)
    diff = np.abs(np.diff(rgb.astype(int), axis=0)).sum(-1)
    diff = np.where(fg[1:] | fg[:-1], diff, 0)
    sy = np.concatenate([[0], (diff > 40).sum(1)]).astype(float)
    return sx, sy


def comb(signal: np.ndarray, p: float) -> tuple[float, float]:
    """突变最集中落在 phase + k*p 上时的 (得分, phase)；得分 = 网格线上平均突变 / 全局平均。"""
    n, best = len(signal), (0.0, 0.0)
    for ph in np.arange(0, p, 0.25):
        idx = np.round(np.arange(ph, n, p)).astype(int)
        idx = idx[idx < n]
        sc = signal[idx].mean() / (signal.mean() + 1e-9)
        if sc > best[0]:
            best = (sc, float(ph))
    return best


def global_period(signals: list[np.ndarray], lo: float = 5.0, hi: float = 14.0) -> float:
    """整张表共用一个像素尺寸：所有格子、两个方向的梳状得分相加。2p 的网格线是 p 的子集、得分相近 → 取接近最高分的最小周期。"""
    ps = np.arange(lo, hi + 1e-6, 0.05)
    sc = np.array([sum(comb(s, p)[0] for s in signals) for p in ps])
    pmin = ps[sc >= 0.9 * sc.max()].min()
    near = np.abs(ps - pmin) <= 0.75
    return float(ps[near][sc[near].argmax()])


def detect_grid(rgb: np.ndarray, fg: np.ndarray, P: float, span: float = 0.3) -> tuple[float, float, float]:
    """固定像素尺寸附近微调（span=0 则完全固定），只找每格自己的网格相位。"""
    sx, sy = edge_signals(rgb, fg)
    best = max(((comb(sx, p)[0] + comb(sy, p)[0], p) for p in np.arange(P - span, P + span + 0.001, 0.05)))
    p = best[1]
    return p, comb(sx, p)[1], comb(sy, p)[1]


def downsample(rgb: np.ndarray, fg: np.ndarray, p: float, phx: float, phy: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = fg.shape
    xs = np.arange(phx - p * np.ceil(phx / p), w, p)
    ys = np.arange(phy - p * np.ceil(phy / p), h, p)
    out = np.zeros((len(ys) - 1, len(xs) - 1, 3), np.uint8)
    alpha = np.zeros(out.shape[:2], bool)
    for j in range(len(ys) - 1):
        y0, y1 = int(round(ys[j] + p * 0.2)), int(round(ys[j + 1] - p * 0.2))  # 只取块中心，避开边缘过渡
        y0, y1 = max(y0, 0), min(max(y1, y0 + 1), h)
        for i in range(len(xs) - 1):
            x0, x1 = int(round(xs[i] + p * 0.2)), int(round(xs[i + 1] - p * 0.2))
            x0, x1 = max(x0, 0), min(max(x1, x0 + 1), w)
            if y0 >= h or x0 >= w:
                continue
            m = fg[y0:y1, x0:x1]
            if m.size == 0 or m.mean() < 0.5:
                continue
            px = rgb[y0:y1, x0:x1][m]
            q = (px // 8).astype(int)  # 粗量化后取众数，代表这个像素块的颜色
            keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]
            vals, cnt = np.unique(keys, return_counts=True)
            sel = px[keys == vals[cnt.argmax()]]
            out[j, i] = sel.mean(0).astype(np.uint8)
            alpha[j, i] = True
    return out, alpha


def bands(proj: np.ndarray, n: int) -> list[tuple[int, int]]:
    """按投影上的空白间隙切出 n 段（模型画的格子不均匀，不能等分）；切不出 n 段就退回等分。"""
    occ = proj > 2
    runs, i = [], 0
    while i < len(occ):
        if occ[i]:
            j = i
            while j < len(occ) and occ[j]:
                j += 1
            runs.append([i, j])
            i = j
        else:
            i += 1
    while len(runs) > n:  # 合并间隙最小的相邻两段（同一帧里被断开的部分，如脚和身体）
        g = [runs[k + 1][0] - runs[k][1] for k in range(len(runs) - 1)]
        k = int(np.argmin(g))
        runs[k] = [runs[k][0], runs[k + 1][1]]
        del runs[k + 1]
    if len(runs) != n:
        L = len(proj)
        return [(int(k * L / n), int((k + 1) * L / n)) for k in range(n)]
    out = []
    for k, (a0, a1) in enumerate(runs):  # 每段左右各留一点余量，取到间隙中点
        lo = 0 if k == 0 else (runs[k - 1][1] + a0) // 2
        hi = len(proj) if k == n - 1 else (a1 + runs[k + 1][0]) // 2
        out.append((lo, hi))
    return out


def kmeans(x: np.ndarray, k: int, iters: int = 30, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = x.astype(float)
    # k-means++ 初始化
    c = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min([((x - ci) ** 2).sum(1) for ci in c], axis=0)
        c.append(x[rng.choice(len(x), p=d / d.sum())])
    c = np.array(c)
    for _ in range(iters):
        lab = ((x[:, None] - c[None]) ** 2).sum(-1).argmin(1)
        for i in range(k):
            if (lab == i).any():
                c[i] = x[lab == i].mean(0)
    return np.round(c).astype(np.uint8)


def main_body(alpha: np.ndarray, keep: float = 0.04) -> np.ndarray:
    """只留主体：8 连通分量里比最大分量的 keep 倍还小的碎块去掉（邻格漏进来的边、杂点）。"""
    h, w = alpha.shape
    lab = np.zeros((h, w), int)
    sizes, n = [0], 0
    for y0 in range(h):
        for x0 in range(w):
            if alpha[y0, x0] and not lab[y0, x0]:
                n += 1
                stack, cnt = [(y0, x0)], 0
                lab[y0, x0] = n
                while stack:
                    y, x = stack.pop()
                    cnt += 1
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and alpha[yy, xx] and not lab[yy, xx]:
                                lab[yy, xx] = n
                                stack.append((yy, xx))
                sizes.append(cnt)
    if n == 0:
        return alpha
    sizes = np.array(sizes)
    ok = sizes >= keep * sizes.max()
    ok[0] = False
    return ok[lab]


def remove_orphans(alpha: np.ndarray) -> np.ndarray:
    a = alpha.copy()
    pad = np.pad(a, 1)
    nb = sum(np.roll(np.roll(pad, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)[1:-1, 1:-1]
    a[(a) & (nb <= 1)] = False
    return a


def keep_layout(a, out: pathlib.Path, cells: dict, offs: dict, pal: np.ndarray, report: dict) -> None:
    """每格降采样结果按它在原格子里的位置放进同一坐标系，取所有帧的并集包围盒裁成统一画布。"""
    M = 8
    big = {}
    for (r, c), (small, alpha) in cells.items():
        alpha = alpha.copy()
        if not getattr(a, "no_border_clear", False):
            alpha[:2], alpha[-2:], alpha[:, :2], alpha[:, -2:] = False, False, False, False  # 格子线残留（提示词要求内容不碰格边）
        alpha = main_body(remove_orphans(alpha), a.keep)
        lab = ((small[..., None, :].astype(int) - pal[None, None].astype(int)) ** 2).sum(-1).argmin(-1)
        h, w = alpha.shape
        oy, ox = offs[(r, c)]
        cv = np.zeros((h + 2 * M, w + 2 * M, 4), np.uint8)
        y0, x0 = M + oy, M + ox
        cv[y0:y0 + h, x0:x0 + w, :3] = pal[lab]
        cv[y0:y0 + h, x0:x0 + w, 3] = alpha * 255
        big[(r, c)] = cv
    H = max(v.shape[0] for v in big.values())
    W = max(v.shape[1] for v in big.values())
    for k, v in big.items():
        big[k] = np.pad(v, ((0, H - v.shape[0]), (0, W - v.shape[1]), (0, 0)))
    # 脚底对齐：角色在格子左侧，取最左不透明列往右 24 列（身体宽度）里最低的一行当脚底；特效可能比脚低，不算
    feet = {}
    for k, v in big.items():
        al = v[..., 3] > 0
        xl = np.nonzero(al.any(0))[0].min()
        feet[k] = np.nonzero(al[:, xl:xl + 24].any(1))[0].max()
    base = max(feet.values())
    for k in big:
        if a.anchor == "feet":
            big[k] = np.roll(big[k], base - feet[k], axis=0)
    report["feet_shift"] = {f"r{k[0]}c{k[1]}": int(base - feet[k]) if a.anchor == "feet" else 0 for k in big}
    occ = np.any([v[..., 3] > 0 for v in big.values()], axis=0)
    ys, xs = np.nonzero(occ)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    fw, fh = x1 - x0, y1 - y0
    order = sorted(big)
    sheet = Image.new("RGBA", (fw * len(order), fh), (0, 0, 0, 0))  # 横排一条
    for i, k in enumerate(order):
        fr = Image.fromarray(big[k][y0:y1, x0:x1])
        fr.save(out / "frames" / f"f{i}.png")
        sheet.alpha_composite(fr, (i * fw, 0))
        al = big[k][y0:y1, x0:x1, 3] > 0
        rows = np.nonzero(al.any(1))[0]
        report["cells"][f"r{k[0]}c{k[1]}"].update(bottom=int(rows.max()), left=int(np.nonzero(al.any(0))[0].min()))
    sheet.save(out / "sheet.png")
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save(out / "sheet_x8.png")
    report["frame_size"] = [int(fw), int(fh)]
    report["palette"] = ["#%02x%02x%02x" % tuple(x) for x in pal]
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("out")
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--colors", type=int, default=16)
    ap.add_argument("--cell", default="32x40", help="输出每帧画布 宽x高")
    ap.add_argument("--pixel", type=float, default=0, help="原图一个美术像素的边长；0 = 自动检测")
    ap.add_argument("--height", type=float, default=0, help="目标身高（像素）：按各格原图人物高度中位数反推像素尺寸，优先于 --pixel")
    ap.add_argument("--anchor", choices=["feet", "none"], default="feet", help="keep 布局下是否按脚底对齐（上下方向行走用 none）")
    ap.add_argument("--fixed", action="store_true", help="每格不再微调像素尺寸（行走帧身高必须一致）")
    ap.add_argument("--uniform", action="store_true", help="等分切格（模型按等分网格画的，如攻击表）")
    ap.add_argument("--layout", choices=["center", "keep"], default="center",
                    help="center = 按脚底+上半身重新居中（行走）；keep = 保留角色在格子里的原位置（攻击：特效在身体外，身体前冲也要保留）")
    ap.add_argument("--no-border-clear", action="store_true", help="不清格子四周 2 像素（按间隙切帧时用，避免脚尖被当格边清掉）")
    ap.add_argument("--keep", type=float, default=0.04, help="小于最大连通块该比例的碎块删掉；攻击特效（叶子、火星）要调小")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    cw, ch = map(int, a.cell.split("x"))

    rgba_img = np.array(Image.open(a.sheet).convert("RGBA"))
    img = rgba_img[..., :3]
    has_alpha = (rgba_img[..., 3] < 128).mean() > 0.05
    fg_all = (rgba_img[..., 3] >= 128) if has_alpha else key_background(img)  # 带透明通道的图只看 alpha
    ybands = bands(fg_all.sum(1), a.rows) if not a.uniform else \
        [(int(r * fg_all.shape[0] / a.rows), int((r + 1) * fg_all.shape[0] / a.rows)) for r in range(a.rows)]
    cells, boxes, offs, report = {}, {}, {}, {"cells": {}}
    for r, (ya, yb) in enumerate(ybands):
        xb = bands(fg_all[ya:yb].sum(0), a.cols) if not a.uniform else \
            [(int(c * fg_all.shape[1] / a.cols), int((c + 1) * fg_all.shape[1] / a.cols)) for c in range(a.cols)]
        for c, (xa, xe) in enumerate(xb):
            boxes[(r, c)] = (ya, yb, xa, xe)
    sigs = []
    for ya, yb, xa, xe in boxes.values():
        sigs += edge_signals(img[ya:yb, xa:xe], fg_all[ya:yb, xa:xe])
    if a.height > 0:
        hs = []
        for ya, yb, xa, xe in boxes.values():
            m = fg_all[ya:yb, xa:xe].copy()
            m[:12], m[-12:], m[:, :12], m[:, -12:] = False, False, False, False  # 去格子线
            rows = np.nonzero(m.sum(1) > 3)[0]
            if len(rows):
                hs.append(rows.max() - rows.min() + 1)
        a.pixel = float(np.median(hs)) / a.height
        report["source_height_px"] = float(np.median(hs))
    P = global_period(sigs) if a.pixel <= 0 else a.pixel
    report["global_pixel_size"] = round(P, 2)
    for (r, c), (ya, yb, xa, xe) in boxes.items():
        rgb, fg = img[ya:yb, xa:xe], fg_all[ya:yb, xa:xe]
        p, phx, phy = detect_grid(rgb, fg, P, 0.0 if a.fixed else 0.3)
        small, alpha = downsample(rgb, fg, p, phx, phy)
        cells[(r, c)] = (small, alpha)
        offs[(r, c)] = (int(round((phy - p * np.ceil(phy / p)) / p)), int(round((phx - p * np.ceil(phx / p)) / p)))
        report["cells"][f"r{r}c{c}"] = {"pixel_size": round(p, 2), "fg_pixels": int(alpha.sum())}

    allpx = np.concatenate([s[al] for s, al in cells.values()])
    pal = kmeans(allpx, a.colors)
    Image.fromarray(np.repeat(np.repeat(pal[None], 16, 0), 16, 1)).save(out / "palette.png")

    if a.layout == "keep":
        keep_layout(a, out, cells, offs, pal, report)
        return
    sheet = Image.new("RGBA", (cw * a.cols, ch * a.rows), (0, 0, 0, 0))
    for (r, c), (small, alpha) in cells.items():
        if a.uniform:  # 等分切格时格子线会残留在边上
            alpha = alpha.copy()
            alpha[:2], alpha[-2:], alpha[:, :2], alpha[:, -2:] = False, False, False, False
        alpha = main_body(remove_orphans(alpha), a.keep)
        lab = ((small[..., None, :].astype(int) - pal[None, None].astype(int)) ** 2).sum(-1).argmin(-1)
        rgba = np.zeros(small.shape[:2] + (4,), np.uint8)
        rgba[..., :3] = pal[lab]
        rgba[..., 3] = alpha * 255
        ys, xs = np.nonzero(alpha)
        if len(ys) == 0:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = rgba[y0:y1, x0:x1]
        top = alpha[y0:y1, x0:x1][: max(1, (y1 - y0) // 2)]  # 上半身（头+躯干）质心定水平位置，腿摆动不影响
        cx = np.nonzero(top)[1].mean()
        fr = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ox = int(round(cw / 2 - cx))
        oy = ch - 1 - (y1 - y0)  # 脚底贴到倒数第 1 行
        fr.alpha_composite(Image.fromarray(crop), (max(ox, 0), max(oy, 0)))
        fr.save(out / "frames" / f"r{r}_c{c}.png")
        sheet.alpha_composite(fr, (c * cw, r * ch))
        report["cells"][f"r{r}c{c}"].update(size=[int(x1 - x0), int(y1 - y0)], fits=bool(x1 - x0 <= cw and y1 - y0 < ch))
    sheet.save(out / "sheet.png")
    sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save(out / "sheet_x8.png")
    report["palette"] = ["#%02x%02x%02x" % tuple(x) for x in pal]
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report["cells"], ensure_ascii=False))


if __name__ == "__main__":
    main()
