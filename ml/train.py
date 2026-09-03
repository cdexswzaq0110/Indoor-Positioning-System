"""訓練後端確認用的 YOLO 數字偵測模型。

雛型階段的目標不是刷分，是拿到一組能讓整條鏈路跑起來的權重。
訓練完會把 best.pt 複製到 ml/weights/，後端 detector 直接吃那個路徑。
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
WEIGHTS_DIR = ML_DIR / "weights"


def main() -> None:
    ap = argparse.ArgumentParser(description="訓練地板數字偵測模型")
    ap.add_argument("--model", default="yolo11n.pt",
                    help="起始權重。n 最快，s/m 較準但慢")
    ap.add_argument("--data", default=str(ML_DIR / "dataset.yaml"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=320,
                    help="SVHN 原圖很小，320 就夠；換真實地板照片再調大")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--device", default="0", help="'0' 用 GPU，'cpu' 強制 CPU")
    ap.add_argument("--name", default="digits")
    ap.add_argument("--resume", action="store_true")
    # ultralytics 預設 workers=8。Windows 是 spawn，每個 worker 都是完整的
    # Python + torch 行程（各約 1GB RSS），16GB 的機器會被塞爆——
    # 症狀是 DataLoader worker 丟 MemoryError，不是 CUDA OOM。見 docs/lessons/0002。
    ap.add_argument("--workers", type=int, default=4,
                    help="dataloader worker 數。16GB RAM 用 4，32GB 以上可以往上加")
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"找不到 {data_path}，請先跑 ml/prepare_svhn.py")

    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(ML_DIR / "runs"),
        name=args.name,
        exist_ok=True,
        resume=args.resume,
        patience=10,
        # 地板數字會被踩髒、被斜角拍到，所以留較強的幾何與亮度擾動。
        degrees=10.0,
        perspective=0.0005,
        scale=0.5,
        hsv_v=0.5,
        # 數字左右鏡射會變成別的字（2/5、6/9 之類），一定要關。
        fliplr=0.0,
        flipud=0.0,
        mosaic=1.0,
    )

    best = ML_DIR / "runs" / args.name / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit(f"訓練結束但找不到 {best}")
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, WEIGHTS_DIR / "best.pt")
    print(f"\n權重已就位：{WEIGHTS_DIR / 'best.pt'}")
    print("後端重載： curl -X POST http://localhost:8100/api/v1/admin/reload")


if __name__ == "__main__":
    main()
