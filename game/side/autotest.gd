extends Node
## 机器人自动测试（--autotest）：在真实游戏逻辑里跑，逐项断言，打印 AT PASS / AT FAIL，最后 RESULT 行并退出（失败 exit 1）。
##  1 NPC 浸泡：每个场景跑 soak 秒，检查卡住（stuck_log）、原地踏步（播行走动画但不动）、走出纵深带、站进家具碰撞
##  2 主角扫街：每条街按 里/中/外 三条线从左走到右、再走回来，记录意外被挡的位置
##  3 交互：每扇能进的门进出、每条斑马线来回、每个出口、每个座位坐下起身、摸狗、和每个人把话说完、拍照
##  4 界面：平时屏幕上没有任何文字/按键提示（A1.5 用户：界面要干净），对话文字不超过两行、头像存在
##  5 碰撞：顶着障碍走动画不抽风、动画方向和实际位移一致；带着居民和猫狗扫街不被卡住
##  6 光影与鸟：影子随太阳转向、车不惊鸟、鸽子惊飞后会落下（屋脊或地面）再回来觅食
## 选项：--soak=秒（默认 90）

var M: Node                       # side_main
var fails: Array = []
var passes := 0
var soak := 90.0


## --only=soak,sweep,interact,misc,collide,live,ambient,birds 只跑这些段（调试用；交付前必须全跑）
func _on(phase: String) -> bool:
	var only: String = str(M.args.get("only", ""))
	return only == "" or phase in only.replace("+", ",").split(",")


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
	for sid in (ids if _on("soak") else []):
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
			if M.args.has("trace_npc") and int(t * 60) % 15 == 0 and t < 25.0:
				for n in M.npcs:
					if n.cid == M.args["trace_npc"]:
						print("AT TRACE t=%.2f %s pos=%s cur=%s detour=%.1f stuck=%.2f step=%d hold=%.2f" % [t, n.cid, str(n.position), n.cur, n.detour, n.stuck_t, n.step_i, n.hold])
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
	for sid in (ids if _on("sweep") else []):
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
			var tlim := 0.0
			var nox := 0.0
			while M.player.position.x < M.scene.width - 30 and tlim < 240.0:
				var p0: Vector2 = M.player.position
				await get_tree().physics_frame
				tlim += 1.0 / 60.0
				# 横向没前进（被挡住，或者上下抖）都算被挡
				nox = nox + 1.0 / 60.0 if absf(M.player.position.x - p0.x) < 0.01 else 0.0
				if nox > 1.0:
					M.player.position.y = lane
				if M.player.position.distance_to(p0) < 0.01 or nox > 1.0:
					blocked += 1.0 / 60.0
					if blocked > 1.0:
						spots.append(int(M.player.position.x))
						M.player.position.x += 40   # 跳过障碍继续扫
						blocked = 0.0
				else:
					blocked = 0.0
			M.test_want = Vector2.ZERO
			ok(tlim < 240.0, "%s 扫街 y=%d 4 分钟没走完（卡死）" % [sid, lane])
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
	for sid in (ids if _on("interact") else []):
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
	if _on("misc"):
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
		var txt := []
		for c in M.hud.get_children():
			if c is Label and c.visible:
				txt.append(c.text)
		ok(txt.is_empty(), "平时屏幕上还有文字：%s" % str(txt))
		# 室内：主角走不出房间
		M._go("chenji", Vector2(480, 430), "side", 1)
		await frames(3)
		await hold(Vector2(1, 0), 6.0)
		ok(M.player.position.x <= M.scene.x_range.y + 0.5, "室内往右走出了房间（x=%d，房间到 %d）" % [M.player.position.x, M.scene.x_range.y])
		await hold(Vector2(-1, 0), 10.0)
		ok(M.player.position.x >= M.scene.x_range.x - 0.5, "室内往左走出了房间（x=%d）" % M.player.position.x)
	if _on("collide"):
		await _collide_phase()
	if _on("live"):
		await _live_sweep()
	if _on("ambient"):
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
		ok(A.shade != null and A.shade.visible and A.sun_alpha > 0.1, "中午没有影子")
		ok(A.shadow_map.has(M.player) and A.shadow_map[M.player].visible, "主角没有太阳影子")
		var sx := {}
		for hh in [9.0, 12.0, 16.5]:
			A.minutes = hh * 60.0
			await frames(2)
			sx[hh] = [A.sun_ax, A.sun_ay]
			var tr: Transform2D = A.shadow_map[M.player].transform
			ok(absf(-tr.y.x - A.sun_ax) < 0.01 and absf(-tr.y.y - A.sun_ay) < 0.01, "主角影子没跟太阳（%d 点）" % hh)
		print("AT INFO 影子 ax/ay：9点 %s 12点 %s 16点半 %s" % [str(sx[9.0]), str(sx[12.0]), str(sx[16.5])])
		ok(sx[9.0][0] > 0.4, "上午影子没有斜向右（ax=%.2f）" % sx[9.0][0])
		ok(sx[16.5][0] < -0.6, "下午影子没有斜向左（ax=%.2f）" % sx[16.5][0])
		ok(absf(sx[12.0][0]) < 0.3, "中午影子还斜得厉害（ax=%.2f）" % sx[12.0][0])
		ok(sx[16.5][1] > sx[12.0][1], "傍晚影子没有比中午长")
		# 主角跑起来影子贴脚：跑步每帧最低点都在地线上
		var ra: Dictionary = M.player.anims["run_side"]
		ok(ra["oy"] <= ra["fh"] - 1, "跑步帧地线超出画布")
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
	if _on("birds"):
		await _bird_phase()
	print("RESULT %s  pass=%d fail=%d" % ["PASS" if fails.is_empty() else "FAIL", passes, fails.size()])
	get_tree().quit(1 if fails.size() else 0)


