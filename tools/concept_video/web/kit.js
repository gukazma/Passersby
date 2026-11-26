// 共享工具：数学、随机、3D 小人、相机轨道、2D 覆盖层（标签/气泡/卡片/字幕）
import * as THREE from 'three';
export { THREE };
export const W = 1920, H = 1080;

// ---------- 数学 ----------
export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const ease = (t) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
export const ramp = (t, a, b) => clamp((t - a) / (b - a)); // t 在 [a,b] 内 0→1
export const win = (t, a, b, f = 0.3) => Math.min(smooth((t - a) / f), smooth((b - t) / f)); // 区间淡入淡出
export function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
export const v3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
export const angLerp = (a, b, t) => { let d = ((b - a + Math.PI * 3) % (Math.PI * 2)) - Math.PI; return a + d * t; };

// ---------- 调色（暖色系，不用蓝紫） ----------
export const PAL = {
  bg: '#1c1916', card: 'rgba(28,24,20,0.86)', text: '#f6efe4', dim: '#c9bba6', amber: '#f2a93b', red: '#e5484d', green: '#5bb974',
  players: ['#e5484d', '#f2a93b', '#f5d547', '#5bb974', '#2fb3a0', '#e95f9b', '#c98a5a', '#eae2d6'],
};

// ---------- 3D 基础 ----------
export function basicWorld(S, { sky = '#2a2420', fog = [25, 80], hemi = 1.1, sun = 1.8, shadow = true, sunPos = [12, 22, 8], shadowSize = 26 } = {}) {
  S.background = new THREE.Color(sky);
  if (fog) S.fog = new THREE.Fog(sky, fog[0], fog[1]);
  const h = new THREE.HemisphereLight('#fff4e2', '#3b2c22', hemi); S.add(h);
  const d = new THREE.DirectionalLight('#ffe2b8', sun); d.position.set(...sunPos);
  if (shadow) { d.castShadow = true; d.shadow.mapSize.set(1024, 1024); Object.assign(d.shadow.camera, { left: -shadowSize, right: shadowSize, top: shadowSize, bottom: -shadowSize, far: 80 }); d.shadow.bias = -0.0015; }
  S.add(d); S.add(d.target);
  return { hemi: h, sun: d };
}
export const mat = (color, o = {}) => new THREE.MeshLambertMaterial({ color, ...o });
export function box(w, h, d, color, o = {}) { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, o)); m.castShadow = true; m.receiveShadow = true; return m; }

// 低多边形小人：身体胶囊 + 头 + 面罩（指示朝向）+ 背包；yaw=0 面向 +Z
export function makePawn(color, { scale = 1, visor = '#2b2522', pack = true, hat = null } = {}) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.32, 0.55, 3, 8), mat(color, { flatShading: true })); body.position.y = 0.62; body.castShadow = true; g.add(body);
  const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.27, 0), mat(color, { flatShading: true })); head.position.y = 1.25; head.castShadow = true; g.add(head);
  const vis = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.12, 0.12), mat(visor)); vis.position.set(0, 1.28, 0.22); g.add(vis);
  if (pack) { const p = box(0.36, 0.42, 0.18, '#5a4636'); p.position.set(0, 0.75, -0.33); g.add(p); }
  if (hat) { const ht = new THREE.Mesh(new THREE.ConeGeometry(0.22, 0.35, 6), mat(hat, { flatShading: true })); ht.position.y = 1.62; ht.castShadow = true; g.add(ht); }
  const legs = [-0.13, 0.13].map((x) => { const l = box(0.14, 0.32, 0.16, '#3a302a'); l.position.set(x, 0.16, 0); g.add(l); return l; });
  g.scale.setScalar(scale);
  const P = { g, body, head, vis, legs, yaw: 0, color, alpha: 1 };
  P.walk = (phase, amt = 1) => { const s = Math.sin(phase) * 0.35 * amt; legs[0].rotation.x = s; legs[1].rotation.x = -s; body.position.y = 0.62 + Math.abs(Math.cos(phase)) * 0.05 * amt; };
  P.face = (yaw) => { P.yaw = yaw; g.rotation.y = yaw; };
  P.setOpacity = (a) => { P.alpha = a; g.traverse((o) => { if (o.material) { o.material.transparent = a < 1; o.material.opacity = a; o.material.depthWrite = a > 0.5; } }); g.visible = a > 0.01; };
  return P;
}
// 朝向向量（yaw→XZ）
export const dirOf = (yaw) => v3(Math.sin(yaw), 0, Math.cos(yaw));
export const yawTo = (from, to) => Math.atan2(to.x - from.x, to.z - from.z);

