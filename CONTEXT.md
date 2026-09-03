# Indoor Positioning System 共享語言

> 這份檔是這個專案的**共享記憶體區段**。人與 Agent 讀同一份定義。
> 維護方式見 `.claude/skills/se-context-language`。
> **不要一次寫完。** 詞彙在命名衝突、解釋超過兩句、歧義被戳破時才長出來。

## Language

**Landmark（地標）**：
場域中一個實際貼在地板上的數字標記，是這套系統唯一的位置真相來源。
_避免_：marker、tag、QR

**Node（節點）**：
地圖上對應某個 Landmark 的一筆資料，帶有座標與鄰接關係。Landmark 是實體，Node 是它在地圖裡的紀錄。
_避免_：point、location（太泛）

**Detection（偵測）**：
YOLO 對一張影像輸出的單一結果：數字類別 + 信心值 + bounding box。還沒有位置意義。
_避免_：recognition、prediction

**Fix（定位結果）**：
Detection 對上 Node 之後產生的、帶座標的位置判定。前端顯示的是 Fix，不是 Detection。
_避免_：position（當名詞太泛）、result

**Screening（端上初篩）**：
手機端輕量模型的工作：判斷這一幀「有沒有數字值得上傳」。它不負責認出是幾號。
_避免_：detection（會和後端的 Detection 混淆）

## Relationships

- 一個 **Node** 對應剛好一個 **Landmark**
- 一次 **Screening** 通過才會產生一次上傳，一次上傳產生 0..n 個 **Detection**
- 一個 **Fix** 由最高信心的 **Detection** 對上一個 **Node** 而來
- 一個 device 在任一時刻只有一個「目前 **Fix**」，但保留歷史軌跡

## Flagged ambiguities

- 「辨識」曾同時指端上初篩與後端確認 —— 已解決：端上叫 **Screening**，後端叫 **Detection**。
- 「座標」曾同時指影像內的 bbox 像素座標與場域平面座標 —— 已解決：bbox 一律講 box，
  場域平面座標才叫 **coordinate**。

## Out of scope

- **航向／朝向（heading）**：雛型只解「我在哪個節點」，不解「我面向哪」。等單一 Landmark 的
  多視角資料夠了再談。
- **樓層轉換（floor transition）**：Node 有 floor 欄位，但跨樓層的路徑邏輯先不定義。
