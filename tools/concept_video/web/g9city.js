// 《烟火之城》讲解用的像素城市模拟：读 pixel_city 的 city.json（AI 整块街区 + 程序地面），
// 2D 画布里重现 Godot 场景：街区分层遮挡、道具、车流、F 根运动行人、昼夜、气泡。
import { clamp, lerp, smooth } from './kit.js';

const R = '/yh/';
const cache = new Map();
export function img(url) { if (cache.has(url)) return cache.get(url).im; const im = new Image(); im.src = url; const p = im.decode().then(() => im).catch(() => { console.warn('img fail', url); return null; }); cache.set(url, { im, p }); return im; }
export async function loadAll(urls) { urls.forEach(img); await Promise.all(urls.map((u) => cache.get(u).p)); }

export let CITY = null;
const SHEETS = {}; // name -> {im, rm, fps}
export async function loadCity() {
  if (CITY) return CITY;
  CITY = await (await fetch(R + 'city.json')).json();
  const sprites = new Set(CITY.props.map((p) => p.sprite));
  ['taxi', 'car_red', 'bus'].forEach((c) => ['right', 'down', 'up'].forEach((d) => sprites.add(`${c}_${d}`)));
  ['stall_food', 'stall_fruit', 'stall_flower', 'kiosk', 'bench', 'lamp2', 'vending', 'bikes'].forEach((s) => sprites.add(s));
  const urls = [R + 'ground.png', ...CITY.blocks.map((b) => `${R}blocks/${b.img}.png`), ...[...sprites].map((s) => `${R}${s}.png`)];
  await loadAll(urls);
  return CITY;
}
export async function loadSheet(name) {
  if (SHEETS[name]) return SHEETS[name];
  const base = name.replace(/_(old|lin|aunt|kid|w\d)$/, '');
  const m = await (await fetch(`${R}${base}.json`)).json();
  await loadAll([`${R}${name}.png`, `${R}${name}_idle.png`]);
  SHEETS[name] = { im: img(`${R}${name}.png`), idle: img(`${R}${name}_idle.png`), rm: m.root_motion_px, fps: m.anim_fps };
  return SHEETS[name];
}
const ROW = { down: 0, left: 1, right: 2, up: 3 };

