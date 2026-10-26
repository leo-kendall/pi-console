// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.util.*;
public final class DeliveryRegressionTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  List<String> history=new ArrayList<>();for(int i=0;i<128;i++)history.add("event"+i);
  Set<String> candidates=AlertDelivery.candidates(history,Arrays.asList("old-active"));check(candidates.contains("old-active"));check(AlertDelivery.unseen(candidates,Collections.emptySet()).contains("old-active"));check(AlertDelivery.unseen(candidates,candidates).isEmpty());
  check(AlertDelivery.stale(Double.NaN,200));check(AlertDelivery.stale(1,200));check(!AlertDelivery.stale(195,200));
  for(int request:new int[]{41,42,51,52})check(!PendingDocumentRequest.accepts(request,false,true));
  check(PendingDocumentRequest.accepts(41,true,false));check(PendingDocumentRequest.accepts(52,true,false));check(!PendingDocumentRequest.accepts(42,true,false));check(!PendingDocumentRequest.accepts(51,true,false));check(PendingDocumentRequest.accepts(42,true,true));
  BackupRules.encodedSize(65536);try{BackupRules.encodedSize(65537);throw new AssertionError();}catch(IllegalArgumentException expected){}
  System.out.println("Notification/SAF recreation/backup size regressions passed");
 }
}
