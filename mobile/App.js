import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useColorScheme,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { StatusBar } from "expo-status-bar";

import { DEFAULTS, loadSettings, pingHealth, postDetect, saveSettings } from "./src/config";
import { createScreener } from "./src/screening";

export default function App() {
  const scheme = useColorScheme();
  const t = scheme === "dark" ? dark : light;

  const [permission, requestPermission] = useCameraPermissions();
  const [settings, setSettings] = useState(DEFAULTS);
  const [ready, setReady] = useState(false);
  const [running, setRunning] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [health, setHealth] = useState(null);
  const [fix, setFix] = useState(null);
  const [status, setStatus] = useState("待機");
  const [log, setLog] = useState([]);
  const [stats, setStats] = useState({ frames: 0, uploads: 0, fixes: 0 });

  const cameraRef = useRef(null);
  const runningRef = useRef(false);
  const busyRef = useRef(false);
  const screenerRef = useRef(null);

  useEffect(() => {
    loadSettings().then((s) => {
      setSettings(s);
      screenerRef.current = createScreener({
        detailProxy: { threshold: s.screenThreshold },
      });
      setReady(true);
    });
  }, []);

  const addLog = useCallback((line, kind = "info") => {
    setLog((prev) => [
      { id: `${Date.now()}-${Math.random()}`, line, kind, at: new Date() },
      ...prev.slice(0, 40),
    ]);
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const h = await pingHealth(settings);
      setHealth(h);
      addLog(
        `後端 OK · 模型 ${h.model_loaded ? h.model : "未載入"} · ${h.nodes} 個地標`,
        h.model_loaded ? "ok" : "warn"
      );
    } catch (err) {
      setHealth(null);
      addLog(`連不到後端：${err.message}`, "bad");
    }
  }, [settings, addLog]);

  /** 一輪：拍照 → 端上初篩 → 通過才上傳後端確認。 */
  const tick = useCallback(async () => {
    if (busyRef.current || !cameraRef.current) return;
    busyRef.current = true;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.6,
        skipProcessing: true,
        shutterSound: false,
      });
      setStats((s) => ({ ...s, frames: s.frames + 1 }));

      const verdict = await screenerRef.current.screen(photo);
      if (!verdict.pass) {
        setStatus(`初篩擋下（${verdict.detail}）`);
        return;
      }

      setStatus("上傳確認中…");
      setStats((s) => ({ ...s, uploads: s.uploads + 1 }));
      const res = await postDetect(settings, photo.uri);

      if (res.ok && res.fix) {
        setFix(res.fix);
        setStats((s) => ({ ...s, fixes: s.fixes + 1 }));
        setStatus(`已定位：${res.fix.node_name}`);
        addLog(
          `${res.fix.node_name}（數字 ${res.fix.digit}，${Math.round(res.fix.confidence * 100)}%）· ${res.inference_ms}ms`,
          "ok"
        );
      } else {
        setStatus(res.reason || "後端無結果");
        addLog(`未定位：${res.reason || "無結果"}`, "warn");
      }
    } catch (err) {
      setStatus(`錯誤：${err.message}`);
      addLog(err.message, "bad");
    } finally {
      busyRef.current = false;
    }
  }, [settings, addLog]);

  useEffect(() => {
    runningRef.current = running;
    if (!running) return;
    let cancelled = false;
    const loop = async () => {
      while (!cancelled && runningRef.current) {
        await tick();
        await new Promise((r) => setTimeout(r, Number(settings.intervalMs) || 1500));
      }
    };
    loop();
    return () => {
      cancelled = true;
    };
  }, [running, tick, settings.intervalMs]);

  const applySettings = async (next) => {
    setSettings(next);
    await saveSettings(next);
    screenerRef.current = createScreener({
      detailProxy: { threshold: Number(next.screenThreshold) || 2600 },
    });
  };

  if (!ready || !permission) {
    return (
      <View style={[styles.center, { backgroundColor: t.bg }]}>
        <ActivityIndicator color={t.accent} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={[styles.center, { backgroundColor: t.bg, padding: 28 }]}>
        <StatusBar style={scheme === "dark" ? "light" : "dark"} />
        <Text style={[styles.h1, { color: t.ink, textAlign: "center" }]}>
          需要相機權限
        </Text>
        <Text style={[styles.muted, { color: t.muted, textAlign: "center", marginTop: 8 }]}>
          這個 App 用相機辨識地板上的數字地標來判斷你的位置。
        </Text>
        <Pressable
          style={[styles.btn, { backgroundColor: t.accent, marginTop: 20 }]}
          onPress={requestPermission}
        >
          <Text style={styles.btnText}>授予權限</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: t.bg }]}>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />

      <View style={styles.cameraWrap}>
        <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />
        <View style={styles.reticle} pointerEvents="none">
          <View style={[styles.corner, styles.tl, { borderColor: t.accent }]} />
          <View style={[styles.corner, styles.tr, { borderColor: t.accent }]} />
          <View style={[styles.corner, styles.bl, { borderColor: t.accent }]} />
          <View style={[styles.corner, styles.br, { borderColor: t.accent }]} />
        </View>
        <View style={[styles.badge, { backgroundColor: t.panel + "e6" }]}>
          <Text style={[styles.badgeText, { color: t.ink }]}>
            {running ? "掃描中" : "已停止"} · {stats.frames} 幀 / {stats.uploads} 上傳 / {stats.fixes} 定位
          </Text>
        </View>
      </View>

      <View style={[styles.fixCard, { backgroundColor: t.panel, borderColor: t.line }]}>
        {fix ? (
          <>
            <Text style={[styles.label, { color: t.muted }]}>目前位置</Text>
            <Text style={[styles.h1, { color: t.ink }]}>{fix.node_name}</Text>
            <Text style={[styles.muted, { color: t.muted }]}>
              座標 ({fix.coordinate.x.toFixed(1)}, {fix.coordinate.y.toFixed(1)}) ·{" "}
              {fix.coordinate.floor}F · 信心 {Math.round(fix.confidence * 100)}%
            </Text>
          </>
        ) : (
          <>
            <Text style={[styles.label, { color: t.muted }]}>目前位置</Text>
            <Text style={[styles.h1, { color: t.muted }]}>尚未定位</Text>
          </>
        )}
        <Text style={[styles.status, { color: t.muted }]} numberOfLines={1}>
          {status}
        </Text>
      </View>

      <View style={styles.controls}>
        <Pressable
          style={[styles.btn, { backgroundColor: running ? t.line : t.accent, flex: 1 }]}
          onPress={() => setRunning((v) => !v)}
        >
          <Text style={[styles.btnText, running && { color: t.ink }]}>
            {running ? "停止" : "開始定位"}
          </Text>
        </Pressable>
        <Pressable
          style={[styles.btnGhost, { borderColor: t.line }]}
          onPress={checkHealth}
        >
          <Text style={[styles.btnGhostText, { color: t.ink }]}>測試後端</Text>
        </Pressable>
        <Pressable
          style={[styles.btnGhost, { borderColor: t.line }]}
          onPress={() => setShowSettings((v) => !v)}
        >
          <Text style={[styles.btnGhostText, { color: t.ink }]}>設定</Text>
        </Pressable>
      </View>

      {showSettings && (
        <View style={[styles.panel, { backgroundColor: t.panel, borderColor: t.line }]}>
          <Field label="後端位址" theme={t} value={settings.backendUrl}
                 onChange={(v) => applySettings({ ...settings, backendUrl: v })}
                 placeholder="http://192.168.x.x:8100" autoCapitalize="none" />
          <Field label="裝置 ID" theme={t} value={settings.deviceId}
                 onChange={(v) => applySettings({ ...settings, deviceId: v })} />
          <Field label="取樣間隔 (ms)" theme={t} value={String(settings.intervalMs)}
                 keyboardType="numeric"
                 onChange={(v) => applySettings({ ...settings, intervalMs: v })} />
          <Field label="初篩門檻" theme={t} value={String(settings.screenThreshold)}
                 keyboardType="numeric"
                 onChange={(v) => applySettings({ ...settings, screenThreshold: v })} />
          <Text style={[styles.hint, { color: t.muted }]}>
            初篩策略：{screenerRef.current ? screenerRef.current.describe() : "—"}
            {health ? `\n後端模型：${health.model}（${health.device}）` : ""}
          </Text>
        </View>
      )}

      <ScrollView style={styles.logWrap} contentContainerStyle={{ paddingBottom: 20 }}>
        {log.length === 0 ? (
          <Text style={[styles.hint, { color: t.muted }]}>尚無事件。</Text>
        ) : (
          log.map((e) => (
            <Text key={e.id} style={[styles.logLine, { color: logColor(e.kind, t) }]}>
              {e.at.toLocaleTimeString()} — {e.line}
            </Text>
          ))
        )}
      </ScrollView>
    </View>
  );
}

