"""从像素实测落地脚位移（不看姿势表）：靴子色块 → 连通块 → 着地判定 → 帧间同一只脚配对。
侧面：着地 = 鞋底在第 37 行（填充最低行）；位置 = 该行靴子像素 x 均值。
正背面：位置 = 靴子最低行（脚在画面里上下移动）；着地 = 姿势表里标为着地（被裙子挡住的看不到就不计）。"""
import sys, json
import numpy as np
from PIL import Image
sys.path.insert(0, '.')
from legs import C

BOOT = [C['boot'], C['boot_dk'], C['boot_hi'], C['out2']]
ROWS = ['down', 'left', 'right', 'up']
GROUND = 37


def label(m):
    lab = np.zeros(m.shape, int); n = 0
    for y, x in zip(*np.nonzero(m)):
        if lab[y, x]:
            continue
        n += 1; st = [(y, x)]; lab[y, x] = n
        while st:
            cy, cx = st.pop()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = cy + dy, cx + dx
                if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; st.append((yy, xx))
    return lab, n


def boots(fr):
    rgb = fr[..., :3].astype(int); al = fr[..., 3] > 0
    m = np.zeros(al.shape, bool)
    for c in BOOT:
        m |= (np.abs(rgb - c).sum(-1) == 0) & al
    m[:26] = False          # 只看腿部（上身轮廓也用 out2）
    lab, n = label(m)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < 3:
            continue
        low = ys.max()
        out.append({'xc': float(xs.mean()), 'low': int(low), 'sole_x': float(xs[ys == low].mean()), 'n': len(ys)})
    return out


def measure(strip, d, n, pose=None):
    fw = strip.shape[1] // n
    F = [boots(strip[:, k * fw:(k + 1) * fw]) for k in range(n)]
    res = []
    for k in range(n):
        a, b = F[k], F[(k + 1) % n]
        best = None
        if d in ('left', 'right'):
            sg = 1 if d == 'right' else -1
            for p in a:
                for q in b:
                    if p['low'] == GROUND and q['low'] == GROUND:     # 两帧都着地：同一只脚
                        dd = sg * (p['sole_x'] - q['sole_x'])
                        if -2 <= dd <= 12 and (best is None or abs(dd - 6) < abs(best - 6)):
                            best = dd
        else:
            sg = 1 if d == 'down' else -1
            for p in a:
                for q in b:
                    if abs(p['xc'] - q['xc']) <= 2.5 and pose is not None:
                        # 只在姿势表说这只脚两帧都着地时比较（同一 x 列的脚）
                        dd = sg * (p['low'] - q['low'])
                        if 0.5 <= dd <= 12 and (best is None or dd > best):
                            best = dd
        res.append(best)
    return res, F


if __name__ == '__main__':
    png, n = sys.argv[1], int(sys.argv[2])
    rm = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    sh = np.array(Image.open(png).convert('RGBA'))
    for r, d in enumerate(ROWS):
        m, F = measure(sh[40 * r:40 * r + 40], d, n, pose=True)
        print(d, 'measured', [None if v is None else round(v, 2) for v in m])
