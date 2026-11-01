
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
if(typeof module!=='undefined')module.exports={fitScale,desktopSize};
