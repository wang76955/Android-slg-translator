package com.slgtranslator.app;

import android.content.Context;
import android.content.Intent;

/** Pure runtime evidence classification shared by native and bridge callers. */
public final class RuntimeValidationSupport {
    private RuntimeValidationSupport() {
    }

    /** Launch resolution seam that the Android bridge can satisfy with Context. */
    public interface ContextLike {
        Intent getLaunchIntentForPackage(String packageName);
    }

    /** Result of a launch probe: resolved means a launch intent exists, started
     * means only that startActivity returned without throwing. */
    public static final class LaunchResult {
        public final boolean resolved;
        public final boolean started;

        public LaunchResult(boolean resolved, boolean started) {
            this.resolved = resolved;
            this.started = started;
        }
    }

    /** Pure resolve: true only when a launch intent is actually available. */
    public static boolean resolveLaunchable(ContextLike context, String packageName) {
        if (context == null || packageName == null || packageName.trim().isEmpty()) {
            return false;
        }
        return context.getLaunchIntentForPackage(packageName) != null;
    }

    /** Launches the game if a launch intent resolves; started never means rendered. */
    public static LaunchResult launchGame(Context context, String packageName) {
        if (context == null || packageName == null || packageName.trim().isEmpty()) {
            return new LaunchResult(false, false);
        }
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(packageName);
        if (intent == null) {
            return new LaunchResult(false, false);
        }
        try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
            return new LaunchResult(true, true);
        } catch (Exception error) {
            return new LaunchResult(true, false);
        }
    }

    public static final class Evidence {
        public final boolean installed;
        public final boolean staticAsserts;
        public final boolean launched;
        public final Boolean textAppears;

        public Evidence(boolean installed, boolean staticAsserts, boolean launched,
                Boolean textAppears) {
            this.installed = installed;
            this.staticAsserts = staticAsserts;
            this.launched = launched;
            this.textAppears = textAppears;
        }
    }

    public static final class Status {
        public final String code;
        public final String display;
        public final String reason;
        public final String nextSteps;

        private Status(String code, String display, String reason, String nextSteps) {
            this.code = code;
            this.display = display;
            this.reason = reason;
            this.nextSteps = nextSteps;
        }
    }

    public static Status classify(Evidence evidence) {
        if (evidence == null || !evidence.installed) {
            return new Status("NOT_INSTALLED", "安装未成功", "补丁未安装到设备。",
                    "检查安装来源与签名后重试安装。");
        }
        if (!evidence.staticAsserts) {
            return new Status("PATCH_NOT_APPLIED", "未生效（入口缺失）",
                    "补丁产物缺少语言入口或译文，always-on 未编入。",
                    "重新生成补丁，确认编译覆盖后再安装。");
        }
        if (!evidence.launched) {
            return new Status("LAUNCH_FAILED", "启动失败",
                    "已发出启动动作，但未确认游戏进程启动。",
                    "手动启动游戏一次，回来说一声结果即可继续验证。");
        }
        if (Boolean.FALSE.equals(evidence.textAppears)) {
            return new Status("STRING_MISMATCH", "label 失效（文本未出现）",
                    "补丁已安装且启动成功，但游戏内未显示目标语言文本：已编译翻译字符串未匹配到运行时引用。",
                    "保留现有补丁与证据；后续阶段用运行时映射验证定位失效的 label 引用。");
        }
        if (Boolean.TRUE.equals(evidence.textAppears)) {
            return new Status("ACTIVE", "汉化生效",
                    "安装成功、语言入口存在、目标语言文本实际出现。",
                    "验证完成。");
        }
        return new Status("PENDING_CONFIRM", "待确认",
                "已安装并已发出启动动作，等待你确认游戏内是否出现目标语言文本。",
                "在游戏内切换到目标语言并检查文本后，选择'已生效'或'未生效'。");
    }
}
