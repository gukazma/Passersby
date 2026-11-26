// 《烟火之城》玩法方案讲解：像素城市实景模拟（AI 整块街区）+ 居民大脑/事件/室内/主线/版本 示意
import { W, H, clamp, lerp, smooth, ease, ramp, rrect, win } from './kit.js';
import { loadCity, loadSheet, loadAll, img, World, render, camLerp } from './g9city.js';

// ---------- 字体 / 图标 ----------
const faces = [new FontFace('px', 'url(/web/fonts/px.woff2)'), new FontFace('lucide', 'url(/web/fonts/lucide.ttf)'), new FontFace('NSC', 'url(/web/fonts/NotoSansSC-VF.ttf)', { weight: '100 900' }), new FontFace('Barlow Condensed', 'url(/web/fonts/BarlowCondensed-Bold.ttf)', { weight: '700' })];
await Promise.all(faces.map((f) => f.load().then((x) => document.fonts.add(x))));
const ICON = await (await fetch('/web/icons_all.json')).json();
const ART = '/yh/art/';
const A = (n) => img(ART + n + '.png');
const C = { ink: '#1b1410', paper: '#fbf3e2', paper2: '#f1e2c2', line: '#5a3a24', amber: '#f2a93b', red: '#d9573e', green: '#5bb974', teal: '#2fa391', dim: '#b9ab96', text: '#f6efe4', panel: 'rgba(22,17,13,0.86)' };

function T(g, s, x, y, size, color = C.text, o = {}) {
  if ((o.a ?? 1) <= 0.01) return 0; g.save(); g.globalAlpha *= o.a ?? 1;
  g.font = o.px ? `${size}px px` : `${o.w ?? 700} ${size}px "NSC", "Noto Sans CJK SC", sans-serif`; if (o.num) g.font = `700 ${size}px "Barlow Condensed", "NSC", sans-serif`;
  g.textAlign = o.align || 'left'; g.textBaseline = o.base || 'top'; const w = g.measureText(s).width;
  if (o.shadow) { g.shadowColor = 'rgba(0,0,0,0.8)'; g.shadowBlur = o.shadow; g.shadowOffsetY = 2; }
  if (o.stroke) { g.lineWidth = o.stroke; g.strokeStyle = o.strokeC || 'rgba(12,9,7,0.9)'; g.lineJoin = 'round'; g.strokeText(s, x, y); }
  g.fillStyle = color; g.fillText(s, x, y); g.restore(); return w;
}
function TW(g, s, size, o = {}) { g.save(); g.font = o.px ? `${size}px px` : `${o.w ?? 700} ${size}px "NSC", sans-serif`; const w = g.measureText(s).width; g.restore(); return w; }
function icon(g, name, x, y, size, color, a = 1) { const cp = ICON[name]; if (!cp || a <= 0.01) return; g.save(); g.globalAlpha *= a; g.font = `${size}px lucide`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = color; g.fillText(String.fromCodePoint(cp), x, y + size * 0.04); g.restore(); }
// 讲解面板（深色扁平）
function panel(g, x, y, w, h, a = 1, o = {}) { if (a <= 0.01) return; g.save(); g.globalAlpha *= a; rrect(g, x, y, w, h, o.r ?? 10); g.fillStyle = o.fill || C.panel; g.fill(); if (o.accent) { g.fillStyle = o.accent; g.fillRect(x, y + 10, 5, h - 20); } g.restore(); }
// 游戏内 UI（像素风奶油色框）
function pxBox(g, x, y, w, h, a = 1, o = {}) { if (a <= 0.01) return; g.save(); g.globalAlpha *= a; x = Math.round(x); y = Math.round(y); const b = 4;
  g.fillStyle = o.border || C.line; g.fillRect(x + b, y, w - 2 * b, h); g.fillRect(x, y + b, w, h - 2 * b);
  g.fillStyle = o.fill || C.paper; g.fillRect(x + b, y + b, w - 2 * b, h - 2 * b); g.fillStyle = 'rgba(90,58,36,0.12)'; g.fillRect(x + b, y + h - 2 * b, w - 2 * b, b); g.restore(); }
// 头顶气泡：像素字 + 图标；(sx,sy) = 头顶屏幕坐标
function bubble(g, sx, sy, text, o = {}) { const a = o.a ?? 1; if (a <= 0.01) return; const size = o.size || 24; const iw = o.icon ? size + 8 : 0; const w = Math.round(TW(g, text, size, { px: true }) + 28 + iw), h = size + 22;
  const pop = o.pop ?? 1; g.save(); g.globalAlpha *= a; g.translate(sx, sy); g.scale(pop, pop); const x = -w / 2, y = -h - 14;
  pxBox(g, x, y, w, h, 1, { fill: o.fill || '#fffaf0', border: o.border || '#3a2a20' }); g.fillStyle = o.border || '#3a2a20'; g.fillRect(-6, y + h - 2, 12, 6); g.fillStyle = o.fill || '#fffaf0'; g.fillRect(-3, y + h - 4, 6, 6); g.fillStyle = o.border || '#3a2a20'; g.fillRect(-2, y + h + 4, 4, 4);
  if (o.icon) icon(g, o.icon, x + 14 + size / 2, y + h / 2, size, o.ic || C.red);
  T(g, text, x + 14 + iw, y + h / 2 + 1, size, o.color || C.ink, { px: true, base: 'middle' }); g.restore(); }
const popIn = (t, t0, d = 0.28) => { const u = clamp((t - t0) / d), c = 1.70158; return u <= 0 ? 0 : 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); };
const fadeWin = (t, a, b, f = 0.25) => clamp(Math.min((t - a) / f, (b - t) / f));
function cover(g, im, z = 1, px = 0.5, py = 0.5, a = 1, smoothOn = false) { if (!im || !im.width) return; const s = Math.max(W / im.width, H / im.height) * z; const w = im.width * s, h = im.height * s; g.save(); g.globalAlpha *= a; g.imageSmoothingEnabled = smoothOn; g.drawImage(im, (W - w) * px, (H - h) * py, w, h); g.restore(); }
function fit(g, im, x, y, w, h, a = 1, o = {}) { if (!im || !im.width) { g.save(); g.globalAlpha *= a; g.fillStyle = '#3a2f26'; g.fillRect(x, y, w, h); g.restore(); return; } const s = o.cover ? Math.max(w / im.width, h / im.height) : Math.min(w / im.width, h / im.height); const dw = im.width * s, dh = im.height * s; g.save(); g.globalAlpha *= a; g.beginPath(); g.rect(x, y, w, h); g.clip(); g.imageSmoothingEnabled = !!o.smooth; g.drawImage(im, x + (w - dw) / 2, y + (h - dh) * (o.py ?? 0.5), dw, dh); g.restore(); }
function vgrad(g, y0, y1, a0, a1, rgb = '10,8,6') { const gr = g.createLinearGradient(0, y0, 0, y1); gr.addColorStop(0, `rgba(${rgb},${a0})`); gr.addColorStop(1, `rgba(${rgb},${a1})`); g.fillStyle = gr; g.fillRect(0, Math.min(y0, y1), W, Math.abs(y1 - y0)); }
function hgrad(g, x0, x1, a0, a1) { const gr = g.createLinearGradient(x0, 0, x1, 0); gr.addColorStop(0, `rgba(10,8,6,${a0})`); gr.addColorStop(1, `rgba(10,8,6,${a1})`); g.fillStyle = gr; g.fillRect(Math.min(x0, x1), 0, Math.abs(x1 - x0), H); }
function dim(g, a) { g.fillStyle = `rgba(8,6,4,${a})`; g.fillRect(0, 0, W, H); }
function portrait(g, n, x, y, s, a = 1) { const im = A('por_' + n); g.save(); g.globalAlpha *= a; pxBox(g, x - 6, y - 6, s + 12, s + 12, 1, { fill: '#efe2c6' }); fit(g, im, x, y, s, s, 1, { cover: true, py: 0.3 }); g.restore(); }
// 列表项（图标 + 文字），出现时从左滑入
function item(g, x, y, ic, text, a, o = {}) { if (a <= 0.01) return; const dx = (1 - smooth(a)) * -40; g.save(); g.globalAlpha *= clamp(a); icon(g, ic, x + 24 + dx, y + 22, 34, o.ic || C.amber); T(g, text, x + 66 + dx, y + 2, o.size || 38, o.color || C.text, { w: o.w ?? 700 }); if (o.sub) T(g, o.sub, x + 66 + dx, y + 50, 26, C.dim, { w: 500 }); g.restore(); }
function arrow(g, x0, y0, x1, y1, col, a = 1, w = 4, dash = null) { if (a <= 0.01) return; g.save(); g.globalAlpha *= a; g.strokeStyle = col; g.fillStyle = col; g.lineWidth = w; if (dash) g.setLineDash(dash); g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); g.setLineDash([]); const an = Math.atan2(y1 - y0, x1 - x0); g.beginPath(); g.moveTo(x1, y1); g.lineTo(x1 - 16 * Math.cos(an - 0.45), y1 - 16 * Math.sin(an - 0.45)); g.lineTo(x1 - 16 * Math.cos(an + 0.45), y1 - 16 * Math.sin(an + 0.45)); g.closePath(); g.fill(); g.restore(); }
function bar(g, x, y, w, h, v, col, a = 1) { g.save(); g.globalAlpha *= a; g.fillStyle = 'rgba(255,245,230,0.12)'; g.fillRect(x, y, w, h); g.fillStyle = col; g.fillRect(x, y, Math.round(w * clamp(v)), h); g.restore(); }
function keycap(g, x, y, k, a = 1, down = 0) { g.save(); g.globalAlpha *= a; pxBox(g, x, y + down * 4, 48, 48, 1, { fill: down ? '#f2c96a' : '#fff6e2' }); T(g, k, x + 24, y + 25 + down * 4, 28, C.ink, { px: true, align: 'center', base: 'middle' }); g.restore(); }
function clockHud(g, hour, a = 1) { if (a <= 0.01) return; const x = W - 290, y = 40; pxBox(g, x, y, 250, 84, a, { fill: '#fff6e2' }); g.save(); g.globalAlpha *= a; const h = Math.floor(hour) % 24, m = Math.floor((hour % 1) * 60); icon(g, hour >= 6 && hour < 18.5 ? 'sun' : 'moon', x + 46, y + 42, 38, hour >= 6 && hour < 18.5 ? '#e08a1e' : '#6c6a8a'); T(g, `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`, x + 86, y + 44, 48, C.ink, { px: true, base: 'middle' }); g.restore(); }
function toast(g, ic, text, sub, a, y, col = C.green) { if (a <= 0.01) return; const w = 520, x = W - w - 40 + (1 - smooth(a)) * 80; pxBox(g, x, y, w, sub ? 104 : 72, clamp(a * 1.5), { fill: '#fff8ea' }); g.save(); g.globalAlpha *= clamp(a * 1.5); icon(g, ic, x + 42, y + 36, 34, col); T(g, text, x + 76, y + 36, 30, C.ink, { px: true, base: 'middle' }); if (sub) T(g, sub, x + 76, y + 76, 24, '#7a6450', { px: true, base: 'middle' }); g.restore(); }
// 一次性触发
const once = (st, k, cond) => { st.done = st.done || {}; if (cond && !st.done[k]) { st.done[k] = true; return true; } return false; };
const cue = (st, i, d = 0) => st.cues[i] + d;

