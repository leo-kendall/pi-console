// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
/** Normalized WebView routing keeps controls local and releases remote drags. */
final class DesktopPointer {
 private double left,top,right,bottom;private boolean dragging;
 void set(double l,double t,double r,double b){
  for(double v:new double[]{l,t,r,b})if(Double.isNaN(v)||Double.isInfinite(v)||v<0||v>1)throw new IllegalArgumentException("Invalid desktop bounds");
  if(r<l||b<t)throw new IllegalArgumentException("Invalid desktop bounds");left=l;top=t;right=r;bottom=b;
 }
 void reset(){dragging=false;}
 double[] sample(double x,double y,int buttons){
  if(Double.isNaN(x)||Double.isNaN(y)||Double.isInfinite(x)||Double.isInfinite(y)||right<=left||bottom<=top)return null;
  boolean inside=x>=left&&y>=top&&x<right&&y<bottom;if(!inside&&!dragging)return null;
  dragging=buttons!=0;
  return new double[]{Math.max(left,Math.min(Math.nextDown(right),x)),Math.max(top,Math.min(Math.nextDown(bottom),y))};
 }
}
