extends Node2D
## 街道的生气：时间与光影、影子、路灯/店灯（闪烁）、落叶与蒸汽（随风）、车流、鸟群（鸽子/麻雀/海鸥）、
## 定位音效（脚步按鞋子、车、动物、蒸汽，近大远小）和场景环境声。
## 由 side_main 在每次进场景时 setup()，每帧 tick()。数据：world.json 的 fx / fauna / traffic，sfx/sfx.json。

const DATA := "res://side_data/"

var M: Node                       # side_main
var scene: Node2D
var minutes := 16.0 * 60.0        # 游戏时间（分钟），默认下午 4 点
var day_speed := 2.0              # 游戏分钟 / 真实秒（12 分钟一天）
var fast := false                 # T 键：时间快进
var wind := 8.0                   # 横向风速（px/s），缓慢变化
var tt := 0.0
var cmod: CanvasModulate
var shadows: Array = []           # [Sprite2D, kind]
var lights: Array = []            # {node, base, kind:"lamp"|"shop"|"car", flicker}
var cars: Array = []              # {node, spr, data, v, dir, lane_y, lights:[]}
var car_cd := 3.0
var birds: Array = []             # 鸟：{node, spr, kind, state, vel, home, t, flock}
var flocks: Array = []
var emitters: Array = []
var sfx: Dictionary = {}
var streams: Dictionary = {}
var amb: AudioStreamPlayer
var pool: Array = []              # AudioStreamPlayer2D 池
var pool_i := 0
var steps_played := 0             # 自动测试用
var light_tex: Texture2D
var leaf_tex: Texture2D
var puff_tex: Texture2D
var interior := false
var veh: Dictionary = {}


func _ready() -> void:
	sfx = JSON.parse_string(FileAccess.get_file_as_string(DATA + "sfx/sfx.json"))
	veh = JSON.parse_string(FileAccess.get_file_as_string(DATA + "vehicles/vehicles.json"))
	light_tex = _radial(128, Color(1, 1, 1, 1))
	leaf_tex = _pix(["0110", "1111", "0110"], [Color("6f9a3a"), Color("a7c45a")])
	puff_tex = _pix(["0110", "1111", "1111", "0110"], [Color(1, 1, 1, 0.55), Color(1, 1, 1, 0.8)])
	amb = AudioStreamPlayer.new()
	amb.volume_db = -14.0
	add_child(amb)
	for i in 24:
		var p := AudioStreamPlayer2D.new()
		p.attenuation = 1.6
		p.max_distance = 400.0
		add_child(p)
		pool.append(p)


# ------------------------------------------------------------------ 工具
func _radial(size: int, c: Color) -> Texture2D:
	var g := Gradient.new()
	g.set_color(0, c)
	g.set_color(1, Color(c.r, c.g, c.b, 0.0))
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = size
	t.height = size
	return t


func _pix(rows: Array, cols: Array) -> Texture2D:
	var img := Image.create(rows[0].length(), rows.size(), false, Image.FORMAT_RGBA8)
	for y in rows.size():
		for x in rows[y].length():
			var ch: String = rows[y][x]
			if ch != "0":
				img.set_pixel(x, y, cols[(int(ch) - 1) % cols.size()])
	return ImageTexture.create_from_image(img)


func _stream(file: String) -> AudioStream:
	if not streams.has(file):
		var p := DATA + "sfx/" + file
		streams[file] = load(p) if ResourceLoader.exists(p) else null
	return streams[file]


## 定位播放一个音效（近大远小、左右声道随位置）
func play_at(name: String, pos: Vector2, vol_add := 0.0) -> void:
	if not sfx.has(name):
		return
	var e: Dictionary = sfx[name]
	var files: Array = e.get("files", [])
	if files.is_empty():
		return
	var st := _stream(files[randi() % files.size()])
	if st == null:
		return
	var p: AudioStreamPlayer2D = pool[pool_i]
	pool_i = (pool_i + 1) % pool.size()
	p.stream = st
	p.global_position = pos
	p.max_distance = float(e.get("max_distance_px", 400))
	p.volume_db = float(e.get("volume_db", -6.0)) + vol_add
	p.pitch_scale = randf_range(0.94, 1.06)
	p.play()


