// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
public final class ServerSettingsTest {
 interface Operation {void run()throws Exception;}
 static void rejected(Operation op)throws Exception{boolean bad=false;try{op.run();}catch(Exception e){bad=true;}if(!bad)throw new AssertionError("stale or unsafe operation accepted");}
 static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
  Context c=new Context(),other=new Context();
  check(ServerSettings.url(c).isEmpty()&&!ServerSettings.paired(c));
  check(ServerSettings.url(other).isEmpty()&&!ServerSettings.paired(other));
  ServerSettings.set(c,"https://a.example.test");ServerSettings.Snapshot a=ServerSettings.snapshot(c);
  ServerSettings.pair(c,a,"token-A");ServerSettings.Snapshot paired=ServerSettings.snapshot(c);
  check(ServerSettings.url(other).isEmpty()&&!ServerSettings.paired(other));
  ServerSettings.set(other,"https://independent.example.test");
  ServerSettings.pair(other,ServerSettings.snapshot(other),"independent-token");
  check(ServerSettings.snapshot(c).token.equals("token-A"));
  check(ServerSettings.snapshot(other).token.equals("independent-token"));
  rejected(()->ServerSettings.set(c,"https://b.example.test"));
  ServerSettings.forget(c);ServerSettings.set(c,"https://b.example.test");ServerSettings.Snapshot b=ServerSettings.snapshot(c);
  check(paired.token.equals("token-A")&&paired.endpoint.host.equals("a.example.test"));check(b.token.isEmpty());
  rejected(()->ServerSettings.pair(c,a,"late-A"));
  ServerSettings.set(c,"https://a.example.test");rejected(()->ServerSettings.pair(c,a,"same-URL-stale-generation"));
  ServerSettings.Snapshot beforeForget=ServerSettings.snapshot(c);ServerSettings.forget(c);
  rejected(()->ServerSettings.pair(c,beforeForget,"pair-after-forget"));
  check(!ServerSettings.paired(c));ServerSettings.pair(c,ServerSettings.snapshot(c),"fresh-A");check(ServerSettings.paired(c));
  c.getSharedPreferences("paired",0).edit().putString("server","https://other.example.test").commit();check(ServerSettings.snapshot(c).token.isEmpty());
  check(ServerSettings.paired(other));
  System.out.println("Fresh-install defaults, independent preferences, server switch, immutable request routing, stale pairing and forget cancellation tests passed");
 }
}
