# 车辆精灵笔记（A1.4 VEHICLES fork）

- **出图**：短提示词，「Image 1: style reference. Draw <车>, exact side view facing right, whole vehicle visible with a wide margin, wheels at the bottom. Same pixel art style as Image 1. Flat magenta. No text, no logos, no shadow.」
  - 5 种车各出 2 版，全部一次可用，朝向都对。
- **定尺寸**：`vehproc.py <raw> <目标长度px> <out>`，按 65 px/m 用车长反推像素尺寸。AI 自己的网格和目标相差 ≤8% 时用 AI 网格。
  - 裁剪前四周留 14 px 原图边。不留边的话，只有 1–2 个像素宽的车头、车尾会被切掉（白车的前保险杠被切过一次）。
- **车轮**：自动找轮子（底部的深色列段）对小轿车可靠；面包车、摩托会认错（把发动机认成轮子，两个轮子半径不一）。
  - 先出带刻度的标记图 `mark.py`，看过后用 `--wheelspec x,y,r;x,y,r` 手动指定。
- **轮子转动**：不另画假轮毂，而是把 AI 画的轮毂区域（半径 0.62r）按最近邻旋转，每帧 22.5°，共 4 帧，保留原画风。
  - 帧速 = fps_per_100px × 速度/100，其中 fps_per_100px = 1600 / 周长。
- **车灯**：自动找亮黄、红像素不可靠（会认到车顶或车窗），全部按标记图手动给 `--lights front=x,y/...;rear=x,y`。
- **自行车**：`bikeguide.py` 画 8 帧曲柄角的姿势模特：大腿、小腿用两节反解，膝盖朝前。注意反解的符号，第一次膝盖朝后了。
  - AI 照着画后，细车架线会混进洋红变成紫边。处理办法：紫色像素旁边有不透明像素的改成车架深色，孤立的删掉（`cycfix.py`）。
  - 按后轮左缘对齐各帧。最后一帧前轮被原图边切掉，用前一帧同位置补上。
- **检查**：洋红 0、半透明 0、切边 0（切边判据同 lint：边上的不透明像素大多是非描边色）。另外出一张带 110 px 灰人的总览图看比例。
