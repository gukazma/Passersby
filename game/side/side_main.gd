extends Node2D
## 《我亦是行人》横版主控：街段/室内切换、主角操作、NPC、镜头、提示、对话、气泡、转场、拍照、自动演示。
## 世界数据 res://side_data/world.json。命令行（-- 之后）：--scene=<id> --pos=x,y --demo=<json> --photo

const DATA := "res://side_data/"
const VIEW := Vector2(960, 540)

var world: Dictionary = {}
var scene: Node2D = null
var scene_id := ""
var player: Node2D
var npcs: Array = []
var cam: Camera2D
var hud: CanvasLayer
var fade: ColorRect
var loc_label: Label
var help_label: Label
var card: Label
var prompt: Label
var dlg: PanelContainer
var dlg_name: Label
var dlg_text: Label
var dlg_lines: Array = []
var dlg_npc: Node2D = null
var px_font: FontFile
var busy := false                 # 转场中，不接受输入
var cutscene_move := Vector2.ZERO # 转场时自动走（进门、过马路）
var demo: Array = []
var demo_i := 0
var demo_t := 0.0
var demo_on := false
var demo_press := ""
var photo := false
var args: Dictionary = {}
var t_total := 0.0
var spots_taken: Dictionary = {}  # spot_id -> 占用者
var bgm: AudioStreamPlayer
var bgm_path := ""
var smoke_mark: Dictionary = {}   # npc -> 上次冒烟的帧
var flash: ColorRect
var dlg_portrait: TextureRect
var dlg_hearts: HBoxContainer
var friend: Dictionary = {}       # cid -> 好感点数（100 点 = 1 颗心，最多 10 颗）
var talked: Dictionary = {}       # 本次游戏已经聊过的人（第一次聊天 +20）
var heart_tex: Array = []         # [空, 半, 满]
var emote_cd: Dictionary = {}
var test_want := Vector2.ZERO     # 自动测试：机器人输入
var test_run := false
var test_no_edges := false
var testing := false
var shots_saved := 0
var _scene_cache: Dictionary = {}
var ambient: Node2D
var crossing_zebra := Vector2.ZERO  # 有人正在过的斑马线 (x0, x1)，车在前面停
var clock_label: Label


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	px_font = FontFile.new()
	px_font.load_dynamic_font("res://fonts/px.woff2")
	px_font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	px_font.hinting = TextServer.HINTING_NONE
	px_font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	world = JSON.parse_string(FileAccess.get_file_as_string(DATA + "world.json"))
	for n in world.get("npcs", []):
		var cid0: String = n["char"].split("/")[1]
		friend[cid0] = int(n.get("friend", 0))
	cam = Camera2D.new()
	cam.process_callback = Camera2D.CAMERA2D_PROCESS_PHYSICS
	add_child(cam)
	cam.make_current()
	_build_hud()
	ambient = load("res://side/ambient.gd").new()
	add_child(ambient)
	if args.has("time"):
		var hm: PackedStringArray = args["time"].split(":")
		ambient.minutes = float(hm[0]) * 60.0 + (float(hm[1]) if hm.size() > 1 else 0.0)
	player = load("res://side/actor.gd").new()
	player.load_char(DATA + world["player"])
	player.body_half = 9
	var st: Dictionary = world["start"]
	var sid: String = args.get("scene", st["scene"])
	var pos := Vector2(st["x"], st["y"])
	if args.has("pos"):
		var p: PackedStringArray = args["pos"].split(",")
		pos = Vector2(float(p[0]), float(p[1]))
	if args.has("demo"):
		var dj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA + args["demo"]))
		demo = dj["steps"]
		demo_on = true
		if dj.has("start"):
			sid = dj["start"]["scene"]
			pos = Vector2(dj["start"]["x"], dj["start"]["y"])
	_go(sid, pos, "side", 1)
	if args.has("autotest"):
		testing = true
		var at: Node = load("res://side/autotest.gd").new()
		at.M = self
		add_child(at)
		at.call_deferred("run_all")
	elif args.has("shots"):
		testing = true
		var at2: Node = load("res://side/autotest.gd").new()
		at2.M = self
		add_child(at2)
		at2.call_deferred("run_shots", args["shots"])
	if args.has("photo"):
		_toggle_photo()


