extends Node2D
## 对话气泡：挂在角色头上，显示几秒后消失。中文用系统字体（微软雅黑等）。

static var font: SystemFont


static func make(text: String, secs: float = 2.8) -> Node2D:
	if font == null:
		font = SystemFont.new()
		font.font_names = PackedStringArray(["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei"])
		font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	var b := Node2D.new()
	b.set_script(load("res://scripts/bubble.gd"))
	var lab := Label.new()
	lab.text = text
	lab.add_theme_font_override("font", font)
	lab.add_theme_font_size_override("font_size", 11)
	lab.add_theme_color_override("font_color", Color8(62, 39, 25))
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color8(255, 248, 232)
	sb.border_color = Color8(62, 39, 25)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(3)
	sb.content_margin_top = 1
	sb.content_margin_bottom = 1
	lab.add_theme_stylebox_override("normal", sb)
	b.add_child(lab)
	b.set_meta("life", secs)
	b.z_as_relative = false
	b.z_index = 200
	return b


func _ready() -> void:
	var lab: Label = get_child(0)
	await get_tree().process_frame
	lab.position = Vector2(round(-lab.size.x / 2.0), -60.0)


func _process(delta: float) -> void:
	var l: float = get_meta("life") - delta
	set_meta("life", l)
	if l <= 0.0:
		queue_free()
