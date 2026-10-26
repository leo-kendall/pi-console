// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
final class BackupRules {
 static void encodedSize(int bytes){if(bytes<0||bytes>65536)throw new IllegalArgumentException("配置超过 64 KiB，请减少应用入口或缩短网址后再导出");}
 static void ui(String theme,int frequency){if(!("system".equals(theme)||"light".equals(theme)||"dark".equals(theme))||!(frequency==0||frequency==3000||frequency==10000))throw new IllegalArgumentException("备份外观或刷新频率无效");}
 static void thresholds(double temperature,double memory,double disk){if(!Double.isFinite(temperature)||temperature<45||temperature>95||!Double.isFinite(memory)||memory<50||memory>99||!Double.isFinite(disk)||disk<50||disk>99)throw new IllegalArgumentException("备份告警阈值无效");}
}
