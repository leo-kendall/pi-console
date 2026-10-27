// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import android.security.keystore.*;
import java.security.KeyStore;
import javax.crypto.*;
final class SecretStore {
 private static final String ALIAS="pi-console-pairing";
 private static javax.crypto.SecretKey key()throws Exception{
  KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
  if(!ks.containsAlias(ALIAS)){KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());gen.generateKey();}
  return (javax.crypto.SecretKey)ks.getKey(ALIAS,null);
 }
 static void save(Context c,String token)throws Exception{save(c,ServerSettings.activeId(c),token);}
 static synchronized void save(Context c,String id,String token)throws Exception{
  String value=CredentialCipher.encrypt(key(),id,token);
  if(!c.getSharedPreferences("paired-"+id,0).edit().putString("credential",value).commit())throw new Exception("保存配对失败");
 }
 static String read(Context c)throws Exception{return read(c,ServerSettings.activeId(c));}
 static synchronized String read(Context c,String id)throws Exception{
  String value=c.getSharedPreferences("paired-"+id,0).getString("credential","");if(value.isEmpty())return "";return CredentialCipher.decrypt(key(),id,value);
 }
 static void clear(Context c)throws Exception{clear(c,ServerSettings.activeId(c));}
 static synchronized void clear(Context c,String id)throws Exception{if(!c.getSharedPreferences("paired-"+id,0).edit().clear().commit())throw new Exception("移除凭证失败");}
 static synchronized void migrate(Context c,String id)throws Exception{
  android.content.SharedPreferences old=c.getSharedPreferences("paired",0);
  if(!c.getSharedPreferences("paired-"+id,0).edit().putString("credential",old.getString("credential","")).putString("server",old.getString("server","")).commit())throw new Exception("迁移配对失败");
 }
}