// ---------- 行人 ----------
export class Agent {
  constructor(o) { Object.assign(this, { x: 0, y: 0, dir: 'down', frame: 0, acc: 0, route: [], ri: 0, wait: 0, spd: 1, moving: false, lie: 0, alpha: 1, bubbles: [], name: '', hidden: false, loop: false, face: null }, o); this.sh = SHEETS[o.sheet]; }
  go(route, loop = false) { this.route = route; this.ri = 0; this.loop = loop; this.wait = 0; }
  say(text, o = {}) { this.bubbles.push({ text, t: 0, dur: o.dur ?? 2.6, icon: o.icon, col: o.col, kind: o.kind || 'say' }); }
  update(dt) {
    this.idleT = this.moving ? 0 : (this.idleT || 0) + dt;
    this.bubbles.forEach((b) => (b.t += dt)); this.bubbles = this.bubbles.filter((b) => b.t < b.dur);
    if (this.lie) { this.moving = false; return; }
    if (this.wait > 0) { this.wait -= dt; this.moving = false; this.frame = 0; if (this.face) this.dir = this.face; return; }
    const wp = this.route[this.ri];
    if (!wp) { this.moving = false; this.frame = 0; if (this.face) this.dir = this.face; return; }
    const dx = wp[0] - this.x, dy = wp[1] - this.y;
    if (Math.abs(dx) < 0.6 && Math.abs(dy) < 0.6) {
      this.x = wp[0]; this.y = wp[1]; this.wait = wp[2] || 0; if (wp[3]) this.face = wp[3]; if (wp[4]) wp[4](this);
      this.ri++; if (this.ri >= this.route.length && this.loop) this.ri = 0; this.frame = 0; this.acc = 0; return;
    }
    // 先走偏差小的轴把它对正，再走大的（和 Godot 版一致）
    const ax = Math.abs(dx), ay = Math.abs(dy);
    const horiz = ay < 0.6 ? true : ax < 0.6 ? false : ax < ay;
    const d = horiz ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
    if (d !== this.dir) { this.dir = d; this.frame = 0; this.acc = 0; }
    this.face = null; this.moving = true; this.acc += dt * this.sh.fps * this.spd;
    while (this.acc >= 1) {
      this.acc -= 1; const st = (this.sh.rm[d] || [3.75])[this.frame] ?? 3.75;
      if (horiz) this.x += Math.sign(dx) * Math.min(st, Math.abs(wp[0] - this.x)); else this.y += Math.sign(dy) * Math.min(st, Math.abs(wp[1] - this.y));
      this.frame = (this.frame + 1) % 8;
    }
  }
  draw(g) {
    if (this.hidden || this.alpha <= 0.01) return; const x = Math.round(this.x), y = Math.round(this.y);
    g.save(); g.globalAlpha = this.alpha;
    g.fillStyle = 'rgba(26,20,36,0.32)'; g.beginPath(); g.ellipse(x + 1, y - 1, 7, 2.5, 0, 0, 7); g.fill();
    if (this.lie) { g.translate(x, y - 4); g.rotate(this.lie > 0 ? Math.PI / 2 : -Math.PI / 2); g.drawImage(this.sh.idle, 32, 0, 32, 40, -36, -16, 32, 40); }
    else if (this.moving) g.drawImage(this.sh.im, this.frame * 32, ROW[this.dir] * 40, 32, 40, x - 16, y - 39, 32, 40);
    else { // 站立：专用站立帧（双脚着地）+ 轻微呼吸（上半身每 1.2 s 起伏 1px）
      const im = this.sh.idle, c = ROW[this.dir] * 32; const br = Math.floor(((this.idleT || 0) + (this.ph ?? (this.x * 0.013))) / 0.6) % 2;
      g.drawImage(im, c, 0, 32, 26, x - 16, y - 39 + br, 32, 26); g.drawImage(im, c, 26, 32, 14, x - 16, y - 13, 32, 14);
    }
    g.restore();
  }
}

// ---------- 车 ----------
class Car {
  constructor(c) { this.pts = c.pts; this.type = c.type; this.speed = c.speed; this.loop = c.loop; this.s = c.s0 || 0; this.L = []; let a = 0; for (let i = 0; i < this.pts.length - (this.loop ? 0 : 1); i++) { const p = this.pts[i], q = this.pts[(i + 1) % this.pts.length]; const l = Math.hypot(q[0] - p[0], q[1] - p[1]); this.L.push([a, l, p, q]); a += l; } this.total = a; this.pos(); }
  pos() { let s = this.s % this.total; for (const [a, l, p, q] of this.L) if (s <= a + l) { const u = (s - a) / l; this.x = lerp(p[0], q[0], u); this.y = lerp(p[1], q[1], u); const vx = q[0] - p[0], vy = q[1] - p[1]; this.dir = Math.abs(vx) >= Math.abs(vy) ? (vx > 0 ? 'right' : 'left') : (vy > 0 ? 'down' : 'up'); return; } }
  update(dt) { this.s += this.speed * dt; this.pos(); }
  draw(g) { const im = img(`${R}${this.type}_${this.dir === 'left' ? 'right' : this.dir}.png`); if (!im.width) return; const x = Math.round(this.x), y = Math.round(this.y);
    g.fillStyle = 'rgba(26,20,36,0.3)'; g.beginPath(); g.ellipse(x, y + im.height / 2 - 3, im.width * 0.45, 4, 0, 0, 7); g.fill();
    if (this.dir === 'left') { g.save(); g.translate(x, 0); g.scale(-1, 1); g.drawImage(im, -Math.round(im.width / 2), y - Math.round(im.height / 2)); g.restore(); } else g.drawImage(im, x - Math.round(im.width / 2), y - Math.round(im.height / 2)); }
}

