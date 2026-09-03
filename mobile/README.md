# 手機端（Expo / React Native）

手機端負責兩件事：**拍**、以及**端上初篩**。認出是幾號、換算座標都在後端。

## 跑起來

```bash
cd mobile
npm install
npx expo install --fix   # 讓套件版本對齊 Expo SDK 57
npx expo start
```

手機裝 Expo Go，掃 terminal 的 QR code。

**進 App 後先開「設定」，把後端位址改成這台電腦的區網 IP**（不是 `localhost`——
在手機上 localhost 指的是手機自己）。查法：

```bash
ipconfig | findstr /i "IPv4"
```

填成 `http://<那個 IP>:8100`。手機和電腦要在同一個 Wi-Fi。

## 這台機器的限制

preflight 查過：**沒有 Android SDK、沒有 adb、沒有 Flutter**，只有 Java 17。
所以 `npx expo run:android` 這種本機原生建置會失敗。要出實機安裝檔走 EAS（雲端建置）：

```bash
npm install -g eas-cli
eas login
eas build --platform android --profile preview
```

Expo Go 足夠開發與驗證整條鏈路，只有在需要原生模組（下一節）時才必須 dev build。

## 初篩策略：現在是什麼、還差什麼

`src/screening.js` 有兩條路。

**現在跑的是 `detail-proxy`**（Expo Go 就能用）：
把畫面中央縮到 96×96、固定品質壓成 JPEG，看壓出來多大。空地板壓完很小；
有高對比印刷數字的畫面邊緣多、壓不下去。門檻在 App 設定裡可調（預設 2600）。

這是**代理指標，不是偵測器**。它擋掉的是「明顯沒東西」的幀，
不保證通過的幀裡真的有數字——那由後端確認。這符合混合架構的分工，
但它的判斷力明顯低於一個真模型。

**`onnx` 那條路還沒接完。** 缺的是像素來源：React Native 沒有內建的
影像像素存取，`takePictureAsync` 給的是檔案 URI 不是張量。要接完需要：

1. `npx expo install onnxruntime-react-native react-native-vision-camera`
2. 用 vision-camera 的 frame processor 直接吃相機緩衝（不要存檔再讀回來，那樣比初篩本身還慢，等於白做）
3. `ml/weights/best.onnx`（`python ml/export.py --imgsz 256` 產生）複製成 `mobile/assets/screen-model.onnx`
4. 因為引入原生模組，之後就得走 EAS dev build，不能再用 Expo Go

`createOnnxScreener()` 的載入與挑選邏輯已經寫好，`screen()` 現在會明確丟錯而不是
假裝有結果——接上像素來源後把那個 throw 換掉即可。

### 為什麼是 ONNX 不是 TFLite

原本規劃走 `react-native-fast-tflite`，但 **ultralytics 的 LiteRT 匯出只支援 Linux x86 與 macOS**，
在 Windows 開發機上直接失敗【已確認：2026-09-03 實測 `LiteRT export only supported on Linux x86 and macOS`】。

ONNX 匯出在 Windows 正常（`best.onnx`，imgsz 256，10.0 MB）。真要 TFLite 的話，
得換到 Linux/macOS 匯出，或用 Ultralytics 的雲端匯出服務。

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `App.js` | 相機畫面、定位迴圈、狀態與事件列表 |
| `src/config.js` | 設定持久化、`/api/v1/detect` 與 `/api/v1/health` 呼叫 |
| `src/screening.js` | 端上初篩的兩種策略與自動挑選 |