// ---------- 城市里的公共布置 ----------
const SHEET = ['npc_office', 'npc_office_b', 'npc_office_c', 'npc_student', 'npc_student_g', 'npc_student_r', 'hero', 'npc_office_lin', 'npc_office_old', 'hero_aunt', 'npc_student_kid'];
const walkers = ['npc_office', 'npc_office_b', 'npc_office_c', 'npc_student', 'npc_student_g', 'npc_student_r', 'hero'];
async function baseWorld(st, o = {}) {
  await loadCity(); for (const s of SHEET) await loadSheet(s);
  const w = new World(); w.hour = o.hour ?? 10; st.w = w; w.decals.push(clockSign);
  if (o.crowd !== false) { // city.json 里的人行道路线，加一些随机变化
    w.C.npcs.forEach((n, i) => { if (!n.path || n.path.length < 2) return; const sh = walkers[i % walkers.length]; const p = n.path; const a = w.add({ sheet: sh, x: p[0][0] + ((i * 97) % Math.max(1, Math.abs(p[1][0] - p[0][0]) || 1)), y: p[0][1] }); a.x = Math.min(Math.max(a.x, Math.min(p[0][0], p[1][0])), Math.max(p[0][0], p[1][0])); a.go([[p[1][0], p[1][1], 0.5 + (i % 3)], [p[0][0], p[0][1], 0.5 + (i % 2)]], true); a.spd = 0.9 + (i % 4) * 0.08; });
  }
  return w;
}
function simUpdate(st, dt) { st.w.update(dt); }
function drawWorld(g, st, cam) { st.view = render(g, st.w, cam); return st.view; }
const head = (v, a) => [v.sx(a.x), v.sy(a.y - 40)];
function agentBubbles(g, st, v) { for (const a of st.w.agents) for (const b of a.bubbles) { const [x, y] = head(v, a); if (x < -200 || x > W + 200 || y < -50 || y > H + 80) continue; bubble(g, x, y, b.text, { icon: b.icon, ic: b.col, a: fadeWin(b.t, 0, b.dur, 0.2), pop: popIn(b.t, 0) }); } }

// 钟表铺招牌（盖住原来的书店招牌）
function clockSign(g) { const x = 395, y = 900; g.fillStyle = '#3b2416'; g.fillRect(x, y, 64, 28); g.fillStyle = '#7a4a26'; g.fillRect(x + 2, y + 2, 60, 24); g.fillStyle = '#e9c46a'; g.fillRect(x + 4, y + 4, 56, 1); g.fillRect(x + 4, y + 23, 56, 1);
  const cx = x + 32, cy = y + 14; g.fillStyle = '#2a1a10'; g.beginPath(); g.arc(cx, cy, 10, 0, 7); g.fill(); g.fillStyle = '#fff4d6'; g.beginPath(); g.arc(cx, cy, 8, 0, 7); g.fill(); g.fillStyle = '#2a1a10'; g.fillRect(cx, cy - 6, 1, 6); g.fillRect(cx, cy, 5, 1); g.fillStyle = '#c0392b'; g.fillRect(cx - 1, cy - 1, 2, 2);
  g.fillStyle = '#e9c46a'; g.fillRect(x + 8, y + 12, 6, 4); g.fillRect(x + 50, y + 12, 6, 4); }
// 场景里用到的地点（世界像素坐标，按 city.json 的街道）
const P = {
  shopSide: 1040, aptSide: 1097, blvdN: 470, blvdS: 563, riverWalk: 1735,
  crossX: 855, stall: [1760, 1043], noodleDoor: [1893, 1034], clockDoor: [462, 1012],
};

