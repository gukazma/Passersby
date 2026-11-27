# 侧面行走行锁头：每帧 [0,N) 行换成参考帧的头（固定高度、固定 x），去掉闪脸和头部 1px 乱跳
import sys, json, numpy as np
from PIL import Image
G = '/tmp/yh/g/'
NECK = {'hero': 17, 'npc_office': 19, 'npc_student': 18}
BASE = {'hero': ['hero', 'hero_aunt'], 'npc_office': ['npc_office', 'npc_office_b', 'npc_office_c', 'npc_office_lin', 'npc_office_old'],
        'npc_student': ['npc_student', 'npc_student_g', 'npc_student_kid', 'npc_student_r']}
REF = {}
def stats(c):
    a = c[..., 3] > 0; t = np.where(a.any(1))[0].min(); hx = np.where(a[t:t + 10].any(0))[0]; return int(t), (hx.min() + hx.max()) / 2
def pick(w, r):
    cs = [w[40 * r:40 * r + 40, 32 * k:32 * k + 32] for k in range(8)]
    st = [stats(c) for c in cs]
    tops = [s[0] for s in st]; mt = max(set(tops), key=tops.count)
    xs = [s[1] for s in st if s[0] == mt]; mx = max(set(xs), key=xs.count)
    return [k for k in range(8) if st[k] == (mt, mx)][0]
out = {}
for b, names in BASE.items():
    wb = np.array(Image.open(G + b + '.png').convert('RGBA'))
    refs = {r: pick(wb, r) for r in (1, 2)}           # 参考帧由底版决定，配色版同一帧（同 alpha）
    for n in names:
        w = np.array(Image.open(G + n + '.png').convert('RGBA'))
        N = NECK[b]
        for r, k0 in refs.items():
            head = w[40 * r:40 * r + N, 32 * k0:32 * k0 + 32].copy()
            for k in range(8):
                w[40 * r:40 * r + N, 32 * k:32 * k + 32] = head
        Image.fromarray(w).save(f'../out/{n}.png')
        out[n] = refs
print(out)
