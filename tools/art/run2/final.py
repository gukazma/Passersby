import json, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, '.')
import run_gen
from measure import measure, ROWS

OUT = '/home/guleixin/pw/a11/sprites/run2/'
for n, fps, name in ((8, 14.0, 'hero_run'), (16, 28.0, 'hero_run16')):
    order = {d: list(range(8)) for d in ROWS}
    sheet, info = run_gen.build(n, order)
    Image.fromarray(sheet).save(OUT + name + '.png')
    step = run_gen.CYCLE / n
    rm = {d: [step] * n for d in ROWS}
    qc = {}
    for r, d in enumerate(ROWS):
        m, _ = measure(sheet[40 * r:40 * r + 40], d, n, pose=True)
        st = [k for k in range(n) if info[d][k][0][3] and info[d][(k + 1) % n][0][3] or info[d][k][1][3] and info[d][(k + 1) % n][1][3]]
        err = [abs(m[k] - step) for k in range(n) if m[k] is not None]
        qc[d] = {'measured_px': m, 'stance_transitions': st, 'visible_stance_measured': len(err),
                 'max_abs_root_minus_measured_px': max(err) if err else None}
        # 每帧着地脚的鞋底位置（像素）：纵向被裙子挡住的不计
    a = np.array(Image.open(OUT + name + '.png'))[..., 3] > 0
    meta = {"sheet": name + ".png", "frame": [32, 40], "anchor_feet": [16, 39], "rows": ROWS, "frames_per_row": n,
            "anim_fps": fps, "cycle_px": run_gen.CYCLE, "speed_px_per_s": run_gen.CYCLE * fps / n,
            "movement": "跑步：每只脚着地占 1/4 循环（落地 +6 → 正下方 → 蹬地 −6，相对髋部），每帧落地脚后移量 = root_motion_px（像素级精确）；"
                        "另外两个 1/4 是双脚腾空。上身（头、躯干、手臂、背篓）用 AI 跑步帧（与行走表同一个头，侧面前倾 1 像素），裙摆与腿程序绘制（run2/work/run_gen.py）。",
            "root_motion_px": rm, "qc": qc}
    json.dump(meta, open(OUT + name + '.json', 'w'), ensure_ascii=False, indent=1)
    print(name, 'speed', meta['speed_px_per_s'], {d: (qc[d]['visible_stance_measured'], qc[d]['max_abs_root_minus_measured_px']) for d in ROWS})
    ys = np.nonzero(a.any(1))[0]
    for r in range(4):
        rr = a[40 * r:40 * r + 40]
        print('  row', ROWS[r], 'feet bottom rows', sorted({int(np.nonzero(rr[:, 32 * k:32 * k + 32].any(1))[0].max()) for k in range(n)}),
              'top', sorted({int(np.nonzero(rr[:, 32 * k:32 * k + 32].any(1))[0].min()) for k in range(n)}))
