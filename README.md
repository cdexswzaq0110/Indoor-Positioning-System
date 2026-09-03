# Indoor Positioning System

用手機鏡頭辨識**地板上的數字地標**，經中控後端換算成場域座標，即時推送到前端地圖。

```
手機相機 ──► 端上初篩 ──► 上傳 JPEG ──► 後端 YOLO 確認 ──► 數字→節點→座標 ──► WebSocket ──► 前端地圖
  拍照        有沒有數字      只傳過篩的        認出是幾號          查地圖              即時推送        畫出位置
```

分工的關鍵在：**端上只判斷「值不值得傳」，後端才判斷「是幾號」**。
用詞的精確定義見 [`CONTEXT.md`](CONTEXT.md)。

## 現況

| 部分 | 狀態 |
|---|---|
| 後端 API（FastAPI） | 可用。stub 模式與載入模型後都驗證過 |
| 前端地圖（WebSocket 即時） | 可用 |
| 地圖／座標換算 | 可用，4 個地標 + 2 個 POI 的示範場域 |
| 資料集（SVHN → YOLO） | 完成，train 33,402 / val 4,000 |
| 模型訓練 | 完成。30 epochs，**mAP50 0.905 / P 0.903 / R 0.867**，推論 2.8ms/張，權重 5.4MB |
| 端上模型匯出 | `best.onnx`（imgsz 256, 10.0MB）。TFLite 在 Windows 匯不出來，見 `mobile/README.md` |
| 手機 App（Expo） | 可用；端上初篩目前是 detail-proxy，ONNX 那條路還沒接完（見 `mobile/README.md`） |

## 跑起來

### 1. 後端

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8100 --reload
```

**Port 是 8100，不是 8000**——這台機器的 8000 已被其他程序佔用。

前端地圖：`http://localhost:8100/`　API 文件：`http://localhost:8100/docs`

沒有權重檔時後端進入 **stub 模式**：API 全部照常回應，但不產生定位結果。
這是刻意的——整條鏈路要能在模型訓練完成之前就先驗證。

### 2. 訓練

```bash
.venv\Scripts\python.exe ml/prepare_svhn.py     # 下載好的 SVHN → YOLO 格式
.venv\Scripts\python.exe ml/train.py            # yolo11n, 30 epochs, imgsz 320, workers 4
curl -X POST http://localhost:8100/api/v1/admin/reload
```

**`--workers` 預設是 4，不是 ultralytics 的 8。** 16GB RAM 的 Windows 機器上，
8 個 worker（spawn，每個一份完整 torch）會在第二個 epoch 把 RAM 吃光。
症狀是 DataLoader 丟 `MemoryError`（連 1 MiB 都配不到），**不是** CUDA OOM——
往顯卡方向找會找錯。RAM 更大的機器可以往上加。

`train.py` 結束後會把 `best.pt` 複製到 `ml/weights/`，後端就是讀那個路徑。
`admin/reload` 讓後端不用重啟就換模型。

**訓練途中也可以先接上去驗證**——ultralytics 每個 epoch 都會寫 `ml/runs/digits/weights/last.pt`，
複製成 `ml/weights/best.pt` 再 reload 即可，不會干擾還在跑的訓練。

### 信心門檻

`IPS_CONF` 預設 `0.35`。這是給**已收斂模型**的值；模型還沒訓練夠時它會濾掉大量正確偵測
（實測：只跑 1 epoch 的模型，正確的 3 與 4 分別只有 0.31／0.35，剛好被擋在門外）。

驗證早期模型時用 `IPS_CONF=0.2` 啟動，但**不要為了讓 demo 好看就把正式門檻調低**——
那是拿誤判換召回。`admin/reload` 只重載地圖與模型，**不會**重讀門檻，改它要重啟後端。

### 3. 手機端

見 [`mobile/README.md`](mobile/README.md)。要點：後端位址要填**電腦的區網 IP**，不是 localhost。

## 資料集與它的限制

用的是 [SVHN Format 1](http://ufldl.stanford.edu/housenumbers/)（門牌號碼，含 bounding box）。
選它的理由是免 API key、可直接下載、標註品質穩定。

**但 SVHN 是門牌，不是地板數字。** 兩者的視角、光線、材質、透視變形都不一樣，
存在明確的 domain gap。所以：

- SVHN 上的驗證分數**不能**當作場域準確率
- 真實地板照片是必要的，不是加分項
- 後端預設會把每張上傳的影像存到 `backend/data/captures/`，就是為了累積真實資料回頭 fine-tune

轉檔時 SVHN 的標籤 `10`（代表數字 0）會映回 `0`，讓 **class index 等於實際數字**，
後端 `detector.py` 才能直接把類別索引當數字用。

訓練時 `fliplr` 與 `flipud` 都設 0——數字鏡射會變成別的字，翻轉增強會直接教壞模型。

## API

| 方法 | 路徑 | 用途 |
|---|---|---|
| GET | `/api/v1/health` | 模型是否載入、跑在哪個 device、幾個地標 |
| GET | `/api/v1/map` | 樓層、節點、POI |
| POST | `/api/v1/detect` | multipart：`image`、`device_id`、選填 `floor_hint` |
| GET | `/api/v1/positions` | 每個裝置目前的定位結果 |
| GET | `/api/v1/positions/{device_id}/history` | 軌跡 |
| POST | `/api/v1/admin/reload` | 重載地圖與模型，不必重啟 |
| WS | `/ws/positions` | 定位結果即時推送 |

## 場域設定

改 [`backend/data/map.json`](backend/data/map.json)：每個 `node` 的 `landmark_digit`
對應實際貼在地板上的數字，`x`／`y` 是公尺、`floor` 是樓層。
同一層樓不能有兩個相同數字（載入時會直接報錯）；跨樓層重複則需要呼叫端帶 `floor_hint`。

改完 `POST /api/v1/admin/reload` 生效。

## 專案結構

```
backend/app/     FastAPI：detector（YOLO）、landmarks（數字→座標）、store、ws
backend/data/    map.json 場域地圖 + captures/ 上傳影像存檔
ml/              prepare_svhn.py（轉檔）、train.py、export.py（端上模型）
web/             前端地圖，後端直接掛載在 /
mobile/          Expo App
.claude/         工程 harness（來自 Serendipity-Epiphany）
```

開發流程與約束見 [`CLAUDE.md`](CLAUDE.md)，共享詞彙見 [`CONTEXT.md`](CONTEXT.md)。
