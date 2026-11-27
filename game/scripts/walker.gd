extends CharacterBody2D
## 行走/跑步：动画固定帧率；身体在每一帧的时间里按该帧的根运动匀速前进（连续移动，不再一跳一跳），
## 一个周期走过的距离 = 根运动之和，脚步不打滑。撞到东西沿墙滑。
## 精灵表：8 列 x 4 行（down, left, right, up），每帧 32x40，脚底锚点 (16, 39)。

const ROWS := {"down": 0, "left": 1, "right": 2, "up": 3}
const DIRS := {"down": Vector2.DOWN, "left": Vector2.LEFT, "right": Vector2.RIGHT, "up": Vector2.UP}

var rm: Dictionary = {}          # root_motion_px[dir] -> 8 个位移
var anim_fps := 12.5
var dir := "down"
var frame := 0
var acc := 0.0
var moving := false
var blocked_time := 0.0           # 连续被静止物体（楼、道具）挡住的时间
var waiting_time := 0.0           # 被人/车挡住、原地等待的时间
var spr: Sprite2D
var walk_tex: Texture2D
var idle_tex: Texture2D          # 站立帧：4 帧横排（down/left/right/up），双脚着地
var run_tex: Texture2D           # 跑步帧（可选）：布局同行走
var walk_rm: Dictionary = {}
var walk_fps := 12.5
var run_rm: Dictionary = {}
var run_fps := 14.0
var running := false             # 当前是否在跑
var nframes := 8                 # 当前动画每行帧数（行走 8；跑步表可以是 16）
var run_n := 8


func setup(tex: Texture2D, motion: Dictionary, fps: float) -> void:
	rm = motion
	anim_fps = fps
	walk_rm = motion
	walk_fps = fps
	var sh := Sprite2D.new()      # 脚下影子
	var si := Image.create(14, 5, false, Image.FORMAT_RGBA8)
	for y in 5:
		for x in 14:
			var dx := (x - 6.5) / 7.0
			var dy := (y - 2.0) / 2.5
			if dx * dx + dy * dy < 1.0:
				si.set_pixel(x, y, Color(0.1, 0.08, 0.14, 0.32))
	sh.texture = ImageTexture.create_from_image(si)
	sh.position = Vector2(1, -1)
	sh.z_index = -1
	add_child(sh)
	spr = Sprite2D.new()
	walk_tex = tex
	spr.texture = tex
	spr.hframes = 8
	spr.vframes = 4
	spr.centered = false
	spr.offset = Vector2(-16, -39)
	add_child(spr)
	var cs := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = Vector2(10, 6)
	cs.shape = shape
	cs.position = Vector2(0, -3)
	add_child(cs)
	_update_frame()


## 每物理帧调用：want = 想走的方向名（"" = 站住）；run = 想跑（没有跑步帧时用快走代替）
func step_walk(want: String, delta: float, run: bool = false) -> void:
	if want == "":
		if running:          # 停下时回到行走表（站立帧照常）
			running = false
			rm = walk_rm
			anim_fps = walk_fps
			nframes = 8
		moving = false
		frame = 0
		acc = 0.0
		_update_frame()
		return
	if run != running:
		running = run
		var old_n := nframes
		if run and run_tex:
			rm = run_rm
			anim_fps = run_fps
			nframes = run_n
		elif run:
			rm = walk_rm
			anim_fps = walk_fps * 1.7
			nframes = 8
		else:
			rm = walk_rm
			anim_fps = walk_fps
			nframes = 8
		frame = int(frame * nframes / old_n) % nframes      # 走↔跑切换时接着同一个相位
	if want != dir:
		dir = want
		frame = 0
		acc = 0.0
	moving = true
	var left := delta * anim_fps      # 这一物理帧要走掉的"动画帧"数
	var hit := false
	while left > 0.0:
		var part := minf(left, 1.0 - acc)
		var step: float = float(rm[dir][frame]) if rm.has(dir) else 3.75
		var col := move_and_collide(DIRS[dir] * step * part)
		if col:
			hit = true
			if col.get_collider() is StaticBody2D:
				blocked_time += part / anim_fps
			else:
				waiting_time += part / anim_fps
			var rest := col.get_remainder().slide(col.get_normal())
			if rest.length() > 0.01:
				move_and_collide(rest)
		acc += part
		left -= part
		if acc >= 1.0 - 1e-6:
			acc = 0.0
			frame = (frame + 1) % nframes
	if not hit:
		blocked_time = 0.0
		waiting_time = 0.0
	_update_frame()


## 站着不动时换成站立帧（不再停在走路的中间帧上）
func set_idle(t: Texture2D) -> void:
	idle_tex = t
	_update_frame()


func _update_frame() -> void:
	if not spr:
		return
	if not moving and idle_tex:
		if spr.texture != idle_tex:
			spr.frame = 0
			spr.texture = idle_tex
			spr.hframes = 4
			spr.vframes = 1
		spr.frame = ROWS[dir]
	else:
		var want_tex: Texture2D = run_tex if (running and run_tex) else walk_tex
		if spr.texture != want_tex:
			spr.frame = 0
			spr.texture = want_tex
			spr.hframes = nframes
			spr.vframes = 4
		spr.frame = ROWS[dir] * nframes + frame


## 跑步帧：贴图 + 根运动 + 帧率（hero_run.json）
func set_run(t: Texture2D, motion: Dictionary, fps: float, frames: int = 8) -> void:
	run_n = frames
	run_tex = t
	run_rm = motion
	run_fps = fps