// 视锥扇形（地面上的半透明扇形）
export function makeCone(color, range = 7, half = 0.5, opacity = 0.22) {
  const sh = new THREE.Shape(); sh.moveTo(0, 0); const N = 18;
  for (let i = 0; i <= N; i++) { const a = -half + (2 * half * i) / N; sh.lineTo(Math.sin(a) * range, Math.cos(a) * range); }
  sh.lineTo(0, 0);
  const geo = new THREE.ShapeGeometry(sh); geo.rotateX(Math.PI / 2); // 形状 XY → XZ（+Y 前方 → +Z）
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide }));
  m.position.y = 0.06; m.renderOrder = 2; return m;
}

// ---------- 相机：关键帧 ----------
// keys: [{t, pos:[x,y,z], look:[x,y,z], fov}]；t 为场景内秒
export function camKeys(cam, keys, t) {
  let a = keys[0], b = keys[keys.length - 1];
  for (let i = 0; i < keys.length - 1; i++) if (t >= keys[i].t && t <= keys[i + 1].t) { a = keys[i]; b = keys[i + 1]; break; }
  if (t < keys[0].t) b = a; if (t > keys[keys.length - 1].t) a = b;
  const u = a === b ? 0 : ease((t - a.t) / (b.t - a.t));
  const p = a.pos.map((x, i) => lerp(x, b.pos[i], u)), l = a.look.map((x, i) => lerp(x, b.look[i], u));
  cam.position.set(...p); cam.lookAt(...l);
  const f = lerp(a.fov || 45, b.fov || 45, u); if (cam.fov !== f) { cam.fov = f; cam.updateProjectionMatrix(); }
}
export function orbit(cam, center, radius, height, ang, fov = 45) {
  cam.position.set(center[0] + radius * Math.sin(ang), center[1] + height, center[2] + radius * Math.cos(ang)); cam.lookAt(...center);
  if (cam.fov !== fov) { cam.fov = fov; cam.updateProjectionMatrix(); }
}