export const scenes = {
  // ---------- 封面 ----------
  cover: {
    async setup(st) { await loadAll([ART + 'key_art.png']); },
    overlay(g, st, t) { cover(g, A('key_art'), 1.04 - t * 0.006, 0.5, 0.6); vgrad(g, H * 0.35, H, 0, 0.82); hgrad(g, 0, 1100, 0.55, 0);
      T(g, '暂定名', 120, 520, 32, C.amber, { w: 600 }); T(g, '烟火之城', 112, 560, 168, '#fff8ec', { w: 900, shadow: 24 });
      T(g, '像素开放世界 · 城市生活模拟', 120, 770, 52, '#f6efe4', { w: 600, shadow: 12 });
      g.save(); rrect(g, 120, 862, 400, 64, 32); g.fillStyle = C.amber; g.fill(); g.restore(); T(g, '玩法方案 · 讲解 v1', 320, 895, 32, C.ink, { w: 800, align: 'center', base: 'middle' }); },
  },
  // ---------- 我的理解 ----------
  intro: {
    async setup(st) { await baseWorld(st, { hour: 10 }); },
    update(st, t, dt) { simUpdate(st, dt); },
    overlay(g, st, t) {
      const u = t / st.dur; const v = drawWorld(g, st, { x: lerp(980, 1500, ease(u)), y: lerp(1000, 900, u), z: 3 }); agentBubbles(g, st, v);
      hgrad(g, 0, 980, 0.78, 0); const its = [[0, 'map', '自由探索的像素开放世界'], [0.35, 'user', '主角是普通人，不犯罪'], [1, 'users', '每个居民都在过自己的日子'], [1.3, 'zap', '街上随时发生随机事件'], [1.6, 'git-branch', '你做的事改变主线走向'], [2, 'map-pinned', '版本更新，地图一直扩张']];
      its.forEach(([c, ic, s], i) => { const t0 = st.cues[Math.floor(c)] + (c % 1) * 8 + 0.6; item(g, 90, 170 + i * 104, ic, s, ramp(t, t0, t0 + 0.4)); });
    },
  },
  // ---------- 城市 ----------
  city: {
    async setup(st) { await loadAll([ART + 'map.png']); },
    overlay(g, st, t) {
      const z = 1.02 + t * 0.004; cover(g, A('map'), z, 0.5, 0.5, 1); dim(g, 0.12);
      const D = st.plan.districts || DIST; const fogA = ramp(t, cue(st, 2, 1.2), cue(st, 2, 2.6));
      // 雾：未开放区域
      if (fogA > 0) for (const d of D) if (!d.open) { g.save(); g.globalAlpha = fogA * 0.86; const gr = g.createRadialGradient(d.x * W, d.y * H, 10, d.x * W, d.y * H, d.r * W); gr.addColorStop(0, 'rgba(236,232,224,1)'); gr.addColorStop(0.7, 'rgba(230,226,218,0.9)'); gr.addColorStop(1, 'rgba(230,226,218,0)'); g.fillStyle = gr; g.fillRect(0, 0, W, H); g.restore(); }
      D.forEach((d, i) => { const t0 = cue(st, 1, 0.9 + i * 1.25); const a = ramp(t, t0, t0 + 0.3); if (a <= 0) return; const p = popIn(t, t0); const x = d.x * W, y = d.y * H; g.save(); g.translate(x, y); g.scale(p, p);
        const w = TW(g, d.name, 36, { px: true }) + 40; pxBox(g, -w / 2, -30, w, 60, 1, { fill: d.open && fogA > 0 ? '#ffe7a8' : '#fff8ea' }); T(g, d.name, 0, 1, 36, C.ink, { px: true, align: 'center', base: 'middle' });
        if (fogA > 0.3 && !d.open) icon(g, 'lock', w / 2 + 6, -30, 30, '#6a5a48', fogA);
        g.restore(); });
      const a2 = ramp(t, cue(st, 2, 2.4), cue(st, 2, 2.9)); if (a2 > 0) { panel(g, 70, 140, 600, 120, a2, { accent: C.amber }); T(g, 'v1.0 开放', 110, 160, 30, C.amber, { a: a2 }); T(g, '老城区 + 码头', 110, 200, 40, C.text, { a: a2 }); }
    },
  },
  // ---------- 主角 ----------
  hero: {
    async setup(st) { await loadAll(['wanshi', 'por_lin', 'vehicles'].map((n) => ART + n + '.png').concat([ART + 'int_wanshi.png'])); await loadSheet('npc_office_lin'); st.room = await roomSim('int_wanshi', [{ sheet: 'npc_office_lin', at: [0.5, 0.72], dir: 'down' }]); },
    update(st, t, dt) { st.room.update(dt); },
    overlay(g, st, t) {
      const B = cue(st, 1), Cc = cue(st, 3);
      if (t < B + 0.4) { drawRoom(g, st.room, 1); const a = ramp(t, 0.6, 1.1); panel(g, 1180, 160, 660, 520, a, { accent: C.amber }); portrait(g, 'lin', 1230, 210, 200, a);
        T(g, '林屿', 1470, 220, 64, C.text, { a, w: 900 }); T(g, '26 岁 · 万事屋店主', 1472, 304, 30, C.amber, { a, w: 600 });
        ['回到家乡澜港', '接手舅舅留下的小店', '什么活都接'].forEach((s, i) => item(g, 1230, 450 + i * 64, ['ship', 'store', 'hammer'][i], s, ramp(t, 1.6 + i * 1.3, 2.0 + i * 1.3), { size: 32 }));
      } else if (t < Cc) { const lt = t - B; drawRoom(g, st.room, 1); dim(g, 0.55); phoneJobs(g, st, t, lt); gtaMap(g, st, t); }
      else { vehiclesRow(g, st, t - Cc); }
      if (t > B - 0.3 && t < B + 0.5) dim(g, 1 - Math.abs(t - B - 0.1) / 0.4);
      if (t > Cc - 0.3 && t < Cc + 0.3) dim(g, 1 - Math.abs(t - Cc) / 0.3);
    },
  },
  // ---------- 活着的街道：一天的时间流逝 ----------
  street: {
    async setup(st) { const w = await baseWorld(st, { hour: 5.6, crowd: false }); stageStreet(st, w); },
    update(st, t, dt) { streetUpdate(st, t, dt); },
    overlay(g, st, t) { const v = drawWorld(g, st, { x: 1700 + Math.sin(t * 0.15) * 30, y: 960, z: 3 }); agentBubbles(g, st, v); clockHud(g, st.w.hour, ramp(t, 0.3, 0.8));
      const ph = st.phase; if (ph && t - ph.t0 < 2.2) { const a = fadeWin(t - ph.t0, 0, 2.2, 0.2); pxBox(g, 60, 150, TW(g, ph.label, 36, { px: true }) + 60, 70, a, { fill: '#fff6e2' }); T(g, ph.label, 90, 186, 36, C.ink, { px: true, base: 'middle', a }); }
      if (st.flash > 0) dim(g, st.flash); },
  },
  // ---------- 居民大脑 ----------
  brain: {
    async setup(st) { const w = await baseWorld(st, { hour: 9.5 }); await loadAll([ART + 'por_wang.png']); stageBrain(st, w); },
    update(st, t, dt) { simUpdate(st, dt); brainUpdate(st, t, dt); },
    overlay(g, st, t) { brainDraw(g, st, t); },
  },
  // ---------- 分层模拟 ----------
  lod: {
    async setup(st) { const w = await baseWorld(st, { hour: 14 }); lodSetup(st, w); },
    update(st, t, dt) { simUpdate(st, dt); lodUpdate(st, t, dt); },
    overlay(g, st, t) { lodDraw(g, st, t); },
  },
  // ---------- 随机事件：老人摔倒 ----------
  event: {
    async setup(st) { const w = await baseWorld(st, { hour: 15.5, crowd: false }); stageEvent(st, w); },
    update(st, t, dt) { simUpdate(st, dt); eventUpdate(st, t, dt); },
    overlay(g, st, t) { eventDraw(g, st, t); },
  },
  events2: {
    async setup(st) { await loadAll(['ev_typhoon', 'ev_fire', 'ev_lost', 'ev_propose'].map((n) => ART + n + '.png')); },
    overlay(g, st, t) { g.fillStyle = '#17120e'; g.fillRect(0, 0, W, H);
      const L = [['ev_typhoon', '台风天 · 整条街停电', 'cloud-lightning'], ['ev_fire', '夜市 · 摊位失火', 'flame'], ['ev_lost', '车站 · 孩子走丢', 'baby'], ['ev_propose', '海边 · 街头求婚', 'heart']];
      L.forEach(([n, s, ic], i) => { const t0 = 0.6 + i * 2.2; const a = ramp(t, t0, t0 + 0.35); const x = 90 + (i % 2) * 885, y = 120 + Math.floor(i / 2) * 420; const p = 0.92 + 0.08 * smooth(a);
        g.save(); g.globalAlpha = a; g.translate(x + 415, y + 190); g.scale(p, p); g.translate(-415, -190); fit(g, A(n), 0, 0, 830, 380, 1, { cover: true }); vgrad2(g, 0, 250, 830, 130); icon(g, ic, 40, 335, 34, C.amber); T(g, s, 72, 315, 36, '#fff', { w: 800, shadow: 8 }); g.restore(); });
      const a = ramp(t, cue(st, 1, 0.3), cue(st, 1, 0.8)); if (a > 0) { dim(g, 0.45 * a); panel(g, W / 2 - 520, 440, 1040, 150, a, { fill: 'rgba(242,169,59,0.95)' }); T(g, '你在场 ≠ 你不在场：结果完全不同', W / 2, 515, 50, C.ink, { a, w: 900, align: 'center', base: 'middle' }); }
    },
  },
  // ---------- 室内 ----------
  interior: {
    async setup(st) { const w = await baseWorld(st, { hour: 16 }); await loadAll(['int_clock', 'por_zhong', 'flashback'].map((n) => ART + n + '.png')); await stageInterior(st, w); },
    update(st, t, dt) { simUpdate(st, dt); interiorUpdate(st, t, dt); },
    overlay(g, st, t) { interiorDraw(g, st, t); },
  },
  rooms: {
    async setup(st) { st.rooms = []; for (const R of ROOMS) st.rooms.push(await roomSim(R.img, R.actors)); },
    update(st, t, dt) { st.rooms.forEach((r) => r.update(dt)); },
    overlay(g, st, t) { const k = Math.min(ROOMS.length - 1, Math.floor(t / (st.dur / ROOMS.length))); const R = ROOMS[k], lt = t - k * (st.dur / ROOMS.length); drawRoom(g, st.rooms[k], 1);
      const a = ramp(lt, 0.3, 0.7); const w = TW(g, R.who, 34, { px: true }) + 70; pxBox(g, 60, 150, Math.max(w, TW(g, R.story, 26, { px: true }) + 60), 128, a); T(g, R.who, 90, 190, 34, C.ink, { px: true, base: 'middle', a }); T(g, R.story, 90, 240, 26, '#6a5240', { px: true, base: 'middle', a });
      if (lt < 0.25) dim(g, 1 - lt / 0.25); },
  },
  // ---------- 主线 ----------
  story: {
    async setup(st) { await loadAll(['key_art', 'por_wang', 'por_xm', 'por_chen', 'por_zhong', 'por_zhou'].map((n) => ART + n + '.png')); },
    overlay(g, st, t) { storyDraw(g, st, t); },
  },
  endings: {
    async setup(st) { await loadAll(['end_keep', 'end_trendy', 'end_half'].map((n) => ART + n + '.png')); },
    overlay(g, st, t) { g.fillStyle = '#17120e'; g.fillRect(0, 0, W, H); const L = [['end_keep', '老街完整保留', '街坊节年年办'], ['end_trendy', '改成网红商业街', '老住户陆续搬走'], ['end_half', '拆一半，留一半', '新旧隔着一道围墙']];
      L.forEach(([n, s, s2], i) => { const t0 = 0.5 + i * 1.6; const a = ramp(t, t0, t0 + 0.4); const x = 70 + i * 600, y = 200; g.save(); g.globalAlpha = a; fit(g, A(n), x, y + (1 - smooth(a)) * 30, 580, 560, 1, { cover: true }); g.restore(); panel(g, x, y + 470, 580, 130, a, { fill: 'rgba(18,14,10,0.9)', r: 0 }); T(g, `结局 ${'ABC'[i]} · ${s}`, x + 30, y + 492, 38, C.text, { a, w: 800 }); T(g, s2, x + 30, y + 548, 28, C.dim, { a, w: 500 }); });
      const a = ramp(t, 6.2, 6.7); if (a > 0) { panel(g, W / 2 - 360, 95, 720, 76, a, { fill: 'rgba(242,169,59,0.95)' }); T(g, '地图会跟着结局真的改变', W / 2, 134, 38, C.ink, { a, w: 900, align: 'center', base: 'middle' }); } },
  },
  // ---------- 版本 ----------
  versions: {
    async setup(st) { await loadAll([ART + 'map.png']); },
    overlay(g, st, t) { versionsDraw(g, st, t); },
  },
  // ---------- 技术 ----------
  tech: {
    async setup(st) { await loadCity(); await loadSheet('npc_office_lin'); await loadAll([ART + 'por_wang.png']); },
    overlay(g, st, t) { techDraw(g, st, t); },
  },
  outro: {
    async setup(st) { await loadAll([ART + 'key_art.png']); },
    overlay(g, st, t) { cover(g, A('key_art'), 1.08 + t * 0.003, 0.5, 0.55); dim(g, 0.62);
      T(g, '请你来定', 140, 150, 64, C.amber, { w: 900, a: ramp(t, 0.2, 0.6) });
      const Q = [['user-round', '主角的身份与故事基调', '万事屋青年？记者？外卖员？温情 / 悬疑 / 轻喜剧'], ['map', '城市更偏哪种味道', '香港 · 台湾 · 上海 · 东南亚'], ['heart', '要不要加恋爱和养成', '好感度、约会、成家、店铺经营']];
      Q.forEach(([ic, s, sub], i) => { const t0 = cue(st, 0, 3 + i * 3.2); const a = ramp(t, t0, t0 + 0.4); panel(g, 140, 270 + i * 170, 1100, 140, a, { accent: C.amber }); icon(g, ic, 210, 340 + i * 170, 50, C.amber, a); T(g, s, 270, 290 + i * 170, 44, C.text, { a, w: 800 }); T(g, sub, 270, 350 + i * 170, 30, C.dim, { a, w: 500 }); });
      const a = ramp(t, cue(st, 1), cue(st, 1, 0.5)); if (a > 0) { g.save(); rrect(g, 140, 800, 760, 84, 42); g.globalAlpha = a; g.fillStyle = C.amber; g.fill(); g.restore(); T(g, '下一步：做第一条能玩的街道', 520, 843, 40, C.ink, { a, w: 900, align: 'center', base: 'middle' }); } },
  },
};
function vgrad2(g, x, y, w, h) { const gr = g.createLinearGradient(0, y, 0, y + h); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,0.85)'); g.fillStyle = gr; g.fillRect(x, y, w, h); }

// 地图上的区域（相对坐标，按 map.png 调）
const DIST = [
  { name: '老城区', x: 0.3, y: 0.44, r: 0.17, open: true },
  { name: '渔港码头', x: 0.4, y: 0.8, r: 0.14, open: true },
  { name: '夜市', x: 0.68, y: 0.5, r: 0.1 },
  { name: '商务区', x: 0.7, y: 0.14, r: 0.17 },
  { name: '半山', x: 0.15, y: 0.13, r: 0.15 },
  { name: '离岛', x: 0.9, y: 0.84, r: 0.08 },
];

