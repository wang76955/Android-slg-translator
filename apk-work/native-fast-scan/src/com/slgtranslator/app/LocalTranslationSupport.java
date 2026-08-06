package com.slgtranslator.app;

import android.content.Context;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Capacitor bridge entry points for the on-device translation kernel.
 *
 * Two engines are exposed:
 *  - "mlkit": Google ML Kit on-device translation (fast, ~30-60 MB model,
 *    free, works offline after one download).
 *  - "llm": bundled llama.cpp runtime with a downloaded Qwen GGUF model
 *    (higher quality, slower, optional download ~1 GB).
 *
 * Every method runs its heavy work on a background thread so the Capacitor
 * call never blocks the WebView; the call is resolved/rejected when the work
 * finishes. Long-running downloads also emit "localDownloadProgress" events
 * through the FileManager plugin when it supports notifyListeners.
 */
public final class LocalTranslationSupport {

    private LocalTranslationSupport() {
    }

    /** Rejects ambiguous exact-old mappings before a translation artifact is compiled. */
    public static String translationCollisionConflict(List<String[]> pairs) {
        Map<String, String> translations = new LinkedHashMap<>();
        if (pairs == null) return null;
        for (String[] pair : pairs) {
            if (pair == null || pair.length < 2 || pair[0] == null) continue;
            String old = pair[0];
            String next = pair[1] == null ? "" : pair[1];
            if (translations.containsKey(old)) {
                String previous = translations.get(old);
                if (!previous.equals(next)) {
                    return "translation_collision_conflict: conflicting translations for exactOld '"
                            + old + "': '" + previous + "' vs '" + next + "'";
                }
            } else {
                translations.put(old, next);
            }
        }
        return null;
    }

    public static boolean hasTranslationCollision(List<String[]> pairs) {
        return translationCollisionConflict(pairs) != null;
    }

    /** A single translatable text item passed from the WebView. */
    public static final class TextItem {
        public final String keyPath;
        public final String text;

        public TextItem(String keyPath, String text) {
            this.keyPath = keyPath == null ? "" : keyPath;
            this.text = text == null ? "" : text;
        }
    }

    /** Query availability and storage state of both local engines. */
    public static void localStatus(Context context, PluginCall call) {
        try {
            JSObject result = new JSObject();

            JSObject mlkit = new JSObject();
            boolean enReady = MlKitTranslator.isModelDownloaded(context, "en");
            boolean zhReady = MlKitTranslator.isModelDownloaded(context, "zh");
            mlkit.put("supported", true);
            mlkit.put("downloaded", enReady && zhReady);
            mlkit.put("downloading", MlKitTranslator.isDownloading());
            mlkit.put("downloadState", MlKitTranslator.downloadState());
            mlkit.put("downloadedBytes", MlKitTranslator.modelBytes(context));
            result.put("mlkit", mlkit);

            JSObject llm = new JSObject();
            File model = LocalLlmEngine.modelFile(context);
            boolean installed = model.isFile() && model.length() > 0;
            llm.put("installed", installed);
            llm.put("modelPath", installed ? model.getAbsolutePath() : "");
            llm.put("sizeBytes", installed ? model.length() : 0L);
            llm.put("variant", LocalLlmEngine.currentVariant(context));
            llm.put("loading", LocalLlmEngine.isLoading());
            llm.put("downloading", LocalLlmEngine.isDownloading());
            llm.put("downloadedBytes", LocalLlmEngine.downloadBytes());
            llm.put("totalBytes", LocalLlmEngine.downloadTotal());
            result.put("llm", llm);

            call.resolve(result);
        } catch (Throwable t) {
            call.reject("查询本地翻译状态失败: " + safeMessage(t));
        }
    }

    /**
     * Download the ML Kit EN<->ZH models (both directions share the same
     * language models, so one download enables en->zh and zh->en).
     */
    public static void localDownload(Context context, Object plugin, PluginCall call) {
        final String sourceLang = firstNonEmpty(call.getString("sourceLang"), "en");
        final String targetLang = firstNonEmpty(call.getString("targetLang"), "zh");
        new Thread(() -> {
            try {
                MlKitTranslator.downloadModel(context, sourceLang, targetLang,
                        new ProgressBridge(plugin), call);
            } catch (Throwable t) {
                MlKitTranslator.markDownloadFailed(safeMessage(t));
                call.reject("下载本地翻译模型失败: " + safeMessage(t));
            }
        }, "slg-mlkit-download").start();
    }