// ---------- 2D 覆盖层 ----------
export const FONT = '"Noto Sans CJK SC", sans-serif';
export function font(g, size, weight = 'bold') { g.font = `${weight} ${size}px ${FONT}`; }
export function project(cam, p) { const v = (p.isVector3 ? p.clone() : v3(...p)).project(cam); return { x: (v.x + 1) / 2 * W, y: (1 - v.y) / 2 * H, ok: v.z < 1 && v.z > -1 }; }
export function rrect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
// 头顶名牌
export function tag(g, cam, pos, text, color = PAL.text, a = 1, size = 24, bg = 'rgba(20,17,14,0.72)') {
  if (a <= 0.01) return; const s = project(cam, pos); if (!s.ok) return;
  g.save(); g.globalAlpha = a; font(g, size); const w = g.measureText(text).width + 22;
  rrect(g, s.x - w / 2, s.y - size - 14, w, size + 14, 8); g.fillStyle = bg; g.fill();
  g.fillStyle = color; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, s.x, s.y - size / 2 - 7); g.restore();
}
// 气泡标注：指向世界坐标，偏移 (dx,dy)
export function callout(g, cam, pos, text, a = 1, { dx = 120, dy = -110, color = PAL.amber, size = 32, sub = null } = {}) {
  if (a <= 0.01) return; const s = project(cam, pos); if (!s.ok) return;
  g.save(); g.globalAlpha = a; font(g, size); const lines = text.split('\n');
  const tw = Math.max(...lines.map((l) => g.measureText(l).width)); let sw = 0;
  if (sub) { font(g, size * 0.62, 'normal'); sw = g.measureText(sub).width; }
  const w = Math.max(tw, sw) + 40, h = lines.length * size * 1.3 + (sub ? size * 0.9 : 0) + 22;
  const bx = s.x + dx - (dx < 0 ? w : 0), by = s.y + dy - h / 2;
  g.strokeStyle = color; g.lineWidth = 3; g.beginPath(); g.moveTo(s.x, s.y); g.lineTo(dx < 0 ? bx + w : bx, by + h / 2); g.stroke();
  g.fillStyle = color; g.beginPath(); g.arc(s.x, s.y, 7, 0, 7); g.fill();
  rrect(g, bx, by, w, h, 12); g.fillStyle = PAL.card; g.fill(); g.lineWidth = 2.5; g.stroke();
  font(g, size); g.fillStyle = color; g.textAlign = 'left'; g.textBaseline = 'top';
  lines.forEach((l, i) => g.fillText(l, bx + 20, by + 12 + i * size * 1.3));
  if (sub) { font(g, size * 0.62, 'normal'); g.fillStyle = PAL.dim; g.fillText(sub, bx + 20, by + 14 + lines.length * size * 1.3); }
  g.restore();
}
// 信息卡：title + 若干行（支持 [颜色]前缀 用于高亮）
export function card(g, x, y, w, title, lines, a = 1, { size = 30, titleColor = PAL.amber, lh = 1.55, pad = 34 } = {}) {
  if (a <= 0.01) return; g.save(); g.globalAlpha = a;
  const h = pad * 2 + (title ? size * 1.5 + 14 : 0) + lines.length * size * lh;
  rrect(g, x, y, w, h, 18); g.fillStyle = PAL.card; g.fill(); g.strokeStyle = 'rgba(242,169,59,0.55)'; g.lineWidth = 2; g.stroke();
  let cy = y + pad; g.textBaseline = 'top'; g.textAlign = 'left';
  if (title) { font(g, size * 1.3); g.fillStyle = titleColor; g.fillText(title, x + pad, cy); cy += size * 1.5 + 14; }
  for (const L of lines) { let t = L, c = PAL.text; const m = /^\[(#[0-9a-fA-F]{6}|\w+)\](.*)$/.exec(L); if (m) { c = PAL[m[1]] || m[1]; t = m[2]; } font(g, size, 'normal'); g.fillStyle = c; g.fillText(t, x + pad, cy); cy += size * lh; }
  g.restore(); return h;
}
// 大标题（居中）
export function bigTitle(g, text, sub, a = 1, y = H / 2) {
  if (a <= 0.01) return; g.save(); g.globalAlpha = a; g.textAlign = 'center'; g.textBaseline = 'middle';
  font(g, 120); g.lineWidth = 10; g.strokeStyle = 'rgba(15,12,10,0.85)'; g.strokeText(text, W / 2, y); g.fillStyle = PAL.text; g.fillText(text, W / 2, y);
  if (sub) { font(g, 44, 'normal'); g.lineWidth = 6; g.strokeText(sub, W / 2, y + 105); g.fillStyle = PAL.amber; g.fillText(sub, W / 2, y + 105); }
  g.restore();
}
export function vignette(g, a = 0.5) { const r = g.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95); r.addColorStop(0, 'rgba(0,0,0,0)'); r.addColorStop(1, `rgba(0,0,0,${a})`); g.fillStyle = r; g.fillRect(0, 0, W, H); }
// 横向流程条：phases=[{name, sub, w(权重), color}]，hi=高亮索引（可小数表示进度）
export function flowBar(g, x, y, w, phases, prog = -1, a = 1, h = 96) {
  if (a <= 0.01) return; g.save(); g.globalAlpha = a; const tot = phases.reduce((s, p) => s + (p.w || 1), 0); let cx = x;
  phases.forEach((p, i) => {
    const pw = w * (p.w || 1) / tot - 8; const done = prog >= i + 1, curr = prog >= i && prog < i + 1, on = done || curr;
    rrect(g, cx, y, pw, h, 12); g.fillStyle = on ? (p.color || PAL.amber) : 'rgba(60,52,45,0.85)'; g.fill();
    if (curr) { g.save(); rrect(g, cx, y, pw, h, 12); g.clip(); g.fillStyle = 'rgba(255,255,255,0.28)'; g.fillRect(cx, y, pw * (prog - i), h); g.restore(); g.save(); rrect(g, cx - 3, y - 3, pw + 6, h + 6, 14); g.strokeStyle = '#fff8ec'; g.lineWidth = 4; g.stroke(); g.restore(); }
    g.textAlign = 'center'; g.textBaseline = 'middle'; font(g, 32); g.fillStyle = on ? '#1c1916' : PAL.text; g.fillText(p.name, cx + pw / 2, y + h / 2 - (p.sub ? 15 : 0));
    if (p.sub) { font(g, 22, 'normal'); g.fillText(p.sub, cx + pw / 2, y + h / 2 + 22); }
    cx += pw + 8;
  }); g.restore();
}
export function chip(g, x, y, text, color = PAL.amber, size = 28, a = 1) {
  g.save(); g.globalAlpha = a; font(g, size); const w = g.measureText(text).width + 36; rrect(g, x, y, w, size + 22, (size + 22) / 2); g.fillStyle = color; g.fill();
  g.fillStyle = '#1c1916'; g.textBaseline = 'middle'; g.textAlign = 'left'; g.fillText(text, x + 18, y + (size + 22) / 2 + 1); g.restore(); return w;
}
// 仪表条
export function meter(g, x, y, w, h, v, label, color = PAL.amber, a = 1) {
  g.save(); g.globalAlpha = a; rrect(g, x, y, w, h, h / 2); g.fillStyle = 'rgba(40,34,29,0.9)'; g.fill();
  rrect(g, x, y, Math.max(h, w * clamp(v)), h, h / 2); g.fillStyle = color; g.fill();
  if (label) { font(g, 26); g.fillStyle = PAL.text; g.textBaseline = 'bottom'; g.textAlign = 'left'; g.fillText(label, x, y - 6); }
  g.restore();
}
