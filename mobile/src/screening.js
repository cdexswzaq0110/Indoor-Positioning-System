/**
 * 端上初篩（Screening）。
 *
 * 職責只有一個：判斷「這一幀有沒有數字值得上傳」。
 * 認出是幾號是後端的事（見 CONTEXT.md 對 Screening 與 Detection 的區分）。
 *
 * 兩種策略，按環境自動選：
 *
 *   1. detail-proxy（預設，Expo Go 就能跑）
 *      把中央區域縮到 96x96、用固定品質壓成 JPEG，看壓出來多大。
 *      空地板壓縮後很小；有高對比印刷數字的畫面邊緣多、壓不下去。
 *      這是個代理指標不是偵測器——它擋掉的是「明顯沒東西」的幀，
 *      不保證通過的幀裡真的有數字，那由後端確認。
 *
 *   2. onnx（需要 EAS dev build，見 mobile/README.md）
 *      跑匯出的輕量模型，看最高 objectness。準得多，但要原生模組。
 *      用 ONNX 而不是 TFLite，是因為 ultralytics 的 LiteRT 匯出只支援
 *      Linux x86 與 macOS，在這個專案的開發機（Windows）上匯不出來。
 */

let manipulator = null;
try {
  manipulator = require("expo-image-manipulator");
} catch {
  manipulator = null;
}

/** SDK 54 之後 ImageManipulator 換成 context API，舊的 manipulateAsync 標為 deprecated。 */
async function shrinkToBase64(uri, size, quality) {
  if (!manipulator) throw new Error("expo-image-manipulator 未安裝");

  const actions = [{ resize: { width: size, height: size } }];
  const saveOpts = { compress: quality, format: "jpeg", base64: true };

  if (typeof manipulator.manipulateAsync === "function") {
    const out = await manipulator.manipulateAsync(uri, actions, {
      ...saveOpts,
      format: manipulator.SaveFormat ? manipulator.SaveFormat.JPEG : "jpeg",
    });
    return out.base64;
  }

  // 新 context API
  const ctx = manipulator.ImageManipulator.manipulate(uri);
  ctx.resize({ width: size, height: size });
  const image = await ctx.renderAsync();
  const out = await image.saveAsync({
    compress: quality,
    format: manipulator.SaveFormat.JPEG,
    base64: true,
  });
  return out.base64;
}

/**
 * @param {object} opts
 * @param {number} opts.threshold detail-proxy 的門檻（base64 字元數）。
 *   愈高愈嚴格、上傳愈少。實測從 2600 起調。
 */
export function createDetailProxyScreener(opts = {}) {
  const size = opts.size ?? 96;
  const quality = opts.quality ?? 0.5;
  const threshold = opts.threshold ?? 2600;

  return {
    name: "detail-proxy",
    describe: () => `detail-proxy · 門檻 ${threshold}`,
    async screen(photo) {
      try {
        const b64 = await shrinkToBase64(photo.uri, size, quality);
        const score = b64 ? b64.length : 0;
        return {
          pass: score >= threshold,
          score,
          detail: `${score} / ${threshold}`,
        };
      } catch (err) {
        // 初篩壞掉時寧可放行，讓後端去判——漏傳比誤擋難查。
        return { pass: true, score: -1, detail: `初篩失敗，放行：${err.message}` };
      }
    },
  };
}

/**
 * ONNX 初篩。需要 onnxruntime-react-native（原生模組，Expo Go 沒有）。
 * 模組不在時回 null，呼叫端自己退回 detail-proxy。
 */
export function createOnnxScreener(opts = {}) {
  let ort = null;
  try {
    ort = require("onnxruntime-react-native");
  } catch {
    return null;
  }
  if (!ort || !ort.InferenceSession) return null;

  const threshold = opts.threshold ?? 0.25;
  let session = null;

  return {
    name: "onnx",
    describe: () => `onnx · 門檻 ${threshold}`,
    async load() {
      if (!session) {
        // ml/export.py 產生的 best.onnx，放進 mobile/assets/
        session = await ort.InferenceSession.create(
          require("../assets/screen-model.onnx")
        );
      }
      return session;
    },
    async screen(photo) {
      // 待接：把 photo 轉成 Float32 張量 (1,3,256,256)。
      // RN 沒有內建的像素存取，takePictureAsync 給的是檔案 URI 不是像素。
      // 實務上用 react-native-vision-camera 的 frame processor 直接吃相機緩衝，
      // 而不是先存檔再讀回來——後者比初篩本身還慢，等於白做。
      throw new Error("onnx 初篩尚未接上像素來源，見 mobile/README.md");
    },
  };
}

/** 自動挑一個能用的。 */
export function createScreener(opts = {}) {
  if (opts.preferModel) {
    const m = createOnnxScreener(opts.onnx);
    if (m) return m;
  }
  return createDetailProxyScreener(opts.detailProxy);
}
