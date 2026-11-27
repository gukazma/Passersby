# 预览：地面带刻度，侧面走 16 帧 → 站 6 帧 → 反向走 16 帧 → 站（检查走/停切换头不跳、站姿）；hero 另做跑步
import json, numpy as np
from PIL import Image, ImageDraw
O = '/home/guleixin/pw/a11/sprites/out/'; Q = '/home/guleixin/pw/a11/sprites/qc/'
def ground(w=220, h=56):
    g = Image.new('RGBA', (w, h), (196, 190, 178, 255)); d = ImageDraw.Draw(g)
    for x in range(0, w, 8): d.line([(x, 44), (x, 47)], fill=(150, 144, 132, 255))
    return g
def frames_for(name, run=False):
    tex = Image.open(O + name + ('_run' if run else '') + '.png').convert('RGBA')
    idle = Image.open(O + name + '_idle.png').convert('RGBA')
    js = json.load(open(O + name + '_run.json')) if run else json.load(open('/tmp/yh/g/' + name + '.json'))
    rm = js['root_motion_px']; fps = js['anim_fps']
    seq = []; x = 20.0
    for d, r in (('right', 2), ('left', 1)):
        for k in range(16):
            seq.append((tex.crop((32 * (k % 8), 40 * r, 32 * (k % 8) + 32, 40 * r + 40)), x, 1 / fps))
            x += rm[d][k % 8] * (1 if d == 'right' else -1)
        for k in range(6):
            seq.append((idle.crop((32 * r, 0, 32 * r + 32, 40)), x, 1 / fps))
    for r, d in ((0, 'down'), (3, 'up')):
        for k in range(8): seq.append((tex.crop((32 * k, 40 * r, 32 * k + 32, 40 * r + 40)), x, 1 / fps))
        for k in range(4): seq.append((idle.crop((32 * r, 0, 32 * r + 32, 40)), x, 1 / fps))
    out = []
    for spr, x, dt in seq:
        g = ground(); g.alpha_composite(spr, (int(round(x)) - 16, 46 - 39)); out.append((g.resize((g.width * 4, g.height * 4), Image.NEAREST), dt))
    return out
def save(name, run=False):
    fr = frames_for(name, run)
    fr[0][0].save(Q + name + ('_run' if run else '') + '.gif', save_all=True, append_images=[f for f, _ in fr[1:]],
                  duration=[int(dt * 1000) for _, dt in fr], loop=0, disposal=2)
names = ['hero', 'hero_aunt', 'npc_office', 'npc_office_b', 'npc_office_c', 'npc_office_lin', 'npc_office_old', 'npc_student', 'npc_student_g', 'npc_student_kid', 'npc_student_r']
for n in names: save(n)
save('hero', True)
# 4x 总表
S = Image.new('RGBA', (256 + 8 + 128, 160 * len(names) + 160), (190, 190, 190, 255))
for j, n in enumerate(names):
    S.alpha_composite(Image.open(O + n + '.png').convert('RGBA'), (0, 160 * j)); S.alpha_composite(Image.open(O + n + '_idle.png').convert('RGBA'), (264, 160 * j + 60))
S.alpha_composite(Image.open(O + 'hero_run.png').convert('RGBA'), (0, 160 * len(names)))
S.resize((S.width * 4, S.height * 4), Image.NEAREST).save(Q + 'contact_x4.png')
print('ok')
