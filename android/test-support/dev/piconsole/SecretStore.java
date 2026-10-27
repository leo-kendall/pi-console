// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
/** Keystore boundary substitute, does not validate Android encryption. */
final class SecretStore {
 static String read(Context c)throws Exception{return read(c,ServerSettings.activeId(c));}
 static String read(Context c,String id){return c.getSharedPreferences("paired-"+id,0).getString("credential","");}
 static void save(Context c,String token){c.getSharedPreferences("paired",0).edit().putString("credential",token).commit();}
 static void save(Context c,String id,String token){c.getSharedPreferences("paired-"+id,0).edit().putString("credential",token).commit();}
 static void clear(Context c)throws Exception{clear(c,ServerSettings.activeId(c));}
 static void clear(Context c,String id){c.getSharedPreferences("paired-"+id,0).edit().clear().commit();}
 static void migrate(Context c,String id){android.content.SharedPreferences p=c.getSharedPreferences("paired",0);c.getSharedPreferences("paired-"+id,0).edit().putString("credential",p.getString("credential","")).putString("server",p.getString("server","")).commit();}
}
