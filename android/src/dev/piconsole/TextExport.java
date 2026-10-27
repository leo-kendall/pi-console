// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.app.Activity;import android.content.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.util.concurrent.*;
/** One bounded local text export. No server action occurs during document selection. */
final class TextExport {
 private final Activity activity;private byte[] pending;private final ExecutorService executor=Executors.newSingleThreadExecutor();
 TextExport(Activity a){activity=a;}
 static void validate(String name,String text)throws Exception{if(!name.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,100}\\.txt")||text.getBytes(StandardCharsets.UTF_8).length>262144)throw new IOException("导出名称无效或日志超过 256 KiB");}
 void start(String name,String text)throws Exception{validate(name,text);if(pending!=null)throw new IOException("请先完成日志文件选择");pending=text.getBytes(StandardCharsets.UTF_8);try{activity.startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("text/plain").putExtra(Intent.EXTRA_TITLE,name),61);}catch(Exception e){pending=null;throw e;}}
 void result(int request,int code,Intent data){if(request!=61)return;byte[] bytes=pending;pending=null;if(bytes==null||code!=Activity.RESULT_OK||data==null||data.getData()==null)return;executor.execute(()->{String message;try(OutputStream out=activity.getContentResolver().openOutputStream(data.getData(),"wt")){if(out==null)throw new IOException("无法写入文件");out.write(bytes);message="日志已导出";}catch(Exception e){message="日志导出失败";}final String m=message;activity.runOnUiThread(()->android.widget.Toast.makeText(activity,m,android.widget.Toast.LENGTH_LONG).show());});}
 void close(){pending=null;executor.shutdown();}
}