// ---------- 室内小模拟：AI 室内图（真像素）+ 人物 ----------
import { Agent } from './g9city.js';
const ROOM_META = { // 每张室内图的地板可走区 + 门（室内图的像素坐标，处理后再调）
  int_wanshi: { floor: [0.18, 0.45, 0.82, 0.9], door: [0.5, 0.95] },
  int_clock: { floor: [0.15, 0.5, 0.85, 0.9], door: [0.5, 0.95], counter: [0.5, 0.42] },
  int_noodle: { floor: [0.15, 0.45, 0.85, 0.9], door: [0.5, 0.95] },
  int_home: { floor: [0.15, 0.45, 0.85, 0.9], door: [0.5, 0.95] },
};
const ROOMS = [
  { img: 'int_noodle', who: '阿珍 · 面馆老板娘', story: '想把面馆传给女儿，女儿却想去商务区上班', actors: [{ sheet: 'hero_aunt', at: [0.5, 0.35], dir: 'down' }, { sheet: 'npc_office', at: [0.52, 0.64], dir: 'up' }, { sheet: 'npc_student', at: [0.37, 0.67], dir: 'right' }] },
  { img: 'int_home', who: '周伯 · 退休船工', story: '老伴走后一个人住，每天下午去公园下棋', actors: [{ sheet: 'npc_office_old', at: [0.62, 0.72], dir: 'down' }] },
  { img: 'int_wanshi', who: '万事屋 · 你的店', story: '委托板上贴满了街坊们的麻烦事', actors: [{ sheet: 'npc_office_lin', at: [0.5, 0.74], dir: 'right' }, { sheet: 'npc_student_g', at: [0.6, 0.74], dir: 'left' }] },
];
async function roomSim(name, actors) {
  await loadAll([ART + name + '.png']); for (const a of actors) await loadSheet(a.sheet);
  const im = A(name); const meta = ROOM_META[name] || ROOM_META.int_wanshi; const RW = im.width || 384, RH = im.height || 256;
  const r = { name, im, RW, RH, meta, agents: [], t: 0 };
  for (const a of actors) { const at = a.at === 'center' ? [0.5, 0.7] : a.at; const ag = new Agent({ sheet: a.sheet, x: at[0] * RW, y: at[1] * RH, dir: a.dir || 'down' }); ag.face = a.dir; r.agents.push(ag); }
  r.update = (dt) => { r.t += dt; r.agents.forEach((a) => a.update(dt)); };
  return r;
}
const rpc = document.createElement('canvas');
// 室内画面：整数倍放大，居中，四周黑
function drawRoom(g, r, a = 1, o = {}) {
  const im = r.im; const RW = r.RW, RH = r.RH; rpc.width = RW; rpc.height = RH; const c = rpc.getContext('2d'); c.imageSmoothingEnabled = false; c.clearRect(0, 0, RW, RH);
  if (im.width) c.drawImage(im, 0, 0, RW, RH); else { c.fillStyle = '#6b5643'; c.fillRect(0, 0, RW, RH); }
  [...r.agents].sort((p, q) => p.y - q.y).forEach((ag) => ag.draw(c));
  const s = o.s || Math.min(Math.floor(H / RH), Math.floor(W / RW)) || 1; const k = Math.min(W / RW, H / RH); const sc = Math.max(s, Math.min(k, s)); const dw = RW * sc, dh = RH * sc;
  g.save(); g.globalAlpha *= a; g.fillStyle = '#000'; g.fillRect(0, 0, W, H); g.imageSmoothingEnabled = false; g.drawImage(rpc, (W - dw) / 2, (H - dh) / 2, dw, dh); g.restore();
  r.sx = (x) => (W - dw) / 2 + x * sc; r.sy = (y) => (H - dh) / 2 + y * sc; r.sc = sc;
  for (const ag of r.agents) for (const b of ag.bubbles) bubble(g, r.sx(ag.x), r.sy(ag.y - 40), b.text, { icon: b.icon, ic: b.col, a: fadeWin(b.t, 0, b.dur, 0.2), pop: popIn(b.t, 0) });
}

// ---------- hero 场景的部件 ----------
function phoneJobs(g, st, t, lt) {
  const x = 120, y = 110, w = 620, h = 820; const a = ramp(lt, 0.2, 0.6); pxBox(g, x, y, w, h, a, { fill: '#2b231d', border: '#140f0b' }); pxBox(g, x + 22, y + 60, w - 44, h - 110, a, { fill: '#fff6e2', border: '#140f0b' });
  T(g, '万事屋 · 委托', x + w / 2, y + 32, 30, '#f6efe4', { px: true, align: 'center', base: 'middle', a });
  const J = [['package', '跑腿送货 · 限时 12 分钟', '¥80'], ['car-taxi-front', '开出租 · 码头到老城', '¥35'], ['wrench', '修冰箱 · 王阿姨家', '¥60'], ['cat', '找猫 · 三花，叫「豆包」', '¥120'], ['handshake', '调解 · 楼上漏水吵架', '好感'], ['camera', '报社约拍 · 码头日出', '¥150']];
  J.forEach(([ic, s, p], i) => { const t0 = 0.8 + i * 0.9; const b = ramp(lt, t0, t0 + 0.3); if (b <= 0) return; const yy = y + 90 + i * 112; g.save(); g.globalAlpha = a * b; g.fillStyle = i === Math.floor((lt - 6) / 1.4) % 6 && lt > 6 ? '#f7dc9a' : 'rgba(90,58,36,0.06)'; g.fillRect(x + 40, yy, w - 80, 96); g.restore();
    icon(g, ic, x + 84, yy + 48, 40, C.red, a * b); T(g, s, x + 122, yy + 30, 28, C.ink, { px: true, base: 'middle', a: a * b }); T(g, p, x + w - 66, yy + 70, 28, '#b0561f', { px: true, align: 'right', base: 'middle', a: a * b }); });
}
function gtaMap(g, st, t) {
  const t0 = cue(st, 2); const a = ramp(t, t0, t0 + 0.4); if (a <= 0) return; const x = 820, y = 160; panel(g, x, y, 1000, 640, a);
  T(g, 'GTA 式玩法', x + 60, y + 40, 32, C.dim, { a, w: 600 }); T(g, '万事屋版本', x + 560, y + 40, 32, C.amber, { a, w: 700 });
  const R = [['飙车', '限时送货、送病人去医院'], ['追逐', '追偷包贼、追跑掉的猫'], ['潜入', '帮报社暗访黑心工厂'], ['调查', '寻人、寻物、查真相']];
  R.forEach(([l, r], i) => { const b = ramp(t, t0 + 0.6 + i * 1.6, t0 + 1.0 + i * 1.6); const yy = y + 120 + i * 120; T(g, l, x + 60, yy, 46, C.text, { a: a * b, w: 800 }); arrow(g, x + 220, yy + 28, x + 520, yy + 28, C.amber, a * b, 4); T(g, r, x + 560, yy + 6, 36, C.text, { a: a * b, w: 600 }); });
}
function vehiclesRow(g, st, lt) {
  g.fillStyle = '#1c1612'; g.fillRect(0, 0, W, H); const im = A('vehicles'); const V = [[0.017, 0.223, 398, 611], [0.248, 0.415, 398, 611], [0.437, 0.706, 425, 611], [0.729, 0.986, 367, 617]]; const L = [['旧自行车', '开局'], ['电驴', '¥2,000'], ['二手车', '¥30,000'], ['小船', '去离岛']];
  T(g, '赚钱 → 升级店面、换交通工具', W / 2, 150, 52, C.text, { w: 900, align: 'center', a: ramp(lt, 0.1, 0.5) });
  L.forEach(([s, p], i) => { const a = ramp(lt, 0.6 + i * 1.3, 1.0 + i * 1.3); const cx = 260 + i * 470, cy = 540; if (im.width && a > 0) { const [u0, u1, y0, y1] = V[i]; const sw = (u1 - u0) * im.width; const sh = y1 - y0 + 1; const sc = 1.0; g.save(); g.globalAlpha = a; g.imageSmoothingEnabled = false; g.drawImage(im, u0 * im.width, y0, sw, sh, cx - sw * sc / 2, 660 - sh * sc, sw * sc, sh * sc); g.restore(); }
    T(g, s, cx, 760, 44, C.text, { a, w: 800, align: 'center' }); T(g, p, cx, 822, 32, C.amber, { a, w: 600, align: 'center' }); if (i < 3) arrow(g, cx + 170, 520, cx + 280, 520, C.amber, ramp(lt, 1.0 + i * 1.3, 1.3 + i * 1.3), 5); });
}

// ---------- street：一天 ----------
function stageStreet(st, w) {
  const y = P.shopSide; st.aunt = w.add({ sheet: 'hero_aunt', x: 1560, y }); st.cart = null;
  st.crowd = []; for (let i = 0; i < 14; i++) { const a = w.add({ sheet: walkers[i % walkers.length], x: 1400 + i * 60, y: i % 2 ? P.aptSide : y, hidden: true }); st.crowd.push(a); }
  st.phases = [[0, 5.6, '清晨'], [cue(st, 2, 0), 6.0, '06:00 王阿姨出摊'], [cue(st, 2, 2.2), 8.0, '08:00 上班高峰'], [cue(st, 2, 4.6), 12.1, '12:00 面馆排队'], [cue(st, 2, 7.0), 18.2, '18:00 下班回家'], [cue(st, 2, 9.0), 22.0, '22:00 夜市开张']];
  st.aunt.go([[P.stall[0] - 40, y, 0], [P.stall[0], y, 99, 'down']]);
}
function streetUpdate(st, t, dt) {
  const w = st.w; w.update(dt); st.flash = 0;
  let k = 0; st.phases.forEach((p, i) => { if (t >= p[0]) k = i; }); const p = st.phases[k], q = st.phases[k + 1];
  // 时间：本阶段内缓慢推进，阶段切换时快速转
  const tgt = p[1] + (q ? Math.min(1, (t - p[0]) / Math.max(0.1, q[0] - p[0])) * 0.6 : (t - p[0]) * 0.05); w.hour = lerp(w.hour, tgt, Math.min(1, dt * 6));
  if (q && q[0] - t < 0.18) st.flash = (0.18 - (q[0] - t)) / 0.18 * 0.5; if (t - p[0] < 0.18 && k > 0) st.flash = (0.18 - (t - p[0])) / 0.18 * 0.5;
  if (once(st, 'ph' + k, true)) { st.phase = { t0: t, label: p[2] }; phaseStage(st, k); }
}
function phaseStage(st, k) {
  const w = st.w, y = P.shopSide, cr = st.crowd; const hideAll = () => cr.forEach((a) => { a.hidden = true; a.route = []; a.bubbles = []; a.spd = 1; });
  if (k === 1) { st.cartP = w.prop('stall_food', P.stall[0] + 34, y + 2, { glow: 40 }); st.aunt.say('出摊咯！豆浆油条～', { icon: 'soup', dur: 2.2 }); cr.slice(0, 3).forEach((a, i) => { a.hidden = false; a.x = 1500 - i * 70; a.y = y; a.go([[P.stall[0] - 24 - i * 18, y, 3, 'right'], [2200, y]]); }); cr[0].say('两根油条！', { icon: 'coffee', dur: 1.8 }); }
  if (k === 2) { hideAll(); cr.forEach((a, i) => { if (i > 9) return; a.hidden = false; const r2 = i % 2 === 0; a.x = r2 ? 1400 + i * 45 : 2050 - i * 40; a.y = r2 ? y + 2 : P.aptSide; a.spd = 1.55; a.go([[r2 ? 2400 : 1200, a.y]]); }); cr[1].say('要迟到了！', { icon: 'alarm-clock', dur: 2 }); cr[4].say('地铁又挤爆了…', { icon: 'train-front', dur: 2 }); }
  if (k === 3) { hideAll(); st.aunt.hidden = true; if (st.cartP) w.extra = w.extra.filter((e) => e !== st.cartP); const d = P.noodleDoor; cr.slice(0, 6).forEach((a, i) => { a.hidden = false; a.x = d[0] - 40 - i * 22; a.y = y; a.face = 'right'; a.route = []; }); cr[6].hidden = false; cr[6].x = 1500; cr[6].y = y; cr[6].go([[d[0] - 40 - 6 * 22, y, 9, 'right']]); cr[2].say('饿了 → 去面馆', { icon: 'soup', dur: 2.1 }); }
  if (k === 4) { hideAll(); cr.forEach((a, i) => { if (i > 7) return; a.hidden = false; a.x = 1500 + i * 70; a.y = i % 2 ? P.aptSide : y; a.go([[a.x - 600, a.y]]); }); cr[3].say('下班回家', { icon: 'house', dur: 2 }); cr[6].say('买点菜…', { icon: 'shopping-bag', dur: 1.8 }); }
  if (k === 5) { hideAll(); st.aunt.hidden = true; [['stall_fruit', 1560], ['stall_flower', 1680], ['stall_food', 1800], ['stall_food', 1930]].forEach(([s, x], i) => w.prop(s, x, y + 4, { glow: 70, flip: i % 2 })); cr.forEach((a, i) => { if (i > 9) return; a.hidden = false; a.x = 1500 + i * 48; a.y = y + 14 + (i % 2) * 4; a.spd = 0.6; a.go([[a.x + (i % 2 ? 90 : -90), a.y, 1.5], [a.x, a.y, 1]], true); }); cr[2].say('宵夜！', { icon: 'soup', dur: 2 }); }
}

