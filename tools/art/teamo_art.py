"""出图（TeamoRouter 中转，gpt-image-2.6-sunburst），清单格式与 concept_art.py 相同：
    [{"id", "prompt", "refs": ["art:<id>" | 绝对路径], "size", "quality"(可选, 默认 high)}]

    python teamo_art.py <work> <spec.json> [输出子目录=art] [并发=4]
key 只从环境变量 TEAMO_API_KEY 读（用户自己在 114 上设置），不打印、不落盘。
输出 <work>/<子目录>/<id>.png，日志 <子目录>/art.log；失败会把接口返回的错误信息（不含 key）写进日志。
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

BASE = "https://api.teamorouter.ai/v1/images"
MODEL = "gpt-image-2.6-sunburst"


def key() -> str:
    k = os.environ.get("TEAMO_API_KEY", "")
    if not k:
        try:  # ssh 会话里用户级变量可能没带进来，直接读注册表里的用户环境变量
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                k = winreg.QueryValueEx(h, "TEAMO_API_KEY")[0]
        except Exception:  # noqa: BLE001
            pass
    if not k:
        sys.exit("TEAMO_API_KEY 未设置")
    return k


def call(out: pathlib.Path, prompt: str, refs: list[pathlib.Path], size: str, quality: str, extra: dict | None = None) -> str:
    """成功返回 ""，失败返回错误信息。"""
    auth = f"Authorization: Bearer {key()}"
    if refs:
        cmd = ["curl", "-s", "--max-time", "600", "-H", auth, "-F", f"model={MODEL}", "-F", f"size={size}", "-F", f"quality={quality}",
               "-F", "input_fidelity=high"]
        for r in refs:
            cmd += ["-F", f"image[]=@{r}"] if len(refs) > 1 else ["-F", f"image=@{r}"]
        for k, v in (extra or {}).items():
            cmd += ["-F", f"{k}={v}"]
        cmd += ["-F", f"prompt={prompt.replace(';', ',')}", f"{BASE}/edits"]
    else:
        body = json.dumps({"model": MODEL, "prompt": prompt, "size": size, "quality": quality, "n": 1, **(extra or {})})
        cmd = ["curl", "-s", "--max-time", "600", "-H", auth, "-H", "Content-Type: application/json", "-d", body, f"{BASE}/generations"]
    err = ""
    for _ in range(3):
        r = subprocess.run(cmd, capture_output=True)
        try:
            j = json.loads(r.stdout)
            if "data" in j:
                d0 = j["data"][0]
                if d0.get("b64_json"):
                    out.write_bytes(base64.b64decode(d0["b64_json"]))
                    return ""
                if d0.get("url"):   # 有时只回图片链接（已扣费）→ 下载
                    subprocess.run(["curl", "-s", "--max-time", "300", "-o", str(out), d0["url"]], check=True)
                    if out.exists() and out.stat().st_size > 1000:
                        return ""
                    err = "url 下载失败 " + d0["url"]
                    return err
            err = json.dumps(j.get("error", j), ensure_ascii=False)[:300]
            if "insufficient" in err or "balance" in err:
                return err
        except Exception:  # noqa: BLE001
            err = (r.stdout[:200] or r.stderr[:200]).decode("utf-8", "replace")
        time.sleep(5)
    return err


def main() -> int:
    work = pathlib.Path(sys.argv[1])
    items = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
    out = work / (sys.argv[3] if len(sys.argv) > 3 else "art")
    jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    out.mkdir(parents=True, exist_ok=True)
    log = out / "art.log"
    key()

    def ref(r: str) -> pathlib.Path:
        return out / f"{r[4:]}.png" if r.startswith("art:") else pathlib.Path(r)

    def run(it: dict) -> None:
        dst = out / f"{it['id']}.png"
        ext = it.get("extra", {}).get("output_format")
        if dst.exists() or (ext and (out / f"{it['id']}.{ext}").exists()):
            return
        refs = [ref(r) for r in it.get("refs", [])]
        miss = [str(p) for p in refs if not p.exists()]
        if miss:
            msg = f"SKIP {it['id']} 缺参考图 {miss}"
        else:
            t = time.time()
            extra = it.get("extra", {})
            if extra.get("output_format") in ("gif", "webp", "jpeg"):
                dst = out / f"{it['id']}.{extra['output_format']}"
            e = call(dst, it["prompt"], refs, it.get("size", "1536x1024"), it.get("quality", "high"), extra)
            msg = f"{'OK' if not e else 'FAIL'} {it['id']} {time.time() - t:.0f}s {e}"
        with log.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
        print(msg, flush=True)

    first = [it for it in items if not any(r.startswith("art:") and any(r[4:] == j["id"] for j in items) for r in it.get("refs", []))]
    second = [it for it in items if it not in first]
    for batch in (first, second):
        with ThreadPoolExecutor(jobs) as ex:
            list(ex.map(run, batch))
    done = sum(1 for it in items if any((out / f"{it['id']}.{e}").exists() for e in ("png", "gif", "webp", "jpeg")))
    print(f"ALLDONE {done}/{len(items)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
