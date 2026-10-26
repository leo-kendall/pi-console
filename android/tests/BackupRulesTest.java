// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class BackupRulesTest {
 interface Check { void run(); }
 static void refused(Check r){try{r.run();}catch(IllegalArgumentException e){return;}throw new AssertionError("accepted invalid backup rule");}
 public static void main(String[] args){
  BackupRules.ui("system",3000);BackupRules.ui("dark",0);refused(()->BackupRules.ui("javascript",3000));refused(()->BackupRules.ui("light",-1));
  BackupRules.thresholds(75,90,90);refused(()->BackupRules.thresholds(Double.NaN,90,90));refused(()->BackupRules.thresholds(30,90,90));refused(()->BackupRules.thresholds(75,100,90));
  System.out.println("Backup bounds tests passed");
 }
}
