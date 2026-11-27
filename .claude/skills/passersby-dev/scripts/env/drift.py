"""新旧两张整排楼（RGBA 真像素）对比：尺寸、轮廓 IoU、最佳水平/垂直平移。 python drift.py old.png new.png"""
import sys, numpy as np
from PIL import Image
def load(f):
    a = np.array(Image.open(f).convert("RGBA"))[..., 3] > 0; ys, xs = np.nonzero(a); return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
A, B = load(sys.argv[1]), load(sys.argv[2])
best = (0, 0, 0)
for dy in range(-20, 21, 2):
    for dx in range(-80, 81, 2):
        H = min(A.shape[0], B.shape[0] + dy) ; W = min(A.shape[1], B.shape[1] + dx)
        a = A[max(dy, 0):H, max(dx, 0):W]; b = B[max(-dy, 0):H - dy if dy > 0 else H, max(-dx, 0):W - dx if dx > 0 else W]
        h, w = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1]); a, b = a[:h, :w], b[:h, :w]
        iou = (a & b).sum() / max((a | b).sum(), 1)
        if iou > best[0]: best = (iou, dx, dy)
print("old", A.shape[::-1], "new", B.shape[::-1], "iou %.3f shift" % best[0], best[1:])