# ---------------------------------------------------------------- 场景
func _go(id: String, pos: Vector2, view: String, facing: int) -> void:
	if scene:
		scene.ysort.remove_child(player)
		for n in npcs:
			n.queue_free()
		npcs.clear()
		scene.queue_free()
	scene_id = id
	scene = load("res://side/scene.gd").new()
	add_child(scene)
	move_child(scene, 0)
	scene.build(DATA + world["scenes"][id])
	for ep in world.get("extra_props", {}).get(id, []):
		scene.add_prop(ep)
	scene.add_actor(player)
	pos.x = clampf(pos.x, scene.x_range.x, scene.x_range.y)
	player.position = pos
	player.band = scene.band
	player.x_range = scene.x_range
	player.solids = scene.solids
	player.view = view
	player.facing = facing
	player.drive(Vector2.ZERO, false, 0.0)
	for cfg in world.get("npcs", []):
		if cfg.get("scene", "") != id:
			continue
		var n: Node2D = load("res://side/npc.gd").new()
		n.load_char(DATA + cfg["char"])
		n.position = Vector2(cfg["x"], cfg["y"])
		n.band = Vector2(cfg.get("band", [scene.band.x, scene.band.y])[0], cfg.get("band", [scene.band.x, scene.band.y])[1])
		n.solids = scene.solids
		n.x_range = scene.x_range
		n.scene_ref = scene
		n.player_ref = player
		n.say_cb = Callable(self, "_bubble")
		n.main_ref = self
		n.setup_brain(cfg)
		scene.add_actor(n)
		npcs.append(n)
	var everyone: Array = npcs.duplicate()
	everyone.append(player)
	for a in everyone:
		a.others = everyone
	cam.limit_left = 0
	cam.limit_right = maxi(scene.width, int(VIEW.x))
	cam.limit_top = 0
	cam.limit_bottom = int(VIEW.y)
	cam.position = Vector2(clampf(pos.x, VIEW.x / 2, scene.width - VIEW.x / 2), VIEW.y / 2)
	cam.reset_smoothing()
	spots_taken.clear()
	_play_bgm(world.get("bgm", {}).get(id, ""))
	ambient.setup(self, scene)
	player.step_cb = Callable(ambient, "footstep")
	for n2 in npcs:
		n2.step_cb = Callable(ambient, "footstep")
	var d: Dictionary = scene.data
	var side_txt = d.get("side", "")
	loc_label.text = str(d.get("name", id))


func _transition(callback: Callable, card_text: String = "") -> void:
	busy = true
	var tw := create_tween()
	tw.tween_property(fade, "color:a", 1.0, 0.35)
	tw.tween_callback(callback)
	if card_text != "":
		tw.tween_callback(func(): card.text = card_text; card.visible = true)
		tw.tween_interval(0.6)
		tw.tween_callback(func(): card.visible = false)
	tw.tween_property(fade, "color:a", 0.0, 0.35)
	tw.tween_callback(func(): busy = false)


# ---------------------------------------------------------------- 每帧
func _physics_process(delta: float) -> void:
	t_total += delta
	var want := Vector2.ZERO
	var run := false
	if demo_on:
		var dm := _demo_tick(delta)
		want = dm[0]; run = dm[1]
	elif testing:
		want = test_want; run = test_run
	elif not busy and not photo and dlg_npc == null:
		want = Vector2(Input.get_axis("move_left", "move_right"), Input.get_axis("move_up", "move_down"))
		want = Vector2(signf(want.x), signf(want.y))
		run = Input.is_key_pressed(KEY_SHIFT)
	if busy:
		if cutscene_move != Vector2.ZERO:
			var b: Vector2 = player.band
			player.band = Vector2(-10000, 10000)
			player.drive(cutscene_move, false, delta)
			player.band = b
		else:
			player.drive(Vector2.ZERO, false, delta)
	else:
		if player.special != "" and (want != Vector2.ZERO):
			_player_stand()
		if player.special == "":
			player.drive(want, run, delta)
			_check_edges()
		elif player.special == "photo":
			_photo_tick()
		elif not player.anims[player.special]["loop"] and player.special_done:
			_player_stand()
	ambient.tick(delta)
	clock_label.text = ambient.clock_text() + ("  ▶▶" if ambient.fast else "")
	for n in npcs:
		n.tick(delta)
		_smoke_tick(n)
		_mood_emote(n, delta)
	_update_prompt()
	_follow_cam(delta)
	if scene:
		scene.update_parallax(cam.get_screen_center_position().x - VIEW.x / 2)


func _follow_cam(delta: float) -> void:
	if photo:
		return
	var look: float = 70.0 * player.facing if player.view == "side" else 0.0
	var tx := clampf(player.position.x + look, VIEW.x / 2, maxf(VIEW.x / 2, scene.width - VIEW.x / 2))
	cam.position.x = lerpf(cam.position.x, tx, 1.0 - exp(-delta * 3.5))
	cam.position.y = VIEW.y / 2


func world_scene(sid: String) -> Dictionary:
	if not _scene_cache.has(sid):
		_scene_cache[sid] = JSON.parse_string(FileAccess.get_file_as_string(DATA + world["scenes"][sid]))
	return _scene_cache[sid]


