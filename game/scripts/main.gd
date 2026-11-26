extends Node2D
## v4：按 assets/city.json 搭城市。街区 = AI 整块图（地面层 + 后排/前排两个 y 排序层 + 碰撞块），
## 道路程序画；道具、车（红绿灯）、NPC（对话）、鸽子、环境效果。
## 运行参数（-- 之后）：--autoplay 按路线自动走；--duration=秒；--trace 打印状态。

const WalkerPlayer := preload("res://scripts/player.gd")
const WalkerNPC := preload("res://scripts/npc.gd")
const Car := preload("res://scripts/car.gd")
const Bird := preload("res://scripts/bird.gd")
const Ambient := preload("res://scripts/ambient.gd")
const Bubble := preload("res://scripts/bubble.gd")

const L_WORLD := 1
const L_CHAR := 2
const L_CAR := 4
const L_CURB := 8

var city: Dictionary
var tex_cache := {}
var world: Node2D
var player: CharacterBody2D
var npcs: Array = []
var cars: Array = []
var vendings: Array = []
var lights: Array = []          # [节点, 轴 "ew"/"ns"]
var inters: Array = []          # 路口 Rect2
var duration := 0.0
var t := 0.0
var trace := false
var next_trace := 0.0
var sig_t := 0.0
var fades: Array = []           # [sprite, x0, x1, top, origin]


func tex(name: String) -> Texture2D:
	if not tex_cache.has(name):
		var img := Image.load_from_file(ProjectSettings.globalize_path("res://assets/%s.png" % name))
		tex_cache[name] = ImageTexture.create_from_image(img)
	return tex_cache[name]


## 站立帧（<name>_idle.png，没有就返回 null = 仍用第 0 帧）
func idle_tex(name: String) -> Texture2D:
	if FileAccess.file_exists("res://assets/%s_idle.png" % name):
		return tex(name + "_idle")
	return null


## 红绿灯：东西绿 7 s → 全红 1 s → 南北绿 7 s → 全红 1 s
func phase() -> String:
	var k := fmod(sig_t, 16.0)
	if k < 7.0:
		return "ew"
	if k < 8.0:
		return ""
	if k < 15.0:
		return "ns"
	return ""


## 车问能不能往前开：快到路口停止线、本方向红灯 → 停
func car_may_go(c: Node2D, dir: String, half_len: float) -> bool:
	var axis := "ew" if dir in ["left", "right"] else "ns"
	if phase() == axis:
		return true
	var p := c.global_position
	for r in inters:
		var rr: Rect2 = r
		var front := 0.0
		var dist := 1e9
		if dir == "right" and absf(p.y - rr.get_center().y) < rr.size.y / 2.0:
			front = p.x + half_len
			dist = rr.position.x - front
		elif dir == "left" and absf(p.y - rr.get_center().y) < rr.size.y / 2.0:
			front = p.x - half_len
			dist = front - rr.end.x
		elif dir == "down" and absf(p.x - rr.get_center().x) < rr.size.x / 2.0:
			front = p.y + half_len
			dist = front - 0.0
			dist = rr.position.y - front
		elif dir == "up" and absf(p.x - rr.get_center().x) < rr.size.x / 2.0:
			front = p.y - half_len
			dist = front - rr.end.y
		if dist > 0.0 and dist < 16.0:
			return false
	return true


func say(who: Node2D, text: String, secs: float = 2.8) -> void:
	for c in who.get_children():
		if c.has_meta("life"):
			c.queue_free()
	who.add_child(Bubble.make(text, secs))


## 玩家按确认键 / 自动巡游的交互
func interact(target: String = "") -> void:
	var p := player.global_position
	if target.begins_with("talk:"):
		_talk(npcs[int(target.split(":")[1])])
		return
	if target == "buy" or target == "":
		for v in vendings:
			if (v as Vector2).distance_to(p) < 30.0:
				say(player, ["叮！买到一瓶汽水", "叮！买到一杯热咖啡", "叮！买到一瓶矿泉水"][randi() % 3])
				return
	if target == "" :
		var best: Node2D = null
		var bd := 30.0
		for n in npcs:
			var d := (n as Node2D).global_position.distance_to(p)
			if d < bd:
				bd = d
				best = n
		if best:
			_talk(best)
	elif target.begins_with("say:"):
		say(player, target.substr(4))


