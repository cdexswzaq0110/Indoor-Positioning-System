"""API 契約。手機端與前端都照這份對齊。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Box(BaseModel):
    """影像內的 bounding box，像素座標。"""
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    """YOLO 對一張影像的單一輸出。還沒有位置意義。"""
    digit: int = Field(..., ge=0, le=9)
    confidence: float = Field(..., ge=0.0, le=1.0)
    box: Box


class Coordinate(BaseModel):
    x: float
    y: float
    floor: int


class Fix(BaseModel):
    """Detection 對上 Node 之後的位置判定。前端顯示的是這個。"""
    device_id: str
    node_id: str
    node_name: str
    digit: int
    confidence: float
    coordinate: Coordinate
    timestamp: datetime
    source: Literal["backend-confirm", "manual"] = "backend-confirm"


class DetectResponse(BaseModel):
    """POST /api/v1/detect 的回應。"""
    ok: bool
    fix: Fix | None = None
    detections: list[Detection] = []
    reason: str | None = None
    inference_ms: float
    model: str
    capture_id: str | None = None


class NodeOut(BaseModel):
    id: str
    landmark_digit: int | None = None
    floor: int
    x: float
    y: float
    name: str
    neighbors: list[str] = []


class PoiOut(BaseModel):
    id: str
    floor: int
    x: float
    y: float
    name: str
    name_en: str | None = None


class FloorOut(BaseModel):
    id: int
    name: str
    width_m: float
    height_m: float


class MapOut(BaseModel):
    site: str
    version: int
    coordinate_unit: str
    floors: list[FloorOut]
    nodes: list[NodeOut]
    pois: list[PoiOut]


class HealthOut(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
    model: str
    device: str
    nodes: int
