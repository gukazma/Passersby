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
var shadows: Array = []           # [Sprite2D, kind]（楼排、高道具）
var shade: CanvasGroup            # 所有太阳影子画进同一个组：重叠处不会叠黑
var shadow_map: Dictionary = {}   # 角色/车/地上的鸟 -> 影子 Sprite2D
var sun_ax := 0.0                 # 每 1 px 高度，影子在屏幕上的横向偏移（正 = 向右）
var sun_ay := 0.3                 # 每 1 px 高度，影子在屏幕上向下（朝镜头）的长度
var sun_alpha := 0.3
const SHADOW_ALPHA := 0.46        # 调参：正午影子浓度（A1.5 试玩前 0.34 偏淡，人影看不出来）
var perches: Array = []           # 能落鸟的点 {p: Vector3(x, 纵深, 高度), g: 组}：画面里的屋脊、路灯顶、牌子顶、栏杆、树冠
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
	shadows.clear(); lights.clear(); cars.clear(); birds.clear(); flocks.clear(); emitters.clear(); shadow_map.clear(); perches.clear()
	shade = null
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
		_prop_perches()
	_make_lights()
	_make_fx()
	_make_fauna()
	car_cd = randf_range(1.0, 4.0)


func _make_shadows() -> void:
	## 太阳影子：楼排、高道具、角色、车、地上的鸟，都用自己的剪影压扁、斜切到地面上。
	## 设定：街道东西向，镜头朝南看，太阳在楼的后上方 → 影子朝镜头（屏幕下方）落；
	## 早上太阳在左（东）影子斜向右，傍晚在右（西）影子斜向左；太阳越低影子越长。
	shade = CanvasGroup.new()
	shade.z_index = -9
	scene.add_child(shade)
	for L in scene.data.get("layers", []):
		var img: String = L["img"]
		if not (img.begins_with("row_") or img.begins_with("block")):
			continue
		var tex: Texture2D = load(scene.base + "/" + img) if ResourceLoader.exists(scene.base + "/" + img) else null
		if tex == null:
			continue
		var s := _shadow_sprite(tex)
		s.offset = Vector2(0, -tex.get_height())
		s.position = Vector2(float(L.get("x", 0)), float(L.get("y", 0)) + tex.get_height())
		s.set_meta("foot", s.position)
		shadows.append([s, "row"])
		_find_perches(tex, Vector2(float(L.get("x", 0)), float(L.get("y", 0))))
	for P in scene.data.get("props", []):
		var nm: String = P["img"]
		if not (nm.begins_with("tree") or nm.contains("lamp") or nm.begins_with("kiosk") or nm.begins_with("post") or nm.begins_with("gate") or nm.begins_with("teakiosk") or nm.begins_with("stall") or nm.begins_with("bench") or nm.begins_with("bicycle") or nm.begins_with("railing") or nm.begins_with("bollard") or nm.begins_with("hydrant") or nm.begins_with("light") or nm.begins_with("pot_")):
			continue
		var p: String = scene.base + "/" + nm
		if not ResourceLoader.exists(p):
			continue
		var tex: Texture2D = load(p)
		var s := _shadow_sprite(tex)
		s.offset = Vector2(-float(P.get("ox", tex.get_width() / 2.0)), -float(P.get("oy", tex.get_height())))
		s.set_meta("foot", Vector2(P["x"], P["y_foot"]))
		shadows.append([s, "prop"])


func _shadow_sprite(tex: Texture2D) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = false
	s.modulate = Color(0.16, 0.09, 0.06, 1.0)
	shade.add_child(s)
	return s


## 影子变换：本地 (x, -h)（脚底以上 h 像素）→ 屏幕 (x + ax·h, ay·h)
func _shadow_xform(foot: Vector2, k := 1.0) -> Transform2D:
	return Transform2D(Vector2(1, 0), Vector2(-sun_ax * k, -sun_ay * k), foot)