// ---------- brain ----------
function stageBrain(st, w) { const y = P.shopSide; st.aunt = w.add({ sheet: 'hero_aunt', x: P.stall[0], y, dir: 'down' }); st.aunt.face = 'down'; w.prop('stall_food', P.stall[0] + 34, y + 2);
  st.lin = w.add({ sheet: 'npc_office_lin', x: 1560, y: P.aptSide }); st.cust = w.add({ sheet: 'npc_office_b', x: P.stall[0] - 26, y, dir: 'right' }); st.cust.face = 'right'; st.nb = w.add({ sheet: 'npc_office_old', x: P.stall[0] + 110, y, dir: 'left' }); st.nb.face = 'left'; }
function brainUpdate(st, t, dt) {
  if (once(st, 'tired', t > cue(st, 1, 6.5))) st.aunt.say('腰疼…今天早点收摊', { icon: 'bed', dur: 3 });
  if (once(st, 'rumor', t > cue(st, 2, 6.2))) { st.aunt.say('听说海晟要拆这条街？', { icon: 'message-circle', dur: 2.6 }); }
  if (once(st, 'rumor2', t > cue(st, 2, 8.4))) st.nb.say('真的假的？！', { icon: 'triangle-alert', dur: 2 });
  if (once(st, 'linwalk', t > cue(st, 3, 0))) st.lin.go([[P.stall[0] - 60, P.aptSide], [P.stall[0] - 60, P.shopSide + 2]]);
  if (once(st, 'react1', t > cue(st, 3, 2.6))) st.aunt.say('小林！来碗豆浆？', { icon: 'face-grinning', dur: 2.6 });
  if (once(st, 'react2', t > cue(st, 3, 3.6))) st.nb.say('上次谢谢你啊', { icon: 'heart', dur: 2.4 });
  if (once(st, 'react3', t > cue(st, 3, 4.6))) st.cust.say('万事屋的？', { icon: 'eye', dur: 2.2 });
}
function brainDraw(g, st, t) {
  const zf = ramp(t, 0, 1.6); const cam = { x: lerp(1760, P.stall[0] + 140, ease(zf)), y: lerp(960, 990, ease(zf)), z: lerp(3, 4, ease(zf)) };
  const v = drawWorld(g, st, cam); agentBubbles(g, st, v);
  // 选中标记
  const [hx, hy] = head(v, st.aunt); const bob = Math.sin(t * 6) * 4; g.fillStyle = '#f2c94c'; g.beginPath(); g.moveTo(hx - 14, hy - 74 + bob); g.lineTo(hx + 14, hy - 74 + bob); g.lineTo(hx, hy - 54 + bob); g.closePath(); g.fill(); g.strokeStyle = '#3a2a20'; g.lineWidth = 3; g.stroke();
  const a = ramp(t, 0.8, 1.3); const X = 1040, Y = 110, PW = 830; panel(g, X, Y, PW, 830, a);
  portrait(g, 'wang', X + 40, Y + 40, 150, a); T(g, '王秀英', X + 220, Y + 44, 56, C.text, { a, w: 900 }); T(g, '52 岁 · 早餐摊主 · 住老城区 3 年', X + 222, Y + 120, 28, C.amber, { a, w: 600 });
  const rows = [['users', '家人', '儿子在外地打工，一年回来一次'], ['face-grinning', '性格', '热心、嘴快、爱面子'], ['lock', '秘密', '偷偷攒钱，想开一家自己的店']];
  rows.forEach(([ic, k, s], i) => { const b = ramp(t, cue(st, 0, 2 + i * 1.6), cue(st, 0, 2.4 + i * 1.6)) * a; icon(g, ic, X + 58, Y + 236 + i * 52, 28, C.amber, b); T(g, k, X + 90, Y + 220 + i * 52, 28, C.dim, { a: b, w: 600 }); T(g, s, X + 170, Y + 220 + i * 52, 28, C.text, { a: b, w: 600 }); });
  // 日程 + 需求
  const b1 = ramp(t, cue(st, 1), cue(st, 1, 0.5)) * a; const yS = Y + 400;
  if (b1 > 0) { T(g, '日程', X + 40, yS, 28, C.amber, { a: b1, w: 800 }); const S = [['05:30', '备料'], ['06:00', '出摊'], ['10:30', '收摊'], ['14:00', '打麻将'], ['18:00', '做饭'], ['21:30', '睡觉']]; S.forEach(([h, s], i) => { const x = X + 40 + i * 128; g.save(); g.globalAlpha = b1; g.fillStyle = i === 1 ? C.amber : 'rgba(255,245,230,0.14)'; g.fillRect(x, yS + 44, 120, 64); g.restore(); T(g, h, x + 60, yS + 50, 22, i === 1 ? C.ink : C.dim, { a: b1, num: true, align: 'center' }); T(g, s, x + 60, yS + 76, 24, i === 1 ? C.ink : C.text, { a: b1, w: 700, align: 'center' }); });
    const b2 = ramp(t, cue(st, 1, 3.2), cue(st, 1, 3.7)) * a; const N = [['饥饿', 0.35, C.amber], ['疲劳', lerp(0.55, 0.86, ramp(t, cue(st, 1, 4), cue(st, 1, 6.5))), C.red], ['心情', 0.7, C.green], ['钱包', 0.42, C.teal]];
    N.forEach(([k, val, col], i) => { const x = X + 40 + (i % 2) * 390, y = yS + 140 + Math.floor(i / 2) * 50; T(g, k, x, y, 26, C.dim, { a: b2, w: 600 }); bar(g, x + 70, y + 8, 280, 16, val, col, b2); });
    if (t > cue(st, 1, 6.5)) { const b3 = ramp(t, cue(st, 1, 6.5), cue(st, 1, 7)) * a; panel(g, X + 40, yS + 250, PW - 80, 56, b3, { fill: 'rgba(229,87,62,0.9)', r: 6 }); T(g, '疲劳 > 80 → 改计划：提前收摊', X + 64, yS + 278, 28, '#fff', { a: b3, w: 800, base: 'middle' }); }
  }
  // 记忆 / 关系 / 传闻：换页
  const b4 = ramp(t, cue(st, 2), cue(st, 2, 0.5)) * a;
  if (b4 > 0) { g.save(); g.globalAlpha = b4; g.fillStyle = 'rgba(22,17,13,0.97)'; g.fillRect(X + 20, yS - 10, PW - 40, 330); g.restore();
    T(g, '记忆', X + 40, yS, 28, C.amber, { a: b4, w: 800 }); [['帮我修好了推车', '+15', C.green], ['上周插队买豆浆', '−5', C.red]].forEach(([s, d, col], i) => { const b = ramp(t, cue(st, 2, 0.6 + i * 0.8), cue(st, 2, 1 + i * 0.8)) * b4; T(g, '林屿：' + s, X + 40, yS + 48 + i * 44, 28, C.text, { a: b, w: 600 }); T(g, d, X + 420, yS + 48 + i * 44, 28, col, { a: b, w: 800 }); });
    T(g, '关系网', X + 480, yS, 28, C.amber, { a: b4, w: 800 }); const cx = X + 640, cy = yS + 140; const Nd = [['儿子', -110, -70, C.green], ['周伯', 110, -70, C.green], ['钟伯', -120, 80, C.green], ['海晟拆迁办', 90, 90, C.red]];
    const b5 = ramp(t, cue(st, 2, 2.2), cue(st, 2, 2.8)) * b4; Nd.forEach(([s, dx, dy, col]) => { g.save(); g.globalAlpha = b5; g.strokeStyle = col; g.lineWidth = 3; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + dx, cy + dy); g.stroke(); g.restore(); const tw = TW(g, s, 24) + 24; panel(g, cx + dx - tw / 2, cy + dy - 20, tw, 40, b5, { fill: 'rgba(255,245,230,0.12)', r: 6 }); T(g, s, cx + dx, cy + dy, 24, C.text, { a: b5, w: 600, align: 'center', base: 'middle' }); });
    g.save(); g.globalAlpha = b5; g.fillStyle = C.amber; g.beginPath(); g.arc(cx, cy, 30, 0, 7); g.fill(); g.restore(); T(g, '王', cx, cy, 28, C.ink, { a: b5, w: 900, align: 'center', base: 'middle' });
    const b6 = ramp(t, cue(st, 2, 5.6), cue(st, 2, 6.1)) * b4; T(g, '传闻', X + 40, yS + 160, 28, C.amber, { a: b6, w: 800 }); T(g, '「海晟要拆这条街」', X + 40, yS + 206, 30, C.text, { a: b6, w: 700 }); T(g, '王秀英 → 周伯 → 整条街', X + 40, yS + 252, 26, C.dim, { a: b6, w: 600 }); }
  const b7 = ramp(t, cue(st, 3, 0), cue(st, 3, 0.4)); if (b7 > 0) { g.save(); g.globalAlpha = b7 * 0.0; g.restore(); }
}

