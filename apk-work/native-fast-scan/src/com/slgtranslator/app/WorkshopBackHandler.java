package com.slgtranslator.app;

import android.app.Activity;
import android.webkit.WebView;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.lifecycle.Lifecycle;

import java.lang.ref.WeakReference;
import java.util.Map;
import java.util.WeakHashMap;

public final class WorkshopBackHandler {
    private static final Map<ComponentActivity, WeakReference<OnBackPressedCallback>> callbacks =
        new WeakHashMap<>();
    private static final String HANDLE_BACK =
        "(function(){try{return window.__slgHandleAndroidBack&&" +
        "window.__slgHandleAndroidBack()===true}catch(e){return false}})()";

    private WorkshopBackHandler() {}

    public static void enable(Activity activity, WebView webView) {
        if (activity == null || webView == null) {
            return;
        }
        activity.runOnUiThread(() -> install(activity, webView));
    }

    private static void install(Activity activity, WebView webView) {
        if (!(activity instanceof ComponentActivity) || activity.isFinishing() || activity.isDestroyed()) {
            return;
        }
        ComponentActivity componentActivity = (ComponentActivity) activity;
        WeakReference<OnBackPressedCallback> existingReference = callbacks.get(componentActivity);
        if (existingReference != null && existingReference.get() != null) {
            return;
        }
        OnBackPressedCallback callback = new OnBackPressedCallback(true) {
            private boolean evaluating;

            @Override
            public void handleOnBackPressed() {
                if (evaluating || !isLive(componentActivity)) {
                    return;
                }
                evaluating = true;
                try {
                    webView.evaluateJavascript(HANDLE_BACK, value -> {
                        evaluating = false;
                        if (isLive(componentActivity) && !"true".equals(value)) {
                            delegateDefaultBack(componentActivity, this);
                        }
                    });
                } catch (Throwable ignored) {
                    evaluating = false;
                    if (isLive(componentActivity)) {
                        delegateDefaultBack(componentActivity, this);
                    }
                }
            }
        };
        callbacks.put(componentActivity, new WeakReference<>(callback));
        componentActivity.getOnBackPressedDispatcher().addCallback(componentActivity, callback);
    }

    private static boolean isLive(ComponentActivity activity) {
        return !activity.isFinishing()
            && !activity.isDestroyed()
            && activity.getLifecycle().getCurrentState().isAtLeast(Lifecycle.State.STARTED);
    }

    private static void delegateDefaultBack(
        ComponentActivity activity,
        OnBackPressedCallback callback
    ) {
        if (!isLive(activity)) {
            return;
        }
        callback.setEnabled(false);
        try {
            activity.getOnBackPressedDispatcher().onBackPressed();
        } finally {
            if (isLive(activity)) {
                callback.setEnabled(true);
            }
        }
    }
}