func _loop_player(name: String, pos: Vector2, parent: Node) -> AudioStreamPlayer2D:
	if not sfx.has(name):
		return null
	var e: Dictionary = sfx[name]
	var st := _stream(e["files"][0])
	if st == null:
		return null
	if "loop" in st:
		st.set("loop", true)
	var p := AudioStreamPlayer2D.new()
	p.stream = st
	p.max_distance = float(e.get("max_distance_px", 600))
	p.attenuation = 1.4
	p.volume_db = float(e.get("volume_db", -8.0))
	p.position = pos
	parent.add_child(p)
	p.play()
	return p


# ------------------------------------------------------------------ 进场景
func setup(main: Node, sc: Node2D) -> void:
	M = main
	scene = sc
	interior = sc.data.get("kind", "street") == "interior"
	shadows.clear(); lights.clear(); cars.clear(); birds.clear(); flocks.clear(); emitters.clear()
	if cmod and is_instance_valid(cmod):
		cmod.queue_free()
	cmod = CanvasModulate.new()
	sc.add_child(cmod)
	# 环境声
	var ambname: String = sfx.get("_scene_ambience", {}).get(sc.data.get("id", ""), "")
	if ambname != "" and sfx.has(ambname):
		var st := _stream(sfx[ambname]["files"][0])
		if st:
			if "loop" in st:
				st.set("loop", true)
			amb.stream = st
			amb.volume_db = float(sfx[ambname].get("volume_db", -14.0))
			amb.play()
	else:
		amb.stop()
	if not interior:
		_make_shadows()
	_make_lights()
	_make_fx()
	_make_fauna()
	car_cd = randf_range(1.0, 4.0)


func _make_shadows() -> void:
	## 楼排和高的道具（树、路灯、报亭、路牌）的影子：剪影压扁、翻到地面上，随太阳倾斜
	for L in scene.data.get("layers", []):
		var img: String = L["img"]
		if not (img.begins_with("row_") or img.begins_with("block")):
			continue
		var tex: Texture2D = load(scene.base + "/" + img) if ResourceLoader.exists(scene.base + "/" + img) else null
		if tex == null:
			continue
		var s := Sprite2D.new()
		s.texture = tex
		s.centered = false
		s.offset = Vector2(0, -tex.get_height())
		s.position = Vector2(float(L.get("x", 0)), float(L.get("y", 0)) + tex.get_height())
		s.modulate = Color(0.12, 0.07, 0.05, 0.0)
		s.z_index = -9
		scene.add_child(s)
		shadows.append([s, "row"])
	for P in scene.data.get("props", []):
		var nm: String = P["img"]
		if not (nm.begins_with("tree") or nm.contains("lamp") or nm.begins_with("kiosk") or nm.begins_with("post") or nm.begins_with("gate") or nm.begins_with("teakiosk")):
			continue
		var p: String = scene.base + "/" + nm
		if not ResourceLoader.exists(p):
			continue
		var tex: Texture2D = load(p)
		var s := Sprite2D.new()
		s.texture = tex
		s.centered = false
		s.offset = Vector2(-tex.get_width() / 2.0, -tex.get_height())
		s.position = Vector2(P["x"], P["y_foot"])
		s.modulate = Color(0.12, 0.07, 0.05, 0.0)
		s.z_index = -9
		scene.add_child(s)
		shadows.append([s, "prop"])


func _light(pos: Vector2, color: Color, scale: float, kind: String, flicker := false) -> void:
	var l := PointLight2D.new()
	l.texture = light_tex
	l.texture_scale = scale
	l.color = color
	l.energy = 0.0
	l.position = pos
	l.blend_mode = Light2D.BLEND_MODE_ADD
	scene.add_child(l)
	lights.append({"node": l, "kind": kind, "flicker": flicker, "ph": randf() * 10.0, "base": 1.0})


