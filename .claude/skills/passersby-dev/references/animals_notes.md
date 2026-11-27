# 街边小动物笔记（A1.4 ANIMALS fork，供合并进 passersby-dev skill）

- **先出设定稿**：每种动物一张，单行排开，包含站、走、坐、睡、舔爪等姿态，1536×1024，参考图用 fineA_ref_b。后面的动作图都拿设定稿当角色参考。5 张一次全部合格。
- **多行动作图省预算**：
  - 一张图里放 3–4 行，每行是一个动作的 n 帧。提示词写「Draw N rows, each row is k frames …, wide magenta gaps between rows」。
  - 出图后用 `split_rows.py` 按水平洋红空带切成行，再逐行转像素。
  - 本批 14 张全部可用。
- **同一种动物比例统一**：同一张图里，先用站立的那一行按目标高度算出像素尺寸，其余行用 `--pixel P` 沿用（`stripbuild.py`）。
  - 飞行图里没有站姿：海鸥按滑翔翼展反推，滑翔原图宽约 1040 px 对应 60 px，所以 P = 17.2。
- **坑：pixelize 会清掉每格最外 2 个像素**（用来去格线残留）。
  - 6–7 px 高的小鸟会被削成 3 px，比例尺寸较大的鸽子和海鸥边缘也会少一圈。
  - 解决：行图先四周补 260 px 洋红再转像素（stripbuild 已内置）。
- **小动物的根运动用模特设计值**：猫每帧只走 1–2 px，实测脚位移全是噪声，会出现负值。
  - 用 dogguide 的 guide_px 均值，靠步频调速度。
  - 猫 17–19 fps，约 26 px/s；狗 14 fps，约 37 px/s。
  - 鸟飞行 root_motion 留空，由代码按 fly_speed_px_s 移动。
- **尺寸**（65 px/m，小鸟为了看得清稍微放大）：

  | 动物 | 尺寸 |
  |---|---|
  | 猫 | 约 44×27 |
  | 小狗 | 约 46 高 |
  | 鸽子 | 约 26×13 |
  | 麻雀 | 约 18×7（真实只有约 10 px 长，太小看不清） |
  | 海鸥 | 站立 34×19，翼展 60 |
  | 远景海鸥剪影 | 20×6 |

- **平顶的鸟**（啄食的麻雀、展翅的远景海鸥）顶边是一条直线，会被 lint 判成「上边被切」。打包时每个动画顶上加 2 行透明，origin 的 y 也 +2。
- **AI 画的动作线**（摇尾巴、喘气的小短线）是独立小碎块，转像素后被去碎块步骤清掉了，挑版本时还是要看一眼。
- 出图 19 张，约 ¥4.75。全部用短提示词。

## 步态第二版（11-27 用户：「狗和猫猫的步态都有问题，你这个得好好研究一下」）

### 旧版错在哪（A1.4）
1. **模特本身会打滑**：dogguide 支撑期爪子相对躯干后移 S，又把身体每周期前进也写成 S。支撑只占 62% 周期，爪子相对地面每周期往后滑 0.6 S —— 看上去就是「原地刨地」。
   正确关系：步长 L = 身体每周期前进；支撑期爪子相对关节后移 = L × duty；根运动每帧 = L / 帧数。
2. **步子太小、步频太高**：步长只有 0.62 倍肩高（真实走路 ≈1.6–2.0 倍），只好把步频拉到 17–19 fps（猫）、14 fps（狗）凑速度，像碎步小跑。
3. **腿只有两节**：前腿没有向后的肘，后腿没有向前的膝 + 向后的跗关节，AI 照着画就成了木棍腿 / 反关节。
4. **猫用的是狗的模特**：猫躯干更长、肚子收、臀比肩高、头低平、尾巴竖起末端弯，全都没有。
5. **AI 没按模特的步序画**：旺财 walk 相邻帧腿的前后顺序乱跳、第 0 帧和第 7 帧几乎一样，根运动里还有一帧 0 → 一顿一顿。
6. **模特太小**：384×1024 的格子里肩高只有 100–110 px，AI 自由发挥空间大。

### 真实数据（来源见末尾）
| | 猫走 | 狗走 | 狗快步 trot |
|---|---|---|---|
| 速度 | 0.5–0.75 m/s（走/快步转换 ≈1 m/s，Fr≈0.5） | ≈1 m/s | 1.5–2.5 m/s |
| 步长（每周期身体前进） | 0.44–0.49 m ≈ 1.8–2.0 × 肩高 | ≈1.5–1.8 × 肩高 | ≈2.0–2.2 × 肩高 |
| 周期 | 0.6–1.04 s（1.0–1.7 Hz） | 小狗周期更短、步频更高 | |
| duty（支撑占比） | ≈0.55–0.60 | 0.6–0.66（走 50–80%） | 0.40–0.50（小狗在同速下已经在快步） |
| 步序 | 侧序四拍 LH→LF→RH→RF，四拍间隔近似均匀（diagonality ≈25%，蹲伏时更高） | 侧序四拍，二/三足支撑交替，永远不全离地 | 对角两拍 LH+RF / RH+LF，极短腾空 |

- 关节：前腿 肩关节→肘（向后凸）→腕→爪；后腿 髋→膝（向前凸）→跗（向后凸）→趾行着地。前腿抬起时腕关节折叠、爪子翻向后上方，落地前伸直前探。
- 猫：肩胛随同侧前腿支撑上下滚动；头低、几乎不上下动；尾巴竖起、末端问号弯、随步子轻摆；后爪落在前爪刚离开的位置（直接踩点）。
- 狗：头随前腿着地轻点；卷尾左右轻晃；身体每周期起伏两次。

