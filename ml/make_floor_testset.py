"""合成「地板數字」測試集。

為什麼要自己合成：**公開資料集裡沒有這種東西。**
找過 Roboflow Universe、Kaggle、Chars74K、ICDAR、SVHN 與相關論文——
有的是建築平面圖、停車格佔用、街景門牌，沒有一個是「地板上的印刷數字、
從約 1 公尺高斜角俯視」。這不是搜尋不夠努力：用 floor camera 做定位的論文
（arXiv 2504.03249）自己就寫了他們在實驗室錄資料，理由是 lack of available datasets。

所以這支腳本產生的不是「更多訓練資料」，是**一組幾何對得上的測試集**，
用來量化 SVHN（遠距離街景門牌）與真實場域（近距離地板俯視）之間的 domain gap。

它產出的仍然是合成資料，不能取代真實照片——但它至少在**透視、視角、尺度**
這三件事上跟手機實際會看到的畫面一致，而 SVHN 在這三件事上全都不一致。

用法：
    python ml/make_floor_testset.py --n 300
    yolo val model=ml/weights/best.pt data=ml/data/floor_test/floor_test.yaml
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ML_DIR = Path(__file__).resolve().parent
OUT_DIR = ML_DIR / "data" / "floor_test"

FONTS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/tahomabd.ttf",
    "C:/Windows/Fonts/verdanab.ttf",
    "C:/Windows/Fonts/impact.ttf",
]

PLANE = 512          # 標記在「正上方俯視」平面裡的邊長
CANVAS_W, CANVAS_H = 1024, 768


def make_floor(rng: random.Random) -> np.ndarray:
    """產生地板底圖：磁磚、接縫、雜訊、光照漸層。"""
    base = rng.choice([
        (206, 202, 196), (188, 184, 178), (222, 218, 210),
        (168, 166, 162), (198, 190, 176), (150, 148, 146),
    ])
    img = np.full((CANVAS_H, CANVAS_W, 3), base, dtype=np.uint8)

    # 磁磚：每格給一點色差，接縫畫深色線
    tile = rng.randint(90, 190)
    grout = max(0, min(255, base[0] - rng.randint(25, 55)))
    off_x, off_y = rng.randint(0, tile), rng.randint(0, tile)
    for gy in range(-1, CANVAS_H // tile + 2):
        for gx in range(-1, CANVAS_W // tile + 2):
            x0, y0 = gx * tile + off_x, gy * tile + off_y
            shade = rng.randint(-8, 8)
            cv2.rectangle(
                img, (x0, y0), (x0 + tile, y0 + tile),
                tuple(int(max(0, min(255, c + shade))) for c in base), -1,
            )
    for gy in range(-1, CANVAS_H // tile + 2):
        y = gy * tile + off_y
        cv2.line(img, (0, y), (CANVAS_W, y), (grout,) * 3, rng.randint(2, 4))
    for gx in range(-1, CANVAS_W // tile + 2):
        x = gx * tile + off_x
        cv2.line(img, (x, 0), (x, CANVAS_H), (grout,) * 3, rng.randint(2, 4))

    # 光照：一個亮區加一個線性漸層，模擬天花板燈與窗光
    yy, xx = np.mgrid[0:CANVAS_H, 0:CANVAS_W].astype(np.float32)
    lx, ly = rng.uniform(0, CANVAS_W), rng.uniform(0, CANVAS_H)
    radial = 1.0 - 0.45 * np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) / (CANVAS_W * 0.9)
    linear = 1.0 + rng.uniform(-0.18, 0.18) * (yy / CANVAS_H)
    img = np.clip(img.astype(np.float32) * (radial * linear)[..., None], 0, 255)

    img += np.random.normal(0, rng.uniform(2, 7), img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def make_marker(digit: int, rng: random.Random) -> tuple[Image.Image, tuple[float, float, float, float]]:
    """在正上方俯視的平面裡畫一個地標，回傳 (RGBA 影像, 數字的緊密 bbox)。"""
    marker = Image.new("RGBA", (PLANE, PLANE), (0, 0, 0, 0))
    d = ImageDraw.Draw(marker)
    style = rng.choice(["plate", "plate", "painted"])

    if style == "plate":
        # 貼片式：底色方塊 + 外框，數字反白（像示意圖那種）
        plate = rng.choice([
            (176, 85, 31), (60, 60, 64), (200, 195, 185), (30, 90, 140), (190, 150, 40),
        ])
        pad = rng.randint(40, 80)
        d.rounded_rectangle(
            [pad, pad, PLANE - pad, PLANE - pad],
            radius=rng.randint(8, 34), fill=plate + (255,),
            outline=(245, 243, 238, 255), width=rng.randint(5, 12),
        )
        fill = (250, 248, 244, 255) if sum(plate) < 480 else (35, 32, 30, 255)
    else:
        # 直接漆在地上：只有數字，沒有底板
        fill = rng.choice([
            (245, 243, 238, 255), (40, 38, 36, 255), (210, 160, 40, 255),
        ])

    font_size = rng.randint(210, 300)
    font = ImageFont.truetype(rng.choice(FONTS), font_size)
    text = str(digit)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (PLANE - tw) / 2 - bbox[0]
    ty = (PLANE - th) / 2 - bbox[1]
    d.text((tx, ty), text, font=font, fill=fill)

    # 數字本身的緊密框（不含底板）——這才是要標註的東西
    glyph = (tx + bbox[0], ty + bbox[1], tx + bbox[2], ty + bbox[3])
    return marker, glyph


def oblique_quad(rng: random.Random) -> np.ndarray:
    """產生一個梯形，模擬手機在約 1–1.5m 高、俯角 30–65 度看地板。

    近端（畫面下緣）比遠端寬，這就是透視前縮；SVHN 的門牌幾乎都是正對鏡頭，
    沒有這個特徵，所以這是 domain gap 最主要的來源之一。
    """
    scale = rng.uniform(0.30, 0.72)
    half_w = CANVAS_W * scale / 2
    half_h = half_w * rng.uniform(0.55, 0.95)

    # 遠端收縮比例：越小代表俯角越平、透視越強
    far = rng.uniform(0.42, 0.88)

    cx = rng.uniform(CANVAS_W * 0.30, CANVAS_W * 0.70)
    cy = rng.uniform(CANVAS_H * 0.35, CANVAS_H * 0.72)

    quad = np.array([
        [-half_w * far, -half_h],   # 遠端左
        [+half_w * far, -half_h],   # 遠端右
        [+half_w,       +half_h],   # 近端右
        [-half_w,       +half_h],   # 近端左
    ], dtype=np.float32)

    # 繞光軸轉一點：使用者不會每次都把手機擺正
    a = math.radians(rng.uniform(-22, 22))
    rot = np.array(
        [[math.cos(a), -math.sin(a)],
         [math.sin(a),  math.cos(a)]], dtype=np.float32
    )
    quad = quad @ rot.T
    quad += np.array([cx, cy], dtype=np.float32)
    return quad


def warp_points(H: np.ndarray, pts: np.ndarray) -> np.ndarray:
    p = np.hstack([pts, np.ones((len(pts), 1), dtype=np.float32)])
    q = (H @ p.T).T
    return q[:, :2] / q[:, 2:3]


def compose(floor: np.ndarray, marker: Image.Image, glyph, rng: random.Random):
    src = np.array([[0, 0], [PLANE, 0], [PLANE, PLANE], [0, PLANE]], dtype=np.float32)
    dst = oblique_quad(rng)
    H = cv2.getPerspectiveTransform(src, dst)

    m = np.array(marker)  # RGBA
    warped = cv2.warpPerspective(
        m, H, (CANVAS_W, CANVAS_H),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
    )
    alpha = (warped[..., 3:4].astype(np.float32) / 255.0) * rng.uniform(0.82, 1.0)
    out = warped[..., :3].astype(np.float32) * alpha + floor.astype(np.float32) * (1 - alpha)

    # 數字緊密框的四角跟著同一個 H 走，再取軸對齊外接框
    x1, y1, x2, y2 = glyph
    corners = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)
    wc = warp_points(H, corners)
    bx1, by1 = wc[:, 0].min(), wc[:, 1].min()
    bx2, by2 = wc[:, 0].max(), wc[:, 1].max()
    return np.clip(out, 0, 255).astype(np.uint8), (bx1, by1, bx2, by2)


def degrade(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """手持拍攝該有的劣化：失焦、動態模糊、雜訊、JPEG。"""
    if rng.random() < 0.55:
        k = rng.choice([3, 5, 7])
        img = cv2.GaussianBlur(img, (k, k), 0)
    if rng.random() < 0.30:
        k = rng.choice([7, 11, 15])
        kern = np.zeros((k, k), np.float32)
        a = math.radians(rng.uniform(0, 180))
        for i in range(k):
            x = int(round((i - k / 2) * math.cos(a) + k / 2))
            y = int(round((i - k / 2) * math.sin(a) + k / 2))
            if 0 <= x < k and 0 <= y < k:
                kern[y, x] = 1
        s = kern.sum()
        if s > 0:
            img = cv2.filter2D(img, -1, kern / s)
    img = np.clip(img.astype(np.float32) + np.random.normal(0, rng.uniform(1.5, 6), img.shape), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(55, 92)])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR) if ok else img


def main() -> None:
    ap = argparse.ArgumentParser(description="合成地板數字測試集")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--digits", default="1234", help="要產生哪些數字（預設對應地圖上的 4 個地標）")
    ap.add_argument("--seed", type=int, default=20260903)
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()

    out = Path(args.out)
    img_dir, lbl_dir = out / "images" / "val", out / "labels" / "val"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    np.random.seed(args.seed)
    digits = [int(c) for c in args.digits]
    counts = {d: 0 for d in digits}

    for i in range(args.n):
        digit = digits[i % len(digits)]
        floor = make_floor(rng)
        marker, glyph = make_marker(digit, rng)
        img, (x1, y1, x2, y2) = compose(floor, marker, glyph, rng)
        img = degrade(img, rng)

        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(CANVAS_W), x2), min(float(CANVAS_H), y2)
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue  # 被裁到幾乎不見的就跳過，不要製造壞標註

        stem = f"floor_{i:05d}"
        cv2.imwrite(str(img_dir / f"{stem}.jpg"), img)
        cx, cy = (x1 + x2) / 2 / CANVAS_W, (y1 + y2) / 2 / CANVAS_H
        bw, bh = (x2 - x1) / CANVAS_W, (y2 - y1) / CANVAS_H
        (lbl_dir / f"{stem}.txt").write_text(
            f"{digit} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8"
        )
        counts[digit] += 1

    yaml_path = out / "floor_test.yaml"
    yaml_path.write_text(
        "# 由 ml/make_floor_testset.py 產生的合成地板數字測試集。\n"
        "# 這是 domain gap 的量測工具，不是訓練資料。\n"
        f"path: {out.as_posix()}\n"
        "train: images/val\n"
        "val: images/val\n"
        "names:\n" + "".join(f"  {i}: '{i}'\n" for i in range(10)),
        encoding="utf-8",
    )
    print(f"產生 {sum(counts.values())} 張：{counts}")
    print(f"設定檔：{yaml_path}")


if __name__ == "__main__":
    main()
