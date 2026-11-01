
'use strict';
function fitScale(viewWidth,viewHeight,remoteWidth,remoteHeight,zoomed){
 if(zoomed||Math.min(viewWidth,viewHeight,remoteWidth,remoteHeight)<=0)return 1;
 return Math.min(viewWidth/remoteWidth,viewHeight/remoteHeight);
}
function desktopSize(width,height,density){
 const lower=Math.max(640/width,480/height),upper=Math.min(2560/width,1440/height);
 const scale=Math.min(upper,Math.max(lower,Math.min(3,density||1)));
 return {width:Math.max(640,Math.min(2560,Math.round(width*scale/2)*2)),height:Math.max(480,Math.min(1440,Math.round(height*scale/2)*2))};
}
const DESKTOP_RATIOS={'16:9':16/9,'16:10':16/10,'4:3':4/3,'3:2':3/2,'21:9':21/9};
function checkedDesktopResolution(value){
 if(typeof value!=='string'||!/^\d{3,4},\d{3,4}$/.test(value))throw new Error('请输入有效的宽度和高度');
 const [width,height]=value.split(',').map(Number);
 if(width<640||width>2560||height<480||height>1440)throw new Error('宽度范围为 640–2560，高度范围为 480–1440');
 if(width%2||height%2)throw new Error('宽度和高度须为偶数像素');
 return {width,height};
}
function requestedDesktopSize(selection,ratio,width,height,density){
 if(ratio!=='original'&&!Object.hasOwn(DESKTOP_RATIOS,ratio))throw new Error('无效的屏幕比例');
 if(selection!=='auto')return checkedDesktopResolution(selection);
 if(ratio!=='original'){
  const target=DESKTOP_RATIOS[ratio];if(width/height>target)width=height*target;else height=width/target;
 }
 return desktopSize(width,height,density);
}
function fixedDesktopAspect(width,height,ratio){
 if(ratio==='original')return checkedDesktopResolution(width+','+height);
 if(!Object.hasOwn(DESKTOP_RATIOS,ratio))throw new Error('无效的屏幕比例');
 const target=DESKTOP_RATIOS[ratio],lo=Math.max(640,480*target),hi=Math.min(2560,1440*target);
 width=Math.max(lo,Math.min(hi,width));return checkedDesktopResolution(Math.round(width/2)*2+','+Math.round(width/target/2)*2);
}
function positionDesktopCursor(display){
 // A moving cursor must not add another transformed canvas layer inside
 // the already-scaled framebuffer. Keep Guacamole's coordinates/hotspot
 // and cursor image, but position only its special cursor layer by layout.
 const cursor=display.getCursorLayer(),element=cursor.getElement();
 cursor.translate=function(x,y){
  cursor.x=x;cursor.y=y;
  element.style.left=x+'px';element.style.top=y+'px';
  element.style.transform=element.style.webkitTransform=element.style.WebkitTransform='none';
 };
 cursor.translate(cursor.x,cursor.y);
}
function configureDesktopScaling(display,initialMode){
 const root=display.getElement().firstElementChild,scale=display.scale;
 // Guacamole canvases use z-index:-1. Preserve their stacking context when
 // removing the transform so they cannot fall behind the viewport background.
 root.style.isolation='isolate';
 let mode='transform';
 const supported=typeof CSS!=='undefined'&&CSS.supports('zoom','1');
 display.scale=function(value){
  // Retain Guacamole's scale metadata and input bounds. Layout zoom avoids
  // scaling a retained compositor surface after a remote framebuffer resize.
  scale.call(display,value);
  root.style.zoom=mode==='layout'?String(value):'1';
  if(mode==='layout')for(const name of ['transform','WebkitTransform','MozTransform','OTransform','msTransform'])root.style[name]='none';
 };
 const controller={get mode(){return mode;},setMode(value){mode=value==='layout'&&supported?'layout':'transform';display.scale(display.getScale());return mode;}};
 controller.setMode(initialMode);return controller;
}
if(typeof module!=='undefined')module.exports={fitScale,desktopSize,checkedDesktopResolution,requestedDesktopSize,fixedDesktopAspect};
