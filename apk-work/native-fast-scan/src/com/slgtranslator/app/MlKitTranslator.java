package com.slgtranslator.app;

import android.content.Context;

import com.getcapacitor.JSObject;
import com.getcapacitor.PluginCall;

import com.google.android.gms.tasks.Task;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.common.model.DownloadConditions;
import com.google.mlkit.common.model.RemoteModelManager;
import com.google.mlkit.nl.translate.TranslateLanguage;
import com.google.mlkit.nl.translate.TranslateRemoteModel;
import com.google.mlkit.nl.translate.Translation;
import com.google.mlkit.nl.translate.Translator;
import com.google.mlkit.nl.translate.TranslatorOptions;

import java.io.File;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Google ML Kit on-device translation engine (EN <-> ZH).
 *
 * The models are downloaded by ML Kit into the app's private storage on first
 * use (~30-60 MB total for both directions) and then work fully offline. ML
 * Kit is not a language model and cannot follow game-localization prompts, so
 * every text is translated literally with the stock engine; for higher
 * quality the app offers the llama.cpp LLM engine instead.
 */
public final class MlKitTranslator {

    private static final long DOWNLOAD_TIMEOUT_SECONDS = 15 * 60;
    private static final long TRANSLATE_TIMEOUT_SECONDS = 60;

    private static volatile boolean downloading = false;
    private static volatile String downloadState = "idle";

    private MlKitTranslator() {
    }

    /** Map the app language code to an ML Kit language constant. */
    public static String toMlKitLang(String lang) {
        if (lang == null) {
            return null;
        }
        String value = lang.trim().toLowerCase();
        if (value.equals("zh") || value.equals("zh-cn") || value.equals("zh-hans")
                || value.equals("cmn") || value.equals("chinese")) {
            return TranslateLanguage.CHINESE;
        }
        if (value.equals("en") || value.equals("english")) {
            return TranslateLanguage.ENGLISH;
        }
        if (value.equals("ja") || value.equals("japanese")) {
            return TranslateLanguage.JAPANESE;
        }
        if (value.equals("ko") || value.equals("korean")) {
            return TranslateLanguage.KOREAN;
        }
        return null;
    }

    public static boolean isDownloading() {
        return downloading;
    }

    public static String downloadState() {
        return downloadState;
    }

    static void markDownloadFailed(String message) {
        downloading = false;
        downloadState = "error:" + message;
    }

    private static TranslateRemoteModel remoteModel(String mlKitLang) {
        return new TranslateRemoteModel.Builder(mlKitLang).build();
    }

    /** Check whether a single language model is downloaded. */
    public static boolean isModelDownloaded(Context context, String lang) throws Exception {
        String mlKitLang = toMlKitLang(lang);
        if (mlKitLang == null) {
            return false;
        }
        try {
            Task<Boolean> task = RemoteModelManager.getInstance().isModelDownloaded(remoteModel(mlKitLang));
            return Boolean.TRUE.equals(Tasks.await(task, 20, TimeUnit.SECONDS));
        } catch (ExecutionException | TimeoutException e) {
            return false;
        }
    }

    /** Total bytes used by ML Kit models inside the app-private storage. */
    public static long modelBytes(Context context) {
        long total = 0;
        total += mlkitBytes(context.getFilesDir());
        total += mlkitBytes(context.getNoBackupFilesDir());
        return total;
    }

    /** Sum bytes of any directory whose name contains "mlkit" (the model
     * directory is com.google.mlkit.translate.models on this SDK). */
    private static long mlkitBytes(File parent) {
        if (parent == null || !parent.isDirectory()) {
            return 0;
        }
        long total = 0;
        File[] files = parent.listFiles();
        if (files == null) {
            return 0;
        }
        for (File file : files) {
            if (file.isDirectory() && file.getName().toLowerCase().contains("mlkit")) {
                total += dirBytes(file);
            }
        }
        return total;
    }

    private static long dirBytes(File dir) {
        if (dir == null || !dir.isDirectory()) {
            return 0;
        }
        long total = 0;
        File[] files = dir.listFiles();
        if (files == null) {
            return 0;
        }
        for (File file : files) {
            if (file.isFile()) {
                total += file.length();
            } else if (file.isDirectory()) {
                total += dirBytes(file);
            }
        }
        return total;
    }

    /** Download both direction models; emits progress while running. */
    public static void downloadModel(Context context, String sourceLang, String targetLang,
                                     LocalTranslationSupport.ProgressBridge progress,
                                     PluginCall call) throws Exception {
        String source = toMlKitLang(sourceLang);
        String target = toMlKitLang(targetLang);
        if (source == null || target == null) {
            throw new IllegalArgumentException(
                    "ML Kit 轻量翻译暂不支持该语言对（当前支持英文/中文，繁体请用高质量本地模型或云端 API）");
        }
        if (isModelDownloaded(context, sourceLang) && isModelDownloaded(context, targetLang)) {
            JSObject ok = new JSObject();
            ok.put("downloaded", true);
            ok.put("downloadedBytes", modelBytes(context));
            call.resolve(ok);
            return;
        }

        downloading = true;
        downloadState = "downloading";
        TranslatorOptions options = new TranslatorOptions.Builder()
                .setSourceLanguage(source)
                .setTargetLanguage(target)
                .build();
        Translator translator = Translation.getClient(options);
        try {
            Task<Void> task = translator.downloadModelIfNeeded(
                    new DownloadConditions.Builder().build());
            long deadline = System.currentTimeMillis() + DOWNLOAD_TIMEOUT_SECONDS * 1000;
            while (true) {
                long remaining = deadline - System.currentTimeMillis();
                if (remaining <= 0) {
                    throw new TimeoutException("下载本地翻译模型超时，请检查网络后重试");
                }
                try {
                    Tasks.await(task, Math.min(2, Math.max(1, remaining / 1000)), TimeUnit.SECONDS);
                    break;
                } catch (TimeoutException te) {
                    emitProgress(progress, true, context);
                    if (Thread.currentThread().isInterrupted()) {
                        throw new InterruptedException("下载已取消");
                    }
                }
            }
            boolean enReady = isModelDownloaded(context, "en");
            boolean zhReady = isModelDownloaded(context, "zh");
            downloadState = (enReady && zhReady) ? "downloaded" : "partial";
            emitProgress(progress, false, context);
            JSObject result = new JSObject();
            result.put("downloaded", enReady && zhReady);
            result.put("downloadedBytes", modelBytes(context));
            call.resolve(result);
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            throw new Exception(cause == null ? e.getMessage() : cause.getMessage());
        } finally {
            downloading = false;
            try {
                translator.close();
            } catch (Throwable ignored) {
            }
        }
    }

