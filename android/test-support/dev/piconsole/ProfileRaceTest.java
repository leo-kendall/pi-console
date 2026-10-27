// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.Context;import java.util.concurrent.*;import java.util.concurrent.atomic.*;
/** JVM Android-preferences boundary substitute; all profile code is production code. */
public final class ProfileRaceTest {
 static void check(boolean v){if(!v)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
  Context c=new Context();String a=ServerSettings.add(c,"A","https://a.test"),b=ServerSettings.add(c,"B","https://b.test");ServerSettings.pair(c,ServerSettings.snapshot(c),"A");
  ServerSettings.Snapshot request=ServerSettings.snapshot(c);CountDownLatch release=new CountDownLatch(1);AtomicBoolean lateRejected=new AtomicBoolean();
  Thread pairing=new Thread(()->{try{release.await();ServerSettings.pair(c,request,"late-A");}catch(Exception expected){lateRejected.set(true);}});pairing.start();ServerSettings.activate(c,b);release.countDown();pairing.join();
  check(lateRejected.get()&&ServerSettings.snapshot(c).token.isEmpty());
  ServerSettings.pair(c,ServerSettings.snapshot(c),"B");AtomicReference<Throwable> failure=new AtomicReference<>();
  Runnable worker=()->{try{for(int i=0;i<200;i++){ServerSettings.Snapshot s=ServerSettings.snapshot(c);if(!(s.endpoint.host.equals("a.test")&&s.token.equals("A")||s.endpoint.host.equals("b.test")&&s.token.equals("B")))throw new AssertionError("cross-server credential snapshot");}}catch(Throwable e){failure.set(e);}};
  Thread first=new Thread(worker),second=new Thread(worker);first.start();second.start();for(int i=0;i<100;i++)ServerSettings.activate(c,i%2==0?a:b);first.join();second.join();if(failure.get()!=null)throw new AssertionError(failure.get());
  // An unpair response from A must not clear B after a switch.
  ServerSettings.activate(c,b);
  try{ServerSettings.forget(c,request);throw new AssertionError("late unpair accepted");}catch(IllegalStateException expected){}
  check(ServerSettings.snapshot(c).token.equals("B"));
  // Pending SAF/server requests keep their original captured endpoint and token.
  check(request.endpoint.canonical.equals("https://a.test")&&request.token.equals("A"));
  check(c.getSharedPreferences("paired-"+b,0).getString("credential","").equals("B"));
  ServerSettings.remove(c,a);check(!ServerSettings.current(c,request));check(c.getSharedPreferences("paired-"+a,0).getString("credential","").isEmpty());
  System.out.println("Profiles native boundary: concurrent request/switch race, late pairing, captured SAF routing and isolated removal passed");
 }
}
