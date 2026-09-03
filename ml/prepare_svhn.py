"""把 SVHN Format 1 轉成 YOLO 偵測資料集。

SVHN 的標註放在 digitStruct.mat，是 MATLAB v7.3（HDF5）格式，得用 h5py 走參考解析。
類別索引刻意等於實際數字：SVHN 用 10 代表 0，這裡一律映回 0，
後端 detector 才能直接把 class index 當數字用。
"""
from __future__ import annotations

import argparse
import random
import shutil
import tarfile
from pathlib import Path

import h5py
from PIL import Image

ML_DIR = Path(__file__).resolve().parent
RAW_DIR = ML_DIR / "data" / "raw"
EXTRACT_DIR = ML_DIR / "data" / "svhn"
OUT_DIR = ML_DIR / "data" / "yolo"


def extract(archive: Path, dest: Path) -> Path:
    """解壓 tar.gz，回傳裡面那個資料夾。已解壓過就跳過。"""
    stem = archive.name.replace(".tar.gz", "")
    target = dest / stem
    if target.exists() and any(target.glob("*.png")):
        print(f"[skip] {target} 已存在")
        return target
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[extract] {archive.name} -> {dest}")
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")
    return target


def read_digit_struct(mat_path: Path) -> list[tuple[str, list[dict]]]:
    """解析 digitStruct.mat，回傳 [(檔名, [box, ...]), ...]。"""
    records: list[tuple[str, list[dict]]] = []
    with h5py.File(mat_path, "r") as f:
        struct = f["digitStruct"]
        names, bboxes = struct["name"], struct["bbox"]

        def deref(ref):
            return f[ref]

        def values(item, key: str) -> list[float]:
            attr = item[key]
            if attr.shape[0] == 1:
                return [float(attr[0][0])]
            return [float(deref(attr[i][0])[0][0]) for i in range(attr.shape[0])]

        total = names.shape[0]
        for i in range(total):
            name = "".join(chr(c[0]) for c in deref(names[i][0])[:])
            item = deref(bboxes[i][0])
            heights = values(item, "height")
            lefts = values(item, "left")
            tops = values(item, "top")
            widths = values(item, "width")
            labels = values(item, "label")
            boxes = [
                {"left": l, "top": t, "width": w, "height": h, "label": int(lb)}
                for l, t, w, h, lb in zip(lefts, tops, widths, heights, labels)
            ]
            records.append((name, boxes))
            if (i + 1) % 5000 == 0:
                print(f"  parsed {i + 1}/{total}")
    return records


def to_yolo_lines(boxes: list[dict], img_w: int, img_h: int) -> list[str]:
    """SVHN 的絕對座標框換成 YOLO 的正規化 cx cy w h。座標會被夾回影像範圍內。"""
    lines: list[str] = []
    for b in boxes:
        # SVHN label：1..9 就是 1..9，10 代表 0。
        digit = 0 if b["label"] == 10 else b["label"]
        if not 0 <= digit <= 9:
            continue
        x1 = max(0.0, b["left"])
        y1 = max(0.0, b["top"])
        x2 = min(float(img_w), b["left"] + b["width"])
        y2 = min(float(img_h), b["top"] + b["height"])
        if x2 <= x1 or y2 <= y1:
            continue
        cx = (x1 + x2) / 2 / img_w
        cy = (y1 + y2) / 2 / img_h
        w = (x2 - x1) / img_w
        h = (y2 - y1) / img_h
        lines.append(f"{digit} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return lines


def build_split(src_dir: Path, split: str, limit: int | None, move: bool) -> int:
    img_out = OUT_DIR / "images" / split
    lbl_out = OUT_DIR / "labels" / split
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    print(f"[parse] {src_dir / 'digitStruct.mat'}")
    records = read_digit_struct(src_dir / "digitStruct.mat")
    if limit is not None and limit < len(records):
        random.Random(42).shuffle(records)
        records = records[:limit]

    written = 0
    for name, boxes in records:
        src = src_dir / name
        if not src.exists():
            continue
        with Image.open(src) as im:
            img_w, img_h = im.size
        lines = to_yolo_lines(boxes, img_w, img_h)
        if not lines:
            continue
        (lbl_out / f"{Path(name).stem}.txt").write_text("\n".join(lines), encoding="utf-8")
        dst = img_out / name
        if not dst.exists():
            shutil.move(str(src), dst) if move else shutil.copy2(src, dst)
        written += 1
        if written % 5000 == 0:
            print(f"  wrote {written}")
    print(f"[done] {split}: {written} 張")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="SVHN -> YOLO 資料集")
    ap.add_argument("--val-limit", type=int, default=4000,
                    help="驗證集取樣張數（SVHN test 全量 13068 太慢）")
    ap.add_argument("--train-limit", type=int, default=None)
    ap.add_argument("--copy", action="store_true",
                    help="複製而非搬移影像（預設搬移，省 700MB）")
    args = ap.parse_args()

    train_src = extract(RAW_DIR / "train.tar.gz", EXTRACT_DIR)
    test_src = extract(RAW_DIR / "test.tar.gz", EXTRACT_DIR)

    n_train = build_split(train_src, "train", args.train_limit, move=not args.copy)
    n_val = build_split(test_src, "val", args.val_limit, move=not args.copy)

    yaml_path = ML_DIR / "dataset.yaml"
    yaml_path.write_text(
        "# 由 ml/prepare_svhn.py 產生。class index == 實際數字。\n"
        f"path: {OUT_DIR.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        + "".join(f"  {i}: '{i}'\n" for i in range(10)),
        encoding="utf-8",
    )
    print(f"\n資料集就緒：train={n_train} val={n_val}")
    print(f"設定檔：{yaml_path}")


if __name__ == "__main__":
    main()
