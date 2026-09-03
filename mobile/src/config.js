import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "ips.settings.v1";

export const DEFAULTS = {
  // 換成後端實際位址。手機和後端要在同一個區網，localhost 在手機上指的是手機自己。
  backendUrl: "http://192.168.1.100:8100",
  deviceId: "phone-01",
  intervalMs: 1500,
  floorHint: "",
  screenThreshold: 2600,
};

export async function loadSettings() {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

export async function saveSettings(settings) {
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    // 設定存不起來不該擋住定位本身
  }
}

/** 上傳一張影像給中控後端確認。 */
export async function postDetect(settings, photoUri) {
  const form = new FormData();
  form.append("image", {
    uri: photoUri,
    name: "frame.jpg",
    type: "image/jpeg",
  });
  form.append("device_id", settings.deviceId);
  if (settings.floorHint !== "" && settings.floorHint != null) {
    form.append("floor_hint", String(settings.floorHint));
  }

  const base = settings.backendUrl.replace(/\/+$/, "");
  const res = await fetch(`${base}/api/v1/detect`, {
    method: "POST",
    body: form,
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json();
}

export async function pingHealth(settings) {
  const base = settings.backendUrl.replace(/\/+$/, "");
  const res = await fetch(`${base}/api/v1/health`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
