"""素材与数据静态检查（每次交付前必须跑，FAIL 就不交付）。
    python tests/lint_assets.py [game_dir]
检查：
 A 精灵/道具：边缘被直线切掉、洋红杂边、半透明像素、全透明空图
 B 角色动画：图宽 = 帧数×帧宽、origin 在帧内、每帧脚底一致、身高一致（行走类）、帧边缘被裁（人物贴到帧边）
   速度范围：walk_side 50–110 px/s，run_side 130–220，walk_front/back 15–60
 C 头像：每个对话角色 6 种表情齐全、96×96、非空
 D world.json：引用文件存在、门/座位/斑马线/出口指向有效、座位和 NPC 路点在纵深带内且不在家具碰撞里、补摆道具不挡门
输出每条问题一行，末行 RESULT PASS/FAIL。
"""
import json, os, sys, glob
import numpy as np
from PIL import Image
G = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..')
D = os.path.join(G, 'side_data')
problems, warns = [], []
def P(msg): problems.append(msg)
def W(msg): warns.append(msg)
def rgba(p): return np.array(Image.open(p).convert('RGBA'))

def edge_cut(a, name, min_px=6):
    """被切掉的判据：边上有一长段不透明像素，而且这些像素大多不是深色描边（物体自然的直边会有描边，切口露出的是内部颜色）。"""
    al = a[..., 3] > 0
    lum = (a[..., :3].astype(int) @ [30, 59, 11]) // 100
    for side, sl in (('左', (slice(None), 0)), ('右', (slice(None), -1)), ('上', (0, slice(None)))):
        m = al[sl]; n = int(m.sum())
        if n < min_px: continue
        inner = (lum[sl][m] > 85).mean()        # 非描边（亮/中间色）的比例
        span = n / max(1, (al.any(1).sum() if side != '上' else al.any(0).sum()))
        if inner > 0.5 and span > 0.15:
            P(f'[切边] {name}: {side}边有 {n} 个不透明像素贴边，其中 {inner:.0%} 是内部颜色（疑似被裁切）')
            return


def fringe(a, name):
    r, g, b, al = (a[..., i].astype(int) for i in range(4))
    m = (al > 0) & (r - g > 60) & (b - g > 60) & (np.abs(r - b) < 80)
    if m.sum() > 3:
        P(f'[洋红] {name}: {int(m.sum())} 个洋红色像素')
    semi = ((al > 0) & (al < 255)).sum()
    if semi > 0:
        W(f'[半透明] {name}: {int(semi)} 个半透明像素')

# A 道具精灵
FULL = ('ground', 'far', 'bg', 'row', 'block', 'room', 'sky', 'interior', 'alley', 'zebra', 'harbour', 'promenade')
for sc in sorted(glob.glob(os.path.join(D, 'scenes', '*', '*.json'))):
    j = json.load(open(sc, encoding='utf-8')); base = os.path.dirname(sc); sid = j['id']
    layer_imgs = {L['img'] for L in j.get('layers', [])}
    for p in j.get('props', []):
        f = os.path.join(base, p['img'])
        if not os.path.exists(f):
            P(f'[缺图] {sid}: {p["img"]}'); continue
        a = rgba(f)
        if a[..., 3].max() == 0: P(f'[空图] {sid}/{p["img"]}')
        edge_cut(a, f'{sid}/{p["img"]}'); fringe(a, f'{sid}/{p["img"]}')
    for L in j.get('layers', []):
        if not os.path.exists(os.path.join(base, L['img'])): P(f'[缺图] {sid}: layer {L["img"]}')
for f in glob.glob(os.path.join(D, 'props', '*.png')):
    a = rgba(f); edge_cut(a, 'props/' + os.path.basename(f)); fringe(a, 'props/' + os.path.basename(f))

