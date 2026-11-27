extends "res://scripts/walker.gd"
## 玩家：方向键走，按住 Shift 跑；--autoplay 时按 route 自动走（录演示用）。

var route: Array = []      # [[x, y, wait_s], ...]，相邻点轴对齐
var ri := 0
var wait := 0.0
var autoplay := false
var detour := Vector2.INF   # 被人/车挡住时的临时让路点
var main: Node = null      # 主场景（交互、红绿灯）
var frozen := false        # 拍照模式时主角不动
var auto_run := false      # 测试用：自动巡游时跑


func _physics_process(delta: float) -> void:
	var want := ""
	if frozen:
		step_walk("", delta)
		return
	if autoplay:
		want = _route_dir(delta)
	else:
		var v := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		if v != Vector2.ZERO:
			if absf(v.x) > absf(v.y):
				want = "right" if v.x > 0 else "left"
			else:
				want = "down" if v.y > 0 else "up"
	step_walk(want, delta, auto_run if autoplay else Input.is_key_pressed(KEY_SHIFT))


func _route_dir(delta: float) -> String:
	if ri >= route.size():
		return ""
	if wait > 0.0:
		wait -= delta
		return ""
	if detour != Vector2.INF:
		var dd := detour - global_position
		if dd.length() < 3.0 or blocked_time > 0.4:
			detour = Vector2.INF
			blocked_time = 0.0
		else:
			return _axis_dir(dd)
	var p: Array = route[ri]
	var target := Vector2(p[0], p[1])
	var d := target - global_position
	if d.length() < 3.0:
		var act: String = str(p[4]) if p.size() > 4 else ""
		if act.begins_with("wait_") and main != null and main.phase() != act.substr(5):
			return ""          # 等绿灯
		blocked_time = 0.0
		wait = p[2] if p.size() > 2 else 0.0
		if act != "" and not act.begins_with("wait_") and main != null:
			main.interact(act)
		ri += 1
		return ""
	if p.size() > 3 and blocked_time > float(p[3]):   # 路线里特意安排的"撞上去"：撞够了就走下一个点
		blocked_time = 0.0
		wait = p[2]
		ri += 1
		return ""
	if (p.size() <= 3 and blocked_time > 0.5) or waiting_time > 1.2:   # 意外被挡：往空的一侧让一下
		blocked_time = 0.0
		waiting_time = 0.0
		var along := Vector2(signf(d.x), 0) if absf(d.x) >= absf(d.y) else Vector2(0, signf(d.y))
		var perp := Vector2(-along.y, along.x)
		for side in [perp * 14.0, -perp * 14.0, perp * 28.0, -perp * 28.0]:
			if not test_move(global_transform, side):
				detour = global_position + side
				break
		return ""
	return _axis_dir(d)


func _axis_dir(d: Vector2) -> String:
	# 两个方向都有偏差时先把小的那个走正（贴回设计的行走线），再走大的
	var ax := absf(d.x) >= absf(d.y)
	if absf(d.x) > 2.5 and absf(d.y) > 2.5:
		ax = not ax
	if ax:
		return "right" if d.x > 0 else "left"
	return "down" if d.y > 0 else "up"