## 动的东西（角色、车、地上的鸟）的影子：每帧复制它的当前帧
func _sync_shadow(key: Object, src: Sprite2D, foot: Vector2, show: bool) -> void:
	if shade == null:
		return
	var s: Sprite2D = shadow_map.get(key)
	if s == null:
		s = _shadow_sprite(src.texture)
		shadow_map[key] = s
	s.visible = show and sun_alpha > 0.01
	if not s.visible:
		return
	s.texture = src.texture
	s.hframes = src.hframes
	s.vframes = src.vframes
	s.frame = src.frame
	s.flip_h = src.flip_h
	s.offset = src.offset + Vector2(0, src.position.y)
	s.transform = _shadow_xform(foot)


func _prop_perches() -> void:
	## 街上的鸟最常歇在：路灯顶、路牌/报亭顶、栏杆扶手、系缆桩、树冠里（麻雀）。纵深 = 道具脚 + 0.5，画在道具前面
	for P in scene.data.get("props", []):
		var nm: String = P["img"]
		var p: String = scene.base + "/" + nm
		if not ResourceLoader.exists(p):
			continue
		var tex: Texture2D = load(p)
		var h: float = float(P.get("oy", tex.get_height()))
		var x: float = float(P["x"])
		var y: float = float(P["y_foot"])
		var g := "%s@%d" % [nm, int(x)]
		if nm.contains("lamp"):
			perches.append({"p": Vector3(x, y + 0.5, h - 3.0), "g": g})
		elif nm.begins_with("post") or nm.begins_with("kiosk") or nm.begins_with("teakiosk") or nm.begins_with("gate"):
			for dx in [-10.0, 0.0, 10.0]:
				perches.append({"p": Vector3(x + dx, y + 0.5, _top_at(tex, P, dx)), "g": g})
		elif nm.begins_with("railing"):
			for dx in range(-110, 111, 14):
				perches.append({"p": Vector3(x + dx, y + 0.5, _top_at(tex, P, float(dx))), "g": g})
		elif nm.begins_with("tree"):
			for dx in [-30.0, -12.0, 8.0, 26.0]:
				perches.append({"p": Vector3(x + dx, y + 1.0, h * 0.62 + randf_range(-8, 8)), "g": g, "tree": true})


## 道具在 dx 处最高的不透明像素离脚底多高（落在实处，不悬空）
func _top_at(tex: Texture2D, P: Dictionary, dx: float) -> float:
	var img := tex.get_image()
	if img == null:
		return float(tex.get_height()) - 2.0
	if img.is_compressed():
		img.decompress()
	var ox: float = float(P.get("ox", tex.get_width() / 2.0))
	var oy: float = float(P.get("oy", tex.get_height()))
	var cx := clampi(int(ox + dx), 0, img.get_width() - 1)
	for yy in img.get_height():
		if img.get_pixel(cx, yy).a > 0.5:
			return oy - float(yy) - 0.5
	return oy - 2.0


func _find_perches(tex: Texture2D, at: Vector2) -> void:
	## 屋脊上平的地方（连续 10 px 高度差 ≤ 1）可以落鸟
	var img := tex.get_image()
	if img == null:
		return
	if img.is_compressed():
		img.decompress()
	var w := img.get_width()
	var tops: Array = []
	for x in range(0, w, 2):
		var top := -1
		for y in img.get_height():
			if img.get_pixel(x, y).a > 0.5:
				top = y
				break
		tops.append(top)
	for i in range(3, tops.size() - 3, 6):
		var ok: bool = tops[i] >= 0
		for j in range(i - 3, i + 4):
			if tops[j] < 0 or absi(tops[j] - tops[i]) > 1:
				ok = false
		if ok and at.y + tops[i] > 40.0:      # 屋脊要在画面里
			var py: float = at.y + tops[i]
			perches.append({"p": Vector3(at.x + i * 2, scene.band.x - 1.0, scene.band.x - 1.0 - py), "g": "roof%d" % int(py)})


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


