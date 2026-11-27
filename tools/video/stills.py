import json, os
from PIL import Image, ImageDraw, ImageFont
H = os.path.expanduser('~'); FONT = H + '/gdemo/web/fonts/NotoSansSC-VF.ttf'
BG = (34, 24, 18); FG = (255, 244, 220); AC = (233, 184, 106)
def font(sz, wght=700):
    f = ImageFont.truetype(FONT, sz)
    try: f.set_variation_by_axes([wght])
    except Exception: pass
    return f
def canvas(title):
    c = Image.new('RGB', (1920, 1080), BG); d = ImageDraw.Draw(c)
    d.text((80, 50), title, font=font(54), fill=AC)
    return c, d
def paste_fit(c, im, box, nearest=True):
    x, y, w, h = box; s = min(w / im.width, h / im.height)
    if nearest and s >= 2: s = int(s)
    im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.NEAREST if nearest else Image.LANCZOS)
    c.paste(im2, (x + (w - im2.width) // 2, y + (h - im2.height) // 2), im2 if im2.mode == 'RGBA' else None)
    return im2
G = H + '/pw/a13/game/side_data'
# style：街景 + 招牌特写
c, d = canvas('新画风：960×540 真像素 ×2 显示，招牌字由 AI 直接画上')
st = Image.open('src/frame_street.png').convert('RGB')
paste_fit(c, st, (80, 150, 1120, 630))
crop = st.crop((10, 135, 310, 205)); paste_fit(c, crop, (1240, 200, 600, 160))
crop2 = st.crop((735, 135, 960, 205)); paste_fit(c, crop2, (1240, 420, 600, 160))
d.text((1240, 620), '招牌特写（放大）', font=font(36), fill=FG)
c.save('stills/style.png')
# heroes
c, d = canvas('主角三套设计（每套男 / 女）')
for i, h in enumerate('ABC'):
    im = Image.open(f'src/hero{h}_gait.png').convert('RGB'); im = im.resize((im.width * 300 // im.height, 300), Image.LANCZOS)
    c.paste(im, (220, 150 + i * 305)); d.text((90, 270 + i * 305), h, font=font(80), fill=AC)
d.text((1450, 990), '演示先用 A（芥黄风衣）', font=font(34), fill=FG)
c.save('stills/heroes.png')
# guide → AI → pixels
c, d = canvas('姿势模特（真人步态数据）→ AI 照着画 → 真像素')
g = Image.open(H + '/pw/a13/chars/walk_guide.png').convert('RGB'); g = g.resize((1560, 520), Image.LANCZOS).crop((0, 80, 1560, 520))
c.paste(g, (180, 140)); d.text((60, 330), '模特', font=font(40), fill=FG)
px = Image.open(H + '/pw/a13/chars/out/hero_walk_f.png').convert('RGBA'); bgp = Image.new('RGBA', px.size, (236, 226, 206, 255)); bgp.alpha_composite(px)
k = min(1700 / px.width, 420 / px.height); px2 = bgp.resize((int(px.width * k), int(px.height * k)), Image.NEAREST)
c.paste(px2.convert('RGB'), (150 + (1700 - px2.width) // 2, 600)); d.text((40, 760), '成品', font=font(40), fill=FG)
c.save('stills/guide.png')
# dirs：五个方向 + 跑 + 站
c, d = canvas('主角动画：五个方向行走 + 跑步 + 站立（朝左用镜像）')
cj = json.load(open(G + '/chars/hero/char.json'))
names = [('walk_side', '侧面走'), ('walk_diagf', '右前斜'), ('walk_front', '正面走'), ('walk_diagb', '右后斜'), ('walk_back', '背面走'), ('run_side', '跑'), ('idle_side', '站立')]
x = 70
for k, lab in names:
    a = cj['anims'][k]; im = Image.open(G + '/chars/hero/' + a['file']).convert('RGBA').crop((0, 0, a['frame_w'], a['frame_h']))
    im = im.resize((im.width * 5, im.height * 5), Image.NEAREST)
    bb = im.getbbox(); im = im.crop(bb)
    c.paste(im, (x, 900 - im.height), im); d.text((x + im.width // 2 - 50, 930), lab, font=font(36), fill=FG); x += im.width + 40
c.save('stills/dirs.png')
# gait
c, d = canvas('每个人走路都不一样（身高 · 胖瘦 · 年龄 · 是否健身 · 拿着东西）')
paste_fit(c, Image.open(H + '/pw/a13/npc/out/gait_compare.png').convert('RGB'), (80, 140, 1760, 900), nearest=False)
c.save('stills/gait.png')
# ruler
c, d = canvas('室内比例：一米七的人 = 110 像素（1 米 ≈ 65 像素）')
paste_fit(c, Image.open(H + '/pw/a13/env/out/preview_chenji.png').convert('RGB'), (80, 130, 1760, 920))
c.save('stills/ruler.png')
# graph
c, d = canvas('街道怎么衔接：一段段街组成一张图')
def box(x, y, w, h, t, sub=''):
    d.rounded_rectangle([x, y, x + w, y + h], 18, fill=(70, 48, 34), outline=AC, width=4)
    d.text((x + 30, y + 25), t, font=font(44), fill=FG)
    if sub: d.text((x + 30, y + 90), sub, font=font(28, 400), fill=(220, 200, 170))
def arrow(x0, y0, x1, y1, t):
    d.line([x0, y0, x1, y1], fill=AC, width=6)
    d.text(((x0 + x1) // 2 - 80, (y0 + y1) // 2 - 50), t, font=font(32), fill=AC)
box(160, 430, 560, 170, '永安街 · 北侧', '约 3.8 屏 · 10 间铺面')
box(1180, 430, 560, 170, '滨江路', '沿海港 · 渡轮码头 · 长椅')
box(160, 820, 560, 170, '永安街 · 南侧', '街市 · 书店 · 小学 · 旺财')
box(160, 160, 560, 170, '陈记云吞面（室内）', '剖面视角 · 陈伯 · 食客')
arrow(720, 515, 1180, 515, '走到街角拐弯')
arrow(440, 600, 440, 820, '斑马线按 S 过马路')
arrow(440, 430, 440, 330, '门前按 W 进门')
c.save('stills/graph.png')
# todo
c, d = canvas('需要你定的事')
items = ['1. 主角用哪一套设计（A 芥黄风衣 / B 牛仔外套 / C 红开衫眼镜，男女可选）',
         '2. 每个场景的背景音乐各有两首候选，挑你喜欢的',
         '3. 试玩这一版：横版移动、斜走、跑步、进门、坐下、摸狗、拍照的手感']
for i, t in enumerate(items): d.text((140, 260 + i * 160), t, font=font(44), fill=FG)
d.text((140, 860), '双击仓库根目录的「运行.cmd」开始玩', font=font(40), fill=AC)
c.save('stills/todo.png')
# cover
c = Image.new('RGB', (1920, 1080), BG)
paste_fit(c, st, (0, 0, 1920, 1080)); d = ImageDraw.Draw(c)
d.rectangle([0, 360, 1920, 720], fill=(34, 24, 18))
d.text((960, 450), '我亦是行人', font=font(120), fill=FG, anchor='mm')
d.text((960, 600), 'A1.3 横版演示：街道 · 居民 · 进门 · 动作 · 音乐', font=font(48), fill=AC, anchor='mm')
c.save('stills/cover.png')
print('ok')
