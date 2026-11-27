"""豆包语音 seed-audio-1.0 生成背景音乐。key 从 .env 的 VOLC_TTS_APIKEY_NEW 读，不打印。
    python seed_bgm.py <spec.json> <out_dir>"""
import base64, json, os, sys, uuid, requests
from dotenv import dotenv_values
key = dotenv_values(r'D:\OpenMontage\.env').get('VOLC_TTS_APIKEY_NEW') or ''
spec = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
for s in spec:
    for k in range(s.get("n", 1)):
        f = os.path.join(out, f"{s['id']}_{k + 1}.mp3")
        if os.path.exists(f): continue
        body = {"model": "seed-audio-1.0", "text_prompt": s["prompt"], "audio_config": {"format": "mp3", "sample_rate": 44100}}
        r = requests.post("https://openspeech.bytedance.com/api/v3/tts/create", json=body,
                          headers={"X-Api-Key": key, "X-Api-Request-Id": str(uuid.uuid4()), "Content-Type": "application/json"}, timeout=600)
        try:
            j = r.json()
        except Exception:
            print("FAIL", s["id"], r.status_code, r.text[:300]); continue
        if j.get("audio"):
            open(f, "wb").write(base64.b64decode(j["audio"]))
            print("OK", s["id"], k + 1, j.get("duration"), os.path.getsize(f))
        elif j.get("url"):
            open(f, "wb").write(requests.get(j["url"], timeout=300).content); print("OK(url)", s["id"], k + 1, j.get("duration"))
        else:
            print("FAIL", s["id"], r.status_code, {kk: vv for kk, vv in j.items() if kk != "audio"})
