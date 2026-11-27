extends "res://side/actor.gd"
## 街上/室内的居民：按 loop 日程行动，走路用自己的步态（char.json 里各自的动画和根运动）。
## loop 指令：["walk", x, y] 走到点；["wait", 秒]；["face", "left|right|front|back"]；["say", "文字", 秒]；
##           ["enter", 门id] 走到门前→背面进门消失；["inside", 秒] 在店里待着；["exit", 门id] 从门里出来（正面）；
##           ["special", 动画名, 秒] 坐、干活、吃面；["goto", 序号]
## 玩家靠近会打招呼（greet），按空格对话时停下来、转身面对玩家（talk）。

var loop: Array = []
var step_i := 0
var t := 0.0
var target := Vector2.ZERO
var talking := false
var greet := ""
var greet_cd := 0.0
var talk: Array = []
var mood := "neutral"             # happy / neutral / tired / busy / annoyed / sleepy
var scene_ref: Node = null       # 所在场景（查门的位置）
var say_cb: Callable             # 冒气泡：say_cb.call(self, text, secs)
var player_ref: Node2D = null
var main_ref: Node = null        # 主控（查座位、狗、隐藏家具）
var using_spot: Dictionary = {}


func setup_brain(cfg: Dictionary) -> void:
	loop = cfg.get("loop", [])
	greet = cfg.get("greet", "")
	talk = cfg.get("talk", [])
	mood = cfg.get("mood", "neutral")
	speed_scale = float(cfg.get("speed_scale", 1.0))
	if cfg.has("special"):
		play_special(cfg["special"])
	if cfg.has("face"):
		_face(cfg["face"])


func _face(f: String) -> void:
	match f:
		"left":
			facing = -1; view = "side"
		"right":
			facing = 1; view = "side"
		_:
			view = f
	if special == "":
		_play("idle_" + view if anims.has("idle_" + view) else "idle_side")
	_update_frame()


## 被摸（狗）：转向对方，播开心动画
func petted_by(who: Node2D, secs: float) -> void:
	talking = true
	mood = "happy"
	facing = 1 if who.position.x > position.x else -1
	view = "side"
	if anims.has("happy"):
		play_special("happy")
	var tw := create_tween()
	tw.tween_interval(secs)
	tw.tween_callback(func(): stop_special(); talking = false)


func mood_face() -> String:
	return {"happy": "happy", "tired": "sad", "busy": "surprised", "annoyed": "angry", "sleepy": "sad"}.get(mood, "neutral")


func face_to(p: Vector2) -> void:
	facing = 1 if p.x > position.x else -1
	view = "side"
	if special == "":
		_play("idle_side")
	_update_frame()


func tick(delta: float) -> void:
	if talking or loop.is_empty():
		if special == "":
			drive(Vector2.ZERO, false, delta)
		return
	greet_cd = maxf(0.0, greet_cd - delta)
	if player_ref and greet != "" and greet_cd == 0.0 and visible and not hidden_in_door:
		var d := player_ref.position - position
		if absf(d.x) < 70 and absf(d.y) < 30:
			say_cb.call(self, greet, 2.0)
			greet_cd = 25.0
	var c: Array = loop[step_i % loop.size()]
	match c[0]:
		"walk":
			if walk_to(Vector2(c[1], c[2]), delta):
				_next()
		"wait":
			drive(Vector2.ZERO, false, delta)
			t += delta
			if t >= float(c[1]):
				_next()
		"face":
			_face(c[1]); _next()
		"say":
			say_cb.call(self, c[1], float(c[2]) if c.size() > 2 else 2.5); _next()
		"special":
			if special == "":
				play_special(c[1]); t = 0.0
			t += delta
			if t >= float(c[2]):
				stop_special(); _next()
		"enter":
			var dd: Dictionary = scene_ref.door_by_id(c[1])
			var dx: float = (dd["x0"] + dd["x1"]) / 2.0
			var tgt := Vector2(dx, band.x + 2)
			var d := tgt - position
			if absf(d.x) > 2.0 or absf(d.y) > 1.5:
				walk_to(tgt, delta)
			else:
				view = "back"; _play("walk_back" if anims.has("walk_back") else "idle_side")
				t += delta
				modulate.a = clampf(1.0 - t / 0.5, 0.0, 1.0)
				position.y -= 6.0 * delta
				_advance(delta, true)
				if t >= 0.5:
					hidden_in_door = true; visible = false; _next()
		"inside":
			t += delta
			if t >= float(c[1]):
				_next()
		"exit":
			var dd: Dictionary = scene_ref.door_by_id(c[1])
			if not visible:
				position = Vector2((dd["x0"] + dd["x1"]) / 2.0, band.x + 1)
				visible = true; hidden_in_door = false; modulate.a = 0.0; t = 0.0
			view = "front"; _play("walk_front" if anims.has("walk_front") else "idle_side")
			t += delta
			modulate.a = clampf(t / 0.4, 0.0, 1.0)
			position.y += 10.0 * delta
			_advance(delta, true)
			if t >= 0.5:
				modulate.a = 1.0; _next()
		"goto":
			step_i = int(c[1]) - 1; _next()
		"anim":
			# 原地动作：抽烟、看手机、大笑、蹦跳……循环动作按秒数，一次性动作播完为止
			if special == "":
				play_special(c[1]); t = 0.0
			t += delta
			if (anims[special]["loop"] and t >= float(c[2])) or special_done:
				stop_special(); _next()
		"use":
			# 走到座位 → 坐下（座位家具隐藏，坐姿精灵自带座位）→ 坐够时间起身
			var sp: Dictionary = main_ref.spot(c[1])
			if sp.is_empty():
				_next(); return
			if special == "":
				var tgt := Vector2(sp["x"], sp["y"])
				if main_ref.spot_taken(c[1], self):
					t += delta
					drive(Vector2.ZERO, false, delta)
					if t > 4.0: _next()
					return
				var d0 := tgt - position
				if absf(d0.x) > 2.0 or absf(d0.y) > 1.5:
					var before := stuck_log.size()
					walk_to(tgt, delta)
					if stuck_log.size() > before:
						_next()
					return
				facing = int(sp.get("face", 1)); view = "side"
				var an: String = c[3] if c.size() > 3 else sp.get("anim", "sit_bench")
				if not anims.has(an):
					_next(); return
				position = tgt
				main_ref.occupy(c[1], self)
				play_special(an); t = 0.0
			t += delta
			if t >= float(c[2]):
				stop_special(); main_ref.release(c[1]); _next()
		"pet":
			# 逗狗：走到狗面前蹲下摸它，狗开心摇尾巴
			var dog: Node2D = main_ref.find_npc(c[1])
			if dog == null or not anims.has("pet_dog"):
				_next(); return
			if special == "":
				var side := -1.0 if dog.position.x < position.x else 1.0
				var tgt := dog.position + Vector2(-side * 30.0, 0)
				var d := tgt - position
				if absf(d.x) > 3.0 or absf(d.y) > 2.0:
					var before2 := stuck_log.size()
					walk_to(tgt, delta, 3.0)
					if stuck_log.size() > before2:
						_next()
					return
				facing = int(side); view = "side"
				play_special("pet_dog"); t = 0.0
				dog.petted_by(self, float(c[2]))
			t += delta
			if t >= float(c[2]):
				stop_special(); _next()
		_:
			_next()


