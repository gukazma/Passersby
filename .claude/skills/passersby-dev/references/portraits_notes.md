# 对话肖像与表情图标（11-27 PORTRAITS fork）

- 用户要求：对话框里要有人物肖像（星露谷那类约定俗成的做法，画是原创的），表情随心情变化，还要有好感爱心等表情图标。
- 出图：每个角色 1 张 3×2 宫格，6 种表情依次为 neutral、happy、laugh、sad、angry、surprised。
  - 用短提示词，参考图用角色设定稿；主角用 heroA_gait 第一行，提示词里写「the young man in the top row of Image 1」。
  - 尺寸 1536×1024，每个角色出 2 版；共 16 张图，一次全部成功。
  - 提示词里写上「wide gaps between portraits」，切格才干净。
- 挑版本时要逐格看：
  - 某一格的发色或衣服会漂（乐乐 a 版「开心」那格头发变成绿色）；
  - 会多出装饰（黄丽 b 版旁边多了黄色小标记）。
- 像素化：`pixelize.py --rows 2 --cols 3 --uniform --cell 96x96 --height 90 --fixed --layout center --anchor feet --colors 40`。
  - 身高固定，所以同一角色 6 张缩放一致；胸像底边对齐到格子底部。
  - 然后迭代清理贴透明的偏洋红像素（6 轮），alpha 只留 0/255。
- 表情图标由程序画（`emotes.py`，16×16 字符画，深色描边）：heart、note、exclaim、question、sweat、anger、sleepy、dots。不花出图费用。
- 输出：`side_data/portraits/<id>/<表情>.png`（96×96）；`side_data/portraits/emotes/<名>.png`（16×16）。总览图是 `portraits/sheet.png`。
