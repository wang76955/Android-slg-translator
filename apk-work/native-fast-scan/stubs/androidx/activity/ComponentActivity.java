package androidx.activity;

import android.app.Activity;
import androidx.lifecycle.Lifecycle;
import androidx.lifecycle.LifecycleOwner;

public class ComponentActivity extends Activity implements LifecycleOwner {
    private final Lifecycle lifecycle = new Lifecycle();
    public OnBackPressedDispatcher getOnBackPressedDispatcher() { return null; }
    public Lifecycle getLifecycle() { return lifecycle; }
}
