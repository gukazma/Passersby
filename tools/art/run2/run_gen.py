"""跑步表生成：上身 = AI 跑步帧（锁头），裙摆与腿按相位程序画；落地脚精确跟随根运动。
用法: run_gen.py <N帧> <out_prefix> [--order-<dir>=01234567]"""
import sys, json, math
import numpy as np
from PIL import Image
sys.path.insert(0, '.')
from legs import C, H, W, rgba, draw_leg, outline

SRC = np.array(Image.open('/home/guleixin/pw/a11/sprites/out/hero_run.png').convert('RGBA'))
ROWS = ['down', 'left', 'right', 'up']
CYCLE = 48.0                    # 一个循环前进 48 像素（两步，每步 24）
STANCE = 0.25                   # 每只脚着地占循环的 1/4（0→0.25 从 +6 移到 −6）；另外各 1/4 是腾空
HIP_Y = 28.0
GA = 34                         # 着地时脚踝行：鞋底填到 37，描边在 38
# 侧面：空中轨迹关键帧 (t, dx, ankle_y, 靴子)
SIDE_AIR = [(0.25, -6, GA, 'flat'), (0.375, -9, 32, 'lift'), (0.5, -6, 30, 'lift'), (0.625, -1, 30, 'lift'),
            (0.75, 4, 31, 'lift'), (0.875, 7, 33, 'flat'), (1.0, 6, GA, 'flat')]
# 正面（朝下跑）：着地脚被身体"跨过"，在画面里往上移（+6 → 0 → −6 对应行 GA → GA−6 → GA−12，后两者被裙子挡住）
DOWN_AIR = [(0.25, 0, GA - 12, 'lift'), (0.375, 0, GA - 8, 'lift'), (0.5, 0, GA - 5, 'lift'), (0.625, 0, GA - 4, 'lift'),
            (0.75, 0, GA - 3, 'lift'), (0.875, 0, GA - 1, 'flat'), (1.0, 0, GA, 'flat')]
# 背面（朝上跑）：落脚点在身体前方（画面上方、被挡住），蹬地时到正下方，然后脚后跟往镜头这边踢起
UP_AIR = [(0.25, 0, GA, 'flat'), (0.375, 0, GA - 3, 'lift'), (0.5, 0, GA - 4, 'lift'), (0.625, 0, GA - 7, 'lift'),
          (0.75, 0, GA - 9, 'lift'), (1.0, 0, GA - 12, 'flat')]
# 正背面：腿在身体"前面"（离镜头近）的相位区间 → 画在裙摆上层
FRONT = {'down': (0.5, 1.0), 'up': (0.25, 0.56)}


def lerp_keys(keys, t):
    for (t0, x0, y0, k0), (t1, x1, y1, k1) in zip(keys, keys[1:]):
        if t0 <= t <= t1 + 1e-9:
            u = (t - t0) / (t1 - t0)
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, (k0 if u < 0.5 else k1)
    return keys[-1][1:]


def foot(direction, t):
    """一只脚在相位 t（0 = 落地瞬间）的 (dx, ankle_y, 靴子, 着地?)"""
    t %= 1.0
    if direction in ('right', 'left'):
        if t <= STANCE + 1e-9:
            return 6 - 12 * t / STANCE, GA, 'flat', True
        x, y, k = lerp_keys(SIDE_AIR, t)
        return x, min(y, GA - 1) if t < 0.999 else y, k, False
    if direction == 'down':
        if t <= STANCE + 1e-9:
            return 0, GA - 12 * t / STANCE, 'flat', True
        x, y, k = lerp_keys(DOWN_AIR, t)
        return x, min(y, GA - 1), k, False
    # up
    if t <= STANCE + 1e-9:
        return 0, GA - 12 + 12 * t / STANCE, 'flat', True
    x, y, k = lerp_keys(UP_AIR, t)
    return x, min(y, GA - 1) if t > 0.26 else y, k, False


def torso_cx(fr):
    ol = (np.abs(fr[21:26, :, :3].astype(int) - C['olive']).sum(-1) < 30) & (fr[21:26, :, 3] > 0)
    xs = np.nonzero(ol.any(0))[0]
    return int(round((xs.min() + xs.max()) / 2)) if len(xs) else 16