func _particles(pos: Vector2, kind: String, depth := 0.0) -> CPUParticles2D:
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
		p.amount = 22
		p.lifetime = 2.8
		p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
		p.emission_rect_extents = Vector2(8, 2)
		p.direction = Vector2(0, -1)
		p.spread = 12.0
		p.initial_velocity_min = 10.0
		p.initial_velocity_max = 16.0
		p.gravity = Vector2(wind * 0.7, -4)
		p.scale_amount_min = 1.2
		p.scale_amount_max = 2.4
		var ramp := Gradient.new()
		ramp.set_color(0, Color(1, 1, 1, 0.85))
		ramp.set_color(1, Color(1, 1, 1, 0.0))
		p.color_ramp = ramp
		p.preprocess = 2.0
	if kind == "steam" and depth > 0.0:
		# 蒸汽按所在位置的纵深参与前后排序：锅在店里，路过的人挡在蒸汽前面
		var holder := Node2D.new()
		holder.position = Vector2(pos.x, depth)
		p.position = Vector2(0, pos.y - depth)
		p.z_index = 0
		holder.add_child(p)
		scene.ysort.add_child(holder)
	else:
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
			_particles(Vector2(f["x"], f["y"]), "steam", float(f.get("depth", 0.0)))
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


## 鸟的行为（A1.5 按真实城市鸟改；用户：「鸽子咋一直在半空中飞」「鸟没有做遮挡，得模拟鸟的实际行为」）：
##  - 城里的鸽子、麻雀习惯了车和行人：车不惊鸟；行人走近只是走开/跳开，贴得很近、有人跑过来、狗猫冲过来才整群惊飞
##  - 惊飞：先陡升躲开，鸽子绕一圈，然后落到屋脊上或者远一点的地面；在屋脊上歇一会儿，没人了再飞回地上觅食
##  - 麻雀飞得短，直接躲到最近的屋脊上，很快回来；海鸥在海面上空借风盘旋，偶尔落在栏杆、系缆桩上
##  - 每只鸟都有「地面点」(x, 纵深 y) 和高度 alt：节点放在地面点参与前后排序（树、路灯、行人能挡住它），
##    精灵向上抬 alt 画；落在屋脊上的鸟纵深 = 楼脚，被人行道上所有东西挡住
const BIRD := {
	"pigeon": {"walk": 14.0, "avoid": 75.0, "flush": 34.0, "flush_run": 120.0, "flush_animal": 110.0, "fly": 330.0, "lap": 150.0, "alt": 110.0, "perch_s": [10.0, 25.0], "roof_p": 0.6},
	"sparrow": {"walk": 24.0, "avoid": 70.0, "flush": 46.0, "flush_run": 140.0, "flush_animal": 130.0, "fly": 260.0, "lap": 0.0, "alt": 70.0, "perch_s": [5.0, 12.0], "roof_p": 1.0},
	"seagull": {"walk": 12.0, "avoid": 90.0, "flush": 50.0, "flush_run": 140.0, "flush_animal": 120.0, "fly": 120.0, "lap": 260.0, "alt": 170.0, "perch_s": [20.0, 40.0], "roof_p": 0.0},
}


func _bird(kind: String, pos: Vector2, alt: float, flock: Dictionary, state: String) -> void:
	var node := Node2D.new()
	node.position = pos
	var spr := Sprite2D.new()
	spr.centered = false
	node.add_child(spr)
	scene.ysort.add_child(node)
	var b := {"node": node, "spr": spr, "kind": kind, "state": state, "vel": Vector3.ZERO, "t": randf() * 3.0, "alt": alt,
		"anim": "", "f": 0.0, "flock": flock, "facing": 1 if randf() < 0.5 else -1,
		"off": Vector3(randf_range(-28, 28), randf_range(-8, 8), randf_range(-14, 14)), "dest": Vector3.ZERO}
	if kind == "seagull":
		b["off"] = Vector3(randf_range(-150, 150), randf_range(-10, 30), randf_range(-60, 60))   # 海鸥散得开
	birds.append(b)
	_bset(b, "idle_side" if state == "ground" and flock["anims"].has("idle_side") else ("stand" if state == "ground" else "fly_side"))


