extends Node2D
## 横版角色：侧面左右走（朝左用镜像）、正面/背面纵向走、斜走、站立呼吸、跑步。
## 根运动连续：第 k 帧播放期间，身体以 root_motion[k] * fps 的速度前进（侧面沿 x，正背面沿 y），脚不打滑。
## 动画资源 = char.json：{id, name, height_px, anims:{walk_side, walk_front, walk_back, idle_side, idle_front, idle_back, run_side?, ...}}
## 每个动画：{file, frames, fps, frame_w, frame_h, origin:[x,y], root_motion_px:[...], axis:"x"|"y"}

signal arrived

const DEPTH_RATIO := 0.37        # 斜走时纵向分量 = 侧面根运动 × 该比例（俯视投影 0.4 × 步幅）

var cid := ""
var cname := ""
var anims: Dictionary = {}       # name -> {tex, frames, fps, fw, fh, ox, oy, rm:Array, axis}
var spr: Sprite2D
var shadow: Sprite2D
var facing := 1                  # 1 右 / -1 左
var view := "side"               # side / front / back（站立时保持最后的朝向）
var cur := ""
var frame := 0
var acc := 0.0
var moving := false
var running := false
var band := Vector2(392, 468)    # 可走的纵深带（脚底 y 范围）
var solids: Array = []           # 场景里的脚底障碍 Rect2
var others: Array = []           # 其他角色（软阻挡）
var body_half := 9.0             # 脚底占地半宽
var speed_scale := 1.0
var special := ""                # 正在播放的特殊动画（坐、干活、吃）
var hidden_in_door := false


func load_char(path: String) -> void:
	var j: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var base := path.get_base_dir()
	cid = j.get("id", "")
	cname = j.get("name", "")
	for k in j["anims"]:
		var a: Dictionary = j["anims"][k]
		var o: Array = a.get("origin", [a["frame_w"] / 2, a["frame_h"] - 1])
		anims[k] = {"tex": _tex(base + "/" + a["file"]), "frames": int(a["frames"]), "fps": float(a.get("fps", 10)),
			"fw": int(a["frame_w"]), "fh": int(a["frame_h"]), "ox": float(o[0]), "oy": float(o[1]),
			"rm": a.get("root_motion_px", []), "axis": a.get("axis", "x"), "dir": a.get("dir_screen", [1.0, 0.0]), "view": a.get("view", ""), "loop": a.get("loop", true), "prop": a.get("prop", null), "hand": a.get("hand_point", null), "meta": a}
	shadow = Sprite2D.new()
	var w := 22
	var si := Image.create(w, 7, false, Image.FORMAT_RGBA8)
	for y in 7:
		for x in w:
			var dx := (x - (w - 1) / 2.0) / (w / 2.0)
			var dy := (y - 3.0) / 3.5
			if dx * dx + dy * dy < 1.0:
				si.set_pixel(x, y, Color(0.18, 0.1, 0.06, 0.28))
	shadow.texture = ImageTexture.create_from_image(si)
	shadow.position = Vector2(0, -1)
	add_child(shadow)
	spr = Sprite2D.new()
	spr.centered = false
	add_child(spr)
	_play("idle_side" if anims.has("idle_side") else anims.keys()[0])


static func _tex(p: String) -> Texture2D:
	if ResourceLoader.exists(p):
		return load(p)
	return ImageTexture.create_from_image(Image.load_from_file(p))


func has_anim(n: String) -> bool:
	return anims.has(n)


func _play(n: String) -> void:
	if n == cur or not anims.has(n):
		return
	var old: Dictionary = anims.get(cur, {})
	var a: Dictionary = anims[n]
	# 走 ↔ 跑切换时按周期相位换帧，不从头开始（步子不跳）
	if old.size() > 0 and (cur.begins_with("walk") or cur.begins_with("run")) and (n.begins_with("walk") or n.begins_with("run")):
		frame = int(floor(float(frame) / old["frames"] * a["frames"])) % a["frames"]
	else:
		frame = 0
		acc = 0.0
	cur = n
	spr.texture = a["tex"]
	spr.hframes = a["frames"]
	spr.vframes = 1
	_update_frame()