func _make_lights() -> void:
	var lamp_i := 0
	for P in scene.data.get("props", []):
		var nm: String = P["img"]
		if nm == "lamp.png" or nm == "slamp.png":
			var p: String = scene.base + "/" + nm
			var h := 190.0
			if ResourceLoader.exists(p):
				h = load(p).get_height()
			_light(Vector2(P["x"], P["y_foot"] - h + 16), Color(1.0, 0.82, 0.55), 1.6, "lamp", lamp_i == 1)
			lamp_i += 1
	for d in scene.data.get("doors", []):
		_light(Vector2((d["x0"] + d["x1"]) / 2.0, scene.band.x - 46), Color(1.0, 0.72, 0.42), 1.25, "shop")
	if interior:
		_light(Vector2(480, 250), Color(1.0, 0.85, 0.6), 4.0, "room")


func _particles(pos: Vector2, kind: String) -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.position = pos
	p.z_index = 40
	if kind == "leaves":
		p.texture = leaf_tex
		p.amount = 3
		p.lifetime = 7.0
		p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
		p.emission_rect_extents = Vector2(40, 22)
		p.gravity = Vector2(wind, 16)
		p.initial_velocity_min = 2.0
		p.initial_velocity_max = 8.0
		p.angular_velocity_min = -120.0
		p.angular_velocity_max = 120.0
		p.direction = Vector2(1, 1)
		p.spread = 60.0
		p.preprocess = 4.0
		p.z_index = 45
	else:   # steam：从锅里冒出、随风斜飘、越来越淡
		p.texture = puff_tex
		p.amount = 14
		p.lifetime = 2.6
		p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
		p.emission_rect_extents = Vector2(8, 2)
		p.direction = Vector2(0, -1)
		p.spread = 12.0
		p.initial_velocity_min = 10.0
		p.initial_velocity_max = 16.0
		p.gravity = Vector2(wind * 0.7, -4)
		p.scale_amount_min = 1.0
		p.scale_amount_max = 2.0
		var ramp := Gradient.new()
		ramp.set_color(0, Color(1, 1, 1, 0.75))
		ramp.set_color(1, Color(1, 1, 1, 0.0))
		p.color_ramp = ramp
		p.preprocess = 2.0
	scene.add_child(p)
	emitters.append([p, kind])
	return p


func _make_fx() -> void:
	for P in scene.data.get("props", []):
		if str(P["img"]).begins_with("tree"):
			var p: String = scene.base + "/" + str(P["img"])
			var h := 240.0
			if ResourceLoader.exists(p):
				h = load(p).get_height()
			_particles(Vector2(P["x"], P["y_foot"] - h * 0.72), "leaves")
	for f in M.world.get("fx", {}).get(scene.data.get("id", ""), []):
		if f["type"] == "steam":
			_particles(Vector2(f["x"], f["y"]), "steam")
			_loop_player("steam_hiss_loop", Vector2(f["x"], f["y"]), scene)


# ------------------------------------------------------------------ 鸟群
func _anim_sprite(cid: String) -> Dictionary:
	var cj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA + "chars/%s/char.json" % cid))
	var out := {}
	for k in cj["anims"]:
		var a: Dictionary = cj["anims"][k]
		var p := DATA + "chars/%s/%s" % [cid, a["file"]]
		out[k] = {"tex": load(p) if ResourceLoader.exists(p) else ImageTexture.create_from_image(Image.load_from_file(p)),
			"n": int(a["frames"]), "fps": float(a.get("fps", 8)), "fw": int(a["frame_w"]), "fh": int(a["frame_h"]),
			"o": a.get("origin", [a["frame_w"] / 2, a["frame_h"] - 1]), "loop": a.get("loop", true)}
	out["_speed"] = float(cj.get("fly_speed_px_s", 100))
	return out


func _bird(kind: String, pos: Vector2, flock: Dictionary, state: String) -> void:
	var node := Node2D.new()
	node.position = pos
	var spr := Sprite2D.new()
	spr.centered = false
	node.add_child(spr)
	scene.ysort.add_child(node)
	var b := {"node": node, "spr": spr, "kind": kind, "state": state, "vel": Vector2.ZERO, "t": randf() * 3.0,
		"anim": "", "f": 0.0, "flock": flock, "home": pos, "facing": 1 if randf() < 0.5 else -1}
	birds.append(b)
	_bset(b, flock["anims"].keys()[0] if state == "ground" else "fly_side")