func _check_edges() -> void:
	if test_no_edges:
		return
	var p: Vector2 = player.position
	var ex: Dictionary = scene.exits
	if p.x < 14 and ex.get("left") != null and player.moving and player.facing < 0:
		_take_exit(ex["left"], -1)
	elif p.x > scene.width - 14 and ex.get("right") != null and player.moving and player.facing > 0:
		_take_exit(ex["right"], 1)
	# 室内：走到下沿出门
	if scene.data.get("kind", "") == "interior" and p.y >= scene.band.y - 1 and player.view == "front" and player.moving:
		_leave_interior()


func _take_exit(e: Dictionary, dirn: int) -> void:
	var to: String = e["to"]
	_transition(func():
		var w := _scene_width(to)
		var y: float = player.position.y
		var x := 40.0 if dirn > 0 else w - 40.0
		_go(to, Vector2(x, y), "side", dirn), "→ " + e.get("label", to))


func _scene_width(id: String) -> float:
	var j: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA + world["scenes"][id]))
	return float(j.get("width", 960))


# ---------------------------------------------------------------- 交互
func _unhandled_input(ev: InputEvent) -> void:
	if not (ev is InputEventKey) or not ev.pressed or ev.echo:
		return
	match ev.keycode:
		KEY_ESCAPE:
			get_tree().quit()
		KEY_P:
			_take_photo()
		KEY_O:
			_toggle_photo()
		KEY_ENTER, KEY_F12:
			if photo: _shot()
		KEY_H:
			help_label.visible = not help_label.visible
		KEY_T:
			ambient.fast = not ambient.fast
		KEY_SPACE, KEY_E:
			_interact()
		KEY_W, KEY_UP:
			if not busy and dlg_npc == null and not scene.door_at(player.position).is_empty():
				_interact()
		KEY_S, KEY_DOWN:
			if not busy and dlg_npc == null and not scene.zebra_at(player.position).is_empty():
				_cross(scene.zebra_at(player.position))


func _interact() -> void:
	if busy or photo:
		return
	if dlg_npc != null:
		_dlg_next()
		return
	var best: Node2D = null
	for n in npcs:
		if not n.visible or n.hidden_in_door:
			continue
		var d: Vector2 = n.position - player.position
		if absf(d.x) < 46 and absf(d.y) < 18 and (best == null or absf(d.x) < absf(best.position.x - player.position.x)):
			best = n
	if player.special != "":
		_player_stand()
		return
	if best and not best.talk.is_empty():
		_talk(best)
		return
	var dog := _near_dog()
	if dog and player.has_anim("pet_dog"):
		_player_pet(dog)
		return
	var sp := _near_spot()
	if not sp.is_empty():
		_player_sit(sp)
		return
	var door: Dictionary = scene.door_at(player.position)
	if not door.is_empty():
		_enter(door)
		return
	var z: Dictionary = scene.zebra_at(player.position)
	if not z.is_empty():
		_cross(z)


func _enter(door: Dictionary) -> void:
	if not door.has("interior"):
		_bubble(player, door.get("closed", "门关着。"), 1.4)
		return
	var dx: float = (door["x0"] + door["x1"]) / 2.0
	busy = true
	player.position.x = dx
	cutscene_move = Vector2(0, -1)
	var tw := create_tween()
	tw.tween_property(player, "modulate", Color(0.35, 0.3, 0.3, 1), 0.45)
	tw.tween_property(fade, "color:a", 1.0, 0.3)
	tw.tween_callback(func():
		cutscene_move = Vector2.ZERO
		player.modulate = Color.WHITE
		var it: String = door["interior"]
		var j: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA + world["scenes"][it]))
		var en: Dictionary = j.get("entry", {"x": 480, "y": j.get("band", [392, 468])[1]})
		world["_return"] = {"scene": scene_id, "x": dx, "y": scene.band.x + 4}
		_go(it, Vector2(en["x"], float(en["y"]) + 18), "back", 1)
		cutscene_move = Vector2(0, -1))
	tw.tween_callback(func(): card.text = door.get("label", ""); card.visible = true)
	tw.tween_property(fade, "color:a", 0.0, 0.3)
	tw.tween_interval(0.25)
	tw.tween_callback(func(): cutscene_move = Vector2.ZERO; busy = false)
	tw.tween_interval(0.6)
	tw.tween_callback(func(): card.visible = false)


func _leave_interior() -> void:
	var r: Dictionary = world.get("_return", {})
	if r.is_empty():
		return
	busy = true
	cutscene_move = Vector2(0, 1)
	var tw := create_tween()
	tw.tween_interval(0.25)
	tw.tween_property(fade, "color:a", 1.0, 0.3)
	tw.tween_callback(func():
		_go(r["scene"], Vector2(r["x"], r["y"]), "front", 1)
		cutscene_move = Vector2(0, 1))
	tw.tween_property(fade, "color:a", 0.0, 0.3)
	tw.tween_interval(0.15)
	tw.tween_callback(func(): cutscene_move = Vector2.ZERO; busy = false)