// ---------- 世界 ----------
export class World {
  constructor() {
    const C = CITY; this.C = C; this.agents = []; this.cars = C.cars.map((c, i) => new Car({ ...c, s0: i * 137 })); this.extra = []; this.decals = []; this.t = 0; this.hour = 10; this.fx = [];
    this.layers = []; // 街区的 y 排序层
    for (const b of C.blocks) for (const p of b.parts) this.layers.push({ kind: 'part', b, p, y: b.y + p[2] });
    for (const p of C.props) this.layers.push({ kind: 'prop', p, y: p.y });
  }
  add(o) { const a = new Agent(o); this.agents.push(a); return a; }
  prop(sprite, x, y, o = {}) { const p = { kind: 'prop', p: { sprite, x, y, ...o }, y }; this.extra.push(p); return p; }
  update(dt) { this.t += dt; this.agents.forEach((a) => a.update(dt)); this.cars.forEach((c) => c.update(dt)); this.fx.forEach((f) => (f.t += dt)); this.fx = this.fx.filter((f) => f.t < f.dur); }
  // 把世界画到像素画布 pc（视口左上 = (vx,vy)，1 世界像素 = 1 画布像素）
  draw(pc, vx, vy) {
    const g = pc.getContext('2d'); const w = pc.width, h = pc.height; g.imageSmoothingEnabled = false;
    g.setTransform(1, 0, 0, 1, -Math.round(vx), -Math.round(vy));
    g.fillStyle = '#3d6f78'; g.fillRect(vx - 2, vy - 2, w + 4, h + 4);
    g.drawImage(img(R + 'ground.png'), 0, 0);
    this.drawWater(g, vx, vy, w, h);
    const inView = (x0, y0, x1, y1) => x1 >= vx - 8 && x0 <= vx + w + 8 && y1 >= vy - 8 && y0 <= vy + h + 8;
    for (const b of this.C.blocks) if (inView(b.x, b.y, b.x + b.w, b.y + b.h)) { const im = img(`${R}blocks/${b.img}.png`); if (im.naturalWidth) g.drawImage(im, b.x, b.y); else { g.fillStyle = '#8a7b6a'; g.fillRect(b.x, b.y + 40, b.w, b.base - 40); } }
    const list = [];
    for (const L of this.layers) list.push(L);
    for (const L of this.extra) list.push(L);
    for (const a of this.agents) list.push({ kind: 'agent', a, y: a.y + (a.lie ? -6 : 0) });
    for (const c of this.cars) list.push({ kind: 'car', c, y: c.y + 6 });
    list.sort((p, q) => p.y - q.y);
    for (const L of list) {
      if (L.kind === 'part') { const { b, p } = L; if (!inView(b.x, b.y + p[0], b.x + b.w, b.y + p[1])) continue; const im = img(`${R}blocks/${b.img}.png`); if (im.naturalWidth) g.drawImage(im, 0, p[0], im.width, p[1] - p[0], b.x, b.y + p[0], im.width, p[1] - p[0]); }
      else if (L.kind === 'prop') { const p = L.p; const im = img(R + p.sprite + '.png'); if (!im.naturalWidth || !inView(p.x - im.width, p.y - im.height, p.x + im.width, p.y)) continue; if (p.flip) { g.save(); g.translate(p.x, 0); g.scale(-1, 1); g.drawImage(im, -Math.round(im.width / 2), p.y - im.height); g.restore(); } else g.drawImage(im, p.x - Math.round(im.width / 2), p.y - im.height); }
      else if (L.kind === 'agent') { if (inView(L.a.x - 20, L.a.y - 44, L.a.x + 20, L.a.y + 4)) L.a.draw(g); }
      else if (L.kind === 'car') { if (inView(L.c.x - 60, L.c.y - 40, L.c.x + 60, L.c.y + 40)) L.c.draw(g); }
    }
    for (const d of this.decals) d(g);
    for (const f of this.fx) f.draw(g, f.t / f.dur);
    this.light(g, vx, vy, w, h);
    g.setTransform(1, 0, 0, 1, 0, 0);
  }
  drawWater(g, vx, vy, w, h) { const ry = this.C.river_y; if (vy + h < ry) return; g.save(); g.globalAlpha = 0.35; g.fillStyle = '#d9f0ea'; for (let i = 0; i < 40; i++) { const x = ((i * 173 + this.t * 9 * (1 + (i % 3))) % 2500) - 20, y = ry + 12 + ((i * 37) % 70); g.fillRect(Math.round(x), y, 6 + (i % 4) * 2, 1); } g.restore(); }
  // 昼夜：整体乘色 + 夜里路灯暖光
  light(g, vx, vy, w, h) {
    const hr = this.hour; const night = hr < 5.5 || hr > 19.5 ? 1 : hr < 7 ? 1 - (hr - 5.5) / 1.5 : hr > 18 ? (hr - 18) / 1.5 : 0;
    const dusk = hr > 16.5 && hr < 19.8 ? Math.sin(((hr - 16.5) / 3.3) * Math.PI) : hr > 5.2 && hr < 7.5 ? Math.sin(((hr - 5.2) / 2.3) * Math.PI) * 0.7 : 0;
    if (dusk > 0.01) { g.save(); g.globalCompositeOperation = 'multiply'; g.fillStyle = `rgba(255,${Math.round(200 - 30 * dusk)},${Math.round(150 - 40 * dusk)},${0.42 * dusk})`; g.fillRect(vx, vy, w, h); g.restore(); }
    if (night > 0.01) {
      g.save(); g.globalCompositeOperation = 'multiply'; g.fillStyle = `rgba(${Math.round(255 - 170 * night)},${Math.round(255 - 160 * night)},${Math.round(255 - 120 * night)},1)`; g.fillRect(vx, vy, w, h); g.restore();
      g.save(); g.globalCompositeOperation = 'lighter';
      const glow = (x, y, r, c, a) => { const gr = g.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, `rgba(${c},${a})`); gr.addColorStop(1, `rgba(${c},0)`); g.fillStyle = gr; g.fillRect(x - r, y - r, 2 * r, 2 * r); };
      for (const p of this.C.props) if ((p.sprite === 'lamp2' || p.sprite === 'lamp') && p.x > vx - 60 && p.x < vx + w + 60 && p.y > vy - 40 && p.y < vy + h + 80) { glow(p.x, p.y - 4, 34, '255,190,110', 0.38 * night); glow(p.x, p.y - 30, 9, '255,230,170', 0.8 * night); }
      for (const e of this.extra) if (e.p.glow) { glow(e.p.x, e.p.y - 12, e.p.glow, '255,170,80', 0.6 * night); glow(e.p.x, e.p.y - 26, 16, '255,220,150', 0.7 * night); }
      // 店面窗光：前排墙脚一线
      for (const b of this.C.blocks) { const base = b.y + b.base; if (base < vy - 20 || base - 60 > vy + h) continue; for (let x = b.x + 20; x < b.x + b.w - 10; x += 46) glow(x + ((x * 7) % 13), base - 14, 26, '255,200,120', 0.22 * night); }
      g.restore();
    }
    this.night = night;
  }
}

