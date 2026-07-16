package com.slgtranslator.app;

import android.app.Activity;
import android.webkit.WebView;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;

import java.util.Map;
import java.util.WeakHashMap;

public final class WorkshopBackHandler {
    private static final Map<Activity, OnBackPressedCallback> callbacks = new WeakHashMap<>();
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
        if (callbacks.containsKey(activity)) {
            return;
        }
        ComponentActivity componentActivity = (ComponentActivity) activity;
        OnBackPressedCallback callback = new OnBackPressedCallback(true) {
            private boolean evaluating;

            @Override
            public void handleOnBackPressed() {
                if (evaluating) {
                    return;
                }
                evaluating = true;
                try {
                    webView.evaluateJavascript(HANDLE_BACK, value -> {
                        evaluating = false;
                        if (!"true".equals(value)) {
                            delegateDefaultBack(componentActivity, this);
                        }
                    });
                } catch (Throwable ignored) {
                    evaluating = false;
                    delegateDefaultBack(componentActivity, this);
                }
            }
        };
        callbacks.put(activity, callback);
        componentActivity.getOnBackPressedDispatcher().addCallback(componentActivity, callback);
    }

    private static void delegateDefaultBack(
        ComponentActivity activity,
        OnBackPressedCallback callback
    ) {
        callback.setEnabled(false);
        try {
            activity.getOnBackPressedDispatcher().onBackPressed();
        } finally {
            if (!activity.isFinishing() && !activity.isDestroyed()) {
                callback.setEnabled(true);
            }
        }
    }
}