func _cross(z: Dictionary) -> void:
	## 斑马线过马路：正面走下路缘 → 淡出 → 对面街段（镜头掉头，x 镜像）从马路一侧背面走上人行道
	busy = true
	cutscene_move = Vector2(0, 1)
	crossing_zebra = Vector2(z["x0"], z["x1"])
	var to: String = z["to"]
	var tw := create_tween()
	tw.tween_interval(0.7)
	tw.tween_property(fade, "color:a", 1.0, 0.35)
	tw.tween_callback(func():
		var w := _scene_width(to)
		var j: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DATA + world["scenes"][to]))
		var x := w - player.position.x
		for z2 in j.get("zebras", []):
			if z2.get("to", "") == scene_id:
				x = (float(z2["x0"]) + float(z2["x1"])) / 2.0
				crossing_zebra = Vector2(z2["x0"], z2["x1"])
		if z.has("to_x"): x = float(z["to_x"])
		var b: Array = j.get("band", [392, 468])
		_go(to, Vector2(x, float(b[1]) + 30), "back", -player.facing)
		cutscene_move = Vector2(0, -1)
		card.text = "过马路 → " + z.get("label", to); card.visible = true)
	tw.tween_property(fade, "color:a", 0.0, 0.35)
	tw.tween_interval(0.55)
	tw.tween_callback(func():
		cutscene_move = Vector2.ZERO; busy = false; card.visible = false; crossing_zebra = Vector2.ZERO
		player.position.y = clampf(player.position.y, scene.band.x + 1, scene.band.y - 2))


func _talk(n: Node2D) -> void:
	dlg_npc = n
	n.talking = true
	n.face_to(player.position)
	player.facing = 1 if n.position.x > player.position.x else -1
	player.view = "side"
	dlg_lines = n.talk.duplicate()
	dlg_name.text = n.cname
	if not talked.has(n.cid):
		talked[n.cid] = true
		friend[n.cid] = int(friend.get(n.cid, 0)) + 20
		_emote(n, "heart", 1.6)
	_draw_hearts(int(friend.get(n.cid, 0)))
	_dlg_next()


func _portrait(cid: String, face: String) -> Texture2D:
	for f in [face, "neutral"]:
		var p := DATA + "portraits/%s/%s.png" % [cid, f]
		if ResourceLoader.exists(p):
			return load(p)
	return null


func _dlg_next() -> void:
	if dlg_lines.is_empty():
		dlg.visible = false
		if player.special == "laugh":
			player.stop_special()
		if dlg_npc:
			if dlg_npc.special == "laugh":
				dlg_npc.stop_special()
			dlg_npc.talking = false
		dlg_npc = null
		return
	var L = dlg_lines.pop_front()
	if dlg_npc and dlg_npc.special == "laugh":
		dlg_npc.stop_special()
	if player.special == "laugh":
		player.stop_special()
	var face: String = dlg_npc.mood_face() if dlg_npc else "neutral"
	if L is Dictionary:
		dlg_text.text = L.get("t", "")
		if L.has("anim") and dlg_npc and dlg_npc.has_anim(L["anim"]):
			dlg_npc.play_special(L["anim"])
		if L.has("hero") and player.has_anim(L["hero"]):
			player.play_special(L["hero"])
		face = L.get("face", "laugh" if L.get("anim", "") == "laugh" else face)
		if L.has("emote") and dlg_npc:
			_emote(dlg_npc, L["emote"], 1.6)
	else:
		dlg_text.text = str(L)
	dlg_portrait.texture = _portrait(dlg_npc.cid, face) if dlg_npc else null
	dlg_portrait.flip_h = false
	dlg.visible = true


func _draw_hearts(points: int) -> void:
	for c in dlg_hearts.get_children():
		c.queue_free()
	for i in 10:
		var v := clampi(points - i * 100, 0, 100)
		var tr := TextureRect.new()
		tr.texture = heart_tex[2 if v >= 100 else (1 if v >= 50 else 0)]
		tr.stretch_mode = TextureRect.STRETCH_KEEP
		dlg_hearts.add_child(tr)


func _make_hearts() -> void:
	## 程序画的 9x8 像素爱心：空 / 半 / 满
	var shape := ["011000110", "111101111", "111111111", "111111111", "011111110", "001111100", "000111000", "000010000"]
	for kind in 3:
		var img := Image.create(9, 8, false, Image.FORMAT_RGBA8)
		for y in 8:
			for x in 9:
				if shape[y][x] == "1":
					var edge: bool = (x == 0 or y == 0 or x == 8 or shape[y][x - 1] == "0" or shape[y][x + 1] == "0" or (y > 0 and shape[y - 1][x] == "0") or (y < 7 and shape[y + 1][x] == "0"))
					var fill: bool = kind == 2 or (kind == 1 and x <= 4)
					img.set_pixel(x, y, Color("3a1a12") if edge else (Color("e0483e") if fill else Color("6b4a3a")))
		heart_tex.append(ImageTexture.create_from_image(img))