### 新流水线
- 模特 `scripts/actions/quadguide.py --species dog|puppy|cat --gait walk|trot`：三节腿 + IK、肩胛前后移（有效支点更高，腿摆角不过大）、身体起伏、点头、尾巴摆动；2 行 × 4 列、每格 768×768、肩高 230 px，出图 3072×1536。
- 参数（以肩高 Hs 为单位）：狗走 L=1.70、duty 0.62、10 fps；狗快步 L=2.10、duty 0.45、16 fps；小狗走 L=1.45、11 fps；猫走 L=1.90、duty 0.60、10 fps。
- 出图提示词（短）：「Image 1: pose reference, 8 grey four-legged mannequins walking to the right, in 2 rows of 4 (light grey = near-side legs, dark grey = far-side legs). Image 2: <动物> (use its side view). Draw … in each of the 8 poses of Image 1, same grid, positions and size; copy every leg angle and which paws touch the ground exactly. All legs keep the animal's own fur colour, far-side legs one shade darker, no grey. Same pixel art style as Image 2. Flat magenta #FF00FF background. No text, no shadow, no people.」
- 构建 `scripts/actions/quadbuild.py <ai.png> <guide.json> <out> --height H`：洋红底守门 → pixelize 2×4 → 躯干对齐 + 统一底线 → 实测着地爪后移作根运动 → 回放爪滑 slip。模特自己跑一遍 slip ≈0.3 px（验证模特不滑）。
- 挑版本：逐帧看 4 条腿（近深远浅分得开、没有多腿/少腿、爪没被切）、步序对得上模特；slip_mean_px 越小越好。

### 来源
- 猫行走压力步道（速度 0.54–0.74 m/s、duty 0.54–0.55、步长 0.44–0.49 m、周期 ≈1.03 s）：https://bmcvetres.biomedcentral.com/articles/10.1186/1746-6148-9-129
- 猫明暗环境行走（0.49–0.65 m/s、步周期 594–768 ms、duty ≈60%、步频 1.25–1.75 Hz）：https://www.researchgate.net/figure/General-characteristics-of-walking-Velocity-A-stride-length-B-stride-duration-C_fig4_304399315
- 猫潜行步态（走/快步转换 ≈1 m/s、Fr 0.5；diagonality 猫常 ≈25%、蹲伏时更高）：https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0003808
- 狗步态参数（走 duty 50–80%、快步 40–60%）：https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0198893
- 小狗同速下已在快步、步频更高：https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5015230/
- 崎岖地面狗走 duty 0.66：https://journals.biologists.com/jeb/article/220/10/1864/17791/Longitudinal-quasi-static-stability-predicts
- 狗走侧序四拍、二/三足支撑交替：https://www.sitstaysquat.ca/blog/canine-gait-patterns/
- 艺术作品里四足走路常画错（侧序是正确的）：https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3515592/
- Muybridge 狗走 Plate 704（12 帧 0.83 s）：https://sillydragon.com/muybridge/Plate_0704.html

### 本轮结果（11-27，第二版步态已放进游戏）
| 角色/动画 | 选用 | 帧 | fps | 速度 | slip_mean_px |
|---|---|---|---|---|---|
| 旺财 walk_side | wc_walk_a（洋红底） | 78×52 | 10 | 65 px/s ≈ 1.0 m/s（旧 33） | 0.25 |
| 旺财 run_side（快步） | wc_trot3_f（透明底） | 78×47 | 16 | 111 px/s ≈ 1.7 m/s | 0.73 |
| 小黑白狗 walk_side | d2_walk_b（洋红底） | 74×47 | 11 | 63 px/s ≈ 0.97 m/s（旧 37） | 0.44 |
| 橘猫 walk_side | co_walk3_f（透明底） | 60×28 | 11 | 40 px/s ≈ 0.61 m/s（旧 27 @17fps） | 0.20 |
| 三花 walk_side | cc_walk3_e（透明底） | 56×29 | 11 | 42 px/s ≈ 0.65 m/s（旧 23 @19fps） | 0.18 |

- **透明底出图首选**：spec 加 `"extra": {"background": "transparent", "output_format": "png"}`，提示词把洋红那句换成「Transparent background, no glow, no halo.」。两张参考图（模特 + 设定稿）+ 洋红底时，32 张里 22 张出黑底/光晕；透明底 6 张全部可用，像素化后描边也更干净（洋红底的三花描边断成虚线）。quadbuild 自动识别透明底（alpha<128 当背景）。
- **猫模特别按真猫的瘦长比例画**：第一版（躯干 1.45 倍肩高、腿长）AI 照着画成细长猫，和游戏里圆滚滚的设定对不上；改成设定稿比例（躯干 1.22、腿短、头大、尾巴短）。提示词加「keep the animal's own body shape and proportions from Image 2」。
- **尺寸核对**：新走路帧和 idle_side 并排放大看身体大小；快步帧按同样高度会偏大（身体放低、腿张开），旺财快步 --height 46、走路 50；猫 28。
- **origin.x 按 idle_side 的躯干偏移对齐**（`gait2/package.py`），站↔走切换身体不横跳；origin.y = 底行（lint [悬空]）。
- lint 的 [内部切口] 警告在猫走帧上是浅色胸口/爪尖没描边，不是真切口（已放大核对）。
- 出图 38 张（20 + 12 + 6），约 ¥9.5。