func _bset(b: Dictionary, anim: String) -> void:
	var A: Dictionary = b["flock"]["anims"]
	if not A.has(anim) or b["anim"] == anim:
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
		var ground: bool = fa.get("ground", true)
		var home := Vector2(fa["x"], fa.get("y", scene.band.y - 10))
		var flock := {"id": flocks.size(), "kind": kind, "anims": anims, "home": home, "state": "ground" if ground else "soar",
			"t": 0.0, "c": Vector3(home.x, scene.band.x + 30.0, 0.0), "lap_a": 0.0, "lap_c": Vector2.ZERO, "flushes": 0,
			"air_t": 0.0, "dest": {}, "sky_alt": float(fa.get("sky_alt", 330.0 - float(fa.get("sky_y", 140))))}
		flocks.append(flock)
		for i in int(fa.get("n", 5)):
			if ground:
				var gy: float = clampf(home.y + randf_range(-10, 10), scene.band.x + 4, scene.band.y)
				_bird(kind, Vector2(home.x + randf_range(-40, 40), gy), 0.0, flock, "ground")
			else:
				var c := Vector2(home.x + randf_range(-160, 160), scene.band.x + randf_range(-4, 30))
				_bird(kind, c, flock["sky_alt"] + randf_range(-40, 40), flock, "fly")


func _threats() -> Array:
	## [位置, 种类("person"/"animal"), 在跑, 在动]
	var out: Array = []
	var actors: Array = [M.player]
	actors.append_array(M.npcs)
	for a in actors:
		if is_instance_valid(a) and a.visible and not a.hidden_in_door:
			out.append([a.position, "animal" if a.kind in ["dog", "cat"] else "person", a.running, a.moving])
	return out


func _bird_tick(delta: float) -> void:
	var threats := _threats()
	for fl in flocks:
		var fid: int = fl["id"]
		var members: Array = birds.filter(func(b): return b["flock"]["id"] == fid)
		var cfg: Dictionary = BIRD.get(fl["kind"], BIRD["pigeon"])
		match fl["state"]:
			"ground", "perch":
				# 惊飞判定：任何一只被吓到，整群一起飞
				var scare := Vector2.INF
				for b in members:
					if b["state"] != "ground" and b["state"] != "perch":
						continue
					var bp: Vector2 = b["node"].position
					for th in threats:
						var d: float = bp.distance_to(th[0])
						if b["state"] == "perch" and b["alt"] > 90.0:
							continue        # 高处（屋脊、路灯顶）的鸟不怕街上的人；栏杆、低矮处的照样会惊飞
						var r: float = cfg["flush"]
						if th[1] == "animal" and th[3]:
							r = cfg["flush_animal"]
						elif th[2]:
							r = cfg["flush_run"]
						if d < r:
							scare = th[0]
				if scare != Vector2.INF:
					_flush(fl, members, scare)
				elif fl["state"] == "perch":
					fl["t"] -= delta
					if fl["t"] <= 0.0:
						# 歇够了：觅食点附近没人就飞回地上
						var spot := _ground_spot(fl, threats, true)
						if spot != Vector2.INF:
							_fly_to(fl, members, {"kind": "ground", "p": spot})
						else:
							fl["t"] = 4.0
			"flee", "circle", "approach":
				fl["air_t"] += delta
				_flock_center(fl, cfg, delta)
			"soar":
				_flock_center(fl, cfg, delta)
		for b in members:
			_bird_move(b, fl, cfg, threats, delta)
		if fl["state"] == "approach" and members.all(func(b): return b["state"] == "ground" or b["state"] == "perch"):
			fl["state"] = fl["dest"]["kind"]
			fl["air_t"] = 0.0
			fl["t"] = randf_range(cfg["perch_s"][0], cfg["perch_s"][1])
		if fl["kind"] == "seagull" and randf() < delta * 0.25:
			play_at("seagull_call", Vector2(fl["c"].x, fl["c"].y))
		if fl["kind"] == "pigeon" and fl["state"] == "ground" and randf() < delta * 0.12:
			play_at("pigeon_coo", fl["home"])
		if fl["kind"] == "sparrow" and randf() < delta * 0.2:
			play_at("sparrow_chirp", fl["home"])


func _flush(fl: Dictionary, members: Array, from: Vector2) -> void:
	var cfg: Dictionary = BIRD.get(fl["kind"], BIRD["pigeon"])
	var cx := 0.0
	for b in members:
		cx += b["node"].position.x
	cx /= maxf(1.0, members.size())
	var away: float = 1.0 if cx >= from.x else -1.0
	fl["flushes"] += 1
	fl["air_t"] = 0.0
	fl["state"] = "flee"
	fl["t"] = 0.9
	fl["c"] = Vector3(cx + away * 90.0, scene.band.x + 20.0, cfg["alt"])
	fl["away"] = away
	for b in members:
		b["state"] = "fly"
		b["vel"] = Vector3(away * randf_range(60, 120), randf_range(-20, 0), randf_range(160, 220))
		_bset(b, "takeoff" if fl["anims"].has("takeoff") else "fly_side")
	play_at("pigeon_wings_takeoff" if fl["kind"] == "pigeon" else "sparrow_chirp", Vector2(cx, members[0]["node"].position.y))


