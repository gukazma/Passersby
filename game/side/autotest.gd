extends Node
## 机器人自动测试（--autotest）：在真实游戏逻辑里跑，逐项断言，打印 AT PASS / AT FAIL，最后 RESULT 行并退出（失败 exit 1）。
##  1 NPC 浸泡：每个场景跑 soak 秒，检查卡住（stuck_log）、原地踏步（播行走动画但不动）、走出纵深带、站进家具碰撞
##  2 主角扫街：每条街按 里/中/外 三条线从左走到右、再走回来，记录意外被挡的位置
##  3 交互：每扇能进的门进出、每条斑马线来回、每个出口、每个座位坐下起身、摸狗、和每个人把话说完、拍照
##  4 界面：提示牌在屏幕内、和气泡不重叠、对话文字不超过两行、头像存在
## 选项：--soak=秒（默认 90）

var M: Node                       # side_main
var fails: Array = []
var passes := 0
var soak := 90.0


func ok(cond: bool, what: String) -> void:
	if cond:
		passes += 1
	else:
		fails.append(what)
		print("AT FAIL ", what)


func frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func wait_idle(max_s := 6.0) -> void:
	var t := 0.0
	while (M.busy or M.cutscene_move != Vector2.ZERO) and t < max_s:
		await get_tree().physics_frame
		t += 1.0 / 60.0


func hold(want: Vector2, secs: float, run := false) -> void:
	M.test_want = want
	M.test_run = run
	await frames(int(secs * 60))
	M.test_want = Vector2.ZERO
	M.test_run = false


