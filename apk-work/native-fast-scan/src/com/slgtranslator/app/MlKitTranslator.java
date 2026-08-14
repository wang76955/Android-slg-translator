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
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
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
    private static final Pattern SENTINEL = Pattern.compile("__SLGPH\\d+__");
    private static final Pattern DOT_RUN = Pattern.compile("\\.{2,}");
    private static final Pattern EXCLAMATION_RUN = Pattern.compile("!{2,}");
    private static final Pattern QUESTION_RUN = Pattern.compile("\\?{2,}");

    private static volatile boolean downloading = false;
    private static volatile String downloadState = "idle";

    private static final Object TRANSLATOR_LOCK = new Object();
    private static Translator sharedTranslator = null;
    private static String sharedSource = null;
    private static String sharedTarget = null;

    interface SegmentTranslator {
        String translate(String text) throws Exception;
    }

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
        resetSharedTranslator();
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

    /** Reuse one ML Kit Translator for the same language pair so every batch
     * does not pay model loading again. Callers must hold TRANSLATOR_LOCK.
     */
    private static Translator getSharedTranslator(Context context, String sourceLang, String targetLang) throws Exception {
        String source = toMlKitLang(sourceLang);
        String target = toMlKitLang(targetLang);
        if (source == null || target == null) {
            throw new IllegalArgumentException(
                    "ML Kit 轻量翻译暂不支持该语言对（当前支持英文/中文，繁体请用高质量本地模型或云端 API）");
        }
        if (sharedTranslator != null && source.equals(sharedSource) && target.equals(sharedTarget)) {
            return sharedTranslator;
        }
        if (!isModelDownloaded(context, sourceLang) || !isModelDownloaded(context, targetLang)) {
            throw new IllegalStateException("本地翻译模型尚未下载，请先在“翻译服务”中下载轻量翻译模型");
        }
        if (sharedTranslator != null) {
            try {
                sharedTranslator.close();
            } catch (Throwable ignored) {
            }
            sharedTranslator = null;
        }
        TranslatorOptions options = new TranslatorOptions.Builder()
                .setSourceLanguage(source)
                .setTargetLanguage(target)
                .build();
        Translator translator = Translation.getClient(options);
        try {
            Tasks.await(translator.downloadModelIfNeeded(
                    new DownloadConditions.Builder().build()), DOWNLOAD_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (Throwable e) {
            try {
                translator.close();
            } catch (Throwable ignored) {
            }
            throw e;
        }
        sharedTranslator = translator;
        sharedSource = source;
        sharedTarget = target;
        return sharedTranslator;
    }

    /** Close the shared translator, e.g. after models are deleted. */
    public static void releaseSharedTranslator() {
        synchronized (TRANSLATOR_LOCK) {
            if (sharedTranslator != null) {
                try {
                    sharedTranslator.close();
                } catch (Throwable ignored) {
                }
                sharedTranslator = null;
            }
            sharedSource = null;
            sharedTarget = null;
        }
    }

    /** Backward-compatible internal alias used by model deletion. */
    static void resetSharedTranslator() {
        releaseSharedTranslator();
    }

    /** Translate only ordinary text fragments, leaving Ren'Py sentinels intact. */
    static String translateProtectedText(String protectedText,
                                         SegmentTranslator segmentTranslator) throws Exception {
        if (protectedText == null || segmentTranslator == null) {
            return null;
        }
        Matcher matcher = SENTINEL.matcher(protectedText);
        StringBuilder result = new StringBuilder(protectedText.length());
        int last = 0;
        while (matcher.find()) {
            String fragment = protectedText.substring(last, matcher.start());
            String translated = translateFragment(fragment, segmentTranslator);
            if (translated == null) {
                return null;
            }
            result.append(translated).append(matcher.group());
            last = matcher.end();
        }
        String tail = translateFragment(protectedText.substring(last), segmentTranslator);
        if (tail == null) {
            return null;
        }
        result.append(tail);
        return result.toString();
    }

    /** True when protected text contains no translatable letters outside sentinels. */
    static boolean isNonTranslatableProtectedText(String protectedText) {
        if (protectedText == null || protectedText.length() == 0) {
            return true;
        }
        Matcher matcher = SENTINEL.matcher(protectedText);
        int last = 0;
        while (matcher.find()) {
            if (containsTranslatableLetters(protectedText.substring(last, matcher.start()))) {
                return false;
            }
            last = matcher.end();
        }
        return !containsTranslatableLetters(protectedText.substring(last));
    }

    /** Normalize punctuation once when ML Kit echoes a sentence unchanged. */
    static String normalizeForMlKit(String text) {
        if (text == null || text.length() == 0) {
            return text;
        }
        return QUESTION_RUN.matcher(
                EXCLAMATION_RUN.matcher(DOT_RUN.matcher(text).replaceAll(".")).replaceAll("!")
        ).replaceAll("?");
    }

    private static String translateFragment(String fragment,
                                            SegmentTranslator segmentTranslator) throws Exception {
        if (fragment == null || fragment.length() == 0 || !containsTranslatableLetters(fragment)) {
            return fragment;
        }
        int start = 0;
        int end = fragment.length();
        while (start < end && Character.isWhitespace(fragment.charAt(start))) {
            start++;
        }
        while (end > start && Character.isWhitespace(fragment.charAt(end - 1))) {
            end--;
        }
        if (start >= end) {
            return fragment;
        }
        String leading = fragment.substring(0, start);
        String core = fragment.substring(start, end);
        String trailing = fragment.substring(end);
        String translated = requestFragment(core, segmentTranslator);
        if (translated == null || translated.trim().length() == 0) {
            return null;
        }
        return leading + translated.trim() + trailing;
    }

    private static String requestFragment(String fragment,
                                           SegmentTranslator segmentTranslator) throws Exception {
        String translated = segmentTranslator.translate(fragment);
        if (translated != null && translated.trim().length() > 0
                && !translated.trim().equals(fragment.trim())) {
            return translated;
        }
        String normalized = normalizeForMlKit(fragment);
        if (!normalized.equals(fragment)) {
            String retry = segmentTranslator.translate(normalized);
            if (retry != null && retry.trim().length() > 0
                    && !retry.trim().equals(normalized.trim())) {
                return retry;
            }
            if (translated == null || translated.trim().length() == 0) {
                return retry;
            }
        }
        return translated;
    }

    private static boolean containsTranslatableLetters(String text) {
        for (int i = 0; i < text.length(); i++) {
            char value = text.charAt(i);
            if ((value >= 'A' && value <= 'Z') || (value >= 'a' && value <= 'z')) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------
    // ML Kit echo resolution.
    //
    // ML Kit is a sentence NMT engine: short interjections, onomatopoeia,
    // character names and ritual phrases are echoed back unchanged (often
    // only with full-width punctuation). The stock accept check rejects
    // identical echoes so untranslated text can never be shipped silently,
    // but that turns an engine limitation into a coverage blocker. This
    // layer resolves echoes that are safe to translate deterministically:
    // a curated fallback dictionary + scream normalization + a visible
    // pass-through for text that is already non-English script.
    // Unresolved echoes keep rejecting (visible warning, missing coverage).
    // ------------------------------------------------------------------

    private static final Pattern RENPY_TAG = Pattern.compile("\\{[^{}]*\\}");

    /** Ren'Py tags and interpolation placeholders: protected during echo fallback. */
    private static final Pattern RENPY_PROTECTED = Pattern.compile("\\{[^{}]*\\}|\\[[^\\[\\]]*\\]");

    private static final Map<String, String> ECHO_FALLBACK = new HashMap<String, String>();
    static {
        ECHO_FALLBACK.put("fuck", "操");
        ECHO_FALLBACK.put("ehem", "嗯哼");
        ECHO_FALLBACK.put("chiara", "琪亚拉");
        ECHO_FALLBACK.put("gillie", "吉利");
        ECHO_FALLBACK.put("eep", "呀");
        ECHO_FALLBACK.put("thwock", "砰");
        ECHO_FALLBACK.put("wha", "什");
        ECHO_FALLBACK.put("w什么", "什……什么");
        ECHO_FALLBACK.put("嘿,eshtel", "嘿，艾什特尔");
        ECHO_FALLBACK.put("sema tomi al saamaselam", "塞玛·托米·阿尔·萨马塞拉姆");
        ECHO_FALLBACK.put("ishani a'gradi al vashi samako", "伊沙妮·阿格拉迪·阿尔·瓦希·萨马科");
        ECHO_FALLBACK.put("alrighty", "好嘞");
        ECHO_FALLBACK.put("dafuq", "什么鬼");
        ECHO_FALLBACK.put("druthari", "德鲁萨里");
        ECHO_FALLBACK.put("saarya", "萨里亚");
        ECHO_FALLBACK.put("mmh", "嗯");
        ECHO_FALLBACK.put("evie clements", "伊维·克莱门茨");
        ECHO_FALLBACK.put("ne", "呢");
        ECHO_FALLBACK.put("serious", "认真的");
        ECHO_FALLBACK.put("（beeeeeeeeeeeeeep）", "（哔——）");
        ECHO_FALLBACK.put("（flapflapflapflapflapflap）", "（扑棱扑棱扑棱扑棱扑棱扑棱）");
        ECHO_FALLBACK.put("（whrrrrrrrrrrrrrrr）", "（嗡——）");
        ECHO_FALLBACK.put("fucking", "他妈的");
        ECHO_FALLBACK.put("interloper", "闯入者");
        ECHO_FALLBACK.put("so can you just", "所以你能不能就");
        ECHO_FALLBACK.put("y'know", "你知道的");
        ECHO_FALLBACK.put("are also the most dangerous", "也是最危险的");
        ECHO_FALLBACK.put("bawk", "嘎");
        ECHO_FALLBACK.put("sai halane dema", "赛·哈拉内·德马");
        ECHO_FALLBACK.put("al mishai", "阿尔·米沙伊");
        ECHO_FALLBACK.put("al saamase-lam", "阿尔·萨马塞-拉姆");
        ECHO_FALLBACK.put("alule na amai al aluka", "阿鲁莱·纳·阿迈·阿尔·阿卢卡");
        ECHO_FALLBACK.put("etha alai thaya na vele,al veia moratsai", "埃萨·阿莱·塔亚·纳·韦莱，阿尔·维亚·莫拉赛");
        ECHO_FALLBACK.put("ia vai belelende", "伊亚·瓦伊·贝莱伦德");
        ECHO_FALLBACK.put("jiga madi ashagari al hashesh", "吉加·马迪·阿沙加里·阿尔·哈谢什");
        ECHO_FALLBACK.put("kai'e a'wari dema", "凯耶·阿瓦里·德马");
        ECHO_FALLBACK.put("cha jiga,rogasai al veiasshi alai soli", "查·吉加，罗加赛·阿尔·维亚希·阿莱·索利");
        ECHO_FALLBACK.put("ishani", "伊沙尼");
        ECHO_FALLBACK.put("chiara begins to sing", "琪亚拉开始唱歌");
        ECHO_FALLBACK.put("after you get home", "你到家之后");
        ECHO_FALLBACK.put("gimme", "给我");
        ECHO_FALLBACK.put("mhm", "嗯哼");
        ECHO_FALLBACK.put("hmph", "哼");
        ECHO_FALLBACK.put("f", "操");
        ECHO_FALLBACK.put("gimme gimme gimme", "给我给我给我");
        ECHO_FALLBACK.put("nope", "不");
        ECHO_FALLBACK.put("nope nope nope nope nope", "不不不不不");
        ECHO_FALLBACK.put("bawk bawk bawk", "嘎嘎嘎");
        ECHO_FALLBACK.put("shh", "嘘");
        ECHO_FALLBACK.put("goddamn", "妈的");
        ECHO_FALLBACK.put("goddammit", "妈的");
        ECHO_FALLBACK.put("yeesh", "噫");
        ECHO_FALLBACK.put("whoo", "呼");
        ECHO_FALLBACK.put("autophobia", "孤独恐惧症");
        ECHO_FALLBACK.put("nonhumans", "非人类");
        ECHO_FALLBACK.put("whowhat", "谁——什么");
        ECHO_FALLBACK.put("sup", "哟");
        ECHO_FALLBACK.put("sup aweebin", "哟，阿威宾");
        ECHO_FALLBACK.put("rufus", "鲁弗斯");
        ECHO_FALLBACK.put("serafina", "塞拉菲娜");
        ECHO_FALLBACK.put("nichiri", "尼基里");
        ECHO_FALLBACK.put("charyut", "查里尤特");
        ECHO_FALLBACK.put("galka", "加尔卡");
        ECHO_FALLBACK.put("marbog", "马博格");
        ECHO_FALLBACK.put("wasteman", "废物");
        ECHO_FALLBACK.put("aweebin", "阿威宾");
        ECHO_FALLBACK.put("eshtel", "艾什特尔");
        ECHO_FALLBACK.put("eric lalonde", "埃里克·拉隆德");
        ECHO_FALLBACK.put("inphyy obeys", "因菲服从了");
        ECHO_FALLBACK.put("d.o.t", "D.O.T.");
        ECHO_FALLBACK.put("fu", "操");
        ECHO_FALLBACK.put("sho", "应");
        ECHO_FALLBACK.put("kill", "杀掉");
        ECHO_FALLBACK.put("rukah c", "鲁卡 C");
        ECHO_FALLBACK.put("shoo a", "嘘 A");
        ECHO_FALLBACK.put("q", "Q");
        ECHO_FALLBACK.put("ringalingalingaling", "叮铃铃铃铃");
        ECHO_FALLBACK.put("aye,ya cheeky brat", "哟，你个小捣蛋");
        ECHO_FALLBACK.put("whatcha doin", "在干嘛呢");
    }

    /** Whole-sentence echoes: value keeps the original tag positions verbatim. */
    private static final Map<String, String> FULL_ECHO_FALLBACK = new HashMap<String, String>();
    static {
        FULL_ECHO_FALLBACK.put("the person she tried to kill", "她差点{b}{i}杀掉{/b}{/i}的那个人？");
        FULL_ECHO_FALLBACK.put("the fuck are you doing here", "你{b}{i}他妈{/b}{/i}的在这干什么？");
        FULL_ECHO_FALLBACK.put("remember this dress", "还记得这条裙子吗？");
        FULL_ECHO_FALLBACK.put("titty pics", "涩图？");
    }

    /** The game's ritual-language vocabulary for word-wise echo transliteration. */
    private static final Map<String, String> RITUAL_WORDS = new HashMap<String, String>();
    static {
        RITUAL_WORDS.put("mele", "梅莱");
        RITUAL_WORDS.put("dema", "德马");
        RITUAL_WORDS.put("yurish", "尤里什");
        RITUAL_WORDS.put("pala", "帕拉");
        RITUAL_WORDS.put("oshtel", "奥什特尔");
        RITUAL_WORDS.put("saimamai", "赛马迈");
        RITUAL_WORDS.put("iga", "伊加");
        RITUAL_WORDS.put("tomishi", "托米希");
        RITUAL_WORDS.put("sama", "萨马");
        RITUAL_WORDS.put("vele", "韦莱");
        RITUAL_WORDS.put("al", "阿尔");
        RITUAL_WORDS.put("ragath", "拉加斯");
        RITUAL_WORDS.put("migasai", "米加赛");
        RITUAL_WORDS.put("danemete", "达内梅特");
        RITUAL_WORDS.put("moruna", "莫鲁纳");
        RITUAL_WORDS.put("rhamugari", "拉穆加里");
        RITUAL_WORDS.put("tanzenest", "坦泽内斯特");
        RITUAL_WORDS.put("semasa", "塞马萨");
        RITUAL_WORDS.put("giel", "吉尔");
        RITUAL_WORDS.put("kei", "凯");
        RITUAL_WORDS.put("vaad", "瓦德");
        RITUAL_WORDS.put("paleimai", "帕莱迈");
        RITUAL_WORDS.put("vailam", "瓦伊拉姆");
        RITUAL_WORDS.put("hashesh", "哈谢什");
        RITUAL_WORDS.put("rogasa", "罗加萨");
        RITUAL_WORDS.put("majie", "马杰");
        RITUAL_WORDS.put("therakiin", "塞拉金");
        RITUAL_WORDS.put("na", "纳");
        RITUAL_WORDS.put("romiya", "罗米亚");
        RITUAL_WORDS.put("layala", "拉亚拉");
        RITUAL_WORDS.put("lelane", "莱拉内");
        RITUAL_WORDS.put("hashmi", "哈什米");
        RITUAL_WORDS.put("tomi", "托米");
        RITUAL_WORDS.put("roga", "罗加");
        RITUAL_WORDS.put("enbatan", "恩巴坦");
        RITUAL_WORDS.put("alai", "阿莱");
        RITUAL_WORDS.put("soli", "索利");
        RITUAL_WORDS.put("ai-hala", "艾-哈拉");
        RITUAL_WORDS.put("vaishi", "瓦伊希");
        RITUAL_WORDS.put("wari", "瓦里");
        RITUAL_WORDS.put("nandara", "南达拉");
        RITUAL_WORDS.put("saamase", "萨马塞");
        RITUAL_WORDS.put("mishai", "米沙伊");
        RITUAL_WORDS.put("luamara", "卢阿马拉");
        RITUAL_WORDS.put("saratash", "萨拉塔什");
        RITUAL_WORDS.put("sam", "萨姆");
        RITUAL_WORDS.put("a'wari", "阿瓦里");
        RITUAL_WORDS.put("kai'e", "凯耶");
    }

    /** Resolve one normalized word: exact table, interjection rules, ritual words. */
    private static String resolveWord(String w) {
        String base = ECHO_FALLBACK.get(w);
        if (base != null) {
            return base;
        }
        if (w.matches("a+gh")) {
            return "呃啊";
        }
        if (w.matches("ha+h+")) {
            return "哈——";
        }
        if (w.matches("a+h+")) {
            return "啊";
        }
        if (w.matches("(?:ha)+h?")) {
            return "哈哈";
        }
        if (w.matches("a(?:ha)+h?a*")) {
            return "啊哈哈";
        }
        if (w.matches("ba(?:ha)+a*h*")) {
            return "哈哈哈";
        }
        if (w.matches("a+i+e+")) {
            return "啊啊啊";
        }
        if (w.matches("kh+[he]+")) {
            return "嘿嘿";
        }
        if (w.matches("h+")) {
            return "哈……";
        }
        if (w.matches("by+e+")) {
            return "拜拜";
        }
        if (w.matches("m+h?")) {
            return "嗯";
        }
        if (w.matches("m+")) {
            return "唔";
        }
        if (w.matches("n+h")) {
            return "唔";
        }
        if (w.matches("hn+g+")) {
            return "哼";
        }
        if (w.matches("g+h+k+")) {
            return "呃";
        }
        if (w.matches("gk+h*")) {
            return "呃";
        }
        if (w.matches("h+g+k")) {
            return "呃";
        }
        if (w.matches("a+u+g+h+")) {
            return "呃啊";
        }
        if (w.matches("u+g+h+")) {
            return "呃";
        }
        if (w.matches("o+h+my+")) {
            return "哦——天哪";
        }
        if (w.matches("o+h+")) {
            return "哦";
        }
        if (w.matches("e+w+")) {
            return "呕";
        }
        if (w.matches("p+r+e+")) {
            return "咿";
        }
        if (w.matches("p+r+t+")) {
            return "噗";
        }
        if (w.matches("w+h+e+")) {
            return "哇";
        }
        if (w.matches("w+h+")) {
            return "什";
        }
        if (w.matches("h+e+l+o+")) {
            return "喂";
        }
        if (w.matches("y+e+a+h+")) {
            return "耶";
        }
        if (w.matches("g+r+e+a+t+")) {
            return "太棒了";
        }
        if (w.matches("i+n+t+e+r+e+s+t+i+n+g+")) {
            return "有趣";
        }
        if (w.matches("c+h+i+c+k+e+n+")) {
            return "鸡";
        }
        if (w.matches("s+q+u+a+w+k+")) {
            return "呱";
        }
        if (w.matches("c+a+l+m+")) {
            return "冷静";
        }
        if (w.matches("r+a+w+r+")) {
            return "嗷呜";
        }
        if (w.matches("b+l+e+g+h+")) {
            return "呸";
        }
        if (w.matches("ohmigosh")) {
            return "哦我的天";
        }
        if (w.matches("s+h+r+i+e+k+")) {
            return "尖叫";
        }
        if (w.matches("s+l+u+r+p+")) {
            return "吸溜";
        }
        if (w.matches("(?:ohfuck)+")) {
            return "哦操";
        }
        if (w.matches("k+a+n+a+k+o+")) {
            return "加奈子";
        }
        if (w.matches("m+(?:-m+)*-mele")) {
            return "梅——梅莱";
        }
        if (w.matches("p+(?:-p+)*-pala")) {
            return "帕——帕拉";
        }
        if (w.matches("n+(?:-n+)*-nandara")) {
            return "南——南达拉";
        }
        return RITUAL_WORDS.get(w);
    }

    private static boolean isEchoPunct(char c) {
        return c == '!' || c == '?' || c == '.' || c == ',' || c == '-'
                || c == '\'' || c == '\u2026' || c == '~';
    }

    /** Normalize a text segment into a fallback dictionary key. */
    static String echoKey(String text) {
        if (text == null) {
            return "";
        }
        String s = RENPY_TAG.matcher(text).replaceAll("");
        StringBuilder sb = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\uFF01') {
                c = '!';
            } else if (c == '\uFF1F') {
                c = '?';
            } else if (c == '\u3002') {
                c = '.';
            } else if (c == '\uFF0C') {
                c = ',';
            } else if (c == '\u2018' || c == '\u2019' || c == '\u02BC') {
                c = '\'';
            }
            sb.append(Character.toLowerCase(c));
        }
        String norm = sb.toString().trim();
        int start = 0;
        int end = norm.length();
        while (start < end && isEchoPunct(norm.charAt(start))) {
            start++;
        }
        while (end > start && isEchoPunct(norm.charAt(end - 1))) {
            end--;
        }
        return norm.substring(start, end);
    }

    private static boolean containsNonLatinScript(String text) {
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if ((c >= '\u3040' && c <= '\u30FF')          // hiragana / katakana
                    || (c >= '\u3400' && c <= '\u4DBF')   // CJK ext A
                    || (c >= '\u4E00' && c <= '\u9FFF')   // CJK unified
                    || (c >= '\uF900' && c <= '\uFAFF')) { // CJK compat
                return true;
            }
        }
        return false;
    }

    /** Translate one tag-free segment through the fallback layers, or null. */
    private static String fallbackSegment(String segment) {
        if (segment == null) {
            return null;
        }
        String key = echoKey(segment);
        if (key.length() == 0) {
            return null;
        }
        String base = ECHO_FALLBACK.get(key);
        if (base == null && key.matches("ig+a+ ia dema")) {
            base = "伊加——伊亚·德马";
        }
        if (base == null && key.matches("o+h+ my+")) {
            base = "哦——天哪";
        }
        if (base == null && key.matches("（b+e+p+）")) {
            base = "（哔——）";
        }
        if (base == null && key.matches("（w+h+r+）")) {
            base = "（嗡——）";
        }
        if (base == null && key.matches("（f+l+a+p+）")) {
            base = "（扑棱扑棱扑棱）";
        }
        if (base == null) {
            if (key.indexOf(' ') >= 0 || key.indexOf(',') >= 0) {
                // Word-wise resolution: only when every word resolves, so a
                // normal English sentence can never be transliterated.
                String[] words = key.split("[\\s,]+");
                StringBuilder joined = new StringBuilder();
                boolean allResolved = words.length > 0;
                for (String w : words) {
                    if (w.length() == 0) {
                        continue;
                    }
                    if (w.matches("\\d+")) {
                        joined.append(w);
                        continue;
                    }
                    String wb = resolveWord(w);
                    if (wb == null) {
                        allResolved = false;
                        break;
                    }
                    if (joined.length() > 0) {
                        joined.append("·");
                    }
                    joined.append(wb);
                }
                if (allResolved) {
                    base = joined.toString();
                }
            } else {
                base = resolveWord(key);
            }
        }
        if (base == null) {
            return null;
        }
        String result = base;
        if (segment.charAt(0) == '-') {
            result = "——" + result;
        }
        String trimmed = segment.trim();
        char last = trimmed.charAt(trimmed.length() - 1);
        if (last == '-') {
            return result + "——";
        }
        if (last == '\uFF01' || last == '!') {
            return result + "！";
        }
        if (last == '\uFF1F' || last == '?') {
            return result + "？";
        }
        if (last == '\u3002' || last == '.') {
            if (trimmed.length() >= 2 && trimmed.charAt(trimmed.length() - 2) == '.') {
                return result + "……";
            }
            return result + "。";
        }
        if (last == '\uFF0C' || last == ',') {
            return result + "，";
        }
        if (last == '\u2026') {
            return result + "……";
        }
        return result;
    }

    /**
     * Resolve an ML Kit echo into a real translation when a deterministic
     * fallback applies. Ren'Py tags ({i}, {b}, ...) are preserved around
     * translated segments. Returns the original string for already
     * non-English-script text (visible pass-through), or null when the echo
     * stays unresolved and must keep rejecting.
     */
    static String echoFallback(String original) {
        if (original == null || original.length() == 0) {
            return null;
        }
        String full = FULL_ECHO_FALLBACK.get(echoKey(original));
        if (full != null) {
            return full;
        }
        Matcher m = RENPY_PROTECTED.matcher(original);
        StringBuilder out = new StringBuilder();
        int last = 0;
        boolean changed = false;
        while (m.find()) {
            String seg = original.substring(last, m.start());
            String fb = fallbackSegment(seg);
            if (fb != null && !fb.equals(seg)) {
                out.append(fb);
                changed = true;
            } else {
                out.append(seg);
            }
            out.append(m.group());
            last = m.end();
        }
        String tail = original.substring(last);
        String fb = fallbackSegment(tail);
        if (fb != null && !fb.equals(tail)) {
            out.append(fb);
            changed = true;
        } else {
            out.append(tail);
        }
        if (changed) {
            return out.toString();
        }
        if (containsNonLatinScript(original)) {
            return original;
        }
        return null;
    }

    /** Translate a batch of texts sequentially with a shared ML Kit engine. */
    public static void translate(Context context, List<LocalTranslationSupport.TextItem> items,
                                 String sourceLang, String targetLang, PluginCall call) throws Exception {
        if (items.isEmpty()) {
            JSObject empty = new JSObject();
            empty.put("translations", new JSObject());
            empty.put("count", 0);
            empty.put("warnings", LocalTranslationSupport.toJsonArray(new java.util.ArrayList<String>()));
            call.resolve(empty);
            return;
        }
        synchronized (TRANSLATOR_LOCK) {
            Translator translator = getSharedTranslator(context, sourceLang, targetLang);
            JSObject translations = new JSObject();
            List<String> warnings = new java.util.ArrayList<>();
            int count = 0;
            int warned = 0;
            for (LocalTranslationSupport.TextItem item : items) {
                if (item.text == null || item.text.trim().length() == 0) {
                    continue;
                }
                try {
                    // ML Kit is a literal sentence translator and may change the
                    // case or spelling of Ren'Py placeholders such as [mc].
                    // Protect them exactly like the local LLM path, then restore
                    // and validate before exposing the result to the WebView.
                    LocalLlmEngine.PlaceholderGuard guard =
                            LocalLlmEngine.protectPlaceholders(item.text);
                    String translated = translateProtectedText(guard.protectedText,
                            new SegmentTranslator() {
                                @Override
                                public String translate(String text) throws Exception {
                                    return Tasks.await(translator.translate(text),
                                            TRANSLATE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
                                }
                            });
                    if (translated == null || translated.trim().length() == 0) {
                        if (warned < 50) {
                            warnings.add(item.keyPath + ": 翻译结果为空，已跳过");
                            warned++;
                        }
                        continue;
                    }
                    String restored = LocalLlmEngine.restorePlaceholders(translated, guard);
                    if (restored == null) {
                        if (warned < 50) {
                            warnings.add(item.keyPath + ": 占位符未完整恢复，已跳过");
                            warned++;
                        }
                        continue;
                    }
                    translated = restored;
                    RenpyTextValidator.ValidationResult validation =
                            RenpyTextValidator.validate(item.text, translated);
                    if (!validation.valid) {
                        if (warned < 50) {
                            warnings.add(item.keyPath + ": 译文格式校验失败 " + validation.codes);
                            warned++;
                        }
                        continue;
                    }
                    if (translated.trim().equals(item.text.trim())
                            && !isNonTranslatableProtectedText(guard.protectedText)) {
                        // ML Kit echoed the text back. Resolve it through the
                        // deterministic fallback layer instead of failing the
                        // whole file; unresolved echoes still reject visibly.
                        String fallback = echoFallback(item.text);
                        if (fallback != null) {
                            boolean passThrough = fallback.equals(item.text);
                            RenpyTextValidator.ValidationResult fallbackValidation =
                                    RenpyTextValidator.validate(item.text, fallback);
                            if (fallbackValidation.valid) {
                                translations.put(item.keyPath, fallback);
                                count++;
                                if (warned < 50) {
                                    warnings.add(item.keyPath + (passThrough
                                            ? ": ML Kit 回显，混排文本按原文保留"
                                            : ": ML Kit 回显，已用兜底词典翻译"));
                                    warned++;
                                }
                                continue;
                            }
                        }
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
        }
    }
}