func _talk(n: Node2D) -> void:
	var lines: Array = n.get_meta("lines", ["你好呀！"])
	n.face_to(player.global_position)
	n.pause = 3.2
	say(n, lines[n.get_meta("li", 0) % lines.size()], 3.0)
	n.set_meta("li", n.get_meta("li", 0) + 1)


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	city = JSON.parse_string(FileAccess.get_file_as_string("res://assets/city.json"))
	var ws: Array = city["world"]
	var ground := Sprite2D.new()
	ground.texture = tex("ground")
	ground.centered = false
	ground.z_index = -100
	add_child(ground)
	world = Node2D.new()
	world.y_sort_enabled = true
	add_child(world)
	for b in city.get("blocks", []):
		_block(b)
	for p in city["props"]:
		_static(p)
	for r in city.get("solids", []):
		_rect_body(r, L_WORLD)
	for r in city.get("barriers", []):
		_rect_body(r, L_CURB)
	for poly in city.get("polys", []):
		var body := StaticBody2D.new()
		body.collision_layer = L_WORLD
		var cp := CollisionPolygon2D.new()
		var pts := PackedVector2Array()
		for q in poly:
			pts.append(Vector2(q[0], q[1]))
		cp.polygon = pts
		body.add_child(cp)
		add_child(body)
	_rect_body([-20, -20, ws[0] + 40, 20], L_WORLD)
	_rect_body([-20, ws[1], ws[0] + 40, 20], L_WORLD)
	_rect_body([-20, 0, 20, ws[1]], L_WORLD)
	_rect_body([ws[0], 0, 20, ws[1]], L_WORLD)
	for r in city.get("intersections", []):
		inters.append(Rect2(r[0], r[1], r[2], r[3]))
	for v in city.get("vendings", []):
		vendings.append(Vector2(v[0], v[1]))
	for c in city["cars"]:
		_car(c)
	var motions := {}
	var kinds := ["hero"]
	for n in city["npcs"]:
		if not n["type"] in kinds:
			kinds.append(n["type"])
	for n in kinds:
		motions[n] = JSON.parse_string(FileAccess.get_file_as_string("res://assets/%s.json" % n))
	for i in city["npcs"].size():
		var n: Dictionary = city["npcs"][i]
		var npc := CharacterBody2D.new()
		npc.set_script(WalkerNPC)
		var m: Dictionary = motions[n["type"]]
		npc.setup(tex(n["type"]), m["root_motion_px"], m["anim_fps"])
		npc.set_idle(idle_tex(n["type"]))
		npc.path = n["path"]
		if n.has("idle"):
			npc.idle_dir = n["idle"]
		npc.set_meta("lines", n.get("lines", ["你好呀！", "今天天气真好。"]))
		npc.rng.seed = 100 + i
		npc.global_position = Vector2(n["path"][0][0], n["path"][0][1])
		npc.collision_layer = L_CHAR
		npc.collision_mask = L_WORLD | L_CHAR | L_CAR | L_CURB
		world.add_child(npc)
		npcs.append(npc)
	player = CharacterBody2D.new()
	player.set_script(WalkerPlayer)
	var hm: Dictionary = motions["hero"]
	player.setup(tex("hero"), hm["root_motion_px"], hm["anim_fps"])
	player.set_idle(idle_tex("hero"))
	var st: Array = city["player"]["start"]
	player.global_position = Vector2(st[0], st[1])
	player.route = city["player"]["route"]
	player.autoplay = "--autoplay" in args
	player.main = self
	player.collision_layer = L_CHAR
	player.collision_mask = L_WORLD | L_CHAR | L_CAR | L_CURB
	world.add_child(player)
	var cam := Camera2D.new()
	cam.position_smoothing_enabled = true
	cam.position_smoothing_speed = 4.0
	cam.limit_left = 0
	cam.limit_top = 0
	cam.limit_right = int(ws[0])
	cam.limit_bottom = int(ws[1])
	cam.offset = Vector2(0, -16)
	player.add_child(cam)
	cam.make_current()
	var bird_frames: Array[ImageTexture] = Bird.make_frames()
	var scarers: Array = [player] + npcs
	for f in city.get("birds", []):
		var r := RandomNumberGenerator.new()
		r.seed = int(f["x"]) * 7 + int(f["y"])
		for i in int(f["n"]):
			var b := Node2D.new()
			b.set_script(Bird)
			b.frames = bird_frames
			b.position = Vector2(f["x"] + r.randf_range(-24, 24), f["y"] + r.randf_range(-10, 10)).round()
			b.rng.seed = r.randi()
			b.watch = scarers
			world.add_child(b)
	var amb := Node2D.new()
	amb.set_script(Ambient)
	amb.z_index = -50
	add_child(amb)
	var fp: Array = city.get("fountain", [])
	amb.setup(city.get("pond", [0, 0, 0, 0]), float(city.get("river_y", ws[1] - 68)), Vector2(ws[0], ws[1]),
		Vector2(fp[0], fp[1]) if fp.size() == 2 else Vector2.INF)
	var cm := CanvasModulate.new()
	cm.color = Color(1.0, 0.97, 0.92)
	add_child(cm)
	trace = "--trace" in args
	for a in args:
		if a.begins_with("--duration="):
			duration = float(a.split("=")[1])