// ---------- lod：全城分层模拟 ----------
function lodSetup(st, w) {
  st.dots = []; const lines = [[0, 2457, 470], [0, 2457, 563], [0, 2457, 1040], [0, 2457, 1097], [0, 2457, 1630], [0, 2457, 1690], [0, 2457, 1735], [820, 820, 0, 1700], [890, 890, 0, 1700], [1605, 1605, 0, 1700], [1675, 1675, 0, 1700], [0, 2457, 776], [0, 2457, 1340], [900, 1600, 820]];
  let s = 7; const r = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
  for (let i = 0; i < 260; i++) { const L = lines[i % lines.length]; const d = { L, u: r(), v: (0.02 + r() * 0.04) * (r() < 0.5 ? -1 : 1), qx: 0, qy: 0, tick: r() * 3 }; st.dots.push(d); }
  st.center = [1250, 1000]; st.notes = [];
}
const dotPos = (d) => { const L = d.L; const u = ((d.u % 1) + 1) % 1; return L.length === 3 ? [lerp(L[0], L[1], u), L[2]] : [L[0], lerp(L[2], L[3], u)]; };
function lodUpdate(st, t, dt) {
  const NOTES = ['+¥120 上班', '和邻居吵架', '去医院复查', '买菜做饭', '加班到深夜', '孩子考试', '打麻将输了', '收到快递', '面馆涨价', '约会'];
  let k = 0; for (const d of st.dots) { const [x, y] = dotPos(d); const r = Math.hypot(x - st.center[0], y - st.center[1]); d.ring = r < 330 ? 0 : r < 760 ? 1 : 2;
    if (d.ring === 0) d.u += d.v * dt; else if (d.ring === 1) { d.acc = (d.acc || 0) + dt; if (d.acc > 0.5) { d.u += d.v * 0.5; d.acc = 0; } } else { d.tick -= dt; if (d.tick < 0) { d.tick = 2.5 + (k % 5) * 0.7; d.u += d.v * 3; if (t > 2 && st.notes.length < 9 && (k % 3 === 0)) st.notes.push({ x, y, s: NOTES[(k + Math.floor(t)) % NOTES.length], t0: t }); } }
    k++; }
  st.notes = st.notes.filter((n) => t - n.t0 < 2.2);
}
function lodDraw(g, st, t) {
  const z0 = 1080 / 1845; const zIn = ramp(t, 0, 2.2); const cam = { x: lerp(st.center[0], 2457 / 2, ease(zIn)), y: lerp(st.center[1], 1845 / 2, ease(zIn)), z: lerp(3, z0, ease(zIn)) };
  const v = drawWorld(g, st, cam); dim(g, 0.35 * zIn);
  const cx = v.sx(st.center[0]), cy = v.sy(st.center[1]); const a = ramp(t, 2.0, 2.6);
  const rings = [[760, 'rgba(242,169,59,0.10)', C.amber], [330, 'rgba(91,185,116,0.16)', C.green]];
  for (const [R0, f, s] of rings) { g.save(); g.globalAlpha = a; g.beginPath(); g.arc(cx, cy, R0 * v.z, 0, 7); g.fillStyle = f; g.fill(); g.strokeStyle = s; g.lineWidth = 4; g.setLineDash([14, 10]); g.stroke(); g.restore(); }
  for (const d of st.dots) { const [x, y] = dotPos(d); const sx = v.sx(x), sy = v.sy(y); g.save(); g.globalAlpha = a; g.fillStyle = d.ring === 0 ? '#7cf08f' : d.ring === 1 ? '#ffc35c' : '#e9e0d2'; g.beginPath(); g.arc(sx, sy, d.ring === 0 ? 6 : 5, 0, 7); g.fill(); g.restore(); }
  // 玩家
  if (a > 0) { g.save(); g.globalAlpha = a; g.fillStyle = C.red; g.beginPath(); g.arc(cx, cy, 11, 0, 7); g.fill(); g.strokeStyle = '#fff'; g.lineWidth = 3; g.stroke(); g.restore(); T(g, '你', cx, cy - 34, 28, '#fff', { a, w: 900, align: 'center', base: 'middle', stroke: 5 }); }
  const L = [[cue(st, 1, 0.5), C.green, '身边 · 逐帧完整模拟'], [cue(st, 1, 4), C.amber, '同一街区 · 简化动作'], [cue(st, 1, 7.2), '#e9e0d2', '全城 · 每小时结算一次']];
  L.forEach(([t0, col, s], i) => { const b = ramp(t, t0, t0 + 0.4); panel(g, 60, 150 + i * 92, 520, 72, b, { accent: col }); T(g, s, 92, 186 + i * 92, 32, C.text, { a: b, w: 700, base: 'middle' }); });
  if (t > cue(st, 1, 7.2)) for (const n of st.notes) { const b = fadeWin(t - n.t0, 0, 2.2, 0.25); bubble(g, v.sx(n.x), v.sy(n.y) - 6, n.s, { a: b, size: 22, pop: popIn(t, n.t0) }); }
  const b2 = ramp(t, cue(st, 2, 3.4), cue(st, 2, 3.9)); if (b2 > 0) { panel(g, W - 640, 150, 580, 330, b2, { accent: C.amber }); T(g, '你离开 3 天后……', W - 600, 178, 34, C.amber, { a: b2, w: 800 }); [['store', '街口新开了一家奶茶店'], ['truck', '李家搬去了商务区'], ['soup', '面馆的面涨了两块']].forEach(([ic, s], i) => item(g, W - 610, 250 + i * 70, ic, s, ramp(t, cue(st, 2, 4.2 + i * 1.1), cue(st, 2, 4.6 + i * 1.1)) * b2, { size: 32 })); }
}

// ---------- event：周伯摔倒 ----------
function stageEvent(st, w) {
  const y = P.shopSide, X = P.crossX + 70; st.ev = { x: X, y };
  st.zhou = w.add({ sheet: 'npc_office_old', x: X - 260, y }); st.zhou.spd = 0.55; st.zhou.go([[X, y]]);
  st.by = [['npc_office_b', X - 150, P.aptSide], ['npc_student', X + 160, y], ['npc_office_c', X + 240, P.aptSide], ['npc_student_g', X - 90, y - 1], ['hero', X + 120, P.aptSide]].map(([s, x, yy], i) => { const a = w.add({ sheet: s, x, y: yy }); a.go([[x + (i % 2 ? -60 : 60), yy, 1], [x, yy, 1]], true); return a; });
  st.lin = w.add({ sheet: 'npc_office_lin', x: X + 420, y: P.aptSide }); st.helped = false;
}
function eventUpdate(st, t, dt) {
  const { x: X, y } = st.ev; const fall = cue(st, 1, 4.2);
  if (once(st, 'fall', t > fall)) { st.zhou.lie = 1; st.zhou.route = []; st.fallT = t; st.w.fx.push(dustFx(X - 10, y)); }
  const near = [[X - 30, y - 2, 'right'], [X + 36, y + 2, 'left'], [X - 2, y + 6, 'up'], [X + 18, y - 10, 'down'], [X - 50, y + 4, 'right']];
  if (once(st, 'gather', t > fall + 0.7)) st.by.forEach((a, i) => { a.loop = false; a.go([[near[i][0], near[i][1], 99, near[i][2]]]); a.spd = 1.3; });
  if (once(st, 'b1', t > fall + 1.4)) st.by[1].say('有人摔倒了！', { icon: 'triangle-alert', dur: 2.4 });
  if (once(st, 'b2', t > fall + 2.6)) st.by[0].say('快打 120！', { icon: 'phone-call', dur: 2.6 });
  if (once(st, 'b3', t > fall + 3.8)) st.by[2].say('我先拍下来…', { icon: 'video', dur: 2.6, col: '#555' });
  if (once(st, 'linGo', t > cue(st, 2, 0.3))) { st.lin.spd = 1.4; st.lin.go([[X + 60, P.aptSide], [X + 60, y + 4], [X + 16, y + 4, 99, 'left']]); }
  if (once(st, 'help', t > cue(st, 2, 6.4))) { st.zhou.lie = 0; st.zhou.dir = 'right'; st.zhou.face = 'right'; st.zhou.say('谢谢你啊，小伙子', { icon: 'heart', dur: 2.6 }); st.helped = true; }
  // 第二天：传闻
  const D = cue(st, 3, 0); if (once(st, 'day2', t > D)) { st.w.hour = 9; st.zhou.hidden = true; st.by.forEach((a, i) => { a.route = []; a.x = X - 300 + i * 150; a.y = i % 2 ? P.aptSide : y; a.face = i % 2 ? 'left' : 'right'; a.bubbles = []; }); st.lin.x = X + 520; st.lin.y = P.aptSide; st.lin.route = []; }
  const R = ['听说万事屋的小林…', '昨天扶了周伯去医院', '这小伙子人不错！', '我家水管也找他修', '周伯的儿子说要谢他'];
  R.forEach((s, i) => { if (once(st, 'r' + i, t > D + 0.6 + i * 1.1)) st.by[i].say(s, { icon: 'message-circle', dur: 3.2, col: C.teal }); });
}
function dustFx(x, y) { return { t: 0, dur: 0.9, draw(g, u) { g.save(); g.globalAlpha = 1 - u; g.fillStyle = '#d8cbb4'; for (let i = 0; i < 7; i++) { const an = (i / 7) * Math.PI * 2; g.fillRect(Math.round(x + Math.cos(an) * (4 + u * 14)), Math.round(y - 3 + Math.sin(an) * (2 + u * 5)), 2, 2); } g.restore(); } }; }
function eventDraw(g, st, t) {
  const D = cue(st, 3, 0); const { x: X, y } = st.ev; const day2 = t > D;
  const cam = day2 ? { x: X + 20, y: y - 20, z: 3 } : { x: lerp(X - 140, X + 40, ease(ramp(t, 0, cue(st, 1, 4)))), y: y - 30, z: lerp(3, 3.6, ease(ramp(t, cue(st, 1, 4), cue(st, 1, 6)))) };
  const v = drawWorld(g, st, cam); agentBubbles(g, st, v);
  if (st.fallT && !st.helped && !day2) { const u = t - st.fallT; if (u < 1.2) { const [hx, hy] = [v.sx(X - 10), v.sy(y - 24)]; T(g, '!', hx, hy - u * 30, 90, C.red, { px: true, align: 'center', base: 'middle', stroke: 8, strokeC: '#fff', a: 1 - u / 1.2 }); } }
  // 选择提示
  const c0 = cue(st, 2, 3.4), c1 = cue(st, 2, 6.4); const a = fadeWin(t, c0, c1 + 0.6, 0.25);
  if (a > 0 && !day2) { const x = W / 2 - 330, yy = 760; pxBox(g, x, yy, 660, 120, a, { fill: '#fff6e2' }); keycap(g, x + 40, yy + 36, 'E', a, t > c1 - 0.3 && t < c1 + 0.2 ? 1 : 0); T(g, '扶起周伯', x + 104, yy + 61, 34, C.ink, { px: true, base: 'middle', a }); keycap(g, x + 360, yy + 36, 'Q', a); T(g, '走开', x + 424, yy + 61, 34, '#7a6450', { px: true, base: 'middle', a }); }
  if (day2) { const u = t - D; if (u < 0.35) dim(g, 1 - u / 0.35); const b = ramp(u, 0.2, 0.6); pxBox(g, 60, 150, 280, 70, b, { fill: '#fff6e2' }); T(g, '第二天', 92, 186, 36, C.ink, { px: true, base: 'middle', a: b });
    // 传闻连线
    g.save(); g.strokeStyle = 'rgba(47,163,145,0.9)'; g.lineWidth = 4; g.setLineDash([10, 8]); for (let i = 0; i < 4; i++) { const p = st.by[i], q = st.by[i + 1]; const b2 = ramp(u, 1.2 + i * 1.1, 1.6 + i * 1.1); if (b2 <= 0) continue; const x0 = v.sx(p.x), y0 = v.sy(p.y - 20), x1 = v.sx(q.x), y1 = v.sy(q.y - 20); g.globalAlpha = b2; g.beginPath(); g.moveTo(x0, y0); g.lineTo(lerp(x0, x1, b2), lerp(y0, y1, b2)); g.stroke(); } g.restore();
    toast(g, 'users', '街坊信任 +8', null, ramp(u, 5.6, 6.0), 150); toast(g, 'star', '名声 +5', null, ramp(u, 6.2, 6.6), 240); toast(g, 'hand-heart', '周海（周伯的儿子）好感 +20', '以后在关键时刻会帮你', ramp(u, 6.8, 7.2), 330, C.red); toast(g, 'package', '新委托 ×3', null, ramp(u, 7.6, 8.0), 452, C.amber); }
}

