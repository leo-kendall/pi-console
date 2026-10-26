// SPDX-License-Identifier: Apache-2.0
package android.content;
import java.util.HashMap;
import java.util.Map;
/** Storage boundary substitute for JVM tests, never in android/src or an APK. */
public class Context {
 private final Map<String,Preferences> files=new HashMap<>();
 public SharedPreferences getSharedPreferences(String name,int mode){if(!files.containsKey(name))files.put(name,new Preferences());return files.get(name);}
 private static final class Preferences implements SharedPreferences {
  final Map<String,String> values=new HashMap<>();
  public String getString(String key,String fallback){return values.getOrDefault(key,fallback);}
  public Editor edit(){return new Editor(){final Map<String,String> next=new HashMap<>(values);public Editor putString(String key,String value){next.put(key,value);return this;}public Editor clear(){next.clear();return this;}public boolean commit(){values.clear();values.putAll(next);return true;}};}
 }
}