func _bset(b: Dictionary, anim: String) -> void:
	var A: Dictionary = b["flock"]["anims"]
	if not A.has(anim):
		return
	if b["anim"] == anim:
		return
	b["anim"] = anim
	b["f"] = 0.0
	var a: Dictionary = A[anim]
	var spr: Sprite2D = b["spr"]
	spr.texture = a["tex"]
	spr.hframes = a["n"]
	spr.frame = 0


func _make_fauna() -> void:
	for fa in M.world.get("fauna", {}).get(scene.data.get("id", ""), []):
		var kind: String = fa["type"]
		var anims := _anim_sprite(kind)
		var flock := {"id": flocks.size(), "kind": kind, "anims": anims, "center": Vector2(fa["x"], fa.get("y", scene.band.y - 10)),
			"state": "ground" if fa.get("ground", true) else "sky", "t": 0.0, "landing": Vector2(fa["x"], fa.get("y", scene.band.y - 10)),
			"range": float(fa.get("range", 260)), "sky_y": float(fa.get("sky_y", 140))}
		flocks.append(flock)
		for i in int(fa.get("n", 5)):
			if flock["state"] == "ground":
				var gy: float = clampf(float(fa.get("y", scene.band.y - 10)) + randf_range(-10, 10), scene.band.x + 2, scene.band.y + 4)
				_bird(kind, Vector2(fa["x"] + randf_range(-40, 40), gy), flock, "ground")
			else:
				_bird(kind, Vector2(fa["x"] + randf_range(-120, 120), flock["sky_y"] + randf_range(-40, 40)), flock, "sky")


func _bird_tick(delta: float) -> void:
	var threats: Array = [M.player.position]
	for n in M.npcs:
		if n.visible and n.moving:
			threats.append(n.position)
	for c in cars:
		threats.append(c["node"].position)
	for fl in flocks:
		var fid: int = fl["id"]
		var members: Array = birds.filter(func(b): return b["flock"]["id"] == fid)
		if fl["state"] == "ground":
			var alarm := false
			for b in members:
				for tp in threats:
					if b["node"].position.distance_to(tp) < (90.0 if fl["kind"] != "sparrow" else 60.0):
						alarm = true
			if alarm:
				fl["state"] = "sky"
				fl["t"] = randf_range(7.0, 14.0)
				var away: float = -1.0 if M.player.position.x > fl["center"].x else 1.0
				fl["center"] = Vector2(fl["center"].x + away * 220.0, fl["sky_y"])
				for b in members:
					b["state"] = "takeoff"
					b["vel"] = Vector2(away * randf_range(30, 60), -randf_range(70, 110))
					_bset(b, "takeoff" if fl["anims"].has("takeoff") else "fly_side")
				play_at("pigeon_wings_takeoff" if fl["kind"] == "pigeon" else "sparrow_chirp", members[0]["node"].position)
		elif fl["state"] == "sky":
			fl["t"] -= delta
			# 在天上绕圈（徘徊中心缓慢移动），时间到了找地方落下（地面鸟）
			var cc: Vector2 = fl["center"]
			cc.x += sin(tt * 0.3 + fl["range"]) * 20.0 * delta
			fl["center"] = cc
			if fl["anims"].has("walk_peck") or fl["anims"].has("hop"):
				if fl["t"] <= 0.0:
					fl["state"] = "landing"
					var w: float = float(scene.width)
					fl["landing"] = Vector2(clampf(fl["center"].x + randf_range(-300, 300), 80, w - 80), randf_range(scene.band.x + 6, scene.band.y))
		for b in members:
			_bird_move(b, fl, delta)
		if fl["state"] == "landing" and members.all(func(b): return b["state"] == "ground"):
			fl["state"] = "ground"
			fl["center"] = fl["landing"]
		if fl["kind"] == "seagull" and randf() < delta * 0.25:
			play_at("seagull_call", fl["center"])
		if fl["kind"] == "pigeon" and fl["state"] == "ground" and randf() < delta * 0.12:
			play_at("pigeon_coo", fl["center"])
		if fl["kind"] == "sparrow" and randf() < delta * 0.2:
			play_at("sparrow_chirp", fl["center"])