func _fly_to(fl: Dictionary, members: Array, dest: Dictionary) -> void:
	fl["state"] = "approach"
	fl["dest"] = dest
	var i := 0
	for b in members:
		if dest["kind"] == "perch":
			var pp: Vector3 = dest["slots"][i % dest["slots"].size()]
			var extra: int = i / dest["slots"].size()
			b["dest"] = pp + Vector3(extra * 7.0 * (1.0 if i % 2 == 0 else -1.0), 0, 0)
		else:
			var gp: Vector2 = dest["p"] + Vector2(randf_range(-36, 36), randf_range(-8, 8))
			gp.y = clampf(gp.y, scene.band.x + 4, scene.band.y)
			b["dest"] = Vector3(gp.x, gp.y, 0.0)
		if b["state"] != "fly":
			b["state"] = "fly"
			b["vel"] = Vector3(0, 0, 120)
			_bset(b, "takeoff" if fl["anims"].has("takeoff") else "fly_side")
		i += 1


func _ground_spot(fl: Dictionary, threats: Array, prefer_home: bool) -> Vector2:
	## 找一块离人远的人行道（不在家具里），优先回原来的觅食点
	var cands: Array = []
	if prefer_home:
		cands.append(fl["home"])
	for k in 8:
		cands.append(Vector2(clampf(fl["c"].x + randf_range(-320, 320), 60, float(scene.width) - 60), randf_range(scene.band.x + 8, scene.band.y - 2)))
	for c in cands:
		var good := true
		for th in threats:
			if c.distance_to(th[0]) < 170.0:
				good = false
		for r in scene.solids:
			if r.grow(10).has_point(c):
				good = false
		if good:
			return c
	return Vector2.INF


func _flock_center(fl: Dictionary, cfg: Dictionary, delta: float) -> void:
	var c: Vector3 = fl["c"]
	match fl["state"]:
		"flee":
			fl["t"] -= delta
			c.x += fl["away"] * cfg["fly"] * 0.6 * delta
			if fl["t"] <= 0.0:
				if cfg["lap"] > 0.0:
					fl["state"] = "circle"
					fl["lap_a"] = 0.0
					fl["lap_c"] = Vector2(c.x + fl["away"] * cfg["lap"], c.y)
				else:
					_choose_dest(fl, cfg)
		"circle":
			# 鸽子惊飞后在街道上空绕一个大圈（逆时针，经过镜头前和楼前）
			fl["lap_a"] += cfg["fly"] / cfg["lap"] * delta
			var a: float = fl["lap_a"] + PI
			c = Vector3(fl["lap_c"].x + cos(a) * cfg["lap"] * fl["away"], scene.band.x + 40.0 + sin(a) * 34.0, cfg["alt"] + sin(a * 2.0) * 20.0)
			if fl["lap_a"] >= TAU * 0.85:
				_choose_dest(fl, cfg)
		"soar":
			# 海鸥：借风慢慢盘旋，中心随风漂
			fl["lap_a"] += cfg["fly"] / cfg["lap"] * delta * 0.6
			var a2: float = fl["lap_a"]
			c = Vector3(fl["home"].x + cos(a2) * cfg["lap"] + sin(tt * 0.05) * 120.0, scene.band.x + 10.0 + sin(a2) * 20.0, fl["sky_alt"] + sin(a2 * 0.5) * 30.0)
	fl["c"] = c


