// SPDX-License-Identifier: Apache-2.0
// Optional Node 22+/Firefox BiDi smoke check against scripts/preview_ui.py.
import assert from 'node:assert/strict';
const socket=new WebSocket('ws://127.0.0.1:19226/session');
await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
let serial=0;const waiting=new Map();
socket.onmessage=e=>{const m=JSON.parse(e.data),w=waiting.get(m.id);if(!w)return;waiting.delete(m.id);clearTimeout(w.timer);m.type==='error'?w.reject(Error(m.message)):w.resolve(m.result);};
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++serial,timer=setTimeout(()=>reject(Error('Timeout '+method)),20000);waiting.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});}
await call('session.new',{capabilities:{alwaysMatch:{}}});
const context=(await call('browsingContext.getTree')).contexts[0].context;
async function evaluate(expression){const r=await call('script.evaluate',{expression,target:{context},awaitPromise:true});if(r.type==='exception')throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(expr){for(let i=0;i<130;i++){if(await evaluate(expr))return;await delay(100);}throw Error('Timeout: '+expr);}
try{
 await call('browsingContext.setViewport',{context,viewport:{width:818,height:392},devicePixelRatio:2});
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});await waitFor("page==='settings'");
 await evaluate("$('server-url').value='https://console.example.test';$('save-server').click();void 0");await waitFor("!$('pair').disabled");
 await evaluate("$('pair-code').value='ABCDEF12';$('pair').click();void 0");await waitFor('paired');
 await evaluate(`window.opened=[];window.sizeRequests=[];window.incoming='';window.reads=0;window.acceptSizes=true;window.clampSizes=false;
 const frame=(...parts)=>parts.map(p=>String(p).length+'.'+p).join(',')+';';
 const incomingParser=new Guacamole.Parser();incomingParser.oninstruction=(op,args)=>{if(op==='size'){const size=args.map(Number);sizeRequests.push(size);if(acceptSizes)incoming+=frame('size',0,...size)+frame('sync',Date.now());else if(clampSizes)incoming+=frame('size',0,1280,720)+frame('sync',Date.now());}};
 api=async(path,body)=>{if(path==='/api/desktop/open'){opened.push(body);reads=0;return {id:'display-settings-'+opened.length,protocol:'rdp'};}if(path.startsWith('/api/desktop/write/')){incomingParser.receive(body.data);return {ok:true};}if(path.startsWith('/api/desktop/read/')){if(reads++===0){const size=opened.at(-1);return {data:frame('size',0,size.width,size.height)+frame('sync',1)};}await new Promise(r=>setTimeout(r,100));const data=incoming;incoming='';return {data:data+frame('sync',reads)};}return {ok:true};};
 navigate('desktop');setDeviceLandscape(true);$('desktop-connect').click();void 0`);
 await waitFor('desktopClient?.getDisplay().getWidth()>0');
 assert.equal(await evaluate("Boolean($('desk-display'))"),true,'Connected session exposes display settings without disconnecting');
 async function settings(){await evaluate("if(fullscreenDesktop&&!document.body.classList.contains('desktop-controls-open'))$('desk-controls').click();$('desk-display').click();void 0");await waitFor("$('sheet').open&&Boolean($('desktop-size-choice'))");}
 async function choose(value){await evaluate(`$('desktop-size-choice').value=${JSON.stringify(value)};$('desktop-size-choice').dispatchEvent(new Event('change'));void 0`);}
 async function apply(){await evaluate("$('desktop-display-apply').click();void 0");await waitFor("!$('sheet').open");}
 await settings();
 const draftRequests=await evaluate('sizeRequests.length');
 await call('browsingContext.setViewport',{context,viewport:{width:818,height:300},devicePixelRatio:2});await delay(700);
 assert.equal(await evaluate('sizeRequests.length'),draftRequests,'Opening the keyboard while editing display settings never applies an automatic remote resize');
 await choose('1920,1080');await apply();await waitFor('desktopClient.getDisplay().getWidth()===1920&&desktopClient.getDisplay().getHeight()===1080');
 const requests=await evaluate('sizeRequests.length');
 await call('browsingContext.setViewport',{context,viewport:{width:392,height:802},devicePixelRatio:2});await evaluate('setDeviceLandscape(false);void 0');await delay(1100);
 assert.equal(await evaluate('sizeRequests.length'),requests,'Fixed resolution remains exact when phone rotates');
 await settings();await evaluate("$('desktop-ratio-choice').value='4:3';$('desktop-ratio-choice').dispatchEvent(new Event('change'));void 0");
 assert.equal(await evaluate("$('desktop-display-preview').textContent.includes('1920 × 1440')"),true,'Ratio change shows actual converted fixed pixel dimensions');
 await apply();await waitFor('desktopClient.getDisplay().getWidth()===1920&&desktopClient.getDisplay().getHeight()===1440');
 await settings();await choose('custom');await evaluate("$('desktop-custom-width').value='1921';$('desktop-custom-height').value='1080';$('desktop-display-apply').click();void 0");
 assert.equal(await evaluate("$('sheet').open&&$('desktop-display-error').textContent.length>0"),true,'Invalid odd custom dimensions stay in dialog with clear validation');
 await evaluate("$('desktop-custom-width').value='1600';$('desktop-custom-height').value='1200';void 0");await apply();await waitFor('desktopClient.getDisplay().getWidth()===1600&&desktopClient.getDisplay().getHeight()===1200');
 await settings();await choose('auto');await evaluate("$('desktop-ratio-choice').value='16:9';$('desktop-ratio-choice').dispatchEvent(new Event('change'));void 0");await apply();await delay(400);
 assert.equal(await evaluate("$('resolution').value==='auto'&&Math.abs(desktopClient.getDisplay().getWidth()/desktopClient.getDisplay().getHeight()-16/9)<.006"),true,'Adaptive resolution honors selected aspect without stretching the frame');
 // A backend that does not confirm resizing keeps its old framebuffer and reports the failure.
 const previous=await evaluate('desktopClient.getDisplay().getWidth()+","+desktopClient.getDisplay().getHeight()');
 await evaluate('acceptSizes=false;void 0');await settings();await choose('1024,768');await apply();await waitFor("$('desktop-status').textContent.includes('未确认')");
 assert.equal(await evaluate('desktopClient.getDisplay().getWidth()+","+desktopClient.getDisplay().getHeight()'),previous,'Unconfirmed request never pretends the remote framebuffer changed');
 await evaluate('clampSizes=true;window.clampStart=sizeRequests.length;void 0');await settings();await choose('1920,1200');await apply();
 await waitFor("($('desktop-status').textContent.includes('未确认')&&$('desktop-status').textContent.includes('1920 × 1200'))||sizeRequests.length-clampStart>5");
 assert.equal(await evaluate('sizeRequests.length-clampStart<=5'),true,'Repeated mismatched server replies cannot restart the same resize budget indefinitely');
 assert.equal(await evaluate("$('desktop-status').textContent.includes('未确认')"),true,'Clamped server replies report the unconfirmed target');
 const stoppedCount=await evaluate('sizeRequests.length');await delay(1400);assert.equal(await evaluate('sizeRequests.length'),stoppedCount,'No repeated background requests after resize budget is exhausted');
 await evaluate('acceptSizes=true;void 0');await settings();await apply();await waitFor('desktopClient.getDisplay().getWidth()===1920&&desktopClient.getDisplay().getHeight()===1200');
 assert.equal((await evaluate('sizeRequests.length'))>stoppedCount,true,'An explicit retry of the same target can recover after server resize support becomes available');
 assert.equal(await evaluate("JSON.parse(localStorage.getItem('desktop-display-settings')).resolution"),'1920,1200','Exact display choice is saved for next connection');
 await evaluate("stopDesktop();$('desktop-connect').click();void 0");await waitFor('desktopClient?.getDisplay().getWidth()===1920');
 assert.equal(await evaluate('opened.at(-1).width===1920&&opened.at(-1).height===1200'),true,'Reconnect uses saved fixed resolution in initial handshake');
 await evaluate('stopDesktop();void 0');
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});await waitFor("page==='settings'");
 assert.equal(await evaluate("$('resolution').value"),'1920,1200','Display preference survives a full page restart');
 await evaluate("localStorage.setItem('desktop-display-settings','{invalid');void 0");
 await call('browsingContext.navigate',{context,url:'http://127.0.0.1:18777',wait:'complete'});await waitFor("page==='settings'");
 assert.equal(await evaluate("$('resolution').value==='auto'&&$('desktop-ratio').value==='original'"),true,'Corrupt saved display settings recover to safe automatic defaults');
 console.log('Desktop display settings: live fixed/auto/aspect/custom choices, rotation stability, bounded validation, confirmed/unconfirmed resize and saved reconnect settings passed.');
}finally{await evaluate('stopDesktop();pauseApp();void 0').catch(()=>{});await call('session.end');socket.close();}