func _bird_move(b: Dictionary, fl: Dictionary, delta: float) -> void:
	var node: Node2D = b["node"]
	var sp: float = fl["anims"]["_speed"]
	match b["state"]:
		"ground":
			b["t"] -= delta
			if b["t"] <= 0.0:
				b["t"] = randf_range(0.8, 2.5)
				var r := randf()
				if r < 0.45:
					b["vel"] = Vector2(randf_range(-14, 14), randf_range(-3, 3))
					b["facing"] = 1 if b["vel"].x >= 0 else -1
					_bset(b, "walk_peck" if fl["anims"].has("walk_peck") else ("hop" if fl["anims"].has("hop") else "idle_side"))
				elif r < 0.75 and fl["anims"].has("peck"):
					b["vel"] = Vector2.ZERO
					_bset(b, "peck")
				else:
					b["vel"] = Vector2.ZERO
					_bset(b, "idle_side" if fl["anims"].has("idle_side") else "stand")
			var np: Vector2 = node.position + b["vel"] * delta
			np.y = clampf(np.y, scene.band.x + 2, scene.band.y + 6)
			np.x = clampf(np.x, fl["center"].x - 70, fl["center"].x + 70)
			node.position = np
		"takeoff", "sky":
			# 简单鸟群：朝群中心、互相避开、保持速度
			var tgt: Vector2 = fl["center"] + Vector2(cos(tt * 0.7 + node.get_instance_id() % 7) * 90.0, sin(tt * 0.9 + node.get_instance_id() % 5) * 30.0)
			var acc: Vector2 = (tgt - node.position).normalized() * 90.0
			for o in birds:
				if o != b and o["flock"]["id"] == fl["id"]:
					var d: Vector2 = node.position - o["node"].position
					if d.length() < 14.0 and d.length() > 0.01:
						acc += d.normalized() * 60.0
			b["vel"] += acc * delta
			b["vel"] = b["vel"].limit_length(sp)
			node.position += b["vel"] * delta
			node.position.y = minf(node.position.y, scene.band.x - 20)
			b["facing"] = 1 if b["vel"].x >= 0 else -1
			if b["state"] == "takeoff" and node.position.y < fl["sky_y"] + 40:
				b["state"] = "sky"
			_bset(b, "glide" if (fl["anims"].has("glide") and absf(b["vel"].y) < 12.0 and randf() < 0.01) else "fly_side")
			if fl["state"] == "landing":
				b["state"] = "descend"
				b["home"] = fl["landing"] + Vector2(randf_range(-35, 35), randf_range(-6, 6))
		"descend":
			var d2: Vector2 = b["home"] - node.position
			if d2.length() < 4.0:
				node.position = b["home"]
				b["state"] = "ground"
				b["vel"] = Vector2.ZERO
				_bset(b, "idle_side" if fl["anims"].has("idle_side") else "stand")
			else:
				b["vel"] = b["vel"].lerp(d2.normalized() * minf(sp, d2.length() * 2.0), 0.08)
				node.position += b["vel"] * delta
				b["facing"] = 1 if b["vel"].x >= 0 else -1
				_bset(b, "land" if fl["anims"].has("land") and d2.length() < 40.0 else "fly_side")
	# 帧动画
	var a: Dictionary = fl["anims"][b["anim"]]
	b["f"] += delta * a["fps"]
	var fr := int(b["f"])
	if not a["loop"]:
		fr = mini(fr, a["n"] - 1)
	var spr: Sprite2D = b["spr"]
	spr.frame = fr % a["n"]
	var o: Array = a["o"]
	var mirror: bool = b["facing"] < 0
	spr.flip_h = mirror
	spr.offset = Vector2(-(a["fw"] - float(o[0])) if mirror else -float(o[0]), -float(o[1]))
	# 天上的鸟画在最前面（不参与地面排序）
	node.z_index = 60 if b["state"] != "ground" else 0


