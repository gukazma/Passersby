extends Node2D
## 一个横版场景（街段或室内），从 json 搭建：
## {id, name, kind:"street"|"interior", width, band:[y0,y1], layers:[{img,x,y,parallax,z?}], props:[{img,x,y_foot,solid:[w,h],ox?}],
##  doors:[{id,label,x0,x1,interior?}], exits:{left:{to,label}, right:{to,label}}, zebras:[{x0,x1,to,label}],
##  entry:{x,y}（室内：从下沿进来的位置）, scale_ruler?:bool}
## 图片路径相对 json 所在目录。

var data: Dictionary = {}
var base := ""
var width := 960
var band := Vector2(392, 468)
var solids: Array = []
var ysort: Node2D
var par_layers: Array = []       # [sprite, parallax, x0]
var doors: Array = []
var zebras: Array = []
var exits: Dictionary = {}
var x_range := Vector2(-1e9, 1e9)   # 可走的横向范围（室内 = 房间内）


func build(path: String) -> void:
	data = JSON.parse_string(FileAccess.get_file_as_string(path))
	base = path.get_base_dir()
	width = int(data.get("width", 960))
	var b: Array = data.get("band", [392, 468])
	band = Vector2(b[0], b[1])
	doors = data.get("doors", [])
	zebras = data.get("zebras", [])
	exits = data.get("exits", {})
	var xr: Array = data.get("x_range", [])
	if xr.size() == 2:
		x_range = Vector2(xr[0], xr[1])
	for L in data.get("layers", []):
		var s := _sprite(L["img"])
		if s == null:
			continue
		s.position = Vector2(L.get("x", 0), L.get("y", 0))
		s.z_index = int(L.get("z", -10))
		add_child(s)
		var p := float(L.get("parallax", 1.0))
		if p != 1.0:
			par_layers.append([s, p, s.position.x])
	ysort = Node2D.new()
	ysort.y_sort_enabled = true
	add_child(ysort)
	for P in data.get("props", []):
		var s := _sprite(P["img"])
		if s == null:
			continue
		var tex_h := s.texture.get_height()
		var tex_w := s.texture.get_width()
		var holder := Node2D.new()
		holder.position = Vector2(P["x"], P["y_foot"])
		s.position = Vector2(-float(P.get("ox", tex_w / 2.0)), -float(P.get("oy", tex_h)))
		holder.add_child(s)
		ysort.add_child(holder)
		var so: Array = P.get("solid", [])
		if so.size() == 2 and so[0] > 0:
			solids.append(Rect2(P["x"] - so[0] / 2.0, P["y_foot"] - so[1], so[0], so[1]))


func add_prop(P: Dictionary) -> void:
	## world.json 里补充的道具（凳子等），格式同场景 props；img 可以是 res:// 绝对路径
	var s: Sprite2D
	if str(P["img"]).begins_with("res://"):
		s = Sprite2D.new(); s.centered = false
		var pth: String = P["img"]
		s.texture = load(pth) if ResourceLoader.exists(pth) else (ImageTexture.create_from_image(Image.load_from_file(pth)) if FileAccess.file_exists(pth) else null)
		if s.texture == null:
			push_error("补摆道具缺图 " + pth)
			return
	else:
		s = _sprite(P["img"])
	if s == null:
		return
	var holder := Node2D.new()
	holder.position = Vector2(P["x"], P["y_foot"])
	s.position = Vector2(-s.texture.get_width() / 2.0, -s.texture.get_height() - float(P.get("lift", 0)))
	holder.add_child(s)
	ysort.add_child(holder)
	var so: Array = P.get("solid", [])
	if so.size() == 2 and so[0] > 0:
		solids.append(Rect2(P["x"] - so[0] / 2.0, P["y_foot"] - so[1], so[0], so[1]))


func _sprite(rel: String) -> Sprite2D:
	var p := base + "/" + rel
	if not FileAccess.file_exists(p):
		push_warning("缺图 " + p)
		return null
	var s := Sprite2D.new()
	s.centered = false
	s.texture = load(p) if ResourceLoader.exists(p) else ImageTexture.create_from_image(Image.load_from_file(p))
	return s


func add_actor(a: Node2D) -> void:
	ysort.add_child(a)


func update_parallax(cam_left: float) -> void:
	for e in par_layers:
		e[0].position.x = e[2] + cam_left * (1.0 - e[1])


func door_at(p: Vector2) -> Dictionary:
	for d in doors:
		if p.x >= d["x0"] and p.x <= d["x1"] and p.y <= band.x + 16:
			return d
	return {}


func zebra_at(p: Vector2) -> Dictionary:
	for z in zebras:
		if p.x >= z["x0"] and p.x <= z["x1"] and p.y >= band.y - 10:
			return z
	return {}


func door_by_id(id: String) -> Dictionary:
	for d in doors:
		if d["id"] == id:
			return d
	return {}
