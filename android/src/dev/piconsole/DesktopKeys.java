// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import java.util.LinkedHashMap;
/** Android key codes to X11 keysyms, independent of platform state. */
final class DesktopKeys {
 static int keysym(int key,int unicode){
  if(key>=131&&key<=142)return 65470+key-131;
  switch(key){
   case 4:return 0;
   case 19:return 65362;case 20:return 65364;case 21:return 65361;case 22:return 65363;
   case 61:return 65289;case 66:case 160:return 65293;case 67:return 65288;case 111:return 65307;case 112:return 65535;
   case 92:return 65365;case 93:return 65366;case 122:return 65360;case 123:return 65367;case 124:return 65379;
   case 59:return 65505;case 60:return 65506;case 57:return 65513;case 58:return 65514;
   case 113:return 65507;case 114:return 65508;case 117:return 65515;case 118:return 65516;
   case 115:return 65509;case 116:return 65300;case 120:return 65377;case 121:return 65299;case 82:return 65383;
   default:return unicode>=32&&unicode<=0x10ffff&&!(unicode>=0xd800&&unicode<=0xdfff)?(unicode<=255?unicode:0x01000000|unicode):0;
  }
 }
 static final class Pressed {
  private final LinkedHashMap<Integer,Integer> keys=new LinkedHashMap<>();
  int down(int code,int sym){if(!keys.containsKey(code))keys.put(code,sym);return keys.get(code);}
  int up(int code,int fallback){Integer sym=keys.remove(code);return sym==null?fallback:sym;}
  int size(){return keys.size();}
  int[] release(){int[] out=new int[keys.size()];int i=0;for(int sym:keys.values())out[i++]=sym;keys.clear();return out;}
 }
}