func _emote(who: Node2D, name: String, secs: float) -> void:
	var p := DATA + "portraits/emotes/%s.png" % name
	if not ResourceLoader.exists(p) or not is_instance_valid(who):
		return
	var sp := Sprite2D.new()
	sp.texture = load(p)
	var h: float = 110.0
	if who.anims.has(who.cur):
		h = who.anims[who.cur]["oy"]
	sp.position = Vector2(0, -h - 14)
	sp.z_index = 55
	who.add_child(sp)
	var tw := sp.create_tween()
	tw.tween_property(sp, "position:y", sp.position.y - 4, 0.25).set_trans(Tween.TRANS_BACK)
	tw.tween_interval(secs)
	tw.tween_callback(sp.queue_free)


func _update_prompt() -> void:
	var txt := ""
	if not busy and dlg_npc == null:
		for n in npcs:
			var d: Vector2 = n.position - player.position
			if n.visible and not n.talk.is_empty() and absf(d.x) < 46 and absf(d.y) < 18:
				txt = "空格  和" + n.cname + "说话"
				break
		if txt == "" and player.special in ["sit_bench"]:
			txt = "空格 / 方向键  起身"
		if txt == "" and _near_dog() and player.special == "":
			txt = "空格  摸摸" + _near_dog().cname
		if txt == "" and not _near_spot().is_empty() and player.special == "":
			txt = "空格  坐下"
		if txt == "":
			var door: Dictionary = scene.door_at(player.position)
			if not door.is_empty():
				txt = ("W  进入 " if door.has("interior") else "") + door.get("label", "")
		if txt == "":
			var z: Dictionary = scene.zebra_at(player.position)
			if not z.is_empty():
				txt = "S  过马路 → " + z.get("label", "")
		if txt == "" and scene.data.get("kind", "") == "interior" and player.position.y > scene.band.y - 14:
			txt = "S  出门"
		var ex: Dictionary = scene.exits
		if txt == "" and player.position.x < 70 and ex.get("left") != null:
			txt = "←  " + ex["left"].get("label", "")
		elif txt == "" and player.position.x > scene.width - 70 and ex.get("right") != null:
			txt = ex["right"].get("label", "") + "  →"
	prompt.text = txt
	prompt.visible = txt != "" and not photo and not player.has_meta("bubble")
	var sp: Vector2 = player.get_global_transform_with_canvas().origin
	prompt.size = prompt.get_combined_minimum_size()      # 刚换文字的这一帧 size 还没更新，按最小尺寸算，否则提示牌会偏
	var top: float = 120.0
	if player.anims.has(player.cur):
		top = player.anims[player.cur]["oy"] + 8
	prompt.position = Vector2(roundf(clampf(sp.x - prompt.size.x / 2, 2, VIEW.x - prompt.size.x - 2)), roundf(maxf(2, sp.y - top - prompt.size.y)))


func _bubble(who: Node2D, text: String, secs: float) -> void:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", px_font)
	l.add_theme_font_size_override("font_size", 12)
	l.add_theme_color_override("font_color", Color("3a2116"))
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color("fff4dc")
	sb.border_color = Color("3a2116")
	sb.set_border_width_all(1)
	sb.content_margin_left = 4; sb.content_margin_right = 4; sb.content_margin_top = 1; sb.content_margin_bottom = 2
	l.add_theme_stylebox_override("normal", sb)
	var h: float = 120.0
	if who.has_method("load_char") and who.anims.has(who.cur):
		h = who.anims[who.cur]["oy"] + 10
	l.position = Vector2(-20, -h - 6)
	l.z_index = 50
	who.add_child(l)
	who.set_meta("bubble", true)
	l.tree_exiting.connect(func(): if is_instance_valid(who) and who.has_meta("bubble"): who.remove_meta("bubble"))
	var tw := l.create_tween()      # 跟着气泡自己走：换场景时一起销毁，不会访问已释放的对象
	tw.tween_interval(secs)
	tw.tween_callback(l.queue_free)


# ---------------------------------------------------------------- 座位、狗、拍照、烟、BGM
func spot(id: String) -> Dictionary:
	for sp in world.get("spots", {}).get(scene_id, []):
		if sp["id"] == id:
			return sp
	return {}


func spot_taken(id: String, who: Node) -> bool:
	return spots_taken.has(id) and spots_taken[id] != who


