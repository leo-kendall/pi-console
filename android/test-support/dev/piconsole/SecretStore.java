// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
/** Keystore boundary substitute. These tests do not validate Android encryption. */
final class SecretStore {
 static String read(Context c){return c.getSharedPreferences("paired",0).getString("credential","");}
 static void save(Context c,String token){c.getSharedPreferences("paired",0).edit().putString("credential",token).commit();}
 static void clear(Context c){c.getSharedPreferences("paired",0).edit().clear().commit();}
}
