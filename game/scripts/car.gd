extends AnimatableBody2D
## 车辆：沿车道折线匀速行驶。loop=true 绕圈；false 开到终点后回到起点（穿城直行）。
## 前方传感器碰到人/车就停：前面是人就一直等（人可以随便过马路）；前面是车且停超过 2.5 秒（防路口互等）才强行通过。贴图：右/下/上（左 = 右翻转）。原点 = 车身中心。

var pts: PackedVector2Array
var seg := 0
var speed := 42.0
var loop := true
var tex := {}
var spr: Sprite2D
var cs: CollisionShape2D
var sensor: ShapeCast2D
var stopped := 0.0
var dir := "right"
var shadow: Sprite2D
var city: Node = null       # 主场景（问红绿灯）
var red := false
var half_len := 20.0


func setup(points: Array, textures: Dictionary, spd: float, is_loop: bool) -> void:
	for p in points:
		pts.append(Vector2(p[0], p[1]))
	tex = textures
	speed = spd
	loop = is_loop
	position = pts[0]
	var sh := Sprite2D.new()      # 车底影子
	var si := Image.create(40, 8, false, Image.FORMAT_RGBA8)
	for y in 8:
		for x in 40:
			var dx := (x - 19.5) / 20.0
			var dy := (y - 3.5) / 4.0
			if dx * dx + dy * dy < 1.0:
				si.set_pixel(x, y, Color(0.1, 0.08, 0.14, 0.3))
	sh.texture = ImageTexture.create_from_image(si)
	sh.z_index = -1
	add_child(sh)
	shadow = sh
	spr = Sprite2D.new()
	spr.centered = false
	add_child(spr)
	cs = CollisionShape2D.new()
	cs.shape = RectangleShape2D.new()
	add_child(cs)
	sensor = ShapeCast2D.new()
	sensor.shape = RectangleShape2D.new()
	sensor.collision_mask = 2 | 4
	sensor.target_position = Vector2.ZERO
	sensor.add_exception(self)
	add_child(sensor)
	_face(pts[1] - pts[0])


func _face(v: Vector2) -> void:
	if absf(v.x) >= absf(v.y):
		dir = "right" if v.x > 0 else "left"
	else:
		dir = "down" if v.y > 0 else "up"
	var key := "right" if dir == "left" else dir
	if not tex.has(key):
		key = "right"
	var t: Texture2D = tex[key]
	spr.texture = t
	spr.flip_h = dir == "left"
	var w := float(t.get_width())
	var h := float(t.get_height())
	spr.offset = Vector2(-round(w / 2.0), -round(h * 0.75))   # 车身中心偏下（轮子落在车道上）
	shadow.position = Vector2(3, round(h * 0.25) - 3)
	shadow.scale = Vector2(w / 40.0 * 1.05, 1.0) if dir in ["left", "right"] else Vector2(w / 40.0, 2.0)
	var horiz := dir in ["left", "right"]
	var foot := Vector2(w * 0.9, 14.0) if horiz else Vector2(w * 0.8, h * 0.6)
	half_len = (foot.x if horiz else foot.y) / 2.0
	(cs.shape as RectangleShape2D).size = foot
	cs.position = Vector2.ZERO
	var dv: Vector2 = {"right": Vector2.RIGHT, "left": Vector2.LEFT, "down": Vector2.DOWN, "up": Vector2.UP}[dir]
	var ss := Vector2(12, 12) if horiz else Vector2(foot.x * 0.8, 12)
	(sensor.shape as RectangleShape2D).size = ss
	sensor.position = dv * ((foot.x if horiz else foot.y) / 2.0 + 10.0)


func _physics_process(delta: float) -> void:
	red = city != null and not city.car_may_go(self, dir, half_len)
	if red:
		return
	sensor.force_shapecast_update()
	if sensor.is_colliding():
		var person := false
		for i in sensor.get_collision_count():
			if sensor.get_collider(i) is CharacterBody2D:
				person = true
		if person or stopped < 2.5:
			stopped += delta
			return
	if not sensor.is_colliding():
		stopped = 0.0
	var nxt := seg + 1
	if nxt >= pts.size():
		if loop:
			nxt = 0
		else:
			global_position = pts[0]
			reset_physics_interpolation()     # 瞬移回起点，不要插值出一道残影
			seg = 0
			_face(pts[1] - pts[0])
			return
	var target := pts[nxt]
	var d := target - global_position
	var stepv := speed * delta
	if d.length() <= stepv:
		global_position = target
		seg = nxt % pts.size()
		var after := (seg + 1) % pts.size()
		if loop or after != 0:
			_face(pts[after] - pts[seg])
	else:
		global_position += d.normalized() * stepv
