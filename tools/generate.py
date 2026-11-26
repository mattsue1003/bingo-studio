#!/usr/bin/env python3
"""
童趣賓果工作室：用 OpenAI 圖片模型生成內建圖卡（326 張）。

用法（在這個資料夾裡執行）：
  export OPENAI_API_KEY=你的金鑰          # 金鑰只在你的電腦上使用
  python3 generate.py --limit 3            # 先試做 3 張，看看風格
  python3 generate.py                      # 生成全部（已存在的會自動跳過，可隨時中斷再續跑）

常用選項：
  --quality low|medium|high   畫質，預設 medium（low 最便宜）
  --only animals,fruits       只做某些主題
  --redo animals-03           重做指定的圖（可用逗號分隔多張）
  --model gpt-image-1         使用的模型
  --workers 3                 同時生成幾張

輸出：img/<主題-序號>.webp（512×512）與 img/manifest.json。
只需要 Python 3；有安裝 Pillow 會自動縮成 512px 的 WebP，沒有就保留原尺寸。
"""
import argparse, base64, io, json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "img")

STYLE = (
    "Children's picture-book illustration for a bingo flashcard set used by preschool teachers in Taiwan. "
    "Exactly one subject, centered, filling about 75% of the frame. "
    "Soft rounded shapes, warm friendly colors, gentle gouache-like shading, clean dark-brown outline, "
    "consistent art style across the whole set. Plain pure white background, no shadow on the ground, "
    "no border, no frame. Absolutely no text, letters, numbers or symbols anywhere in the image."
)

def prompt_for(item):
    return f"{STYLE}\nSubject: {item['subject']}"

def call_api(key, model, quality, prompt):
    body = {"model": model, "prompt": prompt, "size": "1024x1024", "quality": quality, "n": 1,
            "background": "opaque", "output_format": "webp", "output_compression": 85}
    req = urllib.request.Request("https://api.openai.com/v1/images/generations",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())
    return base64.b64decode(data["data"][0]["b64_json"])

def shrink(raw):
    try:
        from PIL import Image
    except ImportError:
        return raw
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((512, 512))
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=82, method=6)
    return buf.getvalue()

def make(item, key, args):
    path = os.path.join(OUT, item["key"] + ".webp")
    for attempt in range(5):
        try:
            raw = call_api(key, args.model, args.quality, prompt_for(item))
            with open(path, "wb") as f:
                f.write(shrink(raw))
            return item["key"], None
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(60, 5 * 2 ** attempt))
                continue
            return item["key"], f"HTTP {e.code}: {msg}"
        except Exception as e:  # network hiccup
            time.sleep(5 * (attempt + 1))
            err = str(e)
    return item["key"], f"重試 5 次仍失敗：{err if 'err' in locals() else ''}"

def write_manifest():
    keys = sorted(f[:-5] for f in os.listdir(OUT) if f.endswith(".webp"))
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"items": keys}, f, ensure_ascii=False)
    return len(keys)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-image-1")
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--only", default="")
    ap.add_argument("--redo", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("找不到 OPENAI_API_KEY。請先執行：export OPENAI_API_KEY=你的金鑰")

    os.makedirs(OUT, exist_ok=True)
    items = json.load(open(os.path.join(HERE, "prompts.json"), encoding="utf-8"))
    redo = {k.strip() for k in args.redo.split(",") if k.strip()}
    if redo:
        items = [i for i in items if i["key"] in redo]
    else:
        if args.only:
            themes = {t.strip() for t in args.only.split(",")}
            items = [i for i in items if i["key"].rsplit("-", 1)[0] in themes]
        items = [i for i in items if not os.path.exists(os.path.join(OUT, i["key"] + ".webp"))]
    if args.limit:
        items = items[: args.limit]

    print(f"要生成 {len(items)} 張（畫質 {args.quality}，模型 {args.model}）")
    fails = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(make, it, key, args) for it in items]
        for n, f in enumerate(as_completed(futs), 1):
            k, err = f.result()
            print(f"[{n}/{len(items)}] {k} {'✓' if not err else '✗ ' + err}", flush=True)
            if err:
                fails.append(k)
    total = write_manifest()
    print(f"\n完成。img 資料夾裡共有 {total} 張圖。")
    if fails:
        print("失敗的圖（可用 --redo 重做）：" + ",".join(fails))

if __name__ == "__main__":
    main()