func run_all() -> void:
	soak = float(M.args.get("soak", "90"))
	await frames(10)
	var ids: Array = M.world["scenes"].keys()
	# ---------- 1 NPC 浸泡
	for sid in ids:
		print("AT PHASE soak ", sid)
		M._go(sid, Vector2(60, M.scene.band.y - 4), "side", 1)
		await frames(5)
		var moon := {}
		var out := {}
		var solid := {}
		var last := {}
		for n in M.npcs:
			moon[n] = 0.0; out[n] = 0; solid[n] = 0; last[n] = n.position
		var t := 0.0
		while t < soak:
			await get_tree().physics_frame
			t += 1.0 / 60.0
			for n in M.npcs:
				var moved: float = n.position.distance_to(last[n])
				last[n] = n.position
				if (n.cur.begins_with("walk") or n.cur.begins_with("run")) and n.special == "" and moved < 0.001 and n.visible:
					moon[n] += 1.0 / 60.0
				if n.visible and not n.hidden_in_door and (n.position.y < n.band.x - 1 or n.position.y > n.band.y + 1) and n.special == "":
					out[n] += 1
				if n.visible and n.special == "" and n.loop.size() > 0:
					for r in M.scene.solids:
						if r.has_point(n.position):
							solid[n] += 1
							break
		for n in M.npcs:
			ok(n.stuck_log.is_empty(), "%s %s 卡住 %d 次：%s" % [sid, n.cname, n.stuck_log.size(), str(n.stuck_log.slice(0, 2))])
			ok(moon[n] < 0.5, "%s %s 原地踏步 %.1f 秒" % [sid, n.cname, moon[n]])
			ok(out[n] == 0, "%s %s 走出纵深带 %d 帧" % [sid, n.cname, out[n]])
			ok(solid[n] == 0, "%s %s 站进家具碰撞 %d 帧" % [sid, n.cname, solid[n]])
	# ---------- 2 主角扫街
	for sid in ids:
		print("AT PHASE sweep ", sid)
		var d: Dictionary = M.world_scene(sid)
		if d.get("kind", "street") != "street":
			continue
		M._go(sid, Vector2(30, M.scene.band.x + 2), "side", 1)
		M.test_no_edges = true
		M.player.others = [M.player]          # 扫街只查静态障碍，路过的居民不算
		var b: Vector2 = M.scene.band
		for lane in [b.x + 3, (b.x + b.y) / 2.0, b.y - 3]:
			M.player.position = Vector2(30, lane)
			var blocked := 0.0
			var spots := []
			M.test_want = Vector2(1, 0)
			while M.player.position.x < M.scene.width - 30:
				var p0: Vector2 = M.player.position
				await get_tree().physics_frame
				if M.player.position.distance_to(p0) < 0.01:
					blocked += 1.0 / 60.0
					if blocked > 1.0:
						spots.append(int(M.player.position.x))
						M.player.position.x += 40   # 跳过障碍继续扫
						blocked = 0.0
				else:
					blocked = 0.0
			M.test_want = Vector2.ZERO
			# 连续的被挡位置（间隔 < 60 px）算同一个障碍物
			var groups := 0
			var last_x := -1000
			for sx in spots:
				if sx - last_x > 60:
					groups += 1
				last_x = sx
			print("AT INFO %s 扫街 y=%d 被挡位置 %s（%d 个障碍物）" % [sid, lane, str(spots), groups])
			ok(groups <= 8, "%s 扫街 y=%d 被 %d 个障碍物挡住（太多）" % [sid, lane, groups])
			ok(lane != (b.x + b.y) / 2.0 or spots.is_empty(), "%s 人行道中线被挡：%s" % [sid, str(spots)])
		M.test_no_edges = false
	# ---------- 3 交互
	for sid in ids:
		print("AT PHASE interact ", sid)
		var d: Dictionary = M.world_scene(sid)
		for door in d.get("doors", []):
			if not door.has("interior"):
				continue
			M._go(sid, Vector2((door["x0"] + door["x1"]) / 2.0, M.scene.band.x + 4), "back", 1)
			await frames(3)
			M._interact()
			await frames(5)
			await wait_idle()
			ok(M.scene_id == door["interior"], "%s 门 %s 进不去（现在在 %s）" % [sid, door["id"], M.scene_id])
			if M.scene_id == door["interior"]:
				M.test_want = Vector2(0, 1)
				var t2 := 0.0
				while M.scene_id == door["interior"] and t2 < 8.0:
					await get_tree().physics_frame
					t2 += 1.0 / 60.0
				M.test_want = Vector2.ZERO
				await wait_idle()
				ok(M.scene_id == sid, "%s 室内出不来（现在在 %s）" % [door["interior"], M.scene_id])
				ok(absf(M.player.position.x - (door["x0"] + door["x1"]) / 2.0) < 20, "%s 出门后不在门口（x=%d）" % [sid, M.player.position.x])
		for z in d.get("zebras", []):
			M._go(sid, Vector2((z["x0"] + z["x1"]) / 2.0, M.scene.band.y - 2), "front", 1)
			await frames(3)
			M._cross(z)
			await frames(5)
			await wait_idle()
			ok(M.scene_id == z["to"], "%s 斑马线过不去（现在在 %s）" % [sid, M.scene_id])
			ok(M.player.position.y >= M.scene.band.x - 1 and M.player.position.y <= M.scene.band.y + 1, "过马路后不在人行道上（y=%d）" % M.player.position.y)
			var back: Dictionary = M.scene.zebra_at(M.player.position + Vector2(0, M.scene.band.y - M.player.position.y - 2))
			ok(not back.is_empty(), "%s 过马路后落点不在对面斑马线上（x=%d）" % [M.scene_id, M.player.position.x])
		for side in ["left", "right"]:
			var exs = d.get("exits", {})
			if exs == null:
				exs = {}
			var e = exs.get(side)
			if e == null:
				continue
			var w: float = float(d.get("width", 960))
			M._go(sid, Vector2(60 if side == "left" else w - 60, M.scene.band.x + 30), "side", -1 if side == "left" else 1)
			await frames(3)
			M.test_want = Vector2(-1 if side == "left" else 1, 0)
			var t3 := 0.0
			while M.scene_id == sid and t3 < 4.0:
				await get_tree().physics_frame
				t3 += 1.0 / 60.0
			M.test_want = Vector2.ZERO
			await wait_idle()
			ok(M.scene_id == e["to"], "%s %s 出口走不过去（现在在 %s）" % [sid, side, M.scene_id])
	print("AT PHASE spots/npcs")
	for sid in M.world.get("spots", {}):
		for sp in M.world["spots"][sid]:
			if not sp.get("player", true):
				continue
			M._go(sid, Vector2(sp["x"] + 8, sp["y"] + 6), "side", 1)
			await frames(3)
			M._interact()
			await frames(10)
			ok(M.player.special == sp.get("hero_anim", "sit_bench"), "%s 座位 %s 坐不下（special=%s）" % [sid, sp["id"], M.player.special])
			M._interact()
			await frames(5)
			ok(M.player.special == "", "%s 座位 %s 起不来" % [sid, sp["id"]])
	for cfg in M.world["npcs"]:
		var sid: String = cfg["scene"]
		M._go(sid, Vector2(cfg["x"] - 30, clampf(cfg["y"], M.scene.band.x, M.scene.band.y)), "side", 1)
		await frames(3)
		var n: Node2D = M.find_npc(cfg["char"].split("/")[1])
		ok(n != null, "%s 找不到 NPC %s" % [sid, cfg["char"]])
		if n == null:
			continue
		M.player.position = n.position + Vector2(-30 if n.position.x > 40 else 30, 0)
		M.player.position.y = clampf(n.position.y, M.scene.band.x, M.scene.band.y)
		await frames(2)
		if n.cid == "wangcai":
			M._interact()
			await frames(10)
			ok(M.player.special == "pet_dog", "摸不了狗（special=%s）" % M.player.special)
			ok(n.special == "happy", "狗被摸时没有开心动画（%s）" % n.special)
			await frames(220)
			ok(M.player.special == "", "摸完狗没有起身")
			continue
		if n.talk.is_empty():
			continue
		M._interact()
		await frames(3)
		ok(M.dlg.visible, "%s 对话框没打开" % n.cname)
		var lines := 0
		while M.dlg_npc != null and lines < 12:
			ok(M.dlg_portrait.texture != null, "%s 没有头像" % n.cname)
			ok(M.dlg_text.get_line_count() <= 2, "%s 台词超过两行：%s" % [n.cname, M.dlg_text.text])
			M._interact()
			await frames(3)
			lines += 1
		ok(M.dlg_npc == null and not M.dlg.visible, "%s 对话关不掉" % n.cname)
		ok(not n.talking, "%s 对话结束后还停着" % n.cname)
	M._go("yongan_n", Vector2(800, 440), "side", 1)
	await frames(5)
	var before: int = M.shots_saved
	M._take_photo()
	await frames(120)
	ok(M.shots_saved > before, "拍照没有存图")
	ok(M.player.special == "", "拍完照没有恢复")
	print("AT PHASE ui")
	M._go("yongan_n", Vector2(457, M.scene.band.x + 4), "back", 1)
	await frames(5)
	M._update_prompt()
	ok(M.prompt.visible, "门前没有提示")
	var psp: Vector2 = M.player.get_global_transform_with_canvas().origin
	var pc: float = M.prompt.position.x + M.prompt.size.x / 2
	ok(absf(pc - psp.x) < 6, "提示牌没在人物正上方（提示中心 %d，人物 %d）" % [pc, psp.x])
	ok(M.prompt.position.y + M.prompt.size.y < psp.y - 60, "提示牌压在人物身上")
	# 室内：主角走不出房间
	M._go("chenji", Vector2(480, 430), "side", 1)
	await frames(3)
	await hold(Vector2(1, 0), 6.0)
	ok(M.player.position.x <= M.scene.x_range.y + 0.5, "室内往右走出了房间（x=%d，房间到 %d）" % [M.player.position.x, M.scene.x_range.y])
	await hold(Vector2(-1, 0), 10.0)
	ok(M.player.position.x >= M.scene.x_range.x - 0.5, "室内往左走出了房间（x=%d）" % M.player.position.x)
	ok(M.prompt.position.x >= 0 and M.prompt.position.x + M.prompt.size.x <= 960 and M.prompt.position.y >= 0, "提示牌出了屏幕")
	print("AT PHASE ambient")
	var A: Node = M.ambient
	# 脚步声
	M._go("yongan_n", Vector2(600, 430), "side", 1)
	await frames(3)
	var st0: int = A.steps_played
	await hold(Vector2(1, 0), 3.0)
	ok(A.steps_played - st0 >= 4, "走 3 秒只有 %d 声脚步" % (A.steps_played - st0))
	# 白天 / 夜晚
	A.minutes = 12 * 60.0
	await frames(5)
	var lamp_e := 0.0
	for l in A.lights:
		if l["kind"] == "lamp":
			lamp_e = maxf(lamp_e, l["node"].energy)
	ok(lamp_e < 0.01, "中午路灯还亮着（%.2f）" % lamp_e)
	var sh_a := 0.0
	for e in A.shadows:
		sh_a = maxf(sh_a, e[0].modulate.a)
	ok(sh_a > 0.1, "中午没有影子")
	A.minutes = 21 * 60.0
	await frames(5)
	lamp_e = 0.0
	for l in A.lights:
		if l["kind"] == "lamp":
			lamp_e = maxf(lamp_e, l["node"].energy)
	ok(lamp_e > 0.8, "晚上路灯不亮（%.2f）" % lamp_e)
	ok(A.lights.size() >= 5, "灯太少：%d" % A.lights.size())
	A.minutes = 15 * 60.0
	# 车流：40 秒内要有车，不追尾
	var seen := 0
	var crash := 0
	for i in 40 * 60:
		await get_tree().physics_frame
		seen = maxi(seen, A.cars.size())
		for c1 in A.cars:
			for c2 in A.cars:
				if c1 != c2 and c1["dir"] == c2["dir"]:
					var dd: float = absf(c1["node"].position.x - c2["node"].position.x)
					if dd < (float(c1["d"]["length_px"]) + float(c2["d"]["length_px"])) * 0.5 - 4.0:
						crash += 1
	ok(seen >= 1, "40 秒内街上没有车")
	ok(crash == 0, "车辆重叠 %d 帧" % crash)
	# 有人过斑马线时车要停
	if A.cars.size() > 0:
		var c0: Dictionary = A.cars[0]
		var cx: float = c0["node"].position.x + c0["dir"] * 300.0
		M.crossing_zebra = Vector2(cx - 40, cx + 40)
		await frames(240)
		ok(c0["v"] < 5.0 or not is_instance_valid(c0["node"]), "有人过斑马线车没停（速度 %d）" % c0["v"])
		M.crossing_zebra = Vector2.ZERO
	# 鸽子：人靠近飞走，之后落回人行道
	M._go("yongan_s", Vector2(300, 440), "side", 1)
	await frames(5)
	var fl: Dictionary = A.flocks[0]
	ok(fl["kind"] == "pigeon" and fl["state"] == "ground", "南侧鸽子初始不在地上")
	M.player.position = fl["center"] + Vector2(-20, 0)
	await frames(30)
	ok(fl["state"] != "ground", "人走近鸽子没飞")
	M.player.position = Vector2(60, 440)
	var t4 := 0.0
	while fl["state"] != "ground" and t4 < 30.0:
		await get_tree().physics_frame
		t4 += 1.0 / 60.0
	ok(fl["state"] == "ground", "鸽子 30 秒内没落地（%s）" % fl["state"])
	for b in A.birds:
		if b["state"] == "ground":
			var by: float = b["node"].position.y
			ok(by >= M.scene.band.x and by <= M.scene.band.y + 8, "鸟落在人行道外 y=%d" % by)
		elif b["state"] in ["sky", "takeoff"]:
			ok(b["node"].position.y < M.scene.band.x - 10, "飞着的鸟低于屋檐 y=%d" % b["node"].position.y)
	print("RESULT %s  pass=%d fail=%d" % ["PASS" if fails.is_empty() else "FAIL", passes, fails.size()])
	get_tree().quit(1 if fails.size() else 0)


