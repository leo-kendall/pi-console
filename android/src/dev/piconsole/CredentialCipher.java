// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import javax.crypto.*;import javax.crypto.spec.GCMParameterSpec;import java.util.Base64;import java.nio.charset.StandardCharsets;
/** Versioned AES-GCM format. New credentials authenticate their local profile namespace. */
final class CredentialCipher {
 static String encrypt(SecretKey key,String profile,String token)throws Exception{
  Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key);c.updateAAD(profile.getBytes(StandardCharsets.UTF_8));
  return "v2:"+Base64.getEncoder().encodeToString(c.getIV())+":"+Base64.getEncoder().encodeToString(c.doFinal(token.getBytes(StandardCharsets.UTF_8)));
 }
 static String decrypt(SecretKey key,String profile,String value)throws Exception{
  if(value.isEmpty())return "";boolean v2=value.startsWith("v2:");String[] parts=(v2?value.substring(3):value).split(":",-1);if(parts.length!=2)throw new IllegalArgumentException("配对凭证格式无效");
  byte[] iv=Base64.getDecoder().decode(parts[0]);if(iv.length!=12)throw new IllegalArgumentException("配对凭证格式无效");Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,iv));if(v2)c.updateAAD(profile.getBytes(StandardCharsets.UTF_8));
  return new String(c.doFinal(Base64.getDecoder().decode(parts[1])),StandardCharsets.UTF_8);
 }
}
