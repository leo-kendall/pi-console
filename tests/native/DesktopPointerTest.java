// SPDX-License-Identifier: Apache-2.0
package dev.piconsole;
public final class DesktopPointerTest {
 public static void main(String[] args){
  DesktopPointer p=new DesktopPointer();p.set(.1,.2,.8,.9);
  check(p.sample(.05,.3,0)==null,"toolbar mouse remains local");
  double[] point=p.sample(.4,.5,1);check(point[0]==.4&&point[1]==.5,"inside mouse captured");
  point=p.sample(1,1,0);check(point!=null&&point[0]<.8&&point[1]<.9,"drag release outside clamps to remote bounds");
  check(p.sample(1,1,0)==null,"capture ends after release");
  check(p.sample(Double.NaN,.5,1)==null,"nonfinite rejected");
  p.sample(.4,.5,1);p.reset();check(p.sample(1,1,0)==null,"focus reset clears drag");
  p.set(0,0,0,0);check(p.sample(.4,.5,1)==null,"disabled region keeps mouse local");
  boolean bad=false;try{p.set(-1,0,1,1);}catch(IllegalArgumentException e){bad=true;}check(bad,"out of range rejected");
  p.set(0,0,1,1,new double[][]{{.7,0,.85,.2},{.9,0,1,.2}});
  check(p.sample(.75,.1,1)==null,"overlaid target button click remains local");
  check(p.sample(.95,.1,0)==null,"collapsed Controls hover remains local");
  check(p.sample(.4,.5,1)!=null,"remote drag starts outside controls");
  check(p.sample(.75,.1,0)!=null,"remote drag release over button still reaches remote");
  check(p.sample(.75,.1,0)==null,"button hover local again after drag release");
  bad=false;try{p.set(0,0,1,1,new double[][]{{.8,0,.7,.2}});}catch(IllegalArgumentException e){bad=true;}check(bad,"malformed exclusion refused");
  System.out.println("Desktop pointer routing / outside releases / toolbar isolation tests passed");
 }
 static void check(boolean value,String reason){if(!value)throw new AssertionError(reason);}
}
