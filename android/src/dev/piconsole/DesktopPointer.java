// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
/** Normalized WebView routing keeps controls local and releases remote drags. */
final class DesktopPointer {
 private double left,top,right,bottom;private boolean dragging;
 private double[][] excluded=new double[0][];
 private static void check(double l,double t,double r,double b){
  for(double v:new double[]{l,t,r,b})if(Double.isNaN(v)||Double.isInfinite(v)||v<0||v>1)throw new IllegalArgumentException("Invalid desktop bounds");
  if(r<l||b<t)throw new IllegalArgumentException("Invalid desktop bounds");
 }
 void set(double l,double t,double r,double b){set(l,t,r,b,new double[0][]);}
 void set(double l,double t,double r,double b,double[][] holes){
  check(l,t,r,b);if(holes==null||holes.length>8)throw new IllegalArgumentException("Invalid desktop exclusions");
  double[][] copy=new double[holes.length][];
  for(int i=0;i<holes.length;i++){double[] e=holes[i];if(e==null||e.length!=4)throw new IllegalArgumentException("Invalid desktop exclusion");check(e[0],e[1],e[2],e[3]);copy[i]=e.clone();}
  left=l;top=t;right=r;bottom=b;excluded=copy;
 }
 void reset(){dragging=false;}
 double[] sample(double x,double y,int buttons){
  if(Double.isNaN(x)||Double.isNaN(y)||Double.isInfinite(x)||Double.isInfinite(y)||right<=left||bottom<=top)return null;
  if(!dragging)for(double[] e:excluded)if(x>=e[0]&&y>=e[1]&&x<e[2]&&y<e[3])return null;
  boolean inside=x>=left&&y>=top&&x<right&&y<bottom;if(!inside&&!dragging)return null;
  dragging=buttons!=0;
  return new double[]{Math.max(left,Math.min(Math.nextDown(right),x)),Math.max(top,Math.min(Math.nextDown(bottom),y))};
 }
}