    private static void emitProgress(LocalTranslationSupport.ProgressBridge progress, boolean running, Context context) {
        try {
            JSObject data = new JSObject();
            data.put("kind", "mlkit");
            data.put("running", running);
            data.put("downloadedBytes", modelBytes(context));
            progress.emit("localDownloadProgress", data);
        } catch (Throwable ignored) {
        }
    }

    /** Delete downloaded ML Kit models through the official API. */
    public static long deleteModels(Context context) throws Exception {
        RemoteModelManager manager = RemoteModelManager.getInstance();
        for (String lang : new String[]{TranslateLanguage.ENGLISH, TranslateLanguage.CHINESE}) {
            try {
                Tasks.await(manager.deleteDownloadedModel(remoteModel(lang)), 30, TimeUnit.SECONDS);
            } catch (Exception ignored) {
                // The model may not exist; keep deleting.
            }
        }
        long freed = 0;
        freed += deleteMlkitDirs(context.getFilesDir());
        freed += deleteMlkitDirs(context.getNoBackupFilesDir());
        downloading = false;
        downloadState = "idle";
        return freed;
    }

    private static long deleteMlkitDirs(File parent) {
        if (parent == null || !parent.isDirectory()) {
            return 0;
        }
        long total = 0;
        File[] files = parent.listFiles();
        if (files == null) {
            return 0;
        }
        for (File file : files) {
            if (file.isDirectory() && file.getName().toLowerCase().contains("mlkit")) {
                total += deleteDir(file);
            }
        }
        return total;
    }

    private static long deleteDir(File dir) {
        if (dir == null || !dir.isDirectory()) {
            return 0;
        }
        long total = 0;
        File[] files = dir.listFiles();
        if (files == null) {
            return 0;
        }
        for (File file : files) {
            if (file.isDirectory()) {
                total += deleteDir(file);
            } else {
                total += file.length();
                file.delete();
            }
        }
        dir.delete();
        return total;
    }

    /** Translate a batch of texts sequentially with the ML Kit engine. */
    public static void translate(Context context, List<LocalTranslationSupport.TextItem> items,
                                 String sourceLang, String targetLang, PluginCall call) throws Exception {
        String source = toMlKitLang(sourceLang);
        String target = toMlKitLang(targetLang);
        if (source == null || target == null) {
            throw new IllegalArgumentException(
                    "ML Kit 轻量翻译暂不支持该语言对（当前支持英文/中文，繁体请用高质量本地模型或云端 API）");
        }
        if (items.isEmpty()) {
            JSObject empty = new JSObject();
            empty.put("translations", new JSObject());
            empty.put("count", 0);
            empty.put("warnings", LocalTranslationSupport.toJsonArray(new java.util.ArrayList<String>()));
            call.resolve(empty);
            return;
        }
        if (!isModelDownloaded(context, sourceLang) || !isModelDownloaded(context, targetLang)) {
            throw new IllegalStateException("本地翻译模型尚未下载，请先在“翻译服务”中下载轻量翻译模型");
        }

        TranslatorOptions options = new TranslatorOptions.Builder()
                .setSourceLanguage(source)
                .setTargetLanguage(target)
                .build();
        Translator translator = Translation.getClient(options);
        try {
            Tasks.await(translator.downloadModelIfNeeded(
                    new DownloadConditions.Builder().build()), DOWNLOAD_TIMEOUT_SECONDS, TimeUnit.SECONDS);

            JSObject translations = new JSObject();
            List<String> warnings = new java.util.ArrayList<>();
            int count = 0;
            int warned = 0;
            for (LocalTranslationSupport.TextItem item : items) {
                if (item.text == null || item.text.trim().length() == 0) {
                    continue;
                }
                try {
                    String translated = Tasks.await(translator.translate(item.text),
                            TRANSLATE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
                    if (translated == null || translated.trim().length() == 0) {
                        if (warned < 50) {
                            warnings.add(item.keyPath + ": 翻译结果为空，已跳过");
                            warned++;
                        }
                        continue;
                    }
                    if (translated.trim().equals(item.text.trim())) {
                        if (warned < 50) {
                            warnings.add(item.keyPath + ": 译文与原文相同（专有名词或无法识别文本）");
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
                if (Thread.currentThread().isInterrupted()) {
                    break;
                }
            }
            JSObject result = new JSObject();
            result.put("translations", translations);
            result.put("count", count);
            result.put("warnings", LocalTranslationSupport.toJsonArray(warnings));
            call.resolve(result);
        } finally {
            try {
                translator.close();
            } catch (Throwable ignored) {
            }
        }
    }
}
