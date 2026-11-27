import numpy as np
from PIL import Image
G = '/tmp/yh/g/'
def cmap(base, var):
    B = np.array(Image.open(G + base + '.png').convert('RGBA')); V = np.array(Image.open(G + var + '.png').convert('RGBA'))
    m = B[..., 3] > 0; kb = B[m][:, :3]; kv = V[m][:, :3]
    d = {}
    for cb, cv in zip(map(tuple, kb), map(tuple, kv)):
        d.setdefault(cb, {}); d[cb][cv] = d[cb].get(cv, 0) + 1
    return {k: max(v, key=v.get) for k, v in d.items()}
def palette(base):
    B = np.array(Image.open(G + base + '.png').convert('RGBA')); m = B[..., 3] > 0
    return np.unique(B[m][:, :3], axis=0)
def to_pal(img, pal):
    a = img.copy(); m = a[..., 3] > 0
    px = a[m][:, :3].astype(int); d = ((px[:, None, :] - pal[None].astype(int)) ** 2).sum(-1)
    a[..., :3][m] = pal[d.argmin(1)]; a[..., 3] = np.where(m, 255, 0); return a
def apply(img, cm):
    a = img.copy(); m = a[..., 3] > 0
    for i, (y, x) in enumerate(zip(*np.where(m))):
        a[y, x, :3] = cm.get(tuple(a[y, x, :3]), tuple(a[y, x, :3]))
    return a
if __name__ == '__main__':
    for b, v in [('hero', 'hero_aunt'), ('npc_office', 'npc_office_lin'), ('npc_student', 'npc_student_kid')]:
        cm = cmap(b, v); print(v, len(cm), len(palette(b)), sum(1 for k, x in cm.items() if k != x))
