package androidx.activity;

import androidx.lifecycle.LifecycleOwner;

public class OnBackPressedDispatcher {
    public void addCallback(LifecycleOwner owner, OnBackPressedCallback callback) {}
    public void onBackPressed() {}
}