func _update_frame() -> void:
	var a: Dictionary = anims[cur]
	spr.frame = frame % a["frames"]
	var mirror: bool = facing < 0 and (cur.ends_with("_side") or cur.begins_with("walk_diag") or a.get("view", "") == "side")
	spr.flip_h = mirror
	spr.offset = Vector2(-(a["fw"] - a["ox"]) if mirror else -a["ox"], -a["oy"])


## 每帧调用。want: x ∈ {-1,0,1}，y ∈ {-1,0,1}（-1 = 往里/背面，+1 = 往外/正面）。返回实际位移。
func drive(want: Vector2, run: bool, delta: float) -> Vector2:
	if special != "":
		return Vector2.ZERO
	if want == Vector2.ZERO:
		moving = false
		_play("idle_" + view if anims.has("idle_" + view) else "idle_side")
		_advance(delta, false)
		return Vector2.ZERO
	moving = true
	var n := ""
	var diag := false
	if want.x != 0:
		facing = 1 if want.x > 0 else -1
		view = "side"
		if want.y != 0 and not run:
			# 斜走：右前斜（向右下）/ 右后斜（向右上），朝左镜像
			n = "walk_diagf" if want.y > 0 else "walk_diagb"
			diag = anims.has(n)
		if not diag:
			n = "run_side" if run and anims.has("run_side") else "walk_side"
	else:
		view = "front" if want.y > 0 else "back"
		n = "walk_" + view
		if not anims.has(n):
			n = "walk_side"
	running = n.begins_with("run")
	_play(n)
	var a: Dictionary = anims[cur]
	var rm: Array = a["rm"]
	var v := 0.0
	if rm.size() > 0:
		v = float(rm[frame % rm.size()]) * a["fps"] * speed_scale
	var mv := Vector2.ZERO
	if a["axis"] == "dir":
		mv = Vector2(v * a["dir"][0] * facing, v * absf(a["dir"][1]) * signf(want.y)) * delta
	elif a["axis"] == "x":
		mv.x = v * facing * delta
		if want.y != 0:
			mv.y = v * DEPTH_RATIO * want.y * delta
	else:
		mv.y = v * want.y * delta
	mv = _collide(mv)
	position += mv
	_advance(delta, true)
	return mv


func _advance(delta: float, _walking: bool) -> void:
	var a: Dictionary = anims[cur]
	acc += delta * a["fps"] * (speed_scale if moving else 1.0)
	while acc >= 1.0:
		acc -= 1.0
		if special != "" and not a.get("loop", true) and frame >= a["frames"] - 1:
			special_done = true
			break
		frame = (frame + 1) % a["frames"]
	_update_frame()


func _foot_rect(p: Vector2) -> Rect2:
	return Rect2(p.x - body_half, p.y - 3, body_half * 2, 6)


func _blocked(p: Vector2) -> bool:
	if p.y < band.x or p.y > band.y:
		return true
	var r := _foot_rect(p)
	for s in solids:
		if r.intersects(s):
			return true
	for o in others:
		if o == self or not is_instance_valid(o) or o.hidden_in_door or not o.visible:
			continue
		var d: Vector2 = o.position - p
		if absf(d.x) < (body_half + o.body_half) * 0.8 and absf(d.y) < 6:
			# 只挡"往对方身上走"的方向，已经重叠时允许走开
			var now: Vector2 = o.position - position
			if d.length() < now.length():
				return true
	return false


func _collide(mv: Vector2) -> Vector2:
	var p := position
	var out := Vector2.ZERO
	if mv.x != 0 and not _blocked(p + Vector2(mv.x, 0)):
		out.x = mv.x
	if mv.y != 0 and not _blocked(p + Vector2(out.x, mv.y)):
		out.y = mv.y
	return out


func play_special(n: String) -> void:
	if anims.has(n):
		special = n
		special_done = false
		cur = ""
		_play(n)


func stop_special() -> void:
	special = ""
	special_done = false
	_play("idle_" + view if anims.has("idle_" + view) else "idle_side")


## 一次性动作（拍照、蹦跳）播完后停在最后一帧，special_done = true
var special_done := false


func _process(delta: float) -> void:
	if special != "":
		_advance(delta, false)
	z_index = 0