func _choose_dest(fl: Dictionary, cfg: Dictionary) -> void:
	var members: Array = birds.filter(func(b): return b["flock"]["id"] == fl["id"])
	if randf() < cfg["roof_p"] and perches.size() > 0:
		# 落到附近（离当前位置 120–450 px，在画面附近）的一处高处，同一处一只挨一只；麻雀爱钻树冠
		var cands: Array = []
		for pp in perches:
			var dxp: float = absf(pp["p"].x - fl["c"].x)
			if dxp < 450.0 and (fl["kind"] == "sparrow" or not pp.get("tree", false)):
				cands.append(pp)
		if cands.size() > 0:
			var pick: Dictionary = cands[randi() % cands.size()]
			var slots: Array = []
			for pp in perches:
				if pp["g"] == pick["g"] and absf(pp["p"].x - pick["p"].x) < 70.0:
					slots.append(pp["p"])
			_fly_to(fl, members, {"kind": "perch", "slots": slots})
			return
	var spot := _ground_spot(fl, _threats(), false)
	if spot == Vector2.INF:
		spot = fl["home"]
	_fly_to(fl, members, {"kind": "ground", "p": spot})


func _bird_move(b: Dictionary, fl: Dictionary, cfg: Dictionary, threats: Array, delta: float) -> void:
	var node: Node2D = b["node"]
	match b["state"]:
		"ground":
			# 觅食：走走、啄啄、站站；有人走近就往另一边走开（不飞）
			var flee := Vector2.ZERO
			for th in threats:
				var d: Vector2 = node.position - th[0]
				if d.length() < cfg["avoid"] and th[3]:
					flee += d.normalized()
			b["t"] -= delta
			if flee != Vector2.ZERO:
				var v: Vector2 = Vector2(signf(flee.x) if flee.x != 0.0 else 1.0, clampf(flee.y, -0.4, 0.4)) * cfg["walk"] * 2.2
				b["vel"] = Vector3(v.x, v.y, 0)
				b["facing"] = 1 if v.x >= 0 else -1
				_bset(b, "walk_peck" if fl["anims"].has("walk_peck") else ("hop" if fl["anims"].has("hop") else "idle_side"))
				b["t"] = 0.6
			elif b["t"] <= 0.0:
				b["t"] = randf_range(0.8, 2.5)
				var r := randf()
				if r < 0.45:
					# 往觅食点方向慢慢走，不会越走越远
					var back: float = signf(fl["home"].x - node.position.x) if absf(fl["home"].x - node.position.x) > 60.0 else (1.0 if randf() < 0.5 else -1.0)
					b["vel"] = Vector3(back * randf_range(0.5, 1.0) * cfg["walk"], randf_range(-3, 3), 0)
					b["facing"] = 1 if b["vel"].x >= 0 else -1
					_bset(b, "walk_peck" if fl["anims"].has("walk_peck") else ("hop" if fl["anims"].has("hop") else "idle_side"))
				elif r < 0.75 and fl["anims"].has("peck"):
					b["vel"] = Vector3.ZERO
					_bset(b, "peck")
				else:
					b["vel"] = Vector3.ZERO
					_bset(b, "idle_side" if fl["anims"].has("idle_side") else "stand")
			var np: Vector2 = node.position + Vector2(b["vel"].x, b["vel"].y) * delta
			np.y = clampf(np.y, scene.band.x + 3, scene.band.y + 4)
			np.x = clampf(np.x, 10, float(scene.width) - 10)
			for r2 in scene.solids:
				if r2.has_point(np):
					np = node.position
			node.position = np
			b["alt"] = 0.0
		"perch":
			b["t"] -= delta
			if b["t"] <= 0.0:
				b["t"] = randf_range(1.5, 4.0)
				b["facing"] = -b["facing"] if randf() < 0.3 else b["facing"]
				_bset(b, "idle_side" if fl["anims"].has("idle_side") else "stand")
		"fly":
			var tgt: Vector3
			var landing: bool = fl["state"] == "approach"
			if landing:
				tgt = b["dest"]
			else:
				tgt = fl["c"] + b["off"]
			var pos := Vector3(node.position.x, node.position.y, b["alt"])
			var to: Vector3 = tgt - pos
			var sp: float = cfg["fly"]
			if landing:
				sp = minf(sp, 40.0 + to.length() * 1.6)        # 快到了减速
			var want: Vector3 = to.normalized() * sp if to.length() > 0.5 else Vector3.ZERO
			b["vel"] = b["vel"].lerp(want, clampf(delta * (3.0 if landing else 2.2), 0.0, 1.0))
			# 同群互相让开一点
			for o in birds:
				if o != b and o["flock"]["id"] == fl["id"] and o["state"] == "fly":
					var dd := Vector2(node.position.x - o["node"].position.x, b["alt"] - o["alt"])
					if dd.length() < 10.0 and dd.length() > 0.01:
						b["vel"] += Vector3(dd.x, 0, dd.y).normalized() * 30.0 * delta
			pos += b["vel"] * delta
			pos.y = clampf(pos.y, scene.band.x - 2.0, scene.band.y + 40.0)
			pos.z = maxf(0.0, pos.z)
			node.position = Vector2(pos.x, pos.y)
			b["alt"] = pos.z
			if absf(b["vel"].x) > 4.0:
				b["facing"] = 1 if b["vel"].x > 0 else -1
			if landing and to.length() < 3.0:
				node.position = Vector2(tgt.x, tgt.y)
				b["alt"] = tgt.z
				b["vel"] = Vector3.ZERO
				b["state"] = fl["dest"]["kind"]
				b["t"] = randf_range(0.5, 2.0)
				_bset(b, "idle_side" if fl["anims"].has("idle_side") else "stand")
			elif b["anim"] == "takeoff" and b["f"] < 4.0:
				pass
			elif landing and to.length() < 40.0 and fl["anims"].has("land"):
				_bset(b, "land")
			elif fl["anims"].has("glide") and (b["vel"].z < -15.0 or (fl["state"] == "soar" and sin(tt * 0.4 + b["off"].x) > 0.3)):
				_bset(b, "glide")       # 下滑、盘旋时张开翅膀滑翔
			else:
				_bset(b, "fly_side")
	# 帧动画；精灵抬到高度 alt 上画，节点留在地面点参与前后遮挡
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
	spr.position = Vector2(0, -roundf(b["alt"]))
	node.z_index = 0


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
	_update_sun(sun)
	for e in shadows:
		var s: Sprite2D = e[0]
		# 楼的剪影是压缩过层高的，按 0.35 算，只在楼脚压一条随屋顶起伏的阴影，不把整条人行道盖黑
		s.transform = _shadow_xform(s.get_meta("foot"), 0.35 if e[1] == "row" else 1.0)
	_sync_movers()
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