func occupy(id: String, who: Node) -> void:
	spots_taken[id] = who


func release(id: String) -> void:
	spots_taken.erase(id)


func find_npc(cid: String) -> Node2D:
	for n in npcs:
		if n.cid == cid:
			return n
	return null


func _near_dog() -> Node2D:
	for n in npcs:
		if n.cid == "wangcai" and n.visible:
			var d: Vector2 = n.position - player.position
			if absf(d.x) < 50 and absf(d.y) < 16:
				return n
	return null


func _near_spot() -> Dictionary:
	for sp in world.get("spots", {}).get(scene_id, []):
		if not sp.get("player", true) or spots_taken.has(sp["id"]):
			continue
		var d := Vector2(sp["x"], sp["y"]) - player.position
		if absf(d.x) < 30 and absf(d.y) < 20 and player.has_anim(sp.get("hero_anim", "sit_bench")):
			return sp
	return {}


func _player_sit(sp: Dictionary) -> void:
	player.position = Vector2(sp["x"], sp["y"])
	player.view = sp.get("hero_view", "front")
	occupy(sp["id"], player)
	player.set_meta("spot", sp["id"])
	player.play_special(sp.get("hero_anim", "sit_bench"))


func _player_pet(dog: Node2D) -> void:
	var side := 1.0 if dog.position.x > player.position.x else -1.0
	player.facing = int(side)
	player.view = "side"
	var hp = player.anims["pet_dog"]["meta"].get("hand_point", [30, -35])
	player.position = Vector2(dog.position.x - side * float(hp[0]), dog.position.y)
	player.play_special("pet_dog")
	dog.petted_by(player, 3.0)
	var tw := create_tween()
	tw.tween_interval(3.0)
	tw.tween_callback(func(): if player.special == "pet_dog": _player_stand())


func _player_stand() -> void:
	if player.has_meta("spot"):
		release(player.get_meta("spot"))
		player.remove_meta("spot")
		player.position.y += 6
	player.stop_special()


func _take_photo() -> void:
	if busy or dlg_npc != null or not player.has_anim("photo"):
		_shot()
		return
	if player.special != "":
		_player_stand()
	player.view = "side"
	player.play_special("photo")
	player.set_meta("shot_done", false)


func _photo_tick() -> void:
	var sf := int(player.anims["photo"]["meta"].get("shutter_frame", 3))
	if player.frame >= sf and not player.get_meta("shot_done", false):
		player.set_meta("shot_done", true)
		var was := help_label.visible
		loc_label.visible = false; help_label.visible = false; prompt.visible = false
		if DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
		_shot()
		loc_label.visible = true; help_label.visible = was
		flash.color.a = 0.85
		create_tween().tween_property(flash, "color:a", 0.0, 0.35)
	if player.special_done:
		_player_stand()


func _smoke_tick(n: Node2D) -> void:
	if n.special != "smoke" or not n.visible:
		return
	var m: Dictionary = n.anims["smoke"]["meta"]
	var sf := int(m.get("smoke_frame", 4))
	if n.frame == sf and smoke_mark.get(n, -1) != n.frame:
		smoke_mark[n] = n.frame
		var mp = m.get("mouth_point", [18, -88])
		var base: Vector2 = n.position + Vector2(float(mp[0]) * n.facing, float(mp[1]))
		for i in 6:
			var px := ColorRect.new()
			px.size = Vector2(2, 2)
			px.color = Color(0.86, 0.84, 0.82, 0.85)
			px.position = base + Vector2(randf_range(-2, 2), randf_range(-2, 1))
			px.z_index = 60
			scene.add_child(px)
			var tw := create_tween().set_parallel(true)
			var dt := randf_range(1.2, 2.0)
			tw.tween_property(px, "position", px.position + Vector2(randf_range(2, 10) * n.facing, -randf_range(14, 26)), dt)
			tw.tween_property(px, "color:a", 0.0, dt)
			tw.chain().tween_callback(px.queue_free)
	elif n.frame != sf:
		smoke_mark[n] = -1


func _mood_emote(n: Node2D, delta: float) -> void:
	## 心情：偶尔在头顶冒情绪气泡（开心 ♪、累 …、忙 汗滴、生气 怒）
	var cd: float = emote_cd.get(n, randf_range(4.0, 12.0)) - delta
	if cd <= 0.0:
		cd = randf_range(9.0, 18.0)
		var e: String = {"happy": "music", "tired": "dots", "busy": "sweat", "annoyed": "anger", "sleepy": "sleepy"}.get(n.mood, "")
		if e != "" and n.visible and not n.talking:
			_emote(n, e, 1.4)
	emote_cd[n] = cd