// ---------- interior：钟表铺 ----------
function stageInterior(st, w) {
  const d = P.clockDoor; st.lin = w.add({ sheet: 'npc_office_lin', x: d[0] - 160, y: P.aptSide }); st.lin.go([[d[0], P.aptSide], [d[0], d[1] + 8], [d[0], d[1] - 2]]);
  return roomSim('int_clock', [{ sheet: 'npc_office_old', at: [0.33, 0.545], dir: 'down' }]).then((r) => { st.room = r; const RW = r.RW, RH = r.RH; st.rl = new Agent({ sheet: 'npc_office_lin', x: RW * 0.5, y: RH * 0.98 }); st.rl.dir = 'up'; r.agents.push(st.rl); });
}
const TR = 5.3; // 进门转场时刻
function interiorUpdate(st, t, dt) {
  if (!st.room) return; st.room.update(dt); const r = st.room;
  if (once(st, 'enter', t > TR + 0.4)) st.rl.go([[r.RW * 0.5, r.RH * 0.86], [r.RW * 0.56, r.RH * 0.86], [r.RW * 0.56, r.RH * 0.66, 99, 'left']]);
}
function interiorDraw(g, st, t) {
  if (t < TR || !st.room) { const d = P.clockDoor; const v = drawWorld(g, st, { x: d[0] - 40, y: d[1] - 40, z: 3 }); agentBubbles(g, st, v); const b = ramp(t, 2.6, 3.1); if (b > 0 && t < TR) { const [hx, hy] = [v.sx(d[0]), v.sy(d[1] - 70)]; bubble(g, hx, hy, '钟表铺', { icon: 'watch', ic: C.amber, a: b }); }
    if (t > TR - 0.5) { const u = (t - (TR - 0.5)) / 0.5; dim(g, clamp(u)); } return; }
  const r = st.room; drawRoom(g, r, 1); const u = t - TR; if (u < 0.45) dim(g, 1 - u / 0.45);
  const zb = r.agents[0]; const zx = r.sx(zb.x), zy = r.sy(zb.y - 40);
  // 名字 + 交谈提示
  const a1 = fadeWin(t, cue(st, 1, 0.5), cue(st, 2, 0.2), 0.3); if (a1 > 0) { bubble(g, zx, zy - 10, '钟伯', { icon: 'watch', ic: C.amber, a: a1 }); keycap(g, zx + 110, zy - 110, 'E', a1); T(g, '交谈', zx + 170, zy - 85, 30, '#fff', { px: true, base: 'middle', stroke: 5, a: a1 }); }
  // 对话框
  const c2 = cue(st, 2, 0), c3 = cue(st, 3, 0), c4 = cue(st, 4, 0); const a2 = fadeWin(t, c2, c4 - 0.1, 0.25);
  if (a2 > 0) { const lines = [[c2, '钟伯', '又来啦，小林。坐，喝口茶。'], [c2 + 3.2, '钟伯', '这只怀表……停在三点十七分，四十年了。'], [c3 + 0.2, '钟伯', '那年在码头，她说等这只表修好，就回来。']];
    let L = lines[0]; for (const l of lines) if (t >= l[0]) L = l; const n = Math.ceil(L[2].length * clamp((t - L[0]) / (L[2].length * 0.07))); const x = 160, y = 650, w = W - 320, h = 220; pxBox(g, x, y, w, h, a2, { fill: '#fff6e2' }); portrait(g, 'zhong', x + 30, y + 30, 160, a2);
    T(g, L[1], x + 230, y + 46, 34, C.red, { px: true, a: a2 }); T(g, L[2].slice(0, n), x + 230, y + 110, 38, C.ink, { px: true, a: a2 }); }
  // 怀表物品卡
  const a3 = fadeWin(t, c2 + 4.2, c3 + 0.2, 0.3); if (a3 > 0) { pxBox(g, W - 520, 150, 420, 150, a3, { fill: '#fff6e2' }); icon(g, 'watch', W - 455, 225, 64, '#b07a2a', a3); T(g, '旧怀表', W - 390, 192, 36, C.ink, { px: true, a: a3 }); T(g, '指针停在 3:17', W - 390, 244, 28, '#7a6450', { px: true, a: a3 }); }
  // 支线开启 + 回忆
  const a4 = fadeWin(t, c3 + 1.6, c4 + 0.2, 0.4); if (a4 > 0) { g.save(); g.globalAlpha = a4 * 0.92; cover(g, A('flashback'), 1.05 + (t - c3) * 0.01, 0.5, 0.5, 1); g.restore(); vgrad(g, 0, 360, 0.7 * a4, 0); const p = popIn(t, c3 + 2.0); if (p > 0) { g.save(); g.translate(W / 2, 220); g.scale(p, p); pxBox(g, -460, -70, 920, 140, 1, { fill: '#ffe7a8' }); T(g, '新支线', -400, -18, 30, '#8a5a20', { px: true, base: 'middle' }); T(g, '老钟表铺的约定', -400, 30, 52, C.ink, { px: true, base: 'middle' }); icon(g, 'scroll-text', 380, 0, 64, C.red); g.restore(); } }
  // 人生线
  if (t > c4 - 0.2) { const b = ramp(t, c4 - 0.2, c4 + 0.3); g.fillStyle = `rgba(14,11,8,${0.9 * b})`; g.fillRect(0, 0, W, H); T(g, '钟伯的人生线', 150, 180, 48, C.amber, { a: b, w: 900 });
    const N = [['1985', '码头的约定', '她坐船去了离岛'], ['现在', '守着钟表铺', '怀表一直没修'], ['v1.x', '支线：寻找她', '要你帮忙查旧船票'], ['v2.0', '离岛开放', '也许能重逢']];
    N.forEach(([k, s, s2], i) => { const x = 230 + i * 430, y = 520; const c = ramp(t, c4 + 0.4 + i * 0.9, c4 + 0.8 + i * 0.9); if (i < 3) { g.save(); g.globalAlpha = c; g.fillStyle = 'rgba(242,169,59,0.6)'; g.fillRect(x, y - 2, 430, 4); g.restore(); } g.save(); g.globalAlpha = c; g.fillStyle = i === 3 ? '#5bb974' : C.amber; g.beginPath(); g.arc(x, y, 18, 0, 7); g.fill(); g.restore(); T(g, k, x, y - 80, 34, C.amber, { a: c, num: true, align: 'center' }); T(g, s, x, y + 44, 38, C.text, { a: c, w: 800, align: 'center' }); T(g, s2, x, y + 100, 28, C.dim, { a: c, w: 500, align: 'center' }); }); }
}

// ---------- story ----------
function storyDraw(g, st, t) {
  cover(g, A('key_art'), 1.1, 0.5, 0.5); dim(g, 0.8);
  const ch = ['归来', '新港计划', '听证会', '台风夜', '老街的明天']; const a0 = ramp(t, 0.3, 0.8);
  ch.forEach((s, i) => { const x = 170 + i * 395, y = 170; const b = ramp(t, 0.4 + i * 0.5, 0.8 + i * 0.5); panel(g, x - 150, y - 50, 300, 100, b, { fill: i === 1 ? 'rgba(242,169,59,0.95)' : 'rgba(255,245,230,0.1)' }); T(g, i < 4 ? `第${'一二三四'[i]}章` : '终章', x, y - 22, 24, i === 1 ? C.ink : C.dim, { a: b, w: 600, align: 'center' }); T(g, s, x, y + 16, 34, i === 1 ? C.ink : C.text, { a: b, w: 800, align: 'center' }); if (i < 4) arrow(g, x + 156, y, x + 238, y, C.amber, b, 3); });
  // 各方
  const F = [['wang', '街坊会', '守住老街'], ['zhong', '老商户', '留下手艺'], ['xm', '记者 · 小满', '查清真相'], ['chen', '海晟集团 · 陈总', '新港计划']];
  F.forEach(([n, s, s2], i) => { const t0 = cue(st, 1, 2.5 + i * 1.6); const b = ramp(t, t0, t0 + 0.4); const x = 110 + i * 440, y = 320; panel(g, x, y, 400, 200, b, { accent: i === 3 ? C.red : C.green }); portrait(g, n, x + 30, y + 30, 140, b); T(g, s, x + 196, y + 46, 32, C.text, { a: b, w: 800 }); T(g, s2, x + 196, y + 100, 28, C.dim, { a: b, w: 500 }); });
  // 世界变量
  const c2 = cue(st, 2); const V = [['街坊信任', 0.72, C.green, 'users'], ['城市名声', 0.55, C.amber, 'star'], ['海晟关系', 0.22, C.red, 'building-2'], ['手里的证据', 0.43, C.teal, 'search']];
  V.forEach(([s, val, col, ic], i) => { const t0 = c2 + 3 + i * 1.6; const b = ramp(t, t0, t0 + 0.4); const x = 110 + (i % 2) * 880, y = 580 + Math.floor(i / 2) * 90; icon(g, ic, x + 20, y + 24, 34, col, b); T(g, s, x + 56, y + 6, 32, C.text, { a: b, w: 700 }); bar(g, x + 260, y + 14, 520, 22, val * ramp(t, t0, t0 + 1.2), col, b); });
  // 例子
  const c3 = cue(st, 3); const E = [['扶过周伯', '听证会上，周海站出来作证', C.green], ['没管夜市失火', '第四章：夜市被整顿关停', C.red]];
  E.forEach(([l, r, col], i) => { const b = ramp(t, c3 + 1 + i * 3.2, c3 + 1.4 + i * 3.2); const y = 790 + i * 0; const x = i ? 990 : 110; panel(g, x, y, 820, 90, b, { accent: col }); T(g, l, x + 30, y + 45, 32, C.text, { a: b, w: 800, base: 'middle' }); arrow(g, x + 250, y + 45, x + 320, y + 45, col, b, 4); T(g, r, x + 336, y + 45, 30, C.text, { a: b, w: 600, base: 'middle' }); });
}

