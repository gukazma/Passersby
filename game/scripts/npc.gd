extends "res://scripts/walker.gd"
## NPC：沿人行道上的路点循环走；被挡住就停一会儿，再掉头。

var path: Array = []
var pidx := 0
var pause := 0.0
var rng := RandomNumberGenerator.new()
var idle_dir := ""          # 非空 = 站着不走（聊天/张望），偶尔转身
var turn_t := 0.0


func face_to(p: Vector2) -> void:
	var d := p - global_position
	if absf(d.x) >= absf(d.y):
		dir = "right" if d.x > 0 else "left"
	else:
		dir = "down" if d.y > 0 else "up"
	turn_t = 3.0
	_update_frame()


func _physics_process(delta: float) -> void:
	if idle_dir != "" and pause > 0.0:
		pause -= delta
		_update_frame()
		return
	if idle_dir != "":
		if dir != idle_dir and turn_t <= 0.0:
			dir = idle_dir
		turn_t -= delta
		if turn_t < -rng.randf_range(4.0, 9.0):          # 偶尔转头看一眼别处，再转回来
			dir = ["down", "left", "right"][rng.randi() % 3]
			turn_t = 1.2
		step_walk("", delta)
		return
	if path.is_empty():
		return
	if pause > 0.0:
		pause -= delta
		moving = false
		frame = 0
		_update_frame()
		return
	var p: Array = path[pidx]
	var d := Vector2(p[0], p[1]) - global_position
	if d.length() < 3.0:
		pidx = (pidx + 1) % path.size()
		if rng.randf() < 0.25:
			pause = rng.randf_range(0.5, 2.0)   # 偶尔驻足
		return
	if blocked_time > 0.8 or waiting_time > 0.8:   # 被挡住：等一下，然后往回走
		blocked_time = 0.0
		waiting_time = 0.0
		pause = 0.6
		# 掉头：目标改成上一个路过的点（反转后它的下标 = size - pidx）
		path.reverse()
		pidx = (path.size() - pidx) % path.size()
		return
	var want := ""
	if absf(d.x) >= absf(d.y):
		want = "right" if d.x > 0 else "left"
	else:
		want = "down" if d.y > 0 else "up"
	step_walk(want, delta)
