// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.ArrayList;
import java.util.List;
import org.json.JSONArray;
import org.json.JSONObject;

final class AppStore {
    static final class Entry {
        String name;
        String url;
        boolean inline;
        Entry(String name, String url, boolean inline) {
            this.name = name; this.url = url; this.inline = inline;
        }
    }

    private final SharedPreferences preferences;
    AppStore(Context context) { preferences = context.getSharedPreferences("app_entries", Context.MODE_PRIVATE); }

    List<Entry> load() {
        List<Entry> entries = new ArrayList<>();
        String stored = preferences.getString("items", null);
        if (stored == null) {

            return entries;
        }
        try {
            JSONArray array = new JSONArray(stored);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.getJSONObject(i);
                entries.add(new Entry(item.getString("name"), UrlRules.validate(item.getString("url")),
                        item.optBoolean("inline", false)));
            }
        } catch (Exception ignored) {
            // A damaged private preference cannot crash the application screen.
        }
        return entries;
    }

    void save(List<Entry> entries) {
        JSONArray array = new JSONArray();
        for (Entry entry : entries) {
            JSONObject item = new JSONObject();
            try {
                item.put("name", entry.name);
                item.put("url", UrlRules.validate(entry.url));
                item.put("inline", entry.inline);
                array.put(item);
            } catch (Exception ex) { throw new IllegalArgumentException("无效应用入口", ex); }
        }
        if(!preferences.edit().putString("items", array.toString()).commit())throw new IllegalArgumentException("应用入口保存失败");
    }
}