# ------------------------------------------------------------------ 车流
func _spawn_car() -> void:
	var ids: Array = veh.keys().filter(func(k): return not str(k).begins_with("_"))
	if ids.is_empty():
		return
	var id: String = ids[randi() % ids.size()]
	var d: Dictionary = veh[id]
	var p := DATA + "vehicles/" + str(d["file"])
	if not ResourceLoader.exists(p):
		return
	var dir := 1 if randf() < 0.5 else -1
	var lane_y := 500.0 if dir > 0 else 528.0       # 远车道向右、近车道向左
	var node := Node2D.new()
	var spr := Sprite2D.new()
	spr.texture = load(p)
	spr.hframes = int(d.get("frames", 1))
	spr.centered = false
	var o: Array = d.get("origin", [d["frame_w"] / 2, d["frame_h"] - 1])
	spr.flip_h = dir < 0
	spr.offset = Vector2(-(float(d["frame_w"]) - float(o[0])) if dir < 0 else -float(o[0]), -float(o[1]))
	node.add_child(spr)
	var sh := Sprite2D.new()      # 车底阴影
	sh.texture = _radial(64, Color(0.1, 0.06, 0.04, 0.5))
	sh.scale = Vector2(float(d.get("length_px", 280)) / 64.0 * 1.1, 0.18)
	sh.z_index = -1
	node.add_child(sh)
	var L: float = float(d.get("length_px", 280))
	var cam_l: float = M.cam.get_screen_center_position().x - 480.0
	node.position = Vector2(cam_l - L if dir > 0 else cam_l + 960.0 + L, lane_y)
	scene.ysort.add_child(node)
	var eng := _loop_player("car_engine_idle_loop", Vector2.ZERO, node)
	var car := {"node": node, "spr": spr, "d": d, "dir": dir, "v": float(d.get("typical_speed_px_s", 200)) * randf_range(0.85, 1.1),
		"vmax": 0.0, "f": 0.0, "lights": [], "passed": false, "eng": eng}
	car["vmax"] = car["v"]
	for kk in ["front", "rear"]:
		for lp in d.get("lights", {}).get(kk, []):
			var l := PointLight2D.new()
			l.texture = light_tex
			l.texture_scale = 0.35 if kk == "front" else 0.2
			l.color = Color(1.0, 0.9, 0.7) if kk == "front" else Color(1.0, 0.25, 0.2)
			l.energy = 0.0
			var lx: float = float(lp[0]) - float(o[0])
			if dir < 0:
				lx = -lx
			l.position = Vector2(lx, float(lp[1]) - float(o[1]))
			node.add_child(l)
			car["lights"].append(l)
	cars.append(car)


func _car_tick(delta: float) -> void:
	if interior:
		return
	car_cd -= delta
	if car_cd <= 0.0 and cars.size() < 3:
		car_cd = randf_range(4.0, 11.0)
		_spawn_car()
	var night := _night()
	var zx: Vector2 = M.crossing_zebra
	for c in cars.duplicate():
		var node: Node2D = c["node"]
		var L: float = float(c["d"].get("length_px", 280))
		var front: float = node.position.x + c["dir"] * L * 0.5
		var stop := false
		# 斑马线有人过马路：车在斑马线前停
		if zx != Vector2.ZERO:
			var gap: float = (zx.x - front) if c["dir"] > 0 else (front - zx.y)
			if gap > -20.0 and gap < 160.0:
				stop = true
		# 跟车：不追尾
		for o in cars:
			if o != c and o["dir"] == c["dir"]:
				var dist: float = (o["node"].position.x - node.position.x) * c["dir"]
				if dist > 0.0 and dist < L * 0.5 + float(o["d"].get("length_px", 280)) * 0.5 + 40.0:
					stop = true
		c["v"] = move_toward(c["v"], 0.0 if stop else c["vmax"], (400.0 if stop else 120.0) * delta)
		node.position.x += c["dir"] * c["v"] * delta
		c["f"] += delta * float(c["d"].get("fps_per_100px", 6)) * c["v"] / 100.0
		c["spr"].frame = int(c["f"]) % maxi(1, c["spr"].hframes)
		for l in c["lights"]:
			l.energy = night * 1.2
		if c["eng"]:
			c["eng"].pitch_scale = 0.8 + c["v"] / c["vmax"] * 0.4
		var cx: float = M.cam.get_screen_center_position().x
		if not c["passed"] and absf(node.position.x - cx) < 200.0:
			c["passed"] = true
			play_at("motorbike_passby" if c["d"].get("kind", "") == "motorbike" else ("bike_bell" if c["d"].get("kind", "") == "bike" else "car_passby"), node.position)
			if c["d"].get("kind", "") == "car" and randf() < 0.12:
				play_at("taxi_horn", node.position)
		if (c["dir"] > 0 and node.position.x > cx + 480.0 + L + 40.0) or (c["dir"] < 0 and node.position.x < cx - 480.0 - L - 40.0):
			node.queue_free()
			cars.erase(c)


