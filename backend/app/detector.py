"""後端確認用的 YOLO 推論。

沒有權重檔時進入 stub 模式：API 仍然可用、仍然回 200，但明說沒有模型。
這是刻意的——整條鏈路要能在模型訓練完成之前就先跑通。
"""
from __future__ import annotations

import io
import logging
import time
from pathlib import Path

from .schemas import Box, Detection

log = logging.getLogger(__name__)


class Detector:
    def __init__(self, weights: Path, conf: float, iou: float) -> None:
        self.weights = weights
        self.conf = conf
        self.iou = iou
        self._model = None
        self._device = "cpu"
        self._names: dict[int, str] = {}
        self._load()

    # ---- 生命週期 ------------------------------------------------------

    def _load(self) -> None:
        if not self.weights.exists():
            log.warning("找不到權重 %s，detector 進入 stub 模式", self.weights)
            return
        try:
            import torch
            from ultralytics import YOLO
        except ImportError as exc:
            log.warning("ultralytics/torch 未安裝（%s），detector 進入 stub 模式", exc)
            return

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = YOLO(str(self.weights))
        self._model.to(self._device)
        self._names = dict(self._model.names)
        log.info("已載入模型 %s，device=%s，classes=%s", self.weights, self._device, self._names)

    def reload(self) -> None:
        self._model = None
        self._load()

    # ---- 狀態 ----------------------------------------------------------

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    @property
    def model_name(self) -> str:
        return self.weights.name if self.loaded else "stub(no-weights)"

    # ---- 推論 ----------------------------------------------------------

    def _class_to_digit(self, cls_id: int) -> int | None:
        """類別索引換成實際數字。

        訓練流程刻意讓 class index == digit，所以正常路徑是直接用索引；
        名稱能解析成數字時以名稱為準，才不會在換模型後默默錯位。
        """
        name = self._names.get(cls_id)
        if name is not None:
            stripped = str(name).strip()
            if stripped.isdigit() and len(stripped) == 1:
                return int(stripped)
        if 0 <= cls_id <= 9:
            return cls_id
        return None

    def infer(self, image_bytes: bytes) -> tuple[list[Detection], float]:
        if not self.loaded:
            return [], 0.0

        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        started = time.perf_counter()
        results = self._model.predict(
            source=image,
            conf=self.conf,
            iou=self.iou,
            verbose=False,
            device=self._device,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        detections: list[Detection] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                digit = self._class_to_digit(int(box.cls.item()))
                if digit is None:
                    continue
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                detections.append(
                    Detection(
                        digit=digit,
                        confidence=float(box.conf.item()),
                        box=Box(x1=x1, y1=y1, x2=x2, y2=y2),
                    )
                )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections, elapsed_ms
