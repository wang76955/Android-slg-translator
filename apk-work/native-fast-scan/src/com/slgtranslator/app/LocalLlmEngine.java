package com.slgtranslator.app;

import android.content.Context;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import dev.ffmpegkit.llama.Llama;
import dev.ffmpegkit.llama.LlamaConfig;
import dev.ffmpegkit.llama.LlamaModel;
import dev.ffmpegkit.llama.LlamaResult;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import kotlin.coroutines.Continuation;
import kotlin.coroutines.CoroutineContext;
import kotlin.coroutines.EmptyCoroutineContext;

/**
 * Local LLM translation engine powered by the bundled llama.cpp runtime.
 *
 * The model is a quantized Qwen2.5 Instruct GGUF file that the user downloads
 * once (~1 GB for 1.5B Q4_K_M, or ~470 MB for the smaller 0.5B used for
 * testing) into the app's external files directory. Every text is translated
 * with a dedicated localization prompt and a fresh completion so earlier
 * items never pollute later ones.
 */
public final class LocalLlmEngine {

    static final String DEFAULT_VARIANT = "1.5b";
    private static final String MODELS_DIR = "models";
    private static final String VARIANT_MARKER = "variant.txt";

    private static final long DOWNLOAD_CHUNK_BYTES = 256 * 1024;
    private static final long DOWNLOAD_PROGRESS_INTERVAL_MS = 1500;
    private static final long COMPLETE_TIMEOUT_SECONDS = 300;
    private static final int MAX_TOKENS = 512;

    private static volatile LlamaModel loadedModel;
    private static volatile String loadedModelPath;
    private static volatile boolean loading = false;
    private static volatile boolean downloading = false;
    private static volatile long downloadBytes = 0;
    private static volatile long downloadTotal = 0;

    private LocalLlmEngine() {
    }

    public static boolean isLoading() {
        return loading;
    }

    public static boolean isDownloading() {
        return downloading;
    }

    public static long downloadBytes() {
        return downloadBytes;
    }

    public static long downloadTotal() {
        return downloadTotal;
    }

    /** The model file used by the LLM engine. */
    public static File modelFile(Context context) {
        File dir = context.getExternalFilesDir(MODELS_DIR);
        return dir == null ? new File(context.getFilesDir(), MODELS_DIR + "/model.gguf")
                : new File(dir, installedFileName(context));
    }

    private static String installedFileName(Context context) {
        String variant = currentVariant(context);
        return variant.equals("0.5b") ? "qwen2.5-0.5b-instruct-q4_k_m.gguf"
                : "qwen2.5-1.5b-instruct-q4_k_m.gguf";
    }

    /** Which model variant is currently installed (defaults to 1.5b). */
    public static String currentVariant(Context context) {
        File dir = context.getExternalFilesDir(MODELS_DIR);
        if (dir != null) {
            File marker = new File(dir, VARIANT_MARKER);
            if (marker.isFile()) {
                try {
                    String value = readSmallFile(marker).trim();
                    if (value.equals("0.5b") || value.equals("1.5b")) {
                        return value;
                    }
                } catch (Throwable ignored) {
                }
            }
            if (new File(dir, "qwen2.5-0.5b-instruct-q4_k_m.gguf").isFile()) {
                return "0.5b";
            }
            if (new File(dir, "qwen2.5-1.5b-instruct-q4_k_m.gguf").isFile()) {
                return "1.5b";
            }
        }
        return DEFAULT_VARIANT;
    }

    private static String modelUrl(String variant) {
        if (variant.equals("0.5b")) {
            return "https://hf-mirror.com/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf";
        }
        return "https://hf-mirror.com/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf";
    }

    private static long expectedSize(String variant) {
        return variant.equals("0.5b") ? 491400032L : 1117320736L;
    }

    private static String readSmallFile(File file) throws Exception {
        java.io.FileInputStream in = new java.io.FileInputStream(file);
        try {
            byte[] buffer = new byte[(int) Math.min(file.length(), 64)];
            int read = in.read(buffer);
            return new String(buffer, 0, Math.max(0, read), "UTF-8");
        } finally {
            in.close();
        }
    }

