"""把訓練好的模型匯出成手機端初篩用的格式。

端上只需要判斷「這一幀有沒有數字值得上傳」，所以用同一組權重、
較小的 imgsz 匯出即可；認出是幾號仍然由後端負責。
"""
from __future__ import annotations

import argparse
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
WEIGHTS_DIR = ML_DIR / "weights"


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出端上初篩模型")
    ap.add_argument("--weights", default=str(WEIGHTS_DIR / "best.pt"))
    ap.add_argument("--imgsz", type=int, default=256,
                    help="端上初篩解析度。越小越省電，但太小會漏掉遠處的數字")
    # tflite 不放進預設：ultralytics 的 LiteRT 匯出只支援 Linux x86 與 macOS，
    # 在 Windows 上一定失敗（2026-09-03 實測）。要 tflite 得換平台或用 Ultralytics 雲端。
    ap.add_argument("--formats", nargs="+", default=["onnx"],
                    help="onnx 給 onnxruntime-react-native（Windows 可用）；"
                         "tflite 給 react-native-fast-tflite，但只能在 Linux/macOS 匯出")
    ap.add_argument("--int8", action="store_true", help="tflite 走 int8 量化，體積最小")
    args = ap.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        raise SystemExit(f"找不到 {weights}，請先跑 ml/train.py")

    from ultralytics import YOLO

    model = YOLO(str(weights))
    for fmt in args.formats:
        print(f"\n[export] {fmt} imgsz={args.imgsz}")
        kwargs = {"format": fmt, "imgsz": args.imgsz}
        if fmt == "tflite" and args.int8:
            kwargs["int8"] = True
        try:
            out = model.export(**kwargs)
            print(f"  -> {out}")
        except Exception as exc:
            # tflite 匯出需要額外的 tensorflow 相依，缺了不該擋住 onnx。
            print(f"  ✕ {fmt} 匯出失敗：{exc}")

    print("\n把產出的模型檔複製到 mobile/assets/ 給 App 使用。")


if __name__ == "__main__":
    main()