## 碰撞：顶着障碍物走 2 秒，动画切换不超过 2 次；走路动画必须和实际位移方向一致
func _anim_ok(cur: String, d: Vector2) -> bool:
	if not (cur.begins_with("walk") or cur.begins_with("run")):
		return d.length() < 0.001
	if cur.ends_with("_side"):
		return absf(d.x) > 0.001
	if cur.begins_with("walk_diag"):
		return absf(d.x) > 0.001 and absf(d.y) > 0.001
	return absf(d.x) < 0.001 and absf(d.y) > 0.001


func _push(want: Vector2, secs: float, label: String, run := false) -> void:
	var switches := 0
	var bad := 0
	var last: String = M.player.cur
	M.test_want = want
	M.test_run = run
	for i in int(secs * 60):
		var p0: Vector2 = M.player.position
		await get_tree().physics_frame
		var d: Vector2 = M.player.position - p0
		if M.player.cur != last:
			switches += 1
			last = M.player.cur
		if not _anim_ok(M.player.cur, d):
			bad += 1
	M.test_want = Vector2.ZERO
	M.test_run = false
	ok(switches <= 3, "%s：动画来回切 %d 次（抽风）" % [label, switches])
	ok(bad <= 1, "%s：%d 帧动画和位移对不上（脚在滑/原地踏步）" % [label, bad])


func _collide_phase() -> void:
	print("AT PHASE collide")
	M._go("yongan_n", Vector2(60, 430), "side", 1)
	M.test_no_edges = true
	await frames(3)
	var keep: Array = M.player.others
	M.player.others = [M.player]
	# 1 顶着报亭（实心道具）往左走
	var kiosk := Rect2()
	for r in M.scene.solids:
		if r.has_point(Vector2(100, 418)):
			kiosk = r
	if kiosk.size != Vector2.ZERO:
		M.player.position = Vector2(kiosk.end.x + 30, kiosk.get_center().y)
		await _push(Vector2(-1, 0), 2.0, "顶着报亭往左走")
		await _push(Vector2(-1, 0), 1.0, "顶着报亭往左跑", true)
		await _push(Vector2(-1, 1), 2.0, "斜着顶报亭")
	# 2 顶着人行道里沿（楼脚）往上走、斜上走
	M.player.position = Vector2(600, M.scene.band.x + 6)
	await _push(Vector2(0, -1), 1.5, "顶着楼脚往里走")
	await _push(Vector2(1, -1), 2.0, "沿着楼脚斜走")
	# 3 街的左端尽头
	M.player.position = Vector2(20, 430)
	await _push(Vector2(-1, 0), 1.5, "顶着街道尽头走")
	M.player.others = keep
	# 4 正面撞上一个站着的人：自动绕过去，不卡住
	var n0: Node2D = null
	for n in M.npcs:
		if n.kind == "person" and n.visible and not n.hidden_in_door:
			n0 = n
			break
	if n0:
		var saved: Array = n0.loop
		n0.loop = []
		n0.talking = true
		# 找一个人两边都空的位置（不在家具里）
		for xx in [2000.0, 2600.0, 3100.0, 800.0, 1600.0]:
			var okp := true
			for r in M.scene.solids:
				if r.grow(14).intersects(Rect2(xx - 90, 425, 180, 12)):
					okp = false
			if okp:
				n0.position = Vector2(xx, 431)
				break
		var y0: float = n0.position.y
		M.player.position = Vector2(n0.position.x - 60, y0)
		M.test_want = Vector2(1, 0)
		var t := 0.0
		print("AT INFO 迎面：人 %s 主角 %s" % [str(n0.position), str(M.player.position)])
		var k3 := 0
		while M.player.position.x < n0.position.x + 30 and t < 4.0:
			await get_tree().physics_frame
			t += 1.0 / 60.0
			k3 += 1
			if k3 % 20 == 0 and t > 1.0:
				print("AT INFO   t=%.2f 主角 %s %s slide=%s hold=%.2f" % [t, str(M.player.position), M.player.cur, M.player.slide_dir, M.player.hold])
		M.test_want = Vector2.ZERO
		ok(t < 4.0, "迎面撞上%s绕不过去（卡住）" % n0.cname)
		n0.talking = false
		n0.loop = saved
	M.test_no_edges = false


