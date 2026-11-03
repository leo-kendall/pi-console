// SPDX-License-Identifier: Apache-2.0
// Real Guacamole layout/pixel checks; Firefox screenshots do not reproduce Android GPU defects.
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
const socket=new WebSocket('ws://127.0.0.1:19226/session');
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let serial=0;const waiting=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data),w=waiting.get(m.id);if(!w)return;waiting.delete(m.id);clearTimeout(w.timer);m.type==='error'?w.reject(Error(m.message)):w.resolve(m.result);};
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>reject(Error('Timeout '+method)),20000);waiting.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});}
await call('session.new',{capabilities:{alwaysMatch:{}}});
const context=(await call('browsingContext.getTree')).contexts[0].context;
async function evaluate(expression){const r=await call('script.evaluate',{expression,target:{context},awaitPromise:true});if(r.type==='exception')throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(expr){for(let i=0;i<60;i++){if(await evaluate(expr))return;await delay(100);}throw Error('Timeout: '+expr);}
async function saveScreenshot(name){if(!process.env.PI_TEST_SCREENSHOT_DIR)return;mkdirSync(process.env.PI_TEST_SCREENSHOT_DIR,{recursive:true});const shot=await call('browsingContext.captureScreenshot',{context,origin:'viewport'});writeFileSync(join(process.env.PI_TEST_SCREENSHOT_DIR,name+'.png'),Buffer.from(shot.data,'base64'));}
async function checkPixels(){
 await waitFor("!$('desktop').getAnimations().some(a=>a.playState==='running')");
 await evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))");
 const coordinates=JSON.parse(await evaluate("JSON.stringify({w:innerWidth,h:innerHeight,box:(()=>{const b=$('screen').getBoundingClientRect();return [b.x,b.y,b.width,b.height];})()})"));
 const shot=await call('browsingContext.captureScreenshot',{context,origin:'viewport'});
 const pixels=JSON.parse(await evaluate(`(async()=>{const m=${JSON.stringify(coordinates)},image=new Image();image.src='data:image/png;base64,'+${JSON.stringify(shot.data)};await image.decode();const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);const [x,y,w,h]=m.box,sx=canvas.width/m.w,sy=canvas.height/m.h;return JSON.stringify([.05,.5,.56,.58,.7,.9,.99].map(f=>Array.from(ctx.getImageData(Math.round((x+w*f)*sx),Math.round((y+h*.55)*sy),1,1).data).slice(0,3)));})()`));
 assert.deepEqual(pixels,Array(7).fill([31,177,107]),'Presented window has color across old/new resize boundary and right edge');
}
async function checkBounds(){
 assert.equal(await evaluate("(()=>{const d=desktopClient.getDisplay(),b=$('screen').getBoundingClientRect(),inner=d.getElement().firstElementChild,r=inner.getBoundingClientRect();return Math.abs(b.width-r.width)<1&&Math.abs(b.height-r.height)<1&&Math.abs(r.width-d.getWidth()*d.getScale())<1;})()"),true,'Decoded layer, input bounds and scaled viewport agree without double scaling');
}
try{
 await call('browsingContext.setViewport',{context,viewport:{width:392,height:802},devicePixelRatio:2.75});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});await waitFor("page==='settings'");
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate(`window.reads=0;window.incoming='';window.sent=[];
 const frame=(...parts)=>parts.map(p=>String(p).length+'.'+p).join(',')+';';
 window.coloredFrame=(w,h)=>frame('size',0,w,h)+frame('rect',0,0,0,w,h)+frame('cfill',14,0,31,177,107,255)+frame('sync',1);
 api=async(path,body)=>{if(path==='/api/desktop/open')return {id:'presentation-test',protocol:'rdp'};if(path.startsWith('/api/desktop/write/')){sent.push(body.data);return {ok:true};}if(path.startsWith('/api/desktop/read/')){if(reads++===0)return {data:coloredFrame(1280,800)};await new Promise(r=>setTimeout(r,100));const data=incoming;incoming='';return {data:data+frame('sync',reads)};}return {ok:true};};
 navigate('desktop');$('desktop-connect').click();void 0`);
 await waitFor('desktopClient?.getDisplay().getWidth()===1280');
 await waitFor("desktopClient.getDisplay().flatten().getContext('2d').getImageData(100,100,1,1).data[1]===177");
 await waitFor("!$('desktop').getAnimations().some(a=>a.playState==='running')");
 assert.equal(await evaluate("getComputedStyle(desktopClient.getDisplay().getElement().firstElementChild).transform"),'none','Framebuffer root uses layout scaling instead of a composited CSS transform');
 await checkBounds();await checkPixels();
 await call('browsingContext.setViewport',{context,viewport:{width:818,height:392},devicePixelRatio:2.75});
 await evaluate("setDeviceLandscape(true);incoming=coloredFrame(2250,1080);void 0");await waitFor('desktopClient.getDisplay().getWidth()===2250');await delay(250);
 await checkBounds();await checkPixels();
 await evaluate("$('toast').hidden=true;appBack();void 0");await saveScreenshot('desktop-landscape-controls');await evaluate("$('desk-controls').click();void 0");
 // Keep a real cursor layer/hotspot and test its displayed position under layout zoom.
 await evaluate("(()=>{const d=desktopClient.getDisplay(),layer=d.getCursorLayer();layer.resize(16,16);d.cursorHotspotX=3;d.cursorHotspotY=4;d.showCursor(true);d.moveCursor(2000,900);})();void 0");
 assert.equal(await evaluate("(()=>{const d=desktopClient.getDisplay(),b=d.getElement().getBoundingClientRect(),c=d.getCursorLayer().getElement().getBoundingClientRect();return Math.abs(c.left-b.left-(2000-3)*d.getScale())<1&&Math.abs(c.top-b.top-(900-4)*d.getScale())<1;})()"),true,'Cursor retains remote coordinates and hotspot after resize');
 await evaluate("desktopClient.getDisplay().showCursor(false);$('desk-inspect').click();void 0");await waitFor("$('sheet').open");
 assert.equal(await evaluate("Boolean($('desk-presentation-mode'))"),true,'User can return to previous presentation path without reconnecting');
 await evaluate("$('desk-presentation-mode').click();void 0");await waitFor("!$('sheet').open");
 assert.equal(await evaluate("getComputedStyle(desktopClient.getDisplay().getElement().firstElementChild).transform.startsWith('matrix')"),true,'Previous transform presentation remains available');
 await checkBounds();await checkPixels();
 await evaluate("$('desk-inspect').click();void 0");await waitFor("$('sheet').open");await evaluate("$('desk-presentation-mode').click();void 0");await waitFor("!$('sheet').open");
 await checkBounds();await checkPixels();
 await evaluate("$('desk-zoom').click();void 0");await delay(150);await checkBounds();
 assert.equal(await evaluate('desktopClient.getDisplay().getScale()'),1,'1:1 zoom preserves input coordinate scale');
 await evaluate("$('desk-fit').click();void 0");await delay(100);await checkBounds();await checkPixels();
 // The reported2250x1080 desktop is shorter than the old200px minimum in portrait.
 await call('browsingContext.setViewport',{context,viewport:{width:392,height:802},devicePixelRatio:2.75});
 await evaluate('setDeviceLandscape(false);void 0');await delay(100);
 assert.equal(await evaluate("(()=>{const v=$('screen-scroll').getBoundingClientRect(),s=$('screen').getBoundingClientRect();return Math.abs(v.height-s.height)<1&&Math.abs(v.x+v.width/2-s.x-s.width/2)<1&&Math.abs(v.y+v.height/2-s.y-s.height/2)<1;})()"),true,'Portrait preview hugs the wide desktop and centers it without excess bottom space');
 await checkBounds();await checkPixels();
 await saveScreenshot('desktop-portrait-centered');
 // A tall remote display must also be centered horizontally, within60vh.
 await evaluate('incoming=coloredFrame(800,1200);void 0');await waitFor('desktopClient.getDisplay().getWidth()===800');await delay(100);
 assert.equal(await evaluate("(()=>{const v=$('screen-scroll').getBoundingClientRect(),s=$('screen').getBoundingClientRect();return Math.abs(v.x+v.width/2-s.x-s.width/2)<1&&Math.abs(v.y+v.height/2-s.y-s.height/2)<1&&s.height<=innerHeight*.6+1&&s.width<=v.width+1;})()"),true,'Tall desktop fits and centers inside available portrait space');
 await checkBounds();await checkPixels();
 console.log('Desktop presentation: colored screenshot columns, portrait→landscape 1280→2250 resize, cursor hotspot, no double scale, reversible modes and 1:1 zoom passed (Firefox, not Android hardware).');
}finally{await evaluate('stopDesktop();pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
