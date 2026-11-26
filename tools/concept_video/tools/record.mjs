// 用法: node record.mjs <id> [--scale 0.5] [--from s] [--to s] [--out file.mp4] [--stills t1,t2,...] [--fps n]
import { chromium } from '/home/guleixin/tools/pw/node_modules/playwright-core/index.mjs';
import fs from 'fs'; import { spawn } from 'child_process';
const a = process.argv.slice(2); const id = a[0]; const opt = (k, d) => { const i = a.indexOf('--' + k); return i >= 0 ? a[i + 1] : d; };
const scale = +opt('scale', 1), from = +opt('from', 0), stills = opt('stills', null);
const env = { ...process.env, LD_LIBRARY_PATH: fs.readFileSync('/home/guleixin/tools/pw/ldpath.txt', 'utf8').trim(), FONTCONFIG_FILE: '/home/guleixin/tools/pw/fonts.conf' };
const browser = await chromium.launch({ env, args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await browser.newPage({ viewport: { width: Math.round(1920 * scale), height: Math.round(1080 * scale) } });
let err = null; p.on('pageerror', (e) => { err = e; console.error('PAGEERROR', e.message); }); p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('console', m.text()); });
await p.goto(`http://127.0.0.1:8765/web/index.html?id=${id}&scale=${scale}`);
await p.waitForFunction(() => window.ready || window.__err, null, { timeout: 60000 });
const plan = JSON.parse(fs.readFileSync(`/home/guleixin/gdemo/out/${id}/plan.json`)); const FPS = plan.fps;
const total = await p.evaluate(() => window.total); const to = +opt('to', total / FPS);
const grab = async (i) => Buffer.from((await p.evaluate((i) => window.frame(i), i)).split(',')[1], 'base64');
if (stills) {
  const dir = opt('outdir', `/home/guleixin/gdemo/out/${id}/stills`); fs.mkdirSync(dir, { recursive: true });
  const ts = stills.split(',').map(Number).sort((x, y) => x - y);
  // 为了保证模拟一致，从每个目标所在场景开头逐帧推进（引擎内部会补帧），这里直接按时间取
  for (const t of ts) { const b = await grab(Math.round(t * FPS)); fs.writeFileSync(`${dir}/${id}_${t.toFixed(1)}.jpg`, b); if (err) break; }
  console.log('stills ->', dir);
} else {
  const out = opt('out', `/home/guleixin/gdemo/out/${id}/video.mp4`);
  const ff = spawn('/home/guleixin/tools/vid/ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', 'pipe:0', '-vf', scale < 1 ? 'scale=1920:1080:flags=bicubic,format=yuv420p' : 'format=yuv420p', '-c:v', 'libx264', '-preset', opt('preset', 'veryfast'), '-crf', opt('crf', '19'), '-r', String(FPS), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const i0 = Math.round(from * FPS), i1 = Math.min(total, Math.round(to * FPS)); const t0 = Date.now();
  for (let i = i0; i < i1; i++) {
    const b = await grab(i); if (!ff.stdin.write(b)) await new Promise((r) => ff.stdin.once('drain', r));
    if (err) break;
    if ((i - i0) % 300 === 0) console.log(`frame ${i}/${i1}  ${((Date.now() - t0) / Math.max(1, i - i0)).toFixed(0)} ms/f`);
  }
  ff.stdin.end(); await new Promise((r) => ff.on('close', r)); console.log('video ->', out, ((Date.now() - t0) / 1000).toFixed(0), 's');
}
await browser.close(); process.exit(err ? 1 : 0);