## 带着所有居民、猫狗扫街（中线来回）：不能被卡住超过 1.5 秒
func _live_sweep() -> void:
	for sid in M.world["scenes"].keys():
		var d: Dictionary = M.world_scene(sid)
		if d.get("kind", "street") != "street":
			continue
		print("AT PHASE live_sweep ", sid)
		M._go(sid, Vector2(30, 430), "side", 1)
		M.test_no_edges = true
		await frames(3)
		var lane: float = (M.scene.band.x + M.scene.band.y) / 2.0
		for dirn in [1, -1]:
			M.player.position.y = lane
			var stuck := 0.0
			var worst := 0.0
			var where := 0
			M.test_want = Vector2(dirn, 0)
			var t := 0.0
			while ((dirn > 0 and M.player.position.x < M.scene.width - 40) or (dirn < 0 and M.player.position.x > 40)) and t < 90.0:
				var p0: Vector2 = M.player.position
				await get_tree().physics_frame
				t += 1.0 / 60.0
				if absf(M.player.position.x - p0.x) < 0.01:
					stuck += 1.0 / 60.0
					if stuck > worst:
						worst = stuck
						where = int(M.player.position.x)
				else:
					stuck = 0.0
				# 偏离中线太多时拉回去（模拟玩家）
				if absf(M.player.position.y - lane) > 26.0:
					M.test_want = Vector2(dirn, -signf(M.player.position.y - lane))
				else:
					M.test_want = Vector2(dirn, 0)
			M.test_want = Vector2.ZERO
			ok(worst < 1.5, "%s 带着居民和猫狗扫街（%s）在 x=%d 卡了 %.1f 秒" % [sid, "→" if dirn > 0 else "←", where, worst])
			ok(t < 90.0, "%s 扫街 90 秒没走完" % sid)
		M.test_no_edges = false


