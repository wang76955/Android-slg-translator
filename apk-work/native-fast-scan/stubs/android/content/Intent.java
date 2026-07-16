package android.content;

public class Intent {
    public static final String ACTION_MAIN = "android.intent.action.MAIN";
    public static final String CATEGORY_LAUNCHER = "android.intent.category.LAUNCHER";
    public Intent(String action) {}
    public Intent addCategory(String category) { return this; }
}
