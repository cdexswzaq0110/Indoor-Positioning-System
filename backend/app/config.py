"""集中設定。環境變數優先，否則用雛型預設值。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = BASE_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
WEB_DIR = BASE_DIR / "web"

# 這台機器的 8000 已被佔用，預設走 8100。
PORT = int(os.getenv("IPS_PORT", "8100"))

MAP_PATH = Path(os.getenv("IPS_MAP_PATH", DATA_DIR / "map.json"))

# 後端確認用的完整模型。沒有這個檔案時 detector 會退回 stub 模式。
WEIGHTS_PATH = Path(os.getenv("IPS_WEIGHTS", BASE_DIR / "ml" / "weights" / "best.pt"))

# 低於這個信心值的 Detection 不產生 Fix。
CONF_THRESHOLD = float(os.getenv("IPS_CONF", "0.35"))
IOU_THRESHOLD = float(os.getenv("IPS_IOU", "0.45"))

# 存下上傳的影像，方便之後回頭標註成真實訓練資料。
SAVE_CAPTURES = os.getenv("IPS_SAVE_CAPTURES", "1") == "1"
CAPTURES_DIR = DATA_DIR / "captures"

# 每個 device 保留多少筆歷史 Fix。
HISTORY_LIMIT = int(os.getenv("IPS_HISTORY", "200"))

MAX_UPLOAD_BYTES = int(os.getenv("IPS_MAX_UPLOAD", str(8 * 1024 * 1024)))
