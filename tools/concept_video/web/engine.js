// 视频引擎：按 plan.json 的时间线逐帧推进场景、渲染 3D、叠加字幕与 HUD
import { THREE, W, H, PAL, font, rrect, clamp, smooth } from './kit.js';
const qs = new URLSearchParams(location.search);
const id = qs.get('id'); const scale = +(qs.get('scale') || 1);
const plan = await (await fetch(`/out/${id}/plan.json?${Date.now()}`)).json();
const mod = await import(`./${id}.js?${Date.now()}`);
const RW = Math.round(W * scale), RH = Math.round(H * scale);
const renderer = new THREE.WebGLRenderer({ antialias: !!plan.aa, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(RW, RH); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
document.body.appendChild(renderer.domElement);
const comp = document.createElement('canvas'); comp.width = RW; comp.height = RH; const g = comp.getContext('2d');
let cur = null, curIdx = -1, st = null;
const FPS = plan.fps, DT = 1 / FPS;

function disposeScene(S) { S.traverse((o) => { o.geometry?.dispose?.(); const m = o.material; if (m) (Array.isArray(m) ? m : [m]).forEach((x) => { x.map?.dispose?.(); x.dispose(); }); }); }
async function enter(k) {
  if (st) { st.dispose?.(); disposeScene(st.S); }
  const sc = plan.scenes[k]; const def = mod.scenes[sc.scene];
  if (!def) throw new Error('no scene ' + sc.scene);
  const S = new THREE.Scene(); const cam = new THREE.PerspectiveCamera(45, W / H, 0.1, 400);
  st = { ...sc, S, cam, renderer, simT: 0, cues: sc.lines.map((l) => l.start - sc.start), cueEnd: sc.lines.map((l) => l.start - sc.start + l.dur), plan, scale, RW, RH };
  cur = def; await def.setup?.(st); curIdx = k;
}
function chunks(text) {
  const parts = text.match(/[^，。！？；：、,!?;]+[，。！？；：、,!?;]*/g) || [text]; const out = [];
  for (const p of parts) { if (out.length && (out[out.length - 1] + p).replace(/[，。；：、,;]$/, '').length <= 24 && !/[。！？!?]$/.test(out[out.length - 1])) out[out.length - 1] += p; else out.push(p); }
  return out;
}
function subtitle(t) {
  let L = null; for (const sc of plan.scenes) for (const l of sc.lines) if (t >= l.start && t < l.start + l.dur + 0.25) L = l;
  if (!L) return; const cs = chunks(L.text); const tot = cs.reduce((s, c) => s + c.length, 0); let acc = 0, txt = cs[cs.length - 1];
  for (const c of cs) { const a = L.start + (acc / tot) * L.dur; acc += c.length; if (t < L.start + (acc / tot) * L.dur) { txt = c; break; } }
  txt = txt.replace(/[，。；、,;]$/, '');
  if (plan.sub === 'game') { g.save(); const gr = g.createLinearGradient(0, H - 200, 0, H); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,0.55)'); g.fillStyle = gr; g.fillRect(0, H - 200, W, 200);
    g.font = '600 44px "Noto Sans CJK SC", sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.letterSpacing = '1px'; g.shadowColor = 'rgba(0,0,0,0.9)'; g.shadowBlur = 10; g.shadowOffsetY = 2; g.lineWidth = 5; g.strokeStyle = 'rgba(0,0,0,0.55)'; g.lineJoin = 'round'; g.strokeText(txt, W / 2, H - 92); g.fillStyle = '#fbf6ec'; g.fillText(txt, W / 2, H - 92); g.restore(); return; }
  g.save(); font(g, 46); g.textAlign = 'center'; g.textBaseline = 'middle'; const w = g.measureText(txt).width + 60;
  rrect(g, W / 2 - w / 2, H - 128, w, 76, 14); g.fillStyle = 'rgba(14,12,10,0.62)'; g.fill();
  g.fillStyle = '#fff8ec'; g.fillText(txt, W / 2, H - 89); g.restore();
}
window.frame = async (i) => {
  const t = i / FPS; let k = plan.scenes.findIndex((s) => t >= s.start && t < s.start + s.dur); if (k < 0) k = plan.scenes.length - 1;
  if (k !== curIdx) await enter(k);
  const lt = t - st.start;
  while (st.simT <= lt + 1e-6) { cur.update?.(st, st.simT, DT); st.simT += DT; }
  if (cur.prepare) await cur.prepare(st, lt);
  if (st.render) st.render(renderer); else renderer.render(st.S, st.cam);
  g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(renderer.domElement, 0, 0); g.setTransform(scale, 0, 0, scale, 0, 0);
  g.save(); cur.overlay?.(g, st, lt); g.restore(); g.textAlign = 'left'; g.textBaseline = 'alphabetic';
  if (st.chrome !== false) {
    g.save(); font(g, 26); const tt = `${plan.title}`; const w1 = g.measureText(tt).width + 36; rrect(g, 36, 30, w1, 48, 24); g.fillStyle = PAL.amber; g.fill();
    g.fillStyle = '#1c1916'; g.textBaseline = 'middle'; g.fillText(tt, 54, 55);
    if (st.chapter) { font(g, 26, 'normal'); const w2 = g.measureText(st.chapter).width + 36; rrect(g, 46 + w1, 30, w2, 48, 24); g.fillStyle = 'rgba(20,17,14,0.75)'; g.fill(); g.fillStyle = PAL.text; g.fillText(st.chapter, 64 + w1, 55); }
    g.restore();
  }
  if (st.sub !== 'none') subtitle(t);
  const fin = st.fade === false ? 1 : Math.min(smooth(lt / 0.3), smooth((st.dur - lt) / 0.22));
  if (k === 0) { /* 首帧即封面，不淡入 */ } else if (fin < 1) { g.fillStyle = `rgba(0,0,0,${1 - fin})`; g.fillRect(0, 0, W, H); }
  if (k === plan.scenes.length - 1 && st.dur - lt < 0.6) { g.fillStyle = `rgba(0,0,0,${1 - (st.dur - lt) / 0.6})`; g.fillRect(0, 0, W, H); }
  return comp.toDataURL('image/jpeg', 0.92);
};
window.total = Math.round(plan.total * FPS);
window.ready = true;
