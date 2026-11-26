extends Node2D
## 环境：水面闪光（池塘 + 河）、喷泉水花、云影。

var pond := Vector4.ZERO        # cx, cy, rx, ry
var river_y := 0.0
var world := Vector2.ZERO
var sparkles: Array = []
var rng := RandomNumberGenerator.new()
var acc := 0.0


func setup(p: Array, ry: float, ws: Vector2, fountain: Vector2) -> void:
	pond = Vector4(p[0], p[1], p[2], p[3])
	river_y = ry
	world = ws
	for i in 70:
		sparkles.append(_new_sparkle())
	if fountain == Vector2.INF:
		_clouds(ws)
		return
	# 喷泉水花
	var parts := CPUParticles2D.new()
	parts.position = fountain + Vector2(0, -44)
	parts.amount = 26
	parts.lifetime = 0.8
	parts.direction = Vector2(0, -1)
	parts.spread = 25.0
	parts.initial_velocity_min = 26.0
	parts.initial_velocity_max = 38.0
	parts.gravity = Vector2(0, 90)
	parts.scale_amount_min = 1.0
	parts.scale_amount_max = 1.0
	parts.color = Color8(210, 236, 244)
	parts.z_index = 40
	add_child(parts)
	_clouds(ws)


func _clouds(ws: Vector2) -> void:
	# 云影：抖动点阵的大椭圆，半透明，慢慢往右下飘
	for i in 4:
		var s := Sprite2D.new()
		s.texture = _cloud_tex(rng.randi_range(160, 260), rng.randi_range(70, 110))
		s.position = Vector2(rng.randf_range(0, ws.x), rng.randf_range(0, ws.y))
		s.modulate = Color(0.12, 0.1, 0.18, 0.16)
		s.z_index = 100
		s.set_meta("v", Vector2(rng.randf_range(6, 10), rng.randf_range(1, 3)))
		add_child(s)


func _new_sparkle() -> Array:
	# [位置, 剩余寿命]
	if pond.z > 0.0 and rng.randf() < 0.35:
		var a := rng.randf() * TAU
		var r := sqrt(rng.randf()) * 0.85
		return [Vector2(pond.x + cos(a) * pond.z * r, pond.y + sin(a) * pond.w * r).round(), rng.randf_range(0.2, 0.9)]
	return [Vector2(rng.randf_range(0, world.x), rng.randf_range(river_y + 6, world.y - 2)).round(), rng.randf_range(0.2, 0.9)]


func _cloud_tex(w: int, h: int) -> ImageTexture:
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			var dx := (x - w / 2.0) / (w / 2.0)
			var dy := (y - h / 2.0) / (h / 2.0)
			var d := dx * dx + dy * dy
			var bayer: float = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]][y % 4][x % 4] / 16.0
			if d < 1.0 and (1.0 - d) * 1.6 > bayer:   # 边缘抖动渐隐（像素风的"软"边）
				img.set_pixel(x, y, Color(1, 1, 1, 1))
	return ImageTexture.create_from_image(img)


func _process(delta: float) -> void:
	acc += delta
	for s in sparkles:
		s[1] -= delta
		if s[1] <= 0.0:
			var n := _new_sparkle()
			s[0] = n[0]
			s[1] = n[1]
	for c in get_children():
		if c is Sprite2D and c.has_meta("v"):
			c.position += c.get_meta("v") * delta
			if c.position.x > world.x + 200:
				c.position = Vector2(-200, rng.randf_range(0, world.y))
	if acc > 0.08:
		acc = 0.0
		queue_redraw()


func _draw() -> void:
	for s in sparkles:
		var a: float = clampf(s[1] * 2.0, 0.0, 1.0)
		draw_rect(Rect2(s[0], Vector2(2, 1)), Color(0.92, 0.97, 1.0, a))
