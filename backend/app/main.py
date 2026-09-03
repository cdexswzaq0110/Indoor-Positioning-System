"""中控系統後端：接收手機上傳的影像，確認地標，換算座標，推送給前端。"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .detector import Detector
from .landmarks import LandmarkMap
from .schemas import (
    Coordinate,
    DetectResponse,
    Fix,
    HealthOut,
    MapOut,
)
from .store import PositionStore
from .ws import ConnectionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("ips")

landmark_map = LandmarkMap(config.MAP_PATH)
detector = Detector(config.WEIGHTS_PATH, config.CONF_THRESHOLD, config.IOU_THRESHOLD)
store = PositionStore(config.HISTORY_LIMIT)
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    log.info(
        "後端啟動 | port=%s model=%s device=%s nodes=%d",
        config.PORT, detector.model_name, detector.device, landmark_map.node_count,
    )
    if not detector.loaded:
        log.warning("目前是 stub 模式：/api/v1/detect 會回 200 但不產生 Fix。先跑 ml/train.py。")
    yield


app = FastAPI(
    title="Indoor Positioning System — 中控後端",
    version="0.1.0",
    lifespan=lifespan,
)

# 雛型階段：手機端與前端可能來自任意區網位址，先全開。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")


@api.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(
        status="ok",
        model_loaded=detector.loaded,
        model=detector.model_name,
        device=detector.device,
        nodes=landmark_map.node_count,
    )


@api.get("/map", response_model=MapOut)
def get_map() -> MapOut:
    return MapOut(**landmark_map.raw)


@api.post("/detect", response_model=DetectResponse)
async def detect(
    image: UploadFile = File(..., description="手機端初篩通過後上傳的影像"),
    device_id: str = Form(..., min_length=1, max_length=64),
    floor_hint: int | None = Form(None),
) -> DetectResponse:
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="影像是空的")
    if len(payload) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"影像超過上限 {config.MAX_UPLOAD_BYTES} bytes",
        )

    capture_id: str | None = None
    if config.SAVE_CAPTURES:
        capture_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
        (config.CAPTURES_DIR / f"{capture_id}.jpg").write_bytes(payload)

    try:
        detections, inference_ms = detector.infer(payload)
    except Exception as exc:  # 壞圖不該打掛整個中控
        log.exception("推論失敗 device=%s", device_id)
        raise HTTPException(status_code=422, detail=f"推論失敗：{exc}") from exc

    base = {
        "detections": detections,
        "inference_ms": round(inference_ms, 2),
        "model": detector.model_name,
        "capture_id": capture_id,
    }

    if not detector.loaded:
        return DetectResponse(ok=False, reason="模型尚未載入（stub 模式）", **base)
    if not detections:
        return DetectResponse(ok=False, reason="影像中沒有偵測到地板數字", **base)

    best = detections[0]
    node, why = landmark_map.resolve(best.digit, floor_hint)
    if node is None:
        return DetectResponse(ok=False, reason=why, **base)

    fix = Fix(
        device_id=device_id,
        node_id=node["id"],
        node_name=node["name"],
        digit=best.digit,
        confidence=best.confidence,
        coordinate=Coordinate(x=node["x"], y=node["y"], floor=node["floor"]),
        timestamp=datetime.now(timezone.utc),
    )
    store.record(fix)
    await manager.broadcast({"type": "fix", "data": fix.model_dump(mode="json")})
    log.info(
        "FIX device=%s digit=%d conf=%.2f -> %s (%.1f, %.1f) %.0fms",
        device_id, best.digit, best.confidence, node["id"], node["x"], node["y"], inference_ms,
    )
    return DetectResponse(ok=True, fix=fix, **base)


@api.get("/positions", response_model=list[Fix])
def positions() -> list[Fix]:
    return store.all_current()


@api.get("/positions/{device_id}/history", response_model=list[Fix])
def history(device_id: str, limit: int = 50) -> list[Fix]:
    return store.history(device_id, limit=limit)


@api.post("/admin/reload")
def reload_all() -> dict:
    landmark_map.reload()
    detector.reload()
    return {
        "map_nodes": landmark_map.node_count,
        "model_loaded": detector.loaded,
        "model": detector.model_name,
    }


app.include_router(api)


@app.websocket("/ws/positions")
async def ws_positions(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        # 一連上先補現況，前端就不必等下一次 Fix 才有畫面。
        for fix in store.all_current():
            await ws.send_json({"type": "fix", "data": fix.model_dump(mode="json")})
        while True:
            await ws.receive_text()  # 心跳；內容不使用
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)


if config.WEB_DIR.exists():
    app.mount("/app", StaticFiles(directory=config.WEB_DIR, html=True), name="web")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(config.WEB_DIR / "index.html")
