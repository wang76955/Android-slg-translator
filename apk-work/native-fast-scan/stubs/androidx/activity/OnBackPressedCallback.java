package androidx.activity;

public abstract class OnBackPressedCallback {
    public OnBackPressedCallback(boolean enabled) {}
    public abstract void handleOnBackPressed();
    public void setEnabled(boolean enabled) {}
}
