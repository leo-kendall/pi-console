// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
import android.content.*;import android.database.Cursor;import android.database.MatrixCursor;import android.net.Uri;import android.os.ParcelFileDescriptor;import java.io.*;
/** Read-only URI grant for the platform package installer, no directory traversal. */
public final class UpdateProvider extends ContentProvider {
 @Override public boolean onCreate(){return true;}
 private void path(Uri u)throws FileNotFoundException{if(!"/apk".equals(u.getPath())||u.getQuery()!=null||u.getFragment()!=null||!UpdateManager.prefs(getContext()).getString("state","").equals("ready"))throw new FileNotFoundException();}
 @Override public String getType(Uri u){return "application/vnd.android.package-archive";}
 @Override public ParcelFileDescriptor openFile(Uri u,String mode)throws FileNotFoundException{path(u);if(!"r".equals(mode))throw new FileNotFoundException();return ParcelFileDescriptor.open(UpdateManager.apk(getContext()),ParcelFileDescriptor.MODE_READ_ONLY);}
 @Override public Cursor query(Uri u,String[] projection,String selection,String[] args,String sort){try{path(u);}catch(Exception e){return null;}MatrixCursor c=new MatrixCursor(new String[]{"_display_name","_size"});c.addRow(new Object[]{"pi-console-update.apk",UpdateManager.apk(getContext()).length()});return c;}
 @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
 @Override public int update(Uri u,ContentValues v,String w,String[] args){throw new UnsupportedOperationException();}
 @Override public int delete(Uri u,String w,String[] args){throw new UnsupportedOperationException();}
}