def skirt(img, cx, face, sway):
    if face == 0:
        rows = {26: (-5, 5), 27: (-6, 6), 28: (-6, 6), 29: (-7, 7)}
    else:
        rows = {26: (-4, 4), 27: (-5, 5), 28: (-6, 5), 29: (-6 - sway, 6)}
    m = np.zeros((H, W), bool)
    for y, (a, b) in rows.items():
        xa, xb = (cx + a, cx + b) if face >= 0 else (cx - b, cx - a)
        m[y, max(0, xa):min(W, xb + 1)] = True
    img[m] = rgba(C['olive'])
    for y, (a, b) in rows.items():
        xa, xb = (cx + a, cx + b) if face >= 0 else (cx - b, cx - a)
        if face != 0:
            img[y, xa if face > 0 else xb] = rgba(C['olive_dk'])
    img[29][m[29]] = rgba(C['cream'])
    outline(img, m, C['out'])


def upper(fr):
    u = fr.copy()
    u[26:] = 0                         # 26 行以下全换成程序画的裙摆和腿（AI 的腿姿不连贯）
    return u


def make_frame(direction, t, src, cx):
    face = {'right': 1, 'left': -1, 'down': 0, 'up': 0}[direction]
    img = np.zeros((H, W, 4), np.uint8)
    hip = (cx + .5, HIP_Y)
    A = foot(direction, t)
    B = foot(direction, t + 0.5)
    legs = []
    if face != 0:
        # 侧面：远侧腿 B 先画，近侧腿 A 后画
        for f, near in ((B, False), (A, True)):
            ank = (cx + f[0] * face, f[1])
            legs.append(draw_leg(img, hip, ank, face, near, f[2]))
    front = []
    if face == 0:
        # 正背面：左右两条腿；离镜头近（向前摆腿 / 往后踢）的那条画在裙摆上面
        lo, hi = FRONT[direction]
        for x, f, tt in ((cx - 2.5, A, t % 1.0), (cx + 3.5, B, (t + 0.5) % 1.0)):
            (front if lo <= tt < hi else legs).append((x, f))
        legs.sort(key=lambda p: p[1][1])
        for x, f in legs:
            draw_leg(img, (x, HIP_Y), (x, f[1]), 0, True, f[2])
    sk = np.zeros((H, W, 4), np.uint8)
    skirt(sk, cx, face, 1 if (t % 0.5) > 0.25 else 0)
    al = sk[..., 3] > 0; img[al] = sk[al]
    for x, f in front:
        lay = np.zeros((H, W, 4), np.uint8)
        draw_leg(lay, (x, HIP_Y + 1), (x, f[1]), 0, True, f[2])
        lay[:27] = 0                    # 只露出裙摆以下（膝盖把裙摆顶起）
        al = lay[..., 3] > 0; img[al] = lay[al]
    u = upper(src); al = u[..., 3] > 0; img[al] = u[al]
    return img, A, B


def build(n, order):
    sheet = np.zeros((H * 4, W * n, 4), np.uint8)
    info = {}
    for r, d in enumerate(ROWS):
        src_row = SRC[40 * r:40 * r + 40]
        info[d] = []
        cx = int(np.median([torso_cx(src_row[:, 32 * j:32 * j + 32]) for j in range(8)]))   # 髋部固定（逐帧取会抖 ±1 像素）
        for k in range(n):
            t = k / n
            sk = order[d][int(k * 8 / n)]
            fr, A, B = make_frame(d, t, src_row[:, 32 * sk:32 * sk + 32], cx)
            sheet[40 * r:40 * r + 40, 32 * k:32 * k + 32] = fr
            info[d].append((A, B))
    return sheet, info


if __name__ == '__main__':
    n = int(sys.argv[1]); out = sys.argv[2]
    order = {d: list(range(8)) for d in ROWS}
    for a in sys.argv[3:]:
        if a.startswith('--order-'):
            d, v = a[8:].split('=')
            order[d] = [int(c) for c in v]
    sheet, info = build(n, order)
    Image.fromarray(sheet).save(out + '.png')
    json.dump({d: [[list(map(lambda v: v if isinstance(v, (str, bool)) else round(float(v), 2), f)) for f in fr] for fr in info[d]] for d in info},
              open(out + '_pose.json', 'w'))
