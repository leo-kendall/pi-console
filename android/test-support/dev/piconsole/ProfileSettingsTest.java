// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;
public final class ProfileSettingsTest {
 interface Op {void run()throws Exception;}
 static void check(boolean v){if(!v)throw new AssertionError();}
 static void deny(Op op)throws Exception{try{op.run();}catch(Exception expected){return;}throw new AssertionError("unsafe profile operation accepted");}
 public static void main(String[] args)throws Exception {
  Context c=new Context();c.getSharedPreferences("server",0).edit().putString("url","https://legacy.test").putString("generation","legacy").commit();
  c.getSharedPreferences("app_entries",0).edit().putString("items","legacy-apps-fixture").commit();
  SecretStore.save(c,"legacy-token");c.getSharedPreferences("paired",0).edit().putString("server","https://legacy.test").commit();
  check(ServerSettings.paired(c));String a=ServerSettings.activeId(c);check(ServerSettings.profiles(c).size()==1);
  ServerSettings.Snapshot original=ServerSettings.snapshot(c);check(original.token.equals("legacy-token"));
  String b=ServerSettings.add(c,"Laboratory","https://b.test/pi");check(ServerSettings.activeId(c).equals(a));
  ServerSettings.activate(c,b);check(!ServerSettings.paired(c));deny(()->ServerSettings.pair(c,original,"late-token"));
  ServerSettings.pair(c,ServerSettings.snapshot(c),"B-token");ServerSettings.activate(c,a);
  check(ServerSettings.snapshot(c).token.equals("legacy-token"));check(!ServerSettings.current(c,original));
  ServerSettings.forget(c);ServerSettings.activate(c,b);check(ServerSettings.snapshot(c).token.equals("B-token"));
  deny(()->ServerSettings.add(c,"duplicate","https://B.test:443/pi/"));deny(()->ServerSettings.add(c,"bad","http://bad.test"));
  ServerSettings.rename(c,b,"Production");check(ServerSettings.profiles(c).get(1).name.equals("Production"));
  ServerSettings.remove(c,a);check(ServerSettings.paired(c));
  check(c.getSharedPreferences("app_entries",0).getString("items","").isEmpty());
  check(c.getSharedPreferences("server",0).getString("url","").isEmpty());
  for(int i=1;i<32;i++)ServerSettings.add(c,"node "+i,"https://n"+i+".test");
  deny(()->ServerSettings.add(c,"overflow","https://overflow.test"));
  ServerSettings.remove(c,b);check(!ServerSettings.paired(c));check(ServerSettings.profiles(c).size()==31);
  System.out.println("Profiles: legacy migration, endpoint privacy, generation races, limits and local removal passed");
 }
}