## 街区：整张图铺地面层；后排、前排各一个 y 排序层（原点 = 各自墙脚）
func _block(b: Dictionary) -> void:
	var t2 := tex("blocks/" + b["img"])
	var g := Sprite2D.new()
	g.texture = t2
	g.centered = false
	g.position = Vector2(b["x"], b["y"])
	g.z_index = -90
	add_child(g)
	for part in b["parts"]:   # [y0, y1, origin]（相对街区图顶）
		var s := Sprite2D.new()
		s.texture = t2
		s.centered = false
		s.region_enabled = true
		s.region_rect = Rect2(0, part[0], t2.get_width(), part[1] - part[0])
		s.position = Vector2(b["x"], b["y"] + part[2])
		s.offset = Vector2(0, part[0] - part[2])
		world.add_child(s)
		fades.append([s, float(b["x"]), float(b["x"] + b["w"]), float(b["y"] + part[0]), float(b["y"] + part[2])])


func _rect_body(r: Array, layer: int) -> void:
	var body := StaticBody2D.new()
	body.collision_layer = layer
	body.collision_mask = 0
	var cs := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(r[2], r[3])
	cs.shape = rect
	cs.position = Vector2(r[0] + r[2] / 2.0, r[1] + r[3] / 2.0)
	body.add_child(cs)
	add_child(body)


func _static(d: Dictionary) -> void:
	var body := StaticBody2D.new()
	body.position = Vector2(d["x"], d["y"])
	body.collision_layer = L_WORLD
	body.collision_mask = 0
	var t2 := tex(d["sprite"])
	var spr := Sprite2D.new()
	spr.texture = t2
	spr.centered = false
	spr.offset = Vector2(-round(t2.get_width() / 2.0), -t2.get_height())
	spr.flip_h = bool(d.get("flip", false))
	body.add_child(spr)
	var foot: Array = d["foot"]
	if foot[0] > 0:
		var cs := CollisionShape2D.new()
		var rect := RectangleShape2D.new()
		rect.size = Vector2(foot[0], foot[1])
		cs.shape = rect
		cs.position = Vector2(0, -float(foot[1]) / 2.0)
		body.add_child(cs)
	if d.has("light"):            # 红绿灯：灯头上叠一个会变色的点
		var dot := ColorRect.new()
		dot.size = Vector2(3, 3)
		dot.position = Vector2(-1, -t2.get_height() + int(d["light"][1]))
		body.add_child(dot)
		lights.append([dot, d["light"][0]])
	world.add_child(body)


func _car(c: Dictionary) -> void:
	var car := AnimatableBody2D.new()
	car.set_script(Car)
	var tx := {"right": tex(c["type"] + "_right"), "down": tex(c["type"] + "_down"), "up": tex(c["type"] + "_up")}
	car.collision_layer = L_CAR
	car.collision_mask = 0
	car.city = self
	car.setup(c["pts"], tx, float(c["speed"]), bool(c["loop"]))
	world.add_child(car)
	cars.append(car)


func _unhandled_input(e: InputEvent) -> void:
	if e.is_action_pressed("ui_accept"):
		interact("")


func _process(delta: float) -> void:
	t += delta
	sig_t += delta
	if duration > 0.0 and t >= duration:
		get_tree().quit()
	var pp := player.global_position
	for f in fades:
		# 人在这排楼"后面"（脚在墙脚以北、身体和这排楼的画面有重叠）→ 楼半透明
		var behind: bool = pp.y < f[4] and pp.y > f[3] - 8.0 and pp.x > f[1] and pp.x < f[2]
		var spr: Sprite2D = f[0]
		spr.modulate.a = move_toward(spr.modulate.a, 0.42 if behind else 1.0, delta * 3.0)
	var ph := phase()
	for l in lights:
		(l[0] as ColorRect).color = Color8(90, 230, 110) if ph == l[1] else Color8(240, 70, 60)
	if trace and t >= next_trace:
		next_trace += 2.0
		var p := player.global_position
		var stopped := 0
		for c in cars:
			if c.stopped > 0.0 or c.red:
				stopped += 1
		print("t=%.0f player=%d,%d route=%d/%d blocked=%.1f wait=%.1f phase=%s cars_stopped=%d" % [t, p.x, p.y, player.ri, player.route.size(), player.blocked_time, player.waiting_time, ph, stopped])
