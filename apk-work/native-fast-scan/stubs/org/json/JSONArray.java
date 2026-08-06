package org.json;

public class JSONArray {
    public static final Object NULL = new Object();
    public JSONArray() {}
    public JSONArray(String json) throws Exception {}
    public JSONArray put(Object value) { return this; }
    public int length() { return 0; }
    public JSONObject getJSONObject(int index) { return null; }
    public Object opt(int index) { return null; }
    public boolean isNull(int index) { return true; }
}
