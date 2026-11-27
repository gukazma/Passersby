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
var x_range := Vector2(-1e9, 1e9) # 可走的横向范围
var solids: Array = []           # 场景里的脚底障碍 Rect2
var others: Array = []           # 其他角色（软阻挡）
var body_half := 9.0             # 脚底占地半宽
var speed_scale := 1.0
var special := ""                # 正在播放的特殊动画（坐、干活、吃）
var hidden_in_door := false
var step_cb: Callable             # 落脚帧回调（脚步声）
var hold := 0.0                  # 被挡后至少站这么久，防止走/站来回闪
var slide_dir := 0.0             # 正在往哪边让步（定了就不改，防止上下来回抖）
var slide_t := 0.0
var kind := "person"             # person / dog / cat / bird（动物不挡人，人也不挡动物）


func load_char(path: String) -> void:
	var j: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var base := path.get_base_dir()
	cid = j.get("id", "")
	cname = j.get("name", "")
	kind = j.get("kind", "person")
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
## 先按意图选动画、算根运动位移、做碰撞；再按「实际」位移决定播什么：
##   横向被挡但能纵向走 → 换正/背面走（各用各的根运动，不打滑）；被挡 → 站住并保持 block_hold 秒，
##   不会每帧在走/站之间来回切（A1.4 用户：「碰撞物体的时候转向和移动脚就会抽风」）。
func drive(want: Vector2, run: bool, delta: float) -> Vector2:
	if special != "":
		return Vector2.ZERO
	hold = maxf(0.0, hold - delta)
	if want == Vector2.ZERO:
		_stand(delta)
		return Vector2.ZERO
	if want.x != 0:
		facing = 1 if want.x > 0 else -1
	var mv := _try_anim(_pick_anim(want, run), want, delta)
	if mv == Vector2.INF and want.x != 0 and want.y != 0:
		# 斜着走被挡了一个方向：沿墙/楼脚横着走（侧面帧），横向也走不了就纵向走（正/背面帧）
		mv = _try_anim(_pick_anim(Vector2(want.x, 0), run), Vector2(want.x, 0), delta)
		if mv == Vector2.INF:
			mv = _try_anim(_pick_anim(Vector2(0, want.y), run), Vector2(0, want.y), delta)
	if mv == Vector2.INF and want.x != 0 and want.y == 0:
		# 横着走被小东西挡住（人、桌角）：沿纵深让一步绕过去
		mv = _slide(want, run, delta)
	elif mv != Vector2.INF:
		slide_dir = 0.0
		slide_t = 0.0
	if mv == Vector2.INF or hold > 0.0:
		if mv == Vector2.INF:
			hold = 0.15
		_stand(delta)
		return Vector2.ZERO
	moving = true
	position += mv
	_advance(delta, true)
	return mv


func _stand(delta: float) -> void:
	moving = false
	_play("idle_" + view if anims.has("idle_" + view) else "idle_side")
	_advance(delta, false)


func _pick_anim(want: Vector2, run: bool) -> String:
	if want.x != 0:
		if want.y != 0 and not run:
			var d := "walk_diagf" if want.y > 0 else "walk_diagb"
			if anims.has(d):
				return d
		return "run_side" if run and anims.has("run_side") else "walk_side"
	var n := "walk_" + ("front" if want.y > 0 else "back")
	return n if anims.has(n) else "walk_side"


## 用动画 n 的根运动算这一帧的位移并做碰撞。走不动返回 Vector2.INF（不改任何状态）。
func _try_anim(n: String, want: Vector2, delta: float) -> Vector2:
	var a: Dictionary = anims[n]
	var fr := frame
	if n != cur and cur != "" and (cur.begins_with("walk") or cur.begins_with("run")):
		fr = int(floor(float(frame) / anims[cur]["frames"] * a["frames"]))
	elif n != cur:
		fr = 0
	var rm: Array = a["rm"]
	var v := 0.0
	if rm.size() > 0:
		v = float(rm[fr % rm.size()]) * a["fps"] * speed_scale
	var mv := Vector2.ZERO
	if a["axis"] == "dir":
		mv = Vector2(v * a["dir"][0] * signf(want.x), v * absf(a["dir"][1]) * signf(want.y)) * delta
	elif a["axis"] == "x":
		mv.x = v * signf(want.x) * delta
		if want.y != 0:
			mv.y = v * DEPTH_RATIO * want.y * delta
	else:
		mv.y = v * want.y * delta
	if mv.length() < 0.0001:
		mv = Vector2(signf(want.x), signf(want.y)) * 0.01
	var got := _collide(mv)
	# 有一个分量被挡就不用这个动画（否则斜走动画配横移，脚会滑），交给上面换动画
	if not got.is_equal_approx(mv):
		return Vector2.INF
	if n.ends_with("_side") or n.begins_with("walk_diag"):
		view = "side"
	elif n == "walk_front":
		view = "front"
	elif n == "walk_back":
		view = "back"
	running = n.begins_with("run")
	_play(n)
	return got


func _slide(want: Vector2, run: bool, delta: float) -> Vector2:
	## 横着走被人/桌角挡住：看上下 3–18 px 哪边能过去，定下一个方向（不再改），用正/背面帧往那边让（脚不滑）。
	## 让了 1.2 秒还过不去就放弃，站住。
	var n := _pick_anim(want, run)
	var a: Dictionary = anims[n]
	var rm: Array = a["rm"]
	var step := Vector2(signf(want.x) * (float(rm[frame % rm.size()]) if rm.size() > 0 else 1.0) * 3.0, 0)
	if slide_dir == 0.0:
		for k in [3, 6, 9, 12, 15, 18]:
			for sgn in [1.0, -1.0]:
				var off := Vector2(0, k * sgn)
				if slide_dir == 0.0 and not _blocked(position + off) and not _blocked(position + off + step):
					slide_dir = sgn
		slide_t = 0.0
	if slide_dir == 0.0:
		return Vector2.INF
	slide_t += delta
	if slide_t > 1.2:
		return Vector2.INF
	var keep := facing
	var mv := _try_anim(_pick_anim(Vector2(0, slide_dir), false), Vector2(0, slide_dir), delta)
	facing = keep
	if mv == Vector2.INF:
		slide_dir = 0.0
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
		# 走/跑的落脚帧（第 0 帧和半周期那一帧）发脚步声
		if moving and special == "" and (cur.begins_with("walk") or cur.begins_with("run")) and step_cb.is_valid():
			var half: int = maxi(1, int(a["frames"]) / 2)
			if frame % half == 0:
				step_cb.call(self)
	_update_frame()


func _foot_rect(p: Vector2) -> Rect2:
	return Rect2(p.x - body_half, p.y - 3, body_half * 2, 6)


func _blocked(p: Vector2) -> bool:
	if p.y < band.x or p.y > band.y or p.x < x_range.x or p.x > x_range.y:
		return true
	var r := _foot_rect(p)
	for s in solids:
		if r.intersects(s):
			return true
	for o in others:
		if o == self or not is_instance_valid(o) or o.hidden_in_door or not o.visible:
			continue
		if o.kind != "person" or kind != "person":
			continue    # 只有人挡人；猫狗小，人从旁边走过去，猫狗之间也不互相卡住
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
