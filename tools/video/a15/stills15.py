import os, sys
from PIL import Image, ImageDraw, ImageFont
FONT = os.path.expanduser('~/gdemo/web/fonts/NotoSansSC-VF.ttf')
def f(sz):
    x = ImageFont.truetype(FONT, sz)
    try: x.set_variation_by_axes([700])
    except Exception: pass
    return x
t = Image.new('RGB', (1920, 1080), (34, 24, 18)); d = ImageDraw.Draw(t)
d.text((140, 90), 'A1.5 这一版', font=f(60), fill=(233, 184, 106))
items = ['界面干净：平时屏幕上没有任何文字，只留对话框',
         '影子跟着太阳转：早上斜向右、中午短、傍晚斜向左变长',
         '面馆原图里的静态雾抠掉，蒸汽从锅口冒出、参与遮挡',
         '跑步、走路每一帧脚都踩在地上；素材检查防悬空',
         '撞墙、撞报亭不抽风；猫狗不挡人，迎面碰到人会让开',
         '鸽子：车不惊、人近走开、跑近才飞，落路灯/屋脊再回来',
         '猫狗步态按真实四足步态重画',
         '自动测试 225 项全部通过 · 双击「运行.cmd」试玩，T 键快进时间']
for i, s in enumerate(items): d.text((160, 200 + i * 88), '· ' + s, font=f(42), fill=(255, 244, 220))
t.save('stills/todo.png')
if len(sys.argv) > 1:
    src = Image.open(sys.argv[1]).convert('RGB').resize((1920, 1080), Image.NEAREST)
    d = ImageDraw.Draw(src, 'RGBA')
    d.rectangle([0, 390, 1920, 690], fill=(30, 20, 14, 205))
    d.text((960, 475), '我亦是行人', font=f(120), fill=(255, 244, 220), anchor='mm')
    d.text((960, 610), 'A1.5 讲解：太阳影子 · 鸽子习性 · 猫狗步态 · 碰撞 · 干净界面', font=f(46), fill=(233, 184, 106), anchor='mm')
    src.save('stills/cover.png')