// ---------- versions ----------
const VER = [['v1.0', '老城区 + 码头', [0, 1]], ['v1.5', '夜市 + 商务区', [2, 3]], ['v2.0', '离岛', [5]], ['v3.0', '半山', [4]]];
function versionsDraw(g, st, t) {
  cover(g, A('map'), 1.02, 0.5, 0.5); dim(g, 0.1); const D = st.plan.districts || DIST;
  const c2 = cue(st, 2); const openAt = [0, c2 + 1.5, c2 + 5.2, c2 + 8.4]; let lv = 0; openAt.forEach((x, i) => { if (t >= x) lv = i; });
  for (let k = 0; k < D.length; k++) { const vi = VER.findIndex((v) => v[2].includes(k)); const op = vi < 0 ? 0 : clamp((t - openAt[vi]) / 1.2); const fa = vi === 0 ? 0 : 1 - op; if (fa <= 0.01) continue; const d = D[k]; g.save(); g.globalAlpha = fa * 0.88; const gr = g.createRadialGradient(d.x * W, d.y * H, 10, d.x * W, d.y * H, d.r * W * 1.1); gr.addColorStop(0, 'rgba(236,232,224,1)'); gr.addColorStop(0.7, 'rgba(230,226,218,0.92)'); gr.addColorStop(1, 'rgba(230,226,218,0)'); g.fillStyle = gr; g.fillRect(0, 0, W, H); g.restore(); }
  D.forEach((d, k) => { const vi = VER.findIndex((v) => v[2].includes(k)); const op = vi <= 0 ? 1 : clamp((t - openAt[vi]) / 0.8); const x = d.x * W, y = d.y * H; const w = TW(g, d.name, 32, { px: true }) + 40; pxBox(g, x - w / 2, y - 26, w, 52, 0.4 + 0.6 * op, { fill: op >= 1 ? '#fff8ea' : '#ddd5c6' }); T(g, d.name, x, y + 1, 32, C.ink, { px: true, align: 'center', base: 'middle', a: 0.5 + 0.5 * op }); });
  // 时间轴
  const y = H - 250; g.fillStyle = 'rgba(20,16,12,0.82)'; g.fillRect(0, y - 50, W, 110); VER.forEach(([v, s], i) => { const x = 220 + i * 470; const on = lv >= i; g.save(); g.fillStyle = on ? C.amber : '#6b6055'; g.beginPath(); g.arc(x, y, 14, 0, 7); g.fill(); g.restore(); if (i < 3) { g.fillStyle = lv > i ? C.amber : '#6b6055'; g.fillRect(x + 20, y - 2, 430, 4); } T(g, v, x + 28, y - 36, 30, on ? C.amber : C.dim, { num: true }); T(g, s, x + 28, y + 2, 28, on ? C.text : C.dim, { w: 700 }); });
  // v1.0 内容卡
  const c1 = cue(st, 1); const a = fadeWin(t, c1, c2, 0.4); if (a > 0) { panel(g, 70, 140, 560, 380, a, { accent: C.amber }); T(g, 'v1.0 首发内容', 110, 166, 34, C.amber, { a, w: 800 }); [['door-open', '40 栋能进的建筑'], ['users', '120 位有完整故事的居民'], ['book-open', '主线第一章'], ['briefcase', '10 种以上的工作']].forEach(([ic, s], i) => item(g, 90, 230 + i * 68, ic, s, ramp(t, c1 + 0.5 + i * 1.2, c1 + 0.9 + i * 1.2) * a, { size: 34 })); }
  const c3 = cue(st, 3); const a3 = fadeWin(t, c3, cue(st, 4), 0.4); if (a3 > 0) { panel(g, 70, 140, 640, 400, a3, { accent: C.green }); T(g, '老存档继承 · 居民继续生活', 110, 166, 34, C.green, { a: a3, w: 800 }); [['heart', '小满和阿杰结婚了'], ['store', '王阿姨的店终于开张'], ['truck', '周伯搬去和儿子住'], ['briefcase', '阿珍的女儿去了商务区']].forEach(([ic, s], i) => item(g, 90, 230 + i * 70, ic, s, ramp(t, c3 + 0.8 + i * 1.6, c3 + 1.2 + i * 1.6) * a3, { size: 34, ic: C.green })); }
  const c4 = cue(st, 4); const a4 = ramp(t, c4, c4 + 0.4); if (a4 > 0) { panel(g, 70, 140, 1100, 200, a4, { accent: C.red }); T(g, '节日与季节活动', 110, 166, 34, C.red, { a: a4, w: 800 }); [['party-popper', '春节'], ['moon', '中秋'], ['cloud-lightning', '台风季'], ['soup', '夜市节']].forEach(([ic, s], i) => { const b = ramp(t, c4 + 0.6 + i * 0.9, c4 + 1.0 + i * 0.9) * a4; icon(g, ic, 140 + i * 250, 270, 50, C.amber, b); T(g, s, 180 + i * 250, 252, 38, C.text, { a: b, w: 800 }); }); }
}

// ---------- tech ----------
function techDraw(g, st, t) {
  g.fillStyle = '#17120e'; g.fillRect(0, 0, W, H);
  const cols = [['AI 整块画街区 → 真像素', 0.3], ['测量根运动 → 脚步不打滑', 3.6], ['数据驱动的居民', cue(st, 1)]];
  cols.forEach(([s, t0], i) => { const b = ramp(t, t0, t0 + 0.4); const x = 70 + i * 610; panel(g, x, 130, 580, 600, b); T(g, s, x + 30, 156, 34, C.amber, { a: b, w: 800 }); });
  // 1：街区图
  const bk = img('/yh/blocks/food.png'); const b1 = ramp(t, 0.5, 1); if (bk.width && b1 > 0) { g.save(); g.globalAlpha = b1; g.imageSmoothingEnabled = false; const s = Math.min(520 / bk.width, 470 / bk.height); g.drawImage(bk, 100, 230, bk.width * s, bk.height * s); g.restore(); }
  // 2：行走动画
  const b2 = ramp(t, 3.8, 4.3); if (b2 > 0) { const sh = img('/yh/npc_office_lin.png'); const fr = Math.floor(t * 12.5) % 8; g.save(); g.globalAlpha = b2; g.imageSmoothingEnabled = false; g.drawImage(sh, fr * 32, 2 * 40, 32, 40, 760, 250, 32 * 9, 40 * 9); g.restore(); g.save(); g.globalAlpha = b2; g.fillStyle = 'rgba(242,169,59,0.9)'; g.fillRect(740, 610, 330, 4); g.restore(); T(g, '每换一帧，按脚的实际位移前进', 990, 650, 26, C.dim, { a: b2, w: 500, align: 'center' }); }
  // 3：居民数据卡
  const c1 = cue(st, 1); const b3 = ramp(t, c1 + 0.3, c1 + 0.7); if (b3 > 0) { const x = 1340, y = 230; const L = ['id: wang_xiuying', 'age: 52   job: 早餐摊主', 'home: 老城区 骑楼街 12 号', 'schedule: 05:30 备料 → 06:00 出摊 …', 'needs: 饥饿 疲劳 心情 钱包', 'traits: 热心 嘴快 爱面子', 'secret: 想开自己的店', 'quests: 王阿姨的店 (v1.2)'];
    L.forEach((s, i) => T(g, s, x, y + i * 56, 26, i === 0 ? C.amber : '#e8dcc8', { a: ramp(t, c1 + 0.5 + i * 0.4, c1 + 0.8 + i * 0.4) * b3, px: true })); }
  // 切片清单
  const c2 = cue(st, 2); const a = ramp(t, c2, c2 + 0.4); if (a > 0) { g.save(); g.globalAlpha = a * 0.9; g.fillStyle = '#17120e'; g.fillRect(0, 0, W, H); g.restore(); T(g, '第一步：可玩切片', 150, 150, 56, C.amber, { a, w: 900 });
    [['map-pin', '一条街'], ['door-open', '10 栋能进的房子'], ['users', '30 个有日程的居民'], ['zap', '5 种随机事件'], ['book-open', '主线第一章']].forEach(([ic, s], i) => { const b = ramp(t, c2 + 0.8 + i * 1.3, c2 + 1.2 + i * 1.3) * a; panel(g, 150, 260 + i * 120, 900, 96, b, { fill: 'rgba(255,245,230,0.08)' }); icon(g, 'circle-check', 205, 308 + i * 120, 44, C.green, b); icon(g, ic, 285, 308 + i * 120, 40, C.amber, b); T(g, s, 330, 308 + i * 120, 42, C.text, { a: b, w: 800, base: 'middle' }); }); }
}

// 纯 2D：跳过 three 渲染
for (const k of Object.keys(scenes)) { const sc = scenes[k]; const su = sc.setup, ov = sc.overlay; sc.setup = async (st) => { st.render = () => {}; if (su) await su(st); }; sc.overlay = (g, st, t) => { g.fillStyle = '#000'; g.fillRect(0, 0, W, H); ov(g, st, t); }; }
