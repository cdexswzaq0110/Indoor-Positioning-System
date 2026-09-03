# CLAUDE.md — Indoor Positioning System

> **描述：** 用手機鏡頭辨識地板數字地標，經中控後端換算成座標，即時推送到前端地圖。
> **階段：** 雛型
> **語言：** Python 3.11（FastAPI + Ultralytics YOLO）／React Native + Expo（手機端）／Vanilla JS（前端地圖）

## 開發流程

沒有寫死的命令序列。能力按需載入，路由見 `.claude/skills/INDEX.md`；
任務怎麼切、派給誰見 `.claude/EXECUTION_MODEL.md`。

預設節奏：確認分支 → 爬最小實作階梯 → 做出最小可動的東西 → 跑起來看 → 留 Lesson。

## 共享語言

見 `CONTEXT.md`。詞彙有衝突時以那份為準。

## 這個專案的實際指令

| 用途 | 指令 |
|---|---|
| 後端啟動 | `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8100 --reload` |
| 前端地圖 | 後端已掛載，直接開 `http://<host>:8100/` |
| 資料集轉檔 | `.venv\Scripts\python.exe ml\prepare_svhn.py` |
| 訓練 | `.venv\Scripts\python.exe ml\train.py` |
| 匯出端上模型 | `.venv\Scripts\python.exe ml\export.py` |
| 手機端 | `cd mobile && npm install && npx expo start` |

## 這個專案特有的約束

- **Port 8100，不是 8000。** 這台機器的 8000 已被其他程序佔用（preflight 已確認）。
- **這台機器沒有 Android SDK／adb／Flutter，只有 Java 17。** 手機端要出實機安裝檔走 EAS Build（雲端），
  不要假設可以本機 `gradlew assembleRelease`。
- **訓練的 `workers` 不要超過 4。** 這台機器 16GB RAM，ultralytics 預設 8 個 worker，
  Windows 是 spawn（每個 worker 一份完整 torch，約 1GB），跑到第二個 epoch 會被 RAM 撐爆。
  症狀是 DataLoader 丟 `MemoryError`，**不是** CUDA OOM——別往顯卡方向找。見 `docs/lessons/0002`。
- **推論是混合式的**：手機端跑輕量模型做初篩（有沒有數字），後端跑完整模型做確認與座標換算。
  改任一端的模型時，`ml/export.py` 的輸出必須與 `backend/app/detector.py` 的類別順序一致。
- **端上模型走 ONNX，不走 TFLite。** ultralytics 的 LiteRT 匯出只支援 Linux x86 與 macOS，
  在這台 Windows 機器上一定失敗。要 TFLite 得換平台或用 Ultralytics 雲端匯出。
- **SVHN 是門牌號碼，不是地板數字。** 這是 bootstrap 用的代理資料集，存在 domain gap；
  真實地板照片進來後必須 fine-tune，不要拿 SVHN 的驗證分數當作場域準確率。
- **地板地標不要用數字 1。** 合成地板測試集上「1」的 recall 只有 0.499（2/3/4 是 0.83–0.96）——
  細直筆畫在地板透視前縮下更細，SVHN 又幾乎只有正面平視的「1」。這是功能性缺陷不是精度問題，
  改地圖比再訓練有效。見 `docs/lessons/0004`。
