// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import javax.crypto.*;import javax.crypto.spec.*;import java.util.*;
public final class CredentialCipherTest {
 interface Op{void run()throws Exception;}static void deny(Op op)throws Exception{try{op.run();}catch(Exception expected){return;}throw new AssertionError("credential namespace not authenticated");}
 public static void main(String[] a)throws Exception {
  javax.crypto.SecretKey key=new SecretKeySpec(new byte[32],"AES");String encoded=CredentialCipher.encrypt(key,"profile-a","secret-A");
  if(!CredentialCipher.decrypt(key,"profile-a",encoded).equals("secret-A"))throw new AssertionError();
  deny(()->CredentialCipher.decrypt(key,"profile-b",encoded));
  deny(()->CredentialCipher.decrypt(new SecretKeySpec(new byte[16],"AES"),"profile-a",encoded));
  // Literal beta2 algorithm fixture: IV:ciphertext, no AAD, same retained Keystore key.
  Cipher old=Cipher.getInstance("AES/GCM/NoPadding");old.init(Cipher.ENCRYPT_MODE,key,new GCMParameterSpec(128,new byte[12]));String legacy=Base64.getEncoder().encodeToString(new byte[12])+":"+Base64.getEncoder().encodeToString(old.doFinal("beta2-token".getBytes("UTF-8")));
  if(!CredentialCipher.decrypt(key,"legacy",legacy).equals("beta2-token"))throw new AssertionError();
  deny(()->CredentialCipher.decrypt(key,"legacy","garbage"));
  System.out.println("Credential AES-GCM: beta2 compatibility, profile AAD isolation, wrong key and malformed ciphertext passed");
 }
}