    /** Delete the ML Kit downloaded models to free storage. */
    public static void mlkitDelete(Context context, PluginCall call) {
        new Thread(() -> {
            try {
                long freed = MlKitTranslator.deleteModels(context);
                JSObject result = new JSObject();
                result.put("deleted", true);
                result.put("freedBytes", freed);
                call.resolve(result);
            } catch (Throwable t) {
                call.reject("删除 ML Kit 模型失败: " + safeMessage(t));
            }
        }, "slg-mlkit-delete").start();
    }

    /** Translate a batch of texts with the selected local engine. */
    public static void translateLocal(Context context, PluginCall call) {
        String engine = firstNonEmpty(call.getString("engine"), "mlkit");
        String sourceLang = firstNonEmpty(call.getString("sourceLang"), "en");
        String targetLang = firstNonEmpty(call.getString("targetLang"), "zh");
        List<TextItem> items = parseTexts(call);
        new Thread(() -> {
            try {
                if ("llm".equalsIgnoreCase(engine)) {
                    LocalLlmEngine.translate(context, items, sourceLang, targetLang, call);
                } else {
                    MlKitTranslator.translate(context, items, sourceLang, targetLang, call);
                }
            } catch (Throwable t) {
                call.reject("本地翻译失败: " + safeMessage(t));
            }
        }, "slg-local-translate").start();
    }

    /** Download the Qwen GGUF model used by the LLM engine. */
    public static void llmDownload(Context context, Object plugin, PluginCall call) {
        String variant = firstNonEmpty(call.getString("variant"), LocalLlmEngine.DEFAULT_VARIANT);
        new Thread(() -> {
            try {
                LocalLlmEngine.downloadModel(context, variant, new ProgressBridge(plugin), call);
            } catch (Throwable t) {
                call.reject("下载本地大模型失败: " + safeMessage(t));
            }
        }, "slg-llm-download").start();
    }

    /** Delete the downloaded GGUF model to free storage. */
    public static void llmDelete(Context context, PluginCall call) {
        new Thread(() -> {
            try {
                long freed = LocalLlmEngine.deleteModel(context);
                JSObject result = new JSObject();
                result.put("deleted", true);
                result.put("freedBytes", freed);
                call.resolve(result);
            } catch (Throwable t) {
                call.reject("删除本地大模型失败: " + safeMessage(t));
            }
        }, "slg-llm-delete").start();
    }

    private static List<TextItem> parseTexts(PluginCall call) {
        List<TextItem> items = new ArrayList<>();
        try {
            JSONArray array = call.getArray("texts");
            if (array == null) {
                return items;
            }
            for (int i = 0; i < array.length(); i++) {
                JSONObject object = array.getJSONObject(i);
                if (object == null) {
                    continue;
                }
                String keyPath = object.optString("keyPath", "");
                String text = object.optString("text", "");
                if (keyPath.length() == 0 && text.length() == 0) {
                    continue;
                }
                items.add(new TextItem(keyPath, text));
            }
        } catch (Throwable t) {
            // Partial input is still usable; return what parsed.
        }
        return items;
    }

    static String firstNonEmpty(String value, String fallback) {
        return value == null || value.trim().length() == 0 ? fallback : value.trim();
    }

    static String safeMessage(Throwable t) {
        if (t == null) {
            return "未知错误";
        }
        String message = t.getMessage();
        return message == null || message.length() == 0 ? t.toString() : message;
    }

    /** Convert a warning list into a JSONArray so Capacitor serializes it as
     * a real JS array instead of a Java object reference string. */
    static org.json.JSONArray toJsonArray(List<String> warnings) {
        org.json.JSONArray array = new org.json.JSONArray();
        for (String warning : warnings) {
            array.put(warning);
        }
        return array;
    }

    /**
     * Small adapter that forwards download progress to the Capacitor plugin
     * listeners through reflection (the build stubs do not expose Plugin).
     */
    static final class ProgressBridge {
        private final Object plugin;

        ProgressBridge(Object plugin) {
            this.plugin = plugin;
        }

        void emit(String event, JSObject data) {
            if (plugin == null) {
                return;
            }
            try {
                Method method = plugin.getClass().getMethod("notifyListeners", String.class, JSObject.class);
                method.invoke(plugin, event, data);
            } catch (Throwable ignored) {
                // Progress events are best-effort; the polling status API is
                // the reliable path.
            }
        }
    }
}
