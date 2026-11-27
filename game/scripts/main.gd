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
# ---- A1：美术风格 / 比例 / 镜头 / 时间 对比（设置存在 Engine meta 里，切换时重载场景也不丢）----
const STYLES := [["s1", "现状·彩色小镇"], ["s2", "岭南骑楼老街"], ["s3", "港台现代街巷"]]
const RATIOS := [["100", "100%（门比人略高）"], ["85", "85%（楼更矮、城更紧凑）"]]
const ZOOMS := [[Vector2i(480, 270), "近（×4）"], [Vector2i(640, 360), "中（×3）"], [Vector2i(960, 540), "远（×2）"]]
const TODS := [[Color(1.0, 0.97, 0.92), "白天"], [Color(1.0, 0.82, 0.66), "黄昏"], [Color(0.46, 0.48, 0.64), "夜晚（灯光在 B1 做）"]]
var cm: CanvasModulate
var hud: CanvasLayer
var hud_label: Label
var help_label: Label
var toast_label: Label
var toast_t := 0.0
var px_font: FontFile
var cam: Camera2D
var help_bg: ColorRect
var photo := false             # 拍照模式
var photo_zoom := 1
const PHOTO_FAR := Vector2i(1920, 1080)


static func opt(key: String, def):
	return Engine.get_meta(key) if Engine.has_meta(key) else def


func variant() -> String:
	return "%s_%s" % [STYLES[opt("style", 0)][0], RATIOS[opt("ratio", 0)][0]]
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
var trace_frames := false
var last_pf := -1
var next_trace := 0.0
var sig_t := 0.0
var fades: Array = []           # [sprite, x0, x1, top, origin]