function Field({ label, value, onChange, theme, ...rest }) {
  return (
    <View style={{ marginBottom: 10 }}>
      <Text style={[styles.label, { color: theme.muted }]}>{label}</Text>
      <TextInput
        style={[styles.input, { color: theme.ink, borderColor: theme.line, backgroundColor: theme.bg }]}
        value={value}
        onChangeText={onChange}
        placeholderTextColor={theme.muted}
        {...rest}
      />
    </View>
  );
}

function logColor(kind, t) {
  if (kind === "ok") return t.ok;
  if (kind === "bad") return t.bad;
  if (kind === "warn") return t.warn;
  return t.muted;
}

const light = {
  bg: "#f7f5f2", panel: "#ffffff", ink: "#1c1917", muted: "#78716c",
  line: "#e7e2dc", accent: "#b4551f", ok: "#15803d", warn: "#b45309", bad: "#b91c1c",
};
const dark = {
  bg: "#16130f", panel: "#211d18", ink: "#f5f0ea", muted: "#a8a29e",
  line: "#37312a", accent: "#e2833f", ok: "#4ade80", warn: "#fbbf24", bad: "#f87171",
};

const styles = StyleSheet.create({
  root: { flex: 1, paddingTop: 48 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  cameraWrap: { height: "42%", marginHorizontal: 16, borderRadius: 16, overflow: "hidden" },
  reticle: { ...StyleSheet.absoluteFillObject, margin: "18%" },
  corner: { position: "absolute", width: 28, height: 28, borderWidth: 3 },
  tl: { top: 0, left: 0, borderRightWidth: 0, borderBottomWidth: 0 },
  tr: { top: 0, right: 0, borderLeftWidth: 0, borderBottomWidth: 0 },
  bl: { bottom: 0, left: 0, borderRightWidth: 0, borderTopWidth: 0 },
  br: { bottom: 0, right: 0, borderLeftWidth: 0, borderTopWidth: 0 },
  badge: { position: "absolute", left: 10, top: 10, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 99 },
  badgeText: { fontSize: 11, fontWeight: "600" },
  fixCard: { margin: 16, marginBottom: 8, padding: 16, borderRadius: 14, borderWidth: 1 },
  label: { fontSize: 11, textTransform: "uppercase", letterSpacing: 0.6, fontWeight: "600" },
  h1: { fontSize: 22, fontWeight: "700", marginTop: 4 },
  muted: { fontSize: 13, marginTop: 4 },
  status: { fontSize: 12, marginTop: 10 },
  controls: { flexDirection: "row", gap: 8, paddingHorizontal: 16 },
  btn: { paddingVertical: 12, paddingHorizontal: 18, borderRadius: 10, alignItems: "center" },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 15 },
  btnGhost: { paddingVertical: 12, paddingHorizontal: 14, borderRadius: 10, borderWidth: 1, justifyContent: "center" },
  btnGhostText: { fontWeight: "600", fontSize: 13 },
  panel: { margin: 16, marginBottom: 0, padding: 14, borderRadius: 14, borderWidth: 1 },
  input: { borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 14, marginTop: 4 },
  hint: { fontSize: 12, lineHeight: 18, paddingHorizontal: 4 },
  logWrap: { flex: 1, paddingHorizontal: 20, paddingTop: 12 },
  logLine: { fontSize: 12, paddingVertical: 3 },
});
