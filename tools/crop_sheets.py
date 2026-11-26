#!/usr/bin/env python3
"""把 ChatGPT 生成的 3×3 九宮格（sheets/sNN.png）切成單張圖卡 img/<key>.webp，並更新 img/manifest.json。"""
import json, os, sys
from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS = os.path.join(HERE, "sheets")
OUT = os.path.join(HERE, "img")

def grid_lines(im, axis):
    """找出九宮格分隔線位置（灰色細線）；找不到就用三等分。"""
    g = im.convert("L")
    w, h = g.size
    n = w if axis == 0 else h
    px = g.load()
    scores = []
    for i in range(n):
        dark = 0
        for j in range(0, (h if axis == 0 else w), 4):
            v = px[i, j] if axis == 0 else px[j, i]
            if v < 235:
                dark += 1
        scores.append(dark / ((h if axis == 0 else w) / 4))
    cuts = []
    for target in (n / 3, 2 * n / 3):
        lo, hi = int(target - n * 0.06), int(target + n * 0.06)
        best = max(range(lo, hi), key=lambda i: scores[i])
        cuts.append(best if scores[best] > 0.6 else int(target))
    return [0, cuts[0], cuts[1], n]

def tidy(cell):
    """去掉殘留的格線，補成白底正方形。"""
    w, h = cell.size
    m = max(6, int(min(w, h) * 0.02))
    cell = cell.crop((m, m, w - m, h - m))
    bg = Image.new("RGB", cell.size, (255, 255, 255))
    diff = ImageChops.difference(cell, bg).convert("L").point(lambda v: 255 if v > 18 else 0)
    box = diff.getbbox()
    side = max(cell.size)
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    if box:
        obj = cell.crop(box)
        pad = int(side * 0.08)
        obj.thumbnail((side - 2 * pad, side - 2 * pad))
        canvas.paste(obj, ((side - obj.width) // 2, (side - obj.height) // 2))
    canvas = canvas.resize((512, 512), Image.LANCZOS)
    return canvas, bool(box)

def main():
    os.makedirs(OUT, exist_ok=True)
    sheets = json.load(open(os.path.join(HERE, "sheets.json"), encoding="utf-8"))
    only = set(sys.argv[1:])
    for s in sheets:
        if only and s["sheet"] not in only:
            continue
        path = os.path.join(SHEETS, s["sheet"] + ".png")
        if not os.path.exists(path):
            continue
        im = Image.open(path).convert("RGB")
        xs, ys = grid_lines(im, 0), grid_lines(im, 1)
        for k, key in enumerate(s["keys"]):
            r, c = divmod(k, 3)
            cell = im.crop((xs[c], ys[r], xs[c + 1], ys[r + 1]))
            out, ok = tidy(cell)
            out.save(os.path.join(OUT, key + ".webp"), "WEBP", quality=82, method=6)
            if not ok:
                print("空白格？", key)
        print("切好", s["sheet"])
    keys = sorted(f[:-5] for f in os.listdir(OUT) if f.endswith(".webp"))
    json.dump({"items": keys}, open(os.path.join(OUT, "manifest.json"), "w"), ensure_ascii=False)
    print("img 共", len(keys), "張")

if __name__ == "__main__":
    main()
