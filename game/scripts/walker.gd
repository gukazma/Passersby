extends CharacterBody2D
## F 方案行走：动画固定帧率，身体只在换帧时按根运动前进（撞到东西沿墙滑）。
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


func setup(tex: Texture2D, motion: Dictionary, fps: float) -> void:
	rm = motion
	anim_fps = fps
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


## 每物理帧调用：want = 想走的方向名（"" = 站住）
func step_walk(want: String, delta: float) -> void:
	if want == "":
		moving = false
		frame = 0
		acc = 0.0
		_update_frame()
		return
	if want != dir:
		dir = want
		frame = 0
		acc = 0.0
	moving = true
	acc += delta * anim_fps
	while acc >= 1.0:
		acc -= 1.0
		var step: float = float(rm[dir][frame]) if rm.has(dir) else 3.75
		var motion: Vector2 = DIRS[dir] * step
		var col := move_and_collide(motion)
		if col:
			if col.get_collider() is StaticBody2D:
				blocked_time += 1.0 / anim_fps
			else:
				waiting_time += 1.0 / anim_fps
			var rest := col.get_remainder().slide(col.get_normal())
			if rest.length() > 0.01:
				move_and_collide(rest)
		else:
			blocked_time = 0.0
			waiting_time = 0.0
		frame = (frame + 1) % 8
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
		if spr.texture != walk_tex:
			spr.frame = 0
			spr.texture = walk_tex
			spr.hframes = 8
			spr.vframes = 4
		spr.frame = ROWS[dir] * 8 + frame