func _play_bgm(path: String) -> void:
	if path == bgm_path:
		return
	bgm_path = path
	if path == "" or not ResourceLoader.exists(DATA + path):
		var tw0 := create_tween()
		tw0.tween_property(bgm, "volume_db", -40.0, 0.6)
		tw0.tween_callback(bgm.stop)
		return
	var st: AudioStream = load(DATA + path)
	if "loop" in st:
		st.set("loop", true)
	var tw := create_tween()
	if bgm.playing:
		tw.tween_property(bgm, "volume_db", -40.0, 0.6)
	tw.tween_callback(func(): bgm.stream = st; bgm.volume_db = -40.0; bgm.play())
	tw.tween_property(bgm, "volume_db", -8.0, 1.2)


# ---------------------------------------------------------------- 界面
func _build_hud() -> void:
	hud = CanvasLayer.new()
	add_child(hud)
	fade = ColorRect.new()
	fade.color = Color(0.08, 0.05, 0.04, 0.0)
	fade.size = VIEW
	fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	loc_label = _label(Vector2(8, 6), 12, Color("fff4dc"))
	help_label = _label(Vector2(8, VIEW.y - 18), 12, Color("fff4dc"))
	clock_label = _label(Vector2(VIEW.x - 64, 6), 12, Color("fff4dc"))
	help_label.text = "WASD 走（可斜走）  Shift 跑  空格 说话/进门/坐下/摸狗  P 拍照  T 时间快进  H 隐藏  Esc 退出"
	prompt = _label(Vector2.ZERO, 12, Color("3a2116"))
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(1.0, 0.96, 0.86, 0.92)
	sb.border_color = Color("3a2116"); sb.set_border_width_all(1)
	sb.content_margin_left = 4; sb.content_margin_right = 4; sb.content_margin_top = 1; sb.content_margin_bottom = 2
	prompt.add_theme_stylebox_override("normal", sb)
	card = _label(Vector2(0, 220), 12, Color("fff4dc"))
	card.size = Vector2(VIEW.x, 24)
	card.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.add_theme_font_size_override("font_size", 24)
	card.visible = false
	_make_hearts()
	dlg = PanelContainer.new()
	var ps := StyleBoxFlat.new()
	ps.bg_color = Color("f3e2c0")
	ps.border_color = Color("6b3e22"); ps.set_border_width_all(3)
	ps.corner_radius_top_left = 4; ps.corner_radius_top_right = 4; ps.corner_radius_bottom_left = 4; ps.corner_radius_bottom_right = 4
	ps.content_margin_left = 10; ps.content_margin_right = 12; ps.content_margin_top = 8; ps.content_margin_bottom = 8
	dlg.add_theme_stylebox_override("panel", ps)
	dlg.position = Vector2(90, 398)
	dlg.custom_minimum_size = Vector2(780, 128)
	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 12)
	dlg.add_child(hb)
	var pf := PanelContainer.new()
	var pfs := StyleBoxFlat.new()
	pfs.bg_color = Color("d9b98a"); pfs.border_color = Color("6b3e22"); pfs.set_border_width_all(2)
	pf.add_theme_stylebox_override("panel", pfs)
	dlg_portrait = TextureRect.new()
	dlg_portrait.custom_minimum_size = Vector2(96, 96)
	dlg_portrait.stretch_mode = TextureRect.STRETCH_KEEP_CENTERED
	dlg_portrait.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	pf.add_child(dlg_portrait)
	hb.add_child(pf)
	var vb := VBoxContainer.new()
	vb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vb.add_theme_constant_override("separation", 4)
	hb.add_child(vb)
	var top := HBoxContainer.new()
	dlg_name = Label.new(); _style(dlg_name, 12, Color("6b3e22"))
	top.add_child(dlg_name)
	var gap := Control.new(); gap.custom_minimum_size = Vector2(10, 1); top.add_child(gap)
	dlg_hearts = HBoxContainer.new(); dlg_hearts.add_theme_constant_override("separation", 1)
	top.add_child(dlg_hearts)
	vb.add_child(top)
	dlg_text = Label.new(); _style(dlg_text, 12, Color("3a2116"))
	dlg_text.autowrap_mode = TextServer.AUTOWRAP_ARBITRARY
	dlg_text.custom_minimum_size = Vector2(620, 60)
	vb.add_child(dlg_text)
	var more := Label.new(); _style(more, 12, Color("9a5a2a")); more.text = "空格 ▶"
	more.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	vb.add_child(more)
	dlg.visible = false
	hud.add_child(dlg)
	flash = ColorRect.new()
	flash.color = Color(1, 1, 1, 0)
	flash.size = VIEW
	flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(flash)
	hud.add_child(fade)
	bgm = AudioStreamPlayer.new()
	bgm.volume_db = -8.0
	add_child(bgm)


