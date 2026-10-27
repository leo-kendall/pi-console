// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.util.*;
public final class UpdateRulesTest {
 interface Op{void run()throws Exception;}static void deny(Op op)throws Exception{try{op.run();}catch(Exception expected){return;}throw new AssertionError("unsafe update accepted");}
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] a)throws Exception{
  check(UpdateRules.newer("0.6.0","0.5.0-beta.2"));check(UpdateRules.newer("v0.5.0","0.5.0-beta.2"));check(!UpdateRules.newer("0.5.0-beta.1","0.5.0-beta.2"));check(UpdateRules.newer("0.5.0-beta.10","0.5.0-beta.2"));
  check(UpdateRules.apkName("pi-console.apk"));check(UpdateRules.apkName("pi-console-release.apk"));check(UpdateRules.apkName("pi-console-0.6.0-beta.1.apk"));check(!UpdateRules.apkName("pi-console-debug.apk"));check(!UpdateRules.apkName("other.apk"));
  UpdateRules.url("https://github.com/leo-kendall/pi-console/releases/download/v1/a.apk");
  deny(()->UpdateRules.url("http://github.com/a"));deny(()->UpdateRules.url("https://github.com.evil.test/a"));deny(()->UpdateRules.url("https://user:pass@github.com/a"));deny(()->UpdateRules.url("https://github.com:444/a"));
  check(UpdateRules.signers(new String[]{"old"},new String[]{"new"},new String[]{"old","new"}));
  check(!UpdateRules.signers(new String[]{"current"},new String[]{"attacker"},new String[]{"old","attacker"}));
  check(!UpdateRules.signers(new String[]{"a","b"},new String[]{"a"},new String[]{"a","b"}));
  check(!UpdateRules.signers(new String[]{},new String[]{},new String[]{}));
  deny(()->UpdateRules.digest("sha256:xyz"));check(UpdateRules.digest("sha256:"+String.join("",Collections.nCopies(64,"a"))).length()==64);
  System.out.println("Updates: semantic versions, endpoint allowlist, digest and signer lineage policy passed");
 }
}