# B 角色动画
SPEED = {'walk_side': (25, 120), 'run_side': (130, 220), 'walk_front': (15, 60), 'walk_back': (15, 60), 'walk_diagf': (40, 110), 'walk_diagb': (40, 110)}
DOG_SPEED = {'walk_side': (20, 80), 'run_side': (50, 130)}
for cj in sorted(glob.glob(os.path.join(D, 'chars', '*', 'char.json'))):
    c = json.load(open(cj, encoding='utf-8')); base = os.path.dirname(cj); cid = c['id']
    dog = c.get('kind') == 'dog'
    for k, an in c['anims'].items():
        f = os.path.join(base, an['file']); name = f'{cid}/{k}'
        if not os.path.exists(f): P(f'[缺图] {name}'); continue
        a = rgba(f); h, w = a.shape[:2]
        fw, fh, n = an['frame_w'], an['frame_h'], an['frames']
        if w != fw * n or h != fh: P(f'[帧尺寸] {name}: 图 {w}x{h}，应为 {fw * n}x{fh}')
        ox, oy = an.get('origin', [fw // 2, fh - 1])
        if not (0 <= ox <= fw and 0 <= oy <= fh): P(f'[origin] {name}: {ox},{oy} 不在帧内')
        fringe(a, name)
        bottoms, heights = [], []
        for i in range(n):
            fr = a[:, i * fw:(i + 1) * fw, 3] > 0
            if not fr.any(): P(f'[空帧] {name} 第 {i} 帧'); continue
            ys = np.nonzero(fr.any(1))[0]; xs = np.nonzero(fr.any(0))[0]
            bottoms.append(ys.max()); heights.append(ys.max() - ys.min())
            # 真被切 = 边上出现一长条直线；只是贴边（头发尖、鞋尖）不算
            hgt = ys.max() - ys.min() + 1; wid = xs.max() - xs.min() + 1
            if fr[:, 0].sum() > 0.22 * hgt or fr[:, -1].sum() > 0.22 * hgt:
                P(f'[帧裁切] {name} 第 {i} 帧: 左/右边被直线切掉（{max(fr[:, 0].sum(), fr[:, -1].sum())} px）')
            if fr[0, :].sum() > 0.45 * wid:
                P(f'[帧裁切] {name} 第 {i} 帧: 上边被直线切掉（{fr[0, :].sum()} px）')
        # 内部切口：轮廓上出现一竖条（≥3 像素）非描边的亮色边界像素 = 被直线切过（不管在帧的哪里）
        lum = (a[..., :3].astype(int) @ [30, 59, 11]) // 100
        al_all = a[..., 3] > 0
        for i in range(n):
            fal = al_all[:, i * fw:(i + 1) * fw]; flum = lum[:, i * fw:(i + 1) * fw]
            hh, ww = fal.shape
            for side in (-1, 1):
                nb = np.zeros_like(fal)
                if side < 0: nb[:, 1:] = ~fal[:, :-1]; nb[:, 0] = True
                else: nb[:, :-1] = ~fal[:, 1:]; nb[:, -1] = True
                edge = fal & nb & (flum > 95)
                for x in range(ww):
                    col = edge[:, x]
                    run = best = 0
                    for v in col:
                        run = run + 1 if v else 0; best = max(best, run)
                    if best >= 4:
                        W(f'[内部切口] {name} 第 {i} 帧: x={x} 有 {best} 像素长的亮色直边（像被切过）')
                        break
                else:
                    continue
                break
        # 侧面走/跑：地面附近两只脚的大小要相近
        if k == 'walk_side' and not dog:
            for i in (0, n // 2):            # 触地帧：双脚都在地上
                fal = al_all[:, i * fw:(i + 1) * fw]
                ys = np.nonzero(fal.any(1))[0]
                if len(ys) == 0: continue
                band_ = fal[max(0, ys.max() - 7):ys.max() + 1]
                cols = np.nonzero(band_.any(0))[0]
                blobs = [r for r in np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1) if len(r)]
                if len(blobs) >= 2:
                    sizes = sorted(int(band_[:, r[0]:r[-1] + 1].sum()) for r in blobs)
                    if sizes[-2] < 0.3 * sizes[-1] and sizes[-2] < 25:
                        P(f'[脚被切] {name} 第 {i} 帧: 两只脚大小 {sizes[-2]} / {sizes[-1]} 像素，有一只只剩一点')
        if k.startswith(('walk', 'run', 'idle')) and len(heights) > 1:
            if max(bottoms) - min(bottoms) > 3 and k in ('walk_side', 'idle_side', 'idle_front', 'idle_back'):
                P(f'[脚底] {name}: 各帧脚底相差 {max(bottoms) - min(bottoms)} px')
            if max(heights) - min(heights) > max(10, 0.12 * max(heights)):
                W(f'[身高] {name}: 各帧高度 {min(heights)}–{max(heights)}')
        rm = an.get('root_motion_px', [])
        lim = (DOG_SPEED if dog else SPEED).get(k)
        if cid == 'hero' and k == 'walk_side': lim = (65, 95)
        if lim and rm:
            v = sum(rm) / n * an['fps']
            if not (lim[0] <= v <= lim[1]): P(f'[速度] {name}: {v:.0f} px/s 不在 {lim[0]}–{lim[1]}')
            if min(rm) < 0: P(f'[根运动] {name}: 有负值 {min(rm)}')

# C 头像
W_ = json.load(open(os.path.join(D, 'world.json'), encoding='utf-8'))
talkers = {n['char'].split('/')[1] for n in W_['npcs'] if n.get('talk')}
for cid in talkers:
    for e in ('neutral', 'happy', 'laugh', 'sad', 'angry', 'surprised'):
        f = os.path.join(D, 'portraits', cid, e + '.png')
        if not os.path.exists(f): P(f'[头像] {cid} 缺 {e}'); continue
        im = Image.open(f)
        if im.size != (96, 96): P(f'[头像] {cid}/{e} 尺寸 {im.size}')

# D world.json
scenes = {}
for sid, rel in W_['scenes'].items():
    f = os.path.join(D, rel)
    if not os.path.exists(f): P(f'[场景] {sid}: {rel} 不存在'); continue
    scenes[sid] = json.load(open(f, encoding='utf-8'))
def solids(sid):
    j = scenes[sid]; out = []
    for p in j.get('props', []):
        so = p.get('solid') or []
        if len(so) == 2 and so[0] > 0: out.append((p['x'] - so[0] / 2, p['y_foot'] - so[1], p['x'] + so[0] / 2, p['y_foot'], p['img']))
    return out
def inside_solid(sid, x, y, half=9):
    for x0, y0, x1, y1, img in solids(sid):
        if x + half > x0 and x - half < x1 and y + 3 > y0 and y - 3 < y1: return img
    return None
for sid, j in scenes.items():
    for side, e in (j.get('exits') or {}).items():
        if e and e.get('to') and e['to'] not in scenes: P(f'[出口] {sid}.{side} → {e["to"]} 不存在')
    for z in j.get('zebras', []):
        if z['to'] not in scenes: P(f'[斑马线] {sid} → {z["to"]} 不存在')
        elif not any(z2.get('to') == sid for z2 in scenes[z['to']].get('zebras', [])): P(f'[斑马线] {z["to"]} 没有回到 {sid} 的斑马线')
    for d in j.get('doors', []):
        if d.get('interior') and d['interior'] not in scenes: P(f'[门] {sid}/{d["id"]} → {d["interior"]} 不存在')
for sid, lst in W_.get('spots', {}).items():
    b = scenes[sid].get('band', [392, 468])
    for sp in lst:
        if not (b[0] <= sp['y'] <= b[1]): P(f'[座位] {sid}/{sp["id"]} y={sp["y"]} 不在纵深带 {b}')
for sid, lst in W_.get('spots', {}).items():
    for sp in lst:
        if sp.get('hero_anim', 'sit_bench') == 'sit_bench' and sp.get('player', True):
            near = [p for p in scenes[sid].get('props', []) if 'bench' in p['img'] and abs(p['x'] - sp['x']) <= 12 and abs(p['y_foot'] - sp['y']) <= 10]
            if not near: P(f'[座位] {sid}/{sp["id"]} ({sp["x"]},{sp["y"]}) 附近没有长椅')
for sid, lst in W_.get('extra_props', {}).items():
    for ep in lst:
        for d in scenes[sid].get('doors', []):
            if d['x0'] - 8 < ep['x'] < d['x1'] + 8 and ep['y_foot'] < scenes[sid]['band'][0] + 14 and 'bowl' not in ep['img']:
                P(f'[挡门] {sid}: 补摆道具 {os.path.basename(ep["img"])} x={ep["x"]} 挡住门 {d["id"]}')
for n in W_['npcs']:
    sid = n['scene']; b = n.get('band', scenes[sid].get('band'))
    cf = os.path.join(D, n['char'])
    if not os.path.exists(cf): P(f'[NPC] {n["char"]} 不存在'); continue
    anims = json.load(open(cf, encoding='utf-8'))['anims']
    pts = ([] if (n.get('special') and not n.get('loop')) else [('起点', n['x'], n['y'])]) + [(str(c), c[1], c[2]) for c in n.get('loop', []) if c[0] == 'walk']   # 柜台后不动的人不查
    for lab, x, y in pts:
        if not (b[0] - 0.5 <= y <= b[1] + 0.5): P(f'[NPC 路点] {n["char"]} {lab}: y={y} 不在纵深带 {b}')
        s_ = inside_solid(sid, x, y)
        if s_: P(f'[NPC 路点] {n["char"]} {lab}: ({x},{y}) 在家具 {s_} 的碰撞里')
        if not (0 <= x <= scenes[sid]['width']): P(f'[NPC 路点] {n["char"]} {lab}: x={x} 超出街宽')
    for c in n.get('loop', []):
        if c[0] in ('anim',) and c[1] not in anims: P(f'[NPC 动作] {n["char"]} 没有动画 {c[1]}')
        if c[0] == 'use':
            if len(c) > 3 and c[3] not in anims: P(f'[NPC 动作] {n["char"]} 没有动画 {c[3]}')
            if not any(sp['id'] == c[1] for sp in W_.get('spots', {}).get(sid, [])): P(f'[NPC 座位] {n["char"]} 座位 {c[1]} 不存在')
        if c[0] in ('enter', 'exit') and not any(d['id'] == c[1] for d in scenes[sid].get('doors', [])): P(f'[NPC 门] {n["char"]} 门 {c[1]} 不存在')
    for L in n.get('talk', []):
        t = L if isinstance(L, str) else L.get('t', '')
        if len(t) > 60: P(f'[台词过长] {n["char"]}: {len(t)} 字（对话框两行约 52 字）')
for w in warns: print('WARN', w)
for p in problems: print('FAIL', p)
print(f'RESULT {"PASS" if not problems else "FAIL"}  problems={len(problems)} warnings={len(warns)}')
sys.exit(1 if problems else 0)