    /** Download and verify the GGUF model; emits progress while running. */
    public static void downloadModel(Context context, String variant,
                                     LocalTranslationSupport.ProgressBridge progress,
                                     PluginCall call) throws Exception {
        if (!variant.equals("0.5b") && !variant.equals("1.5b")) {
            throw new IllegalArgumentException("未知模型规格: " + variant);
        }
        File dir = context.getExternalFilesDir(MODELS_DIR);
        if (dir == null) {
            dir = new File(context.getFilesDir(), MODELS_DIR);
        }
        if (!dir.isDirectory() && !dir.mkdirs()) {
            throw new Exception("无法创建模型目录");
        }
        String fileName = variant.equals("0.5b")
                ? "qwen2.5-0.5b-instruct-q4_k_m.gguf"
                : "qwen2.5-1.5b-instruct-q4_k_m.gguf";
        File target = new File(dir, fileName);
        long expected = expectedSize(variant);
        if (target.isFile() && target.length() == expected) {
            writeVariantMarker(dir, variant);
            JSObject ok = new JSObject();
            ok.put("modelPath", target.getAbsolutePath());
            ok.put("sizeBytes", target.length());
            ok.put("variant", variant);
            call.resolve(ok);
            return;
        }
        // Remove a stale model of the other variant so only one is kept.
        File other = new File(dir, variant.equals("0.5b")
                ? "qwen2.5-1.5b-instruct-q4_k_m.gguf"
                : "qwen2.5-0.5b-instruct-q4_k_m.gguf");
        if (other.isFile()) {
            releaseLoadedModel();
            other.delete();
        }

        String url = modelUrl(variant);
        File part = new File(dir, fileName + ".part");
        downloading = true;
        downloadBytes = 0;
        downloadTotal = expected;
        HttpURLConnection connection = null;
        InputStream input = null;
        OutputStream output = null;
        try {
            connection = openConnection(url);
            int code = connection.getResponseCode();
            if (code / 100 != 2) {
                throw new Exception("模型下载失败（HTTP " + code + "），请稍后重试");
            }
            long total = connection.getContentLengthLong();
            if (total > 0 && expected > 0 && total != expected) {
                total = expected;
            }
            downloadTotal = total > 0 ? total : expected;
            input = connection.getInputStream();
            output = new FileOutputStream(part);
            byte[] buffer = new byte[(int) DOWNLOAD_CHUNK_BYTES];
            long downloaded = 0;
            long lastEmit = 0;
            while (true) {
                int read = input.read(buffer);
                if (read < 0) {
                    break;
                }
                output.write(buffer, 0, read);
                downloaded += read;
                downloadBytes = downloaded;
                long now = System.currentTimeMillis();
                if (now - lastEmit >= DOWNLOAD_PROGRESS_INTERVAL_MS) {
                    lastEmit = now;
                    emitProgress(progress, variant, downloaded, total);
                }
                if (Thread.currentThread().isInterrupted()) {
                    throw new InterruptedException("下载已取消");
                }
            }
            output.flush();
            output.close();
            output = null;
            input.close();
            input = null;
            connection.disconnect();
            connection = null;

            if (expected > 0 && part.length() != expected) {
                throw new Exception("模型文件不完整（大小 " + part.length() + "，应为 " + expected + "），请重试");
            }
            if (!hasGgufMagic(part)) {
                throw new Exception("模型文件校验失败，请重试");
            }
            if (!part.renameTo(target)) {
                throw new Exception("模型文件保存失败");
            }
            writeVariantMarker(dir, variant);
            emitProgress(progress, variant, expected, expected);
            JSObject result = new JSObject();
            result.put("modelPath", target.getAbsolutePath());
            result.put("sizeBytes", target.length());
            result.put("variant", variant);
            call.resolve(result);
        } finally {
            downloading = false;
            if (output != null) {
                try {
                    output.close();
                } catch (Throwable ignored) {
                }
            }
            if (input != null) {
                try {
                    input.close();
                } catch (Throwable ignored) {
                }
            }
            if (connection != null) {
                connection.disconnect();
            }
            if (part.exists() && !target.exists()) {
                part.delete();
            }
        }
    }

    private static void writeVariantMarker(File dir, String variant) throws Exception {
        File marker = new File(dir, VARIANT_MARKER);
        java.io.FileOutputStream out = new java.io.FileOutputStream(marker);
        try {
            out.write(variant.getBytes("UTF-8"));
        } finally {
            out.close();
        }
    }