## 截图模式（--shots=<目录>）：固定机位截图，做视觉对比和人工/视觉模型逐张检查
##  每条街每 700 px 一张（人物在中线）、室内、每个人的对话框、坐长椅、摸狗、门前提示
func run_shots(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	await frames(10)
	var k := 0
	for sid in M.world["scenes"].keys():
		var d: Dictionary = M.world_scene(sid)
		var w: float = float(d.get("width", 960))
		var x := 200.0
		while x < w:
			M._go(sid, Vector2(x, (M.scene.band.x + M.scene.band.y) / 2.0), "side", 1)
			M.cam.position.x = clampf(x, 480, maxf(480, w - 480)); M.cam.reset_smoothing()
			await frames(30)
			await _save(dir, "%s_x%04d" % [sid, int(x)])
			x += 700.0
	for cfg in M.world["npcs"]:
		var n: Node2D = null
		M._go(cfg["scene"], Vector2(cfg["x"] - 30, clampf(cfg["y"], 0, 999)), "side", 1)
		await frames(5)
		n = M.find_npc(cfg["char"].split("/")[1])
		if n == null or n.talk.is_empty():
			continue
		M.player.position = Vector2(n.position.x - 30, clampf(n.position.y, M.scene.band.x, M.scene.band.y))
		M._interact()
		var i := 0
		while M.dlg_npc != null and i < 6:
			await frames(12)
			await _save(dir, "talk_%s_%d" % [n.cid, i])
			M._interact()
			i += 1
	for sid in M.world.get("spots", {}):
		for sp in M.world["spots"][sid]:
			if sp.get("player", true):
				M._go(sid, Vector2(sp["x"] + 8, sp["y"] + 6), "side", 1)
				await frames(5)
				M._interact()
				await frames(20)
				await _save(dir, "sit_%s" % sp["id"])
				M._interact()
	M._go("yongan_n", Vector2(457, M.scene.band.x + 4), "back", 1)
	await frames(20)
	await _save(dir, "prompt_door")
	print("SHOTS DONE")
	get_tree().quit(0)


func _save(dir: String, name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	if img:
		img.save_png(dir.path_join(name + ".png"))
