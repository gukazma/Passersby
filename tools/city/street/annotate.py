"""永安街样张标注：楼界、招牌空板（自动精修到单色板的实际范围）、门、屋顶高度 → out/<row>.json + 预览。"""
import json
import numpy as np
from PIL import Image, ImageDraw

ROWS = {
 "yongan_N": {
  "buildings": [("L01", "陈记云吞面", 0, 84, 3), ("L02", "福安堂凉茶", 84, 145, 2), ("L03", "钟记钟表行", 145, 210, 3),
                ("L04", "永和五金", 210, 284, 3), ("L05", "何家唐楼", 284, 383, 7), ("L06", "永安茶楼", 383, 511, 4)],
  "signs": [("陈记云吞面", 17, 237, 56, 16), ("福安堂凉茶", 93, 237, 45, 16), ("钟记钟表行", 158, 237, 41, 16),
            ("永和五金", 221, 237, 53, 16), ("何记烧腊", 301, 237, 66, 16), ("永安茶楼", 413, 237, 58, 14, "fix")],
  "doors": [("L01-1", 15, 258, 59, 63), ("L02-1", 92, 258, 48, 63), ("L03-1", 157, 258, 46, 63),
            ("L04-1", 218, 258, 62, 63), ("L05-1", 296, 258, 81, 63), ("L06-1", 394, 258, 100, 63)],
 },
 "yongan_S": {
  "buildings": [("L07", "新华理发", 0, 73, 2), ("L08", "永安街坊会", 73, 156, 2), ("L09", "天后庙", 156, 233, 1),
                ("L10", "永安街市", 233, 364, 2), ("L11", "拾光书店", 364, 417, 2), ("L12", "永安小学", 417, 508, 3)],
  "signs": [("新华理发", 12, 169, 55, 14), ("永安街坊会", 87, 169, 58, 14), ("天后古庙", 179, 156, 49, 9, "fix"),
            ("永安街市", 257, 169, 81, 14), ("拾光书店", 369, 169, 42, 14), ("永安小学", 437, 169, 50, 12, "fix")],
  "doors": [("L07-1", 48, 198, 16, 44), ("L08-1", 87, 195, 23, 47), ("L09-1", 162, 180, 63, 62),
            ("L10-1", 238, 187, 119, 56), ("L11-1", 395, 198, 15, 44), ("L12-1", 442, 195, 38, 48)],
 },
}


def refine(A, x, y, w, h):
    """在大致范围内找面积最大的单色块（招牌空板），返回其包围盒和颜色。"""
    sub = A[y - 3:y + h + 3, x - 3:x + w + 3, :3].astype(int)
    q = sub // 8
    keys, cnt = np.unique(q.reshape(-1, 3), axis=0, return_counts=True)
    c = keys[cnt.argmax()] * 8 + 4
    m = np.abs(sub - c).sum(-1) < 40
    rows = np.nonzero(m.mean(1) > 0.5)[0]; cols = np.nonzero(m.mean(0) > 0.5)[0]
    col = np.median(sub[m], axis=0).astype(int)
    return [x - 3 + int(cols.min()), y - 3 + int(rows.min()), int(cols.max() - cols.min() + 1), int(rows.max() - rows.min() + 1)], col


for name, R in ROWS.items():
    img = Image.open(f"out/{name}.png").convert("RGBA")
    A = np.array(img)
    h, w = A.shape[:2]
    al = A[..., 3] > 0
    cov = al.mean(1)
    base = int(np.nonzero(cov > 0.6)[0].max()) + 1
    out = {"w": w, "h": h, "base": base, "buildings": [], "doors": [], "signs": [],
           "note": "RGBA true pixels, alpha 0/255. Facades face south (camera). depth = visible roof strip (suggested collision footprint from base upward is a gameplay choice, see report)."}
    for bid, nm, x0, x1, fl in R["buildings"]:
        colcov = al[:, x0:x1].mean(1)
        solid = int(np.nonzero(colcov > 0.5)[0].min())       # 主体（不算天线、旗杆、单个水箱）
        anyp = int(np.nonzero(colcov > 0.0)[0].min())          # 最高点（含天线、旗杆）
        out["buildings"].append({"id": bid, "name": nm, "x0": x0, "x1": x1, "floors": fl, "roof_top_y": anyp, "solid_top_y": solid,
                                 "height_px": base - solid, "depth": 24})
    for did, x, y, dw, dh in R["doors"]:
        out["doors"].append({"id": did, "x": x, "y": y, "w": dw, "h": dh, "enter_xy": [x + dw // 2, base]})
    for text, x, y, sw, sh, *fix in R["signs"]:
        if fix:
            rect = [x, y, sw, sh]
            sub = A[y + 1:y + sh - 1, x + 2:x + sw - 2, :3].reshape(-1, 3).astype(int)
            col = np.median(sub, axis=0).astype(int)
        else:
            rect, col = refine(A, x, y, sw, sh)
        lum = 0.3 * col[0] + 0.59 * col[1] + 0.11 * col[2]
        fg = [252, 236, 196] if lum < 120 else [74, 40, 18]
        if text == "天后古庙":
            fg = [246, 208, 96]
        out["signs"].append({"text": text, "x": rect[0], "y": rect[1], "w": rect[2], "h": rect[3], "bg": [int(v) for v in col], "fg": fg})
    json.dump(out, open(f"out/{name}.json", "w"), ensure_ascii=False, indent=1)
    # 标注检查图
    K = 3
    big = Image.new("RGBA", (w * K, h * K), (214, 204, 184, 255)); big.alpha_composite(img.resize((w * K, h * K), Image.NEAREST))
    d = ImageDraw.Draw(big)
    for b in out["buildings"]:
        d.line((b["x0"] * K, 0, b["x0"] * K, h * K), fill=(0, 160, 255)); d.line((b["x0"] * K, b["solid_top_y"] * K, b["x1"] * K, b["solid_top_y"] * K), fill=(0, 160, 255), width=2)
    for s in out["signs"]:
        d.rectangle((s["x"] * K, s["y"] * K, (s["x"] + s["w"]) * K - 1, (s["y"] + s["h"]) * K - 1), outline=(255, 0, 255), width=2)
    for o in out["doors"]:
        d.rectangle((o["x"] * K, o["y"] * K, (o["x"] + o["w"]) * K - 1, (o["y"] + o["h"]) * K - 1), outline=(0, 255, 0), width=2)
    d.line((0, base * K, w * K, base * K), fill=(255, 0, 0), width=2)
    big.save(f"work/{name}_ann.png")
    print(name, w, h, base, [(b["id"], b["floors"], b["height_px"]) for b in out["buildings"]])
    print("  signs", [(s["text"], s["x"], s["y"], s["w"], s["h"]) for s in out["signs"]])
