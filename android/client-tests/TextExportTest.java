// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class TextExportTest {
 interface Op{void run()throws Exception;}
 static void deny(Op op)throws Exception{try{op.run();}catch(Exception expected){return;}throw new AssertionError("unsafe text export accepted");}
 public static void main(String[] args)throws Exception{
  TextExport.validate("logs.txt","Plain text <script> stays data");
  deny(()->TextExport.validate("../logs.txt","data"));
  deny(()->TextExport.validate("logs.html","data"));
  deny(()->TextExport.validate("logs.txt",new String(new char[90000]).replace('\0','界')));
  TextExport.validate("logs.txt",new String(new char[262144]).replace('\0','a'));
  System.out.println("Native text export: safe names, plain text, exact byte limit and UTF-8 oversize passed");
 }
}