# ------------------------------------------------------------------ 时间、光影
func _sun() -> Vector2:
	## x = 太阳从东到西（-1..1），y = 高度（0..1）
	var h := minutes / 60.0
	var k := clampf((h - 6.0) / 12.0, 0.0, 1.0)
	return Vector2(-cos(k * PI), sin(k * PI) if h > 6.0 and h < 18.0 else 0.0)


func _night() -> float:
	var h := minutes / 60.0
	if h >= 19.0 or h < 5.5:
		return 1.0
	if h >= 17.5:
		return (h - 17.5) / 1.5
	if h < 6.5:
		return 1.0 - (h - 5.5)
	return 0.0


func _tint() -> Color:
	var h := minutes / 60.0
	var keys := [[0.0, Color(0.30, 0.32, 0.46)], [5.0, Color(0.34, 0.34, 0.48)], [6.2, Color(0.95, 0.74, 0.64)], [8.0, Color(1, 0.98, 0.94)],
		[16.0, Color(1, 0.97, 0.92)], [17.8, Color(1.0, 0.8, 0.6)], [19.0, Color(0.62, 0.52, 0.6)], [20.5, Color(0.36, 0.36, 0.5)], [24.0, Color(0.30, 0.32, 0.46)]]
	for i in keys.size() - 1:
		if h >= keys[i][0] and h < keys[i + 1][0]:
			var t: float = (h - keys[i][0]) / (keys[i + 1][0] - keys[i][0])
			return (keys[i][1] as Color).lerp(keys[i + 1][1], t)
	return Color.WHITE


func clock_text() -> String:
	var h := int(minutes / 60.0) % 24
	var m := int(minutes) % 60
	return "%02d:%02d" % [h, m]


func tick(delta: float) -> void:
	tt += delta
	minutes = fmod(minutes + delta * day_speed * (12.0 if fast else 1.0), 1440.0)
	wind = 6.0 + 10.0 * sin(tt / 23.0) + 4.0 * sin(tt / 7.0)
	if cmod and is_instance_valid(cmod):
		var c := _tint()
		cmod.color = c.lerp(Color(1, 0.95, 0.88), 0.55) if interior else c
	var sun := _sun()
	var night := _night()
	for e in shadows:
		var s: Sprite2D = e[0]
		var k: float = 0.16 + 0.34 * (1.0 - sun.y)      # 太阳越低，影子越长
		s.scale = Vector2(1.0, -k)
		s.skew = clampf(-sun.x * 0.9, -0.9, 0.9)
		s.modulate.a = 0.32 * clampf(sun.y * 3.0, 0.0, 1.0)
	for l in lights:
		var n: PointLight2D = l["node"]
		var e2: float = night
		if l["kind"] == "room":
			e2 = 0.25 + 0.5 * night
		if l["flicker"] and night > 0.2:
			var f: float = sin(tt * 37.0 + l["ph"]) * sin(tt * 3.1 + l["ph"])
			if f > 0.85 or fmod(tt + l["ph"], 9.0) < 0.25:
				e2 *= 0.15
		n.energy = e2 * (1.3 if l["kind"] == "lamp" else 0.9)
	for em in emitters:
		var p: CPUParticles2D = em[0]
		if em[1] == "leaves":
			p.gravity = Vector2(wind, 16)
		else:
			p.gravity = Vector2(wind * 0.7, -4)
	_car_tick(delta)
	_bird_tick(delta)


## 脚步：由 actor 在落脚帧调用
func footstep(who: Node2D) -> void:
	var name: String = sfx.get("_shoe_map", {}).get(who.cid, "")
	if name == "":
		name = "step_paw" if (str(who.cid).begins_with("cat") or str(who.cid).begins_with("dog") or who.cid == "wangcai") else "step_sneaker"
	if interior and (name == "step_sneaker" or name == "step_kid"):
		name = "step_tile"
	steps_played += 1
	play_at(name, who.position, 2.0 if who == M.player else 0.0)