func _update_sun(sun: Vector2) -> void:
	## 太阳高度角最高约 62°；影子长度 = cot(高度角)；横向分量随方位（东 → 西）由右转到左
	var elev: float = deg_to_rad(maxf(sun.y, 0.0) * 62.0)
	var cot: float = 1.0 / maxf(tan(elev), 0.25)
	var lat: float = clampf(sun.x, -1.0, 1.0)
	sun_ax = clampf(-lat * cot, -2.4, 2.4)
	sun_ay = clampf(sqrt(maxf(0.0, 1.0 - lat * lat)) * cot * 0.45 + 0.08, 0.1, 0.9)
	sun_alpha = SHADOW_ALPHA * clampf(sun.y * 4.0, 0.0, 1.0)
	if shade:
		shade.self_modulate = Color(1, 1, 1, sun_alpha)
		shade.visible = sun_alpha > 0.01


func _sync_movers() -> void:
	if shade == null:
		return
	var actors: Array = [M.player]
	actors.append_array(M.npcs)
	for a in actors:
		if is_instance_valid(a) and a.spr:
			_sync_shadow(a, a.spr, a.position, a.visible and not a.hidden_in_door and a.modulate.a > 0.5)
	for c in cars:
		_sync_shadow(c["node"], c["spr"], c["node"].position, true)
	for b in birds:
		_sync_shadow(b["node"], b["spr"], b["node"].position, b["alt"] < 1.0)
	for k in shadow_map.keys():
		if not is_instance_valid(k):
			shadow_map[k].queue_free()
			shadow_map.erase(k)


## 脚步：由 actor 在落脚帧调用
func footstep(who: Node2D) -> void:
	var name: String = sfx.get("_shoe_map", {}).get(who.cid, "")
	if name == "":
		name = "step_paw" if (str(who.cid).begins_with("cat") or str(who.cid).begins_with("dog") or who.cid == "wangcai") else "step_sneaker"
	if interior and (name == "step_sneaker" or name == "step_kid"):
		name = "step_tile"
	steps_played += 1
	play_at(name, who.position, 2.0 if who == M.player else 0.0)