## 鸟：车不惊鸟；慢慢走近先走开；跑过去整群惊飞；飞起来 15 秒内要落下（屋脊或地面）；之后回到地上觅食
func _bird_phase() -> void:
	print("AT PHASE birds")
	var A: Node = M.ambient
	M._go("yongan_s", Vector2(1500, 430), "side", 1)
	await frames(5)
	var fl: Dictionary = {}
	for f in A.flocks:
		if f["kind"] == "pigeon":
			fl = f
	ok(not fl.is_empty() and fl["state"] == "ground", "南侧鸽子初始不在地上")
	var fid: int = fl["id"]
	var members: Array = A.birds.filter(func(b): return b["flock"]["id"] == fid)
	# 1 主角站远处 40 秒（车照常过）：鸽子基本一直在地上
	for n in M.npcs:
		n.visible = n.visible   # 居民照常走
	var air := 0.0
	var cars_seen := 0
	for i in 40 * 60:
		await get_tree().physics_frame
		if fl["state"] in ["flee", "circle", "approach"]:      # 在路灯/屋脊上歇着不算「在天上飞」
			air += 1.0 / 60.0
		cars_seen = maxi(cars_seen, A.cars.size())
	print("AT INFO 站远处 40 秒：鸽子在天上飞 %.1f 秒，期间车 %d 辆，最后状态 %s" % [air, cars_seen, fl["state"]])
	ok(air < 10.0, "没人靠近鸽子也在天上飞了 %.1f 秒（车/路人惊鸟太敏感）" % air)
	# 2 飞着的鸟节点在地面点（参与遮挡排序）
	for b in members:
		ok(b["node"].get_parent() == M.scene.ysort and b["node"].z_index == 0, "鸟不参与前后遮挡排序")
		break
	await _wait_ground(fl, 40.0)
	# 3 慢慢走近：先走开
	var c := Vector2.ZERO
	for b in members:
		c += b["node"].position
	c /= members.size()
	M.player.position = Vector2(c.x - 140, clampf(c.y, M.scene.band.x + 4, M.scene.band.y - 2))
	await frames(2)
	var x0 := 0.0
	for b in members:
		x0 += b["node"].position.x
	M.test_want = Vector2(1, 0)
	var walked_away := false
	var t := 0.0
	while fl["state"] == "ground" and t < 6.0:
		await get_tree().physics_frame
		t += 1.0 / 60.0
		var x1 := 0.0
		for b in members:
			x1 += b["node"].position.x
		if x1 - x0 > members.size() * 6.0:
			walked_away = true
	M.test_want = Vector2.ZERO
	ok(walked_away, "人走近时鸽子没有先走开")
	# 4 跑过去：整群惊飞，15 秒内落下
	await _wait_ground(fl, 40.0)
	members = A.birds.filter(func(b): return b["flock"]["id"] == fid)
	var b0: Dictionary = members[0]
	M.player.position = b0["node"].position + Vector2(-150, 0)
	M.player.position.y = clampf(M.player.position.y, M.scene.band.x + 2, M.scene.band.y - 2)
	M.test_want = Vector2(1, 0)
	M.test_run = true
	t = 0.0
	while fl["state"] == "ground" and t < 4.0:
		await get_tree().physics_frame
		t += 1.0 / 60.0
	M.test_want = Vector2.ZERO
	M.test_run = false
	ok(fl["state"] != "ground", "人跑向鸽子没惊飞")
	M.player.position.x = 100.0 if b0["node"].position.x > 800 else 1600.0
	t = 0.0
	var max_alt := 0.0
	var on_screen_top := 999.0
	while fl["state"] in ["flee", "circle", "approach"] and t < 20.0:
		await get_tree().physics_frame
		t += 1.0 / 60.0
		for b in members:
			max_alt = maxf(max_alt, b["alt"])
	print("AT INFO 鸽子惊飞后 %.1f 秒落在 %s，最高 %d px" % [t, fl["state"], max_alt])
	ok(t < 15.0, "鸽子惊飞后 %.1f 秒还没落下" % t)
	ok(max_alt > 40.0, "鸽子惊飞没飞起来")
	for b in members:
		var top: float = b["node"].position.y - b["alt"]
		ok(top > 20.0, "鸟落在画面外（y=%d）" % top)
		if b["state"] == "ground":
			ok(b["node"].position.y >= M.scene.band.x and b["node"].position.y <= M.scene.band.y + 8, "鸟落在人行道外 y=%d" % b["node"].position.y)
	# 5 之后回到地上
	await _wait_ground(fl, 60.0)
	ok(fl["state"] == "ground", "鸽子 60 秒内没回到地上（%s）" % fl["state"])


func _wait_ground(fl: Dictionary, secs: float) -> void:
	var t := 0.0
	while fl["state"] != "ground" and t < secs:
		await get_tree().physics_frame
		t += 1.0 / 60.0


## 截图模式（--shots=<目录>）：固定机位截图，做视觉对比和人工/视觉模型逐张检查
##  每条街每 700 px 一张（人物在中线）、室内、每个人的对话框、坐长椅、摸狗、门前提示
func run_shots(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	M.testing = true        # 截图时用 test_want 驱动主角
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
	# 影子随时间：同一机位 8 / 10 / 12 / 15 / 17 / 18:30 点
	for hh in [8.0, 10.0, 12.0, 15.0, 17.0, 18.5]:
		M._go("yongan_n", Vector2(2700, 440), "side", 1)
		M.cam.position.x = 2700; M.cam.reset_smoothing()
		M.ambient.minutes = hh * 60.0
		await frames(20)
		await _save(dir, "sun_%02d%02d" % [int(hh), int(fmod(hh, 1.0) * 60)])
	M.ambient.minutes = 15 * 60.0
	# 面馆蒸汽（静态雾已去掉）
	M._go("yongan_n", Vector2(420, 440), "side", 1)
	M.cam.position.x = 480; M.cam.reset_smoothing()
	await frames(90)
	await _save(dir, "steam_yongan")
	M._go("chenji", Vector2(480, 440), "side", 1)
	await frames(90)
	await _save(dir, "steam_chenji")
	# 鸽子：惊飞后绕圈、落屋脊
	M._go("yongan_s", Vector2(400, 452), "side", 1)
	M.cam.position.x = 560; M.cam.reset_smoothing()
	await frames(10)
	M.test_want = Vector2(1, 0); M.test_run = true
	await frames(60)
	M.test_want = Vector2.ZERO; M.test_run = false
	for k2 in 10:
		await frames(45)
		await _save(dir, "birds_%d" % k2)
	print("SHOTS DONE")
	get_tree().quit(0)


func _save(dir: String, name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	if img:
		img.save_png(dir.path_join(name + ".png"))