// ---------- 视图：像素画布 → 1920x1080 ----------
const pcs = {};
function pcFor(w, h) { const k = w + 'x' + h; if (!pcs[k]) { const c = document.createElement('canvas'); c.width = w; c.height = h; pcs[k] = c; } return pcs[k]; }
// cam = {x,y,z}：画面中心对应世界坐标 (x,y)，z = 放大倍数
export function render(g, world, cam, W = 1920, H = 1080) {
  const z = cam.z; const w = Math.ceil(W / z) + 2, h = Math.ceil(H / z) + 2; const pc = pcFor(w, h);
  const vx = Math.round(cam.x - W / z / 2), vy = Math.round(cam.y - H / z / 2);
  world.draw(pc, vx, vy); g.save(); g.imageSmoothingEnabled = z < 1.5 ? true : false; const ox = (cam.x - W / z / 2 - vx) * z, oy = (cam.y - H / z / 2 - vy) * z;
  g.drawImage(pc, -ox, -oy, w * z, h * z); g.restore();
  return { vx: cam.x - W / z / 2, vy: cam.y - H / z / 2, z, sx: (x) => (x - (cam.x - W / z / 2)) * z, sy: (y) => (y - (cam.y - H / z / 2)) * z };
}
export const camLerp = (a, b, u) => ({ x: lerp(a.x, b.x, u), y: lerp(a.y, b.y, u), z: lerp(a.z, b.z, u) });
