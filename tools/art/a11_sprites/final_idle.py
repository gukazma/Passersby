import numpy as np
from PIL import Image
from mkidle import build
from recolor import cmap, apply
G = '/tmp/yh/g/'
PICK = {('hero', 'left'): ('a', 0), ('hero', 'right'): ('a', 0), ('npc_office', 'left'): ('a', 0), ('npc_office', 'right'): ('a', 0),
        ('npc_student', 'left'): ('a', 0), ('npc_student', 'right'): ('a', 0)}
BASE = {'hero': ['hero', 'hero_aunt'], 'npc_office': ['npc_office', 'npc_office_b', 'npc_office_c', 'npc_office_lin', 'npc_office_old'],
        'npc_student': ['npc_student', 'npc_student_g', 'npc_student_kid', 'npc_student_r']}
for b, names in BASE.items():
    side = {d: build(b, d, *PICK[(b, d)])[0] for d in ('left', 'right')}
    for n in names:
        old = np.array(Image.open(G + n + '_idle.png').convert('RGBA'))
        cm = cmap(b, n) if n != b else {}
        new = old.copy()
        for i, d in ((1, 'left'), (2, 'right')):
            new[:, 32 * i:32 * i + 32] = apply(side[d], cm) if cm else side[d]
        Image.fromarray(new).save(f'../out/{n}_idle.png')
        print(n, 'ok')