    private static HttpURLConnection openConnection(String url) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setInstanceFollowRedirects(true);
        connection.setConnectTimeout(30000);
        connection.setReadTimeout(60000);
        connection.setRequestProperty("User-Agent", "SLG-Translator/1.0");
        connection.connect();
        int code = connection.getResponseCode();
        if (code / 100 == 3) {
            String location = connection.getHeaderField("Location");
            connection.disconnect();
            if (location == null || location.length() == 0) {
                throw new Exception("模型下载重定向无效");
            }
            return openConnection(location);
        }
        return connection;
    }

    private static boolean hasGgufMagic(File file) throws Exception {
        java.io.FileInputStream in = new java.io.FileInputStream(file);
        try {
            byte[] magic = new byte[4];
            int read = in.read(magic);
            return read == 4 && magic[0] == 'G' && magic[1] == 'G' && magic[2] == 'U' && magic[3] == 'F';
        } finally {
            in.close();
        }
    }

    private static void emitProgress(LocalTranslationSupport.ProgressBridge progress,
                                     String variant, long downloaded, long total) {
        try {
            JSObject data = new JSObject();
            data.put("kind", "llm");
            data.put("variant", variant);
            data.put("downloadedBytes", downloaded);
            data.put("totalBytes", total);
            data.put("percent", total > 0 ? (int) (downloaded * 100 / total) : -1);
            progress.emit("localDownloadProgress", data);
        } catch (Throwable ignored) {
        }
    }

    /** Release the loaded model and delete the downloaded GGUF file. */
    public static long deleteModel(Context context) throws Exception {
        releaseLoadedModel();
        downloading = false;
        downloadBytes = 0;
        downloadTotal = 0;
        File dir = context.getExternalFilesDir(MODELS_DIR);
        long freed = 0;
        if (dir != null && dir.isDirectory()) {
            File[] files = dir.listFiles();
            if (files != null) {
                for (File file : files) {
                    if (file.isFile()) {
                        freed += file.length();
                        file.delete();
                    }
                }
            }
            dir.delete();
        }
        return freed;
    }

    private static synchronized void releaseLoadedModel() {
        LlamaModel model = loadedModel;
        loadedModel = null;
        loadedModelPath = null;
        if (model != null && model.isLoaded()) {
            try {
                Llama.INSTANCE.releaseModel(model);
            } catch (Throwable ignored) {
            }
        }
    }

    /** Translate a batch with the local LLM, one fresh completion per item. */
    public static void translate(Context context, List<LocalTranslationSupport.TextItem> items,
                                 String sourceLang, String targetLang, PluginCall call) throws Exception {
        File modelFile = modelFile(context);
        if (!modelFile.isFile() || modelFile.length() == 0) {
            throw new IllegalStateException("高质量本地模型尚未下载，请先在“翻译服务”中下载（约 1GB）");
        }
        if (items.isEmpty()) {
            JSObject empty = new JSObject();
            empty.put("translations", new JSObject());
            empty.put("count", 0);
            empty.put("warnings", LocalTranslationSupport.toJsonArray(new java.util.ArrayList<String>()));
            call.resolve(empty);
            return;
        }

        LlamaModel model = getLoadedModel(modelFile.getAbsolutePath());
        String systemPrompt = buildSystemPrompt(sourceLang, targetLang);
        JSObject translations = new JSObject();
        List<String> warnings = new java.util.ArrayList<>();
        int count = 0;
        int warned = 0;
        for (LocalTranslationSupport.TextItem item : items) {
            if (item.text == null || item.text.trim().length() == 0) {
                continue;
            }
            if (Thread.currentThread().isInterrupted()) {
                break;
            }
            try {
                LlamaResult result = completeSync(model, item.text, systemPrompt, MAX_TOKENS);
                String translated = cleanOutput(result.getText());
                if (translated == null || translated.length() == 0) {
                    if (warned < 50) {
                        warnings.add(item.keyPath + ": 本地模型未生成译文，已跳过");
                        warned++;
                    }
                    continue;
                }
                if (translated.equals(item.text.trim())) {
                    if (warned < 50) {
                        warnings.add(item.keyPath + ": 译文与原文相同，已跳过");
                        warned++;
                    }
                    continue;
                }
                translations.put(item.keyPath, translated);
                count++;
            } catch (Exception e) {
                if (warned < 50) {
                    warnings.add(item.keyPath + ": 翻译失败 - "
                            + LocalTranslationSupport.safeMessage(e));
                    warned++;
                }
            }
        }
        JSObject result = new JSObject();
        result.put("translations", translations);
        result.put("count", count);
        result.put("warnings", LocalTranslationSupport.toJsonArray(warnings));
        result.put("engine", "llm");
        call.resolve(result);
    }

    private static synchronized LlamaModel getLoadedModel(String path) throws Exception {
        if (loadedModel != null && loadedModel.isLoaded() && path.equals(loadedModelPath)) {
            return loadedModel;
        }
        releaseLoadedModel();
        loading = true;
        try {
            int threads = Math.max(2, Math.min(4, Runtime.getRuntime().availableProcessors() - 1));
            LlamaConfig config = new LlamaConfig(2048, threads, 0, 0.2f, 0.95f, 40, -1);
            LlamaModel model = loadModelSync(path, config);
            loadedModel = model;
            loadedModelPath = path;
            return model;
        } finally {
            loading = false;
        }
    }

    private static LlamaModel loadModelSync(String path, LlamaConfig config) throws Exception {
        final Object[] box = new Object[1];
        final CountDownLatch latch = new CountDownLatch(1);
        Continuation<LlamaModel> continuation = new Continuation<LlamaModel>() {
            @Override
            public CoroutineContext getContext() {
                return EmptyCoroutineContext.INSTANCE;
            }

            @Override
            public void resumeWith(Object result) {
                box[0] = result;
                latch.countDown();
            }
        };
        Llama.INSTANCE.loadModel(path, config, continuation);
        if (!latch.await(COMPLETE_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
            throw new java.util.concurrent.TimeoutException("加载本地模型超时（内存不足或模型损坏）");
        }
        return (LlamaModel) unpackResult(box[0]);
    }

    private static LlamaResult completeSync(LlamaModel model, String prompt,
                                            String systemPrompt, int maxTokens) throws Exception {
        final Object[] box = new Object[1];
        final CountDownLatch latch = new CountDownLatch(1);
        Continuation<LlamaResult> continuation = new Continuation<LlamaResult>() {
            @Override
            public CoroutineContext getContext() {
                return EmptyCoroutineContext.INSTANCE;
            }

            @Override
            public void resumeWith(Object result) {
                box[0] = result;
                latch.countDown();
            }
        };
        Llama.INSTANCE.complete(model, prompt, systemPrompt, maxTokens, continuation);
        if (!latch.await(COMPLETE_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
            throw new java.util.concurrent.TimeoutException("本地模型推理超时");
        }
        return (LlamaResult) unpackResult(box[0]);
    }

    private static Object unpackResult(Object result) throws Exception {
        if (result instanceof kotlin.Result.Failure) {
            Throwable cause = ((kotlin.Result.Failure) result).exception;
            throw new Exception(cause == null ? "本地模型执行失败" : cause.getMessage());
        }
        if (result == null) {
            throw new Exception("本地模型返回空结果");
        }
        return result;
    }

    private static String buildSystemPrompt(String sourceLang, String targetLang) {
        return "You are a professional game localization translator for visual novels. "
                + "Translate the following " + langName(sourceLang) + " text into "
                + langName(targetLang) + ". "
                + "Make it natural, match the tone of the original, and localize idioms. "
                + "Preserve placeholders and markup exactly (like %s, {name}, <b>). "
                + "Output ONLY the translation. No quotes, no explanations, no notes.";
    }

    private static String langName(String lang) {
        if (lang == null) {
            return "the target language";
        }
        String value = lang.trim().toLowerCase();
        if (value.startsWith("zh")) {
            if (value.contains("tw") || value.contains("hant") || value.contains("trad")) {
                return "Traditional Chinese";
            }
            return "Simplified Chinese";
        }
        if (value.equals("ja") || value.equals("japanese")) {
            return "Japanese";
        }
        if (value.equals("ko") || value.equals("korean")) {
            return "Korean";
        }
        return "English";
    }

    private static String cleanOutput(String text) {
        if (text == null) {
            return null;
        }
        String value = text.trim();
        // Strip a possible leading "Translation:" style prefix.
        int colon = value.indexOf(':');
        if (colon > 0 && colon < 20 && !value.contains("\n")) {
            String prefix = value.substring(0, colon).toLowerCase();
            if (prefix.contains("translation") || prefix.contains("译文") || prefix.contains("翻译")) {
                value = value.substring(colon + 1).trim();
            }
        }
        // Strip wrapping quotes the model may add.
        while (value.length() >= 2) {
            char first = value.charAt(0);
            char last = value.charAt(value.length() - 1);
            if ((first == '"' && last == '"') || (first == '\u201c' && last == '\u201d')
                    || (first == '\u2018' && last == '\u2019') || (first == '\'' && last == '\'')) {
                value = value.substring(1, value.length() - 1).trim();
            } else {
                break;
            }
        }
        return value.length() == 0 ? null : value;
    }
}
