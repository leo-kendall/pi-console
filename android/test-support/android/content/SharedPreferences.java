// SPDX-License-Identifier: Apache-2.0
package android.content;
public interface SharedPreferences {
 String getString(String key,String fallback);
 Editor edit();
 interface Editor {Editor putString(String key,String value);Editor clear();boolean commit();}
}