func tex(name: String) -> Texture2D:
	if not tex_cache.has(name):
		var path := "res://assets/%s.png" % name
		if name == "ground" or name.begins_with("blocks/"):
			path = "res://assets/variants/%s/%s.png" % [variant(), name]
		var img := Image.load_from_file(ProjectSettings.globalize_path(path))
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
	for a in ([] if Engine.has_meta("args_done") else args):   # 截图/测试用（只在启动时生效一次）：--style=1 --ratio=0 --zoom=1 --tod=0 --pos=x,y --nohelp
		for k in ["style", "ratio", "zoom", "tod"]:
			if a.begins_with("--%s=" % k):
				Engine.set_meta(k, int(a.split("=")[1]))
		if a.begins_with("--pos="):
			var xy: PackedStringArray = a.split("=")[1].split(",")
			Engine.set_meta("keep_pos", Vector2(float(xy[0]), float(xy[1])))
	Engine.set_meta("args_done", true)
	if not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path("res://assets/variants/" + variant())):
		Engine.set_meta("style", 0)
		Engine.set_meta("ratio", 0)
	get_window().content_scale_size = ZOOMS[opt("zoom", 1)][0]
	city = JSON.parse_string(FileAccess.get_file_as_string("res://assets/variants/%s/city.json" % variant()))
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
	if FileAccess.file_exists("res://assets/hero_run.json"):
		var rj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/hero_run.json"))
		player.set_run(tex("hero_run"), rj["root_motion_px"], rj["anim_fps"])
	var st: Array = city["player"]["start"]
	player.global_position = Vector2(st[0], st[1])
	player.route = city["player"]["route"]
	player.autoplay = "--autoplay" in args
	player.main = self
	player.collision_layer = L_CHAR
	player.collision_mask = L_WORLD | L_CHAR | L_CAR      # 主角不受路中护栏限制：哪里都能过马路（NPC 仍走斑马线）
	world.add_child(player)
	cam = Camera2D.new()
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
	cm = CanvasModulate.new()
	cm.color = TODS[opt("tod", 0)][0]
	add_child(cm)
	if Engine.has_meta("keep_pos"):         # 只换风格时保留主角位置
		player.global_position = Engine.get_meta("keep_pos")
		Engine.remove_meta("keep_pos")
	player.reset_physics_interpolation()
	cam.force_update_scroll()
	cam.reset_smoothing()               # 镜头直接到位，不从起点滑过来
	_build_hud()
	trace = "--trace" in args
	trace_frames = "--trace_frames" in args       # 测试用：每个画面帧打印主角插值后的位置（查卡顿）
	player.auto_run = "--autorun" in args
	if "--photo" in args:          # 测试用：进拍照模式、拉到全景、存一张截图
		_photo(true)
		photo_zoom = ZOOMS.size()
		get_window().content_scale_size = PHOTO_FAR
		_update_hud()
		get_tree().create_timer(0.6).timeout.connect(_shot)
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
	var occ = b.get("occ")
	if occ is Array:              # 南排楼顶伸进后巷的东西（楼梯间、水箱）：跟南排楼一起排序，挡住后巷里的人
		var o := Sprite2D.new()
		o.texture = tex("blocks/" + b["img"] + "_occ")
		o.centered = false
		o.position = Vector2(b["x"], b["y"] + occ[2])
		o.offset = Vector2(0, occ[0] - occ[2])
		world.add_child(o)
		fades.append([o, float(b["x"]), float(b["x"] + b["w"]), float(b["y"] + b["alley"][1]), float(b["y"] + occ[2])])


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
	if not (e is InputEventKey and e.pressed and not e.echo):
		return
	match (e as InputEventKey).keycode:
		KEY_1, KEY_2, KEY_3:
			var i: int = (e as InputEventKey).keycode - KEY_1
			if i != opt("style", 0):
				_switch("style", i, true)
		KEY_R:
			_switch("ratio", (opt("ratio", 0) + 1) % RATIOS.size(), false)
		KEY_Z:
			if photo:      # 拍照模式多一档「全景（×1）」
				photo_zoom = (photo_zoom + 1) % (ZOOMS.size() + 1)
				get_window().content_scale_size = PHOTO_FAR if photo_zoom == ZOOMS.size() else ZOOMS[photo_zoom][0]
				_toast("镜头：" + ("全景（×1）" if photo_zoom == ZOOMS.size() else ZOOMS[photo_zoom][1]))
			else:
				Engine.set_meta("zoom", (opt("zoom", 1) + 1) % ZOOMS.size())
				get_window().content_scale_size = ZOOMS[opt("zoom", 1)][0]
				_toast("镜头：" + ZOOMS[opt("zoom", 1)][1])
		KEY_T:
			Engine.set_meta("tod", (opt("tod", 0) + 1) % TODS.size())
			cm.color = TODS[opt("tod", 0)][0]
			_toast("时间：" + TODS[opt("tod", 0)][1])
		KEY_H:
			if not photo:
				help_label.visible = not help_label.visible
				help_bg.visible = help_label.visible
				hud_label.get_parent().visible = help_label.visible
		KEY_P:
			_photo(not photo)
		KEY_ENTER, KEY_KP_ENTER, KEY_F12:
			if photo:
				_shot()
		KEY_TAB:
			if photo:
				return
			player.autoplay = not player.autoplay
			if player.autoplay:         # 从最近的路线点接着走
				var best := 0
				var bd := INF
				for i in player.route.size():
					var q: Array = player.route[i]
					var dd := player.global_position.distance_to(Vector2(q[0], q[1]))
					if dd < bd:
						bd = dd
						best = i
				player.ri = best
			_toast("自动巡游：" + ("开" if player.autoplay else "关"))
		KEY_ESCAPE:
			get_tree().quit()
	_update_hud()


## 拍照模式：隐藏界面、主角站住、方向键平移镜头、Z 切远近（多一档全景）、回车/F12 存截图到 截图/
func _photo(on: bool) -> void:
	photo = on
	player.frozen = on
	for n in [help_label, help_bg, hud_label.get_parent()]:
		n.visible = not on
	if on:
		photo_zoom = opt("zoom", 1)
		_toast("拍照模式：方向键移动镜头  Z 远近  回车 保存截图  P 退出")
	else:
		cam.offset = Vector2(0, -16)
		get_window().content_scale_size = ZOOMS[opt("zoom", 1)][0]
		_toast("退出拍照模式")


func _shot() -> void:
	toast_label.visible = false
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	toast_label.visible = true
	var dir := ProjectSettings.globalize_path("res://").path_join("../截图").simplify_path()
	DirAccess.make_dir_recursive_absolute(dir)
	var name := "我亦是行人_%s.png" % Time.get_datetime_string_from_system().replace(":", "-").replace("T", "_")
	img.save_png(dir.path_join(name))
	_toast("已保存 截图/" + name)


## 切换风格（同比例布局一样，保留主角位置）或比例（布局变了，回到起点）
func _switch(key: String, val: int, keep: bool) -> void:
	var old = opt(key, 0)
	Engine.set_meta(key, val)
	if not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path("res://assets/variants/" + variant())):
		Engine.set_meta(key, old)
		_toast("这个组合还没生成")
		return
	if keep:
		Engine.set_meta("keep_pos", player.global_position)
	Engine.set_meta("toast", ("风格：" + STYLES[opt("style", 0)][1]) if key == "style" else ("比例：" + RATIOS[opt("ratio", 0)][1]))
	get_tree().call_deferred("reload_current_scene")