func _style(l: Label, size: int, c: Color) -> void:
	l.add_theme_font_override("font", px_font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", c)


func _label(pos: Vector2, size: int, c: Color) -> Label:
	var l := Label.new()
	_style(l, size, c)
	var bgsb := StyleBoxFlat.new()
	bgsb.bg_color = Color(0.13, 0.08, 0.05, 0.55)
	bgsb.content_margin_left = 4; bgsb.content_margin_right = 4; bgsb.content_margin_top = 1; bgsb.content_margin_bottom = 2
	l.add_theme_stylebox_override("normal", bgsb)
	l.position = pos
	hud.add_child(l)
	return l


func _toggle_photo() -> void:
	photo = not photo
	loc_label.visible = not photo
	help_label.visible = not photo


func _shot() -> void:
	shots_saved += 1
	if DisplayServer.get_name() == "headless":
		return
	var img := get_viewport().get_texture().get_image()
	if img == null:
		return
	var dir := ProjectSettings.globalize_path("res://").path_join("../截图")
	DirAccess.make_dir_recursive_absolute(dir)
	var f := dir.path_join("我亦是行人_%s_%d.png" % [Time.get_datetime_string_from_system().replace(":", "-"), shots_saved])
	img.save_png(f)
	_bubble(player, "已保存截图", 1.2)


# ---------------------------------------------------------------- 自动演示（录视频用）
## demo.json: {start:{scene,x,y}, steps:[{x:1,y:0,run:false,t:2.0} | {act:"interact"} | {act:"wait",t:1} | {act:"photo"}]}
func _demo_tick(delta: float) -> Array:
	if busy or demo_i >= demo.size():
		if demo_i >= demo.size() and not busy:
			demo_t += delta
			if demo_t > 1.5 and args.has("quit_after_demo"):
				get_tree().quit()
		return [Vector2.ZERO, false]
	var s: Dictionary = demo[demo_i]
	if s.has("act"):
		match s["act"]:
			"interact":
				_interact(); demo_i += 1
			"down":
				var z: Dictionary = scene.zebra_at(player.position)
				if not z.is_empty(): _cross(z)
				demo_i += 1
			"wait":
				demo_t += delta
				if demo_t >= float(s["t"]):
					demo_t = 0.0; demo_i += 1
			"photo":
				_toggle_photo(); demo_i += 1
			"approach":
				var n := find_npc(s["npc"])
				if n == null:
					demo_i += 1; return [Vector2.ZERO, false]
				var off := float(s.get("dx", 34.0))
				var tgt2: Vector2 = n.position + Vector2(-off if player.position.x < n.position.x else off, 0)
				var d2 := tgt2 - player.position
				var w2 := Vector2(signf(d2.x) if absf(d2.x) > 4.0 else 0.0, signf(d2.y) if absf(d2.y) > 3.0 else 0.0)
				demo_t += delta
				if w2 == Vector2.ZERO or demo_t > float(s.get("max", 15.0)):
					demo_t = 0.0; demo_i += 1
					return [Vector2.ZERO, false]
				return [w2, bool(s.get("run", false))]
			"take_photo":
				_take_photo(); demo_i += 1
			"time":
				var hm2: PackedStringArray = str(s["v"]).split(":")
				ambient.minutes = float(hm2[0]) * 60.0 + (float(hm2[1]) if hm2.size() > 1 else 0.0)
				demo_i += 1
			"fast":
				ambient.fast = bool(s.get("on", true)); demo_i += 1
			"say_hero":
				_bubble(player, str(s["t"]), float(s.get("secs", 2.0))); demo_i += 1
			"stand":
				if player.special != "": _player_stand()
				demo_i += 1
			"walkto":
				var tgt := Vector2(float(s.get("x", player.position.x)), float(s.get("y", player.position.y)))
				var d := tgt - player.position
				var w := Vector2(signf(d.x) if absf(d.x) > 3.0 else 0.0, signf(d.y) if absf(d.y) > 2.0 else 0.0)
				demo_t += delta
				if w == Vector2.ZERO or demo_t > float(s.get("max", 12.0)):
					demo_t = 0.0; demo_i += 1
					return [Vector2.ZERO, false]
				return [w, bool(s.get("run", false))]
			"talk":
				if dlg_npc == null and demo_t == 0.0:
					_interact()
				demo_t += delta
				if demo_t >= float(s.get("each", 2.4)):
					demo_t = 0.001
					_dlg_next()
					if dlg_npc == null:
						demo_t = 0.0; demo_i += 1
			_:
				demo_i += 1
		return [Vector2.ZERO, false]
	demo_t += delta
	if demo_t >= float(s.get("t", 1.0)) or (s.has("until_x") and absf(player.position.x - float(s["until_x"])) < 3.0):
		demo_t = 0.0
		demo_i += 1
	return [Vector2(s.get("x", 0), s.get("y", 0)), bool(s.get("run", false))]
