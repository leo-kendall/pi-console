// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
import android.security.keystore.*;
import android.util.Base64;
import java.security.KeyStore;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
final class SecretStore {
 private static final String ALIAS="pi-console-pairing";
 private static javax.crypto.SecretKey key()throws Exception{
  KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
  if(!ks.containsAlias(ALIAS)){KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");gen.init(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());gen.generateKey();}
  return (javax.crypto.SecretKey)ks.getKey(ALIAS,null);
 }
 static synchronized void save(Context c,String token)throws Exception{Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());String value=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(cipher.doFinal(token.getBytes("UTF-8")),Base64.NO_WRAP);if(!c.getSharedPreferences("paired",0).edit().putString("credential",value).commit())throw new Exception("保存配对失败");}
 static synchronized String read(Context c)throws Exception{String value=c.getSharedPreferences("paired",0).getString("credential","");if(value.isEmpty())return "";String[] parts=value.split(":",2);Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)));return new String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),"UTF-8");}
 static synchronized void clear(Context c)throws Exception{c.getSharedPreferences("paired",0).edit().clear().commit();KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);ks.deleteEntry(ALIAS);}
}