var stuck_t := 0.0
var detour := 0.0                 # 绕行时临时的纵深偏移
var stuck_log: Array = []         # 自动测试用：卡住记录


## 走向目标：到了返回 true。
## 「卡住」按有没有接近目标算（不是按动没动）：在障碍角上上下抖、原地来回也算卡住。
## 卡住 0.4 秒 → 往能过去的一侧绕行（_pick_detour）；1.6 秒 → 换另一侧；累计 3 秒仍到不了 → 记录并放弃（返回 true）
var best_d := INF
var last_goal := Vector2.INF


func walk_to(tgt: Vector2, delta: float, tol := 2.0) -> bool:
	var goal := Vector2(tgt.x, clampf(tgt.y + detour, band.x, band.y))
	var d := goal - position
	if absf(d.x) <= tol and absf(d.y) <= 1.5:
		if detour != 0.0:
			detour = 0.0
			return false
		stuck_t = 0.0
		best_d = INF
		return true
	if not goal.is_equal_approx(last_goal):
		last_goal = goal
		best_d = d.length()
	var want := Vector2(signf(d.x) if absf(d.x) > tol else 0.0, signf(d.y) if absf(d.y) > 1.5 else 0.0)
	drive(want, false, delta)
	var nd: float = (goal - position).length()
	if nd < best_d - 0.75:
		best_d = nd
		stuck_t = maxf(0.0, stuck_t - delta * 2.0)
	else:
		stuck_t += delta
		if stuck_t > 0.4 and detour == 0.0:
			detour = _pick_detour(tgt)
		elif stuck_t > 1.6 and absf(detour) < 30.0:
			detour = -detour * 1.6
		if stuck_t > 3.0:
			stuck_log.append({"t": Time.get_ticks_msec(), "pos": position, "tgt": tgt, "detour": detour, "want": want, "cur": cur, "cmd": str(loop[step_i % loop.size()]) if loop.size() else ""})
			stuck_t = 0.0
			detour = 0.0
			return true
	return false


func _next() -> void:
	step_i = (step_i + 1) % maxi(1, loop.size())
	t = 0.0


## 被挡时往哪边绕：往前看 24 px，上下 14–70 px 哪个位置能走（不在家具里、不出纵深带），选最近的
func _pick_detour(tgt: Vector2) -> float:
	var dirx: float = signf(tgt.x - position.x)
	for k in [14.0, 24.0, 36.0, 50.0, 70.0]:
		for sgn in [1.0, -1.0]:
			var y: float = position.y + k * sgn
			if y < band.x or y > band.y:
				continue
			var p := Vector2(position.x, y)
			if not _blocked(p) and not _blocked(p + Vector2(dirx * 24.0, 0)):
				return y - tgt.y
	return 22.0 if position.y < (band.x + band.y) / 2.0 else -22.0