func _build_hud() -> void:
	px_font = FontFile.new()
	px_font.load_dynamic_font(ProjectSettings.globalize_path("res://fonts/px.woff2"))
	px_font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	px_font.hinting = TextServer.HINTING_NONE
	px_font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	hud = CanvasLayer.new()
	add_child(hud)
	var bg := ColorRect.new()
	bg.color = Color(0.1, 0.07, 0.05, 0.62)
	bg.position = Vector2(4, 4)
	hud.add_child(bg)
	hud_label = _mk_label(Vector2(9, 6))
	bg.add_child(hud_label)
	hud_label.position = Vector2(5, 2)
	help_bg = ColorRect.new()
	help_bg.color = Color(0.1, 0.07, 0.05, 0.62)
	hud.add_child(help_bg)
	help_label = _mk_label(Vector2(9, 0))
	hud.add_child(help_label)
	toast_label = _mk_label(Vector2(0, 0))
	toast_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hud.add_child(toast_label)
	if Engine.has_meta("toast"):
		_toast(Engine.get_meta("toast"))
		Engine.remove_meta("toast")
	_update_hud()


func _mk_label(pos: Vector2) -> Label:
	var l := Label.new()
	l.position = pos
	l.add_theme_font_override("font", px_font)
	l.add_theme_font_size_override("font_size", 12)
	l.add_theme_color_override("font_color", Color8(250, 240, 222))
	l.add_theme_color_override("font_outline_color", Color8(30, 20, 14))
	l.add_theme_constant_override("outline_size", 2)
	return l


func _update_hud() -> void:
	if hud_label == null:
		return
	var vs: Vector2i = get_window().content_scale_size
	var k := maxf(1.0, roundf(vs.x / 640.0))      # 远镜头时界面按整数倍放大，字不会变小
	hud.scale = Vector2(k, k)
	vs = Vector2i(roundi(vs.x / k), roundi(vs.y / k))
	hud_label.text = "A1.1 美术风格与比例\n风格[1/2/3] %s\n比例[R] %s\n镜头[Z] %s   时间[T] %s" % [STYLES[opt("style", 0)][1], RATIOS[opt("ratio", 0)][1], ZOOMS[opt("zoom", 1)][1], TODS[opt("tod", 0)][1]]
	var bg := hud_label.get_parent() as ColorRect
	bg.size = hud_label.get_minimum_size() + Vector2(10, 4)
	help_label.text = "方向键 走  Shift 跑  空格 交互  P 拍照  Tab 巡游  H 隐藏  Esc 退出"
	help_label.position = Vector2(9, vs.y - 18)
	help_bg.position = Vector2(4, vs.y - 19)
	help_bg.size = help_label.get_minimum_size() + Vector2(10, 2)
	toast_label.size = Vector2(vs.x, 16)
	toast_label.position = Vector2(0, 40)


func _toast(msg: String) -> void:
	if toast_label == null:
		return
	toast_label.text = msg
	toast_t = 2.0


func _process(delta: float) -> void:
	t += delta
	if photo:
		var v := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
		var sp := 160.0 * (3.0 if Input.is_key_pressed(KEY_SHIFT) else 1.0)
		cam.offset += v * sp * delta
		var ws: Array = city["world"]
		var half := Vector2(get_window().content_scale_size) / 2.0      # 别推出地图边（不然往回按会"卡住"）
		var c := (player.global_position + cam.offset).clamp(half, Vector2(ws[0], ws[1]) - half)
		cam.offset = c - player.global_position
	if toast_label != null:
		toast_t -= delta
		toast_label.modulate.a = clampf(toast_t / 0.4, 0.0, 1.0)
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
	if trace_frames and Engine.get_physics_frames() != last_pf:
		last_pf = Engine.get_physics_frames()
		var o: Vector2 = player.global_position
		print("F %.4f %.3f %.3f %s %d" % [t, o.x, o.y, player.dir, player.frame])
	if trace and t >= next_trace:
		next_trace += 2.0
		var p := player.global_position
		var stopped := 0
		for c in cars:
			if c.stopped > 0.0 or c.red:
				stopped += 1
		print("t=%.0f player=%d,%d route=%d/%d blocked=%.1f wait=%.1f phase=%s cars_stopped=%d" % [t, p.x, p.y, player.ri, player.route.size(), player.blocked_time, player.waiting_time, ph, stopped])
