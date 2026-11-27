"""程序画地面（与 A 画风同色系，平涂、无噪点）：人行道纵深带 392..468、路缘 468..476、马路 476..540。
按整条街宽度一次画完（确定性随机），没有接缝。另出斑马线、小巷片。

    python ground.py <out_dir> <id> <width> [--kind oldtown|promenade]
"""
import argparse, json, random
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("id"); ap.add_argument("width", type=int)
ap.add_argument("--kind", default="oldtown"); a = ap.parse_args()
W, H = a.width, 540
Y0, Y1, Y2 = 392, 468, 476
rnd = random.Random(sum(map(ord, a.id)))
im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
if a.kind == "oldtown":
    tones = [(196, 182, 158), (188, 173, 149), (204, 191, 168)]; mortar = (150, 134, 114); hi = (214, 203, 182)
    sw, rows = 38, [19, 19, 19, 19]
else:
    tones = [(214, 202, 178), (206, 193, 168), (220, 210, 188)]; mortar = (164, 149, 126); hi = (230, 221, 202)
    sw, rows = 52, [25, 25, 26]
y = Y0
for ri, rh in enumerate(rows):
    off = (sw // 2) * (ri % 2)
    x = -off
    while x < W:
        c = rnd.choice(tones)
        d.rectangle([x, y, x + sw - 1, y + rh - 1], fill=c)
        d.line([(x, y), (x + sw - 1, y)], fill=hi)                      # 上沿高光
        d.line([(x + sw - 1, y), (x + sw - 1, y + rh - 1)], fill=mortar)  # 右缝
        d.line([(x, y + rh - 1), (x + sw - 1, y + rh - 1)], fill=mortar)  # 下缝
        if rnd.random() < 0.06:  # 裂纹
            cx = x + rnd.randint(6, sw - 10); cy = y + rnd.randint(4, rh - 6)
            d.line([(cx, cy), (cx + 3, cy + 2), (cx + 6, cy + 2)], fill=mortar)
        if rnd.random() < 0.04:  # 旧水渍（一块平涂深色）
            cx = x + rnd.randint(4, sw - 14); cy = y + rnd.randint(3, rh - 7)
            d.rectangle([cx, cy, cx + 8, cy + 3], fill=tuple(v - 10 for v in c))
        x += sw
    y += rh
d.line([(0, Y0), (W, Y0)], fill=(120, 104, 88)); d.line([(0, Y0 + 1), (W, Y0 + 1)], fill=(160, 144, 124))  # 楼脚阴影
# 路缘石
d.rectangle([0, Y1, W, Y1 + 2], fill=(222, 214, 200)); d.rectangle([0, Y1 + 3, W, Y2 - 1], fill=(150, 142, 132))
for x in range(rnd.randint(0, 60), W, 64):
    d.line([(x, Y1), (x, Y2 - 1)], fill=(120, 112, 104))
# 马路
d.rectangle([0, Y2, W, H], fill=(92, 87, 84))
d.rectangle([0, Y2, W, Y2 + 3], fill=(70, 66, 64))                              # 边沟
for x in range(rnd.randint(100, 300), W, rnd.randint(280, 340)):               # 雨水篦子
    d.rectangle([x, Y2 + 1, x + 22, Y2 + 5], fill=(50, 47, 46))
    for k in range(x + 2, x + 21, 3): d.line([(k, Y2 + 2), (k, Y2 + 4)], fill=(80, 76, 72))
for _ in range(W // 160):                                                    # 补丁（平涂色块）
    x = rnd.randint(0, W); w = rnd.randint(30, 90); yy = rnd.randint(Y2 + 8, H - 10)
    d.rectangle([x, yy, x + w, yy + rnd.randint(4, 8)], fill=(86, 81, 78))
for x in range(0, W, 80):                                                    # 中线虚线
    d.rectangle([x + 10, 509, x + 50, 511], fill=(214, 206, 186))
im.save(f"{a.out}/ground_{a.id}.png")
# 斑马线（叠在马路上，宽 96）
z = Image.new("RGBA", (96, H - Y2), (0, 0, 0, 0)); zd = ImageDraw.Draw(z)
for yy in range(6, H - Y2 - 2, 9):
    zd.rectangle([0, yy, 95, yy + 4], fill=(226, 220, 206)); zd.line([(0, yy + 4), (95, yy + 4)], fill=(196, 190, 176))
for _ in range(14):
    x = rnd.randint(0, 92); yy = rnd.randint(0, H - Y2 - 3); zd.rectangle([x, yy, x + 3, yy + 1], fill=(0, 0, 0, 0))
z.save(f"{a.out}/zebra.png")
# 小巷片（两栋楼之间的窄巷，宽 44，高 420，底边对齐 392）
al = Image.new("RGBA", (44, 420), (0, 0, 0, 0)); ad = ImageDraw.Draw(al)
ad.rectangle([0, 0, 43, 419], fill=(58, 46, 40))
ad.polygon([(0, 0), (8, 0), (8, 405), (0, 419)], fill=(74, 60, 50)); ad.polygon([(43, 0), (35, 0), (35, 405), (43, 419)], fill=(48, 38, 33))
ad.rectangle([8, 405, 35, 419], fill=(96, 84, 72))                            # 巷口地面
ad.rectangle([14, 150, 29, 172], fill=(140, 110, 60)); ad.rectangle([16, 152, 27, 170], fill=(200, 160, 80))   # 一扇亮着的远窗
ad.line([(10, 90), (33, 96)], fill=(30, 24, 20))                               # 晾衣绳
for x, c in ((13, (190, 70, 60)), (20, (220, 210, 190)), (27, (90, 120, 100))):
    ad.rectangle([x, 92, x + 4, 100], fill=c)
ad.line([(31, 0), (31, 404)], fill=(40, 32, 28)); ad.line([(32, 0), (32, 404)], fill=(90, 80, 70))  # 水管
al.save(f"{a.out}/alley.png")
print("ground", a.id, W)
