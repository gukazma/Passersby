extends Node2D
## 鸽子：地上啄食/小跳；人或 NPC 靠近就扑腾飞走（飞行时在楼上方），飞一会儿落到附近。
## 贴图由代码画（7x5 像素），4 帧：站、低头啄、飞 1、飞 2。

var frames: Array[ImageTexture] = []
var spr: Sprite2D
var state := "ground"
var t := 0.0
var vel := Vector2.ZERO
var home := Vector2.ZERO
var rng := RandomNumberGenerator.new()
var watch: Array = []          # 会吓到鸽子的节点


static func make_frames() -> Array[ImageTexture]:
	var g := Color8(150, 150, 158)
	var d := Color8(96, 96, 108)
	var w := Color8(220, 220, 226)
	var k := Color8(40, 34, 40)
	var o := Color8(230, 150, 60)
	var pats := [
		["..dd...", ".dkdggg", "..gggg.", "...gwg.", "...o.o."],   # 站
		[".......", "...ggg.", "ddggggg", "dk.gwg.", "...o.o."],   # 啄
		["g.....g", "gg.d.gg", ".gdkdg.", "..ggg..", "......."],   # 飞（翅上）
		[".......", "..dd...", "ggdkdgg", "g.ggg.g", "......."],   # 飞（翅下）
	]
	var out: Array[ImageTexture] = []
	for p in pats:
		var img := Image.create(7, 5, false, Image.FORMAT_RGBA8)
		for y in 5:
			for x in 7:
				var c: String = p[y][x]
				var col := Color(0, 0, 0, 0)
				if c == "g": col = g
				elif c == "d": col = d
				elif c == "w": col = w
				elif c == "k": col = k
				elif c == "o": col = o
				img.set_pixel(x, y, col)
		out.append(ImageTexture.create_from_image(img))
	return out


func _ready() -> void:
	spr = Sprite2D.new()
	spr.centered = false
	spr.offset = Vector2(-3, -5)
	add_child(spr)
	spr.texture = frames[0]
	home = position
	t = rng.randf_range(0.0, 2.0)


func _process(delta: float) -> void:
	t += delta
	if state == "ground":
		spr.texture = frames[1] if fmod(t, 1.3) < 0.25 else frames[0]
		if rng.randf() < delta * 0.4:                       # 偶尔小跳一步
			position += Vector2(rng.randf_range(-3, 3), rng.randf_range(-2, 2)).round()
			spr.flip_h = rng.randf() < 0.5
		for n in watch:
			if is_instance_valid(n) and (n as Node2D).global_position.distance_to(global_position) < 30.0:
				state = "fly"
				t = 0.0
				vel = Vector2(rng.randf_range(30, 60) * (1 if rng.randf() < 0.5 else -1), rng.randf_range(-70, -50))
				spr.flip_h = vel.x < 0
				z_index = 60
				break
	elif state == "fly":
		spr.texture = frames[2] if int(t * 12.0) % 2 == 0 else frames[3]
		position += vel * delta
		vel.y += 25.0 * delta
		if t > 1.6:
			state = "land"
			t = 0.0
			var target := home + Vector2(rng.randf_range(-60, 60), rng.randf_range(-30, 30))
			vel = (target - position) / 1.2
	elif state == "land":
		spr.texture = frames[2] if int(t * 10.0) % 2 == 0 else frames[3]
		position += vel * delta
		if t > 1.2:
			state = "ground"
			z_index = 0
			t = 0.0
			position = position.round()
